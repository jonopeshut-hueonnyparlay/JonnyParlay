# MLB Deep Investigation — Research Agenda

**Created:** 2026-05-14  
**Purpose:** Complete research brief for fixing every MLB market. Each section contains all questions needed to reach a fix/kill decision.  
**Use in session:** Load this file, then run research sessions in order or in parallel. Every question must be answered before writing code.

---

## Shadow Log Summary (Apr 12 – May 13, 3268 graded picks)

| Stat | WR | P&L | n | Avg Odds | Break-even | Verdict |
|------|----|-----|---|----------|------------|---------|
| TB | 43.8% | -93u | 714 | -37 (mixed) | ~52% | Critical |
| HRR (1.5) | 48.0% | -53u | 1810 | +30 | 77.2% | Critical |
| HRR (0.5) | 57.4% | — | 129 | -122 | 55.0% | Profitable |
| NRFI | 28.9% | -41u | 211 | +100 | 50.1% | Critical |
| K | 44.3% | -14u | 79 | +58/+40 at 4.5/5.5 | 63-71% | Losing |
| OUTS | 46.2% | -12u | 93 | -18 (under) | ~52% | Losing |
| F5_ML | 30.0% | -4u | 10 | +41 | — | Losing |
| ER | 14.3% | ~0u | 7 | legacy | — | Legacy/dead |
| TEAM_TOTAL | 51.6% | +2u | 124 | — | ~52% | Marginal |
| HA | 52.9% | +4u | 17 | — | — | Inconclusive |
| ML_FAV | 54.2% | +4u | 48 | -113 | 53.1% | Marginal |
| F5_TOTAL | ~80% | +1u | 5 | — | — | Inconclusive |
| F5_SPREAD | 75.0% | +3u | 4 | — | — | Inconclusive |
| ML_DOG | 33.3% | -2u | 3 | — | — | Inconclusive |
| HITS | 0 picks | — | 0 | — | — | Never fires |
| YRFI | 0 picks | — | 0 | — | — | Never fires |
| SPREAD | 0 picks | — | 0 | — | — | Never fires |

**Root cause hypotheses:**
- TB/HRR: Wrong distribution (Normal for a discrete non-negative right-skewed stat). At HRR 1.5, market requires 77% WR — model overestimates beyond even that, actual is 48%.
- NRFI: Model only uses pitcher quality, ignores team offense. Market at +100 (50% implied) is far more accurate than our model at ~70% estimate.
- K: SaberSim K projections systematically below actual. At 4.5/5.5 lines, model bets under at +58/+40 odds (market says over is more likely). Market is correct.
- OUTS: IP variance is high and unpredictable pre-game. Model sigma too tight.

---

## TB (Total Bases)

**Current config:** Normal dist, mult=1.20, min=1.5. T2, min_edge=5%. All overs, all line 1.5.

### Distribution
1. Normal distribution for TB — is this correct? TB is a discrete non-negative integer (0,1,2,3,4+) with a spike at 0 and right-skewed tail. Pull actual empirical TB distribution from MLB Stats API (2024-25 season, all qualified batters).
2. Which distribution fits best — Zero-Inflated Poisson, Negative Binomial, or mixture model? Fit each and compare AIC/BIC.
3. What are the fitted parameters (λ, r, p, zero-inflation weight) from the best-fit distribution?
4. With the correct distribution, what is P(TB > 1.5) for an average batter projecting 1.5 TB? Compare to Normal's estimate. This is where the overcalculation is happening.
5. Does the correct distribution ever produce under edge at realistic lines? Should the model even look for TB unders?

### Projection inputs
6. TB is derived in parse_csv as singles + 2×doubles + 3×triples + 4×HR. Are SaberSim's component projections individually unbiased vs actuals?
7. Is the sum-of-components a valid TB projection? Does it ignore within-game component correlation (a player who hits a double is more likely to also record a single in the same game)?
8. Systematic bias: compare SaberSim TB proj vs actual TB outcomes across all graded picks. What is mean error and direction?

### Sigma
9. mult=1.20 note says "was 41% UNDER real variance" — what dataset was this calibrated on? Is it still valid?
10. With a correct non-Normal distribution, sigma concept doesn't apply. What replaces it for G14 clearance?

### Market structure
11. All 714 picks at line 1.5. Is TB line 2.5 consistently available from CO-legal books?
12. TB line 0.5 — is this offered? HRR 0.5 is profitable; would TB 0.5 behave similarly?
13. Are there books consistently pricing TB better than others?

### Situational factors
14. Does ballpark (Coors Field, Oracle Park) significantly affect TB probability? Does SaberSim encode this, or is it missing from the model?
15. Does opposing pitcher FIP/ERA factor into TB projection or is it purely batter-driven?

### Gate/tier
16. G13B sets WP≥60% for TB. With a corrected distribution model, does this gate remain necessary or become redundant?
17. G14 (z≥0.10 clearance) — how does this apply if distribution changes from Normal?
18. T2 (min_edge=5%) — is this the right tier with a correct model?

### Kill/fix criteria
19. If corrected distribution produces P(TB > 1.5) that matches actual ~44%, the model will stop finding over edge at line 1.5. Should we then pursue line 2.5 instead?
20. What n of corrected picks at what WR validates the fix before going live?

---

## HRR (Hits + Runs + RBIs)

**Current config:** Normal dist, mult=0.75, min=1.3. T1, min_edge=3%. Almost all overs. Line 1.5 = disaster (-53u); line 0.5 = profitable (57.4% > 55% break-even).

### Distribution
1. Normal distribution for HRR — same problem as TB. HRR is a discrete non-negative integer. Pull actual empirical HRR distribution from Stats API.
2. Which distribution fits best? Fit per line bucket (0.5, 1.5, 2.5) — the distribution may have different shape at different lines.
3. At line 1.5: market requires 77.2% WR (avg odds +30). Our model estimates probability above 77%, actual is 48%. What does the correct distribution give for P(HRR > 1.5) at a typical batter projection of ~2.0? This is the core miscalculation.
4. At line 0.5: 57.4% actual WR vs 55% break-even — profitable. What does the correct distribution give for P(HRR > 0.5)?

### Projection inputs
5. HRR = H + R + RBI from SaberSim components. Are H, R, RBI projections individually unbiased?
6. H, R, and RBI for the same player are correlated within a game. Does the model account for within-game correlation or does it sum independent projections?
7. Does batting order position matter? Leadoff = high R/low RBI, cleanup = high RBI/low R opportunity. Does SaberSim already encode this?
8. Systematic bias: mean SaberSim HRR proj vs actual across 1953 graded picks. Direction and magnitude?

### Sigma
9. mult=0.75, min=1.3 — what data was this calibrated on?
10. With a correct distribution, what replaces sigma for the 1.5 line?

### Market structure
11. HRR 0.5: n=129, profitable. Is this consistently available? Which books offer it?
12. HRR 1.5: avg odds +30 (market implies 77% probability). Is this pricing consistent across books or does it vary?
13. HRR 2.5: n=14, 57.1% WR, avg odds -9. Is 2.5 consistently available?

### Situational factors
14. Does opposing pitcher quality factor into HRR probability in the current model?
15. Does game run environment (high-scoring game vs pitcher's duel) affect HRR independent of the player projection?
16. Park factor for HRR?

### Gate/tier
17. G13B (WP≥55%) — does this gate help meaningfully at line 1.5, or does the corrected distribution make it redundant?
18. HRR T1 (min_edge=3%) — with corrected model, does the 3% threshold still make sense?
19. STAT_CAP=2 for HRR. Does this apply in shadow mode? With 63 HRR picks/day logged, is the cap actually enforced at runtime?
20. Should HRR be tiered separately by line bucket — different min_edge for 0.5 vs 1.5 vs 2.5?

### Kill/fix criteria
21. With corrected distribution, will line 1.5 still produce picks? Or should line 1.5 be gated out and only 0.5/2.5 pursued?
22. Is HRR at 0.5 profitable enough to stand alone as the primary HRR market?

---

## HITS

**Current config:** Poisson, mult=0.90, min=0.7. T1B. 0 picks in 31 days.

### Why zero picks
1. G8 bans HITS at line ≤1.5. HITS market lines are predominantly 0.5 and 1.5. Does G8 effectively kill all HITS picks?
2. Does the Odds API consistently offer batter_hits at line 2.5 or higher across CO-legal books?
3. At line 2.5, does any SaberSim HITS projection clear G14 (z≥0.10 clearance with Poisson)?
4. T1B note says "unders 3.5+ only / low volume." Is there code enforcing this? If HITS unders must be at 3.5+, and lines are max 2.5, that kills all picks.

### Distribution
5. Poisson for HITS — is this right? HITS per game is a count stat (0, 1, 2, 3...) with independent at-bats. Poisson seems appropriate. Validate with empirical data.
6. What is the actual empirical distribution of HITS per game from Stats API?

### Market structure
7. Pull actual Odds API HITS market — what lines are offered across CO-legal books? Is 2.5 consistently available?
8. What vig do books charge on HITS markets?

### Kill/fix criteria
9. If HITS lines are predominantly 0.5/1.5 and G8 bans both — is HITS dead in the current architecture? Options: (a) remove from PROP_MARKETS entirely, (b) remove G8 for HITS and validate 0.5/1.5, (c) wait for 2.5 line availability.
10. What would a HITS 0.5 over WR look like if G8 were lifted? Is there genuine edge there?

---

## K (Strikeouts)

**Current config:** Poisson, mult=0.45, min=1.5. T1, min_edge=3%. 76/79 are unders. At line 4.5/5.5, market prices under at +58/+40 (underdog) — we bet under and lose.

### Distribution
1. Poisson for K — is this correct? Or is K overdispersed (some starts dominant 8+K, some poor 1-2K)? Pull empirical K distribution from Stats API and fit Negative Binomial vs Poisson. Compare AIC.
2. If K is overdispersed (Negative Binomial), what are the r and p parameters?

### Projection inputs
3. The model almost exclusively finds K under value — SaberSim K projections are systematically below actual K. Measure: compute mean(SaberSim K proj) - mean(actual K) across all graded K picks. What is the bias magnitude and direction?
4. Is the bias consistent across line buckets (3.5, 4.5, 5.5, 6.5+)?
5. K is a function of IP. Does SaberSim project K assuming full-game completion, or does it model partial outings?
6. Modern MLB has heavy bulk/opener usage. Does SaberSim distinguish starter vs bulk reliever K projections?
7. If K bias is purely IP-related (pitcher goes shorter than projected), can a calibration deflator fix this similar to NBA PLAYOFF_RATE_DEFLATORS?

### Sigma
8. SIGMA["K"] = mult=0.45, min=1.5 — used for G14 clearance only (since K is Poisson). Is min=1.5 the right floor?

### Market structure
9. What vig does the K market carry at each line bucket?
10. Does opposing lineup strikeout rate (team K%) factor into market lines in a way that should be incorporated?
11. Which CO-legal books offer pitcher_strikeouts most consistently?

### Situational factors
12. Does days of rest or scheduled pitch count limit affect K outcomes in a predictable way from pre-game SaberSim data?
13. Does park or weather affect K rates meaningfully?

### Gate/tier
14. Should there be a minimum K line gate (e.g., only evaluate K at line ≥5.5) to avoid the worst-performing low-line picks?
15. Should K over and K under be evaluated separately? K over at 0/3 WR suggests overs should be gated.
16. K is T1 (min_edge=3%) — appropriate given the SaberSim projection bias?

### Kill/fix criteria
17. If SaberSim K is biased low by X (measured above), can a multiplier correction fix this?
18. Or is the bias non-uniform (varies by pitcher type, line level) requiring a more complex fix?
19. Minimum data requirement to validate fix before live deployment.

---

## OUTS (Outs Recorded)

**Current config:** Normal, mult=0.22, min=3.0. T2, min_edge=5%. 80/93 unders. Under at avg odds -18 (near even money), winning 45%.

### Distribution
1. Normal for OUTS — is this right? OUTS = IP × 3. IP is highly variable (4 IP to 7+ IP) and may be bimodal (quality start vs early hook). Pull empirical OUTS distribution from Stats API.
2. Is the OUTS distribution bimodal? If so, Normal fails completely. What's the correct model?
3. How much of OUTS variance is predictable from pre-game data vs random (manager hook, game script, injury)?

### Projection inputs
4. How does SaberSim project OUTS — IP column directly, or derived from innings projection?
5. Systematic bias: mean SaberSim OUTS proj vs actual across graded picks.
6. What fraction of IP variance can be explained by pre-game variables (pitcher quality, opponent, park)? Estimate R² from regression.
7. Does bullpen workload or availability affect actual IP in a way that SaberSim doesn't capture?

### Sigma
8. mult=0.22, min=3.0. What is the actual standard deviation of OUTS per start from Stats API data? If actual σ is 4-5 outs (not 3), G14 clearance threshold is wrong and sigma-based edge is inflated.
9. With correct sigma, how many of the 93 picks would have been filtered by G14?

### Market structure
10. Is pitcher_outs consistently available across CO-legal books?
11. What line range does the market typically offer (14.5, 17.5, 20.5)?
12. OUTS overs (53.8% WR, n=13) are outperforming unders (45.0%, n=80). Are overs at a different typical odds level?

### Situational factors
13. Do any pre-game signals predict IP reliably: starter vs bulk/opener designation, team's bullpen situation, game importance, or schedule density?

### Gate/tier
14. Should OUTS unders be gated out entirely given 45% WR? Or is the model fixable?
15. Should OUTS overs be separately tiered/evaluated given their higher WR?
16. Is OUTS in the right correlation group with K and HA (PITCHER_STATS)? Is G11 dedup preventing correlated losses?

### Kill/fix criteria
17. If actual IP variance is dominated by unpredictable factors (game script, manager), OUTS may be fundamentally ungradable pre-game. Kill vs keep decision depends on what % of variance is predictable.
18. If kept, should OUTS be restricted to overs only?

---

## HA (Hits Allowed)

**Current config:** Normal, mult=0.50, min=2.5. T1B (note says "unders 3.5+ only"). All 17 picks are overs. n=17 insufficient.

### Distribution
1. Normal for HA — comment says "moved from Poisson (15% overdispersed)." Is Normal actually better? Pull empirical HA distribution from Stats API and re-validate.
2. Same IP-dependency issue as K and OUTS. Is HA capped by actual innings pitched in the model?

### T1B discrepancy
3. T1B comment says "unders 3.5+ only / low volume." All 17 shadow picks are overs. Is there code enforcing unders-only, or is the comment misleading? If overs are allowed, why are they in T1B?
4. Pull the code path that assigns HA to T1B and check if any direction restriction is enforced.

### Projection inputs
5. How is HA projected from SaberSim? Direct column or derived?
6. Systematic bias: SaberSim HA proj vs actual across graded picks.
7. Does opposing lineup quality affect HA projection in the model?

### Sigma
8. mult=0.50, min=2.5 — what data was this calibrated on? What is actual σ of HA per start from Stats API?

### Market structure
9. Is pitcher_hits_allowed consistently available? With n=17 in 31 days, why so few picks — market thin or gates filtering?
10. What lines does the market offer?

### Situational factors
11. Does park factor affect HA (Coors Field dramatically inflates hits allowed)?
12. Should park factor be incorporated?

### Kill/fix criteria
13. n=17 too small to conclude. Resolve T1B directional discrepancy first, then accumulate data.
14. What data volume is needed before evaluating HA?

---

## ER (Earned Runs)

**Current config:** Not in PROP_MARKETS, not in SIGMA. 7 picks from April 14-15 only. T2 in log.

### Origin
1. ER is not in PROP_MARKETS or SIGMA — how were these 7 picks generated? Find the code path. Was there an ER evaluation block that was subsequently removed?
2. These picks are T2 — what tier logic was assigning ER to T2?

### Market availability
3. Does any CO-legal book currently offer a pitcher_earned_runs prop market in the Odds API?
4. If the market exists, should ER be added to PROP_MARKETS?

### Model
5. What distribution and sigma should ER use? ER has all the IP-dependency problems of OUTS/K/HA plus noise from unearned run classification (errors).
6. Is ER correlated with K, OUTS, HA enough to require G11 dedup inclusion in PITCHER_STATS?

### Kill/fix criteria
7. If ER market no longer exists in the API, formally remove any residual code paths.
8. If ER market is available, is it projectable with SaberSim data, or does the earned/unearned distinction make it too noisy?

---

## NRFI

**Current config:** BASE_SCORING_RATE=0.194, FIP constant 3.20, 60/40 FIP/ERA blend. Scoring prob clipped [0.05, 0.45]. T3 (but 201/211 picks logged as T2). Avg odds +100 (even money). Actual WR 28.9%.

### Base rate
1. BASE_SCORING_RATE=0.194 derived as 1-√0.65 (baseline NRFI=65%). What is the actual 2025 first-inning NRFI rate from MLB Stats API? Pull inning-by-inning data.
2. Does first-inning NRFI rate vary by team, ballpark, or game context in a way the model should encode?

### Formula
3. P(NRFI) = (1-p_away)(1-p_home) — assumes the two scoring events are independent. Is this valid? Test empirically.
4. The market at +100 (50% implied) is far more accurate for these specific games than our model. The market incorporates team offense; we don't. What offensive metrics drive first-inning scoring probability beyond pitcher quality alone?
5. Scoring prob clipped at 0.45 max — why this ceiling? If a very weak pitcher faces an elite offense, should P(team scores) exceed 45%? What does empirical data show?

### FIP calibration
6. FIP constant 3.20 — what is the correct FIP constant for 2025 MLB? (FIP constant = lgERA - FIP_component/IP, recalculated each season.)
7. 60/40 FIP/ERA blend — is this empirically justified or arbitrary? Test FIP-only vs ERA-only vs blend on historical first-inning data.
8. avg_er_per_ip = 0.46 ("2025 ERA ≈ 4.16") — what is the actual 2025 MLB ERA through current date?

### Missing inputs
9. Does SaberSim MLB CSV contain any team offensive quality data (team wOBA, OPS+, lineup projection, run expectancy)?
10. If not from SaberSim, what public API provides real-time team offensive quality pre-game? (Statcast, FanGraphs, Baseball Reference?)
11. If team offense data is obtainable, what is the correct updated formula for p_team_scores that incorporates both pitcher quality and offensive quality?

### Tier discrepancy
12. NRFI is T3 in code (min_edge=6%) but 201/211 shadow picks are logged as T2. Trace the code path — is there a bug in NRFI tier assignment?

### Kill/fix
13. If team offense data is unavailable pre-game at scale, NRFI model is structurally incomplete. Should it be disabled until data is available?
14. If fixable: what sample of corrected NRFI picks at what WR validates the fix?

---

## YRFI

**Current config:** T3, min_edge=8%. 0 picks in 31 days.

1. YRFI never fires because NRFI model overestimates P(NRFI) → underestimates P(YRFI) → YRFI never shows edge. Confirm this is the cause.
2. If NRFI model is corrected, will YRFI naturally produce picks at 8% min edge? Or is there a separate calibration needed?
3. Is YRFI market (totals_1st_1_innings over 0.5) consistently available at reasonable odds?
4. After NRFI fix, validate that YRFI picks emerge and test their WR before going live.

---

## TEAM_TOTAL

**Current config:** Uses saber_team directly, BLEND_ALPHA=0.25, sigma=3.0. T2, min_edge=5%. All 124 picks are overs. +2.30u.

### Model
1. With BLEND_ALPHA=0.25, model = line + 0.25×(saber_team - line). SaberSim must systematically project ABOVE market lines — that's why all 124 picks are overs. What is mean(saber_team - market_line) across these 124 picks?
2. Is 0.25 the right BLEND_ALPHA for MLB team totals specifically? Has it been empirically validated?
3. sigma=3.0 for team totals — what is the actual standard deviation of MLB team runs scored per game from Stats API? Is 3.0 correct?
4. +2.30u on 124 picks at ~52.4% break-even, actual 51.6%. Is this genuinely profitable or within noise? Compute confidence interval.

### Missing signal
5. Does saber_team account for opposing starting pitcher quality? If not, the model over-projects team runs against elite starters and under-projects against weak ones.
6. Does the model apply any park factor? If SaberSim encodes park in saber_team, does BLEND_ALPHA correctly propagate it?
7. Weather adjustment (wind, temperature, humidity)? Any available pre-game?

### Direction gap
8. Zero under picks in 31 days. SaberSim appears always above market line (hence all overs qualify). Is this accurate? Compute distribution of (saber_team - market_line) — how often is it negative?
9. Should model be able to find under value? If saber_team is consistently high, that's a SaberSim bias issue, not a model issue.

### Kill/fix
10. If TEAM_TOTAL is profitable (needs larger n to confirm), what improvements would increase edge?
11. Is the market efficient enough that 25% SaberSim signal produces real edge, or is this statistical noise?

---

## ML_FAV

**Current config:** sigma=6.0, BLEND_ALPHA=0.25. T2, min_edge=5%. Avg odds -113, break-even 53.1%, actual WR 54.2%. n=48.

### Model
1. sigma=6.0 for win probability via normal_cdf(0, team_margin, 6.0) — what is the actual standard deviation of MLB full-game run differentials? Pull from Stats API (2024-25). Is 6.0 correct?
2. With BLEND_ALPHA=0.25, margin = market_margin + 0.25×(saber_margin - market_margin). Is model adding signal beyond the market, or is 75% anchor doing all the work?
3. 54.2% WR vs 53.1% break-even on n=48 — is this statistically significant? What n is needed to confirm edge at 90% confidence?

### Missing signal
4. Does the model incorporate home field advantage explicitly? MLB HFA is ~54% historically — is this in the projection?
5. Does pitching matchup quality (starter FIP differential) factor in beyond the Vegas line?

### Kill/fix
6. With n=48, this cannot be confirmed as profitable. Track to n=200 before conclusions.
7. Is there any model improvement (HFA, pitcher differential) that adds measurable signal?

---

## ML_DOG

**Current config:** T3, min_edge=8%. n=3, 33.3% WR, -2.25u.

1. n=3 is completely insufficient. What are the actual odds on these 3 picks and are they above break-even?
2. Is there a meaningful edge signal for ML dogs in MLB beyond what's in the Vegas line?
3. Should ML_DOG minimum edge be raised to 12%+ given underdog variance?
4. Track to n=100+ before any conclusions about ML_DOG.

---

## F5_TOTAL

**Current config:** proj = game_total × 0.51, then BLEND. F5_SIGMA["total"]=2.6. T2. n=5.

1. Is 0.51 (F5 ≈ 51% of full-game runs) empirically correct? Pull 2024-25 first-5-inning run data vs full-game totals from Stats API.
2. F5_SIGMA=2.6 — what is actual σ of F5 run totals from Stats API?
3. Does starter confirmation quality affect F5 accuracy? What % of F5 picks had starters who actually pitched?
4. Is F5_TOTAL consistently available across CO-legal books?
5. n=5 insufficient. Validate 0.51 scaling and sigma, then accumulate data.

---

## F5_ML

**Current config:** f5_team = team_proj × 0.54, sigma=F5_SIGMA["spread"]=2.5. T2 favs/T3 dogs. n=10, 30% WR.

1. Why is the scaling 0.54 for F5_ML vs 0.51 for F5_TOTAL? These should be consistent. Which is correct?
2. sigma for F5_ML uses F5_SIGMA["spread"]=2.5. Should F5 ML win probability use a different sigma than F5 spread coverage? (They measure different things.)
3. Late picks (May 12): 4 consecutive losses at +155 odds. Is the model finding dog value that doesn't exist?
4. With n=10 and a mix of fav/dog results, what is the break-even WR at actual average odds? Are we genuinely losing?
5. Is F5_ML consistently available across books?

---

## F5_SPREAD

**Current config:** raw_f5_margin = (t_proj - o_proj) × 0.51, blended to market. sigma=2.5. T2. n=4.

1. Why does F5_SPREAD use 0.51 but F5_ML uses 0.54? Resolve the inconsistency.
2. sigma=2.5 — what is actual σ of F5 run differentials?
3. n=4 insufficient. Validate scaling constant, then accumulate data.

---

## SPREAD (Run Line)

**Current config:** alternate_run_line market, sigma=3.8. GG5 blocks positive-odds spreads. 0 picks.

1. Is the alternate_run_line market being pulled from the Odds API? Are lines being returned?
2. For MLB standard -1.5/+1.5 run line, which side does GG5 block? Does it block the dog (+1.5 at positive odds) or something else?
3. sigma=3.8 for run line — what is actual σ of MLB run differentials? Is 3.8 calibrated correctly?
4. With 0 picks in 31 days, is SPREAD being evaluated at all? If GG5 kills all SPREAD picks, should SPREAD be removed from TIERS?
5. Is the -1.5 run line market efficient enough to find edge? What would the model need to show genuine edge here?

---

## Cross-Cutting System Questions

### BLEND_ALPHA
1. BLEND_ALPHA=0.25 is used for all MLB game lines (ML, SPREAD, TEAM_TOTAL, F5). Is 0.25 right for MLB specifically, or should it differ from NBA's 0.25?
2. Should different MLB markets have different BLEND_ALPHA? (Team totals may have more SaberSim signal than ML.)
3. Empirically validate: compare blended projections vs actual outcomes across market types. What BLEND_ALPHA minimizes projection error per market?

### GAME_SIGMA validation
4. MLB total sigma=4.0 — what is actual σ of MLB game totals from 2024-25 Stats API data?
5. MLB spread sigma=3.8 — what is actual σ of MLB run differentials?
6. MLB team sigma=3.0 — what is actual σ of team runs scored per game?
7. MLB ML sigma=6.0 — is this the right parameter for win probability, or should it derive from run differential σ?

### Park factors
8. No park factor model in MLB. Coors Field inflates totals ~20-30%. Does SaberSim encode park in saber_team and player projections? If yes, does BLEND_ALPHA correctly propagate this signal?
9. If park is not encoded in SaberSim, should a park factor adjustment be added to team total and game line projections?

### STAT_CAP
10. STAT_CAP=2 for all MLB stats. Does this apply in shadow mode, or does shadow log all qualifying picks regardless of cap?
11. For HRR and TB, should per-run cap be reduced to 1 given high correlation between batters in the same lineup?

### Sizing
12. SPORT_UNIT_CAP=8.0u for MLB (same as NBA). Is 8.0u appropriate while in shadow/calibration mode?
13. VAKE_MULT is uniform across sports. Should MLB have a temporary multiplier reduction during shadow validation?
14. T1 sizing: var_mult=1.00, tier_mult=1.00 — full size. Given MLB T1 (K, HRR) is losing, is full sizing appropriate?

### Book coverage map
15. Which CO-legal books consistently offer each market: pitcher_strikeouts, pitcher_outs, pitcher_hits_allowed, batter_hits, batter_total_bases, batter_hits_runs_rbis, NRFI/YRFI, team_totals, ML, F5? Build a coverage matrix.
16. Are there markets where only 1-2 books offer lines, making best-line shopping effectively impossible?

### SaberSim data quality
17. Does SaberSim MLB CSV provide reliable confirmed starter flags? What is the day-of scratch rate?
18. Does SaberSim provide any team offensive quality metrics alongside player projections?
19. What is the typical SaberSim release time vs game time for MLB? Are projections stale for late lineup changes?

### ER cleanup
20. ER picks exist in shadow log (April 14-15) but ER is not in PROP_MARKETS or SIGMA. Find and remove any residual ER code paths if the market is dead.

---

## Research Session Order

**Priority order (biggest dollar impact first):**

1. **TB + HRR distribution** — share same root cause. Pull Stats API game logs, fit distributions, get correct probability formula. -146u combined.
2. **NRFI** — structural fix or kill. Check team offense data availability, recalibrate FIP/base rate. -41u.
3. **K + OUTS** — projection bias measurement. Compare SaberSim vs actuals, decide deflator vs kill. -26u combined.
4. **TEAM_TOTAL + ML_FAV** — validate if marginal positive is real or noise. Check sigma, BLEND_ALPHA, park factors.
5. **F5 markets** — validate scaling constants (0.51 vs 0.54 inconsistency), sigma calibration, market availability.
6. **HITS/YRFI/SPREAD/HA/ER** — resolve zero-pick issues, tier discrepancies, legacy cleanup.
7. **Cross-cutting** — GAME_SIGMA validation, BLEND_ALPHA, park factors, book coverage map.

Each session: research → verdict (fix/kill) → implement → validate on shadow data before live.
