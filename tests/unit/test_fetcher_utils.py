import pytest

from enrichment.fetcher import classify_fetch_error, _find_embedded_pdf_link


@pytest.mark.unit
def test_classify_fetch_error_403():
    status, reason = classify_fetch_error(RuntimeError("403 Client Error: Forbidden"))
    assert status == "blocked_source"
    assert reason == "http_403"


@pytest.mark.unit
def test_classify_fetch_error_404():
    status, reason = classify_fetch_error(RuntimeError("404 Client Error: Not Found"))
    assert status == "broken_link"
    assert reason == "http_404"


@pytest.mark.unit
def test_find_embedded_pdf_link_absolute():
    html = '<a href="./docs/vacancy.pdf">Download PDF</a>'
    out = _find_embedded_pdf_link(html, "https://example.org/jobs/123")
    assert out == "https://example.org/jobs/docs/vacancy.pdf"


@pytest.mark.unit
def test_find_embedded_pdf_link_none():
    html = "<html><body><h1>No attachment</h1></body></html>"
    out = _find_embedded_pdf_link(html, "https://example.org/jobs/123")
    assert out == ""
