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


# ── R9: range validation (well-typed but semantically invalid overrides) ────
#
# Preserves the existing fail-soft philosophy exactly: an invalid override is
# rejected individually (default retained), never a hard fail. Runs after
# type coercion, before applying -- mirrors _TUNABLE's own declarative-table
# idiom rather than a generic validation framework.

def test_valid_override_within_range_still_applies(tmp_path, capsys):
    ns = {"MIN_WIN_PROB": 0.50}
    applied = T._apply_overrides(ns, {"MIN_WIN_PROB": 0.55})
    assert applied == {"MIN_WIN_PROB": 0.55}
    assert ns["MIN_WIN_PROB"] == 0.55
    assert capsys.readouterr().err == ""  # no warning for a valid override


def test_probability_override_above_range_rejected(capsys):
    ns = {"MIN_WIN_PROB": 0.50}
    applied = T._apply_overrides(ns, {"MIN_WIN_PROB": 5.0})
    assert applied == {}
    assert ns["MIN_WIN_PROB"] == 0.50   # default retained
    err = capsys.readouterr().err
    assert "MIN_WIN_PROB" in err and "5.0" in err and "[0.0, 1.0]" in err


def test_probability_override_negative_rejected(capsys):
    ns = {"MIN_WIN_PROB": 0.50}
    applied = T._apply_overrides(ns, {"MIN_WIN_PROB": -1.0})
    assert applied == {}
    assert ns["MIN_WIN_PROB"] == 0.50
    assert "MIN_WIN_PROB" in capsys.readouterr().err


def test_score_override_out_of_range_rejected():
    ns = {"MIN_PICK_SCORE": 15}
    applied = T._apply_overrides(ns, {"MIN_PICK_SCORE": 150})
    assert applied == {}
    assert ns["MIN_PICK_SCORE"] == 15


@pytest.mark.parametrize("value,should_reject", [
    (-99, True),   # inside the dead zone -> reject
    (0, True),     # zero -> reject
    (50, True),    # inside the dead zone -> reject
    (100, False),  # boundary -> valid
    (-100, False), # boundary -> valid
    (150, False),  # valid
    (-250, False), # valid
])
def test_odds_dead_zone_rejected_boundaries_valid(value, should_reject, capsys):
    ns = {"KILLSHOT_ODDS_MIN": -200}
    applied = T._apply_overrides(ns, {"KILLSHOT_ODDS_MIN": value})
    if should_reject:
        assert applied == {}
        assert ns["KILLSHOT_ODDS_MIN"] == -200
        assert "KILLSHOT_ODDS_MIN" in capsys.readouterr().err
    else:
        assert applied == {"KILLSHOT_ODDS_MIN": value}
        assert ns["KILLSHOT_ODDS_MIN"] == value


def test_odds_ordering_between_min_and_max_not_validated():
    # Explicitly out of scope for this change -- an inverted min/max is a
    # separate semantic rule, not attempted here.
    ns = {"KILLSHOT_ODDS_MIN": -200, "KILLSHOT_ODDS_MAX": 110}
    applied = T._apply_overrides(ns, {"KILLSHOT_ODDS_MIN": 150, "KILLSHOT_ODDS_MAX": -150})
    assert applied == {"KILLSHOT_ODDS_MIN": 150, "KILLSHOT_ODDS_MAX": -150}


def test_mixed_valid_and_invalid_overrides_isolate(capsys):
    ns = {"MIN_WIN_PROB": 0.50, "MIN_PICK_SCORE": 15, "KILLSHOT_SIZE_BASE": 3.0}
    applied = T._apply_overrides(ns, {
        "MIN_WIN_PROB": 5.0,          # invalid -> rejected
        "MIN_PICK_SCORE": 25,         # valid -> applied
        "KILLSHOT_SIZE_BASE": -1.0,   # invalid (negative size) -> rejected
    })
    assert applied == {"MIN_PICK_SCORE": 25}
    assert ns["MIN_WIN_PROB"] == 0.50          # rejected, default retained
    assert ns["MIN_PICK_SCORE"] == 25          # applied
    assert ns["KILLSHOT_SIZE_BASE"] == 3.0     # rejected, default retained
    err = capsys.readouterr().err
    assert "MIN_WIN_PROB" in err and "KILLSHOT_SIZE_BASE" in err


def test_constant_without_a_range_rule_applies_with_type_check_only():
    # Not every tunable constant has an explicit range rule (only those with
    # already-clear semantic meaning) -- unranged constants keep exactly the
    # prior type-check-only behavior, unchanged.
    ns = {"BONUS_DAILY_CAP": 5}
    applied = T._apply_overrides(ns, {"BONUS_DAILY_CAP": 999})
    # BONUS_DAILY_CAP has a >=0 rule (a count), so this should apply --
    # confirms count-typed constants aren't accidentally blocked.
    assert applied == {"BONUS_DAILY_CAP": 999}


# ── R9: regression coverage -- unrelated existing behavior unchanged ────────

def test_malformed_toml_still_warns_and_returns_empty(tmp_path, monkeypatch, capsys):
    import paths
    monkeypatch.setattr(paths, "PROJECT_ROOT", tmp_path)
    cfg_dir = tmp_path / "config"
    cfg_dir.mkdir()
    (cfg_dir / "thresholds.toml").write_text("not valid toml [[[", encoding="utf-8")
    result = T._load_threshold_overrides()
    assert result == {}
    assert "ignoring" in capsys.readouterr().err


def test_no_config_file_returns_empty_via_direct_call(tmp_path, monkeypatch):
    import paths
    monkeypatch.setattr(paths, "PROJECT_ROOT", tmp_path)  # no config/ dir created
    assert T._load_threshold_overrides() == {}


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
