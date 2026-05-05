"""generate_projections.py -- Daily custom projection runner.

Orchestrates the full pipeline:
  1. Fetch implied totals + spreads from The Odds API
  2. Fetch injury statuses + minutes overrides from injury_parser
  3. Run nba_projector.run_projections()
  4. Write SaberSim-schema CSV via csv_writer.write_nba_csv()
  5. Optionally invoke run_picks.py with the custom CSV (--run-picks flag)

Usage:
    python engine/generate_projections.py [options]

Options:
    --date YYYY-MM-DD   Game date (default: today)
    --season STR        NBA season string (default: 2025-26)
    --out PATH          Override CSV output path
    --run-picks         Pass the output CSV to run_picks.py after generation
    --shadow            Like --run-picks but logs to pick_log_custom.csv and
                        skips all Discord posts. Use for parallel validation
                        alongside live SaberSim picks.
    --dry-run           Generate CSV but do not invoke run_picks.py
    --no-persist        Do not persist projections to SQLite DB
    --verbose           Extra logging

The generated CSV lands in data/projections/DATE_nba_custom.csv by default.
It is schema-compatible with SaberSim -- parse_csv() in run_picks.py reads it
without modification.

Shadow mode (--shadow):
    Runs run_picks.py with JONNYPARLAY_PICK_LOG=data/pick_log_custom.csv and
    --no-discord. Picks are logged to the custom log only -- the live
    pick_log.csv and Discord are untouched. Use clv_report.py --custom to
    compare CLV between custom and SaberSim picks.
"""
from __future__ import annotations

import argparse
import datetime
import logging
import os
import subprocess
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from paths import DATA_DIR, PROJECT_ROOT
from projections_db import DB_PATH, seed_scheduled_games
from nba_projector import run_projections, CURRENT_SEASON
from csv_writer import write_nba_csv, fetch_nba_implied_totals, make_team_total_key, _odds_api_get
from injury_parser import get_injury_context

log = logging.getLogger("generate_projections")

# ---------------------------------------------------------------------------
# T5: Vegas team-total constraint
# ---------------------------------------------------------------------------
_CONSTRAINT_SCALE_KEYS = ["proj_pts", "proj_reb", "proj_ast", "proj_fg3m",
                           "proj_blk", "proj_stl", "proj_tov"]
_CONSTRAINT_MIN = 0.80
_CONSTRAINT_MAX = 1.20


def constrain_team_totals(
    projections: list,
    team_totals: dict,   # {"{game_id}:{team_id}" -> vegas_team_total}
) -> list:
    """Scale each team's player projections so proj_pts sum ≈ Vegas team total.

    Algorithm:
      1. Group projections by (game_id, team_id).
      2. Sum proj_pts for non-cold_start players only (denominator).
         cold_start players have uncertain roles — include their pts in the sum
         but skip them as anchor-free outliers if total denominator is 0.
      3. scale = vegas_total / sum_proj_pts, clipped to [0.80, 1.20].
      4. Warn if the raw scale was outside [0.80, 1.20] (projection may be stale).
      5. Apply scale to all _CONSTRAINT_SCALE_KEYS for every player on that team.

    T5 (Research Brief 6, 2026-05-02).
    """
    from collections import defaultdict as _dd

    if not team_totals:
        return projections

    # Group by (game_id, team_id)
    by_team: dict = _dd(list)
    for p in projections:
        key = make_team_total_key(p.get('game_id'), p.get('team_id'))  # H17
        by_team[key].append(p)

    for key, tprojs in by_team.items():
        if key not in team_totals:
            continue
        vegas_total = team_totals[key]
        if not vegas_total or vegas_total <= 0:
            continue

        # Denominator: sum proj_pts for all players (cold_start included —
        # they are already calibrated from career priors)
        denom = sum(p.get("proj_pts", 0.0) or 0.0 for p in tprojs)
        if denom <= 0:
            log.warning("constrain_team_totals: zero proj_pts sum for key=%s — skipping", key)
            continue

        raw_scale = vegas_total / denom
        clipped = max(_CONSTRAINT_MIN, min(_CONSTRAINT_MAX, raw_scale))

        if raw_scale < _CONSTRAINT_MIN or raw_scale > _CONSTRAINT_MAX:
            team_id = tprojs[0].get("team_id", "?") if tprojs else "?"
            log.warning(
                "constrain_team_totals: raw scale %.4f clipped to %.4f "
                "(team=%s, vegas=%.1f, proj_sum=%.1f) — projection may need recalibration",
                raw_scale, clipped, team_id, vegas_total, denom
            )

        if abs(clipped - 1.0) < 1e-4:
            continue  # No meaningful adjustment

        for p in tprojs:
            for k in _CONSTRAINT_SCALE_KEYS:
                if k in p and p[k] is not None:
                    p[k] = round(p[k] * clipped, 2)
        log.debug("constrain_team_totals: key=%s  vegas=%.1f  proj=%.1f  scale=%.4f  n=%d",
                  key, vegas_total, denom, clipped, len(tprojs))

    return projections
if not log.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def _fetch_spreads(game_date: str, db_path: str = DB_PATH) -> dict:
    """Fetch spread (home team perspective) for each game from The Odds API.

    Returns {game_id: spread} where spread < 0 means home team favoured.
    Falls back to {} on any error so the pipeline still runs.
    """
    try:
        import os
    except ImportError:
        return {}

    try:
        from secrets_config import ODDS_API_KEY
    except Exception:
        ODDS_API_KEY = os.environ.get("ODDS_API_KEY", "")
    if not ODDS_API_KEY:
        log.warning("_fetch_spreads: no ODDS_API_KEY -- skipping")
        return {}

    try:
        import sqlite3
        con = sqlite3.connect(db_path)
        con.row_factory = sqlite3.Row
        games = con.execute(
            "SELECT game_id, home_team_id, away_team_id FROM games WHERE game_date=?",
            (game_date,),
        ).fetchall()
        teams = {r["team_id"]: r["name"]
                 for r in con.execute("SELECT team_id, name FROM teams").fetchall()}
        con.close()
    except Exception as exc:
        log.warning("_fetch_spreads: DB error -- %s", exc)
        return {}

    if not games:
        return {}

    # Build (home_tid, away_tid) -> game_id index
    matchup_to_gid = {(int(g["home_team_id"]), int(g["away_team_id"])): str(g["game_id"])
                      for g in games}
    # Reverse-index: team_name -> team_id
    name_to_tid = {v: k for k, v in teams.items()}

    try:
        url = "https://api.the-odds-api.com/v4/sports/basketball_nba/odds/"
        resp = _odds_api_get(url, params={
            "apiKey": ODDS_API_KEY,
            "regions": "us",
            "markets": "spreads",
            "oddsFormat": "american",
            "dateFormat": "iso",
        })
        if resp.status_code != 200:
            log.warning("_fetch_spreads: API %s", resp.status_code)
            return {}
        data = resp.json()
    except Exception as exc:
        log.warning("_fetch_spreads: request error -- %s", exc)
        return {}

    spreads: dict = {}
    for game in data:
        home_name = game.get("home_team", "")
        away_name = game.get("away_team", "")
        home_tid = name_to_tid.get(home_name)
        away_tid = name_to_tid.get(away_name)
        if not home_tid or not away_tid:
            continue
        gid = matchup_to_gid.get((int(home_tid), int(away_tid)))
        if not gid:
            continue
        for bm in game.get("bookmakers", []):
            for market in bm.get("markets", []):
                if market.get("key") != "spreads":
                    continue
                for outcome in market.get("outcomes", []):
                    if outcome.get("name") == home_name:
                        try:
                            spreads[gid] = float(outcome["point"])
                        except (KeyError, ValueError):
                            pass
                break
            if gid in spreads:
                break

    log.info("_fetch_spreads: got %d/%d games", len(spreads), len(games))
    return spreads


def _derive_team_totals(
    implied_totals: dict,
    spreads: dict,
    game_date: str,
    db_path: str = DB_PATH,
) -> dict:
    """Derive team totals from game total ± spread/2 when Odds API team_totals absent.

    Math (spread is home-team perspective; spread < 0 = home favoured):
        home_total = (game_total - spread) / 2
        away_total = (game_total + spread) / 2

    Falls back to game_total / 2 per team when no spread is available.
    Returns {"{game_id}:{team_id}": team_total} — same key format as
    fetch_nba_implied_totals() so constrain_team_totals() consumes it unchanged.
    """
    if not implied_totals:
        return {}

    try:
        import sqlite3
        con = sqlite3.connect(db_path)
        con.row_factory = sqlite3.Row
        rows = con.execute(
            "SELECT game_id, home_team_id, away_team_id FROM games WHERE game_date = ?",
            (game_date,),
        ).fetchall()
        con.close()
    except Exception as exc:
        log.warning("_derive_team_totals: DB error — %s", exc)
        return {}

    derived: dict = {}
    for row in rows:
        gid      = str(row["game_id"])
        home_tid = int(row["home_team_id"])
        away_tid = int(row["away_team_id"])

        game_total = implied_totals.get(gid)
        if not game_total or game_total <= 0:
            continue

        spread = spreads.get(gid)  # home spread; None if unavailable
        if spread is None:
            home_total = round(game_total / 2.0, 1)
            away_total = round(game_total / 2.0, 1)
        else:
            home_total = round((game_total - spread) / 2.0, 1)
            away_total = round((game_total + spread) / 2.0, 1)

        derived[make_team_total_key(gid, home_tid)] = home_total
        derived[make_team_total_key(gid, away_tid)] = away_total
        log.debug(
            "_derive_team_totals: game=%s total=%.1f spread=%s → home=%.1f away=%.1f",
            gid, game_total, spread, home_total, away_total,
        )

    log.info("_derive_team_totals: derived %d team totals from %d game totals",
             len(derived), len(implied_totals))
    return derived


def run(
    game_date: str,
    season: str = CURRENT_SEASON,
    out_path: Path | None = None,
    persist: bool = True,
    no_constraint: bool = False,
    db_path: str = DB_PATH,
) -> Path | None:  # M4: can return None when no projections are generated
    """Run the full projection pipeline and return the path to the output CSV.

    This is the public API for callers that import this module.
    """
    log.info("=== generate_projections: %s ===", game_date)

    # 0. Seed today's scheduled games from ScoreboardV2 so the projector can
    #    run before games tip off (games table is normally populated only from
    #    completed PlayerGameLogs, which don't exist until after tip-off).
    log.info("Seeding scheduled games from NBA API...")
    n_seeded = seed_scheduled_games(game_date, season=season, db_path=db_path)
    log.info("  seeded %d game(s) for %s", n_seeded, game_date)

    # 1. Implied totals + team totals (Odds API)
    log.info("Fetching implied totals...")
    implied_totals, team_totals = fetch_nba_implied_totals(game_date, db_path)
    log.info("  totals: %d games, team_totals: %d entries", len(implied_totals), len(team_totals))

    # Warn for any scheduled game missing an implied total (pace constraint won't apply)
    try:
        import sqlite3 as _sqlite3
        _con = _sqlite3.connect(db_path)
        _con.row_factory = _sqlite3.Row
        try:  # H9: close connection in finally so it's released on query error too
            _games = _con.execute(
                "SELECT g.game_id, th.abbreviation AS home_abbr, ta.abbreviation AS away_abbr"
                " FROM games g"
                " JOIN teams th ON th.team_id = g.home_team_id"
                " JOIN teams ta ON ta.team_id = g.away_team_id"
                " WHERE g.game_date = ?", (game_date,)
            ).fetchall()
        finally:
            _con.close()
        for _g in _games:
            if str(_g["game_id"]) not in implied_totals:
                log.warning(
                    "No implied total for %s vs %s (game_id=%s) — pace constraint not applied",
                    _g["home_abbr"], _g["away_abbr"], _g["game_id"],
                )
    except Exception as _e:
        log.debug("Implied total warning check failed: %s", _e)

    # 2. Spreads (Odds API)
    log.info("Fetching spreads...")
    spreads = _fetch_spreads(game_date, db_path)

    # 2b. If Odds API returned 0 explicit team totals, derive from game total ± spread/2.
    #     This ensures constrain_team_totals() always fires — the API rarely returns the
    #     team_totals market during playoffs but always returns game totals + spreads.
    if not team_totals and implied_totals:
        log.info("No explicit team totals from API — deriving from game total ± spread/2")
        team_totals = _derive_team_totals(implied_totals, spreads, game_date, db_path)

    # 3. Injury context
    log.info("Fetching injury context...")
    injury_statuses, injury_minutes_overrides = get_injury_context(game_date, season, db_path)
    log.info("  injuries: %d statuses, %d minute overrides",
             len(injury_statuses), len(injury_minutes_overrides))

    # 4. Run projections
    log.info("Running projections...")
    projections = run_projections(
        game_date=game_date,
        season=season,
        implied_totals=implied_totals,
        spreads=spreads,
        injury_statuses=injury_statuses,
        injury_minutes_overrides=injury_minutes_overrides,
        db_path=db_path,
        persist=persist,
    )
    if not projections:
        log.warning("No projections generated for %s -- no games scheduled?", game_date)
        return None

    log.info("Generated %d player projections", len(projections))

    # T5: Constrain team totals to Vegas lines
    if not no_constraint:
        projections = constrain_team_totals(projections, team_totals)