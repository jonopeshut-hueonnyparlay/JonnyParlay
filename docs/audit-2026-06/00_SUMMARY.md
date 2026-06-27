# FULL-SYSTEM AUDIT — EdgeModel + JonnyParlay — Executive Summary
**Date:** 2026-06-26 · **Method:** multi-agent (one finder per module reading every line →
adversarial verification of every C/H/M finding → per-file frozen-constant validation →
per-repo completeness critic + targeted re-find). Findings grounded only in code at `git HEAD`,
not memory.

## Scope & coverage
- **Every non-test `.py` in both repos** audited: 24 modules, ~144 source files, ~144k LOC.
  Coverage assertion confirmed **0 unmapped files** (EM + JP).
- Tests scanned (X-2), constants registry built (X-4), incomplete-work ledger built (X-3),
  cross-repo interface traced (X-1).
- Run cost: ~703 agents, ~16M subagent tokens across 4 resumes (session-limit interrupted; the
  per-constant validator was re-architected into file-batched validators to finish).

## VERDICT — is it safe to run?
**Yes — safe to run. No critical, run-blocking, or money-losing defect survived verification.**
- **0 Criticals.** Every C-level candidate was refuted or downgraded under adversarial review.
- The single dominant live issue is the **already-known σ-overconfidence gate** (dk_std too
  tight, +8.8pp / WNBA +14.9pp). It is documented, gated, and pending the sign-off-gated σ refit.
- 3 *new* genuine code bugs and a handful of stale/drifted constants warrant fixes, but **none
  crash the daily run and none mis-price the broad book** — they bias specific sports/markets.

"Perfect" it is not yet; this is the punch-list to get there. Nothing below is auto-fixed —
per protocol, every fix is a separate, sign-off-gated change (no edits to FROZEN constants
without your go-ahead).

## Findings tally (after adversarial verification)
| | C | H | M | I (confirmed) | refuted/downgraded |
|---|---|---|---|---|---|
| Both repos | **0** | **5** | **30** | 30 | 100 |
- 251 findings + 20 from the completeness re-find round = 271. 106 further low-risk items logged
  as unverified-Info (coverage evidence).
- Constants: **524 validated** across 86 files → **27 flagged** (6 wrong · 16 stale · 5
  lockstep-drift) + 6 unverifiable. **491 validated clean.**
- Not-done ledger: **132 items** (37 partial-feature · 37 deferred · 32 dead-code · 17
  flag-gated · 7 stub · 2 TODO).

## PRIORITIZED FIX BACKLOG

### High (5) — fix before "perfect", none run-blocking
1. **[NEW · code] `EdgeModel/engine/injury_parser.py:425`** — when an OUT player's position group
   has a single eligible backup, `if secondary.empty: continue` silently **discards the entire
   secondary minutes pool** (`(1−REDISTRIB_PRIMARY_SHARE)` of the redistributed minutes). Minutes
   leak in thin-depth situations. Fix: route the secondary remainder to the primary when no
   secondary exists.
2. **[NEW · code] `EdgeModel/engine/mlb_advanced_fetcher.py:442`** (`_finalize_park_factors`) —
   the `reg(idx)=(4·idx+1)/5` fixed 80/20 shrink is calibrated for a multi-season pool, but
   `_park_accum` is populated per-season (docstring says cross-season). Single-season noisy park
   indices are under-shrunk → park factors too extreme. Also flagged as a **wrong constant**.
3. **[NEW · code] `EdgeModel/engine/nhl_advanced_fetcher.py:198`** — per-team xG is keyed on
   **MoneyPuck** team codes, but the projector/game-lines join on the **api-web** abbreviation →
   silent league-wide team-xG mismatch on the abbreviations that differ. Fix: normalize team
   codes before the join.
4. **[KNOWN · stat] `EdgeModel/engine/nba_projector.py:1646` + `wnba_projector.py:308`** —
   `dk_std = 0.35·proj_pts` understates variance (the live σ gate; WNBA worse — no observed-std
   floor). Pending σ/temperature refit on `pick_log` (n=2180). **No change without sign-off.**
5. **[KNOWN · stat] `JonnyParlay/engine/sgp_builder.py:219`** — SGP/MLB-SGP leg win-probs bypass
   the Platt/temperature calibration that straight props receive → SGP legs priced on raw model
   probs. Decide intended behavior; if unintended, route legs through the same calibration.

### Constant fixes (the X-4 cornerstone — your top worry)
**Validated:** 491/524 clean. **Flagged 27.** Most material:
- **wrong/H** — MLB park-factor regression (=#2 above); **RBI/PA `=0.135`** in
  `mlb_batter_projector.py:161` vs league ~0.11 (over-projects RBI ~15-30%).
- **stale/H** — `DK_STD_COEFF=0.35` (=#4).
- **stale/M cluster** — `calibrated.py GAME_SIGMA['MLB']` interim, never DB-fit;
  `MLB_PARK_FACTORS` (2022-25) stale; `nb_calibrate` NBA REB r `10.18` vs live `13.16`;
  `thresholds.py WNBA_SEASON_START = 2026-05-13` (should be 05-08); WNBA early-season edge mult
  still a data-gated placeholder.
- **lockstep-drift/M** — `calibrate_sigma.py` AST σ fallback `0.40` vs live `0.53` in
  `calibrated.py`; `evaluate_projector.py` opp_tov clip `1.30` vs production `1.20`;
  `context_research_v2.py` line-move threshold `1.0` vs v1 `1.5`.
- **security/M** — **hardcoded Odds API key** literal in `JonnyParlay/analyze_game_lines.py:32`
  (should source `secrets_config.ODDS_API_KEY`). Rotate the key and remove the literal.
- Several **stale display-only** constants in diag tools print pre-refit blowout/σ values
  (cosmetic, no live effect).

### Notable incomplete work (full list in NOT_DONE_LEDGER_*)
- **NFL** half-built: pricing present, data half (CSV export + parse) deferred across
  `nfl_*`, `market_config.py`, `calibrated.py` — matches the `feat/nfl` status. Live NFL slate is
  empty until weekly rows exist (`nfl_player_projector.py:155`).
- **WNBA P(active)** is a V1 binary in/out stub (spec wants a classifier); position is heuristic-
  inferred. `wnba_projector.py`.
- **Dead/non-functional in JonnyParlay**: `gates.py` G1 unreachable (pre-empted by G9);
  `engine/tools/diag_*` import EdgeModel-only modules (ImportError if run from JP);
  `pick_log_schema._MIGRATIONS` framework has zero registered migrations.
- **One-shot placeholder posters**: `post_nrfi_bonus.py`, `analyze_game_lines.py` MLB_PROJS/
  NBA_PROJS hardcoded stale slate fallback.

## Memory / doc reconcile (memory was treated as stale; here's what to correct)
- CLAUDE.md "JonnyParlay reads projections.db" — **NBA reads the CSV**, only WNBA + calibration
  read the DB. Tighten the wording (see CROSS_REPO_INTERFACE.md).
- WNBA game-sigmas were recalibrated 2026-06-09 to total=17.424 / team=11.253; the *advisory*
  `calibrate_distributions.py` still prints the old 10.0/7.5 — display is stale, deployed value
  is current. Worth a note in the calibration memory.
- σ-overconfidence gate, Platt distinct-days block, WNBA combo-ρ done, NFL deferred — all
  **confirmed still accurate** vs CLAUDE.md "Open gates".

## Trust / completeness of the audit itself
- Coverage ledger: every `git ls-files '*.py'` file mapped to exactly one module; 0 unmapped.
- Every C/H/M finding ran the adversarial refuter; 100 were refuted/downgraded and are kept in
  the MASTER_TABLE appendices (nothing silently dropped).
- Completeness critic flagged 9 high-risk/large files as possibly under-audited (e.g.
  `grade_picks.py`, `capture_clv.py`, `backtest_calibration.py`, `evaluators.py`); the re-find
  round re-read them — results in `RE-FIND.md` (no new C/H beyond the 5 above).
- The 3 new High code bugs were hand-spot-checked against the real source (line-accurate).

## File index
- `MASTER_TABLE_EDGEMODEL.md`, `MASTER_TABLE_JONNYPARLAY.md` — all findings + refuted appendix.
- `FROZEN_CONSTANT_REGISTRY.md` — X-4, all 27 flagged + unverifiable.
- `NOT_DONE_LEDGER_EDGEMODEL.md`, `NOT_DONE_LEDGER_JONNYPARLAY.md` — X-3.
- `CROSS_REPO_INTERFACE.md` — X-1.
- `EM-*.md` / `JP-*.md` / `RE-FIND.md` — per-module detail.
- Raw machine-readable result: workflow `audit_result.json` (scratchpad).
