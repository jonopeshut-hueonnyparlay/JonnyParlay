"""Tests for M9 — STALE marker written to pick_log when CLV permanently retired."""
import csv
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "engine"))

from capture_clv import _do_write_closing_odds, picks_needing_clv


class TestSTALEMarker:
    """STALE written to closing_odds marks a pick as permanently missed."""

    def _make_log(self, rows, tmp_path):
        p = tmp_path / "pick_log.csv"
        fields = ["date", "player", "stat", "line", "direction", "closing_odds", "clv"]
        with open(p, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)
        return p

    def test_stale_written_via_do_write(self, tmp_path):
        """_do_write_closing_odds accepts 'STALE' as closing_odds value."""
        rows = [
            {"date": "2026-05-05", "player": "Test Player", "stat": "PTS",
             "line": "25.5", "direction": "over", "closing_odds": "", "clv": ""},
        ]
        log = self._make_log(rows, tmp_path)
        key = ("2026-05-05", "test player", "PTS", "25.5", "over")
        updates = {key: {"closing_odds": "STALE", "clv": None}}
        n = _do_write_closing_odds(log, updates)
        assert n == 1

        with open(log, newline="") as f:
            out = list(csv.DictReader(f))
        assert out[0]["closing_odds"] == "STALE"
        assert out[0]["clv"] == ""  # None → ""

    def test_stale_excluded_from_picks_needing_clv(self, tmp_path):
        """A pick with closing_odds='STALE' is treated as captured — not retried."""
        picks = [
            {"closing_odds": "STALE", "stat": "PTS", "direction": "over",
             "line": "25.5", "player": "Test", "result": ""},
        ]
        result = picks_needing_clv(picks)
        assert result == []

    def test_stale_not_overwritten(self, tmp_path):
        """Once STALE, _do_write_closing_odds must not overwrite with a real value
        (because line 574 guards `not row.get('closing_odds', '').strip()`)."""
        rows = [
            {"date": "2026-05-05", "player": "Test Player", "stat": "PTS",
             "line": "25.5", "direction": "over", "closing_odds": "STALE", "clv": ""},
        ]
        log = self._make_log(rows, tmp_path)
        key = ("2026-05-05", "test player", "PTS", "25.5", "over")
        updates = {key: {"closing_odds": -110.0, "clv": 0.025}}
        n = _do_write_closing_odds(log, updates)
        assert n == 0  # guard: closing_odds non-empty → no overwrite

        with open(log, newline="") as f:
            out = list(csv.DictReader(f))
        assert out[0]["closing_odds"] == "STALE"  # unchanged
