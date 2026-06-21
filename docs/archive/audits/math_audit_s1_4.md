# Math Audit — Sections 1–4
**Date:** 2026-05-22
**Auditor:** Claude Sonnet 4.6 (automated)
**Scope:** engine/run_picks.py (primary), engine/sgp_builder.py (secondary)
**Lines reviewed:** ~6,700 combined

---

## Section 1 — Implied Probability & Edge

### Finding 1.1: CORRECT — American odds → implied probability
**File:** engine/run_picks.py:647–654
**Code:**
```python
def implied_prob(odds):
    if odds == 0:
        return 0.0
    if odds < 0:
        return abs(odds) / (abs(odds) + 100.0)
    else:
        return 100.0 / (odds + 100.0)
```
**Verdict:** Correct formula. Negative odds: |odds| / (|odds| + 100) e.g. -110 → 110/210 = 0.5238. Positive odds: 100 / (odds + 100) e.g. +150 → 100/250 = 0.40. Zero guard returns 0.0 (safe — zero-odds legs are filtered before edge calc). Used consistently across all call sites in run_picks.py (lines 823–824, 2505–2506, 2608–2609, 2903, 2985, 3165–3166). Also duplicated correctly in sgp_builder.py:207–210.

---

### Finding 1.2: CORRECT — No-vig removal
**File:** engine/run_picks.py:656–661
**Code:**
```python
def no_vig(imp1, imp2):
    total = imp1 + imp2
    if total == 0:
        return 0.5, 0.5
    return imp1 / total, imp2 / total
```
**Verdict:** Correct additive normalization for two-way markets. `total` is the combined overround; dividing removes vig proportionally. The zero-guard (returns 0.5, 0.5) is a safe fallback that can only trigger when both odds are 0, which is pre-filtered by `odds == 0` checks. All market types use two-way no-vig: props (via `calc_edge`), spreads (lines 2505–2507), ML (2608–2610), team totals (2679), NRFI (3165–3167), F5 (2903, 2985). There are no 3-way markets in the engine — all bet types are binary (over/under, cover/not-cover, win/lose).

---

### Finding 1.3: CORRECT — Edge always uses no-vig, never raw implied
**File:** engine/run_picks.py:821–829
**Code:**
```python
def calc_edge(model_prob, over_odds, under_odds):
    imp_over = implied_prob(over_odds)
    imp_under = implied_prob(under_odds)
    nv_over, nv_under = no_vig(imp_over, imp_under)
    over_edge = model_prob - nv_over
    under_edge = (1.0 - model_prob) - nv_under
    return over_edge, under_edge, nv_over, nv_under
```
**Verdict:** Correct. Edge is defined as model_prob minus no-vig market probability, never raw implied probability. Props use `calc_edge` (line 2253). Spreads, ML, team totals, F5 lines all compute `no_vig(imp_this, imp_opp)` and then `edge = cover_prob/win_prob - nv_this` — consistent pattern. sgp_builder.py does the same at lines 612–618.

---

### Finding 1.4: CORRECT — NRFI edge uses no-vig (M2 fix)
**File:** engine/run_picks.py:3161–3186
**Code:**
```python
imp_nrfi = implied_prob(nrfi_under["odds"])
imp_yrfi = implied_prob(nrfi_over["odds"])
nv_nrfi, nv_yrfi = no_vig(imp_nrfi, imp_yrfi)
...
raw_edge = win_prob - nv_prob
```
**Verdict:** Correct. The M2 fix is in place — no-vig is computed from both sides and used for edge. The fallback at line 3184 (`nv_prob = implied_prob(odds)`) applies only when one side of odds is missing, in which case no-vig cannot be computed and raw implied is used. This fallback is an acceptable degradation — picks without both sides would fail the `nrfi_under and nrfi_over` check at line 3164 and `nv_nrfi/nv_yrfi` would be None, triggering the fallback.

---

### Finding 1.5: ISSUE — `_implied_prob` undefined in `post_daily_lay`
**File:** engine/run_picks.py:4499
**Code:**
```python
book_implied_combined *= _implied_prob(_leg_odds)
```
**Verdict:** `_implied_prob` is defined in `sgp_builder.py:207` but is never imported into `run_picks.py`. There is no `from sgp_builder import _implied_prob` anywhere in the file. This is a `NameError` that crashes `post_daily_lay()` every time a daily lay is posted with real_odds on the legs (the M26 logging addition). Although `book_implied_combined` is used only for the diagnostic print at line 4515 (not for any gating logic), the crash occurs at line 4499 — before the MIN_DAILY_LAY_PROB gate, before the Discord guard check, before sizing. Every daily lay post is silently broken.

**Fix:** Replace `_implied_prob` with the existing `implied_prob` function defined at line 647 of the same file. Both implementations are identical.

---

### Finding 1.6: CORRECT — ML win_prob for fixed-spread sports blends against no-vig
**File:** engine/run_picks.py:2613–2617
**Code:**
```python
if sport in _FIXED_SPREAD_SPORTS:
    raw_team_wp = 1.0 - normal_cdf(0, raw_margin if is_home else -raw_margin, sigma)
    win_prob = nv_this + BLEND_ALPHA * (raw_team_wp - nv_this)
```
**Verdict:** Correct handling for MLB and NHL where the runline/puck-line (always ±1.5) is a derivative of ML, not an independent margin signal. The ML no-vig is used as the market anchor with 25% weight on the model projection. This prevents the variable-spread blending path from using the ±1.5 fixed line as if it reflects a true scoring margin.

---

## Section 2 — Over Probability Per Stat Per Sport

### Finding 2.1: CORRECT — NBA/WNBA PTS, REB, AST (Normal distribution)
**File:** engine/run_picks.py:735–750
**Code:**
```python
s = (SIGMA_WNBA.get(stat) if sport == "WNBA" else None) or SIGMA.get(stat)
sigma = max(proj * s["mult"], s["min"])
under_p = normal_cdf(line, proj, sigma)
over_p = 1.0 - normal_cdf(line, proj, sigma)
```
**Verdict:** Correct. Normal CDF with `sigma = max(proj * mult, min_sigma)` — the floor prevents zero-sigma collapse when projection is near zero. `under_p = P(X <= line)`, `over_p = P(X > line)`. CDF direction is correct. No push correction needed for continuous Normal — correct. SIGMA values: PTS mult=0.35 min=4.5; REB mult=0.58 min=2.5; AST mult=0.45 min=1.3. SIGMA_WNBA overrides: PTS mult=0.38 min=3.5, AST mult=0.55 min=1.1, REB mult=0.45 min=2.0. These look reasonable.

---

### Finding 2.2: CORRECT — NBA/WNBA AST, REB, SOG, HITS (Poisson with push-adjustment)
**File:** engine/run_picks.py:700–715
**Code:**
```python
if stat in POISSON_STATS and line <= POISSON_CUTOFF:
    k = math.floor(line)
    if line == k:  # Integer line — push-adjusted
        push = poisson_pmf(k, proj)
        strict_over = 1.0 - poisson_cdf(k, proj)
        strict_under = poisson_cdf(k - 1, proj)
        non_push = 1.0 - push
        if non_push > 0:
            over_p = strict_over / non_push
            under_p = strict_under / non_push
    else:  # Half-integer line — no push possible
        under_p = poisson_cdf(k, proj)
        over_p = 1.0 - poisson_cdf(k, proj)
```
**Verdict:** Correct. Push mass (P(X=k) at integer lines) is properly removed and the remaining probability is renormalized. `strict_over = P(X > k)`, `strict_under = P(X < k)`, these sum to `1 - push`. After normalization: `over_p + under_p = 1`. For half-integer lines, push mass is zero, so `over_p = P(X > k) = P(X >= k+1)` and `under_p = P(X <= k)` are complementary and correct. POISSON_STATS = {AST, REB, SOG, REC, HITS}; POISSON_CUTOFF = 8.5 (correct — beyond ~8.5 the Poisson becomes near-Normal anyway).

---

### Finding 2.3: CORRECT — NBA 3PM, MLB HRR, MLB K (Negative Binomial)
**File:** engine/run_picks.py:716–734
**Code:**
```python
elif stat in NB_STATS and not (sport == "WNBA" and stat == "3PM"):
    r = NB_R[stat]
    k = math.floor(line)
    if line == k:  # Integer — push-adjusted
        push = negbinom_pmf(k, proj, r)
        strict_over = 1.0 - negbinom_cdf(k, proj, r)
        strict_under = negbinom_cdf(k - 1, proj, r)
        ...
    else:
        under_p = negbinom_cdf(k, proj, r)
        over_p = 1.0 - negbinom_cdf(k, proj, r)
```
**Verdict:** Correct. NB_STATS = {3PM, HRR, K}. Push correction is identical in structure to the Poisson path and is mathematically correct. The WNBA 3PM exception correctly routes to Normal (SIGMA_WNBA["3PM"]) since WNBA 3PM is underdispersed (var/mean ~0.70). The NB PMF implementation at line 614–635 uses log-space arithmetic — correct for large k. NB parameterization: p = r/(r+mu), var = mu + mu²/r. NB_R: 3PM=12.3, HRR=1.5, K=5.0 — empirically calibrated per documentation.

---

### Finding 2.4: CORRECT — MLB TB (Poisson convolution)
**File:** engine/run_picks.py:752–786
**Code:**
```python
threshold = int(math.floor(line)) + 1  # P(TB >= threshold) for half-integer lines
...
over_p = sum(dist[threshold:])
```
**Verdict:** Correct for the primary case (half-integer lines like 1.5, 2.5). `threshold = floor(1.5)+1 = 2`, so `over_p = P(TB >= 2) = P(TB > 1.5)`. For the rare integer line case (e.g. 2.0): `threshold = 3`, giving `P(TB >= 3) = P(TB > 2)` which correctly excludes the push at exactly 2. The Poisson convolution correctly models each hit type as an independent Poisson process with base 1B-weight, 2B-weight=2, 3B-weight=3, HR-weight=4. max_tb=16 (ceiling: 4 HR = 16 TB, reasonable). Fallback: when SaberSim does not provide TB_1B breakdown (TB_1B is None), the code falls through to `calc_prop_prob()` with SIGMA["TB"] = {mult:1.20, min:1.5}, using a Normal approximation. This is a known accuracy trade-off for SaberSim CSV inputs.

---

### Finding 2.5: CORRECT — MLB HITS (Poisson), HA (Normal)
**File:** engine/run_picks.py:277, 284
**Code:**
```python
POISSON_STATS = {"AST", "REB", "SOG", "REC", "HITS"}
SIGMA = {
    "HA": {"mult": 0.50, "min": 2.5},  # Normal
    "HITS": {"mult": 0.90, "min": 0.7},  # Not used (Poisson takes priority)
}
```
**Verdict:** Correct. HITS routes to Poisson at lines <= 8.5 (typical line: 0.5 or 1.5). At line 0.5: k=0, half-integer, `over_p = 1 - P(X=0) = 1 - exp(-proj)` (probability of getting at least 1 hit). Correct. HA routes to Normal (not in POISSON_STATS). SIGMA["HITS"] exists but is unreachable for typical lines (only used if line > 8.5, which does not occur in practice for batter hits). This is fine — the dead code causes no harm.

---

### Finding 2.6: CORRECT — MLB K (Negative Binomial, overs only, line >= 6.0)
**File:** engine/run_picks.py:297–302, 976–979
**Code:**
```python
NB_STATS = {"3PM", "HRR", "K"}
NB_R = {"K": 5.0, ...}
...
if stat == "K" and direction == "under":
    return False, "G_K_NO_UNDERS"
if stat == "K" and direction == "over" and line < 6.0:
    return False, "G_K_MIN_LINE"
```
**Verdict:** Correct. K uses NB(r=5.0) which models overdispersion in pitcher K totals. Gates block K unders (SaberSim IP bias makes unders structurally -EV) and K overs at low lines (< 6.0). The NB path handles integer line push-adjustment correctly (same as Finding 2.3).

---

### Finding 2.7: CORRECT — MLB OUTS (Normal)
**File:** engine/run_picks.py:275
**Code:**
```python
"OUTS": {"mult": 0.30, "min": 3.0},
```
**Verdict:** Correct. OUTS is not in POISSON_STATS or NB_STATS, so it routes to the Normal path. sigma = max(proj * 0.30, 3.0). For a typical 15-out start (5 IP), sigma = max(4.5, 3.0) = 4.5. Unders only (G_OUTS_UNDER gate blocks overs). CDF direction correct.

---

### Finding 2.8: CORRECT — MLB NRFI/YRFI (custom probability model)
**File:** engine/run_picks.py:3015–3219
**Code:**
```python
p_away_scores = min(0.45, max(0.05, BASE_SCORING_RATE * home_pitch_factor * off_away))
p_home_scores = min(0.45, max(0.05, BASE_SCORING_RATE * away_pitch_factor * off_home))
p_nrfi = (1.0 - p_away_scores) * (1.0 - p_home_scores)
p_yrfi = 1.0 - p_nrfi
```
**Verdict:** Correct. P(NRFI) = P(away_scores=0) * P(home_scores=0), assuming independence of each team's first-inning scoring. `p_yrfi = 1 - p_nrfi` = complement. BASE_SCORING_RATE = 0.1633, consistent with ~70% NRFI baseline (P(NRFI) ≈ (1-0.1633)² ≈ 0.70). Bounds clipped to [0.05, 0.45] to prevent degenerate probabilities. Offense and pitcher quality factors applied correctly.

---

### Finding 2.9: CORRECT — NHL SOG (Poisson)
**File:** engine/run_picks.py:284
**Code:**
```python
POISSON_STATS = {"AST", "REB", "SOG", "REC", "HITS"}
```
**Verdict:** SOG is in POISSON_STATS, so it uses the push-adjusted Poisson path for integer lines. Typical SOG lines are 2.5, 3.5, 4.5 (half-integer) — no push correction needed in practice. For half-integer lines the formula gives `under_p = poisson_cdf(k, proj)` and `over_p = 1 - poisson_cdf(k, proj)`. Correct.

---

### Finding 2.10: CORRECT — WNBA PTS, AST, REB (Normal with WNBA-specific sigma)
**File:** engine/run_picks.py:326–331
**Code:**
```python
SIGMA_WNBA = {
    "PTS": {"mult": 0.38, "min": 3.5},
    "AST": {"mult": 0.55, "min": 1.1},
    "REB": {"mult": 0.45, "min": 2.0},
    "3PM": {"mult": 0.48, "min": 0.70},
}
```
**Verdict:** Correct. WNBA-specific sigmas are used when `sport == "WNBA"`, overriding the NBA values. The selection logic at line 743 `(SIGMA_WNBA.get(stat) if sport == "WNBA" else None) or SIGMA.get(stat)` correctly prioritizes WNBA sigma, falling back to general SIGMA if not present. WNBA 3PM correctly routes to Normal (not NB) via the exception at line 716. WNBA combo stats use COMBO_RHO_WNBA (all pairs lower ~0.20 vs NBA).

---

### Finding 2.11: CORRECT — Combo stats (PRA, PR, PA, RA) — correlated Normal
**File:** engine/run_picks.py:789–818
**Code:**
```python
mu_combo = sum(mus)
var = sum(s * s for s in sigmas)
for i in range(len(components)):
    for j in range(i + 1, len(components)):
        rho = rho_table.get(pair, ...)
        var += 2.0 * rho * sigmas[i] * sigmas[j]
sigma_combo = max(var ** 0.5, 2.0)
over_p = 1.0 - normal_cdf(line, mu_combo, sigma_combo)
```
**Verdict:** Correct. Var(X+Y) = Var(X) + Var(Y) + 2·ρ·σ(X)·σ(Y). The double-sum correctly covers all pairs (PTS-REB, PTS-AST, REB-AST for PRA). The floor of 2.0 on sigma prevents division by zero or extreme probabilities for low-projection players. No push correction needed (continuous Normal). The `1 - over_p` returned as under_p is complementary. COMBO_RHO values are calibrated from 75,367 player-games.

---

## Section 3 — Platt Scaling

### Finding 3.1: CORRECT — Platt formula implementation
**File:** engine/run_picks.py:671–680
**Code:**
```python
def _platt_calibrate_prop(over_p: float) -> float:
    raw = PLATT_A * over_p + PLATT_B
    raw = max(-30.0, min(30.0, raw))
    return 1.0 / (1.0 + math.exp(-raw))
```
**Verdict:** Correct. This is `sigmoid(PLATT_A * over_p + PLATT_B)`, which matches the spec in CLAUDE.md: `1 / (1 + exp(-(PLATT_A * over_p + PLATT_B)))`. The clamp to [-30, 30] prevents float overflow in `math.exp`. Input is `over_p` (raw model over-probability, pre-calibration). Under_p is derived as `1 - over_p` post-Platt, preserving complementarity.

---

### Finding 3.2: CORRECT — Platt applied to NBA and NHL props
**File:** engine/run_picks.py:2248–2250
**Code:**
```python
if _sport != "MLB":
    over_p = _platt_calibrate_prop(over_p)
    under_p = 1.0 - over_p
```
**Verdict:** Correct. The Platt model was fitted on NBA+NHL prop data (76 settled picks). NBA and NHL props get calibration applied. MLB is explicitly excluded as documented — the Platt coefficients are not calibrated on MLB stat distributions.

---

### Finding 3.3: UNCERTAIN — Platt applied to WNBA props
**File:** engine/run_picks.py:2248
**Code:**
```python
if _sport != "MLB":   # applies to NBA, NHL, AND WNBA
    over_p = _platt_calibrate_prop(over_p)
```
**Verdict:** UNCERTAIN. WNBA is not MLB, so Platt is applied. The Platt model was fitted on NBA+NHL data only (no WNBA props in the training set per the comment at line 357–364). WNBA stats have different distributions (higher PTS CV ~0.36 vs NBA ~0.25). Applying NBA+NHL calibration to WNBA is a reasonable approximation (better than no calibration), but it is undocumented as a deliberate decision vs an oversight. Suggest either: (a) add a comment confirming intentional application, or (b) gate on `_sport in ("NBA", "NHL")` once WNBA sample is sufficient to refit.

---

### Finding 3.4: CORRECT — Platt input is raw `over_p`, not directional win_prob
**File:** engine/run_picks.py:2240–2250
**Code:**
```python
over_p_raw = over_p   # saved before Platt
if _sport != "MLB":
    over_p = _platt_calibrate_prop(over_p)
    under_p = 1.0 - over_p
```
**Verdict:** Correct. Platt is applied to the raw model over_p (before direction selection). The `over_p_raw` is saved for the calibrate_platt.py refitting pipeline. After Platt, `under_p = 1 - over_p` ensures the calibrated probabilities sum to exactly 1. The pick's `win_prob` is then set to `over_p` or `under_p` depending on direction (lines 2257–2268) — so the calibrated value flows correctly into edge calculation.

---

### Finding 3.5: CORRECT — Platt not applied to combo stats (TB, PRA etc.)
**File:** engine/run_picks.py:2230–2238
**Code:**
```python
if stat == "TB" and _pp.get("TB_1B") is not None:
    over_p, under_p = calc_tb_prob(...)
elif stat in COMBO_STATS:
    over_p, under_p = calc_combo_prob(...)
else:
    over_p, under_p = calc_prop_prob(...)
# Platt applied after all three paths:
if _sport != "MLB":
    over_p = _platt_calibrate_prop(over_p)
```
**Verdict:** Correct. Platt is applied to all non-MLB props regardless of distribution path — TB (Poisson convolution), combo (correlated Normal), and standard (Poisson/NB/Normal) all pass through Platt. Since TB is an MLB stat (`_sport == "MLB"`), Platt is skipped for it. NBA/WNBA combo stats do get Platt applied, which is acceptable given they use the same Normal model family as regular NBA props.

---

## Section 4 — Pick Score Formula

### Finding 4.1: CORRECT — pick_score formula
**File:** engine/run_picks.py:831–858
**Code:**
```python
def pick_score(win_prob, edge, mode="Default", tier=None, ...):
    sw, ew = PICK_SCORE_MODES.get(mode, (0.40, 0.60))
    wp_n = (win_prob * 100 - 50) / 25 * 100
    e_n  = (edge * 100) / 15 * 100
    score = sw * wp_n + ew * e_n
    score *= PICK_SCORE_TIER_MULT.get(tier, 1.00)
    score += COLD_START_SCORE_PENALTY.get(cold_start_subtype, 0)
    if injury_trigger:
        score += INJURY_TRIGGER_BONUS.get(stat, ...)
    return score
```
**Verdict:** Correct. `wp_n` normalizes win_prob to a 0-centered scale: 50% WP → 0, 75% WP → 100. `e_n` normalizes edge to a 0-based scale: 0% edge → 0, 15% edge → 100 (ceiling). Default weighting 40% WP / 60% edge is edge-dominant as documented. At Platt ceiling (~66.6% WP) + 15% edge: `score = 0.40*66.4 + 0.60*100 = 86.6`, consistent with documented max ~95. Tier multipliers correctly depress T1 (0.90×) and T1B (0.93×) relative to T2 (1.00×) reference. Cold-start penalties (-15 to -5) and injury trigger bonuses (+5 to +10) are additive adjustments applied after the tier multiply.

---

### Finding 4.2: CORRECT — pick_score called with adj_edge for props, raw edge for game lines
**File:** engine/run_picks.py:2338 (props), 2435 (game totals), 2537 (spreads), 2652 (ML), 2723 (team totals)
**Verdict:** Props use `adj_edge = raw_edge * conf` where `conf` penalizes low-GP players (0.70 for GP<10, 0.85 for GP<20, 1.0 otherwise). Game lines set `adj_edge = edge` with `conf = 1.0` (no game-line confidence modifier). pick_score receives the correct adjusted edge in all cases. NRFI at line 3216 also correctly uses `adj_edge` (which equals `raw_edge` since no conf modifier applies to NRFI).

---

### Finding 4.3: CORRECT — Tier multipliers applied before additive adjustments
**File:** engine/run_picks.py:853–857
**Code:**
```python
score = sw * wp_n + ew * e_n
score *= PICK_SCORE_TIER_MULT.get(tier, 1.00)    # multiply first
score += COLD_START_SCORE_PENALTY.get(...)         # add second
if injury_trigger:
    score += INJURY_TRIGGER_BONUS.get(...)          # add third
```
**Verdict:** The order is intentional: tier multiplier scales the core score, then additive signals overlay. Cold-start penalty is never amplified by a tier multiplier — a T2 taxi player gets the same -15 as a T1 taxi player. This is defensible design (cold-start reliability is tier-independent). The injury trigger bonus is similarly additive-only.

---

### Finding 4.4: CORRECT — No sport-specific pick_score adjustments
**File:** engine/run_picks.py (all pick_score call sites)
**Verdict:** pick_score() has no sport parameter and applies no sport-specific weight adjustments. All sports (NBA, NHL, MLB, WNBA) use the same formula with the same tier multipliers. This is consistent design — the sport-specific variation is captured upstream in tier assignment, sigma choice, and edge gates rather than in the scoring function itself.

---

### Finding 4.5: ISSUE (minor) — WNBA early-season edge dampener not propagated to pick_score
**File:** engine/run_picks.py:965–970 (gate), 2338 (pick_score call)
**Code:**
```python
# In check_prop_gates():
effective_edge = edge * mult   # dampened for gate check
if effective_edge < WNBA_EDGE_FLOOR:
    return False, "G_WNBA_EDGE"
# ...pick passes gate with full adj_edge...

# In evaluate_props():
pick["pick_score"] = pick_score(win_prob, adj_edge, ...)  # uses full adj_edge, not dampened
```
**Verdict:** During the WNBA early-season window (days 4–21), the gate check uses a dampened `effective_edge` (e.g., 80% of real edge on days 4–14) to raise the effective bar for noisy early games. However, if a pick passes, it is scored and sized using the full `adj_edge`. This means early-season WNBA picks that barely pass the dampened gate are scored as if they had full-confidence edges, potentially leading to higher pick_scores and larger sizes than the dampening intent warranted. The fix would be to pass `effective_edge` or a dampened version to pick_score() during the early-season window. Currently this is a low-impact issue since WNBA is in SHADOW_SPORTS (not posted publicly).

---

### Finding 4.6: CORRECT — Tier fallback in pick_score
**File:** engine/run_picks.py:854
**Code:**
```python
score *= PICK_SCORE_TIER_MULT.get(tier, 1.00)
```
**Verdict:** The fallback multiplier of 1.00 applies for any tier not in PICK_SCORE_TIER_MULT (e.g. KILLSHOT, DAILY_LAY, SGP, LONGSHOT, MANUAL). KILLSHOT picks explicitly have `"KILLSHOT": 1.00` in the dict — effectively no penalty or boost. DAILY_LAY, SGP, LONGSHOT tiers are not in the dict and get the 1.00 default. This is correct — these pick types have their own sizing logic and the pick_score is less relevant for parlay/parlay-adjacent types.

---

## Summary Table

| Finding | Severity | Status |
|---------|----------|--------|
| 1.1 American odds → implied prob | — | CORRECT |
| 1.2 No-vig removal | — | CORRECT |
| 1.3 Edge = win_prob − no-vig | — | CORRECT |
| 1.4 NRFI no-vig edge (M2 fix) | — | CORRECT |
| **1.5 `_implied_prob` undefined in `post_daily_lay`** | **ISSUE (runtime bug)** | **Crashes every daily lay post** |
| 1.6 ML fixed-spread blending | — | CORRECT |
| 2.1 NBA/WNBA PTS/REB/AST Normal | — | CORRECT |
| 2.2 AST/REB/SOG/HITS Poisson + push | — | CORRECT |
| 2.3 3PM/HRR/K Negative Binomial | — | CORRECT |
| 2.4 TB Poisson convolution | — | CORRECT |
| 2.5 MLB HITS (Poisson), HA (Normal) | — | CORRECT |
| 2.6 MLB K NB, gates | — | CORRECT |
| 2.7 MLB OUTS Normal | — | CORRECT |
| 2.8 NRFI/YRFI custom model | — | CORRECT |
| 2.9 NHL SOG Poisson | — | CORRECT |
| 2.10 WNBA stats sigma | — | CORRECT |
| 2.11 Combo stats correlated Normal | — | CORRECT |
| 3.1 Platt formula sigmoid | — | CORRECT |
| 3.2 Platt applied to NBA+NHL | — | CORRECT |
| 3.3 Platt applied to WNBA | UNCERTAIN | Undocumented; low risk |
| 3.4 Platt input = raw over_p | — | CORRECT |
| 3.5 Platt after all distribution paths | — | CORRECT |
| 4.1 pick_score formula | — | CORRECT |
| 4.2 adj_edge vs raw edge routing | — | CORRECT |
| 4.3 Multiply then additive adjustments | — | CORRECT |
| 4.4 No sport-specific scoring | — | CORRECT |
| 4.5 WNBA early-season edge dampener | ISSUE (minor) | Shadow sport; low impact |
| 4.6 Tier fallback multiplier | — | CORRECT |

## Required Fix

**Finding 1.5** is the only runtime bug. Fix is one line:

```python
# engine/run_picks.py:4499
# Change:
book_implied_combined *= _implied_prob(_leg_odds)
# To:
book_implied_combined *= implied_prob(_leg_odds)
```

`implied_prob` is already defined at line 647 of the same file with identical logic.
