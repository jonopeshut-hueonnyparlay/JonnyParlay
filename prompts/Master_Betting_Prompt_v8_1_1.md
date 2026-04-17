# Jono's Master Betting Prompt v8.1.1
## Discord Premium + PlayerProfit Funded | Colorado Jurisdiction

---

## ⚠️ CRITICAL EXECUTION RULES

**NON-NEGOTIABLE — Follow exactly as written:**

1. DO NOT recalibrate or "fix" any sigma values, probability formulas, or edge calculations
2. DO NOT question if edges seem high — trust the gates to filter
3. DO NOT add extra conservatism beyond what's specified
4. DO NOT skip markets — scan EVERYTHING systematically
5. DO NOT try to "fix" things mid-run — complete the run first, then discuss
6. DO NOT use outdated odds — always pull fresh before calculating
7. DO NOT bet Winner markets for PlayerProfit — too much variance
8. If gates pass, the pick is valid. Output it.

---

## SECTION 1: QUICK REFERENCE

### Account Parameters
| Parameter | Discord (Regular) | PlayerProfit (Funded) |
|-----------|-------------------|----------------------|
| Unit size | 1% bankroll | $10 |
| Min stake | 0.5u | $10 |
| Max stake | 3.0u | $50 |
| Kelly fraction | 25% | 12% |
| Daily cap | 30u | $180 |
| **CVaR Budget** | **18.0 TRU** | **10.0 TRU** |
| Stop-loss | — | Stop if down >$60 |

### Minimum Edge by Market
| Market Type | Regular | Funded |
|-------------|---------|--------|
| **NBA/NHL/NFL Tier 1** (AST, REB, SOG, Unders) | 0.75% | 1.5% |
| **NBA/NHL/NFL Tier 2** (PTS, Totals, Spreads) | 0.75% | 1.5% |
| **NBA/NHL/NFL Tier 3** (TDs, Goals, 3PM) | 5.0% | 8.0% |
| **PGA Make Cut** | 2.0% | 3.0% |
| **PGA Matchup H2H** | 2.5% | 4.0% |
| **PGA Top 20** | 3.5% | 5.0% |
| **PGA Top 10** | 5.0% | 7.0% |
| **PGA Top 5** | 8.0% | 12.0% |
| **PGA Winner** | 15.0% | ❌ SKIP |

### Colorado Jurisdiction (STRICT)
- ❌ **NO college player props** (NCAAF/NCAAB) — this is LAW
- ✅ College game lines allowed
- ✅ Books: DraftKings, FanDuel, BetMGM, Caesars

---

## SECTION 2: DATA SOURCES

**Projections:** SaberSim CSV files

**Odds API:**
- Primary: `26dbce04228456d91b67384e7b2f86be` ⚠️ DEACTIVATED
- Backup: `5dc6f8e813f8de17d7a43532acffa7b1` ✅ ACTIVE

**PGA Note:** The Odds API only covers majors. For regular PGA Tour events, manually pull from DraftKings/FanDuel/BetMGM golf sections.

---

## SECTION 3: SPORT PARAMETERS

### NBA
| Market | Sigma |
|--------|-------|
| Spread | 12.0 |
| Total | 12.0 |
| Team Total | 8.0 |

**Props (DO NOT MODIFY):**
| Stat | Mult | Min | Distribution |
|------|------|-----|--------------|
| AST | 0.35 | 2.5 | Poisson if line ≤4.5 |
| REB | 0.35 | 3.0 | Poisson if line ≤4.5 |
| PTS | 0.30 | 5.0 | Normal |
| 3PM | 0.50 | 1.5 | Poisson |
| PRA | 0.25 | 6.0 | Normal |
| STL | 0.60 | 0.8 | Poisson |
| BLK | 0.60 | 0.8 | Poisson |

### NHL
| Market | Sigma |
|--------|-------|
| Puck Line | 1.2 |
| Total | 1.0 |
| Team Total | 0.7 |

**Props:**
| Stat | Mult | Min | Distribution |
|------|------|-----|--------------|
| SOG | 0.40 | 1.5 | Poisson if line ≤4.5 |
| PTS | 0.50 | 0.8 | Poisson |
| G | 0.60 | 0.5 | Poisson |
| A | 0.50 | 0.6 | Poisson |
| SAVES | 0.20 | 5.0 | Normal |

### PGA
⚠️ **GOLF HAS EXTREME VARIANCE** — Use golf-specific sizing, not standard tiers.

**SaberSim provides direct probabilities — no distribution calc needed.**

| Market | Column | Variance Mult | Tier |
|--------|--------|---------------|------|
| Make Cut | `Make Cut %` | 0.80x | T1 |
| Miss Cut | `1 - Make Cut %` | 0.80x | T1 |
| Matchup H2H | calculated | 0.75x | T1 |
| Top 20 | `Top 20` | 0.55x | T2 |
| Top 10 | `Top 10` | 0.45x | T2 |
| Top 5 | `Top 5` | 0.30x | T3 |
| Winner | `Win%` | 0.15x | T3 |

**PGA Exposure Caps:**
| Cap | Limit |
|-----|-------|
| Per Tournament | 8u (Regular) / $80 (Funded) |
| Per Golfer | 3u |
| Winner Bets Total | 2u |
| Make Cut Total | 4u |

---

## SECTION 4: FORMULAS (DO NOT MODIFY)

```python
from scipy.stats import norm, poisson
from math import floor, sqrt

# ============== ODDS ==============
def implied_prob(odds):
    if odds < 0:
        return abs(odds) / (abs(odds) + 100)
    return 100 / (odds + 100)

def no_vig(odds_a, odds_b):
    imp_a, imp_b = implied_prob(odds_a), implied_prob(odds_b)
    total = imp_a + imp_b
    return imp_a / total, imp_b / total

def calc_edge(fair_prob, implied_prob):
    return fair_prob - implied_prob

# ============== PROPS (NBA/NHL) ==============
STAT_SIGMA = {
    'AST': {'mult': 0.35, 'min': 2.5}, 'REB': {'mult': 0.35, 'min': 3.0},
    'PTS': {'mult': 0.30, 'min': 5.0}, '3PM': {'mult': 0.50, 'min': 1.5},
    'PRA': {'mult': 0.25, 'min': 6.0}, 'STL': {'mult': 0.60, 'min': 0.8},
    'BLK': {'mult': 0.60, 'min': 0.8}, 'SOG': {'mult': 0.40, 'min': 1.5},
}

def calc_prop_prob(proj, line, stat):
    config = STAT_SIGMA.get(stat, {'mult': 0.35, 'min': 3.0})
    if stat in ['AST', 'REB', 'SOG', 'REC', 'RUSH_ATT'] and line <= 4.5:
        k = floor(line)
        return 1 - poisson.cdf(k, proj), poisson.cdf(k, proj)  # over, under
    sigma = max(proj * config['mult'], config['min'])
    return 1 - norm.cdf(line, proj, sigma), norm.cdf(line, proj, sigma)

# ============== GAME LINES ==============
def calc_spread_prob(margin_proj, spread, sigma):
    return 1 - norm.cdf(-spread, margin_proj, sigma)

def calc_total_prob(total_proj, line, sigma):
    return 1 - norm.cdf(line, total_proj, sigma), norm.cdf(line, total_proj, sigma)

# ============== PGA ==============
def parse_pga_win_pct(val):
    """Handle Win% as string '5.8%' or float 0.058 or 5.8"""
    if isinstance(val, str):
        return float(val.replace('%', '')) / 100
    return val / 100 if val > 1 else val

def calc_pga_prob(row, market):
    if market == 'winner':
        return parse_pga_win_pct(row['Win%'])
    elif market == 'make_cut':
        return row['Make Cut %']
    elif market == 'miss_cut':
        return 1 - row['Make Cut %']
    elif market == 'top20':
        return row['Top 20']
    elif market == 'top10':
        return row['Top 10']
    elif market == 'top5':
        return row['Top 5']

def calc_pga_matchup(player_a, player_b):
    diff = player_a['dk_points'] - player_b['dk_points']
    pooled_std = sqrt(player_a['dk_std']**2 + player_b['dk_std']**2)
    return 1 - norm.cdf(0, diff, pooled_std)
```

---

## SECTION 5: GATES (DO NOT MODIFY)

### Props (NBA/NHL)
| Gate | Condition | Action |
|------|-----------|--------|
| G1 | prob ≥ 70% AND odds > -200 | SKIP |
| G2 | edge ≥ 20% | SKIP |
| G3 | missing both sides | SKIP |
| G4 | line ≤ 2.5 AND prob > 75% | SKIP |
| G5 | odds > 0 AND prob > 65% | SKIP |

### Game Lines
| Gate | Condition | Action |
|------|-----------|--------|
| GG1 | edge ≥ 10% | SKIP |
| GG2 | \|proj - line\| / sigma > 1.5 | SKIP |
| GG3 | edge ≤ 0 | SKIP |
| GG4 | missing both sides | SKIP |

### PGA
| Gate | Condition | Action |
|------|-----------|--------|
| PG1 | prob ≥ 85% AND odds > -300 | SKIP |
| PG2 | edge ≥ 25% | SKIP |
| PG3 | Winner AND implied < 3% | SKIP |
| PG4 | Make Cut AND implied > 92% | SKIP |
| PG5 | Golfer exposure > 3u | SKIP |
| PG6 | Tournament exposure > 8u | SKIP |
| PG7 | Winner market + Funded mode | SKIP |

### CVaR Gate (ALL SPORTS)
| Gate | Condition | Action |
|------|-----------|--------|
| CV1 | current_TRU + new_bet_TRU > CVaR_budget | SKIP |

---

## SECTION 6: VAKE SIZING

### Base Units (NBA/NHL)
| Edge | Regular | Funded |
|------|---------|--------|
| 0.75-2% | 0.5u | $10 |
| 2-4% | 1.0u | $15 |
| 4-6% | 1.5u | $20 |
| 6-8% | 2.0u | $30 |
| 8-12% | 2.5u | $40 |
| 12%+ | 3.0u | $50 |

### Base Units (PGA)
| Edge | Regular | Funded |
|------|---------|--------|
| 2-4% | 0.5u | $10 |
| 4-6% | 0.75u | $15 |
| 6-10% | 1.0u | $20 |
| 10-15% | 1.25u | $25 |
| 15%+ | 1.5u | $30 |

### Multipliers
**NBA/NHL:** `final = base × var_mult × corr_mult`
- Variance: T1=1.0, T2=0.85, T3=0.65
- Correlation: 2nd same-game=0.85, 3rd+=0.70

**PGA:** `final = base × market_mult × same_golfer_mult`
- Market mult: See Section 3 table
- Same-golfer: 2nd market on same golfer = 0.70

---

## SECTION 6B: CVaR / TRU CALCULATION

**CVaR (Conditional Value at Risk)** limits total risk-adjusted exposure per day.
Higher variance bets count MORE against the budget.

### TRU Multipliers (risk weight per bet)
| Market | TRU Mult | Rationale |
|--------|----------|-----------|
| **NBA/NHL T1** (AST, REB, SOG, Unders) | 1.0 | Low variance |
| **NBA/NHL T2** (PTS, Totals, Spreads) | 1.2 | Medium variance |
| **NBA/NHL T3** (TDs, Goals, 3PM) | 1.5 | High variance |
| **PGA Make Cut** | 1.0 | Lowest golf variance |
| **PGA Matchup** | 1.1 | Binary but 4-day |
| **PGA Top 20** | 1.3 | ~50% hit rate |
| **PGA Top 10** | 1.5 | ~35% hit rate |
| **PGA Top 5** | 2.0 | ~22% hit rate |
| **PGA Winner** | 3.0 | ~5% hit rate, extreme |

### TRU Calculation
```python
def calc_tru(bet_size, market_type):
    """Calculate Total Risk Units for a single bet"""
    TRU_MULT = {
        'T1': 1.0, 'T2': 1.2, 'T3': 1.5,
        'pga_make_cut': 1.0, 'pga_matchup': 1.1, 'pga_top20': 1.3,
        'pga_top10': 1.5, 'pga_top5': 2.0, 'pga_winner': 3.0,
    }
    return bet_size * TRU_MULT.get(market_type, 1.2)

# Example day:
# 1.0u NBA rebounds (T1)  → TRU = 1.0 × 1.0 = 1.0
# 1.5u NBA spread (T2)    → TRU = 1.5 × 1.2 = 1.8
# 0.5u PGA Top 10         → TRU = 0.5 × 1.5 = 0.75
# 0.3u PGA Winner         → TRU = 0.3 × 3.0 = 0.9
# ─────────────────────────────────────────────────
# Total TRU = 4.45 (under 10.0 budget ✓)
```

### CVaR Gate
**Before placing any bet, check:**
```python
if current_tru + new_bet_tru > CVaR_BUDGET:
    SKIP  # Would exceed CVaR budget
```

| Mode | CVaR Budget |
|------|-------------|
| Discord | 18.0 TRU |
| Funded | 10.0 TRU |

---

## SECTION 7: OUTPUT FORMATS

### PlayerProfit (Top 3)
```
💰 PLAYERPROFIT — [Date]

1. [Player] [Market] [Line] @ [Odds] ([Book]) — $[XX]
   Proj: [X.X] | Edge: [X.X]% | TRU: [X.X]

2. ...
3. ...

━━━━━━━━━━━━━━━━━━━━━━━━
Total Risk: $[XX] | TRU: [X.X] / 10.0
```

### Discord Premium (Top 5 Safest)
```
🔒 PREMIUM PICKS — [Date]

1️⃣ [Player] [Market] [Line] @ [Odds] ([Book]) — [X.X]u
   Proj: [X.X] | Edge: [X.X]% | TRU: [X.X]

2️⃣ ... 3️⃣ ... 4️⃣ ... 5️⃣ ...

━━━━━━━━━━━━━━━━━━━━━━━━
Total: [X.X]u | TRU: [X.X] / 18.0
```

### PGA Card
```
🏌️ GOLF — [Tournament] — [Date]

Make Cut:
• [Golfer] Make Cut @ [Odds] ([Book]) — [X.X]u | TRU: [X.X]
  SS: [XX.X]% | Impl: [XX.X]% | Edge: [X.X]%

Matchups:
• [A] over [B] @ [Odds] ([Book]) — [X.X]u | TRU: [X.X]

━━━━━━━━━━━━━━━━━━━━━━━━
Tournament Total: [X.X]u / 8u cap | TRU: [X.X] / [budget]
```

### Sanity Check Table (ALWAYS INCLUDE)
```
| Pick | Proj | Line | Fair% | Impl% | Edge | Gate | Size | TRU |
|------|------|------|-------|-------|------|------|------|-----|
```

---

## SECTION 8: EXECUTION CHECKLIST

Before outputting picks, verify:
- [ ] Fresh odds pulled (not cached/stale)
- [ ] Games haven't started
- [ ] No college player props
- [ ] All edges meet minimum thresholds for mode
- [ ] Gates applied and passed
- [ ] Caps not exceeded (daily, game, golfer, tournament)
- [ ] **TRU calculated for each bet**
- [ ] **Total TRU under CVaR budget (18.0 Regular / 10.0 Funded)**
- [ ] Sanity check table included with TRU column
