---
name: "Sports Betting System v9.4"
description: "Complete betting framework for @picksbyjonny: projection-driven picks with VAKE sizing, confidence modifiers, CLV tracking, MLB recalibrated sigmas, Golf outrights, and sport-specific rules (NBA/NHL/MLB/Golf)"
aliases: ["picking", "bets", "betting", "picks", "MBP", "master betting prompt"]
---

# Sports Betting System v9.4

## Overview
Complete projection-driven betting system combining quantitative edge detection with variance-aware Kelly-adjacent (VAKE) sizing. Deterministic Python engine (`run_picks.py`) reads SaberSim CSVs, fetches live odds from The Odds API (23 US books + exchanges), runs all math, and outputs a full betting card (sections A-M). Zero external AI. Runs in ~30 seconds.

Sports: **NBA** (full), **NHL** (full), **MLB** (full with F5/NRFI), **Golf** (4 majors outrights).

---

## 1. Risk Management — Rules R1-R13

### Hard Rules (auto-reject)
| Rule | Description |
|------|-------------|
| R1 | Max 8 units total daily exposure |
| R2 | Max 1.25 units on any single pick |
| R3 | No moneyline dogs worse than +220 (unless T1 edge ≥ 8%) |
| R4 | No player rebounds props (REB) — historically unprofitable |
| R5 | If CLV negative for 20+ consecutive bets → switch to Conservative mode |

### Soft Rules (Premium 5 selection & sizing)
| Rule | Description |
|------|-------------|
| R6 | Prefer picks with steam / line movement confirmation |
| R7 | Downgrade if player on back-to-back or 3-in-4 nights |
| R8 | Flag altitude games (Denver, Utah, Mexico City) |
| R9 | Prefer overs for pace-up matchups, unders for pace-down |
| R10 | If 2+ props from same game, flag correlation risk |
| R11 | No Under 2.5 AST props (too low-count, high variance) |
| R12 | Cooldown list: players on cold streaks get -0.5 Pick Score penalty |
| R13 | MLB pitcher props: cap at 0.75× VAKE sizing (higher variance than position players) |

---

## 2. Tiers & Minimum Edges

| Tier | Stats | Min Edge |
|------|-------|----------|
| T1 (Premium) | AST, SOG, REC, K, HRR | 3% |
| T1B (Strong) | REB, HITS, HA | 3% |
| T2 (Core) | PTS, YARDS, TOTAL, SPREAD, TEAM_TOTAL, ML_FAV, TB, OUTS, ER, F5_TOTAL, F5_SPREAD, F5_ML | 5% |
| T3 (Speculative) | TDS, GOALS, 3PM, ML_DOG, NRFI, YRFI | 6% |
| T4 (Golf) | GOLF_WIN | 8% |

---

## 3. VAKE Sizing

### Base Units (edge-driven)
| Edge Range | Base Units |
|------------|------------|
| 3%–5% | 0.50u |
| 5%–7% | 0.75u |
| 7%–9% | 1.00u |
| 9%+ | 1.25u |

### Multipliers
| Factor | T1 | T1B | T2 | T3 | T4 |
|--------|-----|------|-----|-----|-----|
| Variance | 1.00 | 1.00 | 0.85 | 0.65 | 0.40 |
| Tier | 1.00 | 1.00 | 0.90 | 0.60 | 0.35 |

### Formula
```
final_units = base × variance_mult × tier_mult × correlation_adj × exposure_adj
```

Special: R13 pitcher penalty → multiply by 0.75 for any MLB pitcher prop.

---

## 4. Projection Files (SaberSim CSV)

### NBA Columns
Player, Salary, Team, Opp, PTS, REB, AST, 3PM, STL, BLK, TO, MIN

### NHL Columns
Player, Salary, Team, Opp, SOG, G, A, BLK, PIM, TOI

### MLB Columns
Player, Salary, Team, Opp, K, OUTS, HA, ER, HITS, TB, HRR, IP, AB

### Golf Columns
Player, Win%, Top5%, Top10%, Top20%, MadeCut%

---

## 5. Distribution & Sigma (v9.4 Recalibrated)

### Poisson Stats (discrete, low count)
**POISSON_STATS** = {AST, REB, SOG, REC, K, HITS}
**POISSON_CUTOFF** = 8.5 (use Normal if projected mean > 8.5)

Push-adjusted Poisson: for integer lines, `P(over) = P(X > line)`, `P(push) = P(X = line)`, `P(under) = P(X < line)`, then `P_adj(over) = P(over) + 0.5 × P(push)`.

### Normal Stats
All other stats (PTS, 3PM, TB, OUTS, HA, ER, HRR, YARDS, TDS, GOALS)

### Sigma Table
| Stat | Multiplier | Minimum σ | Distribution |
|------|-----------|-----------|-------------|
| AST | 0.45 | 1.3 | Poisson |
| REB | 0.58 | 2.5 | Poisson |
| SOG | 0.55 | 1.2 | Poisson |
| REC | 0.50 | 1.2 | Poisson |
| PTS | 0.35 | 4.5 | Normal |
| 3PM | 0.55 | 0.8 | Normal |
| K | 0.45 | 1.5 | Poisson |
| OUTS | 0.22 | 3.0 | Normal |
| HA | 0.50 | 2.5 | Normal (15% overdispersed vs Poisson) |
| ER | 0.85 | 1.8 | Normal |
| HITS | 0.90 | 0.7 | Poisson |
| TB | 1.20 | 1.5 | Normal (lumpy distribution) |
| HRR | 0.75 | 1.3 | Normal |

σ formula: `sigma = max(mult × projection, min_sigma)`

### MLB Correlation Groups
- **Pitcher group**: {K, OUTS, HA, ER} — all functions of IP, r ≈ 0.70+
- **Batter group**: {HITS, TB, HRR} — HITS is component of TB and HRR, r ≈ 0.70+
- Rule: max 1 prop per player within each correlated group (G11/G11b)

---

## 6. Odds & Edge Formulas

### No-Vig Probability
```
implied = |odds| / (|odds| + 100)   if negative
implied = 100 / (odds + 100)         if positive

novig = implied_side / (implied_over + implied_under)
```

### Edge
```
edge = model_probability - novig_probability
```

### Pick Score
```
pick_score = (safety_weight × winprob_normalized) + (edge_weight × edge_normalized)
```

Modes: Default (60/40), Conservative (70/30), Aggressive (45/55).

---

## 7. Gates — Props (G1-G13)

| Gate | Description |
|------|-------------|
| G1 | Minimum edge ≥ tier minimum (T1: 3%, T2: 5%, T3: 6%, T4: 8%) |
| G2 | Minimum win probability ≥ 52% |
| G3 | Minimum 3 books offering the line |
| G4 | Projection must exist in SaberSim CSV |
| G5 | No stale lines (must be from today's odds pull) |
| G6 | Player must have ≥ 15 games played this season |
| G7 | No props on players listed as Questionable or worse |
| G8 | Pick Score ≥ 50 (normalized 0-100 scale) |
| G9 | Over props: projection must exceed line by ≥ 0.5 units |
| G10 | Under props: line must exceed projection by ≥ 0.5 units |
| G11 | MLB: max 1 prop per player per pitcher correlated group {K, OUTS, HA, ER} |
| G11b | MLB: max 1 prop per player per batter correlated group {HITS, TB, HRR} |
| G12 | MLB: max 2 total pitcher props per team (same pitcher) |
| G13 | Golf: only outrights at +10000 or shorter, max 15 picks per tournament |

---

## 8. Gates — Game Lines (GG1-GG4)

| Gate | Description |
|------|-------------|
| GG1 | Minimum edge ≥ 5% (same as T2) |
| GG2 | Minimum 5 books offering the line; blended projection = market + 0.25 × (saber - market) |
| GG3 | No moneyline dogs worse than +220 (R3) |
| GG4 | Spread: use projected spread (proj + line), not proj alone |

### Game Line Sigmas
| Sport | Total σ | Spread σ | Team Total σ |
|-------|---------|----------|-------------|
| NBA | 12.0 | 12.0 | 9.0 |
| NHL | 1.2 | 1.5 | 1.0 |
| MLB | 4.0 | 3.8 | 3.0 |

### MLB First 5 Innings (F5)
| Metric | σ |
|--------|---|
| F5 Total | 2.6 |
| F5 Spread | 2.5 |
| F5 ML | 2.0 |

### NRFI / YRFI
Binary first-inning prop. Model probability from SaberSim's No Run First Inning projection. Edge = model_prob - novig. Tier T3 (min 6% edge).

---

## 9. Sportsbooks (23 US books + exchanges)

Display name mapping (API key → name):
espnbet → theScore Bet, betonlineag → BetOnline, betmgm → BetMGM, betrivers → BetRivers, betus → BetUS, bovada → Bovada, williamhill_us → Caesars, draftkings → DraftKings, fanatics → Fanatics, fanduel → FanDuel, lowvig → LowVig, mybookieag → MyBookie, ballybet → Bally Bet, betanysports → BetAnySports, betparx → BetParx, fliff → Fliff, hardrockbet → Hard Rock Bet, rebet → ReBet, betopenly → BetOpenly, kalshi → Kalshi, novig → Novig, polymarket → Polymarket, prophetx → ProphetX.

Region suffixes (_az, _co, etc.) are stripped to find the base key.

---

## 10. Output Format — Sections A through M

| Section | Content |
|---------|---------|
| A | Header & date |
| B | Odds API status (quota used/remaining, books active) |
| C | SaberSim projection summary per sport |
| D | Pick Score leaderboard (all picks ranked by PS, shows tier, edge, win prob, direction) |
| E | Premium 5 Picks (top 5 by Pick Score after soft rules, with full sizing) |
| F | Full Card (all passing picks, VAKE-sized) |
| G | Game Lines section (spreads, totals, MLs, team totals, F5, NRFI) |
| H | Golf outrights (if applicable) |
| I | Correlation warnings |
| J | Daily exposure summary |
| K | Gate failure log (why each rejected pick failed) |
| L | Rules applied log |
| M | Closing — mode, caps, next steps |

---

## 11. CLV Tracking

Closing Line Value = most reliable short-term edge indicator.

```
CLV = closing_novig_prob - opening_novig_prob_at_bet_time
```

- Positive CLV = you bet before the market moved your way (edge confirmed)
- Track rolling 20-bet CLV average
- R5: If negative CLV for 20+ consecutive bets → auto-switch to Conservative mode

---

## 12. SGP (Same Game Parlay) Rules

- Max 2 legs from same game in any SGP
- Both legs must independently pass all gates
- Correlation adjustment: if same-game, reduce combined sizing by 20%
- Never parlay correlated MLB pitcher stats (G11 applies within SGPs too)

---

## 13. Colorado-Specific Rules

- All CO-legal books: DraftKings, FanDuel, BetMGM, Caesars, BetRivers, Fanatics, theScore Bet, Hard Rock Bet, Bally Bet, BetParx, Fliff
- Track book account health / limit status separately
- Line shop across all healthy books — always take the best number

---

## 14. Daily Workflow

1. Download SaberSim CSV projections for each active sport → save to `C:\Users\jono4\Downloads\projections\`
2. Run `python run_picks.py nba.csv nhl.csv mlb.csv` (or whichever sports are active)
3. System pulls live odds for: player props (NBA: AST/REB/PTS/3PM, NHL: SOG/AST, MLB: K/OUTS/HA/ER/HITS/TB/HRR), game lines (spreads/totals/MLs/team totals), MLB F5 + NRFI, Golf outrights (during major weeks)
4. Review Section D (leaderboard) and Section E (Premium 5)
5. Check Section I for correlation warnings
6. Place bets — line shop via Section F for best book prices
7. Log results → `grade_picks.py` auto-grades from boxscore APIs

---

## 15. Starter Prompt (for Claude)

When the user asks for picks or analysis, run the full MBP v9.4 workflow:

```
Execute ALL sections A through J:
A. Header
B. Odds API status
C. Projection summary
D. Pick Score leaderboard
E. Premium 5 (apply soft rules R6-R12)
F. Full card with VAKE sizing
G. Game lines
H. Golf (if applicable)
I. Correlation warnings
J. Exposure summary
```

Always check: gates → hard rules → soft rules → dedup → sizing → caps → output.

---

## 16. Key Formulas Reference

```python
# Sigma
sigma = max(SIGMA[stat]["mult"] * projection, SIGMA[stat]["min"])

# Poisson P(over)
P_over = 1 - sum(poisson.pmf(k, mu) for k in range(0, line+1))
# Push-adjusted
P_adj_over = P_over + 0.5 * poisson.pmf(line, mu)

# Normal P(over)
P_over = 1 - norm.cdf(line + 0.5, loc=mu, scale=sigma)

# No-vig
novig = implied_side / (implied_over + implied_under)

# Edge
edge = model_prob - novig_prob

# Pick Score
PS = (w_safety * (winprob - 0.52) / 0.28) + (w_edge * (edge - min_edge) / (0.15 - min_edge))
# Clipped to [0, 100]

# VAKE
final_units = base_units * variance_mult * tier_mult * corr_adj * exposure_adj
# R13: if MLB pitcher prop → multiply by 0.75

# Game line blending
blended = market_line + 0.25 * (saber_line - market_line)
```
