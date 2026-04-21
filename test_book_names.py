#!/usr/bin/env python3
"""Regression tests for audit H-13 — book-name normalization contract.

Before consolidation, run_picks.py, capture_clv.py, grade_picks.py, and
weekly_recap.py each defined their own BOOK_DISPLAY dict. run_picks.py was
missing 6 CO-legal book entries (pointsbetus, tipico, wynnbet, bet365,
twinspires, circasports). These tests lock in the single-source-of-truth.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "engine"))


# ─────────────────────────────────────────────────────────────────
# Canonical module invariants
# ─────────────────────────────────────────────────────────────────

def test_co_legal_books_has_18_entries():
    from book_names import CO_LEGAL_BOOKS
    assert len(CO_LEGAL_BOOKS) == 18, (
        f"CO_LEGAL_BOOKS must stay at 18 books; got {len(CO_LEGAL_BOOKS)}"
    )


def test_every_co_book_has_a_display_name():
    from book_names import CO_LEGAL_BOOKS, BOOK_DISPLAY
    missing = CO_LEGAL_BOOKS - set(BOOK_DISPLAY.keys())
    assert not missing, f"CO books missing display entries: {missing}"


def test_espnbet_maps_to_thescore_bet():
    """Non-negotiable: espnbet API key always renders as 'theScore Bet'."""
    from book_names import display_book, BOOK_DISPLAY
    assert BOOK_DISPLAY["espnbet"] == "theScore Bet"
    assert display_book("espnbet") == "theScore Bet"


def test_region_suffix_stripped():
    from book_names import display_book, norm_book
    # Display: hardrockbet_fl → Hard Rock Bet
    assert display_book("hardrockbet_fl") == "Hard Rock Bet"
    assert display_book("hardrockbet_az") == "Hard Rock Bet"
    # Norm: hardrockbet_fl → hardrockbet (base key)
    assert norm_book("hardrockbet_fl") == "hardrockbet"
    assert norm_book("draftkings_co") == "draftkings"


def test_norm_book_preserves_offshore_keys():
    """Don't strip suffixes for non-CO books (e.g. unibet_us stays as-is)."""
    from book_names import norm_book
    assert norm_book("unibet_us") == "unibet_us"


def test_empty_key_handled():
    from book_names import display_book, norm_book
    assert display_book("") == ""
    assert display_book(None) == ""
    assert norm_book("") == ""
    assert norm_book(None) is None


def test_unknown_book_falls_back_to_title():
    from book_names import display_book
    assert display_book("somenewbook") == "Somenewbook"


# ─────────────────────────────────────────────────────────────────
# No-drift tests — every consumer module must agree with book_names
# ─────────────────────────────────────────────────────────────────

def test_run_picks_reexports_canonical_definitions():
    import run_picks
    import book_names
    assert run_picks.CO_LEGAL_BOOKS is book_names.CO_LEGAL_BOOKS
    assert run_picks.BOOK_DISPLAY is book_names.BOOK_DISPLAY
    assert run_picks.display_book is book_names.display_book


def test_capture_clv_reexports_canonical_definitions():
    import capture_clv
    import book_names
    assert capture_clv.CO_LEGAL_BOOKS is book_names.CO_LEGAL_BOOKS
    assert capture_clv.BOOK_DISPLAY is book_names.BOOK_DISPLAY
    assert capture_clv.display_book is book_names.display_book


def test_grade_picks_reexports_canonical_definitions():
    import grade_picks
    import book_names
    # _BOOK_DISPLAY is kept as a backwards-compat alias
    assert grade_picks._BOOK_DISPLAY is book_names.BOOK_DISPLAY
    assert grade_picks.display_book is book_names.display_book


def test_weekly_recap_reexports_canonical_definitions():
    import weekly_recap
    import book_names
    assert weekly_recap._BOOK_DISPLAY is book_names.BOOK_DISPLAY
    assert weekly_recap.display_book is book_names.display_book


# ─────────────────────────────────────────────────────────────────
# Regression: previously-missing books now render correctly
# ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("api_key,expected", [
    ("pointsbetus",  "PointsBet"),
    ("tipico",       "Tipico"),
    ("wynnbet",      "WynnBET"),
    ("bet365",       "bet365"),
    ("twinspires",   "TwinSpires"),
    ("circasports",  "Circa"),
])
def test_previously_missing_books_now_display(api_key, expected):
    """The 6 CO-legal books run_picks.py used to omit now render correctly."""
    from book_names import display_book
    assert display_book(api_key) == expected


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
