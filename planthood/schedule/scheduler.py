"""Dependency-aware recipe scheduler (correct forward pass + critical path)."""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Dict, List

from ..models import ParsedRecipe, RecipeStep, ScheduledRecipe, ScheduledStep

# Hands-off phases: the cook can do other work while these run, so they don't count as
# active time. Matched as substrings against a step's label/text/notes.
PASSIVE_PHRASES = (
    "bake",
    "roast",
    "simmer",
    "rest for",
    "leave to",
    "leave it",
    "set aside",
    "marinate",
    "chill",
    "refrigerate",
    "soak",
    "prove",
    "proof",
    "cool for",
    "cool down",
    "cool completely",
    "reduce for",
    "let it sit",
    "leave for",
)


def _topological_order(steps: List[RecipeStep]) -> List[str]:
    """Kahn's algorithm; any steps left over by a dependency cycle are appended in
    input order so the schedule still covers every step."""
    ids = [s.id for s in steps]
    id_set = set(ids)
    graph: Dict[str, List[str]] = defaultdict(list)
    indeg: Dict[str, int] = {sid: 0 for sid in ids}

    for s in steps:
        for dep in s.requires:
            if dep in id_set and dep != s.id:
                graph[dep].append(s.id)
                indeg[s.id] += 1

    queue = deque([sid for sid in ids if indeg[sid] == 0])
    order: List[str] = []
    while queue:
        cur = queue.popleft()
        order.append(cur)
        for nxt in graph[cur]:
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                queue.append(nxt)

    if len(order) < len(ids):  # cycle: append remaining in input order
        seen = set(order)
        order.extend(sid for sid in ids if sid not in seen)
    return order


def _is_passive(step: RecipeStep) -> bool:
    text = f"{step.label} {step.raw_text} {step.notes}".lower()
    return any(p in text for p in PASSIVE_PHRASES)


def _active_time(scheduled: List[ScheduledStep], passive_ids: set) -> int:
    """Total wall-clock time the cook is actively engaged = union of non-passive
    step intervals (passive waiting doesn't count, but active prep during a bake does)."""
    intervals = sorted((s.start_min, s.end_min) for s in scheduled if s.id not in passive_ids)
    if not intervals:
        return 0
    merged = [list(intervals[0])]
    for start, end in intervals[1:]:
        if start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return sum(end - start for start, end in merged)


def schedule_recipe(recipe: ParsedRecipe) -> ScheduledRecipe:
    """Compute a timeline for one recipe."""
    base = recipe.model_dump(exclude={"schema_version", "steps", "cookable"})
    steps = recipe.steps
    if not steps:
        return ScheduledRecipe(**base, steps=[], total_time_min=0, active_time_min=0)

    lookup = {s.id: s for s in steps}
    order = _topological_order(steps)
    dur = {s.id: max(1, s.estimated_duration_minutes) for s in steps}

    # Forward pass: earliest start = max end of prerequisites; end = start + duration.
    start: Dict[str, int] = {}
    end: Dict[str, int] = {}
    for sid in order:
        s = lookup[sid]
        est = 0
        for dep in s.requires:
            if dep in end:  # dep already scheduled (guaranteed unless a cycle)
                est = max(est, end[dep])
        start[sid] = est
        end[sid] = est + dur[sid]

    total = max(end.values())

    # Backward pass (critical path): latest times without delaying the makespan.
    dependents: Dict[str, List[str]] = {s.id: [] for s in steps}
    for s in steps:
        for dep in s.requires:
            if dep in dependents and dep != s.id:
                dependents[dep].append(s.id)

    latest_start: Dict[str, int] = {}
    latest_end: Dict[str, int] = {}
    for sid in reversed(order):  # successors processed before their predecessors
        succ = dependents[sid]
        # .get(..., total) tolerates a dependency cycle, where a successor may not yet
        # have a computed latest_start when we reach this node in reverse order.
        le = min((latest_start.get(d, total) for d in succ), default=total)
        latest_end[sid] = le
        latest_start[sid] = le - dur[sid]

    passive_ids = {s.id for s in steps if _is_passive(s)}

    scheduled: List[ScheduledStep] = []
    for s in steps:  # preserve input order; the site sorts by start_min for display
        slack = max(0, latest_start[s.id] - start[s.id])
        scheduled.append(
            ScheduledStep(
                id=s.id,
                raw_text=s.raw_text,
                label=s.label,
                type=s.type,
                duration_min=dur[s.id],
                start_min=start[s.id],
                end_min=end[s.id],
                requires=list(s.requires),
                can_overlap_with=list(s.can_overlap_with),
                equipment=list(s.equipment),
                temperature_c=s.temperature_c,
                notes=s.notes,
                is_critical=slack == 0,
                slack_min=slack,
                latest_start_min=latest_start[s.id],
                latest_end_min=latest_end[s.id],
            )
        )

    return ScheduledRecipe(
        **base,
        steps=scheduled,
        total_time_min=total,
        active_time_min=_active_time(scheduled, passive_ids),
    )


def schedule_all(recipes: List[ParsedRecipe]) -> List[ScheduledRecipe]:
    """Schedule every recipe."""
    return [schedule_recipe(r) for r in recipes]
