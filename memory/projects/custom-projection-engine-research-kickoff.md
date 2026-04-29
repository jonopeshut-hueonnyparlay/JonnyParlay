# Custom Projection Engine — Deep Research Kickoff (2026-04-22)

**Paste this entire document into your research tool of choice (Claude Research, Perplexity Pro, Gemini Deep Research, or a Claude subagent with web_search). It is self-contained — do not edit.**

**The document is in three parts:**
- **Part A — Context primer.** Why this research is being commissioned RIGHT NOW, what's already been tested, and the specific failure pattern the research must explain.
- **Part B — The architectural pivot question.** The single decision the research output must resolve.
- **Part C — The research prompt proper.** The full exhaustive domain taxonomy and deliverable spec.

Parts A and B are additive context on top of Part C. Part C is the canonical prompt; A and B tell the researcher where we are in the journey and what fresh evidence must be explained.

---

# Part A — Context primer (what the researcher must know before starting)

## A.1. Where this engine is in its life cycle

- **Goal:** replace SaberSim ($197/mo) as the CSV input to an NBA props betting engine. CLV over 100+ graded bets vs SaberSim is the one true gate. MAE is a proxy.
- **Architecture (current):** per-minute-rate × minutes-baseline. Architecture A in Part C §6. This is a **greenfield-decision-point**, not a commitment. If the research concludes this architecture is the wrong shape for the problem, we will pivot before sinking more hypothesis-testing cycles into it.
- **Constraint:** public data only. NO band-aids. Every feature or change must be a bug fix, a causally-justified feature addition, or a scope correction.
- **Constraint:** debuggability is load-bearing. Black-box is disqualifying unless it beats a debuggable alternative by a margin that justifies the cost when we're on a cold streak and need to attribute the loss.

## A.2. Phase 1 result (pre-H1)

Full-season backtest (2025-10-22 → 2026-04-13, min_minutes=15, n=19,829 rows):

| Stat | MAE | Bias | Target | Status |
|------|-----|------|--------|--------|
| PTS | 5.036 | -0.619 | ≤5.0 | 0.036 over |
| REB | 2.046 | -0.166 | ≤2.5 | ✅ |
| AST | 1.509 | -0.107 | ≤2.0 | ✅ |
| 3PM | 1.008 | -0.076 | ≤1.5 | ✅ |
| MIN | 4.441 | **-0.877** | — | bias concern |

**Starter MIN bias -1.693. Bench MIN bias +2.641. <15 min projected bucket: MIN bias -9.305, PTS bias -4.325 (n=948).**

Pattern: classic regression-to-mean. Low-projected-minutes players outperform. High-projected-minutes players under-hit. Middle is nearly unbiased.

## A.3. H1 fix applied (2026-04-22)

**H1 hypothesis:** the minutes baseline includes DNP/rest/injury-restricted/ejection games, which drags the healthy-mean downward. Fix = filter the baseline to qualifying games only (minutes ≥ 15.0 used as the healthy-filter threshold across L5, L10, and season-mean components).

**Post-H1 full-season backtest:**

| Stat | MAE | Bias (Δ) | Target | Status |
|------|-----|----------|--------|--------|
| PTS | **4.995** | -0.331 | ≤5.0 | ✅ by 0.005 |
| REB | 2.047 | -0.013 | ≤2.5 | ✅ |
| AST | 1.509 | -0.038 | ≤2.0 | ✅ |
| 3PM | 1.009 | -0.040 | ≤1.5 | ✅ |
| MIN | 4.209 | -0.069 | — | overall bias collapsed |

### Post-H1 bucket table (THE KEY FAILURE PATTERN)

**Starter vs bench:**

| bucket | n | PTS_MAE | PTS_bias | MIN_bias |
|---|---|---|---|---|
| starter (actual ≥20 min) | 16,096 | 5.198 | -0.848 | **-1.144** |
| bench (actual <20 min) | 3,733 | 4.121 | +1.898 | **+4.565** |

**Projected-minutes bucket:**

| bucket | n | PTS_MAE | PTS_bias | MIN_bias |
|---|---|---|---|---|
| <15 | 115 | 5.655 | **-5.041** | **-12.619** |
| 15-20 | 2,213 | 4.041 | -1.577 | -2.427 |
| 20-25 | 5,523 | 4.395 | -0.856 | -0.704 |
| 25-30 | 5,664 | 4.997 | -0.235 | **+0.350** |
| 30-35 | 4,790 | 5.675 | +0.446 | +0.950 |
| 35+ | 1,524 | 6.360 | +0.939 | **+1.843** |

**Usage tier on team:**

| bucket | n | PTS_MAE | PTS_bias | MIN_bias |
|---|---|---|---|---|
| top3 | 7,971 | 5.663 | +0.139 | +0.684 |
| 4-6 | 7,254 | 4.776 | -0.493 | -0.313 |
| 7+ | 4,338 | 4.147 | -0.915 | -1.031 |

## A.4. What the residual pattern now says

1. **Starter undershoot persists** (MIN bias -1.144). H1 helped (was -1.693) but didn't kill it. The healthy-filter is partially working for starters but still missing something — possibly that coaches tighten rotations in April (pace of season), possibly opponent-closeness context, possibly foul-trouble / game-script features absent from the baseline.

2. **Bench overshoot got WORSE in apparent magnitude** (MIN bias +4.565 post-H1 vs +2.641 pre-H1). Pre-H1 the starter filter was "actual minutes ≥20"; the post-H1 slice redrew starter/bench with a different underlying filter. Magnitude aside, the **sign** is unchanged: bench players are systematically over-projected. Why? Hypothesis: the healthy-filter (min ≥ 15) that fixed starters actively BREAKS bench players — their few 15+ min games become the baseline, making them look like rotation regulars. The minutes-baseline × per-minute-rate structure has a **population-mismatch** failure: one filter threshold cannot serve both starters and bench.

3. **<15 projected-min bucket is catastrophic** (n=115, MIN bias -12.62). These are players projected to play ~10 min who actually play ~23. Two causes: (a) late injury-absorption of minutes the model didn't see pre-game (unmodelable from pre-game historical data — correctly scoped out via CSV filter), and (b) EWMA lag on recently-promoted players (potentially fixable with H2 or role-aware cold-start).

4. **35+ bucket overshoots by +1.8 MIN.** Heavy-starter over-projection persists. Candidate mechanism: garbage-time in blowouts, late-season load-management, foul-trouble.

5. **PTS MAE gate was hit by 0.005** — a near-miss dressed as a win. One noisy slice redo flips it.

## A.5. Why research is being commissioned now, not after H2-H8

The temptation is to continue the hypothesis march (H2: date-weighted EWMA; H3: spread-aware minutes; H4: opponent-specific rotation; etc.). Each H is a plausible patch to the existing architecture. But:

- H2-H8 all assume **the current architecture is salvageable**. If the residual pattern (starter undershoot + bench overshoot + <15 min catastrophe) is a **shape mismatch between per-minute-rate × minutes-baseline and the actual NBA-player-population distribution**, then H2-H8 are polishing the wrong model.
- Public NBA analytics may have already solved this. Volume × efficiency (Architecture B), per-possession (C), hierarchical Bayesian with role priors (F), shot-level (E), or ensemble (G) may be the right shape. We don't know — we haven't surveyed.
- Before spending 4-6 weeks grinding H2-H8, a research pass that evaluates **architecture** against this specific residual pattern can either (a) confirm the current shape is right and we continue with better-targeted hypotheses, or (b) tell us to pivot.
- The residuals are now **diagnosable**. Pre-H1 we had one blob (PTS MAE 5.036). Post-H1 we have a specific fingerprint. Research pointed at "why does per-minute-rate × minutes-baseline produce starter-undershoot + bench-overshoot + <15-min catastrophe" is tractable. Research pointed at "help me project NBA minutes" is not.

---

# Part B — The single architectural question the research must resolve

**Given the specific failure pattern in A.4, is the per-minute-rate × minutes-baseline architecture (Part C §6 Architecture A) salvageable with role-stratified minutes modeling and better per-minute features, or does the pattern indicate that a different architectural decomposition (volume × efficiency, per-possession, hierarchical Bayesian with role-aware priors, or ensemble) is structurally required to close the gap?**

The research output must take a position on this. Not "it depends" — a specific, evidence-backed recommendation: **stay, rebuild, or hybrid, with the specific failure-mode evidence that supports the call.**

If **stay**: name the 3-5 specific features/fixes on top of the current architecture that most plausibly address starter-undershoot + bench-overshoot + <15-min catastrophe, ranked by expected CLV impact.

If **rebuild**: name the target architecture, cite the public methodology reference, name the minimum-viable feature set to match current MAE before scaling, and estimate the engineering cost vs the expected CLV ceiling gain.

If **hybrid**: name the specific components to replace vs keep, and justify why the mixed architecture is more debuggable than a clean rebuild.

**This question goes at the top of the Executive Summary (§1) in your output.** Everything else in the research prompt (Part C below) is still required, but §1 must open with your architectural call.

---

# Part C — The research prompt proper

*(Canonical exhaustive prompt. Do not edit when pasting. The references to "my current engine" in §16 should be read in conjunction with A.1–A.4 above for latest state.)*

---

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

**Opens with the architectural call from Part B of this kickoff: stay / rebuild / hybrid, with specific failure-mode evidence.**

Then: top 15 highest-impact levers ranked by expected CLV contribution. Each lever gets: one-sentence mechanism, one-sentence evidence pointer with citation, expected MAE magnitude ("~0.4 PTS MAE reduction" vs "marginal <0.1"), implementation difficulty (trivial / moderate / hard), and **debuggability cost** (clean / opaque / black-box). Include a stoplight column: green = build now, yellow = build v2, red = research first.

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

Evaluate at least five candidate architectures against my use case — see §6 below for the canonical list. For each: what it models natively, what it approximates, what public implementations exist, debuggability cost, CLV implications. **This section must specifically address whether the post-H1 failure pattern described in Part A.4 of the kickoff indicates a shape mismatch in Architecture A vs a feature-level fix.**

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
- **Specific analysis of whether the architecture would produce the failure pattern observed in Part A.4 of the kickoff.** If Architecture A structurally produces starter-undershoot + bench-overshoot + <15-min-catastrophe, and Architecture B/F does not, name that clearly.

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
- **Role-stratified baseline construction.** Specifically address: if minutes-baseline is computed by filtering historical games (e.g. "games with min ≥ 15"), that filter is population-biased. Starter-shaped distributions survive the filter; bench-shaped distributions either get over-represented at their healthy upper tail (→ over-projection) or disappear. What's the published methodology for role-aware minutes baselines?

Deliverable for this section:
- A recommended architecture for the MIN projection (separate from the rate models)
- Named public sources for rotation / minutes prediction
- Benchmark MAE for minutes projection (what's state of the art publicly?)
- A sensitivity analysis: "if we improved MIN MAE from X to Y, how much does PTS MAE improve downstream?"
- **Explicit answer on the role-stratified baseline question above, with at least one cited methodology.**

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

*(The full taxonomy is in the parent research prompt file at `memory/projects/custom-projection-engine-deep-research-prompt.md`. When pasting this kickoff as a single prompt into an external research tool, inline the full §10 A–Z taxonomy by copying that file section here. Domains covered: A Data quality/identity/provenance, B Player static features + archetype clustering, C Player dynamic features + rookie cold-start, D Role & usage + usage-efficiency tradeoff, E Teammate/lineup + absorption hierarchy, F Coaching/tactical, G Opponent defense, H Opponent offense, I Game context, J Pace/possessions/garbage time, K Officiating, L Physical/biomechanical, M Mental/psychological, N Market-derived + Pinnacle reference, O Statistical modeling choices + volume×efficiency, P Uncertainty quantification, Q Live ops, R Betting translation, S Infrastructure, T Failure modes, U Era-specific / rule-change, V Source quality, W Calibration + public MAE benchmarks, X Ensemble/meta, Y Edge cases, Z Meta.)*

---

## 11. Sources to consult, 12. Red-team questions, 13. Meta, 14. Format, 15. Done-state

*(Inline sections 11–15 from the parent prompt file when pasting externally. Cover: public NBA analytics projection models, SaberSim teardown sources, NBA-specific writeups, betting-specific sources, statistical/methodological, concern-specific, data source URLs, open-source libraries, red-team questions on MAE floor and market efficiency, meta-question probe, formatting rules, done-state checklist.)*

---

## 16. Current engine context (for calibration, not scope)

*(Replace the parent prompt's §16 content with Part A.1–A.4 of this kickoff — those sections already contain the current engine state and post-H1 failure pattern. The researcher should read Parts A and B first, then process Part C top to bottom.)*

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
- **§1 must open with the architectural call from Part B of the kickoff. No burying the lede.**

**The goal is CLV-positive NBA prop projections that beat a $197/mo SaberSim subscription using public data. Every word of this report should serve that goal.**

---

# How to actually kick this off

The kickoff file above is split intentionally — Parts A and B are the fresh context, Part C is the canonical prompt with §10–§16 abbreviated to references back to the parent prompt file.

**Two kickoff modes depending on your research tool:**

**Mode 1 — single-paste (Perplexity / Gemini Deep Research / Claude Research with no file access):**
Assemble a single monolithic prompt by concatenating, in order:
1. This file's Part A and Part B (verbatim)
2. The full contents of `memory/projects/custom-projection-engine-deep-research-prompt.md` (the parent prompt with complete §10–§16 taxonomy inline)

Paste as a single message. Expect a 30-60 page markdown report back.

**Mode 2 — file-aware agent (Claude Research with tool access, or a Claude subagent):**
Attach both files:
- `memory/projects/custom-projection-engine-research-kickoff.md` (this file)
- `memory/projects/custom-projection-engine-deep-research-prompt.md` (parent prompt)

Instruct the agent to read the kickoff first for context, then process the parent prompt as the canonical spec, and answer Part B's architectural question at the top of §1.

---

# What to do with the output

1. Read §1 first. If the research says "rebuild" and the target architecture has credible public implementations with better structural handling of the current failure pattern → write a pivot memo, pause H2-H8, scope the rebuild.
2. If the research says "stay" → extract the 3-5 top features named for Architecture A improvements, turn them into H2'-H8' (replacing the old H list), continue the hypothesis march with better-targeted work.
3. If the research says "hybrid" → identify the component to swap (most likely: swap minutes-baseline for a role-stratified or hierarchical model, keep per-minute rates) and scope that as a focused sub-project.
4. Regardless: §12 (Known-unknowns checklist) becomes the immediate next-experiment backlog. Items there get prioritized by CLV-lift estimate and scheduled.
5. §10 SaberSim teardown feeds directly into the shadow-mode comparison once we're CLV-tracking both engines in parallel.
