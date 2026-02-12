# Plan: Implement Scrapers for Remaining Sites

## Background

The project scrapes job listings from ~100 European/international organization websites. There are currently 44 working scrapers in `scrapers/` that all use shared utilities from `scrapers/base.py`. The file `sites.csv` tracks all sites with columns: `name`, `url`, `scraper`. Sites with a blank `scraper` column still need scrapers implemented.

## Project Structure

- `scrapers/base.py` — Shared utilities: `fetch()`, `normalize_url()`, `extract_links()`, `scrape_workday()`, `scrape_taleo()`
- `scrapers/scrape_*.py` — Individual scrapers, each exporting a `scrape()` function returning `list[dict]` (minimum keys: `title`, `url`)
- `test_scrapers.py` — Test runner that loads all scrapers via `importlib` and calls `scrape()`. Has a `SCRAPER_INFO` dict mapping filename to `(name, url)`.
- `sites.csv` — Master list of all sites with scraper coverage status
- `log_utils.py` — Logging utilities used by test runner

## Scraper Contract

Every scraper must:
1. Live in `scrapers/scrape_<abbrev>.py`
2. Import from `base` (e.g., `from base import fetch, normalize_url, extract_links`)
3. Export a `scrape()` function returning `list[dict]` with at minimum `title` and `url` keys
4. Include `if __name__ == "__main__"` block for standalone testing
5. Be added to `SCRAPER_INFO` in `test_scrapers.py`
6. Have its filename noted in the `scraper` column of `sites.csv`

## Existing Patterns to Reuse

### Pattern A: Simple link extraction
```python
from bs4 import BeautifulSoup
from base import fetch, extract_links

BASE_URL = "https://example.org"
URL = f"{BASE_URL}/careers"

def scrape():
    resp = fetch(URL)
    soup = BeautifulSoup(resp.text, "html.parser")
    return extract_links(soup, "/job/", BASE_URL)
```

### Pattern B: Table parsing
```python
from bs4 import BeautifulSoup
from base import fetch, normalize_url

def scrape():
    resp = fetch(URL)
    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.find("table")
    jobs = []
    for row in table.find("tbody").find_all("tr"):
        cells = row.find_all("td")
        link = cells[0].find("a")
        jobs.append({"title": link.get_text(strip=True), "url": normalize_url(link["href"], BASE_URL)})
    return jobs
```

### Pattern C: Paginated HTML (like scrape_eu_careers.py)
```python
def scrape():
    all_jobs = []
    page = 0
    while True:
        jobs = scrape_page(page)
        if not jobs: break
        all_jobs.extend(jobs)
        page += 1
        time.sleep(0.5)
    return all_jobs
```

### Pattern D: SmartRecruiters API (like scrape_oecd.py)
```python
API_URL = "https://api.smartrecruiters.com/v1/companies/COMPANY/postings"
def scrape():
    # offset-based pagination with limit=100
```

### Pattern E: Workday API (4 existing scrapers)
```python
from base import scrape_workday
def scrape():
    return scrape_workday(BASE_URL, API_URL)
```

## Sites NOT Feasible Without Browser Automation – need special handling

| Site | Reason |
|------|--------|
| European Council [Council] | Cloudflare blocks requests |
| ECA (Court of Auditors) | SharePoint + gestmax iframe, JS-only |
| EFCA (Fisheries Control) | Cloudflare blocks requests |
| European Ombudsman | Full Angular SPA, no SSR |
| ECHA (Chemicals Agency) | PeopleSoft, requires cookie/auth flow |
| EIB (Investment Bank) | PeopleSoft, requires cookie/auth flow |
| EUIPO (IP Office) | CloudFront |
| ESM (Stability Mechanism) | Oracle CX SPA, hash-routed, XHR-only data |
| EUROJUST | empty |
| NIB (Nordic Investment Bank) | React hydration with base64-encoded data |
| IOOC (Olive Oil Council) | Dynamic loading, no initial HTML content |
| ICO (Coffee Org) | no jobs |
| EUROFIMA | no jobs |
| EFTA | Cloudflare |
| UNFCC | JS |


## After Implementation (Completed)

1. Added each new scraper to `SCRAPER_INFO` in `test_scrapers.py` (completed).
2. Updated `sites.csv` scraper column for each implemented scraper (completed).
3. Validation run attempted; use project venv interpreter (`./venv/bin/python`) for runtime tests.
4. Some sites may have 0 current vacancies — this remains acceptable when scraper execution succeeds.
