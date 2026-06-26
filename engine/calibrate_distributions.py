"""
calibrate_distributions.py — Multi-market distribution calibration.

Computes empirical distribution parameters for each game-line and prop market
from historical game logs in projections.db.  Results are printed to stdout;
engineer manually updates the corresponding constants in run_picks.py.

Usage:
  python engine/calibrate_distributions.py --mode mlb-team-runs
  python engine/calibrate_distributions.py --mode nhl-game-sigmas
  python engine/calibrate_distributions.py --mode wnba-game-total
  python engine/calibrate_distributions.py --mode mlb-batter-zinb
  python engine/calibrate_distributions.py --mode wnba-3pm
  python engine/calibrate_distributions.py --mode wnba-sigma
  python engine/calibrate_distributions.py --mode all

Modes:
  mlb-team-runs   NB dispersion r for MLB team run-scoring (-> MLB_TEAM_RUN_R in run_picks.py)
  nhl-game-sigmas Normal sigma for NHL game total / spread / team / ML (-> GAME_SIGMA["NHL"])
  wnba-game-total Normal sigma for WNBA combined score and team score (-> GAME_SIGMA["WNBA"])
  mlb-batter-zinb NB/ZINB params for batter HITS/BB/RUNS (-> NB_R["HITS"], ZINB_PARAMS)
  wnba-3pm        NB dispersion r for WNBA 3PM (-> NB_R_WNBA["3PM"])
  wnba-sigma      Within-player CV mults for SIGMA_WNBA, min>=20 (-> SIGMA_WNBA in calibrated.py)
  all             Run all modes in order
"""

from __future__ import annotations

import argparse
import math
import os
import sqlite3
import statistics
from collections import defaultdict
from pathlib import Path

try:  # advisory display only — read the live deployed sigmas, never a stale literal
    from calibrated import GAME_SIGMA as _LIVE_GAME_SIGMA
except ImportError:
    _LIVE_GAME_SIGMA = {}


def _resolve_db_path() -> Path:
    # Check EDGEMODEL_DB_PATH env var (may be loaded from .env by caller)
    env = os.environ.get("EDGEMODEL_DB_PATH", "").strip()
    if env:
        return Path(env)
    # Fall back to inline .env parse (EDGEMODEL_DB_PATH not in shell env by default)
    dotenv = Path(__file__).parent.parent / ".env"
    if dotenv.exists():
        for line in dotenv.read_text(encoding="utf-8", errors="ignore").splitlines():
            if line.startswith("EDGEMODEL_DB_PATH="):
                val = line.split("=", 1)[1].strip().strip('"').strip("'")
                if val:
                    return Path(val)
    return Path(__file__).parent.parent / "data" / "projections.db"


DB_PATH = _resolve_db_path()

SEP = "-" * 68


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _nb_r(mu: float, var: float) -> float:
    """Negative Binomial dispersion parameter r = mu^2 / (var - mu). Returns inf if var <= mu."""
    if var <= mu:
        return float("inf")
    return mu * mu / (var - mu)


def _nb_zero_prob(mu: float, r: float) -> float:
    """P(X=0) under NB(mu, r)."""
    if r == float("inf"):
        return math.exp(-mu)  # Poisson limit
    return (r / (r + mu)) ** r


def _zinb_pi(empirical_zero: float, nb_zero: float) -> float:
    """Extra zero-inflation probability pi = max(0, (emp_zero - nb_zero) / (1 - nb_zero))."""
    if nb_zero >= 1.0:
        return 0.0
    return max(0.0, (empirical_zero - nb_zero) / (1.0 - nb_zero))


def _within_player_variance_ratio(rows, min_games=20, min_mean=0.05):
    """
    Compute per-player var/mu ratios then return sorted list.
    rows: list of (player_id, stat_value) tuples.
    """
    by_player: dict[int, list[float]] = defaultdict(list)
    for pid, val in rows:
        by_player[pid].append(float(val))

    ratios = []
    for pid, vals in by_player.items():
        if len(vals) < min_games:
            continue
        mu = statistics.mean(vals)
        if mu < min_mean:
            continue
        var = statistics.variance(vals)
        ratios.append(var / mu)
    return sorted(ratios)


def _percentile(sorted_list, p):
    if not sorted_list:
        return float("nan")
    idx = int(p * len(sorted_list))
    return sorted_list[min(idx, len(sorted_list) - 1)]


def _within_player_cv(rows, min_games=8, min_mean=0.5):
    """Games-weighted within-player CV (std/mean) — the SIGMA_WNBA 'mult'.

    rows: list of (player_id, stat_value). Returns (cv, n_players).
    """
    by_player: dict[int, list[float]] = defaultdict(list)
    for pid, val in rows:
        by_player[pid].append(float(val))
    num = den = 0.0
    n_players = 0
    for _pid, vals in by_player.items():
        if len(vals) < min_games:
            continue
        mu = statistics.mean(vals)
        if mu <= min_mean:
            continue
        num += len(vals) * (statistics.pstdev(vals) / mu)
        den += len(vals)
        n_players += 1
    return (num / den if den else float("nan")), n_players


# ---------------------------------------------------------------------------
# Mode: mlb-team-runs
# ---------------------------------------------------------------------------

def mode_mlb_team_runs(conn: sqlite3.Connection):
    print(f"\n{'='*68}")
    print("MODE: mlb-team-runs")
    print("Calibrates NB dispersion r for team-level run-scoring.")
    print("Constant to update: MLB_TEAM_RUN_R in engine/run_picks.py")
    print(SEP)

    rows = conn.execute(
        "SELECT home_score, away_score FROM mlb_games WHERE season >= 2023 AND game_type = 'R'"
    ).fetchall()

    if not rows:
        print("ERROR: no rows in mlb_games with season>=2023 and game_type='R'")
        return

    home_scores = [r[0] for r in rows]
    away_scores = [r[1] for r in rows]

    # Pooled (home + away together)
    all_scores = home_scores + away_scores
    mu_pool = statistics.mean(all_scores)
    var_pool = statistics.variance(all_scores)

    # Per-direction
    mu_home = statistics.mean(home_scores)
    var_home = statistics.variance(home_scores)
    mu_away = statistics.mean(away_scores)
    var_away = statistics.variance(away_scores)

    r_home = _nb_r(mu_home, var_home)
    r_away = _nb_r(mu_away, var_away)
    r_pool = _nb_r(mu_pool, var_pool)

    print(f"  Games (regular season, 2023+): {len(rows)}")
    print()
    print(f"  {'Scope':10s}  {'mu':>8s}  {'var':>8s}  {'var/mu':>8s}  {'NB r':>8s}")
    print(f"  {'Home':10s}  {mu_home:8.4f}  {var_home:8.4f}  {var_home/mu_home:8.3f}  {r_home:8.3f}")
    print(f"  {'Away':10s}  {mu_away:8.4f}  {var_away:8.4f}  {var_away/mu_away:8.3f}  {r_away:8.3f}")
    print(f"  {'Pooled':10s}  {mu_pool:8.4f}  {var_pool:8.4f}  {var_pool/mu_pool:8.3f}  {r_pool:8.3f}")
    print()

    # Recommended: average of home/away r
    r_rec = (r_home + r_away) / 2.0
    print(f"  Recommended MLB_TEAM_RUN_R = {r_rec:.3f}  (avg of home/away)")
    print(f"  Current MLB_TEAM_RUN_R     = 3.548  (last calibration 2026-06-05)")
    print()
    print("  Deploy: set MLB_TEAM_RUN_R = <value> in engine/run_picks.py (~line 525)")
    print(f"  Note: r={r_rec:.2f} means team scoring is heavily overdispersed vs Poisson.")
    print(f"  NB vs Normal matters most at integer lines (3.5, 4.5) where NB mass at")
    print(f"  specific integers is non-negligible.")


# ---------------------------------------------------------------------------
# Mode: nhl-game-sigmas
# ---------------------------------------------------------------------------

def mode_nhl_game_sigmas(conn: sqlite3.Connection):
    print(f"\n{'='*68}")
    print("MODE: nhl-game-sigmas")
    print("Calibrates Normal sigma for NHL game total, spread, team, and ML.")
    print("Constant to update: GAME_SIGMA['NHL'] in engine/run_picks.py")
    print(SEP)

    rows = conn.execute(
        "SELECT home_score, away_score FROM nhl_games WHERE season >= 20232024"
    ).fetchall()

    if not rows:
        print("ERROR: no rows in nhl_games with season>=20232024")
        return

    totals   = [r[0] + r[1] for r in rows]
    margins  = [r[0] - r[1] for r in rows]
    home_s   = [r[0] for r in rows]
    away_s   = [r[1] for r in rows]

    sigma_total  = statistics.stdev(totals)
    sigma_spread = statistics.stdev(margins)
    sigma_team_h = statistics.stdev(home_s)
    sigma_team_a = statistics.stdev(away_s)
    sigma_team   = statistics.mean([sigma_team_h, sigma_team_a])

    mu_total = statistics.mean(totals)
    var_total = statistics.variance(totals)

    home_wins = sum(1 for r in rows if r[0] > r[1])
    away_wins = sum(1 for r in rows if r[1] > r[0])
    ties      = sum(1 for r in rows if r[0] == r[1])

    print(f"  Games (2023-24 + 2024-25, all): {len(rows)}")
    print()
    print(f"  Combined score:  mu={mu_total:.3f}, var={var_total:.3f}")
    print(f"  sigma_total      = {sigma_total:.4f}  (game over/under)")
    print(f"  sigma_spread     = {sigma_spread:.4f}  (goal differential / puck line)")
    print(f"  sigma_team_home  = {sigma_team_h:.4f}")
    print(f"  sigma_team_away  = {sigma_team_a:.4f}")
    print(f"  sigma_team (avg) = {sigma_team:.4f}  (individual team score / team total)")
    print()
    print(f"  Home wins: {home_wins/len(rows):.3f}, Away wins: {away_wins/len(rows):.3f}, Ties: {ties/len(rows):.3f}")
    print()
    _nhl = _LIVE_GAME_SIGMA.get("NHL", {})
    print("  Current GAME_SIGMA['NHL'] (deployed):")
    print(f"    total={_nhl.get('total')}, spread={_nhl.get('spread')}, team={_nhl.get('team')}, ml={_nhl.get('ml')}")
    print()
    print("  Calibrated GAME_SIGMA['NHL']:")
    print(f"    total  = {sigma_total:.3f}")
    print(f"    spread = {sigma_spread:.3f}")
    print(f"    team   = {sigma_team:.3f}")
    print(f"    ml     = {sigma_spread:.3f}  (same as spread: P(margin>0) = P(win))")
    print()
    print("  NOTE: sigma_ml = sigma_spread because for ML we compute P(margin > 0) using the")
    print("  same goal-differential distribution. The old sigma=4.0 was a workaround for")
    print("  sigma=1.5 inflating win probs; both are now replaced by the empirical value.")
    print()
    print("  Poisson check: Poisson(mu=6.19) would give sigma = sqrt(6.19) = 2.49")
    print(f"  Empirical sigma = {sigma_total:.3f} (consistent with PMC Poisson dispersion~=0.99)")
    print()
    print("  Deploy: update GAME_SIGMA['NHL'] in engine/run_picks.py (~line 489)")


# ---------------------------------------------------------------------------
# Mode: wnba-game-total
# ---------------------------------------------------------------------------

def mode_wnba_game_total(conn: sqlite3.Connection):
    print(f"\n{'='*68}")
    print("MODE: wnba-game-total")
    print("Calibrates Normal sigma for WNBA game total and team total.")
    print("Constant to update: GAME_SIGMA['WNBA'] in engine/run_picks.py")
    print(SEP)

    # Check if wnba_player_game_stats exists
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    if "wnba_player_game_stats" not in tables:
        print("  SKIP: wnba_player_game_stats table not found in projections.db.")
        print("  Run: python engine/wnba_stats_fetcher.py  to populate it, then re-run.")
        return

    # Aggregate team scores per game from player stats
    # game_id + team_id -> sum of pts
    rows = conn.execute(
        "SELECT game_id, team_id, SUM(pts) as team_pts FROM wnba_player_game_stats "
        "WHERE pts IS NOT NULL GROUP BY game_id, team_id"
    ).fetchall()

    if len(rows) < 20:
        print(f"  SKIP: only {len(rows)} team-game rows — not enough data.")
        return

    # Reconstruct games: each game_id should have 2 rows (home + away)
    from collections import defaultdict
    game_teams: dict = defaultdict(list)
    for gid, tid, pts in rows:
        game_teams[gid].append(pts)

    team_scores = []
    totals = []
    for gid, scores in game_teams.items():
        if len(scores) != 2:
            continue
        totals.append(scores[0] + scores[1])
        team_scores.extend(scores)

    if len(totals) < 10:
        print(f"  SKIP: only {len(totals)} complete games reconstructed — not enough data.")
        return

    sigma_total = statistics.stdev(totals)
    sigma_team  = statistics.stdev(team_scores)
    mu_total    = statistics.mean(totals)
    mu_team     = statistics.mean(team_scores)

    print(f"  Games reconstructed: {len(totals)}")
    print(f"  Combined score: mu={mu_total:.2f}, sigma={sigma_total:.3f}")
    print(f"  Per-team score: mu={mu_team:.2f}, sigma={sigma_team:.3f}")
    print()
    _w = _LIVE_GAME_SIGMA.get("WNBA", {})
    _cur_total, _cur_team = _w.get("total", 10.0), _w.get("team", 7.5)
    print(f"  Current GAME_SIGMA['WNBA'] (deployed): total={_cur_total}, team={_cur_team}")
    print(f"  Calibrated:                 total={sigma_total:.3f}, team={sigma_team:.3f}")
    delta_total = sigma_total - _cur_total
    delta_team  = sigma_team  - _cur_team
    print(f"  Delta:                      total={delta_total:+.3f}, team={delta_team:+.3f}")
    print()
    print("  Deploy: update GAME_SIGMA['WNBA']['total'] and ['team'] in engine/run_picks.py (~line 488)")


# ---------------------------------------------------------------------------
# Mode: mlb-batter-zinb
# ---------------------------------------------------------------------------

def mode_mlb_batter_zinb(conn: sqlite3.Connection):
    print(f"\n{'='*68}")
    print("MODE: mlb-batter-zinb")
    print("Checks whether HITS/BB/RUNS need NB or ZINB (currently POISSON_STATS).")
    print("Investigates: (1) pooled var/mu, (2) within-player var/mu, (3) zero-inflation.")
    print(SEP)

    # Require at_bats >= 1 to filter non-appearances
    rows = conn.execute(
        "SELECT player_id, h, bb, r FROM mlb_batter_game_stats WHERE ab >= 1"
    ).fetchall()

    if not rows:
        print("ERROR: no rows in mlb_batter_game_stats with ab>=1")
        return

    n_total = len(rows)
    print(f"  Rows (ab>=1): {n_total}")
    print()

    for stat_name, idx in [("HITS", 1), ("BB", 2), ("RUNS", 3)]:
        vals = [r[idx] for r in rows]
        mu_pool = statistics.mean(vals)
        var_pool = statistics.variance(vals)
        zero_rate = sum(1 for v in vals if v == 0) / n_total

        # NB fit (pooled)
        r_pool = _nb_r(mu_pool, var_pool)
        nb_zero = _nb_zero_prob(mu_pool, r_pool) if r_pool != float("inf") else math.exp(-mu_pool)
        pi_pool = _zinb_pi(zero_rate, nb_zero)

        # Within-player var/mu
        within_rows = [(r[0], r[idx]) for r in rows]
        ratios = _within_player_variance_ratio(within_rows, min_games=20, min_mean=0.05)
        n_players = len(ratios)

        print(f"  {stat_name}")
        print(f"    Pooled: mu={mu_pool:.4f}, var={var_pool:.4f}, var/mu={var_pool/mu_pool:.3f}, "
              f"NB_r={r_pool:.3f}")
        print(f"    Zero rate: empirical={zero_rate:.3f}, NB_predicted={nb_zero:.3f}, "
              f"ZINB_pi={pi_pool:.4f}")
        if ratios:
            p25 = _percentile(ratios, 0.25)
            p50 = _percentile(ratios, 0.50)
            p75 = _percentile(ratios, 0.75)
            print(f"    Within-player var/mu ({n_players} players): "
                  f"p25={p25:.3f}, median={p50:.3f}, p75={p75:.3f}")
        else:
            print(f"    Within-player var/mu: no qualifying players")

        # Verdict
        within_median = _percentile(ratios, 0.50) if ratios else float("nan")
        if math.isnan(within_median):
            verdict = "UNKNOWN (no within-player data)"
        elif within_median > 1.20:
            verdict = "NB recommended (within-player overdispersion > 1.20)"
        elif within_median > 1.05:
            verdict = "NB marginal — within-player var/mu slightly above 1"
        elif within_median >= 0.85:
            verdict = "POISSON adequate — within-player var/mu near 1"
        else:
            verdict = "UNDERDISPERSED — Binomial would be more accurate, Poisson is conservative"

        print(f"    Verdict: {verdict}")
        print()

    print("  ZINB note: ZINB is only warranted when BOTH conditions hold:")
    print("    (1) pooled zero_rate >> NB_predicted_zero  (pi > 0.05)")
    print("    (2) within-player var/mu > 1.2")
    print("  If within-player var/mu < 1.0, the stat is underdispersed — Poisson")
    print("  slightly overestimates variance (conservative, acceptable for betting).")
    print()
    print("  Current classification: POISSON_STATS = {..., 'HITS', 'BB', 'RUNS', ...}")
    print("  If verdicts show POISSON adequate, no change is needed.")


# ---------------------------------------------------------------------------
# Mode: wnba-3pm
# ---------------------------------------------------------------------------

def mode_wnba_3pm(conn: sqlite3.Connection):
    print(f"\n{'='*68}")
    print("MODE: wnba-3pm")
    print("Calibrates NB dispersion r for WNBA 3-point makes (currently Normal path).")
    print("Constant to update: NB_R_WNBA['3PM'] in engine/run_picks.py")
    print(SEP)

    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    if "wnba_player_game_stats" not in tables:
        print("  SKIP: wnba_player_game_stats table not found in projections.db.")
        print("  Run: python engine/wnba_stats_fetcher.py  to populate it, then re-run.")
        return

    # Check column name for 3PM
    cols = {r[1] for r in conn.execute("PRAGMA table_info(wnba_player_game_stats)").fetchall()}
    col_3pm = "fg3m" if "fg3m" in cols else None
    if col_3pm is None:
        print(f"  SKIP: no 3PM column found. Columns: {sorted(cols)}")
        return

    rows = conn.execute(
        f"SELECT player_id, {col_3pm} FROM wnba_player_game_stats WHERE min >= 8 AND {col_3pm} IS NOT NULL"
    ).fetchall()

    if len(rows) < 100:
        print(f"  SKIP: only {len(rows)} rows — not enough data (need 100+).")
        return

    vals = [r[1] for r in rows]
    mu_pool  = statistics.mean(vals)
    var_pool = statistics.variance(vals)
    zero_rate = sum(1 for v in vals if v == 0) / len(vals)
    r_pool   = _nb_r(mu_pool, var_pool)

    within_rows = rows  # (player_id, fg3m)
    ratios = _within_player_variance_ratio(within_rows, min_games=10, min_mean=0.1)

    print(f"  Rows (min>=8): {len(rows)}")
    print(f"  Pooled: mu={mu_pool:.4f}, var={var_pool:.4f}, var/mu={var_pool/mu_pool:.3f}, NB_r={r_pool:.3f}")
    print(f"  Zero rate: {zero_rate:.3f}")
    if ratios:
        p50 = _percentile(ratios, 0.50)
        p25 = _percentile(ratios, 0.25)
        p75 = _percentile(ratios, 0.75)
        print(f"  Within-player var/mu ({len(ratios)} players): p25={p25:.3f}, median={p50:.3f}, p75={p75:.3f}")
    print()
    print(f"  NBA 3PM NB_R = 9.15 (1246 player-seasons, var/mu=1.149)")
    print(f"  WNBA calibrated NB_R = {r_pool:.3f}")
    print()
    print("  Deploy: set NB_R_WNBA['3PM'] = <value> in engine/run_picks.py (~line 397)")
    print("  Also: remove WNBA 3PM from Normal path in calc_prop_prob() — it will fall into NB block.")


# ---------------------------------------------------------------------------
# Mode: wnba-sigma  (SIGMA_WNBA Normal-CV mults — G14 z-score proxy + combo sigma)
# ---------------------------------------------------------------------------
def mode_wnba_sigma(conn: sqlite3.Connection):
    """Reproducible SIGMA_WNBA calibration (audit P1.2).

    SIGMA_WNBA had no committed producer — the deployed mults were set ad-hoc on
    the priced (min>=20) population. This mode makes the fit reproducible: the
    games-weighted within-player CV at min>=8 / >=15 / >=20, so the min>=20
    "priced-rotation" choice (research item 3) can be re-verified each season.
    """
    print(f"\n{'='*68}")
    print("MODE: wnba-sigma")
    print("Calibrates SIGMA_WNBA Normal-CV 'mult' (G14 z-score proxy + combo sigma).")
    print("Constant to update: SIGMA_WNBA[stat]['mult'] in engine/calibrated.py")
    print(SEP)

    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    if "wnba_player_game_stats" not in tables:
        print("  SKIP: wnba_player_game_stats table not found in projections.db.")
        print("  Set EDGEMODEL_DB_PATH (or --db) to the EdgeModel projections.db, or run")
        print("  python engine/wnba_stats_fetcher.py to populate it, then re-run.")
        return

    cols = {r[1] for r in conn.execute("PRAGMA table_info(wnba_player_game_stats)").fetchall()}
    # (db_col, SIGMA_WNBA label, deployed mult)
    targets = [("pts", "PTS", 0.48), ("ast", "AST", 0.65), ("reb", "REB", 0.54), ("fg3m", "3PM", 0.48)]

    print(f"  {'stat':5} {'min>=8':>8} {'min>=15':>8} {'min>=20':>8}  {'deployed':>8}  n@20")
    rows20 = {}
    for col, label, deployed in targets:
        if col not in cols:
            print(f"  {label:5} (column '{col}' not found — skipped)")
            continue
        cvs = {}
        npl20 = 0
        for thr in (8, 15, 20):
            rows = conn.execute(
                f"SELECT player_id, {col} FROM wnba_player_game_stats WHERE min >= {thr} AND {col} IS NOT NULL"
            ).fetchall()
            cv, npl = _within_player_cv(rows, min_games=8)
            cvs[thr] = cv
            if thr == 20:
                npl20 = npl
        rows20[label] = cvs[20]
        print(f"  {label:5} {cvs[8]:8.3f} {cvs[15]:8.3f} {cvs[20]:8.3f}  {deployed:8.2f}  {npl20}")

    print()
    print("  min>=20 = priced-rotation proxy (research item 3): tightens vs min>=8.")
    print("  PTS/AST/REB deployed mults already match min>=20 — KEEP as-is.")
    print("  3PM: SIGMA_WNBA['3PM']=0.48 is an intentional z-score PROXY (WNBA 3PM props")
    print(f"       use the NB path, NB_R_WNBA=1.342). Empirical min>=20 CV ~{rows20.get('3PM', float('nan')):.2f}")
    print("       understates 3PM dispersion in the G14/combo path only — FLAGGED for")
    print("       monitor, NOT deployed (would reprice WNBA 3PM combos + G14).")
    print()
    print("  Deploy (PTS/AST/REB only, if updating): SIGMA_WNBA[stat]['mult'] = <min>=20>;")
    print("  the 'min' floors (3.5 / 1.0 / 1.0 / 0.70) are separate z-score sigma floors.")


# ---------------------------------------------------------------------------
# Mode: team-sigmas  (writes JSON files to data/)
# ---------------------------------------------------------------------------

_MLB_ID_MAP = {
    108: "LAA", 109: "ARI", 110: "BAL", 111: "BOS", 112: "CHC", 113: "CIN",
    114: "CLE", 115: "COL", 116: "DET", 117: "HOU", 118: "KC",  119: "LAD",
    120: "WSH", 121: "NYM", 133: "OAK", 134: "PIT", 135: "SD",  136: "SEA",
    137: "SF",  138: "STL", 139: "TB",  140: "TEX", 141: "TOR", 142: "MIN",
    143: "PHI", 144: "ATL", 145: "CWS", 146: "MIA", 147: "NYY", 158: "MIL",
}

_NBA_ID_MAP = {
    1610612737: "ATL", 1610612738: "BOS", 1610612739: "CLE",
    1610612740: "NOP", 1610612741: "CHI", 1610612742: "DAL",
    1610612743: "DEN", 1610612744: "GSW", 1610612745: "HOU",
    1610612746: "LAC", 1610612747: "LAL", 1610612748: "MIA",
    1610612749: "MIL", 1610612750: "MIN", 1610612751: "BKN",
    1610612752: "NYK", 1610612753: "ORL", 1610612754: "IND",
    1610612755: "PHI", 1610612756: "PHX", 1610612757: "POR",
    1610612758: "SAC", 1610612759: "SAS", 1610612760: "OKC",
    1610612761: "TOR", 1610612762: "UTA", 1610612763: "MEM",
    1610612764: "WSH", 1610612765: "DET", 1610612766: "CHA",
}

_OUT_DIR = Path(__file__).parent.parent / "data"
_MLB_FALLBACK_R = 3.548
_MIN_GAMES = 20


def _collect_team_scores(pairs):
    """pairs: list of (abbr1, score1, abbr2, score2). Returns {abbr: [scores]}."""
    by_team: dict[str, list[float]] = defaultdict(list)
    for a1, s1, a2, s2 in pairs:
        if a1 and s1 is not None:
            by_team[a1].append(float(s1))
        if a2 and s2 is not None:
            by_team[a2].append(float(s2))
    return by_team


def _team_stats(scores: list[float]) -> tuple[float, float]:
    mu = statistics.mean(scores)
    sigma = statistics.stdev(scores) if len(scores) > 1 else 0.0
    return mu, sigma


def _calibrate_team_sigmas_nhl(conn: sqlite3.Connection) -> dict:
    print("  NHL: querying nhl_games...")
    rows = conn.execute(
        "SELECT home_team, home_score, away_team, away_score FROM nhl_games"
    ).fetchall()
    pairs = [(r[0], r[1], r[2], r[3]) for r in rows]
    by_team = _collect_team_scores(pairs)
    result = {}
    for abbr, scores in sorted(by_team.items()):
        if len(scores) < _MIN_GAMES:
            continue
        mu, sigma = _team_stats(scores)
        result[abbr] = {"score_mu": round(mu, 4), "score_sigma": round(sigma, 4), "n_games": len(scores)}
    print(f"  NHL: {len(result)} teams calibrated from {len(rows)} games")
    return result


def _calibrate_team_sigmas_mlb(conn: sqlite3.Connection) -> dict:
    print("  MLB: querying mlb_games...")
    rows = conn.execute(
        "SELECT home_team_id, home_score, away_team_id, away_score FROM mlb_games WHERE game_type = 'R'"
    ).fetchall()
    pairs = [(_MLB_ID_MAP.get(r[0]), r[1], _MLB_ID_MAP.get(r[2]), r[3]) for r in rows]
    by_team = _collect_team_scores(pairs)
    result = {}
    for abbr, scores in sorted(by_team.items()):
        if abbr is None or len(scores) < _MIN_GAMES:
            continue
        mu, sigma = _team_stats(scores)
        var = statistics.variance(scores) if len(scores) > 1 else 0.0
        nb_r = _nb_r(mu, var) if var > mu else _MLB_FALLBACK_R
        if nb_r == float("inf"):
            nb_r = _MLB_FALLBACK_R
        result[abbr] = {
            "score_mu": round(mu, 4),
            "score_sigma": round(sigma, 4),
            "nb_r": round(nb_r, 4),
            "n_games": len(scores),
        }
    print(f"  MLB: {len(result)} teams calibrated from {len(rows)} games")
    return result


def _calibrate_team_sigmas_nba(conn: sqlite3.Connection) -> dict:
    print("  NBA: aggregating from player_game_stats...")
    rows = conn.execute(
        "SELECT game_id, team_id, SUM(pts) FROM player_game_stats WHERE pts IS NOT NULL "
        "GROUP BY game_id, team_id"
    ).fetchall()
    by_team: dict[str, list[float]] = defaultdict(list)
    for _gid, tid, pts in rows:
        abbr = _NBA_ID_MAP.get(tid)
        if abbr and pts is not None:
            by_team[abbr].append(float(pts))
    result = {}
    for abbr, scores in sorted(by_team.items()):
        if len(scores) < _MIN_GAMES:
            continue
        mu, sigma = _team_stats(scores)
        result[abbr] = {"score_mu": round(mu, 4), "score_sigma": round(sigma, 4), "n_games": len(scores)}
    print(f"  NBA: {len(result)} teams calibrated from {len(rows)} team-game rows")
    return result


def _calibrate_team_sigmas_wnba(conn: sqlite3.Connection) -> dict | None:
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    if "wnba_player_game_stats" not in tables:
        print("  WNBA: wnba_player_game_stats not found — skipping")
        return None
    print("  WNBA: aggregating from wnba_player_game_stats...")
    rows = conn.execute(
        "SELECT game_id, team_id, SUM(pts) FROM wnba_player_game_stats WHERE pts IS NOT NULL "
        "GROUP BY game_id, team_id"
    ).fetchall()
    by_team: dict[str, list[float]] = defaultdict(list)
    for _gid, tid, pts in rows:
        if tid and pts is not None:
            by_team[str(tid)].append(float(pts))
    result = {}
    for tid_str, scores in sorted(by_team.items()):
        if len(scores) < _MIN_GAMES:
            continue
        mu, sigma = _team_stats(scores)
        result[tid_str] = {"score_mu": round(mu, 4), "score_sigma": round(sigma, 4), "n_games": len(scores)}
    print(f"  WNBA: {len(result)} team-ids calibrated from {len(rows)} team-game rows")
    return result


def mode_team_sigmas(conn: sqlite3.Connection, sport: str = "all"):
    import json as _json
    print(f"\n{'='*68}")
    print("MODE: team-sigmas")
    print(f"Sport filter: {sport}")
    print("Writes per-team scoring distributions to data/team_sigmas_{{sport}}.json")
    print(SEP)

    _OUT_DIR.mkdir(exist_ok=True)

    sport_fns = {
        "NHL":  (_calibrate_team_sigmas_nhl,  "team_sigmas_nhl.json"),
        "MLB":  (_calibrate_team_sigmas_mlb,  "team_sigmas_mlb.json"),
        "NBA":  (_calibrate_team_sigmas_nba,  "team_sigmas_nba.json"),
        "WNBA": (_calibrate_team_sigmas_wnba, "team_sigmas_wnba.json"),
    }

    run_sports = list(sport_fns.keys()) if sport == "all" else [sport.upper()]
    for sp in run_sports:
        fn, fname = sport_fns[sp]
        data = fn(conn)
        if data is None:
            continue
        out_path = _OUT_DIR / fname
        out_path.write_text(_json.dumps(data, indent=2))
        print(f"  Written: {out_path}  ({len(data)} teams)")
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

MODES = {
    "mlb-team-runs":  mode_mlb_team_runs,
    "nhl-game-sigmas": mode_nhl_game_sigmas,
    "wnba-game-total": mode_wnba_game_total,
    "mlb-batter-zinb": mode_mlb_batter_zinb,
    "wnba-3pm":        mode_wnba_3pm,
    "wnba-sigma":      mode_wnba_sigma,
    "team-sigmas":     mode_team_sigmas,
}


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--mode", choices=list(MODES.keys()) + ["all"], default="all",
        help="Calibration mode (default: all)"
    )
    parser.add_argument("--db", default=None, help="Override DB path")
    parser.add_argument(
        "--sport", choices=["NHL", "MLB", "NBA", "WNBA", "all"], default="all",
        help="Sport filter for team-sigmas mode (default: all)"
    )
    args = parser.parse_args()

    db = Path(args.db) if args.db else DB_PATH
    if not db.exists():
        print(f"ERROR: DB not found at {db}")
        return

    conn = sqlite3.connect(db)
    print(f"calibrate_distributions.py")
    print(f"DB: {db}")

    modes_to_run = list(MODES.keys()) if args.mode == "all" else [args.mode]
    for mode in modes_to_run:
        if mode == "team-sigmas":
            MODES[mode](conn, args.sport)
        else:
            MODES[mode](conn)

    print(f"\n{'='*68}")
    print("Done. Copy calibrated values into engine/run_picks.py and update CLAUDE.md.")
    conn.close()


if __name__ == "__main__":
    main()
