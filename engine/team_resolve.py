"""Team-name resolution and matchup-sigma accessors.

Extracted from run_picks.py (extract-and-re-export refactor, Step 2) and
re-imported there so existing call sites and `from run_picks import ...` keep
resolving. Imports only {stdlib, market_config, calibrated} — never run_picks
or the other extracted modules.
"""
import math

from market_config import TEAM_ABBREV, WNBA_TEAM_ABBREV
from calibrated import GAME_SIGMA, _TEAM_SIGMAS, _TEAM_SIGMAS_MEANSQ, MLB_TEAM_RUN_R

_WNBA_ABBREVS = frozenset(WNBA_TEAM_ABBREV.values())


def _resolve_sigma_key(sport: str, team: str) -> str:
    """Resolve a team name/abbrev to the key used in _TEAM_SIGMAS[sport].

    WNBA names aren't in TEAM_ABBREV (only WNBA_TEAM_ABBREV), so resolve_team_abbrev
    misses them (P0.2). Route WNBA through WNBA_TEAM_ABBREV; everything else keeps
    the existing resolve_team_abbrev path.
    """
    if sport == "WNBA":
        low = (team or "").strip().lower()
        if low in WNBA_TEAM_ABBREV:
            return WNBA_TEAM_ABBREV[low]
        up = (team or "").strip().upper()
        if up in _WNBA_ABBREVS:  # already an abbrev
            return up
        return team
    return resolve_team_abbrev(team) or team


def get_game_sigma(sport: str, home_team: str, away_team: str, market: str) -> float:
    """Return matchup-specific sigma; falls back to GAME_SIGMA league average.

    Plan 6 §6 rewrite (2026-06-05): team sigmas are used only as a RELATIVE
    variability scaler on the per-market league sigma:
        sigma = sigma_league(market) * sqrt((σh² + σa²) / (2·σ̄²_league))
    The previous independence sum sqrt(σh²+σa²) dropped the home/away covariance
    term (ρ_NBA=+0.227), inflating NBA spread/ML sigma ~45% (≈5pp ML win-prob
    error) and silently overriding the calibrated per-market NHL sigmas.
    """
    league = GAME_SIGMA.get(sport, GAME_SIGMA["NBA"])
    league_sigma = league.get(market, 10.0)
    team_data = _TEAM_SIGMAS.get(sport, {})
    mean_sq = _TEAM_SIGMAS_MEANSQ.get(sport, 0.0)
    if not team_data or mean_sq <= 0:
        return league_sigma
    h_abbr = _resolve_sigma_key(sport, home_team)
    a_abbr = _resolve_sigma_key(sport, away_team)
    h = team_data.get(h_abbr)
    a = team_data.get(a_abbr)
    if (not h or not a
            or h.get("n_games", 0) < 20 or a.get("n_games", 0) < 20):
        return league_sigma
    if market in ("total", "ml", "spread"):
        scaler = math.sqrt((h["score_sigma"] ** 2 + a["score_sigma"] ** 2) / (2.0 * mean_sq))
        return league_sigma * scaler
    return league_sigma

def get_game_sigma_team(sport: str, team_abbr: str) -> float:
    """Return sigma for one team's scoring — used for team total picks."""
    league = GAME_SIGMA.get(sport, GAME_SIGMA["NBA"])
    league_sigma = league.get("team", 10.0)
    t_abbr = _resolve_sigma_key(sport, team_abbr)
    t = _TEAM_SIGMAS.get(sport, {}).get(t_abbr)
    return t["score_sigma"] if t and t.get("n_games", 0) >= 20 else league_sigma

def get_mlb_team_run_r(team_abbr: str) -> float:
    """Return per-team NB dispersion r for MLB run-scoring; falls back to MLB_TEAM_RUN_R."""
    data = _TEAM_SIGMAS.get("MLB", {})
    return data.get(team_abbr, {}).get("nb_r", MLB_TEAM_RUN_R)

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
    # 2. Last-word fallback — match on the unique last word of the team name
    #    (e.g. "Canadiens" → "montreal canadiens" → "MTL"). Avoids the
    #    ANA-in-CANADIENS substring collision that fired when tk="ANA" was
    #    checked against "MONTREAL CANADIENS" via tk in name_upper.
    last_word = api_name.strip().lower().split()[-1] if api_name.strip() else ""
    if last_word and len(last_word) > 3:
        for full_name, fabbr in TEAM_ABBREV.items():
            if last_word in full_name and fabbr in team_proj and team_proj[fabbr].get(field, 0) > 0:
                return team_proj[fabbr][field]
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
