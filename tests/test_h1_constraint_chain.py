"""Tests for H1 (audit 2026-05-06) — Vegas team-total constraint diagnostics.

This file currently covers Step 1 of the H1 plan: the diagnostics hooks added
to engine/diagnostics.py. The Step 5 fix-path tests (adversarial top-5
protection, points-anchor invariance, etc.) are added once the policy
decision is made at the Step 3 checkpoint.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

# diagnostics.py lives under engine/; add that to sys.path so we can import it
# without dragging in the full projection chain (nba_projector et al.).
_ENGINE = Path(__file__).resolve().parent.parent / "engine"
if str(_ENGINE) not in sys.path:
    sys.path.insert(0, str(_ENGINE))

import diagnostics  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _team_projs(n_starters: int = 5, n_bench: int = 7) -> list:
    """Build a synthetic team's projection list, sorted desc by proj_min."""
    starters = [
        {"player_id": 100 + i, "team_id": 1, "game_id": "G1",
         "proj_min": 36.0, "proj_pts": 30.0}
        for i in range(n_starters)
    ]
    bench = [
        {"player_id": 200 + i, "team_id": 1, "game_id": "G1",
         "proj_min": 12.0, "proj_pts": 8.0}
        for i in range(n_bench)
    ]
    return starters + bench


@pytest.fixture(autouse=True)
def _reset_buffers():
    """Reset both diag buffers before/after every test."""
    diagnostics.reset()
    diagnostics.reset_vegas()
    yield
    diagnostics.reset()
    diagnostics.reset_vegas()


@pytest.fixture
def _vegas_diag_on(monkeypatch):
    monkeypatch.setenv("JONNYPARLAY_DIAG_VEGAS_VS_240", "1")


@pytest.fixture
def _vegas_diag_off(monkeypatch):
    monkeypatch.delenv("JONNYPARLAY_DIAG_VEGAS_VS_240", raising=False)


# ---------------------------------------------------------------------------
# Step 1 — diag-hook unit tests
# ---------------------------------------------------------------------------

class TestVegasDiagHooks:

    def test_disabled_by_default(self, _vegas_diag_off):
        assert diagnostics.enabled_vegas_vs_240() is False

    def test_enabled_when_env_set(self, _vegas_diag_on):
        assert diagnostics.enabled_vegas_vs_240() is True

    def test_hooks_no_op_when_disabled(self, _vegas_diag_off):
        """Pre/post hooks must not populate the buffer when env is unset."""
        projs = _team_projs()
        diagnostics.record_team_pre_vegas(1, projs)
        diagnostics.record_team_post_vegas(
            1, raw_scale=0.85, clipped_scale=0.85, vegas_total=110.0,
            projections=projs,
        )
        assert diagnostics._VEGAS_BUFFER == {}

    def test_pre_hook_records_top5_descending(self, _vegas_diag_on):
        """Top-5 is whichever 5 players have highest proj_min, regardless
        of input order."""
        projs = _team_projs()
        # Shuffle bench to the front to verify sorting:
        projs = projs[5:] + projs[:5]
        diagnostics.record_team_pre_vegas(1, projs)

        rec = diagnostics._VEGAS_BUFFER[1]
        assert rec["n_players"] == 12
        assert rec["top5_pids"] == [100, 101, 102, 103, 104]
        assert rec["top5_min_pre"] == [36.0, 36.0, 36.0, 36.0, 36.0]
        assert rec["proj_pts_sum_pre"] == pytest.approx(5 * 30.0 + 7 * 8.0)
        assert rec["team_min_total_pre"] == pytest.approx(5 * 36.0 + 7 * 12.0)

    def test_post_hook_captures_scaled_minutes(self, _vegas_diag_on):
        """Pre + post hooks together capture the audit's adversarial pattern."""
        projs = _team_projs()
        diagnostics.record_team_pre_vegas(1, projs)

        # Simulate constrain_team_totals scaling proj_min by 0.85 uniformly.
        scale = 0.85
        for p in projs:
            p["proj_min"] = round(p["proj_min"] * scale, 2)

        diagnostics.record_team_post_vegas(
            1, raw_scale=scale, clipped_scale=scale, vegas_total=110.0,
            projections=projs,
        )

        rec = diagnostics._VEGAS_BUFFER[1]
        assert rec["raw_scale"] == pytest.approx(0.85, abs=1e-4)
        assert rec["clipped_scale"] == pytest.approx(0.85, abs=1e-4)
        assert rec["vegas_total"] == pytest.approx(110.0)
        # Audit-adversarial top-5 ratio: 36 -> 30.6
        assert rec["top5_min_post"] == [30.6, 30.6, 30.6, 30.6, 30.6]
        # All 12 players captured in matching order
        assert len(rec["all_min_post"]) == 12
        # Bench (rank-6+) was 12.0 -> 10.2
        assert rec["all_min_post"][5:] == [10.2] * 7

    def test_short_circuit_post_hook_still_fires(self, _vegas_diag_on):
        """When clipped_scale ≈ 1.0, mutation skipped but post hook still
        captures state so we can quantify how often vegas was a no-op."""
        projs = _team_projs()
        diagnostics.record_team_pre_vegas(1, projs)
        # No mutation — clipped_scale = 1.0
        diagnostics.record_team_post_vegas(
            1, raw_scale=1.0, clipped_scale=1.0, vegas_total=224.0,
            projections=projs,
        )

        rec = diagnostics._VEGAS_BUFFER[1]
        assert rec["clipped_scale"] == pytest.approx(1.0)
        assert rec["top5_min_post"] == rec["top5_min_pre"]

    def test_post_without_pre_no_op(self, _vegas_diag_on):
        """Defensive: post hook before pre hook silently skips the team."""
        projs = _team_projs()
        diagnostics.record_team_post_vegas(
            7, raw_scale=0.9, clipped_scale=0.9, vegas_total=100.0,
            projections=projs,
        )
        assert 7 not in diagnostics._VEGAS_BUFFER

    def test_flush_writes_sidecar(self, _vegas_diag_on, tmp_path, monkeypatch):
        """flush_vegas() writes vegas_constraint_DATE.json with all teams."""
        # Redirect DATA_DIR for the test
        monkeypatch.setattr(diagnostics, "DATA_DIR", tmp_path)

        projs1 = _team_projs()
        projs2 = _team_projs()
        for p in projs2:
            p["team_id"] = 2
        diagnostics.record_team_pre_vegas(1, projs1)
        diagnostics.record_team_post_vegas(
            1, raw_scale=0.85, clipped_scale=0.85, vegas_total=110.0,
            projections=projs1,
        )
        diagnostics.record_team_pre_vegas(2, projs2)
        diagnostics.record_team_post_vegas(
            2, raw_scale=1.10, clipped_scale=1.10, vegas_total=130.0,
            projections=projs2,
        )

        out = diagnostics.flush_vegas("2026-05-06")
        assert out is not None
        assert out.name == "vegas_constraint_2026-05-06.json"

        payload = json.loads(out.read_text())
        assert set(payload.keys()) == {"1", "2"}
        assert payload["1"]["raw_scale"] == pytest.approx(0.85, abs=1e-4)
        assert payload["2"]["raw_scale"] == pytest.approx(1.10, abs=1e-4)
        # Buffer cleared after flush
        assert diagnostics._VEGAS_BUFFER == {}

    def test_flush_no_op_when_disabled(self, _vegas_diag_off, tmp_path, monkeypatch):
        monkeypatch.setattr(diagnostics, "DATA_DIR", tmp_path)
        # Even if buffer happens to be populated (shouldn't be), flush is a no-op
        # under disabled env. Hooks should also no-op, so buffer stays empty.
        diagnostics.record_team_pre_vegas(1, _team_projs())
        assert diagnostics.flush_vegas("2026-05-06") is None
        assert not list(tmp_path.iterdir())

    def test_redistrib_diag_independent_of_vegas(self, _vegas_diag_on, monkeypatch):
        """Two diag toggles must be fully independent — vegas-on, redistrib-off
        means redistrib hooks remain no-ops and the redistrib buffer stays empty."""
        monkeypatch.delenv("JONNYPARLAY_DIAG_REDISTRIB", raising=False)
        diagnostics.record_out_player(1, 99, "G", 25.0)
        diagnostics.record_team_pre_vegas(1, _team_projs())
        # Redistrib buffer empty, vegas buffer populated.
        assert dict(diagnostics._buffer) == {}
        assert 1 in diagnostics._VEGAS_BUFFER


# ---------------------------------------------------------------------------
# Step 5 — fix-validation tests for Path (b)
# ---------------------------------------------------------------------------
#
# Path (b) (audit 2026-05-06): proj_min removed from _CONSTRAINT_SCALE_KEYS so
# Vegas anchors points (sum of proj_pts) without deflating top-5 minutes.
# These tests pin the post-fix behavior and the points-anchor invariance.

from generate_projections import (  # noqa: E402
    constrain_team_totals,
    _CONSTRAINT_SCALE_KEYS,
    _CONSTRAINT_MIN,
    _CONSTRAINT_MAX,
)


def _player(player_id: int, team_id: int, game_id: str,
            proj_min: float, proj_pts: float, **extra) -> dict:
    p = {
        "player_id": player_id,
        "team_id": team_id,
        "game_id": game_id,
        "proj_min": proj_min,
        "proj_pts": proj_pts,
        "proj_reb": round(proj_pts * 0.18, 2),
        "proj_ast": round(proj_pts * 0.16, 2),
        "proj_fg3m": round(proj_pts * 0.10, 2),
        "proj_blk": 0.5,
        "proj_stl": 0.7,
        "proj_tov": 1.4,
        "dk_std": round(proj_pts * 0.35, 2),
    }
    p.update(extra)
    return p


def _adversarial_team() -> list:
    """5 stars × 36 min / 30 pts + 7 bench × 12 min / 8 pts. team total proj_pts = 206."""
    starters = [_player(100 + i, 1, "G1", 36.0, 30.0) for i in range(5)]
    bench    = [_player(200 + i, 1, "G1", 12.0, 8.0)  for i in range(7)]
    return starters + bench


class TestConstrainTeamTotalsH1Fix:
    """Behavioral tests for the Path (b) fix in constrain_team_totals."""

    def test_proj_min_excluded_from_constraint_keys(self):
        """Sentinel: proj_min must NOT be in the constraint scale keys."""
        assert "proj_min" not in _CONSTRAINT_SCALE_KEYS
        # Stats anchor remains intact:
        assert "proj_pts" in _CONSTRAINT_SCALE_KEYS
        assert "dk_std"   in _CONSTRAINT_SCALE_KEYS

    def test_audit_adversarial_top5_protected(self):
        """Audit-spec fixture: 5*36 + 7*12 vs Vegas total 175.1 (raw scale 0.85).
        Top-5 proj_min must be untouched; only stats scale."""
        team = _adversarial_team()
        # sum proj_pts = 5*30 + 7*8 = 206. Vegas/206 = 0.85 → scale exactly 0.85.
        team_totals = {"G1:1": 175.1}
        constrain_team_totals(team, team_totals)

        starters = [p for p in team if p["player_id"] < 200]
        for p in starters:
            assert p["proj_min"] == pytest.approx(36.0), \
                f"top-5 player {p['player_id']} minute deflated to {p['proj_min']}"
            # Stats scaled by ~0.85
            assert p["proj_pts"] == pytest.approx(30.0 * 0.85, abs=0.05)

    def test_points_anchor_invariance(self):
        """Vegas anchors sum(proj_pts) — invariant must hold regardless of
        proj_min decoupling."""
        team = _adversarial_team()
        vegas = 175.1
        constrain_team_totals(team, {"G1:1": vegas})

        post_pts_sum = sum(p["proj_pts"] for p in team)
        assert post_pts_sum == pytest.approx(vegas, abs=0.5), \
            f"points-anchor broken: post={post_pts_sum} vs vegas={vegas}"

    def test_team_min_total_preserved(self):
        """Total team minutes must be unchanged after Vegas constraint
        (the 240-min constraint upstream is the only authority on minutes).
        Fixture totals 264 (synthetic) — the invariant is pre==post regardless
        of the absolute value."""
        team = _adversarial_team()
        pre_total_min = sum(p["proj_min"] for p in team)
        constrain_team_totals(team, {"G1:1": 175.1})
        post_total_min = sum(p["proj_min"] for p in team)
        assert post_total_min == pytest.approx(pre_total_min, abs=0.01)

    def test_vegas_total_missing_noop(self):
        """Empty team_totals → projections untouched."""
        team = _adversarial_team()
        snapshot = [(p["proj_min"], p["proj_pts"]) for p in team]
        constrain_team_totals(team, {})
        for p, (m, pts) in zip(team, snapshot):
            assert p["proj_min"] == m
            assert p["proj_pts"] == pts

    def test_scale_within_epsilon_short_circuit(self):
        """When raw scale ≈ 1.0, no mutation."""
        team = _adversarial_team()
        # sum proj_pts = 206; pick a vegas total that yields scale within 1e-4 of 1.0.
        vegas = 206.005
        snapshot = [(p["proj_min"], p["proj_pts"]) for p in team]
        constrain_team_totals(team, {"G1:1": vegas})
        for p, (m, pts) in zip(team, snapshot):
            assert p["proj_min"] == m
            assert p["proj_pts"] == pts

    def test_normal_case_no_regression(self):
        """Vegas in agreement with projection (clipped ≈ 1.0) → no changes."""
        team = _adversarial_team()
        vegas = 206.0  # exactly equal to sum proj_pts
        snapshot = [(p["proj_min"], p["proj_pts"]) for p in team]
        constrain_team_totals(team, {"G1:1": vegas})
        for p, (m, pts) in zip(team, snapshot):
            assert p["proj_min"] == pytest.approx(m)
            assert p["proj_pts"] == pytest.approx(pts)

    def test_sub_5_player_team(self):
        """3-player team (pruned roster). Minutes preserved; stats scaled."""
        team = [
            _player(101, 1, "G1", 36.0, 30.0),
            _player(102, 1, "G1", 30.0, 22.0),
            _player(103, 1, "G1", 24.0, 16.0),
        ]
        # sum proj_pts = 68. Vegas = 68 * 0.85 = 57.8 → scale 0.85.
        constrain_team_totals(team, {"G1:1": 57.8})
        # Minutes untouched.
        assert team[0]["proj_min"] == pytest.approx(36.0)
        assert team[1]["proj_min"] == pytest.approx(30.0)
        assert team[2]["proj_min"] == pytest.approx(24.0)
        # Stats scaled.
        assert team[0]["proj_pts"] == pytest.approx(30.0 * 0.85, abs=0.05)

    def test_top5_exceed_240_edge(self):
        """5 players × 50 min, 0 bench (exotic edge). Path (b): minutes still
        untouched. The 240-min upstream logic owns this case; Vegas does not."""
        team = [_player(100 + i, 1, "G1", 50.0, 30.0) for i in range(5)]
        constrain_team_totals(team, {"G1:1": 5 * 30.0 * 0.85})
        for p in team:
            assert p["proj_min"] == pytest.approx(50.0)
            assert p["proj_pts"] == pytest.approx(30.0 * 0.85, abs=0.05)

    def test_clipped_scale_above_1_proj_min_unchanged(self):
        """Vegas wants more points than projector — minutes still untouched."""
        team = _adversarial_team()
        # sum proj_pts = 206; vegas = 230 → raw scale 1.117 (within clip).
        vegas = 230.0
        constrain_team_totals(team, {"G1:1": vegas})
        starters = [p for p in team if p["player_id"] < 200]
        for p in starters:
            assert p["proj_min"] == pytest.approx(36.0)
        assert sum(p["proj_pts"] for p in team) == pytest.approx(vegas, abs=0.5)

    def test_clip_floor_blast_radius_bounded(self):
        """Even if Vegas wants extreme deflation, raw_scale clipped at floor;
        minutes never touched regardless."""
        team = _adversarial_team()
        # vegas = 100 → raw 100/206 = 0.485 → clipped 0.80
        vegas = 100.0
        constrain_team_totals(team, {"G1:1": vegas})
        starters = [p for p in team if p["player_id"] < 200]
        for p in starters:
            assert p["proj_min"] == pytest.approx(36.0)
        # Stats scaled to 0.80, not 0.485, because of clip floor:
        starter_pts_post = sum(p["proj_pts"] for p in team if p["player_id"] < 200)
        assert starter_pts_post == pytest.approx(5 * 30.0 * _CONSTRAINT_MIN, abs=0.05)

    def test_diag_hooks_capture_unchanged_minutes_post_fix(self, monkeypatch):
        """End-to-end: with diag enabled and the fix in place, the sidecar
        records top-5 minutes equal pre and post. Closes the audit pattern."""
        monkeypatch.setenv("JONNYPARLAY_DIAG_VEGAS_VS_240", "1")
        diagnostics.reset_vegas()
        team = _adversarial_team()
        constrain_team_totals(team, {"G1:1": 175.1})  # raw 0.85

        rec = diagnostics._VEGAS_BUFFER[1]
        assert rec["top5_min_pre"] == [36.0] * 5
        assert rec["top5_min_post"] == [36.0] * 5
        # Scale was actually applied (not short-circuited):
        assert rec["clipped_scale"] == pytest.approx(0.85, abs=1e-3)
