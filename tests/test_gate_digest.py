#!/usr/bin/env python3
"""Tests for the weekly gate-counter digest (P2.11, gate_digest.py).

Covers:
  * week-window filter of the blocked-pick ledger
  * gate-fire tally (per-gate counts, per-sport split, blank-gate skip)
  * Section 1 / Section 2 rendering (incl. top-N truncation + exclusion note)
  * blank-webhook / --dry-run console fallback never POSTs
  * post-once guard blocks a re-post; --repost (force) bypasses it
"""

from __future__ import annotations

import sys

import pytest

# engine/ is added to sys.path by the repo-root conftest.py.
import gate_digest


# ── week-window filter ────────────────────────────────────────────────────
def test_filter_week_blocked_window():
    rows = [
        {"date": "2026-06-08", "gate_result": "G9"},   # before
        {"date": "2026-06-09", "gate_result": "G9"},   # mon (inclusive)
        {"date": "2026-06-12", "gate_result": "G9"},   # inside
        {"date": "2026-06-15", "gate_result": "G9"},   # sun (inclusive)
        {"date": "2026-06-16", "gate_result": "G9"},   # after
        {"date": "", "gate_result": "G9"},             # blank date
    ]
    kept = gate_digest.filter_week_blocked(rows, "2026-06-09", "2026-06-15")
    assert [r["date"] for r in kept] == ["2026-06-09", "2026-06-12", "2026-06-15"]


# ── gate-fire tally ───────────────────────────────────────────────────────
def test_tally_gate_fires_counts_and_sport_split():
    rows = [
        {"gate_result": "G9", "sport": "NBA"},
        {"gate_result": "G9", "sport": "NBA"},
        {"gate_result": "G9", "sport": "MLB"},
        {"gate_result": "G13", "sport": "MLB"},
        {"gate_result": "", "sport": "NBA"},      # blank gate — skipped
        {"gate_result": "G13", "sport": ""},      # blank sport -> "?"
    ]
    by_gate, gate_sport, total = gate_digest.tally_gate_fires(rows)
    assert total == 5  # 3 G9 + 2 G13; the blank-gate row is skipped
    assert by_gate["G9"] == 3
    assert by_gate["G13"] == 2
    assert dict(gate_sport["G9"]) == {"NBA": 2, "MLB": 1}
    assert dict(gate_sport["G13"]) == {"MLB": 1, "?": 1}


def test_sport_split_descending():
    c = gate_digest.Counter({"MLB": 1, "NBA": 5})
    assert gate_digest._sport_split(c) == "NBA 5, MLB 1"


# ── Section 1 rendering ───────────────────────────────────────────────────
def test_section1_empty(monkeypatch):
    monkeypatch.setattr(gate_digest, "load_blocked_rows", lambda *a, **k: [])
    lines = gate_digest.build_section1_lines("2026-06-09", "2026-06-15")
    assert lines == ["No structural gate blocks logged this week."]


def test_section1_with_data(monkeypatch):
    rows = [
        {"date": "2026-06-10", "gate_result": "G9", "sport": "NBA"},
        {"date": "2026-06-11", "gate_result": "G9", "sport": "NBA"},
        {"date": "2026-06-12", "gate_result": "G13", "sport": "MLB"},
        {"date": "2026-06-01", "gate_result": "G9", "sport": "NBA"},  # out of week
    ]
    monkeypatch.setattr(gate_digest, "load_blocked_rows", lambda *a, **k: rows)
    lines = gate_digest.build_section1_lines("2026-06-09", "2026-06-15")
    assert lines[0] == "3 structural blocks across 2 gate(s):"
    assert any(ln.startswith("  G9 — 2") for ln in lines)
    assert any(ln.startswith("  G13 — 1") for ln in lines)
    assert any("Excluded by design" in ln for ln in lines)


def test_section1_truncates_to_top_n(monkeypatch):
    # One unique gate per row, all in-week, more than TOP_GATES of them.
    n = gate_digest.TOP_GATES + 5
    rows = [
        {"date": "2026-06-10", "gate_result": f"G{i:03d}", "sport": "NBA"}
        for i in range(n)
    ]
    monkeypatch.setattr(gate_digest, "load_blocked_rows", lambda *a, **k: rows)
    lines = gate_digest.build_section1_lines("2026-06-09", "2026-06-15")
    gate_lines = [ln for ln in lines if ln.strip().startswith("G")]
    assert len(gate_lines) == gate_digest.TOP_GATES
    assert any("and 5 more gate(s)" in ln for ln in lines)


# ── Section 2 rendering ───────────────────────────────────────────────────
def test_section2_markers(monkeypatch):
    fake = [
        ("MLB Platt refit", 30, 100, "graded MLB over_p_raw rows", False),
        ("SGP Platt calib", 100, 100, "scored SGP slips", True),
    ]
    monkeypatch.setattr(gate_digest, "compute_gate_status", lambda: fake)
    lines = gate_digest.build_section2_lines()
    assert any("[ ] MLB Platt refit: 30/100" in ln for ln in lines)
    assert any("[x] SGP Platt calib: 100/100" in ln for ln in lines)


# ── embed structure ───────────────────────────────────────────────────────
def test_build_embed_structure(monkeypatch):
    monkeypatch.setattr(gate_digest, "load_blocked_rows", lambda *a, **k: [])
    monkeypatch.setattr(gate_digest, "compute_gate_status", lambda: [])
    payload = gate_digest.build_digest_embed("2026-06-09", "2026-06-15")
    assert payload["username"] == gate_digest.BRAND_USERNAME
    assert "content" not in payload          # ops-facing: no @everyone ping
    embed = payload["embeds"][0]
    assert "Weekly Gate Digest" in embed["title"]
    assert len(embed["fields"]) == 2


# ── posting / console fallback ────────────────────────────────────────────
def _boom(*a, **k):  # fail loudly if a POST is attempted
    raise AssertionError("_webhook_post must not be called")


def test_dry_run_never_posts(monkeypatch, capsys):
    import discord_post
    monkeypatch.setattr(discord_post, "_webhook_post", _boom)
    monkeypatch.setattr(gate_digest, "DISCORD_GATES_WEBHOOK", "https://example/webhook")
    monkeypatch.setattr(gate_digest, "load_blocked_rows", lambda *a, **k: [])
    monkeypatch.setattr(gate_digest, "compute_gate_status", lambda: [])
    ok = gate_digest.post_digest("2026-06-09", "2026-06-15", dry_run=True)
    assert ok is True
    assert "Weekly Gate Digest" in capsys.readouterr().out


def test_blank_webhook_console_fallback(monkeypatch, capsys):
    import discord_post
    monkeypatch.setattr(discord_post, "_webhook_post", _boom)
    monkeypatch.setattr(gate_digest, "DISCORD_GATES_WEBHOOK", "")  # unconfigured
    monkeypatch.setattr(gate_digest, "load_blocked_rows", lambda *a, **k: [])
    monkeypatch.setattr(gate_digest, "compute_gate_status", lambda: [])
    ok = gate_digest.post_digest("2026-06-09", "2026-06-15", dry_run=False)
    assert ok is True
    assert "DISCORD_GATES_WEBHOOK unset" in capsys.readouterr().out


def test_guard_blocks_repost(monkeypatch):
    import discord_post
    monkeypatch.setattr(discord_post, "_webhook_post", _boom)
    monkeypatch.setattr(gate_digest, "DISCORD_GATES_WEBHOOK", "https://example/webhook")
    monkeypatch.setattr(gate_digest, "_HAS_GUARD", True)
    monkeypatch.setattr(gate_digest, "_claim_post", lambda key: False)  # already posted
    ok = gate_digest.post_digest("2026-06-09", "2026-06-15", dry_run=False, force=False)
    assert ok is True  # skipped cleanly, no POST (else _boom fires)


def test_force_bypasses_guard_and_posts(monkeypatch):
    import discord_post
    calls = []
    monkeypatch.setattr(discord_post, "_webhook_post",
                        lambda url, payload, **k: calls.append(url) or True)
    monkeypatch.setattr(gate_digest, "DISCORD_GATES_WEBHOOK", "https://example/webhook")
    monkeypatch.setattr(gate_digest, "_HAS_GUARD", True)
    monkeypatch.setattr(gate_digest, "_claim_post", lambda key: (_ for _ in ()).throw(
        AssertionError("claim must be skipped when force=True")))
    monkeypatch.setattr(gate_digest, "load_blocked_rows", lambda *a, **k: [])
    monkeypatch.setattr(gate_digest, "compute_gate_status", lambda: [])
    ok = gate_digest.post_digest("2026-06-09", "2026-06-15", dry_run=False, force=True)
    assert ok is True
    assert calls == ["https://example/webhook"]


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
