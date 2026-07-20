"""Unified command line for the recipe pipeline.

python -m planthood.cli extract          # raw    -> extracted   (deterministic)
python -m planthood.cli enrich           # extracted -> parsed   (LLM; --provider mock offline)
python -m planthood.cli schedule         # parsed  -> scheduled
python -m planthood.cli build-data       # extract + enrich + schedule
python -m planthood.cli quality          # print the quality scorecard (exit 1 on fail)
python -m planthood.cli inspect <id>     # run one recipe through every stage and show it
"""

from __future__ import annotations

import argparse
import sys

from . import io
from .enrich import enrich_all, enrich_recipe
from .extract import extract_all, extract_recipe
from .llm import get_provider
from .models import ExtractedRecipe, ParsedRecipe, RawRecipe, ScheduledRecipe
from .quality import compute_report, format_report
from .schedule import schedule_all, schedule_recipe


def _load(path, model, label):
    recipes = io.load_recipes(path, model)
    if not recipes:
        print(f"No {label} found at {path}. Run the previous stage first.")
        sys.exit(1)
    return recipes


def cmd_extract(_args) -> None:
    raws = _load(io.RAW_PATH, RawRecipe, "raw recipes")
    extracted = extract_all(raws)
    io.dump_recipes(io.EXTRACTED_PATH, extracted)  # deterministic: full rebuild
    cookable = sum(1 for e in extracted if e.cookable)
    with_steps = sum(1 for e in extracted if e.steps)
    print(f"Extracted {len(extracted)} recipes: {cookable} cookable, {with_steps} with steps")
    print(f"Saved to {io.EXTRACTED_PATH}")


def cmd_enrich(args) -> None:
    extracted = _load(io.EXTRACTED_PATH, ExtractedRecipe, "extracted recipes")
    provider = get_provider(args.provider)
    # Resume from prior results: recipes already LLM-enriched (for their current text) are
    # reused, so a daily run only spends quota on the backlog. --fresh ignores prior results.
    existing = None if args.fresh else io.load_recipes(io.PARSED_PATH, ParsedRecipe)
    print(f"Enriching with provider: {provider.name} (limit={args.limit or 'none'})")
    parsed = enrich_all(extracted, provider=provider, existing=existing, limit=args.limit)
    io.dump_recipes(io.PARSED_PATH, parsed)  # parsed is the complete, resume-aware set
    print(f"Enriched {len(parsed)} recipes; {sum(1 for r in parsed if r.steps)} have steps")
    print(f"Saved to {io.PARSED_PATH}")


def cmd_schedule(_args) -> None:
    parsed = _load(io.PARSED_PATH, ParsedRecipe, "parsed recipes")
    scheduled = schedule_all(parsed)
    io.dump_recipes(io.SCHEDULED_PATH, scheduled)  # deterministic from parsed
    with_steps = [r for r in scheduled if r.steps]
    avg = sum(r.total_time_min for r in with_steps) / len(with_steps) if with_steps else 0
    print(f"Scheduled {len(scheduled)} recipes; avg cook time {avg:.0f} min")
    print(f"Saved to {io.SCHEDULED_PATH}")


def cmd_build_data(args) -> None:
    cmd_extract(args)
    cmd_enrich(args)
    cmd_schedule(args)


def cmd_quality(_args) -> None:
    extracted = io.load_recipes(io.EXTRACTED_PATH, ExtractedRecipe)
    scheduled = io.load_recipes(io.SCHEDULED_PATH, ScheduledRecipe)
    raws = io.load_recipes(io.RAW_PATH, RawRecipe)
    if not scheduled or not extracted:
        print("Missing artifacts. Run build-data first.")
        sys.exit(1)
    report = compute_report(extracted, scheduled, raws)
    print(format_report(report))
    from .quality import check_thresholds

    passed, _ = check_thresholds(report)
    sys.exit(0 if passed else 1)


def cmd_inspect(args) -> None:
    """Run a single recipe through every stage and print the result."""
    raws = {r.id: r for r in io.load_recipes(io.RAW_PATH, RawRecipe)}
    raw = raws.get(args.recipe)
    if raw is None:
        matches = [rid for rid in raws if args.recipe.lower() in rid.lower()]
        if len(matches) == 1:
            raw = raws[matches[0]]
        else:
            print(
                f"Recipe '{args.recipe}' not found."
                + (f" Did you mean: {matches[:5]}" if matches else "")
            )
            sys.exit(1)

    extracted = extract_recipe(raw)
    provider = get_provider(args.provider)
    parsed = enrich_recipe(extracted, provider=provider)
    scheduled = schedule_recipe(parsed)

    print(f"\n{raw.title}\n{'=' * len(raw.title)}")
    print(
        f"id={raw.id}  cookable={extracted.cookable}  method={extracted.extraction_method}  "
        f"provider={provider.name}"
    )
    print(
        f"total={scheduled.total_time_min}min  active={scheduled.active_time_min}min  "
        f"steps={len(scheduled.steps)}\n"
    )
    for s in sorted(scheduled.steps, key=lambda x: x.start_min):
        crit = " *critical*" if s.is_critical else f" slack={s.slack_min}"
        temp = f" {s.temperature_c}C" if s.temperature_c else ""
        print(
            f"  [{s.start_min:>3}-{s.end_min:<3}] {s.id} ({s.type},{s.duration_min}min{temp}){crit}"
        )
        print(f"        {s.label}  req={s.requires} equip={s.equipment}")
        print(f"        └ {s.raw_text[:90]}")


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(prog="planthood", description="Recipe pipeline CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_provider(p):
        p.add_argument(
            "--provider",
            default=None,
            help="LLM provider (anthropic|openai|gemini|mock). Default: $LLM_PROVIDER or anthropic",
        )

    def add_enrich_opts(p):
        add_provider(p)
        p.add_argument(
            "--limit",
            type=int,
            default=0,
            help="max recipes to LLM-enrich this run (0 = no cap; 'X per day')",
        )
        p.add_argument(
            "--fresh", action="store_true", help="ignore prior results and re-enrich from scratch"
        )

    p_ex = sub.add_parser("extract", help="raw -> extracted (deterministic)")
    p_ex.set_defaults(func=cmd_extract)

    p_en = sub.add_parser("enrich", help="extracted -> parsed (LLM; resumes from prior run)")
    add_enrich_opts(p_en)
    p_en.set_defaults(func=cmd_enrich)

    p_sc = sub.add_parser("schedule", help="parsed -> scheduled")
    p_sc.set_defaults(func=cmd_schedule)

    p_bd = sub.add_parser("build-data", help="extract + enrich + schedule")
    add_enrich_opts(p_bd)
    p_bd.set_defaults(func=cmd_build_data)

    p_q = sub.add_parser("quality", help="print the quality scorecard")
    p_q.set_defaults(func=cmd_quality)

    p_in = sub.add_parser("inspect", help="run one recipe through every stage")
    p_in.add_argument("recipe", help="recipe id (or unique substring)")
    add_provider(p_in)
    p_in.set_defaults(func=cmd_inspect)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
