#!/usr/bin/env python3
"""
Test LLM parsing and Gantt chart generation on a single recipe.
Useful for testing before processing all 237 recipes.
"""

import json
import sys
from pathlib import Path

# Ensure local parser module is found before stdlib's deprecated parser module
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from parser.parse import RecipeParser  # noqa: E402 # pylint: disable=deprecated-module


def list_recipes(limit=20):
    """List available scraped recipes"""
    data_file = project_root / "data" / "raw_recipes.json"

    if not data_file.exists():
        print("No scraped recipes found. Run 'pixi run scrape' first.")
        return []

    with open(data_file, "r", encoding="utf-8") as f:
        recipes = json.load(f)

    print(f"\nFound {len(recipes)} scraped recipes")
    print(f"\nShowing first {min(limit, len(recipes))} recipes:")
    print("=" * 80)

    for i, recipe in enumerate(recipes[:limit], 1):
        title = recipe.get("title", "Untitled")
        recipe_id = recipe.get("id", "unknown")
        has_method = len(recipe.get("method", "")) > 0
        method_len = len(recipe.get("method", ""))
        status = "[OK]" if has_method else "[NO METHOD]"

        print(f"{i:3d}. {status} {title}")
        print(f"      ID: {recipe_id}")
        print(f"      Method text: {method_len} chars")
        print()

    return recipes


def parse_single_recipe(recipe_id: str):
    """Parse a single recipe using LLM and generate Gantt chart data"""
    print(f"\nProcessing recipe: {recipe_id}")
    print("=" * 80)

    # Load raw recipes
    data_file = project_root / "data" / "raw_recipes.json"
    with open(data_file, "r", encoding="utf-8") as f:
        recipes = json.load(f)

    # Find the recipe
    if not (recipe := next((r for r in recipes if r["id"] == recipe_id), None)):
        print(f"Recipe '{recipe_id}' not found")
        return False

    print(f"Found recipe: {recipe.get('title', 'Untitled')}")
    print(f"   Method length: {len(recipe.get('method', ''))} chars")

    if not recipe.get("method"):
        print("Recipe has no method text to parse")
        return False

    # Step 1: Parse with LLM
    print("\nStep 1: Parsing with LLM (Gemini)...")
    print("-" * 80)

    # Create a temporary file with just this recipe
    temp_raw = project_root / "data" / "temp_raw_recipes.json"
    with open(temp_raw, "w", encoding="utf-8") as f:
        json.dump([recipe], f, indent=2)
        f.write("\n")

    # Run parser (it will read from raw_recipes.json)
    # We need to temporarily replace raw_recipes.json
    backup_file = project_root / "data" / "raw_recipes.backup.json"
    raw_file = project_root / "data" / "raw_recipes.json"

    # Backup original
    import shutil

    shutil.copy(raw_file, backup_file)

    try:
        # Replace with single recipe
        shutil.copy(temp_raw, raw_file)

        # Run parser using the class interface
        parser = RecipeParser()
        with open(raw_file, "r", encoding="utf-8") as f:
            raw_recipes = json.load(f)
        parsed_recipes = parser.parse_all_recipes(raw_recipes)
        parsed_file = project_root / "data" / "recipes_parsed.json"
        with open(parsed_file, "w", encoding="utf-8") as f:
            json.dump([r.__dict__ for r in parsed_recipes], f, indent=2, ensure_ascii=False)
            f.write("\n")

        # Step 2: Run scheduler
        print("\nStep 2: Generating Gantt chart timeline...")
        print("-" * 80)

        from scheduler.schedule import main as scheduler_main

        scheduler_main()

        # Load and display results
        print("\nProcessing complete!")
        print("=" * 80)

        scheduled_file = project_root / "data" / "recipes_with_schedule.json"

        if parsed_file.exists():
            with open(parsed_file, "r", encoding="utf-8") as f:
                parsed = json.load(f)

            if parsed:
                print("\nParsed Recipe Data:")
                print(f"   Steps extracted: {len(parsed[0].get('steps', []))}")
                print("\n   First few steps:")
                for i, step in enumerate(parsed[0].get("steps", [])[:5], 1):
                    print(f"   {i}. {step.get('label', 'No label')}")
                    print(f"      Type: {step.get('type', 'unknown')}")
                    print(f"      Duration: {step.get('estimated_duration_minutes', '?')} min")
                    print()

        if scheduled_file.exists():
            with open(scheduled_file, "r", encoding="utf-8") as f:
                scheduled = json.load(f)

            if scheduled:
                print("\nGantt Chart Data:")
                print(f"   Total time: {scheduled[0].get('total_time_min', '?')} minutes")
                print(f"   Active time: {scheduled[0].get('active_time_min', '?')} minutes")
                print("\n   Timeline:")
                for step in scheduled[0].get("steps", [])[:10]:
                    start = step.get("start_min", 0)
                    end = step.get("end_min", 0)
                    label = step.get("label", "No label")
                    print(f"   {start:3d}-{end:3d} min: {label}")

        print("\nOutput files:")
        print("   - data/recipes_parsed.json")
        print("   - data/recipes_with_schedule.json")

        return True

    finally:
        # Restore original raw_recipes.json
        shutil.copy(backup_file, raw_file)
        backup_file.unlink()
        temp_raw.unlink()


def main():
    """Main entry point"""
    if len(sys.argv) > 1:
        # Recipe ID provided as argument
        recipe_id = sys.argv[1]
        parse_single_recipe(recipe_id)
    else:
        # Interactive mode
        recipes = list_recipes(limit=30)

        if not recipes:
            return

        print("\nUsage:")
        print(f"   python {sys.argv[0]} <recipe-id>")
        print("\nExample:")
        print(f"   python {sys.argv[0]} {recipes[0]['id']}")
        print("\nOr use pixi:")
        print(f"   pixi run python {sys.argv[0]} {recipes[0]['id']}")


if __name__ == "__main__":
    main()
