"""Tests for CLV daemon MIN_UPTIME_BEFORE_EXIT_SECS guard.

The daemon must NOT exit with "All picks captured" when uptime is below
MIN_UPTIME_BEFORE_EXIT_SECS, even if every currently-logged pick has CLV.
This prevents the scenario where NHL picks are captured early but NBA
run_picks hasn't fired yet — the daemon would previously declare "done"
and exit before the NBA picks were ever logged.

2026-05-08 fix: capture_clv.py lines ~1108 and ~1354.
"""

import csv
import json
import os
import sys
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

import pytest

# ── Ensure engine/ is importable ────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "engine"))


# ── Helpers ─────────────────────────────────────────────────────────────────

SCHEMA_HEADER = (
    "date,run_time,run_type,sport,player,team,stat,line,direction,proj,"
    "win_prob,edge,odds,book,tier,pick_score,size,game,mode,result,"
    "closing_odds,clv,card_slot,is_home,context_verdict,context_reason,"
    "context_score,legs,over_p_raw"
)

def _write_pick_log(path: Path, rows: list[dict]) -> None:
    """Write a minimal pick_log CSV with the 29-col schema."""
    fields = SCHEMA_HEADER.split(",")
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            full = {k: "" for k in fields}
            full.update(row)
            writer.writerow(full)


def _nhl_pick_with_clv(date: str) -> dict:
    """An NHL pick that already has closing_odds (captured)."""
    return {
        "date": date,
        "sport": "NHL",
        "player": "BUF ML",
        "stat": "ML_FAV",
        "line": "",
        "direction": "win",
        "odds": "-135",
        "game": "Montreal @ Buffalo",
        "closing_odds": "+115",
        "clv": "-0.1090",
        "result": "",
    }


def _nba_pick_needing_clv(date: str) -> dict:
    """An NBA pick that does NOT have closing_odds yet."""
    return {
        "date": date,
        "sport": "NBA",
        "player": "Karl-Anthony Towns",
        "stat": "AST",
        "line": "3.5",
        "direction": "under",
        "odds": "-117",
        "game": "San Antonio Spurs @ Minnesota Timberwolves",
        "closing_odds": "",
        "clv": "",
        "result": "",
    }


# ── Tests ───────────────────────────────────────────────────────────────────

class TestUptimeGuardTopOfLoop:
    """The 'all picks captured' branch at the top of the while-True loop."""

    def test_exits_when_uptime_exceeds_min(self, tmp_path):
        """After MIN_UPTIME, the daemon SHOULD exit when all picks have CLV."""
        import capture_clv as mod

        date = "2026-05-08"
        log_path = tmp_path / "pick_log.csv"
        _write_pick_log(log_path, [_nhl_pick_with_clv(date)])

        # Daemon has been running for 5 hours (> MIN_UPTIME_BEFORE_EXIT_SECS)
        start_utc = datetime.now(timezone.utc) - timedelta(hours=5)

        picks = mod.load_picks(log_path, date)
        open_picks = mod.picks_needing_clv(picks)
        assert len(open_picks) == 0, "NHL pick should have CLV already"

        any_logged = len(picks) > 0
        assert any_logged

        now = datetime.now(timezone.utc)
        uptime_secs = (now - start_utc).total_seconds()
        assert uptime_secs >= mod.MIN_UPTIME_BEFORE_EXIT_SECS, \
            "Uptime should exceed MIN_UPTIME"

    def test_blocks_exit_when_uptime_below_min(self, tmp_path):
        """Before MIN_UPTIME, the daemon should NOT exit even if all logged picks have CLV."""
        import capture_clv as mod

        date = "2026-05-08"
        log_path = tmp_path / "pick_log.csv"
        _write_pick_log(log_path, [_nhl_pick_with_clv(date)])

        # Daemon started 10 minutes ago (well below MIN_UPTIME_BEFORE_EXIT_SECS)
        start_utc = datetime.now(timezone.utc) - timedelta(minutes=10)

        picks = mod.load_picks(log_path, date)
        open_picks = mod.picks_needing_clv(picks)
        assert len(open_picks) == 0, "NHL pick should have CLV already"

        any_logged = len(picks) > 0
        assert any_logged

        now = datetime.now(timezone.utc)
        uptime_secs = (now - start_utc).total_seconds()
        assert uptime_secs < mod.MIN_UPTIME_BEFORE_EXIT_SECS, \
            "Uptime should be below MIN_UPTIME — daemon must NOT exit"

    def test_nba_pick_prevents_exit_regardless(self, tmp_path):
        """When NBA picks still need CLV, the daemon never exits (uptime irrelevant)."""
        import capture_clv as mod

        date = "2026-05-08"
        log_path = tmp_path / "pick_log.csv"
        _write_pick_log(log_path, [
            _nhl_pick_with_clv(date),
            _nba_pick_needing_clv(date),
        ])

        picks = mod.load_picks(log_path, date)
        open_picks = mod.picks_needing_clv(picks)
        assert len(open_picks) == 1, "NBA pick should still need CLV"
        assert open_picks[0]["stat"] == "AST"


class TestUptimeGuardBottomOfLoop:
    """The 'remaining == 0' check at the bottom of the per-sport processing."""

    def test_remaining_zero_blocked_by_uptime(self, tmp_path):
        """remaining==0 should NOT cause exit when uptime < MIN_UPTIME."""
        import capture_clv as mod

        date = "2026-05-08"
        log_path = tmp_path / "pick_log.csv"
        _write_pick_log(log_path, [_nhl_pick_with_clv(date)])

        start_utc = datetime.now(timezone.utc) - timedelta(minutes=30)
        now = datetime.now(timezone.utc)

        remaining = len(mod.picks_needing_clv(mod.load_picks(log_path, date)))
        assert remaining == 0

        uptime_secs = (now - start_utc).total_seconds()
        # Daemon should continue polling — remaining==0 but uptime too low
        assert uptime_secs < mod.MIN_UPTIME_BEFORE_EXIT_SECS

    def test_remaining_zero_allowed_after_uptime(self, tmp_path):
        """remaining==0 SHOULD cause exit when uptime > MIN_UPTIME."""
        import capture_clv as mod

        date = "2026-05-08"
        log_path = tmp_path / "pick_log.csv"
        _write_pick_log(log_path, [_nhl_pick_with_clv(date)])

        start_utc = datetime.now(timezone.utc) - timedelta(hours=5)
        now = datetime.now(timezone.utc)

        remaining = len(mod.picks_needing_clv(mod.load_picks(log_path, date)))
        assert remaining == 0

        uptime_secs = (now - start_utc).total_seconds()
        assert uptime_secs >= mod.MIN_UPTIME_BEFORE_EXIT_SECS


class TestMinUptimeConstant:
    """Sanity checks on the MIN_UPTIME_BEFORE_EXIT_SECS value."""

    def test_min_uptime_is_at_least_2_hours(self):
        """Guard must be long enough to span NHL→NBA gap (~2-3 hours)."""
        import capture_clv as mod
        assert mod.MIN_UPTIME_BEFORE_EXIT_SECS >= 2 * 3600

    def test_min_uptime_is_at_most_12_hours(self):
        """Guard must not exceed Task Scheduler's ExecutionTimeLimit."""
        import capture_clv as mod
        assert mod.MIN_UPTIME_BEFORE_EXIT_SECS <= 12 * 3600
