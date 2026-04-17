# v7 Engine — Complete Status Report

All roadmaps unified — Gap Analysis + Feature Sprint + Future Capabilities

Updated March 28, 2026 — picksbyjonny ML Engine

  22Done
  5Commands
to Run
  3Partially
Fixed
  23Remaining
TODO


## Action Commands to Run

  Built but not yet executed. Run these to activate recent work.


    A1. Retrain NBA with 27-feature structure
    Picks up 2 new referee features (default to 0 until backfill). Harmless — XGBoost ignores constant-zero columns.
    python v7_daily.py train nba



    A2. Backfill historical referee assignments (~5 hours)
    Populates ref_assignments table from NBA Stats API. Rate-limited at 0.8s/request. Run overnight.
    python v7_daily.py ref-backfill



    A3. After backfill: compute ref tendencies + retrain NBA
    Computes per-ref bias stats, then retrains with populated ref features to measure impact.
    python v7_daily.py ref-tendencies
python v7_daily.py train nba



    A4. Confirm feature audit JSON fix
    The np.bool_ serialization fix was applied but never re-run to confirm.
    python validation/feature_audit.py



    A5. Train model stacker (after 50+ shadow predictions)
    Learns optimal XGBoost/Neural blend weights from accumulated shadow logs. Check periodically.
    python v7_daily.py train-stacker



## Complete Done (22 items)

  From Critical + Next Sprint across both roadmaps. Click to expand if needed.

  C1. NCAAB injury feature wired into model
  C2. Barttorvik daily scrape + timestamped CSVs + 5 validation gates
  C3. Neural static features use real XGBoost values
  C4. NCAAB name mapping consolidated to name_map_bart.json
  C5. PBP features added to NBA (4 features: second_chance, fastbreak, paint, tov_battle)
  C6. Auto margin correction + sigma re-estimated on every retrain (OLS)
  C7. Walk-forward temporal validation (NBA: 11 folds, all positive skill)
  C8. Feature importance audit (gain, permutation, collinearity, correlation)
  C9. Conference SOS for NCAAB (conf_strength_diff feature)
  C10. Team-specific HCA for NCAAB (home_team_hca feature)
  C11. Rest days as continuous feature (already existed)
  C12. CLV tracking (shared/clv_tracker.py already existed)
  C13. Pace-adjusted totals model (shared/totals_engine.py already existed)
  C14. Referee tendency integration for NBA (referee.py + 2 features)
  C15. Model stacking meta-learner (Ridge blend, model_stacker.py)
  C16. Corrupted Barttorvik backup file fix (canonical filename matching)
  C17. 3 unmapped NCAAB team names fixed (Gardner-Webb, Sam Houston, LIU)
  C18. JSON serialization fixes (numpy int64, float, bool) in walk_forward.py + feature_audit.py
  C19. NCAAB retrained: 15 features, 19.2% Brier skill
  C20. Barttorvik getadvstats.php disabled (corrupted column mapping)
  C21. find_all_barttorvik_csvs() strict pattern matching
  C22. Timestamped CSV filenames for all scraped data


## Gap Analysis Remaining Critical + Sprint Items

  From the deep code review. These are bugs, debt, and calibration fixes.



    G1. Fallback defaults silently masking missing data
    20+ hardcoded fallbacks (PPG→110, pace→98, eFG→52, etc.) silently replace missing data with league averages. No logging, no visibility into which games run on degraded data. Creates covariate shift.
    **Fix:** Add `data_quality` column counting fallback features per game. Log warnings when >2 features use fallback. Track in pick logs for audit.

      2 hours
      Both
      Root Cause #2





    G2. Favorite compression at extreme spreads
    At 18+ pt spreads, model predicts margin 5.4 vs actual 25.5 (79% compression). SPREAD_CAP=15, margin correction slope, removed market shrinkage are three separate bandaids on the same root cause. Linear correction can't fix a non-linear problem.
    **Fix:** Train on `sign(margin) * log(1 + |margin|)` and reverse at inference. Or quantile regression for tails. Or separate blowout sub-model for spreads >12. Then remove SPREAD_CAP and static correction.

      Half day
      NBA
      Root Cause #1





    G3. Favorite sizing haircuts masking calibration problem
    After favorites went 4W-7L: FAV_SIZE_HAIRCUT=0.75, FAV_SPREAD_MIN_EDGE=0.02, hard cap at 0.25u. All treat the symptom (favorites losing) by throttling sizing. If calibration improves, these actively cost money.
    **Fix:** Run calibration check on favorites only — plot predicted win% vs actual. If calibrated correctly, remove haircuts. If miscalibrated, fix calibration (isotonic/Platt on favorites bucket) instead of penalizing sizing.

      2-3 hours
      NBA
      Root Cause #4





    G4. Injury train/serve skew
    Training uses injury data shifted by 1 game (prevents leakage). Live prediction uses real-time injuries (tonight's status). Model learned from weak delayed signal but receives strong current signal at inference.
    **Fix:** Option A (safe): Use "previous game" injuries at prediction time for consistency, add real-time as separate additive adjustment outside model. Option B: Retrain with two columns (baseline + realtime).

      2-3 hours
      NBA
      Root Cause #5





    G5. No home/away splits in features
    Model has home_team_hca but doesn't capture how teams perform differently home vs away in key stats. Some teams shoot 5% better eFG at home. L10 averages treat all games the same regardless of venue.
    **Fix:** Add `home_efg_diff_ha`, `home_pace_diff_ha`, `home_def_rating_diff_ha`. Three new features from existing data.

      1-2 hours
      Both





    G6. Totals model underpowered (8 features, sigma 19.57)
    Only 8 features. Hardcoded totals_r2=0.12 is a guess. 0.75 Kelly haircut further throttles sizing. Totals have lower market efficiency than sides — edge exists but not with this feature set.
    **Fix:** Add features (four factors, rest/B2B, defensive matchup, ref pace) → 14-16 features. Compute totals_r2 from holdout. Remove 0.75 haircut once calibration is honest.

      Half day
      NBA
      Root Cause #3





    G7. Neural model severely disagrees with XGBoost
    Shadow logs: neural predicts avg margin 1.2 (stdev 2.2) vs XGB 3.3 (stdev 10.3). Disagree on side ~70% of games. Not a useful ensemble — per-sequence normalization may be destroying cross-game signal.
    **Fix:** Evaluate neural Brier skill on same holdout. If <5%, it's underfit. Try global normalization vs per-sequence. Train on more data (4 seasons vs XGB's 15). Static features now fixed (#C3) — re-evaluate.

      1-2 days
      NBA





    G8. Silent error swallowing across pipeline
    Six separate `except Exception` blocks catch all errors (including bugs) and continue with degraded data. Pipeline produces normal-looking picks based on zeroed-out features when something breaks.
    **Fix:** Replace bare `except:` with specific types. Add `warnings` list printed in pick summary: "This run used fallback for: injuries, elo, totals." Log full tracebacks.

      1 hour
      Both
      Root Cause #2





    G9. Probability clipping hides calibration issues
    `np.clip(probs, 0.01, 0.99)` in 3 places + 0.75u Kelly cap. If calibration is correct, these cost money on best plays. Caps should be justified by actual calibration data, not hardcoded.
    **Fix:** Use tighter justified bounds [0.02, 0.98] based on actual calibration curve. Replace fixed 0.75u cap with bankroll-percentage-based max (2% of bankroll).

      30 min
      Both
      Root Cause #4





    G10. XGBoost eval set uses random sampling (not temporal)
    Early stopping eval set is random-sampled with RandomState(42). Leaks future information — 2025 games can influence when training on 2020 data stops.
    **Fix:** Use temporal early stopping with same sample weights as training. Or use fixed time window (last 60 days before calibration fold) as eval set.

      1 hour
      Both




## Maintenance Gap Analysis — When Ready

  Lower priority fixes, cleanup, and validation tasks.


    M1. Contrarian/motivation boosts unvalidated
    CONTRARIAN_EDGE_BOOST=0.01, MOTIVATION_EDGE_BOOST=0.015 — hardcoded, never backtested.
    **Fix:** After 100+ tagged picks, compute actual win rate tagged vs untagged. Set to zero if no edge.
    1 hourRoot Cause #4



    M2. Line shopping ignores book health
    best_home_spread takes best number across ALL books. Some may be restricted/limited.
    **Fix:** Add HEALTHY_BOOKS config list. Filter in pull_odds(). ~10 lines.
    15 min



    M3. Manual data refresh before picks
    No staleness check — if refresh is forgotten, picks run on stale features.
    **Fix:** Add staleness check at top of run_picks(). Auto-run refresh if DB lacks today's date.
    30 min



    M4. No automated grading pipeline
    Grading exists but isn't wired into daily pipeline. model_health.py exists but runs manually.
    **Fix:** Ensure every pick gets result log (W/L, score, CLV, units). Wire model_health.py weekly.
    1-2 hours



    M5. NIT sigma inflation is a guess
    game_sigma = sigma * 1.15 for NIT neutral games. 15% bump with no validation.
    **Fix:** Collect NIT residuals or use all neutral-site games as proxy to compute actual sigma.
    1 hourNCAAB



    M6. Hardcoded tournament team lists
    NCAA_TOURNAMENT_TEAMS, CBC_TEAMS, PUBLIC_TEAMS_NBA are manually maintained Python sets.
    **Fix:** Pull from ESPN API or move to JSON config file.
    1 hour



    M7. Pick volume caps instead of threshold tuning
    MAX_PICKS_PER_DAY=3 drops lowest-edge picks. Portfolio constraint masquerading as model fix.
    **Fix:** Raise edge thresholds until natural pick volume is 4-6. Keep caps as safety net only.
    30 minRoot Cause #4



    M8. Low R² caps maximum edge (ongoing)
    NBA R²=0.14, NCAAB R²=0.10. Market already prices 86%+ of model knowledge. Max edge ~2-3%.
    **Fix:** Continue V8 roadmap: lineup-level prediction, neural ensemble, context-specific sub-models.
    Ongoing



## Features Capability Roadmap — When Ready

  New capabilities from the feature-focused roadmap. All TODO.


    F1. Player-level prop projection pipeline
    Build prop projections for individual player stats (points, assists, rebounds, PRA). Would extend the engine from game-level to player-level predictions.
    Multi-dayNBA



    F2. Live in-game model for KairosEdge halftime trades
    Real-time model that evaluates halftime trade opportunities using live game state, score differential, and historical comeback rates.
    Multi-dayMulti-sport



    F3. Weather integration for outdoor sports (NFL/MLB)
    Quantify weather impact on totals and player performance for outdoor games. Wind, rain, cold, altitude.
    Half dayNFL/MLB



    F4. Automated daily scheduling (cron/Task Scheduler)
    Auto-run refresh → train → predict pipeline on schedule. Windows Task Scheduler or cloud cron.
    2-3 hours



    F5. Dashboard for model performance monitoring
    Interactive dashboard showing Brier skill over time, CLV trends, calibration curves, feature importance, bankroll trajectory.
    1-2 days



    F6. Telegram/Discord bot for auto-posting picks
    Automated pick delivery to Discord channels after daily pipeline runs. Formatted with confidence, edge, sizing.
    Half day



    F7. Bayesian opponent adjustment
    Replace static Barttorvik lookup with dynamic Bayesian updating. Ratings adjust in real-time as new games are played.
    1-2 daysNCAAB



    F8. Multi-sport parlay correlation engine
    Detect correlated outcomes across games for parlay construction. Identify which legs are truly independent vs secretly correlated.
    Multi-dayMulti-sport



## Analysis Root Causes (5)

  These drive ~60% of the bandaids. Fix these and many patches become unnecessary.


    1. XGBoost Margin Compression at Extreme Spreads
    Tree-based predictions regress toward mean at tails. Drives SPREAD_CAP, margin correction, favorite sizing haircuts.
    Partially Fixed — Auto recalibration addresses drift (#C6). SPREAD_CAP avoids worst zone. Root cause (non-linear compression) remains.
    **Remaining items:** G2, G3, G9



    2. Missing/Stale Data Sources
    No universal data quality layer. Missing data silently replaced with league averages. Covariate shift with zero visibility.
    Partially Fixed — Barttorvik daily scrape, PBP features, referee module all added. But no fallback tracking (G1) or error surfacing (G8).
    **Remaining items:** G1, G8, M3



    3. No Automated Recalibration on Retrain
    Sigma, margin correction, R² calibrated once and frozen. Each retrain changes behavior but constants drift.
    FIXED — Auto OLS recalibration on every retrain. Sigma optimized from calibration fold.
    **Remaining items:** G6 (totals R² still hardcoded), M5 (NIT sigma still a guess)



    4. Symptom-Level Fixes Instead of Calibration Fixes
    Favorites lose → cut sizing. Picks too many → add caps. Layers of interacting patches instead of fixing root calibration.
    Not Fixed — FAV_SIZE_HAIRCUT, probability clipping, volume caps all still active.
    **Remaining items:** G3, G9, M1, M7



    5. Train/Serve Feature Mismatch
    Training and live see different data. Injuries shifted in training, real-time live. Name maps were duplicated (now fixed). Neural model statics were zeros (now fixed).
    Partially Fixed — Neural statics fixed (#C3), name maps consolidated (#C4). Injury skew remains (G4).
    **Remaining items:** G4



## Reference V8 Architecture Plan

  Long-term upgrades from V8_ARCHITECTURE_PLAN.md


    v7.7: Play-by-Play Features
    4 PBP features added (second_chance, fastbreak, paint, tov_battle). Historical training defaults to 0, active in live predictions.



    v7.8: Lineup-Level Prediction
    Predict margin using projected starters + rotation RAPM values, not just team averages. Estimated +2-4% Brier. Needs lineup data source (Rotowire/ESPN projected starters).
    1 week



    v8.0: Neural Sequence Model
    LSTM architecture built and running in shadow mode. Static features fixed. But model severely disagrees with XGB (see G7). Needs re-evaluation and potentially retraining with global normalization.
    2-3 weeks full build
