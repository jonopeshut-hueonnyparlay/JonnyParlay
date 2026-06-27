"""Tests for engine/source_readiness.py -- the per-market readiness gate.

Pins the two preconditions (min-sample + significant edge) and the Wilson bound,
using synthetic comparison rows.
"""
import source_readiness as sr


def _rows(sport, stat, n_agree, em_wins, live_wins):
    rows = [{"sport": sport, "stat": stat, "agree": "1", "disagree_winner": ""} for _ in range(n_agree)]
    rows += [{"sport": sport, "stat": stat, "agree": "0", "disagree_winner": "edgemodel"} for _ in range(em_wins)]
    rows += [{"sport": sport, "stat": stat, "agree": "0", "disagree_winner": "live"} for _ in range(live_wins)]
    return rows


def test_insufficient_sample_stays_shadow():
    # only 8 disagreements (< MIN_DISAGREE) even though EM wins them all
    m = sr.score(_rows("NBA", "AST", n_agree=10, em_wins=8, live_wins=0))[0]
    assert m["n_disagree"] == 8
    assert m["min_sample_ok"] == 0
    assert m["verdict"] == "insufficient-sample"
    assert m["mode"] == "shadow"


def test_ready_candidate_when_sample_and_edge_clear():
    # 50 disagreements, EM wins 35 (70%) -> Wilson lower bound > 0.5
    m = sr.score(_rows("NBA", "AST", n_agree=20, em_wins=35, live_wins=15))[0]
    assert m["n_disagree"] == 50
    assert m["min_sample_ok"] == 1
    assert m["edge_ok"] == 1
    assert m["verdict"] == "ready-candidate"
    assert m["mode"] == "shadow"   # candidate != promoted; promotion is a separate step


def test_enough_sample_but_no_edge_holds_live():
    # 50 disagreements, EM wins 26 (52%) -> not significantly > 0.5
    m = sr.score(_rows("NBA", "PTS", n_agree=10, em_wins=26, live_wins=24))[0]
    assert m["min_sample_ok"] == 1
    assert m["edge_ok"] == 0
    assert m["verdict"] == "live-source-holds"


def test_wilson_lower_bounds():
    assert sr._wilson_lower(0, 0) == 0.0
    # 35/50 = 0.70; lower bound should clear 0.5 but stay below the point estimate
    lb = sr._wilson_lower(35, 50)
    assert 0.5 < lb < 0.70
