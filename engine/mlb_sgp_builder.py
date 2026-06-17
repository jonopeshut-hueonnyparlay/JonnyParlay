"""mlb_sgp_builder.py -- MLB Same-Game Parlay builder for JonnyParlay.
3-4 legs, +200-+450 target range.
Sizing: 0.25u default, 0.50u when copula EV margin >= 0.10 + avg edge >= 0.035.
Usage: python mlb_sgp_builder.py <csv> [--dry-run] [--confirm]

Stats available in SGP pool:
  Pitchers: OUTS (recorded outs)
  Batters:  HITS
  Shadow stats (HRR/RBI/RUNS/ER) excluded until they graduate to live status.

Hard kill rules (R0-R1):
  R0: Same player, same stat, same direction (dedup)
  R1: Same player, same stat, opposite direction (contradiction)

Correlation table:
  Two pitchers same game (same direction):  rho = 0.10
  Same-team batters same direction:          rho = 0.15
  Cross-team batters same direction:         rho = 0.08
  Pitcher + same-team batter:                rho = 0.02  (defense != offense)
  Cross-team mixed direction:                rho = 0.02
  Otherwise:                                 rho = 0.00
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

# -- Engine path setup ---------------------------------------------------------
_ENGINE_DIR = Path(__file__).resolve().parent
if str(_ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(_ENGINE_DIR))

from brand import BRAND_TAGLINE
from book_names import display_book
from secrets_config import require_odds_api_key, DISCORD_BONUS_WEBHOOK
from mlb_starter_fetcher import fetch_confirmed_starters, is_confirmed

# Reuse pure-math helpers from NBA SGP builder to avoid duplication
from sgp_builder import (
    _cholesky,
    _copula_joint_prob,
    _copula_joint_approx,
    _american_to_decimal,
    _decimal_to_american,
    _parlay_american,
    _pick_best_book,
    SGP_ALLOWED_BOOKS,
)

# -- Constants -----------------------------------------------------------------

SGP_SIZE_DEFAULT = 0.25
SGP_SIZE_PREMIUM = 0.50

MIN_LEGS = 3
MAX_LEGS = 4
MIN_PARLAY_ODDS = 200
MAX_PARLAY_ODDS = 450
MIN_LEG_EDGE = 0.010
MIN_LEG_WIN_PROB = 0.65
MIN_LEG_WIN_PROB_OUTS = 0.62   # OUTS-specific floor (was tuned to sigma=0.311; sigma now 0.27
                               # starts-only — narrower sigma raises OUTS leg win_probs, so this
                               # floor binds less often. Monitor leg counts; don't retune yet.)
MAX_SGPS_PER_DAY = 3   # MLB has 15 games/night vs NBA's ~5 — cap to top 3 by score
# Plan 9 §9H: joint-EV existence floor — copula joint prob must exceed
# implied(parlay odds) + margin for ANY slip to fire (per-leg WP floors alone can
# construct -EV slips on the 4-leg path). Premium gate (>=0.10) is separate.
# DATA_GATED: re-tune at n=100 scored SGP slips. Mirrors sgp_builder.py.
SGP_JOINT_EV_MARGIN = 0.025

ODDS_BASE = "https://api.the-odds-api.com/v4"
ODDS_REGIONS = "us,us2,us_ex"
API_SLEEP = 1.3

# Stats and their API market keys
MLB_SGP_MARKETS = "pitcher_outs,batter_hits"

MLB_SGP_STAT_MAP = {
    "pitcher_outs":  "OUTS",
    "batter_hits":   "HITS",
}

# Stat families for correlation and kill rules
_PITCHER_STATS = {"OUTS"}   # Pitcher output stats
_BATTER_STATS  = {"HITS"}   # Come from batters

# Stat distribution parameters (mirrors run_picks.py / sgp_builder.py)
# HITS: Poisson (within-batter var/mu ~ 1.0, confirmed Poisson for low-mean counts)
_POISSON_STATS_MLB = {"HITS"}

# OUTS: Normal (SIGMA from run_picks.py — mult=0.27, min=1.0;
# starts-only recalibration 2026-06-05, Plan 6 §1C)
_OUTS_SIGMA = {"mult": 0.27, "min": 1.0}


# -- Math helpers (consolidated in quant/distributions.py) ---------------------
# Previously private copies of the Poisson/Normal CDF math; now aliased to the
# single canonical implementation.
from quant.distributions import (
    poisson_pmf as _poisson_pmf,
    poisson_cdf as _poisson_cdf,
    normal_cdf as _normal_cdf,
)


from quant.odds import implied_prob as _implied_prob


def _fair_prob_mlb(proj, line, stat, direction):
    """Win probability from projection, line, and stat distribution."""
    if stat in _POISSON_STATS_MLB:
        k = math.floor(line)
        if line == k:  # integer line — push-adjust
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
    else:
        # Normal for OUTS
        s = _OUTS_SIGMA
        sigma = max(proj * s["mult"], s["min"])
        under_p = _normal_cdf(line, proj, sigma)
        over_p = 1.0 - under_p
    return over_p if direction == "over" else under_p


# -- Correlation ---------------------------------------------------------------

def _is_negatively_correlated_mlb(leg_a, leg_b):
    """Return True if two legs structurally conflict — never combine."""
    # R0: Same player, same stat, same direction (dedup)
    if (leg_a["player"] == leg_b["player"]
            and leg_a["stat"] == leg_b["stat"]
            and leg_a["direction"] == leg_b["direction"]):
        return True

    # R1: Same player, same stat, opposite direction (contradiction)
    if (leg_a["player"] == leg_b["player"]
            and leg_a["stat"] == leg_b["stat"]
            and leg_a["direction"] != leg_b["direction"]):
        return True

    # R2_MLB: OUTS under + HITS under, same game — pitcher knocked out early ⇒
    # opposing batters are getting hits; HITS under is structurally contradicted
    game_a = leg_a.get("game", "")
    game_b = leg_b.get("game", "")
    if game_a and game_b and game_a == game_b:
        stats = {leg_a["stat"], leg_b["stat"]}
        dirs  = (leg_a["direction"], leg_b["direction"])
        if stats == {"OUTS", "HITS"} and dirs[0] == "under" and dirs[1] == "under":
            return True

    return False


# Provenance + refit-trigger for the MLB SGP rho values (audit P1.6 / S4g-12).
# No JSON matrix — values are hardcoded in _pairwise_rho_mlb() (structural priors,
# NOT an empirical MLB SGP fit). _log_mlb_sgp_rho_status() counts scored slips at
# build time and alerts at the sign (n>=100) and magnitude (n>=160) thresholds.
# Per research item 5: n=100 is sign/coarse-magnitude only (Fisher-z 95% CI ~+-0.20
# for rho=0.30); the point-of-stability for a +-0.10 corridor is ~161 (Schonbrodt
# & Perugini 2013). Until n>=160, empirical-Bayes shrink any observed r toward the
# 0.30 prior rather than replacing it.
_MLB_SGP_RHO_META = {
    "version": "1.0",
    "fit_date": "structural-priors (2026-05-29)",
    "source": "structural priors (WHIP / early-exit mechanism); NOT empirical MLB SGP fit",
    "model": "Gaussian copula pairwise rho",
    "n_sign_check": 100,    # Fisher-z sign / coarse-magnitude only below this
    "n_target": 160,        # point-of-stability for +-0.10 (Schonbrodt & Perugini 2013)
    "key_value_to_tighten": "OUTS-over x opposing-HITS-under = 0.30",
    "shrink_plan": "empirical-Bayes: blend observed r toward the 0.30 prior until n>=160",
    "frozen": True,
}


def _pairwise_rho_mlb(leg_a, leg_b):
    """Pairwise Gaussian copula correlation rho for two MLB SGP legs.

    Provenance: see _MLB_SGP_RHO_META (audit P1.6). Conservative values from
    structural priors, NOT empirical MLB game-log correlations (insufficient SGP
    sample). The 0.30 OUTS-over x opposing-HITS-under value is the one most worth
    tightening once enough scored slips exist; _log_mlb_sgp_rho_status() tracks it.
    """
    stat_a = leg_a["stat"]
    stat_b = leg_b["stat"]
    team_a = leg_a.get("team", "")
    team_b = leg_b.get("team", "")
    dir_a  = leg_a["direction"]
    dir_b  = leg_b["direction"]
    same_team = team_a and team_b and team_a == team_b
    same_dir  = dir_a == dir_b

    # Both pitcher stats, same game — shared game-pace/total environment
    if stat_a in _PITCHER_STATS and stat_b in _PITCHER_STATS and not same_team:
        return 0.10 if same_dir else 0.02

    # Same-team batters (HITS stacking) — lineup correlation
    if stat_a in _BATTER_STATS and stat_b in _BATTER_STATS and same_team:
        return 0.15 if same_dir else 0.02

    # Cross-team batters — weaker game environment link
    if stat_a in _BATTER_STATS and stat_b in _BATTER_STATS and not same_team:
        return 0.08 if same_dir else 0.02

    # OUTS over + opposing HITS under — pitcher dominance ⇒ fewer opposing hits (ρ≈0.30)
    is_outs_over_hits_under = (
        (stat_a in _PITCHER_STATS and stat_b in _BATTER_STATS
         and dir_a == "over" and dir_b == "under" and not same_team)
        or
        (stat_b in _PITCHER_STATS and stat_a in _BATTER_STATS
         and dir_b == "over" and dir_a == "under" and not same_team)
    )
    if is_outs_over_hits_under:
        return 0.30

    # Pitcher + batter (same or different teams, same game) — defense != offense
    return 0.02


def _build_corr_matrix_mlb(legs):
    n = len(legs)
    return [[1.0 if i == j else _pairwise_rho_mlb(legs[i], legs[j])
             for j in range(n)] for i in range(n)]


def _count_scored_mlb_sgps() -> int:
    """Count graded MLB SGP slips in the pick log (run_type=sgp, sport=MLB,
    result in W/L). Returns 0 if the log is absent/unreadable — never raises, so
    it is safe at build time and in CI where the gitignored log isn't present.
    """
    try:
        from paths import PICK_LOG_PATH
        from pick_log_io import read_rows_locked_if_exists
        rows = read_rows_locked_if_exists(str(PICK_LOG_PATH)) or []
        return sum(
            1 for r in rows
            if str(r.get("run_type", "")).lower() == "sgp"
            and str(r.get("sport", "")).upper() == "MLB"
            and str(r.get("result", "")).upper() in ("W", "L")
        )
    except Exception:
        return 0


def _log_mlb_sgp_rho_status(n: int | None = None) -> int:
    """Log the MLB SGP rho refit-trigger status; alert at the sign/magnitude
    thresholds. Returns the observed count (n injectable for tests)."""
    if n is None:
        n = _count_scored_mlb_sgps()
    meta = _MLB_SGP_RHO_META
    print(f"  [MLB SGP] rho: structural priors, n={n}/{meta['n_target']} scored slips "
          f"({meta['key_value_to_tighten']} is the value most worth tightening).")
    if n >= meta["n_target"]:
        print(f"  [MLB SGP] ALERT: n={n} >= {meta['n_target']} — MAGNITUDE refit candidate: "
              "re-estimate the matrix (empirical-Bayes shrink observed r toward 0.30).")
    elif n >= meta["n_sign_check"]:
        print(f"  [MLB SGP] ALERT: n={n} >= {meta['n_sign_check']} — SIGN check only "
              "(coarse magnitude; below the ~160 point-of-stability — keep the priors).")
    return n


def _check_parlay_correlations_mlb(legs):
    for a, b in combinations(legs, 2):
        if _is_negatively_correlated_mlb(a, b):
            return False
    return True


# -- Cohesion -----------------------------------------------------------------

def _correlation_tags_mlb(leg):
    """Return game-script narrative tags for an MLB SGP leg.

    Game-key scope (not team scope) so that OUTS over (pitcher team) and opposing
    HITS under (batter team) share the pitcher_dom tag and receive cohesion credit.
    """
    tags = set()
    stat = leg["stat"]
    direction = leg["direction"]
    game_key = leg.get("game", "").lower().replace(" @ ", "_at_").replace(" ", "_")
    # Pitcher dominance: pitcher OUTS over OR any batter HITS under (being suppressed)
    if (stat == "OUTS" and direction == "over") or (stat == "HITS" and direction == "under"):
        if game_key:
            tags.add(f"pitcher_dom_{game_key}")
    # Batter explosion thesis: HITS over
    if stat == "HITS" and direction == "over":
        if game_key:
            tags.add(f"batter_hot_{game_key}")
    return tags


def _correlation_cohesion_mlb(legs):
    """Fraction of leg pairs that share a game-script narrative tag."""
    total_pairs = linked_pairs = 0
    for a, b in combinations(legs, 2):
        total_pairs += 1
        if _correlation_tags_mlb(a) & _correlation_tags_mlb(b):
            linked_pairs += 1
    return linked_pairs / total_pairs if total_pairs > 0 else 0.0


# -- Scoring -------------------------------------------------------------------

def _score_mlb_sgp(legs):
    """Score an MLB SGP.

    Weights (matches NBA SGP builder):
      edge      0.25 — per-leg model edge
      copula    0.30 — correlation-adjusted joint hit rate (fast equicorr approx for ranking)
      odds      0.15 — Gaussian reward around target odds
      cohesion  0.25 — game-script narrative coherence (pitcher_dom / batter_hot tag overlap)
      stat_div  0.05 — tiebreaker for stat diversity (OUTS vs HITS)
    """
    n = len(legs)
    avg_edge = sum(l["edge"] for l in legs) / n
    parlay_odds = _parlay_american(legs)

    target = 280 if n <= 3 else 360
    sigma_odds = 80.0
    if parlay_odds < MIN_PARLAY_ODDS or parlay_odds > MAX_PARLAY_ODDS:
        odds_score = 0.0
    else:
        odds_score = math.exp(-((parlay_odds - target) ** 2) / (2 * sigma_odds ** 2))

    probs = [l["fair_prob"] for l in legs]
    corr_mat = _build_corr_matrix_mlb(legs)
    off_diag = [corr_mat[i][j] for i in range(n) for j in range(n) if i != j]
    avg_rho = sum(off_diag) / len(off_diag) if off_diag else 0.0
    copula_joint = _copula_joint_approx(probs, avg_rho)
    copula_ideal = 0.38 if n <= 3 else 0.25
    copula_score = min(copula_joint / copula_ideal, 1.0)

    cohesion = _correlation_cohesion_mlb(legs)
    stat_div = len(set(l["stat"] for l in legs)) / n

    return avg_edge * 0.25 + copula_score * 0.30 + odds_score * 0.15 + cohesion * 0.25 + stat_div * 0.05


def _size_mlb_sgp(legs):
    """Same quality gates as NBA SGP sizing."""
    avg_edge = sum(l["edge"] for l in legs) / len(legs)
    if avg_edge < 0.035:
        return SGP_SIZE_DEFAULT
    probs = [l["fair_prob"] for l in legs]
    corr_mat = _build_corr_matrix_mlb(legs)
    cj = _copula_joint_prob(probs, corr_mat)
    parlay_implied = _implied_prob(_parlay_american(legs))
    if cj - parlay_implied < 0.10:
        return SGP_SIZE_DEFAULT
    no_vig_indep = 1.0
    for p in probs:
        no_vig_indep *= p
    if cj - no_vig_indep >= 0.015:
        return SGP_SIZE_PREMIUM
    return SGP_SIZE_DEFAULT


# -- CSV loader ----------------------------------------------------------------

def load_mlb_projections(csv_path):
    """Load pitcher (K, OUTS) and batter (HITS) projections from a SaberSim MLB CSV."""
    players = {}
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            clean = {k.strip(): v.strip() for k, v in row.items()}
            name = clean.get("Name", clean.get("name", "")).strip()
            team = clean.get("Team", clean.get("team", "")).strip()
            pos  = clean.get("Pos",  clean.get("pos",  "")).strip().upper()
            if not name or not team:
                continue
            proj = {}
            is_pitcher = pos == "P"
            try:
                if is_pitcher:
                    ip  = float(clean.get("IP", 0) or 0)
                    if ip > 0:
                        proj["OUTS"] = ip * 3.0
                else:
                    h = float(clean.get("H", 0) or 0)
                    if h > 0:
                        proj["HITS"] = h
            except (ValueError, TypeError):
                pass
            if proj:
                name_key = name.lower().strip()
                players[name_key] = {
                    "name": name, "team": team, "pos": pos,
                    "is_pitcher": is_pitcher, "proj": proj,
                }
    return players


# -- Odds API ------------------------------------------------------------------

def _api_get(url, params):
    import requests
    from http_utils import default_headers
    params["apiKey"] = require_odds_api_key()
    last_r = None
    for _attempt in range(3):
        last_r = requests.get(url, params=params, headers=default_headers(), timeout=15)
        if last_r.status_code != 429:
            break
        retry_after = int(last_r.headers.get("Retry-After", 5))
        time.sleep(min(retry_after, 30))
    last_r.raise_for_status()
    return last_r.json()


def fetch_mlb_events():
    events = _api_get(f"{ODDS_BASE}/sports/baseball_mlb/events", {})
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


def fetch_mlb_event_props(event_id):
    """Fetch K, OUTS, HITS props for one MLB event. Returns same format as NBA SGP."""
    time.sleep(API_SLEEP)
    resp = _api_get(
        f"{ODDS_BASE}/sports/baseball_mlb/events/{event_id}/odds",
        {"regions": ODDS_REGIONS, "markets": MLB_SGP_MARKETS, "oddsFormat": "american"},
    )
    best = {}
    all_outcomes = {}
    book_all = {}
    bookmakers = resp.get("bookmakers", []) if isinstance(resp, dict) else []
    for bk in bookmakers:
        book = bk["key"]
        if book not in SGP_ALLOWED_BOOKS:
            continue
        for mkt in bk.get("markets", []):
            stat = MLB_SGP_STAT_MAP.get(mkt["key"])
            if not stat:
                continue
            for o in mkt.get("outcomes", []):
                player    = o.get("description", "")
                direction = o.get("name", "").lower()
                line      = o.get("point")
                odds      = o.get("price")
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


# -- SGP construction ----------------------------------------------------------

def build_candidate_legs_mlb(projections, odds_data, event):
    away = event.get("away_team", "")
    home = event.get("home_team", "")
    candidates = []

    for (player, stat, line, direction), info in odds_data.items():
        odds  = info["odds"]
        book  = info["book"]
        other = info.get("other_side_odds")
        name_key = player.lower().strip()
        proj_data = projections.get(name_key)
        if not proj_data or stat not in proj_data["proj"]:
            continue
        proj_val = proj_data["proj"][stat]
        team = proj_data["team"]
        if proj_val <= 0:
            continue

        fair = _fair_prob_mlb(proj_val, line, stat, direction)
        imp  = _implied_prob(odds)
        if other is not None:
            imp_other = _implied_prob(other)
            total_imp = imp + imp_other
            nv_imp = imp / total_imp if total_imp > 0 else imp
        else:
            nv_imp = imp
        edge = fair - nv_imp

        if edge < MIN_LEG_EDGE:
            continue
        _wp_floor = MIN_LEG_WIN_PROB_OUTS if stat == "OUTS" else MIN_LEG_WIN_PROB
        if fair < _wp_floor:
            continue
        if odds < -300:
            continue

        wp_excess  = max(0.0, fair - _wp_floor)
        pool_score = edge * 0.40 + wp_excess * 0.60
        candidates.append({
            "player":    player,
            "stat":      stat,
            "line":      line,
            "direction": direction,
            "proj":      proj_val,
            "fair_prob": fair,
            "nv_imp":    nv_imp,
            "edge":      edge,
            "odds":      odds,
            "book":      book,
            "book_odds": info.get("book_odds", {book: odds}),
            "team":      team,
            "game":      f"{away} @ {home}",
            "is_pitcher": proj_data.get("is_pitcher", False),
            "pool_score": pool_score,
        })

    candidates.sort(key=lambda x: x["pool_score"], reverse=True)
    return candidates


def build_mlb_sgp(projections, odds_data, event, _debug=False, confirmed_starters=None):
    """Build the best 3-4 leg MLB SGP for a given game."""
    game = f"{event.get('away_team','?')} @ {event.get('home_team','?')}"
    candidates = build_candidate_legs_mlb(projections, odds_data, event)
    if confirmed_starters:
        for cand in candidates:
            if cand.get("is_pitcher") and not is_confirmed(cand["player"], cand["team"], confirmed_starters):
                print(f"  [MLB SGP] WARNING: {cand['player']} ({cand['team']}) not confirmed starter — skipping {game}")
                return None
    if _debug:
        game = f"{event.get('away_team','?')} @ {event.get('home_team','?')}"
        print(f"    [DBG] {game}: {len(candidates)} candidates | odds_data keys: {len(odds_data)}")
        for c in candidates[:6]:
            print(f"      {c['player']} {c['stat']} {c['direction']} {c['line']} "
                  f"wp={c['fair_prob']:.2f} edge={c['edge']:.3f} odds={c['odds']} "
                  f"books={list(c.get('book_odds',{}).keys())}")
    if len(candidates) < MIN_LEGS:
        if _debug:
            print(f"    [DBG] SKIP: only {len(candidates)} candidates < MIN_LEGS={MIN_LEGS}")
        return None

    pool = candidates[:40]
    n_no_common_book = n_odds_range = n_corr = 0
    for n_legs in range(min(MAX_LEGS, len(pool)), MIN_LEGS - 1, -1):
        leg_best_score = -1
        leg_best = None
        min_players = n_legs
        for combo in combinations(pool, n_legs):
            legs = list(combo)
            # Each leg must be from a different player
            if len(set(l["player"] for l in legs)) < min_players:
                continue
            if not _check_parlay_correlations_mlb(legs):
                n_corr += 1
                continue
            # All legs must be available on a single allowed book
            book_sets = [
                {k for k in leg.get("book_odds", {leg["book"]: leg["odds"]}).keys()
                 if k in SGP_ALLOWED_BOOKS}
                for leg in legs
            ]
            common_books = book_sets[0].intersection(*book_sets[1:])
            if not common_books:
                n_no_common_book += 1
                continue
            chosen_book = _pick_best_book(common_books)
            locked = []
            for leg in legs:
                bk_map = leg.get("book_odds", {leg["book"]: leg["odds"]})
                locked.append({**leg, "odds": bk_map.get(chosen_book, leg["odds"]),
                                "book": chosen_book})
            parlay_odds = _parlay_american(locked)
            if parlay_odds < MIN_PARLAY_ODDS or parlay_odds > MAX_PARLAY_ODDS:
                n_odds_range += 1
                continue
            score = _score_mlb_sgp(locked)
            if score > leg_best_score:
                leg_best_score = score
                leg_best = (locked, parlay_odds, score)
        if leg_best is not None:
            return leg_best
    if _debug:
        print(f"    [DBG] no SGP built: no_common_book={n_no_common_book} "
              f"odds_range={n_odds_range} corr_kill={n_corr}")
    return None


# -- Discord embed -------------------------------------------------------------

def _generate_mlb_thesis(legs):
    """Simple thesis label for MLB SGPs."""
    pitchers = [l for l in legs if l.get("is_pitcher")]
    batters  = [l for l in legs if not l.get("is_pitcher")]
    if len(pitchers) >= 2:
        teams = list({l["team"] for l in pitchers})
        return f"Pitcher duel — {'/'.join(teams)}"
    if pitchers and batters:
        p = pitchers[0]
        b_team = batters[0]["team"]
        return f"{p['player'].split()[-1]} deep + {b_team} hits"
    if batters:
        team = Counter(l["team"] for l in batters).most_common(1)[0][0]
        n_over  = sum(1 for l in batters if l["direction"] == "over")
        n_under = sum(1 for l in batters if l["direction"] == "under")
        if n_under > n_over:
            return f"pitcher suppresses {team} bats"
        elif n_over > n_under:
            return f"{team} hitting barrage"
        else:
            return f"{team} mixed batter stack"
    return "MLB game-script stack"


def build_mlb_sgp_embed(legs, parlay_odds, game, sgp_size=None, _copula_joint=None):
    from datetime import datetime
    now_et = datetime.now(ZoneInfo("America/New_York")).strftime("%I:%M %p ET")
    thesis = _generate_mlb_thesis(legs)
    book_name = display_book(_pick_best_book({l["book"] for l in legs}))
    n = len(legs)

    if _copula_joint is None:
        probs   = [l["fair_prob"] for l in legs]
        corr    = _build_corr_matrix_mlb(legs)
        _copula_joint = _copula_joint_prob(probs, corr)
    if sgp_size is None:
        sgp_size = _size_mlb_sgp(legs)

    parlay_implied = _implied_prob(parlay_odds)
    avg_wp = sum(l["fair_prob"] for l in legs) / n

    leg_lines = []
    for i, leg in enumerate(legs, 1):
        d = "O" if leg["direction"] == "over" else "U"
        edge_pct = leg["edge"] * 100
        wp_pct   = leg["fair_prob"] * 100
        leg_lines.append(
            f"**{i}.** {leg['player']} {d}{leg['line']} {leg['stat']} "
            f"({leg['odds']:+d}) — {wp_pct:.0f}% model"
        )

    legs_text = "\n".join(leg_lines)
    copula_pct  = _copula_joint * 100
    implied_pct = parlay_implied * 100
    edge_pp     = copula_pct - implied_pct

    desc = (
        f"**{game}**\n"
        f"*{thesis}*\n\n"
        f"{legs_text}\n\n"
        f"**{parlay_odds:+d}** | {n} legs | {sgp_size}u\n"
        f"Copula joint: {copula_pct:.1f}% | Implied: {implied_pct:.1f}% ({edge_pp:+.1f}pp)\n"
        f"Avg leg prob: {avg_wp*100:.0f}%\n"
        f"📍 Bet on: **{book_name}**"
    )

    return {
        "username": "PicksByJonny",
        "embeds": [{
            "title": "⚾ MLB SGP — Same-Game Parlay",
            "description": desc,
            "color": 0x2ECC71,  # green for MLB
            "footer": {"text": f"{BRAND_TAGLINE} | {now_et}"},
        }],
    }


# -- Console output ------------------------------------------------------------

def print_mlb_sgp(legs, parlay_odds, game, score):
    thesis = _generate_mlb_thesis(legs)
    print(f"\n  {'='*60}")
    print(f"  MLB SGP -- {game}")
    print(f"  Thesis: {thesis}")
    for leg in legs:
        d = "O" if leg["direction"] == "over" else "U"
        edge_pct = leg["edge"] * 100
        wp_pct   = leg["fair_prob"] * 100
        print(f"    {leg['player'][:20]:20s} {d}{leg['line']:4} {leg['stat']:4} "
              f"{leg['odds']:+5d} @ {display_book(leg['book']):12s} "
              f"| Edge: {edge_pct:.1f}% | WP: {wp_pct:.0f}%")
    sgp_size = _size_mlb_sgp(legs)
    avg_edge = sum(l["edge"] for l in legs) * 100 / len(legs)
    avg_wp   = sum(l["fair_prob"] for l in legs) * 100 / len(legs)
    print()
    print(f"  Parlay odds: {parlay_odds:+d}")
    print(f"  Legs: {len(legs)} | Avg edge: {avg_edge:.1f}% | Avg WP: {avg_wp:.0f}% | Size: {sgp_size}u | Score: {score:.3f}")
    print(f"\n  Correlation check:")
    for a, b in combinations(legs, 2):
        neg = _is_negatively_correlated_mlb(a, b)
        a_short = f"{a['player'].split()[-1]} {'O' if a['direction']=='over' else 'U'}{a['line']} {a['stat']}"
        b_short = f"{b['player'].split()[-1]} {'O' if b['direction']=='over' else 'U'}{b['line']} {b['stat']}"
        rho = _pairwise_rho_mlb(a, b)
        symbol = "XX" if neg else "--"
        print(f"    {symbol} {a_short} x {b_short}: rho={rho:.2f}")
    print(f"\n  {'='*60}")


# -- Logging -------------------------------------------------------------------

def _log_mlb_sgp(legs, parlay_odds, game, today_str, book="", sgp_size=None, copula_joint=None):
    """Append an MLB SGP to pick_log.csv as run_type='sgp', sport='MLB'."""
    try:
        from pick_log_schema import CANONICAL_HEADER
        from run_picks import PICK_LOG_PATH, _pick_log_lock, _normalize_odds, _normalize_size, _write_schema_sidecar
    except ImportError as e:
        print(f"  [MLB SGP] pick_log import failed — not logging: {e}")
        return

    log_path = Path(PICK_LOG_PATH)
    if not log_path.exists():
        return

    run_time = datetime.now(ZoneInfo("America/New_York")).strftime("%H:%M")

    legs_data = [
        {"player": l.get("player", ""), "direction": l.get("direction", "").lower(),
         "line": float(l.get("line", 0)), "stat": l.get("stat", ""),
         "sport": "MLB", "game": l.get("game", game), "win_prob": float(l.get("fair_prob", 0))}
        for l in legs
    ]
    legs_json = json.dumps(legs_data, separators=(",", ":"))

    player_desc = " / ".join(
        f"{l.get('player','').split()[-1]} "
        f"{'O' if l.get('direction','').lower()=='over' else 'U'}"
        f"{l.get('line','')} {l.get('stat','')}"
        for l in legs
    )

    row = {
        "date": today_str, "run_time": run_time, "run_type": "sgp", "sport": "MLB",
        "player": f"SGP {len(legs)}-leg", "team": "", "stat": "PARLAY",
        "line": "", "direction": "", "proj": "",
        "win_prob": round(copula_joint, 4) if copula_joint is not None else "",
        "edge": "", "odds": _normalize_odds(parlay_odds) if parlay_odds else "",
        "book": book, "tier": "SGP", "pick_score": "",
        "size": _normalize_size(sgp_size if sgp_size is not None else SGP_SIZE_DEFAULT),
        "game": player_desc, "mode": "", "result": "", "closing_odds": "", "clv": "",
        "card_slot": "", "is_home": "", "context_verdict": "", "context_reason": "",
        "context_score": "", "legs": legs_json, "over_p_raw": "",
    }

    try:
        with _pick_log_lock(log_path):
            with open(log_path, "r", newline="", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            already = any(
                r.get("date") == today_str and r.get("run_type") == "sgp"
                and r.get("sport") == "MLB" and r.get("game") == player_desc
                for r in rows
            )
            if already:
                print(f"  [MLB SGP] Already logged for {game} today — skipping.")
                return
            with open(log_path, "a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=CANONICAL_HEADER, extrasaction="ignore", restval="")
                writer.writerow(row)
                f.flush()
                os.fsync(f.fileno())
        print(f"  [MLB SGP] Logged to pick_log ({len(legs)} legs, {parlay_odds:+d})")
        try:
            _write_schema_sidecar(log_path)
        except Exception:
            pass
    except Exception as e:
        print(f"  [MLB SGP] pick_log write failed: {e}")


# -- Posting -------------------------------------------------------------------

def _joint_ev_ok_mlb(legs, parlay_odds, _copula_joint=None):
    """Plan 9 §9H joint-EV existence floor (MLB mirror of sgp_builder._joint_ev_ok).

    Returns (ok, joint, margin): ok is True iff the copula joint probability
    exceeds the book-implied parlay probability by at least SGP_JOINT_EV_MARGIN.
    """
    if _copula_joint is None:
        probs = [l["fair_prob"] for l in legs]
        corr = _build_corr_matrix_mlb(legs)
        _copula_joint = _copula_joint_prob(probs, corr)
    margin = _copula_joint - _implied_prob(parlay_odds)
    return margin >= SGP_JOINT_EV_MARGIN, _copula_joint, margin


def post_mlb_sgp(legs, parlay_odds, game, suppress_ping=False, today_str=None, save=True):
    from secrets_config import DISCORD_SGP_WEBHOOK
    webhook = DISCORD_SGP_WEBHOOK or DISCORD_BONUS_WEBHOOK
    if not webhook:
        print("  [MLB SGP] No SGP webhook configured — skipping.")
        return False

    _today = today_str or datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
    _guard_key = f"mlb_sgp:{_today}:{game}"
    try:
        from discord_guard import load_guard, save_guard
        _guard = load_guard()
        if _guard.get(_guard_key):
            print(f"  [MLB SGP] Already posted for {game} today — skipping.")
            return False
    except Exception:
        _guard = None

    probs  = [l["fair_prob"] for l in legs]
    corr   = _build_corr_matrix_mlb(legs)
    cj     = _copula_joint_prob(probs, corr)
    # Plan 9 §9H: belt-and-suspenders joint-EV floor (primary gate is in
    # run_mlb_sgp_builder phase 1; this protects direct post_mlb_sgp callers).
    ev_ok, _, ev_margin = _joint_ev_ok_mlb(legs, parlay_odds, _copula_joint=cj)
    if not ev_ok:
        print(f"  [MLB SGP] Joint-EV gate: margin {ev_margin:+.3f} < "
              f"{SGP_JOINT_EV_MARGIN} — not posting {game}.")
        return False
    size   = _size_mlb_sgp(legs)
    book   = _pick_best_book({l["book"] for l in legs})

    print(f"  [MLB SGP-sizing] avg_wp={sum(probs)/len(probs):.2f} "
          f"avg_edge={sum(l['edge'] for l in legs)/len(legs):.3f} → {size:.2f}u")

    payload = build_mlb_sgp_embed(legs, parlay_odds, game, sgp_size=size, _copula_joint=cj)
    try:
        from run_picks import _webhook_post
        ok = _webhook_post(webhook, payload, label=f"MLB SGP: {game}")
    except ImportError:
        import requests
        from http_utils import default_headers
        try:
            r = requests.post(webhook, json=payload, headers=default_headers(), timeout=10)
            r.raise_for_status()
            ok = True
        except Exception as e:
            print(f"  [MLB SGP] Discord post failed: {e}")
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
            _log_mlb_sgp(legs, parlay_odds, game, today_str, book=book,
                         sgp_size=size, copula_joint=cj)
        elif save and not today_str:
            print("[MLB SGP] WARNING: today_str is None — pick not logged")
    return ok


# -- Orchestrator --------------------------------------------------------------

def run_mlb_sgp_builder(csv_paths, dry_run=False, confirm=False, test=False,
                        save=True, debug=False):
    today_str   = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
    projections = {}
    for csv_path in csv_paths:
        path = Path(csv_path)
        if "mlb" not in path.name.lower():
            continue
        loaded = load_mlb_projections(path)
        projections.update(loaded)
        print(f"  [MLB SGP] Loaded {len(loaded)} players from {path.name}")
    if not projections:
        print("  [MLB SGP] No MLB projections found — skipping MLB SGP builder.")
        return []

    _log_mlb_sgp_rho_status()  # P1.6: report rho refit-trigger status + alerts

    events = fetch_mlb_events()
    print(f"  [MLB SGP] Fetched {len(events)} MLB games — building candidates...")

    confirmed_starters = fetch_confirmed_starters()
    if confirmed_starters:
        print(f"  [MLB SGP] Confirmed starters fetched: {len(confirmed_starters)} teams")
    else:
        print("  [MLB SGP] WARNING: No confirmed starters returned — SP scratch check disabled")

    # Phase 1: build SGPs for every game, collect scored candidates
    candidates = []  # list of (score, legs, parlay_odds, game)
    for event in events:
        eid  = event["id"]
        game = f"{event.get('away_team', '?')} @ {event.get('home_team', '?')}"
        odds_data = fetch_mlb_event_props(eid)
        if not odds_data:
            continue
        result = build_mlb_sgp(projections, odds_data, event, _debug=debug,
                                confirmed_starters=confirmed_starters)
        if result is None:
            continue
        legs, parlay_odds, score = result
        # Plan 9 §9H: joint-EV existence floor — rejected slips must NOT consume
        # MAX_SGPS_PER_DAY slots, so gate before candidates.append.
        ev_ok, ev_joint, ev_margin = _joint_ev_ok_mlb(legs, parlay_odds)
        if not ev_ok:
            print(f"  [MLB SGP] Joint-EV gate: joint {ev_joint:.3f} vs implied "
                  f"{_implied_prob(parlay_odds):.3f} (margin {ev_margin:+.3f} < "
                  f"{SGP_JOINT_EV_MARGIN}) — rejecting {game}.")
            continue
        candidates.append((score, legs, parlay_odds, game))

    if not candidates:
        print("\n  [MLB SGP] No valid MLB SGPs built for tonight's slate.")
        return []

    # Phase 2: take top MAX_SGPS_PER_DAY by score
    candidates.sort(key=lambda x: x[0], reverse=True)
    selected = candidates[:MAX_SGPS_PER_DAY]
    print(f"\n  [MLB SGP] {len(candidates)} valid SGPs found — posting top {len(selected)} by score.")

    results = []
    for score, legs, parlay_odds, game in selected:
        print_mlb_sgp(legs, parlay_odds, game, score)
        results.append((legs, parlay_odds, game))
        if dry_run:
            print("  [MLB SGP] --dry-run: skipping Discord post.")
        elif confirm:
            ans = input(f"  [MLB SGP] Post this SGP to Discord? (y/n): ").strip().lower()
            if ans == "y":
                ok = post_mlb_sgp(legs, parlay_odds, game, suppress_ping=test,
                                   today_str=today_str, save=save)
                print(f"  [MLB SGP] {'Posted' if ok else 'FAILED'}: {game}")
            else:
                print(f"  [MLB SGP] Skipped: {game}")
        else:
            ok = post_mlb_sgp(legs, parlay_odds, game, suppress_ping=test,
                               today_str=today_str, save=save)
            print(f"  [MLB SGP] {'Posted' if ok else 'FAILED'}: {game}")

    return results


# -- CLI entry point -----------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="JonnyParlay MLB SGP Builder")
    parser.add_argument("csvs", nargs="+", help="SaberSim MLB CSV file(s)")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--confirm", action="store_true")
    parser.add_argument("--test", action="store_true")
    args = parser.parse_args()
    run_mlb_sgp_builder(args.csvs, dry_run=args.dry_run, confirm=args.confirm, test=args.test)
