#!/usr/bin/env python3
"""Regression tests for Section 28 — webhook retry safety + API User-Agent.

Two closely related audit items:

  M-4   _webhook_post in grade_picks.py / morning_preview.py / run_picks.py /
        results_graphic.py parsed Discord 429 bodies with
        ``float(r.json().get("retry_after", backoff))``. On an empty /
        non-JSON 429 body this raises and blows up the webhook retry loop.
        It also ignored the RFC-standard ``Retry-After`` HTTP header.

  M-16  Every outbound HTTP request — Odds API, NBA/NHL/MLB stats, Discord
        webhooks — went out with the default ``python-requests/*`` UA. Some
        CDNs (Cloudflare, see post_nrfi_bonus.py's 1010 workaround) block
        that by default, and server-side logs can't distinguish JonnyParlay
        traffic from generic scrapers.

The fix is a shared ``engine/http_utils.py`` module exposing:

    * JONNYPARLAY_UA
    * default_headers(extra=None)
    * retry_after_secs(response, default)

This test file pins its behaviour and guards against regressions in every
call site that now depends on it.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "engine"))


# ─────────────────────────────────────────────────────────────────
# Stub response helpers — these let us exercise retry_after_secs
# without spinning up a real HTTP server.
# ─────────────────────────────────────────────────────────────────

class _StubResp:
    """Minimal stand-in for a requests.Response."""

    def __init__(self, *, headers=None, body=None, raises_on_json=False):
        self.headers = dict(headers or {})
        self._body = body
        self._raises_on_json = raises_on_json

    def json(self):
        if self._raises_on_json:
            raise ValueError("No JSON object could be decoded")
        return self._body


class _NoHeadersResp:
    """Response that doesn't expose .headers — guards the AttributeError path."""

    def json(self):
        return {"retry_after": 1.0}


# ─────────────────────────────────────────────────────────────────
# retry_after_secs: header-first parsing
# ─────────────────────────────────────────────────────────────────

def test_retry_after_secs_prefers_header_over_body():
    """If both header and JSON body are present, the header wins — that's
    what every sane 429 handler does and what Discord documents.
    """
    from http_utils import retry_after_secs
    r = _StubResp(headers={"Retry-After": "5"},
                  body={"retry_after": 12.0})
    assert retry_after_secs(r) == 5.0


def test_retry_after_secs_parses_float_seconds_header():
    from http_utils import retry_after_secs
    r = _StubResp(headers={"Retry-After": "1.5"})
    assert retry_after_secs(r) == 1.5


def test_retry_after_secs_parses_http_date_header():
    """RFC 7231 lets servers send an HTTP-date instead of a delta-seconds
    value. The helper must compute the remaining delta."""
    from datetime import datetime, timezone, timedelta
    from email.utils import format_datetime
    from http_utils import retry_after_secs

    # 3 seconds in the future → helper should return ~3s (clamped to <=30).
    target = datetime.now(tz=timezone.utc) + timedelta(seconds=3)
    r = _StubResp(headers={"Retry-After": format_datetime(target)})
    out = retry_after_secs(r)
    assert 0.5 <= out <= 30.0


def test_retry_after_secs_past_http_date_falls_through():
    """A Retry-After date that's already in the past must not produce a
    negative sleep — it should fall through to the body / default."""
    from datetime import datetime, timezone, timedelta
    from email.utils import format_datetime
    from http_utils import retry_after_secs

    past = datetime.now(tz=timezone.utc) - timedelta(seconds=60)
    r = _StubResp(headers={"Retry-After": format_datetime(past)},
                  body={"retry_after": 3.0})
    # Should use the body value (3.0), not a negative.
    assert retry_after_secs(r) == 3.0


def test_retry_after_secs_falls_back_to_json_body():
    """When the header is missing, the Discord-shape JSON body is the
    next best source."""
    from http_utils import retry_after_secs
    r = _StubResp(body={"retry_after": 4.2})
    assert retry_after_secs(r) == 4.2


def test_retry_after_secs_tolerates_non_json_body():
    """The original bug: ``r.json()`` raises on an empty/non-JSON body
    and the exception propagates out of the retry loop, killing the post.
    """
    from http_utils import retry_after_secs
    r = _StubResp(headers={}, raises_on_json=True)
    # Must return the default, not raise.
    out = retry_after_secs(r, default=2.0)
    assert out == 2.0


def test_retry_after_secs_tolerates_missing_headers_attr():
    """A custom/mocked response without .headers must not crash the
    helper — we fall straight through to the JSON body."""
    from http_utils import retry_after_secs
    r = _NoHeadersResp()
    assert retry_after_secs(r) == 1.0


def test_retry_after_secs_returns_default_on_everything_missing():
    from http_utils import retry_after_secs
    r = _StubResp()
    # Neither header nor body — use the default (clamped).
    assert retry_after_secs(r, default=2.0) == 2.0


def test_retry_after_secs_never_raises():
    """Blanket guarantee: no input combination propagates an exception."""
    from http_utils import retry_after_secs
    cases = [
        _StubResp(headers={"Retry-After": "not-a-number"}),
        _StubResp(body="raw-string-not-a-dict"),
        _StubResp(body=None, raises_on_json=True),
        _StubResp(body={"retry_after": "whatever"}),
        _StubResp(body={"retry_after": None}),
        _StubResp(headers={"Retry-After": ""}),
    ]
    for r in cases:
        out = retry_after_secs(r, default=1.0)
        assert isinstance(out, float)


# ─────────────────────────────────────────────────────────────────
# retry_after_secs: clamping
# ─────────────────────────────────────────────────────────────────

def test_retry_after_secs_clamps_unreasonably_large_values():
    """A rogue ``retry_after=3600`` must not stall the engine for an
    hour — clamp to <=30s."""
    from http_utils import retry_after_secs
    r = _StubResp(body={"retry_after": 3600})
    assert retry_after_secs(r) <= 30.0


def test_retry_after_secs_header_large_value_clamped():
    from http_utils import retry_after_secs
    r = _StubResp(headers={"Retry-After": "9999"})
    assert retry_after_secs(r) <= 30.0


def test_retry_after_secs_clamps_zero_up_to_min():
    """Zero / very small values tighten into a hot loop. Enforce a
    minimum sleep so we never hammer the endpoint."""
    from http_utils import retry_after_secs
    r = _StubResp(body={"retry_after": 0})
    assert retry_after_secs(r) >= 0.5


def test_retry_after_secs_clamps_negative_up_to_min():
    from http_utils import retry_after_secs
    r = _StubResp(body={"retry_after": -10.0})
    assert retry_after_secs(r) >= 0.5


def test_retry_after_secs_clamps_default_too():
    """Defensive: even the ``default=`` kwarg is clamped — caller can't
    accidentally request a 2-minute sleep just by passing default=120.
    """
    from http_utils import retry_after_secs
    r = _StubResp()
    assert retry_after_secs(r, default=120.0) == 30.0
    assert retry_after_secs(r, default=0.0) == 0.5


# ─────────────────────────────────────────────────────────────────
# default_headers / JONNYPARLAY_UA
# ─────────────────────────────────────────────────────────────────

def test_default_headers_includes_ua():
    from http_utils import default_headers, JONNYPARLAY_UA
    h = default_headers()
    assert h["User-Agent"] == JONNYPARLAY_UA


def test_default_headers_merges_extra():
    from http_utils import default_headers, JONNYPARLAY_UA
    h = default_headers({"Content-Type": "application/json"})
    assert h["User-Agent"] == JONNYPARLAY_UA
    assert h["Content-Type"] == "application/json"


def test_default_headers_allows_ua_override():
    """Rare but legal: a scraper that needs to mimic a browser UA exactly
    can override the default via the ``extra`` mapping."""
    from http_utils import default_headers
    h = default_headers({"User-Agent": "Mozilla/5.0 Custom"})
    assert h["User-Agent"] == "Mozilla/5.0 Custom"


def test_default_headers_does_not_leak_between_calls():
    """Two calls must not share state — callers mutating the returned
    dict can't corrupt the next caller's headers."""
    from http_utils import default_headers
    h1 = default_headers()
    h1["X-Injected"] = "leak"
    h2 = default_headers()
    assert "X-Injected" not in h2


def test_jonnyparlay_ua_is_identifiable():
    """The UA must name JonnyParlay so operators can grep it from logs."""
    from http_utils import JONNYPARLAY_UA
    assert "JonnyParlay" in JONNYPARLAY_UA
    assert "picksbyjonny.com" in JONNYPARLAY_UA


# ─────────────────────────────────────────────────────────────────
# Source-level checks — every _webhook_post site must be on the
# new helpers (no bare ``float(r.json().get("retry_after", …))``).
# ─────────────────────────────────────────────────────────────────

_ENGINE = HERE / "engine"

@pytest.mark.parametrize("fname", [
    "grade_picks.py",
    "morning_preview.py",
    "results_graphic.py",
    "run_picks.py",
])
def test_no_bare_retry_after_float_json(fname):
    """The old crash-prone pattern must not reappear anywhere."""
    src = (_ENGINE / fname).read_text(encoding="utf-8")
    # Strip comments before matching — we mention the pattern in docstrings.
    stripped = re.sub(r'""".*?"""', "", src, flags=re.DOTALL)
    stripped = re.sub(r"#.*", "", stripped)
    assert 'float(r.json().get("retry_after"' not in stripped, (
        f"{fname} still uses the crash-prone retry_after pattern"
    )


@pytest.mark.parametrize("fname", [
    "grade_picks.py",
    "morning_preview.py",
    "results_graphic.py",
])
def test_webhook_post_imports_retry_after_secs(fname):
    """Every _webhook_post site must import the shared helper."""
    src = (_ENGINE / fname).read_text(encoding="utf-8")
    assert "retry_after_secs" in src, (
        f"{fname} doesn't import retry_after_secs"
    )


@pytest.mark.parametrize("fname", [
    "grade_picks.py",
    "morning_preview.py",
    "results_graphic.py",
    "run_picks.py",
    "capture_clv.py",
])
def test_files_import_default_headers(fname):
    """Every file that makes outbound HTTP requests must import
    default_headers — run_picks.py and capture_clv.py for the Odds API,
    grade_picks.py for stats APIs + webhooks, etc."""
    src = (_ENGINE / fname).read_text(encoding="utf-8")
    assert "default_headers" in src, (
        f"{fname} doesn't import/use default_headers — outbound traffic "
        f"will go out with the default python-requests UA"
    )


# ─────────────────────────────────────────────────────────────────
# Behavioural check — _webhook_post survives an empty 429 body.
# This is the precise crash M-4 was closing.
# ─────────────────────────────────────────────────────────────────

def test_grade_picks_webhook_post_survives_empty_429_body(monkeypatch):
    """Simulate a Discord 429 with an empty, non-JSON body. The pre-M-4
    implementation crashed with JSONDecodeError here; the fix must sleep
    the default and continue to the next attempt.
    """
    import grade_picks

    calls = {"n": 0, "slept": []}

    class _RL:
        status_code = 429
        headers = {}
        text = ""

        def json(self):
            raise ValueError("Expecting value: line 1 column 1 (char 0)")

        def raise_for_status(self):
            raise AssertionError("should not be called on 429")

    class _OK:
        status_code = 204
        headers = {}
        text = ""

        def json(self):
            return {}

        def raise_for_status(self):
            return None

    def _fake_post(url, json=None, headers=None, timeout=None):
        calls["n"] += 1
        return _RL() if calls["n"] == 1 else _OK()

    def _fake_sleep(s):
        calls["slept"].append(s)

    monkeypatch.setattr(grade_picks.requests, "post", _fake_post)
    monkeypatch.setattr(grade_picks.time, "sleep", _fake_sleep)

    ok = grade_picks._webhook_post(
        "https://example.invalid/webhook", {"content": "hi"},
        retries=3, backoff=2.0, label="test",
    )
    assert ok is True
    # One 429 + one success — and we slept for the clamped default.
    assert calls["n"] == 2
    assert calls["slept"] and 0.5 <= calls["slept"][0] <= 30.0


def test_morning_preview_webhook_post_survives_empty_429_body(monkeypatch):
    """Same invariant for morning_preview."""
    import morning_preview

    calls = {"n": 0}

    class _RL:
        status_code = 429
        headers = {}
        text = ""

        def json(self):
            raise ValueError("no json")

    class _OK:
        status_code = 204
        headers = {}
        text = ""

        def json(self):
            return {}

    def _fake_post(url, json=None, headers=None, timeout=None):
        calls["n"] += 1
        return _RL() if calls["n"] == 1 else _OK()

    monkeypatch.setattr(morning_preview.requests, "post", _fake_post)
    monkeypatch.setattr(morning_preview.time, "sleep", lambda *_a, **_k: None)

    ok = morning_preview._webhook_post(
        "https://example.invalid/webhook", {"content": "hi"},
    )
    assert ok is True
    assert calls["n"] == 2


def test_webhook_post_sends_ua_header(monkeypatch):
    """Behavioural guard that the outbound post actually carries the UA.
    (The source-level check catches the import; this catches forgetting
    to pass ``headers=headers`` into requests.post itself.)"""
    import grade_picks
    from http_utils import JONNYPARLAY_UA

    seen = {}

    class _OK:
        status_code = 204
        headers = {}
        text = ""

        def json(self):
            return {}

        def raise_for_status(self):
            return None

    def _fake_post(url, json=None, headers=None, timeout=None):
        seen["headers"] = headers
        return _OK()

    monkeypatch.setattr(grade_picks.requests, "post", _fake_post)
    grade_picks._webhook_post(
        "https://example.invalid/webhook", {"content": "hi"}, label="ua-check",
    )
    assert seen.get("headers", {}).get("User-Agent") == JONNYPARLAY_UA
