"""Shared utilities for all scrapers."""

import time
from email.utils import parsedate_to_datetime

import requests

from config import DEFAULT_HEADERS, API_JSON_HEADERS, API_EXTENDED_HEADERS


def _retry_delay_seconds(exc: requests.RequestException, attempt: int) -> float:
    """Compute retry delay, honoring Retry-After for 429 responses."""
    default = float(2**attempt)
    resp = getattr(exc, "response", None)
    if resp is None or getattr(resp, "status_code", None) != 429:
        return default

    header = (resp.headers or {}).get("Retry-After", "")
    if not header:
        return default

    try:
        return max(0.0, float(header))
    except ValueError:
        try:
            dt = parsedate_to_datetime(header)
            return max(0.0, dt.timestamp() - time.time())
        except Exception:
            return default


def fetch(url, method="GET", headers=None, **kwargs):
    """HTTP request with retry (3 attempts, 429-aware backoff)."""
    if headers is None:
        headers = DEFAULT_HEADERS
    for attempt in range(3):
        try:
            resp = requests.request(method, url, headers=headers, **kwargs)
            resp.raise_for_status()
            return resp
        except requests.RequestException as exc:
            if attempt == 2:
                raise
            time.sleep(_retry_delay_seconds(exc, attempt))


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
        jobs.append(
            {
                "title": title,
                "url": normalize_url(href, base_url),
            }
        )

    return jobs


def scrape_api_json_paginated(base_url, api_url):
    """Generic JSON API pagination loop. Returns list of {"title", "url", "location"}."""
    parts = api_url.rstrip("/").split("/")
    site = parts[-2] if len(parts) >= 2 else "External"
    site_prefix = f"/{site}"

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
        resp = fetch(api_url, method="POST", headers=API_JSON_HEADERS, json=payload)
        try:
            data = resp.json()
        except Exception:
            # Some tenants occasionally return HTML maintenance pages.
            # Treat this as no postings instead of crashing the whole batch.
            break
        if not isinstance(data, dict):
            break

        postings = data.get("jobPostings", [])
        if not postings:
            break

        for job in postings:
            external_path = job.get("externalPath", "")
            if external_path and not external_path.startswith("/"):
                external_path = "/" + external_path
            if external_path.startswith(site_prefix + "/"):
                full_path = external_path
            else:
                full_path = site_prefix + external_path
            jobs.append(
                {
                    "title": job.get("title", ""),
                    # Some sites require /<site>/job/... (e.g. /External/job/...)
                    # while API externalPath commonly starts at /job/...
                    "url": base_url + full_path,
                    "location": job.get("locationsText", ""),
                }
            )

        offset += limit
        if offset >= data.get("total", 0):
            break

    return jobs


def scrape_api_advanced_paginated(
    base_url,
    portal_id,
    section,
    column_map,
    strip_columns=None,
    filters=None,
    deduplicate=False,
):
    """Generic API pagination with advanced filtering and column mapping.

    column_map: dict mapping column index to field name, e.g. {0: "title", 1: "location"}
    strip_columns: set of column indices whose values should have []" stripped (locations)
    filters: optional list of filter dicts for filterSelectionParam/advancedSearchFiltersSelectionParam
    deduplicate: if True, skip duplicate contestNo values
    """
    api_url = f"{base_url}/careersection/rest/jobboard/searchjobs"
    headers = {
        **API_EXTENDED_HEADERS,
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
            "advancedSearchFiltersSelectionParam": {
                "searchFilterSelections": filter_selections
            },
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

            entry["url"] = (
                f"{base_url}/careersection/{section}/jobdetail.ftl?job={job_id}"
            )
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
