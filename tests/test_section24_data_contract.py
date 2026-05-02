#!/usr/bin/env python3
"""Regression tests for Section 24 — pick_log write-time data contract.

Covers:
  M-3   normalize_is_home collapses bool / "1" / "true"/"True"/"yes" into
        canonical "True"/"False"/"" so grade_picks's
        ``str(val).lower() == "true"`` check stops silently miscategorising
        "1" as False.

  M-10  normalize_size pins sizes to 2 decimals — "0.50" not "0.5" — so
        string-sorting and the xlsx recap's column formatting stay
        consistent across writers.

  M-11  normalize_proj pins projections to 2 decimals. Cosmetic but the
        xlsx column width was jumping between 4- and 1-decimal rows.

  M-12  normalize_edge is 4-decimal decimal form (0.0500 = 5%) so
        float() readers don't lose sub-percent precision.

  M-13  schema sidecar (pick_log.schema.json) records SCHEMA_VERSION +
        canonical header alongside every pick_log CSV — readers can
        verify on-disk schema version without column sniffing.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "engine"))


# ─────────────────────────────────────────────────────────────────
# M-3 — normalize_is_home
# ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("raw,expected", [
    (True,         "True"),
    (False,        "False"),
    ("True",       "True"),
    ("False",      "False"),
    ("true",       "True"),
    ("false",      "False"),
    ("1",          "True"),
    ("0",          "False"),
    (1,            "True"),
    (0,            "False"),
    ("t",          "True"),
    ("f",          "False"),
    ("yes",        "True"),
    ("no",         "False"),
    ("YES",        "True"),
    ("  True  ",   "True"),   # whitespace tolerated
    ("",           ""),
    (None,         ""),
    ("garbage",    ""),       # unparseable collapses to blank
    ("maybe",      ""),
])
def test_normalize_is_home_cases(raw, expected):
    from pick_log_schema import normalize_is_home
    got = normalize_is_home(raw)
    assert got == expected, (
        f"M-3: normalize_is_home({raw!r}) -> {got!r}, expected {expected!r}"
    )


def test_normalize_is_home_is_idempotent():
    """Running normalize twice must be a no-op — important because the
    engine sometimes re-reads a row and writes it back."""
    from pick_log_schema import normalize_is_home
    for raw in [True, False, "1", "0", "", None, "True", "False"]:
        once  = normalize_is_home(raw)
        twice = normalize_is_home(once)
        assert once == twice, (
            f"M-3: not idempotent for {raw!r} — {once!r} → {twice!r}"
        )


def test_validate_is_home_for_stat_team_stats_require_bool():
    """SPREAD/ML/F5/TEAM_TOTAL MUST have a non-blank is_home."""
    from pick_log_schema import validate_is_home_for_stat
    for stat in ["SPREAD", "ML_FAV", "ML_DOG", "F5_SPREAD", "F5_ML", "TEAM_TOTAL"]:
        assert validate_is_home_for_stat(True,  stat) is True
        assert validate_is_home_for_stat(False, stat) is True
        assert validate_is_home_for_stat("",    stat) is False, (
            f"M-3: {stat} with blank is_home must fail validation"
        )
        assert validate_is_home_for_stat(None,  stat) is False


def test_validate_is_home_for_stat_props_require_blank():
    """Props (PTS/REB/AST/SOG/etc.) MUST have a blank is_home —
    a stray True on a prop row is a writer bug."""
    from pick_log_schema import validate_is_home_for_stat
    for stat in ["PTS", "REB", "AST", "SOG", "3PM", "TOTAL", "PARLAY"]:
        assert validate_is_home_for_stat("",    stat) is True, (
            f"M-3: blank is_home must be legal for prop stat {stat}"
        )
        assert validate_is_home_for_stat(True,  stat) is False, (
            f"M-3: {stat} with is_home=True is illegal (props have no home side)"
        )
        assert validate_is_home_for_stat(False, stat) is False


def test_validate_is_home_accepts_normalizable_team_inputs():
    """Validator must call normalize_is_home internally — "1" is legal
    for a SPREAD pick because it normalizes to "True"."""
    from pick_log_schema import validate_is_home_for_stat
    assert validate_is_home_for_stat("1",    "SPREAD") is True
    assert validate_is_home_for_stat("true", "ML_FAV") is True
    assert validate_is_home_for_stat("no",   "F5_ML")  is True


# ─────────────────────────────────────────────────────────────────
# M-10 — normalize_size
# ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("raw,expected", [
    (0.5,       "0.50"),
    (0.50,      "0.50"),
    ("0.5",     "0.50"),
    ("0.50",    "0.50"),
    (1,         "1.00"),
    (1.0,       "1.00"),
    ("1",       "1.00"),
    (2.5,       "2.50"),
    (1.25,      "1.25"),
    (0,         "0.00"),
    ("",        ""),
    (None,      ""),
    ("abc",     ""),
])
def test_normalize_size_cases(raw, expected):
    from pick_log_schema import normalize_size
    assert normalize_size(raw) == expected


def test_normalize_size_idempotent():
    from pick_log_schema import normalize_size
    for raw in [0.5, "0.5", 1, 2.5, "1.25", ""]:
        once = normalize_size(raw)
        assert normalize_size(once) == once, (
            f"M-10: normalize_size not idempotent for {raw!r}"
        )


# ─────────────────────────────────────────────────────────────────
# M-11 — normalize_proj
# ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("raw,expected", [
    (22.3917,   "22.39"),
    (22.4,      "22.40"),
    ("22.3917", "22.39"),
    (0,         "0.00"),
    ("",        ""),
    (None,      ""),
    ("junk",    ""),
])
def test_normalize_proj_cases(raw, expected):
    from pick_log_schema import normalize_proj
    assert normalize_proj(raw) == expected


# ─────────────────────────────────────────────────────────────────
# M-12 — normalize_edge
# ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("raw,expected", [
    (0.05,      "0.0500"),
    (0.213,     "0.2130"),
    ("0.05",    "0.0500"),
    (0,         "0.0000"),
    (-0.02,     "-0.0200"),
    ("",        ""),
    (None,      ""),
    ("junk",    ""),
])
def test_normalize_edge_cases(raw, expected):
    from pick_log_schema import normalize_edge
    assert normalize_edge(raw) == expected


def test_normalize_edge_preserves_sub_percent_precision():
    """The whole point of 4-decimal form is that 0.9% edge doesn't round
    to 1% or 0%. Verify the decimal survives a round-trip through
    normalize_edge -> float."""
    from pick_log_schema import normalize_edge
    s = normalize_edge(0.0097)
    assert s == "0.0097"
    assert abs(float(s) - 0.0097) < 1e-12


# ─────────────────────────────────────────────────────────────────
# M-13 — schema sidecar
# ─────────────────────────────────────────────────────────────────

def test_schema_sidecar_path_convention(tmp_path):
    """Sidecar name is ``<stem>.schema.json`` — not ``<stem>.csv.schema.json``."""
    from pick_log_schema import schema_sidecar_path
    csv_path = tmp_path / "pick_log.csv"
    sidecar = schema_sidecar_path(csv_path)
    assert sidecar == tmp_path / "pick_log.schema.json", (
        f"M-13: unexpected sidecar path {sidecar}"
    )
    # Manual log variant.
    assert schema_sidecar_path(tmp_path / "pick_log_manual.csv") == \
           tmp_path / "pick_log_manual.schema.json"
    # Shadow MLB log variant.
    assert schema_sidecar_path(tmp_path / "pick_log_mlb.csv") == \
           tmp_path / "pick_log_mlb.schema.json"


def test_write_schema_sidecar_roundtrip(tmp_path):
    """Write + read must round-trip the schema version and header verbatim."""
    from pick_log_schema import (
        CANONICAL_HEADER,
        SCHEMA_VERSION,
        read_schema_sidecar,
        write_schema_sidecar,
        schema_sidecar_path,
    )
    csv_path = tmp_path / "pick_log.csv"
    csv_path.write_text("date\n2026-04-20\n", encoding="utf-8")  # any content
    write_schema_sidecar(csv_path)

    sidecar_path = schema_sidecar_path(csv_path)
    assert sidecar_path.exists(), "M-13: sidecar not created"

    # Readable as JSON and contains the documented keys.
    payload = read_schema_sidecar(csv_path)
    assert payload is not None
    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["canonical_header"] == list(CANONICAL_HEADER)
    assert "note" in payload


def test_read_schema_sidecar_missing_returns_none(tmp_path):
    from pick_log_schema import read_schema_sidecar
    assert read_schema_sidecar(tmp_path / "nope.csv") is None


def test_read_schema_sidecar_corrupt_returns_none(tmp_path):
    """A sidecar that was truncated or corrupted must not crash readers."""
    from pick_log_schema import read_schema_sidecar, schema_sidecar_path
    csv_path = tmp_path / "pick_log.csv"
    csv_path.touch()
    sidecar = schema_sidecar_path(csv_path)
    sidecar.write_text("{not json", encoding="utf-8")
    assert read_schema_sidecar(csv_path) is None


def test_sidecar_write_is_atomic(tmp_path, monkeypatch):
    """If os.replace raises mid-write, we must NOT leave an orphaned .tmp
    file lying around. Simulate that by monkeypatching os.replace to fail
    and verify cleanup.
    """
    import os
    from pick_log_schema import schema_sidecar_path, write_schema_sidecar

    csv_path = tmp_path / "pick_log.csv"
    csv_path.touch()
    sidecar = schema_sidecar_path(csv_path)

    def boom(*args, **kwargs):
        raise OSError("simulated replace failure")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError):
        write_schema_sidecar(csv_path)

    tmp_leftovers = list(tmp_path.glob("*.tmp"))
    assert not tmp_leftovers, (
        f"M-13: atomic write left orphaned tmp files: {tmp_leftovers}"
    )
    assert not sidecar.exists(), "M-13: partial sidecar should not exist on failure"


# ─────────────────────────────────────────────────────────────────
# Wire-up — normalizers exported from __all__
# ─────────────────────────────────────────────────────────────────

def test_pick_log_schema_exports_new_helpers():
    import pick_log_schema
    required = {
        "normalize_is_home",
        "normalize_size",
        "normalize_proj",
        "normalize_edge",
        "validate_is_home_for_stat",
        "write_schema_sidecar",
        "read_schema_sidecar",
        "schema_sidecar_path",
    }
    missing = required - set(pick_log_schema.__all__)
    assert not missing, f"M-24 helpers missing from __all__: {missing}"


def test_run_picks_imports_normalizers():
    """Grep run_picks.py to confirm it actually uses the new normalizers
    at its write sites — the whole point is no bypass paths remain."""
    rp = HERE.parent / "engine" / "run_picks.py"
    src = rp.read_text(encoding="utf-8")
    for name in ["normalize_is_home", "normalize_size", "normalize_proj",
                 "normalize_edge", "write_schema_sidecar"]:
        assert name in src, (
            f"M-24: run_picks.py does not import {name} — write-site bypass "
            "means the normalization never fires."
        )


def test_run_picks_write_sites_use_normalize_size():
    """Look for the bare ``{p.get('size', 0):.2f}`` pattern in run_picks —
    that was the old inline formatter, now replaced by normalize_size."""
    rp = HERE.parent / "engine" / "run_picks.py"
    src = rp.read_text(encoding="utf-8")
    # The pattern must be GONE from writer rows. It's OK if it remains in
    # an isolated utility, but no writerow([...]) should still use it.
    # We check the primary log_picks block for the call signature.
    assert "_normalize_size(p.get(\"size\", 0))" in src, (
        "M-10: primary log_picks must route size through normalize_size"
    )
    assert "_normalize_size(pick.get(\"size\", 0))" in src, (
        "M-10: bonus log must route size through normalize_size"
    )


# ─────────────────────────────────────────────────────────────────
# End-to-end: run a write + check sidecar was produced
# ─────────────────────────────────────────────────────────────────

def test_end_to_end_sidecar_written_next_to_csv(tmp_path):
    """Build a minimal CSV + call write_schema_sidecar directly and
    confirm the sidecar lives next to the CSV with the right payload.
    This mirrors what happens at the end of log_picks / _log_bonus_pick.
    """
    from pick_log_schema import (
        CANONICAL_HEADER,
        SCHEMA_VERSION,
        write_schema_sidecar,
        read_schema_sidecar,
    )
    csv_path = tmp_path / "pick_log.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(CANONICAL_HEADER)
        w.writerow(["2026-04-20", "18:00", "primary", "NBA", "Luka Doncic",
                    "DAL", "PTS", "28.5", "over", "29.40", "0.5500",
                    "0.0500", "-110", "draftkings", "T2", "72.5", "1.00",
                    "DAL @ LAC", "Default", "", "", "", "", "", "", "", ""])

    write_schema_sidecar(csv_path)

    sidecar_json = read_schema_sidecar(csv_path)
    assert sidecar_json is not None
    assert sidecar_json["schema_version"] == SCHEMA_VERSION
    assert sidecar_json["canonical_header"] == list(CANONICAL_HEADER)
    # Written-file shape — alongside the CSV, same directory.
    assert (tmp_path / "pick_log.schema.json").exists()


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
