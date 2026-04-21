"""book_names.py — canonical sportsbook key/display/normalization contract.

Single source of truth for:
  - CO_LEGAL_BOOKS: the 18 Colorado-approved sportsbook keys (line-shopping filter)
  - BOOK_DISPLAY:   API key → clean display name used in Discord/IG output
  - norm_book():    strip region suffix (e.g. hardrockbet_fl → hardrockbet)
  - display_book(): API key → display name with region-suffix fallback

Audit H-13, closed Apr 20 2026. Before this consolidation, run_picks.py,
capture_clv.py, grade_picks.py, and weekly_recap.py each defined their own
BOOK_DISPLAY dict. run_picks.py was missing entries for pointsbetus, tipico,
wynnbet, bet365, twinspires, circasports — causing Discord cards to render
raw API keys instead of friendly names for those 6 CO-legal books.

Every module that emits a book name in any user-visible output MUST import
from here. No other module should define BOOK_DISPLAY or display_book.
"""

# ── CO-legal sportsbooks (line-shopping filter) ──────────────────────────────
# Eighteen books approved for Colorado. API key "espnbet" maps to
# "theScore Bet" (they rebranded under the API's old key).
CO_LEGAL_BOOKS = frozenset({
    "draftkings", "fanduel", "betmgm", "williamhill_us", "betrivers",
    "bet365", "fanatics", "hardrockbet", "ballybet", "betparx",
    "espnbet", "pointsbetus", "twinspires", "circasports", "superbook",
    "tipico", "wynnbet", "betway",
})

# ── Display names — CO books ─────────────────────────────────────────────────
_CO_DISPLAY = {
    "espnbet":        "theScore Bet",
    "hardrockbet":    "Hard Rock Bet",
    "draftkings":     "DraftKings",
    "fanduel":        "FanDuel",
    "williamhill_us": "Caesars",
    "betmgm":         "BetMGM",
    "betrivers":      "BetRivers",
    "ballybet":       "Bally Bet",
    "betparx":        "BetParx",
    "pointsbetus":    "PointsBet",
    "bet365":         "bet365",
    "fanatics":       "Fanatics",
    "twinspires":     "TwinSpires",
    "circasports":    "Circa",
    "superbook":      "SuperBook",
    "tipico":         "Tipico",
    "wynnbet":        "WynnBET",
    "betway":         "Betway",
}

# ── Display names — sharp / offshore / exchange / other non-CO books ─────────
# Used by CLV comparison and historical analysis. These are NOT in
# CO_LEGAL_BOOKS, but they appear in Odds API responses and need clean names.
_OTHER_DISPLAY = {
    "unibet_us":     "Unibet",
    "lowvig":        "LowVig",
    "novig":         "Novig",
    "betonlineag":   "BetOnline",
    "mybookieag":    "MyBookie",
    "pinnacle":      "Pinnacle",
    "fliff":         "Fliff",
    "betus":         "BetUS",
    "bovada":        "Bovada",
    "betanysports":  "BetAnySports",
    "rebet":         "ReBet",
    "betopenly":     "BetOpenly",
    "kalshi":        "Kalshi",
    "polymarket":    "Polymarket",
    "prophetx":      "ProphetX",
}

BOOK_DISPLAY = {**_CO_DISPLAY, **_OTHER_DISPLAY}

# Invariant: every CO book has a display entry.
assert CO_LEGAL_BOOKS.issubset(BOOK_DISPLAY.keys()), (
    "book_names.py invariant broken: CO_LEGAL_BOOKS not a subset of BOOK_DISPLAY. "
    f"Missing: {CO_LEGAL_BOOKS - BOOK_DISPLAY.keys()}"
)


def norm_book(key):
    """Normalize book key by stripping region suffix (hardrockbet_fl → hardrockbet).

    Only strips if the stripped result is a known CO book — otherwise returns
    the key unchanged (so offshore/sharp keys aren't mangled).
    """
    if not key:
        return key
    base = key.rsplit("_", 1)[0] if "_" in key else key
    return base if base in CO_LEGAL_BOOKS else key


def display_book(key):
    """API book key → clean display name. Strips region suffix as fallback.

    If neither the key nor its base variant are known, returns key.title() so
    new Odds API books render with a reasonable display instead of leaking
    raw API keys into user-facing output.
    """
    if not key:
        return ""
    k = key.lower()
    if k in BOOK_DISPLAY:
        return BOOK_DISPLAY[k]
    base = k.rsplit("_", 1)[0] if "_" in k else k
    if base in BOOK_DISPLAY:
        return BOOK_DISPLAY[base]
    return key.title()


__all__ = [
    "CO_LEGAL_BOOKS",
    "BOOK_DISPLAY",
    "norm_book",
    "display_book",
]
