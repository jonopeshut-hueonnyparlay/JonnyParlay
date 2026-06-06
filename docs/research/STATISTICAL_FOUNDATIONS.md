# Statistical Foundations — JonnyParlay System
# Last validated: 2026-06-05
# All values verified against engine/run_picks.py and EdgeModel/engine/nba_projector.py
# Research model: claude-opus-4-8 with web search (one research agent per section)

---

## HOW TO USE THIS DOCUMENT

Before changing any distribution, constant, or methodology:
1. Find the relevant section below.
2. Read the VERDICT and the Condition to Revisit.
3. Provide evidence that the condition is met before making any change.

If a NEEDS_CHANGE verdict exists, that section's change has priority.

Audit methodology: every constant below was read from source on 2026-06-05
(not assumed from docs); each of the 21 sections was researched by a dedicated
claude-opus-4-8 agent with mandatory web search; every verdict cites at least
one published source. Baseline test suite: 961 passing before and after this
session.

Code ground-truth corrections found during the audit (documented here because
older planning docs stated otherwise):
- `mlb_ml_from_nb()` is an EXACT NB probability sum (k=0..30, ties 50/50), not Monte Carlo.
- Truncated Normal at [0,∞) applies to PTS only; OUTS/PC/SV use plain Normal.
- SGP copula MC: n=300 for ranking pass, n=4000 for the sizing decision.
- size_picks_vake corr_m is game-count based (1.00/0.85/0.70 by pick order in game),
  plus R13 pitcher ×0.70 and exp_m repeat-stat ×0.70; final clamp [0.50u, 1.25u].
- WNBA GAME_SIGMA spread=10.0 / ml=10.0 are uncalibrated placeholders.
- EdgeModel DAYS_REST decay is `exp(-days/1.5)` — an e-folding time of 1.5 days
  (true half-life ≈ 1.04 days), despite the constant's name DAYS_REST_HALF_LIFE.
- Integer-line props ARE push-renormalized: over/under divided by (1 − push mass).

---

## VERDICT SUMMARY (all 21 sections)

| § | Topic | Verdict |
|---|---|---|
| 1A | NB distribution family | CONFIRMED_WITH_CAVEAT |
| 1B | Poisson validity | CONFIRMED_WITH_CAVEAT |
| 1C | Normal for continuous props | **NEEDS_CHANGE** (OUTS, PC, WNBA PTS sigmas) |
| 1D | Truncation formula | CONFIRMED_WITH_CAVEAT (math exact) |
| 1E | POISSON_CUTOFF=8.5 | CONFIRMED_WITH_CAVEAT (dead branch, NFL foot-gun) |
| 1F | NB PMF/CDF/estimator | CONFIRMED (verified to machine precision) |
| 2 | Combo props (Normal sum) | CONFIRMED_WITH_CAVEAT |
| 3 | Platt scaling | CONFIRMED_WITH_CAVEAT (logit migration confirmed; script missing) |
| 4 | Kelly & sizing | CONFIRMED_WITH_CAVEAT (**NEEDS_CHANGE**: multiplier stack) |
| 5 | Vig removal & edge | CONFIRMED_WITH_CAVEAT |
| 6 | Game line distributions | **NEEDS_CHANGE** (NBA σ, matchup formula) |
| 7 | Push handling | CONFIRMED_WITH_CAVEAT (load-bearing & correct) |
| 8 | G14 clearance | CONFIRMED_WITH_CAVEAT |
| 9 | Correlation penalties | **NEEDS_CHANGE** (retire R13 only) |
| 10 | SGP joint probability | CONFIRMED_WITH_CAVEAT |
| 11 | PICK_SCORE formula | CONFIRMED_WITH_CAVEAT (e_n cap recommended) |
| 12 | EWMA / FG3M / rest | **NEEDS_CHANGE** (3P% padding) |
| 13 | KILLSHOT thresholds | **NEEDS_CHANGE** (dead combos, latent −EV window) |
| 14 | WNBA gates | **NEEDS_CHANGE** (dead-code floor, dampener mechanism) |
| 15 | G9/G9B edge floors | CONFIRMED_WITH_CAVEAT (floors are lower-bound defensible) |
| 16 | TB convolution | CONFIRMED_WITH_CAVEAT (verified empirically) |

---

## LOCKED ASSUMPTIONS
*These should not change unless the sport/market fundamentally changes.*
*These are the mathematical foundations. "Feeling" is not sufficient to change them.*

| Assumption | Value | Verdict | Source(s) | Condition to Revisit |
|---|---|---|---|---|
| NB PMF/CDF (lgamma form, non-integer r) | run_picks.py:781-812 | CONFIRMED | Hilbe 2011; Lawless 1987; verified vs scipy to 1e-16 | Never (formula); r values are PERIODIC_RECAL |
| MOM r estimator r = μ²/(σ²−μ), pooled | calibrate_distributions.py | CONFIRMED | Cameron & Trivedi 2013; Lawless 1987 | Only if a stat with r<0.5 + n<1000 appears |
| Truncated Normal [0,∞) formula (PTS) | run_picks.py:939-946 | CONFIRMED (exact) | Johnson-Kotz-Balakrishnan §10.1; Greene | Low-line PTS over miscalibration → fix is NB path, not formula |
| PTS-only truncation scope | PTS only | CONFIRMED | §1D math: only PTS reaches μ/σ < 2.33 | If combo props on deep-bench players appear |
| Push renormalization P(win\|no push) | run_picks.py:893-925 | CONFIRMED (exact; decision-flipping if removed) | Wong, *Sharp Sports Betting*; 3-outcome Kelly derivation | Integer-line Normal-stat picks appearing (currently 0/695) |
| Proportional no-vig (2-way) | no_vig() | CONFIRMED_WITH_CAVEAT | Štrumbelj 2014; Clarke et al. 2017 — ≤0.2pp error in [-130,+110] | Markets outside ~[-160,+140] become regular |
| Edge = p_model − p_fair + Kelly on actual odds | calc_edge/kelly_units | CONFIRMED (pairing correct) | Kelly 1956; Thorp 2006 | EV-based floors worth considering if odds mix widens |
| CLV: vig-free close vs actual entry price | capture_clv.py post-reform | CONFIRMED (industry standard) | Buchdahl; Pinnacle methodology | None |
| MLB ML exact NB sum, ties 50/50 | mlb_ml_from_nb() | CONFIRMED | Maher 1982 framework; ghost-runner era home extras WR=.493 | Extras rule change |
| MLB_TEAM_RUN_R=3.548 + independence (ρ=0.013) | run_picks.py:580 | CONFIRMED | §6 empirical: 8,095 games | League run environment shift >3% |
| TB Poisson convolution (generalized Hermite) | calc_tb_prob() | CONFIRMED (bias <1pp at 1.5/2.5) | Kemp & Kemp 1965; Bukiet et al. 1997; 436-player calibration test | O1.5 hit-rate drift >3pp at n≥100 graded |
| TB NB fallback r=1.3 | NB_R["TB"] | CONFIRMED (beats μ-dependent r empirically) | §16 RMSE comparison | Same as above |
| corr_m 1.00/0.85/0.70 + exp_m 0.70 | size_picks_vake | CONFIRMED (variance insurance; implied ρ≈0.18-0.21 sensible) | Whitrow 2007; exact joint-Kelly solve | Effective Kelly fraction rises above ~¼ |
| POISSON_CUTOFF=8.5 | run_picks.py:376 | CONFIRMED_WITH_CAVEAT (dead branch today) | λ≥10 Normal-approx convention | NFL REC go-live: drop cutoff or guard fallback σ |
| Sizing floor/cap [0.50u, 1.25u] | size_picks_vake | CONFIRMED as product decision (floored bets stay below full Kelly while edge ≥3%) | Thorp 2006; §4 growth math | Market mults <0.30 added (floor neutralizes them) |

---

## PERIODIC RECALIBRATION
*Correct methodology. Parameter values should be updated each offseason.*

| Assumption | Current Value | Method | Frequency | Last Calibrated |
|---|---|---|---|---|
| NB_R (3PM/AST/REB/HA/RBI/ER) | 9.15/12.16/14.7/13.41/0.87/2.62 | within-player var/μ pooled MOM | Offseason | 2026-05-25/26/30 |
| NB_R_WNBA (AST/REB/3PM) | 11.37/10.74/1.340 | same | Offseason | 2026-06-04/05 |
| Poisson set membership (esp. HITS 0.89, GA 0.83) | POISSON_STATS | re-test var/μ; swap if drift outside [0.85, 1.20] | Offseason | 2026-05-26/30 |
| SIGMA PTS mult/min | 0.35/5.0 | within-player CV (priced population) | Offseason | 2026-05-25 (MAE-confirmed) |
| SIGMA SV | 0.253/3.5 | starter-only CV (note: 0.288 starts-only — recheck) | Offseason (NHL) | 2026-05-26 |
| COMBO_RHO + combo σs | 0.333/0.233/0.251 | within-player Pearson (ρ reproduced exactly in audit); replace marginal σs with NB-consistent √(μ+μ²/r) at next pass | Offseason | 2026-05-25 |
| NHL GAME_SIGMA | 2.311/2.614/1.744/2.614 | league score SDs (excellent — reproduce within 0.05) | Offseason | 2026-06-05 |
| F5_SIGMA / F5_SCALAR | 2.65/2.70/2.10 / 0.540 | market-calibrated (confirmed mid-band of published 0.529–0.556) | Offseason | 2026-05-29 |
| G14 z=0.10 + NB exemption layout | run_picks.py:1252-1279 | re-derive G13↔G14 equivalence at every Platt change | At H3 + offseason | — (never fit) |
| PICK_SCORE weights/tier mults | 40/60; T1 0.90 etc. | tier WR re-eval (T1 gate n=30); add e_n cap | At tier gates | 2026-05-23 |
| Days-rest model (EdgeModel) | 0.10 / e-fold 1.5 / role scalars | regress minutes residuals on days_rest; fix HALF_LIFE naming | Offseason | ~2026-05-01 (literature-set) |
| REGULAR_SEASON_STAT_SCALAR | pts 1.0019 … blk 1.0608 | multiplicative ratio (correct form); add Mincer-Zarnowitz a=0,b=1 test + decile bias | Per refit | 2026-05-10 |
| FG3M_BLEND_ALPHA | 0.60 | grid search — re-run ONLY after PAD_3P fix | After §12 fix | 2026-06-05 |

---

## DATA-GATED
*Correct methodology. Waiting for enough data to finalize parameters.*

| Assumption | Current Value | Gate | Notes |
|---|---|---|---|
| Platt A/B (raw-space, frozen) | 1.4988 / −0.8102 | H3: 100 over_p_raw rows | §3: at n=100 fit intercept-only (A=1 logit-space); free 2-param fit at n≥300; **calibrate_platt.py must be written first — it does not exist** |
| Per-stat Platt | none | ≥200 graded per stat | Partial pooling (global slope, per-stat intercept) preferred |
| Combo Platt | none applied | 100 scored combos (11/100) | §2: also fix NB-consistent σs + skew correction; RA failure was μ-bias not shape |
| SGP thresholds (0.10/0.55/0.035) | heuristic | 100 scored SGP slips (52/100) | Order of magnitude confirmed vs 20-30% SGP hold; raise sizing-gate MC n or go deterministic |
| HRR r=1.5 (moment-matched) | 1.5 | n=50 graded shadow + **refit from mlb_batter_game_stats first** | §1A: tail unconstrained — P(X≥4) varies 2.4× across r values matching the same WR |
| SOG distribution | Poisson (suspended) | G_SOG investigation | §1B: **exonerated** — failure is conditional-mean (~+1.0 shot on elite shooters), do NOT swap to NB |
| G9/G9B floors | 5% / 7% | H3 refit + ~50 graded blocked picks | §15: three lenses say floors are lower-bound defensible; do not lower |
| WNBA constants (post-fix magnitudes) | various | 100 graded WNBA picks (0/100) | After §14 structural fixes |
| BLEND_ALPHA | 0.25 | n=100 graded game-line CLV rows | Confirmed humble prior (nfelo 0.35 for elite model; Kovalchik 2016); per-sport at ≥100 rows each |
| COLD_START penalties / INJURY_TRIGGER bonus | −15..−5 / +7..+10 | n≥30 per subtype / n≥50 CLV on triggered picks | **Blocked: neither flag is persisted in pick_log schema** — add to schema v5 |
| REC distribution | Poisson (assumed) | NFL data (July) | No calibration row exists |

---

## NEEDS_CHANGE
*Research found an error. No code was changed in this session — each item below requires explicit sign-off. Exact lines/values are in the named section.*

| # | Issue | Current | Correct | Priority | Evidence (§) |
|---|---|---|---|---|---|
| 1 | `get_game_sigma()` applies independence sum to ALL markets — breaks NBA spread/ML (~45% too wide → ~5-7pp ML error), degrades NHL | `sqrt(σh²+σa²)` for total/spread/ml (run_picks.py:532-534) | Relative-scaler form: `σ_league(market) × sqrt((σh²+σa²)/(2σ̄²))` | **P0 — live game-line picks affected daily** | §6; coordinator-verified ρ_NBA=+0.227, ρ_NHL=−0.102, ρ_MLB=+0.013 |
| 2 | NBA GAME_SIGMA never calibrated; total=12.0 is ~40% too narrow (WNBA internal contradiction: lower-scoring league with higher σ) | total/spread/team/ml = 12/12/9/12 | total≈18.5, spread/ml≈12.5, team≈11.0 — calibrate from `games` table like NHL | **P0** (same fix pass as #1) | §6; coordinator-verified total SD=20.2 (n=3,922) |
| 3 | SIGMA["OUTS"]/["PC"] calibrated on ALL pitcher appearances incl. relievers; market prices starters only | mult 0.311 / 0.375 | starts-only: OUTS ≈0.27 interim (within-CV 0.228), PC ≈0.18-0.20 (within-CV 0.142); MAE-validate | **P1 — OUTS is a live market (~5pp mispricing at typical lines)** | §1C; coordinator-verified starts/relief CV split |
| 4 | SIGMA_WNBA["PTS"]=0.618 is a sampling-frame artifact (min≥8 sample median 7.2 PPG; NBA same-frame gives 0.615) | mult 0.618 | ≈0.46-0.50 from priced population (min≥20 or μ-stratified); recheck AST 0.779/REB 0.633 same pass | P1 — shadow-only today, gates go-live data quality | §1C |
| 5 | EdgeModel 3P% pad: 750 attempts against ≤30-game window — over-shrinks everyone; quantitatively explains −0.26 FG3M bias | PAD_3P=750 on window (nba_projector.py:904-957) | pad ≈242-300 vs career-to-date 3PA (or ~100-150 if window kept); then re-run alpha grid | P1 (EdgeModel repo) | §12; coordinator-verified docstring; Medvedovsky 2020 optimal pad=242 |
| 6 | R13 pitcher penalty double-counts: G11 guarantees the 2 props are different pitchers (ρ≈0.05-0.20, not 0.70); implied ρ=0.52-0.68 | corr_m ×0.70 stacked (run_picks.py:1727-1731) | Retire R13 | P2 — small EV leak (HA suspended) | §9; coordinator-verified G11 at :3592/:6284 |
| 7 | KILLSHOT gate internally contradictory: PTS∧T1 unsatisfiable, SOG suspended → only NBA AST can fire; latent −EV window at odds<−186; manual path bypasses wp/odds gates; 4u bump unreachable under Platt cap | run_picks.py:206-220, 5935-5936 | Drop T1-strict (floors+score select), odds-dependent wp floor (≥p_be+0.03) or ODDS_MIN=−185 incl. manual path, startup allowlist invariant, log disqualifications | P2 — product integrity (0 KILLSHOTs in 5+ weeks) | §13; coordinator-verified PTS∈T2 vs T1-strict |
| 8 | WNBA_EDGE_FLOOR=0.035 is dead code (G9=0.05 always dominates); comment's vig rationale inverted (correct equivalent floor ≈6.2%); early-season dampener affects ranking only, not sizing; opening gate keyed to days not games | run_picks.py:460-466, 1196-1217 | EV-per-unit floor; dampener → σ inflation; gate → ≥2 games played per team | P2 — shadow-only today | §14; coordinator-verified G9 dominance |
| 9 | KELLY_FRACTION=6.0 labeled "1/6 Kelly" but is ~1/17 Kelly at 100u bankroll; market/var/tier mults triple-count stat-level info; mults <0.3 neutralized by 0.50u floor | run_picks.py:593-617 | Rename/document constant; consolidate to single empirical-Bayes per-market mult at ~50 graded per market; gate (don't multiply) for distrust <0.3 | P3 — system is conservative-coherent as-is | §4 |
| 10 | `calibrate_platt.py` referenced by H3 plan + CLAUDE.md is missing from JonnyParlay — deleted in commit 5b8ee6d (2026-05-29 EdgeModel extraction) although it calibrates pick_log win probs, not projections; it now lives at `EdgeModel\engine\calibrate_platt.py` where it cannot find pick_log.csv via the documented workflow | mislocated file | Move it back to `engine/calibrate_platt.py` (git history intact); apply §3's slope-prior amendment when H3 fires | P1 — H3 gate is at 76/100 and approaching | §3; coordinator traced deletion via git log |
| 11 | PICK_SCORE e_n uncapped — edge 20% scores 133; optimizer's-curse amplifier at top of card | run_picks.py:1053 | `e_n = min(e_n, 100)` or shrink above 15% | P3 | §11 |

---

# SECTION-BY-SECTION FINDINGS

## SECTION 1A — Negative Binomial Distribution Family

**VERDICT:** CONFIRMED_WITH_CAVEAT
**CLASSIFICATION:** (per-constant)
- NBA 3PM/AST/REB r, MLB HA/ER/RBI r, WNBA AST/REB/3PM r: **PERIODIC_RECAL** (annual offseason refit from game logs; estimator is sound)
- NBA STL/BLK/TOV Poisson choice: **PERIODIC_RECAL** (re-test var/mu each refit; switch to NB only if var/mu drifts above ~1.15)
- MLB HRR r=1.5: **DATA_GATED** — the only constant in this family calibrated by a non-standard method; recalibrate from `mlb_batter_game_stats` (data already exists) before or at the n=50 shadow gate

**Condition to revisit:** Refit HRR r from the 169k-row batter game-log table using the same within-player var/mu estimator as RBI/TB; revisit ZINB for RBI/WNBA-3PM only if graded zero-line props show a systematic P(X=0) miss at n≥100.

### Findings

**1. NB for overdispersed sports counts is the published consensus; there is no universal var/mu cutoff — significance is sample-size dependent, and 1.05–1.15 is a legitimate gray zone.**

The standard references are unambiguous that when conditional variance exceeds the conditional mean, NB2 (var = μ + μ²/r, exactly the engine's parameterization, with α = 1/r) is the canonical model (Cameron & Trivedi 2013, ch. 3–4; Hilbe 2011, ch. 7–8; UCLA OARC). In basketball specifically, multiple independent analyses find NBA scoring counts overdispersed and NB "considerably superior" to Poisson — including three-point makes (Squared2020/Jacobs 2017; Binomial Basketball player-consistency modeling; Terner & Franks 2021, *Annual Review of Statistics and Its Application*, arXiv:2007.10550). So NB for 3PM/AST/REB at var/mu 1.15–1.39 is squarely consensus.

On a threshold: there is **no published bright-line var/mu value**. The formal tools are the Cameron & Trivedi (1990) regression-based overdispersion test and the boundary likelihood-ratio test on α (Cameron & Trivedi 2013 §5.5; Hilbe 2011 ch. 7), whose power scales with n — at the engine's n≈70k, even var/mu=1.05 is statistically "significant," which is why **practical materiality, not significance, is the right criterion**. Two anchors support treating ~1.05–1.15 as a gray zone: (a) Karlis & Ntzoufras (2003, JRSS-D) found no meaningful Poisson-vs-NB difference for soccer goals because overdispersion was small; (b) direct computation of the betting-relevant quantity: for BLK (var/mu=1.113, μ=0.5, implied r=4.42), Poisson P(0)=0.6065 vs NB P(0)=0.6227 — a 1.6pp gap at the 0.5 line; for STL (var/mu=1.072, μ=1.0), the P(0) gap is 1.3pp. These are small but not zero — keeping STL/BLK/TOV Poisson is defensible, with BLK (1.113) the closest call. If the engine ever takes volume on BLK 0.5 lines, the 1.6pp P(0) understatement systematically flatters unders; worth a check at refit.

**2. RBI r=0.87: plain NB is appropriate; the math shows the 74% zero rate is mostly NOT evidence of zero-inflation.**

r<1 is a fully valid NB (it is a Poisson-Gamma mixture with gamma shape <1 — a J-shaped, zero-modal distribution; Cameron & Trivedi 2013 §4.2). Computed zero probabilities:

- NB(μ=0.5, r=0.87): **P(X=0) = 0.674**
- NB(μ=0.4, r=0.87): **P(X=0) = 0.720**
- Poisson(0.5): P(X=0) = 0.607 — so low-r NB already adds ~7pp of zero mass over Poisson at the same mean.

The empirical ~74% is a **pooled marginal rate across players of heterogeneous μ**, and P(X=0|μ) is convex in μ, so by Jensen's inequality the pooled zero rate must exceed the zero rate at the pooled mean. Illustration: a 50/50 mix of μ=0.2 and μ=0.8 players (mean 0.5) gives pooled P(0)=0.701 vs 0.674 at-mean — heterogeneity alone closes roughly half the apparent gap, and the league-mean RBI/game is likely below 0.5 (at μ=0.36, NB(r=0.87) gives exactly 0.74). Since the engine prices each player at his **own** μ, the pooled-vs-conditional comparison is not evidence the conditional model is wrong. This matches Allison's published position that "having a lot of zeros doesn't necessarily mean that you need a zero-inflated model" and that plain NB typically fits better than ZIP by AIC/BIC (Allison, Statistical Horizons): ZINB requires a theoretically motivated two-process structure (structural zeros), and RBI zeros are opportunity-driven (lineup slot, runners on base) — a rate process, not a structural-zero process. Caveat: if zero-line RBI props are ever priced, validate P(0) calibration empirically against graded picks rather than against the pooled rate.

**3. WNBA 3PM r=1.34: the ~50% zero rate is fully explained by plain NB — ZINB is unnecessary, and the standard ZINB-vs-NB test is itself discredited.**

Computed: NB(μ=1.0, r=1.34) → **P(X=0)=0.474**; NB(μ=0.9, r=1.34) → **P(X=0)=0.503**, exactly the observed zero rate at a plausible sample-mean μ slightly below 1.0 (vs Poisson(1.0) P(0)=0.368 — Poisson would badly miss). With heterogeneity convexity (point 2) on top, there is no residual zero mass for a ZI component to absorb. On the model-comparison literature: the Vuong test historically used to "prove" ZINB superiority is invalid for this purpose — Wilson (2015, *Economics Letters* 127:51–53) showed NB is nested in ZINB at the boundary γ=0, violating Vuong's non-nested assumptions, and uncorrected implementations are biased toward the zero-inflated model (see also Desmarais & Harden 2013, *Stata Journal*, on AIC/BIC-corrected versions). Published guidance (Allison; UCLA OARC ZINB) is that ZINB earns its keep only when a distinct structural-zero population exists (e.g., players who never attempt threes) — but such players are screened out of 3PM prop offerings anyway, so the betting-relevant population has no structural-zero class. CONFIRMED.

**4. HRR moment-matching: valid as a stopgap, but it is the weakest calibration in the family — one matched point does not constrain the tail, and better data already exists in-house.**

Method-of-moments is a legitimate estimator class (Cameron & Trivedi 2013 §2.4; Real Statistics, MoM for NB), but the engine matched **one tail probability at one (μ, line) point** to identify one parameter given an assumed μ — that pins the CDF only at X≥2 near μ=2.0. Quantified tail risk: holding P(X≥2)=0.478 fixed and varying r, the implied tails diverge severely:

| r | μ matching P(X≥2)=0.478 | P(X≥3) | P(X≥4) | P(0) |
|---|---|---|---|---|
| 0.8 | 2.45 | 0.345 | 0.251 | 0.326 |
| **1.5** | **1.99** | **0.306** | **0.192** | **0.281** |
| 3.0 | 1.79 | 0.272 | 0.144 | 0.246 |
| 8.0 | 1.67 | 0.242 | 0.107 | 0.219 |

P(X≥4) varies by a factor of 2.4× across r values that all reproduce the matched 47.8% win rate — so any HRR line away from 1.5/2.5, or any player whose μ differs materially from 2.0, is priced on an unverified distribution shape. The aggregate-WR match also conflates μ-error with r-error (a biased μ with wrong r can reproduce the same aggregate WR). This is acceptable only because HRR is shadow-only and gated at n=50. The fix is cheap: HRR = H+R+RBI is computable per game from the existing 169k-row `mlb_batter_game_stats` table, so the standard within-player var/mu estimator used for RBI/TB can produce a properly identified r today. **Recommendation: recalibrate HRR r from game logs before go-live; the moment-matched 1.5 should not survive the gate on its own.**

**5. Within-player conditional variance is the correct dispersion for pricing a single player's prop — population variance would double-count heterogeneity.**

This follows from the law of total variance: Var(X) = E[Var(X|player)] + Var(E[X|player]). A prop price is P(X_i > line | μ_i) — the engine already conditions on the player's own projected mean, so the between-player component Var(E[X|player]) is removed by conditioning; including it (by using population/cross-player variance) would inflate σ and systematically overprice tails/unders on every player. This is the standard hierarchical-model decomposition used throughout sports analytics (Jensen et al., *Hierarchical Bayesian Modeling of Hitting Performance*, arXiv:0902.1360; Robinson, empirical Bayes hierarchical modeling; Cameron & Trivedi 2013 ch. 9 on conditional vs marginal count models). The estimator r = Σ(n·μ²)/Σ(n·max(var−μ, 0.001)) is a precision-weighted pooled MoM estimator of the conditional dispersion — correct in structure. Two caveats, neither an error: (a) pooling assumes a **common r across players**, but published work fits player-specific dispersion ("consistency") parameters and finds real variation (Binomial Basketball) — a single league r mildly misprices unusually streaky/consistent players; (b) the conditional variance treats μ̂_i as known — the proper posterior-predictive distribution is slightly wider than NB(μ̂, r) because of estimation error in μ̂ (Gelman et al., *BDA*; Jensen et al. 2009). These two effects partially offset the temptation to widen toward population variance but do not justify it.

### Sources
- Cameron, A.C. & Trivedi, P.K. (2013). *Regression Analysis of Count Data*, 2nd ed., Cambridge University Press. https://www.cambridge.org/core/books/regression-analysis-of-count-data/
- Hilbe, J.M. (2011). *Negative Binomial Regression*, 2nd ed., Cambridge University Press. https://www.cambridge.org/core/books/negative-binomial-regression/12D6281A46B9A980DC6021080C9419E7
- Karlis, D. & Ntzoufras, I. (2003). "Analysis of sports data by using bivariate Poisson models," *JRSS Series D (The Statistician)* 52(3). http://www2.stat-athens.aueb.gr/~jbn/papers2/08_Karlis_Ntzoufras_2003_RSSD.pdf
- Wilson, P. (2015). "The misuse of the Vuong test for non-nested models to test for zero-inflation," *Economics Letters* 127:51–53. https://www.sciencedirect.com/science/article/abs/pii/S016517651400490X
- Allison, P. "Do We Really Need Zero-Inflated Models?" Statistical Horizons. https://statisticalhorizons.com/zero-inflated-models/
- Desmarais, B. & Harden, J. (2013). "Testing for zero inflation in count models: Bias correction for the Vuong test," *Stata Journal* 13(4). https://journals.sagepub.com/doi/pdf/10.1177/1536867X1301300408
- Terner, Z. & Franks, A. (2021). "Modeling Player and Team Performance in Basketball," *Annual Review of Statistics and Its Application*. https://arxiv.org/pdf/2007.10550
- Jensen, S.T., McShane, B. & Wyner, A.J. (2009). "Hierarchical Bayesian Modeling of Hitting Performance in Baseball," *Bayesian Analysis*. https://arxiv.org/pdf/0902.1360
- Jacobs, J. (2017). "Basics in Negative Binomial Regression: Predicting Three Point Field Goal Percentages," Squared Statistics. https://squared2020.com/2017/08/20/basics-in-negative-binomial-regression-predicting-three-point-field-goal-percentages/
- Binomial Basketball. "Player Consistency Modeling." https://www.binomialbasketball.com/p/player-consistency-modeling
- UCLA OARC Statistical Consulting. "Negative Binomial Regression" / "Zero-Inflated Negative Binomial Regression." https://stats.oarc.ucla.edu/r/dae/negative-binomial-regression/ ; https://stats.oarc.ucla.edu/r/dae/zinb/
- Robinson, D. "Understanding empirical Bayesian hierarchical modeling (using baseball statistics)," Variance Explained. http://varianceexplained.org/r/hierarchical_bayes_baseball/
- FanGraphs Community. "Run Distribution Using the Negative Binomial Distribution." https://community.fangraphs.com/run-distribution-using-the-negative-binomial-distribution/
- Real Statistics. "Method of Moments: Negative Binomial Distribution." https://real-statistics.com/distribution-fitting/method-of-moments/method-of-moments-negative-binomial-distribution/
- UVA Library. "Getting Started with Negative Binomial Regression Modeling." https://library.virginia.edu/data/articles/getting-started-with-negative-binomial-regression-modeling
- Gonçalves et al. "The Poisson model limits in NBA basketball: Complexity in team sports." https://moldham74.github.io/AussieCAS/papers/Gon.pdf

---

## SECTION 1B — Poisson Distribution Validity

**VERDICT:** CONFIRMED_WITH_CAVEAT
**CLASSIFICATION:** (per-stat)
- GOALS, NHLPTS, NHLBLK, RUNS, BB — **LOCKED** (within-player var/mu ∈ [0.97, 1.08]; Poisson error sub-1pp at all bettable lines)
- HITS, GA — **PERIODIC_RECAL** (under-dispersed at 0.89 / 0.83; ~1–2pp directional error at the lines actually bet; re-check at each annual `calibrate_distributions.py` run)
- SOG — **DATA_GATED** (distribution shape is approximately fine; the suspension evidence implicates the projection *mean*, not the Poisson assumption — see Finding 2)
- REC — **INSUFFICIENT_DATA** (in POISSON_STATS but no calibration row exists; NFL data lands in July)

**Condition to revisit:** Revisit if any annual recalibration shows within-player var/mu drifting outside [0.85, 1.20] for a live stat, or if the G_SOG investigation confirms the mean-error diagnosis below (in which case the distribution should explicitly NOT be changed).

### Findings

**1. MLB HITS (var/mu = 0.89): Poisson error is immaterial at 1.5, borderline at 0.5 — and the risky direction is unders.**

Matched-moment binomial: np = 1.2, np(1−p) = 1.068 → p = 0.11, n = 10.9 → Bin(11, 0.10909) (realized mean 1.200, var 1.069).

| Line | Bet | Poisson(1.2) | Bin(11, 0.109) | Error (Poisson − true) |
|---|---|---|---|---|
| 1.5 | P(X≥2) | **0.3374** | **0.3413** | **−0.40 pp** |
| 0.5 | P(X≥1) | 0.6988 | 0.7193 | −2.05 pp |
| 0.5 | P(X=0) (under) | 0.3012 | 0.2806 | **+2.05 pp** |
| 2.5 | P(X≥3) | 0.1205 | 0.1099 | +1.06 pp |

At the specified test point (proj 1.2, line 1.5) the error is **0.40 pp — immaterial** against a 5–7% edge threshold. The material case is **line 0.5**, where Poisson's excess mass at zero overstates P(no hit) by ~2 pp: that is *phantom edge on HITS unders at 0.5* (and symmetric conservatism on overs at 0.5, which only costs opportunity, not money). The engine's logs confirm HITS candidates are evaluated almost exclusively at 0.5 and 1.5 (`data/pick_log_blocked.csv`), so the 0.5-line case is live, not hypothetical. 2 pp consumes roughly a third of the minimum edge — a caveat, not an error; the under-dispersion mechanism (hits = sum over ~4 ABs of a Bernoulli trial, var = np(1−p) < np by construction) is exactly what the Conway-Maxwell-Poisson and binomial families are for (Sellers 2021; Florez et al. 2024). If HITS under-0.5 picks ever show win-rate underperformance vs model, a matched-variance binomial (or CMP with ν>1) at lines ≤1.5 is the principled fix.

**2. NHL SOG: literature supports mild player-level overdispersion, and the engine's own data confirms it grows with shot volume — but it is an order of magnitude too small to explain the suspension evidence. The SOG failure is a conditional-mean error, not a distribution error.**

Literature: game-level hockey count events are conventionally modeled as Poisson (Buttrey, Washburn & Price 2011, "Estimating NHL Scoring Rates," JQAS 7(3); Dejardine, "Poisson Processes and Applications in Hockey"; hockeyanalytics.com "Poisson Toolbox"), while season/aggregate-level counts are repeatedly found negative binomial because rate heterogeneity (TOI, PP time, matchup, score effects) gamma-mixes the conditional Poisson (Pollard, "Goal-Scoring and the Negative Binomial Distribution," Math. Gazette; Florez et al. 2024 note NB is standard for North American leagues "prone to overdispersion"). Thomas (2007) shows hockey events are a semi-Markov process, not time-homogeneous Poisson — i.e., within-game rate variation exists, which is precisely the mechanism that produces marginal overdispersion. No published paper specifically models *individual-player* SOG distributions; the prop-modeling trade literature lists Poisson and NB as the standard candidates without resolving the choice (OpticOdds).

Engine's own data (read-only stratification of `data/projections.db`, `nhl_skater_game_stats`, players with ≥40 games):

| Player mean SOG | n players | Pooled within-player var/mu | Frac. individually var>mu |
|---|---|---|---|
| <1.0 | 212 | 1.086 | 0.64 |
| 1.0–2.0 | 461 | 1.115 | 0.76 |
| 2.0–3.0 | 146 | 1.119 | 0.84 |
| ≥3.0 | 28 | **1.150** | **0.86** |

So yes — the literature's mixed-Poisson prediction holds: overdispersion is real and concentrated in elite shooters (the league-wide 1.069 in `docs/calibration_results.json` is diluted by low-volume players). **But the magnitude is decisive:** at μ=3.4, line 3.5, P(under) is 0.5584 under Poisson vs 0.5646 under NB(var/mu=1.15) — a 0.6 pp shift, and in the **wrong direction** (NB makes unders *more* likely; the model was already too bullish on unders). The suspension evidence — model 63.7% vs actual 42.9% on unders ≤3.5 — requires the true conditional mean to have been ~1 full shot higher than projected: Poisson P(X≤3 | λ=3.05) = 0.636 ≈ the model's claim, while P(X≤3 | λ=4.0) = 0.434 ≈ the actual win rate. **No distribution swap can close a 21 pp calibration gap when the shape error is ≤1.6 pp** (even at an implausible var/mu=1.40, the shift is only 1.55 pp). The G_SOG investigation should target systematic under-projection of shot volume for high-volume shooters (TOI/PP-share/role inputs, or stale EWMA on shot rate), not the Poisson assumption. Replacing Poisson with NB here would be a band-aid that slightly *worsens* the observed bias.

**3. MLB BB (var/mu = 0.992): Poisson is appropriate; keep it.**

At 0.992 the data is statistically indistinguishable from equidispersed across 69k pitcher games. The more principled generative model in the literature is per-PA Bernoulli aggregated over a variable number of batters faced — the beta-binomial empirical-Bayes framework standard in baseball rate modeling (Robinson 2016, "Understanding beta binomial regression (using baseball statistics)"; Probabilaball 2015) — but two offsetting effects (binomial thinning pushes var/mu below 1; game-to-game rate/PA heterogeneity pushes it above) evidently net to ≈1 here. A beta-binomial would add a parameter to fit noise. Poisson is correct in the only sense that matters: the implied probabilities at lines 0.5–3.5 are within rounding of the truth.

**4. General — under-dispersed stats (GA 0.83, HITS 0.89, RUNS 0.97, BB 0.99): Poisson's excess variance pulls near-mean probabilities toward 50% and inflates both extremes.**

Directionally: the true (concentrated) distribution has *less* mass at 0 and in the high tail, *more* mass near the mean, than Poisson. Consequences, with GA as the worst case (λ=2.8, matched Bin(16, 0.175), var/mu=0.83):
- **Near-mean lines:** Poisson P(X≥3) = 0.5305 vs true 0.5490 (−1.84 pp). The model is systematically **too conservative on the favored side of lines near the projection** — it understates how often a concentrated distribution lands on its modal side. This loses +EV picks (opportunity cost) but does not create losing picks.
- **Tails and zeros:** Poisson P(X≥4) = 0.3081 vs 0.3028 (+0.52 pp); P(X=0) overstated (HITS: +2.05 pp). The model finds **phantom edge on zero-outcome unders and high-line overs** — small adverse selection in the direction that costs money.

So probabilities at lines near the projection are pulled toward 50%, making the model too conservative exactly where its edge is most reliable, while being mildly anti-conservative in the tails. Magnitudes (0.5–2 pp) sit below the 5–7% edge threshold individually, which is why this is a caveat rather than a NEEDS_CHANGE — but the bias is *systematic*, not noise, and the CMP family is the published remedy when it matters (Sellers & Shmueli, "The COM-Poisson model for count data"). For GA specifically, two structural mechanisms plausibly drive the 0.83: goalie pulls truncate the right tail of a struggling goalie's GA count mid-game, and score-dependent play (Thomas 2007 found a goal "shortens" the remaining game ~20s; score effects modulate shot/goal rates — Hockey Graphs, score effects) acts as negative feedback that compresses variance.

**5. NHLPTS (goals + assists): Poisson is justified — empirically and structurally.**

Theory: a sum of two *independent* Poissons is exactly Poisson; dependence breaks this. Karlis & Ntzoufras (2003), JRSS-D 52, 381–393 is the canonical treatment: a bivariate Poisson with a *positive* common shock makes the sum overdispersed. Hockey-specific work: Thomas (2007) rejects pure Poisson in favor of semi-Markov for inter-arrival structure but the deviations are second-order at game-count level; Buttrey, Washburn & Price (2011) model NHL scoring as a Poisson process with situational rates "adequately" for prediction. (Macdonald's 2012 Sloan paper is an expected-goals *rate* model, not a distributional claim — relevant context only.) Critically, the engine's own calibration resolves the dependence question: var(points) = 0.4635 < var(goals) + var(assists) = 0.2019 + 0.2965 = 0.4984, implying within-player Cov(G,A) ≈ **−0.017** — *slightly negative*, the opposite of the dangerous (common-shock) case. The mechanism is credit competition: on any single team goal, a given player receives a goal *or* an assist, never both, so the components compete rather than co-move. Result: NHLPTS var/mu = 0.983, mildly under-dispersed, safely Poisson. CONFIRMED.

**Summary of caveats (no file changes made):**
- SOG: distribution exonerated; feed Finding 2 (mean error ≈ +1.0 shot on elite shooters, λ 3.05 implied vs 4.0 actual) into the G_SOG_SUSPENDED investigation. Do not swap to NB as a fix.
- HITS line-0.5 unders and GA near-mean lines carry a 1–2 pp systematic Poisson error; monitor at recalibration, with binomial/CMP as the published fix if live win rates confirm.
- REC is in POISSON_STATS with zero calibration evidence — calibrate when NFL data arrives in July.

### Sources
- Buttrey, S., Washburn, A. & Price, W. (2011). "Estimating NHL Scoring Rates." *Journal of Quantitative Analysis in Sports* 7(3). https://faculty.nps.edu/awashburn/docs/EstimatingNHLScoringRates.pdf
- Thomas, A.C. (2007). "Inter-arrival Times of Goals in Ice Hockey." *Journal of Quantitative Analysis in Sports* 3(3). https://hockeyanalytics.com/Research_files/Interarrival%20Times%20of%20Goals%20in%20Ice%20Hockey.pdf
- Karlis, D. & Ntzoufras, I. (2003). "Analysis of Sports Data by Using Bivariate Poisson Models." *JRSS Series D (The Statistician)* 52, 381–393. http://www2.stat-athens.aueb.gr/~jbn/papers2/08_Karlis_Ntzoufras_2003_RSSD.pdf
- Sellers, K.F. (2021). "Conway–Maxwell–Poisson regression models for dispersed count data." *WIREs Computational Statistics*. https://wires.onlinelibrary.wiley.com/doi/10.1002/wics.1533
- Sellers, K.F. & Shmueli, G. (2010). "A Flexible Regression Model for Count Data" (COM-Poisson). *Annals of Applied Statistics*. https://faculty.georgetown.edu/kfs7/MY%20PUBLICATIONS/COMPoissonModelForCountDataWithDiscussion.pdf
- Florez, A. et al. (2024). "Bayesian Bivariate Conway-Maxwell-Poisson Regression Model for Correlated Count Data in Sports." arXiv:2409.17129. https://arxiv.org/abs/2409.17129
- Pollard, R. "Goal-Scoring and the Negative Binomial Distribution." *The Mathematical Gazette* (note 69.9). https://www.researchgate.net/publication/270311475_699_Goal-Scoring_and_the_Negative_Binomial_Distribution
- Macdonald, B. (2012). "An Expected Goals Model for Evaluating NHL Teams and Players." *MIT Sloan Sports Analytics Conference*. https://www.researchgate.net/publication/236687040_An_Expected_Goals_Model_for_Evaluating_NHL_Teams_and_Players
- Robinson, D. (2016). "Understanding beta binomial regression (using baseball statistics)." varianceexplained.org. http://varianceexplained.org/r/beta_binomial_baseball/
- Probabilaball (2015). "Beta-Binomial Empirical Bayes." http://www.probabilaball.com/2015/05/beta-binomial-empirical-bayes.html
- Dejardine, A. "Poisson Processes and Applications in Hockey." Lakehead University. https://www.lakeheadu.ca/sites/default/files/uploads/77/docs/DejardineFinal.pdf
- Hockey Analytics. "The Poisson Toolbox." http://hockeyanalytics.com/Research_files/Poisson_Toolbox.pdf
- OpticOdds. "Probability Paths: Monte Carlo vs. Parametric Distributions in Player Prop Modeling." https://opticodds.com/blog/probability-paths-in-player-prop-modeling
- Hockey Graphs — score effects tag (variance-compression context for GA). https://hockey-graphs.com/tag/score-effects/

Internal evidence used (read-only): `engine/run_picks.py` (lines 375–376, 891), `docs/calibration_results.json`, `data/projections.db` (`nhl_skater_game_stats`, 51k+ rows, ≥40-game players), `data/pick_log.csv` / `pick_log_blocked.csv` (line/direction mix for SOG and HITS).

---

## SECTION 1C — Normal Distribution for Continuous Props

**VERDICT:** NEEDS_CHANGE (per-stat: PTS=CONFIRMED_WITH_CAVEAT, SV=CONFIRMED, OUTS=NEEDS_CHANGE, PC=NEEDS_CHANGE, WNBA PTS=NEEDS_CHANGE)

**CLASSIFICATION:**
- NBA PTS: PERIODIC_RECAL (annual offseason refit)
- SV: PERIODIC_RECAL
- OUTS: NEEDS_CHANGE now → then PERIODIC_RECAL
- PC: NEEDS_CHANGE now → DATA_GATED on whether an empirical-CDF model replaces Normal
- WNBA PTS: NEEDS_CHANGE now → PERIODIC_RECAL

**Condition to revisit:** Re-audit if the priced prop population shifts toward low-μ players (bench PTS lines < 10), or after the July offseason refit recalibrates OUTS/PC/WNBA sigmas on the corrected sampling frames below.

> **Audit-coordinator verification (2026-06-05):** the headline sampling-frame claim was independently re-run against `data/projections.db` (`mlb_pitcher_game_stats`, 69,022 rows of which 16,190 are starts): within-pitcher CV for `ip_outs` — ALL appearances median 0.417, STARTS-only median **0.228**, RELIEF-only 0.454; for `pc` — ALL 0.433, STARTS-only **0.142**, RELIEF 0.460. The deployed mults (0.311 / 0.375) sit between the two roles and are confirmed to be contaminated by relief appearances. NEEDS_CHANGE verified.

### Findings

**Headline:** The Normal *family* is defensible for all four stats at the lines actually priced — the literature supports Normal for high-expectation scoring-type stats — but three of the five deployed multipliers are calibrated on the wrong sampling frame. Verified directly against the project's own databases (read-only queries, `data/projections.db` and `EdgeModel/data/projections.db`); the OUTS/PC calibration mixed relief appearances into a starters-only market, and the WNBA PTS calibration is dominated by sub-8-PPG players who are never priced.

**1. NBA PTS — Normal is valid for the priced population; low-μ players are the weak spot (CONFIRMED_WITH_CAVEAT).**
Published work consistently finds player scoring is an overdispersed count best described by negative binomial: Binomial Basketball's hierarchical NB model explicitly rejects Poisson because it "capped Giannis at 49 points" and required a per-player overdispersion parameter ("Predicting Sensational Stats, pt 3"); Martín-González et al. show basketball scoring variance is inflated relative to Poisson and model it as a gamma-Poisson (= NB) mixture (*Physica A*, 2016). However, Normal-with-empirical-σ converges to the right answer at high μ: Bergman et al. (Shapiro-Wilk tests on fantasy scores) found normality cannot be rejected for 76% of QBs and that "as the expected score increases, the likelihood of rejecting the assumption of normally distributed actual scores falls across all players" — they use a Gaussian model precisely for players projected ≥ ~10 points (arXiv:2112.07002, §6.2.3).

Empirical verification on the project's own 3-season NBA log confirms the μ-dependence the literature predicts:

| Player PPG bucket | within-player CV (median) | skewness (median) |
|---|---|---|
| <8 | 0.594 | **0.866** |
| 8–14 | 0.498 | 0.600 |
| 14–20 | 0.422 | 0.333 |
| 20+ | **0.331** | 0.286 |

The deployed mult=0.35 matches the 20+ PPG bucket (0.331) almost exactly — correct for the stars who dominate PTS prop volume; var/μ for 20+ scorers is 2.86, so Poisson would be badly too tight and Normal-with-CV is the right call. Skew ≈ 0.29 at 20+ PPG means the symmetric approximation costs ~1pp at typical lines. Where Normal degrades is exactly where the literature says: μ<8 (skew 0.87, discreteness). There the min=5.0 floor gives CV=0.625, fortuitously matching the empirical 0.594 — the floor is doing real work. Caveat: the [0,∞) truncation renormalization shifts the implied conditional mean up by σ·φ(μ/σ)/Φ(μ/σ) = +0.59 pts at μ=8/σ=5 (+7.3% of μ), systematically inflating low-μ over_p — consistent with the engine's own comment ("+0.5–4pp") and one reason `KELLY_MARKET_MULT` NBA-PTS-over=0.50 has been needed. The mid-range (14–20 PPG, empirical CV 0.42 vs engine 0.35) is ~17% tight versus the *marginal* within-player CV, but conditional-on-projection residual σ should be smaller than marginal σ, and the mult was confirmed by MAE backtest — acceptable.

**2. OUTS — Normal is marginally defensible at lines 12.5–19.5, but the deployed CV=0.311 is contaminated by relief appearances (NEEDS_CHANGE).**
The calibration note says "within-player CV=0.311 from 69k pitcher game-logs" — but 69,022 rows = all appearances, of which only ~16k are starts (`is_starter=1`). Recomputation:

| Sample | OUTS within-player CV | PC within-player CV |
|---|---|---|
| All appearances (deployed frame) | 0.412 med / 0.421 mean | 0.432 / 0.417 |
| **Starts only** (the priced market) | **0.225 / 0.231** | **0.137 / 0.144** |
| Relief only | 0.443 / 0.448 | 0.460 / 0.476 |

(Coordinator re-run with min 10 appearances per pitcher: starts-only OUTS 0.228/0.239, PC 0.142/0.156 — same conclusion.) The deployed 0.311 sits between the two roles and exceeds even the pooled cross-pitcher population CV of starts (0.276). OUTS props are only offered on confirmed starters, so σ is ~35–38% too wide: at proj=16.5/line=14.5, engine over_p = Φ(2.0/5.13) = 0.652 vs ≈0.70 with the correct σ — a ~5pp mispricing on an active market. Distribution shape: starter outs have mean 15.52, sd 4.29, **skew −0.79**, P(outs≤6)=5.0% (blowup hooks), P(outs≥27)=0.5%. This matches the published structure — FanGraphs' Ben Clemens documents the bulk at 4.1–6 IP (13–18 outs) with the historical right tail compressed by pitch-count policy, and managerial censoring at ~100 pitches is well documented. A symmetric Normal with the correct σ≈3.8 underprices the blowup left tail (predicts 0.9% vs 5.0% empirical for ≤6 outs); the current too-wide σ accidentally buys back some left tail while wrecking the center. **Exact change:** recalibrate `SIGMA["OUTS"]` on `is_starter=1` only — interim mult ≈ 0.27 (pooled-start CV, retains a left-tail buffer over the 0.225 within-pitcher value), validated by the same MAE backtest used for NBA PTS; at the July refit, prefer an empirical/skew-aware CDF (or simulation per OpticOdds' hybrid recommendation) over symmetric Normal. Note the existing OUTS-under prob gate (run_picks.py:1223) and Kelly mult 0.50 are symptom patches for exactly this — per the no-band-aids principle, fixing σ is the cause-level fix.

**3. SV — Normal-with-empirical-CV is the right model and correctly calibrated in family; mult slightly tight (CONFIRMED).**
Goals and shots are canonically Poisson in hockey (Ryder, "The Poisson Toolbox," Hockey Analytics, 2004), but saves = (shots faced) × (save%) is a *mixed* process: game-to-game variation in opponent shot volume makes the marginal save count overdispersed. Verification on the project's 15k goalie logs: within-goalie var/μ for starts = **2.07** (Poisson would require 1.0), so Poisson σ=√26.6=5.2 would be far too tight; pooled starter saves have mean 25.1, sd 7.3, and **skew −0.07 — essentially perfectly symmetric**. At μ≈26 with near-zero skew, Normal is an excellent approximation for an overdispersed count (standard high-λ regime). The mult already encodes the overdispersion (engine σ=6.73 at μ=26.6 vs Poisson 5.2) — this is the correct design. One minor note: starter-only within-goalie CV is 0.288–0.290 vs deployed 0.253 (~12% tight; σ 6.73 vs 7.66). Conditioning on opponent shot-volume projections justifies some of that gap; worth a recheck at the next NHL refit, not a change now. The untruncated CDF is fine — sub-zero mass at μ=26.6/σ=6.7 is Φ(−3.97) ≈ 0.004%, negligible.

**4. WNBA PTS mult=0.618 — a sampling-frame artifact, not a real 77% volatility premium (NEEDS_CHANGE).**
The decisive test: applying the *identical* filter (min≥8 minutes) to the NBA log yields within-player CV = **0.615** — statistically indistinguishable from the WNBA's 0.618. The "WNBA is 77% more volatile" comparison is 0.618-at-min≥8 vs 0.35-at-the-stars-bucket — different frames. CV is strongly μ-dependent (count-stat property: CV ≈ √(1/μ + 1/r) falls with μ), and the WNBA min≥8 sample has median player-mean **7.2 PPG** (115 of 202 players under 8 PPG) — players who are never priced. For the population WNBA props actually price:

| WNBA PPG bucket (min≥8 frame) | within-player CV (median) |
|---|---|
| <8 | 0.760 |
| 8–12 | 0.580 |
| 12–16 | 0.460 |
| 16+ | **0.396** |

Like-for-like (WNBA 16+ = 0.396 vs NBA 20+ = 0.331), the genuine WNBA premium is ~15–20% — plausible given 40-minute games, lower scoring means, and roster volatility, and directionally consistent with the genuinely higher WNBA overdispersion the engine already found elsewhere (3PM var/μ=1.71 vs NBA 1.15). It is not 77%. Consequences of the inflated mult: at proj=14, σ=8.65 compresses every win_prob toward 0.5 (suppressing legitimate picks under `WNBA_EDGE_FLOOR`), and — since WNBA PTS *does* get the truncation correction (code-verified: line 939 keys on `stat == "PTS"` regardless of sport) — the 5.3% sub-zero mass at σ=8.65 produces a +0.99-point effective-mean shift, inflating over_p by ~4–5pp; with a corrected σ≈6.4 the shift is only +0.25. So the oversized σ both flattens probabilities *and* injects an over-side bias through the truncation renormalizer. **Exact change:** recalibrate `SIGMA_WNBA["PTS"]` on the priced population (min≥20 minutes, or stratify by player scoring mean) → expected mult ≈ **0.46–0.50** (min=3.5 unchanged). The same min≥8 frame produced AST=0.779 and REB=0.633 — those feed the G14 z-gate and combo sigmas and should be re-checked in the same pass. Low-μ skewness concerns at WNBA scoring levels are real but secondary to the frame error. Fortunate timing: WNBA is still in shadow (0/100 gate), so no live money has been priced off this.

**4b. PC — worst of both worlds: wrong mult AND weakest Normal fit (NEEDS_CHANGE).**
Starts-only within-pitcher CV is **0.137–0.144** vs deployed 0.375 — 2.6× too wide. Normal(90, 33.75) puts P(PC≥120) = 18.7%; empirically **0.04%** of starts (6 of ~16k) reach 120 pitches — a ~450× tail error, reflecting the hard managerial cap ("almost every arm is allotted… 80 to 100" — Driveline Baseball, 2025; >125 now rare). Starter PC also has skew **−1.93** (right-censored at the cap, long left blowup tail) — the most non-Normal of the four stats. **Exact change:** recalibrate on `is_starter=1` (interim mult ≈ 0.18–0.20, the pooled-start CV=0.204, generous vs the 0.14 within-pitcher value), and treat Normal as provisional — PC is the strongest candidate among these four for an empirical-CDF replacement. If PC is a shadow/low-volume market, deprioritize accordingly, but don't leave 0.375 in place.

**5. Industry practice.** Published quant practice supports Normal for high-volume "points-like" stats while reserving discrete models for low counts: Bergman et al. explicitly justify a multivariate Gaussian for players with high expected scores via Shapiro-Wilk evidence (arXiv:2112.07002); OpticOdds describes the industry toolkit as "Poisson, Negative Binomial, Normal, and Log-Normal" parametric screens backstopped by Monte Carlo for tail precision; Andrew Mack's widely used texts recommend negative binomial specifically for overdispersed counts and prop bets (*Statistical Sports Models in Excel*); Unabated (Capt. Jack Andrews) stresses that skewed stats must be priced off the full distribution/median, not the mean; Wizard of Odds documents distribution-based prop pricing as standard. The engine's architecture — Normal for high-μ stats, Poisson/NB for low counts — matches this consensus; the defects found here are calibration-frame errors, not architecture errors.

### Sources
- Bergman, D., Cardonha, C., Imbrogno, J., Lozano, L. (2021, rev. 2024). arXiv:2112.07002, §6.2.3 Normality Assumption. https://arxiv.org/abs/2112.07002
- Binomial Basketball (2023). *Predicting Sensational Stats, pt 3*. https://www.binomialbasketball.com/p/predicting-sensational-stats-pt-3
- Martín-González, J.M., de Saá Guerra, Y., García-Manso, J.M., et al. (2016). *The Poisson model limits in NBA basketball: Complexity in team sports*. *Physica A* 464. https://www.sciencedirect.com/science/article/abs/pii/S0378437116304599
- Clemens, B. (2024). *A Deeper Dive Into Pitcher Usage Trends*. FanGraphs. https://blogs.fangraphs.com/a-deeper-dive-into-pitcher-usage-trends/
- Ryder, A. (2004). *The Poisson Toolbox*. Hockey Analytics. http://hockeyanalytics.com/2004/09/poisson-toolbox/
- Driveline Baseball (2025). *In Search of A Smarter Pitch Count*. https://www.drivelinebaseball.com/2025/09/in-search-of-a-smarter-pitch-count/
- Wikipedia. *Pitch count*. https://en.wikipedia.org/wiki/Pitch_count
- Shurzy (2024). *Pitcher Outs Recorded Props*. https://content.shurzy.com/post/baseball-betting-explained-pitcher-outs-recorded-props
- OpticOdds (2024). *Probability Paths: Monte Carlo vs. Parametric Distributions in Player Prop Modeling*. https://opticodds.com/blog/probability-paths-in-player-prop-modeling
- Mack, A. (2019). *Statistical Sports Models in Excel*.
- Andrews, J. / Unabated (2024). *Profitable Prop Betting In 3 Easy Steps*. https://unabated.com/articles/profitable-prop-betting-in-3-easy-steps
- Wizard of Odds. *Player Props: Understanding the Math Behind the Lines*. https://wizardofodds.com/article/player-props-understanding-the-math-behind-the-lines/
- Whitestone, I. *NBA Daily Fantasy Sports analysis and player modelling with R*. https://ianwhitestone.work/nba-dfs/
- Internal verification (read-only): `data/projections.db` (16,190 MLB starts; 7,630 goalie starts; 84k NBA player-games) and `EdgeModel/data/projections.db` (13.3k WNBA player-games); independently re-verified by audit coordinator (table above).

---

## SECTION 1D — Normal Truncation Formula
**VERDICT:** CONFIRMED_WITH_CAVEAT
**CLASSIFICATION:** LOCKED
**Condition to revisit:** Revisit only if graded low-line PTS picks (line ≤ 6.5, μ < 10) show systematic over-side miscalibration — the fix would be a count model (NB) for bench PTS, not a change to this formula, which is mathematically exact.

### Findings

**1. Derivation and verification of the formula — CORRECT.**

Let X ~ N(μ, σ²) and condition on X ≥ 0. For t ≥ 0, by the definition of conditional probability:

P(X > t | X ≥ 0) = P(X > t ∩ X ≥ 0) / P(X ≥ 0) = P(X > t) / P(X ≥ 0)   (since t ≥ 0 ⟹ {X > t} ⊂ {X ≥ 0})
= [1 − Φ((t−μ)/σ)] / [1 − Φ((0−μ)/σ)] = [1 − Φ((t−μ)/σ)] / [1 − Φ(−μ/σ)] = [1 − Φ((t−μ)/σ)] / Φ(μ/σ)

(last step by Φ(−z) = 1 − Φ(z); the continuous distribution makes P(X ≥ 0) = P(X > 0)). This matches the standard one-sided truncated Normal: for truncation to [a, b], the CDF is F(x) = [Φ(ξ) − Φ(α)]/Z with Z = Φ(β) − Φ(α); for b = +∞, Φ(β) = 1 and Z = 1 − Φ(α) (Johnson–Kotz–Balakrishnan §10.1; Greene, *Econometric Analysis*, truncation chapter). With a = 0, α = −μ/σ.

Mapping to the code (`engine/run_picks.py:939-946`):
- `phi_zero = normal_cdf(0, proj, sigma)` = Φ((0−μ)/σ) = Φ(−μ/σ) ✓ (mass below 0)
- `phi_above_zero = 1 − phi_zero` = 1 − Φ(−μ/σ) = Φ(μ/σ) = Z ✓
- `over_p = (1 − normal_cdf(line, μ, σ)) / phi_above_zero` = [1 − Φ((t−μ)/σ)]/Z — **exactly the derived survival function** ✓
- `under_p = (normal_cdf(line, μ, σ) − phi_zero) / phi_above_zero` = [Φ((t−μ)/σ) − Φ(−μ/σ)]/Z = P(0 ≤ X ≤ t | X ≥ 0) — **exactly the truncated CDF** ✓

Sum check, algebraically: over_p + under_p = [1 − Φ_t + Φ_t − Φ_0]/(1 − Φ_0) = (1 − Φ_0)/(1 − Φ_0) = 1 exactly. Numerically verified (μ=8, σ=5, line=6.5): sum = 0.9999999999999999 (float ε only). The `max(…, 1e-9)` guard would break the identity only if it bound, which requires Φ(−μ/σ) ≥ 1 − 1e-9, i.e., μ/σ ≈ −6 — impossible since proj > 0. Harmless safeguard. Note the in-code comment `Φ(μ/σ)` on line 941's denominator is correct notation for `1 − Φ(−μ/σ)`.

**2. When truncation matters — quantified** (σ = max(0.35μ, 5.0); all diffs are truncated − untruncated over_p; truncation always *raises* over_p):

| Case | μ | σ | μ/σ | phi_zero | Δ over_p @ line=μ−1.5 | Δ over_p @ line=μ+1.5 |
|---|---|---|---|---|---|---|
| a | 20 | 7.0 | 2.86 | 0.00214 | +0.125 pp | +0.089 pp |
| b | 12 | 5.0 | 2.40 | 0.00820 | +0.511 pp | +0.316 pp |
| c | 8 | 5.0 | 1.60 | 0.05480 | +3.582 pp | +2.215 pp |
| d | 5 | 5.0 | 1.00 | 0.15866 | +11.652 pp | +7.205 pp |

Threshold: at line ≈ μ the correction is 0.5·phi_zero/(1−phi_zero), which exceeds 0.5 pp when phi_zero > 0.0099, i.e., **μ/σ < 2.33**. Under the engine's PTS sigma: for μ ≥ 14.29 the multiplier binds and μ/σ = 1/0.35 = 2.857 (correction ≈ 0.07–0.13 pp, immaterial); for μ < 14.29 the σ=5.0 floor binds, so μ/σ = μ/5 and the correction crosses 0.5 pp at **μ ≈ 11.65 points**. Truncation is material precisely for bench-scorer PTS props and grows fast below μ=10 (case c: +3.6 pp; case d: +11.7 pp — both well above the 5% edge floor's 0.5 pp materiality bar).

**3. PTS-only application is internally consistent for the live Normal stats.** For any mult-based sigma above its floor, μ/σ = 1/mult is constant: OUTS 1/0.311 = 3.22 (phi_zero ≤ 7.1e-4 at the floor-bound worst case μ=15, σ=4.7 → correction 0.035 pp), SV 1/0.253 = 3.95 (μ=26.6, σ=6.7: phi_zero = 3.6e-5 → 0.0018 pp). Their σ floors (1.0, 3.5) bind only at μ values those stats never take (a starting pitcher with μ<3.2 outs; a starting goalie with μ<13.8 saves). PTS is unique because its σ floor (5.0) binds at realistic projections (bench μ=5–12), driving μ/σ as low as 1.0. So skipping truncation for OUTS/SV/PC is correct. Two genuine edge notes: (i) **combos** (PRA/PR/PA, plain Normal) can reach μ/σ < 2.33 for low-usage players — e.g., PR with μ≈10, σ_combo≈5.9 → phi_zero ≈ 0.045, ~2.4 pp missing correction — but books rarely post combo props on deep-bench players and RA is already disabled, so exposure is small; (ii) **WNBA PTS** (mult 0.618 → μ/σ = 1.62 above the floor, phi_zero ≈ 0.053) routes through the same `stat == "PTS"` branch sport-agnostically, so it correctly *receives* the truncation it badly needs. Net: the conditional is in the right place.

**4. Discrete/zero-mass caveat — real but second-order vs the truncation fix.** A truncated continuous Normal sets P(X ≤ 0) = 0 and redistributes the clipped mass proportionally upward; real bench PTS has a genuine point mass at exactly 0 (played-but-scoreless games) and strong right skew. Illustration at μ=6, σ=5, line=4.5: truncated-Normal over_p = 0.698; a Negative Binomial with the same mean and realistic points overdispersion (var/μ = 3 → r = 3, P(X=0) = 3.7% before accounting for the empirically higher zero rate) gives P(X > 4.5) = 0.571 — the truncated Normal **overstates the over by ~13 pp on low lines** because it has too little left-tail/zero mass and too symmetric a body. This is the standard finding in the sports-count literature: low-mean integer outcomes are better modeled by Poisson/NB-family count models than by any Normal variant (Karlis & Ntzoufras 2003 on Poisson-family goal models; the engine itself already concedes this by using NB for 3PM/AST/REB and Poisson convolution for TB). Truncation is the mathematically correct *Normal-family* fix and strictly improves on the untruncated Normal; it does not fix skew. The existing `KELLY_MARKET_MULT` NBA PTS-over = 0.50 dampener partially hedges this in practice. No change recommended now; if low-line PTS overs grade poorly, the remedy is an NB path for μ < ~10 PTS, not a different truncation formula.

### Sources
- Wikipedia — Truncated normal distribution (https://en.wikipedia.org/wiki/Truncated_normal_distribution) — CDF F(x) = [Φ(ξ) − Φ(α)]/Z, Z = Φ(β) − Φ(α), one-sided case Z = 1 − Φ(α); cites Johnson, Kotz & Balakrishnan, *Continuous Univariate Distributions* Vol. 1 (2nd ed., 1994), §10.1, and Greene, *Econometric Analysis* (5th ed., 2003), truncation chapter
- Burkardt, "The Truncated Normal Distribution" (FSU technical reference). https://people.sc.fsu.edu/~jburkardt/presentations/truncated_normal.pdf — lower-truncated PDF normalized by 1 − cdf(a)
- Olive, *Statistical Theory* Ch. 4 — Truncated Distributions (SIU). http://parker.ad.siu.edu/Olive/ch4.pdf
- Karlis, D. & Ntzoufras, I. (2003), "Analysis of sports data by using bivariate Poisson models," *The Statistician* 52(3) — count-model precedent for low-mean sports outcomes (Q4)
- Numerical verification: Python erf-based Φ, this audit (all table values reproducible from the formulas above)

---

## SECTION 1E — POISSON_CUTOFF = 8.5
**VERDICT:** CONFIRMED_WITH_CAVEAT
**CLASSIFICATION:** LOCKED
**Condition to revisit:** Revisit at NFL go-live (July architecture) — REC is the only POISSON_STATS member with realistic market lines > 8.5, and it would route to the fallback-sigma Normal branch with no calibrated SIGMA entry.

### Findings

**1. Theory vs. the line-based cutoff — the rule is λ-based, and the conventional threshold is λ ≥ 10 (with continuity correction).**
The standard treatment: a Poisson(λ) variable is the sum of λ i.i.d. Poisson(1) variables, so the CLT applies in λ, and the conventional rule of thumb is that Normal(μ=λ, σ²=λ) is a good approximation "if λ is greater than about 10, provided an appropriate continuity correction is performed" (standard texts; Cambridge A-Level 9709 and AP Statistics curricula). Some texts allow λ ≥ 5 with continuity correction; conservative texts say λ ≥ 20 without. The rigorous bound is Berry–Esséen: sup-norm CDF error ≤ C/√λ with C < 0.7164, with actual errors ~3× smaller (John D. Cook); empirically the max CDF error near λ=10 is ≈0.083 without continuity correction and ≈0.021 with it.

A LINE cutoff of 8.5 proxies the λ rule only if line ≈ λ (true for a fair line, since books set lines near the median ≈ mean for Poisson). So line ≤ 8.5 → λ ≲ 9, which lands just under the λ ≥ 10 convention — directionally consistent. **But the logic is inverted in one important sense: where the rule says Normal becomes *acceptable* (λ ≥ 10), it never becomes *necessary*.** If the stat is genuinely Poisson (and the engine's own calibration says these are: var/μ = 0.97–1.08 across 141k–169k game logs), the Poisson CDF is *exact* at every line. The Normal branch is an approximation to the truth, switched to precisely where it's least needed. The implementation at run_picks.py:759–772 (naive `exp(-λ)·λᵏ/k!` summation) is numerically safe to λ ≈ 250, so there is no computational reason to switch either.

**2. Boundary error math (λ=9, line=8.5).** Computed exactly:

| Path | P(over) | Error vs exact |
|---|---|---|
| Poisson exact: P(X ≥ 9 \| λ=9) = 1 − F(8) | **0.54435** | — |
| Normal(μ=9, σ=3.0) at 8.5 (variance-matched, σ=√9) | 0.56618 | **+2.18pp** |
| Normal(μ=9, σ=3.6) at 8.5 (actual fallback: max(0.40×9, 2.0)=3.6) | 0.55523 | **+1.09pp** |

Continuity correction: at a half-point line, evaluating the Normal CDF at 8.5 *is* the continuity-corrected evaluation of P(X ≥ 9), so the missing explicit correction is moot for half lines. (Integer lines in the Normal branch would get no push adjustment — a real flaw, but in the same dead branch.)

The fallback σ=3.6 *coincidentally* beats σ=3.0 at this exact point (the line sits below the mean, so the wider σ pulls over_p back toward the Poisson value). This is an artifact, not calibration. Move λ off the line and the σ mismatch dominates:

- λ=12, line=8.5: Poisson = 0.8450; Normal(σ=√12) = 0.8438 (**−0.11pp**, shape error ≈ nil); Normal(fallback σ=4.8) = 0.7671 (**−7.79pp**).
- λ=12, line=9.5: Poisson = 0.7576; Normal(σ=√12) = 0.7648 (+0.71pp); Normal(fallback σ=4.8) = 0.6988 (**−5.88pp**).

**Conclusion: the σ mismatch (0.40×proj vs √proj) is the larger error source — up to ~8pp, vs ≤2.2pp for Normal-vs-Poisson shape error at the boundary.** A 5–8pp probability error is far above the engine's edge thresholds, so this branch would produce materially wrong picks *if it were ever reached*.

**3. Conditioning variable: theory cares about λ (the parameter), not the line (the evaluation point).** The CLT-in-λ argument in (1) makes this unambiguous — accuracy of the Normal approximation is governed by the distribution's parameter, not where you evaluate the CDF. The current rule gets the two cases backwards relative to its own intent:
- proj=12, line=8.5 → stays Poisson. Outcome correct (Poisson is exact), but for the "wrong" reason — λ=12 is exactly where the rule of thumb would have permitted Normal.
- proj=7, line=9.5 → goes Normal with fallback σ = max(0.40×7, 2.0) = 2.8 vs true √7 = 2.65. P(X > 9.5): Poisson exact = 0.1695; fallback Normal = 0.1860 (**+1.65pp absolute = +9.7% relative on a 17% tail**) — material mispricing of a longshot over.

If a cutoff must exist it should key on proj, **but the cleaner fix is no cutoff at all for confirmed-Poisson stats** — exact CDF at every line, one branch deleted. In practice it barely matters: scanning all pick logs, observed lines are SOG 2.5–3.5 (n=58, exempt anyway), NHLBLK ≤2.5, RUNS/NHLPTS 0.5; HITS/BB/GA/GOALS market lines run 0.5–3.5; **zero logged picks on any Poisson stat above line 8.5, ever**. Only REC (NFL receptions — elite slot receivers occasionally see 8.5–9.5) could plausibly trip the branch, and NFL isn't live. The code's own comment at line 375 already acknowledges SIGMA["REC"] was removed *because* POISSON_STATS takes priority — meaning REC at line 9.5 would hit the L11 fallback warning path with the wrong σ.

**4. Verdict weighing.** The branch is effectively dead code for every live stat/line combination, so nothing is currently mispriced — that rules out NEEDS_CHANGE on materiality grounds. But it is a loaded trap: the moment NFL REC props go live (or any new high-count Poisson stat is added), lines > 8.5 silently route to a Normal with an uncalibrated fallback σ that can be wrong by 5–8pp, surfaced only as a log warning. CONFIRMED_WITH_CAVEAT, with a recommended (non-urgent) hardening: change the condition at line 891 to `if stat in POISSON_STATS:` (drop the cutoff and the SOG special-case entirely — Poisson is exact and the CDF implementation is stable far beyond any realistic line), or at minimum key the cutoff on `proj` and route over-cutoff Poisson stats to Normal(μ=proj, σ=√proj) instead of the SIGMA fallback. Zero behavioral change today; removes the NFL-launch foot-gun.

### Sources
- Poisson distribution — Wikipedia (https://en.wikipedia.org/wiki/Poisson_distribution) — "If λ is greater than about 10, then the normal distribution is a good approximation if an appropriate continuity correction is performed" (μ=λ, σ²=λ).
- John D. Cook, "Poisson normal approximation error" (https://www.johndcook.com/blog/normal_approx_to_poisson/) — Berry–Esséen bound C/√λ, C < 0.7164; notes the bound is ~3× pessimistic in practice.
- John D. Cook, "Error in the normal approximation to the Poisson distribution" (https://www.johndcook.com/normal_approx_to_poisson.html) — max CDF error ≈0.083 without continuity correction, ≈0.021 with it, near λ=10.
- Sparkl / Cambridge A-Level Mathematics 9709, "Normal approximation to Poisson distribution" — standard curriculum statement of the λ > 10 + continuity-correction rule.
- Code verified: `engine/run_picks.py` lines 347–376 (SIGMA/POISSON_STATS/POISSON_CUTOFF), 759–772 (poisson_pmf/cdf), 891–950 (branch logic, L11 fallback at 935–937). Line-range evidence: `data/pick_log*.csv` (all logs scanned).

---

## SECTION 1F — NB Parameterization and CDF Correctness
**VERDICT:** CONFIRMED
**CLASSIFICATION:** LOCKED (formula) / PERIODIC_RECAL (r values)
**Condition to revisit:** Re-estimate per-stat r values at each offseason refit (or if a stat's within-player var/μ shifts >10%); the PMF/CDF code itself needs no revisiting unless lines >~30 or r<0.1 appear.

### Findings

**1. r estimator — correct MOM; adequate at these sample sizes.**

For the mean-parameterized NB(μ, r), Var(X) = μ + μ²/r. Solving for r:

  σ² − μ = μ²/r  ⟹  **r = μ²/(σ² − μ)** ✓

This is exactly the classical method-of-moments estimator (equivalently, the moment estimator of α = 1/r in Cameron & Trivedi's NB2 variance function Var = μ + αμ²). The implementation in `engine/calibrate_distributions.py` lines 61–65 (`_nb_r`) matches: `r = mu*mu/(var - mu)`, returning ∞ when var ≤ μ (correctly degenerating to Poisson). The pooled form r = Σ(nᵢμᵢ²)/Σ(nᵢ·max(varᵢ−μᵢ, 0.001)) is a sample-size-weighted ratio-of-sums estimator — a standard, consistent pooling.

MOM vs MLE: the moment estimator is **consistent but asymptotically less efficient** than MLE. Lawless (1987, Canadian J. Statistics 15:209–225) computed the relative efficiencies and found that when the overdispersion parameter α=1/r is **small** (mild overdispersion), both the moment and pseudolikelihood estimators are "relatively highly efficient," with efficiency loss growing as α increases (i.e., as r shrinks). Clark & Perry (1989) and the Anscombe (1950) large-sample variance for the moment estimator give the same qualitative picture: MOM is fine when r is moderate-to-large relative to μ; it degrades for small r combined with large μ. Rough quantification: for r ≥ ~5 (var/μ ≤ ~1.2 at these means — the NBA REB/AST/3PM, NHL SV cases), MOM efficiency relative to MLE is typically >90%; for r ≈ 1 with μ of order 1 (RBI r=0.87, ER r=2.62, μ≤1.5), efficiency can drop toward 70–80%, meaning the standard error of r̂ is ~10–20% wider than MLE would deliver — but with **13k–169k game-logs**, the absolute SE on r is tiny either way. Efficiency loss matters when n is in the hundreds, not the tens of thousands. MOM is an entirely adequate production choice here. One minor note: the `max(var−μ, 0.001)` floor converts underdispersed players' negative contributions into small positives, which slightly inflates the pooled denominator → slightly **lowers** r → slightly fattens tails. This is conservative and negligible given that the targeted stats are overdispersed in aggregate.

**2. PMF verification — exact match, valid for non-integer r.**

Target: P(k; μ, r) = Γ(k+r)/(Γ(r)·k!) · (r/(r+μ))ʳ · (μ/(r+μ))ᵏ.

The code (run_picks.py:795–802) computes p = r/(r+μ), then exp[lgamma(k+r) − lgamma(r) − lgamma(k+1) + r·log(p) + k·log(1−p)]. Since 1−p = μ/(r+μ), this is term-for-term identical to the target. For integer r, Γ(k+r)/(Γ(r)k!) = (k+r−1)!/((r−1)!k!) = C(k+r−1, k), so the gamma form **correctly generalizes the binomial coefficient to non-integer r** — this is the Pólya/gamma-Poisson-mixture distribution (Hilbe, *Negative Binomial Regression*, 2nd ed., §5.1; the gamma-function form is the standard NB2 density). All production r values (0.87, 1.5, 2.62, 3.548, 9.15, 11.37, 12.16, 13.41, 14.7, …) are non-integer, and the gamma form handles them exactly.

Hand computations (verified against scipy `nbinom` to 1e-15):
- **P(X=0; μ=2.0, r=1.5)**: p = 1.5/3.5 = 3/7 ≈ 0.428571. P(0) = p^r = (3/7)^1.5 = **0.280566**. Code: 0.2805658588748473 ✓ (scipy: 0.2805658588748473).
- **P(X=2; μ=2.0, r=1.5)**: coefficient Γ(3.5)/(Γ(1.5)·2!) = r(r+1)/2 = 1.5·2.5/2 = 1.875. P(2) = 1.875 · (3/7)^1.5 · (4/7)² = 1.875 · 0.280566 · 0.326531 = **0.171775**. Code: 0.17177501563766162 ✓ (scipy: 0.17177501563766173 — agreement to 1e-16).

Also verified the moments numerically: summing k·P(k) and k²·P(k) for μ=0.6, r=0.87 recovers mean = 0.600000 and var = 1.013793 = μ + μ²/r exactly. The parameterization is internally consistent.

**3. Numerical accuracy of the iterative CDF — 6+ decimals easily achieved; no genuine risk.**

Hand computation of **negbinom_cdf(1, μ=0.6, r=0.87)**:
- p = 0.87/1.47 = 0.5918367347
- P(0) = p^0.87 = exp(0.87 · ln 0.591837) = exp(−0.456348) = **0.633601**
- P(1) = r·p^r·(1−p) = 0.87 · 0.633601 · 0.408163 = **0.224993**
- CDF(1) = 0.633601 + 0.224993 = **0.858594**

Code output: 0.858593641485597; scipy `nbinom.cdf(1, 0.87, 0.591837)` = 0.8585936414855971. Agreement to 16 significant digits — far beyond the 6-decimal requirement.

Risk assessment:
- **(a) lgamma accuracy for small arguments**: C's `lgamma` (which `math.lgamma` wraps) is accurate to a few ulps over its whole domain, including arguments in (0,1) such as r=0.87. lgamma(0.87) ≈ 0.0899 — no pole proximity (poles are at 0, −1, −2, …), no issue. The smallest production r is 0.87, comfortably away from 0.
- **(b) catastrophic cancellation**: none. The log-PMF sums five terms of moderate magnitude, and the CDF is a sum of strictly positive terms — cancellation is structurally impossible. Per-term relative error ~1–2 ulp (≈2e-16); a sum of ≤10 such terms carries total relative error <1e-14.
- **(c) min(total, 1.0) clamp**: tested the worst plausible drift case — summing the PMF to k=2000 at μ=5, r=0.87 gives total = 0.9999999999999996, i.e., undershoot of 4.4e-16 (4 ulps), never overshoot of any consequence. The clamp is a harmless belt-and-suspenders guard, not a mask for drift.
- **Performance**: lines ≤9.5 → ≤10 PMF evaluations × 3 lgamma calls each ≈ 30 lgamma calls per CDF, sub-microsecond territory. Even `mlb_ml_from_nb()`'s 31-term double loop (~960 PMF calls without memoization) is trivially cheap at the per-game call frequency. Both precision and performance are fine. (Optional micro-optimization, not needed: the PMF satisfies the recurrence P(k+1) = P(k)·(k+r)/(k+1)·(1−p), which would reduce the CDF to one lgamma evaluation — but there is no accuracy or speed motivation to change working code.)

**4. Pooled r — reasonable production simplification; directional error is line-position-dependent and modest.**

A single r per stat assumes dispersion homogeneity across players. The literature on heterogeneous NB dispersion (hierarchical/empirical-Bayes approaches — directly analogous to the genomics dispersion-shrinkage literature, e.g., Robinson & Smyth 2008 and the moderated/trended-dispersion methods in edgeR, which exist precisely because entity-wise MOM dispersion estimates from ~10–80 observations are too noisy to use raw) supports the pooled choice as the **right default**: per-player r̂ from 20–80 games has enormous sampling variance (the MM estimator of r is notoriously unstable in small samples, frequently negative or infinite when sample var ≤ mean — see Saha & Paul 2005, *Biometrics*, on small-sample bias of dispersion estimators), so unshrunken per-player r would inject more noise than the heterogeneity it removes. A future refinement would be empirical-Bayes shrinkage of per-player r toward the pooled value, not raw per-player r.

Directional error, quantified with the production code (μ=7.0 REB, line 9.5, pooled r=14.7): a player whose true r=8 (more volatile than pool) has true P(over)=0.2230 but the model says 0.2051 — **understates P(over) by ~1.8pp** for above-mean overs (model finds fewer edges on volatile players' overs and overstates their unders → conservative on overs, slightly aggressive on unders). A consistent player with true r=25: true P(over)=0.1930 vs model 0.2051 — **overstates by ~1.2pp** (mild over-bet risk on consistent players' high-line overs). For RBI (μ=0.6, line 0.5, r=0.87): true r=0.5 → 0.3258 vs model 0.3664 (+4.1pp overstated); true r=1.5 → 0.3963 vs model 0.3664 (−3.0pp understated) — heterogeneity matters more at low r, consistent with finding 1. General rule: for lines **above** the projection, pooled r overstates win prob for low-dispersion players and understates it for high-dispersion players; the sign flips for lines below the projection. At typical edge thresholds (3.5–6pp) a 1–2pp dispersion error on NBA stats is absorbed; the RBI-class stats (r<1.5) are where per-player heterogeneity could plausibly flip marginal picks and would be the first candidates for shrinkage if RBI ever graduates from shadow.

**Bottom line:** PMF formula exact (verified symbolically and against scipy to machine precision), CDF numerically sound to far better than 6 decimals, r = μ²/(σ²−μ) is the textbook-correct MOM estimator and adequate at n=13k–169k, and pooled r is a defensible production simplification with quantified, modest, sign-known errors.

### Sources
- Lawless, J.F. (1987). "Negative binomial and mixed Poisson regression." *Canadian Journal of Statistics* 15(3):209–225. https://onlinelibrary.wiley.com/doi/abs/10.2307/3314912 (PDF: https://www.math.mcgill.ca/~dstephens/523/Papers/Lawless-1987-CJS.pdf)
- Saha, K. & Paul, S. (2005). "Bias-corrected maximum likelihood estimator of the negative binomial dispersion parameter." *Biometrics* 61(1):179–185. https://onlinelibrary.wiley.com/doi/abs/10.1111/j.0006-341X.2005.030833.x
- Shilane et al., "Estimating the Negative Binomial Dispersion Parameter" (review citing Anscombe 1950 large-sample variance of the MME). https://scialert.net/fulltext/?doi=ajms.2010.1.15
- Savani & Zhigljavsky, "Efficient Estimation of Parameters of the Negative Binomial Distribution." https://ssa.cf.ac.uk/zhigljavsky/pdfs/stats/EfficientEstimationParametersNBD.pdf
- Hilbe, J.M. *Negative Binomial Regression*, 2nd ed., Cambridge University Press (2011) — standard NB2 gamma-function PMF parameterization.
- Local verification: `engine/run_picks.py` lines 781–812; `engine/calibrate_distributions.py` lines 61–65; all hand computations cross-checked against `scipy.stats.nbinom`.

---

## SECTION 2 — Combo Props (Correlated Normal Sum)
**VERDICT:** CONFIRMED_WITH_CAVEAT
**CLASSIFICATION:** PERIODIC_RECAL
**Condition to revisit:** Revisit when the combo Platt gate fires (100 scored combo picks) or before re-enabling RA — and at that point replace the combo-path marginal σs with NB-consistent values (σ = √(μ+μ²/r)) plus a skew correction, since the current Normal mults are inconsistent with the engine's own NB marginals by +6–23% depending on μ.

### Findings

**1. Is the correlated Normal sum the published approach? Does CLT reasoning hold for 2–3 components? What does the skewness imply?**

Partially. The published standard for joint player-prop modeling is a **Gaussian copula over the correct marginals** — Normal where appropriate, NB/Poisson for counts — solved by simulation or numerical integration (Wizard of Odds — "Same-Game Parlays: The Mathematics of Correlation"; *Annals of Operations Research* — multivariate copula-based Bayesian network for basketball performance, which explicitly uses a Gaussian copula "for non-Gaussian data"). The correlated Normal sum is the degenerate case of that copula where every marginal is forced Normal. Industry write-ups (OpticOdds — "Probability Paths") warn that parametric shortcuts are "subtly inaccurate at the tails" and recommend simulation for precision work — but also endorse parametric models for main-line scans, which is what this path does (combo lines sit near the median, not the tails).

CLT reasoning does **not** apply to summing 2–3 variables — n=3 is not asymptotic. The correct justification is different: each component is itself an aggregate over ~70–100 possessions, so PTS is already near-Normal, and NB(μ=6–8, r=12–15) has modest conditional skew (NB skewness = (1+2μ/r)/√(μ(1+μ/r)): AST μ=6 → 0.66; REB μ=8 → 0.59). Summing positively correlated right-skewed components dilutes *relative* skew. Berry–Esseen-type results make the approximation error explicitly a function of skewness.

**Important calibration artifact verified directly:** the code-comment skews (PRA 0.74 … RA 0.94) are **pooled population skews** — they include cross-player mean dispersion, which is irrelevant to pricing a single player's line. Recomputing from the same DB (76,960 rows, 595 players, min≥5, n≥20) with per-player centering, the **decision-relevant within-player skews are: PRA 0.43, PR 0.50, PA 0.51, RA 0.60** (pooled: 0.80/0.81/0.93/1.02 — matching the code comment's basis). So the Normal approximation is meaningfully better than the documented numbers suggest.

Direction and magnitude of error (one-term Edgeworth: P_true(over) − P_Normal(over) = (γ/6)(z²−1)φ(z)): for |z|<1 — the regime of every main combo line — a right-skewed truth means the **Normal over-prices OVERS and under-prices UNDERS**. At z=0 the error is γφ(0)/6 ≈ 0.0665γ: **RA ≈ 4.0pp, PA ≈ 3.4pp, PR ≈ 3.3pp, PRA ≈ 2.9pp**; it decays to ~0 at |z|=1 and flips sign in the far tails (Normal under-prices deep over tails — relevant only to alt lines, which this path doesn't price). Equivalent framing: median ≈ μ − γσ/6, so a book line at the true median sits ~0.5 RA-units below the model's mean, manufacturing a phantom ~4pp over edge. This mean-vs-median trap is well documented in prop betting (Unabated — "Profitable Prop Betting": "if you followed mean projections you would end up on more Overs"; Analytics.bet — "Chopped and Skewed").

**2. Variance identity and the marginal-σ mismatch.**

Confirmed: Var(X+Y) = Var(X) + Var(Y) + 2ρσ_Xσ_Y is a pure second-moment identity — it follows from bilinearity of covariance and holds for **any** joint distribution with finite second moments; no Normality is required. The implementation at `engine/run_picks.py:989-1011` applies it correctly, including the pairwise loop for PRA.

The mismatch math (confirmed):
- **AST μ=6, r=12.16:** NB var = 6 + 36/12.16 = 8.96 → σ = 2.99. Combo path: max(0.53×6, 2.0) = 3.18. **+6.2% σ inflation.**
- **REB μ=8, r=14.7:** NB var = 8 + 64/14.7 = 12.35 → σ = 3.51. Combo path: 0.48×8 = 3.84. **+9.2%.**
- The mismatch **grows with μ** because the mult model assumes σ ∝ μ while NB grows ~√μ: AST μ=9 → NB 3.96 vs 4.77 (**+20%**); REB μ=12 → NB 4.67 vs 5.76 (**+23%**). At low μ the floors are roughly NB-consistent (AST μ=3: NB 1.93 vs floor 2.0).
- Knock-on effect: because ρ is empirical but is multiplied by the *inflated* σs, the implied covariance overstates the measured covariance by the product of the inflations (~×1.16 for an RA pair at μ=6/8). Net for RA (μ_A=6, μ_R=8): engine σ_combo = √(3.18²+3.84²+2·0.251·3.18·3.84) = 5.57 vs NB-consistent 5.16 — **combo σ overstated ~8%**.

Direction of effect: inflated σ pulls every probability toward 0.5, **understating** claimed edge and win_prob on both sides — conservative for pick selection and mildly mispricing taken picks toward 0.5 (~0.5–1pp at typical z≈0.2). This is the *opposite* sign of the skew error for overs (partial accidental offset) and the *same* sign for unders (compounding under-pricing of unders). It cannot explain combos losing more than modeled; if anything it suppresses combo volume. Normal-to-NB approximation adequacy at these μ/r values is marginal-but-acceptable per standard guidance (Vose Software — Approximations to the NegBin).

**3. Pearson vs Spearman.**

Confirmed: **Pearson is the only correct choice for the variance formula**, because Cov(X,Y) = ρ_Pearson·σ_X·σ_Y is the definition — the quantity entering Var(X+Y) is the covariance, a second-moment object. Spearman/Kendall rank correlations are invariant to monotone transforms and depend only on the copula; they are the right input **when parameterizing a copula's dependence structure** for full joint simulation, where Pearson can be distorted by non-elliptical marginals (Embrechts, McNeil & Straumann — "Correlation and Dependence in Risk Management: Properties and Pitfalls"). The engine uses Pearson ρ inside a variance identity — correct pairing. (If the path is ever upgraded to a Gaussian copula with NB marginals, the ρ should be re-estimated as rank correlation converted via the copula, not reused as-is — Embrechts' Fallacy 2 territory.)

**4. Are the ρ values plausible?**

No published within-player game-to-game PTS/REB/AST correlation table exists in the public domain — DFS correlation research (SHRStats, FantasyLabs, Stokastic) is almost entirely **teammate-level**, not within-player. So external numeric corroboration is unavailable; two substitute checks were run:

- **Exact reproduction:** re-running the calibration read-only on `data/projections.db` (76,960 rows, 595 players, min≥5, n≥20, n-weighted within-player Pearson) gives **PTS-REB 0.333, PTS-AST 0.233, REB-AST 0.251** — identical to COMBO_RHO to 3 decimals. The numbers are real, not stale.
- **Structural plausibility:** within-player correlation is driven mainly by shared minutes/pace variance. With within-player CV(min) ≈ 0.18, CV(PTS)=0.35, CV(REB)=0.48, the shared-minutes-induced floor is ≈ CV(min)²/(CV_PTS·CV_REB) ≈ 0.19; pace/blowout/usage variance plausibly adds the rest to 0.33. The ordering (PTS-REB > REB-AST > PTS-AST) matches the known mechanics — points and rebounds can co-occur on the same possession while a scorer's assists trade off against his own shooting. Values in the 0.2–0.35 range are consistent with the qualitative "moderate positive" consensus across SGP-pricing literature (Wizard of Odds uses 0.28–0.42 for analogous NFL within-game pairs).
- **WNBA −0.04 to −0.05:** internally credible — with SE≈0.009 the gap is ~5 SE, so it is a real feature of the 13,322-game sample, and the proposed mechanism (tighter rotations → lower shared-minutes variance) is directionally sound. No published WNBA within-player figures exist to corroborate externally; treat as INSUFFICIENT external validation but sound internal calibration.

**5. Does skewness predict the RA failure direction? — No, and this is the most important finding.**

The skew story predicts the model manufactures **phantom OVER edges** (~4pp at the line for RA) and is *conservative on unders* (true under prob exceeds modeled). The actual RA rows from `data/pick_log.csv`: the 0W/7L record is **5 unders + 2 overs** (Jenkins u5.5, Bridges u5.5, Brunson u9.5, Wallace u5.5, Caruso u5.5; Merrill o3.5, Fox o9.5; plus 1 void). Five of seven losses are on the side where both the skew error AND the σ-inflation error make the model *under-confident* — those unders should have outperformed their stated ~55–58% win probs, and instead went 0-5. **The Normal-sum distributional critique cannot explain this record.** The arithmetic: P(0-7) at the logged win probs ≈ 0.28%; even at true p=0.50 it's 0.78% — so the result is a mix of genuine model error and a tail draw, but the error is in the **mean, not the shape**: every loss occurred May 15–Jun 3 (playoffs), all but Brunson on low-μ role players, where the projection stack (playoff AST deflator 0.845, role-tier minute scalars) drives μ_proj down and mechanically generates under picks; the players then cleared the line. The RA gate (G_RA_DISABLED) is justified, but the documented rationale should be corrected: the suspect is **component μ bias on playoff role players**, not the Normal sum. A secondary contributor consistent with CLAUDE.md's note that combo win_probs run ~5pp hot: no Platt is applied on the combo path, and the skew error does add ~+3–4pp to *over* win_probs (Fox o9.5, Merrill o3.5 fit this). When RA is revisited, fix order should be: (a) validate component μ on the RA pick population, (b) NB-consistent σs, (c) skew/Cornish-Fisher correction or moment-matched NB on the sum — not ρ, which is solid.

### Sources
- Statistics LibreTexts — Variance Sum Law II: Correlated Variables. https://stats.libretexts.org/Bookshelves/Introductory_Statistics/Introductory_Statistics_(Lane)/04%3A_Describing_Bivariate_Data/4.07%3A_Variance_Sum_Law_II_-_Correlated_Variables
- probabilitycourse.com — Covariance, Correlation, Variance of a Sum (§5.3.1). https://www.probabilitycourse.com/chapter5/5_3_1_covariance_correlation.php
- Embrechts, McNeil & Straumann — "Correlation and Dependence in Risk Management: Properties and Pitfalls" (ETH Zürich). https://people.math.ethz.ch/~embrecht/ftp/pitfalls.pdf
- Haugh — Quantitative Risk Management: Copulas (Columbia IEOR E4602). http://www.columbia.edu/~mh2078/QRM/Copulas.pdf
- Wizard of Odds — "Same-Game Parlays: The Mathematics of Correlation." https://wizardofodds.com/article/same-game-parlays-the-mathematics-of-correlation/
- *Annals of Operations Research* — "A Bayesian network to analyse basketball players' performances: a multivariate copula-based approach." https://link.springer.com/article/10.1007/s10479-022-04871-5
- OpticOdds — "Probability Paths: Monte Carlo vs. Parametric Distributions in Player Prop Modeling." https://opticodds.com/blog/probability-paths-in-player-prop-modeling
- Unabated — "Profitable Prop Betting in 3 Easy Steps" (mean vs median, right-skew). https://unabated.com/articles/profitable-prop-betting-in-3-easy-steps
- Analytics.bet — "Chopped and Skewed: The Mathematics of Points Betting." https://analytics.bet/articles/chopped-and-skewed-the-mathematics-of-points-betting/
- arXiv 2111.12267 — "The Practical Scope of the Central Limit Theorem"; arXiv 1904.02623 — skewness correction in tail probability approximations for sums
- Vose Software — Approximations to the Negative Binomial distribution. https://www.vosesoftware.com/riskwiki/ApproximationstotheNegativeBinomialdistribution.php
- SHRStats — Teammate Correlation Overview; FantasyLabs — NBA Player Correlations; Stokastic — NBA Correlation Guide (teammate-level only — basis for the no-external-corroboration note)
- Local verification (read-only): `data/projections.db` (76,960 player-games — ρ reproduction + within-player skew recomputation), `engine/run_picks.py:989-1018`, `data/pick_log.csv` (RA/combo pick rows)

---

## SECTION 3 — Platt Scaling
**VERDICT:** CONFIRMED_WITH_CAVEAT
**CLASSIFICATION:** DATA_GATED
**Condition to revisit:** Migrate to logit-space at H3 as planned, but with a slope-regularized (or intercept-only) fit at n=100 and a free 2-parameter refit deferred to n≥300 — and note that `calibrate_platt.py`, the script the migration plan depends on, does not exist in the repo (verified by glob during this audit — only calibrate_winprob.py / calibrate_sigma.py / calibrate_distributions.py exist).

### Findings

**1. Raw-space Platt on a probability input is a known degeneracy — the planned logit migration is the textbook fix.**

Platt (1999) defined calibration as σ(A·f(x)+B) where f(x) is an **unbounded classifier score** (the SVM decision margin, range ℝ). The sigmoid's full output range (0,1) is only reachable because the input is unbounded. Feed it a bounded input p ∈ [0,1] and the output is confined to [σ(B), σ(A+B)] — here **[σ(−0.8102), σ(0.6886)] = [0.3078, 0.6657]**. No raw model confidence, however extreme, can produce a calibrated probability above 66.57% or below 30.78%. This is not a documented "named pathology" in the literature for a simple reason: the literature never applies the sigmoid to probability-scale inputs. The standard practice (Niculescu-Mizil & Caruana 2005, scikit-learn's `CalibratedClassifierCV`, and every modern treatment) is to calibrate on the **log-odds**: σ(A·logit(p)+B). Kull, Silva Filho & Flach (2017) make the theoretical case explicit: logistic calibration is the correct map only when the input score is (approximately) Gaussian per class — which log-odds are, and raw probabilities are not — and they prove that the logistic family applied to probability-scale scores **does not contain the identity map**, so it "can easily uncalibrate a perfectly calibrated classifier." Logit-space Platt (A=1, B=0 → identity) fixes that, preserves the full (0,1) output range, and is exactly the symmetric special case (a=b) of Kull's 3-parameter beta calibration, which was purpose-built for inputs already in [0,1]. **The research unambiguously confirms the H3 logit migration already documented at run_picks.py:479-485 and :861-863.**

**2. Concrete distortion under σ(1.4988·p − 0.8102):**

| raw over_p | calibrated | Δ per 10pp raw |
|---|---|---|
| 0.55 | 0.5035 | — |
| 0.65 | 0.5409 | +3.74pp |
| 0.75 | 0.5778 | +3.69pp |
| 0.85 | 0.6139 | +3.61pp |

The local derivative A·σ'(·) ≈ 0.355–0.375 across the whole operating range — i.e., the map is effectively the **affine shrinkage cal ≈ 0.37·p + 0.32**. Raw 0.75 vs 0.85 (a 10pp confidence difference) collapses to a 3.6pp difference. Ranking survives (monotone), but Kelly sizing uses the level: at −110, full-Kelly at raw 0.75 is 47.5% of bankroll vs **11.3%** at the calibrated 0.578, and the output cap bounds full-Kelly at ~29.8% regardless of edge. Given the documented overconfidence (mean 0.696 → actual 0.579; the 55–60% bucket printing ~34%), heavy shrinkage is **directionally defensible** — the Kelly literature (Chu, Wu & Swartz 2018, arXiv:1701.02814) confirms that probability overestimation is asymmetrically punished, so shrinking toward 0.5 is the conservative error. The raw-space map approximately matches a correct logit-space map *within the observed data range*; its failures are at the tails and in extrapolation. **However, two production side effects of the cap are concrete and current:** (a) **KILLSHOT's 4u tier (win_prob ≥ 0.70) is mathematically unreachable** for any Platt-calibrated prop — over picks cap at 0.6657 and under picks at 1−0.3078 = 0.6922; (b) the wp ≥ 0.65 KILLSHOT/G13B gates require raw over_p ≥ 0.9536 (overs) — verified against pick_log.csv: the only prop rows with win_prob ≥ 0.65 are MLB (Platt-exempt) or pre-Platt legacy rows. The logit migration removes both artifacts.

**3. Method choice at n≈100–300: parametric (2 params) is correct; isotonic is contraindicated.**

- **Isotonic regression** (Zadrozny & Elkan 2002): non-parametric, needs the most data. Niculescu-Mizil & Caruana (2005) is the canonical reference: isotonic matches or beats Platt only **"when there are 1000 or more points in the calibration set"**; below that it overfits and Platt dominates. At n=100–300, isotonic is wrong. (The engine's own Phase-2 note in calibrate_winprob.py suggesting isotonic at 300+ is **too aggressive** — 300 is well below the published crossover; defer isotonic to ~1000.)
- **Platt/logistic in logit space** (2 params): the right small-n default per NM&C 2005; works whenever the miscalibration is sigmoid-shaped, which a globally overconfident model is.
- **Beta calibration** (Kull et al. 2017, 2–3 params): marginally better than logistic for probability-scale inputs because it contains the identity and handles skewed score distributions; same data appetite as Platt. A reasonable upgrade, but logit-space Platt with the symmetric restriction is already the a=b beta sub-family — at n≈100–300 the third parameter buys little. **No change to the planned method needed.**
- **Temperature scaling** (Guo et al. 2017, 1 param): most data-efficient, but it has **no intercept** — it can only sharpen/flatten around 0.5, not shift the mean. This engine's primary defect is a level bias (0.696 → 0.579), so pure temperature scaling cannot fix it. If a 1-parameter fit is wanted at small n, the right one here is **intercept-only** (fix A=1 in logit space, fit B) — the "calibration-in-the-large" update from the clinical-prediction literature — not temperature.

**4. Per-stat calibration at 50–80 picks per stat: not justified.**

The generic events-per-parameter rule (10–20 EPV) would nominally permit a 2-parameter fit at 40–80 events, but EPV is a bare-stability criterion, not a precision one. The calibration-specific guidance is much stricter: Vergouwe et al. (2005) require **≥100 events AND ≥100 non-events** for external-validation/recalibration of a binary model (≈200 picks at a ~55% base rate), and Riley et al. (Stat Med 2021) show that the **calibration slope is the binding constraint** — their worked examples need SE(slope)≈0.05 for a ±0.1 CI, driving required samples into the hundreds of events even under favorable linear-predictor spread; subsequent simulation work (Snell et al.) found even 200 events/non-events "can give imprecise estimates, especially for calibration." The engine's situation is worse than the clinical baseline because the predictor spread is narrow (logged over_p_raw: SD = 0.125), which inflates slope variance. **Recommended gate: ≥200 graded picks per stat before any per-stat A/B**, and prefer a hierarchy — global slope shared across stats with per-stat intercepts (partial pooling) — over fully independent per-stat fits, which at 50–80 picks would mostly fit noise.

**5. The frozen n=76 fit: the slope is essentially unidentified; the gate at 100 buys almost nothing.**

Monte Carlo (1,500 reps per cell, truth = the deployed A/B, predictor matched to the 79 logged over_p_raw rows: N(0.448, 0.125) clipped, refit by the same Nelder-Mead NLL as calibrate_winprob.py):

| n | SE(A) (Â=1.50) | 90% CI for A | P(fitted slope < 0) |
|---|---|---|---|
| 76 | **2.01** | [−1.84, +4.84] | **22%** |
| 100 | 1.66 | [−1.03, +4.45] | 17% |
| 200 | 1.20 | [−0.38, +3.55] | 10% |
| 300 | 0.93 | [+0.04, +3.11] | 4.5% |
| 500 | 0.75 | [+0.32, +2.75] | 2.2% |

At n=76 the relative SE on A is ~134% and a refit has a 1-in-5 chance of returning a *negative* slope (which would invert pick ranking). The same simulation in logit space gives relSE(A)=1.36 at n=76 — **the data, not the parameterization, is the constraint**, so migrating spaces does not rescue the slope estimate. What n=76 *did* reliably estimate is the mean level (0.696 → 0.579 ≈ a ~30-pick-equivalent binomial estimate, SE ≈ 0.056) — the deployed map is, in effect, a well-estimated mean shift wearing an arbitrary slope. The 6.0% in-sample Brier improvement on the fitting data is consistent with that and should not be read as validated slope information. **The freeze itself is sound policy** (refitting at every n would whipsaw A). **The gate of 100 is too low for a free 2-parameter refit**: SE(A) improves only 2.01→1.66 and the negative-slope probability is still 17%. Recommended plan amendment at H3 (n=100): migrate the formula to logit space as planned, but fit with **A fixed at 1 (intercept-only) or A shrunk toward 1 via a ridge/MAP prior**, and unlock the free 2-parameter fit at **n≥300** (P(A<0) < 5%) with n≈500 preferred for betting-grade slope precision — consistent with both the simulation above and the Riley/Vergouwe calibration-sample-size literature. The OOS-Brier-must-improve deployment check already in the H3 plan is good practice and should be kept.

**Operational defect found during verification (beyond the migration plan):** `engine/calibrate_platt.py` — referenced by the migration note at run_picks.py:479-483 ("calibrate_platt.py now fits logit-space"), by CLAUDE.md ("use `python engine/calibrate_platt.py --native-only --force`"), and by the warning inside calibrate_winprob.py — **does not exist anywhere in the repository** (independently re-verified by the audit coordinator: only `calibrate_winprob.py`, `calibrate_sigma.py`, `calibrate_distributions.py` exist; calibrate_winprob.py fits *raw-space* sigmoid on the already-calibrated win_prob column with an explicit do-not-deploy warning). **Coordinator follow-up resolved the mystery:** the script was deleted from JonnyParlay in commit 5b8ee6d (2026-05-29, "refactor: extract projection engine to EdgeModel repo"), swept up with the projection files even though it calibrates pick_log win probabilities, not projections. It currently lives at `EdgeModel\engine\calibrate_platt.py`, where the documented H3 workflow cannot reach it. **Fix: move it back to `engine/calibrate_platt.py`** (it already fits logit-space per the 2026-05-25 upgrade); apply the slope-prior amendment from Finding 5 when the H3 gate fires.

### Sources
- Platt (1999), "Probabilistic Outputs for Support Vector Machines…" https://www.cs.colorado.edu/~mozer/Teaching/syllabi/6622/papers/Platt1999.pdf
- Niculescu-Mizil & Caruana (2005), "Predicting Good Probabilities with Supervised Learning," ICML — isotonic beats Platt only at n≥1000. https://www.cs.cornell.edu/~alexn/papers/calibration.icml05.crc.rev3.pdf
- Zadrozny & Elkan (2002), "Transforming Classifier Scores into Accurate Multiclass Probability Estimates," KDD.
- Kull, Silva Filho & Flach (2017), "Beta calibration: a well-founded and easily implemented improvement on logistic calibration for binary classifiers," AISTATS. https://proceedings.mlr.press/v54/kull17a.html ; https://betacal.github.io/
- Guo, Pleiss, Sun & Weinberger (2017), "On Calibration of Modern Neural Networks," ICML. https://proceedings.mlr.press/v70/guo17a.html
- Riley et al. (2021), "Minimum sample size for external validation of a clinical prediction model with a binary outcome," *Statistics in Medicine*. https://pubmed.ncbi.nlm.nih.gov/34031906/
- Snell et al. (2021), "External validation of clinical prediction models: simulation-based sample size calculations were more reliable than rules-of-thumb," *J Clin Epi* (Vergouwe et al. 2005 100/100 rule discussed). https://pmc.ncbi.nlm.nih.gov/articles/PMC8352630/
- Chu, Wu & Swartz (2018), "Kelly betting on horse races with uncertainty in probability estimates." https://arxiv.org/pdf/1701.02814
- Downey, "Why fractional Kelly? Simulations of bet size with uncertainty." https://matthewdowney.github.io/uncertainty-kelly-criterion-optimal-bet-size.html
- scikit-learn probability calibration guide. https://scikit-learn.org/stable/modules/calibration.html
- Abzu, "An introduction to calibration (part II): Platt scaling, isotonic regression, and beta calibration." https://www.abzu.ai/data-science/calibration-introduction-part-2/
- Repo evidence: `engine/run_picks.py:476-491, 857-871, 2553-2560`; `engine/calibrate_winprob.py:1-78`; `data/pick_log.csv` (79 over_p_raw rows, mean 0.448, SD 0.125); glob confirms `calibrate_platt.py` absent.

---

## SECTION 4 — Kelly Criterion and Sizing

**VERDICT:** CONFIRMED_WITH_CAVEAT
**CLASSIFICATION:** per-component — `kelly_units` formula: LOCKED (math correct) · `KELLY_FRACTION=6.0`: PERIODIC_RECAL (and rename) · `KELLY_MARKET_MULT`/`VAKE_MULT` stack: NEEDS_CHANGE (consolidate triple-counted stat shrinkage) · floor/cap: LOCKED as product decision · `COLD_START_SCORE_PENALTY`/`INJURY_TRIGGER_BONUS`: DATA_GATED
**Condition to revisit:** Revisit when bankroll convention changes from ~100u, when any `KELLY_MARKET_MULT` entry drops below ~0.30 (the 0.50u floor silently neutralizes it), or when per-market n reaches ~50 graded picks enabling empirical-Bayes replacement of the multiplier stack.

### Findings

**1. Formula verification and the TRUE effective Kelly fraction — `KELLY_FRACTION=6.0` is a mislabel.**

The binary Kelly math in `kelly_units` (run_picks.py:1061–1082) is correct. For American odds −133: b = 100/133 = 0.7519; at p = 0.70: f* = (0.7519×0.70 − 0.30)/0.7519 = 0.2263/0.7519 = **0.3010**. Returns 0.3010 × 6.0 = **1.81u**. All verified against the live code.

Under the 100u-bankroll convention, stake fraction = f*×6/100 = **0.06·f***. That is a **0.06 full-Kelly multiplier ≈ 1/16.7 Kelly**, not 1/6 Kelly. Algebraically, `units = f* × F` equals fraction `f*·F/B` of bankroll B; F=6 would be 1/6 Kelly only if B = 36u. The constant is a *units converter* ("percent of full Kelly expressed in units"), and the calibration note ("median implied-F ≈ 5.9 on 207 picks") confirms it was fit to reproduce the legacy VAKE sizing distribution — a deliberate continuity choice, not a literature-style Kelly fraction. **The docstring "fractional Kelly... scaled by KELLY_FRACTION" is a mislabel and should read something like `KELLY_PCT_OF_FULL = 0.06` or document the bankroll convention explicitly.**

After the stack, effective fractions for representative picks:

| Pick | f* | base (u) | mults | final (u) | eff. fraction of full Kelly |
|---|---|---|---|---|---|
| −133, p=0.70, T1 default market | 0.301 | 1.81 | ×0.75 → 1.35, **cap 1.25** | 1.25 | 1.25/30.1 = **1/24** |
| −110, p=0.60, T1 default | 0.160 | 0.96 | ×0.75 = 0.72 → 0.75 | 0.75 | 0.75/16.0 = **1/21** |
| −110, p=0.60, T2 NBA PTS over | 0.160 | 0.96 | ×0.50×0.85×0.90 = 0.368, **floor 0.50** | 0.50 | 0.50/16.0 = **1/32** |
| −110, p=0.545 (edge ~3%), T1 | 0.045 | 0.27 | ×0.75 = 0.20, **floor 0.50** | 0.50 | 0.50/4.5 = **1/9** |

So the system runs at roughly **1/20–1/35 Kelly for its strongest picks and ~1/9–1/15 Kelly for its weakest** — the floor/cap pair compresses a ~20:1 range of Kelly stakes into a 2.5:1 range of posted units (0.50–1.25u), partially *inverting* the Kelly ordering of effective fractions. This is functionally near-flat staking with a mild Kelly tilt, not fractional Kelly in the Thorp/MacLean–Ziemba sense.

**2. Literature on fractional Kelly and Baker–McHale shrinkage.**

Thorp (2006, "The Kelly Criterion in Blackjack, Sports Betting, and the Stock Market") endorses fractional Kelly primarily because bettors systematically *overestimate* edge and overbetting is asymmetrically worse than underbetting; half-Kelly cuts growth ≤25% while sharply cutting drawdown risk. MacLean, Thorp & Ziemba (2010) and MacLean, Ziemba & Blazenko (1992, *Management Science* 38(11)) frame fractional Kelly as a growth–security tradeoff, with the professional range at **1/4 to 1/2 Kelly for well-calibrated probabilities**.

Baker & McHale (2013, *Decision Analysis* 10(3):189–199) give the back-of-envelope shrinkage coefficient: **k ≈ c²/(c² + σ_c²)** where c is the estimated edge and σ_c its standard error; bet k·f*. Computing the representative case (claimed edge 7%):

- σ_edge = 5pp: k = 0.0049/(0.0049+0.0025) = **0.66** (~2/3 Kelly)
- σ_edge = 7pp: k = 0.0049/(0.0049+0.0049) = **0.50** (half Kelly)
- σ_edge = 15pp (Platt bucket errors of 10–20pp at small n): k = 0.0049/(0.0049+0.0225) = **0.18** (~1/5.6 Kelly)
- σ_edge = 20pp: k = **0.11** (~1/9 Kelly)

To justify 1/16.7 Kelly from Baker–McHale alone you'd need σ_edge ≈ 28pp — i.e., a nearly uninformative model. So **1/15–1/25 is not directly supported by the shrinkage formula even under the worst calibration buckets**, but it becomes defensible when stacking the other legitimate haircuts the literature recognizes: (a) simultaneous correlated bets — Whitrow (2007, JRSS-C 56(5):607–623) shows optimal simultaneous stakes shrink below isolated Kelly stakes (the engine posts 3–10 correlated picks/day plus parlays against the same 12u cap); (b) Thorp's overbet-asymmetry given known residual miscalibration; (c) subscriber-business drawdown constraints (a 30%+ drawdown is brand-fatal even if growth-optimal). Verdict: **ultra-conservative but coherent; it sacrifices growth, not safety.** The cost is foregone EV, which is a legitimate business choice — just don't call it 1/6 Kelly.

**3. Multiplier stack — yes, this is triple-counting the same covariate.**

Verified in code: `get_tier()` (line 1098) is a **deterministic function of (stat, direction, sport)** — exactly the key `KELLY_MARKET_MULT` uses. Therefore market_m, var_m, and tier_m are three multipliers conditioned on the *same information*, applied as if independent. T2 NBA PTS over: 0.50 × 0.85 × 0.90 = **0.3825×** — if the 0.50 market multiplier was fit on empirical PTS-over performance, that performance *already includes* its T2-ness; multiplying by tier shrinkage again over-shrinks. Multiplicative stacking of correlated corrections is the classic over-shrinkage anti-pattern: it assumes independence of log-adjustments. Additionally, `var_m` and `tier_m` are two dicts keyed on the identical tier variable (run_picks.py:614–617) — they are literally one multiplier written as two (T2: 0.765, T3: 0.39 net), which obscures the effective magnitude.

The principled alternative is a **single empirical-Bayes / hierarchical shrinkage per market**: estimate each (sport, stat, direction) market's performance multiplier, partially pooled toward the sport-level (or tier-level) mean with shrinkage proportional to 1/n — the James–Stein/Efron–Morris framework (Efron & Morris 1975, *JASA* 70(350):311–319). One multiplier per pick, with small-n markets automatically pulled toward the prior instead of hand-set 0.10s. The `corr_m` (same-game) and `exp_m` (repeat-stat) multipliers are conceptually distinct and fine — they address portfolio correlation, the problem Whitrow (2007) formalizes — though the ordering-dependence (pick_score order determines who eats the 0.85) is crude but harmless.

**Interaction bug worth flagging:** the 0.50u floor neutralizes small market multipliers. NBA 3PM over (0.10×): a typical base of 0.9–1.8u × 0.10 ≈ 0.09–0.18u → floored to 0.50u. The de facto minimum product is ~0.50/base ≈ 0.28–0.55, so **any KELLY_MARKET_MULT below ~0.3 is cosmetic for Premium-card sizing** — the floor silently restores 3–5× the intended stake. If 0.10 reflects genuine distrust of the market, the correct mechanism is exclusion (gate), not a multiplier the floor will override.

**4. The 0.50u floor — anti-Kelly in principle, defensible in this regime.**

A floor that bumps a 0.10u Kelly stake to 0.50u (5×) violates Kelly *allocation* — but check whether it violates Kelly *growth*: expected log growth g(f) = p·ln(1+bf) + q·ln(1−f) stays positive for f up to ≈ 2f*. The floor binds at 0.5% of bankroll; for the floor to exceed full Kelly f* itself you'd need f* < 0.005, i.e., edge < ~0.45% at −110 — but the tier gates require edge ≥ 3–6% pre-pick, implying f* ≥ ~3.3%, seven times the floored stake. **So floored bets remain far below full Kelly and retain positive expected log growth whenever the claimed edge is even fractionally real.** The honest tension: the floor doesn't threaten ruin, it *flattens relative sizing* — weak picks get overweighted relative to strong picks (1/9 vs 1/24 effective Kelly per Q1 table), which costs growth rate relative to proportional staking. For a subscription product where 0.10u recommendations are illegible and near-flat sizing is easier for subscribers to follow and audit, this is a rational legibility-for-growth trade — but it should be acknowledged as such: the sizing system's growth-optimality claim is weak; its real function is risk-bounded legible staking. Thorp (2006) himself notes practical constraints routinely dominate exact Kelly in deployment.

**5. Score-space vs sizing-space for reliability — wrong mechanism, partially mitigated.**

Kelly theory under estimation uncertainty (Baker & McHale 2013; Chu et al., arXiv:1701.02814) is unambiguous: **higher parameter uncertainty → shrink the stake**, via k = c²/(c²+σ_c²). `COLD_START_SCORE_PENALTY` instead operates in ranking space: a taxi/returner pick that *survives* the −15/−10 penalty and makes the card receives **full sizing** despite carrying the highest projection variance in the system (cold_start σ floors exist in the projector, but nothing in `size_picks_vake` sees reliability). Selection-space penalties are a discontinuous approximation of shrinkage — stake → 0 for displaced picks, stake → unadjusted for survivors — with a cliff exactly where smooth shrinkage is needed. The principled fix is a reliability multiplier in the sizing stack (e.g., cold_start sub-type → 0.5–0.7× stake, derived from the Baker–McHale k using the sub-type's empirical projection-error variance). That said, the practical damage is bounded because the whole system runs at 1/15–1/30 Kelly: even an un-shrunk uncertain pick is staked far below any plausible Baker–McHale optimum. `INJURY_TRIGGER_BONUS` in score-space is more defensible — it encodes *line staleness* (an edge-location signal, properly a selection concern), not projection reliability — but it simultaneously promotes picks with elevated projection uncertainty without a compensating stake adjustment, same asymmetry.

**6. INJURY_TRIGGER ordering (AST > PTS = SOG > REB): INSUFFICIENT_DATA.**

Searches found no peer-reviewed evidence that books reprice assist props slower than points props after injury news. Industry write-ups consistently make the *general* claim that the injured player's own line is pulled fast while teammates' derivative repricing lags, and playmaking redistribution is plausibly harder to price than scoring redistribution (assists concentrate on whoever assumes ball-handling duties; points redistribute more diffusely) — directionally consistent with AST on top. But the specific ordering AST(+10) > PTS(+8) = SOG(+8) > REB(+7) has no published support; the academic literature on betting-market reaction to news (e.g., NBA superstar-absence studies) addresses game lines, not props. **INSUFFICIENT_DATA for this sub-item.** The good news: this is testable in-house — `pick_log.csv` CLV by stat, filtered to injury-trigger picks, is exactly the experiment; the magnitudes are small (±3 score points) so the cost of being wrong is low.

### Sources
- Thorp, E.O. (2006). "The Kelly Criterion in Blackjack, Sports Betting, and the Stock Market." *Handbook of Asset and Liability Management*. https://gwern.net/doc/statistics/decision/2006-thorp.pdf
- MacLean, L.C., Thorp, E.O. & Ziemba, W.T. (2010). "Long-term capital growth: the good and bad properties of the Kelly and fractional Kelly capital growth criteria." *Quantitative Finance*. https://escholarship.org/uc/item/5mr5k8qj
- MacLean, L.C., Ziemba, W.T. & Blazenko, G. (1992). "Growth versus Security in Dynamic Investment Analysis." *Management Science* 38(11).
- Baker, R.D. & McHale, I.G. (2013). "Optimal Betting Under Parameter Uncertainty: Improving the Kelly Criterion." *Decision Analysis* 10(3):189–199. https://pubsonline.informs.org/doi/abs/10.1287/deca.2013.0271
- "Never Go Full Kelly" — restatement of Baker–McHale shrinkage k = edge²/(edge²+σ²). https://www.lesswrong.com/posts/TNWnK9g2EeRnQA8Dg/never-go-full-kelly
- Whitrow, C. (2007). "Algorithms for optimal allocation of bets on many simultaneous events." *JRSS Series C* 56(5):607–623. https://rss.onlinelibrary.wiley.com/doi/abs/10.1111/j.1467-9876.2007.00594.x
- Efron, B. & Morris, C. (1975). "Data Analysis Using Stein's Estimator and Its Generalizations." *JASA* 70(350):311–319.
- Chu, D. et al. "Kelly betting on horse races with uncertainty in probability estimates." https://arxiv.org/pdf/1701.02814
- Practitioner fractional-Kelly guidance: betstamp.com/education/kelly-criterion; managebankroll.com (industry, non-academic)
- Prop-market injury-lag claims: RG prop betting strategy guide (industry, anecdotal — basis for INSUFFICIENT_DATA call on Q6)

---

## SECTION 5 — Vig Removal and Edge Calculation
**VERDICT:** CONFIRMED_WITH_CAVEAT
**CLASSIFICATION:** LOCKED
**Condition to revisit:** Revisit the de-vig method only if the engine begins regularly evaluating markets outside roughly [-160, +140] (e.g., alt lines, ML dogs/favorites), where proportional normalization understates the favorite by >0.5pp vs Shin/power; and consider an EV-consistent edge gate if the pick odds distribution widens.

### Findings

**1. Vig-removal method comparison — proportional is theoretically dominated, but immaterially so in the engine's odds range.**

The implemented method (`no_vig()` at engine/run_picks.py:842 — normalize by booksum) is "basic normalization" in the literature. The published hierarchy:

- Štrumbelj (2014, *International Journal of Forecasting* 30(4):934-943) compared basic normalization, regression models, and Shin probabilities across multiple bookmakers/sports and found **Shin probabilities are more accurate forecasts than basic normalization for all bookmaker/sport pairs**, while noting basic normalization "might still be preferred in applications where forecasting accuracy is not crucial."
- Clarke, Kovalchik & Ingram (2017, *American Journal of Sports Science*, "Adjusting Bookmaker's Odds to Allow for Overround") found the **power method universally outperforms the multiplicative (proportional) method and outperforms or is comparable to Shin** across three large bookmaker datasets. Critically for this engine, they also prove **Shin and the additive (equal-margin) method are equivalent for two-competitor markets** — verified numerically below (Shin z-solution ≡ additive to 4 decimals at all four odds pairs).
- Buchdahl's margin-proportional-to-odds (MPTO/logarithmic) method and the power method both encode favorite-longshot bias; the proportional method assumes vig is distributed proportionally to implied probability, which is the one assumption known to be wrong in the FLB direction (more margin sits on the longshot).

**Quantified differences (fair prob of the favorite side, vs proportional, computed exactly):**

| Market | Booksum | Proportional | Additive/Shin | Power | Shin−Prop | Power−Prop |
|---|---|---|---|---|---|---|
| -110/-110 | 1.0476 | 0.5000 | 0.5000 | 0.5000 | **0.00pp** | **0.00pp** |
| -120/+100 | 1.0455 | 0.5217 | 0.5227 | 0.5232 | **+0.10pp** | **+0.15pp** |
| -150/+120 | 1.0545 | 0.5690 | 0.5727 | 0.5747 | **+0.38pp** | **+0.57pp** |
| -200/+160 | 1.0513 | 0.6341 | 0.6410 | 0.6446 | **+0.69pp** | **+1.05pp** |

At symmetric odds all methods are identical. Through about -130/+110 the methods differ by ≤0.2pp — far below the engine's model sigma noise and its 3.5–6pp edge floors. Proportional begins to materially understate the favorite (i.e., overstate your edge on favorites, understate it on dogs) only beyond roughly -150, reaching ~0.7–1.0pp at -200/+160. Since the prop universe is overwhelmingly -150 to +120 (and KILLSHOT caps at -200), **proportional is not materially biased here**. Two further mitigants: (a) for two-way markets the "best" theoretically motivated method (Shin) collapses to the trivial equal-margin split, so the sophistication gap is smaller than in racing/3-way markets where the literature was developed; (b) datagolf and others have argued much of the apparent two-way FLB is margin-placement convention rather than recoverable signal. Not worth changing.

**2. Edge definition — probability-space gate is internally consistent but not EV-consistent across odds; Kelly pairing is correct.**

The engine's structure is correct where it matters most: `calc_edge()` (run_picks.py:1021) gates on `p_model − p_fair`, and **Kelly stakes use p_model against the actual vigged odds offered** — the canonically correct pairing (Kelly f* = (pd−1)/(d−1) requires the price you actually get, not the fair price).

However, a fixed probability-space floor buys very different EV at different prices. EV per unit at p_model = p_fair + 5pp (p_fair from proportional de-vig of the stated market):

| Bet | p_fair | p_model | EV/unit |
|---|---|---|---|
| -150 (in -150/+120) | 0.5690 | 0.6190 | **+3.16%** |
| -110 (in -110/-110) | 0.5000 | 0.5500 | **+5.00%** |
| +110 (in -130/+110) | 0.4573 | 0.5073 | **+6.52%** |

(Extending to the KILLSHOT bound: -200 → +2.62%; +160 → +8.12%.) The relationship is EV ≈ edge_pp × decimal_odds − vig_cost, so a 5pp gate demands ~2x more EV from underdogs than from -150 favorites. The standard quant convention (Buchdahl; the entire value-betting literature) defines edge in **return space**: EV = p_model × decimal_odds − 1, which is price-invariant by construction. Theoretically the gate should be EV-based (or equivalently, relative edge p_model/p_fair − 1 scaled by odds). Practically, within -150/+110 the distortion is a ~3.2%–6.5% EV band — real but second-order, and it errs in the *conservative* direction for favorites only in the sense of admitting lower-EV favorite bets; if anything it slightly subsidizes favorites and taxes dogs. Worth noting as a known asymmetry; the Kelly sizing downstream partially self-corrects because stakes scale with true EV. (Floor *level* is covered in Section 15.)

**3. CLV benchmark — the 2026-05-31 reform matches published best practice; the "vigged entry side" is not actually an inconsistency.**

The industry-standard CLV measure (Buchdahl's Wisdom of the Crowd methodology, built on Pinnacle closing odds; echoed by Pyckio, BettingIsCool, and the broader quant canon) is: **EV = (your actual odds taken) / (vig-free closing odds) − 1**. E.g., Pinnacle closes 1.95, margin-removed fair close = 2.00, you took 2.10 → EV = 2.10/2.00 = +5%. Two components, two different treatments — and this is deliberate:

- **Close side: vig-free** — because the close is being used as the *truth estimate*, and you must strip the margin to recover the probability. ✅ The post-reform `calc_clv()` (capture_clv.py:909-929) does exactly this for props + totals.
- **Entry side: your actual vigged price** — because that is the *price you transacted at*; de-vigging your own ticket would credit you vig you never received. ✅ The engine keeps `implied_prob(your_odds)` raw, which is **the standard**, not a residual inconsistency. "Vig-free close vs vig-free entry" would measure pure line movement (also a valid diagnostic, but it is not CLV-as-skill-proxy); "vig-free close vs price taken" measures realized expected value, which is what Buchdahl/Pinnacle publish and what predicts long-run profit.

One genuine, minor deviation: the engine reports CLV as a **probability difference** (no_vig_close_prob − your_implied_prob) rather than the standard **odds ratio** (your_odds/fair_close − 1). The pp-difference is monotonically related and fine as a directional/aggregate skill indicator, but it is not directly interpretable as EV% and compresses at long odds. Also note the documented fallback: ML/spread and single-side responses still use fully vigged close — acceptable but should be remembered when comparing CLV across market types. Lastly, the CLV reform applies the proportional de-vig to the close; per Finding 1 this is fine at prop-typical odds.

**4. Asymmetric vig shading — proportional de-vig cannot recover informational shading, and no two-way method can.**

Levitt (2004, *Economic Journal* 114(495):223-246) established that bookmakers do not balance action but **deliberately shade prices away from market-clearing to exploit bettor biases**, taking positions and earning 20-30% more than balanced-book pricing; follow-ups (Paul & Weinbach's NBA/NFL tests of the Levitt model) confirm the pattern. Two distinct cases:

- **Bias shading (soft books, public sides):** the shade is *anti*-informational — the shaded side is the public-bait side. Proportional de-vig of a soft book's prop will pull fair price toward the shaded (wrong) side. This is why standard practice (sharp-bettor canon: devig the sharpest available book, typically Pinnacle, then compare to soft prices) never de-vigs the soft book in isolation.
- **Sharp-money shading (sharp books near close):** the shaded side carries information — this is precisely why the *closing* line is the benchmark (Buchdahl's wisdom-of-the-Pinnacle-crowd evidence; Pyckio's market-efficiency studies showing Pinnacle's vig-free close is nearly unbiased). Proportional de-vig assumes the margin splits proportionally across sides, so when a book concentrates margin on one side for informational reasons, proportional (and equally additive=Shin in two-way) misallocates it. Shin's model was designed for exactly this insider-information problem, but in two-outcome markets it degenerates to the equal-margin split and recovers nothing extra.

Bottom line: the misestimation risk is real but is a *source-selection* problem, not a *formula* problem — no de-vig formula extracts one-sided informational shade from a single book's two-way quote. The engine's existing line-shopping across 18 CO-legal books and its CLV-vs-close feedback loop are the correct structural mitigations.

### Sources
- Štrumbelj, E. (2014). "On determining probability forecasts from betting odds." *International Journal of Forecasting* 30(4):934-943. https://www.sciencedirect.com/science/article/abs/pii/S0169207014000533
- Clarke, S., Kovalchik, S. & Ingram, M. (2017). "Adjusting Bookmaker's Odds to Allow for Overround." *American Journal of Sports Science* 5(6). https://www.sciencepublishinggroup.com/article/10.11648/j.ajss.20170506.12 (PDF mirror: https://outlier.bet/wp-content/uploads/2023/08/2017-clarke-adjusting_bookmakers_odds.pdf)
- Buchdahl, J. — "Using the Wisdom of the Crowd to Find Value in a Football Match Betting Market." https://www.football-data.co.uk/The_Wisdom_of_the_Crowd_updated.pdf
- Buchdahl CLV methodology — Pinnacle Odds Dropper interview/summary. https://www.pinnacleoddsdropper.com/blog/closing-line-value--clv-demystified-by-expert-joseph-buchdahl
- Pyckio — "Pinnacle closing odds, market efficiency and tipsters' skill." https://blog.pyckio.com/en/pinnacle-closing-odds/
- Levitt, S. (2004). "Why are gambling markets organised so differently from financial markets?" *Economic Journal* 114(495):223-246. http://pricetheory.uchicago.edu/levitt/Papers/LevittWhyAreGamblingMarkets2004.pdf
- Paul & Weinbach — "Price Setting in the NBA Gambling Market: Tests of the Levitt Model of Sportsbook Behavior." https://www.researchgate.net/publication/23534378
- Devig method practice guides: sharkbetting.com/blog/devig-explained; BettingIsCool overround-removal script (bettingiscool.com)
- Datagolf — "The favourite-longshot bias is not a bias" (two-way margin-placement argument). https://datagolf.com/fav-longshot-not-a-bias

*Implementation verified read-only at: `engine/run_picks.py` (lines 833-847, 1021-1029) and `engine/capture_clv.py` (lines 909-929). All table values computed exactly (Shin solved iteratively; power solved by bisection; Shin ≡ additive confirmed numerically at all four odds pairs).*

---

## SECTION 6 — Game Line Distributions

**VERDICT:** NEEDS_CHANGE (overall, driven by sub-item 5)
- (1) NHL Normal totals/spreads: **CONFIRMED_WITH_CAVEAT** — league σs are well calibrated, but discreteness costs ~2pp near the mean, and the new matchup-sigma path *degrades* the calibration
- (2) MLB ML independent-NB exact sum: **CONFIRMED** — construction standard, independence empirically validated (ρ=0.013), tie-split near-exact in the ghost-runner era
- (3) BLEND_ALPHA=0.25: **CONFIRMED_WITH_CAVEAT** — defensible humble prior; sport-specific alphas are the right evolution but are data-gated
- (4) F5_SCALAR=0.540: **CONFIRMED** — consistent with market F5/full ratios and per-inning scoring shape
- (5) NBA GAME_SIGMA total=12.0 **and** the uniform `sqrt(σh²+σa²)` matchup formula: **NEEDS_CHANGE** — totals fallback is ~40% too narrow, and the matchup path applies an independence formula to *margins*, inflating spread/ML σ by ~45% and silently overriding the correct per-market NHL calibration

**CLASSIFICATION:**
- NHL GAME_SIGMA per-market values: PERIODIC_RECAL (annual, offseason)
- MLB ML NB sum + MLB_TEAM_RUN_R: LOCKED (re-verify only if rules change, e.g., extras format)
- BLEND_ALPHA: DATA_GATED (existing n=100 graded game-line CLV gate — confirmed appropriate)
- F5_SCALAR / F5_SIGMA: PERIODIC_RECAL (annual; sensitive to league run environment)
- NBA/WNBA GAME_SIGMA + `get_game_sigma()` matchup formula: NEEDS_CHANGE now, then PERIODIC_RECAL

**Condition to revisit:** Re-audit after `get_game_sigma()` is rewritten to preserve per-market covariance structure and NBA total/spread σs are calibrated from the `games` table; thereafter recalibrate each offseason or when league scoring environment shifts >3%.

> **Audit-coordinator verification (2026-06-05):** re-run against `data/projections.db` `games`+`player_game_stats` (3,922 games incl. playoffs): total mean 228.2, **total SD = 20.2**, margin SD = 16.0, home/away score correlation **ρ = +0.227**. Confirms NBA total σ=12.0 is ~40% too narrow and the positive within-game correlation that the independence-sum matchup formula ignores. The `get_game_sigma()` code path (run_picks.py:532-534 returning `sqrt(h²+a²)` for total/ml/spread alike) was also verified directly during the ground-truth pass.

### Findings

**1. NHL: Normal vs Poisson/Skellam — Normal-with-calibrated-σ is adequate to ~2pp; discreteness error is real but second-order; the matchup path is the bigger problem.**

Computed at λ=6.0:

| Line | Poisson(6) P(over) | Normal(6, 2.311) P(over) | Diff |
|---|---|---|---|
| 5.5 | 0.5543 | 0.5856 | −3.13pp |
| 6.5 | 0.3937 | 0.4144 | −2.07pp |

But the raw Poisson comparison overstates the error, because real NHL totals are **underdispersed vs Poisson**: from the engine's own 3,936 games, total goals have mean 6.187, var 5.340, **var/mean = 0.863**. The calibrated σ=2.311 < √6=2.449 is therefore *correct*, not an artifact. Re-running with a variance-matched underdispersed discrete distribution (binomial, var=5.34) vs Normal(6, 2.311): P(over 5.5) = 0.5637 vs 0.5856 (**−2.2pp**), P(over 6.5) = 0.3935 vs 0.4144 (−2.1pp). The residual ~2pp error is pure discreteness/right-skew — material relative to a 3.5–6% edge threshold, but half the naive Poisson-vs-Normal figure. Half-point lines sit exactly at the continuity-correction midpoint, so there is no additional half-point artifact.

Why underdispersed: Thomas (2007) showed hockey goal scoring is approximately Poisson but better described as a semi-Markov process with score effects (each goal effectively shortens the game ~20s; trailing teams push, leading teams defend — negative serial correlation within a game compresses total variance). The empty-net dynamic works the *opposite* way on margins — EN goals systematically pad winning margins — which is exactly what the engine's data shows: within-game home/away goal residual correlation **ρ = −0.102**, so margin σ (2.564 recomputed; 2.614 calibrated) > total σ (2.315 recomputed; 2.311 calibrated). The league GAME_SIGMA["NHL"] values are excellent — they independently reproduce within 0.05 goals.

**The caveat that matters:** `get_game_sigma()` (run_picks.py:532-533) returns `sqrt(σh²+σa²)` ≈ 2.40–2.50 for total, spread, AND ml whenever both teams resolve in `team_sigmas_nhl.json` — overriding the calibrated 2.311 (totals now ~6% too wide) and 2.614 (spreads now ~6% too narrow). The matchup feature shipped 2026-06-05 *destroyed the covariance correction the league dict encoded.* Skellam (Karlis & Ntzoufras 2009) or a bivariate Poisson (Karlis & Ntzoufras 2003) would handle both discreteness and dependence properly, but given the −0.10 correlation and underdispersion, the pragmatic fix is an empirical discrete PMF or simply restoring per-market σs; full Skellam is optional polish worth ~1–2pp.

**2. MLB ML exact NB sum: CONFIRMED on all three counts.**

(a) **Construction is correct and standard.** Independent count marginals per team with the match-outcome probability obtained by summing the joint PMF over the winning region is exactly the Maher (1982) framework (Poisson football), and the engine's exact summation `P(home win) = Σ_k P(H=k)·[P(A≤k−1) + 0.5·P(A=k)]` is the textbook discrete construction — no distributional name is needed for the difference because no approximation of the difference is made. NB marginals (r=3.548 league, per-team r in `team_sigmas_mlb.json`) correctly capture run-scoring overdispersion (var/mu=2.261), which Poisson would miss. The Dixon & Coles (1997) correction targets low-score *dependence* cells in soccer (0-0, 1-0); MLB's score range makes individual-cell dependence corrections immaterial. Truncation at k=30 is harmless (NB(r=3.548, μ=4.7) has <10⁻⁶ mass above 30).

(b) **Independence is empirically fine for MLB.** Common factors (park, weather, umpire) do induce positive correlation in principle, but from the engine's own 8,095 games, the within-game correlation of home/away run residuals (vs team season means) is **ρ = 0.0130** — essentially zero. Sensitivity check via Gaussian copula on the NB marginals (μ_h=4.7, μ_a=4.2): P(home win) = 0.5426 independent → 0.5449 at ρ=0.10 → 0.5475 at ρ=0.20. So even a ρ=0.10 misspecification biases ML by only ~0.2pp, and the direction is: ignoring positive correlation **understates the favorite** (positive correlation shrinks margin variance, Var(H−A)=σ²h+σ²a−2Cov). At the measured ρ=0.013 the bias is ~0.03pp. Negligible.

(c) **Ties-split-50/50 is now almost exactly right.** Historically home teams won extra-inning games at .521–.523 (1957–2007: 4,846–4,449 = .521; 1901–2019: .523 per Baseball-Reference/FanGraphs). But under the ghost-runner rule (2020–2024), home teams won only **49.3%** of extra-inning games — the historical edge inverted. Extras occur in ~8–9% of games, so the error from 0.5 is |0.493−0.500|×0.09 ≈ **0.06pp** — far below model noise. Even under classic rules it was only 0.2pp. Do not change this; if anything, 0.50 is *better* calibrated today than 0.52 would be.

**3. BLEND_ALPHA=0.25: defensible, confirmed as a humble prior; published anchors bracket it.**

- **nfelo** (NFL) found the Brier-optimal blend for their model — a genuinely near-market-quality model refined over years — is **65% model / 35% market**, i.e., market weight 0.35. Framed in JonnyParlay's convention (α = weight on *model* disagreement), nfelo runs α≈0.65 for an elite model. A SaberSim-derived projection with no demonstrated game-line CLV record warrants a much lower α; 0.25 is conservative but rational.
- **Kovalchik (2016)**, JQAS 12(3), tested 11 published tennis forecasting models against the bookmaker consensus model: the BCM was the best performer across accuracy, calibration, and log-loss. This is the canonical citation for "the market is the best single forecaster you have" — which justifies anchoring ≥50% to the market for any unproven model, i.e., α ≤ 0.5, with low α absent evidence.
- Sport-specific alphas are theoretically right (WNBA totals markets are demonstrably softer — wider vig, lower limits — supporting α≈0.35–0.40 there; NBA sides/totals at major books are among the sharpest markets, supporting α≤0.25). But fitting per-sport alphas now would be exactly the kind of parameter-without-data the internal research flagged. **Confirm the existing position:** 0.25 global, re-evaluate at n=100 graded game-line CLV rows, and fit per-sport only when each sport individually has ≥100 rows. One refinement worth adopting from nfelo at that point: error-weighted blending (scale α by situational model-vs-market reliability) outperformed any fixed α in their testing.

**4. F5_SCALAR=0.540: CONFIRMED — sits inside the published band; second-order starter-quality dependence exists but is partially self-correcting.**

Naive innings share is 5/9 = 0.556, but scoring is non-uniform: the 1st inning is the **highest-scoring inning** (~0.5 visitor + ~0.6 home runs; lineups are constructed so the three best hitters are guaranteed to bat — FanGraphs Community) and the 2nd is the lowest (bottom of the order); the 9th is structurally truncated (home team bats in only ~half of 9th innings, plus walk-off truncation), which pushes the 1–5 share back up. Market evidence: typical F5 totals run 4.5 vs full-game 8.5 (ratio 0.529) up to 5 vs 9 (0.556) — OddsIndex/BettorEdge F5 guides cite the 4.5-vs-7.5-to-8.5 relationship. The engine's 0.540 was itself market-calibrated from 2022–2025 F5 lines, i.e., fitted to exactly this quantity, and lands mid-band.

Does it vary by starter quality/park? Yes, mildly — an ace start shifts run share *later* (suppressed innings 1–5, normal bullpen innings 6–9), a weak starter shifts it earlier. But the scalar is applied to SaberSim team totals that already embed the starter, so the error is only in the *share*, not the level, and is second-order (a starter 1.0 ERA better than average moves the F5 share by roughly ±0.01–0.02). The F5 win-rate asymmetry (superior starters win 57% of F5 games vs 59% of full games, per published F5 betting analyses) confirms the effect is real but small. A fixed scalar is acceptable; a starter-quality-conditional scalar is a nice-to-have, not a defect. F5_SIGMA total=2.65 is plausible for a ~4.8-run mean with MLB-level overdispersion (Poisson floor √4.8≈2.19; NB inflation → ~2.5–2.7).

**5. NBA GAME_SIGMA and the matchup-sigma formula: NEEDS_CHANGE — two compounding errors, confirmed empirically from the engine's own database.**

From the repo's `games` + `player_game_stats` tables (3,680 regular-season games, 2023–2026, scores reconstructed by summing player points):

| Quantity | Value |
|---|---|
| Total: raw marginal SD | 20.05 |
| Total: residual SD vs team-season-mean expectation | **19.71** |
| Margin: residual SD vs team-mean expectation (+HFA 1.85) | 15.42 |
| Margin: SD around the closing spread (published) | **~12** (Winston/Mathletics: "near 12 points"; Stern-style Normal-margin literature) |
| Within-game home/away score correlation ρ | **+0.241** |
| Per-team score residual SD | 12.49 / 12.53 |
| `sqrt(σh²+σa²)` (engine's matchup formula) | 17.70 |
| With +2Cov (correct for totals) | 19.71 |
| With −2Cov (correct for margins, vs team means) | 15.42 |

This decomposes exactly as anticipated: Var(A+B) = Var(A)+Var(B)+2Cov > Var(A−B) when Cov>0, and NBA Cov is strongly positive (shared pace/efficiency environment, garbage time). The Boyd's Bets O/U-margin study independently confirms NBA totals variance is large and grows with the total (correlation 0.33 above/below 200). The WNBA cross-check is decisive: WNBA total σ=17.459 on a ~163-point league is σ/μ = 0.107; the engine's own NBA data gives σ/μ = 0.086 (→ σ≈19.7 at μ=229); NBA total σ=12.0 would imply σ/μ = 0.052 — *half* the relative variability of a lower-scoring league. Internally impossible; NBA 12.0 is the miscalibrated one.

**Error quantification (totals).** At a typical 6-point raw model-market total disagreement, BLEND_ALPHA=0.25 shrinks it to 1.5 points before the CDF: P(over) = 0.5497 at σ=12 vs 0.5323 at σ=18.5 — the engine's claimed edge (4.97pp) is **~54% larger than the true edge (3.23pp)**, a 1.74pp probability overstatement on every NBA total. The blend prevents catastrophe (unblended the overstatement would be 6.4pp: 0.6915 vs 0.6272) but the residual error still exceeds the typical 2.5–3.5pp edge thresholds' tolerance — it will systematically promote marginal NBA totals over the line into the card.

**But note which path actually fires.** Since the 2026-06-05 team-sigma commit, all three NBA game-line evaluations (run_picks.py:2704, 2766, 2868) call `get_game_sigma()`, which returns `sqrt(12.65²+12.65²)` ≈ **17.7 for total, spread, and ml alike** whenever both teams resolve in `team_sigmas_nba.json` (they almost always will). Consequences:

- **Totals:** accidentally near-correct (17.7 vs true ~18.5–19.7). Two errors cancel: the formula omits +2Cov (−2.0 pts) but uses marginal team SDs that contain opponent/rest/form variance the market line already prices (+~1–2 pts). The fallback 12.0 is now mostly dead code — but it is still wrong and still fires on team-resolution failures.
- **Spreads/ML: actively broken by the new path.** The correct around-the-spread margin σ is ~12 (Winston; and the old GAME_SIGMA spread=12.0 was right). The matchup path now uses 17.7 — **~45–48% too wide** — because it both omits −2Cov and uses marginal SDs. At a 6-point expected margin, P(ML win) = 0.685 at σ=12.5 vs 0.633 at σ=17.7: a **5.2pp understatement** of favorite win probability, growing with the spread (9-pt margin: 0.764 vs 0.694, 7.0pp). Spread cover-prob edges are roughly **one-third smaller** than they should be (e.g., 0.5497 vs 0.5338 at 1.5 blended points), suppressing legitimate picks and corrupting daily-lay leg gating (`cover_prob≥0.58` becomes nearly unreachable). The comment at line 2868 ("ML uses ml sigma (wider) not spread sigma") is now dead logic — both markets get the identical sqrt-sum.
- The same structural flaw degrades NHL (above) in the opposite-sign direction (ρ<0), and mildly *improves* MLB totals (matchup ≈4.56 vs empirical residual 4.50, vs legacy 4.0 too narrow) only because MLB's ρ≈0.013 makes the independence formula actually appropriate there. One formula, three sports, three different correlation signs — it can only be right for MLB.

**Recommended fix (exact):**
1. Calibrate NBA per-market league σs from the `games` table exactly as NHL was: total σ ≈ **18.5** (split the difference between the team-mean residual 19.71 and the around-the-line estimate; ideally regress vs stored closing totals once game-line CLV rows accumulate), spread/ml σ ≈ **12.5** (team-mean residual 15.42 haircut to the published around-the-spread ~12, consistent with the modern pace era), team ≈ **11.0** (per-team conditional SD; current 9.0 is also too narrow vs 12.5 marginal). WNBA: calibrate spread/ml the same way before any WNBA spread/ML picks go live (current 10.0 placeholders would have the same wrong-σ problem); also fix the WNBA_ID_MAP so the 17.459 total path isn't permanently on fallback.
2. Rewrite `get_game_sigma()` to preserve per-market covariance: `σ_matchup(market) = σ_league(market) × sqrt((σh² + σa²) / (2·σ̄_league²))` — i.e., use team sigmas only as a *relative variability scaler* on the correctly-calibrated per-market league σ, never as an absolute independence sum. This single change simultaneously repairs NBA spreads/ML, restores the NHL per-market calibration, and keeps the matchup specificity the feature was built for. Store ρ per league in the JSON if you later want the exact ±2Cov form.

### Sources
- nfelo — "Using Market Regression to Improve Prediction Accuracy in the NFL." https://www.nfeloapp.com/analysis/using-market-regression-to-improve-prediction-accuracy-in-the-nfl/
- Kovalchik, S. (2016), "Searching for the GOAT of tennis win prediction," *JQAS* 12(3):127–138. https://vuir.vu.edu.au/34652/1/jqas-2015-0059.pdf
- Thomas, A. (2007), "Inter-arrival Times of Goals in Ice Hockey," *JQAS* 3(3). https://hockeyanalytics.com/Research_files/Interarrival%20Times%20of%20Goals%20in%20Ice%20Hockey.pdf
- Karlis & Ntzoufras (2003), "Analysis of sports data by using bivariate Poisson models," *JRSS-D* 52(3); Karlis & Ntzoufras (2009), Skellam goal-difference modelling.
- Wayne Winston (*Mathletics*) — "Why is Standard Deviation of NBA scores about point spread 12 points." https://waynewinston.com/wordpress/p_2333/
- Boyd's Bets — "Standard Deviations of Over/Under Margins by Total." https://www.boydsbets.com/standard-deviations-of-overunder-margins-by-total/
- FanGraphs — "The Math Behind the Extra Innings Home Field Disadvantage"; Baseball-Reference Blog — home team record in extra innings (.521 classic; .493 ghost-runner era)
- FanGraphs Community — "Why Are so Many Runs Scored in the Bottom of the First Inning?"
- OddsIndex — F5 Betting Guide; BettorEdge — MLB First 5 Inning Bets (F5 totals 4.5–5.5 vs full 7.5–9)
- Woolner, K. (Baseball Prospectus) — "An analytic model for per-inning scoring distributions." https://legacy.baseballprospectus.com/images/analytica/rpi_model.pdf
- Maher, M.J. (1982), "Modelling association football scores," *Statistica Neerlandica* 36; Dixon & Coles (1997), *JRSS-C* 46(2)
- Engine-internal empirical calibrations (read-only): `data/projections.db` — 3,680 NBA RS games (total resid σ=19.71, margin resid σ=15.42, ρ=+0.241; coordinator re-run on 3,922 games: total SD 20.2, margin SD 16.0, ρ=+0.227), 8,095 MLB games (ρ=+0.013), 3,936 NHL games (ρ=−0.102, var/mean=0.863); `data/team_sigmas_*.json`; `engine/run_picks.py:519-534, 2701-2868`; `engine/calibrate_distributions.py:477-543`

---

## SECTION 7 — Push Handling
**VERDICT:** CONFIRMED_WITH_CAVEAT
**CLASSIFICATION:** LOCKED
**Condition to revisit:** Revisit only if integer-line picks on Normal-path stats (PTS/OUTS/PC/SV/combos) ever start appearing in the pick logs — currently 0 of 695 logged Normal-stat props across all five logs.

### Findings

**1. Integer-line decomposition and renormalization — CONFIRMED, exact.**
For any discrete distribution and integer line L=k, the three events {X<k}, {X=k}, {X>k} partition the sample space, so CDF(k−1) + pmf(k) + [1−CDF(k)] = 1 identically. Renormalizing by (1−push) is the definition of conditioning: P(X>k | X≠k) = P(X>k)/(1−P(X=k)).

Worked example, NB(μ=5.5, r=12.16) at line=5, using the engine's exact parameterization (implied var/μ = 1+μ/r = 1.452):

| Quantity | Value |
|---|---|
| push = pmf(5) | **0.145030** |
| strict_over = 1−CDF(5) | 0.454556 |
| strict_under = CDF(4) | 0.400414 |
| Sum | **1.0000000000** ✓ |
| over_p = 0.454556/0.854970 | **0.531663** |
| under_p = 0.400414/0.854970 | **0.468337** |
| Conditional sum | **1.0000000000** ✓ |

The conditional distribution is correct: for any j≠5, P(X=j | X≠5) = pmf(j)/(1−push), and summing over j>5 gives exactly strict_over/(1−push) — which is what the code computes (run_picks.py:913–919; identical structure on the Poisson path at 894–900).

**2. Renormalization is the correct treatment under void/refund rules — CONFIRMED, with the edge and Kelly consistency checks both passing.**
When a push refunds the stake, the bet is a conditional wager that only settles when X≠k. The standard reference treatment agrees: Stanford Wong, *Sharp Sports Betting*, states that breaking even at −110 "requires winning 52.4 percent of non-ties" and computes records by removing ties. Equivalently, the EV-with-refund formula (Australia Sports Betting): EV = odds·P(win) + 1.00·P(push) − 1, i.e., the push leg pays decimal odds 1.00 (zero net).

*Apples-to-apples edge check:* the book's implied probability from American odds (e.g., −110 → 52.38%) is exactly the breakeven rate **among decided bets** under refund rules — i.e., it is also conditional on no push. So comparing renormalized model probability against vigged-implied probability is consistent. Confirmed algebraically: unconditional EV per unit = p_w·b − p_l = (1−q)·[p̃_w·b − p̃_l], where p̃ are the conditional probabilities — the (1−q) factor scales EV magnitude but never changes its sign or pick ranking.

*Kelly check (three-outcome):* maximize p_w·log(1+fb) + p_l·log(1−f) + q·log(1). First-order condition gives f* = (p_w·b − p_l) / (b·(p_w+p_l)). Substituting p̃_w = p_w/(1−q), p̃_l = p_l/(1−q) into the standard two-outcome Kelly f = (p̃_w·b − p̃_l)/b yields (p_w·b − p_l)/(b·(1−q)) = (p_w·b − p_l)/(b·(p_w+p_l)) — **identical**. Feeding conditional probabilities into ordinary Kelly is exactly the correct three-outcome optimum. The engine's pipeline (conditional prob → edge → Kelly) is internally consistent.

**3. Materiality — large; the renormalization is decision-flipping, not cosmetic.**
At line=5, μ=5.5, r=12.16: push mass pmf(5) = **0.1450** (14.5%). Raw P(over) = 0.4546 vs conditional P(over|no push) = 0.5317 — a **7.71 pp** difference (6.79 pp on the under side). Against a −110 breakeven of 0.5238, the raw number implies a −6.9 pp edge (no bet / bet the other side) while the correct conditional number implies +0.8 pp. A missing renormalization would not merely shave a 5% edge — it would flip the sign of the decision for near-the-mean integer lines. The push handling is materially load-bearing.

**4. Half-point lines.** For line = k+0.5, floor(line) ≠ line, P(X = line) = 0 for an integer-valued variable, and over_p + under_p = [1−CDF(k)] + CDF(k) = 1 exactly — push=0 by construction. Confirmed.

**5. Degenerate guard.** For any proper PMF with μ>0, pmf(k) < 1 strictly for every k (mass exists at other support points), so non_push > 0 always. The only path to non_push = 0 is μ≤0 with line=0 (the pmf functions return 1.0 at k=0 when μ≤0, run_picks.py:761–762, 788–789), and non-positive projections are filtered upstream. The guard is unreachable in practice and harmless (0.5/0.5 produces zero edge → no pick). Confirmed.

**6. Normal-path integer-line gap — real in theory, second-order in math, and empirically nonexistent in practice.**
Estimate of push mass at a PTS-like integer line: NB with μ=20, var=2.86μ (r = 10.75) gives q = pmf(20) = **0.0523** (~5.2%). True strict P(X>20) = 0.4325; true conditional P(over|no push) = 0.4325/0.9477 = **0.4564** (+2.39 pp vs raw; under side +2.84 pp).

However: a continuous Normal evaluated at integer L implicitly **splits the push mass between the two sides** — with continuity correction, Φ-based P(over) ≈ P(X>L) + q/2 (here 0.4325 + 0.0261 = 0.4587). The correct conditional target is P(X>L)/(1−q) = 0.4564. The push-specific bias is therefore q·(P_over − ½) ≈ 0.052 × 0.024 ≈ **0.2 pp** — second-order, nearly vanishing for near-coin-flip lines, bounded by ~q/2 in the extremes. The engine's actual Normal(20, σ=7) gives P(over)=0.501; the dominant ~4.3 pp of its total 4.5 pp error vs the NB benchmark is **distributional mismatch** (right-skew of count data pulls the median below the mean), not push handling — a separate, already-known modeling choice for the Normal path.

Prevalence check (decisive): across all pick logs — `pick_log.csv` (61), `pick_log_wnba.csv` (506), `pick_log_custom.csv` (128), `pick_log_manual.csv` (0), `pick_log_mlb.csv` — **zero** integer-line picks on Normal-path stats (PTS/OUTS/PC/SV/PRA/PR/PA/RA) out of 695 total. US books post half-point lines for these markets essentially universally. **Recommendation: no code change.** If integer-line Normal-stat offers ever appear, the cheap correct fix is a discretized continuity treatment (push ≈ Φ(L+½)−Φ(L−½), renormalize) or simply skipping such lines; adding it now would be speculative complexity for a market configuration that does not occur.

Files verified: `engine/run_picks.py` (calc_prop_prob lines 874–950; poisson_pmf/cdf 759–772; negbinom_pmf/cdf 781–812).

### Sources
- Stanford Wong, *Sharp Sports Betting* (Pi Yee Press) — breakeven "requires winning 52.4 percent of non-ties"; records computed after removing ties.
- Australia Sports Betting — Implied Probability and Expected Return (EV with refund: refund leg pays decimal odds 1.00). https://www.aussportsbetting.com/guide/basics/implied-probability-expected-return/
- The Action Network — "What Is a Push in Sports Betting?" https://www.actionnetwork.com/education/push
- Wizard of Odds — "Buying and Selling Points in the NFL" (empirical win/loss/push framework for half-point valuation). https://wizardofodds.com/games/sports-betting/appendix/4/

---

## SECTION 8 — G14 Projection Clearance
**VERDICT:** CONFIRMED_WITH_CAVEAT
**CLASSIFICATION:** PERIODIC_RECAL
**Condition to revisit:** Re-derive the G13↔G14 raw-space equivalence the day H3 ships (new Platt A/B/space changes which gate binds, per direction), and revisit the NB-stat exemption when near-line (z<0.25) NB graded picks reach n≈75 — current n=37 runs 43.2% WR, below breakeven.

### Findings

**1. Is z=0.10 meaningful or a near-no-op? Answer: it is a no-op for overs on Platt-calibrated stats, but does real work for unders — and the edge floors dominate both at standard juice.**

Verified math: Φ(0.10) = 0.53983, so G14 is a raw-space win-prob floor of ~54.0% for Normal stats. The critical interaction is with Platt (`_platt_calibrate_prop`, run_picks.py:857–871, applied at :2559 *before* gates for non-MLB, non-combo picks). G13 tests **post-Platt** prob ≥ 0.50. Inverting sigmoid(1.4988p − 0.8102) = 0.50 gives raw p = 0.8102/1.4988 = **0.54057**, i.e. z = **0.1019**. So:

| Stat path | Direction | G13 in raw-z terms | G14 | Binding gate |
|---|---|---|---|---|
| Platt'd Normal (NBA PTS, NHL SV) | over | z ≥ 0.1019 | z ≥ 0.10 | **G13** — G14 redundant by Δz = 0.002 |
| Platt'd Normal | under | z ≥ **−0.1019** | z ≥ 0.10 | **G14** — does real work |
| MLB Normal (OUTS, PC; no Platt) | both | z ≥ 0 | z ≥ 0.10 | **G14** |
| Combos (no Platt) | both | z ≥ 0 | z ≥ 0.10 | **G14** |

The under-side asymmetry is the non-obvious finding: Platt's negative intercept deflates over_p and therefore *inflates* under_p = 1 − Platt(over_p). A Normal-stat under with proj exactly on the line gets under_p = 1 − Platt(0.50) = **0.5152**, which passes G13 with literally zero directional conviction. Only G14 blocks it. So G14 is not redundant; it is the *only* directional-conviction gate for Platt'd unders and all MLB/combo Normal picks.

However, at standard two-sided −110/−110 juice, the edge floors dominate everything: G9 (edge ≥ 0.05) requires post-Platt prob ≥ 0.55 → raw p = 0.6745 → **z ≥ 0.452** for Platt'd overs; **z ≥ 0.236** for Platt'd unders; **z ≥ 0.126** for MLB. G9B (NBA, 0.07) pushes overs to z ≥ 0.609. G14's binding region is therefore confined to **skewed/plus-odds prices** where the no-vig implied prob is low enough that a near-line projection still clears the edge floor. That is exactly the "sigma-driven phantom edge at attractive odds" failure mode, so the gate's residual scope is the right scope.

Should it be a win_prob floor instead? Partially-defensible no. A raw-space wp floor of 0.5398 would be identical for Normal stats but undefined for the combo path (whose sigma comes from `_combo_mu_sigma` with correlations, not SIGMA). The genuine design flaw is that G14's effective strictness silently changes whenever PLATT_A/B change — nothing in the code documents that G14's over-side redundancy and under-side bindingness are artifacts of the current A/B. **Recommendation: add a comment at run_picks.py:1252 recording the equivalence (G13 ⇔ z≥0.1019 overs / z≥−0.1019 unders under current Platt) and flag it in the H3 deployment checklist.**

**2. The NB/Poisson exemption: the stated rationale is real but thin, and the exemption is contradicted by the engine's own WNBA block.**

The code comment's example checks out: AST under 4.5 with proj=4.6 gives NB P(X≤4 | μ=4.6, r=12.16) = **0.5315** (Poisson: 0.5132), while the Normal proxy gives Φ(−0.1/2.438) = **0.4836**. So the discrete CDF genuinely can favor a pick whose projection sits on the wrong side of a half-point line — the half-integer line plus integer mass acts as a built-in continuity correction. The Normal CDF is equally "well-defined," but it gives a *different answer* at the boundary, and the discrete answer is the correct one for count stats. So the rationale is not vacuous: applying z≥0.10 to NB stats would block picks the calibrated distribution legitimately favors.

For NB P(X≥6 | μ=6.0, r=12.16) = **0.5227** (Poisson 0.5543) — note the NB probability is *below* Φ(0.10)=0.5398, i.e., an NB pick can pass at lower true conviction than any Normal pick. That's the hole in the exemption.

The honest assessment: **model error in μ dominates 0.1σ regardless of family**. A ±0.5 error on a 6.0 AST projection is ±0.16σ — larger than the entire clearance requirement. The distribution family determines how the boundary is scored, not whether a 0.1σ edge is trustworthy. The exemption survives in practice only because the G8-family does the work for the worst region: G8 (AST/REB/SOG/HA/HITS line ≤1.5), G8B (AST over ≤4.5 NBA), R11, R4, G8D (3PM over ≤1.5), plus the SOG/HA suspensions. After those, live near-line NB exposure is roughly: AST over ≥5.5, AST under 0.5, REB under ≥3.5, 3PM over ≥2.5/under, MLB ER/RBI. That's coverage by accumulated post-hoc record-based kills, not by principle — i.e., **the exemption is substantially an artifact**.

Decisive internal contradiction: WNBA 3PM/AST/REB get their *probability* from NB (NB_R_WNBA, with 3PM r=1.34, heavily overdispersed) yet G14 *is* applied to them via the SIGMA_WNBA z-proxy (run_picks.py:1268–1273). If "the discrete CDF handles boundary cases correctly" justified exempting NBA NB stats, it would justify exempting WNBA NB stats too. The engine applies clearance where the distribution is *most* skewed/zero-inflated (where a symmetric z-proxy is least valid) and exempts it where the NB is nearly Normal (r=12–15 at typical μ). The layering is historical, not principled.

**3. Empirical z-bucket analysis (data/pick_log.csv, 307 rows, 295 graded W/L).**

Normal stats (PTS n=33, OUTS n=10; PC/SV have no graded rows), z computed from current SIGMA params:

| z bucket | n | W | WR | Wilson 95% CI |
|---|---|---|---|---|
| < 0.10 | 2 | 1 | .500 | (.095, .905) |
| 0.10–0.25 | 3 | 2 | .667 | (.208, .939) |
| 0.25–0.50 | 29 | 19 | .655 | (.473, .801) |
| 0.50–1.00 | 9 | 8 | .889 | (.565, .980) |

WR is monotone in z (directionally consistent with the prior audit's 45.7% close-line vs 53.7% far-line finding), but the 0.10–0.25 band has **n=3** — the data cannot support raising the threshold to 0.20–0.25. This is structural, not just small-sample: G14 censors z<0.10 and G9/G9B's implied z empties the low-z band for the dominant stat. **No change to 0.10 is justified or testable from the live log.**

Exempt NB stats (3PM 33, REB 27, AST 15, HA 10), z via NB sigma √(μ+μ²/r):

| z bucket | n | W | WR | Wilson 95% CI |
|---|---|---|---|---|
| < 0.10 | 27 | 13 | .481 | (.307, .660) |
| 0.10–0.25 | 10 | 3 | .300 | (.108, .603) |
| 0.25–0.50 | 43 | 22 | .512 | (.368, .654) |
| ≥ 0.50 | 5 | 3 | .600 | — |

Combined near-line (z<0.25): **16/37 = 43.2%**, Wilson CI (.287, .591) vs −110 breakeven of 52.4%. Not significant at 95%, and confounded (many rows predate the G8-family kills now blocking this region), but the point estimate sits exactly where the model-error argument predicts: near-line *discrete* picks are the losing region, while gated Normal stats are clean. If anything, the data argues for **extending clearance to NB stats** (in probability space: require NB P ≥ ~0.54, matching the Normal-stat floor), not for raising z on Normal stats.

**4. Literature.** Published work supports thresholds in *both* spaces, and the engine's redundancy is defensible. Paul & Weinbach (2002, *Journal of Sports Economics* 3(3)) is the canonical **projection-space** clearance result: betting unders only when the posted total sat 5/6/7+ points above the distribution mean — profitability required a *minimum points-space disagreement*, with larger clearance → stronger result, the same monotonicity seen in the Normal-stat table above. (Follow-up work, e.g. the AABRI NFL totals replication, finds the rule decayed post-2010 — thresholds are regime-dependent, supporting PERIODIC_RECAL.) On the **probability-space** side, Ramesh et al. (2019, arXiv:1910.08858) bet only when model probability exceeds market implied by an epsilon margin (ε ≈ 0.03, sport-dependent) — the direct analogue of G9/G9B.

The dual-gate design is defensible because the two gates fail on different error sources: **edge floors (G9/G9B) catch odds-driven phantom edges** — a stale or skewed price makes a mediocre projection look +EV; the clearance gate is immune because it never sees the odds. **G14 catches sigma-driven phantom edges** — an overdispersed or mis-specified σ inflates Φ(z) at plus odds where the edge floor is easy to clear. Since G14's binding region is precisely skewed-odds picks, the gates partition the failure space with minimal overlap. The redundancy with G13 on the over side is cosmetic; the system is coherent, just undocumented.

**Caveats driving the verdict:** (a) the z=0.10 value itself was never fit to anything and is untestable from censored live data — it is defensible only as "approximately the Platt-implied G13 boundary," which is a coincidence the code doesn't record; (b) the NB exemption's rationale is half-true and contradicted by the WNBA block; the empirical losing region is exempt NB near-line picks, currently patched by record-based kills rather than a distribution-consistent clearance rule; (c) the entire G13/G14 geometry inverts per-direction when H3 replaces PLATT_A/B — this must be on the H3 checklist.

### Sources
- Paul, R.J. & Weinbach, A.P. (2002). "Market Efficiency and a Profitable Betting Rule: Evidence From Totals on Professional Football." *Journal of Sports Economics* 3(3):256–263. https://journals.sagepub.com/doi/10.1177/1527002502003003003
- Ramesh, S. et al. (2019). "Beating the House: Identifying Inefficiencies in Sports Betting Markets." arXiv:1910.08858
- AABRI — bettor biases and NFL totals market efficiency (post-2010 decay of the Paul–Weinbach unders rule). http://www.aabri.com/manuscripts/193138.pdf
- Core Sports Betting — "How to Set Edge Threshold for Sports Betting"; OpticOdds — "Hold vs. EV"
- Code verified: `engine/run_picks.py` (G14 :1252–1279; Platt :857–871, applied :2559; G9/G9B/G13 :1233–1243; SIGMA :347–368; NB_STATS :395; G8-family :1161–1194). Empirical: `data/pick_log.csv` (295 graded rows), scipy-verified Φ/NB/Poisson computations shown inline.

---

## SECTION 9 — Correlation Penalties in Sizing
**VERDICT:** NEEDS_CHANGE (narrow — base `corr_m` 0.85/0.70 and `exp_m` 0.70 are defensible as conservative heuristics; R13's stacked pitcher penalty is mis-premised and double-counts a correlation that G11 has already removed)
**CLASSIFICATION:** LOCKED (for base multipliers — at current stake fractions, precision is immaterial; R13 is a one-time code fix, not a recalibration)
**Condition to revisit:** Revisit only if effective stake fractions rise above ~¼ of full Kelly (e.g., KELLY_FRACTION increase, unit size increase, or card size growth pushing total simultaneous exposure past ~10% of bankroll), where joint-Kelly optimization starts to bind.

> **Audit-coordinator verification (2026-06-05):** G11 enforcement confirmed at run_picks.py:3592-3602 (Pass 3 MLB correlation dedup over MLB_CORR_GROUPS) and audit assertion at :6284 ("Max pitcher props per pitcher = 1"). R13's `pitcher_game_seen ≥ 2` can therefore only fire on different pitchers — the NEEDS_CHANGE premise is verified.

### Findings

**1. Kelly theory for simultaneous correlated bets — the correct law is 1/(1+ρ), the "(1−ρ)/2" claim is wrong, and at these stake sizes the adjustment is second-order.**

Setup: two bets, p=0.55, −110 (b=0.9091). Single-bet full Kelly f* = (bp−q)/b = **5.50%** of bankroll. Per-dollar edge μ = bp−q = 0.05; per-dollar return variance σ² = pb²+q−μ² = 0.9021.

Joint log-growth for two symmetric correlated bets, quadratic approximation (the standard mean-variance approximation to E[log] used in simultaneous-Kelly treatments, e.g., Thorp's handbook chapter and Whitrow 2007):

G(f₁,f₂) ≈ μ(f₁+f₂) − ½σ²(f₁²+f₂²+2ρf₁f₂)  →  FOC: **f_opt = μ/[σ²(1+ρ)]** for the symmetric pair, i.e. each bet is scaled by **1/(1+ρ)** relative to the simultaneous-independent case (and 1/(1+(n−1)ρ̄) for n equicorrelated bets).

Verified against the exact discrete optimization (maximize p₁₁ln(1+2bf) + 2p₁₀ln(1+(b−1)f) + p₀₀ln(1−2f), with p₁₁ = p²+ρpq etc.):

| ρ | Exact joint f (each bet) | Quadratic approx | Multiplier vs independent case |
|---|---|---|---|
| 0.00 | 5.48% | 5.54% | 1.000 |
| 0.10 | 4.99% | 5.04% | **0.909** |
| 0.25 | ~4.40% | 4.43% | **0.800** |
| 0.50 | ~3.66% | 3.70% | **0.667** |
| 0.70 | 3.23% | 3.26% | **0.588** |

- **The "(1−ρ)/2 reduction" claim FAILS.** As a multiplier it gives 0.45 at ρ=0.10 (correct: 0.909); as a reduction it gives multiplier 0.60 at ρ=0.10 — both wrong by a factor of ~1.5–2. The correct law is 1/(1+ρ). Discard the plan's formula.
- **Implied ρ of the engine's multipliers, read as full-Kelly-optimal adjustments:** 0.85 = 1/(1+ρ) → ρ = 0.176 (2nd pick); 0.70 = 1/(1+2ρ) → ρ = 0.214 (3rd pick, equicorrelated). Both sit at the **top of the empirical same-game different-player band (0.05–0.25)** — conservative but not crazy. Coincidentally well-chosen.
- **The honest part: at this engine's stake sizes, none of this matters in growth terms.** Stakes are 0.50–1.25u ≈ 0.5–1.25% of bankroll against a full-Kelly optimum of ~5.5% — deep fractional (1/15–1/30 Kelly). The correlation cross-term in G is σ²ρf_if_j: at f=0.0075, ρ=0.25 it equals ≈ 1.3×10⁻⁵, vs the pair's edge term 2μf ≈ 7.5×10⁻⁴ — under 2% of the edge contribution. Moreover, marginal growth dG/df = μ − σ²(1+ρ)f is **strictly positive** at these stakes even at ρ=0.70, so shrinking stakes further *reduces* expected log growth. Applying the 0.85 multiplier to a 0.75u pick costs ≈ 1×10⁻⁴ of daily log-growth and buys ≈ 8% reduction in the pair's P&L standard deviation. **The multipliers are not Kelly-derived necessities at these fractions — they are cheap variance insurance.** Fractional Kelly has already "solved" the growth-safety problem; the multipliers' only legitimate role is marginal variance/drawdown smoothing and robustness to overstated edges (where shrinking toward zero is the safe direction per Baker–McHale). Also note the 0.25u rounding grid and 0.50u floor quantize the effect to at most one step, frequently zero.

**2. R13 is mis-premised: it prices a same-player correlation that the G11 gate has already eliminated.**

Verified in code: G11 (run_picks.py:3592–3596, audit check :6244–6249) keeps **max 1 prop per pitcher** across {OUTS, HA, ER, BB, PC}. Therefore when `pitcher_game_seen[game]` reaches 2 (run_picks.py:1728–1731), the two pitcher props are necessarily on **different pitchers** — i.e., opposing starters. The ρ≈0.70 premise (OUTS↔HA through shared IP, per the comment at line 470) is exactly the same-player channel G11 blocks. Opposing starters' workloads share only environment (park, weather, umpire, game flow, blowout/early-hook risk) — plausibly ρ ≈ 0.05–0.20, and the engine's **own** MLB SGP ρ table prices cross-pitcher/cross-type pairs at **0.02** (only the scripted OUTS-over + opposing HITS-under pair gets 0.30). The engine's two correlation models contradict each other.

What the stacked penalty implies: total 0.595× (2nd pick) → 1/(1+ρ) gives ρ = 0.68; total 0.49× (3rd pick) → 1/(1+2ρ) gives ρ = 0.52. What ρ ≈ 0.15 actually warrants: ~0.87× — which the **base game multiplier (0.85) already delivers**. R13 is pure double-counting. Recommendation: **retire R13** (or re-scope it to fire only on same-player pitcher pairs, in which case it's dead code while G11 stands — retiring is cleaner). Mitigating context: with HA suspended (G_HA_SUSPENDED) and the floor/rounding quantization, R13's live cost is one 0.25u step of undersizing on occasional +EV opposing-pitcher pairs — a real but small EV leak, not a risk problem.

**3. Flat multipliers beat dynamic per-pair ρ at this scale; published practice agrees.**

Whitrow (2007, JRSS-C 56(5):607–623) develops the full joint-log-utility optimization for many simultaneous events and shows naive per-bet Kelly materially overbets only when *aggregate* simultaneous exposure is large (his examples operate near full Kelly across dozens of events). Grant, Johnstone & Kwon (2008, *Decision Analysis* 5(1):10–18) treat the λ-fractional-Kelly bettor on simultaneous games and likewise find the interesting effects live near λ=1. This engine's total card exposure is ~2–6% of bankroll — far from that regime. Practitioner standard (and the Benter precedent for race cards) is: fractional Kelly per bet + a total-exposure cap with proportional scaledown, plus coarse correlation haircuts — not per-pair estimated ρ. Quantitatively: moving ρ from 0.10 to 0.25 moves the optimal multiplier from 0.91 to 0.80; on a 0.75u stake that is 0.08u — **below the 0.25u quantization step**. Per-pair ρ estimation (noisy, ~±0.05 SE at realistic sample sizes) would add complexity with literally zero effect on shipped sizes most days. Flat multipliers are the correct complexity level. CONFIRMED.

**4. exp_m=0.70 (repeat stat across card) — directionally supported by estimation-risk theory, but it triple-stacks with mechanisms already serving the same purpose.**

The risk it targets is real: cross-game same-stat picks share *parameter* risk, not outcome correlation — a biased PTS projector hits every PTS pick simultaneously, inducing positive unconditional correlation between their outcomes from the bettor's vantage. Baker & McHale (2013) prove that parameter uncertainty warrants shrinking Kelly stakes below the plug-in optimum, and a common-factor error compounds across concentrated same-model exposure, justifying *extra* shrinkage on the marginal same-stat pick. So a penalty has theoretical standing. However: (a) Baker–McHale's optimal shrinkage for realistic estimation error lands around 0.4–0.8× full Kelly — the engine already sits at ~0.05–0.2× via KELLY_FRACTION, far below any uncertainty-adjusted optimum, so the parameter-risk argument is already over-served; (b) the same risk is independently penalized by **KELLY_MARKET_MULT** (a 2nd NBA PTS-over pick carries 0.50 × 0.70 = 0.35× before corr_m even applies) and capped by **STAT_CAP** (default 2 per stat), which means exp_m can fire at most once per stat anyway. The 0.70 magnitude is arbitrary but the structure is harmless and the concentration-limit function is standard risk practice. Verdict on exp_m: keep, but recognize it as a concentration limit, not a calibrated correlation adjustment — do not tune it as if it were one.

**Summary of required changes:** (1) retire R13 (premise eliminated by G11; implied ρ=0.52–0.68 vs actual ~0.05–0.20 for what it gates); (2) strike the "(1−ρ)/2" formula from any planning docs — correct law is 1/(1+(n−1)ρ̄); (3) leave corr_m 0.85/0.70, exp_m 0.70, and the flat (non-dynamic) design as-is, understood as variance insurance costing ~1bp/day of growth, not Kelly optimality.

### Sources
- Whitrow, C. (2007). "Algorithms for optimal allocation of bets on many simultaneous events." *JRSS Series C* 56(5):607–623. https://rss.onlinelibrary.wiley.com/doi/abs/10.1111/j.1467-9876.2007.00594.x
- Thorp, E.O. (2006). "The Kelly Criterion in Blackjack, Sports Betting, and the Stock Market." *Handbook of Asset and Liability Management*, Vol. 1. https://gwern.net/doc/statistics/decision/2006-thorp.pdf
- Baker, R.D. & McHale, I.G. (2013). "Optimal Betting Under Parameter Uncertainty: Improving the Kelly Criterion." *Decision Analysis* 10(3):189–199. https://pubsonline.informs.org/doi/abs/10.1287/deca.2013.0271
- Grant, A., Johnstone, D. & Kwon, O.K. (2008). "Optimal Betting Strategies for Simultaneous Games." *Decision Analysis* 5(1):10–18. https://pubsonline.informs.org/doi/10.1287/deca.1080.0106
- Vegapit — "Numerically solve Kelly criterion for multiple simultaneous bets." https://vegapit.com/article/numerically_solve_kelly_criterion_multiple_simultaneous_bets/
- Uhrín et al. (2021). "Optimal sports betting strategies in practice: an experimental review." arXiv:2107.08827
- Internal code verification: `engine/run_picks.py` lines 1696–1747 (size_picks_vake, corr_m/exp_m/R13), 468–472 (PITCHER_STATS, G11 groups), 1061–1082 (kelly_units), 3565–3596 & 6244–6249 (G11 dedup + audit assertion).

---

## SECTION 10 — SGP Joint Probability
**VERDICT:** CONFIRMED_WITH_CAVEAT
**CLASSIFICATION:** DATA_GATED
**Condition to revisit:** Revisit when the SGP Platt calibration gate fills (100 scored SGP slips; 52/100 as of 2026-06-03) — validate the copula joint against realized slip hit rate and tune the 0.10/0.55/0.035 thresholds, which the code itself flags as "starting points — tune against CLV/W-L data over 50+ builds" (sgp_builder.py:725).

### Findings

**1. Copula family choice — Gaussian is appropriate; family sensitivity is ≤1.6pp at these ρ levels, sub-0.5pp among tail-symmetric families.**

Implementation verified (engine/sgp_builder.py:288-330): pairwise ρ ranges from −0.20 to +0.35 (same-team offensive overs=0.35, same-player same-direction=0.28, cross-team overs=0.10, cross-game=0.00), Cholesky-factorized with a near-singular clip and an independence fallback. MLB (engine/mlb_sgp_builder.py:179-220): OUTS-over + opposing HITS-under=0.30, same-team batters=0.15, pitcher+own batter=0.02, as documented.

Computed example (Monte Carlo, N=2,000,000, SE≈0.03pp; families matched on Kendall's τ=0.161 ≡ Gaussian ρ=0.25): 3 legs at p=0.65, equicorrelated ρ=0.25:

| Model | Joint P(all 3 hit) | vs Gaussian |
|---|---|---|
| Independent | 0.2746 | −6.6pp |
| **Gaussian ρ=0.25** | **0.3406** | — |
| Frank (θ=1.479) | 0.3395 | −0.1pp |
| t-copula (df=5) | 0.3436 | +0.3pp |
| Clayton (θ=0.383) | 0.3251 | −1.6pp |
| Survival Clayton | 0.3553 | +1.5pp |

The correlation uplift itself (+6.6pp over independence) is an order of magnitude larger than the family sensitivity (±1.6pp worst case, ±0.3pp among tail-symmetric families). This is because P(all legs hit) at p≈0.55–0.75 is a joint-orthant probability evaluated near the center of the copula, not in the deep tail where Clayton/t tail-dependence differences live. Literature support: McHale & Scarf used Frank and Clayton copulas with count margins for soccer score dependence and found family choice secondary to dependence-parameter estimation (McHale & Scarf 2007, *Statistica Neerlandica*; 2011, *Statistical Modelling*); industry sources confirm sportsbooks themselves use Gaussian copulas plus empirical frequency tables for SGP pricing (OddsIndex SGP correlation guide; Wizard of Odds). **Conclusion: getting ρ right matters ~10× more than copula family at these correlation levels. The deliberate ρ floor (<0.40) dominates any family-choice error, and it errs conservative.** One structural note: the equicorrelation interpolation `_copula_joint_approx` (joint = p_indep + ρ̄·(min(p) − p_indep), line 405-416) used for the MLB ranking pass is a linear bound-interpolation, not a copula — its documented 15-20% relative error is acceptable for ranking only, which is how it's used.

**2. Monte Carlo precision — n=300+CRN is sound for ranking; the marginal precision issue is actually in the SIZING pass's Gate 2, not the ranking pass.**

(a) **CRN analysis.** The fixed seed=42 makes every candidate slip's estimate use the same ε-draw sequence — textbook common random numbers, a proven variance-reduction technique for selecting the best of several simulated alternatives (Nelson & Matejcik 1995, *Management Science*; Chick & Inoue 2001; Glasserman & Yao 1992). Var(p̂_A − p̂_B) = Var(p̂_A) + Var(p̂_B) − 2Cov(p̂_A, p̂_B); for candidate slips sharing legs and similar ρ structure, the indicator outcomes are highly positively correlated under common draws, so the SE of the *difference* is far below the naive √2·2.65pp ≈ 3.7pp. A verified implementation detail makes CRN actually work here: `eps` is fully drawn *before* the early-exit leg loop (line 392, break at 397-399), so the random stream stays synchronized across candidates with the same leg count. Also the copula term carries only 0.30 weight in `_score_sgp` (line 704), further diluting MC noise in the final ranking.

(b) **Fixed-seed concern.** Legitimate but second-order: seed=42 means one specific 300-draw set is used permanently, so any "luck" in that draw set is a *systematic level bias* (bounded by ~±2σ ≈ ±5pp worst case on the level) rather than per-run noise. For ranking this mostly cancels; it cannot average out across days the way per-run random seeds would, which is the one theoretical demerit. **Recommendation:** n=300+CRN is defensible as-is, but since 4000 samples costs ~2ms, raising the ranking pass to n=2000 shrinks both the level bias and difference-SE ~2.6× at negligible cost.

(c) **The real precision gap is Gate 2 of sizing** (line 747): the correlation-lift check requires `copula_joint − no_vig_independent ≥ 0.015`, but at n=4000 the MC SE is ≈0.72pp — the threshold is only ~2.1 SEs from zero, and a slip whose true lift is exactly 1.5pp is misclassified ~50% of the time (the band of ambiguity ±1.4pp is as wide as the threshold itself). The 10pp Gate 1 is fine at this SE (≈14 SEs). **Recommendation:** for the one-shot sizing decision on the final slip, either raise to n=50,000 (~25ms, SE→0.2pp) or — since n≤4 legs — compute the Gaussian-copula orthant probability deterministically (bivariate/trivariate normal CDF), eliminating MC error entirely. This affects only the 0.25u-vs-0.50u step, a bounded-cost error.

**3. Conservative copula vs book correlation premium — the design is coherent, and the asymmetry runs in the safe direction.**

The ρ floor means the engine's copula joint *understates* the true joint for positively-correlated legs, making `copula_ev_margin` a lower bound on true EV — conservative, correct direction. Published industry data confirms books extract a large correlation-aware premium: parlay hold runs ~20-31% and SGP hold frequently 20-30%+ vs 4-5% on straights (Legal Sports Report; How Gambling Works; SportsBoom; BettorEdge). Books reprice correlated combinations (the "correlation tax") using their own copula/empirical models — a granted US patent (USPTO 12,080,130, "Sportsbook odds optimization and correlated proposition bet analysis") confirms this is productionized. So the engine needs a large true edge to clear SGP pricing, and the +10pp gate is sized to that reality (arithmetic in Q4). One additional conservatism stacking in the same direction: per CLAUDE.md, the NBA-prop Platt map over-corrects SGP leg probs (model 58% vs 69% actual at n=52) — if leg fair_probs are understated, the copula joint and hence the margin are understated further. Three stacked conservatisms (ρ floor, leg-prob understatement, 10pp gate) mean the 0.50u premium tier fires only on genuinely strong slips, at the cost of some missed premium sizings — an acceptable trade for a 0.25u/0.50u product.

**4. Threshold calibration — theoretical/heuristic, not empirical, and the order of magnitude checks out.**

Provenance: the code explicitly states "Thresholds are starting points — tune against CLV/W-L data over 50+ builds" (sgp_builder.py:725) — consistent with DATA_GATED. Arithmetic check against Q3's hold data: a hold of *h* on a slip at decimal odds *d* means p_true = (1−h)/d. For a 30%-implied slip (d ≈ 3.33): at 20% hold, p_true = 0.240 → the book's pricing buffer is ≈ 6.0pp of joint probability below implied; at 30% hold, p_true = 0.210 → 9.0pp. The gate requires modeled joint ≥ implied + 10pp = 0.40, i.e., modeled EV ≈ +33% — it demands the model beat the implied line by more than the entire typical SGP hold gap (6-9pp), with the copula estimate itself floor-biased. That is the right order of magnitude: large enough to absorb model error and the correlation premium, small enough to be reachable. cohesion≥0.55 and avg_edge≥0.035 are heuristic guards — neither is load-bearing for EV; they gate against spurious copula uplift, which is reasonable belt-and-suspenders. **Assessment: 10pp is correctly calibrated in order of magnitude; defer numeric tuning to the 100-scored-slip gate.**

### Sources
- McHale, I. & Scarf, P. (2007), "Modelling soccer matches using bivariate discrete distributions with general dependence structure," *Statistica Neerlandica*. https://onlinelibrary.wiley.com/doi/abs/10.1111/j.1467-9574.2007.00368.x
- McHale, I. & Scarf, P. (2011), "Modelling the dependence of goals scored by opposing teams in international soccer matches," *Statistical Modelling*. https://journals.sagepub.com/doi/10.1177/1471082X1001100303
- Wizard of Odds, "Same-Game Parlays: The Mathematics of Correlation." https://wizardofodds.com/article/same-game-parlays-the-mathematics-of-correlation/
- OddsIndex, "Same Game Parlay Correlation: How the Hidden Tax on SGPs Really Works." https://oddsindex.com/guides/same-game-parlay-correlation
- Legal Sports Report, "Kalshi Parlay Volume Surges…" (parlay hold ~20-30% vs ~4-5% straights). https://www.legalsportsreport.com/258357/
- How Gambling Works, "Understanding Parlays" (avg parlay hold ≈31%); SportsBoom, "How Sportsbooks Doubled Their Take"; BettorEdge, "How Sportsbooks Profit Off Parlays"
- USPTO Patent 12,080,130, "Sportsbook odds optimization and correlated proposition bet analysis."
- Nelson, B. & Matejcik, F. (1995), "Using Common Random Numbers for Indifference-Zone Selection and Multiple Comparisons in Simulation," *Management Science*; Chick & Inoue (2001); Glasserman & Yao (1992), *Management Science*
- Computed example: 2M-sample Monte Carlo, this audit (Gaussian/Frank/Clayton/survival-Clayton/t₅, Kendall-τ matched)
- Implementation verified read-only: `engine/sgp_builder.py` (lines 253-416, 654-749), `engine/mlb_sgp_builder.py` (lines 179-313)

---

## SECTION 11 — PICK_SCORE Formula
**VERDICT:** CONFIRMED_WITH_CAVEAT
**CLASSIFICATION:** PERIODIC_RECAL
**Condition to revisit:** Re-evaluate tier multipliers at the existing n=30 post-gate T1 checkpoint, and add an e_n cap (or shrinkage) the first time an edge >15% pick reaches the card; re-derive weights if odds composition shifts away from near-even prop pricing.

### Findings

**Code verification (preliminary).** All claims check out against `engine/run_picks.py`: `e_n` has no min/max clamp (line 1053 — the "ceiling" is purely the /15 denominator); scores are computed only for gate-surviving picks — props gate-fail and `continue` at lines 2628–2631 before scoring at 2651, game lines require `passed and edge >= 0.05` at line 2744, and line 3551 sets `pick_score = ... if passed else None`. So G13 (prob ≥ 0.50) guarantees wp_n ≥ 0 on every scored prop; negative wp_n is unreachable in practice. One adjacent finding: a `[LARGE-EDGE]` warning fires at adj_edge ≥ 0.15 (line 2654) but is log-only — it does not dampen the score. Fresh tier empirics from `data/pick_log.csv` (primary+bonus, graded): **T1 27/58 = 46.6%, T1B 23/49 = 46.9%, T2 44/73 = 60.3%, T3 17/33 = 51.5%, KILLSHOT 3/5**.

**1. Is 40/60 WP/edge weighting defensible? Yes — and over the realized book it is nearly inert, which is itself the strongest defense.**

With decimal odds d and model probability p, EV per unit = p·d − 1. Writing edge = p − p_nv with fair p_nv = 1/d gives **EV = d·edge** — linear in edge at fixed odds. Kelly: **f* = d·edge/(d − 1)** — also linear in edge at fixed odds. So edge-dominant weighting is directionally consistent with both EV and Kelly ranking.

The key structural observation: **at fixed odds, wp and edge are affinely related** (edge = wp − p_nv), so the two score terms are collinear and any positive weight split produces the identical ranking. For a typical −110/−115 prop, p_nv ≈ 0.50, so wp_n = 400·edge and e_n = 666.7·edge, giving score = **560·edge** — for near-even-odds props (the bulk of the book) the composite *is* pure edge ranking. The 40/60 split only matters across odds levels.

Worked example: Pick A (p=0.55, edge=0.20 → d=2.857): score=88.0, f*=0.308, EV=0.571. Pick B (p=0.70, edge=0.05 → d=1.538): score=52.0, f*=0.143, EV=0.077. Score, f*, and EV all rank A > B — **orderings agree.** Where they diverge: same edge, different odds. Pick C (p=0.52, edge=0.08, +150): score=35.2, f*=0.133, EV=0.200. Pick D (p=0.66, edge=0.08, −180): score=57.6, f*=0.224, EV=0.124. Raw EV ranks C > D; **Kelly and the score both rank D > C**. The wp term thus implements a Kelly-style variance tilt — at equal edge, shorter odds support larger stakes and lower variance. A Sharpe-style ranking EV/σ = edge/√(pq) is nearly pure edge for p ∈ [0.5, 0.7], so the score sits between Sharpe and Kelly — defensible. A theoretically cleaner alternative exists and is already in the codebase: **rank by `kelly_units()` directly** (line 1061), which would unify ranking with sizing. But since score drives only card selection and tier gates, the composite is an acceptable monotone proxy.

**2. WP normalization: affine, ranking-neutral within wp; effective weight depends on framing — full-range gives ~31/69, realized spreads give ~41/59.**

The linear map (50→0, 75→100) is affine, so it cannot distort ranking within the wp dimension — only the relative scale vs e_n matters. Two framings: *full theoretical ranges* (Platt ceiling 0.666 caps wp_n at ~66; e_n reaches 100 at edge=0.15): effective weights → **30.6% / 69.4%**. *Realized spreads* (wp ∈ [0.52, 0.64] → Δwp_n = 48; edge ∈ [0.05, 0.12] → Δe_n = 46.7): 19.2 vs 28.0 → **40.7% / 59.3%** — almost exactly nominal. Over the picks that actually compete for card slots, the nominal weighting approximately holds. Combined with the collinearity in Finding 1, no material distortion.

**3. Uncapped e_n is the formula's weakest point — extreme edges should attract suspicion, not score.**

Verified: edge=0.20 → e_n=133.3 → contributes 80 points (vs 60 at the nominal ceiling); the "p90 cap" intent was *not* achieved — normalization alone caps nothing. The problem is adverse selection at the top of the card. The closing line at sharp books is the best available estimate of true probability, and skilled bettors beat it by low single digits (Pinnacle CLV resources; Buchdahl, *Wisdom of the Crowd* — de-vigged sharp odds are a near-unbiased estimate of true probabilities). A model claiming 15–20% probability edge over the no-vig market in a liquid market is, with overwhelming prior probability, observing a stale line, a scratched player still in the projection, or a data error — practitioner guidance is explicit that an edge that looks too big means model error (Snowberg & Wolfers 2010, *JPE*: even persistent biases like favorite-longshot are worth ~2–5%, not 20%). This is the optimizer's curse in pure form: ranking by noisy estimated value guarantees the top-ranked items are the most over-estimated (Smith & Winkler 2006, *Management Science*) — and an uncapped linear e_n maximally rewards exactly the picks most likely to be errors. The existing `[LARGE-EDGE]` warning shows the right instinct but has no teeth. **Recommendation:** clamp `e_n = min(e_n, 100)` (flat above 15%) at minimum; better, shrink score-edge toward 15% above the threshold (e.g., 0.15 + 0.3×(edge−0.15)). A hard cap loses no legitimate ranking information because legitimate 20%+ edges essentially don't exist in these markets; it only de-ranks probable errors. Note KELLY_MARKET_MULT and SPORT_UNIT_CAP limit *sizing* damage but do nothing about *card selection* — the score is the only promotion mechanism, so this is where the fix belongs.

**4. Tier multipliers: magnitudes proportionate to borderline evidence; the mechanism is a patch on a stale taxonomy.**

(a) Significance: T1 46.6% (n=58) vs T2 60.3% (n=73). Pooled p̂ = 0.542; SE = 0.0876; z = **1.57, two-sided p ≈ 0.12** — *not* significant at 5%. Given that, a 0.90× multiplier (≈ −5 to −6 points on a typical T1 score) is a proportionate, conservative response: large enough to break ties toward T2, small enough not to act as if a 14pp gap were proven.

(b) The deeper problem: T1 stats were *selected* as historically best, so regression toward the mean predicted part of the observed decline mechanically (Smith & Winkler 2006; regression-to-mean in sports selection). The multiplier therefore partially encodes a transient selection artifact as a permanent dampener. Two mechanism criticisms: the multiplier is applied to the *whole* score, conflating "tier reliability" with edge magnitude; and the resulting ordering T1 (0.90) < T1B (0.93) < T3 (0.95) < T2 (1.00) *inverts* the tier system's own conviction ordering — prima facie evidence the tier definitions, not the scores, are stale. The right long-term mechanism is per-tier win_prob recalibration or tier redefinition, with the multiplier as a stopgap — the existing n=30 post-gate re-evaluation checkpoint is the correct governance. Note T1B at 46.9% (n=49) now tracks T1, suggesting 0.93 may be too generous at the next checkpoint.

**5. Cold-start penalties: heuristics, but theoretically sound ones — crude shrinkage against the optimizer's curse.**

Not calibrated (cold-start picks too rare for per-subtype WR), but defensible: cold-start projections carry the highest estimation variance in the system, and Smith & Winkler's prescription for selection under heterogeneous estimate noise is precisely to discount estimates in proportion to their unreliability before choosing. A flat −15 for taxi (zero career games) down to −5 for new_acquisition is a monotone reliability ordering consistent with that logic. Magnitude: −15 ≈ a 1.5–2 card-slot demotion — strong but arguably correct for a projection with no NBA data. Two upgrades: (i) the *principled* implementation is to inflate σ for cold-start subtypes so win_prob, edge, gates, and Kelly all shrink coherently — not just ranking; (ii) to calibrate, the subtype must be observable in graded data — currently `cold_start_subtype` is written only by `log_candidates()` to `pick_log_candidates.csv`, **which does not exist on disk**, and is absent from the 29-column main schema. Until it is persisted and joined to results/CLV at n≥30 per subtype, these stay heuristic by construction.

**6. Injury bonus mechanism: a deliberate bet on unmeasured edge — coherent as ranking-only speculation, but currently unvalidatable.**

The +7..10 score points promote picks whose *measured* edge does not yet include the injury repricing, betting that books lag the news. (i) Confining the speculation to ranking (score never sizes) is a genuinely good design property — the speculative signal can promote a pick onto the card but cannot inflate its stake, gate passage, or win_prob; (ii) the cost is real: card slots are finite, so a +10 bump can displace a pick with ~1.5–2% more *measured* edge (10 points / 560 points-per-edge-unit from Finding 1) — the bonus implicitly asserts the unmeasured injury edge exceeds that; (iii) the premise is supported: prop markets demonstrably reprice news more slowly than sides, and the engine's own `SLOW_BOOKS` constant (15–40 min lag) encodes the same belief; (iv) validation: the textbook metric for timing-based unmeasured edge is CLV — per Buchdahl/Pinnacle, CLV reaches significance in as few as ~50 bets. **Blocking defect:** `injury_trigger` is not in the main pick_log schema (v4, 29 cols) and the candidates log it does write to doesn't exist on disk — so CLV-on-injury-trigger cannot currently be computed. Add the flag to the main log (schema v5) or activate the candidates log, then gate the bonus's continuation on mean CLV > 0 at n≥50 injury-trigger picks. Until then the AST 10 / PTS 8 / SOG 8 / REB 7 ordering and the mechanism itself remain unfalsifiable, consistent with Section 4's INSUFFICIENT_DATA on the ordering.

### Sources
- Smith & Winkler (2006), "The Optimizer's Curse: Skepticism and Postdecision Surprise in Decision Analysis," *Management Science* 52(3). https://pubsonline.informs.org/doi/10.1287/mnsc.1050.0451
- Snowberg & Wolfers (2010), "Explaining the Favorite-Longshot Bias: Is it Risk-Love or Misperceptions?", *Journal of Political Economy* 118(4). https://www.journals.uchicago.edu/doi/abs/10.1086/655844
- Buchdahl, "Using the Wisdom of the Crowd to Find Value in a Football Match Betting Market." https://www.football-data.co.uk/The_Wisdom_of_the_Crowd_updated.pdf
- Pinnacle, "What is Closing Line Value (CLV) in Sports Betting?" https://www.pinnacle.com/betting-resources/en/educational/what-is-closing-line-value-clv-in-sports-betting
- Kelly criterion — Wikipedia (f* formula); RebelBetting Kelly staking guide
- "A statistical theory of optimal decision-making in sports betting" (PLOS/PMC, 2023). https://pmc.ncbi.nlm.nih.gov/articles/PMC10306238/
- Regression toward the mean — Wikipedia (sports selection examples)
- Bookmakers Review (NBA prop market structure); BettorEdge ("Top 5 Ways Player Injuries Affect NBA Betting Lines"); Sportsbook Review handicapper forum (oversized edges signal model error)

---

## SECTION 12 — EWMA, FG3M Bias, and Projection Methodology

**VERDICT:** NEEDS_CHANGE (one structural defect in the FG3M path; rest model and scalars are CONFIRMED_WITH_CAVEAT)
**CLASSIFICATION:**
- 3P% Bayesian padding (`PAD_3P=750` on 30-game window): **NEEDS_CHANGE**
- `FG3M_BLEND_ALPHA=0.60`: **PERIODIC_RECAL** (re-run grid only after padding fix)
- Days-rest model (0.10 / 1.5 / role scalars): **PERIODIC_RECAL** (plus a documentation fix)
- `REGULAR_SEASON_STAT_SCALAR`: **PERIODIC_RECAL** (add Mincer–Zarnowitz diagnostic before next refit)
- `PLAYOFF_RATE_DEFLATORS` BLK component: **DATA_GATED** (already gated on C01 per project memory)

**Condition to revisit:** Re-run the FG3M grid search and bias measurement after changing the 3P% padding denominator from the ≤30-game window to career-to-date 3PA (and/or reducing the pad toward ~250); if the −0.26 bias does not collapse, decompose bias per blend path before touching any other constant.

> **Audit-coordinator verification (2026-06-05):** confirmed at EdgeModel nba_projector.py:904-907 — the docstring states `stabilised_3p = (career_3PM + 750·LG_3P)/(career_3PA + 750)` but "We approximate career volume with the full df window (up to 30 games)." The 750-pad-on-30-game-window mechanism is real.

### Findings

**1. FG3M structural bias: the engine already shrinks 3P% — but it misapplies the shrinkage in two compounding ways. This, not the blend alpha, is the actionable defect.**

The hypothesized mechanism (noisy 3P% multiplied through FGA × 3PA-rate × 3P%) is real and well-documented, and shrinkage is the canonical fix — Darryl Blackport's stabilization work (Nylon Calculus 2014) found 3P% needs ~750 attempts to "stabilize," and empirical-Bayes shrinkage à la Efron–Morris (JASA 1975) is the standard formalization. But code inspection (`compute_shooting_rates()`, lines 953–957) shows shrinkage is **already implemented**: `fg3_pct = (total_fg3m + 750×0.360) / (total_fg3a + 750)`. The defects:

- **Defect A — wrong denominator.** The docstring says "We approximate career volume with the full df window (up to 30 games)." Blackport's 750 is a career/season-scale threshold; applying a 750-attempt pad against a 30-game window over-shrinks everyone. Math for a high-volume shooter (8 3PA/game, 240 window attempts, true 40%): padded p̂ = (240×0.40 + 750×0.36)/990 = 0.3697, a −0.030/attempt error → **−0.24 makes/game** on the FGA path. For an elite 10-3PA/40% shooter: −0.32/game. The reported −0.26 persistent bias is quantitatively consistent with this mechanism almost exactly. Symmetrically, a low-volume 28% shooter (60 attempts) is pulled up to 0.354 — the "over-projection of rare shooters" pathology. Both halves of the observed bias fall out of one parameter misuse.
- **Defect B — wrong pad magnitude even conceptually.** A stabilization point (split-half reliability = 0.5) is **not** the optimal Bayesian prior weight. Medvedovsky (2020) — the very source the docstring cites — ran differential-evolution optimization of the pad for rest-of-season prediction and found the optimal 3P% pad is **242 attempts, not 750**, noting "only 7 players have ever taken more than 750 three point attempts in an entire season." The code cites Medvedovsky but uses Blackport's number.

Fix: pad with ~242–300 against **career-to-date 3PA** (multi-season totals from projections.db), or if the 30-game window must be kept, scale the pad down proportionally (~100–150). One caveat the grid search raises: if bias was truly flat at −0.26 across α ∈ [0.25, 0.65], the per-minute baseline path must also be biased low on that eval sample (a pure FGA-path defect predicts bias ≈ α × path-bias). Either the eval sample conditions on volume shooters, or a shared factor (proj_min, EWMA lag on fg3a_rate in a league with rising 3PA rates) contributes. **Required diagnostic before deploying the fix: report bias of `proj_fg3m_fga` and `baseline_fg3m` separately on the same eval set.** Also note an internal inconsistency that must be reconciled: the REGULAR_SEASON_STAT_SCALAR comment records post-scalar fg3m bias of **−0.005 on mean 1.336** (30-date backtest, 4,653 player-games) while the grid search reports **−0.26** (n=2000) — a 50× discrepancy that can only mean different eval populations or pipelines.

**2. Flat 0.60/0.40 blend is defensible; regime-conditional weighting is not justified by the evidence at hand.**

The forecast-combination literature since Bates & Granger (1969) consistently finds that simple fixed weights beat estimated "optimal" or regime-dependent weights out of sample — the "forecast combination puzzle" (Stock & Watson 2004), theoretically explained by Claeskens et al. (2016, *IJF*): weight-estimation error typically exceeds the gain from non-equal weights. A player-type-conditional alpha would be estimated on small per-bucket samples and is exactly the construction the puzzle warns against. Moreover, with the MAE curve flat across 0.25–0.65 (range 0.004), the alpha choice is empirically near-irrelevant — combination gains require the two forecasts to have **diverse errors**, and here both paths share inputs and, per the flat bias, share the same low bias. Honest assessment: **0.60 is fine, the question is moot, and the energy belongs in Q1's shrinkage fix.** Re-run the grid after that fix.

**3. The 10% max B2B minutes reduction is high versus published evidence in isolation — but the net implemented effect is smaller than it looks because of an interaction with the minutes scalar.**

Published B2B effects: teams on zero days' rest win ~2–4% less often and score ~0.5–1 point worse; Esteves et al. (2021, *EJSS*) confirms second-night-of-B2B as a robust performance disadvantage but of modest size. Efficiency effects are ~1–3%, not 10%. The minutes channel is the right one to model in the load-management era — star instances of playing one game of a B2B but not the other nearly doubled 2017-18→2022-23 (47→88, Sportico) — but that is mostly a **binary DNP decision**, which the engine handles separately via injury/lineup logic; the conditional-on-playing minutes reduction is much smaller than 10%. The code comment's claim of "~8–12% minutes reduction across all roles" cites no source and none was found. However, the **net** effect is moderated by `REGULAR_SEASON_MINUTES_SCALAR`: because the rest function is penalty-only (factor < 1 at every rest value, ≈0.949 at the modal 1-day rest for starters), it depresses mean minutes by ~4–5%, which the minutes scalar (overall ratio 1.0365) then re-inflates. Net for a starter: B2B → 0.900×1.0667 = 0.960; 1-day → 1.012; 3-day → 1.053. So the **implemented B2B-vs-modal-rest gap is ~−5%**, not −10% — closer to evidence but still above the ~1–3% published range, and the two constants are entangled: refitting one silently invalidates the other. Recommendation: refit empirically by regressing minutes residuals on days_rest in the existing 4,653-game backtest (zero-centered at modal rest), then refit the minutes scalar afterward, not jointly-by-accident.

**4. Decay shape is roughly consistent with recovery physiology; the naming/documentation bug is confirmed and should be fixed for the record.**

Sports-science evidence: post-match neuromuscular impairment is greatest in the first 24h and resolves over 24–72h, with most performance markers back at baseline by 24–48h. The implemented curve — 51% of max effect at 1 day, 26% at 2, 14% at 3 — is directionally consistent, though slightly slower-tailed than physiology suggests; at a 10%×role ceiling these residuals are ≤2.6% of minutes, i.e., minor. **Naming bug, for the record:** `DAYS_REST_HALF_LIFE = 1.5` is used as an *e-folding time* (`exp(-d/1.5)`); the true half-life of this curve is 1.5·ln2 ≈ **1.04 days**. The docstring claim "At days_rest=1.5: reduction ≈ max_reduction × role_scalar / 2" is wrong on the code's own math — at d=1.5 the multiplier is e⁻¹ ≈ 0.368, not 0.5. Behavior is unaffected (calibration was done on the actual curve), but rename to `DAYS_REST_EFOLD_DAYS` or change the formula to `exp(-d·ln2/1.5)` — pick one, document which, and never both.

**5. Multiplicative form is correct for these count stats; the missing piece is the standard slope/intercept diagnostic.**

For volume-driven count stats where errors scale with the projection level, a ratio (multiplicative) correction — equivalent to a regression-through-origin slope correction y = b·ŷ — is standard practice; the general forecast-recalibration form is the Mincer–Zarnowitz regression actual = a + b·projected, which nests both additive (a) and multiplicative (b) corrections, with optimality tested as the joint null a=0, b=1 (Mincer & Zarnowitz 1969). The implemented `scalar = (mean_proj − bias)/mean_proj` matches means by construction and is the right default for proportional bias. **The real risk:** a single ratio scalar assumes bias is uniform in relative terms across the projection range. Q1 demonstrates it is not for fg3m — bias is concentrated in high-projection (volume-shooter) rows and reversed in low-projection rows, so the global scalar (1.0231) over-corrects non-shooters and under-corrects stars while leaving the mean ≈ 0 (which is why the 30-date backtest shows −0.005 residual while the grid search shows −0.26 on its sample). Note also the scalars **compound across refits** (v3 comments record residual bias *after* the v2 scalar) — fine, but must be remembered at refit time. Recommendation: at the next recalibration, fit the MZ regression per stat, test (a, b) = (0, 1), and inspect bias by projection decile; deploy a two-parameter (a + b·ŷ) correction only for stats where the intercept is materially nonzero, otherwise keep the ratio form.

### Sources
- Medvedovsky — "NBA Stabilization Rates and the Padding Approach" (2020). https://kmedved.com/2020/08/06/nba-stabilization-rates-and-the-padding-approach/ — optimal 3P% pad = 242 attempts
- Nylon Calculus / FanSided — Bayesian Analysis of 3PT Shooting (Blackport's 750-attempt stabilization). https://fansided.com/2015/12/18/freelance-friday-bayesian-analysis-of-3pt-shooting/
- Counting the Baskets — Blackport (2014). https://counting-the-baskets.typepad.com/my-blog/2014/09/prediction-are-hard-especially-about-three-point-shooting.html
- Efron & Morris (1975), "Data Analysis Using Stein's Estimator and Its Generalizations," *JASA* 70:311–319
- Claeskens et al. (2016) — "The forecast combination puzzle: a simple theoretical explanation," *Int. J. Forecasting*; Bates & Granger (1969)
- Esteves et al. (2021) — "Basketball performance is affected by the schedule congestion: NBA back-to-backs under the microscope," *Eur. J. Sport Science* 21(1)
- Teramoto et al. — "Game injuries in relation to game schedules in the NBA," *J. Sci. Med. Sport*; Mack et al. rebuttal
- Manner (2016) — "Modeling and forecasting the outcomes of NBA basketball games," *JQAS* 12(1):31–41
- The Data Jocks; PlayDecoded — B2B penalty magnitude (~0.5–1 pt, ~4% win-prob)
- Sportico — NBA load-management policy data; NBA.com load-management study
- Science for Sport — post-match recovery timelines; PMC — knee-extensor fatigue after simulated basketball match-play
- Mincer & Zarnowitz (1969), "The Evaluation of Economic Forecasts," NBER
- Code verified read-only: `EdgeModel/engine/nba_projector.py` (lines 206–223, 302–318, 890–970 incl. PAD_3P=750, 1027–1045, 1425–1442, 1540–1554); independently re-verified by audit coordinator (docstring lines 904–907)

---

## SECTION 13 — KILLSHOT Thresholds

**VERDICT:** NEEDS_CHANGE
**CLASSIFICATION:** PERIODIC_RECAL
**Condition to revisit:** Re-derive the full gate whenever any upstream constant it implicitly depends on changes (Platt A/B at H3, PICK_SCORE_TIER_MULT at the T1 n=30 checkpoint, or any stat suspension/unsuspension) — the gate is a composite of five conditions whose joint feasible region currently collapses to nearly a single stat-direction.

> **Audit-coordinator verification (2026-06-05):** the dead-combination claim is confirmed from the ground-truth pass: `KILLSHOT_STAT_ALLOW = {PTS, AST, SOG}` (run_picks.py:211), but PTS is in T2's stat set (line 587) while `KILLSHOT_TIER_REQUIRED="T1"` is strict — PTS can never qualify. SOG is fully suspended (G_SOG_SUSPENDED, line 1180). Only NBA AST can currently fire.

### Findings

**1. Score≥65 coherence — the math checks out, and it demands an edge size the engine's own calibration data says is over-stated.**

Verified against `engine/run_picks.py:1051-1055`: at the wp floor 0.65: wp_n = 60, so 0.90·(24 + 0.60·e_n) ≥ 65 → e_n ≥ 80.4 → **edge ≥ 12.06%**. (With the +7 injury bonus, edge ≥ 10.11%.) So KILLSHOT structurally requires a ~10–12% edge against a vigged prop line — i.e., the model claiming the market is mispriced by 10+ percentage points on a mainline NBA prop.

The "too good to be true" principle says exactly this region is where model error concentrates (winner's-curse mechanism — extreme estimates are extreme partly *because* they contain extreme errors; cf. Green, Lee & Rothschild's "Favorite-Longshot Midas"). The engine's **own ledger confirms the over-statement**: edge bucket 12%+ runs 57.3% actual vs 66.3% predicted (n=110, −9.0pp calibration deficit), while 8–12% runs 52.8% vs 55.9% (−3.1pp). Score buckets are starker: 60–75 → 61.0% WR, but 75–90 → 54.5% WR vs 70.3% predicted (−15.8pp), and the predicted-70%+ probability bucket actualizes at 55.1% (n=49). The 5 historical KILLSHOTs themselves: predicted 74.4% → actual 60.0% (3-2, n=5). So the empirically best-calibrated, best-performing region is the *moderate* score/probability band (score 60–75, predicted 65–70% → actual 66.7%), and the gate is tuned to select from *above* it. The 12%+ bucket is still the highest raw WR among edge bands (57.3%), so the floor isn't catastrophic — but it selects maximal miscalibration, which is the wrong property for a "highest-conviction" product. **Caveat:** the floor partly *protects* against the −EV window in Finding 4, so it should not be lowered in isolation.

**2. Stat allowlist — confirmed dead combinations; the gate de facto allows one stat, one direction.**

- **PTS is T2** (line 587) → PTS ∧ tier=T1-strict is **logically unsatisfiable**. Dead allowlist entry. (The code comment at line 211 even flags 3PM as "dead code" for the identical reason — the same defect was reintroduced with PTS and not flagged.)
- **SOG**: G_SOG_SUSPENDED (2026-06-05) → dead until the July refit.
- **REC**: T1-eligible but not in the allowlist and NFL isn't live; **HRR**: T1-eligible, not in allowlist, shadow-only.
- Remaining: **NBA AST only** (WNBA is shadow-logged, no KILLSHOT path). And within AST: overs need wp ∈ [0.65, 0.6657] (Platt over-cap) — a 1.6pp window — while G8B blocks AST overs at lines ≤4.5; unders get wp ∈ [0.65, 0.6922]. So the published intent "mainline counting stats only" is in practice **NBA AST, mostly unders**. Consistent with the log: zero KILLSHOTs have fired since 2026-05-01 (5+ weeks), and 3 of the 5 that ever fired used stats since removed from the allowlist (3PM ×2, REB ×1).

This is a textbook rule-base anomaly: in the Preece & Shinghal knowledge-base-verification taxonomy these are "unfirable rules" / "unsatisfiable conditions" — conjunctive gates whose clauses individually look reasonable but jointly have an empty (or near-empty) satisfaction set, undetectable by inspecting any clause alone. The fix is not to delete KILLSHOT but to make the gate's feasible region explicit: either (a) drop `KILLSHOT_TIER_REQUIRED` and select on the floors alone (see Finding 3), or (b) keep a stat allowlist but assert at startup that every allowlisted stat is tier-eligible and unsuspended (a one-line invariant that would have caught both PTS and the 3PM predecessor).

**3. T1-strict is internally contradictory — the engine penalizes T1 in scoring while requiring T1 for its premium product.**

Current empirics (305 graded picks): **T1 = 27-31 (46.6%, −10.2% ROI, n=58)** vs **T2 = 44-31 (58.7%, +9.3% ROI, n=75)**. Two-proportion test: diff = 12.1pp, z ≈ 1.4, p ≈ 0.16 — not statistically significant. The steelman partially holds: T1's record includes pre-G8B AST-over picks (AST over: 2-6, −59.5% ROI) and pre-suspension SOG unders (20-21), so post-fix conditional T1 may be better (AST under is 5-2, 71.4%). The conditional cell T1∩score≥65∩wp≥0.65 has fired ~5 times ever, so it's unanswerable directly. CLV adds a non-WR signal: T1 beat-the-close rate is **5%** (n=20), worst of all tiers.

But even granting the steelman, the structure is incoherent: `PICK_SCORE_TIER_MULT["T1"] = 0.90` exists *because* T1 empirically underperforms T2 (the code comment at line 626 says so explicitly). The engine simultaneously asserts "T1 is worse than T2" (scoring) and "only T1 qualifies for the highest-conviction tier" (KILLSHOT). Decision-theoretically, if `win_prob` is calibrated it is the sufficient statistic for the win event — DeGroot & Fienberg (1983) formalize this: a calibrated, more-refined forecast dominates, and categorical covariates (tier) should matter only insofar as they predict *residual miscalibration*, which is exactly what a tier-conditional calibration adjustment (the score multiplier) already does. Conditioning the gate on category membership *on top of* the floors double-counts tier — in the wrong direction. **Recommendation:** select on floors (score, calibrated wp, edge, odds) with tier entering only through the score multiplier it already has.

**4. Odds window arithmetic — verified; the −EV window exists but is currently unreachable for calibrated props, and is live for manual promotes.**

Breakeven at American odds −X is p_be = X/(X+100). At −200: p_be = 0.6667. The wp floor 0.65 equals breakeven at **−185.7**. So for odds in (−186, −200], a pick at the wp floor is −EV: at −200/wp=0.65, EV = **−2.5%** per unit. Worse, the Platt over-cap is 0.6657 < 0.6667 — even a maximum-confidence calibrated over is −EV at −200; the under cap (0.6922) clears it by only 2.5pp.

However, the **joint** gate analysis shows the score floor closes this window for Platt-calibrated props: at the over cap, score≥65 requires edge ≥ 11.80% → implied ≤ 0.5477 → odds no shorter than ≈ **−121**. For unders: ≈ **−143**. Even with the +7 injury bonus, the binding boundary is ≈ −131 / −155 — all north of −186. So no Platt-calibrated prop can currently fire in the −EV zone. The trap is **latent, not dead**: it becomes live via (a) the **manual override path** — run_picks.py:5935-5936 checks *only* `score ≥ KILLSHOT_MANUAL_FLOOR (75)`, bypassing the wp and odds gates entirely, so a manual promote at −200 is unprotected; (b) any H3 Platt refit that raises the cap; (c) any Platt-exempt stat (MLB) ever entering the allowlist. **Recommendation:** tighten `KILLSHOT_ODDS_MIN` to −185, or better, replace the static wp floor with an odds-dependent one: `wp ≥ p_be(odds) + 0.03`. One line, removes the latent −EV admission under every future parameter regime, including manual.

**5. Weekly cap = 2 — product-sound in principle, currently irrelevant in practice.**

The alert-fatigue canon supports scarcity for a premium @everyone-ping product: clinical decision-support literature finds alert override rates of 49–96% and that each additional alert per encounter drops acceptance of *any* alert by ~30% (Ancker et al. 2017; McCoy et al.) — high-frequency alerts destroy the channel's signal value. So cap=2/week is directionally right for the brand. But the empirics show the cap is not the binding constraint: 5 KILLSHOTs in ~7.5 weeks, **all between Apr 15 and May 1** (pre-Platt-cap era, logged wp 0.73–0.76 — values now mathematically unreachable), and **zero since**. Note also the 4u bump (wp≥0.70) is dead code for calibrated props (cap 0.6922 < 0.70): every future KILLSHOT is 3u. **Data to answer it:** the count of qualifying-but-capped picks — currently uncollectable, because KILLSHOT gate failures are printed to console but not logged. Add a `killshot_qualified` count per run; if qualifiers exceed ~2/week after the gate is repaired per Findings 2–4, revisit the cap — until then it costs nothing.

**Summary of recommended changes:** (i) drop the T1-strict tier requirement, selecting on score/wp/edge floors with tier handled by the existing score multiplier; (ii) add a startup invariant that every `KILLSHOT_STAT_ALLOW` entry is tier-eligible and unsuspended; (iii) make the wp floor odds-dependent (`wp ≥ p_be(odds) + margin`) or set `KILLSHOT_ODDS_MIN = −185`, and apply it to the manual path; (iv) log KILLSHOT qualification/disqualification counts; (v) keep cap=2 and the score floor pending (iv)'s data, but recognize the floor selects the most-miscalibrated region of the model and consider pairing it with extra wp shrinkage rather than raising it.

### Sources

- Snowberg & Wolfers, "Explaining the Favorite-Longshot Bias: Is it Risk-Love or Misperceptions?" NBER WP 15923. https://www.nber.org/system/files/working_papers/w15923/w15923.pdf
- Green, Lee & Rothschild, "The Favorite-Longshot Midas," Wharton Jacobs Levy Center. https://jacobslevycenter.wharton.upenn.edu/wp-content/uploads/2018/08/The-Favorite-Longshot-Midas.pdf
- Preece & Shinghal, "Foundation and application of knowledge base verification," *Int. J. Intelligent Systems* (1994) — rule-base anomaly taxonomy: unfirable rules / unsatisfiable conjunctive conditions.
- DeGroot & Fienberg, "The Comparison and Evaluation of Forecasters," *JRSS-D* (1983) — calibration/refinement and sufficiency.
- Gneiting, Balabdaoui & Raftery, "Probabilistic forecasts, calibration and sharpness," *JRSS-B* (2007) — maximize sharpness *subject to* calibration.
- Ancker et al., "Effects of workload, work complexity, and repeated alerts on alert fatigue in a clinical decision support system," *BMC Med Inform Decis Mak* (2017). https://pmc.ncbi.nlm.nih.gov/articles/PMC5387195/
- McCoy et al., "Clinical Decision Support Alert Appropriateness" (PMC4052586) — alert override rates 49–96%.
- Engine internals verified directly: `engine/run_picks.py` lines 206-220, 582-591, 627-633, 1051-1058, 489-491 + 858-869, 5838-5859 + 5935-5936; empirics from `engine/analyze_picks.py` over `data/pick_log.csv` (305 graded picks, 2026-04-14 → 2026-06-04).

---

## SECTION 14 — WNBA-Specific Gates and Constants
**VERDICT:** NEEDS_CHANGE
**CLASSIFICATION:** DATA_GATED
**Condition to revisit:** Fix the dead-code floor and dampener mechanism now (no data needed); recalibrate the corrected EV-based floor and dampener magnitude when the WNBA go-live gate (100 graded picks, currently 0/100) is reached.

> **Audit-coordinator verification (2026-06-05):** the dead-code determination is confirmed against the ground-truth gate read: G9 (`edge < 0.05 → blocked`, run_picks.py:1234) has no WNBA carve-out and runs on every WNBA pick after G_WNBA_EDGE; with min dampener mult 0.80, the WNBA floor would need 0.05×mult < 0.035 (mult < 0.70) to ever bind — never true.

### Findings

**1. WNBA_EDGE_FLOOR=0.035 is dead code — confirmed by direct code trace. The "compensates for wider vig" rationale is not just moot, it is inverted.**

*Dead-code determination (priority finding).* G_WNBA_EDGE fires at line 1216 when `edge × mult < 0.035`, and the universal G9 fires at line 1234 when `edge < 0.05`. Both run on every WNBA pick. For G_WNBA_EDGE to ever change the pass/fail set relative to G9 alone, it would have to block a pick with raw edge ≥ 0.05, which requires `0.05 × mult < 0.035` → `mult < 0.70`. The minimum multiplier in WNBA_EARLY_SEASON_EDGE_MULT is 0.80. By phase:

| Season phase | mult | G_WNBA_EDGE threshold (0.035/mult) | G9 threshold | Binding |
|---|---|---|---|---|
| Days 4–14 | 0.80 | 0.04375 | 0.05 | **G9** |
| Days 15–21 | 0.90 | 0.0389 | 0.05 | **G9** |
| Day 22+ | 1.00 | 0.035 | 0.05 | **G9** |

G9 dominates in every phase. The 0.035 floor never alters which picks pass; its only observable effect is cosmetic — picks with `edge × mult < 0.035` get labeled `G_WNBA_EDGE` instead of `G9` in `pick_log_blocked.csv`. The real WNBA edge floor is 5%, identical to NHL/MLB and *below* NBA's G9B=7% — the exact opposite of what the line-466 comment claims.

*Correct vig arithmetic.* The engine's `edge` = model probability − no-vig fair probability, so vig enters through the price paid, not the edge measure. EV per unit at edge *e* on a fair-coin line:
- **−110** (b = 0.9091): EV = 1.9091e − 0.0455. Break-even e = **0.0238**.
- **−115** (b = 0.8696): EV = 1.8696e − 0.0652. Break-even e = **0.0349**.

At e = 0.05: EV = **+5.00%/unit at −110** vs **+2.83%/unit at −115** — a 43% EV haircut for the same probability edge. To match the net EV of a 5% edge at NBA vig, the WNBA floor would need to be e = (0.05 + 0.0652)/1.8696 = **0.0616 ≈ 6.2%** — *higher* than 5%, not lower. Notably, 0.035 ≈ the per-side vig at −115 (3.49pp), i.e., it was set at the *zero-EV* threshold — a zero-EV floor is not a betting threshold, and it never binds anyway.

*Conclusion: both (a) and (b).* (b) is the factual state — the 0.035 floor is dead code given G9. (a) is the correct fix — express the floor in **EV per unit** (e.g., require EV ≥ 0.05u), computed from the actual quoted odds already available at gate time. This automatically prices each book's real vig per pick instead of hard-coding an assumed −115, and it eliminates the entire class of "probability edge at heterogeneous prices" inconsistencies (cross-ref Section 5).

**2. Early-season dampener: direction supported, magnitude unvalidated, mechanism incoherent.**

*Mechanism reality (code trace).* The dampener has two code paths: (i) the G_WNBA_EDGE gate path — dead per Q1, so the dampener does **not** actually require 25% more raw edge to pass; and (ii) a live `pick_score` path at run_picks.py:2643–2651, where the dampened edge feeds scoring only. Win_prob is untouched, and Kelly sizing consumes win_prob + odds — so an early-season WNBA pick that passes is **ranked lower but sized at full confidence**. This is the same score-vs-sizing incoherence Section 4 found for cold starts. If the rationale is elevated model uncertainty, the principled encoding is **sigma inflation**: wider sigma → win_prob shrinks toward 0.5 → edge, score, *and* Kelly size all shrink coherently.

*Evidence on early-season degradation.* Published work supports the premise: NBA opening odds early in the season are more biased and insufficiently moved (Winkelmann, Ötting, Deutscher & Makarewicz 2024, *Journal of Sports Economics*); week-1 lines rely almost entirely on prior-season information (college football market-efficiency evidence, AEA). WNBA-specific aggravators are well documented for May 2026: ~2-week training camps, hardship contracts signed hours before openers, prioritization/overseas absences (CBS Sports; Front Office Sports; ESPN). The engine's own −19.8 PTS opening-day miss is consistent. However, no published source quantifies a ×0.80/×0.90 edge haircut — the magnitudes are arbitrary. And the evidence cuts both ways: early-season *markets* also price off priors, so for a model that ingests lineup news faster than thin WNBA books, weeks 1–3 could be the highest-edge window; a blanket dampener may discard the best opportunities. Conservatism is defensible while WNBA is unproven shadow, but the dampener should be re-derived as a sigma multiplier calibrated from week-1–3 vs mid-season projection RMSE once a season of WNBA shadow data exists.

**3. 3-day opening gate: correct instrument, wrong key.**

The motivating failure was a model failure in the zero-data window — with 0 current-season games, projections run on last-season EWMA + priors against rosters reshuffled by camp cuts and hardship signings. A hard gate is the right tool for that. The market does *not* meaningfully "firm up" by day 4: sharp-book WNBA limits run ~$500 with no prop market-maker, and that remains true all season (Unabated; Betstamp). So the gate's value is model protection, not market protection — and on that basis 3 calendar days is a weak proxy. The binding early-WNBA input is *role/minutes confirmation*, which arrives one observation per game played, not per calendar day. By day 4 most teams have 1–3 games, but a team with a late opener can surface on day 4 with **zero** current-season games and re-trigger the May 13 failure mode. **Recommendation: keep the gate but re-key it to games played — require both involved teams have ≥2 current-season games (≈ days 4–6 for most teams) — rather than extending the calendar window.**

**Summary of required changes (in priority order):** (1) delete or repair `WNBA_EDGE_FLOOR` — as written it is dead code and its comment documents the opposite of the true economics; the defensible replacement is an EV-per-unit floor (≈ raw-edge 6.2% equivalent at −115 to match NBA's net bar); (2) rewire the early-season dampener from edge-multiplication to sigma inflation so win_prob and Kelly sizing shrink coherently; (3) convert the opening gate from 3 calendar days to ≥2 games played per team. Items (1) and (3) are structural and need no data; the magnitudes in (1) and (2) are DATA_GATED on the 100-graded-pick WNBA go-live gate.

### Sources
- Winkelmann, Ötting, Deutscher & Makarewicz (2024), "Are Betting Markets Inefficient? Evidence From Simulations and Real Data," *Journal of Sports Economics*. https://journals.sagepub.com/doi/10.1177/15270025231204997
- Betting Markets and Market Efficiency: Evidence from College Football (AEA). https://www.aeaweb.org/conference/2010/retrieve.php?pdfid=406
- Unabated — "Five WNBA Betting Tips For NBA And College Bettors" (~$500 limits, no prop market-maker); "Getting Precise About Closing Line Value"
- Betstamp — WNBA Sharp Betting Strategy Guide
- BettingUSA — Vigorish Explained; nfelo Sportsbook Hold Calculator (52.38% break-even at −110)
- Bet Prediction Site — The Vig Tax Explained (hold as the lower bound on required edge)
- CBS Sports — WNBA rosters finalized ahead of 2026 opening night; Front Office Sports — WNBA hardship contracts; ESPN — WNBA prioritization and overseas play
- Nylon Calculus — team-stat stabilization rates; Quadratic — NBA DFS projection methodology (recency weighting under rotation change)

---

## SECTION 15 — G9/G9B Edge Floors
**VERDICT:** CONFIRMED_WITH_CAVEAT
**CLASSIFICATION:** DATA_GATED
**Condition to revisit:** Re-derive both floors after the H3 Platt refit lands and once ~50 G9/G9B-blocked picks in `pick_log_blocked.csv` can be shadow-graded — the floors' empirical basis is n=46 (G9) and n=12 (G9B), and the NBA bucket is confounded with the pre-2026-05-10 model era.

### Findings

**1. Shrinkage formalization — does 5–7% emerge naturally? Yes, under defensible parameters.**

Setup (probability space throughout): true edge e ~ N(μ₀, τ²) with μ₀ = −0.02; claimed edge ê | e ~ N(e, σ_ε²). Posterior mean: E[e | ê] = w·ê + (1−w)·μ₀, w = τ²/(τ² + σ_ε²).

*Backing out w from the bucket data.* Realized edge per pick computed as `WR − (vigged implied − 0.024)` on the 218 graded primary/bonus picks in `data/pick_log.csv`:

| Claimed bucket | n | mean ê | Realized edge (±SE) |
|---|---|---|---|
| 3–5% | 13 | 0.0415 | **−0.180** ± 0.137 |
| 5–7% | 33 | 0.0593 | **−0.075** ± 0.090 |
| 7–10% | 30 | 0.0851 | +0.087 ± 0.088 |
| 10%+ | 142 | 0.1472 | +0.056 ± 0.041 |

Pooled 3–7% bucket: ê̄ = 0.0543, realized = −0.104 ± 0.072. Solving for w gives **w = −1.13** — infeasible, meaning the point estimate says claimed edge in that bucket was *anti-signal*, not just noise. The best feasible fit is **w ≈ 0** (claimed edge ≈ pure noise there). By contrast, the 10%+ bucket implies w = **0.455** — a single-w Gaussian model cannot fit both, indicating heteroskedastic σ_ε (estimation error is largest exactly where claimed edge is small). A full OLS of realized on claimed: `realized = −0.118 + 1.21·ê` (slope SE 0.73, n=218); break-even claimed edge = **9.7%** all-sport, **11.5%** NBA-only.

*The floor formula.* Two criteria:
- Zero-true-edge: E[e|ê=F] ≥ 0 ⇒ **F₀ = 0.02·(1−w)/w**. F₀ = 5% at w = 0.286; F₀ = 7% at w = 0.222.
- Profitability (true edge must clear per-side vig v ≈ 0.024 at −110): **F\* = (0.024 + 0.02(1−w))/w**. At the empirically fitted global w ≈ 0.46, F\* ≈ **7.6%**; at w = 0.5, F\* = 6.8%; at w = 0.65, F\* = 5.3%.

So **5–7% emerges naturally** when the claimed-edge signal weight is ~0.45–0.65 under the profitability criterion, or ~0.22–0.29 under the zero-edge criterion. The mechanism is exactly selection-on-noise: conditioning on ê > floor selects positive ε, and Bayesian regression toward μ₀ ≈ −vig is the correction — Smith & Winkler (2006) formalize this; Harrison & March (1984) is the antecedent; Baker & McHale (2013) is the betting application. Caveat: the low-bucket data and the OLS break-even (9.7–11.5%) suggest the floors are, if anything, **slightly low**, not high.

**2. Optimizer's Curse and claimed-edge vs true-edge floors — yes, floors above 1–3% are justified.**

Smith & Winkler (2006, *Management Science* 52(3):311–322) prove that selecting alternatives by maximum estimated value guarantees E[realized | selected] < estimate **even with unbiased estimators** — disappointment is a property of the selection operator, not the estimator. The engine's daily card is precisely this operator: top-N by pick_score from hundreds of candidate lines, so the picks that surface are systematically the most upward-biased estimates. The distinction the floors must respect:

- **True-edge floor (sharps' 1–3%)**: applies to *post-shrinkage* edge from vetted models, continuously validated by positive CLV.
- **Claimed-edge floor (G9/G9B)**: applies to *pre-shrinkage* model output with known calibration gaps. The conversion: a claimed 7% at w = 0.5 implies E[true edge] = **+2.5%** — i.e., G9B's 7% claimed floor lands the engine exactly in the sharp 1–3% *true*-edge band. A claimed 5% at w = 0.5 implies +1.5% true — barely clearing vig at −110 and not at −115. The 1–3% benchmark and the 5–7% floors are therefore *consistent*, not contradictory: they are the same number measured before vs after shrinkage.

**3. NBA 16.7% bucket — n=12, heavily confounded; the floor is a defensible tourniquet, but the causal fix is recalibration.**

Empirical check: the NBA 3–7% bucket is **2W/10L (16.7%), n=12**. Wilson 95% CI: [4.7%, 44.8%] — significant vs. a coin flip (P(≤2/12 | p=0.5) ≈ 1.9%) but the point estimate is not trustworthy. Worse, the bucket is confounded: **10 of 12 picks predate 2026-05-10** (the minutes-scalar/position-model overhaul), and it contains one ML_FAV, one TEAM_TOTAL, and one RA (a stat since disabled at 0W/7L). The era split across all sports: 3–7% ran 25.0% pre-05-10 (n=16) vs **46.7% post** (n=30) — the post-overhaul number is below the 52.1% breakeven but consistent with ~zero true edge, not catastrophe. There is also in-sample circularity: G9B was raised *because of* this bucket, so it cannot then be cited as out-of-sample validation of the raise.

On market structure: published evidence supports props generally being *less* efficient than mainlines (hold 8–15% on props vs 4–5% on spreads, lower limits, less sharp flow), while NBA is the highest-volume US prop market, and the academic literature (Hubáček et al. 2019) characterizes the mainstream NBA market as highly efficient. The synthesis: NBA *main-line star props* are sharp; the prop universe broadly is soft but high-hold. So "NBA market is sharper ⇒ higher floor" is directionally plausible but is **not** what the 16.7% actually shows — the NBA win_prob calibration table shows the failure is model-side: the 60–65% bucket delivered 37.5% (n=8) and 70–75% delivered 55.6% (n=36), while 65–70% delivered 70.0% (n=30). That non-monotone pattern is miscalibration, not market sharpness. Per the engine's own no-band-aids principle: the **causal fix is the H3 Platt refit (and eventually sport-specific calibration)**; G9B is a tourniquet. It is an *acceptable* tourniquet only because (a) it fails safe (blocks bets rather than placing them), and (b) blocked picks now log to `pick_log_blocked.csv`, creating the data path to test removal. Keep it, but tie it explicitly to the H3 gate rather than treating it as permanent structure.

**4. Floor as k·σ_cal — coherent at k≈1 under the parametric estimate, undersized under the empirical one.**

- *Parametric*: Platt fit at n=76 → SE of a calibrated probability at mid-range ≈ **σ_cal ≈ 5–8pp**. Then 1×σ_cal ⇒ G9 = 5% and G9B = 7% sit exactly at k ≈ 1. Coherent.
- *Empirical*: weighted RMS bucket-level calibration gap from the pick log = **13.6pp** all-sport (n=213), 14.3pp NBA (n=125); worst buckets −18.7pp (70–75%, n=47) and −22.6pp (55–60%, n=32). Subtracting expected sampling noise (~7.5pp per-bucket SE): true calibration RMS ≈ **11.4pp**. Against this, the floors are k ≈ 0.45–0.6 — claimed edges of 5–7% are *not* statistically distinguishable from zero under the empirical calibration error.

Arithmetic summary: three independent lenses (Bayesian shrinkage with fitted w, k·σ_cal empirical, OLS break-even) all say 5–7% is the *lower bound* of defensible, not an overcorrection. The floors should not be lowered toward the sharp 1–3% range under any reading of the current evidence; whether they should be *raised* (or replaced by post-shrinkage edge computed as w·ê − (1−w)·0.02 directly in pick scoring) is the question the H3 refit and blocked-pick grading will answer.

### Sources
- Smith, J.E. & Winkler, R.L. (2006). "The Optimizer's Curse: Skepticism and Postdecision Surprise in Decision Analysis." *Management Science* 52(3):311–322. https://www.jstor.org/stable/20110511
- Baker, R.D. & McHale, I.G. (2013). "Optimal Betting Under Parameter Uncertainty: Improving the Kelly Criterion." *Decision Analysis* 10(3):189–199.
- Harrison, J.R. & March, J.G. (1984). "Decision Making and Postdecision Surprises." *Administrative Science Quarterly* 29(1):26–42.
- Hubáček, O., Šourek, G. & Železný, F. (2019). "Exploiting sports-betting market using machine learning." *International Journal of Forecasting*. https://www.sciencedirect.com/science/article/abs/pii/S016920701930007X
- Wizard of Odds, "Player Props: Understanding the Math Behind the Lines"; nfelo Sportsbook Hold Calculator (props 8–15% hold vs spreads ~4.5%)
- Sharp Football Analysis, "CLV Betting Guide" (+1–3% sharp CLV benchmarks); VSiN, "The Importance of Closing Line Value"
- Empirical: `data/pick_log.csv` (307 rows, 218 graded primary/bonus with edge+odds, 2026-04-14 → 2026-06-05); floors verified at `engine/run_picks.py:1233–1239`.

---

## SECTION 16 — TB Poisson Convolution

**VERDICT:** CONFIRMED_WITH_CAVEAT
**CLASSIFICATION:** LOCKED
**Condition to revisit:** Revisit only if graded TB pick calibration drifts (e.g., observed O1.5 hit rate deviates >3pp from model at n≥100 graded picks) or the run environment changes the hit-type mix materially; the convolution structure itself has no fitted parameters to recalibrate.

### Findings

**1. Implementation is numerically sound — verified, not asserted.**

(a) **Convolution structure is standard and correct.** The loop computes the distribution of TB = Σᵢ wᵢXᵢ for independent Poisson Xᵢ by sequential convolution. The resulting distribution is the 4-component **generalized Hermite distribution** (pgf `exp(Σ λᵢ(s^wᵢ − 1))`), per Kemp & Kemp (1965) and Gupta & Jain (1974) — the m=2 case (X₁+2X₂) is the classic Hermite. An unconstrained reference convolution (support 0–200, max_count=60) compared against the engine's exact code path: max absolute probability difference = **7.4×10⁻⁷** across all lines (0.5/1.5/2.5) for both example λ sets. Total probability mass retained: 0.99999926.

(b) **Saturation at max_tb=16 is exactly harmless for over-probability.** `target = min(tb+added, 16)` moves all mass that would land above 16 into the 16 bin; since `over_p = sum(dist[threshold:])` with threshold ≤ 10 for any posted line ≤ 9.5, the saturated bin is always **inside** the summed range. Saturation relocates over-mass within the over-region; it never crosses the threshold boundary. Confirmed.

(c) **Component truncation at max_count = max(8, ⌊5λ⌋) loses negligible mass — with one numeric correction:** P(Poisson(1.0) > 8) = **1.125×10⁻⁶** (not ~1×10⁻⁸; off by two orders, still immaterial). Worst case is λ just under 1.8: tail ≈ 9×10⁻⁵. The truncation **drops** mass rather than renormalizing, so over_p is biased low by ≤ ~10⁻⁴ absolute worst case, ~10⁻⁶ typically. Irrelevant at betting precision.

(d) **pmf < 1e-9 skip:** drops ~10⁻⁷ total. Negligible. **Overall: numerically sound.**

**2. Independence assumption — validated at the variance level and by direct calibration; the weights, not correlation, generate the overdispersion.**

The variance arithmetic checks out: Var(TB) = Σwᵢ²λᵢ under independence. For the example set (λ=0.95/0.30/0.02/0.15): mean = **2.210**, var = **4.730**, var/mean = **2.140**. The engine's empirical figure was reproduced exactly from the 169k-row `mlb_batter_game_stats` table: pooled within-player var/μ (players ≥20 games, game-weighted) = **2.1169** — the quoted 2.117. So the w² weighting alone produces essentially all of the observed overdispersion with zero correlation: a single HR contributes 16 to the variance per unit λ, mechanically inflating var/mean to ~2.1–2.3 even though each component is ~Poisson.

One honesty note: at the **actual** starter mix from the database (ab≥3, n=130,998 games: λ₁B=0.612, λ₂B=0.186, λ₃B=0.016, λHR=0.133; mean TB=1.565), the independent model implies var/mean = **2.317** vs empirical pooled 2.077 — i.e., the independence model is modestly **over-dispersed by ~10%**. The cause is measurable in the data:

- **Net hit-type correlation is slightly negative** (mechanical multinomial competition for shared ABs beats the shared-conditions positive effect): corr(1B,2B) = **−0.066**, corr(1B,HR) = **−0.064**, corr(2B,HR) = **−0.023**.
- **Singles are underdispersed** relative to Poisson: var/μ = **0.895** (binomial thinning on ~4 ABs); 2B = 0.970; HR = **1.004** (almost exactly Poisson).

This is consistent with the literature structure: the standard sabermetric event model treats each PA as a multinomial draw over {1B,2B,3B,HR,BB,out,…} — the basis of Bukiet, Harold & Palacios (1997, *Operations Research* 45(1):14–23) and modern hierarchical PA-outcome models (Gerber & Craig, *JQAS* 2020). Multinomial counts are negatively correlated by construction (Cov(Xᵢ,Xⱼ) = −n·pᵢpⱼ).

**Does the residual correlation matter at lines 1.5/2.5? Barely.** Direct per-player calibration test (436 players with ≥100 starter games each; convolution run on each player's own λ̂ vector vs their empirical hit rate): line 1.5 mean bias = **−0.84pp** (model slightly under-predicts P(TB≥2)), MAE = 1.6pp, RMSE = 0.0202; line 2.5 mean bias = **+0.47pp**, RMSE = 0.0155. The signs match the over-dispersion diagnosis. Sub-1pp systematic bias is well inside prop-pricing noise. Independence is a justified simplification.

**3. NB(r=1.3) fallback — reasonable, and fixed r empirically beats the μ-dependent alternative.**

At μ=2.21, NB(r=1.3) gives var/mean = **2.700** vs the component model's 2.140 — but that example λ set is unrealistically elite (mean TB 2.21 ≈ peak-Judge; actual starter average is 1.565). At the **realistic** starter mix, the component model's implied r = 1.565/1.317 = **1.19**, and at the all-games population implied r = **1.22** — both straddling 1.3. So r=1.3 is well-chosen for the batters who actually get TB props.

Should r be μ-dependent? Theory says yes (constant hit mix ⇒ var ∝ μ ⇒ r ∝ μ), but **empirically no**: per-player RMSE at line 1.5 (n=436) — convolution **0.0202** < NB fixed r=1.3 **0.0228** < NB r=μ/1.30 **0.0240**. The μ-proportional r inherits the component model's ~10% over-dispersion and amplifies it for high-μ hitters; fixed r=1.3 accidentally damps it. Keep r=1.3.

Quantified comparison for the example batter (μ=2.21): P(TB≥2) — convolution **0.5287**, NB(1.3) **0.5000** (−2.9pp). At the realistic starter average (μ=1.565): convolution 0.3750, NB(1.3) 0.3878, empirical 0.3831 — both within ~1pp of truth. The fallback diverges from the convolution mainly for elite hitters (under-prices overs by ~3pp); acceptable for a fallback that fires only when SaberSim components are missing.

**4. Empirical anchor — the convolution reproduces the 35–38% O1.5 rate at realistic inputs.**

From the engine's own 169k batter logs: empirical P(TB≥2) = **33.3%** over all batter-games (ab≥1) and **38.3%** for starters (ab≥3) — confirming the quoted 35–38% band. The convolution at the database's actual starter-average rates gives P(TB≥2) = **37.5%** and P(TB≥3) = **23.0%** vs empirical 38.3%/22.5% — squarely in band. For comparison, the old Normal model at the same moments gives P(>1.5) ≈ 61–63% — reproducing the documented pathology (a continuous symmetric density puts far too much mass above 1.5 when the true distribution has P(TB=0) ≈ 45%). Note: a 53% O1.5 prediction for a hitter projected at 2.2 TB/game (≈ .335 BA equivalent) is plausibly correct, not a miscalibration — real per-player starter rates are λ₁B=0.612, λ₂B=0.186, λHR=0.133, well below older league-regular quotes (~0.85 singles/g describes top-of-order players only; 2024 MLB doubles ran 1.54 per team-game ≈ 0.17 per player-game).

### Sources

- Bukiet, B., Harold, E.R. & Palacios, J.L. (1997). "A Markov Chain Approach to Baseball." *Operations Research* 45(1):14–23. https://pubsonline.informs.org/doi/10.1287/opre.45.1.14
- Kemp, C.D. & Kemp, A.W. (1965). "Some Properties of the 'Hermite' Distribution." *Biometrika* 52(3-4):381–394.
- Moriña, Higueras, Puig & Oliveira (2015). "Generalized Hermite Distribution Modelling with the R Package hermite." *The R Journal* 7(2). https://journal.r-project.org/articles/RJ-2015-035/
- Gerber, E.A.E. & Craig, B.A. (2020). "A mixed effects multinomial logistic-normal model for forecasting baseball performance." *JQAS*.
- Hermite distribution — Wikipedia (pgf and weighted-Poisson-sum construction).
- Sportscasting (citing Baseball-Reference): MLB 2024 trends — doubles 1.54/team-game.
- Engine database: `data/projections.db`, `mlb_batter_game_stats` (169,357 rows, 2023–2026) — all empirical rates, correlations, within-player var/μ = 2.1169, and the 436-player calibration test computed directly in this audit.
