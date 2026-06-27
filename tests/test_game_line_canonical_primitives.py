"""Characterization safety net for the game-line pricer collapse (Stage 1, Commit 1).

`analyze_game_lines.py` historically kept LOCAL copies of the distribution
primitives that the canonical `engine/quant` package already provides (the same
math is also used by `engine/evaluators.py`). Step one of collapsing the three
divergent game-line pricers is to delete those local copies and import the
canonical functions instead.

These tests pin that the local and canonical implementations are NUMERICALLY
IDENTICAL across every regime the MLB/NBA game-line markets exercise, so the
dedup is provably byte-identical (not merely close). After the swap the
`analyze_game_lines` names ARE the canonical functions, so the equality still
holds — the file then doubles as a guard against anyone re-introducing a local
fork of the math.

Pure-function tests — no network, no Discord, no filesystem.

Run:
    python -m pytest tests/test_game_line_canonical_primitives.py -v
"""
import analyze_game_lines as agl  # adds engine/ to sys.path on import (also via conftest)

from quant.distributions import (
    normal_cdf as q_normal_cdf,
    negbinom_pmf as q_negbinom_pmf,
    negbinom_cdf as q_negbinom_cdf,
)
from quant.derived import mlb_ml_from_nb as q_mlb_ml_from_nb

# Grids span every sigma/mu/line regime used by the live MLB + NBA game-line
# markets (F5 sigmas 2.10/2.65/2.70, MLB 3.0/4.2/4.6, NBA 11.0/12.5/18.5), the
# sigma<=0 degenerate guard, and team-run NB dispersions (TB r=1.3, team r=3.548,
# WNBA-ast r=11.37) at run-total support k=0..12.
_NORMAL_CASES = [
    (x, mu, sigma)
    for x in (-5.5, -1.5, 0.0, 4.5, 8.5, 107.5, 230.5)
    for mu in (-2.0, 0.0, 3.7, 4.4, 9.3, 107.0, 225.0)
    for sigma in (0.0, 2.10, 2.65, 2.70, 3.0, 4.2, 4.6, 11.0, 12.5, 18.5)
]
_NB_CASES = [
    (k, mu, r)
    for k in range(0, 13)
    for mu in (0.0, 0.5, 3.7, 4.4, 5.3, 6.4)
    for r in (1.3, 3.548, 11.37)
]
_ML_CASES = [
    (mu_home, mu_away)
    for mu_home in (0.0, 3.7, 4.4, 4.9, 6.4)
    for mu_away in (0.0, 3.9, 4.5, 5.3)
]


def test_normal_cdf_identical_to_canonical():
    for x, mu, sigma in _NORMAL_CASES:
        assert agl.normal_cdf(x, mu, sigma) == q_normal_cdf(x, mu, sigma), (x, mu, sigma)


def test_negbinom_pmf_cdf_identical_to_canonical():
    for k, mu, r in _NB_CASES:
        assert agl.negbinom_pmf(k, mu, r) == q_negbinom_pmf(k, mu, r), ("pmf", k, mu, r)
        assert agl.negbinom_cdf(k, mu, r) == q_negbinom_cdf(k, mu, r), ("cdf", k, mu, r)


def test_mlb_ml_from_nb_identical_to_canonical():
    r = agl.MLB_TEAM_RUN_R
    for mu_home, mu_away in _ML_CASES:
        assert agl.mlb_ml_from_nb(mu_home, mu_away, r) == q_mlb_ml_from_nb(mu_home, mu_away, r), (mu_home, mu_away)
