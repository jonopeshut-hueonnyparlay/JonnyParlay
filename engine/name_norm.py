"""Player-name normalization for matching.

Extracted from run_picks.py (extract-and-re-export refactor, Step 1.5) and
re-imported there so existing call sites and `from run_picks import ...` keep
resolving. Imports only {name_utils} — never run_picks or the other extracted
modules.
"""
from name_utils import fold_name as _fold_name


def normalize_name(name):
    """Normalize a player name for matching.

    Thin wrapper around :func:`name_utils.fold_name` — the canonical folding
    contract lives there so the grader, analyzer, and this module all agree
    on whether ``"Dončić"`` == ``"Doncic"`` (it does — accents stripped).
    Audit H-3.
    """
    return _fold_name(name)
