# Deep Research Brief #2 — Implementing the Unified Projection→Pricing Architecture in a Two-Repo, SQLite, Nightly-Batch Betting System

> Stage 2 of 2. Stage 1 researched WHAT the target architecture is (now **decided** — summarized below as GIVEN).
> This brief researches HOW to implement it correctly in our concrete stack without breaking a live nightly
> betting pipeline. Run in Claude deep research (Opus 4.8, max effort, extended thinking).

## YOUR ROLE
You are a senior software architect specializing in production refactors of live, money-handling batch
systems, ML/forecasting deployment, Python packaging, and deterministic/reproducible pipelines. Research the
correct, evidence-based way to IMPLEMENT the architecture below in the specific stack described. Cite
patterns/sources, be concrete and decision-oriented, and flag where evidence is thin.

## DECIDED ARCHITECTURE (from Stage-1 research — treat as GIVEN; do NOT relitigate)
- A thin, **versioned Projection Contract** between producer and consumer: one row per (entity, market)
  emitting compact **distribution parameters** (family + mean + dispersion) by default; optional **sub-period
  component distributions** (e.g. starter/bullpen, innings_1-5/full-game) where the source can produce them;
  escalate to **Monte-Carlo samples or an explicit copula spec ONLY** for correlated / same-game markets.
- **One canonical pricing engine** ((distribution, line, calibration_version, market-anchoring config) →
  probability/edge) that EVERY entry point calls. The three divergent game-line pricers collapse into it,
  with market-anchoring blend + probability shrink as **mandatory** parameters.
- A **shared library** is the ONLY implementation of distribution→probability and calibration application.
  Calibration parameters are stored as **versioned config-as-data** keyed by (sport, market, version,
  valid-from), append-only (refit writes a new version).
- **Adapter + Registry**: a `ProjectionProvider` interface; `EdgeModelAdapter` + `SaberSimAdapter`; a
  **`coverage_manifest`** (date, sport, market, source, mode∈{live,shadow,blend}, weight, calibration_version)
  read by a **resolver** at request time.
- **Readiness-gated BLEND, not binary cutover, during maturation:** PRIMARY gate = proper scoring (CRPS for
  continuous, log loss/Brier for binary) + calibration (ECE) on walk-forward, purged samples; **CLV =
  confirmatory veto** (freeze-and-flag on calibration/CLV disagreement). Blend weight ramps as a
  deterministic, non-overfit, **shrunk-toward-incumbent** function of accuracy-advantage confidence, behind a
  **minimum-sample precondition**. Binary cutover only at decisive, powered superiority.
- **Champion/challenger + shadow logging from day one**; **provenance/lineage** logged per projection and per
  bet. **Separate the bundled feed**: an ingestion adapter writes `slate` (games/players/salaries) and
  `projections(source=...)` separately; the slate layer stays third-party. Preserve **determinism/replay**;
  migrate per-market behind manifest feature-flags.

## OUR CONCRETE STACK (the implementation target)
- **Two separate git repos.** EdgeModel (producer: builds projections; Python; writes `projections.db`,
  SQLite ~16MB) and JonnyParlay (consumer: pricing/sizing/betting/grading/CLV; Python). Today they
  communicate via `projections.db` (EdgeModel writes; JonnyParlay reads via `EDGEMODEL_DB_PATH`). The
  probability/calibration math is currently **DUPLICATED** across both (EdgeModel keeps a mirror for
  shadow/self-calibration; JonnyParlay has `prob_core`/`calibrated` for live) → active **lockstep drift**.
- **SQLite** data store + CSV pick-logs. **Single technical operator**, Windows, **nightly batch** (no
  service/queue/cloud infra).
- **Byte-identical replay/determinism gate:** a replay harness re-runs a frozen slate and requires
  **identical** output. This currently gates every change.
- **Existing pick-log schema** (`pick_log.csv` / `pick_log_calibration.csv` / `pick_log_game_lines.csv` + a
  `pick_log` DB table) already logs picks/results/CLV with some **frozen** columns. It must be **EXTENDED,
  not forked**.
- **Three divergent game-line pricers today:** `analyze_game_lines.py` (standalone; generates the graded
  bets; lacks market-anchoring + shrink), `engine/evaluators.py` (the anchored path), and
  EdgeModel `engine/mlb_game_lines.py` (starter-aware; writes `mlb_game_projections` — currently read by
  nothing).
- **CLV pipeline is thin and fragile:** only dozens of CLV rows; captured by a daemon (`capture_clv.py`) that
  has had reliability problems; closing reference = the Odds API.
- **Four sports** (MLB, WNBA, NBA, NHL); **player props** (larger volume; partly already on EdgeModel) +
  **game lines** (currently SaberSim-derived).
- **~8,500 graded MLB final scores** (3+ seasons) for backtest/backfill; F5/inning truth must be backfilled
  from the MLB Stats API by `game_pk`.

## CORE QUESTION
What is the correct, lowest-risk way to IMPLEMENT the decided architecture in this two-repo, SQLite,
nightly-batch, byte-identical-replay stack — the packaging, schemas, refactor sequence, determinism
preservation, gate/weight implementation, provenance, testing, and backfill — **without breaking the live
betting pipeline at any step**?

## RESEARCH QUESTIONS

### 1. Two-repo shared-library packaging (the central question)
The architecture needs ONE shared pricing/calibration library imported by BOTH repos. Given two separate git
repos and a single operator, what is the correct way to share one library **without re-introducing drift**?
Compare concretely: a shared **installable Python package** (private index / editable install / wheel), a
**git submodule**, a **vendored copy + sync/hash check**, or **merging into a monorepo**. Tradeoffs for a
solo operator on Windows + nightly batch + a byte-identical replay gate. How should the shared-library
version be coordinated with the **contract schema version** and the **calibration-data version**? How to
migrate the currently-duplicated math into the shared library incrementally while both repos keep running.

### 2. Preserving the byte-identical replay/determinism gate
The Stage-1 research suggested *relative tolerance* on continuous values, but our gate is **byte-identical**.
Can byte-identical be preserved given: closed-form parameter emission (no RNG), a nightly weight-ramp
computed from logged metrics, probability-level blending, and SQLite float aggregation order? What concretely
is required — sorted aggregations, fixed serialization/rounding policy, no dict-iteration-order dependence,
pinned library versions, avoiding order-dependent float reductions? Where sampling/copulas are unavoidable
(correlated markets), how to keep replay deterministic (seed pinning/logging), and **should those markets be
exempted from byte-identical and moved to a tolerance gate**? Recommend a concrete determinism policy.

### 3. SQLite schema & contract implementation
Give concrete **DDL** for: the `projections` contract table (identity/provenance + parametric payload +
optional `components_json` + escalation refs), the `coverage_manifest`, the versioned `calibration_params`
table, and the provenance/lineage tables. Address SQLite specifics: JSON columns vs normalized rows,
indexing, nullability, and a **schema-version/migration strategy for SQLite** (which lacks rich `ALTER`). How
to evolve the EXISTING `projections.db` + pick-log schema into this **backward-compatibly** (additive
columns, views, shims) so current readers don't break.

### 4. Resolver & blend implementation
Concrete implementation of the resolver: read `coverage_manifest` → return the active source or a **blended
distribution** per market. **Probability-level vs parameter-level blending** — exact mechanics, and how
blending interacts with **same-game-parlay correlation** (do not blend legs independently and break the
copula). Specify a concrete, deterministic, non-overfit **weight-ramp function**: a recommended closed form
(e.g. weight as a capped/shrunk function of the standardized proper-score improvement with a per-night max
step), its inputs (all from logged metrics), and how to make it exactly replayable.

### 5. Readiness-gate & shadow-logging implementation
How to implement champion/challenger **shadow logging** in a nightly batch + the existing pick-log schema:
capture the challenger's would-be projection AND would-be bet for EVERY market every night, scored against
outcomes and against the champion. Exact fields to ADD (extending, not forking, the pick-log). Concrete batch
computation of the **primary gate** (rolling CRPS/Brier/log loss + ECE, walk-forward + purged) and the **CLV
confirmatory veto** (including the freeze-and-flag-on-disagreement logic).

### 6. Hardening the CLV input
Given a thin, fragile CLV pipeline and the Odds API as reference: how to obtain a **clean closing-line
reference** (no-vig, sharp book) reliably; how to accrue CLV with provenance; and how to weight CLV's
confirmatory role given current sparsity. What to do per market where **no clean close exists**. How robust
must the capture be before CLV is allowed any veto power.

### 7. Incremental refactor sequence without breaking live (strangler-fig / parallel run)
The correct application of the **strangler-fig pattern** + **parallel-run verification** to this refactor:
(1) collapse the three pricers, (2) introduce the contract + shared library, (3) split the bundled feed,
(4) stand up resolver+manifest, (5) instrument provenance/shadow, (6) per-market gated ramp. At each step,
how to verify equivalence (golden-master/characterization tests, parallel old-vs-new run diffing, the
determinism hash) **before** cutting over, and how to sequence so the nightly run never breaks. Where are the
dangerous steps and what's the rollback for each?

### 8. Backfill & validation harness
How to backfill thin markets **point-in-time-correctly**: re-derive historical projections from raw outcomes
(the ~8,500-game archive) and F5/inning truth from the MLB API by `game_pk`, without leakage; then score
sources walk-forward with **purging/embargo**. Concrete harness design on SQLite (storage, indexing, and how
to avoid look-ahead). Minimum graded-sample sizes per gate type before a market may begin ramping.

### 9. Testing & guardrails
The test strategy for a live-money system through this refactor: golden-master/characterization tests,
the determinism-hash gate, property-based tests for the pricing engine, parallel-run diffing, and **automated
rollback** wiring (manifest weight → incumbent) on calibration decay / CLV breach. How to test the resolver,
the weight function, and the shadow path specifically.

### 10. Synthesis
A concrete, sequenced **implementation plan** (milestones with verification gates), the recommended
packaging + determinism + schema decisions, and the **2–3 highest-risk implementation choices**.

## DELIVERABLE FORMAT
1. **Executive summary** — the recommended implementation approach in ~1 page.
2. **A section per question 1–9** with concrete recommendations, code/architecture patterns, and tradeoffs.
3. **Concrete artifacts:** proposed SQLite **DDL** for the new tables; the **shared-library packaging**
   recommendation; the **determinism policy**; the **weight-ramp function** spec; the **refactor step
   sequence** with per-step verification + rollback.
4. **Risks & open questions**, and an annotated bibliography (Python packaging/monorepo, strangler-fig &
   refactoring of live systems, MLOps shadow/champion-challenger, deterministic/reproducible pipelines,
   SQLite schema-migration specifics).

## GROUND RULES
- Take the Stage-1 architecture as **decided**; focus on HOW to build it **here**.
- Optimize for a **single operator on Windows + nightly batch + SQLite** — favor robust, low-overhead,
  low-ceremony solutions over enterprise infrastructure (no k8s/queues/feature-store products unless truly
  justified).
- Every recommendation must respect: **the live nightly run cannot break**; the **byte-identical replay
  gate**; the **existing pick-log schema (extend, don't fork)**; and that **frozen calibrated constants are
  not changed casually**.
- Cite patterns/sources; flag thin evidence; state the conditions under which each recommendation would change.
