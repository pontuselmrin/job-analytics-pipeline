import pytest

from enrichment.fetcher import (
    _find_embedded_pdf_link,
    _is_short_or_placeholder,
    classify_fetch_error,
)
from tests.test_config import GENERIC_URLS


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
def test_classify_fetch_error_429():
    status, reason = classify_fetch_error(RuntimeError("429 Too Many Requests"))
    assert status == "blocked_source"
    assert reason == "http_429"


@pytest.mark.unit
def test_find_embedded_pdf_link_absolute():
    html = '<a href="./docs/vacancy.pdf">Download PDF</a>'
    out = _find_embedded_pdf_link(html, f"{GENERIC_URLS['example']}/jobs/123")
    assert out == f"{GENERIC_URLS['example']}/jobs/docs/vacancy.pdf"


@pytest.mark.unit
def test_find_embedded_pdf_link_none():
    html = "<html><body><h1>No attachment</h1></body></html>"
    out = _find_embedded_pdf_link(html, f"{GENERIC_URLS['example']}/jobs/123")
    assert out == ""


@pytest.mark.unit
def test_is_short_or_placeholder_flags_low_word_count_even_if_long_chars():
    text = ("alpha " * 21).strip()  # >120 chars but only 21 words
    assert _is_short_or_placeholder(text)
