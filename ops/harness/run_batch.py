#!/usr/bin/env python3
"""Run a review-gated batch and emit human-readable + JSON reports."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scrapers"))
sys.path.insert(0, str(PROJECT_ROOT / "scrapers_playwright"))

from ops.harness.batches import BATCHES
from ops.harness.enrichment_matrix import run_matrix
from enrichment.fetcher import classify_fetch_error, extract_html_description, fetch_job_content
from enrichment.schema import extract_abbrev
from scraper_registry import SCRAPER_INFO, SCRAPER_INFO_PW

REPORTS_DIR = PROJECT_ROOT / "ops" / "reports" / "batches"


def _load_and_scrape(scraper_path: Path) -> list[dict]:
    parent = str(scraper_path.parent)
    if parent not in sys.path:
        sys.path.insert(0, parent)
    spec = importlib.util.spec_from_file_location("scraper", scraper_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.scrape()


def _find_scraper_for_org(org_abbrev: str) -> tuple[Path, str, bool]:
    for filename, (org_name, _url) in SCRAPER_INFO.items():
        if extract_abbrev(org_name).upper() == org_abbrev.upper():
            return PROJECT_ROOT / "scrapers" / filename, org_name, False
    for filename, (org_name, _url) in SCRAPER_INFO_PW.items():
        if extract_abbrev(org_name).upper() == org_abbrev.upper():
            return PROJECT_ROOT / "scrapers_playwright" / filename, org_name, True
    raise KeyError(f"No scraper found for org {org_abbrev}")


def _collect_postings_payload(batch_id: str) -> dict:
    ts = datetime.now(timezone.utc).isoformat()
    payload: dict = {
        "batch_id": batch_id,
        "generated_at": ts,
        "orgs": [],
    }

    for org in BATCHES[batch_id]["orgs"]:
        scraper_path, org_name, is_pw = _find_scraper_for_org(org)
        org_block = {
            "org_abbrev": org,
            "org_name": org_name,
            "scraper_file": str(scraper_path.relative_to(PROJECT_ROOT)),
            "is_playwright_scraper": is_pw,
            "jobs": [],
            "scraper_error": "",
        }

        try:
            jobs = _load_and_scrape(scraper_path)
        except Exception as exc:  # noqa: BLE001
            org_block["scraper_error"] = str(exc)
            payload["orgs"].append(org_block)
            continue

        for idx, job in enumerate(jobs, start=1):
            title = (job.get("title") or "").strip()
            url = (job.get("url") or "").strip()
            item = {
                "index": idx,
                "title": title,
                "url": url,
                "content_type": "",
                "enrich_status": "",
                "status_reason": "",
                "description": "",
                "pdf_path": "",
                "fetch_seconds": 0.0,
                "error": "",
            }

            if not url:
                item["enrich_status"] = "no_detail_url"
                item["status_reason"] = "missing_url"
                org_block["jobs"].append(item)
                continue

            started = time.perf_counter()
            try:
                result = fetch_job_content(
                    url=url,
                    org_abbrev=org,
                    title=title or f"job-{idx}",
                    use_playwright=is_pw,
                )
                item["fetch_seconds"] = round(time.perf_counter() - started, 3)
                item["content_type"] = result.get("content_type", "")
                item["enrich_status"] = result.get("enrich_status", "")
                item["status_reason"] = result.get("status_reason", "")
                item["description"] = result.get("description", "")
                item["pdf_path"] = result.get("pdf_path", "")
            except Exception as exc:  # noqa: BLE001
                item["fetch_seconds"] = round(time.perf_counter() - started, 3)
                status, reason = classify_fetch_error(exc)
                # Some Playwright-only pages fail fast in HTTP preflight; recover by
                # extracting directly with Playwright.
                if is_pw:
                    try:
                        started = time.perf_counter()
                        desc = extract_html_description(url, use_playwright=True)
                        item["fetch_seconds"] = round(time.perf_counter() - started, 3)
                        if len(desc) > 100:
                            item["content_type"] = "html"
                            item["enrich_status"] = "ok"
                            item["status_reason"] = "playwright_fallback"
                            item["description"] = desc
                            org_block["jobs"].append(item)
                            continue
                    except Exception:
                        pass

                item["enrich_status"] = status
                item["status_reason"] = reason
                item["error"] = str(exc)

            org_block["jobs"].append(item)

        payload["orgs"].append(org_block)

    return payload


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
    postings_payload = _collect_postings_payload(batch_id)

    md_path, json_path = _write_report(batch_id, results, test_exit_code)
    postings_path = _write_postings_json(batch_id, postings_payload)

    print(f"\nBatch report written to:\n- {md_path}\n- {json_path}\n- {postings_path}")
    print("\nReview + commit checkpoint reached. Stop here for human review.")

    return test_exit_code


if __name__ == "__main__":
    raise SystemExit(main())
