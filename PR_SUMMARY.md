# PR Summary: Incremental Recipe Processing & GitHub Pages Deployment

## Overview

This PR adds complete support for automated recipe scraping, LLM-powered parsing, and incremental processing with GitHub Pages deployment.

## What's New

### 1. **Recipe Scraping** ✅
- Scrapes all 237 recipes from Planthood using Shopify API
- Identifies upcoming recipes from current menu collections
- Tracks already-scraped recipes to avoid re-processing
- Creates recipe manifest for easy tracking

**Files:**
- `scraper/scrape.py` - Enhanced with incremental scraping
- `find_upcoming_recipes.py` - Identifies current week's recipes
- `data/raw_recipes.json` - All scraped recipes (237 total)
- `data/recipe_manifest.json` - Tracking metadata
- `data/upcoming_recipes.json` - Current week's queue (21 recipes)

### 2. **LLM-Powered Recipe Parsing** 🤖
- Parses recipe method text into structured steps
- Extracts timing, dependencies, equipment, temperatures
- Supports OpenAI, Anthropic Claude, and Google Gemini
- Smart caching to avoid re-parsing unchanged recipes

**Files:**
- `parser/parse.py` - LLM recipe parser
- `parser/llm_providers.py` - Multi-provider LLM support
- `.env.example` - Configuration template

### 3. **Gantt Chart Generation** 📅
- Converts parsed recipes into timeline schedules
- Handles dependencies and parallel tasks
- Calculates total time and active time

**Files:**
- `scheduler/schedule.py` - Gantt chart scheduler

### 4. **Incremental Processing** 🔄
- Processes ONE recipe at a time (avoids rate limits)
- Tracks processing status with metadata
- Ideal for GitHub Actions scheduled runs
- Progressive site updates as recipes are processed

**New Files:**
- `process_next_recipe.py` - Process next recipe in queue
- `data/processing_status.json` - Tracks which recipes are done
- `INCREMENTAL_PROCESSING.md` - Complete documentation

**Pixi Tasks:**
```bash
pixi run find-upcoming        # Find current week's recipes
pixi run process-next-recipe  # Process 1 recipe from queue
pixi run process-and-deploy   # Process + build site
```

### 5. **GitHub Actions Workflows** ⚙️

#### A. Daily Incremental Processing (NEW)
**`.github/workflows/process-next-recipe.yml`**
- Runs daily at 2 AM UTC
- Processes 1 recipe per day
- Builds & deploys to GitHub Pages
- Commits updated data back to repo

**Triggers:**
- Schedule: Daily at 2 AM UTC
- Push to `main` (for testing)
- Manual via workflow_dispatch

#### B. Weekly Full Scrape & Parse (EXISTING)
**`.github/workflows/build-and-deploy.yml`**
- Runs weekly on Mondays at 3 AM UTC
- Scrapes all recipes
- Parses all new/changed recipes
- Builds & deploys site

### 6. **Testing Scripts** 🧪
- `test_single_recipe.py` - Test LLM parsing on individual recipes
- `parse_upcoming_recipes.py` - Parse all upcoming recipes at once (for local testing)

### 7. **Documentation** 📚
- `GITHUB_PAGES_SETUP.md` - GitHub Pages deployment guide
- `INCREMENTAL_PROCESSING.md` - Incremental processing guide
- `INCREMENTAL_SCRAPING.md` - Scraping documentation
- `PR_SUMMARY.md` - This file!

## Current Status

### Already Processed Locally
✅ **2 recipes processed** (out of 21 upcoming):
1. Tandoori Tofu Naan Wraps - 10 steps, 48 min
2. Creamy Kimchi Macaroni - 17 steps, 27.5 min

### Ready to Deploy
- ✅ Scraped: 237 recipes
- ✅ Parsed: 2 recipes
- ✅ Scheduled: 2 recipes
- ✅ Site builds successfully
- 🔄 Remaining: 19 recipes (will process incrementally)

## Configuration Required

### GitHub Secrets
Add these in **Settings → Secrets and variables → Actions**:

| Secret | Required | Purpose |
|--------|----------|---------|
| `GEMINI_API_KEY` | ✅ Yes | Google Gemini API key for LLM parsing |
| `LLM_PROVIDER` | No | Defaults to `gemini` |
| `GEMINI_MODEL` | No | Defaults to `gemini-2.5-flash` |

**Alternative LLM providers:**
- `OPENAI_API_KEY` - If using OpenAI
- `ANTHROPIC_API_KEY` - If using Anthropic Claude

### GitHub Pages
Enable GitHub Pages:
1. Go to **Settings → Pages**
2. Source: **GitHub Actions**
3. Save

## How to Test This PR

### Option 1: Merge and Wait for Automatic Run
1. Merge this PR to `main`
2. GitHub Actions will automatically trigger (push to main)
3. Watch the workflow in **Actions** tab
4. Site will deploy to `https://blooop.github.io/planthood/`

### Option 2: Manual Trigger
1. Merge PR
2. Go to **Actions** → **Process Next Recipe**
3. Click **Run workflow** → **Run**
4. Monitor the run

### Option 3: Wait for Daily Schedule
1. Merge PR
2. Wait until 2 AM UTC tomorrow
3. Workflow runs automatically
4. Processes next recipe and deploys

## What Happens After Merge

### Immediate (First Run)
1. Workflow triggers on push to `main`
2. Processes recipe #3 (Peanut Butter Curry)
3. Builds static site with 3 recipes
4. Deploys to GitHub Pages
5. Commits `processing_status.json` back to repo

### Daily (Subsequent Runs)
1. Runs at 2 AM UTC every day
2. Processes 1 recipe per day
3. Updates site incrementally
4. After ~19 days, all 21 recipes processed

### Weekly (Full Scrape)
1. Runs Monday 3 AM UTC
2. Re-scrapes all recipes
3. Finds any new recipes
4. Adds to queue for incremental processing

## Files Changed

### New Files (24)
```
.github/workflows/process-next-recipe.yml
GITHUB_PAGES_SETUP.md
INCREMENTAL_PROCESSING.md
INCREMENTAL_SCRAPING.md
PR_SUMMARY.md
data/processing_status.json
data/recipes_parsed.json
data/upcoming_recipes.json
find_upcoming_recipes.py
parse_upcoming_recipes.py
process_next_recipe.py
test_single_recipe.py
```

### Modified Files (5)
```
.gitignore                          # Allow data files to be tracked
pyproject.toml                      # Added pixi tasks
scraper/scrape.py                   # Enhanced scraping
data/recipes_with_schedule.json     # Updated with 2 recipes
pixi.lock                           # Updated dependencies
```

## Testing Checklist

- [ ] GitHub Secrets configured (GEMINI_API_KEY)
- [ ] GitHub Pages enabled (Source: GitHub Actions)
- [ ] Workflow runs successfully
- [ ] Site deploys to `blooop.github.io/planthood`
- [ ] Site displays processed recipes with Gantt charts
- [ ] Data files committed back to repo after run

## Expected Site Content

After the first run, your site will show:
- **3 recipes** with interactive Gantt charts
- Recipe list with filters
- Detailed recipe pages with:
  - Ingredients
  - Nutrition info
  - Step-by-step instructions
  - Visual timeline/Gantt chart

Each day, **1 more recipe** will be added automatically!

## Rollback Plan

If something goes wrong:
```bash
# Disable the workflow
# Go to .github/workflows/process-next-recipe.yml
# Comment out the 'push' and 'schedule' triggers

# Or delete the workflow file
git rm .github/workflows/process-next-recipe.yml
git commit -m "Disable incremental processing"
git push
```

## Questions?

See documentation:
- [GITHUB_PAGES_SETUP.md](GITHUB_PAGES_SETUP.md) - Setup guide
- [INCREMENTAL_PROCESSING.md](INCREMENTAL_PROCESSING.md) - How incremental processing works

## Merging Instructions

```bash
# 1. Review changes
git status

# 2. Stage all changes
git add -A

# 3. Commit
git commit -m "feat: add incremental recipe processing and GitHub Pages deployment

- Add automated scraping for 237 Planthood recipes
- Implement LLM-powered recipe parsing (Gemini/OpenAI/Claude)
- Generate Gantt chart timelines for recipes
- Add incremental processing (1 recipe/day to avoid rate limits)
- Set up GitHub Actions for daily processing and deployment
- Configure GitHub Pages deployment
- Process 2 recipes initially (19 remaining)
"

# 4. Push to remote
git push origin HEAD

# 5. Create PR on GitHub
# Go to https://github.com/blooop/planthood/pulls
# Click "New pull request"
# Select your branch
# Add this PR_SUMMARY.md content to the PR description
```

## Success Metrics

After merge and first workflow run:
- ✅ Workflow completes without errors
- ✅ Site accessible at blooop.github.io/planthood
- ✅ Shows 3 recipes with Gantt charts
- ✅ `processing_status.json` updated in repo
- ✅ Daily runs scheduled

---

**Ready to merge!** 🚀
