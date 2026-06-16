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
- [ ] P1.4 — Fit Combo + MLB Platt (1-param intercept-only until n≥300)
- [ ] P1.5 — Stamp NBA SGP ρ provenance — EdgeModel
- [ ] P1.6 — MLB SGP ρ awaiting-data + n=100/160 alerts
- [ ] P1.7 — Recalibrate VAKE multiplier stack

_Legend: [ ] todo · [~] deferred/partial · [x] done (append commit SHA + date)_

---

## Carried-forward backlog (HANDOFF — next session entry point)

**Execution protocol reminder:** one task = one commit = one review. STOP after each task; show diff + replay (before/after) + test result, wait for "proceed". Mandatory replay diff. No autonomous numeric-threshold changes — surface with evidence. Don't push without being asked. EdgeModel work commits in `C:\Dev\EdgeModel`. Rollback tag `pre-audit-fixes-2026-06` on both repos. Replay: `python replay/run_replay.py` (06-15 MLB+WNBA only — no NBA snapshot). Tests: `pytest --basetemp=C:/Dev/JonnyParlay/.pytest_tmp` (baseline 1330). ruff: `python -m ruff check .` (green baseline).

**Remaining Phase 1:**
- **P1.4 — Combo + MLB Platt fit: DATA-GATED, not runnable now.** Combo 27/100, MLB 28/100 graded rows (need 100). Below the floor — can't fit. Action: wire the fit (1-param intercept-only until n≥300 per research) to fire when the gate opens; until then it stays raw. Verify `evaluators.py:124` fallback.
- **P1.5 — Stamp NBA SGP ρ provenance** (EdgeModel `data/sgp_correlations/nba_rho.json` — add version/fit_date/n_observations/source; JP asserts on load). Metadata only, code-only. Doable next.
- **P1.6 — MLB SGP ρ awaiting-data + alerts** (n=100 sign / n=160 magnitude; empirical-Bayes shrink toward 0.30 prior). Code-only. Doable next.
- **P1.7 — Recalibrate VAKE multiplier stack** (cap compound multiplier at 0.85× OR additive shrinkage; T3 effective stakes should leave the floor). Real sizing task — replay will show T3 stake changes.

**Deferred Phase 0:**
- **P0.3 — prop edge ceiling**: revisit combo-aware after P1.4 (0.10 card-wide cut a 25% POTD + 29 combos).
- **P0.7 — lineup-freshness gate**: EdgeModel lineup_fetcher has no timestamp; CSV-mtime gate or EdgeModel-stamp approach — revisit when EdgeModel in scope.

**Findings surfaced (own fixes, not yet scheduled):**
- **capture_clv.py:1829** — F821 undefined `stat` in CLV single-side fallback (latent NameError). F821 in ruff ignore until fixed.
- **WNBA SIGMA_WNBA['3PM']=0.48** — NBA proxy; empirical min≥20 CV ~0.91 (understates G14/combo σ; props use NB). Monitor.
- **MLB NB_R (HA 13.41 / ER 2.62)** — producer values relief-contaminated; align after applying starts-only to discrete MLB_P stats (extends P1.1).
- **NB_R duplicated** in calibrated.py + sgp_builder.py → the case for the deferred full JSON single-source (P1.3 architecture half).
- **NBA replay snapshot** — capture one when NBA is in season so the harness covers NBA NB_R / props (P1.3 had no NBA coverage).
- **CLAUDE.md is 40,459 chars** (>40k health-check limit) — trim when convenient.

**Phase 2 / Phase 3:** per `JonnyParlay_Fix_Plan_v2.md` tables (not started).
