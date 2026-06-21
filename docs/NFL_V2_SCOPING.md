# NFL V2 — Status & Build Record

*Started 2026-06-20 from the master implementation spec (V1 §8-9 + V2 §6-9). NFL is the
only model gap with a hard external deadline — **season opens 2026-09-07** (spec Part 4:
player props selective go-live ~Week 6 / early Oct; game lines ~Week 14 / mid-Dec). All
EdgeModel work lives on branch **`feat/nfl`** in worktree `C:\Dev\EdgeModel-nfl` (own
dev-DB snapshot; the live DB and the parallel `feat/wnba-projector` session are untouched).
Pushed to `origin/feat/nfl`; not merged to main until the WNBA branch lands.*

---

## Status at a glance
| Area | State |
|------|-------|
| Player-prop **models** (TD + yardage) | ✅ Built, backtest-calibrated, trustworthy |
| Engine **pricing** of NFL props | ✅ Wired in JonnyParlay (offseason-validatable part) |
| Engine **data feed** for NFL props (A2 data half) | ⏳ Deferred to preseason (needs live odds) |
| Game **lines** (total + spread) | ⚠️ Built but **no market edge** — shadow-only, rework needed |
| Go-live infra (phase/Platt/gate per spec Part 4) | ❌ Not built (would ride JonnyParlay's ad-hoc gates) |

---

## What shipped (EdgeModel `feat/nfl`)
- **`c5da037` F4 — PBP red-zone ingestion** (`nfl_pbp_fetcher.py`): inside-10 + RZ counts
  per player/team/defense from `nflreadpy.load_pbp` (2023-25, 8k player-weeks).
- **`9ac8ffd` F5 — red-zone TD models** in `project_nfl_player`: rushing λ = inside-10
  share × team vol × regressed conv; passing λ = RZ-att EWMA × 0.41 × opp × game-script;
  receiving λ = RZ-tgt share × team RZ vol × rate × opp; anytime = 1−e^−(λ_rush+λ_rec).
- **`7366140` F6 — game-line V2**: real total O/U (killed `p_over_total=0.5`), team totals,
  ML key-number bump (σ_total=13.0 empirical).
- **`37a1277` — total-dispersion calibration** (see findings).
- **`3c5c3a4` F7 + `8d9b73d` + `f0aa1db` — yardage/TD calibration** (see findings).
- **JonnyParlay `569d8e0` — A2 prop pricing half** (engine can price NFL props).

## Key findings (the validation work — more valuable than the code)
1. **TD lambdas** over-projected rush +31% / rec +30% (spec conversion constants `0.40`/`0.41`
   too high vs empirical `0.282`/`0.239`). Recalibrated → ratios rush 1.03 / rec 1.00 / pass 0.96.
2. **Yardage σ** — final prediction CVs **0.36 / 0.62 / 0.72**, calibrated on the *pricing*
   population (players with real projected usage) → SD(z)≈1.0, unbiased. A first cut on the
   conditional-on-*actual*-usage population over-widened it; the within-player CVs were nearly
   right. *Lesson: calibrate σ on the population you actually bet.*
3. **No usage model needed.** The "high-usage mean bias" was a collider artifact of filtering
   on actual usage; unconditionally the yardage mean is unbiased. Efficiency (ypc) is unbiased
   and volume isn't predictable from game script (corr 0.05) — a usage model couldn't help.
4. **Game lines have no market edge** — *both* total (disagreements anti-predictive) and spread
   (MAE 10.34 vs market 9.53; ATS 50-57% wrong way). EWMA-EPA chases streaks that regress.
   **Stay shadow-only.**
5. The spec's **Gamma / hurdle-Gamma / mixture-of-normals** for yardage were **not built** by
   design — the betting engine prices Normal-from-CV, passing yards aren't bimodal, and the
   receiving hurdle is implicit in the unconditional EWMA mean.

## A2 prop pricing — what's done vs deferred
**Done (JonnyParlay `569d8e0`, gated: 1457 pytest + replay byte-identical):** the engine can
turn an NFL projection + line into a win prob. `PROP_MARKETS["NFL"]` + `MARKET_TO_STAT`
(distinct labels `PASS_YDS`/`RUSH_YDS`/`REC_YDS` solved the single-`YARDS` problem);
`SIGMA[*_YDS]=0.36/0.62/0.72`; TD stats Poisson with the λ as proj (anytime→`TDS`, pass→`PASS_TDS`);
the **POISSON_CUTOFF hardening** (POISSON_STATS Poisson at every line).

**Deferred to preseason (needs live odds to validate):** the *data half* — an EdgeModel NFL
projections **CSV export** + a **`parse_csv` NFL branch** in `odds_io.py` (runtime projections
load from CSV, not the DB) + name-matching + an NFL Odds-API feed. Contract: ANYTIME_TD/PASS_TDS
proj = the lambda (rush+rec / passing); yardage proj = `proj_*_yds`.

---

## Remaining work
1. **A2 data half** (above) — preseason, needs live odds.
2. **Game-line rework** — opponent-adjust EPA + regression-to-mean + market-anchor + pace/weather.
   Research; gated (tail-predictiveness must flip *and* CLV ≥ 0, else stays shadow) — **may not
   succeed**. Serves the later (~Week 14) game-line go-live.
3. **QB rushing-TD scramble term** — mobile QBs slightly under-projected on scramble TDs (small add).
4. **NFL go-live infra** — phase/Platt state + gate-check (spec Part 4), or ride JonnyParlay's
   ad-hoc gates as MLB/WNBA did. Decide before Week 1.

## Reference — data sources & constants
- **Feeds:** `nflreadpy` — `load_schedules` / `load_player_stats` / `load_team_stats` (in
  `nfl_stats_fetcher.py`) + `load_pbp` (in `nfl_pbp_fetcher.py`). Weather feed + indoor list
  (`roof` already in `nfl_games`) only needed for the game-line rework.
- **Constants:** yardage CV 0.36/0.62/0.72; `LEAGUE_INSIDE10_CONV=0.305`,
  `LEAGUE_RZ_REC_RATE=0.315`, passing `LEAGUE_RZ_TD_RATE=0.41`; game-line σ_total=13.0,
  σ_spread=13.45, σ_team=9.5, total dispersion shrink 0.67; key numbers {3:0.1193, 7:0.1256}.
