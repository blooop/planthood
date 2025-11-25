import json
import os
import time
from typing import Dict
import requests
from playwright.sync_api import sync_playwright

# Configuration
BASE_URL = "https://planthood.co.uk"
COOKING_INSTRUCTIONS_URL = f"{BASE_URL}/collections/cooking-instructions"
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
OUTPUT_FILE = os.path.join(DATA_DIR, "weekly_schedule.json")


def fetch_product_map() -> Dict[str, str]:
    """
    Fetch all products from Shopify API and create a map of Title -> URL.
    This is needed because the week view only shows titles, but we need URLs.
    """
    print("Fetching product map from Shopify API...")
    title_to_url = {}
    page = 1
    limit = 250

    while True:
        try:
            url = f"{BASE_URL}/products.json?limit={limit}&page={page}"
            print(f"  Fetching page {page}...")
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()

            products = data.get("products", [])
            if not products:
                break

            for product in products:
                title = product.get("title", "").strip()
                handle = product.get("handle", "")
                if title and handle:
                    # Normalize title for better matching
                    title_to_url[title] = f"{BASE_URL}/products/{handle}"
                    # Also store lowercase version
                    title_to_url[title.lower()] = f"{BASE_URL}/products/{handle}"

            if len(products) < limit:
                break
            page += 1

        except Exception as e:
            print(f"Error fetching products page {page}: {e}")
            break

    print(f"Mapped {len(title_to_url)} product titles to URLs")
    return title_to_url


def scrape_weeks():
    """
    Scrape the weekly schedule using Playwright.
    """
    # Ensure data directory exists
    os.makedirs(DATA_DIR, exist_ok=True)

    # 1. Get the product map first
    title_to_url = fetch_product_map()

    print(f"Starting browser automation to scrape weeks from {COOKING_INSTRUCTIONS_URL}...")

    with sync_playwright() as p:
        # Launch browser
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        # Go to page
        print("Navigating to page...")
        page.goto(COOKING_INSTRUCTIONS_URL, timeout=60000)
        page.wait_for_load_state("domcontentloaded")

        # Find the dropdown
        select_selector = "select.ph-input"
        page.wait_for_selector(select_selector, timeout=30000)

        # Wait for options to be populated (dynamic loading)
        print("Waiting for week options to load...")
        try:
            page.wait_for_function(
                f"document.querySelector('{select_selector}').options.length > 1", timeout=60000
            )
        except Exception as e:
            print(f"Error waiting for options: {e}")
            # Debug snapshot
            page.screenshot(path="debug_screenshot_timeout.png")
            with open("debug_page_timeout.html", "w", encoding="utf-8") as f:
                f.write(page.content())
            raise

        # Get all options
        options = page.eval_on_selector(
            select_selector,
            """
            (select) => Array.from(select.options)
                .filter(opt => opt.value && opt.value !== "" && !opt.disabled)
                .map(opt => ({ text: opt.text.trim(), value: opt.value }))
        """,
        )

        print(f"Found {len(options)} week options")

        weekly_schedule = {}

        for i, option in enumerate(options):
            week_label = option["text"]
            value = option["value"]
            print(f"[{i + 1}/{len(options)}] Processing week: {week_label} (value: {value})")

            # Select the option
            page.select_option(select_selector, value)

            # Wait for the content to update.
            time.sleep(3)

            # Extract recipe titles visible on the page
            # We look for h3 tags inside product cards or similar
            titles = page.evaluate("""
                () => {
                    const titles = [];
                    // Selector for titles in the grid
                    document.querySelectorAll('.product-card h3, .card-v3__title').forEach(el => {
                        if (el.offsetParent !== null) { // Check visibility
                            titles.push(el.textContent.trim());
                        }
                    });
                    return titles;
                }
            """)

            # Map titles to URLs
            week_urls = []
            for title in titles:
                # Try exact match
                url = title_to_url.get(title)
                if not url:
                    # Try case-insensitive
                    url = title_to_url.get(title.lower())

                if url:
                    week_urls.append(url)
                else:
                    print(f"  Warning: Could not find URL for recipe '{title}'")

            # Remove duplicates
            week_urls = sorted(list(set(week_urls)))

            if week_urls:
                weekly_schedule[week_label] = week_urls
                print(f"  Found {len(week_urls)} recipes")
            else:
                print("  No recipes found for this week")

        browser.close()

    # Save to file
    print(f"Saving schedule to {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(weekly_schedule, f, indent=2)

    print("Done!")


if __name__ == "__main__":
    scrape_weeks()
