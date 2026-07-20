"""LLM enrichment of extracted steps into scheduling-ready ``RecipeStep`` objects."""

from __future__ import annotations

import json
import time
from typing import Dict, List, Optional

from ..io import DATA_DIR, Cache, content_hash
from ..llm import STEPS_MARKER, LLMProvider, get_provider, mock_enrich_steps
from ..llm import _infer_duration, _infer_equipment, _infer_temp, _infer_type  # fallbacks
from ..models import ExtractedRecipe, ParsedRecipe, RecipeStep

PROMPT_VERSION = "enrich-v1"
MAX_DURATION_MIN = 240  # clamp absurd LLM durations (a step over 4h is a hallucination)
LLM_RETRIES = 3

ENRICH_SCHEMA = {
    "type": "object",
    "properties": {
        "steps": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "raw_text": {"type": "string"},
                    "label": {"type": "string", "description": "3-8 word action summary"},
                    "type": {"type": "string", "enum": ["prep", "cook", "finish"]},
                    "estimated_duration_minutes": {"type": "integer"},
                    "equipment": {"type": "array", "items": {"type": "string"}},
                    "temperature_c": {"type": ["integer", "null"]},
                    "requires": {"type": "array", "items": {"type": "string"}},
                    "can_overlap_with": {"type": "array", "items": {"type": "string"}},
                    "notes": {"type": "string"},
                },
                "required": ["id", "label", "type", "estimated_duration_minutes"],
            },
        }
    },
    "required": ["steps"],
}

_SYSTEM_MARKER = """You enrich pre-split cooking steps for a cooking Gantt chart.
The step texts are FIXED and already correctly split — do NOT merge, split, reorder, or
invent steps. Return exactly one object per given step id, preserving every id.

For each step provide:
- label: 3-8 word action.
- type: prep (chop/marinate/preheat), cook (heat applied), or finish (plate/garnish/rest).
- estimated_duration_minutes: integer >= 1; use the midpoint of any range and note the
  range; infer a sensible default if unstated (chop veg ~4, simmer ~13).
- equipment: tools mentioned or clearly implied (pan to fry, oven to roast).
- temperature_c: integer if a temperature is given, else null.
- requires: ids of steps that must finish before this one starts.
- can_overlap_with: ids of steps that can run in parallel (e.g. prep during a simmer).
- notes: timing ranges, doneness cues, or ordering clarifications.
Ground everything only in the provided text; do not add tools or actions not implied."""

_SYSTEM_PARAGRAPH = """You convert a heuristically split cooking method into atomic steps
for a Gantt chart. The provided fragments may be mis-split — re-segment into clean atomic
steps and assign sequential ids step-1, step-2, ... For each step include raw_text: a short
verbatim fragment from the provided text that justifies it. Then enrich each step with
label, type (prep|cook|finish), estimated_duration_minutes (integer >= 1), equipment,
temperature_c (int or null), requires, can_overlap_with, and notes. Ground everything in
the provided text; do not invent actions or tools."""


def _user_prompt(recipe: ExtractedRecipe) -> str:
    ingredients = "\n".join(f"- {i}" for i in recipe.ingredients) or "(not provided)"
    payload = [{"id": s.id, "text": s.text} for s in recipe.steps]
    return (
        f"Recipe: {recipe.title}\n\n"
        f"Ingredients:\n{ingredients}\n\n"
        f"Enrich these steps.\n{STEPS_MARKER}\n{json.dumps(payload, ensure_ascii=False)}"
    )


def _coerce_step(raw: dict, *, step_id: str, raw_text: str) -> RecipeStep:
    """Build a valid RecipeStep from possibly-incomplete LLM output, with fallbacks."""
    stype = raw.get("type")
    if stype not in ("prep", "cook", "finish"):
        stype = _infer_type(raw_text)

    dur = raw.get("estimated_duration_minutes")
    if not isinstance(dur, int) or dur < 1:
        dur = _infer_duration(raw_text, stype)
    dur = min(dur, MAX_DURATION_MIN)  # clamp hallucinated durations

    label = (raw.get("label") or "").strip() or " ".join(raw_text.split()[:6]).rstrip(".,")

    # For temperature/equipment: respect an explicit LLM value (present key), otherwise
    # infer deterministically from the grounded text.
    if "temperature_c" in raw:
        t = raw.get("temperature_c")
        temp = int(t) if isinstance(t, (int, float)) else None
    else:
        temp = _infer_temp(raw_text)

    if "equipment" in raw:
        equipment = [e for e in raw.get("equipment") or [] if isinstance(e, str)]
    else:
        equipment = _infer_equipment(raw_text)

    return RecipeStep(
        id=step_id,
        raw_text=raw_text,
        label=label or step_id,
        type=stype,
        estimated_duration_minutes=dur,
        equipment=equipment,
        temperature_c=temp,
        requires=[r for r in raw.get("requires", []) if isinstance(r, str)],
        can_overlap_with=[c for c in raw.get("can_overlap_with", []) if isinstance(c, str)],
        notes=(raw.get("notes") or "").strip(),
    )


def _sanitize_graph(steps: List[RecipeStep]) -> List[RecipeStep]:
    """Drop dependency refs to non-existent steps and any self-references."""
    ids = {s.id for s in steps}
    for s in steps:
        s.requires = [r for r in s.requires if r in ids and r != s.id]
        s.can_overlap_with = [c for c in s.can_overlap_with if c in ids and c != s.id]
    return steps


def _build_steps(recipe: ExtractedRecipe, enriched: List[dict]) -> List[RecipeStep]:
    by_id: Dict[str, dict] = {e["id"]: e for e in enriched if isinstance(e, dict) and "id" in e}

    if recipe.needs_llm_segmentation:
        # Trust the model's (re)segmentation; renumber ids sequentially for stability.
        steps: List[RecipeStep] = []
        for i, e in enumerate(enriched, 1):
            if not isinstance(e, dict):
                continue
            raw_text = (e.get("raw_text") or e.get("label") or "").strip()
            steps.append(_coerce_step(e, step_id=f"step-{i}", raw_text=raw_text))
        return _sanitize_graph(steps)

    # Marker case: extractor ids/texts are authoritative — one step out per step in.
    steps = [
        _coerce_step(by_id.get(s.id, {}), step_id=s.id, raw_text=s.text)
        for s in recipe.steps
    ]
    return _sanitize_graph(steps)


def _mock_steps(recipe: ExtractedRecipe) -> List[RecipeStep]:
    """Deterministic enrichment of the extracted steps (no LLM). Used as the fallback
    when a weak/flaky model returns nothing usable, so a cookable recipe is never empty."""
    payload = [{"id": s.id, "text": s.text} for s in recipe.steps]
    return _build_steps(recipe, mock_enrich_steps(payload))


def _complete_with_retry(provider: LLMProvider, system: str, user: str) -> object:
    """Call the provider, retrying transient failures (rate limits, timeouts)."""
    last: Optional[Exception] = None
    for attempt in range(LLM_RETRIES):
        try:
            return provider.complete_json(system, user, ENRICH_SCHEMA)
        except Exception as e:  # noqa: BLE001 - provider SDKs raise varied error types
            last = e
            if attempt < LLM_RETRIES - 1:
                time.sleep(2 * (attempt + 1))
    raise last if last else RuntimeError("enrichment failed")


def enrich_recipe(
    recipe: ExtractedRecipe,
    provider: Optional[LLMProvider] = None,
    cache: Optional[Cache] = None,
) -> ParsedRecipe:
    """Enrich one extracted recipe into a ParsedRecipe.

    Robust to poor/flaky models: a failed or empty LLM response falls back to deterministic
    enrichment rather than producing an empty cookable recipe.
    """
    base = recipe.model_dump(
        exclude={"schema_version", "method_clean", "steps", "extraction_method",
                 "needs_llm_segmentation", "notes", "cookable"}
    )

    if not recipe.cookable or not recipe.steps:
        return ParsedRecipe(**base, steps=[], cookable=recipe.cookable)

    provider = provider or get_provider()
    system = _SYSTEM_PARAGRAPH if recipe.needs_llm_segmentation else _SYSTEM_MARKER
    user = _user_prompt(recipe)

    key = content_hash("enrich", PROMPT_VERSION, provider.name, recipe.id, user)
    result = cache.get(key) if cache else None
    if result is None:
        try:
            result = _complete_with_retry(provider, system, user)
        except Exception as e:  # noqa: BLE001
            print(f"Enrich LLM failed for {recipe.id}: {e}; using deterministic fallback")
            result = None
        if result is not None and cache:
            cache.set(key, result)

    # Accept both {"steps": [...]} (Anthropic/OpenAI schema) and a bare [...] array
    # (some providers, e.g. Gemini JSON mode, may return the array directly).
    if isinstance(result, dict):
        enriched = result.get("steps", [])
    elif isinstance(result, list):
        enriched = result
    else:
        enriched = []

    steps = _build_steps(recipe, enriched)
    if not steps:  # model returned nothing usable → deterministic fallback
        steps = _mock_steps(recipe)
    return ParsedRecipe(**base, steps=steps, cookable=recipe.cookable)


def enrich_all(
    recipes: List[ExtractedRecipe],
    provider: Optional[LLMProvider] = None,
    use_cache: bool = True,
) -> List[ParsedRecipe]:
    """Enrich every recipe, sharing one provider and cache."""
    provider = provider or get_provider()
    cache = Cache(DATA_DIR / ".cache" / "enrich", enabled=use_cache)
    out = []
    for r in recipes:
        try:
            out.append(enrich_recipe(r, provider=provider, cache=cache))
        except Exception as e:  # one bad recipe must not abort the batch
            print(f"Enrich error for {r.id}: {e}")
            base = r.model_dump(
                exclude={"schema_version", "method_clean", "steps", "extraction_method",
                         "needs_llm_segmentation", "notes", "cookable"}
            )
            # Even on unexpected failure, keep grounded steps via deterministic fallback.
            steps = _mock_steps(r) if (r.cookable and r.steps) else []
            out.append(ParsedRecipe(**base, steps=steps, cookable=r.cookable))
    return out
