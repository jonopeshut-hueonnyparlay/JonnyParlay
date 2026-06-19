#!/usr/bin/env python3
"""NB_R consumer regression tests (Phase 3).

`calibrated.NB_R` is the within-player negative-binomial dispersion table. Its
*values* are pinned by tests/test_calibrated.py::test_nb_r_locked_values, and the
sgp_builder single-source contract is guarded by _assert_nb_r_single_source().

What was NOT pinned: the behavior of the main *consumer*, prob_core.calc_prop_prob,
which prices every NB-stat prop. These goldens lock the end-to-end consumer output
(NB_R value x negbinom math x push-adjustment x stat routing) so that any change to
the table, the distribution code, or the wiring produces a reviewed diff instead of
a silent reprice. Captured from current code 2026-06-18.

WNBA NB routing (NB_R_WNBA) is covered separately in test_wnba_distribution_routing.py.
"""

from __future__ import annotations

import pytest

# engine/ is on sys.path via the repo-root conftest.py.
from prob_core import calc_prop_prob
import prob_core
from calibrated import NB_R
from quant.distributions import negbinom_cdf


# Golden (over_p, under_p) for the calibrated.NB_R consumer path. Each row is a
# representative (proj, line, sport). Half-integer lines exercise the no-push
# branch; integer lines exercise the push-adjusted branch.
_GOLDENS = [
    # stat, proj, line, sport,  over_p,               under_p
    ("3PM", 2.5, 1.5, "NBA", 0.6749661773397764, 0.32503382266022357),  # shared, half-int
    ("3PM", 2.5, 2.0, "NBA", 0.5753777578063553, 0.4246222421936447),   # shared, integer (push)
    ("AST", 6.5, 6.5, "NBA", 0.4521973948775777, 0.5478026051224223),   # shared, half-int
    ("AST", 6.5, 7.0, "NBA", 0.3832422575647416, 0.6167577424352584),   # shared, integer (push)
    ("REB", 8.0, 8.5, "NBA", 0.404816915573598,  0.595183084426402),    # shared, half-int
    ("ER",  3.0, 2.5, "MLB", 0.5224954496297447, 0.4775045503702553),   # MLB starts-only
    ("RBI", 1.0, 0.5, "MLB", 0.48609889431729103, 0.513901105682709),   # MLB r<1
]


@pytest.mark.parametrize("stat,proj,line,sport,exp_over,exp_under", _GOLDENS)
def test_nb_r_consumer_golden(stat, proj, line, sport, exp_over, exp_under):
    """calc_prop_prob NB path reproduces the frozen golden output."""
    over_p, under_p = calc_prop_prob(proj, line, stat, sport=sport)
    assert over_p == pytest.approx(exp_over, abs=1e-9)
    assert under_p == pytest.approx(exp_under, abs=1e-9)
    assert over_p + under_p == pytest.approx(1.0, abs=1e-9)


def test_nb_r_consumer_golden_ties_to_constant_and_math():
    """The AST half-integer golden equals negbinom_cdf evaluated with NB_R['AST'].

    This makes the golden self-documenting: it is exactly what the table value
    (NB_R['AST']) and the canonical distribution code produce — not a magic number.
    """
    proj, line = 6.5, 6.5
    k = 6  # floor(6.5); half-integer -> no push
    expected_over = 1.0 - negbinom_cdf(k, proj, NB_R["AST"])
    over_p, _ = calc_prop_prob(proj, line, "AST", sport="NBA")
    assert over_p == pytest.approx(expected_over, abs=1e-12)


def test_calc_prop_prob_consumes_nb_r_table(monkeypatch):
    """The consumer reads r from NB_R[stat] — it is not hardcoded.

    Patch the dispersion for REB to a much smaller r (heavier overdispersion ->
    fatter tails) and assert the priced over-probability both (a) changes from the
    unpatched value and (b) matches negbinom_cdf recomputed with the patched r.
    Guards against a regression that bypasses the table with a constant.
    """
    proj, line = 8.0, 8.5
    k = 8  # floor(8.5); half-integer -> over_p = 1 - cdf(k, proj, r)

    baseline_over, _ = calc_prop_prob(proj, line, "REB", sport="NBA")

    patched_r = 5.0  # vs NB_R["REB"] = 13.16
    assert patched_r != NB_R["REB"]
    monkeypatch.setattr(prob_core, "NB_R", {**prob_core.NB_R, "REB": patched_r})

    patched_over, patched_under = calc_prop_prob(proj, line, "REB", sport="NBA")
    expected_over = 1.0 - negbinom_cdf(k, proj, patched_r)

    assert patched_over == pytest.approx(expected_over, abs=1e-12)
    assert patched_over != pytest.approx(baseline_over, abs=1e-6)  # r actually moved the price
    assert patched_over + patched_under == pytest.approx(1.0, abs=1e-9)
