# Staking & Unit-Cap Math (audit S4h-X)

Canonical reference for how a qualified pick becomes a staked unit size, and the cap
stack that bounds a day's exposure. Companion to `docs/research/MARKET_FOUNDATIONS.md`
(market pricing / BM shrinkage). **All values below are verified-OK and frozen — see
"Do not tune" at the end.**

Bankroll convention: **100u** (1u = 1% bankroll). `kelly_units` (`engine/sizing_core.py`)
computes the Kelly fraction `f* = (b·p − q)/b`, then **`units = f* × KELLY_FRACTION`** with
`KELLY_FRACTION = 6.0` (`engine/thresholds.py`). The realized stake fraction is therefore
`f*×6/100 ≈ 1/16.7` of full Kelly — conservative-safe. This is **not** "1/6 Kelly" (the old
label was wrong, the value is correct — Plan 6 §4; calibrated 2026-06-01 on 207 picks).

## 1. Per-pick sizing (`engine/sizing.py`)

`size_picks_base()` (Full Card) and `size_bonus_pick()` (standalone bonus) both run the
same pipeline:

1. `base = kelly_units(win_prob, odds)` — Kelly fraction `f*` scaled to units (`f* × 6`);
   returns `0.0` when there is no edge so the caller's floor logic fires.
2. `base *= get_market_mult(sport, stat, direction)` — per-market multiplier (the
   per-tier multiplier was retired 2026-06-06, Plan 9 §9F; BM shrinkage now lives on
   `win_prob` upstream). Bonus additionally applies the VAKE **variance** multiplier
   `VAKE_MULT["variance"][tier]` (default 0.85).
3. `round_units(...)`, then bound:
   - **Floor 0.25u** (uniform, Plan 9 §9K — was 0.50u non-T3, which over-staked the
     weakest admitted picks 2–2.5× vs Kelly).
     - Base card: `max(size, 0.25)` (clamp up to floor).
     - Bonus: **drop, don't clamp** — returns `None` when the math rounds below the
       floor (audit H-9; clamping there hid upstream edge miscalculations).
   - **Per-pick cap 1.25u** (`min(size, 1.25)`).
   - **High-variance cap 0.75u** when `win_prob < 0.50` (`min(size, 0.75)`).

## 2. Daily cap stack (`engine/rules.py::apply_caps`)

Picks are sorted **by `pick_score` descending** (best picks get cap priority — H4 fix),
then each pick is admitted only if it clears every cap (`continue`/skip otherwise):

| Cap | Limit | Notes |
|-----|-------|-------|
| `STAT_CAP` | **2 per stat** | `SOG = 6` |
| `max_per_game` | **2** (default) | R7 override — thin-slate nights can raise it |
| `SPORT_UNIT_CAP` | **NBA 8, MLB 8, NHL 5, NFL 5, WNBA 4** (units) | per-sport exposure |
| daily total | **12.0u** | **cross-run** — seeded with `units_already_bet` from earlier runs today |
| G12 | **2 same-direction pitcher props per game** | `PITCHER_STATS` |
| G_HRR_TEAM | **1 HRR per team per game** | within-lineup correlation r≈0.25–0.35 |

`BONUS_DAILY_CAP = 5` (`thresholds.py`) bounds bonus posts per calendar day.

KILLSHOT picks are sized after `apply_caps`, so `run_picks.py` (§5.6, ~line 1312)
re-checks the `SPORT_UNIT_CAP` and 12u daily total against the KILLSHOT sizes and drops
any that would breach them.

## 3. Code map

| Concern | Location |
|---|---|
| Kelly stake, floor/cap, variance cap | `engine/sizing.py` (`size_picks_base`, `size_bonus_pick`) |
| Daily cap stack | `engine/rules.py::apply_caps` |
| KILLSHOT post-sizing cap re-check | `engine/run_picks.py` §5.6 |
| Constants | `engine/thresholds.py` (`KELLY_FRACTION`, `BONUS_DAILY_CAP`) |

## 4. Do not tune

Per the audit anti-patterns: **do not change `KELLY_FRACTION`, the per-sport caps, or
the 12u daily cap** as part of any fix — sizing math is verified-OK and 1/16.7 Kelly is
conservative-safe; touching it during a correctness pass conflates concerns. Cross-tier
BM-weight ↔ edge-floor changes are deferred to the n≥150 per-family bootstrap refit
(`scripts/refit_bm.py`, Research item 8), not hand-tuning.
