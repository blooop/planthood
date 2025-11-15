#!/usr/bin/env python3
"""
Recipe Parser with LLM-backed step extraction
Converts raw recipe method text into structured, dependency-aware steps
"""

import hashlib
import json
import os
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Optional, Dict

from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential

try:
    from .llm_providers import get_llm_provider  # pylint: disable=import-error,deprecated-module
except ImportError:
    # Fallback for running as script
    from llm_providers import get_llm_provider  # type: ignore # pylint: disable=import-error

load_dotenv()

# Configuration
DATA_DIR = Path(__file__).parent.parent / "data"
CACHE_DIR = Path(os.getenv("CACHE_DIR", DATA_DIR / ".cache"))
SKIP_CACHE = os.getenv("SKIP_CACHE", "false").lower() == "true"
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))


@dataclass
class RecipeStep:
    """Structured recipe step"""

    id: str
    raw_text: str
    label: str
    type: str  # prep, cook, finish
    estimated_duration_minutes: int
    requires: List[str]
    can_overlap_with: List[str]
    equipment: List[str]
    temperature_c: Optional[int] = None
    notes: str = ""

    def __post_init__(self):
        if not isinstance(self.requires, list):
            self.requires = []
        if not isinstance(self.can_overlap_with, list):
            self.can_overlap_with = []
        if not isinstance(self.equipment, list):
            self.equipment = []


@dataclass
class ParsedRecipe:
    """Recipe with parsed steps"""

    id: str
    title: str
    source_url: str
    week_label: Optional[str]
    category: Optional[str]
    ingredients: List[str]
    nutrition: Optional[Dict[str, float]]
    steps: List[RecipeStep]


class RecipeCache:
    """Simple file-based cache for parsed recipes"""

    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_key(self, recipe_id: str, method_text: str) -> str:
        """Generate cache key from recipe ID and method text"""
        content = f"{recipe_id}:{method_text}"
        return hashlib.sha256(content.encode()).hexdigest()

    def get(self, recipe_id: str, method_text: str) -> Optional[List[Dict]]:
        """Get cached parsed steps"""
        if SKIP_CACHE:
            return None

        cache_key = self._get_cache_key(recipe_id, method_text)
        cache_file = self.cache_dir / f"{cache_key}.json"

        if cache_file.exists():
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"Cache read error: {e}")
                return None
        return None

    def set(self, recipe_id: str, method_text: str, steps: List[Dict]):
        """Cache parsed steps"""
        cache_key = self._get_cache_key(recipe_id, method_text)
        cache_file = self.cache_dir / f"{cache_key}.json"

        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(steps, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Cache write error: {e}")


class RecipeParser:
    """LLM-powered recipe parser"""

    SYSTEM_PROMPT = """You are a recipe parsing assistant. Your task is to convert unstructured recipe method text into structured, dependency-aware steps suitable for Gantt chart visualization.

For each step, extract:
1. **label**: A short, clear action label (e.g., "Preheat oven", "Roast vegetables")
2. **type**: Classification as "prep", "cook", or "finish"
3. **estimated_duration_minutes**: Time in minutes (extract from text or estimate reasonably)
4. **equipment**: List of equipment used (e.g., ["oven", "frying pan"])
5. **temperature_c**: Temperature if mentioned (numeric only)
6. **requires**: IDs of steps that must complete before this one (e.g., ["step-1"])
7. **can_overlap_with**: IDs of steps that can run in parallel (e.g., ["step-3"])
8. **notes**: Any important contextual notes

Guidelines:
- Split method into atomic, actionable steps
- Extract explicit times; for ranges (e.g., "20-30 minutes"), use midpoint and note the range
- Estimate missing durations sensibly (e.g., "dice onions" = 5 min, "simmer" without time = 15 min)
- Infer dependencies from text cues: "once X is done", "while X cooks", "meanwhile", "after"
- Identify parallel work opportunities (can_overlap_with)
- Number steps sequentially: step-1, step-2, etc.

Respond ONLY with valid JSON array of steps. No additional text."""

    USER_PROMPT_TEMPLATE = """Recipe: {title}

Ingredients:
{ingredients}

Method:
{method}

Parse this into structured steps as JSON array."""

    def __init__(self, llm_provider=None):
        self.llm = llm_provider or get_llm_provider()
        self.cache = RecipeCache(CACHE_DIR)
        print(f"Using LLM provider: {self.llm.get_name()}")

    @retry(
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    def _call_llm(self, prompt: str) -> str:
        """Call LLM with retries"""
        return self.llm.generate(prompt, system_prompt=self.SYSTEM_PROMPT)

    def parse_recipe_steps(self, recipe: Dict) -> List[RecipeStep]:
        """Parse recipe method into structured steps"""
        recipe_id = recipe["id"]
        method = recipe.get("method", "").strip()

        if not method:
            print(f"Warning: No method text for {recipe_id}, skipping")
            return []

        # Check cache
        cached_steps = self.cache.get(recipe_id, method)
        if cached_steps:
            print(f"Cache hit for {recipe_id}")
            return [RecipeStep(**step) for step in cached_steps]

        # Build prompt
        ingredients_text = "\n".join(f"- {ing}" for ing in recipe.get("ingredients", []))
        prompt = self.USER_PROMPT_TEMPLATE.format(
            title=recipe["title"],
            ingredients=ingredients_text or "(not provided)",
            method=method,
        )

        try:
            print(f"Parsing {recipe_id} with LLM...")
            response = self._call_llm(prompt)

            # Extract JSON from response (in case LLM adds extra text)
            response = response.strip()
            if response.startswith("```"):
                # Remove markdown code blocks
                lines = response.split("\n")
                response = "\n".join(line for line in lines if not line.startswith("```"))

            steps_data = json.loads(response)

            # Validate and create RecipeStep objects
            steps = []
            for i, step_data in enumerate(steps_data, 1):
                # Ensure ID is set
                if "id" not in step_data:
                    step_data["id"] = f"step-{i}"

                # Ensure raw_text is set
                if "raw_text" not in step_data:
                    step_data["raw_text"] = step_data.get("label", "")

                # Validate required fields
                required = ["label", "type", "estimated_duration_minutes"]
                if not all(k in step_data for k in required):
                    print(f"Warning: Step {i} missing required fields, skipping")
                    continue

                steps.append(RecipeStep(**step_data))

            # Cache successful parse
            self.cache.set(recipe_id, method, [asdict(s) for s in steps])

            print(f"Parsed {len(steps)} steps for {recipe_id}")
            return steps

        except json.JSONDecodeError as e:
            print(f"Failed to parse JSON response for {recipe_id}: {e}")
            print(f"Response: {response[:200]}...")
            return []
        except Exception as e:
            print(f"Error parsing {recipe_id}: {e}")
            return []

    def parse_all_recipes(self, raw_recipes: List[Dict]) -> List[ParsedRecipe]:
        """Parse all recipes"""
        parsed_recipes = []

        for recipe in raw_recipes:
            steps = self.parse_recipe_steps(recipe)

            parsed_recipe = ParsedRecipe(
                id=recipe["id"],
                title=recipe["title"],
                source_url=recipe["source_url"],
                week_label=recipe.get("week_label"),
                category=recipe.get("category"),
                ingredients=recipe.get("ingredients", []),
                nutrition=recipe.get("nutrition"),
                steps=steps,
            )
            parsed_recipes.append(parsed_recipe)

        return parsed_recipes


def main():
    """Main parser execution"""
    print("=" * 60)
    print("Recipe Parser (LLM-backed)")
    print("=" * 60)

    # Load raw recipes
    raw_recipes_path = DATA_DIR / "raw_recipes.json"
    if not raw_recipes_path.exists():
        print(f"Error: {raw_recipes_path} not found")
        print("Run the scraper first: npm run scrape")
        return

    with open(raw_recipes_path, "r", encoding="utf-8") as f:
        raw_recipes = json.load(f)

    print(f"Loaded {len(raw_recipes)} raw recipes")

    # Parse recipes
    parser = RecipeParser()
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
