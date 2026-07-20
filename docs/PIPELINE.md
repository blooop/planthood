# Recipe Pipeline

The pipeline turns raw Planthood product pages into scheduled, Gantt-ready recipes in four
independent, typed stages. Each stage reads one artifact and writes the next; each validates
its output against a pydantic contract in [`planthood/models.py`](../planthood/models.py).

```
scrape    HTML          -> data/raw_recipes.json          (RawRecipe)
extract   raw method     -> data/recipes_extracted.json    (ExtractedRecipe)   deterministic, no LLM
enrich    grounded steps -> data/recipes_parsed.json       (ParsedRecipe)      LLM
schedule  timeline       -> data/recipes_with_schedule.json (ScheduledRecipe)  consumed by the site
```

## Stages

| Stage | Module | What it does |
|-------|--------|--------------|
| **scrape** | `scraper/scrape.py` | Fetch product pages; extract title, ingredients, method, nutrition. Uses `planthood.text.node_text` so inline spans never fuse into one word. |
| **extract** | `planthood/extract/` | Deterministically clean the method and split it into grounded step fragments. For the ~52% of recipes with explicit `STEP n` markers the split is exact, so the LLM cannot invent or drop steps. Non-cookable products (e.g. snack-bar bundles) are classified and stored with no steps. |
| **enrich** | `planthood/enrich/` + `planthood/llm.py` | For each extracted step, an LLM adds `type`, duration, equipment, temperature, and `requires`/`can_overlap_with` — keyed to the extractor's fixed step ids, with schema-enforced structured output and deterministic fallbacks. |
| **schedule** | `planthood/schedule/` | Forward pass computes each step's `start_min`/`end_min` (`end == start + duration`, never before a prerequisite finishes) plus the critical path and active (hands-on) time. |

## Running it

```bash
# Full run (needs an LLM key for enrich — see below)
pixi run build-data          # scrape -> extract -> enrich -> schedule

# Or stage by stage
pixi run scrape
pixi run extract
pixi run enrich
pixi run schedule

# Inspect a single recipe through every stage
pixi run inspect mushroom-shawarma --provider mock

# Print the quality scorecard (exits non-zero if a threshold is breached)
pixi run quality
```

## LLM provider

Configure via environment (see `.env.example`). The abstraction lives in `planthood/llm.py`.

| `LLM_PROVIDER` | Key | Default model |
|----------------|-----|---------------|
| `anthropic` (default) | `ANTHROPIC_API_KEY` | `claude-haiku-4-5-20251001` |
| `gemini` | `GEMINI_API_KEY` | `gemini-3.5-flash` (best free-tier model; `gemini-2.5-pro` has **no** free tier) |
| `openai` | `OPENAI_API_KEY` | `gpt-4o-mini` |
| `mock` | none | offline deterministic enrichment (for tests / no-key runs) |

> For Gemini use a real **API key** from https://aistudio.google.com/apikey (starts `AIza`),
> not a short-lived OAuth access token.

## Resumable, "X recipes per day" enrichment

There is **no separate cache** — `recipes_parsed.json` is the store. Each recipe records:

- `provenance`: `llm` (genuine model output), `fallback` (deterministic — a candidate for the
  LLM next run), or `none` (non-cookable).
- `source_hash`: a fingerprint of the extracted steps; if a re-scrape changes them, the recipe
  is re-enriched rather than kept stale.

`enrich` resumes from the committed file: recipes already `llm`-enriched for their current text
are reused, and up to `--limit N` of the remaining ones are enriched this run (`--limit 0` = as
many as the quota allows, stopping when a circuit breaker detects the daily quota is spent). So
the daily GitHub Actions run works through the backlog `N` recipes at a time and commits the
result; over several days the whole catalogue becomes real `llm` enrichment. Set the pace with
the `DAILY_ENRICH_LIMIT` repo variable.

## Safety properties

- **Never empty**: a failed/rate-limited/weak model falls back to deterministic enrichment
  (`provenance='fallback'`), so a cookable recipe always has grounded, scheduled steps.
- **Merge-safe saves** (`planthood/io.py`): an empty result never overwrites a good one.
- **Grounding**: extracted step text is a verbatim slice of the source method, so the enriched
  `raw_text` quotes the real recipe.
- **Quality gate** (`planthood/quality/`): coverage, grounding, dependency sanity, and timeline
  realism are measured against thresholds; the golden regression test locks extractor behaviour.
