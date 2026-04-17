# v7 Engine Gap Analysis

NBA & NCAAB ML Projection System — March 28, 2026


## Current State


    56.2%NBA Win Rate (18-14)
    +2.00uNBA Units
    52.9%NCAAB Win Rate (18-16)
    +0.83uNCAAB Units
    21NBA Features
    13NCAAB Features
    17,709NBA Training Games
    18,854NCAAB Training Games



## Critical Architecture Gaps


    1. NBA Favorite Compression Still Unsolved

      The model compresses predictions toward the mean at extreme spreads. At 18+ point spreads, the model predicts an avg margin of 5.4 vs actual 25.5 — a **79% compression rate**. The linear margin correction (`slope=1.172`) helps but can't fix a fundamentally non-linear problem. The current bandaid is `SPREAD_CAP=15`, which just avoids the worst zone rather than fixing it.

    **Impact:** Losing edge on all games with large spreads. Today's MIL/SAS game (spread 18.5) gets pred_margin of -11.2 — the model literally can't see blowouts coming.

      **Fix:** Train a separate "blowout model" for spreads >12, or use a quantile regression approach that explicitly models the tails. Alternatively, use the log-transform trick: predict `sign(margin) * log(1 + |margin|)` during training and reverse at inference.




    2. Model R² is Only 0.14 (NBA) / 0.10 (NCAAB)

      These are honest numbers and the market shrinkage system correctly accounts for them. But 0.14 means the model explains only 14% of variance — the market already prices 86%+ of what the model knows. This caps the maximum possible edge at ~2-3% on most games, making volume (not conviction) the main lever.

    **Impact:** The shrinkage function (`market_shrink_edge`) aggressively discounts edges when the model disagrees with the market by more than ~5 pts. This is correct behavior given R²=0.14, but it means the model rarely outputs high-confidence plays.

      **Fix:** The V8 play-by-play features and lineup-level prediction are the right path. Also consider: (a) adding a "model confidence" feature from the ensemble disagreement, (b) training separate models for different game contexts (B2B, rest advantages, divisional games) where the model may have higher local R².




    3. NCAAB Uses Season-Level Barttorvik Ratings (Stale by March)

      NCAAB features come from Barttorvik season-level snapshots. By late March, these are 4-5 months of aggregated data — they can't capture a team that's on a recent hot/cold streak within the season. The v7.5 rolling_margin_diff feature (`r=0.457`) partially addresses this, but the core 10 Barttorvik features are still season-level.

    **Impact:** March Madness is where this hurts most. Tournament teams are peaking/declining, but the model sees only their season-long profile. The NCAAB 1-5 collapse on March 20 likely reflects this staleness.

      **Fix:** Pull Barttorvik data more frequently (daily scrape → store timestamped ratings → use the most recent pre-game snapshot). This is the single highest-ROI improvement for NCAAB during March Madness.




## Important Feature Engineering Gaps


    4. No Home/Away Splits in Features

      The model has `home_team_hca` (rolling L20 home margin) but doesn't capture how specific teams perform differently home vs away in key stats. Some teams shoot 5% better eFG at home. The features treat a team's L10 offensive rating the same regardless of where those games were played.

    **Impact:** Moderate. Home/away eFG% split, home/away pace split, and home/away defensive rating could each add incremental signal, especially for extreme home-court teams (Denver, Utah).

      **Fix:** Add `home_efg_diff_ha` = (team's eFG% in home games L10) - (team's eFG% in away games L10). Same for pace and defensive rating. 3 new features, minimal risk.




    5. Injury Feature Uses Stale Data (Shifted by 1 Game)

      The training pipeline correctly shifts injury data by 1 game to prevent train/serve skew. But at prediction time, the `injury_scraper.py` pulls the actual real-time injury report. This means training sees "who was missing last game" while prediction sees "who is missing tonight" — a systematic mismatch.

    **Impact:** The model learned injury impact from stale signals, so it may underweight real-time injury data. The RAPM-based impact values are good, but the model's learned coefficients are trained on weaker (shifted) signals.

      **Fix:** Two options: (a) At live prediction time, also use "previous game" injuries for consistency with training, then add real-time injuries as a separate additive adjustment outside the model. (b) Retrain with a two-column approach: `baseline_injury_diff` (shifted, for model) + `realtime_injury_diff` (current, weighted lower because model hasn't learned from it).




    6. No Play-by-Play Features (V8 Plan Exists But Not Implemented)

      The V8 architecture plan identifies transition rate, clutch performance, second chance rate, turnover quality, and paint scoring as key PBP features. The data is available via nba_api for all 15 seasons. This was estimated as "+1-3% Brier, 2-3 days effort" but hasn't been built yet.

    **Impact:** These features capture HOW teams score, not just how much. Two teams with identical offensive ratings but one scores in transition and the other in half-court will perform very differently against different defensive styles.

      **Fix:** Start with just 2 PBP features to validate the signal: `transition_pts_L10_diff` and `paint_pts_L10_diff`. If they improve Brier skill by >0.5%, add the rest.




    7. NCAAB Missing Injury Feature Entirely

      NBA has RAPM-based injury impact as a feature. NCAAB has an `injury_scraper.py` that was added March 27, but the NCAAB feature set (13 features) has NO injury feature. The scraper exists but isn't wired into the feature pipeline or model.

    **Impact:** In March Madness, injuries to key players (like a team's leading scorer being questionable) massively shift game outcomes. The model is blind to this.

      **Fix:** Wire `get_ncaab_injury_impact()` into the NCAAB live features builder. Add `injury_impact_diff` as feature 14. Retrain on all data (the historical training data will have 0 for this feature since we don't have historical NCAAB injury data, but the model will learn to use it when it's non-zero at prediction time).




## Important Decision Layer & Bet Selection Gaps


    8. Contrarian/Motivation Boosts Aren't Validated

      The system adds +1% edge for contrarian plays (fading public teams) and +1.5% for motivation mismatches (eliminated vs playoff-bound). These are research-informed but the values are hardcoded, not calibrated to YOUR model's actual performance in these spots.

    **Impact:** If the +1% contrarian boost is wrong, it's pushing marginal plays over the threshold and adding losing volume. The boosts should be validated against your own results, not general research.

      **Fix:** Track contrarian and motivation tags in pick logs (already happening). After 100+ tagged picks, compute actual win rate in tagged vs untagged spots. If tagged picks don't outperform, remove the boost.




    9. Totals Model Has Huge Sigma (19.57) — Edge Is Thin

      The totals model uses sigma=19.57, meaning the standard deviation of total-point prediction error is ~20 points. With only 8 features and such high noise, the model can rarely generate edges above the 4% threshold. The 0.75 Kelly haircut further reduces sizing.

    **Impact:** Very few totals picks are being generated. The ones that pass are likely noisy. Totals in NBA have lower market efficiency than sides, so there IS edge to capture — just not with 8 features.

      **Fix:** Add more features to the totals model: four factors differentials, rest/B2B (huge impact on totals), defensive matchup quality, and referee pace tendencies. Aim for 14-16 features. Also investigate whether the sigma is inflated by outlier games (overtime, etc.) — trimming OT games from calibration may give a more accurate sigma.




    10. Line Shopping Logic Doesn't Consider Actual Available Books

      The `best_home_spread` / `best_away_ml` fields take the best number across ALL books from the Odds API. But you may be limited or restricted at some of those books. The system doesn't know which books you can actually bet at.

    **Impact:** Picks show "best line" that may not be available to you. Edge calculations using consensus lines may overstate actual edge on your available books.

      **Fix:** Add a `HEALTHY_BOOKS` config list. Filter `all_spreads` and `all_ml` to only include books you can actually bet at. This is 10 lines of code in `pull_odds()`.




## Infrastructure Data Pipeline Gaps


    11. NBA Data Refresh Is Manual

      `v7_daily.py refresh` must be run manually to update team_game_logs, Elo, etc. There's no automated daily pipeline. If you forget to refresh before running picks, you're predicting with stale features.


      **Fix:** Add a `refresh` step at the top of `run_picks()` — before pulling odds, check if the database has today's date. If not, auto-run the refresh. Alternatively, set up a Windows Task Scheduler job.




    12. No Automated Grading Pipeline in v7

      The memory doc says "v7 grading pipeline (not yet implemented in v7)" — grading appears to happen but it's unclear if results are systematically logged with enough detail for model health monitoring. The `model_health.py` tool exists but depends on graded picks having `result` fields.


      **Fix:** Ensure every pick log gets a matching result log with win/loss, actual score, CLV, and units +/-. The `model_health.py` tool is good — just needs to run automatically weekly.




    13. NCAAB Name Mapping Is Fragile

      190+ manual name mappings between ESPN and Barttorvik, plus fuzzy matching for the rest. The `MANUAL` dict is duplicated in both `build_ncaab_training_data()` and `build_ncaab_live_features()`. A mismatch between training and live means the model sees different teams.


      **Fix:** Consolidate all name maps into a single `name_map_bart.json` file (one already exists at `ncaab/models/name_map_bart.json`). Load from that file in both functions. Add a validation step that checks: for every team in tonight's games, does a mapping exist?




## Experimental Neural v8 Shadow Model Status


    14. Neural Model Dramatically Disagrees with XGBoost

      Shadow logs show the neural LSTM predicts much tighter margins (avg 1.2 pts, stdev 2.2) vs XGBoost (avg 3.3 pts, stdev 10.3). They disagree on the pick side in ~70% of games. This level of disagreement suggests either (a) the neural model is severely underfit, or (b) XGBoost is overfit on certain patterns.

    **Impact:** The planned 0.6 XGB + 0.4 Neural ensemble won't work well if one model is fundamentally miscalibrated. Ensembling two miscalibrated models doesn't fix calibration.

      **Fix:** Before ensembling, separately evaluate neural model Brier skill on the same holdout set as XGBoost. If neural Brier skill is <5%, it's underfit and needs (a) more training data (currently only 4 seasons for neural vs 15 for XGB), (b) better normalization, or (c) architectural changes. The within-sequence normalization in `neural_shadow.py` may be destroying signal — try normalizing against global means instead of per-sequence.




    15. Neural Static Features Are Mostly Placeholder Zeros

      The neural model's 5 static features are: `elo_diff` (real), `pace_matchup=0`, `rest_advantage=0`, `injury_impact_diff=0`, `home_team_hca=1.0`. Three of five are hardcoded zeros or constants. The model is making predictions mostly from sequences alone, without matchup context.


      **Fix:** Fill in the static features from the same data sources XGBoost uses. The feat_df already has rest_advantage, injury_impact_diff, pace_matchup, and home_team_hca — just pipe them through to the neural model's static input.




## Priority Matrix


| # | Gap | Sport | Impact | Effort | Priority |
| --- | --- | --- | --- | --- | --- |
| 3 | NCAAB stale Barttorvik ratings | NCAAB | High | Low | Do Now |
| 7 | NCAAB missing injury feature | NCAAB | High | Low | Do Now |
| 6 | No PBP features (NBA) | NBA | Medium-High | Medium | Do Now |
| 1 | Favorite compression at extreme spreads | NBA | High | Medium | Next Sprint |
| 5 | Injury train/serve skew | NBA | Medium | Medium | Next Sprint |
| 4 | No home/away splits in features | Both | Medium | Low | Next Sprint |
| 9 | Totals model thin features | NBA | Medium | Medium | Next Sprint |
| 14 | Neural model miscalibration | NBA | Medium | High | Next Sprint |
| 15 | Neural static features placeholder | NBA | Medium | Low | Next Sprint |
| 8 | Contrarian/motivation boost unvalidated | NBA | Low-Med | Low | When Ready |
| 2 | Low R² caps maximum edge | Both | High | Very High | Ongoing |
| 10 | Line shopping ignores book health | Both | Low | Low | When Ready |
| 11 | Manual data refresh | NBA | Low | Low | When Ready |
| 12 | No automated grading | Both | Low | Low | When Ready |
| 13 | NCAAB name mapping fragile | NCAAB | Low | Low | When Ready |


## Strengths What's Working Well



      **Raw margin regression architecture** — the core v7 decision to predict raw margin (not residual vs Vegas) is validated by both research and your results. Don't change this.




      **Market shrinkage (Baker-McHale)** — the `market_shrink_edge()` function is sophisticated and correctly accounts for model limitations. This prevents phantom edges from large disagreements.




      **Power devig** — using power method instead of multiplicative devig is the right call. Most systems use multiplicative, which overestimates longshot fair probability by 1-2%.




      **Dog outperformance** — NBA dogs at 13.2% avg edge vs favorites at 7.8% confirms the model finds real value on underdogs. The underdog filters (ML_DOG_CEILING=200, ML_DOG_MIN_EDGE=8%) are working.




      **Walk-forward validation discipline** — never using in-sample testing, 70/15/15 temporal splits, and paper-tracking before real money. This is the right methodology.




      **Sport-specific edge thresholds** — NBA 5%/6% vs NCAAB 3%/4% correctly reflects that the NBA market is sharper. Most amateur models use the same threshold for both.




      **Smoothed isotonic calibrator** — the custom `SmoothedIsotonicCalibrator` that interpolates between isotonic steps is a clever fix for the resolution-loss problem. Well-engineered.




## Recommended Next 3 Actions


    1. Wire NCAAB injuries into the feature pipeline (Gap #7)
    The scraper exists. The model has a slot. You just need to connect them. 30 minutes of work, immediate impact for remaining March Madness games.


    2. Add daily Barttorvik scrape for NCAAB (Gap #3)
    Store timestamped ratings (date, team, adj_off, adj_def, etc.) and use the most recent pre-game snapshot. This turns stale season-level features into near-real-time features. 2-3 hours of work.


    3. Add 2 PBP features to NBA (Gap #6)
    Start with transition points per game and paint scoring rate. Both are available from nba_api play-by-play. Add as features 22-23, retrain, and check if Brier skill improves. Half a day of work.
