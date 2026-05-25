# Audit 2026-05-25 — Track L: Documentation vs Reality

Auditor: Claude Sonnet 4.6 (automated)
Scope: CLAUDE.md claims verified against engine/run_picks.py, engine/sgp_builder.py, data/pick_log.csv, data/pick_log_custom.csv, filesystem

---

## Verification Table

| # | CLAUDE.md Claim | Actual Code Value | File / Line | Status |
|---|---|---|---|---|
| 1 | `PLATT_A = 1.4988` | `PLATT_A = 1.4988` | run_picks.py ~370 | ✓ MATCH |
| 1b | `PLATT_B = -0.8102` | `PLATT_B = -0.8102` | run_picks.py ~371 | ✓ MATCH |
| 2 | Formula: `sigmoid(A * logit(over_p) + B)` (logit-space) | Code uses **raw-probability space**: `sigmoid(PLATT_A * over_p + PLATT_B)`. Lines ~357, ~370, ~649 all explicitly label as "raw-probability space (not logit-space)". | run_picks.py ~357–371, ~649 | ✗ MISMATCH — CRITICAL |
| 3 | `NB_R["3PM"] = 9.15` | `"3PM": 9.15` | run_picks.py ~296 | ✓ MATCH |
| 4 | `NB_R["AST"] = 9.68` | `"AST": 9.68` | run_picks.py ~297 | ✓ MATCH |
| 5 | AST in NB_STATS, NOT POISSON_STATS | `NB_STATS = {"3PM","HRR","K","AST"}` — AST confirmed in NB; `POISSON_STATS = {"REB","SOG","REC","HITS"}` — AST absent | run_picks.py ~281, ~294 | ✓ MATCH |
| 6 | SIGMA: AST/SOG/HITS/TB removed | SIGMA contains: REB, REC, PTS, OUTS, HA only. AST/SOG/HITS/TB all absent (noted as comments or gate-killed). | run_picks.py ~263–277 | ✓ MATCH |
| 7 | H3 gate: 50 over_p_raw rows as of 2026-05-25 | Counted **50** non-empty `over_p_raw` rows in pick_log.csv | data/pick_log.csv | ✓ MATCH |
| 8 | CLV gate: 49/100 as of 2026-05-23 | Actual count: **63** CLV-populated rows in pick_log_custom.csv (stale — count has advanced) | data/pick_log_custom.csv | ✗ STALE (49→63, dated 2026-05-23) |
| 9 | SGP Platt gate: 42/100 as of 2026-05-23 | Actual scored SGP slips: **43** | data/pick_log.csv | ✗ STALE (42→43) |
| 10 | `DK_STD_FLOOR`: starter=4.0, sixth_man=4.0, rotation=3.5, spot=3.0, cold_start=3.0 | Confirmed in nba_projector.py ~232–238 (projection system — out of scope for this audit) | nba_projector.py | ✓ MATCH |
| 11 | Context sanity system DELETED 2026-05-23 | No context system logic in run_picks.py. context_verdict/reason/score columns preserved for schema compat (written as empty strings). Two cosmetic residues: string "Qualified picks (pre-context)" (~line 6044) and comment "context layer" (~line 6047). | run_picks.py ~6044, ~6047 | ✓ MATCH (with minor note) |
| 12 | WNBA in `SHADOW_SPORTS` | `SHADOW_SPORTS = {"WNBA"}` | run_picks.py ~211 | ✓ MATCH |
| 13 | `MIN_WIN_PROB = 0.55` | `MIN_WIN_PROB = 0.55` | run_picks.py ~1164 | ✓ MATCH |
| 14 | KILLSHOT stats: `{PTS, AST, SOG}` only | `KILLSHOT_STAT_ALLOW = frozenset({"PTS","AST","SOG"})` — 3PM and REB excluded | run_picks.py ~197 | ✓ MATCH |
| 15 | KILLSHOT weekly cap: 2 | `KILLSHOT_WEEKLY_CAP = 2` | run_picks.py ~201 | ✓ MATCH |
| 16 | "Daily total cap: 12u (G12 check)" | Cap value is 12.0 (literal float), confirmed in apply_caps() and main flow. **BUT G12 in the code refers to the pitcher-prop per-game direction gate, NOT the daily unit cap.** The 12u cap has no named constant. | run_picks.py ~1208, ~1331, ~6142 | ✗ LABEL MISMATCH |
| 17 | SGP range "+200–450" | `MIN_PARLAY_ODDS = 200, MAX_PARLAY_ODDS = 450` | sgp_builder.py ~50–51 | ✓ MATCH |
| 18 | Daily_lay max combined odds: +100 | `MAX_COMBINED_ODDS_VAL = 100` | run_picks.py ~3642 | ✓ MATCH |
| 19 | `morning_preview.py` removed | Source file absent. Only stale .pyc bytecode cache files remain. | filesystem | ✓ MATCH (file gone as documented) |
| 20 | `post_nrfi_bonus.py` listed under Key Files | Source `.py` is MISSING from both root and engine/. Only `__pycache__/post_nrfi_bonus.cpython-*.pyc` bytecode remains. | filesystem | ✗ MISMATCH — source deleted |
| 21 | Context disabled = no live code | Confirmed — no functional context system code. Cosmetic residues only. | run_picks.py | ✓ MATCH |

---

## Additional Undocumented Discrepancies

### L-1 (CRITICAL) — CLAUDE.md Platt formula space is wrong

```
TRACK: L
FILE: CLAUDE.md (Active Scalars → PLATT_A/B entry)
LINE: CLAUDE.md memory section
SEVERITY: CRITICAL
N: N/A
ISSUE: CLAUDE.md states "Formula: sigmoid(A * logit(over_p) + B) (logit-space Platt —
updated 2026-05-25 in calibrate_platt.py; coefficients unchanged until gate fires)."
Production formula in run_picks.py (~line 649) is: `raw = PLATT_A * over_p + PLATT_B`
(RAW-PROBABILITY SPACE). Code comments at lines ~357 and ~370 explicitly label the
constants as "raw-probability space (not logit-space)."
CLAUDE.md was updated to describe the FUTURE logit-space formula (that calibrate_platt.py
now produces) but with the CURRENT raw-space constants. This creates an H3 migration trap:
applying the same A/B (1.4988, -0.8102) to the logit-space formula shifts win_prob by
-12.8pp at over_p=0.55 and +18.4pp at over_p=0.80.
IMPACT: AI tools or engineers reading CLAUDE.md to implement H3 will paste logit-space A/B
into a raw-space formula (or change the formula without updating A/B), corrupting all
prop win_probs.
FIX: Update CLAUDE.md Active Scalars entry to:
`PLATT_A=1.4988, PLATT_B=-0.8102 — frozen until H3 gate. Formula: sigmoid(A * over_p + B)
(raw-probability space — NOT logit-space). At H3, both formula AND coefficients change
simultaneously from calibrate_platt.py output.`
```

### L-2 (MEDIUM) — "Premium = Top 5 picks" — code cap is 3, not 5

```
TRACK: L
FILE: CLAUDE.md (Terms table: "Premium | Top 5 picks from the model each day")
LINE: run_picks.py ~1161
SEVERITY: MEDIUM
N: N/A
ISSUE: CLAUDE.md Terms table says: "Premium | Top 5 picks from the model each day."
Actual code: `MAX_PREMIUM_PICKS = 3` (line ~1161) — per-sport cap is 3, not 5.
This has been 3 since a prior audit redesign. Documentation is wrong.
IMPACT: Misleads anyone reasoning about daily card volume or per-session unit sizing totals.
Subscribers expecting 5 picks see only 3.
FIX: Update CLAUDE.md Terms: "Premium | Top 3 picks per sport from the model each day."
```

### L-3 (MEDIUM) — SGP sizing gate description is stale

```
TRACK: L
FILE: CLAUDE.md (SGP entry under Terms)
LINE: engine/sgp_builder.py ~738–741
SEVERITY: MEDIUM
N: N/A
ISSUE: CLAUDE.md says "Dynamic sizing: 0.25u default / 0.50u premium (avg_wp≥0.70 AND
cohesion≥0.55 AND avg_edge≥0.035)." The avg_wp≥0.70 criterion was replaced in L8 (May 2026)
by a Gaussian copula EV margin check: `if _copula_joint - parlay_implied >= 0.10`. The
cohesion≥0.55 and avg_edge≥0.035 prerequisites remain correct, but avg_wp condition is gone.
IMPACT: CLAUDE.md describes a non-existent gate criterion. Anyone implementing a size
override based on this description would apply the wrong condition.
FIX: Update CLAUDE.md SGP entry: "Dynamic sizing: 0.25u default / 0.50u premium (copula
EV margin ≥ 0.10 AND cohesion ≥ 0.55 AND avg_edge ≥ 0.035)."
```

### L-4 (MEDIUM) — post_nrfi_bonus.py source file missing

```
TRACK: L
FILE: CLAUDE.md (Key Files table) + filesystem
LINE: Root directory + engine/
SEVERITY: MEDIUM
N: N/A
ISSUE: CLAUDE.md documents post_nrfi_bonus.py as an existing Key File:
"One-shot webhook poster for manual bonus drops. Uses Mozilla UA to bypass Cloudflare 1010."
Source .py file is ABSENT from both root directory and engine/. Only stale .pyc bytecode
in __pycache__ remains. If this tool is ever needed, it cannot be run without source
being restored.
IMPACT: Operational: manual NRFI bonus drops require this script; it cannot be run.
FIX: Either (a) restore source from git history (`git log -- post_nrfi_bonus.py`), or
(b) remove from CLAUDE.md Key Files if intentionally deleted.
```

### L-5 (LOW) — G12 label mismatch in CLAUDE.md

```
TRACK: L
FILE: CLAUDE.md (Sizing Caps section)
LINE: run_picks.py ~1208
SEVERITY: LOW
N: N/A
ISSUE: CLAUDE.md says "Daily total cap: 12u (G12 check in run_picks.py)". In code, G12
is the MLB pitcher-prop per-game direction gate (max 2 same-direction pitcher props per
game), NOT the 12u daily cap. The 12u cap is a literal 12.0 float with no named constant.
IMPACT: Minor label confusion only. The 12u cap does exist and is enforced.
FIX: Update CLAUDE.md: "Daily total cap: 12u (12.0 literal in apply_caps() — G12 in code
is the pitcher-prop same-game gate, unrelated)."
```

### L-6 (LOW) — SPORT_UNIT_CAP entries undocumented

```
TRACK: L
FILE: CLAUDE.md (Sizing Caps section)
LINE: run_picks.py ~1315
SEVERITY: LOW
N: N/A
ISSUE: CLAUDE.md says "Sport unit caps: NBA=8.0u max | NHL=5.0u max." Actual dict:
{"NBA": 8.0, "WNBA": 4.0, "NHL": 5.0, "NFL": 5.0, "MLB": 8.0}. WNBA (4.0u),
MLB (8.0u), and NFL (5.0u) per-pick caps are undocumented.
IMPACT: Minor. WNBA is in shadow, NFL is off-season. MLB 8.0u cap is live and undocumented.
FIX: Update CLAUDE.md: "Sport unit caps: NBA=8.0u | MLB=8.0u | NHL=5.0u | NFL=5.0u | WNBA=4.0u."
```

### L-7 (LOW) — CLV/SGP gate counts are stale (dated 2026-05-23)

```
TRACK: L
FILE: CLAUDE.md (Data-gated / Open section)
LINE: N/A
SEVERITY: LOW
N: N/A
ISSUE: Counts as of 2026-05-23 are now stale:
- CLV gate: "49/100 as of 2026-05-23" → actually 63/100 as of 2026-05-25
- SGP gate: "42/100 as of 2026-05-23" → actually 43/100 as of 2026-05-25
These are routine date-specific notes, not logic errors.
IMPACT: Minor. Stale counts could cause confusion when assessing gate proximity.
FIX: Update CLAUDE.md counts to current values (63 CLV, 43 SGP, 50 H3).
```

### L-8 (LOW) — CLV capture window documented incorrectly

```
TRACK: L
FILE: CLAUDE.md (CLV Daemon section)
LINE: engine/capture_clv.py ~157–159
SEVERITY: LOW
N: N/A
ISSUE: CLAUDE.md says "T-30 to T+3" capture window. Code: CAPTURE_BEFORE_SECS = 45*60
(T-45) and CAPTURE_WRITE_BEFORE_SECS = 10*60 (writes within T-10 of tip). So polling
starts T-45, writes gated to T-10.
FIX: Update CLAUDE.md: "T-45 to T+3 polling; CLV written only within T-10 of tip."
```

### L-9 (LOW) — CLV formula described as "vig-free" but is vigged

```
TRACK: L
FILE: CLAUDE.md (Terms: "CLV | closing_implied_prob − your_implied_prob (positive = beat
the close)")
LINE: engine/capture_clv.py ~874
SEVERITY: LOW
N: N/A
ISSUE: The description implies vig-free probabilities but code uses raw vigged implied
probability on both sides. Documented in H2 — repeating here as CLAUDE.md issue.
FIX: Update CLAUDE.md CLV definition: "raw vigged closing implied minus raw vigged open
implied (consistent with industry standard, both sides vigged — not vig-free)."
```

---

## Summary of CLAUDE.md Corrections Needed

| Priority | Item | Change |
|----------|------|--------|
| CRITICAL | Platt formula space | Change from logit-space to raw-probability space description |
| MEDIUM | "Premium = Top 5 picks" | Correct to "Top 3 picks per sport" |
| MEDIUM | SGP sizing gate | Replace avg_wp≥0.70 with copula EV margin ≥ 0.10 |
| MEDIUM | post_nrfi_bonus.py Key File | Remove or restore from git history |
| LOW | G12 label | Clarify G12 is pitcher-prop gate, not the daily cap constant |
| LOW | SPORT_UNIT_CAP | Add WNBA=4.0u, MLB=8.0u, NFL=5.0u |
| LOW | Gate counts | Update CLV=63, SGP=43, H3=50 |
| LOW | CLV capture window | Update to T-45/T-10 |
| LOW | CLV formula | Remove "vig-free" description |
