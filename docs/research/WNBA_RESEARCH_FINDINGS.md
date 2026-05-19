# WNBA Research Findings
# Goal: calibrate run_picks.py pick selection layer to WNBA so it performs at NBA model level

## Status

| Section | Topic | Status |
|---------|-------|--------|
| 1 | SaberSim WNBA projection accuracy + biases | DONE |
| 2 | PTS/REB/AST sigma calibration | **DONE** |
| 3 | 3PM distribution + NB_R | **DONE** |
| 4 | Combo stat correlations (COMBO_RHO) | **DONE** |
| 5 | Market structure — books, line sharpness, coverage | OPEN |
| 6 | Opening day / early-season projection effects | OPEN |
| 7 | Gate review — which NBA gates apply/don't apply to WNBA | OPEN |
| 8 | Platt scaling validity for WNBA | OPEN |
| 9 | WNBA-specific structural differences vs NBA | **DONE** |

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

**Opening day actual vs SS projection audit (May 13 2026, all 4 games):**

Four box scores retrieved and cross-referenced against shadow log projections. Key PTS misses:

| Player | SS PTS Proj | Actual PTS | Error | Context |
|--------|------------|------------|-------|---------|
| Chennedy Carter (LAV) | 7.21 | 27 | **-19.8** | New Aces acquisition, Sun had 5 out |
| Marina Mabrey (TOR) | 15.93 | 26 | **-10.1** | Opening night explosion |
| Kelsey Plum (LAS) | 17.28 | 25 | **-7.7** | First game in LA |
| Caitlin Clark (IND) | 17.12 | 24 | **-6.9** | Season opener |
| Veronica Burton (GSV) | 15.60 | 16 | -0.4 | Accurate |
| Flau'jae Johnson (SEA) | ~11.57 | 7 | +4.6 | Under-performed |
| Kamilla Cardoso (CHI) | ~13.40 | 8 | +5.4 | Quiet game |
| Aliyah Boston (IND) | ~15.02 | 4 | **+11.0** | Very quiet night |

REB projections: mixed (no systematic direction). AST: close. 3PM: slight over-projection (Clark: 2.87→1, Jackson: 2.18→1).

**Directional summary:**
- SS under-projected PTS for star scoring guards by 7-20 pts on opening day
- SS over-projected PTS for role/secondary players (Boston, Cardoso)
- Net opening day PTS error: SS averaged ~-3.1 pts below actual (mean of 8 players)
- Shadow log picks almost all unders because SS proj < lines — but star-explosion losses dominated

**Root cause analysis:**
1. **SaberSim conservatism on stars**: SS likely uses prior-season averages as anchor. Stars who have new context (new team, elevated role, opener adrenaline) explode past SS projections AND past the betting lines.
2. **Opening day extreme variance**: All 43 picks from a single day. Carter's 27-pt game (SS: 7.21) is an obvious outlier — she was newly signed by the Aces and the Sun had 5 key players out (including Griner). SS doesn't dynamically model opponent-absence magnification.
3. **"Almost exclusively unders" finding is correct but diagnosis was wrong**: SS is NOT systematically over-projecting WNBA stats. Rather, SS under-projects star PTS while the lines are set closer to actual. The model sees SS<line and picks under, but SS is the wrong anchor.
4. **dk_std column**: SaberSim WNBA uses same platform/format as NBA. NBA CSVs have dk_std populated (Jokic: 11.37, Edwards: 11.28). WNBA dk_std should be populated in the CSV — but this column is SaberSim's internal std, which may itself be calibrated on NBA-like data. If SS proj is systematically low for WNBA stars, dk_std will also be anchored too low (std is proportional to proj).
5. **SaberSim WNBA model**: Appears to use same simulation platform as NBA. WNBA training data is sparser. No published accuracy metrics found. Community DFS feedback not found via search — WNBA DFS is a smaller market with less public accuracy discussion.
6. **Opening day effect (WNBA-specific)**: WNBA plays 40-game RS vs NBA 82. The longer offseason relative to season length means opening games have higher variance than NBA openers. Players arrive at different readiness levels. No published research found on WNBA opening day statistical underperformance vs season average.
7. **Injury redistribution gap**: When the Sun lost 5 players (Griner etc.), Morrow's actual role and minutes expanded dramatically. SS doesn't reflect this — it projected Morrow at 8.01 REB but she grabbed 11 in extended duty. This is a systematic weakness for WNBA because roster depth is shallower (injuries affect remaining players more than in NBA).

**What the 43-pick sample tells us:**
- WR by stat: AST-under 4/5 (80%), REB-under 6/12 (50%), 3PM-under 3/3 (100%), PTS-under 1/5 (20%), PRA-under 2/7 (29%), PA-under 1/4 (25%), PR-under 3/4 (75%)
- PTS unders are the problem (1W/5L). Stars outperformed lines badly.
- Combo props fail when PTS component fails (Clark PRA/PA/PR lost 4/4 because Clark's PTS alone exceeded lines)
- The combo-pick concentration on star guard combos (Clark: 4 combo picks, Plum: 3 combo picks, Mabrey: 3 combo picks) magnified the damage

**Implementation verdict:**

1. **SS dk_std likely populated for WNBA** — confirm by examining an actual WNBA CSV before adjusting SIGMA. No code change needed unless dk_std is 0.
2. **Opening day gate**: Add a gate to limit or avoid WNBA picks in the first 2-3 games of the season (opening night extreme variance). Simple date-based guard OR minimum-games-played filter on players. This is the single biggest learnable fix from day 1.
3. **SS projection bias for WNBA stars**: SS under-projects star guard PTS by 5-10+ pts on opening day. Consider a WNBA-specific projection "warm-up" scalar for early-season (first 2 weeks) that modestly inflates lines or reduces perceived edge, forcing the model toward neutral rather than strong unders.
4. **Combo picks on same player**: Clark had 4 combo picks (PRA/PA/PR/PRA again). These are all driven by the same PTS error — if SS under-projects PTS, all combos on that player fail. Need a per-player combo pick cap (max 1 combo pick per player per run) to avoid correlated-loss stacking.
5. **No systemic change to SIGMA or COMBO_RHO yet**: One day of data is insufficient to recalibrate. Accumulate 3-4 weeks before drawing calibration conclusions.

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

**Data source:** ESPN game logs + HerHoopStats 2024 WNBA regular season. 9 players, 336 player-games total.
Players: A'ja Wilson (~27 PPG), Breanna Stewart (~20), Napheesa Collier (~20), Arike Ogunbowale (~22), Sabrina Ionescu (~18), Caitlin Clark (~19), Jackie Young (~16), DeWanna Bonner (~15), Angel Reese (~14).

**PTS sigma by player:**

| Player | Avg PPG | n | Sigma | CV (sigma/mean) |
|--------|---------|---|-------|-----------------|
| A'ja Wilson | 26.9 | 38 | 6.64 | 0.247 |
| Breanna Stewart | 20.5 | 39 | 7.19 | 0.350 |
| Napheesa Collier | 20.4 | 34 | 6.14 | 0.301 |
| Arike Ogunbowale | 22.2 | 38 | 7.11 | 0.320 |
| Sabrina Ionescu | 18.3 | 39 | 6.32 | 0.345 |
| Caitlin Clark | 19.2 | 40 | 7.46 | 0.388 |
| Jackie Young | 16.4 | 37 | 8.11 | 0.496 |
| DeWanna Bonner | 15.0 | 40 | 6.38 | 0.425 |
| Angel Reese | 13.6 | 34 | 4.95 | 0.364 |

**PTS sigma by tier (pooled):**
- 20+ PPG tier (Wilson, Stewart, Collier, Ogunbowale): pooled mean=22.6, sigma=7.23, **CV=0.321**
- 15-20 PPG tier (Clark, Ionescu, Young, Bonner): pooled mean=17.2, sigma=7.22, **CV=0.419**
- 10-14 PPG tier (Reese, n=34): mean=13.6, sigma=4.95, **CV=0.364**
- Overall PTS CV range: **0.247-0.496**, weighted average **~0.36**

**PTS at specific projections:**
- ~10 PPG player: sigma ~ 3.7-5.0 (CV ~0.37-0.50)
- ~15 PPG player: sigma ~ 5.5-6.4 (CV ~0.37-0.43)
- ~20 PPG player: sigma ~ 6.1-7.5 (CV ~0.30-0.37)
- ~27 PPG player (Wilson): sigma ~ 6.6 (CV ~0.25)

**REB sigma by tier:**

| Tier | Mean RPG | Sigma | CV |
|------|----------|-------|-----|
| High REB ~9-13 RPG (Wilson, Stewart, Collier, Reese) | 10.75 | 4.20 | 0.391 |
| Low REB ~4-6 RPG (Ionescu, Clark, Young, Bonner, Ogunbowale) | 5.09 | 2.42 | 0.476 |

- ~5 RPG player: sigma ~ 2.1-2.8 (CV ~0.40-0.49)
- ~8 RPG player: sigma ~ 3.5 (interpolated)
- ~10 RPG player: sigma ~ 3.2-4.1 (CV ~0.33-0.48)
- ~13 RPG player (Reese): sigma ~ 4.1 (CV ~0.31)
- Overall REB CV: **0.43** (range 0.31-0.49)

**AST sigma by tier:**

| Tier | Mean APG | Sigma | CV |
|------|----------|-------|-----|
| High AST ~5-8 APG (Clark, Ogunbowale, Young, Ionescu) | 6.32 | 3.02 | 0.478 |
| Low AST ~2-4 APG (Wilson, Reese, Bonner, Stewart, Collier) | 2.61 | 1.66 | 0.635 |

- ~2 APG player: sigma ~ 1.1-1.5 (CV ~0.53-0.67)
- ~4 APG player: sigma ~ 1.8-1.9 (CV ~0.45-0.55)
- ~6 APG player: sigma ~ 2.5-2.6 (CV ~0.41-0.50)
- ~8 APG player: sigma ~ 3.3 (CV ~0.39)
- Overall AST CV: **0.56** (range 0.39-0.67)

**NBA vs WNBA CV comparison:**

| Stat | NBA (RotoGrinders 2013, starters) | WNBA 2024 | WNBA/NBA ratio |
|------|-----------------------------------|-----------|----------------|
| PTS | ~0.23-0.27 (sigma=4.1, avg ~15-18 PPG) | **0.36** | ~1.4x higher |
| REB | ~0.47 (sigma=2.8, avg ~6 RPG) | **0.43** | ~0.92x (similar) |
| AST | ~0.50 (sigma=2.0, avg ~4 APG) | **0.56** | ~1.1x higher |

**Key finding: WNBA PTS CV is ~40% higher than NBA.** A WNBA player scoring 15 PPG has similar absolute sigma (~6-6.5) as an NBA player scoring 20-25 PPG. The NBA SIGMA mult for PTS (if it existed; currently using dk_std) would need to be ~0.35-0.42 for WNBA vs ~0.23-0.27 for NBA.

**Poisson vs Negative Binomial for REB and AST:**

Overdispersion ratio (var/mean): >1.5 indicates NB preferred over Poisson.

- REB: mean var/mean = **1.21** (range 0.72-1.99). Most players borderline. Stewart REB (var/mean=1.99) clearly NB. Low-RPG guards (Ionescu, Young, Ogunbowale) near Poisson (var/mean ~0.72-0.99). Recommendation: **Poisson is a reasonable approximation for WNBA REB** — overdispersion is mild compared to NBA (where var/mean is typically 1.5-2.5 for big men). Current SIGMA approach (Normal with empirical sigma) is adequate.
- AST: mean var/mean = **1.00** (range 0.56-1.29). Very close to Poisson. Low-AST players (Bonner 0.56, Reese 0.63) are actually underdispersed. High-AST guards (Clark 1.29) borderline. Recommendation: **Poisson is appropriate for WNBA AST** — even more so than NBA. `POISSON_STATS` including AST is valid for WNBA.

**Normal distribution for WNBA PTS:**

Skewness near 0 for most players (Wilson: -0.09, Ogunbowale: +0.14, Young: +0.01). Normal is a good approximation. One exception: Angel Reese had skew=+1.13 with right-tail outliers (27-pt game while averaging 13.6) — she is a role player who explodes rarely. Tails in the 20+ PPG range are slightly fatter than Normal (5.3% observed vs 2.3% expected above mean+2sd for Wilson). Normal is appropriate but slightly underestimates tail probability.

The main concern for lower-scoring players (~10 PPG) is not non-normality but scale: Normal allows negative scores. For a ~10 PPG player with sigma=4, P(score<0) under Normal is ~0.6% — negligible for practical purposes. Normal remains appropriate.

**Implementation verdict:**

Current NBA SIGMA dict (AST: mult=0.45/min=1.3, REB: mult=0.58/min=2.5) needs adjustment for WNBA:

```python
# Recommended WNBA SIGMA overrides (when dk_std=0):
SIGMA_WNBA = {
    "PTS": {"mult": 0.38, "min": 3.5},   # NBA uses dk_std; WNBA needs own formula
                                           # CV=0.36 avg; 0.38 adds slight buffer for lower-tier volatility
    "AST": {"mult": 0.55, "min": 1.1},   # NBA=0.45 — WNBA AST CV ~0.56 (25% higher mult than NBA)
    "REB": {"mult": 0.45, "min": 2.0},   # NBA=0.58 — WNBA REB CV ~0.43 (22% LOWER mult than NBA)
                                           # Rationale: WNBA REB variance is similar to NBA low-REB guards;
                                           # NBA mult=0.58 was calibrated for high-RPG bigs; WNBA stars top out ~12 RPG
}
```

Note: dk_std from SaberSim WNBA CSV should still be preferred if non-zero. These formulas are only the dk_std=0 fallback. Key changes vs NBA:
- PTS: new formula needed (NBA doesn't have one; uses dk_std). Set mult=0.38.
- AST: increase mult from 0.45 → 0.55 (+22%)
- REB: decrease mult from 0.58 → 0.45 (-22%) and lower min from 2.5 → 2.0 (WNBA low-REB players average 4-5 RPG)

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

**Data source:** ESPN/HerHoopStats 2024 WNBA regular season game logs for Ionescu (39g), Clark (40g), Collier (34g). League-wide 3PM leaders table from FoxSports 2024.

**WNBA 3PM leaders 2024 (top of market):**

| Player | 3PM/g | 3PA/g | 3P% |
|--------|-------|-------|-----|
| Caitlin Clark | 3.05 | 8.9 | 34.4% |
| Arike Ogunbowale | 2.9 | 8.5 | 34.6% |
| Kelsey Plum | 2.9 | 7.9 | 36.8% |
| Sabrina Ionescu | 2.8 | 8.4 | 33.3% |
| Kelsey Mitchell | 2.7 | 6.8 | 40.2% |
| Kayla McBride | 2.7 | 6.6 | 40.7% |

The WNBA top-of-market 3PM/g range (~2.7-3.1) is comparable to NBA 3PM specialists. Market props will center around 1.5 and 2.5 lines.

**Variance analysis (within-player):**

| Player | Mean 3PM/g | Sigma | CV | Var/Mean | Distribution |
|--------|-----------|-------|-----|-----------|-------------|
| Ionescu | 2.79 | 1.36 | 0.487 | 0.66 | 1:8, 2:10, 3:7, 4:12, 6:2 |
| Clark | 3.05 | 1.47 | 0.481 | 0.71 | 1:5, 2:12, 3:9, 4:7, 5:5, 6+:2 |
| Collier (low-vol) | 0.91 | 0.79 | 0.869 | 0.69 | 0:12, 1:13, 2:9 |

**Critical finding: WNBA 3PM var/mean = 0.66-0.71 (underdispersed relative to Poisson).** This is the opposite of NBA where 3PM is overdispersed (var/mean > 1.0, justifying Negative Binomial with r=12.3). For high-volume WNBA shooters, 3PM is approximately Poisson or even underdispersed.

**Bimodality analysis:**
- Ionescu and Clark: **NOT bimodal.** Zero zeros in 39-40 games each. Distribution is unimodal with right-skew. Every game they attempt 3s — consistent volume shooters.
- Collier (0.9/g): 12/34 zeros (35%), but this matches Poisson P(0) expectation of 40%. Low-volume pattern consistent with Poisson, not bimodal boom/bust.
- **WNBA 3PM is NOT bimodal in the NBA sense.** NBA bimodality arises when a specialist either "goes hot" (4-6 3PM) or shoots 0-1 due to game script. WNBA guards shoot more consistently — there is no quiet night pattern like NBA role players.

**NB_R calibration:**
The NBA `NB_R["3PM"] = 12.3` was calibrated for overdispersed NBA 3PM data (var/mean > 1). For WNBA 3PM with var/mean ~0.7, the data is underdispersed. Using NB with r=12.3 would produce barely-more-than-Poisson distribution. Options:
- Use Poisson directly for WNBA 3PM (var/mean ~1.0 is the Poisson assumption; 0.7 is slightly under)
- Use NB with much higher r (underdispersed NB r → infinity converges to Poisson)
- Or simply use Normal approximation with sigma = 0.48 × mean (CV from data)

Practical impact at a 2.5 line: under Poisson(2.79), P(3PM ≥ 3) = 42.6%. Under Normal(2.79, 1.36), P(3PM ≥ 2.75) ≈ 51.5%. The Normal with empirical sigma is actually the most defensible model here — it captures the correct variance and doesn't require choosing between Poisson/NB.

**Implementation verdict:**

WNBA 3PM should use Normal approximation (not Negative Binomial) because:
1. Var/mean < 1.0 (underdispersed), so Poisson overestimates tails
2. NBA NB_R=12.3 was fit on overdispersed NBA data — inappropriate for WNBA
3. Volume shooters (Ionescu, Clark) have near-Gaussian 3PM distributions (no zero-floor problem)
4. The HIGH-VAR bimodal flag (CV ≥ 0.60, min 8 games) would NOT trigger for WNBA top shooters (CV~0.48), and WOULD trigger for low-volume shooters like Collier (CV=0.87). This is correct behavior — low-volume WNBA shooters are high-variance.

Add WNBA 3PM sigma formula to SIGMA dict:
```python
SIGMA_WNBA["3PM"] = {"mult": 0.48, "min": 0.7}
# sigma = max(0.48 * proj_3pm, 0.7)
# For a 3.0/g shooter: sigma = 1.44
# For a 1.5/g shooter: sigma = 0.72
```

`NB_R["3PM"]` does not need a WNBA-specific override — the code path for WNBA 3PM should use Normal (via SIGMA_WNBA), not NB. If the code currently routes WNBA 3PM through NB_R, add a sport-specific branch.

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

**Data source:** 9 WNBA players × 34-40 games each (2024 RS). Within-player Pearson correlations computed for each pair, then weighted-averaged by n.

**Within-player Pearson correlations:**

| Player | n | rho_PTS_REB | rho_PTS_AST | rho_REB_AST |
|--------|---|-------------|-------------|-------------|
| A'ja Wilson | 38 | +0.110 | -0.191 | -0.277 |
| Breanna Stewart | 39 | +0.060 | +0.020 | -0.206 |
| Napheesa Collier | 34 | +0.006 | -0.130 | +0.107 |
| Arike Ogunbowale | 38 | +0.216 | -0.123 | +0.060 |
| Sabrina Ionescu | 39 | +0.162 | +0.091 | -0.025 |
| Caitlin Clark | 40 | +0.024 | +0.374 | +0.326 |
| Jackie Young | 37 | +0.482 | +0.333 | +0.407 |
| DeWanna Bonner | 40 | +0.064 | +0.054 | +0.000 |
| Angel Reese | 34 | +0.062 | -0.108 | +0.032 |

**Weighted averages (n-weighted):**

| Pair | WNBA 2024 | NBA baseline | Delta |
|------|-----------|-------------|-------|
| PTS-REB | **+0.132** | 0.333 | **-0.201** |
| PTS-AST | **+0.041** | 0.233 | **-0.192** |
| REB-AST | **+0.046** | 0.251 | **-0.205** |

**Interpretation:**

WNBA within-player correlations are dramatically lower than NBA — approximately **0.20 lower across all three pairs.** The main drivers:

1. **PTS-REB near-zero correlation in WNBA**: Scoring guards (Ogunbowale, Ionescu) have very low RPG (4-5), so high-scoring games don't correspond to high-rebounding games. Wilson and Collier are the exceptions (both PTS and REB specialists), but even they show only moderate correlation. In NBA, stars like LeBron or Giannis have high cross-stat correlation because they dominate multiple categories simultaneously.

2. **PTS-AST negative for post players**: Wilson (-0.191), Ogunbowale (-0.123), Collier (-0.130). In games where these players score heavily, they are in isolation/post mode, not passing. Clark and Young are exceptions (positive PTS-AST) because they are pass-first guards who also shoot.

3. **REB-AST near-zero or negative**: Most WNBA stars are either rebounders (Wilson, Collier, Reese) or passers (Clark, Young, Ionescu) but rarely both. The cross-correlation is near zero.

**Practical impact on combo props:**

Higher COMBO_RHO → higher combo sigma → lower over probability → fewer combo picks.
Lower COMBO_RHO → lower combo sigma → higher over probability → more combo picks (and potential over-picking).

With NBA COMBO_RHO values (0.333/0.233/0.251), the model is **underestimating WNBA combo sigma** by assuming correlations that don't exist in WNBA. This means the model produces artificially high over-probabilities on combo props like PRA, PR, PA, RA.

Directional formula:
combo_sigma = sqrt(sigma_A^2 + sigma_B^2 + 2*rho*sigma_A*sigma_B)

With PTS=7, REB=3, rho=0.333 (NBA): PTS+REB sigma = sqrt(49+9+14) = 8.25
With PTS=7, REB=3, rho=0.132 (WNBA): PTS+REB sigma = sqrt(49+9+5.5) = 7.91

Difference: 4.2% lower combo sigma under WNBA calibration. The effect is modest but directionally the WNBA model would be slightly more aggressive (higher over probability) on combos with NBA rho, which in context of an already over-aggressive model is a compounding error.

**Implementation verdict:**

Add WNBA-specific `COMBO_RHO`:

```python
COMBO_RHO_WNBA = {
    ("PTS", "REB"): 0.13,  # NBA=0.333 — dramatically lower in WNBA
    ("PTS", "AST"): 0.04,  # NBA=0.233 — near-zero in WNBA
    ("REB", "AST"): 0.05,  # NBA=0.251 — near-zero in WNBA
}
```

Note: correlations this low (0.04-0.13) make combo props behave nearly additively (sigma close to sqrt of sum of squared individual sigmas). This means WNBA combo props will have higher sigma than NBA combos with the same individual sigmas, producing lower over-probabilities and fewer picks — which is the correct direction given WNBA's lower correlation structure.

Caveat: 9 players is a thin sample. Player-specific variation is large (Clark PTS-AST=+0.374 vs Wilson PTS-AST=-0.191). The weighted averages are the right starting point but should be revisited after 50+ player-seasons of WNBA shadow data.

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

**Q1 — Which CO-legal books offer WNBA player props?**

Confirmed WNBA player prop offerings in CO (2026 season, active as of May 2026):

| Book | WNBA Props | Notes |
|------|-----------|-------|
| DraftKings | YES | Full coverage. Most-referenced book; publishes own "Most Bet WNBA Props" daily. Confirmed single-stat + combo props. |
| FanDuel | YES | Full coverage. Noted as having widest variety of in-game/live props. Frequently best line on many props. |
| BetMGM | YES | Full coverage. Appears in prop aggregators alongside DK/FD. |
| Caesars | YES | Full coverage. Appears in prop aggregators. |
| Hard Rock | YES | Confirmed WNBA props including combo stat lines. Rotogrinders runs a dedicated Hard Rock prop picks page for WNBA. |
| Fanatics | YES | Confirmed WNBA. Featured in dimers.com prop picks as a best-line book. Appears in CO as replacement for PointsBet (Dec 2023 launch). |
| theScore Bet (ESPN BET) | LIKELY YES | Appears in the RotoWire WNBA props interface alongside DK/FD/BetMGM/Caesars/Hard Rock. Not explicitly called out in most roundups but confirmed in the RotoWire props page source. |

**Summary:** All 7 CO-legal books in scope likely offer WNBA player props during the 2026 season. DraftKings, FanDuel, BetMGM, Caesars, Hard Rock, and Fanatics are confirmed with certainty. theScore Bet (ESPN BET) appears in prop aggregators but is less explicitly documented.

**Q2 — Are WNBA lines sharp or soft? Is there meaningful sharp steam?**

WNBA prop lines are **soft relative to NBA**, but the picture is nuanced:

- Game-level lines (spreads, totals) have become moderately sharp — increased betting handle in 2024-25 has attracted professional attention to game lines.
- Player prop lines remain **meaningfully softer** — books invest less time in WNBA prop pricing, public action is thin, and fewer quantitative analysts work WNBA markets.
- WNBA receives ~20x fewer total bets per game than an average NBA game. This keeps sharp/square ratio elevated in WNBA: even small sharp bets can move lines significantly.
- Books explicitly described as "not likely to be well-informed about a sport that doesn't drive much revenue" — opening lines are set on basic stat averages.
- OpticOdds partnership with The Crowd's Line AI (April 2026) to generate AI-driven WNBA prop pricing with "confidence-adjusted vig" signals that some operators still lack good proprietary WNBA prop models and are outsourcing line-setting.
- **Sharp steam does occur** but the market is thinner — a $500 sharp bet can move a WNBA line the same as $5,000 in NBA. Steam moves happen but are concentrated on featured players (Clark, A'ja, Wilson).
- Reverse line movement ROI of ~10% documented in WNBA spread markets — higher than typical NBA.

**Q3 — How much line movement happens between open and close?**

WNBA prop lines move **more than NBA**, not less:

- Props can swing 3+ points in either direction, especially when sharp bettors identify early mispricing. Examples documented: 19.5 → 16.5 by tip-off.
- Game lines: WNBA regularly sees 4+ point spread/total changes; such moves are rare in NBA.
- "Books post soft numbers based on basic stat averages and leave them open for longer than they should" — then adjust sharply when steam hits.
- Line discrepancies across books at open are very wide: one example cited was A'ja Wilson at 18.5 vs 21.5 at two different books simultaneously. 
- The practical implication: **early lines are softer and wider; lines converge and sharpen into tip-off.** This is opposite to NBA where lines are sharp from the start and move predictably.
- CLV (closing line value) signals are **cleaner in WNBA** than NBA — moving against you is a reliable signal.

**Q4 — Props available for all games or only marquee matchups?**

Based on current 2026 season observation (May 13-19 coverage):

- **Props appear available for all WNBA games**, not just Clark/A'ja games. Multiple non-marquee games confirmed with prop coverage.
- DraftKings publishes "Most Bet WNBA Props" daily covering whatever games are on the slate (4-game slate on 5/15, 1-game slate on 5/19 — both had prop coverage).
- Dimers, Covers, RotoWire all publish daily prop picks for every game, suggesting books post props across the full schedule.
- **However, depth varies by game**: A Clark or A'ja Wilson game may have 10-15 players with props, while a non-marquee game may have only 3-5. Star player concentration is real.
- The 5/14/26 DK article showed 12 prop lines for TOR Tempo @ PHO Mercury — a non-marquee matchup — confirming non-marquee games do have prop coverage.

**Q5 — Typical vig on WNBA props?**

WNBA props run **wider vig than NBA standard** with high variation across books:

From observed 2026 data:
- DraftKings: -110 (standard) on many props; also -126, -102 (variable by prop)
- FanDuel: -122 typical
- bet365: -125 typical  
- Hard Rock: -115 typical
- Fanatics: Appearing as best-line book at -105 to -110 on some props
- Outlier lines: -195 (heavily favored side), +120 (underdog side) — significant asymmetry common

**Vig summary:**
- NBA standard: -110/-110 (~4.5% book margin)
- WNBA typical: -115/-115 (~6.5% book margin) to -120/-120 (~9% margin)
- Best available: Often -105 to -110 on the more predictable side at Fanatics or DraftKings
- Worst: -122 to -125 standard at FanDuel/bet365

The vig is notably wider on WNBA than NBA, partly because:
1. Lower volume = books need wider margin to cover risk
2. Less information efficiency = books hedge with more cushion
3. Asymmetric lines are common (one side priced at -150, other at +115) reflecting book uncertainty

**Q6 — Are combo props (PRA/PR/PA/RA) widely available?**

Combo props are available but **not as consistently deep as single-stat props**:

From scoresandodds.com (which aggregates WNBA props across books), confirmed prop type filters for WNBA:
- Points, Rebounds, Assists, Steals, 3 Pointers — all confirmed (single-stat)
- "Points & Rebounds" (PR) — confirmed
- "Points & Assists" (PA) — confirmed
- "Points, Rebounds, & Assists" (PRA) — confirmed
- "Rebounds & Assists" (RA) — confirmed
- Turnovers — also available

DraftKings confirmed offering all four combo types (PRA, PR, PA, RA) on WNBA — their "Most Bet Props" article explicitly shows combo props as a category.
Hard Rock confirmed combo stat lines for WNBA.

**Assessment:** PRA/PR/PA/RA combos are available at DraftKings, FanDuel, and Hard Rock at minimum. BetMGM and Caesars likely offer them but less explicitly confirmed. They may not appear for every player in every game — likely restricted to featured players (stars, primary ballhandlers).

Note: Given Section 4 finding that WNBA COMBO_RHO is near-zero (0.04-0.13 vs NBA 0.23-0.33), combo props should appear more frequently in the WNBA model than NBA combos at similar projection levels. But the availability constraint may limit which players have combo lines to pick from.

**Q7 — Does the edge threshold need to be higher for WNBA?**

**Yes, but the direction of adjustment is non-trivial:**

Arguments for raising the threshold:
- Wider vig (~6-9% margin vs ~4.5% NBA): breakeven edge requirement is higher. At -115/-115, you need edge ≥ 6.5% just to break even, not 4.5%.
- Faster line movement: if you can't act on early lines, the edge you compute may evaporate before placement
- Lower limits: you can't size as aggressively, so small edges aren't worth running
- Less liquid: CLV signals are strong (as above) — if you beat the close, it's meaningful; if you lose CLV, you were picking bad

Arguments against raising threshold excessively:
- Softer pricing: larger edges are genuinely available on WNBA props vs NBA props — the market is less efficient, so edges ARE larger
- The distribution of prop edge in WNBA is wider — you'll see more +8% edges and more -5% traps than in NBA
- Research note from Dimers: "second-tier stars whose name recognition lags their actual production are systematically underpriced" — real edge exists if the model finds it

**Recommendation:**
- Keep the pick-selection gate (G1/G14) minimum edge threshold at **3.5-4.0%** for WNBA (vs NBA's 2.5-3.0%), to account for the higher vig environment
- But the bigger lever is the **vig-adjusted win probability floor** (G2): raise `MIN_WIN_PROB` for WNBA by ~0.015-0.020 above NBA default to compensate for wider average book margins
- **Do not raise threshold so high that the model stops firing**: WNBA edges are real and genuine; a 3.5% edge at -115 is a better bet than a 3.5% edge at -110, because the former represents more market softness

**Q8 — When are WNBA lines typically posted?**

**Day-of, morning of the game. Early lines are the softest.**

Confirmed from multiple sources:
- "Books often release WNBA props the morning of a game, and that's when the lines are softest"
- "Bet early" — explicit recommendation in sharp WNBA strategy articles because early lines are set from basic stat averages
- dimers.com publishes their WNBA props at midnight/1am ET for that day's games; covers.com similar
- Props can be updated as recently as 5pm ET on game day (example: May 19 Dimers article updated 5:13 PM ET for 10:00 PM ET game)
- Line posting is NOT day-before standard for WNBA like NFL; it's day-of morning (usually 9am-11am ET)

**Implication for the engine:** Running run_picks.py in the morning is important for WNBA. Early lines are softest; lines sharpen significantly into tip-off. If the engine runs after 3-4pm ET on late game days, some edge may already be priced out.

**Q9 — Which CO books have best WNBA prop coverage?**

Based on the research:
- **DraftKings**: Best breadth — most players, all prop types, all combo types, early posting, high prop count per slate
- **FanDuel**: Best live props (in-game player props for WNBA); widest live market; solid pre-game coverage
- **Fanatics**: Frequently appears as best-line source in dimers prop analysis — may post softer lines that offer more value
- **Hard Rock**: Good combo prop coverage; Rotogrinders tracks separately — active WNBA prop market
- **BetMGM/Caesars**: Coverage confirmed but not depth-differentiated in research
- **theScore Bet**: Least-confirmed of the group; appears in some aggregators but not prominently referenced

**For line shopping priority:** DraftKings first (benchmark line), then check Fanatics (often best odds), FanDuel (best live), Hard Rock (backup).

**Q10 — Typical WNBA prop bet limits vs NBA?**

**WNBA limits are substantially lower than NBA.** Specific documented findings:
- Sharp bettors can typically get no more than **$250-$500 on a WNBA prop** before being limited or losing the line
- NBA props by comparison: $1,000-$5,000+ depending on book and player
- "Low limits keep sharps away, depriving the market of information" — this is a structural feature, not a bug from the book's perspective
- Prop limits are asymmetric: headliner players (Clark, A'ja) have higher limits than role players
- Once sharp bets hit on a thin WNBA market, books move lines aggressively and may limit future action

**For sizing purposes:** The engine's `SPORT_UNIT_CAP["WNBA"] = 4.0u` is appropriate from a model perspective, but in practice, the binding constraint is the book's $250-500 limit per prop — not the unit cap. At 1u = ~$50-100 stakes, WNBA props are likely within book limits. At 2-4u = $200-400, some props may bump against limits.

**Implementation verdict:**

1. **All 7 CO-legal books in scope offer WNBA props** — no need to filter any book out of WNBA picks. DraftKings/FanDuel/Fanatics are the primary sourcing books; Hard Rock is a solid backup.

2. **Vig adjustment needed:** Current edge threshold calibration assumes ~4.5% vig (NBA -110/-110). WNBA averages ~6-7% vig (-115/-115 typical). The win_prob gate (G2) should be raised by ~0.01-0.02 for WNBA to account for this, or an explicit `EDGE_THRESHOLD_OVERRIDE["WNBA"] = 0.035` should be set vs NBA's 0.025.

3. **Line timing:** WNBA props post morning of game (not day-before). Engine running in the morning is optimal for WNBA. Late-evening re-runs will see sharper (less exploitable) lines.

4. **Combo props:** Available at DK/FD/Hard Rock/Fanatics at minimum. Can run PRA/PR/PA/RA picks but expect lower player count vs NBA — not every player will have all four combo lines available.

5. **No book filtering:** Unlike NBA where some books offer better coverage for specific stats, all 7 CO books offer WNBA props. Line shop normally. Fanatics appears to offer favorable odds on some WNBA props vs the consensus.

6. **Sizing cap:** `SPORT_UNIT_CAP["WNBA"] = 4.0u` is fine but real-world limit is ~$500/pick at most books. At normal sizing of 1-2u this is not binding. If unit size scales above $250, some WNBA picks will hit book limits — add a practical warning in engine logs.

7. **Line movement risk:** WNBA lines move fast once posted. Any pick logged in the morning may have moved by tip-off. CLV tracking is very important for WNBA — it will be the primary validation signal. Strong positive CLV on WNBA picks = strong evidence of genuine model edge.

8. **Edge threshold recommendation:**
   - Minimum: `EDGE_THRESHOLD["WNBA"] = 0.035` (vs NBA 0.025-0.030)
   - This accounts for the ~2% higher vig environment
   - Do not raise to 0.05+ as this would suppress too many genuine edges in a soft market

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

### Game Structure

**Q1 — 4x10 min quarters, downstream effects on absolute stats**

WNBA plays 40 min regulation vs NBA 48 min — a 16.7% shorter game. Actual 2024 league averages (HerHoopStats):

| Stat | WNBA 2024 (per team/game) | NBA 2024-25 (per team/game) | WNBA/NBA ratio |
|------|--------------------------|----------------------------|----------------|
| PPG | 81.6 | ~113-115 | 0.71 |
| RPG | 34.4 | ~43-44 | 0.79 |
| APG | 20.6 | ~26-27 | 0.77 |
| 3PM | 7.6 | ~13-14 | 0.55 |
| FG% | 43.8% | ~47% | lower |
| 3P% | 33.1% | ~36-37% | lower |
| FT% | 78.9% | ~78-79% | similar |

The PPG ratio (0.71) is larger than the game-length ratio (0.833), meaning WNBA scores fewer points per minute than NBA — not just from shorter games. This is confirmed by efficiency data (ORtg 101 vs NBA 115+). Scoring is structurally lower per possession, not just proportional to game length.

**Q2 — WNBA pace vs NBA per-40-minute pace**

WNBA 2024 possessions data (inpredictable.com):
- Avg possessions per team per game: **~81 per 40 minutes** (range: ~79 slow to ~83 fast)

WNBA 2025 early-season (StatMuse, 13 teams): **78.4 poss/game** (range: 75.9 GSV to 80.6 LAL)

NBA 2024-25 pace: 99.6 poss/48 min. Converted to per-40-min basis: 99.6 × (40/48) = **83.0 poss/40 min.**

Conclusion: **WNBA pace (~78-81 poss/40 min) is 2-6% slower than NBA on a per-minute basis.** The difference is real but not enormous. Lower WNBA scoring is primarily from lower efficiency per possession (ORtg 101 vs 115), not dramatically slower pace.

**Q3 — Scoring rate per possession**

WNBA ORtg (2024): **101.0 pts/100 poss**
NBA ORtg (2023-24): **115.3 pts/100 poss**

Gap: 14.3 points per 100 possessions — NOT explained by game length. Causes (per Sportico analysis):
- NBA rim-finishing improved from 64% → 70%; WNBA stayed at 64% → 65% (dunking advantage)
- 3P revolution benefited NBA more due to larger efficiency gap between 2s and 3s in NBA
- Net: WNBA is a genuinely lower-efficiency league per possession

---

### Season Structure

**Q4 — 40-game season and projection stability**

40-game RS (vs NBA 82). Game-to-game variance is identical — individual game outcomes don't become noisier from a shorter season. But:
- A 5-game slump = 12.5% of WNBA season vs 6.1% of NBA — larger signal-to-season weight
- Prior-season sample is half as large, so season-start projections are noisier
- Projection stabilization: for a rolling-average model, WNBA converges after ~5-8 games (vs NBA ~10-15) because there are fewer total games in the pool — but precision is lower throughout the season

**Q5 — Back-to-back frequency**

2024 WNBA: teams averaged **2.86 games/week** (up from 2.5/week in 2023, due to 4-week Olympic break compressing the calendar). Some teams played 7 games in 12 days. The league actively minimizes back-to-backs but they occur.

NBA: ~3.4 games/week, ~18-20 back-to-backs per team per season.
WNBA: fewer total back-to-backs but similar weekly density when the Olympic break removes calendar days.

The official WNBA injury report has an explicit exception for "the second day of a back-to-back" — confirming they occur regularly enough to warrant scheduling exceptions.

**Q6 — Late-season fatigue (August-September)**

No published statistical research on WNBA late-season performance degradation found. Empirical signal:
- Post-All-Star 2024: only 3 of 24 games decided by ≤5 pts (13%), avg margin 16 pts — suggests teams coasting or resting stars in late regular season
- Blowout frequency spikes late, consistent with load management on locked playoff seeds
- No empirical magnitude for PTS/REB/AST decline in August-September found in research

Model implication: Monitor for "rest" designations in injury reports from late August onward.

---

### Roster / Role Structure

**Q7 — Rotation depth vs star reliance**

WNBA rosters: 11-12 players max (vs NBA 15 + 3 two-way + G League depth). No affiliate feeder league.

2024 MPG distribution (top 25 players all averaged 30+ MPG):
- WNBA starters average **32-39 MPG out of 40 available = 80-97% utilization**
- NBA starters average **32-36 MPG out of 48 available = 67-75% utilization**

WNBA stars play a **higher percentage of available game minutes** than NBA stars. This means:
1. WNBA injuries to starters have larger per-game impact (fewer backup minutes to absorb)
2. Approximately 7-8 players per team get meaningful minutes; players 9-12 rarely play
3. Coaches are star-reliant by necessity — smaller roster with no developmental ladder

**Q8 — International/overseas players and early-season conditioning**

Most European overseas leagues run October-April/May, ending just before the WNBA season. Post-2024 prioritization rules: mandatory arrival by training camp start or May 1 (later), with season-long suspension for non-compliance. ~35 players reported late to camp per year pre-rule; ~12 missed early games.

International players (Sabally, Stewart when overseas, European players) arrive mid-competitive-season:
- Generally game-ready physically (continuous competition)
- Risk: accumulated fatigue from near-year-round play
- Risk: week 1 adjustment to different teammates, systems, WNBA rules
- Benefit: no spring rust — they've been playing competitive basketball

No empirical data found confirming systematic international vs domestic early-season performance gap. Opening day variance is high for all players regardless of origin. Prioritization rules should reduce this as a structural issue going forward.

**Q9 — Injury reports**

Official WNBA injury report: teams must designate player status and specific reason by **5 PM local time the day before a game** (exception: second day of back-to-back). Official source: wnba.com/wnba-injury-report. Third-party aggregators (RotoWire, ActionNetwork, Covers) publish consistently.

Status designations: equivalent to NBA (Out/Questionable/Probable categories). Reporting consistency may be lower than NBA (no documented fine structure for non-compliance found), but official day-before reports are available and aggregated by standard sources.

Same processing logic as NBA injury integration is applicable to WNBA.

---

### Stat Distribution

**Q10 — WNBA league averages per game per player**

Team averages 2024 (HerHoopStats): PPG=81.6, RPG=34.4, APG=20.6, 3PM=7.6

Implied per-player averages for prop-relevant rotation (top 8 per team):
- PTS: ~10.2/game (prop lines: 10.5-20.5; A'ja Wilson ceiling ~22.5-23.5)
- REB: ~4.3/game (prop lines: 4.5-9.5; Reese ceiling ~11.5)
- AST: ~2.6/game (prop lines: 2.5-6.5; Clark ceiling ~7.5-8.5)
- 3PM: ~0.95/game (prop lines: 1.5-2.5; Clark/Ionescu/Plum may see 3.5)

**Q11 — WNBA league pace**

- 2024 full season: ~81 possessions per 40 minutes (team average)
- 2025 early season: ~78.4 possessions per game
- Team range: ~76 (slow) to ~83 (fast)
- Per-minute: 3-6% slower than NBA

**Use WNBA_LEAGUE_AVG_PACE = 80.0 possessions per 40 minutes** as model constant.

**Q12 — Parity vs star concentration**

WNBA competitive balance has worsened significantly:
- Best-vs-worst team gap doubled over last 10 years
- 2024: three teams simultaneously outscoring opponents by 8+ pts/game — unprecedented back to 2008
- 2025: NY Liberty and Minnesota Lynx "hogging wins," leaving fewer competitive games for rest of league
- Late-season 2024: 87% of post-All-Star games decided by 6+ points (avg margin 16 pts)

Star concentration: top 2-3 players account for 60-70%+ of team scoring on many rosters. Prop-worthy player pool per slate is much smaller than NBA — expect 20-30 meaningful props across 4-6 WNBA games, vs 60-80+ for NBA.

This is higher star concentration than NBA. A'ja Wilson at 26.9 PPG represents 33% of the Aces' 81.6 PPG — no NBA player represents that share of their team's scoring.

---

### Betting-Specific

**Q13 — Prop line posting timing**

No standardized posting time found in research. WNBA props are typically available **morning of game day** at major books. The day-before injury report deadline (5pm local) creates the logical floor. Unlike NBA where next-day lines often post the prior evening, WNBA props are less predictable in timing but available by ~8-10am game day.

**Q14 — Limits on WNBA props vs NBA**

Documented range from research (Bleacher Nation):
- **WNBA prop limits: $500-$1,000 per bet** (industry standard across DraftKings, FanDuel, others)
- **NBA prop limits: $1,000-$5,000 per bet**
- WNBA limits are approximately 50-80% lower than NBA

Lower limits = softer market = more exploitable edges, but also less sharp money calibrating lines. Books move lines aggressively after any significant action on thin WNBA markets.

Current `SPORT_UNIT_CAP["WNBA"] = 4.0u` is appropriate. At normal sizing (1-2u), WNBA picks stay within book limits. At 3-4u with larger unit sizes, some picks may bump limits.

**Q15 — WNBA props and game flow correlation**

Blowout frequency: WNBA 2024 late-season had 87% of games decided by 6+ points, avg margin 16 pts. This is dramatically higher than NBA (typically 25-30% blowout rate). Implications:
- WNBA stars play 85-97% of game minutes, so coaches bench them in garbage time more readily than NBA coaches (no room to "play through")
- A 15-point Q3 deficit in a 40-min game is a stronger signal to bench stars than in a 48-min NBA game
- Pace correlation: WNBA team pace range (76-83 poss/40 min) is proportionally meaningful — a high-pace vs low-pace game difference of 7 possessions represents ~8.5% more possessions, which linearly inflates counting stats

Model implication: WNBA blowout sigmoid should trigger at a lower margin than NBA (recommend mid=15 vs NBA mid=20). Pace adjustment logic (same as NBA) applies within the 76-83 range.

---

**Implementation verdict:**

Key structural constants for WNBA model:

```python
# Game structure
WNBA_GAME_MINUTES = 40              # vs NBA 48
WNBA_LEAGUE_AVG_PACE = 80.0         # possessions per 40 min (2024: ~81, 2025: ~78.4; midpoint)
WNBA_LEAGUE_ORTG = 101.0            # points per 100 possessions (2024; vs NBA ~115)
WNBA_PACE_RANGE = (76, 83)          # poss/40 min range slow-to-fast teams

# Scoring scale (sanity check / gate threshold calibration)
WNBA_AVG_TEAM_PPG = 81.6            # 2024 league average
WNBA_AVG_PLAYER_PPG = 10.2          # implied top-8 rotation average

# Star utilization
WNBA_STARTER_MPG_PCT = 0.85         # avg WNBA starter plays 85% of game (vs NBA 71%)

# Blowout sigmoid — tighten for WNBA vs NBA
WNBA_BLOWOUT_MID = 15.0             # vs NBA mid=20.0; WNBA blowouts happen at lower margins
WNBA_BLOWOUT_MAX_REDUCTION = 0.22   # slightly more aggressive than NBA 0.19

# Market
WNBA_EDGE_THRESHOLD_MIN = 0.035     # vs NBA 0.025; higher vig (~-115/-115) requires higher edge
WNBA_PROP_LIMIT_APPROX = 750        # USD reference; not in model directly
```

Gates requiring WNBA-specific attention (Section 7 to address in detail):
- **G8B AST exempt at 4.5**: correct — Clark averages 8.4 APG so 4.5 is well below her prop line
- **G8 low-line ban**: WNBA PTS 8.5 lines are common (not low for this market) — may need lower absolute ban thresholds than NBA
- **KILLSHOT**: recommend excluding WNBA — lower limits, higher uncertainty, market too thin
- **STAT_CAP**: impose WNBA-specific cap (max 3-4 picks per stat per run) — smaller player pool
- **Edge threshold**: raise to 0.035 minimum for WNBA vs 0.025 NBA to compensate for higher vig

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
