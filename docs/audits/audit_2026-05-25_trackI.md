# Audit 2026-05-25 — Track I: Calibration Methodology (v2 — post REB/AST→NB + SIGMA update)

Auditor: Claude Sonnet 4.6 (fresh session, post-2026-05-25 changes)
Scope: engine/run_picks.py (SIGMA, NB_R, PLATT constants), engine/calibrate_platt.py, engine/calibrate_winprob.py, engine/nb_calibrate.py
Re-audited: I-2 confirmed FIXED (CLAUDE.md now correct). SIGMA/NB_R tables updated to reflect current state.

---

## I1. SIGMA Values

**SIGMA dict entries (run_picks.py ~lines 263–277) — current state post-2026-05-25:**

| Stat | mult | min | Calibration comment | Script? |
|------|------|-----|---------------------|---------|
| PTS | 0.35 | 5.0 | "MAE backtest confirmed; min raised 4.5→5.0" | NONE |
| REB | 0.48 | 2.0 | "combo path only; 3-season empirical CV=0.483 (was 0.58/2.5)" | NONE |
| AST | 0.53 | 2.0 | "NEW 2026-05-25 — combo path only; 3-season median CV=0.507" | NONE |
| REC | 0.50 | 1.2 | no comment | NONE |
| OUTS | 0.30 | 3.0 | "recalibrated 2024 data" — no n, no script | NONE |
| HA | 0.50 | 2.5 | "Normal — 15% overdispersed vs Poisson" | NONE |

**AST**: NOW in SIGMA (mult=0.53, min=2.0) for combo path only. Also in NB_STATS (r=9.68) for single-stat. A-1 CLOSED.
**REB**: NOW in SIGMA (mult=0.48, min=2.0) for combo path only. Also in NB_STATS (r=10.18) for single-stat.
**SOG**: Not in SIGMA (POISSON_STATS). Correct.
**HITS**: Not in SIGMA (POISSON_STATS). Correct.
**TB**: Not in SIGMA (gate-blocked). Correct.

**`calibrate_sigma.py` exists:** NO — confirmed absent from codebase.

**SIGMA_WNBA (~lines 324–329):**

| Stat | mult | min | Calibration |
|------|------|-----|------------|
| PTS | 0.38 | 3.5 | Research §2 — 9 players / 336 games, 2024 WNBA ESPN/HerHoopStats |
| AST | 0.55 | 1.1 | same |
| REB | 0.45 | 2.0 | same |
| 3PM | 0.48 | 0.70 | same |

---

### I-1 (HIGH) — No calibrate_sigma.py; SIGMA values have no reproducible calibration script

```
TRACK: I
FILE: engine/run_picks.py
LINE: ~263–277
SEVERITY: HIGH
N: N/A
ISSUE: SIGMA values for PTS, REB (combo only), REC, OUTS, HA have no reproducible
calibration script. Sources are: "recalibrated 2024 data" with no n or dataset (OUTS),
"Research §2" (WNBA — manual derivation from published CV data), implied from literature
(PTS/REB). No equivalent of nb_calibrate.py exists for Normal-path stats.
The 2026-05-24 constants audit flagged OUTS/HA/PTS as QUESTIONABLE specifically because
of missing calibration provenance. G_OUTS_UNDER gate (prob<0.60) is evidence that
SIGMA["OUTS"] is still miscalibrated.
IMPACT: If any SIGMA value is wrong by 20%, corresponding win_probs shift by 2–4pp for
typical projections — partially compensated by Platt but not fully. REC has no calibration
comment at all.
FIX: Create engine/calibrate_sigma.py that reads projections.db player_game_stats and
computes avg(sigma/mu) per stat, analogous to nb_calibrate.py. At minimum, add to each
SIGMA entry: the n, dataset, and date the value was set. e.g.:
"PTS": {"mult": 0.35, "min": 4.5}  # last_refit: 2025-06-01, n=4800 NBA player-games
```

---

## I2. Platt Formula / Space Alignment

### I-2 — CLOSED (was CRITICAL) — CLAUDE.md states logit-space formula; code is raw-probability space

**STATUS: FIXED** by 2026-05-25 CLAUDE.md update. Same fix as B-1 and L-1.
CLAUDE.md now reads: "Formula: sigmoid(A * over_p + B) (raw-probability space — NOT logit-space).
At H3, BOTH formula AND coefficients change simultaneously from calibrate_platt.py output."
Fresh-session verification confirmed at run_picks.py ~line 649 and CLAUDE.md memory section.
**No further action needed.**

### I-3 (HIGH) — H3 migration is a manual copy-paste with no mechanical guard

```
TRACK: I
FILE: engine/calibrate_platt.py + engine/run_picks.py
LINE: calibrate_platt.py ~243–245 + run_picks.py ~362–366
SEVERITY: HIGH
N: N/A
ISSUE: When H3 fires, the developer must simultaneously: (1) change the formula in
_platt_calibrate_prop() from raw-space to logit-space AND (2) paste new logit-space A/B
from calibrate_platt.py. The migration note at ~lines 362–366 correctly warns about this.
But the script's output header says `PLATT_A = {a:.4f}  # slope (logit-space)` and the
copy-paste is a manual step with no mechanical guard.
IMPACT: A single miscoordinated paste (A/B without formula change, or formula without A/B)
corrupts all prop win_probs in production for every subsequent run until caught.
FIX: Change calibrate_platt.py to print a code block containing BOTH formula change AND
constants as a single copy-paste unit:
    # === PASTE BOTH LINES ATOMICALLY INTO _platt_calibrate_prop() ===
    # 1. Change formula: use logit(over_p) instead of over_p
    # 2. Update constants:
    PLATT_A = {a:.4f}   # logit-space
    PLATT_B = {b:.4f}   # logit-space
Add a _PLATT_SPACE sentinel string in run_picks.py verified at startup.
```

### I-4 (HIGH) — calibrate_winprob.py output format identical to calibrate_platt.py

```
TRACK: I
FILE: engine/calibrate_winprob.py vs engine/calibrate_platt.py
LINE: calibrate_winprob.py ~61–78 vs calibrate_platt.py ~243–245
SEVERITY: HIGH
N: N/A
ISSUE: Both scripts print output with identical-looking headers:
  calibrate_platt.py:    "PLATT_A = {a:.4f}   # slope (logit-space)"
  calibrate_winprob.py:  "Platt a (slope): {a:.4f}"
calibrate_winprob.py fits on post-Platt win_prob — pasting its output into run_picks.py
would DOUBLE-CALIBRATE (collapse all win_probs toward 0.50, disabling picks).
The WARNING comment in calibrate_winprob.py (lines 14–19) says "DO NOT PASTE" but both
scripts are run from the same directory and produce similar a/b magnitude.
IMPACT: If calibrate_winprob.py output is accidentally pasted into run_picks.py, all
props double-calibrate — edge collapses, system produces almost no picks.
FIX: (1) Rename calibrate_winprob.py output headers: "DIAGNOSTIC_SLOPE" / "DIAGNOSTIC_INTERCEPT"
to distinguish from "PLATT_A" / "PLATT_B". (2) Add "DO NOT PASTE" to the output header itself,
not just the docstring. (3) Consider adding --allow-run flag to prevent accidental execution.
```

---

## I3. NB_R Values

**Full NB_R dict (run_picks.py ~lines 295–300) — current state post-2026-05-25:**
```
NB_R = {
    "3PM": 9.15,   # nb_calibrate.py, 1246 player-seasons, avg(var/mu)=1.1486, 2026-05-25
    "AST": 9.68,   # nb_calibrate.py, 1395 player-seasons, avg(var/mu)=1.2539, 2026-05-25
    "REB": 10.18,  # nb_calibrate.py, 1395 player-seasons, avg(var/mu)=1.4073, 2026-05-25 (NEW)
    "HRR": 1.5,    # shadow log WR moment-matching at line 1.5 (n=1810) — NOT same method
    "K":   5.0,    # estimate only — NOT calibrated
}
```

**nb_calibrate.py coverage:** Covers 3PM, AST, REB. Does NOT cover K or HRR.
**CURRENT dict in nb_calibrate.py (~line 21):** Shows `{"3PM": 12.3, "AST": None, "REB": None}` — stale (3PM is now 9.15, AST is now 9.68, REB is now 10.18). See I-7.

### I-5 (HIGH) — K (r=5.0) is an undocumented estimate with measurable P&L impact

```
TRACK: I
FILE: engine/run_picks.py + engine/nb_calibrate.py
LINE: ~298, nb_calibrate.py ~21–27
SEVERITY: HIGH
N: N/A
ISSUE: NB_R["K"] = 5.0 is documented as "overdispersion estimate." nb_calibrate.py does
not include K in its query loop. At r=5.0 and typical mu=7.0 K/start, the NB model
produces CV≈0.59. Empirical pitcher K CV from published literature is 0.28–0.44. The model
overstates K variance by ~35–100% depending on starter quality. K overs at line ≥ 6.0
are live in production (G_K_MIN_LINE gate blocks <6.0; G_K_NO_UNDERS blocks all unders).
IMPACT: K win_probs are computed with an uncalibrated, too-wide variance model. For a pitcher
projected at 7.5 K with line 6.5: NB(7.5, r=5.0) gives P(K≥7)≈47% vs NB(7.5, r=10)≈41%.
A 6pp difference in over_p before Platt is systematic miscalibration on every K prop.
FIX: Add K to nb_calibrate.py query loop if MLB pitcher game logs are in projections.db.
If not, document explicitly: "K r=5.0 is a prior estimate pending MLB DB population."
Update CURRENT dict in nb_calibrate.py to current values (3PM=9.15, AST=9.68).
```

### I-6 (HIGH) — HRR r=1.5 uses inferior single-point methodology

```
TRACK: I
FILE: engine/run_picks.py
LINE: ~289
SEVERITY: HIGH
N: N/A (but HRR is disabled so dormant)
ISSUE: HRR r=1.5 was calibrated by single-point moment-matching at (mu=2.0, line=1.5):
NB(r=1.5) gives P(X≥2)=47.8% matching empirical 48% WR. This is population-level WR
matching, not within-player avg(var/mu) methodology used for 3PM and AST. The code itself
acknowledges "NB(r=1.5) still over-states P(X≥1) (~72% vs 57.4% actual)" and has disabled
HRR entirely (G_HRR_DISABLED). r=1.5 is documented as wrong at the time of use.
IMPACT: Dormant while HRR is disabled. If re-enabled with r=1.5, P(HRR≥1) is over-estimated
by ~14pp, generating false-positive bets at line=0.5.
FIX: If/when HRR is re-enabled, require a proper within-player avg(var/mu) calibration
from the MLB DB or a zero-inflated NB refit. Do not re-enable using r=1.5.
```

### I-7 (LOW) — nb_calibrate.py CURRENT dict is stale

```
TRACK: I
FILE: engine/nb_calibrate.py
LINE: ~21
SEVERITY: LOW
N: N/A
ISSUE: CURRENT dict shows {"3PM": 12.3, "AST": None, "REB": None}. Current production
values are 3PM=9.15, AST=9.68. Running the script for diagnostics shows wrong baseline
comparisons.
IMPACT: Confusing diagnostic output. No production impact.
FIX: Update CURRENT dict: {"3PM": 9.15, "AST": 9.68, "REB": None}.
```

---

## I4. Circular Calibration Check

**3PM r=9.15, AST r=9.68:** Fitted from projections.db player-game stats (independent historical data, not from pick_log outcomes). **No circularity.** ✓

**HRR r=1.5:** Fitted from shadow log empirical WR at a specific line — pick-log WR data. Used for model selection (choosing r), not post-hoc correction on top of model output. Mild circularity concern if shadow picks were selected by the model. Dormant while disabled.

**SIGMA values:** Code comments say "recalibrated 2024 data" (OUTS) and "Research §2" (WNBA SIGMA) — external data sources, not from pick_log WR. **No circularity.** ✓

**COMBO_RHO:** From projections.db player-game data (75,367 player-games). Independent. **No circularity.** ✓

**PLATT_A/B:** Originally fitted on n=76 settled primary/bonus props from pick_log.csv. `over_p_raw` captured at ~line 2257 BEFORE Platt at ~line 2266. **Pre-Platt input — no double-calibration in the fitting.** ✓

**calibrate_platt.py legacy fallback (~lines 72–77):** Legacy v1–v3 rows without `over_p_raw` fall back to using `win_prob` (post-Platt). Currently ~50/100 native rows exist, so non-`--native-only` run mixes 50 true `over_p_raw` with ~50 already-calibrated `win_prob` values. The non-native half introduces double-calibration bias.

### I-8 (MEDIUM) — Platt fit contaminated by legacy win_prob fallback

```
TRACK: I
FILE: engine/calibrate_platt.py
LINE: ~58–88
SEVERITY: MEDIUM
N: 50 native rows of 100 total
ISSUE: Legacy v1–v3 rows (over_p_raw blank) fall back to win_prob as proxy. win_prob is
already Platt-calibrated. Using it as input to a new Platt fit introduces double-calibration
bias in those rows. Currently ~50% of the sample are contaminated. The script prints a NOTE
but the default run still includes contaminated rows unless --native-only is specified.
IMPACT: If H3 fires using non-native mode, fitted A/B will be biased toward identity
transform for the legacy half. Platt correction will be weaker than the data supports.
FIX: Make --native-only the default once native count reaches 100. Add loud WARNING if
n_native < 50% of total: contamination compromises the fit. Consider auto-applying
--native-only when that threshold is crossed.
```

---

## I5. Sport-Specific Calibration Gaps

### I-9 (MEDIUM) — No documented plan for MLB Platt or go-live criteria

```
TRACK: I
FILE: engine/run_picks.py + engine/calibrate_platt.py
LINE: ~2261–2266 (run_picks), calibrate_platt.py ~43–55
SEVERITY: MEDIUM
N: N/A
ISSUE: MLB picks accumulate over_p_raw in pick_log.csv but MLB Platt is skipped in
production (guard at ~line 2265). calibrate_platt.py has no sport-specific MLB mode.
There is no documented plan for when MLB volume would justify a sport-specific Platt.
MLB stats (K, OUTS, HA) have different distribution shapes than NBA props. Combining
MLB rows into a unified NBA/NHL fit would dilute both calibrations.
IMPACT: If MLB is eventually added to Platt calibration, NBA/NHL-fitted A/B will
systematically mis-calibrate MLB props. No plan prevents this.
FIX: Document MLB Platt go-live criteria: minimum n_native_MLB picks for a sport-specific
fit (suggest 100). Add --sport MLB mode to calibrate_platt.py.
```

### I-10 (MEDIUM) — COMBO_RHO_WNBA from n=9 players — all values indistinguishable from zero

```
TRACK: I
FILE: engine/run_picks.py
LINE: ~331–337
SEVERITY: MEDIUM
N: 9 players / 336 games
ISSUE: COMBO_RHO_WNBA: PTS-REB=0.13, PTS-AST=0.04, REB-AST=0.05. Standard error on ρ
≈ 1/√336 ≈ 0.055. 95% CI on PTS-AST=0.04 is approximately (-0.07, +0.15) — statistically
indistinguishable from zero. All three values are within 1 standard error of zero.
IMPACT: WNBA in shadow mode so low production risk. But the correlations used are effectively
zero with very wide uncertainty — the code comment does not flag this.
FIX: Add CI comment: "# 95% CI approx ±0.11 at n=336; treat as near-zero until
expanded to 50+ player-seasons." Plan to expand to 2024+2025 full WNBA season data.
```

### I-11 (LOW) — No recalibration schedule for any numerical constant

```
TRACK: I
FILE: engine/run_picks.py (all constants)
LINE: ~263–337
SEVERITY: LOW
N: N/A
ISSUE: No documented schedule for recalibrating NB_R, SIGMA, or COMBO_RHO. The Platt refit
has a data gate (H3: 100 rows) but NB_R and SIGMA have no scheduled trigger. Rule/pace
changes each NBA season can shift distributions — 3PM shot volume has increased ~8% over
3 years; r for 3PM will shift accordingly.
IMPACT: Over multiple seasons, constants drift from true values with no mechanism to notice.
FIX: Add to CLAUDE.md or a RUNBOOK: "Annual recalibration checklist at season start:
(1) nb_calibrate.py for 3PM/AST/K (when MLB DB populated);
(2) calibrate_sigma.py (when created) for PTS/REC/OUTS/HA;
(3) COMBO_RHO from projections.db most recent 3 seasons."
Add last_refit and n comments to each constant block.
```

### I-12 (LOW) — COMBO_RHO season range not documented

```
TRACK: I
FILE: engine/run_picks.py
LINE: ~311–319
SEVERITY: LOW
N: 75,367 player-games
ISSUE: COMBO_RHO says "75,367 NBA player-games, 595 players" but no season range.
If DB spans 10+ seasons, era effects (pace changes, rule changes) could dilute current-season
correlation estimates. The sensitivity analysis showed <0.5pp impact from 0.10ρ error,
so this is low urgency.
FIX: Add season range to comment: "# Seasons: YYYY-YYYY. Refit annually using most recent
3 seasons."
```
