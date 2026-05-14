# MLB Research Findings

**Research agenda:** `docs/MLB_RESEARCH_AGENDA.md`  
**Session protocol:** Fill each section as researched. Commit after every completed section.

---

## Status

| Market | Status | Verdict |
|--------|--------|---------|
| TB | pending | — |
| HRR | pending | — |
| NRFI | pending | — |
| K | pending | — |
| OUTS | pending | — |
| HITS | pending | — |
| HA | pending | — |
| ER | pending | — |
| TEAM_TOTAL | pending | — |
| ML_FAV | pending | — |
| ML_DOG | pending | — |
| F5_TOTAL | pending | — |
| F5_ML | pending | — |
| F5_SPREAD | pending | — |
| SPREAD | pending | — |
| Cross-cutting | pending | — |

---

## TB (Total Bases)

**Verdict:** pending

### Distribution
- Best-fit distribution:
- Fitted parameters:
- P(TB > 1.5) correct vs Normal estimate:
- Does correct dist ever produce under edge at realistic lines?

### Projection inputs
- SaberSim component bias (singles/2B/3B/HR individually):
- Sum-of-components valid for TB?
- Mean error (SaberSim TB proj vs actual):

### Sigma / replacement
- mult=1.20 dataset and validity:
- Replacement for G14 clearance if non-Normal:

### Market structure
- TB 2.5 consistently available?
- TB 0.5 offered?
- Best-priced books:

### Situational factors
- Park factor impact (Coors, Oracle):
- Pitcher quality factored in current model?

### Gate/tier
- G13B (WP≥60%) redundant after fix?
- G14 replacement if non-Normal:
- T2 appropriate?

### Fix/kill decision
- Action:
- Validation requirement:

---

## HRR (Hits + Runs + RBIs)

**Verdict:** pending

### Distribution
- Best-fit distribution (per line bucket):
- P(HRR > 1.5) correct vs Normal estimate (avg batter projecting ~2.0):
- P(HRR > 0.5) correct estimate:

### Projection inputs
- H / R / RBI individual bias:
- Within-game correlation accounted for?
- Batting order encoded in SaberSim?
- Mean error across 1953 graded picks:

### Sigma / replacement
- mult=0.75 min=1.3 dataset and validity:
- Replacement for 1.5 line clearance:

### Market structure
- HRR 0.5 consistently available? Which books?
- HRR 1.5 odds consistency across books:
- HRR 2.5 consistently available?

### Situational factors
- Pitcher quality factored in current model?
- Game run environment incorporated?
- Park factor?

### Gate/tier
- G13B (WP≥55%) redundant after fix?
- HRR T1 (3%) appropriate post-fix?
- STAT_CAP=2 enforced in shadow?
- Separate tiering by line bucket?

### Fix/kill decision
- Will line 1.5 still produce picks after fix?
- 0.5 as standalone primary market?
- Action:
- Validation requirement:

---

## NRFI

**Verdict:** pending

### Base rate
- Actual 2025 first-inning NRFI rate from Stats API:
- Variation by team / park / context:

### Formula
- Independence assumption valid empirically?
- Offensive metrics that drive 1st-inning scoring beyond pitcher quality:
- 0.45 probability ceiling justified? Empirical max?

### FIP calibration
- Correct 2025 FIP constant:
- FIP-only vs ERA-only vs blend empirical test:
- Actual 2025 MLB ERA through current date:

### Missing inputs
- SaberSim MLB CSV: team offensive quality columns?
- Best public API for team offensive quality pre-game:
- Updated p_team_scores formula incorporating offense:

### Tier discrepancy
- Code path for T3 vs T2 logged picks — bug found?

### Fix/kill decision
- Team offense data available pre-game at scale?
- Action:
- Validation requirement:

---

## K (Strikeouts)

**Verdict:** pending

### Distribution
- Poisson vs Negative Binomial — AIC comparison:
- Negative Binomial r and p parameters if better fit:

### Projection inputs
- Mean bias (SaberSim K proj vs actual) across all graded picks:
- Bias by line bucket (3.5 / 4.5 / 5.5 / 6.5+):
- SaberSim: full-game completion assumed or partial outing modeled?
- Bulk/opener distinction in SaberSim?
- IP-related deflator viable?

### Sigma
- min=1.5 appropriate floor?

### Market structure
- Vig by line bucket:
- Lineup K% incorporated in market lines?
- Most consistent books for pitcher_strikeouts:

### Situational factors
- Rest / pitch count limit pre-game signal?
- Park / weather effect?

### Gate/tier
- Minimum K line gate (≥5.5)?
- K over (0/3 WR) — gate out?
- T1 (3%) appropriate given SaberSim bias?

### Fix/kill decision
- Uniform multiplier correction viable?
- Or non-uniform (by pitcher type / line)?
- Validation data requirement:
- Action:

---

## OUTS (Outs Recorded)

**Verdict:** pending

### Distribution
- Normal vs bimodal empirical test:
- Bimodal? (quality start vs early hook)
- % of variance predictable vs random (game script / manager hook):

### Projection inputs
- SaberSim OUTS source (IP column or derived):
- Mean bias (SaberSim OUTS proj vs actual):
- R² from regression of IP on pre-game variables:
- Bullpen workload captured by SaberSim?

### Sigma
- Actual σ of OUTS per start from Stats API:
- How many of 93 picks filtered if correct sigma used in G14?

### Market structure
- pitcher_outs consistently available?
- Typical line range (14.5 / 17.5 / 20.5):
- OUTS overs (53.8% WR) vs unders (45.0%): odds differential?

### Situational factors
- Reliable pre-game signals for IP (bulk/opener flag, bullpen situation):

### Gate/tier
- Gate out OUTS unders (45% WR)?
- OUTS overs separately tiered?
- G11 PITCHER_STATS dedup preventing correlated losses?

### Fix/kill decision
- % variance from unpredictable factors:
- If killed: restrict to overs only?
- Action:

---

## HITS

**Verdict:** pending

### Why zero picks
- G8 banning ≤1.5: does this kill all HITS picks?
- batter_hits at line 2.5+ consistently available?
- Does any projection clear G14 at 2.5?
- T1B "unders 3.5+ only" code enforcement found?

### Distribution
- Poisson validation: empirical HITS distribution from Stats API:

### Market structure
- Actual Odds API HITS lines across CO-legal books:
- Vig on HITS markets:

### Fix/kill decision
- Options: remove from PROP_MARKETS / remove G8 for HITS / wait for 2.5 availability:
- HITS 0.5 over WR if G8 lifted:
- Action:

---

## HA (Hits Allowed)

**Verdict:** pending

### Distribution
- Normal vs Poisson re-validation on Stats API data:
- IP-dependency modeled (HA capped by actual IP in model)?

### T1B discrepancy
- "unders 3.5+ only" — code found, direction enforced?
- All 17 picks are overs — is that a bug?

### Projection inputs
- SaberSim HA source:
- Mean bias:
- Opposing lineup quality factored?

### Sigma
- mult=0.50 min=2.5 dataset:
- Actual σ of HA per start:

### Market structure
- pitcher_hits_allowed consistently available?
- Why only 17 picks in 31 days?
- Typical line range:

### Situational factors
- Park factor (Coors):

### Fix/kill decision
- Resolve T1B discrepancy first, then:
- Data volume needed before evaluating HA:
- Action:

---

## ER (Earned Runs)

**Verdict:** pending

### Origin
- Code path that generated 7 April picks:
- Was there an ER evaluation block subsequently removed?

### Market availability
- ER prop currently in Odds API for CO-legal books?

### Model
- Distribution and sigma if market exists:
- G11 PITCHER_STATS inclusion needed?

### Fix/kill decision
- Market dead → remove residual code:
- Market alive → projectable with SaberSim?
- Action:

---

## TEAM_TOTAL

**Verdict:** pending

### Model
- Mean(saber_team - market_line) across 124 picks:
- BLEND_ALPHA=0.25 empirically validated for MLB?
- Actual σ of MLB team runs scored per game from Stats API:
- +2.30u on 124 picks: confidence interval, genuine vs noise?

### Missing signal
- Opposing SP quality in saber_team?
- Park factor in saber_team / propagated via BLEND_ALPHA?
- Weather adjustment available pre-game?

### Direction gap
- Distribution of (saber_team - market_line): how often negative?
- SaberSim systematic high bias or just coincidence?

### Fix/kill decision
- If profitable: improvements to increase edge:
- Efficient enough for 25% signal?
- Action:

---

## ML_FAV

**Verdict:** pending

### Model
- Actual σ of MLB run differentials from Stats API (2024-25):
- BLEND_ALPHA=0.25: signal vs 75% anchor?
- 54.2% WR vs 53.1% BE, n=48: statistically significant? n needed at 90%?

### Missing signal
- HFA explicitly in model?
- Pitcher FIP differential beyond Vegas line?

### Fix/kill decision
- Track to n=200 first:
- Model improvements (HFA, pitcher differential):
- Action:

---

## ML_DOG

**Verdict:** pending

### Data
- Actual odds on 3 picks, above break-even?
- Genuine edge signal for MLB dogs beyond Vegas line?
- Raise min_edge to 12%+?

### Fix/kill decision
- Track to n=100+:
- Action:

---

## F5_TOTAL

**Verdict:** pending

### Model
- 0.51 (F5 ≈ 51% of game runs) empirically correct? Pull 2024-25 data:
- Actual σ of F5 run totals from Stats API:
- Starter confirmation quality impact on F5 accuracy:
- F5_TOTAL consistently available across CO-legal books?

### Fix/kill decision
- Validate 0.51 and sigma, then accumulate data:
- Action:

---

## F5_ML

**Verdict:** pending

### Model
- Why 0.54 for F5_ML vs 0.51 for F5_TOTAL? Which is correct?
- F5_SIGMA["spread"]=2.5 for ML win probability — correct?
- May 12 late picks: 4 consecutive losses at +155. Dog value that doesn't exist?
- Break-even WR at actual average odds, n=10:
- F5_ML consistently available?

### Fix/kill decision
- Action:

---

## F5_SPREAD

**Verdict:** pending

### Model
- Why 0.51 for F5_SPREAD vs 0.54 for F5_ML? Resolve inconsistency:
- Actual σ of F5 run differentials:
- n=4 insufficient — validate scaling constant first:

### Fix/kill decision
- Action:

---

## SPREAD (Run Line)

**Verdict:** pending

### Model
- alternate_run_line being pulled from Odds API with lines returned?
- GG5: which side is blocked, and why?
- Actual σ of MLB run differentials vs sigma=3.8:
- Is SPREAD being evaluated at all? If GG5 kills all picks → remove from TIERS?
- Run line efficient enough to find edge?

### Fix/kill decision
- Action:

---

## Cross-Cutting

**Verdict:** pending

### BLEND_ALPHA
- 0.25 right for MLB specifically?
- Different BLEND_ALPHA per market type?
- Empirical: BLEND_ALPHA that minimizes projection error per market:

### GAME_SIGMA validation
- Actual σ of MLB game totals (total sigma=4.0):
- Actual σ of MLB run differentials (spread sigma=3.8):
- Actual σ of team runs scored (team sigma=3.0):
- ML sigma=6.0 derivation (from run diff σ or separate?):

### Park factors
- SaberSim encodes park in saber_team / player projections?
- If not: park factor adjustment needed for team total / game line?

### STAT_CAP
- STAT_CAP=2 applied in shadow mode?
- HRR/TB cap reduction to 1 (lineup correlation)?

### Sizing
- SPORT_UNIT_CAP=8.0u appropriate during shadow/calibration?
- VAKE_MULT MLB reduction during validation?
- T1 (K, HRR) losing — full sizing appropriate?

### Book coverage map
| Market | Books consistently offering |
|--------|----------------------------|
| pitcher_strikeouts | |
| pitcher_outs | |
| pitcher_hits_allowed | |
| batter_hits | |
| batter_total_bases | |
| batter_hits_runs_rbis | |
| NRFI/YRFI | |
| team_totals | |
| ML | |
| F5 | |

- Markets where only 1-2 books offer lines?

### SaberSim data quality
- Confirmed starter flags reliable? Day-of scratch rate?
- Team offensive quality metrics in SaberSim MLB CSV?
- Typical SaberSim release time vs game time?

### ER cleanup
- Residual ER code paths found and removed?
