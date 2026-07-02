"""Unit tests for the canonical game-line pricing engine (engine/game_line_pricing.py).

Pins team_total_mlb_nb against the exact push-adjusted NB formula it consolidated
(previously duplicated in analyze_game_lines.mlb_tt_prob and inline in
evaluators.evaluate_game_lines), and checks basic invariants.
"""
import math

from game_line_pricing import (
    team_total_mlb_nb,
    blend,
    prob_total_over,
    prob_spread_cover,
    prob_ml_normal,
    prob_ml_mlb_nb,
    prob_team_total_normal,
)
from quant.distributions import normal_cdf, negbinom_pmf, negbinom_cdf
from quant.derived import mlb_ml_from_nb

_R = 3.50  # mirrors calibrated.MLB_TEAM_RUN_R (synced 2026-07-02); tests are relational, any r>0 valid
_ALPHA = 0.25  # evaluators BLEND_ALPHA


def test_blend_trust_one_is_exact_raw_projection():
    # trust==1.0 must return the projection bit-for-bit (anchor must not perturb it).
    for proj in (4.4, 8.5, -1.5, 107.3, 0.0):
        for anchor in (0.0, 8.0, -2.5, 110.0):
            assert blend(proj, anchor, 1.0) == proj


def test_blend_trust_quarter_matches_evaluators_formula():
    for proj in (4.4, 9.3, -1.5):
        for anchor in (8.0, -2.5, 110.0):
            assert blend(proj, anchor, _ALPHA) == anchor + _ALPHA * (proj - anchor)


def test_prob_total_over_trust_one_byte_identical_to_raw():
    # trust=1.0 == the raw analyze_game_lines formula: 1 - normal_cdf(line, proj, sigma)
    for proj, line, sigma in [(9.0, 8.5, 4.6), (224.0, 218.5, 18.5), (4.6, 4.5, 2.65)]:
        assert prob_total_over(proj, line, sigma, trust=1.0) == 1.0 - normal_cdf(line, proj, sigma)


def test_prob_total_over_trust_quarter_byte_identical_to_evaluators():
    for proj, line, sigma in [(9.0, 8.5, 4.6), (224.0, 218.5, 18.5)]:
        blended = line + _ALPHA * (proj - line)
        assert prob_total_over(proj, line, sigma, trust=_ALPHA) == 1.0 - normal_cdf(line, blended, sigma)


def test_prob_spread_cover_trust_one_byte_identical_to_raw():
    # raw analyze: cover_home = 1 - normal_cdf(-sp_line, raw_margin, sigma)
    raw_margin, market_margin, sp_line, sigma = -0.2, 1.5, -1.5, 4.2
    assert prob_spread_cover(raw_margin, market_margin, sp_line, sigma, is_home=True, trust=1.0) == \
        1.0 - normal_cdf(-sp_line, raw_margin, sigma)


def test_prob_ml_mlb_nb_trust_one_is_raw_winprob():
    mu_home, mu_away, nv = 4.4, 4.6, 0.52
    raw = mlb_ml_from_nb(mu_home, mu_away, _R)
    assert prob_ml_mlb_nb(mu_home, mu_away, _R, nv, is_home=True, trust=1.0) == raw


def test_prob_ml_mlb_nb_trust_quarter_anchors_to_novig():
    mu_home, mu_away, nv = 4.4, 4.6, 0.52
    raw = mlb_ml_from_nb(mu_home, mu_away, _R)
    assert prob_ml_mlb_nb(mu_home, mu_away, _R, nv, is_home=True, trust=_ALPHA) == nv + _ALPHA * (raw - nv)


def test_prob_ml_normal_and_team_total_normal_trust_one():
    assert prob_ml_normal(4.0, -3.5, 12.5, is_home=True, trust=1.0) == 1.0 - normal_cdf(0.0, 4.0, 12.5)
    assert prob_team_total_normal(110.0, 105.5, 11.0, trust=1.0) == 1.0 - normal_cdf(105.5, 110.0, 11.0)


def _ref(mu, line, direction):
    """Reference = the formula that previously lived in analyze_game_lines.mlb_tt_prob."""
    k = int(math.floor(line))
    if line == k:  # integer line — push-adjusted
        push = negbinom_pmf(k, mu, _R)
        non = 1.0 - push
        if non <= 0:
            return 0.5
        return (1.0 - negbinom_cdf(k, mu, _R)) / non if direction == "over" else negbinom_cdf(k - 1, mu, _R) / non
    return (1.0 - negbinom_cdf(k, mu, _R)) if direction == "over" else negbinom_cdf(k, mu, _R)


def test_team_total_mlb_nb_matches_reference():
    for mu in (0.5, 3.0, 4.0, 4.4, 5.3, 6.4):
        for line in (2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 5.5, 6.0):
            over_p, under_p = team_total_mlb_nb(mu, line, _R)
            assert over_p == _ref(mu, line, "over"), (mu, line, "over")
            assert under_p == _ref(mu, line, "under"), (mu, line, "under")


def test_team_total_mlb_nb_half_line_is_complement():
    # On a half-line there is no push: over + under == 1 exactly.
    over_p, under_p = team_total_mlb_nb(4.4, 4.5, _R)
    assert over_p + under_p == 1.0


def test_team_total_mlb_nb_degenerate_all_push_returns_half():
    # mu<=0 with an integer line at 0 -> all mass on the push -> (0.5, 0.5).
    assert team_total_mlb_nb(0.0, 0.0, _R) == (0.5, 0.5)


def test_team_total_mlb_nb_probabilities_bounded():
    for mu in (0.5, 4.4, 6.4):
        for line in (3.0, 3.5, 4.0, 4.5):
            over_p, under_p = team_total_mlb_nb(mu, line, _R)
            assert 0.0 <= over_p <= 1.0 and 0.0 <= under_p <= 1.0, (mu, line)
