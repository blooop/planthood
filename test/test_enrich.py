"""Unit tests for the LLM enrich stage (using deterministic fake/mock providers)."""

from planthood.enrich import enrich_all, enrich_recipe
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
    provider = FakeProvider(
        {
            "steps": [
                {
                    "id": "step-1",
                    "label": "Chop carrots",
                    "type": "prep",
                    "estimated_duration_minutes": 4,
                }
            ]
        }
    )
    parsed = enrich_recipe(ex, provider=provider)
    assert len(parsed.steps) == 2
    s2 = parsed.steps[1]
    assert s2.type == "cook"  # inferred from "roast"
    assert s2.estimated_duration_minutes == 25  # parsed from text
    assert s2.temperature_c == 180
    assert s2.label  # non-empty fallback label


def test_invalid_duration_is_repaired():
    ex = _extracted(["Simmer gently."])
    provider = FakeProvider(
        {
            "steps": [
                {"id": "step-1", "label": "Simmer", "type": "cook", "estimated_duration_minutes": 0}
            ]
        }
    )
    parsed = enrich_recipe(ex, provider=provider)
    assert parsed.steps[0].estimated_duration_minutes >= 1


def test_graph_refs_sanitized():
    ex = _extracted(["A.", "B."])
    provider = FakeProvider(
        {
            "steps": [
                {
                    "id": "step-1",
                    "label": "A",
                    "type": "prep",
                    "estimated_duration_minutes": 2,
                    "requires": ["step-1", "step-99"],
                },  # self + phantom
                {
                    "id": "step-2",
                    "label": "B",
                    "type": "cook",
                    "estimated_duration_minutes": 5,
                    "requires": ["step-1"],
                    "can_overlap_with": ["step-2", "ghost"],
                },
            ]
        }
    )
    parsed = enrich_recipe(ex, provider=provider)
    assert parsed.steps[0].requires == []  # self and phantom dropped
    assert parsed.steps[1].requires == ["step-1"]
    assert parsed.steps[1].can_overlap_with == []  # self and ghost dropped


def test_llm_failure_falls_back_to_deterministic_steps(monkeypatch):
    from planthood.enrich import enricher

    monkeypatch.setattr(enricher.time, "sleep", lambda *_: None)  # skip retry backoff
    # A flaky/poor model that always errors must not yield an empty cookable recipe.
    ex = _extracted(["Preheat the oven to 200C.", "Roast for 20 minutes.", "Serve."])

    class Flaky(LLMProvider):
        def complete_json(self, system, user, schema):
            raise RuntimeError("rate limited")

        @property
        def name(self):
            return "flaky"

    parsed = enrich_recipe(ex, provider=Flaky())
    assert len(parsed.steps) == 3  # fallback filled all steps
    assert all(s.estimated_duration_minutes >= 1 for s in parsed.steps)
    assert parsed.steps[0].type == "prep"  # inferred from "Preheat"


def test_daily_quota_error_is_not_retried(monkeypatch):
    from planthood.enrich import enricher

    # A per-day (RPD) quota 429 can't clear within the run, so it must NOT burn retries —
    # exactly one call, then straight to the deterministic fallback.
    monkeypatch.setattr(enricher.time, "sleep", lambda *_: None)
    calls = {"n": 0}

    class DailyQuota(LLMProvider):
        def complete_json(self, system, user, schema):
            calls["n"] += 1
            raise RuntimeError(
                "429 RESOURCE_EXHAUSTED ... 'quotaId': "
                "'GenerateRequestsPerDayPerProjectPerModel-FreeTier'"
            )

        @property
        def name(self):
            return "daily-quota"

    parsed = enrich_recipe(_extracted(["Chop.", "Cook."]), provider=DailyQuota())
    assert calls["n"] == 1  # not retried — LLM_RETRIES times would be 4
    assert len(parsed.steps) == 2  # deterministic fallback filled the steps
    assert parsed.provenance == "fallback"


def test_per_minute_quota_error_is_still_retried(monkeypatch):
    from planthood.enrich import enricher

    # A per-minute (RPM) limit CAN clear within the run, so it must still be retried.
    monkeypatch.setattr(enricher.time, "sleep", lambda *_: None)
    calls = {"n": 0}

    class MinuteQuota(LLMProvider):
        def complete_json(self, system, user, schema):
            calls["n"] += 1
            raise RuntimeError(
                "429 RESOURCE_EXHAUSTED ... 'quotaId': "
                "'GenerateRequestsPerMinutePerProjectPerModel-FreeTier'"
            )

        @property
        def name(self):
            return "minute-quota"

    enrich_recipe(_extracted(["Chop.", "Cook."]), provider=MinuteQuota())
    assert calls["n"] == enricher.LLM_RETRIES  # retried the full budget


def test_daily_quota_discriminator_matches_real_error_shape():
    # Guards the integration assumption: the google-genai SDK stringifies a 429 as
    # "<code> <status>. <details-json>", so the per-day vs per-minute distinction lives in
    # the QuotaFailure quotaId. If that shape changes, the synthetic-message tests above
    # would still pass while the feature silently broke — this pins the real shape.
    from planthood.enrich.enricher import _is_daily_quota_exhausted

    rpd = (
        "429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'status': 'RESOURCE_EXHAUSTED', "
        "'details': [{'@type': 'type.googleapis.com/google.rpc.QuotaFailure', 'violations': "
        "[{'quotaMetric': 'generativelanguage.googleapis.com/generate_content_free_tier_requests', "
        "'quotaId': 'GenerateRequestsPerDayPerProjectPerModel-FreeTier'}]}]}}"
    )
    rpm = rpd.replace("PerDayPerProjectPerModel", "PerMinutePerProjectPerModel")

    assert _is_daily_quota_exhausted(RuntimeError(rpd)) is True
    assert _is_daily_quota_exhausted(RuntimeError(rpm)) is False
    assert _is_daily_quota_exhausted(RuntimeError("read timed out")) is False


class _Boom(LLMProvider):
    def complete_json(self, system, user, schema):
        raise AssertionError("LLM must not be called")

    @property
    def name(self):
        return "boom"


def test_allow_llm_false_never_calls_the_llm():
    parsed = enrich_recipe(_extracted(["Chop.", "Cook."]), provider=_Boom(), allow_llm=False)
    assert len(parsed.steps) == 2  # deterministic fallback, no API call
    assert parsed.provenance == "fallback"


def test_resume_skips_already_enriched():
    ex = _extracted(["Chop the onions.", "Fry them."])
    # A prior 'llm' result for this exact text must be reused without calling the LLM.
    from planthood.enrich.enricher import source_hash

    prior = enrich_recipe(ex, provider=MockProvider())
    prior.provenance = "llm"
    prior.source_hash = source_hash(ex)
    out = enrich_all([ex], provider=_Boom(), existing=[prior])
    assert out[0] is prior  # reused as-is; _Boom would have raised


def test_limit_caps_llm_enrichments():
    # 5 cookable recipes, limit=2 → only 2 get MockProvider ('fallback' provenance here),
    # the rest fall back deterministically too; the point is the cap is respected.
    exs = [_extracted(["Chop.", "Cook."], id=f"r{i}") for i in range(5)]

    calls = {"n": 0}

    class Counting(LLMProvider):
        def complete_json(self, system, user, schema):
            calls["n"] += 1
            return {"steps": []}  # forces fallback, but counts as a call

        @property
        def name(self):
            return "counting"

    enrich_all(exs, provider=Counting(), limit=2)
    assert calls["n"] == 2  # only 2 recipes hit the LLM


def test_circuit_breaker_stops_calling_after_repeated_failures(monkeypatch):
    from planthood.enrich import enricher

    monkeypatch.setattr(enricher.time, "sleep", lambda *_: None)  # keep the test fast

    calls = {"n": 0}

    class AlwaysFails(LLMProvider):
        def complete_json(self, system, user, schema):
            calls["n"] += 1
            raise RuntimeError("rate limited")

        @property
        def name(self):
            return "fails"

    recipes = [_extracted(["Do a thing."], id=f"r{i}") for i in range(20)]
    parsed = enrich_all(recipes, provider=AlwaysFails())
    # Every recipe still gets deterministic steps...
    assert all(len(p.steps) == 1 for p in parsed)
    # ...but the breaker stopped the API hammering well before all 20 recipes.
    assert calls["n"] < 20 * enricher.LLM_RETRIES


def test_absurd_duration_is_clamped():
    ex = _extracted(["Simmer."])
    provider = FakeProvider(
        {
            "steps": [
                {
                    "id": "step-1",
                    "label": "Simmer",
                    "type": "cook",
                    "estimated_duration_minutes": 99999,
                }
            ]
        }
    )
    parsed = enrich_recipe(ex, provider=provider)
    assert parsed.steps[0].estimated_duration_minutes <= 240


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
    provider = FakeProvider(
        [
            {
                "id": "step-1",
                "label": "Chop onions",
                "type": "prep",
                "estimated_duration_minutes": 3,
            },
            {
                "id": "step-2",
                "label": "Fry onions",
                "type": "cook",
                "estimated_duration_minutes": 6,
            },
        ]
    )
    parsed = enrich_recipe(ex, provider=provider)
    assert [s.id for s in parsed.steps] == ["step-1", "step-2"]
    assert parsed.steps[1].type == "cook"


def test_paragraph_case_uses_model_segmentation():
    ex = _extracted(
        ["Heat oil then add garlic and cook then add tomatoes and simmer."],
        extraction_method="paragraph",
        needs_llm_segmentation=True,
    )
    provider = FakeProvider(
        {
            "steps": [
                {
                    "id": "x",
                    "raw_text": "Heat oil",
                    "label": "Heat oil",
                    "type": "cook",
                    "estimated_duration_minutes": 2,
                },
                {
                    "id": "y",
                    "raw_text": "add garlic and cook",
                    "label": "Cook garlic",
                    "type": "cook",
                    "estimated_duration_minutes": 3,
                },
            ]
        }
    )
    parsed = enrich_recipe(ex, provider=provider)
    assert [s.id for s in parsed.steps] == ["step-1", "step-2"]  # renumbered
    assert parsed.steps[0].raw_text == "Heat oil"
