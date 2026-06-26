# AUDIT 2026-06 — JP-13 Gates/rules/config (JonnyParlay)

Files audited (7 read): gate_check.py, gate_digest.py, gates.py, rules.py, market_config.py, thresholds.py, wnba_gate.py

**Findings (final, excl. refuted): C=0 H=0 M=0 I=7** | constants extracted: 38 | not-done: 10

## Findings

| ID | File:line | Sev | Status | Cat | Known | Title |
|----|-----------|-----|--------|-----|-------|-------|
| JP13-07 | gate_check.py:39 | I | unverified | code |  | gate_check reads pick_log.csv without the shared pick_log lock |
| JP13-01 | gates.py:199 | I | refuted | code |  | G1 gate is unreachable dead code (subsumed by G9) |
| JP13-02 | gates.py:193 | I | refuted | code |  | G15 float(pts_cv) can raise on malformed custom-engine column |
| JP13-04 | gates.py:51 | I | refuted | statistical |  | Multiple structural kill/shadow gates calibrated on very small samples (overfitting risk) |
| JP13-08 | gates.py:166 | I | unverified | code |  | G14 evaluated twice for WNBA 3PM (idempotent, safe) |
| JP13-09 | gates.py:55 | I | unverified | code |  | G8B fires for NHL AST-over low-line before G_NHL_AST (attribution only) |
| JP13-06 | rules.py:144 | I | unverified | completeness |  | Stale comment in can_add: claims score<25 / overs 40+ but constants are 15/15 |
| JP13-03 | thresholds.py:72 | I | refuted | statistical | Y | WNBA early-season sigma-inflation factors (0.80/0.90) are DATA_GATED and never recalibrated |
| JP13-05 | thresholds.py:15 | I | refuted | statistical |  | MIN_DAILY_LAY_PROB=0.50 permits exactly zero-EV daily-lay posts at the +100 cap |
| JP13-10 | thresholds.py:124 | I | unverified | code |  | thresholds.toml override surface can mutate live sizing/gating tunables without code review |
| JP13-11 | thresholds.py:83 | I | unverified | statistical |  | WNBA_EV_FLOOR=0.0955 derivation verified consistent |
| JP13-12 | thresholds.py:87 | I | unverified | statistical |  | F5_SCALAR=0.540 is plausible vs innings-fraction benchmark |

## Confirmed-correct / coverage notes

- **G9/G9B edge floors (0.05 / NBA 0.07) and ordering verified**: every prop with edge<0.05 is killed by G9 before later gates; G9B correctly stacks an NBA-only 0.07 floor (gates.py 141-146).
- **G7/G7b juice gates correct**: hard ban at odds<=-150 (line 37); soft band -149..-140 requires edge>=0.10 (line 41); bands are disjoint, no gap/overlap.
- **GG2 SPREAD sign convention is correct**: `abs(proj + line)` for SPREAD (market implied margin = -line) vs `abs(proj - line)` for totals/ML; documented and matches the math (gates.py 233-239).
- **GG5/GG6 game-line gates correct**: dog-cover spread block (positive odds on spread/F5_SPREAD) and total-side conviction (proj on correct side of line) both sound.
- **WNBA_EV_FLOOR=0.0955 derivation verified** as net EV of NBA's G9 0.05-edge pick at -110 (0.05×1.9091); G_WNBA_EDGE computes EV-per-unit from actual quoted odds so it auto-adjusts to vig (gates.py 113-117).
- **WNBA games-played opening gate logic sound**: per-team games-played with day-gate fallback when EdgeModel DB is missing/stale; season_rows==0 correctly returns None (avoids blocking all season); PHX/PHO alias handled (wnba_gate.py 55-81).
- **apply_caps sorts by pick_score desc before capping** (rules.py 249) so best picks get cap priority (H4 fix), and cross-run units_already_bet seeds the 12u daily cap correctly.
- **R9 forced-over swap in apply_soft_rules_premium correctly decrements/restores counters** around can_add() and restores old_pick on no-replacement (rules.py 198-238).
- **auto_r12 window math fixed** (window_days not window_days-1, gives a true 5-day window) and uses the shared pick_log lock for the read (rules.py 64-95).
- **thresholds override whitelist excludes all frozen/calibrated constants** (KELLY_FRACTION, F5_SCALAR, BM_SHRINKAGE_DEFAULT, PLATT_SPACE, BLEND_ALPHA, WNBA_EV_FLOOR, POISSON_CUTOFF, LONGSHOT_PAIR_RHO) and _coerce_override guards types (bool-before-int, integer-valued float) — fail-soft, malformed TOML never crashes a run (thresholds.py 124-205).
- **gate_check distinct-day normalization** uses date.fromisoformat to reject non-ISO drift so phantom days can't mis-open Calibration Platt (gate_check.py 75-117).
- **SUSPENDED_STATS single-source lookup** drives SOG/HA/RA blocks via one dict (market_config.py 211-215) consumed in gates.py 66-67 — no duplicated suspension logic.
- **PLATT_SPACE='raw'** is correctly NOT overridable and flagged to change in lockstep with formula+A/B (known H3 mismatch, superseded).

## Not-Done / incomplete (this module)

| Kind | File | Detail |
|------|------|--------|
| dead-code | gates.py | G1 gate (line 199) is unreachable — its edge<0.05 clause is always pre-empted by G9 at line 141. |
| deferred | gates.py | Pending investigations referenced but unresolved: G8C SOG scope 're-evaluate when distribution investigation completes' (line 64), G_HA_DIR 'when model investig |
| deferred | market_config.py | SUSPENDED_STATS SOG/HA pending lift (SOG July refit, HA lift after WR>=40% at n>=20); KILLSHOT_STAT_ALLOW SOG 're-add at July refit' (thresholds.py line 47). |
| partial-feature | market_config.py | NFL PROP_MARKETS + MARKET_TO_STAT mappings present (pricing half) but NFL data half (CSV export/parse) deferred — known incomplete per feat/nfl. |
| dead-code | market_config.py | SHADOW_LOG_PATHS = {} (line 75) emptied after MLB/WNBA go-lives; SHADOW_SPORTS = set() (line 23) also empty — shadow-sport routing currently inert (by design, r |
| dead-code | rules.py | STAT_CAP['SOG']=6 (line 260) is unreachable while SOG is in SUSPENDED_STATS (blocked in check_prop_gates before apply_caps). |
| flag-gated | gate_digest.py | DISCORD_GATES_WEBHOOK import falls back to os.getenv because secrets_config registration is 'a one-line addition' not yet landed (lines 56-62); webhook blank-by |
| flag-gated | thresholds.py | config/thresholds.toml override mechanism (lines 159-205) is opt-in; absent file = no override, replay byte-identical. Inactive feature surface. |
| deferred | rules.py | R12 cooldown + R9/R11 reclassified product/optics rules with explicit 'when CLV data matures, replace loss trigger with negative-CLV condition' TODOs (lines 104 |
| deferred | gate_check.py | H3 Platt gate retained 'for historical visibility only' (SUPERSEDED, line 176) — counted/displayed but no longer a deploy basis. |
