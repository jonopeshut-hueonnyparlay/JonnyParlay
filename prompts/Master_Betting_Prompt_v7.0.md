# MASTER BETTING PROMPT v7.0

## STATUS
```
PP Record:    0-0
PP Cushion:   $100.00
PP Mode:      STANDARD
Discord Unit: $10 (1u = $10)
Timezone:     MT (Mountain)
```

---

## TIERS

| Tier | Stats | PP Eligible | Min Edge |
|------|-------|-------------|----------|
| T1 | AST, REB, SOG, REC, Saves | Yes | 1% |
| T2 | PTS, Yards, Totals, Spreads, Team Totals, 1H, ML Fav | No | 2% |
| T3 | TDs, Goals, 3PM, ML Dog | No | 5% |

Direction (over/under) does not affect tier.

---

## PLAYERPROFIT

**Eligible:** T1 stats, over or under

| Cushion | Mode | Win% | Edge | Odds |
|---------|------|------|------|------|
| <$15 | CRITICAL | PAUSE | — | — |
| $15-30 | SURVIVAL | ≥62% | ≥6% | -105 to -170 |
| $30-50 | CAUTIOUS | ≥60% | ≥5% | -105 to -180 |
| $50-75 | STANDARD | ≥58% | ≥4% | -105 to -200 |
| $75+ | AGGRESSIVE | ≥55% | ≥3% | -105 to -250 |

**Rules:**
- $10 flat, 1/day max
- Both sides odds required
- All gates must pass
- Loss = stop for day
- No live bets

**Confidence (all required):**
- Played 5+ of last 7
- No injury tag
- Minutes within 15% avg
- Line not moved 0.5+ against

---

## DISCORD

**Unit:** $10 (adjust to your bankroll as 1% of total)

| Edge | Units |
|------|-------|
| 1-2% | 0.5u |
| 2-3.5% | 0.75u |
| 3.5-5% | 1.0u |
| 5-7% | 1.25u |
| 7-10% | 1.5u |
| 10-15% | 1.75u |
| 15-20% | 2.0u |

**Formula:** `Base × Variance × Tier × Correlation × Exposure`

| Multiplier | T1 | T2 | T3 |
|------------|----|----|----| 
| Variance | 1.00 | 0.85 | 0.65 |
| Tier | 1.00 | 0.90 | 0.60 |

| Correlation | Value |
|-------------|-------|
| None | 1.00 |
| Same game, 2nd bet | 0.85 |
| Same game, 3rd+ bet | 0.70 |
| Same player, different stat | 0.85 |

| Exposure | Value |
|----------|-------|
| 1st bet on stat type | 1.00 |
| 2nd bet on stat type | 0.70 |

**Caps (per day, MT midnight reset):**
- Props: 2/stat, 2/game
- Totals: 4, Spreads: 4
- Sport: NBA 10u, NHL 6u, NFL 8u, NCAA 4u
- Daily: 30u

**Same game:** Two props from same contest (e.g., Lakers vs Celtics).

---

## VALIDATION

Before calculation, reject if:
```
proj ≤ 0        → Skip (bad data)
odds = 0        → Skip (invalid)
missing side    → Skip (can't calculate no-vig)
```

Apply floor: `proj = max(proj, 0.05)`

---

## ODDS

**Implied:**
```
Negative: |odds| / (|odds| + 100)
Positive: 100 / (odds + 100)
```

**No-Vig:**
```
p1_nv = p1 / (p1 + p2)
p2_nv = p2 / (p1 + p2)
```

**Staleness:** Re-pull if odds >30 min old before placing bet.

---

## PROPS

**Distribution selection:**
```
IF stat in [AST, REB, SOG, REC, Saves] AND line ≤ 4.5:
    USE Poisson
ELSE:
    USE Normal
```

**Poisson (discrete, low counts):**
```
k = floor(line)
Under: poisson.cdf(k, proj)
Over:  1 - poisson.cdf(k, proj)
```

**Normal (continuous, higher counts):**
```
sigma = max(proj × mult, min_sigma)
Under: norm.cdf(line, proj, sigma)
Over:  1 - norm.cdf(line, proj, sigma)
```

| Stat | Mult | Min σ |
|------|------|-------|
| AST | 0.45 | 1.2 |
| REB | 0.40 | 1.8 |
| SOG | 0.55 | 1.0 |
| REC | 0.50 | 1.2 |
| PTS | 0.35 | 4.5 |
| Yards | 0.30 | 15.0 |

---

## GAME LINES

**Totals:**
```
Under: norm.cdf(line, proj, σ)
Over:  1 - norm.cdf(line, proj, σ)
```

**Team Totals:** Same formula, different σ.

**Spreads:**
```
margin = team_proj - opp_proj
cover = 1 - norm.cdf(-spread, margin, σ)
```
Spread sign: team -3.5 means team favored by 3.5.

**Moneylines:**
```
win = 1 - norm.cdf(0, margin, σ)
```

**1H/1P:**
```
proj_1H = full_proj × 0.48
proj_1P = full_proj × 0.33 (NHL)
```

**Alt Lines:** Same formulas, just different line value. Check if edge gain offsets worse odds.

| Sport | Total σ | Spread σ | Team σ | 1H σ |
|-------|---------|----------|--------|------|
| NBA | 12.0 | 12.0 | 9.0 | 8.5 |
| NHL | 1.2 | 1.5 | 1.0 | 0.9 |
| NFL | 10.0 | 13.5 | 7.5 | 7.0 |
| NCAAB | 11.0 | 11.0 | — | — |
| NCAAF | 12.0 | 14.0 | — | — |

---

## EDGE

```
edge = model_prob - novig_prob
```

Must be positive to bet.

---

## GATES

**Props:**
| Gate | Trigger | Action |
|------|---------|--------|
| G1 | prob ≥ 70% AND odds > -200 | Skip |
| G2 | edge ≥ 20% | Skip |
| G3 | missing both sides | Skip |
| G4 | line ≤ 2.5 AND prob > 75% | Skip |
| G5 | odds > 0 AND prob > 65% | Skip |

**Game Lines:**
| Gate | Trigger | Action |
|------|---------|--------|
| GG1 | edge ≥ 10% | Skip |
| GG2 | \|proj - line\| / σ > 1.5 | Skip |
| GG3 | edge ≤ 0 | Skip |
| GG4 | missing both sides | Skip |

---

## WORKFLOW

1. Load projections
2. Pull odds (both sides, all markets)
3. Validate data (reject bad proj/odds)
4. Calculate prob + edge for everything
5. Apply gates
6. Filter by tier thresholds
7. Check PP eligibility
8. Size with VAKE
9. Output

---

## CHECKLIST

**Per game:**
- [ ] T1 props: O + U
- [ ] PTS props: O + U
- [ ] Spread: both sides
- [ ] Total: O + U
- [ ] Team totals: both teams
- [ ] 1H/1P if available
- [ ] Alts if main shows edge

---

## OUTPUT

**PP:**
```
PP | [Player] [O/U][Line] [Stat] @ [Odds] [Book]
Win: XX.X% | Edge: X.X% | Proj: X.XX
```

**Discord:**
```
X.Xu | [Player/Game] [O/U][Line] @ [Odds]
Win: XX.X% | Edge: X.X%
```

---

## RULES

1. No live betting
2. No college player props (CO law)
3. Re-pull odds if >30 min stale
4. Skip > force
5. Gates protect you — trust them
6. 20%+ prop edge = model error
7. 10%+ game edge = suspicious

---

## API

```
Key: 26dbce04228456d91b67384e7b2f86be
URL: https://api.the-odds-api.com/v4
Books: draftkings,fanduel,betmgm,caesars
```
