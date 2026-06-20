"""Tests for the optional threshold override loader (audit S4f-X).

The override path is dormant by default (no config/thresholds.toml), so importing
thresholds yields the documented defaults — verified here — and replay stays
byte-identical. The whitelist/coercion guards are tested on the pure helpers so we
never mutate the real module globals.
"""

from __future__ import annotations

import pytest

import thresholds as T


# ── defaults intact (no config => no overrides) ──────────────────────────────
def test_defaults_unchanged_without_config():
    assert T.MIN_PICK_SCORE == 15
    assert T.MIN_WIN_PROB == 0.50
    assert T.KELLY_FRACTION == 6.0
    assert T._THRESHOLD_OVERRIDES == {}   # nothing applied on a clean checkout


# ── _coerce_override type handling ───────────────────────────────────────────
@pytest.mark.parametrize("current,new,expected", [
    (15, 20, 20),            # int <- int
    (15, 20.0, 20),          # int <- integer-valued float
    (15, 20.5, None),        # int <- non-integer float rejected
    (3.0, 5, 5.0),           # float <- int promoted
    (0.50, 0.55, 0.55),      # float <- float
    (0.50, "high", None),    # float <- str rejected
    ("raw", "logit", "logit"),  # str <- str
    (15, True, None),        # int <- bool rejected (bool is not a number here)
])
def test_coerce_override(current, new, expected):
    got = T._coerce_override(current, new)
    assert got == expected
    if expected is not None:
        assert type(got) is type(current)   # type preserved


# ── _apply_overrides whitelist + existence + type guards ─────────────────────
def test_apply_overrides_only_whitelisted_scalars():
    ns = {"MIN_PICK_SCORE": 15, "KELLY_FRACTION": 6.0, "MIN_WIN_PROB": 0.50}
    applied = T._apply_overrides(
        ns,
        {
            "MIN_PICK_SCORE": 25,        # whitelisted -> applied
            "MIN_WIN_PROB": 0.55,        # whitelisted -> applied
            "KELLY_FRACTION": 3.0,       # frozen (not in _TUNABLE) -> ignored
            "NONSENSE_KEY": 1,           # unknown -> ignored
        },
    )
    assert applied == {"MIN_PICK_SCORE": 25, "MIN_WIN_PROB": 0.55}
    assert ns["MIN_PICK_SCORE"] == 25 and ns["MIN_WIN_PROB"] == 0.55
    assert ns["KELLY_FRACTION"] == 6.0   # untouched


def test_apply_overrides_rejects_bad_types_and_missing_names():
    ns = {"KILLSHOT_SIZE_BASE": 3.0, "MIN_PICK_SCORE": 15}
    applied = T._apply_overrides(
        ns,
        {
            "KILLSHOT_SIZE_BASE": 5,     # int -> float ok
            "MIN_PICK_SCORE": "lots",    # bad type -> ignored
            "WNBA_OPENING_GATE_DAYS": 4, # whitelisted but absent from this ns -> ignored
        },
    )
    assert applied == {"KILLSHOT_SIZE_BASE": 5.0}
    assert ns["KILLSHOT_SIZE_BASE"] == 5.0 and type(ns["KILLSHOT_SIZE_BASE"]) is float
    assert ns["MIN_PICK_SCORE"] == 15


def test_frozen_constants_not_in_tunable_set():
    for frozen in ("KELLY_FRACTION", "F5_SCALAR", "BM_SHRINKAGE_DEFAULT", "PLATT_SPACE",
                   "BLEND_ALPHA", "DEFAULT_MARKET_MULT", "WNBA_EV_FLOOR"):
        assert frozen not in T._TUNABLE


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
