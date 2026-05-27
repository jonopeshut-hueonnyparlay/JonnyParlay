# Support File Audit — 2026-05-27

Files audited:
1. `engine/sgp_builder.py` (1221 lines)
2. `engine/pick_log_schema.py` (532 lines)
3. `engine/secrets_config.py` (164 lines)
4. `engine/analyze_picks.py` (490 lines)
5. `engine/clv_report.py` (432 lines)
6. `engine/weekly_recap.py` (733 lines)
7. `engine/calibrate_distributions.py` (519 lines)
8. Root shims: `run_picks.py`, `grade_picks.py`, `sgp_builder.py`, `results_graphic.py`, `weekly_recap.py`, `analyze_picks.py`, `clv_report.py`, `capture_clv.py`

---

## 1. `engine/sgp_builder.py`

### Summary
Overall the SGP builder is well-structured. The copula math is solid, the `save` parameter gates `_log_sgp()` correctly, all 29 fields are written in `_log_sgp()`, `today_str` is threaded to all call sites, and `_parlay_american()` correctly handles both positive and negative odds via `_american_to_decimal`. No secrets are printed. However there are two meaningful bugs: (1) the CLI `__main__` block never passes `save=` so it silently defaults to `save=True` but also never supplies `--no-save`, meaning a dry-run from CLI can still log; (2) `post_sgp()` logs even when `today_str` is `None` — the guard `if save and today_str` protects against it, but `today_str` can only be `None` when called from a code path that doesn't pass it, which would silently skip logging without any warning; and (3) `_sgp_book()` in the embed uses a different algorithm than `_pick_best_book()` used during `build_sgp()` — the legs are locked to one book by `build_sgp` but `_sgp_book` re-derives the book from leg `book` fields, which should be identical since all legs are locked, but it's a fragility.

- **MEDIUM** `sgp_builder.py:1094` — **WHAT**: `_log_sgp()` is silently skipped when `today_str` is `None`. **WHY WRONG**: `post_sgp()` accepts `today_str=None` as a default; if a caller forgets to pass `today_str`, the SGP is posted to Discord but never written to pick_log — no warning is emitted. **FIX**: Add a `print("[SGP] WARNING: today_str is None — pick not logged")` in the `if save and today_str:` branch when `save=True` but `today_str` is falsy.

- **MEDIUM** `sgp_builder.py:1208-1220` — **WHAT**: CLI `__main__` block has no `--no-save` / `--save` flag and hardcodes `save=True` (the default). **WHY WRONG**: `--dry-run` prints `"--dry-run: skipping Discord post"` and skips posting, but since `dry_run=True` routes to `if dry_run: ... print ... continue` it never calls `post_sgp`, so logging is also skipped. However the misleading `reason = "--dry-run" if not save else "--no-discord"` string at line 1187 implies a `--no-discord` path that doesn't exist at the CLI level — there is no way to post to Discord *without* saving from the CLI. This is a documentation/logic mismatch rather than a functional bug, but it confuses the control flow. **FIX**: Either add `--no-save` flag, or simplify the reason string.

- **LOW** `sgp_builder.py:878-891` — **WHAT**: `_sgp_book()` (used in embed and `post_sgp`) uses a "preferred + modal count match" algorithm, while `_pick_best_book()` (used in `build_sgp`) uses strict preference order over the common-book intersection. **WHY WRONG**: After `build_sgp` locks all legs to one book via `_pick_best_book`, all legs have the same `book` field, so `_sgp_book` always returns that same book. But if any code path ever passes legs with mixed books (e.g. test mocks or future refactors), `_sgp_book` would diverge from what `build_sgp` chose. **FIX**: In `post_sgp` and `build_sgp_embed`, use the book already on the first leg or accept `book` as a parameter rather than re-deriving it.

- **LOW** `sgp_builder.py:40-41` — **WHAT**: `from secrets_config import require_odds_api_key, DISCORD_BONUS_WEBHOOK` imports `DISCORD_BONUS_WEBHOOK` at module level. **WHY WRONG**: Module-level import captures the value at import time (before the `.env` is loaded if the module is imported early). In practice `secrets_config.py` loads `.env` at its own module-load time, so by the time `sgp_builder.py` imports, it's correct. However `post_sgp` also does `from secrets_config import DISCORD_SGP_WEBHOOK` as a deferred import inside the function — inconsistent pattern. **FIX**: Minor inconsistency only; deferred import inside `post_sgp` is actually the more defensive pattern. Consider moving the module-level `DISCORD_BONUS_WEBHOOK` import into the function too, or add a comment explaining why it's safe at module level.

- **LOW** `sgp_builder.py:1038` — **WHAT**: `print(f"  [SGP] 📝 Logged to pick_log ({len(legs)} legs, +{parlay_odds})")` uses an emoji. **WHY WRONG**: Minor — `start_clv_daemon.bat` is ASCII-only (CLAUDE.md), but this is a Python print, not a .bat file. No real risk. Noted for consistency.

- **OPEN_QUESTION** `sgp_builder.py:56-57` — **WHAT**: `MIN_DISTINCT_PLAYERS = 3` with comment `# unused — diversity gate now enforces n_legs unique players`. **WHY WRONG**: The constant is still defined but never referenced; it's dead code. Not a bug, but a cleanup opportunity.

- **OPEN_QUESTION** `sgp_builder.py:946` — **WHAT**: `build_sgp_embed()` hardcodes `f"+{parlay_odds}"` but does not check whether `parlay_odds` could be negative (it shouldn't be given filtering, but the sign is prepended unconditionally). If the parlay odds filter ever fails, display would show `+-123`. Very unlikely given the odds range filter. Noted.

### TODO/FIXME/HACK
None found.

### Silent `except` blocks
- Line 381: `except Exception:` in `_copula_joint_prob` — falls back to independence product. Documented and intentional.
- Line 477: `except Exception: continue` in `fetch_nba_events` — skips unparseable event timestamps. Acceptable.
- Line 1041: `except Exception: pass` in `_log_sgp` — silently swallows sidecar write failures. Low risk.
- Line 1062: `except Exception: _guard = None` in `post_sgp` — discord_guard failure sets guard to None, so no dedup. Discord re-post possible on guard import failure.
- Line 1092: `except Exception: pass` in `post_sgp` — silently swallows guard-save failures. Discord re-post possible on next run.

---

## 2. `engine/pick_log_schema.py`

### Summary
Schema is solid. `SCHEMA_VERSION = 4`, `CANONICAL_HEADER` has exactly 29 fields in the correct order as per CLAUDE.md. The assert at lines 494-508 guards against duplicates and version column drift. Migration via `migrate_row()` fills missing columns with `""`. The atomic sidecar write is properly implemented with tmp+fsync+replace. One stale comment found.

- **LOW** `pick_log_schema.py:41` — **WHAT**: Comment reads `# Canonical schema (v3)` but `SCHEMA_VERSION = 4`. **WHY WRONG**: Stale comment — was not updated when v4 was added (the `over_p_raw` column). Misleading to anyone reading the file. **FIX**: Change comment to `# Canonical schema (v4)`.

- **LOW** `pick_log_schema.py:136-149` — **WHAT**: `migrate_row()` has `source_header` parameter reserved for future use (`_ = source_header`). **WHY WRONG**: Not a bug — the parameter is documented as reserved. However, `detect_schema_version()` is never called inside `migrate_row()`, which means callers that use `migrate_row()` never get per-column defaulting based on source version. In practice this is fine because all missing columns default to `""`, but it means truly version-aware migration (e.g. setting a non-blank default for a new column) would require callers to do it themselves. **FIX**: Document this explicitly or add a version dispatch path when it becomes needed.

- **OPEN_QUESTION** `pick_log_schema.py:378-413` — **WHAT**: `write_schema_sidecar()` raises on failure after attempting to unlink the `.tmp` file. **WHY WRONG**: Not a bug per se. But `_log_sgp` in `sgp_builder.py` calls `_write_schema_sidecar` (imported from `run_picks`) in a try/except that swallows the exception — so a sidecar write failure is always silenced. The sidecar is non-critical, so this is acceptable, but worth noting.

### TODO/FIXME/HACK
None found.

---

## 3. `engine/secrets_config.py`

### Summary
Clean and complete. Both `DISCORD_LONGSHOT_WEBHOOK` and `DISCORD_SGP_WEBHOOK` are exported. The `summary()` function properly redacts values to `<first8>...<last4>`. No secrets are printed. The `.env.example` reference in the docstring is accurate. One structural issue: the `_WEBHOOK_REGISTRY` captures values at module-load time (not lazily), so if the `.env` were to be reloaded mid-process (not a current pattern but possible in tests), the registry would hold stale values.

- **LOW** `secrets_config.py:121-132` — **WHAT**: `_WEBHOOK_REGISTRY` stores the webhook URL values (strings) captured at module import time via `(env_key, DISCORD_WEBHOOK_URL)`, etc. **WHY WRONG**: If `os.environ` is modified after import (e.g. in tests that set env vars), `require_webhook()` will return the old value, not the updated one. The module-level `DISCORD_*` variables have the same issue — they are all captured once at import. **FIX**: In `require_webhook()`, re-read from `os.getenv` at call time rather than from the registry snapshot. This is a test-environment concern primarily.

- **LOW** `secrets_config.py:104-105` — **WHAT**: `DISCORD_LONGSHOT_WEBHOOK` fallback behavior is documented in CLAUDE.md ("falls back to #bonus-drops") but this fallback is implemented in callers (e.g. `run_picks.py`), not here. **WHY WRONG**: Not a bug in `secrets_config.py` itself, but the module docstring does not list `DISCORD_LONGSHOT_WEBHOOK` or `DISCORD_SGP_WEBHOOK` in the template section (lines 18-27). **FIX**: Add both to the `.env.example` template in the docstring.

### TODO/FIXME/HACK
None found.

---

## 4. `engine/analyze_picks.py`

### Summary
ROI and win-rate calculations are correct: win rate excludes VOID from denominator (handled by `graded_only=True` in `pick_log_io.load_rows`, which should filter to W/L/P), and the `calc_metrics` function correctly excludes P/VOID from `risked`. American odds P&L formula is correct. Date parsing delegates to `load_rows` with `since` filter. The `--shadow` flag includes MLB + custom shadow logs. One significant issue: the `_PROP_STATS` set used for the stat×direction crosstab is incomplete — it is missing several SHADOW_STATS stats (`SV`, `GA`, `BB`, `PC`, `RBI`, `RUNS`, `NRFI`, `YRFI`, `NHLPTS`, `NHLBLK`, `GOALS`) and does not include the WNBA shadow log at all.

- **MEDIUM** `analyze_picks.py:415-416` — **WHAT**: `_PROP_STATS` set is missing several live/shadow stats: `SV` (NHL goalie saves), `GA` (NHL goals against), `BB` (walks), `PC` (pitch count), `RBI`, `RUNS`, `NRFI`, `YRFI`, `NHLPTS`, `NHLBLK`, `GOALS`. **WHY WRONG**: These stats will be silently excluded from the "BY STAT × DIRECTION (props only)" crosstab section. Any MLB/NHL picks with these stats won't appear in the direction-breakdown even if they're graded. Not a data-corruption bug but misleads the analysis. **FIX**: Add the full set of live stat labels: `SV`, `GA`, `BB`, `PC`, `RBI`, `RUNS`, `GOALS`, `NHLPTS`, `NHLBLK`, `NRFI`, `YRFI`.

- **MEDIUM** `analyze_picks.py:357-367` — **WHAT**: `--shadow` flag includes `pick_log_mlb.csv` and `pick_log_custom.csv` but NOT `pick_log_wnba.csv`. **WHY WRONG**: WNBA is in shadow/active log (`pick_log_wnba.csv` per CLAUDE.md). The shadow flag should logically include it, or at least the help text should clarify the exclusion. Users running `--shadow` for a full picture will miss WNBA data. **FIX**: Import `PICK_LOG_WNBA_PATH` from `paths.py` and include it in the `extra` list under `--shadow`.

- **LOW** `analyze_picks.py:94-95` — **WHAT**: `win_rate = w / total` where `total = w + l` correctly excludes pushes from the denominator. However `avg_edge` at line 112 averages over ALL picks including VOID/P. **WHY WRONG**: Pushes/VOIDs shouldn't contribute to the average edge calculation since they have no outcome. Not critical but slightly inflates or deflates the edge signal depending on whether void picks have edge values. **FIX**: Compute `avg_edge` only over `picks where result in (W, L)`.

- **LOW** `analyze_picks.py:456-458` — **WHAT**: Top-10 winners sort key `size * (odds/100 if odds > 0 else 100/abs(odds) if odds < 0 else 0)`. **WHY WRONG**: If `odds_num == 0` (unparseable odds row), profit is forced to 0 rather than being excluded. The `else 0` branch means that a malformed odds entry sorts as 0-profit winner, but won't show at the top. Not critical; matches the pattern in `calc_metrics`. Consistent.

### TODO/FIXME/HACK
None found.

---

## 5. `engine/clv_report.py`

### Summary
CLV formula: the report displays `clv` column values from `pick_log.csv` as already-computed `closing_ip - opening_ip` (positive = beat close), which matches `capture_clv.py` convention per CLAUDE.md. The `exclude_run_types=["daily_lay"]` and `exclude_stats=["PARLAY"]` correctly removes parlays from CLV analysis. The `--shadow` flag works via `include_shadow` parameter. One issue: `sgp` and `longshot` run types are NOT excluded from `load_all_picks`, only `daily_lay` is excluded. SGP/longshot rows have `stat=PARLAY` so they'll be filtered by `exclude_stats=["PARLAY"]`, but this is an implicit dependency rather than explicit exclusion.

- **MEDIUM** `clv_report.py:155-158` — **WHAT**: `exclude_run_types=["daily_lay"]` excludes daily lay from CLV analysis, but `sgp` and `longshot` are not explicitly excluded. They are removed via `exclude_stats=["PARLAY"]` since those rows use `stat=PARLAY`. **WHY WRONG**: The exclusion depends on stat labeling remaining consistent. If `sgp` or `longshot` rows ever get a different stat label (e.g. a leg-level stat), they'd leak into CLV analysis without individual closing lines. **FIX**: Add `"sgp"` and `"longshot"` to `exclude_run_types` explicitly for clarity.

- **LOW** `clv_report.py:49-51` — **WHAT**: `SHADOW_LOGS = {"MLB": PICK_LOG_MLB_PATH}`. **WHY WRONG**: WNBA shadow log (`pick_log_wnba.csv`) is not included, same issue as `analyze_picks.py`. When `--shadow` is used, WNBA picks won't appear. **FIX**: Add `PICK_LOG_WNBA_PATH` from `paths.py` to `SHADOW_LOGS`.

- **LOW** `clv_report.py:269-272` — **WHAT**: `singles` and `parlays` breakdown: `singles` is `primary + bonus`, `parlays` is `sgp + longshot`. `daily_lay` run_type is excluded from the data (line 155) but not listed in either category — `daily_lay` picks with outcome data would simply not appear in singles OR parlays breakdown. **WHY WRONG**: Small omission — `daily_lay` is excluded from load, so they can't appear in any breakdown. The comment at line 276 `"Singles: primary + bonus — use this for model assessment"` is accurate. Not a bug but worth documenting. **FIX**: Document that `daily_lay` is excluded from CLV report.

### TODO/FIXME/HACK
None found.

---

## 6. `engine/weekly_recap.py`

### Summary
P&L logic is correct: `COUNTED_RUN_TYPES = {"primary", "bonus"}` — SGP/longshot/daily_lay are intentionally excluded from weekly P&L per the file comment ("Matches grade_picks.py COUNTED_RUN_TYPES"). `compute_pl()` handles both positive and negative American odds correctly. `_REFUNDED_RESULTS = frozenset({"P", "VOID"})` correctly excludes push/void stakes from the ROI denominator. The Sunday trigger comment matches the Task Scheduler schedule. Discord guard logic is sound. One issue: `week_range()` has an off-by-one possibility on Mondays.

- **MEDIUM** `weekly_recap.py:224-232` — **WHAT**: `week_range()` uses `days_since_sunday = (today.weekday() + 1) % 7` to compute last Sunday. On Monday (`weekday()=0`), this gives `days_since_sunday=1`, so `last_sunday = Monday - 1 day = Sunday`, `last_monday = Sunday - 6 days = Monday`. **WHY WRONG**: If run on Monday (not Sunday as scheduled), it returns the CURRENT week's Mon-Sun (Mon through the previous day), which is the correct behavior. But the docstring says "most recently completed week" — on Monday it returns Mon (today) through Sunday (yesterday), which is a 1-day "week". This is consistent with the docstring note "If today is Sunday, returns this week (Mon–today)" but Monday behavior gives a week ending yesterday (Sunday) starting today — a range where Monday > Sunday. `filter_week` uses `mon_str <= date <= sun_str` so a Monday > Sunday range would return 0 rows. **FIX**: Add explicit handling for Monday: if `today.weekday() == 0`, use last week's range (subtract 7 more days from last_monday). Or better: document that this function should only be called on Sundays.

- **LOW** `weekly_recap.py:665-666` — **WHAT**: In `post_weekly_recap`, fallback guard path: `if not _HAS_SHARED_GUARD: _save_guard(guard)` uses the local `guard` variable defined at line 646 (`guard = _load_guard()`). **WHY WRONG**: If `force=True` is set (--repost), the code skips the `_load_guard()` call entirely (lines 649-652), so `guard` is undefined in the `not force` branch at line 666. Python would raise `NameError: name 'guard' is not defined` if `force=True` and `not _HAS_SHARED_GUARD` and the post succeeds. **FIX**: Initialize `guard = {}` before the `if not force` block, or guard with `if 'guard' in locals()`.

- **LOW** `weekly_recap.py:493-494` — **WHAT**: In `build_weekly_embed`, `w/(w+l)*100` at line 494 could raise `ZeroDivisionError` if `w+l == 0` (all pushes week). **WHY WRONG**: The `round(w/(w+l)*100) if w+l else 0` guard is present — this is actually handled correctly. Note this for reference. Not a bug.

- **LOW** `weekly_recap.py:68` — **WHAT**: `COUNTED_RUN_TYPES = {"primary", "bonus"}`. **WHY WRONG**: SGP/longshot/daily_lay are excluded from the weekly P&L, which is intentional by design. But the Discord embed shows a full win-rate that excludes all the other bet types. If a user checks the weekly recap against their actual book balance, it will differ because SGP/longshot/daily_lay P&L is not counted. This is a known design choice (documented in the comment) but could confuse new users or anyone cross-checking records. **FIX**: Document in the embed or add a footnote clarifying what's excluded.

### TODO/FIXME/HACK
None found.

---

## 7. `engine/calibrate_distributions.py`

### Summary
All 5 sport tables are covered (NBA, MLB_P, MLB_B, NHL_SK, NHL_G) plus WNBA. K is correctly in MLB_P stats table (`"k"`) and is NOT explicitly treated as Poisson or NB in `_CURRENT_PARAMS` — it's listed as `"NB r=5.0 PROVISIONAL"` which contradicts CLAUDE.md which states "K distribution: CLOSED 2026-05-26. Within-player var/mu=1.031 → Poisson confirmed. Moved from NB_STATS to POISSON_STATS." The `deployed_nb_r` comparison table still has `("MLB_P", "k"): 5.0` as if NB is deployed, but CLAUDE.md says K is Poisson. The script does NOT save to `docs/calibration_results.json` by default — that requires `--save docs/calibration_results.json` explicitly.

- **HIGH** `calibrate_distributions.py:310-311` and `404-408` — **WHAT**: `_CURRENT_PARAMS` lists `("MLB_P", "k"): "NB r=5.0 PROVISIONAL"` and `deployed_nb_r` includes `("MLB_P", "k"): 5.0`. **WHY WRONG**: CLAUDE.md states K distribution is CLOSED (2026-05-26): within-player var/mu=1.031 → Poisson confirmed, K moved from NB_STATS to POISSON_STATS in `run_picks.py`. The calibration script still treats K as NB with r=5.0 PROVISIONAL, meaning (a) the `print_report` will show K as currently NB when it's actually Poisson, and (b) `print_changes` will compare new calibration against the old NB r=5.0 instead of against Poisson. This will generate spurious "actionable change" suggestions. **FIX**: Update `_CURRENT_PARAMS` to `("MLB_P", "k"): "Poisson (confirmed 2026-05-26 var/mu=1.031)"` and remove `("MLB_P", "k")` from `deployed_nb_r`.

- **HIGH** `calibrate_distributions.py:376-379` — **WHAT**: `save_json()` does not write atomically — it uses a plain `open(path, "w")`. **WHY WRONG**: CLAUDE.md says results go to `docs/calibration_results.json`. A crash or keyboard interrupt mid-write would leave a partial JSON file, causing any tool that reads the results file (e.g. future calibration comparisons) to get a JSON decode error. **FIX**: Use `atomic_write_json` from `io_utils.py` (already used in `weekly_recap.py`).

- **MEDIUM** `calibrate_distributions.py:301-311` — **WHAT**: `_CURRENT_PARAMS` is missing MLB_B, NHL_SK, NHL_G, and WNBA deployed parameters. The parameters that ARE in CLAUDE.md but missing from `_CURRENT_PARAMS` include: `HA` (NB r=13.41), `RBI` (NB r=0.87), `ER` (NB r=2.62), `HRR` (NB r=1.5), `OUTS` (Normal mult=0.311/min=1.0), `SV` (Normal mult=0.253/min=3.5). **WHY WRONG**: `print_changes()` can only flag actionable changes for params it knows about. Any of these stats that change materially between calibration runs will show as "NEW: ... (currently uncalibrated)" instead of showing the delta from the deployed value. **FIX**: Add all deployed params from CLAUDE.md to `_CURRENT_PARAMS` and `deployed_nb_r`/`deployed_normal`.

- **MEDIUM** `calibrate_distributions.py:107-113` — **WHAT**: NHL_G `continuous_stats` includes `"sa"` and `"sv"` but not `"ga"`. **WHY WRONG**: `ga` (goals against) for a goalie ranges roughly 0-7 with mean ~2.7. It is a count stat. At mean ~2.7, it falls below the `mu >= 8.0` threshold for automatic Normal classification, so it will be classified as Poisson or NB by the script. CLAUDE.md confirms `SV` is Normal (mult=0.253, min=3.5) and `HA` is NB (r=13.41 — hits allowed for pitchers, not `ga`). NHL_G `ga` isn't in CLAUDE.md SIGMA or NB_R, but leaving `sa` as continuous while `ga` is not may be inconsistent (shots against and goals against have similar game-context dependence). **FIX**: Verify whether `ga` should also be in `continuous_stats` for NHL_G, or document why it's treated as a count stat.

- **LOW** `calibrate_distributions.py:229` — **WHAT**: `if is_continuous or mu >= 8.0: dist = "Normal"`. **WHY WRONG**: The threshold `mu >= 8.0` for automatic Normal is hardcoded at line 229 but is not the same as the docstring threshold (`mu >= 5`) at line 16. The docstring says "mu ≥ 5 OR continuous flag → Normal sigma" but the code uses 8.0. **FIX**: Align docstring and code (use the same threshold value), and add a comment explaining why 8.0 was chosen.

- **LOW** `calibrate_distributions.py:459-515` — **WHAT**: The `--save` argument saves to a user-specified path. The CLAUDE.md says results go to `docs/calibration_results.json`, but this path is not hardcoded as a default. **WHY WRONG**: Users must always remember to pass `--save docs/calibration_results.json`; there is no default. Results are never auto-saved to the canonical location. **FIX**: Add a `--save-default` flag or set the canonical docs path as the default for `--save`.

### TODO/FIXME/HACK
None found.

---

## Root Shims

Verified shims (all 5-line pattern):
- `run_picks.py` — correct shim to `engine/run_picks.py` ✓
- `grade_picks.py` — correct shim to `engine/grade_picks.py` ✓
- `sgp_builder.py` — correct shim to `engine/sgp_builder.py` ✓
- `results_graphic.py` — correct shim to `engine/results_graphic.py` ✓
- `weekly_recap.py` — correct shim to `engine/weekly_recap.py` ✓
- `analyze_picks.py` — correct shim to `engine/analyze_picks.py` ✓
- `clv_report.py` — correct shim to `engine/clv_report.py` ✓
- `capture_clv.py` — correct shim to `engine/capture_clv.py` ✓

**MISSING SHIMS (per CLAUDE.md spec):**
- `pick_log_schema.py` — **does not exist** at root level
- `secrets_config.py` — **does not exist** at root level

These are both listed in the CLAUDE.md "Key Files" table as root-level files to check. However, neither is a CLI entry point (they are library modules), and `runpy.run_module` on a library module wouldn't do anything useful. The absence of shims is likely intentional — they're imported directly as library modules, not run as scripts. Flag as LOW/OPEN_QUESTION only.

- **LOW** `(root level)` — **WHAT**: `pick_log_schema.py` and `secrets_config.py` do not have root-level shims. **WHY WRONG**: The audit spec listed them as expected shims, but they are library modules (not CLI entry points). If someone runs `python pick_log_schema.py` from the project root, Python would fail with `ModuleNotFoundError` because `engine/` is not in sys.path. **FIX**: Either add shims for completeness (`runpy.run_module("pick_log_schema", ...)`) or document that these are import-only modules.

---

## Cross-file consistency checks

- **MEDIUM** `sgp_builder.py:77` + `secrets_config.py:105` — `DISCORD_SGP_WEBHOOK` is exported from `secrets_config.py` and imported correctly in `sgp_builder.py` (deferred import inside `post_sgp`). The fallback to `DISCORD_BONUS_WEBHOOK` is implemented at line 1049. ✓

- **MEDIUM** `sgp_builder.py:NB_R` vs `run_picks.py NB_R` — `sgp_builder.py` maintains its own copy of `NB_R` (lines 78-84): `3PM=9.15, AST=9.68, REB=10.18`. These match CLAUDE.md values. However if `run_picks.py` NB_R values are ever updated, `sgp_builder.py` must also be manually updated. There is no single-source import. **FIX**: Consider importing NB_R from `run_picks.py` or extracting to a shared constants module.

- **OPEN_QUESTION** `weekly_recap.py:68` vs `analyze_picks.py` — `weekly_recap.py` defines `COUNTED_RUN_TYPES = {"primary", "bonus"}` and matches `grade_picks.py`. `analyze_picks.py` uses `load_rows` without filtering by run_type (it returns all graded rows including sgp/longshot/daily_lay). The two tools give different totals for the same date range — this is intentional but undocumented in the CLI help text.

- **OPEN_QUESTION** `analyze_picks.py:110-111` — `risked` excludes `P` and `VOID` from the denominator, which is correct. However, VOID rows only appear if `graded_only=True` returns them. Need to verify `pick_log_io.load_rows` treats `result="VOID"` as graded. If it doesn't, VOID picks are excluded from analysis entirely (which is also acceptable behavior) but could explain small discrepancies.

---

## Complete findings list by severity

### CRITICAL
(none)

### HIGH
- **HIGH** `calibrate_distributions.py:310-311,404-408` — K distribution still listed as NB in `_CURRENT_PARAMS` and `deployed_nb_r`; should be Poisson (confirmed closed 2026-05-26).
- **HIGH** `calibrate_distributions.py:376-379` — `save_json()` is not atomic; partial write corrupts the canonical results file.

### MEDIUM
- **MEDIUM** `sgp_builder.py:1094` — `today_str=None` silently skips logging with no warning when `save=True`.
- **MEDIUM** `sgp_builder.py:1208-1220` — CLI has no `--no-save` flag; `reason` string mentions `--no-discord` path that doesn't exist at CLI.
- **MEDIUM** `analyze_picks.py:415-416` — `_PROP_STATS` missing SV, GA, BB, PC, RBI, RUNS, GOALS, NHLPTS, NHLBLK, NRFI, YRFI.
- **MEDIUM** `analyze_picks.py:357-367` — `--shadow` flag doesn't include `pick_log_wnba.csv`.
- **MEDIUM** `clv_report.py:155-158` — `sgp`/`longshot` not explicitly excluded from CLV (implicit via stat=PARLAY filter; fragile).
- **MEDIUM** `calibrate_distributions.py:301-311` — `_CURRENT_PARAMS` missing most deployed params (HA, RBI, ER, HRR, OUTS, SV).
- **MEDIUM** `calibrate_distributions.py:107-113` — NHL_G `ga` may need to be in `continuous_stats`; inconsistent with `sa`/`sv`.

### LOW
- **LOW** `pick_log_schema.py:41` — stale comment "Canonical schema (v3)" should be "(v4)".
- **LOW** `sgp_builder.py:878-891` — `_sgp_book()` uses different algorithm than `_pick_best_book()` (fragile redundancy).
- **LOW** `sgp_builder.py:40-41` — inconsistent import pattern: `DISCORD_BONUS_WEBHOOK` at module level vs `DISCORD_SGP_WEBHOOK` deferred.
- **LOW** `secrets_config.py:121-132` — `_WEBHOOK_REGISTRY` snapshots values at import time; stale in tests that modify env.
- **LOW** `secrets_config.py:18-27` — docstring template missing `DISCORD_LONGSHOT_WEBHOOK` and `DISCORD_SGP_WEBHOOK`.
- **LOW** `analyze_picks.py:112` — `avg_edge` computed over all picks including VOID/P rather than W+L only.
- **LOW** `clv_report.py:49-51` — `SHADOW_LOGS` missing WNBA log.
- **LOW** `weekly_recap.py:665-666` — `guard` variable undefined when `force=True` and `not _HAS_SHARED_GUARD`; potential `NameError`.
- **LOW** `calibrate_distributions.py:16,229` — docstring says `mu >= 5` for Normal but code uses `mu >= 8.0`.
- **LOW** `calibrate_distributions.py:459-515` — no default save path to canonical `docs/calibration_results.json`.
- **LOW** `(root level)` — `pick_log_schema.py` and `secrets_config.py` shims absent (library modules, not CLI entry points).
- **LOW** `sgp_builder.py:56-57` — `MIN_DISTINCT_PLAYERS = 3` dead code constant.

### OPEN_QUESTION
- `sgp_builder.py:946` — `f"+{parlay_odds}"` would display `+-123` if parlay_odds somehow goes negative (not possible given filter, but defensive coding would use `f"{parlay_odds:+d}"`).
- `weekly_recap.py:224-232` — `week_range()` on Monday returns a range ending yesterday that is valid, but Monday > Sunday means zero picks would be returned. Add a warning or guard.
- `pick_log_schema.py:136-149` — `migrate_row()` `source_header` parameter is reserved but unused; version-aware defaulting not implemented.
- Cross-file: `sgp_builder.py` has its own `NB_R` dict (duplicated from `run_picks.py`); no single source of truth.
- Cross-file: `analyze_picks.py` and `weekly_recap.py` give different totals for same date range by design; undocumented in CLI help.
- `clv_report.py`: `daily_lay` exclusion from CLV is correct (no individual closing line) but not documented in `--days`/`--sport` help.
