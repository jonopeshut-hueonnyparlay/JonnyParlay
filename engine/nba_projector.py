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

REB/AST/STL/BLK/TOV: per-possession rates x proj_poss x matchup_factor
    proj_poss = game_pace * proj_min / 48  (pace embedded — no separate pace_factor)
    PTS/FG3M still use FGA-decomp path where pace_factor scales team_proj_fga.

Role tiers: starter / sixth_man / rotation / spot / cold_start
EWMA span=10 for all rolling rates. Cold-start (<5 games on team) -> archetype prior.
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
EWMA_SPAN         = 10   # shooting/per-min rates — longer span for stability
EWMA_SPAN_MIN     = 5    # minutes projection — shorter span; more responsive to role changes
MIN_GAMES_FOR_TIER = 5

USG_ROLE_PRIOR = {
    "starter": 24.0, "sixth_man": 20.0, "rotation": 16.0,
    "spot": 13.0,    "cold_start": 20.0,
}

ROLE_MINUTE_PRIOR = {
    "starter": 32.0, "sixth_man": 24.0, "rotation": 19.0,
    "spot": 14.0, "cold_start": 15.0,
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
# Positional priors calibrated from 2024-25 NBA averages.
_REB_POS_OREB_PRIOR = {"G": 0.022, "F": 0.044, "C": 0.078}   # OREB per team miss/48
_REB_POS_DREB_PRIOR = {"G": 0.078, "F": 0.133, "C": 0.200}   # DREB per opp miss/48
_REB_PRIOR_N_OREB   = 20   # shrinkage weight ≈ 20-game sample
_REB_PRIOR_N_DREB   = 28   # stabilises slower — stronger shrinkage
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
_AST_PRIOR_N   = {"G":  22,  "F":  32,    "C":  35}    # shrinkage weight (games equivalent)
AST_ALPHA      = 0.40   # lean toward baseline until rates stabilise over longer sample
FG3M_BLEND_ALPHA = 0.50  # weight on FGA-decomp path for 3PM; re-evaluate after grid search

# STL/BLK Bayesian shrinkage priors (Brief P3, Sec. 5 — 2026-05-01).
# P5 (2026-05-01): STL/BLK/TOV priors restated in per-POSSESSION units.
# Conversion: prior_per_poss = prior_per_min * (48 / LEAGUE_AVG_PACE) = prior_per_min * 0.4824
# compute_stl_blk_rates() and compute_tov_rate() now normalise training data by
# (team_pace * min / 48) — matching the per-possession basis used by compute_ast_rate().
# Projection: rate_per_poss * proj_poss * matchup  (pace_factor multiplier removed).
_STL_POS_PRIOR = {"G": 0.01606, "F": 0.01206, "C": 0.00936}  # STL per possession
_STL_PRIOR_N   = 25  # shrinkage weight — STL is noisy, strong prior needed

# BLK priors: centers split into non-blockers (C_low) and rim protectors (C_high).
# Classification still uses career BLK/min vs _BLK_CENTER_SPLIT_THRESHOLD (per-minute
# threshold unchanged — classification is independent of the rate training basis).
_BLK_CENTER_SPLIT_THRESHOLD = 0.030   # BLK/min cutoff for center classification (per-minute)
_BLK_POS_PRIOR = {
    "G":      0.00400,  # guards      — 0.0083/min * 0.4824
    "F":      0.00806,  # forwards    — 0.0167/min * 0.4824
    "C_low":  0.00965,  # non-blockers — 0.020/min * 0.4824
    "C_high": 0.03618,  # rim protectors — 0.075/min * 0.4824
}
_BLK_PRIOR_N = {
    "G":     30,   # strong shrinkage — BLK noisy for non-centers
    "F":     30,
    "C_low": 20,   # near-zero rate is stable; lighter shrinkage sufficient
    "C_high": 25,  # rim-protection varies by matchup; moderate shrinkage
}

# TOV per-possession priors — derived from per-36 archetypes / LEAGUE_AVG_PACE * 48.
_TOV_POS_PRIOR = {"G": 0.0335, "F": 0.0241, "C": 0.0268}
_TOV_PRIOR_N   = 20  # moderate shrinkage; TOV rate is relatively stable

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

def compute_per_minute_rates(df):
    if df.empty: return {s: 0.0 for s in PROJ_STATS}
    d = df.sort_values("game_date").copy()
    if d.empty: return {s: 0.0 for s in PROJ_STATS}
    rates = {}
    for stat in PROJ_STATS:
        if stat not in d.columns:
            rates[stat] = 0.0; continue
        per_min  = d[stat] / d["min"]
        weighted = per_min * d["era_weight"]
        ewma_w   = weighted.ewm(span=EWMA_SPAN, min_periods=1).mean().iloc[-1]
        ewma_e   = d["era_weight"].ewm(span=EWMA_SPAN, min_periods=1).mean().iloc[-1]
        rates[stat] = float(ewma_w / max(ewma_e, 1e-6))
    return rates

def compute_reb_rates(df_clean: pd.DataFrame,
                      avail_oreb_per_game: float,
                      avail_dreb_per_game: float,
                      pos_group: str) -> tuple[float, float]:
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

    oreb_ewma = float(oreb_raw.ewm(span=EWMA_SPAN, min_periods=1).mean().iloc[-1])
    dreb_ewma = float(dreb_raw.ewm(span=EWMA_SPAN, min_periods=1).mean().iloc[-1])

    # Bayesian shrinkage: (observed_n * ewma + prior_n * prior) / (observed_n + prior_n)
    oreb_rate = (n_games * oreb_ewma + _REB_PRIOR_N_OREB * oreb_prior) / (n_games + _REB_PRIOR_N_OREB)
    dreb_rate = (n_games * dreb_ewma + _REB_PRIOR_N_DREB * dreb_prior) / (n_games + _REB_PRIOR_N_DREB)
    return float(oreb_rate), float(dreb_rate)


def compute_ast_rate(df_clean: pd.DataFrame,
                     team_pace: float,
                     pos_group: str) -> float:
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

    ast_ewma = float(ast_raw.ewm(span=span, min_periods=1).mean().iloc[-1])

    # Bayesian shrinkage to positional prior
    ast_rate = (n_games * ast_ewma + prior_n * prior) / (n_games + prior_n)
    return float(ast_rate)


def compute_stl_blk_rates(df_clean: pd.DataFrame,
                           pos_group: str,
                           team_pace: float) -> tuple[float, float]:
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
    blk_prior_n = _BLK_PRIOR_N.get(blk_key, 30)

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

    stl_ewma = float(stl_raw.ewm(span=EWMA_SPAN, min_periods=1).mean().iloc[-1])
    blk_ewma = float(blk_raw.ewm(span=EWMA_SPAN, min_periods=1).mean().iloc[-1])

    # Bayesian shrinkage — BLK uses the resolved prior and N for this player's archetype
    stl_rate = (n_games * stl_ewma + _STL_PRIOR_N * stl_prior) / (n_games + _STL_PRIOR_N)
    blk_rate = (n_games * blk_ewma + blk_prior_n * blk_prior) / (n_games + blk_prior_n)
    return float(stl_rate), float(blk_rate)


def compute_tov_rate(df_clean: pd.DataFrame,
                     team_pace: float,
                     pos_group: str) -> float:
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

    tov_ewma = float(tov_raw.ewm(span=EWMA_SPAN, min_periods=1).mean().iloc[-1])
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
    fg3a_rate  = float(fg3a_vals.ewm(span=EWMA_SPAN, min_periods=1).mean().iloc[-1])
    fg3a_rate  = float(np.clip(fg3a_rate, 0.0, 0.85))

    # ------------------------------------------------------------------ #
    # FT% — EWMA                                                           #
    # ------------------------------------------------------------------ #
    mask_fta  = d["fta"] > 0
    ft_series = np.where(mask_fta, d["ftm"] / d["fta"], np.nan)
    ft_vals   = pd.Series(ft_series).ffill().fillna(LG_FT_PCT)
    ft_pct    = float(ft_vals.ewm(span=EWMA_SPAN, min_periods=1).mean().iloc[-1])
    ft_pct    = float(np.clip(ft_pct, 0.40, 1.00))

    # ------------------------------------------------------------------ #
    # FTA/FGA ratio                                                        #
    # ------------------------------------------------------------------ #
    ratio_series  = np.where(mask_fga, d["fta"] / d["fga"], np.nan)
    ratio_vals    = pd.Series(ratio_series).ffill().fillna(LG_FTA_FGA)
    fta_fga_ratio = float(ratio_vals.ewm(span=EWMA_SPAN, min_periods=1).mean().iloc[-1])
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
        usg_pct  = float(usg_vals.ewm(span=EWMA_SPAN, min_periods=1).mean().iloc[-1])
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
        ewma_min = float(clean["min"].ewm(span=EWMA_SPAN_MIN, min_periods=1).mean().iloc[-1])
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
                  .ewm(span=EWMA_SPAN, min_periods=1).mean().iloc[-1]
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
        rates    = compute_per_minute_rates(df_clean)

    proj_min = project_minutes(role, df_clean, b2b, spread=spread,
                               injury_minutes_override=injury_minutes_override)
    if proj_min < 1.0:
        return None

    is_playoff  = season_type == "Playoffs"
    # Always use Regular Season pace data (reliable); playoff pace DB entries
    # are often missing, causing the fallback (99.5) to inflate projections.
    # Playoff adjustment is handled by PLAYOFF_DEFLATOR below instead.
    team_pace   = get_team_pace(team_id,     season, "Regular Season", db_path)
    opp_pace    = get_team_pace(opp_team_id, season, "Regular Season", db_path)
    game_pace   = (team_pace + opp_pace) / 2.0
    pace_factor = game_pace / LEAGUE_AVG_PACE
    if implied_total is not None and implied_total > 0:
        pace_factor = implied_total / LEAGUE_AVG_TOTAL

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
    # proj_3pa and fg3_pct are already computed above in the PTS path.
    # DvP: matchup_fg3m uses the opponent's actual 3PM-allowed ratio from
    # team_def_splits — decoupled from PTS DvP (P3, 2026-05-01).
    # PTS defense and 3PM defense are empirically distinct: a team can be stingy
    # inside (low PTS DvP) while leaking threes (high fg3m DvP), or vice versa.
    proj_fg3m_fga  = player_proj_3pa * fg3_pct * matchup_fg3m
    baseline_fg3m  = rates.get("fg3m", 0.0) * proj_min
    # FG3M_BLEND_ALPHA: FGA path has lower bias, per-min has lower variance.
    # Re-evaluate once 3PM grid search is run (module-level constant).
    projections["fg3m"] = max(0.0, round(
        FG3M_BLEND_ALPHA * proj_fg3m_fga + (1.0 - FG3M_BLEND_ALPHA) * baseline_fg3m, 2
    ))

    # REB: OREB/DREB decomposition (Brief P3, Sec. 2).
    # Separate rates for OREB and DREB — different stabilisation timescales
    # and different contextual drivers (OREB = own-miss recovery; DREB = opp-miss recovery).
    oreb_rate, dreb_rate = compute_reb_rates(df_clean, avail_oreb_pg, avail_dreb_pg, pg)
    proj_oreb       = oreb_rate * avail_oreb_pg * (proj_min / 48.0)
    proj_dreb       = dreb_rate * avail_dreb_pg * (proj_min / 48.0)
    proj_reb_custom = (proj_oreb + proj_dreb) * matchup_reb   # DvP [0.80, 1.20]
    baseline_reb    = rates.get("reb", 0.0) * proj_min
    proj_reb        = REB_ALPHA * proj_reb_custom + (1.0 - REB_ALPHA) * baseline_reb
    projections["reb"] = max(0.0, round(proj_reb, 2))

    # AST: per-possession rate decomposition (Brief P3, Sec. 3).
    # Rate normalised by team possessions — avoids over-normalising via FGA.
    # Position-conditional EWMA span + Bayesian shrinkage (non-PGs volatile).
    # game_pace = (team_pace + opp_pace) / 2 — incorporates opponent tempo.
    ast_rate        = compute_ast_rate(df_clean, team_pace, pg)
    proj_poss       = game_pace * proj_min / 48.0        # game-specific possessions
    proj_ast_custom = ast_rate * proj_poss * matchup_ast  # DvP [0.80, 1.20]
    baseline_ast    = rates.get("ast", 0.0) * proj_min
    proj_ast        = AST_ALPHA * proj_ast_custom + (1.0 - AST_ALPHA) * baseline_ast
    projections["ast"] = max(0.0, round(proj_ast, 2))

    # STL/BLK: per-possession rates × proj_poss × DvP matchup (P5, P6, P7).
    # P5: training basis is per-possession — pace_factor multiplier removed.
    #     pace effect is already captured via proj_poss = game_pace * proj_min / 48.
    # STL DvP (P6): opponents with high TOV rates create more steal opportunities.
    # BLK DvP (P7): opponents who attack the paint more give rim protectors more chances.
    stl_rate, blk_rate = compute_stl_blk_rates(df_clean, pg, team_pace)
    projections["stl"] = max(0.0, round(stl_rate * proj_poss * matchup_stl, 2))
    projections["blk"] = max(0.0, round(blk_rate * proj_poss * matchup_blk, 2))

    # TOV: per-possession rate (P5) — pace embedded via proj_poss, no pace_factor.
    tov_rate = compute_tov_rate(df_clean, team_pace, pg)
    projections["tov"] = max(0.0, round(tov_rate * proj_poss, 2))

    # P11 — Home/away adjustment.
    # Applied after all DvP / pace / blend logic so it acts as a final scalar.
    # is_home=None means venue unknown (e.g. neutral site or missing data) — skip.
    if is_home is not None:
        sign = 1.0 if is_home else -1.0
        for stat, delta in _HOME_AWAY_DELTA.items():
            if stat in projections:
                projections[stat] = max(0.0, round(
                    projections[stat] * (1.0 + sign * delta), 2))

    # Playoff calibration: regular-season per-minute rates over-project in
    # playoffs due to tighter defense and shorter rotations.
    if is_playoff:
        PLAYOFF_DEFLATOR = 0.92
        for stat in PROJ_STATS:
            projections[stat] = round(projections[stat] * PLAYOFF_DEFLATOR, 2)

    n_games = len(df_clean)
    pts_p25,  pts_med,  pts_p75  = compute_distribution(projections["pts"],  "pts",  role, n_games)
    reb_p25,  reb_med,  reb_p75  = compute_distribution(projections["reb"],  "reb",  role, n_games)
    ast_p25,  ast_med,  ast_p75  = compute_distribution(projections["ast"],  "ast",  role, n_games)
    fg3m_p25, fg3m_med, fg3m_p75 = compute_distribution(projections["fg3m"], "fg3m", role, n_games)

    dk_std = round(projections["pts"] * 0.35, 2)
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
