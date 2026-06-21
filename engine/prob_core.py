"""Probability and pick-scoring core for player props and combos.

Extracted from run_picks.py (extract-and-re-export refactor, Step 5) and
re-imported there so existing call sites and `from run_picks import ...` keep
resolving. Imports only {stdlib, thresholds, calibrated, quant.distributions,
wnba_gate} — never run_picks or the other extracted modules.
"""
import logging
import math

from thresholds import POISSON_CUTOFF, PLATT_SPACE
from calibrated import (
    PLATT_A, PLATT_B,
    POISSON_STATS, NB_STATS, NB_R, NB_R_WNBA,
    SIGMA, SIGMA_WNBA,
    COMBO_COMPONENTS, COMBO_RHO, COMBO_RHO_WNBA,
    PICK_SCORE_MODES, COLD_START_SCORE_PENALTY,
    INJURY_TRIGGER_BONUS, INJURY_TRIGGER_BONUS_DEFAULT,
)
from quant.distributions import (
    poisson_pmf, poisson_cdf, normal_cdf, negbinom_pmf, negbinom_cdf,
)
from wnba_gate import _wnba_early_season_factor

logger = logging.getLogger("jonnyparlay")


def _platt_calibrate_prop(over_p: float) -> float:
    """Apply Platt scaling to raw over_p. Formula: sigmoid(PLATT_A * over_p + PLATT_B).

    RAW-PROBABILITY SPACE. PLATT_A/B were fitted for this formula.
    When migrating to logit-space at H3, change this line to:
        raw = PLATT_A * math.log(over_p / (1.0 - over_p)) + PLATT_B
    AND paste the new logit-space A/B simultaneously. Doing one without the other is wrong.
    """
    assert PLATT_SPACE == "raw", (
        "PLATT_SPACE='logit' set but formula still uses raw-space. "
        "Update the formula to logit-space before deploying logit A/B."
    )
    raw = PLATT_A * over_p + PLATT_B
    raw = max(-30.0, min(30.0, raw))   # numerical stability
    return 1.0 / (1.0 + math.exp(-raw))


def calc_prop_prob(proj, line, stat, sigma_override: float = 0.0, sport: str = ""):
    """Calculate over/under probability for a player prop.
    FIX M1: For integer lines, properly handle push probability.
    Push at exactly the line is excluded (DK rules: push = refund),
    so redistribute: over_p and under_p should sum to ~1.0 after
    removing push mass.

    P16: NB_STATS use negative binomial CDF instead of Normal.
    NB_R[stat] is the within-player conditional dispersion parameter r,
    calibrated from per-player avg(var/mu) over the 2024-25 DB sample.
    Exception: WNBA 3PM (var/mu=1.21 borderline) routes to Normal via SIGMA_WNBA.
    WNBA AST/REB are genuinely overdispersed (var/mu=1.21/1.40) — NB via NB_R_WNBA.

    H3: sigma_override — when > 0, replaces the default SIGMA[stat] formula for
    Normal-distribution stats (PTS etc.). Used to pass dk_std from the custom
    projection engine, which includes a role floor and an observed high-var floor.
    """
    # POISSON_CUTOFF hardening (NFL go-live): a true count stat is Poisson at EVERY
    # line. The old `line <= POISSON_CUTOFF or stat == "SOG"` guard let over-cutoff
    # POISSON_STATS (e.g. NFL receptions/receiving lines >8.5) silently fall through to
    # the Normal/SIGMA-fallback path and mis-price ~5-8pp. Route all POISSON_STATS to
    # Poisson; behaviour-unchanged for existing sports (no current pick has a
    # POISSON_STAT line >8.5 — replay byte-identical).
    if stat in POISSON_STATS:
        k = math.floor(line)
        if line == k:  # Integer line — push-adjusted
            push = poisson_pmf(k, proj)
            strict_over = 1.0 - poisson_cdf(k, proj)
            strict_under = poisson_cdf(k - 1, proj)
            non_push = 1.0 - push
            if non_push > 0:
                over_p = strict_over / non_push
                under_p = strict_under / non_push
            else:
                over_p = 0.5
                under_p = 0.5
        else:  # Half-integer line — no push possible
            under_p = poisson_cdf(k, proj)
            over_p = 1.0 - poisson_cdf(k, proj)
    elif stat in NB_STATS:
        # P16 — Negative binomial path for overdispersed count stats.
        # WNBA AST/REB/3PM use NB_R_WNBA (sport-specific r); all other sports use NB_R.
        r = NB_R_WNBA.get(stat, NB_R[stat]) if sport == "WNBA" else NB_R[stat]
        k = math.floor(line)
        if line == k:  # Integer line — push-adjusted
            push = negbinom_pmf(k, proj, r)
            strict_over = 1.0 - negbinom_cdf(k, proj, r)
            strict_under = negbinom_cdf(k - 1, proj, r)
            non_push = 1.0 - push
            if non_push > 0:
                over_p = strict_over / non_push
                under_p = strict_under / non_push
            else:
                over_p = 0.5
                under_p = 0.5
        else:  # Half-integer line — no push possible
            under_p = negbinom_cdf(k, proj, r)
            over_p = 1.0 - negbinom_cdf(k, proj, r)
        if sport == "WNBA":
            # Plan 6 §14 (9b): WNBA early-season dampener. NB has no sigma to
            # inflate, so shrink the probability toward 1/2 by the same factor —
            # the NB-path equivalent of the Normal-path sigma inflation below.
            # DATA_GATED: recalibrate factors at WNBA go-live (100 graded picks).
            _f = _wnba_early_season_factor()
            if _f < 1.0:
                over_p = 0.5 + (over_p - 0.5) * _f
                under_p = 0.5 + (under_p - 0.5) * _f
    else:
        if sigma_override > 0.0:
            # H3: use empirical σ from projection engine (dk_std), which incorporates
            # a role-specific floor and the observed high-variance floor for bimodal players.
            # More accurate than the flat 0.35×proj formula for non-starters and high-CV players.
            sigma = sigma_override
        else:
            # WNBA uses sport-specific sigma calibrated from 2024 season game logs.
            s = (SIGMA_WNBA.get(stat) if sport == "WNBA" else None) or SIGMA.get(stat)
            if s is None:  # L11: warn on unknown stat so calibration gaps surface early
                logger.warning("calc_prop_prob: no SIGMA entry for stat=%r sport=%r — using default fallback (mult=0.40, min=2.0)", stat, sport)
                s = {"mult": 0.40, "min": 2.0}
            sigma = max(proj * s["mult"], s["min"])
        if sport == "WNBA":
            # Plan 6 §14 (9b): early-season sigma inflation (sigma /= 0.80 or 0.90)
            # replaces the old edge-multiplication dampener — win_prob, edge, score
            # and Kelly size now all shrink through this one mechanism.
            sigma /= _wnba_early_season_factor()
        if stat == "PTS":
            # Truncated Normal at [0, ∞): points scored can't be negative.
            # P(X > line | X ≥ 0) = [1-Φ((line-μ)/σ)] / Φ(μ/σ)
            # Correction increases over_p slightly (typically +0.5-4pp at μ=10-25, σ≈5).
            phi_zero = normal_cdf(0, proj, sigma)          # Φ(-proj/σ) = mass below 0
            phi_above_zero = max(1.0 - phi_zero, 1e-9)    # Φ(proj/σ) = mass above 0
            over_p  = (1.0 - normal_cdf(line, proj, sigma)) / phi_above_zero
            under_p = (normal_cdf(line, proj, sigma) - phi_zero) / phi_above_zero
        else:
            under_p = normal_cdf(line, proj, sigma)
            over_p = 1.0 - normal_cdf(line, proj, sigma)
    return over_p, under_p


def _combo_mu_sigma(proj_player: dict, stat: str, sport: str = "") -> tuple:
    """Returns (mu, sigma) for a combo stat using correlated Normal sum.

    Var(X+Y) = Var(X) + Var(Y) + 2·ρ·σ(X)·σ(Y).
    Individual σ from SIGMA dict (SIGMA_WNBA for WNBA); pairwise ρ from COMBO_RHO
    (COMBO_RHO_WNBA for WNBA — all pairs ~0.04–0.05 below NBA equivalents).
    """
    components = COMBO_COMPONENTS[stat]
    rho_table = COMBO_RHO_WNBA if sport == "WNBA" else COMBO_RHO
    mus, sigmas = [], []
    for c in components:
        mu = float(proj_player.get(c, 0) or 0)
        s = (SIGMA_WNBA.get(c) if sport == "WNBA" else None) or SIGMA.get(c, {"mult": 0.40, "min": 2.0})
        mus.append(mu)
        sigmas.append(max(mu * s["mult"], s["min"]))
    mu_combo = sum(mus)
    var = sum(s * s for s in sigmas)
    for i in range(len(components)):
        for j in range(i + 1, len(components)):
            pair = (components[i], components[j])
            rho = rho_table.get(pair, rho_table.get((pair[1], pair[0]), 0.10 if sport == "WNBA" else 0.20))
            var += 2.0 * rho * sigmas[i] * sigmas[j]
    sigma_combo = max(var ** 0.5, 2.0)
    if sport == "WNBA":
        # Plan 6 §14 (9b): early-season sigma inflation — same mechanism as the
        # single-stat Normal path in calc_prop_prob.
        sigma_combo /= _wnba_early_season_factor()
    return mu_combo, sigma_combo


def calc_combo_prob(proj_player: dict, stat: str, line: float, sport: str = "") -> tuple:
    """Correlated Normal probability for combo props (PRA, PR, PA, RA)."""
    mu, sigma = _combo_mu_sigma(proj_player, stat, sport=sport)
    over_p = 1.0 - normal_cdf(line, mu, sigma)
    return over_p, 1.0 - over_p


def pick_score(win_prob, edge, mode="Default", tier=None,
               cold_start_subtype=None, injury_trigger=False, stat=None):
    """Calculate Pick Score: edge-dominant weighted composite with tier and signal adjustments.

    Weights (wp/edge): Default=40/60, Conservative=55/45, Aggressive=30/70.
    Edge ceiling lowered to 15% (from 20%) to match actual p90 of the distribution.
    Tier multiplier retired 2026-06-06 (Plan 9 §9F) — tier calibration quality now
    enters upstream via BM shrinkage on win_prob; ``tier`` kwarg kept for caller compat.
    Cold-start penalty: taxi=-15, returner=-10, extended_absence=-8, new_acquisition=-5.
    Injury trigger bonus: +7 for redistribution-bump picks.

    NOTE: Score is NOT capped at 100. At wp=0.666 (Platt ceiling) + edge=0.15 (ceiling),
    max score is ~87 (T2, no bonuses) or ~97 (T2 + max injury bonus +7 + tier at 1.0×).
    Scores above 100 are theoretically possible but don't occur in practice given the
    Platt calibration ceiling (~66.6%).

    R11 NOTE: Game line picks (totals, spreads, ML) intentionally score lower than
    props. Win probs for game lines cluster near 50-55% (well-priced markets),
    while props can reach 60-70%+ on model-vs-market gaps.  This is correct behavior —
    game lines are lower-conviction by design and rarely surface in the Premium 5.
    """
    sw, ew = PICK_SCORE_MODES.get(mode, (0.40, 0.60))
    wp_n = (win_prob * 100 - 50) / 25 * 100
    e_n  = (edge * 100) / 15 * 100          # ceiling: 15% (was 20%)
    e_n  = min(e_n, 100.0)  # Plan 6 §11: cap at 15% — legitimate edges don't exceed this;
                            # >15% is almost always a data error, and uncapped e_n let the
                            # optimizer's curse amplify those errors to the top of the card.
                            # ([LARGE-EDGE] warning still fires; Kelly sizing uses raw edge.)
    score = sw * wp_n + ew * e_n
    score += COLD_START_SCORE_PENALTY.get(cold_start_subtype, 0)
    if injury_trigger:
        score += INJURY_TRIGGER_BONUS.get(stat, INJURY_TRIGGER_BONUS_DEFAULT) if stat else INJURY_TRIGGER_BONUS_DEFAULT
    return score
