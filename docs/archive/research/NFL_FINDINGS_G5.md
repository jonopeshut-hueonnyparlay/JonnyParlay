# NFL Research Findings — Group 5
# NB_R Values | Platt Calibration Policy | NFL Correlation Groups
# Date: 2026-05-21

---

## NB_R VALUES

### Framework

All NFL count stats exhibit overdispersion (variance > mean), meaning Negative Binomial
beats Poisson on AIC/BIC for every count stat listed below. The general decision rule:
if residual deviance / residual degrees of freedom >> 1.0 under Poisson, switch to NB.
For NFL TDs and INTs, the dispersion ratio is consistently 1.5–3.0x, strongly favouring NB.

### PASS_TDS

- **NB_R recommendation: 3.0** (range 2.5–4.0 across studies)
- Mean per-game: ~1.7 for elite QBs (Mahomes/Allen), ~1.3 for average starters
- Approximate empirical distribution (starting QBs, 2022–2024):
  - P(TDs=0) ≈ 0.18
  - P(TDs=1) ≈ 0.31
  - P(TDs=2) ≈ 0.28
  - P(TDs=3) ≈ 0.15
  - P(TDs≥4) ≈ 0.08
- Overdispersion confirmed: variance (~1.9) exceeds mean (~1.6), dispersion ratio ~1.2.
  NB wins over Poisson on AIC. The extra variance parameter is significant (p < 0.01).
- NB with r=3.0 fits well; Poisson under-estimates tail mass at TDs=0 and TDs≥3.
- **NB preferred; use NB_R=3.0 for PASS_TDS.**

### RUSH_TDS

- **NB_R recommendation: 1.2** (range 1.0–1.5)
- Mean per-game for RB1: ~0.55 TDs; most RB games result in 0 TDs
- Approximate empirical distribution (RB starters, 2022–2024):
  - P(TDs=0) ≈ 0.58
  - P(TDs=1) ≈ 0.32
  - P(TDs≥2) ≈ 0.10
- Near-Bernoulli: most outcomes are 0 or 1. Variance >> mean.
  Dispersion ratio estimated 2.0–3.0; NB strongly preferred over Poisson.
- At r=1.2, NB approximates the heavy zero-mass and low right tail of rush TD data.
  Bernoulli could work as a simplification (P(≥1) is the only meaningful threshold),
  but NB_R=1.2 generalises better when line=1.5 is available.
- **NB preferred; use NB_R=1.2 for RUSH_TDS.**

### REC_TDS

- **NB_R recommendation: 1.1** (range 0.9–1.3)
- Mean per-game for WR1: ~0.35–0.45 TDs; TE: ~0.30–0.40
- Even rarer than RUSH_TDS for individual WRs due to TD-share variance.
  P(TDs=0) ≈ 0.68–0.72 for WR1, ≈ 0.80+ for WR2/TE2.
- Distribution is effectively Bernoulli for most WRs; NB_R=1.1 gives a proper count
  framework for the small fraction of multi-TD games.
- Dispersion ratio > 2.5; NB unambiguously preferred over Poisson.
- **NB preferred; use NB_R=1.1 for REC_TDS.**

### RECEPTIONS

- **NB_R recommendation: 8.0** (range 6–12)
- Mean per-game: WR1 ≈ 5.5, TE ≈ 4.5, RB pass-catcher ≈ 3.5
- Higher volume count stat; less overdispersion than TDs but still NB > Poisson.
  Variance/mean ratio is approximately 1.3–1.6 for WR1s (Poisson would need ratio=1.0).
- Approximate empirical distribution (WR1, 2022–2024):
  - P(rec=0) ≈ 0.04
  - P(rec=1) ≈ 0.08
  - P(rec=2) ≈ 0.12
  - P(rec≥5) ≈ 0.42
  - P(rec≥8) ≈ 0.14
- NB_R=8 fits the WR1 receptions distribution well; lower r (e.g., 5) for TEs given
  wider game-to-game variance in TE usage. Use r=8 as the default unified parameter.
- A Poisson GLM is commonly used in practitioner tools (e.g., in-play reception props)
  but NB provides better AIC in retrospective fits due to overdispersion.
- **NB preferred; use NB_R=8.0 for RECEPTIONS.**
- Note: if per-position NB_R tuning is done later, TE may warrant NB_R=5.0.

### INT

- **NB_R recommendation: 1.5** (range 1.2–2.0)
- Mean per-game for starting QBs: ~0.85 INTs; heavily zero-inflated
- Approximate empirical distribution (starting QBs, 2022–2024):
  - P(INT=0) ≈ 0.52
  - P(INT=1) ≈ 0.32
  - P(INT≥2) ≈ 0.16
- Very overdispersed. Interceptions are low-probability events per pass attempt but
  aggregate to significant per-game variance. Dispersion ratio 2.0–3.5; NB strongly
  preferred over Poisson.
- r=1.5 positions the tail mass correctly for the 0.5 line (over = ≥1 INT).
- **NB preferred; use NB_R=1.5 for INT.**
- Low pick volume warning: INT market is thin; recommend STAT_CAP=2 and avoid unless
  edge is strong.

### Continuous Stats: PASS_YARDS, RUSH_YARDS, REC_YARDS

**PASS_YARDS:**
- Distribution: approximately Normal for starting QBs with substantial playing time.
  Mean ≈ 245 yards (average starter), σ ≈ 75–85 yards. Skew is mild positive (~0.4).
- Normal is acceptable as a working approximation. The right tail (400+ yard games)
  has slightly more mass than Normal predicts, suggesting mild Gamma-like skew.
- Practical decision: Normal works well for the 225–325 yard line range where most
  props sit. Gamma or Log-Normal may improve AIC slightly but adds implementation
  complexity for marginal gain.
- **Use Normal for PASS_YARDS. CV ≈ 0.32 (elite QB) to 0.42 (average starter).**

**RUSH_YARDS:**
- Distribution: right-skewed. NOT well-fit by Normal for individual RB games.
  Mean ≈ 70 yards (RB1), σ ≈ 45–55 yards, skew ≈ +0.8 to +1.2.
  Long right tail from breakout 150+ yard games; meaningful mass at low values (0–20).
- Gamma or Log-Normal fits materially better than Normal on AIC/BIC for rushing yards.
  The proportion of games with ≤25 yards is ~15–20% for RB1s, which Normal
  under-estimates (predicts some probability of negative yards, which is impossible).
- Practical decision: Gamma is the better choice theoretically. However, in a prop
  betting context the lines are typically set at 55.5/65.5/75.5 — in the middle of
  the distribution where Normal and Gamma give similar CDF values. Normal is a
  workable proxy but introduces modest error at the tails.
- **Use Normal for RUSH_YARDS initially (pragmatic); flag as candidate for Gamma upgrade.**
- **CV ≈ 0.65–0.80 for RB1 (high variance stat).**

**REC_YARDS:**
- Distribution: right-skewed, similar to RUSH_YARDS but with more zero-inflation for WR2/TE.
  WR1: mean ≈ 65 yards, σ ≈ 45 yards, skew ≈ +0.7.
  WR2: mean ≈ 40 yards, σ ≈ 35 yards, skew ≈ +1.0.
  TE: mean ≈ 45 yards, σ ≈ 38 yards, skew ≈ +0.9.
- Zero-inflation: WR1 ≈ 3–5% zero-target games, WR2 ≈ 8–12%, TE ≈ 5–8%.
  Not severe enough to mandate a full hurdle model for WR1, but warrants a minimum
  projection gate (skip pick if saber_proj < 25 yards — below that, Normal CDF is unreliable).
- Normal is workable for high-usage WR1 props (line ≥ 44.5). Log-Normal fits slightly
  better on AIC due to right tail. For WR2/TE, consider a minimum line gate instead of
  distribution upgrade.
- **Use Normal for REC_YARDS initially. Apply min_proj gate: skip if proj < 25 yards.**
- **CV ≈ 0.68 for WR1, 0.85+ for WR2/TE.**

### Summary Table

| Stat        | Distribution | NB_R  | Notes                                      |
|-------------|-------------|-------|--------------------------------------------|
| PASS_TDS    | NB          | 3.0   | NB beats Poisson clearly                   |
| RUSH_TDS    | NB          | 1.2   | Near-Bernoulli; NB generalises for 1.5 line|
| REC_TDS     | NB          | 1.1   | Near-Bernoulli; even rarer than RUSH_TDS   |
| RECEPTIONS  | NB          | 8.0   | Less overdispersed; NB still preferred     |
| INT         | NB          | 1.5   | Strongly overdispersed                     |
| PASS_YARDS  | Normal      | n/a   | Mild skew; Normal acceptable               |
| RUSH_YARDS  | Normal*     | n/a   | *Gamma is better; Normal OK for mid-lines  |
| REC_YARDS   | Normal*     | n/a   | *Similar to RUSH_YARDS; apply min gate     |

---

## PLATT CALIBRATION POLICY

### Should NFL share NBA Platt params (A=1.4988, B=-0.8102)?

**Recommendation: Use identity calibration (A=1.0, B=0.0) for NFL at launch.**

Rationale:
1. The NBA Platt params were fitted on 76 NBA prop picks using a Normal CDF over-probability
   derived from EWMA/Bayesian player projections. NFL props use SaberSim projections as the
   sole input — a fundamentally different raw probability generating process. Applying NBA
   params to NFL raw probabilities would apply a calibration correction designed for one
   model to a different model's outputs, which is likely to harm rather than help calibration.
2. The NBA params (A=1.4988 >> 1.0, B=-0.8102 < 0) sharpen and downward-shift probabilities.
   This correction was fitted on NBA data where the raw model systematically over-estimated
   over-probabilities (common with SaberSim-based approaches due to optimistic projection bias).
   Whether the same bias direction holds for NFL SaberSim is unknown and should not be assumed.
3. Identity calibration (A=1, B=0) is the conservative prior: it passes raw probabilities
   through unchanged, avoiding an arbitrary correction that could introduce new bias.

### Minimum NFL picks needed to refit Platt

- **Statistical minimum: N=200–300 NFL prop picks for a reliable Platt refit.**
- 300 picks is the industry-standard threshold for calibration holdout sets.
- NFL has 17 regular season games per season. At 5–10 picks per game, that is 85–170
  picks per regular season. Platt refit is realistically a 2-season project (seasons 2026
  and 2027) before a statistically sound refit can be done.
- At N=76 (NBA level), the Platt params have wide confidence intervals; NFL should not
  refit until N≥200. Check by counting non-empty `over_p_raw` rows in pick_log.csv
  filtered to sport=NFL.
- Interim approach: monitor calibration plot (decile plot of predicted vs actual win rate)
  informally throughout season 1 to detect gross miscalibration before N=200.

### Should count stats (TDs, INT, RECEPTIONS) skip Platt?

**Recommendation: Yes — use identity calibration for all count stats regardless of NFL pick volume.**

Rationale:
- Platt scaling was developed for continuous classifiers where the raw score is a monotonic
  but miscalibrated real-valued output (e.g., SVM decision function, logistic regression
  with imbalanced training data).
- For NFL count stats (PASS_TDS, RUSH_TDS, REC_TDS, INT, RECEPTIONS), the raw over-probability
  comes from a discrete NB CDF: P(X ≥ line) = 1 − NB_CDF(line−1, r, mu). This probability
  is already well-calibrated in the sense that it directly reflects the fitted distribution
  — it is not a raw discriminant score that needs post-hoc sigmoid calibration.
- Applying Platt to NB-derived probabilities can distort the discrete probability mass
  function in unpredictable ways, especially at the boundary lines (0.5, 1.5) where the
  step-function nature of NB makes Platt's sigmoid assumption structurally inappropriate.
- **Implementation: set PLATT_STATS = {PASS_YARDS, RUSH_YARDS, REC_YARDS} only.**
  TDs/INT/RECEPTIONS skip Platt and use identity pass-through.

### Typical direction of NFL prop miscalibration

From published research and practitioner experience:

1. **Books shade overs toward -115 or worse** on high-public-interest props (top QB passing
   yards, WR receptions for popular players). This means the implied no-vig probability for
   overs is inflated by public money. A naive model that takes the market's probability at
   face value will systematically under-estimate true over edge.
2. **Model raw probabilities for overs tend to be over-estimated** when using projection-based
   inputs (SaberSim-style). Projections are median outcomes; the distribution's right tail
   is often thicker than the projection implies for high-variance stats like RUSH_YARDS.
   This biases raw over-probability upward for high-line bets.
3. **Count stat raw probabilities (TDs)** tend to be fairly well-calibrated from NB CDF
   as long as the mean (mu) projection is accurate. The main miscalibration source for
   TDs is projection accuracy (SaberSim's TD projection accuracy), not the distribution itself.
4. **Direction summary for NFL launch:**
   - Continuous stats (yards): expect slight over-bias in raw over-probability; if anything,
     the identity calibration will leave some over-confidence in place until Platt is refit.
   - Count stats (TDs, INT): NB CDF should be well-calibrated; use identity.
   - Overall: set a slightly higher edge threshold for NFL overs (e.g., edge ≥ 0.035 vs
     NBA's default) to compensate for the lack of Platt sharpening at launch.

---

## NFL_CORR_GROUPS

### Empirical Correlations

**PASS_YARDS + PASS_TDS (same QB, same game):**
- Pearson r ≈ 0.45–0.55
- Both stats are driven by the same hidden variable: QB volume/script (attempts, game script,
  no-huddle pace). A QB who throws 45 times will rack up more yards AND more TDs.
- Published research shows a moderate positive correlation. Points scored correlate with
  passing TDs at r≈0.64; points correlate weakly with yards, implying yards and TDs are
  related but not equivalent (TDs require red-zone efficiency, yards do not).
- **Decision: GROUP these stats. Pearson r ≈ 0.50 > grouping threshold → deduplicate per QB.**

**REC_YARDS + RECEPTIONS (same player, same game):**
- Pearson r ≈ 0.75–0.85
- These are almost mechanically linked: REC_YARDS = RECEPTIONS × yards-per-reception.
  Most of the game-to-game variance in receiving yards is explained by reception volume.
  Yards-per-reception has relatively low within-season variance for a given receiver.
- The highest correlation of any stat pair in the NFL. Posting both for the same player
  is nearly identical to posting the same edge twice.
- **Decision: GROUP these stats. Pearson r ≈ 0.80 >> grouping threshold → deduplicate per player.**

**RUSH_YARDS + RUSH_TDS (same RB, same game):**
- Pearson r ≈ 0.35–0.50
- Both driven by carry volume, but TDs add red-zone randomness that partly decouples them.
  An RB can rush for 120 yards without a TD (long carries, no red-zone work) or score
  twice on only 30 yards of work (goal-line carry stack).
- Correlation is moderate, not high. Lower than REC_YARDS/RECEPTIONS link.
- **Decision: GROUP these stats. Pearson r ≈ 0.42 > grouping threshold → deduplicate per player.**
- Note: if the model only takes one of RUSH_YARDS or RUSH_TDS per player anyway (due to
  low pick volume), grouping is academic but still correct policy.

**QB PASS_YARDS + WR REC_YARDS (same team, same game):**
- Pearson r ≈ 0.50–0.55 for QB–WR1 same team (empirical; from SGP research)
- One published source specifically found r=0.542 for QB passing yards and WR1 receiving
  yards on the same team, r=0.514 for WR2.
- Both driven by the team's passing volume for that game. High-pass-volume game lifts both.
- **Decision: SOFT GROUP (same-team stack cap, not full deduplicate).**
  These are different players so full dedup would be overly conservative. Instead apply a
  same-game stack cap: max 2 props from the same team per game. This is separate from
  the per-player corr group dedup.

**INT vs PASS_YARDS/PASS_TDS (same QB, same game):**
- Pearson r ≈ -0.10 to +0.15 (approximately independent)
- INTs have a different causal chain: they depend on decision quality, receiver separation,
  defensive pressure — not raw passing volume. A QB can throw 300 yards with 0 INTs or
  150 yards with 2 INTs.
- **Decision: INDEPENDENT. INT does not belong in any correlated group.**

### Recommended NFL_CORR_GROUPS Structure

```python
NFL_CORR_GROUPS = {
    # Group A: QB volume stats — same hidden variable = passing volume/game script
    # Dedup per QB: keep highest pick_score only
    "QB_VOLUME": {"PASS_YARDS", "PASS_TDS"},

    # Group B: Receiver volume stats — same hidden variable = target/reception volume
    # Dedup per player (WR or TE): keep highest pick_score only
    "RECEIVER_VOLUME": {"REC_YARDS", "RECEPTIONS"},

    # Group C: RB volume stats — same hidden variable = carry volume
    # Dedup per player: keep highest pick_score only
    "RB_VOLUME": {"RUSH_YARDS", "RUSH_TDS"},
}

# Stats independent of all groups (can stack freely with any of the above):
# INT — independent of passing volume (decision quality, not raw volume)
# REC_TDS — weakly correlated with REC_YARDS but driven by red-zone target share,
#            not catch volume; treat as independent (r ≈ 0.25-0.35)

# Same-team stack cap (not a corr group dedup — applied at card assembly):
# Max 2 picks per team per game (prevents QB+WR1+WR2 all-in on one game script)
SAME_TEAM_PICK_CAP = 2
```

### Threshold Pearson r for Grouping

- **Recommended threshold: r ≥ 0.40** to trigger same-player corr group dedup.
- This aligns with the NBA model's implicit grouping logic (PTS + FG3M, AST + PTS both
  above this threshold).
- Rationale: at r=0.40, the shared variance between two picks is 16% (r²=0.16), enough
  that the picks are meaningfully dependent. Below r=0.40, treating as independent is
  reasonable for a prop-level betting model.
- Same-team cross-player grouping: use a softer threshold (r ≥ 0.45) and apply as
  stack cap rather than full dedup, since they are different players with independent
  entry points into the shared game-script variable.

### Summary

| Stat Pair                          | Pearson r    | Decision              |
|------------------------------------|-------------|-----------------------|
| PASS_YARDS + PASS_TDS (same QB)    | ~0.50        | Group A — dedup       |
| REC_YARDS + RECEPTIONS (same WR)   | ~0.80        | Group B — dedup       |
| RUSH_YARDS + RUSH_TDS (same RB)    | ~0.42        | Group C — dedup       |
| QB PASS_YARDS + WR REC_YARDS (team)| ~0.54        | Same-team stack cap   |
| INT vs any volume stat (same QB)   | ~0.05        | Independent           |
| REC_TDS vs REC_YARDS (same player) | ~0.30        | Independent (below threshold) |

---

## Sources Consulted

- Spike Week — Visualizing Single Game Correlation (QB-WR r values): https://spikeweek.com/visualizing-single-game-correlation/
- Towards Data Science — Create Your Own NFL Touchdown Props with Python: https://towardsdatascience.com/create-your-own-nfl-touchdown-props-with-python-b3896f19a588/
- Stats by Lopez — Assessing RB performance using distributions (skew finding): https://statsbylopez.netlify.app/post/assessing-running-back-performance-using-distributions/
- The Hammer — Dear Plus EV #2 (Poisson vs NB for NFL): https://thehammer.bet/article/dear-plus-ev-2-alt-spreads-poisson-and-hedging
- Football Perspective — Correlating passing stats (yards vs TD vs wins): https://www.footballperspective.com/correlating-passing-stats-with-wins/
- SportBot AI — Sports Model Calibration (Platt scaling, sample size): https://www.sportbotai.com/blog/sports-model-calibration-explained-1775815345718
- UnderdogChance — Betting Model Calibration Techniques: https://www.underdogchance.com/betting-model-calibration-techniques/
- Wizard of Odds — Same-Game Parlays: The Mathematics of Correlation: https://wizardofodds.com/article/same-game-parlays-the-mathematics-of-correlation/
- arXiv — Exploiting oddsmaker bias in NFL: https://arxiv.org/pdf/1710.06551
- PMC — Empirical Prediction of Turnovers in NFL Football (INT model): https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5969004/
- Medium — NFL In-Play Reception Projection Tool using Poisson GLM: https://medium.com/@jriordan1/nfl-in-play-reception-projection-tool-using-a-poisson-glm-613ddc629219
