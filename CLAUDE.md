# Memory

## Active Scalars — `engine/nba_projector.py`
- `PLAYOFF_MINUTES_SCALAR` (~line 242): starter=1.075, sixth_man=0.960, rotation=0.924, spot=0.948, cold_start=0.400. Refit 2026-05-06 on 3925 pairs (3 seasons).
- `REGULAR_SEASON_MINUTES_SCALAR` (~line 261): starter=1.0667, sixth_man=1.0462, rotation=1.0854, spot=1.6124, cold_start=1.0880. Refit 2026-05-10 (4653 player-games, 30-date RS backtest, overall ratio 1.0365).
- `REGULAR_SEASON_STAT_SCALAR` (~line 276): pts=1.0019, ast=1.0120, reb=1.0264, fg3m=1.0231, blk=1.0608, stl=1.0017, tov=1.000.
- `LEAGUE_AVG_PACE`=100.22 (2025-26 season-to-date; 2024-25 RS=99.58). `LEAGUE_AVG_PACE_PO`=96.5.
- `_HOME_AWAY_DELTA`: pts=0.0235, reb=0.0088, ast=0.0333, fg3m=0.0452, blk=0.0439, tov=−0.0122.
- `_REB_RATE_PRIOR` (PO): PG=0.135, SG=0.139, SF=0.140, PF=0.175, C=0.246. RS: PG=0.128, SG=0.132, SF=0.168, PF=0.210, C=0.305. **RESOLVED 2026-06-07**
- `DK_STD_FLOOR`: starter=4.0, sixth_man=4.0, rotation=3.5, spot=3.0, cold_start=3.0. `DK_STD_COEFF`=0.35.
- `HIGH_VAR_CV_THRESHOLD`=0.60, `HIGH_VAR_MIN_GAMES`=8 (3PT specialist high-dispersion flag; CV detects dispersion, not bimodality).
- Blowout sigmoid: k=0.15, mid=20.0, max_reduction=0.19 (refit 2026-05-06 on 24,600 rows).
- `PLAYOFF_RATE_DEFLATORS`: pts=0.934, ast=0.845, fg3m=0.948, blk=1.152. Refit 2026-05-10 (20-date PO backtest, 1071 player-games). BLK is an inflator (under-projected, t=−2.74); update pending C01 gate.
- `PLATT_A`=1.4988, `PLATT_B`=−0.8102 (`calibrated.py`) — **frozen** until H3 gate. Formula: `sigmoid(A * over_p + B)` (**raw-probability space — NOT logit-space**). `PLATT_SPACE="raw"` safeguard in `thresholds.py` (read by `prob_core.py`) asserts formula space matches. At H3 all three change together from calibrate_platt.py output: formula + A/B (`calibrated.py`) + PLATT_SPACE→`"logit"` (`thresholds.py`).
- `NB_R` (`calibrated.py`): `3PM`=9.15 (var/mu=1.1486); `AST`=12.16 (var/mu=1.3234, game-level refit 2026-05-30); `REB`=14.7 (var/mu=1.3873, game-level refit 2026-05-30); `HA`=13.41 (var/mu=1.204); `RBI`=0.87 (var/mu=1.535, ~74% zero-RBI games); `ER`=2.62 (var/mu=1.700, bullpen/run-support tails); `HRR`=1.5 (moment-matched shadow log). STL/BLK/TOV Poisson confirmed (var/mu=1.072/1.113/1.050).
- `NB_R_WNBA` (`calibrated.py`): `AST`=11.37, `REB`=10.74, `3PM`=1.342. AST/REB calibrated 2026-06-04 (202 players / 13,322 game-logs, min≥8). 3PM recalibrated 2026-06-09 (13,970 rows, var/mu=1.708, zero_rate=0.502 — heavily overdispersed vs NBA r=9.15, ~50% zero games).
- `COMBO_RHO_WNBA` (`calibrated.py`): PTS-REB=0.294, PTS-AST=0.188, REB-AST=0.200. Refit 2026-06-04 (202 players, 13,322 game-logs). ~0.04–0.05 below NBA equivalents.
- `SIGMA_WNBA` (`calibrated.py`): `PTS`=mult 0.48/min 3.5; `AST`=mult 0.65/min 1.0; `REB`=mult 0.54/min 1.0; `3PM`=mult 0.48/min 0.70 (z-score/combo path only — 3PM props use NB path). Recalibrated 2026-06-05 on priced population (min≥20, 153 players). Used for G14 z-score proxy and combo sigma.
- **WNBA gates** (`thresholds.py` constants + `wnba_gate.py` logic): `WNBA_EV_FLOOR`=0.0955 — G_WNBA_EDGE is an EV-per-unit floor (`win_prob/implied_prob(odds) − 1 ≥ 0.0955`, NBA's G9 net EV at −110), computed from quoted odds so it auto-adjusts to vig. Early-season dampener is **sigma inflation**: `WNBA_EARLY_SEASON_EDGE_MULT` factors (days 1–14: 0.80 → σ×1.25; days 15–21: 0.90 → σ×1.11) divide sigma in calc_prop_prob/_combo_mu_sigma/G14 so win_prob, edge, score AND Kelly size shrink coherently. Factors DATA_GATED: recalibration deferred to 2027 season start. Opening gate keyed to **games played**: `WNBA_OPENING_GATE_GAMES`=2 (both teams, via `_wnba_team_games_played()`; `WNBA_OPENING_GATE_DAYS`=3 fallback; season days 1–14 only). `WNBA_SEASON_START`=2026-05-13 (update each season). `WNBA_TEAM_ABBREV` name→abbrev map (15 teams incl. GSV/TOR/PDX).
- `SIGMA` (`calibrated.py`): `PTS`=mult 0.35/min 5.0; `REB`=mult 0.48/min 2.0 (combo path only); `AST`=mult 0.53/min 2.0 (combo path only); `OUTS`=mult 0.27/min 1.0; `PC`=mult 0.19/min 6.0 (both recalibrated 2026-06-05, Plan 6 §1C, **starts-only** — prior 0.311/0.375 were contaminated by relief appearances; PC skew −1.93 — Normal provisional, empirical-CDF candidate at July refit); `SV`=mult 0.253/min 3.5 (NHL goalie saves, calibrated 2026-05-26). `HA` removed from SIGMA — now NB_STATS (r=13.41). `MIN_LEG_WIN_PROB_OUTS=0.62` tuned to old σ=0.311; monitor SGP leg counts before retuning.
- `GAME_SIGMA["WNBA"]` (`calibrated.py`): `total`=17.424, `team`=11.253 (spread/ml=10.0 — no active WNBA spread/ML picks). Recalibrated 2026-06-09 from 851 games (priors were placeholders).
- `GAME_SIGMA["NHL"]` (`calibrated.py`): `total`=2.311, `spread`=2.614, `team`=1.744, `ml`=2.614. Calibrated 2026-06-05 from 3,936 games; ml=spread (P(win)=P(margin>0)). Prior values were wrong by ~2×.
- `MLB_TEAM_RUN_R`=3.548 (`calibrated.py`): NB dispersion for MLB team run-scoring. Calibrated 2026-06-05 from 8095 RS games (var/mu=2.261). Used for team-total NB CDF and ML NB direct sum (`mlb_ml_from_nb()`). MLB HITS/BB/RUNS remain Poisson — within-player var/mu all near 1.0 (0.89/0.97/0.97).
- `F5_SIGMA` (`calibrated.py`): `total`=2.65, `spread`=2.70, `team`=2.10. Tuned 2026-05-29 (was total=2.6/spread=2.75/team=2.0).
- **F5 scalar**: 0.540 (all three paths — total, ML, spread). Updated 2026-05-29 from 0.503 (market-calibrated from 2022-2025 F5 lines). SaberSim team totals already park-adjusted — no extra park multiplier.
- **NRFI/YRFI model** (`evaluators.py` `evaluate_nrfi()`): Rewritten 2026-05-29 to Poisson λ model. `BASE_LAMBDA_1ST=0.32` (avg matchup → ~53% P(NRFI); replaced miscalibrated `BASE_SCORING_RATE=0.1633`). `_LEAGUE_AVG_BLENDED_RATE=0.4808` (0.25×ERA/9 + 0.75×FIP/9, league avg; updated Plan 9 §9A). `NRFI_GAMMA=0.65` (NB overdispersion dampener; DATA_GATED refit when first-inning data exists). Formula: `λ_team = 0.32 × (pitcher_blended_rate / 0.4808) × (team_runs / 4.45)`; `P(NRFI) = e^(-λ_away - λ_home)`. Park factor intentionally omitted — SaberSim saber_team projections already park-adjusted.
- `MLB_PARK_FACTORS` dict in `calibrated.py` (keyed by home team abbrev, source: Baseball Savant 2022-2025). Not applied to projections (effects already in SaberSim inputs); available for future park-neutral paths.
- `KELLY_FRACTION`=6.0 (`thresholds.py`) — continuous Kelly sizing, replaces VAKE step function. It is a units converter under the 100u bankroll convention (stake fraction = f*×6/100 ≈ 1/16.7 Kelly), NOT "1/6 Kelly".
- `KELLY_MARKET_MULT` (`calibrated.py`): per-market Kelly multiplier dict. `DEFAULT_MARKET_MULT=0.75`. Keys: `(sport, stat, direction)` — direction=None wildcards both sides. Notable: NBA PTS over=0.50, NBA 3PM over=0.10, WNBA REB (both dirs, None-keyed)=0.10 (floor-pin at go-live 2026-06-09; revisit n≥50). Applied before rounding/floor/cap in straight-prop sizing only.
- **Tier system**: tiers = stat-family calibration buckets, NOT conviction. `STAT_FAMILY_TIER` (`calibrated.py`) routes: AST/HITS→T1B; RUNS→T1B; REB/HRR/RBI/ER/HA→T1; REC→T2; 3PM/SOG/NHLPTS/NHLBLK/TDS/GOALS/ML_DOG/GA/SV→T3; rest (incl. NRFI/YRFI/TEAM_TOTAL/F5_TOTAL)→T2. Floors monotone: T2=0.05 < T1B/T3=0.06 < T1=0.07. `BM_SHRINKAGE_WEIGHT`={T2:.85, T1:.75, T1B:.80, T3:.70} (`calibrated.py`) — Baker–McHale `w·model_p+(1−w)·implied_p` via `apply_bm_shrinkage` (`sizing_core.py`), called in `evaluate_props` (`evaluators.py`) post-Platt, ALL props (incl. MLB+combos). Overrides kept: NHL AST→T3, REB over→T2 (shadow).
- `FG3M_BLEND_ALPHA`=0.65 (EdgeModel `engine/nba_projector.py` ~line 408; `evaluate_projector.py` project_3pm default). Re-grid 2026-06-05 post-PAD_3P fix (n=1936): MAE-optimal 0.65, curve flat 0.55–0.70. **PAD_3P fixed 750/30-game-window → 242/career-to-date** via `get_player_career_fg3_totals()` in projections_db.py. Residual −0.26 bias is in the minutes/per-min path, absorbed by REGULAR_SEASON_STAT_SCALAR; not fixable via alpha or padding.
- `GAME_SIGMA["NBA"]` (`calibrated.py`): `total`=18.5, `spread`=12.5, `team`=11.0, `ml`=12.5. Calibrated 2026-06-05 (Plan 6 §6) from 3,922 games, residual-basis. Prior 12/12/9/12 were ~40% too narrow.
- **Team-specific sigmas** (loaded by `_load_team_sigmas()` in `calibrated.py`; lookups in `team_resolve.py`): per-team scoring distributions for matchup-specific sigma. JSON: `data/team_sigmas_{nhl,mlb,nba,wnba}.json`. Functions: `get_game_sigma(sport, home, away, market)` → **relative-scaler formula: `σ_league(market) × sqrt((σ_h²+σ_a²)/(2·σ̄²_league))`, n_games≥20 on both teams, else GAME_SIGMA fallback**; `get_game_sigma_team(sport, team)` → team σ or GAME_SIGMA["team"] fallback; `get_mlb_team_run_r(abbr)` → per-team NB r or MLB_TEAM_RUN_R fallback. The 4 game-line lookups (total/spread/ml/team) use these; F5 stays league-wide. Recalibrate: `python engine/calibrate_distributions.py --mode team-sigmas --sport all`. Mirrored in analyze_game_lines.py. WNBA JSON keys are numeric team_ids — always falls back to GAME_SIGMA["WNBA"] until a WNBA_ID_MAP exists.

## Data-gated / Open
*Current gate counts: see `memory/project_backlog.md`. Quick snapshot: run `python engine/gate_check.py`.*
- **H3 (Platt refit)**: gated on 100 post-v4 graded `over_p_raw` rows — **98/100** as of 2026-06-13 (`python engine/gate_check.py`). **At gate: fit intercept-only (A=1 forced, logit-space) — slope unidentified at n=76–100; free 2-param fit at n≥300.** Run: `python engine/calibrate_platt.py --intercept-only --force` (native-only default; `--all-rows` re-includes legacy); deploy only if OOS Brier improves, changing formula + A/B (`calibrated.py`) + PLATT_SPACE (`thresholds.py`) simultaneously.
- **Combo Platt refit gate**: need 100 scored combo picks (RA/PRA/PR/PA) — **27/100** as of 2026-06-13. Check: `python analyze_picks.py --stat RA` (and PRA/PR/PA). Win_prob inflated ~5pp vs individual stats — no Platt applied (combo path in `evaluate_props`). Refit only after gate + combo-only Brier improvement check.
- **MLB Platt refit gate**: need 100 MLB `over_p_raw` rows — **28/100** as of 2026-06-13. Check: count non-empty `over_p_raw` in pick_log.csv where sport=MLB. Exclusion documented in `evaluators.py` (evaluate_props). Until gate: MLB win_probs are uncalibrated (unknown inflation direction).
- **Shadow CLV go-live**: need ~100 CLV rows in `pick_log_custom.csv` — **0/100** as of 2026-06-13 (227 pre-Plan-6–10 rows archived to `pick_log_custom_archive_pre_plan10.csv`). **At gate also require one-sided t≥1.7 on post-reform rows; never pool pre/post-reform CLV rows.**
- **Plan 10 fixes shipped** (commits 1dfb31f/13fb3f3/f084010, 2026-06-07): tier moves (RBI/ER→T1, RUNS→T1B, GA/SV→T3, HA→T1, REC→T2); MLB GAME_SIGMA interim (total 4.6/spread 4.2/ml 4.2); LEAGUE_AVG_TOTAL 222→229; copula approx ×0.87; G_OUTS_UNDER WP block removed; HITS over→shadow; R11 reclassified; value_parlay +EV gate; MLB_PARK_FACTORS stale warning. DEFERRED/DATA_GATED:
  - **TEAM_TOTAL/ML_DOG not BM-shrunk** (§1b/1c premise void): game-line stats never reach apply_bm_shrinkage. No code change.
  - **CLV capture NRFI/YRFI/TEAM_TOTAL** (§EE): **SHIPPED 2026-06-09** — TEAM_TOTAL via `team_totals` matcher, NRFI/YRFI via `totals_1st_1_innings`; mapped PA/PR/RA/PRA combos + latent ER/BB/RBI/RUNS/GOALS/NHLPTS/NHLBLK/SV, fixed prop-log F5 keys, added `_is_capturable_stat` guard. SKIP_STATS now {GOLF_WIN, PARLAY, GA, PC}.
  - **BM direction inverted** (§B): T1 w=0.75 > T3 w=0.70 but T1 has worst ROI. Refit at n≥150/family.
  - **conf early-season double-shrink** (§V): fold into GP-conditioned BM weight w_eff=w·GP/(GP+k). DATA_GATED.
  - **VAKE_MULT["variance"] double-count** (§K): retire into Kelly-stack consolidation (n≥50/market).
  - **KELLY_MARKET_MULT uncalibrated** (§K): DATA_GATED n≥50/market.
  - **PRA/PR/PA/RA→T1B** (§A): at combo Platt gate n=100.
  - **CLV write-gate latch** (§EE): change to last pre-tip observation; research-gated.
  - **REC Poisson→NB** at NFL go-live (n≥50). **HRR r=1.5→~1.1** — July refit: fix r, audit μ projection path, investigate zero-inflated NB, reset shadow log. **game-line edge floor** ~0.03–0.05 (n≥50 graded).
- **SGP Platt calibration gate**: need 100 scored SGP slips — **70/100** as of 2026-06-13. Current Platt (A=1.4988, B=−0.8102) built on NBA props over-corrects SGP leg probs (model→58% vs 69% actual WR). Gate: 100 scored slips before any SGP Platt refit.
- **Family bootstrap gate (Plan 9 §9F, replaces retired T1 mult + n=30 checkpoint)**: at n≥150 graded picks/family, 95% bootstrap CI on ROI — retire family if P(ROI≥0)<0.10; same gate refits `BM_SHRINKAGE_WEIGHT` per-family (current per-tier values are priors, DATA_GATED).
- **NBA TEAM_TOTAL over block**: maintained. Remove when n=30 TEAM_TOTAL over picks (check via `analyze_picks.py --stat TEAM_TOTAL`).
- **Gate recalibration checkpoints** (2026-05-26 audit): G8B (AST over ≤4.5) at n=30 post-gate AST picks; G8C (SOG under ≤3.5) at n=30 SOG picks; G8D (3PM over ≤1.5) at n=30 3PM picks. Blocked picks not logged — needs shadow run with gates disabled.
- **HRR go-live gate — evaluated 2026-06-09, NOT activated**: n=61, 47.5% WR vs 55.0% breakeven, −21.1% sized ROI. `G_HRR_OVER_LOW_LINE` added: blocks HRR over at line ≤0.5 (−25.5% ROI, n=54). HRR under + over at lines >0.5 stay in SHADOW_STATS. Implied r≈1.1. G13B win_prob thresholds still active (≥0.58 at line ≤0.5, ≥0.65 at >0.5). Next: July refit.
- **AST under 0.5 activated** (R11 narrowed 2026-06-03): 32W/12L 72.7% WR. R11 now blocks only lines 1.5 and 2.5; line 0.5 is live.
- **NHL AST 0.5 under activated** 2026-06-05 via G8 exemption + G_NHL_AST gate (T3, min_edge=0.06). All other NHL AST blocked.
- **G_SOG_SUSPENDED**: SOG fully suspended 2026-06-05 pending distribution investigation. Lift at July refit. **On lift: re-add SOG to `KILLSHOT_STAT_ALLOW` and a tier set — `_assert_killshot_invariants()` enforces consistency at module load.** Suspensions live in the `SUSPENDED_STATS` dict (single source of truth for SOG/HA/RA).
- **G_HA_SUSPENDED**: HA fully suspended 2026-06-05 pending model investigation. Lift TBD — requires HA WR to recover above 40% at n≥20 and model calibration investigation.
- **G_RA_DISABLED**: RA (REB+AST combo) disabled 2026-06-05. 0W/7L (0% actual WR vs 56.7% model, n=11 live picks). Lift when model recalibrated and empirical WR recovers.
- **G_NHL_AST**: NHL AST active only at line==0.5 under. All other NHL AST lines/directions blocked. Added 2026-06-05.
- **WNBA go-live gate: CLOSED 2026-06-09** at 98/100. Early-season factor recalibration (0.80/0.90) **deferred to 2027 season start** (DATA_GATED). REB mult pinned to 0.10 floor (35.3% shadow WR), revisit at n≥50.
- **POISSON_CUTOFF NFL hardening (before NFL go-live)**: replace the `line <= POISSON_CUTOFF` branch with a Poisson-only path (`if stat in POISSON_STATS:`) or route over-cutoff Poisson stats to Normal(μ=proj, σ=√proj) instead of the uncalibrated SIGMA fallback. Zero behavioral change today; NFL REC at lines >8.5 would silently mis-route by 5–8pp.
- **Kelly multiplier-stack consolidation (DATA_GATED, n≥50 graded per market)**: tier_m retired 2026-06-06 (BM shrinkage now carries tier calibration). Remaining chain: KELLY_MARKET_MULT × var_m (VAKE_MULT["variance"], tier-keyed) × corr_m × exp_m. Future: consolidate market_m + var_m to one empirical-Bayes per-market multiplier (James–Stein at ~50 graded/market); flag any KELLY_MARKET_MULT < 0.30 as cosmetic (0.25u floor overrides) and consider gating exclusion instead.
- **Plan 7 EdgeModel NEEDS_CHANGE — Group 3 CLOSED 2026-06-07** (see `docs/research/EDGEMODEL_FOUNDATIONS.md`): (3) AST→Vegas DATA_GATED (game_implied_totals live; reopen ~4–6 wks); (4) spot=1.6124 HELD (filter refit rejected, ratio 1.0025; two-stage hurdle model next at larger sample).
- **Usage-concentration (Plan 8 §8G #2, DATA_GATED at n≥50 injury-replacement events)**: creator threshold is AST% (share of teammate FGs a player assists), NOT 20% of team AST count. Correct constant `_CREATOR_USAGE_SHARE=0.30` — not yet in code. Fix when Plan 8 Group 2 creator metric is implemented.
- **Travel/altitude (Plan 8 §8C #4, DATA_GATED)**: two effects — altitude (DEN/UTA home per-possession efficiency multiplier) and westward travel (win-prob tilt, 2024 circadian study). Neither in code. Implement at July refit; westward tilt conditional on controlling for home/away.
- **NRFI_GAMMA=0.65 recalibration (DATA_GATED)**: m^γ dampener + ERA/FIP 25/75 shipped. γ=0.65 is literature default — recalibrate when first-inning data exists (bucket predicted mult vs realized NRFI on 8,095-game DB). xFIP/FIP− upgrade deferred to July refit.
- **SGP_JOINT_EV_MARGIN=0.025 (DATA_GATED)**: joint-EV existence floor in both builders — copula joint_prob > implied(parlay odds)+0.025 for ANY slip. Re-tune ε at the 100-scored-slip Platt gate. Premium gate (margin ≥0.10) unchanged.
- **R4 REB-over lift condition (Plan 9 §9J, pre-registered)**: lift R4 shadow only when post-refit shadow REB-overs show (a) n≥50, (b) win_prob calibration bias within ±3pp, (c) mean CLV ≥ 0. WR≥55% is secondary check only.
- **MIN_LEG_WIN_PROB_OUTS=0.62 monitor (Plan 9 §9H)**: tuned to the old OUTS σ=0.311; monitor at n≥40 graded OUTS SGP legs; if retune fires, σ-equivalent floor ≈0.64.
- **SB26-131 ops note (CO, URGENT BEFORE AUG 12 2026)**: credit-card deposit ban + max 6 deposits/24h effective 2026-08-12. Action: switch to ACH as primary funding; cache working balance at each book. Not a code change.
- **R9 directional balance monitor**: R9 reclassified as product rule, not EV. When n≥50 forced-over events, compute cumulative score-gap + realized P&L of forced-over vs displaced picks. Long-term: negative-CLV trigger.
- **R12 cooldown trigger replacement**: R12 reclassified as product rule. When CLV data matures, replace loss trigger with negative-CLV condition (CLV ≤ −2pp on last pick, or 2+ consecutive losses with negative CLV).
- **`_POS_FLOW` PG receiver fix** (2026-05-10): NBA API never returns position=PG → PG receiver slot was always skipped (SG injuries redistributed only 78% of minutes). PG weight folded into SG; same-position weights unchanged.

## Closed Audits
Full details: `docs/audits/AUDIT_HISTORY.md` — all pre-2026-06 audits closed.

---

## Me
Jono (jonopeshut@gmail.com). Sports bettor, DFS player, Discord community operator. Runs picks as a trading business — analytical, sharp, luxury brand.

## Brand
**picksbyjonny** · Tagline: *edge > everything* · Aesthetic: luxury · sharp · analytical  
Discord bot display name: **PicksByJonny**

## Projects

| Name | What |
|------|------|
| **JonnyParlay** | Python betting engine — run_picks.py + grade_picks.py. Runs on Windows at `C:\Dev\JonnyParlay` |
| **Discord Overhaul** | Full server rebuild — **done**. Phase 1 design + Phase 2 manual build both shipped. |
| **KILLSHOT** | Premium tier (**v3**, Plan 6 §13, Jun 5 2026). Auto-qualifies when ALL pass: `pick_score≥65`, `odds ∈ [-200, +110]`, `win_prob ≥ implied_prob(odds)+0.03` (odds-dependent), `stat ∈ {PTS,AST}` (NO tier requirement — T1 WR 46.6% < T2 60.3%; SOG removed while suspended, re-add at July refit), sport ≠ WNBA (explicit exclusion at go-live 2026-06-09 until CLV history matures). Sizing: 3u default, 4u iff `win_prob≥0.70 AND edge≥0.06` (no 5u). Weekly cap: **2**. Manual override (`--killshot NAME`) bypasses score/stat selection but MUST pass odds range + wp floor (v3) + `score≥75`, counts toward cap. Module-load invariant asserts allowlist stats are unsuspended + tier-eligible. Near-miss disqualifications logged to pick_log_blocked.csv as `KILLSHOT_{ODDS\|WP\|STAT}`. Posts to #killshot with @everyone. |
| **KairosEdge** | Halftime trade system — buying trailing team YES in full-game winner market. Tracked separately. |
| **Custom Projection Engine** | Replacement for SaberSim as `run_picks.py` CSV input. **Code:** engine/nba_projector.py + projections_db.py + injury_parser.py + csv_writer.py + backtest_projections.py; data/projections.db (SQLite, ~16 MB). **Run daily:** `python engine\generate_projections.py [--run-picks]`. **Late updates:** `--late-run` re-fetches injuries + re-runs without DB persist. **Shadow mode:** `--shadow` → logs to pick_log_custom.csv, no Discord (parallel CLV validation). **Go-live gate:** ~100 shadow CLV rows (see project_backlog.md for current count). **Key features:** EWMA + Bayesian projection per player, role-tier minute scalars (RS + PO), confirmed-starter lineup integration (`engine/lineup_fetcher.py`, C1 2026-05-08), injury redistribution (override/bump split), 240-min lineup-protected constraint, Vegas team-total constraint, blowout sigmoid, high-var `[HIGH-VAR]` flag for bimodal 3PT scorers. Development log: `docs/audits/AUDIT_HISTORY.md`. |

## Key Files

| File | Purpose |
|------|---------|
| `engine/run_picks.py` | Main betting engine orchestrator (**~1578 lines**; refactored 2026-06-12 from 6982 — constants + logic extracted into 30+ focused modules, see **Engine Module Map** below). `main()` is decomposed into named stage helpers. **Source of truth — edit engine/ only. Root entry points are shims — no sync step needed.** Flags: `--force-card` (override card guard), `--no-cache` (bypass 15-min Odds API cache — picks pipeline only). **Game lines decoupled 2026-06-13 (f69095b)** — run_picks no longer cards/logs/posts game lines (TEAM_TOTAL/SPREAD/TOTAL/ML/F5); `analyze_game_lines.py` is sole source. `evaluate_game_lines` still runs internally for prop-correlation filtering only; NRFI/YRFI still shadow-log to pick_log_shadow_stats.csv; Daily Lay unchanged. |
| `engine/grade_picks.py` | Auto-grades pick_log.csv + pick_log_game_lines.csv; posts Discord recaps (game lines to `DISCORD_GAME_LINES_WEBHOOK`). Monthly summary auto-fires on 1st of month. |
| `engine/capture_clv.py` | CLV daemon — polls every 2 min, captures closing odds T-45 to T+3; CLV written only within T-10 of tip. Scheduled via Task Scheduler at 10am daily. S4U logon. `MAX_DAEMON_UPTIME_SECS=18h` guard prevents no-picks day from blocking next-day start. Also watches `pick_log_custom.csv` when `ENABLE_CUSTOM_CLV=True`. |
| `engine/clv_report.py` | CLI report: `python clv_report.py [--days N] [--sport X] [--tier Y] [--stat X] [--shadow]` |
| `engine/analyze_picks.py` | Backtest analysis dashboard. Usage: `python analyze_picks.py [--sport X] [--since YYYY-MM-DD] [--stat X] [--shadow] [--export]` |
| `engine/weekly_recap.py` | Weekly P&L recap posted to #announcements every Sunday. |
| `engine/mlb_stats_fetcher.py` | Fetches historical MLB pitcher+batter game logs from statsapi.mlb.com (2023-2026). Populates `mlb_games`, `mlb_pitcher_game_stats`, `mlb_batter_game_stats` in projections.db. Run: `python engine/mlb_stats_fetcher.py`. Status: 8,095 games, 69k pitcher rows, 169k batter rows. |
| `engine/nhl_stats_fetcher.py` | Fetches historical NHL skater+goalie game logs from api-web.nhle.com (2023-2026). Populates `nhl_games`, `nhl_skater_game_stats`, `nhl_goalie_game_stats` in projections.db. Run: `python engine/nhl_stats_fetcher.py`. Status: 3,936 games, 142k skater rows, 15k goalie rows. |
| `engine/wnba_stats_fetcher.py` | Fetches historical WNBA player game logs via `nba_api` `LeagueGameLog(league_id="10")` (2023-2026). Populates `wnba_player_game_stats` in projections.db. Run: `python engine/wnba_stats_fetcher.py`. |
| `engine/calibrate_distributions.py` | Within-player distribution calibration for all stats in all sport tables. Outputs NB r, Normal CV, Poisson confirmation per stat. Run: `python engine/calibrate_distributions.py [--sport NBA\|MLB_P\|MLB_B\|NHL_SK\|NHL_G] [--save]`. Results: `docs/calibration_results.json`. |
| `data/pick_log.csv` | Model-generated ledger (primary / bonus / daily_lay / sgp / longshot). Starts Apr 14 2026. **29-column** header (schema_version=4, last col is `over_p_raw`). No longer receives game-line/TEAM_TOTAL rows from run_picks (decoupled 2026-06-13). |
| `data/pick_log_manual.csv` | Manual picks only (--log-manual). Same 29-column schema. Graded alongside main log but never posted to Discord. Excluded from CLV daemon. |
| `data/pick_log_mlb.csv` | Historical MLB shadow log (pre-go-live, Apr 12–May 19). MLB now posts to main `pick_log.csv`. |
| `data/pick_log_wnba.csv` | Historical WNBA shadow log (pre-go-live, through Jun 8 2026). WNBA now posts to main `pick_log.csv`. Still graded by grade_picks.py and CLV-watched (`ENABLE_WNBA_CLV`) until legacy rows close. |
| `data/pick_log_calibration.csv` | **Calibration shadow log** (added 2026-06-14). Captures ALL evaluated prop picks with valid `over_p_raw` — qualified **and** gate-failed — for unbiased Platt calibration (10–50× more signal/day than pick_log.csv). Written by run_picks (`run_type=calibration`, guarded by `--no-save`), never posted, graded silently daily via grade_picks.py shadow loop. Gate: **Calibration Platt** (0/100) in `gate_check.py`. NB: requires the `log_picks` `run_type`-param fix (was hard-coded `"primary"`). |
| `data/pick_log_blocked.csv` | Gate failure audit log. Structural gate failures (props + game lines) logged by log_blocked_pick() on each run. Excludes suspension gates. Created on first run. |
| `data/pick_log_game_lines.csv` | Game-line bet log. Written by `analyze_game_lines.py` confirm-to-log flow. Not yet wired to capture_clv.py. |
| `analyze_game_lines.py` | Standalone game-line edge analyzer. Confirm-to-log flow: after ranked table, prompts user to select rows; writes to `data/pick_log_game_lines.csv` (29-col schema, run_type=game_line, card_slot=GL). Discord posting via `_post_game_lines_discord()` — console preview when `DISCORD_GAME_LINES_WEBHOOK` blank, live POST when set. Not yet wired to capture_clv.py. `PICK_LOG_GAME_LINES_PATH` added to `engine/paths.py`. |
| `sgp_builder.py` | Root shim → `engine/sgp_builder.py`. NBA SGP builder. Allowed books: FanDuel, BetMGM, DraftKings, theScore (espnbet), Caesars (williamhill_us), Fanatics, Hard Rock (hardrockbet). Logs as `run_type=sgp`. |
| `engine/mlb_sgp_builder.py` | MLB SGP builder (added 2026-05-29). 3-4 legs, +200–+450. Stats: OUTS (pitchers); HITS (batters). Gaussian copula with MLB-calibrated ρ table. Fires automatically when MLB CSV is present. Logs to pick_log.csv: `sport=MLB, tier=SGP`. ρ table: OUTS-over + opposing HITS-under = 0.30; all other cross-type pairs = 0.02. Kill R2_MLB: OUTS-under + HITS-under same game → killed. `MIN_LEG_WIN_PROB_OUTS=0.62` (lower than global 0.65 — OUTS sigma=0.311 makes 0.65 too tight). SP scratch guard: drops leg if confirmed SP changes before build. Cohesion: pitcher_dom/batter_hot tags via _correlation_cohesion_mlb() (weight=0.25). |
| `start_clv_daemon.bat` | Launcher for CLV daemon. **Must contain ASCII only** — non-ASCII chars cause cmd.exe to crash with exit code 255. |
| `setup_clv_task.ps1` | Registers CLV daemon scheduled task. S4U logon + WakeToRun. `ExecutionTimeLimit=22h`. Re-run as admin to reset. |
| `post_nrfi_bonus.py` | One-shot webhook poster for manual bonus drops. Uses Mozilla UA to bypass Cloudflare 1010. Restored 2026-05-27. |
| `engine/gate_check.py` | Single-shot CLI reporting all open gate counts. Run: `python engine/gate_check.py`. Added 2026-06-03. |
| `engine/context_research.py` | 5 parallel group calls per game (odds/lines, weather, pitching, team/standings, roster), weighted 15-factor aggregation, daily cache, --sport ALL flag. Writes data/context_verdicts.json. Display-only until Plan 11 gate. |
| `docs/research/STATISTICAL_FOUNDATIONS.md` | **Statistical foundations audit (Plan 6).** Every distribution/constant validated against literature; 21 sections, each LOCKED / PERIODIC_RECAL / DATA_GATED / NEEDS_CHANGE with citations. **Before changing any distribution or statistical constant, check this doc — changes must cite evidence that overrides it.** All 11 NEEDS_CHANGE resolved (10 full + #9 Kelly-stack partial). |
| `docs/research/EDGEMODEL_FOUNDATIONS.md` | **EdgeModel projection + player-context audit (Plans 7–8).** Plan 7 (7A–7I): EWMA spans, minute scalars, Vegas constraint, stat scalars/deflators, DK_STD, 3PM architecture, blend alphas. Plan 8 (8A–8H): home/away delta, blowout sigmoid, days-rest, REB priors, role tiers, cold-start, injury redistribution, status probs. **Check before changing any EdgeModel projection/context constant.** Plan 7: 7 NEEDS_CHANGE (July-refit gated): STL/BLK span 8→~20, _AST_EWMA_SPAN inverted, AST Vegas-anchoring, spot=1.6124 root-fix, FG% padding, HIGH_VAR relabel, evaluate_projector frame alignment. Plan 8: 6 NEEDS_CHANGE, headline = `_REB_RATE_PRIOR` ~2× deflation; 8G usage-concentration + 8C days-rest notable; 8H binary LOCKED. Key locks: blend alphas (don't refit), PAD_3P=242, OT cap, Vegas prior. |
| `docs/research/MARKET_FOUNDATIONS.md` | **Market-facing foundations audit (Plan 9).** 11 sections (9A–9K): NRFI/YRFI model, anti-correlation filters (X1, ρ bands), CLV methodology, SLOW_BOOKS, parlay construction, tier system, hard card rules (R4/R7/R9/R10/R12), daily caps. Counts: 24 LOCKED · 9 PERIODIC_RECAL · 13 DATA_GATED · 12 NEEDS_CHANGE — **all 12 RESOLVED**. **Before changing any market-facing constant, gate, or card rule, check this doc.** **Plan 10: ~70 items audited A–GG; ~22 CHANGE/NEEDS_CHANGE backlog + corrected STAT_FAMILY_TIER. Implementation PENDING.** |

## Engine Module Map (post-2026-06-12 refactor)
*Test suite: 1318 passing as of 2026-06-13 (commit ae2e7b3 added direct-module coverage for the refactored modules).*
`run_picks.py` is now a thin orchestrator; constants and logic live in focused modules under `engine/`:
- **`engine/quant/`** — pure math: `distributions.py`, `odds.py`, `derived.py`, `copula.py` (probit/cholesky/copula_joint_prob/copula_joint_approx).
- **`calibrated.py`** — fitted values: `SIGMA`, `SIGMA_WNBA`, `NB_R`, `NB_R_WNBA`, `COMBO_RHO_WNBA`, `GAME_SIGMA`, `F5_SIGMA`, `MLB_TEAM_RUN_R`, `MLB_PARK_FACTORS`, `KELLY_MARKET_MULT`, `PLATT_A`/`PLATT_B`, `STAT_FAMILY_TIER`, `BM_SHRINKAGE_WEIGHT`, `_load_team_sigmas()`.
- **`thresholds.py`** — structural decision-boundary constants: `KELLY_FRACTION`, `PLATT_SPACE`, KILLSHOT + gate thresholds, WNBA gate constants.
- **`market_config.py`** — runtime/market wiring: `SPORT_KEYS`, `SUSPENDED_STATS`.
- **`gates.py`** — `check_prop_gates`, `check_game_gates`. **`rules.py`** — `apply_hard_rules`, R12, caps.
- **`sizing_core.py`** — `kelly_units`, `apply_bm_shrinkage`. **`sizing.py`** — `size_picks_base`, `size_bonus_pick`, `size_picks_vake`.
- **`prob_core.py`** — `calc_prop_prob`, `pick_score`, `_platt_calibrate_prop`. **`evaluators.py`** — `evaluate_props`, `evaluate_game_lines`, `evaluate_f5_lines`, `evaluate_nrfi` (`NRFI_GAMMA` lives here).
- **`correlation.py`** — `deduplicate`, `filter_game_line_correlations`, `filter_cross_type_correlations`.
- **`odds_io.py`** — `OddsFetcher`, CSV parsing, extractors. **`team_resolve.py`** — `get_game_sigma`/`get_game_sigma_team`/`get_mlb_team_run_r`, `resolve_team_abbrev`. **`wnba_gate.py`** — WNBA early-season gate logic. **`name_norm.py`** — `normalize_name`. **`pick_log_lock.py`** — `_pick_log_lock` primitive.
- **`parlays.py`** — pure parlay builders (`build_safest6_parlay` et al.). **`killshot.py`** — KILLSHOT selection/gating (`_assert_killshot_invariants` fires at import). **`discord_post.py`** — Discord I/O, embeds, posters, `set_confirm_mode`/`get_confirm_mode`, `_CTX_VERDICTS`. **`output_format.py`** — `fmt_*`, `format_output`.
- **`pick_log_writers.py`** — WRITERS (`log_picks`, `log_blocked_pick`). **`pick_log_io.py`** — pre-existing locked READERS (unchanged — **distinct from** pick_log_writers.py).
- **SGP contract (keep intact):** `sgp_builder.py` still imports `PICK_LOG_PATH`, `_pick_log_lock`, `_normalize_odds`, `_normalize_size`, `_write_schema_sidecar`, `_webhook_post` from `run_picks` — these remain re-exported. `_pairwise_rho` stayed in `sgp_builder.py` (NBA domain logic).

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
| KILLSHOT | Highest-conviction tier. v3 gate (Plan 6 §13, Jun 5 2026): score≥65, odds ∈ [-200,+110], wp ≥ implied_prob(odds)+0.03 (odds-dependent), stat ∈ {PTS,AST} — no tier requirement (3PM dropped earlier; REB dropped L9; SOG removed while suspended). WNBA excluded (go-live 2026-06-09). Sizing: 3u default, 4u iff wp≥0.70 AND edge≥0.06. Weekly cap: 2. Manual path also enforces odds+wp. @everyone ping. |
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
  - Windows path: `C:\Dev\JonnyParlay\.env` (also searches project root + `engine/.env`)
  - Template: `.env.example` (committed). Real `.env` is gitignored.
  - Debug inventory: `python engine/secrets_config.py` prints a redacted summary.
  - `DISCORD_GAME_LINES_WEBHOOK` added to `secrets_config.py` + `.env` — blank by default; set to go live (no code change needed).
- `espnbet` in Odds API → display as **theScore Bet** everywhere
- CO_LEGAL_BOOKS: 18 books defined in `engine/book_names.py`

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
- **Daily total cap: 12u** (12.0 literal in `apply_caps()`, `rules.py` — `G12` in code is the pitcher-prop same-game direction gate, unrelated) — hard ceiling across all run_types per session.
- **Sport unit caps:** NBA=8.0u | MLB=8.0u | NHL=5.0u | NFL=5.0u | WNBA=4.0u max per pick (`SPORT_UNIT_CAP` dict).
- **VALUE_PARLAY_SIZE=0.25u** — fixed size for value_parlay (5-leg fallback parlay; fires when longshot cannot build).
- **NHL SOG stat cap:** max 6 picks per run (`STAT_CAP = {"SOG": 6, ...}`; default cap = 2 for other stats).

## Negative Correlation Filter System
Two functions in `engine/correlation.py` run before `build_safest6_parlay()` (`parlays.py`) to prevent anti-correlated legs from combining in the longshot pool:

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

## MLB Status
**LIVE as of 2026-05-20.** Picks post to Discord and log to `pick_log.csv`. CLV captured automatically by daemon. Historical shadow log at `data/pick_log_mlb.csv` (Apr 12–May 19, pre-go-live).

## WNBA Status
**LIVE as of 2026-06-09.** Posts to Discord, logs to `pick_log.csv`. `SHADOW_SPORTS` empty (defined in `market_config.py`; mirrored in grade_picks.py). CLV daemon watches main log + legacy `pick_log_wnba.csv` until legacy rows close (then flip `ENABLE_WNBA_CLV=False` in capture_clv.py). Still in force: `SPORT_UNIT_CAP`=4.0u, G_WNBA_EDGE (EV≥0.0955), G_WNBA_OPEN, early-season sigma dampener (2027). **Excluded from KILLSHOT** (sport check in `_passes_killshot_v2_gate`, `killshot.py`) until CLV history matures. REB pinned to 0.25u floor (mult 0.10 both dirs, revisit n≥50); REB over remains R4-shadow-routed.

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
