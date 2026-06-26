# AUDIT 2026-06 — JP-2 Pricing/prob/sizing core (JonnyParlay)

Files audited (10 read): prob_core.py, calibrated.py, sizing_core.py, sizing.py, correlation.py, __init__.py, copula.py, derived.py, distributions.py, odds.py

**Findings (final, excl. refuted): C=0 H=0 M=1 I=4** | constants extracted: 44 | not-done: 8

## Findings

| ID | File:line | Sev | Status | Cat | Known | Title |
|----|-----------|-----|--------|-----|-------|-------|
| JP2-02 | calibrated.py:165 | M | confirmed | statistical | Y | Platt scaling fit on n=76 one-directional props compresses every prop win_prob into [0.308, 0.666] |
| JP2-01 | calibrated.py:225 | I | refuted | statistical |  | MLB_PARK_FACTORS explicitly flagged STALE/inverted but still in the live constant table |
| JP2-03 | calibrated.py:23 | I | refuted | statistical | Y | PTS sigma mult 0.35 implies CV~0.337, tighter than real NBA game-to-game scoring CV (~0.38-0.40) |
| JP2-07 | calibrated.py:187 | I | refuted | statistical | Y | MLB GAME_SIGMA marked interim/uncalibrated; total=4.6 vs documented independence floor, never DB-fit like NBA/NHL |
| JP2-08 | calibrated.py:308 | I | refuted | statistical |  | WNBA REB Kelly mult pinned at 0.10 on a 17-game sample (6W/11L, 35.3% WR) |
| JP2-09 | calibrated.py:84 | I | refuted | statistical | Y | NB_R['HA']=13.41 is from relief-contaminated fit; starts-only data gives var/mu<1 (should be Poisson, not NB) |
| JP2-10 | prob_core.py:113 | I | unverified | code |  | WNBA early-season sigma inflation also applies when sigma_override (dk_std) is supplied |
| JP2-13 | prob_core.py:202 | I | unverified | code | Y | pick_score wp_n is uncapped and unreachable above ~66 due to Platt ceiling — win_prob is structurally under-weighted |
| JP2-06 | copula.py:146 | I | refuted | code |  | copula_joint_prob silently falls back to the independence product on any Cholesky exception |
| JP2-05 | derived.py:43 | I | refuted | code |  | calc_tb_prob does not push-adjust integer total-bases lines (push mass assigned to under) |
| JP2-12 | odds.py:59 | I | unverified | code |  | prob_to_american returns a float, decimal_to_american returns int — inconsistent return types |
| JP2-04 | sizing.py:117 | I | refuted | code |  | size_picks_vake omits the sub-50% win_prob 0.75u cap that size_picks_base and size_bonus_pick both apply |
| JP2-11 | sizing.py:157 | I | unverified | code |  | size_daily_lay hardcodes 0.25 quarter-Kelly instead of importing KELLY_FRACTION |

## C/H/M detail

### [M] JP2-02 — Platt scaling fit on n=76 one-directional props compresses every prop win_prob into [0.308, 0.666]
`C:/Dev/JonnyParlay/engine/calibrated.py:165-171` · statistical · status=confirmed · KNOWN open gate

**Evidence:** PLATT_A=1.4988, PLATT_B=-0.8102 in raw-probability space. _platt_calibrate_prop maps over_p=0 -> sigmoid(-0.8102)=0.308 and over_p=1 -> sigmoid(0.6886)=0.666. The entire [0,1] model range is squashed to [0.308,0.666], with a hard 66.6% ceiling on all prop win_probs. Fit provenance: 76 settled NBA+NHL props, 2026-05-01, in-sample Brier improvement only.

**Recommendation:** This is the KNOWN H3 / overconfidence gate. Refit on the n=2180 graded pick_log with both-sided sample and sigma/temperature scaling. Do not deploy logit-space A/B into the raw-space formula (the assert at line 36 + migration note guard this).

**Verifier (confirmed):** The core technical claims are accurate. In C:/Dev/JonnyParlay/engine/calibrated.py:165-166, PLATT_A=1.4988, PLATT_B=-0.8102 in raw-probability space, and prob_core.py:40 computes raw = PLATT_A*over_p + PLATT_B then sigmoid. I re-derived the bounds: sigmoid(-0.8102)=0.3078 (over_p=0) and sigmoid(1.4988-0.8102=0.6886)=0.6657 (over_p=1), so the model's full [0,1] over_p range is compressed to [0.308, 0.666]. The path is REACHABLE in production: evaluators.py:124-125 calls _platt_calibrate_prop(over


## Confirmed-correct / coverage notes

- **Distribution math is correct.** poisson_pmf/cdf, normal_cdf (erf-based), negbinom_pmf (log-space lgamma, p=r/(r+mu) parameterisation giving var=mu+mu^2/r) and negbinom_cdf are all standard and correct (quant/distributions.py). NB at k<0 and mu<=0 edge cases handled.
- **Push-adjustment for integer prop lines is correct** in both the Poisson and NB branches of calc_prop_prob (prob_core.py 68-102): push=pmf(k), strict_over=1-cdf(k), strict_under=cdf(k-1), renormalized by non_push; over_p+under_p=1. Half-integer branch correctly has no push.
- **Truncated-Normal PTS path is correct** (prob_core.py 130-137): P(X>line|X>=0) and P(X<line|X>=0) both divide by the same Φ(mu/sigma) and sum to 1.
- **Correlated-Normal combo variance is correct**: Var=Σσ²+2Σρσσ (prob_core.py 159-165), with a 2.0 sigma floor and WNBA early-season inflation matching the single-stat path.
- **Kelly sizing is correct**: f*=(b·p−q)/b with proper +odds/−odds b conversion, returns 0 on non-positive edge, scaled by KELLY_FRACTION (sizing_core.py 54-75). round_units rounds to 0.25u. size_daily_lay quarter-Kelly converts fraction→units correctly (1u=1% bankroll).
- **MLB_TEAM_RUN_R=3.548 cross-checks externally**: implies mean ≈ 4.47 runs/team/game, consistent with MLB 2024 actual ≈ 4.39 ([TeamRankings](https://www.teamrankings.com/mlb/stat/runs-per-game)).
- **mlb_ml_from_nb is correct**: discrete NB convolution over 0..30 runs, ties split 50/50, clamped [0,1] (quant/derived.py 14-29).
- **calc_tb_prob Poisson convolution** is correct for half-integer lines (the normal case); only integer-line push is unhandled (JP2-05).
- **t-copula MC (copula_joint_prob)** is a correct t-copula construction: shared chi2(df) scaling across legs gives symmetric tail dependence; marginals hit with prob p by construction; Cholesky for correlation; fixed seed for reproducibility. validate_corr_matrix provides a proper PSD/symmetry/range guard.
- **odds.py conversions** (implied_prob, no_vig, american/decimal) are correct; implied_prob_or_none hardens CSV/API input (NaN/inf/0 → None) and delegates the formula to implied_prob (single source of truth).
- **calc_edge** measures edge vs no-vig (model_prob−nv_over, (1−model_prob)−nv_under) — correct convention, and BM shrinkage's vigged-anchor-vs-no-vig-edge residual is explicitly documented as a known, small, DATA_GATED item.
- **correlation.py gates** (dedup 3-pass, GLC hard/soft conflict matrix, cross-type X1 anti-correlation, TT-divergence warn) are logically sound; cross_type uses id()-based dedup (safe), GLC uses .index() (benign edge case only on value-identical dicts).
- **deduplicate** correctly preserves opposite-direction picks and routes NRFI/YRFI by game key.
- The Platt raw-vs-logit migration is correctly guarded by an assert + paired-update doc; PLATT_FIT_DATE feeds the freshness health check.

## Not-Done / incomplete (this module)

| Kind | File | Detail |
|------|------|--------|
| flag-gated | calibrated.py | USE_NO_VIG_ANCHOR=False (line 291) gates the theoretically-correct no-vig BM shrinkage anchor off; flag-off path is byte-identical (vigged anchor). Intentional  |
| deferred | prob_core.py | _platt_calibrate_prop logit-space migration (lines 32-39) pending H3 gate; assert guards against pasting logit A/B into raw formula. Sigma/temperature refit on  |
| deferred | calibrated.py | MLB_PARK_FACTORS (line 231) flagged 'Do NOT apply without a refit' 2026-06-07; TEX sign inverted, COL/KC/MIN/DET stale. Needs refit from current Savant/Fangraph |
| deferred | calibrated.py | NB_R['HA']=13.41 (line 84) to be reclassified HA->Poisson (starts-only var/mu=0.890<1) on HA unsuspension; tracked under G_HA_SUSPENDED. |
| partial-feature | calibrated.py | NFL constants present but data half deferred: SIGMA PASS/RUSH/REC_YDS (lines 42-44), POISSON_STATS TDS/PASS_TDS (line 52), STAT_FAMILY_TIER NFL entries (254,266 |
| deferred | calibrated.py | GAME_SIGMA['MLB'] (line 187) and F5/park values are interim/uncalibrated — 'Recalibrate from 8095-game DB like NBA/NHL'. |
| deferred | calibrated.py | BM_SHRINKAGE_WEIGHT (line 285) and VAKE_MULT (line 316) DATA_GATED: per-family refit at n>=150 graded picks, and Kelly multiplier-stack consolidation to single  |
| dead-code | calibrated.py | SIGMA dict comments document removed-but-referenced entries (REC, SOG/HITS removed because POISSON_STATS takes priority). Confirmed removed; comments are covera |
