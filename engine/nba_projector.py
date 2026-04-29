"""NBA stat projector -- Step 2 of the custom projection engine.

Consumes historical game logs loaded into ``projections.db`` by
``projections_db.py`` and produces projected PTS, REB, AST, 3PM for a
player against a given opponent on a given date.

Core formula (matches the spec in
``memory/projects/custom-projection-engine.md``):

    projected_stat = per_minute_rate * projected_minutes * matchup_factor * pace_factor

- ``per_minute_rate``  -- EWMA (span=10) of per-minute production, most
  recent game first. Rate, not raw stat, so minutes changes cleanly
  decouple from role changes.
- ``projected_minutes`` -- EWMA baseline of minutes played, then adjusted
  for injury status, back-to-backs, and blowout-spread games.
- ``matchup_factor``    -- opponent's allowed rate over the lookback
  window divided by league average for the same window, clipped to
  ``[0.80, 1.20]`` so one ugly outlier can't drive the projection.
- ``pace_factor``       -- ``implied_total / league_avg_total``. The
  caller supplies ``implied_total`` (already in the Odds-API path of
  ``run_picks.py``); the projector auto-computes the league average if
  the caller doesn't.

This module depends only on the DB, ``name_utils``, and ``paths``. It
never writes to the DB and never touches ``run_picks.py`` -- the whole
point of the custom projector is that the existing engine stays
unchanged, and ``csv_writer.py`` (step 4) consumes the dict this module
returns.

Conventions reused from the rest of the engine:
- ``fold_name`` for all cross-source name matching (diacritics / casing)
- ``paths.DATA_DIR`` / ``projections_db.DB_PATH`` for default DB location
- lowercase sport tokens (``'nba'`` / ``'nhl'`` / ``'mlb'``) in storage

CLI usage (smoke tests -- not the production path):

    python engine/nba_projector.py "Nikola Jokic" --opp MIN --total 228.5
    python engine/nba_projector.py --unit-test
    python engine/nba_projector.py --unit-test --db-path /tmp/projections_test.db
"""
from __future__ import annotations

import argparse
import logging
import sqlite3
import sys
from contextlib import closing
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# Heavyweight imports are kept lazy where possible so ``--help`` still
# runs on a bare Python -- but pandas is load-bearing (EWMA), so we
# fail fast with a clear message if it's missing.
try:
    import pandas as pd
except ImportError:  # pragma: no cover -- install guidance only
    print(
        "nba_projector requires pandas. Install with:\n"
        "  pip install pandas --break-system-packages",
        file=sys.stderr,
    )
    raise

from name_utils import fold_name
import projections_db as _pdb

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tunables. Change at call-time via kwargs, not by editing these -- the
# unit test and backtest harness both rely on these defaults being stable.
# ---------------------------------------------------------------------------

DEFAULT_EWMA_SPAN: int = 10
MATCHUP_CLIP: tuple[float, float] = (0.80, 1.20)
BLOWOUT_SPREAD_THRESHOLD: float = 12.0
BLOWOUT_MIN_REDUCTION: float = 3.0
B2B_MINUTES_MULT: float = 0.92
INJURY_Q_MINUTES_MULT: float = 0.55
DEFAULT_MATCHUP_LOOKBACK_DAYS: int = 60
DEFAULT_LEAGUE_TOTAL_LOOKBACK_DAYS: int = 30
MIN_GAMES_FOR_PROJECTION: int = 3   # under this, we refuse to project

# ---------------------------------------------------------------------------
# Minutes-model tunables (Apr 22 2026). Backtest slice diagnostics showed
# healthy-mean was variance-shrinking: high-role players under-projected by
# ~2.1 min, bench over-projected by ~5.3. Blend of L5-median + season mean
# preserves tail variance; L10-median floor/ceiling prevents over-correction
# at the edges. Values specified by Jono -- do not retune without a slice
# diff showing new values beat these on bucket bias.
# ---------------------------------------------------------------------------
L5_WEIGHT: float = 0.6
SEASON_WEIGHT: float = 0.4
MIN_L5_GAMES_FOR_BLEND: int = 5               # below this, fall back to season mean only
L10_HIGH_MEDIAN_FLOOR_TRIGGER: float = 30.0   # l10 median >= this triggers the floor
L10_HIGH_MEDIAN_FLOOR_VALUE:   float = 28.0   # min proj floor when high-median triggered
L10_LOW_MEDIAN_CEILING_TRIGGER: float = 12.0  # l10 median <= this triggers the ceiling
L10_LOW_MEDIAN_CEILING_VALUE:   float = 18.0  # max proj ceiling when low-median triggered

# Stat tokens that the NBA projector outputs. These match the column
# names in ``player_game_logs`` AND the 4 stats that ``parse_csv`` in
# ``run_picks.py`` expects on the NBA side. Order matters for CLI output
# formatting; do not sort.
STATS_PROJECTED: tuple[str, ...] = ("pts", "reb", "ast", "tpm")

# Display labels used by the CLI -- DB columns are lowercase, but the
# SaberSim CSV uses TitleCase/abbrev (step 4 wires those up).
STAT_LABELS: dict[str, str] = {
    "pts": "PTS",
    "reb": "REB",
    "ast": "AST",
    "tpm": "3PM",
}


# ---------------------------------------------------------------------------
# Data access
# ---------------------------------------------------------------------------

def _open(db_path: Path | str | None) -> sqlite3.Connection:
    """Return a row-factory-enabled read-only-ish connection."""
    conn = _pdb.get_connection(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def load_player_game_logs(
    conn: sqlite3.Connection,
    player_name: str,
    *,
    before_date: Optional[str] = None,
    limit: int = 50,
) -> pd.DataFrame:
    """Return the player's game logs ordered oldest -> newest (so EWMA
    weights the most recent game highest when invoked plain).

    ``player_name`` is matched via ``fold_name`` so "Nikola Jokic" and
    "Nikola Jokic" both resolve to the DB row "Nikola Jokic".

    ``before_date`` (YYYY-MM-DD) excludes games on or after that date --
    used by the backtest harness so a projection for game N doesn't
    leak game-N data.
    """
    folded = fold_name(player_name)
    if not folded:
        return pd.DataFrame()

    # We can't fold in SQL, so pull a candidate set by first-name
    # prefix to keep the scan cheap, then filter in Python. "jokic"
    # candidates: anyone whose folded name starts with the first two
    # chars of the folded target. For short folded names we fall back
    # to a full scan of the sport.
    first_chars = folded[:2] if len(folded) >= 2 else folded
    like_pat = f"{first_chars}%"
    sql = (
        "SELECT player_id, player_name, game_date, opponent, home_away, "
        "       minutes, pts, reb, ast, tpm "
        "FROM player_game_logs "
        "WHERE sport = 'nba' "
        "  AND minutes IS NOT NULL AND minutes > 0 "
        "  AND LOWER(SUBSTR(player_name, 1, 2)) LIKE ? "
    )
    params: list = [like_pat]
    if before_date:
        sql += "  AND game_date < ? "
        params.append(before_date)
    sql += "ORDER BY game_date ASC"

    rows = conn.execute(sql, params).fetchall()
    if not rows:
        # Fallback: candidate-prefix filter missed (e.g., diacritic in
        # position 1). Rare; do a full-season scan.
        sql2 = (
            "SELECT player_id, player_name, game_date, opponent, home_away, "
            "       minutes, pts, reb, ast, tpm "
            "FROM player_game_logs "
            "WHERE sport = 'nba' AND minutes IS NOT NULL AND minutes > 0 "
        )
        p2: list = []
        if before_date:
            sql2 += "AND game_date < ? "
            p2.append(before_date)
        sql2 += "ORDER BY game_date ASC"
        rows = conn.execute(sql2, p2).fetchall()

    df = pd.DataFrame([dict(r) for r in rows])
    if df.empty:
        return df

    df = df[df["player_name"].map(fold_name) == folded].copy()
    if df.empty:
        return df

    # Keep only the most recent ``limit`` games (keeps EWMA short).
    if limit and len(df) > limit:
        df = df.iloc[-limit:].reset_index(drop=True)
    return df


def list_known_players(conn: sqlite3.Connection, *, limit: int = 1000) -> pd.DataFrame:
    """Return distinct NBA player names in the DB, ordered alphabetically.
    Used by the CLI for "did you mean?" style error messages."""
    rows = conn.execute(
        "SELECT DISTINCT player_name FROM player_game_logs "
        "WHERE sport = 'nba' ORDER BY player_name LIMIT ?",
        (limit,),
    ).fetchall()
    return pd.DataFrame([dict(r) for r in rows])


# ---------------------------------------------------------------------------
# Rate / minutes calculation
# ---------------------------------------------------------------------------

def _ewma_last(values: pd.Series, span: int) -> float:
    """Return the final EWMA value of ``values`` with the given span.
    ``nan``-safe -- drops NaNs before computing. Returns 0.0 for empty."""
    clean = pd.to_numeric(values, errors="coerce").dropna()
    if clean.empty:
        return 0.0
    # ewm with adjust=True (default) is the formula most references use:
    # y_t = sum(w_i * x_i) / sum(w_i), with w_i = (1 - alpha)^(t-i).
    return float(clean.ewm(span=span, adjust=True).mean().iloc[-1])


def compute_per_minute_rates(
    games: pd.DataFrame,
    *,
    span: int = DEFAULT_EWMA_SPAN,
) -> dict[str, float]:
    """EWMA of per-minute rates for each projected stat.

    We divide each game's raw stat by minutes-played for THAT game and
    then EWMA the series. This isolates rate from role shifts -- a
    7th-man blowup followed by a DNP doesn't distort the rate, just the
    minutes projection.
    """
    if games.empty:
        return {s: 0.0 for s in STATS_PROJECTED}

    minutes = pd.to_numeric(games["minutes"], errors="coerce")
    out: dict[str, float] = {}
    for stat in STATS_PROJECTED:
        raw = pd.to_numeric(games[stat], errors="coerce")
        # per-minute rate, guarded against div-by-zero (minutes>0 already
        # filtered in SQL, but defensive)
        rate = raw / minutes.where(minutes > 0)
        out[stat] = _ewma_last(rate, span=span)
    return out


def _healthy_mean_minutes_legacy(
    games: pd.DataFrame,
    *,
    span: int = DEFAULT_EWMA_SPAN,
    healthy_min_threshold: float = 15.0,
) -> float:
    """Original healthy-mean minutes baseline (pre Apr-22-2026).

    Preserved byte-for-byte so the blended baseline below can still
    compute its season component, and so we can A/B against the legacy
    model from the backtest harness if anything regresses.

    Implementation notes (unchanged from the original):
      1. We originally used EWMA, but the backtest (Step 5) showed a
         systematic ~2.8-min under-projection driven by blowout-yanked /
         foul-trouble / load-managed games pulling the weighted mean
         down.
      2. We then tried median of the tail window -- that swung the bias
         +4.7 the other direction (median of recent usage runs *hot*
         because the distribution is left-skewed with a few low-minute
         outliers).
      3. The target distribution the projector predicts is "healthy
         night, player plays >= 15 min". Matching the training filter
         to the prediction target (unweighted mean over healthy games)
         eliminates the selection bias in both directions.

    If no recent game clears ``healthy_min_threshold`` (e.g., a player
    just returned from injury), we fall back to the unfiltered mean of
    the tail window so we never return 0.0 for an active player.
    """
    if games.empty:
        return 0.0
    minutes = pd.to_numeric(games["minutes"], errors="coerce").dropna()
    if minutes.empty:
        return 0.0
    tail = minutes.tail(span)
    healthy = tail[tail >= healthy_min_threshold]
    if not healthy.empty:
        return float(healthy.mean())
    # Fallback: no healthy games in window -- use unfiltered tail mean
    # rather than 0.0, so we still emit a projection. Caller can use
    # ``games_used`` + notes to decide whether to trust it.
    return float(tail.mean())


def compute_minutes_baseline(
    games: pd.DataFrame,
    *,
    span: int = DEFAULT_EWMA_SPAN,
    healthy_min_threshold: float = 15.0,
) -> float:
    """Projected minutes = blend of L5-median healthy + season healthy mean.

    Slice diagnostics (Apr 22 2026, n=1927) showed healthy-mean was
    variance-shrinking: starter bucket under-projected by ~2.1 MIN,
    bench bucket over-projected by ~5.3 MIN, monotonically compressed
    across the projected-minutes buckets (<15 = -17.8, 35+ = +2.5).
    The fix preserves tail variance by blending the L5 median of healthy
    games (captures current role) with the season healthy mean (captures
    the player's established ceiling). Both components are computed on
    the same ``minutes >= healthy_min_threshold`` population so the blend
    is internally consistent -- see the [H1] comment inline below.
    L10-median floor/ceiling are edge guardrails -- a player averaging
    32+ in their last 10 healthy games shouldn't be dragged below 28,
    and a player averaging <=12 shouldn't be pushed above 18 by a
    single 40-min outlier inflating the season mean.

    Falls back to season-only when there aren't enough healthy games to
    form a stable L5 median (``MIN_L5_GAMES_FOR_BLEND``). Signature is
    preserved so no call site needs to change.
    """
    season_mean = _healthy_mean_minutes_legacy(
        games, span=span, healthy_min_threshold=healthy_min_threshold,
    )
    if games.empty:
        return season_mean

    minutes = pd.to_numeric(games["minutes"], errors="coerce").dropna()
    # [H1 -- phase2-root-cause, 2026-04-22] The blend target is "healthy
    # night, player plays >= healthy_min_threshold" -- same contract the
    # season_mean component is computed on. The L5/L10 medians must use
    # the same population for internal consistency; otherwise the blend
    # mixes two statistics estimating different quantities. Games below
    # healthy_min_threshold (foul-outs, injury-in-game exits, ejections,
    # blowout-yanked starter minutes, minutes-restriction returns) are
    # contamination for the current-role signal this component is meant
    # to capture. Previously only `minutes > 0` was enforced here while
    # season_mean applied `>= healthy_min_threshold`, so the 0.6-weighted
    # recent component pulled the blend off-target. This is a bug fix
    # (population-consistency), not a tuning change.
    healthy = minutes[minutes >= healthy_min_threshold]
    if len(healthy) < MIN_L5_GAMES_FOR_BLEND:
        logger.debug(
            "minutes baseline fallback (only %d healthy games >= %.1f min) -> "
            "season mean %.2f",
            len(healthy), healthy_min_threshold, season_mean,
        )
        return float(season_mean)

    l5_median = float(healthy.tail(5).median())
    minutes_proj = L5_WEIGHT * l5_median + SEASON_WEIGHT * season_mean

    l10 = healthy.tail(10)
    if len(l10) >= 5:
        l10_median = float(l10.median())
        if l10_median >= L10_HIGH_MEDIAN_FLOOR_TRIGGER:
            if minutes_proj < L10_HIGH_MEDIAN_FLOOR_VALUE:
                logger.debug(
                    "L10 high-median floor triggered: l10_median=%.1f, proj %.2f -> %.2f",
                    l10_median, minutes_proj, L10_HIGH_MEDIAN_FLOOR_VALUE,
                )
                minutes_proj = L10_HIGH_MEDIAN_FLOOR_VALUE
        elif l10_median <= L10_LOW_MEDIAN_CEILING_TRIGGER:
            if minutes_proj > L10_LOW_MEDIAN_CEILING_VALUE:
                logger.debug(
                    "L10 low-median ceiling triggered: l10_median=%.1f, proj %.2f -> %.2f",
                    l10_median, minutes_proj, L10_LOW_MEDIAN_CEILING_VALUE,
                )
                minutes_proj = L10_LOW_MEDIAN_CEILING_VALUE

    return float(minutes_proj)


def adjust_minutes(
    baseline: float,
    *,
    is_b2b: bool = False,
    blowout_spread: Optional[float] = None,
    injury_status: str = "",
) -> tuple[float, list[str]]:
    """Apply spec-defined adjustments to the minutes baseline.

    Returns ``(projected_minutes, notes)`` so the caller can surface
    *why* the minutes moved -- useful in the CLI output and critical
    when debugging a bad projection during the go-live parallel run.

    Spec (see custom-projection-engine.md):
      injury OUT          -> 0 min
      injury Questionable -> 0.55 * baseline
      B2B                 -> * 0.92
      blowout (spread>12) -> -3 min
    """
    notes: list[str] = []
    status = (injury_status or "").strip().lower()

    # Injury gate first -- OUT beats everything else.
    if status in ("out", "o"):
        notes.append("injury=OUT -> 0 min")
        return 0.0, notes

    minutes = max(0.0, float(baseline))

    if status in ("q", "questionable"):
        minutes *= INJURY_Q_MINUTES_MULT
        notes.append(f"injury=Q -> x{INJURY_Q_MINUTES_MULT}")

    if is_b2b:
        minutes *= B2B_MINUTES_MULT
        notes.append(f"B2B -> x{B2B_MINUTES_MULT}")

    if blowout_spread is not None and abs(blowout_spread) > BLOWOUT_SPREAD_THRESHOLD:
        minutes = max(0.0, minutes - BLOWOUT_MIN_REDUCTION)
        notes.append(f"blowout spread={blowout_spread} -> -{BLOWOUT_MIN_REDUCTION} min")

    return minutes, notes


# ---------------------------------------------------------------------------
# Matchup factor
# ---------------------------------------------------------------------------

def _date_floor(before_date: Optional[str], lookback_days: int) -> str:
    """Return ``before_date - lookback_days`` as YYYY-MM-DD. If
    ``before_date`` is None, fall back to the most recent game_date in
    the DB minus lookback_days (caller responsibility).

    SQLite handles the arithmetic via ``date(..., '-N days')`` so we
    build that expression as a literal string; the caller interpolates
    via parameters (``before_date`` is user-influenced).
    """
    # We actually run this arithmetic in SQL via ``date(?, '-N days')``,
    # so this helper just returns ``before_date`` unchanged. It exists
    # to document the intent. (If you port to a different DB, this is
    # where the date math would move.)
    return before_date or ""


def _opponent_allowed_per_minute(
    conn: sqlite3.Connection,
    opponent: str,
    stat: str,
    *,
    lookback_days: int,
    before_date: Optional[str],
) -> Optional[float]:
    """Aggregate ``sum(stat) / sum(minutes)`` across all rows where the
    given opponent was on defense (i.e. ``player_game_logs.opponent = ?``)
    within the lookback window. Returns None if the opponent has no
    rows in the window."""
    sql = (
        f"SELECT SUM({stat}) AS s, SUM(minutes) AS m "  # noqa: S608 -- stat is whitelisted
        "FROM player_game_logs "
        "WHERE sport = 'nba' AND opponent = ? "
        "  AND minutes IS NOT NULL AND minutes > 0 "
    )
    params: list = [opponent]
    if before_date:
        sql += "AND game_date < ? AND game_date >= date(?, ?) "
        params += [before_date, before_date, f"-{int(lookback_days)} days"]
    else:
        sql += (
            "AND game_date >= date("
            "  (SELECT MAX(game_date) FROM player_game_logs WHERE sport='nba'),"
            "  ?)"
        )
        params.append(f"-{int(lookback_days)} days")
    row = conn.execute(sql, params).fetchone()
    if row is None or row["m"] in (None, 0):
        return None
    return float(row["s"]) / float(row["m"])


def _league_avg_per_minute(
    conn: sqlite3.Connection,
    stat: str,
    *,
    lookback_days: int,
    before_date: Optional[str],
) -> Optional[float]:
    sql = (
        f"SELECT SUM({stat}) AS s, SUM(minutes) AS m "  # noqa: S608
        "FROM player_game_logs "
        "WHERE sport = 'nba' AND minutes IS NOT NULL AND minutes > 0 "
    )
    params: list = []
    if before_date:
        sql += "AND game_date < ? AND game_date >= date(?, ?) "
        params += [before_date, before_date, f"-{int(lookback_days)} days"]
    else:
        sql += (
            "AND game_date >= date("
            "  (SELECT MAX(game_date) FROM player_game_logs WHERE sport='nba'),"
            "  ?)"
        )
        params.append(f"-{int(lookback_days)} days")
    row = conn.execute(sql, params).fetchone()
    if row is None or row["m"] in (None, 0):
        return None
    return float(row["s"]) / float(row["m"])


def compute_matchup_factor(
    conn: sqlite3.Connection,
    opponent: str,
    stat: str,
    *,
    lookback_days: int = DEFAULT_MATCHUP_LOOKBACK_DAYS,
    before_date: Optional[str] = None,
) -> tuple[float, dict]:
    """Return ``(factor, diagnostics)``. ``factor`` is clipped to
    ``MATCHUP_CLIP`` (default ``[0.80, 1.20]``). ``diagnostics`` has
    ``opp_rate``, ``league_rate``, and ``raw`` (unclipped factor).

    Returns ``(1.0, {...})`` when either side of the ratio is unknown
    (e.g. we don't have opponent data yet). 1.0 is the neutral value
    that leaves the projection unchanged.

    TODO (custom-projection-engine): compute matchup factor PER
    POSITION, not team-wide. Requires ``player_index.position`` to be
    populated -- currently empty for all rows (confirmed via
    ``engine/backtest_slice.py`` Apr 22 2026: all 1927 projected rows
    bucketed into position ``UNK``). Backfill via
    ``nba_api.stats.endpoints.commonplayerinfo.CommonPlayerInfo`` in
    ``projections_db.py`` (separate PR), then thread ``position``
    through as a required argument here and join team-defense by
    ``(team, position, stat)`` instead of aggregating across all
    opponents. DO NOT backfill in this PR -- minutes-model fix first.
    """
    if stat not in STATS_PROJECTED:
        raise ValueError(f"unknown stat {stat!r}; must be one of {STATS_PROJECTED}")

    opp = _opponent_allowed_per_minute(
        conn, opponent, stat, lookback_days=lookback_days, before_date=before_date
    )
    lg = _league_avg_per_minute(
        conn, stat, lookback_days=lookback_days, before_date=before_date
    )
    diag = {"opp_rate": opp, "league_rate": lg, "raw": None}
    if opp is None or lg is None or lg == 0:
        return 1.0, diag

    raw = opp / lg
    diag["raw"] = raw
    lo, hi = MATCHUP_CLIP
    return max(lo, min(hi, raw)), diag


# ---------------------------------------------------------------------------
# Pace factor
# ---------------------------------------------------------------------------

def league_avg_game_total(
    conn: sqlite3.Connection,
    *,
    lookback_days: int = DEFAULT_LEAGUE_TOTAL_LOOKBACK_DAYS,
    before_date: Optional[str] = None,
) -> float:
    """Approximate league-avg single-game total (both teams combined)
    by aggregating ``pts`` across the lookback window and dividing by
    the number of (team, game_date) pairs / 2. One team's box score
    contributes 5 players * their pts -> roughly team points; two
    teams per game -> divide the pair count by 2.

    Returns a reasonable fallback (225.0) if the DB has no data. The
    production path of ``csv_writer.py`` will pass the league avg
    total explicitly from a rolling Odds-API feed; this helper exists
    for the CLI and the unit test so the projector is self-contained.
    """
    sql = (
        "SELECT SUM(pts) AS total_pts, "
        "       COUNT(DISTINCT game_date || ':' || SUBSTR(player_id,1,0) || opponent) AS team_games "
        "FROM player_game_logs "
        "WHERE sport = 'nba' AND minutes > 0 "
    )
    params: list = []
    if before_date:
        sql += "AND game_date < ? AND game_date >= date(?, ?)"
        params += [before_date, before_date, f"-{int(lookback_days)} days"]
    else:
        sql += (
            "AND game_date >= date("
            " (SELECT MAX(game_date) FROM player_game_logs WHERE sport='nba'), ?)"
        )
        params.append(f"-{int(lookback_days)} days")
    row = conn.execute(sql, params).fetchone()
    if row is None or row["total_pts"] in (None, 0) or row["team_games"] in (None, 0):
        return 225.0

    # team_games counts (date, opponent) pairs -- i.e. one per team per
    # game. Average combined total = total_pts / (team_games / 2) =
    # 2 * total_pts / team_games.
    return 2.0 * float(row["total_pts"]) / float(row["team_games"])


def compute_pace_factor(implied_total: float, *, league_avg_total: float) -> float:
    """pace_factor = implied_total / league_avg_total. No clipping --
    market-implied totals are already noise-filtered by the book's risk
    desk. If the market says a 260-total game, trust it."""
    if league_avg_total is None or league_avg_total <= 0:
        return 1.0
    return float(implied_total) / float(league_avg_total)


# ---------------------------------------------------------------------------
# Top-level projection
# ---------------------------------------------------------------------------

@dataclass
class ProjectionResult:
    player_name: str
    games_used: int
    minutes: float
    pts: float
    reb: float
    ast: float
    tpm: float
    matchup_factors: dict = field(default_factory=dict)
    pace_factor: float = 1.0
    notes: list = field(default_factory=list)

    def as_dict(self) -> dict:
        d = {
            "player": self.player_name,
            "games_used": self.games_used,
            "minutes": round(self.minutes, 2),
            "pts": round(self.pts, 2),
            "reb": round(self.reb, 2),
            "ast": round(self.ast, 2),
            "tpm": round(self.tpm, 2),
            "pace_factor": round(self.pace_factor, 3),
            "matchup_factors": {k: round(v, 3) for k, v in self.matchup_factors.items()},
            "notes": list(self.notes),
        }
        return d


def project_player(
    conn: sqlite3.Connection,
    player_name: str,
    *,
    opponent: str,
    implied_total: float,
    league_avg_total: Optional[float] = None,
    before_date: Optional[str] = None,
    is_b2b: bool = False,
    blowout_spread: Optional[float] = None,
    injury_status: str = "",
    ewma_span: int = DEFAULT_EWMA_SPAN,
    matchup_lookback_days: int = DEFAULT_MATCHUP_LOOKBACK_DAYS,
    games_limit: int = 50,
) -> ProjectionResult:
    """Project PTS / REB / AST / 3PM for ``player_name`` vs ``opponent``.

    Returns a ``ProjectionResult``. Raises ``LookupError`` if the player
    has fewer than ``MIN_GAMES_FOR_PROJECTION`` eligible games -- the
    caller should fall back to SaberSim for unmodelable players during
    the parallel-run window.
    """
    games = load_player_game_logs(
        conn, player_name, before_date=before_date, limit=games_limit
    )
    if len(games) < MIN_GAMES_FOR_PROJECTION:
        raise LookupError(
            f"only {len(games)} eligible games for {player_name!r} "
            f"(need >= {MIN_GAMES_FOR_PROJECTION})"
        )

    # Canonicalize to the name as stored in the DB (preserves diacritics).
    canonical = games["player_name"].iloc[-1]

    # 1. rates
    per_min = compute_per_minute_rates(games, span=ewma_span)
    # 2. minutes
    min_base = compute_minutes_baseline(games, span=ewma_span)
    proj_min, notes = adjust_minutes(
        min_base,
        is_b2b=is_b2b,
        blowout_spread=blowout_spread,
        injury_status=injury_status,
    )
    # 3. matchup (one per stat)
    matchup: dict[str, float] = {}
    for stat in STATS_PROJECTED:
        f, _diag = compute_matchup_factor(
            conn, opponent, stat,
            lookback_days=matchup_lookback_days,
            before_date=before_date,
        )
        matchup[stat] = f

    # 4. pace
    if league_avg_total is None:
        league_avg_total = league_avg_game_total(conn, before_date=before_date)
    pace = compute_pace_factor(implied_total, league_avg_total=league_avg_total)

    projected = {
        stat: per_min[stat] * proj_min * matchup[stat] * pace
        for stat in STATS_PROJECTED
    }

    return ProjectionResult(
        player_name=canonical,
        games_used=len(games),
        minutes=proj_min,
        pts=projected["pts"],
        reb=projected["reb"],
        ast=projected["ast"],
        tpm=projected["tpm"],
        matchup_factors=matchup,
        pace_factor=pace,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# CLI -- smoke tests only; the production path is csv_writer.py (step 4)
# ---------------------------------------------------------------------------

def _format_result(result: ProjectionResult, *, opponent: str, total: float) -> str:
    lines = [
        f"{result.player_name} vs {opponent}  (total={total})",
        f"  games_used     : {result.games_used}",
        f"  minutes        : {result.minutes:.2f}",
        f"  pace_factor    : {result.pace_factor:.3f}",
        "  matchup_factors: "
        + ", ".join(f"{STAT_LABELS[s]}={result.matchup_factors[s]:.3f}" for s in STATS_PROJECTED),
        "  projected      : "
        + ", ".join(f"{STAT_LABELS[s]}={getattr(result, s):.1f}" for s in STATS_PROJECTED),
    ]
    if result.notes:
        lines.append("  notes          : " + "; ".join(result.notes))
    return "\n".join(lines)


# Players and rough sanity ranges for the built-in unit test. Values
# are season-to-date averages as of 2025-26 at the time this module
# was written -- the test just checks the projection is in a
# plausible band, not an exact match, so these bands are wide.
UNIT_TEST_PLAYERS = (
    # (name, opp, implied_total, (pts_lo, pts_hi), (reb_lo, reb_hi), (ast_lo, ast_hi))
    ("Nikola Jokic", "MIN", 228.5, (20, 36), (8, 17), (7, 14)),
    ("Luka Doncic",  "LAL", 232.0, (22, 42), (5, 13), (5, 13)),
    ("Shai Gilgeous-Alexander", "DEN", 230.0, (20, 40), (3, 9), (3, 10)),
)


def _unit_test(conn: sqlite3.Connection) -> int:
    """Run the built-in sanity projection on 3 known players. Returns
    the number of failures."""
    failures = 0
    for name, opp, total, pts_band, reb_band, ast_band in UNIT_TEST_PLAYERS:
        try:
            r = project_player(
                conn, name, opponent=opp, implied_total=total,
            )
        except LookupError as e:
            print(f"[SKIP] {name}: {e}")
            continue
        print(_format_result(r, opponent=opp, total=total))
        bands = {"pts": pts_band, "reb": reb_band, "ast": ast_band}
        for stat, (lo, hi) in bands.items():
            v = getattr(r, stat)
            ok = lo <= v <= hi
            mark = "OK" if ok else "FAIL"
            print(f"    [{mark}] {STAT_LABELS[stat]} {v:.1f} in [{lo}, {hi}]")
            if not ok:
                failures += 1
        print()
    return failures


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="NBA stat projector (step 2 of custom projection engine).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("player", nargs="?", help="Player name, e.g. 'Nikola Jokic'")
    p.add_argument("--opp", help="3-letter opponent team code, e.g. MIN")
    p.add_argument("--total", type=float, help="Game implied total (both teams combined)")
    p.add_argument("--league-avg-total", type=float, default=None,
                   help="Override league-avg game total (else auto-computed).")
    p.add_argument("--before-date", default=None,
                   help="Exclude games on or after this date (YYYY-MM-DD).")
    p.add_argument("--b2b", action="store_true", help="Player is on a back-to-back.")
    p.add_argument("--blowout-spread", type=float, default=None,
                   help="Spread; if |spread| > threshold, applies blowout minutes cut.")
    p.add_argument("--injury", default="", help="OUT / Q / blank.")
    p.add_argument("--ewma-span", type=int, default=DEFAULT_EWMA_SPAN)
    p.add_argument("--matchup-lookback-days", type=int,
                   default=DEFAULT_MATCHUP_LOOKBACK_DAYS)
    p.add_argument("--db-path", default=None, help="Override projections.db path.")
    p.add_argument("--unit-test", action="store_true",
                   help="Run the built-in 3-player sanity test instead.")
    p.add_argument("-v", "--verbose", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    with closing(_open(args.db_path)) as conn:
        if args.unit_test:
            fail = _unit_test(conn)
            if fail:
                print(f"UNIT TEST FAILED: {fail} band(s) out of range")
                return 1
            print("UNIT TEST OK")
            return 0

        if not args.player or not args.opp or args.total is None:
            print(
                "missing required args. Usage:\n"
                "  python engine/nba_projector.py 'Nikola Jokic' --opp MIN --total 228.5\n"
                "  python engine/nba_projector.py --unit-test",
                file=sys.stderr,
            )
            return 2

        try:
            r = project_player(
                conn, args.player,
                opponent=args.opp,
                implied_total=args.total,
                league_avg_total=args.league_avg_total,
                before_date=args.before_date,
                is_b2b=args.b2b,
                blowout_spread=args.blowout_spread,
                injury_status=args.injury,
                ewma_span=args.ewma_span,
                matchup_lookback_days=args.matchup_lookback_days,
            )
        except LookupError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return 1

        print(_format_result(r, opponent=args.opp, total=args.total))
        return 0


if __name__ == "__main__":
    sys.exit(main())
