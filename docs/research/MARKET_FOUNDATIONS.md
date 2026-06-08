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

**Counts: 24 LOCKED · 9 PERIODIC_RECAL · 13 DATA_GATED · 12 NEEDS_CHANGE → ALL 12 RESOLVED** (Plan 9 fixes shipped 2026-06-06 in commits 76fbb36 — ERA/FIP, stake floor, R9/R12/longshot reclassify, SB26-131 note; 3aad87f — NRFI gamma, SGP joint-EV floor, longshot +ρ ranking; c4380ca — tier restructure, BM shrinkage, R8 retired. Residual DATA_GATED follow-ups noted per row).

| § | Item | Current | Verdict | Action |
|---|------|---------|---------|--------|
| 9A | NRFI game-level baseline (53%) | λ=0.32/team | LOCKED | Matches published 52–55% |
| 9A | **NRFI Poisson elasticity** | exp(−0.32·m^0.65) | **✅ RESOLVED** (3aad87f, 2026-06-06) | NRFI_GAMMA=0.65 m^γ dampener shipped (literature default). γ DATA_GATED — recalibrate when first-inning-level data exists |
| 9A | **ERA/FIP blend** | 0.25/0.75 | **✅ RESOLVED** (76fbb36, 2026-06-06) | 25/75 shipped (_LEAGUE_AVG_BLENDED_RATE=0.4808). xFIP/FIP− upgrade deferred to July refit (needs HR/FB data not in CSV) |
| 9A | Lineup slots 1–3 λ adjustment | absent | DATA_GATED | Backtest top-3 wOBA vs team-R/G in-house before adding |
| 9A | Park omission · λ level · 4.45 R/G | — | LOCKED · PERIODIC_RECAL ×2 | Annual April refit from 1st-inning zero rate |
| 9A | λ home/away independence + symmetry | independent, same base | DATA_GATED | Measure φ + bottom-1st premium (0.6 vs 0.5 runs) in-house |
| 9I | P(YRFI)=1−P(NRFI) · min_edge 0.08 · R5 dedup | — | LOCKED ×3 | FLB-supported differential; revisit after elasticity fix |
| 9B | X1 hard block + ER ρ band | −0.65/−0.75 | LOCKED | Optimal at engine edge scale (breakeven needs 11–20%/leg edges) |
| 9B | X1 HA ρ band | −0.65/−0.75 | PERIODIC_RECAL | Overstated; ≈−0.45/−0.60. Re-document + in-house fit at July refit; no behavior change |
| 9B | Positive-ρ pairs in longshot pool | +ρ ranking boost | ✅ RESOLVED (3aad87f) + DATA_GATED ×3 | OUTS-under + opp-TT-over +ρ ranking boost shipped (ranking-only, never blocks). In-house corr fits + NBA over+TOTAL-under co-occurrence check remain DATA_GATED |
| 9C | CLV formula (devig close − raw entry) | post-reform | LOCKED | **Suspected defect inverted — formula is published best practice.** Never pool pre/post-reform rows |
| 9C | Capture window · devig method | T−45→T+3, mult | LOCKED ×2 | Harden: discard post-commence snapshots (live-odds contamination) |
| 9C | CLV go-live gate | n=100 | DATA_GATED | Add one-sided t-test (t≥1.7) on post-reform rows; +0.4pp avg ⇒ ~150–200 rows |
| 9C | Prop CLV validity | soft-book closes | PERIODIC_RECAL | Subordinate to graded W/L; consider multi-book consensus close |
| 9D | Slow-books premise · sustainability | assumed | PERIODIC_RECAL ×2 | Props-specific (20–40 min documented); account-eroding via limits — log limit events |
| 9D | SLOW_BOOKS membership + 15–40 min lag | hardcoded | DATA_GATED ×2 | Unvalidated (Fanatics counter-evidence); event-study or ~50 late-run CLV rows/book |
| 9D | Legality (CO, public news) | — | LOCKED | Legal; known commercial risks: limiting + Rule 6.10 voids. **Ops note: SB26-131 deposit rules effective 2026-08-12** |
| 9E | Daily Lay structure · thresholds · sizing | 0.50/+100/0.25–0.75u | LOCKED ×4 | +7–10% EV by construction at boundary; 0.58 floor = anti-barbell guard (doc fix); align "3-leg" docs to 2–4 |
| 9E | Daily Lay validation | 0 graded | DATA_GATED | n=20 leg-level calibration gate (spec in §9E Q5) |
| 9G | **Longshot leg ranking** | win_prob desc, documented | **✅ RESOLVED** (76fbb36, 2026-06-06) | Option (b) chosen: re-documented as intentional hit-frequency product (engagement value, not EV ranking) |
| 9G | Flat 0.25u · 6/5 legs | — | LOCKED ×2 | Don't raise sizing without data (spans 8–71% of full Kelly) |
| 9G | Same-game independence | max 2/game + kills | PERIODIC_RECAL | Opportunistic SGP-ρ reuse in build_safest6_parlay() |
| 9H | **SGP existence gate** | joint-EV floor live | **✅ RESOLVED** (3aad87f, 2026-06-06) | SGP_JOINT_EV_MARGIN=0.025 in BOTH builders (NBA + MLB). ε re-tune DATA_GATED at n=100 scored slips |
| 9H | Odds window +200–+450 | hard window | PERIODIC_RECAL | 3-leg consistent; 4-leg safe only with joint-EV floor |
| 9H | Premium gate ≥0.10 | premium sizing | LOCKED | ≈+45% ROI condition vs 16–25%+ SGP hold |
| 9H | MIN_LEG_WIN_PROB_OUTS=0.62 | tuned to old σ | DATA_GATED | Monitor at n≥40 graded OUTS legs; σ-equivalent floor ≈0.64 if retune fires |
| 9F | **T1 framing + floors** | STAT_FAMILY_TIER buckets | **✅ RESOLVED** (c4380ca, 2026-06-06) | Tiers reframed as stat-family calibration buckets; floors monotone: T2=0.05 < T1B/T3=0.06 < T1=0.07. R8 reserved slots retired (T1 WR 46.6% < 50% trigger) |
| 9F | **T1 0.90× mult + n=30 checkpoint** | BM shrinkage live | **✅ RESOLVED** (c4380ca, 2026-06-06) | Baker–McHale shrinkage shipped (per-tier w={.85,.80,.75,.70}, post-Platt, ALL props); PICK_SCORE_TIER_MULT + VAKE_MULT["tier"] + n=30 checkpoint retired. Per-family weight refit DATA_GATED at n≥150/family |
| 9F | T1B class | 0.03 floor | DATA_GATED | Bootstrap ROI>0 at n≥100; no expansion before |
| 9F | T3 floor 0.06 | — | LOCKED/PERIODIC_RECAL | Re-derive annually from measured T3 overround |
| 9J | R4 REB-over shadow | no lift condition | DATA_GATED | Pre-register: n≥50 post-refit, calib bias ±3pp, CLV≥0 |
| 9J | R7 max-2/game · R10 same-stat cap | hard caps | LOCKED ×2 | R10 best-justified rule in system |
| 9J | **R9 directional balance · R12 cooldown** | product rules | **✅ RESOLVED** (76fbb36, 2026-06-06) | Both reclassified product rules in code comments + CLAUDE.md. R9 score-gap monitor at n≥50 forced-over events; R12 → negative-CLV trigger when data matures |
| 9K | 12u daily cap | ≈0.2–0.3 joint Kelly | LOCKED | Correct conservative side; revisit at NFL go-live |
| 9K | Sport per-pick caps | never bind | PERIODIC_RECAL | Relabel backstops or convert to per-sport daily budgets |
| 9K | **0.50u stake floor** (adjacent) | 0.25u all tiers | **✅ RESOLVED** (76fbb36, 2026-06-06) | Floor lowered to 0.25u for ALL tiers (no skip-below logic — complexity not justified) |

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
**Verdict: LOCKED (baseline) / NEEDS_CHANGE (elasticity) → ✅ RESOLVED (3aad87f, 2026-06-06).** Fix (b) shipped: `NRFI_GAMMA = 0.65` exponent dampener (`λ = 0.32·m^γ`, multiplier clamped ≥0 before exponentiation). γ=0.65 is the literature default — DATA_GATED recalibration when first-inning-level data exists (bucket predicted multiplier vs realized NRFI rate on the in-house 8,095-game DB).

### Q2 — ERA/FIP 40/60 blend + lineup quality
Literature unambiguously favors FIP-family estimators for *future* run prevention: predictive ranking cFIP > kwERA > SIERA > xFIP > FIP > ERA (Judge/BP via [Pitcher List](https://pitcherlist.com/the-relative-value-of-fip-xfip-siera-and-xera-pt-ii/)); [FanGraphs month-ahead r²](https://fantasy.fangraphs.com/quick-all-star-break-study-3-month-to-month-correlation-for-era-and-related-stats/): **ERA 0.019, FIP 0.038, xFIP 0.061** — ERA half as predictive as FIP, a third of xFIP. 40/60 gives ERA 2–4× the weight predictive-validity ratios justify; literature-consistent is **≤25% ERA / ≥75% FIP** (better: xFIP/SIERA). Damage bounded (rates correlate ~0.7+ within-season) but concentrates on high-BABIP/strand-rate outliers — exactly the pitchers NRFI models mis-rate.
First-inning-specific: league 1st-inning ERA ~4.86 vs ~4.51 overall (+8%, absorbed by BASE_LAMBDA_1ST — no double-count). But team full-game R/G is a weak proxy for **lineup slots 1–3** (the only guaranteed PAs); commercial NRFI models build λ from leadoff OBP / top-3 wOBA vs L/R. 2023 Braves scored in the 1st 39.16% vs league ~27% — dispersion driven by top-of-order quality that team R/G dilutes. Lineup-slot adjustment plausibly worth more than the ERA/FIP weighting choice.
**Verdict: NEEDS_CHANGE → ✅ RESOLVED (76fbb36, 2026-06-06): blend shipped at 0.25 ERA / 0.75 FIP (`_LEAGUE_AVG_BLENDED_RATE`=0.4808); xFIP/FIP− upgrade deferred to July refit (needs league HR/FB data not in CSV). + DATA_GATED (lineup-slot upgrade — backtest top-3 wOBA λ-adjustment on in-house `mlb_batter_game_stats` first).**

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
| Poisson elasticity | exp(−0.32·m^0.65) | ✅ RESOLVED (3aad87f) | NRFI_GAMMA=0.65 dampener shipped; γ DATA_GATED at first-inning data |
| ERA/FIP blend | 0.25/0.75 | ✅ RESOLVED (76fbb36) | Shipped; xFIP/FIP− upgrade deferred to July refit |
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
- **(b) OUTS under + opp TT over**: **positively** correlated (~+0.3–0.4 — SP knocked out early *because* opp scoring). Independence **understates** joint prob → engine under-ranks/under-sizes a combo that's actually better than modeled. Conservative, not dangerous. Key asymmetry: independence on negative-ρ pairs overstates EV (must block — X1 does); on positive-ρ pairs it understates EV (safe to allow). **NEEDS_CHANGE (minor) → ✅ RESOLVED (3aad87f, 2026-06-06)**: +ρ ranking boost shipped in build_safest6_parlay(), mirroring mlb_sgp_builder's OUTS-over/HITS-under=+0.30. Ranking-only; displayed combined_prob stays independence; never blocks.
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
| OUTS under + opp TT over | +ρ ranking boost | ✅ RESOLVED (3aad87f) | +ρ ranking boost shipped in build_safest6_parlay() (ranking-only; displayed combined_prob stays independence; never blocks) |
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
| SB26-131 ops impact (2026-08-12) | Tracked in CLAUDE.md | ✅ RESOLVED (76fbb36, ops note) | Urgent ops note added to CLAUDE.md (switch to ACH, cache working balances before Aug 12, 2026). Not a code change. |

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
**Verdict: NEEDS_CHANGE → ✅ RESOLVED (c4380ca, 2026-06-06)** — (a) `STAT_FAMILY_TIER` shipped (tiers = stat-family calibration buckets); (b) floors monotone: T2=0.05 < T1B/T3=0.06 < T1=0.07; (c) Baker–McHale shrinkage shipped (see Q2). NRFI/YRFI/TEAM_TOTAL/F5_TOTAL promoted to T2; AST→T1B; NHLBLK/SOG→T3; R8 reserved slots retired.

### Q2 — Size multiplier vs raising the threshold
Kelly theory is unambiguous: if true edge is overstated, **both selection and sizing are corrupted**; a stake multiplier repairs only sizing. Baker–McHale shrinkage on the probability propagates into both coherently. MacLean–Thorp–Ziemba asymmetry: overbetting is the fatal direction, and the first-order damage from overstated edges is *admitting −EV bets*, not staking them 10% heavy. Magnitude: T1 ROI −10.2% against a +3% floor implies edge overstated by >100%; a 0.90× multiplier is a 10% correction to a >100% overstatement — off by an order of magnitude. Same defect class as the KELLY_MARKET_MULT layer (already flagged in the Kelly-stack consolidation item).
**Verdict: NEEDS_CHANGE → ✅ RESOLVED (c4380ca, 2026-06-06)** — `apply_bm_shrinkage()` shipped: `shrunk_p = w·model_p + (1−w)·implied_p`, per-tier w = {T2:0.85, T1:0.75, T1B:0.80, T3:0.70}, applied in evaluate_props post-Platt/pre-gate to ALL props (incl. MLB+combos). PICK_SCORE_TIER_MULT and VAKE_MULT["tier"] retired (VAKE_MULT["variance"] kept, flagged for Kelly-stack consolidation). Per-family weight refit DATA_GATED at n≥150 graded/family.

### Q3 — T1B as a distinct class
Justified on two grounds: (1) **distributional** — count stats are NB right-skewed (engine's own refits: var/mu 1.2–1.7); the under side of a high line has bounded body-of-distribution risk while overs are exposed to the misspecified right tail; (2) **market-structure** — documented recreational over-bias that books shade, leaving residual value on unders ([Unabated](https://unabated.com/articles/the-biggest-mistake-youre-making-when-betting-nfl-player-props); [Wizard of Odds — props set at median, not mean](https://wizardofodds.com/article/player-props-understanding-the-math-behind-the-lines/)). T1B's profile (WR 46.9%, ROI +1.7%) — sub-coinflip WR with positive ROI — is the signature of buying the unshaded plus-ish side.
**Verdict: DATA_GATED** — keep the class; bootstrap ROI>0 test at n≥100 graded T1B; don't expand its stat list before then.

### Q4 — Deprecate T1?
The statistics: two-proportion z (46.6% vs 60.3%) needs **~207 picks/tier** at α=0.05/power 0.80; T1-vs-breakeven (52.38%) needs **~580–590**. At the gated n=30 checkpoint, WR SE is ±9.1pp — uninformative. **A WR-significance test will never arrive in useful time**, and the T1 population already changed (SOG/HA suspended, HRR shadow). Testing the historical aggregate tests a tier that no longer exists.
**Verdict: NEEDS_CHANGE → ✅ RESOLVED (c4380ca, 2026-06-06)** — conviction framing dissolved; stat families route on their own calibration record. n=30 checkpoint retired with the multiplier. Family bootstrap gate (n≥150, retire family if P(ROI≥0)<0.10) registered in CLAUDE.md as the formal record.

### Q5 — T3
WR 51.5% + positive ROI implies plus-money average prices — consistent with composition (3PM, GOALS, ML_DOG, NRFI/YRFI). Specialty markets carry wider vig (−115/−120+ vs −110) and less book pricing effort — wider vig but bigger genuine mispricings; the profile of a tier that clears a higher bar less often and profits when it does. The +1pp floor increment over T2 approximates the incremental vig of thinner markets.
**Verdict: LOCKED (floor) / PERIODIC_RECAL (level)** — re-derive 0.06 annually from the measured average overround of T3's actual markets.

### §9F Verdicts

| Item | Current | Verdict | Action |
|---|---|---|---|
| T1 framing + min_edge=0.03 | STAT_FAMILY_TIER, T1 floor 0.07 | ✅ RESOLVED (c4380ca) | Stat-routing buckets shipped; floors monotone in calibration quality |
| T1 size mult 0.90× | BM shrinkage on win_prob | ✅ RESOLVED (c4380ca) | Baker–McHale shrinkage shipped; PICK_SCORE_TIER_MULT + VAKE_MULT["tier"] retired |
| T1B class | WR 46.9%/ROI +1.7% | DATA_GATED | Keep; bootstrap ROI>0 at n≥100; no stat-list expansion |
| T1 retirement test | family bootstrap n≥150 | ✅ RESOLVED (c4380ca) | n=30 checkpoint retired; formal record = ROI bootstrap at n≥150/family (in CLAUDE.md gates) |
| T3 min_edge=0.06 | WR 51.5%/ROI +5.3% | LOCKED / PERIODIC_RECAL | Keep; re-derive annually from measured T3 overround |

---

## §9G — Longshot Parlay Construction

**Current implementation** (run_picks.py:200–202, 4136–4233):
- 6 legs, safest-by-win_prob descending; max 2 legs/game, 1 leg/player; flat 0.25u; legs treated as independent (no copula). VALUE_PARLAY 5-leg fallback, same caps, 0.25u.

### Q6 — "Safest 6" vs EV-ranked selection
The literature is consistent ([OddsShopper "Math Behind Profitable Parlays"](https://www.oddsshopper.com/articles/betting-101/how-to-find-the-best-parlay-bets-today-using-expected-value-ev-y10), Unabated): with multiplicative payout, select legs on **per-leg EV ratio**, not standalone safety. Math: a 65%-WP/20%-edge leg contributes factor ≈1.20 to slip EV; a 70%-WP/3%-edge leg ≈1.03 — current ranking picks the 1.03 leg. Across 6 legs: six 1.10 legs → +77% slip EV vs six 1.03 legs → +19%. Mitigations: the pool is gate-filtered (all legs believed +EV), so safest-6 is still +EV — just not EV-maximal; and there's a legitimate *product* argument (a safest-picks longshot hits every ~2–3 weeks — better community content than a max-EV slip hitting every ~8 weeks).
**Verdict: NEEDS_CHANGE → ✅ RESOLVED (76fbb36, 2026-06-06).** Option (b) chosen: Longshot explicitly re-documented as a hit-frequency product (docstring + sort-line comment in build_safest6_parlay()) — selecting by win_prob maximizes how often the card has a winner (engagement value), accepted as intentional. EV-factor ranking rejected as a product-direction change without clear user benefit.

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
| Leg ranking | win_prob descending, documented | ✅ RESOLVED (76fbb36) | Re-documented as intentional hit-frequency product |
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
**Verdict: NEEDS_CHANGE → ✅ RESOLVED (3aad87f, 2026-06-06).** Per-leg floors kept; joint-EV existence floor shipped in BOTH builders: copula joint_prob > implied(parlay odds) + `SGP_JOINT_EV_MARGIN` (=0.025) for ANY slip to fire. Premium gate unchanged. ε re-tune DATA_GATED at the 100-scored-slip Platt gate.

### Q11 — Odds window +200–+450 (math)
- **3-leg**: per-leg decimal between 3.00^⅓=1.442 (≈−226) and 5.50^⅓=1.765 (≈−131). Legs −135 to −155 combine to +345–+428 — fits. Model-0.65 legs (fair −186) quoted −131…−186 carry positive edge. **Internally consistent.**
- **4-leg**: per-leg decimal forced to 1.316–1.532 (≈ −316 to −188, implied 0.653–0.760). Four −135/−155 legs combine to +632–+819 — **excluded by the cap** (intent: kill high-variance moderate-favorite combos — works). **Tension**: on a −250 leg (implied 0.714), the 0.65/0.62 floor is *below* implied — the leg floor alone admits −EV legs in exactly the regime the cap forces. This is where Q10's joint-EV floor is load-bearing.
**Verdict: PERIODIC_RECAL** — consistent for 3-leg; 4-leg safe only jointly with the Q10 fix (then LOCKED).

### Q12 — Premium gate vs published SGP hold
Published SGP hold: parlays 16–25% (NJ/IL regulated data), SGPs at the top of the range; Wizard of Odds estimates a 3-leg SGP costs ~7× the EV of the same legs straight ("correlation tax" ~15% off independence payouts stacked on per-leg vig). The premium gate margin ≥0.10 at +350 implies **≥+45% ROI** — appropriately strict and rare by design. The 0.25u default is the issue: given 20–30% structural hold, an SGP is only +EV when the model out-prices the book's own copula by the full hold — current leg floors don't enforce that. Empirical note: model→58% vs 69% actual on 52 slips suggests joint probs currently *under*-stated (Platt over-correction) — the safe direction, but by luck not design.
**Verdict: NEEDS_CHANGE → ✅ RESOLVED (3aad87f, same fix as Q10)** — joint-EV existence floor (ε=0.025) now gates ANY slip incl. the 0.25u default path; re-tune ε at the 100-scored-slip Platt gate (DATA_GATED).

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
| Per-leg floors 0.65/0.62 | + joint-EV floor ε=0.025 | ✅ RESOLVED (3aad87f) | Floors kept; SGP_JOINT_EV_MARGIN=0.025 existence floor live in both builders |
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
**Verdict: NEEDS_CHANGE → ✅ RESOLVED (76fbb36, 2026-06-06)** — R9 reclassified in code comments + CLAUDE.md as a product/optics rule, not EV. Score-gap + P&L monitor registered for n≥50 forced-over events; negative-CLV trigger long-term.

### Q9 — R10 same-stat cap
**Stronger basis than R7.** Same-stat picks share a projection model — textbook common-factor exposure: portfolio variance is dominated by the shared stat-model error factor when several positions load on it. Unlike game-level ρ (estimable from outcomes), *model-error* correlation is nearly impossible to estimate online — precisely the condition where a hard cap beats covariance sizing. The cap also self-limits the observed systemic failure mode (a miscalibrated family — e.g., pre-fix REB — can't put >1 losing pick per card).
**Verdict: LOCKED** — the best-justified hard rule in the system.

### Q10 — R12 5-day loss cooldown
Not evidence-based as risk control: one loss on a 55–60% pick has probability 0.40–0.45 *with the model correct* — likelihood ratio ≈ 1, posterior edge essentially unchanged. Conditioning selection on it is gambler's-fallacy-family behavior ([Croson & Sundali, JDM](https://www.cambridge.org/core/journals/judgment-and-decision-making/article/biases-in-casino-betting-the-hot-hand-and-the-gamblersfallacy/8A9D1813D42FFA25634E7FD26A46D484); [Cognition 2014](https://www.sciencedirect.com/science/article/pii/S0010027714000031)). Distinguish from the legitimate cousin: **persistent adverse line movement / negative CLV is information** (market disagreeing repeatedly = Bayesian evidence; a graded loss is not). Subtle selection cost: cooldown removes players exactly when the book may have moved the line *toward* you off the visible miss — sometimes the best re-entry. Honest classification: product-driven (not re-posting a player who just burned the card) with a real but unmeasured EV cost.
**Verdict: NEEDS_CHANGE → ✅ RESOLVED (76fbb36, 2026-06-06)** — R12 documented as product rule (gambler's-fallacy-adjacent) in code comments + CLAUDE.md; trigger replacement with negative-CLV condition registered for when CLV data matures (CLV ≤ −2pp on last pick, or 2+ consecutive losses with negative CLV).

### §9J Verdicts

| Item | Current | Verdict | Action |
|---|---|---|---|
| R4 REB-over shadow | post-fix shadow, no lift condition | DATA_GATED | Pre-register lift: n≥50 post-refit, calibration bias ±3pp, mean CLV ≥0 |
| R7 max-2/game | hard count cap | LOCKED | Sound heuristic under ρ-estimation error; optional per-game stake budget (~2u) |
| R9 directional balance | product rule (documented) | ✅ RESOLVED (76fbb36) | Reclassified; monitor forced-over score-gap + P&L at n≥50 events |
| R10 same-stat cap | 1/stat on Premium 5 | LOCKED | Best-justified rule — unestimable common-factor ρ is where caps beat sizing |
| R12 5-day loss cooldown | product rule (documented) | ✅ RESOLVED (76fbb36) | Reclassified gambler's-fallacy-adjacent product rule; negative-CLV trigger replacement when data matures |

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
**Verdicts: 12u LOCKED · per-pick sport caps PERIODIC_RECAL (relabel backstops) · 0.50u floor NEEDS_CHANGE → ✅ RESOLVED (76fbb36, 2026-06-06: floor lowered to 0.25u for ALL tiers).**

### §9K Verdicts

| Item | Current | Verdict | Action |
|---|---|---|---|
| 12u daily cap | ≈0.2–0.3 joint full Kelly | LOCKED | Correct conservative side; revisit at NFL go-live volume |
| Sport per-pick caps 8/8/5/5/4u | never bind | PERIODIC_RECAL | Ordering correct; relabel as bug backstops or convert to per-sport daily budgets |
| 0.50u stake floor (adjacent finding) | 0.25u all tiers | ✅ RESOLVED (76fbb36) | Floor lowered to 0.25u for ALL tiers; skip-below-0.35u logic rejected (complexity not justified) |

---

# Plan 10 — Assumed Value Research Audit (2026-06-06)

Audits ~26 statistical constants, tier assignments, and copula correlations shipped in
Plans 8–9 **without research backing**. Each is validated against published literature
*and* in-house `pick_log.csv` empirics. Research-only — no code changes this session;
corrected values / DATA_GATED conditions are reported for a later implementation pass.
Spec: `plan_10_full.md`. Groups researched A–GG; consolidated decision table,
NEEDS_CHANGE table, and corrected `STAT_FAMILY_TIER` block at the end.

### Phase 0 — "immediate action" code items: all already RESOLVED (verified read-only)

| Item | Spec claim | Actual current state | Verdict |
|---|---|---|---|
| Z1 sgp_builder NB_R["REB"] | stale 10.18 | **14.7** (synced 2026-05-30, sgp_builder.py:86) | ✅ already fixed |
| Z6 mlb_sgp_builder constants | possible stale copies | imports from sgp_builder/run_picks; no local NB_R/SIGMA | ✅ no drift |
| H2 evaluate_f5_lines tier | hard-coded T1B/0.03 | **T2 / edge≥0.05** (run_picks.py:3406,3411) | ✅ already fixed |
| gate_check T1-mult gate | stale gate present | removed; `count_t1_mult()` deleted (369fd7a) | ✅ already fixed |

### Step 0 — Empirical pick_log ground truth (PRIMARY for tier decisions)

`data/pick_log.csv`, 295 graded (W/L) picks, 2026-04-14 → 2026-06-05. ROI = Σprofit/Σstake
(American-odds payout; VOID/push excluded from both). CLV = mean of post-2026-05-31
non-blank `clv` rows only. **Earlier draft pull had a broken payout calc (negative ROI at
67% WR) — corrected here.**

**Per-stat (n ≥ 15 graded), sorted by ROI:**

| stat | n | WR | ROI | mean edge | mean CLV | n_clv | proposed tier |
|---|---|---|---|---|---|---|---|
| PARLAY | 77 | 0.247 | +0.697 | — | — | 0 | (parlay) |
| PTS | 34 | 0.676 | **+0.277** | 0.140 | — | 0 | T2 |
| TEAM_TOTAL | 20 | 0.550 | +0.073 | 0.060 | — | 0 | T2 |
| REB | 27 | 0.519 | +0.029 | 0.126 | — | 0 | T1 |
| AST | 15 | 0.467 | +0.017 | 0.134 | — | 0 | T1B |
| SOG | 43 | 0.488 | −0.012 | 0.129 | — | 0 | T3 (suspended) |
| 3PM | 34 | 0.529 | −0.018 | 0.150 | — | 0 | T3 |

Near-threshold (n=10–14, watch): **HA** (n=10), **OUTS** (n=10).

**Per-tier (⚠ `tier` column is historical — logged pre-restructure c4380ca, mixes old/new defs):**

| tier | n | WR | ROI | mean CLV | n_clv |
|---|---|---|---|---|---|
| T2 | 73 | 0.603 | **+0.140** | −0.018 | 4 |
| T3 | 33 | 0.515 | +0.053 | — | 0 |
| T1B | 49 | 0.469 | +0.017 | −0.029 | 5 |
| T1 | 58 | 0.466 | **−0.102** | — | 0 |
| KILLSHOT | 5 | 0.600 | +0.044 | — | 0 |
| SGP | 57 | 0.246 | +0.303 | — | 0 |
| LONGSHOT | 10 | 0.200 | +6.221 | — | 0 |
| DAILY_LAY | 10 | 0.300 | −0.470 | — | 0 |

**Reads that drive Group A et al.:** (1) PTS is the empirical anchor — high WR *and* ROI, clean T2.
(2) Monotone ROI tracks the proposed tier ladder T2 > T3 ≈ T1B > T1, but T1 (REB/HRR/REC) is the
*worst* historical tier (ROI −0.102) — the per-stat REB row (+0.029) is less alarming, so the
T1 deficit is partly HRR/REC/historical-mix, not REB alone. (3) **CLV is effectively unusable**
(only 9 post-reform rows total, both tiers slightly negative) — literature must carry the weight;
CLV grounding is reported as thin throughout. (4) DAILY_LAY (−0.470, n=10) and the longshot/SGP
extreme-variance ROIs are small-n and not tier-relevant.

---

## Group A — STAT_FAMILY_TIER assignments (16 stats)

Tier = stat-family **calibration bucket** (not conviction); lower BM shrinkage weight (w) =
shrink harder toward market. Floors: T2=0.05 (w .85, most trusted) < T1B=0.06 (w .80) ≈ T3=0.06
(w .70, specialty/high-variance) < T1=0.07 (w .75, least calibrated). 4 sport-cluster research
agents (opus + web search), cross-referenced with the Step 0 empirical anchor. **7 CHANGEs + 1
DATA_GATED relocation found** — several affect live picks.

| stat | current | rec. tier | verdict | basis |
|---|---|---|---|---|
| REB | T1 | T1 | **CONFIRM** | Lineup/opportunity-dependent (Kiriazis-Genest-Leblanc 2024 JQAS; Deshpande-Wyner 2016). In-house ~10pp over-confidence (61.6%→51.9%, n=27). NB r=14.7 correct. |
| 3PM | T3 | T3 | **CONFIRM** | Overdispersed low-count, volume-driven (Squared2020; Binomial Basketball). NB r=9.15 ✓. Empirical break-even (ROI −0.018). |
| PRA/PR/PA/RA | T2 | **T1B** | **DATA_GATED→CHANGE** | Positive component ρ *inflates* variance-of-sum & stacks errors (Cohen&Cohen 2018) — combos are **not** more projectable; "CLT smoothing" claim is false for correlated components. RA disabled 0W/7L (model 56.7% vs 0% actual). Move PR/PRA/RA→T1B at combo Platt gate (n=100); PA (guard-heavy, low-REB-var) may stay T2. Pre-register: relocate if combo calib bias >+3pp at n≥50. |
| HITS | T1B | T1B | **CONFIRM** | BABIP/batted-ball driven — slowest-stabilizing batter skill (~800 BIP; FanGraphs sample-size). Poisson ✓ (var/mu 0.873). Keep OUT of T2. |
| TB | T2 | T2 | **CONFIRM** | Self-driven (no runner context); power stabilizes fast (~150–200 AB). NB r=1.3 / component-Poisson convolution ✓. Most shrinkage-eligible T2 member. |
| RBI | T2 | **T1** | **CHANGE** | Canonical "stat to avoid" — opportunity/lineup-dependent, no predictive metric, ~74% zero games (FanGraphs). T2 (least shrink) is exactly wrong → T1. NB r=0.87 ✓. |
| RUNS | T2 | **T1B** | **CHANGE** | Context/lineup-dependent like RBI but batter's on-base skill adds a forecastable first step → one step less shrunk than RBI. Poisson ✓ (var/mu 0.969). (T1 acceptable if paired with RBI.) |
| HRR | T1 | T1 | **CONFIRM** | Combo of HITS+RUNS+RBI (2 of 3 context-noisy) + tail. NB ✓ but **r=1.5 is moment-matched; external evidence r≈1.83 — refit at MLB batter gate (possibly ZINB).** Shadow, n=2. |
| HA | T1B (susp) | **T1** | **CHANGE** | Least-controllable pitcher stat — BABIP ~71% of ERA-FIP variance (Beyond the Box Score 2015; FIP framework exists to strip hits out). On unsuspension → T1, not T2. NB r=13.41 ✓. |
| ER | T2 | **T1** | **CHANGE** | Luck/defense/sequencing-driven (BABIP ~71%, LOB% ~26% of ERA-FIP var). T2 unjustifiable for textbook regression-prone stat → T1. NB r=2.62 ✓. |
| BB | T2 | T2 | **CONFIRM** | Genuine command skill — pitcher-attributable, stabilizes ~60 BF, half of K/BB (best predictive metric). Poisson ✓ (var/mu ~0.97; monitor >1.15). |
| PC | T2 | T2 | **CONFIRM** | Manager-targeted ceiling, converges to season avg by ~3rd start. Starters-only frame ✓. Normal provisional (skew −1.93 → empirical-CDF at July refit; under-tail only). |
| SV | T2 | **T3** | **CHANGE + dist NEEDS_CHANGE** | Doubly-conditional event (availability AND save situation); most volatile pitcher role (industry unanimous). T2→T3. **Normal is a poor fit → conditional/Poisson P(situation)×P(convert) at refit.** |
| NRFI/YRFI | T2 (YRFI 0.08 override) | T2 | **CONFIRM** | Poisson λ model well-calibrated to published ~52–55% scoreless-1st. Family T2, YRFI deliberate higher hurdle — internally consistent. γ=0.65 DATA_GATED. |
| GA | T2 | **T3** | **CHANGE** | Goaltending = least-predictable position (RS→PO goalie r≈0.15; jfresh, ExpectedBuffalo). GOALS already T3 → GA should match. Poisson ✓ (team-level, Ryder 2004). |
| REC | T1 | **T2** | **CHANGE** | Target-driven volume — stickiest WR metric, *more* projectable than YARDS (which is T2). T1 (harshest) is backwards. Poisson acceptable but **NB candidate** (overdispersion, like 3PM/AST/REB). Re-confirm at NFL gate. |
| YARDS | T2 | T2 | **DATA_GATED** | NFL anchor, but Normal is a right-skewed approximation (gamma better in tail) and NFL is pre-go-live (rush-yards YoY r≈0.21). Hold T2 pending NFL σ/tail calibration. Keep ≤ REC's tier. |

**Live-impact CHANGEs (MLB/NHL props in current cards):** RBI→T1, RUNS→T1B, ER→T1 (MLB batter/pitcher
live), GA→T3 (NHL live), HA→T1 (on unsuspension). REC→T2 and YARDS are NFL (pre-go-live, no live effect).
SV→T3 + its Normal→conditional distribution fix is the strongest single finding (T2 was clearly wrong).
The combo (PRA/PR/PA/RA) relocation is gated on the existing 100-scored-combo Platt gate. **The Step 0
T1-tier ROI deficit (−0.102) is consistent with this group: the corrected tiering pushes the genuinely
noisy stats (RBI/ER/HA/SV/GA) toward heavier shrinkage, which is the right direction.**

---

## Group Z — sgp_builder.py copula correlations + MC

No published source gives exact same-team NBA prop-over ρ; the only hard anchor is the engine's own
COMBO_RHO. MC sample-size SE claims verified numerically exact.

| item | current | verdict | finding / action |
|---|---|---|---|
| same-team offense ρ | 0.35 | **DATA_GATED** | High end of published intra-game range (WoO NFL SGP matrix tops 0.42/0.35) but unverified. Keep as conservative ceiling ≤0.40; recalibrate from in-house teammate game-logs at n≥50 slips. |
| same-player multistat ρ | flat 0.28 | **CHANGE** | Internally inconsistent with engine's own COMBO_RHO (PTS/AST=0.233, REB/AST=0.251, PTS/REB=0.333). Replace flat 0.28 with a **pair-keyed COMBO_RHO lookup** (fallback 0.25 for 3PM pairs). Single source of truth. |
| same-team REB ρ | 0.20 | **DATA_GATED** | Board-competition pushes teammate REB ρ down; expect 0.10–0.20. Provisional; measure at n≥50 slips. |
| cross-team ρ | 0.10/0.08/0.02 | **CONFIRM** | Consistent with team-level ρ(home,away)=+0.227 (attenuated for player props) + pace literature. |
| pool_score weights | edge·0.40 + wp_excess·0.60 | **DATA_GATED** | **NOT a bug.** Safety-tilt is *more* defensible for a multiplicative parlay (one weak leg dominates survival) — correctly inverse to the prop scorer. Document why; refit split at n≥50 slips; do NOT flip to match prop scorer. |
| MC n=300/4000 | ranking/final | **CONFIRM** | SEs exact (2.5% / 0.7%). Optional: final 4000→10000 (~0.43% SE) for the EV-margin gate; low priority. |
| `_copula_joint_approx` linear interp | "15–20% error" | **NEEDS_CHANGE** | Direct sim confirms **systematic optimistic bias +8% (3-leg) → +29% (4-leg low-p)** — over-rates exactly the riskier 4-leg combos and can promote a worse combo into MC re-score. Replace with single-factor analytic equicorrelation CDF or (n_legs,ρ,min_p) lookup; min fix = deflate approx ×0.85–0.90. Deterministic math, no gate. |

## Group BB — mlb_sgp_builder.py copula + floors

All ρ are docstring-acknowledged structural priors (n=57 slips, no 100-slip refit). Literature validates
the **sign and ordering** of every value; exact magnitudes remain **DATA_GATED** at the builder's own
100-slip gate.

| item | current | verdict | finding |
|---|---|---|---|
| same-team batters ρ | 0.15 | DATA_GATED | Sign ✓; likely low for adjacent-order pairs (DFS stacking). Consider order-distance scaling (adjacent ~0.18–0.22) at gate. |
| two pitchers same game ρ | 0.10 | DATA_GATED | Shared-total link is one of several drivers; 0.05–0.15 band, 0.10 reasonable. Not "too low." |
| OUTS-over + opp-HITS-under ρ | 0.30 | DATA_GATED | Directionally strong (hits↔runs r≈0.80, WHIP r≈0.90); largest ρ correct. Consistent with Group-E longshot pair. Expect 0.20–0.35 at gate. |
| cross-team batters ρ | 0.08 | DATA_GATED | Ordering 0.02<0.08<0.15 correct (game-total only, no RBI-chaining). |
| MIN_LEG_WIN_PROB | 0.65 (MLB) vs 0.60 (NBA) | DATA_GATED | Higher MLB variance (PA Bernoulli, manager hooks) + thin n justify stricter floor. Don't loosen; revisit 0.62–0.63 at n≥100. |
| MIN_LEG_EDGE | 0.010 | **CONFIRM** | Intentionally weak per-leg screen; SGP_JOINT_EV_MARGIN=0.025 + wp floor are the binding EV gates (correlation, not per-leg edge, drives SGP +EV). |
| MAX_SGPS_PER_DAY | 3 (vs NBA 2) | **CONFIRM** | Slate-proportional (~15 MLB games vs ~5 NBA); arguably conservative. |

## Group L — POISSON_STATS vs NB_STATS membership

Cross-references STATISTICAL_FOUNDATIONS §1B/§16 (within-player var/μ measured from game-log tables).

| item | current | verdict | finding |
|---|---|---|---|
| REC | Poisson | **DATA_GATED** | No within-player reception dispersion data (NFL July). Poisson-by-convention only; target-volume swings may overdisperse. Decide at go-live (var/μ>1.15→NB). **POISSON_CUTOFF=8.5 hardening must ship first** (lines >8.5 route to uncalibrated Normal). |
| HITS Poisson vs HRR NB | as-is | **CONFIRM** | Consistent: HITS singles under-dispersed (var/μ=0.895); HRR overdispersion comes from RBI zero-inflation, not HITS. Two genuinely different distributions. |
| RUNS/BB/GA | Poisson | **CONFIRM** | Within-player var/μ = 0.969 / 0.992 / 0.830 — all ≤1.0 (published "overdispersion" is team/population frame, wrong for single-player pricing). GA sub-Poisson → near-mean 1–2pp caveat (PERIODIC_RECAL). |
| corr-stats r≈0.70 hard block | G11/G11b | **DATA_GATED** | 0.70 was **asserted (commit 954e984), never measured** — but structurally sound (TB/HRR contain HITS; pitcher stats all IP-functions). Hard block defensible (Kelly mult ~0.59 at ρ=0.70). Measure ρ from game-log tables + block-vs-penalty cost test at n≥50/group; annotate label "structural lower bound, unmeasured." |

## Group B — BM_SHRINKAGE_WEIGHT {T2:.85, T1B:.80, T1:.75, T3:.70}

**Headline: the "Baker–McHale (2013)" attribution is wrong.**

| item | current | verdict | finding |
|---|---|---|---|
| formula basis | "Baker–McHale (2013)" | **NEEDS_CHANGE (citation)** | BM (2013) shrinks the Kelly **bet size** toward zero by probability variance σ — it never blends probability toward market. The formula `w·model_p+(1−w)·implied_p` is a **linear opinion pool (Stone 1961) / Bayesian shrinkage-to-market**. Re-label in code + CLAUDE.md. Formula itself is valid. (Optional: implement the *real* BM σ-based size-shrinkage separately on the stake.) |
| tier differentiation | w by tier | **CONFIRM** | Inverse-variance/precision weighting justifies differentiating w by calibration quality (Bates–Granger 1969). Caveat: forecast-combination puzzle (Smith–Wallis 2009) — estimating fine weights adds variance; keep modest spread until data. |
| magnitudes 0.85/0.80/0.75/0.70 | as-is | **DATA_GATED** | Plausible but arbitrary; no source pins 5-pt increments. Bound to [0.65, 0.90] (market 10–35%); fit per-family by OOS Brier/log score at n≥150/family (Gneiting–Raftery 2007). |
| direction | T3 lowest w (.70) | **NEEDS_CHANGE** | Inconsistency: **T1 is worst ROI (−0.102) yet w=0.75 > T3's 0.70** — worst family should shrink *hardest*. If T1 holds at n≥150, drop T1 w to ≤ T3 (~0.70–0.72). Also disentangle the **vig-haircut role of w** (shrink toward *no-vig* implied for the calibration component, apply vig separately). |

---

## Group AA — gate_check.py Platt gates (MLB / SGP / Combo)

All three n=100 gates **CONFIRM** against the calibration sample-size literature (Peduzzi 1996 EPV
rule; Niculescu-Mizil & Caruana 2005 — Platt beats isotonic below ~2000 cases), but the binding
statistic is **minority events (min(W,L))**, not raw row count. Each gate carries a concrete action.

| gate | verdict | action at gate |
|---|---|---|
| MLB Platt (n=100) | **CONFIRM (floor)** | Fit **MLB-specific** Platt — do **not** inherit NBA A/B (calibration is population-specific). Start intercept-only (A=1, fit B); ~45 MLB events support 1 param; defer free slope to n≥300. Deploy only on OOS Brier >0. |
| SGP Platt (n=100 slips) | **CONFIRM** | **Stop applying marginal-prop Platt to individual legs** — the documented source of the 58%→69% under-confidence. Calibrate the **slip-level joint prob** vs realized slip WR (intercept-only; ~31 losses). The gate already counts graded slips (correct object). |
| Combo Platt (n=100) | **CONFIRM** | Combo-specific intercept-only fit (don't inherit single-stat A/B, don't stay uncalibrated). ~5pp inflation is the joint-from-marginals signature. Furthest-out gate (11/100, throttled by RA disable). |

*Engine improvement (optional): report EPV = min(W,L) alongside raw count in gate_check.py so the operator sees the real binding statistic.*

## Group K — VAKE_MULT["variance"] + KELLY_MARKET_MULT + default

| item | current | verdict | finding |
|---|---|---|---|
| VAKE_MULT["variance"] | {T1:1,T1B:1,T2:.85,T3:.65} | **NEEDS_CHANGE** | **Double-counts with BM shrinkage** — both channel the *same* parameter-uncertainty correction (BM's k IS a function of σ²). T2=0.85 also penalizes the empirically-*best* tier (inversion; should be monotone in measured dispersion). Retire into BM (as VAKE["tier"] already was), or keep only as a pure growth-variance damper re-derived from realized family variance. Prefer **sigma inflation** (moves wp/edge/score coherently). Fold into DATA_GATED Kelly-stack consolidation. |
| KELLY_MARKET_MULT | per-market dict | **NEEDS_CHANGE** | Uncalibrated bias patches, not variance scaling. **PTS over=0.50 on the BEST-ROI family (+0.277)** is a μ-overprojection patch mis-located in the sizing layer — move to projection/calibration. Mults <0.30 (3PM over=0.10, WNBA AST over=0.10) are **cosmetic** (0.25u floor overrides) → replace with explicit gating-exclusion. Calibrate remainder at n≥50/market (empirical-Bayes/James–Stein). |
| DEFAULT_MARKET_MULT | 0.75 | **CONFIRM** | Reasonable generic parameter-uncertainty discount (¼–½ Kelly practice). Don't tune in isolation — audit the **stacked** effective Kelly fraction (converter × .75 × var × corr × exp) against the ¼–½ band; under-staking, if any, lives in the stack. |

## Group J — pick-scoring constants

| item | current | verdict | finding |
|---|---|---|---|
| PICK_SCORE Default | 0.40 WP / 0.60 edge | **DATA_GATED** | Edge = wp−implied is the **noisier** signal (inherits wp noise + line noise); a top-K ranker enriches the noisier component (winner's/optimizer's curse, Xu 2025; Smith–Winkler). 60% on edge is the wrong direction → favor WP-heavy (0.50/0.50 or Conservative 0.55/0.45). 15% edge cap partially mitigates. Backtest at n≥150/family. |
| COLD_START_SCORE_PENALTY | −15/−10/−8/−5 | **CONFIRM** | Targets the **selection axis** (down-rank thin estimates) — distinct from min_cap/BM (magnitude+stake), so **not** a strict double-penalty (James–Stein supports monotone-in-thinness). Magnitudes DATA_GATED (re-fit at n≥150/sub-type; ideally derive from same σ² as BM). |
| INJURY_TRIGGER_BONUS | AST10/PTS8/SOG8/REB7 | **DATA_GATED** | Book-lag on injury news is real & exploitable (justifies the bonus; consistent with SLOW_BOOKS). AST>PTS ordering defensible (assist redistribution concentrates on one backup). Magnitudes uncalibrated → gate at n≥50/stat on **mean CLV captured**, not intuition. |

## Group I — KILLSHOT parameters

| item | current | verdict | finding |
|---|---|---|---|
| SCORE_FLOOR | 65 | **DATA_GATED** | Provisional internal-unit cut; retune at n≥30–50 (bucket ROI by score band, move floor to lowest band whose bootstrap CI excludes 0). n=5 far too thin. |
| MANUAL_FLOOR | 75 | **CONFIRM** | Manual > auto bar is correct/conservative (override reintroduces human overestimation bias). |
| SIZE_BASE/BUMP | 3u / 4u | **CONFIRM** | **Risk-coherent: 3u ≈ 0.19 full Kelly, 4u bump ≈ 0.11** (at wp .60/.70, −110). The plan doc's "~1.9× Kelly" was vs the 1/16.7 *converter*; vs true full Kelly it's strictly fractional, never overbets. 3× the normal ~1u stake = deliberate conviction overweight (industry typical 1.25–1.5×, aggressive but safe). Watch 12u daily / 8u NBA cap interaction (2 KILLSHOTs = 6–8u). |
| BUMP wp 0.70 / edge 0.06 | AND-gate | **DATA_GATED** | Structurally sound (both above ~3% +EV floor; conservative). Gate magnitudes at n≥30–50 (bumped vs non-bumped ROI separable?). |
| WEEKLY_CAP | 2 | **LOCKED** | Scarcity/signal-concentration judgment; no literature pins an integer; n=5 too thin. Revisit only via per-rank ROI-decay test, never a calendar tweak. |

---

## Group DD — PACE_ELASTICITY

**Provenance: these 6 exponents are in-house structural priors, NOT published values** (code's
"Research Brief 5" tag is internal; both briefs state "no published paper establishes pace
elasticity exponents"). Per-possession-stability theory predicts elasticity ≈1.0 for points/assists/
steals/blocks (per-100 rates are pace-invariant by construction) and substantial for rebounds
(total boards = missed_shots × reb%, and missed shots scale with possessions). All are July-refit
candidates via log-log regression `log(rate)=α+β·log(pace)` on the 83,719-row history.

| exponent | current | verdict | finding |
|---|---|---|---|
| pts | 0.90 | **DATA_GATED** | Close to theory ~1.0 (PPP pace-invariant); within 0.85–0.95 band. Expect β≈0.90–1.0 at refit. |
| fg3m | 0.78 | **DATA_GATED** | Defensible — 3PA share driven by shot-selection (Moreyball), not pure pace. Watch double-count with FG3M_BLEND_ALPHA path. |
| reb | 0.25 | **NEEDS_CHANGE** | Most inconsistent with theory — missed-shot volume (rebound denominator) scales with possessions → expect β≈0.4–0.7. **Refit jointly with the H01 `_REB_RATE_PRIOR` ~2× deflation** (both July) to avoid double-correcting. Don't ship without backtest (REGULAR_SEASON_STAT_SCALAR may already absorb some bias). |
| ast | 0.50 | **NEEDS_CHANGE** | Below theory ~1.0; EDGEMODEL §7C already flags AST elasticity ≈0.7–0.9 (Vegas-anchored, DATA_GATED). Refit. |
| stl/blk | 0.30 (shared) | **NEEDS_CHANGE** | Tempo-free stats → theory ~1.0; 0.30 well below. Keep on pure-possession branch (don't Vegas-anchor) but **decouple the shared constant** and refit each separately (AUDIT 2026-05-02 D5). Low priority (small absolute prop impact). |

## Group W — COMBO_RHO (NBA + WNBA)

All **CONFIRM** — these are *measured* within-player Pearson, not assumed.

| item | current | verdict | finding |
|---|---|---|---|
| NBA COMBO_RHO | 0.333/0.233/0.251 | **CONFIRM** | Reproduced exactly to 3 dp on 76,960 player-games (STATISTICAL_FOUNDATIONS §2); ordering PTS-REB>REB-AST>PTS-AST matches mechanics; consistent with moderate-positive published consensus. |
| WNBA COMBO_RHO | 0.294/0.188/0.200 | **CONFIRM** | Measured ~5-SE discount (SE≈0.009, 13,322 logs); lower WNBA pace plausibly explains it. **Flag PTS-AST=0.188 for re-check** at next WNBA refit — counter-intuitive vs higher WNBA league assist rate (67.5% vs 60.5%). |
| recal cadence | offseason | **CONFIRM (PERIODIC_RECAL)** | Within-player ρ is structurally stable; offseason cadence (already in §2) sufficient. Separate open items (not ρ): NB-consistent σ replacement + 100-scored-combo Platt gate. |

## Group H — evaluate_game_lines vs evaluate_props architecture

| item | current | verdict | finding |
|---|---|---|---|
| game lines no Platt/no BM | BLEND_ALPHA 0.25 only | **CONFIRM** | Prop-fit Platt does NOT transfer domains (Park 2020; Wang/TransCal 2020); game lines already market-anchored on the more-efficient market. If ever wanted, fit a *separate* game-line Platt — never reuse PLATT_A/B. |
| BLEND_ALPHA vs BM | one anchor per path | **CONFIRM** | They are **substitutes** (convex combo toward market, different spaces) — don't add BM to game lines or BLEND_ALPHA to props (double-anchoring). **Caveat:** props stack confidence×Platt×BM (triple, two market/center-ward) — monitor at H3/family gates; if under-confident, raise w (don't touch Platt). |
| game vs prop edge floors | props 0.05/0.07; game lines none | **NEEDS_CHANGE** | Game lines have **no lower edge floor** (only GG1 upper cap 0.10, GG3>0) while *less-efficient* props carry 0.05–0.07 — inverts efficiency theory (more-efficient market should demand ≥ bar). Add a GG lower floor ~0.03–0.05; DATA_GATED on graded game-line ROI by edge bucket (n≥50). |
| H2 F5 tier | T2 / check_game_gates | **CONFIRM** | Consistent with full-game lines (already RESOLVED). Inherits any new GG floor automatically. |

## Group CC — Vegas team-total constraint bounds

| item | current | verdict | finding |
|---|---|---|---|
| bounds | [0.80, 1.20] (±20%) | **DATA_GATED** | ±20% is wide vs the ~5–8% expected-total signal threshold; standard winsorization is 10–20%; prior internal review (research_brief_8 Q48) also recommended **[0.85, 1.15]**. Tighten to ±15%; gate on logging the empirical scale histogram (already captured by `diagnostics.record_team_post_vegas`). §7C LOCK covers architecture, not clip magnitude. |
| breach action | silent clip | **NEEDS_CHANGE** | Silent clip **masks a data error** (scale>1.20 = missing/stale players). Move to **warn-and-continue** + per-team integrity precheck (roster size, Σproj_min≈240, Vegas total present); skip the scale + flag for review on breach. Never abort the whole run for one team. |

---

## Group EE — capture_clv.py write window + SKIP_STATS

| item | current | verdict | finding |
|---|---|---|---|
| write gate | T-10 (first poll inside window) | **NEEDS_CHANGE** | Sharpest moves come from final injury bulletins / late scratches T-15→0; latching at the *first* poll inside T-10 can precede them. Change WRITE rule to **last pre-tip observation** (latch latest, commit at final poll ~T-3..T-5; daemon already polls to T+3). T-45..T+3 polling window stays LOCKED (§9C). Research-gated — validate no increase in post-tip/empty-market misses. |
| SKIP_STATS | {NRFI,YRFI,TEAM_TOTAL,GOLF_WIN,PARLAY} | **NEEDS_CHANGE** | Comment "no standard market coverage" is **false** for NRFI/YRFI (−110..−160 / +100..+130) and TEAM_TOTAL (a core efficient CLV market). Their exclusion is operational plumbing, not market non-existence — add CLV capture for the three. Keep PARLAY skipped (compounding legs defeat clean CLV) and GOLF_WIN (no tip-anchored close). |

## Group V — conf early-season penalty

| item | current | verdict | finding |
|---|---|---|---|
| conf thresholds | 0.70 (GP<10) / 0.85 (GP<20) | **NEEDS_CHANGE** | Round-number guesses shrinking toward **0.50** (a coin flip) — wrong target. Stabilization theory prescribes continuous `GP/(GP+k)` toward an *informative* prior (market). Label as priors; fit k from an early-season prop calibration backtest. |
| 20-game full-conf cutoff | GP≥20→1.0 | **CONFIRM** | Defensible single threshold (practitioner "wait 20 games"; stabilization is stat-specific — 3PM slower, REB/AST/BLK faster). |
| conf vs BM | both shrink early-season picks | **NEEDS_CHANGE** | **Double-shrinkage**: conf→0.50 *and* BM→market on the same low-GP picks. Replace conf with a **GP-conditioned BM weight** (`w_eff=w·GP/(GP+k)`) — single mechanism, anchored to market (the informative early-season prior). Also aligns NBA with the WNBA sigma-inflation design (currently incoherent). |

## Group R — corr_m / exp_m sizing multipliers

| item | current | verdict | finding |
|---|---|---|---|
| corr_m | 1.0/0.85/0.70 by same-game **count** | **DATA_GATED** | Magnitudes directionally OK (≈1/(1+ρ): ρ=0.33→0.75, ρ=0.20→0.83). **Flaw is the count-based trigger** — ignores correlation sign/magnitude, so it over-penalizes independent *cross-team/different-player* same-game legs (which can be ~0 or negative). Make correlation-aware via COMBO_RHO; set 1.0 when legs are independent. Refit at n≥50 multi-pick-per-game. |
| exp_m | 1.0 / 0.70 repeat | **DATA_GATED** | **Not a correlation term** (same stat, different players = independent) — it's a **model-error concentration hedge**; re-document as such (mis-placed next to corr_m). Refine: key to per-stat calibration confidence (PTS needs less cut than DATA_GATED stats); consider applying only to 3rd+ occurrence. |

## Group S — build_value_parlay (5-leg fallback)

| item | current | verdict | finding |
|---|---|---|---|
| existence | fires when longshot can't build; 0.25u flat; no per-leg +EV gate | **NEEDS_CHANGE** | Safest-leg selection with no +EV gate maximizes compounding vig (~14% hold) — presumptively −EV. It inherits longshot's EV deficiency **without** longshot's pre-registered LOCKED status. Add a **per-leg edge>0 admissibility gate**; return None rather than parlay an individually −EV leg. Keep 0.25u (engagement product). |
| "+100 floor" | `combined_dec>=2.0` branch | **CONFIRM (no-op)** | **The +100 floor does not exist** — that line is the decimal→American sign conversion, not a filter. No minimum-odds gate is enforced. Don't add one (would push toward longer, higher-vig legs); fix the labeling so it isn't misread. |
| selection | win_prob (safest) ranking | **DATA_GATED** | EV/edge-correlation-aware ranking is research-correct (own longshot docstring: EV-factor ~4× better slip EV), but win_prob is the same intentional hit-frequency tradeoff as the LOCKED longshot. Gate any switch on the family-bootstrap n≥150; layer a per-leg edge>0 filter meanwhile. |

---

## Group C — injury redistribution constants (EdgeModel)

| item | current | verdict | finding |
|---|---|---|---|
| _CREATOR_USAGE_SHARE | 0.30 | **DATA_GATED** | Directionally right, at upper-plausible end (on/off single-beneficiary usage spikes ~+6–8pp ⇒ ~0.20–0.30 of a star's vacated usage). Refit on own lineup/on-off data (regress teammate usage Δ on absent star's vacated usage); consider role-conditional (lower for small-ball/no-creator rosters). |
| _CREATOR_AST_RATE_THRESHOLD | 0.20 (of team assists) | **NEEDS_CHANGE (metric)** | "20% of *team assists*" under-discriminates — a 5-man rotation trivially averages 20% each. Re-specify against **AST%** (share of teammate FGs assisted while on court) where ~0.20 is a defensible role-player/creator boundary, or a per-100 assist rate. Keep value ~0.20 but fix the metric. |

## Group D — altitude / westward-travel minute reductions (EdgeModel)

Both apply a **minutes** haircut, but the literature measures these effects on **efficiency / win
probability**, never on minutes (rotation length is coach-controlled).

| item | current | verdict | finding |
|---|---|---|---|
| _ALTITUDE_REDUCTION | 0.035 (minutes, DEN/UTA) | **NEEDS_CHANGE** | Wrong metric + likely wrong magnitude. Measured altitude effects: visitor FT% −1.5pp, ~2.6 uncontrolled net-rating; a pace analysis found **no** possession/fatigue decrement. Drop the minutes haircut; if retained, model as a small **efficiency** multiplier (~0.5–1.0% per-possession) validated on the engine's own DEN/UTA road backtest. DATA_GATED. |
| _WESTWARD_TRAVEL_REDUCTION | 0.025 (minutes) | **NEEDS_CHANGE** | The ~9pp travel-direction effect is **win-probability**, not minutes — and a 2024 25,016-game study shows the circadian sign is **contested** (can *favor* westward-moving teams). Don't pass ~9pp through as a minutes haircut; re-specify as a win-prob/efficiency tilt keyed to time-zones crossed × game time. DATA_GATED. |

## Group E — SGP/longshot margin & ρ

| item | current | verdict | finding |
|---|---|---|---|
| SGP_JOINT_EV_MARGIN | 0.025 | **CONFIRM** | Just above the published ~2% pro +EV buffer, below the 0.10 premium gate (correct ordering existence<premium). SGP hold 15–25% ⇒ a thin existence floor is defensible. Hold DATA_GATED at n=100 slips; raise toward 0.03 only if boundary ROI<0. |
| LONGSHOT_PAIR_RHO | 0.35 | **CONFIRM** | Sign correct (early exit → more opponent PAs/runs = positive); 0.30–0.40 band midpoint (bounded below hits→runs r=.80 since OUTS is a noisier proxy). Mutually consistent with BB's 0.30. Ranking-only (never blocks) → low risk. |

## Group F — DAYS_REST_MAX_REDUCTION

| item | current | verdict | finding |
|---|---|---|---|
| DAYS_REST_MAX_REDUCTION | 0.07 | **CONFIRM** | Inside the published **played-player** B2B band (scoring −3–10%, minutes −9–14%); sound midpoint of 0.05–0.08. Don't raise as a flat cap — most of the larger *team* B2B deficit is intentional starter DNP (already handled by lineup/injury removal; double-count risk). Optional DATA_GATED age(>30)/coast-to-coast conditioning toward the 0.08–0.10 tail. |

---

## Group G — game-line tiers / double-shrinkage

| item | current | verdict | finding |
|---|---|---|---|
| game lines excluded from BM | BLEND_ALPHA only | **CONFIRM** | Correct — game lines are the most efficient markets + already market-anchored; BM on top = over-shrinkage (Satopää–Winkler under-confidence). (Nuance: BLEND_ALPHA shrinks the *projection*, BM the *win_prob* — not a literal double-count, but same direction; exclusion stands.) |
| TEAM_TOTAL → T2, BM .85 | BM-shrunk | **NEEDS_CHANGE** | Projection already absorbs the Vegas total (240-min constraint), so model & market probs aren't independent → BM at .85 is **partial double-count**. Raise w→~0.95 or bypass BM (treat like a game line). DATA_GATED n≥150. Keep the NBA TEAM_TOTAL-over block. |
| F5_TOTAL → T2 | BM .85 | **CONFIRM** | T1B→T2 was the right direction (highest BM weight = least shrink, fits high efficiency). Flag same mild double-shrink (F5_SCALAR market-calibrated + BLEND_ALPHA + BM); consider BM-bypass (DATA_GATED). |
| ML_DOG → T3, BM .70 | heaviest shrink | **NEEDS_CHANGE** | Heaviest market-shrink on the *most-efficient* market = inverted + circular; and **ML_FAV is not BM'd** (inconsistent). Favorite-longshot direction is sport-specific (NCAA/horse longshots overbet; **MLB favorites overbet → dogs *underpriced***, so shrinking MLB-dog probs discards real edge). Exclude ML_DOG from BM (preferred, restores game-line consistency) or raise w + sport-aware. T3 looks legacy. |

## Group N — WNBA constants (all pre-go-live)

| item | current | verdict | finding |
|---|---|---|---|
| EARLY_SEASON_EDGE_MULT | 0.80/0.90 (sigma inflation) | **DATA_GATED** | Direction + ~20% magnitude literature-supported (early-season bias, Paul–Weinbach 2007; CI ±31%@10g). Exact factors/14-21d thresholds are placeholders. Recalibrate at go-live; consider re-keying days→games-played for consistency with the opening gate. |
| SIGMA_WNBA 3PM mult | 0.48 | **DATA_GATED (flag)** | **Copied from PTS=0.48** (in-code: PTS/AST/REB cite empirical CV, 3PM cites none) — wrong-signed (WNBA 3PM is the *most* volatile, var/μ=1.709). Low live impact (3PM is NB-routed via NB_R_WNBA=1.340; sigma is z-score/combo proxy only). Refit empirical CV at next WNBA pass — expect ≫0.48. |
| COMBO_RHO_WNBA | 0.294/0.188/0.200 | **CONFIRM** | The "<100 rows" worry conflates the betting sample with the **estimation** sample (13,322 game-logs ≫ N≈250 stability point, Schönbrodt–Perugini 2013). Statistically reliable — do **not** fall back to NBA. Re-verify at full DB refresh, not gated on pick counts. |
| OPENING_GATE_GAMES | 2 | **DATA_GATED** | A noise floor (strips opening-night variance), **not** a stabilization point (stats need dozens of games). Complementary to the sigma window. Consider raising to 3–4 if go-live data shows 2-game-sample picks miscalibrated. |

## Group O — MLB GAME_SIGMA {total 4.0, spread 3.8, team 3.0, ml 4.75}

**Live-impact NEEDS_CHANGE — MLB game-line sigmas are too narrow → overconfident totals/spreads.**

| item | current | verdict | finding |
|---|---|---|---|
| total | 4.0 | **NEEDS_CHANGE** | Structurally too narrow: published total-runs SD = **4.60** (Roberts 2020); variance algebra floor = team×√2 ≈ **4.4** even under independence. 4.0 is *below* the independence floor → over/under win-probs overconfident (~13% too tight). Re-derive from the 8095-game DB (like NBA/NHL/WNBA); interim **4.6**. |
| spread / team / ml | 3.8 / 3.0 / 4.75 | **NEEDS_CHANGE** | **team=3.0 correct** (per-team run SD ≈3.1). spread=3.8 ~8–15% too narrow (run-diff SD ≈4.1–4.4). **ml=4.75 inconsistent** — should equal spread (P(margin>0) under same distribution, per NHL precedent); 4.75 was hand-set (6.0→4.75). Calibrate from DB; interim **spread=ml=4.2, team=3.0**. |

## Group M — MLB_PARK_FACTORS

**Dormant (unapplied — SaberSim inputs already park-adjusted; NRFI omits it as a double-count guard).**

| item | current | verdict | finding |
|---|---|---|---|
| currency | COL 1.28, TEX 1.05, KC/MIN/DET 0.95–0.98 | **NEEDS_CHANGE** | Stale + directionally wrong: COL too low (~1.33), **TEX inverted** (now pitcher park ~0.95), KC/MIN/DET now hitter-friendly (~1.05). Zero production risk today (unapplied) but unsafe as a reference. Add a "STALE/UNVERIFIED — do not apply without refit" docstring warning. |
| type (runs index) | single run multiplier | **CONFIRM** | Runs index is the right type for run totals/NRFI (runs ≠ HR factors — Kauffman high runs but low HR). If HRR park-adjust ever wanted, add a *separate* HR dict. |
| applied scope | defined, never read | **DATA_GATED** | Verified dormant (2 references: definition + NRFI double-count-guard comment). Gate any activation on (a) a 2023-25 runs refit AND (b) a park-*neutral* input source (not SaberSim). |

---

## Group P — Daily Lay thresholds

| item | current | verdict | finding |
|---|---|---|---|
| MIN_DAILY_LAY_MARGIN | 4.0 | **DATA_GATED** | Judgment screen, not researched — NBA has no key numbers, margin SD ~12–13; a 4-pt projected edge isn't independently "reliable." Largely redundant with the LOCKED cover_prob≥0.58 gate. Gate to §9E metric #5 at n≥20 slips. |
| MIN_LEG_EDGE_DAILY | 0.025 | **CHANGE** | 2.5pp sits *below* the published +3–5% +EV band; §9E never validated it. Raise to **0.03** interim (conservative while gate empty); re-tune at §9E n≥20 slips. Don't go below 0.025. |

## Group T — empirical line-threshold gates (tiny samples)

| item | current | verdict | finding |
|---|---|---|---|
| G8B/G8C/G8D lines (4.5/3.5/1.5) | shadow blocks | **DATA_GATED** | Cutpoints are tiny-sample artifacts: G8B 0/5 (Wilson [0,.43], one win flips it), **G8C 6/14 is pure noise** (p=.33), **G8D 8/16 is *at* breakeven, not below** — its loss rationale is wrong; only model-overprojection (70→50%) is the (marginal) signal. *Direction* supported by mechanism (Poisson underdispersion + FLB). Keep as shadow; reclassify cutpoints DATA_GATED (n≥30 directional via **Wilson** lower bound vs .524; n≥100 permanent). Recast G8D as a calibration cap; re-test whether the hard block still adds value *on top of* BM shrinkage. |
| G_OUTS_UNDER WP<0.60 | block | **NEEDS_CHANGE** | **Contradicts the data**: the outs distribution is left-skewed (early exits common) so books *over*-estimate outs → unders should win *more*, not "lose structurally." 0.60 was never researched and is **stale post-σ-fix** (0.311→0.27). Replace with an EV/edge floor (like WNBA); fix real over-projection in the projection (manager-hook/lineup). Retune with MIN_LEG_WIN_PROB_OUTS=0.62 at n≥40. |
| G_HA_DIR (block HA/HITS overs) | permanent | **NEEDS_CHANGE** | Code admits "no research basis" — that's **missing data, not a measured bias** (literature flags HA *overs* as a live edge: hitter parks, May offense). Inconsistent with HITS/HA→T1B-both-directions. HA is moot (suspended); run **HITS over in shadow** (currently a hard kill → no data accrues), decide at n≥30. |

## Group U — R11 AST-under ban

| item | current | verdict | finding |
|---|---|---|---|
| R11 (AST under 1.5/2.5 banned) | hard rule | **NEEDS_CHANGE** | Structural vig thesis partly real, but the ban is **calibrated on noise** (n=15, WR .467, ROI **+0.017** — marginally *positive*; CI ±25pp). The new tier system already screens these (AST→T1B floor 0.06 + BM w=0.80). Reclassify as a DATA_GATED *protective* rule (mirror §9J R4/R9/R12): keep live interim, **strip the "sub-elite" empirical framing**, log blocked picks to pick_log_blocked.csv, pre-register lift at n≥40 shadow (calib bias ±3pp + CLV≥0). |

## Group Y — miscellaneous

| item | current | verdict | finding |
|---|---|---|---|
| Y1 PLATT_SPACE="raw" | sigmoid(A·p+B) | **NEEDS_CHANGE (gated)** | Raw-probability space is **theoretically wrong** — Platt assumes a *logit* input (logistic linear in log-odds). Already correctly DATA_GATED until H3. Migrate to logit-space *at* H3 (intercept-only, A=1; change space+formula+A/B together). No action before H3. |
| Y2 G_HA_DIR vs T1B | apparent double-block | **CONFIRM** | Not contradictory — **tier = calibration/shrinkage routing; gate = tradeability** (two independent layers). Add a one-line clarifying comment; optionally drop HA from G_HA_DIR's tuple (already suspension-short-circuited) — cosmetic. |
| Y3 SLOW_BOOKS {fanatics,hardrockbet,betrivers} | display tag | **DATA_GATED** | Soft-book-lag premise sound, but the specific trio is unvalidated; **BetRivers reportedly carries few/no player props** (can't lag on what it doesn't post). Display-only → low risk. Validate on own late-run CLV at n≥30/book; re-examine BetRivers. |
| Y4 VALUE_PARLAY_SIZE=LONGSHOT_SIZE=0.25 | flat | **DATA_GATED** | Both at the minimal-stake floor (Kelly intentionally abandoned for parlays) → equality harmless but unevidenced. Variance ordering says value_parlay (5-leg) should be **≥** longshot (6-leg), never less. Gate at n≥50 value_parlay slips. |

## Group Q — F5_SIGMA

| item | current | verdict | finding |
|---|---|---|---|
| F5_SIGMA values | {2.65, 2.70, 2.10} | **DATA_GATED** | No calibration source/n cited (unlike full-game GAME_SIGMA). The "±0.1 for park variance" bump **double-counts** MLB_PARK_FACTORS (already applied to the *mean*) — remove it. Recalibrate from real F5 game data (n≥500); consider an NB/Poisson F5 path at July refit. |
| scaling consistency | vs full-game | **NEEDS_CHANGE** | √-window scaling (σ_F5 ≈ √0.54·σ_full) gives **total≈2.94 / spread≈2.79 / team≈2.20** — all current values are **too narrow** (opposite of the comment's rationale), and first-inning variance concentration pushes total higher still. **Cross-dependency with Group O**: if full-game total is corrected to ~4.6, F5 total scales to ≈3.4 — recalibrate the two together. Interim: 2.90–2.95 / 2.79 / 2.20. |

## Group GG — context_research.py (display-only; gate n≥50)

| item | current | verdict | finding |
|---|---|---|---|
| _FACTORS (15) | rlm/weather/.../public_sharp | **NEEDS_CHANGE** | Re-anchor **era_fip to ERA−xFIP/SIERA** (FIP is the weakest forward predictor); **collapse the rlm/line_move/public_sharp triplet** (same sharp-money signal counted 3× — can dominate the ±2 vote); demote umpire (ABS era); merge/drop division (weak). Keep core (rest/travel/pythag/rlm/injury/form/weather/bullpen). Reweight only against graded outcomes. |
| weather "wind ≥10mph" | binary | **CONFIRM** | 10mph is a real run-environment inflection — but **encode direction** (wind-out+over confirms; wind-in+under confirms). Park-specific; domes neutral. |
| era_fip gap ≥1.0 | FIP-based | **NEEDS_CHANGE** | Re-anchor to ERA−xFIP/SIERA; keep ≥1.0 as a first-pass cutoff but DATA_GATE the exact number on the 8095-game DB. |
| GG2 CTX adjustment magnitude | unimplemented | **DATA_GATED** | Keep verdicts categorical (LLM judges miscalibrate fine scales + are systematically overconfident). When enabled: cap the nudge tiny (≤1–2pp wp), ranking-only first, require it to lift CLV before any sizing role; ignore the model's self-confidence. n≥50 display-behavioral, n≥150 sizing. |

## Group FF — EdgeModel minor constants

| item | current | verdict | finding |
|---|---|---|---|
| LEAGUE_AVG_TOTAL | 222.0 | **CHANGE** | Stale — 2025-26 ≈ **229** (~114.5/team); 222 is ~3% low and biases the Vegas pace prior `_base_pf` *upward*. Raise to ~229; PERIODIC_RECAL each season. |
| TEAM_MIN_FLOOR | 180.0 | **DATA_GATED** | No literature anchor (180/240=0.75 "heavy vacancy"); validate the kink at n≥40 vacated games. |
| MIN_AVAILABILITY_WEIGHT | 0.30 | **DATA_GATED** | Arbitrary floor; grid 0.20/0.30/0.40 against MAE at n≥50 vacated games. |
| _AVAIL_KEY_MPG_THRESHOLD | 12.0 | **CONFIRM** | Consistent with the validated role-tier rotation floor (≥12 MPG, §8E); intentionally more inclusive than the 15-MPG convention (correct for a key-player gate). |
| MIN_GAMES_FOR_TIER | 10 | **CONFIRM** | Minutes are the most-stable NBA stat (Medvedovsky 2020); already validated on 76,604 snapshots (§8E). |
