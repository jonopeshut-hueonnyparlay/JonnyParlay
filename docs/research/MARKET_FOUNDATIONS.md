# MARKET FOUNDATIONS — Plan 9 Audit

**Date:** 2026-06-06
**Scope:** Market-facing assumptions of the betting engine — NRFI/YRFI model, anti-correlation filters, CLV methodology, SLOW_BOOKS exploitation, parlay construction (Daily Lay / Longshot / SGP), tier system, hard card rules, daily cap structure.
**Method:** Each section's constants/assumptions verified from source (`engine/run_picks.py`, `engine/mlb_sgp_builder.py`, `engine/capture_clv.py`, `engine/clv_report.py`), then validated against published research via 6 parallel Opus web-search agents.
**Companion doc:** `docs/research/STATISTICAL_FOUNDATIONS.md` (Plans 1–6: distributions and projection constants).

**Verdict taxonomy:**
- **LOCKED** — validated; leave alone. Changes must cite evidence overriding this doc.
- **PERIODIC_RECAL** — validated but refit on a stated schedule.
- **DATA_GATED** — cannot validate without more data; gate defined.
- **NEEDS_CHANGE** — evidence contradicts current implementation; fix stated.

---

## Summary Verdict Table

*(populated as sections complete)*

| § | Item | Current | Verdict | Action |
|---|------|---------|---------|--------|

---

## Code-vs-plan-doc corrections (Phase 0 verification, 2026-06-06)

Before research, every constant in the Plan 9 spec was re-read from source. Corrections vs the plan document:

| Item | Plan doc said | Code actually says |
|---|---|---|
| `MIN_LEG_WIN_PROB` (MLB SGP) | 0.60 | **0.65** (mlb_sgp_builder.py:70) |
| `CLV_REFORM_DATE` | in capture_clv.py | **clv_report.py:57** = "2026-05-31" |
| `--late-run` flag | run_picks.py | lives in **EdgeModel** generate_projections.py; only the `SLOW_BOOKS` frozenset is in run_picks.py:795 |
| Daily Lay leg count | 3-leg | code builds **2–4 legs** (run_picks.py:4250–4299) |
| X2 filter (K over + HITS over) | "verify status" | **confirmed retired/absent** — only X1 exists in filter_cross_type_correlations() |

All other plan-doc values matched code exactly (NRFI constants, YRFI min_edge, Daily Lay thresholds, longshot caps, tier mults, 12u/sport caps, SGP odds window, CLV capture windows).

---

## §9A — NRFI Model

**Current implementation** (run_picks.py:3523–3647):
- Poisson λ model: `λ_team = BASE_LAMBDA_1ST × (pitcher_blended_rate / 0.477) × (team_runs / 4.45)`; `P(NRFI) = exp(−λ_away − λ_home)`
- `BASE_LAMBDA_1ST = 0.32` (avg matchup → P(NRFI) ≈ 53%); `_LEAGUE_AVG_BLENDED_RATE = 0.477` (0.40×ERA/9 + 0.60×FIP/9); `_LEAGUE_AVG_RUNS = 4.45`
- Park factor intentionally omitted (SaberSim team-run inputs already park-adjusted)

*(findings pending — agent A)*

---

## §9I — YRFI Model

**Current implementation** (run_picks.py:3648, 3694, 3888–3890):
- `p_yrfi = 1.0 − p_nrfi`; YRFI min_edge = 0.08 vs NRFI min_edge = 0.06 (T3 floor)
- R5 dedup: NRFI + YRFI same game never both posted (lower pick_score dropped)

*(findings pending — agent A)*

---

## §9B — MLB Anti-Correlation Filter (X1)

**Current implementation** (run_picks.py:3933–3978):
- X1 (HARD): pitcher HA/ER UNDER + opposing TEAM_TOTAL OVER same game → pair killed from parlay/longshot pool (assumed ρ ≈ −0.65 to −0.75)
- X2 retired with K stat. SGP-module kills (R2_MLB) are separate.

*(findings pending — agent B)*

---

## §9C — CLV Capture Methodology

**Current implementation** (capture_clv.py:16–18, 168–171; clv_report.py:57):
- Window: T−45 min → T+3 min capture; CLV written only within T−10 of start; 2-min poll
- Post-reform (CLV_REFORM_DATE=2026-05-31): CLV = vig-free closing prob − raw vigged entry implied. Vig-free computed on the closing side only (proportional devig over both sides of the closing market).

*(findings pending — agent C)*

---

## §9D — SLOW_BOOKS Exploitation

**Current implementation** (run_picks.py:795):
- `SLOW_BOOKS = {"fanatics", "hardrockbet", "betrivers"}` — assumed 15–40 min injury-news repricing lag; exploited via EdgeModel `--late-run` re-fetch. Lag estimates assumed, not measured.

*(findings pending — agent D)*

---

## §9E — Daily Lay Architecture

**Current implementation** (run_picks.py:192–199, 4250–4299, 5140–5165):
- 2–4 leg alt-spread parlay; MIN_DAILY_LAY_PROB=0.50 (combined); per-leg edge ≥0.025, cover_prob ≥0.58, projected margin ≥4.0; max combined odds +100; quarter-Kelly sizing clamped 0.25–0.75u

*(findings pending — agent E)*

---

## §9F — Tier System Design

**Current implementation** (run_picks.py:729, 1214–1221):
- T1 (AST/SOG/REC/HRR) min_edge=0.03 mult=0.90 · T1B (REB/HITS/HA high-line unders) 0.03/0.93 · T2 (PTS/PRA/OUTS/SV/…) 0.05/1.00 · T3 (3PM/GOALS/NRFI/YRFI/ML_DOG/…) 0.06/0.95
- pick_score = 0.40·wp_n + 0.60·e_n, e_n capped at 100 (15% edge ceiling)
- Performance (2026-05 gate audit, plan-supplied): T1 46.6% WR/−10.2% ROI · T1B 46.9%/+1.7% · T2 60.3%/+14.0% · T3 51.5%/+5.3%

*(findings pending — agent F)*

---

## §9G — Longshot Parlay Construction

**Current implementation** (run_picks.py:200–202, 4136–4233):
- 6 legs, safest-by-win_prob descending; max 2 legs/game, 1 leg/player; flat 0.25u; legs treated as independent (no copula). VALUE_PARLAY 5-leg fallback, same caps, 0.25u.

*(findings pending — agent E)*

---

## §9H — SGP Thresholds

**Current implementation** (mlb_sgp_builder.py:65–71, 199–223, 303–318):
- 3–4 legs; per-leg WP ≥0.65 (OUTS ≥0.62); combined odds +200–+450; Gaussian copula joint prob (ρ table: OUTS-over+opp-HITS-under=0.30, same-team batters=0.15, two pitchers=0.10, cross-team batters=0.08, default 0.02)
- Premium 0.50u iff copula EV margin ≥0.10 AND avg_edge ≥0.035; else 0.25u. R2_MLB kill: OUTS-under + HITS-under same game.

*(findings pending — agent E)*

---

## §9J — Hard Rules (R4/R7/R9/R10/R12)

**Current implementation** (run_picks.py:1544–1750, 1602, 6723–6730):
- R4: REB overs (and REB unders ≤2.5) → shadow log, not posted
- R7: max 2 picks/game per card (default arg)
- R9: directional balance — if ≥3 overs passed gates but 0 on premium card, force best over in
- R10: max 1 pick per stat on Premium 5
- R12: 5-day cooldown on players whose pick lost (auto-merged from pick_log)

*(findings pending — agent F)*

---

## §9K — Daily Unit Cap Structure

**Current implementation** (run_picks.py:733, 1763–1782):
- Daily total cap 12u (all run types); SPORT_UNIT_CAP per pick: NBA=8, MLB=8, NHL=5, NFL=5, WNBA=4; STAT_CAP default 2/run (SOG 6)
- KELLY_FRACTION=6.0 on 100u convention ⇒ ≈1/16.7 Kelly; sizes rounded 0.25u, floor 0.50u (0.25u T3)

*(findings pending — agent F)*
