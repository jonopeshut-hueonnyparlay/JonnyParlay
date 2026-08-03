"""Tests for grade_picks.py's local Discord-guard fallback (R12).

_load_guard()/_save_guard() delegate to discord_guard.py's shared,
cross-process-safe implementation whenever it's importable. This file
exercises the *fallback* path only (as if discord_guard couldn't be
imported), which previously returned {} on a corrupted guard file instead
of recovering keys the way discord_guard.py itself does.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "engine"))

import grade_picks


# ---------------------------------------------------------------------------
# _rebuild_guard_from_raw_bytes
# ---------------------------------------------------------------------------

class TestRebuildGuardFromRawBytes:
    def test_clean_json_recovers_all_keys(self):
        raw = json.dumps({
            "recap:2026-04-14": True,
            "killshot:2026-04-15:Anthony Edwards:PTS:OVER:27.5": True,
        }).encode()
        result = grade_picks._rebuild_guard_from_raw_bytes(raw)
        assert result["recap:2026-04-14"] is True
        assert result["killshot:2026-04-15:Anthony Edwards:PTS:OVER:27.5"] is True

    def test_partial_truncation_recovers_intact_keys(self):
        raw = (
            b'{"recap:2026-04-14": true, "premium_card:2026-04-14": true, '
            b'"daily_lay:2026-04-28": tr'  # truncated mid-value
        )
        result = grade_picks._rebuild_guard_from_raw_bytes(raw)
        assert "recap:2026-04-14" in result
        assert "premium_card:2026-04-14" in result
        assert "daily_lay:2026-04-28" not in result

    def test_garbage_bytes_returns_empty(self):
        assert grade_picks._rebuild_guard_from_raw_bytes(b"NOT JSON AT ALL !!!@#$") == {}

    def test_does_not_recover_false_values(self):
        raw = b'{"key_true": true, "key_false": false}'
        result = grade_picks._rebuild_guard_from_raw_bytes(raw)
        assert "key_true" in result
        assert "key_false" not in result


# ---------------------------------------------------------------------------
# _load_guard(), forced onto the local fallback path (_HAS_SHARED_GUARD=False)
# ---------------------------------------------------------------------------

class TestLoadGuardFallback:
    def test_clean_file_returns_dict(self, tmp_path):
        p = tmp_path / "discord_posted.json"
        p.write_text(json.dumps({"recap:2026-04-14": True}))
        with mock.patch.object(grade_picks, "_HAS_SHARED_GUARD", False), \
             mock.patch.object(grade_picks, "DISCORD_GUARD_FILE", str(p)):
            result = grade_picks._load_guard()
        assert result == {"recap:2026-04-14": True}

    def test_missing_file_returns_empty(self, tmp_path):
        p = tmp_path / "discord_posted.json"  # does not exist
        with mock.patch.object(grade_picks, "_HAS_SHARED_GUARD", False), \
             mock.patch.object(grade_picks, "DISCORD_GUARD_FILE", str(p)):
            result = grade_picks._load_guard()
        assert result == {}

    def test_corrupt_file_does_not_return_empty(self, tmp_path):
        """Critical: corrupt guard must NOT silently return {} — that resets
        every guard key and causes a full Discord re-post (same class of bug
        discord_guard.py's own corruption recovery guards against)."""
        raw = (
            b'{"recap:2026-04-28": true, '
            b'"killshot:2026-04-28:Player:PTS:OVER:20.5": true  TRUNCATION'
        )
        p = tmp_path / "discord_posted.json"
        p.write_bytes(raw)
        with mock.patch.object(grade_picks, "_HAS_SHARED_GUARD", False), \
             mock.patch.object(grade_picks, "DISCORD_GUARD_FILE", str(p)):
            result = grade_picks._load_guard()
        assert len(result) > 0, (
            "CRIT: corrupt guard returned {} — this would spam Discord with @everyone"
        )
        assert "recap:2026-04-28" in result
        assert "killshot:2026-04-28:Player:PTS:OVER:20.5" in result

    def test_bom_file_does_not_raise(self, tmp_path):
        """A UTF-8 BOM triggers UnicodeDecodeError on the plain-text open();
        must fall into the same recovery path as a JSONDecodeError, not crash."""
        content = b'\xff\xfe{"recap:2026-05-01": true}'
        p = tmp_path / "discord_posted.json"
        p.write_bytes(content)
        with mock.patch.object(grade_picks, "_HAS_SHARED_GUARD", False), \
             mock.patch.object(grade_picks, "DISCORD_GUARD_FILE", str(p)):
            result = grade_picks._load_guard()
        assert isinstance(result, dict)

    def test_shared_guard_available_bypasses_local_fallback(self):
        """When discord_guard imported successfully, _load_guard must delegate
        to it rather than touching the local file path at all."""
        sentinel = {"delegated": True}
        with mock.patch.object(grade_picks, "_HAS_SHARED_GUARD", True), \
             mock.patch.object(grade_picks, "_shared_load_guard", lambda: sentinel):
            assert grade_picks._load_guard() is sentinel
