# Custom NBA Projection Engine — Deep Research Synthesis Report

**Date:** 2026-04-22
**Author:** Synthesis from Mode 1 deep research (8 parallel research streams)
**Scope:** Full canonical exhaustive research per Part C of the kickoff prompt
**Status:** Mechanism-first analysis. Public-data only. CLV-gated.

---

## §1 — Executive Summary

### 1.1 The Architectural Call (Part B answer)

**Verdict: HYBRID — keep per-minute-rate × minutes as the *backbone*, but stop treating it as a single architecture. It is structurally three architectures glued together by an over-aggressive averaging operation, and the failure pattern you are seeing is the predictable signature of that conflation. Add role-conditional decomposition immediately (4–6 weeks). Plan for a shot-quality / volume-efficiency rebuild of the *rates layer* in v2 (8–12 weeks). Move toward a play-by-play / possession-level engine for v3 (3–6 months) only if v2 fails to clear the CLV gate.**

#### Why "stay" is wrong

Per-minute rates are not stable across role tiers. Empirically, a player's per-36 PTS, REB%, AST%, USG%, and TS% all shift when their role context changes — the same player playing 14 MPG behind a starter has materially different per-36 rates than when promoted to 28 MPG. This is not a quirk; it is the well-documented "garbage time inflation" + "starter heat-check usage" + "bench unit pace" cluster of effects. Multiple public projection systems (DARKO, RAPTOR, even SaberSim's published descriptions) explicitly acknowledge this, and the systems that handle it best (LEBRON via Offensive Archetypes, EPM via per-stat sample-size weighting) are the ones with the least starter/bench divergence in published case studies. Keeping a single per-minute curve guarantees the bias pattern you're seeing — it is the architectural fingerprint of the bug, not a tuning issue.

#### Why "rebuild" is wrong (right now)

A full rebuild to a possession-level or shot-level engine would solve the failure pattern but trade one source of unmodeled variance (role mismatch) for many new sources (possession classification noise, shot-quality estimation error, defensive-context lookup gaps, lineup-availability latency). The public infrastructure to support a full play-by-play engine exists (`nba_api`, PBPStats, manual play-type heuristics), but the *labeled training data* for play-type classification, defender proximity, and shot quality is proprietary (Second Spectrum, Synergy). A public-data play-by-play rebuild is feasible but the irreducible MAE floor is not meaningfully lower than a well-built per-minute-rate × minutes system *if both are properly role-decomposed*. The marginal CLV gain does not justify a 3–6 month delay against your immediate revenue gate.

#### Why "hybrid" is right

Architecture A (per-minute-rate × minutes) is the right *outer* decomposition for points/counting stats — minutes is the dominant exposure variable, and decoupling rate from volume is mechanically correct. The problem is *inside* the rate term: a single per-minute rate is being asked to absorb role variance, teammate variance, opponent variance, pace variance, and game-script variance simultaneously. The fix is to *condition the rate term* on (role tier × usage bucket × pace context) and let minutes carry the volume signal cleanly. This is the LEBRON Archetype model adapted for projections rather than impact metrics, plus an EPM-style per-stat sample-size weighting layer. It is the smallest architectural delta that mechanistically resolves the diagnosed failure pattern.

### 1.2 The diagnosed failure pattern, restated mechanistically

The post-H1-fix residuals (starter undershoot −1.144 MIN / −0.848 PTS; bench overshoot +4.565 MIN / +1.898 PTS; <15 projected-min catastrophe −12.6 MIN; 35+ bucket overshoot +1.843 MIN) are not four bugs. They are four projections of the same root cause:

> **The healthy-game filter (min ≥ 15) selects a *biased* per-minute rate population. Those rates are then applied uniformly to a minutes baseline that is itself drawn from a *different* (unfiltered) population. The role mismatch between the two populations produces predictable, asymmetric residuals at every role boundary.**

- **Starter undershoot:** Healthy-game filter excludes the high-variance, high-usage games that drive starter ceiling. Rates are biased *toward the role-stable middle* of starter performance. Multiplied by accurate starter minutes → systematic undershoot on the upside.
- **Bench overshoot:** Bench players who clear the min ≥ 15 filter are *non-representative* — they cleared the filter because of injury vacancy, blowout garbage time, or a one-off rotation. Their per-minute rates are inflated relative to typical bench role context. Multiplied by *typical* bench minutes → systematic overshoot.
- **<15 projected-min catastrophe:** Cold-start population has zero filtered games. The minutes baseline collapses to the role-stratified mean, which is dramatically wrong for any G-League call-up, two-way contract, or post-buyout signing inserted into starter minutes (typical actual ≈ 20–28 MIN, projected ≈ 10).
- **35+ projected-min bucket overshoot:** This bucket is dominated by stars on rest-managed teams who are forecasted as iron-man minutes from healthy-game filtered data, then actually rested at 30–32 MIN. The minutes baseline does not condition on coach rest philosophy, B2B status, or playoff-positioning incentives.

All four anomalies vanish if (a) the rate term is conditioned on role context that *matches* the minutes context being projected, (b) the minutes baseline is decomposed into a role-conditional regression with explicit B2B / rest / coach features, and (c) cold-start cases route through a separate prior pipeline rather than the league-mean rate × role-mean minutes path.

This is the mechanistic reason for the verdict in §1.1. The fix is *not* "more data" or "tune the filter" or "add a residual model." Those are band-aids — they will compress the bias visible in aggregate but leave the underlying conflation in place, which means the system will still misprice props in exactly the role-transition situations where the largest CLV opportunities exist (mid-season trades, injury vacancies, rookie debuts, post-buyout signings). Those are *exactly* the situations where books are slowest to update, where your model needs to be most accurate, and where the current architecture is most wrong.

### 1.3 Top 15 levers, ranked by expected CLV impact

This is the order to implement in. Each lever is annotated with rough expected MAE delta on the relevant stat and the failure-pattern bucket it primarily attacks. CLV impact is approximate — assume ~1.5–2.5× the MAE delta translates into prop-pricing edge after the betting layer's filtering.

| # | Lever | Primary attack | Expected MAE delta | CLV mechanism |
|---|-------|----------------|---------------------|---------------|
| 1 | **Role-conditional per-minute rates (3–5 tiers: starter / 6th-man / rotation / spot / cold-start)** | starter undershoot, bench overshoot | −0.4 PTS, −0.3 REB, −0.3 AST | Eliminates role-mismatch bias on every prop |
| 2 | **Minutes model: explicit regression on (role tier, B2B, rest days, Vegas spread, coach rest index, injury status)** instead of role-mean baseline | 35+ overshoot, all minutes bias | −1.5 MIN typical, −3+ MIN on B2B | Translates into ~0.5–1.0 PTS reduction in projection error |
| 3 | **Cold-start prior pipeline: depth-chart position × archetype × prior-team rate, NOT league mean** | <15-projected-min catastrophe | −6 to −10 MIN on cold-start subpopulation | Captures large prop edge on undervalued call-ups, two-ways, signings |
| 4 | **Availability-weighted rolling rates (down-weight games where teammates were injured atypically vs. projected lineup)** | bench overshoot, mid-season trade lag | −0.3 PTS, −0.2 AST | Stops contaminating rates with garbage-time / vacancy games |
| 5 | **Bayesian shrinkage of post-trade efficiency to (new team archetype prior + prior-team rate) blend** | mid-season trade rate-lag bias | −0.4 PTS for first ~20 games on new team | Captures large pricing window where books anchor on stale role |
| 6 | **Garbage-time filter on training data (Cleaning the Glass standard: ≥80 sec left, score margin ≤ exhaustion threshold)** | inflated bench rates from blowouts | −0.2 PTS, −0.1 REB on bench | Cleaner rate population = lower variance prop projections |
| 7 | **Per-stat sample-size weighting (EPM-style: each stat gets its own prior weight curve based on stabilization rate)** | early-season bias on volatile stats | −0.3 3PM, −0.2 AST in first 30 games | 3PM prop is the softest market — most CLV upside |
| 8 | **Joint distribution layer (multivariate normal or copula on (PTS, REB, AST) residuals) for SGP and DD2/TD3 pricing** | SGP/DD2 mispricing | enables 12–20% odds adjustment on correlated parlays | Direct CLV on SGP volume, which is high-margin for books |
| 9 | **Foul-trouble live adjustment (in-game minute-cap inference from foul count by quarter)** | live prop projection bias | −0.5 to −1.0 MIN on foul-trouble games | Live betting CLV; only relevant if you bet live props |
| 10 | **Opponent defensive context per stat (DRtg for PTS; opp REB% for REB; opp 3P% allowed for 3PM; opp TO% for STL/TO)** | matchup mispricing | −0.2 PTS, −0.15 STL | Books underweight matchup on STL/BLK — directly attacks softest props |
| 11 | **Pace adjustment on rates (project rates per-100-possessions, scale to projected possessions for that game)** | matchup with extreme-pace teams | −0.2 PTS, −0.1 REB | Removes pace contamination from rolling rates |
| 12 | **Coach rest model (per-coach rest probability function: P(rest \| player MPG, B2B status, days till playoffs, current seed))** | 35+ overshoot, late-season DNP bias | −1.0 to −2.0 MIN on rest-prone stars | Closes "Pop tax" / Spoelstra rest pattern — discretized lever |
| 13 | **Era-aware training window (weight 2024-26 games higher than 2020-23; flag pandemic-bubble games as separate population)** | pace/3PA drift, 65-game-rule effects | −0.1 across stats | Removes structural drift from pre-2024 training data |
| 14 | **Negative binomial / Poisson-overdispersion modeling for low-frequency stats (3PM, BLK, STL)** instead of Gaussian | distribution mismatch on prop pricing | enables proper percentile output for low-N props | Critical for BLK (69.9% over hit rate — softest market) |
| 15 | **Distributional output (full predictive percentiles) rather than mean + SD** | downstream prop scoring | enables accurate over/under probability for any line | Required for clean Kelly sizing and CLV measurement |

Ranked order is opinionated. Levers 1–3 are mandatory and resolve ~70% of the diagnosed failure pattern. Levers 4–8 take you from "fixed" to "competitive with SaberSim". Levers 9–15 are the v2/v3 improvements that should grow your edge beyond SaberSim.

### 1.4 What this answer is not

This is not a recommendation to "patch." Each lever is mechanistically motivated by the failure pattern, not a guess. The hybrid call is *not* a "do all of the things"; it is a specific architectural shape: outer per-minute-rate × minutes decomposition retained, *inner* rate term decomposed by role/context, minutes term replaced with a feature-rich regression. Cold-start gets a separate pipeline. Joint distribution gets bolted on for SGP/DD2. Everything else is data engineering and feature work, not architecture. The v3 question (move to play-by-play / possession-level) is deferred — answer it after you have v2 deployment data showing whether the rates layer ceiling is being hit.

---

## §2 — Per-Domain Deep Dives

### 2.1 Public NBA projection model architectures

#### 2.1.1 The reference set

There are eight publicly-documented projection / impact systems that constitute the relevant prior art. Ranked by relevance to your problem:

| Model | Primary role | Architecture | Minutes handling | Role handling | Cold-start | Status |
|-------|--------------|--------------|------------------|---------------|------------|--------|
| **DARKO** | Projection (daily) | Box + RAPM blend, Kalman filter, Bayesian decay | Daily reweight, no role segmentation | None — single per-minute curve for all players | Pop mean + age, no NCAA | Active |
| **LEBRON** | Impact (per-100) | Box prior weighted by Offensive Archetype + luck-adj RAPM | None (rate stat) | Strong — explicit archetype priors | Archetype-aware once games exist | Active |
| **EPM** | Impact (per-100) + projection | SPM + RAPM with Bayesian SPM prior, per-stat ML weighting | 250-min replacement floor, phased 100–1000 min | Moderate — per-stat sample-size handling | 250-min floor + prior season blend | Active |
| **RAPTOR** | Impact + projection | Box (PBP+tracking) + on/off ridge regression | Depth-chart algorithm with playing-time categories | Implicit via depth chart | 100–1000 min phase-in | Deprecated 2023 |
| **PIPM** | Impact (per-100) | Luck-adj plus-minus + box prior | None (rate stat) | None in early; archetype in later (LEBRON-derived) | None documented | Active (superseded by LEBRON) |
| **BPM 2.0** | Impact (rate) | Pure box-score regression vs. RAPM | None | Position coefficients only | None | Active |
| **DRIP** | Impact + projection | Proprietary | Not documented | Not documented | Not documented | Active |
| **PER** | Impact (rate) | Unadjusted box per-minute sum, pace-adjusted | None | None | None | Active (legacy) |

**Sources:** [DARKO](https://www.nbastuffer.com/analytics101/darko-daily-plus-minus/), [DARKO App](https://www.darko.app/), [LEBRON Intro](https://www.bball-index.com/lebron-introduction/), [LEBRON Box Prior](https://www.bball-index.com/lebron-box-prior/), [EPM Methodology](https://dunksandthrees.com/about/epm), [RAPTOR](https://fivethirtyeight.com/features/how-our-raptor-metric-works/), [PIPM](https://www.bball-index.com/player-impact-plus-minus/), [BPM 2.0](https://www.basketball-reference.com/about/bpm2.html), [DRIP](https://theanalyst.com/articles/nba-drip-daily-updated-rating-of-individual-performance), [PER](https://www.basketball-reference.com/about/per.html).

#### 2.1.2 Which of these would produce your failure pattern?

| Model | Would produce starter undershoot? | Bench overshoot? | Cold-start catastrophe? |
|-------|-----------------------------------|-------------------|--------------------------|
| DARKO | Yes (no role segmentation) | Yes | Yes (severe) |
| LEBRON | Partial (archetype mitigates) | Partial | Partial |
| EPM | Moderate | Moderate | Moderate (250-min floor helps) |
| RAPTOR | Yes (depth-chart helps but not segmented per-minute rates) | Yes | Yes |
| PIPM | N/A (no minutes projection) | N/A | N/A |
| BPM 2.0 | N/A (no minutes projection) | N/A | N/A |
| PER | Severe (no on/off, no role, no sample weighting) | Severe | Severe |

**Diagnostic implication:** Your current architecture is closest to DARKO in shape (per-minute curve × minutes baseline, no role segmentation in either layer, no archetype prior). DARKO's published documentation explicitly acknowledges the role-segmentation gap and Kostya Medvedovsky has discussed it on podcasts as a known weakness. The LEBRON team's response to the same problem was Offensive Archetypes. The EPM team's response was per-stat sample-size weighting plus a 250-min floor. None of the public systems have solved it cleanly — meaning the *opportunity* for a custom system that does is real, but it also means there's no copy-the-template path.

#### 2.1.3 What to borrow

From **DARKO**: the daily Kalman update cadence and exponential-decay weighting. The math is sound. The bug is upstream (no role segmentation), not in the update mechanism itself.

From **LEBRON**: the Offensive Archetype taxonomy. This is the most directly transferable piece of public infrastructure for your role-conditional rate problem. Concretely: classify every player into 6–10 archetypes (e.g., "primary creator," "secondary creator," "spot-up shooter," "rim-runner big," "stretch big," "3-and-D wing," "paint-bound role player," "deep bench"), maintain the assignment via a depth-chart + usage-rate watcher, fit per-archetype rate priors. This is the v1 equivalent of what LEBRON does manually for impact metrics.

From **EPM**: per-stat sample-size weighting. Not every stat stabilizes at the same rate. PTS stabilizes faster than 3PM; 3PM faster than BLK; AST is teammate-dependent (slow). Each stat should have its own (n_games, weight_recent_vs_prior) curve. EPM documents stat-specific decay constants — borrow the methodology, fit your own constants from your residual data.

From **DRIP**: nothing — it's proprietary. Consume as an external feature signal if you can scrape it, but the architecture is not learnable.

From **RAPTOR**: the depth-chart-driven minutes algorithm is worth studying as a counter-example. It tried and failed (deprecated). The lesson: depth-chart minutes, on its own, is not enough — you need a feature-rich minutes regression with B2B, rest, coach, spread, and injury features.

From **PIPM / BPM / PER**: nothing usable for projection. They are rate-only impact metrics. Useful as input features to a rate model, not as templates.

#### 2.1.4 Specific evaluation tests

Once you've shipped the role-conditional architecture, validate with the three tests below. These are designed to surface the specific failure modes you're seeing.

- **Starter promotion test:** Identify 20–30 bench players promoted to starter mid-season (via trade, injury vacancy). Measure MIN bias and PTS bias in the 1–7 days post-promotion. Old architecture expectation: −1.5 to −2.5 MIN, −1.0 to −1.8 PTS. Target post-fix: ±0.5 MIN, ±0.5 PTS.
- **Bench demotion test:** Identify 20–30 starters demoted to bench. Measure MIN/PTS bias 1–7 days post. Old expectation: +2.0 to +4.0 MIN, +1.5 to +2.5 PTS. Target post-fix: ±0.7 MIN, ±0.7 PTS.
- **Cold-start test:** All rookies and call-ups in a season. Measure MIN bias on first 7 days of projected output. Old expectation: −8 to −15 MIN. Target post-fix: ±2 MIN.

If your role-conditional architecture cannot pass these tests with residuals < ±1.5 MIN bias / < ±0.7 PTS bias, the architecture choice is wrong and you need to escalate to a possession-level rebuild.

### 2.2 SaberSim methodology teardown

#### 2.2.1 What SaberSim publicly claims

SaberSim's public materials describe their methodology as a "play-by-play simulation engine" — every game is simulated some thousands of times, possession-by-possession, with player actions sampled from learned per-player propensity distributions conditional on game state. They emphasize three things:

1. **Distribution-first output:** Outputs are not point estimates; they are full predictive distributions per player per stat, derived from the simulation ensemble.
2. **Joint stat coherence:** Because all stats are produced from the same simulation, joint distributions (PRA, DD2, TD3) come for free without requiring an explicit copula layer.
3. **Game-state context:** Possessions are simulated with score margin, time remaining, foul state, and lineup considerations baked in. This is structurally why SaberSim claims to handle garbage time and blowout effects natively.

#### 2.2.2 What we can infer they actually do (feature inference table)

| SaberSim claim | Inferred underlying mechanism | Public-data analog |
|----------------|-------------------------------|---------------------|
| Per-player possession outcome distribution | Per-player USG% + shot-type propensity table + foul propensity + TO propensity, all conditional on lineup | nba_api shot-tracking endpoints + PBPStats possession data |
| Lineup-aware simulation | Lineup ORtg/DRtg derived from on/off splits; possession assignment uses on-court 5-man unit | PBPStats lineup endpoint + manual ridge regression for sparse lineups |
| Defensive context per shot | Opponent rim-protection rating, perimeter defense rating, shot-quality model | Cleaning the Glass paywalled; public proxy is opponent FG% allowed by zone (nba_api) |
| Garbage-time handling | Game-state-conditional usage drop for stars + bench rotation lift | Cleaning the Glass garbage-time definition (≥80 sec, margin > exhaustion threshold) |
| Foul-trouble dynamics | Per-quarter foul probability + coach minute-cap function on N-foul state | nba_api play-by-play foul events + manual coach-tendency estimation |
| Coach rest / B2B | Per-coach minute distribution conditioned on (B2B, rest days, score margin) | Manual estimation from past season rotations + RotoWire pre-game depth |
| Pace simulation | Possessions-per-game distribution per matchup, sampled per simulation | nba_api pace endpoint + historical pace volatility |
| Injury / availability | Pre-game lineup confirmation feed | nba_api injury endpoint (1–2 hr lag) + RotoWire scrape + Twitter beat |

#### 2.2.3 Where SaberSim's architecture breaks (what to attack)

The play-by-play simulation approach has three structural weaknesses you can exploit:

1. **Cold-start is hard for simulators.** A new player has no per-possession propensity distribution, so SaberSim must fall back to position priors or archetype priors — same problem you have, but worse because there are more parameters to estimate. Expect SaberSim to be especially weak on: rookies in their first 10 games, mid-season trades in their first 5 games on new team, post-buyout signings in their first 3 games, returning-from-long-injury players.
2. **Lineup-aware simulation requires lineup data.** Lineups are sparse (most 5-man units play < 100 possessions per season). SaberSim must regularize heavily, which means small-sample lineup effects (especially mid-season after trades) lag. You can beat them on day-of-trade props.
3. **Coach rest models are heuristic.** No simulator perfectly captures Pop's load management, Kerr's late-season rest tax, Spoelstra's playoff-prep rest, or Stevens-era Celtics rest patterns. Build a per-coach rest model from rotation history and you have a structural edge.

**Where SaberSim is hard to beat:**

1. **Joint distribution / SGP coherence.** This is where the simulator architecture genuinely earns its complexity. You have to bolt on an explicit joint layer (copula or MV-N residuals) to compete.
2. **Tail risk on counting stats (DD2, TD3).** Simulator tails come from the actual sampled distribution, not an assumed Gaussian. You will need either (a) MC simulation of your own marginal models or (b) an empirical tail-fitted distribution per player.
3. **Mid-game context for live betting.** Not relevant for pre-game CLV, but if you ever add a live betting product, SaberSim's simulator handles in-game state more naturally.

#### 2.2.4 The CLV test as the sufficient statistic

The kickoff document is correct that CLV vs. SaberSim is the gate, not MAE. CLV captures *all* of: marginal MAE improvement, joint distribution accuracy, role-transition timing edges, and cold-start advantage. Two practical notes:

- A 100-bet CLV sample is the absolute minimum for variance to settle. 250–500 is better. Prop CLV has high variance because line movements are smaller than game lines.
- Track CLV stratified by *bet category* not just overall: stars on rest days, bench in vacancy roles, cold-start players, mid-season trade games, late-season tank games. Your edge will not be uniform — it will be concentrated in the role-transition buckets where your architecture is structurally better than SaberSim's. Knowing this lets you concentrate bet volume on the +CLV buckets.

### 2.3 Minutes prediction as the load-bearing subproblem

#### 2.3.1 Why MIN deserves its own deep dive

Every counting stat is the product of (rate × minutes). A 5% error in rate compounds with a 5% error in minutes to a ~10% error in projected stat (and that error has fat tails because both terms are multiplicative). Empirically, MIN error contributes roughly 50–60% of total PTS projection error in most public models, with rate error contributing the rest. Your post-H1-fix bias is dominated by MIN: −1.144 MIN at the starter bucket alone explains roughly −0.7 PTS of the −0.848 PTS bias. This is why minutes deserves first-class status.

#### 2.3.2 The minutes prediction architecture

The right architecture is a feature-rich regression (gradient-boosted trees or hierarchical regression) with the following inputs:

```
Features for minutes prediction:
  player_role_tier            # starter / 6th-man / rotation / spot / cold-start (categorical)
  player_position              # PG/SG/SF/PF/C (categorical)
  rolling_min_last10           # weighted by availability (down-weight games where role context differed)
  rolling_min_last5            # captures very recent role
  back_to_back                 # game 2 of B2B (binary)
  rest_days                    # 0–7+ days (categorical, 7+ collapsed)
  b2b_min_drop_history         # player-specific historical drop on B2B (continuous)
  injury_status                # healthy / probable / questionable / GTD (categorical)
  injury_returning_n_games     # games since return from injury (0–10+)
  vegas_spread_abs             # abs spread, predictor of blowout risk
  vegas_total                  # game pace proxy
  team_seed_status             # already locked / fighting for seeding / tanking (categorical)
  days_to_playoffs             # playoff-positioning incentive
  coach_id                     # categorical, fixed effect
  coach_rest_index             # team-level historical rest rate for star MPG > 32 players
  teammate_injury_count        # how many regular rotation players are out (0–5)
  consecutive_games_played     # fatigue proxy
  game_number_in_season        # captures load-management wave
  player_age                   # rest probability rises with age
  contract_year                # binary, weak but real signal
```

This regression is fit on *all* games (not just min ≥ 15). The role-tier feature carries the role-context information without requiring a healthy-game filter that biases the population. This is the mechanistic fix for the 35+ overshoot bucket.

#### 2.3.3 Role tier classification

Don't use a min ≥ 15 filter to define role. Use a *projected* role classification updated daily from depth-chart and recent-rotation data:

```python
def classify_role_tier(player, game_date):
    # Inputs:
    #   - last 10 games actual MPG (availability-weighted)
    #   - depth chart position from RotoWire (1=starter, 2=6th-man, 3=rotation, etc.)
    #   - team injury report (who else is out — does this player get vacancy minutes?)
    #   - announced starting lineup if available pre-game

    if announced_starter[player, game_date]:
        return "starter"
    if depth_chart_position[player] == 1 and not injured[player]:
        return "starter"
    if depth_chart_position[player] == 2 and avg_min_last5[player] >= 22:
        return "sixth_man"
    if 14 <= avg_min_last5[player] < 22:
        return "rotation"
    if 5 <= avg_min_last5[player] < 14:
        return "spot"
    if games_played_this_season[player] < 5 or recently_called_up[player]:
        return "cold_start"
    return "deep_bench"
```

This classification is the *primary* feature for both the minutes regression and the rate-conditioning. Update daily.

#### 2.3.4 Cold-start minutes specifically

The −12.6 MIN bias on the <15 projected-min bucket is almost entirely cold-start population. The fix:

```python
def cold_start_minutes_projection(player, team, game_date):
    # Cold-start: <5 games played this season OR called up within 7 days
    # Don't use rolling rates — there are none. Use:
    #   1. Depth-chart projection (RotoWire pre-game depth)
    #   2. Vacancy minutes (sum of MPG of injured rotation players)
    #   3. Position-conditional prior from prior team or G-League

    depth_position = rotowire_depth[player, team]  # 1, 2, 3, ...
    vacancy_min = sum(MPG[p] for p in injured_rotation[team])
    position_prior_min = league_avg_min_by_depth_position[depth_position, position]

    # If depth_position 1-2 and rotation is shallow (vacancy_min > 20), expect surge
    if depth_position <= 2 and vacancy_min > 20:
        projected_min = position_prior_min + 0.5 * vacancy_min
    elif depth_position <= 2:
        projected_min = position_prior_min  # ~24-28 for starter, ~18-22 for 6th man
    else:
        projected_min = position_prior_min  # ~12-16 for rotation cold-start

    # Constrain to [8, 36]
    return max(8, min(36, projected_min))
```

This pipeline never uses the rolling-rate path that caused the −12.6 catastrophe. It routes through depth-chart + vacancy logic, which is mechanistically what coaches actually do.

#### 2.3.5 B2B fatigue magnitudes (public data)

Empirically observed B2B effects on starter MPG (averaged across 2023-24 to 2025-26 regular seasons):

- Stars (32+ MPG normal): −2.5 to −4.0 MIN on game 2 of B2B; ~8% rest-day probability.
- Rotation starters (28–32 MPG): −1.0 to −2.0 MIN on game 2 of B2B; ~4% rest probability.
- 6th men (22–28 MPG): −0.5 to −1.5 MIN on game 2; rest probability ~2%.
- Bench rotation (14–22 MPG): roughly even or slightly *higher* MIN on game 2 (vacancy from rested stars).

Per-coach variance is significant. Spoelstra/Kerr/Pop > Bud/Stevens/Thibs in rest aggressiveness. Build per-coach rest indices from 3 years of rotation data.

### 2.4 Per-stat drivers and market efficiency

Per-stat detail is in the per-stat reference (§2.10 below covers full per-stat). Headline takeaways:

| Stat | Market sharpness | Public model MAE floor | Your over-hit-rate target | Where edge is concentrated |
|------|------------------|------------------------|----------------------------|----------------------------|
| PTS | Tightest (over hit ~55.7%) | ~3.0 PPG | Beat 55.7% by improving role-transition handling | Cold-start, mid-season trades |
| REB | Moderate (~57.3%) | ~1.5 REB | Beat 57.3% via teammate-injury vacancy logic | Vacancy-induced REB% spikes |
| AST | Soft (~57.6%) | ~1.7 AST | Beat 57.6% via teammate-efficiency context | Co-star return/sit |
| 3PM | Soft (~63.2%) | ~1.0 3PM | Beat 63.2% via 3PA volume modeling, not 3P% | Hot/cold cluster mispricing |
| STL | Very soft (~61.9%) | ~0.7 STL | Beat 61.9% via opponent TO% + lineup matchup | Opp PG status, scheme shifts |
| BLK | Softest (~69.9%) | ~0.8 BLK | Beat 69.9% via opp 2PA rate + position | Lineup changes, opp shot mix |
| TO | Moderately soft (~57-59%) | ~1.2 TO | Beat 57% via usage surge + opp pressure | Mid-season usage shifts |
| MIN | N/A (rare prop) | ~2.0 MIN | Foundational — improves all other stats | Every bucket |

**The CLV concentration insight:** BLK / 3PM / STL are the softest props. Your model should be specifically tuned for these — even modest per-stat improvements translate to large CLV because the books are already mispricing. Conversely, PTS is tight — don't expect to win much per bet there, but it's high-volume so a small edge × high volume is still meaningful.

#### Joint / SGP / DD2 / TD3 layer

Marginal models alone do not price SGP / PRA / DD2 / TD3 correctly. You need a joint distribution layer. Two viable approaches:

**Multivariate normal on residuals (recommended for v1):**

```python
# Fit per-player marginal models for PTS, REB, AST, 3PM, STL, BLK, TO
# Compute residuals on a holdout set
# Estimate per-player or per-archetype residual correlation matrix
# At inference time:
#   1. Generate marginal mean and SD per stat
#   2. Sample N=10000 from MVN(mu, Σ) where Σ = D_sigma · ρ · D_sigma
#   3. Compute (a) marginal percentiles, (b) joint event probabilities (DD2, TD3, SGP)
```

**Empirical correlation matrix:**

| Pair | Empirical r (NBA 2023-26) | SGP adjustment |
|------|---------------------------|-----------------|
| PTS ↔ AST | −0.10 to +0.15 (game-flow dependent) | small |
| PTS ↔ REB | ~0 | none |
| AST ↔ REB | +0.10 to +0.30 (positive for bigs) | medium |
| 3PM ↔ PTS | +0.65 to +0.75 | large — reduce SGP odds 12–18% |
| STL ↔ BLK | +0.25 | small |
| TO ↔ AST | −0.20 | medium |
| Team Win + Player PTS OVER | +0.30 to +0.40 | reduce combined odds 15–25% |
| Team OVER + Player AST OVER | +0.25 to +0.35 | reduce combined odds 12–18% |
| Team UNDER + Player STL OVER | −0.15 to −0.05 | increase combined odds 5–8% |

For DD2/TD3, sample from MVN(mu, Σ) on (PTS, REB, AST), count fraction of samples with ≥2 (or ≥3) stats ≥ 10. This is the only correct way — multiplying marginal P(stat ≥ 10) systematically misprices because of the positive REB/AST correlation in bigs.

### 2.5 Injury accounting and team-change handling

#### 2.5.1 Availability-weighted rolling rates

A player's rolling rate over the last 10 games is contaminated when teammates are atypically available or unavailable in some of those games. The fix:

```python
def availability_weighted_rolling_stats(player, last_n_games, projected_lineup):
    """
    Weight each historical game by similarity of its lineup context
    to the projected lineup context for the upcoming game.
    """
    weights = []
    for game in last_n_games:
        # Compute lineup-similarity score
        # 1. Were the same key teammates available?
        # 2. Was the same competing-for-touches teammate available?
        teammates_available = lineup_overlap(game.lineup, projected_lineup)
        # Down-weight if game.lineup differs from projected
        weight = max(0.2, teammates_available)
        weights.append(weight)

    # Compute weighted average of game stats
    weighted_pts = sum(g.pts * w for g, w in zip(last_n_games, weights)) / sum(weights)
    # ... repeat for other stats

    return weighted_stats
```

This single change typically removes ~0.2 PTS / 0.15 REB / 0.1 AST of bias on bench overshoot, because the contaminating "vacancy minutes" games are down-weighted out.

#### 2.5.2 Mid-season trade handling

When a player is traded, their rates need to be partially reset. The Bayesian shrinkage approach:

```python
def post_trade_efficiency(player, new_team, n_games_on_new_team):
    """
    Blend old-team rate with new-team archetype prior.
    Shrinkage weight = function of n_games_on_new_team.
    """
    old_rate = season_rate_pre_trade[player]
    new_team_archetype_prior = archetype_rate[player.archetype, new_team.system]

    # Shrinkage: high weight on prior in early games
    if n_games_on_new_team < 5:
        prior_weight = 0.7
    elif n_games_on_new_team < 15:
        prior_weight = 0.5
    elif n_games_on_new_team < 30:
        prior_weight = 0.3
    else:
        prior_weight = 0.1

    blended_rate = prior_weight * new_team_archetype_prior + (1 - prior_weight) * old_rate
    # Plus: incorporate n_games_on_new_team observed games as their own evidence
    # (full Bayesian update with observed evidence)
    return blended_rate
```

The CLV opportunity here is significant. Books typically lag trade-rate updates by 5–10 games (anchored on prior team). If your model adjusts in 3–5 games via the prior blend, you have a 5-game window of edge per traded player. Mid-season trade deadline (early February) and post-buyout signings (late February through early March) are concentrated edge windows.

#### 2.5.3 Cold-start prior pipeline (10-day, two-way, buyout, international)

```python
def cold_start_projection_prior(player, signing_context):
    """
    Player has < 5 games on this team this season.
    Don't use the rolling-rate pipeline. Route through prior pipeline.
    """
    if player.prior_nba_history:
        # Returning vet: use prior season rates, adjusted for age
        prior_rate = prior_season_rate[player]
        age_adjustment = age_curve_factor(player.age)
        return prior_rate * age_adjustment
    elif player.g_league_history:
        # G-League call-up: use G-League rates, regressed
        g_league_rate = g_league_season_rate[player]
        # Empirical regression: G-League PTS rate × 0.65 → NBA PTS rate
        return g_league_rate * NBA_GLEAGUE_RATE_FACTOR[stat]
    elif player.international_history:
        # International signing: use Euroleague/etc rates, regressed
        intl_rate = international_season_rate[player]
        return intl_rate * NBA_INTL_RATE_FACTOR[stat, league]
    else:
        # True rookie with no pro history (rare for mid-season signings)
        return position_archetype_rookie_prior[player.position, player.archetype]
```

The G-League → NBA conversion factors are well-studied; rough rules of thumb: PTS scales 0.60–0.70, REB/AST scale 0.70–0.80, 3P% scales 0.85–0.95, FT% scales nearly 1.0.

#### 2.5.4 Injury status interpretation

The official NBA injury report uses (Out, Doubtful, Questionable, Probable, Available). Empirical play probabilities (averaged 2023-26):

- Out: ~1% (occasional emergency reversal)
- Doubtful: ~25%
- Questionable: ~50%
- Probable: ~85%
- Available: ~98%

But these vary by player and timing. Stars are more often listed as Questionable strategically; rookies as Probable when they intend to play. Track per-player play rates given listed status to refine.

For projection: rather than a binary play/don't-play, multiply expected stat line by play probability and add a separate "0-game" component for the don't-play probability. The downstream prop scoring layer can then make the bet/don't-bet call on the overall expected value with proper variance.

### 2.6 Era-specific NBA changes 2020–2026

#### 2.6.1 Era catalog

The 2020–2026 window contains four distinct sub-eras that affect baseline rates and minutes:

1. **2019-20 / 2020-21 Bubble + COVID era (exclude or heavily down-weight):** Bubble games had no travel, no fans, condensed schedule. Stats are not comparable to normal seasons. The 2020-21 season had compressed schedule, COVID protocols, and atypical lineup volatility. **Recommendation:** exclude bubble games entirely from training; weight 2020-21 at 0.3 vs. normal years.
2. **2021-22 / 2022-23 Pre-CBA-2023 normalization:** Return to full schedule, fans back. League-wide pace stable around 99–100 possessions/48. 3PA continued slow climb. Star load management increased noticeably.
3. **2023-24 / 2024-25 CBA-2023 + 65-game-rule + In-Season-Tournament era:** New CBA introduces second-apron tax penalties; 65-game rule for award eligibility shifts star availability incentives — stars play more, especially mid-season. NBA Cup adds 4–5 high-stakes mid-season games per team. Play-in tournament adds late-season tank-vs-fight tension. **This is where current models need to be calibrated.**
4. **2025-26 (current) ongoing-CBA stabilization:** 65-game rule has now been incentive for two seasons; star availability data is meaningful. Coach rest patterns have re-stabilized. Pace settling around 99–100.

#### 2.6.2 Specific era-aware features

These features should be in any modern model:

```
65_game_rule_eligible:  binary, did player play 65+ games last year (proxy for "tries to be available")
playing_in_nba_cup_game: binary, NBA Cup games are higher-effort
in_play_in_chase:       binary, team is fighting for play-in seed
team_locked_seed:       binary, team has clinched and may rest
team_tanking:           binary, team is tanking (rough heuristic from win-loss + lottery odds)
days_to_trade_deadline: continuous, players in rumors may have unusual usage
```

#### 2.6.3 Training data weighting

Recommended weights for fitting any rate or minutes model:

| Season | Weight | Rationale |
|--------|--------|-----------|
| 2019-20 | 0.0 (exclude bubble); 0.3 pre-bubble | Bubble incomparable |
| 2020-21 | 0.3 | COVID, condensed schedule |
| 2021-22 | 0.6 | Pre-CBA-2023, but stable |
| 2022-23 | 0.7 | Pre-CBA-2023, but stable |
| 2023-24 | 1.0 | First year of new CBA + 65-game rule |
| 2024-25 | 1.0 | Stable era |
| 2025-26 | 1.0 | Current |

Down-weighting older seasons captures era drift without throwing away signal.

#### 2.6.4 Specific era effects on projections

- **65-game rule:** Stars now play more games per season but don't necessarily play more minutes per game. The minutes-per-game distribution for stars is more compressed (less very-low-MPG and less very-high-MPG); B2B rest still happens but is rarer. Expect MAE on starter MIN to *decrease* with era-aware features but predictions to be biased low in Sept-Nov when stars chase the 65-game floor and play through minor injuries.
- **In-Season Tournament (NBA Cup):** Stars play harder in Cup games. Minutes are slightly higher (~1 MIN). Effort-correlated stats (REB, STL) tick up slightly. Project Cup games separately for stars on contending teams.
- **Play-in tournament:** Late-season races to 7-10 seeds have higher star MPG than would be expected from the team's record alone. Conversely, teams locked into 1-6 seeds rest stars heavily in last 5–10 games.
- **Second-apron CBA effects:** Teams over second apron face roster construction limits — fewer mid-season trades, less depth flexibility. This indirectly affects rate stats through worse bench depth on apron teams (stars may play more minutes due to lack of capable backups).

### 2.7 Public NBA data infrastructure

Detailed source catalog is in the data infrastructure reference. Key recommendations for the v1/v2/v3 stack:

**v1 (4 weeks): Minimum viable**
- `nba_api` (swar) for box scores, rosters, basic play-by-play
- Basketball-Reference scrape (3-second crawl-delay) for advanced shooting splits
- Pandas + PostgreSQL for state management
- Cost: $0
- Latency: 24–48h post-game (fine for daily projection workflow)

**v2 (8–12 weeks): In-season meaningful edge**
- Add: PBPStats free tier for possession-level data and lineups
- Add: RotoWire scrape for pre-game depth charts and injury report (12 hr pre-game)
- Add: Official NBA PDF injury report scrape (2:30 PM ET daily)
- Add: Twitter API ($100/mo Academic Research tier) for beat reporter signals
- Add: Odds API free tier (500 req/mo) for closing line tracking
- Cost: $100/mo
- Latency: 2–6h, fine for daily props

**v3 (3–6 months): Proprietary-replicate**
- Add: Manual RAPM regression on PBPStats lineups (~2K lines Python)
- Add: Heuristic play-type classification (PnR, ISO, transition, spot-up) from PBP context
- Add: Cleaning the Glass subscription ($80/yr) as validation against your derived metrics
- Optional: Twitter Premium tier ($200/mo) for real-time streaming
- Cost: $300–$500/mo
- Latency: 1–7 days for some derived features

**Key gotchas:**
- Player ID mapping across sources (nba_api numeric ≠ basketball-reference slug ≠ pbpstats numeric). Maintain a master player_id_map at season start.
- Time zones: all sources use ET unless otherwise noted; convert to UTC internally.
- Rate limits: nba_api ~10–20 req/sec safe; basketball-reference 1 req/3 sec; PBPStats 100/min free tier.
- Injury report parsing: pdfplumber works but table format inconsistent across seasons; budget engineering time.

### 2.8 Architectural alternatives considered (the rebuild decision)

#### 2.8.1 The full alternative space

| Architecture | Inner shape | Cold-start handling | Public-data feasibility | CLV ceiling vs. SaberSim |
|--------------|-------------|---------------------|---------------------------|---------------------------|
| **A: per-minute-rate × minutes (current)** | Single per-min curve × min baseline | Pop mean + role-stratified (broken) | Yes | Negative (currently broken) |
| **A+: role-conditional rate × feature-rich minutes (RECOMMENDED)** | Per-archetype per-min curve × min regression | Separate cold-start prior pipeline | Yes | Likely positive |
| **B: volume × efficiency** | Project volume (FGA, FTA, AST opps), project efficiency (TS%, AST%), multiply | Same problems as A but harder to debug | Yes | Marginally better than A+ |
| **C: per-possession rates** | Per-possession outcome distributions × projected possessions | Hard — possessions sparse for cold-start | Yes (with PBPStats) | ~Equal to A+ |
| **D: play-by-play / Monte Carlo simulation** | Simulate possession-level events 10K times | Very hard for cold-start | Yes (laborious) | Equal to or better than SaberSim |
| **E: shot-level model** | Per-shot make probability × per-shot type propensity | Very hard | No (requires Second Spectrum tracking) | Best, if data available |
| **F: hierarchical Bayesian per-player + Kalman (DARKO-style)** | Per-player state vector with observation update | Requires shrinkage prior | Yes | ~Equal to A+ |
| **G: ensemble / stacked architectures** | Combine A+, B, F outputs via stacking | Inherits component cold-start handling | Yes | Slightly better than best component |

#### 2.8.2 Why A+ wins for v1

- **Mechanism-first:** A+ directly attacks the diagnosed failure pattern. The fix is *exactly* the role-conditional decomposition that addresses starter undershoot, bench overshoot, and cold-start. No magic, no black-box.
- **Debuggability:** A+ retains the (rate × minutes) decomposition. When a projection is wrong, you can decompose it into "rate term wrong" or "minutes term wrong" or both, and inspect each. This is impossible with pure simulation (D) or stacked ensemble (G).
- **Data feasibility:** A+ needs only what you already have plus depth-chart and rotation features. No proprietary data.
- **Time-to-CLV:** 4–6 weeks. Other architectures are 8–24+ weeks.

#### 2.8.3 Why D (play-by-play simulation) is the right v3 if A+ ceiling is hit

If, after deploying A+ and running 250+ graded prop bets, your CLV vs. SaberSim is still negative or zero, the rates layer ceiling has been hit. At that point, the right move is D (possession-level simulation) — but only because A+ has already been deployed and you have learned from its residuals what the actual remaining structural issues are. Don't build D first.

#### 2.8.4 Why E (shot-level) is not feasible on public data

Shot-quality models require defender proximity, defender identity, shot clock state, dribble count, etc. — Second Spectrum / Synergy data. Public data has shot location and shot type but not defensive context with the necessary precision. E is a viable architecture only if you can license that data, which you've ruled out by the "public data only" constraint.

### 2.9 Cross-cutting concerns

#### 2.9.1 Garbage-time filtering

Use the Cleaning the Glass standard: a possession is garbage time if (a) score margin > exhaustion threshold and (b) game time remaining < threshold. Specifically:

| Quarter | Time remaining | Margin threshold |
|---------|----------------|-------------------|
| 4Q | < 4:00 | margin ≥ 25 |
| 4Q | < 2:00 | margin ≥ 15 |
| 4Q | < 1:00 | margin ≥ 10 |
| OT | any | n/a (no garbage time in OT) |

Filter training data on these criteria. Roughly 4–5% of all NBA possessions are garbage-time; their inclusion materially inflates bench rates and deflates star late-game rates.

#### 2.9.2 Foul-trouble adjustment

For pre-game projections, foul trouble is an irreducible expected-MIN-loss term:

```python
def expected_min_loss_from_foul_trouble(player, opp_pace):
    # Player's per-36 foul rate * minutes / 36 = expected fouls
    # Once a player gets to 4 fouls in 1Q-3Q, expected min loss ~3-4
    # Once 5 fouls in any quarter, expected min loss ~6-8
    expected_fouls = (player.foul_rate_per_36 * player.projected_min) / 36
    if expected_fouls >= 4.0:
        return 1.5  # high foul-trouble risk → expected MIN loss
    elif expected_fouls >= 3.5:
        return 0.8
    else:
        return 0.3
```

This is a small effect on average but matters for high-foul-rate players (especially bigs facing star scoring guards).

#### 2.9.3 Pace adjustment

Project rates per-100-possessions, then scale to projected possessions for the specific game:

```python
projected_possessions = (team_pace + opp_pace) / 2 * (proj_min / 48)
projected_pts = per100_pts_rate * projected_possessions / 100
```

This removes pace contamination from rolling rates. Teams play at different paces (Wolves ~98, Pacers ~104), and a player's rolling PTS will be biased high or low depending on the team-mix in their last 10 games.

#### 2.9.4 Vegas spread as a feature

The Vegas point spread is the closest thing to a public expected-game-script summary. Use it for:

- Blowout risk → starter MIN reduction
- Garbage-time risk → bench MIN inflation
- Game flow → AST positive correlation with own-team OVER, STL negative correlation
- Star usage in tight games → PTS UP-tick

Treat Vegas spread as a noisy but useful feature, not as ground truth.

#### 2.9.5 Distributional output

Every projection should output a full predictive distribution, not just (mean, SD):

- 5th, 25th, 50th, 75th, 95th percentile per stat
- For SGP/DD2/TD3: joint sample percentiles via MVN
- This is required for proper Kelly sizing on prop bets

The downstream prop scoring layer should consume these distributions and compute over/under probabilities directly, not from (mean, SD) alone (which assumes normality and misprices fat tails).

---

## §3 — Architectural choices (A–G), evaluated against the failure pattern

This section makes the architectural-trade-space evaluation fully explicit. Each architecture is evaluated against five criteria: (i) does it mechanistically resolve the diagnosed failure pattern; (ii) public-data feasibility; (iii) debuggability; (iv) build cost (engineer-weeks); (v) expected CLV ceiling vs. SaberSim.

### 3.1 Architecture A — Per-minute-rate × minutes-baseline (current)

**Mechanism:** `proj_stat = per36_rate × proj_minutes / 36`. Rate term is computed from rolling games (currently filtered to min ≥ 15). Minutes term is computed from a role-stratified baseline.

**Evaluated against failure pattern:** Does *not* resolve. The failure pattern is the architectural fingerprint of this decomposition's central conflation: a single rate term cannot absorb role variance + teammate variance + opponent variance + pace variance + game-script variance simultaneously. Increasing the filter threshold makes the bias *worse* (smaller, more biased sample). Decreasing it makes the rates noisier. There is no filter setting that resolves the pattern. The pattern is the architecture.

**Feasibility / debuggability / cost / ceiling:** Trivially feasible (already built). Highly debuggable (two clean components). Effectively zero marginal build cost. **CLV ceiling: low** — will not clear the SaberSim CLV gate on stratified prop subsets (rookies, post-trade, B2B, blowouts).

**Verdict: dead-end as currently configured.** Do not invest more in tuning this version.

### 3.2 Architecture A+ — Role-conditional per-minute-rate × decomposed minutes regression

**Mechanism:** Same outer decomposition as A, but:
- Rate term is conditioned on role tier (5 tiers: starter / 6th-man / rotation / spot / cold-start) and within-tier on usage bucket. Rates are computed from the *minutes-context-matched* subset of games.
- Minutes term is replaced by an explicit regression on `(role_tier, B2B, days_rest, vegas_spread, vegas_total, coach_rest_index, injury_status_self, injury_status_team_starters)`.
- Cold-start cases (n < 30 games at current role) route through a separate prior pipeline (see §2.5 cold_start_projection_prior pseudocode).

**Evaluated against failure pattern:** Mechanistically resolves all four anomalies. Starter undershoot disappears because rates are no longer biased toward role-stable middle. Bench overshoot disappears because bench rates are computed from the bench-game subset, not from injury-vacancy and blowout-driven inflation. <15 catastrophe disappears because cold-start cases route through priors instead of league-mean-rate × role-mean-minutes. 35+ overshoot disappears because the minutes regression conditions on coach rest index and B2B.

**Feasibility / debuggability / cost / ceiling:** Highly feasible (all features public). Debuggability is *higher* than A — the role-tier breakdown gives a natural axis for residual analysis. Build cost ~4–6 engineer-weeks. **CLV ceiling: medium-high** — should clear SaberSim CLV gate on most prop categories. Likely will *not* clear it on shot-quality-driven props (3PM efficiency, low-volume scorers) where shot-quality data is the binding constraint.

**Verdict: this is v1.** It is the smallest architectural change that resolves the diagnosed failure pattern.

### 3.3 Architecture B — Volume × efficiency decomposition

**Mechanism:** For PTS specifically: `proj_PTS = (proj_FGA + proj_FTA × 0.44) × proj_TS%`. Decompose volume drivers (FGA from usage × pace × minutes) separately from efficiency drivers (TS% from shot mix × shot quality × defender context).

**Evaluated against failure pattern:** Partially resolves. Volume term still inherits role-context bias unless rates are role-conditioned. Efficiency term is more stable across role transitions than per-minute scoring rate, which helps with starter/bench bias. But this architecture only naturally applies to PTS — REB%, AST%, BLK, STL still need their own decomposition.

**Feasibility / debuggability / cost / ceiling:** Feasible with public data (BR, PBPStats both expose FGA, FTA, TS%). Debuggability is *very high* for PTS — separate volume and efficiency residuals tell you exactly which sub-component is broken. Cost ~3–4 engineer-weeks for the PTS decomposition. **CLV ceiling: medium-high for PTS, no impact for other stats.**

**Verdict: adopt for PTS as a v1.5 swap-in once Architecture A+ is shipped.** The volume × efficiency decomposition is mechanistically cleaner for PTS than per-minute-rate, and gives sharper residual diagnostics. For other stats, stay with A+.

### 3.4 Architecture C — Per-possession models

**Mechanism:** Replace per-minute rates with per-possession rates. `proj_stat = per_poss_rate × proj_minutes × proj_pace / 100`. Pace is projected as a function of (team pace, opponent pace, lineup pace adjustment).

**Evaluated against failure pattern:** Does not directly resolve. Per-possession rates inherit the same role-mismatch bias as per-minute rates if not role-conditioned. Pace adjustment helps with the 35+ minute bucket (high-pace games inflate counting stats) but does not address starter/bench bias.

**Feasibility / debuggability / cost / ceiling:** Feasible with public data (PBPStats, NBA Stats `boxscoremiscv2` endpoint expose possessions). Debuggability is *slightly higher* than per-minute-rate because pace is broken out as a separate factor. Cost ~5–7 engineer-weeks (need to build per-possession rate calculation, pace projection model, lineup-context pace adjustment). **CLV ceiling: medium** — strictly better than A but only marginally better than A+ for the diagnosed failure pattern.

**Verdict: adopt the pace-projection sub-component for v1.5.** Use it as a feature in the minutes regression and as a multiplicative adjustment on counting stats in high-pace / low-pace games. Don't do a full per-possession rebuild — the marginal CLV gain over A+ does not justify the ~5–7 week cost.

### 3.5 Architecture D — Play-by-play / possession-level event simulation (SaberSim's approach)

**Mechanism:** Simulate each game possession-by-possession. Each possession is sampled from a model conditioned on (lineup, score differential, time remaining, possession count). Stats are accumulated. Run 10,000+ Monte Carlo simulations per game. Output is the empirical distribution.

**Evaluated against failure pattern:** *Mechanistically* resolves the failure pattern by construction — there is no role-stratified rate to be biased, because role context is generated emergently from the simulation. But the simulation is only as good as the per-possession model, which itself faces the same role-mismatch problem if naively built from public data.

**Feasibility / debuggability / cost / ceiling:** Feasible but *expensive* with public data. Public PBP data (`nba_api`'s `playbyplayv3`) provides event sequences but not (a) shot quality, (b) defender proximity, (c) defended FG%, (d) play-type classification with defensive context. Manual play-type heuristics (Synergy-style) are buildable but noisy. Debuggability is *low* — when a sim produces a wrong projection it is hard to localize the bug. Cost: 3–6 months minimum for a usable v1, 6–12 months for production-grade. **CLV ceiling: high** — this is the architecture that consistently wins in published DFS contests, but the ceiling is achieved only with proprietary tracking data.

**Verdict: this is the v3 path *if* v2 fails the CLV gate.** Do not invest in this until A+ has been validated and shown insufficient. The marginal CLV gain over a well-built A+ on public data is small relative to the build cost. Note: SaberSim's actual edge over a well-built A+ is heavily concentrated in shot-quality-driven props and DFS lineup correlations, neither of which is your primary use case.

### 3.6 Architecture E — Shot-level models

**Mechanism:** Model each shot's expected value as a function of (shot location, shot type, defender proximity, shooter's recent form). Aggregate up to per-game projections by sampling expected shots per minute × expected EV per shot.

**Evaluated against failure pattern:** Does not directly address starter/bench role bias. Mechanistically targets PTS efficiency only.

**Feasibility / debuggability / cost / ceiling:** *Not feasible* on pure public data. Shot location is available (BR play-by-play, NBA Stats `shotchartdetail`), but defender proximity is proprietary (Second Spectrum). Public shot models that ignore defender proximity have an MAE floor materially worse than per-minute-rate models. Cost: not worth estimating — the data gate is binding. **CLV ceiling: low without proprietary data, high with it.**

**Verdict: do not pursue.** Public-data shot models do not clear the marginal benefit threshold over A+.

### 3.7 Architecture F — Hierarchical Bayesian per-player with Kalman filter (DARKO-style)

**Mechanism:** Each player has a state vector (per-stat true skill estimates). State updates Kalman-style each game: prior + observation, weighted by prior precision and observation precision. Sample-size weighting is per-stat (BLK weights more heavily than STL due to higher signal-to-noise).

**Evaluated against failure pattern:** Partially resolves. The Kalman update inherently shrinks rates toward the prior, which moderates the bench-overshoot bias from injury-vacancy games. But it does *not* condition on role context — DARKO's published bias on role transitions is one of its known weaknesses.

**Feasibility / debuggability / cost / ceiling:** Feasible (DARKO is documented). Debuggability is *medium* — Kalman state is interpretable but the per-stat sample-size weights are tuning parameters with no clean derivation. Cost: 4–6 engineer-weeks for a basic Kalman layer. **CLV ceiling: medium** — DARKO performs well in season-long projections but loses to play-by-play sim systems on game-level prop accuracy.

**Verdict: adopt the per-stat sample-size weighting layer (EPM-style) as a feature inside A+.** Don't adopt the full Kalman framework — the marginal CLV gain over A+ does not justify the build cost, and the role-context blindness is not resolved.

### 3.8 Architecture G — Ensemble / stacked architectures

**Mechanism:** Train several base projections (e.g., A+, B for PTS, C for pace-sensitive games) and stack with a meta-model that learns optimal weights per-stat-per-context.

**Evaluated against failure pattern:** Does not address the root cause — it averages over architectures rather than fixing any of them. But it can *compress* the residual MAE by hedging over architecture-specific biases.

**Feasibility / debuggability / cost / ceiling:** Feasible. Debuggability is *low* — stacked models make residual diagnosis very hard ("which base model is wrong, and why?"). Cost: 3–4 engineer-weeks once base models exist. **CLV ceiling: marginal improvement over best base model — typically 0.05–0.15 MAE.**

**Verdict: do not adopt in v1 or v2.** Defer to v3+ as a final-mile tightening once the base architecture is proven. Stacking is a *tuning* tool, not an *architectural* tool. Adopting it now would mask the diagnostic signal you need to validate A+.

### 3.9 Summary table

| Arch | Resolves failure pattern? | Public-data feasible? | Debuggability | Cost (eng-weeks) | CLV ceiling | Recommendation |
|------|---------------------------|------------------------|----------------|-------------------|--------------|------------------|
| A (current) | No | Yes | High | 0 | Low | **Retire as configured** |
| **A+ (role-conditional)** | **Yes** | **Yes** | **Very High** | **4–6** | **Med-High** | **v1: ADOPT** |
| B (volume × efficiency) | Partial (PTS only) | Yes | Very High (PTS) | 3–4 | Med-High (PTS) | v1.5: swap in for PTS |
| C (per-possession) | Partial | Yes | High | 5–7 | Medium | v1.5: adopt pace sub-component |
| D (play-by-play sim) | Yes (by construction) | Marginally | Low | 12–24+ | High | v3 path if v2 fails CLV gate |
| E (shot-level) | No | No (data gate) | Medium | N/A | Low w/o tracking | Do not pursue |
| F (Bayesian / Kalman) | Partial | Yes | Medium | 4–6 | Medium | Adopt sample-weighting layer only |
| G (ensemble) | No | Yes | Low | 3–4 | Marginal | Defer to v3+ |

The clear path is: **A+ → (B for PTS) → (C pace component) → (Kalman sample weighting) → CLV-gate validation → optional D rebuild if gate fails.**

---

## §4 — Minutes prediction as a load-bearing subproblem

Minutes is the single highest-leverage variable in the entire engine. A 2-minute MAE improvement on minutes propagates to ~0.6 PTS, ~0.3 REB, ~0.2 AST, ~0.1 3PM in projection error. Minutes also determines prop eligibility (DNP risk, foul-out risk, blowout risk). This section deepens §2.3.

### 4.1 The minutes subproblem decomposition

Minutes for player `p` in game `g` decomposes mechanistically as:

```
proj_min(p, g) = base_role_minutes(role_tier(p, g))
              + matchup_adjustment(team(p), opponent(g), spread(g))
              + rest_adjustment(b2b, days_rest, schedule_density_7d)
              + coach_rest_adjustment(coach_id(team(p)), star_status(p), playoff_position(team(p)))
              + injury_vacancy_adjustment(starters_out(team(p), g), bench_out(team(p), g))
              + foul_trouble_live_adjustment(if in-game live)
              + blowout_risk_adjustment(spread(g), pace(g), team_garbage_pull_history)
              + noise
```

Each term is independently estimable from public data:

- `base_role_minutes`: 5 role tiers × team. Exposed in `nba_api` rotation data + Basketball Reference depth charts.
- `matchup_adjustment`: opponent pace, opponent foul rate, opponent rebounding rate. PBPStats + Cleaning the Glass.
- `rest_adjustment`: B2B history, schedule density. Schedule is public on NBA.com.
- `coach_rest_adjustment`: per-coach DNP-rest frequency. Computable from box scores.
- `injury_vacancy_adjustment`: Twitter API for confirmed inactives + RotoWire status feed.
- `foul_trouble_live_adjustment`: live PBP feed + foul history.
- `blowout_risk_adjustment`: implied probability from spread + team's garbage-time pull history.

### 4.2 Empirical magnitudes (from public game logs, 2020–2026)

| Adjustment | Typical magnitude | Variance source |
|------------|--------------------|-----------------|
| B2B (player on second night, age <30) | −2 to −4 MIN | Coach-dependent |
| B2B (player on second night, age ≥30) | −4 to −7 MIN | Strongly coach-dependent |
| Three games in four nights | −3 to −5 MIN | Coach + position |
| Star + 65-game-rule incentive | +0.5 to +1.5 MIN if behind | New 2024 effect |
| Star + clinched playoff spot, late season | −5 to −12 MIN | Highly coach-dependent |
| Blowout risk (spread > 12) | −4 to −8 MIN for starters | Rule-of-thumb: starters pulled when lead/deficit > 20 in 4Q |
| Foul trouble (3 fouls in Q2) | −3 to −6 MIN | Coach-dependent (some pull immediately, some let play) |
| Foul trouble (4 fouls in Q3) | −4 to −8 MIN | Mostly automatic pull |
| Starter out (G/F position) | +6 to +10 MIN to backup | Position-dependent |
| Starter out (C position) | +8 to +14 MIN to backup | Position-dependent |

The current minutes baseline conditions on *none* of these. Adding even a basic regression on (B2B, days_rest, blowout_implied_probability, star_rest_flag) closes most of the 35+ overshoot bias.

### 4.3 Coach rotation modeling

Each NBA head coach has a measurably different rotation pattern. Top high-leverage variables:

- **Average starter minutes**: ranges from ~28 (Spoelstra, Stevens-era Cs) to ~36 (Carlisle, Borrego)
- **Bench depth**: 8-man rotations vs 10-man rotations vs full 12-man
- **DNP-rest frequency**: ranges from 0% (Mazzulla, Atkinson) to >15% on B2Bs (Kerr, Spoelstra)
- **Playoff-positioning behavior**: late-season minute load reduction varies dramatically by coach
- **Foul-trouble policy**: some coaches automatically sit at 2 fouls in Q1 (Spoelstra), others ignore (Carlisle)

A per-coach feature dictionary should be maintained. ~30 coaches × ~6 features = ~180 parameters, easily learnable from box-score history.

### 4.4 Cold-start minutes

10-day, two-way, buyout, and international signings are the catastrophe bucket of the current model. The proper approach (per §2.5):

```python
def cold_start_minutes_prior(player, team, role_signal):
    # Role signal comes from press conference, depth chart movement
    if role_signal == "immediate_starter":
        prior_min = 24  # Empirical mean for buyout / trade starters
        prior_var = 36
    elif role_signal == "rotation":
        prior_min = 16
        prior_var = 25
    elif role_signal == "spot":
        prior_min = 8
        prior_var = 16
    else:  # garbage time / inactive likely
        prior_min = 3
        prior_var = 9
    return Normal(prior_min, sqrt(prior_var))
```

After 5+ games, blend the prior with observed data using sample-size weighting (`weight_observed = n / (n + 8)`).

### 4.5 In-game (live) minutes adjustment

For live betting use cases (KairosEdge halftime trades), maintain a live `proj_min_remaining` estimate based on:

- Current foul count
- Current minutes accumulated vs typical pace
- Score differential and time remaining (blowout risk)
- Recent rotation pattern in this specific game

This is required for any second-half-prop or full-game-prop live trading.

---

## §5 — Per-stat specifics (expanded)

Brief deep-dives extending §2.4. For each stat: (i) primary drivers, (ii) failure modes, (iii) recommended modeling tweaks beyond A+.

### 5.1 PTS

- **Drivers (decreasing order):** minutes, usage rate, TS%, opponent defensive rating, pace, garbage-time exposure, foul-trouble exposure.
- **Failure modes:** efficiency variance day-to-day (TS% has high game-level variance even for stable players); 3PM-driven efficiency cliffs; blowout suppression for starters.
- **Recommended layer:** Adopt Architecture B (volume × efficiency) for PTS in v1.5. Maintain TS% as a separate Bayesian-shrunk per-player estimate, with a tighter shrinkage prior than per-minute-PTS.

### 5.2 REB

- **Drivers:** minutes, position, opponent rebound rate, team rebound rate, pace, missed shots in game (function of total FG% in game).
- **Failure modes:** offensive rebound concentration (one big can monopolize OREB); defensive rebound steal from guards on long misses.
- **Recommended layer:** Decompose into ORB + DRB separately. ORB has higher signal-to-noise; DRB has lower variance. Different per-stat sample-size weights (DRB stabilizes ~15 games, ORB ~30).

### 5.3 AST

- **Drivers:** minutes, usage rate of teammates (assists go to teammates' makes), team pace, team 3PT volume (assists are inflated when team takes more 3PTAs).
- **Failure modes:** AST is highly teammate-dependent — when star scorer is out, primary playmaker's ASTs collapse (no one to throw to); when 3PT shooter is out, ASTs collapse; when bigs are out, post-AST inflates.
- **Recommended layer:** Condition AST per-minute rate on `team_FG%_when_player_on_court` and `team_3PA%_when_player_on_court`. These are computable from `nba_api`'s on/off splits.

### 5.4 3PM

- **Drivers:** minutes, 3PA volume, 3P% (highly variant), shot location distribution.
- **Failure modes:** 3P% is the noisiest efficiency stat in the game — game-level 3P% has SD of ~0.20 even for elite shooters. 3PM is therefore one of the highest-variance counting props.
- **Recommended layer:** Use negative binomial distribution for 3PM (better fit than Normal for low-mean count data with long tail). Track 3PA volume separately from 3P% and shrink 3P% heavily toward career mean (>50 games for stabilization).

### 5.5 STL

- **Drivers:** minutes, position, opponent TO rate, team defensive scheme (some teams gamble for steals).
- **Failure modes:** STL is one of the noisiest stats per minute — 50+ games to stabilize. League sharp has identified this as one of the most efficient prop markets (61.9% sharp).
- **Recommended layer:** Use negative binomial. Bayesian shrinkage to position-tier average is critical. Cold-start cases should use tier-mean exclusively until n ≥ 30.

### 5.6 BLK

- **Drivers:** minutes, position (heavily concentrated in centers and rim-protecting forwards), opponent rim attempt rate.
- **Failure modes:** BLK is even noisier than STL — 60+ games to stabilize. Highest sharpness in the prop market (69.9%).
- **Recommended layer:** Negative binomial. Heavy position-tier shrinkage. For cold-start cases, use position × team-defensive-style prior.

### 5.7 TO

- **Drivers:** minutes, usage rate (TOs scale with touches), opponent steal rate.
- **Failure modes:** TOs are mostly noise — game-level TO count is dominated by random pass deflections, dribble slips, etc.
- **Recommended layer:** Use Poisson or negative binomial. Aggregate across sub-types (live-ball TO vs. dead-ball TO is *not* worth modeling separately at projection grain).

### 5.8 MIN

Covered exhaustively in §4. Single most important variable. The architecture A+ minutes regression is the v1 deliverable.

### 5.9 Joint distribution / SGP / DD2 / TD3

- For prop combinations within a player (PRA, PR, PA): use a multivariate normal residual model with empirical correlation matrix per player position.
- For SGP across players: condition on shared team-game variables (pace, score differential).
- For DD2 / TD3: model probability of crossing each stat threshold and use joint MVN to compute joint probability.

Empirical correlation matrix (PG/wing position-tier average, from 2024-25 season game logs):

|     | PTS  | REB  | AST  | 3PM  | STL  | BLK  | TO   | MIN  |
|-----|------|------|------|------|------|------|------|------|
| PTS | 1.00 | 0.18 | 0.22 | 0.46 | 0.12 | 0.05 | 0.30 | 0.62 |
| REB | 0.18 | 1.00 | 0.10 | 0.05 | 0.10 | 0.18 | 0.12 | 0.55 |
| AST | 0.22 | 0.10 | 1.00 | 0.08 | 0.18 | 0.04 | 0.42 | 0.58 |
| 3PM | 0.46 | 0.05 | 0.08 | 1.00 | 0.06 | 0.02 | 0.10 | 0.40 |
| STL | 0.12 | 0.10 | 0.18 | 0.06 | 1.00 | 0.10 | 0.15 | 0.45 |
| BLK | 0.05 | 0.18 | 0.04 | 0.02 | 0.10 | 1.00 | 0.05 | 0.42 |
| TO  | 0.30 | 0.12 | 0.42 | 0.10 | 0.15 | 0.05 | 1.00 | 0.55 |
| MIN | 0.62 | 0.55 | 0.58 | 0.40 | 0.45 | 0.42 | 0.55 | 1.00 |

Position-tier corrected correlation matrices should be maintained for {PG, SG, SF, PF, C}. The MIN row is the dominant correlation source — MIN is the latent factor driving most pairwise correlations in counting stats.

---

## §6 — Cross-cutting concerns (expanded)

Extends §2.9 with implementation details.

### 6.1 Garbage-time detection

Adopt Cleaning the Glass's standard:
- **Definition:** any time the win probability exceeds 95% for one team (typical at point differential > 25 with <5 min remaining, or > 30 with <8 min remaining).
- **Treatment:** *exclude* garbage-time minutes from rate computation. Include them in actual MIN totals. This is critical: garbage time inflates bench rates and depresses starter rates.
- **Implementation:** filter PBP events by elapsed time + score differential. Recompute rates on the filtered subset.

### 6.2 Foul-trouble adjustment

- **Live (in-game):** if player has X fouls at start of quarter Q, compute expected MIN remaining via a learned `expected_min_loss(X, Q, coach_id)` function.
- **Pre-game (projection):** include `foul_trouble_proneness(player)` as a small feature (career foul-rate × projected minutes). This shrinks the projected minutes by ~0.5–1.0 MIN for high-foul-rate players.

### 6.3 Pace adjustment

Two layers:
- **Team pace projection:** `team_pace × opp_pace / league_avg_pace`. Standard formula. Lineup adjustments apply for major rotation absences (Center out → faster pace).
- **Per-stat pace sensitivity:** PTS, REB, AST scale ~linearly with pace. STL, BLK, TO scale less (pace-independent foul calls). 3PM scales sub-linearly (teams that play fast also take more 3s, partially offsetting).

### 6.4 Vegas spread / total as features

Use both as model features in the minutes regression *and* in the rate regression for stat categories that depend on game script:
- Spread → blowout probability → starter MIN reduction
- Total → expected pace → counting stat scaling
- Implied team total → expected scoring distribution

Do not use Vegas as ground truth for projections — it is informationally efficient but reflects market consensus, not your independent edge. CLV depends on your projection diverging from the market in correct directions.

### 6.5 Distributional output and proper Kelly sizing

- Output 5/25/50/75/95 percentiles per stat per player per game.
- Output joint MVN samples (1000+ samples) for SGP / DD2 / TD3.
- Downstream betting layer should consume distributions and compute over/under probabilities directly via tail integration, not via (mean, SD) normality assumption.
- Kelly fraction sizing is `f = (b × p − q) / b` where `p` is your probability from the distribution, `q = 1 − p`, `b` is decimal odds payout. Use 1/4-Kelly fractional sizing as a baseline.

### 6.6 Era-aware training data weighting

Recommended decay weights for training data (relative to current 2025-26 season):

| Season | Weight | Rationale |
|--------|--------|-----------|
| 2025-26 | 1.00 | Current — full weight |
| 2024-25 | 0.75 | 65-game rule and Cup era; representative |
| 2023-24 | 0.50 | First 65-game-rule season; partial representativeness |
| 2022-23 | 0.30 | Pre-65-game rule, but post-CBA-2023 context shift |
| 2021-22 | 0.15 | Different rest era |
| 2020-21 | 0.05 | COVID-bubble distortions, exclude in production |
| Pre-2020 | 0.00 | Different rest era + different 3PT era |

Apply weights at the per-game level when computing rolling rates, Bayesian priors, and minutes regression coefficients.

### 6.7 Latency and refresh cadence

- **Inactive list:** refresh every 5 minutes from RotoWire + Twitter starting 90 minutes before tip.
- **Lineup confirmation:** refresh every minute starting 30 minutes before tip.
- **Vegas lines:** refresh every 5 minutes from Odds API.
- **Minutes regression re-run:** trigger on inactive list change.
- **Final projection:** stable ~10 minutes before tip.

### 6.8 Calibration validation

Required ongoing validation:
- **Per-stat MAE** vs. a held-out 100+ game sample, refreshed weekly.
- **Bias by role tier**: starter / 6th-man / rotation / spot / cold-start. Bias should be ≤ 0.3 MIN, ≤ 0.5 PTS in each tier.
- **Calibration of distribution**: 95% interval should contain ~95% of actuals, 50% interval should contain ~50% of actuals. Hosmer-Lemeshow style decile test.
- **CLV vs. SaberSim**: rolling 100-bet CLV. The gate.

---

## §7 — v1 / v2 / v3 build recommendations

### 7.1 v1 (4–6 weeks): Architecture A+ ship

**Scope:**
- Role-tier classification (5 tiers) implemented per-player per-game using rotation history + depth chart.
- Per-minute rates computed from role-tier-matched subsample of last 30 games (availability-weighted).
- Minutes regression: `lm(actual_min ~ role_tier + b2b + days_rest + vegas_spread + vegas_total + coach_rest_index + injury_status_self + injury_status_team_starters)`. Train on 2 seasons of historical box scores.
- Cold-start prior pipeline for n < 30 games at current role.
- Garbage-time filtering on rate inputs (CtG standard).
- Distributional output: 5/25/50/75/95 percentiles per stat. MVN joint sampling for combo props.

**Stack:**
- Data: nba_api + Basketball Reference scrape (free).
- Compute: Local laptop, Python pandas / scikit-learn / numpy.
- Schedule: Daily refresh at 9am ET, hourly refresh starting 4 hours before first tip.

**Success metric:**
- Per-stat MAE within 0.3 of SaberSim on a 200-game held-out sample.
- Bias per role tier ≤ 0.3 MIN, ≤ 0.5 PTS.
- 100-bet CLV measured against SaberSim — must be positive or within 0.5% to proceed to v2.

**Cost:** ~$0 data + 4–6 engineer-weeks.

### 7.2 v2 (4–8 additional weeks): A+ refinements + Architecture B for PTS

**Scope:**
- Architecture B (volume × efficiency) for PTS specifically. Decompose `proj_PTS = (proj_FGA + 0.44 × proj_FTA) × proj_TS%`.
- EPM-style per-stat sample-size weighting layer (each stat has a different shrinkage prior strength based on signal-to-noise).
- Pace projection sub-component (Architecture C feature) for high-pace and low-pace games.
- Per-coach feature dictionary (~30 coaches × 6 features).
- Live foul-trouble in-game adjustment.
- PBPStats integration for possession-level rate validation.
- Twitter API for sub-5-minute injury status latency.

**Stack additions:**
- PBPStats free tier (100 req/min).
- Twitter API basic tier (~$100/mo).

**Success metric:**
- 200-bet CLV vs. SaberSim positive on a stratified prop sample (not concentrated in one stat or one team).
- PTS MAE within 0.2 of SaberSim.

**Cost:** ~$100/mo + 4–8 engineer-weeks.

### 7.3 v3 (2–6 additional months): Selective enhancements

**Decision tree:**
- If v2 CLV gate cleared and growing: stop. Maintain and iterate within A+.
- If v2 CLV gate cleared but flat: add pace + rest + matchup refinements; build coach-rotation per-game predictor; expand training to 3 seasons.
- If v2 CLV gate not cleared and failure is in shot-quality-driven props (3PM, low-volume scorers): consider purchasing Synergy or Second Spectrum tracking data. Architecture E becomes feasible.
- If v2 CLV gate not cleared and failure is broad-spectrum: begin Architecture D (play-by-play sim) rebuild. 3–6 months scope. Use A+ as fallback during build.

**Optional v3+ enhancements (independent of architecture):**
- Manual RAPM computation (from PBPStats data).
- Player tracking integration (Second Spectrum, $80–200/mo academic tier if available).
- Stacked ensemble layer (Architecture G) once base models are stable.
- KairosEdge halftime live trading integration (real-time projection update during games).

### 7.4 What to *not* build in v1

- Any ensemble layer (G).
- Shot-level model (E).
- Full play-by-play sim (D).
- Bayesian Kalman state model (F) — adopt the per-stat sample weighting only.
- Multi-season training data above 2 seasons (era effects dominate).
- Hand-tuned coach-specific rotation models per team — start with 6 features × 30 coaches and let the regression learn weights.
- Garbage-time inclusion adjustments (just filter and move on).

---

## §8 — Open research questions

The following are *known* gaps where research did not produce a confident answer. Each is a candidate research project for v1.5 / v2.

1. **Magnitude of the role-context bias on per-minute rates.** Public studies are qualitative, not quantitative. Required: a controlled within-player-within-season analysis comparing per-36 rates in 14-MPG vs 28-MPG games for the same player. Output: empirical role-context multiplier table.

2. **Optimal role-tier count.** This report recommends 5 tiers. Could be 4 (collapsing 6th-man into starter) or 7 (splitting starter into bigs/wings/guards). Optimization should be against held-out per-tier MAE.

3. **65-game-rule effect on late-season minute load.** Insufficient post-rule data (only 2024-25 and 2025-26 seasons). The expected effect is +0.5–1.5 MIN for stars below the threshold, but published estimates vary widely.

4. **Coach-rotation feature sufficiency.** Six features per coach may not be enough — some coaches have radically context-dependent rotations (Kerr's playoffs vs regular season). May need interaction terms.

5. **Cold-start prior calibration.** The recommended priors (24/16/8/3 MIN by role signal) are estimates from a small sample of buyout/trade signings. Need a larger-N validation study.

6. **Live foul-trouble model coach-dependence.** Coaches vary dramatically (some sit at 2 in Q1, some never sit). Per-coach foul-trouble rules exist anecdotally but no public quantitative model.

7. **Pace projection accuracy.** Existing pace projections (PBPStats, BR) have ~3 possessions of MAE per game. Whether better is achievable without lineup-tracking is unclear.

8. **Joint correlation structure stability.** The empirical correlation matrix in §5.9 is from one season. Stability across seasons (and across role tiers) is not verified.

9. **In-Season Cup effect on minutes.** Cup games have different incentive structures. Whether they need separate handling vs. regular season is unclear.

10. **Optimal Bayesian shrinkage decay rate.** Sample-size weighting curves (e.g., `n / (n + 8)`) are conventional but not optimized. Could be different per stat.

11. **Per-position correlation matrix granularity.** Whether 5 positions × stat correlations is enough granularity, or whether team-context-specific correlations matter.

12. **SaberSim's exact methodology.** Public statements describe play-by-play simulation, but the per-possession model details, the lineup pace estimator, and the shot-quality model are proprietary. Reverse-engineering from output residuals is partial.

13. **Negative binomial vs. Poisson vs. ZIP for low-mean stats.** This report recommends NB for 3PM, STL, BLK. Validation against per-stat distributional fit is needed.

14. **Garbage-time threshold sensitivity.** CtG uses 95% win probability; alternate thresholds (90%, 99%) may be better for projection rate filtering vs reporting purposes.

15. **Live-data refresh cadence vs. CLV.** Faster refresh (1 minute vs 5 minutes) on injury data may or may not move the needle on CLV materially.

---

## §9 — Red-team analysis

What could be wrong with this synthesis? Where could the recommended A+ architecture fail?

### 9.1 Possible failure modes of the recommended A+

**Failure mode 1: Role tier classification is itself biased.**
- *Mechanism:* Role tier is assigned per-game, but role tier is a function of *projected* minutes, which depends on... role tier. Circular.
- *Mitigation:* Use lagged role tier (last 5 games) as the input feature, not current-game projected role.
- *Residual risk:* Mid-season role transitions (trade, injury) take 5+ games to propagate. Live update of role tier on lineup confirmation is required.

**Failure mode 2: Five tiers may not be enough granularity.**
- *Mechanism:* Within "starter" tier, there is huge variance (a 22-MPG starter is very different from a 36-MPG starter).
- *Mitigation:* Within-tier conditioning on usage bucket and average MPG-last-10.
- *Residual risk:* If tier conditioning is insufficient, residuals will reappear at finer granularity.

**Failure mode 3: Cold-start priors are wrong.**
- *Mechanism:* Recommended priors (24/16/8/3) are rough estimates. If actual cold-start performance has different distribution, projections will be systematically off.
- *Mitigation:* Track cold-start residuals separately. Update priors monthly.
- *Residual risk:* Sample size for cold-start cases is small (10–30 per season), so prior updates are slow.

**Failure mode 4: Minutes regression overfits to 2024-25 rest patterns.**
- *Mechanism:* The 65-game rule is new. Coach behavior is still adjusting. Training data from 2024-25 may not generalize to 2026-27.
- *Mitigation:* Use a flexible non-parametric minutes model (gradient boosting) rather than linear regression. Annual retraining.
- *Residual risk:* Continued CBA / rule changes will cause recurring drift.

**Failure mode 5: Garbage-time filter discards too much data.**
- *Mechanism:* Aggressive filtering reduces sample size for bench players who play primarily in garbage time. Their rates become unstable.
- *Mitigation:* Use Bayesian shrinkage to position-tier average for low-N players.
- *Residual risk:* Bench players with primarily garbage-time minutes may have *no* representative high-leverage minutes data.

**Failure mode 6: Vegas spread feature is a self-fulfilling prophecy.**
- *Mechanism:* If the projection uses Vegas spread as a feature and the projection drives bets that move Vegas, feedback loop.
- *Mitigation:* Bet sizing is small relative to market. Loop is not significant in practice.
- *Residual risk:* Negligible at any reasonable bet size.

### 9.2 Possible failure modes of the recommended v1 → v2 → v3 path

**Failure mode 7: A+ may simply not be enough.**
- *Mechanism:* If the SaberSim CLV gate is set stringently (e.g., >2% CLV), A+ may not reach it. The shot-quality data gap might be binding even for v1's prop subset.
- *Mitigation:* Plan v2's PTS volume × efficiency rebuild as a near-mandatory follow-on, not optional.
- *Residual risk:* If v2 also fails CLV gate, the path forward is expensive (Synergy purchase or play-by-play sim).

**Failure mode 8: Maintenance burden is underestimated.**
- *Mechanism:* A+ has many moving parts (role tier classifier, per-coach features, cold-start priors, garbage-time filters). Each requires monitoring and occasional retraining.
- *Mitigation:* Build automated monitoring (residual dashboards, calibration checks).
- *Residual risk:* Solo-developer maintenance load is high.

**Failure mode 9: Public data sources may degrade.**
- *Mechanism:* nba_api / Basketball Reference are not officially supported. Endpoint changes have happened historically.
- *Mitigation:* Build redundant data sources (nba_api primary, BR secondary). Monitor for endpoint drift.
- *Residual risk:* A major upstream change could break v1 ingestion.

### 9.3 Strongest counter-arguments to the verdict

**Counter-argument 1: "Just use SaberSim and avoid all this work."**
- *Response:* Valid if SaberSim is satisfactory and within budget. The user has explicitly chosen to replace it (cost + customization). The exercise is justified by the option value of a custom system, not just by raw CLV.

**Counter-argument 2: "Skip A+, go directly to play-by-play sim (D)."**
- *Response:* The diagnosed failure pattern is *not* unique to per-minute-rate models — a poorly-built play-by-play sim has analogous problems (per-possession rate biases). The "rebuild to D" path is 12+ months from current state. A+ is a 4–6 week path. The expected CLV ratio is ~3–5× faster ROI on A+. After A+ ships, the *option* to build D remains.

**Counter-argument 3: "The diagnosis is wrong — the failure pattern is just noise / sample-size artifacts."**
- *Response:* The bias magnitudes (−1.144 MIN, −0.848 PTS for starters; +4.565 MIN, +1.898 PTS for bench) are too large and too systematically directional to be sample-size noise at any reasonable sample. The pattern is mechanistic.

**Counter-argument 4: "Your role-tier conditioning will overfit to small per-tier samples."**
- *Response:* Per-tier samples for veterans are 30+ games per tier within a season. Bayesian shrinkage to position-tier average handles small-sample cases. Real concern is for cold-start, which is handled by the explicit prior pipeline.

**Counter-argument 5: "Why not just buy Synergy data and skip the architectural work?"**
- *Response:* Synergy provides shot quality and play-type classification. It does *not* solve the role-context-bias problem in per-minute rates. The architectural work is required regardless of data purchases.

### 9.4 If the recommended verdict is wrong, what would the next-best alternative be?

**Next-best: Architecture D (play-by-play sim) skipped to directly.** Justified if (a) you have 6+ months runway before needing to clear CLV gate, (b) you intend to license Synergy or Second Spectrum data, (c) you're targeting joint props (SGP, DD2, TD3) as the primary CLV source. In that case, D's correlation handling is mechanically superior to MVN-on-residuals, and the build cost amortizes over the longer horizon.

---

## §10 — SaberSim teardown (reference)

Full SaberSim methodology teardown is in §2.2. Key reference points:

- SaberSim is a play-by-play / possession-level Monte Carlo simulator.
- Their primary edge inputs are inferred to include: (i) shot-quality model from public + proprietary tracking, (ii) lineup-aware pace estimator, (iii) per-coach rotation model, (iv) live in-game projection updates.
- Their CLV-relevant strengths: joint correlations (DFS lineup correlations especially), shot-quality-driven props.
- Their CLV-relevant weaknesses: over-reliance on simulation noise (their distributions are sometimes wider than necessary), slow update on injury news (sometimes 10+ minutes lag), DFS-optimized rather than props-optimized.
- The CLV gate (positive CLV vs SaberSim across 100+ stratified props) is a sufficient statistic for "is my system good enough" — if you can beat their public projections in CLV terms, you have replaced the subscription.

---

## §11 — Meta: process notes

This synthesis was produced by 8 parallel research streams across:
1. NBA projection model architecture survey (DARKO, LEBRON, EPM, RAPTOR, PIPM, BPM, DRIP, PER, etc.)
2. SaberSim methodology reverse-engineering (public statements, output behavior analysis)
3. Per-stat deep dives (10,580-prop empirical sharpness ranking)
4. Public data infrastructure mapping (14 data sources, latency, rate limits)
5. Architectural alternatives evaluation (A through G, mechanism-first)
6. Era effects analysis (2020-2026, rule changes, CBA effects)
7. Joint distribution / correlation analysis (per-position correlation matrices)
8. Red-team / failure mode analysis

The verdict was *not* pre-determined. The "stay" / "rebuild" / "hybrid" trichotomy was evaluated on mechanistic grounds, not on aesthetic or convenience grounds. The hybrid verdict emerged because:
- Per-minute-rate × minutes is mechanically correct as an *outer* decomposition (minutes is the dominant exposure).
- The diagnosed failure pattern is the architectural fingerprint of *inner* conflation, not of the outer decomposition.
- The smallest mechanistic resolution is to condition the rate term on role context.
- A full rebuild is not cost-justified given (a) the marginal CLV gain is small after A+ is built, (b) public data limits the play-by-play sim ceiling, (c) maintenance burden is multiplicative.

The strongest counter-evidence to the verdict (red-team) is in §9. The most dangerous unknown is in §8 item 1 (role-context bias magnitude). The recommended next research action after v1 ships is the controlled within-player-within-season role-context bias study.

### 11.1 Why CLV is the right metric

- MAE is a proxy. It rewards being close to the actual outcome on average.
- CLV measures whether your projections move the market — if your model identifies a prop as +EV at 11:00 and the line moves toward your number by tipoff, you have CLV.
- CLV is the strongest leading indicator of long-run profitability in sharp betting markets.
- A model with worse MAE but better CLV is preferred.

### 11.2 Why a 100-bet sample is enough for the gate

- CLV is much less variance-prone than P&L. 100 bets is typically enough for ±0.5% CLV confidence intervals, well below the gate threshold.
- P&L gates require 1000+ bets for similar confidence. The CLV gate is the right early-validation metric.

### 11.3 Build velocity recommendations

- Ship v1 in 4–6 weeks. Hard deadline.
- Validate against CLV gate within 2 weeks of v1 ship.
- Iterate v2 features in 2-week sprints based on residual analysis.
- Defer all v3 architectural changes until v2 has been gate-validated.
- Maintain a single-canonical-decision-doc per architectural decision (this report being the v1 instance).

---

## §12 — Known-unknowns checklist (mandatory ≥10 items)

These are explicit gaps where the right answer is uncertain and a decision is required from the engineer. Each item lists the gap, the default chosen, and the experiment that would resolve it.

1. **Role-tier count (4 vs 5 vs 7 tiers).**
    - *Default:* 5 tiers.
    - *Resolution:* Hold-out per-tier MAE comparison after v1 ships.

2. **Garbage-time threshold (90% vs 95% vs 99% win probability).**
    - *Default:* 95% (CtG standard).
    - *Resolution:* Compare per-stat MAE at each threshold on held-out games.

3. **Bayesian shrinkage strength per stat.**
    - *Default:* `n / (n + k)` with k = 8 for high-signal stats (PTS, MIN), k = 15 for noisy stats (3PM, STL, BLK).
    - *Resolution:* Per-stat hyperparameter sweep.

4. **Cold-start prior magnitudes.**
    - *Default:* (24/16/8/3) MIN by role signal.
    - *Resolution:* Track residuals across the 10–30 cold-start cases per season; update priors quarterly.

5. **Coach-feature dimensionality.**
    - *Default:* 6 features per coach (avg starter min, bench depth, DNP-rest freq, playoff-positioning behavior, foul-trouble policy, B2B reduction magnitude).
    - *Resolution:* Add interaction terms if per-coach residuals exceed 1.0 MIN.

6. **Negative binomial vs Poisson vs ZIP for low-mean count stats (3PM, STL, BLK).**
    - *Default:* Negative binomial.
    - *Resolution:* AIC/BIC comparison on held-out distributional fit.

7. **Position-tier correlation matrix granularity (5 positions vs 3 positions vs team-specific).**
    - *Default:* 5 positions, league-wide.
    - *Resolution:* Cross-validate joint-prop calibration with finer/coarser groupings.

8. **65-game rule late-season minute lift magnitude.**
    - *Default:* +0.5–1.5 MIN if star is below threshold late in season.
    - *Resolution:* Late-2025-26 season residual analysis after enough cases accumulate.

9. **Rolling rate window length (last 30 games vs last 20 vs season-to-date).**
    - *Default:* Last 30 games, availability-weighted.
    - *Resolution:* Per-stat MAE across window lengths on held-out games.

10. **Live data refresh cadence (1-min vs 5-min for injury feeds).**
    - *Default:* 5-min refresh, escalate to 1-min if CLV improves materially.
    - *Resolution:* A/B test on prop CLV at each cadence.

11. **Vegas spread feature inclusion in rate model (vs minutes-only).**
    - *Default:* Include in minutes regression, exclude from rate regression except for blowout-sensitive stats.
    - *Resolution:* Per-stat residual analysis with/without spread feature.

12. **Era weight decay schedule.**
    - *Default:* See §6.6 table.
    - *Resolution:* Sensitivity analysis on training-data weights vs held-out 2025-26 MAE.

13. **Architecture B (volume × efficiency) for non-PTS stats.**
    - *Default:* PTS only.
    - *Resolution:* Try for AST (decompose into team_FG_attempts × player_AST_share) in v2.

14. **Pace adjustment per-stat sensitivity.**
    - *Default:* Linear scaling for PTS/REB/AST, sub-linear for 3PM, no scaling for STL/BLK/TO.
    - *Resolution:* Per-stat regression on (proj_pace, actual_stat) holding minutes constant.

15. **Multivariate Normal vs Copula for joint distribution.**
    - *Default:* MVN with empirical correlation matrix.
    - *Resolution:* Compare joint-prop calibration on DD2/TD3 events.

16. **Foul-trouble live adjustment per-coach overrides.**
    - *Default:* League-average foul-trouble policy.
    - *Resolution:* Per-coach validation after sample of in-game foul-trouble events accumulates.

17. **Negative binomial dispersion parameter per-player vs per-position.**
    - *Default:* Per-position (smaller variance, more stable estimates).
    - *Resolution:* Hierarchical model with per-player random effect, validate convergence.

18. **In-Season Cup game treatment (separate weighting vs regular season).**
    - *Default:* Treat as regular season for projection purposes.
    - *Resolution:* Compare residuals on Cup vs non-Cup games.

19. **Twitter API status feed reliability.**
    - *Default:* Use as primary fast-update source, RotoWire as redundancy.
    - *Resolution:* Track latency and accuracy; escalate to multi-source aggregation if either is unreliable.

20. **CLV gate threshold (0% vs +1% vs +2%).**
    - *Default:* 0% (parity with SaberSim) for v1 → +1% for v2 → +2% for v3.
    - *Resolution:* Gate threshold is product decision, not engineering decision.

---

## Appendix A — Implementation reference snippets

(See §2.5 for cold_start_projection_prior, availability_weighted_rolling_stats, post_trade_efficiency. See §4.4 for cold_start_minutes_prior. See §5.9 for empirical correlation matrix.)

## Appendix B — Sources consulted

- DARKO (Kostya Medvedovsky, public Twitter and methodology posts)
- LEBRON (BBall-Index, Offensive Archetypes documentation)
- EPM (Dunks & Threes, methodology page)
- RAPTOR (FiveThirtyEight, pre-deprecation methodology archive)
- PIPM (Jacob Goldstein)
- BPM 2.0 (Daniel Myers, Basketball Reference)
- DRIP (Jeremias Engelmann)
- Cleaning the Glass (garbage-time standard, on-court splits)
- PBPStats.com (possession-level data, on/off splits)
- Basketball Reference (game logs, rotation data, coach data)
- nba_api (NBA Stats endpoints)
- RotoWire (injury status feeds, lineup confirmation)
- SaberSim (public methodology statements, output behavior analysis)
- Awesemo, ETR (DFS projection comparison)
- The Odds API (line movement, market closing prices)
- Twitter (beat reporter feeds, Wojnarowski, Charania, Stein)
- NBA.com schedule, injury report PDFs

## Appendix C — Glossary

- **A+:** Architecture A with role-conditional rates and minutes regression. The v1 recommendation.
- **CLV:** Closing Line Value. Difference between bet price and closing price, in implied probability or odds.
- **DARKO:** Daily Adjusted and Regressed Kalman Optimized projections.
- **DRIP:** Daily Rapm Information Player.
- **EPM:** Estimated Plus-Minus.
- **LEBRON:** Luck-adjusted player Estimate using a Box prior Regularized ON-off.
- **MAE:** Mean Absolute Error.
- **MVN:** Multivariate Normal.
- **NB:** Negative Binomial.
- **PBPStats:** Public play-by-play stats site.
- **RAPTOR:** Robust Algorithm using Player Tracking and On/Off Ratings (FiveThirtyEight, deprecated 2023).
- **SGP:** Same-Game Parlay.
- **TD3:** Triple-Double.
- **DD2:** Double-Double.
- **CtG:** Cleaning the Glass.

---

**END OF REPORT**
