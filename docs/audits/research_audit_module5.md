# RESEARCH AUDIT — MODULE 5: COVERAGE GAPS
**Date:** 2026-05-31  
**Scope:** Every .py file in JonnyParlay + EdgeModel not covered by Modules 1-4  
**Status:** FINDINGS ONLY — no fixes applied

---

## STEP 0 — COMPLETE FILE INVENTORY

### JonnyParlay engine/ (41 files)
```
analyze_picks.py, analyze_playoff_scalars.py*, book_names.py, brand.py,
calibrate_sigma.py, calibrate_winprob.py, capture_clv.py, clv_report.py,
_check_dvp.py*, diagnostics.py, diag_blowout_buckets.py*, diag_h1_constraint_chain.py*,
diag_h6_backtest.py*, diag_h6_pool.py*, discord_guard.py, empirical_analysis.py,
engine_logger.py, evaluate_projector.py, export_pick_log_xlsx.py*, grade_picks.py,
historical_backtest.py, http_utils.py, io_utils.py, log_setup.py, mlb_sgp_builder.py,
mlb_starter_fetcher.py, month_names.py, name_utils.py, nb_calibrate.py, paths.py,
pick_labels.py, pick_log_io.py, pick_log_schema.py, projection_accuracy.py,
run_picks.py, sabersim_backtest.py, secrets_config.py, sgp_builder.py,
webhook_fallback.py, weekly_recap.py
```
*files marked * are in engine/tools/ subdirectory*

### JonnyParlay root/ (9 files)
```
analyze_picks.py (shim), capture_clv.py (shim), clv_report.py (shim),
conftest.py, grade_picks.py (shim), post_nrfi_bonus.py,
run_picks.py (shim), sgp_builder.py (shim), weekly_recap.py (shim)
```

### JonnyParlay tests/ (51 files — light audit only)

### EdgeModel engine/ (20 files — see Module 1 for full list)

---

## COVERAGE MAP

| File | Repo | Module Covered | Notes |
|------|------|---------------|-------|
| analyze_picks.py | JonnyParlay/engine | COVERED (M2, M4) | |
| analyze_playoff_scalars.py | JonnyParlay/engine/tools | **UNCOVERED** | Read M5 |
| book_names.py | JonnyParlay/engine | COVERED (M3) | |
| brand.py | JonnyParlay/engine | **UNCOVERED** | Read M5 |
| calibrate_sigma.py | JonnyParlay/engine | COVERED (M2) | |
| calibrate_winprob.py | JonnyParlay/engine | COVERED (M2) | |
| capture_clv.py | JonnyParlay/engine | COVERED (M3, M4) | |
| clv_report.py | JonnyParlay/engine | COVERED (M4) | |
| _check_dvp.py | JonnyParlay/engine/tools | **UNCOVERED** | Read M5 — trivial diagnostic |
| conftest.py | JonnyParlay/root | **UNCOVERED** | Read M5 — trivial path setup |
| diagnostics.py | JonnyParlay/engine | COVERED (M2, M4) | |
| diag_blowout_buckets.py | JonnyParlay/engine/tools | **UNCOVERED** | Read M5 |
| diag_h1_constraint_chain.py | JonnyParlay/engine/tools | **UNCOVERED** | Read M5 |
| diag_h6_backtest.py | JonnyParlay/engine/tools | **UNCOVERED** | Read M5 |
| diag_h6_pool.py | JonnyParlay/engine/tools | **UNCOVERED** | Read M5 |
| discord_guard.py | JonnyParlay/engine | **UNCOVERED** | Read M5 |
| empirical_analysis.py | JonnyParlay/engine | COVERED (M2) | |
| engine_logger.py | JonnyParlay/engine | COVERED (M4) | |
| evaluate_projector.py | JonnyParlay/engine | **UNCOVERED** | Read M5 |
| export_pick_log_xlsx.py | JonnyParlay/engine/tools | **UNCOVERED** | Read M5 |
| grade_picks.py | JonnyParlay/engine | COVERED (M2, M4) | |
| historical_backtest.py | JonnyParlay/engine | **UNCOVERED** | Read M5 |
| http_utils.py | JonnyParlay/engine | **UNCOVERED** | Read M5 |
| io_utils.py | JonnyParlay/engine | COVERED (M4) | |
| log_setup.py | JonnyParlay/engine | COVERED (M4) | |
| mlb_sgp_builder.py | JonnyParlay/engine | COVERED (M2, M3) | |
| mlb_starter_fetcher.py | JonnyParlay/engine | **UNCOVERED** | Read M5 |
| month_names.py | JonnyParlay/engine | **UNCOVERED** | Read M5 — trivial |
| name_utils.py | JonnyParlay/engine | **UNCOVERED** | Read M5 (distinct from EdgeModel copy) |
| nb_calibrate.py | JonnyParlay/engine | COVERED (M2) | |
| paths.py | JonnyParlay/engine | COVERED (M4) | |
| pick_labels.py | JonnyParlay/engine | **UNCOVERED** | Read M5 |
| pick_log_io.py | JonnyParlay/engine | **UNCOVERED** | Read M5 |
| pick_log_schema.py | JonnyParlay/engine | COVERED (M2, M4) | |
| post_nrfi_bonus.py | JonnyParlay/root | **UNCOVERED** | Read M5 |
| projection_accuracy.py | JonnyParlay/engine | **UNCOVERED** | Read M5 |
| run_picks.py | JonnyParlay/engine | COVERED (M2, M3) | |
| sabersim_backtest.py | JonnyParlay/engine | **UNCOVERED** | Read M5 |
| secrets_config.py | JonnyParlay/engine | **UNCOVERED** | Read M5 — read-only |
| sgp_builder.py | JonnyParlay/engine | COVERED (M2, M3) | |
| webhook_fallback.py | JonnyParlay/engine | **UNCOVERED** | Read M5 |
| weekly_recap.py | JonnyParlay/engine | COVERED (M4) | |
| EdgeModel/engine/backtest_projections.py | EdgeModel | COVERED (M1) | |
| EdgeModel/engine/calibrate_distributions.py | EdgeModel | COVERED (M1, M4) | |
| EdgeModel/engine/calibrate_platt.py | EdgeModel | COVERED (M1, M4) | |
| EdgeModel/engine/csv_writer.py | EdgeModel | COVERED (M1) | |
| EdgeModel/engine/diagnostics.py | EdgeModel | COVERED (M1, M4) | |
| EdgeModel/engine/engine_logger.py | EdgeModel | COVERED (M1, M4) | |
| EdgeModel/engine/generate_projections.py | EdgeModel | COVERED (M1) | |
| EdgeModel/engine/injury_parser.py | EdgeModel | COVERED (M1) | |
| EdgeModel/engine/io_utils.py | EdgeModel | COVERED (M1, M4) | |
| EdgeModel/engine/lineup_fetcher.py | EdgeModel | COVERED (M1) | |
| EdgeModel/engine/log_setup.py | EdgeModel | COVERED (M1, M4) | |
| EdgeModel/engine/mlb_stats_fetcher.py | EdgeModel | COVERED (M1, M4) | |
| EdgeModel/engine/name_utils.py | EdgeModel | COVERED (M1) | |
| EdgeModel/engine/nba_projector.py | EdgeModel | COVERED (M1) | |
| EdgeModel/engine/nhl_stats_fetcher.py | EdgeModel | COVERED (M1, M4) | |
| EdgeModel/engine/paths.py | EdgeModel | COVERED (M1, M4) | |
| EdgeModel/engine/projections_db.py | EdgeModel | COVERED (M1) | |
| EdgeModel/engine/secrets_config.py | EdgeModel | **UNCOVERED** | Read M5 — read-only |
| EdgeModel/engine/wnba_stats_fetcher.py | EdgeModel | COVERED (M1, M4) | |
| tests/*.py (51 files) | JonnyParlay/tests | **UNCOVERED** | Light audit — not audited at depth |

**Note on engine/tools/:** The engine/tools/ subdirectory was missed by all prior modules because the module instructions listed engine/ files only (not recursive). All 8 files in engine/tools/ are UNCOVERED. They are one-shot diagnostic/calibration CLIs per engine/tools/__init__.py ("Production code lives in engine/. Files in this directory are CLI scripts invoked manually.") — none are imported by production code.

---

## UNCOVERED FILES — FULL INVENTORY

### engine/pick_log_io.py (384 lines)
**Purpose:** Canonical locked CSV reader/writer for all pick_log files.  
**Key exports:** `read_rows_locked`, `read_rows_locked_if_exists`, `load_rows`, `pick_log_lock`, `SchemaVersionMismatchError`  
**Lock mechanism:** `filelock.FileLock` with 30s default timeout; fall-through on timeout with loud warning  
**Schema migration:** Applied on read by default via `migrate_row()`; `SchemaVersionMismatchError` raised if sidecar declares version > current  
**`load_rows` filters:** `run_types`, `exclude_run_types`, `sports`, `stats`, `tiers`, `date_equals`, `since`, `date_range`, `graded_only`; all AND semantics

### engine/discord_guard.py (288 lines)
**Purpose:** Cross-process FileLock dedup guard for Discord posting.  
**Guard file:** `data/discord_posted.json`  
**Key constants:** `GUARD_TTL_DAYS=90`, `LOCK_TIMEOUT_S=30`  
**Corruption recovery:** Regex scan of raw bytes for `"key": true` patterns when JSON parse fails  
**Public API:** `load_guard`, `save_guard`, `prune_guard`, `is_posted`, `mark_posted`, `claim_post` (preferred atomic test-and-set), `release_post`  
**Key guard formats:** `recap:YYYY-MM-DD`, `premium_card:YYYY-MM-DD`, `killshot:YYYY-MM-DD:Player:STAT:DIR:line`, `sgp:YYYY-MM-DD:Home vs Away`

### engine/webhook_fallback.py (161 lines)
**Purpose:** Optional secondary alert channel when primary Discord post fails.  
**Key constants:** `FALLBACK_TIMEOUT_SECS=4.0`, `MAX_CONTENT_LEN=400`  
**Activation:** Only fires when `DISCORD_FALLBACK_WEBHOOK` env var is set; silent no-op otherwise  
**Design:** Never raises; compact plain-text payload only

### engine/http_utils.py (140 lines)
**Purpose:** Shared UA + retry-after parser for all outbound HTTP.  
**`JONNYPARLAY_UA`:** `"Mozilla/5.0 (Windows NT 10.0; Win64; x64) JonnyParlay/1.0 (+https://picksbyjonny.com)"`  
**`retry_after_secs`:** Priority: HTTP header → JSON body `retry_after` → default. Clamped to `[0.5, 30.0]`  
**`default_headers(extra=None)`:** Returns `{"User-Agent": JONNYPARLAY_UA, ...extra}`

### engine/mlb_starter_fetcher.py (162 lines)
**Purpose:** Fetch probable MLB starting pitchers from statsapi.mlb.com.  
**API endpoint:** `https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={date}&hydrate=probablePitcher`  
**Team map:** `_TEAM_ID_TO_ABBREV` — 30 teams; OAK=133 (Athletics, still using OAK for SaberSim compat)  
**Return type:** `dict[abbrev, list[str]]` — list handles doubleheaders  
**Name matching:** `_name_key()` → `{last}_{first3}` (duplicates `name_utils.name_key`)

### engine/brand.py (43 lines)
**Purpose:** Single source of truth for brand constants.  
**Constants:** `BRAND_TAGLINE="edge > everything"`, `BRAND_HANDLE="picksbyjonny"`, `SPORT_EMOJI` dict (9 sports)  
**Design:** Zero side-effects, no third-party imports; safe to import from hot paths.

### engine/pick_labels.py (129 lines)
**Purpose:** Canonical pick-label formatters for Discord and backtest reports.  
**`GAME_LINE_STATS`:** `{TOTAL, SPREAD, TEAM_TOTAL, ML_FAV, ML_DOG, F5_TOTAL, F5_SPREAD, F5_ML, NRFI, YRFI, GOLF_WIN, PARLAY}` (must be superset of grade_picks.GAME_LINE_STATS)  
**`short_label(p)`:** Compact one-liner; uses last token of player name for props  
**`detail_line(p)`:** Long backtest format with odds

### engine/name_utils.py (93 lines)
**Purpose:** Canonical player-name folding for cross-source matching.  
**`fold_name`:** NFKD + ASCII + lowercase + strip `[^a-z\s]` + collapse whitespace  
**`name_key`:** `{last}_{first3}` after dropping Jr/Sr/II/III/IV/V suffixes  
**`_SUFFIXES`:** `frozenset({"jr", "sr", "ii", "iii", "iv", "v"})` — no trailing periods

### engine/month_names.py (59 lines)
**Purpose:** Locale-independent English month names.  
**Exports:** `MONTH_NAMES` (13-tuple, 1-indexed), `MONTH_NAMES_SHORT`, `month_name(month)`, `month_name_short(month)`

### engine/projection_accuracy.py (220 lines)
**Purpose:** Post-game projection accuracy CLI using stored projections vs box-score actuals.  
**`STAT_COLS`:** PTS, REB, AST, 3PM, BLK, STL (no TOV)  
**NewScalar formula:** `CurrScalar × (mean_proj - bias) / mean_proj`  
**Reports:** Per-stat MAE/bias/RMSE, minutes model, per-role breakdown, rolling 7/14/30-day PTS trend  
**Imports:** `get_projection_vs_actual` from projections_db, `REGULAR_SEASON_STAT_SCALAR` from nba_projector

### engine/historical_backtest.py (440 lines)
**Purpose:** Retrospective backtest on regular-season games using only pre-game data.  
**Sampling:** Stratified (not purely random) — divides season into n_dates buckets, picks one from each  
**Computes:** Per-stat MAE/bias/RMSE + NewScalar suggestions, role-tier bias breakdown (T4), PTS bias by projection magnitude, minutes analysis  
**Default season:** `"2024-25"` (stale)

### engine/evaluate_projector.py (727 lines)
**Purpose:** Direct DB evaluation with custom stat projectors vs per-minute baseline.  
**`RATE_MIN_MIN=20.0`:** Training history minimum-minutes filter (for PTS/REB/AST only)  
**Per-stat projectors:** `project_pts(alpha=PTS_BLEND_ALPHA)`, `project_3pm(alpha=0.50)`, `project_reb`, `project_ast`, `project_stl(min_min=8.0)`, `project_blk(min_min=8.0)`, `project_per_min`  
**`_pos_to_group`:** Returns G/F/C (OLD 3-group mapping — DB migrated to SG/SF/PF/C on 2026-05-10)  
**Alpha grid search:** Only for PTS, range [0.25, 0.70]

### engine/sabersim_backtest.py (380 lines)
**Purpose:** Full-slate SaberSim CSV vs custom projection comparison.  
**SaberSim cols:** PTS→"PTS", REB→"RB", AST→"AST", 3PM→"3PT"  
**Actuals filter:** `min >= 1` (permissive)  
**Season hardcoded:** `"2025-26"` in regen path  
**`detail_rows`:** Built but not returned in result dict; `--json` is summary-only

### engine/secrets_config.py (166 lines — JonnyParlay version)
**Purpose:** Centralized secrets loader from .env + env vars.  
**`.env` search order:** project root → engine/ → `~/Documents/JonnyParlay/`  
**JonnyParlay-only:** `EDGEMODEL_DB_PATH` (default: hardcoded user-specific Windows path)  
**Webhooks:** 10 webhook constants; `_WEBHOOK_REGISTRY` maps short names → (env_key, url)  
**Helpers:** `require_odds_api_key()`, `require_webhook(name)`, `summary()`

### post_nrfi_bonus.py (root, 190 lines)
**Purpose:** One-shot manual bonus pick poster for NRFI props.  
**Hardcoded pick data:** TOR @ ARI, NRFI under 0.5, +108, FanDuel, T2, 0.50u  
**Routing:** MLB → MAIN_LOG; WNBA → SHADOW_LOG; NRFI posted to Discord (MLB is live)  
**HTTP:** Uses `urllib.request` — no User-Agent header set  
**Guard:** `if __name__ != "post_nrfi_bonus": main()` (non-standard)

### engine/tools/__init__.py
**Purpose:** Documents engine/tools/ as non-production CLI scripts. All files are manually invoked diagnostics; none imported by production code (verified at move time per audit P4 2026-05-06).

### engine/tools/analyze_playoff_scalars.py (295 lines)
**Purpose:** H2 one-shot playoff minutes scalar refit analysis.  
**Output:** `data/diagnostics/playoff_baseline_data.csv` + `docs/research/playoff_scalar_refit.md`  
**Round heuristic:** `_DEEP_ROUND_DAY_THRESHOLD=30` days from playoff start (acknowledged as lazy)

### engine/tools/diag_blowout_buckets.py (149 lines)
**Purpose:** D2 blowout sigmoid recalibration tool.  
**Seasons hardcoded:** `('2024-25','2025-26')`  
**Fits:** `1 - max_reduction / (1 + exp(-k * (margin - mid)))` to bucket means via grid search

### engine/tools/diag_h1_constraint_chain.py (278 lines)
**Purpose:** H1 audit diagnostic for Vegas team-total constraint vs 240-min protection chain.

### engine/tools/diag_h6_backtest.py (109 lines)
**Purpose:** H6 filter backtest — validates no 15+ min player is excluded by pool filter.  
**Season hardcoded:** `"2025-26"`  
**Thresholds:** `REC_THRESHOLD=5.0`, `SEASON_THRESHOLD=25.0`

### engine/tools/diag_h6_pool.py (127 lines)
**Purpose:** H6 pool diagnostic — dumps candidate playoff pools and last-3-team-games appearance.

### engine/tools/export_pick_log_xlsx.py (456 lines)
**Purpose:** Export pick_log.csv to 8-sheet analytical Excel workbook.  
**Sheets:** Dashboard, Picks, By Tier, By Run Type, By Sport, By Stat, By Book, Daily P&L  
**Requires:** `openpyxl` (soft dep)  
**Shadow mode:** Reads `pick_log_custom.csv`; does NOT support `pick_log_wnba.csv`  
**P&L calc:** `pick_profit` = size × (decimal_odds - 1) for W; -size for L; 0 otherwise

### engine/tools/_check_dvp.py (30 lines)
**Purpose:** Trivial diagnostic — dumps `team_def_splits` avg/min/max ratio for PTS stat.

### EdgeModel/engine/secrets_config.py
**Purpose:** Same as JonnyParlay version minus `EDGEMODEL_DB_PATH`. Correct by design.

### conftest.py (root, 7 lines)
**Purpose:** Adds engine/ to sys.path for pytest. Standard pattern. No issues.

---

## FINDINGS

### CRITICAL (C) — 0

None identified.

---

### HIGH (H) — 4

**H1 — evaluate_projector.py:230–242 — `_pos_to_group()` uses stale G/F/C mapping after DB migrated to SG/SF/PF/C**

File: `engine/evaluate_projector.py`, lines 230–242  
```python
def _pos_to_group(position: str) -> str:
    p = (position or "").upper().strip()
    if p.startswith("G"): return "G"
    if p.startswith("C"): return "C"
    return "F"
```
The DB was migrated from G/F/C to PG/SG/SF/PF/C position groups on 2026-05-10 (CLAUDE.md note). `get_team_def_ratio(opp_team_id, pos_group, stat, season, db_path)` in `_compute_pts_components`, `project_ast`, `project_reb`, `project_stl`, `project_blk` all pass G/F/C position keys that no longer match any `team_def_splits.position_group` row. Result: matchup factors silently return default (1.0), disabling DvP adjustments for all evaluate_projector evaluations. The production `nba_projector.py` uses the correct 5-group mapping; evaluate_projector.py was not updated.

Evidence: CLAUDE.md 2026-05-10 entry: "all position groupings expanded from G/F/C → PG/SG/SF/PF/C."

Fix: Update `_pos_to_group` in evaluate_projector.py to match `nba_projector._pos_group()` (SG/SF/PF/C mapping).

---

**H2 — evaluate_projector.py:195 — `project_3pm(alpha=0.50)` hardcoded; no grid search path exists**

File: `engine/evaluate_projector.py`, line 195  
```python
def project_3pm(..., alpha: float = 0.50) -> float | None:
```
`run_alpha_grid_search()` (lines 574–660) only optimizes PTS — it hard-reads `row["pts"]` and `comps["fga_pts"]`/`comps["baseline_pts"]`. There is no `--stat 3PM` path in the grid search. The comment on `project_3pm` says "run --grid-search-alpha with stat=3PM to optimise" but that path doesn't exist. 3PM alpha has been uncalibrated at 0.50 since the evaluator was written.

Evidence: `run_alpha_grid_search` function body (lines 585–660) — only PTS arrays extracted.

Fix: Add 3PM-specific grid search branch (using `comps["fga_3pm"]`/`comps["baseline_3pm"]`), or document that 3PM alpha is intentionally unadjusted.

---

**H3 — post_nrfi_bonus.py:148–154 — Discord POST uses no User-Agent; CLAUDE.md states "Mozilla UA to bypass Cloudflare 1010"**

File: `post_nrfi_bonus.py`, lines 148–154  
```python
req = urllib.request.Request(
    _BONUS_WEBHOOK,
    data=payload,
    headers={"Content-Type": "application/json"},
    method="POST",
)
urllib.request.urlopen(req, timeout=10)
```
No `User-Agent` is set. `urllib.request` defaults to `"Python-urllib/3.x"`. CLAUDE.md says this file "Uses Mozilla UA to bypass Cloudflare 1010" and `http_utils.py` docstring explicitly names `post_nrfi_bonus.py` as the motivation for `JONNYPARLAY_UA`. The UA was never plumbed in. Any Discord webhook POST from this tool uses the default Python UA, which may trigger Cloudflare 1010 Access Denied.

Evidence: `http_utils.py` docstring: "post_nrfi_bonus.py where we had to work around Cloudflare's 1010 block."

Fix: Replace `urllib.request` with `requests.post(..., headers=default_headers({"Content-Type": "application/json"}))` from `http_utils`.

---

**H4 — discord_guard.py:94–95 — `prune_guard()` uses `ZoneInfo("America/New_York")`; fails on Linux/Docker without tzdata**

File: `engine/discord_guard.py`, lines 94–95  
```python
cutoff = (
    datetime.now(ZoneInfo("America/New_York")).replace(tzinfo=None)
    - timedelta(days=GUARD_TTL_DAYS)
)
```
`ZoneInfo("America/New_York")` raises `ZoneInfoNotFoundError` on Linux/Docker containers without the `python-tzdata` package installed. This crashes `prune_guard()` → `_save_unlocked()` → all guard writes fail. With no guard writes succeeding, the Discord dedup guard never persists and `run_picks.py` would repost the full premium card with `@everyone` on the next run.

Risk context: Low on Windows (primary production environment); **HIGH** in cowork/Linux sessions (grade_picks.py is run from cowork per CLAUDE.md).

Fix: Fallback to `datetime.utcnow()` when ZoneInfo raises, or use `timezone.utc` (always available). The TTL precision difference (UTC vs ET, up to ~5 hours) is irrelevant for a 90-day window.

---

### MEDIUM (M) — 21

**M1 — evaluate_projector.py:310,332 — STL/BLK use `min_min=8.0`; PTS/REB/AST use `RATE_MIN_MIN=20.0`**

STL (`project_stl`, line 310) and BLK (`project_blk`, line 332) filter training history to `min >= 8.0`. PTS/REB/AST all use `RATE_MIN_MIN=20.0`. The comment on `RATE_MIN_MIN` explains the 20-min floor eliminates "garbage-time rate bias" from foul-trouble/blowout appearances. STL/BLK training history at 8 min includes those garbage games. No documented reason for the lower threshold.

Fix: Align STL/BLK to `RATE_MIN_MIN=20.0` and re-evaluate whether the change improves MAE.

---

**M2 — evaluate_projector.py:308,330 — STL/BLK pass `season_filter=season`; PTS/REB/AST don't**

`project_stl` (line 308) and `project_blk` (line 330) call `get_player_recent_games(..., season_filter=season)`, restricting training history to the current season only. PTS/REB/AST projectors don't pass `season_filter`, using multi-season history. STL/BLK training samples are artificially smaller, especially early in the season.

Fix: Decide on a consistent policy (multi-season vs current-season) and apply uniformly.

---

**M3 — pick_labels.py:97 — `_SUFFIXES` uses trailing periods and is missing "v"; diverges from name_utils._SUFFIXES**

`pick_labels._SUFFIXES = {"jr.", "sr.", "ii", "iii", "iv"}` (with periods, no "v")  
`name_utils._SUFFIXES = frozenset({"jr", "sr", "ii", "iii", "iv", "v"})` (no periods, has "v")

If a player name in pick_log stores "Jr" without a trailing period (which fold_name produces), `last.lower() = "jr"` does NOT match `"jr."` in pick_labels — the suffix is not dropped and the label shows "JR" as the last name. Whether this fires depends on how names are stored in the CSV (SaberSim typically includes the period, fold_name strips it). Also "v" suffixes (quintas) are handled by name_utils but not pick_labels.

Fix: Align pick_labels._SUFFIXES to name_utils._SUFFIXES: remove periods, add "v".

---

**M4 — pick_labels.py:29 — `GAME_LINE_STATS` superset invariant is undocumented in tests**

The docstring documents: "Must stay a superset of `grade_picks.GAME_LINE_STATS`." If `grade_picks` adds a stat that `pick_labels` doesn't know, the grader handles it correctly but the label formatter produces garbled output. No test enforces this invariant — `test_section37_paths_labels_ghost.py` exists but its scope is unclear from filename alone.

Fix: Add a test that imports both sets and asserts `pick_labels.GAME_LINE_STATS >= grade_picks.GAME_LINE_STATS`.

---

**M5 — mlb_starter_fetcher.py:115 — `requests.get()` missing `headers=default_headers()`**

```python
resp = _req.get(url, timeout=10)
```
No User-Agent header. Every other engine HTTP call uses `http_utils.default_headers()`. MLB Stats API is generally permissive but the inconsistency means this is a maintenance landmine (if MLB adds UA filtering, this silently returns `{}` as if no starters were announced, and the SaberSim confirmation fallback takes over without log noise).

Fix: `resp = _req.get(url, timeout=10, headers=default_headers())`.

---

**M6 — mlb_starter_fetcher.py:83–91 — `_name_key()` duplicates name_utils.name_key logic**

`mlb_starter_fetcher._name_key()` re-implements last+first3 name key extraction that is already in `name_utils.name_key`. The `_norm_name()` helper already calls `fold_name` from name_utils when available. If `name_utils.name_key` changes (e.g., suffix logic), `mlb_starter_fetcher._name_key` diverges silently.

Fix: Replace `_name_key` with a direct call to `name_utils.name_key`.

---

**M7 — secrets_config.py:97–99 — `EDGEMODEL_DB_PATH` fallback hardcodes user-specific Windows path**

```python
EDGEMODEL_DB_PATH: str = os.getenv(
    "EDGEMODEL_DB_PATH",
    r"C:\Users\jono4\Documents\EdgeModel\data\projections.db"
)
```
Any machine other than Jono's (cowork Linux, CI, new Windows setup) that doesn't set `EDGEMODEL_DB_PATH` in .env gets a path that doesn't exist. Import-time read of this variable doesn't fail (it's just a string), but any code that uses it will silently fail at runtime.

Fix: Leave fallback blank (`""`) and let callers raise on empty value, or use a relative path.

---

**M8 — pick_log_io.py:368–372 — `pick_log_lock` timeout prints to stdout; other lock warnings use `_warn()` → stderr**

```python
# pick_log_lock context manager (line 368):
print(f"[pick_log_io] Could not acquire lock...")   # → stdout
# read_rows_locked lock timeout (line 183):
_warn(f"[pick_log_io] Could not acquire read lock...")  # → stderr via _warn()
```
Task Scheduler captures stdout and stderr separately. A lock timeout during a `pick_log_lock` compound RMW would appear in stdout (usually discarded) rather than stderr (captured as an error). The warning about CORRUPTION risk gets silently dropped.

Fix: Replace `print(...)` in `pick_log_lock`'s timeout handler with `_warn(...)`.

---

**M9 — webhook_fallback.py:28 — Docstring references deleted file morning_preview.py**

```python
Usage (from morning_preview / weekly_recap failure paths)::
```
`morning_preview.py` was deleted 2026-05-29. Stale documentation confuses future readers looking for callers.

Fix: Update docstring to remove `morning_preview` reference.

---

**M10 — http_utils.py:122 — Redundant isinstance check**

```python
if isinstance(body, MutableMapping) or isinstance(body, dict):
```
`dict` is a subclass of `MutableMapping`. The `or isinstance(body, dict)` clause is dead code.

Fix: `if isinstance(body, MutableMapping):` (already covers dict and any dict-like object).

---

**M11 — discord_guard.py:162–164 — Corruption warning uses `print()` instead of logger**

```python
print(
    "  [discord_guard] CORRUPT guard file AND failed to read raw bytes...",
    file=sys.stderr,
)
```
All other warnings in the same file also use `print()` rather than `logging`. Inconsistent with `engine_logger` pattern used throughout the engine. Corruption warnings should surface in the engine log file.

Fix: Replace with `log.error(...)` using a module-level logger.

---

**M12 — sabersim_backtest.py:218 — `season="2025-26"` hardcoded in regen path**

```python
projs = run_projections(
    game_date=game_date, season="2025-26", ...
)
```
If run on 2024-25 SaberSim CSVs (historical comparison), projection regen uses the wrong season string. The season should be inferred from the game_date or taken as a CLI argument.

Fix: Add `--season` argument, default to inferring from date range of CSV files.

---

**M13 — sabersim_backtest.py:105 — `min >= 1` actuals filter inflates SaberSim error metrics**

```python
WHERE g.game_date = ? AND pgs.min >= 1
```
Players with 1 minute played are included in the actuals set. SaberSim projects these as 0 (DNP). Including them inflates SaberSim's MAE for no analytical value. The projection engine also doesn't project these players.

Fix: Raise to `min >= 5` or `min >= 12` (matches historical_backtest.py's 5-min floor).

---

**M14 — sabersim_backtest.py — `detail_rows` built but not returned; `--json` is summary-only**

The per-player error list is accumulated in `detail_rows` (274 items) but `result` dict (lines 279–314) never includes it. `--json` output cannot be used for per-player analysis.

Fix: Add `"detail": detail_rows` to the result dict (gated behind a `--detail` flag to avoid huge output by default).

---

**M15 — historical_backtest.py:122 — Default `season="2024-25"` is stale**

```python
def run_historical_backtest(..., season: str = "2024-25", ...):
```
Current season is 2025-26. Direct calls without `--season` analyze last-season data. The CLI entry point correctly passes `CURRENT_SEASON` from nba_projector (line 422), but library callers get the wrong default.

Fix: Change default to `CURRENT_SEASON` (import from nba_projector).

---

**M16 — historical_backtest.py:172–174 — Progress line printed twice in verbose mode**

```python
print(f"[{date_idx+1}/{len(sampled_dates)}] {game_date}: ...")  # always prints
if verbose:
    print(f"\n[{date_idx+1}/{len(sampled_dates)}] {game_date}: ...")  # also prints in verbose
```
In verbose mode, the same progress line is printed twice per date.

Fix: Move the non-verbose print inside `if not verbose:`.

---

**M17 — historical_backtest.py:412–414 — Hardcoded April 2026 playoff benchmark in every RS backtest run**

```
"Reference benchmarks (from playoff backtest Apr 18-29 2026):"
"  Custom adj MAE: 3.436  |  SaberSim raw MAE: 3.254"
```
This benchmark was relevant when written. It will be incorrect once the model is retrained and appears in every regular-season backtest run regardless of context, potentially misleading.

Fix: Either remove it or gate it behind `--show-benchmark` flag.

---

**M18 — projection_accuracy.py:38–44 — `STAT_COLS` omits TOV**

TOV has a scalar in `REGULAR_SEASON_STAT_SCALAR` (`tov=1.000`) but is not in `STAT_COLS`. The tool cannot tell you if TOV is systematically mis-projected.

Fix: Add `("TOV", "tov", "proj_tov", "actual_tov")` to `STAT_COLS`.

---

**M19 — post_nrfi_bonus.py:185 — Non-standard `__main__` guard**

```python
if __name__ != "post_nrfi_bonus":
    main()
```
The conventional Python guard is `if __name__ == "__main__"`. This inverted form is equivalent in the normal import/run cases but also fires when `exec()`'d in a namespace where `__name__` is neither `"__main__"` nor `"post_nrfi_bonus"`. The comment says this is intentional for the test harness, but it's confusing for future maintainers.

Fix: Document the reason explicitly, or refactor the test harness to avoid `exec()` at the module level.

---

**M20 — post_nrfi_bonus.py — No CLI interface; hardcoded pick data requires file edits before each use**

All 13 pick-defining constants (`_AWAY_TEAM`, `_HOME_TEAM`, `_RAW_ODDS`, etc.) are hardcoded. Every manual bonus drop requires editing the source file. Risk: easy to run with stale data from a previous game (e.g., correct odds but wrong teams, or yesterday's game).

Fix: Add `argparse` CLI accepting `--away-team`, `--home-team`, `--odds`, `--stat`, `--line`, `--win-prob`, `--edge`. Keep hardcoded values as defaults for backward compat.

---

**M21 — historical_backtest.py:150–151 — `rng.uniform` upper-bound technically inclusive per Python docs**

```python
all_dates[int(rng.uniform(i * bucket_size, (i + 1) * bucket_size))]
```
`random.uniform(a, b)` is documented as returning N where `a <= N <= b` (inclusive). If `(i+1) * bucket_size == len(all_dates)` exactly and `rng.uniform` returns that value, `int(len(all_dates))` is an IndexError. CPython's implementation makes this practically impossible (uses `a + (b-a) * random()` where `random()` is `[0, 1)`), but it's not guaranteed.

Fix: Clamp the index: `min(int(rng.uniform(...)), len(all_dates) - 1)`.

---

### INFO (I)

**I1** — `engine/tools/__init__.py` documents that engine/tools/ contains only manually-invoked CLIs, none imported by production code (verified at audit P4 2026-05-06). Clean architecture boundary.

**I2** — `engine/tools/analyze_playoff_scalars.py:213` — Hardcoded `"Analysis date": 2026-05-06"` in report header. Stale when rerun. Minor UX issue only.

**I3** — `engine/tools/diag_blowout_buckets.py:52,61` — Hardcodes `seasons IN ('2024-25','2025-26')`. Needs manual update each new season. Same for `diag_h6_backtest.py SEASON = "2025-26"`.

**I4** — `engine/tools/export_pick_log_xlsx.py:33` — `SHADOW_IN = ROOT / "data" / "pick_log_custom.csv"`. The `--shadow` flag targets the custom projection shadow log, not `pick_log_wnba.csv`. WNBA picks cannot be exported to xlsx with this tool.

**I5** — `engine/tools/export_pick_log_xlsx.py` — `load_picks()` reads the CSV directly (not via `pick_log_io.read_rows_locked`). No FileLock. Acceptable for an offline analysis tool invoked manually, but if run while grade_picks.py is writing, could read a partial row set.

**I6** — `engine/name_utils.py` vs `EdgeModel/engine/name_utils.py` — Two separate copies in separate repos. Divergence risk if one is updated. Consider making EdgeModel the canonical source and JonnyParlay import from it (or symlink). Not actionable without repo reorganization.

**I7** — `engine/discord_guard.py:95` — `datetime.now(ZoneInfo(...)).replace(tzinfo=None)` strips timezone before comparison to naive datetime objects from `strptime`. Produces ~hour-level imprecision for pruning. Acceptable for a 90-day TTL window.

**I8** — `engine/http_utils.py:47–50` — `JONNYPARLAY_UA` includes `+https://picksbyjonny.com`. If this domain doesn't serve content, some servers may attempt a callback lookup and experience a timeout. In practice, the URL in a UA string is informational only and never fetched. No functional risk.

**I9** — `engine/pick_labels.py` — PARLAY short_label degrades to `"Daily Lay @ {odds}"` when player field is empty. Acceptable fallback.

**I10** — `engine/pick_log_io.py` — `CANONICAL_HEADER` is imported from `pick_log_schema` but is not in `__all__` and is not used within the file itself. It's accessible via `from pick_log_io import CANONICAL_HEADER` through Python's transitive import semantics, but this is not a formal re-export. No functional issue; minor interface confusion.

**I11** — `engine/tools/analyze_playoff_scalars.py:49–51` — `_DEEP_ROUND_DAY_THRESHOLD=30` is acknowledged as a "lazy heuristic" for round bucketing (early vs deep). For the purposes of the pooled scalar fit (what PLAYWRIGHT_MINUTES_SCALAR uses), the round breakdown is secondary. No functional impact on production constants.

**I12** — `engine/tools/diag_h6_pool.py` and `diag_h1_constraint_chain.py` — Both are one-shot audit diagnostics for specific findings (H1 Vegas constraint chain, H6 pool filter). If re-run today, they produce current-state output, not audit-time output. No production impact.

**I13** — `conftest.py` — 7-line standard pytest path setup. No issues.

---

## SUMMARY

```
TOTAL: 0C / 4H / 21M / 13I
```

### H-priority items ranked by production risk:
1. **H3** (post_nrfi_bonus UA) — live tool, every use today has wrong UA
2. **H4** (discord_guard ZoneInfo) — cowork Linux runs are live risk
3. **H1** (evaluate_projector pos_group) — silently disables DvP in all evaluations
4. **H2** (3PM alpha uncalibrated) — 3PM projector not tunable

### M-priority items most worth addressing first:
- **M3** (pick_labels suffix mismatch) — live label display bug potential
- **M8** (lock timeout stderr) — corruption warnings silently dropped to stdout
- **M5** (mlb_starter_fetcher UA) — production fetch without canonical UA
- **M12** (sabersim season hardcode) — wrong projections on historical runs
- **M15** (historical_backtest default season) — stale default in function sig

=== END MODULE 5 ===
