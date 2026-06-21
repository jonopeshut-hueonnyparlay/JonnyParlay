# Research Brief 6 — Custom NBA Projection Engine & Sports Betting System
## Deep Research Prompt (May 2026)

---

## SYSTEM OVERVIEW

I run a custom NBA projection engine that feeds picks into a sports betting operation. The engine generates per-player stat projections (PTS, REB, AST, 3PM, STL, BLK, TOV), converts them to a SaberSim-schema CSV, and passes that CSV to a betting engine (`run_picks.py`) which calculates win probability, edge, sizing, and posts picks to Discord. The system is currently in **shadow mode** — running parallel to SaberSim projections ($197/mo) with picks logged to a separate file (`pick_log_custom.csv`) without Discord posting. Go-live gate: 100+ picks where custom CLV ≥ SaberSim CLV.

**Stack:** Python, SQLite (projections.db = 15.8 MB), The Odds API, nba_api, Windows Task Scheduler, Discord webhooks.

---

## COMPLETE SYSTEM BENCHMARKS

### Live Betting System (pick_log.csv — Apr 14 to May 2, 2026)
- **Date range:** 18 days of live operation
- **Total logged picks:** 120 rows (all run types)
- **Primary + Bonus graded picks:** 80 (48W–32L = **60.0% hit rate**)
- **Units P/L (primary + bonus):** **+4.13u**
- **Sports breakdown:** NBA 34-23 (60%), NHL 14-9 (61%)

**By tier:**
| Tier | W | L | Hit% | n |
|------|---|---|------|---|
| T1 | 16 | 14 | 53% | 30 |
| T1B | 5 | 6 | 45% | 11 |
| T2 | 16 | 4 | **80%** | 20 |
| T3 | 9 | 6 | 60% | 15 |
| KILLSHOT | 2 | 2 | 50% | 4 |

**By pick_score bucket:**
| Score range | W | L | Hit% | n |
|-------------|---|---|------|---|
| 60s | 9 | 5 | 64% | 14 |
| 70s | 10 | 9 | 53% | 19 |
| 80s | 15 | 11 | 58% | 26 |
| 90s | 8 | 4 | 67% | 12 |

**⚠️ Critical finding — model discrimination failure:**
- Win_prob: **winners mean = 0.695, losers mean = 0.696** (near-zero separation)
- Edge: **winners mean = 0.1479, losers mean = 0.1478** (near-zero separation)
- The model currently cannot statistically distinguish winning picks from losing picks by its own win_prob or edge signals on n=80.

**Parlay/special run types:**
- SGP: 3W–5L (38%) n=8
- Daily Lay: 3W–6L (33%) n=9
- Longshot: 1W–0L n=1

**CLV observations:**
- Total non-zero CLV captures: **7** (out of 120 picks)
- Mean CLV: **+1.479%**
- Positive CLV: 7/7 (100%)
- ⚠️ Sample size is critically small — statistically meaningless at n=7

---

### Custom Projection Engine (projections.db)

**Database overview:**
- DB size: **15.8 MB**
- Players: **802**
- Teams: **30**
- Games: **3,895** (590 distinct game dates)
- player_game_stats rows: **83,719** (Oct 24, 2023 – Apr 29, 2026)
- Total projections stored: **1,221** (Apr 18–29, 2026 only — 8 distinct dates, ~152 players/day)

**Role tier distribution across all stored projections:**
| Role | Count | % |
|------|-------|---|
| cold_start | 416 | **34%** |
| rotation | 297 | 24% |
| starter | 242 | 20% |
| sixth_man | 162 | 13% |
| spot | 104 | 8.5% |

**⚠️ Critical finding:** `cold_start` is the single largest role category at 34% — nearly 1 in 3 projected players has insufficient context for role assignment.

**Projection output ranges (across 1,221 rows):**
| Stat | Avg | Min | Max |
|------|-----|-----|-----|
| proj_min | 20.2 | 11.2 | 41.5 |
| proj_pts | 8.5 | 1.5 | 31.3 |
| proj_reb | 3.2 | 0.3 | 12.9 |
| proj_ast | 1.8 | 0.1 | 10.2 |
| proj_fg3m | 0.9 | 0.0 | 3.6 |

---

### Projection Accuracy (vs SaberSim, playoff sample n=43 graded props + n=459 min rows)
- **Custom engine adj MAE:** 3.436
- **SaberSim adj MAE:** 3.254
- **Gap:** custom is **+10.2% worse** than SaberSim
- **Custom engine bias (P18-v4):** -0.108 (was -0.620 before playoff calibration)
- **SaberSim bias:** unknown (assumed near-zero)
- **adj MAE definition:** rate-adjusted error holding minutes constant — isolates rate accuracy from minutes error

---

### Model Parameters (all hardcoded constants)

**EWMA lookback spans:**
| Stat | Span |
|------|------|
| PTS | 15 games |
| REB | 12 games |
| AST | 13 games |
| FG3M | 10 games |
| STL | 8 games |
| BLK | 8 games |
| TOV | 10 games |
| MIN | 6 games |
| Shooting efficiency (FG%, FT%, FG3A rate, USG%) | 10 games |

**Pace elasticity exponents:**
| Stat | Exponent |
|------|----------|
| PTS | 0.90 |
| FG3M | 0.78 |
| REB | 0.25 |
| AST | 0.50 |
| STL | 0.30 |
| BLK | 0.30 |

**League baselines:**
- Regular season avg pace: 99.5 possessions/game
- Regular season avg total: 222.0 points
- Playoff avg pace: 96.5
- Playoff avg total: 210.0
- League avg TOV rate: 0.136 per possession
- League avg rim attempt rate: 56.0 non-3pt FGA/game

**Blending alphas (per-stat rate path vs. decomposition path):**
- PTS blend alpha: 0.50 (calibrated May 2026 — bias-optimal vs MAE-flat curve; alpha=0.30 MAE-optimal but +0.086 bias)
- REB blend alpha: 0.45 (lean toward baseline until rates stabilise)
- AST blend alpha: 0.40
- FG3M blend alpha: 0.50

**Role minute priors (used when EWMA sample is thin):**
| Role | Prior MPG |
|------|-----------|
| starter | 28.0 |
| sixth_man | 24.0 |
| rotation | 16.0 |
| spot | 6.0 |
| cold_start | 16.0 |

**USG% role priors:**
| Role | USG% |
|------|------|
| starter | 24.0% |
| sixth_man | 20.0% |
| rotation | 16.0% |
| spot | 13.0% |
| cold_start | 20.0% |

**Role minimum games threshold for tier assignment:** 5 games

**Bayesian padding (shooting stabilisation):**
- FG2%: padded to 300 FGA prior
- FG3%: padded to 750 FGA prior

**Position priors (used at cold_start / archetype fallback):**
| Position | PTS/36 | REB/36 | AST/36 | FG3M/36 | STL/36 | BLK/36 | TOV/36 |
|----------|--------|--------|--------|---------|--------|--------|--------|
| G | 14.5 | 3.2 | 5.8 | 1.8 | 1.2 | 0.3 | 2.5 |
| F | 13.8 | 5.8 | 2.8 | 1.2 | 0.9 | 0.6 | 1.8 |
| C | 13.2 | 9.4 | 1.8 | 0.4 | 0.7 | 1.8 | 2.0 |

**AST position priors (per-possession):**
- G: 0.073, F: 0.050, C: 0.045
- AST EWMA spans by position: G=10, F=6, C=5
- AST prior N: G=12, F=14, C=14

**REB decomposition (OREB/DREB split):**
- OREB prior N: 15 games | DREB prior N: 15 games
- OREB positional priors: G=0.02043, F=0.03247, C=0.07048 (per team miss/48)
- DREB positional priors: G=0.08086, F=0.10569, C=0.17162 (per opp miss/48)

**STL priors (per possession):** G=0.01830, F=0.01664, C=0.01405 | prior N: 5
**BLK priors (per possession):** G=0.00537, F=0.00805, C_low=0.00886, C_high=0.02415 | prior N: 5-6
**TOV priors (per possession):** G=0.0335, F=0.0241, C=0.0268 | prior N: 15

**Home/away adjustment deltas (empirical, n=602 players, ≥5 home AND ≥5 away games):**
| Stat | ±Delta | Full spread |
|------|--------|-------------|
| PTS | ±0.52% | 1.04% |
| REB | ±0.58% | 1.17% |
| AST | ±1.35% | 2.69% |
| FG3M | ±1.31% | 2.62% |
| BLK | ±1.27% | 2.54% |
| TOV | ∓0.63% | 1.26% (negative: home teams fewer TOV) |
| STL | excluded | within-player delta was -1.59% (wrong direction, excluded as noise) |

**Back-to-back / rest model:**
- Max reduction at 0 days rest: 10%
- Half-recovery half-life: 1.5 days
- Role-specific scalars: starter=1.00, sixth_man=0.95, rotation=0.90, spot=0.75, cold_start=0.90

**Blowout minutes reduction (sigmoid):**
- Sigmoid steepness k=0.40, inflection at spread=12, max reduction=20%
- Bench weights: margin≥25 → 0.55x, margin 15-24 → 0.75x
- Starter weights: margin≥25 → 0.75x, margin 15-24 → 0.90x
- Minimum valid non-blowout games to apply filter: 12

**Trade blending (post-trade adjustment, games 1-6 on new team):**
- Games 1-3: 60% prior-team rates
- Games 4-6: 40% prior-team rates
- Games 7+: fully adapted to new team

**Availability weighting (L4 — teammate vacancy):**
- Key teammate threshold: ≥12 MPG
- Minimum game weight floor: 0.30

**DK fantasy std coefficient:** 0.35 × proj_pts (r²=0.81, calibrated 2024-25 season)

---

### Playoff Calibration — P18-v4 (May 2, 2026)
Fit on n=459 matched projection-vs-actual rows (Apr 18–29, 2026 playoffs):

**Role-conditional minutes scalars:**
| Role | Scalar | Interpretation |
|------|--------|----------------|
| starter | 1.068 | +6.8%: starters play more in close playoff games |
| sixth_man | 0.909 | -9.1% |
| rotation | 0.786 | -21.4%: coaches tighten to 8-9 man rotations |
| spot | 0.902 | -9.8% |

**Residual rate deflators:**
- AST: 0.8255 (isolation-heavy offense → fewer motion-offense assists)
- FG3M: 0.8780 (tighter perimeter defense)
- PTS, REB, STL, BLK, TOV: no extra rate deflation (effect is minutes-driven)

**Results of P18-v4:**
- Custom MAE: 3.436 | Bias: -0.108
- Custom pre-calibration: MAE 3.413 | Bias: -0.620
- SaberSim MAE: 3.254 | Bias: unknown
- Gap to SaberSim: +10.2% adj MAE

---

### Win Probability Calibration
- **Model:** Platt scaling
- **Constants:** A=1.4988, B=-0.8102
- **Training sample:** n=76 props
- **Brier score:** 6% (0.06)
- **Live discrimination (n=80):** winners mean win_prob=0.695, losers=0.696 → effectively zero separation

---

### CLV Capture System
- **Capture window:** T-30 to T+3 minutes per game
- **Daemon schedule:** 10am daily, Task Scheduler (S4U logon)
- **Live CLV sample (SaberSim, non-zero):** n=7
- **Live CLV mean:** +1.479%, all positive
- **Shadow CLV (custom projections):** 0 observations captured yet
- **Go-live gate:** 100+ shadow picks with custom CLV ≥ SaberSim CLV

---

### Bankroll / Sizing
- **Max daily units:** 12u cap
- **Sport caps:** NBA max 8.0u/pick, NHL max 5.0u/pick
- **Stat cap:** SOG max 6 picks/run; all other stats max 2
- **KILLSHOT sizing:** 3u default; 4u if win_prob≥0.70 AND edge≥0.06
- **SGP sizing:** 0.25u default / 0.50u premium tier (avg_wp≥0.70, cohesion≥0.55, avg_edge≥0.035)
- **Daily Lay sizing:** 0.25–0.75u (Kelly-derived)

---

## RESEARCH QUESTIONS

Please research every question below as deeply as possible, using academic literature, sports analytics published research, betting markets literature, and industry best practices. Where a question references a specific benchmark from this system, assess whether that benchmark is good/poor/typical by comparison to published work, and recommend specific improvements with implementation guidance.

---

### SECTION 1: MINUTES MODEL

**Q1.** What is the empirically optimal EWMA span for NBA player minutes? My current span is 6 games. The literature on sports forecasting (e.g., Kooij 2023, Hubáček et al.) and basketball analytics (Second Spectrum, Cleaning the Glass) may have relevant findings. What span minimizes out-of-sample MPG MAE, and does the optimal span vary by role tier (starters vs. bench)?

**Q2.** Back-to-back: I model rest as a continuous exponential decay with max_reduction=10% and half-life=1.5 days. NBA sports science literature (e.g., Charest et al. 2018, or NBA load management studies) — what is the empirically measured minutes reduction on night-2 B2B by position/role? Is 10% the right magnitude, or is it systematically higher for stars/load-managed players?

**Q3.** Does overtime contaminate minutes baselines? Starters average 35+ min in OT games vs. normal 30-33. Should OT-game minutes be excluded from the EWMA, capped, or normalized to a 48-minute equivalent before averaging?

**Q4.** For players changing teams mid-season: I use a trade blend (60% prior-team rates games 1-3, 40% games 4-6). What does the empirical literature say about how quickly players stabilize in new systems? Is the 6-game blending window too short, too long, or appropriate? Are there role-specific or position-specific differences in adaptation speed?

**Q5.** What is the correct functional form for minutes projection — flat rolling average, EWMA, or something more sophisticated (e.g., state-space model, Kalman filter)? What does the sports forecasting literature recommend for highly coach-reactive variables?

**Q6.** How should in-season load management (unofficial rest, without a formal DNP-CD designation) be detected and modeled? Stars like LeBron, Kawhi, etc. play reduced minutes in certain game contexts even when listed as "active." What signals predict these soft-rest games?

---

### SECTION 2: RATE MODEL & EWMA SPANS

**Q7.** My EWMA spans are: PTS=15, REB=12, AST=13, FG3M=10, STL/BLK=8, TOV=10. What does the basketball analytics literature say about the stabilization windows for each of these stats (i.e., minimum games before a rate is predictive of future rates)? How do these compare to published stabilization research (e.g., Bill Petti's MLB work adapted for NBA, or Second Spectrum)?

**Q8.** I use a blended projection for PTS (50% FGA-decomp path, 50% per-minute EWMA), alpha=0.50 calibrated for bias-optimality (alpha=0.30 is MAE-optimal but adds +0.086 bias). What is the theoretical justification for blending these two paths, and what does the literature say about optimal blending for count statistics with strong usage-rate interactions?

**Q9.** My AST model uses per-possession rates with position-conditional EWMA spans (G=10, F=6, C=5) and empirical priors (G=0.073, F=0.050, C=0.045 AST/possession). Is per-possession normalization the right basis for AST, or does per-minute-with-usage-adjustment outperform it? What's the research consensus?

**Q10.** For FG3M, the model uses FG3A rate × FG3% (decomposed), with 3PM blend alpha=0.50. FG3% is Bayesian-padded to 750 FGA prior. What is the published stabilization sample size for FG3%? Is 750 FGA consistent with the literature (e.g., Ilardi, Kubatko, or more recent Bayesian basketball work)?

**Q11.** My REB model decomposes into OREB and DREB separately using available-rebound denominators with prior N=15 for both. What is the stabilization window for OREB rate vs. DREB rate in published basketball analytics research? Is 15 games correct for both, or does DREB stabilize later (as my earlier estimate of 28 games suggested)?

**Q12.** What is the home/away effect on per-minute stat rates in published NBA research? I measure: PTS±1.04%, REB±1.17%, AST±2.69%, 3PM±2.62%, BLK±2.54%. Are these magnitudes consistent with literature, or are they systematically under/over-estimated? Should STL be excluded (I excluded it because the within-player delta was -1.59%, which was directionally unexpected)?

**Q13.** Are there nonlinear usage-rate interactions that a linear blending approach misses? Specifically, when a primary ball-handler is out, the secondary creator's usage and AST rate may increase superlinearly — do any published lineup-impact models address this?

---

### SECTION 3: OPPONENT DEFENSE & MATCHUP ADJUSTMENTS

**Q14.** My matchup factors use team-level defensive splits (team_def_splits table, 1,890 rows). What is the optimal defensive adjustment methodology — team-level rank, position-level defense rank, or player-vs-player matchup? What does the research say about how much variance is explained by each level?

**Q15.** Are there elite individual defenders (e.g., Rudy Gobert in pick-and-roll coverage, Kawhi Leonard on perimeter) where team-level defense rank significantly underestimates the impact on specific prop types? What is the published magnitude of elite defender suppression effects on ball-handler scoring and point guard assists?

**Q16.** The MATCHUP_CLIP is (0.80, 1.20) — matchup adjustments are capped at ±20%. What is the empirical distribution of legitimate matchup effects in published research? Is ±20% too conservative (missing extreme cases) or appropriately conservative to prevent overfitting?

---

### SECTION 4: ROLE TIER ASSIGNMENT

**Q17.** 34% of my stored projections are classified as `cold_start` (insufficient data for role assignment, <5 games on team). This is the single largest "role" category. What does the literature say about the optimal minimum-games threshold for role stability? Is there a published approach for classifying role tier from roster composition + historical context rather than requiring a minimum sample?

**Q18.** My role minute priors are: starter=28.0, sixth_man=24.0, rotation=16.0, spot=6.0, cold_start=16.0. These were revised from earlier values (starter was 32, rotation was 19, spot was 14). What does the empirical distribution of actual NBA minutes look like by roster position? Are these priors well-calibrated to the league-wide distribution?

**Q19.** For players who split starts and bench games within the same season (situational starters): is it better to use a blended role (starter 40% / sixth_man 60% of games) or to predict the likely starting/bench status for the specific game context? What signals predict game-level starting status most reliably?

---

### SECTION 5: PLAYOFF CALIBRATION

**Q20.** My P18-v4 playoff minutes scalars were fit on n=459 rows from April 18-29, 2026 (one playoff window). What is the confidence interval on these scalars, and how stable are they across multiple playoff seasons (2022, 2023, 2024, 2025)? Is one season of playoff data sufficient, or are these estimates noisy?

**Q21.** The rotation player scalar is -21.4% (0.786). This is very large — rotation players lose 21% of their projected minutes in the playoffs. Is this consistent with published research on playoff rotation tightening? What is the empirical range across seasons?

**Q22.** My rate deflators are: AST=0.8255, FG3M=0.8780. These were fit on n=43 graded props. Is this sample sufficient to distinguish genuine rate effects from minutes-driven effects? What is the correct sample size for stable rate deflator estimation?

**Q23.** Does playoff calibration need to be round-specific (Round 1 vs. Conference Finals vs. Finals) or series-context-specific (elimination games vs. blowout-risk games), or is a single season-type flag sufficient?

---

### SECTION 6: WIN PROBABILITY & EDGE — CRITICAL

**Q24.** ⚠️ CRITICAL: My live data shows near-zero discrimination between winning and losing picks by win_prob (winners=0.695, losers=0.696) and by edge (winners=0.1479, losers=0.1478) on n=80. What sample size is required to detect a statistically meaningful difference in win probability between winning and losing picks, given typical calibration noise? Is n=80 simply too small, or does this suggest a genuine model failure?

**Q25.** My Platt scaling was fit on n=76 props with Brier score=0.06. What is a typical Brier score for a well-calibrated NBA prop model? Is 0.06 good, mediocre, or poor? What is the minimum sample size for stable Platt constant estimation?

**Q26.** The model's win_prob range for graded picks is roughly 0.65-0.75 (mean ~0.695 for both winners and losers). This is a very narrow range — the model is not producing high-confidence (>0.80) or low-confidence (<0.60) picks. Is this appropriate (the model is conservative) or does it suggest the calibration is compressing probabilities toward the mean?

**Q27.** What is the theoretical maximum win probability achievable for NBA player prop bets using purely model-based projection? The market is priced by sharp books — what is the expected edge from statistical projection alone vs. pure timing/information edges?

**Q28.** The pick_score tiers (T1>T2>T3) do not show monotonic hit rates — T2 is 80% (16-4) while T1 is 53% (16-14). This is counterintuitive for a model that ranks picks by quality. What are the most likely causes of this inversion, and how should tier assignment be redesigned to produce monotonic hit rates?

---

### SECTION 7: GAUSSIAN COPULA & SGP

**Q29.** My SGP scoring uses Gaussian copula with equicorrelation approximation (single ρ) during the 91k-combo search, then 4000-sample Monte Carlo for final scoring. What is the published research on same-game correlations for NBA player props? What are typical ρ values for PTS-AST, PTS-REB, AST-3PM for a high-usage guard? Is equicorrelation a reasonable approximation?

**Q30.** SGP hit rate is 3-5 (38%) on n=8 — which is approximately what you'd expect by chance for 4-leg parlays regardless of model skill. What sample size is needed to detect a genuine SGP edge (say, 5% better than market) with 80% power? How many weeks of operation to have a meaningful SGP evaluation?

**Q31.** What is the optimal leg count for SGP construction given the correlation structure of NBA props? Research on parlay optimization — is 3-4 legs (my current design) consistent with EV-maximizing construction, or do 2-leg same-game correlations offer better risk/reward?

---

### SECTION 8: COLD_START HANDLING

**Q32.** 34% of projections are cold_start. The archetype priors (G: PTS=14.5/36, F: 13.8/36, C: 13.2/36) are league-wide averages, which will massively overproject scrubs and underproject stars at cold_start. What is the best-practice approach for cold_start players — positional prior, salary-based prior, or something else? What does the literature say about new-team adaptation?

**Q33.** Is there a way to classify cold_start players into sub-tiers (e.g., known-star cold_start vs. fringe player cold_start) using prior career history, even if recent games on the new team are insufficient? What signals are most predictive of first-game role?

---

### SECTION 9: BACKTESTING METHODOLOGY

**Q34.** My adj MAE metric holds minutes constant to isolate rate accuracy. Should the backtest separately report (a) minutes MAE, (b) rate MAE conditional on actual minutes, and (c) combined stat MAE? What is the published convention for evaluating sports projection models?

**Q35.** The SaberSim gap is +10.2% adj MAE. What is a realistic target adj MAE for a custom model after 6-12 months of tuning? What do published NBA projection models achieve (e.g., ESPN BPI, FiveThirtyEight CARMELO, Basketball-Reference projections)?

**Q36.** The backtest was only run on n=459 rows from 8 days of playoff games (Apr 18-29, 2026). This is both small and non-representative — playoff games have unique characteristics. What is the minimum sample size for a reliable projection accuracy estimate, and how much data from regular-season games is needed for the backtest to be meaningful?

**Q37.** What is the correct treatment of sample selection bias in the backtest — specifically, the cold_start players who represent 34% of projections but whose accuracy is likely much worse? Should the headline adj MAE exclude cold_start, report separately, or use a weighted average?

---

### SECTION 10: CLV ARCHITECTURE

**Q38.** With n=7 CLV observations (all positive, mean +1.479%), what is the minimum sample size to conclude with 80% confidence that the system is beating the close vs. a null hypothesis of 0% CLV? Given typical CLV variance for NBA props (~2-4% std), how many more observations are needed?

**Q39.** What is the published theoretical relationship between CLV and long-run ROI? Specifically: if a system averages +1.5% CLV on NBA player props with a typical edge bet at -110, what is the expected ROI per unit bet? What does the sharp betting literature say (e.g., Pinnacle's Edge, Buchdahl, Joseph Peta)?

**Q40.** Should CLV be computed and tracked separately for props vs. game lines vs. totals? The noise profiles are fundamentally different — prop lines move frequently in the last 2 hours before game time, while game totals are relatively stable. Does lumping them together obscure the signal?

**Q41.** The CLV capture window is T-30 to T+3. What is the industry standard capture window for CLV measurement? Is there evidence that the "true close" (the final price before tipoff) is at T-30 or T-5?

---

### SECTION 11: MARKET TIMING

**Q42.** What is the typical line movement pattern for NBA player props from opening (Sunday/Monday) to close? Is there a documented "sharp window" when line movement is most informative? When should the projection-based system place bets to maximize CLV?

**Q43.** For the stats in the KILLSHOT gate ({PTS, AST, 3PM, SOG}): which stat markets have the most predictable line movement patterns, and which are most volatile close to game time (injury news, lineup confirmations)? What is the optimal timing strategy per stat?

**Q44.** Does the current system have any mechanism for detecting when a line has already moved past the projected edge? This is critical — if the model projects 25.2 pts and the line opened at 24.5 but is now 25.5, the edge is gone. What is the best architecture for live line comparison vs. projection?

---

### SECTION 12: MODEL MONITORING & DRIFT

**Q45.** At what rolling MAE or Brier score degradation should a model refit be triggered? What are published best practices for monitoring sports model drift during a live season?

**Q46.** When should the Platt constants (A=1.4988, B=-0.8102, n=76) be refit? With n=80 live graded props now available, is a refit warranted? What is the minimum sample size at which Platt refit converges to a stable calibration?

**Q47.** Are there known structural breaks in NBA player prop markets that should trigger recalibration? (e.g., trade deadline, all-star break, playoff seeding being clinched, key injuries to stars.) Should the calibration be context-conditional rather than season-wide?

---

### SECTION 13: CROSS-SPORT ARCHITECTURE

**Q48.** For NHL SOG: the projection framework needs to be fundamentally different from NBA counting stats. What is the published best-practice architecture for NHL shots-on-goal projection? Should it be: Poisson rate (shots/60 min ice time), usage-adjusted (PP vs. EV splits), matchup-based (goalie SV%, opponent SOG-allowed), or a combination?

**Q49.** My NHL live betting results are 14-9 (61%) on n=23 primary+bonus — slightly better than NBA 34-23 (60%). Are NHL player prop markets historically more or less efficient than NBA markets? What does the sharp betting literature say about market efficiency differences by sport?

**Q50.** For MLB (currently in shadow): what is the appropriate statistical framework for pitcher strikeout props vs. batter hit/RBI props? What data sources replace nba_api for historical MLB game-level stats?

---

### SECTION 14: ADVANCED MODELING TECHNIQUES

**Q51.** What is the published research on Bayesian hierarchical models for NBA player projection, compared to the EWMA + Bayesian shrinkage approach I use? Would a hierarchical model (player nested in team nested in position) produce materially better accuracy at the required computational budget (must run in <60 seconds for a full slate)?

**Q52.** Is there published research comparing projection accuracy for NBA players with limited data (<15 games) across approaches: (a) positional prior, (b) salary-based prior, (c) career history shrinkage, (d) comparable-player clustering? What is the best-validated approach for the cold_start problem?

**Q53.** For the PTS formula (FGA decomposition path): I use USG% × team_FGA × (min/48) → player_FGA, then decompose into 2PA, 3PA, FTA. What is the published accuracy of FGA-decomposition approaches vs. direct per-minute PTS EWMA? Are there papers comparing these methodologies specifically for NBA player props?

**Q54.** Should pace elasticity exponents (PTS=0.90, REB=0.25, AST=0.50) be fit empirically per season rather than theoretically derived? What methodology should be used — regression of rate_change vs. pace_change across games within a season?

**Q55.** What is the published approach for lineup-conditional projections (when a key player is out, redistribution of minutes and usage)? My system currently updates each player independently — does any published model implement a team-constraint where total projected minutes must sum to ~240?

---

### SECTION 15: BANKROLL & SIZING INTERACTION

**Q56.** My system shows +4.13u profit on 80 graded picks (average stake ~1.0u). The Kelly criterion is not being used directly — what is the relationship between the current sizing formula (VAKE) and Kelly-optimal sizing, given a model with ~60% hit rate at average odds of -115?

**Q57.** T2 is 16-4 (80%) while T1 is 16-14 (53%) — counterintuitively, the lower-ranked tier has a much better hit rate. What is the probability this is variance vs. genuine model misordering, and how should tier assignment be redesigned? Does this suggest the current pick_score weighting is miscalibrated?

**Q58.** The daily 12u cap was set conservatively. Given a model with ~60% hit rate and ~80 picks over 18 days (4.4 picks/day), what is the Kelly-optimal daily betting volume? How does the optimal volume change at different assumed edge levels (1%, 3%, 5%)?

---

### SECTION 16: DATABASE & OPERATIONAL

**Q59.** My player_game_stats table has 83,719 rows covering Oct 2023 – Apr 2026. What is the minimum historical depth needed for stable EWMA projections, given the span sizes I use (max=15 games)? Am I using more historical data than necessary, or is the full 2.5-season history genuinely contributing to projection accuracy?

**Q60.** cold_start is 34% of projections — this likely means the DB has players with limited history who will never be bet on, polluting the average stats. Should the projection pipeline filter to only project players with ≥N games in the DB before running through the full model, and what is the right N?

**Q61.** What is the best-practice approach for handling mid-season trades in a rolling-average projection model? My current approach (60/40 blend over 6 games) — is there published research on the right blending methodology, and does the empirical accuracy of projections for traded players on days 1-10 vs. days 11+ show the expected improvement?

**Q62.** The projections table only covers Apr 18-29, 2026 (8 dates). This means I have no backtest data from regular season 2025-26. What is the priority for building out a full-season backtest — should it be done by fetching historical game data and running the projector retrospectively, and how long would that take?

---

### SECTION 17: PARLAYS — DAILY LAY & SGP

**Q63.** Daily Lay hit rate is 3-6 (33%) on n=9. For a 3-leg alt-spread parlay at max +100 combined odds, what is the theoretical breakeven hit rate, and is 33% above or below break-even given the typical per-leg odds structure?

**Q64.** SGP hit rate is 3-5 (38%) on n=8. For a 4-leg SGP at +200-450 range, what is the theoretical breakeven hit rate? Is 38% above or below break-even? What sample size is needed to have a confident assessment of SGP edge?

**Q65.** What does the published sports betting literature say about parlay construction in correlated markets? Specifically for same-game parlays where the legs involve the same player (e.g., PTS+REB+AST for one player) — is there published research on whether these correlations are correctly priced by books?

---

### SECTION 18: SYSTEM-WIDE CRITICAL GAPS

**Q66.** ⚠️ The most critical finding in this system: win_prob and edge have zero discrimination between winners and losers (n=80). List every possible cause of this failure in order of likelihood, with the most common published causes of calibration collapse in sports prop models. What is the diagnostic approach to identify which cause applies here?

**Q67.** The cold_start category being 34% of projections suggests the role assignment system may be fundamentally broken — it's not classifying players correctly if 1 in 3 projected players has no role. What is the diagnostic approach, and what should the expected distribution of role tiers be for an NBA slate?

**Q68.** With only 8 distinct projection dates (all playoff games) and zero regular-season projection history in the DB, the model has never been validated on regular-season games. What is the risk that the EWMA constants and blending alphas, which were calibrated on playoff games, are systematically miscalibrated for regular-season projection? How large might the accuracy gap be?

**Q69.** The system started April 14, 2026 — the final weeks of the NBA regular season + first round of playoffs. This is the least representative sample of a normal NBA betting season. What are the specific ways this start timing creates bias in all current benchmarks (W-L%, edge, CLV, pick_score reliability)?

**Q70.** Given all the above benchmarks and gaps, what is the recommended prioritized roadmap for improving this projection engine over the next 90 days? Which improvements have the highest expected impact on adj MAE, CLV, and hit rate, based on published research?

---

*End of Research Brief 6 — May 2, 2026*
*System: JonnyParlay custom NBA projection engine v1.0 (custom_v1)*
*Author: Jono (jonopeshut@gmail.com)*
