# Audit 2026-05-25 — End Summary (v2 — post REB/AST→NB + SIGMA re-verification)

Auditor: Claude Sonnet 4.6 (original 12-agent audit + fresh re-verification session)
Tracks: A–L (all completed and re-verified against 2026-05-25 code changes)
n=182 settled primary/bonus picks; n=53 CLV samples

## Re-Verification Closures (this session)

The following findings from the original audit were CLOSED by 2026-05-25 code changes:

| Finding | Was | Closed By |
|---------|-----|-----------|
| A-1: AST sigma fallback in combo path | HIGH | SIGMA["AST"]={mult:0.53,min:2.0} added for combo path |
| B-1 / I-2 / L-1: CLAUDE.md wrong Platt formula space | CRITICAL (×3) | CLAUDE.md updated to raw-probability space |
| D-2: CLAUDE.md wrong Platt space (Track D ref) | MEDIUM | Same as B-1 |
| F-1: pick_score uses pre-confidence win_prob | MEDIUM | Line 2370 now passes adj_wp confirmed |
| G-3: sgp_builder NB_R["3PM"]=2.1 vs 9.15 | HIGH | Both files now 9.15 (recalibrated 2026-05-25) |
| G-4: AST uses wrong distribution in sgp_builder | HIGH | AST in NB_STATS(r=9.68) in sgp_builder confirmed |
| H1 (below): G-3+G-4 combined as "sgp_builder distribution sync" | HIGH | CLOSED |

New findings added this re-verification session:
- G-7 (MEDIUM): sgp_builder SIGMA["PTS"] min=4.5 vs run_picks.py min=5.0 (not updated 2026-05-25)
- G-8 (LOW): size_sgp Gate 1 docstring says "≥10pp margin" but code checks any positive margin (M8 two-gate not documented in docstring)

---

---

## 1. Fix List — CRITICAL First

### CRITICAL

| # | Track | File | Line | Description |
|---|-------|------|------|-------------|
| ~~C1~~ | B, I, L | CLAUDE.md + run_picks.py | ~357–371, ~649 | ~~**Platt formula space wrong in CLAUDE.md.**~~ **CLOSED 2026-05-25.** CLAUDE.md now correctly says raw-probability space. See B-1, I-2, L-1 in track files. |
| C2 | J | data/pick_log.csv | — | **Mean CLV = −0.758%, beat rate 20.8% (n=53).** Market consistently moves against picks. This is the primary evidence of no edge. All other findings are secondary until this is investigated. |

### HIGH

| # | Track | File | Line | Description |
|---|-------|------|------|-------------|
| ~~H1~~ | G | sgp_builder.py | ~71, ~79 | ~~**AST uses wrong distribution in sgp_builder** (Poisson→Normal instead of NB r=9.68). Also NB_R["3PM"]=2.1 in sgp_builder vs 9.15 in run_picks.~~ **CLOSED 2026-05-25.** Both G-3 (NB_R["3PM"]) and G-4 (AST distribution) fixed. sgp_builder now synced. |
| H2 | I | calibrate_platt.py + run_picks.py | ~100–119 | **H3 migration is a manual paste with no mechanical guard.** Formula change and constants must be done atomically; one without the other corrupts all win_probs. calibrate_platt.py should print a single atomic copy-paste block. |
| H3 | I | calibrate_winprob.py vs calibrate_platt.py | ~61–78 | **Both scripts produce visually identical A/B output headers.** calibrate_winprob.py (double-calibration if pasted) looks like calibrate_platt.py (correct). Rename outputs to distinguish. |
| H4 | I | run_picks.py + nb_calibrate.py | ~298, nb_cal ~21 | **K (r=5.0) is an undocumented estimate** with CV 35–100% too wide vs empirical. Live in production for K overs ≥ 6.0. nb_calibrate.py doesn't cover K; CURRENT dict is stale. |
| H5 | I | run_picks.py | ~289 | **HRR r=1.5 uses inferior single-point methodology** — moment-matching at one (μ, line) pair, not within-player avg(var/mu). HRR is disabled so dormant, but would produce +14pp error if re-enabled. |
| H6 | J | pick_log.csv + ops | — | **47% of picks placed at 19:xx (near tip); CLV at 19:xx = −1.52% vs +1.03% at 15:xx.** Moving run to noon ET is the single most actionable hypothesis. No model change required. |
| H7 | J | run_picks.py | no trigger | **No manual review trigger for edges 10–20%.** 65 picks (26%) exceed 15% edge with no reconciliation step. Market moves against these (negative CLV) suggesting projection errors, not genuine edge. |
| H8 | C | run_picks.py | ~1927–1962 | **Multiple lines per player/stat all evaluated independently.** Engine can post alternate lines (e.g., 24.5 instead of market consensus 25.5), doubling positive bias. No line-selection step before building the best-odds dict. |
| H9 | J | data/pick_log.csv | — | **n=244 insufficient for reliable model assessment.** Only 2 stat-direction buckets have n≥30. Any segment conclusions are statistically unreliable. Target 500 singles before drawing calibration conclusions. |
| H10 | I | run_picks.py | ~263–277 | **No calibrate_sigma.py exists.** SIGMA mult values for PTS, REB, REC, OUTS, HA have no reproducible calibration script. G_OUTS_UNDER gate is evidence SIGMA["OUTS"] is still miscalibrated. |

### MEDIUM (selected — see individual track files for full lists)

| # | Track | File | Line | Description |
|---|-------|------|------|-------------|
| ~~M1~~ | A | run_picks.py | ~772 | ~~AST sigma uses uncalibrated fallback in combo path.~~ **CLOSED 2026-05-25.** SIGMA["AST"]={mult:0.53,min:2.0} added. See A-1. |
| M2 | B | run_picks.py | ~2728–2730 | TEAM_TOTAL over block fires for ALL sports despite only NBA empirical basis (n=11). NHL/MLB TEAM_TOTAL overs blocked without evidence. |
| M3 | C | run_picks.py | ~1490–1503 | Local name_key() in run_picks.py duplicates name_utils.name_key() — silent drift risk if name_utils is updated. |
| M4 | D | run_picks.py | ~2728–2730 | (same as M2 — cross-sport over block) |
| ~~M5~~ | F | run_picks.py | ~2369 | ~~pick_score() uses pre-confidence win_prob, not adj_wp.~~ **CLOSED.** Line 2370 confirmed to pass adj_wp. See F-1. |
| M6 | F | run_picks.py | ~5285–5288 | Manual KILLSHOT override (--killshot) bypasses stat/tier checks entirely — only score ≥ 75 enforced. Any stat/tier can be manually promoted. |
| M7 | F | run_picks.py | ~3609, ~3823 | Daily_lay and longshot use naive independence for combined_prob; daily_lay feeds this directly into Kelly sizing (~8–12% overstatement). |
| M8 | F | sgp_builder.py | ~738 | SGP copula EV threshold uses vigged book-implied; ~3–8pp of the 10pp threshold is expected vig, not model alpha. Gate is more permissive than intended. |
| M9 | G | run_picks.py | ~6104 | Bonus pick size not reserved in same-session 12u cap — can overshoot by up to 1.25u within one session. |
| M-G7 | G | sgp_builder.py | ~66 | **NEW (this session)** sgp_builder SIGMA["PTS"] min=4.5 vs run_picks.py min=5.0. Not updated in sgp_builder when run_picks.py was raised 2026-05-25. Creates different win_prob for low-projection PTS in SGP vs single-stat contexts. |
| M10 | G | run_picks.py + sgp_builder.py | — | SGP win_prob blank in pick_log — copula probability not stored, blocking calibration analysis. Actual WR 27.8% vs model 30.9% (3.1pp over-prediction). |
| M11 | H | grade_picks.py | ~110 (analyze_picks) | analyze_picks.calc_metrics includes VOID picks in risked units — understates ROI vs production metrics. |
| M12 | H | grade_picks.py | ~1979–1981 | VOID picks excluded from daily Discord recap — transparency gap vs card posted. |
| M13 | H | grade_picks.py + weekly_recap.py | ~1575, ~492 | No Discord embed length guard — silent 400 error on heavy-pick days (embed > 4096 chars). |
| M14 | H | weekly_recap.py | ~606–612 | 429 retry handling doesn't use shared http_utils utility — non-standard body handling. |
| M15 | I | calibrate_platt.py | ~58–88 | Legacy win_prob fallback contaminates Platt fit — ~50% of current sample is double-calibration-biased. Make --native-only default at 100 rows. |
| M16 | I | run_picks.py | ~2261 | No MLB-specific Platt plan or go-live criteria documented. |
| M17 | I | run_picks.py | ~331–337 | COMBO_RHO_WNBA from n=9 players — all ρ values indistinguishable from zero (95% CI ±0.11). |
| M18 | J | clv_report.py + analyze_picks.py | headline stats | Parlay WR (23.1%) mixed into headline WR (45.9%), obscuring singles performance (53.3%). |
| M19 | J | engine/ | — | CLV uses vigged-implied; edge uses no-vig — not directly comparable in reports. |
| M20 | K | run_picks.py | ~1686, ~1695, ~1711 | Cache TTL 15min (CLAUDE.md says 11min); cache open() calls missing encoding="utf-8". |
| M21 | L | CLAUDE.md | Terms table | "Premium = Top 5 picks" — code is MAX_PREMIUM_PICKS = 3. |
| M22 | L | CLAUDE.md | SGP entry | SGP sizing gate description is stale (avg_wp≥0.70 replaced by copula EV ≥ 0.10 in L8). |
| M23 | L | filesystem | root + engine/ | post_nrfi_bonus.py source file missing — only .pyc bytecode remains. |

---

## 2. Provisional Rules (N < 30 — Monitor Only, Do Not Change)

| Rule | n | Evidence | Status |
|------|---|----------|--------|
| TEAM_TOTAL over block | 11 | 45.5% WR, −11.0pp gap | PROVISIONAL — block is already in place per May 25 audit. Monitor until n≥30 |
| G8B (AST over ≤4.5) | ~8 | 0-5 in blocked range | PROVISIONAL — directionally clear but statistically thin |
| G8D (3PM over ≤1.5) | 16 | 50.0% WR = losing at juice | PROVISIONAL — direction confirmed but n=16 borderline |
| ML_FAV win | 9 | 55.6% WR, −0.01u | PROVISIONAL — do not act |
| PTS under out-performance | 13 | +13.3pp above model | PROVISIONAL — could be variance |
| NHL over-prediction | 54 | −5.0pp gap, inside CI | PROVISIONAL — not statistically confirmed |
| MLB calibration | 11 | −13.8pp gap, CI ±29.4pp | COMPLETELY INCONCLUSIVE |
| KILLSHOT tier | 5 | 60.0% WR | PROVISIONAL — too small |
| +150+ odds bucket | 6 | 50.0% WR | PROVISIONAL |
| −109 to −101 bucket | 11 | 45.5% WR | PROVISIONAL |

---

## 3. Calibration Debt

Every constant below has no documented calibration script or requires independent validation:

| Constant | Issue | Action |
|----------|-------|--------|
| SIGMA["PTS"] mult=0.35 | No script, no n, no date | Create calibrate_sigma.py |
| SIGMA["REC"] mult=0.50 | No comment at all | Create calibrate_sigma.py |
| SIGMA["OUTS"] mult=0.30 | "2024 data" — no script, no n | Create calibrate_sigma.py |
| SIGMA["HA"] mult=0.50 | Distributional observation only, no sigma fit | Create calibrate_sigma.py |
| SIGMA_WNBA all values | Research §2 manual derivation, n=9 players | Expand to 50+ player-seasons |
| NB_R["K"] r=5.0 | Explicitly documented as estimate | Add K to nb_calibrate.py when MLB DB populated |
| NB_R["HRR"] r=1.5 | Single-point moment-matching — inferior methodology | Proper refit before re-enabling HRR |
| COMBO_RHO_WNBA all values | n=9 players — all within 1σ of zero | Expand to 2024+2025 data |
| PLATT_A/B | Legacy win_prob fallback contaminates current fit (50% contamination) | Make --native-only default at n=100 |
| No recalibration schedule | No trigger for annual NB_R/SIGMA refit | Document in runbook |

---

## 4. CLAUDE.md Corrections

| Priority | Section | Current Text | Correct Text |
|----------|---------|-------------|-------------|
| ~~CRITICAL~~ | Active Scalars — PLATT_A/B | ~~"Formula: logit-space"~~ | **CLOSED 2026-05-25** — CLAUDE.md now says raw-probability space, NOT logit-space |
| MEDIUM | Terms — Premium | "Top 5 picks from the model each day" | "Top 3 picks per sport each day" |
| MEDIUM | Terms — SGP | "copula EV margin ≥ 0.10 AND cohesion≥0.55 AND avg_edge≥0.035" | M8 two-gate: "Gate 1: copula_joint > parlay_implied (any positive EV); Gate 2: copula_joint − no_vig_independent ≥ 0.015; plus cohesion≥0.55 AND avg_edge≥0.035" |
| MEDIUM | Key Files — post_nrfi_bonus.py | Listed as existing file | Remove or restore from git history |
| LOW | Sizing Caps — G12 | "12u (G12 check)" | "12u (literal 12.0 in apply_caps — G12 is pitcher-prop gate, unrelated)" |
| LOW | Sizing Caps | "NBA=8.0u, NHL=5.0u" | Add "MLB=8.0u, WNBA=4.0u, NFL=5.0u" |
| LOW | Data-gated — gate counts | CLV=49, SGP=42, H3=50 | Update to CLV=63, SGP=43, H3=50 |
| LOW | CLV Daemon | "T-30 to T+3 capture window" | "T-45 to T+3 polling; writes within T-10 of tip" |
| LOW | Terms — CLV | implies vig-free | "raw vigged closing minus raw vigged open (not vig-free, consistent with industry standard)" |

---

## 5. Biggest Structural Gap vs Professional Sharp Quant Operation

**The engine has never had positive CLV at scale.** Mean CLV = −0.758% over 53 samples with a beat rate of 20.8% — the market moves against this system's picks in 4 out of 5 cases. A professional sharp quant operation would diagnose this as the primary issue before any model refinement.

The gap between what this engine does and what a professional operation does is concentrated in three areas:

**1. Market timing.** 47% of picks are placed within 30–60 minutes of tip-off. Professional operations bet at line open (noon ET for same-day NBA), when lines are softest. By tip-off, Pinnacle and other sharp books have already sharpened lines using information the model doesn't have. The CLV data (−1.52% at 19:xx vs +1.03% at 15:xx) is the clearest evidence that timing is causing more edge destruction than any model error. This is fixable operationally, not mathematically.

**2. No sharp reference line.** The engine uses DraftKings, ESPN Bet, and BetMGM as both the betting books and the CLV benchmark. These are soft books that limit winners and lag on sharp action. A professional operation uses Pinnacle or Circa as the reference close (neither is available in Colorado), and treats soft-book CLV as a lower bound on true CLV. This means current CLV of −0.758% vs soft books is probably −1.5 to −2.0% vs sharp close.

**3. The model's edge estimates are not independently validated.** Mean model edge = 12.5%. Mean CLV = −0.758%. This 13pp gap means the model's self-assessed edge is almost entirely not showing up in the market. In a professional operation, any constant with a 10pp+ gap between model and market is treated as miscalibrated and refitted — not gated around. The SIGMA values (no calibration scripts), the K distribution (r=5.0 estimate), and the combined Platt calibration (50% contaminated by double-calibrated legacy data) are the root causes. The correct fix is calibrate_sigma.py, a proper K calibration, and a clean Platt refit on 100 native rows — not more gates.

The engine has excellent operational infrastructure (filelock safety, process-level concurrency guard, atomic writes, proper VOID handling, CLV tracking) and reasonable mathematical foundations (correct PMF/CDF implementations, push handling, copula SGP). The gap is concentrated in calibration provenance, timing, and using market CLV as the diagnostic instead of model WR.
