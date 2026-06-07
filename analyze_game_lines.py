"""
Standalone game-line edge analyzer.

Distributions:
  MLB team totals : Negative Binomial (var/mu~2.26; NB r=3.548)
  MLB moneyline   : NB direct probability sum (home wins)
  All other markets: Normal (same GAME_SIGMA values as run_picks.py)
"""
import math, requests, sys
from pathlib import Path
from typing import Optional

from engine.secrets_config import ODDS_API_KEY

API_KEY   = ODDS_API_KEY
BASE      = "https://api.the-odds-api.com/v4/sports"
REGIONS   = "us,us2,us_ex"
BOOKS_STR = "draftkings,fanduel,betmgm,caesars,pointsbetus"
HEADERS   = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# ── Distributions ──────────────────────────────────────────────────────────
def normal_cdf(x, mu, sigma):
    if sigma <= 0:
        return 1.0 if x >= mu else 0.0
    return 0.5 * (1.0 + math.erf((x - mu) / (sigma * math.sqrt(2))))

def negbinom_pmf(k, mu, r):
    """NB PMF: P(X=k) with mean=mu, dispersion=r."""
    if mu <= 0:
        return 1.0 if k == 0 else 0.0
    k = int(k)
    if k < 0:
        return 0.0
    p = r / (r + mu)
    log_pmf = (
        math.lgamma(k + r) - math.lgamma(r) - math.lgamma(k + 1)
        + r * math.log(p) + k * math.log(1.0 - p)
    )
    return math.exp(log_pmf)

def negbinom_cdf(k, mu, r):
    """NB CDF: P(X <= k) with mean=mu, dispersion=r."""
    if mu <= 0:
        return 1.0
    total = 0.0
    for i in range(int(k) + 1):
        total += negbinom_pmf(i, mu, r)
    return min(total, 1.0)

def mlb_ml_from_nb(mu_home, mu_away, r):
    """P(home wins) via direct NB probability sum. Ties = 50/50."""
    if mu_home <= 0 or mu_away <= 0:
        return 0.5
    home_wp = 0.0
    for k in range(31):
        ph = negbinom_pmf(k, mu_home, r)
        pa_lt = negbinom_cdf(k - 1, mu_away, r) if k > 0 else 0.0
        pa_eq = negbinom_pmf(k, mu_away, r)
        home_wp += ph * (pa_lt + 0.5 * pa_eq)
    return min(max(home_wp, 0.0), 1.0)

# ── Sigmas (mirrored from GAME_SIGMA + F5_SIGMA in run_picks.py) ───────────
# NHL calibrated 2026-06-05 from 3936 games. MLB team total uses NB (not sigma).
SIGMA = {
    "MLB":  {"total": 4.0,  "spread": 3.8,  "team": 3.0,  "ml": 4.75},
    # NBA calibrated 2026-06-05 (Plan 6 §6, 3,922 games): residual-basis SDs
    # (raw total SD=20.20, residual=19.33; margin residual=15.27; rho=+0.227).
    "NBA":  {"total": 18.5, "spread": 12.5, "team": 11.0, "ml": 12.5},
    "NHL":  {"total": 2.311, "spread": 2.614, "team": 1.744, "ml": 2.614},
}
F5_SIGMA  = {"total": 2.65, "spread": 2.70, "team": 2.10}
F5_SCALAR = 0.540

# NB dispersion for MLB team run-scoring (calibrated 2026-06-05, n=8095 regular-season games)
MLB_TEAM_RUN_R = 3.548

# Team-specific sigma JSONs (mirrored from run_picks.py) — loaded at startup
_TEAM_SIGMAS_AGL: dict = {}
_TEAM_SIGMAS_MEANSQ_AGL: dict = {}

def _load_team_sigmas_agl():
    import json as _json
    _data_dir = Path(__file__).parent / "data"
    for sport, fname in [("NHL", "team_sigmas_nhl.json"), ("MLB", "team_sigmas_mlb.json"),
                         ("NBA", "team_sigmas_nba.json"), ("WNBA", "team_sigmas_wnba.json")]:
        p = _data_dir / fname
        if p.exists():
            data = _json.loads(p.read_text())
            _TEAM_SIGMAS_AGL[sport] = data
            sq = [t["score_sigma"] ** 2 for t in data.values()
                  if isinstance(t, dict) and t.get("score_sigma") and t.get("n_games", 0) >= 20]
            _TEAM_SIGMAS_MEANSQ_AGL[sport] = (sum(sq) / len(sq)) if sq else 0.0

_load_team_sigmas_agl()

def get_game_sigma(sport, home_abbr, away_abbr, market):
    """Return matchup-specific sigma; falls back to SIGMA league average.

    Plan 6 §6 (2026-06-05): relative-variability scaler on the per-market league
    sigma — sigma_league(market) * sqrt((σh²+σa²)/(2·σ̄²)) — mirrors run_picks.py.
    """
    league = SIGMA.get(sport, SIGMA["NBA"])
    league_sigma = league.get(market, 10.0)
    team_data = _TEAM_SIGMAS_AGL.get(sport, {})
    mean_sq = _TEAM_SIGMAS_MEANSQ_AGL.get(sport, 0.0)
    if not team_data or mean_sq <= 0:
        return league_sigma
    h = team_data.get((home_abbr or "").upper())
    a = team_data.get((away_abbr or "").upper())
    if (not h or not a
            or h.get("n_games", 0) < 20 or a.get("n_games", 0) < 20):
        return league_sigma
    if market in ("total", "ml", "spread"):
        scaler = math.sqrt((h["score_sigma"] ** 2 + a["score_sigma"] ** 2) / (2.0 * mean_sq))
        return league_sigma * scaler
    return league_sigma

def get_game_sigma_team(sport, team_abbr):
    """Return sigma for one team's scoring — used for team total picks."""
    league = SIGMA.get(sport, SIGMA["NBA"])
    league_sigma = league.get("team", 10.0)
    t = _TEAM_SIGMAS_AGL.get(sport, {}).get((team_abbr or "").upper())
    return t["score_sigma"] if t and t.get("n_games", 0) >= 20 else league_sigma

def get_mlb_team_run_r(team_abbr):
    """Return per-team NB dispersion r for MLB run-scoring; falls back to MLB_TEAM_RUN_R."""
    return _TEAM_SIGMAS_AGL.get("MLB", {}).get((team_abbr or "").upper(), {}).get("nb_r", MLB_TEAM_RUN_R)

# ── Projections (away_abbr, away_proj, home_abbr, home_proj) ───────────────
MLB_PROJS = [
    ("BOS", 3.9, "NYY", 4.4),
    ("BAL", 4.1, "TOR", 4.6),
    ("TB",  4.4, "MIA", 3.7),
    ("PIT", 4.1, "ATL", 4.5),
    ("ATH", 4.6, "HOU", 4.5),
    ("CLE", 4.3, "TEX", 3.7),
    ("KC",  4.2, "MIN", 4.2),
    ("CIN", 4.5, "STL", 4.8),
    ("MIL", 6.4, "COL", 5.3),
    ("WSH", 4.4, "ARI", 4.9),
    ("NYM", 3.7, "SD",  4.0),
    ("LAA", 3.7, "LAD", 4.9),
]
NBA_PROJS = [
    ("NYK", 107.7, "SAS", 109.1),
]

# ── Team name to abbreviation ───────────────────────────────────────────────
MLB_NAME_MAP = {
    "boston red sox": "BOS", "new york yankees": "NYY",
    "baltimore orioles": "BAL", "toronto blue jays": "TOR",
    "tampa bay rays": "TB", "miami marlins": "MIA",
    "pittsburgh pirates": "PIT", "atlanta braves": "ATL",
    "oakland athletics": "ATH", "athletics": "ATH",
    "sacramento athletics": "ATH", "houston astros": "HOU",
    "cleveland guardians": "CLE", "texas rangers": "TEX",
    "kansas city royals": "KC", "minnesota twins": "MIN",
    "cincinnati reds": "CIN", "st. louis cardinals": "STL",
    "milwaukee brewers": "MIL", "colorado rockies": "COL",
    "washington nationals": "WSH", "arizona diamondbacks": "ARI",
    "new york mets": "NYM", "san diego padres": "SD",
    "los angeles angels": "LAA", "los angeles dodgers": "LAD",
    "chicago white sox": "CWS", "chicago cubs": "CHC",
    "detroit tigers": "DET", "seattle mariners": "SEA",
    "san francisco giants": "SF", "philadelphia phillies": "PHI",
}
NBA_NAME_MAP = {
    "new york knicks": "NYK", "san antonio spurs": "SAS",
    "boston celtics": "BOS", "miami heat": "MIA",
    "golden state warriors": "GSW", "los angeles lakers": "LAL",
    "denver nuggets": "DEN", "oklahoma city thunder": "OKC",
    "minnesota timberwolves": "MIN", "indiana pacers": "IND",
    "cleveland cavaliers": "CLE", "detroit pistons": "DET",
    "phoenix suns": "PHX", "dallas mavericks": "DAL",
    "houston rockets": "HOU", "memphis grizzlies": "MEM",
    "new orleans pelicans": "NOP", "chicago bulls": "CHI",
    "atlanta hawks": "ATL", "milwaukee bucks": "MIL",
    "toronto raptors": "TOR", "charlotte hornets": "CHA",
    "orlando magic": "ORL", "washington wizards": "WSH",
    "brooklyn nets": "BKN", "philadelphia 76ers": "PHI",
    "portland trail blazers": "POR", "utah jazz": "UTA",
    "sacramento kings": "SAC", "los angeles clippers": "LAC",
}

# ── API helpers ────────────────────────────────────────────────────────────
def fetch_odds(sport_key, markets):
    url = f"{BASE}/{sport_key}/odds"
    r = requests.get(url, params={
        "apiKey": API_KEY, "regions": REGIONS,
        "markets": markets, "oddsFormat": "american",
        "bookmakers": BOOKS_STR,
    }, headers=HEADERS, timeout=15)
    if r.status_code != 200:
        print(f"  [API {r.status_code}] {r.text[:300]}")
        return []
    return r.json()

def fetch_event_odds(sport_key, event_id, markets):
    url = f"{BASE}/{sport_key}/events/{event_id}/odds"
    r = requests.get(url, params={
        "apiKey": API_KEY, "regions": REGIONS,
        "markets": markets, "oddsFormat": "american",
        "bookmakers": BOOKS_STR,
    }, headers=HEADERS, timeout=15)
    if r.status_code != 200:
        return None
    return r.json()

# ── Odds math ──────────────────────────────────────────────────────────────
def american_to_prob(odds):
    if odds >= 0:
        return 100 / (odds + 100)
    return abs(odds) / (abs(odds) + 100)

def novigp(p1, p2):
    total = p1 + p2
    if total <= 0:
        return 0.5, 0.5
    return p1 / total, p2 / total

def best_book_odds(game, market_key):
    """Best (lowest total implied) two-outcome market across bookmakers."""
    best, best_vig = None, 999.0
    for bm in game.get("bookmakers", []):
        for mkt in bm.get("markets", []):
            if mkt["key"] != market_key:
                continue
            outs = mkt["outcomes"]
            if len(outs) < 2:
                continue
            tot = sum(american_to_prob(o["price"]) for o in outs)
            if tot < best_vig:
                best_vig = tot
                best = {"book": bm["title"], "outcomes": outs, "vig": tot - 1.0}
    return best

def team_total_odds(game, abbr_list):
    """Return {abbr: {line, over_odds, under_odds, book}} from team_totals market."""
    result = {}
    for bm in game.get("bookmakers", []):
        for mkt in bm.get("markets", []):
            if mkt["key"] != "team_totals":
                continue
            for out in mkt.get("outcomes", []):
                desc = out.get("description", "").upper()
                for abbr in abbr_list:
                    if abbr not in desc:
                        continue
                    side = out["name"].lower()
                    if abbr not in result:
                        result[abbr] = {"book": bm["title"], "line": out.get("point")}
                    result[abbr][f"{side}_odds"] = out["price"]
                    if out.get("point"):
                        result[abbr]["line"] = out["point"]
    return result

# ── Edge formatting ────────────────────────────────────────────────────────
def edge_str(model_p, market_p, label, line=None, odds=None):
    edge = model_p - market_p
    if abs(edge) < 0.020:
        return None
    marker = "*** EDGE" if abs(edge) >= 0.04 else "  + edge"
    parts = [f"  {marker}  {label:<32}"]
    if line is not None:
        parts.append(f" line={line}")
    if odds is not None:
        parts.append(f" odds={odds:+d}" if isinstance(odds, int) else f" odds={odds}")
    parts.append(f"  model={model_p:.3f}  mktNV={market_p:.3f}  edge={edge:+.3f}")
    return "".join(parts)

def find_outcome(outcomes, name_map, abbr):
    for o in outcomes:
        if name_map.get(o["name"].lower()) == abbr:
            return o
        if abbr in o["name"].upper():
            return o
    return None

# ── MLB team total NB probability ──────────────────────────────────────────
def mlb_tt_prob(proj, line, direction="over"):
    """P(over/under) for MLB team total using NB distribution."""
    k_floor = int(math.floor(line))
    if line == k_floor:  # integer line — push-adjusted
        push = negbinom_pmf(k_floor, proj, MLB_TEAM_RUN_R)
        non_push = 1.0 - push
        if non_push <= 0:
            return 0.5
        if direction == "over":
            return (1.0 - negbinom_cdf(k_floor, proj, MLB_TEAM_RUN_R)) / non_push
        else:
            return negbinom_cdf(k_floor - 1, proj, MLB_TEAM_RUN_R) / non_push
    else:  # half-line
        if direction == "over":
            return 1.0 - negbinom_cdf(k_floor, proj, MLB_TEAM_RUN_R)
        else:
            return negbinom_cdf(k_floor, proj, MLB_TEAM_RUN_R)

# ── MLB analysis ────────────────────────────────────────────────────────────
def analyze_mlb(games_data):
    print("\n" + "="*72)
    print("MLB GAME LINES")
    print("  ML/spread/total: Normal  |  Team totals: NB(r=3.548)  |  ML: NB direct sum")
    print("="*72)

    sig = SIGMA["MLB"]
    proj_map = {(a, h): (ap, hp) for a, ap, h, hp in MLB_PROJS}
    matched = 0

    for game in games_data:
        away_name = game.get("away_team", "").lower()
        home_name = game.get("home_team", "").lower()
        away_abbr = MLB_NAME_MAP.get(away_name)
        home_abbr = MLB_NAME_MAP.get(home_name)
        if not away_abbr or not home_abbr:
            continue
        if (away_abbr, home_abbr) not in proj_map:
            if (home_abbr, away_abbr) in proj_map:
                away_abbr, home_abbr = home_abbr, away_abbr
            else:
                continue

        matched += 1
        away_proj, home_proj = proj_map[(away_abbr, home_abbr)]
        total_proj = away_proj + home_proj
        margin = home_proj - away_proj

        edges = []

        # MONEYLINE — NB direct sum
        ml = best_book_odds(game, "h2h")
        if ml:
            outs = ml["outcomes"]
            oa = find_outcome(outs, MLB_NAME_MAP, away_abbr)
            oh = find_outcome(outs, MLB_NAME_MAP, home_abbr)
            if oa and oh:
                pa_nv, ph_nv = novigp(american_to_prob(oa["price"]), american_to_prob(oh["price"]))
                mh = mlb_ml_from_nb(home_proj, away_proj, MLB_TEAM_RUN_R)
                ma = 1.0 - mh
                e = edge_str(mh, ph_nv, f"ML HOME  {home_abbr}", odds=oh["price"])
                if e: edges.append(e)
                e = edge_str(ma, pa_nv, f"ML AWAY  {away_abbr}", odds=oa["price"])
                if e: edges.append(e)

        # RUN LINE (spread) — Normal
        sp = best_book_odds(game, "spreads")
        if sp:
            outs = sp["outcomes"]
            oa = find_outcome(outs, MLB_NAME_MAP, away_abbr)
            oh = find_outcome(outs, MLB_NAME_MAP, home_abbr)
            if oa and oh:
                sp_line = oh.get("point", 0)
                ph_nv, pa_nv = novigp(american_to_prob(oh["price"]), american_to_prob(oa["price"]))
                cover_h = 1.0 - normal_cdf(-sp_line, margin, sig["spread"])
                e = edge_str(cover_h,       ph_nv, f"SPREAD HOME {home_abbr} ({sp_line:+.1f})", odds=oh["price"])
                if e: edges.append(e)
                e = edge_str(1.0-cover_h,   pa_nv, f"SPREAD AWAY {away_abbr} ({-sp_line:+.1f})", odds=oa["price"])
                if e: edges.append(e)

        # GAME TOTAL — Normal
        tot = best_book_odds(game, "totals")
        if tot:
            outs = tot["outcomes"]
            ov = next((o for o in outs if o["name"].lower()=="over"), None)
            un = next((o for o in outs if o["name"].lower()=="under"), None)
            if ov and un:
                tline = ov.get("point", 0)
                pov_nv, pun_nv = novigp(american_to_prob(ov["price"]), american_to_prob(un["price"]))
                mov = 1.0 - normal_cdf(tline, total_proj, sig["total"])
                e = edge_str(mov,      pov_nv, f"TOTAL OVER  ({tline})", odds=ov["price"])
                if e: edges.append(e)
                e = edge_str(1.0-mov,  pun_nv, f"TOTAL UNDER ({tline})", odds=un["price"])
                if e: edges.append(e)

        # EVENT-SPECIFIC: team_totals + F5
        eid = game.get("id")
        ev = None
        if eid:
            ev = fetch_event_odds("baseball_mlb", eid,
                "team_totals,h2h_1st_5_innings,spreads_1st_5_innings,totals_1st_5_innings")

        # TEAM TOTALS — NB
        if ev:
            tt = team_total_odds(ev, [away_abbr, home_abbr])
            for abbr, proj in [(away_abbr, away_proj), (home_abbr, home_proj)]:
                info = tt.get(abbr, {})
                ttl = info.get("line")
                oo  = info.get("over_odds")
                uo  = info.get("under_odds")
                if not ttl or oo is None or uo is None:
                    continue
                pov_nv, pun_nv = novigp(american_to_prob(oo), american_to_prob(uo))
                mov   = mlb_tt_prob(proj, ttl, "over")
                mun   = mlb_tt_prob(proj, ttl, "under")
                e = edge_str(mov, pov_nv, f"TT OVER  {abbr} ({ttl})", odds=oo)
                if e: edges.append(e)
                e = edge_str(mun, pun_nv, f"TT UNDER {abbr} ({ttl})", odds=uo)
                if e: edges.append(e)

        src = ev if ev else game

        # F5 TOTAL — Normal
        f5t = best_book_odds(src, "totals_1st_5_innings")
        if f5t:
            outs = f5t["outcomes"]
            ov = next((o for o in outs if o["name"].lower()=="over"), None)
            un = next((o for o in outs if o["name"].lower()=="under"), None)
            if ov and un:
                f5line = ov.get("point", 0)
                pov_nv, pun_nv = novigp(american_to_prob(ov["price"]), american_to_prob(un["price"]))
                f5proj = total_proj * F5_SCALAR
                mov = 1.0 - normal_cdf(f5line, f5proj, F5_SIGMA["total"])
                e = edge_str(mov,     pov_nv, f"F5 TOTAL OVER  ({f5line})", odds=ov["price"])
                if e: edges.append(e)
                e = edge_str(1.0-mov, pun_nv, f"F5 TOTAL UNDER ({f5line})", odds=un["price"])
                if e: edges.append(e)

        # F5 ML — Normal
        f5ml = best_book_odds(src, "h2h_1st_5_innings")
        if f5ml:
            outs = f5ml["outcomes"]
            oa = find_outcome(outs, MLB_NAME_MAP, away_abbr)
            oh = find_outcome(outs, MLB_NAME_MAP, home_abbr)
            if oa and oh:
                pa_nv, ph_nv = novigp(american_to_prob(oa["price"]), american_to_prob(oh["price"]))
                f5m = (home_proj - away_proj) * F5_SCALAR
                mh = 1.0 - normal_cdf(0, f5m, F5_SIGMA["spread"])
                e = edge_str(mh,     ph_nv, f"F5 ML HOME  {home_abbr}", odds=oh["price"])
                if e: edges.append(e)
                e = edge_str(1.0-mh, pa_nv, f"F5 ML AWAY  {away_abbr}", odds=oa["price"])
                if e: edges.append(e)

        # F5 SPREAD — Normal
        f5sp = best_book_odds(src, "spreads_1st_5_innings")
        if f5sp:
            outs = f5sp["outcomes"]
            oa = find_outcome(outs, MLB_NAME_MAP, away_abbr)
            oh = find_outcome(outs, MLB_NAME_MAP, home_abbr)
            if oa and oh:
                sp_line = oh.get("point", 0)
                ph_nv, pa_nv = novigp(american_to_prob(oh["price"]), american_to_prob(oa["price"]))
                f5m = (home_proj - away_proj) * F5_SCALAR
                cover_h = 1.0 - normal_cdf(-sp_line, f5m, F5_SIGMA["spread"])
                e = edge_str(cover_h,       ph_nv, f"F5 SPREAD HOME {home_abbr} ({sp_line:+.1f})", odds=oh["price"])
                if e: edges.append(e)
                e = edge_str(1.0-cover_h,   pa_nv, f"F5 SPREAD AWAY {away_abbr} ({-sp_line:+.1f})", odds=oa["price"])
                if e: edges.append(e)

        hdr = f"{away_abbr} ({away_proj}) @ {home_abbr} ({home_proj})  proj_total={total_proj:.1f}  margin={margin:+.1f}"
        if edges:
            print(f"\n{hdr}")
            for e in edges:
                print(e)
        else:
            print(f"\n{hdr}  -- no edge >= 2%")

    print(f"\n  Matched {matched}/{len(MLB_PROJS)} games from API")

# ── NBA analysis ────────────────────────────────────────────────────────────
def analyze_nba(games_data):
    print("\n" + "="*72)
    print("NBA GAME LINES  (Normal distribution, all markets)")
    print("="*72)

    sig = SIGMA["NBA"]
    proj_map = {(a, h): (ap, hp) for a, ap, h, hp in NBA_PROJS}
    matched = 0

    for game in games_data:
        away_name = game.get("away_team", "").lower()
        home_name = game.get("home_team", "").lower()
        away_abbr = NBA_NAME_MAP.get(away_name)
        home_abbr = NBA_NAME_MAP.get(home_name)
        if not away_abbr or not home_abbr:
            continue
        if (away_abbr, home_abbr) not in proj_map:
            if (home_abbr, away_abbr) in proj_map:
                away_abbr, home_abbr = home_abbr, away_abbr
            else:
                continue

        matched += 1
        away_proj, home_proj = proj_map[(away_abbr, home_abbr)]
        total_proj = away_proj + home_proj
        margin = home_proj - away_proj

        edges = []

        # MONEYLINE
        ml = best_book_odds(game, "h2h")
        if ml:
            outs = ml["outcomes"]
            oa = find_outcome(outs, NBA_NAME_MAP, away_abbr)
            oh = find_outcome(outs, NBA_NAME_MAP, home_abbr)
            if oa and oh:
                pa_nv, ph_nv = novigp(american_to_prob(oa["price"]), american_to_prob(oh["price"]))
                mh = 1.0 - normal_cdf(0, margin, sig["ml"])
                ma = 1.0 - mh
                e = edge_str(mh, ph_nv, f"ML HOME  {home_abbr}", odds=oh["price"])
                if e: edges.append(e)
                e = edge_str(ma, pa_nv, f"ML AWAY  {away_abbr}", odds=oa["price"])
                if e: edges.append(e)

        # SPREAD
        sp = best_book_odds(game, "spreads")
        if sp:
            outs = sp["outcomes"]
            oa = find_outcome(outs, NBA_NAME_MAP, away_abbr)
            oh = find_outcome(outs, NBA_NAME_MAP, home_abbr)
            if oa and oh:
                sp_line = oh.get("point", 0)
                ph_nv, pa_nv = novigp(american_to_prob(oh["price"]), american_to_prob(oa["price"]))
                cover_h = 1.0 - normal_cdf(-sp_line, margin, sig["spread"])
                e = edge_str(cover_h,       ph_nv, f"SPREAD HOME {home_abbr} ({sp_line:+.1f})", odds=oh["price"])
                if e: edges.append(e)
                e = edge_str(1.0-cover_h,   pa_nv, f"SPREAD AWAY {away_abbr} ({-sp_line:+.1f})", odds=oa["price"])
                if e: edges.append(e)

        # GAME TOTAL
        tot = best_book_odds(game, "totals")
        if tot:
            outs = tot["outcomes"]
            ov = next((o for o in outs if o["name"].lower()=="over"), None)
            un = next((o for o in outs if o["name"].lower()=="under"), None)
            if ov and un:
                tline = ov.get("point", 0)
                pov_nv, pun_nv = novigp(american_to_prob(ov["price"]), american_to_prob(un["price"]))
                mov = 1.0 - normal_cdf(tline, total_proj, sig["total"])
                e = edge_str(mov,     pov_nv, f"TOTAL OVER  ({tline})", odds=ov["price"])
                if e: edges.append(e)
                e = edge_str(1.0-mov, pun_nv, f"TOTAL UNDER ({tline})", odds=un["price"])
                if e: edges.append(e)

        # TEAM TOTALS (event-specific endpoint)
        eid = game.get("id")
        ev = None
        if eid:
            ev = fetch_event_odds("basketball_nba", eid, "team_totals")

        if ev:
            tt = team_total_odds(ev, [away_abbr, home_abbr])
            for abbr, proj in [(away_abbr, away_proj), (home_abbr, home_proj)]:
                info = tt.get(abbr, {})
                ttl = info.get("line")
                oo  = info.get("over_odds")
                uo  = info.get("under_odds")
                if not ttl or oo is None or uo is None:
                    continue
                pov_nv, pun_nv = novigp(american_to_prob(oo), american_to_prob(uo))
                mov = 1.0 - normal_cdf(ttl, proj, sig["team"])
                e = edge_str(mov,     pov_nv, f"TT OVER  {abbr} ({ttl})", odds=oo)
                if e: edges.append(e)
                e = edge_str(1.0-mov, pun_nv, f"TT UNDER {abbr} ({ttl})", odds=uo)
                if e: edges.append(e)

        hdr = f"{away_abbr} ({away_proj}) @ {home_abbr} ({home_proj})  proj_total={total_proj:.1f}  margin={margin:+.1f}"
        if edges:
            print(f"\n{hdr}")
            for e in edges:
                print(e)
        else:
            print(f"\n{hdr}  -- no edge >= 2%")

    print(f"\n  Matched {matched}/{len(NBA_PROJS)} games from API")

# ── Main ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")

    print("Fetching MLB base odds (h2h, spreads, totals)...")
    mlb_data = fetch_odds("baseball_mlb", "h2h,spreads,totals")
    print(f"  {len(mlb_data)} MLB games")

    print("Fetching NBA base odds (h2h, spreads, totals)...")
    nba_data = fetch_odds("basketball_nba", "h2h,spreads,totals")
    print(f"  {len(nba_data)} NBA games")

    analyze_mlb(mlb_data)
    analyze_nba(nba_data)

    print("\n\nLegend: '*** EDGE' >= 4%  |  '  + edge' = 2-4%  |  edge = model_prob - market_no_vig_prob")
    print("Distributions:")
    print("  MLB  : ML = NB direct sum (r=3.548) | team totals = NB | total/spread/F5 = Normal")
    print("  NBA  : all markets = Normal")
    print("  NHL  : all markets = Normal (sigma: total=2.311, spread=2.614, team=1.744, ml=2.614)")
    print("MLB sigmas: total=4.0/spread=3.8  F5: total=2.65/spread=2.70  F5 scalar=0.540")
