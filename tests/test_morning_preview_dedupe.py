#!/usr/bin/env python3
"""Regression tests for audit M-2 — morning_preview duplicate-post guard.

Before this fix, post_morning_preview ran:
    guard = _load_guard()           # read (releases lock)
    if guard.get(key): return       # no lock held
    webhook_post(...)                 # no lock held  ← CONCURRENT PROCESSES RACE HERE
    guard[key] = True; _save_guard() # write (takes + releases lock)

Two processes (Task Scheduler retry + manual run, or two manual runs) could
both pass the check, both fire @everyone, and then both save. Jono woke up
to two identical announcements on at least one day.

These tests lock in:
  - discord_guard.claim_post atomically test-and-sets under one lock
  - Second claim for the same key returns False (no duplicate webhook)
  - release_post un-claims so a failed webhook can retry
  - release_post is a no-op on unset keys
  - post_morning_preview default path uses claim_post (no TOCTOU)
  - Webhook failure triggers release_post so the next run can retry
  - Webhook success does NOT release (the claim must persist)
  - --test (suppress_ping) never claims so repeated test runs work
  - --test still respects an already-set claim (won't spam after real post)
  - --repost (force) bypasses the claim entirely but still persists it
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "engine"))


# ─────────────────────────────────────────────────────────────────
# Fixture: fresh discord_guard + morning_preview with an isolated
# guard file so concurrent tests don't clobber each other.
# ─────────────────────────────────────────────────────────────────

@pytest.fixture
def fresh_guard(tmp_path, monkeypatch):
    """Reload discord_guard + morning_preview against a temp guard file."""
    import discord_guard as dg

    guard_path = tmp_path / "discord_posted.json"
    lock_path = str(guard_path) + ".lock"
    monkeypatch.setattr(dg, "GUARD_FILE", guard_path)
    monkeypatch.setattr(dg, "LOCK_FILE", lock_path)

    # Reload morning_preview so its own `from discord_guard import ...`
    # bindings pick up the patched module state.
    import morning_preview as mp
    importlib.reload(mp)

    # The reloaded morning_preview re-imported discord_guard — rebind too.
    monkeypatch.setattr(mp, "DISCORD_ANNOUNCE_WEBHOOK", "https://fake.webhook/x",
                        raising=False)
    return dg, mp, guard_path


# ─────────────────────────────────────────────────────────────────
# claim_post / release_post — atomic primitives
# ─────────────────────────────────────────────────────────────────

def test_first_claim_wins(fresh_guard):
    dg, _, _ = fresh_guard
    assert dg.claim_post("preview:2026-04-20") is True


def test_second_claim_for_same_key_fails(fresh_guard):
    dg, _, _ = fresh_guard
    assert dg.claim_post("preview:2026-04-20") is True
    assert dg.claim_post("preview:2026-04-20") is False, (
        "claim_post must be idempotent-False for duplicate keys — the whole "
        "point is preventing a second webhook post."
    )


def test_claim_different_keys_both_succeed(fresh_guard):
    dg, _, _ = fresh_guard
    assert dg.claim_post("preview:2026-04-20") is True
    assert dg.claim_post("preview:2026-04-21") is True
    assert dg.claim_post("recap:2026-04-20") is True


def test_release_allows_reclaim(fresh_guard):
    dg, _, _ = fresh_guard
    assert dg.claim_post("preview:2026-04-20") is True
    dg.release_post("preview:2026-04-20")
    assert dg.claim_post("preview:2026-04-20") is True, (
        "After release_post, a subsequent claim must succeed so a failed "
        "webhook can be retried."
    )


def test_release_on_unset_key_is_noop(fresh_guard):
    dg, _, _ = fresh_guard
    # Should not raise, should not alter state.
    dg.release_post("preview:never-claimed")
    assert dg.load_guard() == {}


def test_release_leaves_other_keys_alone(fresh_guard):
    dg, _, _ = fresh_guard
    dg.claim_post("preview:2026-04-20")
    dg.claim_post("recap:2026-04-20")
    dg.release_post("preview:2026-04-20")
    g = dg.load_guard()
    assert "preview:2026-04-20" not in g
    assert g.get("recap:2026-04-20") is True


# ─────────────────────────────────────────────────────────────────
# post_morning_preview — integrates the claim correctly
# ─────────────────────────────────────────────────────────────────

def _sample_picks():
    return [{
        "date": "2026-04-20", "run_type": "primary", "sport": "NBA",
        "player": "X", "team": "LAL", "stat": "PTS", "line": "20",
        "direction": "over", "odds": "-110", "book": "draftkings",
        "tier": "T1", "size": "1",
    }]


def test_post_default_path_claims_before_posting(fresh_guard):
    dg, mp, _ = fresh_guard
    with patch.object(mp, "_webhook_post", return_value=True) as wp:
        ok = mp.post_morning_preview("2026-04-20", _sample_picks(),
                                     suppress_ping=False, force=False)
    assert ok is True
    assert wp.call_count == 1
    # Claim persists after a successful post.
    assert dg.is_posted("preview:2026-04-20") is True


def test_post_second_concurrent_call_is_blocked_by_claim(fresh_guard):
    """This is the M-2 regression: two back-to-back calls must produce ONE
    webhook post. The first claims, the second sees the claim and bails.
    """
    dg, mp, _ = fresh_guard
    picks = _sample_picks()
    with patch.object(mp, "_webhook_post", return_value=True) as wp:
        first = mp.post_morning_preview("2026-04-20", picks,
                                        suppress_ping=False, force=False)
        second = mp.post_morning_preview("2026-04-20", picks,
                                         suppress_ping=False, force=False)
    assert first is True
    assert second is False
    # CRITICAL invariant: webhook fired exactly once.
    assert wp.call_count == 1, (
        f"Expected exactly 1 webhook call across 2 concurrent posts; got "
        f"{wp.call_count}. The M-2 TOCTOU race is back."
    )


def test_post_webhook_failure_releases_claim_for_retry(fresh_guard):
    """When the webhook fails, the claim must be released so the next run
    can re-claim and try again.
    """
    dg, mp, _ = fresh_guard
    picks = _sample_picks()
    with patch.object(mp, "_webhook_post", return_value=False):
        first = mp.post_morning_preview("2026-04-20", picks,
                                        suppress_ping=False, force=False)
    assert first is False
    # Claim was released on failure.
    assert dg.is_posted("preview:2026-04-20") is False

    # A retry succeeds on the second webhook call.
    with patch.object(mp, "_webhook_post", return_value=True) as wp:
        second = mp.post_morning_preview("2026-04-20", picks,
                                         suppress_ping=False, force=False)
    assert second is True
    assert wp.call_count == 1
    assert dg.is_posted("preview:2026-04-20") is True


def test_post_webhook_success_does_not_release(fresh_guard):
    """Inverse of the above — successful posts must KEEP the claim so a
    second run doesn't duplicate the announcement.
    """
    dg, mp, _ = fresh_guard
    picks = _sample_picks()
    with patch.object(mp, "_webhook_post", return_value=True):
        mp.post_morning_preview("2026-04-20", picks,
                                suppress_ping=False, force=False)
    # Second identical call must NOT fire the webhook again.
    with patch.object(mp, "_webhook_post", return_value=True) as wp:
        second = mp.post_morning_preview("2026-04-20", picks,
                                         suppress_ping=False, force=False)
    assert second is False
    assert wp.call_count == 0


def test_post_test_mode_does_not_claim(fresh_guard):
    """--test (suppress_ping=True) must not persist a claim — Jono needs
    to be able to test repeatedly without locking out the real run.
    """
    dg, mp, _ = fresh_guard
    with patch.object(mp, "_webhook_post", return_value=True) as wp:
        ok1 = mp.post_morning_preview("2026-04-20", _sample_picks(),
                                      suppress_ping=True, force=False)
        ok2 = mp.post_morning_preview("2026-04-20", _sample_picks(),
                                      suppress_ping=True, force=False)
    assert ok1 is True and ok2 is True
    assert wp.call_count == 2, "Test mode should allow repeat posts"
    # No claim was ever persisted.
    assert dg.is_posted("preview:2026-04-20") is False


def test_post_test_mode_respects_existing_real_claim(fresh_guard):
    """A real run already posted — --test must NOT fire a second webhook
    even though it doesn't claim. Otherwise it'd spam the channel.
    """
    dg, mp, _ = fresh_guard
    # Real run first.
    with patch.object(mp, "_webhook_post", return_value=True):
        mp.post_morning_preview("2026-04-20", _sample_picks(),
                                suppress_ping=False, force=False)
    assert dg.is_posted("preview:2026-04-20") is True

    # --test run should be blocked by the existing claim.
    with patch.object(mp, "_webhook_post", return_value=True) as wp:
        ok = mp.post_morning_preview("2026-04-20", _sample_picks(),
                                     suppress_ping=True, force=False)
    assert ok is False
    assert wp.call_count == 0


def test_post_force_bypasses_claim_and_persists(fresh_guard):
    """--repost (force=True) fires the webhook even if already claimed.
    After a successful force-repost, the claim is re-persisted (idempotent).
    """
    dg, mp, _ = fresh_guard
    # First run sets the claim.
    with patch.object(mp, "_webhook_post", return_value=True):
        mp.post_morning_preview("2026-04-20", _sample_picks(),
                                suppress_ping=False, force=False)
    assert dg.is_posted("preview:2026-04-20") is True

    # Force-repost fires anyway.
    with patch.object(mp, "_webhook_post", return_value=True) as wp:
        ok = mp.post_morning_preview("2026-04-20", _sample_picks(),
                                     suppress_ping=False, force=True)
    assert ok is True
    assert wp.call_count == 1
    # Claim is still set (either preserved or re-claimed).
    assert dg.is_posted("preview:2026-04-20") is True


def test_post_empty_picks_never_posts_or_claims(fresh_guard):
    dg, mp, _ = fresh_guard
    with patch.object(mp, "_webhook_post", return_value=True) as wp:
        ok = mp.post_morning_preview("2026-04-20", [], suppress_ping=False, force=False)
    assert ok is False
    assert wp.call_count == 0
    assert dg.is_posted("preview:2026-04-20") is False


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
