#!/usr/bin/env python3
"""
Planthood Recipe Scraper
Fetches recipe and instruction pages from planthood.co.uk and extracts structured data.
"""

import json
import os
import re
import time
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

# Configuration
USER_AGENT = os.getenv("USER_AGENT", "Mozilla/5.0 (compatible; PlanthoodScraper/1.0)")
REQUEST_DELAY = float(os.getenv("REQUEST_DELAY", "1.0"))
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")


@dataclass
class Recipe:
    """Structured recipe data"""

    id: str
    title: str
    source_url: str
    week_label: Optional[str] = None
    category: Optional[str] = None
    ingredients: List[str] = None
    method: str = ""
    nutrition: Optional[Dict[str, float]] = None

    def __post_init__(self):
        if self.ingredients is None:
            self.ingredients = []
        if self.nutrition is None:
            self.nutrition = {}


class PlanthoodScraper:
    """Scraper for Planthood recipe pages"""

    BASE_URL = "https://planthood.co.uk"
    COOKING_INSTRUCTIONS_URL = f"{BASE_URL}/collections/cooking-instructions"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        self.visited_urls = set()

    def fetch_page(self, url: str) -> Optional[BeautifulSoup]:
        """Fetch and parse a page with rate limiting"""
        if url in self.visited_urls:
            return None

        try:
            print(f"Fetching: {url}")
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            self.visited_urls.add(url)
            time.sleep(REQUEST_DELAY)
            return BeautifulSoup(response.text, "lxml")
        except Exception as e:
            print(f"Error fetching {url}: {e}")
            return None

    def discover_recipe_urls(self) -> List[str]:
        """Discover recipe URLs using Shopify's products.json API with pagination"""
        recipe_urls = set()
        page = 1
        max_pages = 50  # Safety limit
        products_per_page = 250  # Shopify max

        # Non-recipe product patterns to filter out
        exclude_patterns = [
            "monday-deliveries",
            "thursday-deliveries",
            "gift-card",
            "weekend-box",
            "subscription",
            "delivery",
        ]

        print("Discovering recipes via Shopify API...")

        while page <= max_pages:
            url = f"{self.BASE_URL}/products.json?page={page}&limit={products_per_page}"
            print(f"Fetching page {page}...")

            try:
                response = self.session.get(url, timeout=30)
                response.raise_for_status()
                data = response.json()
                products = data.get("products", [])

                if not products:
                    print(f"No products on page {page}, stopping")
                    break

                found_on_page = 0
                for product in products:
                    handle = product.get("handle", "")
                    title = product.get("title", "")

                    # Skip non-recipe products
                    if any(pattern in handle.lower() for pattern in exclude_patterns):
                        continue

                    # Build product URL
                    product_url = f"{self.BASE_URL}/products/{handle}"

                    if product_url not in recipe_urls:
                        found_on_page += 1
                        recipe_urls.add(product_url)

                print(
                    f"  Found {found_on_page} recipes on page {page} (total: {len(products)} products)"
                )

                # If we got fewer products than the limit, we're on the last page
                if len(products) < products_per_page:
                    print(f"Last page reached ({len(products)} < {products_per_page})")
                    break

                page += 1
                time.sleep(REQUEST_DELAY)

            except Exception as e:
                print(f"Error fetching page {page}: {e}")
                break

        print(f"\nTotal discovered: {len(recipe_urls)} recipe URLs")
        return sorted(list(recipe_urls))

    def _extract_method_from_headers(self, soup: BeautifulSoup) -> str:
        """Extract method text by finding method/instruction headers"""
        for header in soup.find_all(["h2", "h3", "strong"]):
            header_text = header.get_text().lower()
            if not any(keyword in header_text for keyword in ["method", "instruction", "how to"]):
                continue

            # Get the next sibling(s) until next header
            method_parts = []
            for sibling in header.find_next_siblings():
                if sibling.name in ["h2", "h3"]:
                    break
                text = sibling.get_text(strip=True)
                if text:
                    method_parts.append(text)
            return "\n".join(method_parts)
        return ""

    def extract_recipe(self, url: str) -> Optional[Recipe]:
        """Extract recipe data from a recipe page"""
        soup = self.fetch_page(url)
        if not soup:
            return None

        try:
            # Extract recipe ID from URL
            recipe_id = url.split("/products/")[-1].split("?")[0]

            # Extract title
            title_elem = soup.find("h1", class_="product-single__title") or soup.find("h1")
            title = (
                title_elem.get_text(strip=True)
                if title_elem
                else recipe_id.replace("-", " ").title()
            )

            # Extract week label (if present in product description or tags)
            week_label = None
            week_patterns = [
                r"(?:MENU|Delivery)\s*(?:\||w/c)\s*(?:DELIVERED\s*)?([A-Z][a-z]+\s+\d{1,2}(?:st|nd|rd|th)?\s*[A-Z][a-z]+\s*\d{4})",
                r"(?:Week of|w/c)\s+(\d{1,2}/\d{1,2}/\d{4})",
            ]
            page_text = soup.get_text()
            for pattern in week_patterns:
                match = re.search(pattern, page_text, re.IGNORECASE)
                if match:
                    week_label = match.group(1) if match.lastindex else match.group(0)
                    break

            # Extract category (Detox/Nourish/Feast) if mentioned
            category = None
            for cat in ["Detox", "Nourish", "Feast", "Cleanse"]:
                if cat.lower() in page_text.lower():
                    category = cat
                    break

            # Extract ingredients
            ingredients = []
            ingredients_section = (
                soup.find(["div", "section"], class_=lambda x: x and "ingredient" in x.lower())
                if soup
                else None
            )
            if not ingredients_section:
                # Try alternative selectors
                for header in soup.find_all(["h2", "h3", "strong"]):
                    if "ingredient" in header.get_text().lower():
                        ingredients_section = header.find_next(["ul", "div"])
                        break

            if ingredients_section:
                for li in ingredients_section.find_all("li"):
                    ing_text = li.get_text(strip=True)
                    if ing_text:
                        ingredients.append(ing_text)

            # Extract method/instructions
            method = ""
            method_section = soup.find(
                ["div", "section"],
                class_=lambda x: x
                and ("method" in str(x).lower() or "instruction" in str(x).lower()),
            )
            if method_section:
                method = method_section.get_text(separator="\n", strip=True)
            else:
                # Try finding by header
                method = self._extract_method_from_headers(soup)

            # Extract nutrition info
            nutrition = {}
            nutrition_patterns = {
                "calories": r"(\d+)\s*kcal",
                "protein_g": r"Protein[:\s]*(\d+\.?\d*)g",
                "fat_g": r"Fat[:\s]*(\d+\.?\d*)g",
                "carbs_g": r"Carb(?:ohydrate)?s?[:\s]*(\d+\.?\d*)g",
                "fibre_g": r"Fibre[:\s]*(\d+\.?\d*)g",
                "salt_g": r"Salt[:\s]*(\d+\.?\d*)g",
            }

            for key, pattern in nutrition_patterns.items():
                match = re.search(pattern, page_text, re.IGNORECASE)
                if match:
                    try:
                        nutrition[key] = float(match.group(1))
                    except ValueError:
                        pass

            recipe = Recipe(
                id=recipe_id,
                title=title,
                source_url=url,
                week_label=week_label,
                category=category,
                ingredients=ingredients,
                method=method,
                nutrition=nutrition if nutrition else None,
            )

            print(f"Extracted recipe: {title}")
            return recipe

        except Exception as e:
            print(f"Error extracting recipe from {url}: {e}")
            return None

    def scrape_all(self, existing_recipes: Optional[List[Dict]] = None) -> List[Recipe]:
        """Scrape all recipes from Planthood, skipping already extracted ones"""
        # Track existing recipes by URL
        existing_by_url = {}
        if existing_recipes:
            for recipe_data in existing_recipes:
                url = recipe_data.get("source_url")
                if url:
                    existing_by_url[url] = recipe_data

        print(f"Loaded {len(existing_by_url)} existing recipes")

        # Discover all recipe URLs
        recipe_urls = self.discover_recipe_urls()

        # Separate new and existing URLs
        new_urls = [url for url in recipe_urls if url not in existing_by_url]
        existing_urls = [url for url in recipe_urls if url in existing_by_url]

        print("\nRecipe summary:")
        print(f"  Total discovered: {len(recipe_urls)}")
        print(f"  Already scraped: {len(existing_urls)}")
        print(f"  New to scrape: {len(new_urls)}")

        # Start with existing recipes
        recipes = []
        for url in existing_urls:
            # Convert dict back to Recipe object
            recipe_data = existing_by_url[url]
            recipe = Recipe(
                id=recipe_data["id"],
                title=recipe_data["title"],
                source_url=recipe_data["source_url"],
                week_label=recipe_data.get("week_label"),
                category=recipe_data.get("category"),
                ingredients=recipe_data.get("ingredients", []),
                method=recipe_data.get("method", ""),
                nutrition=recipe_data.get("nutrition"),
            )
            recipes.append(recipe)

        # Scrape new recipes
        print(f"\nScraping {len(new_urls)} new recipes...")
        for i, url in enumerate(new_urls, 1):
            print(f"[{i}/{len(new_urls)}] ", end="")
            recipe = self.extract_recipe(url)
            if recipe:
                recipes.append(recipe)

        return recipes


def main():
    """Main scraper execution"""
    print("=" * 60)
    print("Planthood Recipe Scraper")
    print("=" * 60)

    # Ensure data directory exists
    os.makedirs(DATA_DIR, exist_ok=True)

    # Load existing recipes if available
    output_path = os.path.join(DATA_DIR, "raw_recipes.json")
    manifest_path = os.path.join(DATA_DIR, "recipe_manifest.json")
    existing_recipes = None
    if os.path.exists(output_path):
        try:
            with open(output_path, "r", encoding="utf-8") as f:
                existing_recipes = json.load(f)
            print(f"Found existing recipes file with {len(existing_recipes)} recipes\n")
        except Exception as e:
            print(f"Warning: Could not load existing recipes: {e}\n")

    # Run scraper
    scraper = PlanthoodScraper()
    recipes = scraper.scrape_all(existing_recipes)

    # Save recipes to JSON
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump([asdict(r) for r in recipes], f, indent=2, ensure_ascii=False)

    # Save manifest tracking all URLs and their status
    manifest = {
        "total_recipes": len(recipes),
        "last_updated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "recipes": [
            {
                "id": recipe.id,
                "title": recipe.title,
                "url": recipe.source_url,
                "scraped": True,
                "week_label": recipe.week_label,
            }
            for recipe in recipes
        ],
    }
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print(f"\n{'=' * 60}")
    print(f"Total recipes: {len(recipes)}")
    if existing_recipes:
        new_count = len(recipes) - len(existing_recipes)
        print(f"  Previously scraped: {len(existing_recipes)}")
        print(f"  Newly added: {new_count}")
    print(f"Saved to: {output_path}")
    print(f"Manifest saved to: {manifest_path}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
