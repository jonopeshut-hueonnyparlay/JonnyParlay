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
- NBA model uses Platt scaling: cal_over_p = sigmoid(PLATT_A × raw + PLATT_B), PLATT_A=1.4988,
  PLATT_B=-0.8102, fitted on 76 prop picks. NFL will need its own policy.
- NBA model applies a blowout sigmoid (max_reduction=0.19) to dampen projections in lopsided games.
- NBA model uses PLAYOFF_RATE_DEFLATORS (pts, ast, fg3m, blk differ from regular season).
- The model uses binary in/out for NBA injuries (Q/GTD counts as out; probabilistic discounting
  is structurally -EV because prop voids on scratches). NFL must define its own injury policy.

---

## PASS_YARDS (Passing Yards)

Current model: no implementation. Needs distribution, sigma, and gates from scratch.

- What is the empirical per-game passing yards distribution for starting QBs (2022-2024 regular
  season, min 10 starts)? Pull from nflfastR or Pro Football Reference. Give mean, median, σ, skew.
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
  Pull from nflfastR. Give mean, median, σ, skew, fraction of games with 0 yards.
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
  in the passing game (2022-2024, min 8 starts)? Give mean, σ, and fraction of zero-target games.
- Is Normal appropriate, or is there meaningful mass at zero (target share games vs no-target games)?
  Consider a hurdle model (P(target=0) × Normal | target>0). Is zero-inflation a real concern?
  What fraction of WR1 games have 0 receiving yards? WR2? TE?
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
  Give P(rec=0), P(rec=1), P(rec=2), P(rec≥5), P(rec≥8).
- Receptions is a count stat — is Poisson appropriate, or does the low-count, high-variance
  nature require Negative Binomial? Fit both. AIC/BIC comparison. What is the fitted NB r?
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
  AIC/BIC. What is the fitted NB dispersion parameter r? (The model needs a concrete NB_R value.)
- What is the most common passing TD line in the market? (0.5 over seems universal)
- For line 0.5: what is P(TDs ≥ 1) for a QB projecting 1.5-2.0 TDs? Is this consistently
  priced below actual probability?
- For line 1.5: what is P(TDs ≥ 2)? Is this the better market?
- Does game script (expected score, home/away, Vegas spread) meaningfully affect PASS_TDS
  probability beyond what SaberSim encodes?
- Are passing TD unders viable? What are the typical under odds at line 0.5?
- Should PASS_TDS be gated like HRR in MLB (different WP floors by line bucket)?
  Recommend minimum win_prob thresholds for each common line bucket.
- Are passing TD props consistently available on all CO-legal books via The Odds API?

---

## RUSH_TDS + REC_TDS (Rushing and Receiving Touchdowns)

Same binary-ish structure as PASS_TDS but even rarer.

- What is the empirical per-game distribution for RB rushing TDs (2022-2024)?
  Give P(TDs=0), P(TDs=1), P(TDs≥2). What fraction of RB starts result in zero TDs?
- Same for WR/TE receiving TDs.
- Fit Poisson vs Negative Binomial vs Bernoulli (if most outcomes are 0/1).
  What distribution wins for rush TDs? For rec TDs?
  Give the fitted NB dispersion parameter r for each. (Concrete value needed — e.g., r=1.2.)
- What are the most common lines? (0.5 seems dominant; is 1.5 consistently offered?)
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
- Is Negative Binomial the right distribution? Fit and give parameters (r, mean).
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
  What is the exact alternate spreads market key string? (The model uses SPORT_ALT_MARKET.)
  What line range (e.g., ±3 to ±17)?
- Should dog spread bets (positive odds) be gated out in NFL as they are in other sports?
  Is the NFL spread dog bet as lottery-like as MLB/NHL dogs?

---

## Game Lines: TOTAL

- What is the typical NFL total range? (42-52 points)
- What is the standard deviation of NFL game totals empirically?
- Are alternate totals consistently available via Odds API? What market key?
- NFL totals: does a blowout game cause public over-under bias post-halftime? (Not needed —
  but does the pre-game model need to account for weather-driven total suppression?)

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
- NFL does NOT have a fixed runline equivalent like MLB (±1.5) or NHL (±1.5). Confirm: does
  the model simply use ML no-vig directly as the market anchor for NFL ML (same as NBA),
  or is there a fixed-spread equivalent to be aware of?

---

## Distribution Parameters (NB_R Values)

The model's NB_STATS dict maps stat → True/False, and NB_R maps stat → dispersion parameter r.
For NFL the model needs a concrete r for every count stat. Research and recommend:

- PASS_TDS NB r: (expected ~2-4; give empirical fit)
- RUSH_TDS NB r: (even rarer than PASS_TDS; expected r < 2)
- REC_TDS NB r: (similar rarity to RUSH_TDS)
- RECEPTIONS NB r: (higher volume count; expected r 5-15)
- INT NB r: (very overdispersed; expected r < 2)

For each: confirm NB is better than Poisson via AIC/BIC. If Poisson is better for any stat,
say so explicitly — the code needs to know which stats go in NB_STATS and which use Poisson.

For continuous stats (PASS_YARDS, RUSH_YARDS, REC_YARDS): Normal is the default.
Is there a stat where Normal is clearly wrong and a different family fits better?
If so, the model will need a custom distribution path — quantify how wrong Normal is.

---

## Platt Calibration Policy

The NBA model applies Platt scaling (sigmoid calibration) to raw over-probabilities.
PLATT_A=1.4988, PLATT_B=-0.8102, fitted on 76 prop picks.

- Should the NFL model share the NBA Platt params initially (before enough NFL-specific picks
  accumulate), or use identity calibration (A=1.0, B=0.0) as a safer default?
- How many NFL prop picks are needed to reliably refit Platt for NFL-specific calibration?
  (NBA used 76; NFL has 17 games/season, maybe 5-10 picks/game → ~1-2 seasons before refit)
- Is Platt scaling even appropriate for count stats (TDs, INT, RECEPTIONS) where the raw
  probability comes from a discrete distribution rather than Normal CDF?
  Should count stats use identity calibration regardless?
- What is the typical direction of raw over-probability miscalibration for NFL props?
  (Does the raw model systematically over-estimate overs, under-estimate overs, or is it
  stat-dependent?)

---

## NFL Correlation Groups (NFL_CORR_GROUPS)

The NBA model uses MLB_CORR_GROUPS (effectively PITCHER_STATS / BATTER_CORR_STATS) to enforce
a per-player dedup: if two picks for the same player involve the same hidden variable,
only the best-scoring one is kept. Example: PTS + FG3M over are both driven by scoring volume,
so they're in the same correlated group and can't both post.

NFL needs its own correlation groups. Define which stat pairs are driven by the same hidden
variable and should trigger single-pick-per-player dedup:

- Are PASS_YARDS + PASS_TDS correlated enough that posting both for the same QB is picking
  the same edge twice? What is empirical Pearson r between QB passing yards and TD count?
- Are REC_YARDS + RECEPTIONS correlated for the same player? What is the empirical r?
- Are RUSH_YARDS + RUSH_TDS correlated for the same RB? What is the empirical r?
- Which stat pairs should be grouped (same correlated group → dedup to best pick)?
- Which stat pairs are independent enough to allow posting both for the same player?
- What threshold Pearson r should trigger grouping? (NBA uses implicit grouping above ~0.4)

Provide a concrete recommended NFL_CORR_GROUPS structure, e.g.:
  - Group A (QB volume): PASS_YARDS, PASS_TDS → dedup per QB
  - Group B (WR volume): REC_YARDS, RECEPTIONS → dedup per WR/TE
  - Group C (RB volume): RUSH_YARDS, RUSH_TDS → dedup per RB
  - Independent stats that can stack: INT (uncorrelated with volume)

---

## Blowout / Garbage Time Sigmoid

The NBA model applies a blowout sigmoid: when projected point differential is large, it dampens
player stat projections (less effort in garbage time). MLB has no equivalent (score doesn't
affect pitcher stats much). NFL is the most important case.

- In NFL, trailing QBs throw MORE in garbage time (garbage passing yards = stat inflation).
  Leading RBs rush MORE in garbage time (clock management = stat inflation for ground game).
  This means the blowout effect is DIRECTIONAL in NFL, not just a dampening.
- For trailing QB passing yards: what is the empirical excess yards per game vs expected when
  trailing by ≥14 points at game start (i.e., games where the QB team is a heavy underdog)?
  Quantify: e.g., "dog QBs average +18% passing yards vs projection due to garbage time".
- For leading RB rush yards: what is the empirical excess rush yards when team is a ≥14pt favorite?
- For trailing RB rush yards: what is the empirical reduction when team is a heavy dog (team
  abandons run game)?
- For WR rec yards/receptions: does garbage time inflate receiver stats for the trailing QB?
- Should the model apply a DIRECTIONAL game script adjustment (increase some projections in
  blowout scenarios rather than uniformly dampening)?
- What is the recommended sigmoid: k, midpoint, and direction per stat?
  Or should it be simpler: a flat multiplier above a spread threshold?
- At what spread threshold (e.g., ≥10 points, ≥14 points) does the game script effect
  become statistically significant?

---

## Home/Away Delta for Player Props

The NBA model applies _HOME_AWAY_DELTA: pts=+2.35%, reb=+0.88%, ast=+3.33% for home team.

- What is the empirical home/away performance delta for NFL player props (2022-2024)?
  - PASS_YARDS: home QB advantage? (quantify as % of projection)
  - RUSH_YARDS: home RB advantage?
  - REC_YARDS: home WR advantage?
  - RECEPTIONS: home player advantage?
  - PASS_TDS: home QB advantage in TD rate?
- Is the NFL home field advantage large enough to materially affect prop projections,
  or is it already encoded in SaberSim?
- Does SaberSim NFL explicitly encode home/away in its projections?
  If yes, should the model skip the delta adjustment to avoid double-counting?
- What is the strongest home field advantage in the league (loudest stadiums, altitude effects)?
  Should there be stadium-specific adjustments, or is a league-average delta sufficient?

---

## Opponent Defensive Quality Adjustment

The NBA model uses team_def_splits (opponent defensive stats by position group) to adjust
player projections. SaberSim NBA encodes matchup quality. Does SaberSim NFL do the same?

- Does SaberSim NFL CSV adjust QB/RB/WR/TE projections for opponent defensive quality?
  (e.g., does a WR vs the #32 CB defense get more yards than vs the #1 defense?)
- If SaberSim encodes this, no further adjustment is needed. Confirm: is SaberSim's
  opponent adjustment statistically better than naive season-average projections?
- If SaberSim does NOT encode this: what is the best pre-game signal for opponent defensive
  quality (DVOA, EPA/play allowed, points allowed/game)?
- What additional adjustment should the model apply, if any?
  Example: vs bottom-5 pass defense, project QB passing yards ×1.12; vs top-5, ×0.88.
  Quantify the multipliers from 2022-2024 data.
- Is opponent adjustment more important for some stats than others?
  (TDs are highly red-zone dependent; yards may be more consistent across matchups.)

---

## Role Tiers (RB1/RB2/WR1/WR2/WR3/TE1/TE2)

The NBA model classifies players into role tiers (starter/sixth_man/rotation/spot/cold_start)
and applies different minute scalars, confidence weights, and gate thresholds per tier.

NFL players don't have "minutes" but do have role tiers that affect projection reliability:

- What is the best proxy for NFL player role tier without custom projection data?
  (SaberSim salary? snap share projection? target share projection? DraftKings price?)
- Define the recommended tier structure:
  - RB1 (workhorse back, ≥X% snap share or ≥Y salary): high confidence, lower CV
  - RB2 (committee or handcuff): medium confidence, higher CV
  - WR1 (primary receiver, ≥X target share): high confidence
  - WR2 (secondary receiver): medium confidence
  - WR3/slot: lower confidence, noisier target share
  - TE1 (primary TE, ≥X targets/game): medium confidence
  - TE2 (blocking TE, ≤2 targets/game): avoid — model likely to misfire
  - QB (starter): high confidence; backup QB: avoid/gate off
- Should there be a salary or projection floor below which the model refuses to post
  a pick for that player? (e.g., DK salary < $4000 = noise, skip)
- Should role tier affect the tier routing (T1/T2/T3) in the pick card?
  (e.g., all RB2 picks are capped at T2 regardless of edge)

---

## Kickers and D/ST

- Should the model explicitly skip kicker props and D/ST props?
  (Kicker yards are not meaningful; D/ST sacks/INT are too low volume for reliable props.)
- Are kicker/D/ST player props even available on The Odds API for NFL?
  If yes, what are the market keys, and should they be gated out?
- Are there any D/ST prop markets that ARE worth modeling (e.g., sacks total, INT total
  for a defense)? If so, what distribution fits sacks? INT?

---

## STAT_CAP and SPORT_UNIT_CAP

The model defines STAT_CAP (max picks per stat per run) and SPORT_UNIT_CAP (max units
per single pick, per sport). Example: SOG is capped at 6 picks/run; NBA is 8u max/pick.

- For NFL: what is the recommended STAT_CAP per stat?
  - PASS_YARDS: max X picks per run (considering 1-2 starting QBs per game)
  - RUSH_YARDS: max X picks per run
  - REC_YARDS: max X picks per run
  - RECEPTIONS: max X picks per run
  - PASS_TDS: max X picks per run
  - RUSH_TDS: max X picks per run
  - REC_TDS: max X picks per run
  - INT: max X picks per run
- For NFL SPORT_UNIT_CAP: what is the maximum reasonable unit size per single NFL pick,
  given the weekly format and low game count vs daily NBA/MLB?
  (NBA = 8u max/pick; NHL = 5u max/pick — NFL should be lower?)
- Is there a total-day unit cap issue for NFL? On a 16-game Sunday slate, the card could
  have 30+ picks. Should there be a per-day total cap stricter than the existing 12u/day?

---

## KILLSHOT Eligibility

KILLSHOT is the highest-conviction tier. Current gate: tier=T1, score≥90, win_prob≥0.65,
odds ∈ [-200, +110], stat ∈ {PTS, AST, SOG, 3PM}. Max 2/week.

- Which NFL stats should be eligible for KILLSHOT?
  (PASS_YARDS overs? RUSH_YARDS overs? RECEPTIONS overs? TDs are too binary/volatile?)
- Should the KILLSHOT win_prob threshold be higher for NFL than for NBA (0.65)?
  Given the weekly format and single-game variance, should it be 0.70+?
- Should KILLSHOT odds range be different for NFL? NFL props often have wider juice.
- Is 2 KILLSHOT/week appropriate for NFL, or should it be 1/week given lower pick volume?

---

## SHADOW_SPORTS Recommendation

The model has a SHADOW_SPORTS set: sports in this set log picks to a shadow file but do not
post to Discord. MLB was in shadow for months until calibration validated.

- Should NFL launch in shadow mode first? Given the low game count (17 games/season),
  how many weeks of shadow data are needed to validate calibration?
- What is the minimum NFL pick sample (N games, N picks) to meaningfully compare
  projected win_prob vs actual win rate?
- At what point should NFL exit shadow mode and post to Discord?
  (NBA exited shadow at ~100 CLV rows; NFL CLV data accumulates much slower.)

---

## Overtime Effects on Props

NFL overtime rules (10-minute OT period) can affect prop settlement, especially for season-long
stats, but game-level props typically settle based on full game including OT.

- For PASS_YARDS, RUSH_YARDS, REC_YARDS: does The Odds API settle these props including
  OT stats or regular time only?
- For game line props (spread, total, ML): do NFL sportsbooks settle at end of regulation,
  or including OT? (This affects ML and total pick grading.)
- What fraction of NFL games go to OT (2022-2024)? Is this large enough to materially bias
  any projection?
- Should the model add an OT probability adjustment to game line projections?
  (NBA model does not do this — is NFL OT frequent enough to matter?)

---

## Playoff vs Regular Season Adjustments

The NBA model applies PLAYOFF_RATE_DEFLATORS: pts=0.934, ast=0.870, fg3m=0.948, blk=1.152
(fitted on playoff backtest). These capture systematic differences in play style.

- Does NFL require equivalent playoff scalars on top of SaberSim projections?
- Empirically: do NFL players' per-game stat rates change in the playoffs vs regular season?
  - QB passing yards: playoff average vs regular season average (2018-2024)?
  - RB rushing yards: playoff average vs regular season average?
  - WR receiving yards: playoff average vs regular season average?
- Is this effect large enough to be material (>5% direction shift) or is it noise?
- If material: recommend playoff scalars analogous to NBA's PLAYOFF_RATE_DEFLATORS.
- Recommendation: should the model launch with no playoff adjustments initially (wait for
  in-model data), or apply literature-based scalars from day one?

---

## Thursday/Monday/Saturday vs Sunday Slate Differences

NFL has multiple weekly slots with different characteristics.

- Does short-week fatigue (Thursday Night Football) materially affect player stats vs
  Sunday games? Quantify: empirical passing yards / rushing yards on TNF vs Sunday.
- Does TNF have worse market efficiency (public money more predictable, more CLV available)?
  Or is it the reverse (line setters are more careful with the primetime audience)?
- SNF (Sunday Night) and MNF (Monday Night): any systematic differences from afternoon games?
- Saturday games (late season, Week 15-18): are these a distinct market?
- Should there be a short_week_flag gate that reduces confidence (lowers pick_score) on TNF?
- Does SaberSim NFL publish separate CSVs for TNF vs Sunday slate, or one combined slate?
  How does the model distinguish TNF game from Sunday games in the CSV?

---

## Zero-Inflation / Hurdle Models

Some NFL stats have meaningful probability of exactly zero (player gets injured, benched,
or game-scripted out of action entirely).

- For REC_YARDS: what fraction of WR1 games result in exactly 0 receiving yards (2022-2024)?
  For WR2? For TE1? For RB receivers?
- For RUSH_YARDS: what fraction of RB games result in exactly 0 rush attempts (2022-2024)?
  (Committee backs, injury scratches, role changes.)
- For RECEPTIONS: what fraction of WR games result in 0 receptions (2022-2024)?
- If zero-inflation is >5% for any stat/position tier: should the model use a hurdle model
  (separate P(zero) × conditional distribution | nonzero) instead of standard Normal/NB?
  Quantify: how much better does a hurdle model fit vs standard Normal on AIC/BIC?
- Is the zero probability already partially captured by SaberSim (low projection = rare usage),
  or does SaberSim systematically project non-zero when the actual outcome is often zero?
- Decision: if hurdle model is better, should the Python implementation use a custom hurdle
  class, or is a gate (min_proj threshold below which we skip the pick) a sufficient proxy?

---

## Context Sanity Layer Keywords

The model has an optional context sanity layer (--context flag) that uses Claude + web search
to flag OUT/scratched players. Currently uses NBA keywords (active/inactive designation).

NFL has different injury terminology:

- What are the NFL official designations that mean "confirmed playing" vs "confirmed out"?
  (Active list? Inactive list? Practice report statuses: Q, D, O, IR, DNP, LP, FP?)
- When is the official NFL inactive list released on game day? (Exactly 90 minutes before
  kickoff for Sunday games — confirm this.)
- What language should the context scanner search for to confirm a player is OUT?
  Examples: "listed as inactive", "ruled out", "placed on IR", "will not play"
- What language should it search for to confirm a player IS ACTIVE?
  Examples: "active", "off injury report", "full participant"
- Are there edge cases (game-day scratches not on injury report) that the scanner should
  catch from beat reporter tweets?
- Should the context layer also flag weather emergencies (hurricane postponements, dome vs
  outdoor stadium) that affect game-level picks (totals, spreads)?

---

## Injury Status Policy (Binary vs Probabilistic)

The model uses binary in/out for NBA injuries because prop bets void when a player is
scratched — probabilistic discounting is structurally -EV (you lose the edge if they play
but gain nothing from the void if they sit).

For NFL:

- Do NFL sportsbooks void player prop bets if the player doesn't play, or do they grade the
  bet as a loss (0 yards = under wins)?
  - Clarify by book: DraftKings, FanDuel, BetMGM, Caesars — does each void or grade?
- If books grade (don't void): the binary in/out policy is WRONG for NFL props. A player
  who is "Questionable" and plays 60% of the time but projects 80 yards when healthy should
  have their expected value discounted by P(plays)×E[yards | plays]. Confirm whether this
  applies to NFL or not.
- If some books void and some grade: what is the standard behavior across CO-legal books?
  Should the model use the majority behavior and flag exceptions?
- What fraction of "Questionable" players ultimately play for each position (2022-2024)?
  Give P(plays | Q) for QB, RB, WR, TE separately.
- What is the typical snap share / stat rate reduction for a returning Q player vs healthy?
  (e.g., "Q players play but produce at 78% of healthy rate on average")

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
- For game line picks (spread, total, ML): can grade_picks.py use ESPN's scoreboard endpoint
  (which it already uses for NBA/MLB) to get NFL final scores? What is the ESPN NFL
  sport key for their API?

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
- Does SaberSim NFL CSV include a saber_opp column (opponent team abbreviation)?
  (Needed for DVOA/opponent quality lookups if the model does its own adjustment.)
- What team abbreviations does SaberSim NFL use? Do they match Odds API team names?
  Give the full mapping if they differ.

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
  What market key? (The model uses SPORT_ALT_MARKET dict — need the NFL alternate spread key too.)
- What is the exact alternate spread market key for NFL? (e.g., `americanfootball_nfl_alternate_spreads`?)
- What is the typical API response time for NFL player prop markets? (Latency matters for
  day-of runs)
- Are NFL game props (total, spread, ML) under the same `americanfootball_nfl` sport key as player
  props, or different endpoints?

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
- alternate spread
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
- Should there be a minimum edge threshold different from NBA/MLB for NFL picks?
  (NFL variance is higher, so the model needs more cushion to be profitable.)

**Model risks unique to NFL:**
- Single-game format: one bad game destroys a weekly record. Is daily CLV even meaningful for NFL?
  Or should evaluation be weekly? How does the model evaluate CLV on a per-week basis?
- Low n problem: 17 regular season games means Platt refit will take 3+ seasons of picks.
  What n is needed for reliable calibration of NFL win_prob?
- Correlated legs: in a multi-stat card, if QB throws 4 TDs, receiver TDs are correlated.
  Should there be a same-game cap (e.g., max 2 picks per game) for NFL?
  What is the empirical correlation between QB passing TDs and WR receiving TDs?

**CLV:**
- How does NFL CLV compare to NBA/MLB? Are NFL prop lines less efficient (more CLV available)
  or more efficient (public money moves lines predictably)?
- What is the typical line movement window for NFL props (published Thursday, closed Sunday AM)?
- Does The Odds API capture NFL line movement history? Or only current lines?
- Given that NFL games are once/week, should CLV be evaluated game-by-game (not daily)?
  Does the existing CLV daemon (polls every 2 min, runs daily) work for NFL, or does it need
  to be adapted for weekly polling patterns?

**Same-Game Correlation Cap:**
- QB and WR on the same team have correlated outcomes (QB pass yards ↔ WR rec yards).
  Should there be a cap on same-team stacking in the prop card?
  (e.g., max 2 picks involving players from the same team per game)
- What is the empirical Pearson r between: QB pass yards and WR1 rec yards? QB TDs and WR rec TDs?
- Should same-player picks across correlated stats (PASS_YARDS + PASS_TDS for same QB)
  be deduplicated to only the best-scoring pick (like NBA_CORR_GROUPS)?

**Preseason:**
- Should the model be entirely disabled for preseason (starters rarely play full games)?
- If yes: how does the Odds API distinguish preseason from regular season games?
  What is the sport key for NFL preseason? (Expected: `americanfootball_nfl_preseason`)
- Should SHADOW_SPORTS include the preseason key to prevent accidental live posting?
