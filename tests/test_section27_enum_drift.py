#!/usr/bin/env python3
"""Regression tests for Section 27 — downstream enum drift.

Three downstream consumers of pick_log had enums/buckets that fell out
of sync with upstream schema additions:

  M-11   morning_preview.TIER_ORDER was missing T1B and DAILY_LAY, mixed
         tier tokens with run-type labels, and relied on alphabetical
         fallback that placed T1B after T3 in the output.
  M-12   weekly_recap.GAME_LINE_STATS was missing PARLAY, so a daily_lay
         aggregate row dropped into the prop-label branch and emitted
         garbage ("3-LEG COVER  PARLAY").
  M-13   analyze_picks.pick_score_bucket thresholds (< 3 / 3-5 / 5-8 /
         8-12 / 12+) were calibrated to an ancient Pick Score scale;
         real scores are 0-120 and KILLSHOT sizing tiers live at
         90-100 / 100-110 / 110+.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "engine"))


# ─────────────────────────────────────────────────────────────────
# M-11 — morning_preview.TIER_ORDER
# ─────────────────────────────────────────────────────────────────

def test_tier_order_contains_all_real_tier_tokens():
    """Every tier token actually emitted by run_picks.py (per CLAUDE.md
    schema) must be present in TIER_ORDER so morning_preview can render
    it in the intended position instead of falling back to alphabetical.
    """
    from morning_preview import TIER_ORDER
    expected = {"KILLSHOT", "T1", "T1B", "T2", "T3", "DAILY_LAY"}
    assert expected <= set(TIER_ORDER), (
        f"TIER_ORDER is missing real tier tokens: "
        f"{expected - set(TIER_ORDER)}. Present: {TIER_ORDER}"
    )


def test_tier_order_has_no_run_type_contamination():
    """PREMIUM / POTD / BONUS are run-type / channel labels, NOT tier
    tokens. They never appear in pick_log.csv's `tier` column, so their
    presence in TIER_ORDER was dead code that confused readers.
    """
    from morning_preview import TIER_ORDER
    run_type_labels = {"PREMIUM", "POTD", "BONUS", "primary", "bonus",
                       "manual", "daily_lay"}
    contamination = set(TIER_ORDER) & run_type_labels
    assert not contamination, (
        f"TIER_ORDER contains run-type labels, not tier tokens: "
        f"{contamination}. Move these out — TIER_ORDER must be tier-only."
    )


def test_tier_order_places_t1b_between_t1_and_t2():
    """T1B is a sub-tier of T1 (strong but not KILLSHOT). It must render
    between T1 and T2 in the preview, not after T3 (which is what the
    alphabetical fallback produced before M-11 closed).
    """
    from morning_preview import TIER_ORDER
    idx = {t: i for i, t in enumerate(TIER_ORDER)}
    assert "T1" in idx and "T1B" in idx and "T2" in idx
    assert idx["T1"] < idx["T1B"] < idx["T2"], (
        f"Tier display order is wrong: {TIER_ORDER}. Expected T1 < T1B < T2."
    )


def test_tier_order_killshot_first_daily_lay_last():
    """Conviction ordering: KILLSHOT at the top (highest), DAILY_LAY at
    the bottom (separate product, separate pricing model).
    """
    from morning_preview import TIER_ORDER
    assert TIER_ORDER[0] == "KILLSHOT", (
        f"KILLSHOT must render first in the preview. Got TIER_ORDER[0]={TIER_ORDER[0]!r}"
    )
    assert TIER_ORDER[-1] == "DAILY_LAY", (
        f"DAILY_LAY must render last. Got TIER_ORDER[-1]={TIER_ORDER[-1]!r}"
    )


def test_tier_order_is_unique():
    """Defense against a future rebase that duplicates a tier — duplicate
    keys would render twice and inflate the totals in the preview.
    """
    from morning_preview import TIER_ORDER
    assert len(TIER_ORDER) == len(set(TIER_ORDER)), (
        f"TIER_ORDER has duplicates: {TIER_ORDER}"
    )


# ─────────────────────────────────────────────────────────────────
# M-12 — weekly_recap.GAME_LINE_STATS + _pick_short_label for PARLAY
# ─────────────────────────────────────────────────────────────────

def test_parlay_is_in_game_line_stats():
    """PARLAY must live in GAME_LINE_STATS so _pick_short_label routes it
    to the game-line branch rather than the prop (player-last-name) branch.
    """
    from weekly_recap import GAME_LINE_STATS
    assert "PARLAY" in GAME_LINE_STATS


def test_pick_short_label_formats_parlay_with_player_and_odds():
    """Audit M-12: the aggregate daily_lay row shape is
    ``{player: 'Daily Lay 3-leg', stat: 'PARLAY', odds: '+540', ...}``.
    The short label must surface both the leg-count label and the price.
    """
    from weekly_recap import _pick_short_label
    p = {
        "stat": "PARLAY",
        "player": "Daily Lay 3-leg",
        "odds": "+540",
        "direction": "cover",
        "line": "",
    }
    label = _pick_short_label(p)
    assert "Daily Lay 3-leg" in label
    assert "+540" in label
    # Must not fall into the prop branch and emit "3-LEG" as a last-name.
    assert "3-LEG" not in label.upper() or "DAILY LAY" in label.upper()


def test_pick_short_label_parlay_without_odds_is_clean():
    """If odds happen to be missing (legacy row, dry-run, etc.) the
    label must still be readable — no trailing '@', no empty odds string.
    """
    from weekly_recap import _pick_short_label
    p = {
        "stat": "PARLAY",
        "player": "Daily Lay 3-leg",
        "odds": "",
        "direction": "cover",
        "line": "",
    }
    label = _pick_short_label(p).strip()
    assert label == "Daily Lay 3-leg", (
        f"Expected 'Daily Lay 3-leg' verbatim, got {label!r}"
    )


def test_pick_short_label_parlay_default_when_player_missing():
    """If `player` is somehow blank, the label must not degrade to just
    the odds (e.g. "@ +540"). It falls back to a 'Daily Lay' sentinel.
    """
    from weekly_recap import _pick_short_label
    p = {
        "stat": "PARLAY",
        "player": "",
        "odds": "+540",
        "direction": "cover",
        "line": "",
    }
    label = _pick_short_label(p)
    assert label.startswith("Daily Lay"), (
        f"Expected a 'Daily Lay' fallback prefix, got {label!r}"
    )


def test_pick_short_label_spread_still_works():
    """Regression guard: adding PARLAY must not disturb existing branches
    (SPREAD / ML / TOTAL)."""
    from weekly_recap import _pick_short_label
    assert _pick_short_label({
        "stat": "SPREAD", "player": "LAK", "line": "-1.5", "direction": "cover"
    }) == "LAK -1.5"
    assert _pick_short_label({
        "stat": "ML_FAV", "player": "BOS", "line": "", "direction": ""
    }) == "BOS ML"
    assert _pick_short_label({
        "stat": "TOTAL", "player": "NYI @ PHI", "line": "6.5", "direction": "over"
    }) == "Total OVER 6.5"


def test_pick_short_label_prop_branch_still_works():
    """Prop rows must still land in the player-last-name branch."""
    from weekly_recap import _pick_short_label
    label = _pick_short_label({
        "stat": "AST", "player": "Luka Dončić",
        "line": "7.5", "direction": "over",
    })
    assert "DONČIĆ" in label.upper() or "DONCIC" in label.upper()
    assert "AST" in label
    assert "7.5" in label


# ─────────────────────────────────────────────────────────────────
# M-13 — analyze_picks.pick_score_bucket alignment to 0-120 scale
# ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("ps,bucket", [
    (0,     "< 40"),
    (25,    "< 40"),
    (39.9,  "< 40"),
    (40,    "40-60"),
    (59.9,  "40-60"),
    (60,    "60-75"),
    (74.9,  "60-75"),
    (75,    "75-90"),
    (89.9,  "75-90"),
    # KILLSHOT v2 (Apr 21 2026): score >= 90 is the qualification floor.
    # Sizing is no longer tiered by score - it's driven by win_prob + edge -
    # so buckets split the >=90 range into three bins for conviction visibility.
    (90,    "90-95 (KS floor)"),
    (94.9,  "90-95 (KS floor)"),
    (95,    "95-100"),
    (99.9,  "95-100"),
    (100,   "100+"),
    (109.9, "100+"),
    (110,   "100+"),
    (130,   "100+"),
])
def test_pick_score_bucket_aligned_to_killshot_sizing(ps, bucket):
    """Bucket boundaries must align with the KILLSHOT v2 qualification floor
    (pick_score >= 90) and with the real-world score range observed in
    pick_log.csv (~13 -> 95). v2 no longer tiers sizing by score.
    """
    from analyze_picks import pick_score_bucket
    assert pick_score_bucket(ps) == bucket, (
        f"pick_score_bucket({ps}) -> {pick_score_bucket(ps)!r}, expected {bucket!r}"
    )


def test_pick_score_bucket_top_label_calls_out_killshot():
    """The 90-95 bucket must call out that it's the KILLSHOT qualification
    floor - v2 no longer splits the >=90 range by sizing tier, so the label
    is a conviction marker rather than a sizing hint.
    """
    from analyze_picks import pick_score_bucket
    assert "KS" in pick_score_bucket(92)     # 90-95 (KS floor)
    # 95+ buckets deliberately drop the KS tag - sizing isn't score-driven
    # under v2, so over-labeling would mislead the reader.
    assert pick_score_bucket(97) == "95-100"
    assert pick_score_bucket(115) == "100+"


def test_pick_score_bucket_handles_unknown():
    """A pick with no stored pick_score (or malformed string) must not
    crash the whole analyze run. It should land in a dedicated bucket so
    the bad rows can be spotted in the breakdown.
    """
    from analyze_picks import pick_score_bucket
    assert pick_score_bucket(None) == "unknown"
    assert pick_score_bucket("") == "unknown"
    assert pick_score_bucket("not-a-number") == "unknown"


def test_pick_score_bucket_old_thresholds_are_gone():
    """Source-level check: the pre-M-13 thresholds ("< 3", "3-5", "5-8",
    "8-12", "12+") must not survive anywhere in pick_score_bucket. If the
    old copy ever gets resurrected by a bad rebase, the report will go
    silent (every real pick -> "12+").
    """
    src = (HERE.parent / "engine" / "analyze_picks.py").read_text(encoding="utf-8")
    # Pull just the function body.
    m = re.search(
        r"def pick_score_bucket\(ps\):.*?(?=\n(?:def |class |\Z))",
        src, re.DOTALL,
    )
    assert m, "pick_score_bucket not found - test harness out of sync"
    body = m.group(0)
    assert '"< 3"' not in body
    assert '"3-5"' not in body
    assert '"5-8"' not in body
    assert '"8-12"' not in body
    assert '"12+"' not in body


# ─────────────────────────────────────────────────────────────────
# Shared schema sanity — these three enums share upstream assumptions
# ─────────────────────────────────────────────────────────────────

def test_game_line_stats_matches_between_grade_picks_and_weekly_recap():
    """grade_picks and weekly_recap each carry their own GAME_LINE_STATS
    set. They serve slightly different purposes (grading vs. labeling)
    but PARLAY-as-game-line must agree between them - otherwise a pick
    grades fine but its recap label is garbage (or vice versa).

    grade_picks does NOT need PARLAY in GAME_LINE_STATS (daily_lay rows
    take a separate grading path via grade_daily_lay), but weekly_recap
    DOES, because _pick_short_label is the final rendering step.
    """
    from weekly_recap import GAME_LINE_STATS as wr_stats
    from grade_picks import GAME_LINE_STATS as gp_stats
    # weekly_recap is a superset of grade_picks (it adds PARLAY).
    assert gp_stats <= wr_stats, (
        f"weekly_recap.GAME_LINE_STATS is missing grade_picks entries: "
        f"{gp_stats - wr_stats}"
    )
    # PARLAY lives in weekly_recap only.
    assert "PARLAY" in wr_stats
    assert "PARLAY" not in gp_stats
