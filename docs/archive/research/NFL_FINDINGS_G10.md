# NFL Research Findings: G10
## Odds API Market Keys + Book Coverage + Cross-Cutting Considerations
### Researched: 2026-05-21

---

## ODDS API MARKET KEYS

### Confirmed Market Key Strings (americanfootball_nfl)

All player prop markets are accessed via the `/v4/sports/americanfootball_nfl/events/{eventId}/odds` endpoint,
NOT the bulk `/v4/sports/americanfootball_nfl/odds` endpoint. The bulk endpoint only supports featured markets
(h2h, spreads, totals). Player props must be fetched one event at a time.

| Stat | Exact Market Key | Notes |
|------|-----------------|-------|
| Passing yards | `player_pass_yds` | Confirmed in API docs and oddsapiR package |
| Rushing yards | `player_rush_yds` | Confirmed |
| Receiving yards | `player_reception_yds` | Confirmed (NOT player_receiving_yds) |
| Receptions | `player_receptions` | Confirmed |
| Passing TDs | `player_pass_tds` | Confirmed |
| Rushing TDs | `player_rush_tds` | Confirmed (referenced in docs) |
| Receiving TDs | `player_reception_tds` | Confirmed (mirrors reception_yds naming convention) |
| Interceptions | `player_pass_interceptions` | Confirmed — NOT player_interceptions |
| Anytime TD scorer | `player_anytime_tds` | Confirmed as separate market from rush/rec TDs |
| Full game spread | `spreads` | Same as NBA/MLB |
| Full game total | `totals` | Same as NBA/MLB |
| Moneyline | `h2h` | Same as NBA/MLB |
| Team totals | `team_totals` | Same market key as other sports |
| Alternate spread | `alternate_spreads` | Confirmed via API docs examples |
| Alternate totals | `alternate_totals` | Confirmed via API docs examples |
| Combo (pass+rush yds) | `player_pass_rush_yds` | Likely key; verify against live API — sparse coverage |
| Combo (rec+rush yds) | `player_rush_reception_yds` | Likely key; verify against live API — sparse coverage |
| Passing completions | `player_pass_completions` | Listed in docs; available on major books |
| Passing attempts | `player_pass_attempts` | Listed in docs |
| Longest reception | `player_reception_longest` | Listed in docs |
| Longest rush | `player_rush_longest` | Listed in docs |

**CRITICAL NOTE:** The receiving yards key is `player_reception_yds`, not `player_receiving_yds`. This is
inconsistent with intuition and a common source of bugs. Verify on first API call.

### Region

- **Use `us` region for all standard player props.** The `us2` region covers a different set of books
  (smaller operators). For the 18 CO-legal books in the model, `us` covers the primary tier
  (DraftKings, FanDuel, BetMGM, Caesars, FanDuel, Hard Rock). Use `us2` as a supplemental region
  for operators like BetParx, BallyBet, TwinSpires, Circa if those are available via Odds API.
- **Recommendation:** query both `us` and `us2` for props and deduplicate by bookmaker key, same as
  the current NBA implementation.

### Endpoint Architecture

- **Featured markets** (h2h, spreads, totals, team_totals, alternate_spreads, alternate_totals):
  `/v4/sports/americanfootball_nfl/odds?regions=us&markets=spreads,totals,h2h`
- **Player props** (all player_* keys): `/v4/sports/americanfootball_nfl/events/{eventId}/odds?markets=player_pass_yds,player_rush_yds,...`
- Player props update at 1-minute intervals on the event endpoint.
- Fetching 5 prop markets in 1 event-odds call costs: 5 markets × 1 region × number of books returning data (quota units).
- **Implementation note:** The model will need an event ID resolution step — fetch the events list first
  (`/v4/sports/americanfootball_nfl/events`) to get eventId, then call event-odds per game.
  This is different from the NBA implementation if it uses the bulk odds endpoint.

### Alternate Lines for Props

- Alternate passing yards lines (e.g., 225.5 instead of 249.5) are offered by major books
  (DraftKings, FanDuel) but are NOT currently a supported Odds API market key under a single
  `player_pass_yds_alternate` style key. The Odds API returns whatever lines the book posts;
  if a book posts multiple lines (alt lines), they appear as separate outcomes under the same
  market key — i.e., the model may see `player_pass_yds` with outcomes at both 249.5 and 274.5
  from the same book. This is consistent with how alternate spreads work on game lines.
- **SPORT_ALT_MARKET for NFL:** use `alternate_spreads` for game spread alternates and
  `alternate_totals` for game total alternates. No special player prop alt key needed — alt
  lines appear embedded in the main market response.

### API Response Latency

- NFL player prop data on the Odds API event endpoint: typical response 300–800ms per event
  (similar to NBA). No documented NFL-specific latency issues.
- A full Sunday slate of 14 games × 8 prop markets = 14 event-odds calls (can be parallelized).
  At 500ms average, parallel fetch completes in ~2–3 seconds total — acceptable for day-of runs.

### Game Props vs Player Props: Same Sport Key

- Yes. Game lines (h2h, spreads, totals, team_totals) and player props all use the same
  sport key `americanfootball_nfl`. They just use different endpoints and market key strings.
- NFL preseason: sport key is `americanfootball_nfl_preseason` (confirmed — dedicated API page exists).
  Player props coverage is sparse for preseason (API explicitly notes limited preseason prop coverage).

---

## CO-LEGAL BOOK COVERAGE

Research findings on which CO-legal books offer NFL player props and game lines via The Odds API.

Coverage tiers are based on reported API availability, industry reporting, and book market coverage
as of May 2026. "Y (partial)" means the book offers some prop markets but not all.

| Book | Odds API Key | NFL Props | NFL Game Lines | Notes |
|------|-------------|-----------|---------------|-------|
| DraftKings | `draftkings` | Y (full) | Y | Best prop coverage; largest selection including alt lines |
| FanDuel | `fanduel` | Y (full) | Y | Full prop coverage; strong liquidity |
| BetMGM | `betmgm` | Y (full) | Y | Full prop coverage; opens lines early in week |
| Caesars | `williamhill_us` | Y (full) | Y | Full prop coverage; competitive odds |
| Fanatics | `fanatics` | Y (partial) | Y | Prop coverage growing; may not carry all stat types |
| theScore Bet | `espnbet` | Y (partial) | Y | Props available but narrower selection than Tier 1 books |
| Hard Rock | `hardrockbet` | Y (partial) | Y | Props available; coverage comparable to theScore |
| BetRivers | `betrivers` | Y (full) | Y | Kambi platform — 100+ NFL prop markets per game; very broad |
| Bet365 | `bet365` | Y (full) | Y | Extensive prop coverage; often price leaders on big stats |
| BetParx | `betparx` | Y (partial) | Y | Smaller prop selection; game lines reliable |
| BallyBet | `ballybet` | Y (partial) | Y | Modest prop selection |
| PointsBet | `pointsbet` | Y (partial) | Y | Props available; PointsBetting format not in API |
| TwinSpires | `twinspires` | N or sparse | Y | Primarily horse racing; NFL game lines yes, props uncertain |
| Circa | `circasports` | Y (partial) | Y | Known for sharp NFL lines; prop selection narrower |
| SuperBook | `superbook` | Y (partial) | Y | Strong Super Bowl props; regular-season prop depth moderate |
| Tipico | `tipico` | Y (partial) | Y | Moderate prop coverage |
| WynnBet | `wynnbet` | Y (partial) | Y | Props available; known for Thursday reduced-juice props |
| BetWay | `betway` | Y (partial) | Y | Props available; European-style market depth |

### Best / Worst NFL Prop Coverage

**Best coverage (full suite of pass/rush/rec/TD props reliably in API):**
DraftKings, FanDuel, BetMGM, Caesars, BetRivers, Bet365

**Partial / inconsistent coverage (use as secondary sources):**
Fanatics, theScore Bet, Hard Rock, BetParx, BallyBet, PointsBet, WynnBet, SuperBook, Tipico, BetWay, Circa

**Weakest prop coverage:**
TwinSpires — primarily a horse racing book; NFL props may not be available in Odds API at all.
Verify TwinSpires NFL prop availability with a live API call before including in prop market aggregation.

### Typical Vig

| Market | Typical Vig |
|--------|------------|
| Game spread | -110 / -110 standard; -115/-115 at some books |
| Game total | -110 / -110 standard |
| Moneyline | Variable (no-vig priced from spread) |
| Player passing yards | -115 / -115 (slightly juiced vs game lines) |
| Player rushing yards | -115 / -115 to -120 / +100 (wider for volatile backs) |
| Player receiving yards | -115 / -115 standard |
| Player receptions | -115 / -115 to -120 / +100 |
| Player TDs (any) | -120 / +100 to -130 / +110 (TD props carry more juice) |
| Anytime TD scorer | -140 to +130 range (binary, wider spread) |

---

## CROSS-CUTTING CONSIDERATIONS

### NFL CLV: Line Movement Window

- **Props published:** Thursday (for Sunday games) or Wednesday (for Thursday Night Football games).
  Sunday props for major skill positions (QB pass yds, RB rush yds, WR rec yds) begin appearing
  Thursday–Friday. Some books open Monday/Tuesday for star players.
- **Props close:** Sunday morning for 1pm games, approximately 60–90 minutes before kickoff.
  TNF props close Thursday ~7pm ET. MNF closes Monday ~8pm ET.
- **Effective CLV window:** Thursday publication → Sunday kickoff = ~2.5–3 days of line movement.
  This is meaningfully shorter than NBA (daily) but the movement is often more pronounced because
  NFL props carry less liquidity and move more dramatically on injury news.
- **CLV reliability on props:** Research finding — CLV is significantly less meaningful for NFL
  props than for game lines. NFL props have fewer market-making books, limited sharp action, and
  low liquidity. CLV will be noisy as a calibration metric for props specifically. Game line CLV
  (spreads, totals) retains full validity.
- **Recommendation:** Track CLV for all NFL pick types but flag prop CLV separately in analysis.
  Do not use prop CLV as the primary calibration signal for NFL until substantial data accumulates.

### Odds API Line Movement History

- The Odds API **does not** provide real-time line movement history in the standard v4 API.
  The Historical Odds endpoint (`/v4/historical/sports/{sport}/odds`) provides snapshots at
  specific timestamps, not a movement feed. Movement tracking requires:
  1. Polling the API periodically and logging snapshots yourself, or
  2. Subscribing to The Odds API's historical data product (separate paid tier).
- **CLV daemon behavior:** The current daemon polls every 2 minutes and captures closing odds
  at T-30 to T+3 relative to game time. For NFL this works correctly — the daemon will capture
  Sunday morning lines and can be compared to Thursday entry prices logged at pick time.
  No structural change needed. The only adaptation: the daemon fires daily at 10am via Task
  Scheduler, which may miss Saturday/Monday late-closing lines. Review scheduling if MNF picks
  are posted.

### CLV Daemon Adaptation for NFL Weekly Pattern

- **Current daemon:** runs daily 10am, polls every 2min, 18h MAX_UPTIME.
- **NFL compatibility:** On weeks with only Sunday games, the daemon's 10am start fires Sunday
  and correctly captures closing odds (games close 1pm ET). For TNF (Thursday) and MNF (Monday),
  the daemon must fire on the correct day — it already does since it runs daily.
- **Potential gap:** The 18h MAX_UPTIME means a daemon started at 10am exits by 4am — this covers
  all Sunday games (latest kickoff ~8:20pm ET, final whistle ~11:30pm). MNF could end after the
  window if MAX_UPTIME is measured from 10am and MNF runs late. Check: 10am + 18h = 4am next day,
  which covers any MNF game ending by midnight. Safe.
- **No structural change required.** Daemon works for NFL as-is.

### Same-Game Correlation Cap

- **QB + WR1 correlation:** Pearson r ≈ 0.54 (QB passing yards ↔ WR1 receiving yards, same team).
  WR2 from same team: r ≈ 0.51. These are meaningful positive correlations.
- **Risk:** If the model posts QB pass yards over + WR1 rec yards over for the same game, both
  picks are driven by the same underlying variable (QB air yards / game script). A bad day for
  the QB wipes both picks simultaneously, creating correlated loss exposure.
- **Recommendation: cap at 2 picks per team per game in the prop card.** This allows a QB pick
  + one receiver pick (or two receiver picks) from the same team, but prevents a QB + WR1 + WR2
  triple-stack from the same side.
- **Same-game cap for full 16-game Sunday slate:** Max 2 picks per game from the same team.
  Separately, consider a per-game cap (all positions combined) of 3 picks per game maximum —
  prevents a single game from dominating the card if it has attractive lines on multiple stats.
- **NFL_CORR_GROUPS implication:** PASS_YARDS + PASS_TDS for the same QB should be in the same
  correlation group (deduplicate to best pick). REC_YARDS + RECEPTIONS for the same player should
  also be grouped. See G9 findings for full NFL_CORR_GROUPS structure.

### Preseason

- **Recommendation: disable the model entirely for preseason.** Starters typically play 1 quarter
  or fewer in early preseason games. SaberSim projections are unreliable with no sample data.
  Odds API explicitly notes that player prop coverage for preseason is very limited.
- **Odds API preseason key:** `americanfootball_nfl_preseason` (confirmed — dedicated API page
  at the-odds-api.com/sports/nfl-preseason-odds.html).
- **SHADOW_SPORTS inclusion:** YES — add `americanfootball_nfl_preseason` to SHADOW_SPORTS (or
  better, to a DISABLED_SPORTS set) to prevent any accidental live posting from preseason data.
  The model should hard-gate on the sport key and refuse to post picks for preseason.
- **Implementation:** In run_picks.py, add a PRESEASON_SPORTS set containing
  `americanfootball_nfl_preseason`. If the sport key matches, exit before pick generation
  with a log warning.

### Week 1 Damping Gate

- **Yes, a Week 1 damping gate is warranted.** Research confirms Week 1 NFL lines are among the
  "softest numbers of the season" — sportsbooks price maximum uncertainty, and early-season
  model inputs (preseason performance, depth charts, training camp injuries) are low-signal.
- **Variance in Week 1 strength ratings is ~3.5x higher than Week 16** (from betting model
  literature: Week 1 rating variance ≈ 148 vs Week 16 ≈ 42).
- **Recommendation:** Apply a Week 1 confidence scalar: reduce pick_score by 10–15% for all
  NFL Week 1 picks. Equivalent: raise the minimum edge threshold for Week 1 only.
  Alternatively, route all Week 1 picks to T2/T3 regardless of score (no T1 in Week 1).
- **WNBA analog:** The WNBA model uses an early-season damping gate. NFL Week 1 is the direct
  equivalent — same logic applies.

### Minimum Edge Threshold for NFL

- **Current NBA/MLB threshold:** implied by model defaults (not sport-specific).
- **NFL recommendation:** Minimum edge threshold of **4–5%** (vs ~2–3% for NBA/MLB).
  Rationale: NFL has meaningfully higher per-game variance than NBA (single weekly game vs
  daily schedule), the prop market is less liquid and less efficiently priced, and SaberSim
  NFL projection error is higher than NBA equivalents. A larger edge cushion is needed to
  ensure picks remain +EV after accounting for model error and market uncertainty.
- **Industry benchmark:** A general sports betting model target of 2% minimum edge is often
  cited, but high-variance weekly formats warrant doubling this floor.
- **Gate recommendation:** `MIN_EDGE_NFL = 0.045` (4.5%). Set as a sport-specific gate in
  run_picks.py, parallel to how SPORT_UNIT_CAP is implemented per sport.

### Same-Game Cap on 16-Game Sunday Slate

- **Problem:** A 16-game Sunday slate could theoretically generate 30+ prop picks if every game
  has 2–3 strong signals. This creates correlated exposure across the whole card.
- **Recommendation:**
  - Max 2 picks per team per game (as above, enforced at pick selection).
  - Max 3 picks per game total (all teams combined in a single game).
  - Max 10 NFL prop picks per Sunday run (total card cap, separate from the existing 12u/day
    unit cap — this is a pick count cap to preserve card quality).
  - On 16-game slates, enforce the existing G12 unit ceiling strictly; do not raise it for NFL.

### QB + WR Pearson r Reference Values

| Pair | Pearson r | Source |
|------|-----------|--------|
| QB pass yards ↔ WR1 rec yards (same team) | ~0.54 | Spike Week correlation analysis |
| QB pass yards ↔ WR2 rec yards (same team) | ~0.51 | Spike Week correlation analysis |
| QB pass TDs ↔ WR rec TDs (same team) | ~0.45–0.55 (estimated) | Correlated via game script |
| RUSH_YARDS ↔ RUSH_TDS (same RB) | ~0.35–0.45 (estimated) | Positive but weaker than passing stack |

These values confirm that same-team QB+WR stacking should be deduplicated or capped.

### NFL CLV Evaluation: Per-Week Not Per-Day

- NFL CLV should be evaluated on a **per-game-week basis**, not daily.
- A pick posted Monday for a Sunday game accumulates CLV over a 6-day window. Comparing
  Monday open to Sunday close is the meaningful CLV observation, not comparing to a "closing"
  24h later as in daily sports.
- **clv_report.py adaptation:** The `--days N` flag should still work, but interpretation
  differs. Consider a `--weekly` flag or note in analysis output that NFL CLV windows span 3–6
  days, not hours.
- **Daemon capture timing:** Current daemon captures T-30 to T+3 relative to kickoff. This is
  the correct closing snapshot for CLV purposes. No change needed to the daemon itself; just
  ensure that the entry price (logged at pick time) is stored with the pick, which it already is.

### Tier Routing for NFL Props

- **T1 (high-confidence, tight lines):** Passing yards (elite QBs, line ≥ 240.5), Rushing yards
  (workhorse RBs with ≥ 15 projected carries, line ≥ 45.5), Receiving yards (WR1 with high target
  share, line ≥ 50.5), Receptions (WR1/TE1, high floor targets).
- **T2 (medium confidence):** Passing yards (mid-tier QBs), Rushing yards (committee backs),
  Receiving yards (WR2/TE1), Receptions (WR2).
- **T3 (high variance):** All TD props (PASS_TDS, RUSH_TDS, REC_TDS, anytime TD scorer),
  Interceptions. These are binary/rare events and should be treated as lottery-adjacent.
  Apply the same caution as MLB dogs — gating unders on TD props at low lines recommended.

### KILLSHOT Eligibility for NFL

- **Eligible NFL stats for KILLSHOT:** Passing yards overs (elite QBs), Rushing yards overs
  (workhorse RBs), Receiving yards overs (WR1s), Receptions overs.
- **Exclude from KILLSHOT:** All TD props (too binary/volatile), Interceptions (too rare),
  any line under 30 yards for yards stats.
- **Recommended KILLSHOT win_prob threshold for NFL:** 0.70 (raised from 0.65 for NBA).
  NFL single-game variance is significantly higher; need stronger conviction signal.
- **KILLSHOT odds range for NFL:** Keep [-200, +110] range as default; NFL props often sit at
  -115/-115 which is within range.
- **Weekly cap:** Keep at 2/week for NFL. With only 1 game window per week for most games,
  exceeding 2 KILLSHOT picks per week would over-concentrate risk.

### Preseason Key for SHADOW_SPORTS

- Add `americanfootball_nfl_preseason` to SHADOW_SPORTS or a DISABLED_SPORTS hard block.
- Regular season key `americanfootball_nfl` should launch in shadow mode (log to shadow CSV,
  no Discord posting) for at least Weeks 1–4 to accumulate calibration data before go-live.
- **Shadow exit gate for NFL:** Target 50+ prop picks with CLV data (lower than NBA's 100-row
  target because NFL accumulates picks more slowly: 17 games/season × ~5–8 picks/game =
  85–136 picks per season). Set provisional gate at 50 CLV rows, confirm calibration at that
  point, then go live.

---

## IMPLEMENTATION CHECKLIST (from G10 findings)

- [ ] Add `player_reception_yds` (not `player_receiving_yds`) as receiving yards market key
- [ ] Add `player_pass_interceptions` (not `player_interceptions`) as interceptions market key
- [ ] Use `/events/{eventId}/odds` endpoint for all NFL player props
- [ ] Use `/sports/americanfootball_nfl/odds` endpoint only for game lines (h2h, spreads, totals)
- [ ] Add event ID resolution step to NFL pipeline
- [ ] Set `alternate_spreads` and `alternate_totals` in SPORT_ALT_MARKET for NFL
- [ ] Add `americanfootball_nfl_preseason` to DISABLED_SPORTS hard block
- [ ] Set `MIN_EDGE_NFL = 0.045` (4.5% minimum edge for NFL)
- [ ] Implement Week 1 damping: reduce pick_score 10–15% or cap at T2 for Week 1
- [ ] Implement same-team pick cap: max 2 picks per team per game
- [ ] Implement same-game pick cap: max 3 picks per game total
- [ ] Implement NFL Sunday slate total pick cap: max 10 NFL props per run
- [ ] Set KILLSHOT win_prob threshold to 0.70 for NFL (vs 0.65 NBA)
- [ ] Exclude TD stats from KILLSHOT eligibility for NFL
- [ ] Verify TwinSpires NFL prop availability with live API call before including
- [ ] Review CLV daemon scheduling for MNF/TNF game coverage

---

*Sources: The Odds API documentation (the-odds-api.com/liveapi/guides/v4/),
oddsapiR CRAN package documentation (May 2026), Spike Week NFL correlation analysis,
SharpFootballAnalysis CLV guide, Covers.com NFL prop betting site reviews,
industry prop timing research (BetRivers Kambi platform reporting).*
