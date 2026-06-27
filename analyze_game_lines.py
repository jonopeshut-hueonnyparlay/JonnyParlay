"""
Standalone game-line edge analyzer.

Distributions:
  MLB team totals : Negative Binomial (var/mu~2.26; NB r=3.548)
  MLB moneyline   : NB direct probability sum (home wins)
  All other markets: Normal (same GAME_SIGMA values as run_picks.py)
"""
import csv, datetime, math, os, requests, sys
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

try:
    from filelock import FileLock as _FileLock
    _HAVE_FILELOCK = True
except ImportError:
    _HAVE_FILELOCK = False

_ENGINE_DIR = Path(__file__).parent / "engine"
if str(_ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(_ENGINE_DIR))
try:
    from pick_log_schema import CANONICAL_HEADER as _CANONICAL_HEADER
    from paths import PICK_LOG_GAME_LINES_PATH as _PICK_LOG_GL_PATH
    _HAVE_SCHEMA = True
except ImportError:
    _HAVE_SCHEMA = False
    _CANONICAL_HEADER = []
    _PICK_LOG_GL_PATH = Path(__file__).parent / "data" / "pick_log_game_lines.csv"

try:
    from team_resolve import resolve_team_abbrev
except ImportError:
    def resolve_team_abbrev(name):   # graceful fallback if engine import unavailable
        return ""

# Distribution primitives are the canonical engine/quant implementations (the
# same math engine/evaluators.py prices with). Previously duplicated verbatim in
# this file; consolidated 2026-06-26 (Stage 1 game-line pricer collapse). The
# byte-identity of the dedup is pinned by
# tests/test_game_line_canonical_primitives.py.
from quant.distributions import normal_cdf, negbinom_pmf, negbinom_cdf
from quant.derived import mlb_ml_from_nb

try:                                  # source the key from secrets, never hardcode
    from secrets_config import ODDS_API_KEY as API_KEY   # engine/ is on sys.path (above)
except ImportError:
    API_KEY = os.getenv("ODDS_API_KEY", "")
BASE      = "https://api.the-odds-api.com/v4/sports"
REGIONS   = "us,us2,us_ex"
BOOKS_STR = "draftkings,fanduel,betmgm,caesars,pointsbetus"
HEADERS   = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# â”€â”€ Distributions â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# (normal_cdf / negbinom_pmf / negbinom_cdf / mlb_ml_from_nb now imported from
#  quant.distributions + quant.derived — see the import block above.)

# â”€â”€ Sigmas (mirrored from GAME_SIGMA + F5_SIGMA in run_picks.py) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# NHL calibrated 2026-06-05 from 3936 games. MLB team total uses NB (not sigma).
SIGMA = {
    "MLB":  {"total": 4.6,  "spread": 4.2,  "team": 3.0,  "ml": 4.2},   # ml=spread, matches canonical GAME_SIGMA['MLB'] (was 4.75) [audit 2026-06]
    # NBA calibrated 2026-06-05 (Plan 6 Â§6, 3,922 games): residual-basis SDs
    # (raw total SD=20.20, residual=19.33; margin residual=15.27; rho=+0.227).
    "NBA":  {"total": 18.5, "spread": 12.5, "team": 11.0, "ml": 12.5},
    "NHL":  {"total": 2.311, "spread": 2.614, "team": 1.744, "ml": 2.614},
}
F5_SIGMA  = {"total": 2.65, "spread": 2.70, "team": 2.10}
F5_SCALAR = 0.540

# NB dispersion for MLB team run-scoring (calibrated 2026-06-05, n=8095 regular-season games)
MLB_TEAM_RUN_R = 3.548

# Team-specific sigma JSONs (mirrored from run_picks.py) â€” loaded at startup
_TEAM_SIGMAS_AGL: dict = {}
_TEAM_SIGMAS_MEANSQ_AGL: dict = {}

def _load_team_sigmas_agl():
    import json as _json
    from market_config import wnba_sigmas_by_abbrev
    _data_dir = Path(__file__).parent / "data"
    for sport, fname in [("NHL", "team_sigmas_nhl.json"), ("MLB", "team_sigmas_mlb.json"),
                         ("NBA", "team_sigmas_nba.json"), ("WNBA", "team_sigmas_wnba.json")]:
        p = _data_dir / fname
        if p.exists():
            data = _json.loads(p.read_text())
            # P0.2: WNBA JSON is keyed by numeric team_id; re-key to abbrev (mirrors
            # calibrated._load_team_sigmas) so abbrev lookups hit, not league σ.
            if sport == "WNBA":
                data = wnba_sigmas_by_abbrev(data)
            _TEAM_SIGMAS_AGL[sport] = data
            sq = [t["score_sigma"] ** 2 for t in data.values()
                  if isinstance(t, dict) and t.get("score_sigma") and t.get("n_games", 0) >= 20]
            _TEAM_SIGMAS_MEANSQ_AGL[sport] = (sum(sq) / len(sq)) if sq else 0.0

_load_team_sigmas_agl()

def get_game_sigma(sport, home_abbr, away_abbr, market):
    """Return matchup-specific sigma; falls back to SIGMA league average.

    Plan 6 Â§6 (2026-06-05): relative-variability scaler on the per-market league
    sigma â€” sigma_league(market) * sqrt((ÏƒhÂ²+ÏƒaÂ²)/(2Â·ÏƒÌ„Â²)) â€” mirrors run_picks.py.
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
    """Return sigma for one team's scoring â€” used for team total picks."""
    league = SIGMA.get(sport, SIGMA["NBA"])
    league_sigma = league.get("team", 10.0)
    t = _TEAM_SIGMAS_AGL.get(sport, {}).get((team_abbr or "").upper())
    return t["score_sigma"] if t and t.get("n_games", 0) >= 20 else league_sigma

def get_mlb_team_run_r(team_abbr):
    """Return per-team NB dispersion r for MLB run-scoring; falls back to MLB_TEAM_RUN_R."""
    return _TEAM_SIGMAS_AGL.get("MLB", {}).get((team_abbr or "").upper(), {}).get("nb_r", MLB_TEAM_RUN_R)

# â”€â”€ Projections (away_abbr, away_proj, home_abbr, home_proj) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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

# â”€â”€ Team name to abbreviation â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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

# â”€â”€ API helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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

# â”€â”€ Odds math â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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
                # Resolve the outcome's full team name to an abbrev instead of a
                # substring test (abbr is rarely a literal substring of the name —
                # failed for ~half of teams). [audit 2026-06]
                abbr = resolve_team_abbrev(out.get("description", ""))
                if abbr not in abbr_list:
                    continue
                side = out["name"].lower()
                if abbr not in result:
                    result[abbr] = {"book": bm["title"], "line": out.get("point")}
                # Keep the best (highest) price per side across books, not last-seen.
                _cur = result[abbr].get(f"{side}_odds")
                if _cur is None or out["price"] > _cur:
                    result[abbr][f"{side}_odds"] = out["price"]
                if out.get("point"):
                    result[abbr]["line"] = out["point"]
    return result

# â”€â”€ Edge formatting â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def edge_str(model_p, market_p, label, line=None, odds=None, min_stake=0.25, game_label="", book=""):
    edge = model_p - market_p
    # Only show positive edges >= 4%
    if edge < 0.04:
        return None
    marker = "ðŸ”¥ STRONG" if edge >= 0.08 else "*** BET  "
    stake = kelly_stake(model_p, odds) if odds is not None else min_stake
    parts = [f"  {marker}  {label:<32}"]
    if line is not None:
        parts.append(f" line={line}")
    if odds is not None:
        parts.append(f" odds={odds:+d}" if isinstance(odds, int) else f" odds={odds}")
    parts.append(f"  {stake:.2f}u  model={model_p:.3f}  mktNV={market_p:.3f}  edge={edge:+.3f}")
    # Collect for ranked summary table
    ALL_BETS.append({
        "game":   game_label,
        "label":  label.strip(),
        "stake":  stake,
        "model":  model_p,
        "odds":   odds,
        "edge":   edge,
        "book":   book,
        "line":   line,
    })
    return "".join(parts)


GAME_LINE_KELLY_FRACTION = 10.0  # Bigger than props (6.0) to produce usable stakes
                                  # on game lines where WP clusters near 50-55%
GAME_LINE_MARKET_MULT    = 0.75   # Game lines less reliable than props â€” mirrors run_picks DEFAULT_MARKET_MULT

def kelly_stake(model_p, odds_american, min_stake=0.25, max_stake=2.0):
    """Kelly stake sizing for game lines.
    Formula: f* = (b*p - q) / b  then  units = f* * KELLY_FRACTION * MARKET_MULT
    Matches run_picks.py convention: units = f_star * fraction (no Ã—100).
    Uses GAME_LINE_KELLY_FRACTION=10.0 (bigger than props\'s 6.0) to produce
    usable stakes at typical 50-55% game-line win probabilities.
    """
    if odds_american >= 0:
        b = odds_american / 100.0
    else:
        b = 100.0 / abs(odds_american)
    q = 1.0 - model_p
    f_star = (b * model_p - q) / b
    if f_star <= 0:
        return 0.0
    raw = f_star * GAME_LINE_KELLY_FRACTION * GAME_LINE_MARKET_MULT
    rounded = round(raw * 4) / 4
    return max(min_stake, min(max_stake, rounded))

# Shared bet collector â€” populated by edge_str, printed as ranked table at end
ALL_BETS = []

def find_outcome(outcomes, name_map, abbr):
    for o in outcomes:
        if name_map.get(o["name"].lower()) == abbr:
            return o
        if abbr in o["name"].upper():
            return o
    return None

# â”€â”€ MLB team total NB probability â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# MLB team-total NB pricing now lives in the canonical engine
# (game_line_pricing.team_total_mlb_nb) — see the call site in analyze_mlb.
from game_line_pricing import team_total_mlb_nb

# â”€â”€ MLB analysis â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def analyze_mlb(games_data, team_projs=None, ctx_verdicts=None):
    print("\n" + "="*72)
    print("MLB GAME LINES")
    print("  Spread/total: Normal  |  Team totals: NB(r=3.548)  |  ML: NB direct sum")
    print("="*72)

    sig = SIGMA["MLB"]
    # Use CSV-derived projections if available, else fall back to hardcoded
    if team_projs:
        proj_map = {}
        for g in games_data:
            a = MLB_NAME_MAP.get(g.get("away_team","").lower())
            h = MLB_NAME_MAP.get(g.get("home_team","").lower())
            if a and h and a.upper() in team_projs and h.upper() in team_projs:
                proj_map[(a,h)] = (team_projs[a.upper()], team_projs[h.upper()])
    else:
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

        # MONEYLINE â€” NB direct sum
        ml = best_book_odds(game, "h2h")
        if ml:
            outs = ml["outcomes"]
            oa = find_outcome(outs, MLB_NAME_MAP, away_abbr)
            oh = find_outcome(outs, MLB_NAME_MAP, home_abbr)
            if oa and oh:
                pa_nv, ph_nv = novigp(american_to_prob(oa["price"]), american_to_prob(oh["price"]))
                mh = mlb_ml_from_nb(home_proj, away_proj, MLB_TEAM_RUN_R)
                ma = 1.0 - mh
                e = edge_str(mh, ph_nv, f"ML HOME  {home_abbr}", odds=oh["price"], book=ml["book"])
                if e: edges.append(e)
                e = edge_str(ma, pa_nv, f"ML AWAY  {away_abbr}", odds=oa["price"], book=ml["book"])
                if e: edges.append(e)

        # RUN LINE (spread) â€” Normal
        sp = best_book_odds(game, "spreads")
        if sp:
            outs = sp["outcomes"]
            oa = find_outcome(outs, MLB_NAME_MAP, away_abbr)
            oh = find_outcome(outs, MLB_NAME_MAP, home_abbr)
            if oa and oh:
                sp_line = oh.get("point", 0)
                ph_nv, pa_nv = novigp(american_to_prob(oh["price"]), american_to_prob(oa["price"]))
                cover_h = 1.0 - normal_cdf(-sp_line, margin, sig["spread"])
                e = edge_str(cover_h,       ph_nv, f"SPREAD HOME {home_abbr} ({sp_line:+.1f})", odds=oh["price"], book=sp["book"])
                if e: edges.append(e)
                e = edge_str(1.0-cover_h,   pa_nv, f"SPREAD AWAY {away_abbr} ({-sp_line:+.1f})", odds=oa["price"], book=sp["book"])
                if e: edges.append(e)

        # GAME TOTAL â€” Normal
        tot = best_book_odds(game, "totals")
        if tot:
            outs = tot["outcomes"]
            ov = next((o for o in outs if o["name"].lower()=="over"), None)
            un = next((o for o in outs if o["name"].lower()=="under"), None)
            if ov and un:
                tline = ov.get("point", 0)
                pov_nv, pun_nv = novigp(american_to_prob(ov["price"]), american_to_prob(un["price"]))
                mov = 1.0 - normal_cdf(tline, total_proj, sig["total"])
                e = edge_str(mov,      pov_nv, f"TOTAL OVER  ({tline})", odds=ov["price"], book=tot["book"])
                if e: edges.append(e)
                e = edge_str(1.0-mov,  pun_nv, f"TOTAL UNDER ({tline})", odds=un["price"], book=tot["book"])
                if e: edges.append(e)

        # EVENT-SPECIFIC: team_totals + F5
        eid = game.get("id")
        ev = None
        if eid:
            ev = fetch_event_odds("baseball_mlb", eid,
                "team_totals,h2h_1st_5_innings,spreads_1st_5_innings,totals_1st_5_innings")

        # TEAM TOTALS â€” NB
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
                mov, mun = team_total_mlb_nb(proj, ttl, MLB_TEAM_RUN_R)
                e = edge_str(mov, pov_nv, f"TT OVER  {abbr} ({ttl})", odds=oo, book=info.get("book",""))
                if e: edges.append(e)
                e = edge_str(mun, pun_nv, f"TT UNDER {abbr} ({ttl})", odds=uo, book=info.get("book",""))
                if e: edges.append(e)

        src = ev if ev else game

        # F5 TOTAL â€” Normal
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
                e = edge_str(mov,     pov_nv, f"F5 TOTAL OVER  ({f5line})", odds=ov["price"], book=f5t["book"])
                if e: edges.append(e)
                e = edge_str(1.0-mov, pun_nv, f"F5 TOTAL UNDER ({f5line})", odds=un["price"], book=f5t["book"])
                if e: edges.append(e)

        # F5 ML â€” Normal
        f5ml = best_book_odds(src, "h2h_1st_5_innings")
        if f5ml:
            outs = f5ml["outcomes"]
            oa = find_outcome(outs, MLB_NAME_MAP, away_abbr)
            oh = find_outcome(outs, MLB_NAME_MAP, home_abbr)
            if oa and oh:
                pa_nv, ph_nv = novigp(american_to_prob(oa["price"]), american_to_prob(oh["price"]))
                f5m = (home_proj - away_proj) * F5_SCALAR
                mh = 1.0 - normal_cdf(0, f5m, F5_SIGMA["spread"])
                e = edge_str(mh,     ph_nv, f"F5 ML HOME  {home_abbr}", odds=oh["price"], book=f5ml["book"])
                if e: edges.append(e)
                e = edge_str(1.0-mh, pa_nv, f"F5 ML AWAY  {away_abbr}", odds=oa["price"], book=f5ml["book"])
                if e: edges.append(e)

        # F5 SPREAD â€” Normal
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
                e = edge_str(cover_h,       ph_nv, f"F5 SPREAD HOME {home_abbr} ({sp_line:+.1f})", odds=oh["price"], book=f5sp["book"])
                if e: edges.append(e)
                e = edge_str(1.0-cover_h,   pa_nv, f"F5 SPREAD AWAY {away_abbr} ({-sp_line:+.1f})", odds=oa["price"], book=f5sp["book"])
                if e: edges.append(e)

        _ctx_tag = ""
        _ctx_token = ""
        if ctx_verdicts:
            _al = (game.get("away_team","") or "").lower()
            _hl = (game.get("home_team","") or "").lower()
            for _k, _v in ctx_verdicts.items():
                if (_al and _al in _k) or (_hl and _hl in _k):
                    _vrd  = _v.get("verdict","neutral")
                    _conf = int(_v.get("confidence",0)*100)
                    _ctx_tag = f"  [CTX+ {_vrd} {_conf}%]" if _vrd=="confirms" else                                f"  [CTX- {_vrd} {_conf}%]" if _vrd=="fades" else                                f"  [CTX? {_conf}%]"
                    _ctx_token = "confirms" if _vrd=="confirms" else "fades" if _vrd=="fades" else "neutral"
                    break
        hdr = f"{away_abbr} ({away_proj}) @ {home_abbr} ({home_proj})  proj_total={total_proj:.1f}  margin={margin:+.1f}{_ctx_tag}"
        if edges:
            print(f"\n{hdr}")
            for e in edges:
                print(e)
        else:
            print(f"\n{hdr}  -- no edge >= 4%")
        # Tag collected bets with this game's label
        _game_short = f"{away_abbr}@{home_abbr}"
        for b in ALL_BETS:
            if b["game"] == "":
                b["game"]      = _game_short
                b["ctx"]       = _ctx_token
                b["away_abbr"] = away_abbr
                b["home_abbr"] = home_abbr
                b["sport"]     = "MLB"

    print(f"\n  Matched {matched}/{len(proj_map)} games from API")

# â”€â”€ NBA analysis â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def analyze_nba(games_data, team_projs=None, ctx_verdicts=None):
    print("\n" + "="*72)
    print("NBA GAME LINES  (Normal distribution, all markets)")
    print("="*72)

    sig = SIGMA["NBA"]
    # Use CSV-derived projections if available, else fall back to hardcoded
    if team_projs:
        proj_map = {}
        for g in games_data:
            a = NBA_NAME_MAP.get((g.get("away_team","") or "").lower())
            h = NBA_NAME_MAP.get((g.get("home_team","") or "").lower())
            if a and h and a in team_projs and h in team_projs:
                proj_map[(a, h)] = (team_projs[a], team_projs[h])
        for fa, ap, fh, hp in NBA_PROJS:
            if (fa, fh) not in proj_map:
                proj_map[(fa, fh)] = (ap, hp)
    else:
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
                e = edge_str(mh, ph_nv, f"ML HOME  {home_abbr}", odds=oh["price"], book=ml["book"])
                if e: edges.append(e)
                e = edge_str(ma, pa_nv, f"ML AWAY  {away_abbr}", odds=oa["price"], book=ml["book"])
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
                e = edge_str(cover_h,       ph_nv, f"SPREAD HOME {home_abbr} ({sp_line:+.1f})", odds=oh["price"], book=sp["book"])
                if e: edges.append(e)
                e = edge_str(1.0-cover_h,   pa_nv, f"SPREAD AWAY {away_abbr} ({-sp_line:+.1f})", odds=oa["price"], book=sp["book"])
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
                e = edge_str(mov,     pov_nv, f"TOTAL OVER  ({tline})", odds=ov["price"], book=tot["book"])
                if e: edges.append(e)
                e = edge_str(1.0-mov, pun_nv, f"TOTAL UNDER ({tline})", odds=un["price"], book=tot["book"])
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
                e = edge_str(mov,     pov_nv, f"TT OVER  {abbr} ({ttl})", odds=oo, book=info.get("book",""))
                if e: edges.append(e)
                e = edge_str(1.0-mov, pun_nv, f"TT UNDER {abbr} ({ttl})", odds=uo, book=info.get("book",""))
                if e: edges.append(e)

        _ctx_tag = ""
        _ctx_token = ""
        if ctx_verdicts:
            _al = (game.get("away_team","") or "").lower()
            _hl = (game.get("home_team","") or "").lower()
            for _k, _v in ctx_verdicts.items():
                if (_al and _al in _k) or (_hl and _hl in _k):
                    _vrd  = _v.get("verdict","neutral")
                    _conf = int(_v.get("confidence",0)*100)
                    _ctx_tag = f"  [CTX+ {_vrd} {_conf}%]" if _vrd=="confirms" else                                f"  [CTX- {_vrd} {_conf}%]" if _vrd=="fades" else                                f"  [CTX? {_conf}%]"
                    _ctx_token = "confirms" if _vrd=="confirms" else "fades" if _vrd=="fades" else "neutral"
                    break
        hdr = f"{away_abbr} ({away_proj}) @ {home_abbr} ({home_proj})  proj_total={total_proj:.1f}  margin={margin:+.1f}{_ctx_tag}"
        if edges:
            print(f"\n{hdr}")
            for e in edges:
                print(e)
        else:
            print(f"\n{hdr}  -- no edge >= 4%")
        # Tag collected bets with this game's label
        _game_short = f"{away_abbr}@{home_abbr}"
        for b in ALL_BETS:
            if b["game"] == "":
                b["game"]      = _game_short
                b["ctx"]       = _ctx_token
                b["away_abbr"] = away_abbr
                b["home_abbr"] = home_abbr
                b["sport"]     = "NBA"

    print(f"\n  Matched {matched}/{len(proj_map)} games from API")

# â”€â”€ Main â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def _load_team_projs_from_csv(csv_path):
    """Parse SaberSim CSV and extract team-level projections from Saber Team column."""
    import csv as _csv
    team_projs = {}
    try:
        with open(csv_path, "r", encoding="utf-8-sig") as f:
            for row in _csv.DictReader(f):
                clean = {k.strip(): v.strip() for k, v in row.items()}
                team = clean.get("Team", clean.get("team", "")).strip()
                saber_team = clean.get("Saber Team", clean.get("saber team", ""))
                try:
                    val = float(saber_team or 0)
                    if team and val > 0:
                        team_projs[team.upper()] = val
                except (ValueError, TypeError):
                    pass
    except OSError:
        pass
    return team_projs


def _auto_find_csv(sport_key):
    """Auto-find latest SaberSim CSV matching sport_key in Downloads."""
    import time as _time
    import re as _re
    downloads = Path.home() / "Downloads"
    now = _time.time()
    matches = sorted(
        [f for f in downloads.glob("*.csv")
         if _re.search(r"(?<![a-z])" + _re.escape(sport_key) + r"(?![a-z])", f.name.lower())
         and (now - f.stat().st_mtime) < 43200],
        key=lambda f: f.stat().st_mtime, reverse=True
    )
    return matches[0] if matches else None


def _build_projs(sport):
    """Build game projection list from SaberSim CSV, falling back to hardcoded list."""
    csv_file = _auto_find_csv(sport.lower())
    if csv_file:
        projs = _load_team_projs_from_csv(csv_file)
        if projs:
            print(f"  [auto] Loaded {sport} team projections from {csv_file.name} ({len(projs)} teams)")
            # Return as list of (away, away_proj, home, home_proj) â€” will be matched against API games
            return projs  # dict format: {team_abbr: proj}
    return {}



def print_ranked_table(bets):
    """Print all qualifying bets ranked by edge as ASCII table."""
    if not bets:
        return
    bets_sorted = sorted(bets, key=lambda b: b["edge"], reverse=True)

    def p2a(p):
        if p <= 0 or p >= 1: return "N/A"
        return f"-{round(p/(1-p)*100)}" if p >= 0.5 else f"+{round((1-p)/p*100)}"

    show_ctx = any(b.get("ctx") for b in bets_sorted)

    rows = []
    for i, b in enumerate(bets_sorted):
        pick = f"{b['game']} {b['label']}"[:32]
        mkt  = f"{b['odds']:+d}" if isinstance(b['odds'], int) else "N/A"
        cells = [str(i + 1), pick, f"{b['stake']:.2f}u", f"{b['model']*100:.1f}%",
                 p2a(b["model"]), mkt, b.get("book","") or "-", f"+{b['edge']*100:.1f}pp"]
        if show_ctx:
            cells.append(b.get("ctx","") or "-")
        rows.append(tuple(cells))

    hdrs   = ["#", "Pick", "Size", "Fair%", "Fair Odds", "Mkt Odds", "Book", "Edge"]
    if show_ctx:
        hdrs.append("CTX")
    widths = [max(len(h), max(len(r[i]) for r in rows)) for i, h in enumerate(hdrs)]
    div    = "+" + "+".join("-" * (w+2) for w in widths) + "+"
    row_s  = lambda cells: "|" + "|".join(f" {c:<{widths[i]}} " for i,c in enumerate(cells)) + "|"

    print()
    print("=" * 72)
    print("QUALIFYING BETS  (ranked by edge)")
    print("=" * 72)
    print(div)
    print(row_s(hdrs))
    for r in rows:
        print(div)
        print(row_s(r))
    print(div)
    total = sum(b['stake'] for b in bets_sorted)
    print(f"  {len(bets_sorted)} bet(s)  |  total: {total:.2f}u")
    if total > 8.0:
        print(f"  ⚠ TOTAL EXPOSURE {total:.1f}u EXCEEDS MLB DAILY CAP (8.0u)")
    return bets_sorted




def _line_from_label(label):
    """Extract the signed line embedded in an edge_str label.

    The point spread / total is rendered in parentheses at the end of the
    label, e.g. 'SPREAD HOME ATH (-1.5)' -> '-1.5', 'TOTAL OVER  (8.5)' -> '8.5',
    'TT OVER  COL (4.5)' -> '4.5'. Moneyline labels carry no parenthesised
    number ('ML HOME  ATH') and return '' — those stats have no line.

    This is the structured source for the CSV `line` column: the per-market
    edge_str() callers don't pass line=, so without this the column was written
    empty and grade_game_line() bailed at float('').
    """
    import re
    m = re.search(r"\(([+-]?\d+(?:\.\d+)?)\)", label or "")
    return m.group(1) if m else ""


def _parse_label_meta(label):
    """Return (stat, direction) from edge_str label string."""
    s = label.strip().upper()
    if s.startswith("F5 TOTAL"):  return "F5_TOTAL",   "over" if "OVER" in s else "under"
    if s.startswith("F5 ML"):     return "F5_ML",      "home" if "HOME" in s else "away"
    if s.startswith("F5 SPREAD"): return "F5_SPREAD",  "home" if "HOME" in s else "away"
    if s.startswith("TT"):        return "TEAM_TOTAL",  "over" if "OVER" in s else "under"
    if s.startswith("ML"):        return "ML",          "home" if "HOME" in s else "away"
    if s.startswith("SPREAD"):    return "SPREAD",      "home" if "HOME" in s else "away"
    if s.startswith("TOTAL"):     return "TOTAL",       "over" if "OVER" in s else "under"
    return "TOTAL", "over"


@contextmanager
def _gl_lock(log_path):
    if _HAVE_FILELOCK:
        with _FileLock(str(log_path) + ".lock", timeout=30):
            yield
    else:
        yield


def _write_game_line_bets(bets, log_path):
    """Write selected bets to pick_log_game_lines.csv using the 29-col schema."""
    if not _HAVE_SCHEMA or not _CANONICAL_HEADER:
        print("  [warn] pick_log_schema not available -- skipping log.")
        return 0
    log_path = Path(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not log_path.exists() or log_path.stat().st_size == 0
    today = datetime.today().isoformat()[:10]
    now   = datetime.now().strftime("%H:%M:%S")
    with _gl_lock(log_path):
        with open(log_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=_CANONICAL_HEADER,
                                    extrasaction="ignore", restval="")
            if write_header:
                writer.writeheader()
            for b in bets:
                stat, direction = _parse_label_meta(b.get("label", ""))
                game_tag  = b.get("game", "")
                away_abbr = b.get("away_abbr", game_tag.split("@")[0] if "@" in game_tag else "")
                home_abbr = b.get("home_abbr", game_tag.split("@")[1] if "@" in game_tag else "")
                model_p   = b["model"]
                edge      = b["edge"]
                # The edge_str() callers don't pass line=, so b["line"] is None for
                # every game-line bet — recover it from the label text instead. ML
                # markets legitimately have no line and stay blank.
                line_val  = b.get("line")
                if line_val is None or line_val == "":
                    line_val = _line_from_label(b.get("label", ""))
                row = {
                    "date":            today,
                    "run_time":        now,
                    "run_type":        "game_line",
                    "sport":           b.get("sport", ""),
                    "player":          game_tag,
                    "team":            home_abbr,
                    "stat":            stat,
                    "line":            line_val,
                    "direction":       direction,
                    "proj":            f"{model_p:.4f}",
                    "win_prob":        f"{model_p:.4f}",
                    "edge":            f"{edge:.4f}",
                    "odds":            b.get("odds", ""),
                    "book":            b.get("book", ""),
                    "tier":            "T2",
                    "pick_score":      round(edge * 1000),
                    "size":            f"{b["stake"]:.2f}",
                    "game":            game_tag,
                    "mode":            "Default",
                    "result":          "",
                    "closing_odds":    "",
                    "clv":             "",
                    "card_slot":       "GL",
                    "is_home":         1 if direction == "home" else 0,
                    "context_verdict": b.get("ctx", ""),
                    "context_reason":  "",
                    "context_score":   "",
                    "legs":            1,
                    "over_p_raw":      f"{model_p:.4f}",
                }
                writer.writerow(row)
            f.flush()
            os.fsync(f.fileno())
    return len(bets)


def _post_game_lines_discord(bets):
    """Post logged game-line bets to Discord. Prints card to console if webhook not configured."""
    webhook = os.getenv("DISCORD_GAME_LINES_WEBHOOK", "")
    today   = datetime.today().strftime("%b %d, %Y")

    def _p2a(p):
        if p <= 0 or p >= 1:
            return "N/A"
        return f"-{round(p / (1 - p) * 100)}" if p >= 0.5 else f"+{round((1 - p) / p * 100)}"

    _SPORT_EMOJI = {"MLB": "⚾", "NBA": "🏀", "NHL": "🏒"}
    SEP = "━" * 23

    sports = {b.get("sport", "") for b in bets}
    header_emoji = _SPORT_EMOJI.get(next(iter(sports)), "⚡") if len(sports) == 1 else "⚡"

    lines = [f"{header_emoji} GAME LINES — {today}", SEP]
    total = 0.0
    for b in bets:
        sport  = b.get("sport", "")
        game   = b.get("game", "")
        label  = b.get("label", "")
        model  = b["model"]
        edge   = b["edge"]
        stake  = b["stake"]
        odds   = b.get("odds", "N/A")
        book   = b.get("book", "-")
        ctx    = b.get("ctx", "") or "—"
        total += stake

        odds_str = f"{odds:+d}" if isinstance(odds, int) else str(odds)
        lines.append(f"{sport} | {game} — {label}")
        lines.append(f"📋 Book: {book} | Odds: {odds_str} | {stake:.2f}u")
        lines.append(f"⚡ Edge: +{edge * 100:.1f}pp | Fair: {_p2a(model)} | CTX: {ctx}")
        lines.append(SEP)

    lines += [f"Total exposure: {total:.2f}u", "edge > everything ⚡"]
    message = "\n".join(lines)

    if not webhook:
        print()
        print(message)
        print("[Discord] Webhook not configured — card preview only")
        return

    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        resp = requests.post(webhook, json={"content": message}, headers=headers, timeout=(5, 10))
        if resp.status_code in (200, 204):
            print("  [Discord] Game lines card posted.")
        else:
            print(f"  [Discord] Post failed: HTTP {resp.status_code}")
    except Exception as exc:
        print(f"  [Discord] Post error: {exc}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")

    # Load team projections from SaberSim CSVs (auto-detected from Downloads)
    mlb_team_projs = _build_projs("MLB")
    nba_team_projs = _build_projs("NBA")

    print("Fetching MLB base odds (h2h, spreads, totals)...")
    mlb_data = fetch_odds("baseball_mlb", "h2h,spreads,totals")
    print(f"  {len(mlb_data)} MLB games")

    print("Fetching NBA base odds (h2h, spreads, totals)...")
    nba_data = fetch_odds("basketball_nba", "h2h,spreads,totals")
    print(f"  {len(nba_data)} NBA games")

    # Filter to today's unstarted games only, deduplicate by matchup
    from datetime import datetime, timezone
    from zoneinfo import ZoneInfo
    _local_tz = ZoneInfo("America/Denver")  # MT (DST-aware)
    _now_utc = datetime.now(timezone.utc)
    _today_local = datetime.now(_local_tz).date()

    def _is_valid(g):
        try:
            ct = datetime.fromisoformat(g.get("commence_time", "").replace("Z", "+00:00"))
            ct_local = ct.astimezone(_local_tz)
            return ct_local.date() == _today_local and ct > _now_utc
        except Exception:
            return False

    def _dedup_today(games):
        seen, out = set(), []
        for g in sorted(games, key=lambda x: x.get("commence_time","")):
            key = (g.get("away_team",""), g.get("home_team",""))
            if key not in seen and _is_valid(g):
                seen.add(key)
                out.append(g)
        return out

    mlb_data = _dedup_today(mlb_data)
    nba_data = _dedup_today(nba_data)
    print(f"  Filtered to {len(mlb_data)} MLB / {len(nba_data)} NBA unstarted games")

    # Load context verdicts if available
    ctx_verdicts = {}
    try:
        import pathlib as _pl, json as _json
        _ctx_path = _pl.Path(__file__).parent / "data" / "context_verdicts.json"
        if _ctx_path.exists():
            for v in _json.loads(_ctx_path.read_text(encoding="utf-8")):
                ctx_verdicts[v["game"].lower()] = v
            if ctx_verdicts:
                print(f"  [ctx] {len(ctx_verdicts)} verdicts loaded")
    except Exception:
        pass

    analyze_mlb(mlb_data, team_projs=mlb_team_projs, ctx_verdicts=ctx_verdicts)
    analyze_nba(nba_data, team_projs=nba_team_projs, ctx_verdicts=ctx_verdicts)

    bets_sorted = print_ranked_table(ALL_BETS)
    print()
    if bets_sorted:
        raw = input("Log bets? Enter row numbers (e.g. 1,3,5), 'all', or press Enter to skip: ").strip()
        if raw.lower() == "all":
            selected = bets_sorted
        elif raw:
            idxs = []
            for tok in raw.split(","):
                tok = tok.strip()
                if tok.isdigit() and 1 <= int(tok) <= len(bets_sorted):
                    idxs.append(int(tok) - 1)
                else:
                    print(f"  [warn] invalid row '{tok}' -- skipped")
            selected = [bets_sorted[i] for i in idxs]
        else:
            selected = []
        if selected:
            n = _write_game_line_bets(selected, _PICK_LOG_GL_PATH)
            print(f"  Logged {n} bet(s) to {Path(_PICK_LOG_GL_PATH).name}")
            _post_game_lines_discord(selected)
    print()
    print("Legend: STRONG>=8%  |  ***BET>=4%  |  positive edge only  |  stake=f*x10x0.75mult (min 0.25u, max 2.0u)")
    print("MLB: ML=NB(r=3.548) | TT=NB | spread/total/F5=Normal  sigma: total=4.6/spread=4.2  F5=2.65/2.70  scalar=0.540")
    print("NBA: all Normal  |  NHL: all Normal (total=2.311, spread=2.614, team=1.744)")
