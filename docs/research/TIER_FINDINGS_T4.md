# Tier Research Findings — T4: MLB Game Lines + NBA/WNBA/NHL Game Lines

**Date:** 2026-05-21
**Sections covered:** 8 (MLB Game Lines) + 9 (NBA/WNBA/NHL Game Lines)
**Sources:** ActionNetwork, OddsIndex, BetterEdge, Covers, OddsShark, Gamblingsite.com, MLBDataWarehouse, ResearchGate (Woodland & Woodland 2010 NHL study), Traugutt dissertation, ECU weak-form efficiency paper, SABR, Wizard of Odds, ProbWin

---

## SECTION 8: MLB GAME LINES

---

### 8A. NRFI / YRFI — Currently Both T3 (YRFI has 8% override)

#### Empirical Probability

- League-wide P(YRFI) ≈ 29–30% of games have a first-inning run scored by at least one team (TeamRankings 2025-26 data: ~29.85% of team half-innings score; per-game YRFI rate approximates ~55–60% once both teams' half-innings are considered).
- **Clarification on the binary:** NRFI/YRFI is strictly binary — either 0 runs are scored in the first inning (NRFI) or ≥1 run is scored (YRFI). No partial outcomes. This binary structure is the defining variance characteristic.
- Typical NRFI probability per game: **~55–65%** depending on pitching matchup. Strong ace vs. ace matchup: NRFI ~65–70%. Average matchup: NRFI ~55–60%. Weak pitching: NRFI ~45–50%.
- Books price NRFI at approximately **-130 to -180** for most games; break-even implied probability at -150 = 60%.

#### CV of Binary Outcome

- For a binary Bernoulli(p) outcome, CV = sqrt(p(1-p)) / p = sqrt((1-p)/p).
- At p(NRFI) = 0.60: CV = sqrt(0.40/0.60) = **0.816**
- At p(NRFI) = 0.65: CV = sqrt(0.35/0.65) = **0.733**
- At p(YRFI) = 0.40: CV = sqrt(0.60/0.40) = **1.225**
- At p(YRFI) = 0.35: CV = sqrt(0.65/0.35) = **1.363**
- **NRFI CV (~0.73–0.82) is substantially lower than YRFI CV (~1.22–1.36).** The asymmetry is large and material for tier assignment.

#### Market Efficiency

- **Hold on NRFI/YRFI markets is high: 6–10%**, materially above standard game lines (4–5%). Source: MLBDataWarehouse peer-to-peer analysis, BetterEdge 2025.
- The high hold is structural — books price these as soft recreational markets, not sharp markets. Sportsbooks actively promote NRFI bets (often featuring them in morning marketing pushes), indicating they profit reliably from the public's interest.
- Pricing methodology: P(NRFI) ≈ (1 − p_home_scores) × (1 − p_away_scores) where each team's first-inning scoring probability derives from pitcher ERA, team YRFI rate, park factor, and weather. Books apply this formula but with added margin; the formula itself is publicly known and does not generate sustained edge on its own.
- **Is the NRFI/YRFI market "soft"?** Mixed. The formula is well-known, which limits mechanical edges. However, mispricing exists when:
  - Opening day-of starter changes haven't propagated to all books
  - Book has used trailing NRFI rate without adjusting for specific ace opponent
  - Sharp money on related markets (full-game total) hasn't reflected in F1 pricing
- **Public betting bias:** Books push NRFI to recreational users because it settles after one inning. Public generally bets NRFI (lays the juice on the "safe" side). This creates mild structural value on YRFI — not massive, but real.

#### YRFI 8% Override — Is It Justified?

- **Answer: Yes, the 8% override is justified for YRFI specifically.**
- CV for YRFI (~1.22–1.36) is among the highest of any market in the model. At +EV=0 with YRFI at +120 (implied 45.5%), the model needs substantial edge to confirm true probability is materially above 45.5%.
- The standard T3 floor of 6% provides insufficient cushion given YRFI CV > 1.20. A model overestimating P(YRFI) by even 3% produces large negative EV at these variance levels.
- **NRFI 6% floor (no override):** NRFI CV ~0.73–0.82 is meaningfully lower than YRFI. At standard book prices (-140 to -170 for NRFI), the edge threshold of 6% is appropriate and could potentially support a lower threshold for elite pitching matchups. However, 6% is a reasonable floor given the hold is 6–10%.
- **Recommended for NRFI:** T3, min_edge 6%. No change needed.
- **Recommended for YRFI:** T3, min_edge 8% override maintained. Justified by CV asymmetry.

#### Recommendation

| Market | Current Tier | Current Min Edge | Recommended Tier | Recommended Min Edge | Rationale |
|--------|-------------|-----------------|-----------------|---------------------|-----------|
| NRFI | T3 | 6% | **T3** | **6%** | High hold (6-10%), binary CV ~0.75, no systematic edge from formula alone |
| YRFI | T3 | 8% (override) | **T3** | **8% (maintain)** | CV ~1.25+, highest-variance standard market, public-biased toward NRFI |

**Could NRFI move to T2?** Only if hold consistently dropped to 4-5% and model demonstrated repeatable calibrated edge. Current 6-10% hold argues against T2. T3 is correct.

---

### 8B. MLB Runline (Fixed ±1.5) — Currently T2 Under SPREAD

#### Structural Profile

- The MLB runline is fixed at ±1.5 runs regardless of matchup strength — this is the critical structural difference from NBA variable spreads.
- Approximately **30% of MLB games are decided by exactly 1 run**, meaning the runline outcome flips relative to the moneyline in ~30% of all games.
- MLB -1.5 favorite cover rate: **approximately 38–42% of the time** across a full season (home favorites win by 2+ runs ~39% per historical data). Road favorites cover -1.5 at marginally higher rates.
- Moneyline favorites win outright ~58–62% of games, but only cover -1.5 in ~39–42% — a 16–23 percentage point gap caused by the one-run game frequency.

#### Efficiency Profile vs. NBA Variable Spread

- **The fixed runline is structurally more binary-like than NBA spread.** At -1.5, the market is effectively pricing: "Will the favorite win by 2+ runs?" This has a lower win probability (~40%) than the moneyline (~60%) with correspondingly high CV.
- Binary CV for a -1.5 bet where cover_prob ≈ 0.40: CV = sqrt(0.60/0.40) = **1.22** — very high, comparable to YRFI.
- NBA variable spread is priced with spread adjusted to reflect ~50% cover probability per game, making NBA spread CV far lower (~sqrt(0.50/0.50) = **1.00** near 50% cover rate, effectively a near-coin flip with known probability).
- **Is fixed runline more like T3?** Yes in terms of CV profile. However, the model prices it correctly when edge is computed against the book's -1.5 implied probability (not the moneyline probability). If model correctly estimates P(cover -1.5), the CV is still ~1.22 but the edge estimate is calibrated to that probability.
- **Market efficiency:** MLB runline volume is lower than moneyline but still substantial. Books derive runline from moneyline using standard conversion formulas; the market is efficient relative to the moneyline. No structural mispricing exists at the level that props have.

#### Recommendation

| Market | Current Tier | Recommended Tier | Min Edge | Rationale |
|--------|-------------|-----------------|----------|-----------|
| MLB SPREAD (Runline ±1.5) | T2 | **T2/T3 borderline — recommend T3** | **6%** | CV ~1.22 (binary-adjacent), fixed line unlike variable NBA spread, 30% one-run game frequency means line doesn't flex to balance coverage. Strong case for T3 on CV grounds. |

**Implementation note:** If the model separates MLB SPREAD as a distinct market from NBA SPREAD (which is variable), raising MLB SPREAD to T3 with 6% min_edge is warranted. If they share a tier, T2 with 5% min_edge is the pragmatic current default but understates true variance. **Recommendation: split MLB SPREAD to T3 or apply a 6% min_edge override within T2.**

---

### 8C. MLB F5 Markets (F5_TOTAL, F5_SPREAD, F5_ML) — Currently T2

#### F5 vs Full Game Structure

- F5 markets isolate starting pitcher performance for exactly 5 innings (or until the starter exits, with half-inning rules by book). This eliminates bullpen variance, pinch-hitter variance, late-game managerial decisions, and reliever sequencing — all significant sources of full-game uncertainty.
- F5_TOTAL sigma is structurally lower than full-game total sigma. Current model uses F5_SIGMA total=2.6 vs full-game MLB sigma=4.0. The 2.6 vs 4.0 ratio (35% lower) is directionally correct; academic baseball statistics confirm runs-per-inning variance compounds into a ~55–65% full-game sigma across 9 innings.
- F5_SPREAD sigma=2.75, F5_TEAM=2.0 are plausible given pitcher quality drives first-5 run differential more cleanly than full game.

#### Market Efficiency

- **F5 markets receive less betting volume than full-game markets.** Lower liquidity → less sharp money → more potential mispricing persists through game time.
- Books set F5 lines after full-game lines; F5 is derivative. When sharp action hits full-game total, F5 total often doesn't update immediately — creating brief windows of exploitable discrepancy.
- F5 totals see significant sharp action specifically because starting pitcher quality signals translate more cleanly to 5-inning totals than to 9-inning totals. Sharps who have pitcher quality edges prefer F5 as the cleaner expression.
- **Is F5 more or less efficient than full game?** Mixed by sub-market:
  - **F5_TOTAL:** Less efficient than full-game total because books allocate fewer pricing resources to F5 and volume is lower. Sharps can find more edge here specifically on pitcher quality signals.
  - **F5_ML:** Less efficient than full-game ML; lower volume, derived from starter quality only. However, result is binary (winner after 5 innings), so CV structure is high.
  - **F5_SPREAD:** Moderate efficiency; tighter to F5 total in pricing but some residual softness on pitcher-specific matchups.

#### Recommendation

| Market | Current Tier | Recommended Tier | Min Edge | Rationale |
|--------|-------------|-----------------|----------|-----------|
| F5_TOTAL | T2 | **T1B** | **3%** | Lower variance than full-game (σ=2.6 vs 4.0), softer market (less volume/sharp penetration), pitcher quality signals translate cleanly. CV lower than full-game total. Directional restriction: F5 unders preferred when starter is elite (same asymmetry as T1B stats generally). |
| F5_SPREAD | T2 | **T2** | **5%** | Moderate efficiency, slightly higher CV than F5_TOTAL due to run differential binary-adjacent structure. Keep T2. |
| F5_ML | T2 | **T2/T3** | **5–6%** | Binary outcome (who leads after 5), high CV when odds diverge from 50/50. If book price implies >55% probability, CV drops — use 5% floor. If odds imply <45%, use 6%. Pragmatically keep T2 with 5% floor and monitor. |

**Summary judgment on F5:** F5_TOTAL has the best case for promotion, not demotion — lower sigma, softer market, cleaner pitcher signals. F5_ML is the one most worth monitoring for T3 reclassification if model produces poorly calibrated win probabilities there.

---

### 8D. MLB ML_DOG — Currently T3 with 8% Override

#### Variance Profile

- MLB moneyline underdogs span a wide odds range: approximately +115 to +400 depending on matchup.
- CV of a binary bet at typical dog odds:
  - +150 (implied 40%): CV = sqrt(0.60/0.40) = **1.22**
  - +200 (implied 33.3%): CV = sqrt(0.667/0.333) = **1.41**
  - +300 (implied 25%): CV = sqrt(0.75/0.25) = **1.73**
  - +400 (implied 20%): CV = sqrt(0.80/0.20) = **2.00**
- Large-dog MLB ML has extremely high CV (>1.5), among the highest in the model. Lottery-ticket framing is accurate.

#### Is 8% Min Edge Correct?

- At +200 (implied 33.3%), the model needs to project true win probability ≥ 41.3% to generate 8% edge. This is a substantial lift — projecting a meaningful model advantage over the book.
- Baseball's high variance (even best teams lose 38% of games, worst teams win 38%) means dog wins are plentiful but individual game-level prediction is hard. The 8% threshold provides appropriate filter against noise.
- **Historical MLB underdog long-run ROI:** Data shows underdogs +100 to +200 can produce ~+1% ROI over large samples with disciplined edge filters. At 8% required edge, the model is targeting the top-of-funnel, highest-confidence subset. This is correct.
- **Is 8% too high?** For small dogs (+115 to +135), 8% may be too conservative — their CV is closer to T3 than extreme dog. However, unifying at 8% to avoid granular if-then logic is operationally sound.
- **Is 8% too low?** For extreme dogs (+300+), variance is so high that even 8% edge may not be reliable — projection error alone could absorb 5–10% of apparent edge. Consider a separate 10% override for dogs above +250, or simply exclude dogs above +250 from the model.

#### Recommendation

| Market | Current Tier | Recommended Tier | Min Edge | Rationale |
|--------|-------------|-----------------|----------|-----------|
| MLB ML_DOG | T3 | **T3** | **8% (maintain)** | Binary with CV 1.2–2.0+, lottery-ticket variance profile confirmed. 8% override correct for typical range (+140 to +250). Consider excluding +300+ dogs or raising to 10% for that range. |

---

### 8E. MLB TOTAL (Full Game) — Currently T2

#### Variance Profile

- Standard MLB full-game run total: mean ~8.5–9.0 runs/game, σ ≈ 3.8–4.0 runs. Model uses σ=4.0, which is well-calibrated to published estimates.
- CV = 4.0 / 8.75 = **0.457** — moderate, consistent with T2 placement.
- Distribution shape: approximately Normal for game totals (CLT effect of summing both teams across 9 innings), mild positive skew from blowout games.

#### Market Efficiency

- MLB totals are heavily influenced by starting pitcher quality — the single most predictive variable. Books price pitcher quality efficiently; sharp bettors with strong pitcher models have exploited this historically, but the signal is increasingly priced in.
- **MLB totals market efficiency: Moderate.** Not as efficient as NBA totals (less volume, more lineup complexity) but not as soft as team totals or F5 markets.
- Hold on MLB full-game totals: approximately **4.5–5.5%** (slightly higher than NBA game lines at 4–4.5%).

#### Recommendation

| Market | Current Tier | Recommended Tier | Min Edge | Rationale |
|--------|-------------|-----------------|----------|-----------|
| MLB TOTAL | T2 | **T2** | **5%** | CV 0.46, moderate efficiency, higher hold than NBA. T2 is correct. Less efficient than NBA totals → does not qualify for T1. |

---

### 8F. MLB ML_FAV — Currently T2

#### Profile

- MLB moneyline favorites win 58–62% of games. CV for a ML_FAV bet at -150 (implied 60%): CV = sqrt(0.40/0.60) = **0.816**.
- Public over-bets MLB favorites — well-documented. The "fade the public" strategy specifically targets MLB favorite overbetting. Books shade favorite lines by ~3–5 cents of juice to balance handle, creating structural mild undervalue on favorites (the opposite direction from public expectation — public over-bets favorites, books accommodate by shading further, reducing EV of following the public).
- **Correct framing:** ML_FAV bets at -120 to -180 carry moderate CV (~0.75–1.00) and are priced efficiently. The public-bias shading means books are slightly overcorrecting favorite prices, creating marginal structural value on dogs — not on favorites.
- **Market efficiency:** MLB ML_FAV is efficiently priced. No systematic positive EV exists without genuine model edge.

#### Recommendation

| Market | Current Tier | Recommended Tier | Min Edge | Rationale |
|--------|-------------|-----------------|----------|-----------|
| MLB ML_FAV | T2 | **T2** | **5%** | CV 0.75–1.00, moderate efficiency. Public over-bets favorites → books shade lines → model must clear a real 5% edge vs. the shaded line. T2 correct. |

---

### 8G. MLB TEAM_TOTAL — Currently T2

#### Profile

- Team totals are a sub-market of the full-game total — they receive less betting volume, fewer sharp bettors target them systematically, and books price them derivative of full-game total and starting pitcher props.
- **Market efficiency: Lower than full-game total.** Books dedicate less pricing infrastructure to team totals; lines can lag full-game adjustments. This creates occasional exploitable windows.
- CV of team scoring: Team score σ ≈ 2.3–2.5 runs (vs. full-game σ = 4.0). Mean team score ≈ 4.3–4.5 runs. CV = 2.4/4.4 = **0.545**.
- The lower volume and derivative pricing structure makes TEAM_TOTAL potentially the most exploitable MLB game line market.

#### Recommendation

| Market | Current Tier | Recommended Tier | Min Edge | Rationale |
|--------|-------------|-----------------|----------|-----------|
| MLB TEAM_TOTAL | T2 | **T1B** | **3%** | Softer market than full-game total, derivative pricing creates lag opportunities, CV ~0.55 is lower than full-game total. Pattern mirrors NBA TEAM_TOTAL (same recommendation below). Apply directional caution: unders may outperform overs due to pitcher-quality signal dominance. |

---

## SECTION 9: NBA / WNBA / NHL GAME LINES

---

### 9A. TOTAL (Game Total) — Currently T2 for All Sports

#### NBA TOTAL

**Variance Profile:**
- NBA full-game scoring total: mean ~220–230 points/game (2024-25), σ ≈ 11–13 points. Model uses σ=12.0 — well-calibrated.
- CV = 12.0 / 225 = **0.053** — the lowest CV of any market in the model. Game totals are inherently stable.
- Distribution: approximately Normal (CLT effect, 48 minutes of ~4.5 pts/min with known variance).

**Market Efficiency:**
- **NBA totals are among the most efficiently priced markets in sports betting.** Volume is massive, sharp bettors concentrate on totals, Pinnacle's closing line on NBA totals is the industry's most reliable reference.
- Hold: approximately **4–4.5%** at standard retail books (-110/-110), among the lowest holds in the model.
- Public overbets NBA overs (fans prefer high-scoring games). Books respond by shading totals upward by approximately 0.5–1 point on average. This creates a documented mild under bias in NBA totals (paying more for the under than true probability warrants). Sharp bettors systematically exploit this, making the bias partially self-correcting.
- **Academic evidence (Ohio University thesis, CMU capstone research, Sport Journal):** NBA point spread markets are largely efficient but retain seasonal early-season biases in totals. No sustained mechanical edge survives over multiple seasons in NBA totals for individual bettors.

**Should NBA TOTAL move to T1?**
- The efficiency argument supports T1 — if edges appear here, they are likely real because the market is so efficiently priced that false edges are rarely generated.
- The low CV (0.053) also supports T1 — the outcome is as stable as any sports market.
- **Counter-argument:** The primary uncertainty is projection uncertainty (epistemic variance), not aleatory outcome variance. The model's team-level projection may be systematically off. Minimum edge of 3% provides insufficient buffer if the model's NBA total projection has 3–4% inherent error.
- **Verdict: NBA TOTAL → T2 maintained with consideration for T1B.** The market is efficient enough that 5% edge, when it appears, is likely genuine. But the volume and public attention means the model rarely generates 5%+ edge here — when it does, it's worth betting at full T2 sizing. Promoting to T1 (3% min) risks false positives.

**WNBA TOTAL:**
- σ ≈ 8–10 points (model uses 10.0), mean ~150–165 points/game. CV = 10/157 = **0.064** — similar to NBA.
- Market efficiency: Much lower than NBA. WNBA totals lines are set with less precision, fewer sharp bettors pressure them, book limits are lower. This is a genuine inefficiency opportunity.
- **WNBA TOTAL → T2 maintained (or T1B candidate).** Lower efficiency creates genuine edge opportunities, but lower limits reduce sizing appropriately. T2 is pragmatically correct.

**NHL TOTAL:**
- NHL goals totals: mean ~5.5–6.0 goals/game, σ ≈ 1.5–2.0 goals. Model uses σ=1.2 — potentially slightly underestimated. Academic research (Woodland & Woodland 2010, Traugutt dissertation): NHL totals market has historically shown an under bias at high total lines (5.5+). The market has become more efficient since 2010 but the under bias persists weakly.
- CV = 1.7 / 5.7 = **0.298** — moderate, higher than NBA.
- **NHL TOTAL → T2 maintained.** Higher CV than NBA (0.298 vs 0.053), market slightly less efficient. T2 with 5% min is appropriate. The under bias (when betting totals at 5.5+) is worth tracking as a model calibration note.

#### Recommendation Table: TOTAL

| Sport | Current Tier | Recommended Tier | Min Edge | Rationale |
|-------|-------------|-----------------|----------|-----------|
| NBA TOTAL | T2 | **T2** | **5%** | Highly efficient, low CV (0.053). 5% edge here is very likely real but rare. 3% would generate false positives. |
| WNBA TOTAL | T2 | **T2** | **5%** | Less efficient than NBA, similar CV. T2 appropriate. Monitor for T1B if line quality improves. |
| NHL TOTAL | T2 | **T2** | **5%** | Higher CV (0.298), moderate efficiency. Confirmed under bias at high lines (5.5+) worth calibration note. |
| MLB TOTAL | T2 | **T2** | **5%** | (Covered in 8E) |

---

### 9B. SPREAD — Currently T2

#### NBA SPREAD

**Efficiency Profile:**
- NBA spreads and NFL spreads are the **two most efficient markets in sports betting** — massive volume, deep Pinnacle action, closing lines that are the industry's gold standard for true probability estimation.
- Hold: **4–4.5%** at retail books. Sharp books (Pinnacle): ~1.9–2.5%.
- NBA spread CV at typical -5 spread: cover_prob ≈ 50% by construction (books size the spread to balance action). CV at 50% = sqrt(0.50/0.50) = **1.00** — but this is misleading. The spread is designed to be a 50/50 bet; the relevant uncertainty is the model's projection error vs. the closing line.
- Published academic research (Miami University thesis, CMU stats capstone): NBA point spread markets are weak-form efficient. No mechanical rule has produced sustained profits over large samples.
- **Should NBA SPREAD move to T1?** Arguments for T1:
  - Most efficiently priced game-line market
  - If the model generates 5% edge vs. the closing spread line, it's likely a genuine edge (the market almost never leaves 5% on the table)
  - Low aleatory variance (spread is 50/50 by construction)
  - Arguments against T1: epistemic uncertainty is high — the model's spread projection may have 3–4% systematic error, so 3% min edge is too low
- **Verdict: NBA SPREAD → T2 maintained.** Same logic as NBA TOTAL. The efficiency means edges that appear at 5% are likely real, but 3% would generate false signals given model projection uncertainty.

#### NHL Puck Line (Fixed ±1.5)

- NHL puck line is fixed at ±1.5 goals (same structure as MLB runline).
- **NHL favorites cover -1.5 approximately 30–35% of the time** — much less than 50%, making this binary-adjacent.
- The puck line is priced as a derivative of the moneyline. A -250 moneyline favorite typically prices at approximately +110 to +125 on the puck line.
- CV for puck line bet where cover_prob ≈ 0.32: CV = sqrt(0.68/0.32) = **1.46** — very high.
- **NHL puck line (SPREAD) is structurally more like T3 than T2** on CV grounds alone. However, books price it correctly as a derivative of moneyline (which they price efficiently), so there's no additional market inefficiency to exploit.

#### Recommendation Table: SPREAD

| Sport | Current Tier | Recommended Tier | Min Edge | Rationale |
|-------|-------------|-----------------|----------|-----------|
| NBA SPREAD | T2 | **T2** | **5%** | Sharpest market in the model. 5% min edge captures only real edges. Not T1 (epistemic projection uncertainty). |
| NHL SPREAD (Puck Line) | T2 | **T2/T3 borderline — recommend T3** | **6%** | Fixed ±1.5, cover rate ~32%, CV ~1.46. Same structural issue as MLB runline. Consider T3 or 6% override. |
| MLB SPREAD (Runline) | T2 | **T3** | **6%** | (Covered in 8B) |

---

### 9C. ML_FAV — Currently T2

#### NBA ML_FAV

- NBA moneyline favorites win at very high rates (competitive games cluster 55–70% favorite win probability for most lines).
- CV for ML_FAV at -200 (implied 66.7%): CV = sqrt(0.333/0.667) = **0.707**
- CV for ML_FAV at -150 (implied 60%): CV = sqrt(0.40/0.60) = **0.816**
- Public over-bets NBA favorites more than any other sport. Books shade heavily toward favorites; some published research suggests NBA favorites are systematically slightly overpriced (public-inflated) making them mild structural under-value as bets. Sharp money often fades large NBA favorites.
- **NBA ML_FAV → T2 maintained.** CV 0.71–0.82 is consistent with T2.

#### NHL ML_FAV

- NHL favorites at -130 to -200 are common. CV similar to NBA.
- NHL is historically one of the more efficient markets for moneylines per ECU weak-form efficiency research.
- **NHL ML_FAV → T2 maintained.**

#### MLB ML_FAV

- Covered in 8F. T2 maintained.

#### Which Sport Has Most ML_FAV Distortion?

- **NBA** has the clearest public over-betting of favorites (star player bias, media-driven narrative teams). Books shade NBA favorite lines more aggressively than MLB or NHL.
- **MLB** public also over-bets favorites but at lower volume; shading is slightly less.
- **NHL** has the least clear ML_FAV public distortion — parity-driven sport with less casual bettor engagement.
- **Implication:** NBA ML_FAV edges may be slightly harder to find (books have already compensated for public bias by shading); NHL ML_FAV may be the softest of the three on a per-edge basis.

#### Recommendation Table: ML_FAV

| Sport | Current Tier | Recommended Tier | Min Edge | Rationale |
|-------|-------------|-----------------|----------|-----------|
| NBA ML_FAV | T2 | **T2** | **5%** | CV 0.71–0.82, high volume, public over-bets. Books compensate. 5% edge required. |
| NHL ML_FAV | T2 | **T2** | **5%** | Similar CV, slightly lower public-bias distortion. T2 correct. |
| MLB ML_FAV | T2 | **T2** | **5%** | As in 8F. |

---

### 9D. ML_DOG — Currently T3 with 8% Override

#### CV at Typical Dog Odds by Sport

- **NBA ML_DOG:** NBA dog odds typically range +120 to +350, but true blowout mismatches are rarer because parity in NBA is lower (bottom-6 teams are genuinely bad). Common range: +130 to +250.
  - At +150 (implied 40%): CV = **1.22**
  - At +200 (implied 33%): CV = **1.41**
- **NHL ML_DOG:** NHL parity is high. Dog odds: +110 to +200 most commonly. Occasional dogs at +250+.
  - At +140 (implied 41.7%): CV = **1.19**
  - At +170 (implied 37%): CV = **1.29**
- **MLB ML_DOG:** Widest odds range, +115 to +400+. Genuine blowout specialists can be enormous favorites.
  - At +200 (implied 33%): CV = **1.41**
  - At +300 (implied 25%): CV = **1.73**

#### Should NHL ML_DOG Be T2 Rather Than T3?

- NHL dogs at +140 to +180 have CV 1.19–1.29 — lower than MLB dogs at the same odds range, but the structural reason is that NHL has higher parity (underdogs win ~40–43% of games historically).
- The critical question is: does higher parity mean the model's edge estimate is more reliable for NHL dogs? **Yes.** In NHL, +140 dogs genuinely win ~42% of games vs. book's implied 41.7% — the pricing is close to fair, meaning model edges require genuine information.
- **However:** The CV profile alone puts NHL ML_DOG at 1.19–1.29, squarely in T3 range (CV > 1.0). T3 with 8% override is defensible. A case exists for NHL ML_DOG at 6% (standard T3, no override) because the hockey parity means true dog win rates are closer to 40–43%, not the 25–35% of MLB big dogs.
- **Recommended: Sport-specific ML_DOG override.**

#### Sport-Specific ML_DOG Min Edge

- **NHL ML_DOG:** 6% min edge (standard T3) — parity means dog odds are set more accurately; the 8% override is excessive for +110 to +180 range. Reserve 8% for NHL dogs above +250.
- **NBA ML_DOG:** 7% min edge — intermediate. NBA dogs have CV 1.22–1.41, higher variance than NHL dogs but model has richer NBA data.
- **MLB ML_DOG:** 8% override maintained — highest variance sport, largest odds spread, projection quality per-game is lowest of the three sports.

#### Recommendation Table: ML_DOG

| Sport | Current Tier | Recommended Tier | Recommended Min Edge | Rationale |
|-------|-------------|-----------------|---------------------|-----------|
| NBA ML_DOG | T3 | **T3** | **7%** | CV 1.22–1.41, binary high-variance. 8% is too conservative for +130 range; 6% is too loose for +250 range. 7% is appropriate center. |
| NHL ML_DOG | T3 | **T3** | **6%** | Highest hockey parity, dogs win ~40-43%. CV 1.19–1.29. Standard T3 at 6% is sufficient; 8% leaves real value on table. Reserve 8% for +250+ NHL dogs if model covers them. |
| MLB ML_DOG | T3 | **T3** | **8% (maintain)** | Widest odds range, lowest per-game projection quality, highest CV at typical dog ranges. 8% is correct. |

---

### 9E. TEAM_TOTAL — Currently T2

#### NBA TEAM_TOTAL

- **Team totals are a significantly softer market than game totals.** Team-specific scoring lines receive far less sharp attention; books set lines derivative of the full-game total and team-specific splits without the full arsenal of defensive-adjustment modeling.
- Volume: Team totals generate roughly 20–30% of the handle of full-game totals in NBA.
- Model uses NBA team σ=9.0 vs. total σ=12.0. Mean team score ~112 points. CV = 9.0/112 = **0.080** — low, lower than full-game total on a relative basis.
- The combination of lower CV and lower market efficiency (softer) makes TEAM_TOTAL potentially the best game-line market for the model to find edge — similar to F5_TOTAL logic.

#### Recommendation Table: TEAM_TOTAL

| Sport | Current Tier | Recommended Tier | Min Edge | Rationale |
|-------|-------------|-----------------|----------|-----------|
| NBA TEAM_TOTAL | T2 | **T1B** | **3%** | Lower volume than game total, derivative pricing lags, CV ~0.08 (lower than game total). Apply directional caution (unders when team is defending at home or opponent is slow-paced). |
| NHL TEAM_TOTAL | T2 | **T2** | **5%** | Lower volume but also lower σ signal quality. Keep T2 until CLV data confirms persistent edge. |
| MLB TEAM_TOTAL | T2 | **T1B** | **3%** | As in 8G above. Softest game-line market in MLB. |

---

## CONSOLIDATED TIER RECOMMENDATION TABLE (Sections 8 + 9)

```
SPORT | STAT         | CUR  | REC       | CV          | EFFICIENCY   | MIN_EDGE | KEY REASON
------|--------------|------|-----------|-------------|--------------|----------|------------------
MLB   | NRFI         | T3   | T3        | 0.73-0.82   | Low (6-10% hold) | 6%  | Binary, high hold, formula-based pricing well-known
MLB   | YRFI         | T3   | T3        | 1.22-1.36   | Low (6-10% hold) | 8% | CV asymmetry vs NRFI justifies higher override
MLB   | SPREAD(RL)   | T2   | T3        | ~1.22       | Med           | 6%  | Fixed ±1.5 binary-adjacent, 30% one-run game rate
MLB   | F5_TOTAL     | T2   | T1B       | ~0.40-0.45  | Low-Med       | 3%  | Lower σ than full game, softer market, pitcher signals clean
MLB   | F5_SPREAD    | T2   | T2        | ~0.50-0.55  | Med           | 5%  | Slightly higher CV than F5_TOTAL, keep T2
MLB   | F5_ML        | T2   | T2        | ~1.0-1.2    | Med           | 5%  | Binary outcome but cleaner than full-game ML; monitor
MLB   | ML_DOG       | T3   | T3        | 1.22-2.00+  | Med           | 8%  | Widest variance range, lottery-ticket confirmed
MLB   | ML_FAV       | T2   | T2        | 0.75-1.00   | Med           | 5%  | Public overbets, books shade; 5% edge must clear shade
MLB   | TOTAL        | T2   | T2        | ~0.46       | Med           | 5%  | Pitcher quality priced in; moderate efficiency
MLB   | TEAM_TOTAL   | T2   | T1B       | ~0.55       | Low           | 3%  | Softest MLB game line, derivative pricing, lower volume
NBA   | TOTAL        | T2   | T2        | 0.053       | Very High     | 5%  | Most efficient; 5% real when it appears; 3% risks false positives
NBA   | SPREAD       | T2   | T2        | ~1.00*      | Very High     | 5%  | Sharpest market; same logic as TOTAL
NBA   | ML_FAV       | T2   | T2        | 0.71-0.82   | High          | 5%  | Public over-bets; books compensate; 5% clears shading
NBA   | ML_DOG       | T3   | T3        | 1.22-1.41   | High          | 7%  | Binary high-variance; 8% too conservative, 6% too loose
NBA   | TEAM_TOTAL   | T2   | T1B       | ~0.080      | Med-Low       | 3%  | Softest NBA game line, derivative pricing, lower volume
WNBA  | TOTAL        | T2   | T2        | ~0.064      | Low-Med       | 5%  | Less efficient than NBA but similar CV; T2 appropriate
WNBA  | SPREAD       | T2   | T2        | ~1.00*      | Low-Med       | 5%  | Variable spread; thinner market but same binary cover structure
WNBA  | ML_FAV       | T2   | T2        | 0.71-0.90   | Low-Med       | 5%  | Thinner market; book limits constrain sizing more than tier
WNBA  | ML_DOG       | T3   | T3        | 1.22+       | Low-Med       | 7%  | Same as NBA ML_DOG; WNBA parity similar to NBA
NHL   | TOTAL        | T2   | T2        | ~0.298      | Med-High      | 5%  | Historical under bias at 5.5+; monitor for calibration
NHL   | SPREAD(PL)   | T2   | T3        | ~1.46       | High          | 6%  | Fixed ±1.5, cover rate ~32%, binary-adjacent; same as MLB RL
NHL   | ML_FAV       | T2   | T2        | 0.71-0.82   | High          | 5%  | Efficient market, less public distortion than NBA
NHL   | ML_DOG       | T3   | T3        | 1.19-1.29   | High          | 6%  | Parity-driven; standard T3 sufficient; 8% too aggressive
NHL   | TEAM_TOTAL   | T2   | T2        | ~0.30       | Med           | 5%  | Smaller market, lower σ signal quality; keep T2, monitor CLV
```

*Spread CV presented as binary cover-probability CV; the market is priced to ~50% cover by construction.

---

## SUMMARY OF RECOMMENDED CHANGES FROM CURRENT SETTINGS

### Tier Changes (Promotions / Demotions)

| Market | Change | Direction | New Tier | New Min Edge |
|--------|--------|-----------|----------|--------------|
| MLB SPREAD (Runline ±1.5) | Demotion | T2 → T3 | T3 | 6% |
| NHL SPREAD (Puck Line ±1.5) | Demotion | T2 → T3 | T3 | 6% |
| MLB F5_TOTAL | Promotion | T2 → T1B | T1B | 3% |
| MLB TEAM_TOTAL | Promotion | T2 → T1B | T1B | 3% |
| NBA TEAM_TOTAL | Promotion | T2 → T1B | T1B | 3% |

### Override Changes

| Market | Change | Old Min Edge | New Min Edge |
|--------|--------|-------------|-------------|
| NHL ML_DOG | Reduce override | 8% (global) | 6% (sport-specific) |
| NBA ML_DOG | Add sport-specific | 8% (global) | 7% (sport-specific) |
| MLB ML_DOG | Keep | 8% | 8% (unchanged) |
| NRFI | Keep | 6% | 6% (unchanged) |
| YRFI | Keep | 8% | 8% (unchanged) |

### No Change Needed

| Market | Current | Verdict |
|--------|---------|---------|
| MLB NRFI | T3 / 6% | Confirmed correct |
| MLB YRFI | T3 / 8% | Confirmed correct |
| MLB ML_DOG | T3 / 8% | Confirmed correct |
| MLB ML_FAV | T2 / 5% | Confirmed correct |
| MLB TOTAL | T2 / 5% | Confirmed correct |
| MLB F5_SPREAD | T2 / 5% | Confirmed correct |
| MLB F5_ML | T2 / 5% | Confirmed correct (monitor) |
| NBA TOTAL | T2 / 5% | Confirmed correct |
| NBA SPREAD | T2 / 5% | Confirmed correct |
| NBA ML_FAV | T2 / 5% | Confirmed correct |
| WNBA all | T2-T3 current | Confirmed correct |
| NHL TOTAL | T2 / 5% | Confirmed correct (note under bias at 5.5+) |
| NHL ML_FAV | T2 / 5% | Confirmed correct |
| NHL TEAM_TOTAL | T2 / 5% | Keep, monitor CLV |

---

## KEY CALIBRATION NOTES

### 1. Fixed-Line Spread Markets Are Structurally Different

Both MLB runline (±1.5 runs) and NHL puck line (±1.5 goals) are binary-adjacent markets where the fixed line does not flex to achieve 50% cover probability. Cover rates of 32–42% create CV values of 1.22–1.46, firmly in T3 territory. These should not share a tier with NBA spread (variable, priced to ~50% cover). **Both should be T3 with 6% min edge.**

### 2. F5_TOTAL and TEAM_TOTAL Are the Most Undervalued Game-Line Markets

Both markets share a profile: lower absolute variance (smaller sigma than full-game), softer market pricing (derivative or lower-volume), and genuine edge opportunities when the model has good starter/team-specific inputs. Promoting both to T1B (3% min edge) allows the model to post picks that are genuinely +EV but currently filtered out by the 5% T2 threshold.

### 3. NHL Totals — Under Bias at High Lines

Published academic research (Woodland & Woodland) and practitioner analysis confirm an under bias in NHL totals at lines of 5.5+. When model projects UNDER on a 5.5 or 6.0 total, the true edge may be slightly larger than computed (books over-shade over due to public overbetting high-scoring games). This is a model calibration note, not a tier change.

### 4. ML_DOG Override Should Be Sport-Specific

The blanket 8% override for all sports ML_DOG is too aggressive for NHL (where dog odds are +110 to +200 and parity is high) and appropriate for MLB (where dogs can be +300+). Implementing sport-specific overrides: NHL 6%, NBA 7%, MLB 8% — would allow more NHL dog picks at appropriate edge levels without lowering the MLB bar.

### 5. NRFI/YRFI Hold Warning

The 6–10% hold on NRFI/YRFI is a persistent structural tax. Even with genuine edge, the high hold erodes realized EV significantly. The model should ensure that computed edge is measured against the actual book price (inclusive of vig), not against true probability, before posting NRFI/YRFI picks. A 6% edge computed against true probability at a -140 NRFI line (where hold=8%) represents only ~2% edge net of vig — potentially insufficient to post.

---

*End of TIER_FINDINGS_T4.md — Sections 8 and 9 complete.*
*Next section to research: Section 10 (NFL Player Props) and Section 11 (Portfolio Variance).*
