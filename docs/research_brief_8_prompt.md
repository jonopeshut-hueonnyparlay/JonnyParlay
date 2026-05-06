# Research Brief 8 — JonnyParlay NBA Projection Engine
## Performance Review, Playoff Refinement & Next-Level Architecture
### Deep Research Prompt — May 2026

---

## CONTEXT

This is the 8th research iteration on a live NBA projection engine + sports betting operation.
Previous briefs covered: architecture (B1), calibration (B2), stat decomposition/minutes (B3/B4),
playoff scalars + rate deflators (B5/B6), empirical constant refits (B7).

**What changed since Brief 7 (May 3 2026):**
- Injury system now functional — NBA PDF "Last, First" name format fixed; active-team filter live
- Playoff round 2 underway — more data accumulating on playoff dynamics
- CLV daemon fully hardened — STALE marker, date-key dedup, STALE exclusion from retry
- Custom projector running in shadow mode — pick_log_custom.csv accumulating observations
- All audit findings closed — 903 tests passing, 0 failures
- `PLAYOFF_MINUTES_SCALAR` rotation 0.786→0.550, spot 0.902→0.350 (refitted May 3)
- `_REB_RATE_PRIOR` updated to empirical G/F/C values (May 3)
- `_HOME_AWAY_DELTA` updated to empirical values across all 6 stats (May 3)
- `cold_start` sub-types: taxi/returner/new_acquisition with per-subtype minute caps (May 3)
- `constrain_team_totals()` live — Vegas team totals applied as projection constraint
- `_derive_team_totals()` live — fills in when Odds API returns no explicit team totals (spread ± total/2)

**The critical open gate:** Custom projector go-live requires ~100 CLV shadow observations
to formally compare custom vs SaberSim CLV. This has not yet accumulated.

---

## CURRENT SYSTEM BENCHMARKS (as of May 5, 2026)

### Live Betting System (pick_log.csv — Apr 14 to May 4, 2026 — 19 dates, 153 total rows)

**Overall performance — Primary + Bonus picks (graded only):**

| Metric | Value |
|--------|-------|
| Total graded | 116 picks (68W-45L-3P) |
| Hit rate | **60.2%** |
| Net P/L | **+26.00u** |
| Win prob: winners avg | 0.6803 |
| Win prob: losers avg | 0.6754 |
| Discrimination gap | +0.0049 (marginal — still near zero) |

**Hit rate by tier:**

| Tier | W-L | Hit Rate | n |
|------|-----|----------|---|
| T1 | ~23-18 | 56.1% | 41 |
| T1B | ~9-7 | 56.2% | 16 |
| T2 | ~20-8 | **71.4%** | 28 |
| T3 | ~13-10 | 56.5% | 23 |
| KILLSHOT | 3-2 | 60.0% | 5 |

**Hit rate by stat:**

| Stat | Hit Rate | n |
|------|----------|---|
| PTS | **73.1%** | 26 |
| SOG | 61.3% | 31 |
| 3PM | 56.0% | 25 |
| REB | 52.9% | 17 |
| AST | 50.0% | 12 |

**Direction split:**

| Direction | Hit Rate |
|-----------|----------|
| Overs | 54.3% |
| **Unders** | **65.2%** |

Significant under outperformance — model may be systematically underestimating lines or the over pool is more sharply priced.

**Parlay / specialty run types:**

| Run type | Hit rate | P/L |
|----------|----------|-----|
| SGP | 21.7% | -3.75u |
| Daily Lay | 30.0% | -2.50u |
| Longshot | 25.0% | -0.50u |

**CLV — SaberSim live picks (as of May 5, 2026):**

| Metric | Value |
|--------|-------|
| Total CLV observations | 31 (up from 7 in Brief 6) |
| Mean CLV | **+0.350%** |
| Picks with positive CLV | 8/31 = **25.8%** |
| Coverage rate | ~21% of all picks captured |

Note: mean CLV is positive (+0.35%) but beat-close rate is only 25.8% — indicating a few large positive CLV picks are pulling the mean up while the majority of captured picks are negative or zero.

**Known structural issues (updated):**
- Win_prob discrimination: winners=0.6803, losers=0.6754 — still near-zero separation on n=116
- Platt calibration: A=1.4988, B=-0.8102 — fit on n=76, cannot refit (double-calibration design flaw)
- T2 outperforming T1 (71.4% vs 56.1%) — counterintuitive tier ordering persists
- CLV coverage only ~21% — daemon captures about 1 in 5 picks
- Unders systematically outperforming overs (+10.9 pp gap) — possible systematic bias

**Custom projector shadow log:** `pick_log_custom.csv` does not yet exist. 0 custom CLV observations. Go-live gate requires ~100.

### Projection Accuracy (projections.db — Round 1 playoffs only, n=459 player-game rows)

| Stat | MAE | Bias (proj − actual) |
|------|-----|----------------------|
| PTS | 4.884 | **+0.228** (slight over) |
| MIN | 5.632 | **+0.336** (slight over) |
| REB | — | **−0.199** (under) |
| AST | — | **+0.068** (slight over) |
| STL | — | **−0.065** (slight under) |
| BLK | — | **−0.050** (slight under) |
| TOV | — | **−0.125** (under) |

All biases within ±0.35 — materially improved vs Brief 6's −0.620 overall bias. REB remaining the only stat with consistent underestimation. TOV underestimation likely reflects lower-than-expected pace in playoff games.

### Custom Projection Engine State (May 5, 2026)
**Model constants in production:**

| Parameter | Value | Source |
|-----------|-------|--------|
| REGULAR_SEASON_STAT_SCALAR: PTS | 1.000 | Backtest seed=42 |
| REGULAR_SEASON_STAT_SCALAR: AST | 1.005 | Trimmed from 1.013 |
| REGULAR_SEASON_STAT_SCALAR: REB | 1.031 | Backtest |
| REGULAR_SEASON_STAT_SCALAR: FG3M | 1.019 | Backtest |
| REGULAR_SEASON_STAT_SCALAR: BLK | 1.043 | Trimmed from 1.064 |
| REGULAR_SEASON_STAT_SCALAR: STL | 1.000 | Unvalidated |
| REGULAR_SEASON_STAT_SCALAR: TOV | 1.000 | Unvalidated |
| PLAYOFF_MINUTES_SCALAR: starter | 1.068 | 459 rows, Apr 18-29 |
| PLAYOFF_MINUTES_SCALAR: sixth_man | 0.909 | 459 rows, Apr 18-29 |
| PLAYOFF_MINUTES_SCALAR: rotation | 0.550 | 535 rows, refitted May 3 |
| PLAYOFF_MINUTES_SCALAR: spot | 0.350 | 535 rows, refitted May 3 |
| PLAYOFF_MINUTES_SCALAR: cold_start | 1.000 | Unvalidated |
| LEAGUE_AVG_PACE | 100.22 | 2024-25 official |
| LEAGUE_AVG_PACE_PO | 96.5 | Estimate |
| _REB_RATE_PRIOR: G | 0.058 reb/min | Empirical |
| _REB_RATE_PRIOR: F | 0.079 reb/min | Empirical |
| _REB_RATE_PRIOR: C | 0.133 reb/min | Empirical |
| DK_STD floor: starter | 4.0 | Heuristic |
| DK_STD floor: rotation | 3.5 | Heuristic |
| REGULAR_SEASON_MINUTES_SCALAR: starter | 1.056 | Backtest |
| REGULAR_SEASON_MINUTES_SCALAR: rotation | 1.035 | Backtest |
| REGULAR_SEASON_MINUTES_SCALAR: spot | 1.700 | Backtest (floor=1.200) |
| REGULAR_SEASON_MINUTES_SCALAR: cold_start | 0.940 | Backtest |
| Platt: A | 1.4988 | n=76 props |
| Platt: B | -0.8102 | n=76 props |

**Known STL/TOV gap:** Both scalars are 1.000 and have never been validated on backtest data.
The STL model uses pace_factor; the evaluator (research tool) uses opp_tov_fac — these diverge.

---

## RESEARCH QUESTIONS FOR BRIEF 8

Please research every question below as deeply as possible using academic literature,
sports analytics research, sharp betting literature, and industry best practices.
Where a question references a specific system constant, assess whether that constant
is well-calibrated, and recommend a specific improvement with implementation guidance.

---

### SECTION 1: PLATT CALIBRATION — DESIGN FLAW & REPAIR

**Q1. The double-calibration problem.**
My system stores post-Platt `win_prob` in pick_log.csv, but the Platt fitter
(`calibrate_platt.py`) reads `win_prob` from pick_log as its training target,
treating it as the raw over_p input. This means the fitter is trying to calibrate
an already-calibrated probability — it's fitting a Platt transform on a Platt-transformed
output. What is the mathematical consequence of double-calibrating a probability? Does it
systematically compress or expand probabilities toward the mean? What is the correct
design pattern for a production system that needs to: (a) log a human-readable probability,
(b) periodically refit Platt constants on historical data? Should `over_p_raw` be logged
separately, or should there be a different architecture entirely?

**Q2. Minimum sample for stable Platt constants.**
Current: A=1.4988, B=-0.8102, n=76 props, Brier=0.06. What is the published minimum
sample for stable Platt scaling on sports probability models? At what n does the 95% CI
on A and B narrow to within ±10% of the point estimate? Should I refit now at ~100 picks,
or wait for a larger sample? What is the risk of overfitting on n=100?

**Q3. Isotonic regression as Platt alternative.**
Platt scaling assumes the raw model outputs are well-ordered (monotonic) and only need
a sigmoid transformation. But live data (n=116) shows near-zero discrimination between
winners and losers (win_prob winners=0.6803, losers=0.6754 — gap of just 0.0049) — which
means the model outputs may not be well-ordered at all. In this case, is Platt scaling the
wrong tool? Should isotonic regression or Venn predictors be used instead? What is the
published research on calibration method selection when discrimination is poor?

**Q4. What does Brier = 0.06 actually mean?**
The system achieves Brier = 0.06 on n=76 props. A coin flip at 50/50 has Brier = 0.25.
The "no-skill" baseline for props with mean win_prob ~0.695 would be approximately
0.695 × (1-0.695) = 0.212. So Brier=0.06 is substantially better than baseline.
But: is Brier=0.06 good for a sports prop model? What do published NBA prop models achieve?
Is there a published benchmark for player prop Brier scores (e.g., from ESPN, DraftKings
internal models, or academic literature)?

---

### SECTION 2: WIN_PROB DISCRIMINATION — THE ZERO-SEPARATION PROBLEM

**Q5. Is n=116 still too small to detect discrimination?**
Live data now shows winners avg win_prob=0.6803 vs losers=0.6754 (n=116 graded picks).
The gap has grown slightly from Brief 6's 0.695 vs 0.696 on n=80, but is still near zero.
Given that the model's outputs are mostly in the range [0.65, 0.75], what is the minimum
sample size n to detect a meaningful AUC difference (say, AUC=0.60) with 80% power
at α=0.05? How many more graded picks are needed before this test is informative?

**Q6. AUC as the discrimination metric.**
The win_prob range [0.65, 0.75] suggests the model only bets high-confidence picks.
In this narrow range, what is the expected AUC if the model is genuinely adding value?
If all picks have win_prob in [0.65, 0.75] and the true calibration is correct, should
we expect AUC ~0.55–0.60, not 0.80+? Is it possible that the discrimination looks zero
not because the model is wrong, but because the model is calibrated and all its picks
genuinely have similar true probabilities?

**Q7. T2 outperforming T1 (71.4% vs 56.1%).**
The T2 tier hit rate (71.4%, ~20-8, n=28) dramatically exceeds T1 (56.1%, ~23-18, n=41).
This is counterintuitive — T1 should be the highest-conviction tier. What are the most
likely causes: (a) sample variance on n=28/41, (b) T2 lines being systematically easier
or softer, (c) T2 props being in less sharp markets, (d) tier assignment formula error?
Given n=28 for T2, what is the probability this 71.4% hit rate is pure variance vs.
genuine signal? Use the binomial test framework assuming true rate = 55%.

**Q8. pick_score calibration.**
Pick scores in the 60s hit 64%, in the 70s hit 53%, in the 80s hit 58%, in the 90s hit 67%.
There is no monotonic relationship between pick_score and hit rate. What is the correct
approach to recalibrate pick_score so it produces monotonic hit rates? Is this a Platt
scaling problem (same as win_prob), an ordering problem (pick_score formula is wrong),
or a sample problem (n=12-26 per bucket is too small)?

**Q8b. Over/under asymmetry — is the model systematically biased toward overs?**
Live data shows unders hitting at 65.2% vs overs at 54.3% — a 10.9 percentage point gap
on meaningful sample sizes. Two hypotheses: (a) the projection model systematically
overestimates player output (causing excess over picks and under picks that should be overs
to be underpriced), or (b) the over market is more sharply priced than the under market
because casual bettors and DFS players drive over action, meaning the residual edge is
disproportionately in unders. Which hypothesis is consistent with the +0.350% mean CLV
(which measures beating the close, not just hitting the line)? What does published research
say about over/under asymmetry in NBA player prop markets?

---

### SECTION 3: PLAYOFF CALIBRATION — ROUND 2 & SERIES EFFECTS

**Q9. Round 1 vs Round 2 scalar stability.**
My PLAYOFF_MINUTES_SCALAR was fit on Round 1 data (Apr 18-29, n=535 rows). We are now
in Round 2. Published research on playoff basketball: do rotation patterns tighten further
in Round 2+ (fewer teams, higher stakes, more focused coaching), or does the Round 1
scalar generalize? Is there empirical evidence for round-specific scalar drift in the NBA?

**Q10. Spot player collapse in playoffs.**
The spot scalar dropped to 0.350 — spot players get less than 40% of their projected
minutes in the playoffs. This is extreme. Is this consistent with published analyses of
playoff roster compression? What is the published range of "bench player usage rate" across
recent playoff seasons? Is 0.350 possibly over-correcting for Round 1 data that may
have had unusual roster conditions (key injuries, unusual matchups)?

**Q11. cold_start in playoffs — scalar validation.**
`PLAYOFF_MINUTES_SCALAR` for cold_start is 1.000 — meaning no adjustment. But cold_start
players (taxi/new_acquisition/returner) are the most likely to be DNP or have erratic
playoff roles. Is the 1.000 scalar reasonable? What does the empirical data say about
cold_start player playoff utilization vs regular season?

**Q12. Series context effects.**
The current model projects each game independently with no series-level context. Published
sports analytics — does game number within a series (G1 vs G7) predict minutes distribution
or player performance differently? Specifically:
- Do coaches give stars more minutes in elimination games?
- Do role players get fewer opportunities as series get longer?
- Is there a "series fatigue" effect on minutes/efficiency?
What is the magnitude of these effects and should they be modeled?

**Q13. Opponent-specific playoff adjustments.**
The matchup factor uses regular-season defensive splits. In the playoffs, teams game-plan
specifically for their opponent in ways that may far exceed regular-season split magnitudes.
Is there published research quantifying the difference between regular-season matchup effects
and playoff matchup effects? Should a "series opponent" adjustment layer be added on top of
the standard matchup factor?

**Q14. Playoff pace recalibration.**
`LEAGUE_AVG_PACE_PO = 96.5` was estimated. Round 2 2026 data is accumulating.
What is the current (2025-26) observed playoff pace, and how does it compare to 96.5?
The fix (`project_minutes()` scales game_pace by PO/RS ratio = ~0.970) — does this
correctly propagate through all pace-dependent stats? Walk through the mathematical chain
for AST and verify.

---

### SECTION 4: INJURY REDISTRIBUTION — NOW TESTABLE

The injury system was broken until May 5, 2026 (NBA PDF name format mismatch). Starting
now, `injury_minutes_overrides` correctly identifies OUT players and redistributes minutes.
The EWMA-based redistribution model is untested. Brief 8 should provide the framework for
validating it once data accumulates.

**Q15. EWMA redistribution accuracy — methodology.**
When a player is marked OUT, the model redistributes their projected minutes to teammates
using an EWMA-weighted allocation. After N games where the injury data was correct,
how should we measure redistribution accuracy? Propose a specific metric: for each OUT
player event, compare `redistributed_minutes[teammate]` vs `actual_minutes[teammate]`.
What is an acceptable MAE for redistribution accuracy?

**Q16. Superstar OUT vs role player OUT.**
The redistribution model assumes all OUT players' minutes distribute proportionally to
active teammates' EWMA share. But there is likely a difference: when LeBron is OUT,
role players don't benefit much (pick-and-roll usage absorbed by AD/another creator),
but when a bench player is OUT, distributed minutes go to others in the rotation.
Is a single EWMA-weighted redistribution formula adequate, or should the model have
a usage-aware redistribution path for high-USG% players?

**Q17. Q/GTD handling — probability weighting.**
The injury system assigns minute fractions to Q (Questionable) and GTD (Game-Time Decision)
players based on play probabilities. Current logic applies 50% and 30% probability
weighting respectively to reduce their projected minutes. What does the empirical literature
say about the actual play-through rates for Q and GTD designations in the NBA?
Is 50% the right probability for Q, or should it be higher/lower?

**Q18. Lineup confirmation timing.**
Lineups are typically confirmed 30-90 minutes before tip. The current pipeline runs
`generate_projections.py` at some fixed time. Is there a material accuracy improvement
from running a second pass at T-60 minutes (after lineups are confirmed) vs. the morning
run? What is the magnitude of the lineup-confirmation benefit?

---

### SECTION 5: STL / TOV / BLK — UNVALIDATED SCALARS

**Q19. STL scalar = 1.000 — is this correct?**
The `REGULAR_SEASON_STAT_SCALAR` for STL is 1.000 — meaning the model projects STL
perfectly on average in the backtest. But STL was explicitly excluded from home/away
delta calculation because the within-player delta was -1.59% (directionally unexpected).
This suggests the STL model may have a systematic bias that is being masked.
Run a conceptual backtest: if STL actual averages 1.2/game for guards and the model
projects 1.2/game, what is the raw bias? Does 1.000 mean "no bias" or "we never analyzed it"?

**Q20. STL model — pace_factor vs opp_tov_fac divergence.**
Research Brief 4 identified that the evaluator's STL model uses `opp_tov_fac`
(opponent turnover tendency × pace) while `nba_projector.py` uses only `pace_factor`.
This divergence has never been resolved. What is the expected magnitude of the error
introduced by ignoring opponent TOV tendency in STL projection? For a player facing
a high-TOV team (e.g., 20% tov_rate vs league avg 13.6%), how much does this
underestimate STL? Is opp_tov_fac-based STL materially more accurate?

**Q21. TOV scalar = 1.000 — foul trouble and lineup interactions.**
TOV is one of the hardest stats to model because it's partly a function of defensive
pressure (opponent steal tendency) and partly a function of usage (more possessions = more TOV).
The current scalar is 1.000. Is there a systematic bias in TOV that the scalar is hiding?
What is the right formula for TOV projection — per-possession rate × possessions,
or per-minute rate × minutes? Which normalizes better across pace-of-play variation?

**Q22. BLK scalar = 1.043 — rim protection modeling.**
BLK uses: `blk_rate = proj_poss_blk × rim_attempt_rate × matchup_factor_blk`.
`proj_poss_blk` is a possession-based rate. `rim_attempt_rate = (opp_fga - opp_fg3a) / game`.
Is this the right formula? The BLK scalar of 1.043 suggests a 4.3% systematic underestimate.
What is the published model for BLK projection? Is there a better denominator than
raw opponent non-3pt FGA (e.g., restricted area attempt rate, or opponent rim frequency)?

---

### SECTION 6: COLD_START SUB-TYPE VALIDATION

The R7 fix (May 3) introduced taxi/returner/new_acquisition sub-types with different
minute caps. These caps were set heuristically:

| Sub-type | Condition | Min cap |
|----------|-----------|---------|
| taxi | n_career_games = 0 | 12 min |
| returner | days_since_appearance ≥ 180 | min(career_avg, 22) |
| new_acquisition | days_since_appearance < 180 | min(career_avg, 28) |

**Q23. Taxi player cap = 12 minutes — is this right?**
A taxi player (no career games in DB) could be a G-League call-up playing 5 minutes,
or a high-profile rookie. Is 12 minutes the right flat cap? What does the published
distribution of first-call-up minutes look like for NBA players by contract type?

**Q24. Returner cap = min(career_avg, 22) — is 180 days the right threshold?**
180 days (≈6 months) was chosen as the returner threshold. This covers most
long-term injuries (torn ACL, broken foot). But some players return after shorter
absences (3-4 months) and should arguably get closer to their pre-injury average.
What is the empirical distribution of minutes for players returning from injury
by length-of-absence bracket (60-90 days, 90-150 days, 150-180 days, 180+ days)?

**Q25. new_acquisition cap = min(career_avg, 28) — trade vs. free agent vs. waiver claim.**
New acquisitions include mid-season trades, buyout signings, and waiver claims. Their
immediate utilization varies dramatically by the type of acquisition and why their
previous team let them go. Is there a better classification signal than days-since-last-game
for new acquisitions? Should the cap be:
(a) uniform at min(career_avg, 28) regardless of acquisition type, or
(b) role-conditioned (if they were a starter on their prior team vs. a bench player)?

---

### SECTION 7: THE GO-LIVE DECISION

**Q26. Go-live threshold design.**
The current go-live gate is: "100 CLV shadow picks where custom CLV ≥ SaberSim CLV."
This is a binary comparison at the batch level, not a statistical test. What is the correct
formal statistical test for declaring one projection system superior to another on CLV?
Options: paired t-test on per-pick CLV, Wilcoxon signed-rank test, bootstrap confidence
interval on CLV difference. What is the correct null hypothesis and α level?

**Q27. Required sample for meaningful CLV comparison.**
Given that per-pick CLV variance for NBA props is approximately σ ≈ 3-4% (typical CLV
standard deviation), what is the minimum n for an 80% powered test to detect a 1% CLV
advantage (custom vs SaberSim)? How does this scale with effect size (what n for 0.5% advantage)?

**Q28. What to do if custom CLV < SaberSim CLV at 100 picks.**
The go-live gate assumes custom will beat SaberSim. What if it doesn't? What is the
diagnostic protocol:
(a) Which stats is custom worse on (PTS vs AST vs 3PM vs REB)?
(b) Which roles is custom worse on (starter vs cold_start)?
(c) Is the gap closing over time or stable?
What minimum improvement trajectory would justify continuing the shadow run vs.
declaring failure and reverting to SaberSim only?

**Q29. Transition strategy.**
If custom projections meet the go-live gate, how should the transition be managed?
Options: (a) hard switch (drop SaberSim entirely), (b) ensemble (average custom + SaberSim
projections), (c) conditional (use custom for starters/rotation, SaberSim for cold_start).
What does the ensemble literature say about combining projections from two correlated models
(both using nba_api data)?

---

### SECTION 8: EDGE CALCULATION & PICK SELECTION ARCHITECTURE

**Q30. How is `adj_edge` calculated, and is the formula correct?**
`adj_edge` is the primary pick-selection metric. Walk through the full calculation:
raw edge → Platt-calibrated win_prob → implied probability from odds → edge.
Where exactly does Platt scaling enter, and does the ordering matter? Specifically:
should Platt be applied before or after the vig-removal calculation? What is the
mathematical impact of applying them in the wrong order?

**Q31. Edge vs. CLV — are they measuring the same thing?**
"Edge" in this system is model-implied probability minus book-implied probability (vig-removed).
"CLV" is your implied probability at bet time minus the implied probability at close.
These are correlated but distinct. The research question: is there evidence that systems
with positive CLV necessarily have positive edge, and vice versa? Can a system have
positive CLV but negative model edge (and still be profitable)?

**Q32. The vig removal problem.**
The system removes vig by dividing implied probabilities by their sum. This is the
"multiplicative method" of vig removal. Published alternatives include the "additive method"
and the "power method." For NBA player props at typical juice of -115/-115 (5% vig),
how much do these methods differ? Is the multiplicative method the industry standard,
and does it matter for edge calculation?

**Q33. Prop market liquidity and line stickiness.**
NBA player props have lower liquidity than game lines. When a sharp model identifies
edge, how quickly does the market move to close that edge? Is there published research on
the half-life of edge in NBA prop markets? Specifically: if the model projects over 25.5 PTS
with edge=5%, how long after line posting does the line typically move to neutralize that edge?

---

### SECTION 9: DK_STD & FANTASY INTEGRATION

**Q34. DK_STD formula validation.**
Current: `dk_std = max(proj_pts * 0.35, floor)` where floors are 4.0/4.0/3.5/3.0/3.0
(starter/sixth_man/rotation/spot/cold_start). The 0.35 coefficient was described as
"r²=0.81, calibrated 2024-25 season." But proj_pts is fantasy points, and the coefficient
was empirically derived from historical data. Questions:
(a) Is 0.35 stable across roles? Stars have lower dk_std/proj ratio than bench players
    because their variance is lower relative to their mean (they're more predictable).
(b) Is proj_pts the right base variable, or should dk_std use proj_min × per-minute fantasy rate?
(c) How does this formula perform for cold_start players where proj_pts is heavily prior-weighted?

**Q35. Is dk_std used downstream, and how?**
The dk_std column appears in the CSV output and pick_log. Is it used by run_picks.py
in the edge or tier calculation, or is it metadata? If it's not used in pick selection,
should it be? Published DFS + sports betting intersection: does dk_std (as a measure of
outcome variance) help identify props where model edge is reliable vs. noisy?

---

### SECTION 10: LINE SHOPPING & TIMING

**Q36. Best book identification accuracy.**
The system queries odds across 18 CO-legal books and selects the best available line.
Published research on line shopping value: for NBA player props, what is the expected
CLV improvement from line shopping across 5 books vs. 10 books vs. 18 books? Is there
a published estimate of the average "best line premium" for player props?

**Q37. Timing optimization — when to bet.**
NBA player props typically post Sunday/Monday for the week. Sharp line movement occurs
when sharp books move, which signals to square books. Published research: what is the
optimal bet timing for NBA props relative to line posting? Is "bet as soon as line posts"
better than "bet T-2 hours" for catching soft opening lines vs. minimizing stale-line risk?

**Q38. Injury information timing.**
The injury report is typically updated at 5pm ET on game day, with final designations
at 6:30pm. The system runs `generate_projections.py` once per day. Is there a material
edge in running a second pass at T-2 hours (after 5pm injury report)? What is the expected
change in picks between a morning run and a T-2 hour run, and is the edge from late
information worth the operational complexity?

---

### SECTION 11: B2B AND REST — LIVE VALIDATION

**Q39. B2B model accuracy — testable from pick_log.**
The B2B model applies max_reduction=10% at 0 days rest, exponential decay with half-life=1.5 days.
This has never been validated on live data. From pick_log.csv, for every pick where the
player was on a B2B, compare projected minutes vs. actual minutes. Is the 10% reduction
accurate, under-correcting, or over-correcting? What is the correct methodology to
disentangle B2B effects from game-context effects (blowouts, foul trouble)?

**Q40. Role-specific B2B — are the scalars right?**
B2B scalars: starter=1.00, sixth_man=0.95, rotation=0.90, spot=0.75, cold_start=0.90.
The starter=1.00 means "no reduction" — load management notwithstanding, do NBA starters
truly show no statistically significant minutes reduction on B2B nights? Published
sports science literature (e.g., research on circadian rhythm, fatigue, load management)
— what is the measured minutes reduction by role tier?

---

### SECTION 12: ERA_WEIGHT & HISTORICAL DEPTH

**Q41. Current era_weight scheme.**
Current seasons get weight=1.0, prior seasons get weight=0.5 (or similar). For EWMA
calculations, the era_weight is applied via a `starter_flag` weighting in game selection.
What is the theoretical justification for 2:1 weighting of current vs. prior season?
Published research on temporal weighting in basketball projection models — is 2:1 too
aggressive (discards useful history), too conservative (includes stale data), or
approximately correct?

**Q42. Minimum history needed for stable projections.**
The DB has 83,719 rows covering Oct 2023 – Apr 2026 (~2.5 seasons). The EWMA max span
is 15 games. Theoretically, only the most recent 15 games matter for EWMA, and prior
seasons only contribute via era-weighted context. Is the 2.5-season historical depth
genuinely contributing to accuracy, or would a 1-season DB perform identically?
What is the minimum historical depth for stable Bayesian priors (the part of the model
that does use historical data)?

---

### SECTION 13: POSITION CLASSIFICATION ACCURACY

**Q43. Height-based position inference.**
Player positions are inferred from height: ≤76" → G, 77-80" → F, ≥81" → C.
The NBA in 2025-26 has many "positionless" players — guards who play power forward
(Draymond Green), wings who play center (Bam Adebayo). How often is height-based
classification wrong for modern NBA players? What is the error rate for this inference,
and what is the downstream impact on REB priors, AST priors, and STL priors when
a player is misclassified?

**Q44. Better position signals.**
What are better signals for position classification than height alone?
Options: (a) roster position from NBA API (PG/SG/SF/PF/C), (b) lineup data (who they
guard on defense), (c) on-ball usage percentage, (d) rebounding rate (pure proxy for role).
Is there a published methodology for "functional position" classification in modern NBA?

---

### SECTION 14: BLOWOUT ADJUSTMENT

**Q45. Blowout sigmoid — is it calibrated correctly?**
The blowout model uses: sigmoid steepness k=0.40, inflection at spread=12, max reduction=20%.
Bench weights: margin≥25 → 0.55x, margin 15-24 → 0.75x. Starter weights: margin≥25 → 0.75x.
These were set heuristically. What does the empirical distribution of minutes look like
for starters and bench players in blowout games (15+ point margin at halftime, or final
margin >15)? Is 20% the right max reduction for starters?

**Q46. Using Vegas spread as blowout predictor.**
The blowout adjustment uses the pre-game spread as a proxy for expected blowout probability.
But this is a coarse predictor — many spreads of 12 result in competitive games, and many
spreads of 5 result in blowouts. Is there a better signal? What does published research say
about the relationship between pre-game spread and actual blowout frequency?

---

### SECTION 15: TEAM TOTAL CONSTRAINT

**Q47. Spread/2 derivation accuracy.**
When Odds API returns no explicit team totals (common in playoffs), the model derives:
`home_total = (game_total - spread) / 2`, `away_total = (game_total + spread) / 2`.
This assumes teams score symmetrically around the spread. Is this a valid assumption?
Published research on the relationship between game total, spread, and implied team
totals in NBA betting markets — how accurate is the spread/2 formula vs. actual Vegas
team totals when they are available?

**Q48. Constraint scale clip [0.80, 1.20] — is this right?**
The constraint scales all player PTS projections by `vegas_total / sum_proj_pts`,
clipped to [0.80, 1.20]. The clip prevents catastrophic corrections when projections
are wildly off. But if the custom projector is systematically 20%+ off on team totals,
the clip will hide this error. What is the empirical distribution of `vegas_total / sum_proj_pts`
across the projection runs so far? Has the clip ever been triggered? If yes, for which teams?

---

### SECTION 16: OFF-SEASON ARCHITECTURE

**Q49. NBA calendar — what's next?**
The 2025-26 playoffs end in June 2026. After that: NBA Draft (late June), free agency (July),
summer league (July), training camp (late September), preseason (October), and then
the 2026-27 regular season begins late October. The projection engine needs to handle:
(a) Off-season: no games, no CLV to capture, but DB maintenance, roster moves, and summer league stats
(b) New season: player roles will change dramatically — starters become bench players, trades happen
(c) First 10 games of the season: cold_start rates will be highest

What is the recommended engineering plan for the off-season? Should the engine:
- Purge or keep current season weights?
- Apply 2025-26 as the prior-season, with 2026-27 getting new era weights?
- Run special cold_start handling for the first month of the new season?

**Q50. New season role assignment problem.**
In the first week of the 2026-27 season, almost all players will be `cold_start`
by the current definition (fewer than 10 games on team in current season). This is
the worst possible time to have the weakest projection capability. What is the best
architecture for "season start" role assignment — using end-of-prior-season role,
or contract/salary signals, or preseason performance, or some combination?

---

### SECTION 17: ADVANCED ARCHITECTURE — NEXT LEVEL

**Q51. Should the engine move toward a hierarchical Bayesian model?**
Current: EWMA + Bayesian shrinkage per player, per stat, independently.
Alternative: hierarchical model where team-level priors inform player-level estimates.
When a new player joins a team, the hierarchical model uses the team's historical
statistical profile to set better priors than position-based league averages.
What is the published accuracy improvement of hierarchical vs. flat Bayesian approaches
for sports projection? What is the computational cost, and can it run in <60s for a full slate?

**Q52. Ensemble projections — custom + SaberSim.**
If the custom projector doesn't fully beat SaberSim, an ensemble (weighted average)
may outperform both. What is the published research on ensembling sports projection models?
What weighting schemes are used — equal weight, MAE-weighted, CLV-weighted?
For two correlated models (both trained on nba_api data), does ensembling provide meaningful
variance reduction, or do they share so much variance that the ensemble is not materially better?

**Q53. Real-time line movement monitoring.**
The system currently checks odds once (at run time). Sharp prop markets move in the 2 hours
before game time. What is the architecture for a lightweight line-monitoring daemon
that flags when a logged pick's line has moved significantly (e.g., pick logged at
Over 25.5 -110, but now the line is Over 26.5 -110 — the edge may have disappeared)?
Is there a published threshold for "line has moved enough that the original edge is gone"?

**Q54. Foul trouble adjustment — Brief 5 L9 deferred item.**
Foul trouble is listed as "low priority" in Brief 5 (L9) but has never been implemented.
In the playoffs, foul trouble is particularly impactful — stars like Anthony Davis or
Joel Embiid frequently sit with 4 fouls in Q3-Q4. What is the correct modeling approach:
(a) In-game adjustment (not applicable here — we bet pre-game), or
(b) Pre-game adjustment for high-foul-rate players facing aggressive opponents?
What is the magnitude of minutes reduction for players with seasonal foul rates > 4.0 fouls/40min?

---

### SECTION 18: SYSTEM-WIDE PRIORITIZED ROADMAP

**Q55. What are the top 5 highest-ROI improvements for the next 60 days?**
Given everything in this brief — the live betting benchmarks, the model constants,
the structural gaps, and the go-live gate — what are the five specific, implementable
changes most likely to improve CLV and hit rate in the next 60 days?
Rank by: expected_improvement / implementation_complexity.
Focus on changes that can be validated within 30 days of implementation.

**Q56. What are the top 3 risks that could cause the system to degrade?**
Identify the three scenarios most likely to cause a significant performance regression:
model drift, external data changes, market efficiency improvements, or structural failures.
For each risk, propose a monitoring mechanism that would detect it within 7 days.

**Q57. What would a "version 2.0" of this projection engine look like?**
If you were redesigning the engine from scratch with 6 months of live data and the
lessons learned from Briefs 1-8, what would you change? What components of the
current architecture would you keep, discard, or replace? What data sources would
you add? What is the realistic ceiling for this type of statistical projection model
on NBA player props, assuming access to publicly available data only?

---

*End of Research Brief 8 — May 2026*
*System: JonnyParlay custom NBA projection engine*
*Author: Jono (jonopeshut@gmail.com)*
