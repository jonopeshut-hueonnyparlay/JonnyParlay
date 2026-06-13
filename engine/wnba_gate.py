"""WNBA early-season confidence factor and opening-gate games-played helper.

Extracted from run_picks.py (extract-and-re-export refactor, Step 3) and
re-imported there so existing call sites and `from run_picks import ...` keep
resolving. Imports only {stdlib, secrets_config, market_config, thresholds} —
never run_picks or the other extracted modules.
"""
import logging
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from secrets_config import EDGEMODEL_DB_PATH
from market_config import WNBA_TEAM_ABBREV
from thresholds import WNBA_SEASON_START, WNBA_EARLY_SEASON_EDGE_MULT

logger = logging.getLogger("jonnyparlay")

_WNBA_GP_CACHE: dict = {}   # per-run cache: (abbrev, iso_date) -> int


def _wnba_early_season_factor(today=None) -> float:
    """Early-season confidence factor for WNBA (Plan 6 §14, 9b).

    Returns the WNBA_EARLY_SEASON_EDGE_MULT factor for the current season day
    (0.80 days 1-14, 0.90 days 15-21, 1.00 after). Consumers divide sigma by
    this factor (wider sigma → win_prob shrinks toward 0.5 → edge, score and
    Kelly size all shrink coherently). Injectable `today` for tests.
    """
    if today is None:
        today = datetime.now(ZoneInfo("America/New_York")).date()
    season_day = (today - WNBA_SEASON_START).days + 1
    for day_cap, factor in WNBA_EARLY_SEASON_EDGE_MULT:
        if 0 < season_day <= day_cap:
            return factor
    return 1.00


def _wnba_team_games_played(team_name: str, today=None):
    """Count a WNBA team's current-season games before today (Plan 6 §14, 9c).

    Reads wnba_player_game_stats from the EdgeModel DB (read-only). Returns
    None when the count is unavailable (unknown team name, DB missing, no rows
    for the season yet) — callers fall back to the day-based opening gate.
    Cached per (team, date) for the run.
    """
    if today is None:
        today = datetime.now(ZoneInfo("America/New_York")).date()
    abbrev = WNBA_TEAM_ABBREV.get((team_name or "").strip().lower())
    if not abbrev:
        return None
    key = (abbrev, today.isoformat())
    if key in _WNBA_GP_CACHE:
        return _WNBA_GP_CACHE[key]
    abbrevs = ("PHO", "PHX") if abbrev == "PHX" else (abbrev, abbrev)
    try:
        import sqlite3
        con = sqlite3.connect(f"file:{Path(EDGEMODEL_DB_PATH).as_posix()}?mode=ro", uri=True)
        try:
            row = con.execute(
                """
                SELECT COUNT(DISTINCT CASE WHEN team_abbrev IN (?, ?) THEN game_id END),
                       COUNT(*)
                FROM wnba_player_game_stats
                WHERE season = ? AND game_date < ?
                """,
                (abbrevs[0], abbrevs[1], today.year, today.isoformat()),
            ).fetchone()
        finally:
            con.close()
        count, season_rows = (int(row[0] or 0), int(row[1] or 0)) if row else (0, 0)
    except Exception as e:
        logger.warning("WNBA games-played lookup failed for %s: %s — falling back to day gate", team_name, e)
        return None
    if season_rows == 0:
        # No rows for the season at all — the fetcher hasn't run yet. Treat as
        # unavailable (day-gate fallback governs) rather than "0 games played",
        # which would block every team all season.
        return None
    _WNBA_GP_CACHE[key] = count   # count==0 with season rows present = real late opener
    return count
