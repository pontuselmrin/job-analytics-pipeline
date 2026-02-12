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

## Sites to Implement (~26 new scrapers)

### Group 1: Simple HTML scraping (Drupal/WordPress/static)

#### 1. CPVO — `scrape_cpvo.py`
- **URL**: https://cpvo.europa.eu/en/about-us/recruitment#page-search---index
- **Platform**: Drupal
- **Structure**: HTML table with columns (Reserve List, Title, Grade, Initial Date, Valid until). Also has an embedded gestmax iframe.
- **Approach**: Parse the HTML table. If table is empty, try extracting links from the gestmax iframe URL.

#### 2. EU-OSHA — `scrape_eu_osha.py`
- **URL**: https://osha.europa.eu/en/careers
- **Platform**: Drupal
- **Structure**: Accordion/tabbed interface with three views (Open, Evaluation underway, Completed). Uses quicktabs module.
- **Approach**: Parse links from the "Open" tab section. May need to fetch iframe URLs separately.

#### 3. EEAS — `scrape_eeas.py`
- **URL**: https://www.eeas.europa.eu/eeas/vacancies_en?f%5B0%5D=vacancy_site%3AEEAS
- **Platform**: Drupal
- **Structure**: Paginated list, 25 items/page, ~88 pages. Each listing has title (link), location, category, deadline.
- **Approach**: Paginated scraping. Parse article/listing elements. Append `?page=N` for pagination.
- **Note**: CEU (Council of the EU) URL points to same EEAS page — one scraper covers both.

#### 4. EUROFOUND — `scrape_eurofound.py`
- **URL**: https://www.eurofound.europa.eu/en/vacancies
- **Platform**: Next.js with Storyblok CMS
- **Structure**: H3 headings for job titles with plain text dates
- **Approach**: Parse H3 elements and associated links/text

#### 5. EUSPA — `scrape_euspa.py`
- **URL**: https://www.euspa.europa.eu/opportunities/careers
- **Platform**: Drupal
- **Structure**: Card-based with title, reference number, employment type, deadline, external "Apply" link
- **Approach**: Parse card elements

#### 6. EIGE — `scrape_eige.py`
- **URL**: https://eige.europa.eu/about/recruitment
- **Platform**: Drupal
- **Structure**: Views-based card layout with metadata (Type, Reference, Published, Closing date). Has pagination.
- **Approach**: Parse `.views-row` / `.views-field` classes

#### 7. EIT — `scrape_eit.py`
- **URL**: https://www.eit.europa.eu/work-with-us/careers/vacancies/open
- **Platform**: Drupal
- **Structure**: Tab navigation (Open, Ongoing, Closed). Parse the "Open" tab.
- **Approach**: Standard Drupal link/card parsing

#### 8. ETF — `scrape_etf.py`
- **URL**: https://www.etf.europa.eu/en/about/recruitment
- **Platform**: Drupal
- **Structure**: Landing page with card-based links to separate vacancy pages
- **Approach**: Extract links to vacancy pages

#### 9. CEPOL — `scrape_cepol.py`
- **URL**: https://www.cepol.europa.eu/work-us/careers/vacancies
- **Platform**: Drupal/Next.js
- **Structure**: Paragraph-based content with tabs and downloads. May have embedded JSON props.
- **Approach**: Parse rendered HTML or extract from embedded JSON

#### 10. EFTA — `scrape_efta.py`
- **URL**: https://www.efta.int/careers/open-vacancies
- **Platform**: Drupal
- **Structure**: H3 headings followed by paragraph links to external jobs.efta.int portal
- **Approach**: Parse H3 + link elements

#### 11. ICES — `scrape_ices.py`
- **URL**: https://www.ices.dk/about-ICES/Jobs-in-ICES/Pages/default.aspx
- **Platform**: SharePoint 2013/2015
- **Structure**: H5 tags with links, followed by deadline text. Content in `#contentBox`.
- **Approach**: Parse `h5 a` elements

#### 12. CERN — `scrape_cern.py`
- **URL**: https://careers.cern/ (main careers page, not just graduates)
- **Platform**: WordPress with Gutenberg blocks
- **Structure**: Job listings in `.wp-block-post-template` with H3 elements
- **Approach**: Parse WordPress block template elements

#### 13. WCC — `scrape_wcc.py`
- **URL**: https://wcccoe.hire.trakstar.com/?#content
- **Platform**: Trakstar Hire
- **Structure**: Simple HTML — `<a>` tags with `<h3>` title and `<p>` details (location, department, type)
- **Approach**: Parse anchor tags containing h3 elements. Very straightforward.

#### 14. F4E — `scrape_f4e.py`
- **URL**: https://fusionforenergy.europa.eu/vacancies/
- **Platform**: WordPress with GestMax ATS
- **Structure**: Empty divs populated via WordPress REST API at `/wp-json/myplugin/v1/data/`
- **Approach**: Try fetching the REST API endpoint directly. Fallback to parsing static HTML if API works.

#### 15. EUISS — `scrape_euiss.py`
- **URL**: https://www.iss.europa.eu/opportunities
- **Platform**: Drupal with AJAX Views
- **Structure**: Initial 10 items in HTML via `.view-opportunities`, `.views-row`. Pagination via AJAX.
- **Approach**: Parse first page. If pagination needed, make AJAX calls.

#### 16. BIS — `scrape_bis.py`
- **URL**: https://www.bis.org/careers/vacancies.htm
- **Platform**: Custom portal
- **Structure**: May be informational page with links to actual job portal. Need to check.
- **Approach**: Fetch page, extract whatever job links are available.

#### 17. EUMETSAT — `scrape_eumetsat.py`
- **URL**: https://eumetsat.onlyfy.jobs/ (redirects from eumetsat.int/work-us/vacancies)
- **Platform**: Onlyfy jobs platform
- **Approach**: Fetch the Onlyfy page and parse job listings. Check if there's an API.

#### 18. NDF — `scrape_ndf.py`
- **URL**: https://www.ndf.int/contact-us/jobs.html
- **Platform**: Sivuviidakko CMS
- **Structure**: Landing page with links to job listings
- **Approach**: Parse links on the page

#### 19. UNFCCC — `scrape_unfccc.py`
- **URL**: https://unfccc.int/secretariat/employment/recruitment
- **Approach**: Fetch and parse. May have certificate issues — try with `verify=False` if needed.

#### 20. SATCEN — `scrape_satcen.py`
- **URL**: https://www.satcen.europa.eu/recruitment/jobs
- **Approach**: Fetch and parse HTML structure

### Group 2: API-based or adapted from existing scrapers

#### 21. EC — `scrape_ec.py`
- **URL**: https://eu-careers.europa.eu/en/job-opportunities/open-vacancies/ec_vacancies
- **Platform**: Same Drupal EU Careers as `scrape_eu_careers.py`
- **Structure**: HTML table with sortable columns (title, domain, DG, grade, location, dates)
- **Approach**: Copy pattern from `scrape_eu_careers.py` with different URL path

#### 22. Euratom — `scrape_euratom.py`
- **URL**: https://eu-careers.europa.eu/en/job-opportunities/open-for-application
- **Platform**: Same Drupal EU Careers
- **Approach**: Same paginated table approach as `scrape_eu_careers.py`

#### 23. EFSF — `scrape_efsf.py`
- **URL**: https://www.esm.europa.eu/careers/vacancies
- **Platform**: Drupal CMS (ESM website)
- **Structure**: Basic job cards with title, employment type, deadline. Links to Oracle CX portal.
- **Approach**: Scrape the listing page for job titles and external links

#### 24. NATO — `scrape_nato.py`
- **URL**: https://www.nato.int/en/work-with-us/careers/vacancies
- **Platform**: Adobe Experience Manager
- **Structure**: Dynamic content loaded via AJAX endpoint `/_jcr_content/root/container/vacancies.nocache.html`
- **Approach**: Fetch the AJAX partial HTML endpoint directly, parse the HTML fragment

#### 25. Council of Europe — `scrape_coe.py`
- **URL**: https://talents.coe.int/en_GB/careersmarketplace
- **Platform**: Custom recruitment portal
- **API**: Endpoints at `/WidgetOpenPositions` and `/SearchJobs`
- **Approach**: Try the API endpoints directly with POST requests. Parse JSON response.

#### 26. EU-LISA — `scrape_eulisa.py`
- **URL**: https://erecruitment.eulisa.europa.eu/en
- **Platform**: Next.js with Material-UI
- **Structure**: Job data may be in `__NEXT_DATA__` script tag
- **Approach**: Fetch page, extract JSON from `__NEXT_DATA__`, parse job listings from props

## Sites NOT Feasible Without Browser Automation (skip for now)

| Site | Reason |
|------|--------|
| European Council [Council] | Cloudflare blocks requests |
| ECA (Court of Auditors) | SharePoint + gestmax iframe, JS-only |
| EFCA (Fisheries Control) | Cloudflare blocks requests |
| European Ombudsman | Full Angular SPA, no SSR |
| ECHA (Chemicals Agency) | PeopleSoft, requires cookie/auth flow |
| EIB (Investment Bank) | PeopleSoft, requires cookie/auth flow |
| EUIPO (IP Office) | SuccessFactors with heavy SAPUI5 JS framework |
| ESM (Stability Mechanism) | Oracle CX SPA, hash-routed, XHR-only data |
| EUROJUST | TALENToft SPA with AJAX loading |
| EUROCONTROL | SSL certificate verification error |
| IMO (Maritime Org) | Minimal HTML, JS-loaded content |
| EMCDDA (Drugs Agency) | Rebranded to EUDA, URLs redirect to 404 |
| NIB (Nordic Investment Bank) | React hydration with base64-encoded data |
| IOOC (Olive Oil Council) | Dynamic loading, no initial HTML content |
| UNWTO (Tourism Org) | Connection refused |
| EBU (Broadcasting Union) | 403 Forbidden |
| ICO (Coffee Org) | SSL certificate error |
| EUROFIMA | No URL listed in CSV |

## After Implementation

1. Add each new scraper to `SCRAPER_INFO` dict in `test_scrapers.py`
2. Update `sites.csv` scraper column for each new scraper
3. Run `python test_scrapers.py` to verify all scrapers work
4. Some sites may have 0 current vacancies — that's OK if scraper runs without errors
