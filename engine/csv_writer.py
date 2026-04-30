"""SaberSim-schema CSV writer.

Step 4 of the custom projection engine.  Combines:
    * ``nba_projector.project_player``          -- per-player stat projections
    * ``injury_parser.build_injury_index``      -- daily injury report + minutes
      redistribution
    * game context from the operator (spread / implied totals / B2B flags)

into a CSV that ``engine.run_picks.parse_csv`` can consume with zero changes to
the existing engine.

-------------------------------------------------------------------------------
Output schema (matches SaberSim's minimum subset that ``parse_csv`` reads on
the NBA branch):

    Name, Pos, Team, Opp, Status, Saber Team, Saber Total, Min, dk_std,
    PTS, RB, AST, 3PT

Notes:

* ``Status`` -- "O" / "Q" / "Confirmed" / "" per spec
  (``memory/projects/custom-projection-engine.md``).
* ``dk_std`` = ``proj_pts * 0.35`` placeholder until we build an empirical
  std model (spec calls this out explicitly -- do not tune).
* ``Saber Team`` -- the team's implied total (from the Odds API spread +
  game total), per-player.
* ``Saber Total`` -- the game total, both sides identical.
* ``RB`` is the SaberSim column name for rebounds; ``parse_csv`` reads ``RB``
  before ``REB``.  ``3PT`` likewise before ``3PM``.  Keep as-is.
* ``Salary`` column is intentionally omitted -- ``parse_csv`` does not read
  it on the NBA branch and we have no salary source in this pipeline.

-------------------------------------------------------------------------------
Injury -> projection flow:

1. ``build_injury_index`` returns ``{by_player, by_team_out, minutes_adjust}``.
2. For each player on a team's roster:
     a. ``by_player[fold]`` gives us their canonical status (OUT / Q / OK / ...).
     b. ``to_projector_status`` -> kwarg for ``project_player`` (which scales
        the minutes baseline for "Q" via ``INJURY_Q_MINUTES_MULT``).
     c. ``to_csv_status`` -> SaberSim Status string.
3. Players whose status maps to "O" are emitted with all zero stats --
   the engine never bets on an OUT player and ``parse_csv`` already drops
   them downstream.
4. Players listed in ``minutes_adjust`` receive a *post-hoc* minutes bump on
   top of whatever the projector returned.  We scale every stat uniformly
   by ``(new_min / old_min)`` -- approximate, but matches the per-minute-rate
   model used to build the projection.

-------------------------------------------------------------------------------
CLI (smoke tests only; the production driver lives outside this module):

    python csv_writer.py --demo --date 2026-04-21 [--out demo.csv]

``--demo`` uses a hardcoded slate of 2 games so we can sanity-check the
round-trip through ``run_picks.parse_csv`` without the Odds API.  Real runs
will build ``GameContext`` from the Odds API daily pipeline (wired in step 5).
"""

from __future__ import annotations

import argparse
import csv
import logging
import sqlite3
import sys
from dataclasses import dataclass, field
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Iterable, Optional

# Script-style imports -- these modules live alongside us in engine/ with
# no __init__.py.  Same pattern the rest of the engine uses.
try:
    from engine.name_utils import fold_name                 # type: ignore
    from engine import projections_db as _pdb               # type: ignore
    from engine import nba_projector as _proj               # type: ignore
    from engine import injury_parser as _ij                 # type: ignore
    from engine.paths import resolve_db_path                # type: ignore
except ImportError:  # pragma: no cover -- script mode
    from name_utils import fold_name                         # type: ignore
    import projections_db as _pdb                            # type: ignore
    import nba_projector as _proj                            # type: ignore
    import injury_parser as _ij                              # type: ignore
    try:
        from paths import resolve_db_path                    # type: ignore
    except ImportError:
        resolve_db_path = None  # type: ignore

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

#: Column order the writer emits.  Do not rearrange without updating the
#: round-trip test below -- ``parse_csv`` indexes into these names.
CSV_HEADER: list[str] = [
    "Name", "Pos", "Team", "Opp", "Status",
    "Saber Team", "Saber Total",
    "Min", "dk_std",
    "PTS", "RB", "AST", "3PT",
]

#: Multiplier for the dk_std placeholder.  Spec-defined; do not tune.
DK_STD_FACTOR: float = 0.35


# ---------------------------------------------------------------------------
# GameContext -- one per game the operator wants to project
# ---------------------------------------------------------------------------

@dataclass
class GameContext:
    """Everything the projector needs that is NOT in the DB.

    ``home_team`` / ``away_team`` are 3-letter abbreviations (e.g. ``"DEN"``).
    ``implied_home_total`` + ``implied_away_total`` come from the Odds API
    spread + game total.  ``spread_home`` is the home team's spread
    (negative = favorite, positive = underdog) -- used to trigger the
    blowout minutes haircut for players on the favored side.
    """
    home_team: str
    away_team: str
    implied_home_total: float
    implied_away_total: float
    game_total: float
    spread_home: float = 0.0
    is_b2b_home: bool = False
    is_b2b_away: bool = False

    def iter_sides(self) -> Iterable[tuple[str, str, float, bool, float]]:
        """Yield ``(team, opp, implied_total, is_b2b, spread_for_team)`` for
        the two sides.  ``spread_for_team`` is signed from that team's
        perspective (negative = that team is favored)."""
        yield (
            self.home_team, self.away_team,
            self.implied_home_total, self.is_b2b_home, self.spread_home,
        )
        yield (
            self.away_team, self.home_team,
            self.implied_away_total, self.is_b2b_away, -self.spread_home,
        )


# ---------------------------------------------------------------------------
# Row assembly helpers
# ---------------------------------------------------------------------------

@dataclass
class _Row:
    """Internal row shape before we serialize to CSV."""
    name: str
    pos: str
    team: str
    opp: str
    status: str          # SaberSim-schema: "O" / "Q" / "Confirmed" / ""
    saber_team: float
    saber_total: float
    minutes: float
    dk_std: float
    pts: float
    reb: float
    ast: float
    tpm: float
    notes: list = field(default_factory=list)

    def to_cells(self) -> list[str]:
        def _num(x: float, nd: int = 2) -> str:
            if x is None:
                return ""
            return f"{float(x):.{nd}f}"

        return [
            self.name, self.pos, self.team, self.opp, self.status,
            _num(self.saber_team, 4),
            _num(self.saber_total, 2),
            _num(self.minutes, 2),
            _num(self.dk_std, 2),
            _num(self.pts, 2),
            _num(self.reb, 2),
            _num(self.ast, 2),
            _num(self.tpm, 2),
        ]


def _roster_for_team(conn: sqlite3.Connection, team: str) -> list[dict]:
    """Return every player in ``player_index`` tagged to ``team``.

    Returns a list of ``{"fold_name", "display_name", "position"}`` dicts.
    ``player_index`` is populated by ``projections_db.pull_nba_player_index``
    so the caller must have run that at least once before calling us.
    """
    if not team:
        return []
    rows = conn.execute(
        "SELECT fold_name, display_name, position "
        "FROM player_index "
        "WHERE nba_api_id IS NOT NULL AND team = ? "
        "ORDER BY display_name",
        (team,),
    ).fetchall()
    return [
        {
            "fold_name":    r["fold_name"] if hasattr(r, "keys") else r[0],
            "display_name": r["display_name"] if hasattr(r, "keys") else r[1],
            "position":     (r["position"] if hasattr(r, "keys") else r[2]) or "",
        }
        for r in rows
    ]


def _resolve_status(
    fold: str,
    injury_index: Optional[dict],
) -> tuple[str, str, str]:
    """Return (csv_status, projector_status_kwarg, canonical_token).

    - csv_status: the string to write to the Status column.
    - projector_status_kwarg: string passed to ``project_player``.
    - canonical_token: ``_ij.STATUS_OUT`` etc., for OUT-bailout decisions.
    """
    if not injury_index:
        return "", "", ""
    entry = injury_index.get("by_player", {}).get(fold)
    if not entry:
        return "", "", ""
    canonical = entry.status
    return (
        _ij.to_csv_status(canonical),
        _ij.to_projector_status(canonical),
        canonical,
    )


def _apply_minutes_bump(
    result: "_proj.ProjectionResult",
    fold: str,
    injury_index: Optional[dict],
) -> "_proj.ProjectionResult":
    """Post-hoc minutes redistribution bump.

    ``injury_index["minutes_adjust"][fold]`` was built by
    ``injury_parser.redistribute_minutes`` using the *baseline* EWMA minutes
    before the projector applied its own B2B / blowout / Q haircuts.  We
    still want starters to absorb the vacated minutes, so we scale the
    projector's output proportionally: every stat moves by
    ``(result.minutes + delta) / result.minutes``.

    No-op if the bump is zero or the result already has zero minutes
    (projector bailed or player is OUT).
    """
    if not injury_index:
        return result
    adj = injury_index.get("minutes_adjust", {}).get(fold)
    if adj is None or not adj.delta_minutes:
        return result
    if result.minutes <= 0:
        return result
    new_min = result.minutes + adj.delta_minutes
    if new_min <= 0:
        return result
    factor = new_min / result.minutes
    result.minutes = new_min
    result.pts = result.pts * factor
    result.reb = result.reb * factor
    result.ast = result.ast * factor
    result.tpm = result.tpm * factor
    result.notes = list(result.notes) + [
        f"minutes bump +{adj.delta_minutes:.1f} ({adj.reason})"
    ]
    return result


def _zero_row(
    *,
    name: str, pos: str, team: str, opp: str,
    status: str, saber_team: float, saber_total: float,
    note: str,
) -> _Row:
    """Build a row for a player we refuse to project (OUT, not enough
    games, etc.).  Stats = 0, Min = 0; ``parse_csv`` drops zero-PTS rows
    downstream anyway."""
    return _Row(
        name=name, pos=pos, team=team, opp=opp,
        status=status,
        saber_team=saber_team, saber_total=saber_total,
        minutes=0.0, dk_std=0.0,
        pts=0.0, reb=0.0, ast=0.0, tpm=0.0,
        notes=[note],
    )


def _project_team(
    conn: sqlite3.Connection,
    *,
    team: str,
    opp: str,
    implied_total: float,
    saber_total: float,
    is_b2b: bool,
    spread_for_team: float,
    target_date: str,
    league_avg_total: Optional[float],
    injury_index: Optional[dict],
) -> list[_Row]:
    """Project every rostered player for ``team`` and return _Row objects."""
    roster = _roster_for_team(conn, team)
    if not roster:
        logger.warning(
            "no players in player_index for team=%r -- did you run "
            "projections_db.pull_nba_player_index?", team,
        )
        return []

    blowout_spread = spread_for_team  # project_player handles the threshold
    rows: list[_Row] = []

    for p in roster:
        fold = p["fold_name"]
        display = p["display_name"] or fold
        pos = p["position"] or ""

        csv_status, proj_status, canonical = _resolve_status(fold, injury_index)

        # OUT players: short-circuit, don't even hit the projector.
        if canonical in (_ij.STATUS_OUT, _ij.STATUS_DOUBTFUL):
            rows.append(_zero_row(
                name=display, pos=pos, team=team, opp=opp,
                status="O",
                saber_team=implied_total, saber_total=saber_total,
                note=f"OUT per injury report ({canonical})",
            ))
            continue

        try:
            result = _proj.project_player(
                conn, display,
                opponent=opp,
                implied_total=implied_total,
                league_avg_total=league_avg_total,
                before_date=target_date,
                is_b2b=is_b2b,
                blowout_spread=blowout_spread,
                injury_status=proj_status,
            )
        except LookupError as e:
            # Not enough games: emit a zero row marked "unknown status".
            # The engine will skip unknown-status rows on parse.
            logger.debug("skip %s: %s", display, e)
            rows.append(_zero_row(
                name=display, pos=pos, team=team, opp=opp,
                status=csv_status,  # may still be Q or "" -- honor the report
                saber_team=implied_total, saber_total=saber_total,
                note=f"no projection: {e}",
            ))
            continue
        except Exception as e:  # defensive -- projector shouldn't raise otherwise
            logger.warning("projector error for %s: %s", display, e)
            rows.append(_zero_row(
                name=display, pos=pos, team=team, opp=opp,
                status=csv_status,
                saber_team=implied_total, saber_total=saber_total,
                note=f"projector error: {e}",
            ))
            continue

        result = _apply_minutes_bump(result, fold, injury_index)

        rows.append(_Row(
            name=result.player_name,   # canonical casing from DB
            pos=pos,
            team=team,
            opp=opp,
            status=csv_status,
            saber_team=implied_total,
            saber_total=saber_total,
            minutes=result.minutes,
            dk_std=result.pts * DK_STD_FACTOR,
            pts=result.pts,
            reb=result.reb,
            ast=result.ast,
            tpm=result.tpm,
            notes=result.notes,
        ))

    return rows


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def write_nba_csv(
    output_path: Path | str,
    *,
    games: list[GameContext],
    conn: sqlite3.Connection,
    target_date: str,
    league_avg_total: Optional[float] = None,
    injury_index: Optional[dict] = None,
) -> dict:
    """Build a SaberSim-schema CSV for ``target_date`` and write it to
    ``output_path``.  Returns a small summary dict for the CLI / tests.

    Parameters
    ----------
    output_path
        Target file path.  Parent directory must exist.
    games
        List of :class:`GameContext`.  Duplicated team abbreviations across
        games are not supported (a team plays at most one game per day in
        the NBA regular season).
    conn
        Open SQLite connection to the projections DB.
    target_date
        ``"YYYY-MM-DD"``.  Used to (a) exclude same-day game logs from EWMA
        windows and (b) as the injury-report lookup date.
    league_avg_total
        If ``None``, computed once via
        ``nba_projector.league_avg_game_total(conn, before_date=target_date)``
        and reused across every player.
    injury_index
        If ``None``, built via
        ``injury_parser.build_injury_index(conn, target_date)``.

    Returns
    -------
    dict with ``rows_written``, ``games``, ``teams``, ``out_count``,
    ``projected_count``, and ``path`` keys.
    """
    if league_avg_total is None:
        league_avg_total = _proj.league_avg_game_total(
            conn, before_date=target_date,
        )

    if injury_index is None:
        injury_index = _ij.build_injury_index(conn, target_date)

    all_rows: list[_Row] = []
    teams_seen: set[str] = set()
    for g in games:
        for team, opp, implied, is_b2b, spread in g.iter_sides():
            if team in teams_seen:
                logger.warning(
                    "team %s appears in multiple games on %s -- "
                    "emitting both, but this is usually a data error",
                    team, target_date,
                )
            teams_seen.add(team)
            all_rows.extend(_project_team(
                conn,
                team=team, opp=opp,
                implied_total=implied,
                saber_total=g.game_total,
                is_b2b=is_b2b,
                spread_for_team=spread,
                target_date=target_date,
                league_avg_total=league_avg_total,
                injury_index=injury_index,
            ))

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(CSV_HEADER)
        for r in all_rows:
            writer.writerow(r.to_cells())

    out_count = sum(1 for r in all_rows if r.status == "O")
    projected_count = sum(1 for r in all_rows if r.pts > 0)

    summary = {
        "path":            str(path),
        "rows_written":    len(all_rows),
        "games":           len(games),
        "teams":           len(teams_seen),
        "out_count":       out_count,
        "projected_count": projected_count,
    }
    logger.info(
        "wrote %d rows to %s (%d games, %d teams, %d OUT, %d projected)",
        summary["rows_written"], summary["path"],
        summary["games"], summary["teams"],
        summary["out_count"], summary["projected_count"],
    )
    return summary


# ---------------------------------------------------------------------------
# Round-trip verification
# ---------------------------------------------------------------------------

def verify_roundtrip(csv_path: Path | str) -> dict:
    """Feed our CSV back through ``run_picks.parse_csv`` to confirm the
    schema matches.  Returns a summary with the parsed player count and
    a sample row.

    Raises if ``parse_csv`` rejects the schema or returns zero players.
    """
    # Importing run_picks is heavy (pulls in requests, filelock, the odds-API
    # layer, etc.) so we do it lazily inside the test harness only.
    try:
        from engine import run_picks   # type: ignore
    except ImportError:
        import run_picks               # type: ignore

    # parse_csv signature: parse_csv(filepath) -> (list[dict], sport_str)
    players, sport = run_picks.parse_csv(str(csv_path))
    if sport != "NBA":
        raise RuntimeError(
            f"parse_csv detected sport={sport!r} from {csv_path!r}; expected NBA"
        )
    if not players:
        raise RuntimeError(
            f"parse_csv returned 0 players from {csv_path!r} -- schema mismatch"
        )

    first = players[0]
    # parse_csv returns dicts with lowercase shape keys + uppercase stat keys.
    required = {"name", "team", "opp", "PTS", "REB", "AST", "3PM"}
    missing = required - set(first.keys())
    if missing:
        raise RuntimeError(
            f"parse_csv output missing required keys {missing!r}; "
            f"got {sorted(first.keys())!r}"
        )

    return {
        "parsed_count": len(players),
        "sport":        sport,
        "sample":       {k: first.get(k) for k in sorted(required)},
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

#: Hardcoded 2-game slate for ``--demo``.  Totals picked from the real
#: 2026-04-20 SaberSim CSV so players in the DB will project.
_DEMO_GAMES: list[GameContext] = [
    GameContext(
        home_team="DEN", away_team="MIN",
        implied_home_total=118.5, implied_away_total=113.1,
        game_total=231.6, spread_home=-5.4,
        is_b2b_home=False, is_b2b_away=False,
    ),
    GameContext(
        home_team="LAC", away_team="LAL",
        implied_home_total=117.0, implied_away_total=115.0,
        game_total=232.0, spread_home=-2.0,
        is_b2b_home=False, is_b2b_away=False,
    ),
]


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Write a SaberSim-schema CSV from the custom projection engine.",
    )
    p.add_argument("--date", default=None,
                   help="Target date YYYY-MM-DD. Defaults to today.")
    p.add_argument("--out", default=None,
                   help="Output CSV path. Defaults to "
                        "data/custom_projections_<date>.csv.")
    p.add_argument("--demo", action="store_true",
                   help="Use the hardcoded demo slate (no Odds API needed).")
    p.add_argument("--verify", action="store_true",
                   help="Round-trip the output through run_picks.parse_csv "
                        "after writing.")
    p.add_argument("--db", default=None,
                   help="Override DB path (defaults to data/projections.db).")
    p.add_argument("-v", "--verbose", action="count", default=0,
                   help="Increase log verbosity (-v = INFO, -vv = DEBUG).")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    level = logging.WARNING
    if args.verbose >= 2:
        level = logging.DEBUG
    elif args.verbose >= 1:
        level = logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
    )

    # M2: use ET-aware now() so date rolls at midnight Eastern, not UTC
    target_date = args.date or datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")

    if not args.demo:
        logger.error(
            "non-demo runs need a real slate source; use --demo for now "
            "(step 5 wires the Odds API).",
        )
        return 2

    games = _DEMO_GAMES

    out = args.out
    if out is None:
        if resolve_db_path is not None:
            data_dir = Path(resolve_db_path()).parent
        else:
            data_dir = Path("data")
        out = data_dir / f"custom_projections_{target_date}.csv"

    conn = _pdb.get_connection(args.db)
    try:
        summary = write_nba_csv(
            out,
            games=games,
            conn=conn,
            target_date=target_date,
        )
    finally:
        conn.close()

    print(f"wrote {summary['rows_written']} rows to {summary['path']}")
    print(f"  games={summary['games']}  teams={summary['teams']}  "
          f"OUT={summary['out_count']}  projected={summary['projected_count']}")

    if args.verify:
        rt = verify_roundtrip(summary["path"])
        print(f"round-trip: parse_csv returned {rt['parsed_count']} players (sport={rt['sport']})")
        print(f"  sample: {rt['sample']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
