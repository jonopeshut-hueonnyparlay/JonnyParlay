# AUDIT 2026-06 — JP-11 engine/tools (JonnyParlay)

Files audited (9 read): __init__.py, _check_dvp.py, analyze_playoff_scalars.py, calibration_dashboard.py, diag_blowout_buckets.py, diag_h1_constraint_chain.py, diag_h6_backtest.py, diag_h6_pool.py, export_pick_log_xlsx.py

**Findings (final, excl. refuted): C=0 H=0 M=0 I=4** | constants extracted: 20 | not-done: 8

## Findings

| ID | File:line | Sev | Status | Cat | Known | Title |
|----|-----------|-----|--------|-----|-------|-------|
| JP11-4 | analyze_playoff_scalars.py:183 | I | refuted | code |  | analyze_playoff_scalars crashes with IndexError if every candidate row is skipped (empty out_rows) |
| JP11-5 | calibration_dashboard.py:69 | I | unverified | statistical |  | Reliability significance uses predicted-prob Wald SE — acceptable advisory choice |
| JP11-2 | diag_blowout_buckets.py:136 | I | refuted | statistical |  | diag_blowout prints STALE 'current model' constants (0.200 / 12.0 / 0.40) vs live EdgeModel values (0.19 / 20.0 / 0.15) |
| JP11-3 | diag_blowout_buckets.py:73 | I | refuted | statistical |  | Blowout sigmoid fit is equal-weighted across buckets and uses REALIZED final margin, while production reduction keys on pre-game \ |
| JP11-7 | diag_h1_constraint_chain.py:81 | I | unverified | code |  | diag_h1 driver is safe-by-construction (persist=False) but re-invokes the full projection pipeline incl. Odds-API |
| JP11-1 | diag_h6_pool.py:20 | I | confirmed | completeness |  | 6/9 tools ImportError in this repo — they import EdgeModel-only modules (projections_db / nba_projector / generate_projections) ab |
| JP11-6 | export_pick_log_xlsx.py:80 | I | unverified | code |  | export_pick_log_xlsx odds/profit math is correct; read-only Excel export |

## Confirmed-correct / coverage notes

- `__init__.py` is a pure docstring describing the dir as manual CLI diagnostics not imported by production (verified: grep shows only `tests/test_calibration_dashboard.py` imports from `tools`). Correct/benign.
- `calibration_dashboard.py` RUNS in JonnyParlay (imports `paths`, `pick_log_io` — both present). Binning, predicted-prob Wald SE, and `n>=min_n AND |obs-pred|>2*SE` drift flag are statistically sound and explicitly advisory ('do not auto-tune'). Excludes parlays/longshot/daily_lay and ungraded rows correctly. Covered by a unit test.
- `export_pick_log_xlsx.py` RUNS here (only openpyxl + stdlib). `american_to_decimal` and `pick_profit` are arithmetically correct (W=size*(dec-1), L=-size, P/VOID/blank=0). ROI denominator correctly restricted to W/L stakes; CLV averaging guards numeric type; PermissionError falls back to a timestamped filename. Read-only on `pick_log.csv`.
- `diag_h1_constraint_chain.py` is safe-by-construction: calls `generate_projections.run(persist=False)`, so the projections DB is never mutated; per-date exceptions are caught so one failure doesn't abort the sweep. `_percentile` linear-interp and clip floor/ceiling (0.80/1.20) counters match `MATCHUP_CLIP` in nba_projector.
- `diag_h6_backtest.py` / `diag_h6_pool.py` correctly treat DNP as 0-min in recent-average computation (intended) and exclude DNP (min>=5) for season averages. `_check_dvp.py` is a trivial read-only SELECT.
- The hardcoded `0.80`/`1.20` (diag_h1) and `MATCHUP_CLIP=(0.80,1.20)` agree with live EdgeModel. The blowout `current model` print is the only constant mismatch found (stale).
- NONE of these tools are in the automated daily run (`generate_projections.py` / `--run-picks`); they are manual one-shot diagnostics, so even the ImportError breakage has no live-money pricing/sizing impact — it only means the broken tools fail when a human invokes them."

## Not-Done / incomplete (this module)

| Kind | File | Detail |
|------|------|--------|
| dead-code | _check_dvp.py | Imports projections_db (line 8), which does not exist in JonnyParlay/engine. ImportError on run; non-functional in this repo. |
| dead-code | analyze_playoff_scalars.py | Imports nba_projector and projections_db (lines 31-38), both EdgeModel-only. Cannot run from JonnyParlay root. |
| dead-code | diag_blowout_buckets.py | Imports projections_db (line 28); also prints stale pre-refit blowout constants (line 136). Non-functional here. |
| dead-code | diag_h1_constraint_chain.py | Imports generate_projections.run (line 84), EdgeModel-only. ImportError when the re-run path executes. |
| dead-code | diag_h6_backtest.py | Imports projections_db (line 21); EdgeModel-only. Non-functional here. |
| dead-code | diag_h6_pool.py | Imports projections_db (line 20); EdgeModel-only. Non-functional here. |
| partial-feature | diag_h6_backtest.py | Tests a PROPOSED pool filter (REC_THRESHOLD=5.0 / SEASON_THRESHOLD=25.0) — diagnostic for a filter decision, not wired to production; outcome (false-drop %) is  |
| deferred | analyze_playoff_scalars.py | Round bucketing is an explicitly-labelled 'lazy heuristic' (lines 48-50) using a 30-day offset because explicit playoff-round metadata is not available in the g |
