# Market Tier Research Prompt

Paste this into ChatGPT Deep Research or Claude with web search.

---

I am building a Python sports betting model that covers NBA, WNBA, NHL, MLB, and NFL. Every
market in the model is assigned to a tier. The tier determines the minimum edge required to
post a bet and the sizing applied to it. I need you to research the market efficiency profile
of every market the model trades and tell me definitively which tier each market belongs in.

**The tier system:**
- **T1** — most efficient market, tightest lines, sharpest pricing. Min edge: 3%. Full sizing.
- **T1B** — same edge threshold as T1 but lower volume / unders-biased markets. Min edge: 3%.
- **T2** — moderate efficiency. Min edge: 5%. Size reduced (85% variance mult × 90% tier mult).
- **T3** — lowest efficiency / highest variance / binary-adjacent. Min edge: 6%. Size heavily
  reduced (65% variance mult × 60% tier mult).

**What efficiency means in this context:**
A market is efficient when books price it accurately and sharp money quickly corrects any
mispricing. Efficient markets → edges are rare, small, and hard to find. Less efficient
markets → books are slower to correct, public money creates distortions, bigger edges exist.

Counter-intuitively, a LESS efficient market does NOT mean it belongs in a lower tier. It
means the model finds more edge there. The tier assignment reflects where the model can
realistically operate: high-efficiency markets (books are sharp) need a lower edge threshold
because when an edge exists it tends to be real. Low-efficiency/high-variance markets need a
HIGHER edge threshold because noise produces false edges.

**The key question for each market:**
1. How efficiently do sharp books (Pinnacle, market makers) price this market?
2. How much variance is in the outcome vs the projection (CV = σ/μ)?
3. Does public money materially distort this market?
4. What are book limits on this market (low limit = book is uncertain)?
5. How quickly do lines move after opening (fast = sharp market)?
6. Is there a structural bias (over/under skew) in this market?
7. Based on all of the above: what min_edge threshold makes a bet here +EV after vig?

**Current model state (what I need you to validate or correct):**
```
T1  (min_edge 3%): AST, SOG, K, HRR, REC (NFL-planned)
T1B (min_edge 3%): REB, HITS, HA
T2  (min_edge 5%): PTS, PRA, PR, PA, RA, OUTS, TB, TOTAL, SPREAD, ML_FAV,
                   TEAM_TOTAL, F5_TOTAL, F5_SPREAD, F5_ML, YARDS (NFL-planned)
T3  (min_edge 6%): 3PM, ML_DOG, NRFI, YRFI, TDS (NFL-planned), GOALS (NHL-planned)
```

**Current VAKE sizing multipliers (what I need you to validate or correct):**
- Base unit from edge: edge 3–5% → 0.50u | 5–7% → 0.75u | 7–9% → 1.00u | 9%+ → 1.25u
- Variance multiplier: T1=1.00, T1B=1.00, T2=0.85, T3=0.65
- Tier multiplier:     T1=1.00, T1B=1.00, T2=0.90, T3=0.60
- Final size = base × variance_mult × tier_mult
- Example: T1 at 5% edge → 0.75 × 1.00 × 1.00 = 0.75u
           T2 at 5% edge → 0.75 × 0.85 × 0.90 = 0.57u
           T3 at 5% edge → 0.75 × 0.65 × 0.60 = 0.29u

**Current KILLSHOT gate:**
- Only fires when: tier=T1 strict, pick_score≥90, win_prob≥0.65, odds ∈ [-200,+110]
- Eligible stats: {PTS, AST, SOG, 3PM} — one from each of the major sports
- Max 2 KILLSHOT picks per week

---

## SECTION 1: The Efficiency Framework

Before covering individual markets, establish the framework:

- What is the academic/industry consensus on how to measure market efficiency in sports betting?
  Is vig alone sufficient, or do CLV (closing line value) data, sharp action, and limit size
  all need to be combined?
- In a market the model is operating in (CO-legal books: DraftKings, FanDuel, BetMGM, Caesars,
  Fanatics, theScore Bet, Hard Rock, BetRivers, Bet365), how efficient are retail books vs
  Pinnacle? Should the model use Pinnacle as the efficiency benchmark?
- What is the empirical relationship between vig percentage and market efficiency?
  (e.g., -115/-115 = 4.5% vig → is this more or less efficient than -110/-110 = 4.5%?)
  Give the hold percentage formula and how it correlates with sharpness.
- For player props specifically: are they uniformly less efficient than game lines, or does
  it depend on the stat? What does the research show?
- What minimum CLV (closing line value) should the model target per tier to be profitable
  long-term? (e.g., T1 CLV ≥ 1.5%, T2 CLV ≥ 2.5%, T3 CLV ≥ 3.5%?)
- Do retail CO-legal books limit winning bettors faster on some markets than others?
  Which markets get limited soonest (indicating the book knows you're finding real edge)?
- What is the empirical win rate required at typical odds for each tier to be +EV?
  (e.g., at -115 you need 53.5% WR; at -110 you need 52.4%)

---

## SECTION 2: NBA Player Props

### PTS (Points) — currently T2

- How efficiently do books price NBA player points props?
  Compare: does Pinnacle's closing line for PTS move more or less than AST/REB after opening?
- What is the empirical CV (σ/μ) for NBA player PTS props (2022-2025)?
  By role tier: starter vs sixth man vs rotation?
- Do books shade NBA PTS overs due to public bias (public loves overs on star scorers)?
  If yes, does this make overs structurally -EV and unders structurally +EV at certain odds?
- Is PTS correctly placed in T2 or should it be T1 (if efficiently priced and model is good)
  or T3 (if variance is too high for 5% min_edge to be reliable)?
- What typical vig do books charge on NBA PTS props? (-115/-115 or wider?)
- Should PTS be KILLSHOT eligible? It currently is — is this correct for a T2 stat?

### AST (Assists) — currently T1

- How efficiently do books price NBA AST props? Is it more or less efficiently priced than PTS?
- What is the empirical CV for NBA AST props? Is it lower variance than PTS (justifying T1)?
- Is the AST market large enough that sharp action keeps it efficient, or is it thin enough
  that mispricing persists longer?
- What does the research show on over/under bias for AST? (Point guards with high assist props
  — do books over- or under-adjust for game pace, turnovers, etc.?)
- Should the T1 3% min_edge threshold be correct for AST, or does the market require more cushion?
- Is AST correctly KILLSHOT eligible at the current gate (wp≥0.65)?

### REB (Rebounds) — currently T1B

- Why T1B and not T1? Is REB actually less efficiently priced than AST?
  What is the empirical CV for REB vs AST? Which is higher variance?
- What is the over/under bias in the REB market? (Does the public bet REB overs on big men?)
- Should REB be promoted to T1 or demoted to T2? Justify with market efficiency data.
- For REB unders specifically (T1B bias): are unders systematically priced incorrectly?
  What win rate do REB unders produce vs overs at the same line?

### 3PM (Three-Pointers Made) — currently T3

- 3PM is bimodal (specialist shooters have on/off nights). Is T3 correct?
- What is the empirical CV for 3PM? Is it higher than PTS or REB?
- What vig do books charge on 3PM props? Is it wider than PTS/AST (indicating less confidence)?
- Does the public over-bet 3PM overs on known shooters? (Public loves Curry/Thompson overs)
  If yes, are 3PM unders structurally better value?
- Is 3PM currently KILLSHOT eligible (yes, in {PTS, AST, SOG, 3PM}) — should it be?
  Given it's T3, does it make sense to allow it to KILLSHOT?
- Should 3PM have a higher min_edge than the current T3 6%? What threshold is correct?

### Combo Props (PRA, PR, PA, RA) — currently all T2

PRA = points+rebounds+assists. PR = points+rebounds. PA = points+assists. RA = rebounds+assists.

- Are combo props more or less efficiently priced than their component stats?
  (Hypothesis: books set combo lines as sum of components, ignoring correlation → systematic
  underpricing or overpricing)
- What is the empirical correlation between PTS+REB+AST for the same player game?
  Does this create exploitable edges in PRA that don't exist in PTS alone?
- Is the vig on combo props wider or narrower than single-stat props?
- Should all four combos be T2, or do some (PRA = most correlated, most complex) deserve T3?
- Do books offer combo props across all CO-legal books consistently, or only some?
  (Limited availability may reduce the sample size and justify a different tier.)

---

## SECTION 3: WNBA Player Props

WNBA uses SaberSim projections and the same market structure as NBA.

- Are WNBA player prop markets more or less efficiently priced than NBA?
  (Hypothesis: lower public interest → thinner markets → more mispricing → better edges)
- What is the typical vig on WNBA props vs NBA props at the same books?
- Do CO-legal books consistently offer WNBA player_points, player_rebounds, player_assists?
  Or is coverage spotty (low liquidity → inefficient market)?
- Should WNBA props be in the same tiers as NBA props, or should all WNBA props be one tier
  lower (e.g., NBA AST = T1, WNBA AST = T2) due to thinner markets?
- Is WNBA worth having separate tier assignments from NBA, or share the same tiers?
- What SPORT_UNIT_CAP is appropriate for WNBA? (Currently 4u — is this right given thinner
  markets and lower limits?)

---

## SECTION 4: NHL Player Props

### SOG (Shots on Goal) — currently T1, KILLSHOT eligible, STAT_CAP=6

- How efficiently do books price NHL SOG props?
  Is it more or less efficiently priced than NBA PTS?
- What is the empirical CV for NHL SOG props (2022-2025)?
  By position: forward vs defenseman?
- What vig do books charge on SOG? (-115/-115 standard?)
- Is SOG a high-volume market (justified STAT_CAP=6) or should the cap be lower?
- Should SOG be KILLSHOT eligible? It currently is. Given it's a niche stat,
  is the model likely to find genuine T1-level edges at wp≥0.65?
- NHL as a sport: is it a less efficient market than NBA due to lower public interest?
  If yes, should all NHL props be one tier lower than equivalent NBA props?

### AST (Assists) — currently T1 for NHL (same mapping as NBA)

- NHL assists is a very different market from NBA assists. Is it as efficiently priced?
- What is the typical line for NHL AST? (0.5 seems dominant — is this a binary market?)
- If it's primarily O/U 0.5, is it better modeled as Bernoulli rather than Poisson?
- Should NHL AST be T1 (same as NBA AST) or a different tier given it's a sparser market?

### GOALS (NHL Goals) — currently T3, not yet in PROP_MARKETS (planned)

- Does The Odds API offer player_goals for NHL? What is the market key?
- What is the empirical distribution for NHL player goals per game?
  (Most players score 0 in most games — this is very binary at line 0.5)
- Is T3 the right tier for NHL goals, or should it be even more restricted?
  Given the rarity, should there be a minimum win_prob floor (like HRR G13B gate in MLB)?
- What vig do books charge on NHL goal props?
- Should NHL goals even be in the model at all given how rare they are?

---

## SECTION 5: MLB Pitcher Props

### K (Strikeouts) — currently T1 (NB distribution, r=5.0)

- How efficiently do books price MLB pitcher strikeout props?
  Are these among the most efficiently priced props across all sports?
  (Hypothesis: high public interest in K props → sharp action → efficient market)
- What is the empirical CV for pitcher K per start (2022-2024)?
  Does it vary significantly across pitcher archetypes (power pitcher vs contact pitcher)?
- The model kills K unders entirely due to SaberSim conservative IP bias.
  Are K overs at line ≥6.0 correctly T1, or should they be T2 given the IP dependency?
- What vig do books charge on MLB K props? Is it wider than NBA PTS?
- Is K correctly at T1 or should it be T2 given the IP/game-script dependency?

### OUTS (Pitcher Outs Recorded) — currently T2

- How efficiently do books price OUTS vs K? Are they the same market with different units?
  (OUTS = outs recorded = innings × 3; K is different — a pitcher can go 6IP with only 4K)
- What vig do books typically charge on OUTS? Is it wider or narrower than K?
- Is T2 correct for OUTS, or should it be T1B (similar to K but more variance due to early
  hook risk)?
- Should OUTS have a minimum line gate (model currently has one, but what's the right threshold)?

### HA (Pitcher Hits Allowed) — currently T1B

- How efficiently do books price pitcher hits allowed props?
- What is the empirical CV for HA? Is it higher or lower than K?
- Is T1B (unders only, 3% min_edge) correct for HA?
  Is there an over/under bias in HA (books shade one direction)?
- What vig do books charge on HA? Is it a soft market (few sharp bettors)?

---

## SECTION 6: MLB Batter Props

### HITS (Batter Hits) — currently T1B

- How efficiently do books price batter hits props?
- What is the empirical CV for batter hits per game?
  (Low count stat — mean ~1.2 hits/game, so CV is high)
- Is HITS correctly T1B, or should it be T2?
- What vig do books charge on batter HITS? Is this a soft market?
- Should HITS overs and unders be treated differently (model currently T1B = unders bias)?

### TB (Total Bases) — currently T2

- How efficiently do books price batter total bases props?
- What is the empirical CV for TB? (Higher than HITS due to extra base hit variance)
- Is T2 correct for TB, or should it be T1B (same structure as HITS but more variance)?
- What vig do books charge on TB? Wider than HITS?

### HRR (Hits + Runs + RBIs) — currently T1 (NB distribution, r=1.5)

- HRR is a combo stat (H+R+RBI). How efficiently do books price this market?
  Is it more or less efficient than its component stats (HITS, runs, RBIs separately)?
- What is the typical HRR line? (1.5 seems dominant — is this essentially a binary market?)
- The model has a G13B gate: WP floors by HRR line bucket (≤0.5 needs WP≥0.58,
  >0.5 needs WP≥0.65). Are these floors correct?
- Is T1 correct for HRR, or is the batter-total correlation structure (hits correlated with
  R and RBI — same game dependency) better served by T2?
- What vig do books charge on HRR? Is it a sharp or soft market?

---

## SECTION 7: MLB Game Lines

### NRFI (No Run First Inning) — currently T3, min_edge 6%

- How efficiently do books price NRFI? Is this a sharp or soft market?
- What is the typical vig on NRFI at CO-legal books? (-115/-115 or wider?)
- Is T3 correct for NRFI, or should it be T2?
  (NRFI has a known formula: P(NRFI) ≈ (1-p_home)×(1-p_away) — is this well-understood
  by books, making it efficiently priced? Or is it under-analyzed?)
- What does the research show on over/under bias for NRFI?
  (Does the public bet YRFI due to entertainment bias? If yes, NRFI unders are +EV.)

### YRFI (Yes Run First Inning) — currently T3, min_edge 8% (hardcoded override)

- Is YRFI more or less efficiently priced than NRFI?
- The model uses 8% min_edge for YRFI vs 6% for NRFI. Is this differential correct?
- Should YRFI even be in the model? What does the historical win rate show for YRFI overs?

### F5 Lines (F5_TOTAL, F5_SPREAD, F5_ML) — currently all T2

F5 = First 5 innings markets (total, spread, ML).

- Are F5 markets more or less efficiently priced than full-game equivalents?
  (Hypothesis: F5 markets have less liquidity → less sharp action → more mispricing)
- What vig do books charge on F5 markets vs full-game? (Typically wider on F5?)
- Should F5 markets be T1B (less efficient, more edge, but lower volume) rather than T2?
  Or are they appropriately T2?
- Is F5 ML more or less efficiently priced than full-game ML?

### MLB Full-Game Lines (TOTAL, SPREAD/Runline, ML_FAV, ML_DOG, TEAM_TOTAL) — T2/T3

- MLB runline (always ±1.5) vs NBA/NHL spread (variable): does the fixed runline make this
  market more or less efficient than other sports' spreads?
- Is ML_DOG in MLB correctly T3 (min_edge 8% hardcoded)? MLB dogs can be +200 to +400 —
  are these closer to lottery tickets than to genuine value plays?
- Is ML_FAV in MLB correctly T2?
- Is TEAM_TOTAL in MLB correctly T2? Is it efficiently priced?
- Are MLB TOTAL (game total) markets efficiently priced? Is T2 correct?

---

## SECTION 8: NBA/WNBA/NHL Game Lines

### TOTAL (Game Total) — currently T2 across all sports

- Is the NBA game total market efficiently priced? What about WNBA? What about NHL?
- Is T2 the right tier for game totals, or are they so efficiently priced that they should
  be T1 (rare edge = reliable signal when found)?
- Do books shade totals in any direction based on public betting patterns?
  (Public loves overs in NBA — do books adjust?)

### SPREAD — currently T2 across all sports

- Is the NBA spread more or less efficiently priced than the NBA game total?
- Is the NHL puck line (±1.5 fixed) similarly efficient to the NBA variable spread?
- Should SPREAD ever be T1, or is the variance too high to justify the lower edge threshold?

### ML_FAV vs ML_DOG — currently T2 and T3 respectively

- Is the T3 assignment for ML_DOG correct across ALL sports, or does it depend on the sport?
  (NHL ML is a much tighter market than MLB ML — should NHL ML_DOG be T2?)
- What is the empirical win rate of ML_DOG picks in NBA vs NHL vs MLB?
- The model uses min_edge=8% for ML_DOG (hardcoded override). Is 8% the right threshold,
  or should it vary by sport?
- Is ML_FAV correctly T2? Should heavy favorites (>-200) be gated out?

### TEAM_TOTAL — currently T2

- Are NBA/NHL team totals as efficiently priced as game totals, or are they softer?
  (Less volume = less sharp action = more mispricing?)
- Should TEAM_TOTAL be T1B (softer market, more edge, but lower volume and confidence)?

---

## SECTION 9: NFL Player Props (Planned)

The model plans to add NFL. Every new stat needs a tier assignment.

### PASS_YARDS — tier unknown

- Is the NFL passing yards market efficiently priced?
  (High public interest in Mahomes/Allen stats → sharp market → efficient?)
- What is the empirical CV for QB passing yards?
- Should PASS_YARDS be T1 (efficiently priced, tight lines) or T2?
- What minimum edge threshold is appropriate?

### RUSH_YARDS — tier unknown

- Is the rush yards market as efficient as pass yards, or softer?
  (RB props have less public interest than QB → potentially less efficient?)
- What is the empirical CV for RB rushing yards? (Higher than PASS_YARDS due to game script?)
- Should RUSH_YARDS be T1 or T2?

### REC_YARDS — tier unknown

- How efficiently do books price receiving yards? Compare to RUSH_YARDS.
- Should REC_YARDS be T1 or T2?

### RECEPTIONS — currently pre-assigned T1 in model

- Is T1 correct for receptions? Are receptions props efficiently priced?
- Compare to NBA AST: similar low-variance count stat, efficient market?
- What vig do books charge on receptions? Is it tight?

### PASS_TDS / RUSH_TDS / REC_TDS — tier unknown

- TD props are rare events (binary/Bernoulli-like). Does this make them T3 like 3PM and NRFI?
- What is the vig on TD props? (Wider vig = lower efficiency = need more edge)
- Should all TD markets be T3 with min_edge ≥ 6%, or is PASS_TDS (higher volume, line 0.5+)
  more efficiently priced than RUSH_TDS/REC_TDS?

### INT (Interceptions) — tier unknown

- INT is extremely rare and overdispersed. Should it be T3 or excluded entirely?
- Is the INT market even worth building out given volume constraints?

### YARDS (combo: pass+rush or rec+rush) — currently pre-assigned T2

- Is T2 correct for NFL combo yards markets?
- Are these markets soft (less sharp attention) or efficiently priced?

### NFL Game Lines (TOTAL, SPREAD, ML_FAV, ML_DOG, TEAM_TOTAL) — tier unknown

- NFL is the largest betting market in the US. Does this make NFL game lines the MOST
  efficiently priced market in the model?
- If NFL game lines are hyper-efficient, should the min_edge threshold be HIGHER than
  other sports to filter out false edges (e.g., T2 min_edge = 7% for NFL instead of 5%)?
- Should NFL ML_DOG also be T3 with 8% min_edge, or does the NFL market price dogs
  differently than MLB/NBA?

---

## SECTION 10: Cross-Cutting Calibration

### Edge Threshold Calibration

- The current thresholds are: T1=3%, T1B=3%, T2=5%, T3=6%, ML_DOG=8%.
  Are these correct? Derive from first principles:
  - At typical T1 odds (-115), what edge is needed to be +EV after vig?
  - At typical T3 odds (+105 to +130), what edge is needed?
  - Do the thresholds need to differ per sport (e.g., NFL T2 needs higher threshold than NBA T2)?
- What does academic research show about the minimum CLV needed to profit long-term?
  Is 3% edge at T1 enough to produce positive CLV consistently?

### VAKE Multiplier Calibration

- Current sizing: T2 gets 85% × 90% = 76.5% of T1 size. T3 gets 65% × 60% = 39% of T1 size.
- Are these multipliers consistent with Kelly fraction theory?
  (Kelly says bet proportional to edge / variance. T3 has both lower win_prob and higher
  variance — does 39% of T1 size match what Kelly would calculate?)
- Derive the theoretically correct sizing ratio between tiers using Kelly:
  - Assume T1 pick: 53% win rate, -115 odds (edge ≈ 3%)
  - Assume T2 pick: 53% win rate, -115 odds (edge ≈ 3%) but higher variance
  - Assume T3 pick: 55% win rate, +105 odds (edge ≈ 6%) but very high variance
  - What should the Kelly fraction be for each? What sizing ratio does this imply?
- Should T2 and T3 multipliers be per-sport (e.g., WNBA T2 gets less than NBA T2 due to
  lower limits and liquidity)?

### STAT_CAP Calibration (Max Picks Per Stat Per Run)

Current caps: SOG=6, all other stats=2.

- Is SOG=6 correct? Why does SOG get more picks than other stats?
  (Hypothesis: SOG is on every NHL player — high volume — but should there be a per-GAME cap?)
- Should AST have a cap of 2, or can 3-4 AST picks per run be appropriate?
  (Multiple good AST plays on a given night is plausible for a 10-game NBA slate)
- Should PTS have a cap higher than 2? (10 NBA games = 20+ PTS props to evaluate)
- Should MLB K cap be 2 (one starter per team, max 2 games with K plays), or higher?
- Should HRR cap be higher than 2 given multiple batters per team?
- Should game lines (TOTAL, SPREAD, ML) have a separate cap per sport?
  (e.g., max 3 NBA totals per run, max 2 MLB ML picks per run)
- Recommend concrete STAT_CAP values for every stat in the model.

### SPORT_UNIT_CAP Calibration (Max Units Per Single Pick Per Sport)

Current caps: NBA=8u, WNBA=4u, NHL=5u, NFL=8u, MLB=8u.

- Are these caps correct? Derive from:
  - How liquid is each market (higher liquidity → higher limit → larger size possible)?
  - What is the maximum Kelly-recommended bet size at typical edges in each sport?
  - Do CO-legal books limit winners faster in some sports (implying lower safe cap)?
- WNBA=4u vs NBA=8u: is this differential correct given WNBA's thinner markets?
- NHL=5u: is this right given NHL is less liquid than NBA but more liquid than WNBA?
- What should NFL's cap be? (NFL is the largest market, but weekly format = lower n.)

### KILLSHOT Gate Calibration

Current gate: tier=T1 strict, score≥90, wp≥0.65, odds ∈ [-200,+110], stats={PTS,AST,SOG,3PM}.

- Is score≥90 the right threshold? What win rate does score≥90 produce empirically?
- Is wp≥0.65 correct? Should it be higher (0.68? 0.70?) given KILLSHOT is highest-conviction?
- Is odds ∈ [-200,+110] the right range? Should heavy favorites (-150 to -200) be in KILLSHOT?
  Or does the juice erode edge too much at -150+?
- Should KILLSHOT allow T1B stats (e.g., REB unders, HITS unders) at high confidence?
  Or should it stay strictly T1?
- Are the correct stats eligible for KILLSHOT?
  - PTS: currently eligible but T2 stat — should a T2 stat be KILLSHOT eligible?
  - AST: T1 — correct.
  - SOG: T1 — correct.
  - 3PM: T3 — should a T3 stat be KILLSHOT eligible?
  - What NFL stats should be eligible for KILLSHOT once NFL launches?
  - What MLB stats (K? HRR?) should be KILLSHOT eligible?
- Is 2 KILLSHOT picks/week the right cap? Should it be lower (1) or higher (3)?
- What is the historical win rate of plays meeting all KILLSHOT criteria?
  (Academic/industry data on high-confidence prop play win rates at wp≥0.65)

### T1B Tier Validity

T1B is a sub-tier for lower-volume, unders-biased markets (REB, HITS, HA).

- Is T1B a justified separate tier, or should REB/HITS/HA just be T1 or T2?
- What makes a market "T1B" rather than T1? Is the sole distinction that the model
  only trusts unders in these markets, or is there also an efficiency difference?
- Should T1B have the same min_edge as T1 (3%) or a different threshold?
- Are there other markets that should be T1B but currently aren't?
- Recommendation: keep T1B as-is, merge into T1, or merge into T2?

### Cross-Sport Tier Consistency

- Should AST be T1 in both NBA and NHL, or is NHL AST a different efficiency profile?
  (NHL AST = 0.5 line dominant = essentially Bernoulli = different from NBA AST at 4.5-7.5)
- Should ML_DOG always be T3 regardless of sport, or does sport matter?
  (NHL ML is a much sharper market than MLB ML)
- Should game totals always be T2 regardless of sport?
  (NFL total is the most-bet market in the US — possibly so efficient it should be T1 or even excluded)
- Is it correct that NRFI/YRFI are T3 while game totals are T2? They're both MLB totals
  but first-inning totals are structurally different. Justify the differential.

---

## FINAL OUTPUT REQUIRED

Provide a complete recommended tier table in this exact format:

```
SPORT   | STAT         | CURRENT TIER | RECOMMENDED TIER | REASON (1 line)
--------|--------------|--------------|------------------|----------------
NBA     | PTS          | T2           | ?                | ...
NBA     | AST          | T1           | ?                | ...
NBA     | REB          | T1B          | ?                | ...
NBA     | 3PM          | T3           | ?                | ...
NBA     | PRA          | T2           | ?                | ...
NBA     | PR           | T2           | ?                | ...
NBA     | PA           | T2           | ?                | ...
NBA     | RA           | T2           | ?                | ...
NBA     | TOTAL        | T2           | ?                | ...
NBA     | SPREAD       | T2           | ?                | ...
NBA     | ML_FAV       | T2           | ?                | ...
NBA     | ML_DOG       | T3           | ?                | ...
NBA     | TEAM_TOTAL   | T2           | ?                | ...
WNBA    | All props    | same as NBA  | same or differ?  | ...
NHL     | SOG          | T1           | ?                | ...
NHL     | AST          | T1           | ?                | ...
NHL     | GOALS        | T3           | ?                | ...
NHL     | TOTAL        | T2           | ?                | ...
NHL     | SPREAD       | T2           | ?                | ...
NHL     | ML_FAV       | T2           | ?                | ...
NHL     | ML_DOG       | T3           | ?                | ...
MLB     | K            | T1           | ?                | ...
MLB     | OUTS         | T2           | ?                | ...
MLB     | HA           | T1B          | ?                | ...
MLB     | HITS         | T1B          | ?                | ...
MLB     | TB           | T2           | ?                | ...
MLB     | HRR          | T1           | ?                | ...
MLB     | NRFI         | T3           | ?                | ...
MLB     | YRFI         | T3           | ?                | ...
MLB     | TOTAL        | T2           | ?                | ...
MLB     | SPREAD       | T2           | ?                | ...
MLB     | ML_FAV       | T2           | ?                | ...
MLB     | ML_DOG       | T3           | ?                | ...
MLB     | TEAM_TOTAL   | T2           | ?                | ...
MLB     | F5_TOTAL     | T2           | ?                | ...
MLB     | F5_SPREAD    | T2           | ?                | ...
MLB     | F5_ML        | T2           | ?                | ...
NFL     | PASS_YARDS   | (none)       | ?                | ...
NFL     | RUSH_YARDS   | (none)       | ?                | ...
NFL     | REC_YARDS    | (none)       | ?                | ...
NFL     | RECEPTIONS   | T1 (planned) | ?                | ...
NFL     | PASS_TDS     | (none)       | ?                | ...
NFL     | RUSH_TDS     | (none)       | ?                | ...
NFL     | REC_TDS      | (none)       | ?                | ...
NFL     | INT          | (none)       | ?                | ...
NFL     | YARDS        | T2 (planned) | ?                | ...
NFL     | TDS          | T3 (planned) | ?                | ...
NFL     | TOTAL        | (none)       | ?                | ...
NFL     | SPREAD       | (none)       | ?                | ...
NFL     | ML_FAV       | (none)       | ?                | ...
NFL     | ML_DOG       | (none)       | ?                | ...
NFL     | TEAM_TOTAL   | (none)       | ?                | ...
```

Also provide:
1. Recommended min_edge per tier (current: T1=3%, T1B=3%, T2=5%, T3=6%, ML_DOG=8%)
2. Recommended VAKE variance multipliers per tier (current: T1=1.00, T1B=1.00, T2=0.85, T3=0.65)
3. Recommended VAKE tier multipliers per tier (current: T1=1.00, T1B=1.00, T2=0.90, T3=0.60)
4. Recommended STAT_CAP per stat (current: SOG=6, all others=2)
5. Recommended SPORT_UNIT_CAP per sport (current: NBA=8u, WNBA=4u, NHL=5u, NFL=8u, MLB=8u)
6. Recommended KILLSHOT eligible stats per sport
7. Verdict on T1B: keep, merge into T1, or merge into T2
