# JonnyParlay + EdgeModel — Prioritized Fix Plan (v2 — Post-Research)

_Generated: 2026-06-16 09:28 MDT_

_Supersedes `JonnyParlay_Fix_Plan.md` (v1). Incorporates `Research_Validation_Addendum.md`._

_Companion to `JonnyParlay_Findings_Report.md` and `JonnyParlay_Master_Audit_Tracker.xlsx`._

## What changed from v1

Research validation pass changed the plan in 5 places:

| # | Change | Reason |
|---|---|---|
| 1 | **ADDED** Phase 0 #1: CO_LEGAL_BOOKS prune | Research item 9 — CONTRADICTED. Six defunct books in allowlist (WynnBET, PointsBet, Tipico, Betway, TwinSpires, SuperBook). Test hard-pins `len==18`. |
| 2 | **DROPPED** old Phase 0 #1: T3 edge floor bump 0.06→0.08 | Research item 8 — DOWNGRADED. Cross-tier BM-weight↔edge-floor ordering rule not externally endorsed; Plan-10 "BM direction inverted" note contradicts the trust ranking. Defer to n≥150 per-family bootstrap refit. |
| 3 | **DROPPED** old Phase 1 #5: MIN_LEG_WIN_PROB_OUTS retune | Research item 2 — DOWNGRADED. σ=0.27 is pooled, not per-pitcher (within-CV 0.228). External data cannot set the gate. Let existing n≥40 monitor fire. |
| 4 | **FIXED WORDING** Phase 1 #2: WNBA σ refit | Research item 3 — `min≥20` governs `SIGMA_WNBA`, NOT `NB_R` (fit at `min≥8`). v1 plan had this wrong. |
| 5 | **CONSTRAINED** Phase 1 #4: Combo+MLB Platt fit | Research item 4 — Use 1-param intercept-only until n≥300; switch to 2-param after. Don't consider isotonic until any single market exceeds ~1000 rows. |

Unchanged: cross-cutting prerequisites, WNBA team_sigmas key fix, max-edge ceiling, PLATT_SPACE assertion, CI bootstrap, capture_clv fork, lineup gate, MLB starts-only σ, NB_R single-source, SGP ρ stamping, VAKE cap, all Phase 2/3 tasks.

## Overview

The 481 findings + research validation are grouped into **4 execution phases** by:
1. **Correctness blast radius** — does this change priced lines today?
2. **Data dependency** — code-only fix, or needs historical refits / new data volume?
3. **Risk of regression** — how much surface area does the change touch?
4. **Reversibility** — can it roll back via a single config flag?

Each task lists: **Finding ID** · **Location** · **Change** · **Validation** · **Risk if skipped** · **Estimated effort** (S=hours, M=day, L=multi-day, XL=week+).

**Recommended cadence**: Phase 0 this week → validate against historical pick_log → Phase 1 over next 2 weeks → Phase 2 over the month → Phase 3 ongoing.

### Phase summary

| Phase | Window | Focus | Tasks | Code-only? |
|---|---|---|---|---|
| **Phase 0** | This week | P0 correctness, code-only | 7 | Yes |
| **Phase 1** | Next 2 weeks | P0 correctness requiring data refits | 7 | No — needs data |
| **Phase 2** | Next month | P1 silent-drift cleanup | 12 | Mixed |
| **Phase 3** | Backlog / ongoing | P2 tech debt, hygiene | 14 | Yes |

## Cross-cutting prerequisites (do these first)

Before touching any P0 fix, set up a **frozen replay harness**. Without it, every change is a blind change.

**P-1. Replay harness**
- Snapshot last 30 days of `pick_log` + raw odds + lineup data into `replay/` directory.
- Build `replay/run_replay.py` that re-runs `run_picks.py` against the snapshot deterministically (no live API).
- Output: diff of (picks made, units staked, expected EV, gate counters) between current and patched code.
- Validation: replay against unchanged build must produce byte-identical pick list.
- Effort: **M**.

**P-2. Git tag pre-fix state**
- `git tag pre-audit-fixes-2026-06` on both repos before Phase 0 commits.
- One-command rollback: `git checkout pre-audit-fixes-2026-06`.
- Effort: **S**.

---

## Phase 0 — This week (P0 correctness, code-only)


### P0.1 — Prune CO_LEGAL_BOOKS — remove 6 defunct sportsbooks
- **Finding ID**: Research item 9 (NEW)
- **Location**: `engine/book_names.py` + `tests/test_book_names.py`
- **Change**: Remove from CO_LEGAL_BOOKS: **wynnbet, pointsbetus, tipico, betway, twinspires, superbook** (all confirmed-exited the CO market 2022-2024). Relabel `espnbet` comment from 'theScore Bet' → 'ESPN Bet' (PENN rebrand). Update `tests/test_book_names.py` `len==18` assertion to new count in the SAME commit. **Verify final list against the Colorado Division of Gaming official operator roster before finalizing** (research used secondary aggregators; CO DOG is authoritative).
- **Validation**: Test suite passes. Replay last 7d; no priced line should disappear (Odds API returns nothing for defunct keys anyway, so functional impact ~zero — this is a correctness/clarity fix).
- **Risk if skipped**: Stale allowlist confuses contributors and future API integrations; test hard-pins a wrong count.
- **Effort**: S

### P0.2 — Fix WNBA team_sigmas key mismatch (ID vs abbreviation)
- **Finding ID**: S4d-5
- **Location**: `engine/projector_loader.py` (or wherever `team_sigmas` is consumed for WNBA)
- **Change**: Either (a) re-key JSON to use 3-letter abbreviations at export time in EdgeModel, OR (b) build `id → abbr` map at JP load time. Recommended: (a) — single source of truth at producer.
- **Validation**: Add health_check assertion: for each WNBA team played in last 7d, team σ must differ from league σ.
- **Risk if skipped**: WNBA team-level dispersion silently unused; every pick uses league σ.
- **Effort**: S

### P0.3 — Add max-edge ceiling for props (G2 equivalent)
- **Finding ID**: S4f-2
- **Location**: `engine/gates.py` (prop pipeline)
- **Change**: Add `MAX_PROP_EDGE = 0.10`. Reject any prop leg where modeled edge > MAX_PROP_EDGE. Mirror game-line GG1 logic. Log to `gate_check` counter `prop_edge_ceiling_rejects`.
- **Validation**: Replay last 30d; identify blocked picks; spot-check for outlier σ or stale closing line.
- **Risk if skipped**: A single bad σ on a prop produces unbounded "value" signal flowing to staking.
- **Effort**: S

### P0.4 — Add PLATT_SPACE assertion + startup log
- **Finding ID**: S4f-15 (H3)
- **Location**: `engine/calibration_loader.py` + `engine/health_check.py`
- **Change**: On startup, assert `PLATT_SPACE` matches the value stamped in the Platt artifact JSON. Log value at INFO. Hard-fail on mismatch. Stamp `platt_space` into every new Platt artifact in EdgeModel.
- **Validation**: Manually flip flag → daemon must refuse to start. Health check reports PLATT_SPACE every run.
- **Risk if skipped**: Wrong flag silently degrades every calibrated probability with no operator signal.
- **Effort**: S

### P0.5 — Bootstrap minimal CI (test runner + lint)
- **Finding ID**: S4l-3 + Research item 10
- **Location**: `.github/workflows/ci.yml` (new) on both repos
- **Change**: Single workflow: `actions/checkout@v6.0.3` (pinned) → `actions/setup-python@v5` with `cache: 'pip'` → `pip install -r requirements.txt` → `ruff check --output-format=github .` → `ruff format --check .` → `pytest -m 'not network'`. Single Python version (e.g. 3.13), no matrix. **Use the documented manual ruff form, NOT a synthesized `astral-sh/ruff-action@v3` arg list.** Mark network-dependent fetcher tests `@pytest.mark.network`. Do not add new tests in this task — just enforce what exists keeps passing.
- **Validation**: Push branch that breaks a test → CI must fail. Push clean branch → CI passes.
- **Risk if skipped**: Every config knob change is a manual-only correctness check.
- **Effort**: M

### P0.6 — Eliminate `capture_clv` `implied_prob` fork
- **Finding ID**: S4k-3
- **Location**: `engine/capture_clv.py`
- **Change**: Delete local `implied_prob` variant. Import canonical version from `engine/markets.py`. Add test: same input → identical output across old and new path.
- **Validation**: Dry-run capture_clv against last 7d; CLV deltas must match pre-change run to 6 decimals.
- **Risk if skipped**: Vig handling change in markets.py silently breaks CLV ledger.
- **Effort**: S

### P0.7 — Add lineup-freshness gate in `run_picks.py`
- **Finding ID**: S4i-9
- **Location**: `engine/run_picks.py`
- **Change**: Before pricing any prop, assert `lineup_fetcher.last_run_ts > tip_time - 30 min`. If stale, skip the game with `lineup_stale` gate counter + Discord warning.
- **Validation**: Pause lineup_fetcher; rerun run_picks → game must be skipped, counter must increment.
- **Risk if skipped**: Picks priced on yesterday's lineup; out-of-rotation players incorrectly modeled.
- **Effort**: S

### Dropped from Phase 0 (vs v1)

- ~~T3 edge floor bump 0.06 → 0.08~~ (Plan 9 §9F monotonicity). Research downgraded: cross-tier BM-weight↔edge-floor rule not literature-endorsed; Plan-10 "BM direction inverted" note contradicts the trust ranking. **Defer to n≥150 per-family bootstrap refit (Phase 3 candidate).**

---

## Phase 1 — Next 2 weeks (P0 correctness requiring data refits)


### P1.1 — Add MLB starts-only filter to σ calibration
- **Finding ID**: S4e-3
- **Location**: `edgemodel/engine/calibrate_distributions.py` (MLB block)
- **Change**: Filter MLB pitcher σ-fit input to `gs == 1` (games started). Per Plan 6 §1C. Research confirmed via your own DB: within-CV starts-only=0.228 vs relief=0.443. Reliever appearances inflate σ and bias high.
- **Validation**: Compare σ_outs pre/post filter on last 2 seasons. Expect σ to drop ~5-10%. Replay last 30d MLB picks.
- **Risk if skipped**: MLB pitcher σ systematically too wide → priced lines too conservative on overs, aggressive on unders.
- **Effort**: M

### P1.2 — Refit WNBA SIGMA_WNBA on min≥20 priced-minutes subset
- **Finding ID**: S4e-4
- **Location**: `edgemodel/engine/calibrate_distributions.py` (WNBA block)
- **Change**: **Clarification (research item 3):** `min≥20` governs `SIGMA_WNBA` (the Normal-path CV proxy for the G14 z-score gate and combo σ), **NOT `NB_R`** (which is fit at `min≥8`). Filter SIGMA_WNBA input to games where the player was priced by a sportsbook AND played ≥20 minutes. Add a min-cutoff sensitivity table (≥8 vs ≥15 vs ≥20) to confirm stability. Justify the filter as 'priced rotation player', NOT as a public WNBA convention (public qualifiers are games-based: 31g / 525pts / 250reb / 150ast / 25 3PM in 44-game era).
- **Validation**: Sensitivity table; replay; expect WNBA SIGMA_WNBA to tighten modestly.
- **Risk if skipped**: SIGMA_WNBA contaminated by garbage-time/DNP variance.
- **Effort**: M

### P1.3 — Align NB_R values: producer (EdgeModel) ↔ consumer (JonnyParlay)
- **Finding ID**: S4d-1 / S4d-2 / S4e-2
- **Location**: `edgemodel/engine/calibrate_distributions.py` (export) + `engine/thresholds.py` (NB_R dict)
- **Change**: Single source of truth: EdgeModel exports `nb_r` per stat into projector/Platt JSON. JP reads from JSON at startup. Delete the hardcoded `NB_R` dict in JP. Verified drifts: AST (12.16 → 9.65), REB (14.7 → 13.16). Use projector values. Research note: external data cannot adjudicate which r is closer to truth at a single-player level — the population-fit projector value is the correct reference.
- **Validation**: Replay last 30d; NB-modeled lines (AST, REB, 3PM, HR, RBI, TB) will reprice. Compare expected EV + gate pass rates.
- **Risk if skipped**: Every NB-modeled stat has wrong variance — affects ~40% of priced props.
- **Effort**: M

### P1.4 — Fit and ship Combo + MLB Platt calibrators
- **Finding ID**: S4b-8 / S4b-9
- **Location**: `edgemodel/engine/fit_platt.py` + `data/platt/`
- **Change**: Add Combo (SGP joint probability) and MLB game-line Platt fits. **Constraint (research item 4):** use **1-parameter intercept-only fit** for both until n≥300 graded rows per market — matches the native H3 fit pattern at small n (Guo et al. 2017 temperature scaling). Switch to 2-parameter fit once n≥300. Do NOT consider isotonic regression until any single market exceeds ~1000 rows (Niculescu-Mizil & Caruana 2005 crossover; scikit-learn docs). Last 90d of completed picks/SGPs as training. Verify `evaluators.py:124` no longer falls back to raw.
- **Validation**: Health check reports 4 Platt artifacts present (NBA, WNBA, Combo, MLB), each with `platt_space`, `fit_date`, `n_rows`, `param_count` stamps.
- **Risk if skipped**: Combo/MLB probabilities uncalibrated — historical reliability curves show ~3-7% bias.
- **Effort**: L

### P1.5 — Stamp NBA SGP ρ matrix with version + fit_date
- **Finding ID**: S4g-4 / S4g-5
- **Location**: `edgemodel/data/sgp_correlations/nba_rho.json`
- **Change**: Add `version`, `fit_date`, `n_observations`, `source` fields. JP asserts on load. No matrix change — just provenance.
- **Validation**: Health check reports ρ matrix metadata at every startup.
- **Risk if skipped**: Unknown how stale ρ values are; no audit trail.
- **Effort**: S

### P1.6 — Document MLB SGP ρ "awaiting data" status + refit trigger
- **Finding ID**: S4g-12
- **Location**: `engine/sgp_correlation.py` + Plan 9 doc
- **Change**: Add explicit comment + runtime log: "MLB SGP ρ uses structural priors, n=X observed, target n=160-250". **Research item 5 refinement:** n=100 is sign-and-coarse-magnitude only (Fisher z 95% CI ≈ ±0.20 for ρ=0.30; Schönbrodt & Perugini 2013 point-of-stability ~161 for ±0.10 corridor, ~250 for stricter). Use empirical-Bayes shrinkage: blend observed r toward 0.30 prior until n≈160. Effective n is BELOW nominal due to gate-selection + same-game correlation. Increment a counter per MLB SGP placed. Alert at n=100 (sign check), n=160 (magnitude refit candidate).
- **Validation**: Manual: count current observed MLB SGPs. Log on startup. Two-stage alerts.
- **Risk if skipped**: MLB SGP staking continues indefinitely on priors; no auto-trigger for refit.
- **Effort**: S

### P1.7 — Recalibrate VAKE multiplier stack
- **Finding ID**: S4h-8
- **Location**: `engine/sizing.py` (VAKE block)
- **Change**: Audit 5 multipliers (Variance, Adj, Knockout, Edge, …) on T3 picks. Either (a) cap compound multiplier at 0.85x, OR (b) refactor to additive shrinkage. Recommended: (a) — minimal code change, preserves intent.
- **Validation**: Replay last 30d; T3 effective stakes should rise from "always at floor" to a distribution.
- **Risk if skipped**: T3 sizing broken — Kelly logic never engages.
- **Effort**: M

### Dropped from Phase 1 (vs v1)

- ~~Retune MIN_LEG_WIN_PROB_OUTS from 0.62 to ~0.65-0.67~~. Research downgraded: σ=0.27 is a pooled-CV anchor, not the per-pitcher object (within-CV 0.228). External data cannot set the gate. **Let the existing n≥40 graded-OUTS-SGP-leg monitor fire** (σ-equivalent floor ~0.64); only retune when monitor triggers.

---

## Phase 2 — Next month (P1 silent-drift cleanup)


| Task | Finding ID | Location | Change | Validation | Risk if skipped | Effort |
|---|---|---|---|---|---|---|
| P2.1 Remove STALE files flagged as zombie code | S4a-3 | `engine/` | Delete 7 files from audit Step 4a list; verify no imports. | Replay must pass. | Confused contributors edit dead code paths. | S |
| P2.2 Switch daily lay baseline from vigged to no-vig consensus | S4c-6 (F6.9) | `engine/parlays.py:278` | Replace vigged implied prob with no-vig consensus across CO_LEGAL_BOOKS (post-prune). | Compare last 30d parlay EV under both baselines. | Daily lay EV biased toward book vig. | M |
| P2.3 Pick BM shrinkage target: vigged-implied vs no-vig consensus | S4h-3 | `engine/sizing.py` | Document decision; pick one; align everywhere. | Replay both; pick option with better historical CLV. | Ambiguous edge interpretation. | M |
| P2.4 Add travel/altitude effects to MLB+NBA projector (if data available) | S4e-5 | `edgemodel/engine/projector.py` | If team-level travel-days feature exists, add multiplicative σ adjustment. | A/B replay; expect modest improvement on B2B road games. | Modest miss on known signal. | L |
| P2.5 Add reliability-curve smoke test to health_check | S4d-X | `engine/health_check.py` | Bin last 90d picks by predicted probability; assert |obs - pred| < 0.05 per bin. | Smoke runs <5s. | No alert when calibration drifts. | M |
| P2.6 ρ matrix smoke test (positive-definite, in-range) | S4g-X | `engine/sgp_correlation.py` | On load, assert ρ is PD and entries ∈ [-1, 1]. | Run on startup. | Malformed ρ → nonsensical copula. | S |
| P2.7 Platt artifact freshness check | S4b-X | `engine/health_check.py` | Warn if any Platt artifact >60d old. | Health check warning surfaces. | Stale Platt drifts as model improves. | S |
| P2.8 Eliminate hardcoded `C:\Dev\JonnyParlay` paths | S4l-4 | `engine/secrets_config.py + scripts` | Read base path from env var `JONNYPARLAY_HOME`; default to script dir. | Clone repo to fresh location; runs with no edits. | Cannot relocate or run on second machine. | M |
| P2.9 Lineup_fetcher retry/backoff | S4i-X | `engine/lineup_fetcher.py` | Exponential backoff + 3 retries on API failure. | Force 500 in dev; fetcher must recover. | Transient blip skips a game. | S |
| P2.10 Schedule `health_check.py` pre-run gate | S4l-1 | `engine/run_picks.py` | Call health_check first; abort run on any failed check. | Insert artificial failure; run_picks must abort. | Bad state undetected until results. | S |
| P2.11 Gate counter dashboard / weekly digest | S4f-X | `engine/gate_check.py + digest script` | Aggregate gate counters into weekly Discord summary. | Run digest on last week; sanity-check. | No visibility into which gates fire. | M |
| P2.12 pick_log schema migration framework | S4j-X | `engine/pick_log.py` | Lightweight migration runner (current v4 stable; framework for v5+). | No data change — framework only. | Schema changes risk corruption. | M |

---

## Phase 3 — Backlog / ongoing (P2 tech debt, hygiene)

Includes one moved-from-Phase-0 item: data-gated re-evaluation of BM weights and edge floors.


| Finding ID | Task | Location | Effort |
|---|---|---|---|
| Research item 8 (MOVED) | n≥150 per-family bootstrap refit of BM weights + edge floors | `engine/sizing.py + thresholds.py + new scripts/refit_bm.py` | L |
| S4l-5 | Windows daemon → service wrapper (NSSM or task scheduler) | `ops scripts` | S |
| S4l-X | Log rotation for capture_clv, lineup_fetcher | `logging/` | S |
| S4k-X | CLV ledger weekly CSV export | `engine/capture_clv.py` | S |
| S4j-X | Centralize log format across daemons | `engine/logging_config.py` | M |
| S4i-X | Move secrets to OS keyring or `.env` (not Python file) | `engine/secrets_config.py` | M |
| S4h-X | Document unit-cap math in canonical doc | `docs/staking.md` | S |
| S4g-X | Backfill SGP outcome tracking for ρ refit pipeline | `engine/sgp_log.py` | L |
| S4f-X | Move tunable thresholds into single TOML/YAML | `config/thresholds.yaml` | L |
| S4e-X | Unit tests for NB_R consumer (regression guard) | `tests/test_distributions.py` | M |
| S4d-X | Calibration drift dashboard (rolling reliability per stat) | `tools/calibration_dashboard.py` | L |
| S4c-X | Property-based tests for vig/no-vig conversions | `tests/test_markets.py` | M |
| S4b-X | Versioned Platt artifact directory (keep last 5 fits) | `data/platt/` | S |
| S4a-X | Pre-commit hook: ruff + black + mypy | `.pre-commit-config.yaml` | S |
| S4l-X | README + onboarding doc for future contributors | `README.md` | M |

---

## Anti-patterns to avoid

- **Do not batch P0 fixes into one commit.** Each fix gets its own commit + replay diff.
- **Do not refit Platt before σ is correct** — ordering matters: σ → NB_R → Platt.
- **Do not lower any gate threshold** during the fix pass. Only raise or hold.
- **Do not delete STALE files until P-1 replay harness exists** — confirm they're unreferenced at runtime.
- **Do not change `KELLY_FRACTION` or daily caps.** Sizing math is verified-OK and research confirms 1/16.7 Kelly is conservative-safe; touching it during a correctness pass conflates concerns.
- **Do not skip the replay diff** even for "trivial" changes.
- **Do not hand-tune T3 edge floor or BM weights** as part of any fix. The cross-tier monotonicity rule is not externally validated; defer to the n≥150 bootstrap refit.
- **Do not retune MIN_LEG_WIN_PROB_OUTS by hand.** Let the n≥40 OUTS-SGP-leg monitor fire.
- **Do not use isotonic or beta calibration** at current sample sizes. Stay with Platt (1-param intercept-only below n=300, 2-param above).
- **Do not use `astral-sh/ruff-action@v3` with synthesized args.** Use documented manual `ruff check` and `ruff format --check .` steps.

## Success criteria (end of Phase 1)

After Phase 0 + Phase 1 land, the following must be true:

- [ ] CO_LEGAL_BOOKS contains only currently-licensed CO sportsbooks (verified against CO Division of Gaming).
- [ ] All 4 Platt artifacts present (NBA, WNBA, Combo, MLB), each stamped with `platt_space`, `fit_date`, `n_rows`, `param_count`.
- [ ] `NB_R` consumed from a single JSON source; no hardcoded dict in JP.
- [ ] `team_sigmas` lookup hits on every WNBA game (verified by health_check).
- [ ] MLB σ fit on starts-only; WNBA SIGMA_WNBA fit on min≥20 priced (NB_R remains at min≥8).
- [ ] Replay of any 7-day window before Phase 0 reproduces byte-identical results against pre-audit git tag.
- [ ] CI runs on every push; failing tests block merge; ruff lint + format checks pass.
- [ ] `health_check.py` runs before every `run_picks.py` and aborts on failure.
- [ ] PLATT_SPACE asserted at startup; mismatch hard-fails the daemon.
- [ ] MLB SGP ρ refit alerts wired at n=100 (sign) and n=160 (magnitude).

---

_End of fix plan v2. Audit deliverables complete: Tracker (.xlsx), Findings Report (.md), Fix Plan v2 (.md), Research Validation Addendum (.md)._