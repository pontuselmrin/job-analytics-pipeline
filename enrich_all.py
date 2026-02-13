#!/usr/bin/env python3
"""CLI entry point for job description enrichment.

Usage:
    python enrich_all.py                    # all orgs
    python enrich_all.py --org NATO         # single org
    python enrich_all.py --org NATO --force # ignore cache
    python enrich_all.py --playwright       # use Playwright for detail pages
"""

import argparse
import sys
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).parent))

from enrichment.enrich import enrich_all, enrich_org
from enrichment.schema import extract_abbrev
from scraper_registry import find_scraper_by_abbrev, get_all_scrapers


def main():
    parser = argparse.ArgumentParser(
        description="Enrich scraped job listings with full descriptions"
    )
    parser.add_argument(
        "--org",
        type=str,
        help="Org abbreviation to enrich (e.g. NATO, OECD). Omit for all orgs.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-fetch all jobs, ignoring cached results",
    )
    parser.add_argument(
        "--playwright",
        action="store_true",
        help="Use Playwright for detail page fetching (for JS-heavy sites)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Reduce per-job console verbosity.",
    )
    parser.add_argument(
        "--log-ndjson",
        type=Path,
        help="Path to structured NDJSON run log.",
    )
    parser.add_argument(
        "--profile",
        action="store_true",
        help="Enable pyinstrument profiling and write HTML reports per org.",
    )
    parser.add_argument(
        "--max-orgs",
        type=int,
        help="Only process the first N organizations (all-org mode only).",
    )
    parser.add_argument(
        "--max-jobs",
        type=int,
        help="Only process the first N jobs per organization.",
    )
    parser.add_argument(
        "--job-timeout-seconds",
        type=float,
        default=30.0,
        help="Hard timeout per job detail fetch call.",
    )
    args = parser.parse_args()

    if args.org:
        result = find_scraper_by_abbrev(args.org)
        if not result:
            print(f"Error: No scraper found for org '{args.org}'")
            sys.exit(1)

        filename, org_name, url, is_pw_scraper = result
        org_abbrev = extract_abbrev(org_name)

        enrich_org(
            org_abbrev=org_abbrev,
            org_name=org_name,
            scraper_file=filename,
            is_playwright_scraper=is_pw_scraper,
            use_playwright_detail=args.playwright,
            force=args.force,
            verbose=not args.quiet,
            log_ndjson=args.log_ndjson,
            profile=args.profile,
            max_jobs=args.max_jobs,
            job_timeout_seconds=args.job_timeout_seconds,
        )
    else:
        registry = get_all_scrapers()
        results = enrich_all(
            registry,
            force=args.force,
            use_playwright_detail=args.playwright,
            verbose=not args.quiet,
            log_ndjson=args.log_ndjson,
            profile=args.profile,
            max_orgs=args.max_orgs,
            max_jobs=args.max_jobs,
            job_timeout_seconds=args.job_timeout_seconds,
        )

        # Summary
        print(f"\n{'='*60}")
        print("ENRICHMENT COMPLETE")
        print(f"{'='*60}")
        succeeded = [r for r in results if "error" not in r]
        failed = [r for r in results if "error" in r]
        total_jobs = sum(r.get("job_count", 0) for r in succeeded)

        print(f"  Orgs processed: {len(results)}")
        print(f"  Succeeded: {len(succeeded)}")
        print(f"  Failed: {len(failed)}")
        print(f"  Total jobs enriched: {total_jobs}")

        if failed:
            print("\nFailed orgs:")
            for r in failed:
                print(f"  - {r['org_name']}: {r['error']}")


if __name__ == "__main__":
    main()
