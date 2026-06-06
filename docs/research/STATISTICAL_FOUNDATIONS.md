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

## LOCKED ASSUMPTIONS
*These should not change unless the sport/market fundamentally changes.*
*These are the mathematical foundations. "Feeling" is not sufficient to change them.*

| Assumption | Value | Verdict | Source(s) | Condition to Revisit |
|---|---|---|---|---|
| (populated at end of session) | | | | |

---

## PERIODIC RECALIBRATION
*Correct methodology. Parameter values should be updated each offseason.*

| Assumption | Current Value | Method | Frequency | Last Calibrated |
|---|---|---|---|---|
| (populated at end of session) | | | | |

---

## DATA-GATED
*Correct methodology. Waiting for enough data to finalize parameters.*

| Assumption | Current Value | Gate | Notes |
|---|---|---|---|
| (populated at end of session) | | | |

---

## NEEDS_CHANGE
*Only populated if research finds an error.*

| Issue | Current | Correct | Priority | Evidence |
|---|---|---|---|---|
| (populated at end of session) | | | | |

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

**Operational defect found during verification (beyond the migration plan):** `engine/calibrate_platt.py` — referenced by the migration note at run_picks.py:479-483 ("calibrate_platt.py now fits logit-space"), by CLAUDE.md ("use `python engine/calibrate_platt.py --native-only --force`"), and by the warning inside calibrate_winprob.py — **does not exist anywhere in the repository** (independently re-verified by the audit coordinator: only `calibrate_winprob.py`, `calibrate_sigma.py`, `calibrate_distributions.py` exist; calibrate_winprob.py fits *raw-space* sigmoid on the already-calibrated win_prob column with an explicit do-not-deploy warning). The H3 migration as documented currently has no implementing script. This must be written (logit-space fit on over_p_raw vs outcome, with the slope prior above) before the gate fires.

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

<!-- S6 -->

---

<!-- S7 -->

---

<!-- S8 -->

---

<!-- S9 -->

---

<!-- S10 -->

---

<!-- S11 -->

---

<!-- S12 -->

---

<!-- S13 -->

---

<!-- S14 -->

---

<!-- S15 -->

---

<!-- S16 -->
