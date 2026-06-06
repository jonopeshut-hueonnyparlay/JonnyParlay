"""test_context_research.py — Schema and logic tests for engine/context_research.py.

Tests aggregate_verdict(), _parse_factors(), and output schema validation.
No live Anthropic API calls — the client is mocked in all tests.
"""

import json
import sys
import os
import unittest
from unittest.mock import MagicMock, patch

# ── Path setup ─────────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "engine"))

# Mock anthropic before importing context_research (avoids ImportError if not installed)
_mock_anthropic = MagicMock()
sys.modules.setdefault("anthropic", _mock_anthropic)
_mock_anthropic.APIError = Exception
_mock_anthropic.APIConnectionError = Exception
_mock_anthropic.RateLimitError = Exception

import context_research as cr  # noqa: E402


# ── aggregate_verdict tests ────────────────────────────────────────────────────

def test_aggregate_verdict_confirms():
    factors = {
        "rlm": "confirms", "weather": "confirms", "travel": "confirms",
        "umpire": "fades", "era_fip": "neutral", "bullpen": "neutral",
        "pythag": "neutral", "injury": "neutral", "rest": "neutral",
        "home_away": "neutral", "form": "neutral", "division": "neutral",
        "motivation": "neutral", "line_move": "neutral", "public_sharp": "neutral",
    }
    verdict, confidence = cr.aggregate_verdict(factors)
    assert verdict == "confirms", f"Expected confirms, got {verdict}"
    assert 0.0 <= confidence <= 1.0


def test_aggregate_verdict_fades():
    factors = {
        "rlm": "fades", "weather": "fades", "travel": "fades",
        "umpire": "confirms", "era_fip": "neutral", "bullpen": "neutral",
        "pythag": "neutral", "injury": "neutral", "rest": "neutral",
        "home_away": "neutral", "form": "neutral", "division": "neutral",
        "motivation": "neutral", "line_move": "neutral", "public_sharp": "neutral",
    }
    verdict, confidence = cr.aggregate_verdict(factors)
    assert verdict == "fades", f"Expected fades, got {verdict}"
    assert 0.0 <= confidence <= 1.0


def test_aggregate_verdict_neutral_close():
    """Confirms and fades differ by exactly 1 → neutral."""
    factors = {k: "neutral" for k in cr._FACTORS}
    factors["rlm"] = "confirms"
    factors["weather"] = "fades"
    verdict, confidence = cr.aggregate_verdict(factors)
    assert verdict == "neutral", f"Expected neutral for gap=1, got {verdict}"


def test_aggregate_verdict_neutral_tied():
    """Equal confirms and fades → neutral."""
    factors = {k: "neutral" for k in cr._FACTORS}
    factors["rlm"] = "confirms"
    factors["travel"] = "confirms"
    factors["weather"] = "fades"
    factors["bullpen"] = "fades"
    verdict, _ = cr.aggregate_verdict(factors)
    assert verdict == "neutral"


def test_confidence_range():
    """Confidence must always be in [0.0, 1.0]."""
    for n_confirms in range(0, len(cr._FACTORS) + 1):
        factors = {k: "neutral" for k in cr._FACTORS}
        for i, key in enumerate(cr._FACTORS):
            if i < n_confirms:
                factors[key] = "confirms"
        _, confidence = cr.aggregate_verdict(factors)
        assert 0.0 <= confidence <= 1.0, f"confidence={confidence} out of range"


def test_confidence_all_confirms():
    factors = {k: "confirms" for k in cr._FACTORS}
    verdict, confidence = cr.aggregate_verdict(factors)
    assert verdict == "confirms"
    assert confidence == 1.0


def test_confidence_all_neutral():
    factors = {k: "neutral" for k in cr._FACTORS}
    verdict, confidence = cr.aggregate_verdict(factors)
    assert verdict == "neutral"
    assert confidence == 0.0


# ── _parse_factors tests ───────────────────────────────────────────────────────

def test_parse_factors_valid():
    raw = {k: "confirms" for k in cr._FACTORS}
    out = cr._parse_factors(raw)
    assert set(out.keys()) == set(cr._FACTORS)
    assert all(v == "confirms" for v in out.values())


def test_parse_factors_invalid_value_becomes_neutral():
    raw = {k: "gibberish" for k in cr._FACTORS}
    out = cr._parse_factors(raw)
    assert all(v == "neutral" for v in out.values())


def test_parse_factors_missing_key_defaults_neutral():
    out = cr._parse_factors({})
    assert set(out.keys()) == set(cr._FACTORS)
    assert all(v == "neutral" for v in out.values())


def test_parse_factors_case_insensitive():
    raw = {k: "CONFIRMS" for k in cr._FACTORS}
    out = cr._parse_factors(raw)
    assert all(v == "confirms" for v in out.values())


def test_parse_factors_valid_values():
    """Every value returned by _parse_factors must be in _VALID_VALUES."""
    raw = {cr._FACTORS[i]: v for i, v in enumerate(
        ["confirms", "fades", "neutral", "confirms", "fades",
         "neutral", "NEUTRAL", "FADES", "CONFIRMS", "invalid",
         "fades", "neutral", "confirms", "fades", "neutral"]
    )}
    out = cr._parse_factors(raw)
    for k, v in out.items():
        assert v in cr._VALID_VALUES, f"factor {k!r} has invalid value {v!r}"


# ── Output schema tests ────────────────────────────────────────────────────────

def _make_verdict(overrides=None):
    """Build a minimal valid verdict dict."""
    base = {
        "game": "Boston Red Sox @ New York Yankees",
        "date": "2026-06-05",
        "sport": "MLB",
        "verdict": "confirms",
        "confidence": 0.47,
        "factors": {k: "neutral" for k in cr._FACTORS},
        "summary": "Sharp reverse-line movement against heavy public.",
        "researched_at": "2026-06-05T14:30:00",
    }
    if overrides:
        base.update(overrides)
    return base


_REQUIRED_FIELDS = {"game", "date", "sport", "verdict", "confidence", "factors", "summary", "researched_at"}
_VALID_VERDICTS = {"confirms", "fades", "neutral"}


def test_output_schema_required_fields():
    v = _make_verdict()
    for field in _REQUIRED_FIELDS:
        assert field in v, f"Missing required field: {field!r}"


def test_verdict_valid_values():
    for val in _VALID_VERDICTS:
        v = _make_verdict({"verdict": val})
        assert v["verdict"] in _VALID_VERDICTS


def test_factor_valid_values():
    v = _make_verdict()
    for key, val in v["factors"].items():
        assert val in cr._VALID_VALUES, f"Factor {key!r} has invalid value {val!r}"


def test_confidence_is_float_in_range():
    v = _make_verdict({"confidence": 0.72})
    assert isinstance(v["confidence"], float)
    assert 0.0 <= v["confidence"] <= 1.0


def test_factors_has_all_keys():
    v = _make_verdict()
    assert set(v["factors"].keys()) == set(cr._FACTORS)


# ── Mock API response parsing ──────────────────────────────────────────────────

def test_research_game_mock_api():
    """research_game() parses a mocked Anthropic response correctly."""
    mock_response_text = json.dumps({
        "factors": {
            "rlm": "confirms", "weather": "neutral", "travel": "fades",
            "umpire": "neutral", "era_fip": "confirms", "bullpen": "fades",
            "pythag": "neutral", "injury": "neutral", "rest": "confirms",
            "home_away": "neutral", "form": "neutral", "division": "neutral",
            "motivation": "neutral", "line_move": "confirms", "public_sharp": "neutral",
        },
        "summary": "Sharp money on road team despite public fade.",
    })

    mock_content = MagicMock()
    mock_content.text = mock_response_text
    mock_response = MagicMock()
    mock_response.content = [mock_content]

    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response

    result = cr.research_game(
        game="Boston Red Sox @ New York Yankees",
        sport="MLB",
        date_str="2026-06-05",
        client=mock_client,
    )

    assert result is not None
    assert result["game"] == "Boston Red Sox @ New York Yankees"
    assert result["sport"] == "MLB"
    assert result["verdict"] in _VALID_VERDICTS
    assert 0.0 <= result["confidence"] <= 1.0
    assert result["factors"]["rlm"] == "confirms"
    assert result["factors"]["travel"] == "fades"
    assert "summary" in result
    assert "researched_at" in result
    # 3 confirms, 2 fades → confirms
    assert result["verdict"] == "confirms"


def test_research_game_api_error_returns_none():
    """API error → returns None (graceful skip)."""
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = Exception("connection failed")

    result = cr.research_game("LAL @ GSW", "NBA", "2026-06-05", mock_client)
    assert result is None


def test_research_game_malformed_json_returns_none():
    """Non-JSON response → returns None."""
    mock_content = MagicMock()
    mock_content.text = "Sorry, I cannot help with that."
    mock_response = MagicMock()
    mock_response.content = [mock_content]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response

    result = cr.research_game("LAL @ GSW", "NBA", "2026-06-05", mock_client)
    assert result is None


# ── Fallback runner ────────────────────────────────────────────────────────────

def _run_all():
    tests = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    passed = failed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
            passed += 1
        except Exception as e:
            print(f"  FAIL  {t.__name__}: {e}")
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    _run_all()
