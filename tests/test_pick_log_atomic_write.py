#!/usr/bin/env python3
"""Integration tests for audit H-5 — atomic pick_log writes.

Verifies:
1. Header rewrite uses tmp+os.replace (not in-place truncate).
2. Append sites call flush()+fsync() before releasing the lock.
3. A simulated crash mid-header-rewrite leaves the original file intact.
"""

from __future__ import annotations

import csv
import os
import sys
from datetime import datetime
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "engine"))


def _make_header_mismatch_log(path: Path, old_header: list[str], rows: list[dict]):
    """Seed a pick_log with an outdated header + some rows."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=old_header, extrasaction="ignore")
        writer.writeheader()
        for r in rows:
            writer.writerow(r)


def _today_et():
    return datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")


def test_header_rewrite_uses_tmp_file(tmp_path):
    """The header-rewrite branch must write to <path>.tmp and os.replace it in,
    not truncate the live file."""
    import run_picks

    log_path = tmp_path / "pick_log.csv"
    today = _today_et()
    old_header = ["date", "player", "stat", "line"]  # deliberately missing columns
    rows = [
        {"date": today, "player": "LeBron James", "stat": "PTS", "line": "25.5"},
        {"date": today, "player": "Nikola Jokic",  "stat": "AST", "line": "9.5"},
    ]
    _make_header_mismatch_log(log_path, old_header, rows)

    # Call log_picks with no new picks — we only care about the header rewrite path
    run_picks.log_picks(
        qualified=[],
        mode="Default",
        log_path_override=log_path,
    )

    # Live file must exist and have the new header
    assert log_path.exists()
    with open(log_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        new_header = reader.fieldnames
        surviving_rows = list(reader)

    # New header should be the full 29-col schema (superset of old_header)
    assert set(old_header).issubset(set(new_header))
    assert "context_verdict" in new_header  # one of the v2 columns
    assert "legs" in new_header             # v3: 28th column
    assert "over_p_raw" in new_header       # v4: 29th column
    assert new_header[-1] == "over_p_raw", (
        f"'over_p_raw' must be the final column (schema_version=4) but got: {new_header[-1]!r}"
    )
    assert list(new_header).index("legs") == 27
    assert len(new_header) == 29, f"Expected 29 columns, got {len(new_header)}"
    # Original rows preserved
    assert len(surviving_rows) == 2
    assert surviving_rows[0]["player"] == "LeBron James"
    assert surviving_rows[1]["player"] == "Nikola Jokic"

    # No orphan .tmp left behind after successful replace
    tmp_file = log_path.with_suffix(log_path.suffix + ".tmp")
    assert not tmp_file.exists()


def test_header_rewrite_crash_preserves_original(tmp_path):
    """If os.replace is simulated to crash mid-rewrite, the original file
    must still be intact (tmp file cleaned up)."""
    import run_picks

    log_path = tmp_path / "pick_log.csv"
    today = _today_et()
    old_header = ["date", "player", "stat", "line"]
    original_rows = [
        {"date": today, "player": "Anthony Edwards", "stat": "PTS", "line": "26.5"},
    ]
    _make_header_mismatch_log(log_path, old_header, original_rows)
    # Snapshot original bytes for comparison
    original_bytes = log_path.read_bytes()

    def _boom(src, dst):
        raise OSError("simulated crash mid-replace")

    with mock.patch.object(run_picks.os, "replace", side_effect=_boom):
        with pytest.raises(OSError, match="simulated crash"):
            run_picks.log_picks(
                qualified=[],
                mode="Default",
                log_path_override=log_path,
            )

    # Original file untouched
    assert log_path.read_bytes() == original_bytes
    # Tmp file cleaned up by the except branch
    tmp_file = log_path.with_suffix(log_path.suffix + ".tmp")
    assert not tmp_file.exists(), f"Orphan tmp left behind: {tmp_file}"


def test_append_path_calls_fsync(tmp_path):
    """log_picks append branch must flush()+fsync() before exiting the with block."""
    import run_picks

    log_path = tmp_path / "pick_log.csv"
    today = _today_et()
    # Seed with current 29-col schema (schema_version=4, includes over_p_raw) — no rewrite needed
    current_header = [
        "date", "run_time", "run_type", "sport", "player", "team", "stat", "line",
        "direction", "proj", "win_prob", "edge", "odds", "book",
        "tier", "pick_score", "size", "game", "mode", "result",
        "closing_odds", "clv", "card_slot", "is_home",
        "context_verdict", "context_reason", "context_score", "legs", "over_p_raw",
    ]
    with open(log_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(current_header)

    qualified = [{
        "player": "Jaylen Brown", "team_abbrev": "BOS", "stat": "PTS",
        "line": 23.5, "direction": "over",
        "proj": 26.2, "win_prob": 0.58, "adj_edge": 0.07,
        "odds": -110, "book": "draftkings", "tier": "T1",
        "pick_score": 75.0, "size": 1.25, "game": "BOS @ MIA",
        "sport": "NBA", "is_home": "False",
        "context_verdict": "", "context_reason": "", "context_score": "",
    }]

    # Spy on os.fsync to confirm it's called during the append
    fsync_calls = []
    real_fsync = os.fsync

    def spy(fd):
        fsync_calls.append(fd)
        return real_fsync(fd)

    with mock.patch.object(run_picks.os, "fsync", side_effect=spy):
        run_picks.log_picks(
            qualified=qualified,
            mode="Default",
            log_path_override=log_path,
        )

    assert len(fsync_calls) >= 1, "append branch must fsync before releasing the lock"

    # Verify the pick actually landed with today's date
    with open(log_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    assert len(rows) == 1
    assert rows[0]["player"] == "Jaylen Brown"
    assert rows[0]["run_type"] == "primary"
    assert rows[0]["date"] == today


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
