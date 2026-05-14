# MLB Model Research Prompt

Paste this into ChatGPT Deep Research. One session covers all markets.

---

I am building a Python sports betting model for MLB. It uses SaberSim CSV projections and
The Odds API for lines. I need you to research and answer all of the following questions
about every MLB market the model trades. Be specific — give exact numbers, formulas, and
parameters. Vague answers are not useful.

**System config for context:**
- Distributions in use: Normal (TB, HRR, OUTS, HA, TEAM_TOTAL, game lines), Poisson (K, HITS)
- BLEND_ALPHA=0.25 for all game lines (model = line + 0.25×(saber - line))
- GAME_SIGMA: game total=4.0, run differential=3.8, team runs=3.0, ML win prob=6.0
- SIGMA mult/min: K(0.45/1.5), OUTS(0.22/3.0), HA(0.50/2.5), HITS(0.90/0.7), TB(1.20/1.5), HRR(0.75/1.3)
- F5 scaling: 0.51× game total for F5_TOTAL/F5_SPREAD, 0.54× for F5_ML (inconsistency to resolve)
- NRFI: BASE_SCORING_RATE=0.194, FIP constant=3.20, 60/40 FIP/ERA blend, scoring prob clipped [0.05, 0.45]
- CO-legal books: DraftKings, FanDuel, BetMGM, Caesars, Fanatics, theScore Bet, Hard Rock, others

---

## TB (Total Bases)

TB is a discrete non-negative integer (0,1,2,3,4+). Current model uses Normal distribution.

- Pull the empirical per-game TB distribution from MLB Stats API (2024-25 season, all qualified
  batters). What are P(TB=0), P(TB=1), P(TB=2), P(TB=3), P(TB≥4) for a batter projecting ~1.5 TB?
- Fit Zero-Inflated Poisson, Negative Binomial, and mixture model. Compare AIC/BIC. Which wins?
- Provide fitted parameters for the best-fit distribution (λ, π, r, p as applicable).
- For a batter projecting mean TB=1.5: what is P(TB > 1.5) under Normal vs the correct distribution?
- Does the correct distribution ever produce meaningful over edge at line 1.5? Or does fixing the
  distribution effectively kill TB overs at 1.5?
- What is P(TB > 2.5) for a batter projecting 2.0–3.0 TB? Is line 2.5 a viable alternative?
- What is P(TB > 0.5)? Is this line consistently offered by major books?
- Compare SaberSim TB projection (singles + 2×2B + 3×3B + 4×HR) to actual TB outcomes — is
  the sum-of-components a valid estimate, or does within-game correlation bias it?
- Does ballpark (Coors Field, Oracle Park) significantly affect TB probability beyond what
  SaberSim encodes?
- Is TB line 2.5 consistently available across DraftKings, FanDuel, BetMGM, Caesars?
- Python: show the scipy code for P(X > 1.5) under Zero-Inflated Poisson and Negative Binomial.

---

## HRR (Hits + Runs + RBIs)

HRR is a discrete non-negative integer. Current model uses Normal distribution. Line 1.5 is
catastrophically losing (market requires 77.2% WR at avg odds +30). Line 0.5 is profitable.

- Pull the empirical per-game HRR distribution from MLB Stats API (2024-25). P(HRR=0) through P(HRR≥4)
  for a batter projecting ~2.0 HRR.
- Fit ZIP, NB, mixture. AIC/BIC comparison. Does the correct distribution differ from TB?
- Fitted parameters.
- For a batter projecting mean HRR=2.0: what is P(HRR > 1.5) under Normal vs correct distribution?
  The market implies this should be ~77%; actual WR is 48%. What does the correct model give?
- For mean HRR=1.5–2.0: what is P(HRR > 0.5) under the correct distribution? Is this consistent
  with 57.4% actual WR at break-even 55%?
- H, R, and RBI for the same player are correlated within a game. Does summing independent
  projections (H + R + RBI from SaberSim) systematically over- or under-estimate the composite mean?
- Does batting order position materially affect HRR probability (leadoff = high R/low RBI,
  cleanup = high RBI/low R)? Does SaberSim encode this?
- Is HRR line 0.5 consistently available? Which major books offer it?
- Is HRR line 2.5 consistently available? Typical odds?
- Should HRR be tiered differently by line bucket (0.5 vs 1.5 vs 2.5)?

---

## HITS (Batter Hits)

Current model: Poisson, zero picks in 31 days. Gate bans picks at line ≤1.5.

- What lines does the batter_hits market actually offer across major US books? Is 2.5 consistent?
- At line 2.5, is Poisson the right distribution for hits per game? Pull empirical HITS distribution.
- Does the market offer HITS unders at line 3.5+? Are these consistently available?
- What vig do books charge on HITS markets vs other batter props?
- If HITS lines are predominantly 0.5/1.5, should this stat be removed from the model entirely?

---

## K (Pitcher Strikeouts)

Current model: Poisson, mult=0.45, min=1.5. 76/79 picks are unders. Market prices under as
an underdog at +58/+40 (lines 4.5/5.5) — we bet under and lose. SaberSim K projections appear
systematically low.

- Is Poisson correct for K, or is K overdispersed? Fit Poisson vs Negative Binomial on empirical
  2024-25 per-start K data from MLB Stats API. AIC/BIC comparison. Fitted NB parameters if better.
- What is the mean bias of SaberSim K projections vs actual K outcomes? Direction and magnitude.
  Is this consistent across line buckets (3.5, 4.5, 5.5, 6.5+)?
- Does SaberSim project K assuming full-game completion, or model partial outings?
- Does SaberSim distinguish starter vs bulk reliever K projections?
- If the bias is IP-related (pitcher goes shorter than projected), can a calibration deflator fix it?
- Should there be a minimum K line gate (e.g., only evaluate ≥5.5) to avoid bad low-line picks?
- K overs have a 0/3 WR — should overs be gated out entirely?
- What vig do books charge on pitcher_strikeouts by line bucket?
- Which CO-legal books offer pitcher_strikeouts most consistently?

---

## OUTS (Outs Recorded = IP × 3)

Current model: Normal, mult=0.22, min=3.0. 80/93 picks are unders. Under at avg odds -18, 45% WR.
Overs: 53.8% WR on 13 picks.

- Is the per-start OUTS distribution Normal, or bimodal (quality start vs early hook)?
  Pull empirical distribution from MLB Stats API 2024-25.
- What is the actual standard deviation of OUTS per start? (Current sigma floor=3.0 — correct?)
- What fraction of IP variance is predictable from pre-game data vs random (game script, manager)?
  Estimate R² from regression of actual IP on pre-game variables (pitcher quality, opponent, park).
- How does SaberSim project OUTS — direct IP column or derived?
- What is mean bias of SaberSim OUTS projection vs actual?
- Does bullpen availability affect actual IP in ways SaberSim can't capture?
- Is pitcher_outs consistently available across CO-legal books? Typical line range (14.5/17.5/20.5)?
- Should OUTS unders be gated out given 45% WR? Should overs be separately evaluated?
- What pre-game signals reliably predict IP: bulk/opener flag, bullpen workload, schedule density?

---

## HA (Hits Allowed)

Current model: Normal, mult=0.50, min=2.5. Coded as T1B with note "unders 3.5+ only" but all 17
shadow picks are overs. n=17 insufficient to conclude.

- Is Normal correct for HA? The model previously used Poisson (noted as 15% overdispersed).
  Pull empirical HA distribution from Stats API and revalidate which is better.
- Is HA capped by actual innings pitched in the model? (Same IP-dependency problem as K and OUTS.)
- The T1B tier notes "unders 3.5+ only" but all 17 picks are overs — is there a code bug,
  or is the comment misleading?
- What is mean bias of SaberSim HA projection vs actual?
- What is actual σ of HA per start from Stats API?
- Is pitcher_hits_allowed consistently available? What lines does the market offer?
- Does Coors Field significantly inflate HA in a way SaberSim may not fully encode?
- What data volume is needed before HA can be properly evaluated (given n=17)?

---

## ER (Earned Runs)

7 picks from April 14-15 only. ER is not in the active market config. Appears to be a legacy remnant.

- Does any CO-legal book currently offer a pitcher_earned_runs prop market via The Odds API?
  What is the Odds API market key string if it exists?
- If the market is live: what distribution and sigma should ER use? Does the earned/unearned
  distinction add noise that makes it unprojectable pre-game?
- If the market is dead: confirm so residual code paths can be cleanly removed.

---

## NRFI / YRFI

NRFI model: P(NRFI) = (1-p_away)(1-p_home), where p_team = f(FIP, ERA). Model ignores team offense.
Actual WR: 28.9% on 211 picks at avg odds +100 (50% implied). YRFI: 0 picks.

- What is the actual 2025 first-inning NRFI rate from MLB Stats API? Pull inning-by-inning data.
- Does first-inning NRFI rate vary meaningfully by team offense, ballpark, or game context?
- What offensive metrics best predict first-inning scoring probability beyond pitcher quality alone?
  (wOBA, OPS+, lineup projection, run expectancy — what's available pre-game?)
- Is the independence assumption (two half-innings independent) empirically valid? Test it.
- What is the correct 2025 FIP constant? (FIP constant = lgERA − FIP_component/IP)
- Is 60/40 FIP/ERA blend empirically justified for first-inning prediction, or should it be
  FIP-only, ERA-only, or a different ratio?
- What is actual 2025 MLB ERA through current date (approx)?
- Is BASE_SCORING_RATE=0.194 (implies 65% baseline NRFI) correct? What does empirical data give?
- Is the 0.45 scoring probability ceiling justified? What does the empirical max look like
  for a weak pitcher vs elite offense?
- NRFI is coded T3 (min_edge=6%) but 201/211 shadow picks logged as T2. Is there a code bug?
- Is NRFI/YRFI market (totals_1st_1_innings) consistently available across CO-legal books?
- If team offense data is unavailable pre-game, is NRFI structurally unfixable and should be killed?

---

## TEAM_TOTAL

Current model: blend = line + 0.25×(saber_team - line). All 124 picks are overs. +2.30u.

- What is mean(saber_team - market_line) across typical MLB games? Does SaberSim systematically
  project above market lines (which would explain all picks being overs)?
- What is the actual standard deviation of MLB team runs scored per game from Stats API 2024-25?
  (Current sigma=3.0 — correct?)
- Is BLEND_ALPHA=0.25 empirically validated for MLB team totals? What alpha minimizes projection error?
- 51.6% WR on 124 picks at ~52% break-even — is +2.30u statistically significant, or within noise?
  What n is needed to confirm at 90% confidence?
- Does saber_team account for opposing starting pitcher quality?
- Does SaberSim encode park factor in saber_team? If yes, does 0.25 blend correctly propagate it?
- Should team total unders ever fire? If saber_team is always above market line, is that a SaberSim
  bias or a model issue?

---

## ML_FAV / ML_DOG

ML model: win_prob = normal_cdf(0, blended_margin, 6.0). ML_FAV: n=48, 54.2% WR, avg odds -113,
break-even 53.1%. ML_DOG: n=3, insufficient.

- What is the actual standard deviation of MLB full-game run differentials from Stats API 2024-25?
  (Current sigma=6.0 — is this correct for win probability estimation?)
- Is 54.2% WR at -113 avg odds on n=48 statistically significant? What n is needed at 90% confidence?
- Does the model incorporate home field advantage explicitly? MLB HFA is ~54% historically.
- Does FIP differential between starters add signal beyond the Vegas line?
- For ML_DOG (n=3): should minimum edge be raised to 12%+ given underdog variance?
- What is the break-even WR at typical ML_DOG odds in this sample?

---

## F5_TOTAL / F5_ML / F5_SPREAD

F5 scaling inconsistency: 0.51× game total for F5_TOTAL/F5_SPREAD, 0.54× for F5_ML.

- Is 0.51 (F5 ≈ 51% of full-game runs) empirically correct? Pull 2024-25 first-5-inning run data
  vs full-game totals from Stats API. What is the actual ratio?
- What is the actual standard deviation of F5 run totals from Stats API? (Current F5_SIGMA total=2.6)
- What is the actual standard deviation of F5 run differentials? (Current F5_SIGMA spread=2.5)
- Why does F5_ML use 0.54 while F5_TOTAL/F5_SPREAD use 0.51? Which is correct, and should they
  be consistent?
- Should F5 ML win probability use a different sigma than F5 spread coverage?
- Are F5_TOTAL, F5_ML, and F5_SPREAD consistently available across CO-legal books?
- What starter confirmation quality impact does the F5 market have — how often do starters who
  were confirmed pre-game actually pitch all 5 innings?

---

## SPREAD (Run Line)

Current model: alternate_run_line market, sigma=3.8. Zero picks in 31 days.

- Is the alternate_run_line market returned by The Odds API for CO-legal books? What are the
  exact market key strings?
- What is the standard MLB run line structure (-1.5/+1.5)? What are typical odds on each side?
- What is the actual standard deviation of MLB run differentials from Stats API? (Current sigma=3.8)
- Is the run line market efficient enough that a blended-projection model can find edge?

---

## Cross-cutting

**GAME_SIGMA validation:**
- Actual σ of MLB game totals (2024-25 Stats API) — current model uses 4.0
- Actual σ of MLB run differentials — current model uses 3.8
- Actual σ of MLB team runs per game — current model uses 3.0
- Is sigma=6.0 for ML win probability the right parameter, or should it derive from run diff σ?

**BLEND_ALPHA:**
- Should BLEND_ALPHA=0.25 differ across MLB markets (team totals may carry more SaberSim signal
  than ML)? What alpha minimizes projection error per market type?

**Park factors:**
- Does SaberSim encode park factor in saber_team and player projections?
- If not: what public source provides reliable park factors pre-game for a Python integration?
  Fangraphs? Baseball Reference? What is the URL/API structure?
- Which parks are the most extreme outliers (Coors, Oracle, etc.) and by what magnitude?

**Book coverage — build this matrix:**
For each market, which CO-legal books consistently offer it, and what is the typical vig?
Markets: pitcher_strikeouts, pitcher_outs, pitcher_hits_allowed, batter_hits,
batter_total_bases, batter_hits_runs_rbis, NRFI/YRFI (totals_1st_1_innings),
team_totals, moneyline, alternate_run_line, h2h_first_5_innings, totals_first_5_innings.

**SaberSim MLB CSV:**
- Does SaberSim MLB CSV include confirmed starter flags? What is the day-of scratch rate?
- Does SaberSim MLB CSV include any team offensive quality columns (team wOBA, run total, lineup)?
- What is the typical SaberSim publication time relative to first pitch for MLB games?

**Lineup correlation:**
- H, R, RBI, TB for batters in the same lineup are correlated. Should per-run STAT_CAP for
  HRR and TB be reduced to 1 (vs current cap of 2) to limit lineup correlation exposure?
