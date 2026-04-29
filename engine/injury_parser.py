"""NBA injury report parser -- Step 3 of the custom projection engine.

Pulls the NBA's official daily injury report PDF (via the
``nbainjuries`` package), normalizes statuses into the canonical
tokens the rest of the projector uses, and computes how many minutes
should be redistributed to the rest of the rotation when a player is
ruled OUT.

The output shape is deliberately shaped around two downstream
consumers:

* ``nba_projector.project_player`` -- takes ``injury_status`` as a
  kwarg (``"OUT"`` / ``"Q"`` / ``""``).
* ``csv_writer.py`` (step 4) -- emits the SaberSim Status column,
  which the *existing* ``run_picks.parse_csv`` already reads. The
  schema there is ``"O" / "Q" / "Confirmed" / ""`` (see
  ``memory/projects/custom-projection-engine.md``).

Both are covered by the ``InjuryEntry`` dataclass and the
``to_csv_status()`` helper.

Design constraints:
  1. Time leak is not a worry here -- the injury report for date ``D``
     is published same-day, so pulling the "latest" report for today
     is always fine. For backtests, we cache by date and pull the
     *final* (5pm ET) version for historical dates.
  2. The NBA publishes reports every ~2 hours starting around 5am ET.
     ``fetch_injury_report`` walks candidate hours high -> low and
     returns the most recent valid one for the target date. Absent
     reports return an empty list, not an exception, so the caller
     can fall back to "no injury adjustments" cleanly.
  3. Minutes redistribution is team-level, not position-level. We
     don't have reliable position data in ``player_index`` (the NBA
     ``CommonAllPlayers`` endpoint returns ``position = NULL``), and
     backfilling positions is a per-player call we don't need yet.
     Team-level proportional redistribution gets most of the signal;
     we'll revisit if backtest MAE is ugly at step 5.

CLI usage:

    python engine/injury_parser.py --date 2026-04-21
    python engine/injury_parser.py --date 2026-04-21 --team POR
    python engine/injury_parser.py --date 2026-04-21 --redistribute POR
"""
from __future__ import annotations

import argparse
import logging
import sqlite3
import sys
from contextlib import closing
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable, Optional

try:
    import pandas as pd
except ImportError:  # pragma: no cover
    print(
        "injury_parser requires pandas. Install with:\n"
        "  pip install pandas --break-system-packages",
        file=sys.stderr,
    )
    raise

from name_utils import fold_name
import projections_db as _pdb

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tunables. Stable across calls so the backtest harness is reproducible.
# ---------------------------------------------------------------------------

# Hours (ET) to try when pulling the NBA daily report, high -> low.
# 5pm is the canonical final version; 6:30pm is only used for late games
# and is rare, so we check 5pm first. Earlier versions are preliminary.
DEFAULT_REPORT_HOURS_ET: tuple[tuple[int, int], ...] = (
    (17, 0), (18, 30), (15, 0), (13, 0), (11, 0), (9, 0), (5, 30),
)

REDISTRIBUTE_LOOKBACK_GAMES: int = 20
REDISTRIBUTE_EWMA_SPAN: int = 10
# A player needs at least this many EWMA baseline minutes to count as
# "in the rotation" for redistribution purposes. Below this they
# typically only play in garbage time and shouldn't absorb a starter's
# minutes.
ROTATION_MIN_MINUTES: float = 10.0
# Hard cap so a redistributed bump can't push someone above 40 min/game
# (bench players rarely get pushed above ~38 even with starter out).
MAX_REDISTRIBUTED_MINUTES: float = 40.0


# Canonical internal status tokens. Order = precedence when multiple
# raw statuses conflict (shouldn't happen in practice).
STATUS_OUT = "OUT"
STATUS_DOUBTFUL = "DOUBTFUL"
STATUS_Q = "Q"
STATUS_PROBABLE = "PROBABLE"
STATUS_OK = "OK"
STATUS_UNKNOWN = ""


# NBA team full name -> 3-letter abbreviation. The injury report uses
# full names ("Philadelphia 76ers"); player_index uses abbreviations
# ("PHI"). We need to map report rows to the roster we have on file.
TEAM_NAME_TO_ABBREV: dict[str, str] = {
    "Atlanta Hawks":          "ATL",
    "Boston Celtics":         "BOS",
    "Brooklyn Nets":          "BKN",
    "Charlotte Hornets":      "CHA",
    "Chicago Bulls":          "CHI",
    "Cleveland Cavaliers":    "CLE",
    "Dallas Mavericks":       "DAL",
    "Denver Nuggets":         "DEN",
    "Detroit Pistons":        "DET",
    "Golden State Warriors":  "GSW",
    "Houston Rockets":        "HOU",
    "Indiana Pacers":         "IND",
    "LA Clippers":            "LAC",
    "Los Angeles Clippers":   "LAC",
    "Los Angeles Lakers":     "LAL",
    "Memphis Grizzlies":      "MEM",
    "Miami Heat":             "MIA",
    "Milwaukee Bucks":        "MIL",
    "Minnesota Timberwolves": "MIN",
    "New Orleans Pelicans":   "NOP",
    "New York Knicks":        "NYK",
    "Oklahoma City Thunder":  "OKC",
    "Orlando Magic":          "ORL",
    "Philadelphia 76ers":     "PHI",
    "Phoenix Suns":           "PHX",
    "Portland Trail Blazers": "POR",
    "Sacramento Kings":       "SAC",
    "San Antonio Spurs":      "SAS",
    "Toronto Raptors":        "TOR",
    "Utah Jazz":              "UTA",
    "Washington Wizards":     "WAS",
}


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class InjuryEntry:
    """One row of the daily injury report, normalized for the rest of
    the engine."""
    player_name: str           # flipped to "First Last"
    fold_name: str             # lowercased, diacritic-stripped
    team: str                  # 3-letter abbrev
    team_full: str             # full name as printed on the report
    status: str                # canonical: OUT / Q / OK / etc.
    raw_status: str            # original string from the PDF
    reason: str                # free text
    matchup: str               # "PHI@BOS"
    game_date: str             # "MM/DD/YYYY" from report
    game_time_et: str          # "07:00 (ET)"


@dataclass
class MinutesAdjustment:
    """How many projected minutes a player's baseline should move by
    because of injuries on their team."""
    player_name: str
    team: str
    baseline_minutes: float    # EWMA minutes before adjustment
    delta_minutes: float       # additive adjustment (positive = bump)
    capped: bool               # true if MAX_REDISTRIBUTED_MINUTES hit
    reason: str                # "absorbing 33.6 min from Damian Lillard (OUT)"


# ---------------------------------------------------------------------------
# Status normalization
# ---------------------------------------------------------------------------

_STATUS_MAP: dict[str, str] = {
    "out":                    STATUS_OUT,
    "not with team":          STATUS_OUT,     # G-League assignment etc.
    "out for season":         STATUS_OUT,
    "g league - on assignment": STATUS_OUT,
    "g league - two-way":     STATUS_OUT,
    "doubtful":               STATUS_DOUBTFUL,
    "questionable":           STATUS_Q,
    "day-to-day":             STATUS_Q,
    "day to day":             STATUS_Q,
    "probable":               STATUS_PROBABLE,
    "available":              STATUS_OK,
}


def normalize_status(raw: str) -> str:
    """Map a raw status string (from the PDF) to our canonical token.

    Unknown statuses return ``STATUS_UNKNOWN`` (empty string) and log
    a warning -- if the NBA invents a new status we want the operator
    to notice, not to silently treat them as playing.
    """
    key = (raw or "").strip().lower()
    if not key:
        return STATUS_UNKNOWN
    if key in _STATUS_MAP:
        return _STATUS_MAP[key]
    logger.warning("unknown injury status %r -- treating as unknown", raw)
    return STATUS_UNKNOWN


def to_csv_status(canonical: str) -> str:
    """Translate our canonical token to the SaberSim-schema Status
    value that ``run_picks.parse_csv`` reads.

    Per ``custom-projection-engine.md``:
        Out -> "O", Questionable -> "Q", active -> "Confirmed",
        unknown -> ""
    """
    if canonical == STATUS_OUT:
        return "O"
    if canonical in (STATUS_DOUBTFUL, STATUS_Q):
        return "Q"
    if canonical in (STATUS_PROBABLE, STATUS_OK):
        return "Confirmed"
    return ""


def to_projector_status(canonical: str) -> str:
    """Translate our canonical token to the kwarg
    ``nba_projector.project_player`` accepts (``"OUT"`` / ``"Q"`` / ``""``).

    Doubtful folds to OUT for projection purposes (they almost never
    play, and the Q x0.55 multiplier is too generous). Probable folds
    to "" (they almost always play full minutes)."""
    if canonical in (STATUS_OUT, STATUS_DOUBTFUL):
        return "OUT"
    if canonical == STATUS_Q:
        return "Q"
    return ""


# ---------------------------------------------------------------------------
# Name + team helpers
# ---------------------------------------------------------------------------

def _flip_name(last_first: str) -> str:
    """Flip "Embiid, Joel" -> "Joel Embiid". Also handles suffixes and
    multi-word first names.  Input without a comma passes through."""
    s = (last_first or "").strip()
    if "," not in s:
        return s
    last, first = s.split(",", 1)
    return f"{first.strip()} {last.strip()}".strip()


def _team_abbrev(team_full: str, matchup: str = "") -> str:
    """Resolve a team's 3-letter abbreviation.

    Prefers the ``TEAM_NAME_TO_ABBREV`` map. Falls back to parsing the
    matchup string (``"PHI@BOS"``) if we don't recognize the name --
    future NBA rebrands shouldn't silently drop injuries from the
    projection.
    """
    key = (team_full or "").strip()
    if key in TEAM_NAME_TO_ABBREV:
        return TEAM_NAME_TO_ABBREV[key]

    # case-insensitive retry (defensive)
    for name, abbrev in TEAM_NAME_TO_ABBREV.items():
        if name.lower() == key.lower():
            return abbrev

    # fallback: parse matchup, but we don't know which side. Log loud.
    mu = (matchup or "").upper().replace(" ", "")
    if "@" in mu:
        left, right = mu.split("@", 1)
        logger.warning(
            "unknown team %r on report; can't disambiguate from matchup %r",
            team_full, matchup,
        )
        return ""  # caller handles empty abbrev
    logger.warning("unknown team %r; no matchup to fall back on", team_full)
    return ""


# ---------------------------------------------------------------------------
# Fetch + parse the daily report
# ---------------------------------------------------------------------------

def _iter_candidate_timestamps(
    target_date: datetime,
    hours: Iterable[tuple[int, int]] = DEFAULT_REPORT_HOURS_ET,
) -> list[datetime]:
    """Enumerate candidate report timestamps on target_date, ordered
    by preference (most recent / most-authoritative first)."""
    out = []
    for h, m in hours:
        out.append(target_date.replace(hour=h, minute=m, second=0, microsecond=0))
    return out


def fetch_injury_report(
    target_date: datetime | str,
    *,
    hours: Iterable[tuple[int, int]] = DEFAULT_REPORT_HOURS_ET,
) -> list[InjuryEntry]:
    """Pull the most recent valid injury report for ``target_date``.

    Returns a list of :class:`InjuryEntry` rows. Returns ``[]`` if no
    valid report exists for that date -- caller should treat as "no
    injury adjustments" rather than crashing.

    Requires the ``nbainjuries`` package. If not installed, returns
    ``[]`` and logs a warning once.
    """
    try:
        import nbainjuries.injury as _inj
    except ImportError:
        logger.warning(
            "nbainjuries not installed; cannot fetch report. "
            "Install: pip install nbainjuries --break-system-packages"
        )
        return []

    if isinstance(target_date, str):
        target_date = datetime.strptime(target_date, "%Y-%m-%d")

    for ts in _iter_candidate_timestamps(target_date, hours=hours):
        try:
            valid = _inj.check_reportvalid(ts)
        except Exception as e:
            logger.debug("validation error for %s: %s", ts, e)
            valid = False
        if not valid:
            continue
        try:
            df = _inj.get_reportdata(ts, return_df=True)
        except Exception as e:
            logger.warning("get_reportdata failed for %s: %s", ts, e)
            continue
        logger.info(
            "injury report: %d rows, timestamp %s",
            len(df), ts.strftime("%Y-%m-%d %H:%M"),
        )
        return _df_to_entries(df)

    logger.info("no valid injury report found for %s", target_date.date())
    return []


def _df_to_entries(df: pd.DataFrame) -> list[InjuryEntry]:
    """Convert the nbainjuries DataFrame to a list of InjuryEntry."""
    entries: list[InjuryEntry] = []
    for rec in df.to_dict(orient="records"):
        raw_name = str(rec.get("Player Name", "")).strip()
        reason_raw = str(rec.get("Reason", "")).strip()
        # "NOT YET SUBMITTED" placeholder rows come through with
        # Player Name == Current Status == NaN. Skip them cleanly so
        # we don't emit bogus unknown-status warnings.
        if raw_name.lower() in ("", "nan", "none"):
            continue
        if reason_raw.upper().startswith("NOT YET SUBMITTED"):
            continue

        flipped = _flip_name(raw_name)
        if not flipped:
            continue

        team_full = str(rec.get("Team", "")).strip()
        matchup = str(rec.get("Matchup", "")).strip()
        team_abbrev = _team_abbrev(team_full, matchup=matchup)

        raw_status = str(rec.get("Current Status", "")).strip()
        canonical = normalize_status(raw_status)

        entries.append(InjuryEntry(
            player_name=flipped,
            fold_name=fold_name(flipped),
            team=team_abbrev,
            team_full=team_full,
            status=canonical,
            raw_status=raw_status,
            reason=str(rec.get("Reason", "")).strip(),
            matchup=matchup,
            game_date=str(rec.get("Game Date", "")).strip(),
            game_time_et=str(rec.get("Game Time", "")).strip(),
        ))
    return entries


def team_injuries(entries: list[InjuryEntry], team: str) -> list[InjuryEntry]:
    """Filter ``entries`` down to one team (by 3-letter abbrev)."""
    team = team.upper()
    return [e for e in entries if e.team == team]


# ---------------------------------------------------------------------------
# Minutes redistribution
# ---------------------------------------------------------------------------

def _team_roster_baselines(
    conn: sqlite3.Connection,
    team: str,
    *,
    before_date: Optional[str] = None,
    lookback_games: int = REDISTRIBUTE_LOOKBACK_GAMES,
    ewma_span: int = REDISTRIBUTE_EWMA_SPAN,
) -> dict[str, float]:
    """Return ``{fold_name: ewma_minutes_baseline}`` for everyone on
    the team who has at least a few recent games. ``team`` is a
    3-letter abbrev matching ``player_index.team``.

    We key on ``fold_name`` so downstream matching against the injury
    report is diacritic-insensitive.
    """
    # Resolve roster via player_index (by team).
    conn.row_factory = sqlite3.Row
    roster = conn.execute(
        "SELECT display_name, fold_name FROM player_index "
        "WHERE team = ? AND nba_api_id IS NOT NULL",
        (team,),
    ).fetchall()
    if not roster:
        return {}

    baselines: dict[str, float] = {}
    for r in roster:
        display = r["display_name"]
        folded = r["fold_name"] or fold_name(display)
        # pull last N games for this player
        sql = (
            "SELECT minutes FROM player_game_logs "
            "WHERE sport = 'nba' AND player_name = ? "
            "  AND minutes IS NOT NULL AND minutes > 0 "
        )
        params: list = [display]
        if before_date:
            sql += "AND game_date < ? "
            params.append(before_date)
        sql += "ORDER BY game_date DESC LIMIT ?"
        params.append(int(lookback_games))
        rows = conn.execute(sql, params).fetchall()
        if len(rows) < 3:
            continue
        # reverse so most recent is last -> EWMA weights it highest
        minutes = pd.to_numeric(
            pd.Series([row["minutes"] for row in rows][::-1]),
            errors="coerce",
        ).dropna()
        if minutes.empty:
            continue
        baselines[folded] = float(
            minutes.ewm(span=ewma_span, adjust=True).mean().iloc[-1]
        )
    return baselines


def redistribute_minutes(
    conn: sqlite3.Connection,
    team: str,
    out_players: Iterable[str],
    *,
    before_date: Optional[str] = None,
    lookback_games: int = REDISTRIBUTE_LOOKBACK_GAMES,
    ewma_span: int = REDISTRIBUTE_EWMA_SPAN,
    rotation_min_minutes: float = ROTATION_MIN_MINUTES,
    max_minutes: float = MAX_REDISTRIBUTED_MINUTES,
) -> list[MinutesAdjustment]:
    """Return per-player minutes bumps for everyone on ``team`` whose
    teammates are OUT.

    Model (team-level, position-agnostic):

    1. Build EWMA baselines for all rostered players with >= 3 recent
       games.
    2. Sum baselines of OUT players -> ``minutes_to_absorb``.
    3. Identify the rotation: non-OUT players with baseline >=
       ``rotation_min_minutes``.
    4. Distribute ``minutes_to_absorb`` proportional to each rotation
       player's current baseline. This keeps the allocation directional
       (higher-minute guys absorb more) without needing position data.
    5. Cap each bump so ``baseline + delta <= max_minutes``. If a cap
       kicks in, we redistribute the overflow one more pass to the
       remaining uncapped players.

    Returns a list of :class:`MinutesAdjustment`, non-zero deltas only.
    Empty list when nothing to redistribute (no OUTs, or empty roster).
    """
    team = team.upper()
    baselines = _team_roster_baselines(
        conn, team,
        before_date=before_date,
        lookback_games=lookback_games,
        ewma_span=ewma_span,
    )
    if not baselines:
        return []

    out_folds = {fold_name(p) for p in out_players if p}
    out_folds = {f for f in out_folds if f}  # drop empties

    minutes_to_absorb = sum(
        mins for f, mins in baselines.items() if f in out_folds
    )
    reason_parts = [
        f"{f.title()} ({baselines[f]:.1f} min)"
        for f in out_folds if f in baselines
    ]
    if minutes_to_absorb <= 0 or not reason_parts:
        return []

    # rotation = non-OUT players above the minutes threshold
    rotation = {
        f: m for f, m in baselines.items()
        if f not in out_folds and m >= rotation_min_minutes
    }
    if not rotation:
        return []

    # Two-pass allocation: proportional first, then spill uncapped
    deltas: dict[str, float] = {f: 0.0 for f in rotation}
    capped: set[str] = set()
    remaining = float(minutes_to_absorb)
    # Safety: max 5 passes. Each pass either finishes or shrinks the
    # uncapped set, so 5 is way more than enough for 30 rotation guys.
    for _pass in range(5):
        share_pool = {f: rotation[f] for f in rotation if f not in capped}
        total = sum(share_pool.values())
        if total <= 0 or remaining <= 0.01:
            break
        spill = 0.0
        for f, base in share_pool.items():
            proportional = remaining * (base / total)
            room = max_minutes - (rotation[f] + deltas[f])
            if proportional >= room:
                # cap this player, refund the overflow to spill
                deltas[f] += room
                spill += (proportional - room)
                capped.add(f)
            else:
                deltas[f] += proportional
        remaining = spill

    # Resolve back to display names
    # Build a fold -> display_name map from player_index.
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT fold_name, display_name FROM player_index "
        "WHERE team = ? AND nba_api_id IS NOT NULL",
        (team,),
    ).fetchall()
    fold_to_display = {
        (r["fold_name"] or fold_name(r["display_name"])): r["display_name"]
        for r in rows
    }

    reason = "absorbing " + ", ".join(reason_parts)
    adjustments: list[MinutesAdjustment] = []
    for f, delta in deltas.items():
        if delta <= 0.05:
            continue
        adjustments.append(MinutesAdjustment(
            player_name=fold_to_display.get(f, f.title()),
            team=team,
            baseline_minutes=baselines[f],
            delta_minutes=delta,
            capped=(f in capped),
            reason=reason,
        ))
    adjustments.sort(key=lambda a: a.delta_minutes, reverse=True)
    return adjustments


# ---------------------------------------------------------------------------
# High-level index -- what csv_writer.py (step 4) will consume
# ---------------------------------------------------------------------------

def build_injury_index(
    conn: sqlite3.Connection,
    target_date: datetime | str,
    *,
    hours: Iterable[tuple[int, int]] = DEFAULT_REPORT_HOURS_ET,
    lookback_games: int = REDISTRIBUTE_LOOKBACK_GAMES,
    ewma_span: int = REDISTRIBUTE_EWMA_SPAN,
) -> dict:
    """One-stop call for the CSV writer.

    Returns a dict with:
        'entries':          list[InjuryEntry]          -- raw injuries
        'by_player':        dict[fold_name -> entry]   -- fast lookup
        'by_team_out':      dict[team -> list[str]]    -- OUT fold_names
        'minutes_adjust':   dict[fold_name -> MinutesAdjustment]
    """
    entries = fetch_injury_report(target_date, hours=hours)
    by_player = {e.fold_name: e for e in entries if e.fold_name}

    by_team_out: dict[str, list[str]] = {}
    for e in entries:
        if e.status in (STATUS_OUT, STATUS_DOUBTFUL) and e.team:
            by_team_out.setdefault(e.team, []).append(e.fold_name)

    minutes_adjust: dict[str, MinutesAdjustment] = {}
    for team, out_folds in by_team_out.items():
        for adj in redistribute_minutes(
            conn, team, out_folds,
            lookback_games=lookback_games,
            ewma_span=ewma_span,
        ):
            minutes_adjust[fold_name(adj.player_name)] = adj

    return {
        "entries":        entries,
        "by_player":      by_player,
        "by_team_out":    by_team_out,
        "minutes_adjust": minutes_adjust,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _print_entries(entries: list[InjuryEntry], *, team: str | None = None) -> None:
    if team:
        entries = team_injuries(entries, team)
    if not entries:
        print("(no entries)")
        return
    # Group by team for readability
    by_team: dict[str, list[InjuryEntry]] = {}
    for e in entries:
        by_team.setdefault(e.team or "???", []).append(e)
    for t in sorted(by_team):
        print(f"\n[{t}]  ({by_team[t][0].team_full})")
        for e in by_team[t]:
            print(
                f"  {e.player_name:28s}  "
                f"{e.raw_status:13s}  -> {e.status:10s}  "
                f"{e.reason[:60]}"
            )


def _print_adjustments(adjustments: list[MinutesAdjustment]) -> None:
    if not adjustments:
        print("(no redistribution needed)")
        return
    print(f"{'Player':28s} {'Team':5s} {'base':>8s} {'delta':>8s} {'total':>8s}")
    for a in adjustments:
        flag = "*" if a.capped else " "
        total = a.baseline_minutes + a.delta_minutes
        print(
            f"{a.player_name:28s} {a.team:5s} "
            f"{a.baseline_minutes:8.2f} {a.delta_minutes:+8.2f} "
            f"{total:8.2f}{flag}"
        )
    if any(a.capped for a in adjustments):
        print(f"  * capped at {MAX_REDISTRIBUTED_MINUTES} min")


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Pull + normalize the NBA daily injury report.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--date", required=True, help="YYYY-MM-DD target date.")
    p.add_argument("--team", default=None, help="Filter to one team (abbrev).")
    p.add_argument(
        "--redistribute", default=None,
        help="Print minutes redistribution preview for this team (abbrev).",
    )
    p.add_argument("--db-path", default=None, help="Override projections.db path.")
    p.add_argument("-v", "--verbose", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    target = datetime.strptime(args.date, "%Y-%m-%d")
    entries = fetch_injury_report(target)
    if not entries:
        print(f"No injury report rows for {args.date}.")
        return 0

    _print_entries(entries, team=args.team)

    if args.redistribute:
        team = args.redistribute.upper()
        out_folds = [
            e.fold_name for e in entries
            if e.team == team and e.status in (STATUS_OUT, STATUS_DOUBTFUL)
        ]
        if not out_folds:
            print(f"\nNo OUT/Doubtful players for {team}; nothing to redistribute.")
            return 0

        conn = _pdb.get_connection(args.db_path)
        try:
            adjustments = redistribute_minutes(conn, team, out_folds)
        finally:
            conn.close()

        print(
            f"\nMinutes redistribution for {team} "
            f"(absorbing {len(out_folds)} OUT):"
        )
        _print_adjustments(adjustments)

    return 0


if __name__ == "__main__":
    sys.exit(main())
