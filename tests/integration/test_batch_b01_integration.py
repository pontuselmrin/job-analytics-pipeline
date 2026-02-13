from pathlib import Path
import json

import pytest

from ops.harness.batches import BATCHES
from ops.harness.enrichment_matrix import run_matrix


@pytest.mark.integration
@pytest.mark.batch
@pytest.mark.network
def test_batch_b01_matrix_output_shape(tmp_path):
    orgs = set(BATCHES["B01"]["orgs"])
    results = run_matrix(include_orgs=orgs, sleep_seconds=0.0)

    assert results
    assert {r["org"] for r in results} == orgs

    out = tmp_path / "batch_b01_results.json"
    out.write_text(json.dumps(results, indent=2))

    for row in results:
        assert "org" in row
        assert "scraper_status" in row
        assert "enrich_status" in row
