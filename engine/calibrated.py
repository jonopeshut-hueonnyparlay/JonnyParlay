"""Empirically calibrated / fitted constants for run_picks.py.

Distribution parameters (SIGMA, NB_R, COMBO_RHO, GAME_SIGMA, …), Platt coefficients,
tier routing, shrinkage weights, park factors, and the team-sigma loader's import-time
side effect. Extracted from run_picks.py (extract-and-re-export refactor, Step 10) and
re-imported there so existing call sites and `from run_picks import ...` keep resolving.

Imports only {stdlib, paths, secrets_config} — never run_picks or the other constants
modules. _load_team_sigmas() runs at import and populates _TEAM_SIGMAS / _TEAM_SIGMAS_MEANSQ;
run_picks re-imports those populated dicts (the get_game_sigma* accessors stay in run_picks).
"""
from pathlib import Path

from pricing_core import WNBA_NB_R as _PC_WNBA_NB_R  # WNBA NB-r: shared single source of truth

SIGMA = {
    # NBA / NHL — Normal distribution sigma: σ = max(proj * mult, min)
    # NOTE: SOG/HITS removed — POISSON_STATS takes priority.
    # REB and AST kept here for combo path (_combo_mu_sigma) only:
    #   single-stat REB → NB_STATS (r=13.16); single-stat AST → NB_STATS (r=9.66).  # P1.3
    # Calibrated 2026-05-25 from 84k+ player-games (3 seasons), within-player CV at min>=20.
    "REB": {"mult": 0.48, "min": 2.0},  # was 0.58/2.5 — empirical median CV=0.483 (3-season stable)
    "AST": {"mult": 0.53, "min": 2.0},  # NEW — combo path only; 3-season median CV=0.507; fallback was 0.40/2.0
    # "REC" removed — POISSON_STATS takes priority (REC is in POISSON_STATS); SIGMA["REC"] was unreachable dead code.
    "PTS": {"mult": 0.35, "min": 5.0},  # mult confirmed by MAE backtest (σ≈6.74 at proj=20 → CV=0.337); min raised 4.5→5.0 (MAE by role: spot=5.15, rotation=5.98)
    # "3PM" not here — NB_STATS/NB_R (Negative Binomial, r=9.15). Do NOT add.
    # MLB — calibrated 2026-05-26 from 69k pitcher / 169k batter game logs (2023-2026).
    # "HA" not here — NB_STATS (NB r=50.0, near-Poisson; synced to EdgeModel 2026-07-02).
    # "HRR" not here — NB_STATS (Negative Binomial, r=1.5).
    # "TB" not here — G_TB_DISABLED (structural kill A2 2026-05-22).
    # "HITS" not here — POISSON_STATS takes priority.
    # OUTS/PC recalibrated 2026-06-05 (Plan 6 §1C) on STARTS ONLY (is_starter=1, 16,187 starts,
    # 345 pitchers n>=10). Prior 0.311/0.375 were contaminated by relief appearances (the market
    # prices starters only): within-CV starts-only = 0.228/0.142 vs relief 0.443/0.460.
    "OUTS": {"mult": 0.27, "min": 1.0},   # pooled-start CV=0.276; within=0.228 — 0.27 keeps a left-tail buffer
    "PC":   {"mult": 0.19, "min": 6.0},   # within=0.142, pooled-start=0.204 — 0.19 mid-band; skew −1.93, Normal provisional (empirical-CDF candidate at July refit)
    # NHL goalie — calibrated 2026-05-26 from 15k goalie game-logs (2023-2026), within-player CV=0.253.
    # High-count stat (mean=26.6); Normal is correct (continuous-ish, high-volume).
    "SV":   {"mult": 0.253, "min": 3.5},
    # NFL yardage — Normal. PREDICTION CVs calibrated on the pricing population
    # (players with real projected usage) from a 2024 backtest → SD(z)≈1.0, mean
    # unbiased (EdgeModel feat/nfl-v2 f0aa1db). Mirrors the EdgeModel projector's
    # PASS_CV/RUSH_CV/REC_CV. DATA_GATED: refit at the NFL CLV gate.
    "PASS_YDS": {"mult": 0.36, "min": 35.0},
    "RUSH_YDS": {"mult": 0.62, "min": 14.5},
    "REC_YDS":  {"mult": 0.72, "min": 13.0},
}

# HA removed from Poisson -> NB_STATS. NB r=50.0 (near-Poisson) since the 2026-07-02 EdgeModel sync; the old 13.41 fit was relief-contaminated.
# GOALS, NHLPTS, NHLBLK: NHL skater stats — perfect Poisson (var/mu=0.989, 0.983, 1.081 from 141k skater games)
# RUNS: MLB batter runs — Poisson (var/mu=0.969 from 169k batter games)
# GA: NHL goalie goals against — Poisson (within-player var/mu=0.830 from 15k goalie game-logs; sub-Poisson is fine)
# BB: MLB pitcher walks — Poisson (within-player var/mu=0.992 from 69k pitcher game-logs; Poisson confirmed)
POISSON_STATS = {"SOG", "REC", "HITS", "GOALS", "NHLPTS", "NHLBLK", "RUNS", "GA", "BB",
                 "TDS", "PASS_TDS"}  # AST/REB moved to NB_STATS; REC here makes SIGMA["REC"] unreachable (removed from SIGMA).
# NFL TDS (anytime) / PASS_TDS price as Poisson with the projected lambda as proj:
# P(over 0.5)=1-e^-λ. EdgeModel supplies the lambda (rush+rec for TDS; passing for PASS_TDS).

# P16 — Negative binomial distribution for overdispersed count stats.
# NB(mu, r): var = mu + mu²/r.  r calibrated from within-player conditional variance
# (avg_var / avg_mu per player across 2024-25 DB), NOT population-level cross-player variance.
# Bias-corrected estimator (P1.3, 2026-06-16): r = SUM(n*mu) / SUM(n*(var-mu)/mu)
# (Jensen-corrected pooled MoM). The PRIOR formula SUM(n*mu^2)/SUM(n*(var-mu))
# upweights high-mu players quadratically and INFLATES r for high-mean stats —
# that is why deployed AST/REB sat above what their own var/mu implied.
# Source: EdgeModel engine/calibrate_distributions.py (--sport NBA). Redeploy:
# run it and copy the bias-corrected r values below.
#   3PM: avg(var/mu)=1.1486 (n=1246 player-seasons) -> r=9.15 (near-Poisson; producer now classifies Poisson at var/mu=1.179 — NB kept as the wider/safer choice, flagged)
#   AST: var/mu=1.323 (582 players/69875 logs) -> r=9.66 bias-corrected (was 12.16 from the inflating formula — that implied var/mu~1.24, inconsistent with the stated 1.323)
#   REB: var/mu=1.387 (582 players/69875 logs) -> r=13.16 bias-corrected (was 14.7 from the inflating formula)
#   HRR: r=1.5 calibrated from shadow log: NB(r=1.5, mu=2.0) gives P(X>=2)=47.8% matching empirical 48% WR.
#        Normal was giving 63% for same projection — structural zero-inflation (batter 0-H/R/RBI ~37% of games).
#   HA:  r=13.41 — calibrated 2026-05-26 from 69k pitcher game-logs (2023-2026); within-player var/mu=1.204.
#        Confirmed 2026-05-30 by EdgeModel (56280 game-logs, var/mu=1.2037); no change.
#   RBI: r=0.87 — calibrated 2026-05-26: 169k batter game-logs (2023-2026), within-player var/mu=1.535.
#        Low r means heavy zero-inflation (batters go 0-RBI in ~74% of games) with long right tail.
#   ER:  r=2.62 — calibrated 2026-05-26: 69k pitcher game-logs (2023-2026), within-player var/mu=1.700.
#        Overdispersed relative to Poisson; bullpen usage and run-support create heavy tails.
# STL/BLK/TOV: Poisson confirmed 2026-05-30 (69773 game-logs): var/mu=1.072/1.113/1.050 — all below NB threshold. No move to NB_STATS.
NB_STATS = {"3PM", "HRR", "AST", "REB", "HA", "RBI", "ER", "TB"}
NB_R = {
    "3PM": 9.15,   # recalibrated 2026-05-25: 1246 player-seasons, avg(var/mu)=1.1486 (was 12.3 — too tight)
    "AST": 9.66,   # P1.3 2026-06-16: bias-corrected (Jensen MoM) from EdgeModel producer, var/mu=1.323. Was 12.16 (inflating formula).
    "REB": 13.16,  # P1.3 2026-06-16: bias-corrected (Jensen MoM) from EdgeModel producer, var/mu=1.387. Was 14.7 (inflating formula).
    "HRR": 1.5,    # moment-matched from shadow log: NB(r=1.5, mu=2.0) -> P(X>=2)=47.8% = empirical 48% WR (n=1810). Method differs from var/mu used for NBA stats. Proper refit needs MLB batter game logs (within-player var/mu); zero-inflated NB may be warranted (~37% of games are 0 H/R/RBI).
    "HA":  50.0,   # SYNCED 2026-07-02 to EdgeModel's 06-30 starts-only recal (NB_R_HA=50.0, near-Poisson) — consistent with the 2026-06-16 starts-only flag here (var/mu=0.890 -> ~Poisson; the old 13.41 was relief-contaminated). Market remains SUSPENDED (G_HA_SUSPENDED) so no live reprice; value kept in lockstep per "constants up to date everywhere".
    "RBI": 0.87,   # calibrated 2026-05-26: 169k batter game-logs (2023-2026), within-player var/mu=1.535. r<1 is valid NB; reflects heavy zero-inflation (~74% of games are 0 RBI).
    "ER":  4.75,   # Task#1 2026-06-16: starts-only re-align (is_starter=1, n=370 pitchers / 15,297 starts), var/mu=1.509. Was 2.62 from the relief-inclusive 69k-log fit (var/mu=1.700), which over-disperses starter ER by ~30% (implied var/mu~1.94 at starter mu=2.466). Higher r = thinner tails for the priced (starter) population.
    "TB":  1.6,    # SYNCED 2026-07-02 to EdgeModel's 06-30 recal (TB_R=1.6, within-player re-derivation; was 1.3 from the 2026-05-26 fit). Fallback only — calc_tb_prob() uses component Poisson convolution (1B/2B/3B/HR) when TB_1B available, which is more accurate.
}

# WNBA NB dispersion r — single source: pricing_core.WNBA_NB_R (was a local literal;
# centralised so the JonnyParlay<->EdgeModel lockstep can't drift). Values unchanged:
#   reb/ast calibrated 2026-06-04 (202 players / 13,322 games, 2023-26 WNBA RS, min>=8);
#   3PM(fg3m)=5.0 within-player refit 2026-06-26 (prior 1.342 was pooled/over-dispersed,
#   implied var/mu~1.97, beaten by Poisson; r=5 calibration-optimal on 17k logs). [audit 2026-06]
NB_R_WNBA = {
    "AST": _PC_WNBA_NB_R["ast"],
    "REB": _PC_WNBA_NB_R["reb"],
    "3PM": _PC_WNBA_NB_R["fg3m"],
}

# Combo props: PTS+REB+AST, PTS+REB, PTS+AST, REB+AST
# Projection = sum of individual components. Probability via correlated Normal.
COMBO_STATS = {"PRA", "PR", "PA", "RA"}
COMBO_COMPONENTS = {
    "PRA": ("PTS", "REB", "AST"),
    "PR":  ("PTS", "REB"),
    "PA":  ("PTS", "AST"),
    "RA":  ("REB", "AST"),
}
# Intra-player pairwise ρ — calibrated from 76,960 player-games (595 players,
# n>=20, min>=5) across all seasons in projections.db. Weighted average of
# within-player Pearson correlations; reflects total game-to-game covariance
# including minute variance (correct, since SIGMA already captures total σ).
# Re-verified 2026-05-25 after DB update: all three pairs stable to <0.001.
# Normal approximation validity (min>=20 pop): PRA skew=0.74, PR skew=0.72,
# PA skew=0.80, RA skew=0.94 — all ACCEPTABLE. RA is the most skewed (small
# count stats) but error at typical prop lines is within model uncertainty.
COMBO_RHO = {
    ("PTS", "REB"): 0.333,
    ("PTS", "AST"): 0.233,
    ("REB", "AST"): 0.251,
}

# WNBA-specific sigma (used for G14 z-score proxy and combo sigma).
# Recalibrated 2026-06-05 (Plan 6 §1C) on the PRICED population: min>=20 minutes,
# 153 players n>=10 (2023–2026 RS, EdgeModel projections.db). The prior min>=8 frame
# (PTS 0.618 / AST 0.779 / REB 0.633) was a sampling artifact — median player in that
# frame scores 7.2 PPG and is never actually priced (NBA same-frame check gives 0.615).
# AST/REB use NB for probability (NB_R_WNBA) but Normal sigma here (G14 + combos).
SIGMA_WNBA = {
    "PTS": {"mult": 0.48, "min": 3.5},   # min>=20 median within-CV=0.479
    "AST": {"mult": 0.65, "min": 1.0},   # min>=20 median within-CV=0.650 (was 0.779)
    "REB": {"mult": 0.54, "min": 1.0},   # min>=20 median within-CV=0.537 (was 0.633)
    "3PM": {"mult": 0.48, "min": 0.70},  # z-score/combo proxy only — 3PM probability uses NB (NB_R_WNBA)
}

# WNBA combo correlations — calibrated 2026-06-04 from 202 players / 13,322 games
# (2023–2026 Regular Season, min>=8, n>=10 per player). Within-player weighted
# Pearson; SE≈0.009. All three pairs ~0.04–0.05 below NBA equivalents, consistent
# with slightly lower WNBA pace/usage variance.
COMBO_RHO_WNBA = {
    ("PTS", "REB"): 0.294,
    ("PTS", "AST"): 0.188,
    ("REB", "AST"): 0.200,
}

# MLB Correlation Groups — stats driven by the same hidden variable (IP for pitchers, PA for batters)
# G11/G11b: max 1 prop per player within each correlated group
PITCHER_STATS = {"OUTS", "HA", "ER", "BB", "PC"}  # All functions of IP — r ≈ 0.70+ between OUTS/HA; ER/BB/PC added 2026-05-26

BATTER_CORR_STATS = {"HITS", "TB", "HRR"}           # HITS is component of TB and HRR — r ≈ 0.70+
MLB_CORR_GROUPS = [PITCHER_STATS, BATTER_CORR_STATS]

# P9 — Platt scaling calibration for prop win_prob (2026-05-01).
# Fitted from 76 settled primary/bonus props (NBA + NHL) via Nelder-Mead NLL.
# FORMULA: raw-probability space — sigmoid(PLATT_A * over_p + PLATT_B)
# These coefficients were fitted FOR this formula. Do NOT use them with logit-space.
#
# !! MIGRATION NOTE (2026-05-25): calibrate_platt.py now fits logit-space:
#    i.e. sigmoid(A * logit(over_p) + B)
#    When H3 fires (100 native rows), BOTH of the following must happen together:
#      1. Update _platt_calibrate_prop() below to use logit-space
#      2. Paste new A/B from calibrate_platt.py (they will be different values)
#    Pasting logit-space A/B into the current raw-space formula is WRONG —
#    at over_p=0.75 it would shift output by ~12pp.
#
# Result at fit time: model mean win_prob 0.696 → calibrated 0.579 = actual 0.579.
# Brier improvement: 6.0% (in-sample). H3 gate: 100 native over_p_raw rows.
# PLATT_SPACE (the structural raw/logit flag) lives in thresholds.py.
PLATT_A = 1.4988   # slope  — raw-probability space (not logit-space)
PLATT_B = -0.8102  # intercept — raw-probability space (not logit-space)
# Machine-readable fit date for the deployed PLATT_A/B above (P2.7 freshness
# check). No Platt artifact JSON exists in this repo, so health_check reads this
# constant to warn when the calibration ages past PLATT_MAX_AGE_DAYS. Bump this
# whenever PLATT_A/B are refit (the H3 / calibration-log deploy).
PLATT_FIT_DATE = "2026-05-01"  # ISO; see fit notes above

GAME_SIGMA = {
    # NHL sigmas calibrated 2026-06-05 from 3936 games (2023-24 + 2024-25).
    # total=std(home+away)=2.311; spread=std(home-away)=2.614; team=avg(std(home),std(away))=1.744
    # ml uses spread sigma — P(win) = P(margin > 0) under same goal-differential distribution.
    # Prior values (total=1.2, spread=1.5, ml=4.0) were wrong by ~2x.
    # NBA calibrated 2026-06-05 (Plan 6 §6) from 3,922 reconstructed games (projections.db, 3 seasons):
    #   raw total SD=20.20, raw margin SD=16.04, rho(home,away)=+0.227,
    #   residual SDs vs team-season means: total=19.33, margin=15.27, home=12.23.
    # Deployed values are residual-basis, split toward published around-the-line estimates
    # (total ~18.5; spread/ml ~12.5 per around-the-spread literature; team ~11.0).
    # Prior values (12/12/9/12) were never calibrated — total was ~40% too narrow.
    "NBA":  {"total": 18.5, "spread": 12.5, "team": 11.0,  "ml": 12.5},
    "WNBA": {"total": 17.424, "spread": 10.0, "team": 11.253, "ml": 10.0},  # total+team recalibrated 2026-06-09 (go-live) from 851 games
    "NHL":  {"total": 2.311, "spread": 2.614, "team": 1.744, "ml": 2.614},
    "MLB":  {"total": 4.6,  "spread": 4.2,  "team": 3.0,   "ml": 4.2},  # interim per Plan 10 §O (2026-06-07): total below independence floor (team×√2≈4.4); ml=spread (NHL precedent). Recalibrate from 8095-game DB like NBA/NHL.
}

# Team-specific sigma JSONs — loaded at startup, fallback to GAME_SIGMA league average.
# Generated by: python engine/calibrate_distributions.py --mode team-sigmas --sport all
_TEAM_SIGMAS: dict = {}
# Per-sport mean of score_sigma² across teams (n_games>=20 only) — denominator of the
# relative-variability scaler in get_game_sigma(). 0.0 when no usable team data.
_TEAM_SIGMAS_MEANSQ: dict = {}

def _load_team_sigmas():
    import json as _json
    from market_config import wnba_sigmas_by_abbrev
    _data_dir = Path(__file__).parent.parent / "data"
    for sport, fname in [("NHL", "team_sigmas_nhl.json"), ("MLB", "team_sigmas_mlb.json"),
                         ("NBA", "team_sigmas_nba.json"), ("WNBA", "team_sigmas_wnba.json")]:
        p = _data_dir / fname
        if p.exists():
            data = _json.loads(p.read_text())
            # P0.2: WNBA JSON is keyed by numeric team_id; re-key to abbrev so
            # get_game_sigma (abbrev-keyed) hits instead of falling back to league σ.
            if sport == "WNBA":
                data = wnba_sigmas_by_abbrev(data)
            _TEAM_SIGMAS[sport] = data
            sq = [t["score_sigma"] ** 2 for t in data.values()
                  if isinstance(t, dict) and t.get("score_sigma") and t.get("n_games", 0) >= 20]
            _TEAM_SIGMAS_MEANSQ[sport] = (sum(sq) / len(sq)) if sq else 0.0

_load_team_sigmas()

# Sports where the spread is always a fixed ±1.5 line (MLB runline, NHL puck line).
# The fixed line is a derivative of the ML — it does not carry independent run/goal-margin
# information. ML win_prob must NOT blend against it; use ML no-vig as the market anchor.
_FIXED_SPREAD_SPORTS = {"MLB", "NHL"}

# First 5 innings sigmas (MLB only — starter matchup, no bullpen noise)
F5_SIGMA = {"total": 2.65, "spread": 2.70, "team": 2.10}  # calibrated 2026-05-29; total/team raised ±0.1 for park variance

# Park run factors by HOME team — multiplied onto projected runs.
# Source: Baseball Savant 2022-2025 Statcast park factors (100 = neutral).
# Applied to F5 and NRFI projections; SaberSim team totals don't carry park-factor information.
# ⚠ STALE/UNVERIFIED as of 2026-06-07 (Plan 10 §M): TEX inverted (~1.05 here was pitcher-friendly,
# now plays ~0.95), COL too low (~1.28 → ~1.33), KC/MIN/DET now hitter-friendly. Do NOT apply
# without a refit from current Fangraphs/Savant park factors.
MLB_PARK_FACTORS = {
    "COL": 1.28, "CIN": 1.08, "BOS": 1.07, "PHI": 1.06, "TEX": 1.05,
    "NYY": 1.04, "HOU": 1.03, "ATL": 1.02, "CHC": 1.01, "LAD": 1.00,
    "MIL": 0.99, "ARI": 0.99, "MIN": 0.98, "DET": 0.97, "WSH": 0.97,
    "BAL": 0.97, "MIA": 0.96, "TOR": 0.96, "CLE": 0.96, "STL": 0.95,
    "KC":  0.95, "PIT": 0.95, "NYM": 0.95, "CHW": 0.95, "TB":  0.94,
    "SEA": 0.93, "OAK": 0.93, "LAA": 0.93, "SF":  0.92, "SD":  0.91,
}

# NB dispersion for MLB team run-scoring. SYNCED 2026-07-02 to EdgeModel's MoM re-fit
# (TEAM_RUN_R=3.50 from realized per-team variance; the frozen 3.548 was the 2026-06-05
# pooled fit). Used for team-total NB CDF and ML NB sum — lockstep with EdgeModel.
MLB_TEAM_RUN_R = 3.50

# Plan 9 §9F tier restructure (2026-06-06): tiers are stat-routing buckets keyed
# by empirical calibration quality — NOT conviction levels. T2 = best-calibrated
# families → lowest floor. Floors monotone in calibration: T2 0.05 < T1B/T3 0.06 < T1 0.07.
# The old framing was inverted: "T1 = highest conviction" had the LOWEST floor (0.03)
# on the WORST-calibrated families (T1 WR 46.6%, ROI −10.2% vs T2 WR 60.3%).
STAT_FAMILY_TIER = {
    # T2 — well-calibrated families
    "PTS": "T2", "OUTS": "T2", "PA": "T2", "PR": "T2", "PRA": "T2", "RA": "T2",
    "NRFI": "T2", "YRFI": "T2", "TEAM_TOTAL": "T2", "F5_TOTAL": "T2",
    "YARDS": "T2", "TB": "T2", "BB": "T2", "PC": "T2",
    "PASS_YDS": "T2", "RUSH_YDS": "T2", "REC_YDS": "T2",  # NFL yardage (Normal, calibrated)
    "REC": "T2",    # Plan 10 §Group A: was T1 — target-driven, more projectable than YARDS
    # T1B — binary/low-line
    "AST": "T1B", "HITS": "T1B",
    "RUNS": "T1B",  # Plan 10 §Group A: was T2 — lineup/context-dependent (one step less than RBI)
    # T1 — moderate calibration, needs monitoring
    "REB": "T1", "HRR": "T1",
    "RBI": "T1",    # Plan 10 §Group A: was T2 — ~74% zero games, opportunity-dependent
    "ER": "T1",     # Plan 10 §Group A: was T2 — BABIP/LOB%-driven, regression-prone
    "HA": "T1",     # Plan 10 §Group A: was T1B — least-controllable pitcher stat (on HA unsuspension)
    # T3 — specialty/low-n
    "3PM": "T3", "SOG": "T3", "NHLPTS": "T3", "NHLBLK": "T3",
    "TDS": "T3", "GOALS": "T3", "ML_DOG": "T3", "PASS_TDS": "T3",  # NFL TDs — high-var
    "GA": "T3",     # Plan 10 §Group A: was T2 — goaltending least-predictable (RS→PO r≈0.15)
    "SV": "T3",     # Plan 10 §Group A: was T2 — doubly-conditional event; Normal poor fit
}

TIERS = {
    # min_edge floors only — stat membership lives in STAT_FAMILY_TIER (Plan 9 §9F).
    "T1":  {"min_edge": 0.07},   # was 0.03 — raised to match G9B NBA floor
    "T1B": {"min_edge": 0.06},   # was 0.03 — binary/low-line needs a higher floor
    "T2":  {"min_edge": 0.05},   # unchanged (G9 universal floor)
    "T3":  {"min_edge": 0.06},   # unchanged
    # T4 (GOLF_WIN) removed — see archived_golf_code.py
}

# Baker–McHale (2013) shrinkage weight per tier: shrunk_p = w·model_p + (1−w)·implied_p.
# Replaces PICK_SCORE_TIER_MULT + VAKE_MULT["tier"] — one mechanism that moves win_prob,
# edge, pick_score AND Kelly stake coherently (Plan 9 §9F).
# DATA_GATED: refit per-family from pick_log calibration at n≥150 graded picks/family.
# (BM_SHRINKAGE_DEFAULT lives in thresholds.py.)
BM_SHRINKAGE_WEIGHT = {"T2": 0.85, "T1": 0.75, "T1B": 0.80, "T3": 0.70}

# Track-B Sprint 1: switch the BM shrinkage anchor from the VIGGED single-side implied
# to the NO-VIG market prob (the theoretically-correct anchor — see sizing_core docstring).
# Flag-gated and DATA_GATED: keep False until CLV maturity / per-family refit n>=150 + sign-off.
# False => byte-identical to current behaviour (vigged anchor).
USE_NO_VIG_ANCHOR = False

# Per-market Kelly multipliers applied BEFORE rounding and floor/cap.
# Lookup: (sport, stat, direction) → (sport, stat, None) → DEFAULT_MARKET_MULT.
# Only applied to straight prop sizing (not SGP/parlay/daily_lay).
KELLY_MARKET_MULT = {
    ("NBA", "PTS", "over"):      0.50,
    ("NBA", "PTS", "under"):     1.00,
    ("NBA", "PTS", None):        1.00,
    ("NBA", "3PM", "under"):     0.75,
    ("NBA", "3PM", "over"):      0.10,
    ("NBA", "REB", "under"):     0.50,
    ("MLB", "OUTS", "under"):    0.50,
    ("MLB", "TEAM_TOTAL", None): 0.75,
    ("NHL", "SOG", None):        0.50,
    ("WNBA", "PTS", None):       1.00,
    ("WNBA", "AST", "over"):     0.10,
    ("WNBA", "REB", None):       0.10,  # 35.3% shadow WR (6W/11L) — pinned to 0.25u floor at go-live 2026-06-09, not excluded; revisit at n>=50

}

# "tier" key retired 2026-06-06 (Plan 9 §9F) — replaced by BM shrinkage on win_prob.
# "variance" kept as a legacy tier-keyed sizing damper; candidate for the DATA_GATED
# Kelly multiplier-stack consolidation (single empirical-Bayes per-market mult at
# n≥50 graded/market — see CLAUDE.md).
VAKE_MULT = {
    "variance":    {"T1": 1.00, "T1B": 1.00, "T2": 0.85, "T3": 0.65},
}

PICK_SCORE_MODES = {
    "Default":      (0.40, 0.60),
    "Conservative": (0.55, 0.45),
    "Aggressive":   (0.30, 0.70),
}

# Additive score penalties for cold_start sub-types (lower projection reliability).
COLD_START_SCORE_PENALTY = {
    "taxi":             -15,
    "returner":         -10,
    "extended_absence":  -8,
    "new_acquisition":   -5,
}

INJURY_TRIGGER_BONUS = {   # redistribution-bump picks — stat-keyed score bonus
    "AST":  10,  # primary distributor absent → backup AST spike, high book lag
    "PTS":   8,  # scorer absent → role bump, moderate lag
    "SOG":   8,  # NHL SOG replacement, similar lag profile to PTS
    "REB":   7,  # rebounder absent, default
}
INJURY_TRIGGER_BONUS_DEFAULT = 7  # fallback for stats not in the dict above
