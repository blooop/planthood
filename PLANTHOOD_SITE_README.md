# Planthood Recipe Site Generator

An end-to-end static website generator for Planthood recipes with interactive Gantt chart visualizations. Automatically scrapes recipes weekly, parses them using LLM into structured dependency-aware steps, and generates a beautiful static site hosted on GitHub Pages.

## 🌟 Features

- **📊 Interactive Gantt Charts**: Visual cooking timelines showing dependencies and parallel tasks
- **🤖 LLM-Powered Parsing**: Converts free-form recipe text into structured, timed steps
- **⚡ Fully Static**: Pure HTML/CSS/JS output, no runtime server required
- **🔄 Automated Weekly Updates**: GitHub Actions scrapes and rebuilds weekly
- **🎨 Beautiful UI**: Clean, responsive design optimized for tablets and desktops
- **🔌 Provider-Agnostic**: Supports OpenAI, Anthropic Claude, Google Gemini
- **💾 Smart Caching**: Avoids re-parsing unchanged recipes

## 🏗️ Architecture

```
┌─────────────┐
│   Scraper   │  Fetches recipes from planthood.co.uk
└──────┬──────┘
       │ raw_recipes.json
       ▼
┌─────────────┐
│   Parser    │  LLM converts method text → structured steps
└──────┬──────┘
       │ recipes_parsed.json
       ▼
┌─────────────┐
│  Scheduler  │  Computes Gantt timelines from dependencies
└──────┬──────┘
       │ recipes_with_schedule.json
       ▼
┌─────────────┐
│  Next.js    │  Generates static site with Gantt charts
└──────┬──────┘
       │ out/
       ▼
┌─────────────┐
│GitHub Pages │  Hosts static site
└─────────────┘
```

## 📋 Prerequisites

- **Python 3.11+**
- **Node.js 20+**
- **LLM API Key** (one of):
  - OpenAI API key
  - Anthropic API key
  - Google Gemini API key

## 🚀 Quick Start

### 1. Clone and Install

```bash
git clone <your-repo-url>
cd planthood-site

# Install Python dependencies
pip install -r requirements.txt

# Install Node dependencies
cd site
npm install
cd ..
```

### 2. Configure Environment

Copy `.env.example` to `.env` and set your LLM provider:

```bash
cp .env.example .env
```

Edit `.env`:

```env
# Choose provider: openai, anthropic, or gemini
LLM_PROVIDER=openai

# Set API key for your chosen provider
OPENAI_API_KEY=sk-...
# or
ANTHROPIC_API_KEY=sk-ant-...
# or
GEMINI_API_KEY=...
```

### 3. Run the Pipeline

```bash
# Run all steps (scrape → parse → schedule → build)
npm run build

# Or run individually:
npm run scrape      # Scrape recipes
npm run parse       # Parse with LLM
npm run schedule    # Compute timelines
npm run build-site  # Build static site
```

### 4. Preview Locally

```bash
cd site
npm run dev
# Open http://localhost:3000
```

## 📦 Project Structure

```
planthood-site/
├── scraper/
│   └── scrape.py           # Web scraper for Planthood recipes
├── parser/
│   ├── llm_providers.py    # LLM provider abstraction
│   └── parse.py            # Recipe method → structured steps
├── scheduler/
│   └── schedule.py         # Dependency resolution & timeline computation
├── site/                   # Next.js static site
│   ├── app/
│   │   ├── page.tsx        # Home page (recipe listing)
│   │   └── recipe/[id]/
│   │       └── page.tsx    # Recipe detail with Gantt chart
│   ├── components/
│   │   ├── GanttChart.tsx  # Interactive Gantt visualization
│   │   └── RecipeCard.tsx  # Recipe preview card
│   └── lib/
│       ├── types.ts        # TypeScript types
│       └── data.ts         # Data loading utilities
├── data/                   # Generated data files
│   ├── raw_recipes.json    # Scraped recipes
│   ├── recipes_parsed.json # LLM-parsed recipes
│   └── recipes_with_schedule.json  # Final scheduled data
├── .github/workflows/
│   └── build-and-deploy.yml # CI/CD pipeline
├── requirements.txt        # Python dependencies
├── package.json            # Project scripts
└── .env.example            # Environment variables template
```

## 🔧 Configuration

### LLM Provider Configuration

Set these in `.env` or as environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `LLM_PROVIDER` | Provider name: `openai`, `anthropic`, or `gemini` | `openai` |
| `OPENAI_API_KEY` | OpenAI API key | - |
| `ANTHROPIC_API_KEY` | Anthropic API key | - |
| `GEMINI_API_KEY` | Google Gemini API key | - |
| `OPENAI_MODEL` | OpenAI model to use | `gpt-4o-mini` |
| `ANTHROPIC_MODEL` | Anthropic model to use | `claude-3-5-haiku-20241022` |
| `GEMINI_MODEL` | Gemini model to use | `gemini-1.5-flash` |

### Scraper Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `USER_AGENT` | User agent for HTTP requests | Mozilla/5.0... |
| `REQUEST_DELAY` | Delay between requests (seconds) | `1.0` |

### Parser Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `CACHE_DIR` | Cache directory for parsed recipes | `data/.cache` |
| `SKIP_CACHE` | Skip cache and re-parse all | `false` |
| `MAX_RETRIES` | Max retries for LLM calls | `3` |

## 🤖 LLM Usage & Cost Estimation

### Token Usage per Recipe

Approximate token usage with a typical Planthood recipe:

- **Input**: ~800-1200 tokens (ingredients + method text)
- **Output**: ~400-600 tokens (structured steps JSON)
- **Total**: ~1200-1800 tokens per recipe

### Weekly Cost Estimates

Assuming ~10 new/changed recipes per week:

| Provider | Model | Cost per 1M tokens | Weekly Cost |
|----------|-------|-------------------|-------------|
| OpenAI | gpt-4o-mini | $0.15 (in) / $0.60 (out) | ~$0.01 |
| Anthropic | Claude 3.5 Haiku | $1.00 (in) / $5.00 (out) | ~$0.04 |
| Google | Gemini 1.5 Flash | $0.075 (in) / $0.30 (out) | ~$0.005 |

**Note**: With caching, unchanged recipes are not re-parsed, so weekly costs should be minimal.

### Free Tier Options

- **OpenAI**: $5 free credits for new accounts
- **Google Gemini**: Generous free tier with 1500 requests/day
- **Anthropic**: $5 free credits for new accounts

## 📅 GitHub Actions Workflow

The workflow runs automatically:

- **Weekly**: Every Monday at 3 AM UTC
- **Manual**: Via "Run workflow" button in GitHub Actions
- **On Push**: To `main` branch (for testing)

### Setup GitHub Secrets

Add these secrets in **Settings → Secrets and variables → Actions**:

1. `LLM_PROVIDER` (optional, defaults to `openai`)
2. `OPENAI_API_KEY` (if using OpenAI)
3. `ANTHROPIC_API_KEY` (if using Anthropic)
4. `GEMINI_API_KEY` (if using Gemini)

### Enable GitHub Pages

1. Go to **Settings → Pages**
2. Source: **GitHub Actions**
3. Save

The workflow will automatically deploy to your GitHub Pages URL.

## 🎨 Gantt Chart Features

The interactive Gantt chart visualization includes:

- **Color-coded steps**:
  - 🔵 Blue = Prep
  - 🟠 Orange = Cooking
  - 🟢 Green = Finishing
- **Click any step** to see:
  - Full instructions
  - Equipment needed
  - Temperature settings
  - Dependencies
  - Overlap opportunities
- **Toggle layouts**: Switch between horizontal and vertical views
- **Bold, readable text**: Optimized for 10" tablets and up

## 🧪 Development

### Run Scraper Only

```bash
python scraper/scrape.py
```

### Run Parser Only

```bash
python parser/parse.py
```

### Run Scheduler Only

```bash
python scheduler/schedule.py
```

### Development Mode (Site)

```bash
cd site
npm run dev
```

### Disable LLM Parsing (Offline Mode)

Set `SKIP_CACHE=true` and the parser will skip recipes it can't parse without an LLM.

## 🐛 Troubleshooting

### "No recipes available"

1. Check `data/recipes_with_schedule.json` exists and has content
2. Run the full pipeline: `npm run build-data`
3. Check scraper output for errors

### LLM parsing fails

1. Verify API key is set correctly in `.env`
2. Check provider is available (API limits, billing)
3. Try alternative provider:
   ```bash
   LLM_PROVIDER=gemini npm run parse
   ```

### GitHub Actions failing

1. Check **Actions** tab for error logs
2. Verify secrets are set correctly
3. Ensure GitHub Pages is enabled
4. Check LLM API quotas

### Site not updating

1. Verify workflow ran successfully in **Actions** tab
2. Check GitHub Pages deployment status
3. Clear browser cache
4. Try manual workflow trigger

## 📊 Data Format

### Raw Recipe (from scraper)

```json
{
  "id": "super-green-orzo",
  "title": "Super Green Orzo",
  "source_url": "https://planthood.co.uk/products/super-green-orzo",
  "week_label": "Delivery w/c 27th October 2025",
  "category": "Nourish",
  "ingredients": ["200g orzo pasta", "..."],
  "method": "Preheat your oven to 200°C...",
  "nutrition": { "calories": 559, "protein_g": 21.3 }
}
```

### Parsed Recipe (after LLM)

```json
{
  "steps": [
    {
      "id": "step-1",
      "raw_text": "Preheat your oven to 200°C...",
      "label": "Preheat oven",
      "type": "prep",
      "estimated_duration_minutes": 5,
      "requires": [],
      "can_overlap_with": ["step-2"],
      "equipment": ["oven"],
      "temperature_c": 200
    }
  ]
}
```

### Scheduled Recipe (after scheduler)

```json
{
  "steps": [
    {
      "id": "step-1",
      "start_min": 0,
      "end_min": 5,
      "duration_min": 5
    }
  ],
  "total_time_min": 45,
  "active_time_min": 20
}
```

## 🔮 Future Enhancements

- [ ] Multi-week menu planning view
- [ ] Shopping list generator
- [ ] Nutritional analysis charts
- [ ] Recipe search and filtering
- [ ] Export timeline as PDF/image
- [ ] Voice-guided cooking mode
- [ ] Ingredient substitution suggestions

## 📄 License

MIT License - see LICENSE file

## 🙏 Acknowledgments

- Recipe data from [Planthood](https://planthood.co.uk)
- Built with [Next.js](https://nextjs.org)
- Deployed on [GitHub Pages](https://pages.github.com)

## 🤝 Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📧 Support

For issues or questions:

1. Check the [Troubleshooting](#-troubleshooting) section
2. Search existing GitHub Issues
3. Open a new issue with:
   - Clear description
   - Steps to reproduce
   - Expected vs actual behavior
   - Environment details (OS, Python/Node versions)

---

**Built with 💚 for easier, clearer cooking**
