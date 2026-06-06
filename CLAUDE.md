# Memory

## Active Scalars — `engine/nba_projector.py`
- `PLAYOFF_MINUTES_SCALAR` (~line 242): starter=1.075, sixth_man=0.960, rotation=0.924, spot=0.948, cold_start=0.400. Refit 2026-05-06 on 3925 pairs (3 seasons).
- `REGULAR_SEASON_MINUTES_SCALAR` (~line 261): starter=1.0667, sixth_man=1.0462, rotation=1.0854, spot=1.6124, cold_start=1.0880. Refit 2026-05-10 (4653 player-games, 30-date RS backtest, overall ratio 1.0365).
- `REGULAR_SEASON_STAT_SCALAR` (~line 276): pts=1.0019, ast=1.0120, reb=1.0264, fg3m=1.0231, blk=1.0608, stl=1.0017, tov=1.000.
- `LEAGUE_AVG_PACE`=100.22 (2025-26 season-to-date; 2024-25 RS=99.58). `LEAGUE_AVG_PACE_PO`=96.5.
- `_HOME_AWAY_DELTA`: pts=0.0235, reb=0.0088, ast=0.0333, fg3m=0.0452, blk=0.0439, tov=−0.0122.
- `_REB_RATE_PRIOR` (PO): PG=0.056, SG=0.060, SF=0.066, PF=0.092, C=0.133. RS: PG=0.053, SG=0.057, SF=0.079, PF=0.111, C=0.165. Split 2026-05-10 from G/F/C using StatMuse per-36 ratios.
- `DK_STD_FLOOR`: starter=4.0, sixth_man=4.0, rotation=3.5, spot=3.0, cold_start=3.0. `DK_STD_COEFF`=0.35.
- `HIGH_VAR_CV_THRESHOLD`=0.60, `HIGH_VAR_MIN_GAMES`=8 (3PT specialist bimodal flag, RB8 H5).
- Blowout sigmoid: k=0.15, mid=20.0, max_reduction=0.19 (refit 2026-05-06 on 24,600 rows).
- `PLAYOFF_RATE_DEFLATORS`: pts=0.934, ast=0.845, fg3m=0.948, blk=1.152. Refit 2026-05-10 from 20-date playoff backtest (1071 player-games, Apr 18–May 8 2026). PTS added (was missing, +0.791 over-projection). AST/fg3m updated from stale n=43. BLK added as inflator (under-projected -0.074, t=-2.74; more half-court defense in playoffs). Post-fix biases: PTS −0.007, AST −0.006, FG3M +0.003 (all ≈0); BLK update pending C01 gate (per-possession analysis).
- `PLATT_A`=1.4988, `PLATT_B`=−0.8102 — **frozen** until H3 gate. Formula: `sigmoid(A * over_p + B)` (**raw-probability space — NOT logit-space**). `PLATT_SPACE="raw"` safeguard constant in run_picks.py asserts formula space matches; change to `"logit"` simultaneously with formula+A/B at H3. At H3, ALL THREE change simultaneously from calibrate_platt.py output.
- `NB_R` (run_picks.py): `3PM`=9.15 (1246 player-seasons, var/mu=1.1486); `AST`=12.16 (582 players/69773 game-logs, var/mu=1.3234 — game-level refit 2026-05-30, was 9.68); `REB`=14.7 (582 players/69773 game-logs, var/mu=1.3873 — game-level refit 2026-05-30, was 10.18); `HA`=13.41 (69k pitcher games, var/mu=1.204 — confirmed 2026-05-30 EdgeModel); `RBI`=0.87 (169k batter games, var/mu=1.535 — heavy zero-inflation ~74% games 0-RBI); `ER`=2.62 (69k pitcher games, var/mu=1.700 — bullpen/run-support tails); `HRR`=1.5 (moment-matched shadow log). STL/BLK/TOV Poisson confirmed (var/mu=1.072/1.113/1.050).
- `NB_R_WNBA` (run_picks.py): `AST`=11.37, `REB`=10.74, `3PM`=1.340. AST/REB calibrated 2026-06-04 from 202 players / 13,322 WNBA game-logs (2023–2026 RS, min≥8). 3PM calibrated 2026-06-05 from 13,725 rows (min≥8), var/mu=1.709, zero_rate=0.503 — WNBA 3PM is heavily overdispersed (vs NBA r=9.15) due to ~50% zero games.
- `COMBO_RHO_WNBA` (run_picks.py): PTS-REB=0.294, PTS-AST=0.188, REB-AST=0.200. Refit 2026-06-04 from 202 players / 13,322 game-logs (SE≈0.009). ~0.04–0.05 below NBA equivalents; consistent with lower WNBA pace/usage variance.
- `SIGMA_WNBA` (run_picks.py): `PTS`=mult 0.48/min 3.5; `AST`=mult 0.65/min 1.0; `REB`=mult 0.54/min 1.0; `3PM`=mult 0.48/min 0.70 (z-score/combo path only — 3PM props use NB path). Recalibrated 2026-06-05 (Plan 6 §1C) on the **priced population** (min≥20, 153 players, 2023–2026 RS) — the prior min≥8 frame (0.618/0.779/0.633) was a sampling artifact (median player 7.2 PPG, never priced). Used for G14 z-score proxy and combo sigma calculations.
- `WNBA_EDGE_FLOOR`=0.035 (run_picks.py) — compensates for wider WNBA vig (~-115/-115 vs -110). `WNBA_EARLY_SEASON_EDGE_MULT`: days 4–14 ×0.80; days 15–21 ×0.90; days 1–3 no picks (`WNBA_OPENING_GATE_DAYS`=3). `WNBA_SEASON_START`=2026-05-13 (update each season).
- `SIGMA` (run_picks.py): `PTS`=mult 0.35/min 5.0; `REB`=mult 0.48/min 2.0 (combo path only); `AST`=mult 0.53/min 2.0 (combo path only); `OUTS`=mult 0.27/min 1.0; `PC`=mult 0.19/min 6.0 (both recalibrated 2026-06-05, Plan 6 §1C, **starts-only** — is_starter=1, 16,187 starts; prior 0.311/0.375 were contaminated by relief appearances. Within-CV starts-only 0.228/0.142, pooled-start 0.276/0.204. PC skew −1.93 — Normal provisional, empirical-CDF candidate at July refit); `SV`=mult 0.253/min 3.5 (NHL goalie saves, calibrated 2026-05-26 from 15k goalie games). `HA` removed from SIGMA — now NB_STATS (r=13.41). Note: `MIN_LEG_WIN_PROB_OUTS=0.62` in mlb_sgp_builder was tuned to the old 0.311 sigma — narrower sigma raises OUTS leg win_probs; monitor SGP leg counts before retuning.
- `GAME_SIGMA["WNBA"]` (run_picks.py): `total`=17.459, `team`=11.271 (spread/ml unchanged at 10.0 — no active WNBA spread/ML picks). Calibrated 2026-06-05 from 837 reconstructed games (wnba_player_game_stats, EdgeModel db). Prior values total=10.0/team=7.5 were placeholders.
- `GAME_SIGMA["NHL"]` (run_picks.py): `total`=2.311, `spread`=2.614, `team`=1.744, `ml`=2.614. Calibrated 2026-06-05 from 3936 games (2023-24 + 2024-25). Prior values (total=1.2, spread=1.5, ml=4.0) were wrong by ~2x. ml=spread because P(win)=P(margin>0) under same goal-differential distribution.
- `MLB_TEAM_RUN_R`=3.548 (run_picks.py ~line 524): NB dispersion for MLB team run-scoring. Calibrated 2026-06-05 from 8095 regular-season games (var/mu=2.261). Used for team-total NB CDF and ML NB direct sum (`mlb_ml_from_nb()`). MLB HITS/BB/RUNS remain Poisson — within-player var/mu all near 1.0 (0.89/0.97/0.97); no overdispersion.
- `F5_SIGMA` (run_picks.py): `total`=2.65, `spread`=2.70, `team`=2.10. Tuned 2026-05-29 (was total=2.6/spread=2.75/team=2.0).
- **F5 scalar**: 0.540 (all three paths — total, ML, spread). Updated 2026-05-29 from 0.503 (was ~3-5pp too low; 0.540 is market-calibrated from 2022-2025 F5 lines). SaberSim team totals are already park-adjusted so no additional park multiplier is applied.
- **NRFI/YRFI model** (run_picks.py `evaluate_nrfi()`): Rewritten 2026-05-29 to Poisson λ model. `BASE_LAMBDA_1ST=0.32` (first-inning specific, calibrated so avg matchup → ~53% P(NRFI); was `BASE_SCORING_RATE=0.1633` which was miscalibrated against a misinterpreted 70% baseline). `_LEAGUE_AVG_BLENDED_RATE=0.477` (0.40×ERA/9 + 0.60×FIP/9, league avg). Formula: `λ_team = 0.32 × (pitcher_blended_rate / 0.477) × (team_runs / 4.45)`; `P(NRFI) = e^(-λ_away - λ_home)`. Park factor intentionally omitted — SaberSim saber_team projections already park-adjusted.
- `MLB_PARK_FACTORS` dict added to run_picks.py (keyed by home team abbrev, source: Baseball Savant 2022-2025). Not currently applied to projections (park effects already embedded in SaberSim inputs). Available for future park-neutral input paths.
- `KELLY_FRACTION`=6.0 (run_picks.py) — continuous Kelly sizing, replaces VAKE step function. Shipped commit 50bf05e.
- `KELLY_MARKET_MULT` (run_picks.py ~line 521): per-market Kelly multiplier dict. `DEFAULT_MARKET_MULT=0.75`. Keys: `(sport, stat, direction)` — direction=None wildcards both sides. Notable: NBA PTS over=0.50, NBA 3PM over=0.10, WNBA REB under=0.25. Applied before rounding/floor/cap in straight-prop sizing only.
- `FG3M_BLEND_ALPHA`=0.65 (EdgeModel `engine/nba_projector.py` ~line 408; `evaluate_projector.py` project_3pm default). Re-grid 2026-06-05 post-PAD_3P fix (n=1936, seed 42): MAE-optimal 0.65, curve flat 0.55–0.70. **PAD_3P fixed 750/30-game-window → 242/career-to-date** (Medvedovsky 2020; Plan 6 §12) — new `get_player_career_fg3_totals()` in projections_db.py; FGA-path bias improved −0.276→−0.265. Diagnostic: the residual −0.26 bias is SHARED by both blend components (baseline_3pm −0.247) — it lives in the minutes/per-min path and is absorbed downstream by REGULAR_SEASON_STAT_SCALAR (which is why the 30-date scalar backtest shows −0.005); not addressable via alpha or padding.
- **Team-specific sigmas** (run_picks.py, calibrated 2026-06-05): Per-team scoring distributions for matchup-specific sigma lookups. JSON files: `data/team_sigmas_{nhl,mlb,nba,wnba}.json`. Functions: `get_game_sigma(sport, home, away, market)` → sqrt(σ_h²+σ_a²) or GAME_SIGMA fallback; `get_game_sigma_team(sport, team)` → team σ or GAME_SIGMA["team"] fallback; `get_mlb_team_run_r(abbr)` → per-team NB r or MLB_TEAM_RUN_R fallback. The 4 main game-line sigma lookups (total/spread/ml/team) use these; F5 lines stay league-wide. Recalibrate with: `python engine/calibrate_distributions.py --mode team-sigmas --sport all`. Mirrored in analyze_game_lines.py. WNBA JSON keys are numeric team_ids — lookup always falls back to GAME_SIGMA["WNBA"] until a WNBA_ID_MAP is added.

## Data-gated / Open
*Current gate counts: see `memory/project_backlog.md`. Quick snapshot: run `python engine/gate_check.py`.*
- **H3 (Platt refit)**: gated on 100 post-v4 graded `over_p_raw` rows — **64/100 graded** as of 2026-06-05. Check: `python engine/gate_check.py`. **At gate: fit intercept-only (A=1 forced, logit-space) — slope is unidentified at n=76–100; free 2-parameter fit deferred to n≥300.** calibrate_platt.py is back in engine/ (moved from EdgeModel 2026-06-05, Plan 6; was deleted in 5b8ee6d). Run: `python engine/calibrate_platt.py --intercept-only --force` to test (native-only is the default; `--all-rows` re-includes legacy); deploy only if OOS Brier improvement > 0, and change formula + PLATT_SPACE + A/B in run_picks.py simultaneously.
- **Combo Platt refit gate**: need 100 scored combo picks (RA/PRA/PR/PA) — **11/100** as of 2026-06-03. Check: `python analyze_picks.py --stat RA` (and PRA/PR/PA). Win_prob currently inflated ~5pp vs individual stats — no Platt applied at run_picks.py:2413. Refit only after gate reached and with combo-only Brier improvement check.
- **MLB Platt refit gate**: need 100 MLB `over_p_raw` rows — **16/100** as of 2026-06-03. Check: count non-empty `over_p_raw` in pick_log.csv where sport=MLB. Exclusion documented at run_picks.py:2407. Until gate: MLB win_probs are uncalibrated (unknown inflation direction).
- **Shadow CLV go-live**: need ~100 CLV rows in `pick_log_custom.csv` — **63/100** as of 2026-06-03. Daemon stable post-2026-05-09 MAX_UPTIME fix.
- **SGP Platt calibration gate**: need 100 scored SGP slips — **52/100** as of 2026-06-03. Current Platt (A=1.4988, B=−0.8102) built on NBA props; applying to SGP leg probs over-corrects (model→58% vs 69% actual win rate). Gate: 100 scored SGP slips before any Platt refit on SGP data.
- **PICK_SCORE_TIER_MULT T1=0.90×**: Re-evaluate at n=30 T1 picks post-2026-05-23 gates (G8B/G8C/G8D) — **1/30** as of 2026-06-03. Raise to 0.95× if post-gate T1 WR ≥ 55%; remove T1 reserved slots if WR < 50%.
- **NBA TEAM_TOTAL over block**: maintained. Remove when n=30 TEAM_TOTAL over picks (check via `analyze_picks.py --stat TEAM_TOTAL`).
- **Gate recalibration checkpoints** (2026-05-26 gate audit): G8B (AST over ≤4.5) at n=30 post-gate AST picks; G8C (SOG under ≤3.5) at n=30 SOG picks; G8D (3PM over ≤1.5) at n=30 3PM picks. Blocked picks not logged — requires shadow run with gates disabled or accumulated "top filtered" output review.
- **HRR go-live gate**: HRR is in SHADOW_STATS (accumulating fresh data; G_HRR_DISABLED removed 2026-05-27). Was 57.4% WR at line=0.5 under Normal path; NB r=1.5 corrects distribution. Re-evaluate go-live at n=50 graded HRR shadow picks; G13B win_prob thresholds still active (≥0.58 at line ≤0.5, ≥0.65 at line >0.5).
- **AST under 0.5 activated** (R11 narrowed 2026-06-03): 32W/12L 72.7% WR. R11 now blocks only lines 1.5 and 2.5; line 0.5 is live.
- **NHL AST 0.5 under activated** 2026-06-05 via G8 exemption + G_NHL_AST gate (T3, min_edge=0.06). All other NHL AST blocked.
- **G_SOG_SUSPENDED**: SOG fully suspended 2026-06-05 pending distribution investigation. Lift at July offseason refit.
- **G_HA_SUSPENDED**: HA fully suspended 2026-06-05 pending model investigation. Lift TBD — requires HA WR to recover above 40% at n≥20 and model calibration investigation.
- **G_RA_DISABLED**: RA (REB+AST combo) disabled 2026-06-05. 0W/7L (0% actual WR vs 56.7% model, n=11 live picks). Lift when model recalibrated and empirical WR recovers.
- **G_NHL_AST**: NHL AST active only at line==0.5 under. All other NHL AST lines/directions blocked. Added 2026-06-05.
- **WNBA go-live gate**: need 100 graded picks (pick_score>0) post-dampener (Jun 3+) — **0/100** as of 2026-06-03. Log: pick_log_wnba.csv.
- **Role-tier thresholds** (26/20/12/5 MPG, 0.60 starter_rate in `classify_role()`): refit 2026-05-09 on 76,604 trailing-10-game snapshots. MPG threshold confirmed at 26 (24-26 MPG players project like sixth_man regardless of sr; +6.9% PO bias with starter scalar vs -4.6% with sixth_man). 20/12/5 MPG and 0.60 sr unchanged.
- **Position model** (2026-05-10): all position groupings expanded from G/F/C → PG/SG/SF/PF/C. `_pos_group()` in nba_projector, `_position_group()` in projections_db, and `_normalise_position()` in injury_parser all consistent. NBA API only returns G/F/C + combos → effective mapping: G→SG, F→SF, G-F→SF, F-C→PF, C→C. PG tier ready for finer data. Injury redistribution `_POS_FLOW` expanded to 5-position flows. All Bayesian priors (REB/AST/STL/BLK/TOV/archetypes) split using StatMuse 2024-25 per-36 ratios; weighted averages preserved. DB migrated: 587 players re-pulled, team_def_splits recomputed (2880 rows, SG/SF/PF/C groups). PF_high BLK tier added (≥0.020 BLK/min, ~Turner/JJJ). C/PF classification threshold raised 5→10 games.
- **`_POS_FLOW` PG receiver fix** (2026-05-10): NBA API never returns position=PG, so the PG receiver slot in every `_POS_FLOW` row was always skipped → SG injuries silently redistributed only 78% of missing minutes. PG weight folded into SG; same-position weights unchanged. Empirical surplus analysis (84k rows, 3 seasons) attempted but methodology flawed for same-position flows: 64% of C-absent events have no rotation-quality backup C (teams go small ball), diluting C→C empirical signal to near-zero. Intuitive same-position weights correct for the cases the code actually handles.

## Closed Audits
Full fix-pass details: `docs/audits/AUDIT_HISTORY.md`

| Audit | Findings | Status |
|-------|----------|--------|
| 2026-05-29 accuracy overhaul | 4 tracks | ALL CLOSED (commit 9712b5b). NRFI Poisson rewrite, cross-type correlation kills, F5 scalar 0.503→0.540, MLB SGP builder. 1038 tests passing. |
| 2026-05-28 full re-audit (7-agent) | 1C/8H/16M | ALL CLOSED (commit 2e3738a). Key: post_nrfi_bonus MLB routing, F5 projection lookup, ks_record_line, MLB results_graphic. |
| 2026-05-27 full system | 2C/11H/10M | ALL CLOSED. Shadow-stats system (10 new markets), NRFI pitcher fix, card filter relaxation. |
| 2026-05-26 gate/rule/filter | 2C/5H/6M | ALL CLOSED (commit 89c9605). Full detail: `docs/audits/gate_audit_2026-05-26.md`. |
| 2026-05-25 full system (12-track) | 2C/10H/23M | ALL CLOSED (18 commits). REB→NB(r=10.18) post-audit. |
| 2026-06-02 K retirement | Retire K from eligible universe | CLOSED (commit 88a6e41). K permanently removed from all sport pipelines. mlb_sgp_builder K stat dropped. G_K_NO_UNDERS + G_K_MIN_LINE gates retired. |
| Pre-2026-05-25 | multiple audits | All C/H/M closed. See `docs/audits/AUDIT_HISTORY.md`. |

---

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
| **KILLSHOT** | Premium tier (v2, Apr 21 2026). Auto-qualifies only when ALL pass: `tier=T1` strict, `pick_score≥65`, `win_prob≥0.65`, `odds ∈ [-200, +110]`, `stat ∈ {PTS,AST,SOG}` (3PM dropped — T3 stat, can't pass T1 gate). Sizing: 3u default, 4u iff `win_prob≥0.70 AND edge≥0.06` (no 5u). Weekly cap: **2**. Manual override (`--killshot NAME`) bypasses gate but still counts toward cap + requires `score≥75`. Posts to #killshot with @everyone. |
| **KairosEdge** | Halftime trade system — buying trailing team YES in full-game winner market. Tracked separately from props. |
| **Custom Projection Engine** | Replacement for SaberSim as `run_picks.py` CSV input. **Code:** engine/nba_projector.py + projections_db.py + injury_parser.py + csv_writer.py + backtest_projections.py; data/projections.db (SQLite, ~16 MB). **Run daily:** `python engine\generate_projections.py [--run-picks]`. **Late updates:** `--late-run` re-fetches injuries + re-runs without DB persist. **Shadow mode:** `--shadow` → logs to pick_log_custom.csv, no Discord (parallel CLV validation). **Go-live gate:** ~100 shadow CLV rows (see project_backlog.md for current count). **Key features:** EWMA + Bayesian projection per player, role-tier minute scalars (RS + PO), confirmed-starter lineup integration (`engine/lineup_fetcher.py`, C1 2026-05-08), injury redistribution (override/bump split), 240-min lineup-protected constraint, Vegas team-total constraint, blowout sigmoid, high-var `[HIGH-VAR]` flag for bimodal 3PT scorers. Development log: `docs/audits/AUDIT_HISTORY.md`. |

## Key Files

| File | Purpose |
|------|---------|
| `engine/run_picks.py` | Main betting engine (~5k+ lines). **Source of truth — edit engine/ only. Root entry points are shims — no sync step needed.** Flags: `--force-card` (override card guard), `--no-cache` (bypass 15-min Odds API cache — picks pipeline only). |
| `engine/grade_picks.py` | Auto-grades pick_log.csv results, posts Discord recap + results graphic. Monthly summary auto-fires on 1st of month. |
| `engine/capture_clv.py` | CLV daemon — polls every 2 min, captures closing odds T-45 to T+3; CLV written only within T-10 of tip. Scheduled via Task Scheduler at 10am daily. S4U logon. `MAX_DAEMON_UPTIME_SECS=18h` guard prevents no-picks day from blocking next-day start. Also watches `pick_log_custom.csv` when `ENABLE_CUSTOM_CLV=True`. |
| `engine/clv_report.py` | CLI report: `python clv_report.py [--days N] [--sport X] [--tier Y] [--stat X] [--shadow]` |
| `engine/analyze_picks.py` | Backtest analysis dashboard. Usage: `python analyze_picks.py [--sport X] [--since YYYY-MM-DD] [--stat X] [--shadow] [--export]` |
| `engine/weekly_recap.py` | Weekly P&L recap posted to #announcements every Sunday. |
| `engine/mlb_stats_fetcher.py` | Fetches historical MLB pitcher+batter game logs from statsapi.mlb.com (2023-2026). Populates `mlb_games`, `mlb_pitcher_game_stats`, `mlb_batter_game_stats` in projections.db. Run: `python engine/mlb_stats_fetcher.py`. Status: 8,095 games, 69k pitcher rows, 169k batter rows. |
| `engine/nhl_stats_fetcher.py` | Fetches historical NHL skater+goalie game logs from api-web.nhle.com (2023-2026). Populates `nhl_games`, `nhl_skater_game_stats`, `nhl_goalie_game_stats` in projections.db. Run: `python engine/nhl_stats_fetcher.py`. Status: 3,936 games, 142k skater rows, 15k goalie rows. |
| `engine/wnba_stats_fetcher.py` | Fetches historical WNBA player game logs via `nba_api` `LeagueGameLog(league_id="10")` (2023-2026). Populates `wnba_player_game_stats` in projections.db. Run: `python engine/wnba_stats_fetcher.py`. |
| `engine/calibrate_distributions.py` | Within-player distribution calibration for all stats in all sport tables. Outputs NB r, Normal CV, Poisson confirmation per stat. Run: `python engine/calibrate_distributions.py [--sport NBA\|MLB_P\|MLB_B\|NHL_SK\|NHL_G] [--save]`. Results: `docs/calibration_results.json`. |
| `data/pick_log.csv` | Model-generated ledger (primary / bonus / daily_lay / sgp / longshot). Starts Apr 14 2026. **29-column** header (schema_version=4, last col is `over_p_raw`). |
| `data/pick_log_manual.csv` | Manual picks only (--log-manual). Same 29-column schema. Graded alongside main log but never posted to Discord. Excluded from CLV daemon. |
| `data/pick_log_mlb.csv` | Historical MLB shadow log (pre-go-live, Apr 12–May 19). MLB now posts to main `pick_log.csv`. |
| `data/pick_log_wnba.csv` | WNBA shadow log — separate from pick_log.csv. Go-live gate: 100 graded picks post-dampener (Jun 3+). Current count: see project_wnba_shadow.md. |
| `data/pick_log_blocked.csv` | Gate failure audit log. Structural gate failures (props + game lines) logged by log_blocked_pick() on each run. Excludes suspension gates. Created on first run. |
| `sgp_builder.py` | Root shim → `engine/sgp_builder.py`. NBA SGP builder. Allowed books: FanDuel, BetMGM, DraftKings, theScore (espnbet), Caesars (williamhill_us), Fanatics, Hard Rock (hardrockbet). Logs as `run_type=sgp`. |
| `engine/mlb_sgp_builder.py` | MLB SGP builder (added 2026-05-29). 3-4 legs, +200–+450. Stats: OUTS (pitchers); HITS (batters). Gaussian copula with MLB-calibrated ρ table. Fires automatically when MLB CSV is present. Logs to pick_log.csv: `sport=MLB, tier=SGP`. ρ table: OUTS-over + opposing HITS-under = 0.30 (pitcher-dominant script); all other cross-type pairs = 0.02. Kill R2_MLB: OUTS-under + HITS-under same game → killed (opposite scripts). `MIN_LEG_WIN_PROB_OUTS=0.62` (lower than global 0.65 — OUTS Gaussian sigma=0.311 makes 0.65 too tight for pitcher legs). SP scratch guard: drops leg if confirmed SP changes before build. Cohesion scoring: pitcher_dom/batter_hot tags via _correlation_cohesion_mlb() (scoring weight=0.25). |
| `start_clv_daemon.bat` | Launcher for CLV daemon. **Must contain ASCII only** — non-ASCII chars cause cmd.exe to crash with exit code 255. |
| `setup_clv_task.ps1` | Registers CLV daemon scheduled task. S4U logon + WakeToRun. `ExecutionTimeLimit=22h`. Re-run as admin to reset. |
| `post_nrfi_bonus.py` | One-shot webhook poster for manual bonus drops. Uses Mozilla UA to bypass Cloudflare 1010. Restored 2026-05-27. |
| `engine/gate_check.py` | Single-shot CLI reporting all open gate counts. Run: `python engine/gate_check.py`. Added 2026-06-03. |
| `engine/context_research.py` | Per-game Opus research — 15-factor checklist, writes data/context_verdicts.json. Run before picks: `python engine/context_research.py --sport NBA`. Display-only in v1 (CTX+/CTX- tags); gate: 50 graded picks before behavioral use. |
| `docs/research/STATISTICAL_FOUNDATIONS.md` | **Statistical foundations audit (Plan 6, 2026-06-05).** Every distribution/constant validated against published literature; 21 sections, each LOCKED / PERIODIC_RECAL / DATA_GATED / NEEDS_CHANGE with citations. **Before changing any distribution or statistical constant, check this doc — changes must cite evidence that overrides it.** Open NEEDS_CHANGE items (11) listed in its summary table; P0: get_game_sigma() market-covariance fix + NBA GAME_SIGMA calibration. |

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
| KILLSHOT | Highest-conviction tier. v2 gate (Apr 21 2026): tier=T1 strict, score≥65, win_prob≥0.65, odds ∈ [-200,+110], stat ∈ {PTS,AST,SOG} (3PM dropped — T3; REB dropped L9). Sizing: 3u default, 4u iff wp≥0.70 AND edge≥0.06. Weekly cap: 2. @everyone ping. |
| Premium | Top 3 picks per sport from the model each day |
| Bonus Drop | Single highest-scoring NEW pick per run (max 5/day) |
| Daily Lay | Alt spread parlay — 3-leg (min 2), model-identified mispriced lines. **Max combined odds: +100**. Per-leg gates: `edge≥0.025`, `cover_prob≥0.58`. `MIN_DAILY_LAY_PROB=0.50`. Kelly-derived sizing: 0.25–0.75u via `size_daily_lay()`. Redesigned Apr 28 2026. |
| SGP | Same-Game Parlay — **3-4 leg**, **+200–450 range**. NBA (sgp_builder.py) and MLB (mlb_sgp_builder.py, added 2026-05-29). Gaussian copula joint probability. BetMGM preferred. Dynamic sizing: 0.25u default / 0.50u premium (copula EV margin ≥ 0.10 AND cohesion ≥ 0.55 AND avg_edge ≥ 0.035). Allowed books only. `--sgp-only` flag forces SGP post only. |
| Longshot | 6-leg parlay of safest picks. Logged as `run_type=longshot`. Per-game cap: max 2 legs (`LONGSHOT_MAX_PER_GAME=2`). Per-player cap: max 1 leg (added 2026-05-29 — same player's stats are correlated). Added Apr 28 2026. |
| Value Parlay | 5-leg fallback parlay — fires when longshot cannot build a 6-leg slip. Same safest-picks pool, same per-game (max 2) and per-player (max 1) caps. Posts to #bonus-drops. Logged as `run_type=value_parlay`, `tier=LONGSHOT`. Fixed size: `VALUE_PARLAY_SIZE=0.25u`. Added 2026-06-03. |
| CLV | Closing Line Value — primary edge indicator. Positive = beat the close. Raw vigged closing implied minus raw vigged open implied (not vig-free — consistent with industry standard). |
| CO-legal books | 18 CO-approved books. API key "espnbet" = display "theScore Bet" |
| cold_start sub-types | R7/RB8. Players below `MIN_GAMES_FOR_TIER=10` in current season are classified at projection time: **taxi** — n_career_games=0, min cap=12; **returner** — last appearance ≥180 days, min cap=min(career_avg, 22); **extended_absence** — last appearance 60-179 days, min cap=min(career_avg×0.70, 25); **new_acquisition** — last appearance <60 days, min cap=min(career_avg, 28). Cap applied after role scalar. Source: `project_player()` in nba_projector.py. |

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
- **Soft deps (feature-gated):** `openpyxl` (xlsx recap)

## pick_log.csv Schema (current — schema_version 4, 29 columns)
`date, run_time, run_type, sport, player, team, stat, line, direction, proj, win_prob, edge, odds, book, tier, pick_score, size, game, mode, result, closing_odds, clv, card_slot, is_home, context_verdict, context_reason, context_score, legs, over_p_raw`

Authoritative source: `engine/pick_log_schema.py`. Updated to v4 by RB8 IMMEDIATE 1 (2026-05-05).

- `run_type`: primary | bonus | manual | daily_lay | sgp | longshot
- `tier`: T1 | T1B | T2 | T3 | KILLSHOT | DAILY_LAY | SGP | LONGSHOT | MANUAL
- `stat`: SOG | PTS | REB | AST | 3PM | SPREAD | ML_FAV | ML_DOG | TOTAL | TEAM_TOTAL | F5_ML | F5_SPREAD | F5_TOTAL | PARLAY
- `is_home`: True/False for SPREAD/ML/F5/TEAM_TOTAL picks; blank for props
- `clv`: closing_implied_prob − your_implied_prob (positive = beat the close); filled by capture_clv.py
- `context_verdict`: supports | neutral | conflicts | skipped | disabled — blank on normal runs
- `legs`: JSON array for parlay rows (SGP ✓, longshot ✓, daily_lay ✓). primary/bonus/manual leave blank.
- `over_p_raw`: pre-Platt over-probability for prop picks. Blank for non-props and legacy v1–v3 rows. Populating ~300+ rows unblocks H3 Platt refit.

## Sizing Caps
- **Daily total cap: 12u** (12.0 literal in `apply_caps()` — `G12` in code is the pitcher-prop same-game direction gate, unrelated) — hard ceiling across all run_types per session.
- **Sport unit caps:** NBA=8.0u | MLB=8.0u | NHL=5.0u | NFL=5.0u | WNBA=4.0u max per pick (`SPORT_UNIT_CAP` dict).
- **VALUE_PARLAY_SIZE=0.25u** — fixed size for value_parlay (5-leg fallback parlay; fires when longshot cannot build).
- **NHL SOG stat cap:** max 6 picks per run (`STAT_CAP = {"SOG": 6, ...}`; default cap = 2 for other stats).

## Negative Correlation Filter System
Two functions in run_picks.py run before `build_safest6_parlay()` to prevent anti-correlated legs from combining in the longshot pool:

**`filter_game_line_correlations()`** — GL vs GL pairs. Rules 1-5:
- R1: Team ML/SPREAD + opponent TEAM_TOTAL over → kill
- R2: F5_ML both teams same game → kill
- R3: TOTAL over + TOTAL under same game → kill
- R4: TOTAL + TEAM_TOTAL same direction → kill
- R5: NRFI + YRFI same game (ρ=−1.0) → kill *(added 2026-05-29)*

**`filter_cross_type_correlations()`** — Prop vs GL pairs *(added 2026-05-29)*:
- X1 (HARD): Pitcher HA/ER UNDER + opposing TEAM_TOTAL OVER same game (ρ≈−0.65–0.75 — fewer hits/ER = fewer runs)

**SGP hard kills** (in sgp_builder.py and mlb_sgp_builder.py) are separate — they operate within a single SGP slip, not the main card/longshot pool. MLB-specific kills:
- R2_MLB: OUTS-under + HITS-under same game → kill (pitcher struggles = more hits; negative correlation).

## Context Sanity System
**DELETED 2026-05-23.** All context system code removed from run_picks.py. The `context_verdict` column in pick_log.csv remains (existing rows carry "disabled" value). The `--context` flag no longer exists.

## MLB Status
**LIVE as of 2026-05-20.** Picks post to Discord and log to `pick_log.csv`. CLV captured automatically by daemon. Historical shadow log at `data/pick_log_mlb.csv` (Apr 12–May 19, pre-go-live).

## Running grade_picks.py in Cowork
Set `JONNYPARLAY_ROOT` to the repo root and every module resolves paths correctly:
```
export JONNYPARLAY_ROOT=/sessions/.../mnt/JonnyParlay
python engine/grade_picks.py --date YYYY-MM-DD [--repost] [--dry-run]
```
Windows deployments leave env var unset — `paths.py` falls back to `~/Documents/JonnyParlay`.

## ⚠ Cowork Write Caution
If the engine runs on Windows and writes to pick_log.csv, do NOT use the Write tool to rewrite pick_log.csv — it will clobber engine-written rows. Use Edit/append only.

## Daily Routine
1. Download SaberSim CSV
2. `python run_picks.py nba.csv` (or nhl.csv etc) — posts card, logs picks
3. Done — CLV daemon captures automatically, grade_picks.py grades after games

## CLV Daemon
- Scheduled: Windows Task Scheduler, daily 10am, runs `start_clv_daemon.bat`
- Logon: **S4U** (fires without active desktop session). WakeToRun enabled. `ExecutionTimeLimit=22h`.
- `MAX_DAEMON_UPTIME_SECS=18h` — exits if no picks logged after 18h (prevents blocking next-day start on zero-pick days).
- Manual trigger: `schtasks /run /tn "JonnyParlay CLV Daemon"` or foreground `python -u engine\capture_clv.py`
