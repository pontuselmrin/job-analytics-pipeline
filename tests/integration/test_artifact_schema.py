import json
import os
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUNS_DIR = PROJECT_ROOT / "ops" / "runs"


def _run_ids():
    one = os.environ.get("RUN_ID", "").strip()
    if one:
        return [one]
    return []


def _load_org_blocks(run_id: str) -> list[dict]:
    """Load per-org JSON files from postings/."""
    postings_dir = RUNS_DIR / run_id / "postings"
    assert postings_dir.is_dir(), f"Missing postings dir: {postings_dir}"
    orgs = []
    for p in sorted(postings_dir.glob("*.json")):
        orgs.append(json.loads(p.read_text()))
    return orgs


@pytest.mark.integration
@pytest.mark.parametrize("run_id", _run_ids())
def test_postings_artifact_schema(run_id):
    orgs = _load_org_blocks(run_id)
    assert orgs, f"No per-org JSON files found in postings/ for {run_id}"

    for org in orgs:
        assert isinstance(org.get("org_abbrev"), str)
        assert isinstance(org.get("org_name"), str)
        assert isinstance(org.get("scraper_file"), str)
        assert isinstance(org.get("is_playwright_scraper"), bool)
        assert isinstance(org.get("scraper_error"), str)
        assert isinstance(org.get("jobs"), list)
        for job in org["jobs"]:
            assert isinstance(job.get("index"), int)
            assert isinstance(job.get("title"), str)
            assert isinstance(job.get("url"), str)
            assert isinstance(job.get("content_type"), str)
            assert isinstance(job.get("enrich_status"), str)
            assert isinstance(job.get("status_reason"), str)
            assert isinstance(job.get("description"), str)
            assert isinstance(job.get("pdf_path"), str)
            assert isinstance(job.get("fetch_seconds"), (int, float))
            assert isinstance(job.get("error"), str)


@pytest.mark.integration
def test_requires_run_id_env():
    if os.environ.get("RUN_ID", "").strip():
        return
    pytest.skip("Set RUN_ID to run artifact schema checks for a specific run.")
