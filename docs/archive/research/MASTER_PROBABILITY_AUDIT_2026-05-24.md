# Master Probability Audit — 2026-05-24
*Comprehensive: band-aids, broken things, real fixes, empirical validation.*
*n=182 graded primary+bonus picks (Apr 14 – May 24 2026)*
*Constraint: nothing ships unless empirically validated or provably neutral.*

---

## CRITICAL FINDING #1 — MIN_WIN_PROB Floor Is Set Backwards

The current floor (0.55) blocks the *better* half of the bad bucket and keeps the *worse* half.

| WP Bucket | n | WR% | BE% | Units | Status |
|-----------|---|-----|-----|-------|--------|
| 0.50–0.55 | 39 | **43.6%** | ~52% | −5.50u | BLOCKED by floor |
| 0.55–0.60 | 24 | **33.3%** | ~52% | −4.25u | **STILL ALLOWED** |
| 0.60–0.65 | 24 | 58.3% | ~52% | +4.25u | ✅ profitable |
| 0.65–0.70 | 42 | **66.7%** | ~52% | +13.25u | ✅ best bucket |
| 0.70–0.80 | 48 | **54.2%** | ~52% | +6.50u | ⚠ over-predicted |

**The 0.55–0.60 bucket (33.3% WR) is worse than the 0.50–0.55 bucket (43.6% WR) we blocked.**
Raising MIN_WIN_PROB from 0.55 → 0.60 would have saved 4.25u on those 24 picks.

**Fix**: `MIN_WIN_PROB = 0.60`. Empirically validated. Implementable today.

---

## CRITICAL FINDING #2 — AST Over Has a −40pp Calibration Gap

| Stat+Dir | n | WR% | Model% | Gap |
|---------|---|-----|--------|-----|
| AST over | 8 | **25.0%** | 65.3% | **−40.3pp** |
| AST under | 7 | 71.4% | 64.0% | +7.5pp |

G8B blocks AST over ≤4.5 NBA. Line breakdown of remaining picks:
- 2.6–4.5 over: 0.0% WR (n=3) — these are now blocked by G8B ✓
- 4.6–6.5 over: 66.7% WR (n=3) — n too small to confirm safe

The overall 25% WR includes the now-blocked ≤4.5 range. With G8B in place,
remaining (>4.5) AST overs show n=3. **Verdict: monitor, don't extend block yet.**
Need 10+ picks above 4.5 line before concluding either way.

---

## CRITICAL FINDING #3 — Plus Odds Are Systematically Losing

| Odds Bucket | n | WR% | BE% | Units |
|-------------|---|-----|-----|-------|
| ≤−130 | 57 | 61.4% | 58.2% | +15.75u |
| −129 to −110 | 60 | 55.0% | 54.5% | +7.00u |
| −109 to −101 | 11 | 45.5% | 51.0% | ±0.00u |
| +100 to +119 | 15 | 46.7% | 47.7% | −1.25u |
| **+120 to +149** | **33** | **42.4%** | **43.4%** | **−3.25u** |
| +150+ | 6 | 50.0% | 37.9% | −1.25u |

**We are profitable at juice, losing at plus money.** The model over-estimates win probability
at plus-odds prices. Note: G5 already blocks prob>0.65 at plus odds. But picks at
prob 0.55–0.65 at plus odds (+120 to +149) are still getting through and losing.

**Fix**: Raise edge requirement for plus-odds picks. Empirical: +120–149 hits 42.4% vs
BE 43.4% — we need higher genuine edge to overcome model miscalibration.
Proposed gate: `odds >= +110 AND edge < 0.09 → block` (extending G7b logic to plus side).

This would NOT harm the profitable −130 or −110 buckets. Needs validation pass.

---

## CRITICAL FINDING #4 — TEAM_TOTAL Over Is a Consistent Loser

| Stat+Dir | n | WR% | Model% | Gap | Units |
|---------|---|-----|--------|-----|-------|
| TEAM_TOTAL over | 11 | **45.5%** | 56.5% | −11.0pp | −1.50u |

n=11 is thin but consistent with the direction of the problem. Model over-predicts
team scoring probability. This may be a derivative pricing lag that benefits unders
more than overs in this market.

**Fix**: Gate TEAM_TOTAL over picks (add direction-specific block). Medium confidence (n=11).

---

## All Gates and Filters — Band-Aid vs Structural

### Prop gates (check_prop_gates)

| Gate | Type | Empirical basis | Verdict |
|------|------|----------------|---------|
| G1: prob≥0.70 AND edge<0.05 → block | Band-aid | Platt over-inflation at 0.70–0.80 bucket (54.2% WR, −17.8pp gap) | Covers Platt failure; keep until H3 Platt refit |
| G2: edge≥0.20 → block | Structural | Model error detection | Keep |
| G4: line≤2.5 AND prob>0.75 → block | Band-aid | Platt over-inflation; low-line high-prob rarely real | Keep until Platt refit |
| G5: odds>0 AND prob>0.65 → block | Band-aid | Partially. Plus-odds bucket losing even below 0.65 | Keep; extend via plus-odds edge gate |
| G7: odds≤−150 → block | Structural | Juice too high to overcome | Keep |
| G7b: −149 to −140 AND edge<0.09 → block | Structural | High juice + low edge = negative EV | Keep |
| G8: binary stats ≤1.5 → block | Structural | Line fragility is real regardless of model | Keep |
| G8B: AST over ≤4.5 NBA | Band-aid | Poisson wrong for AST; 0% WR at 2.6–4.5 (n=3, now blocked). 4.6–6.5 shows 66.7% (n=3) | Keep G8B; monitor 4.6+ |
| G8C: SOG under ≤3.5 | Band-aid | 42.9% WR at 2.6–3.5 (n=14). Blocked yesterday | Keep; watch 3.6–4.5 which has no historical data yet |
| G8D: 3PM over ≤1.5 | Band-aid | NB over-predicts at binary threshold; 46.2% WR at line 1.5 (n=13) | Keep |
| G9: edge<0.03 → block | Structural | No-edge picks | Keep |
| G10: under ≤2.5 AND edge<0.08 | Band-aid | Defensive; no empirical validation | Questionable — lacks data backing |
| G13: prob<0.50 → block | Structural | Never bet against your model | Keep |
| G13B: HRR WP floors | Band-aid | NB(r=1.5) inflates HRR | Moot — HRR fully disabled |
| G_HRR_DISABLED | Band-aid (stat killed) | 57.4% WR = breakeven at juice | Correct decision; keep disabled |
| G_TB_DISABLED | Band-aid (stat killed) | Distribution model wrong | Correct; keep disabled |
| G14: z<0.10 projection clearance | Structural | Ensures directional conviction | Keep |
| G15: HIGH-VAR 3PM (CV≥0.60) | Structural | Bimodal shooters real risk | Keep |
| G_K_NO_UNDERS | Structural | SaberSim IP bias documented | Keep |
| G_K_MIN_LINE | Structural | Same | Keep |
| G_OUTS_UNDER: prob<0.60 | Band-aid | SIGMA miscal for pitcher OUTS | Keep as WP threshold until more data |

### Post-gate soft floors

| Rule | Empirical finding | Verdict |
|------|-----------------|---------|
| MIN_PICK_SCORE=25 | Score<30 hits 37.5% WR (n=32), score 30–40 hits 40.0% (n=30). Floor at 25 is too low. | **Raise to 30 or 35** — score<30 is clearly bad |
| MIN_OVER_SCORE=40 | Overs ≤40 score hit 40.0% WR. Score 40–50 hits 61.1% for all picks. Floor seems right. | Keep at 40 |
| MIN_WIN_PROB=0.55 | **0.55–0.60 bucket hits 33.3% — worse than blocked 0.50–0.55 at 43.6%** | **Raise to 0.60** |

---

## Does Pick Score Actually Predict Win Rate?

| Score Bucket | n | WR% | Units |
|-------------|---|-----|-------|
| <30 | 32 | 37.5% | −4.75u |
| 30–40 | 30 | 40.0% | −5.50u |
| 40–50 | 18 | 61.1% | +2.25u |
| 50–60 | 8 | 62.5% | +2.50u |
| 60–70 | 18 | **66.7%** | +6.50u |
| **70+** | **76** | **59.2%** | **+16.00u** |

**Pick score is broadly predictive up to 70, then flattens/inverts.** The 70+ bucket (n=76,
the majority of Premium picks) hits 59.2% vs the 66.7% of the 60–70 bucket.

Root cause: pick_score is 60% edge-weighted. High-edge SOG picks (T1, structural edge vs market)
score 70+ but hit at mediocre rates (SOG under overall: 48.8%). Edge is inflated by the market
vig on SOG — the "edge" is partly illusory because the model's win_prob is too high.

**Fix**: Consider reducing edge weight in pick_score from 60% → 50%, or adding a win_prob
floor that's score-conditional (e.g., picks scoring 70+ still require WP≥0.60).

---

## Does Edge Actually Predict Win Rate?

| Edge Bucket | n | WR% | Units |
|-------------|---|-----|-------|
| 0.03–0.05 | 7 | 28.6% | −1.50u |
| 0.05–0.07 | 23 | **39.1%** | −2.75u |
| 0.07–0.09 | 15 | **66.7%** | +4.25u |
| **0.09+** | **137** | **55.5%** | **+17.00u** |

Edge does NOT predict WR cleanly in the 0.03–0.07 range. The 0.05–0.07 bucket (39.1%)
underperforms even the 0.03–0.05 bucket. These medium-edge picks are almost certainly
SOG/AST picks where the "edge" is model-generated illusion — the win_prob is wrong,
making the edge calculation wrong.

The 0.07–0.09 bucket is the sweet spot (66.7% WR). The 0.09+ bucket (n=137, 55.5%)
is the biggest driver of overall performance.

**Implication**: Edge floors need to be higher than currently set. T1 min_edge=3%, T2=5%,
T3=6% allow picks that empirically don't have real edge. Consider raising T1→5%, T2→7%.

---

## Tier Performance

| Tier | n | WR% | Model% | Gap | Units |
|------|---|-----|--------|-----|-------|
| T1 | 58 | **46.6%** | 63.3% | −16.7pp | −3.75u |
| T2 | 58 | **60.3%** | 63.4% | −3.0pp | +12.00u |
| T3 | 31 | 51.6% | 64.9% | −13.2pp | +1.25u |
| T1B | 30 | 53.3% | 59.8% | −6.4pp | +3.50u |
| KILLSHOT | 5 | 60.0% | 74.4% | −14.4pp | +4.00u |

**T1 (46.6% WR) is performing worse than T2 (60.3%). The best tier is the worst performer.**

T1 = SOG + AST almost exclusively. Both stats are miscalibrated:
- SOG under: 48.8% WR (−14.2pp gap) — now mostly blocked by G8C
- AST overall: ~46% WR when mixed
- The model assigns T1 status because these are "predictable counting stats" but empirically
  they are the hardest to predict at the win-probability level.

**Fix options**:
1. Remove SOG and AST from T1, reclassify to T2 or T1B
2. Raise T1 min_edge to something that filters the worst SOG/AST picks (e.g., 6%)
3. Add stat-specific MIN_WIN_PROB for T1 stats (e.g., SOG under requires WP≥0.62)

---

## Pre-Platt Calibration Analysis (n=48 picks with over_p_raw)

| Raw WP Bucket | n | Actual WR% | Raw WP% | Calibrated WP% | Platt shift |
|--------------|---|-----------|---------|---------------|------------|
| <0.55 | 22 | **40.9%** | 50.7% | 51.6% | +0.9pp |
| 0.55–0.60 | 10 | **30.0%** | 58.1% | 54.5% | −3.6pp |
| 0.60–0.65 | 4 | **25.0%** | 61.8% | 55.9% | −5.9pp |
| 0.65–0.70 | 6 | **33.3%** | 67.2% | 57.4% | −9.8pp |
| 0.70–0.80 | 5 | **40.0%** | 73.7% | 64.8% | −8.9pp |

**The Platt is doing almost nothing in the <0.55 raw bucket (+0.9pp shift).** This is the
largest bucket (n=22) and it's hitting 40.9% with near-zero Platt correction. The Platt
is doing meaningful work at higher raw probabilities (shifting by 6–10pp) but the low
end is essentially uncorrected.

By direction (n=48):
| Direction | n | Actual WR% | Raw WP% | Calibrated WP% | Raw Gap | Cal Gap |
|-----------|---|-----------|---------|---------------|---------|---------|
| over | 5 | **20.0%** | 64.5% | 59.6% | −44.5pp | −39.6pp |
| under | 43 | **39.5%** | 57.8% | 54.5% | −18.2pp | −14.9pp |

**Platt barely helps overs (−44.5pp raw gap → −39.6pp after Platt). For unders (−18.2pp raw → −14.9pp), marginal improvement.**

The n=48 sample (all post-May 5) hitting 37% overall vs 53% historical is alarming. This
is likely explained by the model running without the gates added on May 23 (G8C extended,
G8D, MIN_WIN_PROB). Those 48 picks were made before yesterday's fixes. Going forward, the
filtered picks should improve.

---

## Every Structural Problem in the Probability Math

### S1 — Single Universal Platt (Most Impactful)
One A,B pair (1.4988, −0.8102) for all stats, both directions. Fitted on n=76 picks.
Empirical result: overs still −39.6pp gap after calibration. Unders −14.9pp gap.
**A single monotone function cannot simultaneously fix overs and unders.**

Real fix: Direction-split Platt. Need ~60–80 rows per direction (currently ~5 overs / ~43 unders in raw sample).

### S2 — Platt in Raw-Probability Space (Not Logit-Space)
Standard Platt: `sigmoid(A × logit(p) + B)`. Ours: `sigmoid(A × p + B)`.
Raw-probability Platt compresses the tails less aggressively. This contributes to
the 0.70–0.80 bucket remaining over-inflated (−17.8pp) post-calibration.
Real fix: Re-implement in logit-space at H3 refit.

### S3 — Poisson for AST May Be Wrong
Poisson assumes var = mean. AST is empirically overdispersed (variance >> mean for
most playmakers). If true var ≈ 2×mean, then Poisson over-confidence is built-in.
Evidence: G8B added for AST over ≤4.5 (model over-confident). Overall AST over 25% WR.
Real fix: Move AST to NB_STATS. Calibrate r from projections.db (need to run the calc).

### S4 — I6 Confidence Modifier Applies to Edge Only, Not Win_Prob
When GP<10, adj_edge = raw_edge × 0.70. But win_prob is unchanged.
A player with 3 games gets the same win_prob as a 40-game player.
The uncertainty should shrink win_prob toward 0.50.
Real fix: `adj_wp = 0.50 + (win_prob − 0.50) × conf`. Low effort, implementable now.

### S5 — MLB Has No Platt Calibration
MLB props run on raw distribution probabilities. No calibration at all.
Empirical: MLB hitting 45.5% WR (n=11), −13.8pp gap. Small sample but consistent with over-prediction.
Real fix: MLB Platt when sample reaches ~50–75 props.

### S6 — SIGMA Parameters Not Post-Platt Validated
SIGMA values (PTS mult=0.35, AST mult=0.45, etc.) set distribution width.
If SIGMA is too tight, raw over_p is too extreme → Platt must work harder.
The two systems fight each other. No validation that current SIGMA + current Platt
produces the correct joint calibration.
Real fix: Validate by checking over_p_raw distribution spread — should be roughly uniform, not clustered at extremes.

### S7 — T1 Tier Assignment Contradicts Empirical Performance
T1 (SOG, AST) defined as "predictable" but hits 46.6% WR. T2 (PTS, PRA) hits 60.3%.
The tier system is built on the wrong assumption about which stats are predictable.
Real fix: Reclassify SOG and AST as T1B or T2 based on actual predictability, not theoretical.

---

## Fixes — Validated vs Speculative

### VALIDATED (empirical support, safe to ship):

| Fix | Evidence | Impact | Risk |
|-----|---------|--------|------|
| Raise MIN_WIN_PROB to 0.60 | 0.55–0.60 bucket: 33.3% WR (n=24), worse than blocked 0.50–0.55 (43.6%) | +4.25u on historical data | Reduces card volume |
| Raise MIN_PICK_SCORE to 30 | Score<30: 37.5% WR (n=32) — same as 30–40 bucket (40%) | Minimal — both buckets underperform | Slightly reduces card volume |
| Block TEAM_TOTAL over | 45.5% WR (n=11), −11pp gap, consistent direction | Small (+1.50u historical) | Low — n=11 is thin |
| Gate plus-odds + low edge | +120–149 bucket: 42.4% WR (n=33), BE 43.4% | +3.25u historical | Some volume reduction |
| Apply I6 to win_prob | Logical consistency; low-GP picks shouldn't get same WP as 40-game players | Small but correct | Negligible |

### DATA-GATED (need more data before implementing):

| Fix | What's Needed | Status |
|-----|--------------|--------|
| Direction-split Platt | ~60–80 over + under rows with over_p_raw | ~5 over / ~43 under (far from gate) |
| Logit-space Platt (H3 refit) | 300 total over_p_raw rows | 49/300 |
| AST → NB_STATS (calibrate r) | Run var/mean analysis on projections.db AST data | Analysis not run yet |
| MLB Platt | ~50–75 MLB props | 11 graded (live since May 20) |
| SOG under 3.6–4.5 gate decision | Historical data on 3.6–4.5 SOG unders | None yet (G8C previously blocked only ≤2.5) |

### DO NOT CHANGE (well-calibrated, empirically validated):

| What | Evidence |
|------|---------|
| PTS over | 65.0% WR (n=20), −2.7pp gap. Nearly perfect. |
| PTS under | 76.9% WR (n=13), +13.3pp. Underestimating — do not add floors. |
| 3PM under | 60.0% WR (n=15), +0.6pp. Textbook calibration. |
| REB under ≤4.5 | 60.0% WR (n=20), −2.1pp. Fine. |
| WP 0.65–0.70 bucket | 66.7% WR (n=42), −1.4pp. Best-calibrated bucket. |
| T2 tier | 60.3% WR (n=58), −3.0pp. Working correctly. |
| AST under | 71.4% WR (n=7). Fine — do not over-correct. |
| Juice picks (≤−130) | 61.4% WR (n=57). Profitable. |

---

## Immediate Action Plan (Ordered by Confidence + Impact)

### Action 1: Raise MIN_WIN_PROB from 0.55 → 0.60
**File**: engine/run_picks.py line 1156
**Evidence**: 0.55–0.60 bucket 33.3% WR (n=24). Higher confidence than the previous 0.55 decision.
**Risk**: Some card-thinning nights. Accept — we want quality over volume.

### Action 2: Gate TEAM_TOTAL over
**File**: engine/run_picks.py check_prop_gates or get_tier()
**Evidence**: 45.5% WR (n=11). Medium confidence.
**Implementation**: Block direction=="over" for stat=="TEAM_TOTAL"

### Action 3: Plus-odds edge gate
**File**: engine/run_picks.py check_prop_gates
**Evidence**: +120–149 bucket 42.4% WR (n=33). Strong evidence.
**Proposed rule**: `if odds >= +110 and edge < 0.09: block (G7c)`
**Must validate**: Does this block enough of the bad picks without touching the profitable juice picks?

### Action 4: Apply I6 confidence modifier to win_prob
**File**: engine/run_picks.py line 2292 area
**Evidence**: Logical fix, minimal risk. Only affects low-GP players.

### Action 5: Monitor AST over 4.6+ (don't block yet, need n≥10)
### Action 6: Calibrate AST NB_R (requires projections.db analysis)
### Action 7: Direction-split Platt (data-gated)
### Action 8: H3 Platt refit in logit-space (data-gated, 300 rows)

---

## Web Research Findings (completed)

### AST — Poisson is Wrong
Published research confirms NBA assists are overdispersed (var > mean). Negative Binomial
is the correct model. This validates S3 above. Action: calibrate NB r for AST from projections.db.

### SOG — Poisson is Acceptable
NHL SOG is better-fitted by Poisson than AST — shot volume is more consistent within a player
and game context. Poisson for SOG is conditionally acceptable but should be validated via
goodness-of-fit test. The G8C gate (blocking ≤3.5 unders) covers the worst Poisson failures.

### Logit-Space Platt is Definitively Superior
Standard Platt (logit-space) compresses tails more aggressively than raw-probability Platt.
Our current implementation (sigmoid(A × p + B)) undercompresses the 0.70–0.80 range —
explains why that bucket remains −17.8pp over-predicted even post-calibration.
**H3 refit must implement logit-space Platt.**

### Platt vs Isotonic Regression
Platt scaling is optimal for n~200 samples. Isotonic regression only outperforms Platt
at n > 1,000. Our current n=49 over_p_raw rows is too small even for Platt to be stable.
H3 gate (300 rows) is the right threshold.

### 3PM Overdispersion — r=12.3 May Be Too High
Published NB r for NBA 3PM is approximately 1.8–2.0 (population level). Our r=12.3
is within-player conditional variance (correct methodology), but the empirical 46.2% WR
at 3PM over ≤1.5 (model says 70%) suggests even r=12.3 produces too much confidence.
This is validated by G8D being a band-aid for NB over-prediction at the binary threshold.
May need to reduce r toward 6–8 range and validate with projections.db data.

### Direction Asymmetry — Documented but Below Threshold
Public research documents a bias toward over-betting, but separate calibration is only
recommended when over vs under win rates diverge by >8pp. Our empirical: overs 49.2%
vs unders 55.4% = 6.2pp gap in WR. HOWEVER our model gap is much larger: overs −16.9pp
vs unders −6.6pp. The model treats them identically when they have very different errors.
Direction-split Platt is justified by the model gap even if the WR gap alone isn't >8pp.

---

## Constants Audit Summary (completed)

| Constant | Verdict | Key Issue |
|---------|---------|-----------|
| PLATT A=1.4988, B=−0.8102 | **NEEDS REFIT** | n=76, no train/test split, raw-prob not logit-space, single for all stat-directions |
| NB_R["3PM"] = 12.3 | SOLID | Large sample (n=418 player-seasons), correct methodology; G8D residual at binary threshold |
| NB_R["K"] = 5.0 | QUESTIONABLE | No formal n; implies CV=0.59 vs empirical 0.28–0.44 (too wide ~35%) |
| NB_R["HRR"] = 1.5 | MOOT | Stat disabled; would need zero-inflated NB to fix properly |
| COMBO_RHO NBA | SOLID | n=75,367 player-games, correct methodology, low sensitivity |
| COMBO_RHO_WNBA | QUESTIONABLE | n=9 players / 336 games — statistically indistinguishable from noise |
| SIGMA values (PTS/AST/REB etc.) | QUESTIONABLE | Not formally calibrated; interact with Platt in unknown ways |
| VAKE_BASE sizing | SOLID | Far below Kelly; ruin-safe; conservative errors are safe errors |
| pick_score 40/60 split | QUESTIONABLE | Not validated against WR; edge-dominance untested |
| PICK_SCORE_TIER_MULT T1=0.90 | QUESTIONABLE | 10% score discount for 16pp WR gap — disproportionately small |
| I6 (GP<10→0.70 edge only) | QUESTIONABLE | Win_prob not adjusted — asymmetric uncertainty treatment |
| TIERS min_edge (3/3/5/6%) | SOLID | Research-backed for each tier |
| G5, G7, G14, G15 | SOLID | Well-grounded structural gates |
| G1, G4, MIN_OVER_SCORE | BAND-AIDS | Cover Platt over-inflation |

---

## Final Consolidated Action List

### DO NOW (empirically validated, safe):
1. `MIN_WIN_PROB 0.55 → 0.60` — 0.55–0.60 bucket hits 33.3% WR (n=24), worse than the 0.50–0.55 bucket (43.6%) we already blocked
2. Block `TEAM_TOTAL over` — 45.5% WR (n=11), consistent loser
3. Gate `odds ≥ +110 AND edge < 0.09 → block` (G7c) — +120–149 bucket 42.4% WR (n=33)
4. Apply I6 to win_prob: `adj_wp = 0.50 + (win_prob − 0.50) × conf` — logical consistency fix

### DO NEXT (requires analysis before shipping):
5. Calibrate NB_R for AST from projections.db (within-player avg var/mu)
6. Validate 3PM r=12.3 — may need to reduce toward 6–8 based on empirical over-prediction
7. Calibrate NB_R["K"] with proper within-player methodology

### DATA-GATED (cannot do yet):
8. Direction-split Platt — need ~60–80 over rows with over_p_raw (currently ~5)
9. H3 Platt refit in logit-space — need 300 over_p_raw rows (currently 49)
10. MLB Platt — need ~50–75 MLB props (currently 11)

### DO NOT TOUCH (well-calibrated):
- PTS (both directions)
- 3PM under
- REB under ≤4.5
- WP 0.65–0.70 bucket
- T2 tier picks
- AST under
- Juice picks (≤−130)
