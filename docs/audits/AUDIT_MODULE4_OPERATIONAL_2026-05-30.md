# RESEARCH AUDIT — MODULE 4: OPERATIONAL SYSTEMS
DATE: 2026-05-30
AUDITOR: Claude Sonnet 4.6 (automated multi-agent)

## FILES READ

### JonnyParlay (engine/)
- grade_picks.py
- capture_clv.py
- clv_report.py
- analyze_picks.py
- weekly_recap.py
- pick_log_schema.py
- io_utils.py
- paths.py
- engine_logger.py
- log_setup.py
- diagnostics.py

### EdgeModel (engine/)
- calibrate_distributions.py
- calibrate_platt.py
- mlb_stats_fetcher.py
- nhl_stats_fetcher.py
- wnba_stats_fetcher.py

### Not audited this session (discovered in Step 0, out of scope for Module 4)
JonnyParlay: _check_dvp.py, analyze_playoff_scalars.py, book_names.py, brand.py,
calibrate_sigma.py, calibrate_winprob.py, diag_*.py, discord_guard.py,
empirical_analysis.py, evaluate_projector.py, export_pick_log_xlsx.py,
historical_backtest.py, http_utils.py, mlb_starter_fetcher.py, month_names.py,
name_utils.py, nb_calibrate.py, pick_labels.py, pick_log_io.py,
projection_accuracy.py, sabersim_backtest.py, webhook_fallback.py

---

## PHASE 1 — FULL INVENTORY (key formulas and constants)

### grade_picks.py
- WIN/LOSS/PUSH: `actual > line → W`, `actual < line → L`, `actual == line → P` (line ~1232-1239)
- VOID path: `actual is None` after all name matching → VOID (not LOSS)
- DNP treatment: VOID (correct per industry standard)
- Compute P&L: `size * (100/abs(odds))` if `odds < 0` else `size * (odds/100)` (line ~1332)
- Push P&L: `0.0`. VOID P&L: `0.0`
- ROI: `(pl / risked * 100)` excluding P/VOID from denominator (line ~1354)
- Parlay grade: any leg L → L; VOID/P legs drop, remaining legs decide; all drop → P (line ~853-865)
- F5: requires `len(complete) >= 5` innings (line ~1063)
- NRFI: `away_r1 + home_r1 == 0 → W` (line ~1023)
- HRR: `hits + runs + RBIs` (line ~1475)
- Lock: `FileLock(lock_path, timeout=30)`, fallback to unlocked write on timeout (line ~1782)
- Win rate streak: `if pl > 0` strict, breakeven breaks streak (line ~1384)
- `SHADOW_SPORTS = {"WNBA"}` (line ~83)
- `_GUARD_TTL_DAYS = 90` (line ~1794)
- NHL OT: no regulation-only puck line handler; grades on full final score
- F5: returns None (never grades) for games called official at 4.5+ innings

### capture_clv.py
- `CAPTURE_BEFORE_SECS = 45 * 60` (T-45 polling start) (line ~166)
- `CAPTURE_AFTER_SECS = 3 * 60` (T+3 cutoff) (line ~167)
- `CAPTURE_WRITE_BEFORE_SECS = 10 * 60` (T-10 write gate) (line ~168)
- `POLL_INTERVAL_SECS = 120` (2-minute polling) (line ~169)
- `POLL_INTERVAL_LONG_SECS = 30 * 60` (30-min max sleep between windows) (line ~170)
- `MAX_DAEMON_UPTIME_SECS = 18 * 60 * 60` (18h self-termination) (line ~194)
- `MIN_UPTIME_BEFORE_EXIT_SECS = 4 * 60 * 60` (4h min before "all captured" exit) (line ~184)
- CLV formula: `calc_clv = implied_prob(closing_odds) - implied_prob(your_odds)` (line ~897)
- `implied_prob(o)`: `abs(o)/(abs(o)+100)` if `o < 0` else `100/(o+100)` — **raw vigged** (line ~263)
  - Zero-guard present: `if not o or not math.isfinite(o): return None`
- `STALE_AFTER_SECS = 30 * 60` (line ~175)
- Lock: `FileLock(lock_path, timeout=30)` → skips write on timeout (does NOT fallback to unlocked)
- SGP/Longshot excluded from CLV capture (line ~576)
- Line tolerance: ±0.25 (line ~316)
- Retry: `_API_RETRY_MAX=3`, backoff `[2s, 4s, 8s capped 60s]` (line ~344)

### clv_report.py
- `implied_prob(o)`: `abs(o)/(abs(o)+100)` if `o < 0` else `100/(o+100)` — **NO zero-guard** (line ~57)
- CLV average: `sum(clvs) / len(clvs)` — **simple unweighted mean** (line ~209)
- CLV beat rate: `sum(1 for c in clvs if c > 0) / len(clvs)` — strictly positive (line ~210)
- Picks without CLV data excluded from avg_clv and beat_rate
- Parlay run_types excluded: `exclude_run_types=["daily_lay", "sgp", "longshot"]` (line ~157)
- Rolling window: last 7 days (line ~388)
- Min for trend: 3 distinct dates (line ~383)
- Min CLV samples per stat: 5 (line ~346)
- **Conservative mode: DOES NOT EXIST in current code**

### analyze_picks.py
- Win rate: `w / (w + l)` — pushes excluded from denominator (line ~94-98)
- ROI: `units_pl / risked * 100`, risked excludes P/VOID (line ~112)
- Avg edge: simple unweighted mean of model edge (line ~114)
- Avg win_prob: includes all picks (zeroes from parlays dilute) (line ~116)
- CLV avg: simple unweighted mean of non-null CLV values (line ~290)
- `MIN_SAMPLE_NOTE = 20` (line ~48)
- Calibration warning below 100 picks (line ~283)
- CLV reliability note below 100 CLV rows (line ~324)
- `_PROP_STATS`: hardcoded set (line ~419) — not imported from canonical source
- Parlays (sgp, longshot, daily_lay) are NOT filtered from overall/per-stat/per-tier breakdowns
- Card slot breakdown: includes `run_type == ""` (empty) in "primary" filter (line ~433)
- `PICK_LOG_CUSTOM_PATH` defined locally (not imported from paths.py) (line ~45)

### weekly_recap.py
- `COUNTED_RUN_TYPES = {"primary", "bonus"}` — SGP/Longshot/Daily Lay excluded (line ~68)
- P&L: `size * (100/abs(odds))` or `size * (odds/100)` depending on sign (line ~101-117)
- Push/VOID P&L: `0.0` (correct)
- Zero-odds WIN: silently returns `0.0` profit (line ~107)
- `daily_stats()` rounds: `round(pl, 2)`, `round(roi, 1)` at return (line ~133)
- ROI: excludes P/VOID from `risked` (line ~128-132)
- Monthly total: keyed on Sunday's month; cross-month weeks only show new-month data (line ~474)
- CLV avg: simple unweighted mean (line ~199)
- `_GUARD_TTL_DAYS = 90` (line ~524)
- Weekly window: Monday–Sunday (line ~1575)

### pick_log_schema.py
- `SCHEMA_VERSION = 4`, 29 columns (line ~44)
- `over_p_raw`: blank for legacy/non-prop/manual rows; pre-Platt probability for v4 prop picks
- `legs`: JSON array, expected fields: player, direction, line, stat, sport, game — no validation function
- `context_verdict`: frozen at "disabled" for new rows; present for schema compat only
- `detect_schema_version()`: presence-only check, no completeness validation (line ~105)
- `MANUAL_REQUIRED_FIELDS`: does not include player, tier, result (line ~160)
- `validate_is_home_for_stat()`: advisory only, not enforced at write path (line ~272)
- Module asserts fire at import time (correct) (line ~494)

### io_utils.py
- `atomic_write_json()`: mkstemp → dump → flush → fsync → os.replace (correct atomic pattern)
- Tmp in same directory as target (required for atomic rename)
- This file only handles JSON; CSV locking is in pick_log_io.py

### paths.py
- `PROJECT_ROOT` resolved at import time (line ~82)
- `PICK_LOG_PATH`: `Path(os.environ["JONNYPARLAY_PICK_LOG"])` if set — **no .resolve()** (line ~101)
- `PICK_LOG_CUSTOM_PATH`: hardcoded `DATA_DIR / "pick_log_custom.csv"`, no env override (line ~106)
- `_looks_like_project()`: checks for `data/` subdir only (heuristic)
- Fallback: `~/Documents/JonnyParlay` (Windows hardcoded)

### engine_logger.py
- `_FORMAT = "%(asctime)s  %(levelname)-8s [%(name)s] %(message)s"` (line ~52)
- Idempotency via `_CONFIGURED: set[tuple[str, str]]` keyed by (name, normalized_path)
- `logger.propagate = False` unconditionally
- CWD-sensitive: `os.path.abspath(str(log_path))` for key — breaks if CWD changes between calls
- `reset_for_tests()`: clears cache but does NOT remove existing handlers

### log_setup.py
- `_DEFAULT_FORMAT = "%(asctime)s  %(levelname)-8s %(message)s"` — **MISSING `[%(name)s]`** (line ~53)
- Comment claims format is "identical to engine_logger._FORMAT" — **FALSE**
- Rotation: 5 MB max, 5 backups (line ~47-48)
- Partial rotation failure: leaves backup slots disordered (continues after first OSError)
- Plain FileHandler blocks rotation silently (returns None, caller ignores return) (line ~101)

### diagnostics.py
- Enable check via `os.environ.get()` on every call (not cached) (line ~42)
- `flush()`: `out_file.write_text(json.dumps(...))` — NOT atomic (line ~135)
- `flush_vegas()`: same non-atomic write (line ~248)
- `write_text()`: no `encoding="utf-8"` specified
- Partial record risk: post-hook fires without pre-hook → silent empty pre-fields

### calibrate_distributions.py
- Distribution classification: **var/mu ratio only** — no chi-squared, no KS test (line ~13-16)
  - NB: var/mu > 1.20; Poisson: 0.80-1.20; underdispersed: < 0.80; Normal: mu >= 8.0
- `mu >= 8.0` forces Normal regardless of overdispersion (PTS always Normal)
- NB r: **weighted method of moments** in SQL: `Σ(n·μ²) / Σ(n·max(var−μ, 0.001))` (line ~188)
- NB r floor: max(r, 0.1); cap: min(r, 30.0) (line ~219, 224)
- Variance: `AVG(x*x) - AVG(x)*AVG(x)` — **biased (divides by n, not n-1)** (line ~172)
- Calibration is **within-player**, pooled with game-count weights (correct approach)
- Min games: NBA=15, MLB_P=8, MLB_B=20, NHL_SK=15, NHL_G=8, WNBA=10
- Min players for result: **n_players >= 3** (too low) (line ~211)
- Normal min: `0.5 * avg_std` — **not a principled 10th-percentile estimate** (line ~200)
- Output: printed table + optional JSON/CSV via `--save`
- **No automated deploy path to run_picks.py — manual copy-paste only**
- No date/staleness check anywhere
- `_CURRENT_PARAMS` comparison dict incomplete (no MLB/NHL entries) (line ~303)

### calibrate_platt.py
- Training filter: primary/bonus, W/L only, props only (line ~55-64)
- Formula: fits `sigmoid(A * logit(over_p) + B)` in **logit-space**
- run_picks.py currently applies as `sigmoid(PLATT_A * over_p_raw + PLATT_B)` — **raw-probability space**
- H3 deploy requires atomic 2-step: change formula in run_picks.py THEN update constants
- Loss function: **negative log-likelihood** (correct for training) (line ~117)
- Optimizer: **Nelder-Mead** (correct but suboptimal — L-BFGS-B would be faster) (line ~124)
- Regularization: **none** (line ~108-128)
- Train/test split: **5-fold CV, sequential** (not temporal) (line ~196-222)
  - On time-ordered picks, standard k-fold can train on future data — optimistic OOS Brier
- H3 gate: n >= 100 non-null `over_p_raw` rows; exits with code 0 below gate (line ~150)
- `--native-only` flag required to exclude double-calibration-bias legacy rows; **not default**
- Bucket check: bins [0.55, 0.60, 0.65, 0.70, 0.75, 0.80) — no [0.50, 0.55) bucket (line ~241)
- No guard in run_picks.py to detect formula/constant space mismatch

### mlb_stats_fetcher.py
- API: `https://statsapi.mlb.com/api/v1` (official MLB Stats API)
- Default: Regular season only (game_type="R"), 4 seasons (2023-2026)
- Completion filter: `{"Final", "Game Over", "Completed Early"}`
- IP parsing: `int(whole) * 3 + int(frac)` (correct .1=1out convention)
- Starter: first entry in `pitchers` list — assumes API order
- Sleep: 0.5s per request; retry: 3 attempts, backoff [2s, 5s, 15s]
- Error handling: broad `except Exception` (no 404/429 differentiation)
- Duplicate: `INSERT OR IGNORE` for stat rows (upsert for game metadata)
- **No correction path for corrupted rows** (--force updates game metadata only)
- Per-season abort: >20 errors
- Batch commit: every 50 games
- No post-fetch row count validation

### nhl_stats_fetcher.py
- API: `https://api-web.nhle.com/v1` (official NHL API)
- Default: Regular season only (game_type=2), 3 seasons (20232024-20252026)
- Schedule: weekly pagination following `nextStartDate` field
- Date windows: hardcoded dict per season (line ~68-77)
- RS window end 20252026: 2026-04-19; PO window end: 2026-08-01
- Finality: `gameState == "OFF"` only
- TOI: `MM:SS` → `int(minutes)*60 + int(seconds)`
- Sleep/retry: identical to MLB fetcher
- **Same INSERT OR IGNORE / no correction path issue as MLB**
- Silent stop if `nextStartDate` missing mid-season

### wnba_stats_fetcher.py
- API: `https://stats.wnba.com/stats/leaguegamelog` (official WNBA stats)
- Anti-scraping headers: Chrome 120 UA, WNBA.com Referer (line ~52-62)
- Default: Regular season, 4 seasons (2023-2026)
- Architecture: **entire season in one API call** (no per-game resume)
- Sleep: 2s (more conservative than MLB/NHL); retry backoff: [5s, 15s, 30s]
- Resume: season-level only (complete status in pull_log)
- Duplicate: `INSERT OR IGNORE` — same no-correction-path issue
- Row validation: `< 30` check (but schema has 33 columns)
- Row unpacking: positional — breaks on mid-column API change
- `cur.rowcount` fallback to `len(stat_rows)` can log false insert count (line ~336)
- No dedicated `wnba_games` table

---

## CRITICAL (C): 0

No critical findings. All critical-level risks have either corrective paths or are blocked by data gates.

---

## HIGH (H): 12

**H1** — `grade_picks.py:~1782-1783` — `_atomic_write_rows()` falls back to an **unlocked write** after a 30-second lock timeout. The CLV daemon write path skips on timeout (safe); the grader write path falls through to `_do_write()` without the lock (unsafe). Under lock contention between grade_picks and capture_clv, this opens a concurrent clobber window. — Fix: replace fallback with hard error + warning; do not write without the lock.

**H2** — `clv_report.py:~57-65` — `implied_prob()` has **no zero-guard**. `odds=0` → `100/(0+100) = 1.0` (100% implied probability). In contrast, `capture_clv.py:~263-278` has the guard (`if not o or not math.isfinite(o): return None`). Any row with `closing_odds=0` or `odds=0` (malformed entry or logging bug) injects 1.0 into `avg_clv` and `clv_beat_rate`. This is a copy-divergence: the fix was added to `capture_clv.py` but not propagated to `clv_report.py`. — Fix: add `if not o or not math.isfinite(float(o)): return None` guard in `clv_report.implied_prob()`.

**H3** — `weekly_recap.py:~68, ~240-248` — `COUNTED_RUN_TYPES = {"primary", "bonus"}` **silently excludes SGP, Longshot, and Daily Lay** from the Discord P&L recap. A +$10u SGP win does not appear in the weekly report. The exclusion has no disclaimer. — Fix: either include all run_types or add a footnote line to the embed noting "SGP/Longshot/DailyLay not included."

**H4** — `analyze_picks.py:~407-415` + `weekly_recap.py:~68` — Cross-module **irreconcilable P&L**. `weekly_recap` excludes SGP/Longshot/Daily Lay; `analyze_picks` includes them. A user running both tools sees different total P&L and win rates with no explanation. There is no `--recap-scope` flag in `analyze_picks` that reproduces the weekly_recap's pick scope. — Fix: add `--recap-scope` flag to `analyze_picks` or document the divergence explicitly.

**H5** — `log_setup.py:~53-54` vs `engine_logger.py:~52` — **Format string mismatch**. `log_setup._DEFAULT_FORMAT` is `"%(asctime)s  %(levelname)-8s %(message)s"` (no module name). `engine_logger._FORMAT` is `"%(asctime)s  %(levelname)-8s [%(name)s] %(message)s"` (has `[%(name)s]`). The `engine_logger.py` module comment claims the formats are "identical." File logs (via `attach_rotating_handler`) lack the `[name]` bracket; terminal stream logs have it. `grep` patterns that include `[modulename]` will not match log files. — Fix: add `[%(name)s]` to `log_setup._DEFAULT_FORMAT`; remove false "identical" comment.

**H6** — `diagnostics.py:~135, ~248` — `diagnostics.flush()` and `flush_vegas()` use `Path.write_text(json.dumps(...))` — **not atomic**. A crash mid-write produces a corrupt JSON file. `io_utils.atomic_write_json()` already exists for exactly this purpose and is imported elsewhere. — Fix: replace both `write_text` calls with `atomic_write_json(out_file, payload)`.

**H7** — `EdgeModel/engine/calibrate_distributions.py:~303-319` — **No automated pipeline from calibration output to run_picks.py**. Calibrated NB r values are printed to console and optionally saved to JSON/CSV; deployment is manual copy-paste. The `_CURRENT_PARAMS` comparison dict is maintained by hand and is incomplete (no MLB_P, MLB_B, NHL, WNBA entries). Drift between DB and deployed constants is undetectable. — Fix: add a deploy-diff script that reads JSON output and prints a diff against deployed constants; mark deployed date in run_picks.py comments.

**H8** — `EdgeModel/engine/calibrate_platt.py:~196-222` — **Sequential k-fold CV on time-ordered picks**. Standard 5-fold splits by array position: fold 1 trains on picks 2-5, validates on pick 1 — but pick 1 may be chronologically later than picks 2-5. This allows models trained on future picks to evaluate past picks, inflating OOS Brier improvement. The "OOS Brier improvement > 0" gate can pass even when a refit actually hurts out-of-sample performance. — Fix: replace random k-fold with temporal walk-forward CV (train on first K%, validate on last K%).

**H9** — `EdgeModel/engine/calibrate_platt.py:~27-35` — **Logit-space fit, raw-space application**. `calibrate_platt.py` fits `sigmoid(A * logit(over_p) + B)`. `run_picks.py` currently applies `sigmoid(PLATT_A * over_p_raw + PLATT_B)` (raw probability). At H3, the formula in `run_picks.py` must change SIMULTANEOUSLY with the constants (2-step atomic operation). No guard in `run_picks.py` detects formula/constant space mismatch. Updating only the constants without the formula shifts every prop win_prob by ±12-18pp with no error raised. — Fix: add a `_PLATT_FORMULA_VERSION` constant to run_picks.py that calibrate_platt.py can validate; add a post-deploy smoke test that checks win_prob is in [0.50, 0.85] range.

**H10** — `EdgeModel/engine/calibrate_platt.py:~81-86, ~150-168` — **`--native-only` not default**. Without `--native-only`, legacy rows (pre-v4, no `over_p_raw`) use the already-calibrated `win_prob` as a proxy for `over_p_raw`. These rows carry Platt-corrected probabilities and re-fitting on them introduces double-calibration bias. The flag is documented but is not the default — a user running `python calibrate_platt.py` without the flag risks a corrupted refit. — Fix: make `--native-only` the default; rename the legacy-inclusive path to `--include-legacy`.

**H11** — `mlb_stats_fetcher.py`, `nhl_stats_fetcher.py`, `wnba_stats_fetcher.py` — **INSERT OR IGNORE with no correction path for corrupted stat rows**. All three fetchers use `INSERT OR IGNORE` on `UNIQUE(game_pk/game_id, player_id)`. If a row was partially inserted (API timeout mid-response, partial data), `--force` refreshes game metadata but leaves the corrupted stat rows untouched. There is no delete-and-reinsert path. Bad rows in `mlb_pitcher_game_stats`, `mlb_batter_game_stats`, `nhl_skater_game_stats`, `nhl_goalie_game_stats`, or `wnba_player_game_stats` are permanently frozen until manual SQL intervention. — Fix: add `--reinsert-game GAME_PK` flag to each fetcher that DELETEs existing stat rows for that game before re-fetching.

**H12** — `clv_report.py` (per web research Q3) — **Conservative mode referenced in audit brief, not found in code**. The brief asked for "exact trigger condition" for conservative mode. No such feature exists anywhere in `clv_report.py`. Either it was removed without documentation, or it was planned and never implemented. Any reference to conservative mode in external docs/Discord is misleading. — Fix: confirm with operator whether conservative mode was intentionally removed; if so, scrub any external references.

---

## MEDIUM (M): 25

**M1** — `capture_clv.py:~263`, `clv_report.py:~57` — **Vigged CLV understates true edge**. Both files compute `closing_implied_prob − your_implied_prob` using raw vigged American odds. Industry professionals (Pinnacle, OddsJam, Pikkit) standard is vig-free: devig both sides before comparing. At -110/-115, vigged CLV = +1.11pp; vig-free CLV = +2.17pp — a 95% understatement. CLAUDE.md description "consistent with industry standard" is inaccurate — vigged is the simpler approximation, not the professional standard. Systematic compression is directionally consistent (doesn't corrupt relative rankings between picks), but absolute CLV numbers are understated. — No immediate fix required; update CLAUDE.md description to "simplified vigged method."

**M2** — `grade_picks.py:~1063-1068` — **F5 grading: permanently ungraded for weather-shortened games**. Requires `len(complete) >= 5` full innings. A game called official at 4.5 innings (home team winning after 5 half-innings) returns `None` indefinitely — pick never grades. Books settle F5 on official game status. Affects any MLB rainout where the home team is ahead. — Fix: add handler for games with status "Final" where `len(innings) < 5` but `len(innings) >= 5` half-innings (or game has official status).

**M3** — `grade_picks.py:~1019-1021` — **NHL OT/SO: no regulation-only puck line handler**. NHL spread picks are graded on full final score including OT/SO. Some books (e.g., Bet365, ESPN BET) settle puck lines on regulation only. A team that loses in OT covers -1.5 on regulation result but not on final. No sport-specific OT handler exists. — Note: impact depends on which books were used; verify book settlement rules for puck lines.

**M4** — `grade_picks.py:~1222-1227` — **VOID fires on 422 path even for active players**. When `scores_by_game is None` (Odds API plan-limit 422), grade_picks assumes no game data and VOIDs the pick — even if the player was active and had stats. A name-matching miss on a historical re-run also produces permanent VOID (score data returns None, name match fails, VOID fires). — Fix: log a warning when VOID fires on the 422 path; separate the "no game data" case from the "name not found" case.

**M5** — `grade_picks.py:~856-865` — **DNP VOID drops parlay leg; may mismatch SGP book settlement**. Standard parlays: VOID leg drops, remaining legs continue (confirmed correct per research). SGPs: some books (e.g., BetMGM One Game Parlay) void the entire slip if any leg is voided. The grader always drops the leg and continues. For multi-game longshots this is correct; for SGPs this may overstate wins vs book settlement. — Fix: add a `sgp_dnp_mode` config option; or document that SGP grading may diverge from BetMGM settlement.

**M6** — `clv_report.py:~209`, `analyze_picks.py:~290`, `weekly_recap.py:~199` — **CLV average is simple unweighted mean across all three files**. A 0.25u pick and a 3u pick contribute equally to avg_clv. Stake-weighted mean would better represent bankroll edge. All three files are consistent with each other (no cross-file contradiction) but all three share the same methodological limitation. — Fix: add `stake_weighted_avg_clv` to all three reports alongside the simple mean.

**M7** — `analyze_picks.py:~419-421` — **`_PROP_STATS` hardcoded, not imported from canonical source**. New stats added to `run_picks.py` must also be manually added to this local set or they silently fall out of the stat×direction breakdown. No enforcement or test verifies sync. — Fix: import from `pick_log_schema.py` (add a `PROP_STAT_NAMES` frozenset there) and remove the local definition.

**M8** — `analyze_picks.py:~116` — **`avg_predicted_wp` includes zeroes from parlay/GL rows** in the overall metric display. Parlay and game-line rows have `win_prob=0`, dragging the average down. The calibration section correctly filters `win_prob_num > 0`, but `calc_metrics()` does not. — Fix: filter `win_prob_num > 0` in `calc_metrics()` for the `avg_predicted_wp` calculation.

**M9** — `weekly_recap.py:~133` — **`daily_stats()` rounds P&L to 2dp and ROI to 1dp at return**. The function is called per-day in `day_lines` display AND on the full-week set for totals. The total is computed correctly (one call on all week picks), but per-day values in the breakdown individually carry rounding. The `compute_pl()` docstring notes "do NOT round internally" — `daily_stats()` violates this for its returned values. — Fix: remove the `round()` calls from `daily_stats()` return; format at display layer only.

**M10** — `weekly_recap.py:~474-480` — **Cross-month weeks show partial monthly total without disclaimer**. For a week spanning Apr 28–May 4, the "month so far" is determined by the Sunday's month (May) and shows only May 1–4 picks. No note explains this. A user seeing 4 days of May data might think it's a full week. — Fix: add inline label "May so far (4 days)" instead of generic "month so far."

**M11** — `calibrate_distributions.py:~172-175` — **Biased population variance estimator**. `AVG(x*x) - AVG(x)*AVG(x)` divides by n, not n-1. At minimum thresholds (MLB_P min=8 games), correction factor is 8/7 ≈ 14%. Biased variance → smaller (var−μ) denominator → inflated NB r. At larger sample sizes (NBA min=15+, MLB_B min=20+) the bias is ≤7% and practically negligible. — Fix: replace with `SUM((x - avg)^2) / (COUNT(*) - 1)` or apply n/(n-1) correction in Python after fetch.

**M12** — `calibrate_distributions.py:~200-201` — **Normal min 0.5× multiplier not a principled 10th-percentile estimate**. For a half-normal the 10th percentile is ~0.35×σ, not 0.5×σ. The 0.5× heuristic overestimates the floor for high-variance stats (e.g., OUTS mult=0.311 vs 0.5×σ would yield a larger minimum than calibrated). — Note: the calibrated floor values already override this via manual override dict; low practical impact on deployed values.

**M13** — `calibrate_distributions.py:~211` — **`n_players >= 3` threshold for returning a calibration result**. At 3 players with 8 games each (24 game-observations), NB r estimates are highly unstable. No warning is emitted at low n. — Fix: raise to `n_players >= 10` with a warning at `n_players < 20`.

**M14** — `calibrate_platt.py:~124-128` — **Nelder-Mead optimizer for 2-parameter convex NLL**. The NLL surface for logistic regression is strictly convex; L-BFGS-B (scipy default for bounded optimization) is guaranteed to find the global minimum and is significantly faster. Nelder-Mead is derivative-free and can stall near the optimum for small `fatol`. At n=100-300 picks this is not a performance concern, but the solver is suboptimal. — Fix: replace `method='Nelder-Mead'` with `scipy.optimize.minimize(..., method='L-BFGS-B')` or use `sklearn.linear_model.LogisticRegression`.

**M15** — `calibrate_platt.py:~241-249` — **Bucket calibration check misses [0.50, 0.55) range**. Lowest bucket is `< 0.55`. If model assigns win_prob=0.52 when actual WR is 0.60, this under-confidence is invisible. Also no bucket for `>= 0.80`. — Fix: expand bucket edges to `[0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 1.00]`.

**M16** — `mlb_stats_fetcher.py:~321-323` — **Starter identification assumes API list order**. `starter_id = pitchers_list[0]` assumes the MLB Stats API returns the starting pitcher first. For opener-strategy games, a reliever is the technical "opener" and may be listed first. No validation against `gameData.probablePitchers` or similar. — Fix: cross-reference against game's `probablePitchers` from the schedule hydration or flag rows where `ip_outs < 9` for the "starter."

**M17** — `mlb_stats_fetcher.py:~233-253`, `nhl_stats_fetcher.py:~240-260` — **Broad `except Exception` catches non-retryable errors**. A 404 (invalid game_pk) retries 3 times with 22 seconds of sleep unnecessarily. A 429 (rate limit) retries on the same fixed backoff that may be too short. — Fix: check HTTP status code; fail fast on 4xx (except 429); add extended backoff for 429.

**M18** — `nhl_stats_fetcher.py:~321-324` — **Silent stop if `nextStartDate` missing mid-season**. If the API drops the `nextStartDate` field, the schedule pagination loop terminates silently, potentially missing weeks of games. No warning logged. — Fix: log a warning when `nextStartDate` is missing mid-season; add a date-based fallback that continues from `current_date + 7 days`.

**M19** — `wnba_stats_fetcher.py:~240-247` — **No partial-season resume**. One API call per season; a timeout results in zero rows stored and a "partial" status. The fetcher must re-pull the entire season from scratch. For 2026 mid-season, this is a large call. — Fix: add per-date chunking (split season into monthly windows with individual API calls).

**M20** — `wnba_stats_fetcher.py:~280-287` — **Positional row unpacking breaks on mid-column API schema change**. `(season_id, player_id, ..., plus_minus, *_rest) = row` is robust to appended columns but fails silently if the API inserts or reorders columns. The WNBA Stats API has historically changed column order. — Fix: use column headers from the API response (`resultSets[0]["headers"]`) to build a column-name-to-index mapping before unpacking.

**M21** — `wnba_stats_fetcher.py` — **No dedicated `wnba_games` table**. Game-level metadata (blowout margin, pace, game date) must be aggregated from player rows. Future opponent defense context, blowout sigmoid, or pace adjustments for WNBA would require adding this table. — Fix: create `wnba_games` table at schema level; populate from `game_id`, `game_date`, `matchup`, and `wl` fields in player rows.

**M22** — `mlb_stats_fetcher.py`, `nhl_stats_fetcher.py`, `wnba_stats_fetcher.py` — **`_name_key()` function duplicated across three files** (DRY violation). If a name normalization bug exists (accent handling, suffix removal, first-3 truncation), it must be fixed in all three places independently. — Fix: move `_name_key()` and `_fold_name()` to `name_utils.py` and import.

**M23** — `pick_log_schema.py:~65` — **`legs` JSON column has no validation function**. The expected format (array of dicts with player/direction/line/stat/sport/game keys) is documented in a comment but never enforced. Malformed legs JSON breaks readers silently. — Fix: add `validate_legs_json(legs_str) -> bool` helper; call at write time in sgp_builder and mlb_sgp_builder.

**M24** — `paths.py:~101` — **`PICK_LOG_PATH` env var not `.resolve()`'d**. `Path(os.environ["JONNYPARLAY_PICK_LOG"])` without `.resolve()` is CWD-sensitive. A relative path env var resolves differently if CWD changes between import and use. — Fix: `Path(os.environ["JONNYPARLAY_PICK_LOG"]).resolve()`.

**M25** — `analyze_picks.py:~45` vs `paths.py:~106` — **`PICK_LOG_CUSTOM_PATH` dual-definition**. `analyze_picks.py` constructs `PICK_LOG_CUSTOM_PATH` locally from `_DATA_DIR` instead of importing from `paths.py`. If the constant is renamed in `paths.py`, `analyze_picks.py` silently keeps the old path. — Fix: import `PICK_LOG_CUSTOM_PATH` from `paths` in `analyze_picks.py`; remove local definition.

---

## INFO (I): Selected observations

**I1** — `grade_picks.py` — DNP handling confirmed correct: `actual is None` after name matching → VOID (stake returned). This matches industry standard (all major books: DraftKings, FanDuel, BetMGM void props when player does not participate).

**I2** — `capture_clv.py` — T-10 write gate is consistent with best practice. Professional CLV tools (OddsJam, Pikkit) capture "as close to game time as possible"; T-10 is a practical proxy with no meaningful accuracy loss vs T-0.

**I3** — `calibrate_distributions.py` — Within-player calibration approach (pooling per-player means/variances rather than raw observations) is the correct methodology. Eliminates between-player talent heterogeneity from the distribution parameter estimates.

**I4** — `calibrate_platt.py` — Brier score is the correct metric for evaluating calibration improvement (strictly proper, interpretable, bounded [0,1]). Log-loss for training is also correct. The current combination is methodologically sound.

**I5** — NB r at deployed sample sizes (1246-1395 player-seasons for NBA): at these n values, method-of-moments and MLE converge to nearly identical results. Deployed NB_R values are reliable regardless of estimation method.

**I6** — `grade_picks.py:~795-865` — Standard parlay push rule confirmed by research: pushed leg drops, remaining legs continue. Multi-game longshot (6-leg, max 2/game) grading is correct.

**I7** — `weekly_recap.py:~199` — Win rate denominator (excludes pushes) is confirmed industry standard per professional sports betting literature.

**I8** — `capture_clv.py:~661` — CLV write-lock timeout correctly skips the write (does NOT fall back to unlocked write). This is the safer behavior vs grade_picks (H1).

**I9** — `mlb_stats_fetcher.py:~215-227` — IP parsing formula (`int(whole)*3 + int(frac)`) is correct for MLB inning notation (.1=1 out, .2=2 outs, never .3).

**I10** — `clv_report.py:~157` — SGP/Longshot/Daily Lay correctly excluded from CLV analysis (composite bets; individual leg CLV is not meaningful for single-market CLV comparisons).

---

## TOTAL: 0C / 12H / 25M / 10I

---

## KEY RESEARCH FINDINGS

**CLV methodology (Q1):** Vig-free CLV is the professional standard (Pinnacle, OddsJam, Pikkit). Vigged CLV (current) understates edge by approximately 50-100% of true vig-free value at typical -110/-115 line moves. Example: vigged CLV = +1.11pp; vig-free CLV = +2.17pp for the same line move. Systematic understatement, consistent across all picks — does not corrupt relative rankings but absolute numbers are meaningfully lower than professional benchmarks.

**T-10 capture (Q2):** No published source specifies a minute window. All say "as close to game time as possible." T-10 is acceptable; T-0 to T-5 is slightly more precise but not meaningfully different for CLV quality.

**DNP rules (Q3):** All major US sportsbooks (DraftKings, FanDuel, BetMGM) void props when a player does not play; SGPs may be voided entirely (BetMGM) vs repriced at reduced legs (FanDuel, DraftKings). Current VOID treatment in grade_picks.py is correct for single-game props.

**Platt scaling n=100 (Q4):** n=100 is at the lower workable boundary. Median estimates are stable but sampling distribution skews. n=200-300 provides more reliable confidence intervals. Current H3 gate is defensible but marginal.

**NB MLE vs MoM (Q5):** MLE is preferred for small n (<100 player-seasons); at deployed sample sizes (1200+ player-seasons) both methods converge. Current NB_R values are robust.

**Parlay push (Q6):** Pushed leg drops, parlay continues at reduced legs — confirmed industry standard for standard multi-game parlays. SGPs: BetMGM voids entire slip on any void; FanDuel/DraftKings reprice with leg removed.

**Win rate pushes (Q7):** Exclude from denominator — confirmed industry standard.

**WNBA data quality (Q8):** No systematic data integrity issues reported. Season-type parameter handling is the most common developer error; wnba_stats_fetcher.py explicitly handles this correctly.

---

## CROSS-MODULE ISSUES

**XM1 — CLV calculation divergence**: `capture_clv.py` (with zero-guard) and `clv_report.py` (without zero-guard) have diverged from a common ancestor. The zero-guard fix was applied only to one file. Same divergence risk exists for any future change to the `implied_prob()` function. Both files should import from a shared `engine/odds_utils.py`.

**XM2 — P&L scope mismatch (weekly_recap vs analyze_picks)**: `weekly_recap` reports primary+bonus only; `analyze_picks` reports all run_types. No filter in `analyze_picks` reproduces the `weekly_recap` scope. A user reconciling the two tools will find irreconcilable numbers. Every performance metric (win rate, ROI, P&L) differs systematically between the two reports with no disclaimer.

**XM3 — CLV unweighted mean across all three tools**: `clv_report.py`, `analyze_picks.py`, and `weekly_recap.py` all use simple unweighted CLV mean. This is internally consistent but all three underweight high-stakes picks in the bankroll edge calculation. A single formula change to a shared `compute_clv_mean(picks, stake_weighted=True)` utility would fix all three simultaneously.

**XM4 — Calibration deploy gap**: `calibrate_distributions.py` (EdgeModel) produces NB r and Normal parameters; `calibrate_platt.py` (EdgeModel) produces Platt A/B; `run_picks.py` (JonnyParlay) hard-codes all values. No automated comparison, no version stamp, no staleness detection. A developer re-running calibration in June 2026 with updated DB data has no automated path to know whether the deployed values in `run_picks.py` match the current DB. The `_CURRENT_PARAMS` dict in `calibrate_distributions.py` is a partial manual mirror that covers only NBA stats.

**XM5 — Log format inconsistency (file vs terminal)**: `engine_logger._FORMAT` includes `[%(name)s]`; `log_setup._DEFAULT_FORMAT` does not. File logs and terminal output differ. Any regex or parsing tool that uses module-name patterns (e.g., `grep '\[capture_clv\]'`) will match terminal output but fail on log files. Affects automated log monitoring.

**XM6 — name_key DRY violation (fetchers)**: `_name_key()` and `_fold_name()` are duplicated across `mlb_stats_fetcher.py`, `nhl_stats_fetcher.py`, and `wnba_stats_fetcher.py`. These functions are also used in `grade_picks.py` player matching and `name_utils.py`. A single authoritative definition in `name_utils.py` with imports in all three fetchers would eliminate the divergence risk.

---

## SCOPE NOTE

Files discovered in Step 0 but not read this session (JonnyParlay utility/diagnostic files):
`pick_log_io.py` (CSV locking — referenced but not audited), `nb_calibrate.py` (calibration helper),
`calibrate_sigma.py`, `calibrate_winprob.py`, `sgp_builder.py`, `mlb_sgp_builder.py`,
and 15+ diagnostic/backtest/report files. A future Module 5 should audit `pick_log_io.py` (CSV locking correctness),
`sgp_builder.py` + `mlb_sgp_builder.py` (Gaussian copula math), and `run_picks.py` (core distribution math, gates).

=== END MODULE 4 ===
