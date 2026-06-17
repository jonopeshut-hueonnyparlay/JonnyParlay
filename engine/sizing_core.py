"""Core sizing/Kelly/tier-routing helpers.

Extracted from run_picks.py (extract-and-re-export refactor, Step 4) and
re-imported there so existing call sites and `from run_picks import ...` keep
resolving. Imports only {thresholds, calibrated, quant.odds} — never run_picks
or the other extracted modules.
"""
from thresholds import BM_SHRINKAGE_DEFAULT, KELLY_FRACTION, DEFAULT_MARKET_MULT
from calibrated import BM_SHRINKAGE_WEIGHT, KELLY_MARKET_MULT, STAT_FAMILY_TIER, TIERS
from quant.odds import implied_prob


def apply_bm_shrinkage(win_prob, odds, tier):
    """Baker–McHale (2013) shrinkage of model win_prob toward market implied prob.

    shrunk_p = w·model_p + (1−w)·implied_p, with w = BM_SHRINKAGE_WEIGHT[tier].
    Replaces PICK_SCORE_TIER_MULT + VAKE_MULT["tier"] — one mechanism that moves
    win_prob, edge, pick_score and Kelly stake coherently (Plan 9 §9F).

    DECISION — shrinkage anchor is the VIGGED single-side implied prob
    (`implied_prob(odds)`), the actual market quote. Aligned everywhere: this is
    the only shrinkage path (props only); game-line edges are computed directly
    and never shrunk. EDGE is measured against the NO-VIG prob in every path
    (props: calc_edge -> no_vig; game lines: explicit no_vig()), so the two
    bases are deliberately different.

    Structural reason the anchor is vigged (not no-vig): this fn only receives
    the single-side `odds`, so it cannot devig internally — the no-vig prob
    (`nv_prob`) is computed by the caller (evaluate_props). Switching the anchor
    to no-vig would require threading `nv_prob` in (a signature change), not a
    one-liner.

    KNOWN CONSEQUENCE (DATA_GATED reconsideration — decide at CLV maturity /
    per-family BM weight refit n≥150): because the anchor is vigged but edge is
    measured vs no-vig, a model that exactly equals the FAIR (no-vig) price still
    reports a small positive residual edge = (1−w)·(half-vig) — and it is LARGER
    for lower-weight tiers (T3 w=0.70 -> ~0.71pp at −110; T2 w=0.85 -> ~0.36pp;
    bigger on juicier two-way markets). Baker–McHale theory anchors on the
    market's unbiased p_true estimate (= no-vig), so the theoretically-correct
    anchor is no-vig; vigged is retained for now (small magnitude, immature CLV).
    Revisit alongside the "BM direction inverted §B" item.
    """
    w = BM_SHRINKAGE_WEIGHT.get(tier, BM_SHRINKAGE_DEFAULT)
    return w * win_prob + (1.0 - w) * implied_prob(odds)

def kelly_units(win_prob, odds):
    """Continuous Kelly base sizing: f* = (b*p - q) / b, scaled by KELLY_FRACTION.

    Returns 0.0 for negative or zero Kelly (no edge) so callers' floor logic fires.
    FIX M4 equivalent: safety is handled by the floor in each caller.
    """
    try:
        o = float(odds)
    except (ValueError, TypeError):
        return 0.0
    if o > 0:
        b = o / 100.0
    elif o < 0:
        b = 100.0 / abs(o)
    else:
        return 0.0
    p = float(win_prob)
    q = 1.0 - p
    f_star = (b * p - q) / b
    if f_star <= 0:
        return 0.0
    return f_star * KELLY_FRACTION

def round_units(u):
    """Round to nearest 0.25u."""
    return round(u * 4) / 4

def get_market_mult(sport, stat, direction):
    """Return Kelly market multiplier for (sport, stat, direction).

    Lookup order: exact (sport,stat,direction) → (sport,stat,None) → DEFAULT_MARKET_MULT.
    """
    m = KELLY_MARKET_MULT.get((sport, stat, direction))
    if m is None:
        m = KELLY_MARKET_MULT.get((sport, stat, None))
    return m if m is not None else DEFAULT_MARKET_MULT

def get_tier(stat, direction="over", sport="NBA"):
    """Route a stat family to its calibration-quality tier (Plan 9 §9F).

    STAT_FAMILY_TIER is the single source of truth — direction-independent
    except the REB-over shadow route. The old under-only T1B rule and the
    TEAM_TOTAL/F5_TOTAL T1B overrides are retired (both now T2, floor 0.05).
    Sport-aware override kept: NHL AST → T3 (Bernoulli at 0.5 line, CV >1.0,
    20%+ hold; G_NHL_AST gates it to 0.5-under anyway).
    """
    if stat == "REB" and direction == "over":
        return "T2"  # routed to shadow via apply_hard_rules R4_REB_OVER (was None/banned)
    if stat == "AST" and sport == "NHL":
        return "T3"
    # Unmapped stats (remaining game lines: SPREAD, TOTAL, ML_FAV, F5_ML, F5_SPREAD) → T2
    return STAT_FAMILY_TIER.get(stat, "T2")

def get_tier_min_edge(tier):
    """Get minimum edge for a tier."""
    return TIERS.get(tier, {}).get("min_edge", 0.05)
