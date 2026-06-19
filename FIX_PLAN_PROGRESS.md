# Fix Plan Progress

Tracks execution of `JonnyParlay_Fix_Plan_v2.md`. One task = one commit = one review.
Plan file: `C:\Users\jono4\.claude\plans\you-are-executing-dreamy-brooks.md`

## Prerequisites
- [x] P-1 — Replay harness (JonnyParlay-only, byte-identical gate passes) — 7ea16b9 + d565b55 — 2026-06-16
- [x] P-2 — Git tag `pre-audit-fixes-2026-06` (JonnyParlay d565b55 + EdgeModel db906e5) — 2026-06-16

## Phase 0 (P0.1–P0.6; P0.7 deferred)
- [x] P0.1 — Prune CO_LEGAL_BOOKS (18→12; removed 6 exited books; betparx kept — it's 26% of WNBA props in-feed; betmonarch not added — dead Odds API key). Replay byte-identical. — 2026-06-16
- [x] P0.2 — Fix WNBA team_sigmas key mismatch (id→abbrev re-key via WNBA_ID_MAP; WNBA-aware resolution; health_check §16). Was 2 bugs: id-keyed data + TEAM_ABBREV lacks WNBA. — 2026-06-16
- [~] P0.3 — Add MAX_PROP_EDGE=0.10 prop ceiling — DEFERRED (user decision 2026-06-16). Replay showed 0.10 blocks 32 picks on 06-15: the 25.1%-edge OUTS POTD + 29 WNBA combos (PR/PA/PRA, edges inflated by missing combo Platt P1.4). Too aggressive as a card-wide cap now; revisit after combo Platt or with a different bound. Gate change reverted; only the run_replay.py emoji-print bugfix kept.
- [x] P0.4 — PLATT_SPACE assertion + startup log (health_check §17: space∈{raw,logit} + prob_core space↔formula guard → startup hard-fail; reports config every run). No artifact JSON in this repo → adapted to code-constant consistency. — 2026-06-16
- [x] P0.5 — Bootstrap minimal CI (ruff.toml green baseline + pytest.ini + .github/workflows/ci.yml, windows-latest; ruff check blocking, format advisory, pytest -m "not network"; ruff==0.15.17 pinned). NOT pushed — first push validates. — 2026-06-16
  - FINDING (separate fix): capture_clv.py:1829 F821 undefined `stat` in CLV single-side fallback — latent NameError; F821 left in ruff ignore until fixed.
- [x] P0.6 — Eliminate implied_prob forks: added quant.odds.implied_prob_or_none (C6 None-guard, delegates formula to canonical implied_prob); deleted both forks (capture_clv + clv_report), import the canonical. Pricing path untouched. — 2026-06-16
- [~] P0.7 — Lineup-freshness gate — DEFERRED (EdgeModel scope)

## Phase 1 (data refits; σ → NB_R → Platt ordering)
- [x] P1.1 — MLB pitcher σ starts-only filter — **EdgeModel** `dc1a4ee`. Added MLB_P `continuous_filter="is_starter=1"` scoped to continuous σ-fit stats; ip_outs mult now 0.221 starts-only (was relief-contaminated ~0.31). Deployed SIGMA['OUTS']=0.27 KEPT as buffer (user decision) → zero repricing, replay byte-identical. EdgeModel has no test suite (validation = running the calibration). _Incidental: ER raw NB r=1.46 vs deployed 2.62 — for P1.3._
- [x] P1.2 — WNBA SIGMA_WNBA reproducible (min≥20). Added `wnba-sigma` mode to JonnyParlay calibrate_distributions.py (sensitivity ≥8/≥15/≥20). Table CONFIRMS deployed PTS/AST/REB ≈ min≥20 (0.471/0.644/0.530 vs 0.48/0.65/0.54) → kept, zero repricing. NB_R stays min≥8 (unchanged). — 2026-06-16
  - FLAG (monitor): SIGMA_WNBA['3PM']=0.48 is an NBA z-score proxy; empirical WNBA min≥20 CV ~0.91 (props use NB path so prop pricing OK; understates only G14/combo σ for 3PM). Not deployed — revisit with WNBA 3PM combo/gate performance data.
- [x] P1.3 — Align NB_R (values-only): NBA AST 12.16→9.66, REB 14.7→13.16 — bias-corrected (Jensen MoM); JP's were from an inflating pooled formula. Updated both copies (calibrated.py + sgp_builder.py mirror), health_check pins, tests. Reprices NBA AST/REB over_p ~0.3–0.65pp lower. — 2026-06-16
  - VALIDATION GAP: 06-15 snapshot has no NBA → replay can't cover it (validated via unit tests + direct calc). Capture an NBA snapshot when in season.
  - DEFERRED: 3PM kept 9.15 (producer now classifies Poisson @ var/μ=1.179 — flagged). MLB NB_R (HA 13.41/ER 2.62) drift NOT aligned — producer values relief-contaminated; needs starts-only on discrete stats first. Full JSON single-source deferred (NB_R duplicated in 2 files — that's the case for it).
- [~] P1.4 — Combo + MLB Platt — DATA-GATED, not runnable (combo 27/100, MLB 28/100 graded rows; need 100 to fit). Wire-only scaffolding possible (calibrate_platt.py combo/MLB segments + gate-fire), but the fit can't be validated without data. Defer until the gate opens.
- [x] P1.5 — Stamp NBA SGP ρ provenance. No JSON matrix (ρ is hardcoded in sgp_builder._pairwise_rho) → stamped `_NBA_SGP_RHO_META` (version/fit_date/source/n_observations) + health_check §18 (assert meta + recompute canonical ρ pairs vs frozen values) + tests. n_observations="unrecorded" (never captured). Zero ρ change, replay byte-identical. — 2026-06-16
- [x] P1.6 — MLB SGP ρ provenance + refit-trigger. `_MLB_SGP_RHO_META` + `_count_scored_mlb_sgps()` + `_log_mlb_sgp_rho_status()` (alerts n≥100 sign / n≥160 magnitude) wired into run_mlb_sgp_builder; health_check §19; 4 tests. Empirical-Bayes shrink→0.30 documented (activates at data). No ρ change; golden +1 log line (re-captured). — 2026-06-16
- [~] P1.7 — VAKE multiplier stack — DEFERRED (user decision 2026-06-16) to the engine's DATA_GATED Kelly-stack consolidation (n≥50 graded/market, empirical-Bayes James–Stein per-market mult). The plan's "cap compound at 0.85×" would over-stake T3 (var_m=0.65) + deliberately-de-risked stats (3PM over/WNBA REB market_m=0.10, intentional floor-pins). "T3 always at floor" is partly intended. No code change.

_Legend: [ ] todo · [~] deferred/partial · [x] done (append commit SHA + date)_

---

## HANDOFF — next-session entry point (updated 2026-06-16, end of session 1)

### How to work (protocol)
One task = one commit = one review. **STOP after each task**; show the diff + replay before/after + test result, wait for the user's "proceed". Replay diff is mandatory. **No autonomous numeric-threshold changes** — surface with evidence and let the user decide (this session deferred P0.3, P1.4, P1.7 that way; the user values it). Don't push unless asked. EdgeModel work commits in the separate repo `C:\Dev\EdgeModel`.

**Recurring gotcha:** the Fix Plan repeatedly assumes a JSON-artifact architecture that doesn't exist here — there's no `nba_rho.json`, no Platt artifact JSON, no `engine/markets.py`/`lineup_fetcher.py` in JonnyParlay. Check the real layout first; adapt the plan to code-resident constants. Also: the Bash hook blocks any command whose text contains protected filenames (`pick_log.csv`, `.env`) — avoid those literals.

### Commands
- Replay: `python replay/run_replay.py` (06-15 MLB+WNBA snapshot only — **no NBA**; capture an NBA snapshot when in season). Re-capture after intended output changes: `--capture`.
- Tests: `python -m pytest --basetemp=C:/Dev/JonnyParlay/.pytest_tmp` (baseline **1336**).
- ruff: `python -m ruff check .` (green; F821 now enforced).
- Health check: `python engine/health_check.py` (sections 16–19 added this session).
- CI is **green** on GitHub (windows-latest). Rollback tag `pre-audit-fixes-2026-06` on both repos.

### DONE this session (all pushed)
Prereqs P-1/P-2 · Phase 0: P0.1,P0.2,P0.4,P0.5,P0.6 · Phase 1: P1.1(EdgeModel),P1.2,P1.3,P1.5,P1.6 · CI bootstrap+3 fixes green · capture_clv F821 bug. See the per-task entries above for SHAs.

### NOT done — pick up here
**Data-gated / deferred (not actionable until data/decision):**
- **P1.4 Combo+MLB Platt** — gated (combo 27/100, MLB 28/100; need 100). Wire-only scaffolding possible but the fit can't be validated yet.
- **P1.7 VAKE stack** — deferred to the engine's DATA_GATED n≥50/market Kelly-stack consolidation (a 0.85 cap would over-stake T3 + de-risked stats).
- **P0.3 prop edge ceiling** — revisit combo-aware after P1.4. **P0.7 lineup gate** — EdgeModel-side, no timestamp.
- **WNBA SIGMA_WNBA['3PM']=0.48** proxy (empirical ~0.91) — monitor.

**Standalone, doable next (recommended order):**
1. [x] **MLB NB_R relief-contamination** — DONE 2026-06-16. EdgeModel `bd63b89` (starter filter extended to discrete h/er) + JonnyParlay `6bc9ecd`. **ER 2.62→4.75** (starts-only, n=370/15,297, var/mu=1.509; relief-inclusive 2.62 over-dispersed starter ER ~30%). **HA held at 13.41** + flagged: starts-only HA is var/mu=0.890→Poisson (not NB) — reclassify under the G_HA_SUSPENDED investigation, not a values task. health_check pins + tests added. Replay: carded output byte-identical (one blocked ER candidate shifted G13→TIER_MIN(T1); golden re-captured). 1336 tests.
2. [x] **NB_R single-source** — DONE 2026-06-16. JonnyParlay `018961e`. Adapted away from the phantom JSON pipeline: `sgp_builder.NB_R` now DERIVED from `calibrated.NB_R` for shared stats (3PM/AST/REB); BLK/STL stay SGP-only. 4-layer enforcement: structural (comprehension over NB_STATS) + load-time `_assert_nb_r_single_source()` + 3 CI tests (test_sgp_contract.py) + health_check §6 wiring checks. Values identical → replay byte-identical. 1339 tests.
3. **Phase 2 quick-wins** — progress:
   - [x] **P2.6** ρ-matrix PSD/in-range validation — DONE `cb06345`. `validate_corr_matrix()` in quant/copula.py + load-time `_assert_rho_matrices[_mlb]_wellformed()` in both builders (validated real worst-case matrices are PSD before wiring) + 7 tests + health_check checks. Replay ident.
   - [~] **P2.1** remove STALE files — SKIPPED (no real list). The 🧟 marker is defined but never used; the "7 files" don't exist. Own scan: 11 zero-importer files but all legit CLI tools / `health_check` / `nb_calibrate` (cited provenance). No safe deletions. Reopen only if specific dead files are named.
   - [x] **P2.5** reliability-curve smoke test — DONE `553d0e5`. Advisory (warn) calibration-drift check in health_check §20; flags a bin only when n≥30 AND |obs−pred|>2·binomial-SE (the audit's <0.05 bound false-alarms on noise). **Surfaced a real finding:** model ~18pp overconfident (55-60%: 57.2%→39.5% n=38; 70%+: 72.5%→54.7% n=53) — consistent with open H3 Platt gate; prioritize H3 at 100/100.
   - [x] **P2.10** health_check pre-run gate — DONE `fd15731`. run_picks subprocess-runs health_check before betting work, aborts on blocking fails. Fixed the audit's unsafe "abort on any fail" by demoting the 2 advisory checks (CLAUDE.md size, git-clean) to warn() → health_check's sys.exit(1) is now blocking-only. stdout-silent on pass (replay ident.), crash/missing/subprocess-error all non-blocking, `--skip-health-check` escape hatch (replay/tests use it). 7 gate tests.
   - [x] **P2.8** portable paths — DONE `a6f3564`. paths.py already did 90% ($JONNYPARLAY_ROOT/script-dir/Documents); health_check.py was the last hardcoded-`C:\Dev` file → now JP_ROOT=paths.PROJECT_ROOT, EM_ROOT=$EDGEMODEL_ROOT or sibling checkout. Resolves identically here (146/146, exit 0); replay ident.
   - **Remaining Phase 2:** P2.2 (no-vig daily-lay baseline, M — *behavioral*, needs reprice review), P2.3 (BM shrinkage target doc, M), P2.4 (travel/altitude — EdgeModel, L), P2.7 (Platt freshness — no JSON artifact; adapt to constant fit-date), P2.9 (lineup_fetcher retry — EdgeModel), P2.11 (gate digest, M), P2.12 (schema migration framework, M). Then Phase 3.
   - **HIGH-PRIORITY (surfaced by P2.5):** model is ~18pp overconfident in live data (H3 Platt gate at 98/100). When it hits 100, run `python engine/calibrate_platt.py --intercept-only --force` (per CLAUDE.md H3) — highest-leverage fix available.

**Housekeeping:** CLAUDE.md is 40,459 chars (>40k health-check limit) — trim when convenient. Pre-existing uncommitted `engine/calibrate_platt.py` change in the tree — not ours, left untouched all session; confirm with user before handling.

---

## HANDOFF — session 3 (2026-06-16)

### H3 Platt refit — INVESTIGATED, deploy HELD (not a values change)
`gate_check` showed H3 "reached" (102/100), but the refit is **not safe to deploy**:
- The fittable carded sample (`calibrate_platt`: primary/bonus, non-combo prop stats, native `over_p_raw`) is **72 rows, 65 under / 7 over** — ~90% one-directional. You can't fit a both-sided `over_p->P(win)` curve from it; the free fit collapses to a=0.10 (overfit).
- The "intercept-only a=1/b=0 no-op" was a **bound bug**: `_fit_nll_exact` clipped the intercept at `[-3,0]`, but an under-heavy sample's optimum is **positive** (real b=+0.3335, OOS +1.9%).
- The correct basis is `pick_log_calibration.csv` (unbiased, both directions) — but it's **1 day old** (all 06-15; created 2026-06-14), so cross-day CV is invalid. Its free fit (a=0.7882, b=-0.2705) would *raise* top-end win_probs — opposite of the carded-overconfidence signal (that's selection/regression-to-mean, not a function miscalibration).
- **Decision: HOLD** the reprice until the calibration log spans ≥10 distinct graded days. `PLATT_A/B`/`PLATT_SPACE` UNCHANGED. Plan: `~/.claude/plans/you-are-resuming-execution-elegant-charm.md`.

### DONE this session (NOT pushed)
- [x] **Task A** — `calibrate_platt.py` tooling fix `1b12b3e`. Widened both intercept bounds `[-3,0]`→`[-3,3]` (fixes the under-heavy false no-op) + added `"calibration"` to the run_type filter (user-approved; enables fitting on the calibration log). Offline script only — `calibrated.py` untouched, replay byte-identical, 1353 tests.
- [x] **P2.12** — pick_log schema-migration framework (this commit). Built on the existing `pick_log_schema.py` (real file; the plan's `engine/pick_log.py` doesn't exist). Added a per-version transform registry (`register_migration`/`_MIGRATIONS`), a chain runner (`migrate_row_chain`), and a file-level runner (`migrate_file`, **dry_run=True default**, atomic tmp+fsync+os.replace, `.v<old>.bak.csv` backup, sidecar refresh). v1→v4 were append-only so there are zero registered migrations → pure pass-through, **no data change** (current v4 file → `status="current"` no-op). +7 tests. Replay byte-identical, 1362 tests, 146/146 health.
- [x] **P2.7** — Platt freshness check (commit `6b51ff4`). Adapted (no JSON artifact): added machine-readable `PLATT_FIT_DATE="2026-05-01"` constant in `calibrated.py` next to PLATT_A/B; health_check §21 warns (advisory, never blocks) when age > `PLATT_MAX_AGE_DAYS=60`, pointing to the H3/calibration-log refit path. Currently 47d → PASS fresh; auto-fires ~2026-06-30. Verified both branches. Additive constant → replay byte-identical, 146/146 health, 1356 tests.
- [x] **P2.3** — BM-shrinkage target documented (commit `93c86a9`). The decision was **already consistently implemented**: anchor = **vigged** single-side quote (`apply_bm_shrinkage`, props only); EDGE measured vs **no-vig** everywhere (props `calc_edge`→`no_vig`; game lines explicit `no_vig()`). Documented the anchor choice + rationale in the `apply_bm_shrinkage` docstring and `MARKET_FOUNDATIONS.md` §9F-bis. **Flagged (DATA_GATED, P2.3b):** the vigged anchor injects a residual edge `(1−w)·half-vig`, larger for low-w tiers (T3 ~0.71pp at −110, T2 ~0.36pp) — BM theory anchors on no-vig (p_true), so no-vig is the correct anchor; switching needs `nv_prob` threaded into `apply_bm_shrinkage` (signature change, pricing change, replay-able since props are in-snapshot). Revisit with §B BM-direction-inverted at n≥150/family CLV. Doc-only → replay byte-identical, 1356 tests.
- [x] **Task B** — gate hardening (commit `9663c2c`). `gate_check.py`: Calibration Platt now requires **≥10 distinct graded days** (`CALIBRATION_MIN_DAYS`) in addition to 100 rows — a single big slate (2272 rows / 1 day) no longer "opens" it. H3 row in the table annotated **SUPERSEDED** (carded sample ~90% one-directional → use Calibration Platt). +3 tests in `tests/test_calibration_log.py`. Replay byte-identical, 1356 tests.

### EdgeModel (separate repo C:\Dev\EdgeModel)
- [x] **P2.9** — lineup_fetcher retry/backoff. EdgeModel `e40e033`. `_fetch_with_retry` wraps both the ScoreBoard and per-game BoxScore calls (3 attempts, exponential 0.5/1.0/2.0s); success is zero-latency, exhaustion re-raises so the existing `return {}`/`continue` fallbacks still fire. No test suite in EdgeModel → validated inline (success / transient-recovery / exhaustion / backoff-schedule + graceful `{}`; a live call even hit a real empty-JSON ScoreBoard failure, retried, degraded cleanly). ruff clean.
- [~] **P2.4** — travel/altitude: **DEFERRED (DATA_GATED, July refit)**. Required inputs don't exist: EdgeModel has `days_rest`/B2B (fatigue) but **no travel-distance / altitude / timezone / westward-travel feature**. CLAUDE.md already flags Plan 8 §8C #4 as "Neither in code"; the altitude per-possession multiplier magnitude is uncalibrated (numeric, can't set autonomously). Not built — would be a speculative, unvalidated projection change. Revisit at July refit with schedule-location data + calibrated magnitudes.

### NEXT (recommended)
1. When the calibration log reaches ~10 distinct graded days: run `python engine/calibrate_platt.py --log <calibration log>` (free 2-param), deploy only if cross-day OOS Brier improves — change formula + A/B (`calibrated.py`) + PLATT_SPACE (`thresholds.py`) **together**, with replay + reprice review + sign-off.
2. ~~**P2.2** — no-vig daily-lay baseline~~ **DEFERRED to NBA season** (user decision 2026-06-16). Correct in principle but blocked: daily-lay is NBA-only and the only replay snapshot is MLB+WNBA (no validation route); switching vigged→no-vig raises every leg's edge ~2–3pp vs the fixed `MIN_LEG_EDGE_DAILY=0.025` floor (~doubles the qualifying pool unless the floor is re-tuned — needs data); pick_log lacks opposite-side odds for a historical recompute; NBA is dormant mid-June (10 daily_lay rows total). NB: the in-code "no-vig impossible" comment is **wrong** — `extract_alt_spreads` carries both sides, so two-way same-book de-vig IS feasible. Revisit at NBA resume: capture an NBA snapshot, implement two-way de-vig, tune the compensating floor on live data.
3. Health check is now **145/145** (was 146 in the session-2 brief; environmental/data-conditional, still PASSED + healthy).
4. Flag (separate from Platt): the carded sample is 65/7 under-heavy at 40.3% WR — an under-bet strategy/selection underperformance to watch, not fixable by calibration.

---

## HANDOFF — session 4 (2026-06-18)

### DONE this session (NOT pushed — awaiting review)
- [x] **P2.11** — weekly gate-counter Discord digest (last open Phase 2 task). New standalone module `engine/gate_digest.py` (CLI: `--week`/`--dry-run`/`--repost`). Two sections: **(1)** gate fires this week, tallied from `pick_log_blocked.csv` over the Mon–Sun window (per-gate + per-sport split, top-15 cap, exclusion note for suspension/shadow-routed gates); **(2)** open data-gate progress snapshot, reusing a new **`gate_check.compute_gate_status()`** extraction (one code path with the CLI table — counter values unchanged). Posts to **`DISCORD_GATES_WEBHOOK`**, **blank-default → console-only, never POSTs** (mirrors `DISCORD_GAME_LINES_WEBHOOK`); ops-facing, no `@everyone`; post-once guard (`gate_digest:{mon}`) + `--repost`. ASCII-only console output (Windows cp1252 can't encode emoji; `errors="replace"` on the cp1252-accented blocked log). +12 tests (`tests/test_gate_digest.py`). **Replay byte-identical** (not in pricing path), 1390 tests, health 149/149. Smoke `--dry-run` Section 2 matches `gate_check.py` exactly.
  - **MANUAL FOLLOW-UP (file_guard blocks me):** `secrets_config.py` + `.env.example` are write-protected by `.claude/hooks/file_guard.sh`. The module works today via an `os.getenv("DISCORD_GATES_WEBHOOK")` fallback, but for registry/`summary()`/template discoverability, add by hand: (a) in `secrets_config.py` next to `DISCORD_GAME_LINES_WEBHOOK`: `DISCORD_GATES_WEBHOOK: str = os.getenv("DISCORD_GATES_WEBHOOK", "")` + a `"gates": ("DISCORD_GATES_WEBHOOK", DISCORD_GATES_WEBHOOK)` entry in `_WEBHOOK_REGISTRY`; (b) in `.env.example`: `DISCORD_GATES_WEBHOOK=    # #gate-digest (optional — prints to console if blank)`.
  - **Scheduling (ops, not code):** run Sundays via Task Scheduler *after* `weekly_recap.py`. No `.ps1` added (matches `weekly_recap`'s manual-schedule convention).
- [x] **P2.11a** — verified `count_calibration_days()` counts distinct calendar days (`32d8337`, tests-only). Dedup key is `.strip()`'d (`gate_check.py:77`) so the whitespace-overcount path that opens the Platt gate early is already closed — function correct as-is, no production fix. +2 tests: same-day-twice/whitespace-phantom→1 (overcount guard) and midnight straddle (same-date→1 / adjacent→2, under+overcount guards). Suite 1390→1392, replay byte-identical.

### NEXT (queued, each its own commit/review)
1. **Phase 3** in order: NB_R consumer regression tests → vig/no-vig property tests → versioned Platt artifact dir → pre-commit hook → remaining hygiene.
