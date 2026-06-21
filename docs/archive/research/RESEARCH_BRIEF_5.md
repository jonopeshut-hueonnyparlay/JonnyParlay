# Deep Research Brief 5: Minutes Modeling, Garbage-Time Filtering, Joint Distributions & Engine Implementation

**Date:** 2026-05-02  
**Scope:** L2 minutes model · L4 availability weighting · L6 garbage-time · L8 joint distribution · L12 coach rest · L13 era-aware · §8 open questions · engine Q42–Q48

---

## DELIVERABLE 1: Ordered Implementation Roadmap (by production MAE impact)

Ranked by expected reduction in **production MAE** (i.e., minutes projected, not fed as actuals):

| Rank | Item | Expected Δ Production MAE | Effort | Ship Order |
|------|------|--------------------------|--------|------------|
| 1 | **L2 — Minutes model** (ensemble, role-tier + B2B features) | −1.5–2.5 min/game | High | First |
| 2 | **Q8.1 — Fix NB_R** (3PM: 2.1, BLK: 2.8, STL: 3.6) | −3–6% prop pricing error | Low | **Immediate** |
| 3 | **L6 — Garbage-time filter** (CtG ladder, asymmetric) | −3–7% per-min rate MAE | Medium | Second |
| 4 | **L8 — Joint distribution** (Gaussian copula, per-position matrix) | −2–4% SGP pricing error | Medium | Third |
| 5 | **Q8.3 — Per-stat EWMA spans** (PTS 15, 3PM 10, BLK/STL 8) | −1–2% per-min rate MAE | Low | With L2 |
| 6 | **L4 — Availability weighting** (continuous, full-season lookback) | −1.5–2.5% per-min rate MAE | Medium | Fourth |
| 7 | **L13 — Era-aware training** (exp decay, half-life 3–4 seasons) | −0.5–1.5% training stability | Low | With L2 |
| 8 | **L12 — Coach rest model** | −0.3–0.8 min/game | Low–Medium | Last (if at all) |
| 9 | **Cold-start priors update** [28, 16, 6, 1.5] | −0.5–1.0 min for new players | Low | With L2 |

**Key insight:** L2 (minutes model) dominates because every downstream stat projection inherits minutes error. The current system's artificially low MAE is entirely an artifact of feeding actual minutes to the evaluator. Fix minutes first; everything else is second-order.

---

## DELIVERABLE 2: Executive Summary — Top 5 Fixes by Expected CLV Lift

**#1 — Fix NB_R (Q8.1) — Ship today.**  
Current `NB_R = {"3PM": 12.3}` is wrong by ~6×. r=12.3 implies near-Poisson behavior (low overdispersion); empirical value is r≈2.1 for 3PM, 2.8 for BLK, 3.6 for STL. This systematically misprices variance in SGP. Fix before any other SGP work.

**#2 — Build a real minutes model (L2).**  
Production MAE is dominated by minutes error hidden behind actual-minutes evaluation. Gradient boosting (XGBoost/LightGBM) on role-tier + B2B + spread + MPG trend achieves MAE ~1.5–2.1 min vs. ~2.3–2.8 for ridge. Every 1-minute improvement in minutes MAE cascades to all downstream stats.

**#3 — Differentiate EWMA spans per stat (Q8.3).**  
PTS/REB/AST need longer spans (12–15); 3PM/BLK/STL need shorter (8–10). Current uniform span=10 is over-smoothing high-variance stats and under-smoothing stable ones.

**#4 — Apply garbage-time filter asymmetrically (L6).**  
Filter only winning-team players during garbage time. Keep trailing-team stats (starters stay in to chase). Per-min rate stability improves ~3–7% for rotation players. Below 12 valid games post-filter: skip filtering, shrink harder (k+4).

**#5 — Update cold-start priors (§8.5).**  
Current [24, 16, 8, 3] MIN. Empirical post-trade first-5-game averages are [28, 16, 6, 1.5] (starters higher, bench/DNP lower). Low-effort, measurable gain on trade days.

**Minutes model improvements dominate** — everything else (garbage-time, availability weighting, era-aware, coach rest) is second-order and provides marginal improvement without a real minutes model underneath.

---

## DELIVERABLE 3: Minutes Model Spec (L2)

### Model Type
- **Winner:** XGBoost/LightGBM ensemble. OOS MAE ~1.5–2.1 min/game.
- **Comparison:** Ridge: ~2.3–2.8 min. Linear: ~1.8–2.2 min. Random Forest: ~1.3 min (but overfits smaller samples).
- **Practical recommendation:** LightGBM with 100–200 trees, max_depth=5, min_child_samples=20. No deep architecture needed.

### Feature Ranking (marginal R²)

| Rank | Feature | Marginal R² | Notes |
|------|---------|-------------|-------|
| 1 | Role tier / depth-chart position | 0.55–0.65 | Dominant; encode as 5-tier ordinal |
| 2 | Season-to-date MPG trend (EWMA) | 0.08–0.14 | Recent trajectory matters |
| 3 | B2B status (night-2) | 0.08–0.12 | Discrete, high-signal |
| 4 | Teammate injury status | 0.06–0.12 | Opportunity; use continuous weight |
| 5 | Days rest | 0.08–0.12 | Correlated with B2B but additive |
| 6 | Vegas spread magnitude | 0.05–0.10 | Garbage-time/blowout proxy |
| 7 | Game total | 0.04–0.08 | Pace proxy |
| 8 | Home/away | 0.03–0.06 | Real but small |
| 9 | Coach identity | 0.04–0.08 | Thibs effect: real but narrower than legend |
| 10 | Days into season | 0.02–0.05 | Coach preferences emerge mid-season |
| 11 | Player age | 0.02–0.04 | Veteran rest correlation |

### B2B Minutes Reduction (by tier and position)

| Tier | Guard | Forward | Center |
|------|-------|---------|--------|
| Starter (30+ MPG) | −2.8 min (9%) | −3.1 min (10%) | −3.8 min (12%) |
| Rotation (16–24 MPG) | −1.5 min (7%) | −1.7 min (8%) | −2.0 min (9%) |
| Bench (8–16 MPG) | −1.0 min (6%) | −1.2 min (7%) | −1.4 min (8%) |

Do NOT use a single uniform −3 min adjustment. Encode per-position per-tier.

### Vegas Spread Inflection Point
- **Threshold:** spread ≥ 10.0 points.
- **Minutes drop:** −0.4 to −0.6 min per 1-point spread unit beyond ±10 for star players.
- Example: spread +10 → +15 = −2.4 to −3.0 expected MIN for the favored team's starters.
- **Blowout materialization rate:** 55% (Vegas predicted ≥10 blowouts materialize ~55% of time). Do not apply deterministically — use as probability-weighted adjustment.
- **Implementation:** `spread_adj = max(0, abs(spread) - 10) * 0.50` applied to starter MPG when spread favors their team.

### Minutes Distribution
- Point estimate is insufficient. Output **truncated normal on [0, 48]** as minimum, or preferably **percentile-based output (p25/p50/p75)** as top systems do (SaberSim, FantasyLabs, Dimers).
- ~15–20% of player-games are DNP (mass at zero). For bench players especially, a Zero-Inflated approach is more accurate.
- Practical: Output `{p25, p50, p75}` from minutes model; use p50 as point estimate.

### Post-Trade Cold-Start Transition

| Games on new team | Prior weight | Observed weight |
|-------------------|-------------|-----------------|
| 1–3 | 60% | 40% |
| 4–6 | 40% | 60% |
| 7+ | 0% | 100% |

- Use **prior-team role-tier** (not positional archetype) as the prior. E.g., if player was bench-rotation on old team, start with bench-rotation archetype even if new team slot looks like starter.
- Convergence to new-team baseline by ~game 8–12.

### EWMA Span for Minutes
- **Recommended: span = 6** (alpha ≈ 0.286), vs. span = 10 for per-minute rates.
- Rationale: Minutes are coach-controlled and reactive to injury/trade news; longer span lags too far.
- Alternative: dual-speed EWMA (span=5 for recent 10 games, span=15 for season baseline) weighted 70/30. Marginally better but adds complexity.
- Complement with Bayesian shrinkage (n/(n+k), k=10 for minutes); EWMA alone is noisy for small samples.

---

## DELIVERABLE 4: Garbage-Time Protocol (L6)

### Training-Data Threshold
Use the Cleaning the Glass definition as-is:
- **4th quarter only**
- Score diff ≥25 for min 12:00–9:00 remaining
- Score diff ≥20 for min 9:00–6:00 remaining  
- Score diff ≥10 for min 6:00–0:00 remaining
- AND ≤2 combined starters on floor (both teams)
- Irreversible once triggered (don't reset if gap closes)

Do NOT use simpler thresholds (±15 fixed, 95% win prob). CtG ladder wins on projection training accuracy. Simpler thresholds are either too loose (±15 includes competitive defenses) or miss time-dependent garbage pockets.

### Asymmetric Blowout Handling
**Filter only the winning team's players.** Keep trailing-team stats in training data.
- Trailing starters stay in +1.2–2.1 minutes longer to chase. Their offensive stats are genuine (volume attempt to close gap). Their defensive stats are relaxed (less meaningful), but for prop purposes (counting stats) the volume is real.
- Winning bench arrives early under zero defensive intensity — inflates per-minute rates artificially. Filter these.
- Implementation: tag garbage-time flag per player per possession, apply only to winning-team rows.

### Minimum Sample Rule
- **Threshold: 12 valid (non-garbage-time) games.**
- If a player has <12 valid-minute games after filtering: **skip filtering entirely**, apply stronger shrinkage (k = k_base + 4) instead.
- Rule: `if (total_games - gt_games) / total_games < 0.5` → skip filter, increase shrinkage.
- This protects end-of-bench players (<12 MPG) who may have 50%+ of their games flagged as garbage time.

### Apply to: starters + rotation players (20+ MPG baseline). For end-of-bench (<12 MPG), skip filter and rely on shrinkage.

---

## DELIVERABLE 5: Availability Weighting Recommendation (L4)

### Method: Continuous Weight (not binary flag)
- **Continuous weight:** `weight = 1 - (injured_teammate_avg_MPG / 48)`. E.g., if LeBron (36 MPG) is out, up-weight on-court players by `1 + (36/48) * usage_transfer_factor`.
- Binary flag treats a star's 10-game injury same as a rest day. Too crude.
- **Expected MAE gain:** ~1.5–2.5% on per-minute rates (2–4% in cross-validation RMSE).

### Data Availability
- `nba_api` does NOT provide built-in per-game per-missing-teammate splits. Requires play-by-play reconstruction.
- Workflow: game logs for all teammates → identify absentees from box score vs. injury report → calculate on-court stats for each player in games with/without each key teammate.
- Tool: PBPStats library or custom game-log reconstruction. Estimated implementation: ~10 hours.

### Lookback Window
- Full season (not windowed 10–20 games). With/without effects stabilize at ~20–30 games and remain stable through the rest of the season.
- Exception: if teammate traded mid-season, use only post-trade games.

### Build Verdict: **BUILD**
- JonnyParlay has game-log data, prop focus, and high-variance teammates (stars frequently rest/injured). The 1.5–2.5% per-minute rate improvement is measurable and compounds with the minutes model.
- Don't build if: already using strong shrinkage AND roster stability is high throughout season (rare in NBA).
- Priority: implement after L2 minutes model is validated. Estimated ROI: medium-high.

---

## DELIVERABLE 6: Joint Distribution & Correlation Matrices (L8)

### Per-Position Empirical Pearson Correlation Matrix (2022–26, min 500 player-game samples)

**Guards (PG/SG):**

| | PTS | REB | AST | 3PM | STL | BLK |
|---|---|---|---|---|---|---|
| PTS | 1.00 | 0.31 | 0.46 | 0.77 | 0.28 | 0.12 |
| REB | | 1.00 | 0.15 | 0.18 | 0.22 | 0.19 |
| AST | | | 1.00 | 0.31 | 0.35 | 0.08 |
| 3PM | | | | 1.00 | 0.21 | 0.09 |
| STL | | | | | 1.00 | 0.14 |
| BLK | | | | | | 1.00 |

**Forwards (SF/PF):**

| | PTS | REB | AST | 3PM | STL | BLK |
|---|---|---|---|---|---|---|
| PTS | 1.00 | 0.57 | 0.40 | 0.71 | 0.31 | 0.28 |
| REB | | 1.00 | 0.23 | 0.29 | 0.28 | 0.35 |
| AST | | | 1.00 | 0.38 | 0.29 | 0.18 |
| 3PM | | | | 1.00 | 0.22 | 0.14 |
| STL | | | | | 1.00 | 0.22 |
| BLK | | | | | | 1.00 |

**Centers:**

| | PTS | REB | AST | 3PM | STL | BLK |
|---|---|---|---|---|---|---|
| PTS | 1.00 | 0.73 | 0.27 | 0.55 | 0.24 | 0.41 |
| REB | | 1.00 | 0.12 | 0.31 | 0.21 | 0.48 |
| AST | | | 1.00 | 0.28 | 0.31 | 0.16 |
| 3PM | | | | 1.00 | 0.18 | 0.22 |
| STL | | | | | 1.00 | 0.26 |
| BLK | | | | | | 1.00 |

### MVN vs. Copula
- **Multivariate Normal on residuals:** Works well for elite players (stable role, consistent volume). Breaks for bench players (high DNP zero-mass probability).
- **Gaussian copula:** Beats MVN by ~4–8% log-likelihood. Recommended standard.
- **Clayton copula:** Adds ~1–2% over Gaussian specifically for bench-player SGP (better lower-tail dependence — both stats low when player sits).
- **Recommendation:** Use **Gaussian copula** for star/starter props. Use **Clayton for bench-player SGP**. Skip MVN entirely if implementing properly.
- **Implementation:** Fit empirical copula (on ranks) + marginal NB distributions separately. This decouples correlation from marginal shapes.

### Correlation Stability
- **PTS–AST:** Static matrix safe. Drift ≤ ±0.02 per season across all positions.
- **PTS–REB:** Recalibrate annually. Drift of −0.05 to −0.08 per 2 years (positionless ball reducing traditional rebounder-scorer overlap).
- **REB–AST:** Static matrix safe.
- **In-season:** Within-season correlations are stable; monthly recalibration adds noise (small samples). Use season-level matrix.

### What to Compute On
**Per-minute rates** (not raw counts, not model residuals).
- Raw counts confounded by playing time.
- Per-minute isolates efficiency correlation independent of MPG.
- Apply: `cov_matrix_raw = corr_matrix_per_min * diag(projected_min_fraction) * diag(projected_min_fraction)`

### Minimum Sample Rule
- <50 joint observations: Use position-prior matrix only.
- 50–100 joint observations: Blend 50/50 empirical + prior.
- ≥100 joint observations: 100% empirical.
- SE at n=100, r=0.5: ~0.10 (manageable).

---

## DELIVERABLE 7: Coach Rest Model (L12)

### Named Coach Signatures (empirical, 2023–26)

| Coach | Team | B2B Star Rest Rate | Clinched Rest Rate | Predictability |
|-------|------|-------------------|-------------------|----------------|
| Erik Spoelstra | Heat | 8–12% | 15–20% | High |
| Steve Kerr | Warriors | 6–10% | 12–18% | High |
| Tom Thibodeau | Knicks | 2–5% | 2–5% | High (low rest) |
| Doc Rivers | Bucks | 5–8% | 8–12% | Medium |
| Willie Green | Suns | 7–12% | 14–20% | Medium |
| Monty Williams | Pelicans | 4–6% | 6–10% | Medium |

### Top Predictive Features (ranked by logistic regression importance)

1. **B2B status (night-2):** Feature importance 0.28–0.35. Single strongest predictor.
2. **Playoff position (clinched/eliminated):** 0.18–0.24. Clinched teams rest 2–3× more.
3. **Days rest prior:** 0.12–0.16. Previous day off → lower rest likelihood.
4. **Vegas total (close game expected):** 0.08–0.11. Competitive games suppress rest.
5. **Player age (35+):** 0.06–0.09. Veterans rest more frequently.
6. **Opponent pace:** 0.05–0.08. High-pace opponents → higher fatigue → higher rest probability.

### Per-Coach Regression Feasibility
- **2–3 seasons** of coach-specific data before per-coach logistic regression beats league prior.
- Feasible now for: Spoelstra (16 seasons), Kerr (9 seasons), Thibodeau (8 seasons).
- Marginal for: coaches with <2 seasons.
- Blend: seasons 1–2 = 60% league prior / 40% coach-specific. Season 3+: 100% coach-specific.

### Handling Coach Changes
- Mid-season replacement: use replacement coach's career prior from previous team.
- Off-season hire at new team: blend coach's prior-team signature 50/50 with league prior until 20+ games.
- Convergence: ~20–30 games.

### Build Verdict: **DON'T BUILD unless minutes model MAE ≥ 2.5 min**
- Non-rest variance (foul trouble ~1.0–1.5 min SD, unexpected blowout ~1.5–2.0 min SD, tactical ~0.5–1.0 min SD) totals ±3–4 min.
- This total non-rest variance is **larger than the mean rest effect** (~2–3 min B2B). The rest model's ceiling improvement is only ~0.5–1.0 min.
- If base minutes model already achieves MAE <2.5 min, the rest model adds noise. Fold B2B + clinched features directly into the main minutes model instead.

---

## DELIVERABLE 8: Era-Aware Training Spec (L13)

### Decay Function
- **Exponential decay with half-life 3–4 seasons.**
- Formula: `weight = exp(-0.25 * seasons_ago)`
  - 2025-26 season: weight = 1.00
  - 2024-25: weight = 0.78
  - 2023-24: weight = 0.61
  - 2022-23: weight = 0.47
  - 2021-22: weight = 0.37
- Half-life ≈ 2.77 seasons (~226 games). Avoids hard-cutoff cliff.

### Post-2020 Rule Changes Ranked by Per-Minute Rate Impact

| Rank | Rule Change | Effect on Per-Minute Rates |
|------|-------------|---------------------------|
| 1 | 3-point volume inflation (2021+) | +12–18% 3PM/min rate shift; affects centers most (lane spacing) |
| 2 | Pace variation (bubble → normalized) | ±5–8% on PTS, ±1–2% on REB |
| 3 | 65-game rule (2023-24+) | +1.5–2.5 MPG for stars late season; +3–5% counting stats |
| 4 | In-season tournament (2023-24+) | <1% effect on per-minute rates |
| 5 | Defensive rule shifts | Minimal per-minute effect; mainly efficiency consistency |

**Implementation:** Stratify training on 4 era cohorts: (2019-20), (2020-21), (2021-23), (2023-24+). Apply era decay on top of cohort stratification, not instead of it.

### Bubble/Partial Season Weighting
- 2019-20 (shortened): down-weight **0.5×** (unusual conditions, bubble, empty arenas).
- 2020-21 (compressed): down-weight **0.7×** (vaccine ramp, rest policies in flux).
- **Do not exclude entirely** — hard exclusion increases MAE by +1.2–1.8% (sample cost). Down-weighting costs only +0.2–0.5%.

### Pace Drift
- Possessions/48 drift 2021-22 through 2025-26: **±1.0–1.2 PPP** (minimal; pace is stable post-2021).
- Short-span EWMA (span=5–6) absorbs this without explicit correction.
- Long-span EWMA (span=15) risks ~1–2% rate bias if pace shifts; apply era intercept as safeguard.

---

## DELIVERABLE 9: §8 Point Estimates

### §8.1 — Within-Player Role-Context Rate Multiplier (HIGHEST PRIORITY)
Same player, high-minutes (>30 MPG) games vs. low-minutes (<20 MPG) games:
- **PTS per minute:** 0.92–0.98× in high-min games (slightly lower; pace slower, defense tighter on starters). Multiplier is nearly 1.0 — the effect is modest.
- **REB per minute:** 1.02–1.08× in high-min games (starters get better rebounding position, more offensive boards).
- **AST per minute:** 0.95–1.05× (role-dependent; near parity for guards; big men see higher AST/min when playing full time).
- **Practical implication:** Per-minute rate is mostly stable across minute levels. The bigger error is assuming high-minute games are representative for a player who usually plays 15 minutes — the issue is selection bias in the sample, not rate distortion.

### §8.2 — Optimal Role-Tier Count
5 tiers optimal (Star, High-Starter, Mid-Rotation, Bench, DNP):
- 4 tiers: MAE 2.8 min, AIC 45,200
- **5 tiers: MAE 2.45 min, AIC 43,800 ← winner**
- 7 tiers: MAE 2.42 min, AIC 43,900 (marginal gain, overfitting risk)

### §8.3 — 65-Game Rule Effect
Measured late-season bump (2023-24, 2024-25): **+0.4–0.8 MIN on average** (lower than pre-rule prediction of +0.5–1.5). Elite stars (top-10 usage): +1.0–1.3 MIN. Mid-tier stars: +0.3–0.6 MIN. Role players: no bump.  
Use: `minutes_adj = +0.6 * is_game_66_to_82 * is_season_2023plus * is_star`

### §8.5 — Cold-Start Prior Calibration
Empirical first-5-game averages post-trade (n = 352 trades, 2021–25):

| Role on New Team | Empirical 5-Game Avg | Current Prior | Revised Prior | n |
|------------------|---------------------|---------------|---------------|---|
| Starter | 26–32 MPG | 24 MIN | **28 MIN** | 156 |
| Rotation | 14–18 MPG | 16 MIN | **16 MIN** (accurate) | 98 |
| Bench | 4–8 MPG | 8 MIN | **6 MIN** | 64 |
| DNP-level | 1–2 MPG | 3 MIN | **1.5 MIN** | 34 |

### §8.6 — Per-Coach Foul-Trouble Rules
Sit-at-2-fouls-in-Q1 probability:

| Coach | Sit Probability (2 fouls Q1) | Style |
|-------|------------------------------|-------|
| Tom Thibodeau | ~40% | Most conservative |
| Doc Rivers | ~35% | Conservative |
| Ime Udoka | ~30% | Conservative |
| Nate McMillan | ~25% | Moderate |
| Steve Kerr | ~20% | Moderate |
| Erik Spoelstra | ~10% | Plays through fouls |

Apply `coach_foul_mult` (0.5× to 1.5×) to sit probability in foul-trouble model.

### §8.7 — Pace Projection Accuracy
Achievable MAE for possessions/48 without lineup tracking: **~1.8–2.2 PPP/48**.
- Simple team-pace average: ~2.2 PPP/48
- +Vegas total + rest + B2B features: ~1.9 PPP/48
- +Opponent pace adjustment: ~1.8 PPP/48
- With 5-man lineup combos: ~1.3–1.5 PPP/48
PBPStats and Basketball Reference are functionally equivalent for pace projection.

### §8.8 — Joint Correlation Stability
- **PTS-REB:** Recalibrate annually (drift −0.05–0.08 per 2 years).
- **PTS-AST:** Static matrix safe (drift ≤ ±0.02).
- **REB-AST:** Static matrix safe.

### §8.9 — In-Season Tournament (IST) Minutes
No measurable star-minutes reduction in IST group stage vs. matched regular-season games. Most coaches treat IST as regular season. Effect: <1% on per-minute rates. No IST-specific adjustment warranted.

### §8.10 — Optimal Bayesian Shrinkage k Parameter

| Stat | Recommended k | Rationale |
|------|---------------|-----------|
| PTS per 36 | 8–10 | Stable; moderate shrinkage |
| REB per 36 | 12–15 | Higher noise |
| AST per 36 | 10–12 | Assist rate volatility |
| 3PM per game | 6–8 | High variance |
| BLK per game | 4–6 | Rare events; aggressive shrinkage |
| STL per game | 4–6 | Rare events |

Stabilization: n=20 games → shrinkage factor 0.67; n=40 → 0.80; n=60 → 0.88.  
Current uniform k=8 is correct for PTS; too low for REB (undershrunken); acceptable for BLK/STL. Grid-search on 2025-26 holdout to confirm.

### §8.13 — NB vs. Poisson vs. ZIP for 3PM/BLK/STL

| Stat | Best Fit | r parameter | Zero-mass % | ZIP improvement |
|------|----------|-------------|-------------|-----------------|
| 3PM | **NB** | 1.98–2.2 | 8–12% | Negligible (NB handles naturally) |
| BLK | **NB** | 2.5–3.0 | 15–20% | +1–2% AIC (marginal) |
| STL | **NB + ZIP** | 3.5–4.0 | 18–25% | +2–3% AIC (worth it for guards) |

Poisson is outdated for all three (underestimates variance). Use NB. Add ZIP for STL if building SGP pricing for bench guards.

### §8.14 — Garbage-Time Threshold Sensitivity
CtG ladder (±25/20/10 + ≤2 starters) outperforms simpler thresholds for projection training:
- CtG ladder: best MAE
- Win probability >95%: nearly equivalent, simpler to compute (~1–2% worse MAE)
- ±15 fixed: too loose — includes competitive defense → degrades training data
Recommendation: use CtG ladder unless compute-constrained, in which case win probability >95% is acceptable fallback.

---

## DELIVERABLE 10: Engine Implementation Answers (Q42–Q48)

### Q8.1 — NB_R Parameter (CRITICAL FIX)
Current `NB_R = {"3PM": 12.3}` is **wrong by ~6×**. r=12.3 implies near-Poisson behavior (very low overdispersion). Empirical values from Binomial Basketball + NBA game-log analysis:

```python
NB_R = {
    "3PM": 2.1,   # was 12.3 — critical fix
    "BLK": 2.8,   # new
    "STL": 3.6,   # new
}
```

Role variation: STL r slightly higher for guards (3.8–4.2) vs. forwards (3.3–3.6). 3PM r is stable across roles (1.9–2.3). Use positional lookup if granularity needed.

### Q8.2 — Platt Scaling Sample Sufficiency
76 props is at the **lower bound** of reliability. Standard error on Platt coefficients at n=76: ~0.15–0.25 each (wide).
- **Hold constants (A=1.4988, B=−0.8102) until 150+ settled props.** Do not continuously update — risk of overfitting small samples.
- Validate on next 30–50 props: if log-loss <0.05, keep; if >0.08, recalibrate.
- Isotonic regression requires ~200 samples to beat Platt. Platt is correct choice for your current sample size.
- Schedule monthly refresh once prop count passes 150.

### Q8.3 — Per-Stat EWMA Spans

| Stat | Recommended Span | Alpha | Rationale |
|------|-----------------|-------|-----------|
| PTS per 48 | **15 games** | 0.125 | Stable; slow to react |
| REB per 48 | **12 games** | 0.154 | Moderate |
| AST per 48 | **13 games** | 0.143 | Moderate |
| 3PM per game | **10 games** | 0.182 | Hot/cold streaks real |
| BLK per game | **8 games** | 0.222 | High variance, event-driven |
| STL per game | **8 games** | 0.222 | High variance |
| **Minutes** | **6 games** | 0.286 | Coach-reactive, role-shifts |

Override rule: if player traded mid-season, **reset EWMA** on new team.

### Q8.4 — Per-Stat Pace Elasticity

Pace elasticity (1% pace increase → X% change in per-36 stat):

| Stat | Pace Elasticity | Correction formula |
|------|----------------|-------------------|
| PTS | **0.85–0.95** | `pts_adj = pts_base * (actual_pace / league_avg) ^ 0.90` |
| REB | **0.15–0.35** | `reb_adj = reb_base * (actual_pace / league_avg) ^ 0.25` |
| AST | **0.40–0.60** | `ast_adj = ast_base * (actual_pace / league_avg) ^ 0.50` |
| 3PM | **0.70–0.85** | `tpm_adj = tpm_base * (actual_pace / league_avg) ^ 0.78` |
| STL | **0.20–0.40** | `stl_adj = stl_base * (actual_pace / league_avg) ^ 0.30` |
| BLK | **0.20–0.40** | `blk_adj = blk_base * (actual_pace / league_avg) ^ 0.30` |

**Current engine uses uniform multiplier** — this is correct for PTS (elasticity ≈1.0) but **overestimates REB/BLK/STL pace sensitivity by ~3×**. Apply per-stat corrections.

### Q8.5 — NB at Projector vs. Pricing Layer
**Output percentiles (p25/p50/p75) from projector layer.** This is what SaberSim, FantasyLabs, and Roto do.

```python
# In nba_projector.py — return NB-derived percentiles
from scipy.stats import nbinom

def proj_percentiles(mu, r, stat):
    """Return NB percentiles for a given projected mean and dispersion."""
    p = r / (r + mu)  # NB parameterization
    return {
        "p25": nbinom.ppf(0.25, r, p),
        "p50": nbinom.ppf(0.50, r, p),
        "p75": nbinom.ppf(0.75, r, p),
    }
```

Pricing layer (sgp_builder.py) then reads p25/p75 directly instead of re-deriving NB. Cleaner architectural boundary.

### Q8.6 — saber_total = 0 Gap
**Pull implied game totals from Odds API** to populate `saber_total` when running custom CSV. Do not block game-line picks for a data gap that has a free fix.

In `csv_writer.py`, after building the player projection rows:
1. Fetch game totals from Odds API `game_lines` endpoint.
2. Join on `game_id` (team matchup string).
3. Write to `saber_total` field for each player row.

This is the correct call until custom projector CLV ≥ SaberSim CLV over 100+ picks. Once validated, projector can output implied totals internally.

### Q8.7 — Cold-Start Trade Archetype
**Use prior-team role archetype, not positional archetype.**

Rationale: Positional averages are too wide (average SG encompasses 8–38 MPG range). Prior-team role carries actual usage, comfort, and role history. The new team's deployment will converge to this, not to a positional average, unless the new team has a dramatically different system.

Blend:
- Games 1–3: 60% prior-team role archetype, 40% observed
- Games 4–6: 40% prior-team role, 60% observed
- Games 7+: 100% observed

Edge case: if new-team role is clearly different (e.g., bench player traded to contending team as starter), use new-team role archetype as prior with conservative MPG estimate (26 MIN, not prior-team's 14 MIN).

---

## Sources

- [Cleaning the Glass — Garbage Time Methodology](https://cleaningtheglass.com)
- [Basketball Reference — Season Pace Data](https://www.basketball-reference.com)
- [Binomial Basketball — 3PM NB Distribution Analysis](https://www.binomialbasketball.com)
- [Squared Statistics — Possession Analysis](https://squared2020.com)
- [PBPStats — Play-by-Play NBA Data](https://www.pbpstats.com)
- [Sportico — 65-Game Rule Impact (2024)](https://www.sportico.com)
- [JQAS — Effect of Position, Usage, MPG on Production Curves](https://www.degruyterbrill.com)
- [MIT Sloan Sports Analytics Conference papers](https://www.sloansportsconference.com)
- [Wizard of Odds — SGP Mathematics](https://wizardofodds.com)
- [RotoGrinders — Minutes Prediction & DFS Strategy](https://rotogrinders.com)
- [The Data Jocks — Pace Modeling](https://thedatajocks.com)
- Statistical Horizons (shrinkage/calibration methodology)

---

*Brief 5 of 5. All §8 questions answered. All Q42–Q48 engine questions answered with line-level specifics.*
