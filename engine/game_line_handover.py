"""game_line_handover.py -- readiness-gated MLB game-line blend (resolver for game lines).

The game-line analogue of resolver.py. When the coverage_manifest promotes an MLB
game-line market (TOTAL / ML, mode in {blend,live}, weight>0), blend EdgeModel's
starter-aware mlb_game_projections into the live (SaberSim-derived) projection:

    total      = (1-w)*live_total      + w*em_proj_total
    p_home_win = (1-w)*live_p_home_win + w*em_p_home_win

DORMANT BY DEFAULT: with the all-'shadow' manifest, prepare() returns empty weights
and the blend_* helpers return the live value UNCHANGED -> byte-identical to today
(gated by replay/run_replay.py for evaluators and test_game_line_golden_master for
analyze_game_lines). Fail-soft: any error returns the live value / empty weights, so
a handover problem can never break game-line pricing. MLB only -- EdgeModel has no
game-line projections for other sports.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

_ENGINE = Path(__file__).resolve().parent
if str(_ENGINE) not in sys.path:
    sys.path.insert(0, str(_ENGINE))

log = logging.getLogger("jonnyparlay")

_GL_MARKETS = ("TOTAL", "ML")


def active_weights(manifest_path=None) -> dict:
    """{'TOTAL': w, 'ML': w} for promoted MLB game-line markets; {} when dormant."""
    try:
        import resolver
        active = resolver._active_markets(manifest_path)  # {(SPORT, MARKET): w}
    except Exception as exc:  # pragma: no cover
        log.warning("game_line_handover: manifest read failed (%s)", exc)
        return {}
    return {m: w for (s, m), w in active.items() if s == "MLB" and m in _GL_MARKETS}


def prepare(game_date: str, manifest_path=None, db_path=None) -> tuple[dict, dict]:
    """(weights, em_projections) for promoted MLB game-line markets.

    Returns ({}, {}) when no game-line market is promoted -- and in that case does NOT
    touch projections.db, so the dormant path is a pure no-op. em_projections is keyed
    {(HOME_ABBR, AWAY_ABBR): {...}} (source_shadow_game_lines.fetch_mlb_game_projections).
    """
    weights = active_weights(manifest_path)
    if not weights:
        return {}, {}
    try:
        from source_shadow_game_lines import fetch_mlb_game_projections
        em = fetch_mlb_game_projections(game_date, db_path=db_path)
    except Exception as exc:  # pragma: no cover
        log.warning("game_line_handover: EdgeModel projection fetch failed (%s)", exc)
        em = {}
    return (weights if em else {}), em


def _proj_for(em: dict, home_abbr: str, away_abbr: str):
    return em.get(((home_abbr or "").upper(), (away_abbr or "").upper())) if em else None


def blend_total(weights: dict, em: dict, home_abbr: str, away_abbr: str,
                live_total: float) -> float:
    """Blend EdgeModel proj_total into the live game total. Live value unchanged when
    TOTAL isn't promoted or EdgeModel has no projection for the game."""
    w = weights.get("TOTAL")
    if not w:
        return live_total
    g = _proj_for(em, home_abbr, away_abbr)
    if not g or g.get("proj_total") is None:
        return live_total
    try:
        return (1.0 - w) * live_total + w * float(g["proj_total"])
    except (TypeError, ValueError):
        return live_total


def blend_ml_prob(weights: dict, em: dict, home_abbr: str, away_abbr: str,
                  live_p: float, is_home: bool = True) -> float:
    """Blend EdgeModel's win prob into a live ML win prob. The EdgeModel target is
    p_home_win for the home side, 1-p_home_win for the away side. Live value unchanged
    when ML isn't promoted or EdgeModel has no projection for the game."""
    w = weights.get("ML")
    if not w:
        return live_p
    g = _proj_for(em, home_abbr, away_abbr)
    if not g or g.get("p_home_win") is None:
        return live_p
    try:
        em_p = float(g["p_home_win"]) if is_home else (1.0 - float(g["p_home_win"]))
        return (1.0 - w) * live_p + w * em_p
    except (TypeError, ValueError):
        return live_p
