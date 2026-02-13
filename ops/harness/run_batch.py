#!/usr/bin/env python3
"""Run a review-gated batch and emit human-readable + JSON reports."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scrapers"))
sys.path.insert(0, str(PROJECT_ROOT / "scrapers_playwright"))

from ops.harness.batches import BATCHES
from ops.harness.enrichment_matrix import run_matrix
from enrichment.runner import (
    EventLogger,
    RunnerConfig,
    collect_postings_org_via_runner,
    default_ndjson_path,
    default_run_id,
)
from enrichment.schema import extract_abbrev
from scraper_registry import SCRAPER_INFO, SCRAPER_INFO_PW

REPORTS_DIR = PROJECT_ROOT / "ops" / "reports" / "batches"

def _find_scraper_for_org(org_abbrev: str) -> tuple[Path, str, bool]:
    for filename, (org_name, _url) in SCRAPER_INFO.items():
        if extract_abbrev(org_name).upper() == org_abbrev.upper():
            return PROJECT_ROOT / "scrapers" / filename, org_name, False
    for filename, (org_name, _url) in SCRAPER_INFO_PW.items():
        if extract_abbrev(org_name).upper() == org_abbrev.upper():
            return PROJECT_ROOT / "scrapers_playwright" / filename, org_name, True
    raise KeyError(f"No scraper found for org {org_abbrev}")


def _collect_postings_payload(
    batch_id: str,
    *,
    orgs: list[str] | None = None,
    verbose: bool = True,
    log_ndjson: Path | None = None,
    run_id: str | None = None,
    profile: bool = False,
    max_jobs_per_org: int | None = None,
    job_timeout_seconds: float = 30.0,
) -> dict:
    ts = datetime.now(timezone.utc).isoformat()
    local_run_id = run_id or default_run_id(f"batch-{batch_id.lower()}")
    ndjson_path = log_ndjson or default_ndjson_path(local_run_id)
    cfg = RunnerConfig(
        run_id=local_run_id,
        batch_id=batch_id,
        verbose=verbose,
        ndjson_path=ndjson_path,
        profile=profile,
    )
    logger = EventLogger(cfg)
    payload: dict = {
        "batch_id": batch_id,
        "generated_at": ts,
        "run_id": local_run_id,
        "run_log": str(ndjson_path),
        "orgs": [],
    }

    try:
        target_orgs = orgs if orgs else BATCHES[batch_id]["orgs"]
        for org in target_orgs:
            scraper_path, org_name, is_pw = _find_scraper_for_org(org)
            org_block = collect_postings_org_via_runner(
                org_abbrev=org,
                org_name=org_name,
                scraper_path=scraper_path,
                is_playwright_scraper=is_pw,
                logger=logger,
                profile=profile,
                max_jobs=max_jobs_per_org,
                job_timeout_seconds=job_timeout_seconds,
            )
            payload["orgs"].append(org_block)
        return payload
    finally:
        logger.close()


def _write_report(batch_id: str, orgs: list[str], results: list[dict], test_exit_code: int) -> tuple[Path, Path]:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).isoformat()

    json_path = REPORTS_DIR / f"{batch_id}.json"
    md_path = REPORTS_DIR / f"{batch_id}.md"

    payload = {
        "batch_id": batch_id,
        "generated_at": ts,
        "orgs": orgs,
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
        ", ".join(orgs),
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


def _write_postings_json(batch_id: str, payload: dict) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORTS_DIR / f"{batch_id}_postings.json"
    path.write_text(json.dumps(payload, indent=2))
    return path


def _run_pytest_for_batch(batch_id: str) -> int:
    batch_test_files = [
        "tests/contract/test_batch_quality_gates.py",
        f"tests/contract/test_batch_{batch_id.lower()}_contract.py",
        f"tests/integration/test_batch_{batch_id.lower()}_integration.py",
    ]
    cmd = ["uv", "run", "pytest", "tests/unit", *batch_test_files]
    env = dict(**os.environ, BATCH_ID=batch_id)
    proc = subprocess.run(cmd, cwd=PROJECT_ROOT, env=env)
    return proc.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one review-gated scraper batch.")
    parser.add_argument("--batch", default="B01", help="Batch id (e.g. B01)")
    parser.add_argument("--org", action="append", default=[], help="Run only specified org abbrev(s) within the batch.")
    parser.add_argument("--quiet", action="store_true", help="Reduce per-job console verbosity.")
    parser.add_argument("--log-ndjson", type=Path, help="Path to structured NDJSON run log.")
    parser.add_argument("--profile", action="store_true", help="Enable pyinstrument profiling and write HTML reports.")
    parser.add_argument("--max-jobs-per-org", type=int, help="Only process the first N jobs per org in postings/enrichment.")
    parser.add_argument("--job-timeout-seconds", type=float, default=30.0, help="Hard timeout per job detail fetch call.")
    parser.add_argument("--skip-tests", action="store_true", help="Skip pytest pre-checks for faster iterative org debugging.")
    args = parser.parse_args()

    batch_id = args.batch.upper()
    if batch_id not in BATCHES:
        print(f"Unknown batch '{batch_id}'. Available: {', '.join(sorted(BATCHES))}")
        return 2

    selected_orgs = [o.strip().upper() for o in args.org if o.strip()]
    batch_orgs = [o.upper() for o in BATCHES[batch_id]["orgs"]]
    if selected_orgs:
        invalid = [o for o in selected_orgs if o not in batch_orgs]
        if invalid:
            print(f"Invalid --org for {batch_id}: {', '.join(invalid)}")
            return 2
        orgs_list = selected_orgs
    else:
        orgs_list = batch_orgs
    orgs = set(orgs_list)
    print(f"Running batch {batch_id}: {BATCHES[batch_id]['label']}")
    print(f"Orgs: {', '.join(orgs_list)}")

    test_exit_code = 0 if args.skip_tests else _run_pytest_for_batch(batch_id)
    results = run_matrix(include_orgs=orgs, sleep_seconds=0.0)
    postings_payload = _collect_postings_payload(
        batch_id,
        orgs=orgs_list,
        verbose=not args.quiet,
        log_ndjson=args.log_ndjson,
        profile=args.profile,
        max_jobs_per_org=args.max_jobs_per_org,
        job_timeout_seconds=args.job_timeout_seconds,
    )

    md_path, json_path = _write_report(batch_id, orgs_list, results, test_exit_code)
    postings_path = _write_postings_json(batch_id, postings_payload)

    print(f"\nBatch report written to:\n- {md_path}\n- {json_path}\n- {postings_path}")
    if postings_payload.get("run_log"):
        print(f"- {postings_payload['run_log']} (NDJSON run log)")
    print("\nReview + commit checkpoint reached. Stop here for human review.")

    return test_exit_code


if __name__ == "__main__":
    raise SystemExit(main())
