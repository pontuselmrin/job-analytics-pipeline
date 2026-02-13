import importlib.util
import sys
from pathlib import Path

import pytest

from enrichment.fetcher import classify_fetch_error, fetch_job_content
from enrichment.schema import extract_abbrev
from ops.harness.batches import BATCHES
from scraper_registry import SCRAPER_INFO, SCRAPER_INFO_PW

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _load_and_run(filepath: Path):
    parent = str(filepath.parent)
    if parent not in sys.path:
        sys.path.insert(0, parent)
    spec = importlib.util.spec_from_file_location("scraper", filepath)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.scrape()


def _find_scraper(org_abbrev: str):
    for filename, (org_name, _url) in SCRAPER_INFO.items():
        if extract_abbrev(org_name).upper() == org_abbrev.upper():
            return PROJECT_ROOT / "scrapers" / filename, org_name, False
    for filename, (org_name, _url) in SCRAPER_INFO_PW.items():
        if extract_abbrev(org_name).upper() == org_abbrev.upper():
            return PROJECT_ROOT / "scrapers_playwright" / filename, org_name, True
    raise KeyError(f"No scraper found for {org_abbrev}")


@pytest.mark.contract
@pytest.mark.batch
@pytest.mark.network
@pytest.mark.parametrize("org", BATCHES["B03"]["orgs"])
def test_batch_b03_contract(org):
    filepath, org_name, _is_pw = _find_scraper(org)
    jobs = _load_and_run(filepath)

    assert jobs, f"{org} returned no jobs"
    sample = jobs[0]
    assert sample.get("title", "").strip(), f"{org} sample title is empty"

    url = sample.get("url", "")
    assert url, f"{org} sample URL is empty"

    try:
        result = fetch_job_content(url, org_abbrev=org, title=sample.get("title", "untitled"))
    except Exception as exc:  # noqa: BLE001
        status, _reason = classify_fetch_error(exc)
        assert status in {"blocked_source", "broken_link"}, f"{org} unexpected fetch error: {exc}"
        return

    assert result.get("enrich_status") in {
        "ok",
        "pdf",
        "short_content",
        "js_required",
        "no_detail_url",
    }, f"{org} unexpected enrich_status: {result}"

