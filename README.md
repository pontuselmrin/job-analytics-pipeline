# Job Analytics Pipeline

![tests](https://github.com/pontuselmrin/job-analytics-pipeline/actions/workflows/tests.yml/badge.svg)
![lint](https://github.com/pontuselmrin/job-analytics-pipeline/actions/workflows/lint.yml/badge.svg)
![python](https://img.shields.io/badge/python-3.13-blue)
![code style](https://img.shields.io/badge/code%20style-ruff-orange)

## Background
This is the data-collection part of an end-to-end pipeline for job description analysis. I plan on extending this as a microservice and routing it through a postgres database to run spark jobs on the job descriptions. The end goal is to do supervised and unsupervised learning on a large set of jobs to get some insights into trends, ideas and potential industries of interest.

It's currently in a MVP state and is fully functional, but it only outputs JSON files for each organization. You can see the full set of ideas via the project's Issues page. The next implementation I plan to tackle is orchestration via Airflow.

## What it does

1. **Scrapes** job listings from career pages using requests and Playwright
2. **Enriches** listings by fetching full job descriptions and PDFs
3. **Outputs** structured JSON artifacts per run

## Project structure

```
scrapers/             # requests-based scrapers (one per org)
scrapers_playwright/  # Playwright-based scrapers for JS-heavy sites
enrichment/           # Post-scrape enrichment (full descriptions, PDFs)
ops/                  # CLI runner and run artifacts
scripts/              # Publish script for public repo
tests/                # Unit, integration, and contract tests
```

## Setup

Requires Python 3.13.

```bash
uv sync
playwright install  # for Playwright-based scrapers
```

## Usage

Run scrapers for specific organisations:

```bash
uv run python -m ops.run_orgs --org <orgname1> --org <orgname2>
```

## Adding a scraper

See `scrapers/scrape_example.py` (requests) or `scrapers_playwright/scrape_example_pw.py` (Playwright) for templates.

Each scraper implements a `scrape()` function that returns a list of job listing dicts.


## License
MIT license
