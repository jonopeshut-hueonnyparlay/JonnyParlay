# Audit 2026-05-25 — Track F: Scoring & Sizing

Auditor: Claude Sonnet 4.6 (automated)
Scope: engine/run_picks.py, engine/sgp_builder.py — pick_score, KILLSHOT gate, Kelly/VAKE sizing, parlay sizing

---

## F1. pick_score Formula

**Location:** engine/run_picks.py ~lines 802–829

**Formula:**
```python
def pick_score(win_prob, edge, mode="Default", tier=None,
               cold_start_subtype=None, injury_trigger=False, stat=None):
    sw, ew = PICK_SCORE_MODES.get(mode, (0.40, 0.60))   # Default: 40/60
    wp_n = (win_prob * 100 - 50) / 25 * 100             # 50%→0, 75%→100
    e_n  = (edge * 100) / 15 * 100                       # 15% edge → 100
    score = sw * wp_n + ew * e_n
    score *= PICK_SCORE_TIER_MULT.get(tier, 1.00)        # T1=0.90×, T2=1.00×, T3=0.95×
    score += COLD_START_SCORE_PENALTY.get(cold_start_subtype, 0)
    if injury_trigger:
        score += INJURY_TRIGGER_BONUS.get(stat, 7)
    return score
```

Formula is explicitly documented as a heuristic, not empirically derived.

---

### F-1 (MEDIUM) — pick_score uses pre-confidence win_prob, not adj_wp

```
TRACK: F
FILE: engine/run_picks.py
LINE: ~2369
SEVERITY: MEDIUM
N: N/A
ISSUE: pick_score() is called with the Platt-calibrated win_prob (pre-I6 confidence scalar),
not adj_wp. adj_wp = 0.50 + (win_prob - 0.50) * conf is computed at line ~2303 and stored
in pick["win_prob"], but line ~2369 passes the un-adjusted win_prob to pick_score().
For GP < 10 (conf=0.70): pick_score sees ~0.63 instead of ~0.579 — about 8 points inflated.
For GP < 20 (conf=0.85): ~4 points inflated.
IMPACT: Low-sample early-season players score 4–8 points higher than warranted, potentially
surfacing on Premium card or bonus drops when they shouldn't.
FIX: Change line ~2369 to pass adj_wp:
    pick["pick_score"] = pick_score(adj_wp, _score_edge, mode, tier=tier, ...)
```

### F-2 (LOW) — PICK_SCORE_TIER_MULT["KILLSHOT"] is dead code

```
TRACK: F
FILE: engine/run_picks.py
LINE: ~422–430
SEVERITY: LOW
N: N/A
ISSUE: PICK_SCORE_TIER_MULT maps "KILLSHOT": 1.00, but pick_score() is never called with
tier="KILLSHOT" in normal flow. KILLSHOT tier is applied AFTER pick_score is computed
(tier overwritten at ~line 5300). The existing score is computed under the original tier
(T1 → multiplier 0.90). The "KILLSHOT": 1.00 entry is dead code.
IMPACT: Cosmetic only. No production impact.
FIX: Remove "KILLSHOT": 1.00 from PICK_SCORE_TIER_MULT to eliminate confusion.
```

---

## F2. KILLSHOT Gate

**Location:** engine/run_picks.py ~lines 5184–5212, constants at ~lines 190–207

### All v2 criteria — verified in code

| Criterion | Constant | Status |
|---|---|---|
| tier = T1 strictly | `KILLSHOT_TIER_REQUIRED = "T1"` | ✓ Enforced |
| score ≥ 65 | `KILLSHOT_SCORE_FLOOR = 65.0` | ✓ Enforced |
| win_prob ≥ 0.65 | `KILLSHOT_WIN_PROB_FLOOR = 0.65` | ✓ Enforced |
| odds ∈ [−200, +110] | `KILLSHOT_ODDS_MIN = -200, KILLSHOT_ODDS_MAX = 110` | ✓ Inclusive bounds |
| stat ∈ {PTS, AST, SOG} | `KILLSHOT_STAT_ALLOW = frozenset({"PTS","AST","SOG"})` | ✓ 3PM and REB excluded |

**win_prob used here = adj_wp (confidence-adjusted) ✓** — pick["win_prob"] is adj_wp.

**Weekly cap**: Stored in pick_log.csv (file-backed), read under `_pick_log_lock`. Process-level `run_picks.lock` (timeout=0) prevents simultaneous sport runs. **No race condition risk.**

### F-3 (MEDIUM) — Manual KILLSHOT override bypasses stat/tier checks

```
TRACK: F
FILE: engine/run_picks.py
LINE: ~5285–5288
SEVERITY: MEDIUM
N: N/A
ISSUE: --killshot NAME bypasses _passes_killshot_v2_gate() entirely. For manual promotes,
only score >= KILLSHOT_MANUAL_FLOOR (75) is checked — no tier or stat validation.
A 3PM pick at score 76 (T3 tier) can be manually promoted to KILLSHOT with no other
enforcement. This contradicts CLAUDE.md's description: "Manual override bypasses gate but
still requires score≥75" — the score requirement is the ONLY thing checked.
IMPACT: Discord @everyone ping and 3u stake can be triggered for any stat/tier at score ≥ 75.
Brand risk if a T3 3PM pick posts as KILLSHOT.
FIX: Add stat/tier check on manual path:
    if stat not in KILLSHOT_STAT_ALLOW:
        print(f"WARNING: {stat} not in KILLSHOT_STAT_ALLOW — manual override bypasses")
    Add confirmation prompt or at minimum a warning log.
```

### F-4 (LOW) — SPORT_UNIT_CAP duplicated at two sites

```
TRACK: F
FILE: engine/run_picks.py
LINE: ~1315 and ~6151
SEVERITY: LOW
N: N/A
ISSUE: SPORT_UNIT_CAP is defined inside apply_caps() (~1315) and duplicated inline in
the KILLSHOT sizing re-check at ~6151. If one is updated, the other isn't automatically.
IMPACT: KILLSHOT could slip past its sport cap if the inline dict at ~6151 is stale.
FIX: Extract SPORT_UNIT_CAP to a module-level constant and reference both sites.
```

---

## F3. Kelly / VAKE Sizing

**VAKE is NOT Kelly.** VAKE is a flat edge-bucketed lookup table:

| Edge range | Base size |
|-----------|-----------|
| 3–5% | 0.50u |
| 5–7% | 0.75u |
| 7–9% | 1.00u |
| 9%+ | 1.25u |

Modified by variance × tier × correlation × exposure multipliers.

**VAKE vs full Kelly (WP=0.60, −110 odds):**
- Full Kelly: `f = (0.909×0.60 − 0.40)/0.909 = 16.0%` of bankroll = 16.0u on 100u bankroll
- VAKE at edge≈9%: 1.25u base × ~0.85 var × ~0.90 tier = ~0.95u → ≈1.0u
- **Effective fraction: ~1/16th of full Kelly (≈6.25% of quarter-Kelly)**

**`size_daily_lay()`** (~line 4486): Uses explicit quarter Kelly (`kelly_full * 0.25 * 100.0`), capped 0.25–0.75u. This IS a Kelly formula. Correct.

**12u daily cap enforcement:**
- Applied inside `apply_caps()` (~line 1331) on an in-memory running total
- Read-modify-write protected by process-level `run_picks.lock` — no concurrent run race
- SGP units excluded from session-level cap (see F-7 below)

**Sport caps (NBA=8u, NHL=5u):**
- Applied inside `apply_caps()` before daily cap is hit — correct order

### F-5 (HIGH) — Daily_lay + longshot use naive independence for combined_prob

```
TRACK: F
FILE: engine/run_picks.py
LINE: ~3609 (longshot), ~3823 (daily_lay)
SEVERITY: HIGH
N: N/A
ISSUE: combined_prob for both daily_lay and longshot uses naive independence multiplication:
    combined_prob = product(leg_probs)
For daily_lay, this combined_prob feeds directly into size_daily_lay() as the Kelly p parameter.
Cross-game correlation (pace outliers, market-wide moves) is ignored. For a 3-leg daily_lay
at 0.70 per leg: stated combined_prob=0.343, true ≈ 0.31–0.33 (8–12% overstatement).
After quarter-Kelly and 0.75u cap, final stake is usually at the cap anyway — overstatement
rarely affects final size in practice.
For longshot (6 legs): stated 0.118, true ≈ 0.08–0.10 (up to 50% overstatement). Longshot
is always fixed at 0.25u (flat stake), so Kelly is not used — overstatement affects framing
only, not money at risk.
IMPACT: Daily_lay sizing can be slightly over-aggressive (~8–12% of stake). At max 0.75u cap
the absolute overbet is ≤0.09u per parlay.
FIX: For daily_lay: apply a correlation haircut (e.g., multiply combined_prob by 0.90 for 3-leg,
0.85 for 2-leg) before passing to size_daily_lay(). Or document the independence assumption
explicitly with a comment. For longshot: no fix needed (flat stake).
```

---

## F4. SGP / Parlay / Daily_Lay Sizing and Probability

### SGP joint probability — correctly uses Gaussian copula
SGP uses a Gaussian copula with pairwise ρ values via `_copula_joint_prob()` (~4000 Monte Carlo samples). NOT a naive product. Correctly models within-game correlation. Approved.

### Daily_lay odds cap
`MAX_COMBINED_ODDS_VAL = 100` (+100 max combined parlay odds) — correctly enforced in `build_alt_spread_parlay()`. CLAUDE.md matches code. ✓

### SGP sizing
**Location:** engine/sgp_builder.py ~lines 711–744

CLAUDE.md says: "0.25u default / 0.50u premium (avg_wp≥0.70 AND cohesion≥0.55 AND avg_edge≥0.035)"

**Actual code (L8 update)**: the `avg_wp≥0.70` criterion was replaced by a Gaussian copula EV margin check:
```python
if _copula_joint - parlay_implied >= 0.10:
    return SGP_SIZE_PREMIUM  # 0.50u
```
`cohesion≥0.55` and `avg_edge≥0.035` still required as prerequisites. CLAUDE.md is outdated (see Track L).

### F-6 (MEDIUM) — SGP copula EV threshold uses vigged book-implied, not vig-free

```
TRACK: F
FILE: engine/sgp_builder.py
LINE: ~738–741
SEVERITY: MEDIUM
N: N/A
ISSUE: The copula EV margin check compares _copula_joint (model no-vig) against
parlay_implied (vigged, book-implied). Per code comment at ~line 738, "~3-8pp of the 10pp
gap is expected vig removal, not model alpha." This means only 2–7pp of the 10pp threshold
is genuine model edge. The gate is more permissive than intended, systematically awarding
the 0.50u bump when true alpha may be only 2–7pp.
IMPACT: At 0.25u stakes, overbet is ~0.03–0.05u extra. Gate fires correctly directionally
but the threshold is set against a contaminated baseline.
FIX: Compare _copula_joint against parlay_no_vig_implied (de-vigged leg probs multiplied)
instead of vigged implied. Or raise threshold to 0.15–0.18 to account for expected vig
component. Gate this until 100 SGP slips are scored.
```

### F-7 (MEDIUM) — SGP units excluded from session 12u cap display

```
TRACK: F
FILE: engine/run_picks.py
LINE: ~5606–5607
SEVERITY: MEDIUM
N: N/A
ISSUE: SGP units are posted via a separate flow and not included in the session-level
apply_caps() 12u check. On a day where a 0.50u SGP fires AND the premium card runs
near-capped, actual daily exposure can be up to 12.5u while the sanity display shows ≤12u.
The next sport run reads the log and compensates, but within-session the cap display is off.
IMPACT: Worst-case overage: 0.50u above stated 12u cap. Rare and minor.
FIX: Include SGP stake in total_u_all computation at ~line 5613 by reading pick_log.csv for
SGP picks already logged today before computing the display.
```
