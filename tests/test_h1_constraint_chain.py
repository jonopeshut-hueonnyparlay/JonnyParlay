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
