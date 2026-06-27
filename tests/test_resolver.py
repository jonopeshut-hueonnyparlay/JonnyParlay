"""Tests for engine/resolver.py -- the multi-source projection resolver.

Pins the two contracts that matter: (1) DORMANT = byte-identical pass-through (no
promoted market -> pool untouched), and (2) blend math when a market is promoted.
"""
import resolver
from name_utils import name_key


def _pool():
    return {"NBA": [
        {"name": "Nikola Jokic", "PTS": 28.0, "REB": 12.0},
        {"name": "Jamal Murray", "PTS": 20.0, "REB": 4.0},
    ]}


def _write_manifest(tmp_path, rows):
    p = tmp_path / "coverage_manifest.csv"
    import csv
    with open(p, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["sport", "market", "mode", "weight"])
        w.writeheader()
        w.writerows(rows)
    return p


def test_dormant_is_pass_through(tmp_path, monkeypatch):
    # all 'shadow' -> no active market -> pool returned UNCHANGED (same object, same values)
    monkeypatch.setattr(resolver.ea, "fetch", lambda *a, **k: {(name_key("Nikola Jokic"), "PTS"): 99.0})
    man = _write_manifest(tmp_path, [{"sport": "NBA", "market": "PTS", "mode": "shadow", "weight": 0}])
    pool = _pool()
    out = resolver.resolve_players(pool, "2026-06-26", manifest_path=man)
    assert out is pool
    assert out["NBA"][0]["PTS"] == 28.0  # untouched despite the adapter returning 99


def test_missing_manifest_is_pass_through(tmp_path):
    pool = _pool()
    out = resolver.resolve_players(pool, "2026-06-26", manifest_path=tmp_path / "nope.csv")
    assert out is pool and out["NBA"][0]["PTS"] == 28.0


def test_full_handover_weight_one_swaps_in_edgemodel(tmp_path, monkeypatch):
    monkeypatch.setattr(resolver.ea, "fetch", lambda *a, **k: {
        (name_key("Nikola Jokic"), "PTS"): 30.0, (name_key("Jamal Murray"), "PTS"): 18.0})
    man = _write_manifest(tmp_path, [{"sport": "NBA", "market": "PTS", "mode": "live", "weight": 1.0}])
    out = resolver.resolve_players(_pool(), "2026-06-26", manifest_path=man)
    assert out["NBA"][0]["PTS"] == 30.0  # fully EdgeModel
    assert out["NBA"][1]["PTS"] == 18.0
    assert out["NBA"][0]["REB"] == 12.0  # REB not promoted -> untouched


def test_blend_weight_half(tmp_path, monkeypatch):
    monkeypatch.setattr(resolver.ea, "fetch", lambda *a, **k: {(name_key("Nikola Jokic"), "PTS"): 30.0})
    man = _write_manifest(tmp_path, [{"sport": "NBA", "market": "PTS", "mode": "blend", "weight": 0.5}])
    out = resolver.resolve_players(_pool(), "2026-06-26", manifest_path=man)
    assert out["NBA"][0]["PTS"] == 29.0  # 0.5*28 + 0.5*30


def test_player_without_edgemodel_proj_untouched(tmp_path, monkeypatch):
    monkeypatch.setattr(resolver.ea, "fetch", lambda *a, **k: {(name_key("Nikola Jokic"), "PTS"): 30.0})
    man = _write_manifest(tmp_path, [{"sport": "NBA", "market": "PTS", "mode": "live", "weight": 1.0}])
    out = resolver.resolve_players(_pool(), "2026-06-26", manifest_path=man)
    assert out["NBA"][1]["PTS"] == 20.0  # Murray has no EM proj -> live kept


# ── #6 probability-level / correlated-market blend ──────────────────────────

def test_blend_prob_math_and_clamp():
    import math
    assert math.isclose(resolver.blend_prob(0.4, 0.8, 0.5), 0.6, abs_tol=1e-9)
    assert resolver.blend_prob(0.4, 9.0, 1.0) == 1.0   # clamped to [0,1]
    assert resolver.blend_prob(0.5, "x", 0.5) == 0.5   # non-numeric em -> live kept


def test_blend_marginal_helper():
    assert resolver.blend_marginal(28.0, 30.0, 0.5) == 29.0
    assert resolver.blend_marginal(28.0, None, 0.5) == 28.0   # no em -> live
    assert resolver.blend_marginal(None, 30.0, 0.5) is None   # non-numeric live -> live


def test_promoted_combo_blends_components_not_joint(tmp_path, monkeypatch):
    # Promote the PRA combo: the resolver must blend the COMPONENT marginals
    # (PTS/REB/AST), so the copula re-runs on blended marginals -- not blend a joint.
    jk = name_key("Nikola Jokic")
    monkeypatch.setattr(resolver.ea, "fetch", lambda *a, **k: {
        (jk, "PTS"): 30.0, (jk, "REB"): 10.0, (jk, "AST"): 8.0})
    man = _write_manifest(tmp_path, [{"sport": "NBA", "market": "PRA", "mode": "blend", "weight": 0.5}])
    pool = {"NBA": [{"name": "Nikola Jokic", "PTS": 28.0, "REB": 12.0, "AST": 6.0}]}
    out = resolver.resolve_players(pool, "2026-06-26", manifest_path=man)
    jokic = out["NBA"][0]
    assert jokic["PTS"] == 29.0   # 0.5*28 + 0.5*30
    assert jokic["REB"] == 11.0   # 0.5*12 + 0.5*10
    assert jokic["AST"] == 7.0    # 0.5*6  + 0.5*8


def test_marginal_blend_preserves_copula_vs_naive_joint_blend():
    """The copula is non-linear in the marginals, so blending COMPONENT marginals and
    re-running the single copula gives a DIFFERENT (correct) answer than blending the
    two independently-priced joint combo probabilities -- the #6 anti-pattern."""
    from prob_core import calc_combo_prob
    live = {"PTS": 28.0, "REB": 12.0, "AST": 6.0}
    em = {"PTS": 36.0, "REB": 16.0, "AST": 10.0}
    blended = {k: resolver.blend_marginal(live[k], em[k], 0.5) for k in live}
    line = 50.0
    correct = calc_combo_prob(blended, "PRA", line, sport="NBA")[0]   # single copula on blended marginals
    naive = resolver.blend_prob(
        calc_combo_prob(live, "PRA", line, sport="NBA")[0],
        calc_combo_prob(em, "PRA", line, sport="NBA")[0], 0.5)         # WRONG: blend joints
    assert abs(correct - naive) > 1e-6   # they differ -> marginal blend is not joint blend
