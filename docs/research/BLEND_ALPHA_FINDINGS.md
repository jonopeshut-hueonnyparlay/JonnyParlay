# Research: Optimal Model-vs-Market Blend Ratio for Game-Line Markets (BLEND_ALPHA)

**Date:** 2026-06-05
**Context:** `engine/run_picks.py` currently uses `BLEND_ALPHA = 0.25` — blended projection = market line + 0.25 × (SaberSim projection − market line). Applied uniformly to TOTAL, SPREAD, ML, TEAM_TOTAL, F5 across NBA/MLB/NHL/WNBA.

---

## Summary Recommendation

| Sport | Market | Recommended α (model weight) |
|-------|--------|------------------------------|
| NBA | TOTAL / SPREAD / ML | **0.20–0.25** (keep or slightly lower) |
| MLB | TOTAL / SPREAD / ML | **0.25–0.30** |
| NHL | TOTAL / SPREAD / ML | **0.25** (keep) |
| WNBA | TOTAL / SPREAD / ML | **0.30–0.40** |
| All sports | TEAM_TOTAL, F5 (derivatives) | **+0.05–0.10 over the main-line α** for that sport |

The current uniform 0.25 is well inside the defensible range and very close to the only published empirically-fit number found (nfelo's 35% model / 65% market for NFL spreads, fit on a model that nearly matched market accuracy). The single highest-value upgrade is not a different constant — it is **fitting α empirically per sport from your own logged data** (regress actual outcome vs. market line + model-market gap), since the correct α is a function of *your model's* accuracy relative to *your market's* efficiency, not a universal constant.

---

## Literature on Projection-vs-Market Blending

**1. nfelo (NFL) — the only published quantitative fit found.** nfelo regresses its Elo-based model toward the market line and reports the optimal regression weight is **65% market / 35% model**, and that "when the model and market are combined, the resulting regressed model is more accurate than either in isolation" (Brier basis). An error-weighted dynamic version (more market weight when the model has been missing worse) beats the flat 65%. Critically, nfelo "only slightly underperforms the market in predicting margin" — i.e., a *near-market-quality* model earns only 35% of the disagreement. A weaker model should earn less. ([nfelo: Using Market Regression to Improve Prediction Accuracy in the NFL](https://www.nfeloapp.com/analysis/using-market-regression-to-improve-prediction-accuracy-in-the-nfl/))

**2. Unabated (Captain Jack Andrews / Rufus Peabody ecosystem) — market-based projections.** For *props* (softer markets), Unabated recommends the inverse framing: start with **10–20% weight on the market-based projection** blended into your projection source, decreasing if you have multiple model sources. Their worked example shows blending cut a claimed 28.8% edge to 21.8% — "edges that while smaller, are also more accurate." Note the asymmetry: props are illiquid enough that they advise majority-model; they explicitly warn "the jury is still out as to which, if any, books are truly sharp for props." For liquid game lines the same logic inverts toward majority-market. ([Unabated: Introducing Market-Based Prop Projections](https://unabated.com/articles/introducing-market-based-prop-projections), [Profitable Prop Betting in 3 Easy Steps](https://unabated.com/articles/profitable-prop-betting-in-3-easy-steps))

**3. Closing line ≈ truth (the case for high market weight).** Kaunitz et al. (2017) analyzed **479,440 soccer matches** and found consensus closing implied probability is a "remarkably accurate" estimate of true outcome probability — accurate enough that betting deviations from consensus returned +3.5% with no sports model at all. ([arXiv:1710.02824](https://arxiv.org/abs/1710.02824), [MIT Tech Review summary](https://www.technologyreview.com/2017/10/19/67760/the-secret-betting-strategy-that-beats-online-bookmakers/)). Buchdahl's "Wisdom of the Crowd" method (de-vigged Pinnacle price as true probability) predicted 4.0% profit and realized 3.7% over ~18,000 bets — i.e., the sharp de-vigged price is essentially perfectly calibrated. ([football-data.co.uk: Wisdom of the Crowd PDF](https://www.football-data.co.uk/The_Wisdom_of_the_Crowd_updated.pdf), [Pinnacle wisdom comparison](https://www.football-data.co.uk/blog/pinnacle_wisdom.php))

**4. Public models vs. Vegas.** FiveThirtyEight NFL Elo: RMSE 13.57 vs. Vegas 13.10; 538 overestimated favorites by 0.93 pts vs. Vegas 0.06 pts. A respected public model is *close to* but *worse than* the market, with larger systematic biases — consistent with giving a third-party projection (SaberSim) minority weight. ([trevorData/538NFL](https://github.com/trevorData/538NFL), [Stanford Sports Analytics: CARM-Elo vs Vegas](https://stanfordsportsanalytics.wordpress.com/2017/06/18/in-search-of-a-winning-strategy-comparing-fivethirtyeight-coms-carm-elo-predictions-to-las-vegas-point-spreads/))

**5. Forecast-combination academia ("regression encompassing").** Studies of EPL betting markets find model forecasts and odds-implied forecasts "generally add information to one another" — neither fully encompasses the other — which is the formal justification for a nonzero α. In tennis, by contrast, "official player rankings and bookmaker odds together encompass most of the information," with historical data adding almost nothing. The encompassing regression itself (outcome ~ market + model residual) is the textbook way to *estimate* α. ([Reading/CentAUR: Betting markets for EPL results and scorelines](https://centaur.reading.ac.uk/89738/1/reade_singleton_scorelines.pdf), [Wilkens, tennis ML survey](https://journals.sagepub.com/doi/10.3233/JSA-200463))

**6. Calibration beats accuracy.** An NBA ML-betting study found models selected on *calibration* returned +34.69% vs. −35.17% for models selected on raw accuracy — supporting the entire purpose of BLEND_ALPHA, which is calibration (shrinking inflated edges), not point-prediction accuracy. ([ScienceDirect: ML for sports betting — accuracy or calibration?](https://www.sciencedirect.com/science/article/pii/S266682702400015X))

---

## Market Efficiency by Sport

**NBA — most efficient main lines.** Over 10,000+ games / 8 seasons, totals and spreads at the close are fair bets; the lone documented inefficiency (home dogs +10) faded in recent samples. ([The Sport Journal: NBA Gambling Inefficiencies](https://thesportjournal.org/article/nba-gambling-inefficiencies-a-second-look/)). A weak-form efficiency study found significant inefficiencies in NFL/NCAAF/NCAAB/MLB but **could not reject efficiency for NBA or NHL**. ([ECU: Weak Form Efficiency in Sports Betting Markets](https://myweb.ecu.edu/robbinst/PDFs/Weak%20Form%20Efficiency%20in%20Sports%20Betting%20Markets.pdf)). Two caveats that justify a nonzero α even in NBA: (a) early-season totals are biased — 58.2% of Week 1 games went under, with a simple under strategy returning +11.1%/game in opening week ([ScienceDirect: Learning, price formation and the early season bias in the NBA](https://www.sciencedirect.com/science/article/abs/pii/S1544612307000177)); (b) *opening* lines contain substantial biases when a star is absent, fully removed only by the close ([ScienceDirect: Player absence and betting lines in the NBA](https://www.sciencedirect.com/science/article/abs/pii/S1544612315000227)). Since your engine bets pre-close, the line you blend against is not yet fully efficient — this argues against pushing α below ~0.20.

**MLB — moderate.** Woodland & Woodland (1994, *Journal of Finance*) documented a statistically significant **reverse favorite-longshot bias** in MLB moneylines (underdogs overpriced), and season-win-total markets are demonstrably inefficient ([Wiley: Market Efficiency and the Favorite-Longshot Bias: The Baseball Betting Market](https://onlinelibrary.wiley.com/doi/10.1111/j.1540-6261.1994.tb04429.x), [Springer: heuristic-based inefficiency in MLB season wins totals](https://link.springer.com/article/10.1007/s12197-015-9322-x)). The ECU study also flags MLB as inefficient where NBA/NHL are not. Practitioner consensus: MLB totals/ML retain exploitable value due to daily volume diluting book attention. Supports α slightly above NBA: **0.25–0.30**.

**NHL — moderate, with documented totals bias.** Reverse favorite-longshot bias in moneylines (Woodland & Woodland 2001) and a persistent **under bias in totals: 54.2% under win rate on totals ≥5.5 over 5,000+ games** ([ResearchGate: NHL totals under bias](https://www.researchgate.net/publication/227410468_Market_Efficiency_and_the_NHL_totals_betting_market_Is_there_an_under_bias), [ResearchGate: Can Bettors Score on Longshots?](https://www.researchgate.net/publication/227577382_Market_Efficiency_and_Profitable_Wagering_in_the_National_Hockey_League_Can_Bettors_Score_on_Longshots)). However, the ECU weak-form study could not demonstrate NHL inefficiency. Net: roughly NBA-tier on sides, slightly softer on totals. **0.25 is fine.**

**WNBA — least efficient, but main lines are not free money.** The only peer-reviewed study (2007–2012 data) found clear behavioral biases (public over-bets best teams, especially on the road) but **"simple betting strategies do not earn statistically significant returns"** — even the thin WNBA main-line market self-corrects ([MDPI/REPEC: Market Efficiency and Behavioral Biases in the WNBA Betting Market](https://ideas.repec.org/a/gam/jijfss/v2y2014i2p193-202d35451.html)). The structural case for inefficiency is liquidity: sharp limits often ~$500, "low limits keep sharps away, depriving the market of information," softer openers, slower convergence ([betstamp: 8 Sharp Strategies to Beat the WNBA Betting Market](https://betstamp.com/education/8-ways-to-beat-wnba-betting-market), [Unabated: Five WNBA Betting Tips](https://unabated.com/articles/five-wnba-betting-tips-for-nba-and-college-bettors)). An algorithmic study generated above-market returns in WNBA (alongside NFL/NBA/NCAA) ([arXiv:1910.08858 — Beating the House](https://arxiv.org/abs/1910.08858)). Supports the highest α: **0.30–0.40**, not higher — the MDPI result warns the WNBA main-line market is more efficient than its reputation.

**Quantified efficiency gap:** No study gives a clean "WNBA lines are X% worse than NBA lines" number. The best proxies: NBA closing spreads miss actual margin by ~9–10 pts on a ~13-pt margin SD (i.e., near the theoretical noise floor — almost no signal left for a model to add) ([Boyd's Bets: ATS margin SDs](https://www.boydsbets.com/ats-margin-standard-deviations-by-point-spread/)), while WNBA books concede they spend fewer resources updating information ([MDPI study](https://www.mdpi.com/2227-7072/2/2/193)). The honest conclusion is that sport-tier α differences should be modest (±0.10), not dramatic.

---

## Market Efficiency by Market Type

**Main lines (full-game spread/total/ML) are the sharpest numbers in each sport** — highest limits, first to be bet by sharps, last to retain stale prices. Use the lowest α here.

**Derivatives (team totals, F5, halves/quarters) are systematically weaker.** Miller & Davidow (*The Logic of Sports Betting*) document that books price derivatives via formula from the main line rather than independent handicapping, that "nobody at your favorite retail sportsbook is making the numbers for every game, every day with a database and a push rate chart," and that books *know* these lines are weaker — which is why they post lower limits on them ([Logic of Sports Betting — Derivatives excerpt](https://issuu.com/sbc.global/docs/the_logic_of_sports_betting_v1_0_5/s/12292357), [Legal Sports Report excerpt](https://www.legalsportsreport.com/33079/the-logic-of-sports-betting-market-agreement-and-resistance/)). Practitioner guides concur: "derivative lines are often based on simple division or rough projections… fewer bets are placed, so lines don't adjust as quickly to sharp action" ([Predictem: Betting Derivatives](https://www.predictem.com/betting/strategy/betting-derivatives/)). **Implication: TEAM_TOTAL and F5_* can carry α ≈ main-line α + 0.05–0.10.** (Note your F5 paths currently reuse the full-game BLEND_ALPHA — a small F5-specific bump is the most literature-supported per-market change available.)

**Moneyline vs. spread:** A *Journal of Prediction Markets* (2012) study found the NFL moneyline contains finer information than the spread for the same game — backing favorites on the ML at a given spread was profitable, i.e., the spread market lags the ML slightly ([JPM: Informational Differences in NFL Point Spread and Moneyline Markets](https://www.ubplj.org/index.php/jpm/article/view/498)). Reverse favorite-longshot bias in MLB/NHL moneylines (above) is a *directional* bias (favorites slightly underpriced), better handled by your existing no-vig anchoring than by a different α. **No strong evidence supports different α for ML vs. spread; keep them equal.**

**Totals vs. spreads:** Totals show more documented situational bias (NBA early-season unders, NHL ≥5.5 unders) while spread closes are nearly unbiased. If anything, totals merit equal-or-slightly-higher α than spreads, but the effect sizes are small and situational — not worth a separate constant.

---

## Practical Guidance

1. **The blend constant is model-quality-dependent, not universal.** nfelo's 35% model weight was earned by a model that nearly matched the market's RMSE. SaberSim's game-line accuracy vs. closing lines is unpublished; until measured, 0.25 is an appropriately humble prior. ([nfelo](https://www.nfeloapp.com/analysis/using-market-regression-to-improve-prediction-accuracy-in-the-nfl/))
2. **Fit α empirically (the encompassing regression).** Per sport, regress actual game result (total points / margin) on `market_line` and `(model_proj − market_line)`. The coefficient on the gap term *is* the optimal α. This is exactly nfelo's method and the academic standard ([Reade & Singleton](https://centaur.reading.ac.uk/89738/1/reade_singleton_scorelines.pdf)).
3. **Error-weighted (dynamic) α beats a flat constant** — nfelo's error-weighted market regression beat the flat 65/35. A practical version: scale α down when |gap| is extreme (huge disagreements are usually model error — stale injury info, scheduled rest), scale up early in season when lines are documented to be softest.
4. **Timing matters.** Closing-line efficiency studies set the *floor* for α. You bet before close, against lines that still contain opening-line biases (esp. injury/absence underreaction in NBA, soft WNBA openers) — a reason not to drop α below ~0.20 anywhere.
5. **Validate with CLV, not win rate.** If a higher WNBA α produces picks that consistently beat the close, the extra model trust is justified; if CLV is flat, revert. Your CLV daemon already provides this measurement loop.

---

## Empirical CLV Analysis (engine/analyze_blend.py)

Run 2026-06-05 against data/pick_log.csv:

```
Game-line picks with CLV: 6
Decision requires n >= 50 per quintile (250 total minimum)

Quintile   Disagreement range   Mean CLV   CLV>0%     n
---------------------------------------------------------
Q1         4.56–4.56            -0.1094     0.0%     1
Q2         4.76–4.76            -0.0844     0.0%     1
Q3         4.84–4.84            -0.1189     0.0%     1
Q4         4.88–4.88            +0.0000     0.0%     1
Q5         4.92–5.04            -0.1082     0.0%     2

INCONCLUSIVE: n=6 total game-line picks with CLV (need 250+).
```

**Interpretation:** Only 6 game-line picks have CLV populated (out of 307 rows in pick_log.csv). Game-line CLV captures only when the CLV daemon closes a position on a TOTAL/SPREAD/ML/TEAM_TOTAL pick — these markets are a small fraction of overall volume (mostly props). No actionable signal.

---

## Decision

**INCONCLUSIVE — no code change.** BLEND_ALPHA remains 0.25.

**Gate:** Re-evaluate at n=100 graded game-line picks with CLV. At that point, run `python engine/analyze_blend.py` and apply the decision rule:
- CLV monotonically increases with disagreement AND n ≥ 50/quintile → consider sport-specific dict (see recommended structure below)
- Otherwise → keep 0.25

**Recommended structure if evidence supports a change** (sport-specific dict):

```python
BLEND_ALPHA = {
    ("NBA",  "main"):       0.22,   # most efficient main lines
    ("NBA",  "derivative"): 0.30,   # team totals
    ("MLB",  "main"):       0.27,   # documented RFLB + totals inefficiency
    ("MLB",  "derivative"): 0.33,   # F5, team totals — formula-priced
    ("NHL",  "main"):       0.25,
    ("NHL",  "derivative"): 0.30,
    ("WNBA", "main"):       0.35,   # thin market, soft openers
    ("WNBA", "derivative"): 0.40,
}
DEFAULT_BLEND_ALPHA = 0.25
```

If dict: replace all 9 usages of BLEND_ALPHA in `evaluate_game_lines()` with `BLEND_ALPHA.get((sport, market_class), DEFAULT_BLEND_ALPHA)` — `sport` is already the function parameter at all usage sites.

---

## Sources

- [nfelo — Using Market Regression to Improve Prediction Accuracy in the NFL](https://www.nfeloapp.com/analysis/using-market-regression-to-improve-prediction-accuracy-in-the-nfl/)
- [Unabated — Introducing Market-Based Prop Projections](https://unabated.com/articles/introducing-market-based-prop-projections)
- [Unabated — Profitable Prop Betting In 3 Easy Steps](https://unabated.com/articles/profitable-prop-betting-in-3-easy-steps)
- [Kaunitz et al. — Beating the bookies with their own numbers (arXiv:1710.02824)](https://arxiv.org/abs/1710.02824)
- [Buchdahl — Wisdom of the Crowd (football-data.co.uk)](https://www.football-data.co.uk/The_Wisdom_of_the_Crowd_updated.pdf)
- [trevorData/538NFL — 538 vs Vegas accuracy](https://github.com/trevorData/538NFL)
- [Stanford Sports Analytics — CARM-Elo vs Vegas spreads](https://stanfordsportsanalytics.wordpress.com/2017/06/18/in-search-of-a-winning-strategy-comparing-fivethirtyeight-coms-carm-elo-predictions-to-las-vegas-point-spreads/)
- [Reade & Singleton — Betting markets for EPL results and scorelines](https://centaur.reading.ac.uk/89738/1/reade_singleton_scorelines.pdf)
- [ScienceDirect — ML for sports betting: accuracy or calibration?](https://www.sciencedirect.com/science/article/pii/S266682702400015X)
- [The Sport Journal — NBA Gambling Inefficiencies: A Second Look](https://thesportjournal.org/article/nba-gambling-inefficiencies-a-second-look/)
- [ECU — Weak Form Efficiency in Sports Betting Markets](https://myweb.ecu.edu/robbinst/PDFs/Weak%20Form%20Efficiency%20in%20Sports%20Betting%20Markets.pdf)
- [Woodland & Woodland — Favorite-Longshot Bias: Baseball (J. Finance 1994)](https://onlinelibrary.wiley.com/doi/10.1111/j.1540-6261.1994.tb04429.x)
- [ResearchGate — NHL totals under bias](https://www.researchgate.net/publication/227410468_Market_Efficiency_and_the_NHL_totals_betting_market_Is_there_an_under_bias)
- [MDPI — Market Efficiency and Behavioral Biases in the WNBA Betting Market](https://ideas.repec.org/a/gam/jijfss/v2y2014i2p193-202d35451.html)
- [betstamp — 8 Sharp Strategies to Beat the WNBA Betting Market](https://betstamp.com/education/8-ways-to-beat-wnba-betting-market)
- [Unabated — Five WNBA Betting Tips](https://unabated.com/articles/five-wnba-betting-tips-for-nba-and-college-bettors)
- [arXiv:1910.08858 — Beating the House: Identifying Inefficiencies in Sports Betting Markets](https://arxiv.org/abs/1910.08858)
- [Miller & Davidow — The Logic of Sports Betting, Derivatives chapter](https://issuu.com/sbc.global/docs/the_logic_of_sports_betting_v1_0_5/s/12292357)
- [Predictem — Betting Derivatives: Finding Edges in First Half and Quarter Lines](https://www.predictem.com/betting/strategy/betting-derivatives/)
- [Journal of Prediction Markets — Informational Differences in NFL Point Spread and Moneyline Markets](https://www.ubplj.org/index.php/jpm/article/view/498)
- [Boyd's Bets — ATS margin standard deviations](https://www.boydsbets.com/ats-margin-standard-deviations-by-point-spread/)
