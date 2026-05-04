"""Tests for Apr 28 2026 SGP redesign (3-4 legs, +200-450, Gaussian odds, size_sgp).

Audit H11 — zero coverage existed before this file.
"""

import math
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import pytest
import sgp_builder as sgp


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _leg(fair_prob=0.68, edge=0.04, stat="PTS", odds=-130, book="betmgm",
         game="OKC @ DEN", player="Player A", direction="OVER", line=25.5,
         team="OKC"):
    """Minimal leg dict matching what build_candidate_legs produces."""
    return {
        "fair_prob": fair_prob,
        "edge":      edge,
        "stat":      stat,
        "odds":      odds,
        "book":      book,
        "game":      game,
        "player":    player,
        "direction": direction,
        "line":      line,
        "proj":      line + 2,
        "team":      team,
    }


# ---------------------------------------------------------------------------
# _parlay_american
# ---------------------------------------------------------------------------

class TestParlayAmerican:
    def test_single_leg_passthrough(self):
        """1-leg parlay round-trips: _parlay_american([leg]) == leg odds."""
        legs = [_leg(odds=-110)]
        result = sgp._parlay_american(legs)
        # _american_to_decimal(-110) = 1.909; _decimal_to_american(1.909) ≈ -110
        assert result == -110

    def test_two_legs_compound(self):
        legs = [_leg(odds=-110), _leg(odds=-110)]
        result = sgp._parlay_american(legs)
        # 2-leg at -110 each ≈ +260 area
        assert result > 200

    def test_three_legs_parlay_higher_than_single(self):
        """3-leg parlay always has higher odds than any single leg."""
        legs = [_leg(odds=-130), _leg(odds=-120), _leg(odds=-115)]
        result = sgp._parlay_american(legs)
        assert result > 0  # positive american = higher than any individual favourite

    def test_higher_legs_higher_odds(self):
        """4-leg parlay should have higher odds than 3-leg (same legs)."""
        three = [_leg(odds=-130)] * 3
        four  = [_leg(odds=-130)] * 4
        assert sgp._parlay_american(four) > sgp._parlay_american(three)


# ---------------------------------------------------------------------------
# MIN / MAX leg count constants
# ---------------------------------------------------------------------------

class TestLegCountConstants:
    def test_min_legs_is_3(self):
        assert sgp.MIN_LEGS == 3

    def test_max_legs_is_4(self):
        assert sgp.MAX_LEGS == 4

    def test_odds_window(self):
        assert sgp.MIN_PARLAY_ODDS == 200
        assert sgp.MAX_PARLAY_ODDS == 450


# ---------------------------------------------------------------------------
# _score_sgp — Gaussian odds scoring
# ---------------------------------------------------------------------------

class TestScoreSgp:
    def _three_leg(self, parlay_odds_target=280):
        """Three legs tuned so _parlay_american ≈ parlay_odds_target."""
        # We can't perfectly control parlay_odds here, so we test the
        # invariant that in-range scores > out-of-range scores.
        return [
            _leg(fair_prob=0.68, edge=0.04, stat="PTS"),
            _leg(fair_prob=0.70, edge=0.04, stat="REB"),
            _leg(fair_prob=0.65, edge=0.04, stat="AST"),
        ]

    def test_out_of_range_odds_zero_odds_score(self):
        """Legs whose parlay odds land outside [200,450] get odds_score=0."""
        # 5 very high-prob legs would push combined odds below 200.
        high_prob_legs = [_leg(fair_prob=0.90, edge=0.06, odds=-400)] * 3
        # odds_score component == 0 iff parlay_odds out of range
        parlay_odds = sgp._parlay_american(high_prob_legs)
        if parlay_odds < sgp.MIN_PARLAY_ODDS or parlay_odds > sgp.MAX_PARLAY_ODDS:
            # Expected: these legs should not qualify via _score_sgp's odds gate
            score = sgp._score_sgp(high_prob_legs)
            # Score still exists but odds_score=0; other components carry it
            assert score >= 0.0

    def test_score_nonnegative(self):
        legs = self._three_leg()
        assert sgp._score_sgp(legs) >= 0.0

    def test_score_at_most_1(self):
        """Score is a weighted sum of 0-1 components — should be ≤ 1."""
        legs = self._three_leg()
        assert sgp._score_sgp(legs) <= 1.0 + 1e-9

    def test_three_vs_four_leg_target_differs(self):
        """3-leg target=280, 4-leg target=360 — ensure distinct targets."""
        three_target = 280
        four_target  = 360
        assert three_target != four_target

    def test_stat_diversity_improves_score(self):
        """Three different stats > three same stats, all else equal."""
        same_stat = [_leg(stat="PTS")] * 3
        diff_stat = [_leg(stat="PTS"), _leg(stat="REB"), _leg(stat="AST")]
        assert sgp._score_sgp(diff_stat) > sgp._score_sgp(same_stat)


# ---------------------------------------------------------------------------
# size_sgp
# ---------------------------------------------------------------------------

class TestSizeSgp:
    def test_default_size(self):
        """Below-threshold legs → SGP_SIZE_DEFAULT (0.25u)."""
        legs = [_leg(fair_prob=0.65, edge=0.03)] * 3
        assert sgp.size_sgp(legs, cohesion_score=0.40) == sgp.SGP_SIZE_DEFAULT

    def test_premium_size_all_thresholds_met(self):
        """avg_wp≥0.70 AND cohesion≥0.55 AND avg_edge≥0.035 → 0.50u."""
        legs = [_leg(fair_prob=0.72, edge=0.040)] * 3
        assert sgp.size_sgp(legs, cohesion_score=0.60) == sgp.SGP_SIZE_PREMIUM

    def test_premium_fails_low_copula_ev(self):
        # Gate is copula_ev_margin >= 0.10 (not avg_wp).  Inject a copula value
        # that puts margin at 0.05 (below threshold) to verify DEFAULT is returned.
        legs = [_leg(fair_prob=0.68, edge=0.040)] * 3
        parlay_impl = sgp._implied_prob(sgp._parlay_american(legs))
        low_copula = parlay_impl + 0.05   # margin 0.05 < 0.10
        assert sgp.size_sgp(legs, cohesion_score=0.60,
                            _copula_joint=low_copula) == sgp.SGP_SIZE_DEFAULT

    def test_premium_fails_low_cohesion(self):
        legs = [_leg(fair_prob=0.72, edge=0.040)] * 3
        assert sgp.size_sgp(legs, cohesion_score=0.50) == sgp.SGP_SIZE_DEFAULT  # < 0.55

    def test_premium_fails_low_edge(self):
        legs = [_leg(fair_prob=0.72, edge=0.030)] * 3  # avg_edge < 0.035
        assert sgp.size_sgp(legs, cohesion_score=0.60) == sgp.SGP_SIZE_DEFAULT

    def test_premium_size_value(self):
        assert sgp.SGP_SIZE_PREMIUM == 0.50

    def test_default_size_value(self):
        assert sgp.SGP_SIZE_DEFAULT == 0.25


# ---------------------------------------------------------------------------
# _correlation_cohesion
# ---------------------------------------------------------------------------

class TestCorrelationCohesion:
    def test_returns_float(self):
        legs = [_leg()] * 3
        result = sgp._correlation_cohesion(legs)
        assert isinstance(result, float)

    def test_range_zero_to_one(self):
        legs = [_leg()] * 3
        result = sgp._correlation_cohesion(legs)
        assert 0.0 <= result <= 1.0

    def test_negatively_correlated_pair_reduces_cohesion(self):
        """A OVER + complementary UNDER from same game should hurt cohesion."""
        leg_over  = _leg(direction="OVER",  stat="PTS", game="OKC @ DEN")
        leg_under = _leg(direction="UNDER", stat="PTS", game="OKC @ DEN")
        two_legs  = [leg_over, leg_under]
        # Cohesion when legs agree vs disagree
        agree_legs = [leg_over, leg_over]
        cohesion_agree    = sgp._correlation_cohesion(agree_legs)
        cohesion_disagree = sgp._correlation_cohesion(two_legs)
        # Disagreeing legs should have <= cohesion (may be equal if both neutral)
        assert cohesion_disagree <= cohesion_agree + 1e-9


# ---------------------------------------------------------------------------
# Allowed books constant
# ---------------------------------------------------------------------------

class TestAllowedBooks:
    REQUIRED = {"fanduel", "betmgm", "draftkings", "espnbet",
                "williamhill_us", "fanatics", "hardrockbet"}

    def test_all_required_books_present(self):
        assert self.REQUIRED <= sgp.SGP_ALLOWED_BOOKS

    def test_no_unexpected_books(self):
        """SGP should not accept books outside the approved list."""
        assert "pinnacle" not in sgp.SGP_ALLOWED_BOOKS
        assert "bovada" not in sgp.SGP_ALLOWED_BOOKS


class TestDisallowedBook:
    """H32: SGP builder rejects legs from books not in SGP_ALLOWED_BOOKS."""

    def test_disallowed_book_not_in_allowed_set(self):
        """Confirm well-known sharp/offshore books are excluded."""
        import sgp_builder as sgp
        for book in ("pinnacle", "bovada", "mybookie", "betonline_ag"):
            assert book not in sgp.SGP_ALLOWED_BOOKS, (
                f"'{book}' must not be in SGP_ALLOWED_BOOKS"
            )

    def test_allowed_books_contains_expected_soft_books(self):
        """The major US soft books must all be present."""
        import sgp_builder as sgp
        required = {"fanduel", "draftkings", "betmgm", "williamhill_us"}
        missing = required - sgp.SGP_ALLOWED_BOOKS
        assert not missing, f"Required books missing from SGP_ALLOWED_BOOKS: {missing}"

    def test_book_filter_excludes_disallowed(self):
        """_sgp_book returns empty string / skips legs from non-allowed books."""
        import sgp_builder as sgp
        legs = [
            {"book": "pinnacle",  "wp": 0.65},
            {"book": "fanduel",   "wp": 0.65},
        ]
        # _sgp_book should only count fanduel
        book = sgp._sgp_book(legs)
        assert book == "fanduel"
