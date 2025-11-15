#!/usr/bin/env python3
"""
Recipe Scheduler
Computes Gantt chart timelines from dependency-aware recipe steps
"""

import json
from collections import defaultdict, deque
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Dict, Optional


DATA_DIR = Path(__file__).parent.parent / "data"


@dataclass
class ScheduledStep:
    """Recipe step with computed timeline"""

    id: str
    raw_text: str
    label: str
    type: str
    duration_min: int
    start_min: int
    end_min: int
    requires: List[str]
    can_overlap_with: List[str]
    equipment: List[str]
    temperature_c: Optional[int]
    notes: str


@dataclass
class ScheduledRecipe:
    """Recipe with scheduled steps"""

    id: str
    title: str
    source_url: str
    week_label: Optional[str]
    category: Optional[str]
    ingredients: List[str]
    nutrition: Optional[Dict]
    steps: List[ScheduledStep]
    total_time_min: int
    active_time_min: int


class RecipeScheduler:
    """Dependency-aware recipe scheduler"""

    def __init__(self):
        pass

    def topological_sort(self, steps: List[Dict]) -> List[str]:
        """
        Topologically sort steps based on dependencies.
        Returns ordered list of step IDs.
        """
        # Build adjacency list and in-degree map
        graph = defaultdict(list)
        in_degree = defaultdict(int)
        all_step_ids = {step["id"] for step in steps}

        # Initialize in-degree for all steps
        for step in steps:
            if step["id"] not in in_degree:
                in_degree[step["id"]] = 0

        # Build graph
        for step in steps:
            step_id = step["id"]
            for dep in step.get("requires", []):
                if dep in all_step_ids:
                    graph[dep].append(step_id)
                    in_degree[step_id] += 1

        # Kahn's algorithm for topological sort
        queue = deque([sid for sid in all_step_ids if in_degree[sid] == 0])
        sorted_steps = []

        while queue:
            current = queue.popleft()
            sorted_steps.append(current)

            for neighbor in graph[current]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # Check for cycles
        if len(sorted_steps) != len(all_step_ids):
            print("Warning: Cycle detected in dependencies. Using fallback ordering.")
            # Fallback: use original order
            return [step["id"] for step in steps]

        return sorted_steps

    def compute_schedule(self, steps: List[Dict]) -> List[ScheduledStep]:
        """
        Compute start and end times for each step.
        Handles dependencies and allows parallel execution where possible.
        """
        if not steps:
            return []

        # Create step lookup
        step_lookup = {step["id"]: step for step in steps}

        # Get topological order
        sorted_ids = self.topological_sort(steps)

        # Track when each step finishes
        step_end_times = {}

        # Track what steps are running at each time point (for overlap checking)
        scheduled_steps = []

        for step_id in sorted_ids:
            step = step_lookup[step_id]
            duration = step.get("estimated_duration_minutes", 0)

            # Compute earliest start time based on dependencies
            earliest_start = 0
            for dep_id in step.get("requires", []):
                if dep_id in step_end_times:
                    earliest_start = max(earliest_start, step_end_times[dep_id])

            start_time = earliest_start
            end_time = start_time + duration

            # Store scheduled step
            scheduled_step = ScheduledStep(
                id=step["id"],
                raw_text=step.get("raw_text", ""),
                label=step["label"],
                type=step["type"],
                duration_min=duration,
                start_min=start_time,
                end_min=end_time,
                requires=step.get("requires", []),
                can_overlap_with=step.get("can_overlap_with", []),
                equipment=step.get("equipment", []),
                temperature_c=step.get("temperature_c"),
                notes=step.get("notes", ""),
            )
            scheduled_steps.append(scheduled_step)
            step_end_times[step_id] = end_time

        return scheduled_steps

    def schedule_recipe(self, recipe: Dict) -> ScheduledRecipe:
        """Schedule a single recipe"""
        steps = recipe.get("steps", [])

        # Convert step dicts to proper format if needed
        step_dicts = []
        for step in steps:
            if isinstance(step, dict):
                step_dicts.append(step)
            else:
                # Handle case where steps might be objects
                step_dicts.append(step if isinstance(step, dict) else step.__dict__)

        scheduled_steps = self.compute_schedule(step_dicts)

        # Calculate total and active time
        total_time = max((s.end_min for s in scheduled_steps), default=0)

        # Active time = sum of all non-overlapping prep/cook steps
        # Simplified: sum of all prep and some cook steps
        active_time = sum(s.duration_min for s in scheduled_steps if s.type in ["prep", "finish"])

        return ScheduledRecipe(
            id=recipe["id"],
            title=recipe["title"],
            source_url=recipe["source_url"],
            week_label=recipe.get("week_label"),
            category=recipe.get("category"),
            ingredients=recipe.get("ingredients", []),
            nutrition=recipe.get("nutrition"),
            steps=scheduled_steps,
            total_time_min=total_time,
            active_time_min=active_time,
        )

    def schedule_all_recipes(self, parsed_recipes: List[Dict]) -> List[ScheduledRecipe]:
        """Schedule all recipes"""
        scheduled_recipes = []

        for recipe in parsed_recipes:
            try:
                scheduled = self.schedule_recipe(recipe)
                scheduled_recipes.append(scheduled)
                print(f"Scheduled {recipe['title']}: {scheduled.total_time_min} min total")
            except Exception as e:
                print(f"Error scheduling {recipe['title']}: {e}")

        return scheduled_recipes


def main():
    """Main scheduler execution"""
    print("=" * 60)
    print("Recipe Scheduler")
    print("=" * 60)

    # Load parsed recipes
    parsed_recipes_path = DATA_DIR / "recipes_parsed.json"
    if not parsed_recipes_path.exists():
        print(f"Error: {parsed_recipes_path} not found")
        print("Run the parser first: npm run parse")
        return

    with open(parsed_recipes_path, "r", encoding="utf-8") as f:
        parsed_recipes = json.load(f)

    print(f"Loaded {len(parsed_recipes)} parsed recipes")

    # Schedule recipes
    scheduler = RecipeScheduler()
    scheduled_recipes = scheduler.schedule_all_recipes(parsed_recipes)

    # Save scheduled recipes
    output_path = DATA_DIR / "recipes_with_schedule.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(
            [asdict(r) for r in scheduled_recipes],
            f,
            indent=2,
            ensure_ascii=False,
        )

    # Print summary
    print(f"\n{'=' * 60}")
    print(f"Scheduled {len(scheduled_recipes)} recipes")
    if scheduled_recipes:
        avg_time = sum(r.total_time_min for r in scheduled_recipes) / len(scheduled_recipes)
        print(f"Average cooking time: {avg_time:.1f} minutes")
    print(f"Saved to: {output_path}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
