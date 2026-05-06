# Scalar freeze policy

Closes audit item E5 (2026-05-06).  Establishes which scalars in the NBA
projection chain are eligible for refit at any calibration session vs which
are frozen pending a gating dependency or a season-boundary trigger.

The aim is to prevent ad-hoc calibration drift between sessions: if a value
is on the **active** list, refit it when the data warrants; if it is on the
**frozen** list, do not touch it without first addressing the gate noted
below.

## Active list — eligible at any session if data warrants

These scalars are fitted from JonnyParlay's own backtest residuals.  Refit
when n_pairs hits the threshold below and the bias is large enough to
matter.

| Scalar | Source | Last refit |
|--------|--------|-----------|
| `REGULAR_SEASON_MINUTES_SCALAR` | `engine/nba_projector.py:271` | 2026-05-05 (post REB-prior + EWMA span 6→8) |
| `REGULAR_SEASON_STAT_SCALAR` | `engine/nba_projector.py:286` | 2026-05-05 (same session as RS minutes scalar) |
| `PLAYOFF_MINUTES_SCALAR` | `engine/nba_projector.py:245` | 2026-05-06 (H2 refit, 3925 matched pairs) |
| `_HOME_AWAY_DELTA` (6 stats) | `engine/nba_projector.py:317` | 2026-05-03 (Brief 7 R4) |
| `_REB_RATE_PRIOR_RS` / `_REB_RATE_PRIOR_PO` / `_REB_RATE_PRIOR_N` | `engine/nba_projector.py:356-358` | 2026-05-03 (Brief 7 R6) |
| `PLAYOFF_RATE_DEFLATORS` | `engine/nba_projector.py:302` | 2026-05-02 (P18-v4) |
| `DK_STD_FLOOR` | `engine/nba_projector.py:229` | 2026-05-03 (Brief 7 R2) |
| `PTS_BLEND_ALPHA` | `engine/nba_projector.py:331` | 2026-05-01 (bias-optimal vs MAE-flat curve) |
| Blowout sigmoid `K` / `MID` / `MAX` | `engine/nba_projector.py:184-186` | 2026-05-04 (P1-A empirical refit, 24,600 rows) |
| `EWMA_SPAN_MIN` | `engine/nba_projector.py:102` | 2026-05-04 (raised 6→8) |

## Frozen list — do not refit without addressing the gate

| Scalar | Source | Gate to clear before refit |
|--------|--------|----------------------------|
| `PLATT_A`, `PLATT_B` | `engine/run_picks.py:295-296` | H3 / Brief 7 R1.  Need ~300+ pick_log rows with `over_p_raw` populated (schema-v4 column added 2026-05-05).  A premature refit on stale double-calibrated data produced **−4.2 % OOS Brier** in Fix Pass 6; do not re-run until the column is filled. |
| `LEAGUE_AVG_PACE` | `engine/nba_projector.py:62` | Season boundary.  Value is 2025-26 STD (100.22).  Refit only when 2026-27 begins, not mid-season. |
| `LEAGUE_AVG_PACE_PO` | `engine/nba_projector.py:71` | Season boundary.  Same rule. |

## Refit thresholds

A refit fires only when **all three** thresholds are met:

1. **n_pairs**:
   - Stat scalars: ≥ 300 graded prop pairs (player × game × stat).
   - Minutes scalars: ≥ 500 player-game pairs.
2. **|bias|** ≥ 0.05 standard-units relative to the current scalar's basis.
3. **OOS validation** on a held-out season (e.g., refit on 2025-26, validate
   on 2024-25).  Reject the refit if OOS bias is worse than the in-sample
   improvement.

## Refit checklist

When a scalar is refitted, the calibration session must record in CLAUDE.md:

- Old value → new value (per-role for vector scalars).
- n_pairs used for the fit.
- In-sample bias (pre / post).
- OOS bias on held-out season.
- Commit hash of the refit.
- Test count delta (calibration tests before / after).

This mirrors the pattern used in the H2 / Brief 7 entries — see
`CLAUDE.md` "Audit 2026-05-06" and "Fix pass session 6" blocks.

## Removing a scalar from frozen

A frozen scalar can move to active when:

- `PLATT_A` / `PLATT_B`: unblocked when ≥ 300 pick_log rows carry
  `over_p_raw` (track via `SELECT COUNT(*) FROM ... WHERE over_p_raw != ''`).
  Update this doc and CLAUDE.md when promoting.
- `LEAGUE_AVG_PACE` / `LEAGUE_AVG_PACE_PO`: at the start of a new NBA
  season, recompute from `team_season_stats` and update both the constant
  and the comment provenance.

## Related docs

- `docs/audits/AUDIT_2026-05-06_projection_deep_dive.md` (audit that surfaced E5)
- `memory/projects/custom-projection-engine.md` (project lead, scalar history)
- `CLAUDE.md` Audit 2026-05-06 status block (refit history canonical record)
