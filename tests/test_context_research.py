"""test_context_research.py — Tests for engine/context_research.py (5-group rebuild).

Covers weighted aggregation, per-group response parsing, fast paths (indoor
weather, non-MLB pitching), group failure isolation, data-quality overrides,
neutral_reason population, the daily cache, and merge/prune write semantics.
No live Anthropic API calls — the client is mocked in all tests.
"""

import json
import sys
import os
import tempfile
import unittest
from pathlib import Path
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


# ── Test helpers ───────────────────────────────────────────────────────────────

def _neutral_factors():
    return {k: "neutral" for k in cr._FACTORS}


def _mk_response(text):
    """Anthropic response mock: one content block carrying `text`."""
    block = MagicMock()
    block.text = text
    resp = MagicMock()
    resp.content = [block]
    return resp


def _group_response(group_id, overrides=None, summary="no signal"):
    """Valid JSON response for one group; all factors neutral/fresh unless overridden."""
    factors = {
        f: {"verdict": "neutral", "data_quality": "fresh", "evidence": ""}
        for f in cr._GROUPS[group_id]["factors"]
    }
    for key, vals in (overrides or {}).items():
        factors[key].update(vals)
    return _mk_response(json.dumps({"factors": factors, "summary": summary}))


def _api_gids(game, sport):
    """Group ids that hit the API for this game, in research_game call order."""
    return [g for g in sorted(cr._GROUPS) if cr._fast_path_result(g, game, sport) is None]


def _client_for(game, sport, overrides_by_gid=None, summaries=None):
    """Mock client whose side_effect list matches research_game's call order."""
    responses = []
    for gid in _api_gids(game, sport):
        responses.append(_group_response(
            gid,
            (overrides_by_gid or {}).get(gid),
            (summaries or {}).get(gid, "no signal"),
        ))
    client = MagicMock()
    client.messages.create.side_effect = responses
    return client


_OUTDOOR_MLB = "Boston Red Sox @ Colorado Rockies"
_DOMED_MLB = "Boston Red Sox @ Tampa Bay Rays"
_NBA_GAME = "Los Angeles Lakers @ Golden State Warriors"


# ── aggregate_verdict tests (weighted) ─────────────────────────────────────────

def test_aggregate_verdict_confirms():
    """rlm(3) + era_fip(2) confirms → wc=5 ≥ threshold 4 → confirms."""
    factors = _neutral_factors()
    factors["rlm"] = "confirms"
    factors["era_fip"] = "confirms"
    verdict, confidence, wc, wf = cr.aggregate_verdict(factors)
    assert verdict == "confirms", f"Expected confirms, got {verdict}"
    assert wc == 5 and wf == 0
    assert 0.0 <= confidence <= 1.0


def test_aggregate_verdict_fades():
    """injury(3) + line_move(3) fades → wf=6 → fades."""
    factors = _neutral_factors()
    factors["injury"] = "fades"
    factors["line_move"] = "fades"
    verdict, confidence, wc, wf = cr.aggregate_verdict(factors)
    assert verdict == "fades", f"Expected fades, got {verdict}"
    assert wf == 6 and wc == 0
    assert 0.0 <= confidence <= 1.0


def test_weighted_gap_3_is_neutral():
    """A single 3x factor alone (gap=3 < threshold 4) → neutral."""
    factors = _neutral_factors()
    factors["rlm"] = "confirms"
    verdict, confidence, wc, wf = cr.aggregate_verdict(factors)
    assert verdict == "neutral", f"Expected neutral for gap=3, got {verdict}"
    assert wc == 3


def test_aggregate_verdict_neutral_tied():
    """Equal weighted confirms and fades → neutral."""
    factors = _neutral_factors()
    factors["rlm"] = "confirms"     # +3
    factors["injury"] = "fades"     # +3
    verdict, _, wc, wf = cr.aggregate_verdict(factors)
    assert verdict == "neutral"
    assert wc == wf == 3


def test_weighted_aggregation_math():
    """Table-driven check of weights, threshold=4, confidence=max/25."""
    cases = [
        # (overrides, expected verdict, wc, wf)
        ({"rlm": "confirms"}, "neutral", 3, 0),
        ({"rlm": "confirms", "era_fip": "confirms"}, "confirms", 5, 0),
        ({"injury": "fades", "line_move": "fades", "rlm": "confirms"}, "neutral", 3, 6),
        ({"motivation": "fades", "weather": "fades"}, "neutral", 0, 3),
        ({"rlm": "confirms", "injury": "confirms", "weather": "fades"}, "confirms", 6, 1),
    ]
    for overrides, want_verdict, want_wc, want_wf in cases:
        factors = _neutral_factors()
        factors.update(overrides)
        verdict, confidence, wc, wf = cr.aggregate_verdict(factors)
        assert verdict == want_verdict, f"{overrides}: expected {want_verdict}, got {verdict}"
        assert wc == want_wc and wf == want_wf, f"{overrides}: wc={wc} wf={wf}"
        assert confidence == round(max(wc, wf) / cr._MAX_POSSIBLE, 2)


def test_confidence_range():
    """Confidence must always be in [0.0, 1.0]."""
    for n_confirms in range(0, len(cr._FACTORS) + 1):
        factors = _neutral_factors()
        for i, key in enumerate(cr._FACTORS):
            if i < n_confirms:
                factors[key] = "confirms"
        _, confidence, _, _ = cr.aggregate_verdict(factors)
        assert 0.0 <= confidence <= 1.0, f"confidence={confidence} out of range"


def test_confidence_all_confirms():
    factors = {k: "confirms" for k in cr._FACTORS}
    verdict, confidence, wc, wf = cr.aggregate_verdict(factors)
    assert verdict == "confirms"
    assert confidence == 1.0
    assert wc == cr._MAX_POSSIBLE == 25


def test_confidence_all_neutral():
    verdict, confidence, wc, wf = cr.aggregate_verdict(_neutral_factors())
    assert verdict == "neutral"
    assert confidence == 0.0
    assert wc == wf == 0


def test_weights_cover_all_factors():
    assert set(cr._WEIGHTS) == set(cr._FACTORS)
    assert cr._MAX_POSSIBLE == 25


# ── _parse_group_response tests ────────────────────────────────────────────────

def test_parse_group_response_valid():
    raw = json.dumps({
        "factors": {
            "rlm": {"verdict": "confirms", "data_quality": "fresh", "evidence": "68% on X, line toward Y"},
            "line_move": {"verdict": "neutral", "data_quality": "fresh", "evidence": ""},
            "public_sharp": {"verdict": "fades", "data_quality": "stale", "evidence": "old splits"},
        },
        "summary": "RLM toward road dog.",
    })
    out = cr._parse_group_response(raw, 1)
    assert set(out["factors"]) == set(cr._GROUPS[1]["factors"])
    assert out["factors"]["rlm"]["verdict"] == "confirms"
    assert out["factors"]["public_sharp"]["data_quality"] == "stale"
    assert out["summary"] == "RLM toward road dog."


def test_parse_group_response_invalid_verdict_becomes_neutral():
    raw = json.dumps({"factors": {
        f: {"verdict": "gibberish", "data_quality": "fresh", "evidence": ""}
        for f in cr._GROUPS[1]["factors"]
    }, "summary": ""})
    out = cr._parse_group_response(raw, 1)
    assert all(fr["verdict"] == "neutral" for fr in out["factors"].values())


def test_parse_group_response_missing_factor_failed():
    """A factor the model omitted → neutral / failed / source_failed."""
    raw = json.dumps({"factors": {
        "rlm": {"verdict": "confirms", "data_quality": "fresh", "evidence": ""},
    }, "summary": ""})
    out = cr._parse_group_response(raw, 1)
    assert out["factors"]["line_move"]["verdict"] == "neutral"
    assert out["factors"]["line_move"]["data_quality"] == "failed"
    assert out["factors"]["line_move"]["neutral_reason"] == "source_failed"
    assert out["factors"]["rlm"]["verdict"] == "confirms"


def test_parse_group_response_case_insensitive():
    raw = json.dumps({"factors": {
        f: {"verdict": "CONFIRMS", "data_quality": "FRESH", "evidence": ""}
        for f in cr._GROUPS[1]["factors"]
    }, "summary": ""})
    out = cr._parse_group_response(raw, 1)
    assert all(fr["verdict"] == "confirms" for fr in out["factors"].values())
    assert all(fr["data_quality"] == "fresh" for fr in out["factors"].values())


def test_parse_group_response_invalid_quality_becomes_failed():
    raw = json.dumps({"factors": {
        f: {"verdict": "confirms", "data_quality": "bogus", "evidence": ""}
        for f in cr._GROUPS[1]["factors"]
    }, "summary": ""})
    out = cr._parse_group_response(raw, 1)
    assert all(fr["data_quality"] == "failed" for fr in out["factors"].values())


def test_parse_group_response_no_json_raises():
    try:
        cr._parse_group_response("Sorry, I cannot help with that.", 1)
        assert False, "expected ValueError for non-JSON response"
    except ValueError:
        pass


# ── Fast paths / API call counts ───────────────────────────────────────────────

def test_is_indoor():
    assert cr._is_indoor(_NBA_GAME, "NBA")
    assert cr._is_indoor("A @ B", "NHL")
    assert cr._is_indoor("A @ B", "WNBA")
    assert cr._is_indoor(_DOMED_MLB, "MLB")
    assert not cr._is_indoor(_OUTDOOR_MLB, "MLB")


def test_all_five_groups_called_per_outdoor_mlb_game():
    client = _client_for(_OUTDOOR_MLB, "MLB")
    result = cr.research_game(_OUTDOOR_MLB, "MLB", "2026-06-09", client)
    assert client.messages.create.call_count == 5
    assert result is not None


def test_nba_game_makes_three_api_calls():
    """Groups 2 (weather) and 3 (pitching) are fast-pathed for NBA."""
    client = _client_for(_NBA_GAME, "NBA")
    result = cr.research_game(_NBA_GAME, "NBA", "2026-06-09", client)
    assert client.messages.create.call_count == 3
    assert result["factors"]["weather"] == "neutral"
    assert result["neutral_reason"]["weather"] == "hardcoded_neutral"


def test_domed_mlb_game_skips_weather_call():
    client = _client_for(_DOMED_MLB, "MLB")
    result = cr.research_game(_DOMED_MLB, "MLB", "2026-06-09", client)
    assert client.messages.create.call_count == 4
    assert result["factors"]["weather"] == "neutral"
    assert result["neutral_reason"]["weather"] == "hardcoded_neutral"
    assert result["data_quality"]["weather"] == "fresh"


def test_non_mlb_pitching_factors_not_applicable():
    client = _client_for(_NBA_GAME, "NBA")
    result = cr.research_game(_NBA_GAME, "NBA", "2026-06-09", client)
    for f in ("era_fip", "bullpen", "umpire"):
        assert result["factors"][f] == "neutral"
        assert result["neutral_reason"][f] == "not_applicable"


def test_build_group_prompt_contains_queries():
    prompt = cr._build_group_prompt(1, _OUTDOOR_MLB, "MLB", "2026-06-09")
    assert "Boston Red Sox" in prompt
    assert "Colorado Rockies" in prompt
    assert "2026-06-09" in prompt
    assert "actionnetwork.com" in prompt
    assert '"rlm"' in prompt  # JSON skeleton present


# ── Group failure isolation ────────────────────────────────────────────────────

def test_group_failure_isolated():
    """Group 1 raising must not kill the other groups or the game result."""
    gids = _api_gids(_OUTDOOR_MLB, "MLB")  # [1, 2, 3, 4, 5]
    responses = []
    for gid in gids:
        if gid == 1:
            responses.append(Exception("connection failed"))
        elif gid == 4:
            responses.append(_group_response(4, {"pythag": {"verdict": "confirms"}}))
        else:
            responses.append(_group_response(gid))
    client = MagicMock()
    client.messages.create.side_effect = responses

    result = cr.research_game(_OUTDOOR_MLB, "MLB", "2026-06-09", client)
    assert result is not None
    # Failed group degrades to neutral/failed/source_failed
    for f in cr._GROUPS[1]["factors"]:
        assert result["factors"][f] == "neutral"
        assert result["data_quality"][f] == "failed"
        assert result["neutral_reason"][f] == "source_failed"
    # Other groups intact
    assert result["factors"]["pythag"] == "confirms"
    assert result["data_quality"]["pythag"] == "fresh"


def test_research_game_all_groups_fail_degrades_to_neutral():
    """Every API call failing → entry still produced, visibly all-failed."""
    client = MagicMock()
    client.messages.create.side_effect = Exception("connection failed")

    result = cr.research_game(_NBA_GAME, "NBA", "2026-06-09", client)
    assert result is not None
    assert result["verdict"] == "neutral"
    for f in ("rlm", "pythag", "injury"):
        assert result["data_quality"][f] == "failed"
        assert result["neutral_reason"][f] == "source_failed"
    # Hardcoded fast paths are not "failed"
    assert result["data_quality"]["weather"] == "fresh"


def test_research_game_malformed_json_degrades():
    """Non-JSON text from one group → that group failed, entry still produced."""
    gids = _api_gids(_NBA_GAME, "NBA")  # [1, 4, 5]
    responses = [_mk_response("Sorry, I cannot help with that.")]
    responses += [_group_response(gid) for gid in gids[1:]]
    client = MagicMock()
    client.messages.create.side_effect = responses

    result = cr.research_game(_NBA_GAME, "NBA", "2026-06-09", client)
    assert result is not None
    assert result["data_quality"]["rlm"] == "failed"
    assert result["data_quality"]["pythag"] == "fresh"


# ── Data-quality overrides / neutral_reason ────────────────────────────────────

def test_stale_overrides_to_neutral():
    """Stale data never drives a verdict — confirms/stale → neutral, excluded from weights."""
    client = _client_for(_NBA_GAME, "NBA", overrides_by_gid={
        5: {"injury": {"verdict": "confirms", "data_quality": "stale"}},
    })
    result = cr.research_game(_NBA_GAME, "NBA", "2026-06-09", client)
    assert result["factors"]["injury"] == "neutral"
    assert result["data_quality"]["injury"] == "stale"
    assert result["neutral_reason"]["injury"] == "stale_data"
    assert result["weighted_confirms"] == 0  # injury(3x) must not count


def test_failed_overrides_to_neutral():
    fr = {"verdict": "fades", "data_quality": "failed", "neutral_reason": None, "evidence": ""}
    out = cr._apply_quality_override(fr)
    assert out["verdict"] == "neutral"
    assert out["neutral_reason"] == "source_failed"


def test_neutral_reason_population():
    """fresh neutral → researched_neutral; non-neutral → None; fast paths keep theirs."""
    client = _client_for(_NBA_GAME, "NBA", overrides_by_gid={
        1: {"rlm": {"verdict": "confirms"}},
    })
    result = cr.research_game(_NBA_GAME, "NBA", "2026-06-09", client)
    assert result["neutral_reason"]["rlm"] is None
    assert result["neutral_reason"]["pythag"] == "researched_neutral"
    assert result["neutral_reason"]["weather"] == "hardcoded_neutral"
    assert result["neutral_reason"]["era_fip"] == "not_applicable"


def test_neutral_reason_values_valid():
    client = _client_for(_NBA_GAME, "NBA")
    result = cr.research_game(_NBA_GAME, "NBA", "2026-06-09", client)
    for f, reason in result["neutral_reason"].items():
        assert reason is None or reason in cr._NEUTRAL_REASONS, f"{f}: {reason!r}"


# ── Output schema tests ────────────────────────────────────────────────────────

_REQUIRED_FIELDS = {
    "game", "date", "sport", "verdict", "confidence", "factors", "summary",
    "researched_at", "data_quality", "neutral_reason",
    "weighted_confirms", "weighted_fades",
}
_VALID_VERDICTS = {"confirms", "fades", "neutral"}


def _real_entry(overrides_by_gid=None):
    """Assemble a real entry through research_game with a mocked client."""
    client = _client_for(_OUTDOOR_MLB, "MLB", overrides_by_gid)
    return cr.research_game(_OUTDOOR_MLB, "MLB", "2026-06-09", client)


def test_output_schema_required_fields():
    v = _real_entry()
    for field in _REQUIRED_FIELDS:
        assert field in v, f"Missing required field: {field!r}"


def test_verdict_valid_values():
    v = _real_entry()
    assert v["verdict"] in _VALID_VERDICTS


def test_factor_valid_values():
    v = _real_entry()
    for key, val in v["factors"].items():
        assert val in cr._VALID_VALUES, f"Factor {key!r} has invalid value {val!r}"


def test_confidence_is_float_in_range():
    v = _real_entry({1: {"rlm": {"verdict": "confirms"}}})
    assert isinstance(v["confidence"], float)
    assert 0.0 <= v["confidence"] <= 1.0


def test_factors_has_all_keys():
    v = _real_entry()
    assert set(v["factors"].keys()) == set(cr._FACTORS)
    assert set(v["data_quality"].keys()) == set(cr._FACTORS)
    assert set(v["neutral_reason"].keys()) == set(cr._FACTORS)


def test_data_quality_valid_values():
    v = _real_entry()
    for key, val in v["data_quality"].items():
        assert val in cr._DATA_QUALITY_VALUES, f"{key}: {val!r}"


def test_weighted_counts_are_ints():
    v = _real_entry({1: {"rlm": {"verdict": "confirms"}}})
    assert isinstance(v["weighted_confirms"], int)
    assert isinstance(v["weighted_fades"], int)
    assert v["weighted_confirms"] == 3


def test_entry_is_json_serializable():
    v = _real_entry()
    json.dumps(v)  # must not raise (neutral_reason None → null)


# ── research_game integration ──────────────────────────────────────────────────

def test_research_game_mock_api():
    """research_game() assembles mocked group responses correctly."""
    result = _real_entry({
        1: {"rlm": {"verdict": "confirms", "evidence": "68% public on home, line moved away"},
            "line_move": {"verdict": "confirms"}},
        5: {"travel": {"verdict": "fades"}},
    })
    assert result["game"] == _OUTDOOR_MLB
    assert result["sport"] == "MLB"
    assert result["date"] == "2026-06-09"
    assert result["factors"]["rlm"] == "confirms"
    assert result["factors"]["travel"] == "fades"
    # wc = rlm(3) + line_move(3) = 6, wf = travel(1) = 1 → diff 5 ≥ 4 → confirms
    assert result["verdict"] == "confirms"
    assert result["weighted_confirms"] == 6
    assert result["weighted_fades"] == 1
    assert "researched_at" in result
    assert result["summary"]


def test_compose_summary_prefers_signal_groups():
    client = _client_for(_NBA_GAME, "NBA",
                         overrides_by_gid={4: {"pythag": {"verdict": "confirms"}}},
                         summaries={1: "no odds signal", 4: "Team outperforming pythag."})
    result = cr.research_game(_NBA_GAME, "NBA", "2026-06-09", client)
    assert "pythag" in result["summary"].lower() or "Team outperforming" in result["summary"]
    assert len(result["summary"]) <= 300


# ── Daily cache / merge tests ──────────────────────────────────────────────────

def _entry(game, date, sport="MLB", verdict="neutral"):
    return {"game": game, "date": date, "sport": sport, "verdict": verdict}


def test_split_cache_today_only():
    existing = [
        _entry("A @ B", "2026-06-09"),
        _entry("C @ D", "2026-06-08"),
        {"no_game_key": True},
    ]
    cache = cr._split_cache(existing, "2026-06-09")
    assert set(cache) == {"A @ B"}


def test_daily_cache_hit_skips_research():
    games = [{"game": "A @ B", "sport": "MLB"}, {"game": "C @ D", "sport": "MLB"}]
    cache = {"A @ B": _entry("A @ B", "2026-06-09")}
    to_research, cached = cr._partition_games(games, cache, refresh=False)
    assert [g["game"] for g in to_research] == ["C @ D"]
    assert [e["game"] for e in cached] == ["A @ B"]


def test_refresh_bypasses_cache():
    games = [{"game": "A @ B", "sport": "MLB"}]
    cache = {"A @ B": _entry("A @ B", "2026-06-09")}
    to_research, cached = cr._partition_games(games, cache, refresh=True)
    assert len(to_research) == 1
    assert cached == []


def test_sport_all_merge_preserves_other_sports():
    """New NBA entries must not clobber MLB entries researched today."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "context_verdicts.json"
        existing = [_entry("A @ B", "2026-06-09", sport="MLB")]
        new = [_entry("C @ D", "2026-06-09", sport="NBA")]
        merged = cr._write_merged(new, existing, path, "2026-06-09")
        on_disk = json.loads(path.read_text(encoding="utf-8"))
        games = {e["game"] for e in on_disk}
        assert games == {"A @ B", "C @ D"}
        assert merged == on_disk


def test_merge_prunes_older_dates():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "context_verdicts.json"
        existing = [
            _entry("A @ B", "2026-06-08"),   # yesterday, same matchup as new
            _entry("E @ F", "2026-06-08"),   # yesterday, unrelated
        ]
        new = [_entry("A @ B", "2026-06-09")]
        cr._write_merged(new, existing, path, "2026-06-09")
        on_disk = json.loads(path.read_text(encoding="utf-8"))
        assert len(on_disk) == 1
        assert on_disk[0]["date"] == "2026-06-09"


def test_merge_supersedes_same_game_today():
    """--refresh re-research replaces today's existing entry for that game."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "context_verdicts.json"
        existing = [_entry("A @ B", "2026-06-09", verdict="fades")]
        new = [_entry("A @ B", "2026-06-09", verdict="confirms")]
        cr._write_merged(new, existing, path, "2026-06-09")
        on_disk = json.loads(path.read_text(encoding="utf-8"))
        assert len(on_disk) == 1
        assert on_disk[0]["verdict"] == "confirms"


def test_atomic_write_used():
    """Guards regression to plain write_text — merged write must be atomic."""
    with patch.object(cr, "atomic_write_json") as mock_write:
        new = [_entry("A @ B", "2026-06-09")]
        cr._write_merged(new, [], Path("unused.json"), "2026-06-09")
        mock_write.assert_called_once()
        _, written = mock_write.call_args[0]
        assert written == new


def test_load_existing_verdicts_missing_file():
    assert cr._load_existing_verdicts(Path("does_not_exist_12345.json")) == []


def test_load_existing_verdicts_corrupt_file():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "context_verdicts.json"
        path.write_text("{not json", encoding="utf-8")
        assert cr._load_existing_verdicts(path) == []


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
