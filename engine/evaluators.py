"""Prop / game-line / F5 / NRFI evaluators + prop↔projection matcher.

Extracted from run_picks.py (extract-and-re-export refactor, Step 13) and
re-imported there so existing call sites and `from run_picks import ...` keep
resolving. Imports only {stdlib, book_names, market_config, thresholds,
calibrated, quant.*, prob_core, sizing_core, team_resolve, gates} — never
run_picks or the other extracted modules.
"""
import logging
import math

from book_names import CO_LEGAL_BOOKS
from market_config import TEAM_ABBREV
from thresholds import BLEND_ALPHA, F5_SCALAR
from calibrated import (
    COMBO_COMPONENTS, COMBO_STATS, F5_SIGMA, GAME_SIGMA, MLB_TEAM_RUN_R,
    PITCHER_STATS, TIERS, _FIXED_SPREAD_SPORTS,
)
from quant.distributions import normal_cdf, negbinom_pmf, negbinom_cdf
from quant.odds import implied_prob, no_vig, is_decimal_leak
from quant.derived import mlb_ml_from_nb, calc_tb_prob, calc_edge
from game_line_pricing import team_total_mlb_nb
from prob_core import _platt_calibrate_prop, calc_prop_prob, calc_combo_prob, pick_score
from sizing_core import apply_bm_shrinkage, get_tier, get_tier_min_edge
from team_resolve import (
    find_team_proj, get_game_sigma, get_game_sigma_team, get_mlb_team_run_r,
    get_team_abbrev, resolve_team_abbrev,
)
from gates import check_prop_gates, check_game_gates

try:
    import game_line_handover as _glh
except Exception:  # pragma: no cover
    _glh = None

logger = logging.getLogger("jonnyparlay")


def _gl_today_et() -> str:
    """ET run-date for matching EdgeModel mlb_game_projections (blank on failure)."""
    try:
        from datetime import datetime as _dt
        from zoneinfo import ZoneInfo
        return _dt.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
    except Exception:
        return ""


def match_props_to_projections(props, players):
    """Match API player props to SaberSim projections."""
    player_map = {p["name_key"]: p for p in players}

    matched = []
    for prop in props:
        pk = prop["player_key"]
        if pk in player_map:
            proj_player = player_map[pk]
            proj_val = proj_player.get(prop["stat"], 0)
            if proj_val == 0 and prop["stat"] in COMBO_STATS:
                proj_val = sum(
                    float(proj_player.get(c, 0) or 0)
                    for c in COMBO_COMPONENTS[prop["stat"]]
                )
            if proj_val > 0:
                prop["proj"] = proj_val
                prop["proj_player"] = proj_player
                matched.append(prop)

    return matched

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

        # MLB pitcher confirmation gate: skip K/OUTS/HA when SP is unconfirmed (TBD)
        if stat in PITCHER_STATS and prop.get("proj_player", {}).get("is_pitcher"):
            if prop.get("proj_player", {}).get("status", "").lower() != "confirmed":
                continue

        # H3: pass player's dk_std as sigma_override so high-var players (Strus, Caruso etc.)
        # use their empirically observed σ instead of the flat 0.35×proj formula.
        # Only applies to Normal-distribution stats (PTS etc.); Poisson/NB paths ignore it.
        _dk_std = prop.get("proj_player", {}).get("dk_std", 0.0) or 0.0
        _sport = prop.get("sport", "")

        # Calculate probabilities
        _pp = prop.get("proj_player", {})
        if stat == "TB" and _pp.get("TB_1B") is not None:
            over_p, under_p = calc_tb_prob(
                _pp.get("TB_1B", 0.0), _pp.get("TB_2B", 0.0),
                _pp.get("TB_3B", 0.0), _pp.get("TB_HR", 0.0), line,
            )
        elif stat in COMBO_STATS:
            over_p, under_p = calc_combo_prob(_pp, stat, line, sport=_sport)
        else:
            over_p, under_p = calc_prop_prob(proj, line, stat, sigma_override=_dk_std, sport=_sport)

        # v4: save raw over_p before Platt so calibrate_platt.py can fit on
        # the actual model output without double-calibration bias.
        over_p_raw = over_p

        # I6: Confidence modifier — penalizes early-season or low-sample players.
        # Applied BEFORE Platt so calibration acts on the confidence-adjusted probability.
        # Low-GP players have inflated model confidence — pull toward 50% first, then calibrate.
        proj_player = prop.get("proj_player", {})
        gp = proj_player.get("GP", proj_player.get("gp", 0))
        if gp and int(gp) < 10:
            conf = 0.70  # Very early season — heavy penalty
        elif gp and int(gp) < 20:
            conf = 0.85  # Early season — moderate penalty
        else:
            conf = 1.0   # Full confidence (20+ games or GP not available)
        if conf < 1.0:
            over_p = 0.50 + (over_p - 0.50) * conf
            under_p = 1.0 - over_p

        # P9: Platt calibration — compress overconfident win_probs toward actual hit rate.
        # Calibrate confidence-adjusted over_p; derive under_p to preserve over+under=1.
        # Skip for MLB: Platt was fitted on NBA+NHL props only; applying it to MLB
        # stat distributions (K%, OUTS, HA) would mis-calibrate until an MLB sample exists.
        # WNBA is intentionally included (not MLB, so Platt applies). NBA+NHL coefficients
        # are a reasonable approximation for WNBA; WNBA-specific refit pending sample growth.
        # Skip for combo stats (PRA/PR/PA/RA): Platt was fitted on single-stat props;
        # the joint-Normal combo probability has a different shape and will be mis-calibrated
        # until a separate combo sample exists. TODO: refit at SGP Platt gate (100 scored slips).
        if _sport != "MLB" and stat not in COMBO_STATS:
            over_p = _platt_calibrate_prop(over_p)
            under_p = 1.0 - over_p

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

            # Tier first — BM shrinkage weight is tier-keyed (sport-aware: NHL AST → T3)
            tier = get_tier(stat, direction, sport=_sport)
            if tier is None:
                continue  # banned

            # Plan 9 §9F: Baker–McHale shrinkage toward market-implied prob.
            # Applied to ALL props including MLB and combos — those skip Platt and
            # are the LEAST calibrated paths (MLB uncalibrated, combos ~5pp inflated),
            # so shrinkage toward market is most defensible exactly there.
            # Edge recomputed from the shrunk prob (same formula: model_p − no-vig_p).
            win_prob = apply_bm_shrinkage(win_prob, odds, tier, nv_prob=nv_prob)
            raw_edge = win_prob - nv_prob

            adj_edge = raw_edge * conf
            # Confidence already applied to over_p/under_p before Platt; adj_wp == win_prob.
            adj_wp = win_prob

            # Custom-engine pick_score signals (absent/None for SaberSim CSV runs).
            _cold_start_subtype = proj_player.get("cold_start_subtype")
            _injury_trigger     = bool(proj_player.get("injury_trigger", False))

            # Get team abbreviation from CSV match
            csv_team = proj_player.get("team", "")

            pick = {
                "player": prop["player"],
                "team_abbrev": csv_team.upper() if csv_team else get_team_abbrev(prop.get("game", "")),
                "stat": stat,
                "line": line,
                "direction": direction,
                "proj": proj,
                "win_prob": adj_wp,
                "over_p_raw": over_p_raw,  # v4: pre-Platt over_p for calibrate_platt.py
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
                "pts_cv":             proj_player.get("pts_cv"),
                "cold_start_subtype": _cold_start_subtype,
                "injury_trigger":     _injury_trigger,
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

            # WNBA early-season edge-mult removed 2026-06-05 (Plan 6 §14, 9b):
            # the dampener now lives in calc_prop_prob as sigma inflation, so
            # adj_wp/adj_edge already carry the dampened confidence — applying
            # an edge mult here again would double-count it.
            pick["pick_score"] = pick_score(adj_wp, adj_edge, mode, tier=tier,
                                            cold_start_subtype=_cold_start_subtype,
                                            injury_trigger=_injury_trigger, stat=stat)
            if adj_edge >= 0.15:
                logger.warning("[LARGE-EDGE] %s %s %s %.1f%% edge — verify lineup/injury before accepting",
                            prop["player"], stat, direction, adj_edge * 100)
            picks.append(pick)

    return picks

def evaluate_game_lines(game_lines, team_totals, players, sport, mode="Default"):
    """Evaluate game lines (totals, spreads, MLs, team totals)."""
    picks = []
    sigmas = GAME_SIGMA.get(sport)
    if sigmas is None:
        logger.warning("evaluate_game_lines: no GAME_SIGMA entry for sport %r — skipping game lines", sport)
        return []

    # Build team projection map
    team_proj = {}
    for p in players:
        team = p["team"].upper()
        if team not in team_proj:
            team_proj[team] = {"saber_total": p["saber_total"], "saber_team": p["saber_team"]}

    # Readiness-gated EdgeModel game-line handover (MLB only; DORMANT -> ({}, {}) ->
    # no blend, byte-identical -> replay byte-identical). Fail-soft.
    _gl_w, _gl_em = ({}, {})
    if _glh is not None and (sport or "").upper() == "MLB":
        try:
            _gl_w, _gl_em = _glh.prepare(_gl_today_et())
        except Exception:
            _gl_w, _gl_em = ({}, {})

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
        # Use resolve_team_abbrev-based lookup (same as find_team_proj) to
        # avoid substring collision bugs (e.g. "LAD" not in "LOS ANGELES DODGERS")
        proj = find_team_proj(gl["home"], team_proj, field="saber_total") or \
               find_team_proj(gl["away"], team_proj, field="saber_total")
        if proj is None or proj <= 0:
            continue

        # Blend SaberSim total with market line
        proj = line + BLEND_ALPHA * (proj - line)
        if _gl_w:  # readiness-gated EdgeModel TOTAL handover (dormant -> unchanged)
            proj = _glh.blend_total(_gl_w, _gl_em, resolve_team_abbrev(gl["home"]),
                                    resolve_team_abbrev(gl["away"]), proj)

        sigma = get_game_sigma(sport, home_name, away_name, "total")
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
                pick["pick_score"] = pick_score(wp, edge, mode, tier=pick["tier"])
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
        sigma = get_game_sigma(sport, home_name, away_name, "spread")

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
            home_abbr = TEAM_ABBREV.get(home_name.lower()) or resolve_team_abbrev(home_name) or home_name[:3].upper()
            away_abbr = TEAM_ABBREV.get(away_name.lower()) or resolve_team_abbrev(away_name) or away_name[:3].upper()
            team_abbr = home_abbr if is_home else away_abbr
            matchup_abbrev = f"{away_abbr}/{home_abbr}"

            sign = "+" if sp_line > 0 else ""
            # Fixed-spread sports (MLB runline, NHL puck line): fixed ±1.5, cover rate 38–42%,
            # CV ~1.22–1.46 → T3 territory. Variable-spread sports (NBA, NFL): T2.
            spread_tier = "T3" if sport in _FIXED_SPREAD_SPORTS else "T2"
            spread_min_edge = 0.06 if sport in _FIXED_SPREAD_SPORTS else 0.05
            pick = {
                "player": f"{team_abbr} {sign}{sp_line}",
                "team_abbrev": matchup_abbrev,
                "stat": "SPREAD", "line": sp_line, "direction": "cover",
                "proj": team_margin, "win_prob": cover_prob,
                "raw_edge": edge, "adj_edge": edge, "conf": 1.0,
                "odds": sp_odds, "nv_prob": nv_this, "book": sp_book,
                "game": gl["game"], "sport": sport,
                "tier": spread_tier, "pick_type": "game_line",
                "sigma": sigma, "missing_side": False,
                "is_home": is_home,  # BUG G1 fix: used by grade_picks for correct team id
            }

            passed, gate = check_game_gates(pick)
            pick["gate_result"] = "PASS" if passed else gate
            if passed and edge >= spread_min_edge:
                pick["pick_score"] = pick_score(cover_prob, edge, mode, tier=pick["tier"])
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
        sigma = get_game_sigma(sport, home_name, away_name, "ml")  # FIX: ML uses ml sigma (wider) not spread sigma — spread sigma inflates win probs

        # Variable-spread sports (NBA/WNBA/NFL): blend projected margin against the market
        # spread line, which carries genuine run/point-margin information.
        # Fixed-spread sports (MLB/NHL): the runline/puck-line is always ±1.5 — a derivative
        # of the ML, not an independent margin signal. Use raw_margin; win_prob is anchored to
        # ML no-vig inside the loop instead.
        if sport not in _FIXED_SPREAD_SPORTS:
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

            # No-vig (computed before win_prob — needed as market anchor for fixed-spread sports)
            opp_name = [n for n in ml_data if n != team_name]
            if not opp_name:
                continue
            opp_odds = ml_data[opp_name[0]]["odds"]
            if is_decimal_leak(opp_odds):
                continue

            imp_this = implied_prob(ml_odds)
            imp_opp = implied_prob(opp_odds)
            nv_this, nv_opp = no_vig(imp_this, imp_opp)

            # Win probability
            if sport in _FIXED_SPREAD_SPORTS:
                # Runline/puck-line prices P(win by 2+), not P(win outright) — different bet.
                # Blend projection win_prob against ML no-vig as the market anchor.
                if sport == "MLB":
                    # NB direct sum: more accurate for discrete run-scoring than Normal
                    raw_home_wp = mlb_ml_from_nb(home_proj, away_proj, MLB_TEAM_RUN_R)
                    if _gl_w:  # readiness-gated EdgeModel ML handover (dormant -> unchanged)
                        raw_home_wp = _glh.blend_ml_prob(
                            _gl_w, _gl_em, resolve_team_abbrev(home_name),
                            resolve_team_abbrev(away_name), raw_home_wp, is_home=True)
                    raw_team_wp = raw_home_wp if is_home else (1.0 - raw_home_wp)
                else:
                    raw_team_wp = 1.0 - normal_cdf(0, raw_margin if is_home else -raw_margin, sigma)
                win_prob = nv_this + BLEND_ALPHA * (raw_team_wp - nv_this)
            else:
                win_prob = 1.0 - normal_cdf(0, team_margin, sigma)

            edge = win_prob - nv_this

            # Classify as favorite or dog based on odds
            is_fav = ml_odds < 0
            stat_type = "ML_FAV" if is_fav else "ML_DOG"
            tier = "T2" if is_fav else "T3"
            # Sport-specific ML_DOG floors: NHL parity sport (6%), NBA richer data (7%), MLB widest range (8%)
            _dog_edge = {"NHL": 0.06, "NBA": 0.07}.get(sport, 0.08)
            min_edge = 0.05 if is_fav else _dog_edge

            home_abbr = TEAM_ABBREV.get(home_name.lower()) or resolve_team_abbrev(home_name) or home_name[:3].upper()
            away_abbr = TEAM_ABBREV.get(away_name.lower()) or resolve_team_abbrev(away_name) or away_name[:3].upper()
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
                pick["pick_score"] = pick_score(win_prob, edge, mode, tier=pick["tier"])
            else:
                pick["size"] = 0
            picks.append(pick)

    # --- TEAM TOTALS ---
    for tt in team_totals:
        line = tt["line"]
        team = tt["team"]
        sigma = get_game_sigma_team(sport, team)

        # Find team projection
        proj = find_team_proj(team, team_proj, "saber_team")
        if proj is None or proj <= 0:
            continue

        proj = line + BLEND_ALPHA * (proj - line)

        if sport == "MLB":
            # NB is more accurate for discrete run-scoring (var/mu~2.26); per-team
            # dispersion where available (global r only as fallback). Push-adjusted
            # on integer lines. Canonical impl: game_line_pricing.team_total_mlb_nb.
            _mlb_r = get_mlb_team_run_r(resolve_team_abbrev(team) or team)
            over_p, under_p = team_total_mlb_nb(proj, line, _mlb_r)
        else:
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

            # TEAM_TOTAL → T2 all sports (Plan 9 §9F — was T1B/0.03 for NBA/MLB;
            # the 0.03 floor on a derivative line was the inverted-conviction problem).
            tt_tier = "T2"
            tt_min_edge = TIERS["T2"]["min_edge"]
            pick = {
                "player": f"{team} Team Total",
                "team_abbrev": get_team_abbrev("", team) if team else "",
                "stat": "TEAM_TOTAL", "line": line, "direction": direction,
                "proj": proj, "win_prob": wp,
                "raw_edge": edge, "adj_edge": edge, "conf": 1.0,
                "odds": odds, "nv_prob": nv, "book": book,
                "game": tt["game"], "sport": sport,
                "tier": tt_tier, "pick_type": "game_line",
                "sigma": sigma, "missing_side": False,
                "is_home": tt_is_home,  # BUG G fix: used by grade_picks for correct team score
            }

            # TEAM_TOTAL over blocked for NBA only: 45.5% WR (n=11) — shadow instead of kill (2026-05-27).
            # Pick dict built first so it can be logged to pick_log_shadow_stats.csv.
            if direction == "over" and sport == "NBA":
                pick["gate_result"] = "G_TT_OVER_NBA"
                pick["pick_score"] = pick_score(wp, edge, mode, tier=tt_tier)
                pick["size"] = 0
                picks.append(pick)
                continue

            passed, gate = check_game_gates(pick)
            pick["gate_result"] = "PASS" if passed else gate
            if passed and edge >= tt_min_edge:
                pick["pick_score"] = pick_score(wp, edge, mode, tier=pick["tier"])
            else:
                pick["size"] = 0
            picks.append(pick)

    return picks

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
        away_ab = resolve_team_abbrev(away)
        home_ab = resolve_team_abbrev(home)
        matchup_abbrev = f"{away_ab}/{home_ab}" if away_ab and home_ab else (away_ab or home_ab or "")

        # F5 Total — project as ~53% of full game total
        if "total" in f5:
            over_info = f5["total"].get("Over", {})
            under_info = f5["total"].get("Under", {})
            if over_info and under_info:
                line = over_info.get("line")
                if line is not None:
                    # Find game total projection and scale to F5
                    game_total_proj = (find_team_proj(home, team_proj, "saber_total") or
                                       find_team_proj(away, team_proj, "saber_total"))
                    if game_total_proj and game_total_proj > 0:
                        proj = game_total_proj * F5_SCALAR
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
                                    "tier": "T2", "pick_type": "game_line",  # Plan 9 §9F: T1B→T2 (floor 0.05; was 0.03)
                                    "sigma": sigma, "missing_side": False,
                                }
                                passed, gate = check_game_gates(pick)
                                pick["gate_result"] = "PASS" if passed else gate
                                if passed and edge >= TIERS["T2"]["min_edge"]:
                                    pick["pick_score"] = pick_score(wp, edge, mode, tier=pick["tier"])
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
                    t1_proj = find_team_proj(team1, team_proj, "saber_team")
                    t2_proj = find_team_proj(team2, team_proj, "saber_team")

                    if t1_proj and t2_proj and t1_proj > 0 and t2_proj > 0:
                        f5_t1 = t1_proj * F5_SCALAR
                        f5_t2 = t2_proj * F5_SCALAR
                        margin = f5_t1 - f5_t2
                        sigma = sigmas["spread"]

                        # Blend raw projection win_prob against F5 ML no-vig (mirrors full-game MLB ML fix).
                        # F5 ML has no independent spread line to anchor to, so the ML market is the only anchor.
                        nv1, nv2 = no_vig(implied_prob(odds1), implied_prob(odds2))
                        t1_wp_raw = 1.0 - normal_cdf(0, margin, sigma)
                        t2_wp_raw = normal_cdf(0, margin, sigma)
                        t1_wp = nv1 + BLEND_ALPHA * (t1_wp_raw - nv1)
                        t2_wp = nv2 + BLEND_ALPHA * (t2_wp_raw - nv2)
                        edge1 = t1_wp - nv1
                        edge2 = t2_wp - nv2

                        for team_name, wp, edge, odds, nv, book_key in [
                            (team1, t1_wp, edge1, odds1, nv1, ml_data[team1].get("book", "")),
                            (team2, t2_wp, edge2, odds2, nv2, ml_data[team2].get("book", "")),
                        ]:
                            # FIX 3: Mirror full-game ML — favs T2 (5% min edge), dogs T3 (8% min edge)
                            # F5 is MLB-only; MLB ML_DOG floor is 8% (widest odds range, lowest projection quality)
                            is_fav = odds < 0
                            stat = "F5_ML"
                            tier = "T2" if is_fav else "T3"
                            min_edge = 0.05 if is_fav else 0.08
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
                                pick["pick_score"] = pick_score(wp, edge, mode, tier=pick["tier"])
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
                    t_proj = find_team_proj(team_name, team_proj, "saber_team")
                    o_proj = find_team_proj(other_team[0], team_proj, "saber_team")

                    if t_proj and o_proj:
                        raw_f5_margin = (t_proj - o_proj) * F5_SCALAR
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
                            pick["pick_score"] = pick_score(cover_p, edge, mode, tier=pick["tier"])
                        else:
                            pick["size"] = 0
                        picks.append(pick)

    return picks

def evaluate_nrfi(game_lines, players, odds_data, sport, mode="Default"):
    """Evaluate NRFI/YRFI for MLB games using totals_1st_1_innings market.
    NRFI = Under 0.5 on 1st inning total.  YRFI = Over 0.5.

    Poisson λ model (rewritten 2026-05-29):
      P(team scores 0 in 1st) = e^(-λ)
      P(NRFI) = e^(-λ_away) × e^(-λ_home)

    λ_team = BASE_LAMBDA_1ST × pitcher_quality_mult × offense_mult × park_mult

    BASE_LAMBDA_1ST = 0.32 is calibrated from 2022-2024 empirical NRFI rates:
      avg matchup → P(NRFI) = e^(-0.64) ≈ 0.527  (observed 2022-24: ~52-54%)
    """
    # G_NRFI_DISABLED removed 2026-05-27 — re-enabled for shadow data accumulation; NRFI+YRFI in SHADOW_STATS.
    if sport != "MLB":
        return []

    picks = []
    # Poisson model constants (2026-05-29 calibration)
    BASE_LAMBDA_1ST = 0.32        # first-inning λ per team — calibrated to ~53% NRFI for avg matchup
    # NRFI_GAMMA (Plan 9 §9A, DATA_GATED): elasticity dampener on the matchup multiplier.
    # Pure Poisson elasticity exp(-0.32·m) is ~50-60% too steep under NB overdispersion
    # (±2pp at pick-firing extremes). Literature default γ≈0.6-0.7; applied to the
    # MULTIPLIER (λ = BASE · m^γ), not λ_total, so mult=1 keeps the ~53% baseline.
    # Recalibrate when first-inning-level data exists (bucket predicted mult vs
    # realized NRFI rate on the in-house 8,095-game DB).
    NRFI_GAMMA = 0.65
    _LEAGUE_AVG_RUNS = 4.45       # 2025 MLB runs/game/team (offense normalisation)
    _LEAGUE_AVG_BLENDED_RATE = 0.4808  # 0.25*(4.17/9) + 0.75*(4.38/9) — avg pitcher blended ERA+FIP rate (2025, Plan 9 §9A 25/75 blend)
    # Park factor intentionally omitted: SaberSim saber_team projections and
    # pitcher ERA/FIP inputs are already park-adjusted at source. Applying
    # MLB_PARK_FACTORS here would double-count park effects.
    # TODO (if SaberSim source ever switches to park-neutral inputs): replace
    # _LEAGUE_AVG_BLENDED_RATE with a park-adjusted league average derived
    # from park-neutral pitcher lines, and apply MLB_PARK_FACTORS to λ_team.

    # Build pitcher and team offense maps
    pitcher_map = {}       # team → pitcher stats
    team_saber_runs = {}   # team → projected runs/game (from SaberSim saber_team column)
    for p in players:
        team = p["team"].upper()
        if p.get("is_pitcher") and p.get("status") == "confirmed":  # R10: use confirmed starter
            ip = p.get("IP", 1) or 1.0
            er_per_ip = p.get("ER", 0) / ip
            # I4: Compute projected FIP for more stable pitcher quality estimate
            # FIP = ((13*HR + 3*BB - 2*K) / IP) + 3.26 (FIP constant 3.26 = 2025 lgERA≈4.17)
            hr = p.get("HR", 0)  # R4: HR allowed — now correctly stored for pitchers in parse_csv
            bb = p.get("BB", 0)
            k_val = p.get("K", 0)
            fip_raw = ((13 * hr + 3 * bb - 2 * k_val) / ip) + 3.26 if ip > 0 else 4.50  # FIP constant 3.26 (2025 lgERA≈4.17)
            # Blend ERA proxy and FIP: 75% FIP, 25% ERA (Plan 9 §9A: month-ahead
            # r² ERA 0.019 / FIP 0.038 / xFIP 0.061 — ERA half as predictive as FIP.
            # Prefer xFIP/FIP− at July refit when park HR/FB data is available.)
            fip_per_ip = fip_raw / 9.0  # Convert FIP (per 9) to per-inning rate
            blended_rate = 0.25 * er_per_ip + 0.75 * fip_per_ip
            pitcher_map[team] = {
                "er_per_ip": er_per_ip, "fip_per_ip": fip_per_ip,
                "blended_rate": blended_rate,
                "name": p["name"], "K": k_val, "IP": ip,
            }
        # Accumulate saber_team for each team (first batter entry wins; all rows same value per team)
        st = p.get("saber_team")
        if team and st and team not in team_saber_runs:
            try:
                team_saber_runs[team] = float(st)
            except (TypeError, ValueError):
                pass

    def _team_runs(team_name):
        """Look up projected runs for a team by resolving full API name to abbreviation."""
        abbr = resolve_team_abbrev(team_name)
        if abbr and abbr in team_saber_runs:
            return team_saber_runs[abbr]
        logger.warning(f"NRFI _team_runs: no match for '{team_name}' — using league avg {_LEAGUE_AVG_RUNS}")
        return _LEAGUE_AVG_RUNS

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

        # Find pitcher for each side — resolve full API team name to abbreviation first
        # so pitcher_map (keyed by SaberSim CSV abbrevs e.g. "NYY") matches correctly.
        # The old substring approach silently failed for teams like NYY, LAD, STL.
        home_abbr = resolve_team_abbrev(home)
        away_abbr = resolve_team_abbrev(away)
        home_pitcher = pitcher_map.get(home_abbr) if home_abbr else None
        away_pitcher = pitcher_map.get(away_abbr) if away_abbr else None

        if not home_pitcher or not away_pitcher:
            continue

        # Pitcher quality multiplier: blended FIP/ERA rate normalised to league avg.
        # Higher blended_rate = weaker pitcher = more runs allowed = larger λ.
        # Note: park factor intentionally omitted — SaberSim saber_team projections
        # are already park-adjusted, so the offense factor below inherits park effects.
        home_pitch_mult = home_pitcher.get("blended_rate", home_pitcher["er_per_ip"]) / _LEAGUE_AVG_BLENDED_RATE
        away_pitch_mult = away_pitcher.get("blended_rate", away_pitcher["er_per_ip"]) / _LEAGUE_AVG_BLENDED_RATE

        # Offense factor: batting team full-game projected runs (park-adjusted via SaberSim)
        # vs league average. Away bats vs home pitcher; home bats vs away pitcher.
        off_away = _team_runs(away) / _LEAGUE_AVG_RUNS
        off_home = _team_runs(home) / _LEAGUE_AVG_RUNS

        # Poisson λ per half-inning: higher λ = more expected runs = lower P(0 runs).
        # Plan 9 §9A: dampen the matchup multiplier by NRFI_GAMMA (m^γ) — raw Poisson
        # elasticity is too steep under NB overdispersion. Clamp the multiplier at 0
        # BEFORE exponentiation: elite-K pitchers can produce a negative FIP/blended
        # rate → negative mult, and (negative)**0.65 is a complex number (TypeError).
        mult_away = max(0.0, home_pitch_mult * off_away)
        mult_home = max(0.0, away_pitch_mult * off_home)
        lam_away = BASE_LAMBDA_1ST * mult_away ** NRFI_GAMMA
        lam_home = BASE_LAMBDA_1ST * mult_home ** NRFI_GAMMA
        lam_away = max(0.05, min(0.90, lam_away))
        lam_home = max(0.05, min(0.90, lam_home))

        import math as _math
        p_nrfi = _math.exp(-(lam_away + lam_home))
        p_yrfi = 1.0 - p_nrfi

        # Build matchup abbreviation
        away_ab = resolve_team_abbrev(away)
        home_ab = resolve_team_abbrev(home)
        matchup_abbrev = f"{away_ab}/{home_ab}" if away_ab and home_ab else (away_ab or home_ab or "")

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

            # Plan 9 §9F: NRFI/YRFI → T2 (was T3). R5: YRFI keeps its deliberate 8% bar
            # until sample is built; NRFI follows the T2 floor (0.05).
            min_edge = 0.08 if stat_label == "YRFI" else TIERS["T2"]["min_edge"]
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
                "tier": "T2", "pick_type": "game_line",  # Plan 9 §9F: T3→T2
                "sigma": 0, "missing_side": False,
                "nrfi_detail": {
                    "home_pitcher": home_pitcher["name"],
                    "away_pitcher": away_pitcher["name"],
                    "lam_away": lam_away,
                    "lam_home": lam_home,
                },
            }
            # FIX 4: Run through standard game gates (GG1 edge cap, GG3 positive edge)
            # sigma=0 so GG2 deviation check is skipped — intentional for binary markets
            passed, gate = check_game_gates(pick)
            pick["gate_result"] = "PASS" if passed else gate
            # FIX H2: Use standard pick_score() function
            pick["pick_score"] = pick_score(win_prob, adj_edge, mode, tier=pick["tier"]) if passed else None
            picks.append(pick)

    return picks
