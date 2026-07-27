"""ADR-005 / 1B (revised per architecture review) -- odds_io.parse_csv()'s
required-column validation.

Deliberately narrow: only the core stat columns with no documented graceful
fallback (PTS/REB/AST/3PM for NBA/WNBA, the 12 raw MLB stat columns, SOG/AST/G/
SV/GA for NHL) are required. dk_std is explicitly excluded -- its absence
already has an intentional fallback (falls back to SIGMA["PTS"], see the
dk_std comment in odds_io.py) and this validation must not flag it.

Default behavior (ODDS_IO_STRICT_CSV_VALIDATION unset) is warn-and-continue,
matching the existing tolerant-CSV-parsing philosophy elsewhere in this file.
Setting the env var aborts instead, mirroring the pre-existing empty-CSV
sys.exit(1) pattern already in parse_csv().
"""
from __future__ import annotations

import csv as csv_module
import logging
import sys

import pytest

import odds_io


@pytest.fixture
def jonnyparlay_log(caplog):
    """The "jonnyparlay" logger sets propagate=False (engine_logger.py) so
    caplog's default root-logger handler never sees its records -- attach the
    capture handler directly, same pattern as
    tests/test_log_picks_zero_row_warning.py's jonnyparlay_warnings fixture."""
    logger = logging.getLogger("jonnyparlay")
    handler = caplog.handler
    logger.addHandler(handler)
    prev_level = logger.level
    logger.setLevel(logging.WARNING)
    try:
        yield caplog
    finally:
        logger.removeHandler(handler)
        logger.setLevel(prev_level)


def _write_csv(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv_module.DictWriter(f, fieldnames=header)
        w.writeheader()
        w.writerows(rows)
    return path


_NBA_HEADER_COMPLETE = ["Name", "Pos", "Team", "Opp", "Status",
                        "Saber Team", "Saber Total", "PTS", "RB", "AST", "3PT", "dk_std"]
_NBA_ROW = {"Name": "A'ja Wilson", "Pos": "F", "Team": "LV", "Opp": "SEA", "Status": "",
           "Saber Team": "100", "Saber Total": "200", "PTS": "22.5", "RB": "9.1",
           "AST": "2.3", "3PT": "0.4", "dk_std": "3.1"}

_MLB_HEADER_COMPLETE = ["Name", "Pos", "Team", "Opp", "Status", "Saber Team", "Saber Total",
                        "1B", "2B", "3B", "HR", "R", "RBI", "H", "K", "BB", "IP", "ER", "PA"]
_MLB_BATTER_ROW = {"Name": "Aaron Judge", "Pos": "OF", "Team": "NYY", "Opp": "BOS",
                   "Status": "", "Saber Team": "5", "Saber Total": "9",
                   "1B": "1", "2B": "0", "3B": "0", "HR": "0.4", "R": "0.8", "RBI": "0.9",
                   "H": "1.2", "K": "0", "BB": "0.3", "IP": "0", "ER": "0", "PA": "4.2"}


def test_complete_nba_csv_does_not_warn(tmp_path, jonnyparlay_log):
    p = _write_csv(tmp_path / "slate_nba.csv", _NBA_HEADER_COMPLETE, [_NBA_ROW])
    players, sport, _ = odds_io.parse_csv(p)
    assert sport == "NBA"
    assert len(players) == 1
    assert not any("missing required" in r.message for r in jonnyparlay_log.records)


def test_nba_csv_missing_pts_warns_by_default(tmp_path, jonnyparlay_log, capsys):
    header = [h for h in _NBA_HEADER_COMPLETE if h != "PTS"]
    row = {k: v for k, v in _NBA_ROW.items() if k != "PTS"}
    p = _write_csv(tmp_path / "slate_nba.csv", header, [row])
    players, sport, _ = odds_io.parse_csv(p)
    # Default (flag unset): warns, does NOT abort -- players still returned.
    assert len(players) == 1
    assert any("missing required NBA column" in r.message and "PTS" in r.message
               for r in jonnyparlay_log.records)
    assert "missing required" in capsys.readouterr().out


def test_nba_csv_missing_dk_std_does_not_warn(tmp_path, jonnyparlay_log):
    # dk_std has a documented, intentional fallback -- must NOT be in the
    # required set. This is the key regression guard for the review's scope
    # correction (dk_std was in the ORIGINAL 1B design; it was removed).
    header = [h for h in _NBA_HEADER_COMPLETE if h != "dk_std"]
    row = {k: v for k, v in _NBA_ROW.items() if k != "dk_std"}
    p = _write_csv(tmp_path / "slate_nba.csv", header, [row])
    players, sport, _ = odds_io.parse_csv(p)
    assert len(players) == 1
    assert players[0]["dk_std"] == 0.0  # existing fallback behavior, unchanged
    assert not any("missing required" in r.message for r in jonnyparlay_log.records)


def test_nba_csv_missing_pts_aborts_when_strict(tmp_path, monkeypatch):
    monkeypatch.setenv("ODDS_IO_STRICT_CSV_VALIDATION", "1")
    header = [h for h in _NBA_HEADER_COMPLETE if h != "PTS"]
    row = {k: v for k, v in _NBA_ROW.items() if k != "PTS"}
    p = _write_csv(tmp_path / "slate_nba.csv", header, [row])
    with pytest.raises(SystemExit) as exc_info:
        odds_io.parse_csv(p)
    assert exc_info.value.code == 1


def test_complete_mlb_csv_does_not_warn(tmp_path, jonnyparlay_log):
    p = _write_csv(tmp_path / "slate_mlb.csv", _MLB_HEADER_COMPLETE, [_MLB_BATTER_ROW])
    players, sport, _ = odds_io.parse_csv(p)
    assert sport == "MLB"
    assert not any("missing required" in r.message for r in jonnyparlay_log.records)


def test_mlb_csv_missing_k_column_warns(tmp_path, jonnyparlay_log):
    # MLB fields are exact-case, no fallback chain -- "k" (lowercase) does NOT
    # satisfy the "K" requirement, matching parse_csv()'s own case-sensitive
    # clean.get("K", 0) lookup exactly.
    header = [h if h != "K" else "k" for h in _MLB_HEADER_COMPLETE]
    row = {("k" if k == "K" else k): v for k, v in _MLB_BATTER_ROW.items()}
    p = _write_csv(tmp_path / "slate_mlb.csv", header, [row])
    odds_io.parse_csv(p)
    assert any("missing required MLB column" in r.message and "'K'" in r.message
               for r in jonnyparlay_log.records)


def test_bad_row_value_still_skips_silently_not_a_validation_warning(tmp_path, jonnyparlay_log):
    # Existing per-row tolerance (bad VALUE, not a missing column) must stay
    # unchanged -- this is a regression guard, not new behavior.
    row = dict(_NBA_ROW)
    row["PTS"] = "not-a-number"
    p = _write_csv(tmp_path / "slate_nba.csv", _NBA_HEADER_COMPLETE, [row])
    players, sport, _ = odds_io.parse_csv(p)
    assert players == []  # existing behavior: bad row silently skipped
    assert not any("missing required" in r.message for r in jonnyparlay_log.records)


# ---------------------------------------------------------------------------
# R16: sport-misdetection is a distinct, unconditional failure -- not a
# degraded input. Unlike a missing stat column, there is no defensible
# partial-continuation value when every column may be read under the wrong
# semantics, so this is NEVER gated by ODDS_IO_STRICT_CSV_VALIDATION.
# ---------------------------------------------------------------------------

_GARBAGE_HEADER = ["Name", "Team", "Salary"]
_GARBAGE_ROW = {"Name": "Nobody", "Team": "XXX", "Salary": "5000"}


def test_no_identifying_columns_fails_loudly_unconditionally(tmp_path):
    # No ODDS_IO_STRICT_CSV_VALIDATION set -- must still abort. This is the
    # one check that is never opt-in.
    p = _write_csv(tmp_path / "slate_unknown.csv", _GARBAGE_HEADER, [_GARBAGE_ROW])
    with pytest.raises(SystemExit) as exc_info:
        odds_io.parse_csv(p)
    assert exc_info.value.code == 1


def test_no_identifying_columns_logs_error_with_context(tmp_path, jonnyparlay_log):
    p = _write_csv(tmp_path / "slate_unknown.csv", _GARBAGE_HEADER, [_GARBAGE_ROW])
    with pytest.raises(SystemExit):
        odds_io.parse_csv(p)
    error_records = [r for r in jonnyparlay_log.records if r.levelno == logging.ERROR]
    assert error_records, "sport misdetection must log at ERROR"
    msg = error_records[0].message
    assert "sport detection failure" in msg
    assert "NBA" in msg  # detected sport (falls through to the default)
    assert "PTS" in msg or "pts" in msg  # an expected identifying column named
    assert "Salary" in msg  # the file's actual header, for diagnosis


def test_correct_sport_detection_no_false_positive(tmp_path, jonnyparlay_log):
    # Regression guard: valid CSVs must never trip the new check.
    p = _write_csv(tmp_path / "slate_nba.csv", _NBA_HEADER_COMPLETE, [_NBA_ROW])
    odds_io.parse_csv(p)  # must not raise
    assert not any("sport detection failure" in r.message for r in jonnyparlay_log.records)


def test_no_identifying_columns_ignores_strict_env_var(tmp_path, monkeypatch):
    # Explicitly NOT gated by the same env var as the other checks -- setting
    # it (or not) must not change this check's behavior.
    monkeypatch.setenv("ODDS_IO_STRICT_CSV_VALIDATION", "0")
    p = _write_csv(tmp_path / "slate_unknown.csv", _GARBAGE_HEADER, [_GARBAGE_ROW])
    with pytest.raises(SystemExit):
        odds_io.parse_csv(p)


# ---------------------------------------------------------------------------
# R16: per-row skip visibility (DEBUG -> WARNING) and aggregate drop-rate
# detection. Both preserve the existing skip-and-continue behavior exactly --
# only visibility changes, gated the same way as the existing required-column
# check (warn by default, abort under ODDS_IO_STRICT_CSV_VALIDATION).
# ---------------------------------------------------------------------------

def test_bad_row_value_skip_logs_at_warning_not_debug(tmp_path, jonnyparlay_log):
    row = dict(_NBA_ROW)
    row["PTS"] = "not-a-number"
    p = _write_csv(tmp_path / "slate_nba.csv", _NBA_HEADER_COMPLETE, [row])
    players, sport, _ = odds_io.parse_csv(p)
    assert players == []
    skip_records = [r for r in jonnyparlay_log.records if "Skipped malformed row" in r.message]
    assert skip_records, "expected a skip log record"
    assert skip_records[0].levelno == logging.WARNING


# Distinct last names, not just a trailing digit -- parse_csv()'s dedup keys
# on name_key() ("lastname_firstN"), which strips digits, so e.g. "Player 0"
# and "Player 1" collapse to the same key. Real distinct surnames avoid that.
_DISTINCT_SURNAMES = ["Adams", "Baker", "Clark", "Dixon", "Evans", "Foster",
                      "Garcia", "Harris", "Irwin", "Jones", "King", "Lopez",
                      "Moore", "Nash", "Ortiz", "Park", "Quinn", "Reed",
                      "Smith", "Turner"]


def _many_nba_rows(n_good, n_bad):
    rows = []
    for i in range(n_good):
        r = dict(_NBA_ROW)
        r["Name"] = f"Good {_DISTINCT_SURNAMES[i]}"
        rows.append(r)
    for i in range(n_bad):
        r = dict(_NBA_ROW)
        r["Name"] = f"Bad {_DISTINCT_SURNAMES[n_good + i]}"
        r["PTS"] = "not-a-number"
        rows.append(r)
    return rows


def test_high_row_drop_rate_warns(tmp_path, jonnyparlay_log):
    rows = _many_nba_rows(n_good=6, n_bad=4)  # 40% drop, over threshold
    p = _write_csv(tmp_path / "slate_nba.csv", _NBA_HEADER_COMPLETE, rows)
    players, sport, _ = odds_io.parse_csv(p)
    assert len(players) == 6
    assert any("high row-drop-rate" in r.getMessage() for r in jonnyparlay_log.records)


def test_low_row_drop_rate_does_not_warn(tmp_path, jonnyparlay_log):
    rows = _many_nba_rows(n_good=9, n_bad=1)  # 10% drop, under threshold
    p = _write_csv(tmp_path / "slate_nba.csv", _NBA_HEADER_COMPLETE, rows)
    players, sport, _ = odds_io.parse_csv(p)
    assert len(players) == 9
    assert not any("high row-drop-rate" in r.getMessage() for r in jonnyparlay_log.records)


def test_high_row_drop_rate_aborts_when_strict(tmp_path, monkeypatch):
    monkeypatch.setenv("ODDS_IO_STRICT_CSV_VALIDATION", "1")
    rows = _many_nba_rows(n_good=6, n_bad=4)
    p = _write_csv(tmp_path / "slate_nba.csv", _NBA_HEADER_COMPLETE, rows)
    with pytest.raises(SystemExit) as exc_info:
        odds_io.parse_csv(p)
    assert exc_info.value.code == 1
