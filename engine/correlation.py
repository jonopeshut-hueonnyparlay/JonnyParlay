"""Pick-pool dedup + negative-correlation filters (GLC, cross-type, TT divergence).

Extracted from run_picks.py (extract-and-re-export refactor, Step 12) and
re-imported there so existing call sites and `from run_picks import ...` keep
resolving. Imports only {stdlib, calibrated} — never run_picks or the other
extracted modules.
"""
import logging
from collections import defaultdict

from calibrated import MLB_CORR_GROUPS

logger = logging.getLogger("jonnyparlay")


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

def filter_game_line_correlations(picks):
    """Extended game-line correlation gate (GLC).

    Replaces the old TOTAL+TEAM_TOTAL-only dedup with a full conflict matrix.
    For each same-game pair of game-line picks, classify the relationship and
    drop the lower pick_score leg on HARD CONFLICT.

    HARD CONFLICT — drop lower pick_score leg:
      1. Team A ML/SPREAD-cover + Team B (opponent) TEAM_TOTAL Over:
         Team A winning typically prevents opponent from scoring freely.
         E.g. BUF ML + MTL TT Over — most BUF wins end 3-2 or 3-1, leaving MTL under 3.
      2. F5_ML Team A + F5_ML Team B (same game):
         Both teams cannot win the first 5 innings simultaneously.
      3. TOTAL Over + TOTAL Under (same game):
         Logical impossibility — kept defensively.
      4. TOTAL + TEAM_TOTAL same direction (same game):
         Preserved from original FIX-5 dedup — still a hard dedup, now folded here.

    SOFT TENSION — log at INFO, keep both:
      - ML/SPREAD Team A + TEAM_TOTAL Under Team A:
        Both lean toward a low-scoring win — reinforcing, not conflicting.
      - TOTAL Over + TEAM_TOTAL Over (same team):
        Aligned; original FIX-5 already deduplicated these, which is stricter than needed
        for the TOTAL vs TEAM_TOTAL *different-team* case handled above.

    Prop picks (PTS/AST/REB/SOG/etc.) and NRFI/YRFI are independent markets
    not subject to this gate — they pass through untouched.
    """
    GL_STATS = {"ML_FAV", "ML_DOG", "SPREAD", "TOTAL", "TEAM_TOTAL",
                "F5_ML", "F5_SPREAD", "F5_TOTAL", "NRFI", "YRFI"}

    gl_picks = [p for p in picks if p.get("stat") in GL_STATS]
    prop_picks = [p for p in picks if p.get("stat") not in GL_STATS]

    # Group game-line picks by game string
    game_groups: dict = defaultdict(list)
    for p in gl_picks:
        game_groups[p.get("game", "")].append(p)

    dropped: set = set()  # indices into gl_picks of dropped legs

    for game, group in game_groups.items():
        if len(group) < 2:
            continue

        # Walk all pairs
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                a = group[i]
                b = group[j]
                sa = a.get("stat", "")
                sb = b.get("stat", "")
                da = a.get("direction", "")
                db = b.get("direction", "")
                ha = a.get("is_home")  # True=home, False=away
                hb = b.get("is_home")

                conflict = False

                # Rule 1: ML or SPREAD-cover for Team A + TEAM_TOTAL Over for Team B (opponent)
                # A "wins" pick combined with the opponent's over = contradiction.
                for win_pick, tt_pick in [(a, b), (b, a)]:
                    ws = win_pick.get("stat", "")
                    ts = tt_pick.get("stat", "")
                    td = tt_pick.get("direction", "")
                    wh = win_pick.get("is_home")
                    th = tt_pick.get("is_home")
                    if ws in {"ML_FAV", "ML_DOG", "SPREAD"} and ts == "TEAM_TOTAL" and td == "over":
                        if wh is None or th is None:
                            logger.warning(
                                f"GLC Rule 1 scan: is_home=None for "
                                f"{win_pick.get('player', '?')}/{ws} — "
                                "ML/SPREAD correlation detection skipped"
                            )
                        elif wh != th:          # different teams
                            conflict = True
                            break

                # Rule 2: F5_ML for both teams in the same game
                if not conflict and sa == "F5_ML" and sb == "F5_ML":
                    # Both can't win the first 5
                    conflict = True

                # Rule 3: TOTAL Over + TOTAL Under in same game (logical impossibility)
                if not conflict and sa == "TOTAL" and sb == "TOTAL" and da != db:
                    conflict = True

                # Rule 4: TOTAL + TEAM_TOTAL same direction (original FIX-5 dedup)
                if not conflict:
                    if ({sa, sb} == {"TOTAL", "TEAM_TOTAL"} and da == db):
                        conflict = True

                # Rule 5: NRFI + YRFI same game (logical impossibility — exactly one can hit)
                if not conflict and {sa, sb} == {"NRFI", "YRFI"}:
                    conflict = True

                if conflict:
                    # Drop the lower pick_score leg
                    score_a = a.get("pick_score") or 0
                    score_b = b.get("pick_score") or 0
                    loser_idx = gl_picks.index(b) if score_a >= score_b else gl_picks.index(a)
                    winner = a if score_a >= score_b else b
                    loser = b if score_a >= score_b else a
                    if loser_idx not in dropped:
                        dropped.add(loser_idx)
                        logger.info(
                            "GLC HARD CONFLICT [%s]: dropped %s %s (score=%.1f) "
                            "conflicts with %s %s (score=%.1f)",
                            game,
                            loser.get("stat"), loser.get("direction"),
                            float(loser.get("pick_score") or 0),
                            winner.get("stat"), winner.get("direction"),
                            float(winner.get("pick_score") or 0),
                        )
                        print(
                            f"  [GLC] Dropped {loser.get('player')} {loser.get('stat')} "
                            f"{loser.get('direction')} (score={loser.get('pick_score', 0):.1f}) "
                            f"— conflicts with {winner.get('player')} {winner.get('stat')} "
                            f"(score={winner.get('pick_score', 0):.1f}) [{game}]"
                        )

    kept_gl = [p for idx, p in enumerate(gl_picks) if idx not in dropped]
    return prop_picks + kept_gl

def dedup_game_line_correlation(picks):
    """Thin alias for filter_game_line_correlations (FIX 5, preserved for compatibility)."""
    return filter_game_line_correlations(picks)

def filter_cross_type_correlations(picks):
    """Kill prop-vs-game-line pairs that are structurally anti-correlated.

    filter_game_line_correlations() only checks GL-vs-GL pairs; props pass through
    untouched.  This function handles cross-type MLB conflicts:

      X1 (HARD): Pitcher HA/ER UNDER + opposing team TEAM_TOTAL OVER (same game)
                 ρ ≈ −0.65–0.75 — mechanically anti-correlated (fewer hits/ER = fewer runs)

    Both picks could independently qualify and land in the longshot pool.
    Drop the lower pick_score leg on conflict.
    """
    _PITCHER_KILL = {("HA", "under"), ("ER", "under")}   # X1 triggers

    game_groups: dict = {}
    for p in picks:
        g = p.get("game", "")
        game_groups.setdefault(g, []).append(p)

    dropped: set = set()  # Python id()s of picks to remove

    for group in game_groups.values():
        if len(group) < 2:
            continue
        for i, a in enumerate(group):
            if id(a) in dropped:
                continue
            for b in group[i + 1:]:
                if id(b) in dropped:
                    continue

                conflict = False
                loser = None

                # Try both orderings so we don't have to repeat logic
                for pitcher_pick, other_pick in ((a, b), (b, a)):
                    pp_key  = (pitcher_pick.get("stat", ""), pitcher_pick.get("direction", ""))
                    op_stat = other_pick.get("stat", "")
                    op_dir  = other_pick.get("direction", "")
                    pp_team = pitcher_pick.get("team_abbrev", "")
                    op_team = other_pick.get("team_abbrev", "")
                    same_game_opp = pp_team and op_team and pp_team != op_team

                    # X1: pitcher HA/ER under + opposing TEAM_TOTAL over
                    if (pp_key in _PITCHER_KILL and
                            op_stat == "TEAM_TOTAL" and op_dir == "over" and
                            same_game_opp):
                        conflict = True
                        score_pp = pitcher_pick.get("pick_score") or 0
                        score_op = other_pick.get("pick_score") or 0
                        loser = other_pick if score_pp >= score_op else pitcher_pick
                        break

                if conflict and loser is not None:
                    dropped.add(id(loser))
                    winner = b if loser is a else a
                    logger.info(
                        "CROSS-TYPE CONFLICT [%s]: dropped %s %s %s (score=%.1f) "
                        "conflicts with %s %s %s (score=%.1f)",
                        a.get("game", ""),
                        loser.get("player"), loser.get("stat"), loser.get("direction"),
                        float(loser.get("pick_score") or 0),
                        winner.get("player"), winner.get("stat"), winner.get("direction"),
                        float(winner.get("pick_score") or 0),
                    )
                    print(
                        f"  [XTYPE] Dropped {loser.get('player')} {loser.get('stat')} "
                        f"{loser.get('direction')} (score={loser.get('pick_score', 0):.1f}) "
                        f"— anti-correlated with {winner.get('player')} {winner.get('stat')} "
                        f"{winner.get('direction')} (score={winner.get('pick_score', 0):.1f})"
                    )

    return [p for p in picks if id(p) not in dropped]

def warn_tt_divergence(all_picks, threshold: float = 1.5) -> None:
    """Warn when the engine's projected team total diverges from market-implied.

    Market-implied team total is derived from game total ± spread/2:
        home_team_implied = (total_line - home_spread_line) / 2
        away_team_implied = (total_line + home_spread_line) / 2
    Equivalently: implied = (total_line + team_spread_line) / 2
    where team_spread_line is the spread from that team's perspective
    (positive = underdog / getting points, negative = favourite / giving points).

    Fires a WARNING-level log + console print when |proj - implied| > threshold.
    Operates over ALL picks (qualified + failed) so the warning doesn't depend
    on whether the TOTAL/SPREAD pick itself passed gates.
    """
    # Build per-game lookup tables from ALL picks
    total_by_game: dict = {}          # game → total_line (from TOTAL pick)
    spread_by_game_home: dict = {}    # game → home-team spread_line (is_home=True)

    for p in all_picks:
        game = p.get("game", "")
        stat = p.get("stat", "")
        if stat == "TOTAL" and game not in total_by_game:
            try:
                total_by_game[game] = float(p["line"])
            except (KeyError, TypeError, ValueError):
                pass
        elif stat == "SPREAD" and p.get("is_home") is True and game not in spread_by_game_home:
            try:
                spread_by_game_home[game] = float(p["line"])
            except (KeyError, TypeError, ValueError):
                pass

    # Check each TEAM_TOTAL pick
    for p in all_picks:
        if p.get("stat") != "TEAM_TOTAL":
            continue
        game = p.get("game", "")
        total_line = total_by_game.get(game)
        home_spread = spread_by_game_home.get(game)
        if total_line is None or home_spread is None:
            continue

        is_home = p.get("is_home")
        if is_home is True:
            # home implied = (total - home_spread) / 2
            implied = (total_line - home_spread) / 2.0
        else:
            # away implied = (total + home_spread) / 2
            implied = (total_line + home_spread) / 2.0

        try:
            proj = float(p["proj"])
        except (KeyError, TypeError, ValueError):
            continue

        gap = abs(proj - implied)
        if gap > threshold:
            logger.warning(
                "TT DIVERGENCE [%s]: %s proj=%.2f market-implied=%.2f gap=%.2f > %.2f",
                game, p.get("player", ""), proj, implied, gap, threshold,
            )
            print(
                f"  [TT-DIVERGE] {p.get('player','')} ({game}): "
                f"engine_proj={proj:.2f} market_implied={implied:.2f} "
                f"gap={gap:.2f} > {threshold:.2f} — check projection"
            )
