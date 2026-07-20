"""Compute pipeline quality metrics and check them against thresholds."""

from __future__ import annotations

from typing import Dict, List, Tuple

from ..models import ExtractedRecipe, RawRecipe, ScheduledRecipe
from ..text import normalize_whitespace

# A run is "good" when it clears every threshold. Tune as the pipeline matures.
THRESHOLDS = {
    "cookable_empty_rate_max": 0.05,  # <=5% of cookable recipes may end up with no steps
    "grounding_min": 0.85,  # >=85% of steps quote real source text
    "timeline_violations_max": 0,  # end==start+dur and no step before its deps
    "invalid_dep_rate_max": 0.0,  # every 'requires' points to a real step
    "cycles_max": 0,
}


def _norm(s: str) -> str:
    return normalize_whitespace(s).lower()


def _has_cycle(steps) -> bool:
    ids = {s.id for s in steps}
    graph = {s.id: [d for d in s.requires if d in ids and d != s.id] for s in steps}
    color = {sid: 0 for sid in ids}  # 0 white, 1 grey, 2 black

    def visit(n: str) -> bool:
        color[n] = 1
        for m in graph[n]:
            if color[m] == 1 or (color[m] == 0 and visit(m)):
                return True
        color[n] = 2
        return False

    return any(color[sid] == 0 and visit(sid) for sid in ids)


def compute_report(
    extracted: List[ExtractedRecipe],
    scheduled: List[ScheduledRecipe],
    raws: List[RawRecipe],
) -> Dict:
    """Compute the quality scorecard across all three artifacts."""
    raw_by_id = {r.id: r for r in raws}
    sched_by_id = {s.id: s for s in scheduled}

    cookable = [e for e in extracted if e.cookable]
    n_cook = len(cookable)
    cook_with_steps = sum(1 for e in cookable if sched_by_id.get(e.id) and sched_by_id[e.id].steps)
    empty_rate = (n_cook - cook_with_steps) / n_cook if n_cook else 0.0

    grounded = total_steps = 0
    timeline_violations = invalid_dep = dep_order_violations = cycles = 0

    for s in scheduled:
        raw = raw_by_id.get(s.id)
        method = _norm(raw.method) if raw else ""
        ids = {x.id for x in s.steps}
        by_id = {x.id: x for x in s.steps}
        for st in s.steps:
            total_steps += 1
            if method and _norm(st.raw_text) and _norm(st.raw_text) in method:
                grounded += 1
            if st.end_min != st.start_min + st.duration_min:
                timeline_violations += 1
            for d in st.requires:
                if d not in ids:
                    invalid_dep += 1
                elif st.start_min < by_id[d].end_min:
                    dep_order_violations += 1
        if _has_cycle(s.steps):
            cycles += 1

    grounding = grounded / total_steps if total_steps else 1.0

    return {
        "recipes_total": len(scheduled),
        "recipes_cookable": n_cook,
        "recipes_with_steps": sum(1 for s in scheduled if s.steps),
        "cookable_empty_rate": round(empty_rate, 4),
        "grounding": round(grounding, 4),
        "total_steps": total_steps,
        "timeline_violations": timeline_violations + dep_order_violations,
        "invalid_dep_rate": round(invalid_dep / total_steps, 4) if total_steps else 0.0,
        "cycles": cycles,
    }


def check_thresholds(report: Dict) -> Tuple[bool, List[str]]:
    """Return (passed, failures). Each failure names the metric and the breach."""
    failures = []
    checks = [
        ("cookable_empty_rate", "<=", THRESHOLDS["cookable_empty_rate_max"]),
        ("grounding", ">=", THRESHOLDS["grounding_min"]),
        ("timeline_violations", "<=", THRESHOLDS["timeline_violations_max"]),
        ("invalid_dep_rate", "<=", THRESHOLDS["invalid_dep_rate_max"]),
        ("cycles", "<=", THRESHOLDS["cycles_max"]),
    ]
    for metric, op, limit in checks:
        value = report[metric]
        ok = value <= limit if op == "<=" else value >= limit
        if not ok:
            failures.append(f"{metric} = {value} (want {op} {limit})")
    return len(failures) == 0, failures


def format_report(report: Dict) -> str:
    """Render the scorecard as aligned text."""
    passed, failures = check_thresholds(report)
    lines = ["Recipe pipeline quality report", "=" * 34]
    for k, v in report.items():
        lines.append(f"  {k:24} {v}")
    lines.append("-" * 34)
    lines.append("  RESULT: " + ("PASS ✅" if passed else "FAIL ❌"))
    for f in failures:
        lines.append(f"    - {f}")
    return "\n".join(lines)
