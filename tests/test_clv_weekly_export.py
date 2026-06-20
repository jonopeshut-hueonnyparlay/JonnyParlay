"""Tests for the weekly CLV ledger export (audit S4k-X).

Covers the new logic only:
  * write_ledger_csv — fixed column contract, date/sport/player sort, extra-column drop
  * export_week — orchestration: window read (load_rows) -> write -> CLV summary

load_rows itself (window/grading filters, schema migration, locking) is exercised by
its own tests; here it is monkeypatched so these assert this module's wiring, not the
reader internals.
"""

from __future__ import annotations

import csv

import pytest

# engine/ is added to sys.path by the repo-root conftest.py.


def test_write_ledger_csv_columns_sort_and_drop(tmp_path):
    from clv_weekly_export import LEDGER_COLS, write_ledger_csv
    rows = [
        {"date": "2026-06-16", "sport": "WNBA", "player": "B Stewart", "team": "NY",
         "stat": "PTS", "line": "19.5", "direction": "over", "book": "dk",
         "odds": "-110", "closing_odds": "-120", "clv": "0.012", "result": "W",
         "tier": "T2", "size": "1.5", "win_prob": "0.58"},  # extra col -> dropped
        {"date": "2026-06-15", "sport": "MLB", "player": "A Judge", "team": "NYY",
         "stat": "HITS", "line": "1.5", "direction": "over", "book": "fd",
         "odds": "+120", "closing_odds": "+110", "clv": "-0.005", "result": "L",
         "tier": "T3", "size": "1.0"},
    ]
    out = tmp_path / "clv.csv"
    n = write_ledger_csv(rows, out)
    assert n == 2

    got = list(csv.DictReader(open(out, newline="", encoding="utf-8")))
    assert list(got[0].keys()) == LEDGER_COLS          # exact column contract
    assert [r["date"] for r in got] == ["2026-06-15", "2026-06-16"]  # sorted by date
    assert "win_prob" not in got[0]                    # extrasaction='ignore'
    assert got[1]["clv"] == "0.012" and got[1]["closing_odds"] == "-120"


def test_write_ledger_csv_empty(tmp_path):
    from clv_weekly_export import LEDGER_COLS, write_ledger_csv
    out = tmp_path / "empty.csv"
    assert write_ledger_csv([], out) == 0
    rows = list(csv.reader(open(out, newline="", encoding="utf-8")))
    assert rows == [LEDGER_COLS]                       # header only


def test_export_week_wires_reader_writer_and_summary(tmp_path, monkeypatch):
    import clv_weekly_export as cwe
    captured = {}

    def fake_load_rows(paths, **kwargs):
        captured["paths"] = paths
        captured["kwargs"] = kwargs
        return [
            {"date": "2026-06-15", "sport": "MLB", "player": "X", "clv": "0.01", "result": "W"},
            {"date": "2026-06-16", "sport": "WNBA", "player": "Y", "clv": "", "result": "L"},
        ]

    monkeypatch.setattr(cwe, "load_rows", fake_load_rows)
    out = tmp_path / "w.csv"
    n, summary = cwe.export_week("2026-06-15", "2026-06-21", out, log_paths=["dummy"])

    # window + grading + CLV-population exclusions pushed down to the canonical reader
    assert captured["kwargs"]["date_range"] == ("2026-06-15", "2026-06-21")
    assert captured["kwargs"]["graded_only"] is True
    assert "sgp" in captured["kwargs"]["exclude_run_types"]
    assert "PARLAY" in captured["kwargs"]["exclude_stats"]
    # write happened and the summary reflects the one captured CLV (the blank is "missing")
    assert n == 2 and out.exists()
    assert summary["total"] == 2 and summary["captured"] == 1 and summary["missing"] == 1


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
