# AUDIT 2026-06 — JP-1 Picks pipeline (JonnyParlay)

Files audited (4 read): run_picks.py, evaluators.py, run_picks.py, thresholds.py

**Findings (final, excl. refuted): C=0 H=0 M=1 I=6** | constants extracted: 22 | not-done: 8

## Findings

| ID | File:line | Sev | Status | Cat | Known | Title |
|----|-----------|-----|--------|-----|-------|-------|
| JP1-03 | evaluators.py:100 | M | confirmed | completeness |  | I6 early-season confidence penalty is inert on the SaberSim CSV path (GP never parsed) |
| JP1-01 | evaluators.py:100 | I | confirmed | code |  | Confidence (conf) is applied twice to the prop edge (probability shrink + edge multiply) |
| JP1-02 | evaluators.py:104 | I | refuted | code |  | int(gp) in the live prop loop can raise ValueError on a decimal-string GP and crash the daily run |
| JP1-07 | evaluators.py:55 | I | unverified | code |  | evaluate_props cooldown_players parameter is never used |
| JP1-08 | evaluators.py:228 | I | unverified | completeness |  | evaluate_game_lines output (TOTAL/SPREAD/ML/TEAM_TOTAL) is dropped from the live card by design — math here is shadow/correlation- |
| JP1-09 | evaluators.py:843 | I | refuted | statistical |  | NRFI Poisson constants (BASE_LAMBDA_1ST 0.32, NRFI_GAMMA 0.65, league avgs, FIP const 3.26) are DATA_GATED estimates not fit on fi |
| JP1-10 | evaluators.py:115 | I | unverified | statistical | Y | WNBA props calibrated with NBA+NHL Platt coefficients (known approximation) |
| JP1-04 | run_picks.py:1314 | I | confirmed | code |  | _ks_sport_cap and the 12.0 daily cap are hardcoded duplicates of rules.py SPORT_UNIT_CAP / total cap (lockstep drift risk) |
| JP1-05 | run_picks.py:1570 | I | confirmed | code |  | --repost rebuild does float()/int() on CSV cells that can be empty strings -> ValueError |
| JP1-06 | run_picks.py:1121 | I | refuted | statistical |  | pick_log_calibration.csv logs both over and under rows, each carrying the same over_p_raw (P(over)) — under rows are mis-paired fo |

## C/H/M detail

### [M] JP1-03 — I6 early-season confidence penalty is inert on the SaberSim CSV path (GP never parsed)
`C:/Dev/JonnyParlay/engine/evaluators.py:100-113` · completeness · status=confirmed

**Evidence:** The conf modifier keys entirely on proj_player['GP']/['gp']. parse_csv in odds_io.py does not populate GP (grep shows only dk_std is set), so for any standard SaberSim CSV run gp is absent -> 0 -> conf=1.0 and no early-season dampening ever fires. The feature only does anything when the EdgeModel custom engine injects GP. The docstring/comment present it as an always-on guard ('penalizes early-season or low-sample players').

**Recommendation:** Confirm whether SaberSim CSVs should carry GP; if not, document that I6 is EdgeModel-path-only, or source GP/games-played from the projection DB so the penalty applies on both paths.

**Verifier (confirmed):** Verified against live code. evaluators.py:104 reads gp = proj_player.get("GP", proj_player.get("gp", 0)); the conf branches are gated on truthy gp, so gp absent -> 0 -> conf=1.0 and no dampening. proj_player is set at evaluators.py:50 to the dict produced by parse_csv. parse_csv (odds_io.py:96-118) builds the player dict from a fixed column whitelist (name/team/opp/pos/saber_total/saber_team/status + per-sport stats + dk_std/pts_cv/cold_start_subtype/injury_trigger) and never sets GP; the raw al


## Confirmed-correct / coverage notes

- **Live-money boundary is correctly enforced**: run_picks.py:1159-1167 strips all pick_type=='game_line' picks (TOTAL/SPREAD/ML/TEAM_TOTAL/F5_*) from the live card unless the stat is in SHADOW_STATS. So the live path is props (evaluate_props) + the longshot/value/alt-spread parlay builders + premium card; game-line evaluators feed only correlation filtering and shadow logging. This materially lowers the severity of any spread/ML/F5/total math issues.
- **Spread / ML / total cover-probability math is directionally correct**: spread cover_prob = 1 - normal_cdf(-sp_line, team_margin, sigma) (evaluators.py:372) correctly models 'covers if margin > -line'; ML win_prob = 1 - normal_cdf(0, team_margin, sigma) (501); MLB ML uses NB direct-sum mlb_ml_from_nb anchored to no-vig via BLEND_ALPHA (495-499) and explicitly uses the wider ml sigma not spread sigma (435).
- **Integer vs half-line push handling for MLB team totals is correct** (evaluators.py:558-565): integer lines divide by non-push mass; half-lines use the plain NB CDF.
- **NRFI no-vig is computed from both sides** (evaluators.py:1010-1018, FIX M2) rather than vigged implied, with a documented single-side fallback; lambda clamped to [0.05,0.90] and the multiplier clamped to >=0 before the fractional exponent (983-988) to avoid the complex-number TypeError on elite-K negative FIP.
- **MLB pitcher confirmation gate** (evaluators.py:73-76) correctly suppresses K/OUTS/HA props when the starter is unconfirmed; mirrored by the MLB Stats API patch in run_picks _stage_load_csvs (774-794).
- **Concurrency/locking**: filelock is a hard dependency (no silent fallback, run_picks.py:35-41); a process-level FileLock prevents concurrent runs / double-posts (1012-1017); pick_log appends are guarded by _pick_log_lock with flush+fsync (1522-1539).
- **Cap stacking after KILLSHOT sizing is handled**: the combined premium+KILLSHOT 12u re-check (run_picks.py:1305-1310) and the per-sport re-check (1312-1327) correctly run AFTER KILLSHOT VAKE sizing, which apply_caps did not see.
- **--no-cap is guarded to require --no-discord** (run_picks.py:998-1000), preventing accidental full-pool logging into the live ledger during a real Discord run.
- **Tier-floor consistency**: the hardcoded 0.05 total-edge floor (evaluators.py:311) equals TIERS['T2']['min_edge']=0.05 (calibrated.py:275); team totals correctly reference TIERS['T2']['min_edge'] directly (602-603).
- **Known calibration gates acknowledged in-code and excluded**: WNBA Platt approximation (evaluators.py:119-122) and the EdgeModel sigma/temperature overconfidence are the documented open gate, not novel bugs.

## Not-Done / incomplete (this module)

| Kind | File | Detail |
|------|------|--------|
| todo | evaluators.py | Line 123: TODO refit combo (PRA/PR/PA/RA) Platt at SGP Platt gate (100 scored slips) — combos currently skip Platt and are ~5pp inflated. |
| deferred | evaluators.py | Lines 853-858: NRFI_GAMMA DATA_GATED — recalibrate (predicted mult vs realized NRFI) on the in-house 8,095-game DB when first-inning-level data exists. |
| todo | evaluators.py | Lines 866-867: TODO — if SaberSim source switches to park-neutral inputs, replace _LEAGUE_AVG_BLENDED_RATE with a park-adjusted league avg and apply MLB_PARK_FA |
| partial-feature | evaluators.py | I6 confidence penalty (lines 100-113) is inert on the SaberSim CSV path because parse_csv never sets GP; only fires when the EdgeModel projector injects GP. |
| flag-gated | evaluators.py | Lines 115-127: WNBA Platt uses NBA+NHL coefficients pending a WNBA-specific refit (known sigma/Platt calibration gate). |
| dead-code | evaluators.py | evaluate_props cooldown_players parameter accepted but never referenced; R12 cooldown is applied separately in run_picks.main via apply_r12_cooldown. |
| flag-gated | calibrated.py | USE_NO_VIG_ANCHOR=False (line 291) — Track-B no-vig BM anchor intentionally gated off until n>=150 CLV + sign-off; flag-off path byte-identical (known/expected) |
| deferred | calibrated.py | MLB GAME_SIGMA (line 187) flagged interim per Plan 10 §O — recalibrate from the 8095-game DB like NBA/NHL. Game-line only (dropped from live card). |
