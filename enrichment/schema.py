"""Standardized job schema and helpers for enrichment output."""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from .config import OUTPUT_DIR


def extract_abbrev(org_name: str) -> str:
    """Extract abbreviation from org name like 'Full Name [ABBREV]'."""
    match = re.search(r"\[([^\]]+)\]", org_name)
    if match:
        return match.group(1)
    # Fallback: use first word uppercased
    return org_name.split()[0].upper()


def enrich_job(job: dict, org_name: str, org_abbrev: str) -> dict:
    """Add enrichment fields to a scraped job dict (in-place friendly)."""
    enriched = {**job}
    enriched["org_name"] = org_name
    enriched["org_abbrev"] = org_abbrev
    enriched.setdefault("content_type", "")
    enriched.setdefault("description", "")
    enriched.setdefault("pdf_path", "")
    enriched.setdefault("enriched_at", "")
    enriched.setdefault("enrich_error", "")
    enriched.setdefault("enrich_status", "")
    enriched.setdefault("status_reason", "")
    enriched.setdefault("fetch_method", "")
    return enriched


def mark_enriched(
    job: dict,
    content_type: str,
    description: str = "",
    pdf_path: str = "",
    enrich_status: str = "ok",
    status_reason: str = "",
    fetch_method: str = "http",
) -> dict:
    """Mark a job as successfully enriched."""
    job["content_type"] = content_type
    job["description"] = description
    job["pdf_path"] = pdf_path
    job["enrich_status"] = enrich_status
    job["status_reason"] = status_reason
    job["fetch_method"] = fetch_method
    job["enriched_at"] = datetime.now(timezone.utc).isoformat()
    job["enrich_error"] = ""
    return job


def mark_error(
    job: dict,
    error_msg: str,
    enrich_status: str = "error",
    status_reason: str = "",
    fetch_method: str = "http",
) -> dict:
    """Mark a job as failed enrichment."""
    job["content_type"] = "error"
    job["enrich_status"] = enrich_status
    job["status_reason"] = status_reason
    job["fetch_method"] = fetch_method
    job["enrich_error"] = str(error_msg)
    job["enriched_at"] = datetime.now(timezone.utc).isoformat()
    return job


def is_enriched(job: dict) -> bool:
    """Check if a job was already successfully enriched."""
    status = job.get("enrich_status", "")
    if status:
        return status in ("ok", "pdf")
    return job.get("content_type", "") in ("html", "pdf")


def load_output(org_abbrev: str) -> dict | None:
    """Load existing enrichment output for an org, or None if not found."""
    path = OUTPUT_DIR / f"{org_abbrev}.json"
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)


def save_output(org_name: str, org_abbrev: str, jobs: list[dict]) -> Path:
    """Save enrichment output for an org. Returns the output path."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / f"{org_abbrev}.json"
    data = {
        "org_name": org_name,
        "org_abbrev": org_abbrev,
        "enriched_at": datetime.now(timezone.utc).isoformat(),
        "job_count": len(jobs),
        "jobs": jobs,
    }
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return path
