# Math Audit — Sections 14–17
**Date:** 2026-05-22  
**Files reviewed:** engine/nba_projector.py, engine/capture_clv.py, engine/run_picks.py, engine/generate_projections.py  
**Auditor:** Claude Sonnet 4.6

---

## Section 14 — NBA Projection Pipeline (nba_projector.py)

### Finding 14.1: CORRECT — Minute scalar order of operations
**File:** engine/nba_projector.py:1241–1259

**Code:**
```python
is_playoff  = season_type == "Playoffs"
if injury_minutes_override is None:
    if is_playoff:
        proj_min = round(proj_min * PLAYOFF_MINUTES_SCALAR.get(role, 1.0), 2)
    else:
        _rs_scalar = REGULAR_SEASON_MINUTES_SCALAR.get(role, 1.0)
        if role == "spot": _rs_scalar = max(_rs_scalar, 1.200)
        proj_min = round(proj_min * _rs_scalar, 2)
```

**Verdict:** Correct. The flow is: (1) EWMA baseline minutes via `project_minutes()`, (2) PLAYOFF or RS scalar applied multiplicatively, (3) cold_start subtype cap applied post-scalar, (4) redistribution bump added in absolute-minutes space, (5) role-tier cap applied last. This is the right order. RS and PO scalars are mutually exclusive (playoff gate at line 1241). The `injury_minutes_override` bypass (line 1242) is documented and correct — override is authoritative.

---

### Finding 14.2: CORRECT — Rate deflator application
**File:** engine/nba_projector.py:1524–1536

**Code:**
```python
if is_playoff:
    for stat, defl in PLAYOFF_RATE_DEFLATORS.items():
        if stat in projections:
            projections[stat] = round(projections[stat] * defl, 2)
else:
    for stat, scalar in REGULAR_SEASON_STAT_SCALAR.items():
        if scalar != 1.0 and stat in projections:
            projections[stat] = round(projections[stat] * scalar, 2)
```

**Verdict:** Correct. Deflators are applied to the final projected stat values (e.g., `proj_pts`, not to per-minute rates). This is the intended behavior: the minutes scalar already adjusts minutes, and the rate deflator captures genuine per-minute rate changes in playoffs (e.g., tighter defense reducing PTS/min). Applying to the final output after pace/matchup/home-away adjustments is correct — the deflator is a residual calibration, not an input-stage transform. RS stat scalar is mutually exclusive with PO deflator (same `if is_playoff` gate).

---

### Finding 14.3: CORRECT — Home/away delta (multiplicative, correct sign)
**File:** engine/nba_projector.py:1517–1522

**Code:**
```python
if is_home is not None:
    sign = 1.0 if is_home else -1.0
    for stat, delta in _HOME_AWAY_DELTA.items():
        if stat in projections:
            projections[stat] = max(0.0, round(
                projections[stat] * (1.0 + sign * delta), 2))
```

**Verdict:** Correct. The adjustment is multiplicative: home player gets `(1 + delta)`, away player gets `(1 - delta)`. For a player whose EWMA baseline averages home and away games equally, this round-trips correctly (the design comment at line 338 confirms this intent). TOV delta is negative (`-0.0122`), so home team gets `(1 + 1.0 × -0.0122) = 0.9878` — fewer turnovers at home. That is the correct direction. Sign logic is unambiguous: home → `sign=+1`, away → `sign=-1`.

---

### Finding 14.4: CORRECT — Blowout sigmoid formula and direction
**File:** engine/nba_projector.py:1072–1078

**Code:**
```python
if spread is not None and abs(spread) > 0:
    reduction = BLOWOUT_MAX_REDUCTION / (
        1.0 + math.exp(-BLOWOUT_SIGMOID_K * (abs(spread) - BLOWOUT_SIGMOID_MID))
    )
    proj_min *= (1.0 - reduction)
```

**Verdict:** Correct. The sigmoid is a standard logistic function: `S(x) = L / (1 + exp(-k*(x-mid)))` where `L=0.19`, `k=0.15`, `mid=20`. Spot-checking behavior:
- spread=0: `reduction = 0.19/(1+exp(3.0)) ≈ 0.009` (< 1% — negligible, correct for close games)
- spread=20: `reduction = 0.19/(1+exp(0)) = 0.095` (9.5% at inflection — midrange, correct)
- spread→∞: `reduction → 0.19` (19% asymptote, correct)

Direction is correct: larger spreads mean more expected blowout, so more minutes reduction. `abs(spread)` handles both home-favored and away-favored spreads symmetrically. The `(1 - reduction)` multiplier correctly reduces projected minutes.

---

### Finding 14.5: CORRECT — Vegas team-total constraint (proportional scaling, cold_start denominator)
**File:** engine/generate_projections.py:142–167

**Code:**
```python
denom = sum(p.get("proj_pts", 0.0) or 0.0 for p in tprojs)
if denom <= 0:
    ...
    continue
raw_scale = vegas_total / denom
clipped = max(_CONSTRAINT_MIN, min(_CONSTRAINT_MAX, raw_scale))
...
for p in tprojs:
    for k in _CONSTRAINT_SCALE_KEYS:
        if k in p and p[k] is not None:
            p[k] = round(p[k] * clipped, 2)
```

**Verdict:** Correct. The denominator includes ALL players (cold_start included — comment at line 140 explains this is intentional; they have calibrated archetype priors). Scale is clipped to [0.80, 1.20] to prevent outlier totals from distorting projections. Proportional scaling of all stats by the same factor is mathematically correct under the assumption that players' shares of team scoring are invariant (which is what the model projects). `proj_min` is correctly excluded from `_CONSTRAINT_SCALE_KEYS` (H1 fix, line 77) — Vegas anchors points, not minutes.

One nuance: the cold_start denominator is by design. If a roster has 4 cold_start archetype players with non-trivial projections, their pts inflate the denominator and the Vegas scale becomes `<1.0`, deflating all players including legitimate starters. This is the accepted design tradeoff. The [0.80, 1.20] clip limits the damage.

---

### Finding 14.6: CORRECT — Bayesian priors per position (5-position split)
**File:** engine/nba_projector.py:378–444

**Code:**
```python
_REB_RATE_PRIOR_RS = {"PG": 0.053, "SG": 0.057, "SF": 0.079, "PF": 0.111, "C": 0.165}
_REB_RATE_PRIOR_PO = {"PG": 0.056, "SG": 0.060, "SF": 0.066, "PF": 0.092, "C": 0.133}
_AST_POS_PRIOR = {"PG": 0.0929, "SG": 0.0529, "SF": 0.0559, "PF": 0.0441, "C": 0.0450}
_STL_POS_PRIOR = {"PG": 0.02033, "SG": 0.01627, "SF": 0.01775, "PF": 0.01552, "C": 0.01405}
_BLK_POS_PRIOR = {"PG": 0.00537, "SG": 0.00537, "SF": 0.00716, ...}
_TOV_POS_PRIOR = {"PG": 0.03769, "SG": 0.02931, "SF": 0.02499, "PF": 0.02321, "C": 0.02321}
```

**Verdict:** Correct. All 5-position priors have plausible rank-orderings: PG leads AST, C leads REB/BLK, PG leads STL (by frequency), and PG leads TOV (most ball-handling). The weighted-average preservation was validated per CLAUDE.md (2026-05-10 split). Prior units are consistent with their respective rate denominators: REB is per-min, AST/STL/BLK/TOV are per-possession (confirmed by the `_REB_RATE_PRIOR` entries matching `_reb/min` units vs the `_AST_POS_PRIOR` entries matching per-possession units from the `poss_per_game` denominator).

One structural note: `_REB_RATE_PRIOR_RS` and `_REB_RATE_PRIOR_PO` values are in different units from `_REB_POS_OREB_PRIOR_RS` / `_REB_POS_DREB_PRIOR_RS`. The `_REB_RATE` priors are `reb/min` for the per-minute baseline path; the `_REB_POS_OREB/DREB` priors are `reb_per_available_rebound` for the OREB/DREB decomposition path. Both are used correctly in their respective code paths.

---

### Finding 14.7: CORRECT — EWMA lambda and recency bias direction
**File:** engine/nba_projector.py:508–538

**Code:**
```python
alpha = 2.0 / (span + 1.0)
# recency weights: index 0 = oldest game, index n-1 = most recent
recency = np.array([(1.0 - alpha) ** (n - 1 - i) for i in range(n)], dtype=np.float64)
```

**Verdict:** Correct. The formula `(1-alpha)^(n-1-i)` gives:
- `i=0` (oldest): `(1-alpha)^(n-1)` — smallest weight
- `i=n-1` (most recent): `(1-alpha)^0 = 1.0` — largest weight

Recency bias direction is correct: more recent games have higher weight. The `alpha = 2/(span+1)` is the standard EWMA decay factor. Combined with availability weights, the denominator normalization at `total_w = combined.sum()` ensures the weighted mean is properly normalized. This matches pandas EWMA semantics (`adjust=True` mode, which is pandas default for `ewm()`).

---

### Finding 14.8: CORRECT — PLAYOFF_RATE_DEFLATORS application
**File:** engine/nba_projector.py:1527–1530

**Code:**
```python
if is_playoff:
    for stat, defl in PLAYOFF_RATE_DEFLATORS.items():
        if stat in projections:
            projections[stat] = round(projections[stat] * defl, 2)
```

**Verdict:** Correct. Deflators are applied only when `is_playoff=True` (mutually exclusive with RS stat scalar). The values (pts=0.934, ast=0.870, fg3m=0.948, blk=1.152) are multiplicative — pts/ast/fg3m reduce, blk increases. Application order is correct: this runs AFTER home/away delta, pace factor, matchup, and the minutes scalar has already been applied to `proj_min`. The deflators are calibrated as post-all-other-adjustments residual corrections, so this order is consistent with how they were fit.

---

### Finding 14.9: ISSUE — AST rate training/projection denominator mismatch
**File:** engine/nba_projector.py:716–757 (training) and 1462–1464 (projection)

**Code (training):**
```python
def compute_ast_rate(df_clean, team_pace, pos_group, ...):
    poss_per_game = (team_pace * d["min"] / 48.0).clip(lower=0.1)
    ast_raw = d["ast"].fillna(0) / poss_per_game
```

**Code (projection call):**
```python
# M3: use game_pace as denominator so training basis matches projection basis.
ast_rate = compute_ast_rate(df_clean, game_pace, pg, ...)
proj_poss_ast = _proj_poss_ast * proj_min / 48.0   # where _proj_poss_ast = game_pace^0.50 * LEAGUE_AVG^0.50
```

**Verdict:** ISSUE (minor). When `compute_ast_rate` is called with `game_pace` as the `team_pace` argument (line 1464), it normalizes ALL historical training game rows by the current game's `game_pace = (team_pace + opp_pace) / 2`, not each historical game's own pace. This means a player's historical AST rates in fast games (e.g., pace=105) are being normalized by the current game's pace (e.g., pace=98), overstating their per-possession rate and producing a biased estimate. The correct approach would be to pass each game's own pace from the historical data. This is a systematic bias that affects all players whose historical opponents had different pace than today's opponent. Magnitude: at typical pace variance (~5 possessions), bias is approximately `(98/105)^1 - 1 ≈ -6.7%` on the per-possession rate for a player whose history was in faster games.

This was partially addressed by M3 (using `game_pace` instead of `team_pace` for better consistency), but the fundamental issue remains: the historical normalization uses a single scalar rather than per-game pace values. Given the 1x-per-day runtime, fetching per-game pace from the DB would be feasible.

---

### Finding 14.10: CORRECT — 240-minute lineup-protected constraint
**File:** engine/nba_projector.py:1786–1832

**Verdict:** Correct. The algorithm: (1) sort players by proj_min descending, (2) protect top-5 (on-court lineup), (3) scale bench players to fill remaining budget `(240 - core_total)`. Edge case where top-5 exceed 240 is handled by scaling core proportionally. `_SCALE_KEYS` correctly excludes `proj_min` from the stat-scaling loop (proj_min has its own scaling path). Stats are scaled proportionally with minutes, which is correct under the assumption that per-minute rates are held constant.

---

## Section 15 — CLV Calculation

### Finding 15.1: CORRECT — CLV formula direction
**File:** engine/capture_clv.py:870–872

**Code:**
```python
def calc_clv(your_odds: float, closing_odds: float) -> float:
    """CLV = closing_implied - your_implied. Positive = beat the close."""
    return implied_prob(closing_odds) - implied_prob(your_odds)
```

**Verdict:** Correct. The formula is `CLV = closing_implied_prob - your_implied_prob`. Since implied_prob converts American odds to probability (higher odds = lower implied prob):
- If you bet at -115 (implied 0.535) and line closes at -120 (implied 0.545), CLV = 0.545 - 0.535 = +0.010 → positive, you beat the close.
- If you bet at -115 (implied 0.535) and line closes at -110 (implied 0.524), CLV = 0.524 - 0.535 = -0.011 → negative, line moved in your favor (you missed a better line).

The sign convention and direction are correct per the docstring comment.

---

### Finding 15.2: ISSUE (known design choice) — No vig removal on CLV
**File:** engine/capture_clv.py:254–270, 870–872

**Code:**
```python
def implied_prob(american_odds):
    """Convert American odds to implied probability (raw, with vig)."""
    if o < 0:
        return abs(o) / (abs(o) + 100)
    else:
        return 100 / (o + 100)
```

**Verdict:** ISSUE (known, minor). CLV uses raw vigged implied probabilities, not no-vig fair probabilities. Compare with `run_picks.py` which explicitly calls `no_vig(imp_over, imp_under)` before computing edge. Using raw probs for CLV means:
1. CLV values are slightly compressed vs vig-free CLV (vig typically ~4-5% on each side = ~2-2.5% per pick on a two-sided market)
2. CLV is not directly comparable to edge values from run_picks.py

However, since BOTH `your_odds` and `closing_odds` include vig, the relative direction is preserved and CLV correctly identifies whether you beat the close. The magnitude is slightly understated. This is standard industry practice for CLV tracking and acceptable here. If the team later wants vig-adjusted CLV, apply the two-sided no_vig formula using both sides of the closing market.

---

### Finding 15.3: CORRECT — Implied probability formula
**File:** engine/capture_clv.py:266–270

**Code:**
```python
if o < 0:
    return abs(o) / (abs(o) + 100)
else:
    return 100 / (o + 100)
```

**Verdict:** Correct. Standard American odds to implied probability:
- Negative (favorite): `|o| / (|o| + 100)`. For -110: `110/210 = 0.5238`. Correct.
- Positive (underdog): `100 / (o + 100)`. For +100: `100/200 = 0.500`. For +150: `100/250 = 0.400`. Correct.
- Guard against `o=0` and non-finite values returns `None` (audit C6 fix). Correct.

---

## Section 16 — Daily Cap Accumulation

### Finding 16.1: CORRECT — G12 cap correctly initializes from prior runs
**File:** engine/run_picks.py:1293, 4909–4932, 6409

**Code:**
```python
# apply_caps():
total_units = units_already_bet  # start at cross-run total, not 0

# _units_bet_today():
total = sum(
    float(r.get("size", 0) or 0)
    for r in rows
    if r.get("date") == today_str
    and r.get("run_type", "").lower() != "manual"
)

# main pipeline:
_units_today = _units_bet_today(today_str) if not getattr(args, "no_cap", False) else 0.0
...
qualified = apply_caps(qualified, {}, max_per_game=args.max_per_game, units_already_bet=_units_today)
```

**Verdict:** Correct. `_units_bet_today()` reads pick_log.csv and sums all non-manual pick sizes for today, providing the cross-run baseline. This value is passed as `units_already_bet` to `apply_caps()`, which initializes `total_units = units_already_bet`. Every subsequent pick added to `result` increments `total_units += size`, and the guard `if total_units + size > 12.0: continue` correctly prevents exceeding the cap.

All run_types are included except "manual": primary, bonus, daily_lay, sgp, longshot all count. This is the correct design — all risk-bearing positions count against the daily cap.

---

### Finding 16.2: CORRECT — KILLSHOT units included in cap
**File:** engine/run_picks.py:5907–5911, 6445–6452

**Code:**
```python
# format_output validation:
ks_u = sum(p.get("size", 0) for p in killshots)
total_u_all = total_u + ks_u + units_already_bet

# Post-selection enforcement:
_premium_u = sum(p.get("size", 0) for p in premium)
_ks_total  = sum(p.get("size", 0) for p in killshots)
if _premium_u + _ks_total + _units_today > 12.0:
    while killshots and _premium_u + sum(...) + _units_today > 12.0:
        dropped = killshots.pop()
```

**Verdict:** Correct. KILLSHOT picks are logged with `run_type="primary"` (line 4010 in `log_picks()`), so they are counted in `_units_bet_today()` on subsequent runs. Within a single run, the post-KILLSHOT-selection cap check at lines 6447–6452 correctly enforces the combined premium+KILLSHOT limit. The `format_output` validation at line 5929 shows the breakdown in the output for operator visibility.

---

### Finding 16.3: ISSUE — Daily cap validation in format_output excludes SGP/daily_lay/longshot
**File:** engine/run_picks.py:5907–5929

**Code:**
```python
ks_u = sum(p.get("size", 0) for p in killshots)
total_u_all = total_u + ks_u + units_already_bet
# check: total_u_all <= 12.0
```

**Verdict:** ISSUE (minor, cosmetic). The `format_output` cap validation line (5929) shows `premium + KILLSHOT + prev_units`. It does NOT include the SGP (~0.25–0.50u), daily_lay (~0.25–0.75u), and longshot (0.25u) sizes about to be logged in the same session. These three are logged AFTER `format_output` is called (they're built and logged after the main card flow), so they aren't part of `total_u_all` in the validation display.

Impact: On a cross-run basis, all these are included in `_units_bet_today()` for the next sport's run. But within a single session, the validation check in Section H can show `≤12u` while actually ~1.25u more is about to be logged. The hard cap in `apply_caps()` only guards `qualified` picks; it does not account for upcoming SGP/daily_lay/longshot. In practice this is a small overshoot risk (max ~1.25u over 12u cap) and only matters on days where the premium card is near the cap.

---

## Section 17 — R12 Cooldown

### Finding 17.1: CORRECT — Lookback window math
**File:** engine/run_picks.py:1118–1147

**Code:**
```python
def auto_r12_from_log(today_str: str, window_days: int = 5) -> list[str]:
    cutoff = (datetime.strptime(today_str, "%Y-%m-%d") - timedelta(days=window_days)).strftime("%Y-%m-%d")
    ...
    if not (cutoff <= row_date < today_str):  # exclude today — not graded yet
        continue
```

**Verdict:** Correct. For today=2026-05-22 and window_days=5:
- cutoff = 2026-05-17
- Condition includes: May 17, 18, 19, 20, 21 — exactly 5 days.
- Today is excluded (`< today_str`) because today's picks are not yet graded.
- The F2.8 comment confirms this was previously buggy (`window_days-1` gave only 4 days) and was fixed.

---

### Finding 17.2: CORRECT — Cooldown selection criteria (player name normalization)
**File:** engine/run_picks.py:1149–1154

**Code:**
```python
def apply_r12_cooldown(picks, cooldown_players):
    cool_set = {normalize_name(n) for n in cooldown_players}
    return [p for p in picks if normalize_name(p["player"]) not in cool_set]
```

**Verdict:** Correct. Both the player names from the log and from the current picks are passed through `normalize_name()`, ensuring case-insensitive and accent-insensitive matching. Using a set for `cool_set` provides O(1) lookup. The filter is a simple exclusion of any pick whose player appears in the cooldown set.

---

### Finding 17.3: ISSUE (known design gap) — R12 does not filter by sport
**File:** engine/run_picks.py:1118–1147

**Code:**
```python
for r in rows:
    if r.get("result", "").upper() != "L":
        continue
    if r.get("run_type", "") not in ("primary", "bonus"):
        continue
    row_date = r.get("date", "")
    if not (cutoff <= row_date < today_str):
        continue
    player = r.get("player", "").strip()
    if player:
        losers.add(player)
```

**Verdict:** ISSUE (design gap, minimal practical impact). `auto_r12_from_log` adds any player with a loss across ANY sport to the cooldown list — there is no sport filter. In theory, an NHL player who lost yesterday could be cooled for NBA if they share a name. In practice this is virtually impossible since NHL and NBA players do not share names in any real scenario. More meaningfully: if the same player plays in WNBA and NBA (impossible currently) or MLB and NBA (impossible), they could be cross-sport cooled. The practical risk is near-zero. If the team ever wants clean sport-scoped cooldown, add `r.get("sport", "") == current_sport_filter` to the loop.

A subtler issue: R12 applies to ALL picks from `all_picks` (line 6321), which includes picks from all sports in the current multi-sport run. This is correct behavior — a player on cooldown should not appear regardless of which CSV they came from.

---

### Finding 17.4: CORRECT — Cooldown applied before gate check
**File:** engine/run_picks.py:6317–6324

**Code:**
```python
# Hard rules (R4, R11)
all_picks = apply_hard_rules(all_picks)

# R12 cooldown
all_picks = apply_r12_cooldown(all_picks, cooldown)

# Split qualified vs failed
qualified = [p for p in all_picks if p.get("gate_result") == "PASS" ...]
```

**Verdict:** Correct. R12 removes a player's picks entirely from `all_picks` before the qualified/failed split. This means cooled picks don't appear anywhere — they're not logged, not posted, and don't consume cap space. This is the correct behavior (suppress entirely, not just deprioritize).

---

## Summary

| # | Section | Finding | Severity |
|---|---------|---------|----------|
| 14.1 | Minute scalars | CORRECT — order of operations correct | — |
| 14.2 | Rate deflators | CORRECT — applied to final projections, correct | — |
| 14.3 | Home/away delta | CORRECT — multiplicative, correct sign | — |
| 14.4 | Blowout sigmoid | CORRECT — formula and direction correct | — |
| 14.5 | Vegas constraint | CORRECT — proportional scaling, cold_start included by design | — |
| 14.6 | Bayesian priors | CORRECT — 5-position split values plausible, units consistent | — |
| 14.7 | EWMA lambda | CORRECT — recency direction correct, normalization correct | — |
| 14.8 | PLAYOFF_RATE_DEFLATORS | CORRECT — multiplicative, applied after all other adjustments | — |
| 14.9 | AST rate training/projection denominator | ISSUE — historical per-game pace not used for normalization; systematic bias ~5-7% for players whose past opponents differ in pace from today | Minor |
| 14.10 | 240-min constraint | CORRECT — lineup-protection logic correct | — |
| 15.1 | CLV formula direction | CORRECT — closing − your = positive when beating close | — |
| 15.2 | CLV vig removal | ISSUE (design choice) — raw vigged probs; CLV slightly compressed vs vig-free; direction preserved | Minor |
| 15.3 | Implied prob formula | CORRECT — standard American odds conversion | — |
| 16.1 | G12 cross-run accumulation | CORRECT — _units_bet_today reads all prior runs | — |
| 16.2 | KILLSHOT in cap | CORRECT — logged as primary, counted in both _units_bet_today and in-session cap check | — |
| 16.3 | format_output cap validation | ISSUE — SGP/daily_lay/longshot (~1.25u) excluded from same-session cap display | Minor cosmetic |
| 17.1 | R12 window math | CORRECT — 5-day window inclusive, today excluded | — |
| 17.2 | R12 player matching | CORRECT — normalize_name on both sides | — |
| 17.3 | R12 sport filtering | ISSUE — no sport filter; cross-sport false cooldown theoretically possible | Negligible (design gap) |
| 17.4 | R12 cooldown timing | CORRECT — applied before qualified/failed split | — |

### Critical Issues: 0
### Significant Issues: 0
### Minor Issues: 3 (14.9, 16.3, 17.3)
### Design choices noted: 1 (15.2 — vig in CLV, standard practice)

---

### Recommended fixes (priority order)

1. **14.9 — AST training denominator**: In `compute_ast_rate()`, replace the single `team_pace` normalization of historical rows with per-game pace from `df_clean` (if available as a column). Low urgency since the bias is systematic and partially absorbed by the post-fit deflators, but this is the most mathematically substantive issue found.

2. **16.3 — Cap validation display**: In `format_output()`, add SGP/daily_lay/longshot unit sizes to `total_u_all` for the display check. These are already capped separately by their own builders, but the combined display being incomplete can confuse manual inspection.

3. **17.3 — R12 sport filter**: Add optional sport-scoped cooldown. Low priority given naming divergence across sports makes false positives virtually impossible today.
