# GitHub Pages Setup Guide

This guide will help you set up GitHub Actions and GitHub Pages to automatically deploy the Planthood recipe site.

## Prerequisites

1. Push this repository to GitHub at `https://github.com/blooop/planthood`
2. Have an LLM API key (OpenAI, Anthropic, or Google Gemini)

## Step 1: Configure GitHub Secrets

Add the following secrets to your GitHub repository:

1. Go to **Settings** → **Secrets and variables** → **Actions**
2. Click **New repository secret**
3. Add these secrets:

| Secret Name | Description | Required |
|------------|-------------|----------|
| `OPENAI_API_KEY` | Your OpenAI API key (if using OpenAI) | One of the API keys is required |
| `ANTHROPIC_API_KEY` | Your Anthropic API key (if using Claude) | |
| `GEMINI_API_KEY` | Your Google Gemini API key (if using Gemini) | |
| `LLM_PROVIDER` | Provider name: `openai`, `anthropic`, or `gemini` | Optional (defaults to `openai`) |

### Optional Model Configuration

You can also set these to override the default models:

| Secret Name | Default Value | Description |
|------------|---------------|-------------|
| `OPENAI_MODEL` | `gpt-4o-mini` | OpenAI model to use |
| `ANTHROPIC_MODEL` | `claude-3-5-haiku-20241022` | Anthropic model to use |
| `GEMINI_MODEL` | `gemini-1.5-flash` | Gemini model to use |

## Step 2: Enable GitHub Pages

1. Go to **Settings** → **Pages**
2. Under **Source**, select **GitHub Actions**
3. Click **Save**

![GitHub Pages Source Setting](https://docs.github.com/assets/cb-47267/mw-1440/images/help/pages/publishing-source-drop-down.webp)

## Step 3: Trigger the Workflow

The workflow will run automatically in these cases:
- **Weekly**: Every Monday at 3 AM UTC
- **On push to main**: Whenever you push to the main branch
- **Manual trigger**: You can manually trigger it anytime

### To manually trigger the workflow:

1. Go to **Actions** tab
2. Click on **Build and Deploy to GitHub Pages**
3. Click **Run workflow**
4. Select the branch (usually `main`)
5. Click **Run workflow**

## Step 4: Verify Deployment

After the workflow runs successfully:

1. Check the **Actions** tab to see the workflow status
2. Once complete, your site will be available at:
   - **https://blooop.github.io/planthood/**

## Workflow Details

The GitHub Actions workflow does the following:

1. **Scrapes** recipes from planthood.co.uk
2. **Parses** recipes using LLM to extract structured steps
3. **Schedules** recipes to compute Gantt chart timelines
4. **Builds** the static Next.js site
5. **Deploys** to GitHub Pages
6. **Commits** updated recipe data back to the repository (if changed)

### Workflow Schedule

- Runs every Monday at 3 AM UTC
- Automatically re-scrapes and rebuilds if recipes change
- Uses smart caching to avoid re-parsing unchanged recipes

## Troubleshooting

### Workflow fails with "Authentication failed"

Make sure you have the correct permissions in `.github/workflows/build-and-deploy.yml`:
```yaml
permissions:
  contents: write
  pages: write
  id-token: write
```

### Site shows 404 or broken links

1. Check that `basePath` in `site/next.config.js` matches your repo name:
   ```javascript
   basePath: '/planthood',
   ```
2. If using a custom domain, remove the `basePath` line

### LLM parsing fails

1. Verify your API key is set correctly in GitHub Secrets
2. Check that you have sufficient API credits/quota
3. Try switching to a different provider:
   - Set `LLM_PROVIDER` secret to `gemini` (free tier available)

### Site not updating

1. Check the **Actions** tab for error logs
2. Verify the workflow completed successfully
3. Clear your browser cache
4. Wait a few minutes for GitHub Pages to propagate changes

### Scraper fails

The scraper step has `continue-on-error: true`, so the workflow will continue even if scraping fails. Check the workflow logs to see specific errors.

## Cost Estimation

With smart caching and approximately 10 new/changed recipes per week:

| Provider | Weekly Cost |
|----------|-------------|
| OpenAI (gpt-4o-mini) | ~$0.01 |
| Anthropic (Claude 3.5 Haiku) | ~$0.04 |
| Google Gemini (1.5 Flash) | ~$0.005 or free |

## Custom Domain (Optional)

To use a custom domain:

1. Add a `CNAME` file to the `site/public` directory with your domain
2. Comment out the `basePath` line in `site/next.config.js`
3. Configure your DNS provider to point to GitHub Pages

## Local Development

To test locally before pushing:

```bash
# Install dependencies
pixi install
cd site && npm install && cd ..

# Set up environment
cp .env.example .env
# Edit .env and add your API key

# Run the full pipeline
pixi run scrape
pixi run parse
pixi run schedule
pixi run dev-site

# Or run all data steps at once
pixi run build-data
```

## Updating the Site

The site automatically updates weekly, but you can also:

1. **Manual update**: Trigger the workflow manually (see Step 3)
2. **Push changes**: Any push to `main` will trigger a rebuild
3. **Update schedule**: Edit the cron expression in `.github/workflows/build-and-deploy.yml`

## Need Help?

- Check workflow logs in the **Actions** tab
- Review [PLANTHOOD_SITE_README.md](./PLANTHOOD_SITE_README.md) for detailed documentation
- Open an issue on GitHub if you encounter problems
