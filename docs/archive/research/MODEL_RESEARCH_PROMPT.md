# Model Research Prompt — CLV, Pick Score, Market Timing, Calibration, Sharp Signals & Injury Impact

Paste this into ChatGPT Deep Research or Claude with web search.

---

I am running a Python sports betting model (JonnyParlay) covering NBA, WNBA, NHL, MLB, and NFL.
This prompt covers 6 interconnected model research areas. Every section requires concrete numbers —
exact figures, benchmarks, sample size requirements, formulas. No prose where a number will do.
Flag anything where data was unavailable or conflicting.

## Current Model Context (read before every section)

**Pick score formula:**
```
Modes:
  Default:      score = 0.60 × wp_normalized + 0.40 × edge_normalized
  Conservative: score = 0.70 × wp_normalized + 0.30 × edge_normalized
  Aggressive:   score = 0.45 × wp_normalized + 0.55 × edge_normalized

Normalisation:
  wp_normalized  = (win_prob × 100 − 50) / 25 × 100   (50% wp = 0 pts, 75% wp = 100 pts)
  edge_normalized = (edge × 100) / 20 × 100            (20% edge = 100 pts)

At typical model outputs (wp 55–70%, edge 3–12%):
  wp_n  ≈ 20–80
  e_n   ≈ 15–60
  A 1pp win_prob increase (0.65→0.66) adds 4 score points.
  A 1pp edge increase (7%→8%) adds 2 score points.
  Win_prob is currently 2× more influential per percentage point than edge.
```

**VAKE sizing system:**
```
Base unit from edge:
  3%–5%  → 0.50u base
  5%–7%  → 0.75u base
  7%–9%  → 1.00u base
  9%+    → 1.25u base

Multipliers (variance_mult × tier_mult):
  T1  = 1.00 × 1.00 = 1.00×
  T1B = 1.00 × 1.00 = 1.00×
  T2  = 0.85 × 0.90 = 0.765×
  T3  = 0.65 × 0.60 = 0.39×
```

**Tier system:**
```
T1  (3% min edge): AST, SOG, K, HRR, RECEPTIONS[NFL]
T1B (3% min edge): REB, HITS, HA — direction-restricted (unders only or gated)
T2  (5% min edge): PTS, PRA, PR, PA, RA, OUTS, TB, TOTAL, SPREAD, ML_FAV, TEAM_TOTAL,
                   F5_TOTAL, F5_SPREAD, F5_ML, YARDS[NFL]
T3  (6% min edge): 3PM, ML_DOG, NRFI, YRFI, TDS[NFL], GOALS[NHL]
ML_DOG override: 8% min edge (all sports)
KILLSHOT gate: T1 strict, pick_score≥90, win_prob≥0.65, odds ∈ [-200,+110],
               eligible stats {PTS,AST,SOG,3PM}, max 2/week, 3u default / 4u bump
```

**Calibration (current):**
```
Platt scaling: win_prob = σ(A × raw_logit + B)
PLATT_A = 1.4988, PLATT_B = −0.8102 — frozen pending data accumulation
Status: materially overfit (OOS Brier 0.2511 vs null 0.25)
WP[0.70,0.75) bucket: model says 72%, actual hit rate 53.5% (n=43) — 18pp gap
H3 refit gate: need ~300 graded over_p_raw rows. Currently ~13 rows.
```

**CLV (current):**
```
Formula: clv = closing_implied_prob − your_implied_prob (positive = beat the close)
Captured by: CLV daemon polling every 2 min, T−30 to T+3 min relative to tip
Current SaberSim CLV: mean +0.35%, n=31, 95% CI [+0.08%, +0.62%]
Shadow CLV (custom engine): ~11/100 rows — go-live gate is 100 rows
```

**Books:** 18 Colorado-legal books — DraftKings, FanDuel, BetMGM, Caesars, theScore Bet,
Fanatics, Hard Rock, BetRivers, Bet365, etc. No Pinnacle access directly, but publicly visible.
CLV is measured against whichever book the bet was placed on.

---

## SECTION 1: CLV Methodology — What to do with the data being collected

The model collects CLV for every pick but has no formal framework for what to do with it:
no targets per tier/market, no expand/kill thresholds, no protocol for using it to detect
model drift. Research everything about how to properly use CLV data in a sports betting model.

### 1A. CLV as a proxy for edge — the theoretical foundation

- What is the academic and industry consensus on CLV as a measure of edge?
  Does positive CLV definitively prove long-run profitability, or can you have positive CLV
  without profit? Cite any published studies on the CLV–ROI relationship.
- At what mean CLV is there statistically demonstrated edge vs noise?
  Give minimum n at 80% power, 95% confidence to detect each CLV level:
  ```
  CLV = +0.25%:  n = ?
  CLV = +0.50%:  n = ?
  CLV = +1.00%:  n = ?
  CLV = +2.00%:  n = ?
  ```
  Current model: mean +0.35%, n=31. Is this statistically significant at 95%? At 80%?
- What CLV level constitutes "professional bettor" territory? Benchmarks:
  - Recreational bettor: < ?%
  - Winning recreational: ?–?%
  - Semi-professional: ?–?%
  - Professional sharp: >?%
- Is CLV additive across picks? If 100 picks average +0.5% CLV, does that translate
  reliably to profitable expectation, or does CLV variance dominate at n=100?
- What is the variance (σ) of CLV per pick for player props? For game lines?
  (Needed to calculate confidence intervals on CLV means)

### 1B. CLV targets by tier and market type

For each market below, give the minimum mean CLV target over 50+ picks that indicates
a healthy edge-positive market worth continuing. Give a separate "kill threshold" (negative
CLV sustained over N picks that should trigger removal) and "expand threshold" (CLV level
that justifies raising STAT_CAP or SPORT_UNIT_CAP).

```
Market                      | Min healthy CLV | Kill threshold | Expand threshold | N needed
----------------------------|-----------------|----------------|------------------|----------
NBA player props (PTS/AST)  | +?%             | −?%            | +?%              | ?
NBA 3PM                     | +?%             | −?%            | +?%              | ?
WNBA player props           | +?%             | −?%            | +?%              | ?
NHL SOG                     | +?%             | −?%            | +?%              | ?
MLB K                       | +?%             | −?%            | +?%              | ?
MLB batter props            | +?%             | −?%            | +?%              | ?
NBA game lines (TOTAL)      | +?%             | −?%            | +?%              | ?
NBA game lines (SPREAD)     | +?%             | −?%            | +?%              | ?
MLB game lines              | +?%             | −?%            | +?%              | ?
NFL props (planned)         | +?%             | −?%            | +?%              | ?
NFL game lines (planned)    | +?%             | −?%            | +?%              | ?
```

- Should CLV targets differ by tier?
  (T3 markets have higher variance → more CLV noise → higher n needed to detect real edge vs T1)
- What is the relationship between vig (hold %) and minimum meaningful CLV?
  ```
  −115/−115 vig (4.5%):  min meaningful CLV = ?%
  −120/+100 vig (8.3%):  min meaningful CLV = ?%
  −130/+110 vig (9.1%):  min meaningful CLV = ?%
  ```
- For direction-split tracking (over vs under separately): should tracking be split?
  At what n does per-direction CLV become more meaningful than combined CLV?

### 1C. Using CLV to decide market expand/kill decisions

- At what negative CLV sustained over N picks do you kill a market, stat, or direction?
  What is the right threshold and minimum N?
  (e.g., "If a stat shows mean CLV < −0.5% over 50+ picks, restrict to the direction
  that is positive CLV or remove entirely")
- At what positive CLV do you expand (raise STAT_CAP, increase SPORT_UNIT_CAP)?
- How many picks are required per market before CLV is statistically reliable for
  an expand/kill decision? Give per-market N requirements.
- Should CLV be tracked separately by:
  - Direction (over vs under) per stat?
  - Tier (T1 vs T2 vs T3)?
  - Time of bet placement (opener vs mid-day vs pre-game)?
  - Book (CLV on DraftKings vs Caesars)?
- Should CLV feed directly into pick_score? Proposal:
  If a market has shown mean CLV ≥ +1.0% over 30+ picks, add +5 score points to new picks
  in that market. If CLV ≤ −0.5% over 30+ picks, subtract −5 score points.
  Is this the right approach? What are the risks?

### 1D. CLV by book — which closing lines are most reliable benchmarks?

The model bets on 18 CO-legal books and measures CLV against whichever book the bet is on.

- Which CO-legal books close sharpest on props? On game lines?
  (i.e., which book's closing line is the best proxy for true probability?)
- Empirically: what is the typical CLV advantage of betting on a soft book vs a sharp book?
  (Soft book closes at a worse line = artificially inflated CLV vs actually finding edge)
- Can CLV measured against a soft closing line be compared fairly to CLV measured
  against a sharp closing line? How to normalise?
- Should the model prefer to place bets on known-slower books (higher CLV ceiling)
  vs known-sharp books (lower CLV but more honest signal)?
- Which CO-legal books are known to: copy lines from sharper books immediately /
  move slowly on sharp action / have the best limits for repeat sharp bettors?

### 1E. CLV signal stability — when does CLV history predict future CLV?

- Is historical CLV for a market predictive of future CLV in that same market?
  At what n does the signal stabilise? (i.e., "after 30 picks in a market, CLV history
  predicts future CLV with approximately X% correlation")
- Should recent CLV be weighted more than older CLV?
  What EWMA span is appropriate for CLV tracking? (span = 5? 10? 20?)
- When should the CLV baseline be reset?
  - Start of new season?
  - After a major model change?
  - After a book changes its vig structure?
- Are there market conditions where CLV degrades systematically?
  (early season small samples, post-All Star break, playoff vs regular season)

---

## SECTION 2: Pick Score Formula — Optimising the composite ranking metric

The pick_score controls which 5 picks make the premium card every day. The 60/40 wp/edge
split was set by intuition and has never been formally validated. Research the optimal formula.

### 2A. Theoretical basis — should pick ranking be wp-dominant or edge-dominant?

- Kelly criterion maximises log-wealth via edge-dominant sizing. But pick_score is a
  RANKING metric, not a sizing formula. For ranking, should edge or win_prob dominate? Why?
- If two picks have identical Kelly-implied bet sizes, what differentiates their rank?
  (The higher win_prob pick is more likely to win on this specific bet — argues for wp dominance.
   The higher edge pick has the larger market mispricing — argues for edge dominance.)
- Academic / quant betting literature: is there consensus on how to optimally rank picks?
  Search: "pick selection criterion sports betting", "Kelly ranking vs edge ranking",
  "win probability vs edge in pick selection"
- Is there a theoretical optimal weighting derived from utility maximisation or
  information-theoretic arguments?

### 2B. Diagnosing the current formula — is 60/40 correct?

At typical model outputs:
```
Pick A: win_prob=0.68, edge=0.05 → score = 0.60×(72) + 0.40×(25) = 43.2 + 10.0 = 53.2
Pick B: win_prob=0.60, edge=0.10 → score = 0.60×(40) + 0.40×(50) = 24.0 + 20.0 = 44.0
Pick C: win_prob=0.65, edge=0.08 → score = 0.60×(60) + 0.40×(40) = 36.0 + 16.0 = 52.0
```
Pick A wins despite lower edge, because wp dominates.

- Is Pick A the right selection over Pick B? What does Kelly theory say about which
  pick produces more expected profit on a single bet?
- For Kelly: Pick B at 10% edge may produce more EV per unit than Pick A at 5% edge.
  But Pick A has a higher probability of winning THIS specific bet. When does ranking by
  expected value (edge-dominant) outperform ranking by win probability?
- Empirical test: at pick_log.csv data, does the 60/40 formula correctly rank the
  highest-profit picks? What alternative weightings should be backtested?
  Recommend: 50/50, 70/30, 40/60, 45/55.

### 2C. Normalisation scale — are the anchors correct?

Current normalisation:
- wp baseline (0 points) = 50% — the break-even win probability at -115 odds
- wp ceiling (100 points) = 75% — arbitrary upper anchor
- edge ceiling (100 points) = 20% — never actually reached in practice

Issues:
- What happens to picks with wp > 75%? They score > 100 on wp_n (no cap). Is this intended?
- What happens to picks with edge > 20%? Same (no cap). How often does this occur?
- Is 50% the right wp baseline? At -110 odds, break-even is 52.4%. At -120 odds, 54.5%.
  Should the baseline track the actual vig rather than a fixed 50%?
- Is 75% the right wp ceiling?
  - If win_prob is systematically overfit (known issue: OOS hit rate 59.6% vs model 69.0%),
    what does the ceiling imply about the real wp range the model produces?
  - Should the ceiling be recalibrated after the H3 Platt refit to reflect actual win rates?
- Is 20% edge the right edge ceiling? Give the 95th percentile edge seen in pick_log.csv.
  If p95 edge is 12%, then scores above that are unreachable — ceiling at 15% may be more useful.

### 2D. Should pick_score vary by tier?

Currently identical formula for all tiers. Evaluate:

- T1 picks (AST, SOG): high win_prob confidence, low variance, edge threshold only 3%.
  Should these rank primarily on win_prob with edge as secondary?
- T3 picks (3PM, ML_DOG): high variance, win_prob estimates less reliable (CV > 1.0).
  Should these require a higher edge penalty to rank alongside T1 picks?
- Concretely: a T3 pick at 6% edge / 58% wp and a T1 pick at 3% edge / 58% wp score equally.
  Is that correct? Should the T3 pick rank lower due to higher outcome uncertainty?
- **Proposal — tier handicap in pick_score:**
  ```
  T1  bonus:   × 1.00 (no change)
  T1B bonus:   × 0.95
  T2  bonus:   × 0.90
  T3  bonus:   × 0.80
  ```
  Is this warranted? If yes, what are the correct factors?
- Should KILLSHOT require a higher pick_score threshold for T2-promoted picks (PTS)
  vs native T1 picks (AST/SOG)?

### 2E. Should pick_score vary by stat, direction, or sport?

- **Over vs under**: books shade overs on popular stats (public loves overs on scorers).
  If unders are systematically +EV vs overs in certain markets, should the formula
  give unders a small score bonus? Quantify the bias if it exists.
- **Historical CLV by market**: if AST unders show +1.5% CLV over 50 picks but 3PM overs
  show −0.8% CLV over 50 picks, should this differential feed into scoring?
  What formula?
- **Game lines vs props**: game line win_probs cluster near 50–55% (well-priced markets);
  prop win_probs reach 65–70%+. Game lines structurally score lower and rarely make Premium 5.
  Is this the correct behavior? Or should game lines have a separate normalisation?
- **Sport**: should the formula weight differently across sports?
  (NHL SOG is a different market from NBA 3PM — different variance, different book efficiency)
- **Direction of line movement**: if the line has moved toward your pick (sharp money confirming),
  does this increase confidence? Should it add score points?

### 2F. Additional signals to incorporate into pick_score

For each signal, give: is it worth including, formula for incorporation, risk of adding it:

- **Historical CLV of the market**: running mean CLV over last N picks in that stat/sport.
  Formula: `score += clv_history_weight × (recent_clv_mean − clv_baseline)`
  What weight? What lookback window? What baseline?
- **Line movement direction**: line moved toward your pick vs moved against.
  Formula: `score += line_move_bonus if line_moved_toward_pick else score += line_move_penalty`
  What bonus/penalty magnitude?
- **Injury-triggered flag**: pick was generated from injury redistribution (starter ruled out).
  Should these get a score bonus given the documented book lag?
- **Projection confidence**: cold_start players (fewer than 10 games) have less reliable
  projections. Should score be dampened by a confidence factor?
  Formula: `score *= confidence_factor` where confidence = f(games_in_sample, role_tier)?
- **Time to game**: picks placed at opener have different expected CLV than pre-game picks.
  Should time-of-placement influence score?

### 2G. Backtesting methodology for pick_score optimisation

- What is the correct backtest methodology to determine if changing the 60/40 split
  improves pick selection?
- How to avoid look-ahead bias? (Alternative formula would have selected different picks —
  you don't have graded results for picks that weren't selected under the current formula.)
- What is the minimum n picks in pick_log.csv needed to detect a 5pp improvement in
  win rate from a formula change?
- Is the correct metric: win rate? ROI? CLV? All three? How to weight them?
- Propose a concrete backtesting protocol for this model using pick_log.csv data.

### 2H. Conservative vs Aggressive mode — when to use each

- Conservative (0.70/0.30): produces higher-probability, lower-edge picks.
  Is there empirical evidence that wp-dominant selection outperforms in specific conditions?
  (Small slates? High-variance sports nights? Post-cold-streak confidence rebuild?)
- Aggressive (0.45/0.55): produces higher-edge, lower-probability picks.
  Does edge-dominant selection outperform when the model has demonstrated strong CLV?
  (Well-calibrated model periods? Markets known to be less efficient?)
- Should mode switch be dynamic (auto-detect) or remain manual?
  If dynamic: what signal triggers mode switch?

---

## SECTION 3: Market Timing — When to place bets for maximum CLV

Different markets have optimal bet timing windows. The model currently runs once per day.
Research the optimal timing for every market type and whether a multi-run workflow is warranted.

### 3A. Why timing matters — the information asymmetry framework

- Explain the full timeline from line open to game start for a typical NBA player prop.
  At each stage, what new information has entered the market?
  ```
  Day before or early AM: opener posted → ?
  Mid-day (T-8h to T-4h): ?
  Lineup confirmations (T-90 to T-60 min): ?
  Pre-game (T-60 to T-5 min): ?
  ```
- Empirically: what percentage of total pre-game line movement occurs during each window?
  Give movement distribution for: NBA props / NBA game lines / MLB / NHL / NFL.
- At what point does a market become "fully efficient" (no further expected line movement)?
  By sport: NBA = T−? min, NHL = T−? min, MLB = T−? min, NFL = T−? hours/days.
- Published research on CLV by timing window for sports props. What do the studies show?

### 3B. NBA-specific timing windows

For each market: optimal bet window, reason, expected CLV advantage vs betting at T-30 min,
and what event closes the window.

```
Market          | Optimal window | Reason                        | Expected CLV vs T-30
----------------|----------------|-------------------------------|----------------------
NBA PTS props   | ?              | ?                             | +?%
NBA AST props   | ?              | ?                             | +?%
NBA REB props   | ?              | ?                             | +?%
NBA 3PM props   | ?              | ?                             | +?%
NBA combo (PRA) | ?              | ?                             | +?%
NBA TOTAL       | ?              | ?                             | +?%
NBA SPREAD      | ?              | ?                             | +?%
NBA TEAM_TOTAL  | ?              | ?                             | +?%
NBA ML_FAV      | ?              | ?                             | +?%
```

- Does NBA timing differ: regular season vs playoffs?
- For confirmed starter props (no injury): does opener provide meaningfully more CLV
  than betting at T-2h? Quantify.
- Lineup confirmations (T-90 to T-60 min): should the model wait for lineups before
  posting picks, or is the CLV cost of waiting too large?
  What is the expected CLV at T-90 min (pre-lineup) vs T-60 min (post-lineup)?

### 3C. NHL-specific timing windows

```
Market       | Optimal window | Reason | Expected CLV advantage
-------------|----------------|--------|------------------------
NHL SOG      | ?              | ?      | +?%
NHL AST      | ?              | ?      | +?%
NHL TOTAL    | ?              | ?      | +?%
NHL ML       | ?              | ?      | +?%
```

- NHL lineup confirmation is typically T-60 to T-45 min. How significantly do SOG props
  move after lineup confirmation? Give typical line movement range.
- Is SOG market efficient by T-30 min or does sharp action continue to tip?

### 3D. MLB-specific timing windows

```
Market          | Optimal window | Reason | Expected CLV advantage
----------------|----------------|--------|------------------------
MLB K           | ?              | ?      | +?%
MLB OUTS        | ?              | ?      | +?%
MLB HA          | ?              | ?      | +?%
MLB HITS        | ?              | ?      | +?%
MLB TB          | ?              | ?      | +?%
MLB HRR         | ?              | ?      | +?%
MLB NRFI/YRFI   | ?              | ?      | +?%
MLB TOTAL       | ?              | ?      | +?%
MLB SPREAD      | ?              | ?      | +?%
MLB F5 lines    | ?              | ?      | +?%
```

- Starting pitcher is the biggest MLB variable. After pitcher confirmation, how quickly
  do K/OUTS/HA props reach efficient pricing? Minutes? Hours?
- Weather (wind, temperature at Wrigley, Coors humidor): at what time does weather data
  become actionable for TOTAL and NRFI/YRFI? How much does wind direction affect line?
- Day games vs night games: does earlier lineup posting and earlier weather confirmation
  create a different optimal timing window?

### 3E. NFL-specific timing windows (planned)

```
Market           | Optimal window | Reason | Expected CLV advantage
-----------------|----------------|--------|------------------------
NFL PASS_YARDS   | ?              | ?      | +?%
NFL RUSH_YARDS   | ?              | ?      | +?%
NFL REC_YARDS    | ?              | ?      | +?%
NFL RECEPTIONS   | ?              | ?      | +?%
NFL TOTAL        | ?              | ?      | +?%
NFL SPREAD       | ?              | ?      | +?%
```

- NFL lines open Monday/Tuesday for the following Sunday. Does the sharpest edge appear
  at opener (Tuesday) or does it require the full week to develop?
- NFL timing events and their CLV impact:
  ```
  Wednesday: injury designations released → expected CLV impact on affected props: ?%
  Thursday:  practice participation reports → ?%
  Friday:    final injury report → ?%
  Game-day:  official inactives (T-90 min) → ?%
  ```
- For NFL props: is the market more efficient than NBA props because of the full week
  for sharp action? Does this mean NFL requires higher min_edge to find real edges?

### 3F. Injury-triggered timing — the highest-value window

When a confirmed starter is ruled out (or GTD confirms as active/out):

- What is the typical book response time (minutes from announcement to full line adjustment)
  for replacement player props, by sport and by stat?
  ```
  NBA:  PTS line adjustment lag = ? min
        AST line adjustment lag = ? min
        REB line adjustment lag = ? min
  NHL:  SOG line adjustment lag = ? min
  MLB:  K line adjustment lag = ? min (pitcher scratch)
        TB/HITS line adjustment lag = ? min (batter scratch)
  NFL:  PASS_YARDS lag after injury = ? min
        RUSH_YARDS lag after RB injury = ? min
  ```
- Do books over-adjust, under-adjust, or correctly adjust?
  Give empirical over/under-adjustment direction for: NBA PTS / NBA AST / NHL SOG / NFL yards.
- What CLV is achievable by betting within 10 min of a starter injury announcement?
  Within 30 min? Within 60 min?
- Does lag differ by book? Which CO-legal books are slowest to adjust?
- For GTD players who confirm active: does the opposing team's player props benefit?
  How quickly do books adjust the matchup context for opposing players?
- CLV half-life: how fast does the injury exploitation window close?
  (e.g., "50% of the CLV advantage disappears within X minutes of announcement")

### 3G. Multi-run workflow — should the model run more than once per day?

Currently: one daily run, picks posted, CLV captured at close.

- Given timing research: which pick types benefit most from running at opener vs pre-game?
  (Hypothesis: game lines and rate-based props at opener; injury-triggered props closer to game)
- Is a two-run workflow warranted?
  Run 1 (opener / early AM): game lines + stable prop markets
  Run 2 (T-90 min): injury-triggered props + lineup-confirmed adjustments
- If running only once: what is the single optimal run time (relative to game time) that
  maximises expected CLV across all market types?
- What is the CLV cost of a one-run-per-day workflow vs a two-run workflow?
  Give estimated CLV difference as a %.
- For a 1-person operation with limited time: what is the minimum viable timing improvement?

---

## SECTION 4: Calibration Methodology — When and how to refit the model

The model uses Platt scaling with frozen coefficients pending data accumulation.
Research optimal calibration methodology for every stage of data growth.

### 4A. Platt scaling — theory, reliability, and failure modes

- State the Platt scaling formula: P(win) = σ(A×s + B) where s = pre-Platt raw logit.
  Why does Platt outperform naive logistic regression on small samples?
- What are Platt's failure modes?
  (a) Overfit to in-sample data — at what n does this risk become acceptable?
  (b) Score distribution shift — if the model changes, does the calibration remain valid?
  (c) Non-monotonic raw score — when does Platt fail to improve calibration?
  (d) Others?
- Standard error of Platt A and B coefficients by sample size:
  ```
  n = 50:   SE(A) ≈ ?, SE(B) ≈ ?
  n = 100:  SE(A) ≈ ?, SE(B) ≈ ?
  n = 200:  SE(A) ≈ ?, SE(B) ≈ ?
  n = 300:  SE(A) ≈ ?, SE(B) ≈ ?
  n = 500+: SE(A) ≈ ?, SE(B) ≈ ?
  ```
- At what n does Platt calibration produce a statistically significant Brier improvement
  over the null model (always predict mean win_prob)?
- Cross-validation for Platt: k-fold vs time-series splits.
  For a time-ordered pick log (picks logged chronologically), which CV method is correct?
  Why is random k-fold potentially invalid for time-series data?

### 4B. Alternatives to Platt — when to upgrade

For each alternative, give: minimum n required to outperform Platt, and what conditions
favour it over Platt:

- **Temperature scaling**: single-parameter version (only scales logit, no offset).
  When does it match full Platt? Is it appropriate for small samples (<100 rows)?
  Formula: P(win) = σ(T × s) where T is the temperature parameter.
- **Isotonic regression**: non-parametric monotonic calibration.
  Minimum n to beat Platt: ? (literature says typically n>200).
  Failure mode at small n: what happens?
- **Beta calibration**: log(s) and log(1-s) as features.
  When does it outperform Platt? (Better for bimodal score distributions — does this model have them?)
- **Histogram binning**: discretize scores into N bins, calibrate each separately.
  Minimum n per bin for reliability: ?
  At n=300 total, how many bins are viable?
- **VENN-ABERS prediction**: gives calibration intervals rather than point estimates.
  Is this useful for KILLSHOT gate decisions where interval width matters?
- **Recommendation at each data milestone:**
  ```
  n = 50–100 rows:   use ?
  n = 100–300 rows:  use ?
  n = 300–500 rows:  use ?
  n = 500–1000 rows: use ?
  n > 1000 rows:     use ?
  ```

### 4C. Detecting model drift — early warning system

- What statistical test is most appropriate for detecting Platt calibration drift?
  Options: PSI (Population Stability Index), KS test, rolling Brier score, ECE monitoring.
  For each: how to compute, what threshold triggers investigation.
- Concrete monitoring protocol: what metric, what window, what threshold?
  ```
  Metric: ?
  Rolling window: ? picks
  Alert threshold: ?
  Action when triggered: ?
  ```
- Should drift be monitored globally or per-market?
  (NBA AST calibration may drift while NHL SOG holds — separate monitoring per market)
- What causes calibration drift in sports betting models?
  - Seasonal effects (books adjusting to model patterns)
  - Model changes (any projection update should trigger recalibration check)
  - Market efficiency changes (new books entering, vig changes)
  - Data regime changes (regular season vs playoffs, early season vs late)
  For each: is drift measurable in advance, or only detectable after the fact?

### 4D. Recalibration frequency and triggers

- Fixed schedule vs event-triggered: which is more appropriate for this model?
  Give pros and cons of each.
- Risk of recalibrating too frequently: what is the overfitting risk at n=50/100/200 new rows?
- Risk of recalibrating too infrequently: at what drift level does stale Platt cause
  material impact on KILLSHOT firing frequency and VAKE sizing?
- **Recommended concrete protocol:**
  ```
  First refit trigger:        ? over_p_raw rows (current gate: 300 rows)
  Subsequent refit triggers:  ? new rows accumulated AND/OR drift threshold exceeded
  Maximum recalibration lag:  never let more than ? months pass without checking
  Always refit when:          model change deployed / new sport goes live / ?
  ```
- Should recalibration be split by over/under direction?
  (Current Platt is direction-unified. If AST overs and AST unders have systematically
  different calibration curves, should they be fit separately?)
- Should the model maintain separate Platt coefficients per sport or per tier?
  At what n does per-tier calibration become viable?

### 4E. Calibration metrics — what to measure and target

- **Brier score**: P(error²) averaged. Current OOS = 0.2511 (near null model 0.25).
  What is a realistic target Brier for a prop betting model? Give benchmarks:
  ```
  Professional-grade:    < ?
  Good calibration:      < ?
  Acceptable:            < ?
  Near null (problem):   > ?
  ```
- **Expected Calibration Error (ECE)**: average |P(predicted) − P(actual)| per WP bucket.
  Target ECE for this model: < ?pp
- **Maximum Calibration Error (MCE)**: worst-bucket miscalibration.
  KILLSHOT fires at wp≥0.65 — the [0.65,0.75) buckets are critical.
  Maximum acceptable MCE in the [0.65,0.75) range: ?pp gap
- **Per-bucket gap targets after H3 refit:**
  ```
  WP bucket     | Max acceptable gap (actual vs predicted)
  [0.50, 0.55)  | ≤ ?pp
  [0.55, 0.60)  | ≤ ?pp
  [0.60, 0.65)  | ≤ ?pp
  [0.65, 0.70)  | ≤ ?pp  ← KILLSHOT critical
  [0.70, 0.75)  | ≤ ?pp  ← KILLSHOT critical (currently 18pp off)
  [0.75, 0.80)  | ≤ ?pp
  ```
- **Reliability diagram**: what does good calibration look like at n=100 / n=300 / n=1000 picks?
  How to construct and interpret it.
- **Log-loss vs Brier**: when does log-loss penalise miscalibration more severely?
  Which metric is more actionable for this model's use case?

### 4F. Downstream effects of miscalibration

- Current overfit calibration: WP[0.70,0.75) projects 72%, actual 53.5% (18pp gap).
  Concrete downstream effects:
  - KILLSHOT fires when model says 65%+, but true rate is ~53%. How many false KILLSHOT
    picks per week does this produce? What is the expected ROI on those misfired picks?
  - VAKE sizes assume win_prob is calibrated. If T1 picks at 70% model wp are actually 53%,
    what is the effective Kelly fraction being used vs the intended fraction?
  - Tier thresholds: if wp is systematically high by 15pp, how many T1 picks are falsely
    promoted vs what they would be with correct calibration?
- After the H3 refit, what changes should be audited downstream?
  (KILLSHOT gate threshold, VAKE sizing expectations, tier win-rate benchmarks)

---

## SECTION 5: Sharp Money Signals — Line movement as an additive edge signal

The model uses SaberSim projections + Odds API current lines. Sharp money signals
(steam moves, reverse line movement, book divergence) could be additive signals.
Research what exists, what is reliable, and how to incorporate without double-counting.

### 5A. Sharp signal types — definitions, reliability, and applicability

For each signal: define it precisely, give the detection methodology, historical reliability
(% of time predictive vs noise), and whether it applies to props or game lines only.

- **Steam move**: rapid simultaneous line movement across multiple books.
  - Technical definition: line moves ≥ ? points within ? minutes across ? books simultaneously
  - Reliability: in published studies, what % of steam moves predict the final line direction?
  - Is steam move detection meaningful for player props (thinner markets) or only game lines?
  - What minimum line movement constitutes a steam move for: NBA props / NHL SOG / MLB K / NFL

- **Reverse line movement (RLM)**: line moves opposite to public betting percentage.
  - Definition: >60% of tickets on Team A but line moves toward Team A (sharp on Team B).
  - Reliability: what is the historical win rate of betting with RLM? Against RLM?
    Published benchmarks from Action Network, Pregame.com, or academic sources.
  - Is public ticket % data available for CO-legal books? Which sources provide this?
  - Does RLM exist meaningfully for player props, or only for game lines?

- **Cross-book line divergence**: one CO-legal book has a line materially different from consensus.
  - How to detect: | book_line − consensus_line | > ? points for game lines / ? for props
  - Does the divergent book indicate a weaker model (opportunity) or just slower speed?
  - How quickly do slower books close divergence? Minutes? Hours?

- **Sharp book movement signal**: DraftKings/FanDuel moving in the same direction as
  Pinnacle's published line changes (Pinnacle visible online even if not bettable in CO).
  - Is monitoring Pinnacle's line for directional signal (without betting there) actionable?
  - How correlated are DK/FD movements with Pinnacle's movements, and how lagged?

- **Closing line vs opening line CLV**: the gap between opener and close is itself a sharp signal.
  - If the model's pick matches the direction the line eventually moved (opener vs close),
    does that validate the model's edge or is it noise?
  - Can opening line data from the Odds API be used to compute this?

### 5B. Data sources — what is available and at what cost

For each source, give: what data it provides, cost (free/paid/API), quality for CO-legal books,
and whether it covers props or only game lines:

```
Source               | Line movement? | Public %? | Props? | Cost | CO-legal books? | Quality
---------------------|----------------|-----------|--------|------|-----------------|--------
Odds API (current)   | Current only   | No        | Yes    | Paid | Yes (18)        | Good
Action Network       | ?              | ?         | ?      | ?    | ?               | ?
OddsJam              | ?              | ?         | ?      | ?    | ?               | ?
The Odds Platform    | ?              | ?         | ?      | ?    | ?               | ?
Pinnacle (public)    | ?              | No        | ?      | Free | Not bettable    | Sharp
DonBest              | ?              | ?         | ?      | ?    | ?               | ?
SportsBettingComm.   | ?              | ?         | ?      | ?    | ?               | ?
```

- For each source: can it be accessed via API? If yes, give the endpoint structure.
- Which sources provide line movement HISTORY (tick-by-tick or interval) vs just current line?
- For player prop line movement specifically: which sources track individual stat lines
  (PTS, AST, SOG) vs only game totals and spreads?
- What is the minimum cost setup to access reliable sharp signals for CO-legal books?

### 5C. The double-counting problem — incorporating without duplication

The model already implicitly captures some sharp signal through the current Odds API line
(if sharp money has moved the line, the current line reflects it).

- Define the double-counting failure precisely: the model's edge is calculated against the
  current line. If the line already moved 1 point from open toward the model's pick,
  the model's edge has been partially validated — but using the current line as benchmark
  already captures this. Adding a "sharp move confirmed" bonus would double-count.
- How to detect whether a line movement is already reflected in the edge calculation vs
  represents new information?
- **Correct Bayesian update formula**: given model edge E and a sharp signal (alignment or opposition):
  ```
  Signal aligns with pick:   updated_edge = ?  (more confidence in E)
  Signal opposes pick:       updated_edge = ?  (reduce confidence in E)
  No signal detected:        updated_edge = E  (no change)
  ```
  What are the correct weights? Is this even the right framework?
- Should the model compare to the opening line (not current line) to isolate its independent
  edge from market movement? Pros and cons.
- Is there a clean way to separate: edge from model vs edge from market movement?

### 5D. Implementation recommendation — the simplest approach that adds value

Given the research, evaluate these implementation options:

- **Option A — Pre-filter (block opposing moves)**:
  Don't post picks where the line has moved ≥ X points against the model's direction.
  Block signal: "market disagrees."
  Risk: too aggressive — may block good picks that moved but are still +EV.

- **Option B — Score bonus (confirm alignment)**:
  Add +N score points when sharp movement confirms the model's direction.
  Add −N score points when sharp movement opposes.
  Risk: depends on data source quality and double-counting issue.

- **Option C — Win_prob adjustment**:
  Scale win_prob up or down by a Bayesian factor when sharp signals align or oppose.
  Risk: most complex, most prone to double-counting.

- **Option D — Track only, don't act**:
  Log line movement direction alongside picks. After 100+ picks, analyse whether
  sharp signal alignment predicts better CLV. Only incorporate into scoring after validation.
  Risk: slowest, but safest.

For each option: give the implementation complexity (1=trivial, 5=hard), expected CLV improvement,
and whether it is viable with the current Odds API data subscription.

**Recommend the single best option for a one-person operation at this stage.**

---

## SECTION 6: Injury Market Impact — Exploiting book repricing lag after injuries

The model already handles the projection side of injuries (injury_parser.py with
_POS_FLOW redistribution). The market side — how books reprice other players' props
after an injury, and whether they over/under-adjust — is unresearched.

### 6A. Empirical book adjustment magnitude after starter injury

For each position/stat combination, give the typical book line adjustment after
a starter is ruled out AND whether the adjustment is accurate, over, or under:

**NBA:**
```
Injured player     | Affected market           | Typical line move | Over/Under adjusted?
-------------------|---------------------------|-------------------|---------------------
Star PG (25 PPG)   | Backup PG AST props       | +? pts            | ?
Star PG (25 PPG)   | Team TOTAL                | −? pts            | ?
Star PG (25 PPG)   | Other players PTS         | +? pts (spread)   | ?
Star C (12 REB)    | Backup C REB props        | +? pts            | ?
Star C (12 REB)    | Team TOTAL                | −? pts            | ?
Star SF (20 PPG)   | Other SF PTS              | +? pts            | ?
Star SF (20 PPG)   | Game TOTAL                | −? pts            | ?
Defensive stopper  | Opposing star PTS         | +? pts            | ?  ← often missed
```

**NHL:**
```
Injured player     | Affected market           | Typical line move | Over/Under adjusted?
-------------------|---------------------------|-------------------|---------------------
Top-6 F out        | Other top-6 F SOG         | +? pts            | ?
Top-6 F out        | PP time for others        | ?                 | ?
Top-6 F out        | TOTAL                     | −? pts            | ?
#1 D out           | Other D SOG               | +? pts            | ?
Backup goalie starts| TOTAL                    | +? pts            | ?
```

**MLB:**
```
Injured player     | Affected market           | Typical line move | Over/Under adjusted?
-------------------|---------------------------|-------------------|---------------------
Cleanup hitter out | Team TOTAL                | −? pts            | ?
Cleanup hitter out | Other batters TB/HITS      | ?                 | ?
Starting pitcher   | Replacement pitcher K     | ?                 | ?  ← often wrong
late scratch       | TOTAL                     | ?                 | ?
```

**NFL:**
```
Injured player     | Affected market           | Typical line move | Over/Under adjusted?
-------------------|---------------------------|-------------------|---------------------
RB1 out            | RB2 RUSH_YARDS            | +? pts            | ?
RB1 out            | Game TOTAL                | −? pts            | ?
WR1 out            | WR2 REC_YARDS             | +? pts            | ?
QB injury          | Game TOTAL                | −? pts            | ?
QB injury          | RB RUSH_YARDS             | +? pts (more run) | ?
```

### 6B. Systematic patterns — where is the reliable edge?

Based on the adjustment analysis:

- Which position/stat combinations show the most consistent book under-adjustment?
  (Hypothesis: AST redistribution for backup PG is under-adjusted; books focus on PTS
  and miss the AST impact of star PG absence)
- Which combinations show consistent over-adjustment?
  (Hypothesis: TOTAL lines over-adjust when an offensive star misses — game script shifts
  to slower pace, but books overshoot the total movement)
- Do books more reliably adjust for:
  - Offensive star absence vs defensive anchor absence?
  - Same-team props vs opposing team props?
  - High-volume markets (TOTAL/SPREAD) vs low-volume markets (individual player props)?
- Is there a consistent "forgotten player" pattern? (When Star A is out, Book focuses on
  Star B but misses the impact on Role Player C who now gets more minutes/shots)
- Which sport has the most predictable and exploitable book lag?

### 6C. Exploitation window — timing and CLV magnitude

- What is the exploitation window duration (minutes from announcement to full adjustment)?
  By sport, by book type:
  ```
  NBA props:  DraftKings fully adjusts in ? min / Slower books in ? min
  NHL props:  ? min / ? min
  MLB props:  ? min / ? min
  NFL props:  ? min / ? min
  ```
- What CLV is achievable within the exploitation window?
  Within 10 min: ? CLV
  Within 30 min: ? CLV
  Within 60 min: ? CLV
- CLV half-life: at what point has 50% of the advantage dissipated?
- Does the exploitation window differ by injury severity?
  (Confirmed out vs listed Q vs listed GTD — which has the best lag vs certainty tradeoff?)

### 6D. Implementation — injury edge scanner

The model currently identifies injuries via injury_parser.py but does not score
injury-triggered picks differently from other picks.

- **INJURY_OPPORTUNITY flag**: when the model identifies a pick as injury-triggered
  (win_prob derives from injury redistribution), should it get a pick_score bonus?
  - Bonus magnitude: +? score points (what is the right bonus to reflect the documented
    book lag advantage?)
  - Should the bonus vary by how well-documented the book lag is for that position/stat?
- **Blocking non-injury picks when a major injury occurs**:
  If LeBron is out, should the model suppress non-injury picks and only post the
  injury-redistribution picks? When does "burn the card for injury picks" make sense?
- **Opposing-team flag**: when a defensive player is ruled out, opponent's offensive players
  benefit. Should the model explicitly scan for opposing-team-beneficiary props after
  each injury confirmation?
  Currently: opponent PTS impact is partially captured via matchup factors.
  Gap: AST/REB opponent impact is less explicitly modeled.
- **Minimum viable workflow**:
  Describe the simplest implementation that captures the injury edge:
  1. Detect injury (existing: injury_parser.py)
  2. Identify impacted props (which player markets to scan?)
  3. Calculate expected adjustment vs current book line
  4. Flag as INJURY_OPPORTUNITY and boost pick_score
  What new code/data is needed for steps 2–4?

---

## FINAL OUTPUT REQUIRED

### Table 1: CLV Targets and Decision Thresholds

```
SPORT | STAT/MARKET    | MIN MEANINGFUL CLV | KILL THRESHOLD | EXPAND THRESHOLD | N NEEDED
------|----------------|-------------------|----------------|-----------------|----------
NBA   | PTS props      | +?%               | −?%            | +?%             | ?
NBA   | AST props      | +?%               | −?%            | +?%             | ?
NBA   | REB props      | +?%               | −?%            | +?%             | ?
NBA   | 3PM props      | +?%               | −?%            | +?%             | ?
NBA   | TOTAL          | +?%               | −?%            | +?%             | ?
NBA   | SPREAD         | +?%               | −?%            | +?%             | ?
WNBA  | All props      | +?%               | −?%            | +?%             | ?
NHL   | SOG            | +?%               | −?%            | +?%             | ?
MLB   | K              | +?%               | −?%            | +?%             | ?
MLB   | Batter props   | +?%               | −?%            | +?%             | ?
NFL   | Props (planned)| +?%               | −?%            | +?%             | ?
NFL   | Game lines     | +?%               | −?%            | +?%             | ?
```

### Table 2: Market Timing Windows

```
SPORT | MARKET TYPE        | OPTIMAL WINDOW | EVENT CLOSES WINDOW    | EXPECTED CLV GAIN
------|--------------------|----------------|------------------------|------------------
NBA   | Player props       | ?              | Lineup confirm (T-90)  | +?%
NBA   | Game TOTAL/SPREAD  | ?              | ?                      | +?%
NBA   | Injury-triggered   | T-? to T-?     | Books adjust (? min)   | +?%
NHL   | SOG                | ?              | Lineup confirm (T-60)  | +?%
MLB   | K props            | ?              | Pitcher confirm        | +?%
MLB   | NRFI/YRFI          | ?              | Weather lock           | +?%
MLB   | Game TOTAL         | ?              | ?                      | +?%
NFL   | Props (weekly)     | ? (day before) | Injury report Friday   | +?%
NFL   | Game lines         | ?              | ?                      | +?%
```

### Table 3: Calibration Protocol

```
1. First refit trigger:
   - n rows: ? (current gate: 300 over_p_raw rows)
   - Method: ?-fold CV, time-series splits (Y/N)
   - Target Brier: < ?
   - Target ECE: < ?pp per bucket
   - Critical bucket target ([0.65,0.75)): ≤ ?pp gap

2. Ongoing recalibration:
   - Periodic schedule: every ? months if no drift detected
   - Drift trigger: rolling ?-pick Brier > ? OR per-bucket gap > ?pp
   - Minimum n_new between refits: ? rows

3. Method upgrade path:
   - At n=300:    use Platt (?-fold CV)
   - At n=500:    upgrade to ?
   - At n=1000:   upgrade to ?
   - Per-tier split viable at: n_per_tier = ?

4. Always refit when:
   - Major model change deployed: Y/N
   - New sport goes live: Y/N
   - PLATT_A or PLATT_B drift > ?: Y/N
```

### Table 4: Pick Score Formula — Recommended Parameters

```
1. Weight recommendation:
   Default mode:      wp_weight=?, edge_weight=? (current: 0.60/0.40)
   Conservative mode: wp_weight=?, edge_weight=? (current: 0.70/0.30)
   Aggressive mode:   wp_weight=?, edge_weight=? (current: 0.45/0.55)

2. Normalisation anchors:
   wp baseline (0 pts):  ?%  (current: 50%)
   wp ceiling (100 pts): ?%  (current: 75%)
   edge ceiling (100 pts): ?% (current: 20%)

3. Tier adjustment multipliers:
   T1:  ?× (current: none = 1.0)
   T1B: ?×
   T2:  ?×
   T3:  ?×

4. Additional signals — include Y/N and formula if yes:
   CLV history of market:   Y/N — formula: ?
   Line movement direction: Y/N — formula: ?
   Injury-triggered flag:   Y/N — formula: ?
   Projection confidence:   Y/N — formula: ?
   Direction (over/under):  Y/N — formula: ?

5. Game lines vs props — same formula or separate?
   Same formula: Y/N
   If separate: game line formula = ?
```

### Table 5: Sharp Signal Implementation

```
1. Data source recommendation:
   Primary:    ? (free/paid, what it provides, cost)
   Secondary:  ?

2. Implementation option: A / B / C / D
   (A=pre-filter, B=score bonus, C=wp adjustment, D=track only)
   Rationale: ?

3. If Option B (score bonus):
   Alignment bonus:   +? score points
   Opposition penalty: −? score points
   Detection threshold: line moved ≥ ? pts in ? min

4. Double-counting mitigation:
   Method: ?

5. Apply to game lines: Y/N
   Apply to player props: Y/N
   Reason: ?
```

### Table 6: Injury Edge Scanner Specification

```
1. Book adjustment benchmarks (what books should adjust, empirically):
   Star NBA PG out → backup PG AST line:      +? pts   (books currently under/over by ?)
   Star NBA C out → backup C REB line:        +? pts   (books currently under/over by ?)
   Defensive stopper out → opponent star PTS: +? pts   (books currently under/over by ?)
   Top-6 NHL F out → other F SOG line:        +? pts   (books currently under/over by ?)
   MLB starter scratch → replacement K line:  adjusted? (books currently under/over by ?)

2. Exploitation window:
   NBA: ? min average lag (DraftKings: ? / slower books: ?)
   NHL: ? min
   MLB: ? min
   NFL: ? min

3. pick_score bonus for injury-triggered picks:
   Confirmed book lag for this position/stat: +? score points
   Starter confirmed active (was Q, fear allayed): +? score points
   Opposing-team beneficiary (defensive anchor out): +? score points

4. Implementation phases:
   Phase 1 (add to current model now): ?
   Phase 2 (after custom engine go-live): ?
   Phase 3 (data accumulation required): ?
```
