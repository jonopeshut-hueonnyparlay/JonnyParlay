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

try:
    # Combo (correlated) markets -> their component marginals. Blending a combo means
    # blending each COMPONENT projection so the copula (COMBO_RHO) re-runs on blended
    # marginals downstream -- NOT blending the joint combo probability.
    from calibrated import COMBO_COMPONENTS
except Exception:  # pragma: no cover
    COMBO_COMPONENTS = {}

log = logging.getLogger("jonnyparlay")

_MANIFEST_PATH = Path(DATA_DIR) / "coverage_manifest.csv"
_ACTIVE_MODES = {"blend", "live"}

try:
    from pick_log_schema import LIVE_SOURCE
except Exception:  # pragma: no cover
    LIVE_SOURCE = "sabersim"


def _source_label(weight: float) -> str:
    """Provenance label for a market priced at blend `weight` on EdgeModel.

    w>=1.0 -> fully 'edgemodel'; 0<w<1 -> 'blend:<w>'; otherwise the live source.
    """
    if weight >= 1.0:
        return "edgemodel"
    if weight > 0.0:
        return f"blend:{weight:.3f}"
    return LIVE_SOURCE


def source_map(manifest_path=None) -> dict:
    """{(SPORT, STAT): source_label} for markets promoted off 'shadow'. Markets not
    present are priced by the live source (caller defaults to LIVE_SOURCE). Today's
    all-'shadow' manifest -> {} (every bet's source is the live source). Fail-soft."""
    try:
        return {k: _source_label(w) for k, w in _active_markets(manifest_path).items()}
    except Exception as exc:  # pragma: no cover
        log.warning("resolver.source_map failed (%s)", exc)
        return {}


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


def blend_marginal(live, em, w: float):
    """Projection-level blend of one marginal: (1-w)*live + w*em. Live unchanged if em
    is absent or live isn't numeric."""
    if em is None or not isinstance(live, (int, float)):
        return live
    return (1.0 - w) * live + w * em


def blend_prob(live_p: float, em_p: float, w: float) -> float:
    """Probability-level blend of ONE marginal probability, clamped to [0,1].

    For a CORRELATED multi-leg market (combo / same-game / SGP), blend each leg's
    MARGINAL (projection via blend_marginal, or marginal prob here) and then re-run the
    single copula (calc_combo_prob / the SGP sampler) ONCE on the blended marginals.
    NEVER blend the joint/parlay probability of independently-priced legs -- that
    discards the copula's correlation and double-counts the blend. See
    _blend_market_into_player: a promoted combo market blends its COMPONENTS, not 'PRA'.
    """
    try:
        return max(0.0, min(1.0, (1.0 - w) * float(live_p) + w * float(em_p)))
    except (TypeError, ValueError):
        return live_p


def _blend_market_into_player(p: dict, nk: str, market: str, w: float, em: dict) -> None:
    """Blend one promoted market into player p (in place). Simple stats blend their own
    projection; combo markets blend each component marginal so the copula re-runs on the
    blended marginals (correlation preserved), never on a blended joint probability."""
    components = COMBO_COMPONENTS.get(market, (market,))
    for comp in components:
        em_proj = em.get((nk, comp))
        if em_proj is not None and isinstance(p.get(comp), (int, float)):
            p[comp] = blend_marginal(p[comp], em_proj, w)


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
                for market, w in markets.items():
                    _blend_market_into_player(p, nk, market, w, em)
            log.info("resolver: blended %d EdgeModel market(s) into %s pool", len(markets), sport)
    except Exception as exc:  # pragma: no cover - never break pricing
        log.warning("resolver: blend failed (%s) -- live source unchanged", exc)
    return all_players
