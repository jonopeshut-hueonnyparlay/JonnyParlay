"""Canonical game-line pricing engine.

ONE home for the per-market probability math shared by the live game-line
analyzer (analyze_game_lines.py) and the prop-correlation path
(engine/evaluators.py). Built incrementally during the Stage 1 pricer collapse.

Leaf distribution math comes from quant.* (already canonical). This module owns
the COMPOSED game-line pricing. First in: the push-adjusted MLB team-total NB,
which was previously duplicated verbatim across both callers.

Pure functions — no I/O. Market anchoring (the BLEND_ALPHA blend toward the
market) is NOT applied here yet; callers still compute the projection they want
priced. Anchoring becomes a mandatory parameter when the Normal-market pricing
moves here in Stage 1 Commit 2 (the behavioral, approval-gated change).
"""
import math

from quant.distributions import negbinom_pmf, negbinom_cdf


def team_total_mlb_nb(mu, line, r):
    """P(over), P(under) for an MLB team total via Negative Binomial.

    Push-adjusted on integer lines (the probability mass on exactly ``line`` is
    removed from both sides); a half-line is a plain split. Byte-identical to the
    formula previously duplicated in ``analyze_game_lines.mlb_tt_prob`` and inline
    in ``evaluators.evaluate_game_lines``.

    ``r`` is the NB dispersion — pass the per-team value where one exists, with the
    global league ``r`` only as a fallback (see feedback: prefer per-entity params).
    Returns ``(over_p, under_p)``; both 0.5 on a degenerate all-push line.
    """
    k_floor = int(math.floor(line))
    if line == k_floor:  # integer line — push-adjusted
        push = negbinom_pmf(k_floor, mu, r)
        non_push = 1.0 - push
        if non_push <= 0:
            return 0.5, 0.5
        over_p = (1.0 - negbinom_cdf(k_floor, mu, r)) / non_push
        under_p = negbinom_cdf(k_floor - 1, mu, r) / non_push
    else:  # half-line
        over_p = 1.0 - negbinom_cdf(k_floor, mu, r)
        under_p = negbinom_cdf(k_floor, mu, r)
    return over_p, under_p
