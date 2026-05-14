# WNBA Research Findings
# Goal: calibrate run_picks.py pick selection layer to WNBA so it performs at NBA model level

## Status

| Section | Topic | Status |
|---------|-------|--------|
| 1 | SaberSim WNBA projection accuracy + biases | OPEN |
| 2 | PTS/REB/AST sigma calibration | OPEN |
| 3 | 3PM distribution + NB_R | OPEN |
| 4 | Combo stat correlations (COMBO_RHO) | OPEN |
| 5 | Market structure — books, line sharpness, coverage | OPEN |
| 6 | Opening day / early-season projection effects | OPEN |
| 7 | Gate review — which NBA gates apply/don't apply to WNBA | OPEN |
| 8 | Platt scaling validity for WNBA | OPEN |
| 9 | WNBA-specific structural differences vs NBA | OPEN |

---

## Context — What We Know Going In

**Shadow log state (as of 2026-05-13, first day of WNBA 2026 season):**
- 43 graded picks, all from one day
- PTS+under: 1W/5L (16.7% WR) — terrible
- PRA+under: 2W/4L (33.3% WR) — losing
- PA+under: 1W/3L (25.0% WR) — losing
- REB+under: 6W/6L (50.0%) — break even
- AST+under: 4W/1L (80.0%) — but n=5 only
- **Critical finding: model finds almost exclusively UNDERS** — structural projection over-bias

**What this means before research:**
- SaberSim WNBA projections appear systematically HIGH vs actual
- OR lines are set aggressively low (books pricing in overs)
- OR opening day rust effect
- Under-bias is the #1 issue to diagnose

**Current WNBA implementation in run_picks.py:**
- `GAME_SIGMA["WNBA"]` = {total:10.0, spread:10.0, team:7.5, ml:10.0} — scaled from NBA (12/12/9/12), not empirically calibrated
- `SIGMA` dict (AST mult=0.45/min=1.3, REB mult=0.58/min=2.5) — NBA-calibrated, used as fallback when dk_std=0
- `COMBO_RHO` — calibrated from 75,367 NBA player-games. PTS-REB=0.333, PTS-AST=0.233, REB-AST=0.251
- `NB_R["3PM"]` = 12.3 — NBA-calibrated
- `POISSON_STATS` includes AST + REB — valid for NBA, unknown for WNBA
- `SPORT_UNIT_CAP["WNBA"]` = 4.0u (conservative, reasonable)
- `SHADOW_SPORTS` includes WNBA — not posted to Discord
- G8B (AST over ≤4.5 ban) — correctly exempted for WNBA
- Markets: player_points, player_rebounds, player_assists, player_threes + combo props (PRA/PR/PA/RA)
- Platt scaling: `PLATT_A=1.4988, PLATT_B=-0.8102` — fit on NBA over_p_raw data only

---

## Section 1 — SaberSim WNBA Projection Accuracy + Biases

**Questions to answer:**
1. Is SaberSim known for systematic over-projection on WNBA stats? Which stats (PTS/REB/AST)?
2. How accurate are SaberSim WNBA projections vs actual player performance historically? Any published accuracy metrics?
3. Does SaberSim use the same modeling approach for WNBA as NBA, or is it a simpler model?
4. Is the dk_std column in SaberSim WNBA CSVs populated and accurate, or is it often 0/wrong?
5. Are there known opening-day/early-season over-projection issues specific to WNBA?
6. Community DFS feedback: do WNBA SaberSim projections consistently run hot or cold on specific stats?
7. What projection format does SaberSim WNBA CSV use — same columns as NBA or different?

**Findings:**
<!-- Fill in here -->

**Implementation verdict:**
<!-- What changes needed, if any -->

---

## Section 2 — PTS / REB / AST Sigma Calibration

**Context:**
The NBA SIGMA dict is used as fallback when dk_std=0. For WNBA, we need to know:
- Is the NBA sigma formula (mult × proj + min floor) accurate for WNBA?
- WNBA scoring is much lower (~15-20 PPG elite vs NBA 25-35 PPG), so absolute sigma differs
- The CV (std/mean) may be similar or different

**Questions to answer:**
1. What is the actual game-to-game PTS standard deviation for WNBA players across different projection tiers?
   - For a 10 PPG player: what is σ?
   - For a 15 PPG player: what is σ?
   - For a 20+ PPG player: what is σ?
2. Same for REB: what is actual σ per projection level?
3. Same for AST: what is actual σ per projection level?
4. What is the CV (σ/mean) for WNBA PTS vs NBA PTS? Is it higher/lower/same?
5. Does the Poisson assumption for WNBA AST and REB hold, or are those stats overdispersed?
   - Poisson: var = mean. If actual var >> mean, need NB instead.
6. What is a reasonable min floor for WNBA sigma on each stat?
7. Is Normal distribution appropriate for WNBA PTS or does the smaller scale (10-20 PPG) require a different model?

**Data sources to check:**
- Basketball Reference WNBA game logs (2023, 2024, 2025 seasons)
- StatMuse WNBA per-game splits
- WNBA official stats (stats.wnba.com)

**Target output:** New `SIGMA` entries for WNBA if different from NBA defaults:
```python
# Current NBA values (fallback when dk_std=0):
SIGMA = {
    "AST": {"mult": 0.45, "min": 1.3},
    "REB": {"mult": 0.58, "min": 2.5},
    # PTS uses dk_std from SaberSim; SIGMA["PTS"] not currently defined
}
```

**Findings:**
<!-- Fill in here -->

**Implementation verdict:**
<!-- Updated SIGMA values for WNBA, or confirmation NBA values hold -->

---

## Section 3 — 3PM Distribution + NB_R Calibration

**Context:**
NBA 3PM uses Negative Binomial with r=12.3, calibrated from NBA player-game data (within-player conditional var/mu). WNBA 3PM is structurally different:
- WNBA teams attempt fewer 3s per game overall
- WNBA 3P% is lower than NBA
- Star shooters (Sabrina Ionescu, etc.) have different volume than NBA 3PM specialists

**Questions to answer:**
1. What is the average WNBA 3PM per game for players at typical prop lines (1.5, 2.5, 3.5)?
2. What is the within-player variance of WNBA 3PM vs the mean? (var/mu ratio = key metric)
   - If var/mu ≈ 1.0 → Poisson fits
   - If var/mu >> 1.0 → NB needed, estimate r = mu²/(var-mu)
3. Are WNBA 3PM distributions bimodal (boom/bust like NBA shooters) or smoother?
4. What is typical WNBA 3PA volume for prop-relevant players?
5. Is r=12.3 (NBA value) too high or too low for WNBA? (Higher r = less overdispersion = closer to Poisson)
6. At what 3PM line does the model see most WNBA props? 1.5? 2.5?

**Data sources:**
- Basketball Reference WNBA game logs — pull 3PM per game for top shooters
- StatMuse WNBA 3PM splits

**Findings:**
<!-- Fill in here -->

**Implementation verdict:**
<!-- Updated NB_R["3PM"] for WNBA, or flag that current value needs sport-specific override -->

---

## Section 4 — Combo Stat Correlations (COMBO_RHO)

**Context:**
`COMBO_RHO` was calibrated from 75,367 NBA player-games. It drives the sigma of PRA/PR/PA/RA combo props:
- PTS-REB: ρ=0.333 (NBA)
- PTS-AST: ρ=0.233 (NBA)
- REB-AST: ρ=0.251 (NBA)

Higher ρ → higher combo σ → lower over probability → fewer picks. If WNBA ρ is different, combos are mis-priced.

**Why WNBA might differ:**
- WNBA rosters are smaller → specific players have to do more across stats
- Playmaking guards who score AND assist (Sabrina, Kelsey) may have higher PTS-AST correlation
- Fewer specialists → higher generalist correlation across the board
- Smaller sample of positions involved in rebounding may inflate REB correlation

**Questions to answer:**
1. What is the within-player pairwise correlation between PTS and REB in WNBA? (ρ_PTS_REB)
2. What is the within-player pairwise correlation between PTS and AST in WNBA? (ρ_PTS_AST)
3. What is the within-player pairwise correlation between REB and AST in WNBA? (ρ_REB_AST)
4. Are WNBA correlations higher or lower than NBA values?
5. Do correlations differ by position (guard vs center) in WNBA?
6. What is the practical impact: if ρ is 20% higher in WNBA, how much does combo sigma change?

**How to compute (if data available):**
- Pull WNBA player game logs for 2024-25 season
- For each player with n≥15 games, compute within-player Pearson correlation for each pair
- Average across players (weighted by n)

**Findings:**
<!-- Fill in here -->

**Implementation verdict:**
<!-- Updated COMBO_RHO values for WNBA, or sport-specific override mechanism needed -->

---

## Section 5 — Market Structure: Books, Lines, Sharpness

**Context:**
WNBA is a much smaller market than NBA. Key questions: how many books offer WNBA props in CO, how sharp are the lines, how much line movement is there, and is the market soft enough that our edge thresholds need adjustment.

**Questions to answer:**
1. Which CO-legal books offer WNBA player props? (DK, FD, BetMGM, theScore, Caesars, Fanatics, Hard Rock — which ones actually have WNBA?)
2. Are WNBA lines typically sharp (set by sharp books) or soft (retail pricing)?
3. How much line movement happens on WNBA props between open and close?
4. Are WNBA props available for all games or only marquee matchups?
5. What is the typical vig on WNBA props? (-110/-110 standard, or wider like -115/-115?)
6. Are WNBA combo props (PRA/PR/PA/RA) widely available, or just at 1-2 books?
7. Does our current edge threshold (default ~0.025-0.05) need to be higher for WNBA given thinner markets?
8. What is the typical time WNBA lines are posted? (Day-of, day-before?)
9. Are there any CO books that offer better WNBA prop coverage than others?

**Findings:**
<!-- Fill in here -->

**Implementation verdict:**
<!-- Any adjustments to edge thresholds, book filtering, or market availability for WNBA -->

---

## Section 6 — Opening Day / Early-Season Effects

**Context:**
All 43 shadow log picks came from May 13, 2026 — opening day of WNBA season. The model was predominantly finding unders, and they lost badly. This could be:
- (A) SaberSim structural over-projection
- (B) Opening day rust (players underperform early)
- (C) Books setting lines low (knowing opening day over-enthusiasm)
- (D) Statistical variance (43 picks / 1 day)

**Questions to answer:**
1. Do WNBA players historically underperform their season averages in the first 1-2 weeks of the season?
2. Is there an opening day effect in WNBA — do players score less / commit more turnovers on day 1?
3. Do betting markets price in an opening day discount (lines set lower than season average projection)?
4. Is this effect present in NBA as well, or WNBA-specific (longer offseason relative to season length)?
5. How many games into the season before WNBA projections stabilize?
6. Should we add an early-season dampening scalar (similar to how NBA playoff scalars adjust for context)?
7. Historical WNBA opening week actual vs Vegas line performance — do overs or unders hit more?

**Findings:**
<!-- Fill in here -->

**Implementation verdict:**
<!-- Whether an early-season scalar is warranted, or just accept thin early-season sample -->

---

## Section 7 — Gate Review: Which NBA Gates Apply to WNBA

**Context:**
All gates in `check_prop_gates()` were designed for NBA (and some for NHL/MLB). Need to audit each gate for WNBA applicability.

**Current gates and WNBA status:**

| Gate | Description | WNBA Status | Notes |
|------|-------------|-------------|-------|
| G1 | Edge ≥ threshold | APPLIES | Standard |
| G2 | win_prob ≥ threshold | APPLIES | Standard |
| G3 | Odds range gate | APPLIES | Standard |
| G4 | Score ≥ threshold | APPLIES | Standard |
| G5 | Positive-odds spreads blocked | N/A | No WNBA spread picks |
| G6 | Team total derivation | APPLIES | If team totals available |
| G7 | Line sanity check | APPLIES | Standard |
| G8 | Low line ban (AST/REB ≤1.5) | APPLIES | Keep |
| G8B | AST over ≤4.5 ban | EXEMPT | Correctly exempted for WNBA |
| G14 | Projection clearance gate | APPLIES | Standard |
| G15 | HIGH-VAR 3PM gate (pts_cv≥0.60) | CHECK | Does SaberSim WNBA CSV include pts_cv? |

**Questions to answer:**
1. G8B is already exempt for WNBA — is the threshold of 4.5 AST correct? What is typical elite WNBA AST line?
2. G8 (AST/REB ≤1.5 ban) — should this threshold be lower for WNBA given lower per-game averages?
3. Is there a WNBA equivalent of the NBA over-ban on specific stats? (e.g., should STL overs be banned?)
4. What is the typical WNBA prop line range for each stat (PTS, REB, AST, 3PM)?
   - If most WNBA PTS lines are 12.5-18.5 (vs NBA 20.5-30.5), do our line-based gates need WNBA-specific thresholds?
5. Should there be a WNBA-specific STAT_CAP (max picks per stat per run)?
6. Are there WNBA-specific stats that shouldn't be picked? (e.g., steals, blocks — available at some books)
7. Is KILLSHOT gate appropriate for WNBA (score≥90, win_prob≥0.65, odds ∈ [-200,+110])? Given thin market, should WNBA be excluded from KILLSHOT?
8. Are there WNBA-specific correlation concerns (like MLB's PITCHER_STATS group) that need a new correlation gate?

**Findings:**
<!-- Fill in here -->

**Implementation verdict:**
<!-- List of gate changes needed for WNBA -->

---

## Section 8 — Platt Scaling Validity for WNBA

**Context:**
The Platt scaler (`PLATT_A=1.4988, PLATT_B=-0.8102`) was fit on NBA `over_p_raw` data. It transforms raw model probabilities into calibrated win probabilities. For WNBA:
- WNBA uses the same Platt transform as NBA
- But the underlying sigma/distribution may differ
- If WNBA over_p_raw values are systematically different from NBA values, the NBA Platt will mis-calibrate them

**Questions to answer:**
1. Does applying the NBA Platt scaler to WNBA over_p_raw values make the win_prob higher or lower than it should be?
2. If WNBA σ is larger than NBA (higher variance relative to line), raw over_p values cluster near 0.50 → Platt would produce moderate win_probs. Is this directionally right?
3. Can we validate Platt on WNBA shadow data? (43 picks too thin for a refit, but can check calibration direction)
4. Should WNBA use a sport-specific Platt (separate A/B), or share NBA Platt?
5. How many WNBA over_p_raw rows would we need to refit a WNBA-specific Platt? (Same gate logic as NBA H3 ~300 rows)
6. What win_prob values does the model currently assign to WNBA picks? (avg 0.551 observed) — is that reasonable given actual WR?

**Shadow log Platt check:**
- Avg model win_prob: 0.551
- Avg actual WR: ~44% (total W=27, L=34 across all stats)
- If model says 55% and actual is 44%, the model is systematically overconfident
- This could be Platt mis-calibration OR genuine edge that isn't materializing (thin sample)

**Findings:**
<!-- Fill in here -->

**Implementation verdict:**
<!-- Whether to use sport-specific Platt for WNBA, or validate NBA Platt is acceptable -->

---

## Section 9 — WNBA Structural Differences vs NBA

**Context:**
WNBA is fundamentally different from NBA in ways that affect pick selection beyond sigma calibration.

**Questions to answer:**

### Game structure
1. WNBA plays 4×10 min quarters (40 min) vs NBA 4×12 min (48 min). How does this affect:
   - Absolute stat totals (PTS/REB/AST per game are lower)
   - Pace (possessions per game) — is WNBA faster or slower per 40 min vs NBA per 48 min?
2. Does a WNBA player play a higher % of available minutes than an NBA player? (Smaller rosters, fewer subs)
3. WNBA team average scoring is ~80-85 PPG vs NBA ~115 PPG. Does this affect how we should think about over/under edges?

### Season structure
4. WNBA has a regular season (May-September) and playoffs. Is there a meaningful regular season vs playoff performance difference?
5. WNBA has no mid-season break equivalent — does fatigue/back-to-back structure differ from NBA?
6. How long is the WNBA season in games? (40 games RS vs NBA 82) — does this affect EWMA-equivalent projection stability?

### Roster / role structure
7. WNBA rosters are 12 players (same as NBA). But DNP rates differ — are WNBA coaches more rotation-heavy or more star-reliant?
8. Import players (overseas) — do they affect season-opening projections?
9. Are WNBA injuries reported the same way as NBA (injury reports available from league)?

### Stat distribution differences
10. What are the WNBA league averages per game per player for PTS/REB/AST/3PM?
11. What is WNBA league pace (possessions per 40 min)?
12. What is the spread of player quality — is there more parity or more star concentration than NBA?

### Betting-specific
13. Are WNBA prop lines generally available day-of or posted in advance?
14. Do limits on WNBA props differ significantly from NBA at major books?
15. Are WNBA props more correlated with game flow (blowouts, pace) than NBA props?

**Findings:**
<!-- Fill in here -->

**Implementation verdict:**
<!-- Any structural constants, scalars, or model parameters that need WNBA-specific values -->

---

## Implementation Plan (fill after research complete)

### Parameter changes needed
<!-- List every constant that needs updating with old → new value -->

### Code changes needed
<!-- List every function/dict in run_picks.py that needs modification -->

### New WNBA-specific constants to add
<!-- Any new dicts/parameters that don't exist yet -->

### Gating / shadow removal criteria
<!-- What does WNBA need to achieve before going live (out of shadow)? -->

### Calibration data still needed
<!-- What can't be determined from research alone and requires live data accumulation -->
