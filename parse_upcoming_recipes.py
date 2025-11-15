#!/usr/bin/env python3
"""
Parse only the upcoming/current recipes with LLM.
This processes only the recipes identified by find_upcoming_recipes.py
"""

import json
import shutil
import sys
from pathlib import Path

project_root = Path(__file__).parent


def main():
    """Main entry point"""
    print("\n🤖 Planthood Upcoming Recipe Parser")
    print("=" * 80)
    print()

    # Check for upcoming recipes file
    upcoming_file = project_root / "data" / "upcoming_recipes.json"
    if not upcoming_file.exists():
        print("❌ No upcoming recipes file found.")
        print("   Run: pixi run python find_upcoming_recipes.py")
        return 1

    # Load upcoming recipes
    with open(upcoming_file, "r") as f:
        upcoming_recipes = json.load(f)

    print(f"📚 Loaded {len(upcoming_recipes)} upcoming recipes")
    print()

    if not upcoming_recipes:
        print("❌ No upcoming recipes to parse")
        return 1

    # Display what will be parsed
    print("📋 Recipes to parse:")
    print("=" * 80)
    for i, recipe in enumerate(upcoming_recipes, 1):
        title = recipe.get("title", "Untitled")
        has_method = len(recipe.get("method", "")) > 0
        status = "✅" if has_method else "❌"
        print(f"{i:3d}. {status} {title}")

    print()
    print(f"⚙️  This will:")
    print(f"   1. Parse {len(upcoming_recipes)} recipes with LLM (Gemini)")
    print(f"   2. Generate Gantt chart timelines")
    print(f"   3. Save to data/recipes_parsed.json and data/recipes_with_schedule.json")
    print()

    # Confirm
    if "--yes" not in sys.argv and "-y" not in sys.argv:
        response = input("Continue? [y/N]: ")
        if response.lower() != "y":
            print("Cancelled.")
            return 0

    # Backup existing files
    print("\n💾 Backing up existing parsed data...")
    raw_file = project_root / "data" / "raw_recipes.json"
    parsed_file = project_root / "data" / "recipes_parsed.json"
    scheduled_file = project_root / "data" / "recipes_with_schedule.json"

    backup_raw = project_root / "data" / "raw_recipes.backup.json"
    backup_parsed = project_root / "data" / "recipes_parsed.backup.json"
    backup_scheduled = project_root / "data" / "recipes_with_schedule.backup.json"

    # Backup raw_recipes.json
    if raw_file.exists():
        shutil.copy(raw_file, backup_raw)
        print(f"   ✓ Backed up raw_recipes.json")

    # Backup existing parsed files if they exist
    if parsed_file.exists():
        shutil.copy(parsed_file, backup_parsed)
        print(f"   ✓ Backed up recipes_parsed.json")

    if scheduled_file.exists():
        shutil.copy(scheduled_file, backup_scheduled)
        print(f"   ✓ Backed up recipes_with_schedule.json")

    try:
        # Write upcoming recipes as temporary raw_recipes.json
        with open(raw_file, "w") as f:
            json.dump(upcoming_recipes, f, indent=2, ensure_ascii=False)

        # Step 1: Parse with LLM
        print("\n📝 Step 1: Parsing with LLM...")
        print("=" * 80)

        from parser.parse import main as parser_main

        parser_main()

        # Step 2: Generate schedules
        print("\n📅 Step 2: Generating Gantt charts...")
        print("=" * 80)

        from scheduler.schedule import main as scheduler_main

        scheduler_main()

        print("\n✅ Processing complete!")
        print("=" * 80)

        # Display results
        if parsed_file.exists():
            with open(parsed_file, "r") as f:
                parsed = json.load(f)

            total_steps = sum(len(r.get("steps", [])) for r in parsed)
            print(f"\n📊 Results:")
            print(f"   Recipes parsed: {len(parsed)}")
            print(f"   Total steps extracted: {total_steps}")
            print(f"   Average steps per recipe: {total_steps / len(parsed):.1f}")

        if scheduled_file.exists():
            with open(scheduled_file, "r") as f:
                scheduled = json.load(f)

            total_time = sum(r.get("total_time_min", 0) for r in scheduled)
            avg_time = total_time / len(scheduled) if scheduled else 0

            print(f"\n📅 Timing:")
            print(f"   Average cook time: {avg_time:.1f} minutes")

        print(f"\n💾 Output files:")
        print(f"   - data/recipes_parsed.json")
        print(f"   - data/recipes_with_schedule.json")
        print()
        print(f"💡 Next steps:")
        print(f"   1. Review the parsed recipes in data/recipes_parsed.json")
        print(f"   2. Build the site: pixi run build-site")
        print(f"   3. Test locally: pixi run dev-site")

    finally:
        # Restore original raw_recipes.json
        if backup_raw.exists():
            shutil.copy(backup_raw, raw_file)
            backup_raw.unlink()
            print(f"\n🔄 Restored original raw_recipes.json")

    return 0


if __name__ == "__main__":
    sys.exit(main())
