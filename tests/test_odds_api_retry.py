"""test_odds_api_retry.py — regression tests for capture_clv._odds_api_get.

Covers audit finding C-11 (no retry on HTTP 429 from Odds API).
These are pure-function tests — no network. `requests.get` is monkey-patched
and `time.sleep` is stubbed out so the whole file runs in <1s.

Run:
    cd engine && python -m pytest ../test_odds_api_retry.py -v
    # or: python test_odds_api_retry.py   (no pytest dependency)
"""

import sys
from pathlib import Path

ENGINE_DIR = Path(__file__).resolve().parent / "engine"
sys.path.insert(0, str(ENGINE_DIR))

import capture_clv  # noqa: E402


# ── Fake Response + scripted requests.get ────────────────────────────────────

class _FakeResponse:
    def __init__(self, status_code=200, json_body=None, headers=None, text_body=""):
        self.status_code = status_code
        self._json = json_body
        self.headers = headers or {}
        self.text = text_body

    @property
    def ok(self):
        return 200 <= self.status_code < 300

    def json(self):
        if self._json is None:
            raise ValueError("no json body")
        return self._json


class _ScriptedGet:
    """Replay a list of (response | exception) in order on successive calls."""
    def __init__(self, script):
        self.script = list(script)
        self.calls = 0

    def __call__(self, url, params=None, timeout=None, headers=None):
        # ``headers`` was added in audit M-16 (Section 28) so every outbound
        # Odds API call carries the canonical JonnyParlay UA. This mock must
        # accept (but ignore) the kwarg to stay compatible.
        self.calls += 1
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _install(monkey, script):
    capture_clv.requests.get = _ScriptedGet(script)
    capture_clv.time.sleep = lambda _s: None  # don't actually wait
    capture_clv._quota_low_warned = False     # reset one-shot warning flag
    return capture_clv.requests.get


# ── Tests ────────────────────────────────────────────────────────────────────

def test_200_first_try_returns_body():
    g = _install(None, [_FakeResponse(200, json_body={"ok": True})])
    out = capture_clv._odds_api_get("u", {}, label="t")
    assert out == {"ok": True}
    assert g.calls == 1


def test_429_retries_then_succeeds():
    """One 429, then a 200. Should succeed on attempt 2."""
    g = _install(None, [
        _FakeResponse(429, headers={"Retry-After": "1"}),
        _FakeResponse(200, json_body=[{"id": "evt1"}]),
    ])
    out = capture_clv._odds_api_get("u", {}, label="t")
    assert out == [{"id": "evt1"}]
    assert g.calls == 2


def test_429_exhausts_retries_returns_none():
    """Three consecutive 429s → helper gives up and returns None."""
    g = _install(None, [_FakeResponse(429) for _ in range(3)])
    out = capture_clv._odds_api_get("u", {}, label="t")
    assert out is None
    assert g.calls == 3


def test_500_retries_then_succeeds():
    g = _install(None, [
        _FakeResponse(503),
        _FakeResponse(200, json_body={"x": 1}),
    ])
    out = capture_clv._odds_api_get("u", {}, label="t")
    assert out == {"x": 1}
    assert g.calls == 2


def test_404_no_retry_returns_none():
    """Permanent 4xx — helper must NOT retry (would waste quota and time)."""
    g = _install(None, [_FakeResponse(404, text_body="not found")])
    out = capture_clv._odds_api_get("u", {}, label="t")
    assert out is None
    assert g.calls == 1


def test_connection_error_retries_then_succeeds():
    import requests as _r
    g = _install(None, [
        _r.ConnectionError("net down"),
        _FakeResponse(200, json_body={"ok": True}),
    ])
    out = capture_clv._odds_api_get("u", {}, label="t")
    assert out == {"ok": True}
    assert g.calls == 2


def test_timeout_exhausts_retries_returns_none():
    import requests as _r
    g = _install(None, [_r.Timeout("slow") for _ in range(3)])
    out = capture_clv._odds_api_get("u", {}, label="t")
    assert out is None
    assert g.calls == 3


def test_fetch_events_wrapper_returns_list_on_success():
    _install(None, [_FakeResponse(200, json_body=[{"id": "a"}])])
    out = capture_clv.fetch_events("basketball_nba")
    assert out == [{"id": "a"}]


def test_fetch_events_wrapper_returns_empty_list_on_failure():
    """Even when retries exhaust, the wrapper must return [] (not None) —
    downstream code iterates the result."""
    _install(None, [_FakeResponse(429) for _ in range(3)])
    out = capture_clv.fetch_events("basketball_nba")
    assert out == []


def test_fetch_game_odds_wrapper_returns_empty_dict_on_failure():
    """fetch_game_odds must return {} (not None) on failure —
    downstream code does .get() on the result."""
    _install(None, [_FakeResponse(500) for _ in range(3)])
    out = capture_clv.fetch_game_odds("evt1", "basketball_nba", ["h2h"])
    assert out == {}


def test_malformed_json_returns_none():
    _install(None, [_FakeResponse(200, json_body=None)])  # json() raises
    out = capture_clv._odds_api_get("u", {}, label="t")
    assert out is None


def test_retry_after_header_honored():
    """Confirm Retry-After (in seconds) is parsed and used."""
    sleeps = []
    capture_clv.time.sleep = lambda s: sleeps.append(s)
    g = _ScriptedGet([
        _FakeResponse(429, headers={"Retry-After": "5"}),
        _FakeResponse(200, json_body={"ok": 1}),
    ])
    capture_clv.requests.get = g
    capture_clv._quota_low_warned = False
    out = capture_clv._odds_api_get("u", {}, label="t")
    assert out == {"ok": 1}
    assert 5.0 in sleeps, f"Retry-After=5 should produce a 5s sleep (got {sleeps})"


# ─── Fallback runner (no pytest required) ───────────────────────────────────

def _run_all():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed, failed = 0, []
    for t in tests:
        try:
            t()
            print(f"  ✅ {t.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  ❌ {t.__name__} — {e}")
            failed.append(t.__name__)
        except Exception as e:
            print(f"  🚫 {t.__name__} — {type(e).__name__}: {e}")
            failed.append(t.__name__)
    print(f"\n  {passed}/{len(tests)} passed")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(_run_all())
