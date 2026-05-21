# NFL Research Findings — G9
## Context Keywords, Injury Policy, Grading, SaberSim CSV
*Researched: 2026-05-21*

---

## 1. CONTEXT SANITY KEYWORDS (NFL)

### Official NFL Injury Designations
- **Q** — Questionable: player may or may not play; teams must list
- **D** — Doubtful: unlikely to play; ~25% or less play rate historically
- **O** — Out: will not play this game
- **IR** — Injured Reserve: out minimum 4 weeks (post-2020 rule: 3 weeks for designated return)
- **DNP** — Did Not Practice (practice status, not game status)
- **LP** — Limited Participant (practice)
- **FP** — Full Participant (practice) — strong signal player will be active
- **Probable** — dropped by NFL in 2016; no longer used on official weekly injury report

### Inactive List Release Timing
- **Official rule**: teams submit inactive list exactly **90 minutes before kickoff**
- Sunday 1pm ET games: inactives due ~11:30 AM ET
- Sunday 4:25pm ET games: inactives due ~2:55 PM ET (separate submission per wave)
- SNF: inactives due ~7:00 PM ET (8:20pm kickoff)
- TNF: inactives due ~7:30 PM ET (8:15pm kickoff)
- MNF: inactives due ~8:30 PM ET (8:15pm kickoff on ESPN)
- Teams declare up to 7 inactive players (48-man game-day roster; 53-man + practice squad)

### Keywords: Player IS OUT
- "listed as inactive"
- "ruled out"
- "placed on IR" / "placed on injured reserve"
- "will not play"
- "inactive list"
- "scratched" (used in beat reporter shorthand)
- "doubtful" — treat as soft-out (~75–80% DNP rate empirically)
- "out Sunday" / "out this week"

### Keywords: Player IS ACTIVE
- "active"
- "off injury report" / "no injury designation"
- "full participant" / "FP"
- "no designation" (after appearing on injury report mid-week)
- "cleared" / "good to go" / "expected to play"
- "practicing in full"

### Edge Cases
- **Game-day scratches not on injury report**: teams can add injuries after the Wednesday report. Beat reporters (e.g., Ian Rapoport, Adam Schefter, team beat writers) tweet these ~T-2h to T-30min before kickoff. Context scanner should flag beat-reporter tweets containing "will not play," "out tonight," or similar for players with active bets.
- **Surprise inactives**: players with no designation (healthy scratch/coaching decision) appear only on the formal 90-min inactive list. No prior report coverage. Scanner cannot catch these in advance — they fire in the 90-min window.
- **Q players on final report (Friday)**: if a Q player had DNP Wednesday/Thursday, elevated DNP risk (~40% sit rate). If Q + FP/LP Friday, play rate ~80-85%.

### Weather Flagging
- **Yes, weather should be flagged for outdoor games**
- Relevant thresholds for prop betting: wind >20 mph (passing props), precipitation (kicker props, total props)
- Hurricanes have caused: game relocations (Saints → Jacksonville 2021), rescheduling (Titans-Dolphins 2004), week-long postponements (Browns-Bills → Detroit 2022)
- NFL does NOT cancel regular season games; they relocate or postpone
- Dome stadiums (ATL, NO, DAL, IND, LV, MIN, DET, ARI, HOU): not weather-sensitive
- Context scanner should flag: "postponed," "rescheduled," "relocated," "weather delay" for active bets
- Practically: wind >20mph suppresses passing yards/receiving yards props; QB passing TDs less affected than yardage

---

## 2. INJURY STATUS POLICY — BINARY VS PROBABILISTIC

### Book-by-Book Void/Grade Policy (NFL Props, DNP)

| Book | DNP = 0 snaps | Any participation |
|------|--------------|-------------------|
| **DraftKings** | Voided / stake refunded | Graded (stands as bet) |
| **FanDuel** | Voided / stake refunded | Graded (even 1 snap) |
| **BetMGM** | Voided / stake refunded (parlay: leg removed, ticket repriced) | Graded |
| **Caesars** | Voided / stake refunded | Graded |

- **Consensus across all CO-legal books**: void if player records 0 snaps / does not participate at all. Once any participation occurs (1 snap, 1 carry, 1 target), bet stands and is graded on results — even if player exits immediately with injury.
- For SGP legs: DraftKings and BetMGM remove the voided leg and reprice the parlay. FanDuel and Caesars follow the same pattern.

### P(plays | Q) by Position — Empirical Rates

Source: Footballguys Injury Index (2017–2023, 2,000+ injuries); NFL Nation/ESPN historical data.

| Position | P(plays \| Q) | Notes |
|----------|--------------|-------|
| **QB** | ~70–75% | Backup QB designation inflates; starter Q plays ~75%; if Q + LP Thursday, ~65% |
| **RB** | ~72–78% | Workhorse backs closer to 80%; committee backs closer to 65% |
| **WR** | ~75–80% | Wide range by injury type; hamstring Q = lower; foot/ankle = ~60% |
| **TE** | ~72–76% | Similar to RB pattern |
| **All positions combined** | ~72–75% | Nearly three-fourths of Q players play; peak (Week 2 2016) was 79% |
| **Doubtful** | ~25–30% | Roughly inverse of Questionable; high uncertainty |

- Historical note: "Probable" (97–98% play rate) was dropped in 2016 because it conveyed no useful information.
- Team-specific variation: Philadelphia Q players have historically lower play rates. Tampa Bay and Chicago more liberal with Q designation → higher play rate relative to designation.
- Q + FP Friday: ~85% play rate. Q + DNP Friday: ~55-60% play rate.

### Snap Share for Returning Q Player vs Healthy Baseline
- No published peer-reviewed study with exact numbers for snap-share reduction.
- Practical observation: returning Q player in first game back often enters on limited snap count (~25–35 snaps) before coaches expand role.
- For prop betting purposes: a Q player who plays typically gets **60–80% of healthy snap share** in the return game (general practitioner consensus; no rigorous study found).
- Injury type matters: soft-tissue (hamstring, groin) = deeper snap cut; structural/bone = near-full participation.

### CONCLUSION: Binary vs Probabilistic for NFL

**Use binary in/out (same as NBA), not probabilistic.**

Rationale:
1. All major books void props when player has 0 participation — probabilistic discounting is structurally -EV (same logic as NBA/feedback_play_prob_binary.md).
2. Official inactive list fires 90 min before kickoff — by the time picks are graded, status is known.
3. Q players who do play often have reduced snap share → prop still graded on result, not discounted.
4. Context scanner catches most DNPs before picks are posted; residual risk (surprise inactives after run) is identical to NBA problem — binary cut is correct.
5. Exception to investigate: if running picks BEFORE inactives are posted (>90 min before kickoff), consider flagging Q players but not cutting them — let context scanner surface later.

---

## 3. AUTO-GRADING

### ESPN NFL Sport Key
- NFL sport key for ESPN API: **`football/nfl`**
- Scoreboard endpoint: `https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard`
- With date parameter: `?dates=YYYYMMDD` (e.g., `?dates=20251109`)
- Same structure as NBA (`basketball/nba`) — confirmed compatible with existing grade_picks.py endpoint pattern.

### NFL Final Scores via ESPN Scoreboard Endpoint
- **Yes, ESPN scoreboard endpoint works for NFL final scores.**
- Returns `events[]` array with `competitors[]` each containing `score` and `winner` fields.
- Game status `type.completed = true` signals final.
- No API key required.
- Grading spreads/totals: final score available; grade spread/total against closing line directly.

### Player Stats Sources (Post-Game)

| Source | Data Available | Latency | Method |
|--------|---------------|---------|--------|
| **ESPN hidden API** | Passing yds, rush yds, rec yds, TDs, targets, receptions, carries, snaps (limited) | ~15–30 min post-final whistle | `site.api.espn.com/apis/site/v2/sports/football/nfl/summary?event={EVENT_ID}` |
| **nflfastR (nflverse)** | Full play-by-play; all player stats calculable | **Updated nightly** — available next morning | R package; Python wrapper `nfl-data-py` on PyPI |
| **Pro Football Reference** | Comprehensive box scores | ~1–4 hours post-game (manual entry) | Scraping; rate-limit risk |
| **ESPN player stats API** | Per-game log | ~30–60 min post-game | `sports.core.api.espn.com/v2/sports/football/leagues/nfl/athletes/{id}/statisticslog` |

**Recommendation**: ESPN summary endpoint for same-night grading (passing/rushing/receiving yards, TDs, receptions). nflfastR/nfl-data-py for overnight batch grading with full stat accuracy.

### Grading-Relevant ESPN Endpoints
```
# Scoreboard (final scores):
GET https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates=YYYYMMDD

# Game summary with box score:
GET https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary?event={EVENT_ID}

# Player game log:
GET https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/athletes/{ATHLETE_ID}/statisticslog

# CDN box score (faster cache):
GET https://cdn.espn.com/core/football/boxscore?xhr=1&gameId={EVENT_ID}
```

### Name Canonicalization
- ESPN displays: **"DK Metcalf"** (no periods) — this is ESPN's API display name.
- FantasyCalc and some sources use **"D.K. Metcalf"** (with periods).
- **Standard to implement**: strip all periods from initials, normalize whitespace. "D.K. Metcalf" → "DK Metcalf". Also handle: "AJ Brown" vs "A.J. Brown", "TY Hilton" vs "T.Y. Hilton".
- Existing `name_key()` function in run_picks.py already strips non-alpha characters — confirm this handles NFL initials.
- Additional edge cases: suffix normalization ("Patrick Mahomes II" → "Patrick Mahomes"), Jr./Sr. stripping.

### Stats Finalization Latency
- **Game scores**: real-time via ESPN (200ms behind broadcast); final score available within minutes of final whistle.
- **Player prop stats** (passing yds, rush yds, rec yds, receptions): available in ESPN summary ~15–30 minutes post-game.
- **Full box score accuracy**: ESPN may update for 30–60 minutes as official stats crew finalizes.
- **nflfastR**: nightly update — data available by ~6–8 AM ET next morning (confirmed: "updated nightly during the season").
- **FTN charted data** (targets, routes, etc.): available within 48 hours post-game.

### Game Lines (Spread, Total, ML) — Grading from ESPN
- **Yes**: ESPN final score → compute ATS result directly. `homeScore - awayScore` vs spread.
- For totals: `homeScore + awayScore` vs total line.
- For ML: winning team directly from ESPN `competitors[].winner = true`.
- No additional source needed for game-line grading.

---

## 4. SABERSIM NFL CSV FORMAT

### Confirmed Column Set (from existing run_picks.py parse_csv function + NFL DFS research)

The existing `parse_csv()` in `engine/run_picks.py` already reads a superset of columns. Columns confirmed present in SaberSim exports across sports:

| Column | NFL Relevance | Notes |
|--------|--------------|-------|
| `Name` | Player name | Matches DK/FD roster upload |
| `Team` | Team abbreviation | 3-letter abbrev |
| `Opp` | Opponent abbreviation | Confirmed in existing code (`clean.get("Opp", ...)`) |
| `Pos` | Position | QB, RB, WR, TE, K, DST |
| `Saber Total` | Total fantasy point projection | Primary projection column |
| `Saber Team` | Team total fantasy points | Used for game-line blending |
| `Status` | Injury/confirmation status | "Confirmed" for confirmed starters |

### NFL-Specific Stat Columns (expected, not yet in parse_csv — to be added)
- **QB**: Pass Yds, Pass TD, INT, Rush Yds, Rush TD
- **RB**: Rush Yds, Rush TD, Rec, Rec Yds
- **WR/TE**: Rec, Rec Yds, Rec TD, Targets (may not be present)
- **K**: FG Made, FG Att, PAT (less relevant for prop betting)
- **DST**: Pts Against, Sacks, INTs, TDs
- Likely also: `Floor`, `Ceiling`, `Own%` (ownership projection) — standard SaberSim export columns

### Target Share / Snap Share / Carry Share
- **SaberSim does NOT expose snap share or target share in standard CSV download.**
- SaberSim uses snap/target share internally to build projections but does not output these columns.
- Snap % and target share must be sourced separately (nflverse, PFF, FantasyPoints Data Suite) if needed.
- `Saber Total` already incorporates usage rate implicitly.

### Publication Timing
- **Saturday night**: SaberSim typically posts NFL projections late Saturday (after official injury reports and practice status updates settle Thursday/Friday — with Saturday updates for late-breaking injuries).
- Projections update continuously as injury news breaks; final version ~Saturday 8–11 PM ET.
- **Sunday morning refresh**: projections update again Sunday morning (~7–10 AM ET) incorporating any Sunday-morning injury news.
- For TNF: projections available by Wednesday afternoon/evening.
- For MNF: projections available by Sunday evening.

### Separate CSVs Per Slate vs Combined File
- **SaberSim provides separate slates matching DraftKings/FanDuel slate structure.**
- Typical NFL Sunday: separate CSVs for Main Slate (1pm + 4pm), SNF, and any standalone games.
- TNF and MNF are separate single-game or small slates.
- User selects which slate to export from the SaberSim interface → downloads one CSV per slate.
- Run_picks.py can accept multiple CSVs: `python run_picks.py nfl_main.csv nfl_snf.csv`
- Early games (1pm) and late games (4pm) are often combined in the "Main Slate" single CSV.

### Team Abbreviations
- SaberSim uses **DraftKings-style 3-letter abbreviations**.
- Odds API uses similar but not always identical abbreviations.
- Known mismatches to handle (NFL):

| Team | SaberSim/DK | Odds API | Notes |
|------|-------------|----------|-------|
| Los Angeles Rams | LAR | LA Rams | May vary |
| Los Angeles Chargers | LAC | LA Chargers | May vary |
| New England Patriots | NE | New England Patriots | Full name in some APIs |
| New York Giants | NYG | NY Giants | |
| New York Jets | NYJ | NY Jets | |
| Kansas City Chiefs | KC | Kansas City Chiefs | |
| Tampa Bay Buccaneers | TB | Tampa Bay Buccaneers | |
| Green Bay Packers | GB | Green Bay Packers | |

- **Recommendation**: build a `NFL_TEAM_ALIAS` dict in run_picks.py (same pattern as existing alias handling) to normalize SaberSim abbreviations → Odds API team names.

### Sport Detection for NFL CSV
- Current `parse_csv()` does NOT detect NFL — falls through to NBA if no known headers match.
- NFL CSV will not have `rb`, `ast`, `3pt` (NBA headers) or `sog` (NHL) or `ip`/`k`/`er` (MLB).
- **Need to add NFL detection**. Suggested: check for `qb` or `pass yds` or `rush yds` in headers, or check filename for "nfl".
- Alternatively: add `elif "nfl" in fname: sport = "NFL"` before the `else: sport = "NBA"` fallback.

---

## OPEN QUESTIONS / GAPS

1. **Snap share reduction for Q players**: No rigorous published study with exact percentages by position. Best available: "25–35 snaps" initial return, ~60–80% of healthy baseline. Flag for internal tracking if NFL prop grading tracks actuals.
2. **SaberSim NFL exact stat column names**: Not publicly documented. Must inspect actual downloaded CSV when NFL season begins. Likely mirrors DK salary upload format (Name, Position, Salary, Team, Opp, Fpts projected).
3. **nflfastR Python wrapper**: `nfl-data-py` on PyPI — viable for overnight grading batch. Confirm install: `pip install nfl-data-py`.
4. **ESPN athlete ID lookup for NFL**: need player name → ESPN ID mapping. Can scrape ESPN roster pages or use `sports.core.api.espn.com/v2/sports/football/leagues/nfl/athletes?limit=1000`.
5. **Stats finalization for unusual plays**: official scorer changes (pass vs rush yards) can take 24–48h. For grading purposes, treat ESPN stats as final after 1 hour post-game for standard props.

---

*Sources: Action Network, DraftKings support portal, OddsAssist, RotoGrinders, ESPN NFL API docs (community), Footballguys Injury Index, nflfastR documentation, NFL.com injury rules, NBC Sports weather delay rules.*
