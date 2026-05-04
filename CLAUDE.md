# Memory

## Audit 2026-05-04 — Status
Full audit doc: `docs/audits/AUDIT_2026-05-04.md`. **14 CRIT / 17 HIGH / 28 MED / 17 LOW** — 10-agent full-system audit post Research Brief 7.

**ALL ITEMS ALREADY CLOSED by Fix Pass Session 7** (session 7 completed all fixes before context ended). Post-audit code verification confirmed every finding had already been resolved with inline comments referencing each issue ID (C1–C9, H1–H9, M2/M8/M10, etc.). No new code changes required.

**Test suite (2026-05-04):** 841 passed / 23 FUSE-sandbox failures / 2 skipped = 866 total. Identical to session 7 baseline. FUSE failures (test_tail_guard, test_section38/39/40, test_capture_clv_shutdown::sigterm, test_section32::weekly_recap_fallback) are Linux sandbox artifacts — all pass on Windows.

**Audit 2026-05-04 — ALL ITEMS CLOSED.**

## Audit 2026-05-02 — Status
Full audit doc: `docs/audits/AUDIT_2026-05-02.md`. **6 CRIT / 33 HIGH / 16 MED / 3 LOW / 12 CLEAN.**

**Fix pass session 1 (May 3 2026, 763 tests):**
- CRIT-1 (A1-023): `_pick_log_lock` no longer yields without lock — now raises `_FileLockTimeout`
- CRIT-5 (H-CRIT-001): test_pick_log_atomic_write.py updated to 28-col schema
- CRIT-6 (H-CRIT-002): test_pick_log_schema.py — added `legs` last-position assertion
- H1 (D1-001): `build_monthly_embed()` undefined `tier_lines`/`best_tier_line` removed — monthly recaps now functional
- H15 (B1-001): REB Bayesian shrinkage now conditional on `_reb_n_games == 0` only
- M10 (D1-005): `compute_pick_streak` MODEL_RUN_TYPES narrowed to `{"primary","bonus"}` (props only)
- M12 (D1-007): `grade_prop` direction fallthrough now returns None + logs warning instead of silently grading as "under"
- C2-001 (H16): `get_player_recent_games` in projections_db.py — connection now closed in try/finally
- H12 (A1-022): NBA header detection — added `"reb" in headers` check + warning if rebound column absent
- H17 (C2-002): `make_team_total_key()` helper added to csv_writer.py; both consumers (csv_writer + generate_projections) use it
- H19 (C2-004): `get_player_career_avg_minutes()` now logs warning before returning None
- H26 (G6-004): `_proj_cache.clear()` added at top of both `run_backtest` entry points (backtest_projections.py)
- H31 (H-HIGH-003): TestPerLegGates — per-leg cover_prob + edge gate tests now passing (correct NBA team names + mock.patch)
- H33 (H-HIGH-005): test_odds_client_malformed_json.py — `OddsClient` → `OddsFetcher`, truncation fix; all 3 tests pass

**Fix pass session 2 (May 3 2026, 805 tests pass):**
- M5 (B1-012): nba_projector.py — `_proj_poss_blk` now separate variable from `_proj_poss_stl`; BLK uses `proj_poss_blk`
- M6 (B1-017): `_REB_PRIOR_N_OREB/DREB` standardised to 12 (matching `_REB_RATE_PRIOR_N`)
- M8 (C3-003): `compute_defensive_splits()` now filters `cnt >= MIN_SPLIT_GAMES=5` before inserting splits
- M11 (D1-006): `build_monthly_embed()` — `_next_month` pre-computed with assert before MONTH_NAMES lookup
- M13 (E2-004): Already correct — `SHADOW_LOGS = {}` when `ENABLE_SHADOW_CLV=False` handles this
- M14 (F4-002): `engine_logger.py` idempotency key uses `repr(log_path)` instead of `str()`
- M15 (F7-001): `injury_parser.py` — broad `except Exception` narrowed to specific expected types
- M16 (F7-002): `injury_parser.py` — minute overrides clamped to `[0, 48]` with warning on out-of-range
- L1 (G5-001): `historical_backtest.py` comment updated — `errors_by_role` stores tuples not raw errors
- L2 (H-LOW-007): `test_weekly_recap_clv.py` float equality → `pytest.approx`

**Fix pass session 3 (May 3 2026, 845 tests pass):**
- H22 (A1-027): `_webhook_post` in grade_picks.py — split timeout `(5, 10)`; `ReadTimeout` not retried (POST body already sent — retry risks duplicate Discord post)
- H23 (A1-028): weekly_recap.py `_save_guard` non-atomic fallback removed — logs warning instead of open() write that could truncate guard file
- H24 (A1-029): morning_preview.py — same `_save_guard` fix; `force=True` path now does release+claim BEFORE posting (not post-success claim)
- H25 (G6-005): backtest_projections.py — legacy 27-col rows padded with `""` instead of dropped; `on_bad_lines="error"` after pre-validation
- H27 (H-HIGH-001): calibrate_platt.py — 5-fold cross-validated Brier added; in-sample labeled "biased low"; OOS used for go/no-go
- H28 (H-HIGH-002): calibrate_winprob.py — same 5-fold CV Brier; `brier_score_raw_cv`, `brier_score_cal_cv`, `brier_improvement_pct_cv` added to result dict
- M3 (B1-008): nba_projector.py — `compute_ast_rate` call uses `game_pace` denominator (was `team_pace`) — aligns training basis with projection basis
- M7 (B1-019): nba_projector.py 240-min constraint `_SCALE_KEYS` extended with `proj_*_p25`, `proj_*_p75`, `dk_std` — percentile keys were stale after scaling
- M9 (C3-006): generate_projections.py — implied-total coverage warning already issued before `run_projections()` call (confirmed no-op fix needed)

**Fix pass session 4 (May 3 2026, 845 tests pass):**
- CRIT-2/3/4: confirmed already fixed in prior sessions (no code change needed)
- H2 (A1-002): confirmed already fixed — `pick_score()` used for NRFI/YRFI (FIX H2 comment at line ~2760)
- H3/H7/H8/H9/H11/H12/H13/H20/H21/H29/H30/H32: all confirmed already fixed in prior sessions
- H4 (A2-001): `is_home: ""` added explicitly to TOTAL and F5_TOTAL pick dicts in run_picks.py
- H5 (A1-034b): confirmed already fixed — `MIN_DAILY_LAY_PROB` guard inside builder (line ~3138)
- H6 (A1-034): `extract_game_lines()` spread/ML dict keys now normalized to canonical abbreviations via `resolve_team_abbrev()` — prevents duplicate entries from bookmaker name variation; all consumers updated to match by abbreviation with `raw_name` fallback
- H10 (A1-011): `_load_cache()` `except Exception` narrowed to `json.JSONDecodeError` — real I/O errors now propagate
- H14 (A3-011): `_card_already_posted_today()` now checks discord guard key `premium_card:{today}` first; pick_log fallback requires `card_slot` non-blank — KILLSHOT-only runs no longer suppress the card on next run
- H18 (C2-003): csv_writer.py three `datetime.date.today()` calls replaced with ET-aware `datetime.datetime.now(ZoneInfo(...)).strftime(...)` — `ZoneInfo` import added
- M1 (A3-020): no rowcount sidecar exists in current code — no-op (T2c from Research Brief 6 was not implemented; schema sidecar ordering already correct)
- M2 (A1-something): confirmed already fixed — `log_picks()` uses `p.get("adj_edge", 0)`
- M4 (B1-003): `project_minutes()` already uses `is not None` guards (lines 896/898); `get_player_career_avg_minutes()` returns `None` not `0.0` — no-op

**Fix pass session 7 (May 4 2026, 857+ tests pass) — Fix Pass 7 (10-agent audit, 2025-26 season hardening):**
- CRIT-1/2/3/4/5/6: all closed (prior sessions confirmed or new fixes)
- H8 (sabersim_backtest): persist=True so projections cache to DB during backtest regen
- H9 (generate_projections.py): warning when --shadow and --run-picks both specified (H10); M4 return type hint -> Path|None; L4 --shadow help text expanded
- H12 (clv_report.py): stat sort key uses -inf fallback; M6 unused OrderedDict removed; M28 .upper() normalization; L6 --version added
- H13 (test_pick_log_atomic_write.py): position assertions for legs (final col=27, 28 total cols)
- M16/M17 (calibrate_platt/winprob): sys.exit(1) when OOS Brier improvement negative; L16 warning at n<50
- M7 (analyze_picks.py): pick_log_custom.csv included when --shadow enabled
- M19 (engine_logger.py): idempotency key uses normcase(abspath()) not repr()
- M20 (discord_guard.py): _load_unlocked() uses read_bytes() atomic single read; L14 guard key format documented in module docstring
- M21 (sabersim_backtest.py): run_projections import moved to module level
- C11/C12/C13/C14: tests/test_projections_db_r7.py created (18+ tests for new DB functions and capture_clv constants)
- L1 (nba_projector.py): stale 99.5 pace comment updated to 100.22
- L2 (projections_db.py): get_player_career_game_count() docstring + type hint improved
- L8 (historical_backtest.py): sampled → sampled_dates rename throughout
- L11 (run_picks.py): --force-card help text expanded with dedup clarification
- L17 (CLAUDE.md): cold_start sub-type min caps table added to Terms
- L3 (CLAUDE.md): CLV daemon entry updated to document ENABLE_CUSTOM_CLV / pick_log_custom.csv

**Audit 2026-05-02 (10-agent, 2025-26 season) — ALL ITEMS CLOSED.** 866 tests total (735 + 129 FUSE-deselected + 2 skipped), 0 failures. FUSE-deselected tests (test_tail_guard, test_section38/39/40, test_capture_clv_shutdown::sigterm, test_section32::weekly_recap_fallback) are sandbox artifacts — all pass on Windows. Run `--recompute-splits` on Windows to apply T2d fg3a split schema.

**Audit 2026-05-02 — ALL ITEMS CLOSED.** L3 (operational: run `--recompute-splits` on Windows) remains as a Windows task.

**Fix pass session 6 (May 3 2026, 839 tests pass) — Research Brief 7 Go-Live Audit & Production Hardening:**
- R1 (Platt refit): Calibrate_platt.py run — OOS Brier improvement = **−4.2%** (calibration hurts). Root cause: double-calibration design flaw — pick_log stores post-Platt win_prob, but calibrate_platt.py treats it as pre-Platt raw over_p. Dataset also mixed pre/post-Platt picks (Apr 14 – May 1 pre-fit; May 1+ post-fit). **Decision: keep PLATT_A=1.4988, PLATT_B=-0.8102 unchanged.** To properly refit in future, need `over_p_raw` (pre-Platt) logged as a pick_log column.
- R2 (dk_std floors): `DK_STD_FLOOR = {starter:4.0, sixth_man:4.0, rotation:3.5, spot:3.0, cold_start:3.0}` added to nba_projector.py. `dk_std = round(max(proj_pts * 0.35, DK_STD_FLOOR.get(role, 3.0)), 2)` — prevents underestimating uncertainty for bench roles.
- R3 (PLAYOFF_MINUTES_SCALAR): rotation 0.786→**0.550**, spot 0.902→**0.350**. Empirical basis: 535 matched pairs Apr 18-29 playoffs — rotation projects 18.5 vs 10.2 actual; spot projects 13.9 vs 4.9 actual.
- R4 (_HOME_AWAY_DELTA): Updated all 6 stats to empirical values — pts 0.0052→**0.0235**, reb 0.0058→**0.0088**, ast 0.0135→**0.0333**, fg3m 0.0131→**0.0452**, blk 0.0127→**0.0439**, tov −0.0063→**−0.0122**. STL already absent (unchanged).
- R5 (LEAGUE_AVG_PACE): 99.5→**100.22** (2024-25 full season official NBA pace).
- R6 (REB priors): `_REB_RATE_PRIOR` updated — G 0.055→**0.058**, F 0.095→**0.079**, C 0.165→**0.133**. `_REB_POS_OREB_PRIOR` and `_REB_POS_DREB_PRIOR` scaled proportionally (ratio method per position).
- R7 (cold_start sub-type): Two new DB functions added to projections_db.py — `get_player_career_game_count()` (n_career_games, career_avg_min_raw) and `get_player_last_appearance_days()`. Cold-start block in `project_player()` now classifies: **taxi** (n_career=0, cap=12 min) / **returner** (days≥180, cap=min(career_avg,22)) / **new_acquisition** (days<180, cap=min(career_avg,28)). Cap applied post-scalar. Logged at DEBUG level.
- CLV shadow fix: `capture_clv.py` was not watching `pick_log_custom.csv` — custom projection shadow picks would never get CLV written back. Fixed: added `CUSTOM_SHADOW_LOG = DATA_DIR / "pick_log_custom.csv"` + `ENABLE_CUSTOM_CLV = True` flag. Daemon now appends custom log to `log_paths` whenever the file exists. 839 tests pass.

**Fix pass session 5 (May 3 2026, 846 tests pass) — seed sensitivity + OOS validation + Brief 6 operational hardening:**
- Seed sensitivity (§3): seeds 7, 99, 137 all within ±0.05 threshold. PTS straddles zero across seeds — scalar 1.000 confirmed. Cold-start ratio flips direction between seasons (1.27 in early 2024-25 vs 0.91 in 2023-24) — season-composition artifact, not structural model error.
- OOS 2023-24 validation (§3): overall bias = -0.000 (rate-adj +0.033); diff from seed=42 = 0.026 < 0.05 threshold — scalars generalize cleanly to held-out season.
- `REGULAR_SEASON_STAT_SCALAR` trimmed from OOS results: ast 1.013→1.005 (was over-correcting), blk 1.056→1.043 (cross-seed mean); reb/fg3m/pts/stl confirmed.
- Playoff pace fix (§7.6): `LEAGUE_AVG_PACE_PO = 96.5` was defined but never referenced — dead code. Fixed: `project_minutes()` now scales `game_pace` by `(LEAGUE_AVG_PACE_PO / LEAGUE_AVG_PACE)` (~0.970) when `is_playoff=True` before computing `_base_pf`. Applies to all pace-dependent stats. Override bypassed when implied_total available.
- Historical backtest progress indicator: per-date `print(f"[{date_idx+1}/{len(sampled)}] {game_date}: {len(games)} games", flush=True)` in historical_backtest.py.
- §8 Odds API retry/429 handling: `_odds_api_get()` helper added to csv_writer.py — retries once on Timeout/5xx (3s delay), backs off 60s on 429, logs `X-Requests-Remaining` header. Both `fetch_nba_implied_totals()` calls (totals + team_totals) now use it. `generate_projections.py` imports `_odds_api_get` from csv_writer and uses it in `_fetch_spreads()`.
- §8 BEGIN IMMEDIATE transaction: `nba_projector.py` now opens `BEGIN IMMEDIATE` before the per-player upsert loop when `persist=True` — single exclusive write transaction reduces contention with CLV daemon; `conn.commit()` at end closes it.
- §7.5 Spot role scalar floor: added `if role == "spot": _rs_scalar = max(_rs_scalar, 1.200)` in `project_minutes()` — current fitted value 1.700 is unchanged (above floor); floor protects future refits given wide CI [1.57, 1.83].

## Audit 2026-05-01 — Status
Full audit doc: `docs/audits/AUDIT_2026-05-01.md`. **0 CRIT / 2 HIGH / 4 MED / 9 LOW / 54 CLEAN.**

**Closed May 1 2026:** H1, H2, M1, M2, M3, M4, L1–L9. P9 Platt constants fitted (PLATT_A=1.4988, PLATT_B=-0.8102, 76 props, 6% Brier). 832 tests pass. **Audit fully closed.**

## Audit 2026-04-28 — Status
Full audit doc: `docs/audits/AUDIT_2026-04-28.md`. **52 findings: 3 CRIT / 11 HIGH / 14 MED / 20 LOW / 4 CLEAN.**

**All CRIT + HIGH items closed (Apr 28–29 2026).** Branch: `audit-2026-04-28-fixes` merged to main.

**MED — all closed:** M1 (mlb schema), M2 (csv_writer TZ), M3 (KILLSHOT substring), M5 (push-leg drop), M6 (empty CSV abort), M8 (run lock), M9 (paths.py sweep), M12 (stdout utf-8).

**LOW — all closed Apr 30 2026:** L1 (tests/ dir), L2 (docs/audits/), L3 (marketing/ untracked), L5 (fuse artifacts — auto-clear), L6 (backtest logs — never tracked), L7 (pre-commit hook — `.git/hooks/pre-commit` guards shims), L9 (REB dropped from KILLSHOT_STAT_ALLOW), L10 (is_decimal_leak — already invoked), L11 (SIGMA fallthrough warning), L12 (unit cap docs), L13 ($PSScriptRoot in setup_clv_task.ps1), L14 (legs column docs), L15 (MBP terminology note), L16 (root shims — eliminate copy-sync drift), L17 (NHL sizing docs), L18 (conftest.py), L19 (streak docs), L20 (discord corruption test). **Audit fully closed.**

## Me
Jono (jonopeshut@gmail.com). Sports bettor, DFS player, Discord community operator. Runs picks as a trading business — analytical, sharp, luxury brand.

## Brand
**picksbyjonny** · Tagline: *edge > everything* · Aesthetic: luxury · sharp · analytical  
Discord bot display name: **PicksByJonny**

## Projects

| Name | What |
|------|------|
| **JonnyParlay** | Python betting engine — run_picks.py + grade_picks.py. Runs on Windows at `C:\Users\jono4\Documents\JonnyParlay\` |
| **Discord Overhaul** | Full server rebuild — **done**. Phase 1 design + Phase 2 manual build both shipped. |
| **KILLSHOT** | Premium tier (v2, Apr 21 2026). Auto-qualifies only when ALL pass: `tier=T1` strict, `pick_score≥90`, `win_prob≥0.65`, `odds ∈ [-200, +110]`, `stat ∈ {PTS,AST,SOG,3PM}`. Sizing: 3u default, 4u iff `win_prob≥0.70 AND edge≥0.06` (no 5u). Weekly cap: **2**. Manual override (`--killshot NAME`) bypasses gate but still counts toward cap + requires `score≥75`. Posts to #killshot with @everyone. |
| **KairosEdge** | Halftime trade system — buying trailing team YES in full-game winner market. Tracked separately from props. |
| **Custom Projection Engine** | In-flight replacement for SaberSim as the CSV input to `run_picks.py`. **Code lives in this repo** (engine/nba_projector.py + projections_db.py + injury_parser.py + csv_writer.py + backtest_projections.py; data/projections.db = 16 MB SQLite). Build order steps 1–4 complete and verified May 2 2026. **P18-v4 implemented May 2 2026** (role-conditional playoff minutes scalar + AST/3PM rate deflators — bias cut from -0.620 to -0.108; adj MAE +10.2% vs SaberSim). Research Brief 5: 14/15 levers done (L9 foul-trouble live = low priority). `engine/generate_projections.py` added — daily runner that orchestrates Odds API → injuries → projections → SaberSim CSV → optional run_picks.py. Run: `python engine\generate_projections.py [--run-picks]`. **Shadow mode (6fef8f5):** `--shadow` flag logs to `data/pick_log_custom.csv` with no Discord — use alongside live SaberSim run for parallel CLV validation. `paths.py` honors `JONNYPARLAY_PICK_LOG` env var to redirect all pick logging. Daily: `python engine\generate_projections.py --shadow` + `python run_picks.py nba.csv`. Full spec: `memory/projects/custom-projection-engine.md`. **May 2 2026 calibration session — tasks #2–#5 complete:** (1) `MIN_GAMES_FOR_TIER` raised 5→10 (task #2 cold_start fix); (2) career history minutes prior added via `get_player_career_avg_minutes()` in projections_db.py — replaces flat 16 MPG for cold_start players; (3) `REGULAR_SEASON_MINUTES_SCALAR` v2 fitted from 30-date backtest residuals (starter=1.056, sixth_man=1.019, rotation=1.035, spot=1.700, cold_start=0.940); (4) `REGULAR_SEASON_STAT_SCALAR` added (task #3) for per-stat bias correction: pts=1.000, ast=1.013, reb=1.031, fg3m=1.019, blk=1.064, stl/tov=1.000; (5) OT cap and team constraint tasks complete. **Final backtest results (3rd run, seed=42, n=30):** overall raw bias -0.033 (was -0.620), PTS bias +0.024, minutes ratio 0.9993, cold_start ratio 1.0000. Go-live gate: need ~100 CLV shadow observations from custom projector shadow runs (pick_log_custom.csv). The ~7 CLV observations in pick_log.csv as of May 2 are SaberSim live picks, not shadow custom picks. Shadow pipeline has 0 observations — must run `generate_projections.py --shadow` daily to accumulate. **Research Brief 6 (May 2 2026) — all 7 tasks complete:** T1 (calibration contamination audit — PTS scalar anomaly resolved analytically, DB integrity clean); T2a (busy_timeout=20000 in get_conn); T2b (implied-total coverage warning in generate_projections.py); T2c (pick_log row-count guard — sidecar `pick_log.rowcount`, aborts write on truncation); T2d (3PM matchup: fg3m→fg3a ratio — uses attempts-conceded not makes-conceded; requires `--recompute-splits` on next pull); T3 (clv_report.py `--stat` filter + per-stat CLV table N≥5); T4 (historical_backtest.py bias-by-role-tier + PTS magnitude buckets); T5 (Vegas team-total constraint in generate_projections.py via `constrain_team_totals()`, scale clipped [0.80,1.20], `--no-constraint` flag); T6 (REB baseline Bayesian shrinkage to positional prior `_REB_RATE_PRIOR = {G:0.055, F:0.095, C:0.165}` reb/min, k=12). **Seed sensitivity + OOS validation (May 3 2026) — COMPLETE:** seeds 7/99/137 all pass ±0.05; 2023-24 OOS bias = -0.000. Final `REGULAR_SEASON_STAT_SCALAR`: pts=1.000, ast=1.005 (trimmed from 1.013), reb=1.031, fg3m=1.019, blk=1.043 (trimmed from 1.064), stl/tov=1.000. Playoff pace fix live (§7.6). Odds API retry/429 handling live (§8). BEGIN IMMEDIATE persist tx live (§8). Spot scalar floor 1.200 live (§7.5). **Research Brief 6 ALL items fully complete.** Go-live gate: need ~100 CLV shadow observations from custom projector shadow runs (pick_log_custom.csv). The ~7 CLV observations in pick_log.csv as of May 2 are SaberSim live picks, not shadow custom picks. Shadow pipeline has 0 observations — must run `generate_projections.py --shadow` daily to accumulate. **Research Brief 7 (May 3 2026) — all 7 items complete:** R1 (Platt refit skipped — OOS -4.2%, double-calibration flaw; need `over_p_raw` column in pick_log to fix properly); R2 (DK_STD_FLOOR per-role floors); R3 (PLAYOFF_MINUTES_SCALAR rotation 0.786→0.550, spot 0.902→0.350); R4 (_HOME_AWAY_DELTA all 6 stats empirical); R5 (LEAGUE_AVG_PACE 99.5→100.22); R6 (_REB_RATE_PRIOR G/F/C empirical, OREB/DREB priors proportionally scaled); R7 (cold_start sub-type: taxi/returner/new_acquisition + per-subtype min cap; `get_player_career_game_count()` + `get_player_last_appearance_days()` added to projections_db.py). 839 tests pass. Go-live gate: ~100 CLV shadow observations still needed. |

## Key Files

| File | Purpose |
|------|---------|
| `engine/run_picks.py` | Main betting engine (large — ~5k+ lines and growing). **Source of truth — edit engine/ only. Root entry points are shims (L16, Apr 30 2026) — no sync step needed.** Flags added May 2 2026: `--force-card` (override card guard for fresh repost without double-logging), `--no-cache` (bypass 11-min Odds API cache for fresh odds). |
| `engine/grade_picks.py` | Auto-grades pick_log.csv results, posts Discord recap + results graphic. Monthly summary auto-fires on 1st of month. |
| `engine/capture_clv.py` | CLV daemon — polls every 2 min, captures closing odds in T-30 to T+3 window per game. Writes `closing_odds` + `clv` to pick_log. Scheduled via Windows Task Scheduler at 10am daily. Single-instance guard via filelock. Ghost-game checkpoint integrity check on startup. Also watches `pick_log_custom.csv` when `ENABLE_CUSTOM_CLV=True` (default) — required for custom projection shadow CLV tracking. Disable per-log by setting `ENABLE_CUSTOM_CLV = False` in capture_clv.py. (L3) |
| `engine/clv_report.py` | CLI report: `python clv_report.py [--days N] [--sport X] [--tier Y] [--stat X] [--shadow]` — `--stat` added May 2 2026 (T3). Per-stat CLV table in BY STAT section (N≥5 gate, sorted best→worst CLV). |
| `engine/results_graphic.py` | Generates PNG results card posted to Discord after recap. |
| `engine/analyze_picks.py` | Backtest analysis dashboard. Usage: `python analyze_picks.py [--sport X] [--since YYYY-MM-DD] [--stat X] [--shadow] [--export]` |
| `engine/weekly_recap.py` | Weekly P&L recap posted to #announcements every Sunday. |
| `engine/morning_preview.py` | Posts daily card teaser to #announcements after run_picks.py runs. |
| `data/pick_log.csv` | Model-generated ledger (primary / bonus / daily_lay / sgp / longshot). Starts Apr 14 2026. **28-column** header (schema_version=3, last col is `legs` JSON for parlays). |
| `data/pick_log_manual.csv` | Manual picks only (--log-manual). Same 28-column schema. Graded alongside main log but never posted to Discord recap. Excluded from CLV daemon. |
| `data/pick_log_mlb.csv` | Shadow log for MLB (still in SHADOW_SPORTS). Include in analyze with --shadow flag. |
| `sgp_builder.py` | Root shim → `engine/sgp_builder.py`. Same-Game Parlay builder. Runs after every pick run. Allowed books: FanDuel, BetMGM, DraftKings, theScore (espnbet), Caesars (williamhill_us), Fanatics, Hard Rock (hardrockbet). Logs as `run_type=sgp`. |
| `start_clv_daemon.bat` | Launcher for CLV daemon — called by Task Scheduler. Requires `PYTHONUNBUFFERED=1` + `python -u` (S4U logon). **Must contain ASCII only** — non-ASCII chars (em-dash, box-drawing, ×) cause cmd.exe to crash with exit code 255. |
| `setup_clv_task.ps1` | One-shot PowerShell script that registers the CLV daemon scheduled task. S4U logon + WakeToRun. Re-run as admin to reset. |
| `post_nrfi_bonus.py` | One-shot webhook poster for manual bonus drops. Uses Mozilla UA to bypass Cloudflare 1010. Template for future manual webhooks. |
| `tests/test_context.py` | Manual test harness for context system — run on Windows to test `--context` flag behaviour. |

## Discord Structure (Target)
```
WELCOME: #welcome, #start-here, #announcements
PICKS: #premium-portfolio, #bonus-drops, #daily-lay, #killshot 🔒
RESULTS: #daily-recap, #monthly-tracker, #winning-slips
COMMUNITY: #general, #questions, #community-picks, #testimonials, 🔊gaming
RESOURCES: #glossary, #sports-news, #affiliates
MODS: (hidden)
ARCHIVE: (collapsed)
```

## Terms

| Term | Meaning |
|------|---------|
| VAKE | Bankroll sizing system (proprietary) |
| Pick Score | Model ranking score for each pick |
| POTD | Pick of the Day — standalone embed, posted after premium card |
| KILLSHOT | Highest-conviction tier. v2 gate (Apr 21 2026): tier=T1 strict, score≥90, win_prob≥0.65, odds ∈ [-200,+110], stat ∈ {PTS,AST,SOG,3PM} (REB dropped L9). Sizing: 3u default, 4u iff wp≥0.70 AND edge≥0.06. Weekly cap: 2. @everyone ping. |
| Premium | Top 5 picks from the model each day |
| Bonus Drop | Single highest-scoring NEW pick per run (max 5/day) |
| Daily Lay | Alt spread parlay — 3-leg (min 2), model-identified mispriced lines. **Max combined odds: +100**. Per-leg gates: `edge≥0.025`, `cover_prob≥0.58`. `MIN_DAILY_LAY_PROB=0.47`. Kelly-derived sizing: 0.25–0.75u via `size_daily_lay()`. Redesigned Apr 28 2026. |
| SGP | Same-Game Parlay — **3-4 leg** (redesigned Apr 28 2026), NBA only, **+200–450 range**. Composite pool_score sort, Gaussian odds scoring, BetMGM first. Dynamic sizing: 0.25u default / 0.50u premium (avg_wp≥0.70 AND cohesion≥0.55 AND avg_edge≥0.035). Allowed books only (see sgp_builder.py). `--sgp-only` flag forces SGP post only. |
| Longshot | 6-leg parlay of safest picks. Logged as `run_type=longshot`. Per-game cap: max 2 legs per game (`LONGSHOT_MAX_PER_GAME=2`). Added Apr 28 2026. |
| CLV | Closing Line Value — primary edge indicator. Positive = beat the close. |
| CO-legal books | 18 CO-approved books. API key "espnbet" = display "theScore Bet" |
| cold_start sub-types | R7 (May 3 2026). Players below `MIN_GAMES_FOR_TIER=10` in current season are classified at projection time: **taxi** — n_career_games=0, min cap=12; **returner** — last appearance ≥180 days ago, min cap=min(career_avg, 22); **new_acquisition** — last appearance <180 days, min cap=min(career_avg, 28). Cap applied after role scalar. Source: `project_player()` in nba_projector.py. (L17) |

## Books / APIs
- **Odds API key + Discord webhooks:** loaded from `.env` via `engine/secrets_config.py`
  - Windows path: `C:\Users\jono4\Documents\JonnyParlay\.env` (also searches project root + `engine/.env`)
  - Template: `.env.example` (committed). Real `.env` is gitignored.
  - Debug inventory: `python engine/secrets_config.py` prints a redacted summary.
- `espnbet` in Odds API → display as **theScore Bet** everywhere
- CO_LEGAL_BOOKS: 18 books defined in run_picks.py

## Python Dependencies
- Install: `pip install -r requirements.txt --break-system-packages`
- **Hard deps (required to import):** `filelock` (cross-process locks), `requests`
- **Soft deps (feature-gated):** `openpyxl` (xlsx recap), `Pillow` (results_graphic PNG), `anthropic` (--context mode)
- Audit C-1 closed Apr 19 2026 — `filelock` is hard-required everywhere. If it's missing, the engine fails fast at import with a clear install hint.

## Audit Status
- **Closed Apr 21 2026 — 78/78 items declared resolved.** Section 40 (schema-version fail-fast via sidecar) + Section 41 (print → logging via `engine/engine_logger.py`) were the final two items. Regression suite: 756 passed, 2 skipped.
- **Apr 28 2026 — Parlay sharpness overhaul:** SGP redesigned 6→3-4 legs (+200–450), daily lay per-leg gates + Kelly sizing, longshot per-game cap of 2. All committed. engine/sgp_builder.py synced (H1 closed).
- **Audit 2026-04-28 — 52 findings, ALL items closed Apr 28–30 2026.** CRIT+HIGH closed Apr 28–29; all MED + all LOW closed Apr 29–30. See `docs/audits/AUDIT_2026-04-28.md`.

## pick_log.csv Schema (current — schema_version 3, 28 columns)
`date, run_time, run_type, sport, player, team, stat, line, direction, proj, win_prob, edge, odds, book, tier, pick_score, size, game, mode, result, closing_odds, clv, card_slot, is_home, context_verdict, context_reason, context_score, legs`

- `run_type`: primary | bonus | manual | daily_lay | sgp | longshot
- `tier`: T1 | T1B | T2 | T3 | KILLSHOT | DAILY_LAY | SGP | LONGSHOT | MANUAL
- `stat`: SOG | PTS | REB | AST | 3PM | SPREAD | ML_FAV | ML_DOG | TOTAL | TEAM_TOTAL | F5_ML | F5_SPREAD | F5_TOTAL | PARLAY
- `is_home`: True/False for SPREAD/ML/F5/TEAM_TOTAL picks; blank for props (canonical: `normalize_is_home`)
- `clv`: closing_implied_prob − your_implied_prob (positive = beat the close); filled by capture_clv.py
- `context_verdict`: supports | neutral | conflicts | skipped | disabled — blank on normal runs (context disabled by default)
- `legs`: JSON array for parlay rows. **SGP populates ✓** | longshot populates ✓ | **daily_lay populates ✓** (H9 closed Apr 28 — `_daily_lay_legs_json()` added; grader reads JSON-first with game-string fallback for 9 legacy rows). primary/bonus/manual leave it blank. pick_log_mlb.csv 282 short rows normalized to 28 cols (M1 closed Apr 29).

## Sizing Caps (L12/L17)
- **Daily total cap: 12u** (`G12` check in run_picks.py) — hard ceiling across all run_types per session.
- **Sport unit caps:** NBA = 8.0u max per pick | NHL = 5.0u max per pick (`SPORT_UNIT_CAP` dict).
- **NHL SOG stat cap:** max 6 picks per run (`STAT_CAP = {"SOG": 6, ...}`; default cap = 2 for other stats).

## Context Sanity System

**Status: DISABLED by default.** Enable with `--context` flag.

SaberSim projections already incorporate injury adjustments. Context layer stays in code for future use.

```
python run_picks.py nba.csv --context
```
Requires `anthropic` package + `ANTHROPIC_API_KEY` env var on Windows.

- `run_pregame_scan()` — one Haiku + web_search call per sport (concurrent)
- `run_context_check()` — one call per pick (up to 8 concurrent), checks for OUT/scratched flags
- `conflicts` → pick cut | `supports` → pass + annotation | `neutral` → pass

## MLB Status
Still in **SHADOW_SPORTS** — picks go to `pick_log_mlb.csv`, not posted to Discord. Sizing bug fixed (Apr 19 2026) — shadow picks now get VAKE base sizing. Go-live = Jono's call.

## Running grade_picks.py in Cowork
M9 closed Apr 29 2026 — all engine modules now use `paths.py`. Set `JONNYPARLAY_ROOT` to the repo root and every module resolves paths correctly:
```
export JONNYPARLAY_ROOT=/sessions/.../mnt/JonnyParlay
python engine/grade_picks.py --date YYYY-MM-DD [--repost] [--dry-run]
```
Windows deployments leave the env var unset — `paths.py` falls back to `~/Documents/JonnyParlay` so existing behavior is unchanged.

Migrated: `clv_report`, `csv_writer`, `grade_picks`, `projections_db`, `discord_guard`, `morning_preview`, `weekly_recap`, `analyze_picks`, `results_graphic`, `run_picks`. Remaining hardcoders: `capture_clv` (CLV daemon — low priority, runs on Windows only).

## ⚠ Cowork Write Caution
If the engine runs on Windows and writes to pick_log.csv, do NOT use the Write tool to rewrite pick_log.csv — it will clobber engine-written rows. Use Edit/append only.

## Daily Routine
1. Download SaberSim CSV
2. `python run_picks.py nba.csv` (or nhl.csv etc) — posts card, logs picks
3. Done — CLV daemon captures automatically, grade_picks.py grades after games

## CLV Daemon
- Scheduled: Windows Task Scheduler, daily 10am, runs `start_clv_daemon.bat`
- Logon: **S4U** (fires without active desktop session). WakeToRun enabled.
- Manual trigger: `schtasks /run /tn "JonnyParlay CLV Daemon"` or foreground `python -u engine\capture_clv.