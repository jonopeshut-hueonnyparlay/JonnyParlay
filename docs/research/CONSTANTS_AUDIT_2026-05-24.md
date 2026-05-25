# Constants Audit — 2026-05-24
*Auditing every numerical constant in the probability engine that affects win_prob or edge.*
*Sources: engine/run_picks.py, docs/research/CALIBRATION_ANALYSIS_2026-05-23.md, docs/research/PROBABILITY_PIPELINE_AUDIT_2026-05-24.md, docs/research/TIER_FINDINGS.md, docs/audits/AUDIT_HISTORY.md*

---

## 1. SIGMA Dict — Normal Distribution σ Parameters

`SIGMA = max(proj × mult, min)`

Used for: PTS, OUTS, HA, TB (Normal path). AST, REB, SOG go through Poisson so SIGMA entries for them are dead in production (POISSON_STATS takes priority). SOG has a SIGMA entry but it is never reached.

---

### 1A. PTS — `{"mult": 0.35, "min": 4.5}`

- **Value**: σ = max(proj × 0.35, 4.5). At proj=22.5 (typical starter), σ = 7.875.
- **Calibration**: Set during development. The comment in the code says "unchanged — these are well-calibrated." No specific dataset, n, or method is cited for this value. The TIER_FINDINGS.md confirms NBA PTS CV ≈ 0.40–0.55 for starters (0.25–0.33 for stars). mult=0.35 is at the low end of this range — slightly tight for role players.
- **Sample size / confidence**: No empirical calibration record found. Indirectly validated by CALIBRATION_ANALYSIS_2026-05-23.md which shows Over PTS at 65.0% actual vs 67.7% model (n=20, gap −2.7pp ✅) and Under PTS at 76.9% actual vs 63.6% model (n=13, gap +13.3pp — under PTS is being underpredicted). The under over-prediction suggests the sigma may be slightly too wide for unders (or Platt is over-correcting in the wrong direction for unders).
- **Risk**: If mult is 10% too low (mult=0.315 instead of 0.35), σ shrinks → over_p and under_p pushed further from 0.50 → Platt has to work harder to compress them → edge calculations become less reliable. The bigger risk is that SIGMA and Platt are partially canceling each other: wrong SIGMA + compensating Platt is a coupled mis-calibration.
- **Verdict**: QUESTIONABLE. Over PTS looks fine (n=20). Under PTS shows +13.3pp actual over-performance vs model — suggests sigma may be slightly wide or Platt is suppressing under_p too much. Cannot separate the SIGMA-vs-Platt interaction without direction-split analysis.

---

### 1B. AST — `{"mult": 0.45, "min": 1.3}`

- **Value**: σ = max(proj × 0.45, 1.3). At proj=5.0, σ = 2.25.
- **Calibration**: Set during development. Comment says "unchanged — well-calibrated." TIER_FINDINGS.md cites AST CV = 0.45–0.55 (elite ~0.40–0.48). mult=0.45 is at the low end — potentially tight.
- **Sample size / confidence**: The entry is in SIGMA but AST uses Poisson in production (it is in POISSON_STATS). SIGMA["AST"] is only reached in the G14 gate and in `_combo_mu_sigma()` for combo props containing AST (PA, RA, PRA). It is dead for standalone AST win_prob calculation.
- **Risk**: For combo props (PA, RA, PRA), SIGMA["AST"] sets the σ(AST) component. PROBABILITY_PIPELINE_AUDIT_2026-05-24.md notes that AST is likely overdispersed (true CV empirically higher than Poisson assumes). If SIGMA["AST"]=0.45 is too tight for combos, combo AST contribution is under-dispersed → combo win_probs are over-confident.
- **Verdict**: QUESTIONABLE for combo props. Dead code for standalone AST. The real problem is Poisson being used for AST at all (P2 in the pipeline audit) — SIGMA is a secondary concern.

---

### 1C. REB — `{"mult": 0.58, "min": 2.5}`

- **Value**: σ = max(proj × 0.58, 2.5). At proj=6.5, σ = 3.77.
- **Calibration**: Set during development. TIER_FINDINGS.md cites REB CV = 0.38–0.70 (bigs ~0.38–0.45, guards ~0.55–0.70). mult=0.58 is near the high end for bigs, appropriate for guards — a reasonable population midpoint.
- **Sample size / confidence**: REB is in POISSON_STATS so SIGMA["REB"] is dead for standalone REB win_prob. Only used in combo props. Calibration analysis (n=26 under REB) shows 53.8% actual vs 62.0% model — a −8.2pp gap indicating mild over-prediction. But this could be Platt rather than SIGMA.
- **Risk**: As with AST, the sigma entry matters only for combo props. For PRA/PR that include REB, a mis-specified REB sigma inflates the combo σ → potentially wider combo distribution → lower combo win_probs (conservative error, less harmful).
- **Verdict**: QUESTIONABLE for combo props. mult=0.58 is within the empirical CV range. The −8.2pp REB under gap deserves monitoring.

---

### 1D. SOG — `{"mult": 0.55, "min": 1.2}`

- **Value**: σ = max(proj × 0.55, 1.2). Dead — SOG is in POISSON_STATS. This entry only affects G14.
- **Calibration**: TIER_FINDINGS.md cites NHL SOG CV = 0.47–0.57. mult=0.55 is within that range.
- **Sample size / confidence**: Dead for win_prob. G14 uses it to block picks where the projection barely clears the line (z < 0.10). The entry is reasonable given empirical CV.
- **Risk**: If σ is wrong in G14, the clearance gate either blocks legitimate picks (if σ is too wide) or allows barely-there edges through (if σ is too tight). Low production impact.
- **Verdict**: UNKNOWN (dead code for win_prob, reasonable for G14).

---

### 1E. OUTS — `{"mult": 0.30, "min": 3.0}`

- **Value**: σ = max(proj × 0.30, 3.0). At proj=16.5 outs, σ = 4.95.
- **Calibration**: Code comment: "actual σ ≈ 4.5–5.0 outs/start (was 0.22 → 3.3, too tight)." This is the recalibrated value after the MLB audit. The comment references "2024 season data" but does not give a specific n or method.
- **Sample size / confidence**: Qualitative reference to 2024 season — no specific n. Current empirical evidence: OUTS under WP floor gate (G_OUTS_UNDER: prob<0.60 → block) exists as a band-aid, suggesting the model may still be mis-calibrated for this stat.
- **Risk**: PROBABILITY_PIPELINE_AUDIT_2026-05-24.md explicitly calls `G_OUTS_UNDER` a "partly" band-aid for SIGMA mis-calibration. If mult is too low, the distribution is too wide → unders hit below 50% → G_OUTS_UNDER compensates but the underlying sigma is wrong.
- **Verdict**: QUESTIONABLE. Was updated from 0.22 to 0.30 but band-aid gate `G_OUTS_UNDER` still exists, signaling the calibration is incomplete. No formal n-backed calibration.

---

### 1F. HA — `{"mult": 0.50, "min": 2.5}`

- **Value**: σ = max(proj × 0.50, 2.5). At proj=7.0 hits, σ = 3.5.
- **Calibration**: Code comment: "Normal (15% overdispersed vs Poisson)." This describes WHY it uses Normal not Poisson, but does not explain how mult=0.50 was derived. TIER_FINDINGS.md cites HA CV = 0.40–0.55; mult=0.50 is in the middle of that range.
- **Sample size / confidence**: No specific calibration data cited. The 15% overdispersion claim is a general statistical observation about hit-rate distributions, not a pick-log measurement.
- **Verdict**: UNKNOWN. mult=0.50 is reasonable given published HA CV but has no formal calibration backing.

---

### 1G. TB — `{"mult": 1.20, "min": 1.5}`

- **Value**: σ = max(proj × 1.20, 1.5). TB is currently disabled (`G_TB_DISABLED`). This entry is dead.
- **Calibration**: Code comment: "was 41% UNDER real variance (lumpy dist)." TB was moved to the `calc_tb_prob()` Poisson convolution path but is now killed entirely because the distribution model is wrong.
- **Risk**: None while disabled. If re-enabled, the SIGMA entry would be bypassed by `G_TB_DISABLED` anyway.
- **Verdict**: UNKNOWN (dead code — TB disabled).

---

## 2. NB_R Dict — Negative Binomial Dispersion

`NB(mu, r): var = mu + mu²/r`. Smaller r = more overdispersion.

---

### 2A. 3PM — `r = 12.3`

- **Value**: NB dispersion parameter for three-pointers made.
- **Calibration**: Code comments provide the derivation: `avg(var/mu) = 1.119` across n=418 player-seasons from the 2024-25 projections.db. Then `r = avg_mu / (var/mu ratio - 1) = 1.457 / 0.119 ≈ 12.3`. This is explicitly within-player conditional r (correct approach — captures per-game variance for a given player, not cross-player differences). Calculation is documented and reproducible.
- **Sample size / confidence**: n=418 player-seasons is a substantial sample. The calculation methodology is sound (within-player variance decomposition).
- **Is it still current?**: Calibrated on 2024-25 data. Will need refresh each season as pace/rule changes shift 3PA/game distributions. For 2025-26 playoffs, no update noted.
- **Risk if wrong**: r=12.3 is relatively low overdispersion for 3PM (var/mu = 1 + mu/r = 1 + 1.457/12.3 ≈ 1.12). Calibration analysis shows 3PM over at ≤1.5 hitting 50% WR vs 70.4% model — a −20.4pp gap at the binary threshold. G8D blocks this range. For higher 3PM lines, no obvious calibration failure is documented. If r is 10% too high (less overdispersion), the model assigns too-high probabilities at the tails → more overconfidence.
- **Verdict**: SOLID for the methodology and sample size. The residual G8D gate (≤1.5 overs) signals that the NB model still over-predicts at the binary threshold even with r=12.3. The NB assumption itself (vs a true zero-inflated model) is a limitation, but within NB models r=12.3 is well-estimated.

---

### 2B. HRR — `r = 1.5`

- **Value**: NB dispersion parameter for Hits+Runs+RBIs.
- **Calibration**: Code: "calibrated from shadow log: NB(r=1.5, μ=2.0) gives P(X≥2)=47.8% matching empirical 48% WR." Shadow log n=1810 — this is a large sample for a single-line match. However, this is a different calibration methodology from 3PM: it is a single-point match at one specific (μ, line) combination, not a full within-player variance estimate. r was chosen so that P(X≥2|μ=2.0) = empirical WR at line=1.5. This is a moment-matching calibration for one point on the distribution, not a full MLE.
- **Population vs within-player r**: The comment says "calibrated from shadow log empirical WR" — this is the population-level WR across all bets, not within-player conditional variance. If different players have different mu (some 1.0, some 3.0), fitting r to aggregate P(X≥2) at μ=2.0 is approximate. The true within-player r may differ.
- **Current status**: HRR is fully disabled (`G_HRR_DISABLED`). Code comment: "NB(r=1.5) still over-states P(X≥1) (~72% vs 57.4% actual)." The r calibration was at line=1.5 but the model still fails at line=0.5. r=1.5 may be too large (too little overdispersion) for HRR — real HRR has extreme zero-inflation (batter 0-H/R/RBI in ~37% of games).
- **Risk**: HRR is disabled so this is moot for now. If re-enabled with r=1.5, the model will over-project probabilities, especially at line=0.5. The zero-inflation problem requires a zero-inflated NB or Hurdle model, not a standard NB.
- **Verdict**: NEEDS REFIT. n=1810 is adequate for re-estimation but the moment-matching methodology and single-line focus was insufficient. The stat is disabled pending a better model.

---

### 2C. K — `r = 5.0`

- **Value**: NB dispersion parameter for pitcher strikeouts.
- **Calibration**: Code: "pitcher Ks overdispersed vs Poisson (bimodal: early hook vs deep start). SaberSim projects conservative median IP; market prices to mode IP → K unders structurally lose." r=5.0 is described as an "overdispersion estimate" — no specific sample size or calculation method is cited. The methodology was not like 3PM (where avg(var/mu) was computed). K unders are blocked entirely by `G_K_NO_UNDERS`, and K overs only at line ≥6.0 (`G_K_MIN_LINE`).
- **Sample size / confidence**: No specific n cited. TIER_FINDINGS.md shows MLB K CV = 0.28–0.44 (actual σ/μ). At r=5.0 and μ=7.0 Ks, NB gives var = 7.0 + 49/5 = 16.8, σ = 4.1, CV = 0.59. This is higher than the empirical CV range (0.28–0.44), meaning r=5.0 is producing more variance than real K data shows. However, this may be intentional — wider σ → lower win_probs → more conservative estimates for K overs.
- **Risk**: If r is too low (too much overdispersion vs real data), K over probabilities are understated → the model passes fewer K overs with real edge through gates. The G_K_MIN_LINE gate (≥6.0 only) already restricts to high-confidence situations.
- **Verdict**: QUESTIONABLE. r=5.0 produces CV ≈ 0.59 vs empirical 0.28–0.44, suggesting the NB model overestimates K variance. No formal calibration with n cited. K unders are blocked entirely, limiting downside risk. Needs a proper within-player avg(var/mu) calculation like 3PM received.

---

## 3. COMBO_RHO — Correlation Parameters

`Var(X+Y) = Var(X) + Var(Y) + 2·ρ·σ(X)·σ(Y)`

---

### 3A. PTS-REB: `ρ = 0.333`

- **Value**: Intra-player game-to-game correlation between PTS and REB.
- **Calibration**: Code: "calibrated from 75,367 player-games (595 players, n>=20, min>=5) across all seasons in projections.db. Weighted average of within-player Pearson correlations." This is explicitly the correct approach — within-player (conditional) correlation, not cross-sectional. Includes total covariance including minute variance, which is correct since SIGMA already captures total σ.
- **Sample size / confidence**: 75,367 player-games from 595 players is a large, well-powered dataset. Weighted average methodology avoids domination by high-minute players.
- **Are these total or conditional correlations?**: Total (including minute variance). The code comment confirms this is intentional. Since SIGMA captures total σ (not residual σ after removing minute effects), total ρ is the correct quantity.
- **Sensitivity to error**: If ρ is wrong by 0.10 (ρ = 0.233 instead of 0.333), the combo variance changes by 2 × 0.10 × σ(PTS) × σ(REB). At σ(PTS)=7.875, σ(REB)=3.77: Δvar = 2 × 0.10 × 7.875 × 3.77 = 5.94. σ_combo changes by √(var_combo + 5.94) − √(var_combo). At typical combo σ_combo ≈ 9.5, this is ≈ 0.31 change in σ. For a pick with proj 2 points above the line, the z-score changes from 2/9.5 = 0.211 to 2/9.81 = 0.204. Win_prob changes by Φ(0.211) − Φ(0.204) ≈ 0.003 — less than 0.5pp. Combo win_prob is relatively insensitive to 0.10 ρ error.
- **Verdict**: SOLID. Large sample, correct methodology (within-player Pearson, weighted), total covariance interpretation is appropriate. Low sensitivity to small ρ errors.

---

### 3B. PTS-AST: `ρ = 0.233`

- **Value**: Intra-player PTS-AST correlation.
- **Calibration**: Same 75,367 player-games. PTS-AST correlation is lower than PTS-REB because assists are more role/pace-conditional and can be high even when scoring is low (playmaker games).
- **Sample size / confidence**: Same large dataset as above.
- **Sensitivity**: Similar calculation as above — 0.10 error in ρ causes <0.5pp shift in combo win_prob at typical projection levels.
- **Verdict**: SOLID. Same methodology as PTS-REB. ρ=0.233 is plausible — lower than PTS-REB correlation, consistent with basketball intuition (scoring and distributing can trade off).

---

### 3C. REB-AST: `ρ = 0.251`

- **Value**: Intra-player REB-AST correlation.
- **Calibration**: Same 75,367 player-games.
- **Sample size / confidence**: Same large dataset.
- **Sensitivity**: Similar to above. ρ=0.251 is between PTS-REB and PTS-AST. Both REB and AST are driven partly by minutes (shared factor), which explains a moderate positive correlation even for guards (more minutes → more of both).
- **Verdict**: SOLID. Same methodology, same dataset confidence.

---

### 3D. COMBO_RHO_WNBA

- PTS-REB: 0.13, PTS-AST: 0.04, REB-AST: 0.05
- **Calibration**: "9 players / 336 games (2024 season)."
- **Sample size / confidence**: n=336 player-games from 9 players is thin. Weighted Pearson correlations at this sample size have standard error of roughly 1/√n ≈ 0.054. A 95% CI on ρ=0.04 would be approximately (−0.07, 0.15) — statistically indistinguishable from zero. All three WNBA correlations may be near-zero by noise rather than true structure.
- **Risk**: If true WNBA ρ(PTS-AST) is actually 0.15 instead of 0.04, combo variance changes slightly but given the already-small correlation, the effect on win_prob is minimal. Near-zero correlations mean combos are nearly additive — a conservative approximation that understates variance slightly.
- **Verdict**: QUESTIONABLE. Sample too small (n=9 players) for reliable correlation estimates. The near-zero values may be real or sampling noise. The conservative implication (near-additive combos) limits the damage but the estimates are not trustworthy.

---

## 4. PLATT_A = 1.4988, PLATT_B = -0.8102

- **Value**: Platt scaling applied as `sigmoid(1.4988 × over_p − 0.8102)`. Applied to all NBA, NHL, WNBA props. Skipped for MLB.
- **Calibration**: Fitted 2026-05-01 on n=76 settled primary+bonus props (NBA + NHL) using Nelder-Mead NLL optimization. Result: mean model win_prob 0.696 → calibrated 0.579 = actual 0.579. 6% Brier score improvement. No train/test split cited — appears to be fitted on the full 76-pick sample.
- **Is n=76 enough for stable Platt coefficients?**
  - Platt scaling has 2 free parameters (A and B). Rule of thumb for sigmoid calibration: ~10–20 samples per parameter = 20–40 minimum. n=76 clears the minimum but barely.
  - Bootstrap confidence interval estimate: For logistic regression with n=76 binary outcomes and 2 parameters, standard error on each coefficient ≈ 1.5–3.0 (depends on class balance and predictor spread). A rough 95% CI on A = 1.4988 is approximately (0.9, 2.1); on B = -0.8102 approximately (−1.4, −0.2). These are wide — a different 76-pick sample from the same generating process could give A between 0.9 and 2.1.
  - At A=0.9 vs A=2.1, the sigmoid output at over_p=0.65 gives: sigmoid(0.9×0.65 − 0.8102)=0.532 vs sigmoid(2.1×0.65 − 0.8102)=0.622. That's a 9pp difference in calibrated win_prob from coefficient uncertainty alone.
- **NBA and NHL mixed?**: Yes — 76 props from both NBA and NHL. NHL SOG at a ~3.5 line and NBA AST at a 5.0 line have very different underlying distributions. Using a single Platt across both is a simplification. The mixed-sport fitting means the A,B reflect an average over different stat-distribution shapes.
- **Stat composition bias**: No breakdown of the 76 props by stat is documented. If the 76 picks were dominated by SOG unders (the most common pick type), A and B are calibrated primarily to SOG. When applied to PTS overs or 3PM, the calibration may be systematically off.
- **Key structural flaw**: This is NOT standard Platt (which operates in logit-space: `sigmoid(A × logit(p) + B)`). This version takes raw probability directly. The transformation behaves differently at the tails — raw-probability Platt compresses the 0.70–0.90 range less aggressively than logit-space Platt. This partially explains why the 0.70–0.80 WP bucket remains 20.8pp over-predicted even after Platt.
- **The calibration analysis (2026-05-23) confirms this is wrong**: Under PTS is hitting 76.9% vs model 63.6% (Platt is under-predicting unders). Over AST is hitting 25% vs model 65.3% (Platt cannot fix a 40pp gap from a model that is fundamentally wrong). The single-direction Platt is simultaneously too aggressive for some cases and insufficient for others.
- **Verdict**: NEEDS REFIT. n=76 is borderline; no train/test split; mixed stat composition; non-logit-space implementation; already confirmed to fail for stat-direction combinations (over vs under) that behave very differently. The H3 gate (refit at 300 rows) is the correct plan. Direction-split Platt (separate A,B for overs vs unders) is the recommended improvement.

---

## 5. VAKE_BASE Sizing Table

`(0.03-0.05 → 0.50u), (0.05-0.07 → 0.75u), (0.07-0.09 → 1.00u), (0.09+ → 1.25u)`

- **Value**: Flat-step unit sizing based on adj_edge.
- **Calibration**: TIER_FINDINGS.md §1 (Section 1) contains the explicit Kelly comparison:

  | Tier | Edge | VAKE | Full Kelly | Fraction |
  |------|------|------|------------|----------|
  | T1 (min, 3%) | 3% | 0.50u | 6.45u | ~1/13 full Kelly |
  | T1 (mid, 5%) | 5% | 0.75u | 10.75u | ~1/14 full Kelly |
  | T2 (5%) | 5% | 0.57u | 10.75u | ~1/19 full Kelly |
  | T3 (6%) | 6% | 0.29u | 12.6u | ~1/43 full Kelly |

  VAKE runs at approximately 1/4 to 1/9 of quarter Kelly. The research document explicitly endorses this as "appropriate given: high stat-level CV (0.5–1.0+), model edge uncertainty, portfolio variance compounding, and prop market CLV noise."

- **Was this derived from Kelly or empirical?**: Kelly-informed conservative sizing. The TIER_FINDINGS research validated Kelly fractions theoretically; the specific VAKE breakpoints (3/5/7/9% edges) were set by judgment, not empirical optimization.

- **Kelly check at edge=0.05**: At WP=0.60, -110 odds (decimal 1.909), Kelly formula: f = (0.909 × 0.60 − 0.40) / 0.909 = (0.545 − 0.40) / 0.909 = 0.160 = 16% of bankroll = 16u. Quarter Kelly = 4u. VAKE returns 0.75u = 1/21 of full Kelly. VAKE is well below even quarter Kelly, consistent with the research recommendation of ultra-conservative sizing given model uncertainty.

- **Is there a mismatch between Kelly and VAKE?**: VAKE is intentionally far below Kelly — approximately 1/4 to 1/9 of quarter Kelly. This is not a mismatch; it is a deliberate choice documented in the research. The justification: CV of NBA stats (0.45–1.2) means Kelly's assumption of known, stable edge is violated. Fractional Kelly at 1/4 is standard; VAKE at ~1/10 of quarter Kelly reflects the additional uncertainty discount.

- **Missing feature**: VAKE does not incorporate win_prob into sizing — only edge. At the same edge=0.05, a pick with WP=0.58 and a pick with WP=0.66 get the same base units. The VAKE_MULT tiers apply variance and tier multipliers but not WP directly.

- **Verdict**: SOLID from a Kelly-safety standpoint (far below Kelly = ruin-safe). QUESTIONABLE from an optimization standpoint — the breakpoints (3/5/7/9%) are judgment-based and the flat step function loses resolution. WP is not in the sizing formula. But conservative sizing errors are safe errors.

---

## 6. pick_score Formula

`score = sw × wp_n + ew × e_n`
- `wp_n = (win_prob × 100 − 50) / 25 × 100` (normalizes WP: 50%→0, 75%→100, 62.5%→50)
- `e_n = (edge × 100) / 15 × 100` (normalizes edge: 0%→0, 15%→100, 7.5%→50)
- Default: sw=0.40, ew=0.60 (40% WP, 60% edge)
- Then × PICK_SCORE_TIER_MULT (T1=0.90, T1B=0.93, T2=1.00, T3=0.95)
- Plus cold_start penalty, injury trigger bonus

---

### 6A. 40/60 WP/Edge Split

- **Calibration**: Not validated against actual WR correlation. The 40/60 split was set by design (edge-dominant philosophy). No regression of `pick_score` vs actual win_outcome from pick_log.csv is documented.
- **Is it validated?**: No explicit cross-validation. The calibration analysis (2026-05-23) shows T2 tier achieving 58.3% actual WR vs 60.2% model (well-calibrated), which is consistent with the tier performing as expected. But pick_score's predictive power vs win_prob alone is not tested.
- **Does pick_score predict WR better than win_prob alone?**: Unknown from available data. The score's edge-dominance (60%) means high-edge, moderate-WP picks score above low-edge, high-WP picks. Given that WP is poorly calibrated (Platt issues) while edge may be more stable, edge-weighting may be correct — but this is inference, not measurement.
- **Scaling concern**: wp_n = 0 at WP=0.50, 100 at WP=0.75. e_n = 0 at edge=0, 100 at edge=15%. At Platt ceiling WP≈0.666, wp_n = (66.6-50)/25 × 100 = 66.4. At typical edge 6%, e_n = 40. Score = 0.40×66.4 + 0.60×40 = 26.6 + 24 = 50.6. This is a typical T1/T1B pick around the MIN_PICK_SCORE=25 floor but below the MIN_OVER_SCORE=40 for overs.
- **The MIN_OVER_SCORE=40 floor interacts**: Overs need score≥40. Given the Platt ceiling at ~66.6%, and the WP bucket analysis showing overs at −13.6pp overall, MIN_OVER_SCORE=40 is doing the work that a correctly calibrated model should be doing.
- **Verdict**: QUESTIONABLE. No empirical validation that 40/60 predicts WR better than alternative weights. wp_n scaling assumes WP of 75% is the upper reference — post-Platt, this is never reached, making the scale effectively stretched. Edge-dominance is a reasonable philosophy but untested.

---

### 6B. Edge Ceiling at 15% (e_n denominator)

- **Value**: `e_n = (edge × 100) / 15 × 100`. A 15% edge normalizes to e_n = 100.
- **Calibration**: Code comment: "ceiling: 15% (was 20%)." Changed because 15% is the actual p90 of the edge distribution in production. No formal measurement cited but reflects empirical observation.
- **Risk**: If actual p90 of edge is higher than 15%, picks with 16-20% edge are capped at e_n = 100+, but G2 blocks edges ≥20% anyway. The 15% ceiling is compatible with the G2 gate.
- **Verdict**: SOLID. G2 (edge ≥ 20% → block) means no pick ever exceeds the ceiling by much. The 15% choice is reasonable.

---

### 6C. PICK_SCORE_TIER_MULT

- T1=0.90, T1B=0.93, T2=1.00 (reference), T3=0.95
- **Calibration**: Code comment: "T2 is the reference tier (best empirical win rate, 61.1% vs T1=45.1% at n=51/54)." The T1=45.1% WR is alarming — T1 is the premium tier but is performing worse than T2. The tier multiplier T1=0.90 partially penalizes T1 picks in scoring but is a weak response to a 16pp WR differential.
- **Current data (2026-05-23)**: T1 overall hitting 46.6% (n=58). T2 at 58.3% (implied from T2 WR mentioned in calibration). The tier multiplier is applying a 10% score penalty to T1 picks, but T1 is still appearing in the premium card and losing.
- **Risk**: The tier multiplier is downstream of all the structural calibration failures in T1 (over-predicted SOG, over-predicted AST). It is scoring T1 picks lower but not blocking them. The real fix is either raising T1 min edge or accepting that T1 (dominated by SOG unders in the NHL) is simply harder to project.
- **Verdict**: QUESTIONABLE. The multiplier was fitted to observed WR data (T2 61.1%, T1 45.1%) but is not proportional — a 16pp WR gap gets a 10% score discount. The multiplier reduces T1 scores modestly but does not stop T1 picks from appearing. The 0.90/0.93/1.00/0.95 values are judgment calls with real data supporting the T2 > T1 ordering but not the specific magnitudes.

---

## 7. Gate Thresholds

---

### 7A. G1: prob≥0.70 AND odds>−200 AND edge<0.05 → block

- **Value**: Blocks high-probability picks at ordinary odds with weak edge.
- **Calibration**: The 0.70–0.80 WP bucket is hitting 54.2% actual vs ~75% model (−20.8pp, n=48). G1 blocks some but not all of this bucket. The odds>−200 condition allows some picks through (if odds ≤ −200, G7 blocks them first). The edge<0.05 escape hatch lets strong-edge picks at high WP through.
- **Is the threshold validated or arbitrary?**: The 0.70 threshold reflects empirical evidence that high-WP picks are over-predicted. The edge<0.05 threshold (allowing strong-edge exceptions) is judgment-based. PROBABILITY_PIPELINE_AUDIT_2026-05-24.md explicitly calls G1 a band-aid for Platt over-inflation.
- **Verdict**: BAND-AID / QUESTIONABLE. Correct directional response to the 0.70–0.80 over-prediction problem. Arbitrary edge<0.05 escape hatch. The structural fix is the H3 Platt refit.

---

### 7B. G4: line≤2.5 AND prob>0.75 → block

- **Value**: Blocks extreme-probability picks on small lines.
- **Calibration**: When the model says >75% on a line ≤2.5, Platt over-inflation is almost certain (Platt ceiling at ~66.6% under normal operation means prob>0.75 almost never happens legitimately — it would require raw over_p near 1.0). G4 is mostly a safety net for model error cases that slip past Platt.
- **Is the threshold validated or arbitrary?**: The 0.75 threshold is conservative — picks between 0.70 and 0.75 are allowed but G1 catches some of them. The line≤2.5 condition reflects that low-line props are most vulnerable to binary fragility (like G8). Judgment-based but well-reasoned.
- **Verdict**: QUESTIONABLE as a standalone gate. Functions as a second-order safety net after G1. The thresholds (0.75 prob, 2.5 line) are arbitrary but directionally correct.

---

### 7C. G5: odds>0 AND prob>0.65 → block

- **Value**: Blocks positive-money odds picks with high model probability.
- **Calibration**: If a book offers +150 on a pick where the model says 65% probability, the implied model edge is enormous (model 65% vs book's 40% implied). This almost certainly signals a model error (structural over-prediction) rather than a real edge. Only 6 props with WP>0.65 and positive odds have ever genuinely been that mis-priced. The gate is sound in principle.
- **Evidence from calibration data**: None specific to G5, but the overall over-prediction pattern supports blocking.
- **Verdict**: SOLID as a structural integrity gate. The condition is a near-certain model error detector.

---

### 7D. G7: odds≤−150 → block

- **Value**: Hard juice ceiling — any pick at -151 or worse is rejected.
- **Calibration**: At -150 odds, the book implied probability is 60.0% after removing vig. A model edge of 3% over this means WP ≈ 63% vs book's 60% no-vig. At -150 juice, even a real 3% edge requires hitting at 63% to break even on the juice — this is well above the calibration floor where the model is trustworthy. Beyond the math, -150 picks have compressed upside and the model's over-prediction is worst at high probabilities.
- **Historical context**: No specific incident cited. This is a standard sharps' rule — avoid heavy juice props.
- **Verdict**: SOLID. Well-grounded in both Kelly theory and empirical evidence of high-WP over-prediction.

---

### 7E. G7b: −149 to −140 AND edge<0.09 → block

- **Value**: Soft juice gate — allows -140 to -149 picks only if edge is strong (≥9%).
- **Calibration**: The 0.09 threshold is judgment-based. At -145 odds (book nv ~59%), a 9% edge means model WP ≈ 68%. Given Platt ceiling at ~66.6%, achieving 68% WP requires near-maximal raw over_p — essentially requires the pick to be exceptionally strong.
- **Verdict**: QUESTIONABLE. The 9% threshold effectively blocks most -140 to -149 picks since edges rarely reach 9%. The gate is functioning but the specific 9% threshold is arbitrary.

---

### 7F. G10: under≤2.5 AND edge<0.08 → block

- **Value**: Blocks low-line unders with weak edge.
- **Calibration**: Low-line unders (e.g., AST under 2.5, REB under 2.5) are binary-adjacent and have high model error. The 0.08 edge requirement is a quality filter. G8 already blocks ≤1.5 lines for several stats; G10 extends this principle to the 2.5 line for the under direction. The 0.08 threshold (vs the base 0.03 for G9) means you need 2.67× the standard edge to pass a low-line under.
- **Is the threshold validated?**: No specific empirical backing for 0.08 vs 0.07 vs 0.09. The PROBABILITY_PIPELINE_AUDIT_2026-05-24.md calls this "partly" a band-aid for low-line fragility with an arbitrary threshold.
- **Verdict**: QUESTIONABLE. Directionally correct (low-line unders are riskier) but the 0.08 edge threshold is arbitrary.

---

### 7G. G13B: HRR WP floors (0.58 at line 0.5, 0.65 at line 1.5)

- **Value**: HRR-specific win_prob floors.
- **Current status**: HRR is fully disabled by `G_HRR_DISABLED` after G13B — G13B is dead code in production.
- **Calibration history**: The 0.58 floor came from "57.4% empirical WR at line=0.5" (the model's inflated NB probability still doesn't match reality). The 0.65 floor for line>0.5 came from "48% empirical WR — dead without strong NB model conviction."
- **Verdict**: UNKNOWN (dead code — HRR disabled). The thresholds were empirically motivated but HRR failed even with them, leading to full disable.

---

### 7H. MIN_WIN_PROB = 0.55

- **Value**: Global win probability floor applied in `apply_soft_rules_premium()`.
- **Calibration**: Explicitly documented: "WP 0.50-0.60 bucket: 39.3% actual vs 55% model (n=61, gap -15.7pp, 2026-05-23)." The CALIBRATION_ANALYSIS_2026-05-23.md shows this bucket had the largest volume (n=61) and the worst calibration gap. 0.55 cuts the lower portion of the 0.50-0.60 bucket without eliminating the entire range (which would require 0.60).
- **Is the threshold validated?**: The n=61 sample provides reasonable confidence in the bucket-level gap (−15.7pp is 4+ standard deviations away from break-even given n=61). The specific choice of 0.55 vs 0.56 or 0.58 is judgment. Setting at 0.60 would eliminate the entire problematic bucket but reduce card volume significantly.
- **Risk**: The floor helps but doesn't fix the underlying Platt over-prediction. Picks at 0.56–0.60 WP still pass and may hit at only ~45-50%.
- **Verdict**: SOLID as an empirically motivated floor. The gap (−15.7pp, n=61) is statistically significant. The 0.55 choice is conservative (doesn't eliminate the full bucket), which is reasonable pending the structural H3 fix.

---

### 7I. MIN_OVER_SCORE = 40

- **Value**: Higher score floor for over picks vs 25 for unders.
- **Calibration**: Code comment: "overs 5-13 (27.8% WR) vs 18 at sub-40 avg." The calibration analysis (2026-05-23) shows overs overall at 49.2% WR vs 62.8% model (−13.6pp). The directional gap is real and large. MIN_OVER_SCORE=40 is a score-based gate — it indirectly requires higher edge and/or higher WP for overs to pass.
- **Is 40 the right number?**: Judgment-based. At wp=0.60 and edge=0.06: score = 0.40×(60-50)/25×100 + 0.60×(6/15)×100 = 0.40×40 + 0.60×40 = 16 + 24 = 40. So a pick at exactly WP=0.60 and edge=0.06 sits right at the over threshold. This is a reasonable calibration point — overs need to clear a medium-quality bar to appear.
- **Verdict**: QUESTIONABLE. The −13.6pp over gap is real and well-evidenced. MIN_OVER_SCORE=40 is a reasonable band-aid that filters the weakest overs, but the PROBABILITY_PIPELINE_AUDIT_2026-05-24.md correctly identifies it as masking the calibration failure. The structural fix is direction-split Platt.

---

## 8. Other Probability-Affecting Constants

---

### 8A. I6 Confidence Modifier: GP<10 → 0.70, GP<20 → 0.85, else 1.0

- **Value**: Scales adj_edge downward for players with few games played this season.
- **Calibration**: The thresholds (10, 20 games) match MIN_GAMES_FOR_TIER=10 in the projection engine. The factors (0.70, 0.85) are judgment-based — no empirical validation of whether early-season players have WR 15% or 30% below normal.
- **Key inconsistency**: adj_edge is scaled, but win_prob is NOT. A 3-game player gets the same win_prob as a 40-game player. Gates using win_prob (G1, G4, G5, MIN_WIN_PROB) are not affected by the confidence modifier. PROBABILITY_PIPELINE_AUDIT_2026-05-24.md identifies this as P4 — a structural inconsistency. The proposed fix: `adj_wp = 0.50 + (win_prob - 0.50) × conf`.
- **Verdict**: QUESTIONABLE. The concept is sound (early-season uncertainty) but the implementation is asymmetric — only adj_edge reflects uncertainty, not win_prob. The specific factors (0.70, 0.85) are arbitrary.

---

### 8B. BLEND_ALPHA = 0.25 (game line projection blending)

- **Value**: Blended projection = market_line + 0.25 × (saber_proj − market_line). 75% weight to market, 25% to SaberSim.
- **Calibration**: Code comment: "prevents massive edge calculations when SaberSim disagrees with Vegas by 10+ pts." This is a regularization choice, not an empirical calibration. If BLEND_ALPHA = 1.0, the model fully trusts SaberSim (dangerous); if 0.0, the model ignores SaberSim and always finds zero edge (useless). 0.25 is conservative.
- **Risk**: If SaberSim projections have real signal, 75% discounting throws away that signal. If they are noise, 25% weighting still introduces error. No empirical validation of what BLEND_ALPHA maximizes CLV.
- **Verdict**: UNKNOWN. The value is a judgment call without empirical validation. CLV data on game lines could test whether different alpha values improve or worsen outcomes.

---

### 8C. GAME_SIGMA — NBA: `{"total": 12.0, "spread": 12.0, "team": 9.0, "ml": 12.0}`

- **Value**: σ for game line distributions. NBA total σ=12.0 points.
- **Calibration**: NBA game totals have empirical σ ≈ 10–14 points (this is well-documented in public literature). σ=12.0 is consistent with the middle of the empirical range. NHL ml σ=4.0 goals was explicitly calibrated: "need a wider sigma (~4.0) to produce realistic 55-65% win probs for typical NHL favorites." The MLB spread σ=3.8 is cited as "empirical F5 run-diff σ≈2.7-2.8" for F5, 3.8 for full-game.
- **Sample size / confidence**: The NBA value is consistent with published research. NHL and MLB values reference empirical distributions without citing specific n.
- **Verdict**: SOLID for NBA (consistent with published literature). QUESTIONABLE for MLB/NHL (calibrated by matching market-implied probabilities rather than measured from outcomes). No formal validation against pick outcomes in the pick_log.

---

### 8D. F5_SIGMA: `{"total": 2.6, "spread": 2.75, "team": 2.0}`

- **Value**: σ for first-5-innings game lines.
- **Calibration**: Code comment: "spread: 2.5→2.75 (empirical F5 run-diff σ≈2.7-2.8)." The spread σ was updated from 2.5 to 2.75 based on empirical F5 run differential data. No n cited.
- **Verdict**: QUESTIONABLE. The spread σ has an empirical basis (though n unspecified). Total and team σ are unvalidated.

---

### 8E. WNBA_EDGE_FLOOR = 0.035

- **Value**: Minimum effective edge for WNBA picks (vs NBA's implicit tier-minimum of 0.03).
- **Calibration**: Code comment: "compensates for wider WNBA vig (~-115/-115 vs NBA -110/-110)." TIER_FINDINGS.md confirms WNBA vig at -115/-115 (6.5% hold) vs NBA -110/-110 (4.5% hold). The 0.035 floor is the NBA minimum (0.03) scaled up to account for wider vig — not a precise calculation but a reasonable adjustment. The exact 0.035 vs 0.04 is judgment.
- **Verdict**: SOLID conceptually. The vig differential justifies a higher edge floor. The specific 0.035 value is judgment-based but directionally correct.

---

### 8F. WNBA Early-Season Edge Dampeners

- Days 4-14: edge × 0.80; Days 15-21: edge × 0.90
- **Calibration**: Research §1 found "−19.8 PTS miss" on WNBA opening day. The dampeners are a judgment call — no formal calibration of how much early-season uncertainty degrades projection accuracy.
- **Verdict**: QUESTIONABLE. Directionally correct (more uncertainty early), but the specific factors (0.80, 0.90) and day thresholds (14, 21) are arbitrary. No post-implementation validation.

---

### 8G. TIERS min_edge values

- T1: 3%, T1B: 3%, T2: 5%, T3: 6%
- **Calibration**: TIER_FINDINGS.md §3-9 provides explicit research backing for each tier's min_edge:
  - T1 (AST, SOG, HRR): "Market efficiency highest of any NBA prop. Hold%: 4-5%... 3% min edge confirmed."
  - T2 (PTS, combos, game lines): "T2 confirmed. 5% min edge confirmed."
  - T3 (3PM, ML_DOG, NRFI): "CV >1.0... hold 20%+... 6% min edge."
  - T1B: "3% min edge confirmed" (directional stat markets with lower limits and softer pricing).
- **Verdict**: SOLID. Each tier's min_edge has a research justification matching market hold%, CV, and historical performance data. The T1 vs T2 WR data (45.1% vs 61.1%) is concerning for T1 but that is a model mis-calibration issue (over-predicted AST/SOG), not a tier-design issue.

---

## Summary Table

| Constant | Verdict | Key Issue |
|---------|---------|-----------|
| SIGMA["PTS"] mult=0.35, min=4.5 | QUESTIONABLE | Not formally calibrated; Platt interaction unknown; under PTS over-performs model |
| SIGMA["AST"] mult=0.45, min=1.3 | QUESTIONABLE | Dead for win_prob (Poisson takes over); affects combo props; AST likely overdispersed |
| SIGMA["REB"] mult=0.58, min=2.5 | QUESTIONABLE | Dead for win_prob; in-range for empirical CV; combo props only |
| SIGMA["SOG"] mult=0.55, min=1.2 | UNKNOWN | Dead for win_prob; reasonable for G14 |
| SIGMA["OUTS"] mult=0.30, min=3.0 | QUESTIONABLE | Band-aid gate G_OUTS_UNDER still exists; no formal n |
| SIGMA["HA"] mult=0.50, min=2.5 | UNKNOWN | In-range but uncalibrated |
| SIGMA["TB"] | UNKNOWN | Dead (TB disabled) |
| NB_R["3PM"] = 12.3 | SOLID | Large sample (n=418 player-seasons), correct within-player methodology; G8D residual at binary threshold |
| NB_R["HRR"] = 1.5 | NEEDS REFIT | Moment-matched at single point; stat disabled; zero-inflation not modeled |
| NB_R["K"] = 5.0 | QUESTIONABLE | No formal n; implied CV higher than empirical range |
| COMBO_RHO NBA (0.333/0.233/0.251) | SOLID | n=75,367 player-games, correct within-player methodology, low sensitivity to error |
| COMBO_RHO_WNBA (0.13/0.04/0.05) | QUESTIONABLE | n=9 players / 336 games — too thin; near-zero values statistically indistinguishable from noise |
| PLATT_A=1.4988, PLATT_B=−0.8102 | NEEDS REFIT | n=76 borderline; no train/test split; non-logit-space; single Platt for all stat-directions fails badly (over AST 25% WR, under PTS 76.9% WR) |
| VAKE_BASE [(0.03,0.05,0.50)…] | SOLID | Far below Kelly; ruin-safe; conservative is correct given model uncertainty |
| pick_score 40/60 WP/edge split | QUESTIONABLE | Not empirically validated against WR; edge-dominance is reasonable philosophy but untested |
| pick_score edge ceiling 15% | SOLID | Compatible with G2 gate (blocks ≥20%); reflects actual p90 |
| PICK_SCORE_TIER_MULT T1=0.90 | QUESTIONABLE | 10% discount for 16pp WR gap is disproportionately small; T1 still appears and loses |
| G1 (prob≥0.70 + edge<0.05) | BAND-AID | Correct direction; arbitrary edge threshold; structural fix is H3 Platt refit |
| G4 (line≤2.5 + prob>0.75) | BAND-AID | Near-dead code given Platt ceiling ~66.6%; reasonable safety net |
| G5 (odds>0 + prob>0.65) | SOLID | Near-certain model error detector |
| G7 (odds≤−150) | SOLID | Standard sharps' rule; well-grounded |
| G7b (−149 to −140 + edge<0.09) | QUESTIONABLE | 9% threshold arbitrary; effectively blocks most heavy-chalk picks |
| G10 (under≤2.5 + edge<0.08) | QUESTIONABLE | 0.08 threshold arbitrary; directionally correct |
| G13B HRR WP floors | UNKNOWN | Dead code (HRR disabled) |
| MIN_WIN_PROB = 0.55 | SOLID | Empirically motivated (n=61, −15.7pp gap); band-aid pending H3 Platt refit |
| MIN_OVER_SCORE = 40 | BAND-AID | Real over-direction gap (−13.6pp, n=61); structural fix is direction-split Platt |
| I6 confidence (GP<10→0.70) | QUESTIONABLE | Edge-only; win_prob not adjusted; asymmetric treatment of uncertainty |
| BLEND_ALPHA = 0.25 | UNKNOWN | Judgment call; no CLV validation against alternatives |
| GAME_SIGMA NBA=12.0 | SOLID | Consistent with published literature |
| GAME_SIGMA NHL/MLB | QUESTIONABLE | Market-matched rather than empirically measured from outcomes |
| WNBA_EDGE_FLOOR = 0.035 | SOLID | Conceptually correct vig adjustment |
| WNBA early-season dampeners | QUESTIONABLE | Directionally correct; factors (0.80, 0.90) are arbitrary |
| TIERS min_edge (3/3/5/6%) | SOLID | Research-backed with CV, hold%, and historical WR data for each tier |

---

## Top Priority Actions

1. **H3 Platt refit** (data-gated at ~300 over_p_raw rows, currently 49): The single most important fix. Implement in logit-space. Add direction split (separate A,B for overs vs unders). Eliminates G1/G4/G5/MIN_OVER_SCORE band-aids structurally.

2. **Calibrate NB_R["K"]** with within-player avg(var/mu) methodology matching 3PM: Current r=5.0 produces CV ≈ 0.59 vs empirical 0.28–0.44. Overestimates K variance.

3. **Apply I6 confidence modifier to win_prob** (not just edge): `adj_wp = 0.50 + (win_prob − 0.50) × conf`. Low effort, fixes P4 asymmetry.

4. **Validate SIGMA["PTS"] by examining over_p_raw distribution**: If over_p_raw clusters near 0.20 and 0.80 instead of spreading across 0.30–0.70, SIGMA is too tight and Platt is over-working.

5. **SIGMA["AST"] and Poisson for AST**: Consider moving AST to NB_STATS with a calibrated r. Wider distribution → lower over-confidence → AST overs naturally filtered. Calibrate r using avg(var/mu) from projections.db.
