"""Shared Playwright helpers for browser-based job scrapers."""

from __future__ import annotations

from typing import Callable
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from config import USER_AGENT, BLOCK_MARKERS

Extractor = Callable[..., list[dict]]


def normalize_url(href: str, base_url: str) -> str:
    """Return an absolute URL from href + base URL."""
    return urljoin(base_url, href)


def _looks_blocked(html: str, status_code: int | None) -> bool:
    lowered = html.lower()
    if status_code in {401, 403, 429, 503}:
        return True
    return any(marker in lowered for marker in BLOCK_MARKERS)


def _normalize_whitespace(text: str) -> str:
    return " ".join(text.split())


def collect_anchor_jobs_from_html(
    html: str,
    base_url: str,
    include_patterns: list[str],
    exclude_patterns: list[str] | None = None,
    min_title_len: int = 4,
) -> list[dict]:
    """Collect deduplicated job anchors from HTML using pattern filters."""
    soup = BeautifulSoup(html, "html.parser")
    include_patterns_l = [p.lower() for p in include_patterns]
    exclude_patterns_l = [p.lower() for p in (exclude_patterns or [])]

    jobs: list[dict] = []
    seen_urls: set[str] = set()

    for link in soup.find_all("a", href=True):
        href = (link.get("href") or "").strip()
        if not href or href.startswith("javascript:") or href.startswith("mailto:"):
            continue

        title = _normalize_whitespace(link.get_text(" ", strip=True))
        if len(title) < min_title_len:
            continue

        haystack = f"{title} {href}".lower()
        if include_patterns_l and not any(p in haystack for p in include_patterns_l):
            continue
        if exclude_patterns_l and any(p in haystack for p in exclude_patterns_l):
            continue

        full_url = normalize_url(href, base_url)
        if full_url in seen_urls:
            continue
        seen_urls.add(full_url)
        jobs.append({"title": title, "url": full_url})

    return jobs


def run_scraper(
    url: str,
    extractor: Extractor,
    wait_selectors: list[str] | None = None,
    timeout_ms: int = 45000,
    allow_headful_fallback: bool = True,
) -> list[dict]:
    """Run extractor in Playwright with headless-first fallback to headful."""
    modes = [True, False] if allow_headful_fallback else [True]
    last_err: Exception | None = None

    for headless in modes:
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=headless)
                context = browser.new_context(
                    user_agent=USER_AGENT,
                    ignore_https_errors=True,
                    java_script_enabled=True,
                )
                page = context.new_page()
                response = page.goto(
                    url, wait_until="domcontentloaded", timeout=timeout_ms
                )

                if wait_selectors:
                    for selector in wait_selectors:
                        try:
                            page.wait_for_selector(selector, timeout=6000)
                            break
                        except PlaywrightTimeoutError:
                            continue

                page.wait_for_timeout(1200)

                status_code = response.status if response else None
                blocked = _looks_blocked(page.content(), status_code)
                jobs = extractor(page=page, context=context)

                context.close()
                browser.close()

                # Some sites intermittently block automation traffic; treat this as
                # an empty scrape result instead of a hard failure.
                if blocked and not jobs:
                    return []

                return dedupe_jobs(jobs)
        except Exception as exc:  # noqa: PERF203
            last_err = exc
            continue

    if last_err:
        raise last_err
    return []


def extract_from_main_page(
    page,
    base_url: str,
    include_patterns: list[str],
    exclude_patterns: list[str] | None = None,
) -> list[dict]:
    html = page.content()
    return collect_anchor_jobs_from_html(
        html,
        base_url=base_url,
        include_patterns=include_patterns,
        exclude_patterns=exclude_patterns,
    )


def extract_from_frames(
    page,
    include_frame_patterns: list[str],
    base_url: str,
    include_patterns: list[str],
    exclude_patterns: list[str] | None = None,
) -> list[dict]:
    jobs: list[dict] = []
    frame_markers = [m.lower() for m in include_frame_patterns]

    for frame in page.frames:
        frame_url = (frame.url or "").lower()
        if frame_markers and not any(m in frame_url for m in frame_markers):
            continue
        try:
            html = frame.content()
        except Exception:
            continue
        jobs.extend(
            collect_anchor_jobs_from_html(
                html,
                base_url=base_url,
                include_patterns=include_patterns,
                exclude_patterns=exclude_patterns,
            )
        )

    return dedupe_jobs(jobs)


def dedupe_jobs(jobs: list[dict]) -> list[dict]:
    """Deduplicate jobs by URL preserving order."""
    out: list[dict] = []
    seen: set[str] = set()
    for job in jobs:
        url = (job.get("url") or "").strip()
        title = (job.get("title") or "").strip()
        if not url or not title:
            continue
        if url in seen:
            continue
        seen.add(url)
        out.append({**job, "title": title, "url": url})
    return out
