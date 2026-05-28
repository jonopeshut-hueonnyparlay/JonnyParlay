# Audit History — Closed Fix Pass Details

Archived from CLAUDE.md on 2026-05-09 to reduce context window usage.
All audits below are fully closed — no open items.

---

## Audit 2026-05-27 — run_picks / grade_picks / capture_clv / support files (2C/11H/10M)

Full docs: `docs/audits/audit_2026-05-27_run_picks_p1.md`, `audit_2026-05-27_run_picks_p2.md`, `audit_2026-05-27_grade_clv.md`, `audit_2026-05-27_support.md`

**CRITICAL (2) — all closed:**
- grade_picks.py `_mark_posted` fallback: key set before `_save_guard()` — commit `edb4ca2`
- run_picks.py `evaluate_game_lines`: `log.warning` → `logger.warning` — commit `edb4ca2`

**HIGH (11) — all closed:**
- run_picks.py: WNBA gate/dampener `datetime.now()` missing ZoneInfo (×2) — commit `827e984`
- run_picks.py: `log_candidates` naive datetime — commit `827e984`
- run_picks.py: R4/R11 shadow kills missing `pick_score` (set to None sentinel) — commit `827e984`
- run_picks.py: `_save_cache` silent except — commit `827e984`
- grade_picks.py: `pick_log_shadow_stats.csv` never graded — commit `827e984`
- grade_picks.py: NHL goalie stats (SV/GA) never fetched — commit `827e984`
- grade_picks.py: `_read_rows_locked` timeout fallback raises instead of lock-free read — commit `827e984`
- grade_picks.py: `pick_label` uses `.split()[-1]` on game-line picks — commit `827e984`
- capture_clv.py: `DATA_DIR`/`PICK_LOG` now from `paths.py` — commit `827e984`
- capture_clv.py: `calc_clv` TypeError on None implied_prob — commit `827e984`
- calibrate_distributions.py: K still listed as NB; `save_json()` not atomic — commit `eba1a2d`

**MEDIUM (10) — all closed:**
- run_picks.py: `extract_team_totals` Over/Under team-name guard — commit `52ca7fc`
- run_picks.py: TOTALS projection match uses `find_team_proj()` — commit `52ca7fc`
- grade_picks.py: 3× silent except → `logger.warning` (ESPN/MLB per-game) — commit `52ca7fc`
- grade_picks.py: historical bypass UTC → ET — commit `52ca7fc`
- capture_clv.py: ghost-game check excludes terminal results — commit `52ca7fc`
- weekly_recap.py: guard NameError on `force=True` path — commit `52ca7fc`
- analyze_picks.py: `--shadow` adds WNBA log — commit `52ca7fc`
- analyze_picks.py: `_PROP_STATS` adds 11 new stats — commit `52ca7fc`
- clv_report.py: sgp/longshot explicitly excluded from CLV — commit `52ca7fc`
- calibrate_distributions.py: K entry removed from `deployed_nb_r` — commit `eba1a2d`

**Deferred (~25L, several M) — all closed — commit `eada064`:**
- run_picks.py: T4 dead entries in VAKE_MULT; dead MLB SHADOW_LOG_PATHS entry; dead ABBREV_TO_NAMES dict; dead SIGMA["REC"]
- run_picks.py: KILLSHOT sanity check false-positive; run_type="gameline" invalid schema; SGP ImportError→Exception
- run_picks.py: bonus cap check post-VAKE sizing; today_str double-assignment; "Max 5 Positions" wrong text
- run_picks.py: _save_discord_guard TTL prune in fallback; log_candidates FileLock; _log_daily_lay silent return
- run_picks.py: NRFI/F5 matchup_abbrev substring → resolve_team_abbrev(); hardcoded "MST"; G14 comment scope
- run_picks.py: CSV parser debug log; run_type param on log_picks(); "No qualifying picks" shadow-aware message
- grade_picks.py: dead ALL_LOG_PATHS; dead suppress_ping param; docstring "manual" mismatch; _rt lambda default ""
- grade_picks.py: _game_is_complete sport guard; NBA scores for longshot/sgp only when needed
- capture_clv.py: picks_needing_clv run_type filter; closing_odds int normalization; fold_name for accented names
- capture_clv.py: game_str_matches ambiguous city fragments; quota header debug log; redundant math import; direction len guard
- sgp_builder.py: today_str=None warning; CLI reason string; dead MIN_DISTINCT_PLAYERS
- analyze_picks.py: avg_edge W/L only; clv_report.py: WNBA in SHADOW_LOGS
- pick_log_schema.py: "(v3)" → "(v4)"; calibrate_distributions.py: _CURRENT_PARAMS + docstring threshold
- secrets_config.py: .env.example template; tests/test_clv_date_key.py: closing_odds format assertions

---

## Audit 2026-05-06 — Projection Deep-Dive (0C/5H/8M/5L)

Full doc: `docs/audits/AUDIT_2026-05-06_projection_deep_dive.md`

**Fix batch 1 (2026-05-06):**
- H1: Vegas constraint now lineup-protected for `proj_min` (top-5 protected, bench absorbs scaling). Commits: `1c3a528` + `1fda742`.
- H2: `injury_minutes_override is None and` guard at `nba_projector.py:1130`. Commit: `e4911d9`.
- M3: `log.error` in `generate_projections.run()` when both `implied_totals` and `spreads` empty. Commit: `1d00c07`.
- H4: `LEAGUE_AVG_PACE`=100.22 is 2025-26 season-to-date (not 2024-25). Commit: `dceca67`.
- O1: pick_log schema doc updated to v4/29 cols. Commit: `da9b54b`.

**Fix batch 2 (doc-sweep):**
- B4: `MIN_GAMES_FOR_TIER` strict-less-than comment expanded. Commit: `540ea13`.
- E4: `PLAYOFF_MINUTES_SCALAR["cold_start"]=0.400` semantics comment corrected. Commit: `540ea13`.
- F5: `_SCALE_KEYS` cross-reference comments added. Commit: `def608d`.
- P4: 6 diagnostic scripts moved from `engine/` to `engine/tools/`. Commit: `6e4c878`.
- M4: CLAUDE.md `run_picks.py` cache clarification. Commit: `b2ddbd9`.

**Fix batch 3 (shadow-mode + remaining):**
- A1: `apply_caps()` wrapped in `if not getattr(args, "no_cap", False)`. Commit: `773a5d6`.
- A2: Shadow log dedup gated on `is_shadow_log = log_path.name != "pick_log.csv"`. Commit: `828fa72`.
- A3/N3: `logger.warning` at end of `log_picks` for zero-row writes. Commit: `46e3652`.
- B2: `classify_role()` docstring — 26/20/12/5 MPG cutoffs provenance noted. Commit: `33c8fdb`.
- E5: Scalar freeze policy doc at `docs/calibration/scalar-freeze-policy.md`. Commit: `c063589`.
- L2: `busy_timeout=20000` validation documented inline. Commit: `3f8b60e`.
- M1: Injury status change runbook at `docs/runbooks/injury-status-changes.md`. Commit: `d122160`.
- M2: Legacy-override re-EWMA closed wontfix-perf. Commit: `a4da963`.
- A4: `_card_guard_should_block_logging()` helper; bypass when `--no-discord` or `--force-card`. Commit: `30bcd4f`.

**Fix batch 4 (GLC matrix, 2026-05-07):**
- GLC-1: `filter_game_line_correlations()` — 4-rule matrix replacing narrow dedup. 13 tests.
- GLC-2: `warn_tt_divergence()` — `[TT-DIVERGE]` warning when proj diverges >0.25 from market. 8 tests.
- GLC-3: `print_thesis_block()` — pre/post GLC pick comparison. 8 tests.

Test progression: 903 → 919 → 941 → 941 → 951 → 955 → 984.

---

## Audit 2026-05-05 — Injury System + Deep Audit

- **C1 (injury name):** `_maybe_reverse_name()` added to `injury_parser.py`. Active-team filter in `get_injury_context()`.
- **H1:** Override scalar bypass — playoff/season scalar skipped when `injury_minutes_override` set.
- **H2:** USG% OT inflation — `tm_min.clip(upper=240.0)`.
- **H4:** SCHED collision — `seed_scheduled_games` checks for real row before inserting.
- **CLV fixes:** 5-tuple date-prefix write key, terminal-result exclusion, `_mark_picks_stale()` STALE marker.
- **Other:** `constrain_team_totals` in `generate_daily_csv`, KILLSHOT 12u cap, weekly_recap decimal CLV.
- Tests: test_clv_date_key.py (11), test_clv_stale_marker.py (3), test_injury_parser_fixes.py (13). Suite: 903/0.
- Commit: `fd97218`.

---

## Audit 2026-05-04 — 10-agent (14C/17H/28M/17L)

Full doc: `docs/audits/AUDIT_2026-05-04.md`. ALL ITEMS ALREADY CLOSED by Fix Pass Session 7.
Test suite: 853 passed / 21 FUSE-sandbox failures / 2 skipped.

---

## Audit 2026-05-02 — 10-agent season hardening (6C/33H/16M/3L)

Full doc: `docs/audits/AUDIT_2026-05-02.md`.

**Fix pass session 1 (763 tests):**
- CRIT-1: `_pick_log_lock` raises `_FileLockTimeout` instead of yielding without lock.
- H1: `build_monthly_embed()` undefined vars removed.
- H15: REB Bayesian shrinkage conditional on `_reb_n_games == 0` only.
- H19: `get_player_career_avg_minutes()` logs warning before returning None.
- H26: `_proj_cache.clear()` at top of both `run_backtest` entry points.
- H33: `OddsClient` → `OddsFetcher` in test_odds_client_malformed_json.py.

**Fix pass session 2 (805 tests):**
- M5: `_proj_poss_blk` separate from `_proj_poss_stl`; BLK uses `proj_poss_blk`.
- M8: `compute_defensive_splits()` filters `cnt >= MIN_SPLIT_GAMES=5`.
- M14: `engine_logger.py` idempotency key uses `repr(log_path)`.
- M15/M16: `injury_parser.py` exception narrowing + minute override clamp [0,48].

**Fix pass session 3 (845 tests):**
- H22: `_webhook_post` split timeout (5,10); `ReadTimeout` not retried.
- H27/H28: 5-fold CV Brier in `calibrate_platt.py` / `calibrate_winprob.py`.
- M3: `compute_ast_rate` uses `game_pace` denominator.
- M7: 240-min `_SCALE_KEYS` extended with `proj_*_p25`, `proj_*_p75`, `dk_std`.

**Fix pass session 4 (845 tests):**
- H4: `is_home: ""` added to TOTAL and F5_TOTAL dicts.
- H6: `extract_game_lines()` keys normalized via `resolve_team_abbrev()`.
- H14: `_card_already_posted_today()` checks discord guard key first.
- H18: csv_writer.py `datetime.date.today()` → ET-aware ZoneInfo calls.

**Fix pass sessions 5–7:** Seed sensitivity (seeds 7/99/137 pass ±0.05), OOS 2023-24 bias=-0.000, stat scalar trimming, playoff pace fix, Odds API retry/429, BEGIN IMMEDIATE persist tx, spot scalar floor 1.200. All items closed. 866 tests total.

---

## Audit 2026-05-01 (0C/2H/4M/9L)

H1, H2, M1–M4, L1–L9 all closed. Platt constants fitted (A=1.4988, B=−0.8102, 76 props, 6% Brier). 832 tests.

---

## Audit 2026-04-28 (3C/11H/14M/20L)

Full doc: `docs/audits/AUDIT_2026-04-28.md`. Branch `audit-2026-04-28-fixes` merged to main.
All CRIT+HIGH closed Apr 28–29. All MED+LOW closed Apr 29–30.

---

## Audit 2026-05-26 — Gate / Rule / Filter Audit (2C/5H/6M)

Full doc: `docs/audits/gate_audit_2026-05-26.md`
All items closed. Commit: `89c9605`.

**Critical:**
- C1: G13B dead code ahead of G_HRR_DISABLED — deleted G13B block.
- C2: `_is_soft_o05` referenced dead stats HRR/TB — changed to HITS-only.

**High:**
- H1: PICK_SCORE_TIER_MULT T1=0.90× may be stale — monitoring at n=30 T1 picks post-gate.
- H2: OUTS sigma min=3.0 too high vs typical 3–6 outs — recalibrated from 69k games to mult=0.311/min=1.0.
- H3: NB r for HA (pitcher hits allowed) was 12.0 (estimate) vs empirical 13.41 — updated; also moved HA from SIGMA to NB_STATS.
- H4: SV sigma uncalibrated — fitted from 15k goalie games: mult=0.253/min=3.5.
- H5: HIGH_VAR flag fires on 0-3PM games diluting bimodal signal — raised min_games threshold 5→8.

**Medium:**
- M1–M6: Gate recalibration checkpoints, TEAM_TOTAL cross-sport block scope, SIGMA drift, G8 directional gate coverage, K distribution confirmation, Platt refit gate tracking.

---

## Session 2026-05-27 — New Markets + Shadow System + NRFI Fix

Commits: `d198f15`, `db8ba0a`, `a3516b2`, `14e28b8`, `ba329fa`, `658f753`.

**New markets added:**
- NHL: GOALS (Poisson), NHLPTS (Poisson), NHLBLK (Poisson), SV (Normal σ mult=0.253/min=3.5), GA (Poisson)
- MLB: RBI (NB r=0.87), RUNS (Poisson), ER (NB r=2.62), BB (Poisson), PC (Normal σ mult=0.375/min=6.0)
- Re-enabled: TB (NB r=1.3 fallback; calc_tb_prob Poisson convolution is the rebuild), HRR (NB r=1.5), NRFI/YRFI (pitcher matching fixed)

**SHADOW_STATS system:**
- New `SHADOW_STATS` set gates all unvalidated markets — picks logged to `pick_log_shadow_stats.csv`, not posted publicly. Split from `qualified` pool AFTER `size_picks_base` but BEFORE `apply_caps`.
- New `SHADOW_GATE_CODES` set extracts direction/line-specific kills from `failed` pool for shadow logging (covers G8B/C/D, G_K_NO_UNDERS, G_K_MIN_LINE, G_TT_OVER_NBA, R4_REB_OVER, R4_REB_U25, R11_AST_U25).
- `apply_hard_rules` given `shadow_dest` param — R4/R11 kills routed to shadow instead of dropped.
- `get_tier` changed: REB over returns "T2" (was None/banned) so pick reaches `apply_hard_rules` for shadow routing.
- `paths.py` — added `PICK_LOG_SHADOW_STATS_PATH`.

**NRFI pitcher matching fix:**
- `pitcher_map` is keyed by SaberSim CSV abbreviations (NYY, LAD) but `game_lines` use full API names (New York Yankees). Old substring matching silently failed for ~15+ teams, producing biased 28.9% WR on 211 picks vs 70% base rate.
- Fixed `evaluate_nrfi` and `_team_runs` to use `resolve_team_abbrev()` before dict lookup.

**Go-live gate:** each stat in SHADOW_STATS needs n≥30 logged picks at ≥55% WR before promotion to live posting.

---

## Audit 2026-05-25 — Full System (12 Tracks, 2C/10H/23M)

Full docs: `docs/audits/audit_2026-05-25_track*.md`, `docs/audits/audit_2026-05-25_SUMMARY.md`.
All CRITICAL + HIGH + MEDIUM closed. ~25 LOW deferred.

**Critical:**
- C1: Platt formula space wrong in CLAUDE.md — corrected to raw-probability space (not logit). CLOSED 2026-05-25.
- C2: Mean CLV = −0.758%, beat rate 20.8% (n=53) — primary model calibration concern.

**Key highs closed:**
- H1 (G-3+G-4): sgp_builder NB_R["3PM"]=2.1 (should be 9.15) + AST Poisson (should be NB r=9.68) — synced 2026-05-25.
- H4: K distribution r=5.0 estimate — recalibrated from 69k games. var/mu=1.031 → Poisson confirmed; moved K from NB_STATS to POISSON_STATS.
- H5: HRR r=1.5 uses inferior moment-matching → shadowed pending proper calibration.
- H10: No calibrate_sigma.py — created calibrate_distributions.py covering all stats + sports.

**Other closures (same session):**
- AST → NB(r=9.68), 3PM r refit to 9.15, SIGMA["AST"] for combo path, pick_score adj_wp fix, TEAM_TOTAL over block (NBA), I6 wp fix. See CLAUDE.md Closed Audits table.

---

## Custom Projection Engine — Development Log

**Build order (Apr–May 2026):**
- Steps 1–4 complete May 2. P18-v4 (role-conditional playoff scalar + AST/3PM deflators): bias -0.620→-0.108.
- May 2 calibration: `MIN_GAMES_FOR_TIER` 5→10, career-minutes Bayesian prior, `REGULAR_SEASON_MINUTES_SCALAR` v2, `REGULAR_SEASON_STAT_SCALAR`, OT cap + team constraint.
- RB6: T2a busy_timeout, T2b coverage warning, T2c rowcount sidecar, T2d fg3m→fg3a splits, T3 clv_report --stat, T4 bias-by-role backtest, T5 Vegas constraint, T6 REB Bayesian prior.
- RB7: DK_STD_FLOOR per-role, PLAYOFF_MINUTES_SCALAR refit (rotation→0.550, spot→0.350), HOME_AWAY_DELTA empirical, LEAGUE_AVG_PACE 99.5→100.22, REB priors empirical, cold_start sub-types (taxi/returner/new_acquisition).
- RB8: over_p_raw col 29, Q injury prob 0.50→0.65, G14 projection clearance gate, max_days_inactive filter, lineup-protected 240-min constraint, P0-B override/bump split, PLAYOFF_MINUTES_SCALAR refit 2 (3925 pairs), H6 playoff pool filter, blowout sigmoid refit (24,600 rows), C1 lineup_fetcher, H1 role classification with lineup context, extended_absence cold_start sub-type, H5 high-var flag.
- Final 30-date RS backtest (seed=42): overall bias -0.033, PTS bias +0.024, minutes ratio 0.9993, cold_start ratio 1.0000.
