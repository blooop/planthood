"""Schedule stage: compute a correct Gantt timeline from dependency-aware steps.

Invariants the old scheduler violated and this one guarantees:
  * ``end_min == start_min + duration_min`` for every step.
  * no step starts before every step in its ``requires`` has finished.

Parallelism emerges naturally from the dependency graph (independent steps share early
start times); we never mutate start times, which is what corrupted the old timelines.
"""

from .scheduler import schedule_all, schedule_recipe

__all__ = ["schedule_recipe", "schedule_all"]
