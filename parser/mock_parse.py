#!/usr/bin/env python3
"""
Mock Recipe Parser for Testing
Generates structured steps using rule-based parsing instead of LLM
"""

import json
import re
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict

DATA_DIR = Path(__file__).parent.parent / "data"


@dataclass
class RecipeStep:
    """Structured recipe step"""

    id: str
    raw_text: str
    label: str
    type: str
    estimated_duration_minutes: int
    requires: List[str]
    can_overlap_with: List[str]
    equipment: List[str]
    temperature_c: Optional[int] = None
    notes: str = ""


@dataclass
class ParsedRecipe:
    """Recipe with parsed steps"""

    id: str
    title: str
    source_url: str
    week_label: Optional[str]
    category: Optional[str]
    ingredients: List[str]
    nutrition: Optional[Dict]
    steps: List[RecipeStep]


class MockRecipeParser:
    """Rule-based recipe parser for testing"""

    def __init__(self):
        pass

    def extract_steps_from_method(self, method: str) -> List[Dict]:
        """Extract steps from method text using simple sentence splitting"""
        # Split on sentence boundaries
        sentences = re.split(r"(?<=[.!?])\s+", method)

        steps = []
        step_num = 1

        for sentence in sentences:
            if len(sentence.strip()) < 10:
                continue

            # Determine step type
            step_type = "cook"
            if any(
                word in sentence.lower()
                for word in ["preheat", "prepare", "rinse", "chop", "dice", "slice", "mince"]
            ):
                step_type = "prep"
            elif any(word in sentence.lower() for word in ["serve", "garnish", "plate", "drizzle"]):
                step_type = "finish"

            # Extract duration
            duration = 10  # default
            time_match = re.search(r"(\d+)[-–]?(\d+)?\s*(minute|min)", sentence.lower())
            if time_match:
                if time_match.group(2):
                    # Range like "8-10 minutes"
                    duration = (int(time_match.group(1)) + int(time_match.group(2))) // 2
                else:
                    duration = int(time_match.group(1))

            # Extract temperature
            temp = None
            temp_match = re.search(r"(\d+)\s*°C", sentence)
            if temp_match:
                temp = int(temp_match.group(1))

            # Extract equipment
            equipment = []
            equip_keywords = ["oven", "pan", "pot", "bowl", "tray", "wok", "saucepan", "frying pan"]
            for equip in equip_keywords:
                if equip in sentence.lower():
                    equipment.append(equip)

            # Create step label (first 50 chars or until comma/period)
            label = sentence[:50]
            if "," in label:
                label = label[: label.index(",")]
            elif "." in label:
                label = label[: label.index(".")]

            step = {
                "id": f"step-{step_num}",
                "raw_text": sentence.strip(),
                "label": label.strip(),
                "type": step_type,
                "estimated_duration_minutes": duration,
                "requires": [f"step-{step_num - 1}"]
                if step_num > 1 and step_type != "prep"
                else [],
                "can_overlap_with": [],
                "equipment": equipment,
                "temperature_c": temp,
                "notes": "",
            }

            steps.append(step)
            step_num += 1

        return steps

    def parse_recipe(self, recipe: Dict) -> ParsedRecipe:
        """Parse a single recipe"""
        method = recipe.get("method", "").strip()
        steps_data = []

        if method:
            steps_data = self.extract_steps_from_method(method)

        steps = [RecipeStep(**step) for step in steps_data]

        return ParsedRecipe(
            id=recipe["id"],
            title=recipe["title"],
            source_url=recipe["source_url"],
            week_label=recipe.get("week_label"),
            category=recipe.get("category"),
            ingredients=recipe.get("ingredients", []),
            nutrition=recipe.get("nutrition"),
            steps=steps,
        )

    def parse_all_recipes(self, raw_recipes: List[Dict]) -> List[ParsedRecipe]:
        """Parse all recipes"""
        parsed_recipes = []

        for recipe in raw_recipes:
            try:
                parsed = self.parse_recipe(recipe)
                parsed_recipes.append(parsed)
                print(f"Parsed {recipe['title']}: {len(parsed.steps)} steps")
            except Exception as e:
                print(f"Error parsing {recipe['title']}: {e}")

        return parsed_recipes


def main():
    """Main parser execution"""
    print("=" * 60)
    print("Mock Recipe Parser (Rule-based)")
    print("=" * 60)

    # Load raw recipes
    raw_recipes_path = DATA_DIR / "raw_recipes.json"
    if not raw_recipes_path.exists():
        print(f"Error: {raw_recipes_path} not found")
        return

    with open(raw_recipes_path, "r", encoding="utf-8") as f:
        raw_recipes = json.load(f)

    print(f"Loaded {len(raw_recipes)} raw recipes\n")

    # Parse recipes
    parser = MockRecipeParser()
    parsed_recipes = parser.parse_all_recipes(raw_recipes)

    # Save parsed recipes
    output_path = DATA_DIR / "recipes_parsed.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(
            [asdict(r) for r in parsed_recipes],
            f,
            indent=2,
            ensure_ascii=False,
        )

    print(f"\n{'=' * 60}")
    print(f"Parsed {len(parsed_recipes)} recipes")
    print(f"Total steps: {sum(len(r.steps) for r in parsed_recipes)}")
    print(f"Saved to: {output_path}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
