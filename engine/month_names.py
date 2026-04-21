"""Locale-independent English month names.

Audit M-22 (closed Apr 20 2026).

`calendar.month_name` is locale-sensitive — on a non-en-US Windows install
it returns localized strings ("Avril" instead of "April"), which looks
wrong in a public Discord post. picksbyjonny is an English-language brand
and every customer-facing surface must speak English regardless of the
host's locale.

Rather than hoping every environment has `LC_ALL=en_US.UTF-8`, we use a
hardcoded tuple. Callers index by the 1-based calendar month (1..12) to
match `calendar.month_name`'s API:

    >>> from month_names import MONTH_NAMES
    >>> MONTH_NAMES[4]
    'April'

The tuple has a leading empty string at index 0 so `MONTH_NAMES[month]`
works without the `- 1` offset that would otherwise hide off-by-one bugs.

Do NOT swap this for an upstream dict or i18n lookup — the whole point of
this module is to guarantee English regardless of environment.
"""

from __future__ import annotations

# Index 0 is an empty placeholder so month 1..12 maps 1:1.
MONTH_NAMES: tuple[str, ...] = (
    "",
    "January",   "February", "March",     "April",
    "May",       "June",     "July",      "August",
    "September", "October",  "November",  "December",
)

MONTH_NAMES_SHORT: tuple[str, ...] = (
    "",
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
)


def month_name(month: int) -> str:
    """Return the English name for a calendar month (1..12).

    Raises ``ValueError`` for out-of-range input — fail loud, because a
    silently-wrong month on the monthly summary post would be confusing.
    """
    if not isinstance(month, int) or month < 1 or month > 12:
        raise ValueError(f"month must be an int in 1..12, got {month!r}")
    return MONTH_NAMES[month]


def month_name_short(month: int) -> str:
    """Return the 3-letter English name for a calendar month (1..12)."""
    if not isinstance(month, int) or month < 1 or month > 12:
        raise ValueError(f"month must be an int in 1..12, got {month!r}")
    return MONTH_NAMES_SHORT[month]
