# DFS Exclusion Pipeline — Complete System Spec
### Universal Multi-Sport Player Pool Builder for SaberSim
**Version 1.0 — April 2026**
**Author: Jono × Claude**

---

## 1. SYSTEM PHILOSOPHY

The goal is never to rank the "best" players. The goal is to **kill all the bad apples** so SaberSim's optimizer only works with clean player universes. Different contest types demand different levels of aggression — a single-entry pool should be tight and curated, a 150-max pool should be wide but still free of dead weight.

**Core Principle:** We are a filter, not an optimizer. SaberSim optimizes. We ensure it has nothing bad to optimize around.

**Three universal truths across all sports:**
1. Dead salary is dead salary — a player who is both cheap-output AND low-ceiling cannot help any lineup
2. High ownership with mediocre projection is a trap in every GPP
3. Fragility (risk of zero/bust) is sport-specific but always quantifiable

---

## 2. UNIVERSAL ARCHITECTURE

```
┌─────────────────────────────────────────────────────┐
│                    SPORT CONFIG                      │
│         (golf.yaml / nba.yaml / mlb.yaml)           │
│                                                      │
│  kill_layers:        scoring_weights:                │
│    - layer definitions   - CEIL/VAL/LEV/SAFE/+sport │
│    - thresholds per      - per contest type          │
│      contest type                                    │
│                                                      │
│  adj_projection:     pool_targets:                   │
│    - formula per         - size per contest           │
│      contest type        - min/max constraints        │
│                                                      │
│  feasibility:        data_requirements:              │
│    - salary tiers        - required inputs            │
│    - positions/stacks    - optional enrichment        │
│    - min viable checks                               │
└─────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────┐
│                     PIPELINE                         │
│                                                      │
│  1. INGEST ──→ Parse SaberSim + DK + supplementary  │
│  2. ENRICH ──→ Weather, matchup, SG, pace, park     │
│  3. KILL   ──→ Contest-specific exclusion layers     │
│  4. SCORE  ──→ CEIL/VAL/LEV/SAFE + sport-specific   │
│  5. ADJUST ──→ Contest-specific adjusted projections │
│  6. CHECK  ──→ Feasibility (salary, position, stack) │
│  7. SENSE  ──→ Dirichlet sensitivity analysis        │
│  8. EXPORT ──→ Pool reports + SaberSim upload CSVs   │
│  9. LOG    ──→ Record for threshold calibration       │
└─────────────────────────────────────────────────────┘
```

### 2.1 Step Details

**INGEST:** Every sport starts with the same two core files — a SaberSim export CSV and a DraftKings salary CSV. The SaberSim export is the richest single source: projections, ownership, percentile distributions, win/cut probabilities. DK salary provides the constraint grid.

**ENRICH:** Sport-specific supplementary data gets merged in. Golf gets weather + course + strokes gained. NBA gets pace + DvP + injury + B2B + referee. MLB gets park factors + umpire + lineup confirmation + pitcher matchup + bullpen + weather. This step is where sparsity lives — not every data point is available for every player. The system must degrade gracefully (fallback to base metrics when enrichment data is missing).

**KILL:** The exclusion engine. Each kill layer has a boolean flag (killed or not) and a reason tag. Layers are applied sequentially — a player killed by Layer 1 doesn't need evaluation by Layer 2 (but we log all flags anyway for the kill report). Thresholds vary by contest type.

**SCORE:** Surviving players get scored on 4 universal components (CEIL, VAL, LEV, SAFE) plus optional sport-specific components. All scoring uses P5-P95 robust normalization clipped 0-100.

**ADJUST:** This is the critical new addition. Instead of feeding SaberSim raw projections, we generate a contest-specific adjusted projection that blends ceiling, raw projection, ownership discount, and sport-specific modifiers. This is what actually gets uploaded as the "Projection" column.

**CHECK:** Before exporting, verify the pool is constructable. Can SaberSim build a valid 6-man (golf) or 8-man (NBA/MLB) roster under the salary cap? Are there enough players per salary tier? Per position? Per game (for stacking sports)?

**SENSE:** 50 Dirichlet weight perturbations to identify which players are CORE LOCK (in pool under all perturbations) vs BUBBLE (drop out under some). This tells you who to trust and who to watch.

**EXPORT:** Two files per contest: a full pool report (all scores, archetypes, flags) and a SaberSim upload CSV (Name, DFS ID, Salary, Adjusted Projection, Ownership). Plus a master kill report and cross-pool comparison.

**LOG:** After the slate completes, record which kills were correct (bad players stayed bad) and which were false kills (killed players who finished Top 10). This feeds threshold calibration over time.

---

## 3. UNIVERSAL SCORING FRAMEWORK

### 3.1 Four Core Components

| Component | What It Measures | Universal Formula |
|-----------|-----------------|-------------------|
| **CEIL** | Upside potential | Normalized p95 (or equivalent ceiling metric) |
| **VAL** | Salary efficiency | Points per $1k salary (raw projection / salary × 1000) |
| **LEV** | Contrarian edge | Ceiling rank minus ownership rank + discrete bucket boosts |
| **SAFE** | Floor protection | Normalized probability of meeting minimum viable output |

### 3.2 Normalization

All components use P5-P95 robust normalization:

```
normalized = (raw - P5) / (P95 - P5) × 100
clipped to [0, 100]
```

This prevents one outlier from compressing the entire field.

### 3.3 Leverage Bucket Boosts (Universal)

| Ownership Range | Boost |
|----------------|-------|
| < 8% | +8 |
| 8-15% | +4 |
| 15-22% | 0 |
| 22-30% | -4 |
| > 30% | -8 |

### 3.4 Contest Weight Matrix (Universal Structure)

Weights shift predictably across contest types: as field size grows, CEIL increases, SAFE decreases, LEV increases.

| Contest | CEIL | VAL | LEV | SAFE | Direction |
|---------|------|-----|-----|------|-----------|
| SE | Moderate | High | Low | High | Balanced, slight floor bias |
| 3MAX | Moderate+ | Moderate+ | Moderate | Moderate | Balanced, slight ceiling bias |
| 20MAX | High | Moderate | High | Low | Ceiling + leverage |
| 150MAX | Highest | Low | Highest | Lowest | Max ceiling, max contrarian |

Exact weights are sport-specific (see sections 4-6).

---

## 4. GOLF (PGA DFS)

### 4.1 Kill Layers

**Layer 1 — Dead Salary**
- Condition: Value (pts/$1k) in bottom quartile AND p95 ceiling in bottom quartile
- Logic: Player is both inefficient AND low-upside. No lineup construction justifies this player.
- Contest variation: Same threshold all contests (dead is dead)
- Typical kill count: 25-35 of 140-player field

**Layer 2 — MC Risk + No Ceiling**
- Condition: Make-cut probability below threshold AND p95 ceiling below field median
- Logic: High bust risk with no compensating upside. If they survive the cut, they don't have the ceiling to win anyway.
- Contest variation:

| Contest | MC Threshold | Why |
|---------|-------------|-----|
| SE | > 32% miss | Can't afford a bust in one lineup |
| 3MAX | > 36% miss | Slight more tolerance |
| 20MAX | > 40% miss | Can absorb some busts across entries |
| 150MAX | > 45% miss | Volume can absorb high bust rate |

- Enhancement: When SG data is available, use SG-enhanced fragility. Putting-reliant players (sg_putt / total_sg > 0.40) get a fragility boost because putting is the highest-variance skill. Blend: 60% base MC fragility + 40% putting reliance.

**Layer 3 — Chalk Traps (GPP only, not SE)**
- Condition: Ownership rank significantly exceeds a blend of projection rank and ceiling rank
- Logic: Public is overvaluing this player relative to what projections and ceiling suggest. High ownership + mediocre output = dead leverage.
- Formula: `chalk_gap = own_rank - (0.5 × proj_rank + 0.5 × ceil_rank)`
- Contest variation:

| Contest | Threshold | Why |
|---------|----------|-----|
| SE | Not applied | SE is about correctness, not leverage |
| 3MAX | Not applied | Too few entries for chalk to matter much |
| 20MAX | Bottom 15% chalk gap | Starting to need differentiation |
| 150MAX | Bottom 10% chalk gap | Heavy leverage required |

**Layer 4 — Course Fit Mismatch (NEW)**
- Condition: Player's SG profile is fundamentally mismatched to course demands
- Logic: A course that demands OTT precision (tight fairways, heavy rough) will punish a player who gains strokes primarily from putting. Course context defines which SG components matter most.
- Implementation: Course demands a "SG priority vector" (e.g., TPC San Antonio = OTT: 0.35, APP: 0.30, ARG: 0.20, PUTT: 0.15). Compute dot product of player SG profile × course demand. Kill bottom 10% when SG data is available.
- Fallback: When SG data is unavailable (most players), this layer is skipped for that player.

**Layer 5 — Weather Fragility (NEW)**
- Condition: Player is on the disadvantaged wave side AND has low ceiling AND high MC risk
- Logic: Not every AM/PM player should be killed. But a borderline player on the bad wave side is worse than a borderline player on the good wave side. This layer tips the scales for bubble players.
- Implementation: Wave edge modifier (AM +1.5 to +2 in calm AM / windy PM conditions, reversed when PM is calm). Applied as a tie-breaker within bubble players, not as a standalone kill.

### 4.2 Scoring Weights

| Contest | CEIL | VAL | LEV | SAFE |
|---------|------|-----|-----|------|
| SE | 0.38 | 0.25 | 0.17 | 0.20 |
| 3MAX | 0.40 | 0.25 | 0.20 | 0.15 |
| 20MAX | 0.42 | 0.22 | 0.23 | 0.13 |
| 150MAX | 0.45 | 0.20 | 0.25 | 0.10 |

### 4.3 Adjusted Projection Formula

```
adj_proj = (w_proj × SS_Proj) + (w_ceil × p95) - (w_own × ownership%) + wave_edge
```

| Contest | w_proj | w_ceil | w_own | Wave Edge |
|---------|--------|--------|-------|-----------|
| SE | 0.55 | 0.30 | 0.15 | ±1.0 |
| 3MAX | 0.50 | 0.30 | 0.20 | ±1.0 |
| 20MAX | 0.45 | 0.30 | 0.25 | ±1.5 |
| 150MAX | 0.40 | 0.30 | 0.30 | ±2.0 |

### 4.4 Target Pool Sizes

| Contest | Target Pool | Min | Max |
|---------|------------|-----|-----|
| SE | 30-35 | 25 | 40 |
| 3MAX | 38-42 | 32 | 50 |
| 20MAX | 50-60 | 45 | 70 |
| 150MAX | 70-80 | 60 | 90 |

### 4.5 Feasibility Checks

- Can build a valid 6-man roster under $50,000 salary cap from this pool?
- Are there at least 3 players in each $1k salary tier ($6k-$7k, $7k-$8k, ..., $10k-$11k)?
- If a tier has < 2 players, flag for manual review (optimizer may be forced into bad combos)

### 4.6 Data Inputs

| Source | Data | Required? | Sparsity Risk |
|--------|------|-----------|---------------|
| SaberSim Export | Proj, Own, p25/50/75/85/95/99, MC%, Win%, Tee Time, Birdies, Bogeys, dk_std | **Required** | None — full field |
| DK Salary CSV | Name, ID, Salary | **Required** | None — full field |
| Strokes Gained | OTT, APP, ARG, PUTT per player | Optional | High — typically 5-15% of field from public sources |
| Weather (NWS) | Hourly wind/precip/temp for tournament dates | Optional | Low — NWS is reliable |
| Course Context | Par, yardage, rough, fairway width, green type | Optional | None — static per course |
| Historical Results | Player performance at this venue (last 3-5 years) | Optional | Medium — new courses/players have no history |

### 4.7 Archetypes (Relative to Pool)

Assigned after scoring, using pool medians as thresholds:

| Archetype | Condition |
|-----------|-----------|
| **Ceiling Assassin** | CEIL > pool 75th percentile AND LEV > pool median |
| **Stable Core** | SAFE > pool 75th percentile AND CEIL > pool median |
| **Leverage Pivot** | LEV > pool 75th percentile AND VAL > pool median |
| **Value Stabilizer** | VAL > pool 75th percentile AND SAFE > pool median |
| **Punt/Fragile Value** | Default — doesn't meet any archetype threshold |

---

## 5. NBA (DraftKings Classic)

### 5.1 Kill Layers

**Layer 1 — Dead Salary**
- Condition: Value (FPPG/$1k) in bottom quartile AND ceiling (p95 or recent high) in bottom quartile
- Logic: Same as golf — overpriced floor player with no ceiling
- Contest variation: Universal (dead is dead)
- Typical kill count: 15-25 of ~80-120 player slate

**Layer 2 — Minutes Uncertainty**
- Condition: Player's projected minutes have high variance OR player is GTD/Questionable with < 70% confidence of playing full role
- Logic: In NBA, minutes = opportunity. A player with uncertain minutes is a ticking time bomb. Even if they play, a coach pulling them at 22 minutes instead of 34 destroys their value.
- Signals:
  - Official injury report status (GTD, Questionable, Probable)
  - Recent games played vs DNP pattern
  - Coach quote analysis (beat reporters)
  - Minutes variance last 10 games (std dev > 6 minutes = unstable)
  - Rookie/new acquisition without established role
- Contest variation:

| Contest | Threshold | Why |
|---------|----------|-----|
| SE | Kill any GTD without strong beat confirmation; kill if min_variance > 6 | Can't absorb a 15-min dud |
| 3MAX | Kill GTD without confirmation; flag min_variance > 7 | Slight tolerance |
| 20MAX | Kill OUT/Doubtful; flag GTD | Volume can absorb some |
| 150MAX | Kill only confirmed OUT | Maximum aggression = maximum roster options |

**Layer 3 — Pace-Down / Environment Death**
- Condition: Game total below threshold AND team pace rank is bottom quartile matchup AND spread implies non-competitive game
- Logic: NBA scoring is heavily driven by pace and game environment. A player in a 208-total game between two slow teams has a compressed ceiling. The game itself limits what's possible.
- Signals:
  - Vegas game total (primary)
  - Team pace rankings (both teams)
  - Projected pace = average of both teams' pace, adjusted for matchup history
  - Historical performance in slow-pace games
- Thresholds:

| Contest | Total Threshold | Combined With |
|---------|----------------|---------------|
| SE | < 215 AND both teams bottom-10 pace | Kill if also below-median ceiling |
| 3MAX | < 213 AND both teams bottom-8 pace | Kill if also below-median ceiling |
| 20MAX | < 210 AND both teams bottom-5 pace | Kill if ceiling < 40th percentile |
| 150MAX | < 208 | Kill only extreme pace-down |

**Layer 4 — Blowout Risk**
- Condition: Game spread > threshold AND player is on expected winning team AND player's value is counting-stat dependent
- Logic: Big favorites pull starters in the 4th quarter (sometimes late 3rd). A player projected for 42 FP in a -14 spread game might only get 28 minutes. Stars on heavy favorites are ownership traps.
- Key distinction: Players on the LOSING side of a blowout can actually benefit (garbage time stats). This layer only kills players on the favored side.
- Signals:
  - Game spread (absolute value)
  - Player's team favored or underdog
  - Player's usage rate (high-usage stars lose more from reduced minutes)
  - Backup quality (if backup is good, coach pulls starter earlier)
- Thresholds:

| Contest | Spread Threshold | Additional Condition |
|---------|-----------------|---------------------|
| SE | Spread > 9 | Kill favored-side players with ceiling < pool median |
| 3MAX | Spread > 10 | Same |
| 20MAX | Spread > 11 | Kill only if ceiling < 40th percentile |
| 150MAX | Spread > 13 | Kill only extreme blowouts |

**Layer 5 — B2B Fatigue**
- Condition: Player is on second game of back-to-back AND has documented fatigue splits
- Logic: Not all B2B is equal. Home B2B with short travel is manageable. Road B2B after a cross-country flight is brutal. The key is the combination of B2B + travel distance + age + minutes load.
- Signals:
  - B2B flag (yes/no)
  - Home/away for both games
  - Travel distance between cities
  - Player age (>30 = higher fatigue impact)
  - Minutes played in first game of B2B
  - Season-long minutes average (heavy-minutes players fatigue more)
- Fatigue Score: `fatigue = b2b_flag × (1 + travel_factor + age_factor + minutes_factor)`
  - travel_factor: 0 for same city, 0.1 for < 500 miles, 0.2 for 500-1500 miles, 0.3 for > 1500 miles
  - age_factor: 0 for < 28, 0.1 for 28-32, 0.2 for > 32
  - minutes_factor: 0 for < 32 mpg, 0.1 for 32-36, 0.2 for > 36
- Kill if fatigue score > threshold AND ceiling is below median

| Contest | Fatigue Kill Threshold |
|---------|----------------------|
| SE | > 1.2 |
| 3MAX | > 1.3 |
| 20MAX | > 1.4 |
| 150MAX | > 1.5 (only extreme cases) |

**Layer 6 — Chalk Traps**
- Same logic as golf. Ownership rank far exceeds projection/ceiling rank.
- NBA-specific wrinkle: "narrative ownership" — player facing former team, player coming off career high, player with dramatic injury return. Public inflates ownership on stories. The system flags when ownership rank is 15+ spots above projection rank.

| Contest | Threshold |
|---------|----------|
| SE | Not applied |
| 3MAX | Not applied |
| 20MAX | Bottom 15% chalk gap |
| 150MAX | Bottom 10% chalk gap |

**Layer 7 — Defensive Matchup Kill (NEW)**
- Condition: Player faces elite positional defender AND player's recent production already trends below average
- Logic: A slumping scorer against a DPOY candidate is a double kill. But don't kill a hot player just because the defense is tough — great players overcome matchups. This is a tiebreaker for borderline players.
- Data: DvP (Defense vs Position) rankings, ideally opponent defensive rating at the player's position
- Kill only if: DvP bottom quartile AND player's last-5 FPPG is below season average AND ceiling is below pool median

### 5.2 Scoring Weights

| Contest | CEIL | VAL | LEV | SAFE | PACE* | MATCH* |
|---------|------|-----|-----|------|-------|--------|
| SE | 0.30 | 0.25 | 0.10 | 0.20 | 0.10 | 0.05 |
| 3MAX | 0.32 | 0.23 | 0.15 | 0.15 | 0.10 | 0.05 |
| 20MAX | 0.35 | 0.20 | 0.20 | 0.10 | 0.10 | 0.05 |
| 150MAX | 0.38 | 0.17 | 0.25 | 0.05 | 0.10 | 0.05 |

*PACE = normalized game pace projection (pace combo of both teams)
*MATCH = DvP matchup quality (how much the opposing defense allows to this position)

### 5.3 Adjusted Projection Formula

```
adj_proj = (w_proj × SS_Proj) + (w_ceil × ceiling) - (w_own × ownership%) + pace_boost + matchup_mod
```

Where:
- pace_boost = (game_pace_rank / max_pace_rank) × scale_factor (higher = faster pace = boost)
- matchup_mod = DvP percentile adjustment (positive for weak defense, negative for strong)

| Contest | w_proj | w_ceil | w_own | Pace Scale | Matchup Scale |
|---------|--------|--------|-------|------------|---------------|
| SE | 0.55 | 0.25 | 0.10 | 1.0 | 0.5 |
| 3MAX | 0.50 | 0.25 | 0.15 | 1.0 | 0.5 |
| 20MAX | 0.45 | 0.25 | 0.20 | 1.5 | 0.5 |
| 150MAX | 0.40 | 0.25 | 0.25 | 2.0 | 0.5 |

### 5.4 Target Pool Sizes (Slate-Size Dependent)

| Slate Size | SE | 3MAX | 20MAX | 150MAX |
|------------|-----|------|-------|--------|
| 2-3 games (15-25 players) | ALL players* | ALL* | ALL* | ALL* |
| 4-5 games (30-45 players) | 22-28 | 25-32 | 30-38 | 35-42 |
| 6-8 games (50-70 players) | 28-35 | 32-40 | 40-50 | 50-60 |
| 9+ games (75-110 players) | 35-45 | 40-50 | 50-65 | 60-80 |

*On tiny slates (2-3 games), killing players is dangerous because SaberSim needs roster construction flexibility. Apply kill layers very lightly — only Dead Salary and confirmed OUT.

### 5.5 Feasibility Checks

**Position Coverage:**
DK NBA Classic requires: PG, SG, SF, PF, C, G, F, UTIL (8 roster spots)
- Minimum 3 viable players per primary position (PG, SG, SF, PF, C)
- If any position has < 3, flag immediately — the optimizer cannot build diverse rosters

**Game Stack Coverage:**
- For every game in the pool, need at least 3 players (to enable meaningful game correlation)
- If a high-total game has < 3 surviving players, consider rescuing the highest-scored killed player from that game

**Salary Distribution:**
- Salary cap: $50,000 across 8 players = $6,250 avg
- Need players in every $1k tier from min salary to max
- Cannot have pool skew entirely to one salary range

**Slate-Size Override:**
- On 2-game slates: disable all kill layers except confirmed OUT
- On 3-game slates: only apply Dead Salary kill
- Below 4 games, the pool is so small that any kill risks breaking feasibility

### 5.6 Data Inputs

| Source | Data | Required? | Sparsity Risk |
|--------|------|-----------|---------------|
| SaberSim Export | Proj, Own, ceiling, floor, minutes, usage | **Required** | None |
| DK Salary CSV | Name, ID, Salary, Position, Game Info | **Required** | None |
| Vegas Lines | Spread, Total, Moneyline per game | **Required** | Very low |
| Injury Reports | Official NBA injury report | **Required** | None — published daily |
| Team Pace | Pace rankings (possessions per 48) | Recommended | Low — stats sites |
| DvP Rankings | Defense vs Position | Recommended | Low — stats sites |
| B2B Schedule | Back-to-back flags + travel | Recommended | None — schedule is public |
| Minutes Logs | Last 10 games minutes per player | Recommended | Low |
| Usage Rate | Recent usage rate vs season | Optional | Low |
| Referee Crew | Ref assignments + tendencies | Optional | Medium — not always published early |
| Confirmed Lineups | Starting lineups | **Critical** | Published ~30 min before lock |
| Beat Reporter Intel | GTD/rotation updates | Optional | High — requires manual collection |

### 5.7 Archetypes

| Archetype | NBA Meaning |
|-----------|------------|
| **Ceiling Assassin** | High-usage star in pace-up spot with moderate ownership |
| **Stable Core** | High-floor player with consistent minutes and role clarity |
| **Leverage Pivot** | Underowned player with strong matchup/pace environment |
| **Value Stabilizer** | Salary-efficient role player with locked minutes |
| **Punt/Fragile Value** | Cheap player with upside but minutes/role risk |
| **Game Stack Anchor** | (NBA-specific) Player from highest-total game who enables correlation |

### 5.8 NBA-Specific Correlation Considerations

SaberSim handles in-game correlation, but the pool needs to ENABLE good correlations:

- **High-total games must have adequate representation.** If the highest-total game is 238.5 and only 2 players survived the pool, SaberSim can't build game stacks. The feasibility check should ensure at least 4 players per high-total game (top 3 totals on slate).
- **Bring-back viability.** For each game, the pool should have players from BOTH teams so SaberSim can build bring-back lineups (Player A from Team X stacked with Player B from Team Y in the same high-total game).
- **Anti-correlation with blowout.** Don't have 6 players from a -14 spread game — the blowout risk means stacking both sides is dangerous. Cap representation from extreme-spread games.

---

## 6. MLB (DraftKings Classic)

### 6.1 Kill Layers

**Layer 1 — Dead Salary (Hitters)**
- Condition: Value (proj/$1k) in bottom quartile AND ceiling in bottom quartile
- Same as other sports. Overpriced floor guys with no pop.

**Layer 1B — Dead Arm (Pitchers)**
- Condition: Pitcher has declining velocity (last 3 starts trend), rising hard-hit rate (> 40%), and poor xFIP (> 4.50 in a neutral park)
- Logic: Pitchers are binary — a bad pitcher gets shelled and goes negative. Unlike hitters who can go 0-for-4 and still not hurt you much, a pitcher giving up 7 runs actively destroys your lineup.
- Enhancement: Adjust xFIP for park factor. A 4.50 xFIP at Coors is death. A 4.50 xFIP at Oracle Park is mediocre but survivable.

**Layer 2 — Lineup Uncertainty (CRITICAL for MLB)**
- Condition: Player is NOT in a confirmed batting order
- Logic: MLB lineups are not guaranteed until ~1-2 hours before first pitch. A player who isn't in the lineup scores 0.00 DK points. This is the #1 risk in MLB DFS.
- Implementation:
  - Before lineups confirmed: Flag all players as "unconfirmed" — do NOT kill yet but mark as risky
  - After lineups confirmed: Kill all players NOT in the confirmed lineup
  - Lineup order matters: A player batting 8th has fundamentally fewer AB opportunities than a player batting 2nd
- The system should have TWO modes:
  - **Pre-lock mode:** Run pipeline with projected lineups, flag unconfirmed
  - **Lock-time mode:** Re-run with confirmed lineups, hard-kill anyone not starting

**Layer 3 — Platoon Disadvantage**
- Condition: Hitter faces a pitcher with dominant same-side splits AND hitter's own splits show significant platoon weakness
- Logic: A left-handed hitter facing an elite LHP who holds lefties to a .250 wOBA is dead. The handedness matchup is the strongest single predictor of hitter performance in MLB.
- Signals:
  - Pitcher's splits vs same-hand hitters (wOBA, K%, BB%)
  - Hitter's splits vs same-hand pitchers (wOBA, ISO, K%)
  - Kill if: hitter wOBA vs same-hand < .280 AND pitcher wOBA vs same-hand < .290
- Contest variation:

| Contest | Platoon Kill Threshold |
|---------|----------------------|
| SE | Hitter wOBA < .290 vs hand + pitcher holds < .300 |
| 3MAX | Hitter wOBA < .285 + pitcher < .295 |
| 20MAX | Hitter wOBA < .275 + pitcher < .285 |
| 150MAX | Hitter wOBA < .265 + pitcher < .275 (only extreme splits) |

**Layer 4 — Park-Down**
- Condition: Hitter is playing in an extreme pitcher's park AND game total confirms low-scoring environment
- Logic: Park factor is the silent killer in MLB DFS. A hitter at Oracle Park (PF 0.88 for RHB) with a 7.0 game total has a compressed ceiling. The park literally reduces how far the ball travels.
- Signals:
  - Park factor (overall + by handedness)
  - Game total (Vegas)
  - Team implied run total
- Kill if: Park factor < 0.92 for hitter's handedness AND team implied runs < 3.5 AND hitter ceiling < pool median

**Layer 5 — Lineup Order Risk**
- Condition: Hitter is confirmed batting 7th or lower with no significant stolen base upside
- Logic: Batting order directly determines plate appearances. A player batting 2nd gets ~4.5 PA per game. A player batting 8th gets ~3.2 PA. That's a ~30% reduction in opportunity. The only exception is if the player has steal upside (which is DK-specific scoring).
- Kill if: Batting 7th+ AND stolen base probability < 10% AND salary > $3,500 (cheap guys batting low are fine for punt plays)

| Contest | Kill Batting Order |
|---------|-------------------|
| SE | 7th+ (with conditions above) |
| 3MAX | 8th+ |
| 20MAX | 8th+ (only if also low ceiling) |
| 150MAX | 9th only |

**Layer 6 — Chalk Traps**
- Same framework as golf/NBA. Ownership rank exceeding projection/ceiling rank.
- MLB-specific: "Narrative stacks" — public loves stacking against a "bad" pitcher who is actually improved. Or stacking the Coors game regardless of actual matchup quality.

**Layer 7 — Umpire Factor (NEW)**
- Condition: Home plate umpire has extreme tendencies that hurt specific player types
- Logic: A tight-zone umpire increases strikeouts and decreases scoring. This helps pitchers and hurts free-swinging hitters. A wide-zone umpire does the opposite.
- Signals:
  - Umpire's historical run scoring (runs/game above/below average)
  - Umpire's K rate impact
  - Umpire's WHIP impact on pitchers
- Kill if: Umpire is extreme tight-zone (top 10% K-rate ump) AND hitter has K-rate > 28% AND hitter's ceiling is below pool median
- Also kill pitcher if: Umpire is extreme wide-zone (bottom 10%) AND pitcher relies on called strikes (low swinging strike rate)

**Layer 8 — Bullpen Exposure (Pitchers)**
- Condition: Starting pitcher has a short leash (low pitch count tendency, recent injury, early hooks) AND bullpen behind them is strong
- Logic: A pitcher who goes 5 innings gets fewer K opportunities, fewer win probability points, and hands the ball to a good bullpen that won't blow the lead but also limits the pitcher's stat accumulation.
- Alternative concern: Pitcher with weak bullpen may lose quality start/win despite pitching well
- Kill if: Pitcher's recent average innings < 5.5 AND K/9 < 7 AND salary > $8,000

### 6.2 Scoring Weights

| Contest | CEIL | VAL | LEV | SAFE | STACK* |
|---------|------|-----|-----|------|--------|
| SE | 0.28 | 0.25 | 0.10 | 0.22 | 0.15 |
| 3MAX | 0.30 | 0.23 | 0.15 | 0.17 | 0.15 |
| 20MAX | 0.33 | 0.20 | 0.20 | 0.12 | 0.15 |
| 150MAX | 0.35 | 0.17 | 0.25 | 0.08 | 0.15 |

*STACK = Team stacking potential. Measures how "stackable" a player's team is — combines team implied runs, park factor boost, opposing pitcher vulnerability, and how many quality hitters are in the same lineup. A player on a 5.5 implied run team at Coors is inherently more valuable than an identical player on a 3.2 implied run team at Oracle Park.

### 6.3 Adjusted Projection Formula

```
HITTERS:
adj_proj = (w_proj × SS_Proj) + (w_ceil × ceiling) - (w_own × ownership%)
           + park_boost + lineup_order_mod + handedness_mod

PITCHERS:
adj_proj = (w_proj × SS_Proj) + (w_ceil × ceiling) - (w_own × ownership%)
           + park_boost + ump_mod + bullpen_mod
```

Where:
- park_boost = (park_factor - 1.0) × 5.0 for hitters (Coors = +0.5 to +1.0 point boost)
- lineup_order_mod = batting_position_value (1st-3rd: +1.0, 4th-5th: +0.5, 6th: 0, 7th+: -0.5)
- handedness_mod = platoon advantage/disadvantage adjustment
- ump_mod = umpire tendency adjustment (run-friendly ump helps hitters, hurts pitchers)
- bullpen_mod = bullpen quality behind pitcher (good bullpen = slightly lower adj because limits ceiling)

| Contest | w_proj | w_ceil | w_own | Park Scale | Order Scale |
|---------|--------|--------|-------|------------|-------------|
| SE | 0.55 | 0.25 | 0.10 | 1.0 | 0.5 |
| 3MAX | 0.50 | 0.25 | 0.15 | 1.0 | 0.5 |
| 20MAX | 0.45 | 0.25 | 0.20 | 1.5 | 0.5 |
| 150MAX | 0.40 | 0.25 | 0.25 | 2.0 | 1.0 |

### 6.4 Target Pool Sizes

| Slate Size | SE | 3MAX | 20MAX | 150MAX |
|------------|-----|------|-------|--------|
| Early (4-6 games) | 30-35 | 35-40 | 40-50 | 50-60 |
| Main (8-12 games) | 40-50 | 45-55 | 55-70 | 70-90 |
| Night (3-5 games) | 25-30 | 28-35 | 32-42 | 40-50 |

### 6.5 Feasibility Checks

**Position Coverage (DK MLB Classic: P, P, C, 1B, 2B, 3B, SS, OF, OF, OF = 10 roster spots):**
- Minimum 2 viable pitchers per pool (often only 3-4 are even worth considering)
- Minimum 2 viable players per infield position (C, 1B, 2B, 3B, SS)
- Minimum 4 viable outfielders
- Pitcher quality is make-or-break — if the pool has only bad pitcher options, the entire pool is compromised

**Stack Coverage (THE MOST CRITICAL CHECK IN MLB):**
- For every team with 4.0+ implied runs, need at least 4 hitters in the pool from that team
- Without 4+ hitters from a stack-worthy team, SaberSim cannot build meaningful team stacks
- Priority teams: top 3 implied run totals must have full stack representation
- Bring-back check: for each high-total game, need at least 2 hitters from EACH side

**Stack Integrity Rule:** If a kill layer removes a player from a top-3 implied run team, check if that team still has 4+ hitters in the pool. If not, rescue the highest-scored killed player from that team. **Stacks take priority over individual player quality.**

**Salary Distribution:**
- Salary cap: $50,000 across 10 players = $5,000 avg
- Need pitcher options at multiple salary tiers
- Need hitter options from min salary ($2,000) through max
- Two-pitcher construction means pitcher salary allocation is critical

### 6.6 Data Inputs

| Source | Data | Required? | Sparsity Risk |
|--------|------|-----------|---------------|
| SaberSim Export | Proj, Own, ceiling, floor per player | **Required** | None |
| DK Salary CSV | Name, ID, Salary, Position, Game Info | **Required** | None |
| Confirmed Lineups | Batting order for each team | **CRITICAL** | Available 1-2hrs pre-lock |
| Vegas Lines | Game total, team total, moneyline | **Required** | Very low |
| Park Factors | Overall + by handedness | **Required** | None — static per park |
| Pitcher Stats | xFIP, SIERA, K/9, BB/9, HR/FB, velocity | Recommended | Low |
| Batter Splits | wOBA/ISO vs LHP and vs RHP | Recommended | Low |
| Umpire Assignment | HP umpire + tendencies | Recommended | Medium — sometimes late |
| Weather | Wind speed/direction, temp, dome flag | Recommended | Low for outdoor parks |
| Bullpen Data | Bullpen ERA, recent usage, availability | Optional | Medium |
| Stolen Base Rates | Sprint speed, SB attempts | Optional | Low |
| Recent Form | Last 14-day wOBA, last 7-day splits | Optional | Low |

### 6.7 Archetypes

| Archetype | MLB Meaning |
|-----------|------------|
| **Ceiling Assassin** | Power hitter in plus matchup at hitter-friendly park |
| **Stable Core** | High-OBP hitter batting 1-3 with consistent AB volume |
| **Leverage Pivot** | Underowned hitter on a high-implied-run team (public stacking the other team) |
| **Value Stabilizer** | Cheap hitter with locked lineup spot and steal upside |
| **Stack Anchor** | Best hitter on the most stackable team (often highest correlated player) |
| **Ace Lock** | Top-tier pitcher in plus matchup — these are essentially required plays |
| **Punt Arm** | Cheap pitcher with decent floor (5+ innings likely) as salary relief |

### 6.8 MLB-Specific Correlation Considerations

Stacking is EVERYTHING in MLB DFS. The system must protect stack integrity:

- **Primary stack:** 4-5 hitters from the same team, ideally consecutive in the batting order (1-2-3-4-5 or 2-3-4-5-6). Runs score in bunches — when one guy reaches base, the next guy drives him in. Individual hitter ceilings are low; team stack ceilings are high.
- **Bring-back:** 1-2 hitters from the opposing team in the same game. High-total games tend to see runs from both sides.
- **Wrap-around stacks:** Batting order 6-7-8-9-1 can be viable in high-run environments — don't over-kill bottom-of-order hitters from plus-matchup teams.
- **Pitcher-stack correlation:** Your pitcher is negatively correlated with hitters on the same team they face. SaberSim handles this, but the pool needs to enable it by having pitchers from different games than your primary stack.

---

## 7. ADJUSTED PROJECTION — DEEP DIVE

This is the single most impactful addition to the system. The raw SS_Proj is a point estimate that SaberSim treats as gospel. By feeding it a modified number, we change what the optimizer prioritizes.

### 7.1 Why Adjusted Projections Matter

SaberSim's optimizer maximizes total projection under the salary cap. If Player A projects 42.5 and Player B projects 41.8, SaberSim picks Player A. It doesn't care that Player A is 32% owned and Player B is 8% owned. It doesn't care that Player B has a higher ceiling. It doesn't care that Player B is in a pace-up spot.

The adjusted projection embeds all of that context INTO the number SaberSim optimizes on.

### 7.2 Ownership Discount Mechanics

The ownership discount is not linear. Going from 5% to 10% ownership is barely noticeable. Going from 20% to 30% is significant. Going from 30% to 45% is massive.

```
own_penalty_curve:
  0-10%:  penalty_multiplier = 0.5  (barely noticeable)
  10-20%: penalty_multiplier = 1.0  (standard)
  20-30%: penalty_multiplier = 1.5  (accelerating)
  30-40%: penalty_multiplier = 2.0  (heavy)
  40%+:   penalty_multiplier = 3.0  (massive)
```

So a 35% owned player doesn't just get a 35 × w_own penalty — they get 35 × w_own × 2.0.

### 7.3 Ceiling Integration

Using raw p95 in the formula can distort things because p95 is on a different scale than SS_Proj. We normalize: `ceil_contribution = (player_p95 - field_median_p95) / field_std_p95 × scaling_factor`

This ensures the ceiling component adds proportional upside without overwhelming the projection component.

### 7.4 Sport-Specific Modifiers

These are additive adjustments after the base formula:

**Golf:** wave_edge (±1.0 to ±2.0 based on wind differential)
**NBA:** pace_boost (0 to +3.0 based on game pace environment) + matchup_mod (±1.0 based on DvP)
**MLB:** park_boost (±2.0 based on park factor) + order_mod (±1.0 based on batting position) + handedness_mod (±1.0 based on platoon advantage)

---

## 8. SENSITIVITY ANALYSIS

### 8.1 Dirichlet Perturbation

Generate 50 random weight vectors from a Dirichlet distribution centered on the target weights. Re-score and re-rank the pool under each perturbation. Players who survive the pool cut in all 50 are CORE LOCKS. Players who drop out in 5+ perturbations are BUBBLE.

### 8.2 Output

| Label | Condition | Meaning |
|-------|-----------|---------|
| CORE LOCK | In pool for 50/50 perturbations | Safe to include regardless of weight uncertainty |
| STRONG | 45-49/50 | Very likely in, minor risk |
| BUBBLE | 35-44/50 | Could go either way — watch for late news |
| FRINGE | 25-34/50 | More out than in — needs strong reason to include |
| CUT | < 25/50 | Not in pool under most scenarios |

### 8.3 Actionable Use

The sensitivity labels tell you where to spend manual research time. CORE LOCKS don't need more analysis — they're in. BUBBLE players are where your edge lives. If you find a piece of information the system doesn't have (beat reporter tip, lineup change, weather shift), and it affects a BUBBLE player, that's where you gain edge over the system alone.

---

## 9. BACKTESTING & CALIBRATION

### 9.1 Slate Logging

After every slate completes, log:

```csv
date, sport, contest_type, player_name, in_pool, kill_reason (if killed),
actual_DK_points, actual_finish_rank, was_in_optimal_lineup,
projected_own, actual_own
```

### 9.2 Calibration Metrics

**Kill Accuracy:**
- True Kill Rate: % of killed players who finished outside Top 30% (good kill)
- False Kill Rate: % of killed players who finished Top 10% (bad kill — missed a winner)
- Target: True Kill Rate > 85%, False Kill Rate < 5%

**Pool Inclusion Accuracy:**
- Optimal Capture Rate: What % of the DK optimal lineup's players were in our pool?
- Target: > 80% of optimal lineup players were in pool (missing 1 of 6 in golf, 1-2 of 8 in NBA/MLB is acceptable)

**Threshold Drift:**
If False Kill Rate rises above 8% for a specific kill layer over 10+ slates, loosen that threshold by one step. If True Kill Rate drops below 80%, tighten it.

### 9.3 A/B Testing Framework

Run two pipeline versions in parallel (different thresholds) and track which one has better Optimal Capture Rate over 20 slates. The winning thresholds become the new default.

### 9.4 Seasonal Recalibration

- **Golf:** Recalibrate MC risk thresholds every 10 events. Course difficulty varies — Augusta MC rates are different from the Waste Management Open.
- **NBA:** Recalibrate pace/total thresholds monthly. League-wide pace trends shift through the season (faster early, slower in playoffs).
- **MLB:** Recalibrate platoon thresholds monthly. Early-season splits are unreliable (small sample); mid-season splits stabilize.

---

## 10. SLATE-SIZE ADAPTATION

Not all slates are equal. A 2-game NBA slate is fundamentally different from a 10-game slate. The system must adapt.

### 10.1 Small Slate Rules

| Slate Size | Kill Aggressiveness | Pool Size | Why |
|------------|-------------------|-----------|-----|
| Tiny (2-3 games NBA, 3-4 games MLB) | Minimal — only confirmed OUT + Dead Salary | Nearly full field | Too few players to exclude aggressively |
| Small (4-5 games NBA, 5-6 games MLB) | Light — add MC Risk / Minutes layers | 70-80% of field | Some filtering but preserve options |
| Standard (6-8 games NBA, 8-10 games MLB) | Normal — all layers active | 50-65% of field | Full pipeline |
| Large (9+ games NBA, 11+ games MLB) | Aggressive — tightest thresholds | 35-50% of field | Can afford to be selective |
| Golf | Always 140ish field | Standard rules | Field size is consistent |

### 10.2 Dynamic Pool Sizing

Rather than fixed pool targets, use a formula:

```
target_pool = field_size × contest_retention_rate

contest_retention_rates:
  SE:     0.22 - 0.25
  3MAX:   0.28 - 0.32
  20MAX:  0.38 - 0.42
  150MAX: 0.50 - 0.55
```

For a 100-player NBA slate:
- SE pool ≈ 22-25 players
- 150MAX pool ≈ 50-55 players

For a 30-player NBA slate:
- SE pool ≈ 22-25 players (minimum floor — don't go below 20)
- 150MAX pool ≈ 28-30 players (nearly all)

---

## 11. IMPLEMENTATION ROADMAP

### Phase 1: Fix Golf Pipeline (Immediate)
- Add adjusted projections to golf pipeline
- Regenerate VTO 2026 upload CSVs with adjusted projections
- Verify SaberSim builds less chalky lineups

### Phase 2: NBA Pipeline (Next)
- Build NBA-specific kill layers
- Integrate vegas lines, pace data, DvP
- Handle slate-size adaptation
- Build NBA adjusted projection formula

### Phase 3: MLB Pipeline (After NBA)
- Build MLB-specific kill layers
- Integrate lineup confirmation workflow (pre-lock vs lock-time modes)
- Build stacking feasibility checks
- Handle park factors, umpire, handedness

### Phase 4: Backtesting Framework
- Build slate logging
- Implement calibration metrics
- Start tracking kill accuracy across sports
- Build threshold drift detection

### Phase 5: Automation & Speed
- Script the full pipeline so each slate is a single command
- Auto-pull SaberSim exports and DK salaries
- Auto-fetch weather, lineups, injury reports
- Output ready-to-upload CSVs in < 60 seconds

---

## 12. OPEN QUESTIONS & FUTURE CONSIDERATIONS

1. **Showdown/Captain Mode:** Single-game contests have totally different dynamics. Captain multiplier changes everything. Do we build a separate kill framework for Showdown?

2. **Live / In-Game Adjustments:** For NBA and MLB, late scratches happen after we build pools. Do we build a "hot swap" mechanism that can quickly re-run the pipeline with a player removed?

3. **Ownership Leverage vs Correlation:** In large-field contests, is it better to be contrarian on individual players or contrarian on game stacks? The system currently treats ownership at the player level, but game-level ownership (% of lineups using players from Game X) might be more important.

4. **Multi-Entry Optimization:** For 20-max and 150-max, you're not building one lineup — you're building a portfolio. Should the pool be different for "lineup 1 of 150" vs "lineup 150 of 150"? SaberSim handles this, but our adjusted projections might benefit from a "diversity bonus" that encourages the optimizer to spread across more players.

5. **Cross-Sport Bankroll Allocation:** If you're playing golf + NBA + MLB on the same day, how do you allocate bankroll across sports? Does the strength of edge in each sport determine allocation?

6. **Machine Learning Layer:** After 50+ slates of backtesting data, can we train a classifier that predicts "kill" vs "keep" better than our rule-based thresholds? The rules are a great starting point, but ML could find interaction effects we miss (e.g., "low ceiling + high ownership + bad weather + PM wave" is worse than the sum of its parts).
