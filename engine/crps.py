"""crps.py -- Continuous Ranked Probability Score (Stage-1 metric design, #11).

CRPS is the proper score for a FULL predictive distribution against a realized
continuous outcome (Brier's continuous generalization): it rewards both calibration
and sharpness, and reduces to Brier when the outcome is binarized at a threshold.

    CRPS(F, y) = integral_-inf^inf (F(x) - 1{y <= x})^2 dx

Lower is better; a point forecast at y scores 0. This module gives the closed-form
Normal CRPS, an empirical (ensemble) CRPS, and a discrete-support CRPS from a CDF --
enough to score either a Normal or a count (Poisson/NB) predictive distribution. Pure
stdlib; no numpy.
"""
from __future__ import annotations

import math

_INV_SQRT_PI = 1.0 / math.sqrt(math.pi)
_SQRT2 = math.sqrt(2.0)
_SQRT2PI = math.sqrt(2.0 * math.pi)


def _std_norm_cdf(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / _SQRT2))


def _std_norm_pdf(z: float) -> float:
    return math.exp(-0.5 * z * z) / _SQRT2PI


def crps_normal(mu: float, sigma: float, y: float) -> float:
    """Closed-form CRPS for a Normal predictive N(mu, sigma) vs outcome y.

    CRPS = sigma * [ z*(2*Phi(z)-1) + 2*phi(z) - 1/sqrt(pi) ],  z = (y-mu)/sigma
    (Gneiting & Raftery 2007). sigma<=0 (a point forecast) degenerates to |y-mu|.
    """
    mu, y = float(mu), float(y)
    sigma = float(sigma)
    if sigma <= 0.0:
        return abs(y - mu)
    z = (y - mu) / sigma
    return sigma * (z * (2.0 * _std_norm_cdf(z) - 1.0) + 2.0 * _std_norm_pdf(z) - _INV_SQRT_PI)


def crps_ensemble(samples, y: float) -> float:
    """Empirical CRPS from an ensemble/sample set:  mean|X-y| - 0.5*mean|X-X'|."""
    xs = [float(s) for s in samples]
    n = len(xs)
    if n == 0:
        raise ValueError("crps_ensemble: empty ensemble")
    y = float(y)
    term1 = sum(abs(x - y) for x in xs) / n
    term2 = sum(abs(a - b) for a in xs for b in xs) / (n * n)
    return term1 - 0.5 * term2


def crps_from_cdf(cdf, y: float, lo: int, hi: int) -> float:
    """Discrete-support CRPS for an integer-valued predictive distribution.

    CRPS = sum_{k=lo}^{hi} (F(k) - 1{y <= k})^2, where cdf(k)=F(k)=P(X<=k). Use for
    count predictives (Poisson / negative binomial) with support truncated to [lo, hi].
    """
    y = float(y)
    total = 0.0
    for k in range(int(lo), int(hi) + 1):
        ind = 1.0 if y <= k else 0.0
        total += (float(cdf(k)) - ind) ** 2
    return total
