#!/usr/bin/env python3
"""Run scrapers for specified orgs and emit reports from a single fetch pass."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scrapers"))
sys.path.insert(0, str(PROJECT_ROOT / "scrapers_playwright"))

from enrichment.runner import (  # noqa: E402
    EventLogger,
    RunnerConfig,
    collect_postings_org_via_runner,
    default_ndjson_path,
    default_run_id,
)
from enrichment.schema import extract_abbrev  # noqa: E402
from scraper_registry import SCRAPER_INFO, SCRAPER_INFO_PW, find_scraper_by_abbrev  # noqa: E402

RUNS_DIR = PROJECT_ROOT / "ops" / "runs"


def _find_scraper_for_org(org_abbrev: str) -> tuple[Path, str, bool]:
    for filename, (org_name, _url) in SCRAPER_INFO.items():
        if extract_abbrev(org_name).upper() == org_abbrev.upper():
            return PROJECT_ROOT / "scrapers" / filename, org_name, False
    for filename, (org_name, _url) in SCRAPER_INFO_PW.items():
        if extract_abbrev(org_name).upper() == org_abbrev.upper():
            return PROJECT_ROOT / "scrapers_playwright" / filename, org_name, True
    raise KeyError(f"No scraper found for org {org_abbrev}")


def _resolve_orgs(args) -> list[str]:
    """Resolve org list from --all or --org flags."""
    if args.all:
        all_abbrevs = []
        for _filename, (org_name, _url) in SCRAPER_INFO.items():
            all_abbrevs.append(extract_abbrev(org_name).upper())
        for _filename, (org_name, _url) in SCRAPER_INFO_PW.items():
            all_abbrevs.append(extract_abbrev(org_name).upper())
        return sorted(set(all_abbrevs))

    orgs = []
    for abbrev in args.org:
        abbrev = abbrev.strip().upper()
        result = find_scraper_by_abbrev(abbrev)
        if result is None:
            print(f"Error: unknown org abbreviation '{abbrev}'")
            sys.exit(2)
        orgs.append(abbrev)
    return orgs


def _collect_postings_payload(
    orgs: list[str],
    *,
    verbose: bool = True,
    live_events: bool = False,
    log_ndjson: Path | None = None,
    run_id: str | None = None,
    profile: bool = False,
    max_jobs_per_org: int | None = None,
    job_timeout_seconds: float = 30.0,
    parallel_orgs: int = 1,
) -> dict:
    ts = datetime.now(timezone.utc).isoformat()
    local_run_id = run_id or default_run_id("run")
    ndjson_path = log_ndjson or default_ndjson_path(local_run_id)
    cfg = RunnerConfig(
        run_id=local_run_id,
        verbose=verbose,
        live_events=live_events,
        ndjson_path=ndjson_path,
        profile=profile,
    )
    logger = EventLogger(cfg)
    payload: dict = {
        "run_id": local_run_id,
        "generated_at": ts,
        "run_log": str(ndjson_path),
        "orgs": [],
    }

    def _persist_org_block(org_block: dict) -> None:
        _write_org_postings_json(local_run_id, org_block)

    try:
        if parallel_orgs <= 1 or len(orgs) <= 1:
            for org in orgs:
                scraper_path, org_name, is_pw = _find_scraper_for_org(org)
                org_abbrev = extract_abbrev(org_name)
                org_block = collect_postings_org_via_runner(
                    org_abbrev=org_abbrev,
                    org_name=org_name,
                    scraper_path=scraper_path,
                    is_playwright_scraper=is_pw,
                    logger=logger,
                    profile=profile,
                    max_jobs=max_jobs_per_org,
                    job_timeout_seconds=job_timeout_seconds,
                )
                payload["orgs"].append(org_block)
                _persist_org_block(org_block)
        else:
            indexed = list(enumerate(orgs))
            out_by_index: dict[int, dict] = {}

            def _run_one(pair: tuple[int, str]) -> tuple[int, dict]:
                i, org = pair
                scraper_path, org_name, is_pw = _find_scraper_for_org(org)
                org_abbrev = extract_abbrev(org_name)
                org_block = collect_postings_org_via_runner(
                    org_abbrev=org_abbrev,
                    org_name=org_name,
                    scraper_path=scraper_path,
                    is_playwright_scraper=is_pw,
                    logger=logger,
                    profile=profile,
                    max_jobs=max_jobs_per_org,
                    job_timeout_seconds=job_timeout_seconds,
                )
                return i, org_block

            with ThreadPoolExecutor(max_workers=parallel_orgs) as pool:
                futures = [pool.submit(_run_one, pair) for pair in indexed]
                for fut in as_completed(futures):
                    i, org_block = fut.result()
                    out_by_index[i] = org_block
                    _persist_org_block(org_block)

            for i in range(len(orgs)):
                payload["orgs"].append(out_by_index[i])
        return payload
    finally:
        logger.close()


def _results_from_postings(payload: dict) -> list[dict]:
    rows: list[dict] = []
    for org in payload.get("orgs", []):
        org_abbrev = org.get("org_abbrev", "")
        scraper_error = org.get("scraper_error", "")
        jobs = org.get("jobs", [])

        if scraper_error:
            rows.append(
                {
                    "org": org_abbrev,
                    "scraper_status": "error",
                    "enrich_status": "skipped",
                    "desc_len": 0,
                    "scraper_error": scraper_error,
                    "enrich_error": "",
                }
            )
            continue

        if not jobs:
            rows.append(
                {
                    "org": org_abbrev,
                    "scraper_status": "empty",
                    "enrich_status": "skipped",
                    "desc_len": 0,
                    "scraper_error": "",
                    "enrich_error": "",
                }
            )
            continue

        statuses = [j.get("enrich_status", "") for j in jobs]
        enrich_status = (
            "ok" if "ok" in statuses else (statuses[0] if statuses else "skipped")
        )
        desc_len = max((len((j.get("description") or "")) for j in jobs), default=0)
        enrich_error = next((j.get("error", "") for j in jobs if j.get("error")), "")
        rows.append(
            {
                "org": org_abbrev,
                "scraper_status": "ok",
                "enrich_status": enrich_status,
                "desc_len": desc_len,
                "scraper_error": "",
                "enrich_error": enrich_error,
            }
        )
    return rows


def _write_report(
    run_id: str, orgs: list[str], results: list[dict], test_exit_code: int
) -> tuple[Path, Path]:
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).isoformat()

    json_path = run_dir / "report.json"
    md_path = run_dir / "report.md"

    payload = {
        "run_id": run_id,
        "generated_at": ts,
        "orgs": orgs,
        "test_exit_code": test_exit_code,
        "results": results,
    }
    json_path.write_text(json.dumps(payload, indent=2))

    lines = [
        "# Run Report",
        "",
        f"Generated at: `{ts}`",
        f"Run ID: `{run_id}`",
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
        err = (row.get("scraper_error") or row.get("enrich_error") or "").replace(
            "|", "/"
        )[:120]
        lines.append(
            f"| {row['org']} | {row['scraper_status']} | {row['enrich_status']} | {row['desc_len']} | {err} |"
        )

    lines.extend(
        [
            "",
            "## Review Gate",
            "1. Review this report and sample output quality.",
            "2. Commit changes only after approval.",
        ]
    )

    md_path.write_text("\n".join(lines) + "\n")
    return md_path, json_path


def _write_org_postings_json(run_id: str, org_block: dict) -> Path:
    run_dir = RUNS_DIR / run_id
    postings_dir = run_dir / "postings"
    postings_dir.mkdir(parents=True, exist_ok=True)
    org_abbrev = (org_block.get("org_abbrev") or "UNKNOWN").upper()
    path = postings_dir / f"{org_abbrev}.json"
    path.write_text(json.dumps(org_block, indent=2))
    return path


def _run_pytest(run_id: str) -> int:
    cmd = [
        "uv",
        "run",
        "pytest",
        "tests/unit",
        "tests/contract/test_artifact_quality.py",
        "tests/integration/test_artifact_schema.py",
    ]
    env = dict(**os.environ, RUN_ID=run_id)
    proc = subprocess.run(cmd, cwd=PROJECT_ROOT, env=env)
    return proc.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Run scrapers for specified orgs.")
    parser.add_argument(
        "--org", action="append", default=[], help="Org abbreviation (repeatable)."
    )
    parser.add_argument(
        "--all", action="store_true", help="Run all orgs from the registry."
    )
    parser.add_argument(
        "--quiet", action="store_true", help="Reduce per-job console verbosity."
    )
    parser.add_argument(
        "--live-events",
        action="store_true",
        help="Print each structured run event as JSON in real time.",
    )
    parser.add_argument(
        "--log-ndjson", type=Path, help="Path to structured NDJSON run log."
    )
    parser.add_argument(
        "--profile",
        action="store_true",
        help="Enable pyinstrument profiling and write HTML reports.",
    )
    parser.add_argument(
        "--max-jobs-per-org",
        type=int,
        help="Only process the first N jobs per org in postings/enrichment.",
    )
    parser.add_argument(
        "--job-timeout-seconds",
        type=float,
        default=30.0,
        help="Hard timeout per job detail fetch call.",
    )
    parser.add_argument(
        "--parallel-orgs",
        type=int,
        default=1,
        help="Number of organizations to process in parallel.",
    )
    parser.add_argument(
        "--skip-tests",
        action="store_true",
        help="Skip pytest pre-checks for faster iterative debugging.",
    )
    args = parser.parse_args()

    if not args.all and not args.org:
        parser.error("Provide --org (one or more) or --all.")

    orgs_list = _resolve_orgs(args)
    print(f"Running {len(orgs_list)} org(s): {', '.join(orgs_list)}")

    postings_payload = _collect_postings_payload(
        orgs_list,
        verbose=not args.quiet,
        live_events=args.live_events,
        log_ndjson=args.log_ndjson,
        profile=args.profile,
        max_jobs_per_org=args.max_jobs_per_org,
        job_timeout_seconds=args.job_timeout_seconds,
        parallel_orgs=max(1, args.parallel_orgs),
    )

    run_id = postings_payload["run_id"]
    postings_dir = RUNS_DIR / run_id / "postings"

    test_exit_code = 0 if args.skip_tests else _run_pytest(run_id)
    results = _results_from_postings(postings_payload)
    md_path, json_path = _write_report(run_id, orgs_list, results, test_exit_code)

    print(
        f"\nRun report written to:\n- {md_path}\n- {json_path}\n"
        f"- {postings_dir} (per-org JSON files)"
    )
    if postings_payload.get("run_log"):
        print(f"- {postings_payload['run_log']} (NDJSON run log)")
    print("\nReview checkpoint reached. Stop here for human review.")

    return test_exit_code


if __name__ == "__main__":
    raise SystemExit(main())
