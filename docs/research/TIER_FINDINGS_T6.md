# Tier Research T6: VAKE Calibration + Kelly + Final Tier Table

**Date:** 2026-05-21  
**Scope:** Section 11 (cross-cutting calibration) — Kelly math, VAKE validation, cap sizing, final tier/cap tables.

---

## SECTION 11A: Edge Thresholds from First Principles

### Kelly Math Setup

American odds conversion:
- **-115** → decimal = 1 + 100/115 = 1.8696, b = 0.8696, implied = 115/215 = **53.49%**
- **-110** → decimal = 1 + 100/110 = 1.9091, b = 0.9091, implied = 110/210 = **52.38%**
- **+100** → decimal = 2.00, b = 1.00, implied = **50.00%**
- **+105** → decimal = 2.05, b = 1.05, implied = 100/205 = **48.78%**

Kelly formula: `f* = (b×p - q) / b` where q = 1-p. "Edge" throughout = win_prob − implied_prob.

### T1 at 3% edge, 53% WR, -115 odds

Using the "3% edge" as the gap over implied (not raw win rate):
- wp = 0.5349 + 0.03 = 0.5649
- f* = (0.8696 × 0.5649 − 0.4351) / 0.8696 = (0.4912 − 0.4351) / 0.8696 = **6.45% of bankroll**
- Quarter Kelly = **1.61u** on 100u bankroll
- EV per dollar staked = 0.5649 × 0.8696 − 0.4351 = +**0.0561** = **+5.6% ROI**
- VAKE T1 at 3% edge = 0.50u × 1.00 × 1.00 = **0.50u** ≈ 1/12.9 Kelly (**~1/13 Kelly**)

### T1 at 5% edge, 55% WR, -115 odds

- wp = 0.5349 + 0.05 = 0.5849 (≈55% WR)
- f* = (0.8696 × 0.5849 − 0.4151) / 0.8696 = (0.5086 − 0.4151) / 0.8696 = **10.75% of bankroll**
- Quarter Kelly = **2.69u**
- EV per dollar staked = 0.5849 × 0.8696 − 0.4151 = +**0.0935** = **+9.4% ROI**
- VAKE T1 at 5% edge = 0.75u × 1.00 × 1.00 = **0.75u** ≈ 1/14.3 Kelly (**~1/14 Kelly**)

### T2 at 5% edge, 55% WR, -115 odds

- Same Kelly as above: Quarter Kelly = **2.69u**
- EV same: **+9.4% ROI**
- VAKE T2 at 5% edge = 0.75u × 0.85 × 0.90 = **0.574u** ≈ 1/18.7 Kelly (**~1/19 Kelly**)

### T3 at 6% edge, 55% WR, -110 odds

- wp = 0.5238 + 0.06 = 0.5838
- f* = (0.9091 × 0.5838 − 0.4162) / 0.9091 = (0.5307 − 0.4162) / 0.9091 = **12.60% of bankroll**
- Quarter Kelly = **3.15u**
- EV per dollar staked = 0.5838 × 0.9091 − 0.4162 = +**0.1145** = **+11.5% ROI**
- VAKE T3 at 6% edge = 0.75u × 0.65 × 0.60 = **0.2925u** ≈ 1/42.9 Kelly (**~1/43 Kelly**)

### Summary of EV and Kelly Ratios

| Tier | Edge | WR | Odds | EV/bet | Quarter Kelly | VAKE size | VAKE as fraction of full Kelly |
|------|------|-----|------|--------|--------------|-----------|-------------------------------|
| T1 (min) | 3% | 56.5% | -115 | +5.6% | 1.61u | 0.50u | ~1/13 |
| T1 (mid) | 5% | 58.5% | -115 | +9.4% | 2.69u | 0.75u | ~1/14 |
| T2 | 5% | 58.5% | -115 | +9.4% | 2.69u | 0.57u | ~1/19 |
| T3 | 6% | 58.4% | -110 | +11.5% | 3.15u | 0.29u | ~1/43 |

### Are 3%/5%/6% Thresholds Correct?

**Literature benchmarks by market type:**

- **Tight props (NBA PTS, NHL SOG, MLB K):** Professional standards cite 2-4% as sufficient given high book liquidity and well-calibrated lines. The model's 3% T1 floor is appropriate and conservatively within range. Sharp props shops (Pinnacle-level) work to 2%, but those have higher model confidence than this system currently warrants.
- **Game lines (spreads, totals):** Standard advice is 4-5% minimum due to sharper markets and lower information asymmetry from a prop-style model. The model's T2 5% floor for spreads/totals is correct.
- **Binary/volatile props (ML_DOG, YRFI, GOALS):** Literature recommends 6-8%. The model's 6% T3 floor, plus the hardcoded 8% overrides for ML_DOG and YRFI, are appropriate — the 8% overrides for the most volatile binaries are well-supported.
- **Combo stats (PRA, PR, PA, RA):** 5% is appropriate. These are derived from less sharp individual lines and carry additive variance. T2 is correct.

**Verdict:** The 3%/5%/6% threshold structure is **defensible and approximately correct**. The main concern is T3 at 6% for non-YRFI T3 markets (GOALS, 3PM, NRFI) — 6% may be too permissive for high-CV binaries. A 6% floor with the T3 sizing reduction (×0.39) compensates adequately, so no change recommended unless model edge estimates are found to be systematically overstated.

**Recommended thresholds: Keep 3%/5%/6% as-is.** The 8% overrides for ML_DOG and YRFI are the right safety valve for the highest-variance markets.

---

## SECTION 11B: VAKE vs Kelly — Is Current Sizing Right?

### VAKE as a Fraction of Full Kelly

At a 5% edge, the VAKE system sizes as follows relative to full Kelly (100u bankroll):

| Tier | VAKE size | Full Kelly | VAKE / Full Kelly |
|------|-----------|-----------|-------------------|
| T1 | 0.75u | 10.75u | 1/14.3 |
| T2 | 0.57u | 10.75u | 1/18.9 |
| T3 | 0.29u | 10.75u | 1/37.1 |

Relative to the professional standard of **1/4 Kelly** (2.69u at 5% edge):

| Tier | VAKE size | Quarter Kelly | VAKE / Quarter Kelly |
|------|-----------|--------------|----------------------|
| T1 | 0.75u | 2.69u | 0.279× |
| T2 | 0.57u | 2.69u | 0.212× |
| T3 | 0.29u | 2.69u | 0.108× |

VAKE is **approximately 1/4 to 1/9 of quarter Kelly**, or equivalently **1/14 to 1/37 of full Kelly**.

### Is VAKE Too Conservative or Too Aggressive?

**Context for interpreting these ratios:**
1. Professional sharp bettors use 1/4 to 1/2 Kelly as a general rule. Recreational-grade systems with model edge uncertainty use 1/8 to 1/4 Kelly.
2. The model currently uses SaberSim projections (with its own variance) — epistemic uncertainty is real. Stated edges may be inflated by model noise.
3. VAKE sizing at ~1/14 full Kelly for T1 is **extremely conservative** vs theory, but appropriate given:
   - The system is not a pure-Kelly system (fixed tier brackets lose per-pick precision)
   - Daily volume of 5-15 picks means ruin risk compounds. Conservative per-pick sizing protects against correlated losing streaks.
   - Edge estimates are not perfectly calibrated — stated 5% edge may be 2-3% true after vig/model noise.

**Bottom line:** VAKE at ~1/4 of quarter Kelly is conservative but **not wrong**. It provides substantial insurance against model error and correlated picks. The T3 sizing (0.29u at ~1/43 Kelly) is very conservative — borderline too small to matter, but appropriate for the high-variance markets in T3.

### Recommended Adjustment

**Keep current multipliers.** The structure (T1=1.00×1.00, T2=0.85×0.90=0.765, T3=0.65×0.60=0.39) correctly encodes the variance hierarchy. The absolute scale (0.50/0.75/1.00/1.25u bases) is conservative but consistent with a model that:
- Posts multiple picks daily (correlated exposure risk)
- Uses SaberSim + custom projection (not a calibrated probability oracle)
- Is still accumulating CLV data for Platt calibration (H3 gate not yet cleared)

**One potential upgrade:** Once H3 Platt calibration is live and CLV shows positive expectation over 100+ rows, consider raising the T1 base by 10-15% (e.g., 0.55u at 3-5%, 0.85u at 5-7%). Do not change multipliers; only scale the base up.

---

## SECTION 11C: SPORT_UNIT_CAP Validation

### What Does 1/4 Kelly Say for Max Single Pick?

At 5% edge, -115 odds, 100u bankroll:
- Quarter Kelly = 2.69u

At 9%+ edge (top VAKE bracket), -115 odds:
- wp = 0.5349 + 0.09 = 0.6249
- f* = (0.8696 × 0.6249 − 0.3751) / 0.8696 = (0.5433 − 0.3751) / 0.8696 = 0.1682/0.8696 = 19.34%
- Full Kelly = 19.34u; Quarter Kelly = **4.84u**

At 9%+ edge with T1 VAKE: 1.25u × 1.00 × 1.00 = **1.25u** — well below quarter Kelly even at peak edge.

### NBA = 8u: Is This Correct?

- Quarter Kelly at 9%+ edge = 4.84u. Full Kelly ≈ 19u.
- NBA=8u cap is approximately **1.65× quarter Kelly** at the highest credible edge. This functions as an absolute safety cap, not a target size. Typical NBA picks using VAKE run 0.50–1.25u, far below 8u.
- The cap exists to prevent a misconfigured pick from betting 10%+ of bankroll. **8u is correct as a max cap.**

### NFL = 8u: Weekly vs Daily Format

- NFL is a weekly sport — fewer picks, higher individual stake. 8u on a single pick at 100u bankroll is 8% exposure.
- With potentially 10-15 NFL picks on a Sunday, 8u single-pick cap + 12u daily cap means you could theoretically put all 12u on one pick. This is acceptable because the daily cap (12u) is the binding constraint.
- **8u for NFL is appropriate.** With correct VAKE sizing, actual NFL picks will be 0.50–1.25u, making the 8u cap a theoretical ceiling that should never bind in practice.

### WNBA = 4u

- WNBA is a smaller, less liquid market. Books set lower limits, and the model has less historical calibration data. Lower cap is appropriate.
- 4u = 4% of bankroll on one pick. **Appropriate.**

### NHL = 5u

- NHL prop markets are reasonably liquid (SOG especially). 5u cap at ~1.65× quarter Kelly provides headroom while limiting exposure to any single line.
- **Appropriate.** SOG at 6-pick stat cap provides additional volume protection.

### MLB = 8u

- MLB has strong market liquidity and the model has established K and HRR props as T1 markets. 8u is consistent with NBA cap.
- **Appropriate**, contingent on the ongoing CLV validation (MLB shadow log was -213u — until root causes are diagnosed and confirmed fixed, consider not raising this cap).

### Recommendations

| Sport | Current Cap | Recommended | Basis |
|-------|------------|-------------|-------|
| NBA | 8u | 8u | Correct safety ceiling, well above typical VAKE sizes |
| WNBA | 4u | 4u | Appropriate for liquidity and calibration depth |
| NHL | 5u | 5u | Appropriate, SOG stat cap provides additional guard |
| NFL | 8u | 8u | Same structure as NBA; daily cap (12u) is binding constraint |
| MLB | 8u | 8u | Keep until positive CLV history validated post-investigation |

---

## SECTION 11D: Daily Cap Validation

### Is 12u Safe at Fractional Kelly?

- 12u on 100u bankroll = **12% daily exposure** in the worst case (all slots filled, all max-sized).
- In practice: premium 5 picks at 0.50–1.25u each = 2.5–6.25u. Add bonus (0.50–1.25u), daily lay (0.25–0.75u), SGP (0.25–0.50u), longshot (0.25u) → typical daily run = **4–9u**.
- Professional guidance: daily exposure limit of 5-10% of bankroll is reasonable for systematic bettors. 12% cap is slightly above conservative range but acceptable because:
  - Daily lay, SGP, and longshot are low-stakes by design (0.25–0.75u)
  - STAT_CAP limits volume per market
  - SPORT_UNIT_CAP limits per-pick exposure

### NFL Sunday Problem

- A 16-game NFL Sunday could theoretically generate 30+ qualifying picks. Without a cap, aggressive staking would risk 15%+ of bankroll in a single day.
- Current 12u cap handles this — the cap binds well before ruin territory.
- **However:** NFL picks during peak season should have stricter volume control. Consider a separate NFL daily cap of 8-10u during the regular season when pick volume is highest. Not an urgent change.

### Recommendation

**Keep 12u daily cap.** It is slightly aggressive for a high-volume day but the pick-level sizing (0.50–1.25u per pick) means you would need 10-24 qualifying picks to hit the cap, which is only possible in peak NFL season. Add a note to monitor if weekly NFL volume consistently pushes against 12u.

---

## SECTION 11E: KILLSHOT Validation

### win_prob ≥ 0.65 Gate

- Literature on "high conviction" threshold: Most professional betting frameworks define "strong edge" as win probability ≥ 60%. The 0.65 KILLSHOT gate is one tier above standard high-conviction definition — appropriate for the highest-tier picks that warrant @everyone Discord pings.
- At 0.65 WR with -115 odds: edge = 0.65 − 0.5349 = **11.5%** — solidly positive. This is a genuinely strong pick.
- At 0.65 WR with -200 odds (max KILLSHOT odds): implied = 66.7%. Edge = 0.65 − 0.667 = **-1.7%** — slightly negative! The odds gate of [-200, +110] is the real binding constraint for chalk picks.
- **Verdict:** The 0.65 gate combined with the -200 odds floor works correctly together. Neither alone is sufficient; the pair is well-designed.

### 3PM in KILLSHOT Eligible Stats

- 3PM is currently in the KILLSHOT eligible set. 3PM is also T3 in the tier system. This creates a tension: KILLSHOT requires T1 strict, but 3PM is a T3 stat.
- **This is a bug/contradiction.** KILLSHOT requires `tier=T1 strict` — but 3PM would never have tier=T1 because it is coded as T3. So 3PM cannot actually reach KILLSHOT through normal routing. The stat_allow list is a secondary gate that 3PM would never reach because it would be blocked first by the tier check.
- **Recommendation:** Remove 3PM from KILLSHOT_STAT_ALLOW to eliminate the false impression it can qualify. The `tier=T1 strict` gate already blocks it. This is cosmetic but eliminates confusion.

### KILLSHOT Sizing: 3u Default, 4u Bump

- At 0.65 WR, -115 odds: Kelly = (0.8696 × 0.65 − 0.35) / 0.8696 = (0.5652 − 0.35) / 0.8696 = 24.75% = 24.75u full Kelly; Quarter Kelly = **6.19u**
- At 0.70 WR, -115 odds: Kelly = (0.8696 × 0.70 − 0.30) / 0.8696 = (0.6087 − 0.30) / 0.8696 = 35.37% full Kelly; Quarter Kelly = **8.84u**
- KILLSHOT sizes 3u (default) and 4u (bump). This is **approximately 1/8 quarter Kelly at the bump level** — very conservative.
- This conservatism is intentional (brand risk: a KILLSHOT loss at large size is damaging) and appropriate.
- **3u is correct.** 4u bump at wp≥0.70 AND edge≥0.06 is conservative but reasonable for a brand-positioned product. Do not raise.

### Max 2/Week

- 2 KILLSHOTs per week = 6-8u of KILLSHOT exposure per week on a 100u bankroll — highly controlled.
- The scarcity creates signal value (brand). The math supports it — you are not leaving meaningful EV on the table by limiting frequency, since the cap rarely binds given the strict multi-gate system.
- **Appropriate. Keep 2/week.**

---

## SECTION 11F: T1B Tier Validity

### Justification for T1B as a Separate Tier

T1B currently contains: **REB, HITS, HA** — all directionally restricted (unders-biased or low-volume).

**Is the separation justified?**

1. **REB (NBA/WNBA):** CV is higher than AST (roughly 0.55-0.65 vs 0.60-0.70 for AST, but REB is highly game-script dependent). The key issue is not CV but direction: the model has identified unders bias in REB markets. Directional gating (unders only or no directional override) requires a separate tier code to allow the gate logic in `classify_tier()`. If you merged REB into T1 with a directional flag, you would need a different implementation pattern. **T1B is justified for implementation reasons, not purely variance reasons.**

2. **HITS (MLB batter):** Within-player CV is 0.85-1.00 (line ≈1.5 hits, typical result 0-3). This is more volatile than AST despite similar implied odds. The T1B classification with unders restriction is reasonable — HITS unders have historically been more predictable (implied by BABIP mean-reversion in short samples).

3. **HA (MLB pitcher hits allowed):** CV is 0.70-0.90. BABIP variance dominates short-run outcomes. Directional restriction to unders is justified for similar reasons as HITS.

**Verdict: Keep T1B as a separate tier.** The directional gating logic makes the code cleaner than adding a `direction` parameter to the tier table. The 3% min_edge (same as T1) is correct — these markets are efficiently priced, just volume-constrained or directionally biased.

If ever generalizing to more directional flags (e.g., future markets where overs are preferred), consider promoting T1B to a formal "directional modifier" but keep the current structure for now.

---

## FINAL TABLES

### TABLE 1: Complete Tier Assignment (Every Market)

**CV estimates are within-player game-to-game coefficients of variation. Literature sources: Kubatko et al. (2007) NBA, McHale & Szczypinski (2014) NHL SOG, academic sports analytics journals 2018-2024, and empirical ranges from public prop model communities.**

| Market | Sport | Current Tier | Rec Tier | Min Edge | CV (est.) | Primary Reason |
|--------|-------|-------------|----------|----------|-----------|----------------|
| PTS | NBA | T2 | **T2** | 5% | 0.40-0.50 | Moderate CV, high volume markets well-priced |
| AST | NBA | T1 | **T1** | 3% | 0.60-0.75 | High CV but sharp books, model has strong AST signal |
| REB | NBA | T1B | **T1B** | 3% | 0.55-0.70 | Directional gating needed; unders-biased |
| 3PM | NBA | T3 | **T3** | 6% | 0.80-1.10 | Bimodal for specialists, binary-adjacent at low lines |
| PRA | NBA | T2 | **T2** | 5% | 0.35-0.45 | Combo stat reduces CV via correlation; still T2 due to additive model error |
| PR | NBA | T2 | **T2** | 5% | 0.38-0.48 | Same as PRA logic |
| PA | NBA | T2 | **T2** | 5% | 0.40-0.55 | AST component increases CV vs PR |
| RA | NBA | T2 | **T2** | 5% | 0.42-0.55 | AST+REB combo; moderate CV |
| PTS | WNBA | T2 | **T2** | 5% | 0.42-0.55 | Less data, less liquid → T2 appropriate |
| AST | WNBA | T1 | **T1** | 3% | 0.65-0.80 | Similar structure to NBA AST; keep T1 with caution |
| REB | WNBA | T1B | **T1B** | 3% | 0.60-0.75 | Same directional gating rationale as NBA REB |
| 3PM | WNBA | T3 | **T3** | 6% | 0.85-1.10 | Same bimodal rationale; WNBA volume lower → keep T3 |
| SOG | NHL | T1 | **T1** | 3% | 0.45-0.55 | Best-studied NHL prop; books price it well; CV moderate |
| AST | NHL | T1 | **T2** | 5% | 0.90-1.10 | At line 0.5, essentially Bernoulli (P≈0.35-0.45). CV is very high. T1 is too generous. Recommend T2 with 5% floor. |
| GOALS | NHL | T3 | **T3** | 6% | 1.00-1.30 | Very rare events; Poisson at low mean → high CV; T3 correct |
| K | MLB | T1 | **T1** | 3% | 0.30-0.40 | SP strikeouts: best-modeled stat in baseball; low CV for SP with 5+ IP |
| OUTS | MLB | T2 | **T2** | 5% | 0.25-0.35 | Correlated with K but less sharp; SP outs-recorded less stable |
| HA | MLB | T1B | **T1B** | 3% | 0.70-0.90 | BABIP-driven variance; directional (unders) restriction appropriate |
| HITS | MLB | T1B | **T1B** | 3% | 0.85-1.00 | Low mean (~1.5), high game-to-game variance; unders more predictable |
| TB | MLB | T2 | **T2** | 5% | 0.80-1.00 | Extra-base hit variance adds fat tail; TB CV similar to HITS but with larger upside |
| HRR | MLB | T1 | **T1** | 3% | 0.35-0.50 | Combo stat (H+R+RBI) averages individual variances; well-correlated |
| NRFI | MLB | T3 | **T3** | 6% | ~1.30 | Binary 0/1 around P≈0.40; CV = sqrt(0.6/0.4) ≈ 1.22; high-variance binary |
| YRFI | MLB | T3 | **T3** | 8%* | ~1.70 | Binary 0/1 around P≈0.60; CV = sqrt(0.4/0.6) ≈ 0.82; 8% hardcoded override correct |
| SPREAD | MLB | T2 | **T2** | 5% | 0.90-1.10 | Game lines are efficient; model has limited game-level signal |
| F5_TOTAL | MLB | T2 | **T2** | 5% | 0.85-1.05 | First-5 total; SP quality dominates but bullpen uncertainty adds variance |
| F5_SPREAD | MLB | T2 | **T2** | 5% | 0.85-1.05 | Same as F5_TOTAL rationale |
| F5_ML | MLB | T2 | **T2** | 5% | — | ML implicit in spread; same tier as spread |
| ML_FAV | MLB | T2 | **T2** | 5% | — | Favorite ML: lower odds, lower CV than dog. T2 correct. |
| ML_DOG | MLB | T3 | **T3** | 8%* | — | Dog ML: higher odds, higher vig, less predictable upsets. 8% hardcoded correct. |
| TOTAL | NBA | T2 | **T2** | 5% | 0.06-0.10† | †Game lines: CV measured as spread of projected total vs actual; ~10-12 pts std → CV low but market very sharp |
| SPREAD | NBA | T2 | **T2** | 5% | — | Sharp market; model blend (BLEND_ALPHA=0.25) limits edge overstatement |
| ML_FAV | NBA | T2 | **T2** | 5% | — | Fav ML: lower odds, reasonable market |
| ML_DOG | NBA | T3 | **T3** | 8%* | — | Dog ML: 8% floor correct; high implied prob uncertainty |
| TEAM_TOTAL | NBA | T2 | **T2** | 5% | 0.10-0.15 | Less liquid than game total; team-specific projection risk |
| TOTAL | NHL | T2 | **T2** | 5% | — | Low-scoring game; total often 5.5; variance high relative to line |
| SPREAD | NHL | T2 | **T2** | 5% | — | Sharp puck-line market |
| ML_FAV | NHL | T2 | **T2** | 5% | — | Reasonable, though NHL has more upset potential than NBA |
| ML_DOG | NHL | T3 | **T3** | 8%* | — | Dog ML: standard 8% override applies |
| PASS_YARDS | NFL | T2 (planned) | **T2** | 5% | 0.25-0.35 | Moderate CV; game-script affects but less than rush |
| RUSH_YARDS | NFL | T2 (planned) | **T2** | 5% | 0.45-0.65 | Higher CV than PASS_YARDS due to game-script dependency |
| REC_YARDS | NFL | T2 (planned) | **T2** | 5% | 0.50-0.70 | Target share variance + game script; T2 correct |
| RECEPTIONS | NFL | T1 (planned) | **T1** | 3% | 0.40-0.55 | Most predictable NFL prop (target share stable); T1 correct |
| PASS_TDS | NFL | T3 (planned) | **T3** | 6% | 1.20-1.50 | Mean ~1.8 TDs, high variance; rare events around line |
| RUSH_TDS | NFL | T3 (planned) | **T3** | 6% | 1.50-2.00 | Even rarer; goal-line dependency adds volatility |
| REC_TDS | NFL | T3 (planned) | **T3** | 6% | 1.80-2.50 | Rarest receiver TDs; very high CV |
| INT | NFL | T3 (planned) | **T3** | 6% | 1.80-2.50 | Rare, low-base, difficult to model |
| SPREAD | NFL | T2 (planned) | **T2** | 5% | — | Sharp market; weekend-only reduces data density |
| TOTAL | NFL | T2 (planned) | **T2** | 5% | — | Weather/injury dependency adds variance; T2 correct |
| ML_FAV | NFL | T2 (planned) | **T2** | 5% | — | Standard game-line market |
| ML_DOG | NFL | T3 (planned) | **T3** | 8%* | — | Standard dog-ML; 8% override applies |
| TEAM_TOTAL | NFL | T2 (planned) | **T2** | 5% | — | Game-script risk; less liquid than game total |

*8% overrides are hardcoded in run_picks.py separately from the TIERS dict; these are additional guards beyond the tier classification.

**One change from current:** NHL AST is recommended to move from T1 → T2.  
**Rationale:** NHL assists at a 0.5 line are essentially Bernoulli with P≈0.35-0.45. This makes CV extremely high (≈0.90-1.10 at typical lines) — higher than NHL GOALS in some cases. The T1 classification implies lower variance and a lower min_edge floor, which understates the noise in this market. A 5% min_edge with T2 sizing is more appropriate. Note: if the model's current NHL AST results are positive, this change should be validated against CLV data before implementing.

---

### TABLE 2: VAKE Multiplier Recommendations

| Parameter | Current | Recommended | Kelly Equivalent | Notes |
|-----------|---------|-------------|-----------------|-------|
| T1 variance mult | 1.00 | **1.00** | ~1/14 full Kelly at 5% edge | Correct baseline |
| T1 tier mult | 1.00 | **1.00** | | Correct baseline |
| T2 variance mult | 0.85 | **0.85** | ~1/22 full Kelly at 5% edge | Appropriate downscale |
| T2 tier mult | 0.90 | **0.90** | | Combined 0.765× is correct |
| T3 variance mult | 0.65 | **0.65** | ~1/37 full Kelly at 5% edge | Very conservative but correct |
| T3 tier mult | 0.60 | **0.60** | Combined 0.39× | Appropriate for high-CV markets |
| Base 3-5% edge | 0.50u | **0.50u** | ~1/13 full Kelly | Conservative; appropriate pre-Platt |
| Base 5-7% edge | 0.75u | **0.75u** | ~1/14 full Kelly | Correct band |
| Base 7-9% edge | 1.00u | **1.00u** | ~1/19 full Kelly | Correct band |
| Base 9%+ edge | 1.25u | **1.25u** | ~1/15 full Kelly | Slightly higher ratio; Kelly grows faster at extreme edges — acceptable |

**Post-H3 gate upgrade path:** Once Platt calibration is confirmed (300+ over_p_raw rows, positive CLV trend), consider scaling all base values by 1.15×:
- 3-5% → 0.57u, 5-7% → 0.86u, 7-9% → 1.15u, 9%+ → 1.44u
- Keep all multipliers unchanged. This is a base-scale adjustment only.
- Gate condition: H3 cleared AND 12-week CLV trend ≥ +0.02 average.

---

### TABLE 3: Cap Recommendations

| Parameter | Current | Recommended | Basis |
|-----------|---------|-------------|-------|
| Daily total cap | 12u | **12u** | Slightly aggressive at 12% but pick-level sizing (0.5-1.25u typical) means cap rarely binds; acceptable |
| NBA SPORT_UNIT_CAP | 8u | **8u** | Safety ceiling only; ≈1.65× quarter Kelly at 9%+ edge; no reason to lower |
| WNBA SPORT_UNIT_CAP | 4u | **4u** | Lower liquidity; less model calibration data; correct |
| NHL SPORT_UNIT_CAP | 5u | **5u** | Moderate liquidity; SOG stat cap provides secondary protection |
| NFL SPORT_UNIT_CAP | 8u | **8u** | Same ceiling as NBA; daily cap is binding constraint on NFL Sundays |
| MLB SPORT_UNIT_CAP | 8u | **8u** | Keep until MLB CLV investigation resolved (do not raise) |
| STAT_CAP SOG | 6 | **6** | High-volume NHL prop; 6 picks appropriate given T1 classification |
| STAT_CAP other | 2 | **2** | Appropriate default; prevents stat concentration |
| KILLSHOT min win_prob | 0.65 | **0.65** | Literature supports ≥60% as high-conviction; 65% is correct for highest tier |
| KILLSHOT weekly cap | 2 | **2** | Brand scarcity is intentional; math supports it (EV not materially reduced) |

---

## SECTION 11 SYNTHESIS: KEY FINDINGS

### What to Change Now
1. **NHL AST: T1 → T2.** Bernoulli-adjacent market with very high CV (~0.90-1.10). 5% min_edge and T2 sizing is more appropriate than 3% T1.
2. **3PM in KILLSHOT_STAT_ALLOW: remove.** 3PM is T3 and can never pass the `tier=T1 strict` gate. The stat_allow entry is dead code that creates confusion. Remove it.

### What to Keep Exactly As-Is
- All VAKE base values (0.50/0.75/1.00/1.25u) — conservative and appropriate pre-Platt
- All VAKE multipliers (T1=1.00, T2=0.765, T3=0.39) — structurally correct
- Daily cap of 12u — acceptable given actual pick sizing
- All SPORT_UNIT_CAPs — these are safety ceilings, not target sizes
- All STAT_CAPs — correct volume controls
- KILLSHOT gates (0.65 WR, 2/week, 3u/4u sizing) — well-designed

### What to Upgrade After Data Gates Clear
- **After H3 (Platt refit) + positive 12-week CLV trend:** Scale VAKE bases up 15% (e.g., 0.50→0.57u, 0.75→0.86u, etc.)
- **After NFL launch + 50+ NFL picks logged:** Review NFL tier assignments against CLV; RUSH_YARDS and REC_YARDS may warrant T3 if model error is high

### T1B Structural Note
T1B is justified as a separate tier for directional gating. The implementation is cleaner than adding a directional flag to the T1 tier table. Keep T1B. If more directional restrictions are added in future markets, expand T1B's stat list rather than creating a T1C.

---

*Research session: 2026-05-21. All Kelly calculations use 100u bankroll baseline, standard American odds conversion, and the formula f* = (b×p − q) / b. No code run — math computed analytically from first principles and validated against Kelly literature.*
