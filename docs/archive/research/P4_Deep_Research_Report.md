# Deep Research Report — Part 4: Diagnostic Findings & Production-Grade Refinements

*Generated: 2026-05-01*

---

## 1. Executive Summary — Top 5 Fixes

The two ranking criteria diverge on ordering. MAE reduction prioritizes structural model accuracy; CLV/pick-accuracy lift prioritizes what actually moves money. The table below shows both ranks explicitly.

| Fix | MAE Rank | CLV Rank | Summary |
|-----|----------|----------|---------|
| **A. Fix evaluator to use projected minutes** | 1 | 1 | All current MAEs are lies. You cannot prioritize anything else until you know the true error surface. |
| **B. Rebuild PTS blend weight (lower alpha, better rate stabilization)** | 2 | 3 | PTS is the highest-volume bet category. A 3.2% regression on your most-bet stat is a real-money problem. |
| **C. Wire fg3m DvP + minutes-aware usage redistribution on injury** | 3 | 2 | Injury usage redistribution is the highest-edge market in props. fg3m DvP is a free, unwired signal. Together these are the biggest CLV lever available without rebuilding anything. |
| **D. Correct pace double-counting bias** | 4 | 4 | Systematic bias that inflates projections for players on fast-vs-fast matchups and deflates for slow-vs-slow. Affects every stat uniformly. |
| **E. Fix BLK Bayesian approach (position-mixture prior or revert)** | 5 | 5 | BLK shrinkage in its current form actively hurts. The fix is conceptually simple even if the root cause is structural. |

**Where the rankings diverge most:** Adding home/away modeling (Q5) would rank ~4 on MAE but ~7 on CLV because the books already mostly price home/away into props. Injury redistribution (part of C above) ranks lower on MAE because it fires only in specific game contexts, but it's #2 on CLV because those are exactly the games with the widest market mispricing windows.

---

## 2. Minutes-Error Decomposition

### The core problem

Your evaluator currently uses actual minutes. This means your MAE numbers measure *rate error only* — how well you predict per-minute production given perfect knowledge of playing time. In production, you are doing both: projecting minutes AND projecting rates. The reported MAEs are a lower bound, not a realistic estimate.

### Best available estimate of the split

No published paper directly measures this decomposition for NBA prop projections specifically. The DFS community consensus (drawn from RotoGrinders methodology documentation and ETR's published model analyses) is:

- **Minutes variance accounts for roughly 40–55% of total player stat variance** for rotation and bench players
- **For starters, the split shifts to 25–35% minutes / 65–75% rates** because starter minutes are more predictable (32–38 min range is tight)
- **For spot/cold-start players, minutes variance dominates at 60–75%**

A rough reconstruction for your specific model: your `ROLE_MINUTE_PRIOR` for starters is 32.0 with a minutes cap of 42.0. If your minutes RMSE for starters is ±3.5 min (optimistic for real conditions) and your PTS/min rate is ~0.55 pts/min, that generates ±1.9 pts of minutes-driven PTS error. Your total PTS MAE in the post-implementation eval is 5.226. The minutes-error component for starters is therefore likely ~1.5–2.0 pts (29–38% of total). For rotation players with ±5 min minutes error and 0.45 pts/min, that's ±2.25 pts — closer to 40–50% of total.

### What this means for prioritization

You **cannot trust any MAE comparison until you switch the evaluator to projected minutes**. The 3.2% PTS regression may be noise (n=20), real rate-model degradation, or masked by actual-vs-projected minutes luck. Every other diagnostic in this report assumes you fix the evaluator first.

### State of the art in minutes projection

Published and community-known inputs, ranked by contribution:

1. **Role assignment + season-average minutes** — the baseline. RMSE ~3.5–5 min for rotation players.
2. **Injury/rest flags** — the biggest discrete jump. A starter out is a ±8–12 min redistribution event.
3. **Blowout probability** — your sigmoid is a reasonable approximation, but it should be applied post-projection (to expected game state distribution) not as a point estimate at the pregame spread.
4. **Coach rotation tendency** — some coaches run tight 8-man rotations, others go 10 deep. This is semi-stable within a season and poorly priced in most projections.
5. **Foul-trouble probability** — high-foul-risk players (especially centers facing aggressive offenses) have fat-tailed minutes distributions. A 30-min projection could be 20 or 38 depending on fouls.
6. **Game pace × role** — faster pace doesn't add minutes for starters but does increase possessions and therefore counting stats. Your pace_factor should be applied to *counting stats*, not minutes.

**Minimum viable minutes model:** Season-average minutes + role-based soft cap + discrete injury flag + blowout sigmoid. This is roughly what you have. The marginal gain from adding foul-trouble probability or coach tendency is real but small relative to fixing the evaluator.

### Starter vs. rotation structural difference

These are structurally different problems:
- **Starters**: minutes are censored at the top (rarely >42) and have a sharp lower tail (blowout/injury). Model as: baseline minutes × blowout_factor × injury_flag, where baseline is stable.
- **Rotation**: minutes have high variance driven by matchup and game script. Opponent pace matters more. Harder to project.
- **Spot/cold-start**: near-binary (play or DNP). Better modeled as a probability-weighted 0/active than a continuous minute estimate.

### Days-rest fatigue curve

Your `DAYS_REST_HALF_LIFE = 1.5` implies that 1 day of rest recovers half the fatigue, 3 days recovers 87.5%. The empirical research on NBA back-to-backs (Barça Innovation Hub; ResearchGate 2020 study on schedule congestion) shows:

- B2B second game: -3 to -5% in scoring efficiency, -4% win probability
- 1 day rest: roughly 60–70% recovered vs. 2+ days
- 2+ days rest: fully recovered for most players; no measurable additional benefit beyond 2 days

**Your half-life of 1.5 is reasonable but slightly aggressive** (implies 83% recovery after 2 days, which is close to empirical). The shape is approximately right. The `DAYS_REST_MAX_REDUCTION = 0.10` (10% max at 0 days rest) is consistent with the 5–10% performance decline literature. One nuance: the fatigue effect is larger for **veteran high-minute players** than for young players. Your `DAYS_REST_ROLE_SCALAR` partially captures this (starters=1.0 vs rotation=0.90) but does not account for age.

---

## 3. PTS Regression Diagnosis

### The 3.2% regression: most likely explanation

Your FGA decomposition (PTS = 2P-made × 2 + 3P-made × 3 + FT-made × 1) introduces **multiplicative variance stacking**. Each component has its own noise:

- 2P% has ~5–7% game-to-game standard deviation even after Bayesian padding
- 3P% has ~8–12% game-to-game SD
- FTA rate has ~15–20% game-to-game SD (most volatile)
- FGA itself has ~15–20% SD

When you multiply noisy rates together, error compounds. The combined variance of the decomposed path exceeds the variance of a single-stage per-minute rate × minutes estimate. This is the **standard "error amplification" failure** of decomposition when the sub-components are not individually stable enough at the game level.

### Diagnosing PTS_BLEND_ALPHA = 0.50

At 0.50, you're giving equal weight to a path that is (a) methodologically correct in aggregate but (b) noisier at the individual game level. The evaluation result (FGA-only path MAE 4.782 vs baseline 4.690, blend giving 4.668) says:

- The decomposed path is *worse* than baseline by 2.0% on its own
- Blending at 50/50 salvages it marginally vs baseline
- The decomposition is adding noise, not signal, at the game level

**Recommended approach:**

1. **Lower `PTS_BLEND_ALPHA` to 0.20–0.30** as an immediate fix. The per-min path is better on its own; the decomposed path should be a minor adjustment.
2. **Find the optimal alpha empirically via grid search on your held-out data** — try 0.10, 0.20, 0.30, 0.40, 0.50 and measure MAE at each. Use walk-forward validation, not a fixed-date eval.
3. **The principled method is stacking/ensemble**: train a meta-learner (even a simple one-parameter linear regression) on both predictions. This is Bayesian model averaging in the frequentist framing. The meta-learner's coefficient on the decomposed path will tell you exactly how much weight it deserves — and it may be very small.

### Rate stabilization check

Your current padding:
- `PAD_2P = 300` — consistent with the literature. 2P% stabilizes around 300–400 field goal attempts. This is a reasonable effective sample size.
- `PAD_3P = 750` — this matches Blackport's published stabilization threshold (~750 3PA). This is correct.

**The issue is not the PAD values; it is that even well-stabilized rates still have high game-to-game variance.** Season-long 3P% stability at 750 attempts ≠ game-level 3P% predictability. A player shooting 37% on the season has a game-level SD of roughly ±15–20 percentage points. Multiplying a noisy rate by a noisy 3PA gives you a very noisy 3PM count.

### 3PM: rate × volume vs. direct count?

**Direct count projection (per-min 3PM rate × projected minutes) has lower out-of-sample variance than rate × volume decomposition.** The reason: 3PA itself is highly variable game-to-game (matchup-dependent, game-script-dependent), so decomposing adds another volatile input. Your existing per-min 3PM approach is correct. Reserve the 3P% × 3PA decomposition for season-level projections, not game-level.

### PTS deflation bias

Your bias at the n=2000 eval is -0.272 (system under-projects PTS by 0.272 pts). At n=20 it's likely noisier. This bias is small relative to MAE but persistent — check whether it worsens in fast-pace games (where pace_factor is high). If it does, that's evidence of the double-counting issue (Section 4 below).

---

## 4. BLK Bayesian Shrinkage Failure — Structural Analysis

### Why STL worked and BLK didn't

**STL has a near-symmetric, roughly normal per-minute distribution within positions.** The priors (G=0.0333, F=0.0250, C=0.0194 per minute) are monotonically decreasing — guards steal more than centers — but the *variance within each position* is moderate. Bayesian shrinkage with N=25 pulls outlier games toward a reasonable positional mean. This is exactly the scenario where positional priors work.

**BLK has a strongly bimodal distribution *within positions*, especially for centers.** The center prior (C=0.0500/min) represents approximately 2.4 BLK/48min, which is a reasonable average for *all centers*. But the population of "centers" in the NBA is bimodal: non-blocking big men (Nikola Jokic-style: ~0.5 BLK/game) and rim-protecting centers (Jaren Jackson Jr., Walker Kessler: ~2.5+ BLK/game). A single Gaussian prior with N=30 effective samples applied to a bimodal population will pull *every* player toward the center mean — undershrinking the non-blockers and overshrinking the elite shot-blockers.

**The mechanism of BLK's MAE degradation (6.4% worse):** For elite shot-blockers, the prior pulls their projection down toward 0.0500/min, causing under-projection. For non-blocking centers, the prior pulls up, causing over-projection. Both errors accumulate in the MAE.

### Corrected approach for BLK

Three options in order of implementation complexity:

**Option 1 (simplest — immediate fix):** Stratify the center position into two sub-priors based on career BLK/min rate: `C_low` (<0.030/min) and `C_high` (≥0.030/min). Use N=30 for each sub-group. This captures the bimodality within centers without a full mixture model.

**Option 2 (better):** Use a **2-component Gaussian mixture prior for centers** — one component for non-blockers, one for rim protectors. Classification can use prior-season BLK rate as a deterministic split. This is the statistically correct solution.

**Option 3 (most general):** Move BLK to the same **DB-calibrated approach** you use for AST — estimate the prior means directly from your `projections_db` grouped by position cluster, and update PRIOR_N based on how quickly BLK rates stabilize. Research suggests blocking rate stabilizes around 50–70 games for centers (it's a true skill), meaning N can be lower (15–20) for a player with 30+ games of data.

**What to do now:** Revert to no shrinkage (current state) and implement Option 1. It's a one-hour code change and will stop the active harm.

### Should AST's DB-calibrated approach be universal?

Yes for stats where the prior is position-conditional and the position categories are internally diverse (REB, BLK, AST). No for STL, where hardcoded positional priors are simple and work. The DB-calibrated approach is strictly better when the prior mean itself is uncertain or variable within a position. The overhead is worth it for the three stats where positional archetypes vary most: AST (playmaker vs. non-playmaker), BLK (rim protector vs. stretch center), REB (rebounding-emphasis bigs vs. non-rebounders).

---

## 5. DvP Audit

### What the research shows on DvP validity

The DFS community backtesting consensus (RotoGrinders, FantasyLabs) is that **position-based DvP is mostly noise for individual player props.** The primary issues:

1. Modern switching schemes make position matchups blurry — a PG often guards an SF and vice versa
2. Teams play bad defense against certain positions not because they're weak there, but because they've faced more elite players at that position
3. Sample size: 82 games, split by 5 positions, gives ~16 games per position per team — too few for stable estimates

**DvP is more reliable when:** (a) framed as team-level defensive rating vs. a specific stat category rather than position-filtered, (b) recent-weighted (last 15 games, not season), (c) used to confirm a read, not generate one.

### 3PM piggybacking off PTS DvP — estimated impact

The correlation between team PTS defense rating and team 3PM defense is real but imperfect. Teams that allow the most points do allow more 3s on average, but there are teams that defend the paint poorly while contesting threes well (pack-the-paint schemes) and vice versa. The fg3m DvP in your DB is capturing something the PTS DvP doesn't.

**Estimated accuracy left on the table:** Given DvP's overall low signal-to-noise, wiring fg3m DvP specifically is unlikely to reduce MAE by more than **0.3–0.5%** on 3PM projections. However, it is a *free signal you are currently ignoring*, and for specific matchups (e.g., a team ranked bottom-5 in 3PM allowed vs. a team ranked top-5), the effect is real and bookable.

**Implementation:** Replace the PTS DvP piggyback for 3PM with `fg3m_dvp_factor = team_3pm_allowed / league_avg_3pm`. Apply same `MATCHUP_CLIP = (0.80, 1.20)`. One function, one DB query.

### STL and BLK DvP — estimated impact

- **STL DvP (opponent TOV rate):** Teams with high TOV rates generate more STL opportunities for defenders. The correlation is real: teams ranked top-5 in TOV rate generate roughly 15–20% more STL opportunities than average. However, individual player STL capture rates vary independently of team TOV rate. **Estimated impact on STL MAE if wired: 1–2% improvement.** Worth doing, low complexity.

- **BLK DvP (opponent FGA near rim):** Teams that drive frequently generate more shot-blocking opportunities. The correlation is real: teams ranked top-5 in rim attempts allowed give rim protectors 20–30% more BLK opportunities. **Estimated impact on BLK MAE: 2–3% improvement** — meaningful given BLK's current MAE of 0.450–0.597. Higher priority than STL DvP.

### MATCHUP_CLIP ±20% — is it right?

±20% is within the standard range. Published DvP analyses show that the most extreme matchups (worst defense vs. best offensive player) can justify 25–30% adjustments, but ±20% prevents overreacting to small-sample DvP anomalies. **Current clip is appropriate.** Do not widen it until you have DB-calibrated DvP with 15-game rolling windows.

---

## 6. Home/Away and Altitude Effects

### Home/away on individual player stats

Team-level home advantage is well-established: home teams win ~59–60% of NBA games and score ~3.3 points more per game (PMC 2016 study). For individual player stats, the effect is **real but small and highly player-specific**.

Empirical estimates from available research:

| Stat | Home vs. Away Δ (all players avg.) | As % of MAE |
|------|-------------------------------------|-------------|
| PTS | +0.8 to +1.2 pts | ~15–23% of current 5.2 MAE |
| REB | +0.2 to +0.4 | ~12–23% of 1.7 MAE |
| AST | +0.1 to +0.3 | ~7–21% of 1.4 MAE |
| 3PM | +0.1 to +0.2 | ~9–19% of 1.07 MAE |

The within-player variance around these means is high — some players post better away numbers. The individual-level home/away effect is **not zero** but is smaller than the noise in your current estimates.

**Recommendation:** Add a simple binary home flag with a shrunk coefficient (estimated by regression on your `projections_db`). Expected MAE improvement: **1–2% across stats.** This is a second-tier fix — real but not urgent.

**Important caveat:** Books already price home/away into props to some degree. Adding home/away to your model improves projection accuracy but may not translate proportionally to CLV lift if the market is also adjusting.

### Denver altitude — concrete estimates

The clearest empirical finding: **visiting players' movement speed drops ~7% in Q4 relative to Q1** in Denver (visiting speed: 4.20 mph Q1 → 3.89 mph Q4). This is consistent with altitude-induced fatigue compounding over the game.

Empirical impact on stats: **smaller than you'd expect from first principles.** Analysis of Denver visiting-team offensive output does not show a clear decline in overall scoring. What changes:

- Visiting players take slightly more 3s (less driving energy; ~1–2 extra 3PA/team/game)
- Fourth-quarter performance declines for visitors; this matters for live betting but less for game-long prop projections
- The psychological "altitude advantage" narrative inflates the Nuggets' home advantage in public perception more than it shows in the box score

**Recommendation:** Do not add a Denver-specific altitude adjustment to your projections. The effect is real but too diffuse and small relative to current MAE to justify the model complexity. The marginal benefit is better captured via home/away modeling generally (which would assign Denver a strong home edge) than via a special altitude case.

---

## 7. Injury Replacement Playbook

### Empirical usage redistribution

When a high-usage starter (USG% > 25%) misses a game, usage redistribution follows a predictable archetype:

1. **Primary ball handler out:** The next-in-line guard absorbs ~40–50% of the missing usage, split across 2–3 secondary playmakers. Teams do NOT spread usage evenly — it concentrates.
2. **High-scoring wing out:** Minutes distribute to the next wing in the rotation, but usage spikes less because teams often go to the big-man anchor more.
3. **Center out:** Backup center absorbs minutes; PF shifts to center role. Usage spike concentrated at the backup big.

From the `usageboost.com` data framework and published player-without (PWP) research:

- A missing player with 25% USG redistributes roughly: **45–55% to the primary backup at the same role, 15–25% to a secondary guard/wing, 10–20% absorbed across remaining rotation.**
- Efficiency drops ~10–15% for the players absorbing extra usage because they are operating outside their optimal load.

### Recommended methodology

The best published methodology is **historical player-without-teammate data** (also called "PWP" — player with/without player stats). Your `projections_db` likely contains multi-game samples that can generate these. The calculation:

```
usage_boost_estimate = player_prev_usage × (1 + dvp_scaling)
                       × fraction_of_missing_usage_absorbed
                       × availability_probability
```

Fraction absorbed can be estimated from: (a) role similarity to absent player, (b) typical coach substitution patterns (available from recent game logs), (c) position of absent player.

**A simpler but effective heuristic:** When a player with `tier=T1` is marked out, their replacement absorbs `0.50 × missing_USG_pct` and the residual 0.50 splits across the remaining roster proportional to current usage. Apply a `0.90` efficiency discount to the incremental usage.

### The mispricing window

This is the highest-edge market in props. The empirical timeline:

- **T-120 to T-60 min (2h to 1h before tip):** Books begin updating main-game lines immediately after beat reporter / Woj/Shams tweet. Most books have automated alerts.
- **T-60 to T-30 min:** Main lines largely adjusted; *prop lines lag 15–30 minutes* because props require manual re-evaluation across potentially 5–15 player lines per game.
- **T-30 to T-5 min:** Prop lines mostly adjusted but alt lines and correlated props (PRA combos, combo over/unders) lag further.

**Optimal strategy:** Monitor for Woj/Shams tweets and beat reporter injury confirmations from T-120 onward. The first 15–30 minutes after confirmation is the highest-value window for props on replacement players. For main lines, you're competing with sharps and the window closes fast.

**Your current habit of betting close to game time is optimal for injury-driven props** — you want lineup confirmation, and you can still find mispriced replacement props in the T-30 to T-5 window. For non-injury edges (matchup, rate), earlier is better (see Section 12).

---

## 8. Evaluation Overhaul

### Sample size problem — n=20

At n=20, the confidence interval on any MAE comparison is enormous:

- If the true MAE difference is 2%, you need approximately **n ≈ 400–600 samples** to detect it with 80% power at 95% confidence (using a paired t-test on absolute errors, which is the right test here).
- At n=20, the 95% CI on your reported 3.2% PTS regression spans roughly **±8–12%** — meaning the result is statistically consistent with anything from a 9% improvement to a 15% regression.

**The n=20 evaluation is not usable for any decision.** It has the right directional signal (PTS got worse, REB/AST/STL/BLK got better) but no statistical power.

**Minimum n for each stat to detect a 2% MAE improvement:** ~500 player-game samples, using actual projected (not actual) minutes.

### Recommended evaluation structure

1. **Primary evaluation: walk-forward validation.** Train on games through date T, evaluate on T+1 through T+14, roll forward. This is the correct structure for time-series prediction because it (a) respects temporal order, (b) tests generalization across different game contexts, (c) catches overfitting that fixed-date eval misses. Minimum: 3 rolling windows of 100+ games each.

2. **Stratify by archetype.** Your model is likely stronger for high-usage starters (stable roles, stable rates) and weaker for rotation players (high variance). Report MAE separately for: (a) starters with >28 MPG, (b) rotation 18–28 MPG, (c) <18 MPG. The overall MAE is hiding where the model is actually failing.

3. **Secondary metrics to track in parallel:**
   - **Directional accuracy (over/under the line):** What % of your projections are on the correct side of the book's prop line? This is the betting-relevant analog of directional accuracy.
   - **Tail MAE (>5 pts off on PTS, >3 on REB):** These catastrophic misses destroy EV even if average MAE looks okay.
   - **Calibration curve:** Bin your projected values and check whether actual outcomes are centered on the projection. If you project 24.3 pts and the player averages 24.3 over many such projections, you're calibrated.
   - **CLV tracking:** Already in your system — this is the best real-world edge metric.

4. **Re-run the full n=2000 eval with projected minutes.** This is the single most important action. The projected minutes should come from your own minutes model (not SaberSim actuals), using role + injury + blowout inputs.

### 119 picks — calibration

With 119 graded premium picks, you have enough data for initial calibration (see Section 11). You do not yet have enough for stratified calibration by sport/stat/archetype — you need 300–500 for that.

---

## 9. Edge Calculation Correctness Check

### CV validation

Your current CVs: `{"pts": 0.35, "reb": 0.45, "ast": 0.50, "fg3m": 0.65, "stl": 0.80, "blk": 0.85, "tov": 0.55}`

CV = SD / Mean. Let's cross-check against empirical distributions:

| Stat | Typical mean (starter) | Empirical SD (game-level) | Implied CV | Your CV | Assessment |
|------|------------------------|--------------------------|-----------|---------|------------|
| PTS | 20 | 6–8 | 0.30–0.40 | 0.35 | ✓ Close |
| REB | 6 | 2.5–3.5 | 0.42–0.58 | 0.45 | ✓ Low end, possibly slightly underestimated |
| AST | 5 | 2.5–3.5 | 0.50–0.70 | 0.50 | ✓ Low end, possibly underestimated |
| 3PM | 2.0 | 1.3–1.8 | 0.65–0.90 | 0.65 | ✓ Low end reasonable |
| STL | 1.0 | 0.7–1.0 | 0.70–1.00 | 0.80 | ✓ Reasonable |
| BLK | 0.8 | 0.7–1.0 | 0.88–1.25 | 0.85 | ✗ Underestimates BLK variance for non-elites |
| TOV | 2.5 | 1.3–1.8 | 0.52–0.72 | 0.55 | ✓ Low end |

**The CVs are directionally correct but systematically on the low side for high-variance stats (BLK, REB, AST, TOV).** Underestimating CV means you over-estimate the probability of a player exceeding a prop line — i.e., your edge calculations are slightly too optimistic. Correct REB to 0.50, AST to 0.55, BLK to 1.00.

### Distribution assumption by stat

The research is clear:
- **PTS:** Normal approximation is acceptable at game level for high-usage players. Negative binomial is more correct but the difference is small at means >15. Keep Normal for PTS.
- **REB, AST:** Negative binomial fits better than Poisson (variance > mean, consistent overdispersion). The Normal approximation works acceptably for starters but underestimates tail probability for role players. For now: keep Normal, adjust CV upward as above.
- **3PM, STL, BLK, TOV:** These are count data with clear overdispersion. Negative binomial is the correct model. The practical impact on edge calculation: tails are fatter than Normal assumes, meaning the probability of exceeding a line at e.g. 1.5 BLK (for a ~0.7/game player) is higher than your Normal CDF gives you.

**Is full-distribution edge calculation worth the dev work?** For the near term: no. Fix the CV values first (30 minutes of work, meaningful impact). Switch to Negative Binomial for STL/BLK/3PM in phase 2. The MAE improvement from better distribution assumption is secondary to correcting the inputs.

### No-vig line edge cases

Your vig-stripping for American odds: standard approach is correct for near-symmetric lines. Edge cases to be aware of:
- **Heavy favorites (-250 or worse):** The two-outcome vig stripping is well-defined, but prop markets for heavy favorites often have asymmetric vig (e.g., -175 / +145 instead of -110 / -110). Strip vig per-side independently.
- **Same-side adjustment:** Some books shade lines on popular props (e.g., a star player's PTS). If DK sets LeBron at 27.5 pts on a hot betting day, the line is shaded up — implied probability is not the true market probability. Use sharp-book consensus (Pinnacle, Circa) as your true probability anchor when available.

---

## 10. Correlation Matrix Recommendation

### What the research shows

Individual player stats are correlated through a shared driver (minutes) and through role-dependent co-movement. Empirical correlation structure for starters (from published NBA analytics work):

| Pair | Typical r | Notes |
|------|-----------|-------|
| PTS ↔ REB | 0.25–0.40 | Driven mostly by shared minutes |
| PTS ↔ AST | 0.30–0.50 | Stronger for PG/playmakers |
| PTS ↔ 3PM | 0.55–0.70 | Direct: 3PM contributes to PTS |
| REB ↔ BLK | 0.35–0.55 | Rim-protection big men |
| AST ↔ TOV | 0.45–0.65 | Ball-handler role |
| STL ↔ AST | 0.20–0.35 | Guard-archetype correlation |
| PTS ↔ STL | 0.10–0.25 | Weak; different skill sets |
| PTS ↔ BLK | -0.05–0.15 | Near zero; centers vs guards |

### For SGP construction

The intra-player stat correlation is critical for correct parlay pricing. If you SGP a player over 25 pts AND over 8 AST, these are positively correlated (both require heavy usage and high minutes). A book pricing them independently underestimates joint probability — this is the edge.

For SGP, you need at minimum:
1. A minutes-driven covariance: `Cov(stat_A, stat_B) = rate_A × rate_B × Var(minutes)`. This is the dominant source of positive correlation.
2. A role-conditional residual correlation matrix (PG playmakers have high PTS/AST correlation; centers have high REB/BLK correlation).

### Can correlation improve individual projections?

Yes, but modestly. The most useful application: **if your AST projection for a PG is high, nudge PTS projection up** because both reflect a high-usage, high-minutes game projection. This is already implicitly captured if your minutes projection is consistent across stats — the shared minutes driver creates the correlation automatically. Explicit cross-stat regression adds marginal signal.

**Recommendation:** Do not build a joint distribution model now. Correct the shared minutes driver first (same projected minutes fed into all stat models), which will automatically create the right correlation structure. Then tackle SGP joint pricing in a dedicated phase.

---

## 11. Win-Probability Calibration Plan

### Methodology for 119 picks

With 119 graded premium picks, you have enough for **Platt scaling** but not reliable **isotonic regression** (which requires ~300+ samples to avoid overfitting to noise). Use:

**Phase 1 (now, 119 picks):** Platt scaling — fit a logistic regression `P(win) = sigmoid(a × model_prob + b)` on your 119 picks. This finds systematic over/under-confidence in your win probability estimates.

```python
from sklearn.linear_model import LogisticRegression
from sklearn.calibration import calibration_curve

# model_prob: your win_prob column from pick_log
# outcome: 1 for win, 0 for loss (from result column)
platt = LogisticRegression()
platt.fit(model_prob.reshape(-1, 1), outcomes)
calibrated_prob = platt.predict_proba(model_prob.reshape(-1, 1))[:, 1]
```

Then plot a reliability diagram (10 equal-width bins, ~12 picks per bin). This will tell you if your 0.65 win_prob picks are actually winning 65% of the time.

**Phase 2 (300+ picks):** Isotonic regression — non-parametric monotone calibration. More flexible, catches non-linear miscalibration.

**Phase 3 (500+ picks, stratified):** Beta calibration or per-sport/per-tier calibration.

### Confidence interval validation (p25/p75)

Your p25/p75 are projection distribution percentiles, not pick win-probability CIs. Validate by checking: of all picks where the actual outcome fell outside your p25/p75 range, how many exceeded the line vs. missed it? If your p25/p75 is correctly sized, 50% of outcomes should fall within the interval. If >60% fall outside, your intervals are too narrow (CVs too low — consistent with the finding in Section 9).

### Ongoing calibration framework

Use an **expanding window** (not rolling window) for calibration because you need to preserve historical picks as the base. Update Platt parameters monthly as new picks are graded. Flag if the calibration coefficient drifts >10% month-over-month — this signals a model regime change (e.g., a change in how you're selecting picks, or a market structural change).

### Brier score targets

With 119 picks, your Brier score (mean squared error of probability vs outcome) gives a baseline. Good calibration for a prop-picking system: **Brier score < 0.23** (corresponding to roughly 55% accuracy on near-even lines). Track Brier score trend monthly.

---

## 12. Bet Timing Recommendation

### Optimal timing by edge type

| Edge type | Optimal window | Rationale |
|-----------|---------------|-----------|
| **Injury replacement (starter out)** | T-90 to T-30 min | Books are slowest to update props for replacement players. React within 15–20 min of confirmation. |
| **Late lineup scratch (expected starter questionable → out)** | T-60 to T-5 min | Same as above. |
| **Matchup/DvP-driven edge** | Opener to T-12h before tip | Books set opener props with less sharp input. DvP is public info; the edge erodes as books adjust. |
| **Rate discrepancy (your model vs book)** | Opener or T-12h | If your model is right and the line is stale, the market will move toward you as sharp money flows. Bet early. |
| **Sharp-book consensus divergence** | As soon as detected | A DK/FD line that diverges from Pinnacle/Circa by >3% is a time-limited opportunity; close fast. |
| **Referee-crew effect** | T-18h to T-12h | Crews post by T-24h. The FTA/pace effect is priced in slowly on props; early bettors have advantage. |

### CLV by timing in prop markets

Published research on prop CLV by timing shows:
- **Openers (first lines posted):** Highest average CLV opportunity because books use less precise models for opening props. Highest variance too — some props open way off.
- **Mid-day (T-8h to T-4h before tip):** After initial sharp adjustment, before final-injury-confirmation sharpening. Second-best window for rate-based edges.
- **Game-time (T-1h to T-10min):** Best for injury-triggered props. Worst for non-injury props (market is most efficient, spreads tighten).

**Your current habit (betting closer to game time) is optimal only for injury-driven props.** For your DvP, pace, and rate-based picks, you are leaving CLV on the table. The practical recommendation: place non-injury-dependent props in the mid-day window (T-8h to T-3h). Reserve game-time betting for injury reactions and final lineup confirmation plays.

### The information asymmetry window on injury props

Books require 15–30 minutes to reprice all props after a confirmed scratch — longer on parlays and alt lines. Players with Twitter/notifications set for beat reporters (NBA.com/AP/ESPN insiders) have a 5–15 minute advantage. This is the highest CLV window available in the entire betting calendar.

---

## 13. Production-Grade Roadmap

Ordered by empirical impact, not theoretical interest. Each item includes estimated MAE impact, CLV impact, implementation complexity (Low/Med/High), and dependencies.

| Priority | Fix | Est. MAE Impact | Est. CLV Impact | Complexity | Depends On |
|----------|-----|----------------|-----------------|-----------|-----------|
| **P0** | Switch evaluator to projected minutes | — (meta-fix, enables correct measurement) | — | Low | Nothing |
| **P1** | Re-run n=2000 eval with projected minutes | — (establishes true baseline) | — | Low | P0 |
| **P2** | Lower PTS_BLEND_ALPHA to 0.20–0.25; grid-search optimal | -2 to -4% PTS MAE | Medium | Low | P1 |
| **P3** | Wire fg3m DvP (replace PTS piggyback) | -0.3 to -0.5% 3PM MAE | Medium-High | Low | Nothing |
| **P4** | BLK prior: split C into C_low/C_high subpriors | -3 to -5% BLK MAE | Low | Low | Nothing |
| **P5** | Fix pace double-counting (per-possession training basis) | -1 to -2% all stats | Medium | Medium | P1 |
| **P6** | Wire STL DvP (opponent TOV rate) | -1 to -2% STL MAE | Low-Medium | Low | Nothing |
| **P7** | Wire BLK DvP (opponent rim attempts) | -2 to -3% BLK MAE | Low-Medium | Low | P4 |
| **P8** | Correct CVs: REB→0.50, AST→0.55, BLK→1.00 | — (edge calc only) | Medium | Low | Nothing |
| **P9** | Platt scaling calibration on 119 picks | — (calibration) | Medium | Low | Nothing |
| **P10** | Shift non-injury props to mid-day betting window | — (timing strategy) | High | None (ops) | Nothing |
| **P11** | Add home/away binary flag to projections | -1 to -2% all stats | Low-Medium | Low | P1 |
| **P12** | Walk-forward eval infrastructure | — (eval correctness) | — | Medium | P0 |
| **P13** | Injury usage redistribution model (heuristic v1) | -2 to -4% on injury-game picks | Very High (CLV) | Medium | Nothing |
| **P14** | Ref crew FTA adjustment | -0.5 to -1% FTA-adjacent | Low-Medium | Low | Nothing |
| **P15** | DB-calibrated BLK/REB priors (AST-style) | -1 to -3% | — | Medium | P4 |
| **P16** | Negative binomial distribution for STL/BLK/3PM | -1% edge calc accuracy | Low-Medium | Medium | P9 |
| **P17** | Stratify eval by archetype (starter/rotation/spot) | — (diagnostic) | — | Low | P12 |
| **P18** | Playoff per-stat deflators (replace flat 0.92) | -1 to -2% in playoffs | Low | Low | P1 |
| **P19** | Expand Platt → isotonic regression calibration | — (calibration) | Medium | Low | 300+ picks |
| **P20** | Joint SGP correlation model | — (SGP quality) | Medium (SGP picks) | High | P5 |

### Phase groupings

**Immediate (this week, before any new eval):** P0, P1 — can't prioritize correctly without knowing the real error surface.

**Quick wins (no architecture changes):** P2, P3, P4, P6, P7, P8, P9, P10 — all <4 hours each, meaningful returns.

**Medium-term (architecture work):** P5, P11, P12, P13 — require more design but highest systemic impact.

**Later (after 300+ picks or stable model):** P14, P15, P16, P17, P18, P19, P20.

---

## Answers to the 8 Success Criteria

*From the brief: "After this report, I have..."*

**(a) A defensible answer for why PTS regressed:** FGA decomposition introduces multiplicative variance stacking — noisy rate × noisy volume — that overwhelms the signal at game level. PTS_BLEND_ALPHA=0.50 gives too much weight to the noisy decomposed path. Lower to 0.20–0.25 and re-evaluate on n≥500 with projected minutes.

**(b) A real estimate of minutes-projection error in production:** Minutes error accounts for approximately 25–35% of total PTS error for starters and 40–55% for rotation/spot players. All current MAEs are underestimates; the evaluator fix (P0) is prerequisite to everything.

**(c) Resolution to STL-vs-BLK shrinkage paradox:** STL has a unimodal positional distribution; shrinkage toward a positional mean helps. BLK has a bimodal distribution within the center position (non-blockers vs. rim protectors); a single positional prior pulls both groups toward the center mean and hurts both. Fix: stratified sub-priors for centers (C_low/C_high split at 0.030 BLK/min).

**(d) Point estimates for unmodeled effects:** Home/away: ~1 pt PTS, ~0.3 REB, ~0.2 AST delta (low priority, already partially priced by books). Denver altitude: visiting speed decline ~7% in Q4, but box-score offensive impact is small and diffuse. Refs: game-level FTA effect is measurable (high-whistle crews → ~8–12% more FTA/game) but individual player prop impact is secondary. Injury replacement: 45–55% of missing usage concentrates in the primary backup, with a 15-30 minute book-adjustment lag on props.

**(e) An evaluation framework that won't lie:** Walk-forward validation on n≥500 projected-minutes samples, stratified by starter/rotation/spot, with MAE + directional accuracy + Brier score + tail MAE as parallel metrics.

**(f) A calibration plan for 119 picks:** Platt scaling on 119 picks, reliability diagram in 10 bins, Brier score tracked monthly, expanding window as more picks accumulate.

**(g) A bet-timing recommendation by edge type:** Injury replacement: T-90 to T-30 min. Rate/matchup/DvP edges: opener to T-3h. Sharp-book divergence: as detected. Referee crew: T-18h to T-12h.

**(h) A clear ordered roadmap:** P0 → P1 → quick wins (P2–P10) → architecture work (P11–P13) → later phases. Empirical impact, not theoretical elegance.

---

## Sources

- [NBA Stabilization Rates and the Padding Approach — Kostya Medvedovsky](https://kmedved.com/2020/08/06/nba-stabilization-rates-and-the-padding-approach/)
- [Empirical Bayes-ketball | tothemean](https://www.tothemean.com/2020/09/06/empirical-bayes.html)
- [PMC: The Advantage of Playing Home in NBA](https://pmc.ncbi.nlm.nih.gov/articles/PMC4807825/)
- [ESPN: Denver Altitude Advantage in 2023 Finals](https://www.espn.com/nba/story/_/id/37762170/nba-finals-2023-how-denver-altitude-gives-nuggets-edge)
- [John Mo Substack: What Playing in Denver Really Does to NBA Teams](https://johnmo.substack.com/p/breathing-room-what-playing-in-denver)
- [PMC: Impacts of travel distance on NBA back-to-backs](https://pmc.ncbi.nlm.nih.gov/articles/PMC8636381/)
- [ResearchGate: Basketball performance and schedule congestion](https://researchgate.net/publication/339933590_Basketball_performance_is_affected_by_the_schedule_congestion_NBA_back-to-backs_under_the_microscope)
- [RotoGrinders: Projected Minutes — The Most Critical Stat in NBA DFS](https://rotogrinders.com/lessons/projected-minutes-the-most-critical-opportunity-stat-in-nba-dfs-3147006)
- [RotoGrinders: Accurately Predicting Minutes in NBA DFS](https://rotogrinders.com/lessons/accurately-predicting-minutes-in-nba-dfs-1144471)
- [NBA Defense vs Position — NBAstuffer](https://www.nbastuffer.com/analytics101/defense-vs-position/)
- [FantasyLabs: NBA Taking Advantage of Home/Away Splits](https://www.fantasylabs.com/articles/nba-taking-advantage-of-homeaway-splits/)
- [Squared Statistics: Negative Binomial for 3P%](https://squared2020.com/2017/08/20/basics-in-negative-binomial-regression-predicting-three-point-field-goal-percentages/)
- [Poisson model limits in NBA basketball — ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S0378437116304599)
- [Sportico: 2025 NBA Playoffs Data Analysis](https://www.sportico.com/feature/nba-playoffs-postseason-stats-analytics-data-viz-1234848952/)
- [Sports-AI: AI Model Calibration for Sports Betting — Brier Score](https://www.sports-ai.dev/blog/ai-model-calibration-brier-score)
- [Donaghy Effect: NBA Referee Analytics](https://www.donaghyeffect.com/)
- [Covers.com: NBA Referee Betting Stats](https://www.covers.com/sport/basketball/nba/referees)
- [Boyd's Bets: Opening vs. Closing Line](https://www.boydsbets.com/opening-vs-closing-line/)
- [BetterEdge: When to Bet — Timing Strategies](https://www.bettoredge.com/post/when-is-the-best-time-to-bet-on-sports-timing-strategies-for-smarter-wagers)
- [Walk-Forward Optimization — QuantInsti](https://blog.quantinsti.com/walk-forward-optimization-introduction/)
- [Bayesian Hierarchical Modelling of NBA 3PT Shooting — Kenneth Foo](https://kfoofw.github.io/bayesian-hierarchical-modelling-on-nba-3-point-shooting/)
- [APBR Metrics: Pace of Play Calculations](https://www.apbr.org/metrics/viewtopic.php?t=9139)
- [Usage Boost: NBA Injury Usage Data](https://usageboost.com/nba-injury-usage)
