"""Tests: WNBA AST and REB route to Normal (SIGMA_WNBA), not Negative Binomial.

NBA NB parameters (AST r=12.16, REB r=14.7) are over-dispersed for WNBA
(WNBA AST var/mu≈1.00, REB var/mu≈1.21). The fix routes WNBA AST and REB to
Normal via SIGMA_WNBA, matching the existing WNBA 3PM treatment.
"""

import pytest
from run_picks import calc_prop_prob, normal_cdf, negbinom_cdf, check_prop_gates


# ---------------------------------------------------------------------------
# Distribution routing: calc_prop_prob
# ---------------------------------------------------------------------------

def test_wnba_ast_routes_to_normal():
    proj, line = 5.0, 4.5
    sigma = max(proj * 0.55, 1.1)  # SIGMA_WNBA["AST"]
    expected_over = 1.0 - normal_cdf(line, proj, sigma)
    nb_over = 1.0 - negbinom_cdf(int(line), proj, 12.16)  # NB_R["AST"]

    over_p, _ = calc_prop_prob(proj, line, "AST", sport="WNBA")

    assert abs(over_p - expected_over) < 1e-9, f"WNBA AST should use Normal; got {over_p}, expected {expected_over}"
    assert abs(over_p - nb_over) > 0.001, "WNBA AST result should differ from NBA NB result"


def test_wnba_reb_routes_to_normal():
    proj, line = 6.0, 5.5
    sigma = max(proj * 0.45, 2.0)  # SIGMA_WNBA["REB"]
    expected_over = 1.0 - normal_cdf(line, proj, sigma)
    nb_over = 1.0 - negbinom_cdf(int(line), proj, 14.7)  # NB_R["REB"]

    over_p, _ = calc_prop_prob(proj, line, "REB", sport="WNBA")

    assert abs(over_p - expected_over) < 1e-9, f"WNBA REB should use Normal; got {over_p}, expected {expected_over}"
    assert abs(over_p - nb_over) > 0.001, "WNBA REB result should differ from NBA NB result"


def test_wnba_3pm_routes_to_normal_regression():
    """Regression: WNBA 3PM was already using Normal before this fix."""
    proj, line = 2.0, 1.5
    sigma = max(proj * 0.48, 0.70)  # SIGMA_WNBA["3PM"]
    expected_over = 1.0 - normal_cdf(line, proj, sigma)

    over_p, _ = calc_prop_prob(proj, line, "3PM", sport="WNBA")

    assert abs(over_p - expected_over) < 1e-9


def test_nba_ast_still_uses_nb():
    """NBA AST must remain on NB path — no regression."""
    proj, line = 5.0, 4.5
    k = int(line)
    nb_over = 1.0 - negbinom_cdf(k, proj, 12.16)
    normal_sigma = max(proj * 0.55, 1.1)
    normal_over = 1.0 - normal_cdf(line, proj, normal_sigma)

    over_p, _ = calc_prop_prob(proj, line, "AST", sport="NBA")

    assert abs(over_p - nb_over) < 1e-9, f"NBA AST should use NB; got {over_p}, expected {nb_over}"
    assert abs(over_p - normal_over) > 0.001, "NBA AST result should differ from Normal result"


def test_nba_reb_still_uses_nb():
    """NBA REB must remain on NB path — no regression."""
    proj, line = 6.0, 5.5
    k = int(line)
    nb_over = 1.0 - negbinom_cdf(k, proj, 14.7)
    normal_sigma = max(proj * 0.45, 2.0)
    normal_over = 1.0 - normal_cdf(line, proj, normal_sigma)

    over_p, _ = calc_prop_prob(proj, line, "REB", sport="NBA")

    assert abs(over_p - nb_over) < 1e-9, f"NBA REB should use NB; got {over_p}, expected {nb_over}"
    assert abs(over_p - normal_over) > 0.001, "NBA REB result should differ from Normal result"


# ---------------------------------------------------------------------------
# G14 gate: borderline WNBA AST and REB picks are blocked
# ---------------------------------------------------------------------------

def _wnba_pick(stat, proj, line, direction="under"):
    return {
        "stat": stat,
        "direction": direction,
        "line": line,
        "proj": proj,
        "sport": "WNBA",
        "win_prob": 0.60,
        "adj_edge": 0.08,
        "odds": -115,
    }


def test_wnba_ast_g14_blocks_borderline():
    pick = _wnba_pick("AST", proj=3.0, line=3.0, direction="under")
    # z = (3.0 - 3.0) / max(3.0*0.55, 1.1) = 0 < 0.10 → G14
    passed, gate = check_prop_gates(pick)
    assert not passed
    assert gate == "G14"


def test_wnba_reb_g14_blocks_borderline():
    pick = _wnba_pick("REB", proj=4.0, line=4.0, direction="under")
    # z = (4.0 - 4.0) / max(4.0*0.45, 2.0) = 0 < 0.10 → G14
    passed, gate = check_prop_gates(pick)
    assert not passed
    assert gate == "G14"
