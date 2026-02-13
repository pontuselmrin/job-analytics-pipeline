from pathlib import Path

from enrichment.runner import PROJECT_ROOT, EventLogger, RunnerConfig, _fetch_one, collect_postings_org_via_runner


def test_event_logger_writes_ndjson(tmp_path):
    path = tmp_path / "run.ndjson"
    cfg = RunnerConfig(run_id="r1", batch_id="B00", verbose=False, ndjson_path=path)
    logger = EventLogger(cfg)
    try:
        logger.emit("org_start", org_abbrev="ACER", org_name="Org Name")
    finally:
        logger.close()

    lines = path.read_text().strip().splitlines()
    assert len(lines) == 1
    assert '"event": "org_start"' in lines[0]
    assert '"run_id": "r1"' in lines[0]
    assert '"batch_id": "B00"' in lines[0]


def test_fetch_one_success(monkeypatch, tmp_path):
    path = tmp_path / "run.ndjson"
    cfg = RunnerConfig(run_id="r1", batch_id="", verbose=False, ndjson_path=path)
    logger = EventLogger(cfg)

    def fake_fetch(**kwargs):
        return {
            "content_type": "html",
            "description": "alpha beta gamma",
            "pdf_path": "",
            "enrich_status": "ok",
            "status_reason": "",
            "fetch_method": "http",
        }

    monkeypatch.setattr("enrichment.runner.fetch_job_content", fake_fetch)
    try:
        out = _fetch_one(
            org_abbrev="ACER",
            org_name="Agency [ACER]",
            idx=1,
            total=1,
            title="Role",
            url="https://example.com/job",
            is_playwright=False,
            logger=logger,
        )
    finally:
        logger.close()

    assert out["enrich_status"] == "ok"
    assert out["content_type"] == "html"
    assert out["fetch_seconds"] >= 0.0


def test_fetch_one_error(monkeypatch, tmp_path):
    path = tmp_path / "run.ndjson"
    cfg = RunnerConfig(run_id="r1", batch_id="", verbose=False, ndjson_path=path)
    logger = EventLogger(cfg)

    def fake_fetch(**kwargs):
        raise RuntimeError("403 Forbidden")

    monkeypatch.setattr("enrichment.runner.fetch_job_content", fake_fetch)
    try:
        out = _fetch_one(
            org_abbrev="ACER",
            org_name="Agency [ACER]",
            idx=1,
            total=1,
            title="Role",
            url="https://example.com/job",
            is_playwright=False,
            logger=logger,
        )
    finally:
        logger.close()

    assert out["enrich_status"] == "blocked_source"
    assert out["status_reason"] == "http_403"
    assert out["error"]


def test_collect_postings_stops_org_after_consecutive_429(monkeypatch, tmp_path):
    path = tmp_path / "run.ndjson"
    cfg = RunnerConfig(run_id="r1", batch_id="B00", verbose=False, ndjson_path=path)
    logger = EventLogger(cfg)

    jobs = [{"title": f"Role {i}", "url": f"https://example.com/{i}"} for i in range(1, 6)]
    monkeypatch.setattr("enrichment.runner.run_scraper_for_org", lambda *args, **kwargs: jobs)

    calls = {"n": 0}

    def fake_fetch_one(**kwargs):
        calls["n"] += 1
        return {
            "content_type": "error",
            "description": "",
            "pdf_path": "",
            "enrich_status": "blocked_source",
            "status_reason": "http_429",
            "fetch_method": "http",
            "fetch_seconds": 0.1,
            "error": "429",
        }

    monkeypatch.setattr("enrichment.runner._fetch_one", fake_fetch_one)
    try:
        out = collect_postings_org_via_runner(
            org_abbrev="EEAS",
            org_name="EEAS",
            scraper_path=PROJECT_ROOT / "scrapers" / "scrape_eeas.py",
            is_playwright_scraper=False,
            logger=logger,
        )
    finally:
        logger.close()

    assert calls["n"] == 3
    assert len(out["jobs"]) == 5
    assert out["jobs"][0]["status_reason"] == "http_429"
    assert out["jobs"][1]["status_reason"] == "http_429"
    assert out["jobs"][2]["status_reason"] == "http_429"
    assert out["jobs"][3]["status_reason"] == "org_rate_limited_skip"
    assert out["jobs"][4]["status_reason"] == "org_rate_limited_skip"
