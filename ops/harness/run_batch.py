#!/usr/bin/env python3
"""Run a review-gated batch and emit human-readable + JSON reports."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from ops.harness.batches import BATCHES
from ops.harness.enrichment_matrix import run_matrix

REPORTS_DIR = PROJECT_ROOT / "ops" / "reports" / "batches"


def _write_report(batch_id: str, results: list[dict], test_exit_code: int) -> tuple[Path, Path]:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).isoformat()

    json_path = REPORTS_DIR / f"{batch_id}.json"
    md_path = REPORTS_DIR / f"{batch_id}.md"

    payload = {
        "batch_id": batch_id,
        "generated_at": ts,
        "orgs": BATCHES[batch_id]["orgs"],
        "test_exit_code": test_exit_code,
        "results": results,
    }
    json_path.write_text(json.dumps(payload, indent=2))

    lines = [
        f"# Batch {batch_id} Review Report",
        "",
        f"Generated at: `{ts}`",
        f"Batch label: `{BATCHES[batch_id]['label']}`",
        f"Test exit code: `{test_exit_code}`",
        "",
        "## Orgs",
        ", ".join(BATCHES[batch_id]["orgs"]),
        "",
        "## Results",
        "| Org | Scraper Status | Enrich Status | Desc Len | Error |",
        "| --- | --- | --- | ---: | --- |",
    ]

    for row in sorted(results, key=lambda x: x["org"]):
        err = (row.get("scraper_error") or row.get("enrich_error") or "").replace("|", "/")[:120]
        lines.append(
            f"| {row['org']} | {row['scraper_status']} | {row['enrich_status']} | {row['desc_len']} | {err} |"
        )

    lines.extend([
        "",
        "## Human Review Gate",
        "1. Review this report and sample output quality.",
        "2. Commit batch changes only after approval.",
        "3. Start next batch manually.",
    ])

    md_path.write_text("\n".join(lines) + "\n")
    return md_path, json_path


def _run_pytest_for_batch(batch_id: str) -> int:
    batch_test_files = [
        f"tests/contract/test_batch_{batch_id.lower()}_contract.py",
        f"tests/integration/test_batch_{batch_id.lower()}_integration.py",
    ]
    cmd = ["uv", "run", "pytest", "tests/unit", *batch_test_files]
    proc = subprocess.run(cmd, cwd=PROJECT_ROOT)
    return proc.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one review-gated scraper batch.")
    parser.add_argument("--batch", default="B01", help="Batch id (e.g. B01)")
    args = parser.parse_args()

    batch_id = args.batch.upper()
    if batch_id not in BATCHES:
        print(f"Unknown batch '{batch_id}'. Available: {', '.join(sorted(BATCHES))}")
        return 2

    orgs = set(BATCHES[batch_id]["orgs"])
    print(f"Running batch {batch_id}: {BATCHES[batch_id]['label']}")
    print(f"Orgs: {', '.join(BATCHES[batch_id]['orgs'])}")

    test_exit_code = _run_pytest_for_batch(batch_id)
    results = run_matrix(include_orgs=orgs, sleep_seconds=0.0)

    md_path, json_path = _write_report(batch_id, results, test_exit_code)

    print(f"\nBatch report written to:\n- {md_path}\n- {json_path}")
    print("\nReview + commit checkpoint reached. Stop here for human review.")

    return test_exit_code


if __name__ == "__main__":
    raise SystemExit(main())
