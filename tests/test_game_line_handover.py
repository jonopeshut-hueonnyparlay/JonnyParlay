"""Tests for engine/game_line_handover.py + its wiring into analyze_mlb (#5).

Covers the blend math, the dormant=no-op contract, manifest-gated weights, and that
the analyze_game_lines MLB pricer actually shifts when a market is promoted.
"""
import csv

import game_line_handover as glh


def _manifest(tmp_path, rows):
    p = tmp_path / "coverage_manifest.csv"
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["sport", "market", "mode", "weight"])
        w.writeheader()
        w.writerows(rows)
    return p


# ── active_weights / prepare ────────────────────────────────────────────────

def test_active_weights_dormant_is_empty(tmp_path):
    man = _manifest(tmp_path, [{"sport": "MLB", "market": "TOTAL", "mode": "shadow", "weight": "0"}])
    assert glh.active_weights(manifest_path=man) == {}


def test_active_weights_promoted_mlb_only(tmp_path):
    man = _manifest(tmp_path, [
        {"sport": "MLB", "market": "TOTAL", "mode": "blend", "weight": "0.4"},
        {"sport": "MLB", "market": "ML", "mode": "live", "weight": "1.0"},
        {"sport": "NBA", "market": "TOTAL", "mode": "blend", "weight": "0.5"},  # not MLB -> excluded
    ])
    w = glh.active_weights(manifest_path=man)
    assert w == {"TOTAL": 0.4, "ML": 1.0}


def test_prepare_dormant_does_not_fetch(tmp_path, monkeypatch):
    # If weights are empty, prepare must NOT touch projections.db (pure no-op).
    import source_shadow_game_lines as gl
    man = _manifest(tmp_path, [{"sport": "MLB", "market": "TOTAL", "mode": "shadow", "weight": "0"}])

    def _boom(*a, **k):
        raise AssertionError("fetch must not be called when dormant")
    monkeypatch.setattr(gl, "fetch_mlb_game_projections", _boom)
    assert glh.prepare("2026-06-26", manifest_path=man) == ({}, {})


# ── blend math ──────────────────────────────────────────────────────────────

_EM = {("NYY", "BOS"): {"proj_total": 9.5, "p_home_win": 0.62}}


def test_blend_total_dormant_returns_live():
    assert glh.blend_total({}, _EM, "NYY", "BOS", 8.0) == 8.0


def test_blend_total_promoted_blends():
    out = glh.blend_total({"TOTAL": 0.5}, _EM, "NYY", "BOS", 8.0)
    assert out == 0.5 * 8.0 + 0.5 * 9.5


def test_blend_total_unmatched_game_returns_live():
    assert glh.blend_total({"TOTAL": 0.5}, _EM, "LAD", "SFG", 8.0) == 8.0


def test_blend_ml_prob_home_and_away():
    home = glh.blend_ml_prob({"ML": 0.5}, _EM, "NYY", "BOS", 0.50, is_home=True)
    assert home == 0.5 * 0.50 + 0.5 * 0.62
    away = glh.blend_ml_prob({"ML": 0.5}, _EM, "NYY", "BOS", 0.50, is_home=False)
    assert away == 0.5 * 0.50 + 0.5 * (1.0 - 0.62)


def test_blend_ml_prob_dormant_returns_live():
    assert glh.blend_ml_prob({}, _EM, "NYY", "BOS", 0.55) == 0.55


# ── wiring: analyze_mlb TOTAL shifts when promoted ──────────────────────────

_MLB_GAME = {
    "id": "evt1", "away_team": "Boston Red Sox", "home_team": "New York Yankees",
    "bookmakers": [{"title": "DraftKings", "markets": [
        {"key": "totals", "outcomes": [
            {"name": "Over", "price": -110, "point": 7.0},
            {"name": "Under", "price": -110, "point": 7.0}]},
    ]}],
}


def _total_over_model(monkeypatch, prepare_ret):
    import analyze_game_lines as agl
    monkeypatch.setattr(agl, "fetch_event_odds", lambda *a, **k: None)
    monkeypatch.setattr(agl._gl_handover, "prepare", lambda *a, **k: prepare_ret)
    agl.ALL_BETS.clear()
    # Dormant total proj = 9.2 (well over the 7.0 line) so the dormant case clears the
    # edge gate and logs a TOTAL OVER; the promoted case (proj_total 12) pushes it higher.
    agl.analyze_mlb([_MLB_GAME], team_projs={"BOS": 4.6, "NYY": 4.6}, ctx_verdicts=None)
    rows = [b for b in agl.ALL_BETS if b.get("label", "").startswith("TOTAL OVER")]
    agl.ALL_BETS.clear()
    return rows[0]["model"] if rows else None


def test_analyze_mlb_total_dormant_vs_promoted(monkeypatch):
    # Dormant: live total proj = 8.0 -> over prob at line 8.0.
    dormant = _total_over_model(monkeypatch, ({}, {}))
    # Promoted fully to EdgeModel with a much higher proj_total -> over prob rises.
    promoted = _total_over_model(
        monkeypatch, ({"TOTAL": 1.0}, {("NYY", "BOS"): {"proj_total": 12.0}}))
    assert dormant is not None and promoted is not None
    assert promoted > dormant
