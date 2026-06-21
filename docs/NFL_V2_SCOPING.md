# NFL V2 Models — Scoping Document

*Created 2026-06-20 from the master implementation spec (`master_implementation_spec`,
V1 §8-9 + V2 §6-9). The biggest **model** gap in the spec and the only one with a hard
external deadline (NFL season opens **2026-09-07**).*

---

## Build progress (2026-06-20) — Phases 1, 2, 4 SHIPPED
Built in an isolated worktree `C:\Dev\EdgeModel-nfl` on branch **`feat/nfl-v2`**
(off the in-flight `feat/wnba-projector` tip; own dev-DB snapshot; live DB + parallel
WNBA session untouched). Pushed to `origin/feat/nfl-v2`, not merged to main (waits on
the WNBA branch landing). Commits:
- **`c5da037`** F4 — PBP red-zone ingestion (`nfl_pbp_fetcher.py`): inside-10 + RZ
  counts per player/team/defense from `nflreadpy.load_pbp` (2023-25; 8k player-weeks).
- **`9ac8ffd`** F5 — red-zone TD models in `project_nfl_player`: rushing λ = inside-10
  share × team vol × regressed conv (0.40/prior 85); passing λ = RZ-att EWMA × 0.41 ×
  opp × game-script; receiving λ = RZ-tgt share × team RZ vol × 0.41 × opp. Validated
  vs real goal-line/RZ roles. `source='nfl_v2'`.
- **`7366140`** F6 — game-line V2: real total O/U (kills `p_over_total=0.5`), team
  totals, ML key-number bump. σ_total=13.0 (empirical residual SD).
- **`37a1277`** total-dispersion calibration (see finding below).

### ⚠ KEY FINDING — NFL totals have NO market edge yet (shadow-only)
385-game backtest (2023-24): the EPA→points total is **mean-unbiased** (proj 44.2 vs
market 43.8 / actual 45.3) but was **2× over-dispersed** (SD 6.7 vs market 4.5) →
fixed by a 0.67 dispersion shrink (spread preserved). **However**, the model's total
*disagreements with the market remain anti-predictive* (P(over)>0.55 → 49% over;
<0.45 → 57% over) — EWMA EPA chases hot streaks that regress. **Do not bet NFL totals**
until the projection adds regression-to-mean / pace / weather. Spread was healthier
(corr 0.76, dispersion matched) but was not directionally validated.

### Phase 3 / A1 — yardage dispersion calibrated (DONE, EdgeModel `3c5c3a4`)
Extended `calibrate_distributions.py` with position-scoped NFL configs and fit the
**within-player** CV (σ=CV·μ — what the betting engine prices from). Replaced the
guessed multipliers in `nfl_player_projector.py`:
- passing_yards 0.26 → **0.314** (min 35) — was too tight   [59 QB / 1634 g]
- rushing_yards 0.70 → **0.545** (min 14.5) — was too wide  [120 RB / 2982 g]
- receiving_yds 0.85 → **0.705** (min 13) — was too wide    [362 / 9427 g]
TD counts confirm Poisson (var/μ 0.80-0.92). The spec's Gamma/hurdle/mixture were
**not** used: the engine prices Normal-from-CV, passing yards aren't bimodal, and the
receiving hurdle is already implicit in the unconditional EWMA mean.

### A2 — JonnyParlay prop wiring (NOT done; bigger than first scoped)
**Finding:** NFL props are not wired into the betting engine *at all* — `SPORT_KEYS`
has NFL but there is **no NFL prop-market→stat mapping** in `market_config.py`, the tier
table uses a single generic `"YARDS"` label (can't carry the 3 distinct CVs), there is
no `SIGMA["YARDS"]`, and nothing loads `nfl_player_projections`. So A2 is a **full
new-sport integration into live pricing code**, replay-and-test-gated — not a few
additive constants (those would be dead config). Recommended approach when tackled:
- **Use `sigma_override`** (pass EdgeModel's per-stat `proj_*_yds_sigma` into
  `calc_prop_prob`, `prob_core.py`) rather than `SIGMA[label]` constants — this sidesteps
  the single-`YARDS`-label problem and reuses A1's fitted per-stat σ directly.
- Add NFL prop markets (pass/rush/rec yards, receptions, anytime TD, passing TD) to
  `market_config.py`; map each to a distinct stat label; tier them.
- Add a loader for `nfl_player_projections`; apply the CLAUDE.md **POISSON_CUTOFF
  hardening** so REC (receptions) doesn't mis-route at lines >8.5.
- Gate: `pytest -m "not network"` green + replay byte-identical. Offseason — no urgency.

### Validation backtest (2024, 5,699 player-games / 385 games) — EdgeModel `8d9b73d`
Point-in-time backtest caught and fixed two miscalibrations, diagnosed a third:
- **TD lambdas over-projected** rush +31% / rec +30% (passing fine). Fixed:
  `LEAGUE_INSIDE10_CONV 0.40→0.305` (empirical 0.282), receiving onto its own
  `LEAGUE_RZ_REC_RATE=0.315` (empirical 0.239). Post-fix ratios rush 1.03 / rec 1.00.
- **Yardage σ — calibrated on the pricing population** (final CVs **0.36/0.62/0.72**,
  `f0aa1db`). The path here was a lesson in population choice: A1's within-player CVs
  (0.314/0.545/0.705) were nearly right; a first "fix" to 0.51/0.77/0.93 was calibrated
  on the conditional-on-*actual*-usage population (selection-inflated → too wide); the
  final values target players with real *projected* usage (what a prop is carded for) →
  SD(z)=1.00/1.01/1.00, cover90 0.90/0.94/0.94. *Lesson: calibrate σ on the population
  you actually bet.*
- **No usage model needed.** The "mean under-projects high-usage games" (+0.36σ, up to
  +0.75σ at 15+ carries) was a **collider artifact** of filtering on *actual* usage —
  unconditionally and on the pricing population the mean is ~0 (unbiased). The decomposition
  also showed efficiency (ypc) is unbiased, volume residuals aren't predictable from game
  script (corr 0.05), so a usage model couldn't help even if a bias existed. Dropped.

### Game-line model rework (NOT done) — totals AND spreads have no market edge
Backtest confirmed **both** game lines are non-predictive vs market: total disagreements
anti-predictive; spread MAE 10.34 vs market 9.53 with ATS cover 50-57% in the wrong
direction. Rework = regression-to-mean on EPA + opponent-adjustment + market-anchor +
pace/weather. Larger effort; prerequisite for game-line go-live. Gated (tail-predictiveness
must flip + CLV ≥ 0, else shadow-only) — **and may not succeed**; game lines stay shadow.

---

## 1. Current state (what exists today)

NFL has a working **V1 skeleton** in EdgeModel — both files stamp `"source": "nfl_v1"`:

### `EdgeModel/engine/nfl_player_projector.py`
- Means = **EWMA** (span 6 weeks) of each player's weekly logs, nudged by a tight
  opponent-defense factor from team EPA-allowed (`_def_factor`, clipped ±12%).
- Dispersion = **fixed CV multipliers**, NOT fitted distributions:
  `PASS_CV=0.26`, `RUSH_CV=0.70`, `REC_CV=0.85` → σ = CV·μ (Normal).
- TDs = EWMA rate → Poisson; anytime TD = `1 − exp(−(rush_td + rec_td))`.
- The docstring itself flags the deferrals (§7 RZ-attempt × 0.41 needs play-by-play).

### `EdgeModel/engine/nfl_game_lines.py`
- **EPA power ratings** ARE implemented: EWMA span 8, Hermsmeyer WEPA weighting
  (`W_OFF=0.55`, `W_DEF=0.45`), `pts = LG_PPG + W_OFF·off + W_DEF·opp_def_weakness ± HFA/2`.
- Spread + win prob via Normal on margin (`SIGMA_SPREAD=13.45`, frozen). 1H total/spread
  via flat share constants (`0.48`/`0.52`).
- **Stub:** `p_over_total` is hard-coded to **0.5** — there is no total O/U distribution,
  and there are **no key-number adjustments**. Team-total / ML are not priced as NB.

**Verdict:** functional projections exist, but at V1 fidelity. They were never go-live
validated (NFL not started — no shadow, no Platt, no gate; see Part-4 go-live audit).

---

## 2. Spec gaps (V2 — what's missing vs the spec)

| Spec § | Market | Current | Gap to close |
|--------|--------|---------|--------------|
| V1 §8.1 | Rushing/receiving/passing yards dispersion | Fixed CV·μ | **Gamma MLE** fit (α, scale) per player/role |
| V1 §8.4 | Receiving yards | EWMA·CV Normal | **Hurdle-Gamma** — Stage 1 logistic P(yds>0), Stage 2 Gamma |
| V1 §8.5 | Passing yards | EWMA·CV Normal | **Mixture of two Normals** (blowout-stop vs full-game components) |
| V2 §6 | Anytime / rushing TD | EWMA Poisson, flat | **Inside-10 carry share**, RB conversion-rate regression (prior=85 carries), YoY-regressed share, XGBoost anytime-TD framework |
| V2 §7 | Passing TD | EWMA Poisson | **RZ pass-attempt formula** (RZ att × ~0.41), opponent RZ-TD-rate adj, game-script spread adj; add ρ to copula (QB passTD↔passYds, QB passTD↔game total via Frank copula) |
| V2 §8 | 1H total / 1H spread | Flat 0.48/0.52 shares | **Key-number bumps**, derived `σ_1H` (total vs spread distinct), 2H σ |
| V2 §9 | Team total / ML | Not priced | `mu_team = (total ∓ spread)/2`, team-total key-number bumps, ML from spread/σ, **total O/U distribution** (replaces the `p_over_total=0.5` stub) |

Not a gap: nothing here is "broken" — it's all unbuilt V2 sophistication on top of a V1 base.

---

## 3. Data dependencies (must land before modelling)

- **`nflreadpy`** (recommended; `nfl_data_py` is archived but still works) — play-by-play,
  weekly, schedule, roster, injury.
- **Play-by-play filters:** inside-10 rushes, RZ (inside-20) pass attempts/targets — for
  TD share models (V2 §6-7). Not currently ingested.
- **RZ shares:** per-player inside-10 carry share + WR/TE RZ target share (rolling 6-game).
- **Weather feed** + **indoor-stadium list** (spec V1 §9.3-9.4; `roof` column: dome/
  retractable/outdoor/open) — for outdoor totals.
- **WOPR / target share / air-yards share** — already available in weekly data; the V1
  projector carries `wopr` as metadata but does not weight projections by it yet.

EdgeModel has `nfl_stats_fetcher.py` already; confirm which of the above it pulls vs. what
needs adding before any V2 model work.

---

## 4. Phased build order (against the 2026-09-07 season)

Spec Part-4 NFL timeline: **player props selective go-live ~Week 6 (early Oct)**, **game
lines ~Week 14 (mid-Dec)** — game lines need ~300 graded picks at 1 slate/week (~19 weeks),
so game-line shadow must start Week 1.

1. **Now → preseason:** land data deps (§3) — inside-10/RZ PBP, weather, WOPR wiring.
   Fit distribution families offline (Gamma MLE, hurdle-Gamma, mixture-normal) on prior
   seasons; validate VMR/Brier vs the V1 CV baseline.
2. **Preseason:** build V2 TD models (inside-10 carry share, RZ pass-att, anytime-TD) and
   the team-total / ML / total-O/U pricing that replaces the `p_over_total=0.5` stub +
   key-number bumps (§8-9).
3. **Week 1 (Sep 7):** game-line **shadow** starts (long lead time to 300 picks). Player
   props shadow starts too.
4. **~Week 6 (early Oct):** player-props selective go-live IF gate passes (Brier ≤ baseline,
   ECE < 0.05 per market).
5. **~Week 14 (mid-Dec):** game-line go-live once ~300 graded picks accrue and gate passes.

**Hard dependency for go-live:** none of the Part-4 go-live infrastructure exists yet
(no `*_phase.json`, `*_platt.json`, gate-check scripts, per-market Platt). NFL go-live
either needs that subsystem built first, or to ride JonnyParlay's existing ad-hoc gate
mechanism the way MLB/WNBA did. Decide that before Week 1.

---

## 5. Out of scope here
Implementation. Also the broader Part-3 monitoring subsystem and Part-4 go-live state
machine (tracked separately) — NFL can launch on the existing ad-hoc path if needed.
