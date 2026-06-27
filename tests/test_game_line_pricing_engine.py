"""Unit tests for the canonical game-line pricing engine (engine/game_line_pricing.py).

Pins team_total_mlb_nb against the exact push-adjusted NB formula it consolidated
(previously duplicated in analyze_game_lines.mlb_tt_prob and inline in
evaluators.evaluate_game_lines), and checks basic invariants.
"""
import math

from game_line_pricing import team_total_mlb_nb
from quant.distributions import negbinom_pmf, negbinom_cdf

_R = 3.548


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
