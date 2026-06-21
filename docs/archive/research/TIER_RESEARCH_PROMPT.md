# Market Tier & Variance Research Prompt

Paste this into ChatGPT Deep Research or Claude with web search.

---

I am building a Python sports betting model covering NBA, WNBA, NHL, MLB, and NFL. Every
market is assigned to a tier that controls (a) the minimum edge required to post a bet and
(b) the sizing applied via a VAKE system derived from Kelly. Tier placement must reflect two
things simultaneously: market efficiency (how accurately books price it) AND variance profile
(how volatile the outcome is, independent of edge). Both drive tier. A market with low
efficiency but very high variance still belongs in a lower tier because the noise in the
outcome requires a larger edge cushion to be confidently +EV. Getting the tier wrong in
either direction costs money: too high a tier on a volatile market → undersized edge cushion
→ posts false edges → loses. Too low a tier on a stable market → over-penalizes sizing on
genuine edges → leaves profit on the table.

**The tier system (current — validate and correct):**
- **T1** — most efficiently priced, lowest outcome variance. Min edge: 3%. Full VAKE sizing.
- **T1B** — same edge threshold but lower volume or directionally restricted (unders-biased).
  Min edge: 3%. Full VAKE sizing. Separate from T1 to allow directional gating.
- **T2** — moderate efficiency or moderate variance. Min edge: 5%. Sizing reduced to 76.5% of T1.
- **T3** — lowest efficiency and/or highest variance / binary-adjacent outcomes. Min edge: 6%.
  Sizing reduced to 39% of T1.

**VAKE sizing system (current — validate and correct):**
```
Base unit from edge:
  3%–5%  → 0.50u base
  5%–7%  → 0.75u base
  7%–9%  → 1.00u base
  9%+    → 1.25u base

Multipliers applied to base:
  Variance multiplier: T1=1.00, T1B=1.00, T2=0.85, T3=0.65
  Tier multiplier:     T1=1.00, T1B=1.00, T2=0.90, T3=0.60

Final size = base × variance_mult × tier_mult

Examples:
  T1 pick at 5% edge  → 0.75 × 1.00 × 1.00 = 0.75u
  T2 pick at 5% edge  → 0.75 × 0.85 × 0.90 = 0.57u
  T3 pick at 5% edge  → 0.75 × 0.65 × 0.60 = 0.29u
  T3 pick at 8% edge  → 1.00 × 0.65 × 0.60 = 0.39u
```

**Current tier assignments (validate every one):**
```
T1  (3% min): AST, SOG, K, HRR, REC[NFL-planned]
T1B (3% min): REB, HITS, HA
T2  (5% min): PTS, PRA, PR, PA, RA, OUTS, TB, TOTAL, SPREAD, ML_FAV,
              TEAM_TOTAL, F5_TOTAL, F5_SPREAD, F5_ML, YARDS[NFL-planned]
T3  (6% min): 3PM, ML_DOG, NRFI, YRFI, TDS[NFL-planned], GOALS[NHL-planned]
ML_DOG override: 8% min_edge (all sports, hardcoded separate from tier system)
YRFI override:   8% min_edge (hardcoded separate from tier system)
```

**Current KILLSHOT gate:**
- Fires when: tier=T1 strict, pick_score≥90, win_prob≥0.65, odds ∈ [-200, +110]
- Eligible stats: {PTS, AST, SOG, 3PM}
- Max 2 per week

**Current caps:**
- Daily total cap: 12u (all sports combined)
- STAT_CAP: SOG=6, all other stats=2 (max picks per stat per run)
- SPORT_UNIT_CAP: NBA=8u, WNBA=4u, NHL=5u, NFL=8u, MLB=8u (max per single pick)

---

## SECTION 1: Variance Theory — The Foundation of VAKE

Before covering individual markets, establish the variance framework that drives everything.

### 1A. What variance means for bet sizing

- State the Kelly criterion formula for a binary bet:
  f* = (b×p - q) / b  where b = decimal odds - 1, p = win prob, q = 1-p
  Confirm: Kelly maximises log-wealth growth and is the theoretical optimal fraction.
- Why does variance reduce Kelly sizing beyond what the formula shows?
  (Kelly assumes infinite trials and known true probabilities. In practice: parameter
  uncertainty about p, correlated outcomes across picks, and fat tails all mean full Kelly
  is too aggressive. Fractional Kelly is standard. What fraction is used by professional
  bettors — 1/4 Kelly? 1/3 Kelly? 1/2 Kelly?)
- The model uses VAKE (a tiered system) instead of per-pick Kelly. What fraction of full
  Kelly does VAKE approximately represent at each tier?
  Work through:
  - T1 at 5% edge, 53% WR, -115 odds: what does 1/4 Kelly say? What does VAKE give?
  - T2 at 5% edge, 53% WR, -115 odds: same Kelly fraction but higher variance → what
    adjustment is correct?
  - T3 at 6% edge, 55% WR, +105 odds: full Kelly? VAKE gives 0.39u — is this right?
- Is VAKE_BASE (0.50/0.75/1.00/1.25u by edge bracket) consistent with fractional Kelly
  at typical win rates and odds? Or is it systematically over/under-sized?

### 1B. Outcome variance vs projection variance

There are two distinct sources of uncertainty the model faces:
1. **Aleatory variance** — irreducible randomness in the outcome even with a perfect
   projection (e.g., a player projected at 6.2 assists could score 2 or 10 on any given night)
2. **Epistemic variance** — uncertainty in the projection itself (SaberSim may be wrong;
   injuries/lineup changes not yet captured)

- Which source of variance is larger for player props? For game lines?
- Does epistemic variance dominate for new markets (early-season, Week 1 NFL) while
  aleatory variance dominates for established ones?
- How does this affect tier placement? A market where epistemic variance dominates
  needs a higher edge threshold (T2 or T3) even if aleatory variance is low, because
  the model's edge estimate itself is unreliable.
- For which stats in the model is epistemic variance highest?
  (e.g., RUSH_YARDS where game script can completely change a RB's role)

### 1C. Coefficient of Variation (CV = σ/μ) per market

CV is the primary metric for aleatory variance normalised by projection magnitude.
Higher CV = more volatile = larger edge cushion needed = lower tier or higher min_edge.

Provide empirical CV for every market below from historical data (2022-2025 where available).
CV is measured as: per-player per-game std dev divided by per-player per-game mean,
averaged across all players within the relevant population.

**IMPORTANT: use within-player CV (same player, game-to-game variance), NOT
cross-player CV (variance across different players). The model projects a specific player —
the relevant uncertainty is how much that player's outcome varies around their own projection,
not how much players differ from each other.**

```
NBA:
  PTS        CV = ?   (starter population, 2022-25)
  AST        CV = ?
  REB        CV = ?
  3PM        CV = ?   (expected high — bimodal for specialists)
  PRA        CV = ?   (will be lower than sum of components due to correlation)
  PR         CV = ?
  PA         CV = ?
  RA         CV = ?

NHL:
  SOG        CV = ?   (forward population)
  SOG        CV = ?   (defenseman population — different?)
  AST        CV = ?   (at typical line 0.5 — essentially Bernoulli; give P(assist≥1))
  GOALS      CV = ?

MLB:
  K          CV = ?   (starting pitcher, min 5 IP)
  OUTS       CV = ?   (correlated with K — is CV similar?)
  HA         CV = ?   (hits allowed — higher CV due to BABIP variance)
  HITS       CV = ?   (batter hits — low mean ~1.2 → high CV expected)
  TB         CV = ?   (total bases — higher than HITS due to extra base variance)
  HRR        CV = ?   (combo stat — H+R+RBI; correlation reduces CV vs components)
  NRFI       CV = ?   (binary 0/1 — CV = sqrt(p(1-p))/p = sqrt((1-p)/p))
  YRFI       CV = ?

NFL (planned):
  PASS_YARDS CV = ?
  RUSH_YARDS CV = ?   (expected highest — game script dependent)
  REC_YARDS  CV = ?
  RECEPTIONS CV = ?
  PASS_TDS   CV = ?   (mean ~1.8 → very high CV)
  RUSH_TDS   CV = ?   (even rarer → very high CV)
  REC_TDS    CV = ?
  INT        CV = ?

Game lines (CV of projected margin vs actual margin):
  NBA SPREAD CV = ?   (game-to-game spread differential std dev / mean spread)
  MLB TOTAL  CV = ?
  NHL TOTAL  CV = ?
  NFL TOTAL  CV = ?
```

### 1D. Distribution shape: skewness, kurtosis, and fat tails

Standard Kelly assumes symmetric, normally-distributed outcomes. Real sports props are not:

- Which stats have significantly right-skewed distributions?
  (e.g., PASS_YARDS: most games 200-300 yards but occasional 400+ yard outbursts)
- Which stats are zero-inflated (meaningful probability of exactly 0)?
  Give P(outcome=0) for: HITS, TB, HRR, RUSH_YARDS, REC_YARDS, RECEPTIONS, GOALS, INT
- Which stats are bimodal (two distinct modes, not a single bell curve)?
  (e.g., 3PM for specialist shooters — either shoots many or none)
- For any stat with heavy right tail (kurtosis > 3): does this increase or decrease the
  effective Kelly fraction? (Fat right tails increase expected variance of the Kelly path →
  use lower fraction than standard Kelly suggests)
- Does zero-inflation require a separate hurdle-model CV estimate?
  (e.g., RUSH_YARDS: if P(0 yards)=8%, the conditional CV given >0 yards is lower than the
  unconditional CV. Which does VAKE care about?)

### 1E. CV ranking — how should CV drive tier placement?

Once empirical CV is established for every market:

- Rank all markets from lowest CV to highest CV.
- Is CV alone sufficient to determine tier, or must it be weighted with market efficiency?
- Propose a CV-based tier framework:
  - CV < X → T1 candidate
  - CV X–Y → T2 candidate
  - CV > Y → T3 candidate
  What are the right X and Y thresholds based on the data?
- Are there markets where efficiency and CV point to different tiers?
  (e.g., a market that is inefficiently priced but has very low CV — does it go to T1 for
  the low CV, or T2 for the inefficiency?)
- Final rule: when efficiency and CV conflict, which wins?

---

## SECTION 2: Market Efficiency — The Second Driver

Efficiency is the second axis. Together with CV, it determines tier.

### 2A. The efficiency framework

- What is the academic/industry consensus on how to measure market efficiency in sports betting?
  Is vig alone sufficient, or do CLV (closing line value) data, sharp action, and limit size
  all need to be combined?
- How efficient are CO-legal retail books (DraftKings, FanDuel, BetMGM, Caesars, Fanatics,
  theScore Bet, Hard Rock, BetRivers, Bet365) vs Pinnacle?
  Should Pinnacle's closing line be used as the efficiency benchmark?
- What is the empirical relationship between vig (hold percentage) and market efficiency?
  Give the hold % formula. Do wider vig markets (−120/−110) contain more mispricing than
  tighter markets (−115/−115)?
- For player props vs game lines: are props uniformly less efficient, or does it depend on
  the stat and sport?
- What do book limits signal about efficiency?
  (Low limits = book is less confident in its pricing = less efficient market)
- Which CO-legal books set their own lines vs copy Pinnacle or other sharp books?
  (Line originators vs line copiers — matters for CLV evaluation)
- What minimum CLV should the model target per tier to be profitable long-term?
- Do books limit winning prop bettors faster than game line bettors?
  Which specific markets trigger limits soonest?

### 2B. The combined tier decision rule

For each market, both axes must be assessed. Propose a concrete decision matrix:

```
                    Low CV (stable)  |  High CV (volatile)
                    -----------------|--------------------
Efficient market:        T1          |       T2
Inefficient market:      T1B/T2      |       T3
```

- Is this the correct 2×2 decision matrix? What modifications are needed?
- For combo stats (PRA, HRR, YARDS): does correlation between components reduce effective
  CV vs the sum of component CVs? If yes, does that justify a higher tier for combos?
- For game lines vs props: do game lines always land in a specific part of the matrix,
  or do they span multiple cells depending on sport?

---

## SECTION 3: NBA Player Props

For each stat: give empirical CV, characterise distribution shape, assess efficiency,
and recommend tier with explicit justification citing both CV and efficiency.

### PTS (Points) — currently T2

- Empirical within-player CV for NBA PTS? Break down by role: starter / sixth man / rotation.
- Distribution shape: symmetric Normal, right-skewed, or bimodal? Kurtosis?
- How efficiently do books price NBA PTS? Does Pinnacle's closing line move significantly
  post-opening (indicating sharp money found mispricing)?
- Do books shade PTS overs due to public bias on star scorers? If yes: are overs structurally
  -EV and unders structurally +EV at certain lines?
- Typical vig on NBA PTS props?
- **Recommended tier and min_edge — justify with CV and efficiency data.**
- KILLSHOT eligibility: PTS is currently eligible (T2 stat allowed in KILLSHOT). Correct?

### AST (Assists) — currently T1

- Empirical within-player CV for NBA AST? Is it lower than PTS (justifying T1 for lower variance)?
- Distribution shape: Poisson-like or overdispersed? Is AST at line 4.5+ well-approximated
  by Normal, or does skew matter at lower lines?
- How efficiently do books price AST vs PTS? Is the AST market thinner (less sharp money)?
- What over/under bias exists in AST? (Books over- or under-adjust for pace/turnover rate?)
- Typical vig on NBA AST?
- **Recommended tier and min_edge.**
- KILLSHOT eligibility: currently eligible. Correct?

### REB (Rebounds) — currently T1B

- Empirical within-player CV for NBA REB? Compare directly to AST CV.
- Is REB higher or lower CV than AST? This is the core question for T1 vs T1B.
- Distribution shape: Normal-ish or overdispersed? Does REB have meaningful zero-inflation
  (e.g., big men who get 0 rebounds in some games)?
- Over/under bias in REB market? (Public bets big-man REB overs?)
- Typical vig on NBA REB?
- **Recommended tier: T1, T1B, or T2? Justify using CV comparison to AST.**

### 3PM (Three-Pointers Made) — currently T3

- Empirical within-player CV for NBA 3PM. Expected to be among the highest in the model.
- Is 3PM bimodal for specialist shooters (many games with 0, some games with 5+)?
  Quantify: what fraction of starter games have 0 threes made? For a Klay Thompson type?
- Distribution: NB(r=12.3) currently used. Does r=12.3 correctly capture the variance?
- Books shade 3PM overs heavily (public loves shooter overs). Quantify the degree of
  public bias if possible. Does this make 3PM unders the better bet systematically?
- Typical vig on NBA 3PM?
- **Recommended tier. Given the high CV and bimodal nature, is T3 correct?**
- KILLSHOT eligibility: 3PM is currently eligible despite being T3. Should a T3 stat be
  KILLSHOT eligible? What win rate does wp≥0.65 on a T3 stat produce?

### Combo Props (PRA, PR, PA, RA) — currently all T2

PRA = pts+reb+ast. PR = pts+reb. PA = pts+ast. RA = reb+ast.

- Empirical within-player CV for PRA vs standalone PTS.
  (Hypothesis: positive correlation between PTS/REB/AST for the same player reduces PRA
  CV relative to the sum of component CVs — combo stats are actually less volatile
  than their components suggest. Confirm or deny with data.)
- Give empirical Pearson r for: PTS vs REB, PTS vs AST, REB vs AST, for same player same game.
  (Model already has COMBO_RHO: PTS-REB=0.333, PTS-AST=0.233, REB-AST=0.251. Do these
  match literature/data? If PRA CV < PTS CV, does PRA deserve T1 rather than T2?)
- Distribution shape of PRA: is it more Normal than its components (Central Limit Theorem
  effect from summing three distributions)?
- Are combo markets efficiently priced? Do books correctly account for inter-stat correlation,
  or do they price combos as sum of components (ignoring correlation → systematic bias)?
- Vig on combo props vs single-stat props? (Wider vig = less efficient = potentially better edge)
- **Recommended tier for each: PRA / PR / PA / RA separately. Should they all be T2,
  or does lower CV justify T1B or even T1 for some?**

---

## SECTION 4: WNBA Player Props

WNBA uses the same stat structure as NBA but is a much thinner market.

- Give empirical within-player CV for WNBA PTS, AST, REB separately.
  Is WNBA CV higher or lower than NBA for the same stat?
  (Hypothesis: fewer games, smaller rosters, higher role-change frequency → higher CV)
- Is WNBA PTS sigma significantly higher than NBA? The model currently uses CV mult=0.38
  (only 8.6% above NBA baseline of 0.35), but CV research suggests 0.36 WNBA vs 0.25 NBA
  — a 44% difference. Confirm empirically.
- Are WNBA markets more or less efficiently priced than NBA?
  (Thinner markets → less sharp money → more mispricing → potentially larger edges,
  but also less liquid → lower limits → smaller safe bet size)
- Typical vig on WNBA props vs NBA? Is it wider (indicating lower efficiency)?
- SPORT_UNIT_CAP=4u for WNBA vs 8u for NBA. Is the 2× reduction correct given:
  - How much lower are book limits for WNBA vs NBA?
  - How much higher is WNBA CV vs NBA?
- **Recommended: should all WNBA stats be one tier lower than NBA equivalents,
  or is the current shared tier assignment correct?**

---

## SECTION 5: NHL Player Props

### SOG (Shots on Goal) — currently T1, STAT_CAP=6, KILLSHOT eligible

- Empirical within-player CV for NHL SOG by position (forward vs defenseman).
  Is SOG CV lower than NBA AST CV (justifying same T1 placement)?
- Distribution shape: Poisson-like or overdispersed?
  Give P(SOG=0), P(SOG=1), P(SOG=2), P(SOG≥5) for a typical forward.
- How efficiently do books price SOG? Is it as sharp as NBA AST?
- Typical vig on SOG?
- STAT_CAP=6: NHL has ~14 forwards per team per game. On a 7-game NHL slate, 98 forward
  SOG markets exist. Is cap=6 correctly calibrated to limit over-concentration?
- KILLSHOT eligibility for SOG: at wp≥0.65 on a SOG pick, what does the empirical
  win rate look like for that confidence level?
- **Recommended tier. Is T1 correct given both CV and efficiency?**

### AST (Assists) — currently T1 for NHL

- NHL assists is a fundamentally different market from NBA assists.
  Dominant line is 0.5 — this is effectively a Bernoulli (did the player get 1+ assist?).
  P(assist≥1) for a top-6 forward is ~0.35-0.45 per game. CV for a Bernoulli(p) = sqrt((1-p)/p).
  At p=0.40: CV = sqrt(0.6/0.4) = 1.22. This is extremely high variance.
- Is CV=1.22 consistent with T1 placement? Compare to NBA AST CV.
  If NHL AST CV >> NBA AST CV, should NHL AST be T2 or T3?
- Is the NHL AST market efficiently priced? Books offering -115/-115 on a near-coin-flip
  outcome — does that indicate the market is efficient or that it's a soft recreational market?
- **Recommended tier for NHL AST. The binary nature at 0.5 may make this T3-adjacent.**

### GOALS (NHL Goals) — currently T3, planned but not active

- NHL goals: even more rare than assists. P(goal≥1) for a top scorer ~0.25-0.35 per game.
  At p=0.30: CV = sqrt(0.7/0.3) = 1.53. Extremely high variance.
- Is T3 (6% min_edge) sufficient for a market this volatile, or should it require even
  higher edge (7-8%) or be excluded entirely?
- Does The Odds API consistently offer player_goals for NHL?
- Typical vig on NHL goal props?
- **Recommended: include at T3 with higher min_edge, or exclude from model?**

---

## SECTION 6: MLB Pitcher Props

### K (Strikeouts) — currently T1, NB(r=5.0)

- Empirical within-pitcher CV for K per start (2022-2024, min 5 IP).
  By archetype: power pitcher (K/9 ≥ 10) vs contact pitcher (K/9 ≤ 7).
- Distribution: NB(r=5.0) currently used. Does r=5.0 correctly capture within-pitcher
  variance? Give the fitted r from 2022-2024 data.
- Key structural issue: K variance has two sources: pure K variance AND IP variance
  (early hook = fewer K chances). Does the IP variance make K effectively higher CV than
  the NB model captures?
- How efficiently do books price K props? High public interest in K props → sharp market?
- Typical vig on MLB K props?
- **Recommended tier. If IP variance makes K CV higher than expected, should it be T2?**

### OUTS (Pitcher Outs Recorded) — currently T2

- Empirical within-pitcher CV for OUTS per start. Compare directly to K CV.
- Is OUTS the same market as K in different units? (6 innings × 3 outs = 18 outs, but
  K/9 and OUTS/start are only loosely correlated — a pitcher can throw 6 shutout innings
  with only 4 K.)
- Which has higher CV: K or OUTS? This should drive their relative tier placement.
- Typical vig on OUTS props?
- **Recommended tier. If OUTS CV < K CV: should OUTS be T1, not T2?**

### HA (Pitcher Hits Allowed) — currently T1B

- Empirical within-pitcher CV for HA per start. HA is BABIP-dependent (high randomness).
  Expected CV is high relative to K and OUTS.
- BABIP variance: hits allowed per game has high variance even for great pitchers because
  BABIP regresses to ~0.300 regardless of pitch quality. Does this make HA inherently T2/T3?
- Typical vig on HA props? Is this a soft market (few sharp bettors focus here)?
- **Recommended tier. If HA CV >> K CV: should HA be T2 or T3 rather than T1B?**

---

## SECTION 7: MLB Batter Props

### HITS (Batter Hits) — currently T1B

- Empirical within-player CV for batter HITS per game (2022-2024).
  Mean ~1.2 hits/game. P(0 hits) for a starter? (Expected ~25-30%)
- Zero-inflation: what fraction of batter games have exactly 0 hits?
  Does this significantly increase effective CV vs a non-zero-inflated count stat?
- Poisson is currently used. Does Poisson correctly model HITS, or does zero-inflation
  require a hurdle model? Give AIC/BIC comparison.
- Typical vig on batter HITS?
- **Recommended tier. If CV is high and market is soft: T2? Or does low vig justify T1B?**

### TB (Total Bases) — currently T2

- Empirical within-player CV for TB per game.
  (TB = 1×1B + 2×2B + 3×3B + 4×HR — extra base hits add extreme right-tail variance)
- Is TB CV significantly higher than HITS CV due to the power/contact volatility?
- Distribution shape: is TB right-skewed with fat tail (home run games spike TB)?
- Typical vig on TB?
- **Recommended tier. If TB CV >> HITS CV and market is soft: should TB be T3?**

### HRR (Hits + Runs + RBIs) — currently T1, NB(r=1.5)

- Empirical within-player CV for HRR per game. NB(r=1.5, μ=2.0) is currently used.
  Does r=1.5 correctly capture within-player variance?
- HRR is a combo stat: H+R+RBI. The correlation between hits, runs, and RBIs for the same
  player reduces CV vs the sum of components. What is the empirical Pearson r between:
  H vs R, H vs RBI, R vs RBI for the same player same game?
- Key structural issue: P(HRR=0) is significant (~37% of batter games have 0 H/R/RBI combined).
  This zero-inflation is the reason NB(r=1.5) was chosen. Confirm this is the right approach.
- How efficiently do books price HRR? Is it a soft market (less sharp attention)?
  The model has G13B gate: WP floor at line 1.5 requires WP≥0.65. Is this gate correct?
- Typical vig on HRR props?
- **Recommended tier. HRR is currently T1 despite being a complex 3-component combo.
  Is T1 justified given the zero-inflation and CV, or should it be T1B or T2?**

---

## SECTION 8: MLB Game Lines

### NRFI/YRFI — currently both T3

- NRFI binary outcome: P(no scoring in inning 1) ≈ 0.70 league-wide.
  CV for NRFI as a binary: sqrt(0.70 × 0.30)/0.70 ≈ 0.655. This is very high variance.
- Is the high CV the primary reason NRFI is T3? Confirm with data.
- How efficiently do books price NRFI? Does the formula P(NRFI) ≈ (1-p_home)×(1-p_away)
  give an edge that books consistently fail to capture? Or is this well-known and priced in?
- YRFI has 8% min_edge override (vs 6% for NRFI). Is this differential justified by data?
  What is the empirical win rate on YRFI picks vs NRFI picks at similar edges?
- **Recommended tier and min_edge for each. Could NRFI be T2 if efficiency is low?**

### F5 Lines (F5_TOTAL, F5_SPREAD, F5_ML) — currently T2

- What is the empirical variance (σ) of F5 run differentials vs full-game?
  Model uses F5_SIGMA: total=2.6, spread=2.75, team=2.0.
  Are these correctly calibrated? (Full-game MLB spread σ ≈ 3.8; F5 should be lower.)
- Are F5 markets more or less efficiently priced than full-game equivalents?
  (Hypothesis: F5 has less volume → less sharp action → more mispricing)
- Typical vig on F5 markets vs full game?
- **Recommended tier. If F5 is less efficient AND has lower variance than full-game:
  could F5_TOTAL be T1B rather than T2?**

### MLB Full-Game Lines (TOTAL, SPREAD, ML_FAV, ML_DOG, TEAM_TOTAL)

- Empirical CV of MLB game total outcomes (σ/mean_total over 2022-2024). Current σ=4.0.
- Is MLB TOTAL more or less efficiently priced than NBA TOTAL?
  (MLB totals are affected by starting pitcher — the single biggest variable.
  If sharp money has strong pitcher quality signals, is the market very efficient?)
- ML_DOG min_edge=8% (all sports): for MLB dogs (+200 to +400), what is the empirical
  win rate of ML_DOG picks at 8% edge? Is 8% enough cushion?
- TEAM_TOTAL: is this market thinner/less efficient than full-game total?
  If yes, should it be T1B (inefficient, softer market, more edge, but lower volume)?
- **Recommend tier for each MLB game line market.**

---

## SECTION 9: NBA/WNBA/NHL Game Lines

### TOTAL (Game Total) — currently T2

- Give empirical σ of game total outcomes for NBA, WNBA, NHL (current model: NBA=12.0, WNBA=10.0, NHL=1.2).
- Is the game total market more or less efficiently priced than player props?
  (Game totals have the most betting volume → most sharp action → most efficient)
- Does the public over-bet NBA totals (overs are more exciting)? If yes, do books shade
  total lines up by X points on average?
- If game totals are the most efficiently priced market: should they be T1 (rare edge =
  reliable) rather than T2 (common edge = less reliable)?
- **Recommended tier for TOTAL across NBA/WNBA/NHL.**

### SPREAD — currently T2

- Is the NBA spread more or less efficient than the NBA total? (Both are high-volume markets.)
- Empirical σ of spread outcomes: NBA=12.0. Is this the right number?
- For NHL puck line (±1.5 fixed): does the fixed line make it derivative of ML (like MLB
  runline)? If yes, should it be modeled differently from variable spreads?
- **Recommended tier for SPREAD across sports.**

### ML_FAV vs ML_DOG — currently T2 and T3

- Why is ML_DOG structurally higher variance than ML_FAV at the same edge?
  (Dog bets at +150 to +300: occasional large wins but majority losses — higher Kelly variance)
- What is the CV equivalent for a moneyline bet at +200? At +300? Compare to a -150 ML_FAV.
  (For a binary bet: CV = sqrt(p(1-p))/p = sqrt((1-p)/p); at +200 implied prob ≈33%:
  CV = sqrt(0.67/0.33) ≈ 1.42; at -150 implied prob ≈60%: CV = sqrt(0.40/0.60) ≈ 0.82)
- Does this CV difference justify T3 for ML_DOG and T2 for ML_FAV? Or should the
  threshold be odds-based rather than a blanket tier?
- Should NHL ML_DOG be T2 rather than T3? NHL dogs (+130 to +180) have lower CV than
  MLB dogs (+200 to +400). Is a blanket T3 for all ML_DOG too conservative for NHL?
- Is min_edge=8% for ML_DOG too high, too low, or correct given the CV at typical dog odds?

### TEAM_TOTAL — currently T2

- Is TEAM_TOTAL volume lower than GAME_TOTAL, making it a less efficient market?
- What is the empirical CV of team scoring outcomes vs game total outcomes?
  (Team total σ is lower than game total σ — model uses NBA team σ=9.0 vs total σ=12.0)
- **Should TEAM_TOTAL be T1B (less efficient market, more edge, but lower confidence)?**

---

## SECTION 10: NFL Player Props (Planned)

NFL is the highest-volume betting market in the US. Market efficiency for game lines is
very high. Props are more variable.

For each NFL stat: empirical CV, distribution shape, market efficiency, recommended tier.

### PASS_YARDS — tier unknown

- Within-QB CV for passing yards per game (2022-2024, starting QBs, min 10 starts).
  Expected range: 0.25-0.35? Confirm.
- Distribution: Normal-ish or right-skewed? (Occasional 400+ yard games create right tail)
- Game-script effect: trailing QBs throw more. Does this increase CV for underdogs?
  If yes, should there be a separate tier for dog-team QBs?
- How efficiently do books price PASS_YARDS? (High public interest → sharp market?)
- **Recommended tier: T1 or T2?**

### RUSH_YARDS — tier unknown

- Within-RB CV for rushing yards per game. Expected to be highest CV of all NFL stats
  due to game-script dependency (team trailing = abandon run = zero rush yards).
- Give P(rush_yards=0) for a typical RB1. (If team trails by 14+ early, rush yards collapse)
- Distribution: right-skewed (100+ yard games) with zero-inflation (blowout losses)?
- How efficiently do books price RUSH_YARDS? Is it a softer market than PASS_YARDS?
- **Recommended tier. Given high CV: T2 or T3?**

### REC_YARDS — tier unknown

- Within-WR CV for receiving yards per game. Compare to RUSH_YARDS CV.
- P(rec_yards=0) for WR1? WR2? (Target-share games vs no-target games)
- Distribution: zero-inflated Normal?
- **Recommended tier.**

### RECEPTIONS — currently pre-assigned T1

- Within-WR CV for receptions per game. Compare to NBA AST CV.
  (Hypothesis: both are completion-dependent count stats with similar variance profiles)
- Distribution: Poisson or NB? Is receptions more or less overdispersed than AST?
- How efficiently do books price receptions? Is vig similar to NBA AST?
- **Is T1 correct? Justify with CV comparison to NBA AST.**

### PASS_TDS — tier unknown

- Mean PASS_TDS per game for starting QBs ≈ 1.7. P(TDs=0) ≈ 20-25%.
  CV = sqrt(var)/mean. At mean=1.7 with high variance: expected CV > 0.8.
- Is PASS_TDS line 0.5 essentially Bernoulli (will QB throw 1+ TD)?
  P(≥1 TD) for a QB projecting 1.7 TDs: what does NB say?
- **Recommended tier: T3 (like NRFI/binary outcomes)?**

### RUSH_TDS / REC_TDS — tier unknown

- Even rarer than PASS_TDS. P(rush_TD=0) for a typical RB ≈ 70-75%.
  CV >> 1.0. This is structurally similar to NHL GOALS.
- **Recommended tier: T3 or exclude?**

### INT (Interceptions) — tier unknown

- P(INT=0) for a starting QB ≈ 60-70%. Mean ≈ 0.8-1.0 per game. CV >> 1.0.
- Is INT worth building at all? What is the bet volume potential?
- **Recommended tier: T3 or exclude?**

### NFL Game Lines

- NFL is the most-bet market in the US. Does this mean NFL TOTAL, SPREAD, and ML are
  hyper-efficiently priced — potentially more efficient than NBA game lines?
- If NFL game lines are hyper-efficient: should min_edge be HIGHER than 5% (T2) to filter
  false edges? Could NFL game lines require 6-7% min_edge?
- Empirical σ of NFL outcomes: full-game spread σ, total σ, team-total σ.
  (Model needs: GAME_SIGMA["NFL"] = {total: ?, spread: ?, team: ?, ml: ?})
- NFL ML_DOG odds range: +120 to +350. At these odds, CV is very high (1.0 to 1.6).
  Is T3 with 8% min_edge correct, or does NFL's market efficiency justify T2?
- **Recommended tier for each NFL game line.**

---

## SECTION 11: Portfolio Variance — Correlated Picks

Individual pick variance is only half the story. When the model posts 5-10 picks per session,
their outcomes are correlated. Portfolio variance determines bankroll risk.

### 11A. Same-game correlation

When the model bets multiple markets in the same game:
- NBA: TOTAL over + ML_FAV + TEAM_TOTAL over (same game). These are correlated.
  If the game goes to a high-scoring blowout, all three win together; if slow pace, all lose.
  What is the empirical correlation between NBA game total outcome and team ML outcome?
  Between game total and team total outcome?
- MLB: If the model bets K over + NRFI + game TOTAL under in the same game:
  Strong pitching → more Ks AND more NRFI AND lower total. These are positively correlated.
  What is the empirical correlation between pitcher K count and NRFI outcome?
  Between game total and K count?
- NHL: SOG over on the home team + home ML_FAV: are these correlated?
  (More shots → more likely to win → correlated)
- Should there be a same-game pick cap across all market types?
  (The model already caps per-game for parlays; should it cap for the full card too?)

### 11B. Same-sport same-night correlation

When the model bets 5 NBA picks on the same slate:
- Are NBA picks on a 10-game slate somewhat correlated (shared factors: refs, weather dome,
  national TV vs local broadcast)?
- Is there a "high-scoring night" phenomenon where pace league-wide affects all totals?
  If yes, betting 5 NBA TOTAL overs on the same night is riskier than 5 independent bets.
- What is the empirical cross-game correlation for: NBA game totals on the same night?
  NBA player PTS overs on the same night?
- Does this correlation justify reducing SPORT_UNIT_CAP below what individual Kelly suggests?

### 11C. Portfolio variance and the 12u/day cap

The model has a hard 12u/day cap across all sports.

- At typical variance for T1/T2/T3 picks, what is the expected single-session variance of
  a 12u card? (Assume 10 picks averaging 1.2u each at -115 odds)
- What is the 95th percentile single-session loss given that variance?
  (e.g., "there's a 5% chance of losing X units in a single session")
- What is the expected maximum drawdown over a 100-session period (one season)?
- Is 12u/day the right cap given bankroll ruin prevention standards?
  Kelly theory suggests max bet = bankroll × Kelly fraction. If bankroll = 100u and
  Kelly fraction per pick = 1%, max daily total exposure at 10 picks = 10u. Is 12u right?
- Should the daily cap be lower for high-variance days (e.g., MLB-only slate with lots of
  T3 picks) and allow more for low-variance days (NBA with mostly T1 picks)?
  Or is the flat 12u simpler and good enough?

### 11D. Fractional Kelly and bankroll ruin probability

- What is the probability of 50% bankroll drawdown (ruin threshold) using the current VAKE
  system at 10 picks/day, assuming a 54% long-run win rate at -115 odds?
- How does this ruin probability change if all picks are T3 vs all T1?
- What fractional Kelly does each tier approximately represent?
  (e.g., "T1 at 5% edge uses approximately 1/3 Kelly, T3 at 6% edge uses approximately 1/4 Kelly")
- Is there an academic recommendation for the optimal Kelly fraction for sports betting
  with parameter uncertainty? (Most research says 1/4 to 1/2 Kelly is optimal)
- Does the model's VAKE system fall within this recommended range at each tier?

---

## SECTION 12: Cross-Cutting Calibration

### 12A. Edge threshold derivation from variance

The minimum edge threshold per tier should be derived from variance, not set arbitrarily.
The logic: if outcome variance is high, the model's edge estimate has high uncertainty →
need larger edge cushion before the pick is reliably +EV.

- Derive the minimum edge required per tier using this framework:
  1. Assume the model has projection error ε (normally distributed with σ_proj).
     At what minimum true edge does the pick remain +EV even after accounting for σ_proj?
  2. For T1 markets (low CV, stable projections): σ_proj is low → lower min_edge required.
  3. For T3 markets (high CV, volatile outcomes): σ_proj is high → higher min_edge required.
  4. Give concrete σ_proj estimates for each tier and the resulting min_edge recommendation.
- Current thresholds: T1=3%, T1B=3%, T2=5%, T3=6%, ML_DOG=8%.
  Are these consistent with the variance-based derivation above?
- Should min_edge vary by sport within a tier?
  (e.g., NFL game lines T2 needs 7% min_edge vs NBA game lines T2 needs 5%,
  because NFL projection error is higher for a weekly sport with less data)

### 12B. VAKE multiplier derivation from CV ratios

The variance multiplier (T1=1.00, T2=0.85, T3=0.65) and tier multiplier (T1=1.00, T2=0.90,
T3=0.60) should be derived from the CV ratios between tiers.

- If T1 has average CV of X and T3 has average CV of Y, Kelly says size should scale as
  approximately X²/Y² (bet proportional to 1/variance, and variance ∝ CV²×μ²).
  Given the empirical CV values from Section 1C: what should the T3/T1 sizing ratio be?
- Current T3/T1 combined multiplier = 0.65 × 0.60 = 0.39. Is this correct?
- Current T2/T1 combined multiplier = 0.85 × 0.90 = 0.77. Is this correct?
- Should the model collapse variance_mult and tier_mult into a single multiplier per tier
  (simpler, same result), or is there a reason to keep them separate?
- Should multipliers vary by stat within a tier?
  (e.g., 3PM has higher CV than ML_DOG, both T3 — should they have different multipliers?)

### 12C. STAT_CAP calibration

Current: SOG=6, all other stats=2.

For each stat below, recommend a STAT_CAP value based on:
- How many independent good picks are plausible per session (slate size × qualified players)?
- How correlated are multiple picks of the same stat on the same night (high correlation → lower cap)?
- What is the concentration risk if the same variance source affects all picks?

```
NBA:  PTS=?, AST=?, REB=?, 3PM=?, PRA=?, PR=?, PA=?, RA=?
      TOTAL=?, SPREAD=?, ML_FAV=?, ML_DOG=?, TEAM_TOTAL=?
NHL:  SOG=? (currently 6), AST=?, GOALS=?
      TOTAL=?, SPREAD=?, ML_FAV=?, ML_DOG=?
MLB:  K=?, OUTS=?, HA=?, HITS=?, TB=?, HRR=?
      NRFI=?, YRFI=?, TOTAL=?, SPREAD=?, ML_FAV=?, ML_DOG=?, TEAM_TOTAL=?
      F5_TOTAL=?, F5_SPREAD=?, F5_ML=?
NFL:  PASS_YARDS=?, RUSH_YARDS=?, REC_YARDS=?, RECEPTIONS=?, PASS_TDS=?
      RUSH_TDS=?, REC_TDS=?, INT=?, TOTAL=?, SPREAD=?, ML_FAV=?, ML_DOG=?, TEAM_TOTAL=?
```

### 12D. SPORT_UNIT_CAP calibration

Current: NBA=8u, WNBA=4u, NHL=5u, NFL=8u, MLB=8u.

- Derive recommended caps from:
  1. Maximum book limits per sport (higher limits → can bet more safely)
  2. CV per sport (higher CV → lower safe max size per pick)
  3. Kelly fraction at typical edges per sport
- Is NBA=8u appropriate? What does 1/4 Kelly say at 5% edge, 53% WR, -115 odds?
  (Kelly = (0.53×0.87-0.47)/0.87 ≈ 0.077 of bankroll. At 100u bankroll: 7.7u.
  1/4 Kelly: 1.9u. The 8u cap allows full Kelly, not fractional. Is this intentional?)
- WNBA=4u: is this calibrated to the CV differential, or just a conservative guess?
- NFL=8u: given NFL's weekly format (fewer picks per year, higher per-pick stakes),
  should NFL actually have a LOWER cap than NBA, not the same?
- **Recommend a final SPORT_UNIT_CAP for each sport with derivation.**

### 12E. KILLSHOT calibration

Current gate: tier=T1 strict, pick_score≥90, wp≥0.65, odds ∈ [-200, +110], 2/week max.
Eligible stats: {PTS, AST, SOG, 3PM}.

- At wp≥0.65 on a T1 stat at -115 odds: what is the expected ROI if win rate = 65%?
  (ROI = 0.65 × 0.87 - 0.35 = +0.22 — 22% expected ROI. Is this achievable?)
- Is wp≥0.65 the right threshold? What does the empirical win rate look like on picks
  where model projects 65%+ win probability? (Academic: models are usually overconfident)
- Should KILLSHOT require a higher win_prob for T3-adjacent stats?
  (3PM is T3 but KILLSHOT eligible at wp≥0.65 — 3PM has very high CV. Should 3PM
  require wp≥0.70 or be removed from KILLSHOT entirely?)
- PTS is T2 but KILLSHOT eligible: is it appropriate to promote a T2 pick to KILLSHOT?
  What does this do to the KILLSHOT expected variance?
- Sizing: KILLSHOT is 3u default, 4u if wp≥0.70 AND edge≥0.06. Is this consistent with
  VAKE theory? (3u for a pick where model says 65%+ WR seems aggressive — verify against Kelly)
- Is 2 KILLSHOT/week the right frequency cap? What is the probability of both KILLSHOTs
  losing in the same week (both at wp=0.65: P(both lose) = 0.35² ≈ 12%)?
  Is a 12% chance of a double KILLSHOT loss acceptable?
- **Recommended KILLSHOT stat eligibility for each sport. Which stats should be in
  {PTS, AST, SOG, 3PM}? Should K, HRR, RECEPTIONS be added? Should 3PM be removed?**

### 12F. T1B tier validity

T1B currently contains: REB, HITS, HA — all direction-restricted (unders-biased or gated).

- What is the economic purpose of a separate T1B? Is it:
  a) A different variance profile from T1 (justifying lower sizing)?
  b) A directional restriction only (unders work, overs don't)?
  c) Both?
- If T1B is purely directional (same variance as T1 but only bet unders): should it have
  the same VAKE multiplier as T1 (currently yes, both = 1.00)?
- Are REB, HITS, and HA correctly grouped together, or do they have different variance
  profiles that should put them in different tiers?
- Is T1B even needed, or can directional gating be handled within T1 itself?
- **Recommendation: keep T1B as-is, merge into T1 with directional gate, or merge into T2?**

---

## FINAL OUTPUT REQUIRED

### Table 1: Tier Recommendations

```
SPORT | STAT       | CUR  | REC  | CV   | EFFICIENCY | REASON
------|------------|------|------|------|------------|-------
NBA   | PTS        | T2   | ?    | ?    | High/Med/Low | ...
NBA   | AST        | T1   | ?    | ?    | ...
NBA   | REB        | T1B  | ?    | ?    | ...
NBA   | 3PM        | T3   | ?    | ?    | ...
NBA   | PRA        | T2   | ?    | ?    | ...
NBA   | PR         | T2   | ?    | ?    | ...
NBA   | PA         | T2   | ?    | ?    | ...
NBA   | RA         | T2   | ?    | ?    | ...
NBA   | TOTAL      | T2   | ?    | ?    | ...
NBA   | SPREAD     | T2   | ?    | ?    | ...
NBA   | ML_FAV     | T2   | ?    | ?    | ...
NBA   | ML_DOG     | T3   | ?    | ?    | ...
NBA   | TEAM_TOTAL | T2   | ?    | ?    | ...
WNBA  | PTS        | T2   | ?    | ?    | ...
WNBA  | AST        | T1   | ?    | ?    | ...
WNBA  | REB        | T1B  | ?    | ?    | ...
WNBA  | 3PM        | T3   | ?    | ?    | ...
WNBA  | TOTAL      | T2   | ?    | ?    | ...
WNBA  | SPREAD     | T2   | ?    | ?    | ...
WNBA  | ML_FAV     | T2   | ?    | ?    | ...
WNBA  | ML_DOG     | T3   | ?    | ?    | ...
NHL   | SOG        | T1   | ?    | ?    | ...
NHL   | AST        | T1   | ?    | ?    | ...
NHL   | GOALS      | T3   | ?    | ?    | ...
NHL   | TOTAL      | T2   | ?    | ?    | ...
NHL   | SPREAD     | T2   | ?    | ?    | ...
NHL   | ML_FAV     | T2   | ?    | ?    | ...
NHL   | ML_DOG     | T3   | ?    | ?    | ...
MLB   | K          | T1   | ?    | ?    | ...
MLB   | OUTS       | T2   | ?    | ?    | ...
MLB   | HA         | T1B  | ?    | ?    | ...
MLB   | HITS       | T1B  | ?    | ?    | ...
MLB   | TB         | T2   | ?    | ?    | ...
MLB   | HRR        | T1   | ?    | ?    | ...
MLB   | NRFI       | T3   | ?    | ?    | ...
MLB   | YRFI       | T3   | ?    | ?    | ...
MLB   | TOTAL      | T2   | ?    | ?    | ...
MLB   | SPREAD     | T2   | ?    | ?    | ...
MLB   | ML_FAV     | T2   | ?    | ?    | ...
MLB   | ML_DOG     | T3   | ?    | ?    | ...
MLB   | TEAM_TOTAL | T2   | ?    | ?    | ...
MLB   | F5_TOTAL   | T2   | ?    | ?    | ...
MLB   | F5_SPREAD  | T2   | ?    | ?    | ...
MLB   | F5_ML      | T2   | ?    | ?    | ...
NFL   | PASS_YARDS | none | ?    | ?    | ...
NFL   | RUSH_YARDS | none | ?    | ?    | ...
NFL   | REC_YARDS  | none | ?    | ?    | ...
NFL   | RECEPTIONS | T1*  | ?    | ?    | ...
NFL   | PASS_TDS   | none | ?    | ?    | ...
NFL   | RUSH_TDS   | none | ?    | ?    | ...
NFL   | REC_TDS    | none | ?    | ?    | ...
NFL   | INT        | none | ?    | ?    | ...
NFL   | YARDS      | T2*  | ?    | ?    | ...
NFL   | TDS        | T3*  | ?    | ?    | ...
NFL   | TOTAL      | none | ?    | ?    | ...
NFL   | SPREAD     | none | ?    | ?    | ...
NFL   | ML_FAV     | none | ?    | ?    | ...
NFL   | ML_DOG     | none | ?    | ?    | ...
NFL   | TEAM_TOTAL | none | ?    | ?    | ...
```

### Table 2: CV Reference Table

```
STAT         | SPORT | WITHIN-PLAYER CV | DISTRIBUTION SHAPE    | P(outcome=0)
-------------|-------|------------------|-----------------------|-------------
PTS          | NBA   | ?                | Normal / Right-skewed | ~0%
AST          | NBA   | ?                | Poisson / NB          | ~5%
REB          | NBA   | ?                | ...                   | ~2%
3PM          | NBA   | ?                | NB bimodal            | ~30%
PTS          | WNBA  | ?                | ...                   | ...
[continue for all stats]
```

### Table 3: Calibration Parameters

```
1. Min edge per tier:
   T1   = ?%  (current 3%)
   T1B  = ?%  (current 3%)
   T2   = ?%  (current 5%)
   T3   = ?%  (current 6%)
   ML_DOG override = ?%  (current 8%, all sports)
   YRFI override   = ?%  (current 8%)
   NFL game lines  = ?%  (may differ from NBA/MLB T2)

2. VAKE variance multiplier per tier:
   T1  = ?   (current 1.00)
   T1B = ?   (current 1.00)
   T2  = ?   (current 0.85)
   T3  = ?   (current 0.65)

3. VAKE tier multiplier per tier:
   T1  = ?   (current 1.00)
   T1B = ?   (current 1.00)
   T2  = ?   (current 0.90)
   T3  = ?   (current 0.60)

4. SPORT_UNIT_CAP per sport:
   NBA  = ?u  (current 8u)
   WNBA = ?u  (current 4u)
   NHL  = ?u  (current 5u)
   MLB  = ?u  (current 8u)
   NFL  = ?u  (current 8u)

5. STAT_CAP per stat: [full table as requested in Section 12C]

6. KILLSHOT eligible stats per sport:
   NBA/WNBA: currently {PTS, AST, SOG, 3PM} — remove 3PM? add K/HRR?
   NHL:      currently {SOG} — correct?
   MLB:      currently none explicitly — should K or HRR be eligible?
   NFL:      not yet defined — RECEPTIONS? PASS_YARDS?

7. Daily total cap:
   Current: 12u/day. Recommended: ?u

8. T1B verdict:
   Keep as separate tier / Merge into T1 / Merge into T2

9. Kelly fraction per tier (informational — what fraction of full Kelly does VAKE represent):
   T1  ≈ ?× Kelly
   T2  ≈ ?× Kelly
   T3  ≈ ?× Kelly
```
