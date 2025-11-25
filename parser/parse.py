#!/usr/bin/env python3
"""
Recipe Parser with LLM-backed step extraction
Converts raw recipe method text into structured, dependency-aware steps
"""

import argparse
import hashlib
import json
import os
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Optional, Dict, Union

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
CACHE_VERSION = "v2-validated"


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
    weeks: List[str]
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
        content = f"{CACHE_VERSION}:{recipe_id}:{method_text}"
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
                f.write("\n")
        except Exception as e:
            print(f"Cache write error: {e}")


class RecipeParser:
    """LLM-powered recipe parser"""

    SYSTEM_PROMPT = """You are a careful recipe parsing assistant. Convert the method text into grounded, dependency-aware steps for a cooking Gantt chart.

Rules for each step:
- label: 3-8 word action.
- type: one of ["prep","cook","finish"] (prep = chopping/marinating/preheating, cook = heat applied, finish = plating/garnish/resting).
- estimated_duration_minutes: integer minutes; use midpoint for ranges and record the range in notes. Never output 0.
- equipment: list of tools explicitly mentioned or obviously implied (e.g., pan for frying, oven for bake/roast).
- temperature_c: numeric degrees C if specified. Leave null/omit if not mentioned.
- requires: ids of prerequisite steps that must finish before this one starts.
- can_overlap_with: ids of safe parallel steps (e.g., prep during simmer).
- notes: keep any timing ranges, doneness cues, or ordering clarifications.
- raw_text: short quote/sentence fragment from the provided method that justifies the step.

Grounding:
- Only use information from the provided method/ingredients. Do not hallucinate extra actions, tools, or ingredients.
- Preserve the order of the method unless there is a clear parallel/precedence cue such as "meanwhile" or "once done".
- Split into atomic actions (one pot stir, one bake, one garnish) without merging unrelated instructions.
- If a duration is missing, infer a sensible default (e.g., chop vegetables = 3-6 min, simmer until thick = 12-15 min) and mention that it was inferred in notes.

Output:
- Respond ONLY with a JSON array of step objects following this schema:
  [{"id":"step-1","label":"...","raw_text":"...","type":"prep|cook|finish","estimated_duration_minutes":12,"equipment":["..."],"temperature_c":180,"requires":[],"can_overlap_with":[],"notes":"..."}]
- Number ids sequentially starting at step-1. Do not add prose before or after the JSON."""

    COMBINED_VALIDATION_SYSTEM_PROMPT = """You are a strict validator and scheduler. Review the extracted steps against the method text.
    
Return JSON only in the form:
{"status":"ok|adjusted","issues":["..."],"steps":[...same schema as input...]}

Your goals:
1. GROUNDING: Remove hallucinations (steps not in method). Add missing instructions clearly described in text.
2. SCHEDULING: Ensure dependencies are logical. 'requires' must point to existing step IDs.
3. CONSISTENCY: Ensure 'type' is prep/cook/finish. 'estimated_duration_minutes' must be > 0.
4. ORDER: Preserve method order unless parallel execution is explicitly possible.

Rules:
- Keep raw_text snippets as short quotes.
- If a step is removed, remove it from 'requires' lists of other steps.
- If a step is added, give it a new ID (e.g. step-new-1)."""

    USER_PROMPT_TEMPLATE = """Recipe: {title}

Ingredients:
{ingredients}

Method:
{method}

Extract grounded, dependency-aware steps as JSON."""

    def __init__(self, llm_provider=None):
        self.llm = llm_provider or get_llm_provider()
        self.cache = RecipeCache(CACHE_DIR)
        print(f"Using LLM provider: {self.llm.get_name()}")

    @retry(
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    def _call_llm(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Call LLM with retries"""
        return self.llm.generate(prompt, system_prompt=system_prompt or self.SYSTEM_PROMPT)

    @staticmethod
    def _strip_code_fences(text: str) -> str:
        """Remove Markdown fences that may wrap JSON"""
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(line for line in lines if not line.startswith("```"))
        return text.strip()

    def _load_json(self, text: str) -> Optional[Union[Dict, List]]:
        """Load parsed JSON (object or array) after stripping markdown fences"""
        try:
            return json.loads(self._strip_code_fences(text))
        except json.JSONDecodeError as e:
            print(f"Validation JSON parse error: {e}")
            return None

    @staticmethod
    def _is_valid_step_list(steps: Optional[List[Dict]]) -> bool:
        """Basic schema validation before accepting LLM adjustments"""
        if not isinstance(steps, list) or not steps:
            return False
        required_fields = {"label", "type", "estimated_duration_minutes"}
        for step in steps:
            if not isinstance(step, dict):
                return False
            if not required_fields.issubset(step.keys()):
                return False
        return True

    @staticmethod
    def _is_template_only_method(method: str) -> bool:
        """Check if method contains only template text without actual cooking instructions"""
        method_lower = method.lower()

        # Template indicators that suggest no real content
        template_phrases = [
            "cooking instructions",
            "what's in your box",
            "nutritional info",
            "prep time",
            "total time",
            "cooking mode:",
            "all nutritional values are based on a per person scale",
            "calories total fat",
            "ingredients / allergens",
        ]

        # Count how much of the text is template vs content
        template_chars = 0
        for phrase in template_phrases:
            if phrase in method_lower:
                template_chars += len(phrase)

        # If method is short and mostly template phrases, it's template-only
        if len(method) < 500 and template_chars > len(method) * 0.4:
            return True

        # Check for specific patterns that indicate no instructions
        has_step_words = any(
            word in method_lower
            for word in [
                "step",
                "heat",
                "cook",
                "add",
                "mix",
                "stir",
                "chop",
                "slice",
                "fry",
                "bake",
                "boil",
                "simmer",
                "roast",
                "place",
                "remove",
            ]
        )

        # If no cooking action words and short, likely template-only
        if len(method) < 600 and not has_step_words:
            return True

        return False

    def _run_validation_passes(
        self,
        recipe: Dict,
        method: str,
        initial_steps: List[Dict],
    ) -> List[Dict]:
        """Run a combined validation pass to reduce hallucinations and fix scheduling"""
        steps = initial_steps

        # Combined Pass: Grounding + Consistency + Scheduling
        validation_prompt = (
            "Review and refine these steps based on the method.\n"
            f"Title: {recipe['title']}\n\n"
            f"Method:\n{method}\n\n"
            "Current steps (JSON):\n"
            f"{json.dumps(steps, indent=2)}\n\n"
            "Return the corrected JSON object with status, issues, and steps."
        )

        response = self._call_llm(
            validation_prompt,
            system_prompt=self.COMBINED_VALIDATION_SYSTEM_PROMPT,
        )

        data = self._load_json(response) or {}
        candidate_steps = data.get("steps") if isinstance(data, dict) else None

        if self._is_valid_step_list(candidate_steps):
            steps = candidate_steps
            if data.get("issues"):
                print(f"Validation issues fixed: {data['issues']}")
        else:
            print("Validation returned invalid data, keeping previous steps.")

        return steps

    def parse_recipe_steps(self, recipe: Dict) -> List[RecipeStep]:
        """Parse recipe method into structured steps"""
        recipe_id = recipe["id"]
        method = recipe.get("method", "").strip()

        if not method:
            print(f"Warning: No method text for {recipe_id}, skipping")
            return []

        # Check for template-only content (no actual instructions)
        if self._is_template_only_method(method):
            print(
                f"Warning: Recipe {recipe_id} contains only template text, no cooking instructions"
            )
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

            steps_data = self._load_json(response)
            if steps_data is None:
                raise json.JSONDecodeError("Invalid primary JSON", response, 0)
            if not isinstance(steps_data, list):
                raise ValueError("Primary LLM response was not a list of steps")

            # Verification + validation passes to reduce hallucinations and missed steps
            steps_data = self._run_validation_passes(recipe, method, steps_data)

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

                # Drop dependencies that point to non-existent steps
                valid_ids = {f"step-{j}" for j in range(1, len(steps_data) + 1)}
                step_data["requires"] = [
                    req for req in step_data.get("requires", []) if req in valid_ids
                ]
                step_data["can_overlap_with"] = [
                    overlap
                    for overlap in step_data.get("can_overlap_with", [])
                    if overlap in valid_ids
                ]

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
                weeks=recipe.get("weeks", []),
                category=recipe.get("category"),
                ingredients=recipe.get("ingredients", []),
                nutrition=recipe.get("nutrition"),
                steps=steps,
            )
            parsed_recipes.append(parsed_recipe)

        return parsed_recipes


def main():
    """Main parser execution"""
    parser = argparse.ArgumentParser(description="Parse recipes with LLM")
    parser.add_argument("--week", help="Filter recipes by week label (e.g. 'Nov 24, 2025')")
    args = parser.parse_args()

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

    # Filter by week if specified
    if args.week:
        print(f"Filtering for week: {args.week}")
        # Check both weeks array and week_label
        raw_recipes = [
            r
            for r in raw_recipes
            if args.week in r.get("weeks", []) or r.get("week_label") == args.week
        ]
        print(f"Found {len(raw_recipes)} recipes for {args.week}")

    # Load existing parsed recipes to preserve data
    parsed_recipes_path = DATA_DIR / "recipes_parsed.json"
    existing_parsed = {}
    if parsed_recipes_path.exists():
        try:
            with open(parsed_recipes_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                existing_parsed = {r["id"]: r for r in data}
            print(f"Loaded {len(existing_parsed)} existing parsed recipes")
        except Exception as e:
            print(f"Warning: Could not load existing parsed recipes: {e}")

    # Parse recipes
    parser = RecipeParser()
    new_parsed_recipes = parser.parse_all_recipes(raw_recipes)

    # Update existing recipes with new ones
    for recipe in new_parsed_recipes:
        existing_parsed[recipe.id] = asdict(recipe)

    final_recipes = list(existing_parsed.values())

    # Save parsed recipes
    output_path = DATA_DIR / "recipes_parsed.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(
            final_recipes,
            f,
            indent=2,
            ensure_ascii=False,
        )
        f.write("\n")

    print(f"\n{'=' * 60}")
    print(f"Parsed {len(new_parsed_recipes)} new/updated recipes")
    print(f"Total recipes in database: {len(final_recipes)}")
    print(f"Saved to: {output_path}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
