# Tier Findings T5 — NFL Market Tier Assignments

**Research Date:** 2026-05-21  
**Scope:** Section 10 of the Tier Research Prompt — NFL market tier assignments for all planned stats and game lines.  
**Status:** Complete. All NFL markets covered with CV estimates, efficiency assessments, and concrete tier recommendations.

---

## Summary Table

| STAT | PLANNED | REC | CV (est.) | EFFICIENCY | MIN EDGE |
|------|---------|-----|-----------|------------|----------|
| PASS_YARDS | T2 | T2 | 0.35–0.42 | Medium (soft on star QBs) | 5% |
| RUSH_YARDS | T2 | T3 | 0.65–0.90+ | Medium-Low | 6% |
| REC_YARDS | T2 | T2 | 0.55–0.75 | Medium | 5% |
| RECEPTIONS | T1 | T2 | 0.40–0.55 | Medium | 5% |
| PASS_TDS | T3 | T3 | 0.90–1.10 | Low | 6% (or exclude) |
| RUSH_TDS | T3 | EXCLUDE | >1.50 | Very Low | Exclude |
| REC_TDS | T3 | EXCLUDE | >1.50 | Very Low | Exclude |
| INT | none | EXCLUDE | >1.80 | Low | Exclude |
| SPREAD | T2 | T2 | N/A | HIGH | 5–6% |
| TOTAL | T2 | T2 | N/A | HIGH | 5–6% |
| ML_FAV | T2 | T2 | ~0.80 | High | 5% |
| ML_DOG | T3 | T3 | 1.00–1.60 | High (but CV too wide) | 8% |
| TEAM_TOTAL | T2 | T2 | N/A | Medium-High | 5% |

---

## SECTION 10A: NFL PASS_YARDS

### CV Data
- Within-QB CV (game-to-game, same QB, starting QBs with 10+ starts): **0.35–0.42**
- Source: Player Variance Manifesto (PlayerProfiler) reports QB fantasy point CV peaks near 0.40; Underdog Network best-ball research confirms QB is the least-volatile position. BSC Analytics machine-learning study: mean passing yards = 224.1, std dev = 79.3, implied CV ≈ 0.35.
- QBs are by far the most stable offensive position week-to-week. 73% of passing yards variance is attributable to the QB's own ability/offense; 27% to the defensive opponent.
- Game-script effect: trailing QBs throw more (positive), blowout losers throw garbage-time yards (upward noise). Underdog risk-team QBs have elevated CV ≈ 0.45+; elite QBs in balanced game scripts closer to 0.30–0.35.

### Distribution Shape
- Right-skewed: typical range 200–300 yards but occasional 400–500 yard outbursts create right tail.
- Not zero-inflated (P(0 passing yards) ≈ 0% for a starting QB who finishes a game).
- Approximately log-normal or gamma-shaped rather than Normal.

### Limits and Hold%
- Props carry 8–15% vig at retail books (DraftKings, FanDuel) vs 4.55–4.76% for spreads/totals.
- Prop limits: $250–$500 maximum at sharp books (vs $10,000+ for game spreads). NFL prop lines can vary 25+ yards between sportsbooks — significant line-shopping value.
- Passing yards is described as "one of the most efficiently priced" NFL prop markets due to high public interest, BUT star QB props (Mahomes, Lamar) attract heavy recreational action → book shades lines to exploit public bias.

### Soft vs Sharp
- Mixed: Sharp for marquee QBs (heavily bet, more resources devoted by books), softer for backup or middling QBs (books spend less calibration effort).
- Public overbets QB passing overs on star names. Recommend checking both sides; unders on inflated Mahomes/Lamar lines historically offer value.

### Recommendation
- **Tier: T2, min edge: 5%**
- Justification: CV 0.35–0.42 is meaningfully higher than NBA AST (CV ~0.30) which is T1. The prop market is medium-efficiency (not as sharp as spreads, but higher interest than most props). T2 is correct as planned. YARDS umbrella stat at T2 fits.

---

## SECTION 10B: NFL RUSH_YARDS

### CV Data
- Within-RB CV (RB1, starting role, min 8 games): **0.65–0.90+**
- Game-script is the dominant source of variance. A team trailing by 14+ points will abandon the run; RB effectively gets 0–20 yards in those games. Same RB in a favorable game script can rush for 100+.
- P(very low rush yards, <10) in blowout losses: ~15–20% of RB1 game-weeks involve dramatic game-script collapses.
- Rushing yards is highlighted by betting analysts as the **hardest NFL prop to project** due to carry allocation and game flow dependency.
- DFS research confirms: "At first glance, running back output is seemingly a random thing" — the variance is compressible only via game-script modeling, not stat-based alone.

### Distribution Shape
- Right-skewed with zero-inflation spike: bimodal-ish (many low-yardage games, some 100+ explosion games).
- P(rush yards = 0) for a typical RB1 who finishes the game: ~3–6%. P(rush yards < 20) in bad game scripts: ~15–20%.

### Limits and Hold%
- Rush yards props carry standard prop vig: 8–12%. Less liquid than passing yards at retail books.
- A softer market than passing yards — books devote fewer resources to per-game RB rushing line calibration, especially for non-star RBs.

### Recommendation
- **Tier: T3, min edge: 6%**
- Justification: CV 0.65–0.90+ far exceeds T2 territory. This is the highest-variance non-binary NFL player prop. The epistemic problem (game script is fundamentally unknowable until kickoff) compounds the aleatory variance. Planned T2 is too generous. Upgrade to T3.
- Note: if the model incorporates Vegas spread (proxy for expected game script), CV is reducible but still well above 0.55. Even after adjustment, T3 is appropriate.
- RUSH_YARDS should be separated from a generic YARDS umbrella — it has fundamentally different variance from PASS_YARDS and REC_YARDS.

---

## SECTION 10C: NFL REC_YARDS

### CV Data
- Within-WR CV (WR1 receiving yards, min 8 games): **0.55–0.75**
- Research confirms: "yardage gained has a lot more variance per opportunity than rushing yards" because targets and catch rates are volatile.
- WR1 receiving yards variance is target-share driven. Target-rich WRs (WR1 on pass-heavy teams) have CV closer to 0.55; boom/bust WRs and WR2/3s have CV 0.70–0.80+.
- P(0 receiving yards) for WR1: ~5–10% (DNP, game-script run-heavy, or targeted 0 times in a given game).
- Tyler Lockett example from Player Variance Manifesto: CV = 0.80 despite consistent role. Davante Adams equivalent: CV ≈ 0.47 (route-runner with consistent usage).

### Distribution Shape
- Right-skewed with non-trivial zero-inflation. YPR (yards per reception) adds fat-tail variance (long TDs or big plays spike yardage on few catches).

### Market Efficiency
- Softer than PASS_YARDS. Books spend less calibration effort on non-QB props.
- Line discrepancies of 10–20 yards between books are common for receiving yards — line shopping is important.

### Recommendation
- **Tier: T2, min edge: 5%**
- Justification: CV 0.55–0.75 fits T2 (between T1 and T3 territory). Market is medium-efficiency. Planned T2 is correct.

---

## SECTION 10D: NFL RECEPTIONS — Planned T1 (3% min)

### CV Data
- Within-WR CV for receptions per game: **0.40–0.55**
- Receptions is the most stable NFL receiving stat: "targets per game is the most stable metric, and receptions and yardage per game round out the top three" (SharpFootballAnalysis / FantasyPros research).
- Receptions CV is lower than receiving yards CV because catch/drop variance is smaller than per-reception yardage variance.
- Compare to NBA AST (T1, CV ~0.30–0.40): receptions CV is slightly higher than NBA AST CV. NBA AST is a higher-frequency stat (20+ opportunities per game vs 6–10 targets per NFL game), which compresses NBA AST variance further via law of large numbers.

### Is T1 Correct?
- **T1 at 3% min seems too aggressive.** Key differences from NBA AST:
  1. NFL receptions occur ~17 times per regular season (weekly sport) — far fewer samples to calibrate model confidence.
  2. Receptions are target-dependent: a QB benching, injury, or game-script shift can collapse targets to zero.
  3. Book limits for NFL props are $250–$500 (vs NBA AST limits somewhat higher), indicating market is less efficient than NBA.
  4. The prop market hold for NFL is 8–15% (vs NBA props 6–10%) — wider vig signals lower efficiency.
- **Recommendation: bump RECEPTIONS from planned T1 to T2, min edge 5%.**
- Rationale: CV is defensible at T1 boundary (0.40–0.55), but the weekly format, lower sample size per season, and medium market efficiency push this to T2. Revisit after one NFL season of live data — if CV confirms <0.45 and model accuracy is high, can move to T1.

### Comparison to NBA AST
- NBA AST is T1 because: high frequency (nightly picks available), efficient market, CV ~0.30–0.40, and model has 2+ seasons of calibration data.
- NFL RECEPTIONS has: once-per-week picks, no model calibration data yet, and slightly higher CV. T2 is the correct initial assignment.

---

## SECTION 10E: NFL PASS_TDS / RUSH_TDS / REC_TDS — Planned T3

### PASS_TDS

#### CV and Distribution
- Mean PASS_TDS for starting QBs: ~1.7–1.8 per game.
- P(PASS_TDS = 0): ~20–25% of QB starts (roughly 1 in 4–5 games).
- Variance is very high relative to mean: CV estimated **0.90–1.10**.
- At mean=1.7 with NB-like distribution: σ ≈ 1.5–1.8 TDs, giving CV ≈ 0.90–1.10.
- Most sportsbooks offer the dominant line at 1.5 TDs (over/under 1.5). At this line it is essentially binary: will QB throw 2+ TDs? Yes ~55–60% of games.

#### Market Efficiency and Public Bias
- TD props are explicitly identified as a soft market: "the public bets TDs aggressively." Books shade TD prop lines to exploit public bias toward overs (fans root for touchdowns).
- This creates structural value on UNDER 1.5 TDs for star QBs where public demand inflates the over price.
- However, soft market + high variance = T3 or avoid. The inefficiency doesn't compensate for the binary noise.

#### Recommendation
- **Tier: T3, min edge: 6%, size accordingly (0.29u base at 5% edge)**
- PASS_TDS is the only TD stat worth including — it has enough mean value (1.7–1.8) that the distribution has some continuous character. The primary line at 1.5 TDs is binary-adjacent but not fully binary.
- Flag: DO NOT include as KILLSHOT eligible. TD variance is too high for 3u–4u sizing.

### RUSH_TDS

#### CV and Viability
- RB1 rush TDs: mean ≈ 0.30–0.40 per game (roughly 1 TD every 2.5–3 games).
- P(rush TD = 0): ~65–75% of RB games.
- CV = sqrt(var)/mean >> 1.5 for a Bernoulli-adjacent process.
- At mean=0.35: CV ≈ sqrt(0.35×0.65)/0.35 ≈ 1.44.
- Structurally equivalent to NHL GOALS (which is flagged as borderline exclude).

#### Recommendation
- **EXCLUDE from model.** CV >1.5, binary-adjacent, extremely game-script dependent. No minimum edge is sufficient to make this reliably +EV in a model without red-zone touch forecasting. If red-zone target/carry share data is integrated in the future, revisit as T3.

### REC_TDS

#### CV and Viability
- WR1 rec TDs: mean ≈ 0.20–0.30 per game (roughly 1 TD every 3.5–5 games).
- P(rec TD = 0): ~72–82% of WR games.
- CV >> 1.5.
- Even more binary than RUSH_TDS. Entire outcome determined by whether player got a red-zone target in the game.

#### Recommendation
- **EXCLUDE from model.** Same reasoning as RUSH_TDS. Impossible to model reliably without red-zone target data that the model doesn't currently have.

### TDS Umbrella Stat
- The planned YARDS→T2 and TDS→T3 structure should be refined:
  - PASS_TDS: T3, include
  - RUSH_TDS: EXCLUDE
  - REC_TDS: EXCLUDE
  - TDS umbrella stat should only refer to PASS_TDS if the model groups them; label PASS_TDS separately.

---

## SECTION 10F: NFL INT (Interceptions)

### CV and Distribution
- Mean QB INTs per game (2024 season data): league average ≈ **0.74 interceptions per game** (total 401 INTs / 544 team-games = 0.74 per team's QB).
- Top INT throwers: ~1.0–1.2 per game (Cousins, Mayfield led with 16 over 16 games).
- Low INT throwers: 0.3–0.5 per game.
- P(INT = 0): ~55–65% of QB game-weeks (QB throws 0 interceptions most games).
- CV for Bernoulli-adjacent at mean=0.74: CV = sqrt(0.74×(1-0.74))/0.74 = sqrt(0.19)/0.74 ≈ 0.59, but the actual variance is higher because INTs are extremely lumpy (0, 0, 0, 2, 0, 3, 0...). Effective CV with overdispersion: **1.50–2.00+**.

### Betting Viability
- Market exists at DraftKings: "QB to throw interception" is a live market. Lines are typically set at 0.5 INTs (binary: will QB throw 1+ INT?).
- At line 0.5: P(INT ≥ 1) ≈ 35–45% depending on QB. This is a near-coin-flip with substantial uncertainty. Hold on these markets is very high (10–15%+).
- The public does NOT aggressively bet INTs (unlike touchdowns), meaning the market gets less sharp attention — could mean more mispricing, but the fundamental problem is model accuracy is low for sparse events.
- Books offer very low limits on INT props. Sharp books hang $100–$250 max on INT props.
- A model without possession-level pass defense data, pocket pressure metrics, and QB decision-making grades cannot reliably project INTs.

### Recommendation
- **EXCLUDE from model.** CV too high (effectively >1.50), sparse event (mean <1 per game), low limits, hard to model without advanced pass defense data. Revisit only if model integrates EPA and pass defense pressure rate data.

---

## SECTION 10G: NFL SPREAD

### Market Efficiency
- NFL is the most bet sport in the US. NFL spread lines at DraftKings/FanDuel reflect the consensus of enormous sharp money.
- Academic research (multiple papers): NFL point spread markets are generally efficient; exploitable anomalies (home underdog underestimation) exist but are not consistently profitable.
- NFL spread at -110/-110 carries 4.55–4.76% hold — same as NBA spread, same vig structure.
- NFL props carry 8–15% hold vs spread's 4.55% — the spread market is 2–3× more efficiently priced.
- Sharp book limits: $10,000–$100,000+ on NFL spreads (vs $250–$500 on props). This is the clearest signal that NFL game lines are the sharpest markets available.

### NFL vs NBA Spread: Which Is Sharper?
- NFL is overall SHARPER than NBA for game lines. Reasons:
  1. NFL has the highest total betting handle of any US sport — more sharp money moving lines.
  2. Once-per-week structure gives professional bettors more research time per game (sharper consensus).
  3. NBA has slight advantage in per-game frequency (more picks per season), but NFL game lines represent tighter consensus markets.
- Academic result: NBA spread market shows near-random efficiency; NFL market shows some identifiable biases (home underdog) that have been arbitraged away over time.

### Recommendation
- **Tier: T2, min edge: 5–6%**
- The NFL spread is the sharpest non-game-line market in the model. The hold% is the same as NBA spreads (4.55%), but because the NFL market is weekly and each line gets saturated with sharp money, **min edge should be bumped to 6%** (top of T2 territory) rather than 5%.
- Alternative: Add a sport-specific min_edge override for NFL game lines at 6% vs 5% for NBA game lines (both remain T2 but with different min_edge floors).
- Do NOT move NFL SPREAD to T1. T1 is reserved for player props with demonstrably low CV. Game lines belong in T2 even when very efficient, because they carry moderate outcome variance (spread σ ~13–14 points for NFL games).

---

## SECTION 10H: NFL TOTAL

### Hold% and Efficiency
- NFL totals carry same vig as spread: 4.55–4.76% at -110/-110.
- Research confirms NFL totals market has identifiable inefficiencies (quadratic relationship between line size and cover probability; weather effects not fully priced in), but these are small and require sophisticated situational data to exploit.
- Totals receive slightly less sharp betting volume than spreads (spreads are bet more heavily) → totals may be very slightly less efficient than spreads.
- Weather effects (wind, rain, cold) are the primary exploitable angle in NFL totals — a model with weather data can find edges.

### CV of Game Totals
- NFL game total σ: typical spread in final scores = 8–12 points above or below the total line. Full-game NFL totals have σ ≈ 12–14 points around the line.
- This is the same order of magnitude as NBA totals (σ ≈ 12), but NFL totals are based on combined scores with a typical range of 35–55 points.

### Recommendation
- **Tier: T2, min edge: 5–6%**
- Same reasoning as SPREAD. Apply 6% min_edge override for NFL totals specifically, same as NFL spread.
- Note: if the model does not incorporate weather data for NFL totals, the projection error is higher → 6% min_edge is mandatory, not optional.

---

## SECTION 10I: NFL ML_FAV / ML_DOG

### ML_FAV
- NFL ML_FAV: standard -150 to -300 range.
- At -200: implied prob = 66.7%. CV = sqrt(0.333/0.667) = 0.71.
- At -150: implied prob = 60%. CV = sqrt(0.40/0.60) = 0.82.
- NFL ML_FAV is a liquid, efficient market. Same hold structure as spread (books price ML from spread).
- 2024 season: favorites won 71.7% of games SU (historical high), which temporarily hurt books. But this is variance in outcomes, not efficiency — the market was priced correctly.

**Recommendation: Tier T2, min edge: 5%** (same as NBA ML_FAV)

### ML_DOG
- NFL ML_DOG: typical range +120 to +350.
- At +200: implied prob = 33.3%. CV = sqrt(0.667/0.333) = 1.41.
- At +300: implied prob = 25%. CV = sqrt(0.75/0.25) = 1.73.
- NFL ML_DOG has SAME or HIGHER CV than NBA/MLB dogs due to similar odds range. The weekly format (one-shot per week, no injury news until Thursday injury reports) increases epistemic uncertainty.
- NFL ML_DOG is NOT softer than NBA ML_DOG — the market is extremely liquid and well-arbitraged.
- 2024 data: big underdogs (+5.5+) went 13–2 ATS in first 3 weeks, showing occasional systematic anomalies — but not a persistent edge signal.

**Recommendation: Tier T3, min edge: 8% (same as existing ML_DOG override)**  
Justification: CV 1.41–1.73 is identical to other sports' ML_DOG ranges. The NFL market efficiency means the edge must be genuine (not just model noise) to justify the binary bet risk.

---

## SECTION 10J: NFL TEAM_TOTAL

### Market Characteristics
- Team totals are derivative of game total + spread (implied team total = (total + spread) / 2).
- Lower betting volume than game totals → slightly less sharp → potentially more mispricing.
- Sportsbooks post team totals for NFL games, but they are moved less aggressively by sharp money because total action on team totals is lower.
- Team total σ is lower than game total σ: if game total σ ≈ 13 points, team total σ ≈ 9–10 points (not fully correlated).

### Efficiency Assessment
- Less efficient than TOTAL (lower volume, less sharp action) but not dramatically so.
- Retail sportsbooks like DraftKings and FanDuel post team totals for most NFL games. Lines move less due to lower action volume.
- Best angle: team total pricing doesn't always update as quickly as game total when sharp money moves the main line — lag creates occasional discrepancy.

### Recommendation
- **Tier: T2, min edge: 5%**
- Same tier as TOTAL. The slightly lower efficiency (less sharp action than game total) could justify T1B, but NFL team totals are less soft than MLB team totals because NFL game total markets are more informationally saturated. T2 at 5% is appropriate.
- Apply same 6% min_edge NFL override if implementing sport-specific floor for NFL game lines.

---

## Key Cross-Cutting Findings for NFL Implementation

### NFL-Specific Min Edge Override
**Recommendation: implement NFL game line min_edge = 6%** (vs 5% for NBA game lines), applied to: SPREAD, TOTAL, ML_FAV, TEAM_TOTAL.  
Rationale: NFL spread/total markets are the most efficiently priced in the model. When a very efficient market shows 5% edge, the probability that it's a projection artifact is higher than for less-efficient markets. The 6% floor filters more aggressively for genuine edge.

### NFL SPORT_UNIT_CAP
- Current: NFL = 8u (same as NBA).
- NFL weekly format means **fewer picks per season** (17 game-weeks vs NBA's 82 games). Each miss has higher marginal impact on season P&L.
- Sportsbooks are MORE restrictive with NFL prop limits ($250–$500) than NBA props.
- **Recommendation: NFL SPORT_UNIT_CAP = 5u** (same as NHL). Weekly sport with high per-game stakes warrants a lower cap than a nightly sport. NBA 8u is appropriate for a high-frequency sport; NFL 5u better reflects lower pick frequency and weekly compounding risk.

### NFL STAT_CAP Recommendations
| STAT | CAP | Reason |
|------|-----|--------|
| PASS_YARDS | 2 | 1 QB per team; max 2 good games per slate |
| RUSH_YARDS | 1 | High CV, game-script correlated; cap at 1 per run |
| REC_YARDS | 2 | Multiple WR1s per slate |
| RECEPTIONS | 2 | Same as REC_YARDS |
| PASS_TDS | 2 | Binary-adjacent; don't stack same-game risk |
| SPREAD | 3 | Can diversify across multiple games |
| TOTAL | 3 | Same |
| ML_FAV | 2 | Lower multiplier risk than dog |
| ML_DOG | 1 | High variance; 1 max per session |
| TEAM_TOTAL | 2 | Correlated with TOTAL; cap relative to total picks |

### KILLSHOT Eligibility for NFL
- **No NFL stats should be KILLSHOT eligible at launch.** NFL model has zero calibration data — win probability estimates from a new model cannot be trusted at wp ≥ 0.65 with sufficient confidence for 3u sizing.
- After one full NFL season (~17 weeks of live picks), revisit. Candidate stats if model proves well-calibrated: RECEPTIONS (if re-assigned to T1), PASS_YARDS (if T2 model shows 65%+ win rate on high-confidence picks).

### P(outcome = 0) Reference Table

| STAT | P(0) | Notes |
|------|------|-------|
| PASS_YARDS | ~0% | QBs always attempt some passes |
| RUSH_YARDS | 3–6% | Blowout scenario where RB not used |
| REC_YARDS | 5–10% | WR1 targeted 0 times |
| RECEPTIONS | 3–8% | Similar to REC_YARDS |
| PASS_TDS | 20–25% | 1 in 4–5 games no TD |
| RUSH_TDS | 65–75% | Most games no TD |
| REC_TDS | 72–82% | Most games no TD |
| INT | 55–65% | Most games no INT |

---

## Revised NFL Tier Assignment Table

```
SPORT | STAT       | PLANNED | REC  | CV       | EFFICIENCY | MIN EDGE | NOTES
------|------------|---------|------|----------|------------|----------|------
NFL   | PASS_YARDS | T2      | T2   | 0.35-0.42| Medium     | 5%       | Star QB lines soft (public bias)
NFL   | RUSH_YARDS | T2      | T3   | 0.65-0.90| Medium-Low | 6%       | Game-script kills projection
NFL   | REC_YARDS  | T2      | T2   | 0.55-0.75| Medium     | 5%       | Line shop aggressively
NFL   | RECEPTIONS | T1(plan)| T2   | 0.40-0.55| Medium     | 5%       | T1 too aggressive for weekly sport
NFL   | PASS_TDS   | T3      | T3   | 0.90-1.10| Low-Med    | 6%       | Binary-adjacent; soft market
NFL   | RUSH_TDS   | T3      | EXCL | >1.50    | Very Low   | N/A      | Too binary; exclude
NFL   | REC_TDS    | T3      | EXCL | >1.50    | Very Low   | N/A      | Too binary; exclude
NFL   | INT        | N/A     | EXCL | >1.80    | Low        | N/A      | Too sparse; exclude
NFL   | SPREAD     | T2      | T2   | N/A      | HIGH       | 6%*      | *NFL-specific floor
NFL   | TOTAL      | T2      | T2   | N/A      | HIGH       | 6%*      | *NFL-specific floor
NFL   | ML_FAV     | T2      | T2   | 0.71-0.82| HIGH       | 5%       | Standard game line
NFL   | ML_DOG     | T3      | T3   | 1.41-1.73| HIGH       | 8%       | Same ML_DOG override as all sports
NFL   | TEAM_TOTAL | T2      | T2   | N/A      | Med-High   | 5%       | Less liquid than TOTAL
```

---

## Implementation Notes

1. **YARDS umbrella stat**: Do NOT group PASS_YARDS and RUSH_YARDS under a single YARDS stat — they have fundamentally different CVs (0.37 vs 0.75+) and should be assigned different tiers (T2 vs T3). Either split at the stat level, or handle as separate stats.

2. **TDS umbrella stat**: Only PASS_TDS should be implemented. RUSH_TDS and REC_TDS should be excluded from MVP. If using a TDS umbrella that previously included all three, gate to PASS_TDS only.

3. **NFL game line min_edge**: Add NFL-specific override in config: `NFL_GAME_LINE_MIN_EDGE = 0.06` applied to SPREAD, TOTAL, ML_FAV, TEAM_TOTAL. ML_DOG already has its own 8% override.

4. **SPORT_UNIT_CAP**: Recommend NFL = 5u (not 8u). The weekly format and lower prop limits at retail books make 8u too aggressive for a sport with only 17 betting weeks per year.

5. **No KILLSHOT at NFL launch**: Model has no calibration data. Gate all NFL stats out of KILLSHOT for the first season. Add `NFL` to a KILLSHOT sport blocklist until Win Rate ≥ 53% confirmed on 50+ live NFL picks.

---

## Sources

- [The Player Variance Manifesto — Week-to-Week Player Variance By Position (PlayerProfiler)](https://www.playerprofiler.com/article/the-player-variance-manifesto/)
- [Weekly Variance By Position — Best Ball Key (Underdog Network)](https://underdognetwork.com/football/best-ball-research/weekly-variance-by-position-a-key-to-best-ball)
- [Predicting Yards Passing for NFL QBs Using Machine Learning (BSC Analytics)](https://bscanalytics.com/insights/predicting-yards-passing-for-nfl-qbs-with-machine-learning-part-3)
- [NFL Player Prop Betting Strategy (Leans.ai)](https://leans.ai/nfl-player-prop-strategy/)
- [The Biggest Mistake You're Making When Betting NFL Player Props (Unabated)](https://unabated.com/articles/the-biggest-mistake-youre-making-when-betting-nfl-player-props)
- [Player Prop Limits & Timing Windows (Bettopia)](https://bettopia.us.com/player-prop-limits-timing-windows-when-the-price-is-softest/)
- [Fine Tune Your NBA Prop Betting Strategy (Unabated — NBA/NFL comparison)](https://unabated.com/articles/fine-tune-your-nba-prop-betting-strategy-using-unabated-nba)
- [Best Strategy to Bet NFL Touchdown Props (Outlier)](https://help.outlier.bet/en/articles/12428522-best-strategy-to-bet-nfl-touchdown-props)
- [Bettor Biases and Market Efficiency in the NFL Totals Market (AABRI)](http://www.aabri.com/manuscripts/193138.pdf)
- [Is the NFL Betting Market Still Inefficient? (Springer / Journal of Economics and Finance)](https://link.springer.com/article/10.1007/s12197-018-9431-4)
- [Testing the Efficiency of the NFL Point Spread Betting Market (Claremont)](https://scholarship.claremont.edu/cgi/viewcontent.cgi?params=/context/cmc_theses/article/2102/&path_info=Charles_Spinosa_Thesis.pdf)
- [NFL League Average for Interceptions Per Game in 2024 (StatMuse)](https://www.statmuse.com/nfl/ask/nfl-league-average-for-interceptions-per-game-in-2024)
- [Touchdown Regression — FanDuel Research](https://www.fanduel.com/research/touchdown-regression-what-it-is-and-how-to-use-it-for-player-prop-bets-fantasy-football)
- [How to Analyze QB Interception Props (Outlier)](https://help.outlier.bet/en/articles/8387260-how-to-analyze-qb-interception-props-nfl-player-props)
- [Vigorish Explained (BettingUSA)](https://www.bettingusa.com/sports/vig/)
- [Sportsbook Hold Calculator (nfeloapp)](https://www.nfeloapp.com/tools/sportsbook-hold-calculator/)
- [Wide Receiver Stats That Matter for Fantasy Football (SharpFootballAnalysis)](https://www.sharpfootballanalysis.com/fantasy/wide-receiver-stats-that-matter-fantasy-football-2023/)
- [NFL Prop Bets Explained — Soft Market / Public Bias (NFLBettingHub)](https://nflbettinghub.com/articles/nfl-prop-bets-explained/)
- [Differences Between NBA and NFL Betting (SportyTrader — NBA/NFL efficiency comparison)](https://www.sportytrader.com/us/sports-betting/guide/nba-vs-nfl-betting-differences/)
