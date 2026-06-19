"""test_context_research_v2.py — rest/travel wiring for NBA/WNBA + the MLB B2B fix.

Covers the sport dispatch added to _factor_rest / _factor_travel in
context_research_v2.py: NBA/WNBA now resolve recent games via ESPN, and MLB
back-to-back detection (previously unreachable — it tested gap==0) now fires at
gap==1. All schedule fetchers are monkeypatched; no live network calls.
"""

from datetime import date, timedelta

import context_research_v2 as crv2


def _today():
    return date.fromisoformat(crv2._today_local())


def _canonical(d):
    """A factor dict must always carry exactly the 4 canonical keys."""
    return set(d) == {"verdict", "data_quality", "neutral_reason", "evidence"}


# ── ESPN-backed rest (NBA / WNBA) ────────────────────────────────────────────────

def _wire_espn(monkeypatch, ids, games_by_id):
    """ids: {team_name: id}; games_by_id: {id: [{date,...}, ...]} newest-first."""
    monkeypatch.setattr(crv2, "_espn_team_id",
                        lambda sport, name: ids.get(name))
    monkeypatch.setattr(crv2, "_espn_team_recent_games",
                        lambda sport, tid: games_by_id.get(tid, []))


def test_rest_nba_confirms_home_rested_away_b2b(monkeypatch):
    today = _today()
    game = "Los Angeles Lakers @ Boston Celtics"  # away @ home
    _wire_espn(
        monkeypatch,
        ids={"Boston Celtics": 2, "Los Angeles Lakers": 13},
        games_by_id={
            2: [{"date": today - timedelta(days=3)}],   # home rested (gap 3)
            13: [{"date": today - timedelta(days=1)}],  # away B2B (gap 1)
        },
    )
    r = crv2._factor_rest(game, "NBA")
    assert _canonical(r)
    assert r["verdict"] == "confirms" and r["data_quality"] == "fresh"


def test_rest_nba_fades_away_rested_home_b2b(monkeypatch):
    today = _today()
    game = "Los Angeles Lakers @ Boston Celtics"
    _wire_espn(
        monkeypatch,
        ids={"Boston Celtics": 2, "Los Angeles Lakers": 13},
        games_by_id={
            2: [{"date": today - timedelta(days=1)}],   # home B2B
            13: [{"date": today - timedelta(days=3)}],  # away rested
        },
    )
    r = crv2._factor_rest(game, "NBA")
    assert r["verdict"] == "fades"


def test_rest_wnba_neutral_both_rested(monkeypatch):
    today = _today()
    game = "Las Vegas Aces @ New York Liberty"
    _wire_espn(
        monkeypatch,
        ids={"New York Liberty": 9, "Las Vegas Aces": 17},
        games_by_id={
            9: [{"date": today - timedelta(days=2)}],
            17: [{"date": today - timedelta(days=2)}],
        },
    )
    r = crv2._factor_rest(game, "WNBA")
    assert r["verdict"] == "neutral" and r["neutral_reason"] == "researched_neutral"


def test_rest_nba_stale_when_team_id_missing(monkeypatch):
    monkeypatch.setattr(crv2, "_espn_team_id", lambda sport, name: None)
    monkeypatch.setattr(crv2, "_espn_team_recent_games", lambda sport, tid: [])
    r = crv2._factor_rest("Los Angeles Lakers @ Boston Celtics", "NBA")
    # stale → override forces neutral
    assert r["verdict"] == "neutral" and r["data_quality"] == "stale"


def test_rest_nba_stale_when_schedule_empty(monkeypatch):
    _wire_espn(
        monkeypatch,
        ids={"Boston Celtics": 2, "Los Angeles Lakers": 13},
        games_by_id={2: [], 13: []},
    )
    r = crv2._factor_rest("Los Angeles Lakers @ Boston Celtics", "NBA")
    assert r["verdict"] == "neutral" and r["data_quality"] == "stale"


# ── MLB B2B regression (gap==1 now fires) ────────────────────────────────────────

def test_rest_mlb_b2b_now_fires(monkeypatch):
    """Home rested (gap 3) + away B2B (gap 1) → confirms. Pre-fix this returned
    neutral because the old code tested gap==0, which the window makes unreachable."""
    today = _today()
    game = "Boston Red Sox @ New York Yankees"  # BOS away, NYY home
    nyy = crv2._MLB_NAME_TO_ID["New York Yankees"]
    bos = crv2._MLB_NAME_TO_ID["Boston Red Sox"]
    last_by_id = {
        nyy: today - timedelta(days=3),  # home rested
        bos: today - timedelta(days=1),  # away B2B
    }

    def fake_sched(tid, start, end):
        return [{"date": last_by_id[tid], "home_id": tid, "away_id": 0}]

    monkeypatch.setattr(crv2, "_mlb_team_schedule", fake_sched)
    r = crv2._factor_rest(game, "MLB")
    assert r["verdict"] == "confirms"


# ── ESPN-backed travel (NBA / WNBA) ──────────────────────────────────────────────

def test_travel_nba_fades_eastward_shift(monkeypatch):
    today = _today()
    game = "Los Angeles Lakers @ Boston Celtics"  # tonight ET (offset 0)
    monkeypatch.setattr(crv2, "_espn_team_id", lambda sport, name: 13)
    # Away team's previous game was hosted by a PT team (offset -3) → +3 east.
    monkeypatch.setattr(
        crv2, "_espn_team_recent_games",
        lambda sport, tid: [{"date": today - timedelta(days=2),
                             "is_home": False,
                             "home_name": "Golden State Warriors",
                             "away_name": "Los Angeles Lakers"}],
    )
    r = crv2._factor_travel(game, "NBA")
    assert _canonical(r)
    assert r["verdict"] == "fades" and r["data_quality"] == "fresh"


def test_travel_nba_neutral_same_tz(monkeypatch):
    today = _today()
    game = "Brooklyn Nets @ Boston Celtics"  # both ET
    monkeypatch.setattr(crv2, "_espn_team_id", lambda sport, name: 17)
    monkeypatch.setattr(
        crv2, "_espn_team_recent_games",
        lambda sport, tid: [{"date": today - timedelta(days=2),
                             "is_home": False,
                             "home_name": "New York Knicks",  # ET
                             "away_name": "Brooklyn Nets"}],
    )
    r = crv2._factor_travel(game, "NBA")
    assert r["verdict"] == "neutral" and r["neutral_reason"] == "researched_neutral"


def test_travel_stale_when_tonight_tz_unknown(monkeypatch):
    # Unmapped home team → tonight's tz unknown → stale.
    r = crv2._factor_travel("Los Angeles Lakers @ Fake Team FC", "NBA")
    assert r["verdict"] == "neutral" and r["data_quality"] == "stale"


def test_travel_nba_stale_when_no_recent_game(monkeypatch):
    monkeypatch.setattr(crv2, "_espn_team_id", lambda sport, name: 13)
    monkeypatch.setattr(crv2, "_espn_team_recent_games", lambda sport, tid: [])
    r = crv2._factor_travel("Los Angeles Lakers @ Boston Celtics", "NBA")
    assert r["verdict"] == "neutral" and r["data_quality"] == "stale"


# ── graceful degradation: never raises ───────────────────────────────────────────

def test_rest_travel_never_raise_on_fetcher_error(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("network down")
    monkeypatch.setattr(crv2, "_espn_team_id", boom)
    monkeypatch.setattr(crv2, "_espn_team_recent_games", boom)
    for fn in (crv2._factor_rest, crv2._factor_travel):
        r = fn("Los Angeles Lakers @ Boston Celtics", "NBA")
        assert _canonical(r) and r["verdict"] == "neutral"


def test_unsupported_sport_stays_stale():
    for fn in (crv2._factor_rest, crv2._factor_travel):
        r = fn("A @ B", "NHL")
        assert r["verdict"] == "neutral" and r["data_quality"] == "stale"


# ── NBA/WNBA short-name normalization (ESPN / nba_api vs Odds-API full names) ─────

def test_canon_team_la_variants():
    assert crv2._canon_team("LA Clippers") == "Los Angeles Clippers"
    assert crv2._canon_team("LA Lakers") == "Los Angeles Lakers"
    assert crv2._canon_team("LA Sparks") == "Los Angeles Sparks"


def test_canon_team_passthrough_and_no_false_expansion():
    # Already-canonical names are unchanged...
    assert crv2._canon_team("Boston Celtics") == "Boston Celtics"
    assert crv2._canon_team("Los Angeles Lakers") == "Los Angeles Lakers"
    # ...and "Las Vegas"/other non-"LA " names are not mangled by the prefix rule.
    assert crv2._canon_team("Las Vegas Aces") == "Las Vegas Aces"
    assert crv2._canon_team("Golden State Warriors") == "Golden State Warriors"


def test_name_match_resolves_clippers_variant():
    # The substring matcher misses raw, but canonicalization makes it hit.
    assert crv2._name_match("Los Angeles Clippers", "LA Clippers")
    assert not crv2._name_match("Los Angeles Clippers", "Los Angeles Lakers")


def test_espn_team_id_resolves_full_name_against_short_scoreboard(monkeypatch):
    fake_sb = {"events": [{"competitions": [{"competitors": [
        {"team": {"id": "12", "displayName": "LA Clippers"}},
        {"team": {"id": "13", "displayName": "Los Angeles Lakers"}},
    ]}]}]}
    monkeypatch.setattr(crv2, "_espn_scoreboard", lambda sport: fake_sb)
    # Odds-API full name resolves against ESPN's short "LA Clippers".
    assert crv2._espn_team_id("NBA", "Los Angeles Clippers") == 12
    assert crv2._espn_team_id("NBA", "Los Angeles Lakers") == 13
