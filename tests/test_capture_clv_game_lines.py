"""test_capture_clv_game_lines.py — game-line CLV capture in capture_clv.py.

Covers the additive game-line path (pick_log_game_lines.csv):
  - GAME_LINE_CLV_MARKET stat→market mapping (6 stats; TEAM_TOTAL deferred)
  - _gl_resolve_abbr: full team name → log abbreviation (exact + substring)
  - find_game_line_event: abbreviated 'AWAY@HOME' tag → API event
  - get_game_line_closing_odds: TOTAL / SPREAD / ML matching + TEAM_TOTAL→None

Run:
    python tests/test_capture_clv_game_lines.py
    # or: python -m pytest tests/test_capture_clv_game_lines.py -v
"""

import sys
from pathlib import Path

ENGINE_DIR = Path(__file__).resolve().parent.parent / "engine"
sys.path.insert(0, str(ENGINE_DIR))

import capture_clv  # noqa: E402

# A guaranteed Colorado-legal book key for synthetic outcomes.
_BOOK = next(iter(capture_clv.CO_LEGAL_BOOKS))


def _oc(name, price, point=None, description="", book=_BOOK):
    return {"name": name, "description": description, "price": price,
            "point": point, "book": book}


# ── Market mapping ─────────────────────────────────────────────────────────────

def test_market_map_covers_six_stats():
    m = capture_clv.GAME_LINE_CLV_MARKET
    assert m == {
        "TOTAL": "totals",
        "SPREAD": "spreads",
        "ML": "h2h",
        "F5_TOTAL": "totals_1st_5_innings",
        "F5_SPREAD": "spreads_1st_5_innings",
        "F5_ML": "h2h_1st_5_innings",
    }


def test_team_total_deferred():
    assert "TEAM_TOTAL" not in capture_clv.GAME_LINE_CLV_MARKET
    out = capture_clv.get_game_line_closing_odds(
        {"stat": "TEAM_TOTAL", "direction": "over", "line": "4.5"},
        {"team_totals": [_oc("Over", -110, 4.5)]},
        home_team="New York Yankees", away_team="Boston Red Sox",
    )
    assert out == (None, "")


# ── Abbreviation resolution ────────────────────────────────────────────────────

def test_resolve_abbr_exact():
    assert capture_clv._gl_resolve_abbr("MLB", "New York Yankees") == "NYY"
    assert capture_clv._gl_resolve_abbr("MLB", "Boston Red Sox") == "BOS"
    assert capture_clv._gl_resolve_abbr("NBA", "San Antonio Spurs") == "SAS"


def test_resolve_abbr_miss():
    assert capture_clv._gl_resolve_abbr("MLB", "Nonexistent Team") == ""
    assert capture_clv._gl_resolve_abbr("NFL", "New York Yankees") == ""  # sport not mapped


# ── Event matching ─────────────────────────────────────────────────────────────

_EVENTS = [{
    "id": "evt1",
    "home_team": "New York Yankees",
    "away_team": "Boston Red Sox",
    "commence_time": "2026-06-09T23:05:00Z",
}]


def test_find_event_matches_abbrev_tag():
    ev = capture_clv.find_game_line_event("BOS@NYY", _EVENTS, "MLB")
    assert ev is not None and ev["id"] == "evt1"


def test_find_event_rejects_wrong_order():
    # 'NYY@BOS' means away=NYY home=BOS — does not match the event.
    assert capture_clv.find_game_line_event("NYY@BOS", _EVENTS, "MLB") is None


def test_find_event_none_without_at():
    assert capture_clv.find_game_line_event("NYY", _EVENTS, "MLB") is None


# ── Closing-odds matching ──────────────────────────────────────────────────────

def test_total_over_under():
    outcomes = {"totals": [_oc("Over", -105, 8.5), _oc("Under", -115, 8.5)]}
    assert capture_clv.get_game_line_closing_odds(
        {"stat": "TOTAL", "direction": "over", "line": "8.5"}, outcomes)[0] == -105
    assert capture_clv.get_game_line_closing_odds(
        {"stat": "TOTAL", "direction": "under", "line": "8.5"}, outcomes)[0] == -115


def test_spread_home_away_with_line():
    outcomes = {"spreads": [
        _oc("New York Yankees", -120, -1.5),
        _oc("Boston Red Sox", +100, 1.5),
    ]}
    row_home = {"stat": "SPREAD", "direction": "home", "line": "-1.5"}
    row_away = {"stat": "SPREAD", "direction": "away", "line": "1.5"}
    assert capture_clv.get_game_line_closing_odds(
        row_home, outcomes, "New York Yankees", "Boston Red Sox")[0] == -120
    assert capture_clv.get_game_line_closing_odds(
        row_away, outcomes, "New York Yankees", "Boston Red Sox")[0] == +100


def test_spread_line_mismatch_skipped():
    # Outcome point 2.5 is >0.25 from row line 1.5 → no match.
    outcomes = {"spreads": [_oc("Boston Red Sox", +100, 2.5)]}
    row = {"stat": "SPREAD", "direction": "away", "line": "1.5"}
    assert capture_clv.get_game_line_closing_odds(
        row, outcomes, "New York Yankees", "Boston Red Sox") == (None, "")


def test_moneyline_home_away():
    outcomes = {"h2h": [
        _oc("New York Yankees", -150),
        _oc("Boston Red Sox", +130),
    ]}
    assert capture_clv.get_game_line_closing_odds(
        {"stat": "ML", "direction": "home"}, outcomes,
        "New York Yankees", "Boston Red Sox")[0] == -150
    assert capture_clv.get_game_line_closing_odds(
        {"stat": "ML", "direction": "away"}, outcomes,
        "New York Yankees", "Boston Red Sox")[0] == +130


def test_moneyline_picks_best_price_across_books():
    outcomes = {"h2h": [
        _oc("New York Yankees", -150, book=_BOOK),
        _oc("New York Yankees", -140, book=_BOOK),  # better (higher) price
    ]}
    odds, _ = capture_clv.get_game_line_closing_odds(
        {"stat": "ML", "direction": "home"}, outcomes,
        "New York Yankees", "Boston Red Sox")
    assert odds == -140


def test_f5_total_uses_first5_market():
    # F5_TOTAL must read the totals_1st_5_innings market, not full-game totals.
    outcomes = {
        "totals_1st_5_innings": [_oc("Over", -110, 4.5)],
        "totals": [_oc("Over", +999, 4.5)],  # decoy — must be ignored
    }
    assert capture_clv.get_game_line_closing_odds(
        {"stat": "F5_TOTAL", "direction": "over", "line": "4.5"}, outcomes)[0] == -110


# ── End-to-end: find → match → calc → write ────────────────────────────────────

def test_process_game_lines_end_to_end():
    import csv as _csv
    import tempfile
    from datetime import datetime, timedelta, timezone
    from pathlib import Path as _Path
    from pick_log_schema import CANONICAL_HEADER

    now = datetime.now(timezone.utc)
    commence = (now + timedelta(seconds=300)).strftime("%Y-%m-%dT%H:%M:%SZ")  # T-5min: write gate open
    date_str = now.strftime("%Y-%m-%d")

    event = {"id": "evt1", "home_team": "New York Yankees",
             "away_team": "Boston Red Sox", "commence_time": commence}
    event_data = {"bookmakers": [{"key": _BOOK, "markets": [
        {"key": "totals", "outcomes": [
            {"name": "Over", "price": -110, "point": 8.5},
            {"name": "Under", "price": -110, "point": 8.5}]},
        {"key": "h2h", "outcomes": [
            {"name": "New York Yankees", "price": -150},
            {"name": "Boston Red Sox", "price": 130}]},
    ]}]}

    def _base_row(stat, direction, line, odds):
        r = {c: "" for c in CANONICAL_HEADER}
        r.update({"date": date_str, "run_type": "game_line", "sport": "MLB",
                  "player": "BOS@NYY", "team": "NYY", "stat": stat, "line": line,
                  "direction": direction, "odds": odds, "book": _BOOK, "tier": "T2",
                  "game": "BOS@NYY", "card_slot": "GL",
                  "is_home": "1" if direction == "home" else "0"})
        return r

    tmpdir = tempfile.mkdtemp()
    tmp_csv = _Path(tmpdir) / "pick_log_game_lines.csv"
    with open(tmp_csv, "w", newline="", encoding="utf-8") as f:
        w = _csv.DictWriter(f, fieldnames=CANONICAL_HEADER, extrasaction="ignore")
        w.writeheader()
        w.writerow(_base_row("TOTAL", "over", "8.5", "-105"))
        w.writerow(_base_row("ML", "home", "", "-140"))

    orig_path = capture_clv.PICK_LOG_GAME_LINES
    orig_events = capture_clv.fetch_events
    orig_odds = capture_clv.fetch_game_odds
    try:
        capture_clv.PICK_LOG_GAME_LINES = tmp_csv
        capture_clv.fetch_events = lambda sport_key: [event]
        capture_clv.fetch_game_odds = lambda eid, sk, markets: event_data

        pending, _ = capture_clv.process_game_lines(date_str, now)
        assert pending == 0, f"expected all captured, {pending} still open"

        with open(tmp_csv, newline="", encoding="utf-8") as f:
            rows = list(_csv.DictReader(f))
        by_stat = {r["stat"]: r for r in rows}
        assert by_stat["TOTAL"]["closing_odds"] == "-110"
        assert by_stat["TOTAL"]["clv"].strip() != ""
        assert by_stat["ML"]["closing_odds"] == "-150"
        assert by_stat["ML"]["clv"].strip() != ""
    finally:
        capture_clv.PICK_LOG_GAME_LINES = orig_path
        capture_clv.fetch_events = orig_events
        capture_clv.fetch_game_odds = orig_odds


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"  PASS  {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"  FAIL  {fn.__name__}: {e}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)
