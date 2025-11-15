# Deployment Guide

Quick reference for deploying the Planthood Recipe Site to GitHub Pages.

## Prerequisites Checklist

Before deploying, ensure you have:

- [ ] GitHub repository with the code
- [ ] LLM API key (OpenAI, Anthropic, or Gemini)
- [ ] GitHub Actions enabled in your repository
- [ ] GitHub Pages enabled

## Step 1: Configure GitHub Secrets

Go to your repository → **Settings** → **Secrets and variables** → **Actions**

Add these secrets:

| Secret Name | Value | Required |
|------------|-------|----------|
| `LLM_PROVIDER` | `openai`, `anthropic`, or `gemini` | Yes |
| `OPENAI_API_KEY` | Your OpenAI API key | If using OpenAI |
| `ANTHROPIC_API_KEY` | Your Anthropic API key | If using Claude |
| `GEMINI_API_KEY` | Your Gemini API key | If using Gemini |

Optional model overrides:
- `OPENAI_MODEL` (default: `gpt-4o-mini`)
- `ANTHROPIC_MODEL` (default: `claude-3-5-haiku-20241022`)
- `GEMINI_MODEL` (default: `gemini-1.5-flash`)

## Step 2: Enable GitHub Pages

1. Go to **Settings** → **Pages**
2. Under "Source", select **GitHub Actions**
3. Click **Save**

Your site will be available at: `https://<username>.github.io/<repo-name>/`

## Step 3: Trigger Initial Build

### Option A: Merge to Main

```bash
git checkout main
git merge <feature-branch>
git push origin main
```

The workflow will automatically run.

### Option B: Manual Trigger

1. Go to **Actions** tab
2. Click "Build and Deploy to GitHub Pages"
3. Click **Run workflow**
4. Select branch: `main`
5. Click **Run workflow**

## Step 4: Monitor Build

1. Go to **Actions** tab
2. Click the running workflow
3. Watch each step complete:
   - Checkout repository
   - Set up Python & Node.js
   - Install dependencies
   - Run scraper (may fail if site down)
   - Run parser (may fail without API key)
   - Run scheduler
   - Build Next.js site (must succeed)
   - Deploy to GitHub Pages

**Note**: Some steps have `continue-on-error: true`, so the build will continue even if they fail.

## Step 5: Verify Deployment

Once the workflow completes:

1. Go to **Settings** → **Pages**
2. You'll see: "Your site is live at `https://...`"
3. Click the URL to view your site
4. Check that:
   - Home page loads with recipe cards
   - Recipe detail pages work
   - Gantt charts render correctly
   - Styles are applied

## Troubleshooting

### Build Fails: "npm ci" Error

**Problem**: Package lock file mismatch

**Solution**:
```bash
cd planthood-site/site
rm package-lock.json
npm install
git add package-lock.json
git commit -m "fix: regenerate package-lock.json"
git push
```

### Build Fails: "Module not found" in Next.js

**Problem**: Missing dependencies or TypeScript errors

**Solution**:
```bash
cd planthood-site/site
npm run build
# Fix any errors shown
```

### No Recipes Displayed

**Problem**: Scraper/parser failed, no data generated

**Solution**:
1. Check if `data/recipes_with_schedule.json` has content
2. Run pipeline locally to generate test data:
   ```bash
   cd planthood-site
   python parser/mock_parse.py  # Use mock parser for testing
   python scheduler/schedule.py
   ```
3. Commit the generated data files

### Styles Not Loading

**Problem**: Jekyll processing is interfering

**Solution**: Verify `.nojekyll` file exists in `site/public/`
```bash
ls planthood-site/site/public/.nojekyll
```

### Pages Deployment Fails

**Problem**: GitHub Pages configuration issue

**Solution**:
1. Ensure "Source" is set to **GitHub Actions** (not branch)
2. Check workflow has correct permissions:
   ```yaml
   permissions:
     contents: write
     pages: write
     id-token: write
   ```

## Weekly Automated Updates

The site automatically updates every **Monday at 3 AM UTC** via the cron schedule:

```yaml
schedule:
  - cron: '0 3 * * 1'
```

To change the schedule, edit `.github/workflows/build-and-deploy.yml`:

| Schedule | Cron Expression |
|----------|----------------|
| Daily at midnight | `0 0 * * *` |
| Twice weekly (Mon/Thu) | `0 3 * * 1,4` |
| Monthly (1st of month) | `0 3 1 * *` |

## Cost Monitoring

### OpenAI (gpt-4o-mini)

**Per recipe**: ~1,200 tokens (~$0.0002)

**Weekly cost** (10 new recipes): ~$0.002

**Free tier**: $5 credit = ~25,000 recipes

### Anthropic (claude-3-5-haiku)

**Per recipe**: ~1,200 tokens (~$0.0018)

**Weekly cost** (10 new recipes): ~$0.018

**Free tier**: $5 credit = ~2,777 recipes

### Google Gemini (gemini-1.5-flash)

**Per recipe**: ~1,200 tokens (~$0.00015)

**Weekly cost** (10 new recipes): ~$0.0015

**Free tier**: 1,500 requests/day (plenty for weekly updates)

## Support

For issues:

1. Check **Actions** tab for workflow logs
2. Review this troubleshooting guide
3. Check [README.md](README.md) for detailed documentation
4. Open an issue on GitHub with:
   - Workflow run URL
   - Error messages
   - Steps to reproduce

## Quick Commands

```bash
# Local testing
cd planthood-site
npm run build-data    # Run scraper → parser → scheduler
npm run build-site    # Build Next.js site
cd site && npm run dev  # Preview locally

# Manual deployment trigger (via GitHub CLI)
gh workflow run "Build and Deploy to GitHub Pages"

# View workflow status
gh run list --workflow="Build and Deploy to GitHub Pages"
```

---

**Ready to deploy?** Follow Steps 1-5 above. The entire process takes ~5 minutes.
