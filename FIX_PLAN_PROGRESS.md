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
