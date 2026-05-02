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
    used during 91k search; full 4000-sample MC used once for the final SGP.
    Embed now shows "Copula joint: X% | Implied: Y% (+Zpp)" for transparency.
"""
from __future__ import annotations

import csv
import math
import os
import random
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
MIN_DISTINCT_PLAYERS = 3     # ceil(n_legs * 0.75): 3-leg → 3 players, 4-leg → 3 players

ODDS_BASE = "https://api.the-odds-api.com/v4"
ODDS_REGIONS = "us,us2,us_ex"
API_SLEEP = 1.3

STAT_COLS = {"PTS": "PTS", "AST": "AST", "REB": "RB", "3PM": "3PT"}

SIGMA = {
    "PTS": {"mult": 0.35, "min": 4.5},
    "AST": {"mult": 0.45, "min": 1.3},
    "REB": {"mult": 0.58, "min": 2.5},
    # "3PM" intentionally absent — P16 routes 3PM through NB_STATS/NB_R. Do NOT add to SIGMA.
}
POISSON_STATS = {"AST", "REB"}
POISSON_CUTOFF = 8.5

# P16 (M1, May 1 2026): Negative Binomial for overdispersed count stats.
# Mirrors NB_STATS / NB_R in run_picks.py — keep in sync.
# r values updated 2026-05-02 per Research Brief 5 (empirical per-game game-log analysis).
# Previous 3PM r=12.3 underestimated overdispersion by ~6×.
NB_STATS = {"3PM", "BLK", "STL"}
NB_R = {
    "3PM": 2.1,   # empirical per-game r; Research Brief 5, 2026-05-02
    "BLK": 2.8,   # empirical per-game r; Research Brief 5, 2026-05-02
    "STL": 3.6,   # empirical per-game r; Research Brief 5, 2026-05-02
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
    # Defensive dominance -- unders on opposing players
    if direction == "under" and stat in ("PTS", "AST", "3PM"):
        tags.add(f"team_def_vs_{team}")
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
    # R0: Same player, same stat, same direction, different line = DEDUP
    # e.g. DiVincenzo O9.5 PTS + O8.5 PTS -- redundant (9.5 dominates 8.5)
    if (leg_a["player"] == leg_b["player"]
            and leg_a["stat"] == leg_b["stat"]
            and leg_a["direction"] == leg_b["direction"]
            and leg_a["line"] != leg_b["line"]):
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


# -- Math (mirrors run_picks.py) -------------------------------------------

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

def _negbinom_pmf(k, mu, r):
    """Negative binomial PMF with mean=mu, dispersion=r. Mirrors run_picks.py."""
    if mu <= 0:
        return 1.0 if k == 0 else 0.0
    k = int(k)
    if k < 0:
        return 0.0
    p = r / (r + mu)
    log_pmf = (
        math.lgamma(k + r) - math.lgamma(r) - math.lgamma(k + 1)
        + r * math.log(p)
        + k * math.log(1.0 - p)
    )
    return math.exp(log_pmf)

def _negbinom_cdf(k, mu, r):
    """Negative binomial CDF: P(X <= k). Mirrors run_picks.py."""
    if mu <= 0:
        return 1.0
    return min(sum(_negbinom_pmf(i, mu, r) for i in range(int(k) + 1)), 1.0)

def _implied_prob(odds):
    if odds == 0:
        return 0.0
    return abs(odds) / (abs(odds) + 100.0) if odds < 0 else 100.0 / (odds + 100.0)

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
        # P16 (M1) — Negative binomial for overdispersed count stats (3PM).
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

def _probit(p):
    """Standard normal quantile function Φ^{-1}(p).

    Uses math.erfinv when available (Python ≥ 3.12); otherwise falls back to
    the Beasley-Springer-Moro rational approximation (max error ≈ 4.5e-4).
    """
    p = max(1e-9, min(1.0 - 1e-9, p))
    try:
        return math.sqrt(2.0) * math.erfinv(2.0 * p - 1.0)
    except AttributeError:
        # BSM coefficients
        _a = [2.50662823884, -18.61500062529, 41.39119773534, -25.44106049637]
        _b = [-8.47351093090, 23.08336743743, -21.06224101826, 3.13082909833]
        _c = [0.3374754822726147, 0.9761690190917186, 0.1607979714918209,
              0.0276438810333863, 0.0038405729373609, 0.0003951896511349,
              0.0000321767881768, 0.0000002888167364, 0.0000003960315187]
        y = p - 0.5
        if abs(y) < 0.42:
            r = y * y
            return y * ((((_a[3]*r + _a[2])*r + _a[1])*r + _a[0])
                        / ((((_b[3]*r + _b[2])*r + _b[1])*r + _b[0])*r + 1.0))
        r = p if y < 0 else 1.0 - p
        r = math.log(-math.log(r))
        x = _c[0] + r*(_c[1] + r*(_c[2] + r*(_c[3] + r*(_c[4]
              + r*(_c[5] + r*(_c[6] + r*(_c[7] + r*_c[8])))))))
        return -x if y < 0 else x


def _pairwise_rho(leg_a, leg_b):
    """Pairwise Gaussian copula correlation ρ for two SGP legs.

    Calibrated from empirical NBA game-log correlation analysis.  Values are
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


def _cholesky(mat):
    """Lower triangular Cholesky L such that mat = L @ L^T (n ≤ 4).

    Clips near-zero diagonal to avoid sqrt of negative due to floating-point
    rounding on near-singular matrices.
    """
    n = len(mat)
    L = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1):
            s = sum(L[i][k] * L[j][k] for k in range(j))
            if i == j:
                L[i][j] = math.sqrt(max(mat[i][i] - s, 1e-12))
            else:
                L[i][j] = (mat[i][j] - s) / L[j][j] if L[j][j] > 1e-12 else 0.0
    return L


def _copula_joint_prob(probs, corr_mat, n_samples=4000, seed=42):
    """Gaussian copula joint probability via Monte Carlo.

    P(all legs hit) accounting for inter-leg correlations.  Algorithm:
      1. Factorize R = L L^T  (Cholesky)
      2. Sample ε ~ N(0, I_n)
      3. x = L ε  → correlated standard normals with cov = R
      4. U_i = Φ(x_i)  → correlated uniform marginals
      5. Joint hit = all U_i ≤ p_i  (equivalent to all x_i ≤ Φ^{-1}(p_i))

    At n_samples=4000: SE ≈ 0.7% for joint≈0.40.  Fixed seed gives
    reproducible scores for identical leg sets.

    Runtime: ~2 ms for 4-leg at 4000 samples (called once per final SGP).
    """
    n = len(probs)
    if n == 0:
        return 0.0
    if n == 1:
        return probs[0]
    try:
        L = _cholesky(corr_mat)
    except Exception:
        result = 1.0
        for p in probs:
            result *= p
        return result

    rng = random.Random(seed)
    gauss = rng.gauss
    erf = math.erf
    inv_sqrt2 = 1.0 / math.sqrt(2.0)
    hits = 0
    for _ in range(n_samples):
        eps = [gauss(0.0, 1.0) for _ in range(n)]
        ok = True
        for i in range(n):
            xi = sum(L[i][k] * eps[k] for k in range(i + 1))
            ui = 0.5 * (1.0 + erf(xi * inv_sqrt2))
            if ui > probs[i]:
                ok = False
                break
        if ok:
            hits += 1
    return hits / n_samples


def _copula_joint_approx(probs, avg_rho):
    """Fast equicorrelation Gaussian copula approximation for combo scoring.

    Linearly interpolates between independence (ρ=0) and perfect correlation
    (ρ=1, joint = min(p_i)).  Error < 3% for ρ ∈ [0, 0.40] — accurate enough
    to rank 91k combos; full MC is reserved for the final chosen SGP.
    """
    p_indep = 1.0
    for p in probs:
        p_indep *= p
    p_min = min(probs)
    return p_indep + avg_rho * (p_min - p_indep)


def _american_to_decimal(odds):
    return 1 + odds / 100 if odds > 0 else 1 + 100 / abs(odds)

def _decimal_to_american(dec):
    if dec >= 2.0:
        return int(round((dec - 1) * 100))
    else:
        return int(round(-100 / (dec - 1)))


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
                        Uses fast equicorrelation approx (microseconds per combo).
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

    # L8: fast copula approx for combo scoring — avg ρ across all leg pairs.
    # Benchmark: 3-leg at 0.70 avg WP, avg_rho=0.30 → copula_joint ≈ 0.385
    # (vs independence 0.343); ideal thresholds: 3-leg=0.38, 4-leg=0.25.
    pairs = list(combinations(range(n), 2))
    avg_rho = (sum(_pairwise_rho(legs[i], legs[j]) for i, j in pairs) / len(pairs)
               if pairs else 0.0)
    probs = [l["fair_prob"] for l in legs]
    copula_joint = _copula_joint_approx(probs, max(avg_rho, 0.0))
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
    parlay_implied = _implied_prob(_parlay_american(legs))
    if _copula_joint - parlay_implied >= 0.10:
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
        # Player diversity gate: require at least ceil(n_legs * 0.75) distinct players.
        # 3-leg → min 3 players (all different). 4-leg → min 3 players.
        min_players = math.ceil(n_legs * 0.75)
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


def build_sgp_embed(legs, parlay_odds, game, sgp_size=None):
    now_et = datetime.now(ZoneInfo("America/New_York")).strftime("%I:%M %p ET")
    thesis = _generate_thesis(legs)
    book = _sgp_book(legs)
    cohesion_raw = _correlation_cohesion(legs)
    # L8: compute copula joint prob once; reuse for sizing + display.
    _probs = [l["fair_prob"] for l in legs]
    _corr  = _build_corr_matrix(legs)
    copula_joint = _copula_joint_prob(_probs, _corr)
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
        f"**+{parlay_odds}** | {len(legs)} legs | {sgp_size:.2f}u",
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


def _log_sgp(legs, parlay_odds, game, today_str, book="", sgp_size=None):
    """Append an SGP to pick_log.csv as run_type='sgp'."""
    import csv, json, os
    from pathlib import Path
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
        "win_prob":        "",
        "edge":            "",
        "odds":            _normalize_odds(parlay_odds) if parlay_odds else "",
        "book":            book,
        "tier":            "SGP",
        "pick_score":      "",
        "size":            _normalize_size(sgp_size if sgp_size is not None else size_sgp(legs, _correlation_cohesion(legs))),
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
    }

    try:
        with _pick_log_lock(log_path):
            with open(log_path, "r", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                header = reader.fieldnames or list(CANONICAL_HEADER)
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
                writer = csv.DictWriter(f, fieldnames=header, extrasaction="ignore")
                writer.writerow(row)
                f.flush()
                os.fsync(f.fileno())
        print(f"  [SGP] 📝 Logged to pick_log ({len(legs)} legs, +{parlay_odds})")
        try:
            _write_schema_sidecar(log_path)
        except Exception:
            pass
    except Exception as e:
        print(f"  [SGP] ⚠ pick_log write failed: {e}")


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
    sgp_size = size_sgp(legs, cohesion_val)
    print(f"  [SGP-sizing] avg_wp={sum(l['fair_prob'] for l in legs)/len(legs):.2f} cohesion={cohesion_val:.2f} avg_edge={sum(l['edge'] for l in legs)/len(legs):.3f} → {sgp_size:.2f}u")
    payload = build_sgp_embed(legs, parlay_odds, game, sgp_size=sgp_size)
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
            _log_sgp(legs, parlay_odds, game, today_str, book=book, sgp_size=sgp_size)
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
    print(f"  Parlay odds: +{parlay_odds}")
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
        print_sgp(legs, parlay_odds, game, score)
        results.append((legs, parlay_odds, game))
        if dry_run:
            reason = "--dry-run" if not save else "--no-discord"
            print(f"  [SGP] {reason}: skipping Discord post.")
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
