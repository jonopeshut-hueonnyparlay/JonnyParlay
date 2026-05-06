# H2 — Playoff Minutes Scalar Refit

**Analysis date**: 2026-05-06
**Sample**: 3925 playoff player-games (min ≥ 5) across 2023-24, 2024-25, 2025-26
**Method**: For each playoff player-game, recompute baseline minutes via
`project_minutes()` (EWMA + rest + blowout, pre-PLAYOFF_MINUTES_SCALAR), then
fit scalar = `mean(actual_min) / mean(baseline_min)` per cell.
**Data**: `data/diagnostics/playoff_baseline_data.csv`

## Headline finding

Current `rotation` (0.550) and `spot` (0.350) scalars are **massively
over-deflating** bench projections. Empirical reality across 3 playoff seasons:

| Role | n | mean(actual) | mean(baseline) | **fitted scalar** | current | Δ |
|------|--:|-:|-:|-:|-:|-:|
| starter   | 1969 | 34.42 | 32.02 | **1.075** | 1.068 | +0.007 |
| sixth_man |  861 | 21.24 | 22.13 | **0.960** | 0.909 | +0.051 |
| rotation  |  986 | 14.60 | 15.81 | **0.924** | 0.550 | **+0.374** |
| spot      |  109 | 10.00 | 10.55 | **0.948** | 0.350 | **+0.598** |

`cold_start` excluded from the fit (filtered out — sub-type caps in
`project_player()` already constrain those players).

## Why the original scalars were wrong

The original calibration came from 535 matched pairs across Apr 18-29 2026 (12
days, all early-round 2025-26 playoffs). With that sample size and that narrow
a window, the rotation and spot scalars happened to land at extreme values.
Across the broader 3-season sample (n=3925), bench-tier players play 92-95%
of their EWMA baseline — close to starter behavior, not the 55%/35% the
old values implied.

**Mechanistic interpretation**: rotation tightening in playoffs reduces the
NUMBER of bench players who play meaningful minutes, but the ones who DO play
get nearly their normal allocation. Old scalars assumed both fewer players AND
fewer minutes per player; reality is mostly the former.

## Per-season stability

| Season | Role | n | fitted scalar |
|--------|------|--:|---:|
| 2023-24 | starter   | 756 | 1.084 |
| 2023-24 | sixth_man | 277 | 0.983 |
| 2023-24 | rotation  | 379 | 0.942 |
| 2023-24 | spot      |  55 | 0.932 |
| 2024-25 | starter   | 791 | 1.054 |
| 2024-25 | sixth_man | 357 | 0.927 |
| 2024-25 | rotation  | 381 | 0.931 |
| 2024-25 | spot      |  41 | 0.968 |
| 2025-26 | starter   | 422 | 1.101 |
| 2025-26 | sixth_man | 227 | 0.983 |
| 2025-26 | rotation  | 226 | 0.883 |
| 2025-26 | spot      |  13 | 0.949 |

Per-season values are tightly clustered:
- starter: 1.054-1.101 (range 0.047)
- sixth_man: 0.927-0.983 (range 0.056)
- rotation: 0.883-0.942 (range 0.059)
- spot: 0.932-0.968 (range 0.036)

No season-of-data is an outlier. Pooled scalars are safe.

## Round split (early R1+R2 vs deep CF+Finals)

| Round | Role | n | fitted scalar |
|-------|------|--:|---:|
| early | starter   | 1674 | 1.084 |
| early | sixth_man |  752 | 0.957 |
| early | rotation  |  818 | 0.912 |
| early | spot      |   71 | 0.926 |
| deep  | starter   |  295 | 1.025 |
| deep  | sixth_man |  109 | 0.981 |
| deep  | rotation  |  168 | 0.986 |
| deep  | spot      |   38 | 0.990 |

Round buckets: `early` = days 0-29 within each season's playoff window
(R1 + R2). `deep` = days 30+ (CF + Finals).

Deep-round patterns:
- **Starter scalar drops** 1.084 -> 1.025 (-5.4%) — elite-player rest management
  in deep series (less back-to-back blowout games).
- **Rotation scalar rises** 0.912 -> 0.986 (+8.1%) — rotation tightening; coach
  trusts the rotation guys MORE in must-win deep games.
- **Sixth_man and spot** essentially unchanged across rounds.

The starter / rotation flip is consistent and meaningful (~5-8% in opposite
directions). Could justify round-stratified scalars in v2; for v1, pooled
scalars are accurate enough and simpler.

## Recommendation

**v1 — replace pooled scalars** (apply now):

```python
PLAYOFF_MINUTES_SCALAR = {
    "starter":    1.075,   # was 1.068 — essentially unchanged (+0.007)
    "sixth_man":  0.960,   # was 0.909 — modest increase (+0.051)
    "rotation":   0.924,   # was 0.550 — major correction (+0.374)
    "spot":       0.948,   # was 0.350 — major correction (+0.598)
    "cold_start": 0.400,   # unchanged — no data in this fit; sub-type caps handle
}
```

**v2 — round-stratified scalars** (defer; revisit when 2025-26 deep-round
sample grows):

```python
PLAYOFF_MINUTES_SCALAR_EARLY = {
    "starter": 1.084, "sixth_man": 0.957, "rotation": 0.912, "spot": 0.926,
}
PLAYOFF_MINUTES_SCALAR_DEEP = {
    "starter": 1.025, "sixth_man": 0.981, "rotation": 0.986, "spot": 0.990,
}
```

Round inference: derive from days-since-playoff-start (>= 30 = deep). Or use
NBA API series metadata for precision.

## Acceptance criteria for v1 deployment

1. Re-run May 5 diagnostic with new scalars. **OKC `pre_constraint` should rise
   from 190.93 to 215-235** (still below 240 because OKC has thin rotation,
   but no longer dramatically under-projecting).
2. **LAL `pre_constraint` should rise from 259.75 to ~270-285**, with bench_scale
   dropping into the 0.6-0.75 range as the constraint absorbs more bench
   minutes. (More bench = more constraint pressure, but stars still protected.)
3. Test suite 905/905.
4. RS regression test: 30-date 2025-26 RS backtest unchanged (PLAYOFF scalar is
   skipped for RS games).

## Open questions / follow-ups

- **Cold_start in playoffs**: this analysis filtered out cold_start players
  (small sample, sub-type caps already constrain). Could re-fit `cold_start`
  scalar separately on a future pass — current 0.400 was derived from FIX-P2
  empirical work and may still be appropriate.
- **Round split implementation**: requires a `is_deep_round(game_date)` function
  in `project_player()`. Defer until 2025-26 has more deep-round games.
- **Spread x scalar interaction**: blowout sigmoid already handles this in
  `project_minutes()`. Confirm scalar fits don't double-count the blowout
  effect. (Spot-checked OK: scalars derived from baseline projections that
  already include blowout sigmoid.)
- **Why was the old fit so far off?** 535-pair sample on 12 days of one
  playoff round produced edge-case ratios that didn't generalize. Lesson: scalar
  refits need cross-season data with cell sizes >= 100.
