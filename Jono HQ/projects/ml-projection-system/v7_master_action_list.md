# v7 Master Action List

Gaps + Bandaids — Deduplicated & Prioritized — March 28, 2026

  7Critical /
Do Now
  9Next
Sprint
  8When
Ready
  5Root
Causes


## Critical Do Now



      1. NCAAB Injury Feature Not Wired Into Model
      Gap

    The `injury_scraper.py` for NCAAB was added March 27, but the 13-feature NCAAB pipeline has no injury feature. The scraper exists, the model has capacity for more features, they're just not connected. During March Madness, a key player being questionable massively shifts outcomes and the model is blind to it.
    **Fix:** Wire `get_ncaab_injury_impact()` into the NCAAB live features builder. Add `injury_impact_diff` as feature 14. Historical training rows will have 0 for this feature — the model will learn to use it when non-zero at prediction time. ~30 min.

      ncaab/features.py
      NCAAB
      30 min





      2. NCAAB Barttorvik Ratings Are Season-Level (Stale by March)
      Gap

    All 10 core Barttorvik features are season-level snapshots. By late March, these represent 4-5 months of aggregated data and can't capture a team that's peaking or declining into the tournament. The `rolling_margin_diff` feature (r=0.457) partially compensates, but the primary feature set is stale. The NCAAB 1-5 collapse on March 20 likely reflects this.
    **Fix:** Daily Barttorvik scrape → store timestamped ratings (date, team, adj_off, adj_def, barthag, etc.) → at prediction time, use the most recent pre-game snapshot instead of season-level. ~2-3 hours.

      ncaab/features.py
      NCAAB
      2-3 hours





      3. Neural Static Features Are Placeholder Zeros
      Bandaid

    The LSTM's 5 static features: `elo_diff` (real), `pace_matchup=0`, `rest_advantage=0`, `injury_impact_diff=0`, `home_team_hca=1.0`. Four of five are hardcoded placeholders. The model makes predictions from sequences alone with no matchup context. You can't evaluate whether the neural ensemble is worth promoting while it's running crippled.
    **Fix:** The feat_df already computes rest_advantage, injury_impact_diff, pace_matchup, and home_team_hca for XGBoost. Pipe them through to the neural model's static input in `neural_shadow.py`. ~30 min.

      shared/neural_shadow.py
      NBA
      30 min





      4. NCAAB Name Mapping Fragile + Duplicated
      Bandaid

    190+ manual ESPN→Barttorvik name mappings in a `MANUAL` dict, copy-pasted into both `build_ncaab_training_data()` and `build_ncaab_live_features()`. If mappings diverge, training and live see different teams. If a mapping is missing, the game is silently dropped with no warning. One missing team = one missed +EV opportunity you never know about.
    **Fix:** Consolidate into a single `name_map_bart.json` (one already exists at `ncaab/models/name_map_bart.json`). Load from that file in both functions. Add a validation check: for every team in tonight's games, does a mapping exist? Log a warning if not. Add fuzzy-match fallback. ~1 hour.

      ncaab/features.py
      NCAAB
      1 hour





      5. Add Play-by-Play Features to NBA
      Gap

    V8 architecture plan identifies transition rate, clutch performance, second chance rate, turnover quality, and paint scoring as key PBP features. Estimated +1-3% Brier improvement. Data available via nba_api for all 15 training seasons. Two teams with identical offensive ratings but different scoring profiles perform very differently against different defensive styles.
    **Fix:** Start with 2 PBP features: `transition_pts_L10_diff` and `paint_pts_L10_diff`. Add as features 22-23, retrain, check Brier improvement. If >0.5%, add the rest (clutch, second chance, TOV quality). ~half day.

      nba/features.py
      NBA
      Half day





      6. Margin Correction & Sigma Never Re-Estimated on Retrain
      Bandaid

    `MARGIN_CORRECTION = {"nba": (1.172, -0.45, 12.7)}` and `SPORT_SIGMA = {"nba": 11.5}` are hardcoded constants calibrated once and frozen. XGBoost's compression behavior changes with each retrain as the training data shifts. These should be recomputed from the calibration fold every time you retrain, not treated as permanent constants.
    **Fix:** In `train_and_save()`, after fitting XGBoost on the train fold, compute slope/intercept from calibration fold residuals via OLS. Store in model metadata alongside the .json model file. Same for sigma — compute from calibration fold prediction errors. ~10-15 lines of code.

      v7_daily.py
      Both
      1 hour





      7. 20+ Fallback Defaults Silently Masking Missing Data
      Bandaid

    Across features.py and totals_engine.py, missing stats are silently replaced with league averages: PPG→110, pace→98, eFG%→52, TOV%→13, FTR→27, OREB→10, HCA→3.0. The blanket `fillna(median)` in training does the same. This treats "data missing" as "perfectly average team" — a covariate shift that corrupts predictions without any visibility. No logging of which games used fallback data.
    **Fix:** (a) Add a `data_quality` column that counts how many features used fallback values per game. (b) Log a warning when >2 features are fallback. (c) Consider skipping games where critical features (net_rating, elo, four_factors) are all missing. (d) At minimum, track fallback usage in pick logs so you can audit. ~2 hours across all files.

      nba/features.py, ncaab/features.py, totals_engine.py
      Both
      2 hours




## Important Next Sprint



      8. Favorite Compression at Extreme Spreads
      Gap Bandaid

    XGBoost predicts avg margin of 5.4 at 18+ point spreads vs actual 25.5 — a 79% compression rate. The current patches: `SPREAD_CAP=15` (avoids the worst zone), `MARGIN_CORRECTION slope=1.172` (linear stretch), and the removed market shrinkage. These are three separate bandaids on the same root cause. The linear correction can't fix a fundamentally non-linear problem.
    **Fix:** (a) Train a separate "blowout model" for spreads >12, or (b) use quantile regression for the tails, or (c) predict `sign(margin) * log(1 + |margin|)` during training and reverse at inference. Option (c) is simplest — 5 lines in `train_margin_model()`. Then remove the SPREAD_CAP and static margin correction.

      shared/engine.py, v7_daily.py
      NBA
      Half day





      9. Favorite Sizing Haircuts Masking Calibration Problem
      Bandaid

    After favorites went 4W-7L, three patches were added: `FAV_SIZE_HAIRCUT=0.75` (25% Kelly reduction for all favorites), `FAV_SPREAD_MIN_EDGE=0.02` (extra 2% edge requirement), and `sz = min(sz, 0.25)` (hard cap dog exposure). These treat the symptom — favorites losing — by throttling sizing. If the model's favorite calibration improves (or was just on a variance run), these patches actively cost you money on correct favorite picks.
    **Fix:** Investigate the root cause: is the model overestimating favorite win probability, or was 4W-7L variance? Run a calibration check on favorites specifically — plot predicted win% vs actual win% for favorites only. If calibrated correctly, remove the haircuts. If miscalibrated, fix calibration (isotonic/Platt on favorites bucket) rather than penalizing at sizing time.

      v7_daily.py
      NBA
      2-3 hours





      10. Injury Train/Serve Skew
      Gap

    Training uses injury data shifted by 1 game (to prevent leakage). Live prediction uses real-time injury reports (tonight's actual status). The model learned injury impact from a weaker, delayed signal but receives a stronger, current signal at inference. Systematic mismatch in what the model learned vs what it sees.
    **Fix:** Two options: (a) At prediction time, use "previous game" injuries for consistency with training, then add real-time injuries as a separate additive adjustment outside the model. (b) Retrain with two columns: `baseline_injury_diff` (shifted) + `realtime_injury_diff` (current, weighted lower). Option (a) is safer.

      nba/features.py, nba/injury_scraper.py
      NBA
      2-3 hours





      11. No Home/Away Splits in Features
      Gap

    The model has `home_team_hca` (rolling L20 home margin) but doesn't capture how specific teams perform differently home vs away in key stats. Some teams shoot 5% better eFG at home. Features treat L10 offensive rating the same regardless of venue.
    **Fix:** Add `home_efg_diff_ha`, `home_pace_diff_ha`, `home_def_rating_diff_ha`. Three new features, minimal risk, computed from data already in the pipeline.

      nba/features.py
      Both
      1-2 hours





      12. Totals Model Underpowered (8 Features, Sigma 19.57)
      Gap Bandaid

    Only 8 features with sigma=19.57 means the model can rarely clear the 4% edge threshold. The hardcoded `totals_r2=0.12` is a guess, not computed from holdout data. The 0.75 Kelly haircut further throttles sizing. Totals in NBA have lower market efficiency than sides — there's edge to capture but not with this feature set.
    **Fix:** (a) Add features: four factors diffs, rest/B2B, defensive matchup quality, ref pace tendencies → target 14-16 features. (b) Compute totals_r2 from actual holdout residuals during training. (c) Investigate if sigma is inflated by OT games — trim from calibration. (d) Remove the 0.75 haircut once calibration is honest.

      shared/totals_engine.py
      NBA
      Half day





      13. Neural Model Severely Disagrees with XGBoost
      Gap

    Shadow logs: neural LSTM predicts avg margin 1.2 pts (stdev 2.2) vs XGBoost 3.3 pts (stdev 10.3). They disagree on pick side ~70% of games. This isn't a useful ensemble — it's two models that see different things. The per-sequence normalization in `neural_shadow.py` may be destroying cross-game signal.
    **Fix:** (a) Evaluate neural Brier skill on the same holdout set as XGBoost — if

      shared/neural_shadow.py, nba_neural_model.py
      NBA
      1-2 days





      14. Silent Error Swallowing Across Pipeline
      Bandaid

    Six separate `except Exception` blocks catch all errors (including bugs) and continue with degraded data: totals import, neural shadow import, neural shadow execution, timezone parsing (bare `except:`), injury loading, elo loading. When something breaks, you don't know — the pipeline produces picks that look normal but are based on zeroed-out features.
    **Fix:** (a) Replace bare `except:` with specific exception types (`ImportError`, `ValueError`, `FileNotFoundError`). (b) Add a `warnings` list that gets printed in the pick summary: "This run used fallback data for: injuries, elo, totals." (c) For the neural shadow, log the full traceback, not just the message. ~1 hour.

      v7_daily.py, nba/features.py
      Both
      1 hour





      15. Probability Clipping Hides Calibration Issues
      Bandaid

    `np.clip(probs, 0.01, 0.99)` applied in three places: isotonic fitting, smoothed isotonic output, and Venn-ABERS output. This prevents log(0) errors but also silently caps any prediction the model is highly confident about. The 0.75u Kelly cap (`min(..., 0.75)`) does the same at the sizing level. If calibration is correct, these caps cost you money on your best plays.
    **Fix:** (a) Use a tighter but justified bound like [0.02, 0.98] based on your actual calibration curve — check if ANY of your predictions should genuinely be >98%. (b) For Kelly cap, replace fixed 0.75u with a bankroll-percentage-based max (e.g., 2% of bankroll) that scales naturally.

      shared/engine.py, v7_daily.py
      Both
      30 min





      16. XGBoost Eval Set Uses Random Sampling (Not Temporal)
      Bandaid

    Code comment explains: temporal early stopping is biased because the most recent games have the highest decay weights, so they'd dominate the eval set. The workaround is random sampling with `RandomState(42)`. This leaks future information into early stopping — games from 2025 can influence when training on 2020 data stops.
    **Fix:** Use temporal early stopping but weight the eval set by the same sample weights used in training. This preserves temporal integrity while avoiding the "recent games dominate" problem. Alternatively, use a fixed time window (e.g., last 60 days before the calibration fold) as the eval set.

      shared/engine.py
      Both
      1 hour




## Maintenance When Ready



      17. Contrarian/Motivation Boosts Unvalidated
      Bandaid

    `CONTRARIAN_EDGE_BOOST=0.01` (+1% for fading public teams), `MOTIVATION_EDGE_BOOST=0.015` (+1.5% for motivation mismatches), `ELIM_WIN_PCT_THRESHOLD=0.350`, `CLINCH_WIN_PCT_THRESHOLD=0.700`, `LATE_SEASON_GAME_THRESHOLD=60`. All hardcoded, none backtested against your own results.
    **Fix:** After 100+ tagged picks, compute actual win rate in contrarian/motivation-tagged vs untagged spots. If tagged picks don't outperform, set boosts to zero. If they do, calibrate the boost size from data.

      v7_daily.py
      NBA
      1 hour





      18. Line Shopping Ignores Book Health
      Gap

    `best_home_spread` / `best_away_ml` take the best number across ALL books from the Odds API. You may be limited or restricted at some of those books. Edge calculations using consensus lines may overstate actual available edge.
    **Fix:** Add a `HEALTHY_BOOKS` config list. Filter in `pull_odds()`. ~10 lines.

      v7_daily.py
      Both
      15 min





      19. Manual Data Refresh Before Picks
      Gap

    `v7_daily.py refresh` must be run manually. If forgotten, picks run on stale features. No staleness check at the top of `run_picks()`.
    **Fix:** Add a staleness check at the top of `run_picks()` — if database doesn't have today's date, auto-run refresh. Or Windows Task Scheduler.

      v7_daily.py
      NBA
      30 min





      20. No Automated Grading Pipeline
      Gap

    Grading exists but it's unclear if results are systematically logged with enough detail for `model_health.py`. The health monitoring tool exists but isn't wired into the daily pipeline.
    **Fix:** Ensure every pick log gets a result log with W/L, actual score, CLV, units +/-. Wire `model_health.py` to run automatically weekly.

      v7_daily.py, tools/model_health.py
      Both
      1-2 hours





      21. NIT Sigma Inflation Is a Guess
      Bandaid

    `game_sigma = sigma * 1.15` for NIT neutral games — a hardcoded 15% uncertainty bump because "we don't have enough NIT data to calibrate properly." No validation that 1.15 is the right multiplier vs 1.05 or 1.30.
    **Fix:** Collect NIT game residuals over multiple seasons and compute the actual sigma. If not enough data, use all neutral-site games as a proxy.

      v7_daily.py
      NCAAB
      1 hour





      22. Hardcoded Tournament Team Lists
      Bandaid

    `NCAA_TOURNAMENT_TEAMS` and `CBC_TEAMS` are manually updated sets. These go stale if the bracket changes and need annual maintenance. `PUBLIC_TEAMS_NBA` for contrarian logic is also static.
    **Fix:** Pull from an authoritative source (ESPN API, NCAA bracket API) or at minimum move to a JSON config file that's easier to update than embedded Python sets.

      v7_daily.py
      NCAAB / NBA
      1 hour





      23. Pick Volume Caps Instead of Threshold Tuning
      Bandaid

    `MAX_PICKS_PER_DAY=3` per sport and `MAX_PICKS_COMBINED=6` drop the lowest-edge picks when the model generates too many. This is a portfolio constraint masquerading as a fix for the model outputting too many marginal edges.
    **Fix:** If the model consistently produces >6 qualifying picks, the edge thresholds (NBA 5%/6%, NCAAB 3%/4%) are too low. Raise thresholds until natural pick volume is 4-6 per day. The caps can remain as a safety net but shouldn't be binding daily.

      v7_daily.py
      Both
      30 min





      24. Low R² Caps Maximum Edge (Ongoing)
      Gap

    NBA R²=0.14, NCAAB R²=0.10. The market already prices 86%+ of what the model knows. This caps maximum possible edge at ~2-3% on most games. This isn't a "fix" — it's the fundamental constraint. Gains from here come from PBP features, lineup-level prediction, context-specific sub-models, and eventually neural ensemble.
    **Fix:** Continue the V8 roadmap: PBP features (#5), lineup-level prediction (v7.8), neural ensemble (v8.0). Also consider training separate models for high-R² contexts (B2B games, large rest advantages, divisional matchups) where the model may explain more variance.

      Entire system
      Both
      Ongoing




## Analysis Root Causes Behind the Bandaids

  Most bandaids trace back to five root problems. Fix these and ~60% of the patches become unnecessary.


    1. XGBoost Margin Compression at Extreme Spreads
    XGBoost's tree-based predictions regress toward mean values at the tails. This drives the SPREAD_CAP, the margin correction slope, the removed market shrinkage, and indirectly the favorite sizing haircuts.
    **Items caused:** #6, #8, #9, #15



    2. Missing/Stale Data Sources
    The pipeline has no universal "data quality" layer. When sources fail or return stale data, features silently fall back to hardcoded league averages. This creates covariate shift between good-data games and bad-data games with no visibility.
    **Items caused:** #2, #7, #10, #14, #19



    3. No Automated Recalibration on Retrain
    Sigma, margin correction, and R² are calibrated once and hardcoded. Each retrain changes the model's behavior but the downstream parameters stay frozen, creating drift between model output and calibration assumptions.
    **Items caused:** #6, #12, #21



    4. Symptom-Level Fixes Instead of Calibration Fixes
    When favorites underperform, the response is sizing haircuts — not investigating whether calibration is wrong. When picks exceed volume, the response is caps — not raising thresholds. This pattern creates layers of patches that interact unpredictably.
    **Items caused:** #9, #15, #17, #23



    5. Train/Serve Feature Mismatch
    Training and live prediction don't always see the same data. Injuries are shifted in training but real-time in live. Name mappings are duplicated and can diverge. Neural model trains on placeholder zeros but the plan is to eventually fill them in live. Each mismatch means the model's learned coefficients are miscalibrated for what it actually sees.
    **Items caused:** #3, #4, #10
