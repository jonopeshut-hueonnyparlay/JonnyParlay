"""Gaussian copula joint-probability math for same-game parlays.

Pure functions — stdlib ``math`` + ``random`` only. Extracted verbatim from
sgp_builder.py (the canonical implementation). The Monte-Carlo sampler builds its
RNG inside the function from the ``seed`` argument (default 42), so output is
bit-identical across runs and machines for a given (probs, corr_mat, n_samples, seed).

The domain-specific correlation lookup (``_pairwise_rho``) and matrix builder
(``_build_corr_matrix``) deliberately stay in sgp_builder.py — they encode NBA
business logic, not generic math.
"""
import math
import random


def probit(p):
    """Standard normal quantile function Φ^{-1}(p).

    Uses math.erfinv when available (Python ≥ 3.12); otherwise falls back to
    the Beasley-Springer-Moro rational approximation (max error ≈ 4.5e-4).
    """
    p = max(1e-9, min(1.0 - 1e-9, p))
    try:
        return math.sqrt(2.0) * math.erfinv(2.0 * p - 1.0)
    except AttributeError:
        # BSM coefficients
        _a = [2.50662823884, -18.61500062529, 41.39119773534, -25.44106049637]
        _b = [-8.47351093090, 23.08336743743, -21.06224101826, 3.13082909833]
        _c = [0.3374754822726147, 0.9761690190917186, 0.1607979714918209,
              0.0276438810333863, 0.0038405729373609, 0.0003951896511349,
              0.0000321767881768, 0.0000002888167364, 0.0000003960315187]
        y = p - 0.5
        if abs(y) < 0.42:
            r = y * y
            return y * ((((_a[3]*r + _a[2])*r + _a[1])*r + _a[0])
                        / ((((_b[3]*r + _b[2])*r + _b[1])*r + _b[0])*r + 1.0))
        r = p if y < 0 else 1.0 - p
        r = math.log(-math.log(r))
        x = _c[0] + r*(_c[1] + r*(_c[2] + r*(_c[3] + r*(_c[4]
              + r*(_c[5] + r*(_c[6] + r*(_c[7] + r*_c[8])))))))
        return -x if y < 0 else x


def cholesky(mat):
    """Lower triangular Cholesky L such that mat = L @ L^T (n ≤ 4).

    Clips near-zero diagonal to avoid sqrt of negative due to floating-point
    rounding on near-singular matrices.
    """
    n = len(mat)
    L = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1):
            s = sum(L[i][k] * L[j][k] for k in range(j))
            if i == j:
                L[i][j] = math.sqrt(max(mat[i][i] - s, 1e-12))
            else:
                L[i][j] = (mat[i][j] - s) / L[j][j] if L[j][j] > 1e-12 else 0.0
    return L


def copula_joint_prob(probs, corr_mat, n_samples=4000, seed=42):
    """Gaussian copula joint probability via Monte Carlo.

    P(all legs hit) accounting for inter-leg correlations.  Algorithm:
      1. Factorize R = L L^T  (Cholesky)
      2. Sample ε ~ N(0, I_n)
      3. x = L ε  → correlated standard normals with cov = R
      4. U_i = Φ(x_i)  → correlated uniform marginals
      5. Joint hit = all U_i ≤ p_i  (equivalent to all x_i ≤ Φ^{-1}(p_i))

    At n_samples=4000: SE ≈ 0.7% for joint≈0.40.  Fixed seed gives
    reproducible scores for identical leg sets.

    Runtime: ~2 ms for 4-leg at 4000 samples (called once per final SGP).
    """
    n = len(probs)
    if n == 0:
        return 0.0
    if n == 1:
        return probs[0]
    try:
        L = cholesky(corr_mat)
    except Exception:
        result = 1.0
        for p in probs:
            result *= p
        return result

    rng = random.Random(seed)
    gauss = rng.gauss
    erf = math.erf
    inv_sqrt2 = 1.0 / math.sqrt(2.0)
    hits = 0
    for _ in range(n_samples):
        eps = [gauss(0.0, 1.0) for _ in range(n)]
        ok = True
        for i in range(n):
            xi = sum(L[i][k] * eps[k] for k in range(i + 1))
            ui = 0.5 * (1.0 + erf(xi * inv_sqrt2))
            if ui > probs[i]:
                ok = False
                break
        if ok:
            hits += 1
    return hits / n_samples


def copula_joint_approx(probs, avg_rho):
    """Fast equicorrelation Gaussian copula approximation for combo scoring.

    Linearly interpolates between independence (ρ=0) and perfect correlation
    (ρ=1, joint = min(p_i)).  Error ~15-20% for ρ ∈ [0.20, 0.35] — accurate
    enough to rank 91k combos; full MC is reserved for the final chosen SGP.
    """
    p_indep = 1.0
    for p in probs:
        p_indep *= p
    p_min = min(probs)
    # Plan 10 §Z: linear interp is optimistically biased +8% (3-leg) to +29% (4-leg, low-p)
    # vs full Gaussian copula MC; deflate by 0.87 (midpoint of recommended 0.85-0.90).
    return (p_indep + avg_rho * (p_min - p_indep)) * 0.87
