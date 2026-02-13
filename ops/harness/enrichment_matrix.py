#!/usr/bin/env python3
"""Test enrichment extraction for every scraper.

For each org: run scraper, take the first job URL, try to extract
a description, and report whether it worked.
"""

import importlib.util
import json
import sys
import time
import argparse
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPORT_PATH = PROJECT_ROOT / "ops" / "reports" / "enrichment" / "enrichment_matrix_latest.json"

sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scrapers"))
sys.path.insert(0, str(PROJECT_ROOT / "scrapers_playwright"))

from enrichment.fetcher import extract_html_description, detect_content_type
from enrichment.schema import extract_abbrev
from scraper_registry import SCRAPER_INFO, SCRAPER_INFO_PW


def load_and_run(filepath):
    parent = str(filepath.parent)
    if parent not in sys.path:
        sys.path.insert(0, parent)
    spec = importlib.util.spec_from_file_location("scraper", filepath)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.scrape()


def test_one(scraper_file, org_name, is_pw):
    base_dir = PROJECT_ROOT / ("scrapers_playwright" if is_pw else "scrapers")
    filepath = base_dir / scraper_file
    abbrev = extract_abbrev(org_name)

    # Step 1: run scraper
    try:
        jobs = load_and_run(filepath)
    except Exception as e:
        return {"org": abbrev, "scraper_status": "error", "scraper_error": str(e),
                "job_count": 0, "sample_url": "", "content_type": "", "desc_len": 0,
                "enrich_status": "skipped", "enrich_error": ""}

    if not jobs:
        return {"org": abbrev, "scraper_status": "empty", "scraper_error": "",
                "job_count": 0, "sample_url": "", "content_type": "", "desc_len": 0,
                "enrich_status": "skipped", "enrich_error": ""}

    sample = jobs[0]
    url = sample.get("url", "")
    result = {"org": abbrev, "scraper_status": "ok", "scraper_error": "",
              "job_count": len(jobs), "sample_url": url, "content_type": "",
              "desc_len": 0, "enrich_status": "", "enrich_error": ""}

    if not url:
        result["enrich_status"] = "no_url"
        return result

    # Step 2: detect content type
    try:
        ct = detect_content_type(url)
        result["content_type"] = ct
    except Exception as e:
        result["content_type"] = "detect_error"
        result["enrich_status"] = "error"
        result["enrich_error"] = str(e)
        return result

    # Step 3: if HTML, try extraction
    if ct == "pdf":
        result["enrich_status"] = "pdf"
        return result

    try:
        desc = extract_html_description(url)
        result["desc_len"] = len(desc)
        result["enrich_status"] = "ok" if len(desc) > 100 else "short"
        if len(desc) <= 100:
            result["enrich_error"] = repr(desc[:100])
    except Exception as e:
        result["enrich_status"] = "error"
        result["enrich_error"] = str(e)

    return result


def run_matrix(include_orgs: set[str] | None = None, sleep_seconds: float = 0.5) -> list[dict]:
    results = []

    all_scrapers = []
    for f, (name, url) in SCRAPER_INFO.items():
        all_scrapers.append((f, name, False))
    for f, (name, url) in SCRAPER_INFO_PW.items():
        all_scrapers.append((f, name, True))

    if include_orgs:
        include_orgs_norm = {org.strip().upper() for org in include_orgs if org.strip()}
        all_scrapers = [
            (f, name, is_pw)
            for (f, name, is_pw) in all_scrapers
            if extract_abbrev(name).upper() in include_orgs_norm
        ]

    total = len(all_scrapers)
    for i, (scraper_file, org_name, is_pw) in enumerate(all_scrapers):
        abbrev = extract_abbrev(org_name)
        pw_tag = " [PW]" if is_pw else ""
        print(f"[{i+1}/{total}] {abbrev}{pw_tag}...", end=" ", flush=True)

        r = test_one(scraper_file, org_name, is_pw)
        results.append(r)

        status_parts = [f"scraper={r['scraper_status']}"]
        if r["job_count"]:
            status_parts.append(f"jobs={r['job_count']}")
        if r["content_type"]:
            status_parts.append(f"type={r['content_type']}")
        if r["desc_len"]:
            status_parts.append(f"desc={r['desc_len']}ch")
        status_parts.append(f"enrich={r['enrich_status']}")
        if r["scraper_error"]:
            status_parts.append(f"err={r['scraper_error'][:60]}")
        elif r["enrich_error"]:
            status_parts.append(f"err={r['enrich_error'][:60]}")
        print(" | ".join(status_parts))

        time.sleep(sleep_seconds)

    return results


def print_summary(results: list[dict]) -> None:
    # Summary
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")

    scraper_ok = [r for r in results if r["scraper_status"] in ("ok",)]
    scraper_empty = [r for r in results if r["scraper_status"] == "empty"]
    scraper_err = [r for r in results if r["scraper_status"] == "error"]
    print(f"Scrapers: {len(scraper_ok)} ok, {len(scraper_empty)} empty, {len(scraper_err)} error")

    enrich_ok = [r for r in results if r["enrich_status"] == "ok"]
    enrich_short = [r for r in results if r["enrich_status"] == "short"]
    enrich_pdf = [r for r in results if r["enrich_status"] == "pdf"]
    enrich_err = [r for r in results if r["enrich_status"] == "error"]
    enrich_skip = [r for r in results if r["enrich_status"] in ("skipped", "no_url")]
    print(f"Enrichment: {len(enrich_ok)} ok, {len(enrich_pdf)} pdf, "
          f"{len(enrich_short)} short, {len(enrich_err)} error, {len(enrich_skip)} skipped")

    if enrich_short or enrich_err:
        print(f"\n--- NEEDS ATTENTION ---")
        for r in enrich_short + enrich_err:
            print(f"  {r['org']}: enrich={r['enrich_status']} "
                  f"type={r['content_type']} err={r['enrich_error'][:80]}")


def parse_args():
    parser = argparse.ArgumentParser(description="Run enrichment extraction matrix across scrapers.")
    parser.add_argument(
        "--org",
        action="append",
        default=[],
        help="Organization abbreviation to include. Repeat for multiple orgs (e.g. --org EDA --org ESMA).",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_REPORT_PATH,
        help=f"Output JSON path (default: {DEFAULT_REPORT_PATH})",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=0.5,
        help="Seconds to sleep between org runs.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    include_orgs = set(args.org) if args.org else None
    results = run_matrix(include_orgs=include_orgs, sleep_seconds=args.sleep)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved matrix results to {args.out}")
    print_summary(results)


if __name__ == "__main__":
    main()
