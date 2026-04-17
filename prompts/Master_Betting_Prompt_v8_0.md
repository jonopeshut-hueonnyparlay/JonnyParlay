# MASTER BETTING PROMPT v8.0

## STATUS
```
PP Record:    0-0
PP Cushion:   $100.00
PP Mode:      AGGRESSIVE
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

## CLV TRACKING (NEW - CRITICAL)

⚠️ **TRACK ON EVERY BET:**

```
Bet Placed: [Player] [O/U][Line] [Stat] @ [Odds] [Book]
Time Placed: [HH:MM] MT
Closing Line: [Odds] @ Pinnacle (or sharpest available)
CLV: [+/- cents]
```

**CLV Calculation:**
```
If you bet -147 and it closes -170:
CLV = implied_close - implied_bet
    = 0.6296 - 0.5952 = +3.44 cents (+$0.034 per $1 risked)
```

**Weekly CLV Report (generate every Sunday):**
```
📊 WEEKLY CLV REPORT
Week: MM/DD - MM/DD
Total Bets: XX
Record: X-X (XX.X%)
Positive CLV Bets: XX (XX%)
Negative CLV Bets: XX (XX%)
Average CLV: +X.X cents
Implied Long-term ROI: X.X%
```

**Why CLV matters:** CLV is the single best predictor of long-term profitability. A bettor with +3% average CLV will be profitable regardless of short-term W/L variance. Track it religiously.

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
- [ ] CLV tracking fields ready

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

**Line Movement Decision Tree:**
```
Line moves TOWARD your side (sharp money agrees):
├── Edge still meets threshold? → Bet with confidence
└── Edge below threshold? → Still bet at reduced size (0.75x)

Line moves AWAY from your side (sharp money disagrees):
├── Move < 0.5 pts? → Proceed if edge still meets threshold
├── Move 0.5-1 pt? → Re-evaluate, reduce size by 25%
└── Move > 1 pt? → SKIP (you missed the number)

Reverse Line Movement (RLM) detected:
├── Sharps on opposite side → Strong skip signal
└── Exception: You have proprietary info (injury, etc.)
```

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
| Number | Why | CLV Value |
|--------|-----|-----------|
| 3 | Field goal margin (most common) | ~16% when crossed |
| 7 | Touchdown margin | ~10% when crossed |
| 6 | TD without extra point | ~5% |
| 10 | TD + FG | ~5% |
| 14 | Two touchdowns | ~3% |

**Premium for moving off/onto key numbers:**
- Buying from -3 to -2.5 = worth extra juice (major value)
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
Player A Over 6.5 AST → 1.0u (full size)
Player A Over 22.5 PTS → 0.7u (reduced 30%)
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
- -105 vs -115 = significant over time (~1% edge difference)
- +EV can disappear with bad juice

**Line shopping is NON-NEGOTIABLE.** Check all 4 books on EVERY bet.

---

## BETTING TIMING (NEW)

**Optimal bet windows:**

| Market | Best Time | Why |
|--------|-----------|-----|
| NBA Props | 2-4 hours pre-game | After lineups, before sharp steam |
| NHL Props | After goalie confirm (~10am ET) | Massive swing on goalie news |
| NFL Props | Thursday-Saturday | Before Sunday sharp action |
| Game Totals | Morning of game | Weather/injury priced in |
| Spreads | When you have best number | Varies by game |

**Early week vs game day:**
- Early week = potentially better numbers, more uncertainty
- Game day = more information, tighter lines
- Props = game day (after lineup confirmation)

---

## ALLOCATION (UPDATED)

**Daily allocation by market:**

| Market | Allocation | Why |
|--------|------------|-----|
| Props (T1 + T2) | **60%** | Most inefficient market |
| Game Lines | 25% | More efficient, less edge |
| SGPs/Parlays | 15% | High variance, use sparingly |

**Props are where edge lives.** Books cap them at $100-500 while accepting $10k+ on sides. They're telling you where they're vulnerable.

---

## TIERS (UPDATED)

| Tier | Stats | PP Eligible | Min Edge | Max Daily |
|------|-------|-------------|----------|-----------|
| T1 | AST, REB, SOG, REC | Yes | 1% | 8 bets |
| T2 | PTS, Yards, Totals, Spreads, Team Totals, ML Fav | No | 2% | 4 bets |
| T3 | TDs, Goals, 3PM, ML Dog | No | 5% | 2 bets |

Direction (over/under) does not affect tier.

**NEW: Daily limits per tier** prevent overexposure to high-variance markets.

---

## PLAYERPROFIT (UPDATED)

**Eligible:** T1 stats, over or under

| Cushion | Mode | Bet Size | Win% | Edge | Odds | Daily Max |
|---------|------|----------|------|------|------|-----------|
| <$15 | CRITICAL | PAUSE | — | — | — | 0 |
| $15-30 | SURVIVAL | $8 | ≥62% | ≥6% | -105 to -170 | 1 |
| $30-50 | CAUTIOUS | $10 | ≥60% | ≥5% | -105 to -180 | 1 |
| $50-75 | STANDARD | $10 | ≥58% | ≥4% | -105 to -200 | 2 |
| $75-100 | COMFORTABLE | $12 | ≥56% | ≥3% | -105 to -220 | 2 |
| $100+ | AGGRESSIVE | $15 | ≥55% | ≥2% | -105 to -250 | 3 |

**Rules:**
- Both sides odds required
- All gates must pass
- Loss = stop for day (in SURVIVAL/CAUTIOUS modes)
- No live bets
- T1 stats only

---

## DISCORD (UPDATED - Conservative Sizing)

**Unit:** $10 (adjust to your bankroll as 1% of total)

| Edge | Units |
|------|-------|
| 1-2% | 0.25u |
| 2-3.5% | 0.5u |
| 3.5-5% | 0.75u |
| 5-7% | 1.0u |
| 7-10% | 1.25u |
| 10-15% | 1.5u |
| 15-20% | 1.75u |

**Why reduced:** Research shows quarter-to-half Kelly outperforms full Kelly long-term. Reduces volatility while only marginally reducing growth.

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
- Sport: NBA 8u, NHL 5u, NFL 6u
- Daily: 25u

---

## DISCORD OUTPUT FORMAT

**Props:**
```
[Player] [over/under] [line] [stat] [odds] [units]u
```
Examples:
- `Jabari Walker under 3.5 rebounds -111 1u`
- `Duncan Robinson over 1.5 assists -105 0.75u`
- `Tony DeAngelo under 1.5 shots on goal +126 0.5u`

**Game Totals:**
```
[Away]/[Home] [Over/Under] [line] [odds] [units]u
```
Examples:
- `Flames/Devils Over 5.5 -125 0.75u`
- `Pacers/76ers Over 226.5 -114 1u`

**Spreads:**
```
[Team] [spread] [odds] [units]u
```
Examples:
- `Pistons -2.5 -110 0.75u`
- `Celtics +2.5 -110 0.5u`

**Moneylines:**
```
[Team] ML [odds] [units]u
```
Examples:
- `Warriors ML -200 0.5u`
- `Rangers ML +116 0.25u`

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

⚠️ **ALWAYS compare SGP pricing across 4+ books.** Same SGP can pay +369 at FanDuel vs +580 at Caesars.

**Best games for SGP:**
- High totals (more stats)
- Clear favorite (predictable flow)
- Star players on both sides

**Correlation rules:**
| Combo | Correlation | Action |
|-------|-------------|--------|
| Team win + player stats (same team) | Positive | Full size |
| Over + offensive player stats | Positive | Full size |
| Under + defensive metrics | Positive | Full size |
| High pace game + overs | Positive | Full size |
| Player A pts + Player B pts (same team) | **Negative** | Reduce 30% |
| Blowout potential + bench players | **Negative** | Avoid |

**5-leg SGP template:**
```
1. Game outcome (ML or spread)
2. Star player points/assists
3. Opposing star player stat
4. Role player high-floor prop
5. Another role player or total
```

**Target odds:** +300 to +450 for 5-leg
**Max SGP allocation:** 15% of daily action

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
| G2 | edge ≥ 20% | Skip (model error) |
| G3 | missing both sides | Skip |
| G4 | line ≤ 2.5 AND prob > 75% | Skip |
| G5 | odds > 0 AND prob > 65% | Skip |

**Game Lines:**
| Gate | Trigger | Action |
|------|---------|--------|
| GG1 | edge ≥ 10% | Skip (suspicious) |
| GG2 | |proj - line| / σ > 1.5 | Skip |
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
15. **Check daily limits per tier (NEW)**
16. Sort by edge descending
17. Apply caps
18. Size with VAKE (updated conservative sizing)
19. Output ALL picks (props + game lines)
20. Generate Discord copy/paste format
21. Identify top 5 safest picks
22. Run sanity checks
23. **Prepare CLV tracking fields (NEW)**

---

## OUTPUT FORMAT

**Props:**
```
X.Xu | [Player] [O/U][Line] [Stat] @ [Odds] [Book]
Win: XX.X% | Edge: X.X% | Proj: X.XX
CLV: [track post-close]
```

**Game Lines:**
```
X.Xu | [Game] [O/U][Line] [Type] @ [Odds] [Book]
Win: XX.X% | Edge: X.X% | Proj: XXX.X
CLV: [track post-close]
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
10. **Daily tier limits** — T1 ≤8, T2 ≤4, T3 ≤2 (NEW)
11. **Allocation check** — ~60% props, ~25% game lines, ~15% SGP (NEW)

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
12. **Track CLV on every bet (NEW)**
13. **Line shop every bet across 4 books (NEW)**
14. **Respect daily tier limits (NEW)**

---

## RESULT TRACKING FORMAT

**Daily log:**
```
Date: YYYY-MM-DD
Sport | Pick | Odds | Units | Result | P/L | CLV
NBA | Curry O5.5 AST | -147 | 1.0u | W | +0.68u | +3.4c
NHL | TOR/MIN U6.5 | -110 | 0.75u | L | -0.75u | -1.2c
...
Daily P/L: +X.XXu
Rolling: +XX.Xu (X-X record)
Daily CLV: +X.Xc avg
```

**Weekly summary:**
```
Week of MM/DD - MM/DD
Props: X-X (+X.Xu) | Avg CLV: +X.Xc
Game Lines: X-X (+X.Xu) | Avg CLV: +X.Xc
Total: X-X (+X.Xu)
ROI: X.X%
Overall CLV: +X.X%
+CLV Rate: XX%
```

---

## QUICK REFERENCE CARD

```
┌─────────────────────────────────────────────────────────┐
│ DAILY LIMITS                                            │
├─────────────────────────────────────────────────────────┤
│ T1 (AST/REB/SOG/REC): 8 bets max, 1%+ edge             │
│ T2 (PTS/Yards/Lines): 4 bets max, 2%+ edge             │
│ T3 (TD/Goals/3PM):    2 bets max, 5%+ edge             │
│ Total daily:          25u max                           │
├─────────────────────────────────────────────────────────┤
│ ALLOCATION                                              │
├─────────────────────────────────────────────────────────┤
│ Props:      60%                                         │
│ Game Lines: 25%                                         │
│ SGPs:       15%                                         │
├─────────────────────────────────────────────────────────┤
│ PLAYERPROFIT QUICK REF                                  │
├─────────────────────────────────────────────────────────┤
│ $15-30:  $8,  6%+ edge, 1/day                          │
│ $30-50:  $10, 5%+ edge, 1/day                          │
│ $50-75:  $10, 4%+ edge, 2/day                          │
│ $75-100: $12, 3%+ edge, 2/day                          │
│ $100+:   $15, 2%+ edge, 3/day                          │
└─────────────────────────────────────────────────────────┘
```

---

## CHANGELOG

**v8.0 (January 23, 2026) - Research-Validated Update:**
- Added CLV TRACKING section (critical for long-term evaluation)
- Added BETTING TIMING section with optimal windows
- Added ALLOCATION section (60% props, 25% game lines, 15% SGP)
- Added daily limits per tier (T1: 8, T2: 4, T3: 2)
- Updated unit sizing to conservative (quarter-to-half Kelly)
- Added LINE MOVEMENT DECISION TREE
- Added COMFORTABLE tier ($75-100) to PlayerProfit
- Increased PP daily max at higher cushions
- Added CLV value to key numbers table
- Updated caps (reduced from 30u to 25u daily)
- Added allocation check to sanity checks
- Added CLV tracking to result format
- Emphasized line shopping as non-negotiable
- Added SGP correlation table with actions
- Updated workflow to 23 steps

**v7.6:**
- Added PARLAY FORMATS section (alt spread parlay + SGP)
- Added NFL team matching dictionary
- Added CFB/NCAAB sigma values
- Added RESULT TRACKING FORMAT section

**v7.5:**
- Added PRE-LOCK CHECKLIST section
- Added INJURY/NEWS CHECK section
- Added LINE MOVEMENT TRACKING section
- Added KEY NUMBERS section (NFL/NBA/NHL)
- Added MAX EXPOSURE PER PLAYER section
- Added BOOK PRIORITY section

**v7.4:**
- Added MANDATORY OUTPUT REQUIREMENTS section
- Added DISCORD OUTPUT FORMAT section
- Added SAFETY/VARIANCE RANKING section

**v7.3:**
- Added spreads, team totals, ML, alt lines
- Added NFL receptions market
- Documented all available API markets
