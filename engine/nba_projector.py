"""nba_projector.py -- Architecture A+ NBA projection engine.

PTS formula (2P%/3P% decomposition with Bayesian padding):
    team_proj_fga   = team_avg_fga * pace_factor
    player_proj_fga = (USG%/100) * team_proj_fga * (proj_min/48)
    player_proj_3pa = fg3a_rate * player_proj_fga
    player_proj_2pa = (1 - fg3a_rate) * player_proj_fga
    player_proj_fta = fta_fga_ratio * player_proj_fga
    proj_pts        = 2PA*2*fg2_pct + 3PA*3*fg3_pct + FTA*ft_pct

    fg2_pct: Bayesian-padded to 300 FGA (stabilises fast)
    fg3_pct: Bayesian-padded to 750 FGA (stabilises slow)

All other stats:
    projected_stat = per_minute_rate x projected_minutes x matchup_factor x pace_factor

Role tiers: starter / sixth_man / rotation / spot / cold_start
EWMA span=10 for all rolling rates. Cold-start (<5 games on team) -> archetype prior.
"""
from __future__ import annotations
import datetime, logging, sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from projections_db import (
    DB_PATH, get_player_recent_games, get_player_season_game_count,
    get_team_pace, get_team_def_ratio, get_player_b2b_context,
    get_all_active_players, get_games_for_date, upsert_projection, get_conn,
    get_team_avg_fga,
)

log = logging.getLogger("nba_projector")
if not log.handlers:
    logging.basicConfig(level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S")

LEAGUE_AVG_PACE   = 99.5
LEAGUE_AVG_TOTAL  = 222.0
# Playoffs run slower / lower-scoring — separate baselines
LEAGUE_AVG_PACE_PO  = 96.5
LEAGUE_AVG_TOTAL_PO = 210.0
EWMA_SPAN         = 10
MIN_GAMES_FOR_TIER = 5

USG_ROLE_PRIOR = {
    "starter": 24.0, "sixth_man": 20.0, "rotation": 16.0,
    "spot": 13.0,    "cold_start": 20.0,
}

ROLE_MINUTE_PRIOR = {
    "starter": 32.0, "sixth_man": 24.0, "rotation": 19.0,
    "spot": 14.0, "cold_start": 15.0,
}

_ROLE_MIN_MINUTES = {
    "starter": 15.0, "sixth_man": 12.0, "rotation": 10.0,
    "spot": 8.0,  "cold_start": 5.0,
}

BLOWOUT_SPREAD_THRESHOLD = 12.0
BLOWOUT_MIN_REDUCTION    = 0.80
MATCHUP_CLIP             = (0.80, 1.20)
B2B_MINUTE_FACTOR = {
    "starter": 0.90, "sixth_man": 0.88, "rotation": 0.85,
    "spot": 0.82, "cold_start": 0.85,
}
PROJ_STATS    = ["pts", "reb", "ast", "fg3m", "stl", "blk", "tov"]
CURRENT_SEASON = "2025-26"

_ARCHETYPE_PER36 = {
    "G": {"pts": 14.5, "reb": 3.2, "ast": 5.8, "fg3m": 1.8, "stl": 1.2, "blk": 0.3, "tov": 2.5},
    "F": {"pts": 13.8, "reb": 5.8, "ast": 2.8, "fg3m": 1.2, "stl": 0.9, "blk": 0.6, "tov": 1.8},
    "C": {"pts": 13.2, "reb": 9.4, "ast": 1.8, "fg3m": 0.4, "stl": 0.7, "blk": 1.8, "tov": 2.0},
}

def _pos_group(pos):
    if not pos: return "F"
    p = str(pos).strip().upper()
    if p.startswith("G"): return "G"
    if p.startswith("C"): return "C"
    return "F"

def cold_start_rates(position):
    return dict(_ARCHETYPE_PER36[_pos_group(position)])

def classify_role(df):
    if df.empty: return "cold_start"
    recent = df.head(10)
    avg_min = recent["min"].mean()
    starter_rate = recent["starter_flag"].mean()
    if starter_rate >= 0.60 and avg_min >= 26: return "starter"
    if avg_min >= 20: return "sixth_man"
    if avg_min >= 12: return "rotation"
    if avg_min >= 5:  return "spot"
    return "cold_start"

def compute_per_minute_rates(df):
    if df.empty: return {s: 0.0 for s in PROJ_STATS}
    d = df.sort_values("game_date").copy()
    if d.empty: return {s: 0.0 for s in PROJ_STATS}
    rates = {}
    for stat in PROJ_STATS:
        if stat not in d.columns:
            rates[stat] = 0.0; continue
        per_min  = d[stat] / d["min"]
        weighted = per_min * d["era_weight"]
        ewma_w   = weighted.ewm(span=EWMA_SPAN, min_periods=1).mean().iloc[-1]
        ewma_e   = d["era_weight"].ewm(span=EWMA_SPAN, min_periods=1).mean().iloc[-1]
        rates[stat] = float(ewma_w / max(ewma_e, 1e-6))
    return rates

def compute_shooting_rates(df) -> dict:
    """Compute EWMA shooting efficiency rates for FGA/FTA PTS decomposition.

    Returns dict with keys:
        fg2_pct        — Bayesian-padded 2P% (stabilises at ~300 FGA)
        fg3_pct        — Bayesian-padded 3P% (stabilises at ~750 FGA)
        fg3a_rate      — EWMA of FG3A/FGA  (share of shots from 3)
        ft_pct         — EWMA FT%
        fta_fga_ratio  — EWMA FTA/FGA
        usg_pct        — EWMA USG%  (percentage, e.g. 22.5)

    Composite eFG% is retired: separating 2P% and 3P% avoids conflating two
    distributions with different stabilisation rates (300 vs 750 attempts).

    Bayesian padding formula (Kostya Medvedovsky / FantasyLabs approach):
        stabilised_2p = (career_2PM + 300 * LG_2P) / (career_2PA + 300)
        stabilised_3p = (career_3PM + 750 * LG_3P) / (career_3PA + 750)
    We approximate career volume with the full df window (up to 30 games).
    """
    # League-average constants — calibrated from 2024-25 DB (Apr 30 2026)
    # Previously used stale estimates; updated from actual player_game_stats:
    #   fg2_pct: 0.5438, fg3_pct: 0.3598, fg3a_rate: 0.4205, fta/fga: 0.2450
    LG_2P_PCT    = 0.544   # league avg 2P%  (was 0.532 — biased Bayesian anchor low)
    LG_3P_PCT    = 0.360   # league avg 3P%
    LG_FT_PCT    = 0.780
    LG_FG3A_RATE = 0.420   # ~42% of FGA are 3PA league-wide (was 0.385 — stale)
    LG_FTA_FGA   = 0.245   # FTA/FGA ratio (was 0.280 — inflating FT projection +14%)

    if df.empty:
        return {
            "fg2_pct":       LG_2P_PCT,
            "fg3_pct":       LG_3P_PCT,
            "fg3a_rate":     LG_FG3A_RATE,
            "ft_pct":        LG_FT_PCT,
            "fta_fga_ratio": LG_FTA_FGA,
            "usg_pct":       20.0,
        }

    d = df.sort_values("game_date").copy()

    # ------------------------------------------------------------------ #
    # 2P% — Bayesian padding to 300 FGA equivalent                        #
    # ------------------------------------------------------------------ #
    has_fg3a = "fg3a" in d.columns
    if has_fg3a:
        d_fg3a = d["fg3a"].fillna(0)
        fg2a   = (d["fga"] - d_fg3a).clip(lower=0)
        fg2m   = (d["fgm"] - d["fg3m"]).clip(lower=0)
    else:
        # Approximate: assume LG_FG3A_RATE of attempts are 3PA
        fg2a = (d["fga"] * (1 - LG_FG3A_RATE)).clip(lower=0)
        fg2m = (d["fgm"] - d["fg3m"]).clip(lower=0)

    total_fg2a = float(fg2a.sum())
    total_fg2m = float(fg2m.sum())
    PAD_2P     = 300.0
    fg2_pct    = (total_fg2m + PAD_2P * LG_2P_PCT) / (total_fg2a + PAD_2P)
    fg2_pct    = float(np.clip(fg2_pct, 0.35, 0.75))

    # ------------------------------------------------------------------ #
    # 3P% — Bayesian padding to 750 FGA equivalent                        #
    # ------------------------------------------------------------------ #
    total_fg3a = float(d["fg3a"].sum()) if has_fg3a else float((d["fga"] * LG_FG3A_RATE).sum())
    total_fg3m = float(d["fg3m"].sum())
    PAD_3P     = 750.0
    fg3_pct    = (total_fg3m + PAD_3P * LG_3P_PCT) / (total_fg3a + PAD_3P)
    fg3_pct    = float(np.clip(fg3_pct, 0.20, 0.55))

    # ------------------------------------------------------------------ #
    # FG3A rate — EWMA of what fraction of this player's FGA are 3PA      #
    # ------------------------------------------------------------------ #
    mask_fga = d["fga"] > 0
    if has_fg3a:
        fg3a_series = np.where(mask_fga, d["fg3a"] / d["fga"], np.nan)
    else:
        fg3a_series = np.full(len(d), LG_FG3A_RATE, dtype=float)
    fg3a_vals  = pd.Series(fg3a_series).ffill().fillna(LG_FG3A_RATE)
    fg3a_rate  = float(fg3a_vals.ewm(span=EWMA_SPAN, min_periods=1).mean().iloc[-1])
    fg3a_rate  = float(np.clip(fg3a_rate, 0.0, 0.85))

    # ------------------------------------------------------------------ #
    # FT% — EWMA                                                           #
    # ------------------------------------------------------------------ #
    mask_fta  = d["fta"] > 0
    ft_series = np.where(mask_fta, d["ftm"] / d["fta"], np.nan)
    ft_vals   = pd.Series(ft_series).ffill().fillna(LG_FT_PCT)
    ft_pct    = float(ft_vals.ewm(span=EWMA_SPAN, min_periods=1).mean().iloc[-1])
    ft_pct    = float(np.clip(ft_pct, 0.40, 1.00))

    # ------------------------------------------------------------------ #
    # FTA/FGA ratio                                                        #
    # ------------------------------------------------------------------ #
    ratio_series  = np.where(mask_fga, d["fta"] / d["fga"], np.nan)
    ratio_vals    = pd.Series(ratio_series).ffill().fillna(LG_FTA_FGA)
    fta_fga_ratio = float(ratio_vals.ewm(span=EWMA_SPAN, min_periods=1).mean().iloc[-1])
    fta_fga_ratio = float(np.clip(fta_fga_ratio, 0.0, 1.20))

    # ------------------------------------------------------------------ #
    # USG%                                                                 #
    # ------------------------------------------------------------------ #
    has_team = all(c in d.columns for c in ("tm_fga", "tm_fta", "tm_tov", "tm_min"))
    if has_team:
        tm_denom = d["tm_fga"] + 0.44 * d["tm_fta"] + d["tm_tov"]
        pl_num   = d["fga"]   + 0.44 * d["fta"]   + d["tov"]
        usg_raw  = np.where(
            (d["min"] > 0) & (tm_denom > 0),
            100.0 * pl_num * (d["tm_min"] / 5.0) / (d["min"] * tm_denom),
            np.nan,
        )
        usg_vals = pd.Series(usg_raw).ffill().fillna(20.0)
        usg_pct  = float(usg_vals.ewm(span=EWMA_SPAN, min_periods=1).mean().iloc[-1])
    else:
        usg_pct = 20.0
    usg_pct = float(np.clip(usg_pct, 5.0, 45.0))

    return {
        "fg2_pct":       fg2_pct,
        "fg3_pct":       fg3_pct,
        "fg3a_rate":     fg3a_rate,
        "ft_pct":        ft_pct,
        "fta_fga_ratio": fta_fga_ratio,
        "usg_pct":       usg_pct,
    }


def project_minutes(role, df, b2b, spread=None, injury_minutes_override=None):
    if injury_minutes_override is not None:
        return float(injury_minutes_override)
    if not df.empty:
        clean = df.sort_values("game_date")
        ewma_min = float(clean["min"].ewm(span=EWMA_SPAN, min_periods=1).mean().iloc[-1])
        weight = min(len(clean) / 20.0, 1.0)
    else:
        ewma_min = ROLE_MINUTE_PRIOR[role]
        weight   = 0.0
    prior    = ROLE_MINUTE_PRIOR[role]
    proj_min = weight * ewma_min + (1 - weight) * prior
    if b2b.get("is_b2b"):
        proj_min *= B2B_MINUTE_FACTOR.get(role, 0.88)
    if spread is not None and abs(spread) >= BLOWOUT_SPREAD_THRESHOLD:
        proj_min *= BLOWOUT_MIN_REDUCTION
    proj_min = max(proj_min, 0.0)
    proj_min = min(proj_min, 42.0 if role == "starter" else 38.0)
    return proj_min

def compute_distribution(mean, stat, role, n_games):
    _CV = {"pts": 0.35, "reb": 0.45, "ast": 0.50, "fg3m": 0.65, "stl": 0.80, "blk": 0.85, "tov": 0.55}
    cv          = _CV.get(stat, 0.50)
    uncertainty = 1.0 + max(0, (20 - n_games) / 40.0)
    std         = mean * cv * uncertainty
    p25         = max(0.0, mean - 0.674 * std)
    p75         = mean + 0.674 * std
    return round(p25, 2), round(mean, 2), round(p75, 2)

def project_player(
    player_id, player_name, position, team_id, opp_team_id,
    game_id, game_date, season=CURRENT_SEASON,
    season_type="Regular Season",
    implied_total=None, spread=None, injury_status="",
    injury_minutes_override=None, db_path=DB_PATH,
):
    if injury_status in ("O", "OUT"):
        return None

    df            = get_player_recent_games(player_id, game_date, n_games=30,
                                            season_filter=season, db_path=db_path)
    games_on_team = get_player_season_game_count(player_id, season, team_id, db_path)
    b2b           = get_player_b2b_context(player_id, game_date, db_path)

    is_cold_start = games_on_team < MIN_GAMES_FOR_TIER
    if is_cold_start:
        role     = "cold_start"
        rates    = cold_start_rates(position)
        rates    = {k: v / 36.0 for k, v in rates.items()}
        df_clean = df
    else:
        role = classify_role(df)

        # Injury role promotion: backup absorbing star minutes gets promoted so
        # the min_minutes filter and prior both reflect the elevated duty.
        if injury_minutes_override is not None and not df.empty:
            ewma_baseline = float(
                df.sort_values("game_date")["min"]
                  .ewm(span=EWMA_SPAN, min_periods=1).mean().iloc[-1]
            )
            override_delta = injury_minutes_override - ewma_baseline
            if override_delta >= 6.0 and role == "spot":
                role = "rotation"
            elif override_delta >= 6.0 and role == "rotation":
                role = "sixth_man"
            elif override_delta >= 8.0 and role == "sixth_man":
                role = "starter"

        min_min  = _ROLE_MIN_MINUTES[role]
        df_clean = df[df["min"] >= min_min].copy()
        rates    = compute_per_minute_rates(df_clean)

    proj_min = project_minutes(role, df_clean, b2b, spread=spread,
                               injury_minutes_override=injury_minutes_override)
    if proj_min < 1.0:
        return None

    is_playoff  = season_type == "Playoffs"
    # Always use Regular Season pace data (reliable); playoff pace DB entries
    # are often missing, causing the fallback (99.5) to inflate projections.
    # Playoff adjustment is handled by PLAYOFF_DEFLATOR below instead.
    team_pace   = get_team_pace(team_id,     season, "Regular Season", db_path)
    opp_pace    = get_team_pace(opp_team_id, season, "Regular Season", db_path)
    game_pace   = (team_pace + opp_pace) / 2.0
    pace_factor = game_pace / LEAGUE_AVG_PACE
    if implied_total is not None and implied_total > 0:
        pace_factor = implied_total / LEAGUE_AVG_TOTAL

    pg = _pos_group(position)
    matchup_pts = float(np.clip(
        get_team_def_ratio(opp_team_id, pg, "pts", season, db_path), *MATCHUP_CLIP))
    matchup_reb = float(np.clip(
        get_team_def_ratio(opp_team_id, pg, "reb", season, db_path), *MATCHUP_CLIP))
    matchup_ast = float(np.clip(
        get_team_def_ratio(opp_team_id, pg, "ast", season, db_path), *MATCHUP_CLIP))
    matchup_factors = {
        "pts": matchup_pts, "reb": matchup_reb, "ast": matchup_ast,
        "fg3m": matchup_pts, "stl": 1.0, "blk": 1.0, "tov": 1.0,
    }

    # --- Shooting efficiency rates for 2P%/3P% decomposition ---
    shoot         = compute_shooting_rates(df_clean)
    fg2_pct       = shoot["fg2_pct"]
    fg3_pct       = shoot["fg3_pct"]
    fg3a_rate     = shoot["fg3a_rate"]        # fraction of FGA that are 3PA
    ft_pct        = shoot["ft_pct"]
    fta_fga_ratio = shoot["fta_fga_ratio"]
    usg_pct       = shoot["usg_pct"]          # percentage, e.g. 22.5

    projections = {}

    # PTS: 2P% / 3P% decomposition
    #   team_proj_fga   = historical team FGA scaled by pace
    #   player_proj_fga = player's usage share × team FGA × minutes fraction
    #   player_proj_3pa = fg3a_rate × player_proj_fga
    #   player_proj_2pa = (1 - fg3a_rate) × player_proj_fga
    #   player_proj_fta = fta_fga_ratio × player_proj_fga
    #   proj_pts        = 2PA×2×fg2% + 3PA×3×fg3% + FTA×ft%
    #
    #   2P% and 3P% use Bayesian padding (300 / 750 FGA) to stabilise noisy
    #   per-game rates — replaces composite eFG% which conflated two
    #   distributions with different stabilisation timescales.
    team_avg_fga    = get_team_avg_fga(team_id, game_date, season, db_path=db_path)
    team_proj_fga   = team_avg_fga * pace_factor
    player_proj_fga = (usg_pct / 100.0) * team_proj_fga * (proj_min / 48.0)
    player_proj_3pa = fg3a_rate * player_proj_fga
    player_proj_2pa = (1.0 - fg3a_rate) * player_proj_fga
    player_proj_fta = fta_fga_ratio * player_proj_fga
    proj_pts        = (player_proj_2pa * 2.0 * fg2_pct
                       + player_proj_3pa * 3.0 * fg3_pct
                       + player_proj_fta * ft_pct)
    # NOTE: matchup opponent adjustment disabled — get_team_def_ratio averages
    # >1.0 across dataset (data sparsity artefact). Will replace with proper
    # position-differentiated DvP model in next iteration.
    projections["pts"] = max(0.0, round(proj_pts, 2))

    # All other stats: per-minute rates (unchanged)
    for stat in PROJ_STATS:
        if stat == "pts":
            continue
        rate = rates.get(stat, 0.0)
        mf   = matchup_factors.get(stat, 1.0)
        projections[stat] = max(0.0, round(rate * proj_min * mf * pace_factor, 2))

    # Playoff calibration: regular-season per-minute rates over-project in
    # playoffs due to tighter defense and shorter rotations.
    if is_playoff:
        PLAYOFF_DEFLATOR = 0.92
        for stat in PROJ_STATS:
            projections[stat] = round(projections[stat] * PLAYOFF_DEFLATOR, 2)

    n_games = len(df_clean)
    pts_p25,  pts_med,  pts_p75  = compute_distribution(projections["pts"],  "pts",  role, n_games)
    reb_p25,  reb_med,  reb_p75  = compute_distribution(projections["reb"],  "reb",  role, n_games)
    ast_p25,  ast_med,  ast_p75  = compute_distribution(projections["ast"],  "ast",  role, n_games)
    fg3m_p25, fg3m_med, fg3m_p75 = compute_distribution(projections["fg3m"], "fg3m", role, n_games)

    dk_std = round(projections["pts"] * 0.35, 2)
    run_ts = datetime.datetime.utcnow().isoformat(timespec="seconds")

    return {
        "run_date": game_date, "run_ts": run_ts,
        "player_id": player_id, "player_name": player_name,
        "team_id": team_id, "opp_team_id": opp_team_id, "game_id": game_id,
        "role_tier": role,
        "proj_min":  round(proj_min, 2),
        "proj_pts":  pts_med,  "proj_pts_p25":  pts_p25,  "proj_pts_p75":  pts_p75,
        "proj_reb":  reb_med,  "proj_reb_p25":  reb_p25,  "proj_reb_p75":  reb_p75,
        "proj_ast":  ast_med,  "proj_ast_p25":  ast_p25,  "proj_ast_p75":  ast_p75,
        "proj_fg3m": fg3m_med, "proj_fg3m_p25": fg3m_p25, "proj_fg3m_p75": fg3m_p75,
        "proj_stl":  projections["stl"],
        "proj_blk":  projections["blk"],
        "proj_tov":  projections["tov"],
        "injury_status": injury_status,
        "pace_factor":        round(pace_factor, 4),
        "matchup_factor_pts": round(matchup_pts, 4),
        "matchup_factor_reb": round(matchup_reb, 4),
        "matchup_factor_ast": round(matchup_ast, 4),
        "source": "custom_v1",
        "dk_std": dk_std,
    }

def run_projections(
    game_date, season=CURRENT_SEASON,
    implied_totals=None, spreads=None,
    injury_statuses=None, injury_minutes_overrides=None,
    db_path=DB_PATH, persist=True,
):
    implied_totals           = implied_totals or {}
    spreads                  = spreads or {}
    injury_statuses          = injury_statuses or {}
    injury_minutes_overrides = injury_minutes_overrides or {}

    games = get_games_for_date(game_date, db_path)
    if games.empty:
        log.warning("No games found for %s", game_date)
        return []

    game_implied    = {}
    game_spread     = {}
    game_season_type = {}
    team_to_game    = {}

    for _, g in games.iterrows():
        gid = str(g["game_id"])
        ht  = int(g["home_team_id"])
        at  = int(g["away_team_id"])
        team_to_game[ht] = (gid, at)
        team_to_game[at] = (gid, ht)
        if gid in implied_totals: game_implied[gid] = implied_totals[gid]
        if gid in spreads:        game_spread[gid]  = spreads[gid]
        game_season_type[gid] = g.get("season_type", "Regular Season") or "Regular Season"

    active = get_all_active_players(game_date, min_recent_games=2, db_path=db_path)
    active = active[active["team_id"].isin(team_to_game.keys())]

    log.info("Projecting %d players for %s ...", len(active), game_date)
    results = []
    conn = get_conn(db_path) if persist else None

    for _, row in active.iterrows():
        pid     = int(row["player_id"])
        team_id = int(row["team_id"])
        if team_id not in team_to_game: continue
        game_id, opp_team_id = team_to_game[team_id]
        status = injury_statuses.get(pid, "")
        if status in ("O", "OUT"): continue
        try:
            proj = project_player(
                player_id=pid, player_name=row["name"],
                position=row.get("position"),
                team_id=team_id, opp_team_id=opp_team_id,
                game_id=game_id, game_date=game_date, season=season,
                season_type=game_season_type.get(game_id, "Regular Season"),
                implied_total=game_implied.get(game_id),
                spread=game_spread.get(game_id),
                injury_status=status,
                injury_minutes_override=injury_minutes_overrides.get(pid),
                db_path=db_path,
            )
        except Exception as exc:
            log.debug("project_player error %s (%d): %s", row["name"], pid, exc)
            continue
        if proj is None: continue
        results.append(proj)
        if persist and conn is not None:
            try:   upsert_projection(conn, proj)
            except Exception as exc:
                log.debug("upsert error %d: %s", pid, exc)

    if persist and conn is not None:
        conn.commit(); conn.close()

    log.info("Projections complete: %d players", len(results))
    return results

def _main():
    import argparse
    parser = argparse.ArgumentParser(description="Run NBA projections for a date")
    parser.add_argument("--date",   default=str(datetime.date.today()))
    parser.add_argument("--season", default=CURRENT_SEASON)
    parser.add_argument("--db",     default=DB_PATH)
    parser.add_argument("--no-persist", action="store_true")
    parser.add_argument("--top",    type=int, default=20)
    args = parser.parse_args()

    results = run_projections(
        game_date=args.date, season=args.season,
        db_path=args.db, persist=not args.no_persist,
    )
    if not results:
        print("No projections generated.")
        return

    df   = pd.DataFrame(results).sort_values("proj_pts", ascending=False)
    cols = ["player_name", "role_tier", "proj_min", "proj_pts",
            "proj_reb", "proj_ast", "proj_fg3m", "pace_factor",
            "matchup_factor_pts", "injury_status"]
    print(df[cols].head(args.top).to_string(index=False))
    print(f"\nTotal: {len(df)} players projected.")

if __name__ == "__main__":
    _main()
proj_pts", ascending=False)
    cols = ["player_name", "role_tier", "proj_min", "proj_pts",
            "proj_reb", "proj_ast", "proj_fg3m", "pace_factor",
            "matchup_factor_pts", "injury_status"]
    print(df[cols].head(args.top).to_string(index=False))
    print(f"\nTotal: {len(df)} players projected.")

if __name__ == "__main__":
    _main()
