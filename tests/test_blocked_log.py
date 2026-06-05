"""Tests for log_blocked_pick() — gate-failure CSV logger.

Verifies:
- Structural gate failures are written to pick_log_blocked.csv
- Suspension gates (G_SOG_SUSPENDED, G_HA_SUSPENDED, G_RA_DISABLED) are NOT written
- "PASS" picks are not written
- Header is created on first write; rows append correctly
"""

import csv
import pytest
import run_picks


def _pick(gate_result, stat="PTS", sport="NBA", direction="over",
          line=25.5, odds=-115, adj_edge=0.04, win_prob=0.58, player="Test Player"):
    return {
        "gate_result": gate_result,
        "stat": stat,
        "sport": sport,
        "direction": direction,
        "line": line,
        "odds": odds,
        "adj_edge": adj_edge,
        "win_prob": win_prob,
        "player": player,
    }


@pytest.fixture(autouse=True)
def patch_blocked_path(tmp_path, monkeypatch):
    """Redirect PICK_LOG_BLOCKED_PATH to a temp file for every test."""
    blocked = tmp_path / "pick_log_blocked.csv"
    monkeypatch.setattr(run_picks, "PICK_LOG_BLOCKED_PATH", str(blocked))
    return blocked


# ---------------------------------------------------------------------------
# Basic write / skip behaviour
# ---------------------------------------------------------------------------

def test_structural_gate_written(tmp_path):
    pick = _pick("G9")
    run_picks.log_blocked_pick(pick)
    path = tmp_path / "pick_log_blocked.csv"
    rows = list(csv.DictReader(path.open()))
    assert len(rows) == 1
    assert rows[0]["gate_result"] == "G9"
    assert rows[0]["player"] == "Test Player"
    assert rows[0]["stat"] == "PTS"


def test_g9b_gate_written(tmp_path):
    pick = _pick("G9B", sport="NBA")
    run_picks.log_blocked_pick(pick)
    path = tmp_path / "pick_log_blocked.csv"
    rows = list(csv.DictReader(path.open()))
    assert len(rows) == 1
    assert rows[0]["gate_result"] == "G9B"


def test_pass_not_written(tmp_path):
    run_picks.log_blocked_pick(_pick("PASS"))
    path = tmp_path / "pick_log_blocked.csv"
    assert not path.exists()


def test_sog_suspended_not_written(tmp_path):
    run_picks.log_blocked_pick(_pick("G_SOG_SUSPENDED", stat="SOG", sport="NHL"))
    path = tmp_path / "pick_log_blocked.csv"
    assert not path.exists()


def test_ha_suspended_not_written(tmp_path):
    run_picks.log_blocked_pick(_pick("G_HA_SUSPENDED", stat="HA", sport="MLB"))
    path = tmp_path / "pick_log_blocked.csv"
    assert not path.exists()


def test_ra_disabled_not_written(tmp_path):
    run_picks.log_blocked_pick(_pick("G_RA_DISABLED", stat="RA"))
    path = tmp_path / "pick_log_blocked.csv"
    assert not path.exists()


# ---------------------------------------------------------------------------
# Header + append behaviour
# ---------------------------------------------------------------------------

def test_header_created_on_first_write(tmp_path):
    run_picks.log_blocked_pick(_pick("G7b"))
    path = tmp_path / "pick_log_blocked.csv"
    with path.open() as fh:
        header = fh.readline().strip().split(",")
    assert header == run_picks._BLOCKED_LOG_COLS


def test_appends_on_subsequent_writes(tmp_path):
    run_picks.log_blocked_pick(_pick("G9", player="Player A"))
    run_picks.log_blocked_pick(_pick("G9B", player="Player B"))
    path = tmp_path / "pick_log_blocked.csv"
    rows = list(csv.DictReader(path.open()))
    assert len(rows) == 2
    assert rows[0]["player"] == "Player A"
    assert rows[1]["player"] == "Player B"


def test_game_line_gate_written(tmp_path):
    """GG3 (game line gate) should be logged, not skipped."""
    pick = _pick("GG3", stat="TOTAL", sport="MLB", player="")
    run_picks.log_blocked_pick(pick)
    path = tmp_path / "pick_log_blocked.csv"
    rows = list(csv.DictReader(path.open()))
    assert len(rows) == 1
    assert rows[0]["gate_result"] == "GG3"


def test_edge_field_uses_adj_edge(tmp_path):
    pick = _pick("G9", adj_edge=0.042)
    run_picks.log_blocked_pick(pick)
    path = tmp_path / "pick_log_blocked.csv"
    rows = list(csv.DictReader(path.open()))
    assert float(rows[0]["edge"]) == pytest.approx(0.042, abs=1e-5)


def test_empty_gate_not_written(tmp_path):
    """Empty gate_result string → no write."""
    run_picks.log_blocked_pick(_pick(""))
    path = tmp_path / "pick_log_blocked.csv"
    assert not path.exists()
