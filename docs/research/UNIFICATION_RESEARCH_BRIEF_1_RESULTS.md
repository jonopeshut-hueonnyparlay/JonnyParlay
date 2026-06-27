# Stage-1 Research Results — Unification Architecture (DECIDED)

> Output of the Claude deep-research run on `UNIFICATION_RESEARCH_BRIEF_1.md` (2026-06-26).
> This is the **decided** target architecture. Stage-2 (`UNIFICATION_RESEARCH_BRIEF_2.md`) researches how to
> implement it. Reviewed + endorsed by Claude Code; thin spots flagged below feed Brief 2.

## TL;DR (verdict)
- **Thin versioned Projection Contract** between EdgeModel (producer) and JonnyParlay (consumer): emit
  compact **distribution parameters** (family + mean + dispersion) per market by default; escalate to MC
  samples / explicit copula spec ONLY for correlated / same-game markets. Resolve the active source per
  (sport, market) at request time via a **coverage manifest**, and **collapse the three divergent pricers
  into one canonical engine** every entry point calls.
- **Readiness-gated BLEND, not binary cutover, during maturation:** proper scoring (log loss / Brier / CRPS)
  + calibration (ECE) are the **PRIMARY** promotion gate; **CLV is a MANDATORY confirmatory signal**. Blend
  weight ramps as a shrinkage-controlled function of accuracy-confidence — the structure that resolves the
  problem that calibration is provable on a thin sample while CLV needs far more bets to confirm.
- **Centralize all probability/calibration math in ONE shared library** with calibration parameters stored
  as **versioned config-as-data**, so producer and consumer can never drift. Preserve determinism via
  closed-form parameters, output hashing for the replay gate, and per-market migration behind feature flags
  with full provenance logging from day one.

## Key findings
1. **Forecast combination usually beats the single best forecast** (Bates & Granger 1969; confirmed across
   M-competitions) — supports blend over cutover during maturation. Caveat: the **"forecast combination
   puzzle"** — estimated optimal weights are often beaten by simple averages due to finite-sample error.
2. The blend-weight decision resolves in favor of a **gated blend during the transition**, because of the
   calibration/CLV timing mismatch (calibration superiority is demonstrable on a thin sample long before CLV
   is conclusive).
3. **CLV is ~10× more statistically efficient than realized P&L** (per-bet SD ~0.1 vs ~1.0) — significance in
   far fewer bets — but it is reference-dependent and misleads against soft books or for a novel
   "odds-originator" model the market hasn't absorbed.
4. **Calibration superiority and CLV can diverge** (different references: realized outcomes vs the sharp
   closing price). A first-class design concern, not an edge case.
5. **Compact distribution parameters give closed-form line probabilities and are deterministic** — satisfies
   byte-identical replay far better than MC samples; reserve samples/copulas for genuinely joint markets.
6. **Duplicated probability/calibration code → "lockstep drift"**; canonical fix is one shared library +
   versioned calibration params as data.
7. **Champion/challenger with shadow logging** is the standard pattern for safe, measurable handover; maps
   directly onto a single-operator nightly batch.

## A. Projection ↔ Pricing separation
- **Canonical interface:** mirror the quant stack — EdgeModel = Alpha/signal layer ("what will happen");
  JonnyParlay = pricing + portfolio construction + execution ("what's it worth, what do I do"). The contract
  is that boundary; it's the single most important structural decision.
- **What a projection emits:** a predictive distribution as compactly as the market allows + provenance —
  NOT a bare point estimate (a point estimate forces the consumer to re-introduce dispersion = how
  calibration leaked into the consumer). Default = parameters (closed-form line probs, tiny, byte-repro).
- **Where line-probability is computed:** in the **shared pricing engine**, not the producer, not duplicated
  in the consumer. Producer stops carrying a mirror; it calls the same shared library in shadow mode. One
  code path from distribution→probability.

## B. Multi-source abstraction & blending
- **Provider abstraction:** Adapter + Registry/Strategy — one `ProjectionProvider` interface;
  `EdgeModelAdapter` + `SaberSimAdapter`; resolver keyed by (sport, market). Each adapter normalizes its
  source onto the contract; translate source errors into domain errors at the boundary.
- **Blend vs cutover (pressure-tested):** combination generally beats single-best, BUT the combination puzzle
  says simple equal-weights often beat estimated-optimal weights. Bias–variance framing → **optimal weights
  SHRUNK toward equal weights**. Verdict: **gated blend wins DURING maturation** (resolves the calibration/CLV
  timing problem by moving weight ∝ confidence); **binary cutover** is the terminal state once decisively
  superior; **static equal-weight ensemble** is the robust fallback / shrink target.
- **Normalizing SaberSim (sim-based DFS, point + ceiling in a bundled CSV):** the adapter maps to
  (family, mean, dispersion); where SaberSim gives only a mean, dispersion must come from the **shared
  calibration library (config-as-data), NOT invented in the adapter**. Missing markets → not registered in
  the coverage manifest.

## C. Readiness gating / promotion
- **Metrics:** continuous player-stat markets → **CRPS** primary (+ MAE/RMSE/bias diagnostics); binary/line
  markets → **log loss + Brier + ECE/reliability**; multi-outcome → ranked probability score. Calibration >
  accuracy for betting (Kelly only behaves with calibrated probs; Walsh & Joshi: +34.69% vs −35.17% ROI
  selecting by calibration vs accuracy).
- **Champion/challenger + shadow:** champion serves live bets; challenger runs in shadow on identical inputs,
  logged + scored, not acted on. Promote only on the gate; guardrails auto-rollback. Maps to nightly batch:
  both sources project every market nightly; resolver decides which drives real bets; other logged in shadow.
- **CLV vs calibration (the central interaction):** they measure vs different references (realized outcomes
  vs sharp close). A model can be calibration-better yet CLV-negative (calibrated to wrong reference / value
  only on stale lines), or CLV-positive yet poorly calibrated. **Odds-originator exception:** a genuinely
  superior novel model can show zero/negative CLV initially. CLV is ~10× more efficient than P&L (~50–65 bets
  vs thousands) but needs a clean sharp reference. **Resolution:** move blend weight ∝ accumulated **accuracy**
  evidence (shrunk toward incumbent); use **CLV as a confirmatory veto** — block further ramp + flag whenever
  calibration and CLV disagree on a meaningful sample. Never require CLV to clear a significance bar it's too
  underpowered to reach early.

## D. Calibration as single source of truth
- One shared library is the ONLY distribution→probability + calibration implementation. Calibration params =
  **versioned config-as-data** keyed by (sport, market, version, valid-from), content-hashed, **append-only**
  (refit writes a new version). Producer self-checks + consumer pricing read the **same row**. (Eliminates
  train/serve skew, like a feature store.)

## E. Data/interface contract & topology
- **Handoff:** for a solo nightly SQLite system → a **shared store (SQLite/Parquet) governed by an explicit
  versioned data contract**, NOT API/queue. Specify schema/types/nullability/units/semantics + schema
  version; dropping/renaming a required field = breaking change → version bump. `as_of` timestamp + max-age
  for freshness; manifest + incumbent fallback for partial coverage.
- **Coverage manifest:** data not code — `coverage_manifest(date, sport, market, source, mode∈{live,shadow,
  blend}, weight, calibration_version)`. Resolver reads it at request time. Per-market migration = a data
  edit.

## F. Cross-sport generalization
- One contract because it's about **distributions over outcomes, not sport mechanics**. Sport-specific logic
  (minutes/pace, goalie, pitcher/innings) lives **inside producer/adapters**, never in the contract or pricer.
- **Sub-period structure (F5):** contract **optionally** exposes named **component distributions** (e.g.
  `starter`/`bullpen`, `innings_1_5`/`full_game`). That's what lets the pricer fix the F5 flaw downstream
  (flat-fraction pro-rating ignores that the starter throws ~all of F5). Contract only EXPOSES the split;
  the F5 modeling formula is the separate pricing-methodology track. Sources that can't produce it omit it →
  pricer falls back.

## G. Validation / backtesting
- **Walk-forward + strict point-in-time** inputs; López de Prado **purged & embargoed CV** (and Combinatorial
  Purged CV) to remove leakage and get a distribution of OOS estimates (PBO / Deflated Sharpe). ~8,500-game
  MLB archive supports robust game-line evaluation; thin markets don't.
- **Live monitoring:** rolling ECE, rolling proper-score deltas vs incumbent, input drift (PSI/KL,
  missingness); alert + feed back into the resolver (auto-demote on decay).

## H. Operational & migration
- **Parallel per-market migration** driven by the coverage manifest (feature-flags-as-data); migration = manifest
  edits, never code forks. **Determinism:** closed-form params (no RNG) where possible; pin+log seeds where
  sampling is unavoidable; hash nightly output (SHA-256 over serialized log) and compare across replays
  (byte-identical for counts/timestamps, tight tolerance for continuous). **SQLite risk:** float aggregation
  order — sort inputs to aggregations.
- **Anti-patterns:** duplicated math → lockstep drift; the overconfident pricer (no anchoring/shrink) →
  CLV-negative + Kelly overbet ruin (fractional Kelly is the cure); promoting on underpowered CLV (or the
  odds-originator trap of refusing to); estimated-weight overfitting → shrink to simple; bundled-feed coupling.

## J. Consolidation, separation of concerns & provenance
- **Collapse 3 pricers → 1 engine** every entry point imports; market-anchoring + shrink become
  **non-optional params**. Prevent re-divergence: delete (not deprecate) the others; one public entry;
  golden-master tests; determinism hash gate. **Do this first — the live/graded pricer is the worst variant
  and is actively costing CLV.**
- **Untangle the bundled feed:** ingestion adapter writes a `slate` table (games/players/salaries) AND a
  `projections` table tagged `source=...`, separately. Slate stays third-party; projections migrate per market.
- **Provenance from day one:** per projection — source, model/calibration version, input snapshot hash,
  as_of, params. Per bet — which projection(s) + blend weights, calibration version, line + closing line,
  stake, grade. Shadow logging captures the challenger's would-be projection + bet every market every night.
- **Data sufficiency:** accuracy/calibration gates need hundreds of graded outcomes (converge fast); CLV gates
  ~50–65 bets vs a clean close; ROI confirmation ~1,000–2,500+. Thin markets → re-derive history from raw
  outcomes, else accrue in shadow, else hold on incumbent. Encode a **minimum-sample precondition** before any
  ramp; shrinkage keeps early weight small.

## Recommended PROJECTION CONTRACT spec (row per entity×market)
- **Identity/provenance (always):** `as_of, sport, event_id, entity_id, market, source, model_version,
  calibration_version, input_snapshot_hash`.
- **Default payload:** `dist_family` (normal/poisson/negbinom/lognormal), `mean`, `dispersion`, optional
  `params_json`.
- **Optional sub-period:** `components_json` (named sub-distributions: starter/bullpen/innings_1_5/full_game).
- **Escalation (correlated only):** `samples_ref` (stored MC matrix + logged seed) OR `copula_spec`
  (marginals + correlation). Used only where joint outcomes matter.
- **Coverage/quality:** `is_covered`, `confidence`/`n_effective`, `staleness_max_age`.
- **Rule:** consumer never adds dispersion or re-derives probability locally — it calls the shared engine.

## Recommended RESOLVER + GATE
- Resolver reads `coverage_manifest`; returns a single source or a blended distribution. Prefer
  **probability-level blending** (price each source, combine by weight) over parameter-level. Default shrink
  target = incumbent (weight 0 → in-house at start).
- Gate: primary = rolling proper score + ECE (in-house vs incumbent, walk-forward + purged); **promotion
  precondition** = min graded count; **weight** = shrunk, capped, deterministic function of standardized
  proper-score improvement (from logged metrics only, max step per refresh, replayable); **CLV =
  confirmatory veto** (freeze + flag on disagreement); **rollback** = weight→incumbent on calibration decay /
  materially-negative CLV on a powered sample. Cutover only at decisive, powered superiority.

## Migration strategy (parallel, gated, replay-safe)
1. **Consolidate pricers first** (stops the CLV-negative path). 2. Contract + shared library; both sources
write `projections` via adapters; all prob math into the library. 3. Split bundled feed (slate vs
projections). 4. Coverage manifest + resolver (all markets incumbent-live, in-house-shadow). 5. Provenance +
shadow logging from night one. 6. Backfill thin markets from the archive. 7. Per-market gated ramp. 8. Cutover
per market at decisive accuracy + CLV-neutrality.

## Highest-risk decisions / caveats
- **Blend-weight derivation** (combination puzzle) → heavy shrinkage to simple/incumbent, deterministic
  non-overfit weight function.
- **CLV as confirmatory gate** rests largely on one expert (Buchdahl) + a clean sharp reference; odds-originator
  case means weak CLV can wrongly block a good model → use veto-on-disagreement, validate the reference per
  market.
- **Determinism on SQLite** is achievable but fragile (float order, dict order) → sorted aggregations, pinned
  seeds, hash gates.
- The claim that **a gated blend uniquely resolves the calibration/CLV timing dilemma** is sound engineering
  reasoning, **not a proven theorem** — treat as opinionated design.

## Claude Code's flagged thin spots (→ feed Brief 2)
1. Two-repo packaging (the research says "one shared library" but never grapples with two separate repos).
2. Byte-identical replay vs the suggested tolerance gate — resolved by Jono: keep byte-identical, **pin
   calibration_version + manifest weights as snapshot inputs to replay**; tolerance only for sampled/copula.
3. CLV is the weakest input (thin + fragile capture daemon) — implementation must harden it / lean on
   calibration early.
4. The weight-ramp function is left abstract — needs a concrete, replayable formula.
5. The strangler-fig refactor sequence (don't break the nightly run) is listed but not engineered.
