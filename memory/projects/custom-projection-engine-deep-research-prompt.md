# Custom Projection Engine — Deep Research Prompt (Exhaustive)

**Hand this to a deep-research agent (Claude Research, a subagent, Perplexity Pro, Gemini Deep Research, etc.). This prompt is self-contained and should not be edited when pasting. The agent's output will be consumed by a builder who is actively writing the engine, so ground everything in mechanism and implementability.**

---

## 1. Mission

I am building a custom NBA player-projection engine that outputs mean projections and full predictive distributions for **PTS, REB, AST, 3PM, STL, BLK, TO, MIN** (and ideally DD2/TD3 flags) for every NBA player on every NBA slate. The engine's output is consumed by a downstream betting system (`run_picks.py`) that scores props, sizes bets via a Kelly-derivative, and places OVER/UNDER wagers across CO-legal sportsbooks.

**Baseline to beat:** SaberSim ($197/mo). SaberSim stays live until my custom engine delivers equal or better **live closing-line value (CLV)** across 100+ graded bets. CLV is the ONLY real gate. Backtest MAE is a proxy and can mislead.

**Scope of this research:** everything — literally everything — that contributes to producing a humanly-best-possible pre-game projection. I want a ruthlessly comprehensive, evidence-backed treatment of every factor that can move player-projection accuracy, ranked by expected impact on live CLV, with concrete implementation guidance from public data only.

This is not a survey paper. This is a build doc. Every section must end in something I can implement.

**Hard constraint — data:** public or self-scraped only. nba_api, Basketball Reference scraping, public Kaggle datasets, Odds API, NBA.com stats endpoints, RotoWire public feeds, beat-reporter Twitter/X, YouTube game footage (manual tagging at most), open-source NBA analytics libraries (e.g. `py-ball`, `nba-api`, `pbp-stats` open endpoints). If a premium source (Second Spectrum, Synergy, BBall Index, Cleaning the Glass paid tier, PBP Stats paid, Krossover) is clearly best-in-class, note it, cite the feature it unlocks, and propose a public-data approximation with a magnitude estimate of the accuracy gap.

**Hard constraint — philosophy:** mechanism-first. No empirical constants or tuned multipliers without a named causal justification. If a factor "works in backtest" but no one can explain why, treat it as suspect overfitting. Black-box ML is acceptable only when (a) the feature set is mechanism-grounded and (b) calibration is testable on held-out data.

**Hard constraint — debuggability:** the model must be debuggable when I'm on a cold streak. When the projection system disagrees with the market, I need to be able to attribute the disagreement to specific features ("we projected the OVER because of pace × matchup factor × absorption bump"). Pure end-to-end black-box architectures are rejected. Every recommendation must state its **debuggability cost** — how hard it is to explain a single prediction post-hoc.

---

## 2. Deliverable — what I want back

A long-form markdown report with this **exact top-level structure**:

### §1. Executive summary (≤2 pages)

Top 15 highest-impact levers ranked by expected CLV contribution. Each lever gets: one-sentence mechanism, one-sentence evidence pointer with citation, expected MAE magnitude ("~0.4 PTS MAE reduction" vs "marginal <0.1"), implementation difficulty (trivial / moderate / hard), and **debuggability cost** (clean / opaque / black-box). Include a stoplight column: green = build now, yellow = build v2, red = research first.

### §2. Per-domain deep dives (one section per domain in §10 below)

Each domain section must contain:
- **Mechanism** — what the factor is and the causal path by which it affects projection accuracy
- **Evidence** — citations (papers, post-mortems, public model cards, Kaggle write-ups, NBA analytics blogs, substantive Twitter threads with data). Quote numbers where possible, not vibes
- **Data source** — exact public endpoint / URL / scrape target, with sample response schema where non-obvious
- **Implementation sketch** — pseudocode, SQL, or Python fragments. Not a full implementation; enough for a builder to start
- **Expected impact** — rough magnitude for NBA prop projection MAE (in PTS-equivalent units where possible)
- **Debuggability cost** — how hard is it to explain a single projection after this feature is in the model
- **Contamination / failure modes** — how this factor can silently break the model if implemented wrong
- **Interaction effects** — which other domains this factor correlates with (so the builder avoids double-counting)

### §3. Architectural choices

Evaluate at least five candidate architectures against my use case — see §6 below for the canonical list. For each: what it models natively, what it approximates, what public implementations exist, debuggability cost, CLV implications.

### §4. Minutes prediction as a standalone subproblem

Deep dive. See §7 below.

### §5. Prop-type specifics

Per-stat deep dives: PTS, REB, AST, 3PM, STL, BLK, TO, MIN. See §8 below.

### §6. Cross-cutting concerns

Data infrastructure, backtesting methodology, leakage prevention, statistical modeling choices, calibration, uncertainty quantification, production-vs-research gap. Treat as first-class content, not an appendix.

### §7. Concrete recommendations for my specific case

I am replacing SaberSim for NBA player props, CLV-graded. What to build first, what to defer, what to skip entirely as noise. Name the v1 feature set, the v2 feature set, and the v3 "maybe" pile. Explicitly call out factors that most public writeups overrate.

### §8. Open research questions

Where the public literature is thin, contested, or contradictory. What would need to be measured empirically on my data. Each open question gets a proposed experiment design (data needed, metric, expected effect size to detect).

### §9. Red-team section

Pre-emptive counterarguments to §7. What assumptions am I making that could silently sink this entire project? What's the null-result outcome if every recommendation above is implemented correctly? Where could SaberSim already be doing something I can't replicate from public data?

### §10. SaberSim teardown

Explicit, evidence-based reverse-engineering of SaberSim's methodology from their public marketing, podcast appearances, Reddit AMAs, DFS-community discussion, publicly visible export format, blog posts, and any employee LinkedIn / conference talk. What stats do they model? What architecture is implied? What signals dominate their output? What's the public-data-replicable portion of their edge vs the proprietary-data portion? Include a table of inferred features ranked by confidence of inference.

### §11. Meta — what this prompt didn't ask about

If in your research you found factors or considerations that don't fit any domain in §10 below and weren't anticipated by this prompt, add them as a final section. This is explicitly solicited — I want what I didn't know to ask.

### §12. Known-unknowns checklist

A hard list of every question you tried to answer but couldn't find public evidence on. Format: one line per unknown, with (a) the question, (b) why it matters, (c) what public source you'd want but couldn't locate, (d) the experiment I could run to resolve it. This becomes my next-experiment backlog. If this section has fewer than 10 items, you weren't trying.

---

## 3. Hard rules — do not violate

- **Public data only.** Premium sources noted but not relied on.
- **Mechanism-first.** No "this just works" explanations. No tuned constants without named priors.
- **No band-aids.** Every proposed feature must have a causal justification or it gets rejected.
- **CLV is the gate, not MAE.** When MAE and CLV disagree, CLV wins. Call out cases where a feature might improve MAE but hurt CLV (e.g. by chasing noise the market already priced).
- **Debuggability required.** Every recommendation names its debuggability cost. Black-box preferences are flagged, not hidden.
- **Prefer 2018+ sources**; pre-2018 sources are acceptable for foundational ideas but must be flagged as "classical — verify still applies post-Zach Lowe era / post-load-management era."
- **Cite or caveat.** Every non-obvious claim gets a citation or an explicit "my hypothesis, unconfirmed."
- **Don't validate — challenge.** If my starting taxonomy is missing something important, add it. If something I listed is noise, flag it and move on. Don't just reorganize my list.
- **Quantify when possible.** "Small improvement" is useless. Give a range, a benchmark, a p-value, or say "no public estimate exists."
- **Flag proprietary moats.** If a factor genuinely requires proprietary data (Second Spectrum tracking, Synergy play types), call it out and estimate what MAE I'm leaving on the table by skipping it.

---

## 4. Non-goals — explicitly out of scope

- **Playoff-specific modeling.** Regular-season NBA is my focus. Note playoff differences where relevant but do not build a separate methodology.
- **Live / in-game projections.** Pre-game close only. KairosEdge handles live trading separately.
- **DFS contest selection / lineup construction.** DFS-flavored projection sources are noted, but GPP-vs-cash lineup strategy is out of scope.
- **Non-NBA sports.** This research is NBA-specific. Cross-sport transferability may be noted but not developed.
- **Futures markets.** Championship, MVP, win-totals are not player-prop markets; skip.
- **Spread / total game-line modeling.** Only as far as it feeds into player props (via pace, garbage-time probability, implied team totals). Do not build a game-line model.
- **Preseason projections.** Volatile enough to treat as noise. Regular season start = the projection horizon.
- **Summer League / G-League standalone projections.** Only used as cold-start priors for rookies and call-ups, not as a projection target.
- **Retrospective / post-hoc analysis tools.** This is a forward projection engine, not a post-game analytics dashboard.
- **Model compression / inference latency.** Scale is 200-300 projections per slate; inference time is not a constraint.

---

## 5. Ranking criterion for the Executive Summary

Each of the top 15 levers in §1 should have an estimated CLV contribution, computed as:

> **CLV lift = (expected MAE improvement) × (market sensitivity to that MAE improvement in player props) × (fraction of slates where the factor meaningfully applies)**

Examples:
- A factor that improves PTS MAE by 0.3 across 80% of slates > a factor that improves MAE by 1.0 on 5% of slates.
- A factor that tightens REB MAE for centers by 0.5 but centers' lines are already sharp (low market sensitivity) < a factor that tightens 3PM MAE by 0.2 for guards where books are soft.
- Stat-specific market sensitivity matters. Books are sharpest on PTS, softer on AST and 3PM, varying on REB. Call this out when ranking.

Where evidence for magnitude is thin: say so, and propose a **cheap empirical test** I can run to measure it (experiment design, metric, target effect size, sample size needed).

---

## 6. Architectural choices — evaluate alternative designs

Before diving into the factor taxonomy, the research should evaluate the architecture itself. My current engine is **per-minute-rate × minutes-baseline**, which is one design among many. For a greenfield rebuild, I want a sober evaluation of at least these architectures:

### Architecture A — Per-minute-rate × minutes-baseline (my current)
- Project MIN separately, project per-minute rate for each stat, multiply
- Pros: interpretable, modular, well-understood failure modes
- Cons: assumes rates are stable across minutes played (they're not — early minutes differ from garbage-time minutes)

### Architecture B — Volume × efficiency decomposition
- PTS = (FGA × FG%) + (FTA × FT%) + (3PA × 3P%). Project each component separately.
- Pros: decouples the volume drivers (pace, usage, opponent defense possessions) from efficiency drivers (defender quality, shot profile, rest). Usually more robust.
- Cons: more components = more variance unless correlations are modeled
- See §10.AC for research ask

### Architecture C — Per-possession / per-play models
- Rate stats modeled per-possession (not per-minute). Possessions ≠ minutes due to FTs, timeouts, reviews.
- Pros: isolates pace effect more cleanly
- Cons: possession counts must be estimated; data is sparser

### Architecture D — Play-by-play event engine
- Monte Carlo simulation of games at the possession level. Each possession is a mini-simulation drawing from player and defensive archetypes.
- Public reference: DARKO's approach, possession-level sims in NFL (e.g., numberFire-style)
- Pros: natively produces full distributions, handles garbage-time and usage-absorption implicitly, handles OT
- Cons: expensive, many hidden assumptions, debuggability is harder, calibration is a nightmare

### Architecture E — Shot-level model
- Each shot as a row with features (location, defender, clock, fatigue). Aggregate to player-game projections.
- Pros: best for efficiency; handles defender matchup at the shot level
- Cons: requires shot-tracking data (some in public box score, much proprietary)

### Architecture F — Hierarchical Bayesian per-player
- DARKO-style Kalman-filtered per-player state with league-wide priors
- Pros: principled handling of small samples, rookies, returns from injury
- Cons: computationally heavier; priors drive results when data is thin (good or bad)

### Architecture G — Ensemble / stacked
- Multiple base projections (A + B + F) combined by a meta-learner
- Pros: usually lower variance, catches complementary errors
- Cons: meta-learner can overfit, debuggability drops sharply

**For each architecture, the research should return:**
- Public implementations or methodology writeups that exemplify it
- Native handling of the three concerns in §9 (injuries, team changes, unknown unknowns)
- Debuggability cost
- Expected CLV ceiling vs my current Architecture A
- Engineering cost vs Architecture A

Include a recommendation: which architecture (or hybrid) is best for a solo builder targeting CLV-positive NBA props with public data, and why.

---

## 7. Minutes prediction as a standalone subproblem

"Who plays how many minutes" is arguably 70% of projection variance for counting stats. A bad minutes projection dominates everything downstream. I want this treated as its own research thread:

- **Rotation prediction models** — how do public and DFS projections predict rotations? Depth charts, beat-reporter signals, coach history, load-management flags
- **Minutes floor / ceiling detection** — when is a player on a minutes restriction? When is a player due for heavy minutes (playoff push, opponent depth thin)?
- **Back-to-back minutes adjustment** — second night of B2B, how much to dock star minutes?
- **Foul-trouble expected value** — how to project minutes when a player averages high foul rates against foul-drawing opponents
- **Blowout detection and garbage time** — if spread is 12+, starters likely pulled in 3Q. Model this explicitly vs hoping the mean projection covers it
- **Injury-driven minutes spikes** — when a star is OUT, who absorbs the minutes, and by how much? Absorption hierarchy research
- **Mid-game exit detection** — not predictable pre-game, but historical tail-probability weight matters for variance estimate
- **Coach-specific rotation patterns** — some coaches (Pop historically, Spoelstra, Stevens) rotate aggressively; others (Monty Williams historically, Thibs) play starters heavy
- **Ejection / foul-out rate as player features**

Deliverable for this section:
- A recommended architecture for the MIN projection (separate from the rate models)
- Named public sources for rotation / minutes prediction
- Benchmark MAE for minutes projection (what's state of the art publicly?)
- A sensitivity analysis: "if we improved MIN MAE from X to Y, how much does PTS MAE improve downstream?"

---

## 8. Prop-type specifics — per-stat deep dives

The current prompt treats PTS / REB / AST / 3PM as similar. They're not. Each has its own variance structure, market-efficiency profile, and dominant drivers. The research must include a named sub-section for each stat:

### PTS
- Dominant drivers: MIN × usage × TS%, all modulated by opponent
- Market efficiency: highest — books are sharpest on PTS
- Key failure modes: blowout garbage-time depression, foul-trouble minutes loss
- Recommended features: (list in output)

### REB
- Dominant drivers: opponent missed shots (OFF rating × pace × position-specific rebounding) + teammate rebound competition
- Market efficiency: moderate
- Key failure modes: teammate bigs swapping in/out (absorption), small-ball lineup shifts
- Recommended features: (list in output)

### AST
- Dominant drivers: teammate FG% × personal passing volume × opponent defensive rotation quality
- Market efficiency: softer than PTS
- Key failure modes: teammate hot-shooting or cold-shooting swings the AST number 2-3 even with identical playmaking
- Recommended features: (list in output)

### 3PM
- Dominant drivers: 3PA × 3P% (high variance). 3PA more predictable than 3P%
- Market efficiency: softer; heavy-variance stat with bookmakers relying on linear blends
- Key failure modes: binomial variance is huge on 6-8 3PA per game, hot/cold streaks amplified
- Recommended features: (list in output)

### STL / BLK
- Dominant drivers: MIN × opponent offensive style. Pure counting stats with high variance
- Market efficiency: softest of major stats
- Key failure modes: any player on any night can bank a 3-STL game with zero predictability
- Recommended features: (list in output)

### TO
- Dominant drivers: usage × ball-handling role × opponent pressure defense
- Market efficiency: moderate
- Key failure modes: negatively correlated with scoring volume (usage ↑ = TO ↑); propped mostly for PG/playmakers
- Recommended features: (list in output)

### MIN
- Treated separately in §7 above. Included here for completeness.

For each stat, the research should also address:
- The stat's specific variance floor (even perfect projection of the mean leaves residual variance — what's the minimum achievable MAE given natural variance alone?)
- Whether separate models per stat or a multi-output shared model is better
- Which stats have SGP correlation effects that require joint modeling

---

## 9. Specific concerns — address head-on

I have hit three classes of issue in my current engine. Each is representative of a broader blind spot. Address them EXPLICITLY in the report with named sections.

### Concern 1 — Season-long injury accounting is suspect

When a player tears an ACL in December, the historical data pull still includes their pre-injury games in rolling windows for opponent defense, team pace, teammate absorption, and lineup context. Their presence/absence distorts:

- **Opponent defensive ratings.** Team defended at rank X with their rim protector; now defends at rank Y without him. Rolling-30 DEF ratings blend the two.
- **Teammate usage redistribution.** When Jamal Murray tore his ACL in 2021, Denver's usage structure changed. Historical means don't know that.
- **Team pace and shot distribution.** Core player out → pace changes, shot profile changes, spacing changes.
- **"Healthy-mean" historical projections for teammates** that don't account for "this player was out for the last 50 games."
- **Opponent match-ups retrospectively.** A team "allowed 30 PTS to opposing PGs" — except most of those came before their starting PG-defender got hurt.

**Research questions:**
1. How do DARKO, LEBRON, RAPTOR, PIPM, EPM, BPM publicly handle season-ending injuries in rolling windows? Cite methodology posts.
2. What's the right way to split "historical data pre-injury" from "post-injury" for aggregations? Do serious models use **availability-weighted rolling windows**, explicit "scenario" models, or just ignore the problem?
3. How long does it take for teammate stats to stabilize after a key teammate goes down? (cite or propose an experiment)
4. Do teams that routinely lose stars to injury (LAC Kawhi, PHI Embiid) have systematic mispricings in player props? Is there a market-timing edge here?
5. What's the difference between "season-ending" and "long-term-IL-15-games-or-more" for projection purposes? Are they modeled the same, or separately?
6. How do public models handle the asymmetric case where injury happens mid-game (player exits, usage redistributes live)?
7. Is there an open-source library that handles "availability masking" for rolling NBA stats? (nba_api doesn't; what does?)
8. **Injury-report hit rates.** What percentage of "Q" designations actually play? By team (some teams are known to sandbag Q designations), by player type, by injury type, by time-to-tip. This is prior work that can be leveraged directly for real-time adjustments.

### Concern 2 — Players on the wrong team

nba_api and most public sources have a lag on team assignments. Mid-season trades, waivers, 10-day contracts, two-way call-ups, buyout signings, G-League assignments. A traded player can show up with their old team for days. The projector then:

- Attributes their stats to the old team's pace/context
- Uses the old team's opponent schedule and matchup factors
- Misses rotation effects of the new team (new role, new usage, new partners)
- In extreme cases, matches them up against their former team with the wrong priors (insult to injury)

**Research questions:**
1. What's the authoritative real-time source for NBA team assignments? NBA transactions feed (official)? Basketball Reference daily updates? RotoWire? Twitter? Rank them by latency and reliability.
2. How do serious projection models detect and handle mid-season team changes? Is there a "freshness-check" pattern?
3. What's the typical stabilization period for a traded player in new context? (cite or propose)
4. Specifically: post-trade, how many games until the player's projection should rely on new-team pace/lineup data vs old-team priors? Is this linear decay, step function, Bayesian update?
5. How should 10-day contracts, two-way players, and G-League call-ups be handled? They often have very limited NBA sample in the current season.
6. Buyout market — players signed late season (e.g., post-deadline). What priors are reasonable? Do public models just skip them, or is there a methodology?
7. What's the edge available from beating the market to team-change information (minutes after trade announced vs at line release)?
8. International signings mid-season — how do you build a projection for a player with zero NBA games in 2026 but overseas games? Translation factors?

### Concern 3 — Unknown unknowns

List every factor a serious NBA projection model should consider. Assume my starting taxonomy in §10 is incomplete. Use the research to find factors I've missed. Give new factors equal treatment in the deep-dive sections.

Specific directions to search:
- What's changed about the NBA from 2020-2025 that older models don't capture? (pace, 3PT rate, load management, 65-game awards rule, In-Season Tournament / NBA Cup, play-in tournament, new CBA, second apron rules)
- What's the role of emerging tracking-data features (even if proprietary) and can any be proxied from play-by-play?
- What are the NBA-specific analogs of recent advances in sports modeling from other leagues (MLB launch-angle revolution, NFL EPA/PFF grades, soccer xG)?
- What do top DFS players (RotoGrinders top 100) actually look at that public projection models don't?
- Are there non-obvious behavioral / psychological factors with public evidence? Contract year, revenge game, homecoming, national TV, playoff implications, milestone chases, final-season veterans?

---

## 10. Domains to cover — exhaustive taxonomy

This taxonomy is the minimum. Expand, reorganize, and add new domains as needed. Do not treat this as complete — I expect the report to surface categories I didn't list.

### A. Data quality, identity, and provenance

- **Player identity:** correct canonical ID across sources, handling of Jr/Sr, name changes (legal, married), diacritics (Dončić, Jokić, Šarić), nicknames and short-names used by beat writers
- **Team identity:** abbreviation changes over history (BRK vs BKN, PHX vs PHO, CHA vs CHO, NJN → BKN), relocation handling
- **Game identity:** game ID stability across sources, doubleheader handling, rescheduled games, COVID-era postponements, neutral-site games (Mexico City, Paris, London, in-season tournament Vegas)
- **Minutes precision:** whole-minute reporting vs seconds, missing box score (rare but happens), play-by-play reconstruction when box score fails
- **OT handling:** extra minutes distorting per-36 / per-possession rates, how to decide whether to include OT in rolling stats
- **DNP taxonomy:** Coach's Decision, Rest, Injury (specific), Personal, Not With Team, G-League Two-Way Limit, Suspension, Bereavement, Precautionary Health and Safety Protocols (legacy), 65-game eligibility maintenance. Which of these exist in nba_api? Which require scraping?
- **Foul-outs:** 6+ fouls = DQ. Box score shows full minutes if played until DQ'd; how to detect and flag for usage projection on future games (foul-out rate as a player feature)
- **Ejections:** tech + flagrant accumulations; rare but real (Draymond, Embiid)
- **Mid-game exits:** injury that didn't return; silent in box score (just low minutes), critical for understanding the game's usage context that day
- **Rookie data sources:** college (NCAA box), G-League, EuroLeague, NBL (Australia), Summer League, Pro Day, combine. Translation factors between leagues
- **Back-of-schedule artifacts:** All-Star break, Christmas Day, MLK Day, In-Season Tournament semifinals/finals
- **Playoffs vs regular season:** if including playoff data in features, how to weight / flag
- **Preseason:** mostly noise, but rookies and late-summer adds can have signal. How to handle
- **Historical backfills:** nba_api sometimes backfills corrections. Snapshotting vs live-query
- **Timezone and DST:** game times stored as what? Date parsing failures on DST boundaries
- **Home/away logic:** confirm from game_id not from column that could swap. Neutral site handling
- **Box score variants:** traditional, advanced, tracking (proprietary), hustle, defense. Which are free and where
- **Schema evolution:** nba_api changing endpoints, deprecated endpoints, rate limits
- **Injury-report classifications** — Out, Doubtful, Questionable, Probable, Available. Hit rates by classification. Team-specific sandbagging. Time-of-release latency (1h pre-tip vs 3h pre-tip)

### B. Player-level static features (slow-changing)

- Age (exact birthdate, not just year), height, weight, wingspan (if measurable), standing reach (rarely public)
- Position (traditional 1-5 + modern classifications: combo guard, wing, stretch 4, small-ball 5, point forward)
- **Player archetype clustering (modern positionless)** — go beyond traditional positions. Public approaches use K-means / Gaussian mixture over shot profile + usage + defensive role + height × speed. Cite recent work (2022+). This unlocks better matchup priors than raw position.
- Draft position, draft year (pedigree prior for young players)
- Years of experience (rookie, sophomore leap, prime, decline curves)
- Handedness (affects defender matchup modeling)
- College / international origin (prior strength by league)
- Historical injury record (games missed by season, types of injuries, chronic flags)
- Physical conditioning reputation (hard to quantify; beat reporters reference it)
- Shot form classification (catch-and-shoot specialist, pull-up artist, rim finisher, post scorer, playmaker)
- Defensive archetype (switch-everything, drop big, rim protector, pestering guard, help defender)

### C. Player-level dynamic features (per-game, trend-aware)

- EWMA per-minute rates for every stat, various spans
- Usage rate and variance over time
- Shooting efficiency: TS%, eFG%, 3P%, FT%, 2P%, rim FG%, mid-range FG%, corner-3 vs above-break-3
- Shot profile: rim / mid / 3 share; corner-3 share; pull-up vs catch-and-shoot; assisted vs unassisted
- Assist rate, turnover rate, OREB%, DREB%, total REB%
- Free throw rate (FTA per FGA), which signals drawing-fouls skill
- Usage curve by time (does usage spike late-game? early-quarter? clutch?)
- Personal pace (possessions when on floor, not same as team pace)
- Home/away splits (magnitude by player, not just league average)
- National TV splits (do stars step up? small sample, contested result)
- Day/night splits, weekday/weekend splits
- Back-to-back first game vs second game degradation
- 3-in-4, 4-in-6, 5-in-7 schedule density effects
- Days of rest curve (0, 1, 2, 3+) — rest-boost or rust?
- Season arc: early-season (rusty, heavier rotation), midseason, post-ASB jump, March fatigue, playoff push intensity, tank-team lineup compression
- Age-aware curves (rookie, sophomore, 2nd-contract, late-career)
- Contract year effects (often overstated — what does evidence show?)
- Post-trade adjustment (games until stabilization, as a function of role change magnitude)
- Fatigue: cumulative minutes L7 / L14 / L30 days
- Load: miles traveled, games in N days
- Hot/cold streak persistence vs regression. Is there a hot-hand effect? Gilovich said no, modern tracking says maybe
- Specific-opponent priors (does player historically crush certain defenses?)
- **Rookie / cold-start curves** — how do first-year projections stabilize? Suggested framework: Bayesian prior (college/G-League/combine) with exponential decay of prior weight as NBA games accumulate. What's the half-life of the prior? What's the minimum NBA sample before per-minute rates dominate?
- Jersey-number trivia (no predictive value; included here to flag as noise and skip)

### D. Role & usage context

- Pecking order within team (1st / 2nd / 3rd option in usage)
- On-court usage rate vs bench usage
- Touches per game (Second Spectrum metric; proxy from assists + FGA + TOV + FTA)
- Time of possession (proprietary; proxy from play-types)
- Pick-and-roll ball handler rate, screener rate
- Spot-up rate, catch-and-shoot rate
- Post-up rate (dwindling league-wide but still relevant for some bigs)
- Transition rate (leaks out, runs with ball, spot-up in transition)
- Isolation rate
- Shot-clock-pressured shot frequency (end of clock possessions)
- Clutch-time usage (Basketball Reference has this split; define clutch)
- Lineup-specific usage (role changes with starters vs bench units)
- **Usage-efficiency tradeoff curve** — well-documented: as usage increases, TS% typically decreases non-linearly. When absorbing usage from an injured star, the replacement's per-minute rates do NOT scale linearly with usage. Research the published curves (Kostya / DARKO methodology, Hollinger, APBR forums). What's the recommended functional form?

### E. Teammate / lineup features

- Who else is on the floor (5-man lineup or at minimum 3-man units)
- Lineup net rating, on/off splits
- Floor spacing — how many 3PT shooters are on the floor
- Playmaking hierarchy — when the primary creator sits, who runs offense, how much does the target player's usage jump
- Screen-setter availability (affects PnR ball-handler scoring)
- Rim protection presence (affects the target's paint scoring and the opponent's)
- Small-ball vs traditional lineups (affects rebounding, spacing)
- Staggered minutes — when stars sit, which bench units does the target share floor with
- Post-trade integration — new teammates, learning curve
- Rookie minutes trajectory — front-loaded opportunity or earned over time
- **Absorption hierarchy when a star is OUT** — not all teammates benefit equally. Research the modeling of absorption factors (Jacob Goldstein writeups, LineupLab approaches)

### F. Coaching and tactical features

- Coach identity and scheme (fast / slow pace, PnR-heavy, post-up heavy, 5-out)
- Rotation depth (7-man vs 10-man rotations)
- Minutes distribution pattern (star load vs democratic)
- Foul-tolerance (does coach pull player at 2 in 1st? 3 in 2nd? 6 = bench entire 3rd Q?)
- Late-game lineup preferences
- In-game adjustment tendency (reactive to matchups?)
- Development philosophy for rookies / sophomores
- Tendency to rest stars on back-to-backs (by coach, by star, by season)
- Playoff-seeding stakes approach (some coaches rest aggressively, some don't)

### G. Opponent features — defense

- Team DEF rating; league-average normalization
- Pace-adjusted DEF rating (defensive possessions)
- Defense vs Position (DVP) — team allows X PTS to PGs, Y to Cs
- Stat-specific DVP — REB allowed to bigs, AST allowed to PGs, 3PM allowed to wings
- Shot location allowed — rim attempts, mid-range allowed, 3PA allowed, corner-3 allowed
- FG% allowed by zone
- Opponent-specific primary defender — who will guard the target player, their height / speed / switch-ability
- Switch-heavy vs drop-coverage team (affects PnR ball-handler props)
- Rim protection (blocks, DRtg at rim)
- Opponent rebounding (DREB% affects offensive rebound opportunity for your bigs)
- Opponent turnover generation (steals, forced TOs) — affects pace and transition points
- Opponent fouling rate — affects FTA for drivers
- Opponent personnel changes (star defender out = stat boost for offense)

### H. Opponent features — offense (yes, it matters)

- Opponent OFF rating — affects game flow and garbage-time probability
- Opponent pace — combined pace is not additive; research shows team with slower pace often pulls combined pace toward theirs
- Opponent 3PT volume and accuracy — high-volume 3PT opponents force defensive scheme adjustments
- Opponent offensive rebounding — extends their possessions, reduces your touches
- Opponent shot profile — pace/style interaction

### I. Game context

- Location: home, away, neutral (play-in, in-season tournament, international game, All-Star)
- Altitude effect (Denver 5,280ft, Utah 4,226ft). Cite any evidence
- Travel distance, number of time zones crossed, direction (east-west asymmetry)
- Day-of-week effects (Saturday afternoon vs Wednesday late)
- Game time local vs circadian-ideal (East coast team playing 10pm PT)
- Back-to-back status (first game, second game, or standalone)
- 3-in-4, 4-in-6, 5-in-7
- Rest differential (you on 1 day, opponent on 3)
- Playoff implications (seeding, tanking, clinched)
- Contract-year motivation
- Revenge game (statistical evidence is weak; flag this)
- Homecoming / hometown game
- Milestone chases (approaching career records)
- National TV games (stat boost or just selection bias?)
- In-Season Tournament stakes (weighted differently by players / coaches?)
- Play-in tournament stakes

### J. Pace, possessions, and garbage time

- Team pace (possessions per 48) as rolling and seasonal
- Opponent pace
- **Pace interaction** — not a simple average; dominant tempo-setter tends to win the pace battle. Research the actual published formula(s) for combining two teams' paces (Dean Oliver, Hollinger, modern refinements)
- Implied possessions for the game
- Vegas total as a market-derived summary statistic for game flow
- Blowout probability from spread (affects garbage-time risk for starter props)
- **Garbage-time definition and detection** — Cleaning the Glass famously strips garbage time. Research the public-derivable definition (spread × minutes-remaining thresholds). Propose a reproducible formula from play-by-play data. What's the MAE improvement from excluding garbage time from rolling-average inputs?
- Overtime probability (low base rate but not zero; affects stat distributions)
- Fouling situations (late-game intentional fouling affects FT props, pace artificially)
- FT rate of game (affects clock-stoppage time, real-minute vs game-time)

### K. Officiating features

- Referee crew assignment (released ~24 hours pre-game, sometimes less)
- Crew tendency: foul rate, pace, tech-happiness, star treatment
- Crew pace (faster or slower games on average)
- Individual ref tendencies (some crews call more offensive fouls, some more defensive 3-seconds)
- Tech / flagrant call rate (ejection risk → minutes distribution impact)
- Home cooking (weak evidence but recurring claim)
- Video review frequency by crew (affects pace via stoppages)

### L. Physical and biomechanical

- Minutes load over last 7 / 14 / 30 days
- Miles of travel over last 7 / 14 days
- Games-in-X-nights schedules (3-in-4 through 5-in-7)
- Recent DNPs (load management as a leading indicator)
- Age-adjusted fatigue sensitivity
- Return-from-injury minutes restriction — when it's official and when it's inferred
- Chronic-injury flags (knee, back, Achilles) — different re-aggravation patterns
- Conditioning returns (from extended IL)
- Jump load / explosive work proxy (no public source; flag)
- Sleep and circadian proxies — scheduling-based (rarely individual-level)

### M. Mental / psychological

- Contract year (specific season — final year before FA)
- Free agency looming (last year of a multi-year deal)
- Post-injury return confidence (conservative play early after return)
- Trade rumor swirl (distraction hypothesis — evidence is thin)
- Revenge narrative (mostly noise but media amplifies small effects)
- Homecoming effect (returning to college town, hometown, former team)
- Clutch performer history (high-variance; flag the hot-hand debate)
- Tilt risk (recent ejection, family issue, public drama)
- Leadership game (captain motivated) — noise, flag
- Milestone chase (closing in on career record)
- Coach-player friction reported (rare, public)
- "Too-many-thoughts" concept (pre-game stakes overload) — pop-science, flag

### N. Market-derived features

- Opening line vs current line (movement magnitude and direction)
- Sharp-vs-recreational book divergence on props (CIRCA / Pinnacle / Bet365 vs DK / FD)
- Implied probability after removing vig (and methods: proportional, power, Shin)
- Line consensus across N books at close
- Volume and limit signals (hard to access publicly — flag)
- Alt-line curve coherence — does DK's 2.5-line imply the same distribution as their 3.5-line?
- Reverse-line-movement detection (line moves against public %)
- **Market-implied projections** — you can invert the line (+ vig) back to an implied median and std dev assumption. That's SaberSim's likely starting point. How sharp is the market as a projection source?
- Injury-timing edge — getting lineups before the line adjusts
- Steam moves (aggressive sharp action)
- Prop-specific market depth (PTS deepest, BLK/STL shallowest)
- **Pinnacle as a reference line.** Pinnacle's closing line is the public-accessible "truest" line for many markets. How do we translate Pinnacle's line to a projection distribution? Does Pinnacle's methodology have any public documentation?

### O. Statistical modeling choices

- **Point projection vs full distribution.** For O/U, distribution matters more than mean. Poisson, negative binomial, empirical-bootstrap, zero-inflated variants
- **Correlation structure between stats** (PTS ↔ AST for playmakers; PTS ↔ FGA; REB ↔ opponent shooting; 3PM ↔ 3PA). This matters hugely for SGP pricing but also for consistency checks
- **Hierarchical / Bayesian priors** — player within team within league. DARKO-style Kalman filter. PECOTA-style weighted-comp priors
- **Shrinkage to position-matched mean** for small samples (rookies, low-minute players)
- **EWMA alpha / span** — short (5-10 games) picks up form, long (30+) picks up underlying skill. Often blended
- **Date-weighted vs game-count-weighted recency** — are January games equal to December games? Schedule strength varies
- **Cold start** — rookies, post-trade, return from long injury. College / international translation
- **Stationarity assumptions** — when do they break? (trade, injury to key teammate, coaching change, role change)
- **Outlier handling** — blowups (50-pt games) and duds. Winsorize? Robust estimators? Mixture model?
- **Leak prevention in backtest** — no future data in past projections. Especially around injury status, team assignment, line movement
- **Walk-forward validation** — time-respecting CV, not K-fold
- **Survivorship bias** — filtering out players who didn't play masks the opposite group
- **Selection bias** — filtering "played games" implicitly selects against injury-affected performance
- **Regularization** — L1 / L2, elastic net, early stopping
- **Ensembles** — bagging (random forest), boosting (XGBoost, LightGBM), stacking. When they help vs when they hide signal
- **Neural approaches** — LSTMs, transformers on game sequences. Almost always overfit on 80 games/season/player. Flag
- **Monte Carlo simulation** — game-level sim with possession engine, vs feature-engineered regression. Tradeoffs
- **Calibration methods** — isotonic regression, Platt scaling, beta calibration
- **Mixture models** — "this player is either hurt or healthy this game; model each separately"
- **Quantile regression** — for variance estimate when full distributional fit is too fragile
- **Volume × efficiency decomposition** — see Architecture B in §6. Published evidence on whether product-of-components is more robust than end-to-end stat regression

### P. Uncertainty quantification

- Prediction intervals (not just point estimates)
- Variance components (player, team, opponent, context, residual)
- Empirical Bayes priors for small-sample players
- James-Stein shrinkage
- Bootstrap vs analytical CIs
- Calibration at different probability levels (50%, 75%, 90%)

### Q. Live operations / real-time features

- Injury news scraping latency (RotoWire, Twitter X, official NBA injury report)
- Starting lineup pings (~1-2 hours pre-game; confirmed via various sources)
- Late scratches (pregame warmup injuries, DNP-coach's decisions revealed late)
- Line movement monitoring and alert triggers
- Load-management watchlist (Kawhi, Embiid, AD, historical pattern)
- Personal / family emergency absences (rare, one-off, hard to predict)
- Weather-related travel delays (low frequency, rare impact)
- Last-minute lineup changes (announced 20 minutes before tip)
- "Game-time decision" handling — how to build a projection for a player who may or may not play

### R. Betting-specific translation

- Converting mean projection + variance estimate to OVER/UNDER probability
- Line positioning sensitivity: X.5 (no push), whole number (push), X.5 hook
- Push probability on integer lines and how it shifts implied probability
- Edge calculation: probability × (decimal_odds - 1) - (1 - probability)
- Kelly sizing derivatives (VAKE in my system)
- SGPs and correlation pricing (when is 2-leg a discount vs overpriced?)
- Alt-line exploitation (2.5 soft at DK while 3.5 sharp at Circa)
- Prop-market depth signals (deeper market = tighter true line)
- Timing of line release (openers vs close; openers noisier, close sharper)
- Book-specific tendencies (DK softer on AST, FD softer on 3PM — verify with data)

### S. Infrastructure / data engineering

- Refresh cadence per feed (nba_api, Odds API, injury sources)
- Schema versioning and migration
- Data lineage — which source, which timestamp, which transform
- Backtest harness — leak-free walk-forward
- Metric tracking per bucket: starter/bench, projected-minutes tier, usage tier, position, team, opponent
- CLV tracking as real ground truth post-hoc
- Model versioning — every live projection tagged with model version for attribution
- A/B testing — shadow-run new models before going live
- Monitoring and alerting for data anomalies (empty pulls, schema changes, rate limiting)
- Single-source-of-truth discipline — avoid two data paths producing different answers

### T. Failure modes to audit

- NULL-as-0 silent corruption (especially minutes, stats)
- Player name mismatches across sources (McGruder, Payne, duplicates)
- Team abbreviation mismatches (BKN vs BRK, PHX vs PHO, CHA vs CHO)
- Duplicate game rows (rare, but catches builders)
- Date timezone bugs (off-by-one on game dates)
- Home/away swap bugs
- Missing games in historical pull (especially Christmas, MLK, in-season tournament neutral sites, paused games)
- Preseason / playoff leaking into regular-season features
- Injury status stale (feed hasn't updated but you've already pulled)
- Team assignment stale (Concern 2)
- Rolling-window contamination when core player was out (Concern 1)
- Blowout games dominating averages
- Small-sample contamination for bench / two-way / 10-day contract players
- Survivor bias in averages (players who DNP'd don't get 0s included, silently biasing team aggregates)

### U. Era-specific / rule-change considerations

- 65-game rule (2023-24 season onward) affects load management patterns and award-chasers behavior
- New CBA second apron (2024+) affects roster construction and two-way availability
- In-Season Tournament (NBA Cup) — how much weight do teams put on it?
- Play-in tournament (9-10 seed matters)
- Rule changes: take-foul removal (2022), transition foul, Zaza rule, hostile crowd considerations
- 3PT revolution maturation (pace and style different 2016-2025)
- Load management backlash and league response
- Streaming / broadcast deals affecting scheduling
- COVID-era data — 2020-21 bubble, 2021-22 H&S protocols — treat as structural outlier or include with caveat

### V. Source quality and provenance

- nba_api (python-nba-api) — free, official endpoint wrapper, occasional rate limits, occasional schema drift
- Basketball Reference — comprehensive historical, scrape carefully (robots.txt), some tables gated
- NBA.com/stats — official, some advanced/tracking stats live here
- PBPstats.com — paid and free tiers; free has pretty good play-by-play
- ESPN — older scrape target, less reliable now
- RotoWire — injury feed, public and premium tiers
- Odds API — prop and game odds, consumed API, ~18 books
- Twitter / X — real-time injury news, scraping is fragile, rate-limited
- Reddit /r/nba — game threads, weak signal but possible
- YouTube (manual) — visual confirmation of minutes restrictions, injuries
- Synergy / Second Spectrum — proprietary tracking; note what features they unlock
- BBall Index / Cleaning the Glass paid — proprietary analytics; propose public proxies
- Kaggle — occasional NBA competitions, archived datasets
- Academic — JQAS, MIT Sloan proceedings, ASU / UT analytics departments
- Baseball Prospectus (PECOTA methodology — transfers via Bayesian priors)

### W. Calibration and validation

- Walk-forward backtest with explicit leak audit
- Per-bucket metrics (by stat, tier, position, minutes, usage)
- Calibration plots for O/U probability at 50 / 75 / 90%
- CLV tracking — the real gate, not MAE
- A/B shadow testing new model versions before live
- Comparison to SaberSim / public benchmarks
- Confidence interval coverage on prediction intervals
- Out-of-distribution detection (rookies, post-trade, return from injury)
- Rolling performance monitoring (drift detection over weeks)
- **Public MAE benchmarks** — what's state of the art for public models? Research and report: best-in-class MAE for PTS / REB / AST / 3PM from any cited public projection system. This defines the "MAE floor" I should target.

### X. Ensemble / meta-modeling

- Combining multiple sub-models (minutes model + per-minute rate model)
- Model selection vs model averaging (when to pick vs when to blend)
- Stacking (meta-learner over base models)
- Contextual meta-models (different models for rookies vs vets, starters vs bench)
- Mixture-of-experts (different specialized models for different player archetypes)

### Y. Edge cases and rare scenarios

- Trade-deadline day projections (roster churn)
- All-Star voting impact on minutes (not real but flagged)
- Emergency starts (backup PG starting because both PGs are out — usage spike)
- 2nd-round playoff push by 8-seed
- Return-from-suspension first game
- Return-from-personal-leave first game
- Rookie debuts
- G-League call-up first NBA game of the season
- Buyout signee first game on new team
- Coach fired mid-season — interim coach projections
- Final game of tanking team
- Game 82 with playoff seeding locked (rest everyone)

### Z. Meta — what this taxonomy might be missing

- **Macro-level factors** — CBA incentive structure changes, league-wide pace and 3PA trends, positional eras (center renaissance or death)
- **Motivation as a feature** — playoff vs tanking, awards chasing, team-building narratives
- **Information asymmetry** — sharpest bettors have faster injury news, warmup reports, insider access. What's the public-best ceiling?
- **Second-order effects** — how do opponent prep and counter-prep shift the projection? Can a smart projector know that Jokić's passing volume spikes when the opponent's primary rotation defender is out?
- **Style compression in the modern NBA** — positional archetypes blurring. How robust is "PG scoring" as a category in 2026?
- **Real-time model adjustments within the slate** — starting lineups drop at 6pm for a 7pm tip; market and projection both update. Is there a timing edge?

---

## 11. Sources to consult (starting list — expand aggressively)

### Public NBA analytics / projection models

- **DARKO** (Daily Adjusted and Regressed Kalman Optimized) — Kostya Medvedovsky. Public methodology blog posts, Twitter threads
- **LEBRON** — BBall-Index. Public methodology posts (even if full model is paid)
- **FiveThirtyEight RAPTOR** and **CARMELO** projection systems — archived methodology posts
- **PIPM** — Jacob Goldstein (public methodology)
- **EPM** (Estimated Plus-Minus) — Dunks & Threes (public writeups)
- **BPM** / **VORP** — Basketball Reference (simple but foundational)
- **ESPN RPM** — archived
- **Cleaning the Glass** — Ben Falk, public pieces only
- **Thinking Basketball** — Ben Taylor, YouTube + writeups
- **Positive Residual** — Todd Whitehead
- **Nylon Calculus** — historical archive, many foundational posts
- **APBRmetrics forum** — forum archives
- **MIT Sloan Sports Analytics Conference** — published papers
- **ASU Sports Analytics**, **UT Austin Sports Analytics** — academic output
- **Journal of Quantitative Analysis in Sports (JQAS)** — paywalled but some preprints exist

### SaberSim teardown — dedicated subsection

SaberSim is my baseline. I want an evidence-grounded reverse-engineering of what they do.

Sources to consult specifically:
- SaberSim's own marketing pages, "how it works" explainers, blog posts
- SaberSim founders / engineers' public appearances: podcasts (RotoGrinders, DraftKings Sweat, Establish The Run, Fantasy Points Radio), conferences, LinkedIn posts
- DFS community teardowns: RotoGrinders forums, Reddit r/dfsports, Twitter
- Visible export format: CSV column names, stat granularity, inclusion of variance, inclusion of ownership (DFS-specific)
- Review sites (Fantasy Labs, RotoWire comparisons)
- Public case studies or win-rate reports

Deliverables for this section:
- Inferred architecture (is it rate × minutes, Monte Carlo sim, ensemble?)
- Inferred stat set and output format
- Inferred feature set (what do they clearly use, what's unclear)
- Public-data-replicable portion vs proprietary portion
- Failure modes others have publicly called out
- A confidence-ranked table of inferred features

### NBA-specific writeups on projection mechanics

- Seth Partnow — The Midrange Theory, book + The Athletic columns
- Kirk Goldsberry — spatial analytics, YouTube + book
- John Hollinger — The Athletic archive, PER inventor
- Ben Falk — Cleaning the Glass (public content)
- Ben Taylor — Thinking Basketball, episode-level content
- Zach Lowe — occasional analytics deep dives
- Owen Phillips — F5 newsletter, public statistical writing
- Nate Duncan / Danny Leroux — Dunker Spot podcast (practitioner insights)
- Jacob Goldstein — Twitter and blog
- Kostya Medvedovsky — DARKO and related threads
- Todd Whitehead — Positive Residual
- Andrew Patton / Patrick Miao / other academic-adjacent analysts

### Betting-specific

- **Unabated** — public methodology on prop modeling, vig removal, market efficiency
- **Rufus Peabody** (Massey-Peabody) — podcast appearances, some writeups
- **Krackman** — Twitter, podcast appearances
- **Joe Peta** — Trading Bases (MLB methodology that transfers)
- **TeamRankings** — public methodology posts
- **Action Network** sharps content (some public)
- **Crossing Broad** — some analytics pieces
- **Sportsline** — public projections; use as competitor benchmark
- Relevant subreddits: r/sportsbook, r/sportsanalytics, r/NBAspreads (filter aggressively for actual data)

### Statistical and methodological

- Andrew Gelman — hierarchical modeling in sports, many blog posts
- PECOTA methodology (Nate Silver / Baseball Prospectus) — transferable
- Bill James — foundational for sample weighting and projection system design
- The Book: Playing the Percentages in Baseball (Tango/Lichtman/Dolphin) — linear weights and context effects
- Causal inference in sports — recent JQAS papers
- EWMA and exponential smoothing literature — Hyndman's forecasting textbook
- State-space models for sports — academic papers

### Concern-specific

- **For Concern 1 (injuries):**
  - Jacob Goldstein on teammate absorption
  - Rosen injury papers (if he has public ones)
  - Any academic paper on availability-weighted rolling stats
  - FiveThirtyEight CARMELO writeup specifically discusses injury handling
  - DARKO's handling of availability (check methodology posts)
  - Research on "Q" designation hit rates (RotoGrinders, FantasyLabs historical posts)

- **For Concern 2 (team changes):**
  - NBA.com transactions feed (official)
  - Basketball Reference transactions page
  - RotoWire / LineupLab / LineupHQ documentation of how they handle trades
  - Any trade-season post-mortem articles

### Data sources (exact URLs / repos)

- `github.com/swar/nba_api` — python wrapper
- `basketball-reference.com` — scrapeable, note robots.txt
- `stats.nba.com` — official endpoints
- `pbpstats.com` — play-by-play data
- `rotowire.com/basketball` — lineups, injuries
- `rotogrinders.com/projections` — DFS projections (competitor benchmark)
- `the-odds-api.com` — betting odds
- `kaggle.com/datasets` — search "NBA"
- `nbastuffer.com` — free stats
- `hashtagbasketball.com` — player stats + DFS
- `sportsreference.com/transactions` — trade history

### Open source libraries / notebooks

- `py-ball` (Basketball Reference scraper)
- `nba_api` (endpoints)
- `ballchasing-analytics` (if any)
- Any open GitHub repo labeled "NBA projection system"
- Kaggle NBA notebooks

---

## 12. Red-team questions for the researcher to answer before finishing

- **If every domain in §10 is implemented correctly, what's the expected MAE floor?** Public models suggest ~4.0-4.5 PTS MAE for engaged projection systems. Is getting to <4.5 realistic on public data alone?
- **What percentage of SaberSim's edge likely comes from proprietary data I can't replicate?** Be specific — is it 5%, 20%, 50% of their advantage?
- **Is there a single dominant lever (one factor that alone would close my MAE gap) vs many small ones?** If many small, what's the priority order?
- **Where is market already more efficient than even a best-in-class projector?** (Avoid building features the market already priced in)
- **What features SOUND smart but backtests show are noise?** (Revenge games, contract years, national TV games — what does the evidence actually say?)
- **What's the minimum viable feature set that beats SaberSim on CLV?** If it's 5 features, name them.
- **What are the 3 features that typically ruin rookie projectors and I should absolutely not build naively?** (Based on failure-mode patterns)
- **Is there an existing open-source NBA projection system I should fork rather than build from scratch?**
- **What do the current top DFS players know/do that public projection models don't replicate?**
- **What's the market-maker's response if my projections are CLV-positive?** Limit slashing, line moves, bet-deletion — what should I expect if my engine works, and how do I mitigate?

---

## 13. Meta — what this prompt might have missed

Before finalizing, reflect on this question: *what did this prompt not ask about that it should have?*

Possibilities to probe:
- **Cultural / team-chemistry factors** — hard to quantify, but some teams are famously "buy-in" or "fractured"; does public evidence support this as a stat-level feature?
- **Coaching tree / system effects** — do Spoelstra teams systematically outperform on certain props?
- **In-game information** — if our projection is purely pre-game, are we leaving CLV on the table by not ingesting live data in a pre-close loop?
- **Lineup card leakage** — coach announces starting lineup to media 45 min before tip. What's the information advantage window?
- **Rule-change adaptation curves** — when rules change, some teams/players adapt faster. Is there a leading indicator?
- **Player trajectory vs age curve outliers** — some players defy age curves (LeBron, Curry); how do models handle outliers?
- **Jersey retirement / ceremonial nights** — noise but flagged for completeness
- **First game post-trade-deadline leaguewide** — systemic volatility; is there a league-level regime shift?
- **In-game coaching adjustments** — not pre-game, but affects how well pre-game projections hold

Add your own: what meta-questions should I have asked that I didn't?

---

## 14. Format and style for the output

- Long-form markdown. Aim for 30-60 pages. If it's shorter than 30, you didn't cover the taxonomy.
- Use tables for comparisons, bullets only when listing items, prose for analysis.
- Every non-obvious claim: citation (`[source name](url)`) or "hypothesis, unconfirmed."
- Do not flatter. Do not preamble. Do not summarize the question back to me.
- If two sources conflict, say so, state your best-judgment call, and give the reasoning.
- If a domain has no rigorous public evidence, SAY SO. Don't fabricate confidence.
- If a factor sounds important but evidence is weak, say so and rank it accordingly.
- Include exact URLs / endpoints wherever possible, not just source names.
- Code samples in SQL or Python are encouraged where they clarify implementation.
- Every recommendation names its **debuggability cost** — clean, opaque, or black-box.
- Every section ends with a one-line "builder's takeaway" — what I should do about this section.

---

## 15. What "done" looks like

The report is done when I can:

1. Read §1 Executive summary and know the top 15 things to build next, in order, with expected CLV magnitude
2. Compare my current per-minute × minutes architecture against 5+ alternatives (§3) with a reasoned recommendation
3. Understand minutes prediction as its own subproblem with its own research thread (§4)
4. Know per-stat specifics for PTS, REB, AST, 3PM, STL, BLK, TO, MIN (§5)
5. Flip to any domain in §2 and find concrete implementation guidance with a public data source
6. Identify which factors are noise vs signal
7. Know specifically how to fix Concern 1 (injury accounting) and Concern 2 (team assignments) with cited methodology
8. Understand which factors I currently don't model that matter most (Concern 3)
9. Know the empirical-experiment design for any open research question (§8)
10. See what SaberSim is likely doing and what's replicable from public data (§10)
11. Have a red-team assessment (§9) that tells me where I might be wrong
12. See in §11 the factors I didn't know to ask about
13. Have a known-unknowns checklist (§12) that becomes my next-experiment backlog
14. Be able to hand the report to a future engineer and have them understand both what to build and what to NOT build

---

## 16. Current engine context (for calibration, not scope)

I already have:
- A working custom engine: `engine/nba_projector.py` with EWMA per-minute rates, blended L5-median + season-healthy-mean minutes baseline, opponent-matchup factor (team-level, not per-position), pace factor from Vegas total
- A SQLite DB (`data/projections.db`) with 3+ seasons of nba_api PlayerGameLogs (~79k+ rows), plus separate injury_status table (OUT / Q / P / D / ACTIVE)
- Backtest harness producing per-bucket MAE and bias
- Current state (Phase 2 root-cause hypotheses in flight): PTS MAE 5.036 (target ≤5.0), starter MIN bias -1.693, <15 min bucket bias -9.3 (players projected sub-15 actually play ~24 min because of late injury absorption — largely unmodelable from pre-game data alone)
- Phase 2 root-cause plan at `memory/projects/custom-projection-engine-phase2-root-cause.md`

I am NOT looking for a review of my current engine. I am looking for a comprehensive map of the entire projection problem so I know what to build toward. The research should be engine-agnostic — assume a greenfield rebuild informed by every factor that matters.

---

## 17. Final hard rules — do not violate

- Public data only (premium noted, not relied on)
- Mechanism-first, not ML-black-box
- No band-aids — every proposed feature must have a named causal justification
- CLV (vs SaberSim over 100+ graded bets) is the real gate, not MAE
- Debuggability is required; every recommendation names its cost
- Non-goals are non-goals — do not scope-creep into playoffs, live, DFS, non-NBA
- Mention premium tools only if clearly superior, and always propose a public proxy
- If my taxonomy missed something, add it — don't just validate what I wrote
- Be ruthless about noise — most projection-blog factors are overrated
- Quantify magnitudes wherever possible; when you can't, say so explicitly
- Do not flatter; do not preamble; do not recap the question back to me
- Every section must end in something I can implement or measure
- §12 Known-unknowns checklist is mandatory. If you can't fill it with 10+ items, you aren't trying hard enough

**The goal is CLV-positive NBA prop projections that beat a $197/mo SaberSim subscription using public data. Every word of this report should serve that goal.**
