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
from urllib.parse import urljoin

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
        """Discover recipe URLs from the cooking instructions collection page"""
        soup = self.fetch_page(self.COOKING_INSTRUCTIONS_URL)
        if not soup:
            return []

        recipe_urls = set()

        # Method 1: Find all product links in the HTML
        for link in soup.find_all("a", href=True):
            href = link["href"]
            # Look for product pages (recipes)
            if "/products/" in href:
                full_url = urljoin(self.BASE_URL, href)
                recipe_urls.add(full_url)

        # Method 2: Extract from JavaScript data (for dynamically loaded pages)
        # Look for script tags containing product data
        for script in soup.find_all("script"):
            script_text = script.string
            if not script_text:
                continue

            # Look for product handles in JavaScript objects
            # Common patterns: {"handle":"product-name"} or /products/product-name
            product_handles = re.findall(r'["\']handle["\']\s*:\s*["\']([^"\']+)["\']', script_text)
            product_urls_in_js = re.findall(r'/products/([a-z0-9\-]+)', script_text)

            for handle in product_handles:
                if handle and handle not in ["monday-deliveries", "thursday-deliveries"]:
                    # Skip subscription boxes, focus on actual recipes
                    full_url = f"{self.BASE_URL}/products/{handle}"
                    recipe_urls.add(full_url)

            for url_path in product_urls_in_js:
                if url_path and url_path not in ["monday-deliveries", "thursday-deliveries"]:
                    full_url = f"{self.BASE_URL}/products/{url_path}"
                    recipe_urls.add(full_url)

        print(f"Discovered {len(recipe_urls)} recipe URLs")
        return list(recipe_urls)

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

    def scrape_all(self) -> List[Recipe]:
        """Scrape all recipes from Planthood"""
        recipe_urls = self.discover_recipe_urls()
        recipes = []

        for url in recipe_urls:
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

    # Run scraper
    scraper = PlanthoodScraper()
    recipes = scraper.scrape_all()

    # Save to JSON
    output_path = os.path.join(DATA_DIR, "raw_recipes.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump([asdict(r) for r in recipes], f, indent=2, ensure_ascii=False)

    print(f"\n{'=' * 60}")
    print(f"Scraped {len(recipes)} recipes")
    print(f"Saved to: {output_path}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
