#!/usr/bin/env python3
"""
JonnyParlay MBP Runner v2.0 — Pure Python Engine
=================================================
Master Betting Prompt v9.4 (no Bravo Six)

Automates the full workflow:
  1. Reads SaberSim CSV projections
  2. Fetches live odds from The Odds API (all 23 US books + exchanges)
  3. Runs ALL math: Poisson/Normal distributions, no-vig, edge, gates, sizing
  4. Outputs the full betting card (sections A-J)

Zero external AI. Deterministic. Runs in ~30 seconds.

SETUP:
  pip install requests

USAGE:
  python run_picks.py                              # Interactive
  python run_picks.py nba.csv                      # Direct
  python run_picks.py nba.csv nhl.csv              # Multi-sport
  python run_picks.py nba.csv --mode Conservative  # Cold streak
  python run_picks.py nba.csv --dry-run            # Test odds pull only
  python run_picks.py nba.csv --cooldown "Reaves,Sheppard"  # R12 cooldown list
"""

import os, sys, csv, json, time, argparse, math, unicodedata, re, logging
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    import anthropic as _anthropic
    _ANTHROPIC_AVAILABLE = True
except ImportError:
    _ANTHROPIC_AVAILABLE = False
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path
from collections import defaultdict, OrderedDict

# ============================================================
#  CONFIG
# ============================================================

ODDS_API_KEY  = "adb07e9742307895c8d7f14264f52aee"
CSV_FOLDER    = os.path.expanduser("~/Documents/JonnyParlay/projections")
OUTPUT_FOLDER = os.path.expanduser("~/Documents/JonnyParlay/data/picks")
PICK_LOG_PATH = os.path.expanduser("~/Documents/JonnyParlay/data/pick_log.csv")
LOG_FILE_PATH = os.path.expanduser("~/Documents/JonnyParlay/data/jonnyparlay.log")
DISCORD_GUARD_FILE = os.path.expanduser("~/Documents/JonnyParlay/data/discord_posted.json")

# ── File logger setup (file only — console output stays as print()) ───────────
_log_dir = Path(LOG_FILE_PATH).parent
_log_dir.mkdir(parents=True, exist_ok=True)
logger = logging.getLogger("jonnyparlay")
logger.setLevel(logging.INFO)
if not logger.handlers:
    _fh = logging.FileHandler(LOG_FILE_PATH, encoding="utf-8")
    _fh.setFormatter(logging.Formatter("%(asctime)s  %(levelname)-8s %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
    logger.addHandler(_fh)
logger.propagate = False  # Don't bubble up to root logger (avoids duplicate prints)

ODDS_BASE    = "https://api.the-odds-api.com/v4"
ODDS_REGIONS = "us,us2,us_ex"
API_SLEEP    = 1.3  # seconds between calls

SPORT_KEYS = {"NBA": "basketball_nba", "NHL": "icehockey_nhl",
              "NFL": "americanfootball_nfl", "MLB": "baseball_mlb",
              "NCAAB": "basketball_ncaab", "NCAAF": "americanfootball_ncaaf"}

# Colorado-legal sportsbooks — line shopping filtered to these only.
# API key "espnbet" maps to theScore Bet (display name updated in BOOK_DISPLAY).
CO_LEGAL_BOOKS = {
    "draftkings", "fanduel", "betmgm", "williamhill_us", "betrivers",
    "bet365", "fanatics", "hardrockbet", "ballybet", "betparx",
    "espnbet", "pointsbetus", "twinspires", "circasports", "superbook",
    "tipico", "wynnbet", "betway",
}

# Golf code removed — see archived_golf_code.py

# ============================================================
#  DISCORD WEBHOOK CONFIG
# ============================================================
# Paste webhook URLs after creating them in Discord (Phase 2).
# Bot display name on all webhooks: PicksByJonny

DISCORD_WEBHOOK_URL        = "https://discord.com/api/webhooks/1493388060342091958/8J54-XRKRyVOdmVvEc3UhIS9I6ee3u124xD9Ultf8uaoh7uCaFJJFLsAocfyPNCvulmk"   # → #premium-portfolio
DISCORD_BONUS_WEBHOOK      = "https://discord.com/api/webhooks/1493388215476944947/SOFSinJ1bLthupJ6KZRHF7gmzIpOfdBnUijoZQYTpr5HFDiQZKYAUVvvDyQYwWFVV7J0"   # → #bonus-drops
DISCORD_ALT_PARLAY_WEBHOOK = "https://discord.com/api/webhooks/1493388490644263105/_uCAZufERfGx5-Hr2KugkFQxVMRY9TYBGkNGGjmsQiKNpIScgYKv26wITrNBiaO3kTtG"   # → #daily-lay
DISCORD_RECAP_WEBHOOK      = "https://discord.com/api/webhooks/1493388658638848344/1RixaqCAX9kYdjrfDPt9bLKrr3Xn1LQmNvzWHAutT62k09dSsdhvOYBb18JhkS49mwU0"   # → #daily-recap
DISCORD_KILLSHOT_WEBHOOK   = "https://discord.com/api/webhooks/1493388744739393609/pXaLY6oeln8loypUI_mMayo5z9lwKE-McxSx2yTQ15biPcVJC-qflo6SmUV5CIjOzXAE"   # → #killshot  (scaffold — trigger TBD)
DISCORD_MONTHLY_WEBHOOK    = "https://discord.com/api/webhooks/1493398458357383420/YOxYOEjexatDSvAoGnNA-76dP1cX57jKj7frfvwR-4nosBjmXhCZkUKJ5efJ6dDoXkXr"  # → #monthly-tracker
DISCORD_ANNOUNCE_WEBHOOK   = "https://discord.com/api/webhooks/1493399935515889768/GV9M__Wd2ZC037gJ_3zFhjWKGDE_srWzhzQYWIAvmUpAscgRO1p-XjgkS0zVLgK_4s_x"  # → #announcements

BONUS_DAILY_CAP = 5             # Max bonus posts per calendar day

# ── KILLSHOT tier ─────────────────────────────────────────────
KILLSHOT_SCORE_FLOOR  = 90.0   # Minimum Pick Score to auto-qualify
KILLSHOT_MANUAL_FLOOR = 75.0   # Minimum score to allow manual --killshot promote
KILLSHOT_WEEKLY_CAP   = 3      # Max KILLSHOTs per rolling 7 days
# Sizing: replaces VAKE entirely for KILLSHOT picks
KILLSHOT_SIZING = [(110, 999, 5.0), (100, 110, 4.0), (90, 100, 3.0)]
BRAND_LOGO = "https://cdn.discordapp.com/attachments/1115840612915228727/1225636209221566625/JonnyParlaylogoRedBlack.png"

# Shadow sports — evaluated + logged internally but NEVER posted to Discord.
# Remove a sport from this set once it's proven profitable over a meaningful sample.
SHADOW_SPORTS = {"MLB"}

# Each shadow sport logs to its own isolated CSV (keeps main pick_log clean).
SHADOW_LOG_PATHS = {
    "MLB": os.path.expanduser("~/Documents/JonnyParlay/data/pick_log_mlb.csv"),
}

# Per-sport alt spread market names for the parlay builder
SPORT_ALT_MARKET = {
    "NBA": "alternate_spreads",
    "NHL": "alternate_puck_line",
    "MLB": "alternate_run_line",
}

PROP_MARKETS = {
    "NBA": ["player_assists", "player_rebounds", "player_points", "player_threes"],
    "NHL": ["player_shots_on_goal", "player_assists"],
    "MLB": ["pitcher_strikeouts", "pitcher_outs", "pitcher_hits_allowed",
            "batter_hits", "batter_total_bases",
            "batter_hits_runs_rbis"],
}

# Maps API market key → our stat label
MARKET_TO_STAT = {
    "player_assists": "AST", "player_rebounds": "REB",
    "player_points": "PTS", "player_threes": "3PM",
    "player_shots_on_goal": "SOG",
    # MLB
    "pitcher_strikeouts": "K", "pitcher_outs": "OUTS",
    "pitcher_hits_allowed": "HA",
    "batter_hits": "HITS", "batter_total_bases": "TB",
    "batter_hits_runs_rbis": "HRR",
}

# ============================================================
#  SIGMA & TIER CONFIG (v9.4)
# ============================================================

SIGMA = {
    # NBA / NHL (unchanged — these are well-calibrated)
    "AST": {"mult": 0.45, "min": 1.3},
    "REB": {"mult": 0.58, "min": 2.5},
    "SOG": {"mult": 0.55, "min": 1.2},
    "REC": {"mult": 0.50, "min": 1.2},
    "PTS": {"mult": 0.35, "min": 4.5},
    "3PM": {"mult": 0.55, "min": 0.8},
    # MLB — RECALIBRATED to match real-world variance (2024 season data)
    "K":    {"mult": 0.45, "min": 1.5},   # Pitcher Ks — Poisson is a good fit
    "OUTS": {"mult": 0.22, "min": 3.0},   # Pitcher outs — was overestimating variance (conservative)
    "HA":   {"mult": 0.50, "min": 2.5},   # Pitcher hits allowed — MOVED to Normal (15% overdispersed vs Poisson)
    "HITS": {"mult": 0.90, "min": 0.7},   # Batter hits — Poisson is good at low counts
    "TB":   {"mult": 1.20, "min": 1.5},   # Batter total bases — was 41% UNDER real variance (lumpy dist)
    "HRR":  {"mult": 0.75, "min": 1.3},   # Batter H+R+RBI — was 11% under real variance
}

# HA removed from Poisson — overdispersed at typical lines (std 2.70 vs Poisson-predicted 2.35)
POISSON_STATS = {"AST", "REB", "SOG", "REC", "K", "HITS"}
POISSON_CUTOFF = 8.5

# MLB Correlation Groups — stats driven by the same hidden variable (IP for pitchers, PA for batters)
# G11/G11b: max 1 prop per player within each correlated group
PITCHER_STATS = {"K", "OUTS", "HA"}                 # All functions of IP — r ≈ 0.70+ between K/OUTS
BATTER_CORR_STATS = {"HITS", "TB", "HRR"}           # HITS is component of TB and HRR — r ≈ 0.70+
MLB_CORR_GROUPS = [PITCHER_STATS, BATTER_CORR_STATS]

GAME_SIGMA = {
    # "ml" sigma is separate from "spread" sigma — used only for moneyline win probability.
    # NHL puck-line spread sigma (1.5 goals) inflates ML win probs to 80%+ when used for
    # P(margin > 0). Need a wider sigma (~4.0) to produce realistic 55-65% win probs
    # for typical NHL favorites. Calibrated so -150 fav (55% nv) with ~0.5-goal margin ≈ 55%.
    "NBA": {"total": 12.0, "spread": 12.0, "team": 9.0,  "ml": 12.0},
    "NHL": {"total": 1.2,  "spread": 1.5,  "team": 1.8,  "ml": 4.0},
    "MLB": {"total": 4.0,  "spread": 3.8,  "team": 3.0,  "ml": 6.0},
}

# First 5 innings sigmas (MLB only — starter matchup, no bullpen noise)
F5_SIGMA = {"total": 2.6, "spread": 2.5, "team": 2.0}

# Game line projection blending: anchor SaberSim to the market line
# blended = market + BLEND_ALPHA * (saber - market)
# 0.25 = trust SaberSim for 25% of the disagreement, market for 75%
# This prevents massive edge calculations when SaberSim disagrees with Vegas by 10+ pts
BLEND_ALPHA = 0.25

TIERS = {
    "T1":  {"stats": {"AST", "SOG", "REC", "K", "HRR"}, "min_edge": 0.03},
    "T1B": {"stats": {"REB", "HITS", "HA"},              "min_edge": 0.03},  # unders 3.5+ only / low volume
    "T2":  {"stats": {"PTS", "YARDS", "TOTAL", "SPREAD", "TEAM_TOTAL", "ML_FAV",
                       "TB", "OUTS", "F5_TOTAL", "F5_SPREAD", "F5_ML"}, "min_edge": 0.05},
    "T3":  {"stats": {"TDS", "GOALS", "3PM", "ML_DOG", "NRFI", "YRFI"}, "min_edge": 0.06},
    # T4 (GOLF_WIN) removed — see archived_golf_code.py
}

VAKE_BASE = [(0.03, 0.05, 0.50), (0.05, 0.07, 0.75), (0.07, 0.09, 1.00), (0.09, 9.99, 1.25)]
VAKE_MULT = {
    "variance":    {"T1": 1.00, "T1B": 1.00, "T2": 0.85, "T3": 0.65, "T4": 0.40},
    "tier":        {"T1": 1.00, "T1B": 1.00, "T2": 0.90, "T3": 0.60, "T4": 0.35},
}

# ── Context Sanity Layer ──────────────────────────────────────
CONTEXT_API_MODEL       = "claude-haiku-4-5-20251001"
CONTEXT_CONFLICT_MULT   = 0.80   # adj_edge multiplier on conflict verdict
CONTEXT_MAX_WORKERS     = 8      # concurrent API calls
_CONTEXT_CACHE          = {}     # {(sport, player, stat, line, direction, date_str): (verdict, reason)}

def _build_context_prompt(sport, stat, player, direction, line, game, today, pregame_notes=""):
    """Build a sanity-check prompt for a single pick.

    This is NOT a projection system — SaberSim already handles matchup/form analysis.
    The only job here is to catch obvious red flags that broke AFTER the CSV was exported:
    player injured/scratched, late lineup change, something clearly wrong.

    Args:
        sport, stat, player, direction, line, game, today: pick fields
        pregame_notes: pre-scanned injury/lineup bulletin from run_pregame_scan
    """
    notes_block = f"\nToday's injury/lineup news:\n{pregame_notes}\n" if pregame_notes else "\n(No pregame intel available)\n"

    return (
        f"Date: {today} | Pick: {player} {direction} {line} {stat} | Game: {game}"
        f"{notes_block}\n"
        f"Two-part check for {player} tonight:\n"
        f"1. RED FLAG? Is {player} listed OUT, DOUBTFUL, scratched, or did a serious injury break today?\n"
        f"2. If no red flag — give a 'supports' verdict if ANY of these are true:\n"
        f"   - {player} is confirmed active/healthy/present tonight\n"
        f"   - {player} has been in strong recent form\n"
        f"   - A key opponent defender or teammate is out affecting this matchup\n"
        f"   - Any other clear positive context for this bet\n\n"
        f'Output ONLY this JSON: {{"verdict": "conflicts"|"neutral"|"supports", "reason": "<10 words>"}}\n\n'
        f'- "conflicts" = player OUT, DOUBTFUL, scratched, or serious new injury — ONLY for clear hard stops\n'
        f'- "supports"  = confirmed active OR any positive signal found — lean toward this when no red flag\n'
        f'- "neutral"   = genuinely nothing found either way'
    )

PICK_SCORE_MODES = {
    "Default":      (0.60, 0.40),
    "Conservative": (0.70, 0.30),
    "Aggressive":   (0.45, 0.55),
}

# Sportsbook display names (API key → clean name)
BOOK_DISPLAY = {
    "espnbet": "theScore Bet", "betonlineag": "BetOnline", "betmgm": "BetMGM",
    "betrivers": "BetRivers", "betus": "BetUS", "bovada": "Bovada",
    "williamhill_us": "Caesars", "draftkings": "DraftKings", "fanatics": "Fanatics",
    "fanduel": "FanDuel", "lowvig": "LowVig", "mybookieag": "MyBookie",
    "ballybet": "Bally Bet", "betanysports": "BetAnySports", "betparx": "BetParx",
    "fliff": "Fliff", "hardrockbet": "Hard Rock Bet", "rebet": "ReBet",
    "betopenly": "BetOpenly", "kalshi": "Kalshi", "novig": "Novig",
    "polymarket": "Polymarket", "prophetx": "ProphetX",
    "superbook": "SuperBook", "betway": "Betway",
}

def _norm_book(key: str) -> str:
    """Normalize book key by stripping region suffix (e.g. hardrockbet_fl → hardrockbet).
    Used when writing to pick_log so downstream tools always see the base key."""
    if not key:
        return key
    base = key.rsplit("_", 1)[0] if "_" in key else key
    return base if base in CO_LEGAL_BOOKS else key

def display_book(api_key):
    """Convert API book key to display name. Handles region suffixes like _az, _co."""
    if api_key in BOOK_DISPLAY:
        return BOOK_DISPLAY[api_key]
    # Try stripping region suffix (e.g. hardrockbet_az → hardrockbet)
    base = api_key.rsplit("_", 1)[0] if "_" in api_key else api_key
    return BOOK_DISPLAY.get(base, api_key)

# Team abbreviation reverse lookup (full API name → abbreviation)
TEAM_ABBREV = {
    # NBA
    "boston celtics": "BOS", "brooklyn nets": "BKN", "new york knicks": "NYK",
    "philadelphia 76ers": "PHI", "toronto raptors": "TOR", "chicago bulls": "CHI",
    "cleveland cavaliers": "CLE", "detroit pistons": "DET", "indiana pacers": "IND",
    "milwaukee bucks": "MIL", "atlanta hawks": "ATL", "charlotte hornets": "CHA",
    "miami heat": "MIA", "orlando magic": "ORL", "washington wizards": "WAS",
    "dallas mavericks": "DAL", "houston rockets": "HOU", "memphis grizzlies": "MEM",
    "new orleans pelicans": "NOP", "san antonio spurs": "SAS",
    "denver nuggets": "DEN", "minnesota timberwolves": "MIN",
    "oklahoma city thunder": "OKC", "portland trail blazers": "POR",
    "utah jazz": "UTA", "golden state warriors": "GSW",
    "la clippers": "LAC", "los angeles clippers": "LAC",
    "los angeles lakers": "LAL", "la lakers": "LAL",
    "phoenix suns": "PHX", "sacramento kings": "SAC",
    # NHL
    "anaheim ducks": "ANA", "arizona coyotes": "ARI", "boston bruins": "BOS",
    "buffalo sabres": "BUF", "calgary flames": "CGY", "carolina hurricanes": "CAR",
    "chicago blackhawks": "CHI", "colorado avalanche": "COL",
    "columbus blue jackets": "CBJ", "dallas stars": "DAL", "detroit red wings": "DET",
    "edmonton oilers": "EDM", "florida panthers": "FLA", "los angeles kings": "LAK",
    "minnesota wild": "MIN", "montreal canadiens": "MTL", "nashville predators": "NSH",
    "new jersey devils": "NJD", "new york islanders": "NYI", "new york rangers": "NYR",
    "ottawa senators": "OTT", "philadelphia flyers": "PHI",
    "pittsburgh penguins": "PIT", "san jose sharks": "SJS",
    "seattle kraken": "SEA", "st louis blues": "STL", "tampa bay lightning": "TBL",
    "toronto maple leafs": "TOR", "vancouver canucks": "VAN",
    "vegas golden knights": "VGK", "washington capitals": "WSH", "winnipeg jets": "WPG",
    "utah hockey club": "UTA",
    # MLB
    "arizona diamondbacks": "ARI", "atlanta braves": "ATL", "baltimore orioles": "BAL",
    "boston red sox": "BOS", "chicago cubs": "CHC", "chicago white sox": "CWS",
    "cincinnati reds": "CIN", "cleveland guardians": "CLE", "colorado rockies": "COL",
    "detroit tigers": "DET", "houston astros": "HOU", "kansas city royals": "KC",
    "los angeles angels": "LAA", "los angeles dodgers": "LAD", "miami marlins": "MIA",
    "milwaukee brewers": "MIL", "minnesota twins": "MIN", "new york mets": "NYM",
    "new york yankees": "NYY", "oakland athletics": "OAK", "philadelphia phillies": "PHI",
    "pittsburgh pirates": "PIT", "san diego padres": "SD", "san francisco giants": "SF",
    "seattle mariners": "SEA", "st. louis cardinals": "STL", "st louis cardinals": "STL",
    "tampa bay rays": "TB", "texas rangers": "TEX", "toronto blue jays": "TOR",
    "washington nationals": "WSH",
    # Odds API alternate name formats
    "la angels": "LAA", "la dodgers": "LAD",
}

# Reverse lookup: abbreviation → set of possible full names (for spread/ML team identification)
ABBREV_TO_NAMES = {}
for _full, _abbr in TEAM_ABBREV.items():
    ABBREV_TO_NAMES.setdefault(_abbr, set()).add(_full)

def resolve_team_abbrev(api_name):
    """Resolve a full API team name (e.g., 'Los Angeles Clippers') to abbreviation.
    Tries: exact TEAM_ABBREV lookup → substring match → last-word match.
    Returns abbreviation string or '' if no match.
    """
    low = api_name.strip().lower()
    # 1. Exact match in TEAM_ABBREV
    if low in TEAM_ABBREV:
        return TEAM_ABBREV[low]
    # 2. Check if any TEAM_ABBREV key is a substring of the name (or vice versa)
    for full_name, abbr in TEAM_ABBREV.items():
        if full_name in low or low in full_name:
            return abbr
    # 3. Last-word match (e.g., "Clippers" → find key containing "clippers")
    last_word = low.split()[-1] if low.split() else ""
    if last_word and len(last_word) > 3:
        for full_name, abbr in TEAM_ABBREV.items():
            if last_word in full_name:
                return abbr
    return ""

def find_team_proj(api_name, team_proj, field="saber_team"):
    """Find a team's projection value given an API team name and the team_proj dict.
    team_proj is keyed by CSV abbreviations (DEN, MEM, etc.).
    Returns the projection value or None.
    """
    # 1. Direct abbreviation lookup
    abbr = resolve_team_abbrev(api_name)
    if abbr and abbr in team_proj and team_proj[abbr].get(field, 0) > 0:
        return team_proj[abbr][field]
    # 2. Substring fallback (existing behavior for simple cases like VAN in VANCOUVER)
    for tk, tv in team_proj.items():
        if tv.get(field, 0) > 0:
            name_upper = api_name.upper()
            if (tk in name_upper or name_upper in tk or
                any(w in tk for w in name_upper.split()[-1:])):
                return tv[field]
    return None

def get_team_abbrev(game_str, team_csv=""):
    """Get team abbreviation from game string or CSV team column."""
    if team_csv:
        return team_csv.upper()
    # Try to extract from game string
    for full_name, abbr in TEAM_ABBREV.items():
        if full_name in game_str.lower():
            return abbr
    return ""

# ============================================================
#  MATH ENGINE
# ============================================================

def poisson_pmf(k, lam):
    """Poisson PMF: P(X = k) given lambda."""
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return math.exp(-lam) * (lam ** k) / math.factorial(k)

def poisson_cdf(k, lam):
    """Poisson CDF: P(X <= k)."""
    if lam <= 0:
        return 1.0
    total = 0.0
    for i in range(int(k) + 1):
        total += poisson_pmf(i, lam)
    return min(total, 1.0)

def normal_cdf(x, mu, sigma):
    """Normal CDF using math.erf."""
    if sigma <= 0:
        return 1.0 if x >= mu else 0.0
    return 0.5 * (1.0 + math.erf((x - mu) / (sigma * math.sqrt(2))))

def implied_prob(odds):
    """American odds → implied probability."""
    if odds == 0:
        return 0.0
    if odds < 0:
        return abs(odds) / (abs(odds) + 100.0)
    else:
        return 100.0 / (odds + 100.0)

def no_vig(imp1, imp2):
    """Remove vig from two-sided implied probs."""
    total = imp1 + imp2
    if total == 0:
        return 0.5, 0.5
    return imp1 / total, imp2 / total

def is_decimal_leak(odds):
    """Check if odds look like decimal format leaked through."""
    return 1.0 < odds < 3.0

def calc_prop_prob(proj, line, stat):
    """Calculate over/under probability for a player prop.
    FIX M1: For integer lines, properly handle push probability.
    Push at exactly the line is excluded (DK rules: push = refund),
    so redistribute: over_p and under_p should sum to ~1.0 after
    removing push mass.
    """
    if stat in POISSON_STATS and line <= POISSON_CUTOFF:
        k = math.floor(line)
        if line == k:  # Integer line — push-adjusted
            push = poisson_pmf(k, proj)
            strict_over = 1.0 - poisson_cdf(k, proj)
            strict_under = poisson_cdf(k - 1, proj)
            non_push = 1.0 - push
            if non_push > 0:
                over_p = strict_over / non_push
                under_p = strict_under / non_push
            else:
                over_p = 0.5
                under_p = 0.5
        else:  # Half-integer line — no push possible
            under_p = poisson_cdf(k, proj)
            over_p = 1.0 - poisson_cdf(k, proj)
    else:
        s = SIGMA.get(stat, {"mult": 0.40, "min": 2.0})
        sigma = max(proj * s["mult"], s["min"])
        under_p = normal_cdf(line, proj, sigma)
        over_p = 1.0 - normal_cdf(line, proj, sigma)
    return over_p, under_p

def calc_edge(model_prob, over_odds, under_odds):
    """Calculate no-vig edge for both sides. Returns (over_edge, under_edge)."""
    imp_over = implied_prob(over_odds)
    imp_under = implied_prob(under_odds)
    nv_over, nv_under = no_vig(imp_over, imp_under)
    # model_prob is P(over)
    over_edge = model_prob - nv_over
    under_edge = (1.0 - model_prob) - nv_under
    return over_edge, under_edge, nv_over, nv_under

def pick_score(win_prob, edge, mode="Default"):
    """Calculate Pick Score: 0.60×wp_normalized + 0.40×edge_normalized.

    R11 NOTE: Game line picks (totals, spreads, ML) intentionally score lower than
    props. Win probs for game lines cluster near 50-55% (well-priced markets),
    while props can reach 60-70%+ on model-vs-market gaps.  This is correct behavior —
    game lines are lower-conviction by design and rarely surface in the Premium 5.
    """
    sw, ew = PICK_SCORE_MODES.get(mode, (0.60, 0.40))
    wp_n = (win_prob * 100 - 50) / 25 * 100
    e_n = (edge * 100) / 20 * 100
    return sw * wp_n + ew * e_n

def base_units(edge):
    """VAKE base unit from edge.
    FIX M4: Safety floor — if edge < 3% somehow slips past G9, return minimum
    instead of falling through to max 1.25u.
    """
    if edge < 0.03:
        return 0.50  # safety floor
    for lo, hi, size in VAKE_BASE:
        if lo <= edge < hi:
            return size
    return 1.25

def round_units(u):
    """Round to nearest 0.25u."""
    return round(u * 4) / 4

def get_tier(stat, direction="over"):
    """Determine tier for a stat + direction.
    FIX H1: T1B must be checked before T1/T2/T3 fallthrough.
    HITS and HA are in T1B (unders only, 3% min edge).
    """
    if stat == "REB":
        if direction == "over":
            return None  # BANNED
        return "T1B"
    if stat in TIERS["T1B"]["stats"] and direction == "under":
        return "T1B"
    if stat in TIERS["T1"]["stats"]:
        return "T1"
    if stat in TIERS["T2"]["stats"]:
        return "T2"
    if stat in TIERS["T3"]["stats"]:
        return "T3"
    # Game lines
    return "T2"

def get_tier_min_edge(tier):
    """Get minimum edge for a tier."""
    return TIERS.get(tier, {}).get("min_edge", 0.05)

# ============================================================
#  GATES
# ============================================================

def check_prop_gates(pick):
    """Apply gates G1-G10. Returns (pass, gate_failed) tuple."""
    prob = pick["win_prob"]
    edge = pick["adj_edge"]
    odds = pick["odds"]
    line = pick["line"]
    stat = pick["stat"]
    direction = pick["direction"]

    # G3: missing both sides
    if pick.get("missing_side"):
        return False, "G3"

    # G7: hard juice ban
    if odds <= -150:
        return False, "G7"

    # G7b: soft juice
    if -149 <= odds <= -140 and edge < 0.09:
        return False, "G7b"

    # G8: binary fragility (FIX M3: extended to MLB low-count stats)
    # Exception: SOG ≤ 1.5 UNDER passes if model is very confident (WP ≥ 0.80 AND edge ≥ 0.15)
    if stat in ("AST", "REB", "SOG", "K", "HA", "HITS") and line <= 1.5:
        if stat == "SOG" and direction == "under" and prob >= 0.80 and edge >= 0.15:
            pass  # High-conviction SOG under exception — allow through
        else:
            return False, "G8"

    # G9: universal floor
    if edge < 0.03:
        return False, "G9"

    # G13: sub-50% win probability ban — proven 1-3 record, negative PS
    if prob < 0.50:
        return False, "G13"

    # G1: high prob + bad odds — but allow if edge is strong (FIX L2)
    if prob >= 0.70 and odds > -200 and edge < 0.05:
        return False, "G1"

    # G2: model error — but O0.5 HRR/TB/HITS are soft markets with legitimately large edges
    _is_soft_o05 = (stat in ("HRR", "TB", "HITS") and line <= 0.5 and direction == "over")
    g2_threshold = 0.28 if _is_soft_o05 else 0.20
    if edge >= g2_threshold:
        return False, "G2"

    # G4: low line + extreme prob — exempt O0.5 soft markets (HRR/TB/HITS)
    if line <= 2.5 and prob > 0.75 and not _is_soft_o05:
        return False, "G4"

    # G5: plus odds + high prob — exempt O0.5 soft markets
    if odds > 0 and prob > 0.65 and not _is_soft_o05:
        return False, "G5"

    # G10: low-line under fragility
    if direction == "under" and line <= 2.5 and edge < 0.08:
        return False, "G10"

    return True, None

def check_game_gates(pick):
    """Apply gates GG1-GG5."""
    edge = pick["adj_edge"]
    proj = pick["proj"]
    line = pick["line"]
    sigma = pick["sigma"]
    stat = pick.get("stat", "")

    if pick.get("missing_side"):
        return False, "GG4"
    if edge >= 0.10:
        return False, "GG1"
    # GG2: projection too far from market expectation
    # For SPREAD: proj = team margin, line = spread (opposite sign convention)
    #   Market implied margin = -line, so distance = abs(proj - (-line)) = abs(proj + line)
    # For TOTAL/TEAM_TOTAL/ML: abs(proj - line) is correct
    if sigma > 0:
        if stat == "SPREAD":
            deviation = abs(proj + line) / sigma
        else:
            deviation = abs(proj - line) / sigma
        if deviation > 1.5:
            return False, "GG2"
    if edge <= 0:
        return False, "GG3"

    # GG5: No dog-cover spread bets (positive odds on a -1.5/+1.5 line)
    # Puck line / run line dogs at +150 to +205 are lottery tickets, not systematic edges.
    # The model finds "edge" vs market but win_prob < 50% and pick_score goes negative.
    if pick.get("stat") == "SPREAD" and pick.get("odds", 0) > 0:
        return False, "GG5"

    return True, None

# ============================================================
#  RULES ENGINE (R1-R12)
# ============================================================

def apply_hard_rules(picks):
    """Apply R4 (REB bans), R11 (U2.5 AST ban) before anything else."""
    filtered = []
    for p in picks:
        # R4: REB Overs banned entirely
        if p["stat"] == "REB" and p["direction"] == "over":
            continue
        # R4: U2.5 REB banned
        if p["stat"] == "REB" and p["direction"] == "under" and p["line"] <= 2.5:
            continue
        # R11: U2.5 AST fully banned
        if p["stat"] == "AST" and p["direction"] == "under" and p["line"] <= 2.5:
            continue
        filtered.append(p)
    return filtered

def auto_r12_from_log(today_str: str, window_days: int = 5) -> list[str]:
    """Read pick_log.csv and return player names with a loss in the last window_days.
    These are auto-added to the R12 cooldown list so you never have to pass --cooldown manually.
    Only counts primary/bonus picks (not manual) to avoid polluting the list with one-offs."""
    log_path = Path(PICK_LOG_PATH)
    if not log_path.exists():
        return []
    try:
        cutoff = (datetime.strptime(today_str, "%Y-%m-%d") - timedelta(days=window_days - 1)).strftime("%Y-%m-%d")
        with open(log_path, "r", newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        losers = set()
        for r in rows:
            if r.get("result", "").upper() != "L":
                continue
            if r.get("run_type", "") not in ("primary", "bonus"):
                continue
            row_date = r.get("date", "")
            if not (cutoff <= row_date < today_str):  # exclude today — not graded yet
                continue
            player = r.get("player", "").strip()
            if player:
                losers.add(player)
        return list(losers)
    except Exception as e:
        logger.warning(f"auto_r12_from_log failed: {e}")
        return []

def apply_r12_cooldown(picks, cooldown_players):
    """R12: Skip players whose last MBP pick was a loss within 5 days."""
    if not cooldown_players:
        return picks
    cool_set = {normalize_name(n) for n in cooldown_players}
    return [p for p in picks if normalize_name(p["player"]) not in cool_set]

def apply_soft_rules_premium(premium, all_qualifying):
    """
    Apply R6, R7, R8, R9, R10 to build the Premium 5.

    R8 (updated): Reserve first 3 slots for T1/T1B (by PS desc).
    Fill remaining 2 slots by pure Pick Score from ALL tiers.
    This ensures T1 dominance while letting strong T2/T3 picks break through.
    """
    T1_RESERVED = 3  # slots reserved for T1/T1B

    t1_picks = sorted([p for p in all_qualifying if p["tier"] in ("T1", "T1B")],
                       key=lambda p: p["pick_score"], reverse=True)
    all_by_ps = sorted(all_qualifying, key=lambda p: p["pick_score"], reverse=True)

    # Count how many overs passed all gates
    total_overs = sum(1 for p in all_qualifying if p["direction"] == "over")

    premium = []
    used = set()  # track by id() to avoid duplicates
    game_count = defaultdict(int)
    stat_dir_count = defaultdict(int)
    pitcher_game_dir_count = defaultdict(int)  # G12: (game, direction) → pitcher prop count
    over_count = 0
    has_over = False

    def can_add(p):
        game = p.get("game", "")
        key = (p["stat"], p["direction"])
        if game_count[game] >= 2:  # R7
            return False
        if stat_dir_count[key] >= 2:  # R10
            return False
        if p["direction"] == "over" and over_count >= 3:  # R6
            return False
        # G12: Max 2 same-direction pitcher props per game on Premium
        if p["stat"] in PITCHER_STATS:
            pgd_key = (game, p["direction"])
            if pitcher_game_dir_count[pgd_key] >= 2:
                return False
        return True

    def add_pick(p):
        nonlocal over_count, has_over
        premium.append(p)
        used.add(id(p))
        game = p.get("game", "")
        game_count[game] += 1
        stat_dir_count[(p["stat"], p["direction"])] += 1
        if p["stat"] in PITCHER_STATS:
            pitcher_game_dir_count[(game, p["direction"])] += 1
        if p["direction"] == "over":
            over_count += 1
            has_over = True

    # Phase 1: Fill up to T1_RESERVED slots with T1/T1B picks
    for p in t1_picks:
        if len(premium) >= T1_RESERVED:
            break
        if can_add(p):
            add_pick(p)

    # Phase 2: Fill remaining slots (up to 5) by pure Pick Score from ALL tiers
    for p in all_by_ps:
        if len(premium) >= 5:
            break
        if id(p) in used:
            continue
        if can_add(p):
            add_pick(p)

    # R9: If 3+ overs passed gates but none on Premium, force one
    if total_overs >= 3 and not has_over and len(premium) == 5:
        # Identify the lowest-PS non-over to remove (last in list = lowest PS)
        swap_idx = None
        for i in range(len(premium) - 1, -1, -1):
            if premium[i]["direction"] != "over":
                swap_idx = i
                break
        if swap_idx is not None:
            old_pick = premium[swap_idx]
            old_game = old_pick.get("game", "")
            old_key  = (old_pick["stat"], old_pick["direction"])
            # Temporarily remove old_pick's contributions so can_add() sees correct state
            game_count[old_game] -= 1
            stat_dir_count[old_key] -= 1
            if old_pick["stat"] in PITCHER_STATS:
                pitcher_game_dir_count[(old_game, old_pick["direction"])] -= 1
            used.discard(id(old_pick))
            # Find best valid over replacement given freed slot
            best_over = None
            for p in all_by_ps:
                if p["direction"] == "over" and id(p) not in used:
                    if can_add(p):
                        best_over = p
                        break
            if best_over:
                # Commit the swap and update all tracking counters
                premium[swap_idx] = best_over
                new_game = best_over.get("game", "")
                game_count[new_game] += 1
                stat_dir_count[(best_over["stat"], best_over["direction"])] += 1
                if best_over["stat"] in PITCHER_STATS:
                    pitcher_game_dir_count[(new_game, best_over["direction"])] += 1
                used.add(id(best_over))
            else:
                # No valid over found — restore old_pick's contributions
                game_count[old_game] += 1
                stat_dir_count[old_key] += 1
                if old_pick["stat"] in PITCHER_STATS:
                    pitcher_game_dir_count[(old_game, old_pick["direction"])] += 1
                used.add(id(old_pick))

    return premium[:5]

def apply_caps(picks, sport_totals):
    """Apply daily caps: per-stat, per-game, per-sport, daily total.
    Includes G12: max 2 same-direction pitcher props per game."""
    # Sort by pick_score descending so best picks get cap priority (fixes H4 bug)
    picks = sorted(picks, key=lambda p: p.get("pick_score", 0), reverse=True)

    result = []
    stat_count = defaultdict(int)
    game_count = defaultdict(int)
    sport_units = defaultdict(float)
    total_units = 0.0
    pitcher_game_dir = defaultdict(int)   # G12: (game, direction) → count of pitcher props

    # NHL SOG gets 6 per stat, everything else 2
    STAT_CAP = defaultdict(lambda: 2)
    STAT_CAP["SOG"] = 6

    SPORT_UNIT_CAP = {"NBA": 8.0, "NHL": 5.0, "NFL": 8.0, "MLB": 8.0}

    for p in picks:
        stat = p["stat"]
        game = p.get("game", "")
        sport = p.get("sport", "NBA")
        size = p["size"]

        if stat_count[stat] >= STAT_CAP[stat]:
            continue
        if game_count[game] >= 2:
            continue
        if sport_units[sport] + size > SPORT_UNIT_CAP.get(sport, 8.0):
            continue
        if total_units + size > 12.0:
            continue

        # G12: Max 2 same-direction pitcher props per game
        if stat in PITCHER_STATS:
            pgd_key = (game, p["direction"])
            if pitcher_game_dir[pgd_key] >= 2:
                continue

        result.append(p)
        stat_count[stat] += 1
        game_count[game] += 1
        sport_units[sport] += size
        total_units += size
        if stat in PITCHER_STATS:
            pitcher_game_dir[(game, p["direction"])] += 1

    return result

# ============================================================
#  VAKE SIZING
# ============================================================

def size_picks_base(picks):
    """Apply BASE sizing to all qualifying picks (Full Card). No VAKE multipliers.
    Sub-50% win probability bets get capped at 0.75u max (high variance)."""
    for p in picks:
        edge = p["adj_edge"]
        base = base_units(edge)
        # FIX L3: T3 picks (3PM, NRFI) get 0.25u floor instead of 0.50u
        tier = p.get("tier", "T2")
        floor = 0.25 if tier == "T3" else 0.50
        final = max(round_units(base), floor)
        final = min(final, 1.25)
        # Cap high-variance bets (win prob < 50%) at 0.75u
        if p.get("win_prob", 1.0) < 0.50:
            final = min(final, 0.75)
        p["size"] = final
    return picks

def size_picks_vake(premium):
    """Apply full VAKE sizing to Premium 5 only, in Pick Score descending order.
    Includes R13: pitcher correlation penalty for same-game pitcher props."""
    premium_sorted = sorted(premium, key=lambda p: p["pick_score"], reverse=True)

    stat_seen = defaultdict(int)
    game_seen = defaultdict(int)
    pitcher_game_seen = defaultdict(int)  # R13: track pitcher props per game

    for p in premium_sorted:
        edge = p["adj_edge"]
        tier = p["tier"]
        game = p.get("game", "")
        stat = p["stat"]

        base = base_units(edge)

        # Variance multiplier
        var_m = VAKE_MULT["variance"].get(tier, 0.85)
        # Tier multiplier
        tier_m = VAKE_MULT["tier"].get(tier, 0.90)

        # Correlation multiplier (general same-game)
        game_seen[game] += 1
        if game_seen[game] == 1:
            corr_m = 1.00
        elif game_seen[game] == 2:
            corr_m = 0.85
        else:
            corr_m = 0.70

        # R13: Extra pitcher correlation penalty — same-game pitcher props share IP/pace
        if stat in PITCHER_STATS:
            pitcher_game_seen[game] += 1
            if pitcher_game_seen[game] >= 2:
                corr_m *= 0.70  # additional 0.70x on top of existing game correlation

        # Exposure multiplier
        stat_seen[stat] += 1
        exp_m = 1.00 if stat_seen[stat] == 1 else 0.70

        raw = base * var_m * tier_m * corr_m * exp_m
        final = min(round_units(raw), 1.25)
        final = max(final, 0.50)  # minimum 0.50u, never 0.25u

        p["size"] = final
        p["size_detail"] = {
            "base": base, "var": var_m, "tier": tier_m,
            "corr": corr_m, "exp": exp_m, "raw": raw
        }

    return premium_sorted

# ============================================================
#  CSV PARSER
# ============================================================

def normalize_name(name):
    """Normalize a player name for matching."""
    name = unicodedata.normalize("NFKD", name)
    name = name.encode("ascii", "ignore").decode("ascii")
    name = name.strip().lower()
    name = re.sub(r"[^a-z\s]", "", name)
    return name

def name_key(name):
    """Generate a fuzzy match key: last name + first 3 chars of first name.
    FIX M5: Strip Jr/Sr/II/III/IV/V suffixes before extracting last name,
    so 'Jaren Jackson Jr.' → 'jackson_jar' instead of 'jr_jar'.
    """
    parts = normalize_name(name).split()
    if len(parts) < 2:
        return normalize_name(name)
    suffixes = {"jr", "sr", "ii", "iii", "iv", "v"}
    while len(parts) > 2 and parts[-1] in suffixes:
        parts.pop()
    first = parts[0][:3]
    last = parts[-1]
    return f"{last}_{first}"

def parse_csv(filepath):
    """Parse SaberSim CSV. Returns list of player dicts and detected sport."""
    path = Path(filepath)
    with open(path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        print(f"  [!] Empty CSV: {filepath}")
        return [], "NBA"

    headers = {h.strip().lower() for h in rows[0].keys()}

    # Detect sport
    if "sog" in headers or any("shot" in h for h in headers):
        sport = "NHL"
    elif "ip" in headers and ("er" in headers or "k" in headers or "qs" in headers):
        sport = "MLB"
    elif "rb" in headers or "ast" in headers or "3pt" in headers:
        sport = "NBA"
    else:
        # Fallback: check filename
        fname = path.name.lower()
        if "mlb" in fname:
            sport = "MLB"
        elif "nhl" in fname:
            sport = "NHL"
        else:
            sport = "NBA"

    players = []
    for row in rows:
        # Clean keys
        clean = {k.strip(): v.strip() for k, v in row.items()}

        try:
            # R10: Parse Status column — "Confirmed" means SaberSim has confirmed this starter
            raw_status = clean.get("Status", clean.get("status", "")).strip().lower()
            p = {
                "name": clean.get("Name", clean.get("name", "")),
                "team": clean.get("Team", clean.get("team", "")),
                "opp":  clean.get("Opp", clean.get("opp", "")),
                "pos":  clean.get("Pos", clean.get("pos", "")),
                "saber_total": float(clean.get("Saber Total", clean.get("saber total", 0)) or 0),
                "saber_team":  float(clean.get("Saber Team", clean.get("saber team", 0)) or 0),
                "status": raw_status,  # "confirmed" for confirmed starters, "" otherwise
            }

            if sport == "NBA":
                p["AST"] = float(clean.get("AST", clean.get("ast", 0)) or 0)
                p["REB"] = float(clean.get("RB", clean.get("rb", clean.get("REB", 0))) or 0)
                p["PTS"] = float(clean.get("PTS", clean.get("pts", 0)) or 0)
                p["3PM"] = float(clean.get("3PT", clean.get("3pt", clean.get("3PM", 0))) or 0)
            elif sport == "NHL":
                # Filter goalies
                if p["pos"].upper() == "G":
                    continue
                p["SOG"] = float(clean.get("SOG", clean.get("sog", 0)) or 0)
                p["AST"] = float(clean.get("A", clean.get("a", clean.get("AST", 0))) or 0)
            elif sport == "MLB":
                is_pitcher = p["pos"].upper() == "P"
                # Raw stats from SaberSim
                singles = float(clean.get("1B", 0) or 0)
                doubles = float(clean.get("2B", 0) or 0)
                triples = float(clean.get("3B", 0) or 0)
                hr = float(clean.get("HR", 0) or 0)
                r = float(clean.get("R", 0) or 0)
                rbi = float(clean.get("RBI", 0) or 0)
                h = float(clean.get("H", 0) or 0)
                k = float(clean.get("K", 0) or 0)
                bb = float(clean.get("BB", 0) or 0)
                ip = float(clean.get("IP", 0) or 0)
                er = float(clean.get("ER", 0) or 0)
                pa = float(clean.get("PA", 0) or 0)

                p["is_pitcher"] = is_pitcher
                if is_pitcher:
                    p["K"] = k
                    p["OUTS"] = ip * 3  # Convert IP to outs recorded
                    p["HA"] = h         # Hits allowed
                    p["ER"] = er        # Earned runs — internal use only (game-line projection math)
                    p["IP"] = ip
                    p["BB"] = bb
                    p["HR"] = hr        # R4: HR allowed — required for FIP calculation
                else:
                    p["HITS"] = h
                    p["TB"] = singles + 2 * doubles + 3 * triples + 4 * hr  # Total bases
                    p["HRR"] = h + r + rbi  # Hits + Runs + RBIs
                    p["R"] = r
                    p["RBI"] = rbi
                    p["HR"] = hr
                    p["PA"] = pa

            p["name_key"] = name_key(p["name"])
            players.append(p)
        except (ValueError, KeyError):
            continue

    # Deduplicate by name_key (handles Showdown CSVs where each player appears twice)
    seen = {}
    deduped = []
    for p in players:
        nk = p["name_key"]
        if nk not in seen:
            seen[nk] = True
            deduped.append(p)
    is_showdown = "showdown" in path.name.lower()
    if is_showdown and len(players) != len(deduped):
        print(f"  Loaded {path.name}: {len(deduped)} players (Showdown deduped from {len(players)}), sport: {sport}")
    else:
        print(f"  Loaded {path.name}: {len(deduped)} players, sport: {sport}")
    return deduped, sport

# ============================================================
#  ODDS FETCHER
# ============================================================

import requests

class OddsFetcher:
    def __init__(self):
        self.remaining = None

    def _get(self, url, params):
        params["apiKey"] = ODDS_API_KEY
        for attempt in range(3):
            try:
                r = requests.get(url, params=params, timeout=15)
                self.remaining = r.headers.get("x-requests-remaining")
                if r.status_code == 200:
                    return r.json()
                elif r.status_code == 422:
                    return []
                elif r.status_code == 401:
                    print("[ERROR] Invalid Odds API key.")
                    sys.exit(1)
                else:
                    print(f"  [!] API {r.status_code}")
                    time.sleep(2 ** attempt)
            except Exception as e:
                print(f"  [!] {e}")
                time.sleep(2 ** attempt)
        return []

    def _load_cache(self, sport):
        """Load cached odds data if fresh enough (< 15 min old)."""
        cache_dir = Path(OUTPUT_FOLDER) / "cache"
        cache_file = cache_dir / f"odds_{sport}_{datetime.now().strftime('%Y-%m-%d')}.json"
        if cache_file.exists():
            age_min = (time.time() - cache_file.stat().st_mtime) / 60
            if age_min < 15:
                try:
                    with open(cache_file, "r") as f:
                        data = json.load(f)
                    print(f"  ♻️  Using cached {sport} odds ({age_min:.0f} min old)")
                    return data
                except Exception:
                    pass
        return None

    def _save_cache(self, sport, data):
        """Save odds data to cache."""
        cache_dir = Path(OUTPUT_FOLDER) / "cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file = cache_dir / f"odds_{sport}_{datetime.now().strftime('%Y-%m-%d')}.json"
        try:
            with open(cache_file, "w") as f:
                json.dump(data, f, default=str)
        except Exception:
            pass

    def fetch_all(self, sports, fetch_alt_spreads=False, game_lines_only=False, no_cache=False, force=False):
        """Fetch all odds. Batches markets per event. Caches for 15 min."""
        all_data = {}

        for sport in sports:
            sk = SPORT_KEYS.get(sport)
            if not sk:
                continue

            print(f"\n  {'='*40}")
            print(f"  Fetching {sport} odds...")

            # Check cache first
            if not no_cache:
                cached = self._load_cache(sport)
                if cached:
                    all_data[sport] = cached
                    continue

            data = {"events": [], "game_lines": [], "props": {}}
            api_calls = 0

            # Events
            events = self._get(f"{ODDS_BASE}/sports/{sk}/events", {})
            api_calls += 1
            now = datetime.now(timezone.utc)
            # FIX L1: Dynamic timezone — handles MST/MDT automatically
            CO_TZ = ZoneInfo("America/Denver")
            local_now = now.astimezone(CO_TZ)
            local_date = local_now.strftime("%Y-%m-%d")
            # End of today = next midnight local → in UTC
            local_midnight = local_now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
            end_of_today_utc = local_midnight.astimezone(timezone.utc)

            def parse_commence(ct):
                """Parse API commence_time string to UTC datetime."""
                try:
                    ct = ct.replace("Z", "+00:00")
                    return datetime.fromisoformat(ct)
                except Exception:
                    return None

            upcoming = []
            for e in (events or []):
                ct = parse_commence(e.get("commence_time", ""))
                # --force: skip the now < ct check so already-started games are included (test only)
                in_window = ct and ct < end_of_today_utc and (force or now < ct)
                if in_window:
                    upcoming.append(e)
            data["events"] = upcoming
            total_events = len(events or [])
            print(f"  {len(upcoming)} today's games (filtered from {total_events} total)")
            print(f"  Local date: {local_date} MST | Now UTC: {now.strftime('%H:%M')} | Cutoff UTC: {end_of_today_utc.strftime('%Y-%m-%d %H:%M')}")
            if upcoming:
                for ue in upcoming[:5]:
                    ct_str = ue.get("commence_time", "?")
                    ct_dt = parse_commence(ct_str)
                    local_ct = ct_dt.astimezone(CO_TZ).strftime("%I:%M %p %Z") if ct_dt else "?"
                    print(f"    {ue.get('away_team','?')} @ {ue.get('home_team','?')} — {local_ct}")

            if not upcoming:
                all_data[sport] = data
                continue

            # Game lines (bulk — 1 call for all games)
            print(f"\n  Pulling game lines...")
            gl = self._get(f"{ODDS_BASE}/sports/{sk}/odds",
                          {"regions": ODDS_REGIONS, "markets": "spreads,totals,h2h",
                           "oddsFormat": "american"})
            data["game_lines"] = gl or []
            api_calls += 1
            time.sleep(API_SLEEP)

            # Per-event markets — BATCHED into as few calls as possible
            for ev in upcoming:
                eid = ev["id"]
                matchup = f"{ev.get('away_team','?')} @ {ev.get('home_team','?')}"
                print(f"\n  {matchup}")

                # Alt lines (spreads/puck_line/run_line) — sport-specific market name
                alt_market = SPORT_ALT_MARKET.get(sport)
                if fetch_alt_spreads and alt_market:
                    print(f"    {alt_market}...")
                    alts = self._get(f"{ODDS_BASE}/sports/{sk}/events/{eid}/odds",
                                    {"regions": ODDS_REGIONS, "markets": alt_market,
                                     "oddsFormat": "american"})
                    if alts:
                        data["props"][f"{eid}_{alt_market}"] = alts
                    api_calls += 1
                    time.sleep(API_SLEEP)

                # Skip props + team totals in game_lines_only mode
                if game_lines_only:
                    continue

                # BATCH all prop markets + team_totals (+ F5 for MLB) into ONE call
                batch_markets = ["team_totals"] + PROP_MARKETS.get(sport, [])
                if sport == "MLB":
                    batch_markets.extend(["h2h_1st_5_innings", "spreads_1st_5_innings",
                                          "totals_1st_5_innings", "totals_1st_1_innings"])
                markets_str = ",".join(batch_markets)
                print(f"    batched: {len(batch_markets)} markets in 1 call")

                resp = self._get(f"{ODDS_BASE}/sports/{sk}/events/{eid}/odds",
                                {"regions": ODDS_REGIONS, "markets": markets_str,
                                 "oddsFormat": "american"})
                api_calls += 1

                if resp:
                    # Parse the batched response into separate keyed entries
                    # The API returns all markets in one response — we need to split them
                    # into the format the rest of the code expects
                    if isinstance(resp, dict):
                        bms = resp.get("bookmakers", [])
                    elif isinstance(resp, list) and resp:
                        bms = resp[0].get("bookmakers", []) if isinstance(resp[0], dict) else []
                    else:
                        bms = []

                    # Group markets from the response
                    market_data = {}  # market_key → list of bookmaker entries with only that market
                    for bm in bms:
                        book_key = bm.get("key", "")
                        for market in bm.get("markets", []):
                            mk = market.get("key", "")
                            if mk not in market_data:
                                market_data[mk] = []
                            # Build a bookmaker entry with just this one market
                            market_data[mk].append({
                                "key": book_key,
                                "title": bm.get("title", ""),
                                "markets": [market],
                            })

                    # Store each market under the expected key format
                    for mk, bm_entries in market_data.items():
                        if mk == "team_totals":
                            store_key = f"{eid}_team_totals"
                        elif mk in ("h2h_1st_5_innings", "spreads_1st_5_innings", "totals_1st_5_innings"):
                            store_key = f"{eid}_f5_innings"
                        elif mk == "totals_1st_1_innings":
                            store_key = f"{eid}_nrfi"
                        else:
                            store_key = f"{eid}_{mk}"

                        # Build response object matching what individual calls return
                        if store_key in data["props"]:
                            # Merge bookmakers into existing entry (for F5 which has 3 markets)
                            existing = data["props"][store_key]
                            if isinstance(existing, dict):
                                existing.setdefault("bookmakers", [])
                                # Merge: add new markets to existing bookmaker entries
                                existing_books = {b["key"]: b for b in existing["bookmakers"]}
                                for bm_entry in bm_entries:
                                    bk = bm_entry["key"]
                                    if bk in existing_books:
                                        existing_books[bk]["markets"].extend(bm_entry["markets"])
                                    else:
                                        existing["bookmakers"].append(bm_entry)
                        else:
                            data["props"][store_key] = {"bookmakers": bm_entries}

                time.sleep(API_SLEEP)

            all_data[sport] = data

            # Save to cache
            self._save_cache(sport, data)

            print(f"\n  {sport}: {api_calls} API calls total")
            if self.remaining:
                print(f"  API requests remaining: {self.remaining}")

        return all_data

# ============================================================
#  ODDS PARSER — extract best lines from API response
# ============================================================

def extract_player_props(odds_data, sport):
    """
    Parse API odds data into a list of prop opportunities.
    Returns list of dicts: {player, player_key, stat, line, over_odds, under_odds, game, book_over, book_under}
    """
    props = []
    events = odds_data.get("events", [])
    event_map = {e["id"]: e for e in events}

    for key, response in odds_data.get("props", {}).items():
        parts = key.split("_", 1)
        eid = parts[0]
        market_key = parts[1] if len(parts) > 1 else ""

        if market_key == "team_totals":
            continue  # handled separately

        stat = MARKET_TO_STAT.get(market_key, "")
        if not stat:
            continue

        ev = event_map.get(eid, {})
        game = f"{ev.get('away_team','?')} @ {ev.get('home_team','?')}"

        # response is the event odds object or list
        if isinstance(response, dict):
            bookmakers = response.get("bookmakers", [])
        elif isinstance(response, list) and len(response) > 0:
            bookmakers = response[0].get("bookmakers", []) if isinstance(response[0], dict) else []
        else:
            continue

        # Collect best odds per (player, line, direction)
        best = {}  # key: (player, line) -> {over_odds, under_odds, book_over, book_under}

        for bm in bookmakers:
            book = bm.get("key", "")
            # Strip region suffix (e.g. hardrockbet_az → hardrockbet) for CO_LEGAL_BOOKS check
            book_base = book.rsplit("_", 1)[0] if "_" in book else book
            if book_base not in CO_LEGAL_BOOKS and book not in CO_LEGAL_BOOKS:
                continue  # Skip books not available in Colorado
            for market in bm.get("markets", []):
                if market.get("key", "") != market_key:
                    continue
                for outcome in market.get("outcomes", []):
                    player = outcome.get("description", "")
                    line = outcome.get("point")
                    odds = outcome.get("price", 0)
                    name = outcome.get("name", "")  # "Over" or "Under"

                    if not player or line is None or odds == 0:
                        continue
                    if is_decimal_leak(odds):
                        continue

                    pk = (player, line)
                    if pk not in best:
                        best[pk] = {"over_odds": None, "under_odds": None,
                                    "book_over": "", "book_under": ""}

                    if name == "Over":
                        if best[pk]["over_odds"] is None or odds > best[pk]["over_odds"]:
                            best[pk]["over_odds"] = odds
                            best[pk]["book_over"] = book
                    elif name == "Under":
                        if best[pk]["under_odds"] is None or odds > best[pk]["under_odds"]:
                            best[pk]["under_odds"] = odds
                            best[pk]["book_under"] = book

        for (player, line), info in best.items():
            props.append({
                "player": player,
                "player_key": name_key(player),
                "stat": stat,
                "line": float(line),
                "over_odds": info["over_odds"],
                "under_odds": info["under_odds"],
                "book_over": info["book_over"],
                "book_under": info["book_under"],
                "game": game,
                "sport": sport,
                "event_id": eid,
            })

    return props

def extract_game_lines(odds_data, sport):
    """Parse game lines from API response. Only includes upcoming (not started) games."""
    lines = []
    events = odds_data.get("events", [])
    event_map = {e["id"]: e for e in events}
    # Set of upcoming event IDs (already filtered by commence_time in fetch_all)
    upcoming_ids = {e["id"] for e in events}

    for game_data in odds_data.get("game_lines", []):
        # Skip games that have already started (not in upcoming events)
        eid = game_data.get("id", "")
        if eid and upcoming_ids and eid not in upcoming_ids:
            continue
        eid = game_data.get("id", "")
        home = game_data.get("home_team", "")
        away = game_data.get("away_team", "")
        game = f"{away} @ {home}"

        best_spread = {}    # {team: {line, odds, book}}
        best_total = {}     # {direction: {line, odds, book}}
        best_ml = {}        # {team: {odds, book}}

        for bm in game_data.get("bookmakers", []):
            book = bm.get("key", "")
            book_base = book.rsplit("_", 1)[0] if "_" in book else book
            if book_base not in CO_LEGAL_BOOKS and book not in CO_LEGAL_BOOKS:
                continue  # Skip books not available in Colorado
            for market in bm.get("markets", []):
                mk = market.get("key", "")
                for outcome in market.get("outcomes", []):
                    name = outcome.get("name", "")
                    odds = outcome.get("price", 0)
                    point = outcome.get("point")

                    if odds == 0 or is_decimal_leak(odds):
                        continue

                    if mk == "spreads" and point is not None:
                        if name not in best_spread or odds > best_spread[name]["odds"]:
                            best_spread[name] = {"line": point, "odds": odds, "book": book}
                    elif mk == "totals":
                        if name not in best_total or odds > best_total[name]["odds"]:
                            best_total[name] = {"line": point, "odds": odds, "book": book}
                    elif mk == "h2h":
                        if name not in best_ml or odds > best_ml[name]["odds"]:
                            best_ml[name] = {"odds": odds, "book": book}

        lines.append({
            "game": game, "home": home, "away": away,
            "spread": best_spread, "total": best_total, "ml": best_ml,
            "sport": sport, "event_id": eid,
        })

    return lines

def extract_team_totals(odds_data, sport):
    """Parse team totals from API response."""
    results = []
    events = odds_data.get("events", [])
    event_map = {e["id"]: e for e in events}

    for key, response in odds_data.get("props", {}).items():
        if "team_totals" not in key:
            continue

        eid = key.split("_")[0]
        ev = event_map.get(eid, {})
        game = f"{ev.get('away_team','?')} @ {ev.get('home_team','?')}"

        if isinstance(response, dict):
            bookmakers = response.get("bookmakers", [])
        elif isinstance(response, list) and response:
            bookmakers = response[0].get("bookmakers", []) if isinstance(response[0], dict) else []
        else:
            continue

        # (team, point) -> {over_odds, under_odds, book_over, book_under, book_set}
        by_line = {}
        book_counts = {}  # (team, point) -> set of books offering BOTH sides

        for bm in bookmakers:
            book = bm.get("key", "")
            book_base = book.rsplit("_", 1)[0] if "_" in book else book
            if book_base not in CO_LEGAL_BOOKS and book not in CO_LEGAL_BOOKS:
                continue
            for market in bm.get("markets", []):
                for outcome in market.get("outcomes", []):
                    team = outcome.get("description", outcome.get("name", ""))
                    name = outcome.get("name", "")
                    odds = outcome.get("price", 0)
                    point = outcome.get("point")

                    if not team or odds == 0 or point is None or is_decimal_leak(odds):
                        continue

                    direction = "over" if name == "Over" else "under"
                    pk = (team, point)
                    if pk not in by_line:
                        by_line[pk] = {}
                    entry = by_line[pk]

                    odds_key = f"{direction}_odds"
                    book_key = f"book_{direction}"
                    # Keep best odds per direction at this exact point
                    if odds_key not in entry or odds > entry[odds_key]:
                        entry[odds_key] = odds
                        entry[book_key] = book

        # Count how many books offer BOTH sides at each (team, point)
        # Re-scan bookmakers to count matched lines per book
        for bm in bookmakers:
            book = bm.get("key", "")
            book_base = book.rsplit("_", 1)[0] if "_" in book else book
            if book_base not in CO_LEGAL_BOOKS and book not in CO_LEGAL_BOOKS:
                continue
            book_sides = {}  # (team, point) -> set of directions this book offers
            for market in bm.get("markets", []):
                for outcome in market.get("outcomes", []):
                    team = outcome.get("description", outcome.get("name", ""))
                    name = outcome.get("name", "")
                    odds = outcome.get("price", 0)
                    point = outcome.get("point")
                    if not team or odds == 0 or point is None or is_decimal_leak(odds):
                        continue
                    direction = "over" if name == "Over" else "under"
                    pk = (team, point)
                    book_sides.setdefault(pk, set()).add(direction)
            for pk, sides in book_sides.items():
                if "over" in sides and "under" in sides:
                    book_counts.setdefault(pk, set()).add(book)

        # For each team, pick the point offered by the most books (= main line)
        # Require both over and under to exist at that point
        teams_seen = set(team for (team, _) in by_line)
        for team in teams_seen:
            candidates = []
            for (t, point), entry in by_line.items():
                if t != team:
                    continue
                if "over_odds" not in entry or "under_odds" not in entry:
                    continue
                n_books = len(book_counts.get((team, point), set()))
                candidates.append((n_books, point, entry))

            if not candidates:
                continue

            # Most books = main line; break ties by picking most-negative under odds
            candidates.sort(key=lambda x: (-x[0], x[2].get("under_odds", 0)))
            _, point, entry = candidates[0]

            results.append({
                "team": team, "game": game, "sport": sport,
                "line": point,
                "over_odds": entry["over_odds"], "under_odds": entry["under_odds"],
                "book_over": entry.get("book_over", ""), "book_under": entry.get("book_under", ""),
                "home_team": ev.get("home_team", ""),
            })

    return results


def extract_alt_spreads(odds_data, sport):
    """Parse alternate spreads from API response.
    Returns list of dicts: [{"team", "line", "odds", "book"}, ...]
    Keeps ALL book prices so parlay builder can group by book.
    """
    alt_lines = []
    events = odds_data.get("events", [])

    for key, response in odds_data.get("props", {}).items():
        if not any(m in key for m in ("alternate_spreads", "alternate_puck_line", "alternate_run_line")):
            continue

        if isinstance(response, dict):
            bookmakers = response.get("bookmakers", [])
        elif isinstance(response, list) and response:
            bookmakers = response[0].get("bookmakers", []) if isinstance(response[0], dict) else []
        else:
            continue

        for bm in bookmakers:
            book = bm.get("key", "")
            book_base = book.rsplit("_", 1)[0] if "_" in book else book
            if book_base not in CO_LEGAL_BOOKS and book not in CO_LEGAL_BOOKS:
                continue
            for market in bm.get("markets", []):
                for outcome in market.get("outcomes", []):
                    team = outcome.get("name", "")
                    odds = outcome.get("price", 0)
                    point = outcome.get("point")

                    if not team or odds == 0 or point is None or is_decimal_leak(odds):
                        continue

                    alt_lines.append({
                        "team": team, "line": point,
                        "odds": odds, "book": book,
                    })

    return alt_lines


# ============================================================
#  PLAYER MATCHING
# ============================================================

def match_props_to_projections(props, players):
    """Match API player props to SaberSim projections."""
    player_map = {p["name_key"]: p for p in players}

    matched = []
    for prop in props:
        pk = prop["player_key"]
        if pk in player_map:
            proj_player = player_map[pk]
            proj_val = proj_player.get(prop["stat"], 0)
            if proj_val > 0:
                prop["proj"] = proj_val
                prop["proj_player"] = proj_player
                matched.append(prop)

    return matched

# ============================================================
#  MAIN PIPELINE
# ============================================================

def evaluate_props(matched_props, mode="Default", cooldown_players=None):
    """Run the full prop evaluation pipeline. Returns list of qualified picks."""
    picks = []

    for prop in matched_props:
        stat = prop["stat"]
        proj = prop["proj"]
        line = prop["line"]
        over_odds = prop.get("over_odds")
        under_odds = prop.get("under_odds")

        if proj <= 0:
            continue

        # Need both sides for no-vig
        if over_odds is None or under_odds is None:
            continue

        # Calculate probabilities
        over_p, under_p = calc_prop_prob(proj, line, stat)

        # Calculate edges
        over_edge, under_edge, nv_over, nv_under = calc_edge(over_p, over_odds, under_odds)

        # Evaluate both directions
        for direction in ("over", "under"):
            if direction == "over":
                win_prob = over_p
                raw_edge = over_edge
                odds = over_odds
                nv_prob = nv_over
                book = prop.get("book_over", "")
            else:
                win_prob = under_p
                raw_edge = under_edge
                odds = under_odds
                nv_prob = nv_under
                book = prop.get("book_under", "")

            if odds is None or odds == 0:
                continue

            # I6: Confidence modifier — penalizes early-season or low-sample players
            # Uses games played (GP) if available from CSV, else defaults to 1.0
            proj_player = prop.get("proj_player", {})
            gp = proj_player.get("GP", proj_player.get("gp", 0))
            if gp and int(gp) < 10:
                conf = 0.70  # Very early season — heavy penalty
            elif gp and int(gp) < 20:
                conf = 0.85  # Early season — moderate penalty
            else:
                conf = 1.0   # Full confidence (20+ games or GP not available)
            adj_edge = raw_edge * conf

            # Get tier
            tier = get_tier(stat, direction)
            if tier is None:
                continue  # banned (REB overs)

            # Get team abbreviation from CSV match
            csv_team = prop.get("proj_player", {}).get("team", "")

            pick = {
                "player": prop["player"],
                "team_abbrev": csv_team.upper() if csv_team else get_team_abbrev(prop.get("game", "")),
                "stat": stat,
                "line": line,
                "direction": direction,
                "proj": proj,
                "win_prob": win_prob,
                "raw_edge": raw_edge,
                "adj_edge": adj_edge,
                "conf": conf,
                "odds": odds,
                "nv_prob": nv_prob,
                "book": book,
                "game": prop.get("game", ""),
                "sport": prop.get("sport", ""),
                "tier": tier,
                "pick_type": "prop",
                "missing_side": False,
            }

            # Apply gates
            passed, gate = check_prop_gates(pick)
            pick["gate_result"] = "PASS" if passed else gate

            if not passed:
                pick["size"] = 0
                picks.append(pick)  # keep for sanity table
                continue

            # Check tier minimum edge
            if adj_edge < get_tier_min_edge(tier):
                pick["gate_result"] = f"TIER_MIN({tier})"
                pick["size"] = 0
                picks.append(pick)
                continue

            pick["pick_score"] = pick_score(win_prob, adj_edge, mode)
            picks.append(pick)

    return picks

def evaluate_game_lines(game_lines, team_totals, players, sport, mode="Default"):
    """Evaluate game lines (totals, spreads, MLs, team totals)."""
    picks = []
    sigmas = GAME_SIGMA.get(sport, GAME_SIGMA["NBA"])

    # Build team projection map
    team_proj = {}
    for p in players:
        team = p["team"].upper()
        if team not in team_proj:
            team_proj[team] = {"saber_total": p["saber_total"], "saber_team": p["saber_team"]}

    # --- TOTALS ---
    for gl in game_lines:
        total_info = gl.get("total", {})
        over_info = total_info.get("Over", {})
        under_info = total_info.get("Under", {})

        if not over_info or not under_info:
            continue

        line = over_info.get("line")
        if line is None:
            continue

        # Match projection to THIS game's teams (not first random team)
        home_name = gl["home"].upper()
        away_name = gl["away"].upper()

        proj = None
        # Try to find saber_total from players on either team in this game
        for tk, tv in team_proj.items():
            if tv["saber_total"] > 0:
                # Check if this team key matches home or away
                if (tk in home_name or home_name in tk or
                    tk in away_name or away_name in tk or
                    any(w in tk for w in home_name.split()[-1:]) or
                    any(w in tk for w in away_name.split()[-1:])):
                    proj = tv["saber_total"]
                    break
        if proj is None or proj <= 0:
            continue

        # Blend SaberSim total with market line
        proj = line + BLEND_ALPHA * (proj - line)

        sigma = sigmas["total"]
        over_p = 1.0 - normal_cdf(line, proj, sigma)
        under_p = normal_cdf(line, proj, sigma)

        over_odds = over_info["odds"]
        under_odds = under_info["odds"]

        if is_decimal_leak(over_odds) or is_decimal_leak(under_odds):
            continue

        over_edge, under_edge, nv_over, nv_under = calc_edge(over_p, over_odds, under_odds)

        for direction in ("over", "under"):
            wp = over_p if direction == "over" else under_p
            edge = over_edge if direction == "over" else under_edge
            odds = over_odds if direction == "over" else under_odds
            nv = nv_over if direction == "over" else nv_under
            book = over_info.get("book", "") if direction == "over" else under_info.get("book", "")

            # Build matchup abbreviation for game total display
            game_str = gl.get("game", "")
            matchup_parts = []
            for full_name, abbr in TEAM_ABBREV.items():
                if full_name in game_str.lower():
                    matchup_parts.append(abbr)
            matchup_abbrev = "/".join(matchup_parts[:2]) if matchup_parts else ""

            pick = {
                "player": f"Game Total", "team_abbrev": matchup_abbrev,
                "stat": "TOTAL", "line": line, "direction": direction,
                "proj": proj, "win_prob": wp,
                "raw_edge": edge, "adj_edge": edge, "conf": 1.0,
                "odds": odds, "nv_prob": nv, "book": book,
                "game": gl["game"], "sport": sport,
                "tier": "T2", "pick_type": "game_line",
                "sigma": sigma, "missing_side": False,
            }

            passed, gate = check_game_gates(pick)
            pick["gate_result"] = "PASS" if passed else gate
            if passed and edge >= 0.05:
                pick["pick_score"] = pick_score(wp, edge, mode)
            else:
                pick["size"] = 0
            picks.append(pick)

    # --- SPREADS ---
    for gl in game_lines:
        spread_data = gl.get("spread", {})
        if len(spread_data) < 2:
            continue  # need both sides

        home_name = gl["home"]
        away_name = gl["away"]

        home_proj = find_team_proj(home_name, team_proj, "saber_team")
        away_proj = find_team_proj(away_name, team_proj, "saber_team")

        if home_proj is None or away_proj is None:
            continue

        raw_margin = home_proj - away_proj  # positive = home favored
        sigma = sigmas["spread"]

        # Derive market-implied margin from the spread data (home team perspective)
        # Home team's spread line: negative = home favored, so market_margin = -home_line
        home_spread_line = None
        for sn, si in spread_data.items():
            sn_abbr = resolve_team_abbrev(sn)
            home_abbr_check = resolve_team_abbrev(gl["home"])
            if sn_abbr and home_abbr_check and sn_abbr == home_abbr_check:
                home_spread_line = si["line"]
                break
            elif sn.lower() in gl["home"].lower() or gl["home"].lower() in sn.lower():
                home_spread_line = si["line"]
                break

        if home_spread_line is not None:
            market_margin = -home_spread_line  # if home is -5.5, market says home by 5.5
            proj_margin = market_margin + BLEND_ALPHA * (raw_margin - market_margin)
        else:
            proj_margin = raw_margin

        # Process each team's spread line
        for team_name, sp_info in spread_data.items():
            sp_line = sp_info["line"]       # e.g., -5.5 for fav, +5.5 for dog
            sp_odds = sp_info["odds"]
            sp_book = sp_info.get("book", "")

            if is_decimal_leak(sp_odds):
                continue

            # Margin from THIS team's perspective
            team_abbr_resolved = resolve_team_abbrev(team_name)
            home_abbr_resolved = resolve_team_abbrev(home_name)
            is_home = (team_abbr_resolved == home_abbr_resolved) if team_abbr_resolved and home_abbr_resolved else (
                team_name.lower() in home_name.lower() or home_name.lower() in team_name.lower()
            )
            team_margin = proj_margin if is_home else -proj_margin

            # Cover probability: team covers if actual_margin > -line
            cover_prob = 1.0 - normal_cdf(-sp_line, team_margin, sigma)

            # Get opposing side odds for no-vig calculation
            opp_name = [n for n in spread_data if n != team_name]
            if not opp_name:
                continue
            opp_odds = spread_data[opp_name[0]]["odds"]
            if is_decimal_leak(opp_odds):
                continue

            imp_this = implied_prob(sp_odds)
            imp_opp = implied_prob(opp_odds)
            nv_this, nv_opp = no_vig(imp_this, imp_opp)
            edge = cover_prob - nv_this

            # Team abbreviations
            home_abbr = TEAM_ABBREV.get(home_name.lower(), home_name[:3].upper())
            away_abbr = TEAM_ABBREV.get(away_name.lower(), away_name[:3].upper())
            team_abbr = home_abbr if is_home else away_abbr
            matchup_abbrev = f"{away_abbr}/{home_abbr}"

            sign = "+" if sp_line > 0 else ""
            pick = {
                "player": f"{team_abbr} {sign}{sp_line}",
                "team_abbrev": matchup_abbrev,
                "stat": "SPREAD", "line": sp_line, "direction": "cover",
                "proj": team_margin, "win_prob": cover_prob,
                "raw_edge": edge, "adj_edge": edge, "conf": 1.0,
                "odds": sp_odds, "nv_prob": nv_this, "book": sp_book,
                "game": gl["game"], "sport": sport,
                "tier": "T2", "pick_type": "game_line",
                "sigma": sigma, "missing_side": False,
                "is_home": is_home,  # BUG G1 fix: used by grade_picks for correct team id
            }

            passed, gate = check_game_gates(pick)
            pick["gate_result"] = "PASS" if passed else gate
            if passed and edge >= 0.05:
                pick["pick_score"] = pick_score(cover_prob, edge, mode)
            else:
                pick["size"] = 0
            picks.append(pick)

    # --- MONEYLINES ---
    for gl in game_lines:
        ml_data = gl.get("ml", {})
        if len(ml_data) < 2:
            continue

        home_name = gl["home"]
        away_name = gl["away"]

        home_proj = find_team_proj(home_name, team_proj, "saber_team")
        away_proj = find_team_proj(away_name, team_proj, "saber_team")

        if home_proj is None or away_proj is None:
            continue

        raw_margin = home_proj - away_proj
        sigma = sigmas["ml"]  # FIX: ML uses ml sigma (wider) not spread sigma — spread sigma inflates win probs

        # Blend with market-implied margin from spread data (same approach as SPREADS)
        spread_data = gl.get("spread", {})
        home_spread_line = None
        for sn, si in spread_data.items():
            sn_abbr = resolve_team_abbrev(sn)
            home_abbr_check = resolve_team_abbrev(home_name)
            if sn_abbr and home_abbr_check and sn_abbr == home_abbr_check:
                home_spread_line = si["line"]
                break
            elif sn.lower() in home_name.lower() or home_name.lower() in sn.lower():
                home_spread_line = si["line"]
                break

        if home_spread_line is not None:
            market_margin = -home_spread_line
            proj_margin = market_margin + BLEND_ALPHA * (raw_margin - market_margin)
        else:
            proj_margin = raw_margin

        for team_name, ml_info in ml_data.items():
            ml_odds = ml_info["odds"]
            ml_book = ml_info.get("book", "")

            if is_decimal_leak(ml_odds):
                continue

            team_abbr_resolved = resolve_team_abbrev(team_name)
            home_abbr_resolved = resolve_team_abbrev(home_name)
            is_home = (team_abbr_resolved == home_abbr_resolved) if team_abbr_resolved and home_abbr_resolved else (
                team_name.lower() in home_name.lower() or home_name.lower() in team_name.lower()
            )
            team_margin = proj_margin if is_home else -proj_margin

            # Win probability: team wins if actual_margin > 0
            win_prob = 1.0 - normal_cdf(0, team_margin, sigma)

            # No-vig
            opp_name = [n for n in ml_data if n != team_name]
            if not opp_name:
                continue
            opp_odds = ml_data[opp_name[0]]["odds"]
            if is_decimal_leak(opp_odds):
                continue

            imp_this = implied_prob(ml_odds)
            imp_opp = implied_prob(opp_odds)
            nv_this, nv_opp = no_vig(imp_this, imp_opp)
            edge = win_prob - nv_this

            # Classify as favorite or dog based on odds
            is_fav = ml_odds < 0
            stat_type = "ML_FAV" if is_fav else "ML_DOG"
            tier = "T2" if is_fav else "T3"
            min_edge = 0.05 if is_fav else 0.06

            home_abbr = TEAM_ABBREV.get(home_name.lower(), home_name[:3].upper())
            away_abbr = TEAM_ABBREV.get(away_name.lower(), away_name[:3].upper())
            team_abbr = home_abbr if is_home else away_abbr
            matchup_abbrev = f"{away_abbr}/{home_abbr}"

            pick = {
                "player": f"{team_abbr} ML",
                "team_abbrev": matchup_abbrev,
                "stat": stat_type, "line": 0, "direction": "win",
                "proj": team_margin, "win_prob": win_prob,
                "raw_edge": edge, "adj_edge": edge, "conf": 1.0,
                "odds": ml_odds, "nv_prob": nv_this, "book": ml_book,
                "game": gl["game"], "sport": sport,
                "tier": tier, "pick_type": "game_line",
                "sigma": sigma, "missing_side": False,
                "is_home": is_home,  # BUG G2 fix: used by grade_picks for correct team id
            }

            passed, gate = check_game_gates(pick)
            pick["gate_result"] = "PASS" if passed else gate
            if passed and edge >= min_edge:
                pick["pick_score"] = pick_score(win_prob, edge, mode)
            else:
                pick["size"] = 0
            picks.append(pick)

    # --- TEAM TOTALS ---
    for tt in team_totals:
        line = tt["line"]
        team = tt["team"]
        sigma = sigmas["team"]

        # Find team projection
        proj = None
        for tk, tv in team_proj.items():
            if tk in team.upper() or team.upper() in tk:
                proj = tv["saber_team"]
                break
        if proj is None or proj <= 0:
            continue

        over_p = 1.0 - normal_cdf(line, proj, sigma)
        under_p = normal_cdf(line, proj, sigma)

        over_odds = tt["over_odds"]
        under_odds = tt["under_odds"]

        if is_decimal_leak(over_odds) or is_decimal_leak(under_odds):
            continue

        over_edge, under_edge, nv_over, nv_under = calc_edge(over_p, over_odds, under_odds)

        # Determine home/away for TEAM_TOTAL (BUG G fix — was always missing is_home)
        home_team_name = tt.get("home_team", "")
        if home_team_name:
            tt_home_abbr = resolve_team_abbrev(home_team_name)
            tt_team_abbr = resolve_team_abbrev(team)
            tt_is_home = (tt_team_abbr == tt_home_abbr) if (tt_team_abbr and tt_home_abbr) else (
                team.lower() in home_team_name.lower() or home_team_name.lower() in team.lower()
            )
        else:
            # Fallback: parse game string "AWAY @ HOME"
            parts = tt.get("game", "").split(" @ ")
            tt_is_home = (len(parts) == 2 and (
                team.lower() in parts[1].lower() or parts[1].lower() in team.lower()
            ))

        for direction in ("over", "under"):
            wp = over_p if direction == "over" else under_p
            edge = over_edge if direction == "over" else under_edge
            odds = over_odds if direction == "over" else under_odds
            nv = nv_over if direction == "over" else nv_under
            book = tt.get("book_over", "") if direction == "over" else tt.get("book_under", "")

            pick = {
                "player": f"{team} Team Total",
                "team_abbrev": get_team_abbrev("", team) if team else "",
                "stat": "TEAM_TOTAL", "line": line, "direction": direction,
                "proj": proj, "win_prob": wp,
                "raw_edge": edge, "adj_edge": edge, "conf": 1.0,
                "odds": odds, "nv_prob": nv, "book": book,
                "game": tt["game"], "sport": sport,
                "tier": "T2", "pick_type": "game_line",
                "sigma": sigma, "missing_side": False,
                "is_home": tt_is_home,  # BUG G fix: used by grade_picks for correct team score
            }

            passed, gate = check_game_gates(pick)
            pick["gate_result"] = "PASS" if passed else gate
            if passed and edge >= 0.05:
                pick["pick_score"] = pick_score(wp, edge, mode)
            else:
                pick["size"] = 0
            picks.append(pick)

    return picks

# Golf outright evaluation removed — see archived_golf_code.py

def extract_f5_lines(odds_data, sport):
    """Extract First 5 innings lines from MLB API response."""
    if sport != "MLB":
        return []
    f5_lines = []
    events = odds_data.get("events", [])
    event_map = {e["id"]: e for e in events}

    for key, response in odds_data.get("props", {}).items():
        if "f5_innings" not in key:
            continue
        parts = key.split("_", 1)
        eid = parts[0]
        ev = event_map.get(eid, {})
        game = f"{ev.get('away_team','?')} @ {ev.get('home_team','?')}"
        home = ev.get("home_team", "")
        away = ev.get("away_team", "")

        if isinstance(response, dict):
            bookmakers = response.get("bookmakers", [])
        elif isinstance(response, list) and len(response) > 0:
            bookmakers = response[0].get("bookmakers", []) if isinstance(response[0], dict) else []
        else:
            continue

        f5_data = {"game": game, "home": home, "away": away, "sport": sport, "event_id": eid}

        # Parse each F5 market type
        for bm in bookmakers:
            book = bm.get("key", "")
            book_base = book.rsplit("_", 1)[0] if "_" in book else book
            if book_base not in CO_LEGAL_BOOKS and book not in CO_LEGAL_BOOKS:
                continue
            for market in bm.get("markets", []):
                mk = market.get("key", "")
                for outcome in market.get("outcomes", []):
                    name = outcome.get("name", "")
                    odds = outcome.get("price", 0)
                    point = outcome.get("point")
                    if odds == 0 or is_decimal_leak(odds):
                        continue

                    if mk == "totals_1st_5_innings":
                        if name == "Over" and point is not None:
                            f5_data.setdefault("total", {})
                            if "Over" not in f5_data["total"] or odds > f5_data["total"]["Over"].get("odds", -9999):
                                f5_data["total"]["Over"] = {"odds": odds, "line": point, "book": book}
                        elif name == "Under" and point is not None:
                            f5_data.setdefault("total", {})
                            if "Under" not in f5_data["total"] or odds > f5_data["total"]["Under"].get("odds", -9999):
                                f5_data["total"]["Under"] = {"odds": odds, "line": point, "book": book}
                    elif mk == "h2h_1st_5_innings":
                        f5_data.setdefault("ml", {})
                        if name not in f5_data["ml"] or odds > f5_data["ml"].get(name, {}).get("odds", -9999):
                            f5_data["ml"][name] = {"odds": odds, "book": book, "team": name}
                    elif mk == "spreads_1st_5_innings":
                        if point is not None:
                            f5_data.setdefault("spread", {})
                            if name not in f5_data["spread"] or odds > f5_data["spread"].get(name, {}).get("odds", -9999):
                                f5_data["spread"][name] = {"odds": odds, "line": point, "book": book, "team": name}

        if any(k in f5_data for k in ("total", "ml", "spread")):
            f5_lines.append(f5_data)

    return f5_lines

def evaluate_f5_lines(f5_lines, players, mode="Default"):
    """Evaluate First 5 innings lines for MLB."""
    picks = []
    sigmas = F5_SIGMA

    # Build team projection map
    team_proj = {}
    for p in players:
        team = p["team"].upper()
        if team not in team_proj:
            team_proj[team] = {"saber_total": p["saber_total"], "saber_team": p["saber_team"]}

    for f5 in f5_lines:
        game = f5["game"]
        home = f5["home"]
        away = f5["away"]

        # Build matchup abbreviation
        matchup_parts = []
        for full_name, abbr in TEAM_ABBREV.items():
            if full_name in game.lower():
                matchup_parts.append(abbr)
        matchup_abbrev = "/".join(matchup_parts[:2]) if matchup_parts else ""

        # F5 Total — project as ~53% of full game total
        if "total" in f5:
            over_info = f5["total"].get("Over", {})
            under_info = f5["total"].get("Under", {})
            if over_info and under_info:
                line = over_info.get("line")
                if line is not None:
                    # Find game total projection and scale to F5
                    game_total_proj = None
                    for tk, tv in team_proj.items():
                        if tv["saber_total"] > 0:
                            if (tk in home.upper() or home.upper() in tk or
                                tk in away.upper() or away.upper() in tk or
                                any(w in tk for w in home.upper().split()[-1:]) or
                                any(w in tk for w in away.upper().split()[-1:])):
                                game_total_proj = tv["saber_total"]
                                break
                    if game_total_proj and game_total_proj > 0:
                        proj = game_total_proj * 0.51  # F5 is ~51% of full game (2024 data: 4.41/8.76)
                        # FIX: Anchor F5 projection to market line (same as full-game BLEND_ALPHA)
                        proj = line + BLEND_ALPHA * (proj - line)
                        sigma = sigmas["total"]
                        over_p = 1.0 - normal_cdf(line, proj, sigma)
                        under_p = normal_cdf(line, proj, sigma)
                        over_odds = over_info["odds"]
                        under_odds = under_info["odds"]

                        if not is_decimal_leak(over_odds) and not is_decimal_leak(under_odds):
                            over_edge, under_edge, nv_over, nv_under = calc_edge(over_p, over_odds, under_odds)
                            for direction in ("over", "under"):
                                wp = over_p if direction == "over" else under_p
                                edge = over_edge if direction == "over" else under_edge
                                odds = over_odds if direction == "over" else under_odds
                                nv = nv_over if direction == "over" else nv_under
                                book = over_info.get("book", "") if direction == "over" else under_info.get("book", "")

                                pick = {
                                    "player": "F5 Total", "team_abbrev": matchup_abbrev,
                                    "stat": "F5_TOTAL", "line": line, "direction": direction,
                                    "proj": proj, "win_prob": wp,
                                    "raw_edge": edge, "adj_edge": edge, "conf": 1.0,
                                    "odds": odds, "nv_prob": nv, "book": book,
                                    "game": game, "sport": "MLB",
                                    "tier": "T2", "pick_type": "game_line",
                                    "sigma": sigma, "missing_side": False,
                                }
                                passed, gate = check_game_gates(pick)
                                pick["gate_result"] = "PASS" if passed else gate
                                if passed and edge >= 0.05:
                                    pick["pick_score"] = pick_score(wp, edge, mode)
                                else:
                                    pick["size"] = 0
                                picks.append(pick)

        # F5 ML
        if "ml" in f5:
            ml_data = f5["ml"]
            if len(ml_data) >= 2:
                teams = list(ml_data.keys())
                team1, team2 = teams[0], teams[1]
                odds1 = ml_data[team1]["odds"]
                odds2 = ml_data[team2]["odds"]

                if not is_decimal_leak(odds1) and not is_decimal_leak(odds2):
                    # Derive F5 ML probability from team total projections
                    t1_proj, t2_proj = None, None
                    for tk, tv in team_proj.items():
                        if tk in team1.upper() or team1.upper() in tk or any(w in tk for w in team1.upper().split()[-1:]):
                            t1_proj = tv["saber_team"]
                        if tk in team2.upper() or team2.upper() in tk or any(w in tk for w in team2.upper().split()[-1:]):
                            t2_proj = tv["saber_team"]

                    if t1_proj and t2_proj and t1_proj > 0 and t2_proj > 0:
                        # F5 team runs scaled
                        f5_t1 = t1_proj * 0.54
                        f5_t2 = t2_proj * 0.54
                        margin = f5_t1 - f5_t2
                        sigma = sigmas["spread"]
                        t1_wp = 1.0 - normal_cdf(0, margin, sigma)
                        t2_wp = normal_cdf(0, margin, sigma)

                        nv1, nv2 = no_vig(implied_prob(odds1), implied_prob(odds2))
                        edge1 = t1_wp - nv1
                        edge2 = t2_wp - nv2

                        for team_name, wp, edge, odds, nv, book_key in [
                            (team1, t1_wp, edge1, odds1, nv1, ml_data[team1].get("book", "")),
                            (team2, t2_wp, edge2, odds2, nv2, ml_data[team2].get("book", "")),
                        ]:
                            # FIX 3: Mirror full-game ML — favs T2 (5% min edge), dogs T3 (6% min edge)
                            is_fav = odds < 0
                            stat = "F5_ML"
                            tier = "T2" if is_fav else "T3"
                            min_edge = 0.05 if is_fav else 0.06
                            # BUG G3 fix: determine home/away using resolved abbrevs
                            t_abbr = resolve_team_abbrev(team_name)
                            h_abbr = resolve_team_abbrev(home)
                            f5_is_home = (t_abbr == h_abbr) if (t_abbr and h_abbr) else (
                                team_name.lower() in home.lower() or home.lower() in team_name.lower()
                            )
                            pick = {
                                "player": f"F5 ML {team_name}", "team_abbrev": get_team_abbrev("", team_name),
                                "stat": stat, "line": 0, "direction": "over",
                                "proj": f5_t1 if team_name == team1 else f5_t2,
                                "win_prob": wp,
                                "raw_edge": edge, "adj_edge": edge, "conf": 1.0,
                                "odds": odds, "nv_prob": nv, "book": book_key,
                                "game": game, "sport": "MLB",
                                "tier": tier, "pick_type": "game_line",
                                "sigma": sigma, "missing_side": False,
                                "is_home": f5_is_home,  # BUG G3 fix: used by grade_picks
                            }
                            passed, gate = check_game_gates(pick)
                            pick["gate_result"] = "PASS" if passed else gate
                            if passed and edge >= min_edge:
                                pick["pick_score"] = pick_score(wp, edge, mode)
                            else:
                                pick["size"] = 0
                            picks.append(pick)

        # F5 Spread
        if "spread" in f5:
            sp_data = f5["spread"]
            if len(sp_data) >= 2:
                teams = list(sp_data.keys())
                for team_name in teams:
                    sp_info = sp_data[team_name]
                    sp_line = sp_info.get("line", 0)
                    sp_odds = sp_info.get("odds", 0)
                    if sp_odds == 0 or is_decimal_leak(sp_odds):
                        continue

                    # Find other side for no-vig
                    other_team = [t for t in teams if t != team_name]
                    if not other_team:
                        continue
                    other_odds = sp_data[other_team[0]].get("odds", 0)
                    if other_odds == 0 or is_decimal_leak(other_odds):
                        continue

                    # Project F5 margin
                    t_proj = None
                    for tk, tv in team_proj.items():
                        if tk in team_name.upper() or team_name.upper() in tk or any(w in tk for w in team_name.upper().split()[-1:]):
                            t_proj = tv["saber_team"]
                    o_proj = None
                    for tk, tv in team_proj.items():
                        if tk in other_team[0].upper() or other_team[0].upper() in tk or any(w in tk for w in other_team[0].upper().split()[-1:]):
                            o_proj = tv["saber_team"]

                    if t_proj and o_proj:
                        raw_f5_margin = (t_proj - o_proj) * 0.51  # FIX: 51% scaling (2024 data)
                        # FIX: Anchor F5 margin to market-implied margin (same BLEND_ALPHA as full-game)
                        market_f5_margin = -sp_line  # sp_line is from team perspective: negative = fav
                        f5_margin = market_f5_margin + BLEND_ALPHA * (raw_f5_margin - market_f5_margin)
                        sigma = sigmas["spread"]
                        cover_p = 1.0 - normal_cdf(-sp_line, f5_margin, sigma)

                        nv_cover, nv_other = no_vig(implied_prob(sp_odds), implied_prob(other_odds))
                        edge = cover_p - nv_cover

                        # BUG G3 fix: determine home/away using resolved abbrevs
                        t_abbr = resolve_team_abbrev(team_name)
                        h_abbr = resolve_team_abbrev(home)
                        f5_is_home = (t_abbr == h_abbr) if (t_abbr and h_abbr) else (
                            team_name.lower() in home.lower() or home.lower() in team_name.lower()
                        )
                        pick = {
                            "player": f"F5 {team_name}", "team_abbrev": get_team_abbrev("", team_name),
                            "stat": "F5_SPREAD", "line": sp_line, "direction": "over",
                            "proj": f5_margin, "win_prob": cover_p,
                            "raw_edge": edge, "adj_edge": edge, "conf": 1.0,
                            "odds": sp_odds, "nv_prob": nv_cover, "book": sp_info.get("book", ""),
                            "game": game, "sport": "MLB",
                            "tier": "T2", "pick_type": "game_line",
                            "sigma": sigma, "missing_side": False,
                            "is_home": f5_is_home,  # BUG G3 fix: used by grade_picks
                        }
                        passed, gate = check_game_gates(pick)
                        pick["gate_result"] = "PASS" if passed else gate
                        if passed and edge >= 0.05:
                            pick["pick_score"] = pick_score(cover_p, edge, mode)
                        else:
                            pick["size"] = 0
                        picks.append(pick)

    return picks

def evaluate_nrfi(game_lines, players, odds_data, sport, mode="Default"):
    """Evaluate NRFI/YRFI for MLB games using totals_1st_1_innings market.
    NRFI = Under 0.5 on 1st inning total.  YRFI = Over 0.5.
    P(NRFI) = P(away scores 0 in 1st) × P(home scores 0 in 1st)
    Base rate: ~70% NRFI league-wide (~16.3% scoring prob per team per 1st inning)
    Adjust per team based on pitcher ER rate + opposing team quality.
    """
    if sport != "MLB":
        return []

    picks = []
    BASE_SCORING_RATE = 0.163  # League avg per-team 1st inning scoring rate

    # Build pitcher and team maps
    pitcher_map = {}  # team → pitcher stats
    # R9: team_quality removed — SaberSim saber_team already prices in the matchup/starter,
    # so multiplying by opponent offensive quality was double-counting that signal.
    for p in players:
        team = p["team"].upper()
        if p.get("is_pitcher") and p.get("status") == "confirmed":  # R10: use confirmed starter
            ip = p.get("IP", 1)
            er_per_ip = p.get("ER", 0) / ip
            # I4: Compute projected FIP for more stable pitcher quality estimate
            # FIP = ((13*HR + 3*BB - 2*K) / IP) + 3.20 (FIP constant ~3.20)
            hr = p.get("HR", 0)  # R4: HR allowed — now correctly stored for pitchers in parse_csv
            bb = p.get("BB", 0)
            k_val = p.get("K", 0)
            fip_raw = ((13 * hr + 3 * bb - 2 * k_val) / ip) + 3.20 if ip > 0 else 4.50
            # Blend ERA proxy and FIP: 60% FIP, 40% ERA (FIP is more stable)
            fip_per_ip = fip_raw / 9.0  # Convert FIP (per 9) to per-inning rate
            blended_rate = 0.40 * er_per_ip + 0.60 * fip_per_ip
            pitcher_map[team] = {
                "er_per_ip": er_per_ip, "fip_per_ip": fip_per_ip,
                "blended_rate": blended_rate,
                "name": p["name"], "K": k_val, "IP": ip,
            }

    # Extract NRFI odds from the _nrfi keyed entries (totals_1st_1_innings)
    events = odds_data.get("events", [])
    event_map = {e["id"]: e for e in events}
    nrfi_odds_map = {}  # event_id → {over: {odds, book}, under: {odds, book}}

    for key, response in odds_data.get("props", {}).items():
        if "_nrfi" not in key:
            continue
        eid = key.split("_", 1)[0]

        if isinstance(response, dict):
            bookmakers = response.get("bookmakers", [])
        elif isinstance(response, list) and response:
            bookmakers = response[0].get("bookmakers", []) if isinstance(response[0], dict) else []
        else:
            continue

        best = {"over": None, "under": None}
        for bm in bookmakers:
            book = bm.get("key", "")
            book_base = book.rsplit("_", 1)[0] if "_" in book else book
            if book_base not in CO_LEGAL_BOOKS and book not in CO_LEGAL_BOOKS:
                continue
            for market in bm.get("markets", []):
                for outcome in market.get("outcomes", []):
                    name = outcome.get("name", "").lower()
                    odds = outcome.get("price", 0)
                    if odds == 0 or is_decimal_leak(odds):
                        continue
                    if name == "over" and (not best["over"] or odds > best["over"]["odds"]):
                        best["over"] = {"odds": odds, "book": book}
                    elif name == "under" and (not best["under"] or odds > best["under"]["odds"]):
                        best["under"] = {"odds": odds, "book": book}

        if best["over"] or best["under"]:
            nrfi_odds_map[eid] = best

    for gl in game_lines:
        if gl.get("sport", "").upper() != "MLB":
            continue

        home = gl["home"]
        away = gl["away"]
        game = gl.get("game", f"{away} @ {home}")
        event_id = gl.get("event_id", "")

        # Find pitcher for each side
        home_pitcher = None
        away_pitcher = None

        for tk in pitcher_map:
            if tk in home.upper() or home.upper() in tk or any(w in tk for w in home.upper().split()[-1:]):
                home_pitcher = pitcher_map[tk]
            if tk in away.upper() or away.upper() in tk or any(w in tk for w in away.upper().split()[-1:]):
                away_pitcher = pitcher_map[tk]

        if not home_pitcher or not away_pitcher:
            continue

        # Adjust scoring rate per team (I4: use blended ERA/FIP rate for stability)
        # R9: team_quality multiplier removed — SaberSim saber_team already bakes in the matchup
        avg_er_per_ip = 0.46  # R2: 2025 MLB ERA ≈ 4.16 → 4.16/9 = 0.462
        home_pitch_factor = home_pitcher.get("blended_rate", home_pitcher["er_per_ip"]) / avg_er_per_ip
        away_pitch_factor = away_pitcher.get("blended_rate", away_pitcher["er_per_ip"]) / avg_er_per_ip

        # Away bats vs HOME pitcher, home bats vs AWAY pitcher
        p_away_scores = min(0.45, max(0.05, BASE_SCORING_RATE * home_pitch_factor))
        p_home_scores = min(0.45, max(0.05, BASE_SCORING_RATE * away_pitch_factor))

        p_nrfi = (1.0 - p_away_scores) * (1.0 - p_home_scores)
        p_yrfi = 1.0 - p_nrfi

        # Build matchup abbreviation
        matchup_parts = []
        for full_name, abbr in TEAM_ABBREV.items():
            if full_name in game.lower():
                matchup_parts.append(abbr)
        matchup_abbrev = "/".join(matchup_parts[:2]) if matchup_parts else ""

        # Get real odds from totals_1st_1_innings
        odds_entry = nrfi_odds_map.get(event_id)
        if not odds_entry:
            continue  # No 1st inning odds for this game — skip

        # NRFI = Under 0.5, YRFI = Over 0.5
        nrfi_sides = [
            ("under", p_nrfi, "NRFI", odds_entry.get("under")),
            ("over",  p_yrfi, "YRFI", odds_entry.get("over")),
        ]

        # FIX M2: Compute no-vig from both sides (same as every other market)
        nrfi_under = odds_entry.get("under")
        nrfi_over = odds_entry.get("over")
        if nrfi_under and nrfi_over:
            imp_nrfi = implied_prob(nrfi_under["odds"])
            imp_yrfi = implied_prob(nrfi_over["odds"])
            nv_nrfi, nv_yrfi = no_vig(imp_nrfi, imp_yrfi)
        else:
            nv_nrfi, nv_yrfi = None, None

        for direction, win_prob, stat_label, side_odds in nrfi_sides:
            if not side_odds:
                continue

            odds = side_odds["odds"]
            book = side_odds["book"]

            # Use no-vig prob instead of vigged implied (FIX M2)
            if stat_label == "NRFI" and nv_nrfi is not None:
                nv_prob = nv_nrfi
            elif stat_label == "YRFI" and nv_yrfi is not None:
                nv_prob = nv_yrfi
            else:
                nv_prob = implied_prob(odds)  # fallback if missing one side

            raw_edge = win_prob - nv_prob

            # Tier T3 gate — R5: YRFI requires 8% min edge (higher bar until sample is built)
            min_edge = 0.08 if stat_label == "YRFI" else TIERS["T3"]["min_edge"]
            if raw_edge < min_edge:
                continue

            adj_edge = raw_edge  # No additional confidence modifier for NRFI

            pick = {
                "player": stat_label, "team_abbrev": matchup_abbrev,
                "stat": stat_label, "line": 0.5, "direction": direction,
                "proj": win_prob, "win_prob": win_prob,
                "raw_edge": raw_edge, "adj_edge": adj_edge, "conf": 1.0,
                "odds": odds, "nv_prob": nv_prob, "book": book,
                "game": game, "sport": "MLB",
                "tier": "T3", "pick_type": "game_line",
                "sigma": 0, "missing_side": False,
                "nrfi_detail": {
                    "home_pitcher": home_pitcher["name"],
                    "away_pitcher": away_pitcher["name"],
                    "p_away_scores": p_away_scores,
                    "p_home_scores": p_home_scores,
                },
            }
            # FIX 4: Run through standard game gates (GG1 edge cap, GG3 positive edge)
            # sigma=0 so GG2 deviation check is skipped — intentional for binary markets
            passed, gate = check_game_gates(pick)
            pick["gate_result"] = "PASS" if passed else gate
            # FIX H2: Use standard pick_score() function
            pick["pick_score"] = pick_score(win_prob, adj_edge, mode) if passed else None
            picks.append(pick)

    return picks

# ============================================================
#  DEDUPLICATION
# ============================================================

def deduplicate(picks):
    """
    Three-pass dedup:
    1. Group by (player, stat, line, direction) — collapse identical lines from different books
    2. Group by (player, stat, direction) — keep best line per player per stat per direction
       (fixed: preserves valid opposite-direction picks like Fox O7.5 AST + Fox U6.5 AST)
    3. MLB correlation dedup (G11/G11b): within each correlated stat group
       (pitcher: K/OUTS/HA/ER, batter: HITS/TB/HRR), keep only ONE prop per player.
       Pitcher stats are all driven by IP; batter stats overlap (HITS ⊂ HRR).
       This prevents the Luzardo K+OUTS problem.
    """
    # Pass 1: collapse same-line dupes (different books, same everything else)
    best_line = {}
    for p in picks:
        key = (p["player"], p["stat"], p["line"], p["direction"])
        if key not in best_line or p["adj_edge"] > best_line[key]["adj_edge"]:
            best_line[key] = p

    # Pass 2: one pick per player per stat per direction — keep highest edge
    # NRFI/YRFI use (stat, direction, game) as key since "player" is the stat label,
    # not a real player — multiple NRFI picks from different games must all survive.
    _GAME_LINE_DEDUP_BY_GAME = {"NRFI", "YRFI"}
    best_player_stat = {}
    for p in best_line.values():
        stat = p["stat"]
        if stat in _GAME_LINE_DEDUP_BY_GAME:
            key = (stat, p["direction"], p.get("game", ""))
        else:
            key = (p["player"], stat, p["direction"])
        if key not in best_player_stat or p["adj_edge"] > best_player_stat[key]["adj_edge"]:
            best_player_stat[key] = p

    # Pass 3: MLB correlation dedup (G11/G11b)
    # Within each correlated group, keep only the BEST pick per player (by pick_score)
    result = {}
    corr_best = {}  # (player, group_id) → best pick in that group

    for p in best_player_stat.values():
        stat = p["stat"]

        # Check if this stat belongs to a correlated group
        group_id = None
        for i, group in enumerate(MLB_CORR_GROUPS):
            if stat in group:
                group_id = i
                break

        if group_id is not None:
            # This stat is in a correlated group — enforce 1 per player per group
            corr_key = (p["player"], group_id)
            ps = p.get("pick_score", 0)
            if corr_key not in corr_best or ps > corr_best[corr_key].get("pick_score", 0):
                corr_best[corr_key] = p
        else:
            # Not in a correlated group — pass through directly
            direct_key = (p["player"], p["stat"], p["direction"])
            result[direct_key] = p

    # Merge correlated group winners into result
    for p in corr_best.values():
        key = (p["player"], p["stat"], p["direction"])
        result[key] = p

    return list(result.values())


def dedup_game_line_correlation(picks):
    """FIX 5: Remove correlated intra-game line pairs before premium selection.

    TOTAL + TEAM_TOTAL in the same direction for the same game are highly correlated
    (both win/lose together based on scoring level).  Keep only the higher pick_score.

    Correlated pairs (same game, same direction):
      - TOTAL over  + TEAM_TOTAL over   → keep best
      - TOTAL under + TEAM_TOTAL under  → keep best
    Opposite directions are NOT correlated (Total over + Team Total under = hedge).
    F5_TOTAL and NRFI/YRFI are independent markets — not subject to this rule.
    """
    CORR_STATS = {"TOTAL", "TEAM_TOTAL"}
    # Separate game-line picks that might be correlated from everything else
    gl = [p for p in picks if p.get("stat") in CORR_STATS]
    other = [p for p in picks if p.get("stat") not in CORR_STATS]

    # Group by (game, direction)
    groups = defaultdict(list)
    for p in gl:
        groups[(p.get("game", ""), p.get("direction", ""))].append(p)

    kept = []
    for (game, direction), group in groups.items():
        stats_present = {p["stat"] for p in group}
        if "TOTAL" in stats_present and "TEAM_TOTAL" in stats_present:
            # Correlated — keep only the best pick_score in this group
            best = max(group, key=lambda p: p.get("pick_score", 0) or 0)
            kept.append(best)
        else:
            kept.extend(group)

    return other + kept

# ============================================================
#  PARLAY BUILDERS
# ============================================================

def prob_to_american(prob):
    """Convert probability to American odds."""
    if prob <= 0 or prob >= 1:
        return 0
    if prob >= 0.5:
        return -(prob / (1.0 - prob)) * 100
    else:
        return ((1.0 - prob) / prob) * 100

def build_safest6_parlay(qualified):
    """Build a longshot parlay from the 6 safest picks by win probability."""
    daily = qualified
    safest = sorted(daily, key=lambda p: p["win_prob"], reverse=True)[:6]
    if len(safest) < 6:
        return None
    combined_prob = 1.0
    for p in safest:
        combined_prob *= p["win_prob"]
    parlay_odds = prob_to_american(combined_prob)
    return {"legs": safest, "combined_prob": combined_prob, "parlay_odds": parlay_odds}

def build_alt_spread_parlay(game_lines, team_proj_map, sport_sigmas, alt_spread_data=None):
    """
    Build alt spread parlay (NBA ONLY):
    - 3 legs at ~-500 each when 3+ favorites available
    - 2 legs at ~-285 each when only 2 favorites (lighter slate)
    - ALL legs from the SAME book
    - Target combined parlay: -110 to -130
    """
    if alt_spread_data is None:
        alt_spread_data = []

    # Step 1: Identify NBA favorites by projected margin
    favorites = []
    for gl in game_lines:
        if gl.get("sport", "").upper() != "NBA":
            continue
        home = gl["home"]
        away = gl["away"]
        sport = gl.get("sport", "NBA")
        sigma = sport_sigmas.get(sport, sport_sigmas.get("NBA", {})).get("spread", 12.0)

        home_proj = None
        away_proj = None
        sport_prefix = sport.upper() + "_"

        for full_name, abbr in TEAM_ABBREV.items():
            sport_key = sport_prefix + abbr
            if full_name in home.lower() and sport_key in team_proj_map:
                hp = team_proj_map[sport_key].get("saber_team", 0)
                if hp > 0:
                    home_proj = hp
            if full_name in away.lower() and sport_key in team_proj_map:
                ap = team_proj_map[sport_key].get("saber_team", 0)
                if ap > 0:
                    away_proj = ap

        if home_proj is None or away_proj is None:
            continue

        margin = home_proj - away_proj

        spread_data = gl.get("spread", {})
        home_spread_info = spread_data.get(home, {})
        away_spread_info = spread_data.get(away, {})

        for side, side_name, side_margin in [
            ("home", home, margin),
            ("away", away, -margin),
        ]:
            if side_margin <= 0:
                continue
            std_spread_info = home_spread_info if side == "home" else away_spread_info
            std_spread = std_spread_info.get("line", None)
            if std_spread is None:
                continue

            favorites.append({
                "team": side_name,
                "team_abbrev": get_team_abbrev(gl["game"], ""),
                "game": gl["game"],
                "margin": side_margin,
                "std_spread": std_spread,
                "sigma": sigma,
                "sport": sport,
            })

    favorites.sort(key=lambda f: f["margin"], reverse=True)

    # Decide legs + target per-leg odds based on available favorites
    # 3 legs: ~-500 each → combined ~-130
    # 2 legs: ~-285 each → combined ~-125
    if len(favorites) >= 3:
        num_legs = 3
        target_per_leg = -500
        odds_range = (-700, -350)
    elif len(favorites) >= 2:
        num_legs = 2
        target_per_leg = -285
        odds_range = (-450, -180)
    else:
        return None

    top_favs = favorites[:num_legs]
    top_teams = {f["team"] for f in top_favs}

    # Step 2: Index alt spread data by book → team → list of (line, odds)
    book_lines = defaultdict(lambda: defaultdict(list))
    for entry in alt_spread_data:
        if entry["team"] in top_teams and entry["odds"] < 0:
            book_lines[entry["book"]][entry["team"]].append((entry["line"], entry["odds"]))

    # Step 3: For each book, find the best line (closest to target) per team
    best_book = None
    best_parlay_odds = float("-inf")
    best_legs = None

    for book, team_lines in book_lines.items():
        if not all(team in team_lines for team in top_teams):
            continue

        legs = []
        for fav in top_favs:
            team = fav["team"]
            available = team_lines[team]

            # Find line closest to target per-leg odds
            closest = min(available, key=lambda x: abs(x[1] - target_per_leg))
            line_val, odds_val = closest

            # Must be within acceptable range
            if odds_val > odds_range[1] or odds_val < odds_range[0]:
                break

            bought_pts = line_val - fav["std_spread"]
            cover_prob = 1.0 - normal_cdf(-line_val, fav["margin"], fav["sigma"])

            legs.append({
                "team": fav["team"],
                "team_abbrev": fav["team_abbrev"],
                "game": fav["game"],
                "margin": fav["margin"],
                "std_spread": fav["std_spread"],
                "alt_spread": line_val,
                "bought_pts": bought_pts,
                "alt_cover_prob": cover_prob,
                "real_odds": odds_val,
                "real_book": display_book(book),
                "book_key": book,
                "sport": fav["sport"],
            })

        if len(legs) != num_legs:
            continue

        # Calculate parlay odds for this book
        combined_decimal = 1.0
        for leg in legs:
            ro = leg["real_odds"]
            dec = 1.0 + (100.0 / abs(ro))
            leg["decimal_odds"] = dec
            combined_decimal *= dec

        if combined_decimal >= 2.0:
            parlay_odds = (combined_decimal - 1.0) * 100.0
        else:
            parlay_odds = -100.0 / (combined_decimal - 1.0)

        if parlay_odds > best_parlay_odds:
            best_parlay_odds = parlay_odds
            best_book = book
            best_legs = legs

    if not best_legs:
        return None

    combined_prob = 1.0
    for leg in best_legs:
        combined_prob *= leg["alt_cover_prob"]

    return {
        "legs": best_legs,
        "num_legs": num_legs,
        "combined_prob": combined_prob,
        "parlay_odds": best_parlay_odds,
        "book": display_book(best_book),
        "has_real_odds": True,
    }


# ============================================================
#  OUTPUT FORMATTER
# ============================================================

def fmt_odds(odds):
    """Format American odds."""
    if odds is None:
        return "N/A"
    o = int(round(odds))
    return f"+{o}" if o > 0 else str(o)

def fmt_dir(direction):
    return "O" if direction == "over" else "U"

def fmt_pct(val):
    return f"{val*100:.1f}%"

def log_picks(qualified, mode, log_path_override=None, premium_picks=None):
    """Append all qualified picks to pick_log.csv for backtesting.
    Columns: date, run_time, sport, player, team, stat, line, direction,
             proj, win_prob, edge, odds, book, tier, pick_score, size, game, mode
    Actual result column left blank — fill in manually or automate later.

    premium_picks: list of up to 5 picks that were on the posted premium card.
                   These get card_slot=1-5; all others get card_slot=''.

    DEDUP: On repeat runs, skips picks that already exist in the log for today
    (matched on date + player + stat + line + direction). Updates odds/size/proj
    on the existing row if the pick already exists but values changed.
    """
    log_path = log_path_override if log_path_override else Path(PICK_LOG_PATH)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    run_date = datetime.now().strftime("%Y-%m-%d")
    run_time = datetime.now().strftime("%H:%M")

    # Build card slot lookup: (player_lower, stat, line, direction) -> slot number
    card_slot_map = {}
    if premium_picks:
        for i, p in enumerate(premium_picks[:5], start=1):
            key = (
                p.get("player", "").strip().lower(),
                p.get("stat", "").strip(),
                str(p.get("line", "")).strip(),
                p.get("direction", "").strip().lower(),
            )
            card_slot_map[key] = i

    HEADER = [
        "date", "run_time", "run_type", "sport", "player", "team", "stat", "line",
        "direction", "proj", "win_prob", "edge", "odds", "book",
        "tier", "pick_score", "size", "game", "mode", "result",
        "closing_odds",      # CLV: closing line odds — filled by capture_clv.py pre-game
        "clv",               # CLV: closing_implied - your_implied (positive = beat the close)
        "card_slot",         # 1-5 = was on premium card; blank = qualified but not posted
        "is_home",           # BUG G1/G2/G3 fix: True/False for SPREAD/ML/F5 picks; blank for props
        "context_verdict",   # supports | neutral | conflicts | skipped
        "context_reason",    # ≤12-word explanation from context check
        "context_score",     # 0-3 confluence count (independent positive signals)
    ]

    # Load existing rows and build a set of today's pick keys
    existing_rows = []
    existing_keys = set()
    old_header = None
    if log_path.exists() and log_path.stat().st_size > 0:
        with open(log_path, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            old_header = reader.fieldnames or []
            for row in reader:
                existing_rows.append(row)
                if row.get("date", "") == run_date:
                    # Key: (date, player, stat, line, direction)
                    key = (
                        row.get("date", ""),
                        row.get("player", "").strip().lower(),
                        row.get("stat", "").strip(),
                        str(row.get("line", "")).strip(),
                        row.get("direction", "").strip().lower(),
                    )
                    existing_keys.add(key)

    # If header has changed (new columns added), rewrite the file with updated header
    if old_header and set(HEADER) != set(old_header):
        with open(log_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=HEADER, extrasaction="ignore")
            writer.writeheader()
            for row in existing_rows:
                writer.writerow(row)
        print(f"  📋 Updated pick_log header: added {set(HEADER) - set(old_header)}")

    # Split qualified picks into new vs already-logged
    new_picks = []
    skipped = 0
    for p in qualified:
        key = (
            run_date,
            p.get("player", "").strip().lower(),
            p.get("stat", "").strip(),
            str(p.get("line", "")).strip(),
            p.get("direction", "").strip().lower(),
        )
        if key in existing_keys:
            skipped += 1
        else:
            new_picks.append(p)
            existing_keys.add(key)  # prevent intra-run dupes too

    # Append only new picks
    write_header = not log_path.exists() or log_path.stat().st_size == 0
    if new_picks:
        with open(log_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if write_header:
                writer.writerow(HEADER)
            for p in new_picks:
                if not p.get("player") or not p.get("stat"):
                    print(f"  ⚠ Skipping incomplete pick (missing player/stat): {p}")
                    continue
                slot_key = (
                    p.get("player", "").strip().lower(),
                    p.get("stat", "").strip(),
                    str(p.get("line", "")).strip(),
                    p.get("direction", "").strip().lower(),
                )
                card_slot = card_slot_map.get(slot_key, "")
                writer.writerow([
                    run_date,
                    run_time,
                    "primary",          # run_type — primary picks
                    p.get("sport", ""),
                    p.get("player", ""),
                    p.get("team_abbrev", ""),
                    p.get("stat", ""),
                    p.get("line", ""),
                    p.get("direction", ""),
                    f"{p.get('proj', 0):.2f}",
                    f"{p.get('win_prob', 0):.4f}",
                    f"{p.get('adj_edge', 0):.4f}",
                    p.get("odds", ""),
                    _norm_book(p.get("book", "")),
                    p.get("tier", ""),
                    f"{p.get('pick_score', 0):.1f}",
                    f"{p.get('size', 0):.2f}",
                    p.get("game", ""),
                    mode,
                    "",  # result — blank, fill in after games
                    "",  # closing_odds — filled by capture_clv.py
                    "",  # clv — filled by capture_clv.py
                    card_slot,  # 1-5 if on premium card, blank otherwise
                    p.get("is_home", ""),  # BUG G fix: True/False for SPREAD/ML/F5; blank for props
                    p.get("context_verdict", ""),
                    p.get("context_reason", ""),
                    p.get("context_score", ""),
                ])

    if skipped > 0:
        print(f"\n  📝 Logged {len(new_picks)} new picks to {log_path} (skipped {skipped} duplicates from earlier run)")
    else:
        print(f"\n  📝 Logged {len(new_picks)} picks to {log_path}")


# ============================================================
#  DISCORD POSTING FUNCTIONS
# ============================================================

# Set to True via --confirm flag — gates every Discord post behind a y/n prompt
_CONFIRM_MODE = False


def _confirm_post(label):
    """Prompt user before posting to Discord. Returns True to proceed, False to skip.
    Always returns True when _CONFIRM_MODE is off."""
    if not _CONFIRM_MODE:
        return True
    try:
        ans = input(f"\n  [Confirm] Post '{label}' to Discord? [y/n] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("\n  [Confirm] Skipping (no input).")
        return False
    return ans in ("y", "yes")


def _load_discord_guard():
    """Load the Discord post de-dup registry from disk. Returns {} on miss."""
    try:
        with open(DISCORD_GUARD_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_discord_guard(guard):
    """Persist the Discord post de-dup registry."""
    try:
        os.makedirs(os.path.dirname(DISCORD_GUARD_FILE), exist_ok=True)
        with open(DISCORD_GUARD_FILE, "w", encoding="utf-8") as f:
            json.dump(guard, f, indent=2)
    except Exception as e:
        logger.warning(f"[Discord] Guard write failed: {e}")


def _discord_already_posted(key):
    """Return True if this guard key has already been posted."""
    return bool(_load_discord_guard().get(key))


def _discord_mark_posted(key):
    """Record a successful Discord post in the guard registry."""
    g = _load_discord_guard()
    g[key] = True
    _save_discord_guard(g)


def _webhook_post(url, payload, retries=3, backoff=2.0, label="Discord post"):
    """POST a JSON payload to a Discord webhook URL. Retries on failure with exponential backoff.
    If _CONFIRM_MODE is True, prompts for y/n confirmation before sending.
    """
    if not url:
        logger.warning("[Discord] Webhook URL not configured — skipping post.")
        return False
    if not _confirm_post(label):
        print(f"  [Confirm] ⏭️  Skipped: {label}")
        return False
    import requests as _req
    for attempt in range(1, retries + 1):
        try:
            r = _req.post(url, json=payload, timeout=10)
            if r.status_code == 429:
                retry_after = float(r.json().get("retry_after", backoff))
                logger.warning(f"[Discord] Rate limited — waiting {retry_after:.1f}s (attempt {attempt}/{retries})")
                time.sleep(retry_after)
                continue
            r.raise_for_status()
            return True
        except Exception as e:
            if attempt < retries:
                wait = backoff ** attempt
                logger.warning(f"[Discord] Post failed (attempt {attempt}/{retries}): {e} — retrying in {wait:.1f}s")
                time.sleep(wait)
            else:
                logger.error(f"[Discord] Post failed after {retries} attempts: {e}")
    return False


def build_premium_embed(premium, mode, today, suppress_ping=False):
    """Build the Discord embed payload for the premium card (#premium-portfolio)."""
    emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]
    mode_emoji = {"Default": "⚖️", "Aggressive": "🔥", "Conservative": "🛡️"}
    picks = premium[:5]
    total_u = sum(p.get("size", 0) for p in picks)

    now_et = datetime.now(ZoneInfo("America/New_York")).strftime("%I:%M %p ET")
    mode_str = f"{mode_emoji.get(mode, '⚖️')} {mode}"

    lines = [f"**{len(picks)} picks · {total_u:.2f}u · {mode_str}**\n"]
    for i, p in enumerate(picks):
        e = emojis[i] if i < len(emojis) else "•"
        stat = p.get("stat", "")
        direction = p["direction"].upper()
        line_val = p["line"]
        odds_str = fmt_odds(p["odds"])
        book_str = display_book(p["book"])
        size = p.get("size", 0)
        game = p.get("game", "")
        edge_str = f"+{p['adj_edge']*100:.1f}%"
        score_str = f"{p.get('pick_score', 0):.1f}"
        tier = p.get("tier", "")

        # For team totals use full player name; for props use last name only
        if stat == "TEAM_TOTAL":
            display_name = p["player"]
            pick_label = f"{display_name} {direction} {line_val}"
        else:
            last = p["player"].split()[-1].upper()
            pick_label = f"{last} {direction} {line_val} {stat}"

        ctx_verdict = p.get("context_verdict", "")
        ctx_reason  = p.get("context_reason", "")
        ctx_flag    = " ⚠️" if ctx_verdict == "conflicts" else ""
        lines.append(f"{e} **{pick_label}** · {odds_str} · {book_str} · **{size:.2f}u**{ctx_flag}")
        lines.append(f"╰ {game} · Edge {edge_str} · Score {score_str} · {tier}")
        if ctx_verdict == "supports" and ctx_reason:
            lines.append(f"  ↳ ✅ {ctx_reason}")

    lines.append(f"\n━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"**Total:** {total_u:.2f}u")

    return {
        "username": "PicksByJonny",
        "content": "" if suppress_ping else "@everyone",
        "embeds": [{
            "title": f"🔒 Premium Portfolio — {today}",
            "description": "\n".join(lines),
            "color": 0xFFD700,  # Gold
            "thumbnail": {"url": BRAND_LOGO},
            "footer": {"text": f"edge > everything · {now_et}"},
        }]
    }


def build_potd_embed(potd, today):
    """Build the standalone POTD embed (posted after premium card, same channel)."""
    stat = potd.get("stat", "")
    direction = potd["direction"].upper()
    line_val = potd["line"]
    game = potd.get("game", "")
    odds_str = fmt_odds(potd["odds"])
    book_str = display_book(potd["book"])
    size = potd.get("size", 0)
    edge_str = f"+{potd['adj_edge']*100:.1f}%"
    score_str = f"{potd.get('pick_score', 0):.1f}"
    tier = potd.get("tier", "")
    proj = potd.get("proj", 0)
    now_et = datetime.now(ZoneInfo("America/New_York")).strftime("%I:%M %p ET")

    if stat == "TEAM_TOTAL":
        pick_label = f"{potd['player']} {direction} {line_val}"
    else:
        last = potd["player"].split()[-1].upper()
        pick_label = f"{last} {direction} {line_val} {stat}"

    ctx_verdict = potd.get("context_verdict", "")
    ctx_reason  = potd.get("context_reason", "")
    ctx_line    = f"\n↳ ✅ {ctx_reason}" if ctx_verdict == "supports" and ctx_reason else ""

    description = (
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"**{pick_label}**\n"
        f"{potd['player']} · {game}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{odds_str} @ {book_str} · **{size:.2f}u**\n\n"
        f"Edge: **{edge_str}** · Score: **{score_str}** · Tier: {tier}\n"
        f"Projection: {proj:.1f} {stat.lower()}"
        f"{ctx_line}"
    )

    return {
        "username": "PicksByJonny",
        "embeds": [{
            "title": f"⭐ Pick of the Day — {today}",
            "description": description,
            "color": 0xFF4500,  # OrangeRed
            "thumbnail": {"url": BRAND_LOGO},
            "footer": {"text": f"edge > everything · {now_et}"},
        }]
    }


def post_to_discord(premium, mode, today, suppress_ping=False):
    """Post the premium card + standalone POTD embed to #premium-portfolio."""
    if not premium:
        print("  [Discord] No premium picks — skipping premium post.")
        return

    # Premium card
    payload = build_premium_embed(premium, mode, today, suppress_ping=suppress_ping)
    if _webhook_post(DISCORD_WEBHOOK_URL, payload, label="premium card"):
        print(f"  [Discord] ✅ Premium card posted ({len(premium[:5])} picks)")

    # POTD — separate embed, same channel, same webhook
    potd = premium[0]
    potd_payload = build_potd_embed(potd, today)
    if _webhook_post(DISCORD_WEBHOOK_URL, potd_payload, label=f"POTD: {potd['player']} {potd['stat']}"):
        print(f"  [Discord] ✅ POTD posted: {potd['player']} {potd['stat']}")


def post_daily_lay(alt_spread_parlay, today, suppress_ping=False, save=True):
    """Post the alt spread parlay to #daily-lay channel."""
    if not DISCORD_ALT_PARLAY_WEBHOOK or not alt_spread_parlay:
        print("  [Discord] No alt spread parlay — skipping #daily-lay post.")
        return
    legs = alt_spread_parlay.get("legs", [])
    if not legs:
        return

    guard_key = f"daily_lay:{today}"
    if _discord_already_posted(guard_key):
        print(f"  [Discord] ⏭️  Daily Lay already posted for {today} — skipping")
        return

    now_et = datetime.now(ZoneInfo("America/New_York")).strftime("%I:%M %p ET")
    book = alt_spread_parlay.get("book", "N/A")
    parlay_odds = fmt_odds(alt_spread_parlay.get("parlay_odds", 0))
    n_legs = len(legs)
    DAILY_LAY_SIZE = 0.50  # Standard unit size for the daily lay parlay

    leg_lines = [f"{n_legs}-leg alt spread parlay @ {book}\n"]
    for i, leg in enumerate(legs, 1):
        team = leg.get("team", "")
        spread = leg.get("alt_spread", 0)
        sign = "+" if spread > 0 else ""
        leg_odds = fmt_odds(leg.get("real_odds", 0)) if leg.get("real_odds") else "N/A"
        cover_pct = f"{leg.get('alt_cover_prob', 0)*100:.0f}%"
        game = leg.get("game", "")
        leg_lines.append(f"**Leg {i}** · {team} {sign}{spread:.1f} (alt) · {leg_odds} · {cover_pct} cover")
        leg_lines.append(f"╰ {game}")

    leg_lines.append(f"\n━━━━━━━━━━━━━━━━━━━━━━━━━")
    leg_lines.append(f"**{parlay_odds}** combined · **{DAILY_LAY_SIZE:.2f}u**")

    payload = {
        "username": "PicksByJonny",
        "content": "" if suppress_ping else "@everyone",
        "embeds": [{
            "title": f"🎲 Daily Lay — {today}",
            "description": "\n".join(leg_lines),
            "color": 0x9B59B6,
            "footer": {"text": f"edge > everything · {now_et}"}
        }]
    }
    if _webhook_post(DISCORD_ALT_PARLAY_WEBHOOK, payload, label=f"daily lay ({n_legs} legs @ {parlay_odds})"):
        print(f"  [Discord] ✅ Daily Lay posted to #daily-lay ({n_legs} legs @ {parlay_odds})")
        _discord_mark_posted(guard_key)
        _log_daily_lay(alt_spread_parlay, today, save=save)


def _log_daily_lay(alt_spread_parlay, today_str, save=True):
    """Append the Daily Lay parlay to pick_log.csv as run_type='daily_lay'."""
    if not save:
        return
    log_path = Path(PICK_LOG_PATH)
    if not log_path.exists():
        return
    legs = alt_spread_parlay.get("legs", [])
    if not legs:
        return
    run_time = datetime.now().strftime("%H:%M")
    parlay_odds = alt_spread_parlay.get("parlay_odds", 0)
    book = alt_spread_parlay.get("book", "")

    # Single row summarising the whole parlay
    legs_desc = " / ".join(
        f"{leg.get('team','')} {'+' if leg.get('alt_spread',0)>0 else ''}{leg.get('alt_spread','')}"
        for leg in legs
    )
    rows_to_add = [{
        "date": today_str,
        "run_time": run_time,
        "run_type": "daily_lay",
        "sport": "",
        "player": f"Daily Lay {len(legs)}-leg",
        "team": "",
        "stat": "PARLAY",
        "line": "",
        "direction": "cover",
        "proj": "",
        "win_prob": "",
        "edge": "",
        "odds": parlay_odds,
        "book": book,
        "tier": "DAILY_LAY",
        "pick_score": "",
        "size": 0.50,
        "game": legs_desc,
        "mode": "",
        "result": "",
        "closing_odds": "",
        "card_slot": "",
    }]

    try:
        with open(log_path, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            header = reader.fieldnames or []
            existing = list(reader)

        # Check not already logged today
        already = any(
            r.get("date") == today_str and r.get("run_type") == "daily_lay"
            for r in existing
        )
        if already:
            return

        with open(log_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=header, extrasaction="ignore")
            for row in rows_to_add:
                writer.writerow(row)
        print(f"  📝 Daily Lay logged ({len(rows_to_add)} legs)")
    except Exception as e:
        print(f"  ⚠ Daily Lay log failed: {e}")


def post_card_announcement(premium, mode, today, suppress_ping=False):
    """Post a card-drop tease to #announcements when the premium card goes live."""
    if not DISCORD_ANNOUNCE_WEBHOOK or not premium:
        return
    guard_key = f"card_announcement:{today}"
    if _discord_already_posted(guard_key):
        print(f"  [Discord] ⏭️  Card announcement already posted for {today} — skipping")
        return
    potd = premium[0]
    potd_dir  = potd.get("direction", "").upper()
    potd_line = potd.get("line", "")
    potd_stat = potd.get("stat", "")
    if potd_stat == "TEAM_TOTAL":
        potd_label = f"{potd.get('player', '')} {potd_dir} {potd_line}"
    else:
        potd_last = potd.get("player", "").split()[-1].upper()
        potd_label = f"{potd_last} {potd_dir} {potd_line} {potd_stat}"
    sport_counts = {}
    for p in premium[:5]:
        s = p.get("sport", "")
        if s:
            sport_counts[s] = sport_counts.get(s, 0) + 1
    sport_str = " · ".join(f"{s} ({n})" for s, n in sorted(sport_counts.items())) if sport_counts else ""
    total_u = sum(p.get("size", 0) for p in premium[:5])
    payload = {
        "username": "PicksByJonny",
        "content": "" if suppress_ping else "@everyone",
        "embeds": [{
            "title": "🔒 Premium card is live",
            "description": (
                f"{sport_str} · {min(len(premium), 5)} picks · {total_u:.2f}u\n"
                f"POTD: **{potd_label}**\n\n"
                f"→ #premium-portfolio"
            ),
            "color": 0xFFD700,
            "footer": {"text": f"edge > everything · {today}"}
        }]
    }
    if _webhook_post(DISCORD_ANNOUNCE_WEBHOOK, payload, label="card announcement"):
        print(f"  [Discord] ✅ Announcement posted to #announcements")
        _discord_mark_posted(guard_key)


def _card_already_posted_today(today_str):
    """Return True if primary picks already exist in pick_log.csv for today.

    Blank/missing run_type is treated as primary (matches legacy pre-migration
    rows + the default). This prevents duplicate card posts when a prior run
    logged picks without setting run_type explicitly.
    """
    log_path = Path(PICK_LOG_PATH)
    if not log_path.exists():
        return False
    primary_markers = {"primary", "", None}
    try:
        with open(log_path, "r", newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        return any(
            r.get("date") == today_str and r.get("run_type") in primary_markers
            for r in rows
        )
    except Exception:
        return False


def post_extras_to_discord(qualified, run_id=None, save=True):
    """Post a single bonus drop to #bonus-drops.

    Selection rules (Option A from handoff):
      - "New" = pick not already in pick_log.csv under run_type='bonus' OR 'primary' for today
      - Single highest Pick Score new pick only
      - Hard cap: 5 bonus posts per calendar day (checked via pick_log.csv)

    run_id: optional identifier for this run (defaults to current timestamp string).
    """
    if not DISCORD_BONUS_WEBHOOK:
        print("  [Discord] DISCORD_BONUS_WEBHOOK not configured — skipping bonus post.")
        return

    today_str = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
    run_id = run_id or datetime.now().strftime("%H%M%S")

    # --- Check daily cap ---
    log_path = Path(PICK_LOG_PATH)
    bonus_today_count = 0
    already_posted_keys = set()  # (player_lower, stat, line, direction)

    if log_path.exists() and log_path.stat().st_size > 0:
        with open(log_path, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("date", "") != today_str:
                    continue
                # Count bonus posts
                if row.get("run_type", "").lower() == "bonus":
                    bonus_today_count += 1
                # Only block re-posting if: was on the premium card OR already a bonus drop
                # Qualified picks that didn't make the card ARE eligible for bonus
                is_card_pick = row.get("card_slot", "").strip() not in ("", None)
                is_bonus = row.get("run_type", "").lower() == "bonus"
                if is_card_pick or is_bonus:
                    already_posted_keys.add((
                        row.get("player", "").strip().lower(),
                        row.get("stat", "").strip(),
                        str(row.get("line", "")).strip(),
                        row.get("direction", "").strip().lower(),
                    ))

    if bonus_today_count >= BONUS_DAILY_CAP:
        print(f"  [Discord] Bonus cap reached ({BONUS_DAILY_CAP}/day) — skipping bonus post.")
        return

    # --- Find single highest-score new pick ---
    eligible = []
    for p in qualified:
        key = (
            p.get("player", "").strip().lower(),
            p.get("stat", "").strip(),
            str(p.get("line", "")).strip(),
            p.get("direction", "").strip().lower(),
        )
        if key not in already_posted_keys and p.get("pick_score") is not None and p.get("tier") != "KILLSHOT":
            eligible.append(p)

    if not eligible:
        print("  [Discord] No new picks available for bonus drop.")
        return

    best = max(eligible, key=lambda p: p.get("pick_score", 0))

    # --- Build embed ---
    dir_word = "Over" if best["direction"] == "over" else "Under"
    team = best.get("team_abbrev", "")
    lines = [
        f"**{best['player']} ({team}) {dir_word} {best['line']} {best['stat']}**",
        f"{fmt_odds(best['odds'])} @ {display_book(best['book'])} — **{best.get('size',0):.2f}u**",
        "",
        f"Win: **{fmt_pct(best['win_prob'])}** · Edge: **{fmt_pct(best['adj_edge'])}** · Score: **{best.get('pick_score',0):.1f}**",
        f"Projection: {best['proj']:.2f} · Tier: {best['tier']} · {best['game']}",
    ]
    payload = {
        "username": "PicksByJonny",
        "embeds": [{
            "title": "💎 Bonus Drop",
            "description": "\n".join(lines),
            "color": 0x00BFFF,  # Deep sky blue
            "footer": {"text": "edge > everything"},
        }]
    }

    if _webhook_post(DISCORD_BONUS_WEBHOOK, payload, label=f"bonus drop: {best['player']} {best['stat']}"):
        print(f"  [Discord] ✅ Bonus drop posted: {best['player']} {best['stat']} (Score: {best.get('pick_score',0):.1f})")
        # Log this bonus pick to pick_log.csv with run_type='bonus'
        _log_bonus_pick(best, run_id, today_str, save=save)


def _log_bonus_pick(pick, run_id, today_str, save=True):
    """Append a bonus pick to pick_log.csv with run_type='bonus'."""
    if not save:
        return
    log_path = Path(PICK_LOG_PATH)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    run_time = datetime.now().strftime("%H:%M")

    # Use the same HEADER as log_picks() to stay in sync
    BONUS_HEADER = [
        "date", "run_time", "run_type", "sport", "player", "team", "stat", "line",
        "direction", "proj", "win_prob", "edge", "odds", "book",
        "tier", "pick_score", "size", "game", "mode", "result",
        "closing_odds", "clv", "card_slot", "is_home",
        "context_verdict", "context_reason", "context_score",
    ]
    write_header = not log_path.exists() or log_path.stat().st_size == 0
    with open(log_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=BONUS_HEADER, extrasaction="ignore")
        if write_header:
            writer.writeheader()
        writer.writerow({
            "date":       today_str,
            "run_time":   run_time,
            "run_type":   "bonus",
            "sport":      pick.get("sport", ""),
            "player":     pick.get("player", ""),
            "team":       pick.get("team_abbrev", ""),
            "stat":       pick.get("stat", ""),
            "line":       pick.get("line", ""),
            "direction":  pick.get("direction", ""),
            "proj":       f"{pick.get('proj', 0):.2f}",
            "win_prob":   f"{pick.get('win_prob', 0):.4f}",
            "edge":       f"{pick.get('adj_edge', 0):.4f}",
            "odds":       pick.get("odds", ""),
            "book":       pick.get("book", ""),
            "tier":       pick.get("tier", ""),
            "pick_score": f"{pick.get('pick_score', 0):.1f}",
            "size":       f"{pick.get('size', 0):.2f}",
            "game":       pick.get("game", ""),
            "mode":       "",
            "result":     "",
            "closing_odds": "",
            "clv":        "",
            "card_slot":        "",  # blank for bonus picks
            "is_home":          pick.get("is_home", ""),
            "context_verdict":  pick.get("context_verdict", ""),
            "context_reason":   pick.get("context_reason", ""),
            "context_score":    pick.get("context_score", ""),
        })


# ============================================================
#  KILLSHOT TIER
# ============================================================

def _killshot_size(score):
    """Return KILLSHOT unit size based on Pick Score.
    Replaces VAKE entirely for KILLSHOT picks.
    90–99 → 3u · 100–109 → 4u · 110+ → 5u
    """
    for lo, hi, size in KILLSHOT_SIZING:
        if lo <= score < hi:
            return size
    return 3.0  # fallback floor


def _killshots_this_week(today_str):
    """Count KILLSHOT picks logged in the rolling 7 days (including today)."""
    log_path = Path(PICK_LOG_PATH)
    if not log_path.exists():
        return 0
    cutoff = (datetime.strptime(today_str, "%Y-%m-%d") - timedelta(days=6)).strftime("%Y-%m-%d")
    try:
        with open(log_path, "r", newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        return sum(
            1 for r in rows
            if r.get("tier") == "KILLSHOT"
            and cutoff <= r.get("date", "") <= today_str
        )
    except Exception:
        return 0


def select_killshots(qualified, today_str, manual_players=None):
    """Identify KILLSHOT picks from the qualified pool.

    Criteria:
      - Pick Score >= KILLSHOT_SCORE_FLOOR (90)
      - Manual promote: pick_score >= KILLSHOT_MANUAL_FLOOR (75) + player in manual_players set
      - Weekly cap: max KILLSHOT_WEEKLY_CAP (3) per rolling 7 days
      - Never duplicate a pick already in the same run

    Returns list of picks with tier='KILLSHOT' and KILLSHOT sizing applied.
    """
    manual_players = manual_players or set()
    # CLI passes last names ("Pastrnak,McDavid") but pick rows store full names.
    # Normalise manual_players to lowercase tokens for case-insensitive substring match.
    manual_tokens = {m.strip().lower() for m in manual_players if m.strip()}
    already_posted = _killshots_this_week(today_str)
    remaining_cap  = max(0, KILLSHOT_WEEKLY_CAP - already_posted)

    if remaining_cap == 0:
        print(f"  [KILLSHOT] Weekly cap reached ({already_posted}/{KILLSHOT_WEEKLY_CAP}) — no KILLSHOTs today")
        return []

    def _player_matches(full_name: str) -> bool:
        if not manual_tokens:
            return False
        parts = {w.lower() for w in full_name.split() if w}
        full_lower = full_name.lower()
        # Exact full-name match OR any token matches any name part OR substring match
        return any(tok == full_lower or tok in parts or tok in full_lower for tok in manual_tokens)

    candidates = []
    for p in qualified:
        score = p.get("pick_score", 0)
        player = p.get("player", "")
        auto_qualify   = score >= KILLSHOT_SCORE_FLOOR
        manual_qualify = _player_matches(player) and score >= KILLSHOT_MANUAL_FLOOR
        if auto_qualify or manual_qualify:
            candidates.append(p)

    # Sort by score desc, apply cap
    candidates.sort(key=lambda x: x.get("pick_score", 0), reverse=True)
    killshots = candidates[:remaining_cap]

    # Apply KILLSHOT tier + sizing
    for p in killshots:
        p["tier"] = "KILLSHOT"
        p["size"] = _killshot_size(p.get("pick_score", 0))

    if killshots:
        print(f"  [KILLSHOT] {len(killshots)} pick(s) qualified (weekly total: {already_posted + len(killshots)}/{KILLSHOT_WEEKLY_CAP})")

    return killshots


def build_killshot_embed(pick, today, suppress_ping=False):
    """Build a KILLSHOT embed for #killshot channel."""
    dir_word = "Over" if pick.get("direction") == "over" else "Under"
    team     = pick.get("team_abbrev", "")
    score    = pick.get("pick_score", 0)
    content  = "" if suppress_ping else "@everyone"

    desc = "\n".join([
        f"**{pick['player']} ({team}) {dir_word} {pick['line']} {pick['stat']}**",
        f"{fmt_odds(pick['odds'])} @ {display_book(pick['book'])} — **{pick.get('size', 0):.2f}u**",
        "",
        f"Win: **{fmt_pct(pick['win_prob'])}** · Edge: **{fmt_pct(pick['adj_edge'])}** · Score: **{score:.1f}**",
        f"Proj: {pick['proj']:.2f} · {pick['game']}",
    ])

    return {
        "username": "PicksByJonny",
        "content": content,
        "embeds": [{
            "title":       "🎯 KILLSHOT",
            "description": desc,
            "color":       0xFF0000,
            "thumbnail":   {"url": BRAND_LOGO},
            "footer":      {"text": f"{today} · edge > everything · high conviction only"},
        }]
    }


def post_killshots_to_discord(killshots, today, today_str, suppress_ping=False):
    """Post each KILLSHOT pick to #killshot channel."""
    if not killshots:
        return
    if not DISCORD_KILLSHOT_WEBHOOK:
        print("  [Discord] DISCORD_KILLSHOT_WEBHOOK not configured — skipping KILLSHOT posts.")
        return
    for pick in killshots:
        payload = build_killshot_embed(pick, today, suppress_ping=suppress_ping)
        if _webhook_post(DISCORD_KILLSHOT_WEBHOOK, payload, label=f"KILLSHOT: {pick['player']} {pick['stat']}"):
            print(f"  [Discord] 🎯 KILLSHOT posted: {pick['player']} {pick['stat']} ({pick.get('size', 0):.2f}u · Score {pick.get('pick_score', 0):.1f})")
        else:
            print(f"  [Discord] ⚠ KILLSHOT post failed: {pick['player']} {pick['stat']}")


# ============================================================
#  CONTEXT SANITY LAYER
# ============================================================

_STAT_DISPLAY = {
    "SOG":        "shots on goal",
    "PTS":        "points",
    "REB":        "rebounds",
    "AST":        "assists",
    "3PM":        "3-pointers made",
    "REC":        "receptions",
    "SPREAD":     "spread",
    "ML_FAV":     "moneyline (fav)",
    "ML_DOG":     "moneyline (dog)",
    "TOTAL":      "game total",
    "TEAM_TOTAL": "team total",
    "F5_ML":      "F5 moneyline",
    "F5_SPREAD":  "F5 spread",
    "F5_TOTAL":   "F5 total",
    "NRFI":       "no run first inning",
    "YRFI":       "yes run first inning",
    "PARLAY":     "parlay",
    "GOLF_WIN":   "tournament win",
}

def fmt_stat(stat: str) -> str:
    """Return human-readable stat label for context prompts."""
    return _STAT_DISPLAY.get(stat, stat)


def run_pregame_scan(sports, today_str):
    """Fire one Haiku+web_search call per sport to get a broad injury/lineup bulletin.

    Called once before individual pick context checks.  The bulletins are passed
    into each pick's prompt as pregame_notes so the model doesn't have to re-search
    for broad injury news on every single pick.

    Args:
        sports:     iterable of sport strings found in today's qualifying picks
        today_str:  YYYY-MM-DD

    Returns:
        dict mapping sport → bulletin text  (empty string if scan failed)
    """
    if not _ANTHROPIC_AVAILABLE:
        return {}

    _sport_prompts = {
        "NBA": (
            f"Today is {today_str}. Search for today's NBA injury report and lineup news. "
            "List any players who are OUT, QUESTIONABLE, or DOUBTFUL. "
            "Also note any confirmed starters or key role changes. "
            "Be concise — 4-8 bullet points max."
        ),
        "NHL": (
            f"Today is {today_str}. Search for today's NHL injury report and lineup news. "
            "List confirmed scratches, players marked OUT or QUESTIONABLE, "
            "and any confirmed starting goalies announced. "
            "Be concise — 4-8 bullet points max."
        ),
        "MLB": (
            f"Today is {today_str}. Search for today's MLB starting pitchers and key lineup news. "
            "List confirmed starters, any notable batting order changes, and injured/scratched players. "
            "Be concise — 4-8 bullet points max."
        ),
    }

    def _fetch(sport):
        prompt = _sport_prompts.get(sport, "")
        if not prompt:
            return sport, ""
        try:
            client = _anthropic.Anthropic()
            resp = client.messages.create(
                model      = CONTEXT_API_MODEL,
                max_tokens = 500,
                tools      = [{"type": "web_search_20250305", "name": "web_search", "max_uses": 2}],
                messages   = [{"role": "user", "content": prompt}],
            )
            text = ""
            for block in reversed(resp.content):
                if hasattr(block, "text") and block.text.strip():
                    text = block.text.strip()
                    break
            return sport, text
        except Exception as e:
            logger.warning(f"[Context] Pregame scan error for {sport}: {e}")
            return sport, ""

    unique_sports = list(dict.fromkeys(s for s in sports if s in _sport_prompts))
    if not unique_sports:
        return {}

    print(f"  [Context] Pre-scanning injury/lineup news for: {', '.join(unique_sports)} ...")
    bulletins = {}
    with ThreadPoolExecutor(max_workers=3) as ex:
        futures = {ex.submit(_fetch, sport): sport for sport in unique_sports}
        for fut in as_completed(futures):
            sport, text = fut.result()
            bulletins[sport] = text
            status = "✅" if text else "—"
            print(f"  [Context]   {status} {sport} pregame scan {'done' if text else 'empty'}")
    return bulletins


def run_context_check(pick, today_str, pregame_notes=""):
    """Fire a Claude API call with web search for one qualifying pick.

    Returns (verdict, reason, score):
        verdict: 'supports' | 'neutral' | 'conflicts'
        reason:  brief explanation string (≤12 words)
        score:   0-3 confluence count (independent positive signals)

    Errors / missing anthropic → ('neutral', 'error description', 0).
    Results are cached per (player, stat, direction, date) for the session.
    """
    cache_key = (pick.get("sport", ""), pick["player"], pick["stat"], str(pick.get("line", "")), pick["direction"], today_str)
    if cache_key in _CONTEXT_CACHE:
        return _CONTEXT_CACHE[cache_key]

    if not _ANTHROPIC_AVAILABLE:
        return "neutral", "anthropic package not installed", 0

    sport  = pick.get("sport", "NBA")
    prompt = _build_context_prompt(
        sport         = sport,
        stat          = pick["stat"],
        player        = pick["player"],
        direction     = pick["direction"].capitalize(),
        line          = pick["line"],
        game          = pick.get("game", "TBD"),
        today         = today_str,
        pregame_notes = pregame_notes,
    )

    try:
        client   = _anthropic.Anthropic()          # reads ANTHROPIC_API_KEY from env
        response = client.messages.create(
            model     = CONTEXT_API_MODEL,
            max_tokens= 120,
            system    = (
                "You output ONLY valid JSON. No prose. No markdown. No explanation. "
                'Respond with exactly: {"verdict": "...", "reason": "...", "score": N} '
                "Nothing before or after the JSON object."
            ),
            messages  = [{"role": "user", "content": prompt}],
        )

        # Extract the last text block (appears after any web_search tool_result blocks)
        result_text = ""
        for block in reversed(response.content):
            if hasattr(block, "text") and block.text.strip():
                result_text = block.text.strip()
                break

        # Parse JSON verdict
        verdict, reason, score = "neutral", "", 0

        m = re.search(r'\{[^{}]+\}', result_text, re.DOTALL)
        if m:
            try:
                data    = json.loads(m.group())
                verdict = data.get("verdict", "neutral").lower()
                reason  = data.get("reason", "")
            except (json.JSONDecodeError, ValueError, TypeError):
                pass

        # Fallback: keyword scan if JSON didn't parse or reason missing
        if not reason or verdict not in ("conflicts", "neutral"):
            tl = result_text.lower()
            _conflict_words = (
                "out ", "ruled out", "scratch", "doubtful", "injured", "injury",
                "did not play", "won't play", "listed out", "inactive",
            )
            verdict = "conflicts" if any(w in tl for w in _conflict_words) else "neutral"
            for sent in re.split(r'[.!?\n]', result_text):
                sent = re.sub(r'\*+', '', sent).strip().lstrip('—–- \t:')
                if sent and not sent.startswith('{') and len(sent) > 8:
                    reason = " ".join(sent.split()[:10])
                    break
            if not reason:
                reason = "no detail"

        # Clean up reason
        reason = re.sub(r'\*+', '', reason)
        reason = re.sub(r'^[—–\-\s:]+', '', reason).strip()
        reason = " ".join(reason.split()[:10])

        if verdict not in ("conflicts", "neutral"):
            verdict = "neutral"

    except Exception as e:
        logger.warning(f"[Context] API error for {pick['player']}: {e}")
        verdict, reason, score = "neutral", "api error", 0

    _CONTEXT_CACHE[cache_key] = (verdict, reason, score)
    return verdict, reason, score


def apply_context_sanity(qualified, today_str, skip=False, mode="Default"):
    """Post-gate context sanity layer — runs after all math gates, before sizing.

    For each qualifying pick:
      - Fires a Claude API call (web search enabled) using a sport-specific prompt
      - Returns structured verdict: 'supports' | 'neutral' | 'conflicts'
      - On 'conflicts': multiplies conf by CONTEXT_CONFLICT_MULT → recomputes
        adj_edge and pick_score → re-checks tier minimum edge
      - Picks that drop below tier min are moved to context_rejects
        (logged as gate_result = 'CONTEXT_CONFLICT' in diagnostics)

    Returns (still_qualified, context_rejects).
    Pass skip=True (--no-context flag) to bypass entirely.
    """
    if skip or not qualified:
        for p in qualified:
            p["context_verdict"] = "skipped"
            p["context_reason"]  = ""
        return qualified, []

    print(f"\n  [Context] Running sanity layer on {len(qualified)} qualifying picks...")
    if not _ANTHROPIC_AVAILABLE:
        print("  [Context] ⚠️  anthropic package not found — skipping (pip install anthropic)")
        for p in qualified:
            p["context_verdict"] = "skipped"
            p["context_reason"]  = "anthropic not installed"
            p["context_score"]   = 0
        return qualified, []

    # Step 1: Pre-scan injury/lineup news per sport (one call per sport, not per pick)
    sports_in_run = [p.get("sport", "NBA") for p in qualified]
    pregame_bulletins = run_pregame_scan(sports_in_run, today_str)

    # Step 2: Run all individual pick checks concurrently
    futures_map = {}
    with ThreadPoolExecutor(max_workers=CONTEXT_MAX_WORKERS) as ex:
        for p in qualified:
            notes = pregame_bulletins.get(p.get("sport", "NBA"), "")
            fut = ex.submit(run_context_check, p, today_str, notes)
            futures_map[fut] = p
        for fut in as_completed(futures_map):
            pick = futures_map[fut]
            try:
                verdict, reason, score = fut.result(timeout=45)
            except Exception:
                verdict, reason, score = "neutral", "timeout", 0
            pick["context_verdict"] = verdict
            pick["context_reason"]  = reason
            pick["context_score"]   = score

    # Only picks with 'supports' verdict make it through — neutral and conflicts are cut.
    # If context is skipped entirely (--no-context / no anthropic), all picks pass as before.
    still_qualified  = []
    context_rejects  = []

    for p in qualified:
        verdict = p["context_verdict"]

        if verdict == "conflicts":
            p["gate_result"] = "CONTEXT_CONFLICT"
            context_rejects.append(p)
            print(f"  [Context] ❌ CUT:      {p['player']:<22} {p['stat']:<4} | {p['context_reason']}")
        elif verdict == "supports":
            print(f"  [Context] ✅ SUPPORTS: {p['player']:<22} {p['stat']:<4} | {p['context_reason']}")
            still_qualified.append(p)
        else:
            # neutral / skipped / timeout / api error — all pass
            print(f"  [Context] —  PASS:     {p['player']:<22} {p['stat']:<4} | {p['context_reason'] or 'no flag'}")
            still_qualified.append(p)

    n_supports  = sum(1 for p in still_qualified if p.get("context_verdict") == "supports")
    n_conflicts = len(context_rejects)
    print(
        f"\n  [Context] Done — {len(still_qualified)}/{len(qualified)} pass "
        f"({n_supports} with positive signal, {n_conflicts} cut)"
    )
    return still_qualified, context_rejects


def format_output(premium, safest5, all_qualified, all_picks, mode, today,
                   safest6_parlay=None, alt_spread_parlay=None):
    """Format the full output (sections A-J + parlays)."""
    out = []

    # === PICK OF THE DAY ===
    if premium:
        potd = premium[0]  # Highest Pick Score
        out.append(f"{'='*50}")
        out.append("⭐ PICK OF THE DAY")
        out.append(f"{'='*50}")
        out.append(f"  {potd['player']} ({potd.get('team_abbrev','')}) {'Over' if potd['direction']=='over' else 'Under'} {potd['line']} {potd['stat']}")
        out.append(f"  {fmt_odds(potd['odds'])} @ {display_book(potd['book'])} — {potd.get('size',0):.2f}u")
        out.append(f"  Win Prob: {fmt_pct(potd['win_prob'])} | Edge: {fmt_pct(potd['adj_edge'])} | Pick Score: {potd.get('pick_score',0):.1f}")
        out.append(f"  Projection: {potd['proj']:.2f} | Tier: {potd['tier']} | {potd['game']}")
        out.append("")

    # === A. PREMIUM CARD ===
    out.append(f"🔒 PREMIUM PICKS — {today} | Mode: {mode}")
    out.append("")
    total_u = 0
    if premium:
        emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]
        for i, p in enumerate(premium[:5]):
            e = emojis[i] if i < 5 else f"  "
            size = p.get("size", 0)
            total_u += size
            out.append(f"{e} {size:.2f}u | {p['player']} ({p.get('team_abbrev','')}) {fmt_dir(p['direction'])}{p['line']} {p['stat']} @ {fmt_odds(p['odds'])} ({display_book(p['book'])})")
            out.append(f"   Win: {fmt_pct(p['win_prob'])} | Edge: {fmt_pct(p['adj_edge'])} | Pick Score: {p.get('pick_score',0):.1f} | Proj: {p['proj']:.2f} | {p['tier']} | {p['game']}")
            out.append("")
        out.append("━" * 40)
        out.append(f"Total: {total_u:.2f}u | Bets: {len(premium[:5])}")
    else:
        out.append("No qualifying daily picks.")
    out.append("")

    # === B. SAFEST 5 ===
    out.append(f"🛡️ SAFEST 5 — {today}")
    out.append("")
    if safest5:
        for i, p in enumerate(safest5[:5]):
            out.append(f"  {i+1}. {p.get('size',0):.2f}u | {p['player']} ({p.get('team_abbrev','')}) {fmt_dir(p['direction'])}{p['line']} {p['stat']} @ {fmt_odds(p['odds'])} ({display_book(p['book'])}) | Win: {fmt_pct(p['win_prob'])}")
    else:
        out.append("  No qualifying daily picks.")
    out.append("")

    # === C-E. FULL CARD BY TIER ===
    for tier_label, tier_keys in [("C. T1/T1B PROPS", ("T1", "T1B")),
                                   ("D. T2 PROPS", ("T2",)),
                                   ("E. T3 PROPS", ("T3",))]:
        tier_picks = [p for p in all_qualified if p["tier"] in tier_keys and p["pick_type"] == "prop"]
        tier_picks.sort(key=lambda p: p["adj_edge"], reverse=True)
        out.append(f"{'='*50}")
        out.append(tier_label)
        out.append(f"{'='*50}")
        if not tier_picks:
            out.append("No qualifying picks.")
        else:
            # Group by stat
            by_stat = defaultdict(list)
            for p in tier_picks:
                by_stat[p["stat"]].append(p)
            for stat, picks in sorted(by_stat.items()):
                tier_disp = f"{picks[0]['tier']} {stat}" + (" UNDERS" if stat == "REB" else "")
                out.append(f"\n{tier_disp}")
                out.append("─" * 40)
                for p in picks:
                    out.append(f"  {p.get('size',0):.2f}u | {p['player']} ({p.get('team_abbrev','')}) {fmt_dir(p['direction'])}{p['line']} {stat} @ {fmt_odds(p['odds'])} ({display_book(p['book'])}) | {fmt_pct(p['win_prob'])} | {fmt_pct(p['adj_edge'])} | {p['game']}")
        out.append("")

    # === F. GAME LINES ===
    gl_picks = [p for p in all_qualified if p["pick_type"] == "game_line"]
    gl_picks.sort(key=lambda p: p["adj_edge"], reverse=True)
    out.append(f"{'='*50}")
    out.append("F. GAME LINES")
    out.append(f"{'='*50}")
    if not gl_picks:
        out.append("No qualifying picks.")
    else:
        for p in gl_picks:
            out.append(f"  {p.get('size',0):.2f}u | {p['player']} {fmt_dir(p['direction'])}{p['line']} @ {fmt_odds(p['odds'])} ({display_book(p['book'])}) | {fmt_pct(p['win_prob'])} | {fmt_pct(p['adj_edge'])} | {p['game']}")
    out.append("")

    # === G. CONTEXT FLAGS ===
    ctx_picks = [p for p in all_qualified if p.get("context_verdict") not in ("neutral", "skipped", "")]
    if ctx_picks:
        out.append(f"{'='*50}")
        out.append("G. CONTEXT FLAGS")
        out.append(f"{'='*50}")
        for p in sorted(ctx_picks, key=lambda x: x.get("context_verdict", "")):
            v = p.get("context_verdict", "")
            icon = "✅" if v == "supports" else "⚠️ "
            label = f"{p['player']} {fmt_dir(p['direction'])}{p['line']} {p['stat']}"
            reason = p.get("context_reason", "")
            out.append(f"  {icon} {label:<38} {reason}")
        out.append("")

    # === H. SANITY CHECK TABLE (PASS picks only) ===
    out.append(f"{'='*50}")
    out.append("H. SANITY CHECK TABLE")
    out.append(f"{'='*50}")
    out.append(f"{'Pick':<35} {'Proj':>5} {'Line':>5} {'Fair%':>6} {'NV%':>6} {'Edge':>6} {'AdjE':>6} {'Size':>5} {'Tier':>4} {'Ctx':<8}")
    out.append("─" * 110)
    pass_picks = sorted(all_qualified, key=lambda x: x.get("adj_edge", 0), reverse=True)
    for p in pass_picks:
        label = f"{p['player']} {fmt_dir(p['direction'])}{p['line']} {p['stat']}"[:34]
        size  = p.get("size", 0)
        nv    = p.get("nv_prob", 0)
        raw_e = p["raw_edge"]
        ctx   = p.get("context_verdict", "—")[:8]
        out.append(
            f"{label:<35} {p['proj']:5.1f} {p['line']:5.1f} {p['win_prob']*100:5.1f}% "
            f"{nv*100:5.1f}% {raw_e*100:5.1f}% {p['adj_edge']*100:5.1f}% "
            f"{size:5.2f} {p.get('tier',''):>4} {ctx:<8}"
        )
    out.append("")

    # === DISCORD COPY/PASTE ===
    out.append(f"{'='*50}")
    out.append("DISCORD COPY/PASTE BLOCK")
    out.append(f"{'='*50}")
    if premium:
        out.append(f"@everyone Today's Portfolio – {today}")
        out.append("")
        out.append("Unit Framework:")
        out.append("1u = 1% bankroll")
        out.append("Max Single Position = 1.25u")
        out.append("Max 5 Positions")
        out.append("Target Daily Exposure = 4–6u")
        out.append("")
        out.append("Plays")
        max_size = 0
        for p in premium[:5]:
            size = p.get("size", 0)
            max_size = max(max_size, size)
            dir_word = "Over" if p["direction"] == "over" else "Under"
            team = p.get("team_abbrev", "")
            out.append(f"{p['player']} ({team}) {dir_word} {p['line']} {p['stat']} {fmt_odds(p['odds'])} ({display_book(p['book'])}) — {size:.2f}u")
        out.append("")
        out.append(f"Total Risk Today: {total_u:.2f}u")
        out.append(f"Largest Single Position: {max_size:.2f}u")
    else:
        out.append("No qualifying daily picks.")
    out.append("")

    # === SAFEST 6 LONGSHOT PARLAY ===
    out.append(f"{'='*50}")
    out.append("LONGSHOT PARLAY — Safest 6 Picks")
    out.append(f"{'='*50}")
    if safest6_parlay and safest6_parlay["legs"]:
        for i, leg in enumerate(safest6_parlay["legs"], 1):
            dir_word = "Over" if leg["direction"] == "over" else "Under"
            team = leg.get("team_abbrev", "")
            out.append(f"  {i}. {leg['player']} ({team}) {dir_word} {leg['line']} {leg['stat']} {fmt_odds(leg['odds'])} ({display_book(leg['book'])}) | Win: {fmt_pct(leg['win_prob'])}")
        out.append(f"  ────────────────────────────────")
        out.append(f"  Combined Probability: {safest6_parlay['combined_prob']*100:.2f}%")
        out.append(f"  Fair Odds: {fmt_odds(safest6_parlay['parlay_odds'])}")
    else:
        out.append("  Not enough qualifying picks for 6-leg parlay.")
    out.append("")

    # === ALT 3-LEG SPREAD PARLAY ===
    out.append(f"{'='*50}")
    out.append("ALT SPREAD PARLAY — 3 Legs @ ~-500 Each")
    out.append(f"{'='*50}")
    if alt_spread_parlay and alt_spread_parlay["legs"]:
        out.append(f"  Book: {alt_spread_parlay.get('book', 'N/A')}")
        out.append("")
        for i, leg in enumerate(alt_spread_parlay["legs"], 1):
            sign = "+" if leg["alt_spread"] > 0 else ""
            odds_str = fmt_odds(leg["real_odds"]) if leg.get("real_odds") else "N/A"
            out.append(f"  {i}. {leg['team']} {sign}{leg['alt_spread']:.1f} ({odds_str})")
            out.append(f"     {leg['game']} | Margin: {leg['margin']:+.1f} | Cover: {leg['alt_cover_prob']*100:.1f}%")
        out.append(f"  ────────────────────────────────")
        out.append(f"  Parlay Odds: {fmt_odds(alt_spread_parlay['parlay_odds'])}")
        out.append(f"  Model Cover Prob: {alt_spread_parlay['combined_prob']*100:.1f}%")
    else:
        out.append("  Not enough qualifying NBA game lines for 3-leg parlay.")
    out.append("")

    # === I. VERIFICATION CHECKLIST ===
    out.append(f"{'='*50}")
    out.append("I. OUTPUT VERIFICATION CHECKLIST")
    out.append(f"{'='*50}")

    n_prem = len(premium)
    n_overs_prem = sum(1 for p in premium if p["direction"] == "over")
    n_overs_all = sum(1 for p in all_qualified if p["direction"] == "over")
    stat_dir_counts = defaultdict(int)
    for p in premium:
        stat_dir_counts[(p["stat"], p["direction"])] += 1
    max_same = max(stat_dir_counts.values()) if stat_dir_counts else 0
    has_u25_ast = any(p["stat"] == "AST" and p["direction"] == "under" and p["line"] <= 2.5 for p in all_qualified)
    has_u25_reb = any(p["stat"] == "REB" and p["direction"] == "under" and p["line"] <= 2.5 for p in all_qualified)
    has_reb_over = any(p["stat"] == "REB" and p["direction"] == "over" for p in all_qualified)
    has_g8_fail = any(p["stat"] in ("AST","REB","SOG","K","HA","HITS") and p["line"] <= 1.5 for p in all_qualified)
    has_heavy_juice = any(p["odds"] <= -150 for p in all_qualified)
    max_game = max(defaultdict(int, {p["game"]: sum(1 for q in all_qualified if q["game"]==p["game"]) for p in all_qualified}).values()) if all_qualified else 0

    # G11 check: any pitcher with 2+ props across K/OUTS/HA/ER?
    pitcher_prop_counts = defaultdict(int)
    for p in all_qualified:
        if p["stat"] in PITCHER_STATS:
            pitcher_prop_counts[p["player"]] += 1
    max_pitcher_props = max(pitcher_prop_counts.values()) if pitcher_prop_counts else 0
    # G11b check: any batter with 2+ props across HITS/TB/HRR?
    batter_prop_counts = defaultdict(int)
    for p in all_qualified:
        if p["stat"] in BATTER_CORR_STATS:
            batter_prop_counts[p["player"]] += 1
    max_batter_corr = max(batter_prop_counts.values()) if batter_prop_counts else 0

    checks = [
        (f"Premium card: {n_prem} picks generated", n_prem == 5 or n_prem == 0),
        (f"Safest 5 generated", len(safest5) >= 5 or len(safest5) == 0),
        (f"R9 directional balance: {n_overs_prem} overs on Premium", n_overs_prem >= 1 if n_overs_all >= 3 else True),
        (f"R10 same-stat cap: max {max_same} same-stat same-dir", max_same <= 2),
        (f"R11 enforced: No U2.5 AST", not has_u25_ast),
        (f"R4 enforced: No REB Overs, no U2.5 REB", not has_reb_over and not has_u25_reb),
        (f"G8 enforced: No AST/REB/SOG/K/HA/HITS at line ≤ 1.5", not has_g8_fail),
        (f"G7 enforced: No odds ≤ -150", not has_heavy_juice),
        (f"R7 enforced: Max per game = {max_game}", max_game <= 2),
        (f"G11 enforced: Max pitcher props per pitcher = {max_pitcher_props}", max_pitcher_props <= 1),
        (f"G11b enforced: Max batter corr props per batter = {max_batter_corr}", max_batter_corr <= 1),
        (f"All sizes ≤ 1.25u", all(p.get("size",0) <= 1.25 for p in all_qualified)),
        (f"Daily cap: {total_u:.2f}u ≤ 12u", total_u <= 12.0),
    ]
    for label, ok in checks:
        mark = "✓" if ok else "✗"
        out.append(f"  [{mark}] {label}")
    out.append("")

    # === J. NOTES ===
    out.append(f"{'='*50}")
    out.append("J. NOTES")
    out.append(f"{'='*50}")
    n_over = sum(1 for p in all_qualified if p["direction"] == "over")
    n_under = sum(1 for p in all_qualified if p["direction"] == "under")
    # FIX L5: Guard against division by zero on empty pick days
    total_dir = n_over + n_under
    if total_dir > 0:
        out.append(f"  Directional mix: {n_over} overs, {n_under} unders ({n_over/total_dir*100:.0f}%/{n_under/total_dir*100:.0f}% split)")
    else:
        out.append("  No picks")
    out.append(f"  Total qualifying picks: {len(all_qualified)}")
    out.append(f"  Mode: {mode}")
    out.append("")

    return "\n".join(out)

# ============================================================
#  MAIN
# ============================================================

def find_csvs(folder=None):
    folder = Path(folder or CSV_FOLDER)
    if not folder.exists():
        return []
    csvs = sorted(folder.glob("*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
    result = []
    for c in csvs[:20]:
        try:
            with open(c, "r", encoding="utf-8-sig") as f:
                hdr = f.readline().lower()
            if any(k in hdr for k in ["saber", "ast", "rb", "sog", "pts", "win%", "make cut", "birdies"]):
                result.append(c)
        except:
            continue
    return result

def main():
    parser = argparse.ArgumentParser(description="JonnyParlay MBP Runner v2.0 — Pure Python")
    parser.add_argument("csvs", nargs="*", help="SaberSim CSV file(s)")
    parser.add_argument("--mode", default="Default", choices=["Default", "Conservative", "Aggressive"])
    parser.add_argument("--exclude", default="", help="Teams to exclude")
    parser.add_argument("--cooldown", default="", help="R12 cooldown players (comma-separated last names)")
    parser.add_argument("--output", default=None)
    parser.add_argument("--no-save", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="Fetch odds only")
    parser.add_argument("--parlays-only", action="store_true", help="Only output Longshot + Alt Spread parlays")
    parser.add_argument("--alt-parlay", action="store_true", help="Only output Alt Spread parlay (skips props, minimal API calls)")
    parser.add_argument("--no-cache", action="store_true", help="Skip odds cache, force fresh API calls")
    parser.add_argument("--force", action="store_true", help="Skip game start-time filter (test with already-started games)")
    parser.add_argument("--no-discord", action="store_true", help="Skip all Discord posts (dry run for Discord only)")
    parser.add_argument("--test",       action="store_true", help="Suppress @everyone ping on all Discord posts (safe preview)")
    parser.add_argument("--repost",     action="store_true", help="Re-fire premium card + POTD from the most recent primary log entry")
    parser.add_argument("--context", action="store_true", help="Enable context sanity layer (Claude API calls for injury/news check)")
    parser.add_argument("--killshot", default="", help="Manually promote picks to KILLSHOT tier (comma-separated player last names, e.g. 'Pastrnak,McDavid')")
    parser.add_argument("--log-manual", action="store_true", help="Log a manually posted pick to pick_log.csv (interactive prompt)")
    parser.add_argument("--confirm",    action="store_true", help="Prompt y/n before every Discord post")

    args = parser.parse_args()

    global _CONFIRM_MODE
    _CONFIRM_MODE = args.confirm

    print("""
    ╔═══════════════════════════════════════════╗
    ║  JonnyParlay MBP Runner v2.0              ║
    ║  Master Betting Prompt v9.4               ║
    ║  Pure Python — Zero AI, Deterministic     ║
    ╚═══════════════════════════════════════════╝
    """)

    # --- CSV ---
    csv_paths = []
    if args.csvs:
        csv_paths = [Path(c) for c in args.csvs]
    else:
        found = find_csvs()
        if not found:
            print(f"  No SaberSim CSVs in {CSV_FOLDER}")
            print("  Usage: python run_picks.py path/to/nba.csv")
            sys.exit(1)
        print(f"  Found {len(found)} CSV(s):\n")
        for i, f in enumerate(found[:10]):
            mt = datetime.fromtimestamp(f.stat().st_mtime).strftime("%m/%d %H:%M")
            print(f"    [{i+1}] {f.name} ({mt})")
        choice = input(f"\n  Select (e.g. '1' or '1,2'): ").strip()
        if not choice:
            sys.exit(0)
        indices = [int(x.strip())-1 for x in choice.split(",") if x.strip().isdigit()]
        csv_paths = [found[i] for i in indices if 0 <= i < len(found)]

    all_players = {}
    for path in csv_paths:
        players, sport = parse_csv(path)
        if sport not in all_players:
            all_players[sport] = []
        all_players[sport].extend(players)

    sports = list(all_players.keys())
    cooldown = [s.strip() for s in args.cooldown.split(",") if s.strip()]

    # Auto-R12: merge pick_log losses (last 5 days) into cooldown list automatically
    today_str_main = datetime.now().strftime("%Y-%m-%d")
    auto_cool = auto_r12_from_log(today_str_main, window_days=5)
    if auto_cool:
        # Merge: manual --cooldown takes precedence, auto adds any not already listed
        manual_cool_norm = {normalize_name(n) for n in cooldown}
        for p in auto_cool:
            if normalize_name(p) not in manual_cool_norm:
                cooldown.append(p)

    # Parse exclude list — accepts team names, abbreviations, or city names
    exclude_raw = [s.strip().lower() for s in args.exclude.split(",") if s.strip()]
    # Common abbreviation/name mappings
    TEAM_ALIASES = {
        "celtics": "boston celtics", "bos": "boston celtics", "boston": "boston celtics",
        "hornets": "charlotte hornets", "cha": "charlotte hornets", "charlotte": "charlotte hornets",
        "wizards": "washington wizards", "was": "washington wizards", "washington": "washington wizards",
        "raptors": "toronto raptors", "tor": "toronto raptors", "toronto": "toronto raptors",
        "blazers": "portland trail blazers", "trailblazers": "portland trail blazers", "por": "portland trail blazers", "portland": "portland trail blazers",
        "magic": "orlando magic", "orl": "orlando magic", "orlando": "orlando magic",
        "kings": "sacramento kings", "sac": "sacramento kings", "sacramento": "sacramento kings",
        "nets": "brooklyn nets", "bkn": "brooklyn nets", "brooklyn": "brooklyn nets",
        "lakers": "los angeles lakers", "lal": "los angeles lakers",
        "clippers": "la clippers", "lac": "la clippers",
        "knicks": "new york knicks", "nyk": "new york knicks",
        "warriors": "golden state warriors", "gsw": "golden state warriors",
        "nuggets": "denver nuggets", "den": "denver nuggets", "denver": "denver nuggets",
        "thunder": "oklahoma city thunder", "okc": "oklahoma city thunder",
        "rockets": "houston rockets", "hou": "houston rockets", "houston": "houston rockets",
        "pelicans": "new orleans pelicans", "nop": "new orleans pelicans",
        "suns": "phoenix suns", "phx": "phoenix suns",
        "mavs": "dallas mavericks", "dal": "dallas mavericks", "mavericks": "dallas mavericks",
        "heat": "miami heat", "mia": "miami heat",
        "bucks": "milwaukee bucks", "mil": "milwaukee bucks",
        "76ers": "philadelphia 76ers", "sixers": "philadelphia 76ers", "phi": "philadelphia 76ers",
        "hawks": "atlanta hawks", "atl": "atlanta hawks",
        "bulls": "chicago bulls", "chi": "chicago bulls",
        "cavs": "cleveland cavaliers", "cle": "cleveland cavaliers", "cavaliers": "cleveland cavaliers",
        "pistons": "detroit pistons", "det": "detroit pistons",
        "pacers": "indiana pacers", "ind": "indiana pacers",
        "grizzlies": "memphis grizzlies", "mem": "memphis grizzlies",
        "timberwolves": "minnesota timberwolves", "min": "minnesota timberwolves", "wolves": "minnesota timberwolves",
        "spurs": "san antonio spurs", "sas": "san antonio spurs",
        "jazz": "utah jazz", "uta": "utah jazz",
        # NHL
        "avalanche": "colorado avalanche", "col": "colorado avalanche", "avs": "colorado avalanche",
        "blackhawks": "chicago blackhawks",
        "devils": "new jersey devils", "njd": "new jersey devils",
        "flyers": "philadelphia flyers",
        "penguins": "pittsburgh penguins", "pit": "pittsburgh penguins", "pens": "pittsburgh penguins",
        "islanders": "new york islanders", "nyi": "new york islanders",
        "flames": "calgary flames", "cgy": "calgary flames",
        "maple leafs": "toronto maple leafs", "leafs": "toronto maple leafs",
        "ducks": "anaheim ducks", "ana": "anaheim ducks",
        "blues": "st louis blues", "stl": "st louis blues",
        "sharks": "san jose sharks", "sjs": "san jose sharks",
        "canucks": "vancouver canucks", "van": "vancouver canucks",
        "golden knights": "vegas golden knights", "vgk": "vegas golden knights", "knights": "vegas golden knights",
        "stars": "dallas stars",
    }
    exclude_teams = set()
    for ex in exclude_raw:
        if ex in TEAM_ALIASES:
            exclude_teams.add(TEAM_ALIASES[ex])
        else:
            exclude_teams.add(ex)  # keep raw for fuzzy matching

    # --- ODDS ---
    print(f"\n  Sports: {', '.join(sports)} | Mode: {args.mode}")
    if exclude_teams:
        print(f"  Excluding: {', '.join(sorted(exclude_teams))}")
    if cooldown:
        manual_listed = [s.strip() for s in args.cooldown.split(",") if s.strip()]
        auto_listed = [p for p in cooldown if p not in manual_listed]
        parts = []
        if manual_listed:
            parts.append(f"manual: {', '.join(manual_listed)}")
        if auto_listed:
            parts.append(f"auto: {', '.join(auto_listed)}")
        print(f"  R12 Cooldown: {' | '.join(parts)}")

    fetcher = OddsFetcher()
    odds_data = fetcher.fetch_all(sports,
                                   fetch_alt_spreads=True,
                                   game_lines_only=args.alt_parlay,
                                   no_cache=args.no_cache,
                                   force=args.force)

    if args.dry_run:
        out_path = Path(OUTPUT_FOLDER)
        out_path.mkdir(parents=True, exist_ok=True)
        dp = out_path / f"odds_dry_{datetime.now().strftime('%Y-%m-%d')}.json"
        with open(dp, "w") as f:
            json.dump(odds_data, f, indent=2, default=str)
        print(f"\n  Dry run saved: {dp}")
        return

    # --- EVALUATION ---
    print(f"\n  {'='*40}")
    print(f"  Running MBP v9.4 engine...")
    print(f"  {'='*40}")

    all_prop_picks = []
    all_game_picks = []
    all_game_lines = []  # For alt spread parlay
    all_team_proj = {}   # For alt spread parlay
    all_alt_spreads = [] # For alt spread parlay — real book prices

    for sport, players in all_players.items():
        sd = odds_data.get(sport, {})

        # Game lines (needed for all modes)
        game_lines = extract_game_lines(sd, sport)
        all_game_lines.extend(game_lines)

        # Alt spreads (real book prices for parlay)
        if sport == "NBA":
            alt_sp = extract_alt_spreads(sd, sport)
            all_alt_spreads.extend(alt_sp)

        # Build team projection map for this sport (keyed by sport+team to avoid DAL/DET collisions)
        for p in players:
            team = p["team"].upper()
            key = f"{sport}_{team}"
            if key not in all_team_proj:
                all_team_proj[key] = {"saber_total": p["saber_total"], "saber_team": p["saber_team"], "sport": sport}

        # Skip props + game line evaluation in alt-parlay mode
        if args.alt_parlay:
            continue

        # Props
        raw_props = extract_player_props(sd, sport)
        matched = match_props_to_projections(raw_props, players)
        print(f"\n  {sport}: {len(raw_props)} prop lines found, {len(matched)} matched to projections")

        prop_picks = evaluate_props(matched, args.mode, cooldown)
        all_prop_picks.extend(prop_picks)

        # Game line evaluation
        team_tots = extract_team_totals(sd, sport)
        gl_picks = evaluate_game_lines(game_lines, team_tots, players, sport, args.mode)
        all_game_picks.extend(gl_picks)

        # MLB-specific: F5 innings + NRFI/YRFI
        if sport == "MLB":
            f5_data = extract_f5_lines(sd, sport)
            f5_picks = evaluate_f5_lines(f5_data, players, args.mode)
            all_game_picks.extend(f5_picks)
            print(f"  MLB F5: {len(f5_data)} games, {len(f5_picks)} F5 picks evaluated")

            nrfi_picks = evaluate_nrfi(game_lines, players, sd, sport, args.mode)
            all_game_picks.extend(nrfi_picks)
            print(f"  MLB NRFI: {len(nrfi_picks)} NRFI/YRFI evaluated")

    # === ALT-PARLAY FAST PATH ===
    if args.alt_parlay:
        sport_sigmas = {}
        for sport in all_players:
            sport_sigmas[sport] = GAME_SIGMA.get(sport, GAME_SIGMA["NBA"])
        alt_spread_parlay = build_alt_spread_parlay(all_game_lines, all_team_proj, sport_sigmas, all_alt_spreads)

        today = datetime.now().strftime("%B %d, %Y")
        pout = []
        pout.append(f"{'='*50}")
        pout.append(f"ALT SPREAD PARLAY — {today}")
        pout.append(f"3 Legs @ ~-500 Each")
        pout.append(f"{'='*50}")
        if alt_spread_parlay and alt_spread_parlay["legs"]:
            pout.append(f"  Book: {alt_spread_parlay.get('book', 'N/A')}")
            pout.append("")
            for i, leg in enumerate(alt_spread_parlay["legs"], 1):
                sign = "+" if leg["alt_spread"] > 0 else ""
                odds_str = fmt_odds(leg["real_odds"]) if leg.get("real_odds") else "N/A"
                pout.append(f"  {i}. {leg['team']} {sign}{leg['alt_spread']:.1f} ({odds_str})")
                pout.append(f"     {leg['game']} | Margin: {leg['margin']:+.1f} | Cover: {leg['alt_cover_prob']*100:.1f}%")
            pout.append(f"  ────────────────────────────────")
            pout.append(f"  Parlay Odds: {fmt_odds(alt_spread_parlay['parlay_odds'])}")
            pout.append(f"  Model Cover Prob: {alt_spread_parlay['combined_prob']*100:.1f}%")
        else:
            pout.append("  Not enough qualifying NBA game lines for 3-leg parlay.")
        print("\n" + "\n".join(pout))
        print("\n  Done. Let's eat.\n")
        return

    # Combine
    all_picks = all_prop_picks + all_game_picks

    # Exclude teams
    if exclude_teams:
        before = len(all_picks)
        all_picks = [p for p in all_picks
                     if not any(ex in p.get("game", "").lower() for ex in exclude_teams)]
        print(f"\n  Excluded {before - len(all_picks)} picks from {len(exclude_teams)} teams")

    # Hard rules (R4, R11)
    all_picks = apply_hard_rules(all_picks)

    # R12 cooldown
    all_picks = apply_r12_cooldown(all_picks, cooldown)

    # Split qualified vs failed
    qualified = [p for p in all_picks if p.get("gate_result") == "PASS" and p.get("pick_score") is not None]
    failed = [p for p in all_picks if p.get("gate_result") != "PASS" or p.get("pick_score") is None]

    # Deduplicate
    qualified = deduplicate(qualified)
    # FIX 5: Remove correlated intra-game TOTAL + TEAM_TOTAL pairs (same direction)
    qualified = dedup_game_line_correlation(qualified)

    print(f"\n  Qualified picks (pre-context): {len(qualified)}")
    print(f"  Failed gates: {len(failed)}")

    # ── Split shadow sports out BEFORE context layer (don't burn API calls on shadow picks) ──
    shadow_picks  = [p for p in qualified if p.get("sport") in SHADOW_SPORTS]
    qualified     = [p for p in qualified if p.get("sport") not in SHADOW_SPORTS]

    # ── Context sanity layer (disabled — pass --context to enable) ───────────
    today_str = datetime.now().strftime("%Y-%m-%d")
    today_str_cs = today_str
    qualified, context_rejects = apply_context_sanity(
        qualified, today_str_cs, skip=not args.context, mode=args.mode
    )
    failed.extend(context_rejects)

    print(f"\n  Qualified picks (post-context): {len(qualified)}")
    print(f"  Failed gates: {len(failed)}")

    # Gate failure diagnostic
    gate_counts = defaultdict(int)
    for p in failed:
        gate_counts[p.get("gate_result", "UNKNOWN")] += 1
    print(f"\n  Gate failure breakdown:")
    for gate, count in sorted(gate_counts.items(), key=lambda x: -x[1]):
        print(f"    {gate}: {count}")

    # Show top 15 picks killed by gates (best edges that got filtered)
    interesting_fails = sorted(
        [p for p in failed if p.get("adj_edge", 0) > 0.03],
        key=lambda p: p.get("adj_edge", 0), reverse=True
    )[:15]
    if interesting_fails:
        print(f"\n  Top filtered picks (edge > 3% but failed gates):")
        print(f"  {'Player':<25} {'Stat':<6} {'Line':>5} {'Dir':<6} {'WP':>6} {'Edge':>6} {'Odds':>6} {'Gate':<12}")
        print(f"  {'-'*85}")
        for p in interesting_fails:
            print(f"  {p['player']:<25} {p['stat']:<6} {p['line']:>5} {p['direction']:<6} {p['win_prob']*100:>5.1f}% {p['adj_edge']*100:>5.1f}% {p['odds']:>6} {p.get('gate_result','?'):<12}")

    if not qualified:
        print("\n  [!] No qualifying picks found. Check CSV data and odds availability.")
        return

    # Log shadow picks to their own CSVs (never touches main pick_log)
    if not args.no_save:
        for sport, path in SHADOW_LOG_PATHS.items():
            sport_shadow = [p for p in shadow_picks if p.get("sport") == sport]
            if sport_shadow:
                log_picks(sport_shadow, args.mode, log_path_override=Path(path))

    # Base sizing for qualifying picks (Full Card)
    qualified = size_picks_base(qualified) if qualified else []

    # Apply caps
    qualified = apply_caps(qualified, {}) if qualified else []

    # Build Premium 5
    premium = apply_soft_rules_premium([], qualified) if qualified else []

    # Apply VAKE sizing to Premium 5 only (overwrites base sizing for these 5)
    premium = size_picks_vake(premium) if premium else []

    # ── KILLSHOT selection ────────────────────────────────────
    manual_ks = {n.strip() for n in args.killshot.split(",") if n.strip()} if args.killshot else set()
    killshots  = select_killshots(qualified, today_str, manual_players=manual_ks)
    # Promote tier label on matching premium picks so the card shows KILLSHOT
    ks_keys = {(p["player"], p["stat"], p["line"]) for p in killshots}
    for p in premium:
        if (p["player"], p["stat"], p["line"]) in ks_keys:
            p["tier"] = "KILLSHOT"
            p["size"] = _killshot_size(p.get("pick_score", 0))

    # Log only premium card picks — only on first run of the day (skip if card already posted)
    today_str_log = datetime.now().strftime("%Y-%m-%d")
    _card_was_already_up = _card_already_posted_today(today_str_log)
    if not args.no_save and not _card_was_already_up:
        log_picks(premium, args.mode, premium_picks=premium)

    # Safest 5
    safest5 = sorted(qualified, key=lambda p: p["win_prob"], reverse=True)[:5] if qualified else []

    # Build parlays
    safest6_parlay = build_safest6_parlay(qualified)
    sport_sigmas = {}
    for sport in all_players:
        sport_sigmas[sport] = GAME_SIGMA.get(sport, GAME_SIGMA["NBA"])
    alt_spread_parlay = build_alt_spread_parlay(all_game_lines, all_team_proj, sport_sigmas, all_alt_spreads)

    today = datetime.now().strftime("%B %d, %Y")

    # === PARLAYS-ONLY MODE ===
    if args.parlays_only:
        pout = []
        pout.append(f"{'='*50}")
        pout.append(f"PARLAYS ONLY — {today}")
        pout.append(f"{'='*50}")
        pout.append("")

        # Longshot Parlay
        pout.append(f"{'='*50}")
        pout.append("LONGSHOT PARLAY — 6 Safest Picks by Win Probability")
        pout.append(f"{'='*50}")
        if safest6_parlay and safest6_parlay["legs"]:
            for i, leg in enumerate(safest6_parlay["legs"], 1):
                side = f"{fmt_dir(leg['direction'])} {leg['line']}" if "direction" in leg else leg.get("team", "?")
                pout.append(f"  {i}. {leg['player']} {side} ({leg['stat']}) — WP: {leg['win_prob']*100:.1f}%")
            pout.append(f"  ────────────────────────────────")
            pout.append(f"  Combined Probability: {safest6_parlay['combined_prob']*100:.2f}%")
            pout.append(f"  Fair Odds: {fmt_odds(safest6_parlay['parlay_odds'])}")
        else:
            pout.append("  Not enough qualifying picks for 6-leg parlay.")
        pout.append("")

        # Alt Spread Parlay
        pout.append(f"{'='*50}")
        pout.append("ALT SPREAD PARLAY — 3 Legs @ ~-500 Each")
        pout.append(f"{'='*50}")
        if alt_spread_parlay and alt_spread_parlay["legs"]:
            pout.append(f"  Book: {alt_spread_parlay.get('book', 'N/A')}")
            pout.append("")
            for i, leg in enumerate(alt_spread_parlay["legs"], 1):
                sign = "+" if leg["alt_spread"] > 0 else ""
                odds_str = fmt_odds(leg["real_odds"]) if leg.get("real_odds") else "N/A"
                pout.append(f"  {i}. {leg['team']} {sign}{leg['alt_spread']:.1f} ({odds_str})")
                pout.append(f"     {leg['game']} | Margin: {leg['margin']:+.1f} | Cover: {leg['alt_cover_prob']*100:.1f}%")
            pout.append(f"  ────────────────────────────────")
            pout.append(f"  Parlay Odds: {fmt_odds(alt_spread_parlay['parlay_odds'])}")
            pout.append(f"  Model Cover Prob: {alt_spread_parlay['combined_prob']*100:.1f}%")
        else:
            pout.append("  Not enough qualifying NBA game lines for 3-leg parlay.")

        parlay_output = "\n".join(pout)
        print("\n" + parlay_output)
        print("\n  Done. Let's eat.\n")
        return

    # Format full output
    output = format_output(premium, safest5, qualified, all_picks, args.mode, today,
                           safest6_parlay=safest6_parlay, alt_spread_parlay=alt_spread_parlay)

    # Print
    print("\n" + "=" * 60)
    print(output)
    print("=" * 60)

    # Save
    if not args.no_save:
        folder = Path(OUTPUT_FOLDER)
        folder.mkdir(parents=True, exist_ok=True)
        out_path = args.output or str(folder / f"picks_{datetime.now().strftime('%Y-%m-%d')}.txt")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"\n  Saved: {out_path}")

    # Post to Discord
    today_str = datetime.now().strftime("%Y-%m-%d")
    suppress_ping = args.test  # --test suppresses @everyone on all posts

    # ── Manual pick logging mode ──────────────────────────────────────────────────
    if args.log_manual:
        print("\n  Log a manually posted pick to pick_log.csv")
        print("  (Use this for picks you posted in Discord without running the model)\n")
        today_manual = datetime.now().strftime("%Y-%m-%d")
        run_time_manual = datetime.now().strftime("%H:%M")
        player   = input("  Player name: ").strip()
        sport    = input("  Sport (NBA/NHL/MLB/NFL): ").strip().upper()
        team     = input("  Team abbreviation: ").strip().upper()
        stat     = input("  Stat (PTS/REB/AST/SOG/3PM etc): ").strip().upper()
        line     = input("  Line (e.g. 24.5): ").strip()
        direction = input("  Direction (over/under): ").strip().lower()
        odds     = input("  Odds (e.g. -115 or +105): ").strip()
        book     = input("  Book (e.g. draftkings): ").strip().lower()
        size     = input("  Size in units (e.g. 1.25): ").strip()
        game     = input("  Game (e.g. 'Boston Celtics @ Miami Heat'): ").strip()
        tier     = input("  Tier (T1/T1B/T2/T3/KILLSHOT or leave blank): ").strip().upper() or "MANUAL"
        log_path = Path(PICK_LOG_PATH)
        write_header = not log_path.exists() or log_path.stat().st_size == 0
        with open(log_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if write_header:
                writer.writerow([
                    "date", "run_time", "run_type", "sport", "player", "team", "stat", "line",
                    "direction", "proj", "win_prob", "edge", "odds", "book",
                    "tier", "pick_score", "size", "game", "mode", "result",
                    "closing_odds", "clv", "card_slot", "is_home",
                    "context_verdict", "context_reason", "context_score",
                ])
            writer.writerow([
                today_manual, run_time_manual, "manual", sport, player, team, stat, line,
                direction, "", "", "", odds, book,
                tier, "", size, game, "Default", "", "", "", "", "",
                "", "", "",  # context_verdict, context_reason, context_score
            ])
        print(f"\n  ✅ Logged: {player} {direction.upper()} {line} {stat} ({sport}) to pick_log.csv")
        print("\n  Done. Let's eat.\n")
        return

    # ── Repost mode: re-fire premium card + POTD from the most recent log entry ──
    if args.repost:
        log_path = Path(PICK_LOG_PATH)
        if log_path.exists():
            with open(log_path, "r", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                repost_rows = [r for r in reader if r.get("run_type", "primary") == "primary"
                               and r.get("date", "") == today_str]
            if repost_rows:
                # Reconstruct minimal pick dicts from log
                repost_picks = []
                for r in repost_rows[:5]:  # top 5 primary picks
                    repost_picks.append({
                        "player": r.get("player", ""), "team_abbrev": r.get("team", ""),
                        "stat": r.get("stat", ""), "line": float(r.get("line", 0)),
                        "direction": r.get("direction", ""),
                        "proj": float(r.get("proj", 0)), "win_prob": float(r.get("win_prob", 0)),
                        "adj_edge": float(r.get("edge", 0)), "raw_edge": float(r.get("edge", 0)),
                        "conf": 1.0, "odds": int(float(r.get("odds", -110))),
                        "book": r.get("book", ""), "game": r.get("game", ""),
                        "sport": r.get("sport", ""), "tier": r.get("tier", ""),
                        "size": float(r.get("size", 0)),
                        "pick_score":      float(r.get("pick_score", 0)),
                        "pick_type":       "prop",
                        "context_verdict": r.get("context_verdict", ""),
                        "context_reason":  r.get("context_reason", ""),
                        "context_score":   int(float(r.get("context_score", 0) or 0)),
                    })
                if repost_picks:
                    print(f"\n  [Discord] --repost: re-firing premium card + POTD for {today_str}…")
                    post_to_discord(repost_picks, args.mode, today_str, suppress_ping=suppress_ping)
                else:
                    print(f"\n  [Discord] --repost: no primary picks found for {today_str}")
            else:
                print(f"\n  [Discord] --repost: no picks logged for {today_str} yet")
        else:
            print("\n  [Discord] --repost: pick_log.csv not found")
        print("\n  Done. Let's eat.\n")
        return

    if args.no_discord:
        print("\n  [Discord] --no-discord flag set — skipping all Discord posts.")
    else:
        card_already_up = _card_was_already_up

        _save = not args.no_save
        if card_already_up:
            print("\n  [Discord] Card already posted today — skipping premium card, POTD, daily lay.")
            print("  [Discord] Running bonus drop check only...")
            post_extras_to_discord(qualified, save=_save)
        else:
            post_to_discord(premium, args.mode, today_str, suppress_ping=suppress_ping)
            post_card_announcement(premium, args.mode, today_str, suppress_ping=suppress_ping)
            post_extras_to_discord(qualified, save=_save)
            post_daily_lay(alt_spread_parlay, today_str, suppress_ping=suppress_ping, save=_save)

            # ── KILLSHOT posts → #killshot ────────────────────────
            post_killshots_to_discord(killshots, today, today_str, suppress_ping=suppress_ping)

            # ── Morning preview → #announcements ─────────────────
            try:
                from morning_preview import post_morning_preview, get_today_picks, load_pick_log
                _mp_rows = load_pick_log()
                _mp_picks = get_today_picks(_mp_rows, today_str)
                post_morning_preview(today_str, _mp_picks, suppress_ping=suppress_ping)
            except ImportError:
                pass   # morning_preview.py not present — non-fatal
            except Exception as _mp_err:
                print(f"  ⚠ Morning preview failed: {_mp_err}")

    print("\n  Done. Let's eat.\n")


if __name__ == "__main__":
    main()
