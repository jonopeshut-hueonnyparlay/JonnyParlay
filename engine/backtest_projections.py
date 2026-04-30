"""Walk-forward backtest harness for the custom projection engine.

Step 5 of the custom projection engine.  Answers one question per spec:

    "For every (player, game) the DB has game logs for, how close does
     ``nba_projector.project_player`` (trained only on *prior* games) get
     to the actual box score?"

The projection gate in the spec is MAE-based:

    PTS  <= 5.0
    REB  <= 2.5
    AST  <= 2.0

CLV is the *primary* edge indicator downstream, but CLV requires the real
odds-API pipeline and a parallel-run window to evaluate.  This module
covers the pre-parallel-run check: does the projector's *stat accuracy*
clear the spec bar before we bother bolting it into ``run_picks.py``?

-------------------------------------------------------------------------------
What this does
-------------------------------------------------------------------------------

1. Pulls every row of ``player_game_logs`` in the requested date range.
2. For each row, calls ``project_player`` with ``before_date=game_date``
   so the projection sees only games *strictly before* the one being
   predicted (no leakage).
3. Records ``(actual, projected, error)`` per stat.
4. Aggregates MAE, RMSE, and mean bias across the full window, and
   emits a per-player breakdown for the top-N highest-sample players.
5. Exits with status 1 if any MAE target is exceeded.

-------------------------------------------------------------------------------
Known simplifications (document, don't fix yet)
-------------------------------------------------------------------------------

* ``implied_total`` is set to ``league_avg_game_total`` for every game
  because we don't have historical odds-API data.  The projector's pace
  factor is therefore ~1.0 across the backtest.  A future iteration
  could use the actual post-game total as a proxy, but that leaks future
  information.  This is a known bias source -- expect PTS MAE to run a
  touch high on high/low-pace games.
* ``is_b2b`` and ``blowout_spread`` are omitted.  We could derive B2B
  from consecutive game dates in the DB, but for the v1 bar we want
  baseline EWMA accuracy, not minutes modelling accuracy.
* Injury status is omitted.  A player who played 8 minutes due to a
  mid-game injury will still show up in the backtest with big residuals
  -- use ``--min-minutes`` to filter those out.

-------------------------------------------------------------------------------
CLI
-------------------------------------------------------------------------------

    # Full-window summary over last 14 days:
    python backtest_projections.py --dates 2026-03-29:2026-04-12

    # Per-player breakdown (top 30 by sample size):
    python backtest_projections.py --dates 2026-04-01:2026-04-12 --per-player 30

    # Dump every row to CSV for ad-hoc analysis:
    python backtest_projections.py --dates 2026-04-01:2026-04-12 \\
        --out /tmp/backtest_rows.csv

    # Use a non-default DB (e.g. the test DB):
    python backtest_projections.py --db /tmp/projections_test.db \\
        --dates 2026-04-01:2026-04-12
"""

from __future__ import annotations

import argparse
import csv
import logging
import math
import sqlite3
import statistics
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

try:
    from engine.name_utils import fold_name         # type: ignore
    from engine import projections_db as _pdb       # type: ignore
    from engine import nba_projector as _proj       # type: ignore
except ImportError:  # pragma: no cover -- script mode
    from name_utils import fold_name                 # type: ignore
    import projections_db as _pdb                    # type: ignore
    import nba_projector as _proj                    # type: ignore

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: MAE gate per the custom-projection-engine spec.
TARGET_MAE: dict[str, float] = {
    "pts": 5.0,
    "reb": 2.5,
    "ast": 2.0,
    "tpm": 1.5,   # not in spec; pragmatic bar (3PT MAE ~1 expected)
}

#: Stats we project and score against.
STATS: tuple[str, ...] = _proj.STATS_PROJECTED

#: Default min-minutes filter -- below this, the game is dominated by
#: minutes model noise rather than per-minute rate accuracy.
DEFAULT_MIN_MINUTES: float = 15.0


# ---------------------------------------------------------------------------
# Row types
# ---------------------------------------------------------------------------

@dataclass
class BacktestRow:
    """One (player, game) backtest result.  Stats on the right of the
    dataclass; the error columns are computed post-hoc for readability."""
    game_date: str
    player_name: str
    opponent: str
    minutes_actual: float
    minutes_proj: float
    games_used: int
    # actuals
    pts_actual: float
    reb_actual: float
    ast_actual: float
    tpm_actual: float
    # projections
    pts_proj: float
    reb_proj: float
    ast_proj: float
    tpm_proj: float
    # bookkeeping
    skipped_reason: str = ""   # empty if projected; populated if skipped

    @property
    def projected(self) -> bool:
        return not self.skipped_reason

    def err(self, stat: str) -> float:
        actual = getattr(self, f"{stat}_actual")
        proj = getattr(self, f"{stat}_proj")
        return proj - actual

    def abs_err(self, stat: str) -> float:
        return abs(self.err(stat))


# ---------------------------------------------------------------------------
# DB access
# ---------------------------------------------------------------------------

def _pull_games(
    conn: sqlite3.Connection,
    *,
    start_date: str,
    end_date: str,
    min_minutes: float,
    player_filter: Optional[str] = None,
) -> list[dict]:
    """Return candidate (player, game) rows in [start_date, end_date].

    ``player_filter`` is matched on ``fold_name`` if provided.
    """
    sql = (
        "SELECT player_id, player_name, game_date, opponent, "
        "       minutes, pts, reb, ast, tpm "
        "FROM player_game_logs "
        "WHERE sport = 'nba' "
        "  AND game_date BETWEEN ? AND ? "
        "  AND minutes IS NOT NULL AND minutes >= ? "
    )
    params: list = [start_date, end_date, min_minutes]
    rows = conn.execute(sql + "ORDER BY game_date, player_name", params).fetchall()
    out: list[dict] = []
    target_fold = fold_name(player_filter) if player_filter else None
    for r in rows:
        d = dict(r) if hasattr(r, "keys") else {
            "player_id": r[0], "player_name": r[1], "game_date": r[2],
            "opponent": r[3], "minutes": r[4],
            "pts": r[5], "reb": r[6], "ast": r[7], "tpm": r[8],
        }
        if target_fold and fold_name(d["player_name"]) != target_fold:
            continue
        out.append(d)
    return out


# ---------------------------------------------------------------------------
# Backtest driver
# ---------------------------------------------------------------------------

def backtest(
    conn: sqlite3.Connection,
    *,
    start_date: str,
    end_date: str,
    min_minutes: float = DEFAULT_MIN_MINUTES,
    player_filter: Optional[str] = None,
    limit: Optional[int] = None,
) -> list[BacktestRow]:
    """Run the walk-forward backtest over ``[start_date, end_date]``.

    Returns one :class:`BacktestRow` per game log row.  Rows the projector
    refused (< ``MIN_GAMES_FOR_PROJECTION`` prior games) still come back,
    with ``skipped_reason`` populated and projections set to ``nan`` so
    downstream aggregators can filter them out cleanly.
    """
    games = _pull_games(
        conn,
        start_date=start_date,
        end_date=end_date,
        min_minutes=min_minutes,
        player_filter=player_filter,
    )
    if limit:
        games = games[:limit]
    logger.info(
        "backtest window %s..%s -- %d candidate rows (min_minutes=%.1f)",
        start_date, end_date, len(games), min_minutes,
    )

    # Cache league-avg total per game_date so we don't recompute it for
    # every player on the slate.
    league_avg_cache: dict[str, float] = {}

    out: list[BacktestRow] = []
    n_projected = 0
    n_skipped = 0
    for i, g in enumerate(games):
        gd = g["game_date"]
        if gd not in league_avg_cache:
            league_avg_cache[gd] = _proj.league_avg_game_total(
                conn, before_date=gd,
            )
        league_avg = league_avg_cache[gd]

        row = BacktestRow(
            game_date=gd,
            player_name=g["player_name"],
            opponent=g["opponent"] or "",
            minutes_actual=float(g["minutes"] or 0),
            minutes_proj=float("nan"),
            games_used=0,
            pts_actual=float(g["pts"] or 0),
            reb_actual=float(g["reb"] or 0),
            ast_actual=float(g["ast"] or 0),
            tpm_actual=float(g["tpm"] or 0),
            pts_proj=float("nan"),
            reb_proj=float("nan"),
            ast_proj=float("nan"),
            tpm_proj=float("nan"),
        )

        try:
            result = _proj.project_player(
                conn, g["player_name"],
                opponent=g["opponent"] or "",
                implied_total=league_avg,    # no historical odds -> neutral pace
                league_avg_total=league_avg,
                before_date=gd,
            )
        except LookupError as e:
            row.skipped_reason = f"insufficient_games: {e}"
            n_skipped += 1
            out.append(row)
            continue
        except Exception as e:
            logger.warning("projector crash on %s %s: %s", g["player_name"], gd, e)
            row.skipped_reason = f"crash: {e}"
            n_skipped += 1
            out.append(row)
            continue

        row.minutes_proj = result.minutes
        row.games_used = result.games_used
        row.pts_proj = result.pts
        row.reb_proj = result.reb
        row.ast_proj = result.ast
        row.tpm_proj = result.tpm
        n_projected += 1
        out.append(row)

        if (i + 1) % 500 == 0:
            logger.info("  progress: %d/%d rows", i + 1, len(games))

    logger.info(
        "backtest done: %d rows, %d projected, %d skipped",
        len(out), n_projected, n_skipped,
    )
    return out


# ---------------------------------------------------------------------------
# Aggregation / reporting
# ---------------------------------------------------------------------------

@dataclass
class StatSummary:
    stat: str
    n: int
    mae: float
    rmse: float
    bias: float        # mean(proj - actual); positive = over-projection
    target: float

    @property
    def passes(self) -> bool:
        return self.mae <= self.target


def summarize(rows: list[BacktestRow]) -> dict[str, StatSummary]:
    """Compute MAE / RMSE / bias per stat across projected rows only."""
    projected = [r for r in rows if r.projected]
    out: dict[str, StatSummary] = {}
    for stat in STATS:
        errs = [r.err(stat) for r in projected]
        abs_errs = [abs(e) for e in errs]
        sq_errs = [e * e for e in errs]
        n = len(errs)
        mae = statistics.mean(abs_errs) if n else float("nan")
        rmse = math.sqrt(statistics.mean(sq_errs)) if n else float("nan")
        bias = statistics.mean(errs) if n else float("nan")
        out[stat] = StatSummary(
            stat=stat, n=n, mae=mae, rmse=rmse, bias=bias,
            target=TARGET_MAE.get(stat, float("inf")),
        )
    return out


def per_player_summary(
    rows: list[BacktestRow],
    top_n: int = 30,
) -> list[dict]:
    """Group by player, compute per-stat MAE, return top_n by sample size."""
    by_player: dict[str, list[BacktestRow]] = {}
    for r in rows:
        if not r.projected:
            continue
        by_player.setdefault(r.player_name, []).append(r)

    out = []
    for name, player_rows in by_player.items():
        entry = {
            "player": name,
            "n": len(player_rows),
            "avg_minutes_actual": statistics.mean(
                r.minutes_actual for r in player_rows
            ),
        }
        for stat in STATS:
            entry[f"{stat}_mae"] = statistics.mean(
                abs(r.err(stat)) for r in player_rows
            )
            entry[f"{stat}_bias"] = statistics.mean(
                r.err(stat) for r in player_rows
            )
        out.append(entry)

    out.sort(key=lambda e: e["n"], reverse=True)
    return out[:top_n]


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

def format_summary(summaries: dict[str, StatSummary]) -> str:
    header = f"{'stat':<6} {'n':>6} {'MAE':>8} {'RMSE':>8} {'bias':>8} {'target':>8}   gate"
    sep = "-" * len(header)
    lines = [header, sep]
    for stat in STATS:
        s = summaries[stat]
        gate = "PASS" if s.passes else "FAIL"
        label = _proj.STAT_LABELS.get(stat, stat)
        lines.append(
            f"{label:<6} {s.n:>6} {s.mae:>8.3f} {s.rmse:>8.3f} "
            f"{s.bias:>+8.3f} {s.target:>8.3f}   {gate}"
        )
    return "\n".join(lines)


def format_per_player(entries: list[dict]) -> str:
    header = (
        f"{'player':<28} {'n':>4} {'min':>6}  "
        f"{'PTS mae':>8} {'REB mae':>8} {'AST mae':>8} {'3PM mae':>8}"
    )
    lines = [header, "-" * len(header)]
    for e in entries:
        lines.append(
            f"{e['player'][:28]:<28} {e['n']:>4} {e['avg_minutes_actual']:>6.1f}  "
            f"{e['pts_mae']:>8.2f} {e['reb_mae']:>8.2f} "
            f"{e['ast_mae']:>8.2f} {e['tpm_mae']:>8.2f}"
        )
    return "\n".join(lines)


def write_rows_csv(rows: list[BacktestRow], path: Path | str) -> None:
    """Dump every row to CSV for spreadsheet / ad-hoc inspection."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow([
            "game_date", "player_name", "opponent",
            "minutes_actual", "minutes_proj", "games_used",
            "pts_actual", "pts_proj", "pts_err",
            "reb_actual", "reb_proj", "reb_err",
            "ast_actual", "ast_proj", "ast_err",
            "tpm_actual", "tpm_proj", "tpm_err",
            "skipped_reason",
        ])
        for r in rows:
            writer.writerow([
                r.game_date, r.player_name, r.opponent,
                f"{r.minutes_actual:.2f}",
                "" if math.isnan(r.minutes_proj) else f"{r.minutes_proj:.2f}",
                r.games_used,
                f"{r.pts_actual:.2f}",
                "" if math.isnan(r.pts_proj) else f"{r.pts_proj:.2f}",
                "" if math.isnan(r.pts_proj) else f"{r.err('pts'):+.2f}",
                f"{r.reb_actual:.2f}",
                "" if math.isnan(r.reb_proj) else f"{r.reb_proj:.2f}",
                "" if math.isnan(r.reb_proj) else f"{r.err('reb'):+.2f}",
                f"{r.ast_actual:.2f}",
                "" if math.isnan(r.ast_proj) else f"{r.ast_proj:.2f}",
                "" if math.isnan(r.ast_proj) else f"{r.err('ast'):+.2f}",
                f"{r.tpm_actual:.2f}",
                "" if math.isnan(r.tpm_proj) else f"{r.tpm_proj:.2f}",
                "" if math.isnan(r.tpm_proj) else f"{r.err('tpm'):+.2f}",
                r.skipped_reason,
            ])


# ---------------------------------------------------------------------------
# --slice diagnostic (additive; no gate or projection side-effects)
# ---------------------------------------------------------------------------
#
# Reuses bucket helpers from ``engine/backtest_slice.py`` (the prior
# standalone diagnostic) so future tweaks to position collapse /
# minutes-bucket edges stay in one place.
#
# Differences vs. the standalone ``backtest_slice.py``:
#   * role dimension uses PROJECTED minutes >= 24 as "starter" (the
#     standalone used *actual* >= 20). Per-prompt spec for this PR --
#     diagnosing the projection model needs projection-side buckets.
#   * minutes-bucket dimension drops rows with projected MIN < 15 so
#     the table only covers the spec's go-forward sample. Dropped count
#     is logged.
#   * CSV output is the *aggregated* table
#     ``(dimension, bucket, n, pts_mae, pts_bias, min_bias)`` under
#     ``diagnostics/slice_YYYYMMDD_HHMM.csv`` -- not the per-row dump.

#: Role threshold (per prompt, Apr 22 2026). Differs intentionally from
#: backtest_slice.STARTER_MIN_THRESHOLD which uses actual minutes.
SLICE_STARTER_PROJ_MIN: float = 24.0


def _run_slice_diagnostic(
    rows: list[BacktestRow],
    conn: sqlite3.Connection,
    *,
    start_date: str,
    end_date: str,
) -> Optional[Path]:
    """Emit a 4-dimension bucket diagnostic (role / min_bucket /
    usage_tier / position) for a completed backtest.

    Read-only: does not re-run ``backtest()``, does not mutate the DB,
    does not affect the PASS/FAIL gate. Safe to call any time; the
    caller gates this on ``--slice``.

    Returns the path to the CSV it wrote, or ``None`` if there were no
    projected rows to slice.
    """
    from collections import defaultdict
    from datetime import datetime as _dt

    try:
        from engine import backtest_slice as _bs          # type: ignore
    except ImportError:  # pragma: no cover -- script mode
        import backtest_slice as _bs                      # type: ignore

    projected = [r for r in rows if r.projected]
    if not projected:
        print("[--slice] no projected rows; skipping slice diagnostic.")
        return None

    idx = _bs._load_player_index(conn)
    idx_hit = sum(
        1 for r in projected
        if fold_name(r.player_name) in idx
    )

    slice_rows: list[dict] = []
    for r in projected:
        folded = fold_name(r.player_name)
        meta = idx.get(folded, {"team": "", "position": ""})
        team = meta.get("team") or ""
        pos_raw = meta.get("position") or ""
        pos_collapsed = _bs._collapse_position(pos_raw)
        role = "starter" if r.minutes_proj >= SLICE_STARTER_PROJ_MIN else "bench"
        min_bucket = _bs._bucket_minutes(r.minutes_proj)
        slice_rows.append({
            "game_date":    r.game_date,
            "player_name":  r.player_name,
            "team":         team,
            "position":     pos_collapsed,
            "role":         role,
            "min_bucket":   min_bucket,
            "usage_tier":   "",          # filled below
            "min_actual":   r.minutes_actual,
            "min_proj":     r.minutes_proj,
            "min_err":      r.minutes_proj - r.minutes_actual,
            "pts_err":      r.err("pts"),
            "reb_err":      r.err("reb"),
            "ast_err":      r.err("ast"),
            "tpm_err":      r.err("tpm"),
        })

    # Usage tier: rank within (team, game_date) by projected minutes.
    # No native projected USG% -- this is a fallback proxy.
    usage_fallback = True
    by_tg: dict[tuple[str, str], list[int]] = defaultdict(list)
    for i, row in enumerate(slice_rows):
        by_tg[(row["team"], row["game_date"])].append(i)
    for (team, _gd), indices in by_tg.items():
        indices.sort(key=lambda i: slice_rows[i]["min_proj"], reverse=True)
        for rank, i in enumerate(indices, start=1):
            if not team:
                slice_rows[i]["usage_tier"] = "no_team"
            elif rank <= _bs.USAGE_TIER_TOP:
                slice_rows[i]["usage_tier"] = "top3"
            elif rank <= _bs.USAGE_TIER_MID_MAX:
                slice_rows[i]["usage_tier"] = "4-6"
            else:
                slice_rows[i]["usage_tier"] = "7+"

    # Dimension 2: drop <15 projected-MIN rows from THIS dimension only.
    min_bucket_rows = [r for r in slice_rows if r["min_bucket"] != "<15"]
    dropped_low_min = len(slice_rows) - len(min_bucket_rows)

    unk_count = sum(1 for r in slice_rows if r["position"] == "UNK")

    def _agg(rs: list[dict], col: str) -> list[dict]:
        groups: dict[str, list[dict]] = defaultdict(list)
        for r in rs:
            groups[r[col]].append(r)
        out: list[dict] = []
        for bucket, grp in groups.items():
            n = len(grp)
            out.append({
                "bucket":   bucket,
                "n":        n,
                "pts_mae":  sum(abs(r["pts_err"]) for r in grp) / n,
                "pts_bias": sum(r["pts_err"] for r in grp) / n,
                "min_bias": sum(r["min_err"] for r in grp) / n,
            })
        out.sort(key=lambda e: e["n"], reverse=True)
        return out

    dims: list[tuple[str, list[dict]]] = [
        ("role",       _agg(slice_rows,      "role")),
        ("min_bucket", _agg(min_bucket_rows, "min_bucket")),
        ("usage_tier", _agg(slice_rows,      "usage_tier")),
        ("position",   _agg(slice_rows,      "position")),
    ]

    # ---- stdout ----
    print("=" * 72)
    print(
        f"[--slice] diagnostic -- n={len(slice_rows)} projected rows "
        f"({start_date}..{end_date})"
    )
    print(
        f"  role         : starter = projected MIN >= "
        f"{SLICE_STARTER_PROJ_MIN:.0f} (proxy; no native is_starter flag)"
    )
    print(
        f"  min_bucket   : dropped {dropped_low_min} rows with projected "
        "MIN < 15 from this dimension only"
    )
    usage_tag = "FALLBACK to projected-min proxy" if usage_fallback else "native USG%"
    print(
        f"  usage_tier   : rank by projected minutes within "
        f"(team, game_date) -- {usage_tag}"
    )
    print(
        f"  position     : from player_index.position (native); "
        f"UNK when missing -- UNK count = {unk_count} of {len(slice_rows)} "
        f"(player_index match rate: {idx_hit}/{len(projected)})"
    )
    print()
    for dim_name, table in dims:
        header = (
            f"{'bucket':<12} {'n':>5} {'PTS_MAE':>8} "
            f"{'PTS_bias':>9} {'MIN_bias':>9}"
        )
        print(f"== {dim_name} ==")
        print(header)
        print("-" * len(header))
        if not table:
            print("  (no rows)")
        else:
            for e in table:
                print(
                    f"{str(e['bucket'])[:12]:<12} {e['n']:>5} "
                    f"{e['pts_mae']:>8.3f} {e['pts_bias']:>+9.3f} "
                    f"{e['min_bias']:>+9.3f}"
                )
        print()

    # ---- CSV ----
    diag_dir = Path("diagnostics")
    diag_dir.mkdir(parents=True, exist_ok=True)
    ts = _dt.now().strftime("%Y%m%d_%H%M")
    csv_path = diag_dir / f"slice_{ts}.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            ["dimension", "bucket", "n", "pts_mae", "pts_bias", "min_bias"]
        )
        for dim_name, table in dims:
            for e in table:
                writer.writerow([
                    dim_name, e["bucket"], e["n"],
                    f"{e['pts_mae']:.3f}",
                    f"{e['pts_bias']:+.3f}",
                    f"{e['min_bias']:+.3f}",
                ])
    print(f"[--slice] wrote {csv_path}")
    print()
    return csv_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_date_range(arg: str) -> tuple[str, str]:
    """Parse a ``YYYY-MM-DD:YYYY-MM-DD`` date range.  A single date is
    treated as a one-day window."""
    if ":" in arg:
        start, end = arg.split(":", 1)
    else:
        start = end = arg
    # Validate both sides parse as dates.
    datetime.strptime(start, "%Y-%m-%d")
    datetime.strptime(end, "%Y-%m-%d")
    if start > end:
        raise ValueError(f"start {start!r} is after end {end!r}")
    return start, end


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Walk-forward MAE backtest for the custom NBA projector.",
    )
    p.add_argument("--dates", default=None,
                   help="YYYY-MM-DD[:YYYY-MM-DD]. Defaults to last 14 days "
                        "of game logs in the DB.")
    p.add_argument("--window", default=None,
                   help="Alias for --dates (same format). Convenience flag.")
    p.add_argument("--slice", action="store_true", dest="slice_diag",
                   help="Emit a read-only bucket diagnostic (role / "
                        "min_bucket / usage_tier / position) after the "
                        "gate summary. Also writes "
                        "diagnostics/slice_YYYYMMDD_HHMM.csv. Does not "
                        "change the PASS/FAIL decision.")
    p.add_argument("--min-minutes", type=float, default=DEFAULT_MIN_MINUTES,
                   help=f"Exclude games under N minutes (default "
                        f"{DEFAULT_MIN_MINUTES}).")
    p.add_argument("--player", default=None,
                   help="Restrict backtest to one player (fold-matched).")
    p.add_argument("--limit", type=int, default=None,
                   help="Cap total rows scored (for quick smoke tests).")
    p.add_argument("--per-player", type=int, default=0, metavar="N",
                   help="Also print a top-N per-player MAE breakdown.")
    p.add_argument("--out", default=None,
                   help="Write every row to this CSV for inspection.")
    p.add_argument("--db", default=None,
                   help="Override DB path (defaults to data/projections.db).")
    p.add_argument("-v", "--verbose", action="count", default=0,
                   help="Log verbosity (-v = INFO, -vv = DEBUG).")
    return p


def _default_date_range(conn: sqlite3.Connection) -> tuple[str, str]:
    """Last 14 game-dates in the DB, so a fresh user gets useful output
    without knowing the data window."""
    row = conn.execute(
        "SELECT MAX(game_date) FROM player_game_logs WHERE sport = 'nba'"
    ).fetchone()
    end = row[0] if row else None
    if not end:
        raise SystemExit("DB has no NBA game logs; run projections_db --pull-nba first")
    start_dt = datetime.strptime(end, "%Y-%m-%d") - timedelta(days=14)
    return start_dt.strftime("%Y-%m-%d"), end


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

    # --window is an alias for --dates. Accept either; reject both.
    if args.window and args.dates:
        raise SystemExit("pick one of --window / --dates, not both")
    date_arg = args.window or args.dates

    conn = _pdb.get_connection(args.db)
    try:
        if date_arg:
            start_date, end_date = _parse_date_range(date_arg)
        else:
            start_date, end_date = _default_date_range(conn)
            logger.info("no --dates/--window given; defaulting to %s..%s",
                        start_date, end_date)

        rows = backtest(
            conn,
            start_date=start_date, end_date=end_date,
            min_minutes=args.min_minutes,
            player_filter=args.player,
            limit=args.limit,
        )
    finally:
        conn.close()

    summaries = summarize(rows)
    n_total = len(rows)
    n_projected = sum(1 for r in rows if r.projected)
    n_skipped = n_total - n_projected
    coverage = (100.0 * n_projected / n_total) if n_total else 0.0

    print()
    print(f"Window      : {start_date} .. {end_date}")
    print(f"min_minutes : {args.min_minutes:.1f}")
    if args.player:
        print(f"player      : {args.player}")
    print(f"Rows        : {n_total}  (projected={n_projected}, "
          f"skipped={n_skipped}, coverage={coverage:.1f}%)")
    print()
    print(format_summary(summaries))
    print()

    if args.slice_diag:
        # Separate conn -- the main one is already closed above. Slice is
        # read-only, so open/close is cheap and doesn't affect the gate.
        slice_conn = _pdb.get_connection(args.db)
        try:
            _run_slice_diagnostic(
                rows, slice_conn,
                start_date=start_date, end_date=end_date,
            )
        finally:
            slice_conn.close()

    if args.per_player > 0:
        entries = per_player_summary(rows, top_n=args.per_player)
        print(format_per_player(entries))
        print()

    if args.out:
        write_rows_csv(rows, args.out)
        print(f"wrote {n_total} rows to {args.out}")
        print()

    failed = [s.stat for s in summaries.values() if not s.passes]
    if failed:
        print(f"RESULT: FAIL -- stats over target: {', '.join(failed)}")
        return 1
    print("RESULT: PASS -- all MAE targets cleared")
    return 0


if __name__ == "__main__":
    sys.exit(main())
