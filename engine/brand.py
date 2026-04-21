"""Centralized picksbyjonny brand constants.

Audit L-7 (closed Apr 21 2026): the tagline "edge > everything" was
hardcoded across 30+ call sites spanning run_picks, grade_picks,
weekly_recap, morning_preview, results_graphic, and post_nrfi_bonus.
If the brand ever evolves, we want ONE edit to change it — not a
grep-and-pray sweep. This module is the single source of truth.

Audit L-1 (closed Apr 21 2026): sport emoji were also scattered across
morning_preview and weekly_recap with inconsistent mappings. SPORT_EMOJI
is the canonical lookup. Downstream code should prefer
`SPORT_EMOJI.get(sport, "")` over inline `{"NBA":"🏀",...}` dicts.

Import pattern:
    from brand import BRAND_TAGLINE, SPORT_EMOJI
    footer = {"text": f"{date} · {BRAND_TAGLINE}"}

This module has ZERO side effects and no third-party imports — safe to
import from anywhere, including hot paths like the CLV daemon.
"""
from __future__ import annotations

# The tagline. Keep the " > " as ASCII greater-than (NOT the Unicode ≻ or »)
# so it renders identically in Discord, console, and PNG graphic contexts.
BRAND_TAGLINE: str = "edge > everything"

# Brand handle — used in results_graphic and the weekly recap footer line.
BRAND_HANDLE: str = "picksbyjonny"

# Canonical sport → emoji mapping. Consolidates two separate dicts that
# previously lived in morning_preview.py and weekly_recap.py. Add new
# sports here, not in-line at call sites.
SPORT_EMOJI: dict[str, str] = {
    "NBA":   "🏀",
    "NHL":   "🏒",
    "NFL":   "🏈",
    "MLB":   "⚾",
    "NCAAB": "🏀",
    "NCAAF": "🏈",
    "MLS":   "⚽",
    "PGA":   "⛳",
    "WNBA":  "🏀",
}

__all__ = ["BRAND_TAGLINE", "BRAND_HANDLE", "SPORT_EMOJI"]
