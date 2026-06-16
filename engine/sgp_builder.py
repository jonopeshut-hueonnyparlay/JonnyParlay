"""sgp_builder.py -- Same-Game Parlay builder for JonnyParlay.
NBA only. 3-4 legs, +200-+450 target range.
Sizing: 0.25u default, 0.50u when copula EV margin ≥ 0.10 + cohesion ≥ 0.55 + avg edge ≥ 0.035.
Usage: python sgp_builder.py <csv> [--dry-run] [--confirm] [--test]

Design rationale (Apr 2026 redesign + L8 copula update May 2026):
  - 6-leg SGPs have 7x worse EV than singles (Wizard of Odds). Correlation
    uplift (~35%) can't close the gap to break even at +400-700.
  - 3-4 legs: at 0.68+ avg WP with 35% correlation uplift, joint prob
    exceeds the +200-+300 implied probability — real edge is possible.
  - Search space: C(40,4) = 91k vs C(25,6) = 177k. Faster with better results.
  - BetMGM is preferred book (independently measured 2-3% better SGP pricing).
  - L8 (May 2026): Gaussian copula joint probability replaces independence-based
    scoring and the raw avg_wp >= 0.70 sizing gate.  Fast equicorrelation approx
    Full 300-sample MC used during the combo ranking pass; 4000-sample MC used once for final sizing/display.
    Embed now shows "Copula joint: X% | Implied: Y% (+Zpp)" for transparency.
"""
from __future__ import annotations

import csv
import json
import math
import os
import sys
import time
import argparse
from collections import Counter
from datetime import datetime, timezone, timedelta
from itertools import combinations
from pathlib import Path
from zoneinfo import ZoneInfo

# -- Engine imports --------------------------------------------------------
_ENGINE_DIR = Path(__file__).resolve().parent
if str(_ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(_ENGINE_DIR))

from brand import BRAND_TAGLINE
from book_names import display_book
from secrets_config import require_odds_api_key, DISCORD_BONUS_WEBHOOK

# -- Constants -------------------------------------------------------------

SGP_SIZE_DEFAULT = 0.25
SGP_SIZE_PREMIUM = 0.50   # unlocked when avg WP + cohesion + edge all strong (see size_sgp)
SGP_SIZE = SGP_SIZE_DEFAULT  # backwards-compat alias used by _log_sgp

MIN_LEGS = 3
MAX_LEGS = 4
MIN_PARLAY_ODDS = 200        # 3-leg at 0.68 WP avg lands ~+220; 4-leg ~+350
MAX_PARLAY_ODDS = 450        # keeps it out of pure lottery territory
MIN_LEG_EDGE = 0.010         # lowered from 0.005 — any signal counts at this pool stage
MIN_LEG_WIN_PROB = 0.65      # floor: 0.65^3 = 29% × 1.35 corr = 39% > +200 implied 33%
IDEAL_LEG_WIN_PROB = 0.70    # target: 0.70^3 = 34% × 1.35 corr = 46% — clearly +EV
MAX_LEG_ODDS = -115          # loosened: -130 to -149 alt lines excluded before were good value
                              # floor still screens out uncorrelated junk (+100 etc.)
# Plan 9 §9H: joint-EV existence floor. Per-leg WP floors alone can construct -EV
# slips on the 4-leg path (the +200-450 window forces per-leg implied 0.653-0.760,
# above the 0.65/0.62 floors). ANY slip must clear: copula joint prob >
# implied(parlay odds) + margin. The premium-sizing gate (margin >= 0.10) is separate.
# DATA_GATED: re-tune at n=100 scored SGP slips.
SGP_JOINT_EV_MARGIN = 0.025
ODDS_BASE = "https://api.the-odds-api.com/v4"
ODDS_REGIONS = "us,us2,us_ex"
API_SLEEP = 1.3

STAT_COLS = {"PTS": "PTS", "AST": "AST", "REB": "RB", "3PM": "3PT"}

SIGMA = {
    "PTS": {"mult": 0.35, "min": 5.0},  # synced with run_picks.py (raised 4.5→5.0, 2026-05-25)
    # AST moved to NB_STATS (r=9.66) — no longer Normal path.
    # REB moved to NB_STATS (r=13.16) — no longer Normal path.
    # "3PM" intentionally absent — NB_STATS/NB_R. Do NOT add to SIGMA.
}
POISSON_STATS: set = set()  # AST and REB moved to NB_STATS; nothing left Poisson in SGP
POISSON_CUTOFF = 8.5

# P16 (M1, May 1 2026): Negative Binomial for overdispersed count stats.
# Mirrors NB_STATS / NB_R in run_picks.py — keep in sync.
# r values from engine/nb_calibrate.py (within-player conditional variance method).
NB_STATS = {"3PM", "AST", "REB", "BLK", "STL"}
NB_R = {
    "3PM": 9.15,   # recalibrated 2026-05-25: 1246 player-seasons, avg(var/mu)=1.1486 (was 2.1/12.3)
    "AST": 9.66,   # P1.3 2026-06-16: bias-corrected (Jensen MoM), EdgeModel producer. Was 12.16. Keep in sync with calibrated.py NB_R.
    "REB": 13.16,  # P1.3 2026-06-16: bias-corrected (Jensen MoM), EdgeModel producer. Was 14.7. Keep in sync with calibrated.py NB_R.
    "BLK": 2.8,    # empirical per-game r; Research Brief 5, 2026-05-02
    "STL": 3.6,    # empirical per-game r; Research Brief 5, 2026-05-02
}


# -- Correlation rules -----------------------------------------------------

def _correlation_tags(leg):
    """Return team-scoped correlation group tags for a leg."""
    tags = set()
    team = leg["team"]
    stat = leg["stat"]
    direction = leg["direction"]
    # Offensive flow -- PTS, AST, 3PM overs on the SAME team
    if stat in ("PTS", "AST", "3PM") and direction == "over":
        tags.add(f"team_off_{team}")
    # Rebound control -- REB overs on same team
    if stat == "REB" and direction == "over":
        tags.add(f"team_reb_{team}")
    # Defensive dominance -- unders on opposing players (same team)
    if direction == "under" and stat in ("PTS", "AST", "3PM"):
        tags.add(f"team_def_vs_{team}")
    # Slow-game thesis -- cross-team under stacks share a game-level tag so that
    # e.g. OKC unders + SAS unders in the same game score cohesion correctly.
    # pairwise_rho already assigns ρ=0.08 for cross-team unders; this tag lets
    # the cohesion score reflect that shared game-script narrative.
    if direction == "under" and stat in ("PTS", "AST", "3PM", "REB"):
        game = leg.get("game", "")
        if game:
            game_key = game.lower().replace(" @ ", "_at_").replace(" ", "_")
            tags.add(f"game_under_{game_key}")
    return tags


# Cross-stat tension pairs: (stat_under, stat_over) on the SAME player
# that work against each other. Under 3PM + Over PTS = tension because
# fewer threes means fewer points from beyond the arc.
_CROSS_STAT_TENSION = {
    ("3PM", "PTS"),   # fewer 3s hurts total scoring (for players in 3PM markets)
    ("PTS", "AST"),   # low scoring + high assists is rare (need possessions to assist)
    # NOTE: (AST, PTS) intentionally EXCLUDED -- iso scorer games (U AST + O PTS)
    # are a real playoff archetype (e.g. Edwards drops 35 with 2 assists).
}


def _is_negatively_correlated(leg_a, leg_b):
    """Return True if two legs conflict -- HARD KILL, never combine."""
    # R0: Same player, same stat, same direction = DEDUP (any line, including exact duplicate)
    # e.g. DiVincenzo O9.5 PTS + O8.5 PTS -- redundant (9.5 dominates 8.5)
    if (leg_a["player"] == leg_b["player"]
            and leg_a["stat"] == leg_b["stat"]
            and leg_a["direction"] == leg_b["direction"]):
        return True

    # R1: Same player, same stat, opposite direction
    if (leg_a["player"] == leg_b["player"]
            and leg_a["stat"] == leg_b["stat"]
            and leg_a["direction"] != leg_b["direction"]):
        return True

    # R2: Same team, same stat, opposite direction (different players)
    if (leg_a["team"] == leg_b["team"]
            and leg_a["stat"] == leg_b["stat"]
            and leg_a["direction"] != leg_b["direction"]
            and leg_a["player"] != leg_b["player"]):
        return True

    # R3: Same player cross-stat tension
    # e.g. Naz Reid Under 2.5 3PM + Naz Reid Over 8.5 PTS
    if leg_a["player"] == leg_b["player"]:
        for under_leg, over_leg in [(leg_a, leg_b), (leg_b, leg_a)]:
            if under_leg["direction"] == "under" and over_leg["direction"] == "over":
                pair = (under_leg["stat"], over_leg["stat"])
                if pair in _CROSS_STAT_TENSION:
                    return True

    # R4: Cross-team overs are soft tension (no hard kill).
    # Cohesion score naturally penalizes since they won't share tags.
    return False


def _check_parlay_correlations(legs):
    for a, b in combinations(legs, 2):
        if _is_negatively_correlated(a, b):
            return False
    return True


# -- Math (consolidated in quant/distributions.py) -------------------------
# Previously private copies of run_picks.py's distribution math; now the single
# canonical implementation, aliased to the historical underscore names.
from quant.distributions import (
    poisson_pmf as _poisson_pmf,
    poisson_cdf as _poisson_cdf,
    normal_cdf as _normal_cdf,
    negbinom_pmf as _negbinom_pmf,
    negbinom_cdf as _negbinom_cdf,
)

from quant.odds import implied_prob as _implied_prob

def _fair_prob(proj, line, stat, direction):
    if stat in POISSON_STATS and line <= POISSON_CUTOFF:
        k = math.floor(line)
        if line == k:
            push = _poisson_pmf(k, proj)
            strict_over = 1.0 - _poisson_cdf(k, proj)
            strict_under = _poisson_cdf(k - 1, proj)
            non_push = 1.0 - push
            if non_push > 0:
                over_p = strict_over / non_push
                under_p = strict_under / non_push
            else:
                over_p, under_p = 0.5, 0.5
        else:
            under_p = _poisson_cdf(k, proj)
            over_p = 1.0 - under_p
    elif stat in NB_STATS:
        # P16 (M1) — Negative binomial for overdispersed count stats (3PM, AST, REB, BLK, STL).
        r = NB_R[stat]
        k = math.floor(line)
        if line == k:  # integer line — push-adjusted
            push = _negbinom_pmf(k, proj, r)
            strict_over = 1.0 - _negbinom_cdf(k, proj, r)
            strict_under = _negbinom_cdf(k - 1, proj, r)
            non_push = 1.0 - push
            if non_push > 0:
                over_p = strict_over / non_push
                under_p = strict_under / non_push
            else:
                over_p, under_p = 0.5, 0.5
        else:  # half-integer line — no push
            under_p = _negbinom_cdf(k, proj, r)
            over_p = 1.0 - under_p
    else:
        s = SIGMA.get(stat, {"mult": 0.40, "min": 2.0})
        sigma = max(proj * s["mult"], s["min"])
        under_p = _normal_cdf(line, proj, sigma)
        over_p = 1.0 - under_p
    return over_p if direction == "over" else under_p


# -- Gaussian copula joint probability (L8, May 2026) ----------------------
# Rationale: multiplying independent leg probabilities underestimates the
# true joint hit rate when legs share game-script correlation.  The copula
# captures this uplift for the sizing gate and embed display.
# Full MC (4000 samples, ~2 ms) is used only on the final chosen SGP;
# the fast equicorrelation approx is used during the 91k-combo search.

# Pure copula math consolidated in quant/copula.py; aliased to the historical
# underscore names so internal call sites and `from sgp_builder import ...`
# (used by mlb_sgp_builder.py) keep resolving. _pairwise_rho / _build_corr_matrix
# stay below — they encode NBA correlation domain logic, not generic math.
from quant.copula import (
    probit as _probit,
    cholesky as _cholesky,
    copula_joint_prob as _copula_joint_prob,
    copula_joint_approx as _copula_joint_approx,
)


# Provenance for the NBA SGP ρ values below (audit P1.5 / S4g-4/5). There is no
# JSON ρ matrix — the values are hardcoded in _pairwise_rho(); this is the audit
# trail. health_check asserts this meta is present and that _pairwise_rho still
# returns the canonical values (regression guard against silent ρ edits).
# When the ρ values change, bump `version` and `fit_date` in the SAME commit.
_NBA_SGP_RHO_META = {
    "version": "1.0",
    "fit_date": "2026-05 (L8)",          # best signal available; see notes
    "source": "empirical NBA game-log correlation analysis (L8, May 2026)",
    "n_observations": "unrecorded",      # P1.5: not captured at fit time — audit gap
    "model": "Gaussian copula pairwise rho",
    "frozen": True,
    "notes": "Hardcoded in _pairwise_rho() (no JSON artifact). Conservative "
             "(rho<0.40) so the copula joint estimate is a floor, not a ceiling. "
             "n_observations was never recorded at fit time.",
}


def _pairwise_rho(leg_a, leg_b):
    """Pairwise Gaussian copula correlation ρ for two SGP legs.

    Provenance: see _NBA_SGP_RHO_META (audit P1.5). Calibrated from empirical NBA
    game-log correlation analysis (L8, ~May 2026; n unrecorded). Values are
    conservative (ρ < 0.40) because we want the copula estimate to be a floor,
    not an optimistic ceiling.

    Hierarchy (highest ρ first):
      1. Same-team offensive flow — PTS/AST/3PM overs:       ρ = 0.35
      2. Same-player multi-stat (same direction):             ρ = 0.28
      3. Same-team REB overs:                                 ρ = 0.20
      4. Same-team, same direction, other combos:             ρ = 0.15
      5. Cross-team overs (same game, game-pace link):        ρ = 0.10
      6. Cross-team unders (same game):                       ρ = 0.08
      7. Same-team mixed direction (soft tension):            ρ = -0.10
      8. Same-player opposite direction (killed by R1 first): ρ = -0.20
      9. Unrelated / different games:                         ρ = 0.00
    """
    # Same player
    if leg_a["player"] == leg_b["player"]:
        return 0.28 if leg_a["direction"] == leg_b["direction"] else -0.20

    off_stats = {"PTS", "AST", "3PM"}
    # Same team
    if leg_a["team"] == leg_b["team"]:
        same_dir = leg_a["direction"] == leg_b["direction"]
        if (leg_a["stat"] in off_stats and leg_b["stat"] in off_stats
                and leg_a["direction"] == "over" and leg_b["direction"] == "over"):
            return 0.35
        if (leg_a["stat"] == "REB" and leg_b["stat"] == "REB"
                and leg_a["direction"] == "over" and leg_b["direction"] == "over"):
            return 0.20
        return 0.15 if same_dir else -0.10

    # Different teams, same game — game-pace / total correlation
    if leg_a.get("game") and leg_a.get("game") == leg_b.get("game"):
        if leg_a["direction"] == "over" and leg_b["direction"] == "over":
            return 0.10
        if leg_a["direction"] == "under" and leg_b["direction"] == "under":
            return 0.08
        return 0.02

    return 0.0


def _build_corr_matrix(legs):
    """Build n×n Gaussian copula correlation matrix from pairwise ρ values."""
    n = len(legs)
    return [[1.0 if i == j else _pairwise_rho(legs[i], legs[j])
             for j in range(n)] for i in range(n)]


# Odds<->decimal converters consolidated in quant/odds.py; aliased to the historical
# underscore names so `from sgp_builder import _american_to_decimal, ...` (used by
# mlb_sgp_builder.py) keeps resolving.
from quant.odds import (
    american_to_decimal as _american_to_decimal,
    decimal_to_american as _decimal_to_american,
)


# -- CSV loader ------------------------------------------------------------

def load_projections(csv_path):
    players = {}
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row.get("Name", "").strip()
            team = row.get("Team", "").strip()
            if not name or not team:
                continue
            proj = {}
            for our_stat, csv_col in STAT_COLS.items():
                val = row.get(csv_col, "")
                try:
                    proj[our_stat] = float(val)
                except (ValueError, TypeError):
                    pass
            if proj:
                name_key = name.lower().strip()
                players[name_key] = {"name": name, "team": team, "proj": proj}
    return players


# -- Odds API --------------------------------------------------------------

def _api_get(url, params):
    import requests
    from http_utils import default_headers
    params["apiKey"] = require_odds_api_key()
    r = requests.get(url, params=params, headers=default_headers(), timeout=15)
    r.raise_for_status()
    return r.json()


def fetch_nba_events():
    events = _api_get(f"{ODDS_BASE}/sports/basketball_nba/events", {})
    now = datetime.now(timezone.utc)
    co_tz = ZoneInfo("America/Denver")
    local_now = now.astimezone(co_tz)
    local_midnight = local_now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    end_utc = local_midnight.astimezone(timezone.utc)
    upcoming = []
    for e in (events or []):
        ct = e.get("commence_time", "").replace("Z", "+00:00")
        try:
            ct_dt = datetime.fromisoformat(ct)
        except Exception:
            continue
        if ct_dt < end_utc and now < ct_dt:
            upcoming.append(e)
    return upcoming


def fetch_event_props(event_id):
    markets = "player_points,player_assists,player_rebounds,player_threes"
    time.sleep(API_SLEEP)
    resp = _api_get(
        f"{ODDS_BASE}/sports/basketball_nba/events/{event_id}/odds",
        {"regions": ODDS_REGIONS, "markets": markets, "oddsFormat": "american"},
    )
    stat_map = {
        "player_points": "PTS", "player_assists": "AST",
        "player_rebounds": "REB", "player_threes": "3PM",
    }
    best = {}
    all_outcomes = {}
    book_all = {}   # key -> {book: best_odds_that_book_offers}
    bookmakers = resp.get("bookmakers", []) if isinstance(resp, dict) else []
    for bk in bookmakers:
        book = bk["key"]
        for mkt in bk.get("markets", []):
            stat = stat_map.get(mkt["key"])
            if not stat:
                continue
            for o in mkt.get("outcomes", []):
                player = o.get("description", "")
                direction = o.get("name", "").lower()
                line = o.get("point")
                odds = o.get("price")
                if not player or line is None or odds is None:
                    continue
                side_key = (player, stat, line)
                if side_key not in all_outcomes:
                    all_outcomes[side_key] = {}
                existing = all_outcomes[side_key].get(direction)
                if existing is None or odds > existing[0]:
                    all_outcomes[side_key][direction] = (odds, book)
                key = (player, stat, line, direction)
                if key not in best or odds > best[key]["odds"]:
                    best[key] = {"odds": odds, "book": book}
                if key not in book_all:
                    book_all[key] = {}
                if book not in book_all[key] or odds > book_all[key][book]:
                    book_all[key][book] = odds
    for (player, stat, line, direction), info in best.items():
        other_dir = "under" if direction == "over" else "over"
        side_key = (player, stat, line)
        other = all_outcomes.get(side_key, {}).get(other_dir)
        info["other_side_odds"] = other[0] if other else None
        info["book_odds"] = book_all.get((player, stat, line, direction),
                                         {info["book"]: info["odds"]})
    return best


def fetch_event_props_from_cache(cached_data, event_id):
    stat_map = {
        "player_points": "PTS", "player_assists": "AST",
        "player_rebounds": "REB", "player_threes": "3PM",
    }
    best = {}
    all_outcomes = {}
    book_all = {}
    for cache_key, cache_val in cached_data.get("props", {}).items():
        if not cache_key.startswith(event_id):
            continue
        if isinstance(cache_val, dict):
            bookmakers = cache_val.get("bookmakers", [])
        elif isinstance(cache_val, list):
            bookmakers = cache_val
        else:
            continue
        for bk in bookmakers:
            if not isinstance(bk, dict):
                continue
            book = bk.get("key", "")
            for mkt in bk.get("markets", []):
                stat = stat_map.get(mkt.get("key"))
                if not stat:
                    continue
                for o in mkt.get("outcomes", []):
                    player = o.get("description", "")
                    direction = o.get("name", "").lower()
                    line = o.get("point")
                    odds = o.get("price")
                    if not player or line is None or odds is None:
                        continue
                    side_key = (player, stat, line)
                    if side_key not in all_outcomes:
                        all_outcomes[side_key] = {}
                    existing = all_outcomes[side_key].get(direction)
                    if existing is None or odds > existing[0]:
                        all_outcomes[side_key][direction] = (odds, book)
                    key = (player, stat, line, direction)
                    if key not in best or odds > best[key]["odds"]:
                        best[key] = {"odds": odds, "book": book}
                    if key not in book_all:
                        book_all[key] = {}
                    if book not in book_all[key] or odds > book_all[key][book]:
                        book_all[key][book] = odds
    for (player, stat, line, direction), info in best.items():
        other_dir = "under" if direction == "over" else "over"
        other = all_outcomes.get((player, stat, line), {}).get(other_dir)
        info["other_side_odds"] = other[0] if other else None
        info["book_odds"] = book_all.get((player, stat, line, direction),
                                         {info["book"]: info["odds"]})
    return best


# -- SGP construction ------------------------------------------------------

def _normalize_name(name):
    return name.lower().strip()


def build_candidate_legs(projections, odds_data, event):
    away = event.get("away_team", "")
    home = event.get("home_team", "")
    candidates = []
    for (player, stat, line, direction), info in odds_data.items():
        odds = info["odds"]
        book = info["book"]
        other_odds = info.get("other_side_odds")
        name_key = _normalize_name(player)
        proj_data = projections.get(name_key)
        if not proj_data or stat not in proj_data["proj"]:
            continue
        proj_val = proj_data["proj"][stat]
        team = proj_data["team"]
        if proj_val <= 0:
            continue
        fair = _fair_prob(proj_val, line, stat, direction)
        imp = _implied_prob(odds)
        if other_odds is not None:
            imp_other = _implied_prob(other_odds)
            total_imp = imp + imp_other
            nv_imp = imp / total_imp if total_imp > 0 else imp
        else:
            nv_imp = imp
        edge = fair - nv_imp
        if edge < MIN_LEG_EDGE:
            continue
        if fair < MIN_LEG_WIN_PROB:
            continue
        if odds > MAX_LEG_ODDS:   # reject anything not juiced enough (e.g. +100, -110 etc.)
            continue
        if odds < -300:
            continue
        if book not in SGP_ALLOWED_BOOKS:
            continue
        # Composite pool score: blends edge (sharp signal) with excess WP above
        # the floor (hit rate signal). Only WP above MIN_LEG_WIN_PROB matters —
        # we're rewarding legs that are comfortably safe, not just barely passing.
        wp_excess = max(0.0, fair - MIN_LEG_WIN_PROB)
        pool_score = edge * 0.40 + wp_excess * 0.60
        candidates.append({
            "player": player, "stat": stat, "line": line,
            "direction": direction, "proj": proj_val, "fair_prob": fair,
            "nv_imp": nv_imp, "edge": edge, "odds": odds, "book": book,
            "book_odds": info.get("book_odds", {book: odds}),
            "team": team, "game": f"{away} @ {home}",
            "pool_score": pool_score,
        })
    # Sort pool by composite score — high WP + edge both matter
    candidates.sort(key=lambda x: x["pool_score"], reverse=True)
    return candidates


def _parlay_american(legs):
    dec = 1.0
    for leg in legs:
        dec *= _american_to_decimal(leg["odds"])
    return _decimal_to_american(dec)


def _correlation_cohesion(legs):
    total_pairs = 0
    linked_pairs = 0
    for a, b in combinations(legs, 2):
        total_pairs += 1
        if _correlation_tags(a) & _correlation_tags(b):
            linked_pairs += 1
    return linked_pairs / total_pairs if total_pairs > 0 else 0.0


def _score_sgp(legs):
    """Score an SGP. Philosophy: 3-4 tight legs that tell one game-script story.

    Weight rationale (L8 update, May 2026):
      copula    0.30 — replaces avg_wp juice_score; accounts for inter-leg
                        correlation when estimating the true joint hit rate.
                        Uses full 300-sample MC copula (ranking pass).
      edge      0.25 — per-leg model edge; still the sharpest signal
      cohesion  0.25 — tag-sharing narrative coherence (kept for readability signal;
                        copula already captures the quantitative correlation benefit)
      odds      0.15 — Gaussian around leg-count-appropriate sweet spot
      diversity 0.05 — tiebreaker against stat-monotone combos (e.g. 3 PTS overs)
    """
    n = len(legs)
    avg_edge = sum(l["edge"] for l in legs) / n
    parlay_odds = _parlay_american(legs)

    # Gaussian odds scoring — tight reward around target, clean dropoff at edges.
    # Sweet spot: +280 for 3-leg, +360 for 4-leg (derived from 0.68 avg WP + corr).
    target = 280 if n <= 3 else 360
    sigma_odds = 80.0
    if parlay_odds < MIN_PARLAY_ODDS or parlay_odds > MAX_PARLAY_ODDS:
        odds_score = 0.0
    else:
        odds_score = math.exp(-((parlay_odds - target) ** 2) / (2 * sigma_odds ** 2))

    cohesion = _correlation_cohesion(legs)

    # Full MC copula for ranking — n_samples=300 gives SE≈2.5% at joint≈0.40,
    # tighter than the 15-20% relative error of the equicorrelation approx.
    probs = [l["fair_prob"] for l in legs]
    corr_mat = _build_corr_matrix(legs)
    copula_joint = _copula_joint_prob(probs, corr_mat, n_samples=300)
    copula_ideal = 0.38 if n <= 3 else 0.25
    copula_score = min(copula_joint / copula_ideal, 1.0)

    # Stat diversity: rewards legs spanning multiple stat types.
    # 3 different stats in 3-leg = 1.0; all same stat = 0.33.
    stat_diversity = len(set(l["stat"] for l in legs)) / n

    return (avg_edge * 0.25 + copula_score * 0.30 + odds_score * 0.15
            + cohesion * 0.25 + stat_diversity * 0.05)


def size_sgp(legs, cohesion_score, _copula_joint=None):
    """Quality-gated SGP sizing with Gaussian copula EV check (L8, May 2026).

    Stays at 0.25u (fun bet) unless all three criteria align → steps to 0.50u.
    Never higher: 3-4 leg variance doesn't justify it regardless of Kelly math.

    Premium gate (all required):
      1. copula_ev_margin ≥ 0.10  — copula joint probability exceeds the parlay's
                                     implied probability by ≥ 10 percentage points.
                                     This replaces the avg_wp ≥ 0.70 raw threshold
                                     because it directly answers "is this +EV?" after
                                     accounting for inter-leg correlation.
      2. cohesion_score  ≥ 0.55   — legs share enough correlation structure that the
                                     copula uplift is real, not coincidental.
      3. avg_edge        ≥ 0.035  — individual edges are meaningful, not marginal.

    _copula_joint: pre-computed value from build_sgp_embed to avoid double MC.
    Thresholds are starting points — tune against CLV/W-L data over 50+ builds.
    """
    avg_edge = sum(l["edge"] for l in legs) / len(legs)
    if avg_edge < 0.035 or cohesion_score < 0.55:
        return SGP_SIZE_DEFAULT
    # L8: full Monte Carlo copula (4000 samples, ~2 ms) for the sizing decision.
    if _copula_joint is None:
        probs = [l["fair_prob"] for l in legs]
        corr_mat = _build_corr_matrix(legs)
        _copula_joint = _copula_joint_prob(probs, corr_mat)
    # Gate 1: copula joint exceeds book-implied by ≥ 10pp (documented threshold).
    parlay_implied = _implied_prob(_parlay_american(legs))
    if _copula_joint - parlay_implied < 0.10:
        return SGP_SIZE_DEFAULT
    # Gate 2: correlation adds >= 1.5pp lift above no-vig independence baseline.
    # no_vig_independent = product of fair (no-vig) probs — what the parlay is worth
    # at zero vig assuming legs are independent. copula_joint - no_vig_independent is
    # pure correlation signal, not vig removal. Prevents sizing up on combos where
    # the copula edge is entirely explained by leg-level vig removal.
    no_vig_independent = 1.0
    for l in legs:
        no_vig_independent *= l["fair_prob"]
    if _copula_joint - no_vig_independent >= 0.015:
        return SGP_SIZE_PREMIUM
    return SGP_SIZE_DEFAULT


# Books allowed for SGP leg sourcing and placement
SGP_ALLOWED_BOOKS = {
    "fanduel", "betmgm", "draftkings",
    "espnbet",        # theScore Bet
    "williamhill_us", # Caesars
    "fanatics",
    "hardrockbet",
}


def _pick_best_book(books):
    """From a set of allowed SGP books, pick the most preferred one.

    BetMGM is first: independently measured 2-3% better SGP pricing vs
    DraftKings/FanDuel (oddsindex research, Apr 2026). Over volume this
    compounds significantly.
    """
    preferred = ["betmgm", "draftkings", "fanduel", "williamhill_us",
                 "espnbet", "fanatics", "hardrockbet"]
    allowed = {b for b in books if b in SGP_ALLOWED_BOOKS}
    for p in preferred:
        if p in allowed:
            return p
    return next(iter(sorted(allowed))) if allowed else next(iter(sorted(books)))


def build_sgp(projections, odds_data, event):
    """Build the best 3-4 leg SGP for a given game.

    Pool: top 40 candidates by composite pool_score (edge × 0.40 + wp_excess × 0.60).
    Search: tries MAX_LEGS down to MIN_LEGS, returns first leg count that finds
    a valid combo — prefers more legs since they push odds into the target range.
    C(40,4) = 91,390 combos max; typically much less after book intersection filter.
    """
    candidates = build_candidate_legs(projections, odds_data, event)
    if len(candidates) < MIN_LEGS:
        return None
    best_sgp = None
    # Expanded pool: 40 candidates (C(40,4)=91k — fast enough)
    pool = candidates[:40]
    for n_legs in range(min(MAX_LEGS, len(pool)), MIN_LEGS - 1, -1):
        leg_best = None
        leg_best_score = -1
        # Player diversity gate: every leg must come from a different player.
        # 3-leg → 3 players, 4-leg → 4 players. Same player twice = concentration risk
        # (one bad game kills two legs) and the cross-stat tension check doesn't cover
        # all same-player, same-direction combos (e.g. Over PTS + Over AST).
        min_players = n_legs
        for combo in combinations(pool, n_legs):
            legs = list(combo)
            # Player diversity check
            if len(set(l["player"] for l in legs)) < min_players:
                continue
            if not _check_parlay_correlations(legs):
                continue
            # ── Require a single ALLOWED book that carries every leg ─────
            book_sets = [
                {k for k in leg.get("book_odds", {leg["book"]: leg["odds"]}).keys()
                 if k in SGP_ALLOWED_BOOKS}
                for leg in legs
            ]
            common_books = book_sets[0].intersection(*book_sets[1:])
            if not common_books:
                continue   # no allowed book covers all legs
            chosen_book = _pick_best_book(common_books)
            # Lock all legs to that book's actual odds
            locked = []
            for leg in legs:
                bk_map = leg.get("book_odds", {leg["book"]: leg["odds"]})
                locked.append({**leg,
                                "odds": bk_map.get(chosen_book, leg["odds"]),
                                "book": chosen_book})
            # ─────────────────────────────────────────────────────────────
            parlay_odds = _parlay_american(locked)
            if parlay_odds < MIN_PARLAY_ODDS or parlay_odds > MAX_PARLAY_ODDS:
                continue
            score = _score_sgp(locked)
            if score > leg_best_score:
                leg_best_score = score
                leg_best = (locked, parlay_odds, score)
        if leg_best is not None:
            return leg_best
    return best_sgp


# -- Discord embed ---------------------------------------------------------

def _generate_thesis(legs):
    teams = [l["team"] for l in legs]
    team_counts = Counter(teams)
    dominant_team, dom_count = team_counts.most_common(1)[0]
    dom_legs   = [l for l in legs if l["team"] == dominant_team]
    over_stats  = [l["stat"] for l in dom_legs if l["direction"] == "over"]
    under_stats = [l["stat"] for l in dom_legs if l["direction"] == "under"]
    mostly_overs  = len(over_stats)  > len(under_stats)
    mostly_unders = len(under_stats) > len(over_stats)

    if mostly_overs:
        if "PTS" in over_stats and "AST" in over_stats:
            return f"{dominant_team} offensive explosion"
        elif "PTS" in over_stats and "3PM" in over_stats:
            return f"{dominant_team} lights it up from deep"
        elif "REB" in over_stats and len(over_stats) >= 2:
            return f"{dominant_team} dominates the glass"
        elif dom_count >= 4:
            return f"{dominant_team} stat-stuffing night"
    elif mostly_unders:
        if "PTS" in under_stats and dom_count >= 4:
            return f"{dominant_team} quiet scoring night"
        elif "REB" in under_stats and "PTS" in under_stats:
            return f"{dominant_team} below the line across the board"
        elif dom_count >= 4:
            return f"{dominant_team} unders stack"
        else:
            return f"{dominant_team} staying under"

    if len(set(teams)) == 1:
        return f"Full {dominant_team} stack"
    return f"{dominant_team}-heavy game script"


def _sgp_book(legs):
    """Pick the single best allowed book for the SGP (most common across legs).
    BetMGM preferred: independently measured 2-3% better SGP pricing.
    """
    preferred = ["betmgm", "draftkings", "fanduel", "williamhill_us",
                 "espnbet", "fanatics", "hardrockbet"]
    counts = Counter(leg["book"] for leg in legs if leg["book"] in SGP_ALLOWED_BOOKS)
    if not counts:
        counts = Counter(leg["book"] for leg in legs)
    modal_book, modal_count = counts.most_common(1)[0]
    for p in preferred:
        if counts.get(p, 0) == modal_count:
            return p
    return modal_book


def build_sgp_embed(legs, parlay_odds, game, sgp_size=None, _copula_joint=None):
    now_et = datetime.now(ZoneInfo("America/New_York")).strftime("%I:%M %p ET")
    thesis = _generate_thesis(legs)
    book = _sgp_book(legs)
    cohesion_raw = _correlation_cohesion(legs)
    # Compute copula joint prob once; reuse for sizing + display.
    # Caller may pass _copula_joint to avoid a second MC run (post_sgp computes it first).
    if _copula_joint is None:
        _probs = [l["fair_prob"] for l in legs]
        _corr  = _build_corr_matrix(legs)
        _copula_joint = _copula_joint_prob(_probs, _corr)
    copula_joint = _copula_joint
    parlay_implied = _implied_prob(parlay_odds)
    # Dynamic sizing if not supplied — pass copula to avoid recomputation.
    if sgp_size is None:
        sgp_size = size_sgp(legs, cohesion_raw, _copula_joint=copula_joint)
    leg_lines = []
    for i, leg in enumerate(legs, 1):
        dir_word = "Over" if leg["direction"] == "over" else "Under"
        wp_pct = leg["fair_prob"] * 100
        leg_lines.append(
            f"**{i}.** {leg['player']} ({leg['team']}) "
            f"{dir_word} {leg['line']} {leg['stat']} "
            f"({leg['odds']:+d}) — {wp_pct:.0f}% model prob"
        )
    avg_wp = sum(l["fair_prob"] for l in legs) * 100 / len(legs)
    cohesion = cohesion_raw * 100
    # Copula EV line: shows true joint prob vs book-implied — the core edge signal.
    copula_pct  = copula_joint * 100
    implied_pct = parlay_implied * 100
    ev_sign = "+" if copula_joint > parlay_implied else ""
    ev_pct  = (copula_joint - parlay_implied) * 100
    description_parts = [
        f"**{game}**",
        f"*{thesis}*",
        "",
        *leg_lines,
        "",
        f"**{parlay_odds:+d}** | {len(legs)} legs | {sgp_size:.2f}u",
        f"Copula joint: {copula_pct:.0f}% | Implied: {implied_pct:.0f}% ({ev_sign}{ev_pct:.0f}pp)",
        f"Avg leg prob: {avg_wp:.0f}% | Cohesion: {cohesion:.0f}%",
        f"📍 Bet on: **{display_book(book)}**",
    ]
    return {
        "username": "PicksByJonny",
        "embeds": [{
            "title": "🎯 SGP — Same-Game Parlay",
            "description": "\n".join(description_parts),
            "color": 0x9B59B6,
            "footer": {"text": f"{BRAND_TAGLINE} | {now_et}"},
        }]
    }


def _log_sgp(legs, parlay_odds, game, today_str, book="", sgp_size=None, copula_joint=None):
    """Append an SGP to pick_log.csv as run_type='sgp'."""
    try:
        from pick_log_schema import CANONICAL_HEADER
        from run_picks import PICK_LOG_PATH, _pick_log_lock, _normalize_odds, _normalize_size, _write_schema_sidecar
    except ImportError as e:
        print(f"  [SGP] pick_log import failed — not logging: {e}")
        return

    log_path = Path(PICK_LOG_PATH)
    if not log_path.exists():
        return

    from datetime import datetime
    from zoneinfo import ZoneInfo
    run_time = datetime.now(ZoneInfo("America/New_York")).strftime("%H:%M")

    # Build legs JSON (matches _legs_json format in run_picks.py)
    legs_data = []
    for leg in legs:
        legs_data.append({
            "player":    leg.get("player", ""),
            "direction": leg.get("direction", "").lower(),
            "line":      float(leg.get("line", 0)),
            "stat":      leg.get("stat", ""),
            "sport":     "NBA",
            "game":      leg.get("game", game),
            "win_prob":  float(leg.get("fair_prob", 0)),
        })
    legs_json = json.dumps(legs_data, separators=(",", ":"))

    player_desc = " / ".join(
        f"{l.get('player','').split()[-1]} "
        f"{'O' if l.get('direction','').lower()=='over' else 'U'}"
        f"{l.get('line','')} {l.get('stat','')}"
        for l in legs
    )

    row = {
        "date":            today_str,
        "run_time":        run_time,
        "run_type":        "sgp",
        "sport":           "NBA",
        "player":          f"SGP {len(legs)}-leg",
        "team":            "",
        "stat":            "PARLAY",
        "line":            "",
        "direction":       "",
        "proj":            "",
        "win_prob":        round(copula_joint, 4) if copula_joint is not None else "",
        "edge":            "",
        "odds":            _normalize_odds(parlay_odds) if parlay_odds else "",
        "book":            book,
        "tier":            "SGP",
        "pick_score":      "",
        "size":            _normalize_size(sgp_size if sgp_size is not None else size_sgp(legs, _correlation_cohesion(legs))),  # cohesion computed once if needed
        "game":            player_desc,
        "mode":            "",
        "result":          "",
        "closing_odds":    "",
        "clv":             "",
        "card_slot":       "",
        "is_home":         "",
        "context_verdict": "",
        "context_reason":  "",
        "context_score":   "",
        "legs":            legs_json,
        "over_p_raw":      "",
    }

    try:
        with _pick_log_lock(log_path):
            with open(log_path, "r", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            already = any(
                r.get("date") == today_str and r.get("run_type") == "sgp"
                and r.get("game") == player_desc
                for r in rows
            )
            if already:
                print(f"  [SGP] Already logged for {game} today — skipping.")
                return
            with open(log_path, "a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=CANONICAL_HEADER, extrasaction="ignore", restval="")
                writer.writerow(row)
                f.flush()
                os.fsync(f.fileno())
        print(f"  [SGP] 📝 Logged to pick_log ({len(legs)} legs, {parlay_odds:+d})")
        try:
            _write_schema_sidecar(log_path)
        except Exception:
            pass
    except Exception as e:
        print(f"  [SGP] ⚠ pick_log write failed: {e}")


def _joint_ev_ok(legs, parlay_odds, _copula_joint=None):
    """Plan 9 §9H joint-EV existence floor.

    Returns (ok, joint, margin): ok is True iff the copula joint probability
    exceeds the book-implied parlay probability by at least SGP_JOINT_EV_MARGIN.
    Caller may pass a precomputed _copula_joint to avoid a second MC run.
    """
    if _copula_joint is None:
        probs = [l["fair_prob"] for l in legs]
        corr = _build_corr_matrix(legs)
        _copula_joint = _copula_joint_prob(probs, corr)
    margin = _copula_joint - _implied_prob(parlay_odds)
    return margin >= SGP_JOINT_EV_MARGIN, _copula_joint, margin


def post_sgp(legs, parlay_odds, game, suppress_ping=False, today_str=None, save=True):
    from secrets_config import DISCORD_SGP_WEBHOOK
    webhook = DISCORD_SGP_WEBHOOK or DISCORD_BONUS_WEBHOOK
    if not webhook:
        print("  [SGP] No SGP webhook configured — skipping.")
        return False
    # Discord dedup guard
    _today = today_str or datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
    _guard_key = f"sgp:{_today}:{game}"
    try:
        from discord_guard import load_guard, save_guard
        _guard = load_guard()
        if _guard.get(_guard_key):
            print(f"  [SGP] Already posted for {game} today — skipping.")
            return False
    except Exception:
        _guard = None
    book = _sgp_book(legs)
    cohesion_val = _correlation_cohesion(legs)
    _probs = [l["fair_prob"] for l in legs]
    _corr = _build_corr_matrix(legs)
    _cj = _copula_joint_prob(_probs, _corr)
    # Plan 9 §9H: belt-and-suspenders joint-EV floor (primary gate is in
    # run_sgp_builder; this protects direct post_sgp callers).
    _ev_ok, _, _ev_margin = _joint_ev_ok(legs, parlay_odds, _copula_joint=_cj)
    if not _ev_ok:
        print(f"  [SGP] Joint-EV gate: margin {_ev_margin:+.3f} < {SGP_JOINT_EV_MARGIN} — not posting {game}.")
        return False
    sgp_size = size_sgp(legs, cohesion_val, _copula_joint=_cj)
    print(f"  [SGP-sizing] avg_wp={sum(l['fair_prob'] for l in legs)/len(legs):.2f} cohesion={cohesion_val:.2f} avg_edge={sum(l['edge'] for l in legs)/len(legs):.3f} → {sgp_size:.2f}u")
    payload = build_sgp_embed(legs, parlay_odds, game, sgp_size=sgp_size, _copula_joint=_cj)
    try:
        from run_picks import _webhook_post
        ok = _webhook_post(webhook, payload, label=f"SGP: {game}")
    except ImportError:
        import requests
        from http_utils import default_headers
        try:
            r = requests.post(webhook, json=payload, headers=default_headers(), timeout=10)
            r.raise_for_status()
            ok = True
        except Exception as e:
            print(f"  [SGP] Discord post failed: {e}")
            ok = False
    if ok:
        if _guard is not None:
            try:
                from discord_guard import load_guard, save_guard
                _guard = load_guard()
                _guard[_guard_key] = True
                save_guard(_guard)
            except Exception:
                pass
        if save and today_str:
            _log_sgp(legs, parlay_odds, game, today_str, book=book, sgp_size=sgp_size, copula_joint=_cj)
        elif save and not today_str:
            print("[SGP] WARNING: today_str is None — pick not logged")
    return ok


# -- Console output --------------------------------------------------------

def print_sgp(legs, parlay_odds, game, score):
    thesis = _generate_thesis(legs)
    cohesion = _correlation_cohesion(legs)
    print(f"\n  {'='*60}")
    print(f"  SGP -- {game}")
    print(f"  Thesis: {thesis}")
    print(f"  {'='*60}")
    print()
    for i, leg in enumerate(legs, 1):
        dir_word = "Over" if leg["direction"] == "over" else "Under"
        edge_pct = leg["edge"] * 100
        wp_pct = leg["fair_prob"] * 100
        print(f"  Leg {i}: {leg['player']} ({leg['team']}) "
              f"{dir_word} {leg['line']} {leg['stat']}")
        print(f"         {leg['odds']:+d} @ {display_book(leg['book'])} "
              f"| Proj: {leg['proj']:.2f} vs {leg['line']} "
              f"| Edge: {edge_pct:.1f}% | WP: {wp_pct:.0f}%")
    avg_edge = sum(l["edge"] for l in legs) * 100 / len(legs)
    avg_wp = sum(l["fair_prob"] for l in legs) * 100 / len(legs)
    teams = set(l["team"] for l in legs)
    stat_div = len(set(l["stat"] for l in legs)) / len(legs)
    dyn_size = size_sgp(legs, cohesion)
    print()
    print(f"  Parlay odds: {parlay_odds:+d}")
    print(f"  Legs: {len(legs)} | Avg edge: {avg_edge:.1f}% | Avg WP: {avg_wp:.0f}% | Size: {dyn_size}u")
    print(f"  Teams: {', '.join(teams)} | Cohesion: {cohesion*100:.0f}% | Stat diversity: {stat_div*100:.0f}% | Score: {score:.3f}")
    print(f"\n  Correlation check:")
    for a, b in combinations(legs, 2):
        tags_a = _correlation_tags(a)
        tags_b = _correlation_tags(b)
        shared = tags_a & tags_b
        neg = _is_negatively_correlated(a, b)
        status = "CONFLICT" if neg else ("linked" if shared else "neutral")
        a_short = f"{a['player'].split()[-1]} {a['direction'][0].upper()}{a['line']} {a['stat']}"
        b_short = f"{b['player'].split()[-1]} {b['direction'][0].upper()}{b['line']} {b['stat']}"
        symbol = "XX" if neg else ("==" if shared else "--")
        print(f"    {symbol} {a_short} x {b_short}: {status}")
    print(f"\n  {'='*60}")


# -- Main ------------------------------------------------------------------

def run_sgp_builder(csv_paths, dry_run=False, confirm=False, test=False,
                    cached_odds=None, save=True):
    today_str = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
    projections = {}
    for csv_path in csv_paths:
        path = Path(csv_path)
        if "nba" not in path.name.lower():
            continue
        loaded = load_projections(path)
        projections.update(loaded)
        print(f"  [SGP] Loaded {len(loaded)} players from {path.name}")
    if not projections:
        print("  [SGP] No NBA projections found -- skipping SGP builder.")
        return []
    if cached_odds and "events" in cached_odds:
        events = cached_odds["events"]
        print(f"  [SGP] Using cached event data ({len(events)} games)")
    else:
        events = fetch_nba_events()
        print(f"  [SGP] Fetched {len(events)} NBA games")
    results = []
    for event in events:
        eid = event["id"]
        game = f"{event.get('away_team', '?')} @ {event.get('home_team', '?')}"
        print(f"\n  [SGP] Building SGP for: {game}")
        if cached_odds:
            odds_data = fetch_event_props_from_cache(cached_odds, eid)
            if not odds_data:
                print(f"  [SGP] No cached props for {eid} -- fetching live...")
                odds_data = fetch_event_props(eid)
        else:
            odds_data = fetch_event_props(eid)
        if not odds_data:
            print(f"  [SGP] No odds data for {game} -- skipping.")
            continue
        result = build_sgp(projections, odds_data, event)
        if result is None:
            print(f"  [SGP] No valid SGP found for {game} "
                  f"(need {MIN_LEGS}+ legs in +{MIN_PARLAY_ODDS}-{MAX_PARLAY_ODDS} range).")
            continue
        legs, parlay_odds, score = result
        # Plan 9 §9H: joint-EV existence floor — copula joint must beat
        # book-implied + margin for ANY slip to fire.
        ev_ok, ev_joint, ev_margin = _joint_ev_ok(legs, parlay_odds)
        if not ev_ok:
            print(f"  [SGP] Joint-EV gate: joint {ev_joint:.3f} vs implied "
                  f"{_implied_prob(parlay_odds):.3f} (margin {ev_margin:+.3f} < "
                  f"{SGP_JOINT_EV_MARGIN}) — rejecting {game}.")
            continue
        print_sgp(legs, parlay_odds, game, score)
        results.append((legs, parlay_odds, game))
        if dry_run:
            print(f"  [SGP] --dry-run: skipping Discord post.")
        elif confirm:
            ans = input(f"  [SGP] Post this SGP to #bonus-drops? (y/n): ").strip().lower()
            if ans == "y":
                ok = post_sgp(legs, parlay_odds, game, suppress_ping=test,
                              today_str=today_str, save=save)
                print(f"  [SGP] {'Posted' if ok else 'FAILED'}: {game}")
            else:
                print(f"  [SGP] Skipped: {game}")
        else:
            ok = post_sgp(legs, parlay_odds, game, suppress_ping=test,
                          today_str=today_str, save=save)
            print(f"  [SGP] {'Posted' if ok else 'FAILED'}: {game}")
    if not results:
        print(f"\n  [SGP] No valid SGPs built for tonight's slate.")
    return results


# -- CLI entry point -------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="JonnyParlay SGP Builder")
    parser.add_argument("csvs", nargs="+", help="SaberSim NBA CSV file(s)")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--confirm", action="store_true")
    parser.add_argument("--test", action="store_true")
    args = parser.parse_args()
    run_sgp_builder(
        args.csvs,
        dry_run=args.dry_run,
        confirm=args.confirm,
        test=args.test,
    )


