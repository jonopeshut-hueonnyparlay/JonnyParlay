# Projection System Deep Audit — 2026-05-06

Read-only deep audit of the JonnyParlay NBA projection chain (engine/nba_projector.py, projections_db.py, injury_parser.py, generate_projections.py, csv_writer.py, capture_clv.py, calibrate_*.py). Six parallel Explore agents covered scope A–P; constants and edge cases independently verified against code and `data/projections.db`.

## Summary

- **0 CRIT / 5 HIGH / 8 MED / 5 LOW / many CLEAN**

**Top-3 most concerning findings:**

1. **H1 — Vegas team-total constraint silently undoes 240-min lineup protection.** `constrain_team_totals()` scales `proj_min` plus every stat uniformly across the entire team (cores + bench). The 240-min constraint protects top-5 from being scaled down, then the Vegas constraint can scale stars down up to 20% (clip floor 0.80). Limited blast radius (clip), but the protection chain is logically inverted from intent.
2. **H2 — `cold_start_min_cap` clamps `injury_minutes_override`.** A cold_start player with an authoritative override (e.g., taxi rookie with announced 18-min restriction) is silently re-clamped to the sub-type cap (taxi=12) at `nba_projector.py:1130`. Comment at line 1151 explicitly states "override is authoritative" — the cap fires before the bump-skip guard. Rare but real edge case.
3. **H3 — Calibration contamination (R1 from Brief 7) still unresolved, no refit yet.** `over_p_raw` schema-v4 column added 2026-05-05 but pick_log starts now from zero with that column. Path forward is clear (300+ rows), but Platt constants will continue to be stale until the column is populated.

## Findings

### A. Pool & filters

- **A1 [CLEAN]** `get_all_active_players()` thresholds — `engine/projections_db.py:1222–1350`.
  - Season filter, `max_days_inactive` recency cutoff, H6 recent-min filter (≥5 MPG over last 3 stat-having games OR ≥25 MPG season fallback), and SCHED-row exclusion via `EXISTS (...)` all wired correctly.
  - Cold-start rookies with 0 games on season are excluded from active pool by design — they enter via `project_player()` cold_start branch once they have ≥1 game.
  - Sub-5-player teams: filter does not enforce a minimum (correct — playoff rosters are tight; 240-min constraint distributes among whoever passes).

### B. Role classification

- **B1 [CLEAN]** `classify_role()` window — `nba_projector.py:411–420`. `df.head(10)` + `recent["starter_flag"].mean()` for binary start_rate. Tiers: starter (≥0.60 start AND ≥26 MPG), sixth_man (≥20 MPG), rotation (≥12), spot (≥5), cold_start (<5).
- **B2 [MED]** Tier boundary thresholds undocumented basis — `nba_projector.py:416–420`. The cutoffs (26/20/12/5 MPG, 0.60 start_rate) carry no source comment; they appear inherited rather than empirically refit alongside the recent scalar work.
  - **Suggested:** add a comment with the calibration source or run a binned MAE-by-role check at next refit.
- **B3 [CLEAN]** Cold-start sub-type classification + day-threshold — `nba_projector.py:1046–1070`. Boundary at `days_since >= 180` (returner) is explicit; taxi/returner/new_acquisition caps wired correctly (12 / min(career,22) / min(career,28)).
- **B4 [LOW]** `MIN_GAMES_FOR_TIER = 10` strict-less-than — `nba_projector.py:1031`. A player with exactly 10 games on team is NOT cold_start. This is **working as designed** (10 games is enough data for `classify_role`); the prior-day audit reading is overaggressive. No action needed beyond a clarifying comment.
- **B5 [CLEAN]** `classify_role` uses no current-game lineup data. C1 (lineup integration) remains OPEN per `memory/project_minutes_deep_dive.md`.

### C. Minute projection (project_minutes + project_player)

- **C1 [CLEAN]** EWMA span — `nba_projector.py:96`, `EWMA_SPAN_MIN = 8` (raised from 6 in May 2026 accuracy overhaul). Bayesian weight ramp `min(len/20, 1.0)` (line 963) gives 25% recent / 75% prior at n=5 — sane.
- **C2 [CLEAN]** Days-rest reduction — `nba_projector.py:197–198, 924–940`. `DAYS_REST_MAX_REDUCTION=0.10`, `DAYS_REST_HALF_LIFE=1.5`, `exp(-days_rest/1.5)`. Edge cases: B2B = ~10% reduction × role_scalar; 5+ days = ~0% (full recovery).
- **C3 [CLEAN]** Blowout sigmoid (P1-A) — `nba_projector.py:184–186, 976–982`. `k=0.15, mid=20, max_red=0.19`. Verified at edges: spread=0 → reduction ≈ 0.009; spread=20 → ≈ 0.095; spread=60 → ≈ 0.189.
- **C4 [CLEAN]** ROLE_MAX_MIN final cap — `nba_projector.py:1157`. Applied after redistribution bump (line 1153). Order of operations correct.
- **C5 [CLEAN]** Q/GTD/P play_prob = 1.0 in both `_STATUS_MAP` (injury_parser.py) and `_PLAY_PROB` (nba_projector.py). Binary in/out design verified per `feedback_play_prob_binary.md`.
- **H2 [HIGH]** `cold_start_min_cap` clamps `injury_minutes_override` — `nba_projector.py:1121–1133`. The override path correctly skips PLAYOFF / RS scalars (line 1121 guard), but the cold_start cap at line 1130 has no `injury_minutes_override is None` guard. For a taxi cold_start player with override=18, `cold_start_min_cap=12` clamps proj_min to 12 — silently violating the documented "override is authoritative" contract (line 1151 comment).
  - **Evidence:** lines 1121, 1130, 1151–1152 — bump path is guarded, cap path is not.
  - **Reasoning:** rare scenario (cold_start + announced minutes restriction), but produces a silent under-projection. Test the path manually with a synthetic cold_start override case to confirm.
  - **Suggested fix (do not implement):** add `injury_minutes_override is None and` to the line 1130 condition.
- **M1 [MED]** Down-grade race condition — `engine/run_picks.py` and projection rerun path. If a player is downgraded O→Q (or upgraded) after `redistribute_minutes()` already wrote bumps, the bumps stay in `injury_minutes_redistrib_bumps`. Mitigated by `--late-run` (regenerates everything from scratch), but requires operator awareness.
- **M2 [MED]** `injury_minutes_override` legacy path role-promotion uses EWMA in re-fetch — `nba_projector.py:1095–1107`. Computes `ewma_baseline` separately for delta calculation; this is fine but is an isolated re-EWMA call (potential perf issue on large slates, not correctness).

### D. Stat rate models

- **D1 [CLEAN]** PTS via FGA decomposition (not the spec's `pts_per_min × usg × ts_pct`) — `nba_projector.py:1262–1282`. Player FGA = (USG/100) × team_FGA × min/48; pts = 2pa×fg2_pct×2 + 3pa×fg3_pct×3 + fta×ft_pct. Blended with per-min baseline at PTS_BLEND_ALPHA=0.50. USG clipped [5, 45].
- **D2 [CLEAN]** REB rate two-path — primary decomposition uses `_REB_PRIOR_N_OREB/DREB = 5`; baseline reb-rate path uses `_REB_RATE_PRIOR_N = 12` (cold_start fallback). Season-conditional priors `_REB_RATE_PRIOR_RS` / `_REB_RATE_PRIOR_PO` correctly switched on `is_playoff`.
- **D3 [CLEAN]** AST per-game-pace — line 631 uses `game_pace` denominator (B1-008 fix); projection basis matches at line 1340.
- **D4 [CLEAN]** FG3M matchup uses `fg3a` (attempts) — `nba_projector.py:1213–1216` + `team_def_splits` table contains both `fg3a` and `fg3m` rows (verified in DB; T2d carried).
- **D5 [CLEAN]** BLK / STL — separate variables (`_proj_poss_blk`, `_proj_poss_stl`); both currently use the same pace-elasticity 0.30 (intentional duality).
- **D6 [CLEAN]** TOV — per-possession basis explicitly documented. `proj_poss_tov = game_pace × proj_min / 48.0` with linear pace elasticity (no dampening — turnovers are possession-limited). Closes the open RB8 audit item.

### E. Scalars

- **E1 [CLEAN]** `REGULAR_SEASON_MINUTES_SCALAR` — current values starter=1.0534 / sixth_man=1.0139 / rotation=1.0327 / spot=1.5695 / cold_start=1.0034 (post 2026-05-05 refit). Spot floor max(_, 1.200) at line 1126.
- **E2 [CLEAN]** `REGULAR_SEASON_STAT_SCALAR` — pts=1.0019 / ast=1.0120 / reb=1.0264 / fg3m=1.0231 / blk=1.0608 / stl=1.0017 / tov=1.000 (post REB-prior refit; supersedes the values quoted in CLAUDE.md).
- **E3 [CLEAN]** `PLAYOFF_MINUTES_SCALAR` — H2 refit values starter=1.075 / sixth_man=0.960 / rotation=0.924 / spot=0.948 / cold_start=0.400.
- **E4 [LOW]** `PLAYOFF_MINUTES_SCALAR["cold_start"] = 0.400` is unreachable — `nba_projector.py:236–247`. Cold-start players go through the sub-type cap branch (lines 1058–1070) which dominates over the playoff scalar. The 0.400 entry is essentially dead. Keep for future-proofing or remove with a one-line note.
- **E5 [MED]** No documented "freeze" criterion for scalars. Refit cadence is implicit (after material code change to upstream rate or constraint logic). For audit hygiene, declare a frozen-vs-active list and freeze threshold (e.g., n_pairs ≥ X, |bias| ≤ Y).

### F. Constraints

- **H1 [HIGH]** Vegas team-total constraint undoes 240-min lineup protection — `engine/csv_writer.py:75–138` + `nba_projector.py:1556–1660` + `engine/generate_projections.py:63–73, 463–464`.
  - **Evidence:** 240-min constraint protects top-5 (lines 1619–1648). Then `constrain_team_totals()` is applied after (`generate_projections.py:464`) and scales every key in `_CONSTRAINT_SCALE_KEYS` — *including* `proj_min` — uniformly across all players (line 131). So a Vegas scale of 0.85 (within clip floor 0.80) cuts a 36-min star down to 30.6 min, undoing the protection.
  - **Reasoning:** clip [0.80, 1.20] limits damage, but stars routinely deflate by 5–15% when projection_pts > Vegas_total (e.g., LAL underdog with spread total disagreement). The lineup-protected design intent is partially nullified.
  - **Suggested fix (do not implement):** either (a) reorder so Vegas runs first then 240-min is the final arbiter, or (b) make `constrain_team_totals()` lineup-protected for `proj_min` (scale stats uniformly, scale `proj_min` only on bench, then re-renormalize stats). Option (b) is more invasive but matches the design intent.
- **F2 [CLEAN]** 240-min edge cases — sub-5-player team (no bench), all-starter team, total < TEAM_MIN_FLOOR (180) → constraint skipped via `total_min < TEAM_MIN_FLOOR or total_min <= TEAM_MIN_TARGET` guard (line 1613). Core-exceeds-240 fallback (line 1624) scales core proportionally + zeros bench. All paths handled.
- **F3 [CLEAN]** Vegas zero-denom guard (line 113), missing-team no-op (line 104), abs(scale-1) < 1e-4 short-circuit (line 128).
- **F4 [CLEAN]** `_derive_team_totals` math — `engine/generate_projections.py:237–296`. `home_total = (game_total - spread)/2`, `away_total = (game_total + spread)/2`, fallback to `game_total/2` when spread missing. Sign convention verified (spread < 0 = home favored).
- **F5 [LOW]** Asymmetric `_SCALE_KEYS` lists — 240-min constraint omits `proj_min` (handles separately at line 1644); Vegas constraint includes `proj_min`. Both correct as-written but stylistically inconsistent.
- **M3 [MED]** Silent no-op when both `implied_totals` and `spreads` fail — `engine/generate_projections.py:404–421`. Per-game warning fires when a single game lacks an implied total, but no top-level warning when *both* dictionaries are empty. On a full Odds-API blackout, projections proceed un-anchored to Vegas. Add explicit log: `if not implied_totals and not spreads: log.error("Odds API blackout — projections will not be anchored to Vegas totals")`.

### G. Uncertainty (dk_std)

- **G1 [CLEAN]** `DK_STD_COEFF = 0.35`, `DK_STD_FLOOR = {starter:4.0, sixth_man:4.0, rotation:3.5, spot:3.0, cold_start:3.0}`. `dk_std = max(proj_pts × 0.35, FLOOR.get(role, 3.0))` at line 1419. Persisted to projections table (col 31). Does not feed Platt directly.

### H. Pace

- **H4 [HIGH]** `LEAGUE_AVG_PACE = 100.22` is mislabeled in code/docs — `nba_projector.py:62` and CLAUDE.md.
  - **Evidence:** `team_season_stats` table avg pace by season: 2023-24 RS = 99.15, 2024-25 RS = 99.58, 2025-26 RS = 100.22. The constant value (100.22) matches **2025-26**, not "2024-25 full season" as the comment claims.
  - **Reasoning:** label is wrong; actual value is reasonable for current season. Could be that the constant was updated mid-season using partial 2025-26 data and mis-attributed. Risk: if anyone refits using 2024-25 historical data and assumes the constant matches, basis will be off by ~0.6%.
  - **Suggested fix:** correct the comment to "2025-26 season-to-date NBA pace" or recompute from 2024-25 official data and either accept the ~0.6 pt drop or document the choice.
- **H5 [CLEAN]** `LEAGUE_AVG_PACE_PO = 96.5` is now applied — `nba_projector.py:1179–1181`. Override bypassed when `implied_total > 0` to avoid double-discounting Vegas's playoff pricing (C3 fix).

### I. Home/away

- **I1 [CLEAN]** `_HOME_AWAY_DELTA` empirical values (R4 Brief 7) wired at `nba_projector.py:301–308`. Symmetric application (`sign = +1.0 if is_home else -1.0`) at lines 1390–1395. STL absent (delta < noise).

### J. Defensive matchup

- **J1 [CLEAN]** `compute_defensive_splits` — `MIN_SPLIT_GAMES = 5` filter (line 503), ratio clip [0.80, 1.20] at write time, double-clip at read time in `nba_projector.py:1203–1208, 1215–1216`.
- **J2 [CLEAN]** Position normalization via `_position_group()` — "G/F" → "G" via `startswith("G")`. Conservative but acceptable; multi-position handling is an open improvement candidate.
- **J3 [CLEAN]** T2d 3PM uses `fg3a` ratio for matchup factor (volume-only); player's own `fg3_pct` carries efficiency. Verified in DB: `team_def_splits.stat` distinct values include `fg3a` (T2d carried).

### K. Training-quality weights

- **K1 [CLEAN]** L4 vacancy weights — `compute_availability_weights()` at `nba_projector.py:473–551`. `_AVAIL_KEY_MPG_THRESHOLD = 12.0`, `MIN_AVAILABILITY_WEIGHT = 0.30`, per-game floor `1 - absent_mpg / key_baseline`.
- **K2 [CLEAN]** L6 blowout filter — `_BLOWOUT_MIN_VALID_GAMES = 12`. Blowout weight asymmetry (bench heavier-down than starters) at `_blowout_weight()`.
- **K3 [CLEAN]** Combined weight `max(MIN_AVAILABILITY_WEIGHT, w_l4 × w_l6)` floored at 0.30. Used in `compute_per_minute_rates` denominator + numerator.

### L. Persistence & DB

- **L1 [CLEAN]** `BEGIN IMMEDIATE` transaction scope — wraps the upsert loop correctly; `conn.commit()` at end.
- **L2 [MED]** `busy_timeout = 20000` (20s) calibration — `engine/projections_db.py:209`. Sufficient under typical CLV daemon contention but could fall short during peak playoff-evening bulk CLV writes. Calibration question, not a logic bug. Suggest 30000 if any timeout exceptions appear in logs.
- **L3 [CLEAN]** `upsert_projection` schema match — verified against DB `PRAGMA table_info(projections)`: 32 columns, 26 of which are touched by INSERT + ON CONFLICT update. No drift.
- **L4 [CLEAN]** Indexes — `idx_pgs_player`, `idx_pgs_pid_gid`, `idx_games_date/season`, `idx_proj_run/player`, `idx_tds`, `idx_tss`. Coverage adequate for current query patterns.
- **L5 [LOW]** `team_def_splits` — UNIQUE on (team_id, season, position_group, stat); only single-column indexes on (team_id, season). For full-table scans by stat alone, no index — but scan size is small (2160 rows). Non-issue at current scale.

### M. Integration seams

- **M4 [MED]** "11-min Odds API cache" — CLAUDE.md and audit notes describe an 11-min cache; no such cache exists in `engine/csv_writer.py` `_odds_api_get`. The cache likely lives in `engine/run_picks.py` (which has `--no-cache` flag), separate from the projection pipeline. The doc-vs-code seam is misleading; `--late-run` re-calls the API fresh.
  - **Suggested:** either implement a time-keyed cache in csv_writer for `--late-run` quota efficiency, or update CLAUDE.md to clarify which subsystem the cache belongs to.
- **M5 [CLEAN]** Retry / 429 handling — `_odds_api_get` retries once on Timeout / 5xx (3s), backs off 60s on 429, logs `X-Requests-Remaining`. `capture_clv.py` has its own quota-exhaustion logic with persistent reset timestamps.
- **M6 [CLEAN]** Injury parser robustness — `try/except` around `nbainjuries` import handles ImportError + JVMNotFoundException; falls back to previous-day report (commit fcf47e2); active-team filter retains. `_maybe_reverse_name` applied in `_normalise_report`.
- **M7 [CLEAN]** Manual override schema — `inactives_override.json` loaded at `_load_inactives_override`; takes precedence via `injury_statuses.update(_manual)`.
- **M8 [CLEAN]** CLV daemon shadow log — `CUSTOM_SHADOW_LOG = data/pick_log_custom.csv`; `ENABLE_CUSTOM_CLV = True`; appended to `log_paths` only when file exists. STALE marker via `_mark_picks_stale()`.
- **M9 [CLEAN]** CLV polling window — `CAPTURE_BEFORE_SECS = 2700` (T-45m), `CAPTURE_AFTER_SECS = 180` (T+3m), `CAPTURE_WRITE_BEFORE_SECS = 600`. STALE write triggered after `STALE_AFTER_SECS = 30 min`.
- **M10 [CLEAN]** Schema v4 / `over_p_raw` — pick_log canonical header has 29 cols; `recover_over_p()` prefers `over_p_raw` and falls back via direction recovery for legacy v1–v3 rows.

### N. Calibration & validation

- **N1 [CLEAN]** `calibrate_platt.py` — 5-fold CV with OOS Brier; `sys.exit(1)` on negative OOS improvement; `recover_over_p()` v4-aware.
- **N2 [CLEAN]** `calibrate_winprob.py` — same 5-fold CV pattern, same hard exit on negative improvement, low-N warning at n<50.
- **H3 [HIGH]** Calibration contamination (R1 Brief 7) — known double-calibration design flaw. `over_p_raw` schema-v4 column added 2026-05-05 but pick_log resets that column to populated only from May 5 forward. Refit needs ~300+ post-v4 rows. Until then, PLATT_A=1.4988, PLATT_B=-0.8102 remain on stale fit.
  - **Evidence:** `engine/calibrate_platt.py:54–84` (recovery logic with v4 fallback); CLAUDE.md R1 / Fix Pass 6.
  - **Reasoning:** acceptable interim, but the fix is gated on operational discipline (running shadow + live pick logging long enough to accumulate). No code defect; tracking item.
- **N3 [MED]** Shadow CLV pipeline integration — `--shadow` flag in `generate_projections.py` writes to `pick_log_custom.csv`; CLV daemon polls the file when present. The integration relies on `paths.py` `JONNYPARLAY_PICK_LOG` env var or direct write; auditor could not confirm with certainty that `run_picks.py` (when invoked with `--shadow`) actually writes to the custom log path. Suggest a one-line `log.info` at the shadow-write location to make this auditable in operation.

### O. Documentation & memory drift

- **O1 [MED]** CLAUDE.md `pick_log.csv` schema description — line ~173 documents "**28-column** header (schema_version=3, last col is `legs`)". Current code is `SCHEMA_VERSION=4`, 29 columns, last col is `over_p_raw`. RB8 IMMEDIATE 1 was implemented but doc was not updated.
- **O2 [LOW]** CLAUDE.md playoff-scalar section quotes Brief-7 R3 values (rotation 0.550, spot 0.350) — superseded by H2 refit on 2026-05-06 (rotation 0.924, spot 0.948). The H2 history is fully captured in `memory/project_minutes_deep_dive.md`; CLAUDE.md needs a short follow-up paragraph.
- **O3 [LOW]** CLAUDE.md `REGULAR_SEASON_STAT_SCALAR` documents pts=1.000 / ast=1.005 / reb=1.031 / fg3m=1.019 / blk=1.043. Code has pts=1.0019 / ast=1.0120 / reb=1.0264 / fg3m=1.0231 / blk=1.0608 (post REB-prior + EWMA-span refit). Doc snapshot is stale; numerical drift small.
- **O4 [LOW]** `memory/projects/custom-projection-engine.md` opens with "Fresh start — Apr 30 2026 — Previous build wiped." That milestone is now several weeks old and the project is fully built. Update the lead paragraph to reflect "completed May 2–6 2026 / shadow validation gating go-live".
- **O5 [CLEAN]** Verified in code (matches CLAUDE.md): `MIN_GAMES_FOR_TIER=10`, `LEAGUE_AVG_PACE=100.22` (label aside, value present), `LEAGUE_AVG_PACE_PO=96.5`, `EWMA_SPAN_MIN=8`, `_HOME_AWAY_DELTA` 6 stats, `DK_STD_FLOOR` 5-role dict, `SPORT_UNIT_CAP={"NBA":8.0,"NHL":5.0,...}`, G12 daily total cap, PLATT_A/PLATT_B constants, cold_start sub-type caps, `_REB_RATE_PRIOR` G/F/C empirical.

### P. Dead code / orphans

- **P1 [CLEAN]** `LEAGUE_AVG_PACE_PO` — read at `nba_projector.py:1180` (no longer dead after Brief 6 §7.6).
- **P2 [CLEAN]** `_REB_PRIOR_N_OREB/DREB` — used in decomposed REB path (lines 625–626).
- **P3 [CLEAN]** `MIN_DAILY_LAY_PROB`, `_proj_cache.clear()`, `_derive_team_totals` — all wired in.
- **P4 [LOW]** Diagnostic scripts (`diag_blowout_buckets.py`, `diag_h6_pool.py`, `diag_h6_backtest.py`, `analyze_playoff_scalars.py`, `_check_dvp.py`) sit in `engine/` alongside production code. They are intentional one-shots with `__main__` entries, but the layout obscures the production-vs-diagnostic line. Suggest moving to `engine/diagnostics/` (or `tools/`) at next housekeeping pass.
- **P5 [CLEAN]** `sabersim_backtest.py`, `historical_backtest.py`, `evaluate_projector.py` — all called from active paths or have CLI entry points used in calibration sessions. Not dead.
- **P6 [CLEAN]** Test fixtures (test_pick_log_atomic_write.py, test_pick_log_schema.py) updated to schema v4 (29 cols, `over_p_raw` last).

## Validated as correct

- Pool / filters: H6 recent-min logic, season filter, SCHED-row exclusion, sub-5-player team handling.
- Role classification: 10-game window, starter_flag.mean() boundary, cold_start sub-type day threshold.
- Minute projection: EWMA span, days-rest exponential decay, blowout sigmoid edges, ROLE_MAX_MIN ordering, override scalar bypass, redistribute_minutes 3-tuple return shape, binary play_prob 1.0 in both maps.
- Stat rates: PTS FGA decomposition + 0.50 blend, REB two-path (decomp k=5 / baseline k=12), season-conditional REB priors, AST per-game-pace denominator, FG3M fg3a-attempt matchup, BLK/STL separate variables, TOV per-possession.
- Scalars: REGULAR_SEASON minutes & stat values, PLAYOFF_MINUTES_SCALAR H2 values (with cold_start unreachable noted).
- Constraints: 240-min lineup-protected logic + edge cases, Vegas zero-denom guard, `_derive_team_totals` math.
- Uncertainty: `dk_std` formula + role floors.
- Pace: `LEAGUE_AVG_PACE_PO` correctly applied + bypassed under implied_total.
- Home/away: empirical deltas + symmetric application.
- Defensive matchup: MIN_SPLIT_GAMES=5, ratio clip, fg3a-volume vs fg3_pct-efficiency split.
- Persistence: BEGIN IMMEDIATE scope, schema match, FK + index coverage.
- Integration: retry/429, injury parser exception handling, manual override precedence, custom shadow-log file detection, STALE marker.
- Calibration: 5-fold CV + sys.exit on negative OOS improvement (Platt + win_prob), schema-v4 over_p_raw recovery.

## Recommendations

**Priority queue for next implementation session:**

1. **H1 (Vegas vs lineup protection):** decide policy — (a) reorder constraints (cheap), (b) make Vegas constraint lineup-protected for `proj_min` (matches design intent, ~30 lines), or (c) accept current behavior and document the trade-off in CLAUDE.md.
2. **H2 (override + cold_start cap):** add `injury_minutes_override is None and` guard to line 1130. Single-line change. Add a test for the cold_start-with-override path.
3. **H4 (LEAGUE_AVG_PACE label):** decide whether the constant should be 99.58 (true 2024-25) or 100.22 (current 2025-26 STD). Update the comment to match the chosen basis.
4. **O1 (CLAUDE.md schema doc):** update line ~173 to "29-column header (schema_version=4, last col is `over_p_raw`)". 30-second fix.
5. **M3 (Odds API blackout warning):** add a single warning when both `implied_totals` and `spreads` are empty.
6. **E5 (scalar freeze policy):** declare which scalars are frozen and which are eligible for refit; pin a freeze threshold (n_pairs, |bias|).

**Areas warranting deeper follow-up audits:**

- **Vegas constraint lineup protection (F):** simulate impact across May playoff dates and quantify how often top-5 minutes get scaled outside [0.95, 1.05]; that frames urgency of H1.
- **B2 (tier boundaries):** run a per-role MAE bucket to confirm 26/20/12/5 MPG cutoffs are not biasing any role's projections.
- **N3 (shadow CLV flow):** add observability before depending on accumulated CLV for the Platt refit.
- **E5 (scalar refit cadence):** establish a frozen vs active list; current ad-hoc refits invite drift between sessions.

**Operational notes:**

- `over_p_raw` accumulation (RB8 IMMEDIATE 1) is the single biggest unblocker for proper Platt calibration. Daily shadow run discipline is the gating dependency, not code.
- `--late-run` flag is the current mitigation for the down-grade race condition (M1); document this in the operator runbook if not already.
- No CRIT-tier issues found; the system is in good shape post Brief 7 + RB8 + minutes deep-dive sessions.
