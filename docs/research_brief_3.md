# Deep Research Brief Part 3: Multi-Stat Decomposition, Vegas Integration & ML Ceiling

## Who I Am and What I'm Building

Solo developer / sports bettor. I run a Discord-based picks service (picksbyjonny) and operate a
Python betting engine (run_picks.py) that generates NBA player prop picks daily. I'm replacing
SaberSim as my projection input with a custom engine I've built from scratch. The go-live gate is:
custom model CLV >= SaberSim CLV over 100+ live picks. This is a real-money system — accuracy
improvements translate directly to betting edge.

## System Architecture

**Stack:** Python 3.13, SQLite (WAL mode), nba_api for data pull, pandas/numpy for computation.
Windows 11. No ML infrastructure yet — pure statistical/mathematical model. Solo dev.

**Data:** SQLite DB (`data/projections.db`, ~15 MB). Three seasons of NBA box scores pulled via
nba_api: 2023-24, 2024-25, 2025-26. Tables:

- `player_game_stats` — per-game box score rows (min, fgm, fga, fg3m, fg3a, ftm, fta, oreb, dreb,
  reb, ast, stl, blk, tov, pts, plus_minus, starter_flag, ts_pct)
- `games` — game metadata (game_date, home_team_id, away_team_id, season, season_type, era_weight)
- `players` — player metadata (position, team_id)
- `teams` — team abbreviations
- `team_season_stats` — team-level pace, off_rtg, def_rtg, net_rtg per season
- `team_def_splits` — DvP table: opponent-allowed rates by (team_id, season, position_group, stat),
  expressed as a ratio vs league average. Confirmed clean: avg ratio ~1.000, range [0.87, 1.19].
- `projections` — output store for CLV tracking and backtesting

**Era weights applied:** 2021-22: 0.15 / 2022-23: 0.30 / 2023-24: 0.50 / 2024-25: 0.75 /
2025-26: 1.00. Applied inside EWMA computation, not as a separate weighting step.

**What I do NOT have:** shot location data, play-type data (iso%, PnR%), on/off splits, lineup
five-man data, real-time prop lines in the DB, opponent pace at game level (only season-level).
Have Odds API key for live odds — historical props not stored yet.

## Current Engine: nba_projector.py

### Role classification
Players assigned to: starter / sixth_man / rotation / spot / cold_start based on last 10 games
(avg minutes + starter rate). Role-conditional floor/ceiling bounds and priors.

### Minutes projection (`project_minutes`)
EWMA span=5 (EWMA_SPAN_MIN). Role-conditional prior from ROLE_MINUTE_PRIOR dict. B2B flag applies
role-specific reduction (starter: 0.90x, down to spot: 0.82x). Spread input applies blowout
reduction if |spread| > 12 (BLOWOUT_SPREAD_THRESHOLD = 12.0, reduction = 0.80x). Cold-start falls
back to role prior.

### PTS model (FGA decomposition + blend)
```
team_proj_fga   = team_avg_fga * pace_factor        # pace_factor = team_pace / 99.5
player_proj_fga = (USG%/100) * team_proj_fga * (proj_min/48)
player_proj_3pa = fg3a_rate * player_proj_fga
player_proj_2pa = (1 - fg3a_rate) * player_proj_fga
player_proj_fta = fta_fga_ratio * player_proj_fga
proj_pts_fga    = 2PA*2*fg2_pct + 3PA*3*fg3_pct + FTA*ft_pct
proj_pts_fga   *= matchup_pts                        # DvP, clipped [0.80, 1.20]
baseline_pts    = rates["pts"] * proj_min            # EWMA per-min rate
proj_pts        = 0.50*proj_pts_fga + 0.50*baseline_pts   # 50/50 blend
```

Bayesian priors: fg2_pct padded to 300 FGA, fg3_pct to 750 FGA, ft_pct to 50 attempts.
LG_FTA_FGA = 0.257 (calibrated iteratively on 2025-26 data).
EWMA_SPAN = 10 for all shooting/per-min rates.

### All other stats (REB, AST, 3PM, STL, BLK, TOV)
```
projected_stat = per_min_rate * proj_min * matchup_factor * pace_factor
```
Pure EWMA per-minute rate, no decomposition model. DvP applied from team_def_splits.

### Cold-start fallback
Players with <5 games on team use archetype per-36 priors:
- Guard: pts=14.5, reb=3.2, ast=5.8, fg3m=1.8, stl=1.2, blk=0.3
- Forward: pts=13.8, reb=5.8, ast=2.8, fg3m=1.2, stl=0.9, blk=0.6
- Center: pts=13.2, reb=9.4, ast=1.8, fg3m=0.4, stl=0.7, blk=1.8

### Output
CSV matching SaberSim's schema exactly (player, team, opp, min, pts, reb, ast, 3pm, stl, blk,
plus percentile columns). Feeds directly into run_picks.py for pick generation.

## What Has Already Been Tried and Ruled Out

- **Season filter on historical lookups** — filtering `get_player_recent_games` to same season only
  killed all lookups for early-season games (no prior-season data). Removed. Model uses all-season
  history with era weights.
- **Raw pace as pace_factor** — using raw pace value (~100) instead of normalised ratio (~1.0)
  produced MAE=1469. Fixed to `pace_factor = team_pace / LEAGUE_AVG_PACE`.
- **DvP as disabled** — was incorrectly disabled with a comment claiming avg ratio >1.0 was a data
  artefact. Verified the data: avg ratio is actually 1.000 across all seasons/positions, range
  [0.87, 1.19]. Re-enabled.
- **LG_FTA_FGA calibration iterations:** 0.280 → bias +0.510; 0.245 → bias -0.651; 0.265 → bias
  +0.431; 0.257 → bias +0.005. Settled at 0.257.
- **FGA-only custom vs baseline:** custom alone MAE 4.782 (bias +0.005), baseline alone 4.690
  (bias -0.548). Custom beats bias but loses on variance. Blend wins on both.

## Current Evaluation Results

Evaluation harness: `engine/evaluate_projector.py`. Fixed seed=42, n=2000 player-game samples,
min>=20 minutes filter, 2025-26 season. Reproducible.

| Stat | Custom MAE | Baseline MAE | Bias   | Status                      |
|------|-----------|--------------|--------|-----------------------------|
| PTS  | 4.668     | 4.690        | -0.272 | Custom BETTER (blend wired) |
| REB  | 1.914     | 1.914        | -0.072 | Per-min only, no custom     |
| AST  | 1.517     | 1.517        | -0.023 | Per-min only, no custom     |
| 3PM  | 1.065     | 1.065        | -0.051 | Per-min only, no custom     |
| STL  | 0.830     | 0.830        | +0.044 | Per-min only, no custom     |
| BLK  | 0.597     | 0.597        | -0.004 | Per-min only, no custom     |

Custom = Baseline for all non-PTS stats because both paths call the same `project_per_min`
function. There is no differentiation yet.

## What Changed in this Brief vs Previous Briefs

Brief 1 covered: possession-level decomposition rationale, USG% data, model approach selection.
Brief 2 covered: calibration methodology, lookback windows, variance decomposition, B2B effects.

This brief is about everything that comes after the PTS model is solid:
- Extending decomposition cleanly to REB, AST, 3PM, STL, BLK
- Vegas integration without contaminating CLV edge
- Out-of-sample validation protocol
- When hand-crafted rates hit a ceiling that only ML can break
- Whether MAE optimisation is even the right objective for a betting model

I'm done debating whether possession-level decomposition is the right idea. It is. I need concrete,
implementable answers now.

---

## Research Questions

### 1. PTS — Three Unresolved Items

**1a. Blend weight optimisation.** α=0.50 was the obvious midpoint, not the empirically optimal
value. Need: the grid-search methodology (0.10 to 0.90 in 0.05 steps, fixed seed, fixed n), the
published or community consensus on whether optimal α is stable across seasons or drifts, and
whether the optimal weight should be dynamic — e.g. shift toward the FGA path when sample size is
large (stable rates) and toward per-minute when sample is small (noisy rates).

**1b. Systematic -0.272 bias in blended custom.** The FGA decomposition path has near-zero bias
(+0.005) but the 50/50 blend inherits half the baseline's -0.548 underprediction, landing at
-0.272. Options: (i) re-fit LG_FTA_FGA with the blend in place, (ii) add a simple additive bias
correction term, (iii) accept it as within noise. These are different philosophies with different
maintainability implications. Which is correct and why?

**1c. Pace factor: which pace?** Currently using team offensive pace only, normalised to league
average (99.5). Game pace is set by both teams. Is `(team_off_pace + opp_def_pace) / 2` the
standard? Does the literature use something more nuanced — opponent adjusted pace, net possessions
from play-by-play? What does the incremental gain look like from switching?

### 2. REB — Needs a Decomposition Model

The DB has `oreb` and `dreb` as separate columns in player_game_stats, and team-level FGA,
FG%, and pace in team_season_stats. All the ingredients exist.

**2a. Available rebounds decomposition.** Standard formula appears to be:
`player_reb_rate × team_available_rebounds`
where `available_reb = (opp_FGA × (1 - opp_FG%)) + (own_FGA × (1 - own_FG%) × (1 - own_OREB%))`.
Is this the consensus structure? What variants do top projection sites (NumberFire, RotoWire,
Established Names) actually use? What does the literature say?

**2b. OREB vs DREB split.** Should offensive and defensive rebound rates be modelled separately
then summed, or is total REB rate sufficient? What are the stabilisation timescales for OREB rate
vs DREB rate separately? Which has more signal?

**2c. Opponent OREB rate.** Teams that crash the offensive glass reduce defensive rebound
opportunities for opponents. How large is this effect quantitatively on individual DREB projections?
Is it worth modelling explicitly or does it get absorbed into the per-minute rate?

**2d. Position group granularity for REB DvP.** The current DvP groups are Guard / Forward /
Center. For rebounding specifically, is this granular enough, or should it be PF vs C separately
given how different their rebounding roles are?

### 3. AST — Needs a Decomposition Model

The DB has `ast` and `tov` per game, team pace, and player position.

**3a. Assist rate × possessions model.** Standard structure: `player_ast_rate × team_possessions`.
What is the exact definition of assist rate used by projection systems — AST per possession, AST per
minute, AST per FGA? What's the stabilisation sample size for each definition?

**3b. Teammate shooting quality.** Assists require made shots. If a player's primary teammates are
shooting cold, AST opportunities collapse. How significant is this effect on a game-to-game basis?
Is there a clean way to model it without lineup-level data (which I don't have)?

**3c. Secondary playmaker problem.** Lead guards have stable AST rates across minutes; forwards and
centers accumulate assists in clusters when the primary PG sits. EWMA span=10 likely oversmooths
role-change signal for non-PG playmakers. What's the best approach — shorter span for non-PG
positions, role-conditional AST priors, something else?

**3d. Pace interaction.** Does pace affect AST opportunities proportionally (more possessions =
more AST opportunities) the same way it affects scoring opportunities? Or does pace affect AST
non-linearly because ball movement patterns change?

### 4. 3PM — Free Signal Currently Being Ignored

The PTS FGA decomposition already computes `proj_3pa × fg3_pct` internally. This number exists in
memory during every PTS projection but is discarded. It's almost certainly the better 3PM estimate
than per-minute rate.

**4a. Confirm this is standard practice.** Do projection systems extract 3PM from the same
decomposition path used for PTS, or do they model it separately? Is there a published reason to
prefer separate modelling?

**4b. 3P% stabilisation asymmetry.** True stabilisation needs ~750 3PA. At 20 games × 3-5 3PA per
game, we have ~60-100 attempts — far below stabilisation. The Bayesian prior pulls heavily toward
league average. For genuinely hot or cold shooters, is this pulling too hard? How does the
literature handle this — separate prior weights for known shooters vs role players vs non-shooters?

**4c. Opponent 3PA-allowed rate.** Some teams force 3s from weak shooters; others suppress via
switching. Is this adequately captured by general DvP-by-position, or does it need a separate
opponent 3PA-allowed rate model distinct from the DvP ratio?

### 5. STL / BLK — Fundamental Distribution Question

**5a. Poisson vs Normal.** STL and BLK are low-count Poisson events (0/1/2 with rare 3+). EWMA
assumes Normal. For Poisson-distributed counts, Poisson regression or negative binomial is
theoretically correct. What's the published or community-measured MAE improvement from switching
distributions? Is it worth the implementation complexity for a solo dev?

**5b. STL — opponent turnover rate.** Teams that turn it over more give defenders more steal
opportunities. How predictive is opponent TOV% for individual STL projections, and is this data
already computable from what's in the DB?

**5c. BLK — shot location ceiling.** Without shot-location data, I can't know whether a player is
in a position to block shots. What's the realistic ceiling on a box-score-only BLK model vs a
tracking-aware one? Is BLK even worth decomposing further without tracking data, or should I accept
the per-minute approach as the effective ceiling?

**5d. Position as hard multiplier.** BLK is extremely position-concentrated (C > PF >> rest). Does
the EWMA implicitly capture this because centers simply have high historical per-minute rates, or
should position group be a hard prior multiplier applied before EWMA?

### 6. Minutes — Two Unresolved Sub-Questions

Minutes variance is likely the single largest driver of projection error. The model has B2B
reduction and blowout-spread reduction already. Two gaps:

**6a. Spread → blowout → minutes: functional form.** The current model applies a flat 0.80x
reduction when |spread| > 12. What's the empirically validated functional form? Is it a threshold
rule, linear scaling with spread, or a sigmoid? Is 12 the right threshold? What does the
win-probability literature say about the relationship between pre-game spread and probability of
each team playing full rotation minutes?

**6b. Days-rest granularity.** Currently using binary B2B flag only. Does the literature support a
continuous days-rest variable (1 day, 2 days, 3+ days) or does the effect collapse to B2B vs
not-B2B? Is there a meaningful performance difference between 2 days rest and 3+ days rest that I'm
missing by using binary?

### 7. Vegas Integration — Likely the Biggest Single MAE Gain

I have an Odds API key. Historical prop lines are not currently in the DB.

**7a. Published MAE reduction from Vegas prior.** DFS and sharp betting communities cite ~0.08-0.12
PTS MAE reduction from blending model output with the prop line. What is the actual research basis?
What methodology produces this estimate? Does the improvement vary by stat (e.g. larger for low-
count stats like STL/BLK)?

**7b. Optimal blend weight, and does it drift?** The cited technique is `0.60 × model + 0.40 ×
prop_line` but this is vague. What's the theoretically and empirically optimal blend weight? Does
it vary by stat? Crucially: does the optimal weight shift as my underlying model improves — i.e.
if my model gets sharper, should I weight away from the line because my model is incorporating
signal the line missed?

**7c. Game total and implied team total.** Implied team total = `(game_total/2) ± (spread/2)`.
How does this compare to raw pace as a scoring-environment proxy? Is implied team total strictly
dominant over pace as a feature? Should it replace pace_factor or augment it?

**7d. The stale line problem.** Prop lines posted the night before don't reflect morning injury
news or lineup confirmations. If I'm integrating a Vegas prior, its value depends heavily on when
I observe it relative to tip. How do sharp shops handle this — do they use the opening line, the
closing line, or a time-weighted blend? Does the optimal blend weight change depending on how stale
the line is when I integrate it?

**7e. CLV independence.** If my model's errors are correlated with the market's errors, my CLV edge
collapses even with good MAE. How do top quants measure whether projection residuals are
independent of market residuals? What's the standard test? And if I blend model output with the
prop line as a training feature, am I contaminating my ability to beat that same prop line?
Specifically: is there a circular reasoning trap in using the line as a feature and then betting
against the line?

### 8. Cross-Validation — Overfitting Risk

All calibration (LG_FTA_FGA=0.257, EWMA span=10, EWMA_SPAN_MIN=5, blend α=0.50, Bayesian prior
weights 300/750/50) is in-sample on 2025-26. The 2024-25 and 2023-24 seasons are in the DB and
available for out-of-sample testing.

**8a. Right validation structure.** Should I use: (a) full 2024-25 as holdout and 2025-26 as
train, (b) walk-forward by month within a season, (c) expanding window from oldest to newest, or
(d) some combination? What does the sports forecasting literature recommend for EWMA-style models
where the model itself only looks backward?

**8b. Time-series CV vs random K-fold.** EWMA models look backward, so random K-fold doesn't leak
future data into the model itself — it only leaks into calibration constants. How material is this
leakage in practice for sports projection models? Does walk-forward CV significantly change the
calibrated constants vs naive random splits?

**8c. Which constants drift season-to-season.** Of the following, which are known to be stable
across seasons (safe to calibrate once) and which need annual re-fitting: EWMA span, Bayesian prior
weights (300/750/50), blend α, LG_FTA_FGA, DvP clip range [0.80, 1.20], era weights? What does
the research say about NBA rule changes (pace shifts, foul rule changes) and their effect on model
constants?

### 9. Data I Don't Have — ROI-Ranked

For each data category below, I need a rough estimate of MAE impact and the cost/accessibility of
integration for a solo dev with Python access:

- **Play-type data** (iso%, PnR ball-handler%, post-up%) — Second Spectrum / NBA tracking
- **Shot quality / xFG%** from shot location — nba_api has some shot chart endpoints
- **On/off splits** — available via nba_api (but adds schema complexity)
- **Lineup five-man stats** — available via nba_api
- **Real-time injury / minutes-restriction confirmation** — practice reports, beat reporters
- **Travel data** — miles traveled, timezone crossings, local game time
- **Historical prop lines** — backfillable via Odds API (I have the key)

Which of these has the highest ROI per hour of integration time? Which can I safely ignore because
the MAE signal is too small to matter?

### 10. ML Transition — When Does Hand-Crafted Hit a Ceiling?

**10a. Published box-score-only MAE floor.** What's the published or community-estimated MAE floor
for a box-score-only NBA PTS projection model? How much further does tracking data realistically
take you on top of that?

**10b. Concrete transition criteria.** What are the signals that indicate I've outgrown EWMA + 
priors and a supervised model (XGBoost, LightGBM, hierarchical Bayes) would provide a meaningful
lift? Is there a sample-size threshold, a residual-pattern test, or a model-complexity heuristic
that the literature uses?

**10c. Feature set for an ML version.** If I transition, the natural feature set is: role tier,
5/10/20-game form splits, DvP matchup rating, pace factor, B2B flag, home/away, days rest, season
context (month, playoff proximity), implied team total, lineup completeness score. What's missing
or wrong about this feature set? What does the literature say are the highest-weight features for
NBA player prop prediction?

**10d. Architecture recommendation.** At my current data volume (~3 seasons, ~30 players per game,
~1,200 games), is a gradient boosting model (XGBoost/LightGBM) the right starting point, or does
the sample size favour simpler approaches (ridge regression, Gaussian process)? What's the
practical tradeoff for a solo dev?

### 11. Betting-Specific Calibration — The Real Objective

**11a. MAE vs pick accuracy.** MAE minimisation is a proxy. The actual objective is `% of picks
where projection > line correctly predicts the over`. How well do these correlate empirically in
the NBA props literature? Is there a known case where MAE and pick accuracy diverge significantly?

**11b. Win-probability calibration.** `win_prob` in my pick engine is derived from the projection
vs prop-line gap. Do picks with 60% projected win-prob actually win 60%? What's the standard
calibration check (Brier score, reliability diagram) and the standard fix (Platt scaling, isotonic
regression) for a sports betting model specifically?

**11c. CLV as the ground truth.** My system measures CLV = (closing implied prob − entry implied
prob). Positive CLV = beat the close. What's the relationship between model MAE, pick accuracy,
and CLV? Is there published research on which model quality metric best predicts long-run CLV
performance?

**11d. Optimising for CLV directly.** Instead of minimising MAE and hoping it translates to CLV,
is there a way to directly optimise for CLV as the training objective? What would that look like
mathematically? Has anyone published on this in a sports context?

---

## Deliverable

A structured report with:

1. **Executive summary** — top 5 changes ranked by expected reduction in PTS MAE AND expected lift
   in pick accuracy / CLV. The two lists may differ. I want both, with rough quantified estimates
   where available.

2. **Per-stat decomposition templates** — drop-in formulas for REB, AST, 3PM, STL, BLK following
   the same structure as the PTS path above, with stabilisation sample sizes for each underlying
   rate. Format these as pseudocode I can translate directly to Python.

3. **Vegas integration playbook** — concrete steps for adding game total, implied team total, and
   prop line as features, including recommended blend weights, the stale-line handling strategy,
   and the CLV-independence test.

4. **Cross-validation protocol** — exact recommended structure for out-of-sample testing on
   2024-25 and 2023-24, with a table of which constants need annual re-fitting vs which are stable.

5. **Data acquisition ranked list** — the §9 categories sorted by MAE impact per hour of solo-dev
   integration time. Top 3 to chase, bottom 3 to ignore.

6. **ML transition criteria** — concrete signals for when to switch, the recommended architecture
   to start with, and the minimal feature set to build first.

7. **Betting calibration section** — how to convert from MAE-optimal to CLV-optimal, with the
   specific calibration tests to run against my pick_log.csv data.

---

## Sources to Prioritise

- Sloan Sports Analytics Conference papers on NBA forecasting and box-score vs tracking ceilings
- JQAS, arXiv on NBA player performance prediction and reliability/stabilisation studies
- DFS community methodology: FantasyLabs, ETR, Awesemo, RotoGrinders — blend-weight research
- Sharp prop / DFS quant accounts that publish CLV-independence or win-prob calibration work
- Sports betting model calibration literature (Brier scores, isotonic regression)
- Basketball-Reference and PBP Stats stabilisation tables

## Sources to Deprioritise

- Generic SEO DFS content without methodology
- Pre-2020 research unless it's foundational reliability/stabilisation work
- Vendor marketing without published methodology

## What Success Looks Like

After reading this report I have:
(a) Drop-in formulas for REB / AST / 3PM / STL / BLK at the same rigour level as my PTS path
(b) A clear order of operations for adding Vegas features without contaminating CLV edge
(c) An out-of-sample validation protocol I can run immediately against 2024-25 data in the DB
(d) A defensible answer to "stay hand-crafted or switch to ML" with specific transition criteria
(e) The right calibration tests to confirm that lower MAE actually translates to winning picks
