"""name_utils.py — canonical player-name folding contract.

Audit H-3, closed Apr 20 2026. Before this consolidation:

  - ``run_picks.normalize_name`` used NFKD + ASCII-encode → accent-stripped,
    lowercased, punctuation removed.
  - ``grade_picks._norm`` just lowercased + kept alnum+space. It did NOT strip
    accents, so ``"Doncic"`` and ``"Dončić"`` did not compare equal.

Consequence: a pick logged as ``Luka Dončić`` never matched the Odds API's
``Luka Doncic`` (or vice-versa) inside the grader, so that pick stayed
ungraded forever — blank ``result``, never counted in the weekly recap,
silently missing from the ledger summary.

This module is the single source of truth. Every caller that compares
player names (cooldown filter, grader, analyze_picks, future reports)
imports ``fold_name`` from here.

Contract:
  * Accents / combining marks are stripped (NFKD + ASCII filter) so
    ``"Dončić"`` → ``"doncic"`` matches ``"Doncic"`` → ``"doncic"``.
  * Case is lowered.
  * Anything that isn't ``[a-z\\s]`` after folding is removed. Apostrophes,
    periods, commas, hyphens — all gone. ``"D'Angelo Russell"`` →
    ``"dangelo russell"``.
  * Leading/trailing whitespace trimmed.

Do NOT add alternate helpers that "also" normalize names. If a caller needs
extra shaping, wrap ``fold_name``.
"""

from __future__ import annotations

import re
import unicodedata

__all__ = ["fold_name", "name_key"]

# Pre-compile the character filter — called on every ledger/API row during
# grading. Cheap but runs a lot.
_ALLOWED = re.compile(r"[^a-z\s]")

# Suffix tokens dropped before extracting last name, so ``"Jaren Jackson Jr."``
# folds to last name ``"jackson"`` not ``"jr"``. Must stay in sync with the
# set used by ``grade_picks.py`` fuzzy-match. Kept here so there's exactly
# one source.
_SUFFIXES: frozenset[str] = frozenset({"jr", "sr", "ii", "iii", "iv", "v"})


def fold_name(name: str | None) -> str:
    """Canonical folded form of a player name for matching.

    Returns an empty string for ``None`` or any non-string input (defensive
    — callers can always `if fold_name(x):` to gate).
    """
    if name is None:
        return ""
    if not isinstance(name, str):
        try:
            name = str(name)
        except Exception:  # pragma: no cover — defensive
            return ""
    # NFKD + ASCII-strip kills combining marks: "Dončić" → "Doncic",
    # "Łuka" → "Luka", full-width digits → ASCII digits, etc.
    folded = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    folded = folded.strip().lower()
    # Drop anything that isn't a letter or whitespace. Collapse runs of
    # whitespace so "Luka   Doncic" folds identically to "Luka Doncic".
    folded = _ALLOWED.sub("", folded)
    folded = " ".join(folded.split())
    return folded


def name_key(name: str | None) -> str:
    """Short fuzzy-match key: ``"lastname_firstN"``.

    Drops Jr/Sr/II/III/IV/V suffixes so ``"Jaren Jackson Jr."`` →
    ``"jackson_jar"`` not ``"jr_jar"``. For one-token inputs returns the
    full folded form so the key is still deterministic.
    """
    folded = fold_name(name)
    if not folded:
        return ""
    parts = folded.split()
    if len(parts) < 2:
        return folded
    # Drop trailing suffixes: handle up to 2 stacked (e.g. "John Smith III Jr").
    while len(parts) > 2 and parts[-1] in _SUFFIXES:
        parts.pop()
    first = parts[0][:3]
    last = parts[-1]
    return f"{last}_{first}"
