# TIER FINDINGS — CONSOLIDATED
Generated: 2026-05-21 | Merged from TIER_FINDINGS_T1.md through T6.md

---

## SECTION 1: VARIANCE THEORY — FOUNDATION OF VAKE

### Kelly Criterion Basics

**Formula:** f* = (b×p - q) / b
- b = decimal odds - 1 (net odds on a winning bet)
- p = estimated win probability
- q = 1 - p

Full Kelly maximises log-wealth (geometric) growth. Any fixed-fraction strategy higher than Kelly produces lower long-run growth and higher ruin exposure. Sharps universally use fractional Kelly.

**Fractional Kelly — what sharps actually use:**
- Full Kelly: ~50% drawdown expected with high probability. Never used in practice.
- Half Kelly (0.5×): ~75% of full Kelly's growth rate, ~50% variance, ~18% max drawdown. Ed Thorp's blackjack practice.
- Quarter Kelly (0.25×): ~55% of full Kelly's growth, ~25% variance. Most common among sharp sports bettors.
- Academic consensus (Thorp 2008): recommends half Kelly as default; bettors systematically overestimate edge, so half Kelly auto-corrects. Ziemba ("The Kelly Capital Growth Investment Criterion," 2011): 1/4–1/2 Kelly is the practical sweet spot.
- Rule: the less certainty you have in your edge estimate, the smaller the fraction.

**VAKE vs Kelly — T1 (5% edge, 58.5% WR, -115 odds):**
- Full Kelly = 10.75% of bankroll = 10.75u
- Quarter Kelly = 2.69u
- VAKE T1 = 0.75u ≈ **1/14 full Kelly** (0.075×)

**VAKE vs Kelly — T2 (5% edge, -115 odds):**
- VAKE T2 = 0.574u ≈ **1/19 full Kelly** (0.053×)

**VAKE vs Kelly — T3 (6% edge, -110 odds):**
- Full Kelly = 12.6u; Quarter Kelly = 3.15u
- VAKE T3 = 0.29u ≈ **1/43 full Kelly** (0.024×)

**Summary table:**
| Tier | Edge | VAKE | Full Kelly | VAKE/Kelly |
|------|------|------|------------|------------|
| T1 (min) | 3% | 0.50u | 6.45u | ~1/13 |
| T1 (mid) | 5% | 0.75u | 10.75u | ~1/14 |
| T2 | 5% | 0.57u | 10.75u | ~1/19 |
| T3 | 6% | 0.29u | 12.6u | ~1/43 |

VAKE runs ~1/13 to 1/43 of full Kelly — approximately 1/4 to 1/9 of quarter Kelly. Extremely conservative. Appropriate given: high stat-level CV (0.5–1.0+), model edge uncertainty, portfolio variance compounding, and prop market CLV noise.

**EV per dollar staked:**
- T1 at 5% edge: +9.4% ROI
- T2 at 5% edge: +9.4% ROI
- T3 at 6% edge: +11.5% ROI

---

### CV Empirical Values (within-player, game-to-game: CV = σ/μ)

| Stat | CV (σ/μ) | Notes |
|------|----------|-------|
| NBA PTS | 0.40–0.55 | Stars ~0.40; role players 0.55–0.70 |
| NBA AST | 0.50–0.65 | Higher than PTS; primary playmakers ~0.50 |
| NBA REB | 0.45–0.60 | Bigs ~0.45; guards ~0.55–0.60 |
| NBA 3PM | 0.70–1.00 | Highest NBA prop. Bimodal for specialists. |
| NHL SOG | 0.50–0.70 | Forwards ~0.55–0.65; defenders higher |
| NHL GOALS | 1.00–1.50 | Binary-adjacent; mean ~0.3–0.5/game |
| NHL AST | >1.00 | Bernoulli at 0.5 line; P(0 ast) ~55–65% |
| MLB K | 0.30–0.45 | Most predictable stat. R²=0.81–0.88. |
| MLB HR | 1.20–1.80 | Very high CV; near-Bernoulli per game |
| MLB HITS | 0.80–0.84 | .260 hitter: E[H]=1.04, SD=0.877 |
| NFL PASS_YARDS | 0.35–0.42 | Empirical: mean=224.1, σ=79.3, CV≈0.354 |
| NFL RUSH_YARDS | 0.65–0.90 | Game-script dominant; boom/bust |
| NFL REC_YARDS | 0.55–0.75 | Target-share driven; role-dependent |
| NFL RECEPTIONS | 0.40–0.55 | Most stable NFL prop |
| NFL PASS_TDS | 0.90–1.10 | Mean ~1.7; P(0 TDs)=20–25% |

**CV thresholds for Kelly aggressiveness:**
- CV > 0.60: fractional Kelly (0.25–0.33×) becomes essential
- CV > 0.80: reduce further; consider 0.15–0.20×
- CV > 1.00: Kelly may compute near-zero or negative even with real edge. Treat Kelly output >5% with extreme skepticism.

---

### Portfolio Variance

**Correlation compounding (10 picks, average correlation r=0.10):**
- Portfolio variance = N × var × (1 + (N-1)×r)
- At r=0.10, N=10: portfolio variance = **1.9× vs independent**
- At r=0.20, N=10: portfolio variance = **2.8× vs independent**
- 10 picks at r=0.10 behaves like ~5 truly independent picks.

**Same-game props (Tatum PTS + Tatum AST + Tatum REB): r ≈ 0.50–0.70 (very high).**
**Cross-game same-stat (NBA): r ≈ 0.05–0.15 (mostly independent).**

**12u daily cap validation:**
- 12u = 12% max daily drawdown (12% of 100u bankroll)
- Typical session: premium 5 picks (2.5–6.25u) + bonus + daily lay + SGP = 4–9u
- Cap is not binding in normal operations; provides ceiling for extreme days
- Kelly portfolio theory: total exposure ≤ sum of individual Kelly fractions → 12u cap is well within safe range

**P(50% drawdown) by Kelly fraction:**
- Full Kelly: ~50%. Quarter Kelly: ~8–12%. Half Kelly: ~18–25%.

---

## SECTION 2: MARKET EFFICIENCY FRAMEWORK

### Pinnacle Hold% vs Retail Book Hold%

| Book Type | Hold% (Game Lines) | Hold% (Player Props) |
|-----------|-------------------|---------------------|
| Pinnacle (sharp) | 1.5–2.5% | 4–6% |
| Circa / Bookmaker | 2–3% | 4–7% |
| DraftKings / FanDuel | 4–8% | 8–15% |
| BetMGM / Caesars | 5–8% | 8–15% |
| Same-Game Parlays | 15–25%+ | — |

**Sharp CLV targets:**
- NFL/NBA game lines: +1–2% CLV consistently. Hard to sustain above +3%.
- Player props: +3–7% CLV. +5% is achievable on soft lines.
- CLV above +2% = strong evidence of genuine edge.

**Player props are the least efficient major betting market.** Evidence:
1. Low limits: $500–$3k vs $10k–$50k for game lines
2. Books price props algorithmically, not via two-way sharp action
3. Hold% differential: 8–15% on props vs 4–8% on game lines
4. Key (Unabated): "CLV doesn't mean anything in props. There are very few market-making books when it comes to props."

**Soft market signal by hold%:**
- Hold <3%: sharp pricing
- Hold 3–6%: moderate; some edges remain
- Hold 6–10%: soft market; significant edge opportunities
- Hold >10%: very soft; books set lines algorithmically with little sharp input

**Structural public biases:**
| Bias | Direction | Notes |
|------|-----------|-------|
| Favorite bias | Overbetting favorites | Books compensate by shading; sharp bettors fade heavy chalk |
| Over bias | Public leans OVER | Books shade totals up; mild structural under value |
| Home team bias | Overbetting home teams | Road underdogs offer value in efficient models |
| Star player bias | Overbetting star OVER props | LeBron/Mahomes overs shaded high; unders have value |

**Efficiency by market** (most → least efficient):
1. NFL spreads/totals (highest liquidity, most sharp money)
2. NBA spreads/totals
3. MLB spreads/totals
4. NHL spreads/totals
5. MLB/NBA/NHL game lines (ML)
6. Player props (all sports) — most exploitable

---

## SECTION 3: NBA PLAYER PROPS

### 3.1 NBA PTS — T2 (5% min edge) CONFIRMED

- CV: 0.30–0.45 (starters 0.25–0.33; rotation 0.35–0.45)
- Distribution: approximately Normal with mild right skew for superstars
- Public massively overbets star PTS overs → books shade lines 1–1.5 pts for star scorers
- Hold%: 6–8% on star scorers, 4–5% on rotation players
- Limits: DraftKings $3,000–$5,000 per bet
- **Recommendation: T2 confirmed. 5% min edge confirmed.**
- Do not move to T1. Public bias means genuine edges need a larger cushion to filter false positives.

### 3.2 NBA AST — T1 (3% min edge) CONFIRMED

- CV: 0.45–0.55 (elite passer ~0.40–0.48; primary ball-handler ~0.47–0.55)
- AST variance is **epistemically capturable** — role/pace/lineup driven, not shooting variance
- Market efficiency: highest of any NBA prop. Hold%: 4–5%. Lower limits signal book uncertainty — exploitable.
- CLV on AST closes with model more often than PTS → reliable edge signal
- No systematic public over/under bias on AST (unlike PTS overs)
- **Recommendation: T1 confirmed. 3% min edge confirmed.**
- KILLSHOT eligibility: correct (T1, epistemically manageable variance)

### 3.3 NBA REB — T1B (3% min edge, unders) CONFIRMED

- CV: 0.38–0.70 (high-rebounders 0.38–0.45; low-rebounding guards 0.55–0.70)
- Public overbets big-man REB overs; books shade lines 0.5–1.0 high
- REB overs are structural under-bets. REB unders have positive expected CLV.
- T1B directional gate (unders only at line ≥3.5) is empirically correct
- Distribution: Negative Binomial for high-rebounders (overdispersed)
- **Recommendation: T1B confirmed. Directional gate is the key feature.**

### 3.4 NBA 3PM — T3 (6% min edge) CONFIRMED; KILLSHOT REMOVAL REQUIRED

- CV: 0.65–1.20 (volume shooter specialist ~0.65–0.85; low-volume ~0.95–1.20)
- Bimodal distribution for specialists (0–1 and 4–5 modes) — NB model approximates but doesn't capture true bimodality; HIGH_VAR flag handles this
- Hold%: 7–9% (wider than PTS/AST)
- Public massively overbets specialist 3PM overs → books shade specialist lines 0.5–1.0 high
- **3PM must be REMOVED from KILLSHOT_STAT_ALLOW:**
  - 3PM is T3; KILLSHOT requires `tier=T1 strict`. 3PM can never pass this gate.
  - The KILLSHOT_STAT_ALLOW entry is dead code — creates false impression 3PM can qualify.
  - CV ~0.80–1.10 is incompatible with KILLSHOT brand promise.
  - Change: `KILLSHOT_STATS = {PTS, AST, SOG, 3PM}` → `{PTS, AST, SOG}`
- **Recommendation: T3 confirmed. 6% min edge confirmed. Remove from KILLSHOT.**

### 3.5 NBA Combo Props (PRA, PR, PA, RA) — All T2 (5% min edge) CONFIRMED

**CV analysis:**
Using PTS=22.5 (σ=7.0), REB=6.5 (σ=3.5), AST=5.5 (σ=2.5) and COMBO_RHO from 75,367 player-games:
- ρ(PTS,REB)=0.333, ρ(PTS,AST)=0.233, ρ(REB,AST)=0.251

| Combo | Mean | CV |
|-------|------|----|
| PTS   | 22.5 | 0.311 |
| REB   | 6.5  | 0.538 |
| AST   | 5.5  | 0.455 |
| PRA   | 34.5 | 0.285 |
| PR    | 29.0 | 0.277 |
| PA    | 28.0 | 0.282 |
| RA    | 12.0 | 0.353 |

PRA/PR/PA have **lower CV than standalone PTS** (diversification benefit).
But combo props carry wider vig (-115–120) and less sharp action → lower market efficiency.
The efficiency disadvantage offsets the CV advantage. T2 at 5% is correct for all four.

**Recommendation: All combos T2 confirmed. Do not upgrade to T1B.**

### NBA Summary Table

| Stat | Tier | Min Edge | CV | Direction | Change |
|------|------|----------|----|-----------|--------|
| PTS | T2 | 5% | 0.30–0.45 | Both OK | None |
| AST | T1 | 3% | 0.45–0.55 | Both OK | None |
| REB | T1B | 3% | 0.38–0.70 | Unders only | None |
| 3PM | T3 | 6% | 0.65–1.20 | Both | Remove from KILLSHOT |
| PRA | T2 | 5% | 0.285 | Both | None |
| PR | T2 | 5% | 0.277 | Both | None |
| PA | T2 | 5% | 0.282 | Both | None |
| RA | T2 | 5% | 0.353 | Both | None |

---

## SECTION 4: WNBA

### WNBA Market Efficiency vs NBA

WNBA is meaningfully less efficiently priced than NBA:
- ~20× fewer bets per game than average NBA game
- Lines can move 3+ points open-to-close (NBA: 0.5–1.0 typical)
- Cross-book discrepancy example: A'ja Wilson at 18.5 at one book, 21.5 at another simultaneously
- Vig: WNBA -115/-115 (6.5% hold) vs NBA -110/-110 (4.5% hold)
- Reverse line movement ROI ~10% documented in WNBA spread markets

**Implication: More exploitable edges than NBA, but each edge is less certain (thinner market, less sharp calibration).**

### WNBA Tier Assignments

WNBA inherits NBA tier structure with **WNBA_EDGE_FLOOR=0.035** as the sport-level adjustment. No WNBA-specific tiers needed.

**WNBA vs NBA CV comparison (WNBA_RESEARCH_FINDINGS.md §2, n=336 player-games, 2024):**
| Stat | NBA CV | WNBA CV | Delta |
|------|--------|---------|-------|
| PTS | ~0.25 | ~0.36 | +44% higher |
| REB | ~0.47 | ~0.43 | -9% lower |
| AST | ~0.50 | ~0.56 | +12% higher |
| 3PM | ~0.80 | ~0.48 (top shooters) | -40% lower |

WNBA 3PM is less volatile for top shooters (Clark, Ionescu) because they're consistent contributors, not boom/bust like NBA specialists. Still keep at T3 for market thinness.

**WNBA combo correlations (COMBO_RHO_WNBA — nearly additive):**
- PTS-REB: 0.13 (vs NBA 0.333)
- PTS-AST: 0.04 (vs NBA 0.233)
- REB-AST: 0.05 (vs NBA 0.251)

Near-zero correlations mean WNBA combos don't get the diversification benefit NBA combos get. Keep all combos at T2.

**WNBA SPORT_UNIT_CAP = 4u: Confirmed.** Ratio to NBA (8u) reflects limit ratio and CV differential.

**WNBA KILLSHOT: remain excluded** until: (1) WNBA exits SHADOW_SPORTS, (2) sufficient CLV data, (3) wp floor raised to 0.70+ if ever enabled.

**Early-season gate: retain as coded** (block days 1–3, dampen days 4–21).

### WNBA Tier Table

| Stat | NBA Tier | WNBA Tier | Min Edge | Notes |
|------|---------|-----------|----------|-------|
| PTS | T2 | T2 | 5% | Higher CV handled via SIGMA_WNBA |
| AST | T1 | T1 | 3.5% effective | WNBA_EDGE_FLOOR applies |
| REB | T1B | T1B | 3.5% effective | Same directional gate |
| 3PM | T3 | T3 | 6% | Thin market even for Clark/Ionescu |
| PRA | T2 | T2 | 5% | Near-additive COMBO_RHO |
| PR/PA/RA | T2 | T2 | 5% | Same |
| TOTAL | T2 | T2 | 5% | GAME_SIGMA["WNBA"]=10.0 |
| SPREAD | T2 | T2 | 5% | Variable spread |
| ML_FAV | T2 | T2 | 5% | |
| ML_DOG | T3 | T3 | 7% | Same as NBA ML_DOG |

---

## SECTION 5: NHL PLAYER PROPS

### 5.1 NHL SOG — T1 (3% min edge) CONFIRMED

- CV: 0.47–0.57 (top-line forward, 2.5–4.5 SOG/game avg)
- Sharp bettors recognize SOG as sharpest NHL prop market. Hold%: 8–12%.
- Books track SOG data closely; power-play deployment changes create stale lines (exploitable).
- STAT_CAP=6: justified. NHL slates 7–15 games; 6 picks appropriate.
- **Recommendation: T1 confirmed. 3% min edge confirmed.**

### 5.2 NHL AST — **RECLASSIFY T1 → T3** (6% min edge)

**This is the most critical structural error found in the current tier system.**

At the 0.5 line, NHL AST is a **pure binary Bernoulli bet**:
- Elite playmakers (McDavid, ~1.02 APG): fail to record an assist in 35–45% of games
- Players ranked 20–50 in APG: record zero assists in 50–65% of games
- Distribution: bimodal (mode at 0, secondary cluster at 1). Right-skewed with fat upper tail.
- CV for player averaging 0.45 APG with SD ~0.55: **CV ≈ 1.22**
- Hold%: 20%+ (comparable to goal scorer markets, not SOG markets)

T3 classification aligns NHL AST with 3PM — both are binary-adjacent props with high CV where the book prices in substantial vig.

**Recommendation: T1 → T3. Min edge: 6%.**

**Note on T6 discrepancy:** T6 recommended T1→T2. T3's analysis was deeper and more specific to the 0.5 Bernoulli structure. **T3 (T1→T3, 6% min edge) is the correct recommendation.** T2 with 5% underweights the 20%+ hold and CV >1.0 profile.

### 5.3 NHL GOALS — T3 (6% min edge) CONFIRMED (planned)

- CV: 1.23–1.73 (even higher than AST)
- P(goals=0): 45–50% for elite scorers, 70–75% for average forwards
- Hold%: 20–35% (worst in NHL props)
- **Recommendation: T3 confirmed for planned implementation. Add STAT_CAP=4 at go-live.**

### NHL Summary Table

| Stat | Current | Recommended | Min Edge | CV | Notes |
|------|---------|-------------|----------|----|-------|
| SOG | T1 | **T1** | 3% | 0.47–0.57 | Confirmed. STAT_CAP=6. |
| AST | T1 | **T3** | 6% | >1.0 | **CHANGE. Bernoulli at 0.5 line.** |
| GOALS | T3 | **T3** | 6% | 1.23–1.73 | Confirmed. Add STAT_CAP=4. |

---

## SECTION 6: MLB PITCHER PROPS

### 6.1 MLB K (Strikeouts) — T1 (3% min edge) CONFIRMED

- CV: 0.28–0.44. R²=0.81–0.88 for underlying pitcher quality model. Most predictable MLB stat.
- Sharp market; books use CSW (Called Strike + Whiff Rate) from Baseball Savant/FanGraphs
- K Under gate: retain. Industry consensus is "K overs, not unders" as primary edge direction.
- **Recommendation: T1 confirmed. 3% min edge confirmed.**

### 6.2 MLB OUTS — T2 (5% min edge) CONFIRMED

- Effective CV: 0.35–0.50 (CV accounting for manager-hook risk; raw CV ~0.20–0.26)
- Manager hook risk: single biggest driver of variance — unmodellable binary decision
- Manager style, pitch-count limits, game-script blowouts, rain delays all create step-function risk
- OUTS is strictly harder to project than K for the same pitcher
- **Recommendation: T2 confirmed. 5% min edge confirmed.**

### 6.3 MLB HA (Hits Allowed) — T1B (3% min edge) CONFIRMED

- CV: 0.40–0.55 (BABIP randomness adds noise on top of pitcher quality)
- BABIP near-zero predictability game-to-game (Voros McCracken research)
- Directional (unders on elite pitchers); books softer on HA than K
- **Recommendation: T1B confirmed. 3% min edge confirmed.**

---

## SECTION 7: MLB BATTER PROPS

### 7.1 MLB HITS — T1B (3% min edge) CONFIRMED

- CV: 0.80–0.84 (.260 hitter: E[H]=1.04, SD=0.877)
- P(0 hits): ~30% for .260 hitter with 4 ABs. Not binary-adjacent at 0.5 line (P(hit ≥ 1) ≈ 70%).
- T1B with directional gating (overs on 0.5 line) is the correct handling
- **Recommendation: T1B confirmed. 3% min edge confirmed.**

### 7.2 MLB TB (Total Bases) — T2 (5% min edge) CONFIRMED

- CV: 0.84–0.96 (additional hit-type variance on top of HITS)
- Power production (XBH rate) adds second Bernoulli trial on top of base-hit probability
- Books calibrate via Statcast exit velocity/launch angle; moderate efficiency
- **Recommendation: T2 confirmed. 5% min edge confirmed.**

### 7.3 MLB HRR (Hits+Runs+RBIs) — T1 (3% min edge) CONFIRMED

- CV: 0.50–0.75 (diversification across 3 correlated stats reduces CV below single-stat HITS)
- P(HRR ≥ 2): ~55–65% for lineup-relevant batters at 1.5 line → not binary-adjacent
- Books underweight combinatorial path diversity (many ways to reach ≥2 HRR)
- Books slow to adjust for lineup shuffles → primary edge angle: batting order changes
- **Recommendation: T1 confirmed. 3% min edge confirmed. Weight batting order heavily in pick scoring.**

### MLB Batter/Pitcher Summary

| Stat | Tier | Min Edge | CV | Notes |
|------|------|----------|----|-------|
| K | T1 | 3% | 0.28–0.44 | Overs gate. Best MLB prop. |
| OUTS | T2 | 5% | 0.35–0.50 | Manager-hook risk unmodellable. |
| HA | T1B | 3% | 0.40–0.55 | Unders on elite starters. |
| HITS | T1B | 3% | 0.80–0.84 | Overs on 0.5 line. |
| TB | T2 | 5% | 0.84–0.96 | Hit-type variance layer. |
| HRR | T1 | 3% | 0.50–0.75 | Lineup position key signal. |

---

## SECTION 8: MLB GAME LINES

### 8A. NRFI/YRFI — Both T3 CONFIRMED

- P(NRFI): ~55–65% depending on pitching
- CV(NRFI) at P=0.60: **0.816**; CV(YRFI) at P=0.40: **1.225**
- Hold: 6–10% (soft recreational market)
- YRFI 8% override: **justified** (CV asymmetry vs NRFI)
- NRFI 6% floor: **confirmed**

| Market | Tier | Min Edge |
|--------|------|----------|
| NRFI | T3 | 6% |
| YRFI | T3 | 8% (maintain override) |

**Warning:** At 6–10% hold, a 6% edge computed against true probability represents only ~2% edge net of vig at a -140 NRFI line. Verify edge is computed against the actual book price (inclusive of vig), not against true probability.

### 8B. MLB Runline (±1.5) — **T2 → T3** (6% min edge)

- Cover rate: favorites cover -1.5 in ~38–42% of games
- 30% of MLB games decided by exactly 1 run → line outcome flips in ~30% of games
- CV at P(cover)=0.40: **1.22** (same territory as YRFI)
- Fixed line does NOT flex to balance coverage (unlike NBA variable spread)
- **Recommendation: T2 → T3. 6% min edge.**

### 8C. MLB F5 Markets

| Market | Current | Recommended | Min Edge | Rationale |
|--------|---------|-------------|----------|-----------|
| F5_TOTAL | T2 | **T1B** | **3%** | Lower σ than full game (2.6 vs 4.0), softer market, pitcher signals clean |
| F5_SPREAD | T2 | T2 | 5% | Slightly higher CV; keep T2 |
| F5_ML | T2 | T2 | 5% | Binary outcome but cleaner than full-game ML; monitor |

### 8D. MLB ML_DOG — T3 (8% override) CONFIRMED

- CV range: 1.22 (+150) to 2.00+ (+400)
- 8% override correct for typical range (+140–+250)
- Consider excluding +300+ dogs or raising to 10% for extreme range
- **Recommendation: T3 with 8% override maintained.**

### 8E. MLB TOTAL — T2 (5% min edge) CONFIRMED

- CV: 0.457 (σ=4.0, mean ~8.75)
- Moderate efficiency; pitcher quality priced in
- **Recommendation: T2 confirmed.**

### 8F. MLB ML_FAV — T2 (5% min edge) CONFIRMED

- CV: 0.816 at -150 (implied 60%)
- Public overbets MLB favorites; books shade lines → 5% edge must clear the shade
- **Recommendation: T2 confirmed.**

### 8G. MLB TEAM_TOTAL — **T2 → T1B** (3% min edge)

- CV: ~0.545 (team σ ≈ 2.3–2.5, mean ~4.4)
- Softest MLB game line — derivative pricing, lower volume, less sharp attention
- **Recommendation: T2 → T1B. 3% min edge.**

---

## SECTION 9: NBA / WNBA / NHL GAME LINES

### 9A. TOTAL

| Sport | Current | Recommended | Min Edge | CV | Notes |
|-------|---------|-------------|----------|----|-------|
| NBA | T2 | T2 | 5% | 0.053 | Highest efficiency. 5% real when it appears; 3% risks false positives. |
| WNBA | T2 | T2 | 5% | ~0.064 | Less efficient than NBA but similar CV. |
| NHL | T2 | T2 | 5% | ~0.298 | Historical under bias at lines 5.5+; calibration note. |

### 9B. SPREAD

| Sport | Current | Recommended | Min Edge | Notes |
|-------|---------|-------------|----------|-------|
| NBA | T2 | T2 | 5% | Sharpest market in model. 5% min captures only real edges. |
| NHL (Puck Line ±1.5) | T2 | **T3** | **6%** | Fixed ±1.5, cover rate ~32%, CV ~1.46. Same structure as MLB runline. |
| MLB (Runline ±1.5) | T2 | **T3** | **6%** | (See 8B above) |

**Fixed-line spread rule:** Both MLB runline and NHL puck line are fixed at ±1.5 (do not flex to ~50% cover probability). Cover rates of 32–42% create CV values of 1.22–1.46 — firmly T3 territory. **Both should be T3 with 6% min edge.**

### 9C. ML_FAV

All sports: T2 (5% min edge) confirmed.
- NBA: public over-bets → books compensate → 5% must clear shading
- NHL: less public distortion; efficient market
- MLB: (see 8F)

### 9D. ML_DOG — Sport-Specific Min Edge

Current blanket 8% override is too aggressive for NHL (parity sport) and correct for MLB (lottery-ticket range).

| Sport | Tier | Recommended Min Edge | Rationale |
|-------|------|---------------------|-----------|
| NHL ML_DOG | T3 | **6%** | Dogs at +110–+200; parity means win rate ~40–43%; 8% leaves value on table |
| NBA ML_DOG | T3 | **7%** | CV 1.22–1.41; richer NBA data; 8% too conservative for +130 range |
| MLB ML_DOG | T3 | **8% (unchanged)** | Widest odds range (+300+ possible); lowest per-game projection quality |

### 9E. TEAM_TOTAL

| Sport | Current | Recommended | Min Edge | Notes |
|-------|---------|-------------|----------|-------|
| NBA | T2 | **T1B** | **3%** | Softest NBA game line. Derivative pricing lags game total. |
| NHL | T2 | T2 | 5% | Less signal quality; monitor CLV before promoting. |
| MLB | T2 | **T1B** | **3%** | (See 8G above) |

---

## SECTION 10: NFL MARKET TIER ASSIGNMENTS

### Key NFL Context

- NFL props carry 8–15% hold (vs NBA props 6–10%). Lower limits ($250–$500 vs NBA $1,000–$5,000).
- NFL game lines carry 4.55–4.76% hold (same efficiency as NBA spreads).
- Once-per-week format: fewer picks per season, higher epistemic uncertainty (less rolling calibration).
- **No NFL KILLSHOT at launch.** Zero calibration data — wp estimates cannot be trusted at ≥0.65 for 3u sizing. Block NFL from KILLSHOT for first season.

### 10A. NFL PASS_YARDS — T2 (5% min edge) CONFIRMED

- CV: 0.35–0.42 (most stable offensive position)
- 73% of passing yards variance attributable to QB ability/offense; 27% opponent defense
- Mixed efficiency: sharp for marquee QBs (Mahomes/Lamar — heavy public action), softer for middling QBs
- **Recommendation: T2 confirmed. 5% min edge.**

### 10B. NFL RUSH_YARDS — **T2 → T3** (6% min edge)

- CV: 0.65–0.90+ (highest-variance non-binary NFL prop)
- Game-script is the dominant source: trailing team abandons run → RB blowout game = 0–20 yards
- P(rush yards < 20 in bad game script): ~15–20%
- Described by betting analysts as "the hardest NFL prop to project"
- **Recommendation: T2 → T3. 6% min edge. Separate from YARDS umbrella stat.**

### 10C. NFL REC_YARDS — T2 (5% min edge) CONFIRMED

- CV: 0.55–0.75 (WR1 on pass-heavy teams ~0.55; boom/bust WRs ~0.70–0.80)
- Softer than PASS_YARDS; 10–20 yard cross-book discrepancies common
- **Recommendation: T2 confirmed. 5% min edge.**

### 10D. NFL RECEPTIONS — **T1 (planned) → T2** (5% min edge)

- CV: 0.40–0.55 (most stable NFL prop; target share relatively sticky)
- Slightly higher CV than NBA AST (T1) + weekly format = lower sample count per season
- NFL props hold: 8–15% vs NBA props 6–10% (lower efficiency than NBA AST market)
- No model calibration data yet (new sport)
- **Recommendation: Downgrade planned T1 → T2. Revisit after one NFL season.**

### 10E. NFL PASS_TDS — T3 (6% min edge) CONFIRMED; REC_TDS/RUSH_TDS EXCLUDED

**PASS_TDS:**
- CV: 0.90–1.10. Mean ~1.7–1.8 TDs/game. P(0 TDs): 20–25%.
- Lines at 1.5 TDs = binary-adjacent (will QB throw 2+ TDs?)
- Soft market (public over-bets TD overs). Structural value on UNDER 1.5 for star QBs.
- **T3 confirmed. 6% min edge. Do NOT make KILLSHOT eligible.**

**RUSH_TDS: EXCLUDE**
- CV >>1.5 (Bernoulli at mean=0.35: CV ≈ 1.44)
- P(rush TD = 0): 65–75% of RB games
- Cannot model reliably without red-zone touch/carry data

**REC_TDS: EXCLUDE**
- CV >>1.5 (even more binary than RUSH_TDS)
- P(rec TD = 0): 72–82% of WR games
- Requires red-zone target data not in model

### 10F. NFL INT — EXCLUDE

- CV effectively >1.50 (overdispersed: 0,0,0,2,0,3... pattern)
- Mean ~0.74 INTs/game; P(INT=0) ≈ 55–65%
- Hold: 10–15%+. Sharp book limits: $100–$250 max.
- Requires EPA/pressure rate data not in model
- **EXCLUDE from model.**

### 10G. NFL Game Lines — T2 (6% min edge override)

NFL game lines are the sharpest markets in the model. Apply **NFL-specific min_edge = 6%** (vs 5% for NBA) to: SPREAD, TOTAL, ML_FAV, TEAM_TOTAL. ML_DOG keeps 8% override.

| Market | Tier | Min Edge | Notes |
|--------|------|----------|-------|
| SPREAD | T2 | 6%* | Most saturated market in sports betting |
| TOTAL | T2 | 6%* | Weather effects are primary exploitable angle |
| ML_FAV | T2 | 5% | Standard game-line sizing |
| ML_DOG | T3 | 8% | Standard ML_DOG override |
| TEAM_TOTAL | T2 | 5% (or 6%*) | Less liquid than game total |

*6% NFL-specific floor: `NFL_GAME_LINE_MIN_EDGE = 0.06`

### NFL SPORT_UNIT_CAP = 5u (NOT 8u)

T5 recommendation: NFL is a weekly sport (17 game-weeks vs NBA 82 games). Each miss has higher marginal impact on season P&L. Prop limits at retail books ($250–$500) support lower cap.
- T6 recommendation: 8u (same as NBA) — daily cap (12u) is binding constraint anyway.
- **Resolution: T5 is more conservative; use 5u.** Consistent with NHL (5u, similar weekly cadence considerations).

### NFL STAT_CAP Recommendations

| Stat | Cap | Reason |
|------|-----|--------|
| PASS_YARDS | 2 | 1 QB per team; 2 good matchups max |
| RUSH_YARDS | 1 | High CV, game-script correlated |
| REC_YARDS | 2 | Multiple WR1s per slate |
| RECEPTIONS | 2 | Same as REC_YARDS |
| PASS_TDS | 2 | Binary-adjacent; don't stack |
| SPREAD | 3 | Can diversify across games |
| TOTAL | 3 | Same |
| ML_FAV | 2 | |
| ML_DOG | 1 | High variance; 1 max |
| TEAM_TOTAL | 2 | Correlated with TOTAL |

### NFL Summary Table

| Stat | Planned | Recommended | Min Edge | CV | Notes |
|------|---------|-------------|----------|----|-------|
| PASS_YARDS | T2 | **T2** | 5% | 0.35–0.42 | Star QB lines soft |
| RUSH_YARDS | T2 | **T3** | 6% | 0.65–0.90 | Game-script kills projection |
| REC_YARDS | T2 | **T2** | 5% | 0.55–0.75 | Line shop aggressively |
| RECEPTIONS | T1 | **T2** | 5% | 0.40–0.55 | Weekly format; no calibration data |
| PASS_TDS | T3 | **T3** | 6% | 0.90–1.10 | Include; binary-adjacent soft market |
| RUSH_TDS | T3 | **EXCLUDE** | — | >1.50 | Too binary; no red-zone data |
| REC_TDS | T3 | **EXCLUDE** | — | >1.50 | Same |
| INT | — | **EXCLUDE** | — | >1.80 | Sparse; no pass defense data |
| SPREAD | T2 | **T2** | 6%* | — | NFL-specific floor |
| TOTAL | T2 | **T2** | 6%* | — | Weather-driven edges |
| ML_FAV | T2 | **T2** | 5% | 0.71–0.82 | |
| ML_DOG | T3 | **T3** | 8% | 1.41–1.73 | Standard override |
| TEAM_TOTAL | T2 | **T2** | 5% | — | |

---

## SECTION 11: VAKE CALIBRATION + FINAL TABLES

### Edge Threshold Validation (from first principles)

**Literature benchmarks by market type:**
- Tight props (NBA PTS, NHL SOG, MLB K): 2–4% sufficient. T1 at 3% is appropriate and conservatively within range.
- Game lines (spreads, totals): 4–5% minimum. T2 5% floor for game lines is correct.
- Binary/volatile props (ML_DOG, YRFI, GOALS): 6–8%. T3 6% floor + 8% hardcoded overrides are well-supported.
- Combo stats (PRA, PR, PA): 5% appropriate. T2 correct.

**Verdict: Keep 3%/5%/6% thresholds.** 8% overrides for ML_DOG and YRFI are the right safety valve.

### VAKE Multiplier Validation

| Parameter | Current | Recommended | Kelly Equivalent |
|-----------|---------|-------------|-----------------|
| T1 variance mult | 1.00 | **1.00** | ~1/14 full Kelly at 5% edge |
| T1 tier mult | 1.00 | **1.00** | |
| T2 variance mult | 0.85 | **0.85** | ~1/22 full Kelly |
| T2 tier mult | 0.90 | **0.90** | Combined 0.765× correct |
| T3 variance mult | 0.65 | **0.65** | ~1/37 full Kelly |
| T3 tier mult | 0.60 | **0.60** | Combined 0.39× correct |
| Base 3–5% edge | 0.50u | **0.50u** | ~1/13 full Kelly |
| Base 5–7% edge | 0.75u | **0.75u** | |
| Base 7–9% edge | 1.00u | **1.00u** | |
| Base 9%+ edge | 1.25u | **1.25u** | |

**Post-H3 gate upgrade path:** After Platt calibration confirmed (300+ over_p_raw rows, positive 12-week CLV trend ≥ +0.02 avg), scale all bases by 1.15× (e.g., 0.50→0.57u, 0.75→0.86u). Keep all multipliers unchanged.

### SPORT_UNIT_CAP Validation

| Sport | Current | Recommended | Basis |
|-------|---------|-------------|-------|
| NBA | 8u | 8u | Safety ceiling; typical picks 0.50–1.25u |
| WNBA | 4u | 4u | Lower liquidity; less calibration data |
| NHL | 5u | 5u | SOG stat cap provides secondary protection |
| NFL | 8u | **5u** | Weekly format; lower prop limits at books |
| MLB | 8u | 8u | Keep pending CLV investigation resolution |

### KILLSHOT Validation

- wp ≥ 0.65 gate: correct. At 0.65 WR, -115 odds: edge = 11.5%. Genuinely strong pick.
- Odds gate [-200, +110]: binding constraint for chalk picks; works correctly with 0.65 WR gate.
- 3u default / 4u bump: ~1/8 quarter Kelly at bump level — appropriately conservative for brand-risk management.
- 2/week cap: correct. 6–8u weekly KILLSHOT exposure = highly controlled.
- **3PM removal from KILLSHOT_STAT_ALLOW: required.** Dead code (T3 stat can never pass `tier=T1 strict` gate).

---

## CONSOLIDATED CHANGE LIST

### Tier Changes Required (by priority)

| Market | Change | Current | New Tier | New Min Edge | Priority |
|--------|--------|---------|----------|--------------|----------|
| NHL AST | Demotion | T1 | **T3** | 6% | **HIGH** — structural error, affects all NHL runs |
| 3PM from KILLSHOT_STAT_ALLOW | Removal | IN | **OUT** | — | **HIGH** — dead code, brand risk |
| MLB Runline SPREAD | Demotion | T2 | **T3** | 6% | HIGH |
| NHL Puck Line SPREAD | Demotion | T2 | **T3** | 6% | HIGH |
| MLB F5_TOTAL | Promotion | T2 | **T1B** | 3% | MEDIUM |
| MLB TEAM_TOTAL | Promotion | T2 | **T1B** | 3% | MEDIUM |
| NBA TEAM_TOTAL | Promotion | T2 | **T1B** | 3% | MEDIUM |
| NFL RECEPTIONS | Correction | planned T1 | **T2** | 5% | NFL-specific (pre-launch) |
| NFL RUSH_YARDS | Demotion | planned T2 | **T3** | 6% | NFL-specific |
| NFL RUSH_TDS/REC_TDS/INT | Exclusion | planned T3 | **EXCLUDE** | — | NFL-specific |

### Override Changes Required

| Market | Change | Old | New |
|--------|--------|-----|-----|
| NHL ML_DOG | Sport-specific | 8% global | **6%** |
| NBA ML_DOG | Sport-specific | 8% global | **7%** |
| MLB ML_DOG | Keep | 8% | 8% unchanged |
| NFL game lines | NFL-specific floor | 5% | **6%** (SPREAD, TOTAL, ML_FAV, TEAM_TOTAL) |
| NFL SPORT_UNIT_CAP | Reduce | 8u | **5u** |

### No Change Required

| Market | Current | Verdict |
|--------|---------|---------|
| NBA PTS/AST/REB/3PM | As above | Confirmed correct |
| NBA combos PRA/PR/PA/RA | T2/5% | Confirmed |
| WNBA all | Inherit NBA | Confirmed (+ WNBA_EDGE_FLOOR=0.035) |
| NHL SOG | T1/3% | Confirmed |
| NHL GOALS | T3/6% | Confirmed for planned implementation |
| MLB K/OUTS/HA/HITS/TB/HRR | As above | All confirmed |
| MLB NRFI | T3/6% | Confirmed |
| MLB YRFI | T3/8% | Confirmed |
| MLB ML_DOG | T3/8% | Confirmed |
| MLB ML_FAV | T2/5% | Confirmed |
| MLB TOTAL | T2/5% | Confirmed |
| MLB F5_SPREAD/F5_ML | T2/5% | Confirmed |
| NBA TOTAL/SPREAD/ML_FAV | T2/5% | Confirmed |
| NHL TOTAL/ML_FAV | T2/5% | Confirmed |
| NHL TEAM_TOTAL | T2/5% | Keep; monitor CLV |
| VAKE multipliers | All current | Confirmed correct |
| Daily cap 12u | Current | Confirmed |
| KILLSHOT gates | 0.65/2wk/3u4u | Confirmed |
| NFL PASS_YARDS/REC_YARDS/PASS_TDS | Planned tiers | Confirmed |
| NFL game lines SPREAD/TOTAL/ML_FAV/ML_DOG | Planned tiers | Confirmed (with 6% override) |

---

## OPEN DATA GATES

1. **H3 (Platt refit)**: ~300 post-v4 `over_p_raw` rows needed. Currently ~13 (as of 2026-05-09). Once cleared: scale VAKE bases 15% upward.
2. **NHL AST CLV validation**: Implement T1→T3 change, then validate against CLV data after 30+ NHL picks.
3. **NFL calibration**: After first full season (~17 weeks, 50+ live picks), review RUSH_YARDS (likely confirms T3) and RECEPTIONS (may confirm T2; could revisit T1 if model accuracy high).
4. **WNBA Platt refit**: Target ~300 WNBA over_p_raw rows (~mid-June 2026 at 10–15 WNBA picks/day).
5. **MLB CLV investigation**: Do not raise MLB SPORT_UNIT_CAP until root causes of -213u shadow log confirmed fixed and positive CLV history established.

---

*End of TIER_FINDINGS.md — All 6 research sections (T1–T6) consolidated.*
*Source files: TIER_FINDINGS_T1.md through T6.md — all generated 2026-05-21.*
