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

import json

from paths import DATA_DIR, PROJECT_ROOT
from projections_db import DB_PATH, seed_scheduled_games
from nba_projector import run_projections, CURRENT_SEASON
from csv_writer import write_nba_csv, fetch_nba_implied_totals, make_team_total_key, _odds_api_get
from injury_parser import get_injury_context
from name_utils import fold_name

log = logging.getLogger("generate_projections")

# ---------------------------------------------------------------------------
# T5: Vegas team-total constraint
# ---------------------------------------------------------------------------
_CONSTRAINT_SCALE_KEYS = [
    "proj_pts",  "proj_pts_p25",  "proj_pts_p75",
    "proj_reb",  "proj_reb_p25",  "proj_reb_p75",
    "proj_ast",  "proj_ast_p25",  "proj_ast_p75",
    "proj_fg3m", "proj_fg3m_p25", "proj_fg3m_p75",
    "proj_blk", "proj_stl", "proj_tov",
    "proj_min", "dk_std",
]
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
            log.warning("_fetch_spreads: unmatched team name(s) '%s'/'%s' — spread skipped, team totals will use equal split", home_name, away_name)
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


_INACTIVES_OVERRIDE_PATH = DATA_DIR / "inactives_override.json"


def _load_inactives_override(game_date: str, db_path: str = DB_PATH) -> dict:
    """Load data/inactives_override.json and return {player_id: status_code} for game_date.

    Override file format:
        { "2026-05-04": { "Dillon Brooks": "O", "Kevin Durant": "Q" } }

    Player names are matched via fold_name() against the players table.
    Override takes precedence over the injury PDF parser output.
    """
    if not _INACTIVES_OVERRIDE_PATH.exists():
        return {}
    try:
        overrides = json.loads(_INACTIVES_OVERRIDE_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        log.warning("Failed to load inactives_override.json: %s", exc)
        return {}

    day_overrides = overrides.get(game_date, {})
    if not day_overrides:
        return {}

    import sqlite3
    try:
        con = sqlite3.connect(str(db_path))
        con.row_factory = sqlite3.Row
        rows = con.execute("SELECT player_id, name_key FROM players").fetchall()
        con.close()
    except Exception as exc:
        log.warning("_load_inactives_override: DB error — %s", exc)
        return {}

    nk_map = {r["name_key"]: r["player_id"] for r in rows}
    result = {}
    for name, status in day_overrides.items():
        pid = nk_map.get(fold_name(name))
        if pid:
            result[pid] = status.upper()
            log.info("Manual inactive override: %s → %s (player_id=%s)", name, status.upper(), pid)
        else:
            log.warning("Manual inactive override: player '%s' not found in DB", name)
    return result


def run(
    game_date: str,
    season: str = CURRENT_SEASON,
    out_path: Path | None = None,
    persist: bool = True,
    no_constraint: bool = False,
    db_path: str = DB_PATH,
    late_run: bool = False,
) -> Path | None:  # M4: can return None when no projections are generated
    """Run the full projection pipeline and return the path to the output CSV.

    This is the public API for callers that import this module.

    late_run=True (--late-run flag): skips pace/Odds API re-calls and only
    re-fetches injuries + regenerates projections.  Use for a T-90 min second
    pass to catch late scratches without spending the full Odds API quota again.
    """
    log.info("=== generate_projections: %s%s ===", game_date,
             " [LATE RUN]" if late_run else "")

    # 0. Seed today's scheduled games from ScoreboardV2 so the projector can
    #    run before games tip off (games table is normally populated only from
    #    completed PlayerGameLogs, which don't exist until after tip-off).
    if not late_run:
        log.info("Seeding scheduled games from NBA API...")
        n_seeded = seed_scheduled_games(game_date, season=season, db_path=db_path)
        log.info("  seeded %d game(s) for %s", n_seeded, game_date)
    else:
        log.info("Late run: skipping game seed (already seeded this morning)")

    # 1. Implied totals + team totals (Odds API)
    if not late_run:
        log.info("Fetching implied totals...")
        implied_totals, team_totals = fetch_nba_implied_totals(game_date, db_path)
        log.info("  totals: %d games, team_totals: %d entries", len(implied_totals), len(team_totals))
    else:
        # Late run: re-use implied totals from DB / last write via csv_writer cache.
        # The Odds API window is still open but we don't want to spend the quota;
        # totals rarely change in the final 90 min before tip-off.
        log.info("Late run: re-using cached implied totals from csv_writer (no Odds API call)")
        implied_totals, team_totals = fetch_nba_implied_totals(game_date, db_path)
        log.info("  totals: %d games, team_totals: %d entries (cached)", len(implied_totals), len(team_totals))

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
    injury_statuses, injury_minutes_overrides, injury_minutes_redistrib_bumps = \
        get_injury_context(game_date, season, db_path)
    log.info("  injuries: %d statuses, %d minute overrides, %d redistribution bumps",
             len(injury_statuses), len(injury_minutes_overrides),
             len(injury_minutes_redistrib_bumps))

    if len(injury_statuses) == 0:
        log.warning(
            "⚠  0 injury statuses returned — nbainjuries PDF may be unavailable or empty. "
            "All players will be projected as active. Check manually for key DNPs."
        )

    # Apply manual inactive override (data/inactives_override.json) — takes precedence.
    _manual = _load_inactives_override(game_date, db_path)
    if _manual:
        injury_statuses.update(_manual)
        log.info("  applied %d manual override(s) from inactives_override.json", len(_manual))

    # 4. Run projections
    log.info("Running projections...")
    projections = run_projections(
        game_date=game_date,
        season=season,
        implied_totals=implied_totals,
        spreads=spreads,
        injury_statuses=injury_statuses,
        injury_minutes_overrides=injury_minutes_overrides,
        injury_minutes_redistrib_bumps=injury_minutes_redistrib_bumps,
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

    # 5. Write CSV
    log.info("Writing SaberSim-schema CSV...")
    csv_path = write_nba_csv(
        projections=projections,
        game_date=game_date,
        implied_totals=implied_totals,
        team_totals=team_totals,
        injury_statuses=injury_statuses,
        out_path=out_path,
        db_path=db_path,
    )
    log.info("CSV written: %s", csv_path)
    return csv_path


def main() -> None:
    # H18: use Eastern time so default date is correct for late-night runs
    try:
        from zoneinfo import ZoneInfo as _ZI
        import datetime as _dt
        _today = str(_dt.datetime.now(_ZI("America/New_York")).date())
    except Exception:
        _today = str(__import__("datetime").date.today())
    parser = argparse.ArgumentParser(description="Generate custom NBA projections CSV")
    parser.add_argument("--date",          default=_today,
                        help="Game date YYYY-MM-DD (default: today in ET)")
    parser.add_argument("--season",        default=CURRENT_SEASON,
                        help="NBA season string (default: 2025-26)")
    parser.add_argument("--out",           default=None,
                        help="Override CSV output path")
    parser.add_argument("--run-picks",     action="store_true",
                        help="Invoke run_picks.py with the output CSV after generation")
    parser.add_argument("--shadow",        action="store_true",
                        help="Like --run-picks but logs to data/pick_log_custom.csv and suppresses "
                             "all Discord posts. Use alongside a live SaberSim run for parallel CLV "
                             "validation. --run-picks is ignored when this flag is set.")  # L4
    parser.add_argument("--research",      action="store_true",
                        help="Like --shadow but logs ALL qualified picks (not just top-5) for faster "
                             "CLV accumulation. Implies --shadow. Use when you need ~100 observations "
                             "quickly; has no effect on live Discord runs.")
    parser.add_argument("--dry-run",       action="store_true",
                        help="Generate CSV but do not invoke run_picks.py")
    parser.add_argument("--no-persist",    action="store_true",
                        help="Do not write projections to SQLite DB")
    parser.add_argument("--no-constraint", action="store_true",
                        help="Skip Vegas team-total constraint scaling (T5)")
    parser.add_argument("--late-run",      action="store_true",
                        help="T-90 min second pass: re-fetch injuries and regenerate projections "
                             "without re-calling pace/Odds API (uses cached CSV). Catches late "
                             "scratches that weren't on the morning report. Outputs to the same "
                             "CSV path as the morning run so run_picks.py always reads fresh data. "
                             "Combine with --run-picks or --shadow to auto-post updated picks. "
                             "(RB8 HIGH priority)")
    parser.add_argument("--verbose",       action="store_true")
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    out_path = Path(args.out) if args.out else None
    # Late run skips DB persist by default (morning run already wrote projections).
    _persist = False if args.late_run else not args.no_persist
    csv_path = run(
        game_date=args.date,
        season=args.season,
        out_path=out_path,
        persist=_persist,
        no_constraint=args.no_constraint,
        late_run=args.late_run,
    )

    if csv_path is None:
        log.error("Generation failed -- no CSV produced")
        sys.exit(1)

    print(f"\nCustom projection CSV: {csv_path}")

    # --research implies --shadow
    if args.research:
        args.shadow = True

    if args.shadow and args.run_picks:
        # H10: --run-picks is silently overridden by shadow mode; warn so the user knows
        log.warning("Both --shadow and --run-picks specified; --run-picks is ignored "
                    "(shadow mode always invokes run_picks.py with --no-discord)")

    invoke = args.run_picks or args.shadow
    if invoke and not args.dry_run:
        run_picks_script = PROJECT_ROOT / "run_picks.py"
        if not run_picks_script.exists():
            run_picks_script = _HERE / "run_picks.py"
        cmd = [sys.executable, str(run_picks_script), str(csv_path)]
        env = dict(os.environ)
        if args.shadow:
            custom_log = DATA_DIR / "pick_log_custom.csv"
            env["JONNYPARLAY_PICK_LOG"] = str(custom_log)
            cmd.append("--no-discord")
            log.info("Shadow mode: logging to %s, Discord suppressed", custom_log)
        if args.research:
            # Log ALL qualified picks for faster CLV accumulation (~25-50/day vs 8-13).
            cmd.append("--no-cap")
            log.info("Research mode: --no-cap active, logging all qualified picks")
        log.info("Invoking run_picks.py: %s", " ".join(cmd))
        result = subprocess.run(cmd, cwd=str(PROJECT_ROOT), env=env)
        sys.exit(result.returncode)


if __name__ == "__main__":
    main()
