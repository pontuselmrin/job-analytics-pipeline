import pytest
import requests

import scrapers.base as base


class _FakeResp:
    def __init__(self, status_code=200, headers=None):
        self.status_code = status_code
        self.headers = headers or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            err = requests.HTTPError(f"{self.status_code} error")
            err.response = self
            raise err


@pytest.mark.unit
def test_fetch_uses_retry_after_for_429(monkeypatch):
    calls = {"n": 0}
    sleeps = []

    def fake_request(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return _FakeResp(429, {"Retry-After": "3"})
        return _FakeResp(200)

    monkeypatch.setattr(base.requests, "request", fake_request)
    monkeypatch.setattr(base.time, "sleep", lambda s: sleeps.append(s))

    out = base.fetch("https://example.org")
    assert out.status_code == 200
    assert calls["n"] == 2
    assert sleeps == [3.0]


@pytest.mark.unit
def test_fetch_uses_exponential_backoff_without_retry_after(monkeypatch):
    calls = {"n": 0}
    sleeps = []

    def fake_request(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] < 3:
            return _FakeResp(429)
        return _FakeResp(200)

    monkeypatch.setattr(base.requests, "request", fake_request)
    monkeypatch.setattr(base.time, "sleep", lambda s: sleeps.append(s))

    out = base.fetch("https://example.org")
    assert out.status_code == 200
    assert calls["n"] == 3
    assert sleeps == [1.0, 2.0]


@pytest.mark.unit
def test_fetch_retries_non_429_errors_with_default_backoff(monkeypatch):
    calls = {"n": 0}
    sleeps = []

    def fake_request(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] < 3:
            return _FakeResp(500)
        return _FakeResp(200)

    monkeypatch.setattr(base.requests, "request", fake_request)
    monkeypatch.setattr(base.time, "sleep", lambda s: sleeps.append(s))

    out = base.fetch("https://example.org")
    assert out.status_code == 200
    assert calls["n"] == 3
    assert sleeps == [1.0, 2.0]
