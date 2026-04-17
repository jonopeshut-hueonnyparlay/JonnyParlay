# MASTER BETTING PROMPT v7.3

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
| T1 | AST, REB, SOG, REC | Yes | 1% |
| T2 | PTS, Yards, Totals, Spreads, Team Totals, ML Fav | No | 2% |
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

| Exposure | Value |
|----------|-------|
| 1st bet on stat type | 1.00 |
| 2nd+ bet on stat type | 0.70 |

**Caps (per day):**
- Props: 2/stat (NBA), 6/stat (NHL SOG), 2/game
- Totals: 4, Spreads: 4, Team Totals: 4
- Sport: NBA 10u, NHL 6u, NFL 8u
- Daily: 30u

---

## PROJECTION FILES

**Required format:** SaberSim CSV export

**NBA columns:** `Name, Team, Opp, Saber Total, Saber Team, AST, RB, PTS, 3PT`
**NHL columns:** `Name, Team, Opp, Saber Total, Saber Team, SOG, A`
**NFL columns:** `Name, Team, Opp, Saber Total, Saber Team, REC, Yards`

- `Saber Total` = projected game total
- `Saber Team` = projected team total

---

## VALIDATION

Before calculation:
```
proj ≤ 0        → Skip
odds = 0        → Skip
missing side    → Skip
```

**⚠️ ODDS FORMAT CHECK:** If odds are between 1.0 and 3.0, they're decimal not American. Re-fetch with `oddsFormat=american`.

---

## ODDS

**Implied (American):**
```
Negative: |odds| / (|odds| + 100)
Positive: 100 / (odds + 100)
```

**No-Vig:**
```
nv_1 = implied_1 / (implied_1 + implied_2)
nv_2 = implied_2 / (implied_1 + implied_2)
```

**Best book:** Use `max(odds)` across all books for each side.

---

## PROPS

**Distribution:**
```
IF stat in [AST, REB, SOG, REC] AND line ≤ 4.5:
    USE Poisson: k = floor(line)
    Under = poisson.cdf(k, proj)
    Over  = 1 - poisson.cdf(k, proj)
ELSE:
    USE Normal: sigma = max(proj × mult, min_sigma)
    Under = norm.cdf(line, proj, sigma)
    Over  = 1 - norm.cdf(line, proj, sigma)
```

| Stat | Mult | Min σ | Tier |
|------|------|-------|------|
| AST | 0.45 | 1.2 | T1 |
| REB | 0.40 | 1.8 | T1 |
| SOG | 0.55 | 1.0 | T1 |
| REC | 0.50 | 1.2 | T1 |
| PTS | 0.35 | 4.5 | T2 |
| Yards | 0.30 | 15.0 | T2 |
| 3PM | 0.50 | 0.8 | T3 |

---

## GAME LINES

### Totals
```
proj = Saber Total
sigma = sport_sigma['total']
Over  = 1 - norm.cdf(line, proj, sigma)
Under = norm.cdf(line, proj, sigma)
```

### Team Totals
```
proj = Saber Team
sigma = sport_sigma['team']
Over  = 1 - norm.cdf(line, proj, sigma)
Under = norm.cdf(line, proj, sigma)
```

### Spreads
```
margin = home_team_proj - away_team_proj
sigma = sport_sigma['spread']
home_covers = 1 - norm.cdf(home_spread, margin, sigma)
away_covers = 1 - home_covers
```

### Moneylines
```
margin = team_proj - opp_proj
win_prob = 1 - norm.cdf(0, margin, sigma)
```
Favorite = T2, Underdog = T3

### Alt Lines
Same formulas, different line. Only bet if `alt_edge > main_edge + 2%`

| Sport | Total σ | Spread σ | Team σ |
|-------|---------|----------|--------|
| NBA | 12.0 | 12.0 | 9.0 |
| NHL | 1.2 | 1.5 | 1.0 |
| NFL | 10.0 | 13.5 | 7.5 |

---

## EDGE

```
edge = model_prob - novig_prob
```

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

## DEDUPLICATION

Group by `(player, stat, line, direction)`. Keep entry with highest edge.

---

## TEAM MATCHING

Map API names to abbreviations:

**NBA:**
```python
{'Cavaliers': 'CLE', 'Celtics': 'BOS', 'Heat': 'MIA', 'Lakers': 'LAL',
 'Warriors': 'GSW', 'Suns': 'PHX', 'Pistons': 'DET', 'Bucks': 'MIL',
 'Spurs': 'SAS', 'Thunder': 'OKC', 'Rockets': 'HOU', 'Mavericks': 'DAL',
 'Jazz': 'UTA', 'Hawks': 'ATL', 'Blazers': 'POR', 'Knicks': 'NYK',
 'Hornets': 'CHA', '76ers': 'PHI', 'Pelicans': 'NOP', 'Pacers': 'IND',
 'Bulls': 'CHI', 'Nets': 'BKN', 'Clippers': 'LAC', 'Raptors': 'TOR',
 'Timberwolves': 'MIN', 'Magic': 'ORL', 'Grizzlies': 'MEM', 'Kings': 'SAC',
 'Nuggets': 'DEN', 'Wizards': 'WAS'}
```

**NHL:**
```python
{'Bruins': 'BOS', 'Sabres': 'BUF', 'Canadiens': 'MTL', 'Canucks': 'VAN',
 'Blue Jackets': 'CBJ', 'Flyers': 'PHI', 'Penguins': 'PIT', 'Capitals': 'WSH',
 'Kraken': 'SEA', 'Jets': 'WPG', 'Wild': 'MIN', 'Flames': 'CGY',
 'Blackhawks': 'CHI', 'Stars': 'DAL', 'Oilers': 'EDM', 'Islanders': 'NYI',
 'Maple Leafs': 'TOR', 'Golden Knights': 'VGK', 'Panthers': 'FLA',
 'Hurricanes': 'CAR', 'Red Wings': 'DET', 'Lightning': 'TBL', 'Blues': 'STL',
 'Predators': 'NSH', 'Avalanche': 'COL', 'Ducks': 'ANA', 'Kings': 'LAK',
 'Sharks': 'SJS', 'Coyotes': 'ARI', 'Senators': 'OTT', 'Devils': 'NJD',
 'Rangers': 'NYR'}
```

---

## API REFERENCE

```
Key: 26dbce04228456d91b67384e7b2f86be
URL: https://api.the-odds-api.com/v4
Books: draftkings,fanduel,betmgm,caesars
```

**⚠️ CRITICAL: Always include `&oddsFormat=american` in ALL odds calls.**

### Sport Keys
| Sport | Key |
|-------|-----|
| NBA | `basketball_nba` |
| NHL | `icehockey_nhl` |
| NFL | `americanfootball_nfl` |

### Endpoints

**1. Get Events (list games):**
```
GET /sports/{sport}/events?apiKey={key}
```

**2. Get Game Lines (totals, spreads, ML):**
```
GET /sports/{sport}/odds?apiKey={key}&regions=us&markets=totals,spreads,h2h&bookmakers={books}&oddsFormat=american
```

**3. Get Player Props (per event):**
```
GET /sports/{sport}/events/{eventId}/odds?apiKey={key}&regions=us&markets={market}&bookmakers={books}&oddsFormat=american
```

**4. Get Team Totals (per event, NBA only):**
```
GET /sports/{sport}/events/{eventId}/odds?apiKey={key}&regions=us&markets=team_totals&bookmakers={books}&oddsFormat=american
```

**5. Get Alt Lines:**
```
GET /sports/{sport}/odds?apiKey={key}&regions=us&markets=alternate_totals,alternate_spreads&bookmakers={books}&oddsFormat=american
```

### Available Markets

| Market | NBA | NHL | NFL |
|--------|-----|-----|-----|
| `totals` | ✓ | ✓ | ✓ |
| `spreads` | ✓ | ✓ | ✓ |
| `h2h` | ✓ | ✓ | ✓ |
| `team_totals` | ✓ | ✗ | ✗ |
| `alternate_totals` | ✓ | ✓ | ✓ |
| `alternate_spreads` | ✓ | ✓ | ✓ |
| `player_assists` | ✓ | ✓ | — |
| `player_rebounds` | ✓ | — | — |
| `player_points` | ✓ | ✓ | — |
| `player_threes` | ✓ | — | — |
| `player_shots_on_goal` | — | ✓ | — |
| `player_receptions` | — | — | ✓ |
| `player_reception_yds` | — | — | ✓ |
| `player_rush_yds` | — | — | ✓ |
| `player_pass_yds` | — | — | ✓ |
| `player_anytime_td` | — | — | ✓ |

**NOT available:** `goalie_saves`, `1st_half`, `1st_period`

---

## WORKFLOW

1. Load projections
2. Verify slate matches API games
3. Pull odds with `oddsFormat=american`
4. Validate (check for decimal odds bug)
5. Match player/team names
6. Calculate prob + edge (both sides)
7. Apply gates
8. Deduplicate
9. Filter by tier thresholds
10. Sort by edge descending
11. Apply caps
12. Size with VAKE
13. Output

---

## OUTPUT FORMAT

**Props:**
```
X.Xu | [Player] [O/U][Line] [Stat] @ [Odds] [Book]
Win: XX.X% | Edge: X.X% | Proj: X.XX
```

**Game Lines:**
```
X.Xu | [Game] [O/U][Line] [Type] @ [Odds] [Book]
Win: XX.X% | Edge: X.X% | Proj: XXX.X
```

---

## SANITY CHECKS

After generating picks, verify:

1. **Mix of favorites and underdogs** — All plus money = odds format bug
2. **Mix of overs and unders** — All same direction = bias
3. **Edges are 5-15%** — Not 50%+
4. **Win probs are 55-70%** — Not 90%+
5. **Slate matches** — Projection teams match API games

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

## CHANGELOG

**v7.3:**
- Added spreads, team totals, ML, alt lines
- Added NFL receptions market
- Documented all available API markets
- Added team matching dictionaries
- Clarified team_totals needs event endpoint (NBA only)
- Added slate matching to sanity checks

**v7.2:**
- Added projection file requirements
- Added deduplication logic
- Added sanity checks section

**v7.1:**
- Added `&oddsFormat=american` requirement (CRITICAL)
- Increased NHL SOG cap to 6
- Added odds format validation
