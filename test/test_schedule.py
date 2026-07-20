"""Unit tests for the scheduler — focused on the invariants the old one violated."""

from planthood.models import ParsedRecipe, RecipeStep
from planthood.schedule import schedule_recipe


def _recipe(steps):
    return ParsedRecipe(id="r1", title="T", steps=steps)


def _step(sid, dur, requires=None, stype="cook", **kw):
    return RecipeStep(
        id=sid,
        raw_text=kw.get("raw_text", sid),
        label=kw.get("label", sid),
        type=stype,
        estimated_duration_minutes=dur,
        requires=requires or [],
        can_overlap_with=kw.get("can_overlap_with", []),
    )


def test_end_equals_start_plus_duration():
    sched = schedule_recipe(
        _recipe(
            [
                _step("step-1", 5),
                _step("step-2", 3, requires=["step-1"]),
                _step("step-3", 4, requires=["step-2"]),
            ]
        )
    )
    for s in sched.steps:
        assert s.end_min == s.start_min + s.duration_min


def test_no_step_starts_before_its_dependencies_finish():
    sched = schedule_recipe(
        _recipe(
            [
                _step("step-1", 10),
                _step("step-2", 5, requires=["step-1"]),
                _step("step-3", 2, requires=["step-1", "step-2"]),
            ]
        )
    )
    by_id = {s.id: s for s in sched.steps}
    for s in sched.steps:
        for dep in s.requires:
            assert s.start_min >= by_id[dep].end_min


def test_independent_steps_run_in_parallel():
    # Two steps with no dependency between them both start at time 0.
    sched = schedule_recipe(
        _recipe([_step("step-1", 5, stype="prep"), _step("step-2", 8, stype="prep")])
    )
    by_id = {s.id: s for s in sched.steps}
    assert by_id["step-1"].start_min == 0
    assert by_id["step-2"].start_min == 0


def test_total_time_is_makespan():
    # step-1 (10) -> step-3 (4); step-2 (3) parallel. Makespan = 14.
    sched = schedule_recipe(
        _recipe(
            [
                _step("step-1", 10),
                _step("step-2", 3),
                _step("step-3", 4, requires=["step-1"]),
            ]
        )
    )
    assert sched.total_time_min == 14


def test_critical_path_marked():
    sched = schedule_recipe(
        _recipe(
            [
                _step("step-1", 10),
                _step("step-2", 3),  # slack: not critical
                _step("step-3", 4, requires=["step-1"]),
            ]
        )
    )
    by_id = {s.id: s for s in sched.steps}
    assert by_id["step-1"].is_critical
    assert by_id["step-3"].is_critical
    assert not by_id["step-2"].is_critical
    assert by_id["step-2"].slack_min > 0


def test_active_time_excludes_passive_waiting():
    # A 30-min unattended roast should not count as active cooking time.
    sched = schedule_recipe(
        _recipe(
            [
                _step("step-1", 5, stype="prep", label="Chop veg", raw_text="Chop the veg"),
                _step(
                    "step-2",
                    30,
                    stype="cook",
                    label="Roast veg",
                    raw_text="Roast in the oven for 30 minutes",
                    requires=["step-1"],
                ),
            ]
        )
    )
    assert sched.total_time_min == 35
    assert sched.active_time_min < sched.total_time_min
    assert sched.active_time_min == 5  # only the chop is active


def test_cycle_does_not_crash():
    sched = schedule_recipe(
        _recipe(
            [
                _step("step-1", 5, requires=["step-2"]),
                _step("step-2", 5, requires=["step-1"]),
            ]
        )
    )
    assert len(sched.steps) == 2
    for s in sched.steps:
        assert s.end_min == s.start_min + s.duration_min


def test_empty_recipe():
    sched = schedule_recipe(_recipe([]))
    assert sched.steps == []
    assert sched.total_time_min == 0
    assert sched.active_time_min == 0
