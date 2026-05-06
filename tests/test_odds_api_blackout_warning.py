#!/usr/bin/env python3
"""M3 (Audit 2026-05-06): top-level warning when Odds API returns nothing.

Per-game warnings only fire when *some* implied totals are present.  Without
this top-level check, a full Odds API blackout (key revoked, network outage,
quota exhausted) would silently produce un-anchored projections.
"""
from __future__ import annotations

import inspect
import logging
import re
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ENGINE = HERE.parent / "engine"
sys.path.insert(0, str(ENGINE))


# ---------------------------------------------------------------------------
# Source-level guard test — catches accidental removal of the blackout warning.
# ---------------------------------------------------------------------------


class TestM3WarningPresentInSource:
    """Source-level regression check for the M3 fix."""

    def test_blackout_check_present_in_run(self):
        """run() must contain the `not implied_totals and not spreads` blackout check."""
        import generate_projections
        src = inspect.getsource(generate_projections.run)
        # Look for the empty-both check followed by an error-level log call.
        pat = re.compile(
            r"not\s+implied_totals\s+and\s+not\s+spreads"
            r"[\s\S]{0,400}?"
            r"log\.(error|warning)\(",
            re.MULTILINE,
        )
        assert pat.search(src), (
            "M3 fix missing: run() must log an error/warning when both "
            "implied_totals and spreads come back empty (Odds API blackout)."
        )

    def test_warning_message_signals_blackout(self):
        """The warning text must mention blackout + un-anchored so it's grep-able."""
        import generate_projections
        src = inspect.getsource(generate_projections.run)
        # Match the actual error text we wrote (case-insensitive on the keyword).
        assert re.search(r"blackout", src, re.IGNORECASE), \
            "M3 fix: error message must contain the keyword 'blackout' for grep-ability."
        assert re.search(r"un-anchored|un_anchored|unanchored|not be anchored",
                          src, re.IGNORECASE), \
            "M3 fix: error message must signal that projections are un-anchored to Vegas."


# ---------------------------------------------------------------------------
# Behavioral test — exercises the warning by stubbing the Odds-API fetches.
# ---------------------------------------------------------------------------


@pytest.fixture
def stub_run_dependencies(monkeypatch):
    """Stub every external dep used inside run().

    Forces both Odds API fetches to return empty so the blackout branch fires.
    Empty run_projections() result short-circuits run() with "No projections"
    warning *after* the blackout error has fired.
    """
    import generate_projections as gp_mod

    monkeypatch.setattr(gp_mod, "seed_scheduled_games",
                        lambda *a, **k: 0)
    # Both pulls empty → blackout
    monkeypatch.setattr(gp_mod, "fetch_nba_implied_totals",
                        lambda *a, **k: ({}, {}))
    monkeypatch.setattr(gp_mod, "_fetch_spreads",
                        lambda *a, **k: {})
    monkeypatch.setattr(gp_mod, "get_injury_context",
                        lambda *a, **k: ({}, {}, {}))
    monkeypatch.setattr(gp_mod, "_load_inactives_override",
                        lambda *a, **k: {})
    # Empty projections → run() short-circuits cleanly after the blackout warning
    monkeypatch.setattr(gp_mod, "run_projections",
                        lambda *a, **k: [])
    yield gp_mod


def _log_name():
    import generate_projections as gp_mod
    return gp_mod.log.name


class TestM3BehavioralBlackoutWarning:
    """run() emits the blackout error when both fetches are empty."""

    def test_blackout_logs_error(self, stub_run_dependencies, caplog):
        gp_mod = stub_run_dependencies
        with caplog.at_level(logging.ERROR, logger=gp_mod.log.name):
            gp_mod.run(game_date="2026-05-06", season="2025-26", persist=False)
        blackout_records = [r for r in caplog.records
                            if r.levelno == logging.ERROR
                            and "blackout" in r.getMessage().lower()]
        assert blackout_records, (
            "M3 regression: no ERROR-level 'blackout' log fired despite empty "
            "implied_totals + spreads. Captured records: "
            + repr([(r.levelname, r.getMessage()) for r in caplog.records])
        )
        # And the message includes the date so an operator can correlate.
        assert any("2026-05-06" in r.getMessage() for r in blackout_records), (
            "M3: blackout error should include the affected game_date."
        )

    def test_no_warning_when_totals_present(self, stub_run_dependencies,
                                              monkeypatch, caplog):
        """Negative control: warning must NOT fire when implied_totals is non-empty."""
        gp_mod = stub_run_dependencies
        # Override one stub to provide a single implied total
        monkeypatch.setattr(gp_mod, "fetch_nba_implied_totals",
                            lambda *a, **k: ({"100": 220.0}, {}))
        with caplog.at_level(logging.ERROR, logger=gp_mod.log.name):
            gp_mod.run(game_date="2026-05-06", season="2025-26", persist=False)
        blackout_records = [r for r in caplog.records
                            if r.levelno == logging.ERROR
                            and "blackout" in r.getMessage().lower()]
        assert not blackout_records, (
            "M3: blackout error should NOT fire when implied_totals has entries. "
            "Captured: " + repr([r.getMessage() for r in blackout_records])
        )

    def test_no_warning_when_spreads_present(self, stub_run_dependencies,
                                               monkeypatch, caplog):
        """Negative control: warning must NOT fire when spreads are non-empty."""
        gp_mod = stub_run_dependencies
        monkeypatch.setattr(gp_mod, "_fetch_spreads",
                            lambda *a, **k: {"100": -3.5})
        with caplog.at_level(logging.ERROR, logger=gp_mod.log.name):
            gp_mod.run(game_date="2026-05-06", season="2025-26", persist=False)
        blackout_records = [r for r in caplog.records
                            if r.levelno == logging.ERROR
                            and "blackout" in r.getMessage().lower()]
        assert not blackout_records, (
            "M3: blackout error should NOT fire when spreads has entries."
        )


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
