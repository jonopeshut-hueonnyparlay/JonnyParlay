#!/usr/bin/env python3
"""Tests for audit A2 — shadow log dedup must allow same-day re-runs.

The live pick_log.csv keeps full cross-run dedup so re-running
run_picks.py never double-logs to the production ledger.  Shadow logs
(pick_log_custom.csv / pick_log_mlb.csv) bypass cross-run dedup so a
research re-fire produces fresh rows even when keys overlap — silent
no-ops were the symptom that prompted the fix.

Intra-run dedup is preserved everywhere (a single invocation listing the
same pick twice still logs it once).
"""

from __future__ import annotations

import csv
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "engine"))


def _today_et():
    return datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")


CANONICAL_HEADER = [
    "date", "run_time", "run_type", "sport", "player", "team", "stat", "line",
    "direction", "proj", "win_prob", "edge", "odds", "book",
    "tier", "pick_score", "size", "game", "mode", "result",
    "closing_odds", "clv", "card_slot", "is_home",
    "context_verdict", "context_reason", "context_score", "legs", "over_p_raw",
]


def _seed_log(path: Path, rows=()):
    """Write a fresh log with the canonical schema-v4 header + given rows."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(CANONICAL_HEADER)
        for r in rows:
            writer.writerow([r.get(c, "") for c in CANONICAL_HEADER])


def _make_pick(player, stat, line, direction="over"):
    return {
        "player": player, "team_abbrev": "BOS", "stat": stat,
        "line": line, "direction": direction,
        "proj": 26.2, "win_prob": 0.58, "adj_edge": 0.07,
        "odds": -110, "book": "draftkings", "tier": "T1",
        "pick_score": 75.0, "size": 1.25,
        "game": "BOS @ MIA", "sport": "NBA", "is_home": "False",
    }


def _row_count(path: Path) -> int:
    with open(path, "r", encoding="utf-8") as f:
        return sum(1 for _ in csv.DictReader(f))


def test_live_log_dedups_today_picks(tmp_path):
    """Regression guard: pick_log.csv still skips already-logged picks."""
    import run_picks

    log_path = tmp_path / "pick_log.csv"   # canonical filename → live behavior
    today = _today_et()
    seed = [{
        "date": today, "run_type": "primary", "sport": "NBA",
        "player": "Jaylen Brown", "team": "BOS", "stat": "PTS",
        "line": "23.5", "direction": "over",
    }]
    _seed_log(log_path, seed)

    # Resubmit the same pick — live log should dedup (skipped count > 0)
    run_picks.log_picks(
        qualified=[_make_pick("Jaylen Brown", "PTS", 23.5)],
        mode="Default",
        log_path_override=log_path,
    )

    assert _row_count(log_path) == 1, (
        f"live log should dedup; got {_row_count(log_path)} rows"
    )


def test_shadow_log_deduplicates_on_rerun(tmp_path):
    """Shadow logs use the same cross-run dedup as the live log.
    A same-day re-run with an identical pick should not append a 2nd row."""
    import run_picks

    log_path = tmp_path / "pick_log_custom.csv"
    today = _today_et()
    seed = [{
        "date": today, "run_type": "primary", "sport": "NBA",
        "player": "Jaylen Brown", "team": "BOS", "stat": "PTS",
        "line": "23.5", "direction": "over",
    }]
    _seed_log(log_path, seed)
    assert _row_count(log_path) == 1

    # Resubmit the same pick — cross-run dedup should block it
    run_picks.log_picks(
        qualified=[_make_pick("Jaylen Brown", "PTS", 23.5)],
        mode="Default",
        log_path_override=log_path,
    )

    assert _row_count(log_path) == 1, (
        f"shadow log re-run must not duplicate; got {_row_count(log_path)}"
    )


def test_shadow_log_intra_run_dedup_preserved(tmp_path):
    """A pick listed twice in one log_picks call still logs once, even
    when the log is a shadow log."""
    import run_picks

    log_path = tmp_path / "pick_log_custom.csv"
    _seed_log(log_path)  # empty (header only)

    pick = _make_pick("Anthony Edwards", "PTS", 27.5)
    # Same pick appears twice in the qualified list
    run_picks.log_picks(
        qualified=[pick, pick],
        mode="Default",
        log_path_override=log_path,
    )

    assert _row_count(log_path) == 1, (
        f"intra-run dedup must collapse duplicates within a single call; "
        f"got {_row_count(log_path)}"
    )


def test_shadow_log_schema_rewrite_still_fires(tmp_path):
    """Stale-header shadow log must still get its schema upgraded; the
    A2 dedup-skip is gated by is_shadow_log but rows are still loaded."""
    import run_picks

    log_path = tmp_path / "pick_log_custom.csv"
    today = _today_et()
    # Seed with a deliberately old header (pre-v4)
    old_header = ["date", "player", "stat", "line"]
    with open(log_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=old_header, extrasaction="ignore")
        writer.writeheader()
        writer.writerow({
            "date": today, "player": "LeBron James", "stat": "AST", "line": "7.5",
        })

    run_picks.log_picks(
        qualified=[],   # no new picks; only header-rewrite path matters
        mode="Default",
        log_path_override=log_path,
    )

    with open(log_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        new_header = reader.fieldnames
        rows = list(reader)

    # Header upgraded to canonical schema v4
    assert list(new_header)[-3:] == ["source", "model_version", "run_id"]
    assert len(new_header) == 32
    # Original row preserved
    assert len(rows) == 1
    assert rows[0]["player"] == "LeBron James"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
