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
from projections_db import DB_PATH
from nba_projector import run_projections, CURRENT_SEASON
from csv_writer import write_nba_csv, fetch_nba_implied_totals
from injury_parser import get_injury_context

log = logging.getLogger("generate_projections")
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
        import requests, os
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
        resp = requests.get(url, params={
            "apiKey": ODDS_API_KEY,
            "regions": "us",
            "markets": "spreads",
            "oddsFormat": "american",
            "dateFormat": "iso",
        }, timeout=10)
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


def run(
    game_date: str,
    season: str = CURRENT_SEASON,
    out_path: Path | None = None,
    persist: bool = True,
    db_path: str = DB_PATH,
) -> Path:
    """Run the full projection pipeline and return the path to the output CSV.

    This is the public API for callers that import this module.
    """
    log.info("=== generate_projections: %s ===", game_date)

    # 1. Implied totals + team totals (Odds API)
    log.info("Fetching implied totals...")
    implied_totals, team_totals = fetch_nba_implied_totals(game_date, db_path)
    log.info("  totals: %d games, team_totals: %d entries", len(implied_totals), len(team_totals))

    # 2. Spreads (Odds API)
    log.info("Fetching spreads...")
    spreads = _fetch_spreads(game_date, db_path)

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
    parser = argparse.ArgumentParser(description="Generate custom NBA projections CSV")
    parser.add_argument("--date",       default=str(datetime.date.today()),
                        help="Game date YYYY-MM-DD (default: today)")
    parser.add_argument("--season",     default=CURRENT_SEASON,
                        help="NBA season string (default: 2025-26)")
    parser.add_argument("--out",        default=None,
                        help="Override CSV output path")
    parser.add_argument("--run-picks",  action="store_true",
                        help="Invoke run_picks.py with the output CSV after generation")
    parser.add_argument("--shadow",     action="store_true",
                        help="Like --run-picks but logs to pick_log_custom.csv, no Discord posts")
    parser.add_argument("--dry-run",    action="store_true",
                        help="Generate CSV but do not invoke run_picks.py")
    parser.add_argument("--no-persist", action="store_true",
                        help="Do not write projections to SQLite DB")
    parser.add_argument("--verbose",    action="store_true")
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    out_path = Path(args.out) if args.out else None
    csv_path = run(
        game_date=args.date,
        season=args.season,
        out_path=out_path,
        persist=not args.no_persist,
    )

    if csv_path is None:
        log.error("Generation failed -- no CSV produced")
        sys.exit(1)

    print(f"\nCustom projection CSV: {csv_path}")

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
        log.info("Invoking run_picks.py: %s", " ".join(cmd))
        result = subprocess.run(cmd, cwd=str(PROJECT_ROOT), env=env)
        sys.exit(result.returncode)


if __name__ == "__main__":
    main()
