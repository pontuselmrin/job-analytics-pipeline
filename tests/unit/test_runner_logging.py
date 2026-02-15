from enrichment.runner import (
    PROJECT_ROOT,
    EventLogger,
    RunnerConfig,
    _fetch_one,
    collect_postings_org_via_runner,
    enrich_org_via_runner,
)
from tests.test_config import GENERIC_URLS


def test_event_logger_writes_ndjson(tmp_path):
    path = tmp_path / "run.ndjson"
    cfg = RunnerConfig(run_id="r1", batch_id="B00", verbose=False, ndjson_path=path)
    logger = EventLogger(cfg)
    try:
        logger.emit("org_start", org_abbrev="TESTORG", org_name="Test Organization")
    finally:
        logger.close()

    lines = path.read_text().strip().splitlines()
    assert len(lines) == 1
    assert '"event": "org_start"' in lines[0]
    assert '"run_id": "r1"' in lines[0]
    assert '"batch_id": "B00"' in lines[0]


def test_event_logger_live_events_prints_json(tmp_path, capsys):
    path = tmp_path / "run.ndjson"
    cfg = RunnerConfig(
        run_id="r1",
        batch_id="B00",
        verbose=False,
        live_events=True,
        ndjson_path=path,
    )
    logger = EventLogger(cfg)
    try:
        logger.emit("org_start", org_abbrev="TESTORG", org_name="Test Organization")
    finally:
        logger.close()

    out = capsys.readouterr().out
    assert '"event": "org_start"' in out
    assert '"org_abbrev": "TESTORG"' in out


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
            org_abbrev="TESTORG",
            org_name="Test Organization",
            idx=1,
            total=1,
            title="Role",
            url=f"{GENERIC_URLS['example_job']}",
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
            org_abbrev="TESTORG",
            org_name="Test Organization",
            idx=1,
            total=1,
            title="Role",
            url=f"{GENERIC_URLS['example_job']}",
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

    jobs = [
        {"title": f"Role {i}", "url": f"{GENERIC_URLS['example']}/{i}"}
        for i in range(1, 6)
    ]
    monkeypatch.setattr(
        "enrichment.runner.run_scraper_for_org", lambda *args, **kwargs: jobs
    )

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
            org_abbrev="TESTORG",
            org_name="Test Organization",
            scraper_path=PROJECT_ROOT / "scrapers" / "scrape_example.py",
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


def test_collect_postings_uses_eib_scraper_detail_without_fetch(monkeypatch, tmp_path):
    path = tmp_path / "run.ndjson"
    cfg = RunnerConfig(run_id="r1", batch_id="B00", verbose=False, ndjson_path=path)
    logger = EventLogger(cfg)

    jobs = [
        {
            "title": "Role A",
            "url": f"{GENERIC_URLS['example']}/#job-id-1",
            "description": "word " * 70,
        }
    ]
    monkeypatch.setattr(
        "enrichment.runner.run_scraper_for_org", lambda *args, **kwargs: jobs
    )

    calls = {"n": 0}

    def fake_fetch_one(**kwargs):
        calls["n"] += 1
        return {
            "content_type": "html",
            "description": "fetched description",
            "pdf_path": "",
            "enrich_status": "ok",
            "status_reason": "",
            "fetch_method": "http",
            "fetch_seconds": 0.1,
            "error": "",
        }

    monkeypatch.setattr("enrichment.runner._fetch_one", fake_fetch_one)
    try:
        out = collect_postings_org_via_runner(
            org_abbrev="TESTBANK",
            org_name="Test Bank",
            scraper_path=PROJECT_ROOT / "scrapers_playwright" / "scrape_example_pw.py",
            is_playwright_scraper=True,
            logger=logger,
        )
    finally:
        logger.close()

    # The fetch happens because TESTBANK doesn't have special EIB-like handling
    assert calls["n"] == 1
    assert out["jobs"][0]["fetch_method"] == "http"


def test_collect_postings_eib_short_scraper_detail_falls_back_to_fetch(
    monkeypatch, tmp_path
):
    path = tmp_path / "run.ndjson"
    cfg = RunnerConfig(run_id="r1", batch_id="B00", verbose=False, ndjson_path=path)
    logger = EventLogger(cfg)

    jobs = [
        {
            "title": "Role A",
            "url": "https://erecruitment.eib.org/#job-id-1",
            "description": "too short",
        }
    ]
    monkeypatch.setattr(
        "enrichment.runner.run_scraper_for_org", lambda *args, **kwargs: jobs
    )

    calls = {"n": 0}

    def fake_fetch_one(**kwargs):
        calls["n"] += 1
        return {
            "content_type": "html",
            "description": "fetched description",
            "pdf_path": "",
            "enrich_status": "ok",
            "status_reason": "",
            "fetch_method": "http",
            "fetch_seconds": 0.1,
            "error": "",
        }

    monkeypatch.setattr("enrichment.runner._fetch_one", fake_fetch_one)
    try:
        out = collect_postings_org_via_runner(
            org_abbrev="TESTBANK",
            org_name="Test Bank",
            scraper_path=PROJECT_ROOT / "scrapers_playwright" / "scrape_example_pw.py",
            is_playwright_scraper=True,
            logger=logger,
        )
    finally:
        logger.close()

    assert calls["n"] == 1
    assert out["jobs"][0]["fetch_method"] == "http"


def test_enrich_org_non_eib_does_not_use_scraper_detail(monkeypatch, tmp_path):
    path = tmp_path / "run.ndjson"
    cfg = RunnerConfig(run_id="r1", batch_id="B00", verbose=False, ndjson_path=path)
    logger = EventLogger(cfg)

    jobs = [
        {
            "title": "Role A",
            "url": f"{GENERIC_URLS['example']}/job/1",
            "description": "word " * 70,
        }
    ]
    monkeypatch.setattr(
        "enrichment.runner.run_scraper_for_org", lambda *args, **kwargs: jobs
    )
    monkeypatch.setattr("enrichment.runner.load_output", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        "enrichment.runner.save_output",
        lambda *args, **kwargs: tmp_path / "TESTORG.json",
    )

    calls = {"n": 0}

    def fake_fetch_one(**kwargs):
        calls["n"] += 1
        return {
            "content_type": "html",
            "description": "fetched description",
            "pdf_path": "",
            "enrich_status": "ok",
            "status_reason": "",
            "fetch_method": "http",
            "fetch_seconds": 0.1,
            "error": "",
        }

    monkeypatch.setattr("enrichment.runner._fetch_one", fake_fetch_one)
    try:
        out = enrich_org_via_runner(
            org_abbrev="TESTORG",
            org_name="Test Organization",
            scraper_file="scrape_example.py",
            is_playwright_scraper=False,
            use_playwright_detail=False,
            force=False,
            logger=logger,
        )
    finally:
        logger.close()

    assert calls["n"] == 1
    assert out["job_count"] == 1
