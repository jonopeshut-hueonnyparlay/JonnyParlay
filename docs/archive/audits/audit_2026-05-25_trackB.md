# Audit 2026-05-25 — Track B: Probability Pipeline (v2 — post REB/AST→NB + SIGMA update)

Auditor: Claude Sonnet 4.6 (fresh session, post-2026-05-25 changes)
Scope: engine/run_picks.py — distribution routing, Platt scaling, confidence scalar, gate logic, edge calculation
Re-audited after: REB→NB(r=10.18), AST→NB(r=9.68), SIGMA["AST"] added (combo path, mult=0.53/min=2.0),
  SIGMA["REB"] updated (mult=0.48/min=2.0), SIGMA["PTS"] min raised 4.5→5.0.

---

## B1. Distribution Routing — Complete Map

### Normal (SIGMA dict) — current state post-2026-05-25
- `PTS`: mult=0.35, min=5.0 *(min raised from 4.5)*
- `REB`: mult=0.48, min=2.0 *(combo path only; was 0.58/2.5; single-stat now NB)*
- `AST`: mult=0.53, min=2.0 *(NEW 2026-05-25 — combo path only; was uncalibrated fallback)*
- `REC`: mult=0.50, min=1.2 *(also in POISSON_STATS — Poisson when line ≤ 8.5)*
- `OUTS`: mult=0.30, min=3.0
- `HA`: mult=0.50, min=2.5
- Combo stats (PRA, PR, PA, RA): correlated Normal via `_combo_mu_sigma()`

### Poisson (`POISSON_STATS`, line ≤ `POISSON_CUTOFF=8.5`)
`SOG`, `REC`, `HITS` *(REB removed 2026-05-25 — moved to NB)*

### Negative Binomial (`NB_STATS`)
`3PM` (r=9.15), `AST` (r=9.68), `REB` (r=10.18), `HRR` (r=1.5), `K` (r=5.0) *(AST and REB added 2026-05-25)*

### Special/disabled
- `TB`: gate-blocked (`G_TB_DISABLED`). Market not fetched.
- `NRFI`/`YRFI`: `evaluate_nrfi()` returns `[]` immediately (~line 3056) — fully disabled.
- `YARDS`, `TDS`, `GOALS`: In tier dict but NOT in SIGMA/POISSON_STATS/NB_STATS → fall to uncalibrated fallback `{"mult":0.40,"min":2.0}`. NFL off-season; no production impact currently.

### WNBA 3PM routing
~line 687: `elif stat in NB_STATS and not (sport == "WNBA" and stat == "3PM"):`
WNBA 3PM bypasses NB and uses `SIGMA_WNBA["3PM"] = {"mult":0.48,"min":0.70}` (Normal). Correct — WNBA 3PM is underdispersed.

### SIGMA_WNBA (~lines 324–329)
`PTS: {mult:0.38,min:3.5}`, `AST: {mult:0.55,min:1.1}`, `REB: {mult:0.45,min:2.0}`, `3PM: {mult:0.48,min:0.70}`

---

## B2. Platt Scaling Pipeline

### Formula — VERIFIED CORRECT post-2026-05-25 CLAUDE.md fix
**Production code** (~line 649, `_platt_calibrate_prop()`):
```python
raw = PLATT_A * over_p + PLATT_B   # RAW-PROBABILITY SPACE
raw = max(-30.0, min(30.0, raw))    # numerical stability clamp
return 1.0 / (1.0 + math.exp(-raw))
```
Constants annotated at lines ~370–371: `"raw-probability space (not logit-space)"`.

**CLAUDE.md** now correctly states: "Formula: sigmoid(A * over_p + B) (raw-probability space — NOT logit-space)". Finding B-1 CLOSED.

### over_p_raw logging order
`over_p_raw = over_p` saved at ~line 2257, **before** Platt at ~line 2266. Correct.

### win_prob after Platt
`adj_wp = 0.50 + (over_p_platt - 0.50) * conf` at ~line 2303. Correct ordering.

### MLB Platt skip
~line 2265: Platt skipped for MLB. WNBA intentionally included (comment at ~line 2263).

### Game lines — no Platt
`evaluate_game_lines()` and `evaluate_f5_lines()` never call `_platt_calibrate_prop()`. Game line win_probs come directly from Normal CDF.

### sigma_override (custom engine dk_std)
When `sigma_override > 0`, only `calc_prop_prob()` sigma changes. `over_p` returned is Platt-scaled normally. No bypass for custom engine σ.

---

## B3. Confidence Scalar

**Computation** (~lines 2293–2299):
- GP < 10: conf = 0.70
- GP 10–19: conf = 0.85
- GP ≥ 20 or unknown: conf = 1.0

**Applied to BOTH adj_edge AND adj_wp** (~lines 2300, 2303): ✓ Correct.
- `adj_edge = raw_edge * conf`
- `adj_wp = 0.50 + (win_prob - 0.50) * conf`

**pick["win_prob"]** stores `adj_wp`. Gates read `prob = pick["win_prob"]` — confidence-shrunk. Correct.

---

## B4. Gate Logic

### check_prop_gates() — full list (~lines 886–1055)

| Gate | Condition | n at implementation | Band-aid? |
|------|-----------|---------------------|-----------|
| G3 | `missing_side` → block | structural (dead code — see A-3) | No |
| G7 | odds ≤ −150 → block | structural | No |
| G7b | −149 ≤ odds ≤ −140 AND edge < 0.09 | structural | No |
| G8 | low-line binary props (line ≤ 1.5 for fragile stats) | structural | No |
| G8B | AST over ≤ 4.5 (non-WNBA) | n≈8 at implementation | Possibly — thin n |
| G8C | SOG under ≤ 3.5 | n=14–27 | Partially |
| G8D | 3PM over ≤ 1.5 | n=16 | Partially |
| G_WNBA_OPEN | WNBA days 1–3 of season | structural | No |
| G_WNBA_EDGE | WNBA effective_edge < 0.035 | structural | No |
| G_K_NO_UNDERS | K under → always block | structural | No |
| G_K_MIN_LINE | K over < 6.0 → block | structural | No |
| G_OUTS_UNDER | OUTS under AND prob < 0.60 | structural (miscal. indicator) | Partial band-aid |
| G_HA_DIR | HA/HITS over → always block | structural | No |
| G9 | edge < 0.03 → block | structural | No |
| G13 | prob < 0.50 → block | structural | No |
| G13B | HRR line-specific WP floors | shadow log | Partial |
| G_HRR_DISABLED | HRR → always block | empirical | No (structural kill) |
| G_TB_DISABLED | TB → always block | structural | No |
| G14 | Normal stats: proj must clear line by ≥ 0.10σ | structural | No |
| G15 | 3PM AND pts_cv ≥ 0.60 → block (bimodal flag) | structural | No |
| G1 | prob ≥ 0.70 AND odds > −200 AND edge < 0.05 | structural | No |
| G2 | edge ≥ 0.20 (0.28 for soft O0.5) → block | structural (model error) | No |
| G4 | line ≤ 2.5 AND prob > 0.75 | structural | No |
| G5 | odds > 0 AND prob > 0.65 | structural | No |
| G10 | under AND line ≤ 2.5 AND edge < 0.08 | structural | No |

### TEAM_TOTAL over block (~lines 2728–2730)
Hard `continue` in `evaluate_game_lines()`, not a named gate:
```python
# TEAM_TOTAL over blocked: 45.5% WR (n=11), provisional block
if direction == "over":
    continue
```
**Applies to ALL sports** (NBA, NHL, MLB, WNBA) despite being empirically justified only from NBA data (n=11).

### MIN_WIN_PROB (~line 1164)
`MIN_WIN_PROB = 0.55` — applied in `apply_soft_rules_premium()` (premium card only), not a hard gate in `check_prop_gates()`. Picks with WP 0.50–0.55 can still appear in bonus/daily_lay/longshot.

---

## B5. Edge Calculation

**`calc_edge()` (~lines 792–800)**:
```python
imp_over  = implied_prob(over_odds)
imp_under = implied_prob(under_odds)
nv_over, nv_under = no_vig(imp_over, imp_under)
over_edge  = model_prob - nv_over      # raw_edge for over direction
under_edge = (1.0 - model_prob) - nv_under
```

`nv_prob` is the **no-vig probability**, not raw implied. Correct.

**`raw_edge`**: model_p (Platt-calibrated) minus no-vig market probability. Correct.

**Missing-side**: Props with a missing side are dropped at ~2229 before pick dict is created. `missing_side=False` hardcoded at pick-creation sites. G3 is dead code for props (see A-3).

---

## Findings

### B-1 — CLOSED (was CRITICAL) — CLAUDE.md describes wrong Platt formula space

**STATUS: FIXED** by 2026-05-25 CLAUDE.md update. CLAUDE.md now reads:
"Formula: sigmoid(A * over_p + B) (raw-probability space — NOT logit-space). At H3, BOTH
formula AND coefficients change simultaneously from calibrate_platt.py output."
Fresh-session verification confirmed: code at ~line 649 and CLAUDE.md now agree — both
say raw-probability space. **No further action needed.**

### B-2 (MEDIUM) — TEAM_TOTAL over block applies to all sports, only NBA data

```
TRACK: B
FILE: engine/run_picks.py
LINE: ~2728–2730
SEVERITY: MEDIUM
N: 11 (NBA only)
ISSUE: The TEAM_TOTAL over block fires unconditionally for all sports. The empirical basis
is NBA n=11 (45.5% WR). There is no NHL or MLB TEAM_TOTAL over data cited. NHL goals
totals and MLB run totals have different market dynamics and over-bias characteristics.
IMPACT: NHL/MLB TEAM_TOTAL overs are blocked with no empirical justification for those sports.
FIX: Add sport guard: `if direction == "over" and sport == "NBA": continue`
(or whichever sports have proven bad WR). Annotate with sports scope.
```

### B-3 (MEDIUM) — G8B implemented at n<30 (thin sample)

```
TRACK: B
FILE: engine/run_picks.py
LINE: ~919–923
SEVERITY: MEDIUM
N: ~8 at implementation
ISSUE: G8B (AST over ≤ 4.5) was implemented when n≈8 across the full log. n < 30 threshold
means this is provisional. Current evidence (0-5 in blocked range, 2-3 in allowed) is
directionally clear but statistically thin.
IMPACT: Gate may block AST over picks that are actually +EV at certain lines in the blocked
range. Cannot confirm without more data.
FIX: Monitor only. Do not remove or expand until n ≥ 30 in the blocked range.
```

### B-4 (LOW) — MIN_WIN_PROB only filters premium card

```
TRACK: B
FILE: engine/run_picks.py
LINE: ~1164, ~1200
SEVERITY: LOW
N: N/A
ISSUE: MIN_WIN_PROB=0.55 is applied only in apply_soft_rules_premium() (premium card
selection). Picks with WP 0.50–0.55 still appear in bonus, daily_lay, longshot, and
non-premium outputs.
IMPACT: Low — bonus/parlay stakes are smaller. But systematic under-WP picks can appear
in secondary channels.
FIX: Document this scope explicitly. Consider whether MIN_WIN_PROB should also gate bonus.
```

### B-5 (LOW) — NFL/future stats fall to uncalibrated fallback

```
TRACK: B
FILE: engine/run_picks.py
LINE: ~716–717
SEVERITY: LOW
N: N/A
ISSUE: YARDS, TDS, GOALS are not in SIGMA, POISSON_STATS, or NB_STATS. They fall to
{"mult":0.40,"min":2.0} uncalibrated fallback with a logged warning.
IMPACT: None currently (NFL off-season). Would affect win_prob for those stats if enabled.
FIX: Add calibrated SIGMA entries before enabling NFL.
```
