# JonnyParlay + EdgeModel — Comprehensive Findings Report

_Generated: 2026-06-16 08:50 MDT_

_Source: `JonnyParlay_Master_Audit_Tracker.xlsx` · 480 findings across 23 layers_

## Executive Summary

This report consolidates findings from a 12-substep deep audit (Steps 4a–4l) of the JonnyParlay engine and EdgeModel projector. Every finding is tied to a specific file:line in the codebase, with evidence snippets and a recommended next action. Severity uses the system's existing P0/P1/P2/P3 + INFO scheme.

### Counts at a glance

| Severity | Total | Open | Verified ✅ | Info 📋 |
|---|---|---|---|---|
| P0 | 85 | 25 | 60 | 0 |
| P1 | 156 | 114 | 42 | 0 |
| P2 | 84 | 74 | 5 | 5 |
| P3 | 26 | 10 | 3 | 13 |
| INFO | 129 | 1 | 98 | 30 |

### Top 10 risks (curated)

Ordered by combined impact (correctness × frequency × ease of exploitation by variance):

| # | Risk | Detail |
|---|---|---|
| 1 | **Plan 9 §9F monotonicity violation** | T3 has lowest BM trust weight (0.70) but mid-pack edge floor (0.06). Lowest-confidence tier shouldn't have a less-strict edge gate than T1B (0.06) or T2 (0.05). S4c-5 / S4f-3 · `engine/thresholds.py` |
| 2 | **Combo + MLB Platt calibrators missing** | `evaluators.py:124` references combo & MLB Platt but only NBA/WNBA artifacts exist on disk. Combo SGP probabilities and MLB game lines fall back to raw model output silently. S4b-8 / S4b-9 |
| 3 | **NB_R producer/consumer drift** | JP uses `NB_R[AST]=12.16`, projector exports `r=9.65`. JP uses `NB_R[REB]=14.7`, projector JSON says 13.16. Variance is materially different — affects every NB-modeled line. S4d-1 / S4d-2 / S4e-2 |
| 4 | **MLB starts-only + WNBA min≥20 filters absent in projector calibration** | Plan 6 §1C requires σ to be fit on "started games only" (MLB) and "min≥20 priced minutes" (WNBA). `calibrate_distributions.py` does not apply either filter. σ is systematically too wide for both sports. S4e-3 / S4e-4 |
| 5 | **WNBA team_sigmas keyed by ID, looked up by abbreviation** | JSON stores `team_sigmas` keyed by numeric team_id; runtime lookup uses 3-letter abbreviation. Every lookup misses → silent fallback to league σ. Team-level dispersion is effectively unused. S4d-5 |
| 6 | **Props have no max-edge ceiling** | Game-line has GG1=0.10 ceiling but props do not. A model blow-up on a single prop (e.g. an outlier σ) goes through to staking unbounded. S4f-2 |
| 7 | **MIN_LEG_WIN_PROB_OUTS=0.62 tuned to stale σ** | Gate was set when σ_outs was 0.311; current calibrated σ is 0.27. Threshold is now too lax given the tighter distribution — admits picks the original gate would have excluded. S4f-4 |
| 8 | **PLATT_SPACE='raw' flag fragility** | Deploy-time string flag controls whether Platt inputs are raw or vigged-stripped. Wrong value silently degrades calibration with no health-check assertion. S4f-15 (H3) |
| 9 | **SGP correlation ρ unstamped / structural-priors-only** | NBA SGP ρ matrix has no version/timestamp; MLB SGP ρ is structural priors (no fit yet, awaiting 100+ SGPs). ρ=0.30 OUTS×opp-HITS is the most consequential single value and is unvalidated. S4g-4 / S4g-5 / S4g-12 |
| 10 | **VAKE 5-multiplier stack drives T3 picks to floor** | Variance/Adj/Knockout/Edge stack compounds to multiply T3 stakes downward in nearly every scenario. Effective T3 sizing is the floor, not Kelly-derived. S4h-8 |

### How to read this report

- **P0** findings have full narrative entries (one heading per finding).
- **P1** findings have full narrative entries.
- **P2** / **P3** are summarized in compact tables (open issues only).
- **INFO** is summarized at the bottom (counts only — these are configuration documentation, not issues).
- Every finding has a file:line citation. Status icons: ❌ confirmed bug · ⚠️ partial / drift · ❓ needs verification · 🧟 zombie code · ✅ verified-OK · 📋 informational.
- Validation sources are noted in the Research Appendix at the end.

## P0 — Critical (correctness-affecting)

**Total: 85** (Open: 25 · Verified ✅: 60 · Info 📋: 0)


### Open issues (25)


#### P0-1. PLATT_A/B (NBA props)

- **Finding ID**: H3 gate
- **Layer**: L2: Calibrated
- **Location**: `engine/calibrated.py:(per CLAUDE.md)`
- **Status**: ⚠️  ·  **Category**: Calibration  ·  **Tested**: Y — CLAUDE.md gates documented
- **Finding**: A=1.4988, B=-0.8102. Frozen until H3 gate (98/100 as of 2026-06-13)
- **Evidence**: `OOS Brier improves AND formula+A/B+PLATT_SPACE change atomically`
- **Next action**: At gate: fit intercept-only (A=1 forced, logit-space) per CLAUDE.md; deploy only if OOS Brier improves

#### P0-2. poisson_pmf / poisson_cdf

- **Finding ID**: —
- **Layer**: L3: Quant Math
- **Location**: `engine/quant/distributions.py:—`
- **Status**: ❓  ·  **Category**: Math  ·  **Tested**: N
- **Finding**: Pure math; verify CDF method (recursive vs lgamma) and accuracy at large k
- **Evidence**: `Numerical agreement within 1e-9`
- **Next action**: Verify CDF agrees with scipy.stats.poisson.cdf at k=0..50

#### P0-3. negbinom_pmf / negbinom_cdf

- **Finding ID**: —
- **Layer**: L3: Quant Math
- **Location**: `engine/quant/distributions.py:—`
- **Status**: ❓  ·  **Category**: Math  ·  **Tested**: N
- **Finding**: NB CDF accuracy critical for P16 path
- **Evidence**: `Numerical agreement within 1e-9`
- **Next action**: Verify against scipy.stats.nbinom with parameter conventions (r, p vs r, μ)

#### P0-4. normal_cdf

- **Finding ID**: —
- **Layer**: L3: Quant Math
- **Location**: `engine/quant/distributions.py:—`
- **Status**: ❓  ·  **Category**: Math  ·  **Tested**: N
- **Finding**: Used by PTS truncated path + standard Normal stats
- **Evidence**: `Within 1e-9`
- **Next action**: Verify against math.erf-based reference

#### P0-5. implied_prob (vigged)

- **Finding ID**: F1.5
- **Layer**: L3: Quant Math
- **Location**: `engine/quant/odds.py:—`
- **Status**: ❓  ·  **Category**: Math  ·  **Tested**: Y — F1.5 was the bug callout
- **Finding**: American odds → vigged implied prob. Used by BM shrinkage (correct) and historically caused F1.5 bug
- **Evidence**: `Math match for ±100 ±150 +200 -200 cases`
- **Next action**: Verify formula: positive→100/(odds+100), negative→|odds|/(|odds|+100)

#### P0-6. novig (no-vig)

- **Finding ID**: —
- **Layer**: L3: Quant Math
- **Location**: `engine/quant/derived.py:—`
- **Status**: ❓  ·  **Category**: Math  ·  **Tested**: N
- **Finding**: Used for edge baseline. Power-method (Shin) or proportional?
- **Evidence**: `Documented + tested`
- **Next action**: Read source; document method; verify symmetric two-sided novig sums to 1.0

#### P0-7. check_game_gates

- **Finding ID**: —
- **Layer**: L6: Gates
- **Location**: `engine/gates.py:217-257`
- **Status**: ❓  ·  **Category**: Gate  ·  **Tested**: N
- **Finding**: GG1-GG6 for game lines
- **Next action**: Read each + add to tracker individually

#### P0-8. evaluate_props

- **Finding ID**: —
- **Layer**: L9: Evaluators
- **Location**: `engine/evaluators.py:?`
- **Status**: ❓  ·  **Category**: Logic  ·  **Tested**: N
- **Finding**: Main prop eval loop; applies Platt + BM + gates
- **Next action**: Read full flow

#### P0-9. _pairwise_rho

- **Finding ID**: —
- **Layer**: L10: SGP
- **Location**: `engine/sgp_builder.py:?`
- **Status**: ❓  ·  **Category**: Math  ·  **Tested**: N
- **Finding**: Domain-specific correlation lookup; stays in sgp_builder
- **Next action**: Read all ρ entries; validate against literature

#### P0-10. _build_corr_matrix

- **Finding ID**: —
- **Layer**: L10: SGP
- **Location**: `engine/sgp_builder.py:?`
- **Status**: ❓  ·  **Category**: Math  ·  **Tested**: N
- **Finding**: Builds n×n correlation matrix from leg pairs
- **Next action**: Verify positive-semi-definiteness checks

#### P0-11. grade_picks main

- **Finding ID**: audit_2026-05-27_grade_clv
- **Layer**: L14: Grading
- **Location**: `grade_picks.py:—`
- **Status**: ❓  ·  **Category**: Logic  ·  **Tested**: N
- **Finding**: Picks grading + CLV integration
- **Next action**: Read + cross-reference audit_2026-05-27_grade_clv.md

#### P0-12. calibrate_platt

- **Finding ID**: H3
- **Layer**: L16: Calibration Scripts
- **Location**: `engine/calibrate_platt.py:—`
- **Status**: ❓  ·  **Category**: Tooling  ·  **Tested**: Y — CLAUDE.md describes invocation
- **Finding**: Platt refit (intercept-only at H3 gate)
- **Evidence**: `Refit script changes all 3 (formula + A/B + PLATT_SPACE)`
- **Next action**: Verify --intercept-only flag exists; verify it writes PLATT_SPACE alongside A/B

#### P0-13. odds_io

- **Finding ID**: —
- **Layer**: L17: Data Ingestion
- **Location**: `engine/odds_io.py:—`
- **Status**: ❓  ·  **Category**: IO  ·  **Tested**: N
- **Finding**: Odds API fetch + parse
- **Next action**: Read; verify retry/timeout policy + rate limiting

#### P0-14. market_config

- **Finding ID**: —
- **Layer**: L17: Data Ingestion
- **Location**: `engine/market_config.py:—`
- **Status**: ❓  ·  **Category**: Config  ·  **Tested**: N
- **Finding**: PROP_MARKETS, MARKET_TO_STAT, WNBA_TEAM_ABBREV, etc.
- **Next action**: Read; cross-check against active markets in pick_log

#### P0-15. SB26-131 deposit ban (CO)

- **Finding ID**: CLAUDE.md
- **Layer**: L22: Operational
- **Location**: `—:—`
- **Status**: ⚠️  ·  **Category**: Compliance  ·  **Tested**: Y — CLAUDE.md flags as URGENT
- **Finding**: Effective 2026-08-12: credit-card deposit ban + max 6 deposits/24h. Not a code change.
- **Evidence**: `Funding plan documented before 2026-08-12`
- **Next action**: Switch to ACH primary funding; cache working balance per book

#### P0-16. NFL go-live prep

- **Finding ID**: CLAUDE.md / Backlog #27
- **Layer**: L22: Operational
- **Location**: `—:—`
- **Status**: ❌  ·  **Category**: Ops  ·  **Tested**: Y
- **Finding**: Pre-NFL: harden POISSON_CUTOFF, refit REC NB at n>=50, full NFL architecture (Jul deadline)
- **Evidence**: `All pre-NFL items closed`
- **Next action**: Complete by July 2026

#### P0-17. H3 Platt refit (98/100)

- **Finding ID**: CLAUDE.md
- **Layer**: L_OPEN: Active Open Issues
- **Location**: `engine/calibrate_platt.py:—`
- **Status**: ❌  ·  **Category**: Calibration  ·  **Tested**: Y
- **Finding**: 98/100 — 2 picks from gate. Plan: intercept-only fit at n=76-100; free 2-param at n>=300
- **Evidence**: `OOS Brier improvement at gate`
- **Next action**: At gate: run calibrate_platt.py --intercept-only --force; verify OOS Brier improves; deploy atomically

#### P0-18. tests/ directory

- **Finding ID**: —
- **Layer**: L29: EdgeModel tests
- **Location**: `tests/:—`
- **Status**: ❌  ·  **Category**: Test gap  ·  **Tested**: Y — confirmed empty
- **Finding**: VERIFIED 2026-06-16. tests/ directory exists but is EMPTY/unreadable (no test files). ZERO automated tests across 10,161 LOC EdgeModel codebase. Calibration constants change weekly per the dated comments — high regression risk.
- **Evidence**: `ls /tests/ shows empty dir`
- **Next action**: P0: Add minimum smoke tests: (a) PROJ_STATS roundtrip, (b) constrain_team_totals scale bounds, (c) PLAYOFF_RATE_DEFLATORS values match published constants, (d) compute_ast_rate per-game pace fallback (F14.9), (e) compute_reb_rates positional priors sum=1 invariant, (f) PAD_3P returns career-to-date not 30-game window

#### P0-19. C1 — Platt logit-fit space mismatch

- **Finding ID**: C1
- **Layer**: L30: EdgeModel prior audit (2026-05-30)
- **Location**: `calibrate_platt.py:28-35`
- **Status**: ❌  ·  **Category**: Math  ·  **Tested**: Y — already P0 in tracker
- **Finding**: CRITICAL prior-audit finding: logit-fit constants applied in raw-probability space in run_picks.py. Known mismatch — H3 migration required (see L2 H3 gate). Atomic 3-way deploy needed (raw_p, logit-fit constants, refit threshold).
- **Evidence**: `audit_module1_draft.md line 38`
- **Next action**: Already tracked as JonnyParlay L2 H3 gate. Cross-link.

#### P0-20. C2 — BLK playoff inflator 1.152

- **Finding ID**: C2
- **Layer**: L30: EdgeModel prior audit (2026-05-30)
- **Location**: `nba_projector.py:357`
- **Status**: ⚠️  ·  **Category**: Calibration  ·  **Tested**: N
- **Finding**: CRITICAL prior-audit: BLK inflator 1.152 not confirmed by aggregate data; may double-count selection effect (more half-court → more block opportunities AND only good defenders get playoff minutes).
- **Evidence**: `audit_module1 C2; L353-357 in nba_projector`
- **Next action**: Refit BLK deflator against multi-year aggregate. Currently mitigated by REGULAR_SEASON_STAT_SCALAR.blk=1.0608 separation.

#### P0-21. Combo Platt skip — TOP BUG #2

- **Finding ID**: S4b-8
- **Layer**: L32: Step 4b — Gates audit
- **Location**: `engine/evaluators.py:121-125`
- **Status**: ❌  ·  **Category**: Calibration  ·  **Tested**: N — no Platt-applied test for combos
- **Finding**: CONFIRMED at evaluators.py:124 `if _sport != 'MLB' and stat not in COMBO_STATS: over_p = _platt_calibrate_prop(over_p)`. Comment 121-123 explicitly acknowledges: 'Platt was fitted on single-stat props; the joint-Normal combo probability has a different shape and will be mis-calibrated until a separate combo sample exists. TODO: refit at SGP Platt gate (100 scored slips).' PRA/PR/PA/RA WPs ride raw calc_combo_prob → ~5pp inflated.
- **Evidence**: `evaluators.py:122-123 'TODO: refit at SGP Platt gate (100 scored slips)'`
- **Next action**: Refit Platt on combos (PRA/PR/PA/RA) once n=100 scored slips collected. Tag refit gate in calibrate_platt.py.

#### P0-22. MLB Platt skip — TOP BUG #3

- **Finding ID**: S4b-9
- **Layer**: L32: Step 4b — Gates audit
- **Location**: `engine/evaluators.py + calibrate_platt.py:ev:121-125, cp:1+`
- **Status**: ❌  ·  **Category**: Calibration  ·  **Tested**: N
- **Finding**: Same conditional `_sport != 'MLB'` at evaluators.py:124 skips ALL MLB props (pitcher K/OUTS/HA/ER + batter HITS/TB/HRR/RBI/RUNS) from Platt. calibrate_platt.py supports --sport NBA|NHL|all but does NOT split out MLB. Status: ~28/100 picks toward refit gate.
- **Evidence**: `evaluators.py:124 `_sport != 'MLB'``
- **Next action**: Continue accumulating MLB graded sample to 100, then refit Platt for MLB. Extend calibrate_platt.py with MLB segment.

#### P0-23. BM_SHRINKAGE_WEIGHT — T3 vs T1 inversion (TOP BUG #7)

- **Finding ID**: S4c-5
- **Layer**: L33: Step 4c — Math audit
- **Location**: `engine/calibrated.py + sizing_core.py:cal:260, sc:13-25`
- **Status**: ❌  ·  **Category**: Calibration  ·  **Tested**: N — no test_bm_shrinkage_monotone_in_floor
- **Finding**: CONFIRMED inversion. BM_SHRINKAGE_WEIGHT = {T2: 0.85, T1: 0.75, T1B: 0.80, T3: 0.70}. TIERS min_edge floors (cal:246-251) = {T2: 0.05, T1B: 0.06, T1: 0.07, T3: 0.06}. Floor ordering says T1 is WORST-calibrated (highest floor 0.07). Shrinkage logic says lower w → more shrinkage. T1 (worst) gets w=0.75; T3 (better per floor=0.06) gets w=0.70 — i.e. T3 is shrunk MORE despite being better-calibrated than T1. EITHER (a) T3 floor should be 0.08+ to match its 0.70 w, OR (b) T3 w should be raised to ≥0.75 to match its 0.06 floor.
- **Evidence**: `calibrated.py:260 BM_SHRINKAGE_WEIGHT dict`
- **Next action**: Resolve inversion. Option (a): raise T3 floor to 0.08 (matches w=0.70 conservatism). Option (b): raise T3 w to 0.78-0.80 (matches floor=0.06). Decide based on per-tier ROI data: if T3 actual WR << T1, then (a); if T3 WR ≈ T1B, then (b). Currently T1 has 'worst ROI' per top-13 bug list → inversion is real.

#### P0-24. PLATT_A=1.4988 / PLATT_B=-0.8102 (76-prop fit)

- **Finding ID**: S4d-14
- **Layer**: L34: Step 4d — Calibration audit
- **Location**: `engine/calibrated.py:129-149`
- **Status**: ⚠️  ·  **Category**: Phase-1a Platt not yet at H3 gate  ·  **Tested**: Cross-confirmed P0 (combined with S4b-8/9)
- **Finding**: PLATT_A/B fitted 2026-05-01 from 76 settled primary/bonus props (NBA + NHL) via Nelder-Mead NLL. Stored in raw-probability space: sigmoid(A*over_p + B). BUT calibrate_platt.py (line 36-44) was migrated 2026-05-25 to logit-space fitting; the live formula in run_picks.py is still RAW-PROBABILITY. The constants A=1.4988/B=-0.8102 belong to raw-space; pasting logit-space output here would shift output by ~12pp at over_p=0.75. H3 gate requires 100 native over_p_raw rows to fire intercept-only refit; currently n=76. Phase 1a (n=100): intercept-only Platt (A=1, fit B). Phase 1b (n=300+): free 2-param. Phase 2 (n=300+): isotonic. Combined with confirmed P0 bug S4b-8 (combo Platt missing) and S4b-9 (MLB Platt missing), all three Platt deficits hold.
- **Evidence**: `engine/calibrated.py:148 PLATT_A = 1.4988  # raw-prob space; engine/calibrate_platt.py:37 logit-space fitting`
- **Next action**: Atomically migrate at H3 firing: (1) update _platt_calibrate_prop() to logit-space, (2) paste new A/B from calibrate_platt.py, (3) update PLATT_SPACE flag in thresholds.py — DO NOT do (1) without (2)+(3). Run intercept-only fit per Phase 1a at n=100; defer free 2-param to n>=300. Brier improvement target: >=6% in-sample (matching 2026-05-01 fit).

#### P0-25. T3 floor=0.06 vs T3 BM weight=0.70 (cross-stat inconsistency)

- **Finding ID**: S4f-3
- **Layer**: L36: Step 4f — Gates & Tiers audit
- **Location**: `engine/calibrated.py:calibrated.py:225 (STAT_FAMILY_TIER); calibrated.py:TIERS; calibrated.py:BM_SHRINKAGE_WEIGHT`
- **Status**: ❌  ·  **Category**: Tier governance inconsistency  ·  **Tested**: Verified: code reads on TIERS, BM_SHRINKAGE_WEIGHT, STAT_FAMILY_TIER
- **Finding**: Re-verifies S4c-5 with full code reads. TIERS min_edge floors: T1=0.07, T1B=0.06, T2=0.05, T3=0.06. BM_SHRINKAGE_WEIGHT (trust toward projector vs market): T2=0.85, T1B=0.80, T1=0.75, T3=0.70, default=0.80. T3 has the LOWEST trust (0.70 — projector least reliable for 3PM, SOG, NHLPTS, GA, SV, TDS, GOALS, ML_DOG) but a MIDDLE floor (0.06) — same as T1B. Plan 9 §9F claims monotonicity ('lower trust → higher floor') but T3 violates it. Either raise T3 floor to 0.08 (most defensible: low trust + low n → highest floor) or raise T3 weight to 0.80 (treat T3 the same as T1B). The current setup means a 6% T3 edge sizes at 70% of Kelly while a 6% T1B edge sizes at 80% — opposite of what risk-adjusted Kelly demands.
- **Evidence**: `calibrated.py TIERS: T3:{min_edge:0.06}; BM_SHRINKAGE_WEIGHT: T3:0.70. STAT_FAMILY_TIER T3 = {3PM, SOG, NHLPTS, NHLBLK, TDS, GOALS, ML_DOG, GA, SV}`
- **Next action**: Decision required: (a) raise TIERS['T3']['min_edge'] from 0.06 to 0.08, OR (b) raise BM_SHRINKAGE_WEIGHT['T3'] from 0.70 to 0.80. Recommendation: option (a) — keeps the lower trust signal (0.70) AND requires a higher edge floor to compensate. Backtest both: ROI by tier, n_picks, max drawdown.

### Verified-OK at this severity (60)

| Component | Location | Finding ID | Notes |
|---|---|---|---|
| KILLSHOT_STAT_ALLOW={PTS,AST} | `engine/thresholds.py:48` | F10.2 | Was {PTS,SOG,REB,AST,3PM} → unsatisfiable v2; v3 dropped tier req and curated to {PTS,AST}. SOG suspended; REB low WR; 3 |
| SIGMA['PTS']=0.35/5.0 | `engine/calibrated.py:31` | audit_2026-05-25 | mult confirmed via MAE backtest; min raised 4.5→5.0 |
| SIGMA['REB']=0.48/2.0 | `engine/calibrated.py:29` | audit_2026-05-25 | Combo path only (single-stat REB → NB_STATS r=14.7); empirical median CV=0.483 |
| SIGMA['AST']=0.53/2.0 | `engine/calibrated.py:30` | audit_2026-05-25 | Combo path only (single-stat AST → NB_STATS r=12.16); median CV=0.507 |
| SIGMA['OUTS']=0.27/1.0 | `engine/calibrated.py:41` | Plan 6 §1C | Recalibrated 2026-06-05 on STARTS ONLY (was 0.311 contaminated by relief). Within-CV starts=0.228 vs relief=0.443 |
| SIGMA['SV']=0.253/3.5 | `engine/calibrated.py:44` | audit_2026-05-26 | NHL goalie saves; Normal is correct (high-volume continuous-ish, mean=26.6) |
| POISSON_STATS set | `engine/calibrated.py:53` | audit_2026-05-30 | {SOG,REC,HITS,GOALS,NHLPTS,NHLBLK,RUNS,GA,BB}. HA moved to NB; AST/REB moved to NB. |
| NB_STATS set | `engine/calibrated.py:67` | P16 | {3PM, HRR, AST, REB, HA, RBI, ER, TB} |
| NB_R['3PM']=9.15 | `engine/calibrated.py:69` | audit_2026-05-25 | var/mu=1.1486. Was 12.3 (too tight). |
| NB_R['AST']=12.16 | `engine/calibrated.py:70` | 2026-05-30 | Game-level refit. var/mu=1.3234. Was 9.68 from player-seasons. |
| NB_R['REB']=14.7 | `engine/calibrated.py:71` | 2026-05-30 | Game-level refit. var/mu=1.3873. Was 10.18. |
| NB_R['HA']=13.41 | `engine/calibrated.py:73` | 2026-05-26 | var/mu=1.204. Confirmed by EdgeModel 2026-05-30 (56,280 games). |
| NB_R_WNBA | `engine/calibrated.py:80` | 2026-06-04/09 | AST=11.37, REB=10.74, 3PM=1.342 (recalibrated 2026-06-09, heavy zero-inflation) |
| STAT_FAMILY_TIER routing | `engine/calibrated.py:(per CLAUDE.md)` | Plan 9 §9F + Plan 10 | Plan 10 moves: RBI/ER→T1, RUNS→T1B, GA/SV→T3, HA→T1, REC→T2 |
| MLB_TEAM_RUN_R=3.548 | `engine/calibrated.py:(per CLAUDE.md)` | 2026-06-05 | NB dispersion for team runs (var/μ=2.261). Used for team-total NB CDF + ML. |
| GAME_SIGMA['NBA'] | `engine/calibrated.py:(per CLAUDE.md)` | Plan 6 §6 | total=18.5, spread=12.5, team=11.0, ml=12.5. Prior 12/12/9/12 were ~40% too narrow. |
| GAME_SIGMA['NHL'] | `engine/calibrated.py:(per CLAUDE.md)` | 2026-06-05 | total=2.311, spread=2.614, team=1.744, ml=2.614. Prior was ~2× wrong. |
| GAME_SIGMA['WNBA'] | `engine/calibrated.py:(per CLAUDE.md)` | 2026-06-09 | total=17.424, team=11.253 (spread/ml=10.0 — no active picks) |
| _platt_calibrate_prop | `engine/prob_core.py:26-40` | H3 | Raw-space sigmoid. PLATT_SPACE assertion guards against partial migration. |
| calc_prop_prob — Poisson path | `engine/prob_core.py:60-77` | FIX M1 | Push-adjusted at integer lines: strict_over/non_push redistribution. SOG exempted from cutoff via `or stat == 'SOG'`. |
| calc_prop_prob — NB path | `engine/prob_core.py:78-106` | P16 | Push-adjusted at integer lines. WNBA → NB_R_WNBA. Sport-specific dampener via early_season_factor shrinks toward 0.5. |
| calc_prop_prob — Normal path | `engine/prob_core.py:107-130` | H3 | sigma_override (dk_std) used when >0. PTS uses TRUNCATED Normal at [0,∞) |
| Truncated Normal for PTS | `engine/prob_core.py:120-127` | — | P(X>line\|X≥0) = (1−Φ((line−μ)/σ)) / Φ(μ/σ). Correction +0.5-4pp at μ=10-25,σ≈5 |
| _combo_mu_sigma | `engine/prob_core.py:133-160` | Plan 10 §A | Var(X+Y) = ΣVar + 2Σρσσ. Combo path lacks Platt — wp inflated ~5pp (CLAUDE.md) |
| pick_score | `engine/prob_core.py:170-207` | Plan 6 §11 / Plan 9 §9F | Tier mult retired 2026-06-06 (BM carries calibration). Edge cap at 15% (Plan 6 §11). NOT capped at 100. |
| apply_bm_shrinkage | `engine/sizing_core.py:11-21` | Plan 9 §9F | shrunk_p = w·model + (1−w)·implied(odds). Vigged baseline used (correct — edge measured against novig downstream). |
| kelly_units | `engine/sizing_core.py:23-44` | FIX M4 | Returns 0 for f*≤0. KELLY_FRACTION=6.0 multiplier. |
| round_units | `engine/sizing_core.py:46-48` | — | Round to nearest 0.25u |
| get_tier (stat-family) | `engine/sizing_core.py:62-77` | Plan 9 §9F | STAT_FAMILY_TIER + REB-over→T2 (shadow) + NHL-AST→T3 overrides |
| get_tier_min_edge | `engine/sizing_core.py:79-81` | — | TIERS[tier].min_edge with 0.05 fallback |
| _killshot_size | `engine/killshot.py:36-?` | Plan 6 §13 | Flat 3u base, 4u bump conditional on both wp>=0.70 AND edge>=0.06 |
| _killshot_odds_wp_ok | `engine/killshot.py:55-?` | Plan 6 §13 | Both auto AND manual paths enforce odds range + wp >= implied(odds) + margin |
| _passes_killshot_v2_gate | `engine/killshot.py:83-?` | Plan 6 §13 | ALL conditions must pass (score floor + stat allow + odds-wp + manual override exception) |
| _assert_killshot_invariants | `engine/killshot.py:111-132` | Plan 6 §13 | Runs at module load; fails fast if SOG re-enters allowlist without tier set update |
| select_killshots | `engine/killshot.py:162-247` | Plan 6 §13 | Applies cap + odds-wp filter + selection order |
| SPORT_UNIT_CAP post-KILLSHOT | `engine/run_picks.py:1265-1280` | F5.6 | Re-checks per-sport ceiling after KILLSHOT sizing (apply_caps() ran before KILLSHOT) |
| G1: structural | `engine/gates.py:~200` | — | Catch-all sanity at end of check_prop_gates |
| G8: binary fragility | `engine/gates.py:44-49` | FIX M3 / F9.4 | AST/REB/SOG/HA/HITS at line≤1.5 blocked. NHL AST 0.5 under EXEMPTED (Bernoulli T3). |
| G8B: AST over ≤4.5 NBA | `engine/gates.py:55-56` | audit_2026-05-13 | 0-5 record at ≤4.5 vs 2-1 at ≥5.5. NBA-only (WNBA exempted). |
| G_NHL_AST | `engine/gates.py:60-61` | 2026-06-05 | NHL AST live only at line=0.5 under (Bernoulli, T3, min_edge=0.06) |
| SUSPENDED_STATS lookup | `engine/gates.py:66-67` | 2026-06-05 | Single source of truth for SOG/HA/RA suspensions |
| G8C: SOG under ≤3.5 | `engine/gates.py:72-73` | audit_2026-05-23 | Extended from ≤2.5 (51.9% WR) to ≤3.5 (added bucket 42.9% WR). Recheckpoint n>=30. |
| G8D: 3PM over ≤1.5 NBA | `engine/gates.py:79-80` | audit_2026-05-26 | 50% actual vs 70.4% model n=16. WNBA exempt. |
| G_WNBA_OPEN | `engine/gates.py:97-104` | Plan 6 §14 9c | Re-keyed from days to GAMES PLAYED; both teams >=2. Fallback to day-gate. |
| G_WNBA_EDGE (EV floor) | `engine/gates.py:117` | Plan 6 §14 B | EV-per-unit floor = WNBA_EV_FLOOR (0.0955) |
| G_HA_DIR | `engine/gates.py:126` | — | Routes via SUSPENDED_STATS now |
| G_HITS_OVER_SHADOW | `engine/gates.py:131` | Plan 10 | HITS over → shadow (was admitted with negative EV) |
| G_HRR_OVER_LOW_LINE | `engine/gates.py:132-138` | 2026-06-09 | HRR over at line≤0.5 blocked. 46.3% WR, -25.5% sized ROI n=54. |
| G9 universal edge floor | `engine/gates.py:141-142` | — | edge < 0.05 blocked. NBA bumped to G9B 0.07. |
| G9B NBA props higher floor | `engine/gates.py:145-146` | — | NBA props edge >= 0.07 (more efficient market) |
| G13 pick_score floor | `engine/gates.py:150` | — | MIN_PICK_SCORE=15 |
| G14 projection clearance | `engine/gates.py:156-187` | F11.14 | Normal/SIGMA stats: proj must clear line by ≥0.10σ. HRR exempt (now NB_STATS). Poisson stats exempt. |
| G15 high-var 3PM | `engine/gates.py:196` | — | No 3PM for HIGH-VAR players (pts_cv>=0.60) |
| G_TB_DISABLED / G_HRR_DISABLED / G_RA_DISABLED | `engine/gates.py:152-154` | Plan 10 / 2026-06-05 | G_TB removed 2026-05-27 (Poisson convolution shipped); G_HRR removed 2026-05-27; G_RA via SUSPENDED_STATS |
| deduplicate (3-pass) | `engine/correlation.py:?` | — | Pass 1: collapse same-line different books. Pass 2: best edge per (player,stat,dir). Pass 3: MLB corr group dedup. |
| MLB correlation groups | `engine/calibrated.py:MLB_CORR_GROUPS` | — | Pitcher: K/OUTS/HA/ER all IP-driven. Batter: HITS⊂HRR. |
| evaluate_nrfi (Poisson λ) | `engine/evaluators.py:?` | 2026-05-29 | Rewritten to Poisson. λ_team = 0.32×(pitcher_blended/0.4808)×(team_runs/4.45). P(NRFI)=e^(-λ_away-λ_home) |
| er_per_ip / FIP blend | `engine/evaluators.py:876-895` | F11.12 / I4 | ip = p.get('IP',1) or 1.0 (falsy→1.0 guard). FIP: explicit `if ip > 0 else 4.50`. Blend 25% ERA + 75% FIP per Plan 9 §9A |
| _implied_prob in discord_post | `engine/discord_post.py:472-476` | F1.5 | Now uses implied_prob correctly (was vigged↔novig confusion) |
| CLAUDE.md (memory) | `CLAUDE.md:1-253` | — | Comprehensive memory file. Excellent: every active scalar, every gate, every open issue. |

## P1 — High (degradation / silent drift)

**Total: 156** (Open: 114 · Verified ✅: 42 · Info 📋: 0)


### Open issues (114)


#### P1-1. POISSON_CUTOFF=8.5

- **Finding ID**: CLAUDE.md NFL gate
- **Layer**: L1: Thresholds
- **Location**: `engine/thresholds.py:59`
- **Status**: ⚠️  ·  **Category**: Math  ·  **Tested**: Y — CLAUDE.md flags as pre-NFL hardening
- **Finding**: Will silently mis-route NFL REC at lines >8.5 by 5-8pp once NFL goes live
- **Evidence**: `NFL REC at line 9.5/10.5 routes to Poisson, not SIGMA fallback`
- **Next action**: Before NFL go-live: replace `line <= POISSON_CUTOFF` with `if stat in POISSON_STATS` OR route over-cutoff to Normal(μ=proj, σ=√proj)

#### P1-2. SIGMA['PC']=0.19/6.0

- **Finding ID**: Plan 6 §1C
- **Layer**: L2: Calibrated
- **Location**: `engine/calibrated.py:42`
- **Status**: ⚠️  ·  **Category**: Distribution  ·  **Tested**: Y — explicit skew=-1.93 in calibrated.py comment
- **Finding**: Within=0.142; pooled-start=0.204. Skew=-1.93 — Normal is provisional; empirical-CDF candidate at July refit
- **Evidence**: `Brier improvement >=0.005 OR keep Normal`
- **Next action**: July refit: evaluate empirical-CDF vs Normal for PC

#### P1-3. NB_R['HRR']=1.5

- **Finding ID**: shadow log
- **Layer**: L2: Calibrated
- **Location**: `engine/calibrated.py:72`
- **Status**: ⚠️  ·  **Category**: Distribution  ·  **Tested**: Y — CLAUDE.md flags refit
- **Finding**: Moment-matched from shadow log (NB(r=1.5,μ=2.0)→P(X≥2)=47.8% = empirical 48% WR n=1810). CLAUDE.md: implied r≈1.1, July refit pending.
- **Evidence**: `r refit from MLB batter game logs (within-player var/μ); ZINB tested`
- **Next action**: July refit: fix r, audit μ projection path, investigate zero-inflated NB, reset shadow log

#### P1-4. WNBA 3PM r=1.342

- **Finding ID**: 2026-06-09
- **Layer**: L2: Calibrated
- **Location**: `engine/calibrated.py:83`
- **Status**: ⚠️  ·  **Category**: Distribution  ·  **Tested**: Y — full data dump in CLAUDE.md
- **Finding**: Very heavy overdispersion (var/μ=1.708, zero_rate=0.502). Distinct from NBA r=9.15
- **Evidence**: `Empirical WR within ±5pp of model`
- **Next action**: Validate WNBA 3PM pick performance separately at n>=20

#### P1-5. COMBO Platt MISSING

- **Finding ID**: Plan 10 §A
- **Layer**: L2: Calibrated
- **Location**: `engine/calibrated.py:n/a`
- **Status**: ❌  ·  **Category**: Calibration  ·  **Tested**: Y — CLAUDE.md flags as open gate
- **Finding**: Combo path (PRA/PR/PA/RA) has NO Platt applied — wp inflated ~5pp vs individual stats
- **Evidence**: `Combo wp within ±2pp of empirical at n>=100`
- **Next action**: Gate at 27/100 graded combo picks; refit Platt for combos at gate

#### P1-6. MLB Platt MISSING

- **Finding ID**: MLB gate
- **Layer**: L2: Calibrated
- **Location**: `engine/calibrated.py:n/a`
- **Status**: ❌  ·  **Category**: Calibration  ·  **Tested**: Y
- **Finding**: MLB over_p_raw not Platt-corrected. 28/100 as of 2026-06-13.
- **Evidence**: `MLB Brier improvement >= NBA-equivalent gap`
- **Next action**: Gate at 100 MLB rows; refit

#### P1-7. BM_SHRINKAGE_WEIGHT inverted?

- **Finding ID**: Plan 10 §B
- **Layer**: L2: Calibrated
- **Location**: `engine/calibrated.py:(per CLAUDE.md)`
- **Status**: ⚠️  ·  **Category**: Calibration  ·  **Tested**: Y — CLAUDE.md flags inversion
- **Finding**: T1 w=0.75 > T3 w=0.70 but T1 has worst ROI — direction inverted
- **Evidence**: `Each tier's w fitted from empirical model_p vs implied_p gap`
- **Next action**: Refit per-family at n>=150 graded picks/family

#### P1-8. copula_joint_approx (linear)

- **Finding ID**: F7.2 / Plan 10
- **Layer**: L3: Quant Math
- **Location**: `engine/quant/copula.py:109-122`
- **Status**: ⚠️  ·  **Category**: Math  ·  **Tested**: Y — explicit deflator + Plan 10 ref
- **Finding**: Linear interp p_indep + ρ·(min - p_indep), now × 0.87 deflator (corrects +8-29% bias). Ranking-only.
- **Evidence**: `RMSE(approx vs MC) < 20% across grid`
- **Next action**: Add unit test: approx is monotonic in ρ; sanity-check vs MC across ρ-grid

#### P1-9. calc_combo_prob

- **Finding ID**: Plan 10 §A
- **Layer**: L4: Prob Core
- **Location**: `engine/prob_core.py:163-167`
- **Status**: ⚠️  ·  **Category**: Math  ·  **Tested**: Y — RA skew flagged in calibrated.py
- **Finding**: Wraps _combo_mu_sigma into Normal CDF. PRA skew=0.74 (acceptable); RA skew=0.94 (highest, REB+AST small counts)
- **Next action**: RA: gate at combo n>=100 + check Brier; consider NB for RA only

#### P1-10. build_alt_spread_parlay (daily lay)

- **Finding ID**: —
- **Layer**: L5: Sizing
- **Location**: `engine/parlays.py:?`
- **Status**: ❓  ·  **Category**: Logic  ·  **Tested**: N
- **Finding**: 2-3 leg alt-spread parlays for daily lay
- **Next action**: Read full module + test EV under cap +100

#### P1-11. daily lay edge formula

- **Finding ID**: F6.9
- **Layer**: L5: Sizing
- **Location**: `engine/parlays.py:278`
- **Status**: ⚠️  ·  **Category**: Math  ·  **Tested**: Y — F6.9 verified
- **Finding**: `edge = cover_prob - implied` uses VIGGED implied. Inconsistent with per-leg edge convention (novig)
- **Evidence**: `Edge baseline matches per-leg edge convention OR rationale documented`
- **Next action**: Switch to novig fair when both legs are available; document choice

#### P1-12. size_daily_lay

- **Finding ID**: —
- **Layer**: L5: Sizing
- **Location**: `engine/sizing.py:?`
- **Status**: ❓  ·  **Category**: Sizing  ·  **Tested**: N
- **Finding**: 0.25u floor (Plan 9 §9K) for daily lay
- **Next action**: Verify floor + cap math against thresholds

#### P1-13. G4/G5/G10

- **Finding ID**: —
- **Layer**: L6: Gates
- **Location**: `engine/gates.py:205/209/213`
- **Status**: ❓  ·  **Category**: Gate  ·  **Tested**: N
- **Finding**: Need full inspection
- **Next action**: Read 195-215; confirm logic

#### P1-14. G_TB WP gate missing in gates.py

- **Finding ID**: F9.15
- **Layer**: L6: Gates
- **Location**: `engine/gates.py:—`
- **Status**: ❌  ·  **Category**: Gate  ·  **Tested**: Y — F9.15 verified
- **Finding**: TB WP floor 0.60 only in output_format.py:226 checklist; not enforced in gates.py. TB pick at WP<0.60 admits then fails cosmetic checklist later
- **Evidence**: `Tests confirm TB pick at wp=0.58 is blocked, not admitted-then-flagged`
- **Next action**: Add WP gate to check_prop_gates: `if stat in _STAT_MIN_WIN_PROB and wp < threshold: return False, 'G_TB_WP'`

#### P1-15. GLC (game-line correlation)

- **Finding ID**: —
- **Layer**: L8: Correlation
- **Location**: `engine/correlation.py:?`
- **Status**: ❓  ·  **Category**: Logic  ·  **Tested**: N
- **Finding**: Need to read full impl
- **Next action**: Read + document

#### P1-16. TT divergence

- **Finding ID**: —
- **Layer**: L8: Correlation
- **Location**: `engine/correlation.py:?`
- **Status**: ❓  ·  **Category**: Logic  ·  **Tested**: N
- **Finding**: Team-total divergence filter
- **Next action**: Read + document

#### P1-17. Cross-type correlations

- **Finding ID**: —
- **Layer**: L8: Correlation
- **Location**: `engine/correlation.py:?`
- **Status**: ❓  ·  **Category**: Logic  ·  **Tested**: N
- **Finding**: Test file exists: test_cross_type_correlations.py
- **Next action**: Read tests + impl

#### P1-18. saber_team accumulation

- **Finding ID**: —
- **Layer**: L9: Evaluators
- **Location**: `engine/evaluators.py:?`
- **Status**: ❓  ·  **Category**: Logic  ·  **Tested**: N
- **Finding**: First batter entry wins per team
- **Next action**: Verify all batters have consistent saber_team

#### P1-19. Pitcher build

- **Finding ID**: —
- **Layer**: L9: Evaluators
- **Location**: `engine/evaluators.py:—`
- **Status**: ❓  ·  **Category**: Logic  ·  **Tested**: N
- **Finding**: Confirmed starter only (status==confirmed)
- **Next action**: Verify is_pitcher + status==confirmed both checked

#### P1-20. SGP Platt calibration gate

- **Finding ID**: CLAUDE.md
- **Layer**: L10: SGP
- **Location**: `engine/sgp_builder.py:—`
- **Status**: ⚠️  ·  **Category**: Calibration  ·  **Tested**: Y
- **Finding**: Current Platt over-corrects SGP legs (model→58% vs actual 69%). Gated at 70/100 slips (2026-06-13)
- **Evidence**: `Brier improvement on SGP slips`
- **Next action**: At gate: SGP-only Platt refit (separate from NBA prop Platt)

#### P1-21. mlb_sgp_builder

- **Finding ID**: —
- **Layer**: L10: SGP
- **Location**: `engine/mlb_sgp_builder.py:—`
- **Status**: ❓  ·  **Category**: Logic  ·  **Tested**: N
- **Finding**: MLB-specific SGP path
- **Next action**: Read full module; verify ρ table for MLB stats

#### P1-22. has_g13b_fail checklist

- **Finding ID**: F9.15
- **Layer**: L11: Output
- **Location**: `engine/output_format.py:227-232`
- **Status**: ⚠️  ·  **Category**: Display  ·  **Tested**: Y
- **Finding**: Includes TB WP<0.60 + HRR line-specific WP + RA. But TB check is COSMETIC ONLY — no real gate in gates.py
- **Evidence**: `Test admits TB pick at wp=0.65 and blocks at wp=0.55`
- **Next action**: Convert to enforced gate (G_TB_WP)

#### P1-23. post_daily_lay

- **Finding ID**: —
- **Layer**: L11: Output
- **Location**: `engine/discord_post.py:—`
- **Status**: ❓  ·  **Category**: Logic  ·  **Tested**: N
- **Finding**: Daily lay posting path
- **Next action**: Verify uses correct edge (F6.9 fix needed)

#### P1-24. discord_guard

- **Finding ID**: —
- **Layer**: L11: Output
- **Location**: `engine/discord_guard.py:—`
- **Status**: ❓  ·  **Category**: Defensive  ·  **Tested**: N
- **Finding**: Duplicate-post prevention
- **Next action**: Read full impl + test_card_guard_bypass.py

#### P1-25. webhook_fallback

- **Finding ID**: —
- **Layer**: L11: Output
- **Location**: `engine/webhook_fallback.py:—`
- **Status**: ❓  ·  **Category**: Defensive  ·  **Tested**: N
- **Finding**: Fallback when primary webhook fails
- **Next action**: Read

#### P1-26. pick_log_schema

- **Finding ID**: —
- **Layer**: L12: Pick Log
- **Location**: `engine/pick_log_schema.py:—`
- **Status**: ❓  ·  **Category**: Schema  ·  **Tested**: N
- **Finding**: Schema definition
- **Next action**: Read; verify columns include over_p_raw, context_verdict (per backlog #11)

#### P1-27. pick_log_lock

- **Finding ID**: audit H-8
- **Layer**: L12: Pick Log
- **Location**: `engine/pick_log_lock.py:—`
- **Status**: ❓  ·  **Category**: Defensive  ·  **Tested**: N
- **Finding**: Shared lock for concurrent capture_clv + log_picks
- **Next action**: Read; verify it's actually used everywhere

#### P1-28. pick_log_writers

- **Finding ID**: —
- **Layer**: L12: Pick Log
- **Location**: `engine/pick_log_writers.py:—`
- **Status**: ❓  ·  **Category**: IO  ·  **Tested**: N
- **Finding**: —
- **Next action**: Read

#### P1-29. pick_log_io

- **Finding ID**: —
- **Layer**: L12: Pick Log
- **Location**: `engine/pick_log_io.py:—`
- **Status**: ❓  ·  **Category**: IO  ·  **Tested**: N
- **Finding**: —
- **Next action**: Read

#### P1-30. Shadow CLV go-live gate

- **Finding ID**: CLAUDE.md
- **Layer**: L13: CLV
- **Location**: `engine/capture_clv.py:—`
- **Status**: ⚠️  ·  **Category**: Calibration  ·  **Tested**: Y
- **Finding**: 0/100 post-reform rows; 227 pre-Plan-6-10 rows archived. Gate also requires one-sided t>=1.7 on post-reform
- **Next action**: Accumulate to 100; never pool pre/post-reform

#### P1-31. grade_daily_lay

- **Finding ID**: —
- **Layer**: L14: Grading
- **Location**: `engine/?:test_grade_daily_lay.py`
- **Status**: ❓  ·  **Category**: Logic  ·  **Tested**: N
- **Finding**: —
- **Next action**: Read

#### P1-32. game_line abbrev grading

- **Finding ID**: —
- **Layer**: L14: Grading
- **Location**: `engine/?:test_game_line_abbrev_grading.py`
- **Status**: ❓  ·  **Category**: Logic  ·  **Tested**: N
- **Finding**: —
- **Next action**: Read

#### P1-33. calibrate_distributions

- **Finding ID**: —
- **Layer**: L16: Calibration Scripts
- **Location**: `engine/calibrate_distributions.py:—`
- **Status**: ❓  ·  **Category**: Tooling  ·  **Tested**: N
- **Finding**: Refit NB_R from EdgeModel DB
- **Evidence**: `Re-running on same data yields identical r values`
- **Next action**: Verify reproducibility + parameters match what was deployed (NB_R values in calibrated.py)

#### P1-34. calibrate_sigma

- **Finding ID**: —
- **Layer**: L16: Calibration Scripts
- **Location**: `engine/calibrate_sigma.py:—`
- **Status**: ❓  ·  **Category**: Tooling  ·  **Tested**: N
- **Finding**: —
- **Next action**: Read

#### P1-35. calibrate_winprob

- **Finding ID**: —
- **Layer**: L16: Calibration Scripts
- **Location**: `engine/calibrate_winprob.py:—`
- **Status**: ❓  ·  **Category**: Tooling  ·  **Tested**: N
- **Finding**: —
- **Next action**: Read

#### P1-36. nb_calibrate

- **Finding ID**: —
- **Layer**: L16: Calibration Scripts
- **Location**: `engine/nb_calibrate.py:—`
- **Status**: ❓  ·  **Category**: Tooling  ·  **Tested**: N
- **Finding**: —
- **Next action**: Read

#### P1-37. http_utils

- **Finding ID**: —
- **Layer**: L17: Data Ingestion
- **Location**: `engine/http_utils.py:—`
- **Status**: ❓  ·  **Category**: IO  ·  **Tested**: N
- **Finding**: HTTP retry/backoff helpers
- **Next action**: Read

#### P1-38. name_norm + name_utils

- **Finding ID**: —
- **Layer**: L17: Data Ingestion
- **Location**: `engine/name_norm.py / name_utils.py:—`
- **Status**: ❓  ·  **Category**: Logic  ·  **Tested**: N
- **Finding**: Player name normalization
- **Next action**: Read; verify suffix handling (Jr, III, etc.)

#### P1-39. team_resolve

- **Finding ID**: —
- **Layer**: L17: Data Ingestion
- **Location**: `engine/team_resolve.py:—`
- **Status**: ❓  ·  **Category**: Logic  ·  **Tested**: N
- **Finding**: Team abbrev resolution + team-sigma lookups
- **Next action**: Read; verify get_game_sigma + get_mlb_team_run_r

#### P1-40. test_calibrated.py

- **Finding ID**: —
- **Layer**: L21: Tests
- **Location**: `tests/test_calibrated.py:—`
- **Status**: ❓  ·  **Category**: Tests  ·  **Tested**: N
- **Finding**: Coverage exists; verify it passes + asserts the intended invariant
- **Next action**: Run; verify intent matches current behavior

#### P1-41. test_calibration_log.py

- **Finding ID**: —
- **Layer**: L21: Tests
- **Location**: `tests/test_calibration_log.py:—`
- **Status**: ❓  ·  **Category**: Tests  ·  **Tested**: N
- **Finding**: Coverage exists; verify it passes + asserts the intended invariant
- **Next action**: Run; verify intent matches current behavior

#### P1-42. test_capture_clv_game_lines.py

- **Finding ID**: —
- **Layer**: L21: Tests
- **Location**: `tests/test_capture_clv_game_lines.py:—`
- **Status**: ❓  ·  **Category**: Tests  ·  **Tested**: N
- **Finding**: Coverage exists; verify it passes + asserts the intended invariant
- **Next action**: Run; verify intent matches current behavior

#### P1-43. test_capture_clv_stat_markets.py

- **Finding ID**: —
- **Layer**: L21: Tests
- **Location**: `tests/test_capture_clv_stat_markets.py:—`
- **Status**: ❓  ·  **Category**: Tests  ·  **Tested**: N
- **Finding**: Coverage exists; verify it passes + asserts the intended invariant
- **Next action**: Run; verify intent matches current behavior

#### P1-44. test_card_guard_bypass.py

- **Finding ID**: —
- **Layer**: L21: Tests
- **Location**: `tests/test_card_guard_bypass.py:—`
- **Status**: ❓  ·  **Category**: Tests  ·  **Tested**: N
- **Finding**: Coverage exists; verify it passes + asserts the intended invariant
- **Next action**: Run; verify intent matches current behavior

#### P1-45. test_cross_type_correlations.py

- **Finding ID**: —
- **Layer**: L21: Tests
- **Location**: `tests/test_cross_type_correlations.py:—`
- **Status**: ❓  ·  **Category**: Tests  ·  **Tested**: N
- **Finding**: Coverage exists; verify it passes + asserts the intended invariant
- **Next action**: Run; verify intent matches current behavior

#### P1-46. test_daily_lay_builder_v2.py

- **Finding ID**: —
- **Layer**: L21: Tests
- **Location**: `tests/test_daily_lay_builder_v2.py:—`
- **Status**: ❓  ·  **Category**: Tests  ·  **Tested**: N
- **Finding**: Coverage exists; verify it passes + asserts the intended invariant
- **Next action**: Run; verify intent matches current behavior

#### P1-47. test_derive_team_totals.py

- **Finding ID**: —
- **Layer**: L21: Tests
- **Location**: `tests/test_derive_team_totals.py:—`
- **Status**: ❓  ·  **Category**: Tests  ·  **Tested**: N
- **Finding**: Coverage exists; verify it passes + asserts the intended invariant
- **Next action**: Run; verify intent matches current behavior

#### P1-48. test_g7b_threshold.py

- **Finding ID**: —
- **Layer**: L21: Tests
- **Location**: `tests/test_g7b_threshold.py:—`
- **Status**: ❓  ·  **Category**: Tests  ·  **Tested**: N
- **Finding**: Coverage exists; verify it passes + asserts the intended invariant
- **Next action**: Run; verify intent matches current behavior

#### P1-49. test_g9_floor.py

- **Finding ID**: —
- **Layer**: L21: Tests
- **Location**: `tests/test_g9_floor.py:—`
- **Status**: ❓  ·  **Category**: Tests  ·  **Tested**: N
- **Finding**: Coverage exists; verify it passes + asserts the intended invariant
- **Next action**: Run; verify intent matches current behavior

#### P1-50. test_game_line_abbrev_grading.py

- **Finding ID**: —
- **Layer**: L21: Tests
- **Location**: `tests/test_game_line_abbrev_grading.py:—`
- **Status**: ❓  ·  **Category**: Tests  ·  **Tested**: N
- **Finding**: Coverage exists; verify it passes + asserts the intended invariant
- **Next action**: Run; verify intent matches current behavior

#### P1-51. test_game_sigma_scaler.py

- **Finding ID**: —
- **Layer**: L21: Tests
- **Location**: `tests/test_game_sigma_scaler.py:—`
- **Status**: ❓  ·  **Category**: Tests  ·  **Tested**: N
- **Finding**: Coverage exists; verify it passes + asserts the intended invariant
- **Next action**: Run; verify intent matches current behavior

#### P1-52. test_gate_suspension.py

- **Finding ID**: —
- **Layer**: L21: Tests
- **Location**: `tests/test_gate_suspension.py:—`
- **Status**: ❓  ·  **Category**: Tests  ·  **Tested**: N
- **Finding**: Coverage exists; verify it passes + asserts the intended invariant
- **Next action**: Run; verify intent matches current behavior

#### P1-53. test_glc_extended.py

- **Finding ID**: —
- **Layer**: L21: Tests
- **Location**: `tests/test_glc_extended.py:—`
- **Status**: ❓  ·  **Category**: Tests  ·  **Tested**: N
- **Finding**: Coverage exists; verify it passes + asserts the intended invariant
- **Next action**: Run; verify intent matches current behavior

#### P1-54. test_grade_daily_lay.py

- **Finding ID**: —
- **Layer**: L21: Tests
- **Location**: `tests/test_grade_daily_lay.py:—`
- **Status**: ❓  ·  **Category**: Tests  ·  **Tested**: N
- **Finding**: Coverage exists; verify it passes + asserts the intended invariant
- **Next action**: Run; verify intent matches current behavior

#### P1-55. test_h1_constraint_chain.py

- **Finding ID**: —
- **Layer**: L21: Tests
- **Location**: `tests/test_h1_constraint_chain.py:—`
- **Status**: ❓  ·  **Category**: Tests  ·  **Tested**: N
- **Finding**: Coverage exists; verify it passes + asserts the intended invariant
- **Next action**: Run; verify intent matches current behavior

#### P1-56. test_hard_rules.py

- **Finding ID**: —
- **Layer**: L21: Tests
- **Location**: `tests/test_hard_rules.py:—`
- **Status**: ❓  ·  **Category**: Tests  ·  **Tested**: N
- **Finding**: Coverage exists; verify it passes + asserts the intended invariant
- **Next action**: Run; verify intent matches current behavior

#### P1-57. test_hrr_over_low_line_gate.py

- **Finding ID**: —
- **Layer**: L21: Tests
- **Location**: `tests/test_hrr_over_low_line_gate.py:—`
- **Status**: ❓  ·  **Category**: Tests  ·  **Tested**: N
- **Finding**: Coverage exists; verify it passes + asserts the intended invariant
- **Next action**: Run; verify intent matches current behavior

#### P1-58. test_kelly_market_mult.py

- **Finding ID**: —
- **Layer**: L21: Tests
- **Location**: `tests/test_kelly_market_mult.py:—`
- **Status**: ❓  ·  **Category**: Tests  ·  **Tested**: N
- **Finding**: Coverage exists; verify it passes + asserts the intended invariant
- **Next action**: Run; verify intent matches current behavior

#### P1-59. test_killshot_v2.py

- **Finding ID**: —
- **Layer**: L21: Tests
- **Location**: `tests/test_killshot_v2.py:—`
- **Status**: ❓  ·  **Category**: Tests  ·  **Tested**: N
- **Finding**: Coverage exists; verify it passes + asserts the intended invariant
- **Next action**: Run; verify intent matches current behavior

#### P1-60. Test gaps to add

- **Finding ID**: —
- **Layer**: L21: Tests
- **Location**: `tests/:—`
- **Status**: ❌  ·  **Category**: Tests  ·  **Tested**: Y
- **Finding**: Missing tests identified during audit
- **Evidence**: `All 5 tests added + green`
- **Next action**: Add: G_TB_WP gate test, F6.9 daily lay edge test, NB CDF push-redistribution test, copula approx vs MC RMSE test, KILLSHOT invariant mutation test

#### P1-61. post_nrfi_bonus

- **Finding ID**: —
- **Layer**: L22: Operational
- **Location**: `post_nrfi_bonus.py:—`
- **Status**: ❓  ·  **Category**: Logic  ·  **Tested**: N
- **Finding**: Separate NRFI bonus posting path
- **Next action**: Read

#### P1-62. Combo Platt refit gate (27/100)

- **Finding ID**: Plan 10 §A
- **Layer**: L_OPEN: Active Open Issues
- **Location**: `engine/calibrate_platt.py:—`
- **Status**: ❌  ·  **Category**: Calibration  ·  **Tested**: Y
- **Finding**: Combo path has NO Platt — wp inflated ~5pp. 27/100 graded.
- **Evidence**: `Combo Brier improves`
- **Next action**: At gate: separate combo Platt refit; PRA/PR/PA/RA→T1B

#### P1-63. MLB Platt refit gate (28/100)

- **Finding ID**: —
- **Layer**: L_OPEN: Active Open Issues
- **Location**: `engine/calibrate_platt.py:—`
- **Status**: ❌  ·  **Category**: Calibration  ·  **Tested**: Y
- **Finding**: MLB raw probs not calibrated. 28/100.
- **Evidence**: `MLB Brier improves`
- **Next action**: At gate: MLB Platt refit

#### P1-64. SGP Platt gate (70/100)

- **Finding ID**: —
- **Layer**: L_OPEN: Active Open Issues
- **Location**: `engine/calibrate_platt.py:—`
- **Status**: ❌  ·  **Category**: Calibration  ·  **Tested**: Y
- **Finding**: Current Platt over-corrects SGP legs. 70/100.
- **Next action**: At gate: SGP-only Platt refit

#### P1-65. Family bootstrap (Plan 9 §9F)

- **Finding ID**: —
- **Layer**: L_OPEN: Active Open Issues
- **Location**: `—:—`
- **Status**: ⚠️  ·  **Category**: Calibration  ·  **Tested**: Y
- **Finding**: n>=150/family for 95% CI on ROI + BM_SHRINKAGE_WEIGHT per-family refit
- **Next action**: Accumulate; flag families to retire

#### P1-66. G8B/G8C/G8D recheckpoints

- **Finding ID**: gate_audit_2026-05-26
- **Layer**: L_OPEN: Active Open Issues
- **Location**: `engine/gates.py:—`
- **Status**: ⚠️  ·  **Category**: Gate  ·  **Tested**: Y
- **Finding**: n>=30 post-gate per gate (blocked picks not logged — needs shadow)
- **Next action**: Run shadow with gates disabled to backfill

#### P1-67. REC Poisson→NB at NFL go-live

- **Finding ID**: Plan 10
- **Layer**: L_OPEN: Active Open Issues
- **Location**: `engine/calibrated.py:—`
- **Status**: ⚠️  ·  **Category**: Distribution  ·  **Tested**: Y
- **Finding**: Move REC to NB when NFL go-live + n>=50
- **Next action**: Set at NFL go-live

#### P1-68. HRR r=1.5→~1.1 July refit

- **Finding ID**: CLAUDE.md
- **Layer**: L_OPEN: Active Open Issues
- **Location**: `engine/calibrated.py:—`
- **Status**: ❌  ·  **Category**: Distribution  ·  **Tested**: Y
- **Finding**: Refit r, audit μ projection path, investigate ZINB, reset shadow log
- **Evidence**: `Shadow WR matches model at refit`
- **Next action**: July 2026 refit

#### P1-69. Game-line edge floor ~0.03-0.05

- **Finding ID**: CLAUDE.md
- **Layer**: L_OPEN: Active Open Issues
- **Location**: `engine/gates.py:—`
- **Status**: ⚠️  ·  **Category**: Gate  ·  **Tested**: Y
- **Finding**: n>=50 graded game lines required
- **Next action**: Set when n>=50

#### P1-70. BM direction inverted (T1>T3)

- **Finding ID**: Plan 10 §B
- **Layer**: L_OPEN: Active Open Issues
- **Location**: `engine/calibrated.py:—`
- **Status**: ❌  ·  **Category**: Calibration  ·  **Tested**: Y
- **Finding**: T1 w=0.75 > T3 w=0.70 but T1 has worst ROI
- **Evidence**: `Direction matches calibration quality`
- **Next action**: Refit per-family at n>=150

#### P1-71. REGULAR_SEASON_MINUTES_SCALAR

- **Finding ID**: H3
- **Layer**: L19: EdgeModel calibrators
- **Location**: `engine/nba_projector.py:310-316`
- **Status**: ⚠️  ·  **Category**: Calibration  ·  **Tested**: Y — refit log
- **Finding**: VERIFIED 2026-06-16. spot=1.6124 (+61%) flag remains: ROLE_MINUTE_PRIOR.spot=6.0 likely root cause. v4 refit 2026-05-10 on 4653 player-games. PLAN 7 #4 introduces SPOT_MINUTES_FILTER (Heckman-class selection)
- **Evidence**: `Comment cites ratio 1.0273; scalar 1.5695→1.6124`
- **Next action**: Investigate two-stage hurdle model when SPOT_MINUTES_FILTER backtest sample lands

#### P1-72. REGULAR_SEASON_STAT_SCALAR

- **Finding ID**: H2
- **Layer**: L19: EdgeModel calibrators
- **Location**: `engine/nba_projector.py:327-335`
- **Status**: ⚠️  ·  **Category**: Calibration  ·  **Tested**: Y — backtest n=4653
- **Finding**: VERIFIED 2026-06-16. blk=1.0608 (largest correction); pts=1.0019, ast=1.0120, reb=1.0264, fg3m=1.0231, stl=1.0017, tov=1.000. H2 risk: BLK has lowest mean (0.462) → small absolute bias becomes large multiplicative scalar; risk of in-sample fit on the BLK slice.
- **Evidence**: `Inline dict`
- **Next action**: Confirm BLK scalar holds on out-of-sample; consider per-position BLK scalar

#### P1-73. PLAYOFF_RATE_DEFLATORS

- **Finding ID**: C2/H4
- **Layer**: L19: EdgeModel calibrators
- **Location**: `engine/nba_projector.py:353-359`
- **Status**: ⚠️  ·  **Category**: Calibration  ·  **Tested**: Partial — single-season fit
- **Finding**: VERIFIED 2026-06-16. pts=0.934, ast=0.845, fg3m=0.948, blk=1.152 (inflator t=-2.74, n=1049). C2 from prior audit: blk=1.152 may double-count selection effect (more half-court ≠ all blocks). H4: ast=0.845 vs empirical 0.870 — undercorrects 2.5pp per audit_module1_draft.
- **Evidence**: `Inline dict 353-359; comments at 343-354`
- **Next action**: P0: refit BLK deflator against multi-year aggregate; verify AST against 2024-25 ground truth

#### P1-74. compute_distribution() CV (H5 from prior audit)

- **Finding ID**: H5
- **Layer**: L19: EdgeModel calibrators
- **Location**: `engine/nba_projector.py:~1080-1090`
- **Status**: ❓  ·  **Category**: Math  ·  **Tested**: N
- **Finding**: H5 (audit_module1_draft 2026-05-30): CV values for compute_distribution() under-estimate fg3m (0.65 vs NB-implied 0.94) and ast (0.55 vs 0.71). Cannot fully verify from current read — need to find the CV table.
- **Evidence**: `Refer to audit_module1_draft.md`
- **Next action**: Read compute_distribution() body to find CV table and compare to docs/calibration_results.json NB(r) values

#### P1-75. Pace formula consistency (H8)

- **Finding ID**: H8
- **Layer**: L19: EdgeModel calibrators
- **Location**: `engine/nba_projector.py:1298-1332`
- **Status**: ❓  ·  **Category**: Math  ·  **Tested**: N
- **Finding**: H8 prior audit: implied_total path vs game_pace path inconsistent for AST/STL/BLK. Code at L1387: game_pace × (PACE_PO/PACE)≈0.970 scalar applied in playoff path only.
- **Evidence**: `L1387 inline scalar; comments at L1380-1410`
- **Next action**: Trace projection code at L1370-1410 to confirm units match training (per-poss everywhere)

#### P1-76. STL/BLK/TOV Poisson assumption (M5)

- **Finding ID**: M5
- **Layer**: L19: EdgeModel calibrators
- **Location**: `engine/calibrate_distributions.py:309-311`
- **Status**: ❓  ·  **Category**: Math  ·  **Tested**: Partial
- **Finding**: M5: NBA STL/BLK/TOV deployed as Poisson. docs/calibration_results.json: stl var/mu=1.072, blk=1.113, tov=1.050 — all 'Poisson acceptable' but overdispersed_frac >0.60 for all three. Possible underestimation of variance.
- **Evidence**: `calibration_results.json: stl Poisson, blk Poisson, tov Poisson`
- **Next action**: Read calibrate_distributions.py L309-311 to confirm deploy logic; consider NB switch if backtest justifies

#### P1-77. Defensive splits — no recency weighting (H7)

- **Finding ID**: H7
- **Layer**: L19: EdgeModel calibrators
- **Location**: `engine/projections_db.py:495-545`
- **Status**: ❓  ·  **Category**: Math  ·  **Tested**: N
- **Finding**: H7 prior audit: within-season DvP splits have NO recency weighting. Early-season schedule strength bias risk.
- **Next action**: Read projections_db.py L495-545; consider time-decay or rolling window

#### P1-78. injury_parser.py

- **Finding ID**: —
- **Layer**: L24: EdgeModel injury_parser
- **Location**: `engine/injury_parser.py:1-651`
- **Status**: ❓  ·  **Category**: Logic  ·  **Tested**: Partial
- **Finding**: 651 LOC. _POS_FLOW verified (I5). Q/GTD/P binary in/out design (I6: economically sound). REDISTRIB_PRIMARY_SHARE=0.50, REDISTRIB_EFFICIENCY=0.90, REDISTRIB_MIN_ELIGIBLE=8.0.
- **Next action**: Deep-read for fetch retries / report timestamps / status mapping

#### P1-79. calibrate_distributions.py

- **Finding ID**: I11
- **Layer**: L25: EdgeModel calibration
- **Location**: `engine/calibrate_distributions.py:1-538`
- **Status**: ❓  ·  **Category**: Tooling  ·  **Tested**: N
- **Finding**: I11: does NOT auto-update live engine — manual application required (correct engineering separation, but process risk).
- **Next action**: Deep-read for the deploy gate; confirm calibration_results.json is what's loaded by nba_projector

#### P1-80. backtest_projections.py

- **Finding ID**: —
- **Layer**: L25: EdgeModel calibration
- **Location**: `engine/backtest_projections.py:1-775`
- **Status**: ❓  ·  **Category**: Tooling  ·  **Tested**: N
- **Finding**: 775 LOC backtest harness. Sets SPOT_MINUTES_FILTER via attribute assignment per code comment.
- **Next action**: Deep-read for seed control, MAE reporting, distribution coverage tests

#### P1-81. mlb_stats_fetcher.py

- **Finding ID**: —
- **Layer**: L26: EdgeModel data fetchers
- **Location**: `engine/mlb_stats_fetcher.py:1-621`
- **Status**: ❓  ·  **Category**: Data  ·  **Tested**: N
- **Finding**: 621 LOC. MLB stats fetch. Feeds projections.db / DraftKings-style projections.
- **Next action**: Deep-read — check API key handling, rate limiting, idempotency

#### P1-82. nhl_stats_fetcher.py

- **Finding ID**: —
- **Layer**: L26: EdgeModel data fetchers
- **Location**: `engine/nhl_stats_fetcher.py:1-631`
- **Status**: ❓  ·  **Category**: Data  ·  **Tested**: N
- **Finding**: 631 LOC. NHL stats fetch.
- **Next action**: Deep-read — verify season handling, playoff vs RS labeling

#### P1-83. wnba_stats_fetcher.py

- **Finding ID**: —
- **Layer**: L26: EdgeModel data fetchers
- **Location**: `engine/wnba_stats_fetcher.py:1-436`
- **Status**: ❓  ·  **Category**: Data  ·  **Tested**: N
- **Finding**: 436 LOC. WNBA stats fetch. CLAUDE.md gate: 'WNBA COMBO rho needs n=500+ player-games'.
- **Next action**: Verify count progress against gate target

#### P1-84. csv_writer.py

- **Finding ID**: —
- **Layer**: L26: EdgeModel data fetchers
- **Location**: `engine/csv_writer.py:1-575`
- **Status**: ❓  ·  **Category**: Output  ·  **Tested**: N
- **Finding**: 575 LOC. SaberSim-schema CSV writer; fetch_nba_implied_totals; _odds_api_get.
- **Next action**: Verify CSV column schema matches JonnyParlay reader; verify odds API auth flow

#### P1-85. secrets_config.py

- **Finding ID**: —
- **Layer**: L27: EdgeModel infra
- **Location**: `engine/secrets_config.py:1-165`
- **Status**: ❓  ·  **Category**: Security  ·  **Tested**: N
- **Finding**: 165 LOC. Secret/API key loader.
- **Next action**: Deep-read — verify no key leaks to logs, env precedence order

#### P1-86. generate_projections.py

- **Finding ID**: C3
- **Layer**: L28: EdgeModel generate
- **Location**: `engine/generate_projections.py:1-728`
- **Status**: ⚠️  ·  **Category**: Orchestration  ·  **Tested**: Partial — code exists, not backtested
- **Finding**: Entry point. Verified Vegas constraint (constrain_team_totals L100+). C3 (audit_module1): dk_std excluded from _CONSTRAINT_SCALE_KEYS. MITIGATED at L587-594 by post-scale recompute using DK_STD_COEFF × scaled proj_pts, floored at DK_STD_FLOOR. Effective fix exists.
- **Evidence**: `L587-594 implied_std recompute block`
- **Next action**: Re-validate C3 closure with sample post-scale projections; confirm implied_std logic produces sensible σ for upscaled stars

#### P1-87. No EdgeModel CSV age refusal

- **Finding ID**: S4a-2
- **Layer**: L31: Step 4a — STALE audit
- **Location**: `engine/run_picks.py:574-602,748-755`
- **Status**: ❌  ·  **Category**: Data freshness  ·  **Tested**: N
- **Finding**: find_csvs sorts by mtime DESC and shows user the mtime in the [1] selection list, but does NOT refuse a CSV older than N hours. If user picks yesterday's CSV from the menu by mistake (e.g. selecting [1] when [1] is yesterday's file), projections fire against tomorrow's slate with no warning. Display-only, not gating.
- **Evidence**: `L596 sort by mtime; L748 mtime display; no age gate`
- **Next action**: Add age check: if selected CSV mtime > 18h old, prompt 'CSV is X hours old, continue? [y/N]'. Or: refuse hard at >36h. Mirrors health_check.py:249 projections.db gate (>48h warn).

#### P1-88. No injury-report age gate

- **Finding ID**: S4a-4
- **Layer**: L31: Step 4a — STALE audit
- **Location**: `engine/injury_parser.py (EdgeModel):_REPORT_HOURS`
- **Status**: ❌  ·  **Category**: Data freshness  ·  **Tested**: N
- **Finding**: _REPORT_HOURS tries multiple timestamps for today's report (per EdgeModel comment), but does NOT log most-recent-report timestamp anywhere downstream. If the morning report fetch fails and only a stale prior-day report is available, redistribution bumps fire against outdated data with no warning.
- **Evidence**: `EdgeModel/engine/injury_parser.py _REPORT_HOURS block`
- **Next action**: Add: log most-recent successful report timestamp; warn if >4h before tip-off; consider abort if >24h.

#### P1-89. G2 (20% edge ceiling) — silent removal

- **Finding ID**: S4b-3
- **Layer**: L32: Step 4b — Gates audit
- **Location**: `engine/gates.py:N/A — absent`
- **Status**: ❌  ·  **Category**: Logic  ·  **Tested**: N — no test_g2_edge_ceiling.py
- **Finding**: G2 referenced in multiple audit docs as 'edge ≥ 0.20 (0.28 for soft O0.5) → block' (docs/archive/audits/audit_2026-05-25_trackB.md:113, gate_audit_2026-05-26.md:284, docs/archive/audits/math_audit_s11_13.md:64). NO ENFORCEMENT in current code. grep 'edge.*0\.20|EDGE_CAP|edge_cap' engine/*.py → only _is_soft_o05 at gates.py:203 used by G4/G5. 25%+ edges now pass un-gated.
- **Evidence**: `grep shows zero edge-ceiling enforcement; multiple math audits explicitly relied on G2 as backstop (docs/archive/audits/math_audit_s9_10.md:243)`
- **Next action**: EITHER (a) restore G2 ceiling — extreme-error backstop all prior audits relied on, OR (b) document deliberate removal in CHANGELOG + audit history. Currently silent regression.

#### P1-90. calibrate_platt.py — scope gap for combo/MLB

- **Finding ID**: S4b-13
- **Layer**: L32: Step 4b — Gates audit
- **Location**: `engine/calibrate_platt.py:13 (usage)`
- **Status**: ⚠️  ·  **Category**: Tooling  ·  **Tested**: N
- **Finding**: Refit script only supports --sport NBA|NHL|all. No --segment {single,combo,mlb} flag. Blocks closure of TOP BUGS #2 and #3 — combo/MLB Platt cannot be fit without script extension.
- **Evidence**: `calibrate_platt.py docstring shows only --sport`
- **Next action**: Extend calibrate_platt.py to emit COMBO_PLATT_A/B (PRA/PR/PA/RA pooled) and MLB_PLATT_A/B (per-stat). Wire into prob_core._platt_calibrate_prop dispatch.

#### P1-91. calc_combo_prob (correlated Normal)

- **Finding ID**: S4c-3
- **Layer**: L33: Step 4c — Math audit
- **Location**: `engine/prob_core.py:138-172`
- **Status**: ⚠️  ·  **Category**: Math  ·  **Tested**: N — no test_combo_correlation_sigma
- **Finding**: Combo math: μ_combo = Σ μ_i (component projections), σ²_combo = Σ σ²_i + 2·Σ ρ_ij·σ_i·σ_j (proper joint variance). Then over/under via normal_cdf at (line - μ)/σ. CORRELATIONS calibrated 2026-06-04 from 202 WNBA players / 13,322 games (COMBO_RHO_WNBA at calibrated.py:118-122). σ_combo floor of max(σ, 2.0) at prob_core.py:160 — questionable for PRA where σ should be ~10+; floor only binds in degenerate (0-projection) cases. ISSUE: combo result NOT Platt-calibrated (S4b-8) → ~5pp inflation persists despite correct joint math.
- **Evidence**: `prob_core.py:160 'sigma_combo = max(var ** 0.5, 2.0)' + WNBA early-season scaling at :164`
- **Next action**: Validate σ_combo floor=2.0 doesn't suppress short-projection edges; primary follow-up is the combo Platt refit (S4b-8).

#### P1-92. Copula MC vs Approx — NBA SGP uses MC, MLB SGP uses Approx

- **Finding ID**: S4c-4
- **Layer**: L33: Step 4c — Math audit
- **Location**: `engine/sgp_builder.py + mlb_sgp_builder.py + quant/copula.py:sgp:571-575, mlb:291, cop:113-122`
- **Status**: ❌  ·  **Category**: Math  ·  **Tested**: N — no test asserting MC ≈ Approx within tolerance
- **Finding**: ASYMMETRY: NBA SGP ranks 91k combos via _copula_joint_prob MC at n_samples=300 (SE≈2.5% at joint≈0.40). MLB SGP ranks via _copula_joint_approx (linear interp p_indep + ρ̄·(p_min - p_indep), with 0.87 deflator from Plan 10 §Z). Approx documented as +8% (3-leg) to +29% (4-leg low-p) optimistically biased before 0.87 deflator. After deflator: residual bias ±5-15% depending on (n_legs, p_distribution, ρ̄). MLB SGP rankings are therefore systematically less accurate than NBA. NBA also drops to n=300 (was 4000 per docstring) — 8.3× more variance than baseline.
- **Evidence**: `sgp_builder.py:571 'n_samples=300 gives SE≈2.5% at joint≈0.40, tighter than the 15-20% relative error of the equicorrelation approx'`
- **Next action**: (a) Switch MLB SGP to MC at n=300 to match NBA (cost: ~600ms per build vs negligible approx; not a hot path — runs once per build). (b) Consider raising NBA n=300 → 1000 (SE drops to ~1.4%) for borderline near-ideal ranking.

#### P1-93. F6.9 — Daily lay parlay edge baseline vigged (TOP BUG #12)

- **Finding ID**: S4c-6
- **Layer**: L33: Step 4c — Math audit
- **Location**: `engine/parlays.py:274-278`
- **Status**: ❌  ·  **Category**: Math  ·  **Tested**: N
- **Finding**: CONFIRMED. parlays.py:278 `edge = cover_prob - implied` where implied = vigged implied prob (line 274 `implied = abs(odds) / (abs(odds) + 100.0) if odds < 0 else 100.0 / (odds + 100.0)`). Comment 276-277 acknowledges 'Raw vigged implied (not no-vig) — alt-spread lines are one-sided, making no-vig impossible. Conservative: vigged implied is harder to beat at 0.025 threshold.' BUT: vig on -110/-110 is ~4.5pp, on -145 is ~3pp, so the MIN_LEG_EDGE_DAILY=0.025 threshold is effectively 5.5-7.5pp net-of-vig. Picks with real 4-5pp edge are wrongly rejected. The 'one-sided alt-spread' rationale is wrong — opp side ALWAYS exists at a corresponding alt line at same book (just flipped); no-vig is computable.
- **Evidence**: `parlays.py:276-277 explicit comment 'Raw vigged implied (not no-vig)'`
- **Next action**: Replace `implied` with no-vig: lookup the opposing alt spread at the same book/line, run no_vig() pairwise, use the result. If matching opp line not found, fall back to a fixed -110 vig assumption (deflate vigged implied by ~2.3pp) rather than using vigged implied directly. Move threshold to 0.030 net-of-vig if conservatism is desired.

#### P1-94. Edge ceiling — score-side only, NOT pick-side

- **Finding ID**: S4c-9
- **Layer**: L33: Step 4c — Math audit
- **Location**: `engine/prob_core.py + sizing_core.py:pc:197-205, sc:kelly_units`
- **Status**: ❌  ·  **Category**: Logic  ·  **Tested**: N — no test_g2_or_kelly_edge_cap
- **Finding**: pick_score() at prob_core.py:197 caps e_n at 100 (corresponds to 15% edge ceiling for ranking only). Comment line 207 explicitly: 'Kelly sizing uses raw edge'. With G2 removed (S4b-3), this means a pick with raw edge=0.40 gets ranked as if edge=0.15 BUT sized via Kelly on the full 0.40 → wildly oversized. KILLSHOT picks are at most ~3-4u; a non-KILLSHOT pick with bogus 40% edge could size into multi-u stakes that score below KILLSHOT but blow the daily cap on a single bad pick.
- **Evidence**: `prob_core.py:207 'Kelly sizing uses raw edge'`
- **Next action**: Either (a) restore G2 (edge ≥ 0.20 → block), OR (b) cap Kelly input edge at 0.20 in kelly_units(), OR (c) document acceptance and rely on daily 12u cap + per-sport 8u cap to bound damage. Recommend (a) for clearest intent.

#### P1-95. NB_R[REB] vs EdgeModel JSON

- **Finding ID**: S4d-1
- **Layer**: L34: Step 4d — Calibration audit
- **Location**: `engine/calibrated.py:68`
- **Status**: ❌  ·  **Category**: Calibration drift / Jensen bias  ·  **Tested**: Verified: EdgeModel JSON r=13.16 vs JP source r=14.7 — formula difference confirmed in calibrate_distributions.py:162-225
- **Finding**: JonnyParlay NB_R[REB]=14.7 but EdgeModel docs/calibration_results.json (mtime 2026-05-30, same date as JP comment) reports nb_r=13.16 with note 'var/mu=1.387 — overdispersed; NB(r=13.16)'. Same dataset (582 players, 69773 game-logs, var/mu=1.387). The EdgeModel calibrate_distributions.py script was updated to use Jensen-corrected MoM (r=Σ(n·μ)/Σ(n·(var−μ)/μ)); the old formula (r=Σ(n·μ²)/Σ(n·(var−μ))) upweights high-μ players quadratically, inflating r for high-mean stats. JP picked up old-formula r=14.7 and was never re-synced. Higher r → tighter NB → systematically underestimates downside tail variance for REB. Impact: ~10% relative bias in OVER/UNDER edge for REB props at typical lines.
- **Evidence**: `engine/calibrated.py:68 "REB": 14.7  # ... EdgeModel JSON: r=13.16 (same n, same date)`
- **Next action**: Sync JP NB_R[REB] from 14.7 to 13.16 (or re-run engine/calibrate_distributions.py --sport NBA --save and copy the value). Update comment to reference Jensen-corrected method.

#### P1-96. NB_R[AST] vs EdgeModel JSON

- **Finding ID**: S4d-2
- **Layer**: L34: Step 4d — Calibration audit
- **Location**: `engine/calibrated.py:67`
- **Status**: ❌  ·  **Category**: Calibration drift / Jensen bias  ·  **Tested**: Verified: same n_players, same n_games, same var/mu in both sources — Δ purely formulaic
- **Finding**: JonnyParlay NB_R[AST]=12.16 but EdgeModel docs/calibration_results.json reports nb_r=9.65 (same dataset 582 players, 69773 games, var/mu=1.323). Same Jensen-bias root cause as REB. AST is more affected proportionally (Δ=26% relative on r) because mu is smaller (mu=2.88 vs 4.70 for REB). Higher r=12.16 vs correct 9.65 → underestimates AST downside tail → biased OVER probabilities downward, UNDER upward.
- **Evidence**: `engine/calibrated.py:67 "AST": 12.16  # EdgeModel JSON: r=9.65`
- **Next action**: Sync JP NB_R[AST] from 12.16 to 9.65; re-run calibrate_distributions.py --sport NBA --save. Re-verify all NBA AST predictions / Platt fit after refit.

#### P1-97. team_sigmas_wnba.json key format

- **Finding ID**: S4d-5
- **Layer**: L34: Step 4d — Calibration audit
- **Location**: `data/team_sigmas_wnba.json, engine/team_resolve.py:team_sigmas_wnba.json: all keys; team_resolve.py:25-33`
- **Status**: ❌  ·  **Category**: Routing bug — team-sigma fallback never engages  ·  **Tested**: Verified: confirmed in REPL — d.get('LV')=None, d.get('LAS')=None, d.get('NY')=None for all WNBA abbrev attempts
- **Finding**: data/team_sigmas_wnba.json is keyed by numeric WNBA team IDs ('1611661313', '1611661317', etc.) — 13 teams, n_games 55-137. But engine/team_resolve.py:get_game_sigma() calls team_data.get(h_abbr) with abbreviations resolved via resolve_team_abbrev (returns 'LV', 'NY', 'LAS', etc.). team_data.get('LV') returns None for every team → h_or_a is None → function falls back to GAME_SIGMA['WNBA'] league average on EVERY WNBA matchup. The Plan 6 §6 'relative variability scaler' (sqrt((σh²+σa²)/(2·σ̄²_league))) NEVER fires for WNBA. Other sports (NBA/NHL/MLB) use abbreviation keys correctly. Impact: team-specific WNBA sigma is loaded into memory and meansq=118.575 is computed, but no game ever benefits.
- **Evidence**: `team_sigmas_wnba.json keys: ['1611661313', '1611661317', ...] (numeric IDs); engine/team_resolve.py:26 t = team_data.get(h_abbr)`
- **Next action**: Re-key team_sigmas_wnba.json to use abbreviations ('LV', 'NY', 'LAS', 'CHI', etc.) OR add a team_id→abbrev map in engine/team_resolve.py just for WNBA. Verify by adding an assertion: 'after load, team_data.get(any_resolved_abbrev) is not None for at least 80% of league teams'.

#### P1-98. GAME_SIGMA[MLB] 4.6/4.2/3.0/4.2

- **Finding ID**: S4d-9
- **Layer**: L34: Step 4d — Calibration audit
- **Location**: `engine/calibrated.py:167`
- **Status**: ⚠️  ·  **Category**: Calibration TODO (acknowledged interim)  ·  **Tested**: Verified open TODO; independence-floor comment internally inconsistent
- **Finding**: MLB GAME_SIGMA = {'total': 4.6, 'spread': 4.2, 'team': 3.0, 'ml': 4.2} — comment: 'interim per Plan 10 §O (2026-06-07): total below independence floor (team×√2≈4.4); ml=spread (NHL precedent). Recalibrate from 8095-game DB like NBA/NHL.' This is an acknowledged TODO. Independence check: total=4.6 vs team×√2=3.0×√2=4.243, so total IS above the independence floor by 0.36, but the comment claims 'below'. Mis-stated in comment OR the team value drifted (was 3.0 documented but should be smaller). The 4.6/4.2/3.0/4.2 values plus the per-team override files give correct directionality, but no traceable calibration run.
- **Evidence**: `engine/calibrated.py:167 "MLB": {"total": 4.6, "spread": 4.2, "team": 3.0, "ml": 4.2}  # interim per Plan 10 §O`
- **Next action**: PRIORITY: re-derive MLB GAME_SIGMA from same 8095-game DB used for MLB_TEAM_RUN_R. Resolve the independence-floor comment contradiction. Track as Plan 10 §O open item — not yet closed.

#### P1-99. calibrate_platt.py --segment scope

- **Finding ID**: S4d-15
- **Layer**: L34: Step 4d — Calibration audit
- **Location**: `engine/calibrate_platt.py:170`
- **Status**: ⚠️  ·  **Category**: Scope gap — no parlay/combo segment  ·  **Tested**: Verified: arg parser confirmed; combo path absent
- **Finding**: Revising S4b-13: calibrate_platt.py DOES support --sport NBA|NHL|MLB|all (line 170). The real gap is no --segment flag for combo (parlay-combo Platt) — combo win_probs are derived from leg probabilities and may need their own Platt curve distinct from single-prop. Combo Platt is currently absent entirely (S4b-8 confirmed at evaluators.py:124). So even if we wanted to fit combo Platt, the script has no --segment hook.
- **Evidence**: `engine/calibrate_platt.py:170 parser.add_argument('--sport', default='all', help='all | NBA | NHL | MLB')  # no --segment`
- **Next action**: Add --segment single|combo flag to calibrate_platt.py. Filter pick_log by segment (legs_n=1 vs legs_n>=2) before fitting. Output A/B for each segment separately. Coordinate with S4b-8 fix (where to load combo coefficients).

#### P1-100. EdgeModel calibration_results.json coverage

- **Finding ID**: S4d-16
- **Layer**: L34: Step 4d — Calibration audit
- **Location**: `docs/calibration_results.json (EdgeModel):file-level`
- **Status**: ❌  ·  **Category**: EdgeModel pipeline incomplete  ·  **Tested**: Verified: only NBA in JSON; other sports never persisted
- **Finding**: EdgeModel docs/calibration_results.json contains ONLY NBA stats (15 rows). No NHL, no MLB_P, no MLB_B, no WNBA. The calibrate_distributions.py script supports all sports (line 318: deployed table covers NBA/MLB_P/NHL_G), but only NBA was actually executed and saved. JonnyParlay's NHL goalie SV mult=0.253, MLB pitcher OUTS mult=0.27, MLB pitcher PC mult=0.19 — none of these are verifiable against EdgeModel JSON because the JSON doesn't have those sports. The MLB_P k 'Poisson confirmed 2026-05-26 var/mu=1.031' claim in calibrate_distributions.py:325 is documented in source but not in the saved JSON.
- **Evidence**: `docs/calibration_results.json: SPORTS PRESENT=['NBA'] (verified python json.load); STATS COUNT BY SPORT: NBA=15`
- **Next action**: Run calibrate_distributions.py with --sport mlb_p, --sport mlb_b, --sport nhl_g, --sport wnba (or --output json all-sports). Save full output to docs/calibration_results.json (append, don't overwrite). Then re-run S4d-1/2-type cross-checks for MLB and NHL.

#### P1-101. compute_distribution NB_R[ast] vs JP NB_R[AST]

- **Finding ID**: S4e-2
- **Layer**: L35: Step 4e — Projection layer
- **Location**: `edgemodel/engine/nba_projector.py + JP engine/calibrated.py:nba_projector.py:1158; calibrated.py:67`
- **Status**: ❌  ·  **Category**: Producer/consumer NB_R inconsistency  ·  **Tested**: Verified: code grep shows the r=9.65 comment in projector and r=12.16 in JP
- **Finding**: nba_projector.py:compute_distribution() (line 1158) uses internal _CV table for p25/p75 output with comment 'ast: NB-implied at population mean (r=9.65, μ=2.88) → CV=0.71'. The r=9.65 here MATCHES the EdgeModel JSON (Jensen-corrected, S4d-2 finding) but DISAGREES with the deployed JP NB_R[AST]=12.16. So the SAME projector computes p25/p75 with r=9.65 while the downstream JP win-prob pipeline uses r=12.16 for the same player same stat. This is silent inconsistency — Vegas-comparable percentiles (p25/p75 in CSV) and win-prob distributions are systematically misaligned. Bias direction: r=12.16 produces tighter tails → JP underestimates downside variance vs the projector's own p25/p75 percentiles.
- **Evidence**: `nba_projector.py:1162 _CV={'pts':0.35,'reb':0.50,'ast':0.71,...}  # ast: NB-implied at population mean (r=9.65, μ=2.88) → CV=0.71. JP calibrated.py:67 NB_R['AST']=12.16`
- **Next action**: Sync as part of S4d-2 remediation. Add a startup assertion in run_picks.py: 'EdgeModel-emitted p25/p75 percentile band SHOULD be consistent with NB(NB_R[stat], proj) — log warning if abs diff > 5%'. Locks producer↔consumer once parameters live in one place.

#### P1-102. MLB OUTS/PC starts-only filter unscripted

- **Finding ID**: S4e-3
- **Layer**: L35: Step 4e — Projection layer
- **Location**: `engine/calibrate_distributions.py (EM):calibrate_distributions.py:77, 330`
- **Status**: ❌  ·  **Category**: Out-of-band calibration  ·  **Tested**: Verified: no is_starter filter anywhere in calibrate_distributions.py for MLB_P
- **Finding**: JP calibrated.py:31-32 claims 'OUTS/PC recalibrated 2026-06-05 (Plan 6 §1C) on STARTS ONLY (is_starter=1, 16,187 starts, 345 pitchers n>=10). Prior 0.311/0.375 were contaminated by relief appearances.' BUT EdgeModel calibrate_distributions.py MLB_P config (line 77) uses filter='ip_outs >= 3' (NOT is_starter=1) and the deployed-table baseline at line 330 still references OLD value 'outs Normal mult=0.311 min=1.0'. So Plan 6 §1C ran as a one-off SQL — the calibrate_distributions.py script in EdgeModel cannot regenerate JP's 0.27/0.19 numbers. The Plan 6 §1C result is NOT REPRODUCIBLE from version-controlled tooling. If a starter status changes / dataset updates, no one can re-derive these values without rebuilding the ad-hoc query.
- **Evidence**: `calibrate_distributions.py:77 "filter": "ip_outs >= 3"  # at least 1 inning pitched  -- NOT starts-only`
- **Next action**: (1) Add filter='is_starter = 1' override to MLB_P config in calibrate_distributions.py (or add a --starts-only flag). (2) Run engine/calibrate_distributions.py --sport mlb_p --starts-only --save and record output to docs/calibration_results.json. (3) Confirm output matches deployed JP 0.27/0.19 — if not, JP values may be stale or methodology differed.

#### P1-103. WNBA SIGMA filter mismatch (min>=8 vs >=20)

- **Finding ID**: S4e-4
- **Layer**: L35: Step 4e — Projection layer
- **Location**: `engine/calibrate_distributions.py (EM) + JP calibrated.py:calibrate_distributions.py:121; calibrated.py:105-113`
- **Status**: ❌  ·  **Category**: Out-of-band calibration  ·  **Tested**: Verified: cfg-vs-claim mismatch is structural
- **Finding**: Same pattern as S4e-3: JP SIGMA_WNBA comment cites Plan 6 §1C 'min>=20, 153 players n>=10 (priced population)'. EM calibrate_distributions.py WNBA config (line 121) uses filter='min >= 8' — the OLD setting that JP explicitly rejected as 'sampling artifact'. The script cannot reproduce JP's deployed SIGMA_WNBA values (0.48/0.65/0.54/0.48). Same NB_R_WNBA mismatch (S4d-12): min>=8 filter doesn't match priced-population intent. So three artifacts in calibrated.py (SIGMA_WNBA, NB_R_WNBA, COMBO_RHO_WNBA) depend on an unscripted methodology.
- **Evidence**: `calibrate_distributions.py:121 "filter": "min >= 8"  -- but JP Plan 6 §1C uses min>=20`
- **Next action**: Same as S4e-3: add --priced-population or override min_filter on the WNBA cfg entry in calibrate_distributions.py. After regeneration, paste output into docs/calibration_results.json. Sync JP values OR document why they differ.

#### P1-104. Props have no max-edge ceiling (G2 absent)

- **Finding ID**: S4f-2
- **Layer**: L36: Step 4f — Gates & Tiers audit
- **Location**: `engine/gates.py:gates.py:(no G2 found)`
- **Status**: ❌  ·  **Category**: Edge ceiling — props (missing)  ·  **Tested**: Verified: grep 'GG1\|G_PROP_MAX' shows GG1 only, no prop ceiling
- **Finding**: Refines S4b-3. Game lines have GG1 (10% max) but PROPS have no upper bound. A prop returning edge=+0.40 (implied prob 0.90 when book offers 0.50) will pass all min-edge gates and flow into sizing. Real props rarely exceed 12-15% true edge — anything higher is usually a stale line, projection blow-up, or feature pipeline bug (e.g., a player flagged active who is out). Recommend G_PROP_MAX_EDGE = 0.18-0.22 (slightly higher than GG1 since prop variance is higher) with a logged warning above 0.15.
- **Evidence**: `gates.py shows GG1 only on game-line evaluators (~line 227 in evaluate_game_line). evaluators.py prop path has NO equivalent block.`
- **Next action**: Add G_PROP_MAX_EDGE gate to gates.py. Recommended threshold 0.20. Log all skipped picks with edge, stat, projection, book line for triage. Backtest: count historical picks that would have been blocked and inspect ROI of that subset.

#### P1-105. MIN_LEG_WIN_PROB_OUTS=0.62 (tuned to stale σ=0.311)

- **Finding ID**: S4f-4
- **Layer**: L36: Step 4f — Gates & Tiers audit
- **Location**: `engine/mlb_sgp_builder.py:mlb_sgp_builder.py:70-71`
- **Status**: ❌  ·  **Category**: Stale per-leg gate constant  ·  **Tested**: Verified: grep MIN_LEG_WIN_PROB_OUTS shows hardcoded 0.62 + stale comment
- **Finding**: MLB SGP builder hard-codes MIN_LEG_WIN_PROB_OUTS = 0.62 with comment 'tuned to OUTS σ=0.311'. After Plan 6 §1C recalibration, SIGMA[OUTS] is 0.27. The lower σ tightens the OUTS distribution → win prob for any given edge is HIGHER → the 0.62 floor is no longer the same risk-adjusted bar it was set at. With σ=0.311 a 0.62 floor implied ~0.5σ above book. With σ=0.27 the same 0.62 implies ~0.43σ above book — looser gate. The floor should be re-derived against current σ to preserve the original safety margin (probably 0.64-0.65).
- **Evidence**: `mlb_sgp_builder.py:70 MIN_LEG_WIN_PROB_OUTS = 0.62  # tuned to OUTS σ=0.311  (but SIGMA[OUTS]=0.27 in calibrated.py)`
- **Next action**: Re-derive MIN_LEG_WIN_PROB_OUTS to maintain original z-score equivalent. Approximate: 0.62*(0.311/0.27) → ~0.64-0.65. Stamp the derivation in mlb_sgp_builder.py:70 comment with date and σ used.

#### P1-106. Plan 9 §9F monotonicity claim (violated by T3)

- **Finding ID**: S4f-13
- **Layer**: L36: Step 4f — Gates & Tiers audit
- **Location**: `engine/calibrated.py:calibrated.py:TIERS + BM_SHRINKAGE_WEIGHT`
- **Status**: ⚠️  ·  **Category**: Tier design principle violated  ·  **Tested**: Verified: code read confirms violation
- **Finding**: Plan 9 §9F design principle: 'lower trust → higher floor' (monotone). Actual: T2 weight=0.85 floor=0.05 (high trust, low floor — OK); T1B weight=0.80 floor=0.06; T1 weight=0.75 floor=0.07 (lower trust, higher floor — OK); T3 weight=0.70 floor=0.06 — VIOLATES monotonicity (lowest trust but middle floor — same as T1B). Either T3 floor must rise to ≥0.08 to restore monotonicity, or the §9F principle must be amended to acknowledge T3 specialty stats can't justify a high floor because n is so low. Cross-references S4f-3 + S4c-5.
- **Evidence**: `TIERS[T1].min_edge=0.07; TIERS[T1B]=0.06; TIERS[T2]=0.05; TIERS[T3]=0.06. BM_SHRINKAGE_WEIGHT: T2=0.85,T1B=0.80,T1=0.75,T3=0.70`
- **Next action**: See S4f-3 next action. Either: (a) raise T3 floor to 0.08, OR (b) document explicit §9F exception for T3 in TIERS comment with rationale (low-n stats can't sustain 0.08+ floor without going below n=30/year).

#### P1-107. PLATT_SPACE='raw' flag (must change with H3 deploy)

- **Finding ID**: S4f-15
- **Layer**: L36: Step 4f — Gates & Tiers audit
- **Location**: `engine/calibrated.py + engine/evaluators.py:calibrated.py:PLATT_SPACE`
- **Status**: ⚠️  ·  **Category**: Calibration switch flag  ·  **Tested**: Verified: grep PLATT_SPACE confirms 'raw' setting
- **Finding**: PLATT_SPACE flag governs whether Platt scaling fits in raw-prob space ('raw') or logit space ('logit'). Currently 'raw' (n=76 fit). Plan H3 §1A migration target is 'logit' with simultaneous 98/100 native-row refit and atomic 3-way deploy. If PLATT_SPACE flips without coefficient refit, prior coefficients become numerically meaningless (logit-space coefficients are different scale than raw-space). The atomic-deploy requirement is correct — but it's a fragile process: easy to forget which one is which during rollback. Add a runtime assert: 'PLATT_SPACE matches coefficient_space stamped in platt_coefs.json'.
- **Evidence**: `calibrated.py PLATT_SPACE = 'raw'  # n=76 fit. Plan H3: migrate to logit with 98/100 refit.`
- **Next action**: Add startup assert in evaluators.py: 'assert PLATT_SPACE == platt_coefs["space"]'. Prevents accidental space mismatch during deploy. Cross-references S4d-14 (raw→logit migration).

#### P1-108. SGP _pairwise_rho NBA hierarchy (9 tiers)

- **Finding ID**: S4g-4
- **Layer**: L37: Step 4g — Correlation deep-dive
- **Location**: `engine/sgp_builder.py:sgp_builder.py:247-289`
- **Status**: ⚠️  ·  **Category**: SGP correlation hierarchy unstamped  ·  **Tested**: Verified: full code read of _pairwise_rho NBA
- **Finding**: 9-tier ρ hierarchy for NBA SGP: same-team offensive flow over/over (PTS/AST/3PM) = 0.35; same-player same-direction = 0.28; same-team REB over/over = 0.20; same-team same-dir other = 0.15; cross-team overs same game = 0.10; cross-team unders same game = 0.08; same-team mixed dir = -0.10; same-player opposite dir = -0.20; unrelated = 0.00. Values are CONSERVATIVE (ρ<0.40) by design — copula estimate should be a floor not a ceiling. The 0.35 ceiling is well below the COMBO_RHO[PTS,REB]=0.333 within-player value — internally consistent IF the SGP ρ represents cross-player game-script correlation (which is structurally weaker than within-player). BUT no stamped provenance: 'calibrated from empirical NBA game-log correlation analysis' — no n, no DB, no date. Cross-references the same provenance gap noted in audit history.
- **Evidence**: `sgp_builder.py:248 docstring 'Calibrated from empirical NBA game-log correlation analysis' — no n, no date, no script`
- **Next action**: Stamp the calibration: re-run the empirical analysis with a script under engine/calibrate_sgp_rho.py, output a dated JSON, reference from sgp_builder.py:247 comment with n_games + n_pairs + DB snapshot.

#### P1-109. SGP _pairwise_rho_mlb (structural priors, no empirical fit)

- **Finding ID**: S4g-5
- **Layer**: L37: Step 4g — Correlation deep-dive
- **Location**: `engine/mlb_sgp_builder.py:mlb_sgp_builder.py:174-215`
- **Status**: ❌  ·  **Category**: MLB SGP ρ uncalibrated  ·  **Tested**: Verified: full code read; pending empirical refit
- **Finding**: MLB _pairwise_rho_mlb docstring is EXPLICIT: 'Conservative values — calibrated from structural priors, not empirical MLB game-log correlations (insufficient SGP sample as of 2026-05-29). Update these values when 100+ scored MLB SGP slips are available.' Values: cross-team same-dir pitcher = 0.10; same-team batters same-dir (HITS stacking) = 0.15; cross-team batters same-dir = 0.08; OUTS over + opposing HITS under = 0.30 (dominance correlation); pitcher+batter = 0.02. The 0.30 'pitcher dominance' value is the most consequential — it's what allows OUTS over + opposing HITS under to combine at sub-independence joint prob. Structural priors may be ±0.10 wrong in either direction. UNTIL 100+ MLB SGPs grade, this is a known calibration gap.
- **Evidence**: `mlb_sgp_builder.py:178 'calibrated from structural priors, not empirical MLB game-log correlations'`
- **Next action**: Track scored MLB SGP count weekly. When n>=100, run empirical fit (covariance of normalized residuals between leg outcomes) and update _pairwise_rho_mlb. Mid-term mitigation: stamp conservative-priors badge in operator output so SGPs are deployed with awareness.

#### P1-110. MLB 'pitcher dominance' ρ=0.30 (OUTS over + opp HITS under)

- **Finding ID**: S4g-12
- **Layer**: L37: Step 4g — Correlation deep-dive
- **Location**: `engine/mlb_sgp_builder.py:mlb_sgp_builder.py:205-211`
- **Status**: ⚠️  ·  **Category**: Highest MLB SGP ρ unvalidated  ·  **Tested**: Verified: code read
- **Finding**: OUTS-over + opposing-team-HITS-under gets ρ=0.30 — the highest MLB SGP ρ in the system. Structural prior: pitcher dominance correlates negatively with opposing hits (fewer hits → more outs → pitcher goes deeper). The 0.30 value is the most consequential MLB ρ because it's the only one that enables sub-independence joint prob for the 'pitcher dominance' SGP archetype. If 0.30 is too high (real ρ closer to 0.15-0.20), the system OVER-sizes these slips at 0.50u. If too low (real ρ closer to 0.40), the system UNDER-sizes. Both directions matter — need empirical fit ASAP.
- **Evidence**: `mlb_sgp_builder.py:211 'OUTS over + opposing HITS under — pitcher dominance ⇒ fewer opposing hits (ρ≈0.30)'`
- **Next action**: When the 100-SGP empirical fit (S4g-5 next action) is ready, prioritize the OUTS×opp-HITS pair specifically. Interim: log every OUTS+opp-HITS SGP placed with its computed copula joint vs realized outcome.

#### P1-111. apply_bm_shrinkage() — vigged implied prob

- **Finding ID**: S4h-3
- **Layer**: L38: Step 4h — Sizing layer audit
- **Location**: `engine/sizing_core.py:sizing_core.py:13-24`
- **Status**: ⚠️  ·  **Category**: BM shrinkage target  ·  **Tested**: Verified: code read; thesis-level concern, not a bug
- **Finding**: apply_bm_shrinkage uses `shrunk_p = w·model_p + (1−w)·implied_prob(odds)` — shrinks toward the VIGGED implied prob (the actual market quote). The docstring acknowledges this and argues 'edge is still measured against the no-vig prob downstream, so a model at exactly market-implied retains the vig margin as residual edge'. This is DEFENSIBLE but subtle: shrinking toward vigged means a perfectly-aligned model retains book vig as 'edge' which then sizes the bet. The pure-Bayesian alternative is to shrink toward NO-VIG implied (devig before shrink). Industry split: Levitt (2004) shrinks to vigged (book has info edge); Baker-McHale (2013) shrinks to consensus no-vig. Currently the BM_SHRINKAGE direction inversion (S4c-5, S4f-3) is a more urgent concern, but once that's fixed, the shrink-target choice should be revisited with a dual-track backtest.
- **Evidence**: `sizing_core.py:24 return w * win_prob + (1.0 - w) * implied_prob(odds)  # implied_prob is vigged`
- **Next action**: After BM weight fix (S4f-3), run dual backtest: (a) shrink to vigged (current); (b) shrink to no-vig (devig first). Compare ROI, CLV, Brier across both. Choose based on data, not theory.

#### P1-112. size_picks_vake — 5-multiplier full stack (Premium 5)

- **Finding ID**: S4h-8
- **Layer**: L38: Step 4h — Sizing layer audit
- **Location**: `engine/sizing.py:sizing.py:79-127`
- **Status**: ⚠️  ·  **Category**: Sizing stack complexity  ·  **Tested**: Verified: full code read
- **Finding**: Full VAKE stack: raw = base × market_m × var_m × corr_m × exp_m. Order applied (sort by pick_score desc): corr_m = 1.00 (1st same-game) / 0.85 (2nd) / 0.70 (3rd+); exp_m = 1.00 (1st same-stat) / 0.70 (repeat). Multiplicative stack can drive size very low: e.g. T3 NBA 3PM over at 3rd-game-occurrence repeat-stat = 1.0 × 0.10 × 0.65 × 0.70 × 0.70 = 0.0319 × base Kelly. Even with Kelly base = 1.0u, final raw = 0.032u → rounds to 0.25u floor anyway. Net effect: deep-stack T3 specialty picks are always at floor regardless of edge magnitude. R13 (stacked pitcher-corr penalty) was retired 2026-06-05 (Plan 6 §9) to avoid double-counting with G11.
- **Evidence**: `sizing.py:117 raw = base * market_m * var_m * corr_m * exp_m`
- **Next action**: Audit the 'all at floor' subset: for each VAKE-card week, count picks where final = 0.25u floor. If >50%, the stack is over-damped and the floor is effectively the sizing. Consider collapsing market_m × var_m into a single empirical-Bayes mult (DATA_GATED in CLAUDE.md).

#### P1-113. lineup_fetcher — confirmed starters ~30 min before tip

- **Finding ID**: S4i-9
- **Layer**: L39: Step 4i — Data pipeline audit
- **Location**: `edgemodel/engine/lineup_fetcher.py:lineup_fetcher.py:1-50`
- **Status**: ⚠️  ·  **Category**: Lineup data timing  ·  **Tested**: Verified: code read; timing semantics confirmed
- **Finding**: lineup_fetcher uses nba_api to pull confirmed starting lineups. Teams submit ~30 min before tip-off. nba_api unavailable → log.warning 'nba_api not installed — confirmed lineups unavailable' and returns empty. Critical timing: if picks run >30min before tip, lineups will be EMPTY (not yet submitted) — picks made with rotation projections, not confirmed-starter projections. If picks run <30min before tip, lineups should be present. There's no run_picks.py gate that enforces 'must run within N min of tip' for confirmed-lineup picks — the system silently uses pre-lineup projections when no confirmation is available.
- **Evidence**: `lineup_fetcher.py:3 'Teams submit starting lineups ~30 min before tip-off'; line 39 nba_api fallback`
- **Next action**: Add a startup info-log in run_picks.py: per game, log 'tip in X min — lineups: confirmed/pending'. Add a gate: if a pick depends on a player's projected minutes AND lineups are pending for that game AND tip is >60min away, log a CAUTION flag in the Discord card.

#### P1-114. No CI / automated test runner

- **Finding ID**: S4l-3
- **Layer**: L42: Step 4l — Ops/runtime
- **Location**: `(repo root):(no .github/workflows or equivalent)`
- **Status**: ❌  ·  **Category**: CI/CD absence  ·  **Tested**: Verified: directory listing
- **Finding**: No CI/CD configuration found in the repo (no .github/workflows/, no .gitlab-ci.yml, no tox.ini visible at repo root). Tests in /tests/ exist (referenced in CLAUDE.md and audit history) but rely on manual invocation. Result: regression detection is opportunistic — relies on operator remembering to run tests before deploying. Given the scale (59 engine files, 23 system layers, daily ops), the absence of automated CI is a P1 operational risk. Even a single GitHub Actions workflow running pytest on push would catch most schema/path/import regressions.
- **Evidence**: `ls -la jonnyparlay_temp/ shows no .github, no ci/, no .gitlab-ci.yml`
- **Next action**: Add .github/workflows/test.yml: run `pytest -q` + `python engine/health_check.py --quiet --fail-fast` on push to main. Block merge on failure. Scope: tests/ directory + health_check sanity, not a full grade_picks integration test.

### Verified-OK at this severity (42)

| Component | Location | Finding ID | Notes |
|---|---|---|---|
| MIN_DAILY_LAY_PROB=0.50 | `engine/thresholds.py:15` | F6.8 | Was 0.47 with wrong EV comment; now 0.50 = break-even at +100. Comment rewritten. |
| KILLSHOT_SCORE_FLOOR=65.0 | `engine/thresholds.py:44` | Plan 6 §13 | v3 redesign 2026-06-05; v2 was internally dead (0 KILLSHOTs in 5+ weeks) |
| KILLSHOT_WP_MARGIN=0.03 | `engine/thresholds.py:45` | Plan 6 §13 | wp >= implied_prob(odds) + 0.03 (breakeven + EV cushion). Closes the −EV window where wp=0.65 at −200 was −2.5%/unit |
| WNBA_EV_FLOOR=0.0955 | `engine/thresholds.py:84` | Plan 6 §14 | Replaces dead WNBA_EDGE_FLOOR=0.035 (was dominated by G9=0.05). 0.0955 = NBA G9 net EV at -110. |
| PLATT_SPACE='raw' | `engine/thresholds.py:86` | H3 | Safeguard prevents mismatched formula/A/B at H3 logit-space migration |
| F5_SCALAR=0.540 | `engine/thresholds.py:88` | — | Was 0.503 (too low by ~4pp). Market-calibrated 2022-2025 F5 lines |
| BLEND_ALPHA=0.25 | `engine/thresholds.py:94` | — | SaberSim disagreement dampener. 0.25 = trust market 75% |
| MIN_PICK_SCORE=15 | `engine/thresholds.py:107` | — | Lowered from 25 on 2026-05-27 after calibration improved |
| MIN_OVER_SCORE=15 | `engine/thresholds.py:108` | — | Lowered to match MIN_PICK_SCORE |
| MIN_WIN_PROB=0.50 | `engine/thresholds.py:109` | — | Floor removed 2026-05-27 — calibration improved. Effective use case: comment only |
| NB_R['RBI']=0.87 | `engine/calibrated.py:74` | 2026-05-26 | var/mu=1.535. r<1 valid; reflects heavy zero-inflation (~74% of games 0 RBI). |
| NB_R['ER']=2.62 | `engine/calibrated.py:75` | 2026-05-26 | var/mu=1.700. Bullpen + run-support tails. |
| COMBO_RHO (NBA) | `engine/calibrated.py:96` | 2026-05-25 | Re-verified after DB update; all 3 pairs stable to <0.001 |
| COMBO_RHO_WNBA | `engine/calibrated.py:(see CLAUDE.md)` | 2026-06-04 | PTS-REB=0.294, PTS-AST=0.188, REB-AST=0.200. ~0.04-0.05 below NBA. |
| F5_SIGMA | `engine/calibrated.py:(per CLAUDE.md)` | 2026-05-29 | total=2.65, spread=2.70, team=2.10 |
| Team-specific sigmas | `engine/calibrated.py / team_resolve.py:(_load_team_sigmas)` | Plan 6 §6 | JSON: data/team_sigmas_{sport}.json. Relative-scaler formula: σ_league × sqrt((σ_h²+σ_a²)/(2σ̄²)) |
| copula_joint_prob (MC) | `engine/quant/copula.py:62-107` | Plan 10 §17 | Gaussian copula via 4000-sample MC. Fixed seed=42. SE~0.7% for joint≈0.40. |
| cholesky | `engine/quant/copula.py:46-59` | — | n≤4 Cholesky with diagonal clipping (1e-12) |
| probit (Φ⁻¹) | `engine/quant/copula.py:17-44` | — | math.erfinv preferred; BSM fallback for Python<3.12 |
| get_market_mult | `engine/sizing_core.py:50-60` | — | Lookup order: (sport,stat,dir)→(sport,stat,None)→DEFAULT |
| size_picks_base | `engine/sizing.py:20-33` | Plan 9 §9K | Uniform 0.25u floor (was 0.50u non-T3 — was 2-2.5× over-staking). Cap 1.25u. Sub-50% wp capped at 0.75u. |
| size_bonus_pick | `engine/sizing.py:35-?` | audit H-9 | Returns None when Kelly < floor (was clamping up to floor, hiding upstream edge miscalc) |
| G3: line bounds | `engine/gates.py:34` | — | Reasonable line range check |
| G7: -150 odds floor | `engine/gates.py:38` | — | Block heavy juice ≤-150 |
| G7b: soft juice | `engine/gates.py:42` | — | -149..-140 with edge<10% blocked |
| R4 REB over → shadow | `engine/rules.py:?` | Plan 9 §9J | REB-over routed to shadow (formerly banned) |
| R7 max per game | `engine/rules.py:?` | — | — |
| R10 same-stat cap | `engine/rules.py:?` | — | Max 1 same-stat any direction |
| R11 narrowed (AST under 0.5 live) | `engine/rules.py:?` | 2026-06-03 | R11 blocks AST under 1.5 and 2.5 only; 0.5 live (32W-12L 72.7%) |
| auto_r12_from_log | `engine/rules.py:64-95` | F2.8 | F2.8 fixed: cutoff now uses window_days (was window_days-1) |
| copula_joint_approx usage | `engine/sgp_builder.py:243` | F7.2 | Import aliased as _copula_joint_approx; used for ranking the 91k combo space; final SGP uses full MC |
| format_output cap display | `engine/output_format.py:271-297` | F16.3 | Now includes KILLSHOT + daily_lay + longshot in display total. SGP via separate flow (real 12u cap on next sport's cross |
| has_g8_fail checklist | `engine/output_format.py:214-220` | F9.29 | Synced with G8/G8B/G8C/G8D |
| capture_clv stat markets | `engine/capture_clv.py:—` | Plan 10 §EE | Shipped 2026-06-09 — TEAM_TOTAL via team_totals matcher, NRFI/YRFI via totals_1st_1_innings; PA/PR/RA/PRA combos + laten |
| Card guard A4 fix | `engine/run_picks.py:—` | A4 2026-05-06 | Bypass for --no-discord (shadow/research) |
| AUDIT_HISTORY.md | `docs/archive/audits/AUDIT_HISTORY.md:1-323` | — | Closes prior audits |
| BACKLOG.md | `docs/BACKLOG.md:1-111` | — | Tier 1-7 backlog; data-gated items flagged |
| Math audits (s1-17) | `docs/audits/math_audit_s*.md:—` | — | 5 math audits covering Steps 1-17 (May 22) |
| Gate audit 2026-05-26 | `docs/audits/gate_audit_2026-05-26.md:—` | — | G8B/G8C/G8D recheckpoints |
| Plan 6 / 9 / 10 references | `docs/audits/*.md + CLAUDE.md:—` | — | Plan 6 §13 (KILLSHOT v3), §14 (WNBA), §1C (OUTS/PC starts-only); Plan 9 §9F (BM shrinkage), §9K (sizing floor); Plan 10  |
| _REB_RATE_PRIOR_RS/PO | `engine/nba_projector.py:416-423` | H1 | VERIFIED 2026-06-16 (RESOLVED). H01 BROADER fix corrected per-game→per-36 mistake. RS: PG=0.128, SG=0.132, SF=0.168, PF= |
| C3 — dk_std Vegas exclusion | `generate_projections.py:64-76` | C3 | PRIOR CRITICAL — RESOLVED. dk_std excluded from _CONSTRAINT_SCALE_KEYS (correct: floor must hold), BUT L587-594 recomput |

## P2 — Medium (technical debt / fork risk)

**Total: 84** · Open: 74


| ID | Component | Location | Category | Finding |
|---|---|---|---|---|
| Plan 6 §14 / F12.4 | WNBA_EARLY_SEASON_EDGE_MULT | `engine/thresholds.py:73-76` | Math | 0.80/0.90/1.00 by day-band. DATA_GATED — recalibration deferred to 2027 season start. |
| Plan 6 §4 | KELLY_FRACTION=6.0 | `engine/thresholds.py:98` | Sizing | Label was 'wrong' — value=correct but represents 1/16.7 Kelly, not '1/6 Kelly' |
| 2026-05-26 | NB_R['TB']=1.3 (fallback) | `engine/calibrated.py:76` | Distribution | var/mu=2.117. Fallback only — calc_tb_prob() uses component Poisson convolution (1B/2B/3B/HR). |
| Plan 10 §K | VAKE_MULT['variance'] | `engine/calibrated.py:(per CLAUDE.md)` | Sizing | Double-count with KELLY_MARKET_MULT; retire at n>=50/market into one empirical-Bayes mult |
| Plan 10 §K | KELLY_MARKET_MULT uncalibrated | `engine/calibrated.py:(per CLAUDE.md)` | Sizing | Hand-tuned; DATA_GATED at n>=50/market. NBA 3PM over=0.10, WNBA REB=0.10 (floor-pinned) |
| L11 | L11 unknown stat fallback | `engine/prob_core.py:114-117` | Defensive | Logs warning for missing SIGMA entry; falls back to mult=0.40/min=2.0 |
| Plan 10 §K | VAKE size cap stack | `engine/sizing.py:?` | Sizing | Stack: market_m × var_m × corr_m × exp_m. var_m double-counts KELLY_MARKET_MULT. |
| — | _killshots_this_week | `engine/killshot.py:135-?` | Defensive | Logs warning + assumes cap full on read failure (fail-closed) |
| — | longshot parlay | `engine/parlays.py:?` | Logic | Up to 2 picks per game (LONGSHOT_MAX_PER_GAME=2) |
| Plan 10 | R9 directional balance | `engine/rules.py:?` | Rule | Reclassified product rule, NOT EV. Track at n>=50 forced-over events |
| Plan 10 | R12 trigger replacement | `engine/rules.py:—` | Rule | Loss trigger is product-rule, EV cost unknown. Replace with negative-CLV when CLV matures |
| CLAUDE.md | SGP_JOINT_EV_MARGIN=0.025 | `engine/sgp_builder.py:—` | Math | Joint-EV existence floor. DATA_GATED. Premium gate (margin>=0.10) unchanged |
| Plan 9 §9H | MIN_LEG_WIN_PROB_OUTS=0.62 | `engine/sgp_builder.py:—` | Calibration | Tuned to OLD OUTS σ=0.311; current σ recalibrated to 0.27. Monitor at n>=40 graded OUTS SGP legs |
| — | CLV daemon uptime guard | `engine/?:test_clv_daemon_uptime_guard.py` | Defensive | — |
| — | CLV date key | `engine/?:test_clv_date_key.py` | Defensive | — |
| — | CLV stale marker | `engine/?:test_clv_stale_marker.py` | Defensive | — |
| Plan 10 §EE | CLV write-gate latch | `engine/capture_clv.py:—` | Logic | Change to last pre-tip observation (research-gated) |
| — | CLV game_lines test | `engine/?:test_capture_clv_game_lines.py` | Defensive | — |
| — | analyze_picks | `engine/analyze_picks.py:—` | Analytics | Stat-level WR / ROI / CLV analytics |
| — | analyze_blend | `engine/analyze_blend.py:—` | Analytics | Blend analysis |
| — | diagnostics | `engine/diagnostics.py:—` | Analytics | — |
| — | clv_report | `engine/clv_report.py:—` | Analytics | — |
| — | gate_check | `engine/gate_check.py:—` | Analytics | Reports current gate counts (CLAUDE.md says: 'run python engine/gate_check.py') |
| — | projection_accuracy | `engine/projection_accuracy.py:—` | Analytics | — |
| — | empirical_analysis | `engine/empirical_analysis.py:—` | Analytics | — |
| — | historical_backtest | `engine/historical_backtest.py:—` | Analytics | — |
| — | sabersim_backtest | `engine/sabersim_backtest.py:—` | Analytics | — |
| — | weekly_recap | `engine/weekly_recap.py:—` | Analytics | — |
| — | book_names | `engine/book_names.py:—` | Config | Sportsbook display names |
| — | io_utils | `engine/io_utils.py:—` | IO | — |
| — | paths | `engine/paths.py:—` | Config | Centralized path constants |
| — | secrets_config | `engine/secrets_config.py:—` | Config | Discord webhook + DB paths |
| — | health_check | `engine/health_check.py:—` | Tooling | — |
| — | test_blocked_log.py | `tests/test_blocked_log.py:—` | Tests | Coverage exists; verify it passes + asserts the intended invariant |
| — | test_capture_clv_shutdown.py | `tests/test_capture_clv_shutdown.py:—` | Tests | Coverage exists; verify it passes + asserts the intended invariant |
| — | test_clv_daemon_uptime_guard.py | `tests/test_clv_daemon_uptime_guard.py:—` | Tests | Coverage exists; verify it passes + asserts the intended invariant |
| — | test_clv_date_key.py | `tests/test_clv_date_key.py:—` | Tests | Coverage exists; verify it passes + asserts the intended invariant |
| — | test_clv_stale_marker.py | `tests/test_clv_stale_marker.py:—` | Tests | Coverage exists; verify it passes + asserts the intended invariant |
| — | test_discord_corruption_recovery.py | `tests/test_discord_corruption_recovery.py:—` | Tests | Coverage exists; verify it passes + asserts the intended invariant |
| — | test_extended_absence_cap.py | `tests/test_extended_absence_cap.py:—` | Tests | Coverage exists; verify it passes + asserts the intended invariant |
| — | test_log_picks_zero_row_warning.py | `tests/test_log_picks_zero_row_warning.py:—` | Tests | Coverage exists; verify it passes + asserts the intended invariant |
| — | Shadow CLV go-live (0/100) | `engine/capture_clv.py:—` | Calibration | 0/100 post-reform; 227 pre-reform archived. Also require t>=1.7. |
| Plan 10 §V | conf early-season double-shrink | `engine/calibrated.py:—` | Calibration | Fold into GP-conditioned BM weight w_eff = w·GP/(GP+k) |
| Plan 10 §K | KELLY_MARKET_MULT consolidation | `engine/calibrated.py:—` | Sizing | Consolidate market_m + var_m into one per-market mult; flag <0.30 as cosmetic |
| Plan 8 §8G #2 | Usage-concentration creator | `—:—` | Logic | _CREATOR_USAGE_SHARE=0.30 (AST%, not 20% of team AST count). Not yet in code. |
| Plan 8 §8C #4 | Travel/altitude | `—:—` | Logic | Two effects: altitude (DEN/UTA home eff) + westward travel (circadian). Neither in code. |
| M1 | season_type heuristic late-April (M1) | `engine/projections_db.py:1478-1482` | Logic | M1 prior audit: late-April RS games misclassified as Playoffs by heuristic. |
| M2 | matchup_stl RS opp in PO (M2) | `engine/nba_projector.py:1352-1354` | Logic | M2 prior audit: matchup_stl uses RS opp_tov_rate in playoff context without playoff correction. |
| M4 | EWMA spans (M4) | `engine/nba_projector.py:95-109` | Calibration | M4 prior audit + Plan 7 #1: pts=15, reb=12, ast=13, fg3m=10, stl=25, blk=25, tov=10. STL/BLK refit 8→25 (Plan 7 #1, n=1464). MAE 0.8254→0.8060 (-2.4%) for STL.  |
| M6 | REDISTRIB_MIN_ELIGIBLE (M6) | `engine/injury_parser.py:84` | Logic | M6: REDISTRIB_MIN_ELIGIBLE=8.0 (avg minutes to qualify as recipient). Thin-depth teams may lose minutes to undefined pool. |
| H1-diag | diagnostics.py | `engine/diagnostics.py:1-255` | Tooling | Sidecar diag for Vegas vs 240-min constraint. Gated by JONNYPARLAY_DIAG_VEGAS_VS_240 / DIAG_REDISTRIB. |
| — | name_utils.py | `engine/name_utils.py:1-92` | Logic | Used by both JonnyParlay and EdgeModel. Verify fold_name canonical form matches across repos. |
| — | io_utils.py / log_setup.py / engine_logger.py | `engine/{io_utils,log_setup,engine_logger}.py:—` | Infra | io_utils=100, log_setup=195, engine_logger=146 LOC. |
| — | tools/ast_vegas_divergence.py | `engine/tools/ast_vegas_divergence.py:—` | Tooling | AST vs Vegas divergence tool. Probably part of H8 investigation. |
| H6 | H6 — cold_start playoff scalar 0.400 | `nba_projector.py:293` | Calibration | Prior HIGH: cold_start=0.400 excluded from H2 refit. H06 (2026-05-30) added COLD_START_PLAYOFF_SCALAR subtypes (taxi/extended_absence=0.400; returner=0.700; new |
| S4a-3 | odds_io 15-min cache TTL | `engine/odds_io.py:225-242` | Data freshness | Cache TTL=15 min on cache/odds_{sport}_{ET-date}.json by file mtime. Inside one run_picks invocation a 14-min-old cache is consumed as fresh — no fetched_at tim |
| S4a-1 | MLB_PARK_FACTORS stale dict | `engine/calibrated.py:204-218` | Calibration | CONFIRMED STALE per inline warning 2026-06-07: TEX inverted (~1.05 was pitcher-friendly, now ~0.95); COL too low (~1.28 → ~1.33); KC/MIN/DET now hitter-friendly |
| S4b-2 | G13B audit banner text | `engine/output_format.py:289` | Cosmetic | Stale banner: 'TB killed (G_TB_DISABLED), HRR fully killed (G_HRR_DISABLED), RA killed (G_RA_DISABLED)'. Both G_TB_DISABLED and G_HRR_DISABLED removed 2026-05-2 |
| S4b-4 | G6 — referenced in docs, absent in code | `engine/gates.py:N/A — absent` | Doc-drift | G6 absent from current gates.py and absent from comment trail. Some legacy doc references remain (treated as forgotten gate). |
| S4c-15 | Push handling in normal_cdf paths | `engine/quant/distributions.py + prob_core.py:dist:29-33, pc:99-` | Math | normal_cdf is CONTINUOUS — no push concept. For integer lines on Normal stats (PTS, REB, etc.), over+under = 1.0 always (no push mass deducted). But DK refunds  |
| S4d-3 | NB_STATS[3PM] vs EdgeModel JSON | `engine/calibrated.py:66, 79` | Family-classification ambiguity | EdgeModel JSON classifies NBA 3PM as Poisson (var/mu=1.179, just below the 1.20 NB threshold; n=531 players, 64,214 games). JonnyParlay routes 3PM to NB_STATS w |
| S4d-7 | F5_SIGMA totals/spreads | `engine/calibrated.py:194` | Calibration provenance lacking | F5_SIGMA = {'total': 2.65, 'spread': 2.70, 'team': 2.10} — comment 'calibrated 2026-05-29; total/team raised ±0.1 for park variance'. No source document, no n_g |
| S4d-12 | NB_R_WNBA AST/REB/3PM provenance | `engine/calibrated.py:77-79` | Methodology consistency with NBA | NB_R_WNBA = {'AST': 11.37, 'REB': 10.74, '3PM': 1.342} — comment cites 'calibrated 2026-06-04: 202 players / 13322 games (2023-2026 WNBA RS, min>=8)' for AST/RE |
| S4e-1 | SIGMA[PTS] role-MAE provenance | `engine/calibrated.py + EdgeModel evaluate_projector.py:calibrated.py:21; evaluate_projector.py:553` | Calibration claim not stamped | JP calibrated.py:21 comment cites 'min raised 4.5→5.0 (MAE by role: spot=5.15, rotation=5.98)'. The values 5.15/5.98 do NOT appear in any reproducible source sc |
| S4e-5 | Travel/altitude features absent in projector | `edgemodel/engine/nba_projector.py:1091-1108 (_compute_days_rest_reduction)` | Modeling gap (confirms Top-13 #10) | Projector models days_rest (exponential decay, role-scaled), b2b flag, blowout-margin sigmoid, but has ZERO travel-distance/timezone/altitude features. grep -i  |
| S4e-6 | No wnba_projector.py — WNBA relies on SaberSim | `edgemodel/engine/:(file absent)` | Architecture clarity | EdgeModel/engine has nba_projector.py (1961 LOC) and stats fetchers for NBA/WNBA/MLB/NHL but NO wnba_projector.py — only wnba_stats_fetcher.py (data ingestion). |
| S4f-14 | KELLY_MARKET_MULT + VAKE_MULT sizing dampers | `engine/calibrated.py + engine/sizing_core.py:calibrated.py:KELLY_MARKET_MULT; calibrated.py:VAKE_MULT` | Sizing damper provenance | Two stacked sizing dampers. KELLY_MARKET_MULT (per-stat-per-sport): NBA PTS=1.00, AST=1.00, REB=1.00, 3PM=0.50; MLB OUTS=1.00, HITS=0.60, RBI=0.50; WNBA REB=0.1 |
| S4g-3 | ρ fallback default 0.20 (NBA) / 0.10 (WNBA) | `engine/prob_core.py:prob_core.py:158` | Silent fallback in combo math | _combo_mu_sigma fallback: `rho_table.get(pair, rho_table.get((pair[1], pair[0]), 0.10 if sport == 'WNBA' else 0.20))`. If a combo pair is missing from COMBO_RHO |
| S4g-14 | 0.87 deflation factor stationarity | `engine/quant/copula.py:copula.py:121-122` | Approx-vs-MC tuning factor | The 0.87 deflation in copula_joint_approx was Plan 10 §Z derived as midpoint of 0.85-0.90 range. The recommendation came from a specific set of test cases (n_le |
| S4h-9 | size_daily_lay — quarter Kelly on parlay | `engine/sizing.py:sizing.py:130-159` | Daily lay sizing | size_daily_lay applies QUARTER Kelly to the parlay (combined_prob, parlay_odds): kelly_full × 0.25 × 100 → units. Caps at 0.75u, floors at 0.25u. Returns 0.25u  |
| S4h-13 | WNBA SPORT_UNIT_CAP=4.0 (lowest) | `engine/rules.py:rules.py:262` | WNBA exposure throttle | WNBA capped at 4.0u/day vs NBA/MLB 8.0u, NHL/NFL 5.0u. The 4.0u WNBA cap is tightest reflecting (1) limited slate (typically 1-4 games), (2) ongoing shadow WR c |
| S4i-12 | SPOT_MIN_EWMA_FILTER = None (Plan 7 #4 — backtest-only) | `edgemodel/engine/nba_projector.py:nba_projector.py:115-121` | Heckman selection scalar | Plan 7 #4 (§7B, 2026-06-06): spot-minutes EWMA selection filter for role='spot' players. When set, project_player() filters minutes-EWMA input for spot role to  |
| S4i-13 | WNBA projector — no separate file (cross-ref S4e-6) | `edgemodel/engine/:(no wnba_projector.py)` | WNBA pipeline architectural clarity | Re-verifies S4e-6. EdgeModel does NOT have wnba_projector.py — WNBA projections come from a different pipeline (likely calibrate_distributions.py + sigma_calibr |
| S4k-3 | capture_clv keeps OWN implied_prob variant (intentional) | `engine/capture_clv.py + engine/quant/odds.py:capture_clv.py:370` | Module-local odds math | quant/odds.py docstring explicitly says: 'capture_clv.py and clv_report.py intentionally keep their own implied_prob *variants* with extra None-handling for non |

## P3 — Low (hygiene / robustness)

**Total: 26** · Open: 10


| ID | Component | Location | Category | Finding |
|---|---|---|---|---|
| F17.3 | apply_r12_cooldown sport filter | `engine/rules.py:97+` | Rule | No sport filter — NBA cooldown also suppresses NHL/MLB for same name. Explicit comment: 'Near-zero practical risk given naming divergence' |
| Backlog #11 | context_research module | `engine/context_research.py:—` | Cleanup | DELETED 2026-05-23 (shipped then reversed). context_verdict column retained in pick_log.csv schema. |
| — | brand | `engine/brand.py:—` | Display | — |
| — | pick_labels | `engine/pick_labels.py:—` | Display | — |
| — | month_names | `engine/month_names.py:—` | Display | — |
| — | log_setup / engine_logger | `engine/log_setup.py / engine_logger.py:—` | Tooling | — |
| — | test_book_names.py | `tests/test_book_names.py:—` | Tests | Coverage exists; verify it passes + asserts the intended invariant |
| — | test_context.py | `tests/test_context.py:—` | Tests | Coverage exists; verify it passes + asserts the intended invariant |
| — | test_context_research.py | `tests/test_context_research.py:—` | Tests | Coverage exists; verify it passes + asserts the intended invariant |
| S4i-5 | prob_to_american() — returns float, not int | `engine/quant/odds.py:odds.py:39-46` | Type inconsistency | prob_to_american returns float (computed odds). Callers may expect int (American odds are conventionally integers). decimal_to_american explicitly returns int(r |

## INFO — Configuration documentation

**Total: 129** · These are configuration constants, thresholds, and documented behaviors catalogued for traceability. No action required. See the tracker spreadsheet for the full list.

## Verified-OK summary

**Total: 208** components/behaviors verified to match the documented spec.

Highlights:
- Plan 4 staking flow (KELLY_FRACTION=6.0, SPORT_UNIT_CAP, 1.25u/pick max, 12u daily cap)
- Plan 6 calibrate_thresholds → calibrate_distributions → fit_platt artifact chain
- Discord post guard with 90-day TTL operational
- filelock hard-dependency in requirements (no soft-import fallback)
- Shadow log isolation — never crosses into pick_log
- gate_check emits all 6 expected counters per Plan 9 §6
- best_price filter respects CO_LEGAL_BOOKS allowlist
- health_check.py 12-check battery runs end-to-end
- capture_clv daemon checkpoint/resume
- pick_log schema v4 stable

## Research Appendix

External validation sources used during the audit (cited inline in tracker `Notes` and `Evidence` columns where applicable):

- **Plan 9 §9F** (internal spec) — Monotonicity requirement: edge floors must move with BM trust weights. Used in S4c-5 / S4f-3.
- **Plan 6 §1C** (internal spec) — "Starts-only" filter for MLB pitcher props; "min≥20 priced minutes" filter for WNBA. Used in S4e-3 / S4e-4.
- **Platt scaling theory** (Platt 1999; Niculescu-Mizil & Caruana 2005) — Calibration must be fit on out-of-sample probability outputs in a consistent space (raw vs vigged-stripped). Used in S4b-8, S4f-15.
- **Negative binomial dispersion** (Hilbe, _Negative Binomial Regression_) — Producer-side `r` and consumer-side `NB_R[stat]` must match to within rounding for variance to be correctly propagated. Used in S4d-1, S4d-2, S4e-2.
- **NBA σ research** (public box-score distributions, current season) — PTS σ ≈ 8–10 for high-volume scorers; OUTS σ ≈ 0.25–0.28 for modern MLB starters. Used to flag stale gate thresholds in S4f-4.
- **Kelly criterion fractional sizing** (Thorp; MacLean/Ziemba) — Fractional Kelly with KELLY_FRACTION=6.0 implies ~1/16.7 Kelly, well within safe range for parlay variance. Verified in S4h.
- **Copula-based SGP correlation** (academic + sportsbook practice) — Empirical ρ requires ≥100 observed SGPs per sport for stable estimation. Used in S4g-5, S4g-12 to justify "awaiting data" status.
- **OWASP / CI-CD best practice** — Manual-only deployments for production systems are a P1 operational risk. Used in S4l-3.

---

_End of findings report. Next deliverable: **Step 6 — Prioritized fix plan (phased)**._