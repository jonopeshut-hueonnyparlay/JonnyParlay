"""Plan 9 §9F tier restructure regression tests (2026-06-06).

Covers:
  - STAT_FAMILY_TIER routing (tiers = calibration-quality buckets, not conviction)
  - TIERS edge floors monotone in calibration quality (T2 0.05 < T1B/T3 0.06 < T1 0.07)
  - apply_bm_shrinkage(): Baker-McHale shrinkage of win_prob toward market implied
  - BM shrinkage wired into evaluate_props (post-Platt, pre-gate)
  - PICK_SCORE_TIER_MULT retired (score is tier-neutral)
  - VAKE_MULT["tier"] retired (sizing chain has no tier_m)
  - R8 reserved T1/T1B premium slots retired (pure Pick Score fill)
"""

import pytest

import run_picks as rp
from run_picks import (
    BM_SHRINKAGE_WEIGHT,
    STAT_FAMILY_TIER,
    TIERS,
    VAKE_MULT,
    apply_bm_shrinkage,
    apply_soft_rules_premium,
    get_tier,
    get_tier_min_edge,
    implied_prob,
    pick_score,
    size_picks_vake,
)


# ---------------------------------------------------------------------------
# Constants / structure
# ---------------------------------------------------------------------------

class TestTierStructure:
    def test_floors_exact_values(self):
        assert TIERS["T1"]["min_edge"] == 0.07
        assert TIERS["T1B"]["min_edge"] == 0.06
        assert TIERS["T2"]["min_edge"] == 0.05
        assert TIERS["T3"]["min_edge"] == 0.06

    def test_floors_monotone_in_calibration_quality(self):
        """T2 (best-calibrated) lowest floor; T1 (moderate/monitored) highest."""
        assert TIERS["T2"]["min_edge"] < TIERS["T1B"]["min_edge"]
        assert TIERS["T2"]["min_edge"] < TIERS["T3"]["min_edge"]
        assert TIERS["T1B"]["min_edge"] <= TIERS["T1"]["min_edge"]
        assert TIERS["T3"]["min_edge"] <= TIERS["T1"]["min_edge"]

    def test_family_map_values_are_valid_tiers(self):
        assert set(STAT_FAMILY_TIER.values()) <= set(TIERS)

    def test_all_live_stats_mapped(self):
        live = {"PTS", "AST", "REB", "3PM", "PRA", "PR", "PA", "RA",
                "OUTS", "HITS", "HA", "ER", "RBI", "RUNS", "BB", "PC", "TB", "HRR",
                "SOG", "SV", "NHLPTS", "NHLBLK", "GOALS",
                "NRFI", "YRFI", "TEAM_TOTAL", "F5_TOTAL"}
        unmapped = live - set(STAT_FAMILY_TIER)
        assert not unmapped, f"live stats missing from STAT_FAMILY_TIER: {sorted(unmapped)}"

    def test_bm_weights_cover_all_tiers(self):
        assert set(BM_SHRINKAGE_WEIGHT) == set(TIERS)
        for w in BM_SHRINKAGE_WEIGHT.values():
            assert 0.0 < w <= 1.0

    def test_pick_score_tier_mult_retired(self):
        assert not hasattr(rp, "PICK_SCORE_TIER_MULT")

    def test_vake_tier_mult_retired(self):
        assert "tier" not in VAKE_MULT
        assert "variance" in VAKE_MULT  # kept (Kelly-stack consolidation candidate)


# ---------------------------------------------------------------------------
# get_tier routing
# ---------------------------------------------------------------------------

class TestGetTierRouting:
    @pytest.mark.parametrize("stat,direction,sport,expected", [
        ("AST", "over", "NBA", "T1B"),   # was T1
        ("AST", "under", "NBA", "T1B"),
        ("AST", "under", "NHL", "T3"),   # sport override kept
        ("REB", "under", "NBA", "T1"),   # was T1B
        ("REB", "over", "NBA", "T2"),    # shadow route unchanged
        ("PTS", "over", "NBA", "T2"),
        ("3PM", "over", "NBA", "T3"),
        ("HRR", "over", "NBA", "T1"),
        ("SOG", "over", "NHL", "T3"),    # was T1 (suspended anyway)
        ("NHLBLK", "over", "NHL", "T3"), # was T2
        ("NRFI", "under", "MLB", "T2"),  # was T3
        ("YRFI", "over", "MLB", "T2"),   # was T3
        ("TEAM_TOTAL", "over", "NBA", "T2"),   # was T1B
        ("TEAM_TOTAL", "under", "MLB", "T2"),  # was T1B
        ("TEAM_TOTAL", "over", "NHL", "T2"),
        ("F5_TOTAL", "over", "MLB", "T2"),     # was T1B
        ("HITS", "under", "MLB", "T1B"),
        ("SPREAD", "over", "NBA", "T2"),       # unmapped game line default
    ])
    def test_routing(self, stat, direction, sport, expected):
        assert get_tier(stat, direction, sport) == expected

    def test_min_edge_lookup_follows_new_floors(self):
        assert get_tier_min_edge("T1") == 0.07
        assert get_tier_min_edge("T1B") == 0.06


# ---------------------------------------------------------------------------
# apply_bm_shrinkage
# ---------------------------------------------------------------------------

class TestBmShrinkage:
    def test_exact_value(self):
        # w=0.70 (T3): 0.70*0.65 + 0.30*implied(-110)
        expected = 0.70 * 0.65 + 0.30 * implied_prob(-110)
        assert apply_bm_shrinkage(0.65, -110, "T3") == pytest.approx(expected)

    def test_shrinks_toward_market(self):
        """Model above implied → shrunk down; model below implied → shrunk up."""
        imp = implied_prob(-110)
        assert apply_bm_shrinkage(0.65, -110, "T2") < 0.65
        assert apply_bm_shrinkage(0.40, -110, "T2") > 0.40
        # never crosses the market prior
        assert apply_bm_shrinkage(0.65, -110, "T2") > imp

    def test_lower_weight_shrinks_harder(self):
        """T3 (w=0.70) lands closer to implied than T2 (w=0.85)."""
        imp = implied_prob(-110)
        t2 = apply_bm_shrinkage(0.65, -110, "T2")
        t3 = apply_bm_shrinkage(0.65, -110, "T3")
        assert abs(t3 - imp) < abs(t2 - imp)

    def test_unknown_tier_uses_default(self):
        expected = (rp.BM_SHRINKAGE_DEFAULT * 0.60
                    + (1 - rp.BM_SHRINKAGE_DEFAULT) * implied_prob(-120))
        assert apply_bm_shrinkage(0.60, -120, "KILLSHOT") == pytest.approx(expected)

    def test_at_market_is_fixed_point(self):
        imp = implied_prob(-110)
        assert apply_bm_shrinkage(imp, -110, "T1") == pytest.approx(imp)


# ---------------------------------------------------------------------------
# evaluate_props wiring (post-Platt, pre-gate)
# ---------------------------------------------------------------------------

def test_evaluate_props_applies_shrinkage():
    """The logged win_prob must equal BM-shrunk(Platt(raw)) for an NBA prop."""
    prop = {
        "player": "Test Player", "stat": "PTS", "proj": 30.0, "line": 25.5,
        "over_odds": -110, "under_odds": -110,
        "book_over": "draftkings", "book_under": "draftkings",
        "game": "BOS @ NYK", "sport": "NBA", "proj_player": {},
    }
    picks = rp.evaluate_props([prop])
    over = next(p for p in picks if p["direction"] == "over")

    raw_over, _ = rp.calc_prop_prob(30.0, 25.5, "PTS", sigma_override=0.0, sport="NBA")
    platted = rp._platt_calibrate_prop(raw_over)
    expected = apply_bm_shrinkage(platted, -110, get_tier("PTS", "over", "NBA"))

    assert over["win_prob"] == pytest.approx(expected, abs=1e-9)
    assert over["win_prob"] < platted  # shrunk toward market (model > implied here)
    assert over["over_p_raw"] == pytest.approx(raw_over)  # pre-Platt/pre-shrink preserved


# ---------------------------------------------------------------------------
# pick_score is tier-neutral
# ---------------------------------------------------------------------------

def test_pick_score_tier_neutral():
    s_t1 = pick_score(0.62, 0.08, tier="T1")
    s_t2 = pick_score(0.62, 0.08, tier="T2")
    s_t3 = pick_score(0.62, 0.08, tier="T3")
    assert s_t1 == s_t2 == s_t3


# ---------------------------------------------------------------------------
# Sizing chain has no tier_m
# ---------------------------------------------------------------------------

def test_size_detail_has_no_tier_mult():
    pick = {
        "player": "A", "stat": "PTS", "game": "BOS @ NYK", "tier": "T2",
        "win_prob": 0.62, "odds": -115, "pick_score": 80.0,
        "direction": "under", "sport": "NBA", "adj_edge": 0.07,
    }
    sized = size_picks_vake([pick])
    detail = sized[0]["size_detail"]
    assert "tier" not in detail
    assert detail["raw"] == pytest.approx(
        detail["base"] * detail["market"] * detail["var"]
        * detail["corr"] * detail["exp"]
    )


# ---------------------------------------------------------------------------
# R8 retired — premium card fills by pure Pick Score
# ---------------------------------------------------------------------------

def _card_pick(player, stat, game, tier, score):
    return {
        "player": player, "stat": stat, "game": game, "tier": tier,
        "pick_score": score, "direction": "under", "win_prob": 0.62,
        "sport": "NBA", "odds": -110,
    }


def test_r8_retired_no_t1_reservation():
    """T1/T1B picks no longer get reserved slots — three higher-scoring T2
    picks beat two T1 picks for the full card (old R8 forced 2 T1 slots)."""
    t2_picks = [
        _card_pick("A", "PTS", "G1 @ H1", "T2", 80),
        _card_pick("B", "OUTS", "G2 @ H2", "T2", 75),
        _card_pick("C", "PC", "G3 @ H3", "T2", 70),
    ]
    t1_picks = [
        _card_pick("D", "REB", "G4 @ H4", "T1", 60),
        _card_pick("E", "AST", "G5 @ H5", "T1B", 55),
    ]
    premium = apply_soft_rules_premium([], t2_picks + t1_picks)
    chosen = {p["player"] for p in premium}
    assert chosen == {"A", "B", "C"}, (
        f"expected pure pick_score fill (A/B/C), got {sorted(chosen)} — "
        f"R8 T1 reservation should be retired"
    )
