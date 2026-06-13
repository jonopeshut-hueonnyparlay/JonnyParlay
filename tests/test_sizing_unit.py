"""Tests for sizing.py functions not covered by test_kelly_market_mult.py.

size_picks_base is already covered (market-mult application) by
tests/test_kelly_market_mult.py and is not duplicated here. size_picks_vake's
size_detail structure is covered by tests/test_plan9_tier_restructure.py — here
we only assert the list/size contract.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "engine"))

import pytest

from sizing import size_bonus_pick, size_picks_vake, size_daily_lay
from quant.odds import implied_prob


# ---------------------------------------------------------------------------
# size_bonus_pick -> float | None
# ---------------------------------------------------------------------------

def _bonus_pick(win_prob, odds, stat="PTS", sport="NBA", direction="under", tier="T2"):
    return {
        "win_prob": win_prob, "odds": odds, "stat": stat,
        "sport": sport, "direction": direction, "tier": tier,
    }


def test_size_bonus_pick_strong_returns_float_in_range():
    size = size_bonus_pick(_bonus_pick(0.65, -110))
    assert isinstance(size, float)
    assert 0.25 <= size <= 1.25


def test_size_bonus_pick_no_edge_returns_none():
    # win_prob at implied -> Kelly 0 -> rounds below 0.25u floor -> H-9 drop (None).
    size = size_bonus_pick(_bonus_pick(implied_prob(-110), -110))
    assert size is None


def test_size_bonus_pick_high_variance_capped():
    # <50% win prob caps at 0.75u when it would otherwise size up.
    size = size_bonus_pick(_bonus_pick(0.45, +180))
    assert size is None or size <= 0.75


# ---------------------------------------------------------------------------
# size_picks_vake -> list, each with "size"
# ---------------------------------------------------------------------------

def _vake_pick(player, stat, game, score, win_prob=0.62, odds=-115, tier="T2"):
    return {
        "player": player, "stat": stat, "game": game, "pick_score": score,
        "win_prob": win_prob, "odds": odds, "tier": tier,
        "direction": "under", "sport": "NBA",
    }


def test_size_picks_vake_returns_same_length_list():
    picks = [
        _vake_pick("A", "PTS", "BOS @ NYK", 80),
        _vake_pick("B", "AST", "LAL @ DEN", 70),
    ]
    out = size_picks_vake(picks)
    assert isinstance(out, list)
    assert len(out) == len(picks)


def test_size_picks_vake_each_has_nonnegative_size():
    out = size_picks_vake([_vake_pick("A", "PTS", "BOS @ NYK", 80)])
    for p in out:
        assert "size" in p
        assert p["size"] >= 0


# ---------------------------------------------------------------------------
# size_daily_lay(combined_prob, parlay_odds_american)
# ---------------------------------------------------------------------------

def test_size_daily_lay_positive_ev_in_range():
    size = size_daily_lay(0.80, +100)
    assert 0.25 <= size <= 0.75


def test_size_daily_lay_caps_at_075():
    # Very strong parlay -> Kelly would exceed cap -> clamps to 0.75u.
    assert size_daily_lay(0.95, +100) == 0.75


def test_size_daily_lay_floor_on_zero_ev():
    # combined_prob at break-even for +100 (0.5) -> Kelly 0 -> 0.25u floor.
    assert size_daily_lay(0.50, +100) == 0.25


def test_size_daily_lay_floor_on_invalid_inputs():
    assert size_daily_lay(0.0, +100) == 0.25
    assert size_daily_lay(0.80, None) == 0.25


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
