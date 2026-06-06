"""Plan 9 §9H: SGP joint-EV existence floor tests.

Per-leg WP floors alone can construct -EV slips on the 4-leg path (the
+200-450 window forces per-leg implied 0.653-0.760, above the 0.65/0.62
floors). ANY slip must now clear: copula joint prob >= implied(parlay odds)
+ SGP_JOINT_EV_MARGIN, in BOTH builders.
"""

import pytest

import sgp_builder as sgp
import mlb_sgp_builder as msgp


def _implied(odds):
    return abs(odds) / (abs(odds) + 100.0) if odds < 0 else 100.0 / (odds + 100.0)


# ---------------------------------------------------------------------------
# Constants — same margin in both modules
# ---------------------------------------------------------------------------

class TestConstants:
    def test_nba_margin_is_0025(self):
        assert sgp.SGP_JOINT_EV_MARGIN == 0.025

    def test_mlb_margin_is_0025(self):
        assert msgp.SGP_JOINT_EV_MARGIN == 0.025


# ---------------------------------------------------------------------------
# NBA builder gate (_joint_ev_ok)
# ---------------------------------------------------------------------------

class TestNbaJointEvGate:
    def test_just_below_margin_rejected(self):
        odds = 250
        joint = _implied(odds) + 0.024
        ok, j, margin = sgp._joint_ev_ok([], odds, _copula_joint=joint)
        assert not ok
        assert j == pytest.approx(joint)
        assert margin == pytest.approx(0.024)

    def test_just_above_margin_accepted(self):
        odds = 250
        joint = _implied(odds) + 0.026
        ok, _, margin = sgp._joint_ev_ok([], odds, _copula_joint=joint)
        assert ok
        assert margin == pytest.approx(0.026)

    def test_exact_margin_accepted(self):
        odds = 250
        joint = _implied(odds) + sgp.SGP_JOINT_EV_MARGIN
        ok, _, _ = sgp._joint_ev_ok([], odds, _copula_joint=joint)
        assert ok

    def test_negative_ev_slip_rejected(self):
        """Joint prob strictly below book-implied — the slip §9H exists to kill."""
        odds = 200
        ok, _, margin = sgp._joint_ev_ok([], odds, _copula_joint=_implied(odds) - 0.05)
        assert not ok
        assert margin < 0


# ---------------------------------------------------------------------------
# MLB builder gate (_joint_ev_ok_mlb)
# ---------------------------------------------------------------------------

def _mlb_leg(stat="OUTS", direction="over", team="NYY", fair_prob=0.70):
    return {"stat": stat, "direction": direction, "team": team,
            "fair_prob": fair_prob}


class TestMlbJointEvGate:
    def test_just_below_margin_rejected(self):
        odds = 300
        joint = _implied(odds) + 0.024
        ok, j, margin = msgp._joint_ev_ok_mlb([], odds, _copula_joint=joint)
        assert not ok
        assert j == pytest.approx(joint)
        assert margin == pytest.approx(0.024)

    def test_just_above_margin_accepted(self):
        odds = 300
        joint = _implied(odds) + 0.026
        ok, _, margin = msgp._joint_ev_ok_mlb([], odds, _copula_joint=joint)
        assert ok
        assert margin == pytest.approx(0.026)

    def test_computes_joint_from_legs_when_not_supplied(self):
        """Without a precomputed joint, the helper runs the seeded copula path."""
        legs = [
            _mlb_leg("OUTS", "over", "NYY", 0.80),
            _mlb_leg("HITS", "under", "BOS", 0.78),
            _mlb_leg("HITS", "over", "NYY", 0.76),
        ]
        ok, joint, margin = msgp._joint_ev_ok_mlb(legs, 300)
        assert 0.0 < joint < 1.0
        # implied(+300)=0.25; three ~0.78 legs joint ≈ 0.47 — comfortably +EV
        assert ok
        assert margin == pytest.approx(joint - 0.25)

    def test_seeded_copula_deterministic(self):
        legs = [
            _mlb_leg("OUTS", "over", "NYY", 0.70),
            _mlb_leg("HITS", "under", "BOS", 0.70),
            _mlb_leg("HITS", "over", "NYY", 0.70),
        ]
        _, j1, _ = msgp._joint_ev_ok_mlb(legs, 250)
        _, j2, _ = msgp._joint_ev_ok_mlb(legs, 250)
        assert j1 == j2
