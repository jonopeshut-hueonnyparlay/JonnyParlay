# Probability Pipeline Audit — 2026-05-24
*Full analysis of what's wrong, what's a band-aid, and what a real fix looks like.*

---

## 1. Full Pipeline (step by step)

```
CSV projection (proj, line, stat, odds_over, odds_under)
    ↓
calc_prop_prob() / calc_combo_prob() / calc_tb_prob()   [lines 646–781]
    → over_p, under_p  (raw distribution model)
    ↓
over_p_raw = over_p  (saved for H3 refit — line 2249)
    ↓
_platt_calibrate_prop(over_p)  [line 634, skipped for MLB]
    → over_p = sigmoid(1.4988 * over_p − 0.8102)
    → under_p = 1 − over_p
    ↓
win_prob = over_p  (for overs)  OR  under_p  (for unders)
    ↓
calc_edge()  [line 784]
    → over_edge = over_p − nv_over
    → under_edge = under_p − nv_under
    ↓
adj_edge = raw_edge × conf  [line 2292]
    conf: GP<10 → 0.70, GP<20 → 0.85, else 1.0
    ↓
check_prop_gates()  [line 878]  — hard pass/fail
    ↓
tier min edge check  [line 2341]
    ↓
pick_score()  [line 794]
    = (0.40 × wp_normalized) + (0.60 × edge_normalized) × tier_mult
    ↓
apply_soft_rules_premium() / bonus / SGP selection
    → MIN_PICK_SCORE=25, MIN_OVER_SCORE=40, MIN_WIN_PROB=0.55 [lines 1154–1156]
```

---

## 2. Distribution Models by Stat

| Stat | Model | Parameters | Key Risk |
|------|-------|-----------|---------|
| AST, REB, SOG, REC, HITS | Poisson | λ = proj | **Poisson assumes var=mean — AST/SOG may be overdispersed** |
| 3PM, HRR, K | Negative Binomial | r: 3PM=12.3, HRR=1.5, K=5.0 | r calibrated on limited data |
| PTS, OUTS, HA, TB | Normal | σ = max(proj × mult, min) | σ parameters may be too tight |
| PRA, PR, PA, RA | Correlated Normal | ρ from 75k player-games | Correlation is total covariance incl. minute variance — correct |

---

## 3. Platt Scaling — What It Actually Does

**Formula**: `sigmoid(1.4988 × over_p − 0.8102)`

This is NOT standard Platt. Standard Platt operates in logit-space: `sigmoid(A × logit(p) + B)`.
This version takes raw probability as input. The coefficients absorb the different transformation.

**What it was fitted on**: 76 settled NBA+NHL props (2026-05-01). n=76 is small.

**Coverage**: NBA ✓, NHL ✓, WNBA ✓ (approximation). MLB ✗ (skipped entirely).

**The core problem**: A single scalar A,B applied uniformly to all stats and both directions.

Example of why this fails:
- Over AST: raw model says ~65% → Platt → ~58% → actual WR = 25%. Gap = −33pp. Even Platt can't fix this.
- Under PTS: raw model says ~60% → Platt → ~53% → actual WR = 76.9%. Gap = +24pp. Platt is making it worse.

A single Platt that compresses probabilities downward helps some cases and actively hurts others.

---

## 4. All Gates & Filters — Band-Aid vs Structural

### Hard probability/edge gates in check_prop_gates()

| Gate | Line | Condition | Band-Aid? | Root Cause |
|------|------|-----------|----------|------------|
| G1 | 1026 | prob≥0.70 AND odds>−200 AND edge<0.05 → block | **YES** | Platt over-inflation at high WP bucket (0.70–0.80: −20.8pp) |
| G2 | 1032 | edge≥0.20 → block (model error flag) | Structural | Catches obvious mis-pricing |
| G4 | 1036 | line≤2.5 AND prob>0.75 → block | **YES** | Platt over-inflation at high probs + low line |
| G5 | 1040 | odds>0 AND prob>0.65 → block | **YES** | Platt over-inflation; plus odds at >65% WP is almost always model error |
| G8 | 901 | binary stats (AST/REB/SOG etc.) at line≤1.5 | Structural | Line fragility is real, not calibration |
| G8B | 908 | AST over ≤4.5, NBA only | **YES** | Poisson doesn't capture AST overdispersion; over-predicts P(X>4.5) |
| G8C | 914 | SOG under ≤3.5 | **YES** | Poisson underestimates elite shot volume; 42.9% WR |
| G8D | 920 | 3PM over ≤1.5 | **YES** | NB(r=12.3) over-predicts binary threshold; 50% WR vs 70% model |
| G9 | 963 | edge<0.03 → block | Structural | Legitimate floor |
| G10 | 1044 | under ≤2.5 AND edge<0.08 | **PARTLY** | Defensive against low-line fragility, but arbitrary threshold |
| G13 | 967 | prob<0.50 → block | Structural | No negative WP picks |
| G13B | 974 | HRR WP floors | **YES** | NB model inflates HRR; covering for wrong r value |
| G_HRR_DISABLED | 981 | kills HRR entirely | **YES** | NB(r=1.5) still wrong; couldn't fix calibration so killed stat |
| G_TB_DISABLED | 984 | kills TB entirely | **YES** | Distribution model wrong; killed instead of fixed |
| G14 | 997 | z < 0.10 (projection barely clears line) | Structural | Correct gate — ensures directional conviction |
| G15 | 1020 | HIGH-VAR 3PM (CV≥0.60) | Structural | Correctly excludes bimodal players |
| G_K_NO_UNDERS | 949 | K unders → block | Structural | SaberSim IP bias is real and well-documented |
| G_K_MIN_LINE | 951 | K over < 6.0 → block | Structural | Same IP bias logic |
| G_OUTS_UNDER | 956 | OUTS under + prob<0.60 → block | **PARTLY** | WP threshold covering for SIGMA mis-calibration |

### Post-gate soft floors (apply_soft_rules_premium)

| Rule | Line | Condition | Band-Aid? | Root Cause |
|------|------|-----------|----------|------------|
| MIN_PICK_SCORE=25 | 1154 | global score floor | **PARTLY** | Filters low-conviction filler; masks calibration gaps |
| MIN_OVER_SCORE=40 | 1155 | overs must score ≥40 | **YES** | Overs −13.6pp gap; score floor covers for calibration failure |
| MIN_WIN_PROB=0.55 | 1156 | global WP floor | **YES** | 0.50–0.60 bucket: 39.3% actual; floor cuts worst cases |

### Other probability adjustments

| Rule | Line | What it does | Band-Aid? |
|------|------|-------------|----------|
| I6 confidence modifier | 2286 | adj_edge × {0.70, 0.85, 1.0} based on GP | Structural edge dampen; but win_prob is NOT adjusted — inconsistency |
| WNBA edge dampener | 939 | effective_edge × {0.80, 0.90} in early season | Structural |
| Tier min edge | 2341 | T1=3%, T2=5%, T3=6% | Structural |

---

## 5. Structural Problems (Root Causes)

### P1 — Single universal Platt (most impactful)

One A,B pair applied to all stats and both directions. The calibration data shows the model is:
- **Over-predicting** overs by −13.6pp overall
- **Under-predicting** PTS unders (76.9% actual vs 63.6% model)
- **Catastrophically over-predicting** AST overs (25% actual vs 65% model)

A single scalar that pushes probabilities down helps AST overs but actively hurts PTS unders. These cannot be fixed simultaneously by one Platt.

**Real fix**: Direction-split Platt (separate A,B for over vs under). Stat-family Platt (separate coefficients for count stats vs Normal stats) is the longer-term fix.

### P2 — Poisson assumption for AST may be wrong

Poisson assumes var = mean. But AST is highly overdispersed: elite playmakers regularly go 2 one game and 15 the next. If the true variance is 2–3× the mean (like assists empirically are), Poisson is producing too-narrow distributions → over-confident probabilities.

Evidence: G8B was needed to block AST overs ≤4.5 because the model was over-confident there.
AST overs overall (post-G8B) still hitting 25% WR — the problem extends above 4.5.

**Real fix**: Move AST to NB_STATS with a calibrated r value (like we did for 3PM and HRR).

### P3 — Platt operates on raw probability, not logit-space

Standard Platt: `sigmoid(A × logit(p) + B)`.
This Platt: `sigmoid(A × p + B)`.

This isn't necessarily wrong (it was empirically fitted), but the transformation behaves differently at the tails. Raw-probability Platt compresses the 0.70–0.90 range less aggressively than logit-space Platt would. This contributes to the 0.70–0.80 bucket remaining over-inflated (−20.8pp) even after calibration.

**Real fix**: Re-implement Platt in logit-space and refit. This is a breaking change but fixes the tail behavior.

### P4 — I6 adjusts edge but not win_prob

When GP < 10, adj_edge = raw_edge × 0.70. But win_prob is unchanged. This means a 3-game player gets the same win_prob as a 40-game player. The confidence penalty is only felt in edge/scoring, not in the WP that gates use. If GP uncertainty is real, win_prob should also shrink toward 0.50.

**Real fix**: Apply confidence modifier to win_prob too: `adj_wp = 0.50 + (win_prob - 0.50) × conf`. This pulls low-GP players' win_prob toward 0.50 symmetrically.

### P5 — MLB has no Platt at all

MLB was excluded because the Platt was fitted on NBA+NHL. But MLB may be equally mis-calibrated in a different direction. Currently MLB runs with raw distribution probabilities, no calibration at all. We have no empirical WR breakdown for MLB by WP bucket to know how bad this is.

**Real fix**: Once MLB sample reaches ~50–75 props, fit a separate MLB Platt.

### P6 — SIGMA parameters not validated post-Platt

The SIGMA values (e.g., PTS: mult=0.35 min=4.5) were set during development and not re-validated against actual outcomes. Platt partially compensates for wrong SIGMA by shifting calibrated probabilities. But this means the two systems are fighting each other: if SIGMA is too tight, the raw over_p is too extreme → Platt has to work harder → the single Platt may over-correct some stats while under-correcting others.

**Real fix**: Validate SIGMA by checking the distribution of `over_p_raw` — if it clusters near 0.20 and 0.80 instead of having a reasonable spread, SIGMA is too tight.

---

## 6. Band-Aids Currently in Place (Summary)

These gates/rules exist primarily because a deeper model problem hasn't been fixed:

| Band-Aid | Masking |
|---------|---------|
| G1, G4, G5 | Platt over-inflation at high WP (0.70–0.80 bucket −20.8pp) |
| G8B | Poisson over-confidence on AST; should be NB |
| G8C | Poisson wrong for elite SOG — underestimates shot volume |
| G8D | NB(r=12.3) over-predicts 3PM over at binary threshold |
| G_HRR_DISABLED | NB(r=1.5) still mis-calibrated — stat killed instead |
| G_TB_DISABLED | Discrete distribution problem — stat killed instead |
| MIN_WIN_PROB=0.55 | 0.50–0.60 bucket 39.3% WR; blunt instrument |
| MIN_OVER_SCORE=40 | Over direction systemic −13.6pp gap |
| G_OUTS_UNDER | SIGMA mis-calibration for pitcher OUTS |

---

## 7. What Real Fixes Look Like

### Fix 1: Direction-split Platt [HIGH IMPACT, DATA-GATED]
Fit separate (A_over, B_over) and (A_under, B_under).
- Need ~100 over picks + ~100 under picks with over_p_raw logged.
- Currently: 49 total over_p_raw rows (2026-05-23). Overs are ~1/3 of picks → ~16 over rows, ~33 under rows.
- Gate: ~60–80 rows per direction. Estimate: 6–8 more weeks at current pace.
- This directly targets the biggest structural problem.

### Fix 2: Move AST to NB_STATS [MEDIUM, IMPLEMENTABLE NOW]
Calibrate NB r for AST using the same method as 3PM (avg(var/mu) from projections.db).
- Wider distribution → lower over-confidence → AST overs get lower WP → naturally filtered without G8B patch
- Can remove G8B if NB calibration is correct
- Risk: unknown r value without running the calibration

### Fix 3: Logit-space Platt [MEDIUM, PAIRS WITH H3 REFIT]
When we do the H3 refit at 300 rows, implement standard logit-space Platt.
- Fixes tail over-inflation (0.70–0.80 bucket) better than raw-probability version
- Not worth doing separately from H3 — do together

### Fix 4: Apply I6 confidence modifier to win_prob [LOW EFFORT, IMPLEMENTABLE NOW]
`adj_wp = 0.50 + (win_prob - 0.50) × conf`
- Low-GP players' win_probs pulled toward coin-flip
- Makes I6 consistent: if we're uncertain about a player, uncertainty applies to both edge AND win_prob

### Fix 5: Stat-specific MIN_WIN_PROB floors [MEDIUM, IMPLEMENTABLE NOW]
Instead of a global 0.55 floor, set floors by stat/direction based on calibration data:
- AST over: 0.65 floor (25% WR — the entire direction is broken)
- SOG under: 0.60 floor (even after G8C, remaining SOG unders hit 48.8%)
- PTS (both): no floor change — well calibrated
- 3PM over: already blocked by G8D ≤1.5; add 0.58 floor for higher lines
This replaces the blunt global floor with targeted stat-level floors.

### Fix 6: MLB Platt [DATA-GATED]
When MLB sample reaches ~50–75 props (currently live, accumulating fast), fit and apply MLB Platt.
Until then, MLB raw probabilities have no calibration correction.

---

## 8. Priority Order

| Priority | Fix | Effort | Impact | Gate |
|---------|-----|--------|--------|------|
| 1 | Direction-split Platt | Low (once data arrives) | Very High | ~60–80 rows per direction |
| 2 | Stat-specific WP floors | Low | Medium | Implementable now |
| 3 | I6 apply to win_prob | Very Low | Low-Medium | Implementable now |
| 4 | AST → NB_STATS | Medium (calibrate r) | Medium | Need DB analysis |
| 5 | Logit-space Platt (H3 refit) | Medium | High | 300 over_p_raw rows (49 now) |
| 6 | MLB Platt | Low | Unknown | ~50–75 MLB props |
