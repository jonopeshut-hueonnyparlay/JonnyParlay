"""Tests for discord_guard corruption recovery (audit C2 / F3.2 / F7.2).

Verifies that _load_unlocked returns recovered keys (not {}) when
discord_posted.json contains corrupt/truncated JSON.
"""
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest import mock

import pytest

# Allow import from engine/ or repo root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "engine"))
import discord_guard as dg


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_guard_file(content: bytes, tmp_path: Path) -> Path:
    p = tmp_path / "discord_posted.json"
    p.write_bytes(content)
    return p


# ---------------------------------------------------------------------------
# _rebuild_from_raw_bytes
# ---------------------------------------------------------------------------

class TestRebuildFromRawBytes:
    def test_clean_json_with_all_key_types(self):
        raw = json.dumps({
            "recap:2026-04-14": True,
            "premium_card:2026-04-14": True,
            "killshot:2026-04-15:Anthony Edwards:PTS:OVER:27.5": True,
            "sgp:2026-04-15:MIN vs DEN": True,
            "daily_lay:2026-04-28": True,
        }).encode()
        result = dg._rebuild_from_raw_bytes(raw)
        assert result["recap:2026-04-14"] is True
        assert result["premium_card:2026-04-14"] is True
        assert result["killshot:2026-04-15:Anthony Edwards:PTS:OVER:27.5"] is True
        assert result["sgp:2026-04-15:MIN vs DEN"] is True
        assert result["daily_lay:2026-04-28"] is True

    def test_partial_truncation_recovers_intact_keys(self):
        # Simulates NTFS truncation mid-write
        raw = (
            b'{"recap:2026-04-14": true, "premium_card:2026-04-14": true, '
            b'"daily_lay:2026-04-28": tr'   # truncated mid-value
        )
        result = dg._rebuild_from_raw_bytes(raw)
        assert "recap:2026-04-14" in result
        assert "premium_card:2026-04-14" in result
        # truncated key must NOT appear
        assert "daily_lay:2026-04-28" not in result

    def test_empty_bytes_returns_empty(self):
        assert dg._rebuild_from_raw_bytes(b"") == {}

    def test_garbage_bytes_returns_empty(self):
        assert dg._rebuild_from_raw_bytes(b"NOT JSON AT ALL !!!@#$") == {}

    def test_does_not_recover_false_values(self):
        # Should only recover true-valued keys, not false
        raw = b'{"key_true": true, "key_false": false}'
        result = dg._rebuild_from_raw_bytes(raw)
        assert "key_true" in result
        assert "key_false" not in result

    def test_case_insensitive_true(self):
        # Python's json.dumps writes True (capital T)
        raw = b'{"recap:2026-04-14": True}'
        result = dg._rebuild_from_raw_bytes(raw)
        assert "recap:2026-04-14" in result


# ---------------------------------------------------------------------------
# _load_unlocked with mocked GUARD_FILE
# ---------------------------------------------------------------------------

class TestLoadUnlockedCorruption:
    def test_clean_file_returns_dict(self, tmp_path):
        p = _make_guard_file(
            json.dumps({"recap:2026-04-14": True}).encode(), tmp_path
        )
        with mock.patch.object(dg, "GUARD_FILE", p):
            result = dg._load_unlocked()
        assert result == {"recap:2026-04-14": True}

    def test_missing_file_returns_empty(self, tmp_path):
        p = tmp_path / "discord_posted.json"  # does not exist
        with mock.patch.object(dg, "GUARD_FILE", p):
            result = dg._load_unlocked()
        assert result == {}

    def test_corrupt_file_returns_recovered_keys(self, tmp_path, capsys):
        raw = (
            b'{"recap:2026-04-14": true, "premium_card:2026-04-14": true, '
            b'GARBAGE_HERE'
        )
        p = _make_guard_file(raw, tmp_path)
        with mock.patch.object(dg, "GUARD_FILE", p):
            result = dg._load_unlocked()
        assert "recap:2026-04-14" in result, "must recover intact keys from corruption"
        assert "premium_card:2026-04-14" in result
        captured = capsys.readouterr()
        assert "corrupt" in captured.err.lower() or "corrupt" in captured.out.lower()

    def test_corrupt_file_does_not_return_empty(self, tmp_path):
        """Critical: corrupt guard must NOT silently return {}.
        Returning {} resets all guards and causes a full re-post with @everyone.
        """
        raw = (
            b'{"recap:2026-04-28": true, "killshot:2026-04-28:Player:PTS:OVER:20.5": true'
            b'  TRUNCATION'
        )
        p = _make_guard_file(raw, tmp_path)
        with mock.patch.object(dg, "GUARD_FILE", p):
            result = dg._load_unlocked()
        # Must have recovered at least one key — NOT {}
        assert len(result) > 0, (
            "CRIT: corrupt guard returned {} — this would spam Discord with @everyone"
        )

    def test_zero_byte_file_returns_empty_not_raises(self, tmp_path):
        p = _make_guard_file(b"", tmp_path)
        with mock.patch.object(dg, "GUARD_FILE", p):
            result = dg._load_unlocked()
        assert result == {}
