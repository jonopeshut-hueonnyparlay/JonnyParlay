#!/usr/bin/env python3
"""Tests for audit A4 (2026-05-06) — card guard must not block log_picks
for --no-discord runs.

Symptom that prompted the fix: SaberSim's live run posted today's premium
card and tripped the discord guard.  The shadow scheduled task fired
afterwards, generated 31 qualified picks, and silently logged ZERO of
them to pick_log_custom.csv because the card-guard short-circuit at
run_picks.py:5583 suppressed the entire log_picks branch.

The guard exists for Discord dedup; --no-discord runs (shadow / research
/ dry-run) have no Discord post to deduplicate against and must always
log.  --force-card stays as the explicit operator override for live
re-runs that legitimately need to repost the card.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "engine"))


def test_card_not_up_never_blocks():
    """When the card guard is not tripped, never block (regardless of flags)."""
    import run_picks
    helper = run_picks._card_guard_should_block_logging
    assert helper(card_was_up=False, no_discord=False, force_card=False) is False
    assert helper(card_was_up=False, no_discord=True,  force_card=False) is False
    assert helper(card_was_up=False, no_discord=False, force_card=True)  is False
    assert helper(card_was_up=False, no_discord=True,  force_card=True)  is False


def test_card_up_no_bypass_blocks():
    """Live re-run with the card already up and no override flags — block.

    This is the original behavior the guard was designed for: prevent a
    duplicate premium-card post and the duplicate pick_log entries that
    would follow.
    """
    import run_picks
    helper = run_picks._card_guard_should_block_logging
    assert helper(card_was_up=True, no_discord=False, force_card=False) is True


def test_no_discord_bypasses_card_guard():
    """A4 fix: --no-discord runs always log, even when card is up.

    This is the path the shadow scheduled task takes
    (generate_projections.py --shadow appends --no-discord).
    """
    import run_picks
    helper = run_picks._card_guard_should_block_logging
    assert helper(card_was_up=True, no_discord=True, force_card=False) is False


def test_force_card_bypasses_card_guard():
    """Regression guard: --force-card still bypasses (existing operator override)."""
    import run_picks
    helper = run_picks._card_guard_should_block_logging
    assert helper(card_was_up=True, no_discord=False, force_card=True) is False
    # Both flags together also bypass
    assert helper(card_was_up=True, no_discord=True, force_card=True) is False


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
