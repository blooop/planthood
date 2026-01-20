#!/usr/bin/env python3
"""
Analyze scheduling issues and dependency graph problems
"""

import json
import logging
from pathlib import Path
from collections import defaultdict

# Configure logging for CLI use
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def load_data():
    """Load recipe data"""
    data_dir = Path(__file__).parent / "data"

    with open(data_dir / "recipes_parsed.json", "r", encoding="utf-8") as f:
        parsed = json.load(f)

    with open(data_dir / "recipes_with_schedule.json", "r", encoding="utf-8") as f:
        scheduled = json.load(f)

    return parsed, scheduled


def analyze_dependencies(recipes):
    """Analyze dependency patterns in recipes"""
    stats = {
        "total_recipes": len(recipes),
        "recipes_with_steps": 0,
        "recipes_without_steps": 0,
        "total_steps": 0,
        "steps_with_dependencies": 0,
        "invalid_dependencies": [],
        "dependency_chains": [],
        "circular_dependencies": [],
        "orphaned_dependencies": [],
    }

    for recipe in recipes:
        steps = recipe.get("steps", [])
        if steps:
            stats["recipes_with_steps"] += 1
            stats["total_steps"] += len(steps)

            # Build dependency map for this recipe
            step_ids = {step["id"] for step in steps}
            dep_graph = defaultdict(list)

            for step in steps:
                step_id = step["id"]
                deps = step.get("requires", [])

                if deps:
                    stats["steps_with_dependencies"] += 1

                for dep in deps:
                    if dep not in step_ids:
                        stats["invalid_dependencies"].append(
                            {
                                "recipe": recipe.get("title", "Unknown"),
                                "step": step_id,
                                "missing_dep": dep,
                            }
                        )
                        stats["orphaned_dependencies"].append(dep)
                    else:
                        dep_graph[dep].append(step_id)

            # Check for long dependency chains
            for step in steps:
                chain_length = calculate_chain_length(step["id"], steps)
                if chain_length > 3:
                    stats["dependency_chains"].append(
                        {
                            "recipe": recipe.get("title", "Unknown"),
                            "step": step["id"],
                            "chain_length": chain_length,
                        }
                    )
        else:
            stats["recipes_without_steps"] += 1

    return stats


def calculate_chain_length(step_id, steps):
    """Calculate the longest dependency chain from a step"""
    step_lookup = {s["id"]: s for s in steps}

    def get_depth(sid):
        if sid not in step_lookup:
            return 0
        deps = step_lookup[sid].get("requires", [])
        if not deps:
            return 1
        return 1 + max(get_depth(d) for d in deps if d in step_lookup)

    return get_depth(step_id)


def analyze_scheduling_quality(scheduled_recipes):
    """Analyze the quality of scheduled recipes"""
    stats = {
        "total_scheduled": len(scheduled_recipes),
        "successfully_scheduled": 0,
        "empty_schedules": 0,
        "time_distribution": [],
        "critical_path_ratios": [],
        "active_time_ratios": [],
        "zero_duration_steps": 0,
        "negative_times": 0,
    }

    for recipe in scheduled_recipes:
        steps = recipe.get("steps", [])
        total_time = recipe.get("total_time_min", 0)
        active_time = recipe.get("active_time_min", 0)

        if not steps:
            stats["empty_schedules"] += 1
            continue

        stats["successfully_scheduled"] += 1
        stats["time_distribution"].append(total_time)

        # Check for scheduling issues
        for step in steps:
            if step.get("duration_min", 0) == 0:
                stats["zero_duration_steps"] += 1
            if step.get("start_min", 0) < 0 or step.get("end_min", 0) < 0:
                stats["negative_times"] += 1

        # Calculate critical path ratio
        critical_steps = sum(1 for s in steps if s.get("is_critical", False))
        if steps:
            ratio = critical_steps / len(steps)
            stats["critical_path_ratios"].append(ratio)

        # Calculate active time ratio
        if total_time > 0:
            active_ratio = active_time / total_time
            stats["active_time_ratios"].append(active_ratio)

    return stats


def print_analysis(dep_stats, sched_stats):
    """Print analysis results"""
    print("\n" + "=" * 60)
    print("DEPENDENCY ANALYSIS")
    print("=" * 60)

    print(f"Total recipes: {dep_stats['total_recipes']}")
    print(f"  With steps: {dep_stats['recipes_with_steps']}")
    print(f"  Without steps: {dep_stats['recipes_without_steps']}")
    print(f"Total steps: {dep_stats['total_steps']}")
    print(f"Steps with dependencies: {dep_stats['steps_with_dependencies']}")

    if dep_stats["invalid_dependencies"]:
        print(f"\nInvalid dependencies found: {len(dep_stats['invalid_dependencies'])}")
        for i, inv in enumerate(dep_stats["invalid_dependencies"][:5], 1):
            print(f"  {i}. Recipe: {inv['recipe'][:40]}...")
            print(f"     Step {inv['step']} requires missing {inv['missing_dep']}")

    if dep_stats["dependency_chains"]:
        print(f"\nLong dependency chains: {len(dep_stats['dependency_chains'])}")
        for i, chain in enumerate(dep_stats["dependency_chains"][:5], 1):
            print(f"  {i}. Recipe: {chain['recipe'][:40]}...")
            print(f"     Chain length: {chain['chain_length']}")

    print("\n" + "=" * 60)
    print("SCHEDULING QUALITY ANALYSIS")
    print("=" * 60)

    print(f"Total scheduled: {sched_stats['total_scheduled']}")
    print(f"  Successfully scheduled: {sched_stats['successfully_scheduled']}")
    print(f"  Empty schedules: {sched_stats['empty_schedules']}")

    if sched_stats["time_distribution"]:
        avg_time = sum(sched_stats["time_distribution"]) / len(sched_stats["time_distribution"])
        max_time = max(sched_stats["time_distribution"])
        min_time = (
            min(t for t in sched_stats["time_distribution"] if t > 0)
            if any(t > 0 for t in sched_stats["time_distribution"])
            else 0
        )

        print("\nTiming statistics:")
        print(f"  Average total time: {avg_time:.1f} min")
        print(f"  Max time: {max_time} min")
        print(f"  Min time (non-zero): {min_time} min")

    if sched_stats["critical_path_ratios"]:
        avg_critical = sum(sched_stats["critical_path_ratios"]) / len(
            sched_stats["critical_path_ratios"]
        )
        print("\nCritical path analysis:")
        print(f"  Average critical path ratio: {avg_critical:.2%}")

    if sched_stats["active_time_ratios"]:
        avg_active = sum(sched_stats["active_time_ratios"]) / len(sched_stats["active_time_ratios"])
        print("\nActive time analysis:")
        print(f"  Average active time ratio: {avg_active:.2%}")

    print("\nPotential issues:")
    print(f"  Zero duration steps: {sched_stats['zero_duration_steps']}")
    print(f"  Negative time values: {sched_stats['negative_times']}")

    # Identify problematic recipes
    print("\n" + "=" * 60)
    print("RECOMMENDATIONS")
    print("=" * 60)

    if dep_stats["recipes_without_steps"] > dep_stats["recipes_with_steps"]:
        print("⚠️  Most recipes have no parsed steps - check parser implementation")

    if dep_stats["invalid_dependencies"]:
        print("⚠️  Found invalid dependencies - implement dependency validation")

    if sched_stats["zero_duration_steps"] > 0:
        print("⚠️  Some steps have zero duration - check duration parsing")

    if sched_stats["empty_schedules"] > sched_stats["successfully_scheduled"]:
        print("⚠️  Most recipes failed to schedule - check step parsing pipeline")


def main():
    """Main analysis"""
    print("Loading recipe data...")
    parsed, scheduled = load_data()

    print("Analyzing dependencies...")
    dep_stats = analyze_dependencies(parsed)

    print("Analyzing scheduling quality...")
    sched_stats = analyze_scheduling_quality(scheduled)

    print_analysis(dep_stats, sched_stats)


if __name__ == "__main__":
    main()
