"""nba_projector.py -- Architecture A+ NBA projection engine.

PTS formula (2P%/3P% decomposition with Bayesian padding):
    team_proj_fga   = team_avg_fga * pace_factor
    player_proj_fga = (USG%/100) * team_proj_fga * (proj_min/48)
    player_proj_3pa = fg3a_rate * player_proj_fga
    player_proj_2pa = (1 - fg3a_rate) * player_proj_fga
    player_proj_fta = fta_fga_ratio * player_proj_fga
    proj_pts        = 2PA*2*fg2_pct + 3PA*3*fg3_pct + FTA*ft_pct

    fg2_pct: Bayesian-padded to 300 FGA (stabilises fast)
    fg3_pct: Bayesian-padded to 750 FGA (stabilises slow)

Per-stat pace elasticity (Q8.4, Research Brief 5, 2026-05-02):
    PTS  pace_factor = base_pf^0.90  (FGA-decomp path)
    3PM  pace_fg3m   = base_pf^0.78  (separate from PTS)
    REB  pace_reb    = base_pf^0.25  (weak pace sensitivity)
    AST  proj_poss   = game_pace^0.50 * LEAGUE_AVG^0.50 * min/48
    STL/BLK proj_poss= game_pace^0.30 * LEAGUE_AVG^0.70 * min/48
    TOV  proj_poss   = game_pace * min/48  (linear — TOV is directly possession-limited)

Role tiers: starter / sixth_man / rotation / spot / cold_start
Per-stat EWMA spans (Brief 5): PTS=15, REB=12, AST=13, FG3M=10, STL/BLK=8, TOV=10, MIN=6.
Cold-start (<5 games on team) -> archetype prior.
Trade blending (Q8.7, 2026-05-02): games 1-3 on new team → 60% prior-team rates;
    games 4-6 → 40% prior-team rates.  Applied as final overlay over all stats.
Training-quality weights (L4+L6, 2026-05-02): per-game weight = vacancy_w * blowout_w.
    L4 vacancy: down-weight games where key teammates (≥12 MPG) were absent.
    L6 blowout proxy: down-weight games with final margin ≥ 15 (asymmetric:
    bench inflated, starters deflated in garbage time).
"""
from __future__ import annotations
import datetime, logging, math, sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from projections_db import (
    DB_PATH, get_player_recent_games, get_player_season_game_count,
    get_team_pace, get_team_def_ratio, get_player_b2b_context,
    get_all_active_players, get_games_for_date, upsert_projection, get_conn,
    get_team_avg_fga, get_team_shooting_stats,
    get_team_tov_rate, get_team_rim_attempt_rate,
    get_player_trade_context,
    get_team_typical_mpg, get_team_game_participants,
)

log = logging.getLogger("nba_projector")
if not log.handlers:
    logging.basicConfig(level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S")

LEAGUE_AVG_PACE   = 99.5
LEAGUE_AVG_TOTAL  = 222.0
# Playoffs run slower / lower-scoring — separate baselines
LEAGUE_AVG_PACE_PO  = 96.5
LEAGUE_AVG_TOTAL_PO = 210.0

# Per-stat pace elasticity exponents — Research Brief 5, Q8.4, 2026-05-02.
# Exponent < 1 dampens the pace effect on that stat relative to linear scaling.
# PTS/3PM via FGA-decomp: moderate sensitivity (0.90/0.78).
# REB: weak pace sensitivity — possessions change but rebound opportunities
#   per possession are nearly constant; human rebound rates are minutes-limited.
# AST: moderate -- pass volume scales with pace but playmaking roles don't.
# STL/BLK: low -- defensive actions are largely independent of tempo.
PACE_ELASTICITY = {
    "pts":  0.90,
    "fg3m": 0.78,
    "reb":  0.25,
    "ast":  0.50,
    "stl":  0.30,
    "blk":  0.30,
}
# Per-stat EWMA spans — Research Brief 5, 2026-05-02.
# Stable high-volume stats (PTS, REB) need longer spans; high-variance low-frequency
# events (BLK, STL) react faster. Minutes react to coach decisions — shortest span.
EWMA_SPAN_STAT = {
    "pts":  15,   # stable — slow decay
    "reb":  12,   # moderate
    "ast":  13,   # moderate (dedicated compute_ast_rate has position-conditional spans)
    "fg3m": 10,   # hot/cold streaks real; keep moderate
    "stl":   8,   # high variance, event-driven
    "blk":   8,   # high variance, event-driven
    "tov":  10,   # moderate
}
EWMA_SPAN_SHOOTING = 10  # shooting efficiency rates (FG%, FT%, FG3A rate, USG%) — stable
EWMA_SPAN_MIN      = 6   # minutes — coach-reactive; was 5, brief says 6 optimal
# Task #4 (Research Brief 6, 2026-05-02): cap raw minutes before EWMA so OT games
# (player played 44+ min) don't inflate the minutes baseline for future games.
# Regulation max is ~42 min; anything ≥ 44 is almost certainly OT.
OT_MIN_CAP = 44.0
# Task #5 (Research Brief 6, 2026-05-02): 240-minute team constraint.
# After projecting all players, scale team totals so proj_min sums to ≤ 240.
# Stats are proportional to minutes, so scale all proj_* keys together.
# Skip teams below TEAM_MIN_FLOOR (incomplete roster / heavy DNP day).
TEAM_MIN_TARGET = 240.0
TEAM_MIN_FLOOR  = 180.0   # below this, roster is incomplete — do not scale
MIN_GAMES_FOR_TIER = 5

# L4 — Availability weighting constants (Research Brief 5, 2026-05-02).
# "Key" teammate threshold: players averaging ≥ 12 MPG whose absence inflates
# the target player's usage/rate (vacancy games).  Weight floor prevents any
# game from being zeroed out entirely.
_AVAIL_KEY_MPG_THRESHOLD = 12.0   # teammates ≥ this MPG are "key" to lineup
MIN_AVAILABILITY_WEIGHT  = 0.30   # floor weight for heavily vacated games

# L6 — Garbage-time blowout proxy (Research Brief 5, 2026-05-02).
# Without PBP data, approximate CtG garbage-time standard with final-margin proxy.
# Bench players (role=spot/rotation) are most contaminated; starters are depressed
# in blowouts (pulled early).  Asymmetric weights applied on top of L4 weights.
_BLOWOUT_MARGIN_HEAVY  = 25   # ≥ this = heavy blowout (Q4 garbage time near-certain)
_BLOWOUT_MARGIN_LIGHT  = 15   # ≥ this = light blowout (some garbage time likely)
# Down-weight multipliers per role tier.  "bench" = spot/rotation; starters
# have their own deflation (pulled early → stats below normal in close-out min).
_BLOWOUT_WEIGHT_BENCH_HEAVY  = 0.55   # bench game with margin ≥ 25 (inflated stats)
_BLOWOUT_WEIGHT_BENCH_LIGHT  = 0.75   # bench game with margin 15-24
_BLOWOUT_WEIGHT_STAR_HEAVY   = 0.75   # starter game with margin ≥ 25 (deflated late)
_BLOWOUT_WEIGHT_STAR_LIGHT   = 0.90   # starter game with margin 15-24
_BLOWOUT_MIN_VALID_GAMES     = 12     # require ≥ this many non-blowout games to apply filter

USG_ROLE_PRIOR = {
    "starter": 24.0, "sixth_man": 20.0, "rotation": 16.0,
    "spot": 13.0,    "cold_start": 20.0,
}

# Empirical post-trade first-5-game averages (Research Brief 5 §8.5, n=352 trades 2021-25).
# cold_start is a catch-all for <5 games on team.  Q8.7 trade blending overrides
# projections for games 1-6 on new team using prior-team per-minute rates.
ROLE_MINUTE_PRIOR = {
    "starter":    28.0,  # empirical 26-32 MPG; was 32.0
    "sixth_man":  24.0,  # unchanged
    "rotation":   16.0,  # empirical 14-18 MPG; was 19.0
    "spot":        6.0,  # empirical 4-8 MPG bench; was 14.0
    "cold_start": 16.0,  # unknown role → rotation-level prior; was 15.0
}

_ROLE_MIN_MINUTES = {
    # df_clean floor: only include games where player was in full role.
    # starter/sixth_man floored at 20/15 — foul-trouble/blowout games with fewer
    # minutes suppress per-minute rates vs full-game performances (2026-05-01).
    "starter": 20.0, "sixth_man": 15.0, "rotation": 10.0,
    "spot": 8.0,  "cold_start": 5.0,
}

# Blowout minutes reduction: sigmoid centred at spread=12, max reduction 20%.
# Replaces flat 0.80x at |spread|>12 (over-reduces 12-15, under-reduces 18+).
# Formula: factor = 1 - 0.20 / (1 + exp(-0.4 * (|spread| - 12)))
# At |spread|=12: factor≈0.90; 15: 0.875; 18: 0.838; 22+: ~0.80.
BLOWOUT_SIGMOID_K        = 0.40   # steepness
BLOWOUT_SIGMOID_MID      = 12.0   # inflection point (spread units)
BLOWOUT_MAX_REDUCTION    = 0.20   # max minutes reduction (20%)
MATCHUP_CLIP             = (0.80, 1.20)

# Days-rest reduction function (Brief P3, Sec. 6b — 2026-05-01).
# Continuous days_rest variable replaces binary B2B flag.
# Empirical findings (sports science literature):
#   - 0 days (back-to-back): ~8–12% minutes reduction across all roles
#   - 1 day rest: ~3–5% reduction (elevated fatigue signals persist)
#   - 2+ days: approaches full recovery
# Functional form: exponential decay toward full capacity.
# max_reduction and half_life calibrated from NBA literature (~3 games data).
DAYS_REST_MAX_REDUCTION = 0.10   # max reduction at 0 days rest (10%)
DAYS_REST_HALF_LIFE     = 1.5    # half-recovery after 1.5 days
# role-specific scalar: how much the player's rest sensitivity varies by role
DAYS_REST_ROLE_SCALAR = {
    "starter": 1.0,     # starters most sensitive to rest
    "sixth_man": 0.95,
    "rotation": 0.90,
    "spot": 0.75,       # bench players less impacted by fatigue
    "cold_start": 0.90,
}
# B2B_MINUTE_FACTOR removed 2026-05-01: replaced by continuous days-rest model
# (DAYS_REST_ROLE_SCALAR + _compute_days_rest_reduction).
PROJ_STATS    = ["pts", "reb", "ast", "fg3m", "stl", "blk", "tov"]
CURRENT_SEASON = "2025-26"

# DraftKings fantasy pts standard deviation coefficient (L6).
# Derived: dk_std ≈ 0.35 * proj_pts across 2024-25 player sample (r²=0.81).
# Re-calibrate against new season data when running evaluate_projector.py.
DK_STD_COEFF = 0.35

# P18-v4 — Playoff calibration (2026-05-02).
# Two-component design replacing the blunt per-stat PLAYOFF_DEFLATORS (P18-v1):
#
# 1. PLAYOFF_MINUTES_SCALAR (role-conditional minutes correction):
#    Derived from 459 matched projection-vs-actual rows (Apr 18–29 2026 playoffs).
#    Starters play more minutes in close playoff games; rotation/bench fewer as
#    coaches tighten to 8-9 man rotations.
#    Methodology: scalar = mean(actual_min) / mean(proj_min) per role_tier.
PLAYOFF_MINUTES_SCALAR = {
    "starter":   1.068,   # 31.6 → 33.8 actual (+6.8%)
    "sixth_man": 0.909,   # 23.3 → 21.2 actual (-9.1%)
    "rotation":  0.786,   # 18.5 → 14.5 actual (-21.4%)
    "spot":      0.902,   # 14.2 → 12.8 actual (-9.8%)
}

# 1b. REGULAR_SEASON_MINUTES_SCALAR (Research Brief 6, 2026-05-02):
#     Derived from 23,995 player-game records (2024-25 regular season).
#     fast_min_ratio.py: mean(act_min / proj_min) per role_tier using same
#     EWMA logic as project_minutes().  Starter/sixth_man essentially unbiased;
#     rotation undershoots by 5.8%; spot prior (6.0 MPG) severely low for
#     players who actually get run.
REGULAR_SEASON_MINUTES_SCALAR = {
    "starter":    1.0,     # ratio 1.013 — negligible
    "sixth_man":  1.0,     # ratio 1.008 — negligible
    "rotation":   1.058,   # ratio 1.058 — +5.8% consistent underprojection
    "spot":       1.672,   # ratio 1.672 — prior=6 MPG too low for players who play
    "cold_start": 1.151,   # ratio 1.151 — prior=16 MPG slightly low
}

# 2. PLAYOFF_RATE_DEFLATORS (genuine per-stat rate changes, not minutes-driven):
#    AST: isolation-heavy playoff offense → fewer motion-offense assists.
#    FG3M: tighter perimeter defense → fewer open 3-point attempts per minute.
#    PTS, REB, STL, BLK, TOV: effect is primarily minutes-driven; no extra deflation.
#    Calibrated empirically (n=43 graded props Apr-May 2026) — P18-v4 yields
#    MAE=3.436 bias=-0.108 vs P18-v1 MAE=3.413 bias=-0.620 and SaberSim 3.254.
PLAYOFF_RATE_DEFLATORS = {
    "ast":  0.8255,
    "fg3m": 0.8780,
}

# P11 — Home/away adjustment factors (2026-05-01).
# Derived from within-player regression on 602 players with >=5 home AND >=5 away
# games in projections_db (70k+ player-game rows, min>=10 min).
# Method: for each player, compute (home_avg - away_avg) / player_avg; then
# average across players.  Half-delta applied symmetrically: HOME = 1 + delta,
# AWAY = 1 - delta, so the projection round-trips correctly for a player whose
# EWMA baseline averages home and away games roughly equally.
# STL excluded — within-player delta is -1.59% (unexpected direction, marginal,
# likely noise; no adjustment applied).
# TOV is negative because home teams commit fewer turnovers.
_HOME_AWAY_DELTA = {
    "pts":  0.0052,   # +/- 1.04% full spread; home = +0.52%
    "reb":  0.0058,   # +/- 1.17%
    "ast":  0.0135,   # +/- 2.69%
    "fg3m": 0.0131,   # +/- 2.62%
    "blk":  0.0127,   # +/- 2.54%
    "tov": -0.0063,   # +/- 1.26%  (home team fewer turnovers)
}

# PTS blend constants — re-fit annually via:
#   python engine/evaluate_projector.py --grid-search-alpha --season 2025-26 --n 2000 --seed 42
# Alpha: weight on FGA-decomp path (0.0=pure per-min, 1.0=pure FGA).
# Bias correction: additive constant applied after blending. Always re-fit LAST
# (after changing alpha or LG_FTA_FGA), calibrated against actual outcomes only.
PTS_BLEND_ALPHA       = 0.50   # calibrated 2026-05-01: bias-optimal vs MAE-flat curve
                               # (alpha=0.30 MAE-optimal but +0.086 more bias; 0.50 dominates)
BLEND_BIAS_CORRECTION = 0.0    # no additive correction — fix root causes structurally

# REB decomposition constants (Brief P3, Sec. 2 — 2026-05-01)
# Model OREB and DREB separately via available-rebound denominators.
# OREB: player OREB / (team_misses * min/48). Stabilises ~200-250 possessions (~20 games).
# DREB: player DREB / (opp_misses * min/48).  Stabilises ~250-300 possessions (~28 games).
# Positional priors calibrated from 2024-25 DB (min>=10, Regular Season) — P15 2026-05-01.
# Denominator: (tm_fga - tm_fgm + 0.44*tm_fta) * min/48 — matches compute_reb_rates().
_REB_POS_OREB_PRIOR = {"G": 0.02043, "F": 0.03247, "C": 0.07048}  # OREB per team miss/48
_REB_POS_DREB_PRIOR = {"G": 0.08086, "F": 0.10569, "C": 0.17162}  # DREB per opp miss/48
_REB_PRIOR_N_OREB   = 15   # Research Brief 5: REB k=12-15; was 20
_REB_PRIOR_N_DREB   = 15   # Research Brief 5: REB k=12-15; was 28 (overshrunken)
REB_ALPHA           = 0.45  # weight on decomposed path (lean baseline until rates stabilise)

# AST decomposition constants (Brief P3, Sec. 3 — 2026-05-01)
# AST rate per team possession: normalises for pace naturally; avoids per-FGA over-normalisation.
# Position-conditional EWMA span: non-PGs have volatile AST roles → shorter span + stronger shrinkage.
# G/F/C grouping: G prior = midpoint of brief's PG(0.140) and SG(0.075) = 0.110.
_AST_EWMA_SPAN = {"G": 10, "F": 6, "C": 5}
# Priors calibrated from 2024-25 DB (min>=20, Regular Season) — 2026-05-01.
# Brief uses PG/SG split (0.140/0.075); our G bucket is dominated by SGs and combo
# guards, so the midpoint (0.110) massively overstates the actual DB average (0.073).
# Empirical: G=0.073, F=0.050, C=0.045. Re-calibrate annually from DB.
_AST_POS_PRIOR = {"G": 0.073, "F": 0.050, "C": 0.045}  # AST per team possession
_AST_PRIOR_N   = {"G":  12,  "F":  14,    "C":  14}    # Research Brief 5: AST k=10-12; was 22/32/35
AST_ALPHA      = 0.40   # lean toward baseline until rates stabilise over longer sample
FG3M_BLEND_ALPHA = 0.50  # weight on FGA-decomp path for 3PM; re-evaluate after grid search

# STL/BLK Bayesian shrinkage priors (Brief P3, Sec. 5 — 2026-05-01).
# P5 (2026-05-01): STL/BLK/TOV priors restated in per-POSSESSION units.
# Conversion: prior_per_poss = prior_per_min * (48 / LEAGUE_AVG_PACE) = prior_per_min * 0.4824
# compute_stl_blk_rates() and compute_tov_rate() now normalise training data by
# (team_pace * min / 48) — matching the per-possession basis used by compute_ast_rate().
# Projection: rate_per_poss * proj_poss * matchup  (pace_factor multiplier removed).
# P15 (2026-05-01): re-calibrated from 2024-25 DB (min>=10, Regular Season).
# Denominator: team_pace * min / 48 — matches compute_stl_blk_rates().
_STL_POS_PRIOR = {"G": 0.01830, "F": 0.01664, "C": 0.01405}  # STL per possession
_STL_PRIOR_N   = 5   # Research Brief 5: STL k=4-6; was 25 (severely overshrunken)

# BLK priors: centers split into non-blockers (C_low) and rim protectors (C_high).
# Classification still uses career BLK/min vs _BLK_CENTER_SPLIT_THRESHOLD (per-minute
# threshold unchanged — classification is independent of the rate training basis).
_BLK_CENTER_SPLIT_THRESHOLD = 0.030   # BLK/min cutoff for center classification (per-minute)
_BLK_POS_PRIOR = {
    # P15 (2026-05-01): re-calibrated from 2024-25 DB (min>=10, Regular Season).
    # C_low/C_high split uses same _BLK_CENTER_SPLIT_THRESHOLD=0.030 BLK/min.
    "G":      0.00537,  # guards
    "F":      0.00805,  # forwards
    "C_low":  0.00886,  # non-blockers
    "C_high": 0.02415,  # rim protectors
}
_BLK_PRIOR_N = {
    "G":      5,   # Research Brief 5: BLK k=4-6; was 30
    "F":      5,   # was 30
    "C_low":  6,   # near-zero rate — slightly more shrinkage; was 20
    "C_high": 5,   # rim protectors converge quickly; was 25
}

# TOV per-possession priors — derived from per-36 archetypes / LEAGUE_AVG_PACE * 48.
_TOV_POS_PRIOR = {"G": 0.0335, "F": 0.0241, "C": 0.0268}
_TOV_PRIOR_N   = 15  # Research Brief 5 guidance; was 20

LEAGUE_AVG_TOV_RATE        = 0.136  # turnovers per possession, league-wide (2024-25 calibrated)
LEAGUE_AVG_RIM_ATTEMPT_RATE = 56.0   # non-3pt FGA per game, league-wide (2024-25 calibrated)

_ARCHETYPE_PER36 = {
    "G": {"pts": 14.5, "reb": 3.2, "ast": 5.8, "fg3m": 1.8, "stl": 1.2, "blk": 0.3, "tov": 2.5},
    "F": {"pts": 13.8, "reb": 5.8, "ast": 2.8, "fg3m": 1.2, "stl": 0.9, "blk": 0.6, "tov": 1.8},
    "C": {"pts": 13.2, "reb": 9.4, "ast": 1.8, "fg3m": 0.4, "stl": 0.7, "blk": 1.8, "tov": 2.0},
}

def _pos_group(pos):
    if not pos: return "F"
    p = str(pos).strip().upper()
    if p.startswith("G"): return "G"
    if p.startswith("C"): return "C"
    return "F"

def cold_start_rates(position):
    return dict(_ARCHETYPE_PER36[_pos_group(position)])

def classify_role(df):
    if df.empty: return "cold_start"
    recent = df.head(10)
    avg_min = recent["min"].mean()
    starter_rate = recent["starter_flag"].mean()
    if starter_rate >= 0.60 and avg_min >= 26: return "starter"
    if avg_min >= 20: return "sixth_man"
    if avg_min >= 12: return "rotation"
    if avg_min >= 5:  return "spot"
    return "cold_start"

def _weighted_ewm_mean(
    series: pd.Series, weights: pd.Series, span: int
) -> float:
    """Combine per-sample availability weights with EWMA recency decay.

    Standard pandas EWMA gives more weight to recent observations via exponential
    decay.  This function multiplies that decay by per-game availability weights
    (values in [MIN_AVAILABILITY_WEIGHT, 1.0]) so vacancy games are suppressed
    without being excluded entirely.

    Formula:
        combined_w[i] = recency_decay[i] * avail_w[i]
        result = Σ(series[i] * combined_w[i]) / Σ(combined_w[i])

    where recency_decay is oldest→newest: (1-α)^(n-1-i), α = 2/(span+1).
    """
    if series.empty:
        return 0.0
    n     = len(series)
    alpha = 2.0 / (span + 1.0)
    # recency weights: index 0 = oldest game, index n-1 = most recent
    recency = np.array([(1.0 - alpha) ** (n - 1 - i) for i in range(n)],
                       dtype=np.float64)
    aw      = weights.reindex(series.index, fill_value=1.0).clip(
                  lower=MIN_AVAILABILITY_WEIGHT).values.astype(np.float64)
    combined = recency * aw
    total_w  = combined.sum()
    if total_w < 1e-9:
        return float(series.mean())
    vals = series.fillna(0.0).values.astype(np.float64)
    return float((vals * combined).sum() / total_w)


def _blowout_weight(margin: float, player_min: float) -> float:
    """L6 — per-game blowout proxy weight.

    Applies the asymmetric CtG-style garbage-time discount using final margin
    as a proxy (full PBP not available).  Stars get a light deflation discount
    (pulled early → fewer late-game stats); bench players get a heavier discount
    (inflated stats from garbage-time minutes).

    player_min is the player's actual minutes in that game; < 22 = bench context.
    """
    is_bench = player_min < 22.0
    if margin >= _BLOWOUT_MARGIN_HEAVY:
        return _BLOWOUT_WEIGHT_BENCH_HEAVY if is_bench else _BLOWOUT_WEIGHT_STAR_HEAVY
    if margin >= _BLOWOUT_MARGIN_LIGHT:
        return _BLOWOUT_WEIGHT_BENCH_LIGHT if is_bench else _BLOWOUT_WEIGHT_STAR_LIGHT
    return 1.0


def compute_availability_weights(
    df: pd.DataFrame,
    player_id: int,
    team_id: int,
    season: str,
    game_date: str,
    db_path,
) -> pd.Series:
    """Compute per-game training-quality weights (L4 + L6 combined).

    L4 — Vacancy weighting: down-weight games where key teammates (≥ 12 MPG)
    were absent, inflating/deflating the target player's role context.

    L6 — Blowout proxy: down-weight games with large final margins, which
    contain garbage time that inflates bench rates or deflates starter rates.
    Applied asymmetrically (bench more suppressed than starters).

    L6 filter applies only when ≥ _BLOWOUT_MIN_VALID_GAMES non-blowout games
    exist in df; otherwise it is skipped to avoid starving the sample.

    Combined weight per game = L4_weight * L6_weight, floored at
    MIN_AVAILABILITY_WEIGHT.

    Returns pd.Series indexed to df.index.  Falls back to all-1.0 on any error.
    """
    try:
        # --- L4 component ---
        typical_mpg = get_team_typical_mpg(
            team_id, season, game_date,
            min_mpg_threshold=_AVAIL_KEY_MPG_THRESHOLD, db_path=db_path,
        )
        typical_mpg.pop(player_id, None)  # exclude self

        key_baseline = sum(typical_mpg.values()) if typical_mpg else 0.0

        game_ids = df["game_id"].astype(str).tolist()
        participants = (
            get_team_game_participants(team_id, game_ids, db_path)
            if typical_mpg else {}
        )

        # --- L6 component: decide whether to apply blowout filter ---
        has_margin = "game_margin" in df.columns and df["game_margin"].notna().any()
        if has_margin:
            margins = df["game_margin"].fillna(0.0)
            n_nonblowout = int((margins < _BLOWOUT_MARGIN_LIGHT).sum())
            apply_blowout = n_nonblowout >= _BLOWOUT_MIN_VALID_GAMES
        else:
            apply_blowout = False

        weights_list = []
        for _, row in df.iterrows():
            # L4
            if typical_mpg:
                gid     = str(row["game_id"])
                present = participants.get(gid, set())
                absent_mpg = sum(
                    mpg for pid, mpg in typical_mpg.items()
                    if pid not in present
                )
                w_l4 = max(MIN_AVAILABILITY_WEIGHT,
                           1.0 - absent_mpg / max(key_baseline, 1.0))
            else:
                w_l4 = 1.0

            # L6
            if apply_blowout:
                margin = float(row.get("game_margin", 0.0) or 0.0)
                w_l6   = _blowout_weight(margin, float(row.get("min", 0.0) or 0.0))
            else:
                w_l6 = 1.0

            weights_list.append(max(MIN_AVAILABILITY_WEIGHT, w_l4 * w_l6))

        return pd.Series(weights_list, index=df.index, dtype=np.float64)

    except Exception as exc:
        log.debug("compute_availability_weights: fallback to 1.0 — %s", exc)
        return pd.Series(1.0, index=df.index)


def compute_per_minute_rates(df, avail_weights: Optional[pd.Series] = None):
    if df.empty: return {s: 0.0 for s in PROJ_STATS}
    d = df.sort_values("game_date").copy()
    if d.empty: return {s: 0.0 for s in PROJ_STATS}
    # L4: combine era_weight with availability weights when provided.
    if avail_weights is not None:
        aw = avail_weights.reindex(d.index, fill_value=1.0).clip(
                 lower=MIN_AVAILABILITY_WEIGHT)
        combined_era = d["era_weight"] * aw
    else:
        combined_era = d["era_weight"]
    rates = {}
    for stat in PROJ_STATS:
        if stat not in d.columns:
            rates[stat] = 0.0; continue
        per_min  = d[stat] / d["min"]
        weighted = per_min * combined_era
        span     = EWMA_SPAN_STAT.get(stat, 10)
        ewma_w   = weighted.ewm(span=span, min_periods=1).mean().iloc[-1]
        ewma_e   = combined_era.ewm(span=span, min_periods=1).mean().iloc[-1]
        rates[stat] = float(ewma_w / max(ewma_e, 1e-6))
    return rates

def compute_reb_rates(df_clean: pd.DataFrame,
                      avail_oreb_per_game: float,
                      avail_dreb_per_game: float,
                      pos_group: str,
                      avail_weights: Optional[pd.Series] = None) -> tuple[float, float]:
    """Bayesian-shrunk OREB and DREB rates per available rebound.

    avail_oreb_per_game: team_FGA/g * (1 - team_FG%) — OREB pool (own misses).
    avail_dreb_per_game: opp_FGA/g  * (1 - opp_FG%)  — DREB pool (opp misses).

    Rate formula per game i:
        oreb_rate[i] = player_oreb[i] / (avail_oreb_per_game * min[i] / 48)
        dreb_rate[i] = player_dreb[i] / (avail_dreb_per_game * min[i] / 48)

    EWMA (span=10) then Bayesian shrinkage to positional priors.
    Returns (oreb_rate, dreb_rate) — both in units of [rebounds per available rebound].
    """
    oreb_prior = _REB_POS_OREB_PRIOR.get(pos_group, 0.044)
    dreb_prior = _REB_POS_DREB_PRIOR.get(pos_group, 0.133)

    if df_clean.empty or "oreb" not in df_clean.columns or "dreb" not in df_clean.columns:
        return oreb_prior, dreb_prior

    d = df_clean.sort_values("game_date").copy()
    n_games = len(d)

    # Available rebound pool scaled to each game's minutes
    avail_oreb_g = (avail_oreb_per_game * d["min"] / 48.0).clip(lower=0.1)
    avail_dreb_g = (avail_dreb_per_game * d["min"] / 48.0).clip(lower=0.1)

    oreb_raw = (d["oreb"].fillna(0) / avail_oreb_g).replace([np.inf, -np.inf], np.nan).fillna(oreb_prior)
    dreb_raw = (d["dreb"].fillna(0) / avail_dreb_g).replace([np.inf, -np.inf], np.nan).fillna(dreb_prior)

    # L4: use availability-weighted EWMA when weights are provided.
    _span_reb = EWMA_SPAN_STAT["reb"]
    if avail_weights is not None:
        aw = avail_weights.reindex(d.index, fill_value=1.0)
        oreb_ewma = _weighted_ewm_mean(oreb_raw, aw, _span_reb)
        dreb_ewma = _weighted_ewm_mean(dreb_raw, aw, _span_reb)
    else:
        oreb_ewma = float(oreb_raw.ewm(span=_span_reb, min_periods=1).mean().iloc[-1])
        dreb_ewma = float(dreb_raw.ewm(span=_span_reb, min_periods=1).mean().iloc[-1])

    # Bayesian shrinkage: (observed_n * ewma + prior_n * prior) / (observed_n + prior_n)
    oreb_rate = (n_games * oreb_ewma + _REB_PRIOR_N_OREB * oreb_prior) / (n_games + _REB_PRIOR_N_OREB)
    dreb_rate = (n_games * dreb_ewma + _REB_PRIOR_N_DREB * dreb_prior) / (n_games + _REB_PRIOR_N_DREB)
    return float(oreb_rate), float(dreb_rate)


def compute_ast_rate(df_clean: pd.DataFrame,
                     team_pace: float,
                     pos_group: str,
                     avail_weights: Optional[pd.Series] = None) -> float:
    """Bayesian-shrunk AST rate per team possession (Brief P3, Sec. 3).

    Rate formula per game i:
        ast_rate[i] = player_ast[i] / (team_pace * min[i] / 48)

    EWMA span is position-conditional (non-PGs have volatile AST roles):
        G=10, F=6, C=5.
    Shrinkage to positional priors is stronger for non-PGs.

    Returns rate in units of [assists per team-possession-equivalent].
    """
    prior   = _AST_POS_PRIOR.get(pos_group, 0.055)
    prior_n = _AST_PRIOR_N.get(pos_group, 28)
    span    = _AST_EWMA_SPAN.get(pos_group, 8)

    if df_clean.empty or "ast" not in df_clean.columns:
        return prior

    d = df_clean.sort_values("game_date").copy()
    n_games = len(d)

    # Possessions available to the player in each game (scaled by minutes fraction)
    poss_per_game = (team_pace * d["min"] / 48.0).clip(lower=0.1)
    ast_raw = (
        d["ast"].fillna(0) / poss_per_game
    ).replace([np.inf, -np.inf], np.nan).fillna(prior)

    # L4: availability-weighted EWMA — AST is most sensitive to teammate vacancies
    # (e.g. primary ball-handler out inflates backup AST rates).
    if avail_weights is not None:
        aw = avail_weights.reindex(d.index, fill_value=1.0)
        ast_ewma = _weighted_ewm_mean(ast_raw, aw, span)
    else:
        ast_ewma = float(ast_raw.ewm(span=span, min_periods=1).mean().iloc[-1])

    # Bayesian shrinkage to positional prior
    ast_rate = (n_games * ast_ewma + prior_n * prior) / (n_games + prior_n)
    return float(ast_rate)


def compute_stl_blk_rates(df_clean: pd.DataFrame,
                           pos_group: str,
                           team_pace: float,
                           avail_weights: Optional[pd.Series] = None) -> tuple[float, float]:
    """Bayesian-shrunk per-POSSESSION STL and BLK rates.

    P5 (2026-05-01): training basis changed from per-minute to per-possession.
    Historical rates are now normalised by (team_pace * min / 48) so that
    pace variation across training games is removed before Bayesian shrinkage.
    Priors restated in matching per-possession units.

    STL: single Gaussian prior per position group.
    BLK: centers classified into C_low / C_high via career BLK/min vs threshold.
         Classification still uses per-minute career rate (threshold unchanged).
         If df_clean < 5 games, falls back to C_low (conservative).

    Returns (stl_rate, blk_rate) in units of [events per possession].
    """
    stl_prior = _STL_POS_PRIOR.get(pos_group, 0.025)

    # --- BLK prior resolution: classify centers before shrinkage ---
    if pos_group == "C" and not df_clean.empty and "blk" in df_clean.columns:
        mins_all  = df_clean["min"].clip(lower=1.0)
        career_blk_per_min = float(
            (df_clean["blk"].fillna(0) / mins_all)
            .replace([np.inf, -np.inf], np.nan)
            .mean()
        )
        # Require at least 5 games for a reliable classification; otherwise
        # the mean is too noisy and we fall back to the C population midpoint.
        if len(df_clean) >= 5 and not np.isnan(career_blk_per_min):
            blk_key = "C_high" if career_blk_per_min >= _BLK_CENTER_SPLIT_THRESHOLD else "C_low"
        else:
            blk_key = "C_low"   # conservative fallback — under-projection is safer than over
    else:
        blk_key = pos_group   # G or F — lookup unchanged

    blk_prior   = _BLK_POS_PRIOR.get(blk_key, 0.017)
    blk_prior_n = _BLK_PRIOR_N.get(blk_key, 5)

    if df_clean.empty or "stl" not in df_clean.columns:
        return stl_prior, blk_prior

    d = df_clean.sort_values("game_date").copy()
    n_games = len(d)

    # Per-possession normalisation — removes pace variation across training games.
    # poss_g[i] = estimated possessions played by this player in game i.
    poss_g = (team_pace * d["min"] / 48.0).clip(lower=0.1)

    stl_raw = (d["stl"].fillna(0) / poss_g).replace(
        [np.inf, -np.inf], np.nan
    ).fillna(stl_prior)
    blk_col = d.get("blk", pd.Series([0] * len(d), index=d.index))
    blk_raw = (blk_col.fillna(0) / poss_g).replace(
        [np.inf, -np.inf], np.nan
    ).fillna(blk_prior)

    # L4: availability-weighted EWMA for STL/BLK.
    _span_stl, _span_blk = EWMA_SPAN_STAT["stl"], EWMA_SPAN_STAT["blk"]
    if avail_weights is not None:
        aw = avail_weights.reindex(d.index, fill_value=1.0)
        stl_ewma = _weighted_ewm_mean(stl_raw, aw, _span_stl)
        blk_ewma = _weighted_ewm_mean(blk_raw, aw, _span_blk)
    else:
        stl_ewma = float(stl_raw.ewm(span=_span_stl, min_periods=1).mean().iloc[-1])
        blk_ewma = float(blk_raw.ewm(span=_span_blk, min_periods=1).mean().iloc[-1])

    # Bayesian shrinkage — BLK uses the resolved prior and N for this player's archetype
    stl_rate = (n_games * stl_ewma + _STL_PRIOR_N * stl_prior) / (n_games + _STL_PRIOR_N)
    blk_rate = (n_games * blk_ewma + blk_prior_n * blk_prior) / (n_games + blk_prior_n)
    return float(stl_rate), float(blk_rate)


def compute_tov_rate(df_clean: pd.DataFrame,
                     team_pace: float,
                     pos_group: str,
                     avail_weights: Optional[pd.Series] = None) -> float:
    """Bayesian-shrunk per-POSSESSION TOV rate.

    P5 (2026-05-01): replaces the generic per-minute rate from
    compute_per_minute_rates() for TOV.  Training basis is per-possession
    (team_pace * min / 48), consistent with compute_ast_rate() and the
    updated compute_stl_blk_rates().

    Returns rate in units of [turnovers per possession].
    """
    prior   = _TOV_POS_PRIOR.get(pos_group, 0.028)
    prior_n = _TOV_PRIOR_N

    if df_clean.empty or "tov" not in df_clean.columns:
        return prior

    d = df_clean.sort_values("game_date").copy()
    n_games = len(d)

    poss_g = (team_pace * d["min"] / 48.0).clip(lower=0.1)
    tov_raw = (d["tov"].fillna(0) / poss_g).replace(
        [np.inf, -np.inf], np.nan
    ).fillna(prior)

    # L4: availability-weighted EWMA for TOV.
    _span_tov = EWMA_SPAN_STAT["tov"]
    if avail_weights is not None:
        aw = avail_weights.reindex(d.index, fill_value=1.0)
        tov_ewma = _weighted_ewm_mean(tov_raw, aw, _span_tov)
    else:
        tov_ewma = float(tov_raw.ewm(span=_span_tov, min_periods=1).mean().iloc[-1])
    tov_rate = (n_games * tov_ewma + prior_n * prior) / (n_games + prior_n)
    return float(tov_rate)


def compute_shooting_rates(df) -> dict:
    """Compute EWMA shooting efficiency rates for FGA/FTA PTS decomposition.

    Returns dict with keys:
        fg2_pct        — Bayesian-padded 2P% (stabilises at ~300 FGA)
        fg3_pct        — Bayesian-padded 3P% (stabilises at ~750 FGA)
        fg3a_rate      — EWMA of FG3A/FGA  (share of shots from 3)
        ft_pct         — EWMA FT%
        fta_fga_ratio  — EWMA FTA/FGA
        usg_pct        — EWMA USG%  (percentage, e.g. 22.5)

    Composite eFG% is retired: separating 2P% and 3P% avoids conflating two
    distributions with different stabilisation rates (300 vs 750 attempts).

    Bayesian padding formula (Kostya Medvedovsky / FantasyLabs approach):
        stabilised_2p = (career_2PM + 300 * LG_2P) / (career_2PA + 300)
        stabilised_3p = (career_3PM + 750 * LG_3P) / (career_3PA + 750)
    We approximate career volume with the full df window (up to 30 games).
    """
    # League-average constants — calibrated from 2024-25 DB (Apr 30 2026)
    # Previously used stale estimates; updated from actual player_game_stats:
    #   fg2_pct: 0.5438, fg3_pct: 0.3598, fg3a_rate: 0.4205, fta/fga: 0.2450
    LG_2P_PCT    = 0.544   # league avg 2P%  (was 0.532 — biased Bayesian anchor low)
    LG_3P_PCT    = 0.360   # league avg 3P%
    LG_FT_PCT    = 0.780
    LG_FG3A_RATE = 0.420   # ~42% of FGA are 3PA league-wide (was 0.385 — stale)
    LG_FTA_FGA   = 0.257   # FTA/FGA ratio; calibrated Apr 30 2026:
                           # 0.280→+0.510 bias, 0.245→-0.651, 0.265→+0.431; interp→0.257

    if df.empty:
        return {
            "fg2_pct":       LG_2P_PCT,
            "fg3_pct":       LG_3P_PCT,
            "fg3a_rate":     LG_FG3A_RATE,
            "ft_pct":        LG_FT_PCT,
            "fta_fga_ratio": LG_FTA_FGA,
            "usg_pct":       20.0,
        }

    d = df.sort_values("game_date").copy()

    # ------------------------------------------------------------------ #
    # 2P% — Bayesian padding to 300 FGA equivalent                        #
    # ------------------------------------------------------------------ #
    has_fg3a = "fg3a" in d.columns
    if has_fg3a:
        d_fg3a = d["fg3a"].fillna(0)
        fg2a   = (d["fga"] - d_fg3a).clip(lower=0)
        fg2m   = (d["fgm"] - d["fg3m"]).clip(lower=0)
    else:
        # Approximate: assume LG_FG3A_RATE of attempts are 3PA
        fg2a = (d["fga"] * (1 - LG_FG3A_RATE)).clip(lower=0)
        fg2m = (d["fgm"] - d["fg3m"]).clip(lower=0)

    total_fg2a = float(fg2a.sum())
    total_fg2m = float(fg2m.sum())
    PAD_2P     = 300.0
    fg2_pct    = (total_fg2m + PAD_2P * LG_2P_PCT) / (total_fg2a + PAD_2P)
    fg2_pct    = float(np.clip(fg2_pct, 0.35, 0.75))

    # ------------------------------------------------------------------ #
    # 3P% — Bayesian padding to 750 FGA equivalent                        #
    # ------------------------------------------------------------------ #
    total_fg3a = float(d["fg3a"].sum()) if has_fg3a else float((d["fga"] * LG_FG3A_RATE).sum())
    total_fg3m = float(d["fg3m"].sum())
    PAD_3P     = 750.0
    fg3_pct    = (total_fg3m + PAD_3P * LG_3P_PCT) / (total_fg3a + PAD_3P)
    fg3_pct    = float(np.clip(fg3_pct, 0.20, 0.55))

    # ------------------------------------------------------------------ #
    # FG3A rate — EWMA of what fraction of this player's FGA are 3PA      #
    # ------------------------------------------------------------------ #
    mask_fga = d["fga"] > 0
    if has_fg3a:
        fg3a_series = np.where(mask_fga, d["fg3a"] / d["fga"], np.nan)
    else:
        fg3a_series = np.full(len(d), LG_FG3A_RATE, dtype=float)
    fg3a_vals  = pd.Series(fg3a_series).ffill().fillna(LG_FG3A_RATE)
    fg3a_rate  = float(fg3a_vals.ewm(span=EWMA_SPAN_SHOOTING, min_periods=1).mean().iloc[-1])
    fg3a_rate  = float(np.clip(fg3a_rate, 0.0, 0.85))

    # ------------------------------------------------------------------ #
    # FT% — EWMA                                                           #
    # ------------------------------------------------------------------ #
    mask_fta  = d["fta"] > 0
    ft_series = np.where(mask_fta, d["ftm"] / d["fta"], np.nan)
    ft_vals   = pd.Series(ft_series).ffill().fillna(LG_FT_PCT)
    ft_pct    = float(ft_vals.ewm(span=EWMA_SPAN_SHOOTING, min_periods=1).mean().iloc[-1])
    ft_pct    = float(np.clip(ft_pct, 0.40, 1.00))

    # ------------------------------------------------------------------ #
    # FTA/FGA ratio                                                        #
    # ------------------------------------------------------------------ #
    ratio_series  = np.where(mask_fga, d["fta"] / d["fga"], np.nan)
    ratio_vals    = pd.Series(ratio_series).ffill().fillna(LG_FTA_FGA)
    fta_fga_ratio = float(ratio_vals.ewm(span=EWMA_SPAN_SHOOTING, min_periods=1).mean().iloc[-1])
    fta_fga_ratio = float(np.clip(fta_fga_ratio, 0.0, 1.20))

    # ------------------------------------------------------------------ #
    # USG%                                                                 #
    # ------------------------------------------------------------------ #
    has_team = all(c in d.columns for c in ("tm_fga", "tm_fta", "tm_tov", "tm_min"))
    if has_team:
        tm_denom = d["tm_fga"] + 0.44 * d["tm_fta"] + d["tm_tov"]
        pl_num   = d["fga"]   + 0.44 * d["fta"]   + d["tov"]
        usg_raw  = np.where(
            (d["min"] > 0) & (tm_denom > 0),
            100.0 * pl_num * (d["tm_min"] / 5.0) / (d["min"] * tm_denom),
            np.nan,
        )
        usg_vals = pd.Series(usg_raw).ffill().fillna(20.0)
        usg_pct  = float(usg_vals.ewm(span=EWMA_SPAN_SHOOTING, min_periods=1).mean().iloc[-1])
    else:
        usg_pct = 20.0
    usg_pct = float(np.clip(usg_pct, 5.0, 45.0))

    return {
        "fg2_pct":       fg2_pct,
        "fg3_pct":       fg3_pct,
        "fg3a_rate":     fg3a_rate,
        "ft_pct":        ft_pct,
        "fta_fga_ratio": fta_fga_ratio,
        "usg_pct":       usg_pct,
    }



def _compute_days_rest_reduction(days_rest: int, role: str) -> float:
    """Compute minutes reduction factor from days of rest.

    Uses exponential decay: reduction = max_reduction * exp(-days_rest / half_life).
    At days_rest=0 (B2B): reduction ≈ max_reduction * role_scalar.
    At days_rest=1.5: reduction ≈ max_reduction * role_scalar / 2.
    At days_rest=5+: reduction ≈ 0 (full recovery).

    Returns multiplicative factor in (0.90, 1.0] where 1.0 = no reduction.
    """
    days_rest = max(0, min(days_rest, 10))  # clip to [0, 10]
    role_scalar = DAYS_REST_ROLE_SCALAR.get(role, 0.90)
    # Exponential decay: after half_life days, reduction halves.
    reduction = DAYS_REST_MAX_REDUCTION * role_scalar * math.exp(
        -days_rest / DAYS_REST_HALF_LIFE
    )
    return 1.0 - reduction  # return multiplicative factor


def project_minutes(role, df, b2b, spread=None, injury_minutes_override=None):
    if injury_minutes_override is not None:
        return float(injury_minutes_override)
    if not df.empty:
        clean = df.sort_values("game_date")
        # Task #4: cap raw minutes at OT_MIN_CAP before EWMA so OT games
        # (player_min > 44) don't inflate the minutes baseline for future games.
        min_series = clean["min"].clip(upper=OT_MIN_CAP)
        ewma_min = float(min_series.ewm(span=EWMA_SPAN_MIN, min_periods=1).mean().iloc[-1])
        weight = min(len(clean) / 20.0, 1.0)
    else:
        ewma_min = ROLE_MINUTE_PRIOR[role]
        weight   = 0.0
    prior    = ROLE_MINUTE_PRIOR[role]
    proj_min = weight * ewma_min + (1 - weight) * prior

    # Days-rest reduction: continuous variable replaces binary B2B flag (Brief P3, Sec. 6b).
    # Exponential decay from max reduction (B2B) toward full recovery.
    days_rest = b2b.get("days_rest", 3)  # default 3 if missing
    rest_factor = _compute_days_rest_reduction(days_rest, role)
    proj_min *= rest_factor

    if spread is not None and abs(spread) > 0:
        # Sigmoid blowout reduction — continuous, centred at BLOWOUT_SIGMOID_MID.
        # Only material when |spread| > ~8; negligible for close games.
        reduction = BLOWOUT_MAX_REDUCTION / (
            1.0 + math.exp(-BLOWOUT_SIGMOID_K * (abs(spread) - BLOWOUT_SIGMOID_MID))
        )
        proj_min *= (1.0 - reduction)
    proj_min = max(proj_min, 0.0)
    proj_min = min(proj_min, 42.0 if role == "starter" else 38.0)
    return proj_min

def compute_distribution(mean, stat, role, n_games):
    # Empirical game-level CVs (SD/mean). Calibrated 2026-05-01 against NBA player-game
    # distributions. REB/AST/BLK were systematically underestimated — corrected here.
    # BLK CV elevated to 1.00: high-variance count stat with overdispersion (CV > 1 is
    # common for low-mean counts). Prior CVs caused edge calculations to be too optimistic.
    _CV = {"pts": 0.35, "reb": 0.50, "ast": 0.55, "fg3m": 0.65, "stl": 0.80, "blk": 1.00, "tov": 0.55}
    cv          = _CV.get(stat, 0.50)
    uncertainty = 1.0 + max(0, (20 - n_games) / 40.0)
    std         = mean * cv * uncertainty
    p25         = max(0.0, mean - 0.674 * std)
    p75         = mean + 0.674 * std
    return round(p25, 2), round(mean, 2), round(p75, 2)

def project_player(
    player_id, player_name, position, team_id, opp_team_id,
    game_id, game_date, season=CURRENT_SEASON,
    season_type="Regular Season",
    implied_total=None, spread=None, injury_status="",
    injury_minutes_override=None, is_home=None, db_path=DB_PATH,
):
    if injury_status in ("O", "OUT"):
        return None

    df            = get_player_recent_games(player_id, game_date, n_games=30,
                                            season_filter=season, db_path=db_path)
    games_on_team = get_player_season_game_count(player_id, season, team_id, db_path)
    b2b           = get_player_b2b_context(player_id, game_date, db_path)
    # Q8.7 — cold-start trade archetype blending.  Detect if player changed teams
    # this season and is within the 6-game blend window.  Returns None when outside
    # blend window or no trade detected.
    trade_ctx = get_player_trade_context(player_id, season, team_id, game_date, db_path)

    # L4 — availability weighting: down-weight games where key teammates were
    # absent (vacancy games inflate rates for backups, deflate for stars sharing load).
    # Computed early so it can be passed to all rate functions below.
    avail_weights = compute_availability_weights(
        df, player_id, team_id, season, game_date, db_path
    )

    is_cold_start = games_on_team < MIN_GAMES_FOR_TIER
    if is_cold_start:
        role     = "cold_start"
        rates    = cold_start_rates(position)
        rates    = {k: v / 36.0 for k, v in rates.items()}
        df_clean = df
    else:
        role = classify_role(df)

        # Injury role promotion: backup absorbing star minutes gets promoted so
        # the min_minutes filter and prior both reflect the elevated duty.
        if injury_minutes_override is not None and not df.empty:
            ewma_baseline = float(
                df.sort_values("game_date")["min"]
                  .ewm(span=EWMA_SPAN_MIN, min_periods=1).mean().iloc[-1]
            )
            override_delta = injury_minutes_override - ewma_baseline
            if override_delta >= 6.0 and role == "spot":
                role = "rotation"
            elif override_delta >= 6.0 and role == "rotation":
                role = "sixth_man"
            elif override_delta >= 8.0 and role == "sixth_man":
                role = "starter"

        min_min  = _ROLE_MIN_MINUTES[role]
        df_clean = df[df["min"] >= min_min].copy()
        rates    = compute_per_minute_rates(df_clean, avail_weights=avail_weights)

    proj_min = project_minutes(role, df_clean, b2b, spread=spread,
                               injury_minutes_override=injury_minutes_override)
    if proj_min < 1.0:
        return None

    is_playoff  = season_type == "Playoffs"
    if is_playoff:
        proj_min = round(proj_min * PLAYOFF_MINUTES_SCALAR.get(role, 1.0), 2)
    else:
        proj_min = round(proj_min * REGULAR_SEASON_MINUTES_SCALAR.get(role, 1.0), 2)
    # Always use Regular Season pace data (reliable); playoff pace DB entries
    # are often missing, causing the fallback (99.5) to inflate projections.
    # Playoff adjustment is handled by PLAYOFF_DEFLATOR below instead.
    team_pace   = get_team_pace(team_id,     season, "Regular Season", db_path)
    opp_pace    = get_team_pace(opp_team_id, season, "Regular Season", db_path)
    game_pace   = (team_pace + opp_pace) / 2.0
    _base_pf    = game_pace / LEAGUE_AVG_PACE
    if implied_total is not None and implied_total > 0:
        _base_pf = implied_total / LEAGUE_AVG_TOTAL

    # Per-stat pace factors using non-linear elasticity (Q8.4, Research Brief 5).
    # Formula: pace_X = base_pf^e * LEAGUE_AVG^(1-e) preserves absolute value at
    # league-average pace regardless of exponent.  Deviations are dampened by e.
    _e_pts  = PACE_ELASTICITY["pts"]
    _e_fg3m = PACE_ELASTICITY["fg3m"]
    _e_reb  = PACE_ELASTICITY["reb"]
    _e_ast  = PACE_ELASTICITY["ast"]
    _e_stl  = PACE_ELASTICITY["stl"]
    pace_factor     = _base_pf ** _e_pts   # PTS FGA-decomp path
    pace_fg3m       = _base_pf ** _e_fg3m  # 3PM FGA-decomp path (separate)
    pace_reb        = _base_pf ** _e_reb   # REB availability scalar
    # AST/STL/BLK use proj_poss = game_pace^e * LEAGUE_AVG^(1-e) * min/48
    _proj_poss_ast  = (game_pace ** _e_ast  * LEAGUE_AVG_PACE ** (1.0 - _e_ast)
                       * 1.0)              # multiplied by proj_min/48 below
    _proj_poss_stl  = (game_pace ** _e_stl  * LEAGUE_AVG_PACE ** (1.0 - _e_stl)
                       * 1.0)              # multiplied by proj_min/48 below

    pg = _pos_group(position)
    matchup_pts = float(np.clip(
        get_team_def_ratio(opp_team_id, pg, "pts", season, db_path), *MATCHUP_CLIP))
    matchup_reb = float(np.clip(
        get_team_def_ratio(opp_team_id, pg, "reb", season, db_path), *MATCHUP_CLIP))
    matchup_ast = float(np.clip(
        get_team_def_ratio(opp_team_id, pg, "ast", season, db_path), *MATCHUP_CLIP))

    # P3 — fg3m DvP: use opponent 3PM-allowed ratio instead of piggybacking PTS DvP.
    # team_def_splits already computes fg3m ratios (fg3m is in _DEF_STATS).
    # PTS DvP conflated 2P and 3P defense; a team can be stingy inside but leaky from 3.
    matchup_fg3m = float(np.clip(
        get_team_def_ratio(opp_team_id, pg, "fg3m", season, db_path), *MATCHUP_CLIP))

    # P6 — STL DvP: opponents with high TOV rates create more steal opportunities.
    # opp_tov_rate = opp team's TOV / possession. Normalised by league average.
    opp_tov_rate  = get_team_tov_rate(opp_team_id, season, db_path)
    matchup_stl   = float(np.clip(opp_tov_rate / LEAGUE_AVG_TOV_RATE, *MATCHUP_CLIP))

    # P7 — BLK DvP: opponents who attack the paint more give rim protectors more chances.
    # Proxy: opponent non-3pt FGA per game (fga - fg3a). Normalised by league average.
    opp_rim_rate  = get_team_rim_attempt_rate(opp_team_id, season, db_path)
    matchup_blk   = float(np.clip(opp_rim_rate / LEAGUE_AVG_RIM_ATTEMPT_RATE, *MATCHUP_CLIP))

    matchup_factors = {
        "pts": matchup_pts, "reb": matchup_reb, "ast": matchup_ast,
        "fg3m": matchup_fg3m, "stl": matchup_stl, "blk": matchup_blk, "tov": 1.0,
    }

    # --- Team shooting stats for REB decomposition ---
    team_shoot    = get_team_shooting_stats(team_id,     season, db_path)
    opp_shoot     = get_team_shooting_stats(opp_team_id, season, db_path)
    # Own misses = OREB pool; opp misses = DREB pool
    avail_oreb_pg = team_shoot["fga_per_game"] * (1.0 - team_shoot["fg_pct"])
    avail_dreb_pg = opp_shoot["fga_per_game"]  * (1.0 - opp_shoot["fg_pct"])

    # --- Shooting efficiency rates for 2P%/3P% decomposition ---
    shoot         = compute_shooting_rates(df_clean)
    fg2_pct       = shoot["fg2_pct"]
    fg3_pct       = shoot["fg3_pct"]
    fg3a_rate     = shoot["fg3a_rate"]        # fraction of FGA that are 3PA
    ft_pct        = shoot["ft_pct"]
    fta_fga_ratio = shoot["fta_fga_ratio"]
    usg_pct       = shoot["usg_pct"]          # percentage, e.g. 22.5

    projections = {}

    # PTS: 2P% / 3P% decomposition
    #   team_proj_fga   = historical team FGA scaled by pace
    #   player_proj_fga = player's usage share × team FGA × minutes fraction
    #   player_proj_3pa = fg3a_rate × player_proj_fga
    #   player_proj_2pa = (1 - fg3a_rate) × player_proj_fga
    #   player_proj_fta = fta_fga_ratio × player_proj_fga
    #   proj_pts        = 2PA×2×fg2% + 3PA×3×fg3% + FTA×ft%
    #
    #   2P% and 3P% use Bayesian padding (300 / 750 FGA) to stabilise noisy
    #   per-game rates — replaces composite eFG% which conflated two
    #   distributions with different stabilisation timescales.
    team_avg_fga    = get_team_avg_fga(team_id, game_date, season, db_path=db_path)
    team_proj_fga   = team_avg_fga * pace_factor
    player_proj_fga = (usg_pct / 100.0) * team_proj_fga * (proj_min / 48.0)
    player_proj_3pa = fg3a_rate * player_proj_fga
    player_proj_2pa = (1.0 - fg3a_rate) * player_proj_fga
    player_proj_fta = fta_fga_ratio * player_proj_fga
    proj_pts        = (player_proj_2pa * 2.0 * fg2_pct
                       + player_proj_3pa * 3.0 * fg3_pct
                       + player_proj_fta * ft_pct)
    # DvP matchup adjustment for pts — enabled Apr 30 2026.
    # team_def_splits verified: avg ratio ≈ 1.000, range [0.87, 1.19], data clean.
    proj_pts_fga = proj_pts * matchup_pts  # FGA-decomposition path, DvP-adjusted

    # Ensemble blend with per-minute baseline.
    # PTS_BLEND_ALPHA / BLEND_BIAS_CORRECTION are module-level constants;
    # re-fit via: python engine/evaluate_projector.py --grid-search-alpha
    baseline_pts     = rates.get("pts", 0.0) * proj_min
    proj_pts_blended = (PTS_BLEND_ALPHA * proj_pts_fga
                        + (1.0 - PTS_BLEND_ALPHA) * baseline_pts
                        + BLEND_BIAS_CORRECTION)
    projections["pts"] = max(0.0, round(proj_pts_blended, 2))

    # 3PM — extracted from FGA decomposition (Sec. 4a, Brief 3).
    # Q8.4: Uses separate pace_fg3m (^0.78) rather than pace_factor (^0.90).
    # Rationale: 3PM rate is partially shot-selection (pace-insensitive) and
    # partially volume (pace-sensitive) — empirical elasticity is lower than PTS.
    # DvP: matchup_fg3m uses the opponent's actual 3PM-allowed ratio from
    # team_def_splits — decoupled from PTS DvP (P3, 2026-05-01).
    team_proj_fga_3pm   = team_avg_fga * pace_fg3m
    player_proj_fga_3pm = (usg_pct / 100.0) * team_proj_fga_3pm * (proj_min / 48.0)
    player_proj_3pa_3pm = fg3a_rate * player_proj_fga_3pm
    proj_fg3m_fga  = player_proj_3pa_3pm * fg3_pct * matchup_fg3m
    baseline_fg3m  = rates.get("fg3m", 0.0) * proj_min
    # FG3M_BLEND_ALPHA: FGA path has lower bias, per-min has lower variance.
    # Re-evaluate once 3PM grid search is run (module-level constant).
    projections["fg3m"] = max(0.0, round(
        FG3M_BLEND_ALPHA * proj_fg3m_fga + (1.0 - FG3M_BLEND_ALPHA) * baseline_fg3m, 2
    ))

    # REB: OREB/DREB decomposition (Brief P3, Sec. 2).
    # Q8.4: pace_reb (^0.25) applied to availability — rebound opportunities per
    # possession are nearly constant; pace sensitivity is weak.
    # Separate rates for OREB and DREB — different stabilisation timescales
    # and different contextual drivers (OREB = own-miss recovery; DREB = opp-miss recovery).
    oreb_rate, dreb_rate = compute_reb_rates(df_clean, avail_oreb_pg, avail_dreb_pg, pg,
                                             avail_weights=avail_weights)
    proj_oreb       = oreb_rate * avail_oreb_pg * (proj_min / 48.0) * pace_reb
    proj_dreb       = dreb_rate * avail_dreb_pg * (proj_min / 48.0) * pace_reb
    proj_reb_custom = (proj_oreb + proj_dreb) * matchup_reb   # DvP [0.80, 1.20]
    baseline_reb    = rates.get("reb", 0.0) * proj_min
    proj_reb        = REB_ALPHA * proj_reb_custom + (1.0 - REB_ALPHA) * baseline_reb
    projections["reb"] = max(0.0, round(proj_reb, 2))

    # AST: per-possession rate decomposition (Brief P3, Sec. 3).
    # Rate normalised by team possessions — avoids over-normalising via FGA.
    # Position-conditional EWMA span + Bayesian shrinkage (non-PGs volatile).
    # game_pace = (team_pace + opp_pace) / 2 — incorporates opponent tempo.
    ast_rate        = compute_ast_rate(df_clean, team_pace, pg, avail_weights=avail_weights)
    # Q8.4: AST uses pace^0.50 elasticity. Formula: game_pace^e × LEAGUE_AVG^(1-e)
    # preserves the absolute possession count at league-average pace for any e.
    proj_poss_ast   = _proj_poss_ast * proj_min / 48.0
    proj_ast_custom = ast_rate * proj_poss_ast * matchup_ast  # DvP [0.80, 1.20]
    baseline_ast    = rates.get("ast", 0.0) * proj_min
    proj_ast        = AST_ALPHA * proj_ast_custom + (1.0 - AST_ALPHA) * baseline_ast
    projections["ast"] = max(0.0, round(proj_ast, 2))

    # STL/BLK: per-possession rates × proj_poss × DvP matchup (P5, P6, P7).
    # Q8.4: STL/BLK use pace^0.30 elasticity — defensive actions are largely
    #   independent of tempo; faster games don't proportionally create more steals.
    # STL DvP (P6): opponents with high TOV rates create more steal opportunities.
    # BLK DvP (P7): opponents who attack the paint more give rim protectors more chances.
    proj_poss_stl   = _proj_poss_stl * proj_min / 48.0
    stl_rate, blk_rate = compute_stl_blk_rates(df_clean, pg, team_pace,
                                                avail_weights=avail_weights)
    projections["stl"] = max(0.0, round(stl_rate * proj_poss_stl * matchup_stl, 2))
    projections["blk"] = max(0.0, round(blk_rate * proj_poss_stl * matchup_blk, 2))

    # TOV: per-possession rate (P5). Use linear game_pace (TOV scales proportionally
    # with possessions — turnovers are directly possession-limited).
    proj_poss_tov   = game_pace * proj_min / 48.0
    tov_rate = compute_tov_rate(df_clean, team_pace, pg, avail_weights=avail_weights)
    projections["tov"] = max(0.0, round(tov_rate * proj_poss_tov, 2))

    # Q8.7 — trade archetype blending.
    # When a player has 1-6 games on the new team, blend their prior-team per-minute
    # rates with the new-team projections already computed above.
    #   games 1-3 → α = 0.60 (heavier weight on prior-team role)
    #   games 4-6 → α = 0.40 (new team increasingly dominant)
    # Rationale: the new-team projections may be biased by cold-start archetype rates
    # (games 1-4) or a small sample.  The prior team gives a better estimate of the
    # player's true per-minute production, which transfers across teams.
    if trade_ctx is not None:
        _gnew = trade_ctx["games_on_new_team"]      # 1..6
        _alpha = 0.60 if _gnew <= 3 else 0.40       # prior-team weight
        _prior_rates = compute_per_minute_rates(trade_ctx["prev_team_df"])
        if _prior_rates:
            for _stat in ("pts", "fg3m", "reb", "ast", "stl", "blk", "tov"):
                _prior_proj  = _prior_rates.get(_stat, 0.0) * proj_min
                projections[_stat] = max(0.0, round(
                    _alpha * _prior_proj + (1.0 - _alpha) * projections[_stat], 2
                ))
            log.debug(
                "Q8.7 trade blend %s (pid=%s): gnew=%d alpha=%.2f prev_team=%s",
                player_name, player_id, _gnew, _alpha, trade_ctx["prev_team_id"],
            )

    # P11 — Home/away adjustment.
    # Applied after all DvP / pace / blend logic so it acts as a final scalar.
    # is_home=None means venue unknown (e.g. neutral site or missing data) — skip.
    if is_home is not None:
        sign = 1.0 if is_home else -1.0
        for stat, delta in _HOME_AWAY_DELTA.items():
            if stat in projections:
                projections[stat] = max(0.0, round(
                    projections[stat] * (1.0 + sign * delta), 2))

    # Playoff calibration P18-v4 (2026-05-02):
    # Minutes scalar already applied to proj_min above — all stats benefit.
    # Residual rate deflators applied only for AST and FG3M (genuine playoff rate drops).
    if is_playoff:
        for stat, defl in PLAYOFF_RATE_DEFLATORS.items():
            if stat in projections:
                projections[stat] = round(projections[stat] * defl, 2)

    n_games = len(df_clean)
    pts_p25,  pts_med,  pts_p75  = compute_distribution(projections["pts"],  "pts",  role, n_games)
    reb_p25,  reb_med,  reb_p75  = compute_distribution(projections["reb"],  "reb",  role, n_games)
    ast_p25,  ast_med,  ast_p75  = compute_distribution(projections["ast"],  "ast",  role, n_games)
    fg3m_p25, fg3m_med, fg3m_p75 = compute_distribution(projections["fg3m"], "fg3m", role, n_games)

    dk_std = round(projections["pts"] * DK_STD_COEFF, 2)
    run_ts = datetime.datetime.utcnow().isoformat(timespec="seconds")

    return {
        "run_date": game_date, "run_ts": run_ts,
        "player_id": player_id, "player_name": player_name,
        "team_id": team_id, "opp_team_id": opp_team_id, "game_id": game_id,
        "role_tier": role,
        "proj_min":  round(proj_min, 2),
        "proj_pts":  pts_med,  "proj_pts_p25":  pts_p25,  "proj_pts_p75":  pts_p75,
        "proj_reb":  reb_med,  "proj_reb_p25":  reb_p25,  "proj_reb_p75":  reb_p75,
        "proj_ast":  ast_med,  "proj_ast_p25":  ast_p25,  "proj_ast_p75":  ast_p75,
        "proj_fg3m": fg3m_med, "proj_fg3m_p25": fg3m_p25, "proj_fg3m_p75": fg3m_p75,
        "proj_stl":  projections["stl"],
        "proj_blk":  projections["blk"],
        "proj_tov":  projections["tov"],
        "injury_status": injury_status,
        "pace_factor":        round(pace_factor, 4),
        "matchup_factor_pts": round(matchup_pts, 4),
        "matchup_factor_reb": round(matchup_reb, 4),
        "matchup_factor_ast": round(matchup_ast, 4),
        "is_home": is_home,
        "source": "custom_v1",
        "dk_std": dk_std,
    }

def run_projections(
    game_date, season=CURRENT_SEASON,
    implied_totals=None, spreads=None,
    injury_statuses=None, injury_minutes_overrides=None,
    db_path=DB_PATH, persist=True,
):
    implied_totals           = implied_totals or {}
    spreads                  = spreads or {}
    injury_statuses          = injury_statuses or {}
    injury_minutes_overrides = injury_minutes_overrides or {}

    games = get_games_for_date(game_date, db_path)
    if games.empty:
        log.warning("No games found for %s", game_date)
        return []

    game_implied    = {}
    game_spread     = {}
    game_season_type = {}
    team_to_game    = {}
    home_team_ids   = set()   # P11 — track which team_ids are the home side

    for _, g in games.iterrows():
        gid = str(g["game_id"])
        ht  = int(g["home_team_id"])
        at  = int(g["away_team_id"])
        team_to_game[ht] = (gid, at)
        team_to_game[at] = (gid, ht)
        home_team_ids.add(ht)
        if gid in implied_totals: game_implied[gid] = implied_totals[gid]
        if gid in spreads:        game_spread[gid]  = spreads[gid]
        game_season_type[gid] = g.get("season_type", "Regular Season") or "Regular Season"

    active = get_all_active_players(game_date, min_recent_games=2, db_path=db_path)
    active = active[active["team_id"].isin(team_to_game.keys())]

    log.info("Projecting %d players for %s ...", len(active), game_date)
    results = []
    conn = get_conn(db_path) if persist else None

    for _, row in active.iterrows():
        pid     = int(row["player_id"])
        team_id = int(row["team_id"])
        if team_id not in team_to_game: continue
        game_id, opp_team_id = team_to_game[team_id]
        status = injury_statuses.get(pid, "")
        if status in ("O", "OUT"): continue
        try:
            proj = project_player(
                player_id=pid, player_name=row["name"],
                position=row.get("position"),
                team_id=team_id, opp_team_id=opp_team_id,
                game_id=game_id, game_date=game_date, season=season,
                season_type=game_season_type.get(game_id, "Regular Season"),
                implied_total=game_implied.get(game_id),
                spread=game_spread.get(game_id),
                injury_status=status,
                injury_minutes_override=injury_minutes_overrides.get(pid),
                is_home=(team_id in home_team_ids),
                db_path=db_path,
            )
        except Exception as exc:
            log.debug("project_player error %s (%d): %s", row["name"], pid, exc)
            continue
        if proj is None: continue
        results.append(proj)
        if persist and conn is not None:
            try:   upsert_projection(conn, proj)
            except Exception as exc:
                log.debug("upsert error %d: %s", pid, exc)

    if persist and conn is not None:
        conn.commit(); conn.close()

    # Task #5: 240-minute team constraint — scale team proj_min totals to ≤ 240.
    _SCALE_KEYS = ["proj_pts", "proj_reb", "proj_ast", "proj_fg3m",
                   "proj_blk", "proj_stl", "proj_tov"]
    from collections import defaultdict as _dd
    _by_team = _dd(list)
    for p in results:
        _by_team[p.get("team_id")].append(p)
    for tid, tprojs in _by_team.items():
        total_min = sum(p.get("proj_min", 0.0) for p in tprojs)
        if total_min < TEAM_MIN_FLOOR or total_min <= TEAM_MIN_TARGET:
            continue
        scale = TEAM_MIN_TARGET / total_min
        for p in tprojs:
            p["proj_min"] = round(p.get("proj_min", 0.0) * scale, 2)
            for k in _SCALE_KEYS:
                if k in p:
                    p[k] = round(p[k] * scale, 2)
        log.debug("Team %s: 240-min constraint scaled %d players "
                  "(%.1f -> 240.0 min, factor=%.4f)", tid, len(tprojs), total_min, scale)

    log.info("Projections complete: %d players", len(results))
    return results

def _main():
    import argparse
    parser = argparse.ArgumentParser(description="Run NBA projections for a date")
    parser.add_argument("--date",   default=str(datetime.date.today()))
    parser.add_argument("--season", default=CURRENT_SEASON)
    parser.add_argument("--db",     default=DB_PATH)
    parser.add_argument("--no-persist", action="store_true")
    parser.add_argument("--top",    type=int, default=20)
    args = parser.parse_args()

    results = run_projections(
        game_date=args.date, season=args.season,
        db_path=args.db, persist=not args.no_persist,
    )
    if not results:
        print("No projections generated.")
        return

    df   = pd.DataFrame(results).sort_values("proj_pts", ascending=False)
    cols = ["player_name", "role_tier", "proj_min", "proj_pts",
            "proj_reb", "proj_ast", "proj_fg3m", "pace_factor",
            "matchup_factor_pts", "injury_status"]
    print(df[cols].head(args.top).to_string(index=False))
    print(f"\nTotal: {len(df)} players projected.")

if __name__ == "__main__":
    _main()
