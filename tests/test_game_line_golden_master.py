"""Golden-master safety net for analyze_game_lines.py (game-line pricer collapse).

analyze_game_lines.py has NO replay coverage — the run_picks replay harness
explicitly excludes game lines ("No game lines — use analyze_game_lines.py").
This pins the structured priced output (ALL_BETS: model prob + edge + odds per
market) for a frozen synthetic fixture that exercises every market the analyzer
prices: MLB ML / spread / total / team-total (NB, push-adjusted) / F5 total /
F5 ML / F5 spread, plus the NBA Normal markets (ML / total / team-total).

Purpose: prove the upcoming collapse — routing the per-market math through a
shared engine (engine/game_line_pricing.py) — is BYTE-IDENTICAL. model/edge must
match the golden exactly (Python float repr round-trips through JSON losslessly,
so == is an exact bit comparison).

The fixture is fully deterministic: frozen games_data + team_projs (no live
/odds call) and a monkeypatched fetch_event_odds (the only live call inside
analyze_mlb/analyze_nba) returning frozen team-total + F5 odds.

Refresh the golden ONLY after an INTENTIONAL pricing change (e.g. Commit 2 turns
on market anchoring), and review the diff first:
    python tests/test_game_line_golden_master.py --capture
"""
import json
import sys
from pathlib import Path

# Repo root + engine/ on path so this runs both under pytest (conftest already
# adds engine/) and as a direct `python tests/...` capture invocation.
_REPO = Path(__file__).resolve().parent.parent
for _p in (str(_REPO), str(_REPO / "engine")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import analyze_game_lines as agl  # noqa: E402

_GOLDEN = Path(__file__).parent / "data" / "game_line_golden.json"
_FIELDS = ("sport", "game", "label", "model", "edge", "odds", "book", "line")

# ── Frozen event odds (team_totals + F5), per sport ──────────────────────────
_MLB_EVENT_ODDS = {
    "bookmakers": [{
        "title": "DraftKings",
        "markets": [
            {"key": "team_totals", "outcomes": [
                {"name": "Over",  "description": "New York Yankees", "price": -110, "point": 4.5},
                {"name": "Under", "description": "New York Yankees", "price": -110, "point": 4.5},
                {"name": "Over",  "description": "Boston Red Sox",   "price": -110, "point": 4.0},
                {"name": "Under", "description": "Boston Red Sox",   "price": -110, "point": 4.0},
            ]},
            {"key": "totals_1st_5_innings", "outcomes": [
                {"name": "Over", "price": -110, "point": 4.5}, {"name": "Under", "price": -110, "point": 4.5}]},
            {"key": "h2h_1st_5_innings", "outcomes": [
                {"name": "New York Yankees", "price": -125}, {"name": "Boston Red Sox", "price": 105}]},
            {"key": "spreads_1st_5_innings", "outcomes": [
                {"name": "New York Yankees", "price": -110, "point": -0.5},
                {"name": "Boston Red Sox",   "price": -110, "point": 0.5}]},
        ],
    }],
}
_NBA_EVENT_ODDS = {
    "bookmakers": [{
        "title": "DraftKings",
        "markets": [
            {"key": "team_totals", "outcomes": [
                {"name": "Over",  "description": "Boston Celtics",  "price": -110, "point": 105.5},
                {"name": "Under", "description": "Boston Celtics",  "price": -110, "point": 105.5},
                {"name": "Over",  "description": "New York Knicks", "price": -110, "point": 110.5},
                {"name": "Under", "description": "New York Knicks", "price": -110, "point": 110.5},
            ]},
        ],
    }],
}


def _patched_event_odds(sport_key, event_id, markets):
    return _NBA_EVENT_ODDS if "basketball" in sport_key else _MLB_EVENT_ODDS


_MLB_GAME = {
    "id": "evt_mlb_1",
    "away_team": "Boston Red Sox",
    "home_team": "New York Yankees",
    "commence_time": "2026-06-15T23:30:00Z",
    "bookmakers": [{
        "title": "DraftKings",
        "markets": [
            {"key": "h2h", "outcomes": [
                {"name": "Boston Red Sox", "price": 140}, {"name": "New York Yankees", "price": -160}]},
            {"key": "spreads", "outcomes": [
                {"name": "New York Yankees", "price": -110, "point": -1.5},
                {"name": "Boston Red Sox",   "price": -110, "point": 1.5}]},
            {"key": "totals", "outcomes": [
                {"name": "Over", "price": -105, "point": 8.0}, {"name": "Under", "price": -115, "point": 8.0}]},
        ],
    }],
}
_NBA_GAME = {
    "id": "evt_nba_1",
    "away_team": "Boston Celtics",
    "home_team": "New York Knicks",
    "commence_time": "2026-06-15T23:30:00Z",
    "bookmakers": [{
        "title": "DraftKings",
        "markets": [
            {"key": "h2h", "outcomes": [
                {"name": "Boston Celtics", "price": 120}, {"name": "New York Knicks", "price": -140}]},
            {"key": "spreads", "outcomes": [
                {"name": "New York Knicks", "price": -110, "point": -3.5},
                {"name": "Boston Celtics",  "price": -110, "point": 3.5}]},
            {"key": "totals", "outcomes": [
                {"name": "Over", "price": -110, "point": 218.5}, {"name": "Under", "price": -110, "point": 218.5}]},
        ],
    }],
}


def _price_fixture():
    """Run the frozen fixture through the analyzers; return the priced rows."""
    orig = agl.fetch_event_odds
    agl.fetch_event_odds = _patched_event_odds
    try:
        agl.ALL_BETS.clear()
        agl.analyze_mlb([_MLB_GAME], team_projs={"BOS": 4.6, "NYY": 4.4}, ctx_verdicts=None)
        agl.analyze_nba([_NBA_GAME], team_projs={"BOS": 110.0, "NYK": 114.0}, ctx_verdicts=None)
        return [{k: b.get(k) for k in _FIELDS} for b in agl.ALL_BETS]
    finally:
        agl.fetch_event_odds = orig
        agl.ALL_BETS.clear()


def test_game_line_golden_master():
    got = _price_fixture()
    assert _GOLDEN.exists(), "golden missing — run: python tests/test_game_line_golden_master.py --capture"
    expected = json.loads(_GOLDEN.read_text(encoding="utf-8"))
    assert got == expected, (
        "game-line priced output drifted from golden. If intentional, refresh with "
        "`python tests/test_game_line_golden_master.py --capture` and review the diff."
    )


if __name__ == "__main__":
    import sys

    rows = _price_fixture()
    if "--capture" in sys.argv:
        _GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        _GOLDEN.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
        print(f"captured {len(rows)} priced rows -> {_GOLDEN}")
    else:
        print(json.dumps(rows, indent=2))
