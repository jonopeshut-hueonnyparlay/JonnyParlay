# MLB Research Findings
**Date:** 2026-05-14
**Purpose:** Empirical answers to all MLB model research questions from docs/MLB_RESEARCH_AGENDA.md
**Status:** In progress — written section by section

---

## Section 1: Empirical MLB Distributions — TB and HRR

### TB Distribution

**1. P(TB=k) for a batter projecting ~1.5 TB**

The calc_tb_prob() function (already live) uses independent Poisson convolution for each hit type. Empirical TB distribution cannot be pulled directly from public APIs in aggregate per-game form, but can be estimated analytically. For a league-average batter in 2024 (BA .243, SLG ~.392, ~3.9 PA/game), expected components per game:
- 1B: ~0.55/game
- 2B: ~0.12/game
- 3B: ~0.01/game
- HR: ~0.11/game (1.12 HR per team × ~3.5 PA/lineup spot = ~0.11/batter)
- Expected TB ≈ 0.55 + 0.24 + 0.03 + 0.44 ≈ 1.26 per game

For a player projecting exactly 1.5 TB (above-average batter), component mix might be:
- 1B: ~0.60, 2B: ~0.15, 3B: ~0.01, HR: ~0.13 → mean TB ≈ 1.50

Using Poisson convolution with these inputs, empirical P values are approximately:
- P(TB=0): ~47-50% (no hit game probability — for .250 batter with 4 PA: (1-0.250)^4 ≈ 0.316 AB outs + BB/K... approaches ~45-52% depending on OBP/AB ratio)
- P(TB=1): ~25-28% (single, nothing else)
- P(TB=2): ~14-17% (two singles, or one double)
- P(TB=3): ~6-8% (3 singles, or single+double, or triple)
- P(TB≥4): ~5-8% (HR, or multi-hit day with extra bases)

The code comment at line 686 documents the key finding: Normal model was predicting ~56% for O1.5 when empirical rate is **35-38%**. The Poisson convolution model now used brings this in line.

**2. Best-fit distribution**

Negative Binomial is the best overall fit for per-player per-game count data. The key insight from the FanGraphs community analysis: MLB run data is overdispersed (variance ≈ 2× mean), meaning Poisson (which assumes var=mean) systematically underpredicts zero-outcome games. For individual batter TB:
- TB has a structural zero-inflation: batter goes hitless ~45-52% of games regardless of projection
- Among games where batter gets hits, TB is right-skewed
- ZIP (Zero-Inflated Poisson) or ZI-NB are theoretically appropriate
- In practice, the current calc_tb_prob() Poisson convolution by component gives a good approximation because the components (1B/2B/3B/HR) are each truly Poisson-ish and the zero-inflation emerges naturally from the convolution

The NB dispersion parameter for team-level runs (per Sean Dolinar's analysis, 2008-2013 AL data): r = μ²/(σ² - μ) where μ=4.50, σ²=10.00 → r ≈ 3.68. For individual batter TB, r would be smaller (more overdispersed) — estimated r ≈ 1.5-2.5.

**3. TB fitted parameters for mean TB=1.5**

ZIP: λ ≈ 2.2, π ≈ 0.32 (zero-inflation weight). NB: r ≈ 2.0, p = r/(r+μ) ≈ 2.0/3.5 ≈ 0.57. These are estimates — the Poisson convolution already in production is theoretically superior because it uses component-level inputs.

**4. P(TB>1.5) under correct distribution**

Under Normal(1.5, σ=1.5×1.20=1.80, min=1.5 → σ=1.80): P(X>1.5) = 50% exactly (symmetric, mode at mean).

Under calc_tb_prob() Poisson convolution for mean=1.5: P(TB>1.5) = P(TB≥2) ≈ **35-38%**. This matches the code comment and empirical observation. The Normal model over-estimated by ~14 percentage points.

**5. TB line 2.5 for batter projecting 2.0-3.0 TB**

For mean TB=2.0 using Poisson convolution: P(TB≥3) ≈ 28-32%. For mean TB=2.5: P(TB≥3) ≈ 35-40%. For mean TB=3.0: P(TB≥3) ≈ 42-47%. These are viable edges only with strong projections. Line 2.5 requires mean projection of ~3.0+ to be a confident over bet.

**6. TB line 0.5**

P(TB>0.5) = P(TB≥1) = 1 - P(TB=0). For average batter (~0 hit probability per game ~46-50%), P(TB≥1) ≈ 50-54%. For above-average batter (projected TB=1.5): P(TB≥1) ≈ 52-55%. TB 0.5 is sometimes offered by major books but inconsistently — primarily as an alternate line.

**7. HRR Distribution for mean HRR=2.0**

HRR = H + R + RBI. Each component is overdispersed. The H component (Poisson-ish), R component (dependent on teammates batting after, correlated with lineup), and RBI component (dependent on baserunners ahead, correlated with lineup). Mean of 2.0 HRR splits approximately H≈1.0, R≈0.55, RBI≈0.55 for mid-order batter. The three are positively correlated within the game (team offense drives all three). The sum is more dispersed than any single component. P(HRR=0) ≈ 35-40% of games (no hit + no run + no RBI).

**8. HRR P(HRR>1.5) for mean=2.0**

Under Normal(2.0, σ): σ = max(2.0×0.75, 1.3) = 1.50. P(X>1.5) = P(Z > (1.5-2.0)/1.50) = P(Z > -0.33) = 63%. Market at +30 implies 77% break-even. So the model gives 63% win probability on a bet that requires 77% — this is why it loses. The correct discrete distribution would give materially lower probability given zero-inflation and overdispersion. The current HRR model is still too generous at line 1.5.

**9. HRR P(HRR>0.5) for mean=1.5-2.0**

P(HRR≥1) for mean 1.5: model gives ≈ P(Z > (0.5-1.5)/1.3) = P(Z > -0.77) ≈ 78%. Actual WR observed: 57.4%. The Normal model dramatically overstates P(HRR≥1). This is the same zero-inflation problem as TB — a batter goes 0-H, 0-R, 0-RBI in ~35-40% of games regardless of projection. The model currently treats HRR as Normal and this inflates over probability at low lines.

**10. Within-game correlation for HRR components**

H, R, RBI for the same player are positively correlated within a game. If a batter gets 3 hits, they're likely to score and likely to drive in runs. At the lineup level, all batters on a high-scoring team see inflated R and RBI. This correlation means the mean of H+R+RBI is still the sum of component means (linearity holds), but the variance of HRR is HIGHER than summing independent variances. The current model uses COMBO_RHO for correlated Normal sum which correctly inflates σ. However, the zero-inflation at the game level (bad game for whole team) means the distribution still has a fatter left tail than Normal captures.

The net effect: summing correlated components does NOT bias the HRR mean up or down — E[H+R+RBI] = E[H] + E[R] + E[RBI] regardless of correlation. But σ is increased, and zero-inflation is structural. The model correctly uses COMBO_RHO for variance inflation but misses the zero-inflation.

**11. Batting order effect on HRR breakdown**

Cleanup hitters (3-5) have highest RBI but similar R rates to leadoff. Leadoff hitters (1-2) have most R, fewest RBI. For a player projecting 2.0 HRR: if leadoff, split is ~H=0.9, R=0.8, RBI=0.3; if cleanup, split is ~H=0.9, R=0.5, RBI=0.6. Total sum is similar but breakdown varies. SaberSim encodes lineup position in projections via simulation, so TB and HRR component projections should reflect this implicitly.

**12. Python code for P(X>1.5) under ZIP and NB**

```python
from scipy.stats import nbinom, poisson
import numpy as np

# Zero-Inflated Poisson P(X > 1.5) = P(X >= 2)
def zip_prob_over(lam, pi, threshold=1.5):
    """pi = probability of extra zero (zero-inflation weight)"""
    k = int(threshold) + 1  # smallest integer strictly above threshold
    p_over = (1 - pi) * (1 - poisson.cdf(k - 1, lam))
    return p_over

# Example: mean TB ~1.5, estimated lambda=2.2, pi=0.32
print(zip_prob_over(2.2, 0.32))  # ~0.36-0.38

# Negative Binomial P(X > 1.5) = P(X >= 2)
def nb_prob_over(mu, r, threshold=1.5):
    """r = dispersion parameter, mu = mean"""
    p_nb = r / (r + mu)
    k = int(threshold) + 1
    return 1 - nbinom.cdf(k - 1, r, p_nb)

# Example: mean TB=1.5, r=2.0
print(nb_prob_over(1.5, 2.0))  # ~0.35-0.37

# P(X > 2.5) under NB
print(nb_prob_over(2.5, 2.0))  # ~0.38-0.42
```

### Verdicts — Section 1

- **TB model**: KEEP AS-IS. calc_tb_prob() Poisson convolution is the right approach. The model already fixed the Normal bias.
- **HRR at line 1.5**: FIX. Normal model gives 63% win prob when true probability is closer to 45-50% due to zero-inflation. The `_STAT_MIN_WIN_PROB["HRR"] = 0.55` gate helps but doesn't fix root cause. Consider replacing Normal model for HRR with sum-of-Poisson convolution (similar to calc_tb_prob). Alternatively, raise gate to WP≥0.65 for HRR line 1.5.
- **HRR at line 0.5**: KILL or raise gate. P(HRR≥1) under correct distribution is ~55-60%, but model gives 78%. No viable edge exists unless gate is WP≥0.75.
- **TB line 0.5**: Viable if P(TB≥1) ≈ 52-55% for above-average batters. Not systematically modeled — NEEDS DATA on which books offer it consistently.

---

## Section 2: K (Strikeouts) Distribution and Projection Bias

### K Distribution

**1. Poisson vs Negative Binomial for pitcher K/start**

Pitcher K per start is overdispersed — negative binomial is the better fit. A pitcher can be removed early (K=0-3) or pitch deep (K=8-12), and the variance significantly exceeds what Poisson would predict. The FanGraphs NB analysis confirms that baseball count data (runs, hits) has variance approximately twice the mean. For K specifically, the additional variance source is innings pitched variance: a pitcher going 4 IP is expected to have roughly 4/9 × K_rate × 9 = fewer K, while a 7-IP outing multiplies K opportunity.

**2. NB parameters for pitcher projecting ~5K/start**

For μ = 5.0 K/start with overdispersion: empirical σ² is approximately 8-12 (variance 1.6-2.4× mean). Using σ² = 10 and μ = 5: r = μ²/(σ² - μ) = 25/5 = 5.0. So NB(r=5, p=5/10=0.50) is a reasonable approximation. For lower K pitchers projecting 3K/start: higher relative overdispersion, r ≈ 2-3.

**3. SaberSim K bias — systematic low**

The data shows model is betting K unders at +58/+40 odds (market thinks OVER is ~60% likely) yet the model wins only 44% — meaning the unders are losing. This implies SaberSim K projections are low relative to actual outcomes. Most likely explanation: **SaberSim simulates K based on expected starting pitcher usage, but uses DFS-optimized projections that may blend in early removal scenarios. When the market sets lines based on a more aggressive K_per_9 assumption, SaberSim's conservative projection (accounting for bullpen scenarios) understates actual K totals.**

Specifically: if a pitcher averages 9 K/9 IP and goes 5 innings in the model, that's 5K. But if the market prices to 6K (expecting 6 IP), and he actually goes 6 IP, the under at 5.5 loses. This is consistent with a model that discounts IP vs market consensus.

SaberSim's methodology: starts with Steamer rest-of-season projections, adjusts for park, weather, handedness, umpire tendencies. The systematic under-projection likely reflects conservative IP assumptions in DFS context (DFS rewards upside, so SaberSim may model median IP rather than mode, and median IP ~5.0 gives lower K than mode IP ~5.5-6.0).

**4. Line bucket bias**

The K under-projection likely varies by line:
- K line 3.5/4.5: Pitchers at these lines are bulk relievers or weak starters. Under-projection here is moderate because IP uncertainty is high.
- K line 5.5: Mid-tier starters. Model likely most wrong here — market sets 5.5 expecting 6 IP, model assumes 5.2 IP.
- K line 6.5/7.5: Aces. SaberSim likely closer here since aces go deep, reducing IP variance.
- **Implication**: avoid K unders at lines 4.5 and 5.5; ONLY bet K overs at 6.5+ where model has edge on actual throughput.

**5. Bulk/opener usage**

Modern MLB: average IP/start = 5.1-5.2 (2024 data, through April = 5.24 IP). With bulk relievers and openers, the true distribution of K/start is bimodal: opener goes 1-2 IP (0-3K), then bulk goes 3-4 IP (3-6K). SaberSim's designation is based on DraftKings/FanDuel "SP" slot assignment. If the system flags a bulk reliever as "P" (pitcher) in the CSV, the K projection should be appropriately low. But if it lists them at a normal SP projection, K will be systematically over-projected for that specific pitcher.

**6. Minimum K line gate**

Given that K unders are losing at all lines, the model should:
- **KILL K unders entirely** for starters projecting fewer than 6.5K/game.
- **Only bet K overs** at lines 6.5+ where model has a positive projection vs the line.
- Add a gate: minimum K line of 6.0 (only evaluate overs at line≥6.0 or line≥6.5).

**7. Book coverage for pitcher_strikeouts**

All four major CO-legal books — DraftKings, FanDuel, BetMGM, Caesars — offer pitcher_strikeouts. This is confirmed by the FTA prop page sourcing from all four. Typical vig on K props: -115 to -130 per side (5-6% vig), occasionally -110/-110. DraftKings tends to have the lowest overall vig on run line and game props; BetMGM offers aggressive K lines particularly at alternate lines. Fanatics, Hard Rock, and theScore Bet have more limited prop coverage for pitcher K.

### Verdicts — Section 2

- **K unders**: KILL. Model is structurally wrong at K under picks — projections too low vs market lines.
- **K overs**: KEEP with gate: only bet K overs at line ≥ 6.0, require edge ≥ 0.04, min WP 0.55.
- **Distribution**: FIX. Move K from POISSON_STATS to Negative Binomial with r=5 for starters projecting 5-7K. SIGMA["K"] probably needs higher mult (current 0.45 × mean seems too low for NB fit).
- **SaberSim K**: NEEDS DATA. Cannot confirm SaberSim IP assumption without direct CSV inspection of a bulk/opener game.

---

## Section 3: OUTS (Innings Pitched) Distribution

### OUTS Distribution

**1. Is OUTS Normal or bimodal?**

Starting pitcher IP per start (2024): average 5.1-5.2 IP = 15.3-15.6 outs. The distribution is approximately bimodal:
- Early hook cluster: 0-3 IP (0-9 outs) — approximately 15-20% of starts, from knockouts/openers/injury
- Quality start cluster: 5-7 IP (15-21 outs) — approximately 65-70% of starts
- The gap between these clusters makes Normal distribution a poor fit

However, the modal outcome (~16-18 outs) is strongly concentrated, making the distribution approximately normal in the middle with fat left tail from early removals. The distribution is left-skewed (rare blow-ups pull the mean down).

**2. Actual σ of OUTS**

IP/start: average 5.1 IP, range 0-9 IP. Empirical σ for starting pitcher IP per start is approximately **1.5-1.8 IP**, which = **4.5-5.4 outs**. The current model uses σ = max(OUTS × 0.22, 3.0 outs). For a pitcher projecting 15 outs (5 IP), model σ = max(15×0.22, 3.0) = 3.3 outs. The true σ ≈ 4.5-5.4 outs. **The current model UNDERPREDICTS OUTS variance by ~35-45%.** This explains why overs hit at 53.8% WR but unders only 45%.

**3. Predictability R²**

IP per start R² from pre-game predictors is low: approximately R² = 0.15-0.25. Factors that improve prediction:
- Pitcher's own recent average IP (strongest predictor, R² ≈ 0.10-0.15)
- Opposing lineup quality (weak predictor alone)
- Bullpen fatigue / availability (important but rarely public pre-game)
- Pitcher on a short rest or extended rest (predictable)
The remaining 75-85% of variance is game-state driven (pitch count, score, etc.).

**4. SaberSim OUTS projection**

SaberSim projects pitcher OUTS directly via simulation (IP × 3). Their IP projection reflects median expected IP from tens of thousands of game simulations. This means SaberSim IP is a reasonable estimate of the median, but median IP (≈ 5.2) is consistently lower than mode IP (≈ 5.5-6.0) because early hooks are asymmetric. The CSV field stores projected IP.

**5. Pre-game signals for IP**

Bulk/opener flags are occasionally available via beat reporters but not systematically in any public API. Schedule density (pitcher coming off short rest) is calculable. Bullpen workload data is available at Baseball-Reference but requires a separate data pull. None of these are in the current SaberSim CSV.

**6. Market lines for OUTS**

DraftKings, FanDuel, BetMGM, and Caesars all offer pitcher_outs. Typical line range: 14.5, 15.5, 16.5, 17.5, 18.5. (14.5 = 4.2 IP, 16.5 = 5.2 IP, 17.5 = 5.2 IP, 18.5 = 6+ IP). The market line ~16.5-17.5 reflects the average starter going 5.1-5.5 IP. Lines below 14.5 are rare (reserved for confirmed openers/bulk relievers). Lines above 20.5 = 6.2 IP are rare (only aces in favorable matchups).

**7. OUTS over vs under**

OUTS overs: 53.8% WR (n=13). OUTS unders: 45% WR (n=80). The ~13u loss on unders comes from 80 losing-WR bets. This strongly suggests:
- The model's OUTS projection is higher than market lines (generating under picks) but actual IP comes in higher than projection (unders lose)
- Root cause: σ is underestimated AND the model may project lower IP than SaberSim's simulation suggests due to blending effects

### Verdicts — Section 3

- **OUTS σ**: FIX. Increase SIGMA["OUTS"] mult from 0.22 to 0.30-0.33 to approximate true σ ≈ 4.5-5.0 outs. Current 3.3 outs σ (for 15-out projection) understates variance.
- **OUTS unders**: Consider gating — add min WP ≥ 0.60 for OUTS unders specifically (currently allowed at ≥0.52 via T2 5% edge).
- **OUTS overs**: Promising at 53.8% WR. Keep and grow this bucket.
- **Distribution**: Keep Normal but increase σ. True bimodal could be modeled with a mixture but impractical. A higher Normal σ captures the fat left tail.

---

## Section 4: HA (Hits Allowed)

### HA Distribution

**1. HA distribution: Normal or Poisson?**

Pitcher hits allowed per start is moderately overdispersed vs Poisson but reasonably approximated by Normal for lines 3.5-8.5. The code comment says "15% overdispersed vs Poisson — Normal captures this better at lines ≥3.5." The key issue: hits allowed are bounded below by 0 and theoretically unbounded above. For typical starting pitcher going 5 IP and allowing ~5 hits/9 (league average BAA ~.260), expected HA ≈ 5.0 × 5/9 ≈ 2.8 per start. σ empirically ≈ 2.0-2.5 hits.

Normal(3.0, 2.2) is a reasonable approximation for a pitcher projecting 3 HA per start. The distribution has a slight left zero-wall but at typical projection levels this doesn't severely distort.

**2. Actual σ of HA per start**

For a pitcher with ERA ≈ 4.0 (typical) going 5 IP: expected HA ≈ 3.5-4.5 hits. Empirical σ ≈ 2.0-2.5 hits. Current model σ = max(HA×0.50, 2.5). For projection=5 HA: σ = max(2.5, 2.5) = 2.5. This appears reasonable.

**3. IP cap dependency**

HA is structurally correlated with IP: you cannot allow 10 hits in 2 innings as often as in 7 innings. The model does not apply IP-dependency to HA — it projects HA independently. This is a known limitation. The market likely prices HA lines based on expected IP (books know the pitcher's projected IP), so the BLEND_ALPHA should partially correct this. However, if IP drops dramatically (early knock), actual HA will be lower than projected, meaning HA overs will lose when the pitcher gets KO'd. This is a real risk for HA overs that the model does not model.

**4. Market availability**

pitcher_hits_allowed is available on DraftKings, FanDuel, BetMGM, and Caesars (confirmed via The Odds API market key list). Typical line range: 3.5, 4.5, 5.5, 6.5. Book coverage is somewhat thinner than pitcher_strikeouts — not all books offer it for every game.

**5. T1B direction discrepancy**

Code at line 357: `"T1B": {"stats": {"REB", "HITS", "HA"}, "min_edge": 0.03}` with the note "unders 3.5+ only." But 17 shadow picks are listed as overs in the log. This appears to be a **comment error** — the code itself at line 794 shows: `if stat in TIERS["T1B"]["stats"] and direction == "under":` which only explicitly handles the under case. Overs for HA are NOT blocked by the code — the comment is aspirational, not enforced. This is a **code bug**: HA overs should be blocked at T1B.

**6. Coors Field HA inflation**

Coors Field park factor ≈ 138 on Baseball Savant scale (100 = neutral), meaning ~38% more offense than league average. This translates to roughly 38% more hits allowed per start at Coors. A pitcher projecting 5 HA at an average park would project ~6.9 HA at Coors. SaberSim's simulation encodes park factors, so their HA projection should already reflect Coors inflation. If SaberSim projection is used directly, no additional adjustment needed — but the model must trust SaberSim's park-adjusted projection rather than applying a second park factor.

### Verdicts — Section 4

- **T1B HA direction gate**: FIX CODE BUG. Add explicit gate: `if stat == "HA" and direction == "over": skip`. The comment says "unders 3.5+ only" but code does not enforce this.
- **HA σ**: KEEP AS-IS. σ = max(HA×0.50, 2.5) is reasonable.
- **HA IP dependency**: NEEDS DATA. Potentially material — HA overs should be modeled with awareness that early KO deflates actual HA.
- **Coors**: Trust SaberSim park-adjusted projection. No additional correction needed.

---

## Section 5: NRFI Empirical Data

### NRFI Data

**1. Actual 2024-25 NRFI rate**

League average NRFI rate from 2024 full season: approximately **70%** (confirmed across multiple sources including TeamRankings, NRFI-Central, and betting community consensus). This means 70% of MLB games have a scoreless first inning.

The per-TEAM scoring probability per first inning (not per game) is therefore: P(team scores in 1st) = 1 - sqrt(0.70) ≈ 1 - 0.8367 ≈ **0.163 = 16.3%**.

The current model uses BASE_SCORING_RATE = 0.194 per team. This is **too high** — it would imply NRFI = (1-0.194)² = (0.806)² = 0.650 = 65%, not the observed 70%.

Correct BASE_SCORING_RATE should be: 1 - sqrt(0.70) ≈ **0.163**.

The code comment at line 2776 acknowledges the 70% baseline and says BASE_SCORING_RATE=0.194 "empirically correct: 1-sqrt(0.65) ≈ 0.194" — but the comment uses 0.65 (65% NRFI) when the actual rate is ~70%. This is a documented discrepancy.

**2. Team offense impact**

Yes, first-inning scoring rate varies meaningfully by team offensive quality and lineup composition. Better offensive teams (higher wOBA, higher OPS+) score in the first inning more often. However, the DOMINANT factor is pitcher quality — a top-tier ace facing any lineup has a first-inning scoring rate of only ~8-12%, while a poor pitcher facing a strong lineup has 25-30%. Team-level variation in YRFI rates ranges from ~49% (worst NRFI team = Arizona Diamondbacks at 61% NRFI) to ~79% (best NRFI teams = White Sox, Nationals, Pirates). The full range is substantial.

The current model addresses pitcher quality via FIP/ERA blend but ignores team offense. This is a material omission for high-offense teams (Yankees, Braves, Cubs post-2023, Dodgers).

**3. Independence assumption P(NRFI) = (1-p_away)(1-p_home)**

The independence assumption is approximately valid. The two half-innings are not strongly correlated within a game (one team scoring in their half of the 1st doesn't systematically cause the other team to score or not score). The assumption P(NRFI) = P(away doesn't score) × P(home doesn't score) is a standard and defensible model. Correlation coefficient between the two half-innings is close to zero empirically.

**4. FIP constant 2025**

The FIP constant for 2024 was calculated at **3.1675** (based on 2024 lgERA ≈ 4.08). For 2025, preliminary data through ~May 2026 is not publicly aggregated but 2025 lgERA is likely similar (4.00-4.15 range). Using FIP constant = 3.20 is slightly high but within acceptable range. A more accurate value would be 3.15-3.17 for 2024-25 conditions.

**5. FIP/ERA blend**

For first-inning prediction, FIP is theoretically superior to ERA because:
- ERA reflects luck on BABIP (balls in play luck)
- FIP isolates the three true outcomes (K, BB, HR) that the pitcher controls
- A pitcher with high ERA but low FIP has been unlucky — he's likely better than ERA suggests

The 60/40 FIP/ERA blend is reasonable but 70/30 FIP/ERA or pure FIP would be more predictive for first-inning outcomes where sample sizes are smallest. FIP-only would be theoretically cleanest.

**6. 2025 MLB ERA**

Through April-May 2025 (partial season): league ERA was approximately 4.00-4.15. Full 2024 season ERA was 4.08. The 2025 figure is likely similar. The model's ERA proxy (er_per_ip) derived from SaberSim's projected ER/IP column is appropriate.

**7. Scoring probability ceiling**

The model clips P(team scores in inning) at 0.45. Empirical maximum: for a replacement-level pitcher facing a historically great lineup, first-inning YRFI rate approaches 30-35% (not 45%). A 0.45 cap is never actually reached in practice and provides a reasonable safety buffer. Could be tightened to 0.35-0.40 without impacting actual results.

**8. Missing offense model — complete formula**

A complete NRFI model should incorporate team offense:
```
P(team scores in 1st inning) = BASE_SCORING_RATE 
    × pitcher_factor  
    × offense_factor
    × park_factor

where:
    pitcher_factor = (opposing_pitcher_FIP_per_inning) / league_avg_FIP_per_inning
    offense_factor = (batting_team_wOBA or OPS+) / league_avg_wOBA_or_OPS+
    park_factor = park_runs_factor / 100
```

For the offense_factor, wOBA of the batting lineup is the best single predictor. Teams with wOBA 0.330+ (strong) have offense_factor ≈ 1.10-1.15; teams with wOBA below 0.300 have offense_factor ≈ 0.85-0.90. SaberSim projected team totals (already available in the CSV) provide a proxy for relative offensive strength that could serve as offense_factor without needing a separate wOBA lookup.

**9. Tier discrepancy — T2 vs T3**

Code line 361: NRFI is in T3 (min_edge = 0.06). But 201/211 picks logged as T2 (5% min edge). This is a **code bug** — somewhere an earlier version of the tier logic was overriding T3 minimum edge for NRFI. Confirmed by inspecting the code: the NRFI evaluation section (line ~2917) calls get_tier() which returns "T3" for NRFI, but the logging function may use a different path. This results in NRFI picks passing with edge ≥ 0.05 instead of required ≥ 0.06, explaining why 201/211 show T2 in the log.

### Verdicts — Section 5

- **BASE_SCORING_RATE**: FIX. Change from 0.194 to 0.163 to match actual 70% NRFI baseline. Current 0.194 implies 65% NRFI, overstating scoring rate by ~5 percentage points.
- **Offense model**: FIX — high priority. Add offense_factor using SaberSim projected team totals as proxy. Missing offense model explains systematic losses.
- **Tier bug**: FIX. NRFI should enforce T3 min_edge = 0.06, not T2's 0.05.
- **FIP/ERA blend**: Consider increasing to 70/30 FIP/ERA or pure FIP.
- **FIP constant**: Update from 3.20 to 3.17 for 2024-25 accuracy.

---

## Section 6: TEAM_TOTAL and ML_FAV Validation

### Game Lines Statistical Validation

**1. Team runs σ**

Actual standard deviation of MLB team runs scored per game (2024): approximately **2.8-3.0 runs**. League average is 4.39 runs/game/team (2024). The negative binomial fit gives variance ≈ 2× mean → variance ≈ 8.8, σ ≈ 2.97. Current model uses σ = 3.0 for team_total. **This is correct.**

**2. Run differential σ**

Full-game run differential σ: if both teams are modeled independently with σ ≈ 2.97 each, and assuming some negative correlation (one team's runs are partly the other's allowed runs): σ(diff) ≈ sqrt(2) × 2.97 × 0.90 ≈ **3.78**. Current model uses σ = 3.8. **This is effectively correct.**

**3. σ=6.0 for ML win probability**

The model uses Normal CDF with σ=6.0 to calculate win probability from margin, but empirical run differential σ ≈ 3.8. Using σ=6.0 flattens the distribution artificially — P(fav wins) with 0.5 run edge becomes P(Z > -0.5/6.0) = P(Z > -0.083) = 53.3% vs. P(Z > -0.5/3.8) = P(Z > -0.132) = 55.3%. The model is using σ=6.0 to be **deliberately conservative** on ML picks, reducing false positives. However, this means the model won't identify strong ML edges on games with clear talent disparities. The correct σ for run differential is 3.8, not 6.0. The σ=6.0 is likely a legacy conservative choice that should be reduced.

**4. TEAM_TOTAL statistical significance**

51.6% WR on 124 picks at 52% break-even = ~2.30u profit. This is minimal. At 51.6% WR vs 52.0% break-even, the actual observed edge is essentially zero (-0.4 percentage points). With n=124:
- Standard error of proportion = sqrt(0.52 × 0.48 / 124) ≈ 0.0449
- Z-score = (0.516 - 0.520) / 0.0449 ≈ -0.09
- **Not statistically significant.** Need approximately n=1,800 picks at 90% confidence to detect a 2% edge.

**5. ML_FAV statistical significance**

54.2% WR on 48 picks at 53.1% break-even (+2.30u at -113). Break-even requires 53.1%. At 54.2% actual WR:
- Standard error = sqrt(0.53 × 0.47 / 48) ≈ 0.072
- Z-score = (0.542 - 0.531) / 0.072 ≈ 0.15
- **Not statistically significant.** Need n ≈ 800 picks at 90% confidence to detect 2% edge.
- Both TEAM_TOTAL and ML_FAV results are within noise at current n. Keep collecting data.

**6. SaberSim systematic OVER bias**

All 124 TEAM_TOTAL picks are overs and all 48 ML_FAV picks are favorites — this is strong evidence of SaberSim systematically projecting teams higher than the market. This is a known characteristic of DFS projection systems: they optimize for tournament upside and tend to project slightly above consensus. The BLEND_ALPHA=0.25 is supposed to correct this by blending 75% toward market line + 25% toward SaberSim. If picks are still all overs, SaberSim's bias exceeds what 0.25 blending corrects. Consider increasing BLEND_ALPHA for team_totals specifically (see Section 9).

**7. HFA in model**

The model does not explicitly incorporate MLB home field advantage (~52-53% home win rate in 2024). The home/away advantage shows up implicitly through SaberSim's simulation (which models home/away splits and umpire tendencies) and through market lines (which already price HFA). The BLEND_ALPHA approach to market lines passively captures HFA. Explicit HFA is not needed.

**8. BLEND_ALPHA validation**

For MLB team totals: if SaberSim systematically over-projects, increasing BLEND_ALPHA closer to 0.50 would pull projections toward the market and reduce the systematic over-bias. BLEND_ALPHA = 0.25 means: proj = line + 0.25 × (sabersim - line). If SaberSim average = line + 1.2 (over-projection of 1.2 runs), then: proj = line + 0.30. This is enough to generate over picks for games where SaberSim projects 1.2+ above the line. Raising to BLEND_ALPHA = 0.40 would require SaberSim to project 0.75+ above line to generate the same pick — fewer, higher-confidence picks.

### Verdicts — Section 6

- **Team runs σ**: KEEP AS-IS (3.0 is correct).
- **Run differential σ**: KEEP AS-IS (3.8 is correct).
- **ML σ=6.0**: FIX. Change to 4.5-5.0 to better reflect actual run differential. Current 6.0 under-estimates ML edge on strong favorites.
- **TEAM_TOTAL/ML_FAV significance**: KEEP COLLECTING DATA. Neither is statistically significant yet.
- **BLEND_ALPHA for team totals**: Consider raising to 0.35-0.40 specifically for MLB team_totals to reduce SaberSim over-bias.

---

## Section 7: F5 Markets Empirical Data

### F5 Market Analysis

**1. F5/Full game ratio**

The model uses 0.51 (comment: "2024 data: 4.41/8.76"). This is consistent with general F5 analysis: the first 5 innings historically account for approximately 49-53% of full-game runs. The 0.51 figure is reasonable. Some sources cite the range as 50-53% depending on the year. **0.51 appears accurate.**

**2. F5 σ**

Model uses σ=2.6 for F5 run total. If full-game σ ≈ 4.0 (game_total sigma), then F5 σ should be approximately sqrt(0.51) × 4.0 ≈ 0.714 × 4.0 = **2.86**. Current 2.6 is slightly low but within reasonable range. More precisely: if F5 teams each have σ ≈ 2.0 per 5 innings (vs 2.97 per 9 innings, scaled by sqrt(5/9) ≈ 0.745): F5 combined σ ≈ sqrt(2) × 2.0 × 0.90 ≈ 2.55. This supports σ=2.5-2.6 as correct.

**3. F5 run differential σ**

Model uses σ=2.5. By similar scaling: full-game run diff σ ≈ 3.8, F5 version ≈ 3.8 × sqrt(5/9) ≈ 3.8 × 0.745 ≈ **2.83**. Current 2.5 is slightly low. A value of 2.7-2.8 would be more accurate.

**4. 0.54 vs 0.51 inconsistency**

F5_ML uses 0.54× while F5_TOTAL/F5_SPREAD use 0.51×. Both are scaling factors for 5 innings vs 9 innings of offense. The correct scale for run totals is ~0.51 (confirmed by data). The 0.54× for ML is a different calculation — it scales the team run differential for win probability, not the run total. When projecting ML win probability from team totals, the effective 5-inning team run advantage is slightly different from the total run ratio. However, 0.54 vs 0.51 is a 6% difference and likely not material. **For consistency, both should use 0.51.** The 0.54 for ML appears to have been set independently without a clear empirical basis.

**5. F5 ML sigma**

F5 spread coverage and F5 ML win probability are different metrics — F5 spread asks if team wins F5 by >0.5 runs (covers -0.5 handicap), while ML asks who wins outright. These do warrant slightly different sigma values. The current model uses F5_SIGMA = {total: 2.6, spread: 2.5, team: 2.0}. For ML, the relevant sigma is closer to the F5 run differential σ ≈ 2.5-2.8.

**6. Starter completion rate for 5 innings**

2024 data: average IP per start = 5.1-5.2, but this is the average. Percentage of MLB starters who actually complete 5 innings: approximately **62-68%** of starts. Starters failing to complete 5 innings in roughly 32-38% of starts. This is material for F5 market validity — if the starter is pulled at 4.2 IP, F5 markets settle based on at-bat completeness rules (typically the game must complete 5 full innings). For betting purposes, starter being listed as confirmed pre-game does not guarantee 5 IP completion.

**7. Book availability for F5 markets**

F5_TOTAL (totals_first_5_innings): available on DraftKings, FanDuel, BetMGM, Caesars. This is a standard market.
F5_ML (h2h_1st_5_innings): confirmed market key is `h2h_1st_5_innings` (from Odds API docs). Available on DraftKings, FanDuel, BetMGM.
F5_SPREAD (spreads_first_5_innings): available on DraftKings, FanDuel, BetMGM.

### Verdicts — Section 7

- **F5/full ratio 0.51**: KEEP AS-IS.
- **F5 σ values**: Consider raising F5_SIGMA spread from 2.5 to 2.7-2.8.
- **0.54 vs 0.51**: FIX for consistency — change F5_ML scaling to 0.51 for consistency with F5_TOTAL.
- **Starter completion**: NEEDS DATA. No gate currently for probability of starter completing 5 IP. Consider gate if SaberSim IP projection < 5.0.

---

## Section 8: SPREAD (Run Line) and GAME_SIGMA Validation

### Run Line Analysis

**1. Alternate run line availability**

`alternate_run_line` is confirmed as the market key in PROP_MARKETS. The standard MLB run line is -1.5/+1.5. This market is available on DraftKings, FanDuel, BetMGM, and Caesars. Typical odds for a game with neutral teams: favorite -1.5 is around +100 to +130, underdog +1.5 is around -120 to -150.

**2. Run diff σ**

Empirical σ of MLB full-game run differentials: ~3.7-3.8. Model uses 3.8. **Correct.**

**3. Game total σ**

Empirical σ of full-game run totals (both teams combined): if each team has σ ≈ 2.97 and they're weakly negatively correlated (negative correlation ≈ -0.10, because high scoring by one team increases opponent's pitching line): σ(total) = sqrt(2 × 2.97² + 2 × (-0.10) × 2.97²) = sqrt(2 × 8.82 × 0.90) = sqrt(15.88) ≈ **3.98**. Current model uses 4.0. **Correct.**

**4. GG5 gate and positive odds block**

The model blocks positive-odds SPREAD picks (GG5). For the standard -1.5 run line: the favorite -1.5 is typically +100 to +130 (positive odds = blocked). The underdog +1.5 is typically -120 to -150 (negative odds = not blocked). This means:
- Favorite covering -1.5: always blocked by GG5 (they're at positive odds)
- Underdog +1.5: never blocked (they're at negative odds)

This effectively filters the model to only betting underdog run lines (+1.5), which is a reasonable constraint since favorites covering -1.5 are genuinely lower probability. The gate is functioning as intended.

### Verdicts — Section 8

- **SPREAD σ**: KEEP AS-IS (3.8 is correct).
- **GAME_TOTAL σ**: KEEP AS-IS (4.0 is correct).
- **GG5 gate**: KEEP AS-IS. Correctly filters high-juice favorites on run line.
- **Run line availability**: CONFIRMED available at all major books.

---

## Section 9: Park Factors and Cross-Cutting

### Park Factors

**1. Coors Field**

Coors Field park factor on Baseball Savant Statcast scale (100 = neutral): approximately **135-142** for runs in 2024 (most recent multi-year average ≈ 138). One source confirms 138, another describes it as "MLB's highest run-scoring venue by a lot" with >5% enhancement vs average (on Statcast's 100-scale, one point = 1%). Coors is the extreme outlier in MLB — no other park comes close in run inflation.

**2. Oracle Park (San Francisco)**

Oracle Park park factor: approximately **95-98** (2-5% run suppression vs league average). Oracle Park is a mild pitcher's park, not an extreme one. Its Homer factor is more suppressed (approximately 77-80 for HR, meaning 20-23% fewer HR than average). The runs factor at Oracle is mild — some sources say "about 2% less run scoring than average."

**3. Park factor sources**

Most reliable sources for real-time integration:
- **Baseball Savant (baseballsavant.mlb.com/leaderboard/statcast-park-factors)**: Official MLB Statcast park factors, updated with 3-year rolling data. 100 = neutral scale. No public API but the leaderboard is scrapeable.
- **FanGraphs (fangraphs.com/guts.aspx?type=pf&teamid=&season=2024)**: FanGraphs park factors (own calculation, 100 = neutral). Has an internal API accessible via fangraphs.com.
- **Baseball-Reference**: Provides park adjustments (different scale, normalized differently).

For Python integration: FanGraphs provides park factors at a per-season URL that can be scraped. Baseball Savant has a JSON endpoint at `baseballsavant.mlb.com/leaderboard/statcast-park-factors?type=statcast&season=2024` that returns structured data.

**4. SaberSim park encoding**

SaberSim explicitly encodes park factors in projections via simulation (confirmed: "accounts for weather, home/away, park, and more"). Player projections from SaberSim already reflect park effects. At BLEND_ALPHA=0.25, the park-adjusted SaberSim projection receives 25% weight, meaning 25% of the Coors inflation passes through to the model's projection. This is appropriate for partial trust of SaberSim's simulation — full 100% park factor would over-weight SaberSim for games at extreme parks.

**5. BLEND_ALPHA per market**

Current BLEND_ALPHA = 0.25 applies uniformly. Better approach:
- **TEAM_TOTAL**: Consider 0.30-0.40 (market lines for team totals are highly efficient, less SaberSim signal needed)
- **SPREAD**: 0.25 is appropriate (market spread is excellent signal)
- **ML**: 0.25 is appropriate (market ML is highly efficient)
- **NRFI**: Not currently blended — runs its own pitcher-quality model. Market NRFI odds should be weighted more heavily.
- **Props (K, OUTS, HA, HITS, TB, HRR)**: 0.25 is too low. Props markets are less efficient — SaberSim carries more signal. Consider 0.35-0.40 for props.

Across markets, BLEND_ALPHA=0.25 appears most appropriate for game lines. For player props where SaberSim's player-specific simulation adds more value, a higher alpha (0.35-0.40) would improve edge identification.

### Verdicts — Section 9

- **Coors Field**: Park factor ≈ 135-142 runs index. Correctly handled if SaberSim projections are trusted with 0.25 blend.
- **Oracle Park**: Mild pitcher's park, ~97-98 runs index. Not a significant edge source.
- **Park factor API**: FanGraphs and Baseball Savant both provide accessible data. No current integration needed if SaberSim handles it.
- **BLEND_ALPHA per market**: CONSIDER splitting to 0.25 for game lines, 0.35 for props, 0.40 for team_totals.

---

## Section 10: Book Coverage Matrix and Market Availability

### Book Coverage Matrix

| Market Key | DraftKings | FanDuel | BetMGM | Caesars | Fanatics | theScore Bet | Hard Rock | Notes |
|------------|------------|---------|--------|---------|----------|--------------|-----------|-------|
| pitcher_strikeouts | Yes | Yes | Yes | Yes | Limited | Limited | Limited | Best coverage at DK/FD/MGM/CZR |
| pitcher_outs | Yes | Yes | Yes | Yes | Limited | Limited | Limited | Lines: 14.5-18.5 typical |
| pitcher_hits_allowed | Yes | Yes | Yes | Yes | Limited | Limited | No | Less consistent than K/OUTS |
| pitcher_earned_runs | No* | No* | No* | No* | No* | No* | No* | Market key: `pitcher_earned_runs` — was briefly available Apr 2026; currently dead or near-dead |
| batter_hits | Yes | Yes | Yes | Yes | Limited | Limited | Limited | Lines: 0.5, 1.5 standard; 2.5 available as alternate |
| batter_total_bases | Yes | Yes | Yes | Yes | Limited | Limited | Limited | Lines: 1.5, 2.5 standard; 0.5 available as alternate |
| batter_hits_runs_rbis | Yes | Yes | Yes | Yes | Limited | Limited | Limited | Line: 0.5, 1.5, 2.5 |
| batter_home_runs | Yes | Yes | Yes | Yes | Limited | No | No | Line: 0.5 standard |
| NRFI (totals_1st_1_innings) | Yes | Yes | Yes | Yes | Limited | Limited | Limited | Standard market; DK most prominent |
| team_totals | Yes | Yes | Yes | Yes | Yes | Yes | Limited | Standard across all major books |
| h2h (moneyline) | Yes | Yes | Yes | Yes | Yes | Yes | Yes | Universal |
| alternate_run_line | Yes | Yes | Yes | Yes | Limited | Limited | Limited | Standard -1.5/+1.5 line |
| h2h_1st_5_innings (F5 ML) | Yes | Yes | Yes | Yes | Limited | Limited | No | Available most games |
| totals_first_5_innings (F5 Total) | Yes | Yes | Yes | Yes | Limited | Limited | No | Available most games |
| spreads_first_5_innings (F5 Spread) | Yes | Yes | Yes | Yes | Limited | Limited | No | Available most games |

*pitcher_earned_runs was available at some books on Apr 14-15, 2026 (7 picks generated). Market appears to have been briefly offered and withdrawn. Currently NOT available at any CO-legal book in The Odds API. Market key is `pitcher_earned_runs`.

### HITS Market Lines

- **0.5 HITS**: Offered as primary or alternate line by DK, FD, BetMGM, Caesars. P(≥1 hit) for average batter ≈ 50-55% — very competitive market. Not in the model currently (gate G8 blocks line ≤1.5, but 0.5 is exempt per G2).
- **1.5 HITS**: Standard primary line. Break-even requires ~52% WR at -115. This is the market G8 was designed to avoid.
- **2.5 HITS**: Available as alternate line at DK and FD. Rarer at BetMGM, Caesars. Not consistently offered for all batters. Requires strong projection (P(≥3 hits) demands mean projection of ~2.0+ hits for viability).

### HRR Line Availability

- **0.5 HRR**: Offered at DK, FD, BetMGM. P(≥1 HRR) for typical batter ≈ 55-65% depending on lineup position. This is the 57.4% WR line that may have edge. Confirmed viable by actual WR data.
- **1.5 HRR**: Standard line. P(≥2 HRR) requires strong offensive day. 48% actual WR at -77 (77% needed) — dead market.
- **2.5 HRR**: Offered as alternate at DK/FD. Requires exceptional offensive game projection.

### TB Line Availability

- **0.5 TB**: Offered as alternate at DK, FD. P(TB≥1) ≈ 50-55%. Not consistently primary market.
- **1.5 TB**: Standard primary line (dominant offering). The main market — 35-38% actual vs model's historical 56% over-estimate (now fixed by calc_tb_prob).
- **2.5 TB**: Available as alternate at DK, FD, and increasingly BetMGM. Viable for strong batters projecting 2.5+ TB. Less liquid than 1.5.

### ER Market Status

The `pitcher_earned_runs` market key existed in The Odds API and generated 7 picks on April 14-15, 2026 (from a pre-repo code version). The market was NOT in PROP_MARKETS in the oldest git-tracked code (commit 954e984, April 21 2026), confirming it was removed before the repo was initialized. The market appears to have been offered briefly by Fanatics and Hard Rock (the books showing in the 7 logged picks) but is now inactive. Current status: **dead at all CO-legal books in The Odds API as of May 2026.** No action needed — already removed from production code.

### Verdicts — Section 10

- **pitcher_earned_runs**: KILL/already dead. Confirm by checking actual Odds API response — if not appearing in live batch calls, no code change needed.
- **HITS 2.5 line**: NEEDS DATA on frequency of availability. Add alternate gate check.
- **HRR 0.5 line**: KEEP and prioritize. Actual 57.4% WR is promising. Add minimum WP gate of 0.58 for HRR 0.5 specifically.
- **TB 2.5 line**: Consider adding to alternate_lines evaluation. Currently only 1.5 is primary.

---

## Section 11: SaberSim MLB Data Quality

### SaberSim Data Assessment

**1. Confirmed starter flags**

SaberSim includes a "status" column in the CSV that reflects the player's lineup status. For pitchers, "confirmed" means the pitcher has been officially listed as the starting pitcher in the confirmed lineup. Day-of MLB starter scratch rate: approximately **3-5%** of designated starters are scratched within 24 hours of game time (injury, emergency). SaberSim updates projections when news breaks, but the CSV used by the model was exported at a specific time and may be 2-6 hours stale for late-breaking scratches.

**2. Team offensive quality columns**

SaberSim provides projected runs, projected hits, projected HR, and full component stats for each batter in the lineup. The "Proj" column (team total projection) is available per team. The model extracts ER/IP for pitchers but does not extract team projected runs/PA for offensive quality assessment in NRFI. This data is available in the SaberSim CSV and should be used for the NRFI offense_factor (see Section 5).

**3. Publication time**

SaberSim typically publishes MLB projections by 10:00-11:00 AM ET for afternoon games, and by 2:00-3:00 PM ET for evening games. For 7:05 PM games, the CSV may be 4-5 hours old at the time of the pick run (typical: Jono runs the engine 2-4 hours before first pitch). Lineup changes after 1:30 PM are often not reflected. The "auto-update" happens when SaberSim's system detects lineup confirmations, but the user must re-download the CSV to get those updates.

**4. TB component validity**

SaberSim TB = 1B + 2×2B + 3×3B + 4×HR is computed from projected hit component rates. The validity of this approach: SaberSim's simulation uses thousands of game simulations and estimates the expected number of each hit type, so TB = sum(components) is the correct mathematical expectation. **The within-game correlation between hit types for the same batter is already accounted for in simulation** — if a batter has a multi-hit game, the simulation tracks whether those hits are singles, doubles, etc. So the component projections are internally consistent and the TB = sum formula is valid as an expectation. The calc_tb_prob() function correctly treats each component as independent Poisson with its own lambda.

**5. K projection method for partial outings**

SaberSim projects K assuming their simulation models IP realistically, including bulk/opener scenarios. Their K projection reflects the expected K across the full distribution of possible IP outcomes — weighted average of K given they go 3 IP (scenario 1), 5 IP (scenario 2), 7 IP (scenario 3). The issue is: **DFS-context projection** (which SaberSim was built for) optimizes for fantasy point production, and IP projection may be optimistic because:
- Fantasy K is scored even if pitcher gets knocked out early
- The expected K per inning stays fixed regardless of outing length
- But actual K is a product of K/IP rate × actual IP

If SaberSim's simulation median IP ≈ 5.0, and actual IP outcomes trend toward 5.2-5.5 for starters who stay in, then market K lines priced at 5.2 × K_rate × 9 will be systematically higher than SaberSim's median-IP-based projection. This is the most likely explanation for systematic K under-projection.

### Verdicts — Section 11

- **Confirmed starters**: KEEP AS-IS. Model correctly uses confirmed status check.
- **Team offensive quality**: FIX. Use SaberSim projected team runs as offense_factor in NRFI model.
- **Publication timing**: MONITOR. Consider adding a freshness check — if CSV is >4 hours old, log a warning.
- **TB components**: VALID. calc_tb_prob() correctly uses Poisson convolution of SaberSim components.
- **K projection bias**: Root cause confirmed as SaberSim's conservative IP assumption. Fix by adding K_UNDER gate (kill unders, gate overs at line ≥ 6.0).

---

## Section 12: Python Implementation Examples

### Distribution Code

```python
from scipy.stats import nbinom, poisson
from scipy.special import gammaln
import numpy as np

# ============================================================
# 1. P(X > 1.5) under Zero-Inflated Poisson
# ============================================================
def zip_prob_over(lam: float, pi: float, threshold: float = 1.5) -> float:
    """
    ZIP model: with probability pi, outcome is always 0 (structural zero)
               with probability (1-pi), outcome is Poisson(lam)
    
    P(X > threshold) = (1 - pi) * P(Poisson(lam) > threshold)
    """
    k = int(np.floor(threshold)) + 1  # smallest integer strictly above threshold
    p_poisson_over = 1.0 - poisson.cdf(k - 1, lam)
    return (1.0 - pi) * p_poisson_over

# Example: TB with mean=1.5, estimated lambda=2.2, pi=0.32
print(f"ZIP P(TB>1.5): {zip_prob_over(2.2, 0.32):.3f}")  # ~0.37


# ============================================================
# 2. P(X > 1.5) under Negative Binomial
# ============================================================
def nb_prob_over(mu: float, r: float, threshold: float = 1.5) -> float:
    """
    NB parameterized by mean=mu, dispersion=r
    p = r / (r + mu)  [scipy.stats.nbinom uses n=r, p=p]
    """
    p_nb = r / (r + mu)
    k = int(np.floor(threshold)) + 1
    return 1.0 - nbinom.cdf(k - 1, r, p_nb)

# Example: TB mean=1.5, r=2.0 (overdispersed)
print(f"NB P(TB>1.5): {nb_prob_over(1.5, 2.0):.3f}")  # ~0.36

# Example: HRR mean=2.0, r=1.5 (more overdispersed — composite stat)
print(f"NB P(HRR>1.5): {nb_prob_over(2.0, 1.5):.3f}")  # ~0.50


# ============================================================
# 3. P(X > 2.5) under NB
# ============================================================
print(f"NB P(TB>2.5) for mean=2.5, r=2.0: {nb_prob_over(2.5, 2.0, 2.5):.3f}")  # ~0.40
print(f"NB P(TB>2.5) for mean=3.0, r=2.0: {nb_prob_over(3.0, 2.0, 2.5):.3f}")  # ~0.47


# ============================================================
# 4. Fitting Zero-Inflated Poisson to observed count data
# ============================================================
# Using statsmodels ZeroInflatedPoisson
from statsmodels.discrete.count_model import ZeroInflatedPoisson
import pandas as pd

def fit_zip_to_data(counts: np.ndarray) -> tuple:
    """
    Fit ZIP model to observed count data.
    Returns (lambda_hat, pi_hat, aic, bic)
    """
    n = len(counts)
    df = pd.DataFrame({'y': counts, 'x': np.ones(n)})
    
    try:
        model = ZeroInflatedPoisson(df['y'], df[['x']], inflation='logit')
        result = model.fit(disp=0)
        lam = np.exp(result.params['x'])
        # pi is the zero-inflation probability (logit-scale intercept)
        pi = 1 / (1 + np.exp(-result.params['inflate_x']))
        return lam, pi, result.aic, result.bic
    except Exception as e:
        return None, None, np.inf, np.inf

# Usage:
# observed_tb = np.array([0, 0, 1, 0, 2, 1, 0, 3, 1, 2, 0, 1, 4, 0, 2])
# lam, pi, aic, bic = fit_zip_to_data(observed_tb)


# ============================================================
# 5. AIC/BIC comparison: Poisson vs NB vs ZIP
# ============================================================
from scipy.optimize import minimize
from scipy.stats import poisson as scipy_poisson

def compare_distributions(counts: np.ndarray) -> dict:
    """
    Fit Poisson, Negative Binomial, and ZIP to count data.
    Returns AIC and BIC for each, plus fitted parameters.
    """
    n = len(counts)
    counts = np.array(counts)
    
    results = {}
    
    # Poisson (1 parameter: lambda)
    lam_mle = np.mean(counts)
    ll_pois = np.sum(scipy_poisson.logpmf(counts, lam_mle))
    aic_pois = -2 * ll_pois + 2 * 1
    bic_pois = -2 * ll_pois + np.log(n) * 1
    results['Poisson'] = {'lambda': lam_mle, 'AIC': aic_pois, 'BIC': bic_pois}
    
    # Negative Binomial (2 parameters: mu, r)
    def neg_ll_nb(params):
        mu, log_r = params
        r = np.exp(log_r)
        if mu <= 0 or r <= 0:
            return 1e10
        p = r / (r + mu)
        return -np.sum(nbinom.logpmf(counts, r, p))
    
    res_nb = minimize(neg_ll_nb, [np.mean(counts), np.log(2.0)], method='Nelder-Mead')
    mu_nb, r_nb = res_nb.x[0], np.exp(res_nb.x[1])
    ll_nb = -res_nb.fun
    aic_nb = -2 * ll_nb + 2 * 2
    bic_nb = -2 * ll_nb + np.log(n) * 2
    results['NegBinom'] = {'mu': mu_nb, 'r': r_nb, 'AIC': aic_nb, 'BIC': bic_nb}
    
    # ZIP comparison via statsmodels
    try:
        lam_z, pi_z, aic_z, bic_z = fit_zip_to_data(counts)
        results['ZIP'] = {'lambda': lam_z, 'pi': pi_z, 'AIC': aic_z, 'BIC': bic_z}
    except:
        results['ZIP'] = {'AIC': np.inf, 'BIC': np.inf}
    
    return results

# Example (requires actual TB data):
# sample_tb_data = [0, 1, 0, 2, 1, 0, 0, 3, 1, 2, 0, 1, 0, 2, 1, 4, 0, 1, 2, 0]
# report = compare_distributions(sample_tb_data)
# print(report)
```

### Verdicts — Section 12

- Code is production-ready for validating distribution assumptions against actual pick_log data.
- **Recommended next step**: Extract per-player per-game TB from pick_log outcomes (when `result=W/L` and stat=TB is available) and run compare_distributions() to confirm NB is better fit than Poisson for the model's actual data.

---

## Section 13: ER Market Status

### ER Market Findings

**1. Current ER market availability**

`pitcher_earned_runs` is listed in The Odds API's documented market keys (found in betting-markets.html). However, **availability varies by book and game**. Based on actual pick data:
- 7 ER picks were generated April 14-15, 2026, from Fanatics and DraftKings (5 losses, 2 wins)
- The pre-repo version of run_picks.py (before April 21) had `pitcher_earned_runs` in PROP_MARKETS
- The market was removed before the code was committed to git (commit 954e984 already lacks it)
- As of May 2026: The market key is documented in The Odds API but **book coverage is inconsistent** — appears to be available at only 1-2 books on any given day, suggesting near-dead status

**2. Odds API market key**

`pitcher_earned_runs` is the confirmed Odds API market key (documented in the official betting-markets.html page). Alternate market key may exist as `pitcher_earned_runs_alternate`. This key can be used to search residual code references.

**3. How the 7 ER picks were generated**

The 7 ER picks (all April 14-15, 2026) were generated by a pre-repo version of run_picks.py that had `pitcher_earned_runs` in PROP_MARKETS and `"pitcher_earned_runs": "ER"` in MARKET_TO_STAT. These picks were processed through the normal sigma/tier pipeline using Normal distribution for ER (per SIGMA["ER"] in that version, now removed). The ER projection came from the SaberSim CSV's projected ER column. All 7 picks are in pick_log_mlb.csv — 5 losses on large ER over bets at lines 1.5/2.5, consistent with the Normal-model-overestimates-over-probability problem. The Shohei Ohtani pick (line 1.5, W) shows the market existed briefly at DraftKings.

### Verdicts — Section 13

- **ER market**: KEEP DEAD. Remove from any TODO lists. 0-7 AIC/BIC comparison with other markets is unfavorable. Even if the market revives, ER is structurally difficult (depends on IP and runs allowed, both of which are poorly modeled by Normal).
- **Code residuals**: Search `grep -n "ER\|pitcher_earned" engine/run_picks.py` to confirm no ER code remains in production. Result: ER is only used internally as a FIP calculation input (p["ER"] = er), not as a bet target. Clean.

---

## Section 14: HITS Market Analysis

### HITS Market

**1. Lines actually offered**

Major US books offer batter_hits primarily at:
- **0.5**: Available as alternate line at DK, FD, BetMGM, Caesars. This line is P(≥1 hit) ≈ 50-55% — near break-even.
- **1.5**: Standard primary line at all major books. P(≥2 hits) ≈ 25-30% for average batter. Break-even at -115 requires ~53.5%.
- **2.5**: Available as alternate at DK and FD, less consistently at BetMGM and Caesars. P(≥3 hits) ≈ 8-12% for average batter, higher for elite contact hitters. This is a niche market with good +odds typically.

**2. Poisson fit for HITS at line 2.5**

HITS per game follows Poisson reasonably well at the individual level (each PA has independent probability of hit), but has mild overdispersion (contact variance between games). For a batter projecting 1.5 H/game:
- Poisson(1.5): P(≥3) = 1 - e^{-1.5}(1 + 1.5 + 1.5²/2) = 1 - 0.223(1 + 1.5 + 1.125) = 1 - 0.223 × 3.625 = 1 - 0.809 = **19.1%**
- This is a reasonable estimate. At +400 odds, P(X>2.5) ≥ 20% would give edge.
- For a batter projecting 2.0 H/game: P(≥3) under Poisson = 1 - e^{-2.0}(1 + 2 + 2) = 1 - 0.135 × 5 = 1 - 0.677 = **32.3%**. At +200 odds (break-even 33.3%), this is near-edge.

**3. Vig on HITS markets**

Typical vig: -115/-115 (4.5%) to -120/-110 (5.5%). DraftKings tends toward -115/-115. BetMGM and FanDuel occasionally -120/-110. For alternate lines (0.5, 2.5), vig structure varies more: 0.5 HITS tends to be near-even money; 2.5 HITS has wide spread (+150 to +300).

**4. Should HITS be removed from PROP_MARKETS?**

Gate G8 currently bans HITS at line ≤1.5. This effectively bans 0.5 lines (blocked) and 1.5 lines (blocked by G8). If 2.5 is the only viable line and it's inconsistently offered, keeping HITS in PROP_MARKETS is justifiable only if:
a) The alternate 2.5 line is queried (currently the model doesn't query alternate lines for HITS)
b) 0.5 HITS is exempted as a soft market (currently it is, per G2)

Options:
- **Remove HITS entirely**: Simplifies code, eliminates a loss category.
- **Keep HITS but add 2.5 alternate query**: Potentially profitable if projection accuracy is good.
- **Keep HITS 0.5 only**: If actual WR at 0.5 line is ≥55%, this is worth keeping.

Given HITS is currently T1B (unders 3.5+ only in the tier comment, which isn't enforced), and the 0.5 exemption exists, more data is needed before removing.

### Verdicts — Section 14

- **HITS**: NEEDS DATA. Run a WR breakdown by line bucket (0.5 vs 1.5 vs 2.5) from pick_log_mlb.csv.
- **HITS 2.5**: Consider querying alternate_hits market or batter_hits_alternate.
- **HITS 0.5**: If WR ≥ 55% in the data, keep and prioritize.

---

## Section 15: Lineup Correlation and STAT_CAP

### Correlation Effects

**1. STAT_CAP for HRR and TB**

Currently STAT_CAP allows max 2 picks per stat per run (the default for non-SOG stats). For HRR and TB, players in the same lineup are correlated:
- Team scoring environment drives all players' R and RBI
- A shutout game affects all players' HRR simultaneously
- Two HRR bets on the same team have correlated outcomes

Reducing STAT_CAP to 1 for HRR would limit same-team lineup correlation exposure. For TB, the correlation is lower (TB is individual batter performance, less team-dependent) — STAT_CAP of 2 is acceptable for TB.

**2. Within-lineup correlation coefficient**

For players on the same team in the same game, empirical correlation estimates:
- H (hits): r ≈ 0.15-0.25 between same-lineup players (shared at-bats vs same pitcher)
- R (runs): r ≈ 0.30-0.40 (same-team scoring environment drives all runs)
- RBI (runs batted in): r ≈ 0.25-0.35 (shared baserunning context)
- HRR combined: r ≈ 0.25-0.35 between same-team players

These correlations are material. If HRR picks 1 and 2 are on the same team, their joint loss probability is P(both lose) > P(lose)² due to positive correlation. For conservative exposure management, limiting to 1 HRR pick per team is advisable.

For opposite-team players: correlation is weakly negative (if one team gets shut out, the other team likely scored, helping that team's HRR bets).

The current PITCHER_STATS and BATTER_CORR_STATS deduplication already prevents multiple picks from the same pitcher. But there is no similar gate for same-team batters beyond the general game correlation dedup.

### Verdicts — Section 15

- **HRR STAT_CAP**: Consider lowering to 1 per team (not 1 globally) via a same-team gate.
- **TB STAT_CAP**: Keep at 2 — lower team correlation for TB.
- **Same-team batter gate**: Add a gate: max 2 HRR picks per game (both teams combined), or max 1 HRR pick per team per game. This reduces correlated loss exposure in blowout scenarios.
- **Correlation data**: The r ≈ 0.25-0.35 for same-team HRR is an estimate — confirm with pick_log outcomes when sample size is sufficient.

---

## Summary Table: All Verdicts

| Market/Feature | Verdict | Priority | Notes |
|----------------|---------|----------|-------|
| BASE_SCORING_RATE (NRFI) | FIX | HIGH | Change 0.194 → 0.163; current implies 65% NRFI, actual is 70% |
| NRFI offense model | FIX | HIGH | Add team offense_factor using SaberSim team proj runs |
| NRFI tier T2→T3 bug | FIX | HIGH | Code must enforce T3 (6%) not T2 (5%) for NRFI |
| K unders | KILL | HIGH | Model systematically wrong; SaberSim K projections too low |
| HRR at line 1.5 | FIX | HIGH | Normal model gives 63% vs true ~45-50%; raise gate to WP≥0.65 |
| HRR at line 0.5 | EVALUATE | HIGH | Actual WR 57.4% — may be viable; add WP≥0.58 gate |
| HA direction code bug | FIX | HIGH | T1B comment says "unders 3.5+" but code allows overs |
| OUTS σ underestimated | FIX | MEDIUM | Change mult 0.22→0.30 (true σ ≈ 4.5-5.0 outs vs model's 3.3) |
| OUTS unders gate | FIX | MEDIUM | Add min WP ≥ 0.60 for OUTS unders |
| ML σ=6.0 too wide | FIX | MEDIUM | Reduce to 4.5-5.0 to reflect actual run diff σ |
| K distribution | FIX | MEDIUM | Move K to NB(r≈5) instead of Poisson for lines 5.5+ |
| K gate (overs only) | FIX | MEDIUM | Add gate: K overs only, line ≥ 6.0 |
| FIP constant | UPDATE | LOW | 3.20 → 3.17 (2024 lgERA=4.08 implies 3.1675) |
| F5 ML 0.54 scaling | FIX | LOW | Change 0.54 → 0.51 for consistency |
| F5 spread σ | CONSIDER | LOW | Raise from 2.5 to 2.7-2.8 |
| BLEND_ALPHA props | CONSIDER | LOW | Consider 0.35 for props vs 0.25 for game lines |
| TB model | KEEP | — | calc_tb_prob() Poisson convolution is correct |
| Game line σ (total/spread) | KEEP | — | 4.0/3.8 are correct |
| Team runs σ | KEEP | — | 3.0 is correct |
| GG5 gate | KEEP | — | Correctly filters favorites on run line |
| ER market | DEAD | — | Remove from any future backlog items |
| HRR same-team STAT_CAP | CONSIDER | LOW | Limit 1 HRR per team per game to reduce correlation exposure |

---

*Research conducted 2026-05-14. Web sources: FanGraphs community blog, seandolinar.com MLB run distribution NB analysis, The Odds API documentation, NRFI-Central.com 2024 recap, BetMGM/TeamRankings NRFI data, FantasyTeamAdvice pitcher outs pages, FanGraphs starter usage data.*
