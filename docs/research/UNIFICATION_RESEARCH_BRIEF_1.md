# Deep Research Brief #1 — Unifying a Multi-Source Sports Projection → Pricing System

> Stage 1 of 2. This brief researches **WHAT the correct unified structure is** (principles, patterns,
> options, tradeoffs, metrics). A follow-up brief will research **HOW to implement** the findings.
> Paste everything below into a deep-research session.

---

## YOUR ROLE
You are a senior quantitative systems architect with expertise in sports-betting/quant-trading model
infrastructure, probabilistic forecasting, model calibration, and ML model deployment. Research and
synthesize the **correct, evidence-based architecture** for the system described below. Cite sources,
distinguish well-established results from speculation, and be concrete and decision-oriented.

## OBJECTIVE
We run a live sports-betting modeling system and need to **unify two projection sources behind a single
contract** so our in-house model can progressively, safely, and **measurably** take over from a
third-party source — **per market, in parallel, across four sports** — without forking the pricing code,
without duplicating calibration math, and without disrupting a live nightly pipeline. Determine WHAT the
right structure is.

> **Scope boundary:** this brief is about the **unification architecture** only — the contract between
> projection and pricing, the multi-source resolver, readiness-gated handover, calibration-as-single-
> source-of-truth, and migration. The **correctness of the pricing methodology itself** (which
> distribution per market, how to set dispersion, how to decompose sub-period markets like first-5-innings,
> which calibration method) is a **separate research prompt** and is out of scope here. Implementation
> specifics are also a separate, later step.

## SYSTEM CONTEXT (the concrete setup you are advising on)
- **Two components:**
  - **PRODUCER** ("EdgeModel"): builds statistical projections from historical data — player stat lines
    (e.g. points/rebounds/assists/threes; hits/strikeouts/total-bases) and team score/run expectations.
    It is **maturing**. It writes a projections store consumed downstream, and it already keeps its own
    calibration logic for self-checking.
  - **CONSUMER / PRICER** ("JonnyParlay"): reads projections, converts them into **bet probabilities**
    (P(stat > line), win probability), compares to sportsbook odds to compute **edge**, sizes stakes
    (Kelly), places/logs/grades bets, and tracks **closing line value (CLV)**.
- **A third-party projection provider** ("SaberSim", a DFS projection service) is currently used as a
  **placeholder projection source** for markets/sports where the in-house producer is not yet mature.
  The intent is to replace it **per market** as the producer proves out.
- **Markets** span **player props** (points, rebounds, assists, threes; hits, strikeouts, total bases,
  etc.) **and game lines** (moneyline, spread/run-line, totals, team totals, and baseball
  **first-5-innings [F5]**).
- **Sports:** baseball (MLB), women's basketball (WNBA), men's basketball (NBA), hockey (NHL) — they are
  structurally very different (MLB has starting pitchers + innings + F5 sub-markets; basketball has
  minutes/pace; hockey has goalies/special teams).
- **Known pain points (already diagnosed):**
  1. The two sources are wired in **different places** (in-house for some props; third-party for game
     lines), with **no central place to select or blend** a source per market — so the handover cannot be
     managed or measured.
  2. The probability/calibration math is **duplicated** across the producer and the consumer (the producer
     keeps a mirror copy to self-calibrate / shadow-log), causing **"lockstep drift"** whenever one side
     changes a constant.
  3. Game lines **bypass the in-house model entirely** and re-derive from the third-party source — even
     though the in-house model already produces a (better, starting-pitcher-aware) game-line projection
     that currently goes **unused**.
  4. There is a **determinism / "replay" gate** (the pipeline must reproduce identical output) and a live
     **nightly batch run** that must not break during migration.
  5. There is a large archive of **graded historical outcomes** for backtesting (e.g. ~8,500 final MLB
     game scores over 3+ seasons), plus per-bet results and CLV history.
  6. There are currently **multiple divergent implementations of the same pricing** — e.g. three separate
     game-line pricers — and the one that actually generates the live/graded bets **lacks the
     market-anchoring blend and probability shrink** that the main pipeline path applies, making it the
     most overconfident and most CLV-negative variant. These must be **collapsed into one** canonical
     engine.
  7. The third-party source is **bundled**: a single CSV supplies the slate, player universe, salaries,
     *and* projections together. So "taking over projections" must be **untangled** from the slate /
     market-data role that source also plays.
- **Operating reality:** a **single technical operator** running a nightly **Python + SQLite** batch
  system. Favor robust, low-operational-overhead designs.

## CORE QUESTION
What is the correct architecture and set of best practices to **unify multiple projection sources behind a
single contract**, so the in-house model can take over from the third-party source **per-(sport, market),
in parallel, gated by objective readiness metrics** — without forking the pricing/betting code, without
duplicating calibration math, and without disrupting the live pipeline?

---

## RESEARCH QUESTIONS
Be exhaustive. For each, give evidence, the realistic options, their tradeoffs, and a clear recommendation.

### A. Projection ↔ Pricing separation
1. How do professional sports-betting / quant-trading operations separate the **forecasting/projection**
   layer from the **pricing/edge/execution** layer? What is the canonical interface/contract between them?
2. What should a projection **emit** to be pricing-ready across many markets: a point estimate, a full
   predictive distribution, distribution parameters (mean + dispersion), quantiles, or Monte-Carlo
   samples? What **granularity** (per player-stat, per team, per game, per market)? How should
   **correlations** be represented (needed for parlays / same-game / total-vs-sides consistency)?
3. Where should the **line-specific probability** (e.g. P(stat > line), P(team wins)) be computed — in the
   producer, the consumer, or a shared layer — and why?

### B. Multi-source abstraction & blending
4. Best-practice patterns for a **"projection provider" abstraction** with multiple interchangeable
   sources (in-house + third-party): adapter/strategy/registry patterns and how this is structured in
   practice.
5. **Hard cutover** (one source wins per market) vs **ensemble/blend** (weighted combination). When does
   blending beat switching? Methods (inverse-variance weighting, stacking/super-learner, Bayesian model
   averaging, optimal linear pools) and the evidence that **forecast combination** beats the single best
   forecast.
6. How to **normalize heterogeneous sources** onto one schema when one is a black-box DFS projection and
   the other a custom probabilistic model — reconciling units, distributional assumptions, dispersion, and
   missing/asymmetric fields.

### C. Readiness gating / model promotion
7. How to decide **objectively** when a new model is ready to replace or blend with an incumbent for a
   given market. Proper scoring rules for probabilistic forecasts (log loss, Brier, **CRPS**, ranked
   probability score), calibration metrics (**ECE**, reliability diagrams), and point metrics
   (MAE/RMSE/bias) — which apply to which market type, and recommended **thresholds, sample sizes, and
   significance tests**.
8. **Champion/challenger, shadow/canary deployment, and A/B testing for predictive models** — promotion
   gates, guardrails, automatic rollback. How "shadow mode" should be structured for forecasts.
9. In betting specifically: the role of **Closing Line Value (CLV)** as the gold-standard out-of-sample
   signal. How to weigh CLV vs realized W/L vs proper scoring rules when judging a model, and the pitfalls
   (variance, sample size, differing market efficiency by sport/market).

### D. Calibration as a single source of truth
10. Why **duplicated** probability/calibration code across services causes drift, and the canonical
    patterns to **centralize** it (shared library vs service vs config-as-data). Where calibration
    parameters should live and how to **version** them.
11. How should calibration parameters be **stored, versioned, and refreshed** so the producer and consumer
    always use **identical** values (eliminating the lockstep-drift failure)? (*Which* calibration method
    is correct is out of scope — that's the separate pricing-methodology research.)

### E. The data/interface contract & topology
12. Patterns for the **producer→consumer handoff**: shared database/file vs API vs message queue vs shared
    package. Tradeoffs for a single-operator nightly-batch system. **Contract/schema versioning**,
    backward compatibility, freshness/staleness handling, partial coverage + fallback.
13. How to represent **"this market is covered by source X today"** as data (a capability/coverage
    manifest) and resolve it at request time.

### F. Cross-sport generalization
14. How to design **one** projection contract that generalizes across sports with very different structure
    (MLB pitchers/innings/F5; basketball minutes/pace; hockey goalies) and across props vs game lines —
    **without per-sport forks**. Where sport-specific logic belongs vs shared.
15. Should the projection **contract itself** need to express sub-period structure (e.g. inning/period
    splits, or starter-vs-bullpen components) so that derived markets can be priced downstream — or is that
    purely the pricer's concern? **Concrete motivating case:** our baseball first-5-innings (F5) market is
    currently priced by pro-rating the full game by a flat fraction, which ignores that the **starter
    throws nearly all of F5**; whether the contract should carry a starter-vs-bullpen / inning split is
    what would let the pricer fix that downstream. (The *modeling formula* for F5 is the separate
    pricing-methodology research; here we only decide what the **contract** must expose.)

### G. Validation / backtesting harness
16. How to build a **leakage-free, point-in-time-correct backtest** that fairly compares projection
    sources against historical outcomes: proper scoring, walk-forward/rolling validation, avoiding
    look-ahead and overfitting, and handling season/regime changes.
17. **Continuous live calibration monitoring and drift detection** for an in-production forecasting system.

### H. Operational & migration
18. How to run a **per-market migration in parallel** (some markets in-house, some third-party) without
    disrupting a live nightly pipeline — feature-flag/config patterns, safe rollout, observability, and
    preserving **reproducibility/determinism**.
19. **Anti-patterns and failure modes** specific to dual-source forecasting + betting systems; transferable
    lessons from quant-finance "signal vs execution" separation and from ML model-deployment literature.

### J. Code-path consolidation, separation of concerns & provenance
20. We have **multiple divergent implementations of the same pricing** (e.g. three game-line pricers with
    different parameters and market-anchoring). How should duplicate/divergent pricing logic be
    **consolidated into one canonical engine** that every entry point (live picks, analyzers, backtests)
    calls — and what patterns prevent it re-diverging over time?
21. The third-party source supplies the **slate, player universe, salaries, AND projections bundled in one
    feed**. How should the architecture **separate the concerns** — (i) slate / market-data ingestion,
    (ii) projection, (iii) pricing — so the in-house model can take over *projection* per market while the
    slate/market layer stays stable? What should remain with the third-party source vs move in-house?
22. **Provenance / lineage:** what must be recorded per projection and per bet (source identity, model
    version, input snapshot) so source performance can be **compared retrospectively** and readiness gates
    can be evaluated *at all*? How should shadow / champion-challenger logging be instrumented so the
    comparison is possible from day one (not reconstructed later)?
23. **Data sufficiency for gates:** how much graded/outcome data is needed per market to make a sound
    readiness decision, and what should be done for markets that are **currently too thin to validate** —
    re-derive history from raw outcomes, accrue in shadow, or hold on the incumbent? How to avoid declaring
    a market "ready" on an underpowered sample.

### I. Synthesis
24. Given all the above, what is the recommended **target architecture** for this system (a concrete,
    opinionated design), and what are the **2–3 highest-risk decisions** where the evidence is mixed?

---

## DELIVERABLE FORMAT (please return)
1. **Executive summary** — the recommended architecture in ~1 page.
2. **A section per topic A–J** answering the questions with evidence, options, tradeoffs, and a clear
   recommendation.
3. A recommended **projection contract** spec — the fields/shape a projection should expose to be
   pricing-ready across all four sports and both market families.
4. A recommended **source-resolver + readiness-gate** design — metrics, thresholds, promotion/rollback
   rules.
5. A recommended **calibration consolidation** approach (single source of truth).
6. A **migration strategy** (parallel, readiness-gated) that preserves a live nightly pipeline.
7. A **risks & open questions** list, plus a concise **annotated bibliography** prioritizing rigorous
   sources (academic forecasting/ML, quant finance, sports analytics, sportsbook/market-making
   literature, reputable practitioner writeups). Clearly separate established results from speculation.

## GROUND RULES
- Cite sources for non-obvious claims; explicitly flag where evidence is thin or contested.
- Prefer principles that **generalize across all four sports and both market families** (props + game lines).
- Be concrete and decision-oriented, not generic. When you recommend something, state the conditions under
  which the recommendation would change.
- Assume a **single operator** on a **nightly Python/SQLite batch** system — favor robust, low-overhead
  designs over heavyweight infrastructure.
