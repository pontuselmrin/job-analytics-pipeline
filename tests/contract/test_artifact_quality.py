import os
import json
from pathlib import Path

import pytest

from tests.fixtures.quality_gates import (
    format_violations,
    load_quality_gates,
    validate_postings_payload,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUNS_DIR = PROJECT_ROOT / "ops" / "runs"


def _run_ids():
    one = os.environ.get("RUN_ID", "").strip()
    if one:
        return [one]
    return []


def _load_postings_payload(run_id: str) -> dict:
    """Reassemble payload from per-org JSON files in postings/."""
    postings_dir = RUNS_DIR / run_id / "postings"
    assert postings_dir.is_dir(), f"Missing postings dir: {postings_dir}"
    orgs = []
    for p in sorted(postings_dir.glob("*.json")):
        orgs.append(json.loads(p.read_text()))
    return {"run_id": run_id, "orgs": orgs}


@pytest.mark.contract
@pytest.mark.parametrize("run_id", _run_ids())
def test_postings_artifact_quality(run_id):
    payload = _load_postings_payload(run_id)

    gates = load_quality_gates()
    violations = validate_postings_payload(payload, gates)
    assert not violations, (
        f"{run_id} quality gate violations:\n{format_violations(violations)}"
    )


@pytest.mark.contract
def test_requires_run_id_env():
    if os.environ.get("RUN_ID", "").strip():
        return
    pytest.skip("Set RUN_ID to run artifact quality checks for a specific run.")
