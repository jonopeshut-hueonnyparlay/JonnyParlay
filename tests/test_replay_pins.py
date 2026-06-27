"""Tests for the replay harness's #8 pins: coverage_manifest + calibration_version.

The replay worker pins the in-force manifest (so a promoted market replays
deterministically) and records the calibration_version. These exercise the pin
helpers directly (the subprocess worker just calls them).
"""
import json
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "replay"))

import run_replay as rr  # noqa: E402
import resolver  # noqa: E402


@pytest.fixture(autouse=True)
def _restore_manifest_path():
    saved = resolver._MANIFEST_PATH
    yield
    resolver._MANIFEST_PATH = saved


def test_manifest_pin_uses_snapshot_manifest_when_present(tmp_path):
    man = tmp_path / "coverage_manifest.csv"
    man.write_text("sport,market,mode,weight\nMLB,TOTAL,blend,0.4\n", encoding="utf-8")
    used = rr._apply_manifest_pin(tmp_path)
    assert used == man and resolver._MANIFEST_PATH == man
    # The pinned promoted market is now visible to the resolver.
    assert resolver._active_markets() == {("MLB", "TOTAL"): 0.4}


def test_manifest_pin_dormant_when_absent(tmp_path):
    used = rr._apply_manifest_pin(tmp_path)
    assert not used.exists()                       # guaranteed-missing path
    assert resolver._active_markets() == {}        # -> resolver dormant in replay


def test_calibration_pin_records_meta(tmp_path):
    (tmp_path / "meta.json").write_text(
        json.dumps({"calibration_version": "2026-05-01"}), encoding="utf-8")
    assert rr._check_calibration_pin(tmp_path) == "2026-05-01"


def test_calibration_pin_blank_without_meta(tmp_path):
    assert rr._check_calibration_pin(tmp_path) == ""


def test_calibration_pin_mismatch_warns_to_stderr(tmp_path, capsys):
    (tmp_path / "meta.json").write_text(
        json.dumps({"calibration_version": "1999-01-01"}), encoding="utf-8")
    rr._check_calibration_pin(tmp_path)
    assert "WARNING" in capsys.readouterr().err     # advisory mismatch -> stderr only
