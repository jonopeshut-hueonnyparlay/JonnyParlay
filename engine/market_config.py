"""Runtime / market wiring constants for run_picks.py.

Books, APIs, sport keys, market-key maps, shadow/suspension sets, and team-name
maps. Extracted from run_picks.py (extract-and-re-export refactor, Step 8) and
re-imported there so existing call sites and `from run_picks import ...` keep
resolving. Imports only {stdlib, paths, secrets_config} — never run_picks or the
other constants modules.
"""

ODDS_BASE    = "https://api.the-odds-api.com/v4"
ODDS_REGIONS = "us,us2,us_ex"
API_SLEEP    = 1.3  # seconds between calls

SPORT_KEYS = {"NBA": "basketball_nba", "NHL": "icehockey_nhl",
              "NFL": "americanfootball_nfl", "MLB": "baseball_mlb",
              "WNBA": "basketball_wnba",
              "NCAAB": "basketball_ncaab", "NCAAF": "americanfootball_ncaaf"}

# Shadow sports — evaluated + logged internally but NEVER posted to Discord.
# Remove a sport from this set once it's proven profitable over a meaningful sample.
# WNBA went live 2026-06-09 (gate: ~100 graded picks post-dampener). Add a sport
# here (plus a SHADOW_LOG_PATHS entry) to re-shadow it.
SHADOW_SPORTS = set()

# Shadow stats — new markets with zero live track record. Picks are scored,
# sized, and logged to pick_log_shadow_stats.csv (NOT main pick_log.csv) but
# are NEVER included in the Discord card or bonus drops.
# Go-live gate: remove a stat once it has n>=30 logged picks at >=55% WR.
# Check pick_log_shadow_stats.csv manually or via analyze_picks.py --shadow-stats
SHADOW_STATS = {
    # NHL skater — added 2026-05-26, no live history
    "GOALS", "NHLPTS", "NHLBLK",
    # NHL goalie — added 2026-05-26, no live history
    "SV", "GA",
    # MLB pitcher — added 2026-05-26, no live history
    "ER", "BB", "PC",
    # MLB batter — added 2026-05-26, no live history
    "RBI", "RUNS",
    # Previously killed markets — rebuilt/re-enabled for shadow data accumulation
    "TB",    # G_TB_DISABLED removed; calc_tb_prob (Poisson convolution) was already the rebuild; NB r=1.3 fallback added
    "HRR",   # G_HRR_DISABLED removed; over at line<=0.5 blocked by G_HRR_OVER_LOW_LINE (2026-06-09 — 46.3% WR, r=1.5 too thin vs within-player ~1.1); under + over>0.5 still accumulating
    "NRFI",  # G_NRFI_DISABLED removed; was 28.9% WR on 211 shadow picks; re-shadowing for fresh data
    "YRFI",  # same generate_nrfi_picks path as NRFI; shadow alongside it
}

# Gate codes that should route to the shadow log instead of the failed/dropped pool.
# These are direction- or line-specific kills where the stat itself is still bettable on
# the other side or at higher lines. Picks hitting these gates go to pick_log_shadow_stats.csv.
SHADOW_GATE_CODES = {
    "G8B",           # AST over ≤4.5 (0-5 NBA record; ≥5.5 is live)
    "G8C",           # SOG under ≤3.5 (42-52% WR; >3.5 is live)
    "G8D",           # 3PM over ≤1.5 (50% actual vs 70% model; >1.5 is live)
    "G_TT_OVER_NBA", # TEAM_TOTAL over NBA (45.5% WR n=11; under is live; NBA-only block)
    "R4_REB_OVER",   # REB over (structural over-projection; under is live)
    "R4_REB_U25",    # REB under ≤2.5 (volatile at low lines; >2.5 under is live)
    "R11_AST_U25",   # AST under 1.5 and 2.5 (sub-elite lines; 0.5 and >2.5 are live)
    "G_HITS_OVER_SHADOW",  # HITS over (Plan 10 §T — was hard kill; shadow to accrue data, n≥30)
}

# Gates that are full-stat suspensions pending investigation — excluded from
# pick_log_blocked.csv because suspension frequency tells us nothing structural.
_BLOCKED_LOG_SKIP_GATES = frozenset({
    "G_SOG_SUSPENDED",
    "G_HA_SUSPENDED",
    "G_RA_DISABLED",
})
_BLOCKED_LOG_COLS = [
    "date", "sport", "player", "stat", "line", "direction",
    "odds", "edge", "win_prob", "gate_result",
]

# Each shadow sport logs to its own isolated CSV (keeps main pick_log clean).
# MLB went live 2026-05-20, WNBA 2026-06-09 — removed from shadow paths.
# Legacy data/pick_log_wnba.csv is still graded (grade_picks.py) and CLV-watched.
SHADOW_LOG_PATHS = {}

# Per-sport alt spread market names for the parlay builder
SPORT_ALT_MARKET = {
    "NBA": "alternate_spreads",
    "NHL": "alternate_puck_line",
    "MLB": "alternate_run_line",
}

PROP_MARKETS = {
    "NBA": [
        "player_assists", "player_rebounds", "player_points", "player_threes",
        "player_points_rebounds_assists", "player_points_rebounds",
        "player_points_assists", "player_rebounds_assists",
    ],
    "WNBA": [
        "player_assists", "player_rebounds", "player_points", "player_threes",
        "player_points_rebounds_assists", "player_points_rebounds",
        "player_points_assists", "player_rebounds_assists",
    ],
    "NHL": [
        "player_shots_on_goal", "player_assists",
        "player_goals", "player_points", "player_blocked_shots",
    ],
    "MLB": [
        "pitcher_outs", "pitcher_hits_allowed",
        "batter_hits", "batter_hits_runs_rbis",
        "batter_rbis", "batter_runs_scored", "pitcher_earned_runs",
    ],
}

# Maps API market key → our stat label (sport-agnostic)
MARKET_TO_STAT = {
    "player_assists": "AST", "player_rebounds": "REB",
    "player_points": "PTS", "player_threes": "3PM",
    "player_points_rebounds_assists": "PRA",
    "player_points_rebounds": "PR",
    "player_points_assists": "PA",
    "player_rebounds_assists": "RA",
    "player_shots_on_goal": "SOG",
    # NHL skater
    "player_goals": "GOALS",
    "player_blocked_shots": "NHLBLK",
    "goalie_saves": "SV",
    "goalie_goals_against": "GA",
    # player_points for NHL → NHLPTS (G+A) via MARKET_TO_STAT_OVERRIDE below
    # MLB pitcher
    "pitcher_outs": "OUTS",
    "pitcher_hits_allowed": "HA",
    "pitcher_earned_runs": "ER",
    "pitcher_walks": "BB",
    "pitcher_pitches_thrown": "PC",
    # MLB batter
    "batter_hits": "HITS", "batter_total_bases": "TB",
    "batter_hits_runs_rbis": "HRR",
    "batter_rbis": "RBI",
    "batter_runs_scored": "RUNS",
}

# Sport-specific market key overrides — applied after MARKET_TO_STAT when sport is known.
# Handles market keys shared between sports that map to different stat labels.
# player_points: NBA/WNBA → PTS (points scored); NHL → NHLPTS (goals + assists)
MARKET_TO_STAT_OVERRIDE = {
    "NHL": {"player_points": "NHLPTS"},
}

# WNBA team name → abbrev for the games-played opening gate. Odds pipeline carries
# full names; wnba_player_game_stats (EdgeModel DB) is keyed by team_abbrev.
# PHX appears as both PHO (2023-24) and PHX (2025+) in the DB — query matches either.
WNBA_TEAM_ABBREV = {
    "atlanta dream": "ATL", "chicago sky": "CHI", "connecticut sun": "CON",
    "dallas wings": "DAL", "golden state valkyries": "GSV", "indiana fever": "IND",
    "las vegas aces": "LVA", "los angeles sparks": "LAS", "minnesota lynx": "MIN",
    "new york liberty": "NYL", "phoenix mercury": "PHX", "portland fire": "PDX",
    "seattle storm": "SEA", "toronto tempo": "TOR", "washington mystics": "WAS",
}

# WNBA team_id → engine abbrev (audit P0.2, 2026-06-16). Source: nba_api static
# WNBA teams. data/team_sigmas_wnba.json is keyed by these numeric team_ids
# (the producer _calibrate_team_sigmas_wnba groups by team_id without mapping);
# consumers re-key to abbrev at load via wnba_sigmas_by_abbrev() so get_game_sigma
# lookups (keyed by abbrev) hit instead of silently falling back to league σ.
# NB: nba_api lists Phoenix as 'PHO' — we use the engine convention 'PHX' to match
# WNBA_TEAM_ABBREV. 13 historical teams; PDX/TOR are 2026 expansion teams with no
# sigma rows yet (correctly fall back to league σ until n_games>=20).
WNBA_ID_MAP = {
    1611661313: "NYL",  # New York Liberty
    1611661317: "PHX",  # Phoenix Mercury (nba_api 'PHO' → engine 'PHX')
    1611661319: "LVA",  # Las Vegas Aces
    1611661320: "LAS",  # Los Angeles Sparks
    1611661321: "DAL",  # Dallas Wings
    1611661322: "WAS",  # Washington Mystics
    1611661323: "CON",  # Connecticut Sun
    1611661324: "MIN",  # Minnesota Lynx
    1611661325: "IND",  # Indiana Fever
    1611661328: "SEA",  # Seattle Storm
    1611661329: "CHI",  # Chicago Sky
    1611661330: "ATL",  # Atlanta Dream
    1611661331: "GSV",  # Golden State Valkyries
}


def wnba_sigmas_by_abbrev(data: dict) -> dict:
    """Re-key a WNBA team_sigmas dict from numeric team_id → engine abbrev.

    Idempotent: numeric-id keys are mapped via WNBA_ID_MAP; non-numeric keys
    (already abbrev, e.g. after a producer-side fix) pass through unchanged.
    Unmapped numeric ids are dropped (none expected for the 13 historical teams).
    """
    out = {}
    for k, v in data.items():
        if str(k).isdigit():
            abbr = WNBA_ID_MAP.get(int(k))
            if abbr:
                out[abbr] = v
        else:
            out[k] = v
    return out


# Suspended stats — single source of truth (Plan 6 §13, 2026-06-05).
# check_prop_gates() blocks these via one lookup; _assert_killshot_invariants()
# asserts KILLSHOT_STAT_ALLOW never contains a suspended stat (the v2 PTS/SOG
# dead-entry problem took 5+ weeks to discover).
#   SOG: suspended 2026-06-05 pending distribution investigation — lift at July refit.
#   HA:  suspended 2026-06-05 pending model investigation — lift after WR ≥40% at n≥20.
#   RA:  disabled 2026-06-05 — 0W/7L (0% actual vs 56.7% model, n=11 live picks).
SUSPENDED_STATS = {
    "SOG": "G_SOG_SUSPENDED",
    "HA":  "G_HA_SUSPENDED",
    "RA":  "G_RA_DISABLED",
}

SLOW_BOOKS = frozenset({"fanatics", "hardrockbet", "betrivers"})  # 15-40 min injury lag — exploitable on --late-run

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
