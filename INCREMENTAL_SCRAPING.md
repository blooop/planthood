# Incremental Scraping in GitHub Actions

## Overview

The Planthood scraper is designed to run efficiently in GitHub Actions on a weekly schedule. It uses **incremental scraping** to avoid re-processing recipes that have already been extracted.

## How It Works

### 1. **Data Persistence via Git**

All recipe data files are tracked in git and committed back to the repository after each run:

```
data/
├── raw_recipes.json          # All scraped recipes (tracked in git)
├── recipes_parsed.json       # LLM-parsed recipes (tracked in git)
├── recipes_with_schedule.json # Scheduled recipes (tracked in git)
├── recipe_manifest.json      # Tracking metadata (tracked in git)
└── .cache/                   # LLM cache (NOT tracked, regenerated each run)
```

### 2. **Weekly GitHub Actions Workflow**

The workflow (`.github/workflows/build-and-deploy.yml`) runs every Monday at 3 AM UTC:

```yaml
schedule:
  - cron: '0 3 * * 1'  # Every Monday at 3 AM UTC
```

**Workflow steps:**

1. **Checkout** the repository (includes previous data files)
2. **Scrape** recipes:
   - Loads existing `raw_recipes.json`
   - Discovers all recipes from Planthood (237+ recipes)
   - Compares URLs with existing data
   - Only scrapes NEW recipes not in the existing file
   - Merges new + existing recipes
3. **Parse** with LLM:
   - Uses cache to avoid re-parsing unchanged recipes
   - Only parses new or modified recipes
4. **Schedule** recipes:
   - Computes Gantt timelines
5. **Build** static site
6. **Deploy** to GitHub Pages
7. **Commit data** back to repository:
   ```yaml
   - name: Commit updated data (if changed)
     run: |
       git config --local user.email "github-actions[bot]@users.noreply.github.com"
       git config --local user.name "github-actions[bot]"
       git add -A data/
       git diff --quiet && git diff --staged --quiet || \
         (git commit -m "chore: update recipe data [skip ci]" && git push)
   ```

### 3. **Incremental Scraping Benefits**

**First run (cold start):**
- Discovers 237 recipes
- Scrapes all 237 recipes (~30-60 minutes)
- Parses with LLM (~2-3 minutes with caching)
- Commits data files

**Subsequent runs (warm start):**
- Discovers 237+ recipes
- Loads 237 existing recipes from git
- Finds 5 NEW recipes (example)
- Only scrapes 5 new recipes (~2-3 minutes)
- Only parses 5 new recipes with LLM (~10 seconds)
- Commits updated data files

**Cost savings:**
- **Without incremental**: ~$0.10/week (237 recipes × $0.0004/recipe)
- **With incremental**: ~$0.01/week (5 new recipes × $0.0004/recipe)
- **90% cost reduction!**

## Recipe Manifest

The `recipe_manifest.json` file tracks all discovered recipes:

```json
{
  "total_recipes": 237,
  "last_updated": "2025-11-15 12:30:00",
  "recipes": [
    {
      "id": "crispy-tofu-parm",
      "title": "Crispy Tofu 'Parm' Over Creamy Tomato Beans",
      "url": "https://planthood.co.uk/products/crispy-tofu-parm",
      "scraped": true,
      "week_label": "Delivery w/c 27th October 2025"
    },
    ...
  ]
}
```

This helps you:
- See all available recipes
- Track which recipes have been scraped
- Identify when new recipes are added
- Debug scraping issues

## Local Development

When running locally, the same incremental behavior applies:

```bash
# First run - scrapes all recipes
pixi run scrape

# Second run - only scrapes new recipes
pixi run scrape

# View manifest to see what was found
cat data/recipe_manifest.json
```

## Forcing a Full Re-scrape

If you need to re-scrape all recipes (e.g., Planthood changed their HTML structure):

### Option 1: Delete data files locally
```bash
rm data/raw_recipes.json
rm data/recipe_manifest.json
pixi run scrape
```

### Option 2: In GitHub Actions
Delete the data files via git:
```bash
git rm data/raw_recipes.json data/recipe_manifest.json
git commit -m "Force re-scrape"
git push
```

The next scheduled run will start from scratch.

## Monitoring

### Check GitHub Actions logs:
1. Go to **Actions** tab
2. Click on latest "Build and Deploy to GitHub Pages" run
3. Check the "Run scraper" step for output like:
   ```
   Loaded 237 existing recipes

   Recipe summary:
     Total discovered: 242
     Already scraped: 237
     New to scrape: 5

   Scraping 5 new recipes...
   [1/5] Fetching: https://planthood.co.uk/products/new-recipe-1
   ...
   ```

### Check commit history:
Look for commits from `github-actions[bot]`:
```
chore: update recipe data [skip ci]
```

These commits show when new data was added.

## Troubleshooting

### "No recipes found"
- Check if Planthood changed their website structure
- Review scraper logs in GitHub Actions
- The scraper uses Shopify's `products.json` API which should be stable

### "LLM parsing failed"
- Check API key is set in GitHub Secrets
- Check API quota/billing
- Parser has `continue-on-error: true`, so workflow continues even if parsing fails

### "Data not persisting between runs"
- Verify data files are NOT in `.gitignore`
- Check the "Commit updated data" step succeeded in GitHub Actions
- Ensure repository has write permissions for Actions

## Performance Metrics

Based on current implementation:

| Metric | First Run | Subsequent Runs |
|--------|-----------|-----------------|
| Recipes discovered | 237 | 237-250 |
| Recipes scraped | 237 | 0-10 (new only) |
| Scraping time | 30-60 min | 2-5 min |
| LLM parsing time | 2-3 min | 10-30 sec |
| LLM cost | ~$0.10 | ~$0.01 |
| Total workflow time | 35-65 min | 10-15 min |

## Future Enhancements

- [ ] Add recipe version tracking (detect if existing recipes changed)
- [ ] Store scrape timestamps per recipe
- [ ] Add metrics dashboard showing scraping stats
- [ ] Implement partial re-scrape for updated recipes
- [ ] Add webhook trigger for on-demand scraping
