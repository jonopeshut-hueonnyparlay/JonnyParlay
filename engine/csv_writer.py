"""csv_writer.py -- SaberSim-schema CSV output for run_picks.py.

Converts projection dicts (from nba_projector.run_projections()) into a CSV
that parse_csv() in run_picks.py can consume without modification.

SaberSim NBA column order:
  Name, Pos, Team, Opp, Status, Saber Team, Saber Total,
  PTS, RB, AST, 3PT, dk_std

Status values (matching SaberSim convention):
  "Confirmed" -> starter confirmed
  "O"         -> out (row excluded from CSV)
  "Q"         -> questionable (row included, status="Q")
  ""          -> active rotation / no status data

Output path: data/projections/<YYYY-MM-DD>_nba_custom.csv
  Feed directly to:  python run_picks.py data/projections/YYYY-MM-DD_nba_custom.csv
"""
from __future__ import annotations

import csv
import datetime
import logging
from zoneinfo import ZoneInfo
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

_HERE = Path(__file__).resolve().parent

# H17: canonical key format for team-total lookup shared with generate_projections.py
# Format: "<game_id>:<team_id>" -- both files must use this constant to stay in sync.
TEAM_TOTAL_KEY_SEP = ":"

def make_team_total_key(game_id, team_id) -> str:
    """Build the canonical team-total dict key used by fetch_nba_implied_totals()
    and constrain_team_totals(). H17: single definition, two consumers."""
    return f"{game_id}{TEAM_TOTAL_KEY_SEP}{team_id}"

if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from paths import DATA_DIR, PROJECT_ROOT
from projections_db import DB_PATH, get_conn

log = logging.getLogger("csv_writer")
if not log.handlers:
    logging.basicConfig(level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
CSV_SUBDIR       = DATA_DIR / "projections"
CSV_SUBDIR.mkdir(parents=True, exist_ok=True)

NBA_COLUMNS = [
    "Name", "Pos", "Team", "Opp", "Status",
    "Saber Team", "Saber Total",
    "PTS", "RB", "AST", "3PT", "dk_std",
]

# Status codes -> SaberSim Status column value
_STATUS_TO_CSV = {
    "O":   None,        # excluded
    "Q":   "Q",
    "GTD": "Q",         # treat GTD as Q in output
    "P":   "Confirmed", # probable -> confirmed
    "":    "",          # no data -> blank
}

# ---------------------------------------------------------------------------
# Odds API: implied totals fetch  (Q8.6)
# ---------------------------------------------------------------------------
_ODDS_BASE = "https://api.the-odds-api.com/v4"
_NBA_SPORT = "basketball_nba"

# §8: Odds API retry / 429 handling
_ODDS_RETRY_WAIT_S  = 3    # seconds to wait before retry on timeout/5xx
_ODDS_429_WAIT_S    = 60   # seconds to back off on HTTP 429


def _odds_api_get(url: str, params: dict, timeout: int = 15):
    """Thin wrapper around requests.get with retry and 429 handling.

    Behaviour:
      - On HTTP 429: sleep _ODDS_429_WAIT_S seconds, retry once.
      - On requests.Timeout or HTTP 5xx: sleep _ODDS_RETRY_WAIT_S, retry once.
      - Logs X-Requests-Remaining header on every response so we can monitor
        quota usage without touching the API response body.
      - Returns the Response object (caller checks .status_code / .json()).
      - Re-raises on second consecutive failure so callers get a clean exception.
    """
    import time
    import requests as _req

    def _log_remaining(resp):
        remaining = resp.headers.get("X-Requests-Remaining")
        if remaining is not None:
            log.info("_odds_api_get: X-Requests-Remaining=%s", remaining)

    attempt = 0
    last_exc = None
    while attempt < 2:
        attempt += 1
        try:
            resp = _req.get(url, params=params, timeout=timeout)
            _log_remaining(resp)
            if resp.status_code == 429:
                log.warning(
                    "_odds_api_get: HTTP 429 (attempt %d) -- backing off %ds",
                    attempt, _ODDS_429_WAIT_S,
                )
                if attempt < 2:
                    time.sleep(_ODDS_429_WAIT_S)
                    continue
            elif resp.status_code >= 500 and attempt < 2:
                log.warning(
                    "_odds_api_get: HTTP %s (attempt %d) -- retrying in %ds",
                    resp.status_code, attempt, _ODDS_RETRY_WAIT_S,
                )
                time.sleep(_ODDS_RETRY_WAIT_S)
                continue
            return resp
        except _req.Timeout as exc:
            last_exc = exc
            log.warning(
                "_odds_api_get: Timeout (attempt %d) -- retrying in %ds",
                attempt, _ODDS_RETRY_WAIT_S,
            )
            if attempt < 2:
                time.sleep(_ODDS_RETRY_WAIT_S)
        except Exception:
            raise  # unexpected -- let caller handle

    # Exhausted retries
    if last_exc is not None:
        raise last_exc
    raise RuntimeError("_odds_api_get: exhausted retries with no exception captured")


def fetch_nba_implied_totals(
    game_date: str,
    db_path: str = DB_PATH,
) -> Tuple[Dict[str, float], Dict[str, float]]:
    """Fetch NBA over/under totals from The Odds API and join to our game_ids.

    Returns:
        implied_totals  -- {game_id: over_under_line}
        team_totals     -- {"game_id:team_id": team_total_line}

    Falls back to ({}, {}) gracefully on any error (no key, network down, etc.)
    so the projection pipeline still runs -- it just uses pace-only defaults.
    """
    try:
        import requests as _requests_check  # noqa: F401 -- verify requests is available
    except ImportError:
        log.warning("fetch_nba_implied_totals: requests not installed -- skipping")
        return {}, {}

    # Load API key from secrets_config (same as run_picks.py)
    try:
        from secrets_config import ODDS_API_KEY
    except Exception:
        try:
            import os
            ODDS_API_KEY = os.environ.get("ODDS_API_KEY", "")
        except Exception:
            ODDS_API_KEY = ""
    if not ODDS_API_KEY:
        log.warning("fetch_nba_implied_totals: no ODDS_API_KEY -- skipping")
        return {}, {}

    conn = get_conn(db_path)

    # Build name -> team_id map from DB (Odds API uses full team names)
    name_to_tid: Dict[str, int] = {
        r["name"]: r["team_id"]
        for r in conn.execute("SELECT team_id, name FROM teams").fetchall()
    }

    # Load today's games (game_id, home_team_id, away_team_id)
    games_rows = conn.execute(
        "SELECT game_id, home_team_id, away_team_id FROM games WHERE game_date=?",
        (game_date,)
    ).fetchall()
    conn.close()

    if not games_rows:
        log.info("fetch_nba_implied_totals: no games in DB for %s -- skipping", game_date)
        return {}, {}

    # Index: (home_team_id, away_team_id) -> game_id
    matchup_to_gid: Dict[tuple, str] = {
        (int(r["home_team_id"]), int(r["away_team_id"])): str(r["game_id"])
        for r in games_rows
    }

    implied_totals: Dict[str, float] = {}
    team_totals:    Dict[str, float] = {}

    # -- Fetch game totals --------------------------------------------------
    params = {
        "apiKey":     ODDS_API_KEY,
        "regions":    "us",
        "markets":    "totals",
        "oddsFormat": "american",
    }
    try:
        resp = _odds_api_get(
            f"{_ODDS_BASE}/sports/{_NBA_SPORT}/odds",
            params=params,
        )
        if resp.status_code != 200:
            log.warning("fetch_nba_implied_totals: totals API returned %s", resp.status_code)
            return {}, {}
        events = resp.json()
        if not isinstance(events, list):
            log.warning("fetch_nba_implied_totals: unexpected API response shape: %s", type(events).__name__)
            return {}, {}
    except Exception as exc:
        log.warning("fetch_nba_implied_totals: totals fetch failed: %s", exc)
        return {}, {}

    for ev in events:
        home_name = ev.get("home_team", "")
        away_name = ev.get("away_team", "")
        home_tid  = name_to_tid.get(home_name)
        away_tid  = name_to_tid.get(away_name)
        if home_tid is None or away_tid is None:
            log.debug("fetch_nba_implied_totals: unmatched teams '%s' / '%s'",
                      home_name, away_name)
            continue

        game_id = matchup_to_gid.get((home_tid, away_tid))
        if game_id is None:
            continue   # game not in today's schedule

        # Best Over line across bookmakers (first hit wins -- lines nearly identical)
        best_total: Optional[float] = None
        for bm in ev.get("bookmakers", []):
            for mkt in bm.get("markets", []):
                if mkt.get("key") != "totals":
                    continue
                for outcome in mkt.get("outcomes", []):
                    if outcome.get("name") == "Over":
                        pt = outcome.get("point")
                        if pt is not None and best_total is None:
                            best_total = float(pt)
        if best_total is not None:
            implied_totals[game_id] = best_total
            log.debug("  %s @ %s -> total %.1f (game_id %s)",
                      away_name, home_name, best_total, game_id)

    # -- Fetch team totals (optional) --------------------------------------
    params_tt = {
        "apiKey":     ODDS_API_KEY,
        "regions":    "us",
        "markets":    "team_totals",
        "oddsFormat": "american",
    }
    try:
        resp_tt = _odds_api_get(
            f"{_ODDS_BASE}/sports/{_NBA_SPORT}/odds",
            params=params_tt,
        )
        if resp_tt.status_code == 200:
            tt_events = resp_tt.json()
            if not isinstance(tt_events, list):  # H20: validate shape before iterating
                log.warning("fetch_nba_implied_totals: team_totals unexpected shape: %s", type(tt_events).__name__)
                tt_events = []
            for ev in tt_events:
                home_name = ev.get("home_team", "")
                away_name = ev.get("away_team", "")
                home_tid  = name_to_tid.get(home_name)
                away_tid  = name_to_tid.get(away_name)
                if home_tid is None or away_tid is None:
                    continue
                game_id = matchup_to_gid.get((home_tid, away_tid))
                if game_id is None:
                    continue
                for bm in ev.get("bookmakers", []):
                    for mkt in bm.get("markets", []):
                        if mkt.get("key") != "team_totals":
                            continue
                        for outcome in mkt.get("outcomes", []):
                            if outcome.get("name") == "Over":
                                desc = outcome.get("description", "")
                                pt   = outcome.get("point")
                                if pt is None:
                                    continue
                                # description = team name for team_totals market
                                tid = name_to_tid.get(desc)
                                if tid is not None:
                                    key = make_team_total_key(game_id, tid)
                                    if key not in team_totals:
                                        team_totals[key] = float(pt)
    except Exception as exc:
        log.debug("fetch_nba_implied_totals: team_totals fetch failed: %s", exc)
        # team_totals is optional -- don't abort

    log.info("fetch_nba_implied_totals: %d game totals, %d team totals for %s",
             len(implied_totals), len(team_totals), game_date)
    return implied_totals, team_totals


# ---------------------------------------------------------------------------
# Team abbreviation lookup
# ---------------------------------------------------------------------------

def _build_team_abbrev_map(db_path: str = DB_PATH) -> Dict[int, str]:
    """Return {team_id: abbreviation} from teams table."""
    conn = get_conn(db_path)
    rows = conn.execute("SELECT team_id, abbreviation FROM teams").fetchall()
    conn.close()
    return {r["team_id"]: r["abbreviation"] for r in rows}


# ---------------------------------------------------------------------------
# Projection dict -> CSV row
# ---------------------------------------------------------------------------

def _proj_to_row(
    proj: dict,
    team_abbrev_map: Dict[int, str],
    implied_totals: Dict[str, float],   # game_id -> game total
    team_totals: Dict[str, float],      # game_id:team_id -> team total
    injury_statuses: Dict[int, str],
) -> Optional[dict]:
    """Convert one projection dict to a CSV row dict. Returns None to skip."""
    pid      = proj["player_id"]
    status_code = injury_statuses.get(pid, "")
    csv_status  = _STATUS_TO_CSV.get(status_code, "")

    if csv_status is None:
        return None   # OUT -- exclude from CSV

    team_id    = proj.get("team_id")
    opp_id     = proj.get("opp_team_id")
    game_id    = str(proj.get("game_id", ""))
    team_abbr  = team_abbrev_map.get(team_id, "")
    opp_abbr   = team_abbrev_map.get(opp_id, "")

    saber_total = implied_totals.get(game_id, 0.0)
    team_key    = make_team_total_key(game_id, team_id)  # H17
    saber_team  = team_totals.get(team_key, round(saber_total / 2.0, 1))

    # Status: if no injury flag but starter -> "Confirmed"
    if not csv_status and proj.get("role_tier") == "starter":
        csv_status = "Confirmed"

    # Map position to SaberSim-style (G/F/C)
    pos = proj.get("position") or ""
    if not pos:
        # M2: map sixth_man explicitly to "F" -- role_tier[:1] would produce "S"
        # which injury_parser._normalise_position() doesn't recognise, silently
        # excluding sixth-men from minutes redistribution when a starter is OUT.
        role = proj.get("role_tier", "")
        _ROLE_POS = {"starter": "F", "sixth_man": "F", "rotation": "F", "bench": "F"}
        pos = _ROLE_POS.get(role, role[:1].upper() if role else "") or "F"

    return {
        "Name":        proj["player_name"],
        "Pos":         pos,
        "Team":        team_abbr,
        "Opp":         opp_abbr,
        "Status":      csv_status,
        "Saber Team":  round(saber_team, 2),
        "Saber Total": round(saber_total, 2),
        "PTS":         proj.get("proj_pts", 0.0),
        "RB":          proj.get("proj_reb", 0.0),
        "AST":         proj.get("proj_ast", 0.0),
        "3PT":         proj.get("proj_fg3m", 0.0),
        "dk_std":      proj.get("dk_std", 0.0),
    }


# ---------------------------------------------------------------------------
# Public write API
# ---------------------------------------------------------------------------

def write_nba_csv(
    projections: List[dict],
    game_date: Optional[str] = None,
    implied_totals: Optional[Dict[str, float]] = None,
    team_totals: Optional[Dict[str, float]] = None,
    injury_statuses: Optional[Dict[int, str]] = None,
    out_path: Optional[Path] = None,
    db_path: str = DB_PATH,
) -> Path:
    """Write SaberSim-schema NBA CSV from projection dicts.

    Args:
        projections:    List of dicts from run_projections()
        game_date:      "YYYY-MM-DD" (default: today in ET)
        implied_totals: {game_id: over_under_total} from Odds API
        team_totals:    {"game_id:team_id": team_total} from Odds API
        injury_statuses:{player_id: status_code} from injury_parser
        out_path:       Override output path (default: data/projections/DATE_nba_custom.csv)
        db_path:        SQLite DB path

    Returns:
        Path to written CSV.
    """
    if game_date is None:
        game_date = datetime.datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")  # H18: use ET date
    if implied_totals is None:
        implied_totals = {}
    if team_totals is None:
        team_totals = {}
    if injury_statuses is None:
        injury_statuses = {}

    if out_path is None:
        out_path = CSV_SUBDIR / f"{game_date}_nba_custom.csv"

    team_abbrev_map = _build_team_abbrev_map(db_path)

    rows = []
    skipped_out = 0
    for proj in projections:
        row = _proj_to_row(proj, team_abbrev_map, implied_totals,
                           team_totals, injury_statuses)
        if row is None:
            skipped_out += 1
            continue
        rows.append(row)

    # Sort by PTS descending for readability
    rows.sort(key=lambda r: float(r["PTS"]), reverse=True)

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=NBA_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    log.info("CSV written: %s (%d players, %d OUT excluded)",
             out_path.name, len(rows), skipped_out)
    return out_path


# ---------------------------------------------------------------------------
# Validation: feed output through parse_csv() to confirm compatibility
# ---------------------------------------------------------------------------

def validate_csv(csv_path: Path) -> bool:
    """Run the CSV through run_picks.parse_csv() and verify it parses cleanly.

    Returns True if parse succeeds with > 0 players.
    """
    try:
        sys.path.insert(0, str(PROJECT_ROOT / "engine"))
        import csv as _csv
        with open(csv_path, "r", encoding="utf-8-sig") as f:
            reader = _csv.DictReader(f)
            rows = list(reader)
        if not rows:
            log.error("validate_csv: empty CSV at %s", csv_path)
            return False
        headers = {h.strip().lower() for h in rows[0].keys()}
        required_nba = {"name", "pts", "rb", "ast", "3pt"}
        missing = required_nba - headers
        if missing:
            log.error("validate_csv: missing columns %s", missing)
            return False
        log.info("validate_csv: OK -- %d rows, headers=%s", len(rows),
                 sorted(headers - {"dk_std"}))
        return True
    except Exception as exc:
        log.error("validate_csv error: %s", exc)
        return False


# ---------------------------------------------------------------------------
# Convenience: run full pipeline (projections -> CSV in one call)
# ---------------------------------------------------------------------------

def generate_daily_csv(
    game_date: Optional[str] = None,
    season: str = "2025-26",
    implied_totals: Optional[Dict[str, float]] = None,
    team_totals: Optional[Dict[str, float]] = None,
    db_path: str = DB_PATH,
    validate: bool = True,
    fetch_odds: bool = True,
) -> Optional[Path]:
    """Pull injuries, run projections, write CSV.  One-shot daily workflow.

    Args:
        game_date:      "YYYY-MM-DD" (default: today in ET)
        season:         NBA season
        implied_totals: {game_id: total} from Odds API (optional; auto-fetched
                        when fetch_odds=True and caller omits it)
        team_totals:    {"game_id:team_id": team_total} (optional; same)
        db_path:        SQLite path
        validate:       If True, run validate_csv() before returning
        fetch_odds:     If True (default), auto-fetch implied_totals/team_totals
                        from The Odds API when caller doesn't supply them.

    Returns:
        Path to written CSV, or None on failure.
    """
    if game_date is None:
        game_date = datetime.datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")  # H18: use ET date

    # Q8.6 -- auto-fetch implied totals when not supplied by caller
    if fetch_odds and implied_totals is None:
        fetched_totals, fetched_team_totals = fetch_nba_implied_totals(
            game_date=game_date, db_path=db_path)
        implied_totals = fetched_totals
        if team_totals is None:
            team_totals = fetched_team_totals
    else:
        if implied_totals is None:
            implied_totals = {}
        if team_totals is None:
            team_totals = {}

    from nba_projector import run_projections
    from injury_parser import get_injury_context

    injury_statuses, injury_minutes_overrides = get_injury_context(
        game_date=game_date, season=season, db_path=db_path)

    projections = run_projections(
        game_date=game_date,
        season=season,
        implied_totals=implied_totals,
        injury_statuses=injury_statuses,
        injury_minutes_overrides=injury_minutes_overrides,
        db_path=db_path,
        persist=True,
    )

    if not projections:
        log.warning("No projections generated for %s", game_date)
        return None

    # M5: apply team-total constraint when team_totals available.
    # generate_projections.py also derives team totals from spread when API
    # returns none — that derivation is not replicated here; use
    # generate_projections.py for production runs.
    if team_totals:
        try:
            from generate_projections import constrain_team_totals
            projections = constrain_team_totals(projections, team_totals)
        except ImportError:
            log.warning("generate_daily_csv: constrain_team_totals unavailable — team-total constraint skipped")
    else:
        log.warning("generate_daily_csv: no team_totals — team-total constraint skipped; use generate_projections.py for production")

    csv_path = write_nba_csv(
        projections=projections,
        game_date=game_date,
        implied_totals=implied_totals,
        team_totals=team_totals,
        injury_statuses=injury_statuses,
        db_path=db_path,
    )

    if validate:
        ok = validate_csv(csv_path)
        if not ok:
            log.error("CSV validation failed -- check output")

    return csv_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _main() -> None:
    import argparse
    parser = argparse.ArgumentParser(
        description="Generate SaberSim-schema NBA CSV from custom projections")
    parser.add_argument("--date",       default=datetime.datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d"))
    parser.add_argument("--season",     default="2025-26")
    parser.add_argument("--db",         default=DB_PATH)
    parser.add_argument("--out",        default=None, help="Override output path")
    parser.add_argument("--validate",   action="store_true", default=True)
    parser.add_argument("--no-validate", dest="validate", action="store_false")
    parser.add_argument("--no-odds",    action="store_true",
                        help="Skip Odds API fetch (use pace-only defaults)")
    args = parser.parse_args()

    csv_path = generate_daily_csv(
        game_date=args.date,
        season=args.season,
        db_path=args.db,
        validate=args.validate,
        fetch_odds=not args.no_odds,
    )
    if csv_path:
        print(f"CSV ready: {csv_path}")
    else:
        print("Failed to generate CSV.")
        sys.exit(1)


if __name__ == "__main__":
    _main()
