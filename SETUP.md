# Setup Guide

## Step-by-Step Setup for GitHub Pages Deployment

### 1. Prerequisites

Ensure you have:
- Python 3.11 or higher
- Node.js 20 or higher
- Git
- An LLM API key (OpenAI, Anthropic, or Gemini)

### 2. Repository Setup

1. **Create a new GitHub repository** or push this code to an existing one

2. **Enable GitHub Pages**:
   - Go to repository **Settings → Pages**
   - Under "Source", select **GitHub Actions**
   - Click **Save**

3. **Add GitHub Secrets**:
   - Go to **Settings → Secrets and variables → Actions**
   - Click **New repository secret**
   - Add these secrets:
     - `LLM_PROVIDER`: `openai`, `anthropic`, or `gemini`
     - `OPENAI_API_KEY`: Your OpenAI API key (if using OpenAI)
     - `ANTHROPIC_API_KEY`: Your Anthropic API key (if using Claude)
     - `GEMINI_API_KEY`: Your Google API key (if using Gemini)

### 3. Local Development Setup

```bash
# Clone your repository
git clone <your-repo-url>
cd <repo-name>

# Install Python dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env

# Edit .env and add your API key
# Example for OpenAI:
# LLM_PROVIDER=openai
# OPENAI_API_KEY=sk-...

# Install Node dependencies
cd site
npm install
cd ..
```

### 4. Test the Pipeline Locally

```bash
# Test scraper (will fetch real data from Planthood)
npm run scrape

# Test parser (requires LLM API key)
npm run parse

# Test scheduler
npm run schedule

# Build site
npm run build-site

# Preview locally
cd site
npm run dev
# Open http://localhost:3000
```

### 5. First Deployment

```bash
# Commit and push your changes
git add .
git commit -m "Initial setup of Planthood recipe site"
git push origin main

# The GitHub Action will automatically:
# 1. Run the scraper
# 2. Parse recipes with LLM
# 3. Generate timelines
# 4. Build static site
# 5. Deploy to GitHub Pages
```

### 6. Verify Deployment

1. Go to **Actions** tab in your GitHub repository
2. Watch the "Build and Deploy to GitHub Pages" workflow
3. Once complete (usually 2-5 minutes), visit your GitHub Pages URL:
   - Usually: `https://<username>.github.io/<repo-name>/`

### 7. Enable Weekly Updates

The workflow is already configured to run every Monday at 3 AM UTC. No additional setup needed!

### 8. Manual Trigger

To manually trigger a rebuild:

1. Go to **Actions** tab
2. Click **Build and Deploy to GitHub Pages** workflow
3. Click **Run workflow** button
4. Select branch (usually `main`)
5. Click **Run workflow**

## Troubleshooting

### Issue: Site shows "No recipes available"

**Solution**: The data pipeline needs to run first. Either:
- Wait for the GitHub Action to complete
- Run manually: `npm run build-data`
- Check scraper output for errors

### Issue: LLM parsing fails

**Solution**:
- Verify API key is correct in GitHub Secrets
- Check API provider status and quotas
- Try alternative provider: Change `LLM_PROVIDER` secret

### Issue: GitHub Action fails

**Solution**:
- Check **Actions** tab for detailed error logs
- Verify all secrets are set correctly
- Ensure GitHub Pages is enabled
- Check LLM API quotas

### Issue: Site not updating after changes

**Solution**:
- Commit and push changes: `git push`
- Wait for GitHub Action to complete
- Clear browser cache
- Check deployment in **Actions** tab

## Customization

### Change Site Title

Edit `site/app/layout.tsx`:

```typescript
export const metadata = {
  title: 'Your Custom Title',
  description: 'Your custom description',
};
```

### Change Color Scheme

Edit `site/app/globals.css` and modify CSS variables:

```css
:root {
  --color-primary: #your-color;
  --color-secondary: #your-color;
  /* ... */
}
```

### Add Custom Domain

1. In your repository **Settings → Pages**
2. Under "Custom domain", enter your domain
3. Add DNS records as instructed by GitHub

### Adjust Scraping Frequency

Edit `.github/workflows/build-and-deploy.yml`:

```yaml
schedule:
  # Change cron expression
  # Daily at midnight: '0 0 * * *'
  # Weekly Monday 3am: '0 3 * * 1'
  - cron: '0 3 * * 1'
```

## Next Steps

- Monitor your first automated weekly run
- Check recipe data quality
- Customize colors and branding
- Consider adding more features (see README for ideas)

## Getting Help

- Check [README.md](README.md) for detailed documentation
- Review [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines
- Open an issue on GitHub for bugs or questions
