# Audit 2026-05-25 — Track G: Portfolio & Correlation Risk (v2 — post REB/AST→NB + SIGMA update)

Auditor: Claude Sonnet 4.6 (fresh session, post-2026-05-25 changes)
Scope: engine/run_picks.py, engine/sgp_builder.py — same-game correlation, SGP leg correlation, concurrent run safety
Re-audited: G-3 and G-4 confirmed FIXED. Two new findings (G-7, G-8) added from fresh read.

---

## G1. Same-Game Correlation

### Per-game cap — primary/bonus card
`max_per_game=2` (default, R7 rule) enforced in `apply_soft_rules_premium()` and `apply_caps()`. Two picks from the same game can appear on the 3-pick card if `--max-per-game 5` is passed for thin slates. By design.

### LONGSHOT_MAX_PER_GAME
`LONGSHOT_MAX_PER_GAME = 2` (~line 187). Applies ONLY to `build_safest6_parlay()` (longshot). There is NO per-game cap that unifies across run_types. By design — separate products with separate enforcement.

### G-1 (MEDIUM) — No cross-run-type exposure tracking

```
TRACK: G
FILE: engine/run_picks.py
LINE: ~5006–5016, ~3627
SEVERITY: MEDIUM
N: N/A
ISSUE: A player on the primary card (e.g., Tatum Over 27.5 PTS) is NOT blocked from
appearing in a daily_lay leg (BOS -6.5 alt spread). The daily_lay builder operates on
team-level game lines and never cross-checks against prop picks on the primary card.
Additionally, a player's same-game different-stat pick (e.g., primary: Tatum Over 27.5 PTS;
bonus: Tatum Over 7.5 REB) is not blocked by the bonus dedup key because the stat differs.
IMPACT: Subscriber concentration risk. If Tatum's team is in a daily_lay leg AND he's on
the primary card, both channels lose together on a bad game. No financial ruin risk (units
are small), but disclosed diversification is affected.
FIX: (Low priority) Track (player, game) pairs across run_types in bonus eligibility filter.
Add a comment in build_alt_spread_parlay about this intentional design choice.
```

### G-2 (MEDIUM) — Bonus pick size not reserved in same-session 12u cap

```
TRACK: G
FILE: engine/run_picks.py
LINE: ~6104, ~6119, ~6473
SEVERITY: MEDIUM
N: N/A
ISSUE: The 12u daily cap is read before apply_caps() runs, used to constrain premium picks,
then premium is logged. The bonus drop (~6473) adds another 0.50–1.25u AFTER the cap
enforcement. If premium fills 11.5u and a bonus fires, total logged for the session is
12.0–12.75u. The bonus unit is not reserved in the same-session apply_caps() enforcement.
IMPACT: Up to 1.25u over the 12u daily cap within a single session. Caught by subsequent
sport runs (bonus units land in pick_log and are read by the next _units_bet_today() call),
but not within the same run.
FIX: Pass bonus_size_est (1.0u reserve) to apply_caps() so premium is capped at 11u,
leaving headroom for bonus. Or re-check 12u cap before posting in post_extras_to_discord().
```

---

## G2. SGP Leg Correlation

### SGP composite probability — correctly uses copula (GOOD)
`_copula_joint_prob()` implements a Gaussian copula with pairwise ρ values. Full Monte Carlo (4000 samples) on final chosen SGP. Equicorrelation approximation used during 91k combo search. NOT a simple product. Approved.

### G-3 — CLOSED (was HIGH) — sgp_builder NB_R["3PM"] diverges from run_picks.py

**STATUS: FIXED** by 2026-05-25 changes. sgp_builder.py line 79 now reads:
`"3PM": 9.15,  # recalibrated 2026-05-25: 1246 player-seasons, avg(var/mu)=1.1486 (was 2.1/12.3)`
Both files now use NB_R["3PM"] = 9.15 with the same methodology. **No further action needed.**

### G-4 — CLOSED (was HIGH) — AST uses wrong distribution in sgp_builder.py

**STATUS: FIXED** by 2026-05-25 changes. Fresh-session verification confirms sgp_builder.py:
- `POISSON_STATS: set = set()` (empty — AST and REB both moved out)
- `NB_STATS = {"3PM", "AST", "REB", "BLK", "STL"}` (AST and REB added)
- `NB_R["AST"] = 9.68` (calibrated 2026-05-25)
- `SIGMA["AST"]` removed from sgp_builder.py SIGMA dict
AST now routes to NB(r=9.68) in both run_picks.py and sgp_builder.py. **No further action needed.**

### G-5 (MEDIUM) — SGP win_prob not stored in pick_log (blocks calibration)

```
TRACK: G
FILE: engine/run_picks.py + engine/sgp_builder.py
LINE: pick_log.csv win_prob field for sgp rows
SEVERITY: MEDIUM
N: 36 scored SGP picks
ISSUE: SGP picks in pick_log.csv have blank win_prob field. The Gaussian copula joint
probability is not stored anywhere in the log. Actual SGP WR is 27.8% (10/36 graded),
model independence product predicts 30.9% — 3.1pp over-prediction, consistent direction
but at n=36 not statistically significant. Cannot measure copula calibration vs actual WR
because the copula value is never logged.
The SGP Platt calibration gate (42/100 slips) is gated, so no correction is deployed yet.
IMPACT: Zero ability to diagnose SGP model calibration until copula probability is logged.
FIX: Store copula joint probability in win_prob field of SGP pick_log rows at the time
of logging in _log_sgp(). This unblocks calibration analysis and eventual Platt SGP gate.
```

---

## G3. Concurrent Run Race Conditions

### filelock coverage — CORRECT

All write paths in run_picks.py use `_pick_log_lock(log_path)`:
- `log_picks()` (~line 3964) ✓
- `_log_bonus_pick()` (~line 5110) ✓
- `log_daily_lay_pick()` (~line 4671) ✓
- `log_longshot_pick()` (~line 4853) ✓
- `_units_bet_today()` (~line 4958) ✓ (read also locked)
- `sgp_builder._log_sgp()` (~line 1011) ✓ (imports from run_picks)
- `capture_clv.write_closing_odds()` (~line 641) ✓ (separate FileLock)

`filelock` is a hard import dependency — fails explicitly on missing package. No silent fallback. **No file corruption risk from concurrent writes.**

### G-7 (MEDIUM) — sgp_builder.py SIGMA["PTS"] min=4.5 vs run_picks.py min=5.0

```
TRACK: G
FILE: engine/sgp_builder.py
LINE: ~66
SEVERITY: MEDIUM
N: N/A
ISSUE: sgp_builder.py SIGMA["PTS"] = {"mult": 0.35, "min": 4.5}. run_picks.py raised
SIGMA["PTS"] min from 4.5 to 5.0 on 2026-05-25 (confirmed at ~line 263). sgp_builder.py
was NOT updated. Code comment: "Mirrors NB_STATS/NB_R in run_picks.py — keep in sync."
At proj=4.5 and line=4.5: run_picks sigma=max(4.5*0.35, 5.0)=5.0 (floored);
sgp_builder sigma=max(4.5*0.35, 4.5)=4.5 (floored). Different sigma → different win_prob
for the same PTS prop in SGP vs single-stat contexts. Gap narrows for typical projections
(proj≥14.3 puts both above their respective floors) but is non-zero for low-projection PTS.
IMPACT: PTS SGP legs at low projections (proj<14.3) have slightly lower sigma in sgp_builder
(tighter dist → higher win_prob for on-line props). Directionally over-optimistic for low-PTS SGPs.
FIX: Update sgp_builder.py SIGMA["PTS"]["min"] = 5.0 to match run_picks.py.
```

### G-8 (LOW) — size_sgp Gate 1 docstring says "≥10pp margin" but code checks any positive margin

```
TRACK: G
FILE: engine/sgp_builder.py
LINE: ~712–742
SEVERITY: LOW
N: N/A
ISSUE: size_sgp() docstring (line ~719) says "copula_ev_margin ≥ 0.10 — copula joint
probability exceeds the parlay's implied probability by ≥ 10 percentage points."
Actual Gate 1 code (M8, line ~742):
    if _copula_joint <= parlay_implied:
        return SGP_SIZE_DEFAULT
This is a check for ANY positive EV margin, not ≥10pp. The binding constraint for premium
sizing is Gate 2: copula_joint - no_vig_independent >= 0.015 (≥1.5pp correlation lift
above no-vig independence baseline). The "≥10pp" threshold described in the docstring
was the L8 design; M8 replaced it with two-gate logic.
IMPACT: Docstring is actively misleading when reasoning about premium sizing. Anyone reading
the docstring to understand sizing threshold will apply the wrong check. CLAUDE.md inherits
the same stale description (see L-3).
FIX: (1) Update docstring: "Gate 1: any positive EV vs vigged parlay (copula_joint >
parlay_implied). Gate 2: correlation adds ≥1.5pp above no-vig independence baseline."
(2) Update CLAUDE.md SGP entry to describe M8 two-gate logic.
```

### G-6 (MEDIUM) — TOCTOU on 12u daily cap between near-concurrent sport runs

```
TRACK: G
FILE: engine/run_picks.py
LINE: ~6104 (_units_bet_today), ~6119 (apply_caps), ~6199 (log_picks)
SEVERITY: MEDIUM
N: N/A
ISSUE: The read-modify-write for the 12u daily cap is NOT atomic across the full sequence.
Sequence: (1) _units_bet_today() reads pick_log inside filelock → lock released →
(2) caps computed in memory → (3) log_picks() acquires lock again and writes.
If two terminal windows are open and both start within the same ~30 second window,
both could read "0u used today" simultaneously and collectively exceed 12u.
The process-level run_picks.lock (timeout=0 at ~line 5748) DOES prevent truly
simultaneous starts — it kills the second process immediately. The race is only
exploitable if the process lock expires before completion, which should not happen.
IMPACT: Effectively zero risk in practice due to process-level lock. But the lock
is a defense-in-depth measure, not an atomic operation on the cap itself.
FIX: Acceptable as-is. The process lock is the correct defense. Add comment documenting
why the TOCTOU is not a live risk: "process-level run_picks.lock prevents concurrent execution."
```
