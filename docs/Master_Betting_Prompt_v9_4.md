# MASTER BETTING PROMPT v9.4
## Discord Premium | Colorado Jurisdiction

---

## SECTION 0: RISK MANAGEMENT (APPLY BEFORE ALL OUTPUT)

These rules override everything below. Apply BEFORE generating picks.

### Hard Rules
| # | Rule | Detail |
|---|------|--------|
| R1 | **Premium card: 5 picks** | Top 5 by **Pick Score** = Premium. Everything else that passes gates still gets output as Full Card. |
| R2 | **Stop loss** | -3.0u on the day → stop. (Manual enforcement, unit-based only.) |
| R3 | **No heavy juice** | Skip any odds ≤ -150 entirely. Skip -140 to -149 unless edge ≥ 9%. |
| R4 | **REB Overs BANNED + U2.5 REB BANNED** | Do not evaluate, calculate, or output any REB Over prop OR any REB Under at line ≤ 2.5. No exceptions. REB Unders at 3.5+ only. |
| R5 | **Sizing cap** | Max 1.25u on any single bet. No exceptions. |

### Soft Rules
| # | Rule | Detail |
|---|------|--------|
| R6 | **Max 3 overs/day** | If 4+ overs qualify, keep top 3 by Pick Score. Applies to Premium card only. |
| R7 | **Max 2 bets per game** | 3rd+ bet on same game → skip. |
| R8 | **T1 props take priority for Premium** | Fill Premium card with T1/T1B props first. Game lines only fill remaining Premium slots. Full Card has no tier priority — output everything. |
| R9 | **Directional balance** | If 3+ overs pass all gates, Premium card must include at least 1 over. Select the highest-PS over to fill one Premium slot. |
| R10 | **Max 2 same-stat same-direction on Premium** | No more than 2 picks sharing both the same stat type AND same direction (e.g., max 2 AST unders on Premium). If 3+ qualify, keep top 2 by Pick Score. |
| R11 | **U2.5 AST BANNED** | Do not evaluate, calculate, or output any AST Under at line ≤ 2.5. No exceptions. v9.3 was "max 1/day" — upgraded to full ban. All-time: 5-8 (38.5%), -3.75u. v9.3: 1/2. Poisson overestimates edge at this line. |
| R12 | **Repeat-player cooldown** | If a player's most recent MBP pick was a LOSS, skip that player's next appearance. Resets after one skip. Does not apply if the loss was 5+ days ago. |

### Pick Score (R1 ranking formula)

```
Pick Score = (Safety_Weight × WinProb_n) + (Edge_Weight × Edge_n)

Where:
  WinProb_n = (WinProb% - 50) / 25 × 100     (normalized: 50% → 0, 75% → 100)
  Edge_n    = Edge% / 20 × 100                (normalized: 5% → 25, 20% → 100)
```

| Mode | Safety Weight | Edge Weight | Use When |
|------|--------------|-------------|----------|
| **Default** | 0.60 | 0.40 | Every day |
| Conservative | 0.70 | 0.30 | Cold streak, protect bankroll |
| Aggressive | 0.45 | 0.55 | Stacked slate, high conviction |

Default mode unless specified in the starter prompt.

Premium card picks are ranked by Pick Score descending, after tier priority (R8), directional balance (R9), and same-stat cap (R10) are applied.

---

## SECTION 1: STATUS

```
Discord Unit: $10 (1u = 1% of bankroll)
Timezone:     MT (Mountain)
Jurisdiction: Colorado
Books:        DraftKings, FanDuel, BetMGM, Caesars
```

---

## SECTION 2: TIERS

| Tier | Stats | Min Edge |
|------|-------|----------|
| T1 | AST, SOG, REC, K (pitcher), HRR (batter) | 3% |
| T1B | REB Unders ONLY (3.5+ lines only — U2.5 REB banned by R4), HITS (batter unders), HA (pitcher unders) | 3% |
| T2 | PTS, Yards, Totals, Spreads, Team Totals, ML Fav, TB, OUTS, ER, F5 Total, F5 Spread, F5 ML | 5% |
| T3 | TDs, Goals, 3PM, ML Dog, NRFI, YRFI | 6% |
| T4 | Golf Outrights (GOLF_WIN) | 8% |

- Direction (over/under) does not affect tier EXCEPT rebounds
- REB Overs are BANNED — do not evaluate regardless of edge
- REB Unders at line ≤ 2.5 are BANNED (R4) — REB Unders at 3.5+ only

---

## SECTION 3: SIZING (VAKE)

### Base Units
| Edge | Size |
|------|------|
| 3-5% | 0.50u |
| 5-7% | 0.75u |
| 7-9% | 1.00u |
| 9%+ | 1.25u |

**Max bet: 1.25u.** No exceptions.

### Multipliers
`final = base × variance × tier × correlation × exposure`

Apply sizing in **Pick Score descending order** — highest-scored picks receive full 1.00 multipliers before diminishing returns apply to lower-ranked picks.

| Multiplier | T1/T1B | T2 | T3 |
|------------|--------|----|----|
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

### Caps (per day)
- Props: 2 per stat type, 2 per game
- NHL SOG: 6 per stat
- Totals: 4, Spreads: 4, Team Totals: 4
- Sport: NBA 8u, NHL 5u
- **Daily: 12u** (hard cap)

---

## SECTION 4: PROJECTION FILES

**Required format:** SaberSim CSV export (encoding: `utf-8-sig`)

**NBA columns:** `Name, Team, Opp, Saber Total, Saber Team, AST, RB, PTS, 3PT`
**NHL columns:** `Name, Team, Opp, Saber Total, Saber Team, SOG, A`
**MLB columns:** `Name, Team, Opp, Pos, Saber Total, Saber Team, H, 1B, 2B, 3B, HR, R, RBI, K, BB, IP, ER, PA`
**Golf columns:** `Name, Win%, Make Cut %, SS Proj, dk_std, dk_95_percentile`

- `Saber Total` = projected game total
- `Saber Team` = projected team total
- NBA rebounds column is `RB` (not `REB`)
- NHL assists column is `A` (not `AST`)
- Filter NHL goalie rows by `Pos == G` before prop evaluation
- MLB: Pitchers identified by `Pos == P`. Derived stats: `OUTS = IP × 3`, `TB = 1B + 2×2B + 3×3B + 4×HR`, `HRR = H + R + RBI`
- Golf: `Win%` can be decimal (0.05) or percentage (5%) — code auto-detects

---

## SECTION 5: VALIDATION

Before calculation:
```
proj ≤ 0        → Skip
odds = 0        → Skip
missing side    → Skip
```

**⚠️ ODDS FORMAT CHECK:** If odds are between 1.0 and 3.0, they're decimal not American. Filter with `if 1.0 < odds < 3.0: continue`.

---

## SECTION 6: ODDS

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

## SECTION 7: PROPS

### Confidence Modifier (apply BEFORE gate evaluation)
| Condition | Multiplier |
|-----------|------------|
| Played 5+ of last 7, minutes within 10% of avg | 1.00 |
| Played 3-4 of last 7 OR minutes vary 10-15% | 0.85 |
| Played < 3 of last 7 OR minutes vary > 15% | 0.70 |

`adjusted_edge = raw_edge × confidence_multiplier`

Use adjusted edge for ALL gate and tier evaluation.

### Distribution
```
IF stat in [AST, REB, SOG, REC, K, HITS] AND line ≤ 8.5:
    USE Poisson: k = floor(line)
    Under = poisson.cdf(k, proj)
    Over  = 1 - poisson.cdf(k, proj)
ELSE:
    USE Normal: sigma = max(proj × mult, min_sigma)
    Under = norm.cdf(line, proj, sigma)
    Over  = 1 - norm.cdf(line, proj, sigma)
```

Note: HA (hits allowed) was moved OUT of Poisson — overdispersed at typical lines (std 2.70 vs Poisson-predicted 2.35). Uses Normal.

### Sigma Values (v9.4 calibrated)
| Stat | Mult | Min σ | Tier | Distribution | Status |
|------|------|-------|------|-------------|--------|
| **NBA/NHL** | | | | | |
| AST | 0.45 | 1.3 | T1 | Poisson | **LOCKED** — 68.5% WR Jan-Feb |
| REB | 0.58 | 2.5 | T1B (unders 3.5+ only) | Poisson | Widened from 0.40 — high variance |
| SOG | 0.55 | 1.2 | T1 | Poisson | **LOCKED** — 65.6% WR Jan-Feb |
| REC | 0.50 | 1.2 | T1 | Poisson | Unchanged |
| PTS | 0.35 | 4.5 | T2 | Normal | Monitor |
| 3PM | 0.55 | 0.8 | T3 | Normal | Unchanged |
| **MLB** | | | | | |
| K (pitcher) | 0.45 | 1.5 | T1 | Poisson | Good Poisson fit |
| OUTS (pitcher) | 0.22 | 3.0 | T2 | Normal | Conservative — was overestimating variance |
| HA (pitcher) | 0.50 | 2.5 | T1B (unders) | Normal | 15% overdispersed vs Poisson |
| ER (pitcher) | 0.85 | 1.8 | T2 | Normal | Was 19% under real variance |
| HITS (batter) | 0.90 | 0.7 | T1B (unders) | Poisson | Good at low counts |
| TB (batter) | 1.20 | 1.5 | T2 | Normal | Was 41% under real variance (lumpy dist) |
| HRR (batter) | 0.75 | 1.3 | T1 | Normal | Was 11% under real variance |

### MLB Correlation Groups (G11/G11b)
Max 1 prop per player within each correlated group:
- **Pitcher group:** K, OUTS, HA, ER (all functions of IP — r ~ 0.70+)
- **Batter group:** HITS, TB, HRR (HITS is component of TB and HRR — r ~ 0.70+)

---

## SECTION 8: GAME LINES

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

| Sport | Total σ | Spread σ | Team σ |
|-------|---------|----------|--------|
| NBA | 12.0 | 12.0 | 9.0 |
| NHL | 1.2 | 1.5 | 1.0 |
| MLB | 4.0 | 3.8 | 3.0 |
| MLB F5 | 2.6 | 2.5 | 2.0 |

### MLB First 5 Innings (F5)
Same formulas as full game but using F5 sigmas. Starter matchup, no bullpen noise.

### NRFI/YRFI (MLB)
```
P(NRFI) = P(away scores 0 in 1st) × P(home scores 0 in 1st)
Base rate: ~70% NRFI league-wide (~16.3% scoring prob per team per 1st inning)
```
NRFI = T3 (6% min edge), YRFI = T3 (6% min edge)

---

## SECTION 9: EDGE

```
edge = model_prob - novig_prob
```

Must be positive to bet.

---

## SECTION 10: GATES

### Props
| Gate | Trigger | Action |
|------|---------|--------|
| G1 | prob ≥ 70% AND odds > -200 | Skip |
| G2 | edge ≥ 20% | Skip (model error) |
| G3 | missing both sides | Skip |
| G4 | line ≤ 2.5 AND prob > 75% | Skip |
| G5 | odds > 0 AND prob > 65% | Skip |
| **G7** | **odds ≤ -150** | **Skip (hard ban)** |
| **G7b** | **odds -140 to -149 AND edge < 9%** | **Skip** |
| **G8** | **AST, REB, or SOG line ≤ 1.5** | **Skip** |
| **G9** | **adjusted edge < 3%** | **Skip (universal floor)** |
| **G10** | **any under at line ≤ 2.5 AND adjusted edge < 8%** | **Skip** |

G8 rationale: 1.5 lines on low-count stats are binary — one extra count kills the bet. Now includes SOG and MLB low-count stats (K, HA, HITS). Lines at 2.5+ are fine.

G10 rationale: Low-line unders (U2.5 SOG) are structurally fragile — one spike kills the bet. Requiring 8% edge filters out marginal plays while allowing genuinely strong spots through. **Note: U2.5 AST and U2.5 REB are now fully banned by R11 and R4 respectively, so G10 primarily protects U2.5 SOG.**

| **G11** | **MLB: 2+ props from same pitcher corr group (K/OUTS/HA/ER)** | **Keep best by Pick Score, skip rest** |
| **G11b** | **MLB: 2+ props from same batter corr group (HITS/TB/HRR)** | **Keep best by Pick Score, skip rest** |
| **G12** | **3+ same-direction pitcher props on same game (Premium)** | **Max 2 per game per direction** |
| **G13** | **win probability < 50%** | **Skip (proven 1-3 record, negative PS)** |

### Game Lines
| Gate | Trigger | Action |
|------|---------|--------|
| GG1 | edge ≥ 10% | Skip (model error) |
| GG2 | \|proj - line\| / σ > 1.5 | Skip (for SPREAD: uses \|proj + line\| / σ) |
| GG3 | edge ≤ 0 | Skip |
| GG4 | missing both sides | Skip |

---

## SECTION 11: DEDUPLICATION

Group by `(player, stat, line, direction)`. Keep entry with highest edge.

---

## SECTION 12: SGP RULES

Max 1 SGP per day, 2 legs max, 5% min edge per leg, 0.25u max size.

Parlay odds calculated from actual American book odds converted to decimal and multiplied — **never** from model win probabilities.

---

## SECTION 13: CLV TRACKING

Record closing odds 5 min before game lock for every bet placed.
```
CLV = closing_implied - bet_implied
```
- Rolling CLV < 0% for 30+ bets → trigger full sigma review
- Rolling CLV < -2% for 20+ bets → switch to Conservative mode

---

## SECTION 14: EXECUTION WORKFLOW

1. Load SaberSim CSV projections
2. Verify slate matches API games (filter started games by `commence_time` vs current UTC)
3. Pull odds with `oddsFormat=american`
    ```
    Markets to pull (per event, with 1.2-1.5s sleep between calls):
      NBA: player_assists, player_rebounds, player_points, player_threes, team_totals
      NHL: player_shots_on_goal, player_assists, team_totals
      MLB: pitcher_strikeouts, pitcher_outs, pitcher_hits_allowed, pitcher_earned_runs,
           batter_hits, batter_total_bases, batter_hits_runs_rbis, team_totals
      Golf: outrights (4 majors only — Masters, PGA Championship, US Open, The Open)
      Bulk: spreads, totals, h2h (one call per sport)

    After pulling, confirm:
      □ player_assists returned ≥10 players across the slate
      □ player_rebounds returned ≥10 players across the slate
      □ player_points returned ≥10 players across the slate
      □ If ANY market returns <5 players for a 5+ game slate → re-pull that market
      □ If re-pull still empty → note in output, do NOT silently skip

    STOP HERE if checks fail. Do not proceed to step 4 with incomplete data.
    ```
4. Validate (reject bad proj/odds, filter decimal odds bug)
5. Match player/team names (last name + first 3 chars fuzzy match, Unicode normalize)
6. Apply confidence modifiers
7. Calculate prob + edge (both sides, all markets)
8. Apply gates (G1-G10, GG1-GG4)
9. Deduplicate
10. Filter by tier edge thresholds
11. **DATA QUALITY CHECK (mandatory before continuing):**
    ```
    On a 5+ game NBA slate, expect these minimums AFTER gates:
      □ T1 AST qualifying picks: ≥5 (if <5, likely missed API pull — go back to step 3)
      □ T1B REB Under qualifying picks: ≥1 (U2.5 REB banned — only 3.5+ lines qualify now, expect fewer)
      □ T2 PTS qualifying picks: ≥5
      □ Total qualifying picks across all sections: ≥15

    If any check fails, DO NOT just output a sparse card.
    State what failed and re-pull the missing market.
    ```
12. **Apply Section 0 rules (R1-R12)** — including R4 (no REB Overs + no U2.5 REB), R9 directional balance, R10 same-stat cap, R11 U2.5 AST ban, R12 repeat-player cooldown
13. Sort by Pick Score descending (Premium) / edge descending (Full Card)
14. Apply caps (section caps + daily cap)
15. Size with VAKE in Pick Score descending order (max 1.25u)
16. Output per Section 15 format (ALL sections required)
17. **Bravo Six bonus output:**
    a. Pull PrizePicks Partner API: `GET https://partner-api.prizepicks.com/projections?league_id=7&per_page=1000`
    b. Filter goblins (`odds_type == "goblin"`, today, pre_game)
    c. Match to SaberSim projections, calculate win probability, filter 80%+
    d. Build 2 goblin slips (3 legs each, no overlap, CO no-stack)
    e. Build 1 alt parlay (3+ legs, combined odds -130 or longer)
    f. Output sections K, L, M

---

## SECTION 15: OUTPUT FORMAT

**Output EVERYTHING that passes gates.** Follow this exact section order. Do not skip any section — if no picks qualify, state "No qualifying picks."

Sections A–H: picksbyjonny Discord main card
Section H2: Goblin slips + alt parlay — posted to BOTH picksbyjonny Discord AND Bravo Six
Sections I–J: Verification checklist + notes
Sections K–M: Internal build details + verification for goblin slips and alt parlay

### A. Premium Card (Top 5 by Pick Score, after R8/R9/R10 applied)
```
🔒 PREMIUM PICKS — [Date] | Mode: [Default/Conservative/Aggressive]

1️⃣ X.Xu | [Player] [O/U][Line] [Stat] @ [Odds] ([Book])
   Win: XX.X% | Edge: X.X% | Pick Score: XX.X | Proj: X.XX | [Tier] | [Game]

2️⃣ ... 3️⃣ ... 4️⃣ ... 5️⃣ ...

━━━━━━━━━━━━━━━━━━━━━━━
Total: X.Xu | Bets: 5
```

### B. Safest 5 (Top 5 by win probability only — may overlap with Premium)
```
🛡️ SAFEST 5 — [Date]

1. X.Xu | [Player] [O/U][Line] [Stat] @ [Odds] ([Book]) | Win: XX.X%
2. ... 3. ... 4. ... 5. ...
```

### C. Full Card — T1/T1B Props (sorted by edge)
```
T1 ASSISTS
──────────────────────────────────────────
  X.Xu | [Player] [O/U][Line] AST @ [Odds] ([Book]) | XX.X% | X.X% | [Game]

T1 SOG
──────────────────────────────────────────
  X.Xu | [Player] [O/U][Line] SOG @ [Odds] ([Book]) | XX.X% | X.X% | [Game]

T1B REBOUND UNDERS
──────────────────────────────────────────
  X.Xu | [Player] U[Line] REB @ [Odds] ([Book]) | XX.X% | X.X% | [Game]
```

### D. Full Card — T2 Props
### E. Full Card — T3 Props
### F. Full Card — Game Lines (Totals, Team Totals, Spreads, Moneylines)
### G. Sanity Check Table (ALL picks)
```
| Pick | Proj | Line | Fair% | NV% | Edge | AdjEdge | Gate | Size | Tier | CLV_Odds |
|------|------|------|-------|-----|------|---------|------|------|------|----------|
```

### H. Discord Copy/Paste Block
```
@everyone  📌 Today's Portfolio – [Date]

Unit Framework:
1u = 1% bankroll
Max Single Position = 1.25u
Max 5 Positions
Target Daily Exposure = 4–6u

Plays
[Player] ([Team]) [Over/Under] [Line] [Stat] [Odds] ([Book]) — X.Xu
...

Total Risk Today: X.Xu
Largest Single Position: X.Xu
```

### H2. Discord + Bravo Six — Goblin Slips & Alt Parlay

Post this as a **separate message** in picksbyjonny Discord AND in Bravo Six channel. Same content, both places.

```
🟢 PrizePicks Goblin Slips

Slip 1 (3-pick Power Play):
F. Last X+ Stat 🟢 XX%
F. Last X+ Stat 🟢 XX%
F. Last X+ Stat 🟢 XX%

Slip 2 (3-pick Power Play):
F. Last X+ Stat 🟢 XX%
F. Last X+ Stat 🟢 XX%
F. Last X+ Stat 🟢 XX%

⚠️ PP moves goblin lines — verify in-app before locking

🎯 Alt Parlay Slip

3-Pick Parlay ([combined odds]):
[Team] [alt spread/ML/total] ([leg odds])
[Team] [alt spread/ML/total] ([leg odds])
[Team] [alt spread/ML/total] ([leg odds])

$20 wins $[payout]
```

**Format rules:**
- Goblin slips use PP format: `F. Last X+ Stat 🟢 XX%`
- No overlapping players between Slip 1 and Slip 2
- Alt parlay combined odds must be -130 or longer
- Posted to BOTH picksbyjonny Discord AND Bravo Six
- Posted as a separate message AFTER the main Portfolio block

### I. Output Verification Checklist
```
[ ] Premium card: 5 picks generated
[ ] Safest 5 generated
[ ] Step 3A passed: AST ≥10, REB ≥10, PTS ≥10 players pulled
[ ] Step 11 passed: T1 AST ≥5, T1B REB ≥1, T2 PTS ≥5 qualifying
[ ] R9 directional balance: Premium includes ≥1 over (if 3+ overs passed gates)
[ ] R10 same-stat cap: No more than 2 same-stat same-direction on Premium
[ ] R11 enforced: No U2.5 AST anywhere (full ban)
[ ] R12 enforced: No player whose last MBP pick was a loss (within 5 days)
[ ] G8 enforced: No AST/REB/SOG at line ≤ 1.5
[ ] G10 enforced: All ≤2.5 line unders have ≥8% adjusted edge
[ ] G7/G7b enforced: No odds ≤ -150; -140 to -149 has ≥9% edge
[ ] R4 enforced: No REB Overs AND no U2.5 REB anywhere
[ ] R7 enforced: Max 2 per game
[ ] All odds in American format
[ ] All sizes rounded to nearest 0.25u
[ ] Daily cap ≤ 12u
[ ] Bravo Six sections K-M generated (see Section M checklist)
```

### J. Notes
Brief notes: directional mix, notable exclusions, juice warnings, correlation flags, over/under count.

### K. Bravo Six — PrizePicks Goblin Slips

Two 3-leg PrizePicks goblin entries. Posted to **both** picksbyjonny Discord and Bravo Six channel. These use the **PrizePicks Partner API**, not The Odds API.

**Source:**
```
GET https://partner-api.prizepicks.com/projections?league_id=7&per_page=1000
```
Filter: `today == true`, `status == "pre_game"`, `odds_type == "goblin"`. Drop all demons.

**Build process:**
1. Match PP goblin lines to SaberSim projections
2. Calculate win probability (same engine as MBP props — Poisson/Normal)
3. Filter to 80%+ win probability
4. Exclude O0.5 3PM unless 90%+ (binary, fragile)
5. Exclude Q/GTD players
6. Sort by win probability descending
7. Build Slip 1: top 3 picks from 3 different games (CO no-stack)
8. Build Slip 2: next 3 best picks, NO overlapping players with Slip 1, from 3 different games
9. If fewer than 6 qualifying picks from different games, build 1 slip instead of 2

**Output format:**
```
🟢 PrizePicks Goblin Slips

Slip 1 (3-pick Power Play):
F. Last X+ Stat 🟢 XX%
F. Last X+ Stat 🟢 XX%
F. Last X+ Stat 🟢 XX%

Slip 2 (3-pick Power Play):
F. Last X+ Stat 🟢 XX%
F. Last X+ Stat 🟢 XX%
F. Last X+ Stat 🟢 XX%

⚠️ PP moves goblin lines — verify in-app before locking
```

**Format rules:**
- First initial + last name: `D. Gafford` not `Daniel Gafford (DAL)`
- PrizePicks language: `6+ Rebounds` not `O5.5 REB`
- 🟢 on every goblin line
- Win probability at end of line
- No overlapping players between Slip 1 and Slip 2
- All picks from different games within each slip (CO no-stack)

### L. Bravo Six — Alt Parlay Slip

One 3+ leg parlay using alt spreads, alt totals, or heavy favorite MLs. Posted to **both** picksbyjonny Discord and Bravo Six channel. Combined odds must be **-130 or longer** (i.e. -130, -120, -110, +100, +120, etc). This is NOT a straight bet on heavy juice — it's a parlay that bundles high-probability legs into a reasonable payout.

**Eligible leg types:**
- Alt spreads (inflated point spreads favoring the favorite)
- Alt totals (Over set well below projected total, Under set well above)
- Heavy favorite MLs (-200 to -500 range) — only as parlay legs, never as singles
- 1H MLs

**Build process:**
1. Identify all games on the slate
2. For each game, find the best alt spread / alt total / ML with 70%+ individual leg probability
3. Combine 3-4 legs into a parlay
4. Calculate parlay odds from American odds: convert each leg to decimal, multiply, convert back
5. If combined odds are shorter than -130, remove the safest leg or swap for a less juiced alt
6. If combined odds are longer than +200, add a leg or swap for a juicier alt
7. Target range: **-130 to +150**

**Output format:**
```
🎯 Alt Parlay Slip

3-Pick Parlay ([combined odds]):
[Team] [alt spread/ML/total] ([leg odds])
[Team] [alt spread/ML/total] ([leg odds])
[Team] [alt spread/ML/total] ([leg odds])

$20 wins $[payout]
```

### M. Bravo Six Output Verification
```
[ ] Goblin Slip 1: 3 legs, all 80%+, all different games, no Q/GTD players
[ ] Goblin Slip 2: 3 legs, all 80%+, all different games, no overlap with Slip 1
[ ] Alt Parlay: 3+ legs, combined odds -130 or longer, all legs 70%+ individual probability
[ ] PP format: F. Last X+ Stat 🟢 XX%
[ ] No O0.5 3PM under 90%
```

---

## SECTION 16: SANITY CHECKS

After generating picks, verify (applies to FULL card):

1. **Mix of overs and unders** — All same direction = bias. Flag if >80% one direction.
2. **Max 3 overs on Premium** — R6
3. **At least 1 over on Premium if 3+ passed gates** — R9
4. **Max 2 same-stat same-direction on Premium** — R10
5. **No U2.5 AST anywhere** — R11 (full ban)
6. **Win probs are 52-68%** — Not 80%+ (applies to sportsbook picks A-J only, not Bravo Six goblins K-M)
7. **Slate matches** — Projection teams match API games
8. **No heavy juice slipped through** — G7/G7b
9. **No REB Overs AND no U2.5 REB anywhere** — R4
10. **No ≤1.5 AST/REB/SOG lines** — G8
11. **All ≤2.5 line unders have ≥8% adj edge** — G10
12. **Premium = 5 picks** — R1
13. **Max 2 per game** — R7
14. **Daily cap ≤ 12u**
15. **No repeat-player loss violations** — R12

---

## SECTION 17: RULES

1. No live betting
2. No college player props (CO law)
3. Re-pull odds if > 30 min stale
4. Skip > force — when in doubt, don't bet
5. Gates protect you — trust them
6. 20%+ prop edge = model error, always skip
7. 10%+ game line edge = suspicious, always skip
8. Sigma values are calibrated parameters — review quarterly using CLV data
9. Max 1 SGP per day, 2 legs max, 5% min edge per leg
10. **REB Overs are permanently banned + U2.5 REB banned** — do not override
11. **U2.5 AST permanently banned** — do not override (upgraded from "max 1" in v9.3)
12. **Repeat-player cooldown** — if player's last MBP pick was a loss within 5 days, skip. Do not override.
13. **MLB pitcher correlation penalty** — same-game pitcher props share IP/pace. 2nd pitcher prop on same game gets additional 0.70x sizing multiplier on top of game correlation.
14. **MLB correlated stat dedup (G11/G11b)** — max 1 prop per player within each correlated group (pitcher: K/OUTS/HA/ER, batter: HITS/TB/HRR). Keep best by Pick Score.

---

## SECTION 18: PRE-LOCK CHECKLIST

Before placing any bet:
```
□ Odds still valid (re-pull if > 30 min stale)
□ Starting lineups confirmed
□ No late injury news (check Twitter, Rotowire)
□ Goalie confirmed (NHL)
□ No surprise scratches or load management
□ Confidence modifier reflects latest minutes data
□ Line hasn't moved significantly against you
□ Record closing odds for each bet placed (check 5 min before game lock)
```

---

## SECTION 19: INJURY / NEWS SOURCES

**NBA:**
@Underdog__NBA, @FantasyLabsNBA, @ShamsCharania, @wojespn, @KeithSmithNBA, @NBAPRGuy
Rotowire injury reports, team official accounts

**NHL:**
@FantasyLabsNHL, @FriedgeHNIC, @PierreVLeBrun, @DFOIceTime (goalies)
Daily Faceoff, Rotowire

---

## STARTER PROMPT

```
Run Master Betting Prompt v9.4
Sports: NBA [, NHL]
Mode: Default [or Conservative / Aggressive]
Exclude: [teams/games already started]

Complete ALL output sections (A through M). Pull live odds from The Odds API.
Apply confidence modifiers before gate evaluation.
REB Overs are BANNED — do not evaluate or output.
U2.5 REB and U2.5 AST are BANNED — do not evaluate or output.
Apply repeat-player cooldown (R12): skip players whose last MBP pick was a loss within 5 days.
If a section has no qualifying picks, state "No qualifying picks" — do not skip.

Bravo Six bonus (sections K-M):
- Pull PP goblins from https://partner-api.prizepicks.com/projections?league_id=7&per_page=1000
- Build 2 goblin slips (3 legs each, 80%+, no overlap, CO no-stack)
- Build 1 alt parlay (3+ legs, combined -130 or longer)

[attach SaberSim CSV(s)]
```

---

## CHANGELOG

### v9.4 — Bravo Six integration + evidence-based rule tightening (March 24, 2026)

**Data basis:** 55 MBP straight bets, March 12-23. Record: 34-21 (61.8%), +9.87u, +19.0% ROI. System is profitable. Changes target known failure modes without overfitting.

**Rule changes (evidence-based):**

**R4 expanded — U2.5 REB banned.** REB Overs were already banned. Now U2.5 REB Unders are banned too. v9.3: 0/2. Same structural fragility as REB Overs — one random offensive rebound kills the bet. REB Unders at 3.5+ remain allowed.

**R11 upgraded — U2.5 AST fully banned.** Was "max 1 per day" in v9.3. Now full ban. v9.3: 1/2. All-time: 5-8 (38.5%), -3.75u. Poisson model generates fat theoretical edges at proj ~1.8 vs line 2.5, but the real-world hit rate never justifies it. One random 3-assist game from a non-playmaker kills it.

**R12 added — Repeat-player cooldown.** If a player's most recent MBP pick was a loss, skip that player's next appearance. Resets after one skip. Does not apply if the loss was 5+ days ago. v9.3 evidence: Austin Reaves 0/2 (-2.00u), Reed Sheppard 0/2 (-2.00u), Evan Bouchard 1/3 (-1.55u). These three players alone cost -5.55u. When a player misses, something the model doesn't see may be in play — role shift, matchup factor, minutes change. Cooling off for one cycle is cheap insurance.

**What was NOT changed (and why):**
- **AST sigma (0.45):** 56.2% in v9.3 vs 68.5% historical. Concerning but 16 picks is too small to recalibrate. Monitor for 30 more picks — if still under 60%, open sigma review.
- **-116 to -125 odds range:** 5/12 (41.7%) looks bad but 12 picks is noise. No structural issue identified.
- **0.75u sizing:** 45.5% hit rate is by design — these are lower-confidence plays sized smaller. VAKE is working correctly (1.00u bets hit 70.8%).
- **Over/Under lean:** Overs 66.7% vs Unders 59.5% but under sample (37) is profitable (+12.9% ROI). R9 handles directional balance. Don't overfit.

**Bravo Six integration (additive — does not modify picksbyjonny output):**

**Sections K-M added.** Same MBP run, two extra outputs:
- **K: PrizePicks Goblin Slips.** Two 3-leg Power Play entries from PP Partner API. 80%+ per leg, CO no-stack, no overlapping players.
- **L: Alt Parlay Slip.** One 3+ leg parlay (alt spreads/MLs/totals). Combined odds -130 or longer. Bundles heavy favorites into reasonable payout.
- **M: Bravo Six verification checklist.**

**PrizePicks Partner API documented.** `partner-api.prizepicks.com/projections` — free, no key, returns live board with `odds_type: goblin/demon/standard`. Validated 88% match against CO app.

### v9.3 — Low-line under concentration fix (March 11, 2026)

**Data basis:** 53 MBP straight bets in March (22-31, -9.95u). March Premium cards were 83% unders. All-time unders: 31-38 (44.9%), -7.44u. All-time U2.5 AST: 5-8 (38.5%), -3.75u. SOG U1.5: 2-5 (28.6%), -3.35u. Both core engines (AST, SOG) flipped negative in March despite strong Jan-Feb performance, driven by over-concentration on low-line unders.

**Changes:**

**R9 — Directional balance (new):** If 3+ overs pass all gates, at least 1 over must appear on Premium card. Prevents the card from becoming a pure under sheet. March was 83% unders with a 38.6% win rate on unders vs 55.6% on overs.

**R10 — Same-stat same-direction cap on Premium (new):** Max 2 picks sharing both stat type AND direction on Premium. Prevents correlated blowups like Mar 11 (3 AST unders, all lost).

**R11 — U2.5 AST daily cap (new):** Max 1 U2.5 AST under per day across entire card. All-time 5-8 at this line. Poisson generates fat theoretical edges at proj ~1.8 vs line 2.5, but one random 3-assist game kills the bet. Cap limits exposure to this fragile line.

**G8 extended to SOG (modified):** Now blocks AST, REB, AND SOG at line ≤ 1.5 (was AST/REB only). SOG U1.5: 2-5, -3.35u. Same binary fragility — one extra shot kills it.

**G10 — Low-line under gate (new):** Any under at line ≤ 2.5 requires ≥8% adjusted edge (was 3% universal floor). Low-line unders are structurally fragile; this filters marginal plays while keeping genuinely strong spots.

**Not changed:** Poisson model, AST sigma (0.45), SOG sigma (0.55), REB sigma (0.58), Pick Score formula, VAKE sizing, 1.25u cap, 12u daily cap, REB overs ban, -150 juice ban. All remain from v9.2.

### v9.2 — Evidence-based optimization (March 2026)
- R4: REB Overs fully banned (was 6%→8% gate, now hard ban). 8-18 (30.8%), -13.24u structural failure.
- G7 split: ≤-150 hard ban, -140 to -149 needs 9% (was ≤-145 needs 8%). Heavy juice 16-10 but -1.69u.
- Poisson cutoff raised 5.5 → 8.5 for better accuracy on mid-range lines.
- REB sigma widened 0.52 → 0.58, min 2.0 → 2.5.
- CLV tracking added (Section 13).
- G9 universal 3% floor added.
- Confidence modifier added (Section 7).
- Removed G6, RR1, RR2 (dead rules after REB Over ban).
- Sizing table bottom raised (min 0.50u at 3-5%).
- Daily cap 15u → 12u, max size 1.50u → 1.25u.
- Stop loss simplified to -3.0u/day (removed consecutive loss trigger).

### v9.0.3.1
- Step 3A (API Verification Gate) and Step 9A (Data Quality Check)
- Pick Score modes: Default (60/40), Conservative (70/30), Aggressive (45/55)

### v9.0.3
- Premium ranking: edge × win_prob → Pick Score formula

### v9.0.2
- G8 gate (AST/REB at 1.5), Safest 5 section, Discord block, Checklist, Starter Prompt

### v9.0.1
- Premium/Full Card split, R8 tier priority, R6 applies to Premium only

### v9.0 — Rebuilt from v7.3 base
- Section 0 risk management, G6/G7, T1B tier, 1.50u max, 15u daily cap, removed PlayerProfit
