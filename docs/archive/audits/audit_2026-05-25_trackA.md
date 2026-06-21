# Audit 2026-05-25 — Track A: Numerical Correctness (v2 — post REB/AST→NB + SIGMA update)

Auditor: Claude Sonnet 4.6 (fresh session, post-2026-05-25 changes)
Scope: engine/run_picks.py — distribution functions, vig removal, push handling, combo probability
Re-audited after: REB→NB(r=10.18), AST→NB(r=9.68), SIGMA["AST"] added (mult=0.53/min=2.0),
  SIGMA["REB"] updated (mult=0.48/min=2.0 for combo path), SIGMA["PTS"] min raised 4.5→5.0.

---

## Function Locations

| Function | Line |
|---|---|
| `poisson_pmf` | ~562 |
| `poisson_cdf` | ~568 |
| `normal_cdf` | ~577 |
| `negbinom_pmf` | ~584 |
| `negbinom_cdf` | ~608 |
| `implied_prob` | ~617 |
| `no_vig` | ~626 |
| `_platt_calibrate_prop` | ~641 |
| `calc_prop_prob` (push handling) | ~654 |
| `_combo_mu_sigma` | ~760 |
| `calc_combo_prob` | ~785 |
| `calc_edge` | ~792 |
| `COMBO_RHO` dict | ~315 |

---

## Verified Correct

1. **poisson_pmf** (~562): `math.exp(-lam) * (lam ** k) / math.factorial(k)` — textbook correct. No overflow at max production k=8 (POISSON_CUTOFF=8.5 → floor=8; `8.5^8 ≈ 2.7e7`, well within float64). Python's arbitrary-precision `factorial` prevents integer overflow.
2. **poisson_cdf** (~568): Correct cumulative sum with `min(total, 1.0)` clamp.
3. **negbinom_pmf** (~584): Log-space formula `lgamma(k+r) - lgamma(r) - lgamma(k+1) + r*log(p) + k*log(1-p)` is correct. Parameterisation `p = r/(r+mu)` gives E[X] = mu. Verified mathematically.
4. **negbinom_cdf** (~608): Finite discrete sum over 0..k — exact, no convergence issue. `min(total, 1.0)` guard present.
5. **normal_cdf** (~577): `0.5 * (1 + erf(x/sqrt(2)))` — textbook correct. `math.erf` numerically stable at tails.
6. **implied_prob** (~617): Both branches correct (`abs(odds)/(abs(odds)+100)` for negatives; `100/(odds+100)` for positives). `odds=0` returns `0.0` safely.
7. **no_vig** (~626): Standard additive/proportional vig removal (`imp/sum`). `total==0` returns `(0.5, 0.5)`.
8. **Push handling — Poisson** (~673–683): `over_p = strict_over / (1 - push)` is mathematically correct. `strict_over + strict_under + push = 1.0` exactly, so `over_p + under_p = 1.0`. Guard on `non_push > 0` at line ~678.
9. **Push handling — NB** (~692–702): Identical logic, using `negbinom_pmf` and `negbinom_cdf`. Correct.
10. **`_combo_mu_sigma` joint variance** (~776–781): `Var(X+Y) = Var(X) + Var(Y) + 2ρσ_Xσ_Y` — textbook correct, extended to triple sum for PRA.
11. **COMBO_RHO** (~315): Pearson correlations from 75,367 player-games. Missing-pair fallback (0.20 NBA / 0.10 WNBA) is reasonable.
12. **`proj=0` edge case**: `sigma = max(0 * mult, min_floor) = min_floor` — positive, no division by zero.

---

## Findings

### A-1 — CLOSED (was HIGH) — AST sigma fallback in combo path

**STATUS: FIXED** by 2026-05-25 changes. `SIGMA["AST"] = {"mult": 0.53, "min": 2.0}` is now
present in run_picks.py (~line 270) with comment "NEW — combo path only; 3-season median CV=0.507".
`_combo_mu_sigma()` now correctly uses the calibrated value for PA, RA, PRA combinations.
Fresh-session verification confirmed at line ~785: `SIGMA.get("AST")` returns `{mult:0.53, min:2.0}`.
**No further action needed.**

### A-2 (MEDIUM) — No push adjustment for combo stats

```
TRACK: A
FILE: engine/run_picks.py
LINE: ~785–789
SEVERITY: MEDIUM
N: N/A
ISSUE: calc_combo_prob() applies no push adjustment for integer combo lines. Normal CDF
is continuous so P(X=k)=0, but books can offer integer combo lines (e.g. PRA=35, PR=30).
IMPACT: Low in practice — SaberSim lines are predominantly half-integers. If integer combo
line appears, model implicitly assumes no push, slightly mis-stating both over_p and under_p.
Direction of bias depends on projection vs line.
FIX: No urgent fix. Document assumption. Revisit if integer combo lines become common.
```

### A-3 (MEDIUM) — G3 gate is dead code for props

```
TRACK: A
FILE: engine/run_picks.py
LINE: ~897–898, ~2229–2230
SEVERITY: MEDIUM
N: N/A
ISSUE: G3 gate checks pick.get("missing_side") but missing_side is never set to True in any
prop-creation path — missing-side props are silently dropped at line ~2229 (continue) before
a pick dict is built. G3 provides false assurance in gate-logic reviews.
IMPACT: No current production error. If a future code path creates a pick with missing_side=True,
the flag would be checked correctly. But as a code review artifact it is misleading.
FIX: Either remove G3 or add a comment: "# dead for standard prop path — missing_side never True".
```

### A-4 (LOW) — poisson_pmf uses non-log-space arithmetic

```
TRACK: A
FILE: engine/run_picks.py
LINE: ~562–566
SEVERITY: LOW
N: N/A
ISSUE: poisson_pmf uses math.factorial(k) and lam**k (direct multiplication) rather than
log-space arithmetic like negbinom_pmf. Safe at current POISSON_CUTOFF=8.5 (max k=8),
but inconsistent with NB approach and would overflow if cutoff were ever raised above ~150.
IMPACT: None in production.
FIX: No change needed unless POISSON_CUTOFF is raised significantly.
```

### A-5 (LOW) — normal_cdf at sigma=0, x=mu returns 1.0 (should be 0.5)

```
TRACK: A
FILE: engine/run_picks.py
LINE: ~577–581
SEVERITY: LOW
N: N/A
ISSUE: At sigma=0 and x==mu, code returns 1.0 (under_p=1.0, over_p=0.0). Correct answer for
degenerate N(mu,0) is 0.5/0.5 by convention. Cannot occur in production (all SIGMA entries
have positive min floor).
IMPACT: None in production.
FIX: None needed.
```

---

## Verified: Single-sided props handled correctly

Missing-side props are dropped at ~2229 before any pick dict is created. `missing_side` is hardcoded `False` at pick-creation sites. The G3 gate would only fire if a future code path explicitly set `missing_side=True`. This is correct and safe behavior.
