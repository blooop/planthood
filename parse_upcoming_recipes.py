#!/usr/bin/env python3
"""
Parse only the upcoming/current recipes with LLM.
This processes only the recipes identified by find_upcoming_recipes.py
"""

import json
import shutil
import sys
from pathlib import Path

# Ensure local parser module is found before stdlib's deprecated parser module
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from parser.parse import RecipeParser  # noqa: E402 # pylint: disable=deprecated-module


def main():
    """Main entry point"""
    print("\nPlanthood Upcoming Recipe Parser")
    print("=" * 80)
    print()

    # Check for upcoming recipes file
    upcoming_file = project_root / "data" / "upcoming_recipes.json"
    if not upcoming_file.exists():
        print("No upcoming recipes file found.")
        print("   Run: pixi run python find_upcoming_recipes.py")
        return 1

    # Load upcoming recipes
    with open(upcoming_file, "r", encoding="utf-8") as f:
        upcoming_recipes = json.load(f)

    print(f"Loaded {len(upcoming_recipes)} upcoming recipes")
    print()

    if not upcoming_recipes:
        print("No upcoming recipes to parse")
        return 1

    # Display what will be parsed
    print("Recipes to parse:")
    print("=" * 80)
    for i, recipe in enumerate(upcoming_recipes, 1):
        title = recipe.get("title", "Untitled")
        has_method = len(recipe.get("method", "")) > 0
        status = "[OK]" if has_method else "[NO METHOD]"
        print(f"{i:3d}. {status} {title}")

    print()
    print("This will:")
    print(f"   1. Parse {len(upcoming_recipes)} recipes with LLM (Gemini)")
    print("   2. Generate Gantt chart timelines")
    print("   3. Save to data/recipes_parsed.json and data/recipes_with_schedule.json")
    print()

    # Confirm
    if "--yes" not in sys.argv and "-y" not in sys.argv:
        response = input("Continue? [y/N]: ")
        if response.lower() != "y":
            print("Cancelled.")
            return 0

    # Backup existing files
    print("\nBacking up existing parsed data...")
    raw_file = project_root / "data" / "raw_recipes.json"
    parsed_file = project_root / "data" / "recipes_parsed.json"
    scheduled_file = project_root / "data" / "recipes_with_schedule.json"

    backup_raw = project_root / "data" / "raw_recipes.backup.json"
    backup_parsed = project_root / "data" / "recipes_parsed.backup.json"
    backup_scheduled = project_root / "data" / "recipes_with_schedule.backup.json"

    # Backup raw_recipes.json
    if raw_file.exists():
        shutil.copy(raw_file, backup_raw)
        print("   Backed up raw_recipes.json")

    # Backup existing parsed files if they exist
    if parsed_file.exists():
        shutil.copy(parsed_file, backup_parsed)
        print("   Backed up recipes_parsed.json")

    if scheduled_file.exists():
        shutil.copy(scheduled_file, backup_scheduled)
        print("   Backed up recipes_with_schedule.json")

    try:
        # Write upcoming recipes as temporary raw_recipes.json
        with open(raw_file, "w", encoding="utf-8") as f:
            json.dump(upcoming_recipes, f, indent=2, ensure_ascii=False)

        # Step 1: Parse with LLM
        print("\nStep 1: Parsing with LLM...")
        print("=" * 80)

        parser = RecipeParser()
        # Parse all recipes and save to recipes_parsed.json
        parsed_recipes = parser.parse_all_recipes(upcoming_recipes)
        parsed_file = project_root / "data" / "recipes_parsed.json"
        with open(parsed_file, "w", encoding="utf-8") as f:
            json.dump([r.__dict__ for r in parsed_recipes], f, indent=2, ensure_ascii=False)

        # Step 2: Generate schedules
        print("\nStep 2: Generating Gantt charts...")
        print("=" * 80)

        from scheduler.schedule import main as scheduler_main

        scheduler_main()

        print("\nProcessing complete!")
        print("=" * 80)

        # Display results
        if parsed_file.exists():
            with open(parsed_file, "r", encoding="utf-8") as f:
                parsed = json.load(f)

            total_steps = sum(len(r.get("steps", [])) for r in parsed)
            print("\nResults:")
            print(f"   Recipes parsed: {len(parsed)}")
            print(f"   Total steps extracted: {total_steps}")
            print(f"   Average steps per recipe: {total_steps / len(parsed):.1f}")

        if scheduled_file.exists():
            with open(scheduled_file, "r", encoding="utf-8") as f:
                scheduled = json.load(f)

            total_time = sum(r.get("total_time_min", 0) for r in scheduled)
            avg_time = total_time / len(scheduled) if scheduled else 0

            print("\nTiming:")
            print(f"   Average cook time: {avg_time:.1f} minutes")

        print("\nOutput files:")
        print("   - data/recipes_parsed.json")
        print("   - data/recipes_with_schedule.json")
        print()
        print("Next steps:")
        print("   1. Review the parsed recipes in data/recipes_parsed.json")
        print("   2. Build the site: pixi run build-site")
        print("   3. Test locally: pixi run dev-site")

    finally:
        # Restore original raw_recipes.json
        if backup_raw.exists():
            shutil.copy(backup_raw, raw_file)
            backup_raw.unlink()
            print("\nRestored original raw_recipes.json")

    return 0


if __name__ == "__main__":
    sys.exit(main())
