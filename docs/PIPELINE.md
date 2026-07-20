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
| `gemini` | `GEMINI_API_KEY` | `gemini-2.5-flash` |
| `openai` | `OPENAI_API_KEY` | `gpt-4o-mini` |
| `mock` | none | offline deterministic enrichment (for tests / no-key runs) |

Enrichment results are cached under `data/.cache/enrich` keyed on the recipe, prompt version,
and model, so re-runs only call the LLM for changed recipes. Pass `--no-cache` to bypass.

## Safety properties

- **Merge-safe saves** (`planthood/io.py`): a failed or empty enrichment never overwrites a
  previously-good parse. Full clean rebuilds use `--replace`.
- **Grounding**: extracted step text is a verbatim slice of the source method, so the enriched
  `raw_text` quotes the real recipe.
- **Quality gate** (`planthood/quality/`): coverage, grounding, dependency sanity, and timeline
  realism are measured against thresholds; the golden regression test locks extractor behaviour.
