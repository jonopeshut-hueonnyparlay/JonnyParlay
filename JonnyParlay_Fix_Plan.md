# JonnyParlay + EdgeModel — Prioritized Fix Plan

_Generated: 2026-06-16 08:54 MDT_

_Companion to `JonnyParlay_Findings_Report.md` and `JonnyParlay_Master_Audit_Tracker.xlsx`._

## Overview

The 481 findings are grouped into **4 execution phases** based on:
1. **Correctness blast radius** — does this change priced lines today?
2. **Data dependency** — can it be fixed in code only, or does it require historical data refits / new SGP volume?
3. **Risk of regression** — how much surface area does the change touch?
4. **Reversibility** — can it be rolled back via a single config flag?

Each task lists: **Finding ID** · **Location** · **Change** · **Validation** · **Risk if skipped** · **Estimated effort** (S=hours, M=day, L=multi-day, XL=week+).

**Recommended cadence**: Phase 0 this week → freeze, validate against historical pick_log → Phase 1 over next 2 weeks → Phase 2 over the month → Phase 3 as ongoing hygiene.

### Phase summary

| Phase | Window | Focus | Tasks | Code-only? |
|---|---|---|---|---|
| **Phase 0** | This week | P0 correctness, code-only fixes | 7 | Yes |
| **Phase 1** | Next 2 weeks | P0 correctness requiring data refits | 8 | No — needs data |
| **Phase 2** | Next month | P1 silent-drift cleanup | 12 | Mixed |
| **Phase 3** | Backlog / ongoing | P2 tech debt, CI/CD, hygiene | 14 | Yes |

## Cross-cutting prerequisites (do these first)

Before touching any P0 fix, set up a **frozen replay harness** so every change is validated against historical pick output. Without this, you cannot prove a fix isn't making things worse.

**P-1. Replay harness**
- Snapshot last 30 days of `pick_log` + raw odds + lineup data into `replay/` directory.
- Build `replay/run_replay.py` that re-runs `run_picks.py` against the snapshot deterministically (no live API calls).
- Output: diff of (picks made, units staked, expected EV, gate counters) between current code and patched code.
- Validation: replay against an unchanged build must produce a byte-identical pick list.
- Effort: **M** (one day to wire up, payoff lasts forever).
- Risk if skipped: Every P0 fix below becomes a blind change.

**P-2. Git tag the pre-fix state**
- `git tag pre-audit-fixes-2026-06` on both repos before Phase 0 commits.
- One-command rollback if anything misbehaves: `git checkout pre-audit-fixes-2026-06`.
- Effort: **S** (minutes).

---

## Phase 0 — This week (P0 correctness, code-only)

These fix confirmed bugs without requiring data collection or model refits. Each is reversible via a single config or one-file change.


### P0.1 — Restore Plan 9 §9F monotonicity (T3 edge floor)
- **Finding ID**: S4c-5 / S4f-3
- **Location**: `engine/thresholds.py` (TIERS, BM_SHRINKAGE_WEIGHT blocks)
- **Change**: Either (a) **raise** T3 `min_edge` floor from 0.06 → 0.08 to match its low BM trust (0.70), OR (b) **raise** T3 `BM_SHRINKAGE_WEIGHT` from 0.70 → 0.80 (default) to match its mid floor. Recommended: (a) — keeps T3 as the "least trusted, must clear higher edge" tier per Plan 9.
- **Validation**: Replay last 30d; T3 pick count should drop ~15-25%; expected EV per T3 pick should rise.
- **Risk if skipped**: Lowest-confidence tier admits picks with weaker edge than higher tiers — inverted risk gradient bleeds into staking.
- **Effort**: S (single-line config change + replay)

### P0.2 — Fix WNBA team_sigmas key mismatch (ID vs abbreviation)
- **Finding ID**: S4d-5
- **Location**: `engine/projector_loader.py` (or wherever `team_sigmas` is consumed for WNBA)
- **Change**: Either (a) re-key the JSON to use 3-letter abbreviations at export time in EdgeModel, OR (b) build an `id → abbr` map at JP load time and translate lookups. Recommended: (a) — single source of truth at the producer.
- **Validation**: Add an assertion in `health_check.py`: for each WNBA team played in last 7 days, team σ must differ from league σ.
- **Risk if skipped**: WNBA team-level dispersion is silently unused; every pick uses league σ (too wide for high-dispersion teams, too tight for low-dispersion).
- **Effort**: S

### P0.3 — Add max-edge ceiling for props (G2 equivalent)
- **Finding ID**: S4f-2
- **Location**: `engine/gates.py` (prop pipeline)
- **Change**: Add `MAX_PROP_EDGE = 0.10` constant. In the prop gate, reject any leg where modeled edge > MAX_PROP_EDGE. Mirror game-line GG1 logic. Log to `gate_check` counter `prop_edge_ceiling_rejects`.
- **Validation**: Replay last 30d; identify how many picks would have been blocked; spot-check those for outlier σ or stale closing line.
- **Risk if skipped**: A single bad σ on a prop produces an unbounded "value" signal that flows through to staking with no guardrail.
- **Effort**: S

### P0.4 — Add PLATT_SPACE assertion + startup log
- **Finding ID**: S4f-15 (H3)
- **Location**: `engine/calibration_loader.py` + `engine/health_check.py`
- **Change**: On startup, assert `PLATT_SPACE` matches the value stamped into the Platt artifact JSON. Log the value at INFO level. Hard-fail if mismatched. Stamp `platt_space` into every new Platt artifact written by EdgeModel.
- **Validation**: Manually flip flag → daemon must refuse to start. Health check should report PLATT_SPACE on every run.
- **Risk if skipped**: Wrong flag silently degrades every calibrated probability with no operator-visible signal.
- **Effort**: S

### P0.5 — Bootstrap minimal CI (test runner + lint)
- **Finding ID**: S4l-3
- **Location**: `.github/workflows/ci.yml` (new) on both repos
- **Change**: Single workflow: install deps → run existing pytest suite → run `ruff check` on engine/. Trigger on push + PR. Do **not** add new tests in this task — just enforce that what exists keeps passing.
- **Validation**: Push a branch that breaks a test; CI must fail. Push a clean branch; CI must pass.
- **Risk if skipped**: Every config knob change is a manual-only correctness check; regression risk compounds.
- **Effort**: M

### P0.6 — Eliminate `capture_clv` `implied_prob` fork
- **Finding ID**: S4k-3
- **Location**: `engine/capture_clv.py`
- **Change**: Delete local `implied_prob` variant. Import canonical version from `engine/markets.py`. Add a test: same input → identical output across both old and new path.
- **Validation**: Run capture_clv against last 7d in dry-run; CLV deltas must match the pre-change run to 6 decimals.
- **Risk if skipped**: Vig handling change in markets.py silently breaks CLV ledger.
- **Effort**: S

### P0.7 — Add lineup-freshness gate in `run_picks.py`
- **Finding ID**: S4i-9
- **Location**: `engine/run_picks.py`
- **Change**: Before pricing any prop, assert `lineup_fetcher.last_run_ts > tip_time - 30 min`. If stale, skip the game with a `lineup_stale` gate counter and Discord warning.
- **Validation**: Manually pause lineup_fetcher; rerun run_picks → that game must be skipped, counter must increment.
- **Risk if skipped**: Picks priced on yesterday's lineup; out-of-rotation players incorrectly modeled.
- **Effort**: S

---

## Phase 1 — Next 2 weeks (P0 correctness requiring data refits)

These require touching the EdgeModel calibration pipeline and/or waiting on data volume. Order matters — refit dependencies cascade.


### P1.1 — Add MLB starts-only filter to σ calibration
- **Finding ID**: S4e-3
- **Location**: `edgemodel/engine/calibrate_distributions.py` (MLB block)
- **Change**: When fitting σ for MLB pitcher stats (OUTS, ER, K, H, etc.), filter input rows to `gs == 1` (games started). Per Plan 6 §1C. Reliever appearances inflate σ and bias high.
- **Validation**: Compare σ_outs pre/post filter on last 2 seasons. Expect σ to drop ~5-10%. Replay last 30d MLB picks against new σ; gate pass rates should shift.
- **Risk if skipped**: MLB pitcher σ is systematically too wide → priced lines too conservative on overs, too aggressive on unders.
- **Effort**: M

### P1.2 — Add WNBA min≥20 priced-minutes filter to σ calibration
- **Finding ID**: S4e-4
- **Location**: `edgemodel/engine/calibrate_distributions.py` (WNBA block)
- **Change**: Filter input to games where the player was *priced by a sportsbook* AND played ≥20 minutes. Per Plan 6 §1C. Garbage-time and DNPs both inflate σ.
- **Validation**: σ_PTS_WNBA expected to drop materially. Replay; expect WNBA pick volume to rise slightly.
- **Risk if skipped**: Same as MLB — systematic over-conservatism on overs, over-aggression on unders.
- **Effort**: M

### P1.3 — Align NB_R values: producer (EdgeModel) ↔ consumer (JonnyParlay)
- **Finding ID**: S4d-1 / S4d-2 / S4e-2
- **Location**: `edgemodel/engine/calibrate_distributions.py` (export) + `engine/thresholds.py` (NB_R dict)
- **Change**: Single source of truth: EdgeModel exports `nb_r` per stat into the Platt/projector JSON. JP reads from JSON at startup. Delete the hardcoded `NB_R` dict in JP. Verified drifts: AST (12.16 → 9.65), REB (14.7 → 13.16). Use the projector values.
- **Validation**: Replay last 30d; NB-modeled lines (AST, REB, 3PM, HR, RBI, TB) will reprice. Compare expected EV and gate pass rates.
- **Risk if skipped**: Every NB-modeled stat has the wrong variance — affects ~40% of priced props.
- **Effort**: M (touches export + load + 2 files)

### P1.4 — Fit and ship Combo + MLB Platt calibrators
- **Finding ID**: S4b-8 / S4b-9
- **Location**: `edgemodel/engine/fit_platt.py` + artifacts in `data/platt/`
- **Change**: Add Combo (SGP joint probability) and MLB game-line Platt fits. Use last 90d of completed picks/SGPs as training. Verify `evaluators.py:124` no longer falls back to raw output.
- **Validation**: Health check should report 4 Platt artifacts present (NBA, WNBA, Combo, MLB), all with `platt_space` stamp.
- **Risk if skipped**: Combo/MLB probabilities are uncalibrated — historical reliability curves show ~3-7% bias depending on regime.
- **Effort**: L (needs training data inventory + fit + validation)

### P1.5 — Retune `MIN_LEG_WIN_PROB_OUTS` to current σ
- **Finding ID**: S4f-4
- **Location**: `engine/thresholds.py`
- **Change**: Re-derive `MIN_LEG_WIN_PROB_OUTS` from the new σ_outs (post Phase 1 starts-only refit). Original gate at 0.62 assumed σ=0.311; current σ=0.27. New gate likely ~0.65-0.67. Re-derive via the same logic that produced the original value.
- **Depends on**: S4e-3 must land first.
- **Validation**: Replay last 30d MLB pitcher props; pass rate should drop. Spot-check that historically-losing picks are now gated.
- **Risk if skipped**: MLB pitcher props admit too-thin edges relative to true distribution.
- **Effort**: S (after Phase 1 refit lands)

### P1.6 — Stamp NBA SGP ρ matrix with version + fit_date
- **Finding ID**: S4g-4 / S4g-5
- **Location**: `edgemodel/data/sgp_correlations/nba_rho.json`
- **Change**: Add `version`, `fit_date`, `n_observations`, `source` fields to ρ matrix JSON. JP asserts on load. No matrix change yet — just provenance.
- **Validation**: Health check reports ρ matrix metadata at every startup.
- **Risk if skipped**: Unknown how stale ρ values are; no audit trail for future refits.
- **Effort**: S

### P1.7 — Document MLB SGP ρ "awaiting data" status formally
- **Finding ID**: S4g-12
- **Location**: `engine/sgp_correlation.py` + Plan 9 doc
- **Change**: Add explicit comment + runtime log: "MLB SGP ρ uses structural priors, n=X observed SGPs, target n=100". Increment a counter per MLB SGP placed. When n≥100, alert to refit.
- **Validation**: Manual: count current observed MLB SGPs. Log on startup.
- **Risk if skipped**: MLB SGP staking continues indefinitely on priors; no auto-trigger for refit.
- **Effort**: S

### P1.8 — Recalibrate VAKE multiplier stack
- **Finding ID**: S4h-8
- **Location**: `engine/sizing.py` (VAKE block)
- **Change**: Audit the 5 multipliers (Variance, Adj, Knockout, Edge, …) on T3 picks. Either (a) cap the compound multiplier at 0.85x, OR (b) refactor to additive shrinkage. Recommended: (a) — minimal code change, preserves intent.
- **Validation**: Replay last 30d; T3 effective stakes should rise from "always at floor" to a distribution.
- **Risk if skipped**: T3 sizing is broken — Kelly logic never engages.
- **Effort**: M

---

## Phase 2 — Next month (P1 silent-drift cleanup)

These don't break correctness today but accumulate drift or operational risk over time.


| Task | Finding ID | Location | Change | Validation | Risk if skipped | Effort |
|---|---|---|---|---|---|---|
| P2.1 Remove STALE files flagged as zombie code | S4a-3 | `engine/` | Delete 7 files matching audit Step 4a list; verify no imports. | Replay must still pass. | Confused contributors edit dead code paths. | S |
| P2.2 Switch daily lay baseline from vigged to no-vig consensus | S4c-6 (F6.9) | `engine/parlays.py:278` | Replace vigged implied prob with no-vig consensus across CO_LEGAL_BOOKS. | Compare last 30d parlay EV under both baselines. | Daily lay EV is systematically biased toward the book's vig. | M |
| P2.3 Pick BM shrinkage target: vigged-implied vs no-vig consensus | S4h-3 | `engine/sizing.py` | Document decision; pick one; align everywhere. | Replay both options; pick the one with better historical CLV. | Inconsistent shrinkage target creates ambiguous edge interpretation. | M |
| P2.4 Add travel/altitude effects to MLB+NBA projector (if data available) | S4e-5 | `edgemodel/engine/projector.py` | If team-level travel-days feature is available, add multiplicative σ adjustment. | A/B replay; expect modest improvement on back-to-back road games. | Modest miss on a known signal. | L |
| P2.5 Add reliability-curve smoke test to health_check | S4d-X | `engine/health_check.py` | Bin last 90d picks by predicted probability; assert |observed - predicted| < 0.05 per bin. | Smoke test runs in <5s. | No alert when calibration drifts. | M |
| P2.6 ρ matrix smoke test (positive-definite, in-range) | S4g-X | `engine/sgp_correlation.py` | On load, assert ρ matrix is positive-definite and all entries ∈ [-1, 1]. | Run on every startup. | Malformed ρ → nonsensical copula joint probs. | S |
| P2.7 Platt artifact freshness check | S4b-X | `engine/health_check.py` | Warn if any Platt artifact >60d old without refit. | Health check warning surfaces. | Stale Platt drifts as model improves. | S |
| P2.8 Eliminate hardcoded `C:\Dev\JonnyParlay` paths | S4l-4 | `engine/secrets_config.py + scripts` | Read base path from env var `JONNYPARLAY_HOME`; default to script directory. | Clone repo to fresh location; must run with no edits. | Cannot relocate or run on second machine. | M |
| P2.9 Lineup_fetcher retry/backoff | S4i-X | `engine/lineup_fetcher.py` | Add exponential backoff + 3 retries on API failure. | Force a 500 in dev; fetcher must recover. | Transient API blip skips a game. | S |
| P2.10 Schedule `health_check.py` pre-run gate | S4l-1 | `engine/run_picks.py` | Call health_check first; abort run on any failed check. | Replay; insert artificial failure; run_picks must abort. | Bad state goes undetected until results. | S |
| P2.11 Gate counter dashboard / weekly digest | S4f-X | `engine/gate_check.py + new digest script` | Aggregate gate counters into a weekly Discord summary. | Run digest on last week; sanity-check numbers. | No visibility into which gates are firing. | M |
| P2.12 pick_log schema migration framework | S4j-X | `engine/pick_log.py` | Add lightweight migration runner (current schema v4 stable; framework for v5+). | No data change yet — framework only. | Schema changes risk corruption. | M |

---

## Phase 3 — Backlog / ongoing (P2 tech debt, hygiene)

Lower urgency. Fold into normal dev cadence; don't block on these.


| Finding ID | Task | Location | Effort |
|---|---|---|---|
| S4l-5 | Windows daemon → proper service wrapper (NSSM or task scheduler) | `ops scripts` | S |
| S4l-X | Log rotation for capture_clv, lineup_fetcher | `logging/` | S |
| S4k-X | CLV ledger weekly export to CSV | `engine/capture_clv.py` | S |
| S4j-X | Centralize log format across all daemons | `engine/logging_config.py` | M |
| S4i-X | Move secrets to OS keyring or `.env` (not Python file) | `engine/secrets_config.py` | M |
| S4h-X | Document unit-cap math in a single canonical doc | `docs/staking.md` | S |
| S4g-X | Backfill SGP outcome tracking for ρ refit pipeline | `engine/sgp_log.py` | L |
| S4f-X | Move all tunable thresholds into a single TOML/YAML file | `config/thresholds.yaml` | L |
| S4e-X | Add unit tests for NB_R consumer (regression guard) | `tests/test_distributions.py` | M |
| S4d-X | Calibration drift dashboard (rolling reliability per stat) | `tools/calibration_dashboard.py` | L |
| S4c-X | Property-based tests for vig/no-vig conversions | `tests/test_markets.py` | M |
| S4b-X | Versioned Platt artifact directory (keep last 5 fits) | `data/platt/` | S |
| S4a-X | Pre-commit hook: ruff + black + mypy | `.pre-commit-config.yaml` | S |
| S4l-X | README + onboarding doc for future contributors | `README.md` | M |

---

## Anti-patterns to avoid

Audit-driven cleanups frequently backfire. Hard rules:

- **Do not batch multiple P0 fixes into a single commit.** Each fix gets its own commit + replay diff.
- **Do not refit Platt before σ is correct** (Phase 1 ordering matters: σ → NB_R → Platt).
- **Do not lower any gate threshold** during the fix pass. Only raise or hold.
- **Do not delete `STALE`-marked files until Phase 0 P-1 replay harness exists** — you need to confirm they're truly unreferenced at runtime.
- **Do not change `KELLY_FRACTION` or daily caps** as part of any fix. Sizing math is verified-OK; touching it during a correctness pass conflates concerns.
- **Do not skip the replay diff** even for "trivial" changes. Plan 9 monotonicity violation is a 1-line config change but reprices every T3 pick.

## Success criteria (end of Phase 1)

After Phase 0 + Phase 1 land, the following must be true:

- [ ] All 4 Platt artifacts present (NBA, WNBA, Combo, MLB), each stamped with `platt_space` and `fit_date`.
- [ ] `NB_R` consumed from a single JSON source; no hardcoded dict in JP.
- [ ] `team_sigmas` lookup hits on every WNBA game (verified by health_check).
- [ ] Plan 9 §9F monotonicity holds: T3 edge floor ≥ T1B floor OR T3 BM weight = default.
- [ ] MLB σ fit on starts-only; WNBA σ fit on min≥20 priced.
- [ ] Replay of any 7-day window from before Phase 0 reproduces byte-identical results when run against pre-audit git tag.
- [ ] CI runs on every push; failing tests block merge.
- [ ] `health_check.py` runs before every `run_picks.py` and aborts on failure.

---

_End of fix plan. Next deliverable: **Step 7 — Audit cadence doc**._