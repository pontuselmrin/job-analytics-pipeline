"""Batch postings quality gates and validation helpers."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_QUALITY_GATES_PATH = PROJECT_ROOT / "tests" / "fixtures" / "quality_gates.yaml"
SUCCESS_STATUSES = {"ok", "short_content"}


def load_quality_gates(path: Path = DEFAULT_QUALITY_GATES_PATH) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text()) or {}
    defaults = data.get("defaults") or {}
    return {
        "defaults": defaults,
        "org_overrides": data.get("org_overrides") or {},
    }


def count_words(text: str) -> int:
    return len((text or "").split())


def is_successful_description(job: dict[str, Any]) -> bool:
    status = (job.get("enrich_status") or "").strip().lower()
    description = (job.get("description") or "").strip()
    return bool(description) and status in SUCCESS_STATUSES


def org_has_pdf_jobs(jobs: list[dict[str, Any]]) -> bool:
    for job in jobs:
        content_type = (job.get("content_type") or "").strip().lower()
        pdf_path = (job.get("pdf_path") or "").strip()
        if content_type == "pdf" or pdf_path:
            return True
    return False


def _effective_thresholds(
    org_abbrev: str, gates: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    defaults = dict(gates.get("defaults") or {})
    override = dict((gates.get("org_overrides") or {}).get(org_abbrev) or {})

    effective = dict(defaults)
    for key in (
        "min_jobs_per_org",
        "min_words",
        "max_words",
        "max_fetch_seconds_per_job",
        "allow_empty",
    ):
        if key in override:
            effective[key] = override[key]

    return effective, override


def validate_org_block(
    org_block: dict[str, Any],
    gates: dict[str, Any],
    today: date | None = None,
) -> list[str]:
    today = today or date.today()
    org_abbrev = org_block.get("org_abbrev", "<unknown>")
    jobs = list(org_block.get("jobs") or [])
    violations: list[str] = []

    if org_block.get("scraper_error"):
        violations.append(
            f"{org_abbrev}: scraper_error present: {org_block['scraper_error']}"
        )

    thresholds, override = _effective_thresholds(org_abbrev, gates)

    expires_on = override.get("expires_on")
    if expires_on:
        try:
            expires_date = date.fromisoformat(str(expires_on))
            if today > expires_date:
                violations.append(
                    f"{org_abbrev}: override expired on {expires_date.isoformat()} "
                    f"(reason={override.get('reason', '')})"
                )
        except ValueError:
            violations.append(
                f"{org_abbrev}: invalid override expires_on '{expires_on}'"
            )

    max_fetch_seconds = float(thresholds.get("max_fetch_seconds_per_job", 20.0))
    allow_empty = bool(thresholds.get("allow_empty", False))
    min_jobs = int(thresholds.get("min_jobs_per_org", 1))
    min_words = int(thresholds.get("min_words", 50))
    max_words = int(thresholds.get("max_words", 10000))

    if len(jobs) < min_jobs and not allow_empty:
        violations.append(f"{org_abbrev}: returned {len(jobs)} jobs (< {min_jobs})")

    skip_word_based_checks = org_has_pdf_jobs(jobs)
    successful = [job for job in jobs if is_successful_description(job)]
    word_counts = [count_words(job.get("description", "")) for job in successful]

    if not skip_word_based_checks:
        if len(jobs) > 2 and len(successful) >= 3 and len(set(word_counts)) == 1:
            violations.append(
                f"{org_abbrev}: all successful descriptions share identical length ({word_counts[0]} words)"
            )

        for job in successful:
            wc = count_words(job.get("description", ""))
            if wc < min_words or wc > max_words:
                violations.append(
                    f"{org_abbrev}: job #{job.get('index')} word_count={wc} out of bounds "
                    f"[{min_words}, {max_words}] url={job.get('url', '')}"
                )

    for job in jobs:
        url = (job.get("url") or "").strip()
        if not url:
            continue
        fetch_seconds = float(job.get("fetch_seconds", 0.0))
        if fetch_seconds > max_fetch_seconds:
            violations.append(
                f"{org_abbrev}: job #{job.get('index')} fetch_seconds={fetch_seconds:.3f} "
                f"> {max_fetch_seconds:.3f} url={url}"
            )

    return violations


def validate_postings_payload(
    payload: dict[str, Any], gates: dict[str, Any], today: date | None = None
) -> list[str]:
    violations: list[str] = []
    orgs = payload.get("orgs")
    if not isinstance(orgs, list) or not orgs:
        return ["payload: missing non-empty 'orgs' list"]

    for org_block in orgs:
        violations.extend(validate_org_block(org_block, gates=gates, today=today))
    return violations


def format_violations(violations: list[str]) -> str:
    return "\n".join(f"- {item}" for item in violations)
