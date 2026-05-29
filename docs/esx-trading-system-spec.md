# ESX Live NBA Trading System — System Spec
*Research-grounded replacement for KairosEdge. Built for manual desktop execution on Empire Sports Exchange.*
*Drafted: 2026-05-26*

---

## 1. PLATFORM: EMPIRE SPORTS EXCHANGE (ESX)

### What We Know
- Early-stage / invite-only sports trading exchange. Minimal public footprint — no independent reviews, no Reddit presence, no press coverage yet.
- Positioned as a P2P exchange with "pro tools" — the most trader-centric order suite in US sports exchange space if features are real.
- Available markets: Full Game Winner, Spread, Alt Spreads, Game Total, Alt Totals.
- Contracts appear to be binary (0–100¢ style, like Sporttrade was).

### Order Types Available (unique in the US market)
| Order | Function |
|-------|----------|
| Dollar order | Size in $ rather than contracts |
| Limit buy | Resting buy at a set price |
| Buy Dip | Conditional buy when ask ≤ target (buy-limit entry) |
| Buy Breakout | Conditional buy when ask ≥ target (buy-stop, momentum entry) |
| Market sell | Immediate exit at best bid |
| Limit sell | Resting sell at target price |
| Stop Loss | Auto-exit when bid ≤ target (downside protection) |
| Take Profit | Auto-exit when bid ≥ target (locks gains) |

### Pre-Trade Platform Checks (run before every session)
- Spread check: ≤3¢ for game-winner contracts, ≤5¢ for totals. Wider = don't trade.
- Depth check: ≥$500 visible depth on both sides before entering.
- Kyle λ check: if price is moving a lot per unit of volume, book is thin — reduce size or skip.

---

## 2. CORE PHILOSOPHY

This system replaces KairosEdge. The edge thesis is the same — **prediction markets systematically misprice trailing teams** — but the signal suite is now far richer and grounded in research.

**The primary edge (academically validated):**
Teams trailing at halftime win **5.8–8.0 percentage points more often** than halftime score alone predicts (Berger & Pope, Wharton/Columbia). Markets price on narrative ("they're getting blown out"). The system prices on process ("their opponent is shooting 14/22 in H1 — that regresses hard in H2").

**The secondary edge:**
eFG% deviation from season average is the single best halftime regression signal. A team shooting 8%+ above their season average at halftime is almost certainly going to cool off. The trailing team is systematically underpriced because the market doesn't account for this regression.

---

## 3. INDICATOR FRAMEWORK

### Indicator Validity Matrix (Research-Grounded)

#### Game-State Indicators

| Indicator | Academic Validity | Use in System |
|-----------|------------------|---------------|
| eFG% / Heat Regression Index | ★★★★★ High | Primary filter — is lead built on variance? |
| Net Rating Delta (±8 threshold) | ★★★★★ High | Confirms unsustainable lead |
| Foul Pressure (star in trouble) | ★★★★★ High | Most underpriced live signal |
| Turnover Differential | ★★★★ High | Four Factors #2 — structural edge |
| Time Decay / Required PPM | ★★★★ High | Clock-based filter — is comeback realistic? |
| Comeback Capacity / Halftime Deficit | ★★★★ High | Primary gate — deficit must be in tradeable zone |
| Lineup Power Metric | ★★★★ High | Lineup quality differential is measurable + predictive |
| Possession Advantage | ★★★ Moderate | Corroborating signal |
| Heat Indicator (10-min differential) | ★★★ Moderate | Context only — not a standalone trigger |
| Scoring Momentum | ★★★ Moderate | Context only |
| Hot Hand Index | ★★★ Moderate | Real (+8pp effect) but small in live play — use as filter |
| True Shooting % (last 5/10 min) | ★★★ Moderate | Extreme values (>75% or <35%) = flag only |
| Advanced Efficiency Index / Delta | ★★★ Moderate | Corroborating signal |
| Transition Rate Differential | ★★★ Moderate | Corroborating signal |
| Offensive Board Edge | ★★ Moderate | Weak standalone, useful in combination |
| Defensive Index (stl+blk diff) | ★★ Moderate | High variance — corroborating only |
| Consecutive Points (scoring run) | ★ Low | Do NOT use as standalone trigger. Indistinguishable from random (arxiv 2019). |
| PPP last 3 possessions | ★ Low | Too small sample. 3 possessions = noise. |

#### Market Microstructure Indicators

**Signal hierarchy (leading → lagging):**
1. **Liquidity Pulling Index** — leading. MMs canceling more than adding = price jump incoming. Direction unknown, layer TFI/DC on top.
2. **Book Order Flow Imbalance** — leading. Net adds/cancels near touch. ~55-62% directional accuracy at 5-sec horizon.
3. **Taker Flow Imbalance + Taker Flow Shock** — leading/coincident. TFI is core directional signal. TFS normalizes it against baseline (gate on 15+ trades in window).
4. **Directional Confidence** (YES minus NO TFI) — highest reliability. Differences out noise. DC >+0.20 sustained 30s = tradeable. DC >+0.35 = high conviction.
5. **Large Taker Concentration** — coincident. Large + directional = informed trader fingerprint.
6. **Sweep/Walk Indicator** — coincident. Multi-level sweeps = Tier-1 signal (someone needed size urgently).
7. **Activity Burst Score** — coincident. Confirms signal cluster. Multiplier, not standalone.
8. **Event Intensity** — coincident. Consistency check for binary markets (signal should mirror YES and NO).
9. **Kyle Lambda (Price Impact)** — regime flag. High = thin book, mute other signals, reduce size.
10. **Order Book Imbalance** — lagging/weak. Single large passive order skews it. Background only.
11. **News Indicator (VWAP deviation)** — lagging. Confirms after the move. Not a trigger.

**Signal stacking rule:** Take one signal from each of these 4 families:
- (A) Passive book state: OBI
- (B) Taker aggression: TFI + TFS or DC
- (C) Book dynamics: BOFI or LPI
- (D) Composites: Event Intensity or DC

**4-family confluence = Tier 1 trade. 2-family = Tier 3 / starter position only.**

---

## 4. ENTRY LOGIC

### The Three-Tier Entry System

#### Tier A — Halftime Regression Trade (Highest Conviction, Largest Size)
This is the core of the system. Best window: halftime (no broadcast lag, full data, 15 min to analyze).

**Gate 1 — Deficit range:** Trailing team is down 6–15 points at halftime.
*(Below 6 = market already prices close; above 15 = comeback probability too low)*

| Halftime Deficit | Historical WP (trailing) | Tradeable? |
|-----------------|--------------------------|------------|
| 1–5 pts | ~40–47% | Yes (Berger/Pope bias applies) |
| 6–10 pts | ~28–35% | Primary sweet spot |
| 11–15 pts | ~14–20% | Yes with strong indicator alignment |
| 16–20 pts | ~6–9% | Marginal — requires extreme signal stack |
| 20+ pts | ~2–5% | No |

**Gate 2 — Regression signal:** Leading team's H1 eFG% is **≥6 points above their season average** (check NBA.com box score at half). This is non-negotiable for Tier A.

**Gate 3 — Trailing team is structurally viable:**
- Required PPM is in the 0.63–1.4 zone (time decay indicator)
- No significant lineup disruption (no 3+ fouls on trailing team's best player)
- Trailing team was pre-game favorite OR pre-game spread was ≤5 points

**Gate 4 — Market confirmation:**
- Contract price for trailing team has dropped ≥12¢ from pre-game opening
- Current spread ≤3¢ (adequate liquidity to enter and exit)
- DC (directional confidence) is not strongly negative (market isn't actively fading your direction)

**Entry:** Place limit buy at or slightly below current ask. Set stop-loss at trailing-team price −8¢ from entry. Set take-profit at +18–22¢ from entry (approximately 60% of max theoretical profit).

---

#### Tier B — In-Game Momentum Reversal Trade (Medium Conviction)
Best window: after a scoring run ends (timeout taken), Q2 or Q3.

**Setup:**
- One team just had a 7–12 point scoring run that caused market to reprice
- Timeout was called by the disadvantaged team (peak of momentum wave)
- Advanced Efficiency Delta or Heat Change indicator shows run slowing
- Market price has overshot — DC or TFI shows no further informed buying pressure

**Entry:** Wait 1–2 possessions AFTER the timeout. Enter when price stabilizes (spread returns to ≤3¢). This is fading the run at its peak, not chasing it.

**Exit:** Cash out at 55–60% of theoretical max, or on next significant run by same team. Quick trade — don't hold more than one quarter.

---

#### Tier C — Foul Trouble Scalp (Discretionary, Small Size)
**Setup:**
- Leading team's best player (2K rating >87 proxy: all-star caliber) picks up 3rd foul before halftime OR 4th foul in Q3
- Market has NOT yet moved on this
- You see it before the price does

**Entry:** Immediate limit buy on trailing team YES. Small size (Tier C). Set take-profit at +10–12¢.

**Note:** This requires fastest execution. Foul information hits ESPN app before the market reprices. Typically a 5–20 second window.

---

### What NOT To Enter On
- During a scoring run (not at peak momentum — wait for it to end)
- When spread is >5¢ (too thin, vig kills the edge)
- When Kyle λ is elevated (price is moving a lot per unit of volume — book is thin)
- When required PPM >1.5 (comeback pace is unrealistic)
- When deficit >16 points at halftime
- Final 3:00 of regulation (intentional foul parade — exit everything here)

---

## 5. EXIT LOGIC

### The Three-Exit Framework

**1. Take Profit (primary):** Set at entry. Cash out when bid reaches take-profit target — typically when you've captured 60–65% of the maximum theoretical profit from your entry price to 100¢. Don't wait for full resolution. Sell the remaining variance to the next trader.

**2. Stop Loss (always set at entry):** 
- Tier A trades: stop at −8¢ from entry price
- Tier B trades: stop at −5¢ from entry price  
- Tier C trades: stop at −4¢ from entry price

Use ESX's native stop-loss order — set it the moment you enter. Non-negotiable.

**3. Time-Based Force Exit:** Exit all open positions before the **final 3:00 of regulation**, regardless of P&L. NBA late-game intentional fouling creates unmodellable variance. The time-remaining compression makes a 2-point swing worth 15%+ win probability — position management becomes impossible without a foul-count advantage.

### Game Phase Exit Rules

| Phase | Rule |
|-------|------|
| Q1 | Don't enter. Pre-game quality dominates. Market usually right about early moves. |
| Halftime | Best entry window. Full analysis time. No broadcast lag. |
| Q3 (first 6 min) | Second-best window. Halftime adjustments not yet priced. |
| Q4 (8+ min) | Standard Kelly entries OK. Comeback probability data reliable. |
| Final 3:00 | EXIT EVERYTHING. No new entries. |
| OT | Treat as a new game. Pre-game quality dominates again. Reduce size by 50%. |

---

## 6. MARKET SELECTION

### Which Contract Type to Trade When

**Full Game Winner (primary vehicle):**
- Deepest liquidity on any exchange — tightest spreads
- Highest price volatility with game state = most entry/exit opportunities
- Cleanest binary payoff for Kelly sizing
- **Use for:** All Tier A, B, and C trades by default

**Game Total:**
- Less volatile (blowouts affect it differently than winner)
- Best exploitable signal: **halftime regression on shooting**
- If both teams combined <90 points at half AND both are below their season eFG% averages → strong Over signal in H2
- **Use for:** Shooting-regression thesis at halftime specifically

**Spread / Alt Spreads:**
- Useful when you think the score differential is wrong but have no strong winner view
- Adjusts slower than the winner contract in blowout situations = can create lag opportunity
- Wider spreads than winner contracts in live trading — higher vig
- **Use for:** When deficit regression thesis is strong but game is too close to call a winner

---

## 7. POSITION SIZING

### Quarter-Kelly Formula for Binary Contracts

Standard Kelly for binary prediction market contracts:
```
f* = (p - c) / (1 - c)
```
Where `p` = your true probability estimate, `c` = contract price (e.g., 0.38 = 38¢).

Apply **Quarter Kelly** (×0.25) for all live game trades:
- Live probability estimates carry higher estimation error than pre-game
- Need capital available for multiple trades per session
- Full Kelly has 33% chance of halving bankroll before doubling — unacceptable

**Worked example:**
- Market prices trailing team at 38¢
- Your model (halftime regression + foul trouble) says true probability is 52%
- f* = (0.52 − 0.38) / (1 − 0.38) = 0.226
- Quarter Kelly = 0.226 × 0.25 = **5.65% of session bankroll**

### Sizing Tiers

| Edge | Confidence | Session Bankroll % |
|------|-----------|-------------------|
| 3–6% | Medium (2 signals) | 2–3% |
| 6–10% | High (3 signals) | 4–6% |
| 10%+ | Very High (4-family confluence) | Up to 8% |
| Any | Any | Never exceed 10% per trade |

**Correlation rule:** Multiple simultaneous positions in the same game are highly correlated. Treat them as one position for Kelly purposes — sum the sizes.

---

## 8. THE TIMING EDGE

### How to Minimize Broadcast Lag (Manual Execution)

The lag problem is real. TV streams are 15–30 seconds behind live. By the time you see an event on TV and react, professionals with data feeds have already moved the price.

**The fix:**
1. **Use ESPN app or NBA.com for live score** — updates faster than TV by 15–25 seconds
2. **Watch TV for context, trade from data** — never place an order based purely on what you just saw on screen
3. **Trade the correction, not the event** — by the time you can react to a live event, the price has already moved. Your edge is in the 5–30 second overshoot/correction window after the initial price move
4. **Halftime is your best window** — zero broadcast lag, 15 minutes to analyze box score data and calculate regression signals before placing any order

### The "Fade the Run at the Peak" Timing Rule

When a scoring run happens:
1. Price moves (you see it on ESX)
2. **Do not enter yet**
3. Wait for the timeout — that's the psychological peak of the run
4. Watch the first 1–2 possessions after the timeout
5. If the run stops / scoring normalizes → that's your entry on the team that was trailing
6. Enter when spread returns to ≤3¢ (usually 30–60 seconds after the timeout)

---

## 9. INDICATOR USAGE CHEAT SHEET

### At Halftime (Primary Entry Window)

**Check these in order:**

1. **Deficit** — is it 6–15 points? If >16, skip.
2. **eFG% / Heat Regression Index** — is the leading team 6%+ above season average? Check NBA.com box score.
3. **Net Rating Delta** — is the leading team's live net rating 8+ above their season average? (Unsustainable flag)
4. **Foul Pressure** — does the leading team have a star with 3+ fouls?
5. **Turnover Differential** — is the trailing team +2 or better in turnovers?
6. **Time Decay / Required PPM** — is it below 1.4 for a realistic H2 comeback pace?
7. **Lineup Power Metric / Roster Power Edge** — is the trailing team's current lineup quality competitive?
8. **Market check** — has the trailing team price dropped ≥12¢ from open? Spread ≤3¢? DC not strongly negative?

**Score: 5+ green lights = Tier A entry. 3–4 = Tier B. <3 = skip.**

### During the Game (Tier B/C Windows)

**When a scoring run ends:**
- Heat Changes flipping from negative to positive → momentum reversal signal
- Advanced Efficiency Delta reversing direction → efficiency edge shifting
- Consecutive Points resetting → run confirmation over
- LPI spike → MMs repositioning (price jump expected)
- DC swinging toward trailing team → informed buyers entering

**When foul trouble develops:**
- Foul Pressure indicator spikes
- Players Power Metric drops for leading team (star benched)
- Roster Power Edge narrows → immediate entry window

---

## 10. SIGNALS NOT TO TRADE ON (STANDALONE)

Based on research findings, these indicators have LOW standalone validity and should only be used as supporting context:

- **Consecutive points alone** — statistically indistinguishable from random (arxiv 2019 study)
- **PPP last 3 possessions** — too small a sample, meaningless
- **Orderbook Imbalance alone** — easily dominated by one large passive order, spoofable
- **RSI on contract price** — binary terminal condition makes RSI inapplicable; non-stationary process
- **Moving average on contract price** — same problem; use your own `market_price vs model_probability` gap instead

---

## 11. SYSTEM RULES SUMMARY

1. **Halftime is the primary entry window.** Most of the edge is here.
2. **Never enter during a scoring run.** Wait for the run to end and price to stabilize.
3. **Always set stop-loss at entry.** Use ESX's native stop-loss order. Non-negotiable.
4. **Cash out at 60–65% of max theoretical profit.** Don't hold to resolution.
5. **Exit everything before the final 3:00.** Intentional fouls = unmodellable variance.
6. **Spread ≤3¢ for game-winner, ≤5¢ for totals.** Never trade a wider spread.
7. **Quarter Kelly sizing.** Never exceed 10% of session bankroll per trade.
8. **Use ESPN app / NBA.com for live data, not TV.** 15–25 second edge over broadcast.
9. **4+ signals aligned = Tier A. <3 signals = skip.** Signal stacking is mandatory.
10. **Verify ESX liquidity before committing to any session.** This is a new platform — spread and depth can be thin. If depth <$500 on either side, skip the game.

---

## 12. OPEN QUESTIONS / GATES

- [ ] **ESX liquidity verification** — need to confirm real bid/ask spreads and depth on NBA games before sizing up
- [ ] **ESX regulatory status** — what states is it licensed in? Is Colorado covered?
- [ ] **ESX fees** — fee structure affects Kelly sizing. If similar to Kalshi: `~1.75% at-the-money`
- [ ] **ESX API** — pursue access when available. Would enable automated signal monitoring and alert system.
- [ ] **Sizing calibration** — start with small session bankroll (paper trade equivalent) for first 20–30 trades, then scale
- [ ] **Log format** — build a simple trade log (entry price, exit price, contract, signals fired, P&L) to track CLV equivalent on ESX

---

## 13. RELATIONSHIP TO JONNYPARLAY

This system runs **separately** from the JonnyParlay prop/line betting engine. Do not mix P&L. Maintain a separate log file (e.g., `data/esx_trade_log.csv`). KairosEdge's `kairos-trade-journal` skill can be repurposed for this system once the entry criteria are finalized.

---

*Sources: Berger & Pope (Wharton/Columbia halftime comeback study), Miller & Sanjurjo (Econometrica hot hand), ScienceDirect NBA resilience study (31,753 games), MIT Sloan foul trouble paper, Polymarket microstructure paper (arxiv 2604.24366), Kyle lambda literature, Cont-Kukanov-Stoikov (2011) BOFI signal, Betfair NBA live trading guide, BettorEdge live trading framework, Weimer et al. momentum causal study (2023), arxiv scoring runs study (2019).*
