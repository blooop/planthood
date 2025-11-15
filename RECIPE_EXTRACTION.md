# Recipe Extraction Pipeline

## Overview

This project uses a multi-stage pipeline to extract, parse, and schedule recipe data from Planthood's website:

1. **Scraper** (`scraper/scrape.py`) - Extracts raw recipe data from planthood.co.uk
2. **Parser** (`parser/parse.py`) - Uses Gemini API to structure recipe steps with dependencies
3. **Scheduler** (`scheduler/schedule.py`) - Computes cooking timeline for Gantt chart visualization

## Configuration

### Gemini API Setup

The pipeline uses Google's Gemini API (gemini-1.5-flash) to parse recipe text. To configure:

1. **GitHub Actions Secret**: Add `GEMINI_API_KEY` to your repository secrets
2. **Local Development**: Set `GEMINI_API_KEY` in `.env` file

```bash
# .env
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_api_key_here
GEMINI_MODEL=gemini-1.5-flash  # optional, defaults to gemini-1.5-flash
```

### Alternative LLM Providers

The parser supports multiple providers (configure via `LLM_PROVIDER` environment variable):

- `gemini` (default) - Google Gemini
- `openai` - OpenAI GPT models
- `anthropic` - Anthropic Claude models

## Pipeline Execution

### GitHub Actions (Automated)

The workflow runs weekly on Mondays at 3 AM UTC and on every push to main:

```bash
# Triggered automatically by:
# - Schedule: Mondays at 3 AM UTC
# - Push to main branch
# - Manual workflow dispatch
```

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run the pipeline
python scraper/scrape.py      # Step 1: Scrape raw recipes
python parser/parse.py         # Step 2: Parse with Gemini API
python scheduler/schedule.py   # Step 3: Compute schedules

# Build the site
cd site
npm install
npm run build
```

## Data Flow

```
planthood.co.uk/collections/cooking-instructions
  ↓ (scraper)
data/raw_recipes.json
  ↓ (parser + Gemini API)
data/recipes_parsed.json
  ↓ (scheduler)
data/recipes_with_schedule.json
  ↓ (Next.js build)
site/out/
```

## Limitations

### Scraping Challenges

The Planthood website uses JavaScript to dynamically load content, which presents challenges:

1. **Limited public recipes**: Only a few product pages are publicly accessible
2. **Full recipes behind paywall**: Detailed cooking instructions may require subscription
3. **JavaScript rendering**: Static HTML parsing can't access all dynamically loaded content

### Current Approach

The scraper extracts product handles from embedded JavaScript data and fetches available product pages. The Gemini API then parses whatever text is available to extract structured recipe information.

### Future Improvements

- Use Playwright/Selenium for JavaScript rendering (if needed)
- Explore Planthood API endpoints (if available)
- Manual recipe data entry for testing/demonstration

## Monitoring

Check GitHub Actions logs to monitor pipeline execution:

- **Scraper output**: Number of recipes discovered and extracted
- **Parser output**: LLM provider used and number of steps parsed
- **Scheduler output**: Timeline computation results

All pipeline steps use `continue-on-error: true` to ensure the site builds even if data extraction fails (falling back to existing data).
