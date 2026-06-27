"""Tests for engine/source_shadow.py -- the EdgeModel-vs-live source comparison.

Drives compare_rows() with an injected adapter so the outcome-derivation and
agree/disagree/who-was-right logic is pinned without any DB.
"""
import source_shadow as ss
from name_utils import name_key

_FAKE_EM = {
    (name_key("A'ja Wilson"), "PTS"): 21.0,       # over 19.5  -> agrees with a live 'over'
    (name_key("Breanna Stewart"), "PTS"): 18.0,   # under 19.5
    (name_key("Sabrina Ionescu"), "PTS"): 18.0,   # under 19.5
    (name_key("A'ja Wilson"), "REB"): 9.0,
}


def _fetch(sport, date, db_path=None):
    return _FAKE_EM


_ROWS = [
    # agreement (both 'over'), over hit (W) -> agree, no disagree winner
    {"date": "2026-06-26", "sport": "WNBA", "player": "A'ja Wilson", "stat": "PTS",
     "line": "19.5", "direction": "over", "proj": "22.0", "result": "W"},
    # disagree: live 'over' lost -> under hit; EM projects under -> EM was right
    {"date": "2026-06-26", "sport": "WNBA", "player": "Breanna Stewart", "stat": "PTS",
     "line": "19.5", "direction": "over", "proj": "21.0", "result": "L"},
    # disagree: live 'over' won -> over hit; EM projects under -> live was right
    {"date": "2026-06-26", "sport": "WNBA", "player": "Sabrina Ionescu", "stat": "PTS",
     "line": "19.5", "direction": "over", "proj": "21.0", "result": "W"},
    # no EM projection for this (player, stat) -> skipped
    {"date": "2026-06-26", "sport": "WNBA", "player": "Nobody Here", "stat": "PTS",
     "line": "19.5", "direction": "over", "proj": "21.0", "result": "W"},
    # ungraded (blank result) -> skipped
    {"date": "2026-06-26", "sport": "WNBA", "player": "A'ja Wilson", "stat": "REB",
     "line": "8.5", "direction": "over", "proj": "9.0", "result": ""},
]


def test_compare_rows_logic():
    comp = ss.compare_rows(_ROWS, adapter_fetch=_fetch)
    assert len(comp) == 3  # 2 skipped (no EM proj; ungraded)
    by_player = {r["player"]: r for r in comp}

    w = by_player["A'ja Wilson"]
    assert w["actual_over"] == 1 and w["em_side"] == "over" and w["agree"] == 1
    assert w["em_win"] == 1 and w["disagree_winner"] == ""

    s = by_player["Breanna Stewart"]
    assert s["actual_over"] == 0 and s["em_side"] == "under" and s["agree"] == 0
    assert s["em_win"] == 1 and s["live_win"] == 0 and s["disagree_winner"] == "edgemodel"

    i = by_player["Sabrina Ionescu"]
    assert i["actual_over"] == 1 and i["em_side"] == "under" and i["agree"] == 0
    assert i["em_win"] == 0 and i["live_win"] == 1 and i["disagree_winner"] == "live"


def test_summary_counts():
    agg = ss.summarize(ss.compare_rows(_ROWS, adapter_fetch=_fetch))
    allk = agg[("ALL", "ALL")]
    assert allk["n"] == 3
    assert allk["agree"] == 1
    assert allk["disagree"] == 2
    assert allk["em_win_dis"] == 1
    assert allk["live_win_dis"] == 1


def test_empty_adapter_yields_nothing():
    assert ss.compare_rows(_ROWS, adapter_fetch=lambda *a, **k: {}) == []
