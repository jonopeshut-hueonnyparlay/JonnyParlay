# Math Audit — Sections 9 & 10
**Date:** 2026-05-22  
**Scope:** All gate formulas (Section 9) + KILLSHOT gate (Section 10)  
**Files:** `engine/run_picks.py`

---

## Section 9 — All Gate Formulas

### Finding 9.1: CORRECT — G3 (missing_side)
**File:** `engine/run_picks.py:926-927`
**Code:**
```python
if pick.get("missing_side"):
    return False, "G3"
```
**Verdict:** Fires when one side of the market is missing (no over or no under). Condition and placement are correct. Applied first in `check_prop_gates`.

---

### Finding 9.2: CORRECT — G7 (hard juice ban)
**File:** `engine/run_picks.py:929-931`
**Code:**
```python
# G7: hard juice ban
if odds <= -150:
    return False, "G7"
```
**Verdict:** Blocks any pick at -150 or worse odds. Inclusive boundary (odds == -150 is blocked). Correct.

---

### Finding 9.3: CORRECT — G7b (soft juice)
**File:** `engine/run_picks.py:933-935`
**Code:**
```python
# G7b: soft juice
if -149 <= odds <= -140 and edge < 0.09:
    return False, "G7b"
```
**Verdict:** Requires ≥9% edge for odds in the -140 to -149 range. Condition is correct — was previously inverted (edge >= 0.09) which was fixed. Current version blocks low-edge picks at juicy odds. No gap/overlap with G7 boundary (-149 follows -150). Correct.

---

### Finding 9.4: ISSUE — G8 SOG under exception is dead code
**File:** `engine/run_picks.py:937-943`
**Code:**
```python
# G8: binary fragility
if stat in ("AST", "REB", "SOG", "K", "HA", "HITS") and line <= 1.5:
    if stat == "SOG" and direction == "under" and prob >= 0.80 and edge >= 0.15:
        pass  # High-conviction SOG under exception — allow through
    else:
        return False, "G8"
```
**Verdict:** The G8 exception for SOG under (WP ≥ 0.80, edge ≥ 0.15) is unreachable. G4 blocks any pick with `line <= 2.5 AND prob > 0.75` (line 1051). Since the exception requires `prob >= 0.80 > 0.75` and `line <= 1.5 <= 2.5`, G4 will always block it before the pick escapes G8. The exception passes G8 but the pick is guaranteed to fail G4 downstream. No behavioral impact (correct outcomes, just dead code). The comment claiming high-conviction SOG unders are "allowed through" is misleading.

---

### Finding 9.5: CORRECT — G8B (AST over at low lines)
**File:** `engine/run_picks.py:945-950`
**Code:**
```python
# G8B: AST over at line ≤ 4.5
sport = pick.get("sport", "NBA")
if stat == "AST" and direction == "over" and line <= 4.5 and sport != "WNBA":
    return False, "G8B"
```
**Verdict:** Blocks NBA AST overs at line ≤ 4.5 (empirical 0-5 record). WNBA exception is correct (4.5 is elite-playmaker territory in WNBA). Direction correctly checks "over" only. Correct.

---

### Finding 9.6: CORRECT — G_WNBA_OPEN (opening days blackout)
**File:** `engine/run_picks.py:957-960`
**Code:**
```python
if 1 <= season_day <= WNBA_OPENING_GATE_DAYS:
    return False, "G_WNBA_OPEN"
```
**Verdict:** Blocks first 3 days of WNBA season (season_day 1-3). `season_day = (today - WNBA_SEASON_START).days + 1`, so opening day = day 1. Gate fires for days 1-3 inclusive. Correct.  
Note: pre-season dates (before WNBA_SEASON_START) produce season_day ≤ 0, which passes this gate. Pre-season WNBA is still shadow-only so no Discord impact, but the intent is arguably to also block pre-season dates.

---

### Finding 9.7: CORRECT — G_WNBA_EDGE (WNBA edge floor with early-season multiplier)
**File:** `engine/run_picks.py:962-971`
**Code:**
```python
effective_edge = edge
for day_cap, mult in WNBA_EARLY_SEASON_EDGE_MULT:
    if 0 < season_day <= day_cap:
        effective_edge = edge * mult
        break
if effective_edge < WNBA_EDGE_FLOOR:
    return False, "G_WNBA_EDGE"
```
**Verdict:** Multiplier table is `[(14, 0.80), (21, 0.90)]`. The `break` ensures only the first matching tier applies — days 4-14 get 0.80×, days 15-21 get 0.90×, days 22+ get 1.0×. Floor is 0.035. This is correctly structured. G_WNBA_EDGE always supersedes G9 (0.03) since 0.035 > 0.03. Correct.

---

### Finding 9.8: CORRECT — G_K_NO_UNDERS (K direction gate)
**File:** `engine/run_picks.py:976-977`
**Code:**
```python
if stat == "K" and direction == "under":
    return False, "G_K_NO_UNDERS"
```
**Verdict:** Blocks all K unders. Rationale: SaberSim conservative IP projection means K unders structurally lose. Correct.

---

### Finding 9.9: CORRECT — G_K_MIN_LINE (K over minimum line)
**File:** `engine/run_picks.py:978-979`
**Code:**
```python
if stat == "K" and direction == "over" and line < 6.0:
    return False, "G_K_MIN_LINE"
```
**Verdict:** Blocks K overs at lines below 6.0. Only allows high-throughput ace lines. Correct.

---

### Finding 9.10: CORRECT — G_OUTS_UNDER (OUTS direction gate)
**File:** `engine/run_picks.py:981-982`
**Code:**
```python
if stat == "OUTS" and direction == "under":
    return False, "G_OUTS_UNDER"
```
**Verdict:** Same IP-bias rationale as K unders. Correct.

---

### Finding 9.11: CORRECT — G_HA_DIR (HA/HITS direction gate)
**File:** `engine/run_picks.py:984-985`
**Code:**
```python
if stat in ("HA", "HITS") and direction == "over":
    return False, "G_HA_DIR"
```
**Verdict:** T1B tier definition for HA/HITS is unders-only. Blocks overs with no research basis. Correct.

---

### Finding 9.12: CORRECT — G9 (universal edge floor)
**File:** `engine/run_picks.py:987-989`
**Code:**
```python
# G9: universal floor
if edge < 0.03:
    return False, "G9"
```
**Verdict:** 3% minimum edge for all props. Applied after all structural gates and before win-prob checks. Correct ordering. Consistent with T1/T1B min_edge=0.03.

---

### Finding 9.13: CORRECT — G13 (sub-50% WP ban)
**File:** `engine/run_picks.py:991-993`
**Code:**
```python
# G13: sub-50% win probability ban
if prob < 0.50:
    return False, "G13"
```
**Verdict:** Blocks any pick where model has less than 50% confidence. Strict inequality (prob = 0.50 passes). Correct.

---

### Finding 9.14: CORRECT — G13B (HRR line-specific WP floors)
**File:** `engine/run_picks.py:995-1002`
**Code:**
```python
if stat == "HRR":
    if line <= 0.5 and prob < 0.58:
        return False, "G13B"
    if line > 0.5 and prob < 0.65:
        return False, "G13B"
```
**Verdict:** HRR thresholds match documented values (58% at line ≤ 0.5, 65% at line > 0.5). Rationale: NB(r=1.5) over-states P(X≥1) at ~72% vs empirical 57.4%. The binary split on line=0.5 is correct. Correct.

---

### Finding 9.15: ISSUE — G13B TB WP gate exists only in sanity checklist, not in check_prop_gates
**File:** `engine/run_picks.py:995-1002` (gate) vs `5867-5873` (checklist)
**Code:**
```python
# check_prop_gates (the actual gate):
if stat == "HRR":
    if line <= 0.5 and prob < 0.58: return False, "G13B"
    if line > 0.5 and prob < 0.65:  return False, "G13B"

# format_output sanity checklist:
_STAT_MIN_WIN_PROB = {"TB": 0.60}
has_g13b_fail = any(
    (p.get("stat") in _STAT_MIN_WIN_PROB and p.get("win_prob", 0) < _STAT_MIN_WIN_PROB[p["stat"]])
    or (p.get("stat") == "HRR" and ...)
    for p in all_qualified
)
```
**Verdict:** The sanity checklist at line 5867-5873 checks for a TB WP ≥ 60% minimum under the G13B label. No such gate exists in `check_prop_gates`. A TB pick with WP in [0.50, 0.60) will pass all actual gates (G13 requires WP ≥ 0.50) but will flag `has_g13b_fail = True` in the output verification checklist — a false positive. The checklist is over-strict vs the actual gate. The docs (`MLB_RESEARCH_AGENDA.md:69`) also reference "G13B sets WP≥60% for TB" as if it exists in the gate. Either: (a) the TB WP gate was planned but never implemented in `check_prop_gates`, or (b) it was removed from the gate but the checklist wasn't updated. Either way, a TB pick with WP 0.55 would pass all real gates but fail the sanity check, producing a false ✗ in the output verification table.

---

### Finding 9.16: CORRECT — G14 (projection clearance gate)
**File:** `engine/run_picks.py:1004-1029`
**Code:**
```python
if stat in SIGMA and stat not in POISSON_STATS:
    _s = (SIGMA_WNBA.get(stat) if sport == "WNBA" else None) or SIGMA[stat]
    _sigma = max(proj * _s["mult"], _s["min"])
    _z = (line - proj) / _sigma if direction == "under" else (proj - line) / _sigma
    if _z < 0.10:
        return False, "G14"
```
**Verdict:** Applies to Normal/SIGMA stats not in POISSON_STATS. Computes z = directional clearance in sigma units. Threshold 0.10σ (10% of a sigma). The floor `max(proj * mult, min)` prevents division by zero (min is always > 0). POISSON_STATS exemption is correct (Poisson handles near-line projections properly via discrete distribution). COMBO_STATS receive their own G14 block using the correlated-Normal sigma. WNBA 3PM uses SIGMA_WNBA. All three branches are consistent. Correct.

---

### Finding 9.17: CORRECT — G15 (HIGH-VAR 3PM gate)
**File:** `engine/run_picks.py:1031-1038`
**Code:**
```python
if stat == "3PM":
    _cv = pick.get("pts_cv")
    if _cv and float(_cv) >= 0.60:
        return False, "G15"
```
**Verdict:** Blocks 3PM bets when the custom engine flags pts_cv ≥ 0.60 (bimodal scorer). No-op for SaberSim CSV runs (pts_cv column empty). Threshold matches HIGH_VAR_CV_THRESHOLD=0.60 in CLAUDE.md. Correct.

---

### Finding 9.18: CORRECT — G1 (high prob + bad odds)
**File:** `engine/run_picks.py:1040-1042`
**Code:**
```python
if prob >= 0.70 and odds > -200 and edge < 0.05:
    return False, "G1"
```
**Verdict:** Catches high-confidence picks at reasonable odds with insufficient edge — likely overfit model output. `odds > -200` excludes extremely juicy chalk (already caught by G7). Edge exception at 5% means legitimate high-edge picks pass. Correct.

---

### Finding 9.19: CORRECT — G2 (edge ceiling / model error)
**File:** `engine/run_picks.py:1044-1048`
**Code:**
```python
_is_soft_o05 = (stat in ("HRR", "TB", "HITS") and line <= 0.5 and direction == "over")
g2_threshold = 0.28 if _is_soft_o05 else 0.20
if edge >= g2_threshold:
    return False, "G2"
```
**Verdict:** Edge ≥ 20% signals a model/stale-line error. Soft O0.5 markets (HRR/TB/HITS at 0.5 line, overs) get a higher 28% threshold because they legitimately have larger edges (thin, slow-to-update markets). Correct.

---

### Finding 9.20: CORRECT — G4 (low line + extreme probability)
**File:** `engine/run_picks.py:1050-1052`
**Code:**
```python
if line <= 2.5 and prob > 0.75 and not _is_soft_o05:
    return False, "G4"
```
**Verdict:** Extreme WP (>75%) at low lines suggests model is over-confident or market is stale. Soft O0.5 exemption correct (these have legitimately high probs). As a side effect, G4 renders the G8 SOG under exception dead (see Finding 9.4). Correct.

---

### Finding 9.21: CORRECT — G5 (positive odds + high probability)
**File:** `engine/run_picks.py:1054-1056`
**Code:**
```python
if odds > 0 and prob > 0.65 and not _is_soft_o05:
    return False, "G5"
```
**Verdict:** Blocks plus-odds picks with high model confidence — suggests a large market vs model disagreement that is likely a model error. Note interaction with KILLSHOT: WP > 0.65 at positive odds is blocked by G5, meaning KILLSHOT auto-qualify at positive odds is only possible at exactly WP = 0.65 (not strictly greater). This is a tight but correct constraint. Correct.

---

### Finding 9.22: CORRECT — G10 (low-line under fragility)
**File:** `engine/run_picks.py:1058-1060`
**Code:**
```python
if direction == "under" and line <= 2.5 and edge < 0.08:
    return False, "G10"
```
**Verdict:** Low-line unders need ≥8% edge (vs 3% G9 floor). Under at 2.5 or less is fragile — a single bounce changes the outcome. Higher edge requirement is sensible. Correct.

---

### Finding 9.23: CORRECT — GG1 (game line edge ceiling)
**File:** `engine/run_picks.py:1074-1075`
**Code:**
```python
if edge >= 0.10:
    return False, "GG1"
```
**Verdict:** Game lines with ≥10% edge signal a blended projection error (market vs model disagreement is too large). Threshold of 10% is tighter than G2's 20% for props — appropriate since game lines rely on team-level projections with more noise. Correct.

---

### Finding 9.24: CORRECT — GG2 (projection deviation gate)
**File:** `engine/run_picks.py:1076-1086`
**Code:**
```python
if sigma > 0:
    if stat == "SPREAD":
        deviation = abs(proj + line) / sigma
    else:
        deviation = abs(proj - line) / sigma
    if deviation > 1.5:
        return False, "GG2"
```
**Verdict:** SPREAD deviation uses `abs(proj + line)` because line is from the team's perspective (negative = favorite, so -line is the market-implied margin). For all other game stats, `abs(proj - line)` is the standard formula. The 1.5σ threshold is reasonable. Correct.

---

### Finding 9.25: CORRECT — GG3 (positive edge required)
**File:** `engine/run_picks.py:1087-1088`
**Code:**
```python
if edge <= 0:
    return False, "GG3"
```
**Verdict:** Blocks zero-edge or negative-edge game picks. `<=` means exactly-zero edge is also blocked (no bet at fair value). Correct.

---

### Finding 9.26: CORRECT — GG4 (missing side)
**File:** `engine/run_picks.py:1072-1073`
**Code:**
```python
if pick.get("missing_side"):
    return False, "GG4"
```
**Verdict:** Game-line equivalent of G3. Blocks incomplete markets. Applied first in `check_game_gates`. Correct.

---

### Finding 9.27: CORRECT — GG5 (no dog-cover spread bets)
**File:** `engine/run_picks.py:1090-1094`
**Code:**
```python
if pick.get("stat") in ("SPREAD", "F5_SPREAD") and pick.get("odds", 0) > 0:
    return False, "GG5"
```
**Verdict:** Blocks puck-line and run-line underdog bets (fixed ±1.5 spread with positive odds). These have WP < 50% and negative expected score. Correct.

---

### Finding 9.28: CORRECT — TIER_MIN (tier minimum edge after prop gates)
**File:** `engine/run_picks.py:2331-2336`
**Code:**
```python
if adj_edge < get_tier_min_edge(tier):
    pick["gate_result"] = f"TIER_MIN({tier})"
    pick["size"] = 0
    picks.append(pick)
    continue
```
**Verdict:** Applied after `check_prop_gates` passes. Enforces T1=3%, T1B=3%, T2=5%, T3=6% minimums. G9 (3%) is always applied first, so TIER_MIN is only the binding constraint for T2 (5%) and T3 (6%). For T1/T1B, TIER_MIN and G9 are equivalent. `get_tier_min_edge` defaults to 5% for unknown tiers (KILLSHOT, DAILY_LAY). Correct.

---

### Finding 9.29: ISSUE — has_g8_fail sanity check doesn't replicate G8 SOG exception
**File:** `engine/run_picks.py:5860-5865`
**Code:**
```python
has_g8_fail = any(
    (p["stat"] in ("AST","REB","SOG","K","HA","HITS") and p["line"] <= 1.5) or
    (p["stat"] == "AST" and p["direction"] == "over" and p["line"] <= 4.5
     and p.get("sport") != "WNBA")
    for p in all_qualified
)
```
**Verdict:** The sanity check flags any SOG pick with line ≤ 1.5 as a G8 failure, regardless of direction. But G8 has an exception for SOG under at high confidence (WP ≥ 0.80, edge ≥ 0.15). However, as documented in Finding 9.4, that exception is dead code (G4 blocks it anyway). So in practice, no such SOG under at line ≤ 1.5 can survive gates, and the checklist discrepancy has no actual impact. Minor documentation issue only.

---

### Finding 9.30: CORRECT — Daily Lay per-leg gates
**File:** `engine/run_picks.py:3682-3686`
**Code:**
```python
if edge < MIN_LEG_EDGE_DAILY:  # 0.025
    continue
if cover_prob < MIN_LEG_COVER_PROB_DAILY:  # 0.58
    continue
```
**Verdict:** Per-leg gates match CLAUDE.md spec (edge ≥ 0.025, cover_prob ≥ 0.58). The combined parlay minimum is MIN_DAILY_LAY_PROB = 0.47. Thresholds are correct.

---

### Finding 9.31: UNCERTAIN — Daily Lay edge uses vigged (not no-vig) implied probability
**File:** `engine/run_picks.py:3677-3679`
**Code:**
```python
implied = abs(odds) / (abs(odds) + 100.0) if odds < 0 else 100.0 / (odds + 100.0)
cover_prob = 1.0 - normal_cdf(-line, margin, sigma)
edge = cover_prob - implied
```
**Verdict:** The `implied` here is the raw vigged probability, not the no-vig probability. The rest of the engine uses no-vig edges (via `calc_edge()` → `no_vig()`). Using vigged implied understates the edge (vigged prob > no-vig prob for favorites), so the 0.025 threshold is effectively harder to meet than if no-vig were used. This is conservative rather than loose, but it is inconsistent with the main prop pipeline. The alt-spread market only has one side visible in the data (alt spreads are one-directional), so a no-vig calculation may not be feasible. UNCERTAIN — could be intentional given single-sided alt spread data, or could be a documentation gap.

---

### Finding 9.32: CORRECT — NRFI/YRFI min edge gates
**File:** `engine/run_picks.py:3188-3191`
**Code:**
```python
min_edge = 0.08 if stat_label == "YRFI" else TIERS["T3"]["min_edge"]
if raw_edge < min_edge:
    continue
```
**Verdict:** NRFI uses T3 min_edge (6%). YRFI requires 8% (higher bar per R5). NRFI picks then run through `check_game_gates` (GG1-GG5) — no G7 (juice) or G9 (prop edge) checks, which is appropriate since NRFI is a binary game-level bet. Correct.

---

### Finding 9.33: CORRECT — F5 Total min edge
**File:** `engine/run_picks.py:2870`
**Code:**
```python
if passed and edge >= 0.03:  # T1B: 3% min edge
```
**Verdict:** F5 Total is classified T1B (`tier: "T1B"` at line 2865), and T1B min_edge = 0.03. Consistent. Correct.

---

### Finding 9.34: CORRECT — Spread, ML, Team Total min edges
**File:** `engine/run_picks.py:2520, 2629, 2706`
**Code:**
```python
spread_min_edge = 0.06 if sport in _FIXED_SPREAD_SPORTS else 0.05
min_edge = 0.05 if is_fav else _dog_edge  # _dog_edge: NHL=0.06, NBA=0.07, else=0.08
tt_min_edge = 0.03 if sport in ("NBA", "MLB") else 0.05
```
**Verdict:**
- SPREAD: Fixed-spread sports (MLB/NHL) require 6%; variable-spread (NBA) requires 5%. Consistent with T3 vs T2 classification.
- ML_FAV: 5% (T2). ML_DOG: sport-specific (NHL 6%, NBA 7%, MLB 8%) — correct sport-specific tuning.
- TEAM_TOTAL: NBA/MLB 3% (T1B), others 5% (T2). Consistent with tier assignment.
All match documented values. Correct.

---

## Section 10 — KILLSHOT Gate

### Finding 10.1: CORRECT — Tier check (strict T1 only)
**File:** `engine/run_picks.py:5152-5153`
**Code:**
```python
if pick.get("tier") != KILLSHOT_TIER_REQUIRED:
    return False, f"tier={pick.get('tier')!r} (need {KILLSHOT_TIER_REQUIRED})"
```
**Verdict:** `KILLSHOT_TIER_REQUIRED = "T1"`. Strict equality — T1B, T2, T3 all fail. Matches CLAUDE.md spec. Correct.

---

### Finding 10.2: ISSUE — PTS is in KILLSHOT_STAT_ALLOW but can never auto-qualify
**File:** `engine/run_picks.py:200`
**Code:**
```python
KILLSHOT_STAT_ALLOW = frozenset({"PTS", "AST", "SOG"})
```
**Verdict:** PTS is T2 (line 400: `"T2": {"stats": {"PTS", ...}}`). The tier check (T1 required) fires before the stat check for auto-qualify. A PTS pick can never reach the stat check in `_passes_killshot_v2_gate` because it fails the tier gate first. PTS in the allowlist is dead constant for auto-qualify. PTS KILLSHOTs are only achievable via manual `--killshot` override (which bypasses `_passes_killshot_v2_gate` entirely). The constant is misleading — it implies PTS can auto-qualify when it cannot. Low severity; no incorrect pick posting. CLAUDE.md also lists PTS in the stat allowlist, so this reflects a design gap in documentation rather than a code bug.

---

### Finding 10.3: CORRECT — Pick score floor (≥ 65)
**File:** `engine/run_picks.py:5155-5159`
**Code:**
```python
score = float(pick.get("pick_score", 0))
if score < KILLSHOT_SCORE_FLOOR:
    return False, f"score={score:.1f} < {KILLSHOT_SCORE_FLOOR}"
```
**Verdict:** `KILLSHOT_SCORE_FLOOR = 65.0`. Strict inequality (score = 65.0 passes: 65.0 < 65.0 is False). Correct.

---

### Finding 10.4: CORRECT — Win probability floor (≥ 0.65)
**File:** `engine/run_picks.py:5160-5165`
**Code:**
```python
wp = float(pick.get("win_prob", 0))
if wp < KILLSHOT_WIN_PROB_FLOOR:
    return False, f"win_prob={wp:.3f} < {KILLSHOT_WIN_PROB_FLOOR}"
```
**Verdict:** `KILLSHOT_WIN_PROB_FLOOR = 0.65`. Strict inequality (WP = 0.65 passes). Correct.  
Note interaction: G5 blocks picks with `prob > 0.65` at positive odds, meaning the only KILLSHOT at positive odds is one with WP = exactly 0.65. This is a rare-but-possible corner case, not a bug.

---

### Finding 10.5: CORRECT — Odds range ([-200, +110])
**File:** `engine/run_picks.py:5166-5171`
**Code:**
```python
odds = int(float(pick.get("odds", 0)))
if odds < KILLSHOT_ODDS_MIN or odds > KILLSHOT_ODDS_MAX:
    return False, f"odds={odds:+d} outside [{KILLSHOT_ODDS_MIN},{KILLSHOT_ODDS_MAX}]"
```
**Verdict:** `KILLSHOT_ODDS_MIN = -200`, `KILLSHOT_ODDS_MAX = 110`. Both bounds inclusive (-200 passes: -200 < -200 is False; +110 passes: 110 > 110 is False). Correct.  
Note: G7 already blocks odds ≤ -150 in `check_prop_gates`, so KILLSHOT_ODDS_MIN = -200 is effectively dead for auto-qualify (no pick survives G7 at odds < -149). The constant is functionally a no-op for auto-qualifiers. For manual promotes, the `_passes_killshot_v2_gate` is bypassed entirely, so the -200 minimum also doesn't apply to manual promotes.

---

### Finding 10.6: CORRECT — Stat allowlist check ({PTS, AST, SOG})
**File:** `engine/run_picks.py:5172-5174`
**Code:**
```python
stat = pick.get("stat", "")
if stat not in KILLSHOT_STAT_ALLOW:
    return False, f"stat={stat!r} not in allowlist"
```
**Verdict:** Allowlist = {"PTS", "AST", "SOG"}. Check is applied in `_passes_killshot_v2_gate` (auto-qualify path only). Manual promotes bypass this check entirely (the manual path exits before calling `_passes_killshot_v2_gate`). For auto-qualify: AST and SOG can qualify (both T1). PTS cannot (see Finding 10.2). Correct logic; dead-constant issue documented separately.

---

### Finding 10.7: CORRECT — 4u bump condition (wp ≥ 0.70 AND edge ≥ 0.06)
**File:** `engine/run_picks.py:5142-5143`
**Code:**
```python
if wp >= KILLSHOT_BUMP_WIN_PROB and edge >= KILLSHOT_BUMP_EDGE:
    return KILLSHOT_SIZE_BUMP
return KILLSHOT_SIZE_BASE
```
**Verdict:** `KILLSHOT_BUMP_WIN_PROB = 0.70`, `KILLSHOT_BUMP_EDGE = 0.06`. Both conditions required (AND). Default is 3u (`KILLSHOT_SIZE_BASE = 3.0`), bump is 4u (`KILLSHOT_SIZE_BUMP = 4.0`). Matches CLAUDE.md spec exactly. `edge` reads `adj_edge` with fallback to `edge` key, covering both live run and reconstructed log rows. Correct.

---

### Finding 10.8: CORRECT — Weekly cap counting (rolling 7 days)
**File:** `engine/run_picks.py:5183`
**Code:**
```python
cutoff = (datetime.strptime(today_str, "%Y-%m-%d") - timedelta(days=6)).strftime("%Y-%m-%d")
return sum(
    1 for r in rows
    if r.get("tier") == "KILLSHOT"
    and cutoff <= r.get("date", "") <= today_str
)
```
**Verdict:** `today - 6 days` as cutoff means the window is [today-6, today] inclusive = 7 days. Matches CLAUDE.md "rolling 7 days including today". The count includes both auto-qualified and manually promoted KILLSHOTs (both have tier="KILLSHOT" at log time, set at line 5263). Correct.

---

### Finding 10.9: CORRECT — Cap fail-safe (assume full on error)
**File:** `engine/run_picks.py:5194-5202`
**Code:**
```python
except Exception as e:
    logger.error(...)
    return KILLSHOT_WEEKLY_CAP
```
**Verdict:** On any read/parse error, returns the full cap (2), which sets `remaining_cap = 0` and blocks all KILLSHOTs. This is safe — prevents double-posting on a corrupt log at the cost of missing a legitimate KILLSHOT. Correct fail-safe direction.

---

### Finding 10.10: CORRECT — Manual override requires score ≥ 75
**File:** `engine/run_picks.py:5248-5251`
**Code:**
```python
if _player_matches(player) and score >= KILLSHOT_MANUAL_FLOOR:
    candidates.append(p)
    continue
```
**Verdict:** `KILLSHOT_MANUAL_FLOOR = 75.0`. Manual promotes bypass v2 gate but still require score ≥ 75. The weekly cap check happens before this loop (`remaining_cap == 0` → early return). The cap is also applied at line 5259 (`candidates[:remaining_cap]`), so manual promotes count toward and are limited by the weekly cap. Correct.

---

### Finding 10.11: CORRECT — KILLSHOTs excluded from Premium 5 card
**File:** `engine/run_picks.py:6432-6435`
**Code:**
```python
ks_keys = {(p["player"], p["stat"], p["line"]) for p in killshots}
non_ks_qualified = [p for p in qualified if (p["player"], p["stat"], p["line"]) not in ks_keys]
premium = apply_soft_rules_premium([], non_ks_qualified, ...) if non_ks_qualified else []
```
**Verdict:** KILLSHOTs are removed from the qualified pool before building the Premium card. Premium shows next best picks after KILLSHOT is taken. KILLSHOT is posted separately to #killshot. Correct.

---

### Finding 10.12: CORRECT — Daily 12u cap includes KILLSHOT units
**File:** `engine/run_picks.py:6445-6452`
**Code:**
```python
_premium_u = sum(p.get("size", 0) for p in premium)
_ks_total  = sum(p.get("size", 0) for p in killshots)
if _premium_u + _ks_total + _units_today > 12.0:
    killshots = sorted(killshots, key=lambda x: x.get("pick_score", 0), reverse=True)
    while killshots and _premium_u + sum(...) + _units_today > 12.0:
        dropped = killshots.pop()
```
**Verdict:** Combined premium + KILLSHOT + prior units are checked against 12u cap. KILLSHOTs are trimmed (lowest-score first) if cap would be breached. This correctly handles multi-KILLSHOT days. Correct.

---

## Summary Table

| Finding | Gate/Feature | Verdict |
|---------|-------------|---------|
| 9.1 | G3 missing_side | CORRECT |
| 9.2 | G7 hard juice | CORRECT |
| 9.3 | G7b soft juice | CORRECT |
| 9.4 | G8 SOG exception | ISSUE — dead code (superseded by G4) |
| 9.5 | G8B AST over low lines | CORRECT |
| 9.6 | G_WNBA_OPEN blackout | CORRECT |
| 9.7 | G_WNBA_EDGE floor | CORRECT |
| 9.8 | G_K_NO_UNDERS | CORRECT |
| 9.9 | G_K_MIN_LINE | CORRECT |
| 9.10 | G_OUTS_UNDER | CORRECT |
| 9.11 | G_HA_DIR | CORRECT |
| 9.12 | G9 universal edge floor | CORRECT |
| 9.13 | G13 sub-50% WP ban | CORRECT |
| 9.14 | G13B HRR WP floors | CORRECT |
| 9.15 | G13B TB WP missing | ISSUE — checklist checks TB WP≥60%, no gate in check_prop_gates |
| 9.16 | G14 projection clearance | CORRECT |
| 9.17 | G15 HIGH-VAR 3PM | CORRECT |
| 9.18 | G1 high prob + bad odds | CORRECT |
| 9.19 | G2 edge ceiling | CORRECT |
| 9.20 | G4 extreme prob at low line | CORRECT |
| 9.21 | G5 positive odds + high prob | CORRECT |
| 9.22 | G10 low-line under fragility | CORRECT |
| 9.23 | GG1 game line edge ceiling | CORRECT |
| 9.24 | GG2 projection deviation | CORRECT |
| 9.25 | GG3 positive edge required | CORRECT |
| 9.26 | GG4 game line missing side | CORRECT |
| 9.27 | GG5 no dog-cover spreads | CORRECT |
| 9.28 | TIER_MIN per-tier floor | CORRECT |
| 9.29 | has_g8_fail SOG exception gap | ISSUE — false-positive risk in checklist (moot in practice) |
| 9.30 | Daily lay per-leg gates | CORRECT |
| 9.31 | Daily lay vigged vs no-vig edge | UNCERTAIN — conservative/safe but inconsistent with prop pipeline |
| 9.32 | NRFI/YRFI min edge | CORRECT |
| 9.33 | F5 Total min edge | CORRECT |
| 9.34 | Spread/ML/TT min edges | CORRECT |
| 10.1 | KILLSHOT tier=T1 strict | CORRECT |
| 10.2 | PTS in stat allowlist is dead | ISSUE — misleading constant; PTS can never auto-qualify |
| 10.3 | Score ≥ 65 | CORRECT |
| 10.4 | WP ≥ 0.65 | CORRECT |
| 10.5 | Odds [-200, +110] | CORRECT |
| 10.6 | Stat allowlist check | CORRECT |
| 10.7 | 4u bump (wp≥0.70 AND edge≥0.06) | CORRECT |
| 10.8 | Weekly cap rolling 7 days | CORRECT |
| 10.9 | Cap fail-safe on error | CORRECT |
| 10.10 | Manual override score ≥ 75 | CORRECT |
| 10.11 | KILLSHOT excluded from Premium | CORRECT |
| 10.12 | 12u cap includes KILLSHOT | CORRECT |

---

## Action Items

**HIGH — has operational or documentation impact:**

1. **G8 SOG exception (Finding 9.4):** Remove the dead `pass` exception from G8 — no pick can reach it due to G4. The comment "High-conviction SOG under exception — allow through" is misleading. Either remove the exception entirely, or change G4 to explicitly exempt high-confidence SOG unders (which would require a deliberate design decision).

2. **G13B TB WP gate (Finding 9.15):** The sanity checklist labels TB WP≥60% as a G13B check but there is no corresponding gate in `check_prop_gates`. Either:
   - Add `if stat == "TB" and prob < 0.60: return False, "G13B"` to `check_prop_gates`, or
   - Remove `{"TB": 0.60}` from `_STAT_MIN_WIN_PROB` in the sanity checklist.
   Currently a TB pick with WP 0.52 passes all real gates but incorrectly marks the verification checklist ✗.

**LOW — informational / documentation:**

3. **PTS in KILLSHOT_STAT_ALLOW (Finding 10.2):** PTS is T2 and can never auto-qualify. Update the constant comment or CLAUDE.md to note "PTS is manual-only". No code change required.

4. **KILLSHOT_ODDS_MIN = -200 is dead for auto-qualify (Finding 10.5):** G7 already blocks ≤ -150. The -200 minimum is never binding. Comment the constant to note "superseded by G7 for auto-qualify; applies only if G7 is ever relaxed."

5. **Daily lay vigged edge (Finding 9.31):** Consider whether the 0.025 floor should be computed against no-vig probability for consistency with prop pipeline. Current approach is conservative (harder hurdle than it appears), so false positives (overly loose legs) are not a risk.
