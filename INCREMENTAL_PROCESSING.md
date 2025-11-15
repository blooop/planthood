# Incremental Recipe Processing

This document explains the incremental recipe processing system, which processes one recipe at a time to avoid rate limits and make debugging easier.

## Overview

Instead of processing all 237 recipes at once (or all 21 upcoming recipes), this system processes **one recipe at a time** in a queue-based system. This is ideal for:

1. **GitHub Actions scheduled runs** - Process one recipe per run to stay within API rate limits
2. **Debugging** - Test LLM parsing on individual recipes
3. **Cost control** - Spread LLM API costs over time
4. **Progressive updates** - Update the site incrementally as recipes are processed

## Quick Start

### 1. Find Upcoming Recipes

First, identify which recipes are currently being delivered:

```bash
pixi run find-upcoming
```

This creates `data/upcoming_recipes.json` with the current week's recipes (typically ~21 recipes).

### 2. Process One Recipe

Process the next unprocessed recipe from the queue:

```bash
pixi run process-next-recipe
```

Output:
```
Next Recipe: Tandoori Tofu Naan Wraps
Progress: Processed: 0/21, Remaining: 21

Parsing with LLM...
Parsed 10 steps

Generating Gantt chart schedule...
Scheduled: 48 minutes total

Successfully processed recipe!
   Progress: 1/21 recipes
```

### 3. Repeat Until Done

Run the command again to process the next recipe:

```bash
pixi run process-next-recipe  # Processes recipe #2
pixi run process-next-recipe  # Processes recipe #3
# ... etc
```

When all recipes are processed:
```
All recipes processed! (21 total)
   Run 'pixi run find-upcoming' to refresh the queue
```

### 4. Build and Deploy

After processing all (or some) recipes, build the site:

```bash
pixi run build-site    # Build static site
pixi run dev-site      # Test locally
```

## How It Works

### Files

```
data/
├── upcoming_recipes.json       # Queue of recipes to process (from find-upcoming)
├── processing_status.json      # Tracks which recipes have been processed
├── recipes_parsed.json         # Accumulated parsed recipes
└── recipes_with_schedule.json  # Accumulated scheduled recipes
```

### Processing Status Metadata

`data/processing_status.json` tracks the state of each recipe:

```json
{
  "last_updated": "2025-11-15T10:30:00",
  "total_processed": 2,
  "recipes": {
    "tandoori-tofu": {
      "processed": true,
      "timestamp": "2025-11-15T10:25:00",
      "steps_extracted": 10,
      "total_time_min": 48,
      "error": null
    },
    "kimchi-macaroni": {
      "processed": true,
      "timestamp": "2025-11-15T10:30:00",
      "steps_extracted": 17,
      "total_time_min": 27,
      "error": null
    }
  }
}
```

### Workflow

1. **find_upcoming_recipes.py**
   - Queries Planthood's recent menu collections
   - Finds ~21 current recipes
   - Matches to scraped data
   - Saves to `upcoming_recipes.json`

2. **process_next_recipe.py**
   - Loads `upcoming_recipes.json`
   - Loads `processing_status.json`
   - Finds first unprocessed recipe
   - Parses with LLM (using cache if available)
   - Generates Gantt chart schedule
   - Merges with existing processed recipes
   - Updates processing status
   - Saves everything

3. **Repeat** until all recipes processed

## GitHub Actions Integration

### Option 1: Process One Recipe Per Day

Add to `.github/workflows/`:

```yaml
name: Process Next Recipe

on:
  schedule:
    - cron: '0 2 * * *'  # Daily at 2 AM UTC
  workflow_dispatch:     # Manual trigger

jobs:
  process-recipe:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Process next recipe
        env:
          LLM_PROVIDER: gemini
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
        run: python process_next_recipe.py

      - name: Build site
        run: |
          cd site
          npm ci
          npm run build

      - name: Deploy to GitHub Pages
        uses: actions/deploy-pages@v4
        with:
          artifact_name: github-pages
          path: site/out

      - name: Commit updated data
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add data/
          git diff --quiet && git diff --staged --quiet || \
            (git commit -m "chore: process next recipe [skip ci]" && git push)
```

### Option 2: Process Multiple Recipes Per Week

```yaml
on:
  schedule:
    - cron: '0 2 * * 1,3,5'  # Mon, Wed, Fri at 2 AM UTC
```

This processes 3 recipes per week, taking ~1 week to process all 21 recipes.

## Pixi Tasks

```toml
# Find which recipes are upcoming/current
find-upcoming = "python find_upcoming_recipes.py"

# Process the next recipe in the queue
process-next-recipe = "python process_next_recipe.py"

# Process next recipe AND rebuild site
process-and-deploy = { depends-on = ["process-next-recipe", "build-site"] }
```

Usage:
```bash
pixi run find-upcoming          # Refresh the queue
pixi run process-next-recipe    # Process one recipe
pixi run process-and-deploy     # Process + build site
```

## Cost Analysis

### Traditional Approach (All at Once)
- Process all 21 recipes in one run
- Total cost: 21 × $0.0004 = ~$0.01
- Time: ~5 minutes
- Risk: Rate limit errors

### Incremental Approach (One at a Time)
- Process 1 recipe per day for 21 days
- Cost per day: ~$0.0004
- Total cost over 21 days: ~$0.01 (same)
- Time per run: ~10-30 seconds
- Risk: No rate limit issues

**Advantages:**
- **No rate limits**: Spread requests over time
- **Easier debugging**: Test one recipe at a time
- **Progressive updates**: Site updates daily with new recipes
- **Lower peak costs**: Spread API costs over time

## Manual Testing

### Test on a Single Recipe

```bash
# Find upcoming recipes
pixi run find-upcoming

# Process just one
pixi run process-next-recipe

# Check the results
cat data/processing_status.json
cat data/recipes_parsed.json | python -m json.tool | tail -50
```

### Process Multiple Recipes

```bash
# Process 5 recipes in a loop
for i in {1..5}; do
  pixi run process-next-recipe
  sleep 2  # Brief pause between runs
done
```

### Reset Processing State

To start over:

```bash
rm data/processing_status.json
# Next run will start from the beginning
```

### Skip Failed Recipes

If a recipe fails to parse, it's marked as processed with an error. To retry:

1. Edit `data/processing_status.json`
2. Set `"processed": false` for the recipe
3. Run `pixi run process-next-recipe` again

## Debugging

### Check Processing Status

```bash
cat data/processing_status.json | python -c "
import json, sys
data = json.load(sys.stdin)
print(f'Total processed: {data.get(\"total_processed\", 0)}')
for rid, status in data.get('recipes', {}).items():
    if status.get('error'):
        print(f'  [ERROR] {rid}: {status[\"error\"]}')
    else:
        print(f'  [OK] {rid}: {status.get(\"steps_extracted\", 0)} steps')
"
```

### View Queue

```bash
cat data/upcoming_recipes.json | python -c "
import json, sys
recipes = json.load(sys.stdin)
for r in recipes[:5]:
    print(f'- {r[\"id\"]}: {r[\"title\"][:60]}...')
"
```

### Test LLM Without Processing

Use the test script to try individual recipes:

```bash
pixi run python test_single_recipe.py RECIPE-ID
```

## Error Handling

The script handles errors gracefully:

- **No method text**: Skips recipe, marks as processed with error
- **LLM parsing fails**: Marks as processed with error, continues
- **Scheduling fails**: Marks with error, continues
- **All recipes processed**: Returns success message

Errors are tracked in `processing_status.json`:

```json
{
  "recipe-id": {
    "processed": true,
    "error": "No steps extracted",
    "steps_extracted": 0
  }
}
```

## Refreshing the Queue

When new recipes are released:

```bash
# Get the latest recipes
pixi run find-upcoming

# This updates upcoming_recipes.json with new recipes
# process_next_recipe.py will automatically pick up the new ones
```

## Integration with Main Workflow

You can combine incremental processing with full processing:

1. **Weekly scrape**: Get all recipes
2. **Daily incremental**: Process 1-2 recipes per day
3. **Weekly full parse**: Process any missed recipes in batch

This gives you both progressive updates AND a safety net.

## Monitoring

Track progress via git commits:

```bash
git log --all --grep="process next recipe" --oneline
```

Each commit shows one recipe processed, making it easy to track progress over time.
