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

**Counts: 24 LOCKED · 9 PERIODIC_RECAL · 13 DATA_GATED · 12 NEEDS_CHANGE** (NEEDS_CHANGE detail in the table below and per-section verdict tables; none shipped in this session — all await explicit decision).

| § | Item | Current | Verdict | Action |
|---|------|---------|---------|--------|
| 9A | NRFI game-level baseline (53%) | λ=0.32/team | LOCKED | Matches published 52–55% |
| 9A | **NRFI Poisson elasticity** | exp(−0.32·m) | **NEEDS_CHANGE** | NB overdispersion ⇒ elasticity ~50–60% too steep (±2pp at extremes). NB zero-prob or m^γ (γ≈0.6–0.7); validate on in-house 8,095 games first |
| 9A | **ERA/FIP blend** | 0.40/0.60 | **NEEDS_CHANGE** | r² ratios (ERA 0.019 / FIP 0.038 / xFIP 0.061) ⇒ ≤25% ERA / ≥75% FIP, prefer xFIP/FIP− (also fixes pitcher-side park bias). July refit |
| 9A | Lineup slots 1–3 λ adjustment | absent | DATA_GATED | Backtest top-3 wOBA vs team-R/G in-house before adding |
| 9A | Park omission · λ level · 4.45 R/G | — | LOCKED · PERIODIC_RECAL ×2 | Annual April refit from 1st-inning zero rate |
| 9A | λ home/away independence + symmetry | independent, same base | DATA_GATED | Measure φ + bottom-1st premium (0.6 vs 0.5 runs) in-house |
| 9I | P(YRFI)=1−P(NRFI) · min_edge 0.08 · R5 dedup | — | LOCKED ×3 | FLB-supported differential; revisit after elasticity fix |
| 9B | X1 hard block + ER ρ band | −0.65/−0.75 | LOCKED | Optimal at engine edge scale (breakeven needs 11–20%/leg edges) |
| 9B | X1 HA ρ band | −0.65/−0.75 | PERIODIC_RECAL | Overstated; ≈−0.45/−0.60. Re-document + in-house fit at July refit; no behavior change |
| 9B | Positive-ρ pairs in longshot pool | independent | NEEDS_CHANGE (minor) + DATA_GATED ×3 | Optional +ρ for ranking honesty; in-house corr fits; check NBA over+TOTAL-under co-occurrence |
| 9C | CLV formula (devig close − raw entry) | post-reform | LOCKED | **Suspected defect inverted — formula is published best practice.** Never pool pre/post-reform rows |
| 9C | Capture window · devig method | T−45→T+3, mult | LOCKED ×2 | Harden: discard post-commence snapshots (live-odds contamination) |
| 9C | CLV go-live gate | n=100 | DATA_GATED | Add one-sided t-test (t≥1.7) on post-reform rows; +0.4pp avg ⇒ ~150–200 rows |
| 9C | Prop CLV validity | soft-book closes | PERIODIC_RECAL | Subordinate to graded W/L; consider multi-book consensus close |
| 9D | Slow-books premise · sustainability | assumed | PERIODIC_RECAL ×2 | Props-specific (20–40 min documented); account-eroding via limits — log limit events |
| 9D | SLOW_BOOKS membership + 15–40 min lag | hardcoded | DATA_GATED ×2 | Unvalidated (Fanatics counter-evidence); event-study or ~50 late-run CLV rows/book |
| 9D | Legality (CO, public news) | — | LOCKED | Legal; known commercial risks: limiting + Rule 6.10 voids. **Ops note: SB26-131 deposit rules effective 2026-08-12** |
| 9E | Daily Lay structure · thresholds · sizing | 0.50/+100/0.25–0.75u | LOCKED ×4 | +7–10% EV by construction at boundary; 0.58 floor = anti-barbell guard (doc fix); align "3-leg" docs to 2–4 |
| 9E | Daily Lay validation | 0 graded | DATA_GATED | n=20 leg-level calibration gate (spec in §9E Q5) |
| 9G | **Longshot leg ranking** | win_prob desc | **NEEDS_CHANGE (low priority)** | EV-factor ranking with WP≥0.60 floor, OR re-document as hit-frequency product — pick one |
| 9G | Flat 0.25u · 6/5 legs | — | LOCKED ×2 | Don't raise sizing without data (spans 8–71% of full Kelly) |
| 9G | Same-game independence | max 2/game + kills | PERIODIC_RECAL | Opportunistic SGP-ρ reuse in build_safest6_parlay() |
| 9H | **SGP existence gate** | per-leg floors only | **NEEDS_CHANGE** | Add joint-EV floor: copula margin > +0.02–0.03 for ANY slip (4-leg path can currently construct −EV slips) |
| 9H | Odds window +200–+450 | hard window | PERIODIC_RECAL | 3-leg consistent; 4-leg safe only with joint-EV floor |
| 9H | Premium gate ≥0.10 | premium sizing | LOCKED | ≈+45% ROI condition vs 16–25%+ SGP hold |
| 9H | MIN_LEG_WIN_PROB_OUTS=0.62 | tuned to old σ | DATA_GATED | Monitor at n≥40 graded OUTS legs; σ-equivalent floor ≈0.64 if retune fires |
| 9F | **T1 framing + floors** | "conviction" tiers, 0.03 floor | **NEEDS_CHANGE** | Reframe as stat-routing buckets; floors monotone in calibration quality; restructure now (population already changed) |
| 9F | **T1 0.90× mult + n=30 checkpoint** | stake-only fix | **NEEDS_CHANGE** | Replace with per-family probability shrinkage (Baker–McHale); retire mult + checkpoint; merge with Kelly-stack consolidation item |
| 9F | T1B class | 0.03 floor | DATA_GATED | Bootstrap ROI>0 at n≥100; no expansion before |
| 9F | T3 floor 0.06 | — | LOCKED/PERIODIC_RECAL | Re-derive annually from measured T3 overround |
| 9J | R4 REB-over shadow | no lift condition | DATA_GATED | Pre-register: n≥50 post-refit, calib bias ±3pp, CLV≥0 |
| 9J | R7 max-2/game · R10 same-stat cap | hard caps | LOCKED ×2 | R10 best-justified rule in system |
| 9J | **R9 directional balance · R12 cooldown** | EV-framed | **NEEDS_CHANGE (reclassify, doc-only)** | Label both product rules; monitor R9 score-gap cost; R12 → negative-CLV trigger when data matures |
| 9K | 12u daily cap | ≈0.2–0.3 joint Kelly | LOCKED | Correct conservative side; revisit at NFL go-live |
| 9K | Sport per-pick caps | never bind | PERIODIC_RECAL | Relabel backstops or convert to per-sport daily budgets |
| 9K | **0.50u stake floor** (adjacent) | floors 0.20–0.26u → 0.50u | **NEEDS_CHANGE** | Over-stakes weakest picks 2–2.5× vs own Kelly logic; lower to 0.25u or skip below ~0.35u |

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

### Q1 — Poisson validity + 53% baseline
The **53% game-level baseline is well supported**: published references state ~52–55% of MLB games have a scoreless 1st ([OddsIndex NRFI guide](https://oddsindex.com/guides/nrfi-betting-guide)); Odds Shark 2026 team records and NRFI-Central's 2024 recap bracket the same center. (Caution: the "~70% NRFI average" floating in the literature is the per-team-offense scoreless rate, ~70–73% — a different stat; the engine uses the correct game-level definition.) The 1st is the highest-scoring inning (~5.1 R/9; highest in 91% of seasons since 1945, MLB.com) — a first-inning-specific baseline is required and BASE_LAMBDA_1ST does this correctly.

**However, Poisson is formally the wrong family for per-inning runs.** Woolner ([BP per-inning model](https://legacy.baseballprospectus.com/images/analytica/rpi_model.pdf)) and Dolinar both show per-inning runs are **overdispersed (var ≈ 2× mean)**. The engine sidesteps this *at the baseline* — λ=0.32 is not the true 1st-inning mean (~0.50–0.55 runs/team) but an **effective zero-rate parameter** (e^−0.32 = 0.726 matches the empirical scoreless rate); that's a legitimate log-linear model of P(0). The residual error is the **elasticity**: under the engine, d ln P(scoreless)/d ln(mult) = −0.32; under an NB matched to the 1st inning's mean (~0.55) and zero rate (0.726), implied r ≈ 0.31 and elasticity ≈ −0.20 — the Poisson λ-scaling is **~50–60% too steep**. A strong pitching matchup (mult ~0.8/side) over-predicts P(NRFI) by ~+2pp; symmetrically under-predicts YRFI in high-offense matchups. With min_edge floors 0.06/0.08, a systematic ±2pp tilt at exactly the extremes where picks fire is material.
**Verdict: LOCKED (baseline) / NEEDS_CHANGE (elasticity).** Fix: (a) NB zero-probability `(r/(r+μ·m))^r` with r fit to first-inning data, or (b) cheaper, exponent dampener `P(scoreless) = exp(−0.32·m^γ)`, γ ≈ 0.6–0.7 — validate against the in-house 8,095-game DB (bucket by predicted multiplier, compare realized NRFI rate per bucket).

### Q2 — ERA/FIP 40/60 blend + lineup quality
Literature unambiguously favors FIP-family estimators for *future* run prevention: predictive ranking cFIP > kwERA > SIERA > xFIP > FIP > ERA (Judge/BP via [Pitcher List](https://pitcherlist.com/the-relative-value-of-fip-xfip-siera-and-xera-pt-ii/)); [FanGraphs month-ahead r²](https://fantasy.fangraphs.com/quick-all-star-break-study-3-month-to-month-correlation-for-era-and-related-stats/): **ERA 0.019, FIP 0.038, xFIP 0.061** — ERA half as predictive as FIP, a third of xFIP. 40/60 gives ERA 2–4× the weight predictive-validity ratios justify; literature-consistent is **≤25% ERA / ≥75% FIP** (better: xFIP/SIERA). Damage bounded (rates correlate ~0.7+ within-season) but concentrates on high-BABIP/strand-rate outliers — exactly the pitchers NRFI models mis-rate.
First-inning-specific: league 1st-inning ERA ~4.86 vs ~4.51 overall (+8%, absorbed by BASE_LAMBDA_1ST — no double-count). But team full-game R/G is a weak proxy for **lineup slots 1–3** (the only guaranteed PAs); commercial NRFI models build λ from leadoff OBP / top-3 wOBA vs L/R. 2023 Braves scored in the 1st 39.16% vs league ~27% — dispersion driven by top-of-order quality that team R/G dilutes. Lineup-slot adjustment plausibly worth more than the ERA/FIP weighting choice.
**Verdict: NEEDS_CHANGE (blend → ≥75% FIP, prefer xFIP/FIP−, July refit) + DATA_GATED (lineup-slot upgrade — backtest top-3 wOBA λ-adjustment on in-house `mlb_batter_game_stats` first).**

### Q3 — Park factor omission
Valid on the team-runs side (SaberSim inputs park-adjusted; double-applying would double-count Coors ~1.35–1.42×). **No published evidence of a first-inning-specific park effect** distinct from full-game factors — park effects are physical and inning-invariant. One residual inconsistency on the **pitcher side**: raw ERA (and FIP's HR component) embeds the pitcher's own park un-neutralized — a Coors home pitcher is penalized twice. Fixed for free by the Q2 swap to park-adjusted FIP−/xFIP.
**Verdict: LOCKED** (omission itself), with the pitcher-side note folded into Q2's fix.

### Q4 — BASE_LAMBDA_1ST=0.32 level
Triangulated: (a) per-team-offense scoreless rates cluster ~70–73% → scoring ~27–30%; (b) best 1st-inning offense 2023 (Braves) scored in only 39.16% — consistent with league mean ~27–28%; (c) 1−e^−0.32 = 27.4%/team → e^−0.64 = 52.7% game NRFI, matching published 52–55%; (d) true mean ~0.55 with ~72–73% zero rate confirms overdispersion (true-Poisson 0.55 would give 57.7% scoreless — empirically false), validating zero-rate calibration over mean-runs calibration. Also verified: `_LEAGUE_AVG_RUNS=4.45` matches 2025 (NL 4.47/AL 4.42); 0.477×9 = 4.29 ≈ 2025 league ERA — units coherent.
**Verdict: PERIODIC_RECAL** — recalibrate each April from prior-season first-inning zero rate (one SQL query on in-house `mlb_games`; league R/G swung 4.28→4.62→4.39→4.45 over 2022–25).

### Q5 — Independence of λ_away and λ_home
No published study quantifies top-vs-bottom-1st scoring correlation. Mechanistically small **positive** ρ (shared park/weather/ump zone — SABR umpire analytics) ⇒ P(both scoreless) > product ⇒ independence slightly **under-prices NRFI** (conservative on NRFI side, slightly aggressive on YRFI). Plausible ρ ≈ +0.02–0.05 (engine's own NBA full-game ρ=+0.227 is an upper bound for 9× the exposure window) — worth ≤1pp. Separate, better-documented: **bottom of 1st averages 0.6 runs vs 0.5 top** (130k games, [FanGraphs Community](https://community.fangraphs.com/why-are-so-many-runs-scored-in-the-bottom-of-the-first-inning/)) — a ~15–20% home-side λ asymmetry the engine doesn't model (same 0.32 base both sides).
**Verdict: DATA_GATED** — both effects measurable from in-house `mlb_games` (φ-coefficient between top/bottom 1st scoring; residual home λ premium net of team quality) before parameterizing.

### §9A Verdicts

| Item | Current | Verdict | Action |
|---|---|---|---|
| Game-level baseline (53%, λ=0.32/team) | exp(−0.64) | LOCKED | Matches published 52–55% |
| Poisson elasticity | exp(−0.32·m) | NEEDS_CHANGE | NB-overdispersion ⇒ elasticity ~50–60% too steep, ±2pp at pick-firing extremes. NB zero-prob or m^γ (γ≈0.6–0.7) dampener; validate in-house |
| ERA/FIP blend | 0.40/0.60 | NEEDS_CHANGE | Shift to ≤0.25 ERA / ≥0.75 FIP (prefer xFIP/FIP−) at July refit |
| Lineup slots 1–3 adjustment | absent | DATA_GATED | Backtest top-3 wOBA vs team-R/G proxy in-house before adding |
| Park factor omission | omitted | LOCKED | Valid; pitcher-side park bias fixed by FIP−/xFIP swap |
| BASE_LAMBDA_1ST level | 0.32 | PERIODIC_RECAL | Annual April refit from prior-season 1st-inning zero rate |
| _LEAGUE_AVG_RUNS | 4.45 | PERIODIC_RECAL | Confirmed vs 2025; update annually |
| λ independence + home/away symmetry | independent, same base | DATA_GATED | Measure φ + bottom-1st premium (0.6 vs 0.5) in-house |

---

## §9I — YRFI Model

**Current implementation** (run_picks.py:3648, 3694, 3888–3890):
- `p_yrfi = 1.0 − p_nrfi`; YRFI min_edge = 0.08 vs NRFI min_edge = 0.06 (T3 floor)
- R5 dedup: NRFI + YRFI same game never both posted (lower pick_score dropped)

### Q6 — Complement validity
Confirmed. Outcome space is binary ("≥1 run in inning 1" vs "0") — **no push possible**. Settlement: NRFI settles at the 3rd out of the bottom of the 1st; postponed/suspended games not resumed within the book window (DK/MGM/FD: 36h) void both sides symmetrically — complement identity survives. Only asymmetric corner: game called mid-1st *after* a run may grade YRFI win while NRFI voids at some books — rare and bettor-favorable; no model change. **Verdict: LOCKED.**

### Q7 — YRFI min_edge 0.08 vs NRFI 0.06
Directionally well-founded. [Snowberg & Wolfers (JPE 2010)](https://www.nber.org/papers/w15923) confirm favorite-longshot bias (longshots overbet, misperception-driven): YRFI is the recreational plus-money "action" side, so quoted YRFI odds embed more adverse shade — a model edge there is more likely model error colliding with a deliberately shaded price. At +110/+160 (implied 38–48%) FLB magnitude is modest, so the 2pp differential is proportionate. Secondary supports: higher per-bet variance at plus odds, and the Q1 elasticity error *over-states* YRFI probability in high-offense matchups — the higher floor partially hedges a known model bias.
**Verdict: LOCKED.** Revisit if the Q1 elasticity fix ships (it removes the main YRFI-side bias being hedged); keep ≥0.01 differential for FLB regardless.

### Q8 — R5 dedup
Correct: ρ = −1 by construction; within one book both sides can't be simultaneously +EV (implied probs sum >1 with vig). Nuance: across **two books**, NRFI@A and YRFI@B can both clear floors — that's a cross-book arb/middle signal, not a contradiction. Optional: log the dropped side to pick_log_blocked.csv as `R5_ARB_CANDIDATE` when both passed gates at different books — free market-disagreement information.
**Verdict: LOCKED.**

### §9I Verdicts

| Item | Current | Verdict | Action |
|---|---|---|---|
| P(YRFI)=1−P(NRFI) | complement | LOCKED | Binary exhaustive; void rules symmetric |
| YRFI min_edge 0.08 vs 0.06 | +2pp plus-money side | LOCKED | FLB-supported (Snowberg & Wolfers 2010); revisit after elasticity fix, keep ≥1pp |
| R5 dedup | drop lower score | LOCKED | Optional: tag cross-book dual-qualifies as arb candidates |

---

## §9B — MLB Anti-Correlation Filter (X1)

**Current implementation** (run_picks.py:3933–3978):
- X1 (HARD): pitcher HA/ER UNDER + opposing TEAM_TOTAL OVER same game → pair killed from parlay/longshot pool (assumed ρ ≈ −0.65 to −0.75)
- X2 retired with K stat. SGP-module kills (R2_MLB) are separate.

### Q1 — Is ρ ≈ −0.65 to −0.75 the right magnitude?
No published source gives the exact game-level corr(SP HA/ER, opp full-game runs) — DFS correlation tools and SGP pricing keep it behind paywalls. Variance decomposition bounds it:
- SP innings share: **5.22 IP/start (2024)** ≈ 58% of a 9-inning game ([AP/FanGraphs](https://blogs.fangraphs.com/a-deeper-dive-into-pitcher-usage-trends/)); ρ(runs-off-SP, total runs) ≈ √0.58 ≈ 0.76 (opposing adjustments — early hooks vs shared run environment — roughly cancel).
- Hits→runs linkage: season-level BA→runs r≈0.82 ([Bucknell study](https://www.eg.bucknell.edu/~bvollmay/baseball/runs1.html)); game-level conventionally ~0.65–0.75 (sequencing noise).
- **ER**: ρ ≈ 0.95 × 0.76 ≈ **0.65–0.75** ✅ — engine's band is plausible for ER.
- **HA**: extra hits→runs translation step ⇒ ρ ≈ 0.70 × 0.76 ≈ **0.45–0.60** ❌ — engine's band overstated by ~0.10–0.20 for HA.
- Materiality: **zero for behavior** — X1 is a hard block, and even ρ=−0.45 destroys parlay joint EV at engine edge scale (Q4). Note: the in-house DB can settle this exactly — `mlb_pitcher_game_stats` (69k rows) × `mlb_games` final scores in one query.

**Verdict: LOCKED** (ER band) / **PERIODIC_RECAL** (HA band — re-document as ≈ −0.45 to −0.60; fit empirically in-house at July refit; no behavior change).

### Q2 — Sign + hard-block treatment
Sign confirmed. Books historically blocked correlated parlays outright and now reprice them inside SGP engines via copulas ([Wizard of Odds — SGP correlation math](https://wizardofodds.com/article/same-game-parlays-the-mathematics-of-correlation/), OpticOdds, USPTO 12,080,130). Crucially, books do **not** pay proportionally higher odds for negatively correlated combos — so a bettor-side pool pricing payout as independent-product while true joint prob is copula-reduced is structurally −EV on such pairs. Hard exclusion is the correct bettor-side treatment. **Verdict: LOCKED.**

### Q3 — Other anti-correlation candidates (unblocked)
- **(a) OUTS over + same-SP HA over**: exposure effect (more BF → more hits) vs the hook (high hit rates → pulled early) largely cancel; expected |ρ| < 0.2. **DATA_GATED** — compute corr(outs, hits_allowed) on 16k starts in-house before any rule; likely no rule needed.
- **(b) OUTS under + opp TT over**: **positively** correlated (~+0.3–0.4 — SP knocked out early *because* opp scoring). Independence **understates** joint prob → engine under-ranks/under-sizes a combo that's actually better than modeled. Conservative, not dangerous. Key asymmetry: independence on negative-ρ pairs overstates EV (must block — X1 does); on positive-ρ pairs it understates EV (safe to allow). **NEEDS_CHANGE (minor, optional)**: add a +ρ term to the longshot joint-prob estimate for ranking honesty, mirroring mlb_sgp_builder's OUTS-over/HITS-under=+0.30. Never block.
- **(c) ER under + same team ML**: positive ρ ~+0.35–0.45 (NFL analogue: Team Win ↔ QB over ρ=0.35, Wizard of Odds). Independence conservative. **DATA_GATED** — fit in-house, fold into copula when convenient; no block.
- **(d) NBA player PTS/3PM over + same-game TOTAL under** (ρ ≈ −0.2 to −0.4): the most material *unblocked negative* pair if NBA props and totals co-occur in the longshot pool. **DATA_GATED** — check pick_log for actual co-occurrence in longshot legs before adding an NBA X2; per-game cap of 2 bounds exposure. NHL pairs weak/moot (SOG suspended).

### Q4 — Hard block vs copula soft-pricing
Two contexts, and the engine's architecture already splits them correctly:
1. **Parlay (multiplicative payoff)**: at ρ=−0.5, two p=0.60 legs have joint 0.30 vs 0.36 independent (damage ≈0.81) → each leg needs **>~11% edge** to survive; at ρ=−0.65/−0.75, **~16–20% edge**. Engine prop edges run 3–8% — an order below breakeven. A copula soft gate would re-admit essentially zero pairs while adding model risk.
2. **Straight-bet portfolio**: negative correlation *reduces* variance — simultaneous-Kelly theory ([Whitrow 2007 JRSS-C](https://vegapit.com/article/numerically_solve_kelly_criterion_multiple_simultaneous_bets/); Baker & McHale 2013) says negatively correlated straights can size *up*. X1 kills the pair only from the parlay pool while both legs stay available as straights — exactly the optimal split. (Corollary: straight-pick Kelly treats same-game positive-ρ picks as independent, slightly oversizing — swamped by the 0.25u quantization and ~1/16.7 Kelly scaling.)

**Verdict: LOCKED** — hard block is not too conservative at this engine's edge scale.

### §9B Verdicts

| Item | Current | Verdict | Action |
|---|---|---|---|
| X1 hard block (HA/ER under + opp TT over) | HARD kill | LOCKED | None — sign correct, treatment standard, optimal at engine edge scale |
| X1 documented ρ for ER | −0.65 to −0.75 | LOCKED | Plausible (0.95 × 0.76 ≈ 0.72) |
| X1 documented ρ for HA | −0.65 to −0.75 | PERIODIC_RECAL | Overstated; true ≈ −0.45 to −0.60. Re-document + in-house fit at July refit. No behavior change |
| OUTS over + same-SP HA over | Unblocked | DATA_GATED | In-house corr on 16k starts; expected \|ρ\|<0.2 → no rule |
| OUTS under + opp TT over | Independent | NEEDS_CHANGE (minor) | Positive ρ understates joint prob (conservative). Optional +ρ in longshot joint-prob; never block |
| ER under + same team ML | Independent | DATA_GATED | ρ ~+0.35–0.45; fit in-house, fold into copula later |
| NBA player-over + TOTAL-under | Unblocked | DATA_GATED | Check pick_log co-occurrence before adding NBA X2 |
| Hard block vs copula | Hard block | LOCKED | Breakeven needs 11–20% per-leg edges; engine has 3–8% |

---

## §9C — CLV Capture Methodology

**Current implementation** (capture_clv.py:16–18, 168–171; clv_report.py:57):
- Window: T−45 min → T+3 min capture; CLV written only within T−10 of start; 2-min poll
- Post-reform (CLV_REFORM_DATE=2026-05-31): CLV = vig-free closing prob − raw vigged entry implied. Vig-free computed on the closing side only (proportional devig over both sides of the closing market).

### Q1 — Window and write gate
Published consensus (Miller/Davidow *The Logic of Sports Betting*; Buchdahl's Pinnacle efficiency study, 87,960 odds pairs): the close = the last price before the event starts. No published standard exists for a T+3 tail — it's a pragmatic guard against feed/clock skew. With a 120s poll, the last pre-suspension snapshot is within ~2 min of the true close — well inside literature precision. The T−10 write gate captures exactly the window the literature treats as the close.
**One real risk**: markets that flip to in-play at start (totals/spreads especially) — a T+0→T+3 snapshot can return **live odds**, which are not the close. Props are usually delisted at start (benign failure: missing close), but game lines are not.
**Verdict: LOCKED**, with one hardening item: discard (or use only as last-resort fallback) any snapshot with capture_time > commence_time.

### Q2 — Mixed devig formula: NOT a pitfall (the suspected defect is inverted)
The plan hypothesized that devigged-close-minus-raw-entry systematically shifts CLV positive. **The premise is inverted — the current formula is the methodologically correct EV estimator, and it shifts CLV *negative* (conservative).**
- Math: realized EV per unit = p_true × d_entry − 1 > 0 ⟺ p_true > raw vigged entry implied. Best estimate of p_true = devigged close. So **CLV = devig(close) − raw(entry)** has its zero point exactly at zero EV — the engine's post-reform formula.
- Buchdahl: "if you are beating the closing no-vig-price, your bets should hold expected value" — validated on his ~20,000-bet record (realized 3.4% vs expected 4.0%). [Unabated "Getting Precise About CLV"](https://unabated.com/articles/getting-precise-about-closing-line-value): "If you don't compare your bet against a vig-free closing line, you're misrepresenting your CLV" — i.e., the pitfall is raw-vs-raw, and **devig-both would be the error** (puts the zero at "no line movement", overstating edge by the entry vig share ~2.3pp at −110).
- A bet whose line never moves shows CLV ≈ −2.4pp under the current formula — correctly flagging that betting into a static vigged market is −EV by the vig.
- Bookkeeping caveat: pre-reform rows (raw close) sit ~+2–2.5pp relative to post-reform rows — **never pool across CLV_REFORM_DATE** in one mean; the go-live count should include only post-reform rows.
**Verdict: LOCKED.** No formula change.

### Q3 — Devig method (multiplicative vs power vs Shin)
Methods diverge with odds asymmetry, not vig level. At −110/−110 identical; at −150/+120 (~5.4% overround) mult vs power differ ~0.3pp. Published ~1pp divergences come from 1.25/4.20-style lopsided markets — far beyond any priced prop. **Verdict: LOCKED** for the prop/total population; **PERIODIC_RECAL trigger**: switch to power devig if CLV is ever computed on |odds| ≥ 200 markets (ML dogs, alt lines).

### Q4 — Significance at small n (the math)
Buchdahl/Pinnacle: CLV separates skill from noise far faster than W/L ("as few as 50 bets" — but conditional on ~4% effect size). For this engine, in probability points (t = x̄√n/σ):

| avg CLV | σ/bet | n | t | p (two-sided) |
|---|---|---|---|---|
| +0.004 | 0.025 | 63 | 1.27 | 0.21 |
| +0.004 | 0.025 | 100 | 1.60 | 0.11 |
| +0.004 | 0.020 | 100 | 2.00 | 0.046 ✓ |
| +0.010 | 0.025 | 100 | 4.00 | <0.001 ✓ |

n for t=1.96 at x̄=+0.4pp: **96 / 150 / 216** at σ = 2.0/2.5/3.0pp — the 100-row gate sits exactly at the edge. Caveats: same-slate picks have correlated line moves (deflates effective n; t is anti-conservative), and the statistic must use post-reform rows only.
**Verdict: DATA_GATED** — at gate time, augment the fixed n=100 with a one-sided t-test (t ≥ ~1.7) on post-reform rows. At +0.4pp expect ~150–200 rows needed; at +1pp, ~25–40.

### Q5 — Prop CLV vs soft-book closes
The weakest link, well documented. Jack Andrews (Unabated): "**CLV doesn't mean anything in props**… very few market-making books… not a lot of sharp money… that makes it less efficient." Buchdahl's slope≈1.00 CLV→realized-EV result was proven on **Pinnacle soccer mainlines**; no equivalent validation exists for DK/FD/MGM prop closes. Counterweight: FD has sharpened on props via volume, and prop closes do absorb injury news — soft-book prop CLV is *directionally* informative but noisy. Implications: (a) per-bet CLV SD larger → Q4 t-test is a floor; (b) graded shadow W/L must carry ≥ equal weight in the go-live decision (parallel shadow grading already does this); (c) a **multi-book consensus devigged close** is strictly better than single-book when ≥2 books quote the prop.
**Verdict: PERIODIC_RECAL** — keep capturing; treat the CLV gate as supporting evidence subordinate to graded W/L; consider consensus-close upgrade.

### §9C Verdicts

| Item | Current | Verdict | Action |
|---|---|---|---|
| Capture window | T−45→T+3, write T−10, 120s poll | LOCKED | Harden: discard post-commence snapshots (live-odds contamination on game lines) |
| CLV formula | devig(close) − raw(entry) | LOCKED | None — published best practice; zero point = zero EV. Keep pre/post-reform rows segregated |
| Devig method | Multiplicative, close side | LOCKED | Power devig only if \|odds\| ≥ 200 markets enter CLV; immaterial at prop odds |
| Go-live gate | n=100 CLV rows | DATA_GATED | Add one-sided t-test (t ≥ ~1.7) on post-reform rows at gate; +0.4pp avg ⇒ ~150–200 rows |
| Prop CLV validity | Soft-book closes | PERIODIC_RECAL | Subordinate to graded W/L; consider multi-book consensus close |

---

## §9D — SLOW_BOOKS Exploitation

**Current implementation** (run_picks.py:795):
- `SLOW_BOOKS = {"fanatics", "hardrockbet", "betrivers"}` — assumed 15–40 min injury-news repricing lag; exploited via EdgeModel `--late-run` re-fetch. Lag estimates assumed, not measured.

### Q1 — Do operators demonstrably differ in repricing speed?
The two-tier structure (market-makers originate, retail follows with delay) is real and well-documented; the lag magnitude for **props** is plausibly 20–40 min, but for major game lines it has shrunk to seconds–minutes. The specific 3-book membership of SLOW_BOOKS is NOT validated by any public source.
- **Levitt (2004)**, *Economic Journal* 114(495): bookmakers announce a price, after which "adjustments are small and infrequent" — retail books are *price-setters with sticky prices*, not continuous repricers. Staleness is endogenous to their business model. ([PDF](http://pricetheory.uchicago.edu/levitt/Papers/LevittWhyAreGamblingMarkets2004.pdf))
- **Ottaviani & Sørensen (2005–2009)**: posted prices systematically deviate from fair value; informed bets cluster late — theoretical support for the `--late-run` window. ([Timing of Bets and the FLB](https://web.econ.ku.dk/sorensen/Papers/tobaflb.pdf))
- **Croxson & Reade (2014)**, *EJ* 124(575): exchange prices incorporate major news within seconds — the efficiency benchmark retail lag is measured against.
- Post-PASPA practitioner consensus (Unabated, EdgeSlip, Outlier): market-makers (Pinnacle/Circa) originate; retail follows — but **major game line lag is now <60s**; a Princeton live-NBA-arb thesis found arb windows averaging ~13 seconds.
- **Player props after injury news are the genuine slow lane**: practitioner sources describe books that "lag by 20 to 40 minutes" on props ([Shurzy](https://content.shurzy.com/post/comparing-player-prop-odds-across-sportsbooks)) — consistent with the engine's 15–40 min assumption *for props specifically*.
- **Counter-evidence on membership**: Fanatics is reviewed as "extremely quick on line movements" with *lower* avg prop vig (4.74%) than BetRivers (5.94%) ([OddsAssist](https://oddsassist.com/sports-betting/sportsbooks/fanatics/)); it runs the former PointsBet tech stack. No public source ranks Fanatics/Hard Rock/BetRivers as the three slowest.

**Verdict: PERIODIC_RECAL** (premise — structurally sound, props-specific) / **DATA_GATED** (membership + lag numbers).

### Q2 — Sustainability
The edge is durable at the **market** level but self-eroding at the **account** level. Books respond with limits, not faster tech — and limits arrive fast:
- Classic "top-down"/steam-chasing pattern; some books ban/limit steam-chasers *before* traditional sharps (SportsBettingDime, Boyd's, betstamp).
- Rose-Berman ("[The Truth About Limits](https://howgamblingworks.substack.com/p/the-truth-about-limits)"): winners identified "within hours of signing up"; limited users capped ~$200 majors, **~$50 props**. ESPN documents operators defending the practice; Spanky's saga (The Ringer 2019); MA Gaming Commission data shows limiting concentrated on winners.
- Hard Rock specifically noted for limiting consistent winners (OddsAssist).
- Two erosion vectors: per-account ($50 prop limits neuter the strategy) and secular (retail latency shrinking; props lag persists only because prop volume is small and trading-desk attention rationed).

**Verdict: PERIODIC_RECAL.** Action: log per-book bet-acceptance/limit events as a first-class signal; a SLOW_BOOKS book that limits the account is effectively removed from the exploit set.

### Q3 — Legality / ToS (Colorado)
Betting on **public** injury news before a book reprices is legal in Colorado. No insider-trading analogue exists in sports betting.
- CO prohibited-conduct rules (1 CCR 207-2; C.R.S. 44-30-1506) target prohibited participants (athletes, officials, insiders) and proxy betting — not speed-of-reaction to public news. ([CO Division of Gaming rules](https://sbg.colorado.gov/sites/sbg/files/documents/1CCR%20207-2%20SB%20Combined%20Rules%20061424.pdf))
- Even courtsiding (live in-venue data relay) is not US-illegal — venue ToS issue only. The engine's behavior is more benign: pre-game, public, published news.
- **Commercial risk 1 — limiting**: fully legal in CO. **SB26-131** (signed 2026-06-02, effective **2026-08-12**) is consumer-protection only: credit-card deposit ban + max 6 deposits/24h — operationally relevant to bankroll funding from August; does NOT restrict limiting.
- **Commercial risk 2 — obvious-error voiding**: CO Rule 6.10 lets operators void wagers on "obvious error" per their house rules. A stale line hit right after major injury news is the textbook voidable case — expect occasional voids on the best late-run hits (P&L haircut, not legal exposure).

**Verdict: LOCKED** (legality). Document the commercial-risk pair as known costs.

### Q4 — Measurement protocol (lag is assumed, not measured)
No per-operator lag measurement exists publicly; the engine is unusually well-positioned to produce one:
1. **Events**: timestamped material injury changes (top-3-usage OUT/IN flips, late scratches) from official NBA injury report + first-reporter timestamps.
2. **Odds**: extend the existing 2-min CLV daemon to snapshot all CO books on watched events; backfill via The Odds API historical endpoint (5-min snapshots, props from May 2023).
3. **Lag definition**: time from the *sharp-reference move* (Pinnacle first repricing/pull — not the tweet) to the book's first move ≥ threshold or suspension. Isolates follower latency from news-detection latency.
4. **Sample**: ≥30 material events per book; stratify props vs game lines.
5. **Cheap passive validation now**: pick_log.csv already has `book` + `clv` — compare CLV of late-run picks at SLOW_BOOKS vs other books; ~50 graded late-run rows/book gives a first read with zero new infrastructure.
6. **Decision rule**: keep a book in SLOW_BOOKS only if median prop lag ≥ 10 min AND late-run CLV > 0. Fanatics is the most likely member to fail.

**Verdict: DATA_GATED** — both the 15–40 min values and per-book membership. Until measured, SLOW_BOOKS is a hypothesis, not a constant.

### §9D Verdicts

| Item | Current | Verdict | Action |
|---|---|---|---|
| Slow-books premise (retail prop-repricing lag) | Assumed | PERIODIC_RECAL | Literature-backed for props; game lines now reprice in seconds. Re-check annually — latency windows shrinking. |
| SLOW_BOOKS membership {fanatics, hardrockbet, betrivers} | run_picks.py:795 | DATA_GATED | No source validates these three; Fanatics has counter-evidence. Gate on Q4 measurement. |
| 15–40 min lag estimate | Assumed | DATA_GATED | Event-study ≥30 events/book; passive gate ~50 late-run CLV rows/book from pick_log. |
| Edge sustainability | Assumed durable | PERIODIC_RECAL | Account-eroding (limits, ~$50 prop caps documented). Log per-book limit events; drop limited books. |
| Legality (CO, public news) | — | LOCKED | Legal under 1 CCR 207-2. Known commercial risks: limiting + Rule 6.10 obvious-error voids. |
| SB26-131 ops impact (2026-08-12) | Untracked | NEEDS_CHANGE (ops) | Credit-card deposit ban + 6 deposits/24h cap — adjust bankroll funding workflow before Aug 12, 2026. Not a code change. |

---

## §9E — Daily Lay Architecture

**Current implementation** (run_picks.py:192–199, 4250–4299, 5140–5165):
- 2–4 leg alt-spread parlay; MIN_DAILY_LAY_PROB=0.50 (combined); per-leg edge ≥0.025, cover_prob ≥0.58, projected margin ≥4.0; max combined odds +100; quarter-Kelly sizing clamped 0.25–0.75u

### Q1 — Structure soundness
A parlay of genuinely +EV legs **multiplies (1+EV) per leg** — EV-amplifying, not merely variance-amplifying, conditional on calibrated per-leg edges ([Unabated "The Good and Bad of Parlays"](https://unabated.com/articles/the-good-and-bad-of-parlays)). At per-leg edge 2.5pp on ~0.79-implied legs (ROI ≈ 3.15%/leg), 3-leg EV ≈ 1.0315³−1 ≈ **+9.75%** vs +3.15% straight. Joint prob ≥0.50 makes this the *low-variance end* of parlay structures. Parlaying heavy favorites is also a documented vig-reduction technique vs laying −300+ alt-lines individually. The "2–3 legs max" guidance in the vig-compounding literature applies to −EV legs and is what Daily Lay does anyway. **Verdict: LOCKED.**

### Q2 — Does the 0.58 per-leg floor do any work? (math verified)
- 0.58³ = 0.1951 < 0.50 — three legs at the floor fail the joint floor by a wide margin.
- For joint ≥0.50: geometric-mean leg prob ≥ **0.794** (3-leg, fair ≈ −385), **0.707** (2-leg, ≈ −241), **0.841** (4-leg, ≈ −529). The +100 cap independently forces the same regime.
- So in symmetric configurations **0.58 never binds** — it binds only in barbell configurations (e.g., one 0.93 leg + one 0.55 leg: joint 0.51 passes, but 0.58 blocks the coin-flip leg). Its real role: **anti-barbell guard** preventing a near-lock from carrying a coin-flip leg (where model error concentrates).
**Verdict: LOCKED (documentation fix)** — not vestigial but secondary. Optional: raise to ~0.65 (invisible to symmetric slips) to tighten the barbell case.

### Q3 — EV at the +100/0.50 boundary (math)
3-leg at the cap with 2.5pp/leg edge: true joint = 0.50 × 1.0315³ = 0.5488 → EV at +100 = **+9.75%**. 2-leg: **+7.2%**. General result: parlay EV = Π(true/implied) − 1 > 0 whenever every leg clears the edge floor — **+EV by construction, floor ≈ +5–10%**, not marginal. The +100 cap is a variance/branding constraint (hit rate ≥ ~50%), not an EV constraint. Contingent on per-leg alt-spread cover probs being calibrated (2.5pp is within plausible sigma miscalibration — see Q5 gate). **Verdict: LOCKED** (contingent on Q5).

### Q4 — Kelly sizing 0.25–0.75u
Boundary case p=0.55 at +100: f* = 0.10 → engine convention (f*×6) = 0.60u — inside the band; band spans ≈ **1/40 to 1/13 Kelly**. For parlays, joint-prob relative error compounds ≈ n× per-leg error, so a deeper-than-straight fraction is theoretically correct. **Verdict: LOCKED** — revisit the 0.75u ceiling only after Q5 gate confirms calibration.

### Q5 — Validation gate (0 graded post-redesign)
At n=20 slips, slip-level CI is ±22pp — gross-miscalibration detection only. **Primary gate metric must be leg-level** (20 slips ≈ 50–70 legs; ±10pp at n=60). Gate definition (n=20 slips):
1. Per-leg cover rate vs mean predicted (primary): flag if actual < predicted − 10pp
2. Slip hit rate vs predicted joint: directional at n=20, binding at n=50
3. ROI: expected +7–10%; flag if < −15% at n=20
4. Per-leg cover rate vs 0.58 floor: confirm no near-floor legs entering (barbell check)
5. Realized cover margin vs MIN_DAILY_LAY_MARGIN=4.0: clustering <4 ⇒ alt-spread sigma too tight
**Verdict: DATA_GATED** — n=20 for leg-level, n=50 for slip-level/retunes.

### §9E Verdicts

| Item | Current | Verdict | Action |
|---|---|---|---|
| Daily Lay structure | 2–4 leg alt-spread, joint ≥0.50, ≤+100 | LOCKED | Align docs ("3-leg" → 2–4 legs) |
| MIN_LEG_COVER_PROB_DAILY | 0.58 | LOCKED (doc fix) | Anti-barbell guard, not binding constraint. Optionally raise to ~0.65 |
| MIN_DAILY_LAY_PROB / +100 cap | 0.50 / +100 | LOCKED | +7.2–9.75% EV at boundary; cap is variance control |
| Sizing | 0.25–0.75u | LOCKED | ≈1/40–1/13 Kelly; deeper fraction correct for compounded error |
| Validation | 0 graded | DATA_GATED | n=20 leg-level gate as specified above |

---

## §9F — Tier System Design

**Current implementation** (run_picks.py:729, 1214–1221):
- T1 (AST/SOG/REC/HRR) min_edge=0.03 mult=0.90 · T1B (REB/HITS/HA high-line unders) 0.03/0.93 · T2 (PTS/PRA/OUTS/SV/…) 0.05/1.00 · T3 (3PM/GOALS/NRFI/YRFI/ML_DOG/…) 0.06/0.95
- pick_score = 0.40·wp_n + 0.60·e_n, e_n capped at 100 (15% edge ceiling)
- Performance (2026-05 gate audit, plan-supplied): T1 46.6% WR/−10.2% ROI · T1B 46.9%/+1.7% · T2 60.3%/+14.0% · T3 51.5%/+5.3%

### Q1 — T1 underperformance: design or calibration?
Both — the structural problem dominates. Two published strands:
1. **Winner's curse / selection on extreme estimates**: an estimated edge = true_edge + noise; conditioning on the estimate clearing a threshold enriches for estimation error — conditional expectation of true edge is shrunk toward zero (standard empirical-Bayes result; [winner's-curse-under-dependence](https://www.biorxiv.org/content/10.1101/2023.09.22.558978.full.pdf)). [Baker & McHale 2013, *Decision Analysis*](https://pubsonline.informs.org/doi/abs/10.1287/deca.2013.0271) formalize the betting consequence: replace true p with a sample estimate and out-of-sample performance degrades; the fix is **shrinkage on the probability estimate** derived from its variance.
2. **Calibration vs discrimination**: book odds are better *calibrated* than bettor models even when models retain competitive discrimination; profitability requires calibration, not rank-ordering ([Wilkens 2026](https://journals.sagepub.com/doi/10.1177/22150218261416681)).

**The inversion is real**: "T1 = highest conviction" with **min_edge=0.03 — the lowest floor of any tier — on the worst-calibrated stat family** (low-count stats where Normal-vs-NB misspecification was later confirmed) is internally inconsistent. T2 at 0.05 beating T1 at 0.03 is exactly what shrinkage theory predicts. Confound worth stating: the −10.2% T1 aggregate includes now-suspended SOG/HA and shadow HRR — live T1 ≈ AST only (AST 0.5-under independently at 72.7% WR, n=44). The tier-level stat conflates retired components.
**Verdict: NEEDS_CHANGE** — (a) reframe tiers as *stat-routing buckets with per-family edge floors*, not conviction levels (conviction lives in pick_score); (b) make floors monotone in calibration quality (worst-calibrated = highest floor); (c) Baker–McHale probability shrinkage per family (see Q2).

### Q2 — Size multiplier vs raising the threshold
Kelly theory is unambiguous: if true edge is overstated, **both selection and sizing are corrupted**; a stake multiplier repairs only sizing. Baker–McHale shrinkage on the probability propagates into both coherently. MacLean–Thorp–Ziemba asymmetry: overbetting is the fatal direction, and the first-order damage from overstated edges is *admitting −EV bets*, not staking them 10% heavy. Magnitude: T1 ROI −10.2% against a +3% floor implies edge overstated by >100%; a 0.90× multiplier is a 10% correction to a >100% overstatement — off by an order of magnitude. Same defect class as the KELLY_MARKET_MULT layer (already flagged in the Kelly-stack consolidation item).
**Verdict: NEEDS_CHANGE** — replace tier multiplier with per-stat-family empirical-Bayes shrinkage of win_prob toward implied prob (weight from each family's graded calibration); merges with the existing DATA_GATED Kelly-stack consolidation item — one mechanism.

### Q3 — T1B as a distinct class
Justified on two grounds: (1) **distributional** — count stats are NB right-skewed (engine's own refits: var/mu 1.2–1.7); the under side of a high line has bounded body-of-distribution risk while overs are exposed to the misspecified right tail; (2) **market-structure** — documented recreational over-bias that books shade, leaving residual value on unders ([Unabated](https://unabated.com/articles/the-biggest-mistake-youre-making-when-betting-nfl-player-props); [Wizard of Odds — props set at median, not mean](https://wizardofodds.com/article/player-props-understanding-the-math-behind-the-lines/)). T1B's profile (WR 46.9%, ROI +1.7%) — sub-coinflip WR with positive ROI — is the signature of buying the unshaded plus-ish side.
**Verdict: DATA_GATED** — keep the class; bootstrap ROI>0 test at n≥100 graded T1B; don't expand its stat list before then.

### Q4 — Deprecate T1?
The statistics: two-proportion z (46.6% vs 60.3%) needs **~207 picks/tier** at α=0.05/power 0.80; T1-vs-breakeven (52.38%) needs **~580–590**. At the gated n=30 checkpoint, WR SE is ±9.1pp — uninformative. **A WR-significance test will never arrive in useful time**, and the T1 population already changed (SOG/HA suspended, HRR shadow). Testing the historical aggregate tests a tier that no longer exists.
**Verdict: NEEDS_CHANGE (restructure now, don't wait for n)** — dissolve the conviction framing per Q1; route each stat family on its own calibration record. Keep a bootstrap (n≥150, retire family if P(ROI≥0)<0.10) as the formal record. The n=30 PICK_SCORE_TIER_MULT checkpoint should be retired alongside the multiplier — it tests the wrong instrument at an uninformative n.

### Q5 — T3
WR 51.5% + positive ROI implies plus-money average prices — consistent with composition (3PM, GOALS, ML_DOG, NRFI/YRFI). Specialty markets carry wider vig (−115/−120+ vs −110) and less book pricing effort — wider vig but bigger genuine mispricings; the profile of a tier that clears a higher bar less often and profits when it does. The +1pp floor increment over T2 approximates the incremental vig of thinner markets.
**Verdict: LOCKED (floor) / PERIODIC_RECAL (level)** — re-derive 0.06 annually from the measured average overround of T3's actual markets.

### §9F Verdicts

| Item | Current | Verdict | Action |
|---|---|---|---|
| T1 framing + min_edge=0.03 | lowest floor, worst-calibrated stats, ROI −10.2% | NEEDS_CHANGE | Reframe tiers as stat-routing buckets; floors monotone in calibration quality |
| T1 size mult 0.90× | 10% shrink vs >100% overstatement | NEEDS_CHANGE | Per-family probability shrinkage (Baker–McHale); retire tier mult; merge with Kelly-stack consolidation |
| T1B class | WR 46.9%/ROI +1.7% | DATA_GATED | Keep; bootstrap ROI>0 at n≥100; no stat-list expansion |
| T1 retirement test | n=30 checkpoint (1/30) | NEEDS_CHANGE | n=30 uninformative (SE ±9.1pp); restructure now; formal record = ROI bootstrap at n≥150/family |
| T3 min_edge=0.06 | WR 51.5%/ROI +5.3% | LOCKED / PERIODIC_RECAL | Keep; re-derive annually from measured T3 overround |

---

## §9G — Longshot Parlay Construction

**Current implementation** (run_picks.py:200–202, 4136–4233):
- 6 legs, safest-by-win_prob descending; max 2 legs/game, 1 leg/player; flat 0.25u; legs treated as independent (no copula). VALUE_PARLAY 5-leg fallback, same caps, 0.25u.

### Q6 — "Safest 6" vs EV-ranked selection
The literature is consistent ([OddsShopper "Math Behind Profitable Parlays"](https://www.oddsshopper.com/articles/betting-101/how-to-find-the-best-parlay-bets-today-using-expected-value-ev-y10), Unabated): with multiplicative payout, select legs on **per-leg EV ratio**, not standalone safety. Math: a 65%-WP/20%-edge leg contributes factor ≈1.20 to slip EV; a 70%-WP/3%-edge leg ≈1.03 — current ranking picks the 1.03 leg. Across 6 legs: six 1.10 legs → +77% slip EV vs six 1.03 legs → +19%. Mitigations: the pool is gate-filtered (all legs believed +EV), so safest-6 is still +EV — just not EV-maximal; and there's a legitimate *product* argument (a safest-picks longshot hits every ~2–3 weeks — better community content than a max-EV slip hitting every ~8 weeks).
**Verdict: NEEDS_CHANGE (low priority).** Either rank by (1 + edge/implied) descending with a win_prob ≥0.60 floor, or explicitly re-document Longshot as a hit-frequency marketing product and accept the EV sacrifice. Pick one — the current state is an EV product with a safety objective.

### Q7 — Kelly for the 6-leg parlay vs flat 0.25u (math)
Six −150 legs: combined decimal 21.43, implied joint 4.67%. Modest edge (0.625 true vs 0.60/leg): joint p = 0.0596, f* = 0.0136 → full Kelly 1.36u; flat 0.25u = ~1/5.4 Kelly. Strong edge: f* = 0.0302 → 0.25u = 8% of Kelly. **Thin edge** (joint 0.050 vs 0.0467): f* = 0.0035 → 0.35u full Kelly — flat 0.25u is **71% of full Kelly**. With 6×-compounded estimation error, the thin-edge scenario is the planning case — but absolute exposure is 0.25% of bankroll, so the overbet penalty is negligible in absolute terms.
**Verdict: LOCKED** — 0.25u is the engine's minimum quantum and slip-specific Kelly would mostly output 0.05–0.20u that the floor overrides anyway. On record: this is the *most aggressive bet in the book relative to Kelly* when edge is thin — do not raise without graded evidence.

### Q8 — Same-game independence + max 2/game
Key asymmetry confirmed: independence on positive-ρ same-game pairs *understates* joint prob (conservative); on negative-ρ pairs it *overstates* (dangerous). X1 and R5 remove the catastrophic tail. Residual: moderate-negative pairs not in the filter list (player PTS over + same-game TOTAL under, ρ ≈ −0.1 to −0.3). Quantified: one pair at p=0.65 each, ρ=−0.2 → pair joint 0.395 vs 0.423 independent — slip joint prob overstated ≈ **6.5% relative per such pair**. Tolerable at 0.25u flat; would matter if sizing became Kelly-derived.
**Verdict: PERIODIC_RECAL** — sufficient guardrail as-is. Cheap opportunistic upgrade: reuse the existing SGP copula ρ table inside `build_safest6_parlay()`. Reassess if longshot sizing exceeds 0.25u or the per-game cap is raised.

### Q9 — Optimal leg count (5/6/7)
The EV-decay-per-leg literature (hold compounds 4.5% → ~25% at 6 legs; "stick to 2–3") applies to **−EV legs**; with +EV legs, edge compounds at the same rate vig would — leg count becomes a hit-frequency vs payout product question, not an EV question. Six ~0.65–0.70 WP legs → joint 8–15% → a hit every 2–3 weeks at daily cadence — sensible engagement cadence; 5-leg fallback preserves the product on thin slates; 7 legs adds a multiplicative model-error layer for marginal payout gain.
**Verdict: LOCKED.**

### §9G Verdicts

| Item | Current | Verdict | Action |
|---|---|---|---|
| Leg ranking | win_prob descending | NEEDS_CHANGE (low priority) | EV-factor ranking with WP ≥0.60 floor, OR re-document as hit-frequency product |
| Flat 0.25u sizing | flat | LOCKED | Spans 8–71% of full Kelly; acceptable at 0.25% bankroll. Don't raise without data |
| Same-game independence | max 2/game + X1/R5 | PERIODIC_RECAL | Residual negative pairs overstate slip prob ~6.5%/pair; opportunistic SGP-ρ reuse |
| 6-leg / 5-leg fallback | 6/5 | LOCKED | Product-cadence optimal; no EV argument for change |

---

## §9H — SGP Thresholds

**Current implementation** (mlb_sgp_builder.py:65–71, 199–223, 303–318):
- 3–4 legs; per-leg WP ≥0.65 (OUTS ≥0.62); combined odds +200–+450; Gaussian copula joint prob (ρ table: OUTS-over+opp-HITS-under=0.30, same-team batters=0.15, two pitchers=0.10, cross-team batters=0.08, default 0.02)
- Premium 0.50u iff copula EV margin ≥0.10 AND avg_edge ≥0.035; else 0.25u. R2_MLB kill: OUTS-under + HITS-under same game.

### Q10 — Per-leg WP floor vs joint-EV gating
No published source treats a per-leg WP floor as *the* SGP construction criterion — industry practice (Wizard of Odds SGP correlation math, OpticOdds, Kambi/USPTO correlated-prop pricing) gates on **joint** probability vs offered payout. The per-leg floor is legitimate *variance control* but does not guarantee +EV: a 4-leg slip of exactly-0.65 legs at the +450 cap has independent joint 0.1785 vs implied 0.1818 — **slightly −EV before correlation lift**, and the engine's small cross-type ρ's (0.02–0.15) lift it only a few % relative. The engine already computes the copula joint prob and EV margin — it just uses the margin only for premium sizing, not as an existence condition.
**Verdict: NEEDS_CHANGE.** Keep the per-leg floors; add a **joint-EV existence floor**: copula joint_prob > implied(parlay odds) + ε, ε ≈ 0.02–0.03 (≈+10–15% ROI at +350) for ANY slip to fire. Premium gate unchanged.

### Q11 — Odds window +200–+450 (math)
- **3-leg**: per-leg decimal between 3.00^⅓=1.442 (≈−226) and 5.50^⅓=1.765 (≈−131). Legs −135 to −155 combine to +345–+428 — fits. Model-0.65 legs (fair −186) quoted −131…−186 carry positive edge. **Internally consistent.**
- **4-leg**: per-leg decimal forced to 1.316–1.532 (≈ −316 to −188, implied 0.653–0.760). Four −135/−155 legs combine to +632–+819 — **excluded by the cap** (intent: kill high-variance moderate-favorite combos — works). **Tension**: on a −250 leg (implied 0.714), the 0.65/0.62 floor is *below* implied — the leg floor alone admits −EV legs in exactly the regime the cap forces. This is where Q10's joint-EV floor is load-bearing.
**Verdict: PERIODIC_RECAL** — consistent for 3-leg; 4-leg safe only jointly with the Q10 fix (then LOCKED).

### Q12 — Premium gate vs published SGP hold
Published SGP hold: parlays 16–25% (NJ/IL regulated data), SGPs at the top of the range; Wizard of Odds estimates a 3-leg SGP costs ~7× the EV of the same legs straight ("correlation tax" ~15% off independence payouts stacked on per-leg vig). The premium gate margin ≥0.10 at +350 implies **≥+45% ROI** — appropriately strict and rare by design. The 0.25u default is the issue: given 20–30% structural hold, an SGP is only +EV when the model out-prices the book's own copula by the full hold — current leg floors don't enforce that. Empirical note: model→58% vs 69% actual on 52 slips suggests joint probs currently *under*-stated (Platt over-correction) — the safe direction, but by luck not design.
**Verdict: NEEDS_CHANGE (same fix as Q10)** — gate the 0.25u default on copula margin > +0.02–0.03; re-tune ε at the 100-scored-slip Platt gate.

### Q13 — MIN_LEG_WIN_PROB_OUTS=0.62 after sigma 0.311→0.27 (math)
For a leg with cushion c at μ≈17 outs: win_prob = Φ(c/σμ). At c=2: 0.647 → 0.668 (**+2.1pp**); a leg at exactly 0.62 old now reads ~0.635. The 0.62 floor used to require c≈1.62 outs of cushion; it now requires c≈1.40 — effectively looser. Monitoring spec:
1. OUTS legs per slip pre/post 2026-06-05 — trigger: >50% increase
2. OUTS leg grade rate vs predicted — trigger: actual < predicted − 8pp at n≥40 legs
3. Slip-level hit rate vs copula joint (already in the 100-slip Platt gate)
4. Retune action if trigger 2 fires: sigma-equivalent floor = Φ(1.62/4.59) ≈ **0.638** → raise to ~0.64
**Verdict: DATA_GATED** — evaluate at n≥40 graded OUTS legs post-2026-06-05.

### §9H Verdicts

| Item | Current | Verdict | Action |
|---|---|---|---|
| Per-leg floors 0.65/0.62 | leg-screen only | NEEDS_CHANGE | Keep floors; add joint-EV existence floor (copula margin > +0.02–0.03) for any slip |
| Odds window +200–+450 | hard window | PERIODIC_RECAL | 3-leg consistent; 4-leg admits −EV legs without the joint-EV floor |
| Premium gate ≥0.10 + avg_edge ≥0.035 | premium sizing | LOCKED | ≈+45% ROI condition — appropriately strict vs 16–25%+ SGP hold |
| MIN_LEG_WIN_PROB_OUTS=0.62 | tuned to old σ | DATA_GATED | Monitor per spec; sigma-equivalent floor ≈0.64 if retune fires |

---

## §9J — Hard Rules (R4/R7/R9/R10/R12)

**Current implementation** (run_picks.py:1544–1750, 1602, 6723–6730):
- R4: REB overs (and REB unders ≤2.5) → shadow log, not posted
- R7: max 2 picks/game per card (default arg)
- R9: directional balance — if ≥3 overs passed gates but 0 on premium card, force best over in
- R10: max 1 pick per stat on Premium 5
- R12: 5-day cooldown on players whose pick lost (auto-merged from pick_log)

### Q6 — R4 REB-over shadow (post-model-fix protocol)
A gate imposed on a *symptom* (REB overs losing) must be re-evaluated when the *cause* fix ships (NB r=14.7 game-level refit) — otherwise the gate silently becomes permanent and the fix's EV is never collected. Shadow-after-fix is correct **only as a bounded validation window with a pre-registered lift condition**. Power note: WR ≥55% at n=30 has SE ±9.1pp — cannot distinguish 55% from breakeven; calibration-based criteria are far more powerful.
**Verdict: DATA_GATED with explicit lift condition** — lift R4 when post-refit shadow REB-overs show (a) n≥50, (b) win_prob calibration bias within ±3pp (mean predicted − realized), (c) mean CLV ≥ 0. WR≥55% only as secondary check.

### Q7 — R7 max-2-per-game
First-best per theory is joint Kelly with covariance: [Whitrow 2007 JRSS-C](https://rss.onlinelibrary.wiley.com/doi/abs/10.1111/j.1467-9876.2007.00594.x) shows correlation erodes effective portfolio size and shrinks optimal per-bet fractions — **shrink stakes, don't cap counts**. But the robust-control counter is also grounded: joint Kelly needs the ρ matrix, and ρ-estimation error is itself a Kelly hazard (MTZ asymmetry: overallocation is the fatal direction). A count cap is a zeroth-order covariance control that can't be wrong by more than its bluntness, costs ~nothing at ~2u/game exposure, and the engine already covariance-prices where it matters most (parlays/SGP).
**Verdict: LOCKED (as heuristic).** Optional low-priority upgrade: per-game *stake budget* (~2.0u) — same robustness, removes the discontinuity at pick #3.

### Q8 — R9 directional balance
No quantitative justification in portfolio theory, and the over/under shading literature actively argues against it: a model leaning under on a slate may be correctly harvesting the over-shade — the skew is *signal*, and forcing an over dilutes it. The "hedges systematic bias" steelman fails on mechanism (the fix for directional bias is calibration measurement, not card composition), and the forced over displaces a higher-scored pick — strictly EV-negative under the model's own ranking. Mitigation: the forced over passed all gates (+EV by model), so the cost is the score gap — small but systematically negative.
**Verdict: NEEDS_CHANGE (reclassification)** — document R9 honestly as a product/optics rule (card variety for subscribers), not an EV rule. Add a cheap monitor: cumulative score-gap + realized P&L of forced-in overs vs displaced picks. Keep it if the product value is judged worth the measured cost.

### Q9 — R10 same-stat cap
**Stronger basis than R7.** Same-stat picks share a projection model — textbook common-factor exposure: portfolio variance is dominated by the shared stat-model error factor when several positions load on it. Unlike game-level ρ (estimable from outcomes), *model-error* correlation is nearly impossible to estimate online — precisely the condition where a hard cap beats covariance sizing. The cap also self-limits the observed systemic failure mode (a miscalibrated family — e.g., pre-fix REB — can't put >1 losing pick per card).
**Verdict: LOCKED** — the best-justified hard rule in the system.

### Q10 — R12 5-day loss cooldown
Not evidence-based as risk control: one loss on a 55–60% pick has probability 0.40–0.45 *with the model correct* — likelihood ratio ≈ 1, posterior edge essentially unchanged. Conditioning selection on it is gambler's-fallacy-family behavior ([Croson & Sundali, JDM](https://www.cambridge.org/core/journals/judgment-and-decision-making/article/biases-in-casino-betting-the-hot-hand-and-the-gamblersfallacy/8A9D1813D42FFA25634E7FD26A46D484); [Cognition 2014](https://www.sciencedirect.com/science/article/pii/S0010027714000031)). Distinguish from the legitimate cousin: **persistent adverse line movement / negative CLV is information** (market disagreeing repeatedly = Bayesian evidence; a graded loss is not). Subtle selection cost: cooldown removes players exactly when the book may have moved the line *toward* you off the visible miss — sometimes the best re-entry. Honest classification: product-driven (not re-posting a player who just burned the card) with a real but unmeasured EV cost.
**Verdict: NEEDS_CHANGE (reclassify + replace trigger)** — document as product rule; when CLV data matures, replace trigger with negative-CLV condition (e.g., CLV ≤ −2pp on last pick, or 2+ consecutive losses with negative CLV).

### §9J Verdicts

| Item | Current | Verdict | Action |
|---|---|---|---|
| R4 REB-over shadow | post-fix shadow, no lift condition | DATA_GATED | Pre-register lift: n≥50 post-refit, calibration bias ±3pp, mean CLV ≥0 |
| R7 max-2/game | hard count cap | LOCKED | Sound heuristic under ρ-estimation error; optional per-game stake budget (~2u) |
| R9 directional balance | force best over | NEEDS_CHANGE (reclassify) | Product rule, not EV; monitor forced-over score-gap + P&L |
| R10 same-stat cap | 1/stat on Premium 5 | LOCKED | Best-justified rule — unestimable common-factor ρ is where caps beat sizing |
| R12 5-day loss cooldown | loss-triggered skip | NEEDS_CHANGE (reclassify) | Gambler's-fallacy-adjacent; label product rule; replace trigger with negative-CLV when data matures |

---

## §9K — Daily Unit Cap Structure

**Current implementation** (run_picks.py:733, 1763–1782):
- Daily total cap 12u (all run types); SPORT_UNIT_CAP per pick: NBA=8, MLB=8, NHL=5, NFL=5, WNBA=4; STAT_CAP default 2/run (SOG 6)
- KELLY_FRACTION=6.0 on 100u convention ⇒ ≈1/16.7 Kelly; sizes rounded 0.25u, floor 0.50u (0.25u T3)

### Q11 — 12u daily cap
12% max daily exposure = 12–24 picks at ~0.5–1% each at ≈1/16.7 Kelly. Benchmarks: Thorp's own sports operation used ~half Kelly or less explicitly for estimate uncertainty and simultaneous-bet correlation ([Thorp 2006/2008](https://gwern.net/doc/statistics/decision/2006-thorp.pdf)); MTZ simulations: near-full Kelly "very risky" short-term; Baker–McHale: optimal fraction shrinks with estimate variance. Portfolio check: ~15 near-independent bets with full-Kelly fractions ~3–4% each ⇒ joint full-Kelly ~40–60% of bankroll (Whitrow regime); 12u ≈ **0.2–0.3 of joint full Kelly** — inside the conservative band the literature recommends under parameter uncertainty (pre-H3 Platt, uncalibrated MLB win_probs). Worst-case day = 12% drawdown — far from ruin-relevant. If anything conservative — the correct side of the MTZ asymmetry.
**Verdict: LOCKED.** Revisit only at material volume change (e.g., NFL go-live — then the cap starts forcing per-pick underbetting, a growth cost not a risk).

### Q12 — Sport caps (NBA/MLB 8u > NHL/NFL 5u > WNBA 4u)
Liquidity tiering is standard sharp practice (lower-liquidity markets: wider vig, tighter limits, worse fills → scale down; [Durkin on liquidity](https://conordurkin.com/liquidity-in-sports-betting-markets/)), and calibration maturity is the Baker–McHale argument (higher estimate variance for younger sport models ⇒ lower shrunk-Kelly fraction). The **ordering** matches both criteria. The **mechanism** is weaker: these are *per-pick* caps, and with stakes 0.25–2u (KILLSHOT max 4u), an 8u per-pick cap binds with probability ~0 — a bug backstop, not an exposure control. A per-sport **daily budget** (e.g., WNBA ≤2u/day at go-live) would actually implement the liquidity logic.
**Verdict: PERIODIC_RECAL** — keep ordering/values (harmless, correctly ranked); recheck at each sport's go-live; optional conversion to per-sport daily budgets.

### Q13 — Do the caps bind before Kelly?
- **Per-pick sport caps: cosmetic.** Nothing in the live system can generate a 5–8u single stake. Fine as backstops; should not be described as risk controls.
- **The 0.50u floor binds far more often than any cap — and in the wrong direction.** A typical 3–4% edge at −110 gives f* ≈ 3.3–4.4% → stake = f*×6 ≈ 0.20–0.26u, floored UP to 0.50u: **~2–2.5× the Kelly-coherent stake on the weakest admitted picks** — the one place the sizing system over-bets relative to its own Kelly logic (the MTZ-fatal direction). More material than anything about the caps themselves.
- **12u daily cap binds intermittently** — multi-sport days plausibly sum 12–18u pre-cap; single-sport days run 5–8u.
- Settling query (one-liner on pick_log.csv): count days with sum(size) ≥ 11.5u; count picks where size==0.50 and the unfloored Kelly stake < 0.40u (floor inflation rate).
**Verdicts: 12u LOCKED · per-pick sport caps PERIODIC_RECAL (relabel backstops) · 0.50u floor NEEDS_CHANGE (flagged — adjacent finding).**

### §9K Verdicts

| Item | Current | Verdict | Action |
|---|---|---|---|
| 12u daily cap | ≈0.2–0.3 joint full Kelly | LOCKED | Correct conservative side; revisit at NFL go-live volume |
| Sport per-pick caps 8/8/5/5/4u | never bind | PERIODIC_RECAL | Ordering correct; relabel as bug backstops or convert to per-sport daily budgets |
| 0.50u stake floor (adjacent finding) | rounds 0.20–0.26u stakes up 2–2.5× | NEEDS_CHANGE | The actually-binding sizing constraint, over-stakes weakest picks; lower to 0.25u or skip picks with Kelly stake < ~0.35u |
