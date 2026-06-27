"""resolver.py -- multi-source projection resolver (coverage_manifest-driven).

Between loading the live player pool and pricing it, blend/swap EdgeModel
projections in per (sport, market) according to data/coverage_manifest.csv. This
is the mechanism for the readiness-gated, per-market handover from the live
source (SaberSim) to EdgeModel.

DORMANT BY DEFAULT: a market is only touched when the manifest marks it mode in
{blend,live} with weight>0 (set deliberately by the Phase-4 weight-ramp, only
after a market clears the readiness gate AND is signed off). With the current
all-'shadow' / no-weight manifest, resolve_players returns the pool UNCHANGED ->
byte-identical to today. Fail-soft: any error returns the pool unchanged (the live
source), so a resolver problem can never break pricing.

Projection-level blend for independent props: p[stat] = (1-w)*live + w*edgemodel.
Correlated / game-line markets are NOT blended here (that needs probability-level
blending to preserve parlay correlation -- added with the game-line path).
"""
import csv
import logging
from pathlib import Path

import edgemodel_adapter as ea
from name_utils import name_key

try:
    from paths import DATA_DIR
except Exception:  # pragma: no cover
    DATA_DIR = Path(__file__).resolve().parent.parent / "data"

log = logging.getLogger("jonnyparlay")

_MANIFEST_PATH = Path(DATA_DIR) / "coverage_manifest.csv"
_ACTIVE_MODES = {"blend", "live"}


def _active_markets(manifest_path=None) -> dict:
    """{(SPORT, STAT): weight} for markets promoted off 'shadow' (mode in {blend,live}, weight>0)."""
    path = Path(manifest_path or _MANIFEST_PATH)
    if not path.exists():
        return {}
    active: dict = {}
    with open(path, "r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            mode = (row.get("mode") or "").strip().lower()
            try:
                w = float(row.get("weight", 0) or 0)
            except (TypeError, ValueError):
                w = 0.0
            if mode in _ACTIVE_MODES and w > 0.0:
                key = ((row.get("sport") or "").upper(), (row.get("market") or "").upper())
                active[key] = min(w, 1.0)
    return active


def resolve_players(all_players: dict, game_date: str, manifest_path=None, db_path=None) -> dict:
    """Blend EdgeModel projections into the live pool per the coverage_manifest.

    DORMANT default -> returns all_players UNCHANGED (byte-identical). Fail-soft:
    returns the live pool unchanged on any error.
    """
    try:
        active = _active_markets(manifest_path)
    except Exception as exc:
        log.warning("resolver: manifest read failed (%s) -- live source unchanged", exc)
        return all_players
    if not active:
        return all_players  # no promoted market -> byte-identical pass-through

    try:
        for sport, players in all_players.items():
            markets = {m: w for (s, m), w in active.items() if s == (sport or "").upper()}
            if not markets:
                continue
            em = ea.fetch(sport, game_date, db_path=db_path)
            if not em:
                continue
            for p in players:
                nk = name_key(p.get("name"))
                for stat, w in markets.items():
                    em_proj = em.get((nk, stat))
                    live_proj = p.get(stat)
                    if em_proj is not None and isinstance(live_proj, (int, float)):
                        p[stat] = (1.0 - w) * live_proj + w * em_proj
            log.info("resolver: blended %d EdgeModel market(s) into %s pool", len(markets), sport)
    except Exception as exc:  # pragma: no cover - never break pricing
        log.warning("resolver: blend failed (%s) -- live source unchanged", exc)
    return all_players
