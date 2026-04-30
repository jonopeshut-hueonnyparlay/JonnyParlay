# Custom Projection Engine — Phase 2: Root-Cause Investigation Plan

**Status:** Phase 1 slice diagnostic completed 2026-04-22. Gate FAILED, but root causes are isolated.
**Mission:** Drive PTS MAE ≤ 5.0 and ALL Phase 1 slice criteria to PASS **without band-aids**. Every adjustment must trace to a causal mechanism and be documented. No empirical constants without written justification.
**Scope boundary:** Stop at the CLV gate, not at theoretical MAE perfection. MAE is a proxy; live CLV vs SaberSim over 100+ picks is the real target.

---

## Philosophy — the rules this plan operates under

Jono's directive: **zero band-aids**. Every change must be:

1. A **bug fix** (the code did something demonstrably wrong), OR
2. A **model feature** that adds a causal mechanism (e.g., "close games extend starter minutes — incorporate projected spread into minutes projection"), OR
3. A **scope correction** (e.g., "this row type can't be modeled from pre-game historical data and won't become a prop pick anyway — exclude from the CSV output")

Every change gets a comment in code explaining WHY, traced to a hypothesis number from this document.

**Forbidden without written justification:**
- Empirical constant lifts (e.g., "add +0.8 min to starters")
- Hardcoded player overrides
- Multipliers tuned to make a backtest hit target
- Outcome-based filtering
- Floors/caps without modeled mechanism

If the only way to pass a gate is a band-aid, **the gate is the wrong criterion** — re-examine the target, don't hack the code.

---

## Current state (as of 2026-04-22 slice diagnostic)

### Full-season backtest (2025-10-22 → 2026-04-13, min_minutes=15, n=19,829 projected rows)

| Stat | MAE | Bias | Target | Status |
|------|-----|------|--------|--------|
| PTS | **5.036** | -0.619 | ≤5.0 | ❌ 0.036 over |
| REB | 2.046 | -0.166 | ≤2.5 | ✅ |
| AST | 1.509 | -0.107 | ≤2.0 | ✅ |
| 3PM | 1.008 | -0.076 | ≤1.5 | ✅ |
| MIN | 4.441 | **-0.877** | — | bias concern |

### Phase 1 Slice Gate — 7 Criteria

| # | Check | Target | Actual | Result |
|---|-------|--------|--------|--------|
| 1 | Overall MIN bias | ∈ [-0.25, +0.25] | -0.877 | ❌ FAIL |
| 2 | Overall PTS bias | ∈ [-0.35, +0.35] | -0.619 | ❌ FAIL |
| 3 | Bench MIN bias (was +5.340) | < +3.0 | +2.641 | ✅ PASS (51% reduction) |
| 4 | Starter MIN bias (was -2.087) | > -1.0 | -1.693 | ❌ FAIL |
| 5 | <15 and 15-20 MIN bucket magnitudes | ≥50% reduction | — | ⚠️ need old baseline to confirm |
| 6 | 30-35 and 35+ MIN bucket magnitudes | ≤ 2.0 | +0.842 / +1.759 | ✅ PASS |
| 7 | No PTS bucket bias crosses ±3.0 | — | <15 bucket: -4.325 | ❌ FAIL |

### Bucket breakdowns (from slice report)

**Starter vs Bench:**
| Bucket | n | PTS_MAE | PTS_bias | MIN_bias |
|--------|---|---------|----------|----------|
| starter (actual ≥20 min) | 16,096 | 5.267 | -1.046 | -1.693 |
| bench (actual <20 min) | 3,733 | 4.040 | +1.223 | +2.641 |

**Projected Minutes Bucket:**
| Bucket | n | PTS_MAE | PTS_bias | MIN_bias |
|--------|---|---------|----------|----------|
| <15 | 948 | 5.152 | **-4.325** | **-9.305** |
| 15-20 | 2,868 | 4.228 | -2.055 | -3.613 |
| 20-25 | 4,530 | 4.455 | -0.864 | -1.103 |
| 25-30 | 5,283 | 5.015 | -0.322 | +0.036 |
| 30-35 | 4,694 | 5.674 | +0.413 | +0.842 |
| 35+ | 1,506 | 6.335 | +0.926 | +1.759 |

**Usage Tier on Team:**
| Bucket | n | PTS_MAE | PTS_bias | MIN_bias |
|--------|---|---------|----------|----------|
| top3 | 7,971 | 5.667 | +0.044 | +0.427 |
| 4-6 | 7,254 | 4.816 | -0.774 | -1.007 |
| 7+ | 4,338 | 4.255 | -1.542 | -2.973 |
| no_team | 266 | 4.851 | -1.167 | -2.210 |

**Position bucket is UNK for all rows** — player_index.position not populated. Ignore this bucket for now; fixing it is unrelated to the minutes bias.

### Pattern observed

Projection is **mean-reverting too aggressively on both ends**:
- Low-projected-minutes players (<15) actually play ~24 min on average (under-projection -9.3)
- High-projected-minutes players (35+) actually play ~33 min on average (over-projection +1.8)
- Middle buckets (25-30) nearly unbiased

This is classic regression-to-mean — the projection is pulled toward the mean more than reality. The question is WHY, which is what the hypotheses below test.

---

## Hypothesis-driven root-cause investigation

Each hypothesis is a testable claim about why the model is biased. Test in order — highest-probability-impact first. Each test: audit the code, identify the issue (or kill the hypothesis), fix if valid, re-run the slice, update this document with the result.

### H1 — Healthy-mean filter is polluted with DNP-Rest / minutes-restriction / ejection games

**Claim:** The baseline minutes projection uses an EWMA or mean of recent games. If that input includes games where the player sat for non-performance reasons (rest, injury-restricted, ejection), the mean is artificially low. Fixing the filter would lift starter projections toward reality.

**Test:**
1. Open `engine/nba_projector.py`, find the minutes projection function
2. Identify the training baseline computation (EWMA or mean of recent minutes)
3. Check what rows are included. Specifically look for exclusions of:
   - `minutes == 0` (DNP) — rest games, injury scratches
   - Games with explicit `DNP-Rest` or `Inactive` markers if stored
   - Games where player played <10 min AND game was not a blowout (likely injury-in-game or foul-out)
   - Ejection games
4. If any of these are NOT excluded, that is a bug — they contaminate the baseline downward
5. Patch the filter. Re-run slice.

**Expected impact if valid:** Starter MIN bias should drop from -1.693 toward -0.5 or better. Overall MIN bias should halve.

**Kill criterion:** If the filter already excludes all these rows cleanly, H1 is dead. Move to H2.

---

### H1 RESULT (2026-04-22 backtest)

**Fix applied:** healthy-filter (minutes ≥ 15.0) applied to L5, L10, and season-mean components of `compute_minutes_baseline()` in `engine/nba_projector.py` for population-consistent baselines.

**Post-H1 full-season backtest (same window, min_minutes=15, n=19,829 rows):**

| Stat | MAE pre-H1 | MAE post-H1 | Δ | Gate | Status |
|------|-----------|-------------|---|------|--------|
| PTS | 5.036 | **4.995** | -0.041 | ≤5.0 | ✅ by 0.005 |
| REB | 2.046 | 2.047 | — | ≤2.5 | ✅ |
| AST | 1.509 | 1.509 | — | ≤2.0 | ✅ |
| 3PM | 1.008 | 1.009 | — | ≤1.5 | ✅ |
| MIN | 4.441 | 4.209 | -0.232 | — | improved |

**MIN bias collapse (overall):** -0.877 → **-0.069** (huge win).
**Starter MIN bias:** -1.693 → **-1.144** (improved 0.549, still missing \|<1\| gate by 0.144).
**Bench MIN bias:** +2.641 → +4.565 (overshoot got visibly worse — or the underlying starter/bench filter re-drew the buckets; sign unchanged, magnitude unfavorable either way).

**Post-H1 projected-minutes bucket (the smoking gun):**

| bucket | n | PTS_MAE | PTS_bias | MIN_bias |
|---|---|---|---|---|
| <15 | 115 | 5.655 | -5.041 | **-12.619** |
| 15-20 | 2,213 | 4.041 | -1.577 | -2.427 |
| 20-25 | 5,523 | 4.395 | -0.856 | -0.704 |
| 25-30 | 5,664 | 4.997 | -0.235 | +0.350 |
| 30-35 | 4,790 | 5.675 | +0.446 | +0.950 |
| 35+ | 1,524 | 6.360 | +0.939 | **+1.843** |

**Verdict:** H1 hit the PTS MAE gate by 0.005 (not safe margin). Starter MIN bias gate still fails. Residual pattern has sharpened into a specific fingerprint: starter undershoot + bench overshoot + <15 min catastrophe + 35+ min overshoot. This is consistent with a **population mismatch** — the single healthy-filter threshold (min ≥ 15) serves starters but breaks bench players because their few 15+ min games become the baseline.

**Decision point reached (2026-04-22):**

Rather than proceed to H2 (EWMA alpha), H3 (spread-aware minutes), etc. against the current architecture, **pause the hypothesis march and commission deep research** on whether Architecture A (per-minute-rate × minutes-baseline) is salvageable or whether the failure pattern indicates a shape mismatch requiring a different architectural decomposition (volume × efficiency, per-possession, hierarchical Bayesian with role priors, or ensemble).

Kickoff file: `memory/projects/custom-projection-engine-research-kickoff.md` — bundles the H1 bucket table + Part B architectural question + the canonical Part C research prompt.

Research output will resolve:
- **Stay** → extract the 3-5 top-ranked Architecture-A improvements, turn them into H2'-H8', continue the march with better-targeted work
- **Rebuild** → pivot memo, pause H2-H8, scope the rebuild
- **Hybrid** → identify the component to swap (most likely: role-stratified or hierarchical minutes model, keep per-minute rates), scope as focused sub-project

H2-H8 below stay on file as plausible patches but are NOT scheduled until the research resolves the architectural question.

### H2 — EWMA alpha is too conservative (not weighting recent games enough)

**Claim:** Late-season rotation compression is real — April starter minutes are higher than December starter minutes because coaches tighten rotations. If the EWMA alpha is low (e.g., 0.15), old games drag the projection down.

**Test:**
1. Find the EWMA alpha parameter in `nba_projector.py`
2. Check current value and whether it was set empirically or by justified reasoning
3. Sanity test: for a known tight-rotation team in April (e.g., Boston, Oklahoma City in a playoff push), plot projected vs actual minutes over the last 20 games
4. If projections lag actual by a persistent gap → alpha is too low
5. Do NOT just crank alpha up — that's a band-aid. Instead: determine if recency-weighting should be *date-weighted* (half-life in days) rather than *game-weighted* (half-life in games). Half-life in days automatically up-weights games in tight back-to-back stretches.

**Expected impact if valid:** Starter MIN bias further reduces. <15 bucket may also improve if recent expanded roles are up-weighted.

**Kill criterion:** If recency weighting is already date-based with a justified half-life (e.g., 30 days), H2 is dead.

### H3 — Game closeness (projected spread) is not in the minutes model

**Claim:** Starters play more minutes in close games, fewer in blowouts. Historical mean averages across all game types. If a starter is projected to play in a game with a 3-point spread, minutes should be higher than if the same starter is in a game with a 15-point spread.

**Test:**
1. Check `nba_projector.py` — does minutes projection consume opponent, total, spread, or implied team total at all?
2. If minutes projection is context-free (pure historical of the player), H3 is valid and represents a missing feature
3. Adding game-closeness to the minutes model is **not a band-aid** — it's a legitimate model feature with clear causal mechanism

**Expected impact if valid:** Reduces starter bias in close games, reduces over-projection in blowouts. Improves <15 bucket because replacement starters in blowouts play more than expected.

**Kill criterion:** If the model already incorporates projected spread or game-closeness, H3 is dead.

### H4 — Opponent-specific rotation shifts missing

**Claim:** Starter minutes distribution varies by opponent. Against elite teams in close games, starters go deeper. Against tanking teams, starters sit earlier. Historical mean across all opponents flattens this.

**Test:**
1. Pull the slice CSV. Compute starter MIN bias grouped by `opponent`.
2. If there's a clear pattern (e.g., -2.0 vs elite teams, +1.0 vs tanking teams), H4 is valid
3. Fix = opponent-adjusted starter minutes (not a per-opponent constant, but a function of opponent projected win rate or DRtg)

**Expected impact if valid:** Tightens starter bias across opponent classes.

**Kill criterion:** If opponent bias is flat (variance within ±0.5 across opponents), H4 is dead — the starter bias is not opponent-driven.

### H5, H6, H7 — The <15 projected-minutes bucket (948 rows)

These players are projected to play limited minutes. They actually play ~24 min on average. Why? Three possible causes:

**H5 — Injury absorption.** A starter was ruled out late; this player absorbed their minutes. Model didn't see the news.
- This is **unsolvable from pre-game historical data**
- The fix is a live injury-news feed, not modeling
- The existing `--context` flag is the hook for this

**H6 — Rookies/call-ups with thin history.** Expanded role mid-season. EWMA with long half-life under-weights recent expansion.
- If H2 fix (date-weighted half-life) is applied, this partially resolves
- True fix = cold-start logic: if player has <10 games in DB or recent ≠ historical by >50%, up-weight last 5 games

**H7 — Foul trouble / ejection / starter injury upstream.** Player above them fouled out → expanded role. Not knowable pre-game.
- Genuinely unmodelable from pre-game data

**Conclusion for <15 bucket:** After H2 and H6 fixes, residual <15 bucket bias represents the unmodelable tail (H5 + H7). **Do NOT compensate for it with a constant.** Instead, exclude <15 projected-minutes players from the CSV output — not because it's convenient, but because:
1. They are not prop candidates (T1/T2/T3 thresholds in `run_picks.py` won't fire on a <15-min player)
2. The information required to project them accurately (live news, in-game events) doesn't exist at projection time
3. This is a correct scope boundary — the projection engine models expected historical patterns, not late-breaking news

**Implementation:** In `csv_writer.py`, filter `min_proj < 15` rows before writing the CSV.

### H8 — Bench mean contaminated by starter-out absorption games

**Claim:** Bench player historical minutes include games where they got expanded role due to a starter being out. When starters are healthy, they play less. Model averages across both → over-projects bench when starters are healthy.

**Test:**
1. Same filter audit as H1 — but reverse direction
2. Identify games where this bench player played >30 min (abnormal for a bench player). Check if the starter ahead of them was `DNP-Injury` in the same game
3. If yes, those bench games should be **context-flagged** — they're not the player's baseline; they're absorption events
4. Fix = exclude absorption events from bench baseline, OR weight them differently

**Expected impact if valid:** Bench MIN bias drops from +2.641 toward 0.

**Kill criterion:** If absorption events are not contaminating the baseline, H8 is dead.

---

## Execution plan

### Phase 2A — Audit and fix (ordered)

For each hypothesis H1–H8 in order:

1. **Audit the relevant code.** Read the function, understand what it does. Document what was found.
2. **Determine if the hypothesis is valid.** Either confirm the bug/missing feature exists, or kill the hypothesis with evidence.
3. **If valid: design the root-cause fix.** Write a short justification paragraph explaining the causal mechanism and why this fix addresses it.
4. **Implement the fix.** Add a code comment referencing the hypothesis number (e.g., `# [H1] exclude DNP-Rest games from minutes baseline — they contaminate the healthy mean`).
5. **Re-run the slice** with the same command:
   ```
   python engine\backtest_slice.py --start 2025-10-22 --end 2026-04-13 --min-minutes 15 --out slice_results_[YYYY-MM-DD]_[hypothesis] -v
   ```
6. **Update this document** with the result under the hypothesis heading: bias deltas, new gate status, next step.
7. **Move to next hypothesis** only if gate criteria still not all PASS.

**Stop conditions:**
- All 7 Phase 1 criteria PASS → Phase 2A done, move to Phase 2B
- All hypotheses tested, residual bias remains → re-examine whether the gate criteria themselves are achievable without band-aids. Write a memo arguing for relaxed criteria OR new model features, not hacks.

### Phase 2B — Full backtest validation

After Phase 2A passes the slice gate, run the full backtest:
```
python engine\backtest_projections.py --start 2025-10-22 --end 2026-04-13 --min-minutes 15
```

Confirm PTS MAE ≤ 5.0 AND all other stats still pass. If PTS MAE still > 5.0 despite slice gate passing, investigate the delta (the slice excludes non-projected rows; full backtest may have different row count).

### Phase 2C — Shadow mode live validation (the real gate)

Once MAE is cleared:

1. Modify `run_picks.py` / CSV pipeline to generate BOTH SaberSim CSV and custom-engine CSV each day
2. Run picks through both in parallel. Log both to separate pick_log files (`pick_log.csv` for SaberSim, `pick_log_custom.csv` for custom engine) — do NOT mix
3. Track custom-engine CLV via the same `capture_clv.py` daemon
4. Accumulate 100+ graded picks
5. Compare rolling CLV: custom vs SaberSim
6. If custom CLV ≥ SaberSim CLV over 100+ picks → cancel SaberSim ($197/mo saved)
7. If custom CLV < SaberSim CLV → do NOT force the switch. Investigate the delta (possibly H3/H4 features missing, or different signal the custom engine doesn't capture). Continue shadow mode until edge is clear.

---

## Files involved

| File | Role in this plan |
|------|-------------------|
| `engine/nba_projector.py` | Minutes model, EWMA, projection logic — primary edit target |
| `engine/projections_db.py` | DB schema, historical pull — check filters for DNP detection |
| `engine/csv_writer.py` | Outputs SaberSim-schema CSV — Phase 2A final step: exclude <15 min_proj rows |
| `engine/backtest_projections.py` | Full backtest harness — Phase 2B runs this |
| `engine/backtest_slice.py` | Diagnostic slice — re-run after each hypothesis |
| `data/projections.db` | 79,358 rows `player_game_logs`, 2023-10-24 → 2026-04-12 |
| `memory/projects/custom-projection-engine-phase2-root-cause.md` | This plan — update with results after each hypothesis |

---

## RESEARCH RETURNED (2026-04-23) — verdict: HYBRID (Architecture A+)

Deep research deliverable: `uploads/custom-projection-engine-research-report.md` (~1,300 lines, 17 sections).

**Verdict from §1.1 and §3.2:** keep per-minute-rate × minutes as the outer backbone; the diagnosed failure pattern is *not* a refutation of the outer decomposition — it's the architectural fingerprint of *inner* conflation. A single rate term cannot absorb role variance + teammate variance + opponent variance + pace variance + game-script variance simultaneously. The smallest mechanistic resolution is role-conditional rates + feature-rich minutes regression + cold-start prior pipeline.

The report explicitly evaluates H2-H8 (original) against the failure pattern and concludes: filter-tuning and weight-tuning against Architecture A-as-configured are dead-ends. None of the remaining filter/weight changes resolve the starter undershoot + bench overshoot + <15 catastrophe + 35+ overshoot fingerprint. The fingerprint is the architecture.

### Mechanistic mapping (from §3.2)

| Post-H1 anomaly | A+ mechanism that resolves it |
|---|---|
| Starter MIN -1.144 | Rates from role-tier-matched subsample, not universal healthy-filter |
| Bench MIN +4.565 | Bench rates from bench-game subset (not injury-vacancy/blowout-inflated absorption events) |
| <15 MIN -12.619 | Cold-start prior pipeline (depth × archetype × prior-team), not league-mean rate × role-mean minutes |
| 35+ MIN +1.843 | Minutes regression conditioned on coach rest index + B2B + spread + injury_status_team_starters |

### Revised hypothesis sequence (H2'-H8') — replaces original H2-H8

Prerequisites first — without these, role-aware work is blocked or corrupt:

| # | Hypothesis | What it attacks | Source |
|---|---|---|---|
| **H2'-PREREQ1** | Fix position=UNK extraction in player_index | Blocks any role-tier classifier (5-tier gate needs valid position) | Existing known bug |
| **H2'-PREREQ2** | Garbage-time filter on rate inputs (CtG 95%-WP standard) | Inflated bench rates + depressed starter late-game rates | §2.9.1, §6.1 |
| **H2'** | Role-conditional per-minute rates (5 tiers × within-tier usage buckets) | Starter undershoot + bench overshoot — architectural backbone | §2.3, §3.2, Lever #1 |
| **H3'** | Feature-rich minutes regression replaces role-mean baseline | 35+ overshoot + full minutes-baseline refactor | §4, Lever #2 |
| **H4'** | Cold-start prior pipeline (returning vet × age / G-League × 0.65 / international × league factor / rookie archetype) | <15 catastrophe (n=115 bucket, -12.619 MIN bias) | §2.5, §4.4, Lever #3 |
| **H5'** | Availability-weighted rolling rates (down-weight games where teammates differed) | Teammate-vacancy contamination on both rates and minutes | §2.5, Lever #4 |
| **H6'** | Per-stat EPM-style sample-size weighting (k=8 for PTS/MIN, k=15 for 3PM/STL/BLK) | 3PM/STL/BLK noise, over-shrinkage of stable players | §5.4-§5.6, Lever #7 |
| **H7'** | Bayesian shrinkage for post-trade efficiency (decay schedule: <5→0.7, <15→0.5, <30→0.3, else 0.1) | Trade-deadline residuals, not a current priority but on the bench | §2.5.2, Lever #5 |
| **H8'** | Distributional output (5/25/50/75/95 percentiles + MVN joint samples) | Kelly sizing + SGP/DD2/TD3 pricing | §5.9, §6.5, Lever #8 |

**Absorbed into H3' (not separate hypotheses):**
- Old H2 (EWMA alpha) → half-life parameter inside feature-rich minutes regression
- Old H3 (spread in minutes model) → `vegas_spread` is a regressor in H3'
- Old H4 (opponent-specific rotation) → `injury_status_team_starters` + opponent effect in H3'
- Old H6 (date-weighted vs game-weighted) → era weighting table (§6.6) applied in H3' training
- Old H8 (bench absorption contamination) → resolved by role-tier-matched subsample in H2'

**Absorbed into H2'-PREREQ2 (not separate):**
- Old H5/H7 (unmodelable tail) — stays as-is; CtG filter on training data; live-news dependency is an accepted limitation of Architecture A+ per §9.2

**Deferred to v1.5/v2 (after A+ ships and CLV validates):**
- Architecture B (volume × efficiency) for PTS specifically — §3.3
- Pace projection sub-component (Architecture C pace only, not full per-possession rebuild) — §3.4
- Per-coach feature dictionary (~30 coaches × 6 features) — §4.3

**Deferred to v3 (only if A+ fails CLV gate):**
- Architecture D (full play-by-play Monte Carlo sim) — §3.5, §7.3
- Shot-level / Synergy tracking purchase — §3.6
- Stacked ensemble — §3.8

### Gate shift — per-tier bias targets (from §7.1)

The original Phase 1 gate used overall starter MIN bias `|<1|`. Report §7.1 recommends a tighter, *per-tier* gate:

| Tier | MIN bias target | PTS bias target |
|---|---|---|
| Starter | ≤ 0.3 | ≤ 0.5 |
| 6th-man | ≤ 0.3 | ≤ 0.5 |
| Rotation | ≤ 0.3 | ≤ 0.5 |
| Spot | ≤ 0.3 | ≤ 0.5 |
| Cold-start | ≤ 0.5 | ≤ 0.8 |

Each post-H2' backtest should report per-tier bias, not just overall. This is a sharper diagnostic for diagnosing A+ residuals.

### Red-team takeaways (to respect in builder prompts, from §9)

- **Role tier must use lagged assignment** (rolling MIN last-5). Current-game projected role = circular. Non-negotiable.
- **Tier count is a hyperparameter.** Default 5, but 4 (collapse 6th-man) and 7 (split starter by position) are live alternatives. Validate with held-out per-tier MAE after H2' lands.
- **Minutes regression should be gradient-boosted**, not linear, to handle post-CBA rest-pattern drift. Annual retrain.
- **Cold-start priors (24/16/8/3 MIN)** are rough. Track residuals separately; quarterly re-calibration.

### Known-unknowns now formally tracked

Report §12 lists 20 known-unknowns with defaults and resolution experiments. The engine should maintain a per-hypothesis residual dashboard so each resolution experiment can fire opportunistically.

### Execution sequencing (immediate)

Phase 2A-revised begins now:

1. **Builder prompt #1:** H2'-PREREQ1 — diagnose + fix position=UNK data extraction in `player_index`. Surgical bug fix; blocking H2'.
2. **Builder prompt #2:** H2'-PREREQ2 — garbage-time filter on rate inputs in `engine/nba_projector.py`. Data cleanup.
3. **Builder prompt #3:** H2' — role-tier classifier (5-tier) + role-matched rate subsampling. Backbone change.
4. Re-run slice + full backtest after each. Update this document with tier-stratified bias.
5. Continue sequentially through H3'-H8'.

Phase 2B (full backtest validation) and Phase 2C (shadow-mode CLV) unchanged.

## What success looks like

- All 7 Phase 1 slice criteria PASS
- PTS MAE ≤ 5.0, REB/AST/3PM still PASS
- Each code change traceable to a hypothesis with a causal justification
- Zero empirical constants without comments explaining mechanism
- Shadow mode running: custom CSV generated daily alongside SaberSim CSV
- 100 graded picks accumulated with CLV tracked for both sources
- Decision made on SaberSim cancellation based on empirical CLV comparison

---

## What failure looks like (and what to do about it)

If after all 8 hypotheses tested, residual bias cannot be eliminated without band-aids:

1. **Do not apply band-aids.** The gate is a proxy; failing the proxy doesn't mean failing the mission.
2. **Run shadow mode anyway** with current MAE. If live CLV beats SaberSim despite MAE being 5.05 instead of 5.00, **MAE was lying** — live markets are the truth.
3. **If live CLV also lags** → the bottleneck is not projection accuracy; it's line shopping, news latency, or prop selection logic in `run_picks.py`. Re-scope accordingly.

---

## Cowork infrastructure notes (for builder session)

- **Bash cap:** 45s per command. Can't run full backtests from Cowork. Builder writes code + instructs Jono to run on Windows. Paste output back.
- **Mount staleness:** Always verify line counts after edits (`Get-Content file.py | Measure-Object -Line`).
- **SQLite WAL:** DB writes from Cowork land in `/tmp`, then `cp -f` to Windows mount. Do not write directly to `data/projections.db` from Cowork.
- **Source of truth:** `engine/` folder. Always sync to root after edits.

---

## Kickoff command for new session

Read in order:
1. `CLAUDE.md` — full engine context
2. This file — Phase 2 plan
3. `engine/nba_projector.py` — start with H1 audit

Then begin Phase 2A with H1. Report findings, propose fix, wait for Jono to run on Windows, update this document with result, move to next hypothesis.
