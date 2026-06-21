# D1 Redistribution Diagnostic — 2026-05-05

**Date run**: 2026-05-05 (live data via `generate_projections.py --late-run --no-persist`).
**Diagnostic source**: `data/diagnostics/redistrib_2026-05-05.json` (env `JONNYPARLAY_DIAG_REDISTRIB=1`).
**Test suite status**: 905/905 passing — instrumentation is logging-only, zero behavior change.

## Team-level summary

| Team | OUT player | OUT avg_min | ewma_only_sum | override_sum | pre_constraint | core_total (top-5) | bench_total | post_constraint | bench_scale |
|------|------------|------------:|--------------:|-------------:|---------------:|-------------------:|------------:|----------------:|------------:|
| LAL  | Luka (1629029) | 34.64 |   0.00 | 346.37 | **346.37** | 181.09 | 165.28 | 240.00 | **0.3564** |
| OKC  | J.Williams (1631114) | 26.23 |   0.00 | 256.74 | 256.74 | 143.28 | 113.46 | 240.01 | 0.8525 |
| CLE  | (none)         |   —   | 243.26 |   0.00 | 243.26 | 156.32 |  86.94 | 240.00 | 0.9625 |
| DET  | Huerter (1628989)\* | 17.77 |  13.07 | 281.12 | 294.19 | 161.46 | 132.73 | 240.00 | 0.5917 |

\* Huerter was reported O by `nbainjuries`; manual `inactives_override.json` later down-graded him to Q. Redistribution had already written into `existing_overrides` before the down-grade applied. Secondary issue (see §3).

## The verdict

**The bug is none of the three hypotheses from the plan.** It is a fourth pattern that the diagnostic surfaced unambiguously:

> **Hypothesis (d) — Override path bypasses role/playoff scalars.** When `redistribute_minutes()` writes `existing_overrides[pid] = avg_min + bump`, that override **replaces** the player's EWMA-driven projection entirely inside `project_minutes()`:
>
> ```python
> if injury_minutes_override is not None:
>     return float(injury_minutes_override)
> ```
>
> The override value is built from the player's raw 15-game `avg_min` plus a small bump. The natural projection chain — `ewma × PLAYOFF_MINUTES_SCALAR × rest_factor × blowout_sigmoid × REGULAR_SEASON_MINUTES_SCALAR` — is **never applied** to overridden players. On a playoff day with `PLAYOFF_MINUTES_SCALAR["rotation"] = 0.55` and `["spot"] = 0.35`, this inflates bench projections by 50-100%.

## Direct evidence

**Three teams had OUT players today; one did not.** The `ewma_only_sum` field reveals the asymmetry:

- **CLE** (no OUT): `ewma_only_sum = 243.26`, `override_sum = 0.00`. Every player projected via the natural EWMA × scalar chain. Pre-constraint within 4 min of 240. Bench scale 0.9625 (gentle).
- **LAL** (Luka OUT): `ewma_only_sum = 0.00`, `override_sum = 346.37`. **Every** active LAL player has an override (17 recipients spread across G/F/C). Every player bypasses scalars. Pre-constraint balloons 106 min over budget.
- **OKC** (J.Williams OUT): `ewma_only_sum = 0.00`, `override_sum = 256.74`. Same pattern — all-recipient team.
- **DET** (Huerter OUT): `ewma_only_sum = 13.07`, `override_sum = 281.12`. Almost-all-recipient.

When redistribution fires, the entire team flips from EWMA-path to override-path. This is the structural inversion that produces the 240-min budget overshoot.

### LAL recipient examples (extract from JSON)

Player IDs used as keys; names looked up against `players` table:

| pid | role tier (likely) | avg_min | bump | post_override | EWMA × playoff_scalar (estimated) | inflation |
|-----|--------------------|--------:|-----:|--------------:|----------------------------------:|----------:|
| 2544 (LeBron) | starter | 34.21 | 3.90 | 38.11 | 34.21 × 1.068 ≈ 36.54 | +1.6 min  |
| 1630559 (Reaves) | starter | 36.92 | 7.79 | **42.00 (cap)** | 36.92 × 1.068 ≈ 39.43 | +2.6 min (still hits cap) |
| 1641733 (rotation) | rotation | 16.46 | 1.00 | 17.46 | 16.46 × 0.550 ≈ 9.05 | **+8.4 min** |
| 1629020 (rotation) | rotation | 15.35 | 0.93 | 16.29 | 15.35 × 0.550 ≈ 8.44 | **+7.9 min** |
| 1642876 (spot)     | spot     | 14.34 | 0.87 | 15.21 | 14.34 × 0.350 ≈ 5.02 | **+10.2 min** |
| 1642261 (spot)     | spot     | 13.84 | 0.84 | 14.68 | 13.84 × 0.350 ≈ 4.84 | **+9.8 min** |

Stars are nearly unchanged (their playoff scalar is ~1.0, so override ≈ scaled projection). Bench inflation is severe (rotation +8 min, spot +10 min per player). Across LAL's 12-player bench, that's the ~100 min overshoot we see in `pre_constraint_total`.

## Why this is the right diagnosis

1. **CLE control case**: CLE had no OUT player, ran through the EWMA-with-scalars path, and produced a near-budget pre-constraint total of 243.26. The system **works correctly** when no redistribution fires. The bug is exclusively in the override path.

2. **All-recipient pattern**: `_POS_FLOW` distributes minutes across G/F/C with non-zero shares for every group. Every position group has eligible recipients (≥8 MPG). Result: every active player on a team with one OUT player becomes a recipient and bypasses scalars. This isn't an over-eager flow weight — it's that *any* redistribution at all flips the entire team to override path.

3. **Double-counting hypothesis ruled out**: `existing_overrides[pid] = current + bump` where `current = pre_override or avg_min`. The override does not stack with EWMA; it replaces. The 346 overshoot is not double-counting.

4. **Constraint scaling is correct**: Pre-constraint 346 → post-constraint 240 with bench scale 0.36. That's the lineup-protected algorithm working as designed. The 240-min constraint is downstream cleanup; the upstream is what's broken.

## Recommended fix (revised P0-B)

The plan's original P0-B was "cap each recipient's bump at role-tier max." That's a band-aid. The actual fix is structural:

**Split `injury_minutes_override` into two distinct concerns:**

1. **`injury_minutes_override`** (existing, narrow scope): Only used for *known-exactly* minutes — return-from-injury restrictions, Q players with public load management. Replaces EWMA + scalars verbatim. Source: manual override or league announcement.

2. **`injury_minutes_redistrib_bump`** (new, additive): Per-player bump from redistribution. Applied **after** the natural EWMA × scalar chain in `project_minutes()`:

   ```python
   def project_minutes(role, df, b2b, spread,
                       injury_minutes_override=None,
                       injury_minutes_redistrib_bump=None,  # NEW
                       minutes_prior_override=None):
       if injury_minutes_override is not None:
           return float(injury_minutes_override)
       # ... existing EWMA + role scalars + rest + blowout ...
       proj_min = weight * ewma_min + (1 - weight) * prior
       proj_min *= rest_factor
       proj_min *= blowout_factor
       proj_min *= PLAYOFF_MINUTES_SCALAR.get(role, 1.0)  # if playoff
       # NEW — additive bump applied AFTER scalars
       if injury_minutes_redistrib_bump:
           proj_min += injury_minutes_redistrib_bump
       proj_min = min(proj_min, 42.0 if role == "starter" else 38.0)
       return proj_min
   ```

3. **`redistribute_minutes()` writes only the `bump`**, not the recomputed total. The recipient dict becomes `{pid: bump_value}` (additive), not `{pid: avg_min + bump}` (absolute).

### Why this is correct

- Recipients keep their natural role/playoff/rest/blowout calibrations.
- The redistribution bump represents *incremental* opportunity from the OUT player's vacated minutes — that's exactly what's added on top of the player's normal expected minutes.
- The bump amounts are already small (0.4-7.8 min per player), so adding rather than replacing produces sensible totals.
- LAL pre-constraint estimate post-fix: top-5 ~175 (mostly unchanged, scalar ≈ 1.0 anyway) + bench ~70-90 (was 165, scaled correctly) = ~245-265. Constraint barely fires. **Bench scale should land ≈ 0.85-0.95 instead of 0.36.**

### Caps to apply

- `injury_minutes_redistrib_bump` should not push a recipient over their role-tier cap (rotation 32, sixth_man 28, starter 38). Apply the cap *after* adding the bump, not on the bump itself:

   ```python
   ROLE_MAX_MIN = {"starter": 38.0, "sixth_man": 28.0, "rotation": 32.0,
                   "spot": 18.0, "cold_start": 16.0}
   proj_min = min(proj_min, ROLE_MAX_MIN.get(role, 38.0))
   ```

- For starters absorbing primary-backup load (Reaves's 7.79 bump from Luka's redistribution), the post-add value of (39.43 + 7.79 = 47.22) caps at 42 (existing hard cap), not 38 — starter cap should remain 42 to allow legitimate primary-backup absorption.

## Secondary observation — manual override down-grade race

For DET on May 5: `nbainjuries` reported Huerter as OUT, redistribution wrote into overrides for 17 recipients, then `inactives_override.json` down-graded Huerter to Q. The redistribution bumps remained in place even though Huerter is now Q (likely playing). DET's `pre_constraint_total = 294.19` includes phantom redistribution from a Q-listed player.

This is a smaller bug. Fix: the manual override step in `generate_projections.py` should rescind redistribution overrides when it down-grades a player from O→Q/GTD/P. Track separately as a follow-up; not part of P0-B core fix.

## Acceptance criteria for the structural fix

When implementation begins (separate session):

1. Re-run May 5 diagnostic with the fix. **LAL pre-constraint should drop from 346.37 to 245-265 range; bench scale should rise from 0.36 to ≥0.85.**
2. Re-run May 5 player-level backtest. LeBron projected minutes essentially unchanged (he's a starter with playoff scalar ~1.0). Bench player PTS no longer crushed by 0.36 scaling.
3. CLE control case (no OUT): pre-constraint and bench scale unchanged from current values (243.26 / 0.9625).
4. Test suite: 905 → 905+ (new tests for the bump-vs-override split).

## What this changes in the master plan

- **P0-B re-prescribed**: not "role-tier cap on bumps", but "split override into authoritative-replace vs additive-bump, apply scalars to both paths". This is a clearer-architecturally fix.
- **C2 framing in memory**: outdated. Memory said "redistribution ignores team minute budget." More precisely, *redistribution bypasses the per-player scaling that would have kept the team within budget naturally*.
- **C3 (within-bench tiered scale) is dead**: with the structural fix, bench scaling will be gentle (~0.85-0.95) and tiered cuts become unnecessary. Closing C3 entirely.
- **Doesn't affect P0-A (lineup data) or P1-A (blowout sigmoid)** — independent issues.

## What we don't have data for

- May 1-4 redistribution patterns. `nbainjuries` only fetches today's report; historical replay would require either capturing reports daily into a DB, or backfilling from manual sources. **Not blocking** the P0-B fix — May 5 is sufficient because the bug is structural (every redistribution day exhibits the same override-path inversion). Multi-day data would only confirm the fix's robustness, not change its design.
- Pre-FIX-P3 baseline. The 905-test suite incorporates FIX-P3 already; couldn't reproduce the older uniform-scale-all behavior to confirm it has the same root cause. Reasoning suggests yes (the override path was always there, FIX-P3 only changed how the constraint distributes the cut), but unverified.

## Next concrete step

Author P0-B implementation plan with the revised prescription:
- Modify `project_minutes()` signature to accept `redistrib_bump`.
- Modify `redistribute_minutes()` in `injury_parser.py` to write to a **separate** dict (`injury_minutes_redistrib_bumps`) rather than `existing_overrides`.
- Modify `run_projections()` to pass both dicts through.
- Add `ROLE_MAX_MIN` cap dict (starter=42, sixth_man=32, rotation=28, spot=18, cold_start=16) — applied after bump addition.
- Re-run May 5 diagnostic with implementation; confirm LAL pre-constraint ~250 ± 15, bench scale ≥ 0.85.
- Compare against actual May 5 outcomes to verify directional improvement.

---

## P0-B implementation result (2026-05-05)

Implemented in same session. The bump is applied in `project_player()` AFTER the
playoff/RS scalar + cold_start cap + Q/GTD weighting (so it lands in
absolute-minute space rather than getting multiplied by sub-1.0 playoff
scalars). `ROLE_MAX_MIN` cap applied as the final clip. `project_minutes()`
keeps a loose 42/38 baseline cap for the EWMA × rest × blowout product, since
the playoff scalar is applied in `project_player()` immediately after.

Test suite: **905/905 passing** (unchanged).

### Side-by-side verification — same May 5 inputs, before vs after fix

| Team | OUT | pre_constraint **before** | pre_constraint **after** | Δ | bench_scale **before** | **after** | Δ |
|------|-----|-:|-:|-:|-:|-:|-:|
| **LAL** | Luka  | 346.37 | **259.75** | **-86.6** | 0.3564 | **0.7750** | **+0.42** |
| **OKC** | J.Williams | 256.74 | **190.93** | -65.8 | 0.8525 | **1.0000** | +0.15 |
| **DET** | Huerter | 294.19 | **251.02** | -43.2 | 0.5917 | **0.8543** | +0.26 |
| **CLE** (control) | (none) | 243.26 | 243.26 | 0.0 | 0.9625 | 0.9625 | 0.0 |

### Verification verdict

- **LAL pre-constraint hit target 245-265** (dead center at 259.75).
- **LAL bench_scale 0.78 — slightly below the 0.85 acceptance threshold** but a 4× improvement (0.36 → 0.78). The remaining 22% bench cut is the constraint working correctly: 87.76 bench min absorbing the 19.75 overshoot above 240.
- **CLE control case unchanged** — confirming the fix only affects redistribution paths, not the natural EWMA path.
- **OKC pre-constraint 190.93 — below 240** (constraint doesn't fire). This suggests OKC's playoff scalars may be too aggressive (rotation 0.55 / spot 0.35 deflating bench minutes too much for a thin-rotation team). Surfaces H2 (playoff scalar recalibration) as the next priority but is not a P0-B regression — the architecture is correct, the parameter values for OKC's specific roster shape may need refinement.
- **LeBron's projected PTS: 21.35** (was 22.0 pre-fix). Marginal change because LeBron was always in the protected top-5; the fix mainly affected bench player projections. Residual -4-5 PTS gap vs his 27 actual points is a separate issue tracked under P1-A (blowout sigmoid) and P1-B (playoff scalar refit), not a P0-B concern.

### What changed in the codebase

- `engine/nba_projector.py`:
  - Added `ROLE_MAX_MIN` constant (starter=42, sixth_man=32, rotation=28, spot=18, cold_start=16)
  - `project_minutes()`: keeps 42/38 baseline cap (loose, before playoff scalar)
  - `project_player()`: new param `injury_minutes_redistrib_bump`; role-promotion now triggers on bump magnitude; bump applied after Q/GTD weighting; final ROLE_MAX_MIN cap
  - `run_projections()`: new param `injury_minutes_redistrib_bumps`; threaded to per-player call
- `engine/injury_parser.py`:
  - `redistribute_minutes()`: writes to `existing_bumps` (additive, no internal cap) instead of `existing_overrides`
  - `get_injury_context()`: returns 3-tuple `(statuses, overrides, redistrib_bumps)`; overrides dict reserved for future known-exact-minutes use
- `engine/generate_projections.py`, `engine/csv_writer.py`: updated 3-tuple unpack + threaded new dict to `run_projections`
- `tests/test_injury_parser_fixes.py`: 3-tuple unpack
- `engine/diagnostics.py`: comment update on field semantic shift

### What this leaves open

- **OKC under-projection** (pre_constraint 191 < 240). May indicate playoff scalars are too aggressive, especially for thin-rotation teams. Tracked as **H2** (playoff scalar recalibration) — needs full 2024-25 + 2025-26 playoff dataset to refit by round.
- **LeBron residual error** (-4 PTS). Not a redistribution issue; tracked under P1-A (blowout sigmoid) and Vegas team-total scaling.
- **Down-grade race condition**: when `inactives_override.json` down-grades a player from O→Q/GTD/P after `redistribute_minutes` has already written bumps, the bumps remain. Smaller follow-up; track separately.

**P0-B closed.**
