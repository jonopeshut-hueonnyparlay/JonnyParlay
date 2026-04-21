#!/usr/bin/env python3
"""Regression tests for Section 21 — grader correctness.

Covers:
  H-3   Canonical name folding (fold_name, name_key) unifies ``Dončić`` ↔
        ``Doncic`` across the grader, run_picks cooldown, and reports.
  H-4   Ambiguous 2-letter team codes (``LA``, ``NY``, ``SF``, ``SD``) are
        refused rather than best-guessed. grade_game_line returns None for
        SPREAD / ML / F5_SPREAD / F5_ML / TEAM_TOTAL on ambiguous codes, and
        grade_daily_lay drops the whole parlay as ungraded.
  H-5   compute_pl treats ``VOID`` identically to ``P``. daily_stats
        excludes VOID from the ``risked`` denominator and counts VOID +
        push together.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "engine"))


# ─────────────────────────────────────────────────────────────────
# H-3 — canonical name folding
# ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("a,b", [
    ("Luka Dončić",            "Luka Doncic"),
    ("Nikola Jokić",           "Nikola Jokic"),
    ("  Doncic  ",             "Doncic"),
    ("LUKA DONCIC",            "luka doncic"),
    ("D'Angelo Russell",       "DAngelo Russell"),
    ("Ja Morant",              "Ja   Morant"),
    ("Jokić",                  "JOKIC"),
    ("José Alvarado",          "Jose Alvarado"),
    ("Goran Dragić",           "Goran Dragic"),
])
def test_fold_name_equivalences(a, b):
    """Audit H-3: the whole point. Accented and unaccented, punctuated and
    clean, uppercase and lowercase — all must collapse to the same key.
    Without this, a pick logged as 'Luka Dončić' was never matched against
    the Odds API's 'Luka Doncic' and stayed ungraded forever.
    """
    from name_utils import fold_name
    assert fold_name(a) == fold_name(b), f"{a!r} folded to {fold_name(a)!r}; expected same as {b!r} → {fold_name(b)!r}"


@pytest.mark.parametrize("raw,expected", [
    ("Luka Dončić",       "doncic_luk"),
    ("Luka Doncic",       "doncic_luk"),
    ("Jaren Jackson Jr.", "jackson_jar"),
    ("Jaren Jackson Jr",  "jackson_jar"),
    ("Jaren Jackson II",  "jackson_jar"),
    ("Ja Morant",         "morant_ja"),
    ("D'Angelo Russell",  "russell_dan"),
    ("LeBron",            "lebron"),       # single token → full folded form
])
def test_name_key_format(raw, expected):
    from name_utils import name_key
    assert name_key(raw) == expected


def test_fold_name_handles_none_and_non_strings():
    from name_utils import fold_name
    assert fold_name(None) == ""
    assert fold_name("") == ""
    # Non-string inputs coerce via str() — all letters survive, digits/symbols
    # are stripped. The key property is that the function never raises.
    assert fold_name(123) == ""        # str(123) = "123" → digits stripped → ""
    # Exotic input must not crash; we only assert it returns a str.
    assert isinstance(fold_name({"nope": 1}), str)
    assert isinstance(fold_name([1, 2, 3]), str)


def test_grade_picks_norm_delegates_to_fold_name():
    """The grader's internal `_norm` was the accent-stripping bug site.
    It must now route through fold_name so 'Dončić' matches 'Doncic'.
    """
    from name_utils import fold_name
    # _norm is defined inside a function body in grade_picks — exercise
    # it via the public surface instead: _match_players_to_games uses it.
    # We just verify the module imports fold_name as _fold_name.
    import grade_picks
    assert grade_picks._fold_name is fold_name


# ─────────────────────────────────────────────────────────────────
# H-4 — ambiguous team codes
# ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("code", ["LA", "NY", "SF", "SD", "la", "  ny  ", "Sf"])
def test_is_ambiguous_team_code_true(code):
    from grade_picks import is_ambiguous_team_code
    assert is_ambiguous_team_code(code) is True


@pytest.mark.parametrize("code", [
    "LAL", "LAC", "NYK", "BKN", "BOS", "OKC", "GSW",
    "", None, "   ", "ATL",
])
def test_is_ambiguous_team_code_false(code):
    from grade_picks import is_ambiguous_team_code
    assert is_ambiguous_team_code(code) is False


def test_describe_team_ambiguity_lists_candidates():
    from grade_picks import describe_team_ambiguity
    msg = describe_team_ambiguity("LA")
    assert "LAL" in msg and "LAC" in msg
    assert "3-letter" in msg

    msg_ny = describe_team_ambiguity("NY")
    assert "NYK" in msg_ny and "BKN" in msg_ny


def test_describe_team_ambiguity_blank_and_unknown():
    from grade_picks import describe_team_ambiguity
    assert describe_team_ambiguity("") == ""
    assert describe_team_ambiguity(None) == ""
    # Known ambiguous but no candidate list → still produces a warning
    msg = describe_team_ambiguity("SF")
    assert "SF" in msg and "3-letter" in msg


def test_grade_game_line_spread_ambiguous_returns_none():
    """H-4: a legacy SPREAD row with team 'LA' and no is_home field must
    NOT best-guess against Lakers/Clippers. It must stay ungraded.
    """
    from grade_picks import grade_game_line
    pick = {
        "stat": "SPREAD",
        "game": "Denver Nuggets @ Los Angeles Lakers",
        "direction": "over",
        "line": "-3.5",
        "team": "LA",           # ambiguous — could be Lakers OR Clippers
        "player": "",
        "is_home": "",          # legacy row, no is_home flag
    }
    scores = {
        "Denver Nuggets @ Los Angeles Lakers": {
            "home_team": "Los Angeles Lakers",
            "away_team": "Denver Nuggets",
            "scores": [
                {"name": "Los Angeles Lakers", "score": "115"},
                {"name": "Denver Nuggets",     "score": "110"},
            ],
            "completed": True,
        }
    }
    assert grade_game_line(pick, scores) is None


def test_grade_game_line_spread_unambiguous_still_grades():
    """Sanity: LAL (unambiguous) continues to grade normally — we only
    broke the best-guess path for 2-letter codes.
    """
    from grade_picks import grade_game_line
    pick = {
        "stat": "SPREAD",
        "game": "Denver Nuggets @ Los Angeles Lakers",
        "direction": "over",
        "line": "-3.5",
        "team": "LAL",
        "player": "",
        "is_home": "True",   # modern row
    }
    scores = {
        "Denver Nuggets @ Los Angeles Lakers": {
            "home_team": "Los Angeles Lakers",
            "away_team": "Denver Nuggets",
            "scores": [
                {"name": "Los Angeles Lakers", "score": "115"},
                {"name": "Denver Nuggets",     "score": "110"},
            ],
            "completed": True,
        }
    }
    # Home team won by 5, spread -3.5 → covered → W
    assert grade_game_line(pick, scores) == "W"


def test_grade_game_line_ml_ambiguous_returns_none():
    from grade_picks import grade_game_line
    pick = {
        "stat": "ML_FAV",
        "game": "Denver Nuggets @ Los Angeles Lakers",
        "direction": "",
        "line": "0",
        "team": "LA",
        "player": "",
        "is_home": "",
    }
    scores = {
        "Denver Nuggets @ Los Angeles Lakers": {
            "home_team": "Los Angeles Lakers",
            "away_team": "Denver Nuggets",
            "scores": [
                {"name": "Los Angeles Lakers", "score": "115"},
                {"name": "Denver Nuggets",     "score": "110"},
            ],
            "completed": True,
        }
    }
    assert grade_game_line(pick, scores) is None


def test_grade_game_line_team_total_ambiguous_returns_none():
    from grade_picks import grade_game_line
    pick = {
        "stat": "TEAM_TOTAL",
        "game": "Denver Nuggets @ Los Angeles Lakers",
        "direction": "over",
        "line": "112.5",
        "team": "LA",
        "player": "",
        "is_home": "",
    }
    scores = {
        "Denver Nuggets @ Los Angeles Lakers": {
            "home_team": "Los Angeles Lakers",
            "away_team": "Denver Nuggets",
            "scores": [
                {"name": "Los Angeles Lakers", "score": "115"},
                {"name": "Denver Nuggets",     "score": "110"},
            ],
            "completed": True,
        }
    }
    assert grade_game_line(pick, scores) is None


def test_resolve_pick_is_home_ambiguous_returns_none():
    """Unit test of the helper directly."""
    from grade_picks import _resolve_pick_is_home
    pick = {"team": "LA", "player": "", "is_home": ""}
    assert _resolve_pick_is_home(pick, "Los Angeles Lakers") is None


def test_resolve_pick_is_home_modern_row_ignores_ambiguity():
    """When is_home is populated, we don't care about team-code ambiguity."""
    from grade_picks import _resolve_pick_is_home
    pick = {"team": "LA", "player": "", "is_home": "False"}
    assert _resolve_pick_is_home(pick, "Los Angeles Lakers") is False


def test_grade_daily_lay_ambiguous_leg_returns_none():
    from grade_picks import grade_daily_lay
    row = {
        "game": "LA -3.5 / BOS +5.5 / DAL -4.0",
        "date": "2026-04-20",
    }
    all_scores = {
        ("2026-04-20", "NBA"): {
            "Denver Nuggets @ Los Angeles Lakers": {
                "home_team": "Los Angeles Lakers",
                "away_team": "Denver Nuggets",
                "scores": [
                    {"name": "Los Angeles Lakers", "score": "115"},
                    {"name": "Denver Nuggets",     "score": "110"},
                ],
                "completed": True,
            }
        }
    }
    assert grade_daily_lay(row, all_scores) is None


# ─────────────────────────────────────────────────────────────────
# H-5 — VOID result handling in weekly_recap
# ─────────────────────────────────────────────────────────────────

def test_compute_pl_void_returns_zero():
    """VOID must refund exactly like a push — 0 units, no P&L."""
    from weekly_recap import compute_pl
    assert compute_pl(1.0, "-110", "VOID") == 0
    assert compute_pl(2.5, "+150", "VOID") == 0


def test_compute_pl_push_and_void_equivalent():
    """Parity test: compute_pl(..., 'P') must equal compute_pl(..., 'VOID')
    for identical stake/odds — anything else is a regression.
    """
    from weekly_recap import compute_pl
    for size, odds in [(1.0, "-110"), (2.0, "+200"), (0.5, "-250"), (3.0, "+115")]:
        assert compute_pl(size, odds, "P") == compute_pl(size, odds, "VOID"), (
            f"P/VOID diverged for size={size}, odds={odds}"
        )


def test_compute_pl_w_and_l_still_settle_normally():
    """Sanity — we didn't break W/L math while fixing VOID."""
    from weekly_recap import compute_pl
    # -110 at 1u risk → +0.909u on W
    assert compute_pl(1.0, "-110", "W") == pytest.approx(100.0 / 110.0, rel=1e-4)
    # -110 at 1u risk → -1u on L
    assert compute_pl(1.0, "-110", "L") == -1.0
    # +150 at 1u risk → +1.5u on W
    assert compute_pl(1.0, "+150", "W") == pytest.approx(1.5, rel=1e-4)


def test_daily_stats_counts_void_as_push():
    """Daily stats must bucket VOID into the push counter, not Losses.

    ``daily_stats`` returns a 5-tuple ``(w, l, pu, pl, roi)`` — pu is the
    combined push+VOID count.
    """
    from weekly_recap import daily_stats
    picks = [
        {"result": "W",    "size": "1", "odds": "-110", "sport": "NBA", "tier": "T1"},
        {"result": "L",    "size": "1", "odds": "-110", "sport": "NBA", "tier": "T1"},
        {"result": "P",    "size": "1", "odds": "-110", "sport": "NBA", "tier": "T1"},
        {"result": "VOID", "size": "1", "odds": "-110", "sport": "NBA", "tier": "T1"},
    ]
    w, l, pu, pl, roi = daily_stats(picks)
    assert w == 1
    assert l == 1
    # Push count now includes VOID — that's the whole point of H-5.
    assert pu == 2


def test_daily_stats_void_excluded_from_risked():
    """Audit H-5: the VOID stake must not count toward 'risked'. Otherwise
    ROI's denominator is inflated by refunded bets.

    We verify indirectly via ROI: two 1u bets (W at -110, VOID). Net = +0.909u.
    * With correct (H-5) denominator: risked = 1u → ROI = +90.9%.
    * With buggy denominator (VOID counted): risked = 2u → ROI = +45.4%.
    """
    from weekly_recap import daily_stats
    picks = [
        {"result": "W",    "size": "1", "odds": "-110", "sport": "NBA", "tier": "T1"},
        {"result": "VOID", "size": "1", "odds": "-110", "sport": "NBA", "tier": "T1"},
    ]
    w, l, pu, pl, roi = daily_stats(picks)
    # Net P&L from the winning -110 leg.
    assert pl == pytest.approx(round(100.0 / 110.0, 2), abs=0.01)
    # ROI denominator is risked = 1u (NOT 2u); expected ~90.9% not ~45.4%.
    assert roi == pytest.approx(90.9, abs=0.2), (
        f"ROI={roi} — if this is ~45, the VOID stake is still polluting 'risked'."
    )


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
