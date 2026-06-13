"""Property/invariant tests for the pure-math quant modules.

Complements tests/test_quant_golden.py — that file locks exact fixed-point
values; this file asserts structural invariants (monotonicity, normalization,
bounds, symmetry, round-trips) that should hold across ranges of inputs.

Imports the implementations directly from quant.* (conftest puts engine/ on
sys.path), not via the run_picks re-export.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "engine"))

import pytest

from quant.distributions import (
    poisson_pmf, poisson_cdf, normal_cdf, negbinom_pmf, negbinom_cdf,
)
from quant.odds import (
    implied_prob, no_vig, is_decimal_leak, prob_to_american,
    american_to_decimal, decimal_to_american,
)
from quant.derived import calc_tb_prob, mlb_ml_from_nb, calc_edge


# ---------------------------------------------------------------------------
# quant.distributions
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("mu", [2.0, 5.0])
def test_poisson_cdf_monotone_in_k(mu):
    prev = -1.0
    for k in range(6):
        cur = poisson_cdf(k, mu)
        assert cur >= prev - 1e-12, f"poisson_cdf not monotone at k={k}, mu={mu}"
        prev = cur


@pytest.mark.parametrize("mu", [0.5, 2.0, 5.0])
def test_poisson_pmf_sums_to_one(mu):
    total = sum(poisson_pmf(k, mu) for k in range(51))
    assert total == pytest.approx(1.0, abs=1e-6)


@pytest.mark.parametrize("mu", [2.0, 5.0])
def test_poisson_pmf_nonnegative(mu):
    for k in range(40):
        assert poisson_pmf(k, mu) >= 0.0


def test_normal_cdf_in_unit_interval():
    # Moderate x (within a few sigma): genuinely interior. Extreme tails
    # underflow erf to exactly 0.0/1.0 and are covered by the tail-limit test.
    for x in (-1.0, 0.0, 12.3, 20.0):
        v = normal_cdf(x, 10.0, 4.0)
        assert 0.0 < v < 1.0


def test_normal_cdf_tail_limits():
    mu, sigma = 25.0, 5.0
    assert normal_cdf(mu - 10 * sigma, mu, sigma) == pytest.approx(0.0, abs=1e-9)
    assert normal_cdf(mu + 10 * sigma, mu, sigma) == pytest.approx(1.0, abs=1e-9)


def test_normal_cdf_reflection_symmetry():
    mu, sigma = 25.0, 5.0
    for x in (18.0, 25.0, 31.0):
        assert normal_cdf(x, mu, sigma) + normal_cdf(2 * mu - x, mu, sigma) == pytest.approx(1.0)


def test_normal_cdf_zero_sigma_is_step():
    assert normal_cdf(6.0, 5.0, 0.0) == 1.0   # x >= mu
    assert normal_cdf(5.0, 5.0, 0.0) == 1.0   # x == mu
    assert normal_cdf(4.0, 5.0, 0.0) == 0.0   # x < mu


@pytest.mark.parametrize("mu,r", [(5.0, 9.15), (12.0, 14.7)])
def test_negbinom_cdf_monotone_in_k(mu, r):
    prev = -1.0
    for k in range(12):
        cur = negbinom_cdf(k, mu, r)
        assert cur >= prev - 1e-12
        prev = cur


@pytest.mark.parametrize("mu,r", [(5.0, 9.15), (12.0, 14.7)])
def test_negbinom_pmf_sums_to_one(mu, r):
    total = sum(negbinom_pmf(k, mu, r) for k in range(201))
    assert total == pytest.approx(1.0, abs=1e-4)


def test_negbinom_pmf_nonnegative():
    for k in range(60):
        assert negbinom_pmf(k, 8.0, 12.0) >= 0.0


def test_negbinom_pmf_negative_k_is_zero():
    assert negbinom_pmf(-1, 5.0, 9.15) == 0.0
    assert negbinom_pmf(-5, 5.0, 9.15) == 0.0


def test_negbinom_pmf_nonpositive_r_raises():
    with pytest.raises(ValueError):
        negbinom_pmf(3, 5.0, 0.0)
    with pytest.raises(ValueError):
        negbinom_pmf(3, 5.0, -1.0)


# ---------------------------------------------------------------------------
# quant.odds
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("odds", [-500, -200, -150, -110, 100, 150, 200])
def test_implied_prob_in_unit_interval(odds):
    assert 0.0 < implied_prob(odds) < 1.0


def test_implied_prob_zero():
    assert implied_prob(0) == 0.0


@pytest.mark.parametrize("p,q", [(0.55, 0.55), (0.6, 0.45), (0.52, 0.50), (0.7, 0.4)])
def test_no_vig_sums_to_one(p, q):
    a, b = no_vig(p, q)
    assert a + b == pytest.approx(1.0)
    assert 0.0 < a < 1.0
    assert 0.0 < b < 1.0


@pytest.mark.parametrize("odds", [-200, -150, -110, 150])
def test_prob_to_american_roundtrip(odds):
    # +100 (even money) is intentionally excluded: prob_to_american maps 0.5 to
    # -100, so the sign of the even-money boundary is ambiguous by design.
    assert prob_to_american(implied_prob(odds)) == pytest.approx(odds, abs=1e-6)


@pytest.mark.parametrize("odds", [-200, -150, -110, 150, 200])
def test_decimal_american_roundtrip(odds):
    assert decimal_to_american(american_to_decimal(odds)) == odds


@pytest.mark.parametrize("odds,expected", [
    (1.5, True), (1.91, True), (2.0, True), (2.49, True),
    (1.0, False), (2.5, False), (2.6, False), (0.5, False), (3.0, False),
])
def test_is_decimal_leak_threshold(odds, expected):
    # Threshold is the open interval 1.0 < odds < 2.5.
    assert is_decimal_leak(odds) is expected


# ---------------------------------------------------------------------------
# quant.derived
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("line", [1.5, 2.5, 3.5])
def test_calc_tb_prob_complementary_and_bounded(line):
    over_p, under_p = calc_tb_prob(1.0, 0.4, 0.05, 0.3, line)
    assert over_p + under_p == pytest.approx(1.0, abs=1e-9)
    assert 0.0 <= over_p <= 1.0
    assert 0.0 <= under_p <= 1.0


def test_calc_tb_prob_monotone_in_line():
    over = [calc_tb_prob(1.0, 0.4, 0.05, 0.3, line)[0] for line in (1.5, 2.5, 3.5)]
    assert over[0] > over[1] > over[2]


def test_mlb_ml_from_nb_in_unit_interval():
    assert 0.0 < mlb_ml_from_nb(4.5, 4.0, 3.548) < 1.0


def test_mlb_ml_from_nb_symmetric_at_equal_mu():
    assert mlb_ml_from_nb(4.5, 4.5, 3.548) == pytest.approx(0.5, abs=1e-4)


def test_mlb_ml_from_nb_favorite_wins_more():
    assert mlb_ml_from_nb(6.0, 3.5, 3.548) > 0.5


def test_calc_edge_sign_behavior():
    # calc_edge returns (over_edge, under_edge, nv_over, nv_under).
    over_pos, _, nv_over, _ = calc_edge(0.70, -110, -110)
    assert over_pos > 0 and nv_over == pytest.approx(0.5)
    over_neg, *_ = calc_edge(0.30, -110, -110)
    assert over_neg < 0
    over_zero, *_ = calc_edge(0.50, -110, -110)
    assert over_zero == pytest.approx(0.0, abs=1e-9)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
