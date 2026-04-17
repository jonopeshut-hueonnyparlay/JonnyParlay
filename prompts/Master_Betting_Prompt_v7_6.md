# MASTER BETTING PROMPT v7.6

## STATUS
```
PP Record:    0-0
PP Cushion:   $100.00
PP Mode:      STANDARD
Discord Unit: $10 (1u = $10)
Timezone:     MT (Mountain)
```

---

## MANDATORY OUTPUT REQUIREMENTS

⚠️ **EVERY ANALYSIS MUST INCLUDE:**
1. **Player Props** - AST, REB, SOG, REC, PTS, 3PM, Yards (per sport)
2. **Game Totals** - Over/Under on game totals
3. **Team Totals** - Over/Under on team totals (NBA only)
4. **Spreads** - Point spreads / Puck lines
5. **Moneylines** - Straight up winners

**NEVER skip game lines. NEVER output props only. ALWAYS analyze everything.**

---

## PRE-LOCK CHECKLIST

⚠️ **BEFORE PLACING ANY BET:**

- [ ] Odds still valid (re-pull if >30 min stale)
- [ ] Starting lineups confirmed
- [ ] No late injury news (check Twitter, Rotowire)
- [ ] Goalie confirmed (NHL)
- [ ] No surprise scratches
- [ ] Weather check (outdoor sports)
- [ ] Line hasn't moved significantly against you

**If any check fails → Re-evaluate or skip the bet**

---

## INJURY/NEWS CHECK

**Required sources (check within 30 min of lock):**
- Twitter: @Underdog__NBA, @FantasyLabsNBA, @FantasyLabsNHL
- Rotowire injury reports
- Team official accounts
- ESPN/Yahoo injury updates
- Daily Faceoff (NHL goalies)

**Red flags to watch:**
- "Questionable" upgraded to "Out"
- Minutes restriction announced
- Backup goalie starting
- Load management
- Illness (non-injury)
- GTD with no update close to lock

**Action if news breaks:**
- Prop on affected player → VOID/Skip
- Game line affected → Re-calculate with new projection
- Correlated prop affected → Re-evaluate
- Teammate boost → Potential new value

---

## LINE MOVEMENT TRACKING

**Track opening vs current:**
```
Opening: Team -3 -110
Current: Team -5 -110
Move: 2 points toward Team (sharp action)
```

**Types of movement:**

| Movement | Meaning | Action |
|----------|---------|--------|
| Line moves toward your side | Sharp money agrees | Confidence boost |
| Line moves away from your side | Sharp money disagrees | Re-evaluate |
| Reverse line movement (RLM) | Line moves opposite of ticket % | Potential sharp fade |
| Steam move | 1+ point in <5 min | Sharp action confirmed |

**RLM Example:**
- 75% of tickets on Team A
- Line moves from A -3 to A -2.5
- Sharps are on Team B despite public on A

**Best practice:**
- Note line at time of pick
- Check line at lock
- Track CLV (Closing Line Value) post-game
- If edge shrinks below threshold after move, skip

---

## KEY NUMBERS

**NFL/CFB:**
| Number | Why |
|--------|-----|
| 3 | Field goal margin (most common) |
| 7 | Touchdown margin |
| 6 | TD without extra point |
| 10 | TD + FG |
| 14 | Two touchdowns |

**Premium for moving off/onto key numbers:**
- Buying from -3 to -2.5 = worth extra juice
- Selling from +7 to +7.5 = less valuable

**NBA:**
| Number | Why |
|--------|-----|
| 5, 6, 7 | Common final margins |
| 3 | Less important than NFL |

**NHL:**
- 1.5 puck line is standard
- Most games decided by 1-2 goals
- Rarely bet alt puck lines

---

## MAX EXPOSURE PER PLAYER

**Limits:**
- Max 2 props on same player
- If 2 props on same player → reduce 2nd bet by 30%
- Never 3+ props on same player

**Example:**
```
Player A Over 6.5 AST → 1.5u (full size)
Player A Over 22.5 PTS → 1.05u (reduced 30%)
Player A Over 1.5 3PM → SKIP (would be 3rd prop)
```

**Correlated exposure:**
- Same game props count toward exposure
- Track total units per game (max 2u per game for props)
- Max 4 bets touching same game across all markets

---

## BOOK PRIORITY

**Best books by market:**

| Market | 1st Choice | 2nd Choice | Avoid |
|--------|------------|------------|-------|
| NBA Props | FanDuel | DraftKings | Caesars |
| NHL SOG | FanDuel | DraftKings | BetMGM |
| NFL Props | DraftKings | FanDuel | — |
| NBA Totals | BetMGM | DraftKings | — |
| NHL Totals | DraftKings | FanDuel | — |
| Spreads | DraftKings | FanDuel | — |
| MLs | Best odds | Shop all | — |
| SGPs | DraftKings | FanDuel | — |
| Alt Lines | DraftKings | FanDuel | — |

**Juice shopping:**
- Always compare across all 4 books
- -105 vs -115 = significant over time
- +EV can disappear with bad juice

**Line shopping priority:**
```
1. Find best odds for your side
2. Check if alt line has better EV
3. Verify both sides are available
4. Place bet at best number
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

## DISCORD OUTPUT FORMAT

**Props:**
```
[Player] [over/under] [line] [stat] [odds] [units]u
```
Examples:
- `Jabari Walker under 3.5 rebounds -111 2u`
- `Duncan Robinson over 1.5 assists -105 2u`
- `Tony DeAngelo under 1.5 shots on goal +126 2u`

**Game Totals:**
```
[Away]/[Home] [Over/Under] [line] [odds] [units]u
```
Examples:
- `Flames/Devils Over 5.5 -125 1.2u`
- `Pacers/76ers Over 226.5 -114 1.2u`
- `Heat/Warriors Under 239.5 -110 1u`

**Spreads:**
```
[Team] [spread] [odds] [units]u
```
Examples:
- `Pistons -2.5 -110 1.2u`
- `Celtics +2.5 -110 1u`
- `Devils -1.5 +198 0.5u`

**Moneylines:**
```
[Team] ML [odds] [units]u
```
Examples:
- `Warriors ML -200 0.8u`
- `Rangers ML +116 0.6u`
- `Canucks ML +120 0.5u`

---

## PARLAY FORMATS

### Alt Spread Parlay (3-leg)
**Goal:** ~-110 to +130 combined odds

**Selection criteria:**
1. Pick 3 strongest favorites of the day
2. Move each spread 2-4 points in favorite's direction
3. Target individual leg odds: -200 to -300 each

**Example:**
```
🏀 ALT SPREAD PARLAY

Warriors -1.5 (alt from -4.5)
76ers -2.5 (alt from -5.5)
Suns -5.5 (alt from -9.5)

3-leg parlay ~+110
```

### Same Game Parlay (SGP)
**Best games for SGP:**
- High totals (more stats)
- Clear favorite (predictable flow)
- Star players on both sides

**Correlation rules:**
- Team win + player stats from that team = positive correlation
- High pace game + overs = positive correlation
- Blowout potential + bench players = negative correlation

**5-leg SGP template:**
```
1. Game outcome (ML or spread)
2. Star player points/assists
3. Opposing star player stat
4. Role player high-floor prop
5. Another role player or total
```

**Target odds:** +300 to +450 for 5-leg

---

## SAFETY/VARIANCE RANKING

When ranking picks by safety (lowest variance/volatility):

**Safest characteristics:**
- Negative odds (favorites) over plus odds (underdogs)
- Higher win probability = safer
- T1 stats (AST, REB, SOG, REC) = lowest variance
- T2 stats = medium variance
- T3 stats = highest variance
- PP eligible picks = passed strictest gates
- Odds range -105 to -130 = most stable payouts

**Ranking priority for "safest" picks:**
1. Win probability (higher = safer)
2. Odds (favorites over underdogs)
3. Tier (T1 > T2 > T3)
4. Edge (higher edge with above criteria = better)

**Riskiest characteristics:**
- Plus odds (underdogs)
- Lower win probability
- T3 stats (TDs, Goals, 3PM)
- High variance game situations

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
| CFB | 10.0 | 13.5 | 7.5 |
| NCAAB | 11.0 | 11.0 | 8.0 |

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
 'Jazz': 'UTA', 'Hawks': 'ATL', 'Blazers': 'POR', 'Trail Blazers': 'POR',
 'Knicks': 'NYK', 'Hornets': 'CHA', '76ers': 'PHI', 'Pelicans': 'NOP',
 'Pacers': 'IND', 'Bulls': 'CHI', 'Nets': 'BKN', 'Clippers': 'LAC',
 'Raptors': 'TOR', 'Timberwolves': 'MIN', 'Magic': 'ORL', 'Grizzlies': 'MEM',
 'Kings': 'SAC', 'Nuggets': 'DEN', 'Wizards': 'WAS'}
```

**NHL:**
```python
{'Bruins': 'BOS', 'Sabres': 'BUF', 'Canadiens': 'MTL', 'Canucks': 'VAN',
 'Blue Jackets': 'CBJ', 'Flyers': 'PHI', 'Penguins': 'PIT', 'Capitals': 'WSH',
 'Kraken': 'SEA', 'Jets': 'WPG', 'Wild': 'MIN', 'Flames': 'CGY',
 'Blackhawks': 'CHI', 'Stars': 'DAL', 'Oilers': 'EDM', 'Islanders': 'NYI',
 'Maple Leafs': 'TOR', 'Golden Knights': 'VGK', 'Vegas Golden Knights': 'VGK',
 'Panthers': 'FLA', 'Hurricanes': 'CAR', 'Red Wings': 'DET', 'Lightning': 'TBL',
 'Blues': 'STL', 'Predators': 'NSH', 'Avalanche': 'COL', 'Ducks': 'ANA',
 'Kings': 'LAK', 'Sharks': 'SJS', 'Coyotes': 'ARI', 'Utah Hockey Club': 'UTA',
 'Senators': 'OTT', 'Devils': 'NJD', 'Rangers': 'NYR'}
```

**NFL:**
```python
{'Cardinals': 'ARI', 'Falcons': 'ATL', 'Ravens': 'BAL', 'Bills': 'BUF',
 'Panthers': 'CAR', 'Bears': 'CHI', 'Bengals': 'CIN', 'Browns': 'CLE',
 'Cowboys': 'DAL', 'Broncos': 'DEN', 'Lions': 'DET', 'Packers': 'GB',
 'Texans': 'HOU', 'Colts': 'IND', 'Jaguars': 'JAX', 'Chiefs': 'KC',
 'Raiders': 'LV', 'Chargers': 'LAC', 'Rams': 'LAR', 'Dolphins': 'MIA',
 'Vikings': 'MIN', 'Patriots': 'NE', 'Saints': 'NO', 'Giants': 'NYG',
 'Jets': 'NYJ', 'Eagles': 'PHI', 'Steelers': 'PIT', 'Seahawks': 'SEA',
 '49ers': 'SF', 'Buccaneers': 'TB', 'Titans': 'TEN', 'Commanders': 'WAS'}
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
| NCAAF | `americanfootball_ncaaf` |
| NCAAB | `basketball_ncaab` |

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

⚠️ **MUST COMPLETE ALL STEPS - NO SKIPPING**

1. Load projections
2. Verify slate matches API games
3. Pull odds with `oddsFormat=american`
4. Validate (check for decimal odds bug)
5. Match player/team names
6. **PROPS:** Calculate prob + edge for all prop markets
7. **GAME TOTALS:** Calculate prob + edge for all totals
8. **SPREADS:** Calculate prob + edge for all spreads
9. **MONEYLINES:** Calculate prob + edge for all MLs
10. **TEAM TOTALS:** Calculate prob + edge (NBA only)
11. Apply gates
12. Deduplicate
13. Filter by tier thresholds
14. Check max exposure per player
15. Sort by edge descending
16. Apply caps
17. Size with VAKE
18. Output ALL picks (props + game lines)
19. Generate Discord copy/paste format
20. Identify top 5 safest picks
21. Run sanity checks

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

**Discord Format (copy/paste ready):**
```
Props: [Player] [over/under] [line] [stat] [odds] [units]u
Totals: [Away]/[Home] [Over/Under] [line] [odds] [units]u
Spreads: [Team] [spread] [odds] [units]u
MLs: [Team] ML [odds] [units]u
```

---

## SANITY CHECKS

After generating picks, verify:

1. **Mix of favorites and underdogs** — All plus money = odds format bug
2. **Mix of overs and unders** — All same direction = bias
3. **Edges are 5-15%** — Not 50%+
4. **Win probs are 55-70%** — Not 90%+
5. **Slate matches** — Projection teams match API games
6. **PROPS PRESENT** — Must have player props in output
7. **GAME LINES PRESENT** — Must have totals/spreads/MLs in output
8. **Max exposure check** — No player with 3+ props
9. **Injury check done** — All players confirmed active

---

## RULES

1. No live betting
2. No college player props (CO law)
3. Re-pull odds if >30 min stale
4. Skip > force
5. Gates protect you — trust them
6. 20%+ prop edge = model error
7. 10%+ game edge = suspicious
8. **ALWAYS output props AND game lines**
9. Max 2 props per player
10. Run pre-lock checklist before betting
11. Track results daily for model calibration

---

## RESULT TRACKING FORMAT

**Daily log:**
```
Date: YYYY-MM-DD
Sport | Pick | Odds | Units | Result | P/L
NBA | Curry O5.5 AST | -147 | 1.5u | W | +1.02u
NHL | TOR/MIN U6.5 | -110 | 1.0u | L | -1.0u
...
Daily P/L: +X.XXu
Rolling: +XX.Xu (X-X record)
```

**Weekly summary:**
```
Week of MM/DD - MM/DD
Props: X-X (+X.Xu)
Game Lines: X-X (+X.Xu)
Total: X-X (+X.Xu)
ROI: X.X%
CLV: +X.X%
```

---

## CHANGELOG

**v7.6:**
- Added PARLAY FORMATS section (alt spread parlay + SGP)
- Added NFL team matching dictionary
- Added CFB/NCAAB sigma values
- Added RESULT TRACKING FORMAT section
- Expanded workflow to 21 steps
- Added Daily Faceoff to injury sources
- Added correlation rules for SGP

**v7.5:**
- Added PRE-LOCK CHECKLIST section
- Added INJURY/NEWS CHECK section
- Added LINE MOVEMENT TRACKING section
- Added KEY NUMBERS section (NFL/NBA/NHL)
- Added MAX EXPOSURE PER PLAYER section
- Added BOOK PRIORITY section
- Added max exposure check to sanity checks
- Added rules 9-10

**v7.4:**
- Added MANDATORY OUTPUT REQUIREMENTS section
- Added DISCORD OUTPUT FORMAT section with exact formatting
- Added SAFETY/VARIANCE RANKING section
- Added emphasis on ALWAYS including game lines
- Added sanity checks for props and game lines present
- Added NCAAF and NCAAB sport keys

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
