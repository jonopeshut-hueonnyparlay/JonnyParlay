# Audit 2026-05-25 — Track E: Gate Empirical Validation

Auditor: Claude Sonnet 4.6 (automated)
Data source: data/pick_log.csv — primary/bonus picks, result IN (W, L)
**n = 182 settled primary/bonus picks** (as of 2026-05-23, last settled pick)

**N < 30 rule: any empirical finding with n < 30 is PROVISIONAL — cap severity at MEDIUM.**

---

## E1. Sample Size Audit

| Gate | n at implementation | n today | Sufficient (≥30)? |
|------|--------------------|---------|--------------------|
| G8B (AST over ≤4.5) | ~8 | 8 | NO — PROVISIONAL |
| G8C (SOG under ≤3.5) | 14–27 | 41 | YES |
| G8D (3PM over ≤1.5) | 16 | 16 | NO — PROVISIONAL |
| TEAM_TOTAL over block | 11 | 11 | NO — PROVISIONAL |
| MIN_WIN_PROB=0.55 | 39 (below 0.55) | 39+ | YES |
| MIN_PICK_SCORE=25 | post-hoc | — | — |

**G8B** implemented at n≈8 AST over picks total — below the n=30 threshold. **PROVISIONAL at implementation**. Current record (0-5 blocked, 2-3 allowed) is directionally clear but statistically thin.

**G8D** implemented at n=16 total 3PM over ≤1.5 picks — borderline. Gap is −20pp which is large. **PROVISIONAL** but directionally confirmed.

**TEAM_TOTAL over block** n=11 — clearly PROVISIONAL. Already in CLAUDE.md as provisional. Block is in place per May 25 audit.

---

## E2. Stat-Direction Performance (n ≥ 10)

| Stat+Dir | n | WR% | AvgModelWP% | Gap | P&L | Gate? |
|----------|---|-----|------------|-----|-----|-------|
| SOG under | 41 | 48.8% | 59.9% | −11.1pp | −2.77u | G8C blocks ≤3.5 |
| REB under | 26 | 53.8% | 62.0% | −8.1pp | +2.17u | None |
| PTS over | 20 | 65.0% | 67.7% | −2.7pp | +3.42u | None |
| 3PM over | 17 | 47.1% | 70.4% | −23.3pp | −3.25u | G8D blocks ≤1.5 |
| 3PM under | 15 | 60.0% | 59.4% | +0.6pp | +4.90u | None |
| PTS under | 13 | 76.9% | 63.6% | +13.3pp | +5.90u | None |
| TEAM_TOTAL over | 11 | 45.5% | 51.4% | −5.9pp | −1.27u | Blocked (May 25) |
| ML_FAV win | 9 | 55.6% | 62.0% | −6.5pp | −0.01u | PROVISIONAL (n<30) |
| AST over | 8 | 25.0% | 65.3% | −40.3pp | −4.46u | G8B blocks ≤4.5 |
| AST under | 7 | 71.4% | 64.0% | +7.5pp | +2.80u | None |

**Key observations:**
- **AST over (n=8)**: 0-5 in blocked range, 2-3 in allowed range. G8B gate is justified despite thin n.
- **3PM over (n=17)**: Highest model-vs-actual gap (−23.3pp). G8D captures the worst bucket (≤1.5). NB_R update to r=9.15 should narrow the gap for future picks.
- **PTS under (n=13)**: Over-performing (+13.3pp above model WP). Consider whether this is genuine or variance. PROVISIONAL.
- **ML_FAV (n=9)**: Break-even at −0.01u. PROVISIONAL — do not act.

**Blocked pairs where block covers the loss:**
- SOG under: G8C blocks ≤3.5. Historical SOG under as whole is −2.77u; higher lines are rare.
- 3PM over: G8D blocks ≤1.5. Remaining picks >1.5 (n=1) insufficient to evaluate.
- AST over: G8B blocks ≤4.5. 0-5 record in blocked range.

**Premature blocks (n<30 at implementation):**
- G8B (AST over ≤4.5): implemented at n≈8. **PROVISIONAL but directionally supported.**

---

## E3. Tier Performance (n ≥ 5)

| Tier | n | WR% | AvgModelWP% | Gap | P&L |
|------|---|-----|------------|-----|-----|
| T2 | 58 | **60.3%** | 62.3% | −2.0pp | +8.82u |
| T1B | 30 | 53.3% | 59.8% | −6.4pp | +0.54u |
| T3 | 31 | 51.6% | 64.9% | −13.2pp | −0.46u |
| T1 | 58 | **46.6%** | 58.9% | −12.4pp | **−6.46u** |
| KILLSHOT | 5 | 60.0% | 74.4% | −14.4pp | +0.73u |

**T1 vs T2**: T2 outperforms T1 by 13.7pp WR and +15.28u over same pick count (n=58 each). T1 is almost entirely SOG + AST picks (56/58 = 97%); both are over-predicted by the model. G8B/G8C partially address this; H3 Platt refit will address the residual.

**KILLSHOT (n=5)**: PROVISIONAL — do not draw conclusions.

**n ≥ 30 for conclusions?** T1 and T2: YES (n=58). T3 and T1B: YES (n=30–31, borderline). KILLSHOT: NO.

---

## E4. Pick Score Predictive Validity

| Score Bucket | n | WR% | P&L |
|-------------|---|-----|-----|
| <30 | 32 | 37.5% | −9.09u |
| 30–40 | 30 | 40.0% | −7.09u |
| 40–50 | 18 | 61.1% | +3.00u |
| 50–60 | 8 | 62.5% | +1.54u |
| 60–70 | 18 | 66.7% | +4.91u |
| 70+ | 76 | 59.2% | +9.91u |

**Empirical break point: score = 40, not score = 25.**
- Scores <40 (n=62): combined WR=38.7% — systematic losers
- Scores ≥40 (n=120): combined WR=61.7% — winners
- WR gap: 23.0pp — pick_score is doing real predictive work

**Current MIN_PICK_SCORE=25** cuts only the absolute bottom but leaves the 25–40 range in play. That range (n=30+) has 40% WR. The data clearly supports raising to **40** (n=62 in <40 bucket is above n≥30 threshold), but this is a major volume change requiring deliberate decision.

**The 0.55–0.60 WP bucket (n=24, WR=33.3%)** has avg pick_score=33.6. These are doubly low-conviction picks. A MIN_PICK_SCORE raise to 40 would disproportionately filter this bucket.

---

## E5. Odds Bucket Performance

| Bucket | n | WR% | Break-even | P&L |
|--------|---|-----|------------|-----|
| ≤−150 | 1 | 0.0% | 60.8% | −1.00u |
| −149 to −130 | 56 | 62.5% | 58.1% | +4.28u |
| −129 to −110 | 60 | 55.0% | 54.5% | +0.69u |
| −109 to −101 | 11 | 45.5% | 51.0% | −1.16u |
| +100 to +119 | 15 | 46.7% | 47.8% | −0.34u |
| +120 to +149 | 33 | 42.4% | 43.4% | −0.81u |
| +150+ | 6 | 50.0% | 38.0% | +2.09u |

**Key finding:** The −149 to −130 (chalk) bucket is the model's strongest (+4.28u, WR=62.5% vs 58.1% BE). The +100 to +149 combined bucket (n=48) is losing at 43.8% WR.

**+100 to +149 losing (n=48)**: Above n≥30 threshold combined. The model consistently over-prices picks in the plus-money range. Root cause is structural over-prediction (Platt not fully correcting), not a price-specific market inefficiency. A gate on odds range would be a band-aid. Platt H3 refit is the correct fix.

**−109 to −101 bucket (n=11)**: PROVISIONAL — do not act.

---

## E6. Calibration Check

**Overall:**
- n=182, WR=53.30%, AvgModelWP=63.31%
- **Gap: −10.01pp — confirmed systematic over-prediction**
- 95% CI on WR: 53.30% ± 7.25pp = [46.05%, 60.55%]
- AvgModelWP of 63.31% is **outside the 95% CI upper bound (60.55%)**
- **Conclusion: Systematic over-prediction is statistically confirmed at 95% confidence. Not variance.**

**WP Bucket Calibration:**

| WP Range | n | WR% | AvgModelWP% | Gap | P&L |
|---------|---|-----|------------|-----|-----|
| 0.50–0.55 | 37 | 43.2% | 52.1% | −8.9pp | −6.46u |
| 0.55–0.60 | 24 | 33.3% | 56.9% | −23.6pp | −8.73u |
| 0.60–0.65 | 24 | 58.3% | 62.4% | −4.1pp | +2.73u |
| 0.65–0.70 | 42 | 66.7% | 68.1% | −1.4pp | +11.45u |
| 0.70–0.80 | 48 | 54.2% | 72.0% | −17.8pp | +1.63u |

**Three-cluster pattern:**
1. **0.50–0.60 (n=61): WR=39.3%, P&L=−15.19u** — consistent systematic loser. The 0.55–0.60 bucket is actually *worse* than 0.50–0.55 (33.3% vs 43.2% WR), driven by compositional problem: avg pick_score in the 0.55–0.60 band is only 33.6.
2. **0.60–0.70 (n=66): WR=63.6%, P&L=+14.18u** — well-calibrated. Model and reality aligned.
3. **0.70–0.80 (n=48): WR=54.2%, P&L=+1.63u** — over-inflated by Platt (raw→calibrated inflation at high end). Still profitable due to heavy-juice payouts.

**By Sport:**

| Sport | n | WR% | AvgModelWP% | Gap | 95% CI | P&L |
|-------|---|-----|------------|-----|--------|-----|
| NBA | 117 | 54.7% | 63.9% | −9.2pp | ±9.0pp | +5.18u |
| NHL | 54 | 51.9% | 56.9% | −5.0pp | ±13.3pp | −0.55u |
| MLB | 11 | 45.5% | 59.3% | −13.8pp | ±29.4pp | −1.46u |

- **NBA**: Gap −9.2pp, statistically significant (AvgWP=63.9% just above CI upper bound 63.7%).
- **NHL**: Gap −5.0pp inside CI. Not statistically confirmed. **PROVISIONAL.**
- **MLB**: Gap −13.8pp but CI ±29.4pp (n=11). **Completely inconclusive. PROVISIONAL.**

---

## Summary: Key Flags

**Statistically confirmed (n≥30), action warranted:**

| Issue | n | Status |
|-------|---|--------|
| Overall model over-prediction by 10pp | 182 | Awaits H3 Platt refit — correct fix |
| 0.55–0.60 WP bucket worst performer (33.3% WR) | 24 | MIN_WIN_PROB gate helps partially; core fix is Platt |
| Pick score <40 = systematic loser (38.7% WR) | 62 | MIN_PICK_SCORE=25 is too low; empirical break is 40 |
| +100–+149 odds bucket losing | 48 | Root cause: Platt over-inflation, not price gate needed |
| T1 tier deeply underperforms T2 (13.7pp WR gap) | 58/58 | G8B/G8C address part; H3 Platt needed for rest |

**Provisional flags (n<30, monitor only, do not act):**
- TEAM_TOTAL over block (n=11)
- G8B scope (n=8 AST over total)
- G8D scope (n=16 3PM over ≤1.5)
- ML_FAV performance (n=9)
- PTS under out-performance (n=13)
- NHL over-prediction (gap inside CI)
- MLB calibration (n=11, CI ±29.4pp)
- KILLSHOT tier (n=5)

**H3 gate progress:** 50/100 graded `over_p_raw` rows. Pre-Platt bias shows overs are catastrophically over-projected even before Platt adjustment — Platt is partially correcting but not enough. Gate at 100 rows remains appropriate.
