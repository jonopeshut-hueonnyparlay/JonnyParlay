"""American-odds / probability conversions and vig removal.

Pure functions (no stdlib deps beyond arithmetic). Canonical home for the odds
math that was previously duplicated across run_picks.py and the SGP builders.

Note: capture_clv.py and clv_report.py intentionally keep their own implied_prob
*variants* with extra None-handling for non-numeric inputs — different behavior,
not consolidated here.
"""


def implied_prob(odds):
    """American odds → implied probability."""
    if odds == 0:
        return 0.0
    if odds < 0:
        return abs(odds) / (abs(odds) + 100.0)
    else:
        return 100.0 / (odds + 100.0)


def no_vig(imp1, imp2):
    """Remove vig from two-sided implied probs."""
    total = imp1 + imp2
    if total == 0:
        return 0.5, 0.5
    return imp1 / total, imp2 / total


def is_decimal_leak(odds):
    """Check if odds look like decimal format leaked through.
    Range 1.0 < odds < 2.5 catches decimal (e.g. 1.91 for -110).
    Upper bound is 2.5 (not 3.0) to avoid rejecting valid +100 to +149 American odds,
    whose decimal equivalents are 2.0–2.49.
    """
    return 1.0 < odds < 2.5


def prob_to_american(prob):
    """Convert probability to American odds."""
    if prob <= 0 or prob >= 1:
        return 0
    if prob >= 0.5:
        return -(prob / (1.0 - prob)) * 100
    else:
        return ((1.0 - prob) / prob) * 100


def american_to_decimal(odds):
    return 1 + odds / 100 if odds > 0 else 1 + 100 / abs(odds)


def decimal_to_american(dec):
    if dec >= 2.0:
        return int(round((dec - 1) * 100))
    else:
        return int(round(-100 / (dec - 1)))
