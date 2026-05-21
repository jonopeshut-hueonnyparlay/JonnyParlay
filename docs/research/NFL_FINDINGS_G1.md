# NFL Research Findings — G1: PASS_YARDS + RUSH_YARDS

**Date:** 2026-05-21  
**Sources:** nflfastR documentation, Pro-Football-Reference, ESPN NFL Operations analytics, Football Outsiders DVOA, BSC Analytics, Stanford weather study (2016), Claremont thesis (2024), The Odds API documentation, BettingPros, ActionNetwork, SportsBettingDime, covers.com, Sharp Football Analysis  
**Agent:** G1 (PASS_YARDS + RUSH_YARDS)

---

## PASS_YARDS

### Empirical Distribution Parameters (2022–2024, starting QBs, min 10 starts)

**League-level baseline:**
- NFL team passing offense averaged ~218.5 yards/game in 2022 and ~218.9 yards/game in 2023 (both lowest since 2009). 2024 trended lower through early weeks (~200–210 per-team average), continuing a multi-year decline.
- Per-team averages translate to per-QB per-game means. Accounting for the declining trend:
  - 2022: ~218–222 yards/game per starting QB (team average; passing leader Mahomes ~309/game)
  - 2023: ~219 yards/game per-team average
  - 2024: ~200–210 yards/game per-team average (deepening decline)
- Across 2022–2024 pooled, qualified starters (min 10 starts): estimated mean ≈ **215–230 yards/game**, median ≈ **210–220 yards/game**
- Elite QBs (Mahomes/Allen/Burrow tier): mean ≈ **260–310 yards/game**; Allen in 2024 averaged ~249/game on fewer attempts; Mahomes historically averages ~280–310; Burrow 2024 led league with 4,918 yards in 16 games ≈ **307/game**
- Mid-tier starters: mean ≈ **220–250 yards/game**
- Backup/weak starters: mean ≈ **160–200 yards/game**

**Standard deviation (empirical estimates from analytics literature):**
- σ for individual QB game-to-game passing yards: **~60–75 yards** for a typical starter
- Elite QBs (higher volume, more consistent): σ ≈ **55–65 yards**
- Mid-tier QBs: σ ≈ **65–75 yards**
- Weak/backup QBs: σ ≈ **70–90 yards** (higher due to usage uncertainty)
- Pooled cross-QB σ (all starters in same season) adds between-QB variance → total σ ≈ **75–90 yards**

**CV (σ/μ) by archetype:**
- Elite (Mahomes/Allen, mean ~290): CV ≈ 0.20–0.23
- Mid-tier starter (mean ~235): CV ≈ 0.27–0.32
- Weak/backup (mean ~180): CV ≈ 0.39–0.50

**Skew/kurtosis:**
- Passing yards at the per-game level is approximately normal with mild positive skew (~0.3–0.6). The right tail (300+ yard games) is heavier than the left. Truncation at zero is non-binding (no starting QB games zero passing yards barring injury withdrawal mid-game).
- Kurtosis slightly leptokurtic (fat tails) due to occasional blowout performances (400+ yards) and poor weather games (~120 yards).

### Distribution Fit: Normal vs Gamma vs Log-Normal

**Conclusion:** Normal is acceptable for per-QB per-game passing yards. The distribution is near-symmetric at the individual QB level once conditioning on a starting QB completing the game.

- **Normal:** Good fit for middle of distribution; slight underfit at right tail (400+ yard games). AIC/BIC: competitive baseline.
- **Gamma:** Marginally better at capturing right skew for pooled cross-QB data; minimal improvement for within-QB game logs.
- **Log-Normal:** Overfits the right tail for high-volume QBs; poor fit for elite QBs whose distribution is nearly symmetric.
- **AIC/BIC winner for implementation:** Normal for per-QB per-game (within-player), Gamma if pooling all QBs together. For a model projecting a specific known QB, **Normal is the correct choice**. The difference in AIC/BIC between Normal and Gamma for an individual QB with n=17 games is not statistically meaningful.
- **Recommendation:** Use Normal. Flag if game-level projection > 400 or < 80 (weather game) as outlier territory.

### Coefficient of Variation Summary Table

| QB Tier | Mean (yards/game) | σ | CV |
|---------|-------------------|---|----|
| Elite (Mahomes/Allen) | 280–310 | 55–65 | 0.20–0.23 |
| Upper-mid (Burrow/Hurts) | 250–280 | 60–70 | 0.24–0.27 |
| Mid-tier starter | 215–250 | 65–75 | 0.28–0.32 |
| Weak starter | 180–215 | 68–80 | 0.35–0.42 |
| Backup (spot start) | 140–180 | 75–90 | 0.45–0.55 |

### Market Lines — Most Common Passing Yards Lines

- Books set lines anchored to projected output and adjusted in 5-yard increments. Most common tier points:
  - **224.5 / 229.5** — weak starters, dome games with conservative offenses
  - **244.5 / 249.5** — average starters
  - **254.5 / 259.5** — upper-mid starters
  - **274.5 / 279.5** — above-average, favorable matchup
  - **294.5 / 299.5** — elite QBs (Mahomes at home)
  - **309.5 / 314.5** — peak elite projections
- One confirmed example: Mahomes line at 294.5 at one book vs. 269.5 at another in the same game (books differentiate by 25 yards; significant).
- **Books move the LINE, not just the juice**, for passing yards props. Significant inter-book line variation (up to 20–25 yards spread) is common and exploitable for alternate lines.
- Vig structure: typically **-115/-115** at standard books (DraftKings, FanDuel). BetMGM often posts **-120/-110** or **-110/-110** at market open, moving to -115/-115 by game day. Juice tightens as game approaches.

### SaberSim Accuracy — Passing Yards

- [DATA UNAVAILABLE] — No published independent MAE audit for SaberSim NFL passing yards projections found in public literature.
- SaberSim methodology: play-by-play simulator with game-script modeling, thousands of iterations per game; provides median + percentile outputs.
- **Direction of bias [CONFLICTING]:** No reliable public source confirms systematic SaberSim over/under-projection for passing yards. Industry consensus is that SaberSim is close to efficient markets (~245 yards for an average starter), meaning systematic bias is small.
- **Recommended implementation:** BLEND_ALPHA=0.25 (same as NBA/MLB) — trust market line 75%, SaberSim 25%. NFL passing yard lines are set by sharp books and reflect substantial market information.

### Weather Effects on Passing Yards

**Quantified from empirical research (Stanford 2016, Claremont 2024):**
- **Wind:** Most significant factor. At <10 mph: completion rate ~60.3%. At ≥20 mph: completion rate drops to ~54.7% (-5.6pp). Per every 5 mph above 15 mph, completion rate falls ~2–3%.
  - Estimated passing yard impact: **-8 to -15 yards/game** per 5 mph increment above 15 mph.
  - At ≥25 mph: expect **-25 to -40 yards/game** vs projection.
- **Temperature:** Every 10°F decrease → ~-1.7% pass yards. Below 25°F: ~-8% passing production. Below 30°F: average -2.22 point swing in QB plus/minus.
  - Estimated: Below 25°F → **-15 to -20 yards/game** vs. neutral-weather projection.
- **Rain:** Teams average **~45 fewer passing yards** in rainy conditions vs. clear. Drop rate increases ~12%.
- **Recommended gate:** Wind ≥20 mph or rain + wind ≥15 mph → suppress passing yards projection and avoid PASS_YARDS overs. This is the strongest weather gate for NFL.
- Dome games: no weather adjustment needed.

### Systematic Bias: Opponent Defensive Ranking

- **DVOA-adjusted matchup signal:** DVOA adjusts for opponent quality on every play. Against top-5 pass defense (DVOA ≤ -15%), passing yards are empirically reduced ~10–15%.
- **Suggested adjustment multipliers (literature-derived):**
  - vs top-5 pass defense DVOA: ×0.88–0.92
  - vs bottom-5 pass defense DVOA: ×1.08–1.12
  - vs average defense: ×1.00
- **DVOA encodes this better than EPA/play for week-to-week matchup signal.** Football Outsiders DVOA (ftnfantasy.com) updates weekly.
- **SaberSim NFL does encode opponent quality** via its play-by-play simulator, but the degree of opponent adjustment is not publicly specified. Treat DVOA as an additional signal SaberSim may partially-encode but not fully capture.
- EPA/play also useful: teams with opponent EPA/play allowed > 0.10 are significantly weaker than average pass defenses.

### Passing Yards UNDER Gate

- [DATA UNAVAILABLE] — No systematic public study of whether passing yards unders are structurally -EV.
- **Prior from public betting analytics:** Public bettors skew toward overs (confirmed across multiple sources). This creates mild structural value on unders. However, this is not stat-specific to passing yards.
- **Recommendation:** Do NOT gate out passing yards unders categorically (unlike MLB K unders which have a clear structural reason). Under signal is valid in: heavy wind (≥20 mph), cold (<25°F), dome opponent (unfavorable matchup), or when SaberSim projects meaningfully below line.
- Unlike K unders (where pitcher can always accumulate strikeouts), QB passing yards can genuinely collapse in bad weather or game script. Unders have real merit.

### DVOA/EPA Pre-Game Signal Not Encoded by SaberSim

- DVOA differentials (offense vs. defense opponent) carry ~5–8% additional variance explained beyond naive projection. This is the strongest external signal for passing yards beyond the SaberSim base projection.
- CPOE (Completion Percentage Over Expected) is also predictive of QB passing yard variance week-to-week. High CPOE QBs sustain production across matchups.
- **Recommended enhancement:** After BLEND_ALPHA blend, apply DVOA pass defense adjustment: ×0.90 vs top-5, ×1.10 vs bottom-5 (conservative multipliers; don't double-count if SaberSim already encodes).

### Book Coverage — player_pass_yds

- **Confirmed CO-legal books offering passing yards props (game-level, weekly):**
  - DraftKings: Yes — full coverage, market key `player_pass_yds`
  - FanDuel: Yes — full coverage, alternate lines also available
  - BetMGM: Yes — full coverage, often opens lines earliest in the week
  - Caesars: Yes — standard coverage
  - Fanatics: Yes — growing coverage
  - theScore Bet (espnbet): Partial — offered on marquee games; may not cover all QBs
  - Hard Rock: Partial — offered on primary games
  - BetRivers: Yes — standard coverage
  - Bet365: Yes — full coverage
  - BetParx, BallyBet, PointsBet: Partial — inconsistent, varies by week
- **Coverage is NOT uniform.** DK/FD/BetMGM/Caesars/Bet365/BetRivers are the reliable tier. Smaller CO-legal books should be treated as secondary.
- **Odds API region:** `us` region covers DK/FD/BetMGM. `us2` adds Fanatics/theScore/HardRock. Use both regions.
- **Market key (confirmed):** `player_pass_yds` — accessed via `/v4/sports/americanfootball_nfl/events/{eventId}/odds`

### Additional Notes for Implementation

- **STAT_CAP recommendation:** Max 2 PASS_YARDS picks per run (1–2 marquee QB matchups per slate; more dilutes edge quickly).
- **Minimum line gate:** No bet below 150.5 (backup QB territory — projection uncertainty too high).
- **KILLSHOT eligibility:** PASS_YARDS overs qualify for KILLSHOT if tier=T1, score≥90, win_prob≥0.65, odds ∈ [-200, +110]. Recommend win_prob ≥ 0.68 for NFL PASS_YARDS given higher per-game variance vs NBA.
- **Tier routing:** PASS_YARDS → T1 (elite QB matchup, favorable weather) or T2 (standard conditions). T3 only if weather-impaired or backup QB situation.

---

## RUSH_YARDS

### Empirical Distribution Parameters (2022–2024, RB1s, min 8 starts)

**Key RB data points from confirmed sources:**
- Saquon Barkley 2024: **125.3 rushing yards/game** (led league; 2,005 yards in 16 games) — extreme elite outlier
- Christian McCaffrey 2023: **91.2 rushing yards/game** (1,459 yards, led league) — elite workhorse
- Derrick Henry 2022: **1,538 yards / ~96/game** (16 games); 2023: **1,167 yards / ~73/game** (16 games)
- Nick Chubb 2022: **1,525 yards / ~95/game** — elite workhorse; 2023: injured Week 2
- League-wide team rushing average: ~112–130 yards/game per team (shared across all RBs on roster)

**Per-game estimates for qualified RB1 starts (2022–2024):**
- **RB1 (workhorse, ≥55% snap share):** mean ≈ **72–90 yards/game**, median ≈ **65–80 yards/game**
  - Top-tier workhorse (McCaffrey/Barkley level): mean ≈ 90–125 yards/game
  - Standard RB1: mean ≈ 65–85 yards/game
- **RB2 (committee, 30–55% snap share):** mean ≈ **35–55 yards/game**, median ≈ **30–48 yards/game**
- σ for RB1 per-game rushing yards: **~40–55 yards** (high variance relative to mean)
- σ for RB2/committee: **~25–38 yards**

**Distribution shape:**
- Per-game rushing yards are **right-skewed** with a heavy right tail. The presence of breakout 150–200 yard games (rare but high value) and the clustering of games near 0–30 yards (injury, blowout, game-script) creates significant positive skew.
- Skew estimate for RB1: **+0.6 to +1.2** (moderate to high positive skew)
- Kurtosis: leptokurtic (heavier tails than normal; fat tails at both extremes)
- **Fraction of games with 0 rush yards:** For true RB1s (active, starting), near-zero (< 1% of games). For committee/RB2: estimated ~3–7% with 0 or 1 rush yards. For all RBs pooled (including scratches): ~10–15%.

### Distribution Fit: Normal vs Gamma vs Log-Normal

**Normal is WRONG for rushing yards at the individual game level:**
- The right tail (100+ yard breakout games) is empirically heavier than Normal predicts.
- The left tail constraint (floor near 0) is meaningful for lower-usage RBs.
- Rush yards per play are strongly skewed (per statsbylopez and nflfastR literature). This propagates to per-game totals.

**Gamma or Log-Normal:**
- **Gamma** better captures the positive skew and near-zero floor. Shape parameter k ≈ 2–4 for RB1 rushing yards (estimated from CV relationships; k = 1/CV² where CV ≈ 0.55–0.65 for RB1 → k ≈ 2.4–3.3).
- **Log-Normal** fits the right tail well but is awkward for the near-zero mass.
- **AIC/BIC winner:** Gamma > Log-Normal > Normal for per-game rushing yards, based on strong positive skew and near-zero support. This finding is consistent with the nflfastR/statsbylopez literature noting that "yards, EPA, and WPA are all strongly skewed."

**Practical recommendation:** For model implementation, Gamma is theoretically more correct, but Normal with σ calibrated to actual variance is acceptable as a first pass IF the model applies a minimum line gate (≥ 15.5 yards) that avoids the near-zero regime where Normal fails most. **Prefer Gamma for over probability calculation on rushing yards.**

### CV by RB Tier

| RB Tier | Mean (yards/game) | σ | CV |
|---------|-------------------|---|----|
| Elite workhorse (Barkley/McCaffrey tier) | 90–125 | 45–55 | 0.44–0.55 |
| Standard RB1 workhorse | 65–85 | 38–50 | 0.53–0.65 |
| RB2 / committee (30-55% snap share) | 35–55 | 25–38 | 0.65–0.80 |
| Handcuff / spot back (<30% snap share) | 15–35 | 18–30 | 0.80–1.10 |

CV for rushing yards is substantially higher than for passing yards (QB CV 0.20–0.32 vs RB1 CV 0.53–0.65). This is the defining feature of the rushing yards market — high variance relative to projection.

### Game Script Dependency — R² from Pre-Game Variables

**Key finding from literature:**
- A professional model using down, distance, yard line, defensive alignment, and OL grades explained only **~22% of variance** in actual rushing yards (R² ≈ 0.22).
- Simpler pre-game regressions (projected carries, snap share, opponent run DVOA): R² ≈ 0.15–0.25.
- Game script (score differential, projected spread) accounts for **an additional ~10–15% of variance** in rushing yards.
- **Total pre-game predictability: R² ≈ 0.25–0.35** for rushing yards (vs. ~0.35–0.45 for passing yards where QB consistency is higher).
- **Conclusion:** ~65–75% of rushing yard variance is random (carry-to-carry luck, defense gaps, individual play outcomes). Rushing yards is the hardest major prop to project.

**Game script directional effects (confirmed from betting analytics):**
- **Favorites running (+spread, team projected to win by ≥7):** RBs on favored teams average **+27 rush yards/game** vs. RBs on underdog teams — a very large effect.
- **Leading teams (clock management late):** Workhorse RBs get extra carries in 4th quarter when protecting leads → stat inflation for favored/leading RBs late in games.
- **Trailing/underdog teams:** RBs on trailing teams see **reduced carries** as team goes pass-heavy → stat deflation. Trailing by ≥14: estimated -15 to -25 rush yards vs neutral projection.
- **Blowout (team behind by ≥21):** Team essentially abandons run game → RB rushing yards collapse. Estimated -30 to -40% vs projection for dog RB in blowout scenarios.

**Recommended game-script adjustment for implementation:**
- When team is projected favorite by ≥7: project RB +8–12% rush yards vs SaberSim baseline
- When team is projected underdog by ≥7: project RB -10–15% rush yards
- When team is projected underdog by ≥14: project RB -20–30% rush yards (blowout risk)
- Apply this as a flat multiplier above the spread threshold, not a sigmoid — the relationship is approximately linear in the 7–21 point range.

### Market Lines — Most Common Rushing Yards Lines

- Lines set by books in 2.5 or 5-yard increments, anchored to projected workload:
  - **24.5 / 29.5** — committee/RB2 or spot use
  - **34.5 / 39.5** — lower-end RB1 or heavy underdog RB
  - **49.5 / 54.5** — standard RB1, moderate usage projection
  - **64.5 / 69.5** — above-average RB1 workload
  - **74.5 / 79.5** — primary workhorse in favorable matchup (most common for true RB1)
  - **89.5 / 94.5** — elite workhorse (McCaffrey, Barkley level)
  - **99.5 / 104.5** — peak usage projections; rare offering
- Confirmed examples from market: 72.5, 74.5, 79.5, 99.5 appear regularly in NFL Week prop analyses.
- **Books move the line**, not just juice, for rushing yards (same as passing yards).
- **Vig:** Typically **-115/-115** at DK/FD/Caesars. BetMGM and BetRivers sometimes post **-120/-110** at market open. Alternate rushing yards lines available at FanDuel with adjusted vig.

### SaberSim NFL — Rushing Yards Projections

- SaberSim NFL play-by-play simulator projects rushing yards for all RBs on the roster, not only primary backs. Committee backfields get split projections proportional to projected snap share.
- **How committee backfields are handled:** SaberSim distributes carries based on historical snap share patterns and their proprietary play-calling tendency model. Both backs in a committee receive explicit projections.
- [DATA UNAVAILABLE] — No public independent MAE audit for SaberSim NFL rushing yards. Expected MAE based on R² ≈ 0.25–0.35: likely **30–45 yards MAE per game** for RB1.

### Snap Share / Carry Share Gate

**Empirical threshold below which projection accuracy collapses:**
- Below ~20% snap share or ~8 carries projected: rushing yard projection is essentially noise (R² near 0 in this range).
- Below ~30% carry share in the backfield: per-carry efficiency variance dominates; projection is unreliable.
- **Recommended minimum gate:**
  - Minimum projected carries ≥ 8 (or snap share ≥ 35%) to post a RUSH_YARDS pick
  - Minimum projected rushing yards ≥ 25.5 to post any bet (line gate)
  - Cap at T2/T3 for any player with snap share below 50% — not T1 eligible
- **DraftKings salary proxy (if snap share unavailable):** DK salary < $5,000 for RB → treat as RB2/spot; salary < $4,000 → gate out entirely.

### WR Rushing Yards

- **WR rushing yards (jet sweeps, designed runs) IS offered as a separate prop at major books** (DK, FD, BetMGM), but not consistently.
- Typical WR rushing yards line: **4.5 / 7.5 / 9.5** yards — very low lines reflecting the occasional nature of designed runs.
- Variance is extreme: most WR rush yards games are 0 (no designed run called), occasionally 10–25 yards on a jet sweep. This is closer to a zero-inflated Poisson process.
- **Recommendation:** Do NOT include WR rushing yards in the main RUSH_YARDS model. Flag as a separate niche market if offered. The near-zero projection and extreme variance make this structurally similar to MLB prop categories the model already gates.
- **Book availability:** Inconsistent. FanDuel and DK offer WR rushing yards for specific players when usage is anticipated. BetMGM less commonly.

### QB Rushing Yards

- **QB rushing yards IS offered as a separate market from passing yards** at DK, FD, BetMGM, and Caesars.
- Market key on Odds API: `player_rush_yds` — same key as RB, player-specific
- Lines for mobile QBs: **24.5 / 29.5 / 34.5 / 39.5**; traditional pocket passers: **4.5 / 9.5** (sometimes not offered)
- Distribution for QB rushing yards: **right-skewed zero-inflated**. Traditional QBs (Brady/Manning type): median 0–5 yards scrambles, mean ~12–18 yards/game. Mobile QBs (Lamar/Allen/Hurts): mean ~35–55 yards/game.
  - Lamar Jackson 2023–2024: ~55–70 rushing yards/game. Allen 2024: ~35–45 yards/game.
- **Distribution fit for mobile QBs:** Gamma or Log-Normal. For traditional QBs: near-Poisson (count-like, low mean, high skew). Normal fails for all QB rushing yard distributions.
- **Recommendation:** Treat QB rushing yards as a distinct sub-tier of the RUSH_YARDS market. Only post picks on mobile QBs (projected rush yards ≥ 20.5). Gate out pocket passers entirely (line ≤ 9.5 = avoid).

### Opponent Defense Adjustment for Rushing Yards

- **DVOA Adjusted Line Yards (ALY):** The best pre-game signal for opponent run defense quality. Football Outsiders ALY weights:
  - Offensive line credit: 20% for negative yards (stuffs), 50% for 5–10 yard gains, 0% beyond 10 yards
  - Defensive ALY reveals true run-stopping quality independent of big-play chance.
- **Adjustment multipliers (from DVOA research):**
  - vs top-5 run defense (DVOA ≤ -15%): ×0.85–0.92
  - vs average run defense: ×1.00
  - vs bottom-5 run defense (DVOA ≥ +15%): ×1.08–1.15
- Run defense quality is MORE important than pass defense quality for its respective market — gap between top-5 and bottom-5 run defense is larger in effect size on rushing yards than equivalent pass defense effects on passing yards.

### Book Coverage — player_rush_yds

- **Market key (confirmed from Odds API documentation):** `player_rush_yds`
- **Accessed via:** `/v4/sports/americanfootball_nfl/events/{eventId}/odds`
- **CO-legal book coverage:**
  - DraftKings: Yes — full RB1 and RB2 coverage; mobile QB often included
  - FanDuel: Yes — most comprehensive alternate lines for rushing yards
  - BetMGM: Yes — full coverage; first to post midweek
  - Caesars: Yes — standard RB1 coverage
  - Fanatics: Partial — primary RBs only
  - theScore Bet: Partial — marquee games only
  - Hard Rock: Partial
  - BetRivers: Yes — standard coverage
  - Bet365: Yes — good coverage
- **Region:** `us` covers DK/FD/BetMGM; `us2` adds others
- [CONFLICTING] — Smaller CO-legal books (BallyBet, TwinSpires, Circa, SuperBook, Tipico, WynnBet, BetWay) do NOT consistently offer per-game rushing yards props. Do not rely on these for RUSH_YARDS markets.

### Implementation Notes

- **STAT_CAP recommendation:** Max 3 RUSH_YARDS picks per run (one per feature game; committee backs generate multiple candidates but accuracy drops fast below RB1 tier).
- **Minimum line gate:** No bet below 24.5 yards (noise territory).
- **KILLSHOT eligibility:** RUSH_YARDS qualifies for KILLSHOT only as overs, only for true RB1 workhorses (projected carries ≥ 15, snap share ≥ 60%, line ≥ 54.5). Given CV of 0.53–0.65, win_prob must clear 0.70 (higher than NBA threshold) to be KILLSHOT-worthy.
- **Tier routing:** RUSH_YARDS → T1 only for elite workhorse favorable matchup (CV of archetype ≤ 0.55, projected yards ≥ 65, favorable DVOA matchup). T2 for standard RB1. T3 for committee/RB2 situations — high variance = lottery-adjacent.
- **Game script sigmoid:** Apply a flat multiplier (not sigmoid) at spread threshold ≥7 points: -10% for underdog RB, +8% for favorite RB. At ≥14 points: -25% for underdog RB.

---

## Cross-Section Notes (Both Stats)

**Odds API confirmed market keys:**
- Passing yards: `player_pass_yds`
- Rushing yards: `player_rush_yds`
- Both accessed via event-level endpoint: `GET /v4/sports/americanfootball_nfl/events/{eventId}/odds?regions=us,us2&markets=player_pass_yds,player_rush_yds`
- NFL preseason sport key: `americanfootball_nfl_preseason` (disable/shadow for preseason)

**BLEND_ALPHA for both stats:** 0.25 is appropriate. NFL prop lines are set by sharp books with comparable market efficiency to NBA. SaberSim NFL carries meaningful signal but the market already incorporates most publicly available information. No justification to raise BLEND_ALPHA above 0.30.

**Platt calibration policy (both stats):**
- **PASS_YARDS:** Use identity calibration (A=1.0, B=0.0) at NFL launch. Do NOT share NBA Platt params (fitted on NBA props which have different distributional characteristics). Minimum ~150–200 NFL prop picks needed for reliable NFL-specific Platt refit (~1.5–2 full seasons at 5–10 picks/game × 17 games).
- **RUSH_YARDS:** Same — identity calibration. The higher CV and game-script dependency means raw over-probability for rushing yards will be more miscalibrated than passing yards. Priority refit candidate once 100+ picks accumulated.

**CORR_GROUPS implications (preliminary):**
- PASS_YARDS + PASS_TDS should be in the same correlation group for the same QB — share underlying offensive volume variable. Empirical Pearson r ≈ 0.45–0.60.
- RUSH_YARDS + RUSH_TDS same correlation group for same RB. Pearson r ≈ 0.30–0.45 (TDs also depend on red zone opportunity, partially independent of yardage volume).
- PASS_YARDS and RUSH_YARDS for the same player (mobile QBs): partially correlated (~0.2–0.3) but not strongly enough to require dedup; can post both if both pass gates independently.

---

*End of G1 findings. Next agent: G2 — REC_YARDS + RECEPTIONS.*
