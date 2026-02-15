"""Orchestrator: run scrapers and enrich their output with job descriptions."""

from pathlib import Path

from .runner import (
    EventLogger,
    RunnerConfig,
    default_ndjson_path,
    default_run_id,
    enrich_org_via_runner,
)
from .schema import extract_abbrev


def enrich_org(
    org_abbrev: str,
    org_name: str,
    scraper_file: str,
    is_playwright_scraper: bool = False,
    use_playwright_detail: bool = False,
    force: bool = False,
    verbose: bool = True,
    log_ndjson: Path | None = None,
    run_id: str | None = None,
    profile: bool = False,
    max_jobs: int | None = None,
    job_timeout_seconds: float = 30.0,
) -> dict:
    """Scrape and enrich all jobs for a single organization."""
    print(f"\n{'=' * 60}")
    print(f"Enriching: {org_name} [{org_abbrev}]")
    print(f"{'=' * 60}")

    local_run_id = run_id or default_run_id(f"org-{org_abbrev.lower()}")
    ndjson_path = log_ndjson or default_ndjson_path(local_run_id)
    cfg = RunnerConfig(
        run_id=local_run_id,
        batch_id="",
        verbose=verbose,
        ndjson_path=ndjson_path,
        profile=profile,
    )
    logger = EventLogger(cfg)
    try:
        result = enrich_org_via_runner(
            org_abbrev=org_abbrev,
            org_name=org_name,
            scraper_file=scraper_file,
            is_playwright_scraper=is_playwright_scraper,
            use_playwright_detail=use_playwright_detail,
            force=force,
            logger=logger,
            profile=profile,
            max_jobs=max_jobs,
            job_timeout_seconds=job_timeout_seconds,
        )
        print(f"\n  Run log: {ndjson_path}")
        return result
    finally:
        logger.close()


def enrich_all(
    registry: dict,
    force: bool = False,
    use_playwright_detail: bool = False,
    verbose: bool = True,
    log_ndjson: Path | None = None,
    profile: bool = False,
    max_orgs: int | None = None,
    max_jobs: int | None = None,
    job_timeout_seconds: float = 30.0,
) -> list[dict]:
    """Enrich all organizations from a scraper registry."""
    run_id = default_run_id("all")
    ndjson_path = log_ndjson or default_ndjson_path(run_id)
    cfg = RunnerConfig(
        run_id=run_id,
        batch_id="",
        verbose=verbose,
        ndjson_path=ndjson_path,
        profile=profile,
    )
    logger = EventLogger(cfg)
    results = []

    try:
        items = list(registry.items())
        if max_orgs and max_orgs > 0:
            items = items[:max_orgs]

        for scraper_file, info in items:
            org_name = info[0]
            is_pw_scraper = info[2] if len(info) > 2 else False
            org_abbrev = extract_abbrev(org_name)

            try:
                result = enrich_org_via_runner(
                    org_abbrev=org_abbrev,
                    org_name=org_name,
                    scraper_file=scraper_file,
                    is_playwright_scraper=is_pw_scraper,
                    use_playwright_detail=use_playwright_detail,
                    force=force,
                    logger=logger,
                    profile=profile,
                    max_jobs=max_jobs,
                    job_timeout_seconds=job_timeout_seconds,
                )
                results.append(result)
            except Exception as e:  # noqa: BLE001
                print(f"\n  FAILED to enrich {org_name}: {e}")
                logger.emit(
                    "org_done",
                    org_abbrev=org_abbrev,
                    org_name=org_name,
                    scraper_error=str(e),
                    job_count=0,
                )
                results.append(
                    {
                        "org_name": org_name,
                        "org_abbrev": org_abbrev,
                        "error": str(e),
                    }
                )

        print(f"\nRun log: {ndjson_path}")
        return results
    finally:
        logger.close()
