"""Section 39 — pick_log loader consolidation (architectural note #3).

Five consumers used to each roll their own open+lock+filter loop:

    engine/analyze_picks.load_picks
    engine/clv_report.load_all_picks
    engine/morning_preview.load_pick_log
    engine/weekly_recap.load_picks
    engine/results_graphic._load_day_picks

All now delegate to ``engine/pick_log_io.load_rows``. These tests enforce:

* ``load_rows`` exists, is exported, and applies every documented filter
  with AND semantics.
* Legacy per-caller behaviour is preserved — same input rows through each
  wrapper produce the same filtered output as the pre-refactor code did.
* Every migrated caller imports ``load_rows`` and no longer carries its
  own per-path ``read_rows_locked_if_exists`` call in its loader body.
* Root mirrors stay byte-identical to ``engine/`` for every migrated file.
"""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
ENGINE_DIR = REPO_ROOT / "engine"

if str(ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(ENGINE_DIR))


# ── Fixture: a pick_log CSV with a representative row mix ─────────────────

from pick_log_schema import CANONICAL_HEADER  # noqa: E402


def _blank_row(**over):
    row = {k: "" for k in CANONICAL_HEADER}
    row.update(over)
    return row


@pytest.fixture
def sample_log(tmp_path):
    """A CSV with rows covering every branch the 5 legacy loaders cared about."""
    path = tmp_path / "pick_log.csv"
    rows = [
        # graded NBA primary (W)
        _blank_row(date="2026-04-20", run_type="primary", sport="NBA",
                   stat="PTS", tier="T1", result="W", odds="-110", size="1",
                   edge="0.05"),
        # graded NHL primary (L)
        _blank_row(date="2026-04-20", run_type="primary", sport="NHL",
                   stat="SOG", tier="T2", result="L", odds="+105", size="1"),
        # graded MLB shadow bonus (W) — excluded from public-facing views
        _blank_row(date="2026-04-21", run_type="bonus", sport="MLB",
                   stat="F5_ML", tier="T3", result="W", odds="+120", size="1"),
        # ungraded daily_lay parlay (no result)
        _blank_row(date="2026-04-21", run_type="daily_lay", sport="NBA",
                   stat="PARLAY", tier="DAILY_LAY", result="",
                   odds="+350", size="1"),
        # graded manual NBA (P)
        _blank_row(date="2026-04-21", run_type="manual", sport="NBA",
                   stat="AST", tier="T1", result="P", odds="-120", size="1"),
        # graded NBA primary — blank run_type variant (legacy row shape)
        _blank_row(date="2026-04-22", run_type="", sport="NBA",
                   stat="REB", tier="T1", result="W", odds="+100", size="1"),
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CANONICAL_HEADER)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    return path


# ── load_rows: existence + exports ────────────────────────────────────────

def test_load_rows_exported():
    import pick_log_io
    assert hasattr(pick_log_io, "load_rows")
    assert "load_rows" in pick_log_io.__all__


# ── load_rows: filter behaviour ────────────────────────────────────────────

def test_load_rows_no_filters_returns_all(sample_log):
    from pick_log_io import load_rows
    rows = load_rows([sample_log])
    assert len(rows) == 6


def test_load_rows_missing_path_is_skipped(sample_log, tmp_path):
    from pick_log_io import load_rows
    rows = load_rows([sample_log, tmp_path / "nope.csv"])
    assert len(rows) == 6


def test_load_rows_zero_byte_path_is_skipped(sample_log, tmp_path):
    from pick_log_io import load_rows
    empty = tmp_path / "empty.csv"
    empty.write_text("", encoding="utf-8")
    rows = load_rows([sample_log, empty])
    assert len(rows) == 6


def test_load_rows_graded_only(sample_log):
    from pick_log_io import load_rows
    rows = load_rows([sample_log], graded_only=True)
    # 5 graded rows — everything except the ungraded daily_lay parlay.
    assert len(rows) == 5
    for r in rows:
        assert r["result"].strip().upper() in {"W", "L", "P"}


def test_load_rows_sports_is_case_insensitive(sample_log):
    from pick_log_io import load_rows
    rows = load_rows([sample_log], sports=["nba"])
    assert all(r["sport"].upper() == "NBA" for r in rows)
    assert len(rows) == 4


def test_load_rows_exclude_sports(sample_log):
    from pick_log_io import load_rows
    rows = load_rows([sample_log], exclude_sports={"MLB"})
    assert all(r["sport"].upper() != "MLB" for r in rows)
    assert len(rows) == 5


def test_load_rows_stats_filter(sample_log):
    from pick_log_io import load_rows
    rows = load_rows([sample_log], stats=["PTS", "AST"])
    stats = {r["stat"].upper() for r in rows}
    assert stats == {"PTS", "AST"}


def test_load_rows_exclude_stats_filter(sample_log):
    from pick_log_io import load_rows
    rows = load_rows([sample_log], exclude_stats=["PARLAY"])
    assert all(r["stat"].upper() != "PARLAY" for r in rows)


def test_load_rows_run_types_filter(sample_log):
    from pick_log_io import load_rows
    rows = load_rows([sample_log], run_types=["primary", ""])
    rts = {r["run_type"] for r in rows}
    assert rts == {"primary", ""}


def test_load_rows_run_types_accepts_none_as_blank(sample_log):
    """results_graphic's legacy set included None — the loader should treat
    that as the blank-string case so legacy-shaped rows still match."""
    from pick_log_io import load_rows
    rows = load_rows([sample_log], run_types=frozenset({"primary", None}))
    rts = {r["run_type"] for r in rows}
    assert rts == {"primary", ""}


def test_load_rows_exclude_run_types(sample_log):
    from pick_log_io import load_rows
    rows = load_rows([sample_log], exclude_run_types=["daily_lay", "manual"])
    rts = {r["run_type"] for r in rows}
    assert "daily_lay" not in rts and "manual" not in rts


def test_load_rows_tiers_case_insensitive(sample_log):
    from pick_log_io import load_rows
    rows = load_rows([sample_log], tiers=["t1"])
    assert all(r["tier"].upper() == "T1" for r in rows)


def test_load_rows_date_equals(sample_log):
    from pick_log_io import load_rows
    rows = load_rows([sample_log], date_equals="2026-04-21")
    assert {r["date"] for r in rows} == {"2026-04-21"}


def test_load_rows_since(sample_log):
    from pick_log_io import load_rows
    rows = load_rows([sample_log], since="2026-04-21")
    assert all(r["date"] >= "2026-04-21" for r in rows)


def test_load_rows_date_range(sample_log):
    from pick_log_io import load_rows
    rows = load_rows([sample_log], date_range=("2026-04-20", "2026-04-20"))
    assert {r["date"] for r in rows} == {"2026-04-20"}


def test_load_rows_date_range_open_bound(sample_log):
    from pick_log_io import load_rows
    rows = load_rows([sample_log], date_range=(None, "2026-04-20"))
    assert {r["date"] for r in rows} == {"2026-04-20"}


def test_load_rows_and_semantics(sample_log):
    """All supplied filters must pass for a row to be kept."""
    from pick_log_io import load_rows
    rows = load_rows(
        [sample_log],
        sports=["NBA"],
        stats=["PTS"],
        graded_only=True,
    )
    assert len(rows) == 1
    r = rows[0]
    assert r["sport"] == "NBA" and r["stat"] == "PTS" and r["result"] == "W"


def test_load_rows_clv_report_shape(sample_log):
    """Reproduce the old clv_report.load_all_picks filter shape."""
    from pick_log_io import load_rows
    rows = load_rows(
        [sample_log],
        since="2026-04-20",
        exclude_run_types=["daily_lay"],
        exclude_stats=["PARLAY"],
        graded_only=True,
    )
    # Manual pick is a real bet and is included (clv_report appended manual log).
    # Only the ungraded daily_lay parlay is dropped.
    assert len(rows) == 5


def test_load_rows_results_graphic_shape(sample_log):
    """Reproduce the old results_graphic._load_day_picks filter shape."""
    from pick_log_io import load_rows
    rows = load_rows(
        [sample_log],
        date_equals="2026-04-21",
        run_types=frozenset({"primary", "bonus", "daily_lay", "", None}),
        exclude_sports={"MLB"},
        graded_only=True,
    )
    # 2026-04-21: bonus/MLB (dropped, shadow), daily_lay (dropped, ungraded),
    # manual (dropped, not in run_types). Zero matches on this day.
    assert rows == []
    # But 2026-04-22 has a legacy-shape row (blank run_type) that must match.
    rows2 = load_rows(
        [sample_log],
        date_equals="2026-04-22",
        run_types=frozenset({"primary", "bonus", "daily_lay", "", None}),
        exclude_sports={"MLB"},
        graded_only=True,
    )
    assert len(rows2) == 1
    assert rows2[0]["run_type"] == ""


# ── Wrapper regressions: each caller still produces the legacy output ───────

def test_analyze_picks_wrapper(sample_log):
    import analyze_picks
    picks = analyze_picks.load_picks(
        str(sample_log),
        sport_filter="NBA",
        extra_paths=[],
        exclude_run_types={"daily_lay"},
    )
    # NBA graded rows excluding daily_lay: PTS W, AST P, REB W
    assert len(picks) == 3
    # Numeric enrichment must still be applied.
    for r in picks:
        assert "odds_num" in r and "edge_num" in r and "size_num" in r
        assert isinstance(r["odds_num"], int)
        assert r["result"] in {"W", "L", "P"}


def test_morning_preview_wrapper(sample_log):
    import morning_preview
    rows = morning_preview.load_pick_log(str(sample_log))
    assert len(rows) == 6  # no filtering in the wrapper


def test_weekly_recap_wrapper(sample_log, tmp_path):
    import weekly_recap
    rows = weekly_recap.load_picks(str(sample_log), extra_paths=())
    assert len(rows) == 6  # no filtering in the wrapper


def test_results_graphic_wrapper(sample_log, monkeypatch):
    import results_graphic
    monkeypatch.setattr(results_graphic, "PICK_LOG_PATH", str(sample_log))
    rows = results_graphic._load_day_picks("2026-04-22")
    # Legacy blank-run_type row on 2026-04-22 must pass _PUBLIC_RUN_TYPES.
    assert len(rows) == 1
    assert rows[0]["sport"] == "NBA"
    # MLB row on 2026-04-21 must be filtered out as shadow.
    rows2 = results_graphic._load_day_picks("2026-04-21")
    assert all(r["sport"].upper() != "MLB" for r in rows2)


def test_clv_report_wrapper(sample_log, monkeypatch):
    import clv_report
    # Point both log paths at our fixture; manual log will not exist.
    monkeypatch.setattr(clv_report, "PICK_LOG", sample_log)
    monkeypatch.setattr(clv_report, "PICK_LOG_MANUAL", Path(sample_log.parent / "missing_manual.csv"))
    rows = clv_report.load_all_picks(days=365, sport_filter=None, tier_filter=None)
    # Graded rows, minus daily_lay and PARLAY (none anyway). Manual (P) is kept.
    assert len(rows) == 5
    rows_nba = clv_report.load_all_picks(days=365, sport_filter="NBA", tier_filter="T1")
    for r in rows_nba:
        assert r["sport"].upper() == "NBA"
        assert r["tier"].upper() == "T1"


# ── Consumer migration: every wrapper imports load_rows ─────────────────────

_CONSUMERS = [
    "analyze_picks.py",
    "clv_report.py",
    "morning_preview.py",
    "weekly_recap.py",
    "results_graphic.py",
]


@pytest.mark.parametrize("fname", _CONSUMERS)
def test_consumer_imports_load_rows(fname):
    src = (ENGINE_DIR / fname).read_text(encoding="utf-8")
    assert re.search(r"from\s+pick_log_io\s+import\s+[^\n]*load_rows", src), (
        f"{fname} must `from pick_log_io import load_rows` — arch note #3"
    )


def _extract_function_body(src: str, fn_name: str) -> str:
    import ast
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == fn_name:
            lines = src.splitlines()
            return "\n".join(lines[node.lineno - 1: node.end_lineno])
    return ""


_WRAPPER_FNS = [
    ("analyze_picks.py",   "load_picks"),
    ("clv_report.py",      "load_all_picks"),
    ("morning_preview.py", "load_pick_log"),
    ("weekly_recap.py",    "load_picks"),
    ("results_graphic.py", "_load_day_picks"),
]


@pytest.mark.parametrize("fname, fn", _WRAPPER_FNS,
                         ids=[f"{f}::{fn}" for f, fn in _WRAPPER_FNS])
def test_wrapper_delegates_to_load_rows(fname, fn):
    src = (ENGINE_DIR / fname).read_text(encoding="utf-8")
    body = _extract_function_body(src, fn)
    assert body, f"couldn't find def {fn} in {fname}"
    assert "load_rows(" in body, (
        f"{fname}::{fn} must call load_rows(...) — arch note #3"
    )


@pytest.mark.parametrize("fname, fn", _WRAPPER_FNS,
                         ids=[f"{f}::{fn}" for f, fn in _WRAPPER_FNS])
def test_wrapper_has_no_inline_reader(fname, fn):
    """The inline ``read_rows_locked_if_exists(...)`` call should be gone
    from the migrated wrapper bodies — they delegate instead."""
    src = (ENGINE_DIR / fname).read_text(encoding="utf-8")
    body = _extract_function_body(src, fn)
    assert body, f"couldn't find def {fn} in {fname}"
    assert "read_rows_locked_if_exists(" not in body, (
        f"{fname}::{fn} still calls read_rows_locked_if_exists — "
        f"delegate to load_rows(...) instead (arch note #3)"
    )


# ── Root-mirror sync contract ────────────────────────────────────────────────

# L16 (Apr 30 2026): files that had root mirrors now use 5-line runpy shims.
# test_tail_guard.py guards shim validity; byte-identical sync is no longer required.
# _SYNCED_FILES and test_root_mirror_is_byte_identical removed (H1/H2, May 1 2026).
#
# pick_log_io.py is a library module — no root copy ever needed.
# analyze_picks.py, clv_report.py, morning_preview.py, weekly_recap.py,
# results_graphic.py are all L16 runpy shims.
