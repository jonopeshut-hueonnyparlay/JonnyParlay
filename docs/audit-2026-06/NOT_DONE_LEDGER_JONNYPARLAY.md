# NOT-DONE / INCOMPLETE LEDGER — JonnyParlay (audit 2026-06-26)

X-3 deliverable: what is *not* finished, per file — so nothing half-wired is mistaken for done.

**Counts:** dead-code=23 · deferred=23 · flag-gated=12 · partial-feature=18 · stub=6 · todo=2 · total=84

| Kind | Module | File | Detail |
|------|--------|------|--------|
| partial-feature | JP-1 | evaluators.py | I6 confidence penalty (lines 100-113) is inert on the SaberSim CSV path because parse_csv never sets GP; only fires when the EdgeModel projector injects GP. |
| partial-feature | JP-2 | calibrated.py | NFL constants present but data half deferred: SIGMA PASS/RUSH/REC_YDS (lines 42-44), POISSON_STATS TDS/PASS_TDS (line 52), STAT_FAMILY_TIER NFL entries (254,266). DATA_GA |
| partial-feature | JP-3 | mlb_sgp_builder.py | Shadow stats HRR/RBI/RUNS/ER excluded from the MLB SGP pool until they graduate to live status (header lines 8-9); only OUTS and HITS are live. |
| partial-feature | JP-3 | sgp_builder.py | Module header advertises a fast equicorrelation approx for the 91k-combo search, but _score_sgp actually runs full 1000-sample MC per combo (the documented approx path is |
| partial-feature | JP-4 | capture_clv.py | YARDS→player_reception_yards only (line 170, 'NFL — best available'); rushing/passing yards not distinguishable. NFL data path known-deferred. |
| partial-feature | JP-5 | post_nrfi_bonus.py | Module is a hardcoded one-shot NRFI poster with placeholder win_prob/edge/proj/size defaults (73-86); docstring says production would parameterize via CLI args. Not wired |
| partial-feature | JP-6 | context_research_v2.py | WNBA standings lack last10 and home/road splits, so _factor_form and _factor_home_away always degrade to stale-neutral for WNBA (lines 1594,1638); NHL has no standings so |
| partial-feature | JP-7 | analyze_game_lines.py | No analyze_nhl despite NHL entry in SIGMA and NHL mention in the closing legend; __main__ only handles MLB and NBA (lines 949-1006). |
| partial-feature | JP-7 | odds_io.py | totals_1st_1_innings is fetched and stored under {eid}_nrfi (line 354/396) but no extractor in odds_io consumes the _nrfi key (extract_f5_lines only handles 'f5_innings') |
| partial-feature | JP-8 | pick_log_writers.py | clv_corrected (v5 column) is only blank-filled by the DictWriter parlay/bonus paths; the positional log_picks writer never emits it, so primary rows are 29 fields vs the  |
| partial-feature | JP-8 | pick_log_schema.py | validate_is_home_for_stat (line 329) and assert_manual_row_valid/validate_manual_row (lines 568-602) are defined and exported but no writer in pick_log_writers.py invokes |
| partial-feature | JP-9 | health_check.py | Section 9 EdgeModel constant checks (L252-260) are unbound substring matches that do not actually validate constant values/names — effective coverage is much weaker than  |
| partial-feature | JP-9 | weekly_recap.py | COUNTED_RUN_TYPES (L69) is hand-maintained and explicitly must be kept in sync with grade_picks.py; it omits 'killshot' and 'manual'. KILLSHOT inclusion in weekly/monthly |
| partial-feature | JP-10 | calibrate_distributions.py | wnba-3pm deploy note says to also 'remove WNBA 3PM from Normal path in calc_prop_prob()' — a pending manual deploy step. wnba-sigma 3PM proxy (0.48 vs empirical min>=20 C |
| partial-feature | JP-10 | evaluate_projector.py | Component projectors re-implement project_player rather than calling it; eval can silently drift from production if the EdgeModel pipeline changes without mirroring. |
| partial-feature | JP-11 | diag_h6_backtest.py | Tests a PROPOSED pool filter (REC_THRESHOLD=5.0 / SEASON_THRESHOLD=25.0) — diagnostic for a filter decision, not wired to production; outcome (false-drop %) is informatio |
| partial-feature | JP-13 | market_config.py | NFL PROP_MARKETS + MARKET_TO_STAT mappings present (pricing half) but NFL data half (CSV export/parse) deferred — known incomplete per feat/nfl. |
| partial-feature | JP-14 | engine_logger.py | Docstring (M-28) states the print->logging migration is deliberately incomplete: 'doesn't rip out every print overnight'; most engine entry points still use bare print(). |
| stub | JP-4 | capture_clv.py | clv_corrected written by the daemon (1862,1869,1347) is consumed by nothing in the read files; clv_report.py never reads the clv_corrected column, and retro_correct_clv.p |
| stub | JP-5 | grade_picks.py | grade_game_line GOLF_WIN branch (1264-1267) always returns None — golf outrights graded manually only. |
| stub | JP-6 | context_research_v2.py | _factor_rlm keyed branch (lines 1268-1270) is a bare 'pass' — even with a key set, RLM is never computed. |
| stub | JP-6 | context_research_v2.py | _fetch_ump_stats HTML scrape fallback (lines 1474-1481) intentionally returns None ('do not guess a brittle selector'); umpire factor inert without a working JSON source/ |
| stub | JP-7 | analyze_game_lines.py | MLB_PROJS/NBA_PROJS hardcoded slate is a stale fallback (lines 152-168); when no fresh SaberSim CSV is found _build_projs returns {} and analyze_*() silently fall back to |
| stub | JP-8 | pick_log_schema.py | migrate_row source_header param (line 142) and normalize_is_home stat param (line 285) are accepted but unused ('reserved for future'). No current behavior depends on the |
| deferred | JP-1 | evaluators.py | Lines 853-858: NRFI_GAMMA DATA_GATED — recalibrate (predicted mult vs realized NRFI) on the in-house 8,095-game DB when first-inning-level data exists. |
| deferred | JP-1 | calibrated.py | MLB GAME_SIGMA (line 187) flagged interim per Plan 10 §O — recalibrate from the 8095-game DB like NBA/NHL. Game-line only (dropped from live card). |
| deferred | JP-2 | prob_core.py | _platt_calibrate_prop logit-space migration (lines 32-39) pending H3 gate; assert guards against pasting logit A/B into raw formula. Sigma/temperature refit on n=2180 pic |
| deferred | JP-2 | calibrated.py | MLB_PARK_FACTORS (line 231) flagged 'Do NOT apply without a refit' 2026-06-07; TEX sign inverted, COL/KC/MIN/DET stale. Needs refit from current Savant/Fangraphs before u |
| deferred | JP-2 | calibrated.py | NB_R['HA']=13.41 (line 84) to be reclassified HA->Poisson (starts-only var/mu=0.890<1) on HA unsuspension; tracked under G_HA_SUSPENDED. |
| deferred | JP-2 | calibrated.py | GAME_SIGMA['MLB'] (line 187) and F5/park values are interim/uncalibrated — 'Recalibrate from 8095-game DB like NBA/NHL'. |
| deferred | JP-2 | calibrated.py | BM_SHRINKAGE_WEIGHT (line 285) and VAKE_MULT (line 316) DATA_GATED: per-family refit at n>=150 graded picks, and Kelly multiplier-stack consolidation to single empirical- |
| deferred | JP-3 | sgp_builder.py | SGP_JOINT_EV_MARGIN=0.025 and premium gates (0.035/0.55/0.10/0.015) are explicitly DATA_GATED: 'tune against CLV/W-L data over 50+ builds' / 're-tune at n=100 scored SGP  |
| deferred | JP-3 | mlb_sgp_builder.py | MLB pairwise rho is a structural prior; empirical-Bayes magnitude refit (shrink observed r toward 0.30) deferred until n>=160 scored MLB SGP slips (_log_mlb_sgp_rho_statu |
| deferred | JP-4 | capture_clv.py | GAME_LINE_CLV_MARKET omits TEAM_TOTAL: 'TEAM_TOTAL: deferred — needs team-filtered matching in team_totals market' (line 218); get_game_line_closing_odds returns (None,'' |
| deferred | JP-5 | grade_picks.py | NRFI/YRFI has no VOID/postponement terminal path (1175-1192) unlike F5; suspended-game NRFI rows remain ungraded indefinitely. |
| deferred | JP-6 | context_research_v2.py | opening-line snapshot captures home_ml/away_ml (line 755) but _factor_line_move only consumes 'total'; moneyline movement captured-but-unused. |
| deferred | JP-8 | pick_log_schema.py | context_verdict column is frozen/disabled ('context system removed 2026-05-23; existing rows carry "disabled"', line 63); context_reason/context_score retained only for l |
| deferred | JP-9 | health_check.py | Section 7 documents NRFI/YRFI/TEAM_TOTAL CLV capture as deferred — checks assert NRFI remains in capture_clv.SKIP_STATS (L237-242), i.e. CLV is intentionally not captured |
| deferred | JP-10 | nb_calibrate.py | K (pitcher strikeouts) r=5.0 is provisional/undocumented and HRR r=1.5 is single-point moment-matched; proper within-player var/mu refit deferred pending an MLB game-log  |
| deferred | JP-10 | calibrate_sigma.py | MLB pitcher/batter stats (OUTS, HA, K, HRR) not calibrated — no game-log data in projections.db (see backlog). AST has NO SIGMA entry and falls back to mult=0.40/min=2.0  |
| deferred | JP-11 | analyze_playoff_scalars.py | Round bucketing is an explicitly-labelled 'lazy heuristic' (lines 48-50) using a 30-day offset because explicit playoff-round metadata is not available in the games table |
| deferred | JP-12 | analyze_blend.py | Standalone advisory: explicitly a no-code-change gate ('re-evaluate at n=100 graded game-line CLV rows'). BLEND_ALPHA sport-specific split is proposed in docstring but no |
| deferred | JP-13 | gates.py | Pending investigations referenced but unresolved: G8C SOG scope 're-evaluate when distribution investigation completes' (line 64), G_HA_DIR 'when model investigation comp |
| deferred | JP-13 | market_config.py | SUSPENDED_STATS SOG/HA pending lift (SOG July refit, HA lift after WR>=40% at n>=20); KILLSHOT_STAT_ALLOW SOG 're-add at July refit' (thresholds.py line 47). |
| deferred | JP-13 | rules.py | R12 cooldown + R9/R11 reclassified product/optics rules with explicit 'when CLV data matures, replace loss trigger with negative-CLV condition' TODOs (lines 104-108, 193- |
| deferred | JP-13 | gate_check.py | H3 Platt gate retained 'for historical visibility only' (SUPERSEDED, line 176) — counted/displayed but no longer a deploy basis. |
| deferred | JP-14 | secrets_config.py | EDGEMODEL_DB_PATH default is a Documents-folder path that does not match the real C:\Dev\EdgeModel checkout; relies on .env override and has no existence check (latent st |
| flag-gated | JP-1 | evaluators.py | Lines 115-127: WNBA Platt uses NBA+NHL coefficients pending a WNBA-specific refit (known sigma/Platt calibration gate). |
| flag-gated | JP-1 | calibrated.py | USE_NO_VIG_ANCHOR=False (line 291) — Track-B no-vig BM anchor intentionally gated off until n>=150 CLV + sign-off; flag-off path byte-identical (known/expected). |
| flag-gated | JP-2 | calibrated.py | USE_NO_VIG_ANCHOR=False (line 291) gates the theoretically-correct no-vig BM shrinkage anchor off; flag-off path is byte-identical (vigged anchor). Intentional until n>=1 |
| flag-gated | JP-4 | capture_clv.py | ENABLE_SHADOW_CLV=False (line 320) — MLB shadow log CLV capture disabled until MLB goes live; SHADOW_LOGS={} when off. |
| flag-gated | JP-4 | capture_clv.py | SKIP_STATS={GOLF_WIN,PARLAY,GA,PC} (line 200) — no Odds API market; intentionally never CLV-captured. |
| flag-gated | JP-5 | grade_picks.py | SHADOW_SPORTS = set() (87) and SHADOW_LOGS = {} (post_nrfi_bonus 54) — all sports live; shadow-log grading paths (main 2654-2657) retained for legacy CSVs but effectively |
| flag-gated | JP-6 | context_research_v2.py | _factor_rlm and _factor_public_sharp permanently return stale-neutral (weight 5/25 dead) until ACTION_NETWORK_PRO_KEY is added; documented in module docstring lines 25-26 |
| flag-gated | JP-8 | pick_log_schema.py | migrate_file defaults dry_run=True (line 491) — never rewrites a file unless explicitly invoked with dry_run=False; on-disk migration is a manual operator action, not aut |
| flag-gated | JP-9 | diagnostics.py | Entire redistribution + Vegas-vs-240 diagnostic module is a no-op unless JONNYPARLAY_DIAG_REDISTRIB / JONNYPARLAY_DIAG_VEGAS_VS_240 env vars are set (L42-43,L149-150). In |
| flag-gated | JP-10 | calibrate_platt.py | H3 logit-space migration (Step1 formula + PLATT_SPACE + A/B) deferred behind n>=100/n>=300 data gate; free 2-parameter fit deferred to n>=300. Superseded by JonnyParlay C |
| flag-gated | JP-13 | gate_digest.py | DISCORD_GATES_WEBHOOK import falls back to os.getenv because secrets_config registration is 'a one-line addition' not yet landed (lines 56-62); webhook blank-by-default s |
| flag-gated | JP-13 | thresholds.py | config/thresholds.toml override mechanism (lines 159-205) is opt-in; absent file = no override, replay byte-identical. Inactive feature surface. |
| dead-code | JP-1 | evaluators.py | evaluate_props cooldown_players parameter accepted but never referenced; R12 cooldown is applied separately in run_picks.main via apply_r12_cooldown. |
| dead-code | JP-2 | calibrated.py | SIGMA dict comments document removed-but-referenced entries (REC, SOG/HITS removed because POISSON_STATS takes priority). Confirmed removed; comments are coverage notes,  |
| dead-code | JP-3 | sgp_builder.py | IDEAL_LEG_WIN_PROB=0.70 (line 57) is defined but never referenced anywhere. |
| dead-code | JP-3 | sgp_builder.py | POISSON_STATS is an empty set (line 78) so the Poisson branch in _fair_prob (220-234) is unreachable; AST/REB moved to NB_STATS. Intentional but dead. |
| dead-code | JP-4 | capture_clv.py | Unreachable give-up/STALE conditions secs_to_start<-STALE_AFTER_SECS (1782,1889) and secs_to_start<-CAPTURE_AFTER_SECS (1895) inside the in-window block; the enclosing wi |
| dead-code | JP-5 | grade_picks.py | _key_sport_matches (1311-1317) is a documented no-op that always returns True; exists only as a future extension point for mixed-sport score dicts. |
| dead-code | JP-6 | context_research.py | v1 paid-Opus path (claude-opus-4-8 web_search) is superseded by the free v2 implementation per the v2 docstring; retained but not the active producer. |
| dead-code | JP-7 | analyze_game_lines.py | get_game_sigma / get_game_sigma_team / get_mlb_team_run_r and _load_team_sigmas_agl()+_TEAM_SIGMAS_AGL are defined and loaded at import but never called; analyze_mlb/anal |
| dead-code | JP-7 | mlb_starter_fetcher.py | _norm_name() (lines 71-83) is never called; is_confirmed uses name_key(). |
| dead-code | JP-8 | pick_log_schema.py | _MIGRATIONS registry + register_migration/migrate_row_chain framework (lines 178-208) has zero registered transforms today; it is a pure pass-through equal to migrate_row |
| dead-code | JP-10 | nb_calibrate.py | CURRENT={'3PM':9.15,'AST':9.68,'REB':10.18} defined but never used; values hardcoded inline in the loop. |
| dead-code | JP-10 | projection_accuracy.py | Unused 'today' variable in the rolling-trend block (line 224). |
| dead-code | JP-10 | empirical_analysis.py | Frozen one-off research snapshot (2026-05-24) with hardcoded absolute user paths and no CLI/main guard; not part of any automated pipeline. |
| dead-code | JP-11 | _check_dvp.py | Imports projections_db (line 8), which does not exist in JonnyParlay/engine. ImportError on run; non-functional in this repo. |
| dead-code | JP-11 | analyze_playoff_scalars.py | Imports nba_projector and projections_db (lines 31-38), both EdgeModel-only. Cannot run from JonnyParlay root. |
| dead-code | JP-11 | diag_blowout_buckets.py | Imports projections_db (line 28); also prints stale pre-refit blowout constants (line 136). Non-functional here. |
| dead-code | JP-11 | diag_h1_constraint_chain.py | Imports generate_projections.run (line 84), EdgeModel-only. ImportError when the re-run path executes. |
| dead-code | JP-11 | diag_h6_backtest.py | Imports projections_db (line 21); EdgeModel-only. Non-functional here. |
| dead-code | JP-11 | diag_h6_pool.py | Imports projections_db (line 20); EdgeModel-only. Non-functional here. |
| dead-code | JP-12 | analyze_blend.py | Module runs all logic at import time with no `if __name__=='__main__'` guard; importing it executes the analysis and may sys.exit(0). Intended as a script but unguarded. |
| dead-code | JP-13 | gates.py | G1 gate (line 199) is unreachable — its edge<0.05 clause is always pre-empted by G9 at line 141. |
| dead-code | JP-13 | market_config.py | SHADOW_LOG_PATHS = {} (line 75) emptied after MLB/WNBA go-lives; SHADOW_SPORTS = set() (line 23) also empty — shadow-sport routing currently inert (by design, re-populate |
| dead-code | JP-13 | rules.py | STAT_CAP['SOG']=6 (line 260) is unreachable while SOG is in SUSPENDED_STATS (blocked in check_prop_gates before apply_caps). |
| todo | JP-1 | evaluators.py | Line 123: TODO refit combo (PRA/PR/PA/RA) Platt at SGP Platt gate (100 scored slips) — combos currently skip Platt and are ~5pp inflated. |
| todo | JP-1 | evaluators.py | Lines 866-867: TODO — if SaberSim source switches to park-neutral inputs, replace _LEAGUE_AVG_BLENDED_RATE with a park-adjusted league avg and apply MLB_PARK_FACTORS to N |
