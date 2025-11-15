#!/usr/bin/env python3
"""
Find upcoming/current recipes from the Planthood cooking instructions page.
This identifies which recipes are currently being delivered or will be delivered soon.
"""

import json
import os
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

# Configuration
USER_AGENT = os.getenv("USER_AGENT", "Mozilla/5.0 (compatible; PlanthoodScraper/1.0)")
BASE_URL = "https://planthood.co.uk"
COOKING_INSTRUCTIONS_URL = f"{BASE_URL}/collections/cooking-instructions"
project_root = Path(__file__).parent


def _is_recipe_url(url: str) -> bool:
    """Check if URL is a recipe (not a non-recipe product)"""
    exclude_patterns = ["gift-card", "monday-deliveries", "thursday-deliveries"]
    return not any(pattern in url.lower() for pattern in exclude_patterns)


def _extract_product_urls(soup: BeautifulSoup) -> set:
    """Extract all product URLs from page"""
    product_urls = set()
    for link in soup.find_all("a", href=True):
        href = link["href"]
        if "/products/" in href:
            full_url = href if href.startswith("http") else f"{BASE_URL}{href}"
            product_urls.add(full_url)
    return product_urls


def fetch_upcoming_recipes_from_page():
    """Fetch recipes displayed on the cooking instructions page"""
    print(f"Fetching: {COOKING_INSTRUCTIONS_URL}")
    print("=" * 80)

    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    try:
        response = session.get(COOKING_INSTRUCTIONS_URL, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "lxml")

        # Extract and filter product URLs
        product_urls = _extract_product_urls(soup)
        recipe_urls = {url for url in product_urls if _is_recipe_url(url)}

        print(f"Found {len(recipe_urls)} recipe URLs on cooking instructions page")
        return list(recipe_urls)

    except Exception as e:
        print(f"Error fetching page: {e}")
        return []


def fetch_recent_menu_collections():
    """Fetch recipes from recent weekly menu collections"""
    print("\nFetching recent menu collections from API")
    print("=" * 80)

    try:
        response = requests.get(f"{BASE_URL}/collections.json", timeout=30)
        response.raise_for_status()
        data = response.json()

        # Find menu collections
        menu_collections = [
            {"title": title, "handle": handle, "published_at": published_at}
            for coll in data.get("collections", [])
            if "menu" in (title := coll.get("title", "")).lower()
            or "menu" in (handle := coll.get("handle", "")).lower()
            for published_at in [coll.get("published_at", "")]
        ]

        # Sort by published date (most recent first)
        menu_collections.sort(key=lambda x: x.get("published_at", ""), reverse=True)

        print(f"Found {len(menu_collections)} menu collections")

        # Get recipes from the 3 most recent menus
        recent_recipe_urls = set()
        for menu in menu_collections[:3]:
            print(f"\nChecking: {menu['title']}")
            collection_url = f"{BASE_URL}/collections/{menu['handle']}/products.json"

            try:
                coll_response = requests.get(collection_url, timeout=30)
                coll_response.raise_for_status()
                coll_data = coll_response.json()
                products = coll_data.get("products", [])

                for product in products:
                    handle = product.get("handle", "")
                    if handle:
                        product_url = f"{BASE_URL}/products/{handle}"
                        recent_recipe_urls.add(product_url)

                print(f"   Found {len(products)} recipes")

            except Exception as e:
                print(f"   Warning: Error fetching collection: {e}")

        print(f"\nTotal recipes from recent menus: {len(recent_recipe_urls)}")
        return list(recent_recipe_urls)

    except Exception as e:
        print(f"Error fetching menu collections: {e}")
        return []


def match_recipes_to_scraped_data(upcoming_urls):
    """Match upcoming URLs to scraped recipe data"""
    data_file = project_root / "data" / "raw_recipes.json"

    if not data_file.exists():
        print("No scraped recipes found. Run 'pixi run scrape' first.")
        return []

    with open(data_file, "r", encoding="utf-8") as f:
        all_recipes = json.load(f)

    # Create URL to recipe mapping
    url_to_recipe = {recipe["source_url"]: recipe for recipe in all_recipes}

    # Find matching recipes
    return [url_to_recipe[url] for url in upcoming_urls if url in url_to_recipe]


def main():
    """Main entry point"""
    print("\nPlanthood Upcoming Recipe Finder")
    print("=" * 80)
    print()

    # Method 1: Get recipes from cooking instructions page
    page_urls = fetch_upcoming_recipes_from_page()

    # Method 2: Get recipes from recent menu collections
    menu_urls = fetch_recent_menu_collections()

    # Combine both methods
    all_upcoming_urls = set(page_urls + menu_urls)

    print("\nSummary:")
    print("=" * 80)
    print(f"Recipes from cooking instructions page: {len(page_urls)}")
    print(f"Recipes from recent menu collections: {len(menu_urls)}")
    print(f"Total unique upcoming recipes: {len(all_upcoming_urls)}")

    # Match to scraped data
    print("\nMatching to scraped recipes...")
    print("=" * 80)

    upcoming_recipes = match_recipes_to_scraped_data(all_upcoming_urls)

    if not upcoming_recipes:
        print("No matching recipes found in scraped data")
        return

    print(f"Matched {len(upcoming_recipes)} upcoming recipes")
    print()

    # Save to file
    output_file = project_root / "data" / "upcoming_recipes.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(upcoming_recipes, f, indent=2, ensure_ascii=False)

    print(f"Saved to: {output_file}")
    print()

    # Display recipes
    print("Upcoming Recipes:")
    print("=" * 80)
    for i, recipe in enumerate(upcoming_recipes, 1):
        title = recipe.get("title", "Untitled")
        recipe_id = recipe.get("id", "unknown")
        has_method = len(recipe.get("method", "")) > 0
        status = "[OK]" if has_method else "[NO METHOD]"

        print(f"{i:3d}. {status} {title}")
        print(f"      ID: {recipe_id}")
        print()

    print("\nNext steps:")
    print("   1. Review the upcoming recipes above")
    print("   2. Run: pixi run python parse_upcoming_recipes.py")
    print("      (This will parse only the upcoming recipes with LLM)")


if __name__ == "__main__":
    main()
