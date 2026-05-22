# Math Audit — Sections 5–8: Sizing, Daily Lay, SGP, Longshot
**Date:** 2026-05-22  
**Auditor:** Claude Sonnet 4.6  
**Files audited:** `engine/run_picks.py`, `engine/sgp_builder.py`

---

## Section 5 — VAKE Sizing

### Finding 5.1: CORRECT — VAKE_BASE edge tiers and base unit amounts
**File:** `engine/run_picks.py:405`  
**Code:**
```python
VAKE_BASE = [(0.03, 0.05, 0.50), (0.05, 0.07, 0.75), (0.07, 0.09, 1.00), (0.09, 9.99, 1.25)]
```
**Verdict:** Four monotonic tiers. Breakpoints at 3/5/7/9% edge. Amounts step 0.50/0.75/1.00/1.25u. Ranges are left-inclusive, right-exclusive. The `base_units()` function returns 1.25u as a fallback for edge >= 0.09 (caught by the 9.99 upper bound). The safety floor at line 865–866 returns 0.50u for edge < 0.03, which should never occur after gate G9 but protects against bugs. Correct.

---

### Finding 5.2: CORRECT — Variance and tier multipliers
**File:** `engine/run_picks.py:406–409`  
**Code:**
```python
VAKE_MULT = {
    "variance":    {"T1": 1.00, "T1B": 1.00, "T2": 0.85, "T3": 0.65, "T4": 0.40},
    "tier":        {"T1": 1.00, "T1B": 1.00, "T2": 0.90, "T3": 0.60, "T4": 0.35},
}
```
**Verdict:** T1 and T1B receive no penalty on either dimension. T2 moderate penalty (0.85 × 0.90 = 0.765 combined). T3 heavy penalty (0.65 × 0.60 = 0.39 combined). Default fallback (line 1426–1428) for unlisted tiers is `var_m=0.85, tier_m=0.90` — safe defaults. KILLSHOT tier is never routed through `size_picks_vake` (bypasses the premium card), so the missing KILLSHOT entry is not a bug.

---

### Finding 5.3: CORRECT — Correlation multiplier in size_picks_vake
**File:** `engine/run_picks.py:1431–1443`  
**Code:**
```python
game_seen[game] += 1
if game_seen[game] == 1:
    corr_m = 1.00
elif game_seen[game] == 2:
    corr_m = 0.85
else:
    corr_m = 0.70

if stat in PITCHER_STATS:
    pitcher_game_seen[game] += 1
    if pitcher_game_seen[game] >= 2:
        corr_m *= 0.70
```
**Verdict:** First pick from a game: no penalty. Second: 15% reduction. Third+: 30% reduction. R13 extra pitcher penalty stacks correctly (multiplies on top of the existing corr_m). The pitcher penalty only triggers for PITCHER_STATS (K, OUTS, HA) and only on the second+ pitcher prop from the same game. Correct.

---

### Finding 5.4: CORRECT — Exposure multiplier
**File:** `engine/run_picks.py:1446–1447`  
**Code:**
```python
stat_seen[stat] += 1
exp_m = 1.00 if stat_seen[stat] == 1 else 0.70
```
**Verdict:** First pick of each stat type: no penalty. Subsequent same-stat picks on the card: 30% reduction. Simple and correct.

---

### Finding 5.5: CORRECT — VAKE caps and floor
**File:** `engine/run_picks.py:1450–1451`  
**Code:**
```python
final = min(round_units(raw), 1.25)
final = max(final, 0.50)
```
**Verdict:** Max cap 1.25u applied before floor 0.50u. Order is correct — `min` can never produce a value above 1.25u which is higher than the floor, so the floor cannot accidentally override a legitimate cap. The 0.50u floor applies uniformly to all tiers in `size_picks_vake`. (Note: `size_picks_base` uses a 0.25u floor for T3 picks, but `size_picks_vake` is only called for the Premium 5, where a uniform 0.50u minimum is intentional.)

---

### Finding 5.6: ISSUE — SPORT_UNIT_CAP not re-enforced after KILLSHOT re-sizing
**File:** `engine/run_picks.py:1300, 6427–6452`  
**Code:**
```python
# In apply_caps (line 1300):
SPORT_UNIT_CAP = {"NBA": 8.0, "WNBA": 4.0, "NHL": 5.0, "NFL": 5.0, "MLB": 8.0}

# Later (line 6424–6431):
qualified = apply_caps(qualified, {}, max_per_game=args.max_per_game, units_already_bet=_units_today)
killshots = select_killshots(qualified, today_str, manual_players=manual_ks)
# KILLSHOT picks re-sized to 3–4u (line 5264)
# ...
# Only 12u daily cap re-checked (line 6447–6452); no SPORT_UNIT_CAP re-check
```
**Verdict:** `apply_caps()` enforces SPORT_UNIT_CAP using base-sized picks (0.5u–1.25u). KILLSHOT picks are then selected from the capped pool and re-sized to 3u/4u. The subsequent check (line 6447) only re-enforces the 12u daily cap — it does NOT re-check SPORT_UNIT_CAP.

Practical impact: A 3u KILLSHOT NBA pick + up to 5 premium NBA picks (each 1.25u = 6.25u) = 9.25u from NBA, exceeding the 8u SPORT_UNIT_CAP. In the worst case (4u KILLSHOT + 5 × 1.25u premium = 10.25u), the daily cap catches this at 12u but sport-level protection is absent.

Whether this is by design (KILLSHOT is a separate "tier above the cap") or an oversight is not documented. Recommend: either explicitly exempt KILLSHOT from SPORT_UNIT_CAP (with a comment) or add a SPORT_UNIT_CAP re-check after KILLSHOT sizing.

---

### Finding 5.7: CORRECT — Sport unit caps defined and enforced
**File:** `engine/run_picks.py:1300, 1314`  
**Code:**
```python
SPORT_UNIT_CAP = {"NBA": 8.0, "WNBA": 4.0, "NHL": 5.0, "NFL": 5.0, "MLB": 8.0}
...
if sport_units[sport] + size > SPORT_UNIT_CAP.get(sport, 8.0):
    continue
```
**Verdict:** NBA=8u, WNBA=4u, NHL=5u, NFL=5u, MLB=8u. The default fallback for unlisted sports is 8.0u (conservative). The check is `>` not `>=`, so exactly hitting the cap is allowed (picks that equal the cap pass). This is correct and consistent with how the 12u total cap is checked (line 1316: `total_units + size > 12.0`).

---

### Finding 5.8: CORRECT — round_units function
**File:** `engine/run_picks.py:872–874`  
**Code:**
```python
def round_units(u):
    """Round to nearest 0.25u."""
    return round(u * 4) / 4
```
**Verdict:** Multiplies by 4, rounds to integer, divides by 4 — produces 0.25u granularity. Uses Python's `round()` which rounds half to even (banker's rounding). At exact midpoints (e.g., u=0.875), this rounds to nearest even (0.75 or 1.00). For VAKE purposes this is fine.

---

## Section 6 — Daily Lay Sizing & Math

### Finding 6.1: CORRECT — Kelly formula in size_daily_lay
**File:** `engine/run_picks.py:4458, 4471–4479`  
**Code:**
```python
# Formula: f* = (p*b - q) / b  where b = decimal_odds - 1
b = dec - 1.0
q = 1.0 - combined_prob
kelly_full = (combined_prob * b - q) / b
raw_units = kelly_full * 0.25 * 100.0
```
**Verdict:** Standard Kelly formula `f* = (p·b - q) / b`. `b` is net decimal odds (profit per unit). `p = combined_prob`, `q = 1 - p`. Quarter Kelly = `f* × 0.25`. Conversion to units: fraction × 100 (assumes 1u = 1% of bankroll). The American-to-decimal conversion at lines 4467–4470 is standard and correct. Negative Kelly correctly returns 0.25u floor.

---

### Finding 6.2: CORRECT — Fractional Kelly factor
**File:** `engine/run_picks.py:4479`  
**Code:**
```python
raw_units = kelly_full * 0.25 * 100.0
```
**Verdict:** Quarter Kelly (0.25 fraction). This is standard conservative Kelly for parlays with high variance. At `combined_prob=0.60, parlay_odds=+100`: full Kelly ≈ 20% of bankroll → quarter Kelly ≈ 5% = 5u, capped at 0.75u. The cap heavily constrains output; the fraction choice (0.25 vs 0.50) rarely matters in practice given the 0.75u max.

---

### Finding 6.3: CORRECT — Daily lay size caps
**File:** `engine/run_picks.py:4481`  
**Code:**
```python
return max(min(final, 0.75), 0.25)
```
**Verdict:** `min(final, 0.75)` caps at 0.75u. `max(..., 0.25)` floors at 0.25u. Order is correct: cap before floor. Rounding at line 4480 is applied to `raw_units` before capping. The CLAUDE.md spec says "0.25–0.75u via `size_daily_lay()`" — code matches.

---

### Finding 6.4: CORRECT — Combined probability for multi-leg parlay
**File:** `engine/run_picks.py:3786–3788`  
**Code:**
```python
combined_prob = 1.0
for leg in legs:
    combined_prob *= leg["alt_cover_prob"]
```
**Verdict:** Product of independent leg cover probabilities — correct for uncorrelated legs. The legs are from different games (enforced by one-leg-per-game selection at line 3723–3724), so the independence assumption is reasonable. The daily lay is explicitly a "same book, multi-game parlay," not a same-game parlay, so leg independence is defensible.

---

### Finding 6.5: CORRECT — Per-leg gates applied correctly
**File:** `engine/run_picks.py:3681–3687`  
**Code:**
```python
if edge < MIN_LEG_EDGE_DAILY:
    continue
if cover_prob < MIN_LEG_COVER_PROB_DAILY:
    continue
```
**Verdict:** `MIN_LEG_EDGE_DAILY = 0.025` and `MIN_LEG_COVER_PROB_DAILY = 0.58` are applied before scoring. Both gates use strict `<` (not `<=`), so a leg at exactly 0.025 edge or 0.58 cover_prob passes. This is consistent with how prop gates use `<`.

---

### Finding 6.6: CORRECT — Max combined odds +100 enforced correctly
**File:** `engine/run_picks.py:3606–3607, 3751–3752`  
**Code:**
```python
MIN_COMBINED_ODDS_VAL = -130  # combined parlay must be -130 or longer
MAX_COMBINED_ODDS_VAL = 100   # combined parlay must not exceed +100
...
if parlay_odds > MAX_COMBINED_ODDS_VAL:
    continue
```
**Verdict:** The `parlay_odds > 100` check correctly rejects parlays longer than +100. The `parlay_odds < MIN_COMBINED_ODDS_VAL` check correctly rejects heavily juiced parlays (shorter than -130). Both checks use the computed combined parlay odds from actual book prices. Correct.

---

### Finding 6.7: CORRECT — MIN_DAILY_LAY_PROB gate applied correctly
**File:** `engine/run_picks.py:4500–4502`  
**Code:**
```python
if combined_prob < MIN_DAILY_LAY_PROB:
    print(f"  [Discord] Daily Lay combined prob {combined_prob*100:.1f}% < {MIN_DAILY_LAY_PROB*100:.0f}% threshold — skipping weak parlay.")
    return
```
**Verdict:** Gate is applied in `post_daily_lay()` using `combined_prob` from the parlay builder — the product of model cover probabilities, not book-implied probabilities. The `<` check is correct (rejects anything strictly below 0.47). Applied before sizing, so no resources are wasted on invalid parlays.

---

### Finding 6.8: ISSUE — MIN_DAILY_LAY_PROB = 0.47 inline comment is factually wrong
**File:** `engine/run_picks.py:183–185`  
**Code:**
```python
MIN_DAILY_LAY_PROB = 0.47       # Minimum combined cover probability before posting daily lay
                                 # Math: at 0.47 combined, a 2-3 leg parlay has positive Kelly
                                 # at realistic odds (-130 to +100). Old 0.33 allowed zero-EV posts.
```
**Verdict:** The inline comment claims "positive Kelly at realistic odds (-130 to +100)" at 0.47 combined probability. This is **false**. For Kelly to be positive, we need `p · b > q`, i.e., `0.47 · b > 0.53`, so `b > 1.128`, meaning decimal odds > 2.128, American odds > **+112.8**. No parlay in the -130 to +100 range satisfies this at 0.47 probability — they all produce negative Kelly.

`size_daily_lay()` correctly returns the 0.25u floor when Kelly is negative (line 4476–4477), and the docstring at line 4461–4463 explicitly acknowledges this. The comment at line 184 is misleading/wrong and should be corrected to something like: "0.47 is a rough probabilistic floor; Kelly is negative at this threshold for all parlay odds in the -130 to +100 range — the 0.25u floor in size_daily_lay() applies."

**Impact:** Documentation only — no runtime math error. The threshold itself is a policy choice.

---

### Finding 6.9: ISSUE — Daily lay edge uses raw vigged implied, not no-vig
**File:** `engine/run_picks.py:3677–3679`  
**Code:**
```python
implied = abs(odds) / (abs(odds) + 100.0) if odds < 0 else 100.0 / (odds + 100.0)
cover_prob = 1.0 - normal_cdf(-line, margin, sigma)
edge = cover_prob - implied
```
**Verdict:** `implied` is the raw book-implied probability, **including vig**. The prop pipeline at line 2253 uses `calc_edge()` which calls `no_vig()` to remove vig before computing edge. The daily lay does not have a paired opposite-side odds available per entry (alt spreads are stored one-side-per-team), so full no-vig requires matching the opposing team's alt spread entry.

Consequence: Alt spread edges are measured against the vigged implied probability. For typical alt spread odds of -125, raw implied ≈ 55.6%, no-vig implied ≈ 53.0%–54.0% (depending on the other side). The reported edge is therefore understated by ~1.5–2.5 pp relative to no-vig, which is conservative (harder to pass the edge gate). The sign of the error is safe — it does not inflate edges — but the inconsistency with the prop pipeline is worth noting.

**Impact:** Minor — makes daily lay edges slightly conservative. Not a risk-increasing error.

---

### Finding 6.10: CORRECT — cover_prob formula for alt spreads
**File:** `engine/run_picks.py:3678`  
**Code:**
```python
cover_prob = 1.0 - normal_cdf(-line, margin, sigma)
```
**Verdict:** `normal_cdf(x, mu, sigma) = Φ((x - mu)/σ)`. So this computes `1 - Φ((-line - margin)/σ) = P(X > -line)` where `X ~ N(margin, σ)`. For a team with spread `line` (e.g., line = -7.5 means team favored by 7.5), coverage requires `actual_margin > 7.5 = -(-7.5)`. The formula correctly computes `P(margin > -line)`. Consistent with the game-line spread formula at line 2495. Correct.

---

## Section 7 — SGP Math

### Finding 7.1: CORRECT — Gaussian copula MC algorithm
**File:** `engine/sgp_builder.py:358–402`  
**Code:**
```python
def _copula_joint_prob(probs, corr_mat, n_samples=4000, seed=42):
    L = _cholesky(corr_mat)
    for _ in range(n_samples):
        eps = [gauss(0.0, 1.0) for _ in range(n)]
        for i in range(n):
            xi = sum(L[i][k] * eps[k] for k in range(i + 1))
            ui = 0.5 * (1.0 + erf(xi * inv_sqrt2))
            if ui > probs[i]:
                ok = False; break
        if ok: hits += 1
    return hits / n_samples
```
**Verdict:** Correct Gaussian copula MC: (1) Cholesky factorize `R = LL^T`, (2) sample `ε ~ N(0,I)`, (3) `x = Lε` produces correlated standard normals, (4) `u_i = Φ(x_i)` transforms to correlated uniform marginals, (5) check `u_i ≤ p_i` for each leg (joint hit). Steps are mathematically correct. Fixed seed=42 ensures reproducibility. SE ≈ 0.7% at n=4000 for joint≈0.40. `probs[i]` are model probabilities from `_fair_prob()`, so the hit condition is correct.

---

### Finding 7.2: ISSUE — _copula_joint_approx docstring claims "Error < 3%" but error is ~17% at typical rho
**File:** `engine/sgp_builder.py:405–416`  
**Code:**
```python
def _copula_joint_approx(probs, avg_rho):
    """Fast equicorrelation Gaussian copula approximation for combo scoring.
    Linearly interpolates between independence (ρ=0) and perfect correlation
    (ρ=1, joint = min(p_i)).  Error < 3% for ρ ∈ [0, 0.40] — accurate enough
    to rank 91k combos; full MC is reserved for the final chosen SGP.
    """
    p_indep = 1.0
    for p in probs:
        p_indep *= p
    p_min = min(probs)
    return p_indep + avg_rho * (p_min - p_indep)
```
**Verdict:** The formula is a linear interpolation between independence (`p_indep`) and `p_min`. 

For 3 legs at `p=0.70` each with `avg_rho=0.30`:
- `p_indep = 0.70^3 = 0.343`
- `p_min = 0.70`
- `approx = 0.343 + 0.30 × (0.70 - 0.343) = 0.450`

The code comment at line 693 states: "Benchmark: 3-leg at 0.70 avg WP, avg_rho=0.30 → copula_joint ≈ 0.385". The approximation gives **0.450** vs MC value **0.385** — a **relative error of ≈17%** (absolute: 6.5 pp). The docstring claim "Error < 3%" is false for typical ρ values (0.20–0.35).

**Impact:** The approximation is only used for **ranking the 91k combo search**, not for the final sizing decision (which uses full MC). Since all combos are evaluated with the same biased formula, relative rankings may be approximately preserved — but overoptimistic copula scores may cause some suboptimal combos to bubble up through the 40-pick pool filter. The final SGP is then picked by full MC, which corrects this. The risk is that a slightly inferior combo is selected (not scored correctly in the final step) but in practice the impact is small given typical ρ ranges.

Recommend: correct the docstring to reflect the actual error magnitude (≈15–20% for ρ∈[0.20, 0.35]).

---

### Finding 7.3: CORRECT — pairwise_rho values and table structure
**File:** `engine/sgp_builder.py:288–330`  
**Code (summary of hierarchy):**
```python
# Same team offensive flow (PTS/AST/3PM overs):  ρ = 0.35
# Same player, same direction:                    ρ = 0.28
# Same team REB overs:                            ρ = 0.20
# Same team, same direction (other):              ρ = 0.15
# Cross-team overs (same game):                   ρ = 0.10
# Cross-team unders (same game):                  ρ = 0.08
# Same team mixed direction:                      ρ = −0.10
# Same player opposite direction (R1 kills first): ρ = −0.20
# Unrelated / different games:                    ρ = 0.00
```
**Verdict:** Hierarchy is internally consistent. The correlation structure correctly captures positive correlation for same-team offensive flow and negative correlation for opposing directions. The `_build_corr_matrix` correctly builds the n×n symmetric matrix with 1.0 on diagonals and pairwise ρ on off-diagonals. Values are conservative (max ρ = 0.35), reducing risk of overestimating joint probability.

---

### Finding 7.4: CORRECT — COMBO_RHO and COMBO_RHO_WNBA applied correctly
**File:** `engine/run_picks.py:317–339, 797`  
**Code:**
```python
COMBO_RHO = {
    ("PTS", "REB"): 0.333,
    ("PTS", "AST"): 0.233,
    ("REB", "AST"): 0.251,
}
COMBO_RHO_WNBA = {
    ("PTS", "REB"): 0.13,
    ("PTS", "AST"): 0.04,
    ("REB", "AST"): 0.05,
}
...
rho_table = COMBO_RHO_WNBA if sport == "WNBA" else COMBO_RHO
```
**Verdict:** COMBO_RHO is used for NBA combo props (PRA, PR, PA, RA), not for SGP legs. COMBO_RHO_WNBA has lower correlations (~0.20 lower). The sport selector at line 797 correctly routes to WNBA table for WNBA props. The fallback `rho_table.get((pair[1], pair[0]), 0.10 if sport == "WNBA" else 0.20)` handles reverse-key lookup correctly — if `("PTS","REB")` is not found, it tries `("REB","PTS")`, falling back to 0.10/0.20. Correct.

---

### Finding 7.5: CORRECT — SGP odds range gate (+200 to +450) enforced correctly
**File:** `engine/sgp_builder.py:50–51, 818`  
**Code:**
```python
MIN_PARLAY_ODDS = 200
MAX_PARLAY_ODDS = 450
...
if parlay_odds < MIN_PARLAY_ODDS or parlay_odds > MAX_PARLAY_ODDS:
    continue
```
**Verdict:** Gate applied using `_parlay_american(locked)` — the product of actual book decimal odds for the locked book. `< MIN` rejects odds shorter than +200 (too little payout for a 3-4 leg parlay risk). `> MAX` rejects odds longer than +450 (too long, pure lottery). Both checks are strict inequalities. The gate is applied inside the `n_legs` loop before scoring, so invalid parlays never appear in scoring. Also checked inside `_score_sgp` at line 685 for scoring purposes (odds_score = 0 outside range). Correct.

---

### Finding 7.6: CORRECT — SGP sizing conditions
**File:** `engine/sgp_builder.py:711–741`  
**Code:**
```python
avg_edge = sum(l["edge"] for l in legs) / len(legs)
if avg_edge < 0.035 or cohesion_score < 0.55:
    return SGP_SIZE_DEFAULT  # 0.25u
parlay_implied = _implied_prob(_parlay_american(legs))
if _copula_joint - parlay_implied >= 0.10:
    return SGP_SIZE_PREMIUM  # 0.50u
return SGP_SIZE_DEFAULT
```
**Verdict:** Three-gate premium check: (1) avg_edge ≥ 0.035, (2) cohesion ≥ 0.55, (3) copula_joint - parlay_implied ≥ 0.10 pp. All three must pass for 0.50u. Default is 0.25u. Logic correctly uses short-circuit: if (1) or (2) fail, return immediately without computing MC copula (saves ~2ms). The CLAUDE.md spec says "avg_wp≥0.70 AND cohesion≥0.55 AND avg_edge≥0.035" for premium — the `avg_wp` gate was replaced by the `copula_ev_margin ≥ 0.10` gate in the L8 update. CLAUDE.md is stale on this point but the code is internally documented.

---

### Finding 7.7: UNCERTAIN — SGP copula_joint vs vigged parlay_implied comparison in premium gate
**File:** `engine/sgp_builder.py:738–739`  
**Code:**
```python
parlay_implied = _implied_prob(_parlay_american(legs))
if _copula_joint - parlay_implied >= 0.10:
    return SGP_SIZE_PREMIUM
```
**Verdict:** `parlay_implied` is computed from actual book parlay odds (inclusive of vig). For a 3-leg parlay, the combined book vig can be 8–15 pp. Since `copula_joint` is a model probability (no vig), the 10 pp threshold has two components: (1) true model edge and (2) vig removal benefit.

Example: 3 legs at -115 each → book parlay ≈ +310. Vigged implied ≈ 24.4%. At 0.70 avg WP with rho=0.25, copula_joint ≈ 35%. copula - implied = 10.6% → PREMIUM triggered. But no-vig implied at +310 is ≈ 24.4% (same here as there's no opposite side). The vig is baked into the single leg prices.

This means the 10 pp threshold is not a pure model edge test. However, this is documented design intent (doc says "copula joint probability exceeds the parlay's implied probability by ≥ 10 pp"). As a calibrated threshold it may be appropriate, but it should be understood that roughly 3–8 pp of the 10 pp threshold is consumed by vig removal, not model alpha.

**Impact:** Gate may be more permissive than intended. Recommend noting explicitly in docstring that ~3–8 pp of the gap is expected vig removal.

---

### Finding 7.8: CORRECT — Combined win probability handling in SGP
**File:** `engine/sgp_builder.py:986` (win_prob left blank in log)  
**Verdict:** SGP log rows have blank `win_prob`. Individual leg probabilities (`fair_prob`) are stored in the `legs` JSON column. This is a valid design choice — the combined joint probability depends on correlation model, and the copula result is shown in the Discord embed ("Copula joint: X% | Implied: Y%"). Not a math error.

---

### Finding 7.9: CORRECT — _probit fallback implementation (BSM approximation)
**File:** `engine/sgp_builder.py:260–285`  
**Code:** BSM rational approximation used when `math.erfinv` is unavailable (Python < 3.12).
**Verdict:** The Beasley-Springer-Moro approximation is a well-known inverse normal CDF implementation. `_probit` is only called by `_copula_joint_prob` indirectly via `math.erfinv` — actually `_probit` is defined but not called anywhere in the current code (the MC algorithm uses `erf` not `erfinv`). Dead code — not a math error.

---

## Section 8 — Longshot Parlay Math

### Finding 8.1: CORRECT — Combined probability is product of individual win_probs
**File:** `engine/run_picks.py:3570–3574`  
**Code:**
```python
combined_prob = 1.0
for p in safest:
    combined_prob *= p["win_prob"]
```
**Verdict:** Correct independence-based product formula. Per-game cap (LONGSHOT_MAX_PER_GAME=2) reduces correlation by capping same-game legs, making the independence assumption more reasonable. The comment in the function docstring at line 3552–3554 explicitly acknowledges this: "assumes independence across legs." `win_prob` values are Platt-calibrated model probabilities (for NBA/NHL props). Correct.

---

### Finding 8.2: CORRECT — Per-game cap (LONGSHOT_MAX_PER_GAME=2) enforced correctly
**File:** `engine/run_picks.py:3561–3564`  
**Code:**
```python
g = p.get("game", "")
if game_counts.get(g, 0) >= LONGSHOT_MAX_PER_GAME:
    continue
game_counts[g] = game_counts.get(g, 0) + 1
```
**Verdict:** Uses `>=` check against LONGSHOT_MAX_PER_GAME=2. First pick from game: count 0 < 2, allowed, count → 1. Second pick: count 1 < 2, allowed, count → 2. Third pick: count 2 >= 2, rejected. Correct — allows at most 2 legs per game.

**Minor caveat:** If `p.get("game", "")` returns empty string `""` for multiple picks, all empty-game picks share one game bucket. This could incorrectly limit them to 2 combined. In normal operation (all picks have a game field), this is a non-issue.

---

### Finding 8.3: CORRECT — Fair odds from combined probability: formula and usage
**File:** `engine/run_picks.py:3540–3547, 3583–3587`  
**Code:**
```python
# prob_to_american (defined but unused):
def prob_to_american(prob):
    if prob >= 0.5: return -(prob / (1.0 - prob)) * 100
    else: return ((1.0 - prob) / prob) * 100

# Actual parlay_odds (used for display/logging):
if combined_dec >= 2.0:
    parlay_odds = int(round((combined_dec - 1.0) * 100.0))
else:
    parlay_odds = int(round(-100.0 / (combined_dec - 1.0)))
```
**Verdict:** The `prob_to_american` function is mathematically correct (standard American odds formula) but is **dead code** — never called in the codebase. The actual `parlay_odds` displayed and logged uses `combined_dec`, which is the product of actual book decimal odds (lines 3576–3579). This correctly shows what the bettor would actually receive, not the fair-value odds from the model. The fair/model combined probability is shown separately as `combined_prob`. The separation is correct and intentional.

---

### Finding 8.4: CORRECT — Parlay decimal odds computation
**File:** `engine/run_picks.py:3576–3579`  
**Code:**
```python
o = p.get("odds", -110)
if o > 0:
    combined_dec *= 1.0 + o / 100.0
else:
    combined_dec *= 1.0 + 100.0 / abs(o)
```
**Verdict:** Correct American-to-decimal conversion for each leg: positive odds → `1 + o/100`, negative odds → `1 + 100/|o|`. Product of decimal odds gives the combined parlay decimal. Fallback of -110 when odds missing is reasonable. The subsequent American conversion at lines 3584–3587 is correct standard formula.

---

### Finding 8.5: CORRECT — Longshot fixed size
**File:** `engine/run_picks.py:189, 4725, 4800`  
**Code:**
```python
LONGSHOT_SIZE = 0.25
```
**Verdict:** Flat 0.25u regardless of combined probability. This is appropriate — a 6-leg parlay with sub-5% combined probability carries extreme variance, and a fixed minimal stake makes sense. Size is applied consistently: defined at line 189, used in embed display (4725), and in log row (4800). No dynamic sizing attempted for longshot. Correct.

---

## Summary Table

| # | Section | Finding | Severity |
|---|---------|---------|---------|
| 5.1 | VAKE | VAKE_BASE tiers correct | CORRECT |
| 5.2 | VAKE | Variance/tier multipliers correct | CORRECT |
| 5.3 | VAKE | Correlation multiplier correct | CORRECT |
| 5.4 | VAKE | Exposure multiplier correct | CORRECT |
| 5.5 | VAKE | Caps and floor applied correctly | CORRECT |
| **5.6** | **VAKE** | **SPORT_UNIT_CAP not re-enforced after KILLSHOT re-sizing** | **ISSUE** |
| 5.7 | VAKE | Sport unit caps defined correctly | CORRECT |
| 5.8 | VAKE | round_units correct | CORRECT |
| 6.1 | Daily Lay | Kelly formula correct | CORRECT |
| 6.2 | Daily Lay | Quarter Kelly correct | CORRECT |
| 6.3 | Daily Lay | Size caps applied correctly | CORRECT |
| 6.4 | Daily Lay | Combined probability correct | CORRECT |
| 6.5 | Daily Lay | Per-leg gates applied correctly | CORRECT |
| 6.6 | Daily Lay | Max combined odds +100 correct | CORRECT |
| 6.7 | Daily Lay | MIN_DAILY_LAY_PROB gate correct | CORRECT |
| **6.8** | **Daily Lay** | **MIN_DAILY_LAY_PROB=0.47 inline comment factually wrong** | **ISSUE (doc)** |
| **6.9** | **Daily Lay** | **Edge uses raw vigged implied, not no-vig (unlike props)** | **ISSUE (minor)** |
| 6.10 | Daily Lay | cover_prob formula correct | CORRECT |
| 7.1 | SGP | Gaussian copula MC correct | CORRECT |
| **7.2** | **SGP** | **_copula_joint_approx "Error < 3%" claim is false (~17% at typical ρ)** | **ISSUE (doc)** |
| 7.3 | SGP | pairwise_rho values correct | CORRECT |
| 7.4 | SGP | COMBO_RHO/WNBA routing correct | CORRECT |
| 7.5 | SGP | Odds range gate +200/+450 correct | CORRECT |
| 7.6 | SGP | Sizing conditions correct | CORRECT |
| 7.7 | SGP | copula vs vigged implied comparison | UNCERTAIN |
| 7.8 | SGP | Win_prob handling correct | CORRECT |
| 7.9 | SGP | _probit dead code, not a math error | CORRECT |
| 8.1 | Longshot | Combined probability correct | CORRECT |
| 8.2 | Longshot | Per-game cap correct | CORRECT |
| 8.3 | Longshot | Fair odds formula correct, prob_to_american dead code | CORRECT |
| 8.4 | Longshot | Decimal odds computation correct | CORRECT |
| 8.5 | Longshot | Fixed 0.25u size correct | CORRECT |

## Issues Requiring Action

### ISSUE 5.6 — SPORT_UNIT_CAP bypass for KILLSHOT (Risk: moderate)
After `apply_caps()`, KILLSHOT picks are re-sized to 3–4u but the SPORT_UNIT_CAP (8u NBA) is not re-checked. Combined NBA exposure (KILLSHOT 3-4u + premium up to ~6.25u) can reach 9–10.25u, exceeding the 8u cap. Only the 12u daily total is re-enforced.
**Fix options:** (a) Add SPORT_UNIT_CAP check to the post-KILLSHOT cap block at line 6447–6452, or (b) explicitly document KILLSHOT as exempt from SPORT_UNIT_CAP with a comment.

### ISSUE 6.8 — Wrong inline comment for MIN_DAILY_LAY_PROB=0.47 (Risk: documentation)
Comment says Kelly is positive at 0.47 probability for odds in [-130, +100]. Math shows Kelly is negative throughout that range. The 0.25u floor in `size_daily_lay` handles this correctly, but the comment misleads about why 0.47 was chosen.
**Fix:** Update comment at line 184 to accurately describe the threshold rationale.

### ISSUE 6.9 — Daily lay edge uses raw vigged implied, not no-vig (Risk: low)
Props use `calc_edge()` with `no_vig()`. Daily lay uses `cover_prob - raw_implied`. Result: alt spread edges are understated by ~1.5–2.5 pp (conservative, not dangerous). If the opposite-side odds are available from the alt spread data, implementing no-vig would improve consistency.
**Fix:** Check if paired alt spread entries exist and implement two-sided no-vig when available.

### ISSUE 7.2 — _copula_joint_approx docstring error claim (Risk: documentation)
The approximation overestimates the true copula joint probability by ~17% at ρ=0.30, not the claimed "< 3%". Only affects combo scoring ranking during the 91k search, not final sizing (which uses full MC). Suboptimal combos may rank slightly higher than optimal.
**Fix:** Correct docstring to state actual error magnitude (~15–20% for ρ ∈ [0.20, 0.35]).
