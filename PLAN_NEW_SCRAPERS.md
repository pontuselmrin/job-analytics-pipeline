# Plan: Remaining Sites via Playwright

## Background

The repo now has two scraper tracks:

- `scrapers/` for direct HTTP/API scrapers
- `scrapers_playwright/` for browser-automation scrapers (anti-bot/JS-heavy sites)

Both tracks use the same output contract: `scrape() -> list[dict]` with at least `title` and `url`.

## New Playwright Structure

- `scrapers_playwright/base_pw.py`
  - shared browser runtime
  - headless-first with headful fallback
  - HTML link extraction helpers
  - URL normalization and deduplication
- `scrapers_playwright/scrape_*_pw.py`
  - site-specific Playwright implementations
- `test_playwright_scrapers.py`
  - dedicated runner for Playwright scrapers
- `PLAYWRIGHT_SCRAPERS.md`
  - setup + run documentation

## Environment

Project is now `uv`-managed and Python-pinned:

- `.python-version` -> `3.13`
- `pyproject.toml` + `uv.lock`

Setup and run:

```bash
uv sync
uv run python -m playwright install chromium
uv run python test_playwright_scrapers.py
```

## Implemented Remaining Sites (Playwright)

- European Chemicals Agency [ECHA] -> `scrape_echa_pw.py`
- European Council [Council] -> `scrape_council_pw.py`
- European Court of Auditors [ECA] -> `scrape_eca_pw.py`
- European Fisheries Control Agency [EFCA] -> `scrape_efca_pw.py`
- European Investment Bank [EIB] -> `scrape_eib_pw.py`
- European Stability Mechanism [ESM] -> `scrape_esm_pw.py`
- European Union Intellectual Property Office [EUIPO] -> `scrape_euipo_pw.py`
- The European Union's Judicial Cooperation Unit [EUROJUST] -> `scrape_eurojust_pw.py`
- European Patent Office [EPO] -> `scrape_epo_pw.py`
- International Coffee Organization [ICO] -> `scrape_ico_pw.py`
- International Olive Oil Council [IOOC] -> `scrape_iooc_pw.py`
- Nordic Investment Bank [NIB] -> `scrape_nib_pw.py`

## Pending / Not Implemented

- European Company for the Financing of Railroad Rolling Stock [EUROFIMA]
  - still no source URL in `sites.csv`

## Notes

- Some targets may legitimately return zero vacancies at runtime.
- A scraper is considered successful if execution works and returns structured output.
- `test_scrapers.py` remains unchanged for non-Playwright scrapers.
