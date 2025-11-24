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

    VALIDATION_SYSTEM_PROMPT = """You are a strict validator. Check that every output step is grounded in the provided method text and that no method instruction is dropped.

Return JSON only in the form:
{"status":"ok|adjusted","issues":["..."],"steps":[...same schema as input...]}

Rules:
- Remove any step that is not supported by the method text (hallucination).
- Add a missing step only if the method text clearly describes it.
- Keep raw_text snippets as short quotes from the method for traceability.
- Preserve useful labels/notes when possible, but prefer fidelity over style."""

    CONSISTENCY_SYSTEM_PROMPT = """You enforce schema consistency and safe scheduling choices for recipe steps.

Return ONLY the final JSON array of steps (no wrapper object). Apply these corrections without inventing new actions:
- Ensure ids are sequential (step-1, step-2, ...) and that requires/can_overlap_with only reference existing ids.
- type must be prep, cook, or finish.
- estimated_duration_minutes must be positive integers; pick reasonable defaults if missing and mention inference in notes.
- temperature_c should be numeric when present in the method; otherwise omit/null.
- Order should follow the method unless dependencies clearly indicate parallel work.
- Drop duplicate steps; consolidate overlapping notes; keep raw_text grounded to the method."""

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

    def _load_json(self, text: str) -> Optional[Dict]:
        """Load JSON after stripping markdown fences"""
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

    def _run_validation_passes(
        self,
        recipe: Dict,
        method: str,
        initial_steps: List[Dict],
    ) -> List[Dict]:
        """Run multiple LLM validations to reduce hallucinations and missed steps"""
        steps = initial_steps

        # Pass 1: coverage + hallucination guard
        coverage_prompt = (
            "You are checking fidelity between method text and extracted steps.\n"
            f"Title: {recipe['title']}\n\n"
            f"Method:\n{method}\n\n"
            "Current steps (JSON):\n"
            f"{json.dumps(steps, indent=2)}\n\n"
            "Identify unsupported steps or missing instructions and return an adjusted list if needed."
        )
        coverage_response = self._call_llm(
            coverage_prompt,
            system_prompt=self.VALIDATION_SYSTEM_PROMPT,
        )
        coverage_data = self._load_json(coverage_response) or {}
        candidate_steps = coverage_data.get("steps") if isinstance(coverage_data, dict) else None
        if self._is_valid_step_list(candidate_steps):
            steps = candidate_steps
            if coverage_data.get("issues"):
                print(f"Validation (coverage) issues: {coverage_data['issues']}")
        else:
            print("Coverage validation returned invalid data, keeping previous steps.")

        # Pass 2: consistency and scheduling sanity
        consistency_prompt = (
            "Normalize the steps while keeping them grounded in the method.\n"
            f"Title: {recipe['title']}\n\n"
            f"Method:\n{method}\n\n"
            "Steps to normalize (JSON):\n"
            f"{json.dumps(steps, indent=2)}"
        )
        consistency_response = self._call_llm(
            consistency_prompt,
            system_prompt=self.CONSISTENCY_SYSTEM_PROMPT,
        )
        normalized_steps = self._load_json(consistency_response)
        if self._is_valid_step_list(normalized_steps):
            steps = normalized_steps
        else:
            print("Consistency validation returned invalid data, keeping previous steps.")

        return steps

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
                    overlap for overlap in step_data.get("can_overlap_with", []) if overlap in valid_ids
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
        f.write("\n")

    print(f"\n{'=' * 60}")
    print(f"Parsed {len(parsed_recipes)} recipes")
    print(f"Total steps: {sum(len(r.steps) for r in parsed_recipes)}")
    print(f"Saved to: {output_path}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
