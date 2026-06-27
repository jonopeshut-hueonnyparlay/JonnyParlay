"""Tests for engine/capture_clv_batch.py (#15) -- idempotent nightly CLV batch."""
import csv

import capture_clv_batch as cb
from capture_clv import calc_clv
from pick_log_schema import CANONICAL_HEADER


def _row(**kw):
    base = {c: "" for c in CANONICAL_HEADER}
    base.update(kw)
    return base


# ── gap detection ───────────────────────────────────────────────────────────

def test_needs_clv_only_graded_and_uncaptured():
    assert cb.needs_clv(_row(result="W", closing_odds="")) is True
    assert cb.needs_clv(_row(result="L", closing_odds="STALE")) is True   # daemon gave up -> retry
    assert cb.needs_clv(_row(result="W", closing_odds="-110")) is False   # already captured
    assert cb.needs_clv(_row(result="", closing_odds="")) is False        # ungraded


# ── apply_batch: fill + clv + provenance, idempotent ────────────────────────

def _fixed_quote(pick):
    # closing -120, no opposite (vigged), book dk, event/target stamped.
    return (-120, None, "draftkings", "evt1", "2026-06-26T23:05:00Z")


def test_apply_fills_closing_and_clv_and_provenance():
    rows = [_row(result="W", odds="-110", player="A", stat="PTS", date="2026-06-26"),
            _row(result="", odds="-110", player="B", stat="PTS")]  # ungraded -> skipped
    pending, caps = cb.apply_batch(rows, _fixed_quote, "2026-06-27T08:00:00Z")
    assert pending == 1 and len(caps) == 1
    assert rows[0]["closing_odds"] == -120
    assert rows[0]["clv"] == round(calc_clv(-110, -120, None), 6)
    assert rows[1]["closing_odds"] == ""        # ungraded untouched
    p = caps[0]
    assert p["event_id"] == "evt1" and p["target_ts"] == "2026-06-26T23:05:00Z"
    assert p["your_odds"] == -110 and p["closing_odds"] == -120


def test_apply_idempotent_second_pass_is_noop():
    rows = [_row(result="W", odds="-110", player="A", stat="PTS")]
    cb.apply_batch(rows, _fixed_quote, "t1")
    pending2, caps2 = cb.apply_batch(rows, _fixed_quote, "t2")   # already captured
    assert pending2 == 0 and caps2 == []


def test_apply_none_quote_leaves_pending_for_next_run():
    rows = [_row(result="W", odds="-110", player="A", stat="PTS")]
    pending, caps = cb.apply_batch(rows, lambda p: None, "t1")
    assert pending == 1 and caps == []
    assert rows[0]["closing_odds"] == ""    # untouched -> recovered next run


# ── run_batch end-to-end over a CSV (idempotent, provenance written) ────────

def _write_log(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CANONICAL_HEADER, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def test_run_batch_writes_back_and_is_rerunnable(tmp_path):
    log = tmp_path / "pick_log.csv"
    prov = tmp_path / "prov.csv"
    _write_log(log, [
        _row(result="W", odds="-110", player="A", stat="PTS", date="2026-06-26"),
        _row(result="L", odds="+120", player="B", stat="AST", date="2026-06-26"),
        _row(result="", odds="-110", player="C", stat="PTS", date="2026-06-26"),  # ungraded
    ])
    s1 = cb.run_batch(log_paths=[log], closing_for_pick=_fixed_quote,
                      now_iso="t1", provenance_path=prov)
    assert s1["captured"] == 2 and s1["pending"] == 2
    # closing_odds persisted on disk
    got = {r["player"]: r for r in csv.DictReader(open(log, encoding="utf-8"))}
    assert got["A"]["closing_odds"] == "-120" and got["C"]["closing_odds"] == ""
    # provenance recorded
    pv = list(csv.DictReader(open(prov, encoding="utf-8")))
    assert len(pv) == 2 and pv[0]["event_id"] == "evt1"
    # re-run -> nothing new (idempotent / gap-detecting)
    s2 = cb.run_batch(log_paths=[log], closing_for_pick=_fixed_quote,
                      now_iso="t2", provenance_path=prov)
    assert s2["captured"] == 0 and s2["pending"] == 0


def test_run_batch_date_filter(tmp_path):
    log = tmp_path / "pick_log.csv"
    _write_log(log, [
        _row(result="W", odds="-110", player="A", stat="PTS", date="2026-06-26"),
        _row(result="W", odds="-110", player="B", stat="PTS", date="2026-06-25"),
    ])
    s = cb.run_batch(date="2026-06-26", log_paths=[log], closing_for_pick=_fixed_quote,
                     now_iso="t1", provenance_path=tmp_path / "prov.csv")
    assert s["captured"] == 1   # only the 06-26 row
