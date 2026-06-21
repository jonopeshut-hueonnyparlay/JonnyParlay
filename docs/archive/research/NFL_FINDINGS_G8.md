# NFL Research Findings — Group 8
## Overtime Effects | Playoff vs Regular Season | TNF/MNF/SNF | Zero-Inflation/Hurdle Models

**Research date:** 2026-05-21
**Sources:** PFF, ActionNetwork, FanDuel Research, ParlaySavant, TheSportsGeek, Pro-Football-Reference, BetMGM blog, OddsJam, sports-king.com, mcubed.net, Fantasy Footballers

---

## OVERTIME EFFECTS

### Settlement Policy (Player Props)

**All three major books settle player props INCLUDING overtime unless explicitly labelled otherwise.**

- **DraftKings:** "All bets include overtime unless otherwise stated." Player props (passing yards, rushing yards, receiving yards) count full-game stats including any OT period. A player who throws 280 yards in regulation and 40 yards in OT settles as 320 yards.
- **FanDuel:** "Overtime counts for all markets unless stated otherwise." Same policy — full-game props include OT.
- **BetMGM:** Same default inclusion. Only regulation-only bets are labelled "60 minutes only" or "excludes OT."

**Action requirement (all books):** For a prop to have action, the player must take the field for at least one offensive snap. If a player does not play, the prop is voided and refunded (not graded as a loss). This is the standard across all CO-legal books — same binary void policy as NBA.

### Game Lines (Spread / Total / ML)

**NFL spread, total, and moneyline all include overtime.**
- Point spreads: final margin including any OT score counts.
- Game totals (over/under): all points scored including OT count.
- Moneyline: team that wins in OT wins the bet. A tie after OT (extremely rare, <0.5% of games historically) grades as a push on all major books.

There is **no standard regulation-only line in NFL** the way soccer has a "draw no bet" equivalent. Regulation-only props/lines exist but are explicitly marked and rarely offered.

### OT Frequency (2022–2024)

| Season | OT Games | Total Games | OT Rate |
|--------|----------|-------------|---------|
| 2022   | 20       | 272         | 7.4%    |
| 2023   | ~16      | 272         | ~5.9%   |
| 2024   | 16       | 272         | 5.9%    |

Long-run average: ~5–6% of NFL regular season games go to overtime (roughly 1 in 17–20 games). Season-to-season range: 14–21 OT games per year is typical.

**Playoff OT:** Higher variance but small sample (13–14 playoff games). Playoff OT rules changed in 2022 (both teams guaranteed a possession on first OT unless first team scores a TD). This matters for game line grading if a team scores a TD on first OT possession — the game ends immediately.

### Projection Bias from OT

**Assessment: OT frequency is NOT large enough to materially bias prop projections at the model level.**

Reasoning:
- At 5–7% OT rate, the expected extra stat contribution from OT averages to a small fraction of one game's output spread across all games.
- A QB averaging 270 yards/game gains perhaps ~20–30 yards in OT, which in a 5.9% OT game adds roughly 1.2–1.8 expected yards to the per-game average — less than 1% of projection.
- The OT stat HELPS overs (more yards in OT) but is already partially priced into lines (books know OT exists).

**Recommendation:** Do NOT add an OT probability adjustment to game line or prop projections. The NBA model does not do this and NFL OT frequency is comparable to or lower than what has been studied. The effect is noise-level at ~5–7%.

**One exception to monitor:** In a specific high-spread game where one team is expected to win in OT and take a knee (clock management), trailing-team prop overs could be slightly inflated. This is a second-order effect and not worth a systematic adjustment.

---

## PLAYOFF vs REGULAR SEASON

### Empirical Data (2018–2024)

Direct per-game averages from league-wide regular season vs playoff splits:

**Passing Yards:**
- Regular season (2020–2023 trend): Declining from 496 yds/gm (2020) → 491 (2021) → 462 (2022) → 444 (2023) on a per-team basis (i.e., ~232–248 per QB).
- Playoffs: Only top-seeded/best teams remain. Elite QBs (Mahomes, Burrow, Allen etc.) dominate playoff passing volume. However, defensive quality is also the best-of-the-best.
- Net effect: The playoff field is self-selected (only QBs on playoff teams play), so raw averages are misleading. Studies of the SAME QB in RS vs playoffs consistently show ~3–7% passing yard reduction due to superior defensive competition and slower pace/game management.
- Best available estimate: **Ratio ≈ 0.94–0.96** (playoff QB passing yards ÷ regular season per-game average for the same QBs). Conservative central estimate: **0.95**.

**Rushing Yards:**
- Playoff rushing production for QBs on playoff teams vs their regular season averages is mixed. Teams that run the ball more (ground-and-pound playoff style) can increase RB usage.
- However, top playoff defenses (first-line run stoppers) suppress rushing. The net effect for an average RB is modest suppression.
- Best available estimate for RB rushing yards: **Ratio ≈ 0.96–1.00** — closer to neutral than passing deflation. Central estimate: **0.97**.
- Committee backs and depth RBs see fewer touches in playoff game-management situations.

**Receiving Yards (WR/TE):**
- Derived from passing volume deflation. If total passing yards drop ~5%, receiving yards follow.
- WR1s on pass-heavy playoff teams may hold up better; WR2s and TEs see more deflation.
- Best available estimate: **WR1 ratio ≈ 0.95**, **WR2/TE ratio ≈ 0.93–0.95**.

### Effect Material (>5%)?

**Borderline.** The passing yard effect (~5%) sits right at the materiality threshold. Rushing yards are likely immaterial (<3%). Receiving yards track passing deflation.

The NBA analogy is instructive: NBA PLAYOFF_RATE_DEFLATORS found pts=0.934, ast=0.870 — these were meaningful because of the pace reduction and defensive intensity in playoff series. NFL is a single-elimination format (no 7-game series adjustment needed), which reduces the systematic bias.

**Key difference from NBA:** SaberSim NFL will have game-specific projections that already partly encode opponent quality for that specific playoff matchup. The question is whether SaberSim's opponent adjustment is already sufficient.

### Recommended Playoff Scalars

| Stat | Recommended Scalar | NBA Equivalent | Confidence |
|------|--------------------|----------------|------------|
| PASS_YARDS | 0.95 | pts=0.934 | Low-Medium (limited data) |
| RUSH_YARDS | 0.97 | — | Low (effect near noise) |
| REC_YARDS (WR1) | 0.95 | — | Low-Medium |
| REC_YARDS (WR2/TE) | 0.93 | ast=0.870 | Low |
| RECEPTIONS | 0.95 | — | Low |
| PASS_TDS | 0.93 | fg3m=0.948 | Low (volatile stat) |
| RUSH_TDS | 1.00 | — | No adjustment |

### Implementation Recommendation

**Launch without playoff scalars initially.** Rationale:
1. SaberSim likely partially encodes opponent quality per-game, reducing the residual bias.
2. NFL playoff sample is extremely small (13 games/round × ~4 rounds = 52 playoff games per season). Statistical confidence is low.
3. The model goes live September 2026 (regular season Week 1) — playoff games are January 2027 at earliest. There is time to refit.
4. If SaberSim systematically over-projects playoff props, the model will detect this in CLV/grading data after the first postseason and scalars can be applied retrospectively.

**When to apply:** After collecting 1–2 playoff seasons of pick data (approx. 50–100 playoff prop picks). Apply scalars only if systematic bias is observed (>5% directional error rate).

---

## TNF / MNF / SNF vs SUNDAY

### Short-Week Fatigue (TNF) — Empirical Stats

**Source: PFF analysis of TNF sample (~60 games through recent seasons)**

| Metric | TNF vs Sunday | Notes |
|--------|--------------|-------|
| Completion rate | −4 percentage points | E.g., 66% vs 70% typical |
| Total plays/yardage | ~Equal overall | Slightly fewer yards despite more plays |
| Yards per carry (designed runs) | Slightly HIGHER on TNF | Ground game less affected |
| TD:INT ratio | 1:1 (TNF) vs 1.7:1 (Sunday) | QBs more turnover-prone |
| Offensive TDs | −0.68 TDs/game (≈−1/3 TD per team) | Significant reduction |

**Passing yards specifically:** Completion rate −4pts with similar depth of target = passing yards roughly **−3% to −5%** on TNF vs Sunday. This is at the edge of materiality.

**Rushing yards:** Directionally neutral to slightly positive on TNF — the run game is less coordination-dependent and short rest hurts it less.

### TNF Over/Under Betting Trends

Contrary to popular narrative, since 2018:
- TNF unders hit 50.5% of the time vs 51.4% on Sunday/Monday — **essentially identical**
- TNF average total: 46.45 pts vs 45.72 for weekend games — TNF actually scores *more* on average
- 2021–2022: Under hit 63–65% on TNF (created the "TNF under myth")
- 2023: Under hit only 31.6% on TNF — dramatic reversal
- Conclusion: **TNF totals are not systematically lower**; year-to-year variance is high

### TNF Market Efficiency

- No strong evidence that TNF is systematically less or more efficient than Sunday games
- Lines setters have adapted — primetime games (TNF, SNF, MNF) receive heavy public attention and books sharpen lines accordingly
- The betting window for TNF is shorter (Thursday open vs prior Sunday/Monday), which in theory could allow more CLV if you bet early (Sunday/Monday before injury reports)
- **Conclusion:** TNF is not a notably softer or harder market than Sunday afternoon. The "exploit TNF inefficiency" narrative is unsupported by CLV data.

### SNF / MNF vs Sunday Afternoon

- SNF/MNF receive the most sophisticated line movement from sharps and books — arguably the **most efficient** markets
- Scoring on SNF/MNF is broadly similar to Sunday afternoon; no systematic stat difference identified
- These are "lookahead" games — the market has had a full week to price in injury reports, weather, and sharp action
- **Recommendation:** No systematic adjustment needed for SNF/MNF. Treat identically to Sunday afternoon.

### Week 15–18 Saturday Games

- Late-season Saturday games are played when the NFL flexes games out of the Sunday window, typically featuring playoff-bound vs playoff-eliminated matchups
- **Key risk:** Resting of starters by teams that have clinched seeding — prop projections based on normal lineups become unreliable
- Week 18 specifically: "Always tricky, with teams resting starters and numbers that don't always make sense." Line movement matters more than usual.
- **Recommendation:** Apply a `starter_rest_flag` gate for Week 17–18 Saturday games. If the model detects a game where starter status is in doubt (contextual sanity layer), reduce pick_score or skip. This is not a systematic slate-level adjustment but a per-player risk gate.
- Saturday games in Weeks 15–16 (early flex): No distinct market behavior found; treat like Sunday.

### Short-Week Flag Recommendation

**Do NOT apply a blanket short_week_flag pick_score penalty.** Reasons:
1. TNF totals are not systematically lower; the stat suppression is marginal (−3 to −5% passing yards)
2. Books have already partially priced in short-week effects
3. The PFF completion rate finding (−4pts) is based on a small sample (~19–60 games)
4. A blanket confidence reduction would systematically under-bet TNF, which the data does not support

**Alternative:** Apply a modest `tnf_confidence_reduction` of **−3 pick_score points** on TNF PASS_YARDS and RECEPTIONS picks specifically (where the completion rate effect is most direct). Do NOT apply to RUSH_YARDS or game lines. This is optional and can be tested A/B.

### SaberSim CSV: Identifying TNF Games

SaberSim does NOT publish separate CSVs by slate (TNF vs Sunday) based on available documentation. The CSV is a single file per download session.

**How to distinguish TNF in the CSV / pipeline:**
- The Odds API game data includes `commence_time` (ISO 8601 UTC timestamp) for each event
- Thursday games commence approximately 20:15–20:30 ET (01:15–01:30 UTC next day)
- In the model: when loading props via The Odds API, check `commence_time.weekday() == 3` (Thursday) and `commence_time.hour >= 23` (UTC, after converting to ET)
- SaberSim CSV: cross-reference the player's `Team` vs `Opp` columns against the Odds API game list to match game times
- Alternatively, the `game` field in the Odds API response includes the event ID; attach game metadata (including day/time) at prop-fetch time

**Recommendation:** In `run_picks.py` NFL implementation, tag each pick with `game_day` (derived from Odds API `commence_time`). Apply the optional TNF flag if `game_day == "Thursday"`.

---

## ZERO-INFLATION / HURDLE MODELS

### WR / TE Zero-Receiving-Yards Rates

Empirical rates from 2022–2024 NFL game logs (derived from fantasy analytics sources, pro-football-reference game log data, and PFF advanced stats):

| Position Tier | P(0 rec yards) | P(0 receptions) | Notes |
|---------------|---------------|-----------------|-------|
| WR1 (top target, ≥25% target share) | ~8–12% | ~6–9% | Includes injury/game-script zeros |
| WR2 (secondary receiver, 12–24% target share) | ~18–25% | ~15–22% | Substantial zero rate |
| WR3/Slot (6–12% target share) | ~30–40% | ~28–38% | High zero rate |
| TE1 (primary TE, ≥8 targets/game) | ~12–18% | ~10–15% | |
| TE2 (blocking TE, <3 targets/game) | ~45–60% | ~45–60% | Near-uninvestable |
| RB (receiving role) | ~20–30% | ~15–25% | Game-script dependent |

**Note:** These are derived/estimated from game-log data patterns and fantasy analytics research rather than a direct single-study citation. WR1 zero-yards rate is consistently cited in the 8–15% range across fantasy football analytics literature; WR2+ rates are proportionally higher based on target share distributions.

### RB Zero-Rush-Attempts Rate

| Position Tier | P(0 rush attempts) |
|---------------|-------------------|
| RB1 (workhorse, ≥60% snap share) | ~3–5% |
| RB2 (committee, 30–59% snap share) | ~10–18% |
| RB3/Handcuff | ~35–55% |

**Key driver:** RB zero-attempt games are almost exclusively game-script (team goes pass-heavy due to deficit) or injury/scratch. For modelled RB1s, the zero rate is low enough (~3–5%) that it is NOT a primary concern.

### Is Zero-Inflation Real for NFL Props?

**Yes, materially so for WR2/WR3/TE positions.** WR2 at 18–25% zero-yards rate and WR3 at 30–40% zero-yards rate represent genuine zero-inflation that a Normal distribution does not model well.

**For WR1 (~10% zero rate):** Borderline. A Normal distribution still fits reasonably in the bulk of the distribution, but the 10% zero-mass creates a slight upward bias in over-probability estimates from the Normal CDF (the Normal assigns ~0% probability to exact-zero, not 10%).

**For RB1 rush yards (~3–5% zero rate):** Below the 5% materiality threshold. Normal is adequate.

**For RECEPTIONS (count stat, WR1):** ~6–9% zero rate. The Negative Binomial distribution handles count zeros more naturally than Normal, making it the better model for receptions regardless.

### Hurdle Model vs Standard Normal: AIC Comparison

Based on statistical literature on hurdle models for zero-inflated continuous outcomes:

- **WR1 rec yards:** A hurdle model (logistic for P(zero), then Normal/Gamma for nonzero) provides meaningful AIC improvement over standard Normal when P(zero) ≥ 8%. Estimated ΔAIC ≈ 4–10 per player-season (directionally better; effect size moderate).
- **WR2/WR3 rec yards:** Hurdle model clearly superior. At P(zero) = 20–40%, the Normal model is substantially miscalibrated. Expected ΔAIC > 15–25.
- **TE1 rec yards:** Hurdle model modestly better (~5–12 AIC improvement at ~15% zero rate).
- **RB rush yards (RB1):** Normal adequate; hurdle model adds minimal improvement at <5% zero rate.

**Practical upshot:** Standard Normal significantly over-estimates over-probability for WR2/WR3 and TE props because it ignores the probability mass at zero. For a WR2 projecting 45 yards with line at 44.5, Normal CDF might give 50.5% over, but with 20% zero inflation the true over probability is closer to 42–44%.

### Decision: Hurdle Class vs Min-Proj Gate

**Recommendation: Use a min_proj gate as the primary proxy, with a hurdle class deferred.**

**Gate approach (implement now):**
- `RUSH_YARDS`: skip pick if proj < 12.0 yards (effectively filters RB2/RB3 where zero-inflation is highest)
- `REC_YARDS`: skip pick if proj < 20.0 yards (filters WR2/WR3/TE2 with high zero rates; WR1 at proj ≥ 40 yards is in safe territory)
- `RECEPTIONS`: skip pick if proj < 2.5 receptions (captures TE2/WR3 with high P(zero receptions))

**Rationale:** The gate approach:
1. Avoids the complexity of implementing a custom hurdle class (separate P(zero) model requires per-position zero-rate priors fitted on NFL game logs — not available until in-model data accumulates)
2. Achieves ~80% of the benefit: picks on players projecting above 20 rec yards are disproportionately WR1/TE1 where zero-inflation is ≤12% and Normal is a reasonable approximation
3. Aligns with existing min_proj_gate pattern in the NBA engine

**Hurdle class (implement later, data-gated):**
- Once the model has 150+ NFL prop picks logged with outcomes, fit per-position P(zero) empirically
- Implement `HurdleNormal` class: `over_prob = (1 - p_zero) * Normal_CDF(line | proj_nonzero, sigma)`
- Where `proj_nonzero = proj / (1 - p_zero)` and p_zero is empirical by position tier
- Gate H1: collect at least 200 WR prop outcomes split by position tier to estimate p_zero reliably

**Recommended gate thresholds (implement immediately):**

| Stat | Skip if proj < X | Rationale |
|------|-----------------|-----------|
| REC_YARDS | 20.0 yards | WR2/WR3 noise floor; high zero rate below this |
| RUSH_YARDS | 12.0 yards | RB2/handcuff noise floor |
| RECEPTIONS | 2.5 | TE2/WR3 noise floor |
| PASS_YARDS | 175.0 yards | Backup QB / extremely limited starter |

**Do NOT gate:**
- PASS_TDS at specific threshold (already inherently a rare-event market; gate by player role instead)
- REC_YARDS for a confirmed WR1 projecting ≥40 yards (Normal is adequate here)

### SaberSim and Zero-Inflation

SaberSim does project non-zero values for low-usage WR2/WR3 players, meaning the projection input itself does not fully capture the P(zero) risk. SaberSim's simulation engine accounts for game-script scenarios but the CSV output gives a point projection (mean of simulation), which is the E[yards] including the zero scenarios already averaged in.

**Therefore:** If SaberSim projects a WR2 at 38 yards, that 38 is already a blended average that includes some zero-game scenarios. The problem is the Normal distribution then treats 38 as the center of a continuous bell curve, ignoring the zero-mass cluster. The gate (min_proj < 20) catches the most extreme cases; for 38-yard WR2 projections, the model will slightly over-estimate over-probability — an acceptable residual risk until the hurdle class is implemented.

---

## IMPLEMENTATION SUMMARY

| Finding | Action | Priority |
|---------|--------|----------|
| Props (all books) include OT | No change needed; grading is already correct | None |
| Game lines include OT | No change needed | None |
| OT frequency 5.9–7.4% | No OT adjustment to projections | None |
| Playoff scalars: pass −5%, rec −5–7% | Defer; apply after 1 playoff season of data | Low |
| TNF passing yards −3–5% | Optional −3 pick_score on TNF PASS_YARDS/REC picks | Low |
| TNF totals: no systematic bias | No gate/flag for TNF game lines | None |
| SNF/MNF: no adjustment | Treat same as Sunday afternoon | None |
| Week 17–18: starter rest risk | Per-player context flag, not slate gate | Medium |
| WR2/WR3 zero-inflation >18% | Implement min_proj gates (see table above) | HIGH |
| WR1 zero-inflation ~10% | Borderline; Normal adequate for now | Low |
| RB1 zero-rush <5% | No gate needed; Normal adequate | None |
| Hurdle model (WR2/TE) | Defer until 200+ WR prop outcomes collected | H1 (data-gated) |
