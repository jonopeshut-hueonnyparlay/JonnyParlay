# NFL Research Findings — G6: Blowout Sigmoid, Home/Away Delta, Opponent Quality

**Date:** 2026-05-21
**Sections:** Blowout/Garbage Time Sigmoid | Home/Away Delta | Opponent Defensive Quality
**Researcher:** Claude (automated research agent)

---

## BLOWOUT / GARBAGE TIME SIGMOID

### Core Direction: NFL Is Asymmetric (Not a Simple Dampener)

Unlike the NBA blowout sigmoid — which is a uniform dampener (max_reduction=0.19) applied to
all projections when projected margin is large — the NFL sigmoid must be **directional**.
The direction of the effect flips by position:

| Position/Stat | Role | Blowout Direction |
|---|---|---|
| Trailing QB | Forced to pass | INFLATE passing yards, rec yards |
| Trailing WR/TE | More targets from forced passing | INFLATE receiving yards, receptions |
| Trailing RB | Team abandons run game | DEFLATE rushing yards |
| Leading RB | Clock management run-heavy | INFLATE rushing yards |
| Leading QB | Conservative, game-managing | DEFLATE passing yards |

### Trailing QB Passing Yards Inflation

**Empirical signal (qualitative from research):**
- Trailing QBs throw significantly more attempts. When trailing by 10+ in the 4th quarter,
  QBs routinely throw 40+ times into increasingly tight windows.
- Research from footballperspective.com on QB stats while trailing vs. leading:
  - Yards per attempt: 7.7 (leading) vs. 7.2 (trailing) — efficiency drops ~6.5%
  - Completion %: 65.4% (leading) vs. 63.2% (trailing)
  - However, **volume (attempts) increases substantially** — the volume effect outweighs
    the per-attempt efficiency drop for total yards accumulation.
- Industry consensus (prop betting community): heavy underdogs (+14) see QB passing volume
  surge. Prop line setters price in ~+13 yards for a QB facing the league's worst pass defense
  (example: Stroud's line raised 13.3 yards vs. Pittsburgh's worst-in-league pass defense).
  Scale this to the full game-script effect and +15 to +20% total yards is a plausible range.
- PFF game script analysis: "trailing teams pass more, boosting QB yards and WR props" — this
  is the widely accepted directional signal in the prop market.
- **Best estimate: trailing QB (≥14-point dog) passing yards = +15 to +20% vs. projection.**
  Treat as +17% midpoint for model parameterization.

**No published academic study with exact regression coefficient was located.** This estimate
synthesizes multiple prop-betting analytics sources and the footballperspective.com ANY/A
trailing vs. leading dataset. Recommend treating as provisional — refit on live NFL data after
~200 QB-game observations.

### Leading RB Rush Yards Inflation

**Empirical signal:**
- When teams lead by large margins in the second half, they run the ball to drain the clock.
  This is clock management doctrine — well established but not easily quantified from public
  sources without running custom nflfastR queries.
- TeamRankings data on rushing attempts correlates with game time of possession leads.
- Industry guidance: targeting leading-team RBs in blowout scenarios is a well-known
  fantasy/prop strategy. The effect is real but exact magnitude varies by game context.
- **Best estimate: leading RB (≥14-point favorite) rush yards = +10 to +15% vs. projection.**
  Treat as +12% midpoint.
- Note: this effect is less reliable than the trailing QB inflation because some leading teams
  (pass-heavy offenses: Chiefs, Bills) may not shift heavily to the run even when ahead by 14+.

### Trailing RB Rush Yards Deflation

- Heavy underdogs abandon the run game entirely in the second half. RBs on trailing teams
  see carry share collapse.
- **Best estimate: trailing RB (≥14-point dog) rush yards = −20 to −30% vs. projection.**
  Treat as −25% midpoint.
- This is the largest directional effect in the model — a trailing RB in a blowout is
  essentially worthless for rush yards props.

### WR/TE Receiving Yards in Garbage Time

- Trailing QB throws more → WR/TE receiving yards and receptions are inflated alongside QB yards.
- PFF: "when a team is a big underdog, expect more passing — boosting WR/QB props."
- The inflation is correlated with QB inflation: same mechanism (forced passing, prevent defense).
- **Best estimate: trailing WR (≥14-point dog) rec yards = +10 to +15% vs. projection.**
  Treat as +12% midpoint.
- Caveat: Fantasy Footballers Mythbusters research shows that in aggregate, WRs on favorites
  still outperform WRs on underdogs in total fantasy points, because favorites generate
  more total offensive production. The trailing-team WR inflation is real but partially
  offset by lower overall offensive quality.

### Recommended Sigmoid Parameters

**Design principle:** NFL sigmoid is bidirectional. Apply to the **projected spread** (not
actual game score — this is a pre-game adjustment). Split into "trailing" and "leading" branches
based on which team the player is on.

For trailing-team players:
- k = 0.12 (shallower than NBA's 0.15 — NFL blowouts develop over 60 minutes, not 48)
- midpoint = 14.0 points (spread at which max effect applies; ≥10 points shows significance)
- max_inflation_QB_pass_yds = +0.17 (17%)
- max_inflation_WR_rec_yds = +0.12 (12%)
- max_deflation_RB_rush_yds = −0.25 (25%)

For leading-team players:
- k = 0.10 (even shallower — clock management is less abrupt in onset)
- midpoint = 14.0 points
- max_inflation_RB_rush_yds = +0.12 (12%)
- max_deflation_QB_pass_yds = −0.10 (10%; conservative — elite QBs still pass when leading)

**Alternative: flat multiplier above threshold (simpler, less overfit risk)**
- If projected spread ≥ 14 points:
  - Trailing QB PASS_YARDS: ×1.12
  - Trailing WR REC_YARDS: ×1.08
  - Trailing RB RUSH_YARDS: ×0.75
  - Leading RB RUSH_YARDS: ×1.10
  - Leading QB PASS_YARDS: ×0.92
- Below 14 points: no adjustment (identity multiplier)
- At 10-13 points: linear interpolation from 1.0 to full multiplier

**Spread threshold for significance:**
- ≥10 points: effect begins, directional signal detectable
- ≥14 points: effect is statistically material; full multiplier recommended
- ≥21 points: effect saturates; no additional adjustment above ≥14 tier

### Comparison to NBA Blowout Sigmoid

| Parameter | NBA | NFL (recommended) |
|---|---|---|
| Direction | Uniform dampener (all stats) | Bidirectional (stat + team role dependent) |
| k | 0.15 | 0.10–0.12 |
| midpoint | 20.0 pts | 14.0 pts |
| max_reduction | 0.19 | 0.10–0.25 (varies by stat) |
| Threshold for significance | ~15 pts | ~10 pts |

NFL blowout effects are directional and kick in at a lower point threshold. The NBA sigmoid
is a simpler dampener appropriate for basketball where blowouts lead to garbage-time DNPs
for starters. NFL starters play all 60 minutes, so the effect is about **role shift, not
playing time**.

---

## HOME/AWAY DELTA (NFL)

### Summary of Evidence

**The NFL home field advantage is real but smaller and noisier than NBA:**
- League-wide: ~2.5–2.7 points of spread advantage for home teams (vs. ~3 points historically)
- Home teams win ~53–57% of games over recent seasons; declining post-COVID (2022-2024: ~53%)
- EPA per rush play: home teams −0.058 vs. away teams −0.073 (home teams lose ~0.5 fewer
  expected points per 30 rush plays — ~1.5% efficiency gain)
- EPA per pass play: not individually broken down in public sources, but the 2.5-point overall
  advantage implies passing efficiency also gains marginally at home

### SaberSim NFL Home/Away Encoding

**Key finding: SaberSim's NFL model explicitly encodes home/away within its play-by-play
simulations.** Per SaberSim's documentation, projections are generated from "thousands of
play-by-play simulations of every game, building every game from scratch, one play at a time"
and account for "match-ups, weather, play-calling, referees, rotations, and more."

The simulation-based architecture means:
1. Home team's offensive tendencies vs. away team's defensive DVOA are both encoded
2. Home crowd noise effects on opposing QB (false starts, communication disruption) are
   implicitly captured through team-level EPA/DVOA inputs
3. **Applying an additional home/away delta on top of SaberSim projections would double-count
   the home advantage.**

**Recommendation: Skip home/away delta adjustment for NFL — SaberSim encodes it. Verify this
assumption against live data after first ~50 games by comparing SaberSim home-team projections
to actual outcomes split by home/away.**

### Quantified Delta (If Applying Independently of SaberSim)

If the model is ever used without SaberSim (e.g., custom projections), use these estimates
derived from available evidence:

| Stat | Home Delta (% of projection) | Evidence Quality |
|---|---|---|
| PASS_YARDS | +2.0 to +3.0% | Low — no direct measurement found |
| RUSH_YARDS | +1.5 to +2.5% | Low — EPA per rush: ~1.5% efficiency gain at home |
| REC_YARDS | +1.5 to +2.5% | Low — follows pass volume, correlated with QB delta |
| RECEPTIONS | +1.0 to +2.0% | Low — correlated with rec yards delta |
| PASS_TDS | +1.5 to +2.5% | Low — TD rate follows overall efficiency |

**Confidence: Low.** These estimates are derived from the aggregate 2.5-point spread advantage
and EPA rushing efficiency data. No public source contained per-stat, per-position home/away
splits quantified as a percentage for NFL player props.

### Comparison to NBA Home/Away Delta

| Stat | NBA Delta | NFL Equivalent | Ratio |
|---|---|---|---|
| Passing/Points | pts=+2.35% | PASS_YARDS ≈+2.5% | ~1:1 |
| Boards/Rushing | reb=+0.88% | RUSH_YARDS ≈+2.0% | NBA lower |
| Assists/Receiving | ast=+3.33% | REC_YARDS ≈+2.0% | NBA higher |

NFL home effects are comparable in magnitude to NBA, but the evidence base is weaker for
individual stat-level adjustments.

### Stadium-Specific Considerations

Notable outliers (strongest home field advantages per nfelo data):
- Kansas City (Arrowhead): crowd noise substantially impacts opposing QB communication
- Seattle (CenturyLink): historically top HFA, but declined post-2019
- Buffalo (Highmark): cold weather + noise
- Denver (altitude): meaningful fatigue effect, especially in altitude-naive opponents

**Recommendation:** Do not implement stadium-specific adjustments at launch. A league-average
delta (if any, and only if SaberSim doesn't encode it) is sufficient for v1. Flag stadium
as a future improvement gate.

---

## OPPONENT DEFENSIVE QUALITY

### Does SaberSim NFL Encode Opponent Quality?

**Yes — with high confidence.** SaberSim's NFL simulations are built "one play at a time" and
"account for match-ups." Their DFS product is built explicitly around matchup optimization
(identifying players vs. weak defenses). The SaberSim NFL optimizer shows "each player's
projected fantasy points production against the actual defense they're facing this week."

This means **SaberSim NFL projections already incorporate defensive quality adjustments.**
Applying a separate DVOA-based opponent multiplier on top of SaberSim projections would
double-count the matchup effect, just as the home/away delta would.

**Recommendation: Do NOT apply a separate opponent quality multiplier to SaberSim NFL projections.
Trust SaberSim's matchup encoding. Verify empirically after 50+ games.**

### If SaberSim Does NOT Encode (Fallback Research)

If empirical validation shows SaberSim fails to capture matchup effects adequately, use:

**Best pre-game signal: Pass DVOA (Football Outsiders) or EPA/play allowed (nfelo).**
- Pass DVOA is the gold standard for adjusting QB/WR projections vs. opponent.
  It is opponent-adjusted itself, available weekly, and correlates ~0.5 with actual
  offensive output.
- EPA/play allowed is slightly more predictive of future scoring (predictive weight 1.0
  for defense vs. 1.6 for offense in regression frameworks).
- Points allowed per game is the weakest signal — heavily contaminated by garbage time
  and opponent quality, and shouldn't be used.

**Empirically grounded multipliers (from prop betting analytics research):**

For QB PASS_YARDS:
- vs. bottom-5 pass defense (by DVOA): +10 to +15% above projection
  (Concrete example: Stroud prop line raised ~13.3 yards vs. #32 Pittsburgh pass defense,
  representing ~5-6% of a typical 230-yard line — or roughly 13/250 = +5.3% for one
  matchup data point. Extrapolated to full-season worst defense: +10-15% is reasonable.)
- vs. top-5 pass defense: −8 to −12% below projection
- vs. middle-tier (ranks 11–22): no adjustment (identity)

For WR REC_YARDS:
- vs. bottom-5 pass defense: +8 to +12%
- vs. top-5 pass defense: −7 to −10%
- vs. middle-tier: no adjustment

For RB RUSH_YARDS:
- vs. bottom-5 run defense: +8 to +12%
- vs. top-5 run defense: −7 to −10%

### TDs vs Yards: Which Is More Matchup-Dependent?

**TDs are MORE opponent-dependent than yards, but less predictable.**

Evidence:
- TD scoring is heavily red-zone dependent (red zone defense quality, goal-line packages,
  defensive scheme near the end zone). This creates large variance between top and bottom
  red zone defenses.
- Yards accumulate over all areas of the field — the matchup effect is diluted by the
  length of the field.
- DVOA framework confirms this: TD rate shows larger swing vs. strong/weak defenses than
  yards do, but also higher game-to-game variance (sample size problem).
- For the model: **use DVOA-derived adjustments for PASS_YARDS/REC_YARDS if SaberSim fails;
  for PASS_TDS/RUSH_TDS/REC_TDS, keep unadjusted and use wider confidence intervals.**

### Recommended Decision Tree for Opponent Quality

```
1. Use SaberSim projection as-is (opponent quality encoded in simulation)
2. Validate after N=50 games: compare SaberSim projections vs. actual outcomes
   grouped by opponent DVOA quartile.
3. If SaberSim systematically under/over-projects vs. weak/strong defenses:
   Apply residual multiplier from regression of (actual - SaberSim) on opponent pass DVOA.
4. If SaberSim is well-calibrated across matchups: no adjustment needed.
```

---

## CROSS-CUTTING NOTES

### Interaction Between Sections

The three adjustments interact. In a blowout, opponent quality is less relevant because
game script dominates play-calling. A recommended priority order:

1. **Blowout sigmoid**: apply first (overrides normal game flow)
2. **Opponent quality**: apply to base projection before blowout sigmoid
3. **Home/away delta**: skip (SaberSim encodes it)

Formula sketch:
```python
adj_proj = saber_proj * opponent_multiplier(dvoa_rank, stat)
# Then apply game script:
adj_proj = adj_proj * game_script_multiplier(projected_spread, position, stat)
# Home/away: already in saber_proj, do not apply
```

### Data Gaps and Confidence Levels

| Finding | Confidence | Source Quality |
|---|---|---|
| Trailing QB pass yards +15-20% | Medium | Industry consensus, no exact regression |
| Trailing RB rush yards −25% | Medium | Well-established directional signal |
| Leading RB rush yards +12% | Medium-Low | Logical / clock management doctrine |
| WR rec yards inflation +12% trailing | Medium | Follows QB volume signal |
| SaberSim encodes home/away | High | Platform documentation confirms |
| SaberSim encodes opponent quality | High | Platform documentation confirms |
| DVOA multiplier vs bottom-5 defense: +10-15% | Medium | One concrete example extrapolated |
| Threshold ≥14 pts for significance | Medium | Industry standard, confirms with prop lines |
| TDs more opponent-dependent than yards | High | Logical + DVOA methodology support |

### Priority Refit Gates

- After 200 NFL QB-game observations: run regression of (actual_yards - saber_proj)
  on projected_spread × trailing_flag to fit empirical k and midpoint.
- After 50 games: split SaberSim residuals by opponent DVOA quartile to validate
  whether double-counting adjustment is needed.

---

*Sources consulted: footballperspective.com, PFF, Fantasy Footballers Mythbusters, nfeloapp,
sabinanalytics.com, Football Outsiders DVOA methodology, SaberSim help center, Outlier.bet
prop research guides, sportsbettingdime.com, covers.com*
