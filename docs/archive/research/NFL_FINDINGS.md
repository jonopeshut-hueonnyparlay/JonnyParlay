# NFL Model Research Findings
**Completed:** 2026-05-21 | **Merged from:** NFL_FINDINGS_G1 through G10

---

## Table of Contents
- [G1: PASS_YARDS + RUSH_YARDS](#g1-pass_yards--rush_yards)
- [G2: REC_YARDS + RECEPTIONS](#g2-rec_yards--receptions)
- [G3: PASS_TDS, RUSH_TDS, REC_TDS, INT](#g3-pass_tds-rush_tds-rec_tds-int)
- [G4: Game Lines — SPREAD, TOTAL, TEAM_TOTAL, ML](#g4-game-lines--spread-total-team_total-ml)
- [G5: NB_R Values, Platt Policy, Correlation Groups](#g5-nb_r-values-platt-policy-correlation-groups)
- [G6: Blowout Sigmoid, Home/Away Delta, Opponent Quality](#g6-blowout-sigmoid-homeaway-delta-opponent-quality)
- [G7: Role Tiers, Kickers/DST, STAT_CAP, KILLSHOT, SHADOW](#g7-role-tiers-kickersdst-stat_cap-killshot-shadow)
- [G8: OT Effects, Playoffs, TNF/MNF/SNF, Zero-Inflation](#g8-ot-effects-playoffs-tnfmnfsnf-zero-inflation)
- [G9: Context Keywords, Injury Policy, Grading, SaberSim CSV](#g9-context-keywords-injury-policy-grading-sabersim-csv)
- [G10: Odds API Market Keys, Book Coverage, Cross-Cutting](#g10-odds-api-market-keys-book-coverage-cross-cutting)

---

## G1: PASS_YARDS + RUSH_YARDS

### PASS_YARDS

#### Empirical Distribution Parameters (2022–2024, starting QBs, min 10 starts)

| QB Tier | Mean (yards/game) | σ | CV |
|---------|-------------------|---|----|
| Elite (Mahomes/Allen) | 280–310 | 55–65 | 0.20–0.23 |
| Upper-mid (Burrow/Hurts) | 250–280 | 60–70 | 0.24–0.27 |
| Mid-tier starter | 215–250 | 65–75 | 0.28–0.32 |
| Weak starter | 180–215 | 68–80 | 0.35–0.42 |
| Backup (spot start) | 140–180 | 75–90 | 0.45–0.55 |

**Distribution fit:** Normal acceptable for per-QB per-game passing yards. Mild positive skew (~0.3–0.6). Gamma marginally better for pooled data, but Normal is the correct choice for projecting a specific known QB.

**Weather effects (quantified):**
- Wind ≥20 mph: −25 to −40 yards/game vs projection; completion rate drops ~5.6pp per 5 mph above 15 mph
- Temperature <25°F: −15 to −20 yards/game
- Rain + wind ≥15 mph: ~−45 yards/game
- **Gate:** Wind ≥20 mph or rain + wind ≥15 mph → suppress passing yards overs

**Opponent DVOA adjustment (if SaberSim fails to encode):**
- vs top-5 pass defense (DVOA ≤ −15%): ×0.88–0.92
- vs bottom-5 pass defense (DVOA ≥ +15%): ×1.08–1.12
- vs average: ×1.00

**Most common book lines:** 224.5, 244.5, 254.5, 274.5, 294.5, 309.5

**BLEND_ALPHA:** 0.25 (same as NBA/MLB). NFL passing yard lines are set by sharp books.

**Platt policy:** Identity calibration (A=1.0, B=0.0) at NFL launch. Do NOT share NBA Platt params. Minimum ~150–200 NFL prop picks needed to refit.

**STAT_CAP recommendation:** 4 per run. **Minimum line gate:** No bet below 150.5.

**Tier routing:** T1 (elite QB, favorable weather), T2 (standard conditions), T3 (weather-impaired or backup)

**Odds API market key:** `player_pass_yds`

---

### RUSH_YARDS

#### Empirical Distribution Parameters (2022–2024, RB1s, min 8 starts)

| RB Tier | Mean (yards/game) | σ | CV |
|---------|-------------------|---|----|
| Elite workhorse (Barkley/McCaffrey tier) | 90–125 | 45–55 | 0.44–0.55 |
| Standard RB1 workhorse | 65–85 | 38–50 | 0.53–0.65 |
| RB2 / committee (30-55% snap share) | 35–55 | 25–38 | 0.65–0.80 |
| Handcuff / spot back (<30% snap share) | 15–35 | 18–30 | 0.80–1.10 |

**Distribution fit:** Gamma (not Normal) — moderate to high positive skew (+0.6 to +1.2), near-zero floor. Normal acceptable as first pass if minimum line gate ≥15.5 applied.

**Pre-game predictability:** R² ≈ 0.25–0.35 (vs ~0.35–0.45 for passing yards). ~65–75% of rushing yard variance is random.

**Game script adjustments (flat multiplier above threshold, NOT sigmoid):**
- Team projected favorite ≥7: RB +8–12% rush yards
- Team projected underdog ≥7: RB −10–15% rush yards
- Team projected underdog ≥14: RB −25% rush yards

**Most common book lines:** 24.5, 34.5, 49.5, 64.5, 74.5, 89.5, 99.5

**STAT_CAP recommendation:** 5 per run. **Minimum line gate:** No bet below 24.5.

**Minimum gate for picks:** Projected carries ≥8 OR snap share ≥35%. DK salary <$5,000 → treat as RB2; <$4,000 → gate out.

**QB rushing yards:** Treat as distinct sub-tier. Only post picks on mobile QBs (proj rush yards ≥20.5). Gate out pocket passers (line ≤9.5).

**Odds API market key:** `player_rush_yds`

**Tier routing:** T1 only for elite workhorse, CV ≤0.55, proj yards ≥65, favorable DVOA matchup. T2 for standard RB1. T3 for committee/RB2.

---

### Cross-Section Notes

- PASS_YARDS and RUSH_YARDS use same BLEND_ALPHA = 0.25
- Platt: identity calibration for both at NFL launch. Count stats (TDs/INT) skip Platt entirely.
- NFL preseason sport key: `americanfootball_nfl_preseason` — disable/shadow for preseason

---

## G2: REC_YARDS + RECEPTIONS

### REC_YARDS

#### Distribution Parameters (2022–2024, by position tier)

| Tier | Mean (yd/g) | σ (yd/g) | CV |
|------|-------------|----------|----|
| WR1 (top-24 by targets) | 68–75 | 38–45 | 0.55–0.62 |
| WR2 (targets 4–7/g) | 42–52 | 28–36 | 0.62–0.72 |
| WR3/slot (targets <4/g) | 22–32 | 20–28 | 0.75–0.95 |
| TE1 (primary TE, ≥4 tgt/g) | 38–48 | 26–34 | 0.62–0.72 |
| TE2 (blocking TE, <3 tgt/g) | 10–20 | 12–18 | 0.85–1.10 |
| RB (receiving role) | 28–40 | 22–30 | 0.65–0.80 |

**Zero-inflation by tier:** WR1 ~4–8%, WR2 ~10–18%, WR3 ~20–30%, TE1 ~8–15%, TE2 ~30–50%, RB ~15–25%

**Distribution fit:** Normal with minimum projection gate (skip pick if proj <25 yards) as proxy for zero-inflation. Hurdle model deferred.

**Common lines:** WR1 elite: 64.5, 74.5, 79.5 | WR1 solid: 54.5, 59.5 | WR2: 34.5, 39.5, 44.5 | TE1: 34.5, 44.5

**STAT_CAP:** 4 per run. **Minimum projection gate:** Skip if proj <25 yards.

**Tier routing:** T1 for WR1 lines 44.5–74.5; T2 for WR2 lines 24.5–44.5; skip WR3.

**Odds API market key:** `player_reception_yds` (NOT `player_receiving_yds`)

---

### RECEPTIONS

#### Distribution Parameters (2022–2024)

| Tier | Mean (rec/g) |
|------|-------------|
| WR1 (top-24 by targets) | 5.5–6.5 |
| WR2 | 3.5–4.5 |
| WR3/slot | 2.0–3.0 |
| TE1 | 4.0–5.5 |
| RB (pass catcher) | 2.5–4.0 |

**Distribution fit:** Negative Binomial. NB_R["RECEPTIONS"] = 8 (unified default; 6 for TE/RB if per-position tuning done later).

**Gate:** No receptions OVER at line ≥7.5 (except manual override with win_prob ≥0.72 AND target proj ≥9.5 AND odds ≥−110).

**Correlation with REC_YARDS (same player):** Pearson r ≈ 0.70–0.80. Place in same CORR group — dedup per player.

**STAT_CAP:** 4 per run. **Minimum projection gate:** Skip if proj <2.5 receptions.

**Tier routing:** T1 for WR1 lines 4.5–6.5; T2 for WR2 lines 2.5–4.5.

**Odds API market key:** `player_receptions`

---

## G3: PASS_TDS, RUSH_TDS, REC_TDS, INT

### NB_R Summary Table

| Stat | Distribution | NB_R | Key |
|------|-------------|------|-----|
| PASS_TDS | Negative Binomial | 3.5 | NB beats Poisson; variance ~1.5–1.8× mean |
| RUSH_TDS | Negative Binomial | 1.2 | Near-Bernoulli; NB generalises for 1.5 line |
| REC_TDS | Negative Binomial | 1.0 | Even rarer than RUSH_TDS |
| INT | Negative Binomial | 3.0 | Poisson acceptable; NB marginally better |

### PASS_TDS

**Empirical distribution (starting QBs, 2022–2024):**

| Outcome | Estimated P |
|---------|------------|
| TDs = 0 | ~0.14–0.17 |
| TDs = 1 | ~0.26–0.29 |
| TDs = 2 | ~0.27–0.30 |
| TDs = 3 | ~0.16–0.19 |
| TDs ≥ 4 | ~0.08–0.10 |

**Common lines:** 0.5 (dominant), 1.5 (for elite QBs). Books move juice, not line.

**Gate:** Focus on 1.5 line (primary market). At 0.5 line, require win_prob ≥0.70.

**Market key:** `player_pass_tds`

### RUSH_TDS

- RB1 mean: ~0.50–0.65 TDs/game. P(TD=0): ~57–65%
- Red zone usage (carries inside 5-yard line) is stronger predictor than raw carry volume
- **EXCLUDE from model:** CV >1.5, binary-adjacent, extreme game-script dependency, no red-zone touch forecasting
- Market key if implemented: `player_rush_tds`

### REC_TDS

- WR1 mean: ~0.35–0.50 TDs/game. P(TD=0): ~62–70%
- **EXCLUDE from model:** Same reasoning as RUSH_TDS — impossible to model reliably without red-zone target data
- Market key if implemented: `player_reception_tds`

### INT

- Mean ~0.85 INTs/game (average starter). P(INT=0): ~43–48%
- P(INT=0) at 0.5 line: Over (+115) appears to offer structural value for typical starters (market overestimates the under)
- **STAT_CAP:** 2 per run. **KILLSHOT ineligible.**
- **SaberSim may not provide INT projection** — use fallback: proj_int = 0.85 flat, scaled by opponent INT rate if available
- Market key: `player_pass_interceptions`

---

## G4: Game Lines — SPREAD, TOTAL, TEAM_TOTAL, ML

### SPREAD

**GAME_SIGMA["NFL"]["spread"] = 13.5**

- 1978–2012 overall NFL average: σ = 13.45
- 2019–2024 non-TNF games: σ = 13.7
- TNF: σ = 14.6 (noisier — do not use as base)
- Normal distribution is well-validated for NFL point differentials

**NFL spread dogs:** NOT lottery-like ATS. Dogs cover 52–56% historically (vs 50% breakeven). Do NOT gate spread dog bets the same as ML dog bets.

**BLEND_ALPHA for NFL spreads: 0.10** (vs 0.25 in NBA/MLB). SaberSim NFL partially pulls from Vegas, creating circular dependency.

**Market key:** `spreads` | Alternate spreads: `alternate_spreads` (requires per-event endpoint)

### TOTAL

**GAME_SIGMA["NFL"]["total"] = 13.5**

- Derived mathematically: √(9.3² + 9.3²) ≈ 13.2 ≈ 13.5
- 2022 average total set: ~44.2; actual: ~44.0
- 2024 overs hit 53.7% (books lagged upward trend)

**Market key:** `totals` | Alternate: `alternate_totals`

### TEAM_TOTAL

**GAME_SIGMA["NFL"]["team"] = 9.5**

- Individual team score σ ≈ 9.3 (consistent with total σ derivation)
- Typical range: 20.5 to 27.5 points
- **BLEND_ALPHA = 0.10** (same as spread)
- Fallback if team total unavailable: `team_total_home = (total + spread) / 2`

**Market key:** `team_totals`

### ML (Moneyline)

**GAME_SIGMA["NFL"]["ml"] = 13.5** — same as spread

**Win probability formula:**
```python
win_prob = normal_cdf(0, blended_margin, sigma=13.5)
```

**Example conversions:**
- Spread −3 → win_prob ≈ 0.586
- Spread −7 → win_prob ≈ 0.698
- Spread −14 → win_prob ≈ 0.851

**Ceiling check:** For any ML pick where model win_prob > (no-vig implied prob + 0.05), cap at (no-vig implied + 0.05). Normal model overestimates extreme favorites by ~4pp.

**NFL does NOT have a fixed-spread runline equivalent.** Treat as NBA ML.

**Market key:** `h2h`

### Implementation Notes

1. `NFL_BLEND_ALPHA = 0.10` — implement as separate constant from 0.25 NBA/MLB
2. σ = 13.5 across all NFL game line types
3. `alternate_spreads` and `alternate_totals` require per-event endpoint `/events/{event_id}/odds`
4. ML ceiling check for extreme favorites
5. Team totals fallback formula: `(game_total ± spread) / 2`

---

## G5: NB_R Values, Platt Policy, Correlation Groups

### NB_R Summary

| Stat | Distribution | NB_R | Notes |
|------|-------------|------|-------|
| PASS_TDS | NB | 3.0 | NB beats Poisson; dispersion ratio ~1.2 |
| RUSH_TDS | NB | 1.2 | Near-Bernoulli; dispersion ratio ~2.0–3.0 |
| REC_TDS | NB | 1.1 | Near-Bernoulli; even rarer than RUSH_TDS |
| RECEPTIONS | NB | 8.0 | Less overdispersed; NB still preferred |
| INT | NB | 1.5 | Strongly overdispersed |
| PASS_YARDS | Normal | n/a | Mild skew; Normal acceptable |
| RUSH_YARDS | Normal* | n/a | *Gamma better theoretically; Normal OK for mid-lines |
| REC_YARDS | Normal* | n/a | Apply min_proj gate (skip if proj <25 yards) |

### Platt Calibration Policy

**Identity calibration (A=1.0, B=0.0) for ALL NFL stats at launch.**

- Do NOT share NBA Platt params (A=1.4988, B=−0.8102) — those were fit on NBA EWMA/Bayesian projections, not SaberSim NFL
- Count stats (PASS_TDS, RUSH_TDS, REC_TDS, INT, RECEPTIONS): use identity calibration permanently — NB CDF is already well-calibrated
- PLATT_STATS for NFL = {PASS_YARDS, RUSH_YARDS, REC_YARDS} only
- Minimum N = 200–300 NFL prop picks to refit. At 10 picks/week, that's ~20+ weeks (≈1.2 seasons)
- Interim: monitor calibration plot informally; set min_edge NFL = 0.035 (slightly higher than NBA) to compensate for lack of Platt sharpening

### NFL Correlation Groups

```python
NFL_CORR_GROUPS = {
    "QB_VOLUME": {"PASS_YARDS", "PASS_TDS"},      # r ≈ 0.50; dedup per QB
    "RECEIVER_VOLUME": {"REC_YARDS", "RECEPTIONS"}, # r ≈ 0.80; dedup per player
    "RB_VOLUME": {"RUSH_YARDS", "RUSH_TDS"},       # r ≈ 0.42; dedup per player
}

SAME_TEAM_PICK_CAP = 2  # QB pass yards + WR rec yards r ≈ 0.54
```

**Independent stats (can stack freely):**
- INT — independent of passing volume (r ≈ 0.05 with PASS_YARDS/PASS_TDS)
- REC_TDS — weakly correlated with REC_YARDS (r ≈ 0.25–0.35; below grouping threshold)

**Pearson r reference:**

| Stat Pair | Pearson r | Decision |
|-----------|-----------|----------|
| PASS_YARDS + PASS_TDS (same QB) | ~0.50 | Group A — dedup |
| REC_YARDS + RECEPTIONS (same WR) | ~0.80 | Group B — dedup |
| RUSH_YARDS + RUSH_TDS (same RB) | ~0.42 | Group C — dedup |
| QB PASS_YARDS + WR REC_YARDS (team) | ~0.54 | Same-team stack cap |
| INT vs any volume stat (same QB) | ~0.05 | Independent |

---

## G6: Blowout Sigmoid, Home/Away Delta, Opponent Quality

### Blowout / Garbage Time Sigmoid

**NFL sigmoid is DIRECTIONAL, not a uniform dampener.**

| Position/Stat | Role | Blowout Direction |
|---|---|---|
| Trailing QB | Forced to pass | INFLATE passing yards, rec yards |
| Trailing WR/TE | More targets | INFLATE receiving yards, receptions |
| Trailing RB | Team abandons run | DEFLATE rushing yards |
| Leading RB | Clock management | INFLATE rushing yards |
| Leading QB | Game managing | DEFLATE passing yards |

**Quantified multipliers (flat threshold approach, simpler than sigmoid):**

If projected spread ≥ 14 points:
- Trailing QB PASS_YARDS: ×1.12 (best estimate: +17% at 14+ points)
- Trailing WR REC_YARDS: ×1.08 (+12%)
- Trailing RB RUSH_YARDS: ×0.75 (−25%)
- Leading RB RUSH_YARDS: ×1.10 (+12%)
- Leading QB PASS_YARDS: ×0.92 (−10%)

At 10–13 points: linear interpolation from 1.0 to full multiplier. Below 10 points: no adjustment.

**Sigmoid parameters (if implementing smooth version):**
- Trailing players: k = 0.12, midpoint = 14.0 pts
- Leading players: k = 0.10, midpoint = 14.0 pts

**Comparison to NBA:**

| Parameter | NBA | NFL (recommended) |
|---|---|---|
| Direction | Uniform dampener | Bidirectional (stat + team role) |
| k | 0.15 | 0.10–0.12 |
| midpoint | 20.0 pts | 14.0 pts |
| max_reduction | 0.19 | 0.10–0.25 (varies by stat) |

### Home/Away Delta

**Skip home/away delta for NFL — SaberSim encodes it.**

SaberSim NFL uses per-game play-by-play simulation that explicitly encodes home/away within its simulations. Applying an additional delta would double-count.

Verify after first ~50 games by comparing SaberSim home-team projections to actuals split by home/away.

**If applying independently of SaberSim (fallback):**

| Stat | Home Delta (% of proj) |
|---|---|
| PASS_YARDS | +2.0 to +3.0% |
| RUSH_YARDS | +1.5 to +2.5% |
| REC_YARDS | +1.5 to +2.5% |
| RECEPTIONS | +1.0 to +2.0% |

### Opponent Defensive Quality

**Skip separate opponent quality multiplier — SaberSim encodes it.**

SaberSim NFL "accounts for match-ups" and is built per-play against the actual defense. Applying DVOA multiplier on top would double-count.

**Decision tree:**
1. Use SaberSim projection as-is
2. After N=50 games: compare SaberSim residuals by opponent DVOA quartile
3. Only apply residual multiplier if SaberSim systematically over/under-projects by matchup

**Fallback DVOA multipliers (if SaberSim fails):**
- QB PASS_YARDS vs bottom-5 pass defense: +10–15%
- QB PASS_YARDS vs top-5 pass defense: −8–12%
- RB RUSH_YARDS vs bottom-5 run defense: +8–12%

**TDs are MORE opponent-dependent than yards** but less predictable. Use DVOA only for yards; keep TDs unadjusted.

**Priority order for adjustments:**
1. Blowout sigmoid (apply first — overrides normal game flow)
2. Opponent quality multiplier (apply to base projection before blowout sigmoid)
3. Home/away delta (skip — SaberSim encodes it)

---

## G7: Role Tiers, Kickers/DST, STAT_CAP, KILLSHOT, SHADOW

### Role Tier Definitions

**Primary proxy for tier (no custom projections):** DK salary → target share → snap share → projected points

**Tier thresholds:**

| Player Tier | DK Salary / Usage Gate | Max Pick Tier |
|-------------|----------------------|--------------|
| RB1 Workhorse | salary ≥$6,500 OR carry share ≥60% | T1 |
| RB2 Committee | salary $4,500–$6,499 OR carry share 30–59% | T2 |
| RB3 | salary <$4,500 | Skip entirely |
| WR1 | salary ≥$6,500 OR target share ≥22% | T1 |
| WR2 | salary $5,000–$6,499 OR target share 14–21% | T2 |
| WR3/Slot | salary $4,000–$4,999 OR target share <14% | T3 |
| TE1 | salary ≥$4,500 OR projected targets ≥4.0/game | T2 |
| TE2 | salary <$4,500 OR proj targets ≤2.0/game | Skip entirely |
| QB (starter) | salary ≥$6,000 | T1 |
| QB (backup) | salary <$6,000 | Skip entirely |

**Hard skip:** DK salary <$4,000 → refuse to post regardless of edge.

### Kickers and D/ST

**Kickers: Skip entirely.** Gate: if `position == "K"` in SaberSim CSV, skip. Odds API does not expose a reliable kicker market key.

**D/ST player props: Skip Phase 1.** Add team sacks as Phase 2 market once Odds API market key confirmed and NB_R calibrated. Team sacks: NB_R ≈ 3.0, mean ~2.5–3.0/game.

### STAT_CAP (max picks per stat per run)

| Stat | Cap |
|------|-----|
| PASS_YARDS | 4 |
| RUSH_YARDS | 5 |
| REC_YARDS | 8 |
| RECEPTIONS | 6 |
| PASS_TDS | 3 |
| RUSH_TDS | 3 (if included) |
| REC_TDS | 3 (if included) |
| INT | 2 |
| SPREAD | 6 |
| TOTAL | 4 |
| TEAM_TOTAL | 4 |

**Additional caps:** Max 20 total picks per Sunday run. Max 4 picks per single-game slate (TNF/SNF/MNF). Max 2u aggregate per game (not picks — prevents single game blowup).

### SPORT_UNIT_CAP for NFL

**Recommendation: 4u max per single NFL pick** (from G7 research). Note: G10 recommends 5u and G5/T5 recommends 5u — the conservative 4u is the G7 recommendation; G10 confirms "up to 5u after shadow validation."

### KILLSHOT Eligibility for NFL

**Eligible:** PASS_YARDS, RUSH_YARDS, REC_YARDS, SPREAD
**Eligible after 1 season:** RECEPTIONS (if calibration holds)
**Ineligible:** All TD stats, INT, TOTAL (outdoor stadium weather risk)

**win_prob threshold: 0.70** (raised from NBA's 0.65)

**Reasoning:** Weekly format, no NFL-specific Platt scaling at launch, higher per-game variance.

**Weekly cap: 1 KILLSHOT per week** (vs NBA's 2/week)

**Odds range:** Keep [-200, +110] same as NBA.

**KILLSHOT stats must NOT include any NFL stats at launch** (G10 finding). Gate all NFL out of KILLSHOT for first season. Add NFL to KILLSHOT sport blocklist until Win Rate ≥53% confirmed on 50+ live NFL picks.

### Shadow Mode

**Mandatory shadow mode for NFL before going live.**

- **Minimum shadow weeks: 6** (target: 9 weeks / half-season)
- **Hard gate: Do NOT go live before Week 6 regardless of results**
- **Minimum picks for go-live: 200 NFL prop picks (shadow log)**
- **CLV exit gate:** 100 CLV rows AND positive mean CLV (+0.5%+ or better)
- **Fast-track:** If Weeks 1–4 show CLV +1.5%+ AND WR ≥55%, reduce to 75 CLV rows with manual review

**CLV accumulation rate:** ~8–14 rows/week for NFL (1 slate per week)

---

## G8: OT Effects, Playoffs, TNF/MNF/SNF, Zero-Inflation

### Overtime Effects

**Settlement policy (all major books):** ALL props and game lines include overtime.
- DraftKings, FanDuel, BetMGM: OT counts for all markets unless explicitly labelled "60 minutes only"
- Player must take the field for ≥1 offensive snap; 0 snaps = prop voided and refunded

**OT frequency (2022–2024):** ~5.9–7.4% of regular season games. Long-run average: ~5–6%.

**Action:** Do NOT add an OT probability adjustment to projections. Effect is noise-level at ~5–7% OT frequency.

### Playoff vs Regular Season

**Recommended playoff scalars (use after 1–2 playoff seasons of data):**

| Stat | Recommended Scalar | Confidence |
|------|--------------------|------------|
| PASS_YARDS | 0.95 | Low-Medium |
| RUSH_YARDS | 0.97 | Low |
| REC_YARDS (WR1) | 0.95 | Low-Medium |
| REC_YARDS (WR2/TE) | 0.93 | Low |
| RECEPTIONS | 0.95 | Low |
| PASS_TDS | 0.93 | Low |
| RUSH_TDS | 1.00 | No adjustment |

**Launch without playoff scalars initially.** SaberSim partly encodes opponent quality per-game. Apply scalars only after detecting systematic bias (>5% directional error rate) in 50–100 playoff prop picks.

### TNF / MNF / SNF

**TNF short-week effect:** PASS_YARDS −3% to −5%, RUSH_YARDS directionally neutral, offensive TDs −0.68/game. However, TNF totals since 2018 hit over/under at essentially same rate as Sunday. **No blanket short_week_flag penalty recommended.**

**Optional:** Apply −3 pick_score on TNF PASS_YARDS and RECEPTIONS picks specifically.

**Week 17–18:** Apply `starter_rest_flag` gate per-player when starter status is in doubt. Not a slate-level adjustment.

**TNF game day detection from Odds API:** Check `commence_time.weekday() == 3` (Thursday UTC).

### Zero-Inflation / Hurdle Models

**Zero-inflation rates:**

| Position Tier | P(0 rec yards) | P(0 rush attempts) |
|---------------|---------------|-------------------|
| WR1 (≥25% target share) | ~8–12% | N/A |
| WR2 (12–24% target share) | ~18–25% | N/A |
| WR3/Slot | ~30–40% | N/A |
| TE1 | ~12–18% | N/A |
| RB1 (≥60% snap share) | N/A | ~3–5% |
| RB2 (30–59% snap share) | N/A | ~10–18% |

**Min_proj gates (implement immediately — proxy for zero-inflation):**

| Stat | Skip if proj < X |
|------|-----------------|
| REC_YARDS | 20.0 yards |
| RUSH_YARDS | 12.0 yards |
| RECEPTIONS | 2.5 |
| PASS_YARDS | 175.0 yards |

**Hurdle class:** Defer until 200+ WR prop outcomes collected. Gate H1: 200 WR prop outcomes to estimate p_zero empirically.

**SaberSim note:** SaberSim proj for WR2 at 38 yards is already a blended average including zero scenarios — Normal will slightly over-estimate over-probability. Acceptable residual risk until hurdle class implemented.

---

## G9: Context Keywords, Injury Policy, Grading, SaberSim CSV

### Context Sanity Keywords

**Official NFL injury designations:**
- **Q** — Questionable: ~72–75% play rate historically
- **D** — Doubtful: ~25–30% play rate; treat as soft-out
- **O** — Out: will not play
- **IR** — Injured Reserve: out minimum 3–4 weeks
- **FP** — Full Participant: strong signal player will be active (~85% play rate)

**Inactive list timing:** 90 minutes before kickoff. Sunday 1pm games → inactives due ~11:30 AM ET.

**Keywords — Player IS OUT:**
- "listed as inactive", "ruled out", "placed on IR", "will not play", "scratched", "out Sunday/this week"
- "doubtful" → treat as soft-out (~75–80% DNP rate)

**Keywords — Player IS ACTIVE:**
- "active", "off injury report", "full participant", "no designation", "cleared", "good to go", "practicing in full"

**Weather flagging:**
- Wind >20 mph → flag for passing props
- "postponed", "rescheduled", "relocated", "weather delay" → flag for active bets
- Dome stadiums (ATL, NO, DAL, IND, LV, MIN, DET, ARI, HOU): not weather-sensitive

### Injury Status Policy

**Use binary in/out (same as NBA), not probabilistic.**

- All major books void props when player has 0 participation
- Official inactive list fires 90 min before kickoff
- Q players who do play often have reduced snap share (~60–80% of healthy baseline) — prop graded on result, not discounted
- Probabilistic discounting is structurally -EV (same logic as NBA feedback_play_prob_binary.md)

**P(plays | Q) by position:**

| Position | P(plays \| Q) |
|----------|--------------|
| QB | ~70–75% |
| RB | ~72–78% |
| WR | ~75–80% |
| TE | ~72–76% |

### Auto-Grading

**ESPN NFL sport key:** `football/nfl`

**Grading endpoints:**
```
# Final scores:
GET https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates=YYYYMMDD

# Game summary + player stats (~15–30 min post-game):
GET https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary?event={EVENT_ID}

# Player game log:
GET https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/athletes/{ATHLETE_ID}/statisticslog
```

**Overnight full accuracy:** `nfl-data-py` package (`pip install nfl-data-py`). Available ~6–8 AM ET next morning.

**Name canonicalization:** Strip all periods from initials ("D.K. Metcalf" → "DK Metcalf"). Strip Jr./Sr./II suffixes. Verify existing `name_key()` function handles NFL initials.

### SaberSim NFL CSV Format

**Key columns in SaberSim NFL export:**

| Column | Notes |
|--------|-------|
| `Name` | Player name (matches DK roster upload) |
| `Team` | 3-letter DraftKings-style abbreviation |
| `Opp` | Opponent abbreviation |
| `Pos` | QB, RB, WR, TE, K, DST |
| `Saber Total` | Total fantasy point projection |
| `Saber Team` | Team total fantasy points |
| `Status` | "Confirmed" for confirmed starters |

**NFL-specific stat columns to add to parse_csv():** Pass Yds, Pass TD, INT, Rush Yds, Rush TD (QB); Rush Yds, Rush TD, Rec, Rec Yds (RB); Rec, Rec Yds, Rec TD, Targets (WR/TE)

**SaberSim does NOT expose snap share or target share in the CSV.** These must be sourced separately if needed.

**Publication timing:** Saturday 8–11 PM ET (final version). Sunday morning refresh for injury updates.

**CSV format:** Separate slates per DK structure (Main Slate, SNF, TNF, MNF).

**Sport detection (must add to parse_csv):**
```python
elif "nfl" in fname.lower(): sport = "NFL"
```

**NFL team abbreviation aliases:**

| Team | SaberSim/DK | Odds API |
|------|-------------|----------|
| LA Rams | LAR | LA Rams |
| LA Chargers | LAC | LA Chargers |
| New England | NE | New England Patriots |
| NY Giants | NYG | NY Giants |
| NY Jets | NYJ | NY Jets |
| Kansas City | KC | Kansas City Chiefs |
| Tampa Bay | TB | Tampa Bay Buccaneers |
| Green Bay | GB | Green Bay Packers |

---

## G10: Odds API Market Keys, Book Coverage, Cross-Cutting

### Confirmed Market Key Strings

All player prop markets require the per-event endpoint, NOT the bulk endpoint.

| Stat | Market Key | Notes |
|------|-----------|-------|
| Passing yards | `player_pass_yds` | |
| Rushing yards | `player_rush_yds` | |
| Receiving yards | `player_reception_yds` | **NOT** `player_receiving_yds` |
| Receptions | `player_receptions` | |
| Passing TDs | `player_pass_tds` | |
| Rushing TDs | `player_rush_tds` | |
| Receiving TDs | `player_reception_tds` | |
| Interceptions | `player_pass_interceptions` | **NOT** `player_interceptions` |
| Anytime TD scorer | `player_anytime_tds` | Separate from rush/rec TDs |
| Full game spread | `spreads` | Bulk endpoint OK |
| Full game total | `totals` | Bulk endpoint OK |
| Moneyline | `h2h` | Bulk endpoint OK |
| Team totals | `team_totals` | |
| Alternate spread | `alternate_spreads` | Per-event endpoint required |
| Alternate totals | `alternate_totals` | Per-event endpoint required |
| Passing completions | `player_pass_completions` | |
| Passing attempts | `player_pass_attempts` | |

**CRITICAL:** Receiving yards key is `player_reception_yds` — common source of bugs.

**Endpoints:**
```
# Featured markets only (bulk):
GET /v4/sports/americanfootball_nfl/odds?regions=us&markets=spreads,totals,h2h

# All player props (per event):
GET /v4/sports/americanfootball_nfl/events/{eventId}/odds?markets=player_pass_yds,player_rush_yds,...
```

**Region:** Use both `us` and `us2`. Deduplicate by bookmaker key.

### CO-Legal Book Coverage

**Full prop coverage (primary tier):**
DraftKings, FanDuel, BetMGM, Caesars, BetRivers, Bet365

**Partial / inconsistent coverage (secondary):**
Fanatics, theScore Bet, Hard Rock, BetParx, BallyBet, PointsBet, WynnBet, SuperBook, Tipico, BetWay, Circa

**Weakest:** TwinSpires — primarily horse racing; verify NFL prop availability with live API call before including.

### Typical Vig

| Market | Typical Vig |
|--------|------------|
| Game spread | -110/-110 |
| Player passing yards | -115/-115 |
| Player rushing yards | -115/-115 to -120/+100 |
| Player TDs | -120/+100 to -130/+110 |

### Cross-Cutting Implementation Checklist

- [ ] Add `player_reception_yds` (not `player_receiving_yds`) as receiving yards market key
- [ ] Add `player_pass_interceptions` (not `player_interceptions`) as INT market key
- [ ] Use `/events/{eventId}/odds` endpoint for all NFL player props
- [ ] Add event ID resolution step to NFL pipeline
- [ ] Set `alternate_spreads` and `alternate_totals` in SPORT_ALT_MARKET for NFL
- [ ] Add `americanfootball_nfl_preseason` to DISABLED_SPORTS hard block
- [ ] Set `MIN_EDGE_NFL = 0.045` (4.5% minimum edge for NFL props) — or 6% for game lines
- [ ] Implement Week 1 damping: reduce pick_score 10–15% or cap at T2 for Week 1 (variance 3.5× higher than Week 16)
- [ ] Implement same-team pick cap: max 2 picks per team per game
- [ ] Implement same-game pick cap: max 3 picks per game total
- [ ] Set NFL Sunday slate total pick cap: max 10–20 NFL props per run
- [ ] Set KILLSHOT win_prob threshold to 0.70 for NFL (vs 0.65 NBA)
- [ ] Exclude ALL NFL stats from KILLSHOT eligibility for first season
- [ ] Verify TwinSpires NFL prop availability with live API call
- [ ] Add `elif "nfl" in fname.lower(): sport = "NFL"` to parse_csv()
- [ ] Build NFL_TEAM_ALIAS dict for SaberSim ↔ Odds API normalization
- [ ] Set BLEND_ALPHA = 0.10 for NFL game lines (vs 0.25 NBA/MLB)

### NFL CLV Notes

**Prop CLV is less meaningful for NFL than game line CLV.** Few market-making books on NFL props; lower liquidity. Track all CLV but flag prop CLV separately.

**CLV window for NFL:** Thursday publication → Sunday kickoff ≈ 2.5–3 days. Evaluate on per-game-week basis, not daily.

**CLV daemon:** No structural change needed. 10am daily start + 18h MAX_UPTIME covers all Sunday games. MNF games ending by midnight are within the window (10am + 18h = 4am next day).

### Preseason

**Disable model entirely for preseason.** Add `americanfootball_nfl_preseason` to DISABLED_SPORTS hard block. NFL preseason has starters playing <1 quarter; SaberSim projections unreliable; Odds API prop coverage very limited.

---

*End of NFL_FINDINGS.md — Research date: 2026-05-21*
