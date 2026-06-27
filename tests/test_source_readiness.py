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


def _rows_brier(sport, stat, n_agree, em_wins, live_wins, em_brier, live_brier):
    rows = _rows(sport, stat, n_agree, em_wins, live_wins)
    for r in rows:
        r["em_brier"], r["live_brier"] = str(em_brier), str(live_brier)
    return rows


def test_brier_veto_holds_live_when_edgemodel_scores_worse():
    # disagreements favour EM (edge_ok) BUT EM's Brier is worse (0.30 > 0.20) -> vetoed
    m = sr.score(_rows_brier("NBA", "AST", 20, 35, 15, em_brier=0.30, live_brier=0.20))[0]
    assert m["edge_ok"] == 1 and m["brier_edge"] < 0
    assert m["verdict"] == "live-source-holds"


def test_ready_candidate_when_disagreement_and_brier_agree():
    m = sr.score(_rows_brier("NBA", "AST", 20, 35, 15, em_brier=0.18, live_brier=0.25))[0]
    assert m["brier_edge"] > 0
    assert m["verdict"] == "ready-candidate"


def test_ramp_target_weight_zero_until_ready_then_shrunk():
    # not ready -> target 0
    m = sr.score(_rows("NBA", "AST", 10, 8, 0))[0]
    assert m["target_weight"] == 0.0 and m["weight"] == 0.0
    # strongly-better ready market -> capped, shrunk target in (0, W_MAX]
    m2 = sr.score(_rows_brier("NBA", "AST", 20, 45, 5, em_brier=0.15, live_brier=0.25))[0]
    assert m2["verdict"] == "ready-candidate"
    assert 0.0 < m2["target_weight"] <= sr.RAMP_W_MAX
    assert m2["weight"] == 0.0  # LIVE weight stays 0 until promote()


def test_promote_then_demote_round_trip(tmp_path):
    rows = sr.score(_rows_brier("NBA", "AST", 20, 45, 5, em_brier=0.15, live_brier=0.25))
    man = tmp_path / "coverage_manifest.csv"
    import csv as _csv
    with open(man, "w", encoding="utf-8", newline="") as f:
        w = _csv.DictWriter(f, fieldnames=sr._MANIFEST_FIELDS)
        w.writeheader(); w.writerows(rows)

    assert sr.promote("NBA", "AST", manifest_path=man) is True
    got = {r["market"]: r for r in _csv.DictReader(open(man, encoding="utf-8"))}["AST"]
    assert got["mode"] == "blend" and float(got["weight"]) > 0.0

    assert sr.demote("NBA", "AST", manifest_path=man) is True
    got2 = {r["market"]: r for r in _csv.DictReader(open(man, encoding="utf-8"))}["AST"]
    assert got2["mode"] == "shadow" and float(got2["weight"]) == 0.0


def test_promote_noop_when_no_target_weight(tmp_path):
    rows = sr.score(_rows("NBA", "PTS", 10, 5, 5))  # not ready -> target_weight 0
    man = tmp_path / "coverage_manifest.csv"
    import csv as _csv
    with open(man, "w", encoding="utf-8", newline="") as f:
        w = _csv.DictWriter(f, fieldnames=sr._MANIFEST_FIELDS)
        w.writeheader(); w.writerows(rows)
    assert sr.promote("NBA", "PTS", manifest_path=man) is False  # nothing to promote


def test_run_ingests_game_line_comparison(tmp_path):
    import csv as _csv
    pc = tmp_path / "compare.csv"
    with open(pc, "w", encoding="utf-8", newline="") as f:
        w = _csv.DictWriter(f, fieldnames=["sport", "stat", "agree", "disagree_winner"])
        w.writeheader()
        w.writerow({"sport": "NBA", "stat": "PTS", "agree": "1", "disagree_winner": ""})
    gl = tmp_path / "gl.csv"
    with open(gl, "w", encoding="utf-8", newline="") as f:
        w = _csv.DictWriter(f, fieldnames=["market", "agree", "disagree_winner"])
        w.writeheader()
        w.writerow({"market": "TOTAL", "agree": "0", "disagree_winner": "edgemodel"})
    out = sr.run(compare_path=pc, manifest_path=tmp_path / "m.csv", gl_compare_path=gl)
    markets = {(m["sport"], m["market"]) for m in out}
    assert ("MLB", "TOTAL") in markets   # game-line market promoted into the manifest
    assert ("NBA", "PTS") in markets


def test_wilson_lower_bounds():
    assert sr._wilson_lower(0, 0) == 0.0
    # 35/50 = 0.70; lower bound should clear 0.5 but stay below the point estimate
    lb = sr._wilson_lower(35, 50)
    assert 0.5 < lb < 0.70
