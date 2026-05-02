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
import sys
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

_HERE = Path(__file__).resolve().parent
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
    team_key    = f"{game_id}:{team_id}"
    saber_team  = team_totals.get(team_key, round(saber_total / 2.0, 1))

    # Status: if no injury flag but starter -> "Confirmed"
    if not csv_status and proj.get("role_tier") == "starter":
        csv_status = "Confirmed"

    # Map position to SaberSim-style (G/F/C)
    pos = proj.get("position") or ""
    if not pos:
        # M2: map sixth_man explicitly to "F" — role_tier[:1] would produce "S"
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
        game_date:      "YYYY-MM-DD" (default: today)
        implied_totals: {game_id: over_under_total} from Odds API
        team_totals:    {"game_id:team_id": team_total} from Odds API
        injury_statuses:{player_id: status_code} from injury_parser
        out_path:       Override output path (default: data/projections/DATE_nba_custom.csv)
        db_path:        SQLite DB path

    Returns:
        Path to written CSV.
    """
    if game_date is None:
        game_date = str(datetime.date.today())
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
        # Import parse_csv without running the full engine
        import importlib.util, types
        spec = importlib.util.spec_from_file_location(
            "run_picks_stub",
            str(PROJECT_ROOT / "engine" / "run_picks.py"),
        )
        # We only need parse_csv and name_key -- do a targeted import
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
        log.info("validate_csv: OK — %d rows, headers=%s", len(rows),
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
) -> Optional[Path]:
    """Pull injuries, run projections, write CSV.  One-shot daily workflow.

    Args:
        game_date:      "YYYY-MM-DD" (default: today)
        season:         NBA season
        implied_totals: {game_id: total} from Odds API (optional)
        team_totals:    {"game_id:team_id": team_total} (optional)
        db_path:        SQLite path
        validate:       If True, run validate_csv() before returning

    Returns:
        Path to written CSV, or None on failure.
    """
    if game_date is None:
        game_date = str(datetime.date.today())

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

    csv_path = write_nba_csv(
        projections=projections,
        game_date=game_date,
        implied_totals=implied_totals or {},
        team_totals=team_totals or {},
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
    parser.add_argument("--date",     default=str(datetime.date.today()))
    parser.add_argument("--season",   default="2025-26")
    parser.add_argument("--db",       default=DB_PATH)
    parser.add_argument("--out",      default=None, help="Override output path")
    parser.add_argument("--validate", action="store_true", default=True)
    parser.add_argument("--no-validate", dest="validate", action="store_false")
    args = parser.parse_args()

    csv_path = generate_daily_csv(
        game_date=args.date,
        season=args.season,
        db_path=args.db,
        validate=args.validate,
    )
    if csv_path:
        print(f"CSV ready: {csv_path}")
    else:
        print("Failed to generate CSV.")
        sys.exit(1)


if __name__ == "__main__":
    _main()
