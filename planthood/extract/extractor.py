"""Deterministic recipe extraction.

Turns a raw scraped ``method`` blob (title + marketing + instructions + nutrition +
allergens, all concatenated) into a list of grounded :class:`ExtractedStep` fragments.

Strategy:
  1. Normalise whitespace.
  2. Find the instruction region: from the first ``STEP n`` marker (or the
     ``Cooking instructions`` header) up to the first template terminator such as
     ``What's in your box`` / ``Nutritional info`` / ``Ingredients / Allergens``.
  3. If ``STEP`` markers exist, split on them (exact, grounded).
     Otherwise, if the region contains cooking-action words, fall back to a sentence
     split flagged ``needs_llm_segmentation``.
     Otherwise the recipe is non-cookable (e.g. a product bundle) → no steps.
"""

from __future__ import annotations

import re
from typing import List, Optional, Tuple

from ..models import ExtractedRecipe, ExtractedStep, RawRecipe
from ..text import APOSTROPHE, normalize_whitespace

# Markers that delimit steps within the instruction region.
STEP_MARKER_RE = re.compile(r"STEP\s*(\d+)", re.IGNORECASE)

# Header that introduces the instruction region when there are no STEP markers.
COOKING_INSTRUCTIONS_RE = re.compile(r"Cooking\s*instructions", re.IGNORECASE)

# Phrases that mark the END of the instruction region (start of trailing template).
TERMINATOR_RE = re.compile(
    r"(?:What" + APOSTROPHE + r"s in your box"
    r"|Nutritional info"
    r"|Nutritional value"
    r"|Ingredients\s*/\s*Allergens"
    r"|Allergen)",
    re.IGNORECASE,
)

# Boilerplate present in nearly every recipe's preamble — not recipe-specific content.
PREAMBLE_BOILERPLATE = [
    re.compile(
        r"Before you start,? take out all the ingredients for this recipe"
        r".*?(?:section below\)?\.?|\bbelow\b\.?)",
        re.IGNORECASE,
    ),
    re.compile(
        r"Thoroughly wash all fresh vegetables,?.*?before cooking or serving\.?",
        re.IGNORECASE,
    ),
]

# Words that signal genuine cooking instructions (vs a product description).
ACTION_WORDS = (
    "heat", "cook", "add", "mix", "stir", "chop", "slice", "fry", "bake", "boil",
    "simmer", "roast", "place", "remove", "preheat", "drizzle", "season", "serve",
    "pour", "blend", "whisk", "fold", "grate", "toast", "saute", "sauté", "warm",
    "spread", "combine", "cut", "peel", "dice", "grill", "steam", "rinse", "drain",
)


def _has_action_words(text: str) -> bool:
    lowered = text.lower()
    return any(re.search(rf"\b{re.escape(w)}", lowered) for w in ACTION_WORDS)


def _strip_boilerplate(text: str) -> str:
    for pat in PREAMBLE_BOILERPLATE:
        text = pat.sub(" ", text)
    return normalize_whitespace(text)


def _instruction_region(method: str) -> Tuple[str, Optional[int]]:
    """Return (region_text, first_step_marker_number) isolated from surrounding template.

    ``first_step_marker_number`` is None when no STEP markers are present.
    """
    # Where do instructions start?
    first_step = STEP_MARKER_RE.search(method)
    if first_step:
        start = first_step.start()
        first_marker = int(first_step.group(1))
    else:
        header = COOKING_INSTRUCTIONS_RE.search(method)
        start = header.end() if header else 0
        first_marker = None

    # Where do they end? First terminator after the start.
    end = len(method)
    term = TERMINATOR_RE.search(method, start)
    if term:
        end = term.start()

    return method[start:end].strip(), first_marker


def _accept_markers(region: str):
    """Return the STEP markers that form the real step sequence.

    Recipes sometimes contain inline cross-references like ``(STEP 4)`` inside a step's
    text. Those are rejected two ways: a marker immediately preceded by ``(`` is skipped,
    and markers must form a strictly incrementing sequence (1, 2, 3, …) — an out-of-order
    number (e.g. a "4" seen while expecting "3") is treated as a reference, not a boundary.
    """
    accepted = []
    expected: Optional[int] = None
    for m in STEP_MARKER_RE.finditer(region):
        num = int(m.group(1))
        if m.start() > 0 and region[m.start() - 1] == "(":
            continue  # inline cross-reference, e.g. "(STEP 4)"
        if expected is None:
            expected = num  # anchor on the first real marker (normally 1)
        if num != expected:
            continue
        accepted.append(m)
        expected = num + 1
    return accepted


def _split_on_markers(region: str) -> List[Tuple[Optional[int], str]]:
    """Split an instruction region on real STEP markers into (marker_number, text) pairs."""
    accepted = _accept_markers(region)
    if not accepted:
        return []

    steps: List[Tuple[Optional[int], str]] = []
    for i, m in enumerate(accepted):
        text_start = m.end()
        text_end = accepted[i + 1].start() if i + 1 < len(accepted) else len(region)
        text = normalize_whitespace(region[text_start:text_end])
        if text:
            steps.append((int(m.group(1)), text))
    return steps


def _split_sentences(region: str) -> List[Tuple[Optional[int], str]]:
    """Fallback sentence split for regions without STEP markers."""
    region = _strip_boilerplate(region)
    # Split after sentence-ending punctuation followed by a capital/number.
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", region)
    return [(None, normalize_whitespace(p)) for p in parts if len(normalize_whitespace(p)) > 3]


def extract_recipe(raw: RawRecipe) -> ExtractedRecipe:
    """Extract grounded step fragments from a single raw recipe."""
    base = raw.model_dump(exclude={"schema_version", "method"})
    method = normalize_whitespace(raw.method)

    def build(steps, method_clean, cookable, extraction_method, needs_llm, notes=""):
        extracted = [
            ExtractedStep(id=f"step-{i}", text=text, marker=marker)
            for i, (marker, text) in enumerate(steps, 1)
        ]
        return ExtractedRecipe(
            **base,
            method_clean=method_clean,
            steps=extracted,
            cookable=cookable,
            extraction_method=extraction_method,
            needs_llm_segmentation=needs_llm,
            notes=notes,
        )

    if not method:
        return build([], "", False, "none", False, "No method text scraped.")

    region, first_marker = _instruction_region(method)

    # Path 1: explicit STEP markers → exact deterministic split.
    if first_marker is not None:
        step_pairs = _split_on_markers(region)
        if step_pairs:
            return build(step_pairs, region, True, "step_markers", False)

    # Path 2: no markers, but the region reads like cooking instructions → sentence split.
    if region and _has_action_words(region):
        sentence_pairs = _split_sentences(region)
        if sentence_pairs:
            return build(
                sentence_pairs,
                _strip_boilerplate(region),
                True,
                "paragraph",
                True,
                "No STEP markers; sentence-split pending LLM segmentation.",
            )

    # Path 3: no cookable instructions found (e.g. a product bundle).
    return build([], "", False, "none", False, "No cooking instructions found (non-cookable).")


def extract_all(raws: List[RawRecipe]) -> List[ExtractedRecipe]:
    """Extract every recipe."""
    return [extract_recipe(r) for r in raws]
