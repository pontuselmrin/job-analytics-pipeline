from pathlib import Path
import json

import pytest

from ops.harness.batches import BATCHES
from ops.harness.enrichment_matrix import run_matrix
from ops.harness.run_batch import _collect_postings_payload


@pytest.mark.integration
@pytest.mark.batch
@pytest.mark.network
def test_batch_b02_matrix_output_shape(tmp_path):
    orgs = set(BATCHES["B02"]["orgs"])
    results = run_matrix(include_orgs=orgs, sleep_seconds=0.0)

    assert results
    assert {r["org"] for r in results} == orgs

    out = tmp_path / "batch_b02_results.json"
    out.write_text(json.dumps(results, indent=2))

    for row in results:
        assert "org" in row
        assert "scraper_status" in row
        assert "enrich_status" in row


@pytest.mark.integration
@pytest.mark.batch
@pytest.mark.network
def test_batch_b02_postings_schema_has_fetch_seconds():
    payload = _collect_postings_payload("B02")
    assert payload.get("batch_id") == "B02"
    assert payload.get("orgs")
    for org_block in payload["orgs"]:
        assert "org_abbrev" in org_block
        assert "jobs" in org_block
        for job in org_block["jobs"]:
            assert "fetch_seconds" in job

