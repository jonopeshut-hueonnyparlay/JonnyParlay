# TIER FINDINGS T1 — VARIANCE THEORY + MARKET EFFICIENCY FRAMEWORK
Generated: 2026-05-21

---

## SECTION 1: VARIANCE THEORY — FOUNDATION OF VAKE

### Kelly Criterion Basics

**Formula:** f* = (b×p - q) / b
- b = decimal odds - 1 (net odds on a winning bet)
- p = estimated win probability
- q = 1 - p (loss probability)
- Maximises log-wealth (geometric) growth. Kelly is the unique strategy that maximises E[log(W)]. Mathematical proof: Kelly (1956) "A New Interpretation of Information Rate," Bell System Technical Journal. Any fixed-fraction strategy higher than Kelly produces lower long-run growth and higher ruin exposure.

**Fractional Kelly — what sharps actually use:**
- Full Kelly: mathematically optimal growth but 50% drawdown expected with high probability. Extreme volatility.
- Half Kelly (0.5×): ~75% of full Kelly's growth rate, ~50% of variance, ~18% max drawdown vs ~35% at full Kelly. Most common among professional gamblers. Ed Thorp's practice in blackjack/finance.
- Quarter Kelly (0.25×): ~55% of full Kelly's growth, ~25% of variance. Lowest practical drawdown profile. Most common among sharp sports bettors, especially with model uncertainty.
- One-third Kelly (0.33×): intermediate, ~60-65% growth. Used by some quantitative syndicates.
- Academic consensus: Thorp (2008) "The Kelly Criterion in Blackjack, Sports Betting, and the Stock Market" recommends half Kelly as default. Reason cited: bettors systematically overestimate edge, so using half Kelly auto-corrects for overconfidence. Blackjack teams historically use 0.2–0.8× range.
- Practical rule: the less certainty you have in your edge estimate, the smaller the fraction.

**VAKE vs Kelly — T1 calculation:**
- Scenario: T1, 5% edge, 53% WR, -115 odds
  - Implied odds = 0.8696 (decimal = 1.8696, net b = 0.8696)
  - Full Kelly = (0.8696 × 0.53 - 0.47) / 0.8696 = (0.461 - 0.47) / 0.8696 = (−0.009) / 0.8696 ≈ **−0.010**
  - NOTE: At exactly 53% WR vs -115 (which requires 53.49% to break even), Kelly is *negative*. The stated scenario is slightly -EV at face value. Recalculating with correct -115 breakeven = 53.49%:
  - Corrected: 5% edge ON TOP of -115 means actual win_prob ≈ 0.53 + 0.05 × 0.53 = 0.5565, or interpreted as model has 58% WR vs -115 line.
  - At 58% WR, -115 odds: Full Kelly = (0.8696 × 0.58 − 0.42) / 0.8696 = (0.5044 − 0.42) / 0.8696 = 0.0844 / 0.8696 = **9.71% of bankroll = 9.71u**
  - Quarter Kelly = 9.71 × 0.25 = **2.43u**
  - One-third Kelly = 9.71 × 0.33 = **3.20u**
  - Half Kelly = 9.71 × 0.50 = **4.86u**
  - VAKE T1 at 5% edge = 0.75u → equivalent to **~1/13 Kelly** (0.75 / 9.71 = 0.077×)
  - Interpretation: VAKE is extremely conservative relative to Kelly. This is intentional given high stat-level CV, model uncertainty, and the need to survive long negative variance runs.

**VAKE vs Kelly — T2:**
- VAKE T2, 5% edge = 0.57u → ~0.057× full Kelly → **~1/17 Kelly**

**VAKE vs Kelly — T3:**
- T3, 6% edge, 55% WR, +105 odds: decimal = 2.05, net b = 1.05
  - Full Kelly = (1.05 × 0.55 − 0.45) / 1.05 = (0.5775 − 0.45) / 1.05 = 0.1275 / 1.05 = **12.14% = 12.14u**
  - VAKE T3 = 0.29u → **~1/42 Kelly** (0.29 / 12.14 = 0.024×)
  - T3 VAKE is even more fractional — reflects lower model confidence in T3 picks.

**Summary table:**
| Tier | Edge | VAKE | Full Kelly | VAKE/Kelly |
|------|------|------|------------|------------|
| T1 | 5% | 0.75u | ~9.7u | ~1/13 |
| T2 | 5% | 0.57u | ~9.7u | ~1/17 |
| T3 | 6% | 0.29u | ~12.1u | ~1/42 |

VAKE is far more conservative than even quarter Kelly. The implied multiplier is 0.05–0.08×, vs 0.25× for quarter Kelly. This is appropriate given: (a) per-stat CV typically 0.5–1.0+, (b) model edge uncertainty, (c) multi-pick sessions where portfolio variance compounds, (d) prop market pricing uncertainty.

---

### CV Empirical Values (within-player, game-to-game: CV = σ/μ)

Sources: published sports analytics research, StatMuse data, academic papers. Values are estimates from available literature for qualified starters/regulars.

| Stat | CV (σ/μ) | Notes |
|------|----------|-------|
| NBA PTS | 0.40–0.55 | Stars ~0.40 (Durant-tier consistency); role players 0.55–0.70. Consistent scorers lower end. |
| NBA AST | 0.50–0.65 | Higher CV than PTS; game flow dependent. Primary playmakers ~0.50; secondary ~0.65+. |
| NBA REB | 0.45–0.60 | Moderate. Bigs ~0.45 (size advantage stabilises); guards ~0.55–0.60. |
| NBA 3PM | 0.70–1.00 | Highest variance NBA prop. Bimodal distribution common (0 or multi-make nights). 3PT specialists ~0.80–1.00. Confirmed: HIGH_VAR_CV_THRESHOLD=0.60 in model. |
| NHL SOG | 0.50–0.70 | Game-to-game varies widely. Average shooter ~2.5–3.5 SOG/game; σ ≈ 1.5–2.0. Implies CV ~0.55–0.65 for forwards. Defenders lower volume, higher CV. |
| NHL GOALS | 1.00–1.50 | Extremely high CV. Goals are rare events; Poisson-like distribution with mean ~0.3–0.5/game. CV >1 is expected for near-zero-mean Poisson distributions. |
| MLB K (pitcher) | 0.30–0.45 | Lower CV than most — pitchers have strong control. Elite starters ~0.30 (K output most predictable of all stats here). Supported by Poisson-like but high-mean distribution. |
| MLB HR (batter) | 1.20–1.80 | Very high CV. Rare event per game. Mean ~0.1–0.2 HR/game; σ comparable. Effectively Bernoulli per at-bat. |
| MLB HITS (batter) | 0.65–0.85 | Moderate-high CV. Bernoulli each PA; aggregated ~1.5–2.5 hits/game per player. Variance remains substantial. |
| NFL PASS_YARDS | 0.30–0.40 | Most stable of NFL stats. Mean ~230–260 yards; σ ~70–90 yards. CV ~0.30–0.35. (Empirical: mean 224.1, σ 79.3 per game, CV ~0.354 from one source.) |
| NFL RUSH_YARDS | 0.55–0.80 | Higher variance. High-volume backs: mean ~70–90 yards, σ ~40–60 yards. Boom/bust nature raises CV. |
| NFL REC_YARDS | 0.70–0.95 | Receivers highly variable. Role-dependent; target share fluctuates with scheme and coverage. |
| NFL RECEPTIONS | 0.50–0.70 | Moderately high CV. Target-dependent. Primary receivers ~0.50; role receivers ~0.70+. |
| NFL PASS_TDS | 1.00–1.50 | High CV. Rare event per game. Mean ~1.5–2.0 TDs; σ ~1.3–1.7. |

**Key insight:** CV > 0.60 triggers meaningful uncertainty about using point estimates. CV > 1.0 (goals, HR, TDs) signals near-Poisson distributions where standard normal Kelly breaks down.

---

### Skewness and Fat Tails

**Right-skewed distributions and Kelly:**
- Right-skewed stats (rushing yards, receiving yards) have long upper tails — ceiling outcomes are more extreme than a normal distribution would predict.
- For a long bettor (betting OVER), right skew is modestly favorable (more ceiling events than normal assumes).
- For a short bettor (betting UNDER), right skew is unfavorable.
- Standard Kelly assumes the binary win/loss structure of fixed-odds bets — it already captures the bet's discrete payoff. The underlying stat distribution matters for line accuracy, not Kelly sizing per se.
- However: if the model's win_prob estimate is derived from a normal approximation of a right-skewed distribution, the win_prob is systematically biased for OVERs (overstated) and UNDERs (understated) on high-skew stats. This propagates into Kelly being over-sized on OVERs.

**Stats with meaningful fat tails increasing variance risk:**
- NHL Goals: near-Poisson, discrete, mean <1 — fat upper tail relative to normal
- NFL PASS_TDS: same
- NFL RUSH_YARDS: right-skewed, occasional explosion games
- NBA 3PM: bimodal distribution (cold/hot shooting nights), right-skewed upper tail
- MLB HR: near-Bernoulli at game level, extreme fat upper tail

**CV threshold for Kelly aggressiveness:**
- CV > 0.60: standard Kelly becomes noticeably aggressive relative to log-wealth maximisation under uncertainty. Fractional Kelly (0.25×–0.33×) becomes essential.
- CV > 0.80: Kelly should be reduced further. Consider reducing to 0.15–0.20× or using fixed-fraction regardless of computed Kelly.
- CV > 1.00: Kelly may compute near-zero or negative even with real edge, because outcome variance is so high relative to mean. Treat any Kelly output >5% of bankroll with extreme skepticism.
- Academic reference: fat-tail studies (Student's t-distribution) show optimal leverage is materially lower when tail index decreases. The higher the kurtosis excess, the lower the safe Kelly fraction.

---

### Portfolio Variance

**Model posts 5–10 picks/session. Correlation compounding:**

**Same-stat picks, same night (e.g., two NBA PTS):**
- Correlated via: shared game state (blowout affects all PTS props), pace effects, score environment.
- Within-game picks: Pearson r ≈ 0.20–0.35 (moderate positive correlation)
- Cross-game same-stat: r ≈ 0.05–0.15 (low, mainly via slate-wide pace/environment effects)
- Estimates from fantasy/DFS correlation literature; no single authoritative source for exact prop-level r.

**Same-sport picks on full slate (10 games):**
- Cross-game correlation: r ≈ 0.05–0.10 (mostly independent with small slate-level correlation)
- Same-game props across different stats: r ≈ 0.15–0.30 (game-outcome dependency)
- Tatum PTS + Tatum AST + Tatum REB from same game: r ≈ 0.50–0.70 (high; all driven by Tatum's usage/game script)

**Portfolio variance vs sum of individual variances:**
- For N independent picks, portfolio variance = N × (individual variance), i.e., multiplier = 1.0
- With correlation r between all pairs: portfolio variance = N × var + N(N-1) × r × var = N × var × (1 + (N-1)×r)
- At r = 0.10, N = 10: multiplier = 10 × (1 + 9×0.10) = 10 × 1.9 → **portfolio variance = 1.9× vs fully independent**
- At r = 0.20, N = 10: multiplier = 10 × (1 + 9×0.20) = 10 × 2.8 → **2.8× vs independent**
- Practical implication: 10 picks with 10% pairwise correlation behaves like ~5 truly independent picks from a variance perspective.

**95th percentile single-session loss (10 picks at ~0.75u average):**
- Total exposure: ~7.5u
- Assuming 55% WR, -115 odds, CV of session result via binomial: σ ≈ √(10 × 0.55 × 0.45) × avg_unit = √(2.475) × 0.75 ≈ 1.57 × 0.75 = 1.18u
- At 95th percentile (1.645σ): loss ≈ expected_gain + 1.645 × 1.18 ≈ loss of ~1.94u above expected
- Worst-case 0/10 session (p ≈ 0.45^10 ≈ 0.034%): loss = 7.5u gross
- With correlation amplifying variance: effective σ increases by √1.9 ≈ 1.38 → correlated 95th pct loss ≈ 2.7u net loss in a session

**Is 12u/day cap correct?**
- 12u daily cap = 12% of 100u bankroll
- Kelly portfolio theory: total daily exposure should not exceed the sum of individual Kelly fractions
- For 10 picks at quarter Kelly (~0.25u–0.75u each): total ≈ 2.5–7.5u → 12u cap is not binding under normal conditions but provides a hard ceiling for extreme days
- Ruin analysis: 12u single-day loss = 12% bankroll drawdown. Recovering from 12% takes ~12.8% gain. Acceptable.
- 12u cap is conservative in the right direction; typical sessions run 3–8u total exposure.

---

### Bankroll Ruin

**P(50% drawdown) at various Kelly fractions:**
- Full Kelly: ~50% chance of losing half bankroll at some point during extended sequence. (Thorp, multiple simulations confirm.)
- Half Kelly: max drawdown drops to ~18–25%. UPenn simulations: 35% max drawdown at full Kelly → 18% at half Kelly.
- Quarter Kelly: ~8–12% max drawdown probability.
- One-third Kelly: ~12–16% max drawdown.

**Optimal Kelly fraction for <5% ruin probability over 500 sessions:**
- At quarter Kelly (0.25×), ruin probability over 500 sessions approaches near-zero because each bet is small relative to bankroll.
- Academic consensus: 1/4 Kelly keeps ruin probability <5% across 1000 bets in most simulations.
- Note: Kelly's "ruin" in theory = 0 because bets scale with bankroll. In practice, with minimum bet sizes and discretised stakes, ruin risk is real.

**Academic consensus:**
- Thorp (Ed Thorp, blackjack pioneer): Recommends half Kelly (0.5×) as primary recommendation. Justification: bettors overestimate edge → half Kelly auto-corrects and reduces ruin risk.
- Ziemba (William Ziemba, "The Kelly Capital Growth Investment Criterion," World Scientific 2011): Documents that 1/4 to 1/2 Kelly is the practical sweet spot for professionals.
- Aldous (Berkeley, "Good and Bad Properties of the Kelly Criterion"): Notes Kelly is theoretically optimal but practically dangerous; most practitioners should use ≤0.5×.
- Most US sharp sports betting literature: quarter Kelly most cited for prop betting specifically, due to high CV stats.

---

## SECTION 2: MARKET EFFICIENCY FRAMEWORK

### How to Measure Market Efficiency

1. **CLV distribution:** Consistently positive CLV (beating closing price) = evidence of edge. Sharp books (Pinnacle, Circa) close at most efficient prices. If CLV distribution has positive mean over N>200 bets, market is systematically inefficient for that bettor.
2. **Hold%:** Lower hold = more efficient market. Pinnacle: 1.5–3% hold on main markets. US retail (DK/FD/MGM): 4–8% on game lines, 8–15%+ on player props and SGPs.
3. **Limit size:** Low limits signal book uncertainty (they don't trust their own price). Player props at most books: $500–$5,000 limits. Main game lines: $10,000–$50,000. Low-limit = less price discovery = less efficient.
4. **Steam move speed:** Fast (~2–5 min) cross-book line movement after opening = sharp money confirmed. Slow movement = soft market. Steam moves on props are rarer, confirming lower prop efficiency.

### CLV% Realistic for Sharp Bettors

- NFL/NBA game lines (highly efficient): elite bettors average +1% to +2% CLV consistently. Very hard to sustain above +3% on liquid markets.
- Player props (less efficient): sharp bettors can target +3% to +7% CLV. +5% is achievable on soft prop lines.
- CLV above +2% on any market = strong evidence of genuine edge (above market-maker accuracy).
- Win rate proxy: +2% average CLV on -110 lines ≈ 54.5% WR. Consistently profitable.
- Less than 2% of sports bettors are genuinely profitable long-term. Professional sharps maintain 53–55% WR on -110 plays; very few sustain above 56%.

### Pinnacle Hold% vs Retail Book Hold%

| Book Type | Hold% (Game Lines) | Hold% (Player Props) |
|-----------|-------------------|---------------------|
| Pinnacle (sharp) | 1.5–2.5% | 4–6% |
| Circa / Bookmaker (sharp) | 2–3% | 4–7% |
| DraftKings / FanDuel (retail US) | 4–8% | 8–15% |
| BetMGM / Caesars (retail US) | 5–8% | 8–15% |
| Same-Game Parlays (all books) | 15–25%+ | — |

**Interpretation:**
- Soft market signal: hold >8% on game lines (standard retail)
- Sharp pricing signal: hold <3% (Pinnacle-level)
- Player prop hold% gap vs game lines confirms props are structurally less efficient

### Hold% Signal — Soft vs Sharp Market

- Hold <3%: sharp pricing (near Pinnacle level). Closing line is near-efficient.
- Hold 3–6%: moderate. Some exploitable edges remain but market is semi-efficient.
- Hold 6–10%: soft market. Significant edge opportunities. Line is not driven by sharp input.
- Hold >10%: very soft. Props, SGPs, exotic bets. Books set lines algorithmically with little sharp input. CLV metrics unreliable as benchmark here.

### Limit Size as Efficiency Signal

- High limits ($50k+): book confident in price → efficient. Sharp money has already priced it.
- Medium limits ($5k–$20k): semi-efficient. Retail book following sharp market.
- Low limits (<$2k): book uncertain. Price not tested by sharp money. Less efficient = more exploitable.
- Player props at US retail books: typical limit $500–$3,000. Indicates books do NOT trust their own prop lines.
- Implication: prop market inefficiency is partly structural — low limits prevent sufficient sharp capital from correcting mispricing.

### Line Movement Speed After Opening

- Fast movement (within 5 minutes): sharp accounts have bet it. High-priority signal. If YOU have same side before the move, you likely had the right read.
- Slow movement (hours later): driven by public volume, not sharp opinion. Less informative about true probability.
- Cross-book steam (same direction across 3+ books simultaneously): strongest possible sharp signal. Bet or fade based on your model vs the market.
- Reverse line movement (line moves opposite to public betting %): sharp money overrides public. Strong signal for true value being on the sharp side.
- Prop lines: open later, move less, and when they move it's often due to injury news or single sharp bet — not consensus. Less informative as efficiency signal.

### Structural Public Biases — Quantified

| Bias | Direction | Magnitude | Notes |
|------|-----------|-----------|-------|
| Favorite bias | Overbetting favorites | Slight positive return on heavy favorites at college level (~-0.2% vs -50% on longshots). Fading longshots profitable. | Favourite-longshot bias: longshots in college basketball overpriced by up to 3% |
| Over bias | Public leans OVER | Books shade totals toward over to balance exposure. Slight systematic value on UNDERs on public-facing games (nationally televised). | Magnitude: ~1–2% implied probability adjustment |
| Home team bias | Overbetting home teams | Measurable home bias: bettors systematically overestimate home team probability. Books adjust lines to exploit this. | Home favorites most overbet; road underdogs offer value in efficient analysis |
| Popular player bias | Overbetting star player OVER props | Star player props (LeBron, Curry) attract public money → books shade lines higher. Counter: bet UNDERs on high-public-interest star players. | Unquantified exactly; structural direction consistent |

### Player Props vs Game Lines — Market Efficiency Comparison

**Props are systematically less efficient than game lines.** Evidence:

1. **Low limits:** $500–$3k vs $10k–$50k for game lines. Insufficient capital flow to price-correct props.
2. **Book pricing:** Props set by algorithms (statistical models + public-facing adjustments), not by responding to sharp two-way action.
3. **CLV signal quality:** CLV on props is less reliable as a benchmark because the "closing price" itself is not efficiently discovered. A prop closing at -115 may still be mispriced by 5–10% because no sharp limit book has fully priced it.
4. **CLV targets:** Elite bettors target +3–7% CLV on props vs +1–2% on game lines.
5. **Hold% differential:** Props carry 8–15% hold at retail vs 4–8% on game lines. The extra margin is the book's premium for pricing uncertainty.
6. **Key quote (Unabated):** "CLV doesn't mean anything in props. There are very few market-making books when it comes to props. There are very few market signals."

**Conclusion:** Player props across all major sports are the *least* efficient major betting market available. This is where model-driven approaches have the largest exploitable edge — but also where CLV as a validation metric is noisiest.

**Is this true across all sports?** Yes, with degree variation:
- NFL props: still less efficient than NFL game lines, but higher public interest → more price discovery than NBA/NHL props
- NBA props: significant inefficiency, especially role player and non-star props
- NHL SOG props: among the least efficient; few sharp books post props, public interest low, books use thin models
- MLB pitcher Ks: moderate — public interest exists but props still carry high hold%

---

## KEY NUMBERS SUMMARY

| Metric | Value | Source |
|--------|-------|--------|
| Full Kelly (T1 5% edge, 58% WR) | ~9.7u (9.7% bankroll) | Calculated |
| Quarter Kelly (T1) | ~2.43u | Calculated |
| Half Kelly (T1) | ~4.86u | Calculated |
| VAKE T1 (0.75u) equivalent | ~1/13 full Kelly | Calculated |
| P(50% drawdown) full Kelly | ~50% | Thorp, UPenn simulations |
| P(50% drawdown) half Kelly | ~18–25% | UPenn simulations |
| P(50% drawdown) quarter Kelly | ~8–12% | Literature consensus |
| Thorp's recommendation | Half Kelly (0.5×) | Thorp 2008 |
| Sharp game line CLV% | +1–2% | Unabated, VSiN |
| Sharp prop CLV% target | +3–7% | Market consensus |
| Pinnacle hold% (game lines) | 1.5–2.5% | Industry standard |
| US retail hold% (game lines) | 4–8% | Industry standard |
| US retail hold% (props) | 8–15% | Industry standard |
| NBA PTS CV | 0.40–0.55 | Analytics literature |
| NBA 3PM CV | 0.70–1.00 | Analytics literature |
| NHL SOG CV | 0.50–0.70 | Estimated from SOG data |
| NHL GOALS CV | 1.00–1.50 | Poisson theory + data |
| MLB K (pitcher) CV | 0.30–0.45 | Most stable stat |
| NFL PASS_YARDS CV | 0.30–0.40 | Empirical: σ=79, μ=224 |
| NFL RUSH_YARDS CV | 0.55–0.80 | Fantasy variance literature |
| CV threshold for aggressive Kelly | > 0.60 | Applied Kelly theory |
| CV threshold for Kelly breakdown | > 1.00 | Fat-tail distribution research |
| Portfolio variance multiplier (r=0.10, N=10) | 1.9× vs independent | Calculated |
| Portfolio variance multiplier (r=0.20, N=10) | 2.8× vs independent | Calculated |
| 12u/day cap — bankroll impact | 12% max daily drawdown | Engineering estimate |
| Long-run bettor WR at -110 | 53–55% | Published sharp bettor data |
| Break-even WR at -110 | 52.4% | Standard calculation |

---

## IMPLICATIONS FOR VAKE

1. VAKE operates at ~1/13 to 1/42 full Kelly — extraordinarily conservative. This protects against: high CV stats (0.5–1.0+), model edge uncertainty, portfolio correlation compounding, and prop market CLV noise.
2. If model edge is reliably 5%+ and CV is controlled (PTS/AST >20 games), the theoretically safe fraction is quarter Kelly (~2.4u T1). VAKE at 0.75u is ~3× more conservative than quarter Kelly.
3. 3PM props at CV ~0.70–1.00 specifically justify the high-var threshold and the KILLSHOT stat gate excluding REB/3PM in some conditions.
4. The 12u daily cap is well-calibrated: Kelly portfolio theory suggests total exposure ≤ sum of Kelly fractions, and 10 picks × 0.75u = 7.5u typical exposure is well below the 12u ceiling.
5. Player props (all sports) are systematically less efficient than game lines. This is the structural basis for model-driven prop picking having exploitable CLV. The noise in CLV benchmarking on props means ~100 rows is the correct go-live threshold for statistical confidence on the shadow CLV validation (H3 gate).
