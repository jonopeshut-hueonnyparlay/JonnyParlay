# Fix Plan Progress

Tracks execution of `JonnyParlay_Fix_Plan_v2.md`. One task = one commit = one review.
Plan file: `C:\Users\jono4\.claude\plans\you-are-executing-dreamy-brooks.md`

## Prerequisites
- [x] P-1 — Replay harness (JonnyParlay-only, byte-identical gate passes) — 7ea16b9 + d565b55 — 2026-06-16
- [x] P-2 — Git tag `pre-audit-fixes-2026-06` (JonnyParlay d565b55 + EdgeModel db906e5) — 2026-06-16

## Phase 0 (P0.1–P0.6; P0.7 deferred)
- [x] P0.1 — Prune CO_LEGAL_BOOKS (18→12; removed 6 exited books; betparx kept — it's 26% of WNBA props in-feed; betmonarch not added — dead Odds API key). Replay byte-identical. — 2026-06-16
- [x] P0.2 — Fix WNBA team_sigmas key mismatch (id→abbrev re-key via WNBA_ID_MAP; WNBA-aware resolution; health_check §16). Was 2 bugs: id-keyed data + TEAM_ABBREV lacks WNBA. — 2026-06-16
- [ ] P0.3 — Add MAX_PROP_EDGE=0.10 prop ceiling — —
- [ ] P0.4 — PLATT_SPACE assertion + startup log — —
- [ ] P0.5 — Bootstrap minimal CI (pytest + ruff) — —
- [ ] P0.6 — Eliminate implied_prob forks (capture_clv + clv_report) — —
- [~] P0.7 — Lineup-freshness gate — DEFERRED (EdgeModel scope)

## Phase 1 (data refits; not started)
- [ ] P1.1–P1.7 — per plan (σ → NB_R → Platt ordering)

_Legend: [ ] todo · [~] deferred/partial · [x] done (append commit SHA + date)_
