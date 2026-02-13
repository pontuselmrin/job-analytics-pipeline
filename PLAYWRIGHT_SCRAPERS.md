# Playwright Scrapers

This project now includes browser-driven scrapers under `scrapers_playwright/` for sites that block plain HTTP scraping or require JS rendering.

## Setup

```bash
uv sync
uv run python -m playwright install chromium
```

## Run

```bash
uv run python test_playwright_scrapers.py
```

## Output Contract

Each Playwright scraper exports:

- `scrape() -> list[dict]`
- each dict includes at minimum:
  - `title`
  - `url`

## Implemented Sites

- `scrape_echa_pw.py`
- `scrape_council_pw.py`
- `scrape_eca_pw.py`
- `scrape_efca_pw.py`
- `scrape_eib_pw.py`
- `scrape_esm_pw.py`
- `scrape_euipo_pw.py`
- `scrape_eurojust_pw.py`
- `scrape_epo_pw.py`
- `scrape_ico_pw.py`
- `scrape_iooc_pw.py`
- `scrape_nib_pw.py`
