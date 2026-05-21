# NFL Model Research Prompt

Paste this into ChatGPT Deep Research or Claude with web search. One session covers all markets.

---

I am building a Python sports betting model for NFL. It uses SaberSim CSV projections and
The Odds API for lines. I need you to research and answer all of the following questions
about every NFL market the model will trade. Be specific — give exact numbers, formulas, and
parameters. Vague answers are not useful.

**System config for context:**
- No custom projections for NFL — using SaberSim NFL CSV as the only projection source
- Distributions in use for other sports: Normal (continuous stats), Negative Binomial (overdispersed
  counts), Poisson (low-mean counts). NFL may need different choices per stat.
- BLEND_ALPHA=0.25 for all game lines in other sports (model = line + 0.25×(saber - line))
- CO-legal books: DraftKings, FanDuel, BetMGM, Caesars (williamhill_us), Fanatics, theScore Bet
  (espnbet), Hard Rock (hardrockbet), BetRivers, Bet365, BetParx, BallyBet, PointsBet,
  TwinSpires, Circa, SuperBook, Tipico, WynnBet, BetWay (18 total)
- NFL Odds API sport key: `americanfootball_nfl`
- Target: props + game lines. No parlays for NFL initially.
- Season context: model goes live September 2026 (regular season week 1)

---

## PASS_YARDS (Passing Yards)

Current model: no implementation. Needs distribution, sigma, and gates from scratch.

- What is the empirical per-game passing yards distribution for starting QBs (2022-2024 regular
  season, min 10 starts)? Pull from nflfastR or Pro Football Reference.
- Is Normal the right distribution for passing yards, or is there meaningful skew/kurtosis?
  Fit Normal, Gamma, and Log-Normal. AIC/BIC comparison. Which wins?
- What is the empirical coefficient of variation (CV = σ/μ) for QB passing yards?
  Give a range across QB archetypes (elite: Mahomes/Allen, mid: average starter, weak: backup).
- What are the most common passing yards lines in the market? (e.g., 249.5, 274.5, 299.5)
  Do books move the line or the juice?
- What is the mean absolute error of SaberSim QB passing yard projections vs actual outcomes?
  Direction of bias — does SaberSim over- or under-project?
- Is there a systematic bias on over/under based on opponent defensive ranking or weather?
- Should passing yards unders be gated out (similar to K unders in MLB)? What does the data show?
- What vig do books typically charge on passing yards? (-115/-115 or wider)?
- Which CO-legal books consistently offer player_passing_yards? Is coverage uniform?
- Is there a meaningful DVOA/EPA differential pre-game signal that SaberSim doesn't encode?

---

## RUSH_YARDS (Rushing Yards)

- What is the empirical per-game rushing yards distribution for RB1s (2022-2024, min 8 starts)?
  Pull from nflfastR.
- RB usage is highly game-script dependent. What fraction of per-game rushing yard variance is
  predictable from pre-game data vs random (score differential, weather, etc.)?
  Estimate R² from regression of actual rush yards on pre-game variables.
- Is Normal correct, or does the distribution have a heavy right tail (100+ yard games) that
  requires Gamma or Log-Normal?
- What is the empirical CV for RB1 rushing yards? For RB2/committee backs?
- What are the most common rushing yards lines in the market?
- Does SaberSim project rushing yards for all RBs, or only primary backs? How are committee
  backfields handled?
- Should there be a gate banning rushing yard bets on players with < X% snap share or carry share?
  What is the empirical threshold below which projection accuracy collapses?
- Is WR rushing yards a distinct market with different variance profile (jet sweeps, designed runs)?
- What is the typical WR rushing yards line? Is this consistently available?
- QB rushing yards: is this offered as a separate market from passing? What distribution fits?

---

## REC_YARDS (Receiving Yards)

- What is the empirical per-game receiving yards distribution for WR1s vs WR2s vs TEs vs RBs
  in the passing game (2022-2024, min 8 starts)?
- Is Normal appropriate, or is there meaningful mass at zero (target share games vs no-target games)?
  Consider a hurdle model (P(target=0) × Normal | target>0).
- What is the empirical CV for receiving yards by position tier?
- Are WR receiving yards more or less predictable than QB passing yards? Quantify.
- What are the most common receiving yards lines by position (WR: ~54.5/64.5, TE: ~34.5/44.5)?
- Does target share from SaberSim meaningfully improve receiving yards projection accuracy beyond
  a naive yards-per-game estimate?
- Should there be a minimum line gate for receiving yards (e.g., no bets below 25.5)?
  Where does model accuracy collapse?
- Is the receiving yards market offered on all skill positions (WR/TE/RB receivers) consistently
  across CO-legal books?

---

## RECEPTIONS (Receptions)

- What is the empirical per-game receptions distribution for WR1s vs TEs vs RBs (2022-2024)?
- Receptions is a count stat — is Poisson appropriate, or does the low-count, high-variance
  nature require Negative Binomial? Fit both. AIC/BIC comparison.
- What are the most common receptions lines? (WR1: ~5.5/6.5, TE: ~4.5/5.5, RB: ~3.5/4.5)
- Does the completion-dependency make receptions less projectable than yards?
  (A target that falls incomplete contributes zero receptions but still affects yards from the throw.)
- Are receptions props consistently available across CO-legal books?
- Should there be a gate banning receptions overs at high lines (e.g., ≥7.5) where downside risk
  of injury/negative game script is large?

---

## PASS_TDS (Passing Touchdowns)

Passing TDs are a rare count stat — low mean (~1.7/game for elite QBs), highly game-script dependent.

- What is the empirical per-game PASS_TDS distribution for starting QBs (2022-2024)?
  Give P(TDs=0), P(TDs=1), P(TDs=2), P(TDs=3), P(TDs≥4).
- Is Poisson appropriate, or is PASS_TDS overdispersed? Fit Poisson vs Negative Binomial.
  AIC/BIC. What is the fitted NB dispersion parameter r?
- What is the most common passing TD line in the market? (0.5 over seems universal)
- For line 0.5: what is P(TDs ≥ 1) for a QB projecting 1.5-2.0 TDs? Is this consistently
  priced below actual probability?
- For line 1.5: what is P(TDs ≥ 2)? Is this the better market?
- Does game script (expected score, home/away, Vegas spread) meaningfully affect PASS_TDS
  probability beyond what SaberSim encodes?
- Are passing TD unders viable? What are the typical under odds at line 0.5?
- Should PASS_TDS be gated like HRR in MLB (different WP floors by line bucket)?
- Are passing TD props consistently available on all CO-legal books via The Odds API?

---

## RUSH_TDS + REC_TDS (Rushing and Receiving Touchdowns)

Same binary-ish structure as PASS_TDS but even rarer.

- What is the empirical per-game distribution for RB rushing TDs (2022-2024)?
  Give P(TDs=0), P(TDs=1), P(TDs≥2). What fraction of RB starts result in zero TDs?
- Same for WR/TE receiving TDs.
- Fit Poisson vs Negative Binomial vs Bernoulli (if most outcomes are 0/1).
  What distribution wins for rush TDs? For rec TDs?
- What are the most common lines? (0.5 seems dominant; is 1.5 consistently offered?)
- What NB dispersion parameter r fits rushing TDs? Receiving TDs?
- Should a player-scoring TDs market be gated based on red zone usage or touchdown rate?
  What pre-game variables predict TD probability best beyond raw projection?
- Are anytime TD scorer props a different market key than rushing_tds/receiving_tds on The Odds API?
  What is the exact market key string?
- Are rush_td/rec_td props consistently available across CO-legal books for non-QB skill players?

---

## INT (Interceptions)

INT is a rare, heavily overdispersed count stat for QBs.

- What is the empirical per-game INT distribution for starting QBs (2022-2024)?
  P(INT=0), P(INT=1), P(INT≥2). What fraction of starts result in zero INTs?
- Is Negative Binomial the right distribution? Fit and give parameters.
- What are the most common INT lines in the market? (0.5 seems dominant)
- Is the interceptions market consistently available on CO-legal books via Odds API?
- Does SaberSim project interceptions, or would the model need a fallback?
- Is this market worth building out, or is the pick volume too low to matter?
  What is the typical vig?

---

## COMBO STATS (If Available)

Combo stats (passing + rushing yards, receiving + rushing yards) may be available.

- Does The Odds API offer player_passing_rushing_yards or player_receiving_rushing_yards for NFL?
  What is the exact market key string?
- If offered: what is the distribution of these combo stats? Normal or right-skewed?
- Should combo stats be evaluated as their own market, or derived from component projections?
  Does summing independent component projections produce a reliable composite estimate?
- What CO-legal books consistently offer combo markets?

---

## Game Lines: SPREAD

NFL spreads are the primary market — variable line (-0.5 to -14+).

- What is the actual standard deviation of NFL full-game point differentials (2022-2024)?
  (This is GAME_SIGMA["NFL"]["spread"] in the model)
- What is the standard deviation of NFL game totals (combined score)?
  (GAME_SIGMA["NFL"]["total"])
- What is the standard deviation of NFL team point totals?
  (GAME_SIGMA["NFL"]["team"])
- Is BLEND_ALPHA=0.25 (75% market trust) appropriate for NFL spread, or should it be
  higher (market more efficient in NFL than NBA) or lower (SaberSim has more signal)?
  Quantify by regressing SaberSim vs Vegas vs actual over 2022-2024.
- Are alternate spreads consistently available via The Odds API for CO-legal books?
  What market key? What line range (e.g., ±3 to ±17)?
- Should dog spread bets (positive odds) be gated out in NFL as they are in other sports?
  Is the NFL runline equivalent as lottery-like as MLB/NHL?

---

## Game Lines: TOTAL

- What is the typical NFL total range? (42-52 points)
- What is the standard deviation of NFL game totals empirically?
- Are alternate totals consistently available via Odds API?

---

## Game Lines: TEAM_TOTAL

- Are NFL team totals consistently offered by CO-legal books via Odds API?
  What market key? What is the typical team total range (18-28)?
- Is the blend formula (team_total = line + 0.25×(saber_team - line)) appropriate for NFL?
  Or does SaberSim NFL encode team scoring differently than its MLB/NBA counterpart?
- What is the actual standard deviation of NFL team points scored per game (2022-2024)?

---

## Game Lines: MONEYLINE

- What is the appropriate sigma for NFL ML win probability?
  (Model uses normal_cdf(0, blended_margin, σ) to get win_prob from projected point margin)
- NFL ML odds range is much wider than NBA (-350 to +300 on any given week).
  Does a Normal distribution produce accurate win probabilities across this full range?
- Is NFL ML consistently offered by CO-legal books? Any major book that doesn't offer it?

---

## NFL-Specific Modeling Challenges

These are structural issues unique to NFL that the model must handle.

**Injury timing:**
- NFL injury designations (Q/D/O/IR) are released Wednesday through game-day.
  What fraction of "questionable" players ultimately play? By position?
- What is the typical snap share / target share reduction for a returning Q player vs healthy?
- How close to kickoff does final injury status typically resolve? (1hr before? 90min?)

**Backup/handcuff problem:**
- If an RB is ruled out, does his backup's projection reliably increase by the same amount?
  Or does the team shift to passing game (reducing backup RB upside)?
- What is the empirical backup RB yards/game when a starter is absent?

**Weather:**
- Does wind speed significantly affect passing yards and receiving yards projections?
  At what threshold does it become material (e.g., >15mph, >20mph)?
- Does precipitation affect game totals vs spreads differently?
- Does SaberSim NFL incorporate weather, or is it pure historical average?

**Bye weeks / schedule density:**
- Is there a fatigue or performance effect post-bye week, post-Monday/Thursday night game?
  Quantify if significant.

**Preseason vs Regular Season:**
- Should the model be entirely disabled for preseason (starters rarely play full games)?
- If yes: how does the Odds API distinguish preseason from regular season games?
  What is the sport key for NFL preseason?

---

## Auto-Grading: Results Fetching

The model auto-grades picks via grade_picks.py. NFL needs a data source for actual player stats.

- Does The Odds API offer NFL player prop settlement data post-game?
  If yes: what market key format? How long post-game until results are available?
- Does ESPN's public API (site.web.api.espn.com) offer per-player per-game NFL stat lines?
  If yes: what endpoint? What fields are returned (rushing_yards, receiving_yards, etc.)?
- Does nfl-data-py (Python package) offer same-day post-game player stats?
  What is the typical data lag after game end?
- Name matching risk: NFL player names on The Odds API vs SaberSim vs ESPN may differ
  (e.g., "D.K. Metcalf" vs "DK Metcalf" vs "D K Metcalf"). What is the standard canonicalization?
- For a pick logged as "Cooper Kupp REC_YARDS Under 54.5", what is the minimal grading pipeline?

---

## SaberSim NFL CSV

The model reads SaberSim NFL projections as a CSV. I need to know the exact column structure.

- What column names does SaberSim NFL export in its classic CSV?
  List all columns: Name, Team, Position, Opp, Salary, and all projection columns.
- Are rushing yards, receiving yards, passing yards, TDs all in the CSV?
  What are the exact column header strings?
- Does SaberSim NFL CSV include dk_std (DraftKings standard deviation) for each player?
- Does it include saber_total (projected game total) and saber_team (projected team score)?
- How are QBs, RBs, WRs, and TEs differentiated in the Position column?
  (Is it "QB", "RB", "WR", "TE", or abbreviations like "QB1", "FLEX"?)
- Does SaberSim project passing stats for both QBs and any dual-threat players separately?
- How does SaberSim handle two-QB teams or teams running a committee backfield?
- What time of day does SaberSim publish NFL projections relative to Sunday kickoffs?
  Does it publish on Saturday night, Sunday morning, or earlier?
- Does SaberSim publish separate CSVs for each slate (1pm, 4pm, SNF, MNF, TNF)?

---

## The Odds API: Market Keys and Coverage

- Confirm the exact market key strings for all NFL player prop markets:
  - Passing yards: ?
  - Passing touchdowns: ?
  - Interceptions: ?
  - Rushing yards: ?
  - Rushing touchdowns: ?
  - Receptions: ?
  - Receiving yards: ?
  - Receiving touchdowns: ?
  - Anytime touchdown scorer: ?
  - Combo (passing+rushing yards): ?
  - Combo (receiving+rushing yards): ?
- For each market: is it in the `us` region, `us2` region, or both? (Affects API call structure)
- Are NFL props available via the `/events/{id}/odds` endpoint or the `/sports/{sport}/odds` endpoint?
- Does The Odds API offer alternate lines for NFL props (e.g., alternate passing yards at 225.5)?
  What market key?
- What is the typical API response time for NFL player prop markets? (Latency matters for
  day-of runs)

---

## Book Coverage Matrix

Build this matrix: for each NFL prop market, which CO-legal books consistently offer it,
and what is the typical vig (-115/-115, -120/-110, etc.)?

Markets:
- player_passing_yards
- player_passing_touchdowns
- player_rushing_yards
- player_rushing_touchdowns
- player_receptions
- player_receiving_yards
- player_receiving_touchdowns
- player_interceptions
- anytime_touchdown_scorer (if different from td markets above)
- game spread (full game)
- team totals
- game total

Books to cover: DraftKings, FanDuel, BetMGM, Caesars, Fanatics, theScore Bet, Hard Rock,
BetRivers, Bet365.

---

## Cross-Cutting

**GAME_SIGMA — recommend values for:**
- NFL total (combined score std dev): ?
- NFL spread (point differential std dev): ?
- NFL team total (single team score std dev): ?
- NFL ML (use for win probability): ? (should be same as spread for consistency)

**BLEND_ALPHA:**
- Should BLEND_ALPHA differ for NFL vs other sports (0.25 in MLB/NBA)?
- Does SaberSim carry more or less independent signal in NFL than in NBA/MLB?
  Justify with regression data if available.

**Tier routing — recommend:**
- Which NFL stats belong in T1 (high-confidence, tight-line markets)?
- Which belong in T2 (medium confidence, broader lines)?
- Which belong in T3 (high-variance, lottery-adjacent)?
- Are TDs structurally T3 (like MLB dogs) due to binary/rare outcome profile?

**Gate recommendations:**
- Should there be a gate banning TD unders at low lines (similar to G_K_NO_UNDERS for MLB)?
- Should there be a minimum line gate for any NFL stat (e.g., RUSH_YARDS ≥ 15.5)?
- Should weather data (wind, precipitation) be incorporated as a pick-time gate?
  If yes: what API provides reliable pre-game NFL weather? What threshold kills a pass prop?
- Should the model be gated off entirely for Thursday Night Football (short prep, injury risk)?
  What does the data show on TNF market efficiency vs Sunday games?
- Is there a "first game of the season" variance issue similar to WNBA early-season?
  Should there be a Week 1 damping gate?

**Model risks unique to NFL:**
- Single-game format: one bad game destroys a weekly record. Is daily CLV even meaningful for NFL?
  Or should evaluation be weekly?
- Low n problem: 17 regular season games means Platt refit will take 3+ seasons of picks.
  What n is needed for reliable calibration of NFL win_prob?
- Correlated legs: in a multi-stat card, if QB throws 4 TDs, receiver TDs are correlated.
  Should there be a same-game cap (e.g., max 2 picks per game) for NFL?

**CLV:**
- How does NFL CLV compare to NBA/MLB? Are NFL prop lines less efficient (more CLV opportunity)
  or more efficient (public money moves lines predictably)?
- What is the typical line movement window for NFL props (published Thursday, closed Sunday AM)?
- Does The Odds API capture NFL line movement history? Or only current lines?
