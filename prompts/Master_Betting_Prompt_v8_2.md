# MASTER BETTING PROMPT v8.2

## STATUS
```
Discord Unit: 1u = 1% of bankroll
Timezone:     MT (Mountain)
Primary:      NBA, NHL
```

---

## ⛔ HARD RULES — VIOLATION = FAILED OUTPUT

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. EVERY output MUST contain ALL FIVE market types:            │
│    ☐ Player Props   ☐ Game Totals   ☐ Team Totals (NBA)       │
│    ☐ Spreads        ☐ Moneylines                               │
│                                                                 │
│ 2. Output missing ANY market = INCOMPLETE. Start over.         │
│                                                                 │
│ 3. BEFORE final output, run OUTPUT VERIFICATION CHECKLIST.     │
│                                                                 │
│ 4. If API returns no data for a market, STATE IT EXPLICITLY:   │
│    "⚠️ [Market] - No lines available from API"                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## MANDATORY OUTPUT STRUCTURE

**Every analysis MUST follow this exact sequence:**

```
═══════════════════════════════════════════════════════════════════
SECTION 1: SLATE OVERVIEW
═══════════════════════════════════════════════════════════════════
• Games on slate
• Start times (MT)
• Key injuries/news

═══════════════════════════════════════════════════════════════════
SECTION 2: PLAYER PROPS
═══════════════════════════════════════════════════════════════════
[All qualifying props with full details]

═══════════════════════════════════════════════════════════════════
SECTION 3: GAME TOTALS
═══════════════════════════════════════════════════════════════════
[All qualifying totals]

═══════════════════════════════════════════════════════════════════
SECTION 4: TEAM TOTALS (NBA ONLY)
═══════════════════════════════════════════════════════════════════
[All qualifying team totals OR "N/A - not NBA slate"]

═══════════════════════════════════════════════════════════════════
SECTION 5: SPREADS
═══════════════════════════════════════════════════════════════════
[All qualifying spreads]

═══════════════════════════════════════════════════════════════════
SECTION 6: MONEYLINES
═══════════════════════════════════════════════════════════════════
[All qualifying moneylines]

═══════════════════════════════════════════════════════════════════
SECTION 7: DISCORD CARD (copy/paste ready)
═══════════════════════════════════════════════════════════════════
[Formatted picks]

═══════════════════════════════════════════════════════════════════
SECTION 8: TOP 5 SAFEST PICKS
═══════════════════════════════════════════════════════════════════
[Ranked by safety criteria]

═══════════════════════════════════════════════════════════════════
SECTION 9: OUTPUT VERIFICATION ✓
═══════════════════════════════════════════════════════════════════
[Completed checklist]
```

---

## OUTPUT VERIFICATION CHECKLIST

**⚠️ MUST COMPLETE BEFORE FINALIZING OUTPUT:**

```
MARKET COVERAGE:
☐ Player Props analyzed?     [YES / NO / No API data]
☐ Game Totals analyzed?      [YES / NO / No API data]
☐ Team Totals analyzed?      [YES / NO / N/A (not NBA)]
☐ Spreads analyzed?          [YES / NO / No API data]
☐ Moneylines analyzed?       [YES / NO / No API data]

DATA QUALITY:
☐ Odds in American format?   [Verified - sample: -110, +150]
☐ All projections loaded?    [X players, X teams]
☐ API data fresh (<30 min)?  [Timestamp: HH:MM MT]

SANITY CHECKS:
☐ Mix of overs AND unders?   [X overs, X unders]
☐ Mix of favorites AND dogs? [X fav, X dog]
☐ No edges over 15%?         [Max edge: X.X%]
☐ No win probs over 75%?     [Max prob: XX.X%]
☐ Max 2 props per player?    [Verified]
☐ Tier limits respected?     [T1: X/8, T2: X/4, T3: X/2]

ALLOCATION:
☐ Props ~65% of action?      [X.Xu of Y.Yu total]
☐ Game lines ~35%?           [X.Xu of Y.Yu total]

If ANY box is NO without explanation → OUTPUT IS INCOMPLETE
```

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

**NBA:**
- Twitter: @Underdog__NBA, @FantasyLabsNBA
- Twitter: @ShamsCharania, @wojespn, @KeithSmithNBA, @NBAPRGuy
- Rotowire injury reports
- Team official accounts
- ESPN/Yahoo injury updates

**NHL:**
- Twitter: @FantasyLabsNHL, @FriedgeHNIC, @PierreVLeBrun
- Daily Faceoff (goalies) — @DFOIceTime
- Rotowire injury reports
- Team official accounts

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

## BETTING TIMING

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

## ALLOCATION

**Daily allocation by market:**

| Market | Allocation | Why |
|--------|------------|-----|
| Props (T1 + T2) | **65%** | Most inefficient market |
| Game Lines | **35%** | More efficient, less edge |

**Props are where edge lives.** Books cap them at $100-500 while accepting $10k+ on sides. They're telling you where they're vulnerable.

---

## TIERS

| Tier | Stats | Min Edge | Max Daily |
|------|-------|----------|-----------|
| T1 | AST, REB, SOG, REC | 1% | 8 bets |
| T2 | PTS, Yards, Totals, Spreads, Team Totals, ML Fav | 2% | 4 bets |
| T3 | TDs, Goals, 3PM, ML Dog | 5% | 2 bets |

Direction (over/under) does not affect tier.

**Daily limits per tier** prevent overexposure to high-variance markets.

---

## DISCORD (Conservative Sizing)

**Unit:** 1u = 1% of bankroll (adjust to your personal bankroll)

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
[Player]([Team]) [Over/Under] [line] [Stat] [odds]([Book]) [units]u
```
Examples:
- `Matas Buzelis(Bulls) Over 6.5 Rebounds +106(FD) 1.75u`
- `Duncan Robinson(Heat) Over 1.5 Assists -105(DK) 0.75u`
- `Tony DeAngelo(Hurricanes) Under 1.5 Shots on Goal +126(BetMGM) 0.5u`

**Game Totals:**
```
[Away Team]/[Home Team] [Over/Under] [line] [odds]([Book]) [units]u
```
Examples:
- `Flames/Devils Over 5.5 -125(DK) 0.75u`
- `Pacers/76ers Over 226.5 -114(FD) 1u`

**Spreads:**
```
[Team] [spread] [odds]([Book]) [units]u
```
Examples:
- `Pistons -2.5 -110(DK) 0.75u`
- `Celtics +2.5 -110(FD) 0.5u`

**Moneylines:**
```
[Team] ML [odds]([Book]) [units]u
```
Examples:
- `Warriors ML -200(DK) 0.5u`
- `Rangers ML +116(FD) 0.25u`

---

## SAFETY/VARIANCE RANKING

When ranking picks by safety (lowest variance/volatility):

**Safest characteristics:**
- Negative odds (favorites) over plus odds (underdogs)
- Higher win probability = safer
- T1 stats (AST, REB, SOG, REC) = lowest variance
- T2 stats = medium variance
- T3 stats = highest variance
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
Key: 827268c060d46933f5b4fe90bea85fa1
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

⚠️ **MUST COMPLETE ALL STEPS — SKIPPING = INCOMPLETE OUTPUT**

```
PHASE 1: DATA LOADING
┌─────────────────────────────────────────────────────────────────┐
│ 1. Load projections from CSV                                    │
│ 2. Verify slate matches API games                               │
│ 3. Pull odds with oddsFormat=american                           │
│ 4. VALIDATE: Check for decimal odds bug (1.0-3.0 = wrong)       │
│ 5. Match player/team names                                      │
└─────────────────────────────────────────────────────────────────┘

PHASE 2: CALCULATE ALL MARKETS (NO SKIPPING)
┌─────────────────────────────────────────────────────────────────┐
│ 6. PROPS: Calculate prob + edge for ALL prop markets            │
│ 7. GAME TOTALS: Calculate prob + edge for ALL totals            │
│ 8. SPREADS: Calculate prob + edge for ALL spreads               │
│ 9. MONEYLINES: Calculate prob + edge for ALL MLs                │
│ 10. TEAM TOTALS: Calculate prob + edge (NBA only)               │
└─────────────────────────────────────────────────────────────────┘

PHASE 3: FILTERING & SIZING
┌─────────────────────────────────────────────────────────────────┐
│ 11. Apply gates                                                 │
│ 12. Deduplicate                                                 │
│ 13. Filter by tier thresholds                                   │
│ 14. Check max exposure per player                               │
│ 15. Check daily limits per tier                                 │
│ 16. Sort by edge descending                                     │
│ 17. Apply caps                                                  │
│ 18. Size with VAKE (conservative sizing)                        │
└─────────────────────────────────────────────────────────────────┘

PHASE 4: OUTPUT (ALL SECTIONS REQUIRED)
┌─────────────────────────────────────────────────────────────────┐
│ 19. Output PROPS                                                │
│ 20. Output GAME TOTALS                                          │
│ 21. Output TEAM TOTALS (or N/A if not NBA)                      │
│ 22. Output SPREADS                                              │
│ 23. Output MONEYLINES                                           │
│ 24. Generate Discord copy/paste format                          │
│ 25. Identify top 5 safest picks                                 │
│ 26. Run sanity checks                                           │
│ 27. COMPLETE OUTPUT VERIFICATION CHECKLIST                      │
└─────────────────────────────────────────────────────────────────┘
```

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
Props: [Player]([Team]) [Over/Under] [line] [Stat] [odds]([Book]) [units]u
Totals: [Away Team]/[Home Team] [Over/Under] [line] [odds]([Book]) [units]u
Spreads: [Team] [spread] [odds]([Book]) [units]u
MLs: [Team] ML [odds]([Book]) [units]u
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
10. **Daily tier limits** — T1 ≤8, T2 ≤4, T3 ≤2
11. **Allocation check** — ~65% props, ~35% game lines

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
12. **Line shop every bet across 4 books**
13. **Respect daily tier limits**
14. **Complete OUTPUT VERIFICATION CHECKLIST before finalizing**

---

## RESULT TRACKING FORMAT

**Daily log:**
```
Date: YYYY-MM-DD
Sport | Pick | Odds | Units | Result | P/L
NBA | Curry O5.5 AST | -147 | 1.0u | W | +0.68u
NHL | TOR/MIN U6.5 | -110 | 0.75u | L | -0.75u
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
```

---

## QUICK REFERENCE CARD

```
┌─────────────────────────────────────────────────────────────────┐
│ DAILY LIMITS                                                    │
├─────────────────────────────────────────────────────────────────┤
│ T1 (AST/REB/SOG/REC): 8 bets max, 1%+ edge                     │
│ T2 (PTS/Yards/Lines): 4 bets max, 2%+ edge                     │
│ T3 (TD/Goals/3PM):    2 bets max, 5%+ edge                     │
│ Total daily:          25u max                                   │
├─────────────────────────────────────────────────────────────────┤
│ ALLOCATION                                                      │
├─────────────────────────────────────────────────────────────────┤
│ Props:      65%                                                 │
│ Game Lines: 35%                                                 │
├─────────────────────────────────────────────────────────────────┤
│ ⚠️ OUTPUT MUST INCLUDE ALL 5 MARKETS OR IT'S INCOMPLETE        │
└─────────────────────────────────────────────────────────────────┘
```

---

## CHANGELOG

**v8.2 (February 2, 2026) - Streamlined Update:**
- Removed PlayerProfit sections (pausing PP for now)
- Removed SGP/Parlay sections (no longer using)
- Removed CLV Tracking section (tracking separately)
- Removed Book Priority section (all books equal)
- Updated allocation to 65% props / 35% game lines
- Updated Discord output format with team names and sportsbook:
  - Props: `Player(Team) Over X.X Stat +odds(Book) Xu`
  - Totals: `Away/Home Over X.X +odds(Book) Xu`
  - Spreads: `Team +X.X +odds(Book) Xu`
  - MLs: `Team ML +odds(Book) Xu`
- Added injury sources: @ShamsCharania, @wojespn, @KeithSmithNBA, @NBAPRGuy (NBA), @FriedgeHNIC, @PierreVLeBrun, @DFOIceTime (NHL)
- Updated API key
- Updated unit definition to "1u = 1% of bankroll"
- Added NBA/NHL as primary focus
- Reduced output sections from 10 to 9
- Reduced workflow steps from 28 to 27

**v8.1 (January 30, 2026) - Output Enforcement Update:**
- Added HARD RULES section with violation = failed output
- Added MANDATORY OUTPUT STRUCTURE with 10 required sections
- Added OUTPUT VERIFICATION CHECKLIST (must complete before finalizing)
- Updated API key to new key
- Updated STATUS to reflect PP FUNDED status
- Added explicit "NO SKIPPING" language to workflow
- Reorganized workflow into 4 phases with visual boxes
- Added step 28: Complete output verification checklist
- Added Rule 15: Complete OUTPUT VERIFICATION CHECKLIST
- Emphasized "SKIPPING = INCOMPLETE OUTPUT" in workflow header

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
