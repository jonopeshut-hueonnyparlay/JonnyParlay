# AUDIT 2026-06 — JP-10 Calibration/eval/backtest (JonnyParlay)

Files audited (10 read): calibrate_distributions.py, calibrate_platt.py, calibrate_sigma.py, calibrate_winprob.py, nb_calibrate.py, evaluate_projector.py, historical_backtest.py, sabersim_backtest.py, projection_accuracy.py, empirical_analysis.py

**Findings (final, excl. refuted): C=0 H=0 M=1 I=7** | constants extracted: 18 | not-done: 8

## Findings

| ID | File:line | Sev | Status | Cat | Known | Title |
|----|-----------|-----|--------|-----|-------|-------|
| JP10-F1 | calibrate_distributions.py:434 | M | confirmed | statistical |  | wnba-3pm recommends POOLED NB dispersion r, contradicting the within-player method used everywhere else |
| JP10-F2 | calibrate_distributions.py:156 | I | refuted | statistical |  | mlb-team-runs NB r fit on variance pooled across all teams inflates overdispersion |
| JP10-F13 | calibrate_distributions.py:105 | I | unverified | statistical |  | Crude integer-index percentile helpers (acceptable for advisory output) |
| JP10-F6 | calibrate_platt.py:38 | I | unverified | statistical | Y | Platt fit is logit-space but the live run_picks formula is raw-probability space (KNOWN/superseded) |
| JP10-F5 | calibrate_winprob.py:174 | I | confirmed | statistical |  | Win-prob CV is non-time-ordered standard k-fold (future leakage) yet labelled 'use for go/no-go' |
| JP10-F12 | empirical_analysis.py:4 | I | unverified | completeness |  | empirical_analysis.py is a frozen one-off with hardcoded absolute user paths |
| JP10-F11 | evaluate_projector.py:215 | I | refuted | code |  | Eval harness re-implements the projector instead of calling project_player — silent drift risk |
| JP10-F3 | historical_backtest.py:386 | I | refuted | statistical |  | Minutes 'Suggested scalar' uses mean-of-ratios (Jensen-biased high) while per-role uses ratio-of-means |
| JP10-F10 | nb_calibrate.py:14 | I | refuted | completeness |  | Live MLB NB dispersions K r=5.0 and HRR r=1.5 are provisional/single-point, not calibrated here |
| JP10-F8 | nb_calibrate.py:27 | I | unverified | code |  | Dead CURRENT dict and relative DB_PATH in nb_calibrate.py |
| JP10-F9 | projection_accuracy.py:223 | I | unverified | code |  | Unused variable 'today' in rolling-trend block |
| JP10-F4 | sabersim_backtest.py:244 | I | refuted | code |  | Backtest regen writes into the LIVE projections.db (persist=True) for historical dates |
| JP10-F7 | sabersim_backtest.py:405 | I | confirmed | code |  | Unicode glyphs in stdout can crash under cp1252-redirected output |

## C/H/M detail

### [M] JP10-F1 — wnba-3pm recommends POOLED NB dispersion r, contradicting the within-player method used everywhere else
`C:/Dev/JonnyParlay/engine/calibrate_distributions.py:434-456` · statistical · status=confirmed

**Evidence:** mode_wnba_3pm computes r_pool = _nb_r(mu_pool, var_pool) from the POOLED 3PM distribution across all players (line 438) and prints it as the headline 'WNBA calibrated NB_R' / deploy value (lines 453-455). Pooled var/mu conflates large player-to-player heterogeneity (some players attempt 0 threes, others 8+) with within-player game variance, so it massively overstates overdispersion -> r too small -> tails too fat. The within-player var/mu ratios ARE computed (line 441) but only printed as a diagnostic, never turned into an r. This is inconsistent with nb_calibrate.py which uses the within-player estimator r=avg_mu/(avg(var/mu)-1), and with the NBA reference printed on line 452 ('NB_R=9.15, var/mu=1.149') whose 1.149 is itself a within-player ratio (pooled 3PM var/mu is far above 1.149). An engineer copying the printed value would deploy a too-small NB_R.

**Recommendation:** Compute the recommended r from the within-player ratios (median var/mu) as nb_calibrate.py does, not from r_pool. Keep r_pool only as a labelled diagnostic.

**Verifier (confirmed):** Confirmed and material. The code at C:/Dev/JonnyParlay/engine/calibrate_distributions.py:434-456 does exactly what the finding claims: r_pool is computed from the POOLED 3PM mu/var (line 438) and printed as the headline 'WNBA calibrated NB_R' and 'Deploy' value (lines 453-455), while the within-player var/mu ratios (line 441) are printed only as a diagnostic (line 450) and never turned into an r. This contradicts nb_calibrate.py (lines 4-6/75: r = avg_mu/(avg(var/mu)-1), explicitly 'within-playe


## Confirmed-correct / coverage notes

- **Scope context:** All ten files are OFFLINE calibration/eval/backtest tools. None is imported by the daily run (`generate_projections.py`); they print recommended constants for an engineer to paste, or report MAE/Brier diagnostics. So there is no direct C-severity live-price/crash path inside this module — the live risk is indirect (a wrong *recommended* constant being copied into run_picks.py / nba_projector.py).
- **Scalar-suggestion math is correct (coverage):** In historical_backtest.py (line 310), projection_accuracy.py (line 126) and evaluate_projector the bias->scalar correction `sugg=(mean_p - bias)/mean_p` reduces to `mean_actual/mean_proj`, the right multiplicative bias-zeroing factor, with `bias=proj-actual` sign consistent throughout. NewScalar = CurrScalar × correction is applied consistently.
- **calibrate_platt.py guards are sound:** native-only default drops legacy double-calibrated rows; H3 gate blocks at n<100; OOS-negative Brier hard-exits (line 318) preventing bad constant paste; CV is a true time-ordered expanding window (no leakage); symmetric intercept bounds (-3,3) correctly fixed the earlier under-heavy mis-fit.
- **calibrate_winprob.py correctly self-flags** that its win_prob input is already Platt-calibrated and prints DO-NOT-PASTE warnings; it hard-exits on negative OOS Brier. Its only weakness is the non-time-ordered CV (F5).
- **sabersim_backtest.py comparison is apples-to-apples** (SaberSim raw error vs custom raw error, both proj-actual); season inference (month>=10 boundary) is correct; the BETTER/WORSE delta sign is correct.
- **evaluate_projector.py** correctly uses RATE_MIN_MIN=20 to align training and eval minute distributions, reports both raw and production (RS-scalar) frames, and documents the residual minutes-selection bias rather than hiding it; grid-search ranges bracket the deployed alphas (PTS 0.30 at the 0.25 edge, 3PM 0.65 mid-range).
- **NB/ZINB helper math** in calibrate_distributions.py (_nb_r, _nb_zero_prob, _zinb_pi) matches standard NB(mu,r) parameterization; Poisson limit (var<=mu -> r=inf -> exp(-mu)) handled correctly.
- **Team-id maps** (_MLB_ID_MAP, _NBA_ID_MAP) spot-checked correct (e.g. MLB 120=WSH, 158=MIL, 145=CWS; NBA 1610612740=NOP, 1610612766=CHA).
- **NHL Poisson sanity check** (mu=6.19 -> sigma=sqrt(6.19)=2.49) is arithmetically correct and the empirical sigma replacing the old 1.2/1.5 is directionally right (old values were ~2x too tight)."

## Not-Done / incomplete (this module)

| Kind | File | Detail |
|------|------|--------|
| flag-gated | calibrate_platt.py | H3 logit-space migration (Step1 formula + PLATT_SPACE + A/B) deferred behind n>=100/n>=300 data gate; free 2-parameter fit deferred to n>=300. Superseded by Jon |
| deferred | nb_calibrate.py | K (pitcher strikeouts) r=5.0 is provisional/undocumented and HRR r=1.5 is single-point moment-matched; proper within-player var/mu refit deferred pending an MLB |
| dead-code | nb_calibrate.py | CURRENT={'3PM':9.15,'AST':9.68,'REB':10.18} defined but never used; values hardcoded inline in the loop. |
| deferred | calibrate_sigma.py | MLB pitcher/batter stats (OUTS, HA, K, HRR) not calibrated — no game-log data in projections.db (see backlog). AST has NO SIGMA entry and falls back to mult=0.4 |
| partial-feature | calibrate_distributions.py | wnba-3pm deploy note says to also 'remove WNBA 3PM from Normal path in calc_prop_prob()' — a pending manual deploy step. wnba-sigma 3PM proxy (0.48 vs empirical |
| dead-code | projection_accuracy.py | Unused 'today' variable in the rolling-trend block (line 224). |
| dead-code | empirical_analysis.py | Frozen one-off research snapshot (2026-05-24) with hardcoded absolute user paths and no CLI/main guard; not part of any automated pipeline. |
| partial-feature | evaluate_projector.py | Component projectors re-implement project_player rather than calling it; eval can silently drift from production if the EdgeModel pipeline changes without mirro |
