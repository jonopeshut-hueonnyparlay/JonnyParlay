# Research Brief P4: Deep Audit & Remaining Opportunities

**Date:** 2026-05-01  
**Scope:** Exhaustive code-level review of `nba_projector.py`, `evaluate_projector.py`, `projections_db.py`  
**Prior briefs:** P1 (architecture), P2 (calibration), P3 (multi-stat decomposition + minutes)

---

## 1. Code-Level Issues & Inconsistencies

### 1.1 Evaluator / Projector Divergence — STL Path

**File:** `evaluate_projector.py` lines 269–283 vs `nba_projector.py` lines 644–648

The evaluator's `project_stl()` uses:
- `n_games=30` (projector uses 30 via `get_player_recent_games` call at line 498)
- `min_min=8.0` hardcoded (projector uses `_ROLE_MIN_MINUTES[role]` which is 8–20 depending on role)
- **Opponent TOV factor** (`opp_tov / LEAGUE_AVG_TOV_RATE`, clipped [0.80, 1.30])

But `nba_projector.py` line 647 uses:
```python
projections["stl"] = max(0.0, round(stl_rate * proj_min * pace_factor, 2))
```

The projector multiplies by `pace_factor` (generic possessions proxy), while the evaluator multiplies by `opp_tov_fac` (opponent-specific turnover tendency). **These are different models.** The evaluator's STL model is arguably better (steals correlate with opponent carelessness, not raw pace), but it's not what ships in production.

**Action:** Port the evaluator's `opp_tov_fac` logic into `nba_projector.py`'s STL projection. The evaluator already imports `get_team_tov_rate` — this is a free improvement sitting on the shelf.

### 1.2 Evaluator / Projector Divergence — BLK Path

**File:** `evaluate_projector.py` lines 286–297 vs `nba_projector.py` line 648

Evaluator's `project_blk()`:
- Uses `n_games=30`, `min_min=8.0`
- Pure `blk_rate * proj_min` — **no pace_factor**

Projector:
```python
projections["blk"] = max(0.0, round(blk_rate * proj_min * pace_factor, 2))
```

The projector applies `pace_factor` to BLK. This is theoretically debatable — blocks happen at the rim regardless of pace. Higher pace means more shot attempts, so more block opportunities, but the relationship is weaker than for counting stats like points. The evaluator omits it entirely.

**Action:** Run eval with and without pace_factor on BLK. If MAE is flat or worse with pace_factor, remove it. BLK is already the lowest-signal stat (CV=0.85) — adding noise via pace_factor could hurt.

### 1.3 Evaluator Uses Different `n_games` for Different Stats

- PTS/3PM/REB/AST: `n_games=20` (line 111, 244, 309)
- STL/BLK: `n_games=30` (lines 276, 292)
- Projector: `n_games=30` for ALL stats (line 498)

This means the evaluator is testing a *different model* than what ships for STL/BLK (same n_games=30) but a *different model* for PTS/REB/AST (20 vs 30 games). The projector fetches 30 games, then applies `_ROLE_MIN_MINUTES` filter which can reduce the effective sample, but the raw pull is 30.

**Action:** Align evaluator to pull 30 games and apply the same `_ROLE_MIN_MINUTES` filter per role. Currently it applies a flat `RATE_MIN_MIN=20.0` which is correct for starters but too aggressive for bench players (rotation min_min is 10, spot is 8).

### 1.4 `era_weight` in EWMA — Subtle Double-Counting

**File:** `nba_projector.py` lines 177–184

```python
per_min  = d[stat] / d["min"]
weighted = per_min * d["era_weight"]
ewma_w   = weighted.ewm(span=EWMA_SPAN, min_periods=1).mean().iloc[-1]
ewma_e   = d["era_weight"].ewm(span=EWMA_SPAN, min_periods=1).mean().iloc[-1]
rates[stat] = float(ewma_w / max(ewma_e, 1e-6))
```

This implements a weighted-EWMA where `era_weight` attenuates older seasons. But the data is already sorted `game_date` ascending and EWMA naturally decays older observations. The era_weight is *multiplied into* the signal before EWMA, then divided back out by a separate EWMA of the weights. This correctly down-weights older seasons, BUT:

**Problem:** If a player's last 30 games span only the current season (era_weight=1.0 for all), this collapses to `ewma_w / 1.0 = ewma_w` which is just a regular EWMA of `per_min * 1.0`. No issue. But if games span 2024-25 (0.75) and 2025-26 (1.0), the older games get a 0.75x multiplier *on top of* the EWMA's natural exponential decay. This is intentional and fine.

**Actual issue:** The denominator EWMA (`ewma_e`) uses `d["era_weight"]` with the same span, but this doesn't account for games that were *filtered out* by the `_ROLE_MIN_MINUTES` threshold. If a disproportionate number of filtered-out games come from one era, the weight normalization could be slightly off. In practice this is negligible — the filter removes low-minutes games uniformly across seasons.

**Verdict:** Not a bug but worth documenting. The weighted-EWMA approach is sound.

### 1.5 `compute_shooting_rates` — FT% EWMA Uses Forward Fill

**File:** `nba_projector.py` lines 387–391

```python
mask_fta  = d["fta"] > 0
ft_series = np.where(mask_fta, d["ftm"] / d["fta"], np.nan)
ft_vals   = pd.Series(ft_series).ffill().fillna(LG_FT_PCT)
```

When a player has 0 FTA in a game, the code forward-fills from the previous game's FT%. This is reasonable but subtly wrong when `d` is sorted ascending — `ffill()` fills forward in the array (toward newer games), which means a game with 0 FTA *copies the next game's FT%* because the sort is ascending and ffill goes down the series.

Wait — `d = df.sort_values("game_date").copy()` makes oldest first. `ffill()` fills NaN with the *previous* (older) value. So a game with 0 FTA gets the FT% from the game before it (older). This is correct behavior.

**Verdict:** No bug. The ffill direction is correct given ascending sort.

### 1.6 `implied_total` Overrides `pace_factor` Entirely

**File:** `nba_projector.py` lines 544–545

```python
if implied_total is not None and implied_total > 0:
    pace_factor = implied_total / LEAGUE_AVG_TOTAL
```

When Vegas implied total is available, it completely replaces the pace_factor derived from team/opp historical pace. This is correct in principle (Vegas totals incorporate pace, injuries, rest, etc.), but there's a subtle issue:

**The denominator is wrong for decomposed stats.** `pace_factor` is used in multiple places:
1. PTS FGA decomposition: `team_proj_fga = team_avg_fga * pace_factor` (line 589)
2. STL: `stl_rate * proj_min * pace_factor` (line 647)
3. BLK: `blk_rate * proj_min * pace_factor` (line 648)
4. TOV: `tov_rate * proj_min * pace_factor` (line 652)

For PTS: `team_avg_fga * (implied_total / 222.0)` — this scales team FGA attempts by how high/low the total is relative to league average. A game with implied total 230 gets `pace_factor = 1.036`, boosting FGA by 3.6%. This is reasonable.

For STL/BLK/TOV: Applying this same factor uniformly is a rough proxy. STL and TOV should scale with possessions (which the implied total partially captures), but BLK doesn't necessarily scale the same way.

**Action:** Consider stat-specific pace factors. STL/TOV could use possessions; BLK might use opponent 2PA rate (blocks happen on drives/post-ups, not 3s); REB already has its own decomposition.

### 1.7 `PLAYOFF_DEFLATOR` Applied Uniformly

**File:** `nba_projector.py` lines 656–659

```python
if is_playoff:
    PLAYOFF_DEFLATOR = 0.92
    for stat in PROJ_STATS:
        projections[stat] = round(projections[stat] * PLAYOFF_DEFLATOR, 2)
```

A flat 8% reduction to ALL stats in playoffs. This is extremely blunt:
- PTS: Playoff defense tightens, pace drops → deflation makes sense, but 8% is a guess
- AST: Could actually *increase* in playoffs (more half-court sets, more ball movement)
- STL: Often increases in playoffs (more aggressive defense)
- REB: Game-dependent — tighter shooting means more rebounds available
- BLK: Often increases (more rim protection emphasis)

**Action:** Stat-specific playoff adjustors, calibrated from historical playoff vs regular-season per-minute rates in the DB. The data exists (`season_type = "Playoffs"` in games table). Compute actual playoff/regular-season ratios per stat per position group.

### 1.8 Cold-Start Rates Not Decomposed

**File:** `nba_projector.py` lines 504–508

```python
if is_cold_start:
    role     = "cold_start"
    rates    = cold_start_rates(position)
    rates    = {k: v / 36.0 for k, v in rates.items()}
    df_clean = df
```

Cold-start players get archetype per-36 rates converted to per-minute, then go through the same `project_minutes * rate * pace * matchup` path. BUT: `df_clean = df` (the unfiltered dataframe) gets passed to `compute_shooting_rates(df_clean)` at line 567. If the player has *some* games (1–4, since `MIN_GAMES_FOR_TIER=5`), those games will produce shooting rates. If they have 0 games, `compute_shooting_rates` returns league-average defaults.

**Issue:** For a player with 2–4 games, shooting rates will be computed from a tiny sample with heavy Bayesian shrinkage (padded to 300/750 FGA). The archetype-based per-minute PTS rate and the FGA-decomp PTS will diverge significantly. The 50/50 blend then averages two unreliable estimates.

**Action:** For cold-start players, weight the blend heavily toward the per-minute archetype (alpha=0.20 or less) since the shooting rates are almost entirely prior-driven anyway.

### 1.9 Missing DvP for STL, BLK, TOV

**File:** `nba_projector.py` lines 554–557

```python
matchup_factors = {
    "pts": matchup_pts, "reb": matchup_reb, "ast": matchup_ast,
    "fg3m": matchup_pts, "stl": 1.0, "blk": 1.0, "tov": 1.0,
}
```

STL, BLK, and TOV have hardcoded neutral matchup factors. The `team_def_splits` table computes ratios for ALL 7 stats including stl, blk, tov (see `_DEF_STATS` in projections_db.py line 46). The data exists but isn't used.

**Action:** Enable DvP for STL and BLK. TOV is tricky (high TOV against a team = they force turnovers = bad for the player) — the sign is inverted from the other stats. STL should use `get_team_def_ratio(opp_team_id, pg, "stl", season, db_path)` with appropriate clipping.

However, be cautious: STL/BLK DvP may be noisy given the high CV of these stats. Test via evaluator before shipping.

---

## 2. Methodology Gaps

### 2.1 Pace Modeling — Only Season-Level

The DB stores pace in `team_season_stats` — one value per team per season. This is a 82-game average. In reality:
- Teams play at different paces against different opponents
- Pace has significant game-to-game variance (σ ≈ 4–5 possessions)
- Back-to-backs tend to be lower pace
- Home teams play slightly faster

**Current approach:** `game_pace = (team_pace + opp_pace) / 2` — uses season averages.

**What's missing:**
- Recent-game pace trend (last 5–10 games EWMA)
- Opponent-adjusted pace (some teams force pace down regardless of matchup)
- The implied_total override partially fixes this (Vegas prices pace in), but only when that data is passed in

**Improvement path:** Compute rolling 10-game pace from the box scores in the DB. The data exists: `team_season_stats` is season-level, but you can derive game-level pace from `SUM(pgs.fga) + 0.44*SUM(pgs.fta) + SUM(pgs.tov) - SUM(pgs.oreb)` per team per game. Build a rolling pace EWMA per team, then compute `game_pace = (team_rolling_pace + opp_rolling_pace) / 2`.

**Expected impact:** Small but consistent (±0.5–1.0 possessions per game ≈ ±1–2% on projection). Biggest impact on pace-up/pace-down matchup extremes.

### 2.2 Home/Away Splits — Completely Missing

The projector has no concept of home vs away. It doesn't even receive this information (no `is_home` parameter in `project_player()`).

**Known effects:**
- Home teams average +3.2 points (NBA 2024-25)
- Home players get more FTA (+0.8/game average)
- Some players have extreme home/away splits (Denver altitude, crowd effects)
- Referee whistle bias toward home team is measurable

**The DB has this data:** `games` table has `home_team_id` and `away_team_id`. You can determine if a player is home or away for every game in their history.

**Implementation path:**
1. Add `is_home` parameter to `project_player()`
2. Compute home/away per-minute rate split from recent games
3. Apply a small multiplicative adjustment (1.02–1.05 for home, 0.95–0.98 for away) per stat
4. Or better: compute separate EWMA rates for home/away games if sample is sufficient (≥5 games each)

**Expected impact:** Material for PTS (+1.5–2.0 pts home vs away for many players) and FTA-dependent stats.

### 2.3 Altitude Effects (Denver)

Denver's altitude (5,280 ft) is a known statistical outlier:
- Visiting teams average 2–3 fewer points in Denver
- Fatigue effects compound in 2nd half
- Denver players' home/away splits are inflated by altitude advantage

**Current handling:** None. DvP captures some of this (Denver's defense looks good because visitors underperform), but it's diluted across 82 games and doesn't distinguish the *mechanism* (altitude fatigue vs. actual defensive quality).

**Implementation path:** Could be folded into home/away split modeling. If Denver is home, apply additional fatigue factor to visiting players' minutes/efficiency. Simple binary: `if opp_team_id == DENVER_TEAM_ID and not is_home: apply_altitude_penalty`.

**Expected impact:** Small (1–2 games per week involve Denver), but edge-valuable because books may underprice it for specific visiting players.

### 2.4 Opponent Defensive Rankings — Too Coarse

Current DvP uses `team_def_splits` grouped by G/F/C position groups, covering 7 stats. This is the right structure but:

**Problem 1: Position groups are too broad.** A player listed as "F" could be a stretch-4 (mostly perimeter) or a traditional PF (mostly interior). Their matchup profile is very different. The height-based position inference (`pull_player_positions`) puts ≤76" → G, 77–80" → F, ≥81" → C. This puts 6'5" SGs and 6'8" SFs in the same bucket.

**Problem 2: Season-level DvP doesn't capture recent trends.** A team that just traded away their best perimeter defender will have a DvP that still reflects the full season with that player.

**Problem 3: No stat-specific decomposition for DvP.** The PTS DvP is used for both PTS and 3PM (`"fg3m": matchup_pts` at line 556). Teams can be good at defending 3s but bad at interior defense, or vice versa.

**Improvement path:**
1. Use `fg3m` DvP from `team_def_splits` directly for 3PM (the data exists, just not wired)
2. Consider rolling DvP (last 15–20 games) rather than full-season
3. Longer term: 5-position grouping (PG/SG/SF/PF/C) requires richer position data

**Action (immediate):** Wire `matchup_factors["fg3m"]` to use `get_team_def_ratio(opp_team_id, pg, "fg3m", season, db_path)` instead of piggybacking on PTS DvP.

### 2.5 Usage Rate Changes with Teammates In/Out

The engine has an `injury_minutes_override` system for redistributing minutes when a player is out. But it doesn't model **usage rate** changes — the biggest lever for props.

When a team's primary scorer is out:
- Secondary scorers' USG% jumps 3–8%
- Assists often shift dramatically
- Minutes alone don't capture this — a player can play the same minutes but with 30% USG instead of 22%

**Current approach:** `injury_minutes_override` adjusts projected minutes and potentially promotes role tier (line 519–525). But the actual USG% used in the FGA decomposition comes from the player's historical EWMA, which still reflects games WITH the injured teammate.

**The fix:** When injury_minutes_override is set, also adjust `usg_pct` upward proportionally. A simple heuristic: if minutes increase by X%, USG increases by X%/2 (capped at 35%). Or better: look at the player's recent games without the injured teammate if sample exists.

**Expected impact:** Large. This is one of the biggest edges in prop betting — books are slow to adjust lines for injury-driven usage spikes.

### 2.6 Garbage Time / Blowout Effects on Counting Stats

The sigmoid blowout model (lines 71–77) reduces *minutes* for blowouts. But:

**Problem:** Starters who get pulled early in blowouts → fewer counting stats. BUT bench players who come in for garbage time often *pad* stats against soft defense. The current model applies the same blowout penalty to everyone.

**What's missing:**
- Bench players should get *increased* minutes in blowouts (they play the 4th quarter)
- Starters in blowout wins accumulate at a higher rate (up big, running fast, opponent demoralized) until pulled
- The direction of the blowout matters: your team winning → your players already accumulated stats in Q1-Q3; your team losing → opponent's starters still in, your players facing full defense

**Implementation path:**
- Blowout minutes adjustment should be role-conditional: starters get reduced, bench gets increased
- When spread > 12 AND team is favored (negative spread): starter gets -8–15% minutes, bench player gets +10–20% minutes
- When spread > 12 AND team is underdog: starters might play full game trying to keep it close

### 2.7 Correlation Between Stats

The projector treats each stat independently. But stats are correlated:
- PTS and FGA: mechanically linked (more shots = more points)
- AST and teammate PTS: assists require made baskets
- REB and minutes: nearly linear
- PTS + REB + AST (PRA combo): correlated through minutes

**Why this matters for betting:** When the model projects a player above/below the line on *multiple* correlated stats, the true probability of hitting isn't independent. For SGP/parlay construction, understanding correlation is critical.

**Not an immediate projector fix** — this lives in the betting engine's SGP builder. But the projector could output a correlation matrix or covariance estimate alongside point projections. The `compute_distribution` function (line 479) assumes independent normal distributions per stat — it should eventually use a multivariate distribution.

### 2.8 Season Segment Trends

The EWMA span=10 naturally captures recent trends. But there are systematic season-segment effects:
- **October–November:** Players ramp up, stats often below season norms
- **January–February:** Peak regular season performance
- **March–April:** Rest/tanking/load management spikes
- **Playoffs:** Tighter rotations, higher intensity (partially captured by PLAYOFF_DEFLATOR)

The era_weight system handles *across-season* decay but not *within-season* segments. A player's October stats from this season get the same weight as their March stats.

**Current mitigation:** EWMA span=10 means only the last 10 games dominate. If it's April, October games from the same season have decayed significantly. This naturally handles most segmentation.

**Verdict:** Low priority. EWMA already does most of the work here.

### 2.9 Referee Tendencies

Some referee crews are measurably different:
- High-foul crews: +2–4 FTA per team per game
- Fast/slow whistle affects pace (technical FTs, stoppages)
- Some refs call fewer charges → more drives → more PTS/FTA

**The data doesn't exist in the DB** and would require scraping referee assignments + correlating with game outcomes. This is a separate data pipeline.

**Expected impact:** Small for most games but material for FTA-dependent projections and totals.

**Verdict:** Defer until core projector stabilizes. Could be a future addon via Basketball Reference referee data.

---

## 3. Data Pipeline Questions

### 3.1 Freshness of `team_season_stats`

Pace is pulled via `pull_team_advanced()` which calls `LeagueDashTeamStats`. This is triggered by `pull_all()` but there's no automatic refresh mechanism. If the DB was last pulled 2 weeks ago, pace data is stale.

**Impact:** If a team's pace has changed significantly in recent weeks (trade, coaching change), the season-level pace won't reflect it.

**Fix:** Add a `pull_team_advanced_incremental()` that refreshes pace data daily (or before each projection run). The nba_api endpoint returns current-season data with one call.

### 3.2 `team_def_splits` Staleness

`compute_defensive_splits()` is computed once per `pull_all()` run and uses full-season data. It doesn't capture recent defensive changes (trades, injuries to defensive anchors).

**Fix:** Could compute rolling DvP (last 20 games) in addition to full-season. Store both and use a weighted average (e.g., 60% rolling + 40% season) so the model adapts to recent changes without being too noisy.

### 3.3 No In-Season Game Data for Current Day

The projector at runtime doesn't pull fresh data. It relies on whatever's in the DB from the last `--pull`. If games haven't been pulled since yesterday, today's projections use stale history.

**Current workflow:** Manual `python engine/projections_db.py --pull --seasons 2025-26` before running projections. Acceptable for daily use but fragile.

### 3.4 Missing Data Points in DB

The DB stores basic box score stats but lacks:
- **FG2A** (can be derived: FGA - FG3A, but requires FG3A which is present)
- **Personal fouls (PF)** — stored but not used anywhere in the projector
- **Plus/minus** — stored, not used
- **Game score / efficiency** — not stored
- **Pace per game** — only season-level in `team_season_stats`

### 3.5 Position Data Quality

`pull_player_positions()` uses height thresholds (≤76" → G, 77–80" → F, ≥81" → C). This is crude:
- Luka Doncic (6'7") → F, but plays PG role → should be G for DvP purposes
- Nikola Jokic (6'11") → C, correct
- Jalen Brunson (6'2") → G, correct

The position matters for DvP lookups and archetype priors. Misclassification creates systematic bias for players whose playing style doesn't match their body type.

**Better approach:** Use actual lineup position data (who plays the point, who plays the wing) rather than height. This would require a different data source (lineup data from nba_api's `LeagueDashLineups` or `PlayerDashboardByGameSplits`).

---

## 4. Evaluation Methodology

### 4.1 The eval samples actual minutes, not projected minutes

**Critical issue.** `evaluate_projector.py` uses `pmin = float(row["min"])` (the player's actual minutes in that game) as the projected minutes input. This is **cheating** — it gives the model perfect information about how long the player played.

In production, the model must *predict* minutes. The evaluation should test the full pipeline including minutes prediction. Currently, any error in the minutes model is invisible to the evaluator.

**Impact:** The reported MAEs are **lower bounds** on actual production error. The real MAE includes minutes prediction error, which is likely the single largest source of variance.

**Fix:** Run a second eval mode that uses `project_minutes()` instead of actual minutes. Compare MAE with actual-minutes vs projected-minutes to quantify how much the minutes model matters.

### 4.2 No Directional Accuracy Tracking

MAE measures average distance from truth. But for betting, what matters is:
- **Over/under accuracy:** Given a line at X, how often does the model correctly predict above/below?
- **Edge calibration:** When the model says 55% over, does it hit 55% of the time?

The evaluator doesn't compute these. Without them, you can't assess whether the model is useful for betting even if MAE looks good.

**Implementation:**
```python
# Directional accuracy at various thresholds
for line_offset in [0, 0.5, 1.0, 1.5]:
    n_over = sum(1 for r in results if r["custom"] > r["actual_line"] + line_offset and r["actual"] > r["actual_line"])
    ...
```

This requires knowing what the prop line was, which isn't in the DB. But you could use the projection mean as the "line" and measure directional accuracy of the model vs itself (calibration check).

### 4.3 Sample Size Concerns

The eval uses n=2000 with seed=42. This is a decent sample for PTS (high-signal stat) but potentially insufficient for:
- STL: Only ~0.8–1.2 per game average, high noise
- BLK: 0.3–0.6 per game for most players, extremely noisy
- 3PM: Discrete (0, 1, 2, 3...), MAE is bounded by the discrete nature

For low-event stats, consider using the **full dataset** (`n<=0` returns all qualifying rows per the evaluator's code) to get maximum statistical power.

### 4.4 No Out-of-Season Testing

All evals run on 2025-26 data, which is the same data the model's constants were calibrated on (LG_FTA_FGA, priors, etc.). This is **in-sample overfitting risk**.

**Fix:** Run eval on 2024-25 data (era_weight=0.75, not used for calibration). If MAE degrades significantly on 2024-25, the model is overfit to 2025-26 specific patterns.

### 4.5 RATE_MIN_MIN=20.0 Creates Selection Bias

The evaluator only tests games where the player played 20+ minutes. This excludes:
- Injury exits (played 12 minutes then left)
- Foul trouble games (15 minutes)
- Blowout benchings (18 minutes)

In production, the projector will generate projections for these players who then underperform due to minutes loss. The eval doesn't capture this failure mode.

**Fix:** Run eval at multiple min_min thresholds (10, 15, 20, 25) to see how MAE varies with the sample. The production-relevant test is probably min_min=10 or even min_min=5.

---

## 5. The PTS Regression Problem

### 5.1 Diagnosis

From Brief P3 evaluation table:
- PTS custom MAE: 4.668 (blend wired)
- PTS baseline MAE: 4.690
- Delta: -0.022 (custom 0.47% better)

But the changelog mentions "PTS MAE got 3.2% worse from the decomposition." This likely refers to an earlier version before calibration landed at α=0.50.

**Root cause of the regression (when α was higher):** The FGA decomposition introduces multiplicative error from:
1. USG% estimation error (±2–3% absolute USG → ±8–12% FGA)
2. fg3a_rate error (±5% → shifts points between 2P and 3P paths)
3. FTA/FGA ratio error (noisy stat, games with 0 FTA get forward-filled)
4. Team FGA estimation error (based on last 20 games, can shift with roster changes)

Each error multiplies: `proj_pts = (USG/100 * team_FGA * pace * min/48) * (split between 2P/3P/FT) * efficiencies`. Five multiplicative terms each with their own noise. The per-minute baseline has ONE source of noise: the per-minute rate EWMA.

### 5.2 Why α=0.50 Works (Barely)

At α=0.50, you're averaging two models:
- FGA path: lower bias (+0.005) but higher variance (more multiplicative error sources)
- Per-min path: higher bias (-0.548) but lower variance (one EWMA)

The 50/50 blend gets you low bias AND moderate variance. But the MAE improvement is only 0.022 — barely above noise for n=2000 (standard error of MAE ≈ 0.05 for PTS).

### 5.3 Path to Real Improvement

The FGA decomposition's theoretical ceiling is higher than per-minute, but only if the *inputs* are accurate. The highest-leverage improvements to the FGA path:

1. **Better USG% prediction:** Currently uses EWMA of historical USG%. But USG% shifts dramatically with teammate injuries/trades. If you can predict tonight's USG% better (e.g., adjusting for who else is playing), the FGA path becomes much more accurate.

2. **Game-level team FGA instead of season average:** `get_team_avg_fga` uses last 20 games. Consider factoring in the opponent — some defenses force fewer shot attempts (slower pace, more turnovers). This is partially captured by pace_factor but not cleanly.

3. **Minutes in the FGA formula:** `player_proj_fga = (USG/100) * team_FGA * pace * (proj_min/48)`. If projected minutes are wrong by 3 minutes (common), FGA is wrong by ~1.5 attempts, which cascades to ~3 points error. The eval sidesteps this by using actual minutes.

### 5.4 Proposed Fix: Dynamic Alpha Based on Sample Size

When a player has 25+ games this season, their shooting rates are well-estimated → trust FGA path more (α=0.65).
When a player has 5–10 games, rates are noisy → trust per-min more (α=0.30).

```python
dynamic_alpha = min(0.65, 0.25 + (n_games - 5) * 0.02)  # ramps from 0.25 to 0.65 over 25 games
```

This gives the decomposition path more weight exactly when its inputs are reliable.

---

## 6. Edge Calculation — Projection to Betting Line

### 6.1 How the Projector Feeds the Betting Engine

The projector outputs a point estimate (e.g., `proj_pts=22.5`). The betting engine in `run_picks.py` then:
1. Compares projection to the prop line (e.g., line=20.5)
2. Computes win probability using the Normal CDF with `dk_std` as the standard deviation
3. Computes implied probability from the market odds
4. Edge = model_prob - implied_prob

### 6.2 `dk_std` is Poorly Calibrated

**File:** `nba_projector.py` line 667

```python
dk_std = round(projections["pts"] * 0.35, 2)
```

Standard deviation is fixed at 35% of the projection for PTS. This means:
- A 30-point scorer: std=10.5
- A 10-point scorer: std=3.5

The 0.35 coefficient of variation is from the `_CV` dict (line 480). This is a *population average* CV, but individual players have very different variance profiles:
- High-volume scorers: CV closer to 0.30 (more consistent)
- Role players: CV closer to 0.45 (more game-to-game variance)
- Three-point specialists: CV can be 0.50+ (make/miss variance from beyond the arc)

**Impact on edge calculation:** If dk_std is too low, the model over-assigns probability to being far from the mean (fat tails). If too high, it under-assigns. This directly affects the calculated edge.

**Fix:** Compute player-specific std from their recent game history. The data exists — just compute `std = df_clean[stat].std()` for the recent sample and use that instead of `projection * fixed_CV`.

### 6.3 Normal Distribution Assumption

Player stats are NOT normally distributed:
- PTS: Approximately normal for high-volume players, left-skewed for low-volume
- 3PM: Discrete and often bimodal (0 vs 2–3)
- STL/BLK: Poisson-distributed (events per game)
- REB: Approximately normal for starters, skewed for bench

The betting engine likely uses a Normal CDF to compute over/under probabilities. For discrete/Poisson stats, a Poisson CDF would be more appropriate. For 3PM, a negative binomial might work better.

**Impact:** Systematic mispricing of edges for non-normal stats. Most impactful for 3PM and STL where the Normal approximation is worst.

### 6.4 The Projection-to-Edge Pipeline Has No Feedback Loop

The projector outputs numbers. The betting engine uses them. CLV is captured. But there's no automated mechanism to feed CLV back into the projector's parameters.

**Ideal flow:** Track which stats/players/situations systematically beat or miss the close → adjust priors, alphas, or CV assumptions accordingly. Currently this requires manual analysis via `analyze_picks.py`.

---

## 7. Minutes Modeling — The Biggest Lever

### 7.1 Current State

```python
def project_minutes(role, df, b2b, spread=None, injury_minutes_override=None):
    # EWMA(span=5) of recent minutes + role prior blend
    # + days-rest reduction (exponential decay, max -10%)
    # + blowout sigmoid (max -20%)
    # Cap: 42 for starters, 38 for everyone else
```

### 7.2 What's Missing

**Coach tendencies.** Some coaches run tight 8-man rotations (starters get 35+ min). Others run 10+ deep. This is entirely unmodeled. The EWMA captures it indirectly if the rotation has been stable, but misses when a coach changes strategy.

**Game script modeling.** A team down 15 at halftime will:
- Pull starters if the deficit grows (reducing minutes)
- Keep starters in if the game tightens (maintaining minutes)
The current sigmoid blowout model uses *pre-game spread* as a proxy, but the actual game script is unknown pre-game.

**Pre-game spread only approximates blowout probability.** A 12-point spread has a ~20% chance of being a blowout (winning margin >20). The sigmoid model treats every 12-point-spread game identically, but some will be close games and some will be blowouts.

**Foul trouble probability.** Players who average 3+ PF/game have meaningful probability of fouling out or being benched. This isn't modeled at all. The DB stores `pf` per game.

**Overtime.** A game that goes to OT adds 5+ minutes for starters. The probability of OT is ~6% for all games, higher for games with tight spreads. Not modeled.

### 7.3 Elite Minutes Model Architecture

A truly elite minutes model would:

1. **Start with EWMA baseline** (current approach — good)
2. **Apply rotation-depth adjustment:** Compute team's average starters' minutes over last 10 games. If team runs deep (starters avg 30 min), project less. If tight rotation (starters avg 36 min), project more. Currently implicit in EWMA.
3. **Game script distribution:** Instead of one projection, model a distribution:
   - P(blowout win) × minutes_in_blowout_win
   - P(blowout loss) × minutes_in_blowout_loss  
   - P(close game) × minutes_in_close_game
   - P(OT) × minutes_in_OT
   
   Where probabilities come from the spread and each minute estimate comes from historical patterns for that player in each scenario.

4. **Conditional on teammate injuries:** If the backup is out, the starter's minutes floor rises. The current `injury_minutes_override` handles this but requires external input.

5. **Foul trouble penalty:** Players with high PF rates get a negative adjustment (~1–2 min) representing the probability-weighted impact of early fouls.

### 7.4 Quantifying the Minutes Error Impact

A 3-minute error in projected minutes for a 20 PPG scorer at 0.55 PTS/min:
- PTS error: ±1.65 points
- For a line at 20.5 with true mean 20.0: shifts win probability by ~8%

This is enormous. The *single best investment* for improving the projector is reducing minutes prediction error.

**Measurement:** Run the evaluator with actual minutes vs. projected minutes (see Section 4.1). The delta tells you exactly how much the minutes model is costing you.

---

## 8. Additional Findings & Opportunities

### 8.1 TOV Has No Custom Model

```python
tov_rate = rates.get("tov", 0.0)
projections["tov"] = max(0.0, round(tov_rate * proj_min * pace_factor, 2))
```

TOV is the only stat still using the pure per-minute × pace formula without any decomposition or opponent adjustment. TOV should correlate with:
- Usage rate (more possessions = more TOV opportunities)
- Opponent steal rate (teams that force TOs)
- Pace (more possessions = more TOV)

A simple improvement: `tov_rate * proj_min * pace_factor * opp_tov_forcing_factor`.

### 8.2 The 3PM DvP Uses PTS DvP

Line 556: `"fg3m": matchup_pts`. The `team_def_splits` table has `fg3m` as a separate stat. Some teams are elite at defending the 3 but allow interior scoring (e.g., switch-heavy perimeter defenses). Using PTS DvP as a proxy for 3PM DvP loses this differentiation.

**Fix (trivial):**
```python
matchup_fg3m = float(np.clip(
    get_team_def_ratio(opp_team_id, pg, "fg3m", season, db_path), *MATCHUP_CLIP))
matchup_factors["fg3m"] = matchup_fg3m
```

### 8.3 REB Decomposition Doesn't Use Opponent OREB Rate

The available DREB pool is computed as `opp_FGA * (1 - opp_FG%)` — opponent missed shots. But opponent teams that crash the OREB hard grab their own misses back, reducing the DREB available to the projecting team.

**Current formula:**
```python
avail_dreb_pg = opp_shoot["fga_per_game"] * (1.0 - opp_shoot["fg_pct"])
```

**Should be:**
```python
avail_dreb_pg = opp_shoot["fga_per_game"] * (1.0 - opp_shoot["fg_pct"]) * (1.0 - opp_oreb_rate)
```

Where `opp_oreb_rate = opp_oreb / (opp_FGA * (1 - opp_FG%))`. Teams with high OREB rates (like OKC, Cleveland) reduce opposing DREB opportunities by 10–15%.

The `get_team_shooting_stats()` already returns `oreb_per_game` — you can compute the rate from existing data.

### 8.4 AST Rate Computed from Team Pace, Projected with Game Pace

**File:** `nba_projector.py` lines 637–639

```python
ast_rate = compute_ast_rate(df_clean, team_pace, pg)  # uses team_pace
proj_poss = game_pace * proj_min / 48.0               # uses game_pace
proj_ast_custom = ast_rate * proj_poss * matchup_ast
```

The `compute_ast_rate` function (line 228) divides historical AST by `(team_pace * min/48)`. At projection time, it multiplies by `game_pace * min/48`. If team_pace ≠ game_pace (which it won't when facing a fast/slow opponent), this creates a systematic bias:

- If opp is fast (game_pace > team_pace): `ast_rate` was computed with lower denominator → rate is higher → then multiplied by higher game_pace → double-counts the pace-up
- If opp is slow (game_pace < team_pace): opposite effect

**The fix:** `compute_ast_rate` should use the same pace basis that will be applied at projection time, OR the rate should be computed as AST per minute (pace-neutral) and then pace applied once at projection.

Actually, looking more carefully: `compute_ast_rate` normalizes by `team_pace` (the team's own season average), not the game-specific pace of each historical game. This is an approximation — each historical game had a different actual pace. The normalization is only approximate. The bias cancels out on average (historical game paces center around team_pace), but introduces noise.

**Better approach:** For each historical game, compute actual game pace from box score data and normalize by that. This requires joining the game's opponent stats, which adds query complexity but improves rate accuracy.

### 8.5 Implied Total Override and the FGA Decomposition

When `implied_total` is provided:
```python
pace_factor = implied_total / LEAGUE_AVG_TOTAL
```

This gets used in:
```python
team_proj_fga = team_avg_fga * pace_factor
```

So `team_proj_fga = team_avg_fga * (implied_total / 222.0)`. Consider: if the implied total is 210 (slow game), `pace_factor = 0.946`, so `team_proj_fga` drops 5.4%. But team_avg_fga already reflects the team's typical pace! The correct adjustment should be relative to what's *expected* for this matchup, not relative to league average.

**Example:** Two fast teams (each averaging 100 FGA/game) face each other. Implied total = 235. `pace_factor = 235/222 = 1.059`. `team_proj_fga = 100 * 1.059 = 105.9`. But this team already shoots 100/game *because* they're fast! The implied total is only 235 because both teams are fast — it's not telling you this team will shoot MORE than their average.

**The correct formulation:**
```python
expected_total = (team_off_rtg + opp_off_rtg) / 2 * (game_pace / 100)  # or simpler average
pace_factor = implied_total / expected_total  # adjustment relative to THIS matchup's expected total
```

This way, if the implied total matches what you'd expect from these two teams' historical stats, pace_factor = 1.0 (no adjustment). Only deviate when Vegas has information the historical data doesn't.

### 8.6 No Recency Weighting for DvP

The `team_def_splits` table stores one ratio per (team, season, position_group, stat). This is computed from ALL games in the season. A team that traded away a star defender mid-season will have a DvP that's diluted.

**Fix:** Compute DvP from last 20 games only (rolling). This requires changing `compute_defensive_splits()` to window the data or adding a separate `compute_rolling_def_splits()` function.

### 8.7 `dk_std` Only Computed for PTS

Line 667: `dk_std = round(projections["pts"] * 0.35, 2)`

The output dict only includes `dk_std` for PTS. If the betting engine uses standard deviation for other stats (REB, AST, 3PM), it presumably has its own hardcoded CV values. This should be a per-stat output from the projector.

### 8.8 Projection Confidence — Not Used

The `compute_distribution` function (line 479) computes P25/P75 for PTS/REB/AST/3PM. These are stored in the DB. But they're based on a fixed CV and an uncertainty multiplier based on sample size.

**Better confidence interval:** Use the actual historical variance from the player's recent games, adjusted for the current matchup context. This gives *player-specific* confidence bounds rather than one-size-fits-all.

### 8.9 `get_player_recent_games` Minimum Minutes Floor

The DB query (projections_db.py line 567) has `min_minutes=5.0` default. This means games where a player played 5–10 minutes are included in the raw pull, then later filtered by `_ROLE_MIN_MINUTES[role]`.

For starters, this means the raw 30-game pull includes games where they got hurt early (played 8 min). These get filtered out by the `min_min=20` threshold for starters. But the `classify_role()` function (line 161) looks at the raw `df` before filtering:

```python
role = classify_role(df)   # uses unfiltered df
min_min = _ROLE_MIN_MINUTES[role]
df_clean = df[df["min"] >= min_min].copy()
```

So role classification uses ALL games (including low-minutes games), while rate computation only uses games above the floor. This is intentional — you want to see the foul-trouble game when classifying role (it tells you they're still starting), but don't want it polluting per-minute rates.

**Verdict:** Correct design. Just documenting it.

---

## 9. Priority-Ordered Recommendations

### Tier 1: High Impact, Low Effort (Do Immediately)

| # | Finding | Expected Impact | Effort |
|---|---------|-----------------|--------|
| 1 | Wire `fg3m` DvP instead of piggybacking PTS DvP (§8.2) | 1–3% 3PM MAE improvement | 5 min |
| 2 | Port opp_tov_factor to projector's STL calculation (§1.1) | 2–5% STL MAE improvement | 10 min |
| 3 | Enable STL/BLK DvP from existing team_def_splits data (§1.9) | 1–3% improvement | 15 min |
| 4 | Run eval with projected minutes to quantify minutes error (§4.1) | Diagnostic, no direct MAE change | 30 min |
| 5 | Remove pace_factor from BLK if eval confirms no benefit (§1.2) | Cleaner model, possibly better BLK | 20 min |

### Tier 2: Medium Impact, Medium Effort (Next Sprint)

| # | Finding | Expected Impact | Effort |
|---|---------|-----------------|--------|
| 6 | Add home/away adjustment (§2.2) | 1–2% PTS MAE, systematic edge | 2 hrs |
| 7 | Fix implied_total vs expected_total formula (§8.5) | Eliminates systematic bias for fast/slow teams | 1 hr |
| 8 | Dynamic PTS_BLEND_ALPHA based on sample size (§5.4) | 0.5–1% PTS improvement | 1 hr |
| 9 | Adjust USG% when injury_minutes_override is set (§2.5) | Large impact on injury-driven picks | 2 hrs |
| 10 | Fix AST rate normalization asymmetry (§8.4) | 1–2% AST improvement for pace mismatches | 2 hrs |
| 11 | Stat-specific playoff deflators from DB data (§1.7) | Better playoff projections | 2 hrs |
| 12 | Out-of-sample evaluation on 2024-25 (§4.4) | Detects overfitting | 30 min |

### Tier 3: High Impact, High Effort (Future Briefs)

| # | Finding | Expected Impact | Effort |
|---|---------|-----------------|--------|
| 13 | Rolling game-level pace (§2.1) | 1–2% across all stats | 4 hrs |
| 14 | Player-specific std replacing fixed CV (§6.2) | Better edge calculation | 3 hrs |
| 15 | Opponent OREB rate in DREB pool calculation (§8.3) | 1–2% REB improvement | 1 hr |
| 16 | Full minutes model eval pipeline (§7) | Quantifies biggest error source | 4 hrs |
| 17 | Rolling DvP (last 20 games) instead of full-season (§8.6) | Better adaptation to trades/injuries | 3 hrs |
| 18 | Blowout model: role-conditional (starters vs bench) (§2.6) | Better bench player projections | 3 hrs |

---

## 10. Summary of Open Questions

1. **Does the evaluator's use of actual minutes mask the true production MAE?** Almost certainly yes. Measuring this quantifies the ceiling vs. floor of the current system.

2. **Is the implied_total override systematically biased for fast/slow team matchups?** Need to compare projections with and without the override for games where both teams are above/below average pace.

3. **How much does the 3PM DvP fix improve 3PM projections vs the PTS DvP proxy?** Quick A/B test possible with the evaluator.

4. **What's the actual playoff deflator per stat from historical data?** Query: compute avg per-36 in playoffs vs regular season per position group for each stat.

5. **Is BLK × pace_factor actually helping or hurting?** Run eval with and without.

6. **How many projection failures in production are due to minutes error vs rate error?** Decompose prediction error into `(rate_error × actual_min) + (actual_rate × min_error)` + interaction.

---

*End of Research Brief P4. Next steps: implement Tier 1 items (estimated 1 hour total), then run full evaluation suite to measure cumulative improvement before starting Tier 2.*
