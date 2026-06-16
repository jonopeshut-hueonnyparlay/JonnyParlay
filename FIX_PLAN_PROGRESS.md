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
- [ ] P1.2 — WNBA SIGMA_WNBA on min≥20 priced (NB_R stays min≥8) — EdgeModel
- [ ] P1.3 — Align NB_R producer↔consumer to single JSON source — EdgeModel + JonnyParlay
- [ ] P1.4 — Fit Combo + MLB Platt (1-param intercept-only until n≥300)
- [ ] P1.5 — Stamp NBA SGP ρ provenance — EdgeModel
- [ ] P1.6 — MLB SGP ρ awaiting-data + n=100/160 alerts
- [ ] P1.7 — Recalibrate VAKE multiplier stack

_Legend: [ ] todo · [~] deferred/partial · [x] done (append commit SHA + date)_
