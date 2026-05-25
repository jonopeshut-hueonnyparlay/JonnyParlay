# Audit 2026-05-25 — Track D: Sport-Specific Logic

Auditor: Claude Sonnet 4.6 (automated)
Scope: engine/run_picks.py — NBA, NHL, MLB, WNBA code paths

---

## D1. NBA-Specific

### Playoff mode detection
`PLAYOFF_MODE` does not exist as a flag in run_picks.py. Playoff mode is inferred from a date-based heuristic in `projections_db.py`: `"Playoffs" if month >= 5 or (month == 4 and day >= 12)`. This drives the `season_type` column in the games table, read at project time. For SaberSim CSV runs (not custom engine), no playoff-specific scalars are applied in run_picks.py — SaberSim's own projections are used as-is. Playoff scalars only fire when the custom engine runs.

### Playoff scalars — no RS leakage
When `is_playoff=True` in nba_projector.py: PLAYOFF_MINUTES_SCALAR and PLAYOFF_RATE_DEFLATORS are applied correctly. REGULAR_SEASON scalars are bypassed via clean if/else branching. No leakage confirmed.

### Blowout sigmoid in playoff mode
Applied unconditionally (no playoff/RS check). Playoff spreads are tighter → sigmoid fires less often → correct emergent behavior. Sigmoid was fit without playoff/RS stratification per CLAUDE.md.

### NBA combo stats (PA, RA, PRA) — AST sigma fallback
See finding A-1 (HIGH). AST moved to NB_STATS but no calibrated sigma left in SIGMA for combo use. Falls to uncalibrated `{"mult":0.40,"min":2.0}`.

---

## D2. NHL-Specific

### SOG Poisson cutoff
`POISSON_STATS = {"REB", "SOG", "REC", "HITS"}`. `POISSON_CUTOFF = 8.5`. All realistic NHL SOG lines (2.5–5.5) are well below 8.5. Poisson always used. G8C blocks SOG under ≤ 3.5. Correct.

### NHL Platt — shared with NBA
No separate NHL Platt calibration. NHL is included in the combined NBA+NHL Platt. Comment at ~line 2261: "Platt was fitted on NBA+NHL props only." Acceptable for now.

### NHL game lines — same path as NBA
`GAME_SIGMA["NHL"] = {"total":1.2,"spread":1.5,"team":1.8,"ml":4.0}`. NHL spread tier = T3 via `_FIXED_SPREAD_SPORTS` check. No NHL-specific issues.

### No NHL_CORR_GROUPS
NHL has only SOG and AST prop markets. No correlation group needed — no shared hidden variable like pitcher K/OUTS/HA.

---

## D3. MLB-Specific

### MLB stat routing
All MLB stats correctly routed:
- K: NB_STATS (r=5.0)
- OUTS: Normal (SIGMA["OUTS"] = mult=0.30, min=3.0)
- HA: Normal (SIGMA["HA"] = mult=0.50, min=2.5)
- HITS: POISSON_STATS
- HRR: NB_STATS (r=1.5) — gate-blocked (G_HRR_DISABLED)
- TB: gate-blocked (G_TB_DISABLED)

### SIGMA["OUTS"] and SIGMA["HA"] calibration
Comments say "recalibrated 2024 season data" — MLB-specific, not basketball. Appropriate.

### F5 lines
MLB-only (guarded: `if sport != "MLB": return []`). Three markets: F5_TOTAL (T1B), F5_ML, F5_SPREAD (T2). F5 projections scale full-game team totals by 0.503 (empirical F5/full ratio). Correctly isolated.

### MLB_CORR_GROUPS
`PITCHER_STATS = {"K","OUTS","HA"}`, `BATTER_CORR_STATS = {"HITS","TB","HRR"}`. Max 1 per group enforced in `deduplicate()`. TB/HRR are gate-blocked, so batter group currently applies only to HITS. Correct.

### MLB season start gate
No explicit MLB season start date gate in run_picks.py. MLB activates when an MLB CSV is passed. No early-season edge dampener (unlike WNBA). Acceptable — SaberSim only provides MLB CSVs when games are scheduled.

---

## D4. WNBA-Specific

### SHADOW_SPORTS enforcement
`SHADOW_SPORTS = {"WNBA"}` (~line 211). Shadow split occurs at one point immediately after correlation filter — all downstream Discord functions receive only the non-shadow `qualified` list. Shadow picks log to `pick_log_wnba.csv` only. Correct and complete.

### SIGMA_WNBA
`PTS:{mult:0.38,min:3.5}`, `AST:{mult:0.55,min:1.1}`, `REB:{mult:0.45,min:2.0}`, `3PM:{mult:0.48,min:0.70}`. Comment: "calibrated from 9 players / 336 games (2024 season)."

### WNBA 3PM routing
~line 687: explicit exception `not (sport == "WNBA" and stat == "3PM")` — WNBA 3PM bypasses NB, routes to Normal using SIGMA_WNBA["3PM"]. Correct (WNBA 3PM is underdispersed, var/mean ≈ 0.70).

### WNBA_SEASON_START
`WNBA_SEASON_START = date(2026, 5, 13)` (~line 341). Correct for 2026. Must be updated manually each year.

### pick_log_wnba.csv schema
Written via `log_picks(sport_shadow, ...)` using `CANONICAL_HEADER` (29-column schema_version=4). Identical schema to main pick_log. No schema drift.

---

## Findings

### D-1 (MEDIUM) — TEAM_TOTAL over block fires for all sports, only NBA evidence

```
TRACK: D
FILE: engine/run_picks.py
LINE: ~2727–2730
SEVERITY: MEDIUM
N: 11 (NBA only)
ISSUE: Hard `continue` for TEAM_TOTAL overs fires unconditionally for NBA, NHL, and MLB.
Empirical basis is NBA n=11 (45.5% WR, -11.0pp gap). No NHL or MLB TEAM_TOTAL over data
cited. Hockey goals totals and baseball run totals have different market dynamics and
over-bias characteristics than NBA points.
IMPACT: NHL and MLB TEAM_TOTAL overs are blocked with no empirical justification.
If they have a positive WR in those sports, this block silently kills profitable picks.
FIX: Add sport guard: `if direction == "over" and sport in {"NBA"}: continue`
(PROVISIONAL — validate on NHL/MLB once n ≥ 30 per sport).
```

### D-2 (MEDIUM) — CLAUDE.md states Platt is logit-space; code is raw-probability space

```
TRACK: D
FILE: CLAUDE.md + engine/run_picks.py
LINE: CLAUDE.md memory section + ~357, ~649
SEVERITY: MEDIUM (see B-1 for CRITICAL rating at the formula level)
N: N/A
ISSUE: Documented in B-1. The CLAUDE.md memory entry describing the deployed Platt formula
as "logit-space" is wrong. This creates a hazard for H3 migration where someone could
apply logit-space coefficients to a raw-space formula (or vice versa), causing ±12–18pp
errors in all prop win_probs.
IMPACT: Operational risk during H3 migration.
FIX: Correct CLAUDE.md: "Formula: sigmoid(A * over_p + B) (raw-probability space —
frozen until H3 gate fires, at which point BOTH formula AND A/B change simultaneously)."
```

### D-3 (LOW) — Playoff mode detection is date-heuristic only for custom engine

```
TRACK: D
FILE: engine/projections_db.py
LINE: ~1475
SEVERITY: LOW
N: N/A
ISSUE: PLAYOFF_MODE is a date heuristic (April 12+ = playoffs). For SaberSim CSV runs,
no playoff adjustment is applied in run_picks.py — SaberSim's projections are used as-is.
Playoff-specific deflators (PLAYOFF_RATE_DEFLATORS, PLAYOFF_MINUTES_SCALAR) only fire
through the custom engine. This is by design but not documented at the run_picks.py level.
IMPACT: If SaberSim already prices playoff adjustments, no issue. If not, custom engine
users get deflated projections while SaberSim users do not.
FIX: Add a comment in run_picks.py near the SaberSim CSV parse: "SaberSim projections
used as-is in playoff mode — deflators are applied in the custom engine path only."
```

### D-4 (LOW) — HRR in PROP_MARKETS["MLB"] wastes API quota

```
TRACK: D
FILE: engine/run_picks.py
LINE: ~240
SEVERITY: LOW
N: N/A
ISSUE: PROP_MARKETS["MLB"] includes "batter_hits_runs_rbis" (HRR) but HRR is permanently
blocked by G_HRR_DISABLED. Market data is fetched and parsed unnecessarily every run.
IMPACT: Wasted API quota (minor).
FIX: Remove "batter_hits_runs_rbis" from PROP_MARKETS["MLB"] until HRR is re-enabled,
or add comment: "# fetched for monitoring; blocked by G_HRR_DISABLED."
```

### D-5 (LOW) — WNBA_SEASON_START must be manually updated each year

```
TRACK: D
FILE: engine/run_picks.py
LINE: ~341
SEVERITY: LOW
N: N/A
ISSUE: No automation reminder or validation. If WNBA_SEASON_START is not updated for
the 2027 season, early-season dampening fires on the wrong dates.
IMPACT: Wrong early-season edge dampening for 2027+ unless manually updated.
FIX: Add comment: "# UPDATE: must be set to actual WNBA season opener date each year."
```
