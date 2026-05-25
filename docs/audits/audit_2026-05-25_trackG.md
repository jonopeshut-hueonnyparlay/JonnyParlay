# Audit 2026-05-25 — Track G: Portfolio & Correlation Risk

Auditor: Claude Sonnet 4.6 (automated)
Scope: engine/run_picks.py, engine/sgp_builder.py — same-game correlation, SGP leg correlation, concurrent run safety

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

### G-3 (HIGH) — sgp_builder NB_R["3PM"] diverges from run_picks.py

```
TRACK: G
FILE: engine/sgp_builder.py
LINE: ~79
SEVERITY: HIGH
N: N/A
ISSUE: sgp_builder.py has NB_R["3PM"] = 2.1 ("empirical per-game r, Research Brief 5,
2026-05-02"). run_picks.py (updated 2026-05-25) has NB_R["3PM"] = 9.15 (1246 player-seasons,
avg(var/mu)=1.1486). Code comment in sgp_builder says "Mirrors NB_STATS/NB_R in run_picks.py
— keep in sync" but they are OUT OF SYNC by a factor of 4.35.
r=2.1 means far more variance than r=9.15. 3PM probability estimates differ significantly
between the two systems. If per-game r is intentionally different from player-season r,
the comment is actively misleading.
IMPACT: 3PM SGP leg probabilities are miscalibrated relative to run_picks.py. Cohesion
scores and sizing gate derived from 3PM legs use inconsistent volatility assumptions.
FIX: Either (a) document explicitly that sgp_builder uses per-game r values (different
methodology — intentional) and fix the comment; or (b) unify both to the same value
and methodology. Requires a decision on whether per-game vs per-season r is correct
for single-game SGP legs.
```

### G-4 (HIGH) — AST uses wrong distribution in sgp_builder.py

```
TRACK: G
FILE: engine/sgp_builder.py
LINE: ~71 (POISSON_STATS), ~65–70 (SIGMA)
SEVERITY: HIGH
N: N/A
ISSUE: In sgp_builder.py: AST is in POISSON_STATS and falls through to Normal distribution
via SIGMA["AST"] = {"mult": 0.45, "min": 1.3}. In run_picks.py (updated 2026-05-25):
AST was moved from POISSON_STATS to NB_STATS with NB_R["AST"] = 9.68 (avg var/mu=1.2539
from 1395 player-seasons). The sgp_builder was NOT updated.
IMPACT: AST SGP leg probabilities are computed with the wrong distribution. Normal
distribution under-models AST tail variance vs NB(r=9.68). SGP legs on AST are
systematically miscalibrated vs the same calculation in run_picks.py.
FIX: In sgp_builder.py: (1) Remove AST from POISSON_STATS. (2) Add "AST" to NB_STATS.
(3) Add "AST": 9.68 to NB_R. (4) Remove AST from SIGMA dict.
This is a direct sync of the 2026-05-25 run_picks.py update.
```

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
