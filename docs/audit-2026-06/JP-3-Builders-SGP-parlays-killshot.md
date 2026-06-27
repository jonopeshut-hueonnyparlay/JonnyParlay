# AUDIT 2026-06 — JP-3 Builders (SGP/parlays/killshot) (JonnyParlay)

Files audited (11 read): sgp_builder.py, mlb_sgp_builder.py, parlays.py, killshot.py, sgp_builder.py, copula.py, distributions.py, odds.py, COMBO sections), daily sections), run_picks.py (SGP invocation 1595-1647)

**Findings (final, excl. refuted): C=0 H=1 M=2 I=8** | constants extracted: 28 | not-done: 6

## Findings

| ID | File:line | Sev | Status | Cat | Known | Title |
|----|-----------|-----|--------|-----|-------|-------|
| JP3-01 | sgp_builder.py:219 | H | confirmed | statistical | Y | SGP/MLB-SGP leg win-probs bypass the Platt/temperature calibration that straight props receive |
| JP3-03 | mlb_sgp_builder.py:390 | M | confirmed | code |  | MLB _size_mlb_sgp omits the cohesion>=0.55 gate that NBA size_sgp enforces, despite docstring claiming parity |
| JP3-05 | sgp_builder.py:591 | M | confirmed | code |  | NBA candidate dropped when its global-best book is not allowed, even if an allowed book also offers the leg |
| JP3-14 | killshot.py:135 | I | unverified | code |  | KILLSHOT weekly-cap counter fails SAFE (returns full cap on read error) |
| JP3-08 | mlb_sgp_builder.py:560 | I | confirmed | code |  | MLB candidate filter has no upper odds bound (NBA rejects odds > -115); plus-money / low-juice legs can enter MLB SGPs |
| JP3-09 | mlb_sgp_builder.py:596 | I | refuted | code |  | One unconfirmed pitcher prop in the candidate pool kills the entire game's SGP, including batter-only slips |
| JP3-12 | mlb_sgp_builder.py:225 | I | unverified | statistical | Y | MLB rho 0.30 (OUTS-over x opposing-HITS-under) is an unfit structural prior, refit-gated at n=160 |
| JP3-13 | parlays.py:67 | I | unverified | statistical | Y | build_safest6 ranks by hit-frequency (win_prob), not EV — intentional product decision, documented |
| JP3-02 | copula.py:114 | I | refuted | statistical | Y | t-copula (nu=6) adds upward tail-dependence to the joint estimate used as the EV-gate numerator, with no offsetting deflator on th |
| JP3-04 | sgp_builder.py:423 | I | confirmed | code |  | NBA SGP _api_get has no 429/Retry-After handling (MLB has one); a transient rate-limit drops the entire NBA SGP slate |
| JP3-06 | sgp_builder.py:707 | I | refuted | statistical |  | size_sgp Gate 2 (copula minus independence-product >= 0.015) is almost always satisfied and adds little protection |
| JP3-07 | sgp_builder.py:660 | I | confirmed | statistical |  | NBA _score_sgp runs full 1000-sample MC copula for every searched combo; module header claims the fast equicorr approx is used in  |
| JP3-10 | sgp_builder.py:57 | I | unverified | completeness |  | IDEAL_LEG_WIN_PROB defined but never referenced (dead constant) |
| JP3-11 | sgp_builder.py:286 | I | unverified | statistical | Y | NBA SGP pairwise rho table is hardcoded with n_observations 'unrecorded' (self-acknowledged audit gap) |

## C/H/M detail

### [H] JP3-01 — SGP/MLB-SGP leg win-probs bypass the Platt/temperature calibration that straight props receive
`C:/Dev/JonnyParlay/engine/sgp_builder.py:219-257` · statistical · status=confirmed · KNOWN open gate

**Evidence:** _fair_prob (sgp 219-257) and _fair_prob_mlb (mlb 120-143) compute leg win-probabilities straight from the raw NB/Normal/Poisson distribution math (NB_R, SIGMA, _OUTS_SIGMA) with NO calibration shrink. There is no import of prob_core/calibrate_platt anywhere in either builder. These raw fair_probs then feed the copula joint, the joint-EV gate (SGP_JOINT_EV_MARGIN=0.025), the premium-sizing gate (>=0.10) and the displayed/logged win_prob. The KNOWN open gate is that the EdgeModel marginals are ~+8.8pp overconfident (sigma too tight). Overconfident, uncalibrated 0.65-0.75 leg probs compound multiplicatively into a hugely inflated joint, so the +EV gates are systematically defeated and 0.50u premium sizing fires on slips that are likely -EV.

**Recommendation:** Apply the same per-leg calibration (Platt/temperature) used for straight props before feeding fair_prob into the copula and the EV/sizing gates, or hold SGP premium sizing at 0.25u until the sigma/temperature refit lands.

**Verifier (confirmed):** Code-verified and reachable. SGP leg probs come from raw distribution math with no calibration: sgp_builder.py:578 `fair = _fair_prob(...)` and :662 `probs = [l["fair_prob"] for l in legs]` feed `_copula_joint_prob` directly (NB_R/SIGMA only). mlb_sgp_builder.py:120-143 `_fair_prob_mlb` is identical (Poisson/Normal, _OUTS_SIGMA, no shrink). Neither builder imports prob_core/_platt_calibrate_prop. By contrast, the straight-prop path applies TWO compressors that the SGP path skips: evaluators.py:1

### [M] JP3-03 — MLB _size_mlb_sgp omits the cohesion>=0.55 gate that NBA size_sgp enforces, despite docstring claiming parity
`C:/Dev/JonnyParlay/engine/mlb_sgp_builder.py:390-406` · code · status=confirmed

**Evidence:** NBA size_sgp gates premium 0.50u on `avg_edge>=0.035 AND cohesion>=0.55 AND copula-implied>=0.10 AND copula-indep>=0.015` (sgp 695-717). MLB _size_mlb_sgp docstring says 'Same quality gates as NBA SGP sizing' (mlb 391) but only checks `avg_edge>=0.035` then the two copula gates (mlb 393-405) — the cohesion>=0.55 gate is absent. MLB therefore steps to 0.50u more readily than NBA on live money.

**Recommendation:** Either add the cohesion>=0.55 gate to _size_mlb_sgp (compute _correlation_cohesion_mlb) or correct the docstring and document the intentional MLB divergence.

**Verifier (confirmed):** Code confirms the claim. NBA size_sgp (engine/sgp_builder.py:695-697) gates premium sizing on `avg_edge < 0.035 or cohesion_score < 0.55` before the two copula gates, and its docstring (685-691) lists cohesion>=0.55 as an explicit quality gate. MLB _size_mlb_sgp (engine/mlb_sgp_builder.py:390-406) checks avg_edge>=0.035 then only the two copula gates (cj-parlay_implied>=0.10, cj-no_vig_indep>=0.015) and never references cohesion, despite its docstring (line 391) claiming 'Same quality gates as N

### [M] JP3-05 — NBA candidate dropped when its global-best book is not allowed, even if an allowed book also offers the leg
`C:/Dev/JonnyParlay/engine/sgp_builder.py:591-595` · code · status=confirmed

**Evidence:** build_candidate_legs uses info['book']/info['odds'] = the single best price across ALL books (fetch_event_props 486-491 does not filter by SGP_ALLOWED_BOOKS). Line 595 then `if book not in SGP_ALLOWED_BOOKS: continue` discards the entire candidate when the global-best book is e.g. an unallowed exchange, even though book_odds may contain fanduel/betmgm for that same leg. MLB avoids this by filtering at fetch time (mlb 494). NBA therefore under-generates legs that allowed books carry.

**Recommendation:** Filter to allowed-book best price when computing the candidate (intersect book_odds with SGP_ALLOWED_BOOKS) rather than dropping on the global-best book.

**Verifier (confirmed):** Code claims verified against the actual source. NBA fetch_event_props (engine/sgp_builder.py 451-499) does NOT filter bookmakers by SGP_ALLOWED_BOOKS — it walks all books returned by ODDS_REGIONS="us,us2,us_ex" (exchanges via us_ex + non-allowed us2 books) and stores info['book']/info['odds'] as the single GLOBAL-best price/book (lines 486-487). build_candidate_legs line 595 (`if book not in SGP_ALLOWED_BOOKS: continue`) then discards the whole candidate when that global-best book is unallowed, 


## Confirmed-correct / coverage notes

- **Distribution math is correct.** Poisson/Normal/NegBinom PMFs/CDFs (quant/distributions.py) are standard; NB parameterisation p=r/(r+mu), variance=mu+mu^2/r is correct and var/mu rises with mu (right direction). Push-adjustment for integer lines (strict_over/strict_under / non_push) is correct in both _fair_prob and _fair_prob_mlb; SGP lines are predominantly half-integer so the push path rarely fires.
- **t-copula construction is mathematically sound.** copula_joint_prob factors R=LL^T, samples chi2(df), forms t-marginals t_i=z_i/sqrt(chi2/df), and compares to scipy t.ppf(p_i,df) — a valid t-copula. Fixed seed=42 makes the joint, and therefore all gating, deterministic across runs/machines (resolves any MC-nondeterminism concern).
- **rho sign convention is in win-event space and internally consistent.** Positive rho is assigned to leg pairs whose win indicators co-occur (same-team overs, OUTS-over x opposing-HITS-under), negative for tension pairs; matches what the copula needs.
- **PSD safety is enforced at import.** _assert_rho_matrices_wellformed (NBA) and _assert_rho_matrices_mlb_wellformed (MLB) validate the rho hierarchy is symmetric, in-range and PSD at module load, guarding the silent independence-product fallback in copula_joint_prob.
- **NB_R single-source contract is enforced.** _assert_nb_r_single_source guarantees 3PM/AST/REB resolve from calibrated.NB_R (9.15/9.66/13.16) and BLK/STL stay local — drift is structurally impossible.
- **Hard-kill correlation rules are sound.** R0-R4 (NBA) and R0/R1/R2_MLB dedup/contradiction rules, plus per-player and per-game caps, are correct and conservative.
- **Builders are crash-isolated in the daily run.** run_sgp_builder and run_mlb_sgp_builder are each wrapped in try/except in run_picks.py (1606-1640), so an API/parse error skips the SGP stage rather than aborting the daily run.
- **decimal_to_american returns int**, so all `{odds:+d}` formatting in embeds/console is safe.
- **KILLSHOT gating is correct and self-checking.** Odds-dependent wp floor (implied+0.03) closes the static-0.65 -EV window; _assert_killshot_invariants fails fast on dead/suspended allowlist entries; weekly-cap counter fails SAFE (returns full cap on error) under the shared pick-log lock; manual-promote still enforces odds/wp.
- **alt-spread cover math is correct:** cover_prob = 1 - normal_cdf(-line, margin, sigma) correctly yields P(margin_outcome > -line); use of one-sided vigged implied is documented and conservative.
- **Longshot effective-wp boost is a correct bivariate-Bernoulli identity** (joint = pq + rho*sqrt(p(1-p)q(1-q)), P(p|q)=joint/q), used for ranking only with the displayed combined_prob kept as the conservative independence product.

## Not-Done / incomplete (this module)

| Kind | File | Detail |
|------|------|--------|
| deferred | sgp_builder.py | SGP_JOINT_EV_MARGIN=0.025 and premium gates (0.035/0.55/0.10/0.015) are explicitly DATA_GATED: 'tune against CLV/W-L data over 50+ builds' / 're-tune at n=100 s |
| deferred | mlb_sgp_builder.py | MLB pairwise rho is a structural prior; empirical-Bayes magnitude refit (shrink observed r toward 0.30) deferred until n>=160 scored MLB SGP slips (_log_mlb_sgp |
| dead-code | sgp_builder.py | IDEAL_LEG_WIN_PROB=0.70 (line 57) is defined but never referenced anywhere. |
| dead-code | sgp_builder.py | POISSON_STATS is an empty set (line 78) so the Poisson branch in _fair_prob (220-234) is unreachable; AST/REB moved to NB_STATS. Intentional but dead. |
| partial-feature | mlb_sgp_builder.py | Shadow stats HRR/RBI/RUNS/ER excluded from the MLB SGP pool until they graduate to live status (header lines 8-9); only OUTS and HITS are live. |
| partial-feature | sgp_builder.py | Module header advertises a fast equicorrelation approx for the 91k-combo search, but _score_sgp actually runs full 1000-sample MC per combo (the documented appr |
