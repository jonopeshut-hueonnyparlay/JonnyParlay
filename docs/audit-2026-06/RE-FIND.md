# AUDIT 2026-06 — RE-FIND (completeness round) (JonnyParlay)

Files audited (9 read): capture_clv.py, capture_clv.py, evaluators.py, evaluators.py, grade_picks.py, grade_picks.py, evaluate_projector.py, calibrate_winprob.py, calibrate_platt.py

**Findings (final, excl. refuted): C=0 H=0 M=3 I=4** | constants extracted: 21 | not-done: 6

## Findings

| ID | File:line | Sev | Status | Cat | Known | Title |
|----|-----------|-----|--------|-----|-------|-------|
| JP-RF-1 | capture_clv.py:1882 | M | confirmed | code |  | Partial-capture games are never STALE-marked or retired — give-up condition is unreachable |
| JP-RF-4 | evaluators.py:111 | M | confirmed | statistical |  | Early-season confidence penalty applied twice — once to prob, again to edge |
| JP-RF-6 | grade_picks.py:1360 | M | confirmed | code |  | Last-name-only fuzzy player match can settle the wrong player's stat |
| JP-RF-9 | calibrate_platt.py:38 | I | unverified | statistical | Y | calibrate_platt fits in logit-space but the live run_picks formula is raw-probability space (KNOWN/superseded) |
| JP-RF-8 | calibrate_winprob.py:176 | I | unverified | statistical |  | 5-fold CV leaves the remainder rows out of all validation folds |
| JP-RF-2 | capture_clv.py:1075 | I | refuted | statistical |  | Cross-book de-vig inflates no-vig closing prob → optimistic CLV |
| JP-RF-7 | evaluate_projector.py:218 | I | unverified | completeness |  | project_3pm alpha=0.65 hardcoded as a default rather than imported from EdgeModel |
| JP-RF-3 | evaluators.py:860 | I | refuted | statistical |  | NRFI offense normalizer _LEAGUE_AVG_RUNS=4.45 looks stale vs 2025 (~4.26 R/G/team) |
| JP-RF-5 | grade_picks.py:876 | I | confirmed | code |  | Voided/pushed parlay legs drop but P&L is still computed at the original full-parlay odds |

## C/H/M detail

### [M] JP-RF-1 — Partial-capture games are never STALE-marked or retired — give-up condition is unreachable
`C:/Dev/JonnyParlay/engine/capture_clv.py:1882-1902` · code · status=confirmed

**Evidence:** The capture block at L1762+ is only reached when `-CAPTURE_AFTER_SECS <= secs_to_start <= CAPTURE_BEFORE_SECS` (window gate L1752, CAPTURE_AFTER_SECS=180). Inside, the partial-capture give-up path (L1889 `secs_to_start < -STALE_AFTER_SECS` =-1800; L1895 `secs_to_start < -CAPTURE_AFTER_SECS` =-180) can NEVER be true, since secs_to_start is guaranteed >= -180 here. So when a game captures only some of its picks (e.g. one prop market is missing), it is never retired and the missing picks never get closing_odds='STALE'. They stay blank forever for the day, `remaining` never reaches 0, and the daemon cannot take its clean 'all picks captured' early-exit (L1916/L1666) — it runs to MAX_DAEMON_UPTIME (18h). Only fully-captured games (captured>=total) are retired.

**Recommendation:** Gate the partial-capture STALE/retire on wall-clock past the window cutoff using the actual cutoff (e.g. secs_to_start <= -CAPTURE_AFTER_SECS handled BEFORE the window `continue`, or compare against CAPTURE_AFTER_SECS not STALE_AFTER_SECS). STALE_AFTER_SECS (1800) is dead drift from when the post-tip window was wider.

**Verifier (confirmed):** Verified in C:/Dev/JonnyParlay/engine/capture_clv.py. The capture block is only entered after the window gate at L1752 (`-CAPTURE_AFTER_SECS <= secs_to_start <= CAPTURE_BEFORE_SECS`), which guarantees secs_to_start >= -180 (CAPTURE_AFTER_SECS=180, L275). The partial-capture give-up conditions are therefore unreachable: L1889 `secs_to_start < -STALE_AFTER_SECS` (< -1800) is impossible, and L1895 `secs_to_start < -CAPTURE_AFTER_SECS` (< -180) is impossible even at the boundary (strict <). The part

### [M] JP-RF-4 — Early-season confidence penalty applied twice — once to prob, again to edge
`C:/Dev/JonnyParlay/engine/evaluators.py:111-164` · statistical · status=confirmed

**Evidence:** conf (0.70/0.85/1.0 by GP) shrinks over_p/under_p toward 0.50 at L112-113 (before Platt). The resulting win_prob already carries that shrinkage, and the comment at L163 confirms `adj_wp == win_prob`. But L162 then sets `adj_edge = raw_edge * conf`, multiplying the edge (already reduced because win_prob was shrunk) by conf a SECOND time. adj_edge is what gates tier-min-edge (L208) and feeds pick_score. Net: low-GP picks are penalized ~conf^2 on edge. Direction is conservative (under-selects), so not C/H, but it likely suppresses some +EV low-GP picks beyond what calibration intends. The team elsewhere is explicit about avoiding double-counting (L214-217 WNBA edge-mult removal).

**Recommendation:** Decide whether conf belongs on the probability OR the edge, not both; if intentional, document it as a deliberate extra selection-conservatism rather than calibration.

**Verifier (confirmed):** Code confirms the claim. In engine/evaluators.py, conf (0.70/0.85/1.0 by GP<10/<20/else) shrinks over_p toward 0.50 at L111-113 BEFORE Platt, so win_prob carries the shrink. L160 then computes raw_edge = win_prob - nv_prob (from the already-shrunk win_prob), and L162 multiplies that edge by conf a SECOND time: adj_edge = raw_edge * conf. adj_edge gates tier_min_edge (L208) and feeds pick_score (L218), so the duplicate factor materially affects live selection. The comment at L163 ('Confidence alr

### [M] JP-RF-6 — Last-name-only fuzzy player match can settle the wrong player's stat
`C:/Dev/JonnyParlay/engine/grade_picks.py:1360-1389` · code · status=confirmed

**Evidence:** grade_prop falls back to a last-name-only match (L1377-1381) taking the FIRST weak candidate when first+last doesn't match. If two players in the same boxscore share a last name (common: Williams, Jones, Brown, Johnson), the grader can read the wrong player's stat and assign a wrong W/L on real money. The strong first+last branch mitigates most cases, but the weak fallback has no tie-break/abort on ambiguity.

**Recommendation:** When more than one boxscore entry matches last-name-only, abort to None (leave ungraded) rather than grading against an arbitrary first match — mirror the H-4 'refuse to best-guess' policy used for ambiguous team codes.

**Verifier (confirmed):** Code at grade_picks.py:1360-1381 matches the finding. After exact normalized-name match fails, the fuzzy branch does last-name matching: the strong branch requires first+last both present and breaks; the weak fallback (elif best_candidate is None) takes stats.get(stat) for the FIRST last-name-only entry with no tie-break or ambiguity abort. Critically, the dict passed in (all_player_stats[(date,sport)] built at L2330-2360 via fetch_nba_boxscore/fetch_wnba_boxscore/etc. and consumed at L2397) is 


## Confirmed-correct / coverage notes

- **compute_pl payout math (grade_picks L1476-1497)** is correct American-odds settlement: win pays size*(100/abs(odds)) for negative odds and size*(odds/100) for positive; loss returns -size; push/VOID return 0.0. Rounded to 4 dp.
- **Push/void leg removal** in grade_parlay_legs (L876-888) and grade_daily_lay (L760-815) is logically sound for W/L/P resolution: any L short-circuits to L; remaining = legs minus P and VOID; empty remainder → P; else W. The fall-through 'W'/'P' defaults are reachable only in the intended states (the all-loss case returns L inside the loop).
- **Terminal-result idempotency** (TERMINAL_RESULTS frozenset + _is_terminal_result, L158-170) plus the defensive M-23 overwrite guard (L2405-2414, L2565-2567) correctly prevent re-grading W/L/P/VOID rows.
- **ROI denominator** correctly excludes P and VOID from risked (daily_stats L1516), matching the refunded-outcome contract.
- **Game-line grading thresholds** (TOTAL/SPREAD/ML/TEAM_TOTAL/F5/NRFI, L1125-1262) use correct over/under/cover comparisons; spread result_val = margin + signed line; integer-line pushes handled; MLB TEAM_TOTAL integer-line push normalization (evaluators L558-562) yields over_p+under_p=1.
- **Ambiguous 2-letter team codes** (LA/NY/SF/SD) are refused rather than best-guessed in both grade_daily_lay and _resolve_pick_is_home (H-4), preventing wrong-side settlement.
- **Atomic writes + filelock** are consistently applied across grade_picks (_atomic_write_rows) and capture_clv (_do_write_closing_odds tmp+fsync+os.replace under FileLock); guard writes refuse a non-atomic fallback (C7).
- **calc_clv de-vig + clv_corrected** are mathematically consistent for the symmetric -110/-110 hold: the correction p*(_CLV_HOLD/(1+_CLV_HOLD)) recovers the entry-side vig (0.5238*0.0476/1.0476 ≈ 0.0238); clv_corrected is additive/diagnostic and never replaces clv.
- **best_price** correctly selects best-for-bettor by max American odds (valid across the +/- boundary).
- **Odds API quota handling** (capture_clv L468-605): 429/5xx/timeout backoff, 401 OUT_OF_USAGE_CREDITS parking until UTC reset, x-requests-remaining=0 short-circuit — robust, no blanket silent except in the hot path.
- **NRFI Poisson core**: BASE_LAMBDA_1ST=0.32 reproduces the ~70-72% per-team and ~52% game NRFI rates (verified against public figures); negative-multiplier guard before NRFI_GAMMA exponentiation (L983-986) prevents complex-number TypeError; no-vig from both sides (M2 fix).
- **evaluate_game_lines** uses ml-sigma (not spread-sigma) for moneylines (L435), NB direct-sum for MLB ML (mlb_ml_from_nb), and BLEND_ALPHA market anchoring throughout — internally consistent; is_home is propagated to picks for correct grading.
- **calibrate_platt / calibrate_winprob** both gate on sample size, run time-ordered (no-leakage) CV, and hard-exit on negative OOS Brier before printing constants — they cannot silently emit a worse calibration.

## Not-Done / incomplete (this module)

| Kind | File | Detail |
|------|------|--------|
| dead-code | capture_clv.py | L1889/L1895 partial-capture give-up uses secs_to_start < -STALE_AFTER_SECS (-1800) and < -CAPTURE_AFTER_SECS (-180) inside a block already guaranteeing secs_to_ |
| flag-gated | capture_clv.py | ENABLE_SHADOW_CLV=False (L320) — MLB shadow-log CLV capture intentionally off until MLB go-live; GAME_LINE_CLV_MARKET TEAM_TOTAL deferred (L218, 'needs team-fil |
| todo | evaluators.py | L123: 'TODO: refit at SGP Platt gate (100 scored slips)' — combo stats (PRA/PR/PA/RA) skip Platt and remain ~5pp inflated; L860-867 NRFI park-factor + first-inn |
| deferred | calibrate_platt.py | Logit-space fit vs raw-space live formula — H3 migration is a manual two-step paste, not yet applied (KNOWN/superseded by JonnyParlay Calibration Platt). |
| deferred | calibrate_winprob.py | Phase 2/3 (isotonic at n>=300, per-sport/tier stratified at n>=500) not implemented; explicitly advisory-only ('DO NOT PASTE OUTPUT INTO run_picks.py'). |
| partial-feature | grade_picks.py | GOLF_WIN game-line grading returns None (L1264-1267) — outrights graded manually; SHADOW_SPORTS=set() empty (L87) so no sports currently shadow-graded. |
