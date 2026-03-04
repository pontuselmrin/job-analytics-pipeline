# job-analytics-pipeline

![tests](https://github.com/pontuselmrin/job-analytics-pipeline/actions/workflows/tests.yml/badge.svg)
![lint](https://github.com/pontuselmrin/job-analytics-pipeline/actions/workflows/lint.yml/badge.svg)
![python](https://img.shields.io/badge/python-3.13-blue)
![code style](https://img.shields.io/badge/code%20style-ruff-orange)

## Background
An end-to-end pipeline for job description analysis. Scrapes career pages, stores listings in Postgres, detects and strips boilerplate text, and transforms data through dbt into a star schema for analytics. The end goal is supervised and unsupervised learning on a large set of jobs to surface trends and insights.

You can see the full set of ideas for future functionality via the project's Issues page. The next implementation I plan to tackle is orchestration via Airflow.

## What it does

1. **Scrapes** job listings from career pages using requests and Playwright
2. **Enriches** listings by fetching full job descriptions and PDFs
3. **Stores** data in Postgres via SQLAlchemy ORM
4. **Detects** per-org boilerplate sentences and flags them for removal
5. **Transforms** data through dbt into a star schema (staging -> intermediate -> marts)

## Project structure

```
scrapers/             # requests-based scrapers (one per org)
scrapers_playwright/  # Playwright-based scrapers for JS-heavy sites
enrichment/           # Post-scrape enrichment (full descriptions, PDFs)
db/                   # SQLAlchemy models and Postgres init SQL
dbt_project/          # dbt warehouse (staging, intermediate, marts)
ops/                  # CLI runner and run artifacts
scripts/              # Database backfill and boilerplate detection
tests/                # Unit, integration, and contract tests
```

## Setup

Requires Python 3.13 and Docker.

```bash
docker compose up -d   # start Postgres
uv sync
playwright install     # for Playwright-based scrapers
```

## Database

Docker Compose runs Postgres 16 (`docker-compose.yml`). Schema is defined in `db/init.sql` and the SQLAlchemy ORM layer lives in `db/db.py`.

## Usage

Run scrapers for specific organisations:

```bash
uv run python -m ops.run_orgs --org <orgname1> --org <orgname2>
```

## dbt warehouse

The dbt project (`dbt_project/`) transforms raw Postgres data into a star schema:

- **Staging**: `stg_jobs`, `stg_organizations` — raw table mirrors
- **Intermediate**: `int_jobs_cleaned` — boilerplate removal and description cleaning
- **Marts**: `dim_organizations`, `dim_content_types`, `dim_enrich_statuses`, `fact_job_enrichments`

```bash
cd dbt_project && uv run dbt run -t postgres
```

## Adding a scraper

See `scrapers/scrape_example.py` (requests) or `scrapers_playwright/scrape_example_pw.py` (Playwright) for templates.

Each scraper implements a `scrape()` function that returns a list of job listing dicts.


## License
MIT license
