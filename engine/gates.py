"""Prop-pick and game-line gate checks (G* / GG* gates).

Extracted from run_picks.py (extract-and-re-export refactor, Step 9) and
re-imported there so existing call sites and `from run_picks import ...` keep
resolving. Imports only {stdlib, market_config, thresholds, calibrated,
quant.odds, wnba_gate, prob_core} — never run_picks or the other extracted
modules.
"""
from datetime import datetime
from zoneinfo import ZoneInfo

from market_config import SUSPENDED_STATS
from thresholds import (
    WNBA_SEASON_START, WNBA_OPENING_GATE_DAYS, WNBA_OPENING_GATE_GAMES, WNBA_EV_FLOOR,
)
from calibrated import SIGMA, SIGMA_WNBA, POISSON_STATS, NB_STATS, COMBO_STATS
from quant.odds import implied_prob
from wnba_gate import _wnba_team_games_played, _wnba_early_season_factor
from prob_core import _combo_mu_sigma


def check_prop_gates(pick):
    """Apply gates G1-G10, G14-G15. Returns (pass, gate_failed) tuple."""
    prob = pick["win_prob"]
    edge = pick["adj_edge"]
    odds = pick["odds"]
    line = pick["line"]
    stat = pick["stat"]
    direction = pick["direction"]
    proj = pick.get("proj", 0.0)

    # G3: missing both sides
    if pick.get("missing_side"):
        return False, "G3"

    # G7: hard juice ban
    if odds <= -150:
        return False, "G7"

    # G7b: soft juice
    if -149 <= odds <= -140 and edge < 0.10:
        return False, "G7b"

    # G8: binary fragility (FIX M3: extended to MLB low-count stats)
    # NHL AST 0.5 under is exempt — Bernoulli T3 market, activated 2026-06-05
    if stat in ("AST", "REB", "SOG", "HA", "HITS") and line <= 1.5:
        if not (stat == "AST" and pick.get("sport", "NBA") == "NHL"
                and line == 0.5 and direction == "under"):
            return False, "G8"

    # G8B: AST over at line ≤ 4.5 — 0-5 record vs 2-1 at line ≥ 5.5 (n=8).
    # NBA-only: WNBA line 4.5 is elite-playmaker territory, not sub-elite.
    # Model over-projects assists for NBA guards/wings at sub-elite-playmaker lines.
    sport = pick.get("sport", "NBA")
    if stat == "AST" and direction == "over" and line <= 4.5 and sport != "WNBA":
        return False, "G8B"

    # G_NHL_AST: NHL AST active only at line==0.5 under (Bernoulli T3, min_edge=0.06).
    # Block all other NHL AST lines/directions.
    if stat == "AST" and sport == "NHL" and not (line == 0.5 and direction == "under"):
        return False, "G_NHL_AST"

    # Suspension gates — single source of truth (see SUSPENDED_STATS).
    # SOG: re-evaluate G8C scope when the distribution investigation completes.
    # HA: re-evaluate G_HA_DIR scope when the model investigation completes.
    if stat in SUSPENDED_STATS:
        return False, SUSPENDED_STATS[stat]

    # G8C: SOG under at line ≤ 3.5 — extended from ≤2.5 (2026-05-23).
    # ≤2.5 was 51.9% WR (losing at juice). 3.1–3.5 added: 42.9% WR, model 63.7% (n=14).
    # Both ranges show systematic model over-prediction; Poisson underestimates elite shot volume.
    if stat == "SOG" and direction == "under" and line <= 3.5:
        return False, "G8C"

    # G8D: 3PM over at line ≤ 1.5 — 50.0% actual vs 70.4% model (n=16, gap −20pp).
    # Binary line (needs 2+ threes) creates structural over-projection; consistent with
    # G8B/G8C pattern. Was too noisy at n=8-9 (May 13); confirmed at n=16.
    # WNBA exempt: calibrated on NBA data only; WNBA line 1.5 is not sub-elite territory.
    if stat == "3PM" and direction == "over" and line <= 1.5 and sport != "WNBA":
        return False, "G8D"

    # WNBA structural gates — applied after sport is known (Plan 6 §14 rework 2026-06-05)
    if sport == "WNBA":
        today_date = datetime.now(ZoneInfo("America/New_York")).date()
        season_day = (today_date - WNBA_SEASON_START).days + 1  # day 1 = opening day

        # G_WNBA_OPEN (9c): re-keyed from calendar days to GAMES PLAYED — both teams
        # need >= WNBA_OPENING_GATE_GAMES current-season games. Opening-game extreme
        # variance is per-team (new-team/new-role players SaberSim cannot price;
        # May 13 2026: -19.8 PTS miss), so a team with a late opener stays gated on
        # day 5 while a team with 2 games played clears on day 4.
        # Fallback: when games-played counts are unavailable (EdgeModel DB missing/
        # stale), the original day gate (days 1-3) governs. Only evaluated in the
        # first 14 season days — no DB hits the rest of the season.
        # Note: season_day ≤ 0 (pre-season) is not blocked — SaberSim doesn't generate
        # pre-season CSVs in practice, so this theoretical gap has no real exposure.
        if 1 <= season_day <= 14:
            _teams = [t.strip() for t in (pick.get("game", "") or "").split("@")]
            _gps = [_wnba_team_games_played(t, today_date) for t in _teams if t]
            if _gps and all(gp is not None for gp in _gps):
                if any(gp < WNBA_OPENING_GATE_GAMES for gp in _gps):
                    return False, "G_WNBA_OPEN"
            elif 1 <= season_day <= WNBA_OPENING_GATE_DAYS:
                return False, "G_WNBA_OPEN"

        # G_WNBA_EDGE (9a): EV-per-unit floor from ACTUAL quoted odds — replaces the
        # dead WNBA_EDGE_FLOOR=0.035 (always dominated by G9=0.05). Bar = net EV of
        # NBA's G9 floor pick at standard −110 vig (≈0.0955/unit), so the floor
        # auto-adjusts to vig: at −115 it demands ~5.1% edge, at −120 ~5.2%.
        # The old early-season edge-multiplication is gone — early-season uncertainty
        # now flows through sigma inflation in calc_prop_prob (9b), which shrinks
        # prob (and therefore this EV) organically.
        _imp = implied_prob(odds)
        if _imp > 0:
            ev_per_unit = prob / _imp - 1.0
            if ev_per_unit < WNBA_EV_FLOOR:
                return False, "G_WNBA_EDGE"

    # G_MLB_STRUCT: MLB structural direction gates.
    # OUTS under: G_OUTS_UNDER WP<0.60 block removed per Plan 10 §T (2026-06-07). The outs
    # distribution is left-skewed (early exits common) so books OVER-estimate outs → unders
    # should win MORE, not "lose structurally"; the 0.60 floor contradicted the data and was
    # stale post-σ-fix (0.311→0.27). OUTS (T2) now rides the standard T2 min_edge=0.05 floor.
    # HA over: no research basis; HA is suspended anyway (G_HA_SUSPENDED catches it first).
    if stat == "HA" and direction == "over":
        return False, "G_HA_DIR"
    # HITS over: routed to shadow (was hard kill) per Plan 10 §T — hitter parks + May offense
    # suggest possible live edge; accumulate data instead of killing blind.
    # DATA_GATED: lift at n≥30, calib bias ±3pp + CLV≥0.
    if stat == "HITS" and direction == "over":
        return False, "G_HITS_OVER_SHADOW"
    # G_HRR_OVER_LOW_LINE: HRR over at line <= 0.5 suspended 2026-06-09 — shadow gate
    # analysis (n=54): 46.3% WR (25W/29L), -25.5% sized ROI, model overconfident -15.5pp.
    # Root cause: NB r=1.5 too thin (within-player starters r≈1.1, mlb_batter_game_stats)
    # plus residual mu inflation. July refit fixes r + audits the mu path; shadow log
    # resets post-fix. HRR under and over at lines > 0.5 stay in shadow accumulation.
    if stat == "HRR" and direction == "over" and line <= 0.5:
        return False, "G_HRR_OVER_LOW_LINE"

    # G9: universal floor
    if edge < 0.05:
        return False, "G9"

    # G9B: NBA props require a higher edge floor (7%) — more efficient market
    if pick.get("sport") == "NBA" and edge < 0.07:
        return False, "G9B"

    # G13: sub-50% win probability ban — proven 1-3 record, negative PS
    if prob < 0.50:
        return False, "G13"

    # G_HRR_DISABLED removed 2026-05-27 — NB r=1.5 is the correct distribution; routing to SHADOW_STATS for fresh data accumulation.
    # G_TB_DISABLED removed 2026-05-27 — calc_tb_prob (Poisson convolution) was already the rebuild; routing to SHADOW_STATS.
    # G_RA_DISABLED moved to the consolidated SUSPENDED_STATS lookup above (2026-06-05).

    # G14: projection clearance gate — ensures model has directional conviction.
    # Normal/SIGMA stats (PTS, OUTS, HA, TB): proj must clear line by ≥0.10σ.
    # HRR is in NB_STATS (not SIGMA), so it is exempt from G14.
    # Poisson stats (AST, REB, SOG, etc.) are exempt — Poisson probability correctly
    # handles cases where the discrete distribution favors the pick even when proj
    # slightly crosses the line (e.g. AST 4.5 under with proj=4.6 still gives ~51%
    # under probability). G13 (prob≥0.50) already handles true direction failures.
    # All NB_STATS are exempt for non-WNBA — NB distribution handles boundary cases correctly.
    # WNBA 3PM/AST/REB all get G14 via the block below (SIGMA_WNBA as z-score proxy).
    # AST/REB use NB_R_WNBA for probability but SIGMA_WNBA sigma is still used here.
    if stat in SIGMA and stat not in POISSON_STATS and stat not in NB_STATS:
        _s = (SIGMA_WNBA.get(stat) if sport == "WNBA" else None) or SIGMA[stat]
        _sigma = max(proj * _s["mult"], _s["min"])
        if sport == "WNBA":
            _sigma /= _wnba_early_season_factor()   # 9b: early-season inflation
        _z = (line - proj) / _sigma if direction == "under" else (proj - line) / _sigma
        if _z < 0.10:
            return False, "G14"
    if stat in ("3PM", "AST", "REB") and sport == "WNBA":
        _s = SIGMA_WNBA[stat]
        # Early-season sigma inflation applies here too (9b) — wider sigma means
        # the projection must clear the line by more to show 0.10σ conviction.
        _sigma = max(proj * _s["mult"], _s["min"]) / _wnba_early_season_factor()
        _z = (line - proj) / _sigma if direction == "under" else (proj - line) / _sigma
        if _z < 0.10:
            return False, "G14"
    if stat in COMBO_STATS:
        _pp = pick.get("proj_player", {}) or {}
        _, _sigma_c = _combo_mu_sigma(_pp, stat, sport=sport)
        _z = (line - proj) / _sigma_c if direction == "under" else (proj - line) / _sigma_c
        if _z < 0.10:
            return False, "G14"

    # G15: HIGH-VAR 3PM gate — bimodal 3PT shooters have unreliable nightly
    # projections (pts_cv >= 0.60 = seen 0→5 variance within recent games).
    # Only triggers when custom engine provides pts_cv; SaberSim CSV leaves
    # the column empty so this gate is a no-op in non-custom-engine runs.
    if stat == "3PM":
        _cv = pick.get("pts_cv")
        if _cv and float(_cv) >= 0.60:
            return False, "G15"

    # G1: high prob + bad odds — but allow if edge is strong (FIX L2)
    if prob >= 0.70 and odds > -200 and edge < 0.05:
        return False, "G1"

    # G4: low line + extreme prob — exempt HITS O0.5 soft market
    _is_soft_o05 = (stat == "HITS" and line <= 0.5 and direction == "over")
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
    """Apply gates GG1-GG6."""
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
    if pick.get("stat") in ("SPREAD", "F5_SPREAD") and pick.get("odds", 0) > 0:
        return False, "GG5"

    # GG6: Projection clearance for total-type markets (TEAM_TOTAL, TOTAL, F5_TOTAL).
    # Proj must be on the correct side of the line — if the model projects fewer runs
    # than the line, betting the over is pure market arbitrage with no model conviction.
    if stat in ("TEAM_TOTAL", "TOTAL", "F5_TOTAL"):
        direction = pick.get("direction", "")
        if direction == "over" and proj <= line:
            return False, "GG6"
        if direction == "under" and proj >= line:
            return False, "GG6"

    return True, None
