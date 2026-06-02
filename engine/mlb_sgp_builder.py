"""mlb_sgp_builder.py -- MLB Same-Game Parlay builder for JonnyParlay.
3-4 legs, +200-+450 target range.
Sizing: 0.25u default, 0.50u when copula EV margin >= 0.10 + avg edge >= 0.035.
Usage: python mlb_sgp_builder.py <csv> [--dry-run] [--confirm]

Stats available in SGP pool:
  Pitchers: K (strikeouts, over >= 5.5 only), OUTS (recorded outs)
  Batters:  HITS
  Shadow stats (HRR/RBI/RUNS/ER) excluded until they graduate to live status.

Hard kill rules (R0-R3):
  R0: Same player, same stat, same direction (dedup)
  R1: Same player, same stat, opposite direction (contradiction)
  R2: Same pitcher, both K and OUTS (r ~ 0.70 — both driven by IP/dominance)
  R3: Pitcher K over + opposing batter HITS over (rho ~ -0.30 — more K = fewer balls in play)

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

# Reuse pure-math helpers from NBA SGP builder to avoid duplication
from sgp_builder import (
    _cholesky,
    _copula_joint_prob,
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
MAX_LEG_ODDS = -115
MAX_SGPS_PER_DAY = 3   # MLB has 15 games/night vs NBA's ~5 — cap to top 3 by score

ODDS_BASE = "https://api.the-odds-api.com/v4"
ODDS_REGIONS = "us,us2,us_ex"
API_SLEEP = 1.3

# Stats and their API market keys
MLB_SGP_MARKETS = "pitcher_strikeouts,pitcher_outs,batter_hits"

MLB_SGP_STAT_MAP = {
    "pitcher_strikeouts": "K",
    "pitcher_outs":       "OUTS",
    "batter_hits":        "HITS",
}

# Stat families for correlation and kill rules
_PITCHER_STATS = {"K", "OUTS"}   # All come from pitchers — same pitcher R2 kill
_BATTER_STATS  = {"HITS"}        # Come from batters

# Stat distribution parameters (mirrors run_picks.py / sgp_builder.py)
# K: Poisson confirmed (within-player var/mu = 1.031, 69k pitcher games, 2026-05-26)
# HITS: Poisson (within-batter var/mu ~ 1.0, confirmed Poisson for low-mean counts)
_POISSON_STATS_MLB = {"K", "HITS"}

# OUTS: Normal (SIGMA from run_picks.py — mult=0.311, min=1.0)
_OUTS_SIGMA = {"mult": 0.311, "min": 1.0}

# K line gate: K overs < 5.5 are structurally biased (G_K_MIN_LINE gate in run_picks.py)
_K_MIN_LINE_OVER = 5.5


# -- Math helpers (self-contained; Poisson/Normal CDF) -------------------------

def _poisson_pmf(k, lam):
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return math.exp(-lam) * (lam ** k) / math.factorial(k)


def _poisson_cdf(k, lam):
    if lam <= 0:
        return 1.0
    return min(sum(_poisson_pmf(i, lam) for i in range(int(k) + 1)), 1.0)


def _normal_cdf(x, mu, sigma):
    if sigma <= 0:
        return 1.0 if x >= mu else 0.0
    return 0.5 * (1.0 + math.erf((x - mu) / (sigma * math.sqrt(2))))


def _implied_prob(odds):
    if odds == 0:
        return 0.0
    return abs(odds) / (abs(odds) + 100.0) if odds < 0 else 100.0 / (odds + 100.0)


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

    # R2: Same pitcher, K + OUTS (both driven by IP/dominance, r ~ 0.70)
    if (leg_a["player"] == leg_b["player"]
            and leg_a["stat"] in _PITCHER_STATS
            and leg_b["stat"] in _PITCHER_STATS):
        return True

    # R3: Pitcher K over + opposing batter HITS over (rho ~ -0.30)
    # More Ks = fewer balls in play = fewer hits for opposing team
    for k_leg, hits_leg in ((leg_a, leg_b), (leg_b, leg_a)):
        if (k_leg["stat"] == "K" and k_leg["direction"] == "over"
                and hits_leg["stat"] == "HITS" and hits_leg["direction"] == "over"
                and k_leg.get("team") != hits_leg.get("team")):
            return True

    return False


def _pairwise_rho_mlb(leg_a, leg_b):
    """Pairwise Gaussian copula correlation rho for two MLB SGP legs.

    Conservative values — calibrated from structural priors, not empirical
    MLB game-log correlations (insufficient SGP sample as of 2026-05-29).

    Update these values when 100+ scored MLB SGP slips are available.
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

    # Pitcher + batter (same or different teams, same game) — defense != offense
    return 0.02


def _build_corr_matrix_mlb(legs):
    n = len(legs)
    return [[1.0 if i == j else _pairwise_rho_mlb(legs[i], legs[j])
             for j in range(n)] for i in range(n)]


def _check_parlay_correlations_mlb(legs):
    for a, b in combinations(legs, 2):
        if _is_negatively_correlated_mlb(a, b):
            return False
    return True


# -- Scoring -------------------------------------------------------------------

def _score_mlb_sgp(legs):
    """Score an MLB SGP.

    Weights:
      copula  0.35 — primary EV signal (correlation-adjusted joint hit rate; full 300-sample MC)
      edge    0.30 — per-leg model edge
      odds    0.20 — Gaussian reward around target odds
      stat_div 0.15 — reward for mixing pitcher + batter legs
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
    copula_joint = _copula_joint_prob(probs, corr_mat, n_samples=300)
    copula_ideal = 0.38 if n <= 3 else 0.25
    copula_score = min(copula_joint / copula_ideal, 1.0)

    # Reward pitcher + batter mix (more stat diversity = better game-script narrative)
    stat_div = len(set(l["stat"] for l in legs)) / n

    return copula_score * 0.35 + avg_edge * 0.30 + odds_score * 0.20 + stat_div * 0.15


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
                    k   = float(clean.get("K",  0) or 0)
                    ip  = float(clean.get("IP", 0) or 0)
                    if k > 0:
                        proj["K"] = k
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
    r = requests.get(url, params=params, headers=default_headers(), timeout=15)
    r.raise_for_status()
    return r.json()


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
                # K unders structurally biased — exclude from SGP pool
                if stat == "K" and direction == "under":
                    continue
                # K overs below min line excluded
                if stat == "K" and direction == "over" and line < _K_MIN_LINE_OVER:
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
        if fair < MIN_LEG_WIN_PROB:
            continue
        if odds > MAX_LEG_ODDS:
            continue
        if odds < -300:
            continue

        wp_excess  = max(0.0, fair - MIN_LEG_WIN_PROB)
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


def build_mlb_sgp(projections, odds_data, event):
    """Build the best 3-4 leg MLB SGP for a given game."""
    candidates = build_candidate_legs_mlb(projections, odds_data, event)
    if len(candidates) < MIN_LEGS:
        return None

    pool = candidates[:40]
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
                continue
            # All legs must be available on a single allowed book
            book_sets = [
                {k for k in leg.get("book_odds", {leg["book"]: leg["odds"]}).keys()
                 if k in SGP_ALLOWED_BOOKS}
                for leg in legs
            ]
            common_books = book_sets[0].intersection(*book_sets[1:])
            if not common_books:
                continue
            chosen_book = _pick_best_book(common_books)
            locked = []
            for leg in legs:
                bk_map = leg.get("book_odds", {leg["book"]: leg["odds"]})
                locked.append({**leg, "odds": bk_map.get(chosen_book, leg["odds"]),
                                "book": chosen_book})
            parlay_odds = _parlay_american(locked)
            if parlay_odds < MIN_PARLAY_ODDS or parlay_odds > MAX_PARLAY_ODDS:
                continue
            score = _score_mlb_sgp(locked)
            if score > leg_best_score:
                leg_best_score = score
                leg_best = (locked, parlay_odds, score)
        if leg_best is not None:
            return leg_best
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
        if p["stat"] == "K" and p["direction"] == "over":
            return f"{p['player'].split()[-1]} dominates + {b_team} bats"
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
                        save=True):
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

    events = fetch_mlb_events()
    print(f"  [MLB SGP] Fetched {len(events)} MLB games — building candidates...")

    # Phase 1: build SGPs for every game, collect scored candidates
    candidates = []  # list of (score, legs, parlay_odds, game)
    for event in events:
        eid  = event["id"]
        game = f"{event.get('away_team', '?')} @ {event.get('home_team', '?')}"
        odds_data = fetch_mlb_event_props(eid)
        if not odds_data:
            continue
        result = build_mlb_sgp(projections, odds_data, event)
        if result is None:
            continue
        legs, parlay_odds, score = result
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
