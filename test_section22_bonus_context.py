#!/usr/bin/env python3
"""Regression tests for Section 22 — bonus sizing + context honesty.

Covers:
  H-9   size_bonus_pick refuses to ship dust bets: when raw VAKE math
        rounds below the tier floor, returns ``None`` so the caller can
        drop the bonus instead of clamping up to a 0.25u push-on-win bet.
  H-11  apply_context_sanity marks feature-off runs with
        ``context_verdict = "disabled"``, distinct from per-pick
        ``"skipped"``. Keeps schema migrations honest and makes a context-
        side logging bug fail loudly instead of silently poisoning a
        blank column.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "engine"))


# ─────────────────────────────────────────────────────────────────
# H-9 — size_bonus_pick drops dust bets
# ─────────────────────────────────────────────────────────────────

def _bonus_pick(edge, tier, win_prob=0.60, **overrides):
    """Build a minimal pick dict for size_bonus_pick to chew on."""
    base = {
        "adj_edge": edge,
        "tier": tier,
        "win_prob": win_prob,
        "player": "Test Player",
        "stat": "PTS",
        "direction": "over",
    }
    base.update(overrides)
    return base


def test_bonus_size_t1_healthy_edge_returns_size():
    """T1 with healthy edge should size up normally — sanity baseline."""
    from run_picks import size_bonus_pick
    pick = _bonus_pick(edge=0.08, tier="T1")  # 7-9% bracket → base 1.00u
    size = size_bonus_pick(pick)
    assert size is not None
    assert size >= 0.50  # T1 floor
    assert size <= 1.25  # cap


def test_bonus_size_t2_healthy_edge_returns_size():
    from run_picks import size_bonus_pick
    pick = _bonus_pick(edge=0.06, tier="T2")
    size = size_bonus_pick(pick)
    assert size is not None
    assert size >= 0.50
    assert size <= 1.25


def test_bonus_size_t3_borderline_drops_dust():
    """The H-9 bug site. T3 with minimum-edge (3-5%) rolls:
      base=0.50 * var_m=0.65 * tier_m=0.60 = 0.195u raw
    round_units(0.195) = 0.25u. That EQUALS the T3 floor (0.25), so it
    previously clamped to 0.25u and shipped — a dust bet.

    Per H-9, the new behavior: if round_units(raw) < floor, drop entirely.
    0.25 >= 0.25, so this specific case still ships at 0.25u — but only
    because the rounded value meets the floor exactly. Any pick whose raw
    math rolls strictly below 0.25 now drops.

    We verify the strict-below case by using a tier with harsher multipliers.
    """
    from run_picks import size_bonus_pick, VAKE_MULT
    # T4 (multipliers 0.40 * 0.35 = 0.14) × base 0.50 = 0.07 raw → rounds to 0.0
    # Floor for non-T3 is 0.50 — 0.0 < 0.50 → drop.
    assert "T4" in VAKE_MULT["variance"], "T4 must exist in variance multipliers"
    pick = _bonus_pick(edge=0.04, tier="T4")
    size = size_bonus_pick(pick)
    assert size is None, (
        f"T4 with 4% edge should drop as dust — got {size}. The H-9 fix "
        "should refuse to clamp 0.0u up to the 0.50 non-T3 floor."
    )


def test_bonus_size_t3_at_floor_still_ships():
    """Sanity: a T3 pick whose rounded VAKE math *equals* the floor (0.25u)
    ships at the floor. We only drop when strictly below.
    """
    from run_picks import size_bonus_pick
    # T3 @ 4% edge: base 0.50 × 0.65 × 0.60 = 0.195 → rounds to 0.25 (the floor).
    pick = _bonus_pick(edge=0.04, tier="T3")
    size = size_bonus_pick(pick)
    assert size == 0.25, f"T3 at floor should ship at 0.25u, got {size}"


def test_bonus_size_high_variance_caps_at_075():
    """Sanity: <50% win prob caps bonus size at 0.75u."""
    from run_picks import size_bonus_pick
    pick = _bonus_pick(edge=0.12, tier="T1", win_prob=0.45)
    size = size_bonus_pick(pick)
    assert size is not None
    assert size <= 0.75


def test_bonus_size_cap_at_125():
    from run_picks import size_bonus_pick
    pick = _bonus_pick(edge=0.20, tier="T1", win_prob=0.70)
    size = size_bonus_pick(pick)
    assert size is not None
    assert size <= 1.25


def test_bonus_size_returns_none_logs_warning(capsys):
    """The drop path must emit an operator-visible warning — otherwise the
    missing bonus post is invisible. Capture stdout and verify.
    """
    from run_picks import size_bonus_pick
    pick = _bonus_pick(edge=0.04, tier="T4")
    size = size_bonus_pick(pick)
    assert size is None
    captured = capsys.readouterr().out
    assert "H-9 drop" in captured or "below floor" in captured, (
        f"Expected H-9 drop warning on stdout, got: {captured!r}"
    )


# ─────────────────────────────────────────────────────────────────
# H-11 — context verdict "disabled" vs "skipped"
# ─────────────────────────────────────────────────────────────────

def test_apply_context_sanity_skip_marks_disabled():
    """When ``--context`` is NOT passed, the wrapper calls
    apply_context_sanity(skip=True). Every pick must be marked
    ``context_verdict = "disabled"`` — not "skipped".
    """
    from run_picks import apply_context_sanity
    picks = [
        {"player": "Luka Doncic",  "stat": "PTS", "sport": "NBA"},
        {"player": "Nikola Jokic", "stat": "REB", "sport": "NBA"},
    ]
    still_qualified, rejects = apply_context_sanity(
        picks, "2026-04-20", skip=True, mode="Default"
    )
    assert rejects == []
    assert len(still_qualified) == 2
    for p in still_qualified:
        assert p["context_verdict"] == "disabled", (
            f"H-11: skip=True must mark 'disabled', got {p['context_verdict']!r}"
        )
        assert p["context_reason"] == ""
        assert p["context_score"] == 0


def test_apply_context_sanity_disabled_preserves_picks():
    """Every pick passed in with skip=True comes back in still_qualified —
    disabling the feature must never cut picks.
    """
    from run_picks import apply_context_sanity
    picks = [{"player": f"Player{i}", "stat": "PTS", "sport": "NBA"} for i in range(10)]
    still_qualified, rejects = apply_context_sanity(
        picks, "2026-04-20", skip=True, mode="Default"
    )
    assert len(still_qualified) == 10
    assert rejects == []


def test_apply_context_sanity_empty_picks_returns_empty():
    from run_picks import apply_context_sanity
    still_qualified, rejects = apply_context_sanity(
        [], "2026-04-20", skip=True, mode="Default"
    )
    assert still_qualified == []
    assert rejects == []


def test_context_schema_header_documents_disabled_verdict():
    """The schema comment for context_verdict must mention ``disabled``,
    so future maintainers don't trip over the new state.
    """
    import pick_log_schema
    # Sanity: the column is still present and in the canonical position
    assert "context_verdict" in pick_log_schema.CANONICAL_HEADER
    # Grep the source file for the comment mentioning disabled
    src = Path(pick_log_schema.__file__).read_text(encoding="utf-8")
    # Find the context_verdict line and confirm 'disabled' is in its comment
    for line in src.splitlines():
        if '"context_verdict"' in line:
            assert "disabled" in line, (
                f"context_verdict schema comment must mention 'disabled'; got: {line!r}"
            )
            break
    else:
        pytest.fail("context_verdict column not found in schema source")


def test_context_flags_report_skips_disabled_rows():
    """format_output's context-flags section (G) should not list rows
    whose verdict is 'disabled' — that's the whole point of having a
    separate state.

    The filter is written across two lines, so we scan a window starting
    at the ``ctx_picks = [...]`` assignment and require 'disabled' to
    appear inside the ``not in (...)`` tuple.
    """
    import run_picks
    src = Path(run_picks.__file__).read_text(encoding="utf-8")
    lines = src.splitlines()
    # Find the ctx_picks ASSIGNMENT (the list-comp), not the later sorted() call.
    for i, line in enumerate(lines):
        if "ctx_picks" in line and "=" in line and "[" in line:
            # Grab the next 3 lines too — the filter can span lines.
            window = "\n".join(lines[i:i + 4])
            assert "disabled" in window, (
                f"H-11: ctx_picks filter must exclude 'disabled'. Window:\n{window}"
            )
            break
    else:
        pytest.fail("ctx_picks assignment not found in run_picks source")


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
