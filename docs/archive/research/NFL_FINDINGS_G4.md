# NFL Research Findings — G4: Game Lines (SPREAD, TOTAL, TEAM_TOTAL, ML)

**Researcher:** Agent G4
**Date:** 2026-05-21
**Sources:** Published sports analytics research, The Odds API documentation, betting market data 2022-2024
**Sections covered:** SPREAD, TOTAL, TEAM_TOTAL, ML (game lines only — props covered by other agents)

---

## SPREAD

### Empirical σ (Point Differential Standard Deviation)

**Recommended value: GAME_SIGMA["NFL"]["spread"] = 13.5**

Sources are highly consistent across multiple eras and methodologies:
- 1981/1983/1984 seasons (original academic study): σ = 13.86
- 1978–2012 overall NFL average (Pro-Football-Reference model): σ = 13.45
- 2019–2024 Thursday Night Football: σ = 14.6 (TNF is noisier — see note below)
- 2019–2024 non-TNF games: σ = 13.7

**Conclusion:** σ = 13.5 is the right central estimate for regular Sunday games. Round up to 13.86 is also defensible. Do not use TNF's 14.6 as the base — it is venue/schedule-specific.

The Normal distribution is well-validated for NFL point differentials. Multiple independent studies confirm the distribution is not statistically significantly different from Normal. Key numbers (3, 7, 10) create slight mass concentration at those values but do not break the Normal approximation materially for over/under win-probability calculations.

### Typical Line Range

Full-game NFL spreads run from pick'em (0) to approximately -14 or larger for extreme mismatches. Most spread action clusters in the 3–7.5 range. Spreads of ±10+ occur but are infrequent (<10% of games). Spreads of ±14+ are rare (≈2-3% of games).

### Vig

Standard NFL spread vig is -110/-110. Some books offer -108/-108 or even -105/-105 on reduced-juice days. BetMGM and DraftKings both run reduced-juice promotions. The model should use -110 as the baseline vig assumption.

### BLEND_ALPHA Recommendation

**Recommended: BLEND_ALPHA = 0.10 for NFL spreads (vs 0.25 in NBA/MLB)**

Rationale:
- NFL Vegas lines are extremely efficient. Academic research (arxiv 1211.4000) demonstrates betting lines are among the best predictors available for NFL game outcomes — better than most quantitative models.
- SaberSim NFL does not use custom projections (no nba_projector equivalent); it is a DFS optimizer that incorporates Vegas lines into its simulation inputs. This means SaberSim's team-total outputs are partially derived FROM the Vegas line, creating circular dependency.
- There is no empirical BLEND_ALPHA regression data available for SaberSim NFL vs actual outcomes specifically for 2022-2024. [DATA UNAVAILABLE — backtesting would require extracting SaberSim NFL game-level outputs and regressing against outcomes, which has not been published.]
- Given the circularity and the well-established efficiency of NFL lines, the model should trust the market heavily. A BLEND_ALPHA of 0.10 means: blended_spread = vegas_spread + 0.10 × (saber_spread - vegas_spread). This gives SaberSim only 10% weight.
- If you want to be more aggressive, 0.15 is defensible. Going to 0.25 (NBA/MLB level) risks over-weighting a projection source that itself pulls from Vegas.

**Flag: [CONFLICTING]** — No published regression of SaberSim NFL vs Vegas vs actual outcomes exists. The 0.10 recommendation is based on market efficiency priors and the DFS-vs-sportsbook use case mismatch. Validate empirically in shadow mode.

### Alternate Spreads Market Key

**Market key: `alternate_spreads`**

Used the same way as NBA:
```
GET /v4/sports/americanfootball_nfl/events/{event_id}/odds?markets=alternate_spreads&regions=us,us2
```

The Odds API v4 documentation confirms `alternate_spreads` is a valid market parameter for NFL (same key as NBA, not sport-prefixed). Alternate spreads require per-event endpoint (`/events/{id}/odds`), not the bulk `/sports/{sport}/odds` endpoint.

Typical alternate spread line range: approximately ±1.5 to ±17.5, in 0.5-point increments. Coverage varies by book — DraftKings and FanDuel offer the widest alternate spread menus.

### NFL Spread Dogs: Are They Lottery-Like?

**No — NFL spread dogs are NOT lottery-like in the same way as MLB/NHL outright underdogs. NFL spread dogs actually have a historical edge.**

Key data:
- Overall NFL underdogs (all spreads): 1304-1206-62 ATS over the last 10 seasons = **52% cover rate** (vs 50% breakeven)
- Last 5 seasons: underdogs 694-581-28 ATS = **54.4% cover rate**
- Double-digit dogs (+10 or more): **56% ATS win rate** historically
- Double-digit dogs in Week 1 (since 2000): 12-7 ATS = **63.2% cover rate**
- Straight-up win rate for large dogs: ~16-34% depending on size

**Critical distinction:** NFL ATS dogs cover the SPREAD frequently (52-56%), even if they rarely win outright. This is fundamentally different from MLB/NHL where you're betting outright ML on dogs. The ATS market is a zero-sum competition against the line itself — dogs cover because the spread already adjusts for most of the skill differential.

**Recommendation:** Do NOT gate NFL spread dog bets the way you gate MLB/NHL outright ML dogs. The lottery-like framing applies to ML dog bets, not ATS dog bets. An NFL +7 dog is not a lottery ticket on the spread — it is covering 52-56% historically.

**If you ever add NFL ML dog picks** (flat win bets, not ATS): then the lottery gate applies. Straight-up win rates for big dogs are only 16-34%, and ML odds on those dogs often don't compensate adequately.

For the spread market specifically: the main gate should be edge threshold and pick_score, not a blanket dog gate.

---

## TOTAL

### Empirical σ (Game Total Standard Deviation)

**Recommended value: GAME_SIGMA["NFL"]["total"] = 13.5**

The point total (combined score) has approximately the same standard deviation as the point differential. This is mathematically expected if team scores are roughly independent with similar individual variances.

From the search data:
- The total's σ at most observed total ranges is approximately 13-14 points (Boyd's Bets analysis of hundreds of games per total bucket)
- The Studocu/homework example cites NFL total σ ≈ 9.3 points for individual team score distributions (see TEAM_TOTAL section), which implies combined total σ ≈ 13.2 (√(9.3² + 9.3²) ≈ 13.2) — consistent with 13.5

**Note on TNF:** TNF total σ = 14.6 vs Sunday's 13.7. If you add a short_week_flag for TNF, you could use σ = 14.5 for TNF games. This is optional refinement.

### Typical Total Range

- 2022: average total ≈ 44.2 points per game set vs 44.0 actual
- 2023: average total ≈ 43.1 set vs 43.8 actual
- 2024: higher scoring, overs hit 53.7% of the time (suggesting books lagged the upward trend)
- Typical range: **42–51 points**, with most lines clustered in 43–47 range
- Low-total games (dome-less cold weather, defensive matchups): can go to 37-40
- High-total games (dome, both teams top-10 offense): can go to 54-58

### Alternate Totals Market Key

**Market key: `alternate_totals`**

Same structure as `alternate_spreads`:
```
GET /v4/sports/americanfootball_nfl/events/{event_id}/odds?markets=alternate_totals&regions=us,us2
```

Coverage: DraftKings and FanDuel offer the most alternate total lines. BetMGM and Caesars also offer alternate totals but with narrower menus.

### Weather / Blowout Considerations

Weather-driven total suppression is real and pre-game. Wind >15 mph meaningfully suppresses passing efficiency; precipitation has a secondary effect. The pre-game total already partially encodes weather when set Sunday morning, but early-week lines may not. For the model running on game day, the line itself is the best weather-adjusted anchor — BLEND_ALPHA keeps you close to it.

The blowout sigmoid question for totals: if game script creates a blowout, public may bet overs in hope of garbage-time scoring. Pre-game, this is not a concern — the model only needs pre-kickoff projections. No post-halftime adjustment needed for a props model.

---

## TEAM_TOTAL

### Empirical σ (Single Team Points Standard Deviation)

**Recommended value: GAME_SIGMA["NFL"]["team"] = 9.5**

Derivation:
- Individual team score per game: mean ≈ 21-24 points, σ ≈ 9.3 points (Chegg/Studocu homework source cites σ = 9.3 for individual NFL team scores, consistent with academic literature)
- This is consistent with GAME_SIGMA["NFL"]["total"] = 13.5 when you assume rough independence between teams: √(9.3² + 9.3²) ≈ 13.2 ≈ 13.5
- Comparison: MLB team total σ is ~2.7 runs; NBA team score σ is ~11 points. NFL at 9.3-9.5 is reasonable for a sport where teams score 15-45 points.

**Note:** [CONFLICTING] The Chegg source is a textbook problem (σ = 9.3 for individual scores), not a peer-reviewed empirical fit. No direct 2022-2024 team total σ calculation was found in open literature. 9.5 is the recommended estimate pending empirical validation.

### Typical Team Total Range

- Typical NFL team total line: **20.5 to 27.5 points**
- Minimum (defensive mismatch, bad weather): ~14.5-17.5
- Maximum (elite offense vs weak defense, dome): ~30.5-34.5
- Most team totals cluster in the 22.5-26.5 range

### Market Key (The Odds API)

**Market key: `team_totals`**

The Odds API documentation lists `team_totals` as a valid market for NFL. Access via:
```
GET /v4/sports/americanfootball_nfl/events/{event_id}/odds?markets=team_totals&regions=us,us2
```

**Coverage:** [DATA UNAVAILABLE — specific CO-legal book coverage matrix for NFL team totals requires live API testing. Based on NBA/MLB experience: DraftKings and FanDuel are most likely to offer; BetMGM is spotty; Caesars/Fanatics/theScore Bet coverage uncertain for NFL specifically.]

Anecdotally, NFL team totals are less universally offered than NBA team totals. Expect 4-6 CO-legal books to carry them consistently, not all 18.

### BLEND_ALPHA for Team Totals

**Recommended: BLEND_ALPHA = 0.10 (same as spread)**

Same reasoning as spread — Vegas team totals are derived from the same efficient market. SaberSim NFL team scoring projections may have some independent signal from injury/weather adjustments, but the circularity concern remains. 0.10 is conservative and appropriate.

Blend formula remains:
```python
blended_team = team_total_line + 0.10 * (saber_team - team_total_line)
```

If SaberSim does not export a team total field in the NFL CSV, derive it from the game total line + implied spread: `team_total_home = (total + spread) / 2`.

---

## ML (Moneyline)

### Appropriate σ for Win Probability

**Recommended: GAME_SIGMA["NFL"]["ml"] = 13.5 (same as spread)**

The win probability formula is:
```python
win_prob = normal_cdf(0, blended_margin, sigma=13.5)
```

This is the standard NFL spread-to-win-probability conversion used by Pro-Football-Reference, Boyd's Bets, and most quantitative models. The formula:
- `blended_margin` = projected point margin (positive = home team favored)
- σ = 13.5 = the standard deviation of NFL point differentials

Example conversions at σ = 13.5:
- Spread -3 → win_prob ≈ 0.586
- Spread -7 → win_prob ≈ 0.698
- Spread -10 → win_prob ≈ 0.771
- Spread -14 → win_prob ≈ 0.851
- Spread -20 → win_prob ≈ 0.931

### Does Normal Work Across the Full NFL ML Range (-350 to +300)?

**Mostly yes, with a known overestimation bias for extreme favorites.**

Findings:
- At spreads ≤ 10 points, Normal CDF with σ = 13.5 closely matches empirical win rates.
- At spreads of 10+ points, favorites win over 80% of the time empirically — consistent with the Normal model (~0.77-0.85 range).
- For extreme favorites (≥90% implied probability): teams with 90%+ implied win probability have won 86% of their games over the past 7 years. This suggests the Normal model **overestimates** win probability by ~4 percentage points for extreme spreads.
- The practical implication: a -350 ML implies ≈ 77.8% true probability. The Normal spread model at the equivalent spread (≈ -12 to -13) gives 82-85%. The market is slightly more pessimistic about extreme favorites than the Normal model.

**Recommendation:** For ML picks in the -300 to -400 range, apply a small correction: cap the model's win_prob at the implied ML probability (after removing vig) rather than using the Normal CDF output directly. This prevents the model from finding spurious edge by over-projecting extreme favorites.

For practical purposes, a Platt-scaled version of win_prob would absorb this bias if fitted on NFL data. Since NFL data won't exist at launch, use the ML implied probability as a ceiling check.

### Is NFL ML Consistently Offered?

**Yes** — all 18 CO-legal books (DraftKings, FanDuel, BetMGM, Caesars, BetRivers, Bet365, Fanatics, theScore Bet, Hard Rock, etc.) offer NFL ML for every game. It is the most universally available market. No CO-legal book consistently skips NFL ML.

Market key in The Odds API: `h2h`
```
GET /v4/sports/americanfootball_nfl/odds?markets=h2h,spreads,totals&regions=us&apiKey=...
```

### NFL ML vs Fixed-Spread Equivalent

**NFL does NOT have a fixed-spread runline equivalent.** Unlike MLB (±1.5 runline) or NHL (±1.5 puck line), NFL has no standard fixed-spread ML variant.

The model should treat NFL ML exactly as NBA ML:
- Use `h2h` market as the anchor
- Remove vig from both sides to get no-vig implied probabilities
- Use normal_cdf(0, blended_margin, σ=13.5) as the model probability
- Compare model prob vs implied prob to compute edge

No fixed-spread equivalent needs to be handled.

### NFL ML Odds Range

NFL ML ranges from approximately -350 (extreme home favorite, large spread) to +300 (heavy road underdog). Most games are in the -200 to +175 range. Unlike NBA where -500 to +400 ranges occur for blowout mismatches, NFL rarely exceeds ±350 because:
1. NFL has a 13.5-point σ vs NBA's larger σ; the high variance keeps probabilities from being too extreme
2. The NFL parity structure (salary cap, draft) limits extreme skill differentials

For KILLSHOT purposes: NFL ML picks in the -200 to +110 range represent approximately spreads of -3 to -8. These are the "confident favorite" games where the Normal model is well-calibrated and the ML edge is most actionable.

---

## Summary Table

| Parameter | Value | Confidence |
|-----------|-------|------------|
| GAME_SIGMA["NFL"]["spread"] | 13.5 | High — consistent across 40+ years of research |
| GAME_SIGMA["NFL"]["total"] | 13.5 | High — mathematically derived from team σ and spread σ |
| GAME_SIGMA["NFL"]["team"] | 9.5 | Medium — consistent with derivation but not directly measured 2022-2024 |
| GAME_SIGMA["NFL"]["ml"] | 13.5 | High — same as spread by design |
| BLEND_ALPHA (spread/total/team_total/ML) | 0.10 | Medium — conservative, justified by market efficiency and SaberSim circularity |
| Alternate spreads market key | `alternate_spreads` | High — confirmed in Odds API v4 docs |
| Alternate totals market key | `alternate_totals` | High — confirmed in Odds API v4 docs |
| Team totals market key | `team_totals` | High — listed in Odds API market registry |
| ML market key | `h2h` | High |
| Spread market key | `spreads` | High |
| Total market key | `totals` | High |
| Typical total range | 42–51 pts | High — 2022-2024 data confirms 43-44 avg |
| Typical team total range | 20.5–27.5 pts | Medium |
| Standard vig (spread/total) | -110/-110 | High |
| NFL spread dogs lottery-like? | No (ATS context) | High — dogs cover 52-54% ATS |
| Normal distribution valid for ML? | Yes, with ceiling check for extreme favorites | High |

---

## Implementation Notes

1. **BLEND_ALPHA = 0.10** — implement as a separate `NFL_BLEND_ALPHA = 0.10` constant, distinct from the 0.25 used in NBA/MLB. This is the most important deviation from the current cross-sport default.

2. **Sigma 13.5 across all NFL game line types** — use the same σ for spread, total, team_total, and ML win probability. They should be consistent.

3. **Alternate markets require per-event endpoint** — `alternate_spreads` and `alternate_totals` cannot be fetched from the bulk `/sports/{sport}/odds` endpoint. They require `/events/{event_id}/odds`. The model's existing `SPORT_ALT_MARKET` dict approach should work as long as it builds per-event URLs.

4. **NFL ML ceiling check** — for any ML pick where model win_prob > (no-vig implied prob + 0.05), cap at (no-vig implied + 0.05) before edge calculation. This prevents the Normal model's overestimation of extreme favorites from generating phantom edge.

5. **Team totals fallback** — if team total line is unavailable for a given game/book, derive from: `team_total = (game_total ± spread) / 2`. This is the standard market convention.

6. **NFL spread dogs** — do NOT implement a blanket gate against ATS dog picks. The data shows dogs are profitable ATS historically. Gate by edge, pick_score, and win_prob as with favorites.
