# ChatGPT Research Prompts — Sports Integration

These prompts are for deep research on each sport before building it into the JonnyParlay betting engine.
The engine is Python-based and uses: SaberSim CSV projections, The Odds API (for lines/markets), and
normal/Poisson/negative-binomial probability distributions. Be as specific as possible — column names,
exact API strings, sample JSON, URLs. Vague answers are not useful.

---

## 1. NFL

I am building a sports betting model for NFL player props and game lines in Python. I need extremely
specific technical information to integrate NFL into my existing system. Please research and answer
all of the following:

**SaberSim NFL CSV format:**
- Does SaberSim offer NFL projections in the same CSV format as their NBA/NHL product?
- What are the exact column header names in a SaberSim NFL CSV? I need the full header row.
- Specifically, which columns contain: passing yards, rushing yards, receiving yards, receptions,
  passing TDs, rushing TDs, receiving TDs, dk_std (standard deviation), player name, team, position?
- Are projections one row per player, or split by game?

**The Odds API — NFL markets:**
- What is the exact sport key string for NFL in The Odds API? (e.g. `americanfootball_nfl`)
- List every player prop market key available for NFL. I need the exact strings as they appear in
  the API (e.g. `player_pass_yds`, `player_rush_yds`, `player_reception_yds`, `player_receptions`,
  `player_pass_tds`, `player_rush_tds`, `player_anytime_td`). Are there alternate line markets?
- For each market, how is the outcome structured — is it over/under with a point value, or yes/no?
- What game line market keys exist? (spreads, totals, moneylines, team totals, first half lines)

**Statistical distributions:**
- For each of the following stats, what is the typical line range on sportsbooks and roughly what
  is the per-game standard deviation relative to the mean?
  - Passing yards (e.g. line 245.5, sigma ~?)
  - Rushing yards (e.g. line 65.5, sigma ~?)
  - Receiving yards (e.g. line 55.5, sigma ~?)
  - Receptions (e.g. line 4.5, sigma ~?)
  - Passing TDs (are these offered as over/under 1.5 TDs, or anytime scorer markets only?)
- Are rushing and receiving yards roughly normally distributed, or right-skewed?

**PFF (Pro Football Focus) data:**
- Does PFF offer an API or downloadable projection files?
- If API: what are the endpoint URLs, authentication method, and response format (JSON columns)?
- If download: what format (CSV/Excel), column names, update frequency?
- How are player names formatted — full name, last name only, with/without suffixes (Jr./Sr.)?
- What is the exact cost and subscription tier needed to access player projections?

**4th Down Model (rbsdm.com):**
- How do you access 4th Down Model projections programmatically?
- Is there a CSV download, API endpoint, or must it be scraped?
- What columns/fields are available? What does a sample row look like?
- How frequently are projections updated during the week?

**Injury/lineup reporting:**
- What is the standard NFL injury report timeline (Wednesday/Thursday/Friday practice reports)?
- Is there a free or low-cost API for NFL injury report data (player status: questionable/out/IR)?
- What is the most reliable programmatic source for confirmed starting lineup / snap count projections?

---

## 2. College Football (NCAAF)

I am building a sports betting model for NCAAF (college football) game lines and potentially player
props in Python. I need extremely specific technical information. Please research and answer all of
the following:

**SaberSim / DFS projection sources:**
- Does SaberSim offer NCAAF projections? If so, same CSV format as NFL? What are the exact column names?
- If SaberSim doesn't cover NCAAF, which DFS projection sites do (4for4, FantasyPros, etc.)?
- What are the exact column names in whatever CSV format is available?

**The Odds API — NCAAF markets:**
- What is the exact sport key string for NCAAF? (e.g. `americanfootball_ncaaf`)
- What market keys are available? List exact strings for: game totals, spreads, moneylines, team totals.
- Do legal US sportsbooks actually offer NCAAF player props (passing yards, rushing yards, TDs)?
  If yes, what are the exact Odds API market key strings?
- Which books offer the most NCAAF player prop coverage?

**SP+ ratings (Bill Connelly / ESPN):**
- How do you access SP+ ratings programmatically in 2025/2026?
- Is there an ESPN API endpoint, CSV download, or must it be scraped from the web?
- What data fields are available: offensive efficiency, defensive efficiency, projected final score,
  home field advantage adjustment?
- Provide a sample data structure (column names or JSON fields).
- How frequently are ratings updated during the season?

**Game projection math:**
- Given SP+ offensive and defensive efficiency ratings for two teams, what is the standard formula
  to derive: (a) projected total score, (b) projected spread?
- Does BartTorvik or any other source provide NCAAF projections (separate from NCAAB)?

**Player props availability:**
- Which legal US sportsbooks (DraftKings, FanDuel, BetMGM, etc.) offer NCAAF player props?
- What stats are typically available: passing yards, rushing yards, receiving yards, TDs, receptions?
- How do player prop lines for NCAAF compare in liquidity/availability vs NFL?

**Season structure:**
- Regular season dates for 2026 NCAAF season (approx start/end).
- Conference championship weekend, bowl season, and College Football Playoff dates.
- How many games are played per week during the regular season?

---

## 3. College Basketball (NCAAB)

I am building a sports betting model for NCAAB game lines (totals, spreads, moneylines) in Python.
No player props — game lines only. I need extremely specific technical information.

**KenPom:**
- Confirm current subscription cost (~$20/yr).
- What data is available on kenpom.com? Specifically: team tempo (possessions per 40 min),
  adjusted offensive efficiency (points per 100 possessions), adjusted defensive efficiency,
  and projected game scores/totals for upcoming games.
- Does KenPom show projected scores for upcoming games, or only efficiency ratings?
- Is there a programmatic access method (API, CSV export, RSS)?
- If scraping is required: what is the URL structure for game predictions and team ratings pages?
  What HTML elements contain the projection data?
- How are team names formatted on KenPom vs how The Odds API formats them?

**BartTorvik (barttorvik.com):**
- What data does BartTorvik provide? Same efficiency metrics as KenPom?
- Is there a CSV export, API, or must it be scraped?
- If scraping: what URL and HTML structure contains upcoming game projections?
- Does BartTorvik provide projected game totals or just efficiency ratings?
- How do you derive a projected game total from their efficiency + tempo numbers?

**Deriving game totals from efficiency ratings:**
- Given Team A offensive efficiency (OE_A), Team B defensive efficiency (DE_B), and pace (possessions),
  what is the formula to project Team A's score? (Standard formula: Score_A = (OE_A/100) * (DE_B/100)
  * pace * adjustment_factor — confirm or correct this)
- What adjustment factor is typically used for neutral vs home court?

**The Odds API — NCAAB markets:**
- Exact sport key string for NCAAB (e.g. `basketball_ncaab`).
- Available market key strings for: game totals, spreads, moneylines, team totals.
- How many books typically cover NCAAB on The Odds API? Is there enough coverage for reliable no-vig
  calculation?

**Results data for backtesting:**
- Best free source for historical NCAAB game scores programmatically (Sports Reference API,
  ESPN hidden API, college basketball reference)?
- Provide the exact URL/endpoint format and response structure.

**Season calendar:**
- 2026-27 NCAAB season approximate start (early November) and end (April, Final Four).
- When does the conference tournament period start? When is Selection Sunday?
- How many games per day during peak regular season vs tournament?

---

## 4. Golf

I am building a sports betting model for PGA Tour golf markets in Python. I need extremely specific
technical information about data sources and API formats.

**DataGolf API:**
- Confirm current subscription cost (~$30/mo) and what tier is needed for full projection access.
- List every relevant API endpoint. For each, provide:
  - Full URL
  - Required parameters
  - Response format (JSON field names)
  - Update frequency
- Specifically, does DataGolf provide per-player finish probability distributions? I need:
  win%, top-5%, top-10%, top-20%, top-40%, make-cut% as direct probability outputs.
- Does DataGolf provide head-to-head matchup projections (player A vs player B — who scores better)?
- Does DataGolf provide live in-round projections or only pre-tournament?
- How are player names formatted in DataGolf responses?

**The Odds API — Golf markets:**
- How is golf structured in The Odds API? Is it one sport key per tournament
  (e.g. `golf_masters_tournament_winner`) or a unified golf key?
- List all golf-related sport keys that exist in The Odds API.
- For each key, what market keys are available? I need exact strings for:
  outrights (win), top-5, top-10, top-20, make/miss cut, head-to-head matchups.
- How are player names formatted in Odds API golf responses?

**Player name matching:**
- Are there known systematic differences between how DataGolf and The Odds API format player names?
  (e.g. accents: Rory McIlroy vs Rory Mcilroy, Jon Rahm vs Jon Rahm, etc.)
- Provide a list of 10+ players where name formatting is likely to differ between sources.

**Tournament calendar:**
- Full 2026 PGA Tour schedule: tournament names, dates, and the corresponding Odds API sport key
  for each (or the pattern used to construct the sport key).
- Which events are Majors? Which are elevated events?
- How far in advance does DataGolf publish field projections for each event?

**Probability model:**
- Does DataGolf publish finish probabilities directly, or do we need to convert their
  strokes-gained projections? If conversion is needed, what is the standard method?
- How do DataGolf's published win probabilities compare to market-implied win probabilities
  historically? Is there systematic edge?

---

## 5. Tennis

I am building a sports betting model for ATP/WTA tennis match betting in Python. I need extremely
specific technical information.

**Jeff Sackmann data (tennis-abstract):**
- Which GitHub repository is most useful for building match win probability models?
  (tennis_atp, tennis_wta, tennis_slam_pointbypoint, or other)
- What are the exact column names in the main match-level CSV files?
  Provide a sample header row for both ATP and WTA.
- Does Sackmann publish surface-adjusted Elo ratings as a ready-to-use file?
  If yes: what is the URL/filename and column format?
- What is the standard formula to convert Elo difference into match win probability?
  Does it differ for best-of-3 vs best-of-5?

**Alternative projection sources:**
- Beyond Sackmann, are there any public or low-cost APIs that provide tennis match
  win probabilities directly (rather than requiring you to build a model)?
- TennisAbstract.com, Ultimate Tennis Statistics, or others — do any offer
  programmatic access to ratings or predictions?

**The Odds API — Tennis markets:**
- Exact sport key strings for: ATP (`tennis_atp`?), WTA, Grand Slams (are they separate keys?).
- What market key strings exist for:
  match winner (h2h), set betting/handicap, total games in match, first set winner?
- How are player names formatted in Odds API tennis responses?
- How many books typically cover tennis on The Odds API? Enough for reliable no-vig?

**Match structure handling:**
- Best-of-3 vs best-of-5: which tournaments use each format?
- How do sportsbooks handle retirement/walkover — do they void, settle on current score, or other?
- For set handicap markets: how is a -1.5 sets handicap structured as an over/under?

**Draw and schedule:**
- How far in advance are ATP/WTA tournament draws published?
- Is there a reliable free API or data source for: today's matches, draw results,
  court assignments, and match start times?
- How does the qualifying draw interact with the main draw for betting purposes?

**Statistical distributions:**
- For total games in a match: what is the typical line range (e.g. 20.5–22.5) and
  roughly what distribution fits (Normal? Bounded?)
- For set betting: how do books typically structure this market?

---

## 6. MMA/UFC

I am building a sports betting model for UFC/MMA markets in Python. I need extremely specific
technical information.

**SaberSim UFC CSV format:**
- We have confirmed SaberSim offers UFC projections. The columns we've seen are:
  `win` (percentage string), `sig_strikes`, `takedowns`, `submissions`, `quick_win`,
  `control_time`, `dk_std`. Please confirm these are all the stat columns, or list any
  additional columns we may have missed.
- Are projections one row per fighter? How are fighter names formatted?
- What is the typical CSV filename format for UFC events?
- Are projections published per-fight (i.e. each fighter's row contains opponent info)
  or standalone per fighter?
- How far before the event does SaberSim publish UFC projections?

**The Odds API — MMA markets:**
- Exact sport key string for UFC/MMA (e.g. `mma_mixed_martial_arts`).
- List every market key available. I need exact strings for:
  fight winner (ML), round totals (over/under X.5 rounds), method of victory
  (KO/TKO vs decision vs submission), round betting (fight ends in round X),
  will the fight go the distance (yes/no)?
- How are fighter names formatted in Odds API MMA responses?
- How many books typically offer MMA markets? Is there enough for reliable no-vig?
- Are there separate sport keys for PFL, Bellator, ONE Championship?

**Statistical distributions:**
- For sig_strikes: what is the typical per-fight range (e.g. 40–120) and is the
  distribution roughly Normal or skewed?
- For round totals: typical lines are 1.5, 2.5 for 3-round fights and 3.5, 4.5 for
  5-round title fights — confirm and add any nuance.
- For fight winner: is SaberSim's `win` column (a percentage) reliable enough to use
  directly as win probability, or does it need calibration?
- How does a No Contest or DQ outcome affect over/under round bets on major books?

**Event structure:**
- How often do major UFC events occur (roughly how many per month)?
- What is the typical card structure: how many prelim fights vs main card fights?
- Are prelim fights covered by sportsbooks with the same market depth as main card?
- When does SaberSim publish projections relative to fight time (day of? day before?)?

**Method of victory modeling:**
- What data source has the best historical fighter stats for modeling KO/TKO rate,
  submission rate, decision rate? (FightMetric, UFCStats.com, Tapology, MMA Decisions?)
- Is UFCStats.com (ufcstats.com) scrapeable? What data is available there?
- For a fighter with historical stats, what is the standard approach to project
  P(KO/TKO), P(submission), P(decision) for a given matchup?
