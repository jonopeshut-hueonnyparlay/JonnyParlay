"""test_odds_client_malformed_json.py — H33 coverage gap.

Verifies that OddsClient._get() handles a 200 response with malformed JSON
gracefully: returns [] rather than propagating the ValueError/JSONDecodeError.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest import mock

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "engine"))


class _FakeResponse:
    def __init__(self, status_code=200, json_raises=None, json_body=None):
        self.status_code = status_code
        self.headers = {}
        self._json_raises = json_raises
        self._json_body   = json_body

    def json(self):
        if self._json_raises:
            raise self._json_raises
        return self._json_body


def _make_client():
    import run_picks
    client = run_picks.OddsFetcher.__new__(run_picks.OddsFetcher)
    client.remaining = None
    return client


def test_malformed_json_returns_empty_list():
    """200 response with un-parseable body → _get returns [] after retries."""
    import run_picks
    resp = _FakeResponse(status_code=200, json_raises=ValueError("no json"))

    with mock.patch.object(run_picks, "requests") as mock_req:
        mock_req.get.return_value = resp
        with mock.patch.object(run_picks, "time") as mock_time:
            mock_time.sleep = lambda _: None
            client = _make_client()
            result = client._get("https://example.com/odds", {"regions": "us"})

    assert result == [], f"Expected [] on malformed JSON, got {result!r}"


def test_json_decode_error_returns_empty_list():
    """200 response that raises json.JSONDecodeError → _get returns []."""
    import json
    import run_picks
    exc = json.JSONDecodeError("Expecting value", "", 0)
    resp = _FakeResponse(status_code=200, json_raises=exc)

    with mock.patch.object(run_picks, "requests") as mock_req:
        mock_req.get.return_value = resp
        with mock.patch.object(run_picks, "time") as mock_time:
            mock_time.sleep = lambda _: None
            client = _make_client()
            result = client._get("https://example.com/odds", {"regions": "us"})

    assert result == []


def test_valid_json_passes_through():
    """Sanity: a well-formed 200 response is returned as-is."""
    import run_picks
    body = [{"id": "abc", "home_team": "Lakers"}]
    resp = _FakeResponse(status_code=200, json_body=body)

    with mock.patch.object(run_picks, "requests") as mock_req:
        mock_req.get.return_value = resp
        client = _make_client()
        result = client._get("https://example.com/odds", {"regions": "us"})

    assert result == body


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
