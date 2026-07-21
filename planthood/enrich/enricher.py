"""LLM enrichment of extracted steps into scheduling-ready ``RecipeStep`` objects."""

from __future__ import annotations

import json
import os
import time
from typing import Dict, List, Optional

from ..io import content_hash
from ..llm import STEPS_MARKER, LLMProvider, get_provider, mock_enrich_steps
from ..llm import _infer_duration, _infer_equipment, _infer_temp, _infer_type  # fallbacks
from ..models import ExtractedRecipe, ParsedRecipe, RecipeStep

PROMPT_VERSION = "enrich-v1"
MAX_DURATION_MIN = 240  # clamp absurd LLM durations (a step over 4h is a hallucination)
LLM_RETRIES = 4
# Minimum seconds between LLM calls, to stay under a provider's requests-per-minute limit.
# Gemini's free tier is ~5 RPM, so ~13s spacing avoids 429s entirely. Set via env.
MIN_LLM_INTERVAL_SEC = float(os.getenv("ENRICH_MIN_INTERVAL_SEC", "0"))

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
    steps = [_coerce_step(by_id.get(s.id, {}), step_id=s.id, raw_text=s.text) for s in recipe.steps]
    return _sanitize_graph(steps)


def _mock_steps(recipe: ExtractedRecipe) -> List[RecipeStep]:
    """Deterministic enrichment of the extracted steps (no LLM). Used as the fallback
    when a weak/flaky model returns nothing usable, so a cookable recipe is never empty."""
    payload = [{"id": s.id, "text": s.text} for s in recipe.steps]
    return _build_steps(recipe, mock_enrich_steps(payload))


def _is_daily_quota_exhausted(exc: Exception) -> bool:
    """True for a per-day free-tier quota 429 (e.g. Gemini's RPD cap). Unlike a per-minute
    (RPM) limit, a daily window can't clear within a run, so retrying only wastes CI time
    and circuit-breaker patience — fail fast to the deterministic fallback instead."""
    text = str(exc)
    return "RESOURCE_EXHAUSTED" in text and "PerDay" in text


def _complete_with_retry(provider: LLMProvider, system: str, user: str) -> object:
    """Call the provider, retrying transient failures (per-minute rate limits, timeouts).
    A per-day quota exhaustion is not retried — the backoff can't clear a daily window."""
    last: Optional[Exception] = None
    for attempt in range(LLM_RETRIES):
        try:
            return provider.complete_json(system, user, ENRICH_SCHEMA)
        except Exception as e:  # noqa: BLE001 - provider SDKs raise varied error types
            last = e
            if _is_daily_quota_exhausted(e):
                break  # daily quota gone; retrying is futile — fall through to raise
            if attempt < LLM_RETRIES - 1:
                # Backoff long enough to clear a per-minute rate-limit window (up to ~30s).
                time.sleep(min(30, 8 * (attempt + 1)))
    raise last if last else RuntimeError("enrichment failed")


class _Breaker:
    """Trips after N consecutive LLM failures so a daily run that has exhausted its quota
    stops hammering the API and falls back deterministically for the rest of the batch."""

    def __init__(self, threshold: int = 8):
        self.threshold = threshold
        self.consecutive = 0
        self.tripped = False

    def record(self, success: bool) -> None:
        if success:
            self.consecutive = 0
        else:
            self.consecutive += 1
            if self.consecutive >= self.threshold:
                self.tripped = True


def source_hash(recipe: ExtractedRecipe) -> str:
    """Fingerprint of the extracted steps an enrichment is based on. If the recipe is
    re-scraped and its steps change, the hash changes and it is re-enriched."""
    parts = [PROMPT_VERSION, "seg" if recipe.needs_llm_segmentation else "mark"]
    parts += [f"{s.id}:{s.text}" for s in recipe.steps]
    return content_hash(*parts)


def _base(recipe: ExtractedRecipe) -> dict:
    return recipe.model_dump(
        exclude={
            "schema_version",
            "method_clean",
            "steps",
            "extraction_method",
            "needs_llm_segmentation",
            "notes",
            "cookable",
        }
    )


def _fallback_recipe(recipe: ExtractedRecipe) -> ParsedRecipe:
    """Deterministic enrichment (no LLM). provenance='fallback' marks it as a candidate
    for real LLM enrichment on a later run."""
    steps = _mock_steps(recipe) if (recipe.cookable and recipe.steps) else []
    return ParsedRecipe(
        **_base(recipe),
        steps=steps,
        cookable=recipe.cookable,
        provenance="fallback" if steps else "none",
        source_hash=source_hash(recipe),
    )


def enrich_recipe(
    recipe: ExtractedRecipe,
    provider: Optional[LLMProvider] = None,
    allow_llm: bool = True,
    on_llm=None,
) -> ParsedRecipe:
    """Enrich one extracted recipe into a ParsedRecipe.

    Robust to poor/flaky models: a failed or empty LLM response falls back to deterministic
    enrichment (``provenance='fallback'``) rather than producing an empty cookable recipe.
    With ``allow_llm=False`` the LLM is not called and the deterministic fallback is used.
    """
    if not recipe.cookable or not recipe.steps:
        return ParsedRecipe(
            **_base(recipe),
            steps=[],
            cookable=recipe.cookable,
            provenance="none",
            source_hash=source_hash(recipe),
        )

    if not allow_llm:
        return _fallback_recipe(recipe)

    provider = provider or get_provider()
    system = _SYSTEM_PARAGRAPH if recipe.needs_llm_segmentation else _SYSTEM_MARKER
    user = _user_prompt(recipe)

    try:
        result = _complete_with_retry(provider, system, user)
        if on_llm:
            on_llm(True)
    except Exception as e:  # noqa: BLE001
        print(f"Enrich LLM failed for {recipe.id}: {e}; using deterministic fallback")
        if on_llm:
            on_llm(False)
        return _fallback_recipe(recipe)

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
        return _fallback_recipe(recipe)
    # The mock provider is deterministic, not a real model → mark it 'fallback' so a real
    # LLM run still upgrades it later.
    prov = "fallback" if provider.name.startswith("mock") else "llm"
    return ParsedRecipe(
        **_base(recipe),
        steps=steps,
        cookable=recipe.cookable,
        provenance=prov,
        source_hash=source_hash(recipe),
    )


def _already_enriched(existing: Optional[ParsedRecipe], recipe: ExtractedRecipe) -> bool:
    """True if a prior run already produced genuine LLM steps for this recipe's current text."""
    return bool(
        existing and existing.provenance == "llm" and existing.source_hash == source_hash(recipe)
    )


def enrich_all(
    recipes: List[ExtractedRecipe],
    provider: Optional[LLMProvider] = None,
    existing: Optional[List[ParsedRecipe]] = None,
    limit: int = 0,
) -> List[ParsedRecipe]:
    """Enrich recipes, resuming from prior results — no separate cache.

    Recipes already LLM-enriched for their current text (per ``existing``) are reused as-is.
    Up to ``limit`` of the remaining cookable recipes are enriched with the LLM this run
    (``limit=0`` means no cap — enrich until the quota-driven circuit breaker trips). This
    is the "complete X recipes per day" mechanism: point daily CI at the committed
    ``recipes_parsed.json`` and it works through the backlog, ``limit`` new recipes at a time.
    """
    provider = provider or get_provider()
    existing_by_id: Dict[str, ParsedRecipe] = {r.id: r for r in (existing or [])}
    breaker = _Breaker()
    spent = 0
    last_llm_ts = 0.0
    out: List[ParsedRecipe] = []

    for r in recipes:
        prior = existing_by_id.get(r.id)
        if _already_enriched(prior, r):
            out.append(prior)  # done on a previous run; don't spend quota again
            continue

        budget_left = limit == 0 or spent < limit
        allow_llm = r.cookable and bool(r.steps) and budget_left and not breaker.tripped
        if allow_llm:
            # Pace calls to stay under the provider's requests-per-minute limit
            # (e.g. Gemini free tier ~5 RPM). This is what makes the daily run slowly
            # but reliably clear the backlog instead of tripping on 429s.
            wait = MIN_LLM_INTERVAL_SEC - (time.time() - last_llm_ts)
            if wait > 0:
                time.sleep(wait)
            spent += 1
            last_llm_ts = time.time()
        try:
            out.append(
                enrich_recipe(r, provider=provider, allow_llm=allow_llm, on_llm=breaker.record)
            )
        except Exception as e:  # one bad recipe must not abort the batch
            print(f"Enrich error for {r.id}: {e}")
            out.append(_fallback_recipe(r))

    llm_total = sum(1 for r in out if r.provenance == "llm")
    remaining = sum(1 for r in out if r.provenance == "fallback")
    print(
        f"Enrichment: {llm_total} LLM, {remaining} on deterministic fallback, "
        f"{spent} enriched this run (limit={limit or 'none'})."
    )
    if breaker.tripped:
        print(
            "LLM quota exhausted (circuit breaker tripped); remaining recipes will be "
            "enriched on the next run."
        )
    return out
