"""Shared utilities for all scrapers."""
import re
import time
import requests

DEFAULT_HEADERS = {
    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
}

WORKDAY_HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
}

TALEO_HEADERS = {
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "en-US,en;q=0.9",
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
    "X-Requested-With": "XMLHttpRequest",
    "tz": "GMT+01:00",
    "tzname": "Europe/Berlin",
}


def fetch(url, method="GET", headers=None, **kwargs):
    """HTTP request with retry (3 attempts, exponential backoff)."""
    if headers is None:
        headers = DEFAULT_HEADERS
    for attempt in range(3):
        try:
            resp = requests.request(method, url, headers=headers, **kwargs)
            resp.raise_for_status()
            return resp
        except requests.RequestException:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


def normalize_url(href, base_url):
    """Return absolute URL: if href starts with http, return as-is, else prepend base_url."""
    if href.startswith("http"):
        return href
    return base_url + href


def extract_links(soup, href_pattern, base_url, min_title_len=5, exclude_patterns=None):
    """Extract deduplicated links from soup where href contains href_pattern.

    Returns list of {"title": ..., "url": ...}.
    """
    jobs = []
    seen_urls = set()

    for link in soup.find_all("a", href=lambda h: h and href_pattern in h):
        href = link.get("href", "")
        if href in seen_urls:
            continue

        if exclude_patterns and any(p in href for p in exclude_patterns):
            continue

        title = link.get_text(strip=True)
        if not title or len(title) < min_title_len:
            continue

        seen_urls.add(href)
        jobs.append({
            "title": title,
            "url": normalize_url(href, base_url),
        })

    return jobs


def scrape_workday(base_url, api_url):
    """Full Workday pagination loop. Returns list of {"title", "url", "location"}."""
    jobs = []
    offset = 0
    limit = 20

    while True:
        payload = {
            "appliedFacets": {},
            "limit": limit,
            "offset": offset,
            "searchText": "",
        }
        resp = fetch(api_url, method="POST", headers=WORKDAY_HEADERS, json=payload)
        data = resp.json()

        postings = data.get("jobPostings", [])
        if not postings:
            break

        for job in postings:
            jobs.append({
                "title": job.get("title", ""),
                "url": base_url + job.get("externalPath", ""),
                "location": job.get("locationsText", ""),
            })

        offset += limit
        if offset >= data.get("total", 0):
            break

    return jobs


def scrape_taleo(base_url, portal_id, section, column_map, strip_columns=None,
                 filters=None, deduplicate=False):
    """Full Taleo pagination loop.

    column_map: dict mapping column index to field name, e.g. {0: "title", 1: "location"}
    strip_columns: set of column indices whose values should have []" stripped (locations)
    filters: optional list of filter dicts for filterSelectionParam/advancedSearchFiltersSelectionParam
    deduplicate: if True, skip duplicate contestNo values
    """
    api_url = f"{base_url}/careersection/rest/jobboard/searchjobs"
    headers = {
        **TALEO_HEADERS,
        "Origin": base_url,
        "Referer": f"{base_url}/careersection/{section}/jobsearch.ftl?lang=en",
    }
    cookies = {"locale": "en"}
    if strip_columns is None:
        strip_columns = set()

    filter_selections = filters or []

    all_jobs = []
    seen_ids = set()
    page = 1

    while True:
        print(f"Fetching page {page}...")
        payload = {
            "multilineEnabled": True,
            "sortingSelection": {
                "sortBySelectionParam": "3",
                "ascendingSortingOrder": "false",
            },
            "fieldData": {
                "fields": {"KEYWORD": "", "LOCATION": ""},
                "valid": True,
            },
            "filterSelectionParam": {"searchFilterSelections": filter_selections},
            "advancedSearchFiltersSelectionParam": {"searchFilterSelections": filter_selections},
            "pageNo": page,
        }

        resp = fetch(
            api_url,
            method="POST",
            headers=headers,
            json=payload,
            cookies=cookies,
            params={"lang": "en", "portal": portal_id},
        )
        data = resp.json()

        jobs = data.get("requisitionList", [])
        if not jobs:
            break

        new_jobs_count = 0
        for job in jobs:
            job_id = job.get("contestNo", "")

            if deduplicate:
                if job_id in seen_ids:
                    continue
                seen_ids.add(job_id)

            new_jobs_count += 1
            columns = job.get("column", [])
            entry = {}
            for idx, field in column_map.items():
                val = columns[idx] if len(columns) > idx else ""
                if idx in strip_columns:
                    val = val.strip('[]"')
                entry[field] = val

            # Always use contestNo for job_number if not in column_map
            if "job_number" not in entry:
                entry["job_number"] = job_id

            entry["url"] = f"{base_url}/careersection/{section}/jobdetail.ftl?job={job_id}"
            all_jobs.append(entry)

        if deduplicate and new_jobs_count == 0:
            break

        paging = data.get("pagingData", {})
        total_count = paging.get("totalCount", 0)
        if len(all_jobs) >= total_count:
            break

        page += 1
        time.sleep(0.5)

    return all_jobs
