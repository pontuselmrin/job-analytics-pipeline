"""Shared enrichment runner with verbose timing + structured logging."""

from __future__ import annotations

import importlib.util
import json
import signal
import sys
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
import threading

from .config import PLAYWRIGHT_ORGS, REQUEST_DELAY, get_logs_path, get_profile_dir
from .fetcher import classify_fetch_error, extract_html_description, fetch_job_content
from .schema import (
    enrich_job,
    is_enriched,
    load_output,
    mark_enriched,
    mark_error,
    save_output,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRAPERS_DIR = PROJECT_ROOT / "scrapers"
SCRAPERS_PW_DIR = PROJECT_ROOT / "scrapers_playwright"
ORG_429_BREAKER_THRESHOLD = 3


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _word_count(text: str) -> int:
    return len((text or "").split())


@contextmanager
def _time_limit(seconds: float):
    """Hard timeout wrapper for single fetch calls (Unix only)."""
    if (
        seconds <= 0
        or not hasattr(signal, "SIGALRM")
        or threading.current_thread() is not threading.main_thread()
    ):
        yield
        return

    def _raise_timeout(_signum, _frame):
        raise TimeoutError(f"fetch timed out after {seconds:.1f}s")

    old_handler = signal.getsignal(signal.SIGALRM)
    signal.signal(signal.SIGALRM, _raise_timeout)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old_handler)


@dataclass
class RunnerConfig:
    run_id: str
    batch_id: str = ""
    verbose: bool = True
    live_events: bool = False
    ndjson_path: Path | None = None
    profile: bool = False
    profile_dir: Path | None = None


class EventLogger:
    def __init__(self, cfg: RunnerConfig):
        self.cfg = cfg
        self._fh = None
        self._lock = threading.Lock()
        if cfg.ndjson_path:
            cfg.ndjson_path.parent.mkdir(parents=True, exist_ok=True)
            self._fh = cfg.ndjson_path.open("a", encoding="utf-8")

    def close(self):
        if self._fh:
            self._fh.close()
            self._fh = None

    def emit(self, event: str, **fields):
        payload = {
            "event": event,
            "ts_utc": _utc_now(),
            "run_id": self.cfg.run_id,
            "batch_id": self.cfg.batch_id or "",
            **fields,
        }
        if self._fh:
            with self._lock:
                self._fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
                self._fh.flush()
        if self.cfg.live_events:
            with self._lock:
                print(json.dumps(payload, ensure_ascii=False), flush=True)

    def info(self, msg: str):
        if self.cfg.verbose:
            with self._lock:
                print(msg, flush=True)


def default_run_id(prefix: str = "run") -> str:
    return f"{prefix}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"


def default_ndjson_path(run_id: str) -> Path:
    """Get the default ndjson log path for a run."""
    return get_logs_path(run_id)


def _load_scraper_module(filepath: Path):
    parent = str(filepath.parent)
    if parent not in sys.path:
        sys.path.insert(0, parent)
    spec = importlib.util.spec_from_file_location("scraper", filepath)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_scraper_for_org(
    scraper_path: Path, org_abbrev: str, org_name: str, logger: EventLogger
) -> list[dict]:
    logger.info(
        f"[{org_abbrev}] scraper_start file={scraper_path.relative_to(PROJECT_ROOT)}"
    )
    logger.emit(
        "org_start",
        org_abbrev=org_abbrev,
        org_name=org_name,
        scraper_file=str(scraper_path.relative_to(PROJECT_ROOT)),
    )
    started = time.perf_counter()
    mod = _load_scraper_module(scraper_path)
    jobs = mod.scrape()
    elapsed = round(time.perf_counter() - started, 3)
    logger.emit(
        "scraper_done",
        org_abbrev=org_abbrev,
        org_name=org_name,
        job_count=len(jobs),
        duration_seconds=elapsed,
    )
    logger.info(f"[{org_abbrev}] scraper_done jobs={len(jobs)} t={elapsed:.3f}s")
    return jobs


def _profile_call(enabled: bool, profile_out: Path | None, fn: Callable):
    if not enabled:
        return fn()
    if profile_out is None:
        return fn()

    try:
        from pyinstrument import Profiler
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "pyinstrument is not installed. Run: uv add pyinstrument"
        ) from exc

    profile_out.parent.mkdir(parents=True, exist_ok=True)
    profiler = Profiler()
    profiler.start()
    try:
        return fn()
    finally:
        profiler.stop()
        profile_out.write_text(profiler.output_html())


def _fetch_one(
    org_abbrev: str,
    org_name: str,
    idx: int,
    total: int,
    title: str,
    url: str,
    is_playwright: bool,
    logger: EventLogger,
    job_timeout_seconds: float = 30.0,
) -> dict:
    logger.emit(
        "job_start",
        org_abbrev=org_abbrev,
        org_name=org_name,
        job_index=idx,
        total_jobs=total,
        job_title=title,
        job_url=url,
    )
    logger.info(f"[{org_abbrev}] [{idx}/{total}] START title={title[:80]} url={url}")

    if not url:
        result = {
            "content_type": "error",
            "description": "",
            "pdf_path": "",
            "enrich_status": "no_detail_url",
            "status_reason": "missing_url",
            "fetch_method": "none",
            "fetch_seconds": 0.0,
            "error": "",
        }
        logger.emit(
            "job_result",
            org_abbrev=org_abbrev,
            org_name=org_name,
            job_index=idx,
            job_title=title,
            job_url=url,
            duration_seconds=0.0,
            enrich_status=result["enrich_status"],
            content_type=result["content_type"],
            word_count=0,
            status_reason=result["status_reason"],
            error="",
        )
        logger.info(
            f"[{org_abbrev}] [{idx}/{total}] DONE status=no_detail_url words=0 t=0.000s"
        )
        return result

    started = time.perf_counter()
    try:
        with _time_limit(job_timeout_seconds):
            result = fetch_job_content(
                url=url,
                org_abbrev=org_abbrev,
                title=title or f"job-{idx}",
                use_playwright=is_playwright,
                run_id=logger.cfg.run_id,
            )
        fetch_seconds = round(time.perf_counter() - started, 3)
        out = {
            **result,
            "fetch_seconds": fetch_seconds,
            "error": "",
        }
        words = _word_count(out.get("description", ""))
        logger.emit(
            "job_result",
            org_abbrev=org_abbrev,
            org_name=org_name,
            job_index=idx,
            job_title=title,
            job_url=url,
            duration_seconds=fetch_seconds,
            enrich_status=out.get("enrich_status", ""),
            content_type=out.get("content_type", ""),
            word_count=words,
            status_reason=out.get("status_reason", ""),
            error="",
        )
        logger.info(
            f"[{org_abbrev}] [{idx}/{total}] DONE "
            f"status={out.get('enrich_status', '')} type={out.get('content_type', '')} "
            f"words={words} t={fetch_seconds:.3f}s"
        )
        return out
    except Exception as exc:  # noqa: BLE001
        fetch_seconds = round(time.perf_counter() - started, 3)
        status, reason = classify_fetch_error(exc)

        # Some Playwright-only pages fail in HTTP preflight; fallback to browser extraction.
        if is_playwright:
            try:
                fallback_start = time.perf_counter()
                with _time_limit(job_timeout_seconds):
                    desc = extract_html_description(url, use_playwright=True)
                fallback_seconds = round(time.perf_counter() - fallback_start, 3)
                if len(desc) > 100:
                    out = {
                        "content_type": "html",
                        "description": desc,
                        "pdf_path": "",
                        "enrich_status": "ok",
                        "status_reason": "playwright_fallback",
                        "fetch_method": "playwright",
                        "fetch_seconds": fallback_seconds,
                        "error": "",
                    }
                    words = _word_count(desc)
                    logger.emit(
                        "job_result",
                        org_abbrev=org_abbrev,
                        org_name=org_name,
                        job_index=idx,
                        job_title=title,
                        job_url=url,
                        duration_seconds=fallback_seconds,
                        enrich_status="ok",
                        content_type="html",
                        word_count=words,
                        status_reason="playwright_fallback",
                        error="",
                    )
                    logger.info(
                        f"[{org_abbrev}] [{idx}/{total}] DONE status=ok type=html "
                        f"words={words} t={fallback_seconds:.3f}s [playwright_fallback]"
                    )
                    return out
            except Exception:
                pass

        out = {
            "content_type": "error",
            "description": "",
            "pdf_path": "",
            "enrich_status": status,
            "status_reason": reason,
            "fetch_method": "http",
            "fetch_seconds": fetch_seconds,
            "error": str(exc),
        }
        logger.emit(
            "job_error",
            org_abbrev=org_abbrev,
            org_name=org_name,
            job_index=idx,
            job_title=title,
            job_url=url,
            duration_seconds=fetch_seconds,
            enrich_status=status,
            content_type="error",
            word_count=0,
            status_reason=reason,
            error=str(exc),
        )
        logger.info(
            f"[{org_abbrev}] [{idx}/{total}] ERROR status={status}:{reason} t={fetch_seconds:.3f}s err={exc}"
        )
        return out


def _rate_limited_skip_result() -> dict:
    return {
        "content_type": "error",
        "description": "",
        "pdf_path": "",
        "enrich_status": "blocked_source",
        "status_reason": "org_rate_limited_skip",
        "fetch_method": "http",
        "fetch_seconds": 0.0,
        "error": "",
    }


def _scraper_detail_result(raw_job: dict, org_abbrev: str) -> dict | None:
    if (org_abbrev or "").upper() != "EIB":
        return None
    description = (raw_job.get("description") or "").strip()
    if _word_count(description) < 50 or len(description) < 120:
        return None
    return {
        "content_type": "html",
        "description": description,
        "pdf_path": (raw_job.get("pdf_path") or "").strip(),
        "enrich_status": "ok",
        "status_reason": "scraper_detail",
        "fetch_method": "scraper",
        "fetch_seconds": 0.0,
        "error": "",
    }


def enrich_org_via_runner(
    *,
    org_abbrev: str,
    org_name: str,
    scraper_file: str,
    is_playwright_scraper: bool,
    use_playwright_detail: bool,
    force: bool,
    logger: EventLogger,
    profile: bool = False,
    max_jobs: int | None = None,
    job_timeout_seconds: float = 30.0,
) -> dict:
    base_dir = SCRAPERS_PW_DIR if is_playwright_scraper else SCRAPERS_DIR
    scraper_path = base_dir / scraper_file

    def _run():
        raw_jobs = run_scraper_for_org(scraper_path, org_abbrev, org_name, logger)
        existing = load_output(org_abbrev)
        existing_by_url: dict[str, dict] = {}
        if existing and not force:
            for job in existing.get("jobs", []):
                url = job.get("url", "")
                if url and is_enriched(job):
                    existing_by_url[url] = job

        pw_detail = use_playwright_detail or (org_abbrev in PLAYWRIGHT_ORGS)
        enriched_jobs = []
        selected = raw_jobs[:max_jobs] if max_jobs and max_jobs > 0 else raw_jobs
        consecutive_429 = 0
        breaker_open = False
        for i, raw_job in enumerate(selected, start=1):
            url = (raw_job.get("url") or "").strip()
            if url in existing_by_url:
                cached_job = existing_by_url[url]
                enriched_jobs.append(cached_job)
                logger.emit(
                    "job_result",
                    org_abbrev=org_abbrev,
                    org_name=org_name,
                    job_index=i,
                    job_title=raw_job.get("title", ""),
                    job_url=url,
                    duration_seconds=0.0,
                    enrich_status=cached_job.get("enrich_status", "cached"),
                    content_type=cached_job.get("content_type", ""),
                    word_count=_word_count(cached_job.get("description", "")),
                    status_reason="cached",
                    error="",
                )
                logger.info(
                    f"[{org_abbrev}] [{i}/{len(selected)}] DONE status=cached "
                    f"words={_word_count(cached_job.get('description', ''))} t=0.000s"
                )
                continue

            if breaker_open:
                fetch_res = _rate_limited_skip_result()
                logger.emit(
                    "job_result",
                    org_abbrev=org_abbrev,
                    org_name=org_name,
                    job_index=i,
                    job_title=(raw_job.get("title") or "").strip(),
                    job_url=url,
                    duration_seconds=0.0,
                    enrich_status=fetch_res["enrich_status"],
                    content_type=fetch_res["content_type"],
                    word_count=0,
                    status_reason=fetch_res["status_reason"],
                    error="",
                )
                logger.info(
                    f"[{org_abbrev}] [{i}/{len(selected)}] SKIP status=blocked_source:org_rate_limited_skip "
                    "t=0.000s"
                )
            else:
                fetch_res = _scraper_detail_result(raw_job, org_abbrev)
                if fetch_res:
                    words = _word_count(fetch_res.get("description", ""))
                    logger.emit(
                        "job_result",
                        org_abbrev=org_abbrev,
                        org_name=org_name,
                        job_index=i,
                        job_title=(raw_job.get("title") or "").strip(),
                        job_url=url,
                        duration_seconds=0.0,
                        enrich_status=fetch_res.get("enrich_status", ""),
                        content_type=fetch_res.get("content_type", ""),
                        word_count=words,
                        status_reason=fetch_res.get("status_reason", ""),
                        error="",
                    )
                    logger.info(
                        f"[{org_abbrev}] [{i}/{len(selected)}] DONE "
                        "status=ok type=html words="
                        f"{words} t=0.000s [scraper_detail]"
                    )
                    consecutive_429 = 0
                else:
                    fetch_res = _fetch_one(
                        org_abbrev=org_abbrev,
                        org_name=org_name,
                        idx=i,
                        total=len(selected),
                        title=(raw_job.get("title") or "").strip(),
                        url=url,
                        is_playwright=pw_detail,
                        logger=logger,
                        job_timeout_seconds=job_timeout_seconds,
                    )
                    if (
                        fetch_res.get("enrich_status") == "blocked_source"
                        and fetch_res.get("status_reason") == "http_429"
                    ):
                        consecutive_429 += 1
                        if consecutive_429 >= ORG_429_BREAKER_THRESHOLD:
                            breaker_open = True
                            logger.emit(
                                "org_rate_limited",
                                org_abbrev=org_abbrev,
                                org_name=org_name,
                                consecutive_429=consecutive_429,
                                threshold=ORG_429_BREAKER_THRESHOLD,
                            )
                            logger.info(
                                f"[{org_abbrev}] rate_limit_breaker_open "
                                f"after {consecutive_429} consecutive http_429 errors"
                            )
                    else:
                        consecutive_429 = 0

            job = enrich_job(raw_job, org_name, org_abbrev)
            if fetch_res.get("error"):
                mark_error(
                    job,
                    fetch_res["error"],
                    enrich_status=fetch_res.get("enrich_status", "error"),
                    status_reason=fetch_res.get("status_reason", ""),
                    fetch_method=fetch_res.get("fetch_method", "http"),
                )
            else:
                mark_enriched(
                    job,
                    content_type=fetch_res.get("content_type", ""),
                    description=fetch_res.get("description", ""),
                    pdf_path=fetch_res.get("pdf_path", ""),
                    enrich_status=fetch_res.get("enrich_status", "ok"),
                    status_reason=fetch_res.get("status_reason", ""),
                    fetch_method=fetch_res.get("fetch_method", "http"),
                )
            job["fetch_seconds"] = fetch_res.get("fetch_seconds", 0.0)
            enriched_jobs.append(job)

            if i < len(selected):
                time.sleep(REQUEST_DELAY)

        output_path = save_output(org_name, org_abbrev, enriched_jobs)
        logger.emit(
            "org_done",
            org_abbrev=org_abbrev,
            org_name=org_name,
            job_count=len(enriched_jobs),
            output_path=str(output_path),
        )
        logger.info(
            f"[{org_abbrev}] org_done jobs={len(enriched_jobs)} output={output_path}"
        )
        return {
            "org_name": org_name,
            "org_abbrev": org_abbrev,
            "job_count": len(enriched_jobs),
            "output_path": str(output_path),
        }

    profile_out = (
        get_profile_dir(logger.cfg.run_id) / f"{org_abbrev}.html" if profile else None
    )
    return _profile_call(profile, profile_out, _run)


def collect_postings_org_via_runner(
    *,
    org_abbrev: str,
    org_name: str,
    scraper_path: Path,
    is_playwright_scraper: bool,
    logger: EventLogger,
    profile: bool = False,
    max_jobs: int | None = None,
    job_timeout_seconds: float = 30.0,
) -> dict:
    org_block = {
        "org_abbrev": org_abbrev,
        "org_name": org_name,
        "scraper_file": str(scraper_path.relative_to(PROJECT_ROOT)),
        "is_playwright_scraper": is_playwright_scraper,
        "jobs": [],
        "scraper_error": "",
    }

    def _run():
        try:
            jobs = run_scraper_for_org(scraper_path, org_abbrev, org_name, logger)
        except Exception as exc:  # noqa: BLE001
            org_block["scraper_error"] = str(exc)
            logger.emit(
                "org_done",
                org_abbrev=org_abbrev,
                org_name=org_name,
                scraper_error=str(exc),
                job_count=0,
            )
            logger.info(f"[{org_abbrev}] scraper_error={exc}")
            return org_block

        selected = jobs[:max_jobs] if max_jobs and max_jobs > 0 else jobs
        consecutive_429 = 0
        breaker_open = False
        for idx, job in enumerate(selected, start=1):
            title = (job.get("title") or "").strip()
            url = (job.get("url") or "").strip()
            if breaker_open:
                fetch_res = _rate_limited_skip_result()
                logger.emit(
                    "job_result",
                    org_abbrev=org_abbrev,
                    org_name=org_name,
                    job_index=idx,
                    job_title=title,
                    job_url=url,
                    duration_seconds=0.0,
                    enrich_status=fetch_res["enrich_status"],
                    content_type=fetch_res["content_type"],
                    word_count=0,
                    status_reason=fetch_res["status_reason"],
                    error="",
                )
                logger.info(
                    f"[{org_abbrev}] [{idx}/{len(selected)}] SKIP status=blocked_source:org_rate_limited_skip "
                    "t=0.000s"
                )
            else:
                fetch_res = _scraper_detail_result(job, org_abbrev)
                if fetch_res:
                    words = _word_count(fetch_res.get("description", ""))
                    logger.emit(
                        "job_result",
                        org_abbrev=org_abbrev,
                        org_name=org_name,
                        job_index=idx,
                        job_title=title,
                        job_url=url,
                        duration_seconds=0.0,
                        enrich_status=fetch_res.get("enrich_status", ""),
                        content_type=fetch_res.get("content_type", ""),
                        word_count=words,
                        status_reason=fetch_res.get("status_reason", ""),
                        error="",
                    )
                    logger.info(
                        f"[{org_abbrev}] [{idx}/{len(selected)}] DONE "
                        "status=ok type=html words="
                        f"{words} t=0.000s [scraper_detail]"
                    )
                    consecutive_429 = 0
                else:
                    fetch_res = _fetch_one(
                        org_abbrev=org_abbrev,
                        org_name=org_name,
                        idx=idx,
                        total=len(selected),
                        title=title,
                        url=url,
                        is_playwright=is_playwright_scraper,
                        logger=logger,
                        job_timeout_seconds=job_timeout_seconds,
                    )
                    if (
                        fetch_res.get("enrich_status") == "blocked_source"
                        and fetch_res.get("status_reason") == "http_429"
                    ):
                        consecutive_429 += 1
                        if consecutive_429 >= ORG_429_BREAKER_THRESHOLD:
                            breaker_open = True
                            logger.emit(
                                "org_rate_limited",
                                org_abbrev=org_abbrev,
                                org_name=org_name,
                                consecutive_429=consecutive_429,
                                threshold=ORG_429_BREAKER_THRESHOLD,
                            )
                            logger.info(
                                f"[{org_abbrev}] rate_limit_breaker_open "
                                f"after {consecutive_429} consecutive http_429 errors"
                            )
                    else:
                        consecutive_429 = 0

            org_block["jobs"].append(
                {
                    "index": idx,
                    "title": title,
                    "url": url,
                    "content_type": fetch_res.get("content_type", ""),
                    "enrich_status": fetch_res.get("enrich_status", ""),
                    "status_reason": fetch_res.get("status_reason", ""),
                    "fetch_method": fetch_res.get("fetch_method", ""),
                    "description": fetch_res.get("description", ""),
                    "pdf_path": fetch_res.get("pdf_path", ""),
                    "fetch_seconds": fetch_res.get("fetch_seconds", 0.0),
                    "error": fetch_res.get("error", ""),
                }
            )

        logger.emit(
            "org_done",
            org_abbrev=org_abbrev,
            org_name=org_name,
            job_count=len(org_block["jobs"]),
            scraper_error="",
        )
        return org_block

    profile_out = (
        get_profile_dir(logger.cfg.run_id) / f"{org_abbrev}.html" if profile else None
    )
    return _profile_call(profile, profile_out, _run)
