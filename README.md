# Planthood Recipe Site Generator

An automated static website generator for Planthood recipes with interactive Gantt chart visualizations. This project scrapes recipes weekly, parses them using LLM into structured dependency-aware steps, and generates a beautiful static site hosted on GitHub Pages.

## Features

### Recipe Site Generator
* **Interactive Gantt Charts**: Visual cooking timelines showing dependencies and parallel tasks
* **LLM-Powered Parsing**: Converts free-form recipe text into structured, timed steps
* **Fully Static**: Pure HTML/CSS/JS output, no runtime server required
* **Automated Weekly Updates**: GitHub Actions scrapes and rebuilds weekly
* **Provider-Agnostic**: Supports OpenAI, Anthropic Claude, Google Gemini
* **Smart Caching**: Avoids re-parsing unchanged recipes

### Development Tools
* Python development with [pixi](https://pixi.sh)
* pylint & ruff (formatting and linting)
* pytest for testing
* GitHub Actions CI/CD
* Automated deployments to GitHub Pages

## Continuous Integration Status

[![Ci](https://github.com/blooop/planthood/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/blooop/planthood/actions/workflows/ci.yml?query=branch%3Amain)
[![Codecov](https://codecov.io/gh/blooop/planthood/branch/main/graph/badge.svg?token=Y212GW1PG6)](https://codecov.io/gh/blooop/planthood)
[![GitHub issues](https://img.shields.io/github/issues/blooop/planthood.svg)](https://GitHub.com/blooop/planthood/issues/)
[![GitHub pull-requests merged](https://badgen.net/github/merged-prs/blooop/planthood)](https://github.com/blooop/planthood/pulls?q=is%3Amerged)
[![GitHub release](https://img.shields.io/github/release/blooop/planthood.svg)](https://GitHub.com/blooop/planthood/releases/)
[![License](https://img.shields.io/github/license/blooop/planthood)](https://opensource.org/license/mit/)
[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue)](https://www.python.org/downloads/)
[![Pixi Badge](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/prefix-dev/pixi/main/assets/badge/v0.json)](https://pixi.sh)

## Quick Start

### For GitHub Pages Deployment

See **[GITHUB_PAGES_SETUP.md](./GITHUB_PAGES_SETUP.md)** for complete GitHub Pages setup instructions.

Quick steps:
1. Configure GitHub Secrets (LLM API key)
2. Enable GitHub Pages with source: GitHub Actions
3. Push to main or manually trigger the workflow

Your site will be live at: **https://blooop.github.io/planthood/**

### For Local Development

```bash
# Install dependencies
pixi install

# Set up environment
cp .env.example .env
# Edit .env and add your LLM API key

# Run the pipeline
pixi run scrape      # Scrape recipes from planthood.co.uk
pixi run parse       # Parse with LLM into structured steps
pixi run schedule    # Compute Gantt timelines
pixi run dev-site    # Start development server

# Or run all data steps at once
pixi run build-data
```

## Documentation

- **[GITHUB_PAGES_SETUP.md](./GITHUB_PAGES_SETUP.md)** - Complete GitHub Pages deployment guide
- **[PLANTHOOD_SITE_README.md](./PLANTHOOD_SITE_README.md)** - Detailed site generator documentation
- **[SETUP.md](./SETUP.md)** - Development setup instructions
- **[DEPLOYMENT.md](./DEPLOYMENT.md)** - Advanced deployment options

## Architecture

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

# Install (Legacy/Template Info)

There are two methods of using this project.  

1. Use github to use this project as a template
2. Clone the project and run, `scripts/update_from_template.sh` and then run the `scripts/rename_project.sh` to rename the project.

If you want to use docker you may want to run the `scripts/setup_host.sh` script.  It will set up docker and nvidia-docker (assuming you are on ubuntu22.04).

If you are using pixi, look at the available tasks in pyproject.toml  If you are new to pixi follow the instructions on the pixi [website](https://prefix.dev/)

# GitHub Setup

## Planthood Site Workflow

The main workflow is `build-and-deploy.yml` which:
- Scrapes recipes from planthood.co.uk weekly
- Parses them using LLM (OpenAI/Anthropic/Gemini)
- Generates Gantt chart timelines
- Builds and deploys the static site to GitHub Pages

**See [GITHUB_PAGES_SETUP.md](./GITHUB_PAGES_SETUP.md) for complete setup instructions.**

## Legacy CI Workflows

There are also github workflows for CI, codecov and automated pypi publishing in `ci.yml` and `publish.yml`.

- `ci.yml` uses pixi tasks to set up the environment matrix and run the various CI tasks. To set up codecov on github, you need to get a `CODECOV_TOKEN` and add it to your actions secrets.
- `publish.yml` uses [pypy-auto-publish](https://github.com/marketplace/actions/python-auto-release-pypi-github) to automatically publish to pypi if the package version number changes. You need to add a `PYPI_API_TOKEN` to your github secrets to enable this.     


# Usage

## Planthood Site Generator Tasks

Use pixi to run the site generator pipeline:

```bash
# Run individual steps
pixi run scrape      # Scrape recipes from planthood.co.uk
pixi run parse       # Parse recipes with LLM
pixi run schedule    # Compute Gantt timelines
pixi run dev-site    # Start development server

# Run complete pipeline
pixi run build-data       # Scrape + parse + schedule
pixi run build-planthood  # Complete build (data + site)

# Setup and build
pixi run setup-site  # Install Node.js dependencies
pixi run build-site  # Build static site for production
```

## Development Tasks

The preferred way is to use pixi to manage your environment and dependencies:

```bash
cd project

pixi run ci          # Run CI tasks (format, lint, test)
pixi run format      # Format code with ruff
pixi run lint        # Lint code
pixi run test        # Run tests
```

If you have dependencies or configuration that cannot be managed by pixi, you can use alternative tools:

- [rockerc](https://github.com/blooop/rockerc): A command-line tool for dynamically creating docker containers with access to host resources such as GPU and 
- [rockervsc](https://github.com/blooop/rockervsc): A Visual Studio Code extension that integrates rockerc functionality into [vscode remote containers](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers).

These tools help you create isolated environments with specific dependencies, ensuring consistent setups across different machines.

```bash
cd project_name

rockerc # build and launch container with dependencies set up
# OR
rockervsc # build container, launch and attach vscode to that container.

#once you are inside the container you can use the pixi workflows.
pixi run ci
```

## Legacy

If you don't want to install rocker on your system but want to use vscode, you can run the `scripts/launch_vscode.sh` script to build and connect to a docker container. It will install rocker in a venv.  The docker container is dynamically generated using [rocker](https://github.com/osrf/rocker) and the configuration in `rockerc.yaml`. 

## Troubleshooting

The main pixi tasks are related to CI.  Github actions runs the pixi task "ci".  The CI is mostly likely to fail from a lockfile mismatch.  Use `pixi run fix` to fix any lockfile related problems. 

## vscode tasks

There are two core tasks.  

1. set \<cfg\> from active file

    This sets \<cfg\> to the currently opened file in the editor

2. run \<cfg\>

    This runs python with the file set in \<cfg\>
