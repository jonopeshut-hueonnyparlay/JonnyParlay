"""Tests: WNBA AST and REB distribution routing and sigma values.

WNBA AST (var/mu=1.205, NB_R_WNBA r=11.37) and REB (var/mu=1.404, r=10.74)
use NB for probability. SIGMA_WNBA (PTS mult=0.48/min=3.5, AST mult=0.65/min=1.0,
REB mult=0.54/min=1.0) is used for G14 z-score gate and combo sigma.
Recalibrated 2026-06-05 (Plan 6 §1C) on the priced population (min>=20, 153 players).
"""

import pytest
from run_picks import calc_prop_prob, normal_cdf, negbinom_cdf, check_prop_gates, _combo_mu_sigma, NB_R


# ---------------------------------------------------------------------------
# Distribution routing: calc_prop_prob
# ---------------------------------------------------------------------------

def test_wnba_ast_routes_to_nb():
    """WNBA AST uses NB with WNBA-specific r=11.37, not NBA r=9.66 and not Normal."""
    proj, line = 5.0, 4.5
    expected_over = 1.0 - negbinom_cdf(int(line), proj, 11.37)  # NB_R_WNBA["AST"]
    normal_sigma = max(proj * 0.65, 1.0)
    normal_over = 1.0 - normal_cdf(line, proj, normal_sigma)

    over_p, _ = calc_prop_prob(proj, line, "AST", sport="WNBA")

    assert abs(over_p - expected_over) < 1e-9, f"WNBA AST should use NB r=11.37; got {over_p}"
    assert abs(over_p - normal_over) > 0.001, "WNBA AST should differ from Normal"


def test_wnba_reb_routes_to_nb():
    """WNBA REB uses NB with WNBA-specific r=10.74, not NBA r=13.16 and not Normal."""
    proj, line = 6.0, 5.5
    expected_over = 1.0 - negbinom_cdf(int(line), proj, 10.74)  # NB_R_WNBA["REB"]
    normal_sigma = max(proj * 0.54, 1.0)
    normal_over = 1.0 - normal_cdf(line, proj, normal_sigma)

    over_p, _ = calc_prop_prob(proj, line, "REB", sport="WNBA")

    assert abs(over_p - expected_over) < 1e-9, f"WNBA REB should use NB r=10.74; got {over_p}"
    assert abs(over_p - normal_over) > 0.001, "WNBA REB should differ from Normal"


def test_wnba_3pm_routes_to_nb():
    """WNBA 3PM routes to NB path after carve-out removal.

    Uses the live NB_R_WNBA constant (r recalibrated periodically — refit to ~5.0 on
    2026-06-26 from the within-player var/mu=1.16; the prior 1.342 was a pooled fit
    that over-dispersed) so this routing test doesn't break on recalibration; the
    sanity bound below pins it to mild overdispersion, still distinct from NBA's r=9.15.
    """
    from run_picks import NB_R_WNBA
    proj, line = 2.0, 1.5
    r = NB_R_WNBA["3PM"]
    assert 3.0 < r < 9.0  # WNBA 3PM mild overdispersion (within-player), still < NBA r=9.15
    k = int(line)
    expected_over = 1.0 - negbinom_cdf(k, proj, r)

    over_p, _ = calc_prop_prob(proj, line, "3PM", sport="WNBA")

    assert abs(over_p - expected_over) < 1e-9


def test_nba_ast_still_uses_nb():
    """NBA AST must remain on NB path — no regression."""
    proj, line = 5.0, 4.5
    k = int(line)
    nb_over = 1.0 - negbinom_cdf(k, proj, NB_R["AST"])  # live constant (P1.3: 9.66)
    normal_sigma = max(proj * 0.55, 1.1)
    normal_over = 1.0 - normal_cdf(line, proj, normal_sigma)

    over_p, _ = calc_prop_prob(proj, line, "AST", sport="NBA")

    assert abs(over_p - nb_over) < 1e-9, f"NBA AST should use NB; got {over_p}, expected {nb_over}"
    assert abs(over_p - normal_over) > 0.001, "NBA AST result should differ from Normal result"


def test_nba_reb_still_uses_nb():
    """NBA REB must remain on NB path — no regression."""
    proj, line = 6.0, 5.5
    k = int(line)
    nb_over = 1.0 - negbinom_cdf(k, proj, NB_R["REB"])  # live constant (P1.3: 13.16)
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
    # z = (3.0 - 3.0) / max(3.0*0.65, 1.0) = 0 < 0.10 → G14
    passed, gate = check_prop_gates(pick)
    assert not passed
    assert gate == "G14"


def test_wnba_reb_g14_blocks_borderline():
    pick = _wnba_pick("REB", proj=4.0, line=4.0, direction="under")
    # z = (4.0 - 4.0) / max(4.0*0.54, 1.0) = 0 < 0.10 → G14
    passed, gate = check_prop_gates(pick)
    assert not passed
    assert gate == "G14"


# ---------------------------------------------------------------------------
# COMBO_RHO_WNBA: _combo_mu_sigma uses 2026-06-04 calibrated rho values
# ---------------------------------------------------------------------------

def test_wnba_pra_combo_mu_sigma():
    """WNBA PRA mu=sum(components), sigma computed with new rho (0.294/0.188/0.200)."""
    proj = {"PTS": 15.0, "REB": 7.0, "AST": 4.0}
    mu, sigma = _combo_mu_sigma(proj, "PRA", sport="WNBA")

    assert mu == pytest.approx(26.0)

    sig_pts = max(15.0 * 0.48, 3.5)   # 7.20
    sig_reb = max(7.0  * 0.54, 1.0)   # 3.78
    sig_ast = max(4.0  * 0.65, 1.0)   # 2.60
    var = sig_pts**2 + sig_reb**2 + sig_ast**2
    var += 2 * 0.294 * sig_pts * sig_reb
    var += 2 * 0.188 * sig_pts * sig_ast
    var += 2 * 0.200 * sig_reb * sig_ast
    assert sigma == pytest.approx(max(var**0.5, 2.0), rel=1e-6)

    # New rho is larger on all pairs — sigma must be wider than provisional values
    var_old = sig_pts**2 + sig_reb**2 + sig_ast**2
    var_old += 2 * 0.13 * sig_pts * sig_reb
    var_old += 2 * 0.04 * sig_pts * sig_ast
    var_old += 2 * 0.05 * sig_reb * sig_ast
    assert sigma > max(var_old**0.5, 2.0), "New rho should widen WNBA PRA sigma vs old rho"


def test_wnba_pr_combo_mu_sigma():
    """WNBA PR uses PTS-REB rho=0.294."""
    proj = {"PTS": 20.0, "REB": 8.0}
    mu, sigma = _combo_mu_sigma(proj, "PR", sport="WNBA")

    assert mu == pytest.approx(28.0)

    sig_pts = max(20.0 * 0.48, 3.5)   # 9.60
    sig_reb = max(8.0  * 0.54, 1.0)   # 4.32
    var = sig_pts**2 + sig_reb**2 + 2 * 0.294 * sig_pts * sig_reb
    assert sigma == pytest.approx(max(var**0.5, 2.0), rel=1e-6)


def test_wnba_combo_sigma_differs_from_nba():
    """WNBA and NBA combo sigma differ — separate rho tables are applied."""
    proj = {"PTS": 15.0, "REB": 7.0, "AST": 4.0}
    _, sigma_wnba = _combo_mu_sigma(proj, "PRA", sport="WNBA")
    _, sigma_nba  = _combo_mu_sigma(proj, "PRA", sport="NBA")
    assert abs(sigma_wnba - sigma_nba) > 0.05, "WNBA and NBA PRA sigma should differ"
