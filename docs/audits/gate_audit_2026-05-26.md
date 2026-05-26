# Gate / Rule / Filter Audit — 2026-05-26

Full catalog and verification pass on every gate, rule, and filter in `engine/run_picks.py`.
Triggered by: today's runs surfacing Castle (T1B, 51.5% WP not logged), game lines not logged,
and Bailey Falter (80.8% WP blocked by G7).

Severity: **C** = Critical (bug/dead code) | **H** = High (stale/weak data, meaningful impact)
**M** = Medium (no data backing, intuition only) | **L** = Low/defer

---

## CRITICAL

### C1 — G13B is dead code ahead of G_HRR_DISABLED
**File:** `run_picks.py:993–1005`

```python
# G13B fires for low-WP HRR picks (line 993–1000)
if stat == "HRR":
    if line <= 0.5 and prob < 0.58:
        return False, "G13B"
    if line > 0.5 and prob < 0.65:
        return False, "G13B"

# G_HRR_DISABLED catches everything that passed G13B (line 1002–1005)
if stat == "HRR":
    return False, "G_HRR_DISABLED"
```

G13B runs before G_HRR_DISABLED. Low-WP HRR picks return "G13B"; high-WP HRR picks fall through
to "G_HRR_DISABLED". Result: the gate breakdown shows "G13B" for some HRR picks, creating the
false impression that HRR is partially allowed. Since HRR is fully killed, G13B should be removed —
let G_HRR_DISABLED handle all HRR and be the single source of truth.

**Fix:** Delete G13B block (lines 993–1000). Update docstring.

---

### C2 — `_is_soft_o05` references dead stats (HRR, TB) in G2
**File:** `run_picks.py:1052–1056`

```python
_is_soft_o05 = (stat in ("HRR", "TB", "HITS") and line <= 0.5 and direction == "over")
g2_threshold = 0.28 if _is_soft_o05 else 0.20
if edge >= g2_threshold:
    return False, "G2"
```

HRR is killed at G_HRR_DISABLED (line 1004) before reaching G2. TB is killed at G_TB_DISABLED
(line 1009) before reaching G2. Neither stat can ever reach this code. Only HITS legitimately
benefits from the 0.28 threshold. The HRR/TB references create false confidence and should be removed.

**Fix:** Change `_is_soft_o05` to `(stat == "HITS" and line <= 0.5 and direction == "over")`.

---

## HIGH

### H1 — PICK_SCORE_TIER_MULT T1=0.90× may be stale post-gate-additions
**File:** `run_picks.py:437–445`

```python
# T2 is the reference tier (best empirical win rate, 61.1% vs T1=45.1% at n=51/54).
PICK_SCORE_TIER_MULT = {"T1": 0.90, "T1B": 0.93, "T2": 1.00, "T3": 0.95, "KILLSHOT": 1.00}
```

T1's 0.90× multiplier was set when T1 WR was 45.1% (n=51). That data pool included the exact
sub-classes of picks that G8B (AST over ≤4.5), G8C (SOG under ≤3.5), G8D (3PM over ≤1.5)
were later added to eliminate. Post-gate T1 WR is unknown but meaningfully higher. The 0.90×
multiplier depresses T1 pick scores vs T2 picks of identical WP/edge, affecting which picks win
the open card slot under R8. This may be systematically deprioritizing the best current T1 picks.

Also notable: T3 = 0.95× > T1 = 0.90×. A T3 pick outscores a T1 pick with the same WP/edge.
T3 requires 6% min edge vs T1's 3%, so this is partially justified — but it should be documented.

**Action needed:** Pull current T1/T1B WR from pick_log.csv (post-G8B/C/D date), compare to T2.
If T1 WR ≥ T2 WR, raise T1 multiplier to at minimum 0.95×.

---

### H2 — K NB r=5.0 is provisional and undocumented
**File:** `run_picks.py:306`

```python
"K": 5.0,  # PROVISIONAL — undocumented estimate; bimodal (early hook vs deep start).
```

The r-value for MLB strikeouts has never been calibrated from data. Every MLB K over bet
(at line ≥6.0) uses this provisional distribution. Practical impact is limited by G_K_MIN_LINE
(line ≥6.0 only) and the fact that K unders are fully banned, but it means K over probabilities
are computed from a guess. Should use `engine/nb_calibrate.py` on MLB pitcher game logs.

**Action needed:** Run nb_calibrate.py on pitcher game logs from projections.db or MLB Stats API.
Gate: defer to next full MLB audit when sufficient K over pick history exists (suggest n=50+).

---

### H3 — Small-sample gates (G8B, G8C, G8D, G13)
All four were added on small samples. They may be correct but should be explicitly flagged for
recalibration as the pick log accumulates.

| Gate | Sample | Condition blocked | Claim |
|------|--------|-------------------|-------|
| G8B | n=8 | AST over ≤4.5 (NBA) | 0–5 record vs 2–1 at ≥5.5 |
| G8C | n=14 | SOG under 3.1–3.5 | 42.9% actual vs 63.7% model |
| G8D | n=16 | 3PM over ≤1.5 | 50.0% actual vs 70.4% model |
| G13 | n=4 | Sub-50% WP any stat | "proven 1–3 record" |

G13 is the most extreme: blocking all sub-50% picks based on 4 observations. The rule is
probably correct (sub-50% WP bets should lose at juice), but the empirical citation is nearly
meaningless at n=4. The gate is justified on first principles, not the sample.

**Action needed:** Add recalibration checkpoints in CLAUDE.md. At n=30+ per gate, pull actual WR
from pick_log.csv and confirm or adjust thresholds.

---

### H4 — NBA TEAM_TOTAL over block is provisional (n=11)
**File:** `run_picks.py` (search: TEAM_TOTAL over block / 45.5%)

"45.5% WR, n=11, −11pp gap — provisional; revisit at n=30"

The block was added at n=11. 45.5% on 11 picks is statistically noise — at n=11, even a
true 55% WR process has a ~15% chance of showing ≤45% WR. BAL TT O4.5 today (50.3% WP, 6.7%
edge) and NYY TT O5.5 (50.0% WP, 5.3% edge) were blocked. Both had marginal WPs anyway so
the practical impact today was minimal. But the gate is blocking based on insufficient data.

**Action needed:** Count TEAM_TOTAL over picks in pick_log.csv. Remove block when n=30+.

---

### H5 — WNBA COMBO ρ unreliable (n=9)
**File:** `run_picks.py:342–345`

```python
# WARNING: n=9 players is too small for reliable correlation estimation.
# SE ≈ 0.055 per pair, so the near-zero values (AST pairs) could be noise or real WNBA structure.
```

Explicitly flagged in code. Near-zero ρ means WNBA combo props (PRA, PA, RA) treat components
as independent, inflating combo probabilities vs reality if true ρ > 0. Limited practical impact
right now (WNBA shadow mode, few combo picks), but worth noting for go-live.

**Action needed:** Defer until WNBA sample grows. Refit at n=500+ player-games.

---

## MEDIUM

### M1 — G7 absolute -150 threshold has no WP/edge bypass
**File:** `run_picks.py:915–917`

```python
if odds <= -150:
    return False, "G7"
```

Today's example: Bailey Falter OUTS over 8.5 at -160, 80.8% WP, 23.9% edge — blocked.
The rationale for G7 is sound (excessive vig). But G7b provides a partial bypass at -140 to -149
(edge ≥ 9% gets through). There is no equivalent bypass between -150 and ~-180 for very
high-conviction picks.

The counter-argument for keeping G7 absolute: if a pick is at -160, the market thinks it's
~61% (vig-free ~59%). Our model at 80.8% is 22pp above market. In liquid markets that gap
is almost always model error. In soft markets (SaberSim OUTS projections), it's plausible.

Today's Falter case: the user believes it's a bullpen game and SaberSim's 3.84 IP projection
may overstate his outing. If so, G7 is correctly blocking a model-error edge. If the projection
is accurate, G7 is leaving real edge on the table.

**No code change recommended** without data. Flag for manual review when high-WP picks hit G7.
Add a note to top-filtered output showing WP for G7 blocks (already shown in today's output).

---

### M2 — G7b threshold (9% edge at -140 to -149) not calibrated
**File:** `run_picks.py:919–921`

```python
if -149 <= odds <= -140 and edge < 0.09:
    return False, "G7b"
```

The 9% edge requirement in the -140 to -149 juice zone was set without data. At -145 implied
prob ≈ 59%, so a pick needs to win 65%+ to have 9% edge. This is a reasonable bar but it's
a guess. How many picks are passing G7b vs failing it? Not tracked in any report.

**Action needed:** Add G7b pass/fail tracking to analyze_picks.py or the gate breakdown.
Recalibrate at n=30+ G7b-range picks.

---

### M3 — G10 (under ≤2.5 + edge < 0.08) not calibrated
**File:** `run_picks.py:1066–1068`

```python
if direction == "under" and line <= 2.5 and edge < 0.08:
    return False, "G10"
```

"Low-line under fragility" — no data cited. The 8% edge floor at tight lines is intuition.
Today it blocked 3 NBA picks. Whether those picks would have won at a higher rate than 50%
is unknown.

**Action needed:** Pull G10 pick outcomes from pick_log.csv (picks that would have passed G10
but failed due to edge < 8%). Add to next calibration run.

---

### M4 — G14 threshold (0.10σ) is a very low bar
**File:** `run_picks.py:1011–1037`

```python
if _z < 0.10:
    return False, "G14"
```

G14 requires the projected value to clear the line by only 10% of one standard deviation. For a
T2 PTS pick at proj=24.0 with SIGMA=8.4 (24 × 0.35), the line must be ≤ 23.16 (over) or ≥ 24.84
(under) to pass. That's a 0.84 unit clearance. Very liberal — allows picks where proj is almost
exactly at the line.

The rationale is that Poisson/NB stats are exempt (they handle boundary cases correctly), so G14
only applies to Normal stats where the distribution is wider. Still, 0.10σ seems low. 0.25σ would
require 2.1 units clearance on the same PTS example, filtering out borderline model convictions.

**Action needed:** Pull G14-failing vs G14-passing WRs from pick_log.csv. Is there meaningful
win rate difference at various z-score thresholds? Defer until n=50+ G14-adjacent picks.

---

### M5 — G4, G5 are sanity gates with no empirical backing
**File:** `run_picks.py:1058–1064`

- G4: `line ≤ 2.5 AND prob > 0.75` — "binary-adjacent lines with extreme conviction are fragile"
- G5: `odds > 0 AND prob > 0.65` — "plus odds on high-conviction picks = model/market disconnect"

Both fire rarely. Both are directionally reasonable. Neither has been verified against pick outcomes.

**Low priority.** Keep as-is unless they start blocking obvious good picks.

---

### M6 — G1 fires in a narrow, unintuitive range
**File:** `run_picks.py:1048–1050`

```python
if prob >= 0.70 and odds > -200 and edge < 0.05:
    return False, "G1"
```

For edge < 0.05 with prob ≥ 0.70, the market implied probability must be ≥ 0.65 (odds ≤ ~-186).
So G1 only fires for odds between -186 and -200 with 70%+ model WP. This is a tiny slice of
the universe. The gate is fine but it may never fire in practice.

**Action needed:** Check if G1 has ever appeared in gate breakdown output. If not, document it
as a theoretical guard and reduce comment noise.

---

## GATES THAT VERIFIED CLEAN

The following gates have clear rationale, correct logic, and no implementation issues:

| Gate | Verdict |
|------|---------|
| G3 (missing side) | Clean. Structural necessity. |
| G8 (binary fragility at ≤1.5) | Clean. Logic correct, applies to right stats. |
| G8B (AST over ≤4.5) | Correct logic; small sample flagged above (H3). |
| G8C (SOG under ≤3.5) | Correct logic; small sample flagged above (H3). |
| G8D (3PM over ≤1.5) | Correct logic; small sample flagged above (H3). |
| G_WNBA_OPEN | Clean. Structural. |
| G_WNBA_EDGE | Clean. Edge floor + dampener well-documented. |
| G_K_NO_UNDERS | Clean. SaberSim IP bias well-established. |
| G_K_MIN_LINE (≥6.0) | Clean. Directionally correct. |
| G_OUTS_UNDER | Clean. Softened correctly to WP≥0.60 exception. |
| G_HA_DIR | Clean. T1B unders-only definition. |
| G9 (3% edge floor) | Clean. Universal minimum. |
| G13 (sub-50% WP) | Clean logic; tiny sample citation (H3). |
| G_HRR_DISABLED | Clean. Correct kill. G13B should be removed (C1). |
| G_TB_DISABLED | Clean. Correct kill. |
| G14 (projection clearance) | Logic correct; threshold may be too liberal (M4). |
| G15 (high-CV 3PM) | Clean. No-op on SaberSim runs; correct for custom engine. |
| G2 (20% edge ceiling) | Clean logic; HRR/TB dead refs in _is_soft_o05 (C2). |
| GG1 (game line 10% ceiling) | Clean. Right for liquid markets. |
| GG2 (proj deviation > 1.5σ) | Clean. Correct SPREAD sign convention. |
| GG3 (non-positive edge) | Clean. |
| GG4 (missing side) | Clean. |
| GG5 (dog-cover spread ban) | Clean. |
| GG6 (proj wrong side of line) | Clean. |
| R6 (max 2 overs on card) | Clean. |
| R7 (max 2 picks per game) | Clean. |
| R8 (T1/T1B slot reservation) | Clean. |
| R9 (over forcing) | Clean. |
| R10 (per-stat dedup) | Clean. |
| R_COMBO (combo correlation cap) | Clean. |
| G12 (pitcher direction cap) | Clean. |
| R12 (cooldown) | Clean. |
| MIN_WIN_PROB = 0.55 | Clean. Well-documented empirical basis (n=61). |
| MIN_PICK_SCORE = 25 | Clean. |
| MIN_OVER_SCORE = 40 | Clean. Documented. |
| VAKE_BASE / sizing | Clean. |
| KILLSHOT gate (all 5 criteria) | Clean. |

---

## SUMMARY TABLE

| ID | Severity | Issue | Fix effort |
|----|----------|-------|------------|
| C1 | Critical | G13B dead code before G_HRR_DISABLED | Small — delete 7 lines |
| C2 | Critical | `_is_soft_o05` includes dead HRR/TB refs | Small — 1 line change |
| H1 | High | PICK_SCORE_TIER_MULT T1=0.90× may be stale post-G8B/C/D | Data pull needed |
| H2 | High | K NB r=5.0 provisional/undocumented | nb_calibrate.py run needed |
| H3 | High | G8B/G8C/G8D/G13 small samples (n=4–16) | Monitoring only |
| H4 | High | NBA TEAM_TOTAL over block provisional (n=11) | Count picks; remove at n=30 |
| H5 | High | WNBA COMBO ρ unreliable (n=9) | Defer to WNBA go-live |
| M1 | Medium | G7 absolute cutoff blocks high-edge picks at -150 to -160 | No change; manual review |
| M2 | Medium | G7b 9% threshold not calibrated | Add tracking |
| M3 | Medium | G10 8% floor not calibrated | Pull pick outcomes |
| M4 | Medium | G14 0.10σ threshold very low | Defer; need data |
| M5 | Medium | G4/G5 no empirical backing | Low priority; keep |
| M6 | Medium | G1 may never fire | Document |

---

## IMMEDIATE FIXES (C1 + C2)

Both C-level issues are 1–3 line changes each. No behavior change on live picks (HRR/TB
are fully disabled; the fixes are cleanup only). Recommend doing these together in one commit.

**STATUS: CLOSED 2026-05-26** — committed in 89c9605.

---

## HIGH FINDINGS — RESOLUTION (2026-05-26)

Data pulled from pick_log.csv: 185 graded picks (primary/bonus only, excluding sgp/longshot/daily_lay).

### H1 — PICK_SCORE_TIER_MULT confirmed accurate
**STATUS: CLOSED — no code change.**

| Tier | n | Win Rate | Avg Edge |
|------|---|----------|----------|
| T1   | 58 | 46.55% | 13.1% |
| T1B  | 30 | 53.33% | 11.1% |
| T2   | 60 | 61.67% | 11.3% |
| T3   | 32 | 53.12% | 14.6% |

T1 is still at 46.55% — essentially identical to the 45.1% the 0.90× was calibrated on.
The multiplier is NOT stale. T2 genuinely outperforms T1 by 15pp.

T1 breakdown:
- AST: 42.86% WR (n=14)
- SOG: 47.62% WR (n=42)
- HRR: 50.00% WR (n=2 — irrelevant, fully disabled)

Both AST and SOG are below juice break-even (~52.4% at -110). Note: most of this data
is pre-G8B/G8C (gates added 2026-05-23). Post-gate T1 WR will need re-evaluation at n=30+
post-gate picks.

**Monitoring checkpoint:** When n=30 T1 picks post-2026-05-23, re-pull WR. If T1 ≥ 55%,
raise PICK_SCORE_TIER_MULT["T1"] to 0.95. If T1 < 50%, consider removing T1 reserved slots.

---

### H2 — K NB r=5.0: calibration requires MLB pitcher game logs
**STATUS: DEFERRED — data infrastructure gap.**

No MLB pitcher game logs exist in `projections.db` (NBA-only). No graded K picks in
`pick_log.csv` or `pick_log_mlb.csv` (0 K rows in both). `nb_calibrate.py` does not support
MLB stats and explicitly documents K as a backlog item.

Limited practical impact: K unders banned (G_K_NO_UNDERS), K overs require line ≥6.0
(G_K_MIN_LINE). The provisional r=5.0 only affects K overs at ≥6.0 lines.

**Gate:** Build MLB pitcher game log fetcher (statsapi endpoint exists via mlb_starter_fetcher.py
infrastructure). Adapt nb_calibrate.py for MLB. Defer until dedicated MLB data sprint.

---

### H3 — Small-sample gates: monitoring thresholds set
**STATUS: MONITORING — no code change.**

Cannot pull WRs on blocked picks (they don't appear in pick_log). Gates are verified
directionally correct from the data that did come through (T1 AST underperformance confirms
G8B is appropriate). Post-gate pick data will accumulate going forward.

Recalibration thresholds:
| Gate | Condition blocked | Recalibrate when |
|------|-------------------|------------------|
| G8B | AST over ≤4.5 (NBA) | n=30 post-gate AST picks in any direction |
| G8C | SOG under ≤3.5 | n=30 post-gate SOG picks |
| G8D | 3PM over ≤1.5 | n=30 post-gate 3PM picks |
| G13 | Sub-50% WP any stat | n=30 sub-50% WP picks (requires shadow run or --no-cap) |

Note: verifying these gates properly requires either a shadow run with gates disabled,
or reviewing the "top filtered picks" output accumulated across many sessions.

---

### H4 — NBA TEAM_TOTAL over block: maintain
**STATUS: MAINTAINED — not at n=30 threshold.**

Current data: 11 TEAM_TOTAL over picks, 5W/6L = 45.45% WR. Confirmed n=11 as of 2026-05-26.
Below break-even. Block is statistically appropriate even if the sample is small.
TEAM_TOTAL unders: 2/2 (100%, n=2 — too small to act on).

**Gate for removal:** n=30 TEAM_TOTAL over picks. Run `analyze_picks.py --stat TEAM_TOTAL`
to monitor. If WR ≥ 55% at n=30, remove the over block from run_picks.py.

---

### H5 — WNBA COMBO ρ: deferred
**STATUS: DEFERRED — insufficient data.**

n=9 players / 336 games. SE ≈ 0.055 per pair. Near-zero values on AST pairs could be real
WNBA structure or noise. No action until WNBA shadow reaches n=500+ player-games.
WNBA is in shadow mode; combo picks are rare in practice.

**Gate:** Refit COMBO_RHO_WNBA when WNBA shadow DB reaches 500+ player-games.

---

## FINAL STATUS

| ID | Severity | Resolution |
|----|----------|------------|
| C1 | Critical | **CLOSED** — deleted G13B (commit 89c9605) |
| C2 | Critical | **CLOSED** — fixed _is_soft_o05 (commit 89c9605) |
| H1 | High | **CLOSED** — multiplier confirmed accurate; monitor at n=30 post-gate |
| H2 | High | **DEFERRED** — needs MLB pitcher game log infrastructure |
| H3 | High | **MONITORING** — thresholds set; re-evaluate each gate at n=30 |
| H4 | High | **MAINTAINED** — n=11 at 45.45% WR; remove block at n=30 |
| H5 | High | **DEFERRED** — refit WNBA COMBO ρ at n=500+ player-games |
| M1–M6 | Medium | See resolutions below |

---

## MEDIUM FINDINGS — RESOLUTION (2026-05-26)

### M1 — G7 absolute -150 threshold
**STATUS: CLOSED — no change, manual awareness.**

Today's Falter case (-160, 80.8% WP, 23.9% edge) is the canonical example. G7 is blunt by
design: picks at -150+ odds in liquid markets are almost always model overclaiming edge.
The Falter case is also a potential SaberSim projection error (bullpen game, IP overstated).
No WP/edge bypass added — the gate should remain absolute. Flag for manual review when
high-WP picks appear in the G7 top-filtered output.

---

### M2 — G7b threshold (9% edge at -140 to -149)
**STATUS: MONITORING — weak data suggests threshold may be too low.**

Data: n=32 picks at odds -140 to -149 (all passed G7b, meaning edge ≥ 9%). WR = 17/32 = 53.1%.
Break-even at average odds of ~-143 is ~59%. These picks are losing at juice.

The model is overclaiming edge by ~6pp in this juice zone. However n=32 is marginal — the 95% CI
on 53.1% WR includes breakeven. No threshold change yet.

**Monitoring checkpoint:** At n=50 G7b-zone picks, if WR < 56%, raise G7b threshold from 9% to 12%.
If WR < 53% at n=50, consider extending G7 to -140 (kill the entire zone).

---

### M3 — G10 threshold (8% edge at under ≤2.5)
**STATUS: MONITORING — mixed results, no change indicated.**

Data: n=42 picks at under ≤2.5 (all passed G10, edge ≥ 8%). WR = 22/42 = 52.4%.

Split by odds direction:
- Negative-odds (mostly SOG 2.5 unders): ~62% WR — profitable at juice
- Plus-odds (mostly 3PM 0.5/1.5 unders): ~43% WR — losing

The 8% floor is working for negative-odds unders but not screening out the losing plus-odds
3PM unders. The correct fix may not be raising G10's edge floor but rather reviewing whether
plus-odds under ≤2.5 picks need a separate gate (e.g., block 3PM under ≤1.5 at plus odds,
analogous to G8D on the over side).

**Monitoring checkpoint:** At n=60 G10-zone picks, re-split by stat and odds direction.
If 3PM under ≤1.5 at plus odds continues losing, add a stat-specific gate.

---

### M4 — G14 threshold (0.10σ)
**STATUS: DEFERRED — need n=50+ G14-adjacent picks.**

Cannot calibrate without data on picks projected very close to the line. Current threshold
allows picks where proj clears line by only 0.10σ. Whether 0.25σ would materially improve
win rates is unknown. Defer until pick log accumulates sufficient G14-adjacent cases.

---

### M5 — G4/G5 no empirical backing
**STATUS: CLOSED — keep as-is.**

G4 (line ≤2.5 + prob >75%) and G5 (plus odds + prob >65%) are sanity gates that rarely
fire. Both are directionally correct. Neither has produced a false positive visible in output.
No change until one of them blocks an obvious good pick.

---

### M6 — G1 may never fire
**STATUS: CLOSED — documented as theoretical guard.**

G1 fires when prob ≥ 0.70 AND odds > -200 AND edge < 0.05. For edge < 5% with WP ≥ 70%,
the market implied prob must be ≥ 65% (odds ≈ -186). The window is -186 to -200 only.
In practice this fires when a pick has 70%+ model WP but the market has already priced it
near -190 and edge is thin. This is a valid guard for a real (if rare) scenario.
No change — keep as theoretical protection.

---

## FINAL STATUS (COMPLETE)

| ID | Severity | Resolution |
|----|----------|------------|
| C1 | Critical | **CLOSED** — deleted G13B (commit 89c9605) |
| C2 | Critical | **CLOSED** — fixed _is_soft_o05 (commit 89c9605) |
| H1 | High | **CLOSED** — multiplier confirmed accurate; monitor at n=30 post-gate |
| H2 | High | **DEFERRED** — needs MLB pitcher game log infrastructure |
| H3 | High | **MONITORING** — thresholds set; re-evaluate each gate at n=30 |
| H4 | High | **MAINTAINED** — n=11 at 45.45% WR; remove block at n=30 |
| H5 | High | **DEFERRED** — refit WNBA COMBO ρ at n=500+ player-games |
| M1 | Medium | **CLOSED** — no change; manual awareness on G7 top-filtered output |
| M2 | Medium | **MONITORING** — 53.1% WR at n=32 below juice breakeven; checkpoint at n=50 |
| M3 | Medium | **MONITORING** — 52.4% WR; split negative/plus-odds at n=60; watch 3PM unders |
| M4 | Medium | **DEFERRED** — need n=50+ G14-adjacent picks |
| M5 | Medium | **CLOSED** — G4/G5 kept as-is |
| M6 | Medium | **CLOSED** — G1 documented as theoretical guard |
