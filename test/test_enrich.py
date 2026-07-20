"""Unit tests for the LLM enrich stage (using deterministic fake/mock providers)."""

from planthood.enrich import enrich_recipe
from planthood.llm import LLMProvider, MockProvider
from planthood.models import ExtractedRecipe, ExtractedStep


def _extracted(steps, **kw):
    return ExtractedRecipe(
        id=kw.get("id", "r1"),
        title=kw.get("title", "Test"),
        steps=[ExtractedStep(id=f"step-{i}", text=t, marker=i) for i, t in enumerate(steps, 1)],
        cookable=kw.get("cookable", True),
        extraction_method=kw.get("extraction_method", "step_markers"),
        needs_llm_segmentation=kw.get("needs_llm_segmentation", False),
    )


class FakeProvider(LLMProvider):
    """Returns a fixed enrichment payload, to exercise coercion and graph sanitization."""

    def __init__(self, payload):
        self._payload = payload

    def complete_json(self, system, user, schema):
        return self._payload

    @property
    def name(self):
        return "fake"


def test_marker_case_preserves_ids_and_count():
    ex = _extracted(["Preheat oven to 200C.", "Chop onions.", "Serve hot."])
    parsed = enrich_recipe(ex, provider=MockProvider())
    assert [s.id for s in parsed.steps] == ["step-1", "step-2", "step-3"]
    # raw_text stays the authoritative extracted text.
    assert parsed.steps[0].raw_text == "Preheat oven to 200C."


def test_missing_enrichment_falls_back_deterministically():
    # Provider returns enrichment for only one of two steps; the other must still be valid.
    ex = _extracted(["Chop the carrots.", "Roast for 25 minutes at 180C."])
    provider = FakeProvider({"steps": [{"id": "step-1", "label": "Chop carrots",
                                        "type": "prep", "estimated_duration_minutes": 4}]})
    parsed = enrich_recipe(ex, provider=provider)
    assert len(parsed.steps) == 2
    s2 = parsed.steps[1]
    assert s2.type == "cook"                       # inferred from "roast"
    assert s2.estimated_duration_minutes == 25     # parsed from text
    assert s2.temperature_c == 180
    assert s2.label                                # non-empty fallback label


def test_invalid_duration_is_repaired():
    ex = _extracted(["Simmer gently."])
    provider = FakeProvider({"steps": [{"id": "step-1", "label": "Simmer",
                                        "type": "cook", "estimated_duration_minutes": 0}]})
    parsed = enrich_recipe(ex, provider=provider)
    assert parsed.steps[0].estimated_duration_minutes >= 1


def test_graph_refs_sanitized():
    ex = _extracted(["A.", "B."])
    provider = FakeProvider({"steps": [
        {"id": "step-1", "label": "A", "type": "prep", "estimated_duration_minutes": 2,
         "requires": ["step-1", "step-99"]},                       # self + phantom
        {"id": "step-2", "label": "B", "type": "cook", "estimated_duration_minutes": 5,
         "requires": ["step-1"], "can_overlap_with": ["step-2", "ghost"]},
    ]})
    parsed = enrich_recipe(ex, provider=provider)
    assert parsed.steps[0].requires == []           # self and phantom dropped
    assert parsed.steps[1].requires == ["step-1"]
    assert parsed.steps[1].can_overlap_with == []   # self and ghost dropped


def test_non_cookable_yields_no_steps_without_calling_llm():
    ex = _extracted([], cookable=False, extraction_method="none")

    class Boom(LLMProvider):
        def complete_json(self, system, user, schema):
            raise AssertionError("LLM must not be called for non-cookable recipes")

        @property
        def name(self):
            return "boom"

    parsed = enrich_recipe(ex, provider=Boom())
    assert parsed.cookable is False
    assert parsed.steps == []


def test_accepts_bare_array_response():
    # A provider (e.g. Gemini JSON mode) may return a bare array instead of {"steps": [...]}.
    ex = _extracted(["Chop the onions.", "Fry until soft."])
    provider = FakeProvider([
        {"id": "step-1", "label": "Chop onions", "type": "prep", "estimated_duration_minutes": 3},
        {"id": "step-2", "label": "Fry onions", "type": "cook", "estimated_duration_minutes": 6},
    ])
    parsed = enrich_recipe(ex, provider=provider)
    assert [s.id for s in parsed.steps] == ["step-1", "step-2"]
    assert parsed.steps[1].type == "cook"


def test_paragraph_case_uses_model_segmentation():
    ex = _extracted(["Heat oil then add garlic and cook then add tomatoes and simmer."],
                    extraction_method="paragraph", needs_llm_segmentation=True)
    provider = FakeProvider({"steps": [
        {"id": "x", "raw_text": "Heat oil", "label": "Heat oil", "type": "cook",
         "estimated_duration_minutes": 2},
        {"id": "y", "raw_text": "add garlic and cook", "label": "Cook garlic", "type": "cook",
         "estimated_duration_minutes": 3},
    ]})
    parsed = enrich_recipe(ex, provider=provider)
    assert [s.id for s in parsed.steps] == ["step-1", "step-2"]   # renumbered
    assert parsed.steps[0].raw_text == "Heat oil"
