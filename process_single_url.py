#!/usr/bin/env python3
"""
Process a specific recipe URL from Planthood.
Scrapes, parses, and schedules a single recipe by URL.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

# Ensure local parser module is found before stdlib's deprecated parser module
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from parser.parse import RecipeParser
from scraper.scrape import PlanthoodScraper
from scheduler.schedule import RecipeScheduler
from dataclasses import asdict


def _handle_error(error: Exception, prefix: str = "Error") -> str:
    """Handle and display error with traceback"""
    error_msg = str(error)
    print(f"{prefix}: {error_msg}")
    import traceback
    traceback.print_exc()
    return error_msg


def scrape_single_url(url: str):
    """Scrape a single recipe URL"""
    print(f"\nScraping recipe from: {url}")
    print("-" * 80)
    
    try:
        scraper = PlanthoodScraper()
        recipe = scraper.extract_recipe(url)
        
        if recipe:
            print(f"Successfully scraped: {recipe.title}")
            print(f"   ID: {recipe.id}")
            print(f"   Method length: {len(recipe.method)} chars")
            print(f"   Ingredients: {len(recipe.ingredients)} items")
            return recipe, None
        else:
            error = "Failed to extract recipe data"
            print(f"Error: {error}")
            return None, error
            
    except Exception as e:
        return None, _handle_error(e, "Scraping failed")


def parse_recipe(recipe):
    """Parse a recipe with LLM"""
    print("\nParsing with LLM...")
    print("-" * 80)

    try:
        parser = RecipeParser()
        
        # Convert Recipe dataclass to dict format expected by parser
        recipe_dict = {
            "id": recipe.id,
            "title": recipe.title,
            "source_url": recipe.source_url,
            "week_label": recipe.week_label,
            "category": recipe.category,
            "ingredients": recipe.ingredients,
            "nutrition": recipe.nutrition,
            "method": recipe.method,
        }
        
        steps = parser.parse_recipe_steps(recipe_dict)

        if steps:
            # Convert to dict format
            parsed_recipe = {
                "id": recipe.id,
                "title": recipe.title,
                "source_url": recipe.source_url,
                "week_label": recipe.week_label,
                "category": recipe.category,
                "ingredients": recipe.ingredients,
                "nutrition": recipe.nutrition,
                "steps": [asdict(step) for step in steps],
            }
            print(f"Parsed {len(steps)} steps")
            return parsed_recipe, None

        error = "No steps extracted"
        print(f"Error: {error}")
        return None, error

    except Exception as e:
        return None, _handle_error(e, "Parsing failed")


def schedule_recipe(parsed_recipe):
    """Generate Gantt chart schedule for a recipe"""
    print("\nGenerating Gantt chart schedule...")
    print("-" * 80)

    try:
        scheduler = RecipeScheduler()
        scheduled_recipe_obj = scheduler.schedule_recipe(parsed_recipe)

        # Convert to dict
        scheduled_recipe = asdict(scheduled_recipe_obj)

        total_time = scheduled_recipe.get("total_time_min", 0)
        print(f"Scheduled: {total_time} minutes total")
        return scheduled_recipe, None

    except Exception as e:
        return None, _handle_error(e, "Scheduling failed")


def save_processed_recipe(scraped_recipe, parsed_recipe, scheduled_recipe):
    """Save the processed recipe to data files"""
    print("\nSaving processed recipe...")
    print("-" * 80)
    
    # File paths
    raw_file = project_root / "data" / "raw_recipes.json"
    parsed_file = project_root / "data" / "recipes_parsed.json"
    scheduled_file = project_root / "data" / "recipes_with_schedule.json"
    
    recipe_id = scraped_recipe.id
    
    # Load existing data
    existing_raw = []
    existing_parsed = []
    existing_scheduled = []
    
    if raw_file.exists():
        with open(raw_file, "r", encoding="utf-8") as f:
            existing_raw = json.load(f)
    
    if parsed_file.exists():
        with open(parsed_file, "r", encoding="utf-8") as f:
            existing_parsed = json.load(f)
    
    if scheduled_file.exists():
        with open(scheduled_file, "r", encoding="utf-8") as f:
            existing_scheduled = json.load(f)
    
    # Remove old versions if they exist
    existing_raw = [r for r in existing_raw if r.get("id") != recipe_id]
    existing_parsed = [r for r in existing_parsed if r.get("id") != recipe_id]
    existing_scheduled = [r for r in existing_scheduled if r.get("id") != recipe_id]
    
    # Add new versions
    existing_raw.append(asdict(scraped_recipe))
    existing_parsed.append(parsed_recipe)
    existing_scheduled.append(scheduled_recipe)
    
    # Save all files
    with open(raw_file, "w", encoding="utf-8") as f:
        json.dump(existing_raw, f, indent=2, ensure_ascii=False)
        f.write("\n")
    
    with open(parsed_file, "w", encoding="utf-8") as f:
        json.dump(existing_parsed, f, indent=2, ensure_ascii=False)
        f.write("\n")
    
    with open(scheduled_file, "w", encoding="utf-8") as f:
        json.dump(existing_scheduled, f, indent=2, ensure_ascii=False)
        f.write("\n")
    
    print(f"Saved to:")
    print(f"   {raw_file}")
    print(f"   {parsed_file}")
    print(f"   {scheduled_file}")


def main():
    """Main entry point"""
    if len(sys.argv) != 2:
        print("Usage: python process_single_url.py <recipe_url>")
        print("\nExample:")
        print("   python process_single_url.py https://planthood.co.uk/products/recipe-name")
        return 1
    
    url = sys.argv[1]
    
    # Validate URL
    if not url.startswith("https://planthood.co.uk/products/"):
        print("Error: URL must be a Planthood recipe URL")
        print("Format: https://planthood.co.uk/products/recipe-name")
        return 1
    
    print("\nProcess Single Recipe URL")
    print("=" * 80)
    print(f"URL: {url}")
    
    # Step 1: Scrape the recipe
    scraped_recipe, scrape_error = scrape_single_url(url)
    if scraped_recipe is None:
        print(f"\nFailed to scrape recipe: {scrape_error}")
        return 1
    
    # Check if recipe has method text
    if not scraped_recipe.method:
        print("\nSkipping: Recipe has no method text to parse")
        return 1
    
    # Step 2: Parse the recipe with LLM
    parsed_recipe, parse_error = parse_recipe(scraped_recipe)
    if parsed_recipe is None:
        print(f"\nFailed to parse recipe: {parse_error}")
        return 1
    
    # Step 3: Schedule the recipe
    scheduled_recipe, schedule_error = schedule_recipe(parsed_recipe)
    if scheduled_recipe is None:
        print(f"\nFailed to schedule recipe: {schedule_error}")
        return 1
    
    # Step 4: Save the results
    save_processed_recipe(scraped_recipe, parsed_recipe, scheduled_recipe)
    
    print("\nSUCCESS!")
    print("=" * 80)
    print(f"Recipe processed: {scraped_recipe.title}")
    print(f"   Steps extracted: {len(parsed_recipe.get('steps', []))}")
    print(f"   Total time: {scheduled_recipe.get('total_time_min', 0)} minutes")
    print(f"   Active time: {scheduled_recipe.get('active_time_min', 0)} minutes")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())