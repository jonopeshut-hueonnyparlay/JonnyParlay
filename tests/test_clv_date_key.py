"""Tests for CLV date-key fix (C1) — prevents wrong game closing odds being written to old picks.

The 5-tuple key is: (date, player, stat, line, direction).
Without the date component, two picks on different days with identical
player/stat/line/direction would share a key and overwrite each other.
"""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, call
import csv
import io

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "engine"))

from capture_clv import _do_write_closing_odds, picks_needing_clv


# ---------------------------------------------------------------------------
# Key construction
# ---------------------------------------------------------------------------

class TestCLVDateKey:
    """_do_write_closing_odds uses a 5-tuple key including date."""

    def _make_log(self, rows, tmp_path):
        p = tmp_path / "pick_log.csv"
        fields = ["date", "player", "stat", "line", "direction", "closing_odds", "clv"]
        with open(p, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)
        return p

    def test_same_player_different_dates_no_cross_write(self, tmp_path):
        """Two picks same player/stat/line/direction on different dates:
        an update keyed on 2026-05-04 must NOT write to the 2026-05-03 row."""
        rows = [
            {"date": "2026-05-03", "player": "LeBron James", "stat": "PTS",
             "line": "25.5", "direction": "over", "closing_odds": "", "clv": ""},
            {"date": "2026-05-04", "player": "LeBron James", "stat": "PTS",
             "line": "25.5", "direction": "over", "closing_odds": "", "clv": ""},
        ]
        log = self._make_log(rows, tmp_path)
        updates = {
            ("2026-05-04", "lebron james", "PTS", "25.5", "over"): {
                "closing_odds": -110.0, "clv": 0.025,
            }
        }
        n = _do_write_closing_odds(log, updates)
        assert n == 1

        with open(log, newline="") as f:
            out = list(csv.DictReader(f))

        # Only 2026-05-04 row should be updated
        may3_row = next(r for r in out if r["date"] == "2026-05-03")
        may4_row = next(r for r in out if r["date"] == "2026-05-04")
        assert may3_row["closing_odds"] == ""
        assert may4_row["closing_odds"] == str(-110.0)

    def test_update_writes_to_matching_date_row(self, tmp_path):
        """An update should write to the exact row whose date matches the key."""
        rows = [
            {"date": "2026-05-05", "player": "Nikola Jokic", "stat": "REB",
             "line": "12.5", "direction": "over", "closing_odds": "", "clv": ""},
        ]
        log = self._make_log(rows, tmp_path)
        key = ("2026-05-05", "nikola jokic", "REB", "12.5", "over")
        updates = {key: {"closing_odds": -115.0, "clv": 0.012}}
        n = _do_write_closing_odds(log, updates)
        assert n == 1

        with open(log, newline="") as f:
            out = list(csv.DictReader(f))
        assert out[0]["closing_odds"] == str(-115.0)

    def test_no_overwrite_already_filled(self, tmp_path):
        """Row with existing closing_odds should not be overwritten."""
        rows = [
            {"date": "2026-05-05", "player": "Nikola Jokic", "stat": "REB",
             "line": "12.5", "direction": "over", "closing_odds": "-110", "clv": "0.0100"},
        ]
        log = self._make_log(rows, tmp_path)
        key = ("2026-05-05", "nikola jokic", "REB", "12.5", "over")
        updates = {key: {"closing_odds": -120.0, "clv": 0.999}}
        n = _do_write_closing_odds(log, updates)
        assert n == 0  # no update — already filled

        with open(log, newline="") as f:
            out = list(csv.DictReader(f))
        assert out[0]["closing_odds"] == "-110"


# ---------------------------------------------------------------------------
# picks_needing_clv — terminal result filter (L4)
# ---------------------------------------------------------------------------

class TestPicksNeedingCLV:
    def _pick(self, closing="", stat="PTS", result=""):
        return {"closing_odds": closing, "stat": stat, "direction": "over",
                "line": "25.5", "player": "Test Player", "result": result}

    def test_empty_closing_odds_included(self):
        picks = [self._pick(closing="")]
        assert len(picks_needing_clv(picks)) == 1

    def test_filled_closing_odds_excluded(self):
        picks = [self._pick(closing="-110")]
        assert len(picks_needing_clv(picks)) == 0

    def test_win_result_excluded(self):
        picks = [self._pick(closing="", result="W")]
        assert len(picks_needing_clv(picks)) == 0

    def test_loss_result_excluded(self):
        picks = [self._pick(closing="", result="L")]
        assert len(picks_needing_clv(picks)) == 0

    def test_push_result_excluded(self):
        picks = [self._pick(closing="", result="P")]
        assert len(picks_needing_clv(picks)) == 0

    def test_void_result_excluded(self):
        picks = [self._pick(closing="", result="VOID")]
        assert len(picks_needing_clv(picks)) == 0

    def test_empty_result_with_empty_closing_included(self):
        picks = [self._pick(closing="", result="")]
        assert len(picks_needing_clv(picks)) == 1

    def test_stale_closing_excluded(self):
        """STALE sentinel (M9) must be treated as 'captured' — not retried."""
        picks = [self._pick(closing="STALE")]
        assert len(picks_needing_clv(picks)) == 0
