#!/usr/bin/env python3
"""
Process the next unprocessed recipe from the upcoming recipes queue.
This allows incremental processing to avoid rate limits and make debugging easier.

Designed to run on a schedule (e.g., GitHub Actions cron) to process one recipe at a time.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

# Ensure local parser module is found before stdlib's deprecated parser module
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from parser.parse import RecipeParser  # noqa: E402 # pylint: disable=deprecated-module


def _handle_error(error: Exception, prefix: str = "Error") -> str:
    """Handle and display error with traceback"""
    error_msg = str(error)
    print(f"{prefix}: {error_msg}")
    import traceback

    traceback.print_exc()
    return error_msg


def load_processing_status():
    """Load the processing status metadata"""
    status_file = project_root / "data" / "processing_status.json"

    if not status_file.exists():
        return {"recipes": {}, "last_updated": None, "total_processed": 0}

    with open(status_file, "r", encoding="utf-8") as f:
        return json.load(f)


def save_processing_status(status):
    """Save the processing status metadata"""
    status_file = project_root / "data" / "processing_status.json"
    status["last_updated"] = datetime.now().isoformat()

    with open(status_file, "w", encoding="utf-8") as f:
        json.dump(status, f, indent=2, ensure_ascii=False)


def get_next_unprocessed_recipe():
    """Get the next recipe that hasn't been processed yet"""
    upcoming_file = project_root / "data" / "upcoming_recipes.json"

    if not upcoming_file.exists():
        print("No upcoming recipes found. Run: pixi run python find_upcoming_recipes.py")
        return None

    with open(upcoming_file, "r", encoding="utf-8") as f:
        upcoming_recipes = json.load(f)

    if not upcoming_recipes:
        print("No upcoming recipes in queue")
        return None

    # Load processing status
    status = load_processing_status()

    # Find first unprocessed recipe
    for recipe in upcoming_recipes:
        recipe_id = recipe["id"]
        recipe_status = status["recipes"].get(recipe_id, {})

        if not recipe_status.get("processed", False):
            return recipe, recipe_id, status

    return None, None, status


def parse_single_recipe(recipe):
    """Parse a single recipe with LLM"""
    from dataclasses import asdict

    print("\nParsing with LLM...")
    print("-" * 80)

    try:
        parser = RecipeParser()
        steps = parser.parse_recipe_steps(recipe)

        if steps:
            # Convert to dict format
            parsed_recipe = {
                "id": recipe["id"],
                "title": recipe["title"],
                "source_url": recipe["source_url"],
                "week_label": recipe.get("week_label"),
                "category": recipe.get("category"),
                "ingredients": recipe.get("ingredients", []),
                "nutrition": recipe.get("nutrition"),
                "steps": [asdict(step) for step in steps],
            }
            print(f"Parsed {len(steps)} steps")
            return parsed_recipe, None

        error = "No steps extracted"
        print(f"Error: {error}")
        return None, error

    except Exception as e:
        return None, _handle_error(e)


def schedule_single_recipe(parsed_recipe):
    """Generate Gantt chart schedule for a single recipe"""
    from scheduler.schedule import RecipeScheduler
    from dataclasses import asdict

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
        return None, _handle_error(e)


def merge_with_existing_recipes(new_parsed, new_scheduled, recipe_id):
    """Merge newly processed recipe with existing processed recipes"""
    parsed_file = project_root / "data" / "recipes_parsed.json"
    scheduled_file = project_root / "data" / "recipes_with_schedule.json"

    # Load existing
    existing_parsed = []
    existing_scheduled = []

    if parsed_file.exists():
        with open(parsed_file, "r", encoding="utf-8") as f:
            existing_parsed = json.load(f)

    if scheduled_file.exists():
        with open(scheduled_file, "r", encoding="utf-8") as f:
            existing_scheduled = json.load(f)

    # Remove old version of this recipe if it exists
    existing_parsed = [r for r in existing_parsed if r.get("id") != recipe_id]
    existing_scheduled = [r for r in existing_scheduled if r.get("id") != recipe_id]

    # Add new version
    existing_parsed.append(new_parsed)
    existing_scheduled.append(new_scheduled)

    # Save merged results
    with open(parsed_file, "w", encoding="utf-8") as f:
        json.dump(existing_parsed, f, indent=2, ensure_ascii=False)

    with open(scheduled_file, "w", encoding="utf-8") as f:
        json.dump(existing_scheduled, f, indent=2, ensure_ascii=False)

    print("\nSaved to data files")
    print(f"   Total parsed recipes: {len(existing_parsed)}")
    print(f"   Total scheduled recipes: {len(existing_scheduled)}")


def main():
    """Main entry point"""
    print("\nProcess Next Recipe")
    print("=" * 80)

    # Get next unprocessed recipe
    result = get_next_unprocessed_recipe()

    if result[0] is None:
        if result[2]:  # Have status but no unprocessed recipes
            status = result[2]
            total = status.get("total_processed", 0)
            print(f"\nAll recipes processed! ({total} total)")
            print("   Run 'pixi run python find_upcoming_recipes.py' to refresh the queue")
            return 0
        return 1

    recipe, recipe_id, status = result

    title = recipe.get("title", "Untitled")
    method_len = len(recipe.get("method", ""))

    print("\nNext Recipe:")
    print("=" * 80)
    print(f"   ID: {recipe_id}")
    print(f"   Title: {title}")
    print(f"   Method length: {method_len} chars")

    # Count processed vs remaining
    upcoming_file = project_root / "data" / "upcoming_recipes.json"
    with open(upcoming_file, "r", encoding="utf-8") as f:
        total_upcoming = len(json.load(f))

    processed_count = sum(r.get("processed", False) for r in status["recipes"].values())
    remaining_count = total_upcoming - processed_count

    print("\nProgress:")
    print(f"   Processed: {processed_count}/{total_upcoming}")
    print(f"   Remaining: {remaining_count}")

    # Check if recipe has method text
    if not recipe.get("method"):
        print("\nSkipping: Recipe has no method text")
        # Mark as processed but with error
        status["recipes"][recipe_id] = {
            "processed": True,
            "timestamp": datetime.now().isoformat(),
            "error": "No method text",
            "steps_extracted": 0,
        }
        save_processing_status(status)
        return 0

    # Parse the recipe
    parsed_recipe, parse_error = parse_single_recipe(recipe)

    if parsed_recipe is None:
        # Mark as processed with error
        status["recipes"][recipe_id] = {
            "processed": True,
            "timestamp": datetime.now().isoformat(),
            "error": parse_error or "Unknown error",
            "steps_extracted": 0,
        }
        save_processing_status(status)
        print("\nFailed to parse recipe")
        return 1

    # Schedule the recipe
    scheduled_recipe, schedule_error = schedule_single_recipe(parsed_recipe)

    if scheduled_recipe is None:
        # Mark as processed with error
        status["recipes"][recipe_id] = {
            "processed": True,
            "timestamp": datetime.now().isoformat(),
            "error": f"Scheduling failed: {schedule_error}",
            "steps_extracted": len(parsed_recipe.get("steps", [])),
        }
        save_processing_status(status)
        print("\nFailed to schedule recipe")
        return 1

    # Merge with existing recipes
    merge_with_existing_recipes(parsed_recipe, scheduled_recipe, recipe_id)

    # Update status
    status["recipes"][recipe_id] = {
        "processed": True,
        "timestamp": datetime.now().isoformat(),
        "steps_extracted": len(parsed_recipe.get("steps", [])),
        "total_time_min": scheduled_recipe.get("total_time_min", 0),
        "error": None,
    }
    status["total_processed"] = processed_count + 1
    save_processing_status(status)

    print("\nSuccessfully processed recipe!")
    print("=" * 80)
    print(f"   Steps extracted: {len(parsed_recipe.get('steps', []))}")
    print(f"   Total time: {scheduled_recipe.get('total_time_min', 0)} minutes")
    print(f"   Progress: {processed_count + 1}/{total_upcoming} recipes")

    if remaining_count > 1:
        print("\nRun again to process the next recipe:")
        print("   pixi run process-next-recipe")
        print("\n   Or let GitHub Actions run it on schedule")

    return 0


if __name__ == "__main__":
    sys.exit(main())
