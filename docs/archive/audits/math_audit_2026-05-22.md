# JonnyParlay Math Audit — 2026-05-22
**Scope:** Full engine (~26k lines) — all markets, formulas, gates, and calculations  
**Auditors:** 5 parallel Claude Sonnet 4.6 agents  
**Files audited:** engine/run_picks.py, engine/sgp_builder.py, engine/nba_projector.py, engine/projections_db.py, engine/capture_clv.py, engine/generate_projections.py, engine/mlb_starter_fetcher.py  
**Total findings:** 123 (across 17 sections)  
**Detail files:** docs/audits/math_audit_s1_4.md · s5_8.md · s9_10.md · s11_13.md · s14_17.md

---

## ⚠ Issues & Uncertainties — Summary

### FIXED (during this audit)
| ID | File:Line | Issue |
|----|-----------|-------|
| **1.5** | engine/run_picks.py:4499 | `_implied_prob` undefined in `post_daily_lay` — NameError crashed every daily lay post. Fixed to `implied_prob` (already defined at line 647). |

### ACTIONABLE ISSUES

| ID | Severity | File:Line | Issue | Fix |
|----|----------|-----------|-------|-----|
| **5.6** | Moderate | run_picks.py:6447 | KILLSHOT 3–4u re-sizing skips SPORT_UNIT_CAP re-check. A 4u KILLSHOT + 5 × 1.25u premium = 10.25u NBA, exceeding the 8u cap. Only the 12u daily total is re-enforced post-KILLSHOT. | Add SPORT_UNIT_CAP re-check after KILLSHOT sizing at line 6452, or explicitly document KILLSHOT as exempt. |
| **9.15** | Low | run_picks.py:5867 | `_STAT_MIN_WIN_PROB = {"TB": 0.60}` in the sanity checklist checks for a TB WP≥60% G13B gate that does not exist in `check_prop_gates`. A TB pick with WP=0.55 passes all real gates but marks the verification table ✗ (false positive). | Either add `if stat == "TB" and prob < 0.60: return False, "G13B"` to `check_prop_gates`, or remove `"TB"` from `_STAT_MIN_WIN_PROB`. |
| **11.12** | Low | run_picks.py:3036 | `er_per_ip = p.get("ER", 0) / ip` — if `p["IP"]` was set to `0.0` by the CSV parser (missing column), this raises `ZeroDivisionError`. The `fip_raw` formula two lines later guards with `if ip > 0 else 4.50`, but `er_per_ip` does not. | Change `ip = p.get("IP", 1)` to `ip = p.get("IP", 1) or 1.0` (one character). |
| **9.4** | Low | run_picks.py:937 | G8's SOG under exception (`pass` block for WP≥0.80, edge≥0.15) is dead code — G4 (`line≤2.5 AND prob>0.75`) always catches these picks first. The "allow through" comment is misleading. | Remove the `if stat == "SOG" ...` exception block and update the comment. |
| **14.9** | Minor | nba_projector.py:1464 | `compute_ast_rate()` normalises ALL historical training games by the current game's `game_pace` (a single scalar) instead of each game's own pace. Systematic bias ≈ −6.7% on AST rate for players whose historical opponents differed by ~5 pace from today. | Pass per-game opponent pace from `df_clean` if it exists as a column. |

### DOCUMENTATION / DEAD CODE (deferred OK)

| ID | File:Line | Issue |
|----|-----------|-------|
| 6.8 | run_picks.py:184 | `MIN_DAILY_LAY_PROB=0.47` inline comment claims "positive Kelly at -130 to +100". Math: Kelly is negative throughout that range at 47% probability. The `0.25u` floor in `size_daily_lay` handles this correctly. Update comment to reflect actual rationale. |
| 6.9 / 9.31 | run_picks.py:3677 | Daily lay edge uses raw vigged implied prob; prop pipeline uses `no_vig()`. Conservative (harder to pass 0.025 threshold), not dangerous. Alt-spread data is one-sided, making no-vig difficult. |
| 7.2 | sgp_builder.py:408 | `_copula_joint_approx` docstring claims "Error < 3%" but measured error is ~17% at ρ=0.30 (3 legs at 0.70 each: approx=0.450, MC=0.385). Only affects combo ranking search, not final sizing (which uses full MC). Update docstring to "~15–20% for ρ∈[0.20, 0.35]". |
| 9.29 | run_picks.py:5860 | `has_g8_fail` sanity check flags SOG at line≤1.5 without the G8 exception; moot since the exception is dead code (Finding 9.4). |
| 10.2 | run_picks.py:200 | `PTS` in `KILLSHOT_STAT_ALLOW` can never auto-qualify (PTS is T2; tier check fires first). PTS KILLSHOTs are manual-only. Add comment noting this. |
| 11.3 | run_picks.py:992 | 25%+ HRR edge on O0.5 is expected structural inflation from NB(r=1.5) over-predicting P(X≥1) at ~72% vs empirical 57.4%. G13B WP floor of 0.58 manages the risk. Monitor vs more shadow data before widening G2 further. |
| 11.6 | run_picks.py:3027 | NRFI uses full-game team run projections (`_LEAGUE_AVG_RUNS=4.39`) as proxy for 1st-inning scoring rates. Directionally correct but imprecise — 1st-inning rates are pitcher-driven, not full-game-offense-driven. Low priority model approximation. |
| 11.11 | mlb_starter_fetcher.py:94 | Return type annotation `-> dict[str, str]` is wrong; implementation returns `dict[str, list[str]]` (supports doubleheaders). No runtime impact. |
| 11.14 | run_picks.py:1005 | G14 comment still lists HRR as a SIGMA stat; HRR was moved to NB_STATS. Update comment. |
| 11.15 | run_picks.py:277 | `SIGMA["HITS"]` is dead — HITS is in `POISSON_STATS` so Poisson always fires first. Same pattern as `SIGMA["SOG"]` (Finding 13.2). Add `# dead: POISSON_STATS takes priority` or remove. |
| 12.4 | run_picks.py:959 | Pre-season WNBA (season_day ≤ 0) passes `G_WNBA_OPEN` (which only fires for days 1–3). In practice SaberSim doesn't generate pre-season CSVs; theoretical gap only. |
| 13.2 | run_picks.py:269 | `SIGMA["SOG"]` dead entry (same as HITS — Poisson takes precedence). |
| 15.2 | capture_clv.py:870 | CLV uses raw vigged implied probs on both sides; direction is preserved but magnitude is slightly compressed vs vig-free CLV. Standard industry practice. |
| 16.3 | run_picks.py:5907 | `format_output` cap validation excludes same-session SGP/daily_lay/longshot (~0.75–1.25u). Real cap still enforced on next-sport cross-run read; display-only gap. |
| 17.3 | run_picks.py:1118 | R12 cooldown has no sport filter; cross-sport false cooldown theoretically possible. Near-zero practical risk given naming divergence. |

### UNCERTAIN (low risk, worth noting)

| ID | File:Line | Issue |
|----|-----------|-------|
| 3.3 | run_picks.py:2248 | Platt scaling applied to WNBA (not MLB exclusion-only). Platt was fit on NBA+NHL data. WNBA has higher PTS CV. Better than no calibration, but undocumented as intentional. Shadow-only currently. |
| 7.7 | sgp_builder.py:738 | SGP premium gate `copula_joint - parlay_implied ≥ 0.10` uses vigged `parlay_implied`. ~3–8 pp of the 10 pp gap is expected vig removal, not model alpha. Gate may be more permissive than intended for low-edge combos. |

---

## Section-by-Section Findings

### Section 1 — Implied Probability & Edge ✅

**All math correct.** One runtime bug found and fixed.

| Finding | Verdict |
|---------|---------|
| 1.1 American odds → implied prob (`abs(odds)/(abs(odds)+100)`, `100/(odds+100)`) | CORRECT |
| 1.2 No-vig removal: additive normalization `imp1/total, imp2/total` | CORRECT |
| 1.3 Edge always uses no-vig, never raw implied (`calc_edge` → `no_vig`) | CORRECT |
| 1.4 NRFI edge uses no-vig (M2 fix in place) | CORRECT |
| **1.5 `_implied_prob` undefined in `post_daily_lay` — NameError on every daily lay post** | **FIXED** |
| 1.6 ML fixed-spread blending uses ML no-vig as anchor (correct for NHL/MLB) | CORRECT |

---

### Section 2 — Over Probability Per Stat ✅

**All distributions correct.** Push-adjustment, CDF direction, and continuity corrections verified across all stat types.

| Finding | Distribution | Verdict |
|---------|-------------|---------|
| 2.1 NBA/WNBA PTS, REB, AST | Normal, SIGMA/SIGMA_WNBA | CORRECT |
| 2.2 NBA/WNBA AST, REB + NHL SOG, MLB HITS (Poisson ≤8.5) | Poisson + push-adjust on integer lines | CORRECT |
| 2.3 NBA 3PM, MLB HRR, MLB K | NB(r=12.3/1.5/5.0) + push-adjust | CORRECT |
| 2.4 MLB TB | Poisson convolution — `threshold = floor(line)+1` → `P(TB≥threshold)` | CORRECT |
| 2.5 MLB HITS, HA | Poisson (HITS) / Normal (HA) | CORRECT |
| 2.6 MLB K (NB, overs only, line≥6.0) | NB(r=5.0) | CORRECT |
| 2.7 MLB OUTS | Normal sigma mult=0.30 min=3.0 | CORRECT |
| 2.8 NRFI/YRFI: `P(NRFI) = (1-p_away)(1-p_home)`, BASE_SCORING_RATE=0.1633 = `1-√0.70` | Custom model | CORRECT |
| 2.9 NHL SOG | Poisson (same path as AST/REB) | CORRECT |
| 2.10 WNBA PTS/AST/REB/3PM | SIGMA_WNBA overrides; 3PM → Normal (not NB, underdispersed) | CORRECT |
| 2.11 Combo stats (PRA/PR/PA/RA) | Correlated Normal `Var = ΣVar + 2ρσᵢσⱼ` | CORRECT |

---

### Section 3 — Platt Scaling ✅

All correct. One uncertain item (WNBA).

| Finding | Verdict |
|---------|---------|
| 3.1 Formula `1/(1+exp(-(A*p+B)))` with clamp [-30, 30] | CORRECT |
| 3.2 Applied to NBA + NHL (not MLB) | CORRECT |
| 3.3 Also applied to WNBA (undocumented; NBA+NHL coefficients) | UNCERTAIN — low risk, shadow only |
| 3.4 Input is raw `over_p` before direction selection; `over_p_raw` saved for refit | CORRECT |
| 3.5 Applied after all distribution paths (TB convolution, combo, standard) | CORRECT |

---

### Section 4 — Pick Score ✅

| Finding | Verdict |
|---------|---------|
| 4.1 `score = sw*(wp_n) + ew*(e_n)` where `wp_n=(WP-50)/25*100`, `e_n=edge/0.15*100` | CORRECT |
| 4.2 Props use `adj_edge` (confidence-adjusted), game lines use raw edge | CORRECT |
| 4.3 Tier multiplier before additive cold-start penalty and injury bonus | CORRECT |
| 4.4 No sport-specific scoring; sport variation captured upstream in tiers/sigmas | CORRECT |
| 4.5 WNBA early-season edge dampener used in G_WNBA_EDGE gate but NOT in pick_score/sizing | ISSUE (minor, shadow only) |
| 4.6 Tier fallback = 1.00 for KILLSHOT/DAILY_LAY/SGP/LONGSHOT | CORRECT |

---

### Section 5 — VAKE Sizing ✅

| Finding | Verdict |
|---------|---------|
| 5.1 VAKE_BASE tiers (3/5/7/9% edge → 0.50/0.75/1.00/1.25u) | CORRECT |
| 5.2 Variance and tier multipliers (T1=1.00, T2=0.85×0.90, T3=0.65×0.60) | CORRECT |
| 5.3 Correlation multiplier (1st game: 1.00, 2nd: 0.85, 3rd+: 0.70; pitcher: ×0.70) | CORRECT |
| 5.4 Exposure multiplier (1st same-stat: 1.00, subsequent: 0.70) | CORRECT |
| 5.5 Caps: min(raw, 1.25u) then max(result, 0.50u) | CORRECT |
| **5.6 SPORT_UNIT_CAP not re-enforced after KILLSHOT 3–4u re-sizing** | **ISSUE** |
| 5.7 SPORT_UNIT_CAP = {NBA:8u, WNBA:4u, NHL:5u, MLB:8u} enforced in apply_caps | CORRECT |
| 5.8 `round_units` → nearest 0.25u | CORRECT |

---

### Section 6 — Daily Lay Sizing & Math ✅

| Finding | Verdict |
|---------|---------|
| 6.1 Kelly: `f* = (p·b − q)/b`, b = decimal_odds − 1 | CORRECT |
| 6.2 Quarter Kelly (0.25 fraction) | CORRECT |
| 6.3 Caps: min(Kelly, 0.75u), max(result, 0.25u) | CORRECT |
| 6.4 Combined probability = product of independent leg `alt_cover_prob` | CORRECT |
| 6.5 Per-leg gates: `edge < 0.025 → skip`, `cover_prob < 0.58 → skip` | CORRECT |
| 6.6 Max combined odds +100 (`parlay_odds > 100 → reject`) | CORRECT |
| 6.7 `MIN_DAILY_LAY_PROB=0.47` gate applied before sizing | CORRECT |
| **6.8 MIN_DAILY_LAY_PROB=0.47 comment claims "positive Kelly at −130 to +100" — false** | **DOC ISSUE** |
| **6.9 Daily lay edge = `cover_prob − raw_vigged_implied` (not no-vig, unlike props)** | **MINOR ISSUE** |
| 6.10 `cover_prob = 1 − Φ(−line; margin, σ)` — correct for P(margin > line) | CORRECT |

---

### Section 7 — SGP Math ✅

| Finding | Verdict |
|---------|---------|
| 7.1 Gaussian copula MC: `Lε` → correlated normals → `Φ(xᵢ) ≤ pᵢ` hits | CORRECT |
| **7.2 `_copula_joint_approx` docstring claims "Error < 3%" — actual error ~17% at ρ=0.30** | **DOC ISSUE** |
| 7.3 pairwise_rho hierarchy (0.35 same-team offense → −0.20 opposite direction) | CORRECT |
| 7.4 COMBO_RHO / COMBO_RHO_WNBA routing by sport | CORRECT |
| 7.5 SGP odds range gate: `< +200 or > +450 → reject` | CORRECT |
| 7.6 Premium sizing: avg_edge≥0.035 AND cohesion≥0.55 AND copula_joint − implied≥0.10 | CORRECT |
| 7.7 Premium gate compares model copula_joint to vigged parlay_implied; ~3–8 pp is vig removal, not alpha | UNCERTAIN |
| 7.8 win_prob left blank in SGP log rows (joint prob shown in embed) | CORRECT |

---

### Section 8 — Longshot Math ✅

| Finding | Verdict |
|---------|---------|
| 8.1 Combined prob = ∏ win_probs (independence; per-game cap reduces correlation) | CORRECT |
| 8.2 LONGSHOT_MAX_PER_GAME=2: `count ≥ 2 → skip` (allows exactly 2 per game) | CORRECT |
| 8.3 `prob_to_american` is dead code; displayed odds use actual book decimal product | CORRECT |
| 8.4 Decimal odds: positive `1+o/100`, negative `1+100/|o|` | CORRECT |
| 8.5 Fixed 0.25u size regardless of combined probability | CORRECT |

---

### Section 9 — All Gate Formulas

| Finding | Gate | Verdict |
|---------|------|---------|
| 9.1 | G3 missing_side | CORRECT |
| 9.2 | G7 hard juice `odds ≤ −150` | CORRECT |
| 9.3 | G7b soft juice `odds ∈ [−149, −140] AND edge < 0.09` | CORRECT |
| **9.4** | **G8 SOG under exception** | **ISSUE — dead code; G4 always blocks first** |
| 9.5 | G8B AST over ≤4.5 (WNBA exempt) | CORRECT |
| 9.6 | G_WNBA_OPEN: days 1–3 blocked | CORRECT |
| 9.7 | G_WNBA_EDGE: multiplier then 0.035 floor | CORRECT |
| 9.8 | G_K_NO_UNDERS | CORRECT |
| 9.9 | G_K_MIN_LINE ≥6.0 | CORRECT |
| 9.10 | G_OUTS_UNDER | CORRECT |
| 9.11 | G_HA_DIR (overs blocked) | CORRECT |
| 9.12 | G9 universal edge floor 3% | CORRECT |
| 9.13 | G13 WP < 0.50 | CORRECT |
| 9.14 | G13B HRR: 0.58 at line≤0.5, 0.65 at line>0.5 | CORRECT |
| **9.15** | **G13B TB: WP≥0.60 in checklist but NO gate in check_prop_gates** | **ISSUE — false ✗ in verification** |
| 9.16 | G14 clearance `z = (proj − line)/σ ≥ 0.10` | CORRECT |
| 9.17 | G15 HIGH-VAR 3PM (pts_cv ≥ 0.60) | CORRECT |
| 9.18 | G1 high prob + bad odds | CORRECT |
| 9.19 | G2 edge ceiling 20% (28% for soft O0.5) | CORRECT |
| 9.20 | G4 extreme prob at low line | CORRECT |
| 9.21 | G5 positive odds + high WP | CORRECT |
| 9.22 | G10 low-line under needs 8% edge | CORRECT |
| 9.23 | GG1 game line edge ceiling 10% | CORRECT |
| 9.24 | GG2 projection deviation `|proj±line|/σ ≤ 1.5` | CORRECT |
| 9.25 | GG3 positive edge required | CORRECT |
| 9.26 | GG4 game line missing side | CORRECT |
| 9.27 | GG5 no dog-cover spreads | CORRECT |
| 9.28 | TIER_MIN per-tier minimum edge post-G9 | CORRECT |
| 9.29 | has_g8_fail sanity check | ISSUE (moot; G8 exception dead) |
| 9.30 | Daily lay per-leg gates | CORRECT |
| 9.31 | Daily lay vigged edge | UNCERTAIN (conservative direction) |
| 9.32 | NRFI/YRFI min edge (6%/8%) | CORRECT |
| 9.33 | F5 total T1B 3% min edge | CORRECT |
| 9.34 | Spread/ML/TT min edges (sport-specific) | CORRECT |

---

### Section 10 — KILLSHOT Gate ✅

All 5 gate conditions, sizing, weekly cap, and manual override verified correct.

| Finding | Verdict |
|---------|---------|
| 10.1 Tier = T1 strict (T1B/T2/T3 fail) | CORRECT |
| 10.2 PTS in KILLSHOT_STAT_ALLOW is dead for auto-qualify (PTS is T2) | ISSUE (doc) |
| 10.3 Score ≥ 65 | CORRECT |
| 10.4 WP ≥ 0.65 | CORRECT |
| 10.5 Odds ∈ [−200, +110] (−200 bound superseded by G7 for auto-qualify) | CORRECT |
| 10.6 Stat ∈ {PTS, AST, SOG} | CORRECT |
| 10.7 4u bump: WP ≥ 0.70 AND edge ≥ 0.06 (both required) | CORRECT |
| 10.8 Weekly cap: rolling 7 days `[today−6, today]` | CORRECT |
| 10.9 Cap fail-safe: error → assume full cap (safe direction) | CORRECT |
| 10.10 Manual override: score ≥ 75, counts toward weekly cap | CORRECT |
| 10.11 KILLSHOTs excluded from Premium 5 card | CORRECT |
| 10.12 12u daily cap includes KILLSHOT units | CORRECT |

---

### Section 11 — MLB-Specific Math

| Finding | Verdict |
|---------|---------|
| 11.1 HRR projection = H + R + RBI from SaberSim columns | CORRECT |
| 11.2 HRR uses NB(r=1.5) — correct for zero-inflated count | CORRECT |
| **11.3 25%+ edge at HRR O0.5 is NB model inflation (empirical 57.4% vs NB ~72%)** | **ISSUE (documented/gated)** |
| 11.4 K/OUTS/HA gated on confirmed-starter; starter API fallback fails safely | CORRECT |
| 11.5 NRFI independence: P(NRFI) = P(away=0) × P(home=0) | CORRECT |
| **11.6 NRFI uses full-game runs as 1st-inning proxy (approximation)** | **MINOR ISSUE** |
| 11.7 NRFI no-vig edge (M2 fix in place) | CORRECT |
| 11.8 F5 total: 0.503 scaling + BLEND_ALPHA anchoring | CORRECT |
| 11.9 F5 ML: margin = (t1−t2)×0.503; blended to ML no-vig | CORRECT |
| 11.10 F5 spread cover probability | CORRECT |
| **11.11 `fetch_confirmed_starters` type annotation wrong** | **DOC ISSUE** |
| **11.12 `er_per_ip = p.get("ER", 0) / ip` unguarded when ip=0.0** | **ISSUE (ZeroDivision)** |
| 11.13 NRFI skips when no confirmed pitcher for either team | CORRECT |
| **11.14 G14 comment lists HRR as SIGMA stat (stale)** | **DOC ISSUE** |
| **11.15 SIGMA["HITS"] dead config (Poisson takes priority)** | **DEAD CODE** |
| 11.16 FIP formula `(13×HR + 3×BB − 2×K)/IP + 3.17` | CORRECT |
| 11.17 OUTS under gate consistent with NB model | CORRECT |

---

### Section 12 — WNBA-Specific Math ✅

| Finding | Verdict |
|---------|---------|
| 12.1 WNBA_EARLY_SEASON_EDGE_MULT loop (days 4–14 → 0.80×, 15–21 → 0.90×, 22+ → 1.0) | CORRECT |
| 12.2 WNBA_EDGE_FLOOR=0.035 > standard G9 3% floor | CORRECT |
| 12.3 WNBA_OPENING_GATE_DAYS=3 date arithmetic (`today - start + 1 days`) | CORRECT |
| 12.4 Pre-season WNBA (season_day ≤ 0) not blocked by G_WNBA_OPEN | UNCERTAIN (low risk) |
| 12.5 G_WNBA_EDGE applies multiplier then checks floor | CORRECT |
| 12.6 SIGMA_WNBA values calibrated to WNBA CVs | CORRECT |
| 12.7 COMBO_RHO_WNBA (0.04–0.13) correctly routed and applied in variance formula | CORRECT |
| 12.8 WNBA 3PM → Normal (not NB); underdispersed (var/mean ~0.70) | CORRECT |
| 12.9 G14 uses SIGMA_WNBA for WNBA sigma consistency | CORRECT |

---

### Section 13 — NHL-Specific Math ✅

| Finding | Verdict |
|---------|---------|
| 13.1 SOG uses Poisson distribution (correct for shot count data) | CORRECT |
| **13.2 SIGMA["SOG"] dead config (Poisson takes priority)** | **DEAD CODE** |
| 13.3 Goalies filtered at parse time; no goalie save props in scope | CORRECT |
| 13.4 NHL AST → T3 (binary market, 20%+ hold) | CORRECT |
| 13.5 SOG STAT_CAP=6, SPORT_UNIT_CAP=5u | CORRECT |
| 13.6 G8 SOG under exception (high-conviction carve-out) | CORRECT (but dead code per 9.4) |
| 13.7 GAME_SIGMA["NHL"]["ml"]=4.0 prevents inflated ML win probs from ±1.5 spread sigma | CORRECT |
| 13.8 NHL/MLB treated as fixed-spread sports (ML no-vig anchors, not spread line) | CORRECT |
| 13.9 INJURY_TRIGGER_BONUS["SOG"]=8 consistent with comparable stats | CORRECT |
| 13.10 KILLSHOT allows SOG with T1/WP/score gates | CORRECT |

---

### Section 14 — NBA Projection Pipeline ✅

| Finding | Verdict |
|---------|---------|
| 14.1 Minute scalar order: EWMA → RS/PO scalar → cold_start cap → bump → role cap | CORRECT |
| 14.2 Rate deflators applied to final projections after all other adjustments | CORRECT |
| 14.3 Home/away: `proj × (1 ± delta)`, TOV negative delta correct direction | CORRECT |
| 14.4 Blowout sigmoid `L/(1+exp(−k(spread−mid)))`, k=0.15, mid=20, L=0.19 | CORRECT |
| 14.5 Vegas team-total constraint: proportional scaling clipped [0.80, 1.20]; proj_min excluded | CORRECT |
| 14.6 5-position Bayesian priors (REB/AST/STL/BLK/TOV): rank-orderings correct | CORRECT |
| 14.7 EWMA: `α=2/(span+1)`, weight `(1−α)^(n−1−i)` → recent games highest weight | CORRECT |
| 14.8 PLAYOFF_RATE_DEFLATORS applied multiplicatively after all other adjustments | CORRECT |
| **14.9 `compute_ast_rate()` normalises ALL historical games by current game_pace, not each game's own pace — systematic bias ~5–7%** | **MINOR ISSUE** |
| 14.10 240-minute lineup-protected constraint logic | CORRECT |

---

### Section 15 — CLV Calculation ✅

| Finding | Verdict |
|---------|---------|
| 15.1 `CLV = closing_implied − your_implied`; positive = beat the close | CORRECT |
| 15.2 No vig removal on CLV (both sides vigged; direction preserved, magnitude slightly compressed) | ISSUE (design choice, standard practice) |
| 15.3 Implied prob formula identical to run_picks.py | CORRECT |

---

### Section 16 — Daily Cap Accumulation ✅

| Finding | Verdict |
|---------|---------|
| 16.1 `_units_bet_today()` reads all non-manual prior runs; passed as `units_already_bet` to `apply_caps` | CORRECT |
| 16.2 KILLSHOT logged as `run_type=primary`; counted in both cross-run and in-session cap checks | CORRECT |
| 16.3 `format_output` cap display excludes SGP/daily_lay/longshot (~0.75–1.25u same session) | MINOR (display only) |

---

### Section 17 — R12 Cooldown ✅

| Finding | Verdict |
|---------|---------|
| 17.1 Lookback: `cutoff = today − 5 days`; window = [cutoff, today) exactly 5 days | CORRECT |
| 17.2 `normalize_name()` applied on both sides of comparison | CORRECT |
| 17.3 No sport filter in `auto_r12_from_log`; cross-sport false cooldown theoretically possible | ISSUE (negligible) |
| 17.4 Cooldown applied before qualified/failed split (suppresses entirely) | CORRECT |

---

## Recommended Fix Priority

### Fix immediately
1. **11.12** — One-line fix: `ip = p.get("IP", 1) or 1.0` closes a ZeroDivisionError path in NRFI pitcher building.
2. **9.15** — TB WP gate: either add `if stat == "TB" and prob < 0.60: return False, "G13B"` to `check_prop_gates`, or remove `"TB"` from `_STAT_MIN_WIN_PROB` checklist to eliminate false positives.
3. **9.4** — Remove dead G8 SOG exception block; it misleads about what gets through.

### Fix when convenient
4. **5.6** — Add SPORT_UNIT_CAP re-check after KILLSHOT sizing, or document KILLSHOT as explicitly exempt.
5. **6.8** — Update MIN_DAILY_LAY_PROB=0.47 comment to reflect accurate rationale.
6. **7.2** — Correct `_copula_joint_approx` docstring from "Error < 3%" to "~15–20% for ρ∈[0.20, 0.35]".
7. **10.2** — Add comment to `KILLSHOT_STAT_ALLOW` noting PTS is manual-only.
8. **14.9** — Consider per-game pace normalisation in `compute_ast_rate()` for more accurate AST rate training.

### Clean up (dead code / stale comments)
- 11.14: Update G14 comment (HRR no longer in SIGMA)
- 11.15 / 13.2: Add `# dead: POISSON_STATS takes priority` to SIGMA["HITS"] and SIGMA["SOG"]
- 16.3: Add SGP/daily_lay/longshot to `format_output` cap validation total

---

## Overall Assessment

**The engine's core math is sound.** American odds conversion, no-vig removal, edge calculation, distribution selection (Normal / Poisson / NB / copula), Platt scaling, Kelly sizing, and KILLSHOT gating are all implemented correctly.

**One runtime bug was identified and fixed during this audit** (1.5 — `_implied_prob` NameError in `post_daily_lay`).

**The most impactful open items** are the SPORT_UNIT_CAP KILLSHOT bypass (5.6), the TB gate/checklist mismatch (9.15), and the ZeroDivision in er_per_ip (11.12). All three are straightforward fixes.
