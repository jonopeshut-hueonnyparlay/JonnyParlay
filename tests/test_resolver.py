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
