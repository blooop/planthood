"""Tests for the quality report + threshold checks."""

from planthood.models import (
    ExtractedRecipe,
    ExtractedStep,
    RawRecipe,
    ScheduledRecipe,
    ScheduledStep,
)
from planthood.quality import check_thresholds, compute_report


def _scheduled_step(sid, start, dur, requires=None, raw_text="do a thing"):
    return ScheduledStep(
        id=sid,
        raw_text=raw_text,
        label=sid,
        type="cook",
        duration_min=dur,
        start_min=start,
        end_min=start + dur,
        requires=requires or [],
    )


def test_clean_run_passes_thresholds():
    raw = RawRecipe(id="r1", title="T", method="Preheat oven. Chop the onions finely.")
    extracted = [
        ExtractedRecipe(
            id="r1",
            title="T",
            cookable=True,
            steps=[ExtractedStep(id="step-1", text="Chop the onions finely.")],
        )
    ]
    scheduled = [
        ScheduledRecipe(
            id="r1",
            title="T",
            total_time_min=5,
            active_time_min=5,
            steps=[_scheduled_step("step-1", 0, 5, raw_text="Chop the onions finely.")],
        )
    ]
    report = compute_report(extracted, scheduled, [raw])
    assert report["grounding"] == 1.0
    assert report["cookable_empty_rate"] == 0.0
    assert report["timeline_violations"] == 0
    passed, failures = check_thresholds(report)
    assert passed, failures


def test_empty_cookable_recipe_flagged():
    raw = RawRecipe(id="r1", title="T", method="STEP 1 Cook it.")
    extracted = [
        ExtractedRecipe(
            id="r1", title="T", cookable=True, steps=[ExtractedStep(id="step-1", text="Cook it.")]
        )
    ]
    # Scheduling produced no steps (a failure) → empty rate 100%.
    scheduled = [ScheduledRecipe(id="r1", title="T", steps=[])]
    report = compute_report(extracted, scheduled, [raw])
    assert report["cookable_empty_rate"] == 1.0
    passed, failures = check_thresholds(report)
    assert not passed
    assert any("cookable_empty_rate" in f for f in failures)


def test_timeline_violation_detected():
    raw = RawRecipe(id="r1", title="T", method="Chop the onions.")
    extracted = [
        ExtractedRecipe(
            id="r1",
            title="T",
            cookable=True,
            steps=[ExtractedStep(id="step-1", text="Chop the onions.")],
        )
    ]
    bad = ScheduledStep(
        id="step-1",
        raw_text="Chop the onions.",
        label="x",
        type="prep",
        duration_min=5,
        start_min=0,
        end_min=99,
    )  # end != start+dur
    scheduled = [ScheduledRecipe(id="r1", title="T", steps=[bad])]
    report = compute_report(extracted, scheduled, [raw])
    assert report["timeline_violations"] == 1
    assert not check_thresholds(report)[0]


def test_ungrounded_step_lowers_grounding():
    raw = RawRecipe(id="r1", title="T", method="Chop the onions.")
    extracted = [
        ExtractedRecipe(
            id="r1",
            title="T",
            cookable=True,
            steps=[ExtractedStep(id="step-1", text="Chop the onions.")],
        )
    ]
    scheduled = [
        ScheduledRecipe(
            id="r1",
            title="T",
            total_time_min=5,
            active_time_min=5,
            steps=[_scheduled_step("step-1", 0, 5, raw_text="fly to the moon")],
        )
    ]
    report = compute_report(extracted, scheduled, [raw])
    assert report["grounding"] == 0.0
