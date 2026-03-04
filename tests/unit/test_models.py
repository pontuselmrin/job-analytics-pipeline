"""Unit tests for enrichment/models.py Pydantic boundary models."""

import pytest
from pydantic import ValidationError

from enrichment.models import EnrichedJob, FetchResult, ScrapedJob


# ---------------------------------------------------------------------------
# ScrapedJob
# ---------------------------------------------------------------------------


class TestScrapedJob:
    def test_valid_minimal(self):
        job = ScrapedJob.model_validate(
            {"title": "Engineer", "url": "https://example.com/job/1"}
        )
        assert job.title == "Engineer"
        assert job.url == "https://example.com/job/1"

    def test_extra_fields_pass_through(self):
        job = ScrapedJob.model_validate(
            {
                "title": "Engineer",
                "url": "https://example.com",
                "location": "Brussels",
                "deadline": "2026-04-01",
            }
        )
        assert job.location == "Brussels"  # type: ignore[attr-defined]
        assert job.deadline == "2026-04-01"  # type: ignore[attr-defined]

    def test_missing_title_raises(self):
        with pytest.raises(ValidationError) as exc_info:
            ScrapedJob.model_validate({"url": "https://example.com"})
        assert "title" in str(exc_info.value)

    def test_missing_url_raises(self):
        with pytest.raises(ValidationError) as exc_info:
            ScrapedJob.model_validate({"title": "Engineer"})
        assert "url" in str(exc_info.value)

    def test_empty_dict_raises(self):
        with pytest.raises(ValidationError):
            ScrapedJob.model_validate({})


# ---------------------------------------------------------------------------
# FetchResult
# ---------------------------------------------------------------------------


class TestFetchResult:
    def test_valid_minimal(self):
        result = FetchResult.model_validate({"content_type": "html"})
        assert result.content_type == "html"

    def test_defaults_applied(self):
        result = FetchResult.model_validate({"content_type": "pdf"})
        assert result.description == ""
        assert result.pdf_path == ""
        assert result.enrich_status == ""
        assert result.status_reason == ""
        assert result.fetch_method == ""
        assert result.fetch_seconds == 0.0
        assert result.error == ""

    def test_full_valid(self):
        result = FetchResult.model_validate(
            {
                "content_type": "html",
                "description": "Job description text",
                "pdf_path": "",
                "enrich_status": "ok",
                "status_reason": "",
                "fetch_method": "http",
                "fetch_seconds": 1.23,
                "error": "",
            }
        )
        assert result.enrich_status == "ok"
        assert result.fetch_seconds == 1.23

    def test_missing_content_type_raises(self):
        with pytest.raises(ValidationError) as exc_info:
            FetchResult.model_validate({"description": "some text"})
        assert "content_type" in str(exc_info.value)

    def test_extra_fields_ignored(self):
        # FetchResult uses the default extra="ignore": unknown fields are dropped silently.
        result = FetchResult.model_validate(
            {"content_type": "html", "unexpected_field": "value"}
        )
        assert result.content_type == "html"
        assert not hasattr(result, "unexpected_field")

    def test_model_dump_roundtrip(self):
        d = {"content_type": "html", "fetch_seconds": 0.5}
        result = FetchResult.model_validate(d).model_dump()
        assert isinstance(result, dict)
        assert result["content_type"] == "html"
        assert result["fetch_seconds"] == 0.5
        assert result["description"] == ""


# ---------------------------------------------------------------------------
# EnrichedJob
# ---------------------------------------------------------------------------


class TestEnrichedJob:
    def test_valid_minimal(self):
        job = EnrichedJob.model_validate(
            {"title": "Analyst", "url": "https://example.com/job/2"}
        )
        assert job.title == "Analyst"
        assert job.url == "https://example.com/job/2"

    def test_defaults_applied(self):
        job = EnrichedJob.model_validate(
            {"title": "Analyst", "url": "https://example.com"}
        )
        assert job.org_name == ""
        assert job.org_abbrev == ""
        assert job.content_type == ""
        assert job.description == ""
        assert job.pdf_path == ""
        assert job.enriched_at == ""
        assert job.enrich_error == ""
        assert job.enrich_status == ""
        assert job.status_reason == ""
        assert job.fetch_method == ""
        assert job.fetch_seconds == 0.0

    def test_extra_fields_pass_through(self):
        job = EnrichedJob.model_validate(
            {"title": "Analyst", "url": "https://example.com", "location": "Paris"}
        )
        assert job.location == "Paris"  # type: ignore[attr-defined]

    def test_missing_title_raises(self):
        with pytest.raises(ValidationError) as exc_info:
            EnrichedJob.model_validate({"url": "https://example.com"})
        assert "title" in str(exc_info.value)

    def test_missing_url_raises(self):
        with pytest.raises(ValidationError) as exc_info:
            EnrichedJob.model_validate({"title": "Analyst"})
        assert "url" in str(exc_info.value)

    def test_full_enriched(self):
        job = EnrichedJob.model_validate(
            {
                "title": "Data Engineer",
                "url": "https://example.com/job/3",
                "org_name": "ACME Agency",
                "org_abbrev": "ACME",
                "content_type": "html",
                "description": "We are looking for a data engineer...",
                "enrich_status": "ok",
                "fetch_method": "http",
                "fetch_seconds": 2.1,
            }
        )
        assert job.org_abbrev == "ACME"
        assert job.fetch_seconds == 2.1
