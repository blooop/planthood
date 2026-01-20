#!/usr/bin/env python3
"""
Recipe Scheduler
Computes Gantt chart timelines from dependency-aware recipe steps
"""

import json
import logging
from collections import defaultdict, deque
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import List, Dict, Optional, Tuple


DATA_DIR = Path(__file__).parent.parent / "data"

# Get logger for this module (don't configure at import time)
logger = logging.getLogger(__name__)


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
    is_critical: bool = False
    slack_min: int = 0
    latest_start_min: int = 0
    latest_end_min: int = 0
    dependencies_met: bool = True
    warnings: List[str] = field(default_factory=list)


@dataclass
class ScheduledRecipe:
    """Recipe with scheduled steps"""

    id: str
    title: str
    source_url: str
    week_label: Optional[str]
    weeks: List[str]
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

    def validate_dependencies(self, steps: List[Dict]) -> Tuple[bool, List[str]]:
        """
        Validate that all dependencies exist and there are no missing references.
        Returns (is_valid, list_of_errors)
        """
        errors = []
        all_step_ids = {step["id"] for step in steps}

        for step in steps:
            step_id = step["id"]
            for dep in step.get("requires", []):
                if dep not in all_step_ids:
                    error_msg = f"Step '{step_id}' requires non-existent step '{dep}'"
                    errors.append(error_msg)
                    logger.warning(error_msg)

        return len(errors) == 0, errors

    def detect_cycles(self, steps: List[Dict]) -> Tuple[bool, List[List[str]]]:
        """
        Detect cycles in the dependency graph using DFS.
        Returns (has_cycles, list_of_cycles)
        """
        graph = defaultdict(list)
        all_step_ids = {step["id"] for step in steps}

        # Build adjacency list
        for step in steps:
            step_id = step["id"]
            for dep in step.get("requires", []):
                if dep in all_step_ids:
                    graph[dep].append(step_id)

        # Colors: 0 = white (unvisited), 1 = gray (in progress), 2 = black (done)
        colors = {sid: 0 for sid in all_step_ids}
        cycles = []
        path = []

        def dfs(node: str) -> bool:
            """DFS to detect cycles"""
            if colors[node] == 1:  # Found a cycle
                cycle_start = path.index(node)
                cycle = path[cycle_start:] + [node]
                cycles.append(cycle)
                return True

            if colors[node] == 2:  # Already processed
                return False

            colors[node] = 1
            path.append(node)

            for neighbor in graph[node]:
                if dfs(neighbor):
                    pass  # Continue to find all cycles

            path.pop()
            colors[node] = 2
            return False

        # Check all components
        for step_id in all_step_ids:
            if colors[step_id] == 0:
                dfs(step_id)

        return len(cycles) > 0, cycles

    def topological_sort(self, steps: List[Dict]) -> List[str]:
        """
        Topologically sort steps based on dependencies.
        Returns ordered list of step IDs.
        """
        if not steps:
            return []

        # Validate dependencies first
        deps_valid, dep_errors = self.validate_dependencies(steps)
        if not deps_valid:
            logger.error(f"Dependency validation failed: {dep_errors}")

        # Check for cycles
        has_cycles, cycle_list = self.detect_cycles(steps)
        if has_cycles:
            logger.warning(f"Cycles detected in dependency graph: {cycle_list}")
            logger.warning("Attempting to break cycles and continue...")

        # Build adjacency list and in-degree map
        graph = defaultdict(list)
        in_degree = defaultdict(int)
        all_step_ids = {step["id"] for step in steps}

        # Initialize in-degree for all steps
        for step in steps:
            if step["id"] not in in_degree:
                in_degree[step["id"]] = 0

        # Build graph (ignoring invalid dependencies)
        for step in steps:
            step_id = step["id"]
            for dep in step.get("requires", []):
                if dep in all_step_ids:
                    graph[dep].append(step_id)
                    in_degree[step_id] += 1

        # Modified Kahn's algorithm with cycle breaking
        queue = deque([sid for sid in all_step_ids if in_degree[sid] == 0])
        sorted_steps = []
        iterations = 0
        max_iterations = len(all_step_ids) * 2

        while queue and iterations < max_iterations:
            current = queue.popleft()
            sorted_steps.append(current)

            for neighbor in graph[current]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

            iterations += 1

        # Handle remaining nodes (in case of cycles)
        if len(sorted_steps) != len(all_step_ids):
            remaining = all_step_ids - set(sorted_steps)
            logger.warning(
                f"Could not sort {len(remaining)} steps due to circular dependencies: {remaining}"
            )

            # Break cycles by adding remaining nodes in original order
            for step in steps:
                if step["id"] in remaining:
                    sorted_steps.append(step["id"])

        return sorted_steps

    def compute_critical_path(self, scheduled_steps: List[ScheduledStep]) -> List[ScheduledStep]:
        """
        Compute critical path using backward pass with improved error handling.
        Updates each step with latest_start_min, latest_end_min, slack_min, and is_critical.
        """
        if not scheduled_steps:
            return []

        # Build reverse dependency graph
        dependents = {s.id: [] for s in scheduled_steps}

        for step in scheduled_steps:
            for dep_id in step.requires:
                if dep_id in dependents:
                    dependents[dep_id].append(step)
                else:
                    warning = f"Dependency '{dep_id}' not found in scheduled steps"
                    step.warnings.append(warning)
                    logger.warning(f"Step '{step.id}': {warning}")

        # Find project end time
        project_end = max((step.end_min for step in scheduled_steps), default=0)

        # Initialize latest times
        for step in scheduled_steps:
            if not dependents[step.id]:  # Terminal nodes - use their actual end time
                step.latest_end_min = step.end_min
            else:
                step.latest_end_min = project_end
            step.latest_start_min = step.latest_end_min - step.duration_min

        # Backward pass with error handling
        for step in reversed(scheduled_steps):
            deps = dependents[step.id]
            if deps:
                try:
                    min_succ_start = min(d.latest_start_min for d in deps)
                    step.latest_end_min = min_succ_start
                    step.latest_start_min = min_succ_start - step.duration_min
                except (ValueError, AttributeError) as e:
                    logger.error(f"Error computing critical path for step '{step.id}': {e}")
                    step.warnings.append(f"Critical path computation error: {e}")

            # Compute slack and criticality
            step.slack_min = max(0, step.latest_start_min - step.start_min)
            step.is_critical = step.slack_min == 0

        # Log critical path summary
        critical_count = sum(1 for s in scheduled_steps if s.is_critical)
        logger.info(f"Critical path contains {critical_count}/{len(scheduled_steps)} steps")

        return scheduled_steps

    def compute_schedule(self, steps: List[Dict]) -> List[ScheduledStep]:
        """
        Compute start and end times for each step with improved dependency handling.
        Handles dependencies and allows parallel execution where possible.
        """
        if not steps:
            return []

        # Validate and prepare steps
        step_lookup = {step["id"]: step for step in steps}
        all_step_ids = set(step_lookup.keys())

        # Get topological order
        sorted_ids = self.topological_sort(steps)

        # Track when each step finishes and dependencies
        step_end_times = {}
        scheduled_steps = []
        unmet_dependencies = defaultdict(list)

        # Forward pass: compute earliest start and end times
        for step_id in sorted_ids:
            if step_id not in step_lookup:
                logger.error(f"Step '{step_id}' in sorted order but not in lookup")
                continue

            step = step_lookup[step_id]
            duration = max(0, step.get("estimated_duration_minutes", 0))  # Ensure non-negative

            # Compute earliest start time based on dependencies
            earliest_start = 0
            deps_met = True
            missing_deps = []

            for dep_id in step.get("requires", []):
                if dep_id in step_end_times:
                    earliest_start = max(earliest_start, step_end_times[dep_id])
                elif dep_id in all_step_ids:
                    # Dependency exists but not yet scheduled (cycle or error)
                    deps_met = False
                    missing_deps.append(dep_id)
                    logger.warning(f"Step '{step_id}' depends on unscheduled step '{dep_id}'")
                else:
                    # Dependency doesn't exist
                    deps_met = False
                    unmet_dependencies[step_id].append(dep_id)
                    logger.warning(f"Step '{step_id}' has non-existent dependency '{dep_id}'")

            start_time = earliest_start
            end_time = start_time + duration

            # Create scheduled step with dependency status
            scheduled_step = ScheduledStep(
                id=step["id"],
                raw_text=step.get("raw_text", ""),
                label=step.get("label", "Unnamed step"),
                type=step.get("type", "unknown"),
                duration_min=duration,
                start_min=start_time,
                end_min=end_time,
                requires=step.get("requires", []),
                can_overlap_with=step.get("can_overlap_with", []),
                equipment=step.get("equipment", []),
                temperature_c=step.get("temperature_c"),
                notes=step.get("notes", ""),
                dependencies_met=deps_met,
                warnings=missing_deps if missing_deps else [],
            )

            scheduled_steps.append(scheduled_step)
            step_end_times[step_id] = end_time

        # Log any unmet dependencies
        if unmet_dependencies:
            logger.warning(f"Steps with unmet dependencies: {dict(unmet_dependencies)}")

        # Optimize schedule for parallelism where possible (before critical path)
        scheduled_steps = self.optimize_parallel_execution(scheduled_steps)

        # Compute critical path after optimization
        scheduled_steps = self.compute_critical_path(scheduled_steps)

        return scheduled_steps

    def optimize_parallel_execution(
        self, scheduled_steps: List[ScheduledStep]
    ) -> List[ScheduledStep]:
        """
        Optimize schedule to maximize parallel execution where steps can overlap.
        """
        step_lookup = {s.id: s for s in scheduled_steps}

        for step in scheduled_steps:
            # Check if this step can be executed in parallel with any of its non-dependent steps
            for overlap_id in step.can_overlap_with:
                if overlap_id in step_lookup:
                    overlap_step = step_lookup[overlap_id]
                    # If they're not dependent on each other, they can run in parallel
                    if overlap_id not in step.requires and step.id not in overlap_step.requires:
                        # Adjust timing to allow parallel execution
                        step.start_min = min(step.start_min, overlap_step.start_min)
                        logger.debug(
                            f"Allowing parallel execution of '{step.id}' with '{overlap_id}'"
                        )

        return scheduled_steps

    def get_critical_path(self, scheduled_steps: List[ScheduledStep]) -> List[str]:
        """
        Extract the critical path as an ordered list of step IDs.
        Returns steps where is_critical=True in execution order.
        """
        if not scheduled_steps:
            return []

        critical_steps = [step for step in scheduled_steps if step.is_critical]
        # Sort by start time to get execution order
        critical_steps.sort(key=lambda s: s.start_min)
        return [step.id for step in critical_steps]

    def analyze_schedule_quality(self, scheduled_steps: List[ScheduledStep]) -> Dict:
        """
        Analyze the quality of a schedule and return metrics.
        """
        if not scheduled_steps:
            return {
                "total_steps": 0,
                "critical_steps": 0,
                "parallelizable_steps": 0,
                "average_slack": 0,
                "max_slack": 0,
                "dependency_errors": 0,
                "warnings": [],
            }

        critical_steps = sum(1 for s in scheduled_steps if s.is_critical)
        parallelizable = sum(1 for s in scheduled_steps if s.can_overlap_with)
        dep_errors = sum(1 for s in scheduled_steps if not s.dependencies_met)
        all_warnings = [w for s in scheduled_steps for w in s.warnings]

        slack_values = [s.slack_min for s in scheduled_steps]
        avg_slack = sum(slack_values) / len(slack_values) if slack_values else 0
        max_slack = max(slack_values) if slack_values else 0

        return {
            "total_steps": len(scheduled_steps),
            "critical_steps": critical_steps,
            "parallelizable_steps": parallelizable,
            "average_slack": round(avg_slack, 2),
            "max_slack": max_slack,
            "dependency_errors": dep_errors,
            "warnings": all_warnings[:10],  # Limit to first 10 warnings
        }

    def schedule_recipe(self, recipe: Dict) -> ScheduledRecipe:
        """Schedule a single recipe with improved time calculation"""
        steps = recipe.get("steps", [])

        # Convert step dicts to proper format if needed
        step_dicts = []
        for step in steps:
            if isinstance(step, dict):
                # Validate step has required fields
                if "id" not in step:
                    logger.warning(
                        f"Step missing 'id' field in recipe '{recipe.get('title', 'Unknown')}'"
                    )
                    step["id"] = f"step-{len(step_dicts) + 1}"
                if "label" not in step:
                    step["label"] = step.get("raw_text", "Unnamed step")[:50]
                if "type" not in step:
                    step["type"] = "unknown"
                step_dicts.append(step)
            else:
                # Handle case where steps might be objects
                step_dict = step if isinstance(step, dict) else step.__dict__
                step_dicts.append(step_dict)

        scheduled_steps = self.compute_schedule(step_dicts)

        # Calculate total and active time with better logic
        total_time = max((s.end_min for s in scheduled_steps), default=0)

        # Calculate active time more accurately
        active_time = self.calculate_active_time(scheduled_steps)

        # Log schedule quality metrics
        metrics = self.analyze_schedule_quality(scheduled_steps)
        if metrics["dependency_errors"] > 0:
            logger.warning(
                f"Recipe '{recipe.get('title', 'Unknown')}' has {metrics['dependency_errors']} dependency errors"
            )

        return ScheduledRecipe(
            id=recipe.get("id", "unknown"),
            title=recipe.get("title", "Untitled"),
            source_url=recipe.get("source_url", ""),
            week_label=recipe.get("week_label"),
            weeks=recipe.get("weeks", []),
            category=recipe.get("category"),
            ingredients=recipe.get("ingredients", []),
            nutrition=recipe.get("nutrition"),
            steps=scheduled_steps,
            total_time_min=total_time,
            active_time_min=active_time,
        )

    def calculate_active_time(self, scheduled_steps: List[ScheduledStep]) -> int:
        """
        Calculate active cooking time (when cook is actively working).
        Accounts for parallel tasks and passive waiting times.
        """
        if not scheduled_steps:
            return 0

        # Active types are prep, finish, and some cook activities
        active_types = {"prep", "finish", "cook"}
        passive_types = {"bake", "simmer", "rest", "chill", "marinate"}

        # Calculate overlapping time intervals
        active_intervals = []
        for step in scheduled_steps:
            # Check if step is active or passive
            is_active = step.type in active_types
            is_passive = step.type in passive_types or "wait" in step.label.lower()

            if is_active and not is_passive:
                active_intervals.append((step.start_min, step.end_min))

        # Merge overlapping intervals
        if not active_intervals:
            return 0

        active_intervals.sort()
        merged = [active_intervals[0]]

        for start, end in active_intervals[1:]:
            if start <= merged[-1][1]:
                # Overlapping intervals, merge them
                merged[-1] = (merged[-1][0], max(merged[-1][1], end))
            else:
                # Non-overlapping interval
                merged.append((start, end))

        # Sum the merged intervals
        return sum(end - start for start, end in merged)

    def schedule_all_recipes(self, parsed_recipes: List[Dict]) -> List[ScheduledRecipe]:
        """Schedule all recipes with improved error handling and reporting"""
        scheduled_recipes = []
        success_count = 0
        error_count = 0
        empty_count = 0

        for i, recipe in enumerate(parsed_recipes, 1):
            recipe_title = recipe.get("title", "Untitled")
            recipe_id = recipe.get("id", f"recipe_{i}")

            try:
                if not recipe.get("steps"):
                    empty_count += 1
                    logger.debug(f"Skipping '{recipe_title}' - no steps to schedule")
                    # Still create a scheduled recipe with empty steps
                    scheduled = ScheduledRecipe(
                        id=recipe_id,
                        title=recipe_title,
                        source_url=recipe.get("source_url", ""),
                        week_label=recipe.get("week_label"),
                        weeks=recipe.get("weeks", []),
                        category=recipe.get("category"),
                        ingredients=recipe.get("ingredients", []),
                        nutrition=recipe.get("nutrition"),
                        steps=[],
                        total_time_min=0,
                        active_time_min=0,
                    )
                    scheduled_recipes.append(scheduled)
                    continue

                scheduled = self.schedule_recipe(recipe)
                scheduled_recipes.append(scheduled)

                # Get critical path info
                critical_path = self.get_critical_path(scheduled.steps)
                critical_count = len(critical_path)
                total_count = len(scheduled.steps)

                # Check for warnings
                steps_with_warnings = [s for s in scheduled.steps if s.warnings]
                if steps_with_warnings:
                    logger.warning(
                        f"Recipe '{recipe_title}' has {len(steps_with_warnings)} steps with warnings"
                    )

                print(
                    f"Scheduled {recipe_title}: "
                    f"{scheduled.total_time_min} min total, "
                    f"{critical_count}/{total_count} steps on critical path"
                )
                success_count += 1

            except Exception as e:
                error_count += 1
                logger.error(f"Error scheduling '{recipe_title}': {e}", exc_info=True)
                # Create a placeholder scheduled recipe
                scheduled = ScheduledRecipe(
                    id=recipe_id,
                    title=recipe_title,
                    source_url=recipe.get("source_url", ""),
                    week_label=recipe.get("week_label"),
                    weeks=recipe.get("weeks", []),
                    category=recipe.get("category"),
                    ingredients=recipe.get("ingredients", []),
                    nutrition=recipe.get("nutrition"),
                    steps=[],
                    total_time_min=0,
                    active_time_min=0,
                )
                scheduled_recipes.append(scheduled)

        # Summary report
        logger.info(
            f"Scheduling complete: {success_count} successful, "
            f"{empty_count} empty, {error_count} errors out of {len(parsed_recipes)} total recipes"
        )

        return scheduled_recipes


def main():
    """Main scheduler execution"""
    # Configure logging for CLI use
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

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
        f.write("\n")

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
