"""Pydantic models for pipeline boundary validation."""

from pydantic import BaseModel, ConfigDict


class ScrapedJob(BaseModel):
    """Validates scraper output. Requires title + url, passes through extras."""

    model_config = ConfigDict(extra="allow")

    title: str
    url: str


class FetchResult(BaseModel):
    """Validates fetch_job_content() return value."""

    content_type: str
    description: str = ""
    pdf_path: str = ""
    enrich_status: str = ""
    status_reason: str = ""
    fetch_method: str = ""
    fetch_seconds: float = 0.0
    error: str = ""


class EnrichedJob(BaseModel):
    """Validates fully enriched job before DB upsert."""

    model_config = ConfigDict(extra="allow")

    title: str
    url: str
    org_name: str = ""
    org_abbrev: str = ""
    content_type: str = ""
    description: str = ""
    pdf_path: str = ""
    enriched_at: str = ""
    enrich_error: str = ""
    enrich_status: str = ""
    status_reason: str = ""
    fetch_method: str = ""
    fetch_seconds: float = 0.0
