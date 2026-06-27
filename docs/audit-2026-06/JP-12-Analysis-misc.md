# AUDIT 2026-06 — JP-12 Analysis/misc (JonnyParlay)

Files audited (4 read): analyze_picks.py, save_context.py, analyze_blend.py, analyze_picks.py

**Findings (final, excl. refuted): C=0 H=0 M=0 I=3** | constants extracted: 9 | not-done: 2

## Findings

| ID | File:line | Sev | Status | Cat | Known | Title |
|----|-----------|-----|--------|-----|-------|-------|
| JP12-02 | analyze_blend.py:16 | I | refuted | code |  | BLEND_ALPHA hardcoded local copy (0.25) not imported from thresholds.py; stale provenance comment |
| JP12-03 | analyze_blend.py:28 | I | refuted | code |  | analyze_blend reads pick_log.csv with a bare open(), bypassing the shared FileLock and paths.py resolution |
| JP12-04 | analyze_picks.py:116 | I | confirmed | statistical |  | Calibration display dilutes predicted WP by averaging over picks with win_prob==0 |
| JP12-05 | analyze_picks.py:216 | I | unverified | code |  | streak_analysis prints 'Current: 0None' when the set is all pushes |
| JP12-06 | analyze_picks.py:100 | I | unverified | code |  | American-odds payout math and ROI denominator are correct |
| JP12-01 | save_context.py:57 | I | refuted | code |  | _merge() silently discards every prior-day verdict on each write |

## Confirmed-correct / coverage notes

- C:/Dev/JonnyParlay/analyze_picks.py is a correct 5-line shim that re-execs engine/analyze_picks.py via runpy with run_name='__main__'; no logic of its own.
- analyze_picks.py load_picks delegates to pick_log_io.load_rows with graded_only=True and routes every read through the shared FileLock (audit H-8). The keyword args used (sports, since, stats, exclude_run_types, graded_only) all exist in the load_rows signature (pick_log_io.py:234) — no interface drift.
- American-odds payout, ROI (risked excludes P/VOID), and top/worst-10 profit math in calc_metrics/main are arithmetically correct and guard odds==0 against division.
- analyze_blend.py disagreement reconstruction abs((blended-line)/BLEND_ALPHA) is mathematically consistent with the live blend proj=line+BLEND_ALPHA*(raw-line) (evaluators.py:269), so raw_disagreement = |raw-line| is recovered correctly.
- analyze_blend.py monotonic + n>=50 quintile gate logic is internally consistent and labelled advisory; no production code change is triggered.
- save_context.py input validation (VALID_VERDICTS, REQUIRED_FACTORS, per-factor value check) is thorough, fence-stripping is robust, and the write uses a tmp + atomic replace pattern (L163-165) — safe against partial writes.
- These are all offline/manual analysis and research-capture tools; none sit in the daily projection/pricing/sizing path, so no Critical live-money exposure was found. BLEND_ALPHA=0.25 is the only constant here that mirrors a live sizing/pricing literal, and the live source (thresholds.py:95) is unchanged at 0.25.

## Not-Done / incomplete (this module)

| Kind | File | Detail |
|------|------|--------|
| deferred | analyze_blend.py | Standalone advisory: explicitly a no-code-change gate ('re-evaluate at n=100 graded game-line CLV rows'). BLEND_ALPHA sport-specific split is proposed in docstr |
| dead-code | analyze_blend.py | Module runs all logic at import time with no `if __name__=='__main__'` guard; importing it executes the analysis and may sys.exit(0). Intended as a script but u |
