"""Canonical pick-label formatters.

Every place in the codebase that wants to render a pick_log row as human
text should import from this module. Rolling all label logic through one
helper set avoids the drift the Section 37 audit flagged (L-3): the
weekly recap had ``_pick_short_label`` inlined in ``weekly_recap.py`` and
the backtest dashboard had its own one-liner formatter inlined in
``analyze_picks.py``. When MLB brought PARLAY rows into the ledger, only
the recap version was taught to handle them — the analyzer happily
rendered "Daily Lay 3-leg  PARLAY" as though it were a prop.

Two canonical shapes:

* :func:`short_label` — compact Discord-card form (``MAVS -4.5``,
  ``Total OVER 220.5``, ``LAST OVER 8.5 PTS``). Used by the weekly recap
  embed and xlsx, and anywhere a pick has to fit on one embed line.
* :func:`detail_line` — long backtest-report form
  (``PlayerName direction line stat (sport) @ odds``). Used by the Top
  10 / Worst 10 blocks in ``analyze_picks``.

Both know the same ``GAME_LINE_STATS`` set — which, per the weekly recap
invariant, must stay a *superset* of ``grade_picks.GAME_LINE_STATS``.
"""
from __future__ import annotations

from typing import Any, Mapping

# Stats that represent a team / game line rather than an individual prop.
# Must stay a superset of ``grade_picks.GAME_LINE_STATS`` — if the grader
# recognizes a stat as a game line but a label formatter doesn't, a legit
# pick grades cleanly and then renders as a garbled prop line.
#
# PARLAY is included (audit M-12, closed Apr 20 2026) because a daily_lay
# row logs one aggregate PARLAY row per day with an empty / descriptive
# ``player`` field — treating it as a prop produced garbage output like
# "3-LEG COVER  PARLAY".
GAME_LINE_STATS: frozenset[str] = frozenset({
    "TOTAL", "SPREAD", "TEAM_TOTAL", "ML_FAV", "ML_DOG",
    "F5_TOTAL", "F5_SPREAD", "F5_ML", "NRFI", "YRFI",
    "GOLF_WIN", "PARLAY",
})


def _fmt_odds(odds: Any) -> str:
    """Render American odds with an explicit sign, or '' if unparseable."""
    s = str(odds or "").strip()
    if not s:
        return ""
    try:
        o = int(float(s.replace("+", "")))
    except (ValueError, TypeError):
        return s  # already formatted or junk — pass through untouched
    return f"+{o}" if o > 0 else f"{o}"


def short_label(p: Mapping[str, Any]) -> str:
    """Compact Discord-card label for a pick_log row.

    Returns strings like:

    * ``"Mavericks -4.5"`` (SPREAD)
    * ``"Mavericks ML"`` (ML_FAV / ML_DOG)
    * ``"Total OVER 220.5"`` (TOTAL)
    * ``"Daily Lay 3-leg @ +540"`` (PARLAY — uses player + odds)
    * ``"CURRY OVER 3.5 3PM"`` (prop — player last name + dir + line + stat)

    The prop branch uses the player's *last* token so an embed line stays
    short for two-word names ("Stephen Curry" → ``CURRY``). If the player
    field is empty it degrades gracefully to ``OVER 3.5 3PM`` rather than
    raising.
    """
    stat = (p.get("stat") or "").strip()
    if stat in GAME_LINE_STATS:
        team = (p.get("player") or p.get("team") or "").strip()
        dir_ = (p.get("direction") or "").strip().upper()
        line = (p.get("line") or "").strip()
        if stat == "SPREAD":
            return f"{team} {line}".strip()
        if stat in ("ML_FAV", "ML_DOG"):
            return f"{team} ML".strip()
        if stat == "TOTAL":
            return f"Total {dir_} {line}".strip()
        if stat == "PARLAY":
            # Audit M-12: aggregate daily_lay row. `player` is shaped like
            # "Daily Lay 3-leg" and `odds` carries the parlay price. Prefer
            # the player string as the primary identifier and tack on odds
            # when present so the label reads as a single comprehensible
            # line (e.g. "Daily Lay 3-leg @ +540").
            label = (p.get("player") or "Daily Lay").strip()
            odds = (p.get("odds") or "").strip()
            return f"{label} @ {odds}" if odds else label
        return f"{team} {stat} {dir_} {line}".strip()
    # Prop branch.
    player = (p.get("player") or "").strip()
    last = (player.split() or [""])[-1].upper()
    dir_ = (p.get("direction") or "").strip().upper()
    line = (p.get("line") or "").strip()
    return f"{last} {dir_} {line} {stat}".strip()


def detail_line(p: Mapping[str, Any]) -> str:
    """Long backtest-report label:
    ``PlayerName direction line stat (sport) @ odds``.

    Used by the Top 10 / Worst 10 blocks in ``analyze_picks``. The caller
    is responsible for prefixing unit P&L; this helper only builds the
    descriptor so a new stat type doesn't have to be taught to the
    analyzer separately from the recap.
    """
    player = (p.get("player") or "").strip()
    direction = (p.get("direction") or "").strip()
    line = (p.get("line") or "").strip()
    stat = (p.get("stat") or "").strip()
    sport = (p.get("sport") or "").strip()
    odds = _fmt_odds(p.get("odds"))
    core = f"{player} {direction} {line} {stat}".strip()
    tail = f"({sport})"
    if odds:
        return f"{core} {tail} @ {odds}"
    return f"{core} {tail}"


__all__ = ["GAME_LINE_STATS", "short_label", "detail_line"]
