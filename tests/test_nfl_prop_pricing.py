"""NFL player-prop pricing wiring (A2).

NFL is offseason — there are no live NFL odds and no NFL replay snapshot — so this
exercises the PRICING path directly: the engine must know how to turn an NFL projection
+ line into a sane win probability. The data-plumbing (EdgeModel CSV export + parse_csv
NFL branch) is the separate preseason step; these tests cover the engine half.
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "engine"))

from calibrated import POISSON_STATS, SIGMA, STAT_FAMILY_TIER  # noqa: E402
from market_config import MARKET_TO_STAT, PROP_MARKETS  # noqa: E402
from prob_core import calc_prop_prob  # noqa: E402


def test_nfl_markets_registered():
    assert "NFL" in PROP_MARKETS
    expect = {
        "player_pass_yds": "PASS_YDS", "player_rush_yds": "RUSH_YDS",
        "player_reception_yds": "REC_YDS", "player_receptions": "REC",
        "player_anytime_td": "TDS", "player_pass_tds": "PASS_TDS",
    }
    for mk, stat in expect.items():
        assert mk in PROP_MARKETS["NFL"], f"{mk} missing from PROP_MARKETS['NFL']"
        assert MARKET_TO_STAT[mk] == stat


def test_nfl_yardage_stats_have_sigma_and_tier():
    # Every NFL yardage stat must resolve a SIGMA entry (no default-fallback warning)
    # and a tier — else the engine mis-prices / crashes at card time.
    for stat, mult in (("PASS_YDS", 0.36), ("RUSH_YDS", 0.62), ("REC_YDS", 0.72)):
        assert SIGMA[stat]["mult"] == mult
        assert STAT_FAMILY_TIER[stat] == "T2"


def test_nfl_count_stats_are_poisson():
    for stat in ("REC", "TDS", "PASS_TDS"):
        assert stat in POISSON_STATS
    assert STAT_FAMILY_TIER["TDS"] == "T3"
    assert STAT_FAMILY_TIER["PASS_TDS"] == "T3"


def test_yardage_prices_normal_from_calibrated_sigma():
    # σ = max(proj*mult, min); over_p = 1 - Φ((line-proj)/σ). Check a known point.
    from quant.distributions import normal_cdf
    proj, line = 72.0, 68.5
    sigma = max(proj * SIGMA["REC_YDS"]["mult"], SIGMA["REC_YDS"]["min"])
    over_p, under_p = calc_prop_prob(proj, line, "REC_YDS", sport="NFL")
    assert math.isclose(over_p, 1 - normal_cdf(line, proj, sigma), rel_tol=1e-9)
    assert math.isclose(over_p + under_p, 1.0, abs_tol=1e-9)


def test_anytime_td_is_one_minus_exp_neg_lambda():
    # ANYTIME_TD (→ TDS) priced as Poisson with the anytime lambda as proj, line 0.5:
    # P(>=1) = 1 - e^-λ.
    for lam in (0.30, 0.55, 0.90):
        over_p, _ = calc_prop_prob(lam, 0.5, "TDS", sport="NFL")
        assert math.isclose(over_p, 1 - math.exp(-lam), rel_tol=1e-9)


def test_poisson_cutoff_hardening_high_line_receptions():
    # The hardening: a POISSON_STAT above POISSON_CUTOFF (8.5) must stay Poisson,
    # NOT fall through to the Normal/SIGMA default fallback. Compare to a direct
    # Poisson computation at a high line.
    from quant.distributions import poisson_cdf
    proj, line = 9.0, 9.5  # line > 8.5
    over_p, _ = calc_prop_prob(proj, line, "REC", sport="NFL")
    assert math.isclose(over_p, 1 - poisson_cdf(9, proj), rel_tol=1e-9)
