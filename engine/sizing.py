"""Stake-sizing functions (base card, bonus, VAKE premium, daily lay).

Extracted from run_picks.py (extract-and-re-export refactor, Step 10, executed
before Step 6 because format_output depends on size_daily_lay) and re-imported
there so existing call sites and `from run_picks import ...` keep resolving.
Imports only {stdlib, calibrated, sizing_core} — never run_picks or the other
extracted modules.
"""
import logging
from collections import defaultdict

from calibrated import VAKE_MULT
from sizing_core import kelly_units, get_market_mult, round_units

logger = logging.getLogger("jonnyparlay")


def size_picks_base(picks):
    """Apply BASE sizing to all qualifying picks (Full Card). No VAKE multipliers.
    Sub-50% win probability bets get capped at 0.75u max (high variance)."""
    for p in picks:
        base = kelly_units(p["win_prob"], p["odds"])
        base *= get_market_mult(p.get("sport", "NBA"), p["stat"], p.get("direction"))
        # Plan 9 §9K: uniform 0.25u floor (was 0.50u non-T3 — over-staked the
        # weakest admitted picks 2-2.5× vs the engine's own Kelly math).
        floor = 0.25
        final = max(round_units(base), floor)
        final = min(final, 1.25)
        # Cap high-variance bets (win prob < 50%) at 0.75u
        if p.get("win_prob", 1.0) < 0.50:
            final = min(final, 0.75)
        p["size"] = final
    return picks

def size_bonus_pick(pick):
    """VAKE-style sizing for a standalone bonus drop.

    Bonus drops are posted in isolation — no correlation or exposure penalty
    applies (those are for a 5-pick card). But we still apply the variance
    multiplier so a T3 3PM bonus doesn't end up at 1.25u while the same stat
    on the Premium card is 0.50u. (Tier mult retired Plan 9 §9F — BM shrinkage.)

    Floor mirrors size_picks_base (uniform 0.25u, Plan 9 §9K). Cap stays
    at 1.25u. High-variance (<50% win prob) bets cap at 0.75u.

    Audit H-9: returns ``None`` when the Kelly math rounds below the
    tier floor. Previously we clamped up to the floor and shipped a dust
    bet; the clamp was hiding an upstream edge miscalculation. If the math
    says the pick isn't worth the floor, the right move is to drop it (and
    log a warning) rather than size up to a "sure it'll fit" number. The
    caller must treat ``None`` as "do not post / do not log".
    """
    tier = pick.get("tier", "T2")
    base = kelly_units(pick.get("win_prob", 0), pick.get("odds", 0))
    base *= get_market_mult(pick.get("sport", "NBA"), pick.get("stat", ""), pick.get("direction"))
    # Tier mult retired 2026-06-06 (Plan 9 §9F) — BM shrinkage on win_prob upstream.
    var_m = VAKE_MULT["variance"].get(tier, 0.85)
    raw = base * var_m
    final = round_units(raw)
    floor = 0.25  # Plan 9 §9K: uniform floor (was 0.50u non-T3)
    # H-9: drop rather than clamp. The floor is a safety net for legitimate
    # picks whose math lands close to it — it is NOT a way to manufacture
    # size where the VAKE math says zero.
    if final < floor:
        logger.debug(
            "[bonus-sizing] H-9 drop: %s %s %s @ tier %s — "
            "raw VAKE %.3fu rounded to %.2fu, below floor %.2fu. "
            "edge=%.1f%%, win_prob=%.3f. Not shipping.",
            pick.get("player", "?"), pick.get("stat", "?"), pick.get("direction", "?"), tier,
            raw, final, floor, pick.get("edge", 0) * 100, pick.get("win_prob", 0),
        )
        return None
    final = min(final, 1.25)
    if pick.get("win_prob", 1.0) < 0.50:
        final = min(final, 0.75)
    return final


def size_picks_vake(premium):
    """Apply full VAKE sizing to Premium 5 only, in Pick Score descending order.

    R13 (stacked pitcher-correlation penalty) retired 2026-06-05 (Plan 6 §9):
    G11 guarantees max 1 prop per pitcher, so when 2 pitcher props share a game
    they are DIFFERENT pitchers (opposing starters, rho~0.05-0.20) — R13 applied
    a corr_m for rho=0.52-0.68 on top of the general game corr_m, pure
    double-counting. The MLB SGP rho table prices the same pair at 0.02."""
    premium_sorted = sorted(premium, key=lambda p: p["pick_score"], reverse=True)

    stat_seen = defaultdict(int)
    game_seen = defaultdict(int)

    for p in premium_sorted:
        tier = p["tier"]
        game = p.get("game", "")
        stat = p["stat"]

        base = kelly_units(p["win_prob"], p["odds"])
        market_m = get_market_mult(p.get("sport", "NBA"), p["stat"], p.get("direction"))

        # Variance multiplier (tier mult retired 2026-06-06, Plan 9 §9F —
        # tier calibration now enters via BM shrinkage on win_prob upstream)
        var_m = VAKE_MULT["variance"].get(tier, 0.85)

        # Correlation multiplier (general same-game)
        game_seen[game] += 1
        if game_seen[game] == 1:
            corr_m = 1.00
        elif game_seen[game] == 2:
            corr_m = 0.85
        else:
            corr_m = 0.70

        # Exposure multiplier
        stat_seen[stat] += 1
        exp_m = 1.00 if stat_seen[stat] == 1 else 0.70

        raw = base * market_m * var_m * corr_m * exp_m
        final = min(round_units(raw), 1.25)
        final = max(final, 0.25)  # minimum 0.25u (Plan 9 §9K — was 0.50u, which over-staked weakest picks 2-2.5× vs own Kelly)

        p["size"] = final
        p["size_detail"] = {
            "base": base, "market": market_m, "var": var_m,
            "corr": corr_m, "exp": exp_m, "raw": raw
        }

    return premium_sorted


def size_daily_lay(combined_prob, parlay_odds_american):
    """Kelly-derived sizing for the daily lay parlay.

    Treats the parlay as a single bet and applies quarter Kelly, capped at
    0.75u (max) and floored at 0.25u (min).

    Formula: f* = (p*b - q) / b  where b = decimal_odds - 1
    Quarter Kelly = f* * 0.25, converted to units (1u = 1% of bankroll).

    A negative Kelly (zero or negative EV parlay that somehow cleared
    MIN_DAILY_LAY_PROB) returns the 0.25u floor rather than refusing to
    post — the upstream probability gate is responsible for blocking bad bets.
    """
    if combined_prob <= 0 or parlay_odds_american is None:
        return 0.25
    if parlay_odds_american > 0:
        dec = 1.0 + parlay_odds_american / 100.0
    else:
        dec = 1.0 + 100.0 / abs(parlay_odds_american)
    b = dec - 1.0
    if b <= 0:
        return 0.25
    q = 1.0 - combined_prob
    kelly_full = (combined_prob * b - q) / b
    if kelly_full <= 0:
        return 0.25
    # Quarter Kelly, converted: fraction × 100 = units on 100u bankroll
    raw_units = kelly_full * 0.25 * 100.0
    final = round_units(raw_units)
    return max(min(final, 0.75), 0.25)
