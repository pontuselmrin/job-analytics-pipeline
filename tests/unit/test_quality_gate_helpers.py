from datetime import date

from tests.fixtures.quality_gates import (
    count_words,
    format_violations,
    validate_org_block,
    validate_postings_payload,
)


def _base_gates():
    return {
        "defaults": {
            "min_words": 50,
            "max_words": 10000,
            "max_fetch_seconds_per_job": 10.0,
        },
        "org_overrides": {},
    }


def test_count_words_splits_on_whitespace():
    assert count_words("alpha beta\ngamma\t delta") == 4


def test_validate_org_block_flags_expired_override():
    gates = _base_gates()
    gates["org_overrides"]["X"] = {
        "reason": "Known temporary outage",
        "expires_on": "2025-12-31",
    }
    org = {"org_abbrev": "X", "jobs": [], "scraper_error": ""}
    violations = validate_org_block(org, gates, today=date(2026, 2, 13))
    assert any("override expired" in item for item in violations)


def test_validate_org_block_flags_identical_description_lengths_when_more_than_two_jobs():
    gates = _base_gates()
    same = "word " * 60
    jobs = [
        {
            "index": 1,
            "url": "https://a/1",
            "fetch_seconds": 1.0,
            "enrich_status": "ok",
            "description": same,
        },
        {
            "index": 2,
            "url": "https://a/2",
            "fetch_seconds": 1.0,
            "enrich_status": "ok",
            "description": same,
        },
        {
            "index": 3,
            "url": "https://a/3",
            "fetch_seconds": 1.0,
            "enrich_status": "ok",
            "description": same,
        },
    ]
    org = {"org_abbrev": "X", "jobs": jobs, "scraper_error": ""}
    violations = validate_org_block(org, gates, today=date(2026, 2, 13))
    assert any("identical length" in item for item in violations)


def test_validate_org_block_flags_word_bounds_and_timeout():
    gates = _base_gates()
    jobs = [
        {
            "index": 1,
            "url": "https://a/1",
            "fetch_seconds": 12.5,
            "enrich_status": "ok",
            "description": "tiny text",
        }
    ]
    org = {"org_abbrev": "X", "jobs": jobs, "scraper_error": ""}
    violations = validate_org_block(org, gates, today=date(2026, 2, 13))
    assert any("word_count=" in item for item in violations)
    assert any("fetch_seconds=" in item for item in violations)


def test_validate_org_block_skips_word_checks_for_pdf_orgs():
    gates = _base_gates()
    same = "word " * 60
    jobs = [
        {
            "index": 1,
            "url": "https://a/1",
            "fetch_seconds": 1.0,
            "content_type": "html",
            "enrich_status": "ok",
            "description": same,
            "pdf_path": "",
        },
        {
            "index": 2,
            "url": "https://a/2",
            "fetch_seconds": 1.0,
            "content_type": "html",
            "enrich_status": "ok",
            "description": same,
            "pdf_path": "",
        },
        {
            "index": 3,
            "url": "https://a/3",
            "fetch_seconds": 1.0,
            "content_type": "html",
            "enrich_status": "ok",
            "description": same,
            "pdf_path": "",
        },
        {
            "index": 4,
            "url": "https://a/4",
            "fetch_seconds": 1.0,
            "content_type": "pdf",
            "enrich_status": "pdf",
            "description": "",
            "pdf_path": "pdfs/X/test.pdf",
        },
    ]
    org = {"org_abbrev": "X", "jobs": jobs, "scraper_error": ""}
    violations = validate_org_block(org, gates, today=date(2026, 2, 13))
    assert not any("identical length" in item for item in violations)
    assert not any("word_count=" in item for item in violations)


def test_validate_postings_payload_flags_missing_orgs():
    gates = _base_gates()
    violations = validate_postings_payload({"run_id": "test-run"}, gates)
    assert violations == ["payload: missing non-empty 'orgs' list"]


def test_format_violations_is_human_readable_list():
    rendered = format_violations(["a", "b"])
    assert rendered == "- a\n- b"
