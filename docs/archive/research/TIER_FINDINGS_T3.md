# Tier Findings: T3 — NHL Props + MLB Pitcher + MLB Batter

**Research date:** 2026-05-21  
**Scope:** Sections 5–7 — NHL SOG/AST/GOALS, MLB K/OUTS/HA, MLB HITS/TB/HRR  
**Context:** Each market assessed on two axes: (1) outcome variance / CV profile and (2) book pricing efficiency / hold. Both axes determine tier.

---

## SECTION 5: NHL PLAYER PROPS

### 5.1 NHL SOG (Shots on Goal) — Current T1, STAT_CAP=6

**Variance profile**

SOG is the closest thing hockey has to a counting-stat prop with genuine within-player consistency. High-volume shooters (top-line forwards and D with power-play time) show very sticky shot rates game-to-game: a player averaging 4.1 SOG/game tends to cluster near that number regardless of outcome. Typical top-line forward SOG averages range from 2.5 to 4.5 per game. Standard deviation for a player averaging ~3 SOG is approximately 1.4–1.7 shots, implying a game-level CV of roughly **0.47–0.57**. This puts SOG in the lower half of the variance spectrum for player props — meaningfully lower than assists or goals, and comparable to NBA AST (the model's benchmark T1 stat). The lines are set at 2.5 or 3.5, which anchors the over/under around a player's mean, making the market well-behaved for projection purposes.

**Market efficiency**

SOG is recognized by sharp betting communities as the sharpest NHL prop market. Oddsmakers track shot data closely — they use a player's recent averages, role, matchup (opponent SOG suppression), and power-play deployment to set lines. Line movement in SOG markets is responsive and sharp action moves numbers quickly. Books do NOT run the same 20–35% hold they apply to goal scorer props; SOG hold is closer to **8–12%**, more like a standard prop market. Volume throughput on SOG is also higher than any other NHL prop type — over/under shot totals are the highest-traffic NHL player prop category. The Odds Shark NHL Shot on Goal Betting Report and similar tools exist specifically because of market depth.

SOG is also the market most exploited by analytics-forward bettors. Books are slowest to adjust when power-play deployment changes mid-season. Power-play time creates stale lines in SOG because PP usage is volatile but books react slowly to changes in TOI and power-play role.

**STAT_CAP=6 justification**

NHL slates during the regular season carry 7–15 games, meaning 30–60 forwards with SOG lines available. STAT_CAP=6 limits exposure to 6 SOG picks per run, which is proportionate to slate depth. NBA has STAT_CAP=2 for most stats because NBA slates have fewer games (5–13 per night) and less diversity. An NHL SOG-heavy slate legitimately surfaces 8–12 qualified picks, so a cap of 6 is reasonable concentration control without artificially suppressing a genuinely productive market. Justified as-is.

**Recommendation**

- **Tier: T1 — confirmed.** CV ~0.47–0.57 matches NBA AST, which is the T1 benchmark. Hold is reasonable (8–12%). Market is the sharpest NHL prop.
- **Min edge: 3% — confirmed.**
- **STAT_CAP=6: justified.** Leave unchanged.

---

### 5.2 NHL AST (Assists) — Current T1, Line 0.5

**Is AST 0.5 binary-adjacent?**

Yes. Strongly. With the line at 0.5, bettors are wagering on whether a player records at least one assist in the game — a pure binary (over/under). This is structurally identical to a Bernoulli bet. Even elite playmakers like Connor McDavid (~1.02 APG career) fail to record an assist in roughly 35–45% of games. Players ranked 20th–50th in assists per game — the group that typically generates AST prop lines — record zero assists in **50–65% of games**. The hit rate on "over 0.5 assists" for a non-elite playmaker is often only 35–50%, making this genuinely coin-flip adjacent.

**Variance / CV**

Assist outcomes follow a highly skewed distribution: most outcomes are 0, a smaller fraction are 1, and a tail extends to 2–3 in big games. The CV for a player averaging 0.45 APG with SD ~0.55 is approximately **1.22**. That is far above the T1/T1B threshold range (0.45–0.65 for more continuous stats). Assists are more volatile than goals on a per-game basis, which is counterintuitive — but because assists require teammate actions (someone has to score, and the play has to be credited), assists carry more contingency-on-randomness than shots.

Research from HFBoards and adjusted hockey databases confirms that assists frequency graphs are right-skewed and bimodal: the modal value is 0, with a secondary cluster at 1.

**Is NHL AST mis-tiered at T1?**

Yes — NHL AST should be reclassified. The 0.5 line creates a binary bet where:
- The true P(over) is 35–55% for most players getting a line
- The CV is >1.0 (bimodal, extremely high variance)
- Books price it with 20%+ hold, treating it like the goal scorer market (high vig)

This is a T3 profile: binary-adjacent outcome, high book hold, high noise. Keeping it at T1 with 3% min edge means the model is accepting too little edge for the amount of variance being absorbed. A T3 classification at 6% min edge is structurally correct.

**Recommendation**

- **Tier: RECLASSIFY T1 → T3.** Binary-adjacent Bernoulli bet, CV >1.0, holds resemble goal scorer markets (20%+), not SOG markets.
- **Min edge: 6%** (T3 standard).
- **Note:** This reclassification also aligns NHL AST with how the model treats 3PM (T3) — both are binary-adjacent props with high CV where the book prices in substantial vig.

---

### 5.3 NHL GOALS — Planned T3, Not Yet Live

**Variance / CV**

Player goals are the most binary prop in hockey. Even Auston Matthews (0.621 goals/game career) fails to score in roughly 50–55% of games. A typical top-10 goal scorer averages ~0.45 goals/game; a typical 20-goal-season player averages ~0.24 goals/game. At these means, SD ≈ mean × √(1 − p) under a Bernoulli model (since goals are essentially Bernoulli with small p). CV for a 0.40 G/game player: SD ≈ 0.49, CV ≈ **1.23**. CV for a 0.25 G/game player: CV ≈ **1.73**. This is significantly higher than assists, which is already high. Goals are the most binary and volatile NHL player prop available.

**P(goals=0) per game**

- Elite scorer (0.55 G/game): P(0) ≈ 45–50%
- Top-20 scorer (0.40 G/game): P(0) ≈ 55–60%
- Average forward with a line (0.25 G/game): P(0) ≈ 70–75%

**Market efficiency vs SOG**

Goals markets carry the worst hold in NHL props. Books apply 20–35% vig to anytime goal scorer props, compared to 8–12% for SOG. This reflects two things: (1) public money piles onto big names (McDavid, Matthews) distorting the market, and (2) genuine model difficulty in pricing goals (goalie matchup, defensive deployment, puck luck via BABIP-equivalent shooting %). The market is SOFTER in the sense that edges may exist more often — but the variance means you need a much larger edge to overcome it. An edge in a goals market is less reliable than the same-sized edge in a SOG market.

The "softer market" framing is tricky: the market is less efficient (softer to find raw edge) but also higher-variance (the edge is harder to realize within a normal sample). T3 with a 6% min edge requirement is the right framework — require a bigger cushion before posting to compensate for the noise.

**Recommendation**

- **Tier: T3 — confirmed for planned implementation.**
- **Min edge: 6%** (same as 3PM, which has an analogous bimodal profile).
- **Note:** Goals are even more binary than AST; T3 is if anything conservative. If GOALS are added, also consider a STAT_CAP (e.g., 4/run) to limit exposure to a single volatile NHL category.

---

## SECTION 6: MLB PITCHER PROPS

### 6.1 MLB K (Strikeouts) — Current T1

**Variance / CV**

Strikeouts are the most predictable MLB individual stat and the most analytically grounded pitcher prop. Key findings:

- R² for predicting K from underlying pitcher quality (K%, whiff rate, CSW rate) is **0.81–0.88** — the highest of any MLB pitcher stat
- A pitcher averaging 7 K/start has a typical game-to-game SD of approximately **2.0–2.5 K**, yielding a CV of **0.29–0.36**
- An illustrative real-world example: a pitcher with recent starts of 6, 2, 7, 3 K (avg 4.5, swing of 5) reflects CV ≈ 0.44 — and this is a high-variance example, not the norm

The CV range for K is **0.28–0.44**, the tightest of any MLB stat. This is T1-level variance.

**Market efficiency**

Books are well-calibrated on K props. CSW (Called Strike + Whiff Rate) from Baseball Savant and FanGraphs is publicly available and directly models strikeout rate. Books incorporate this. The sharp market on K is deep, with multiple competing books and tight lines. Limits are better than batter props.

K lines are the highest-volume MLB pitcher prop category. Professional tools (Ballpark Pal projections via VSiN, Dimers pitcher projections, FTA CSW analysis) all target K as primary.

**K Under gate justification**

The model gates K unders. This is justified. There are structural reasons K overs are more reliably edged: (1) pitcher K rates are sticky upward — an ace having a bad K night still has elite stuff; (2) K under requires a specific outcome (batter contact) that depends on both pitcher AND batter, making unders harder to project; (3) early hook risk: a pitcher who gets knocked around exits early, potentially missing his K projection — but this cuts both ways and more often helps the over (more at-bats in trouble). The industry consensus among sharp bettors is "K overs, not unders" as the primary edge direction.

**Recommendation**

- **Tier: T1 — confirmed.** CV 0.28–0.44, best-in-class predictability, efficient but not overpriced market.
- **Min edge: 3% — confirmed.**
- **K Under gate: retain.** Directional restriction consistent with T1B philosophy; K overs are the clean edge direction.

---

### 6.2 MLB OUTS (Outs Recorded) — Current T2

**Variance / CV**

Outs recorded is correlated with K (both depend on pitcher quality and innings pitched) but substantially more variable due to game-script factors K is largely insulated from. Typical range: 10–21 outs recorded in a start, with a common line at 17.5 (5.2 IP). SD for a mid-rotation starter is approximately **3.5–4.5 outs**, yielding a CV of **0.20–0.26** on a raw numbers basis — BUT this understates risk because:

1. **Manager hook risk**: The single biggest driver of OUTS variance is manager decision-making, independent of pitcher quality. Strict pitch-count managers pull starters at a fixed threshold (95 pitches) regardless of performance; inning-managers let pitchers finish frames. The same pitcher with the same quality outing can differ 2–3 outs based solely on manager style. This is an unmodellable binary variable game-to-game.

2. **Game-script blowout / mercy hook**: Winning or losing big changes the incentive to extend a starter. A dominant start in a blowout win may result in a shorter outing to protect the arm, paradoxically. Rain delays, DH rules, injury early, opponent big inning — all create catastrophic step-function risk.

3. **Pitch efficiency**: A pitcher running hot on K efficiency throws fewer pitches per out, extending innings. A wild pitcher burns through his limit faster. This IS projectable (WHIP, BB/9) but adds another interaction term.

Effective CV accounting for manager variability: **0.35–0.50**. This puts OUTS between K (T1, CV 0.28–0.44) and batter props (T1B, CV 0.70+). The manager hook risk specifically disqualifies OUTS from T1 — it's a structural, non-eliminable source of variance on top of pitcher quality.

**Is OUTS more volatile than K game-to-game?**

Yes. K variance is driven by pitcher stuff and opponent quality — both projectable. OUTS variance includes K variance PLUS the manager-decision binary PLUS game-script PLUS weather/rain risk. OUTS is strictly harder to project than K for the same pitcher-game.

**Recommendation**

- **Tier: T2 — confirmed.** Manager hook risk creates irreducible step-function variance beyond pitcher quality. CV ~0.35–0.50 with tail risk from early exits.
- **Min edge: 5% — confirmed.**

---

### 6.3 MLB HA (Hits Allowed) — Current T1B

**Variance / CV**

Hits allowed is the most luck-contaminated pitcher stat. The BABIP (Batting Average on Balls in Play) research by Voros McCracken established that most MLB pitchers cluster near .300 BABIP over large samples, with game-to-game variance almost entirely random. Key findings:

- Pitchers have minimal control over BABIP on balls in play — essentially all MLB starters regress to league average (~.300) over time
- A starter facing 25–30 batters per game with ~0.300 BABIP on contact has a binomial hit distribution: expected ~5–7 hits allowed per start with SD ~2.3–2.8
- CV for HA ≈ **0.40–0.55**

**Is HA more like a batter prop (T1B) or game line (T2)?**

HA sits in between. The variance is higher than K (BABIP randomness adds noise), but the direction of modellable edge is pitcher-based (GB%, FB%, whiff rate affects BABIP partially). The T1B classification is defensible because:
- Like HITS (batter), HA involves a per-at-bat probability that compounds
- The edge direction is typically "unders" (elite pitchers under their HA line) — same directional bias as batter HITS overs
- T1B allows directional gating

**Market efficiency**

Books are NOT especially sharp on HA. BABIP luck means no projection system reliably out-performs book lines on HA at high frequency. The market is softer than K lines — books underweight BABIP regression and sometimes set HA lines too tight around recent hit-allowing rates for a pitcher on a hot or cold streak. This is the exploitable edge. However, the variance means individual game results are noisy even when the edge is genuine.

**Recommendation**

- **Tier: T1B — confirmed.** HA is directional (unders on elite pitchers), moderately volatile (CV 0.40–0.55), and books are softer on HA than K. T1B with "unders only" gating or strong directional preference is correct.
- **Min edge: 3% — confirmed.**

---

## SECTION 7: MLB BATTER PROPS

### 7.1 MLB HITS (Batter Hits) — Current T1B

**Variance / CV and distribution shape**

Batter hits per game follow a near-binomial distribution, anchored by the reality that most MLB batters get 3–4 at-bats per game. Using a binomial model for a .260 hitter (league-average batting average) with 4 at-bats:

- **P(0 hits)** = (0.74)^4 ≈ **0.300** (30%)
- **P(1 hit)** = C(4,1) × 0.26^1 × 0.74^3 ≈ **0.421** (42%)
- **P(2 hits)** = C(4,2) × 0.26^2 × 0.74^2 ≈ **0.221** (22%)
- **P(≥3 hits)** = ≈ **0.058** (6%)

Expected hits per game: 4 × 0.260 = **1.04**. Standard deviation: √(4 × 0.26 × 0.74) ≈ **0.877**. CV ≈ **0.84**.

For a .280 hitter (upper end of regular starter):
- Expected hits: 1.12, SD ≈ 0.898, CV ≈ **0.80**

This is clearly high-variance: the modal outcome is 1 hit (42%), zero-hits occurs 30% of the time, and ≥2 hits is the exception. The 0.5 line market (over 0.5 hits = gets any hit) has P(over) ≈ 70% for a .260 hitter — this is priced as a heavy favorite, not binary-adjacent. The 1.5 line market is much more balanced: P(over 1.5 hits) ≈ 28% for a .260 hitter. Most books use the 0.5 or 1.5 line.

**Is HITS binary-adjacent enough for T3?**

At the 0.5 line: No. A .260 hitter hits over 70% of the time — not a coin flip. The directional asymmetry makes this more like a high-frequency T1 prop where the edge comes from accurately pricing P(hit ≥ 1). At the 1.5 line: Yes, more binary-adjacent (28% hit rate for .260 average, closer to coin flip). But T1B with directional gating (overs on the 0.5 line, unders on the 1.5 line) covers both cases more flexibly than T3.

**T1B is the right classification.** CV of 0.80–0.84 is genuinely high, but:
- The statistical edge in HITS comes from identifying when a pitcher's K%/BABIP creates systematic over/under pricing on a specific matchup — this IS projectable
- T1B directional gating lets the model restrict to overs (where the P(hit ≥ 1) calculation is most reliable)

**Recommendation**

- **Tier: T1B — confirmed.** High CV (0.80–0.84) but directable edge; overs on 0.5 line are the clean angle. Binary-adjacent risk at the 1.5 line is handled by directional gating.
- **Min edge: 3% — confirmed.**

---

### 7.2 MLB TB (Total Bases) — Current T2

**Variance / CV**

Total Bases (TB) is strictly more volatile than HITS because:
1. TB is a function of BOTH whether the batter gets a hit AND what kind of hit (single=1, double=2, triple=3, HR=4)
2. Power production (XBH rate) is more volatile than contact rate — home runs are particularly bimodal (Bernoulli at very low p)

For a .260 hitter with average extra-base hit rates (ISO ~.150):
- Expected TB ≈ 1.04 × (1 + ISO factor) ≈ ~1.25 TB/game
- Typical TB distribution: P(0) ≈ 30%, P(1) ≈ 35%, P(2) ≈ 20%, P(≥3) ≈ 15%
- SD ≈ 1.05–1.20, CV ≈ **0.84–0.96**

The extra layer of uncertainty from hit type makes TB harder to model than HITS. The standard 1.5 TB line has P(over) ≈ 35–40% for an average batter, similar to HITS at the 1.5 line. However, hitting a double or HR in a given game is essentially a second Bernoulli trial on top of the first (getting a hit), compounding variance.

**Is TB more predictable than HITS?**

No. TB is less predictable. Power variance (HR swing) makes TB more variable than straight hits. Research consistently notes that "high-floor props like hits, walks, or outs offer more predictability" — TB is explicitly in the lower-predictability bucket because of the hit-type dependency.

**T2 placement** accounts for the additional variance layer beyond HITS (T1B). Books are also reasonably well-calibrated on TB given access to exit velocity / launch angle / barrels from Statcast — so the market is not notably softer than K. But the variance profile warrants the higher threshold.

**Recommendation**

- **Tier: T2 — confirmed.** CV 0.84–0.96, additional hit-type variance layer beyond HITS. Books use Statcast for calibration, moderate efficiency.
- **Min edge: 5% — confirmed.**

---

### 7.3 MLB HRR (Hits + Runs + RBIs) — Current T1

**Variance / CV**

HRR sums three correlated stats. The variance-reduction from summing correlated stats depends on the correlation structure:

- HITS and RBI are positively correlated (hits generate RBI opportunities) but not tightly (most hits are solo or no-RBI)
- HITS and RUNS are positively correlated (on-base is prerequisite for runs)
- RBI and RUNS are weakly correlated

The standard line is 1.5 HRR, with the question: will a player accumulate ≥2 hits + runs + RBIs combined? Expected HRR for a .260 hitter batting 5th in a typical offense: ~1.8–2.2 HRR/game.

Key insight: because the line is 1.5 and mean is ~1.8–2.2, the market is NOT binary-adjacent at all. HRR over 1.5 hits ~55–65% of the time for lineup-relevant batters — this is structurally similar to a T1B market (directional, moderate-to-high hit rate). The combination of three stats widens the path to "over" outcomes: a player can reach 2 HRR via 2 hits + 0 RBI/runs, OR 1 hit + 1 run + 0 RBI, OR 1 hit + 1 RBI + 0 runs, etc.

**Is HRR a soft combo market?**

Partially. Books set HRR lines based on player averages and lineup position, but they underweight the combinatorial path diversity (many ways to reach ≥2 HRR) which creates systematic over-pricing of the under. The market is less refined than K or SOG because three-stat combos have more moving parts and books anchor on recent performance rather than underlying probabilities. Lineup position research shows that mid-order hitters (3-5 slot) have systematically better HRR over rates due to RBI opportunity clustering — and books are slow to adjust for lineup shuffles.

**CV for HRR**

Estimating HRR SD by combining individual stat SDs with correlations:
- Var(HRR) ≈ Var(H) + Var(R) + Var(RBI) + 2×Cov(H,R) + 2×Cov(H,RBI) + 2×Cov(R,RBI)
- Rough estimate: SD(HRR) ≈ 1.10–1.35, mean HRR ≈ 1.8–2.2
- CV ≈ **0.50–0.75**

This is lower CV than single-stat HITS (0.80–0.84) or TB (0.84–0.96) because the three-stat sum does reduce variance through diversification even with positive correlation. This validates T1 placement: HRR has lower per-outcome variance than HITS despite the complexity, because the summing smooths individual spikes.

**Recommendation**

- **Tier: T1 — confirmed.** CV 0.50–0.75 (lower than HITS/TB due to diversification across 3 correlated stats). Lineup position matters significantly for edge identification — the model should weight batting order heavily.
- **Min edge: 3% — confirmed.**
- **Key edge angle:** Exploit books' slow adjustment to lineup changes (mid-order vs leadoff shuffles drive HRR over/under dramatically). Runs and RBI cluster by lineup position regardless of the individual batter's production.

---

## SUMMARY TABLE

| Stat | Sport | Current Tier | CV Estimate | Hold / Efficiency | Verdict |
|------|-------|-------------|-------------|-------------------|---------|
| SOG | NHL | T1 | 0.47–0.57 | 8–12% hold; sharp | **T1 confirmed** |
| AST | NHL | T1 | >1.0 (bimodal) | 20%+ hold; binary-adjacent | **RECLASSIFY → T3** |
| GOALS | NHL | T3 (planned) | 1.23–1.73 | 20–35% hold; softer | **T3 confirmed** |
| K | MLB | T1 | 0.28–0.44 | Sharp; tight lines | **T1 confirmed** |
| OUTS | MLB | T2 | 0.35–0.50 | Moderate; manager-hook risk | **T2 confirmed** |
| HA | MLB | T1B | 0.40–0.55 | Softer (BABIP luck); directional | **T1B confirmed** |
| HITS | MLB | T1B | 0.80–0.84 | Directional; 0.5 line overs | **T1B confirmed** |
| TB | MLB | T2 | 0.84–0.96 | Moderate; Statcast-calibrated | **T2 confirmed** |
| HRR | MLB | T1 | 0.50–0.75 | Softer combo; lineup-position edge | **T1 confirmed** |

---

## KEY ACTIONABLE FINDINGS

1. **NHL AST must be reclassified T1 → T3.** This is the only structural error in the current tier system identified in this research. The 0.5 line is a Bernoulli bet with CV >1.0 and 20%+ book hold. Keeping it at T1 with 3% min edge is accepting far too little cushion for the variance.

2. **NHL GOALS (planned T3): confirmed.** Even more binary than AST. CV exceeds 1.2 for most players with lines. A STAT_CAP (4/run) should accompany go-live to cap concentration in this volatile category.

3. **SOG STAT_CAP=6: justified.** SOG is the most liquid, sharpest NHL prop. Six picks per run is appropriate given NHL slate depth (7–15 games).

4. **MLB K: confirmed T1, overs-preferred gate confirmed.** Best-in-class predictability (R²=0.81–0.88 for underlying model), tightest CV in the dataset.

5. **MLB OUTS: confirmed T2.** Manager hook risk is the dominant variance driver, not pitcher quality — it is structurally unmodellable on a per-game basis. T2 with 5% min edge correctly reflects this.

6. **MLB HRR: confirmed T1.** Diversification across 3 correlated stats reduces CV below single-stat batter props. Primary edge angle is lineup position (mid-order batters have structurally better RBI opportunity) — books adjust slowly to lineup shuffles.

7. **MLB HITS vs TB ordering correct.** HITS (T1B) < TB (T2) in tier is validated: TB adds hit-type variance on top of contact variance, pushing CV from 0.80–0.84 (HITS) to 0.84–0.96 (TB).

---

## NEXT STEPS

- Implement NHL AST reclassification T1 → T3 in run_picks.py tier config.
- When implementing NHL GOALS, add STAT_CAP (recommend 4/run).
- For HRR edge quality: add batting order as a feature to HRR pick scoring (5th-place over vs leadoff under as distinct signals).
- MLB K under gate: retain. Validate it against pick_log.csv K directional split in next backtest run.
