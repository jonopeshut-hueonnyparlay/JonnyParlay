"""Parlay BUILDERS — longshot (safest-6), value (5-leg fallback), alt-spread (daily lay).

Extracted from run_picks.py (extract-and-re-export refactor, Step 14) and re-imported
there so existing call sites and `from run_picks import ...` keep resolving. These are
the pure builders only — the Discord `post_*` functions stay in run_picks (they move to
discord_post.py in Step 16, since they depend on _webhook_post). Imports only {stdlib,
thresholds, market_config, quant.distributions, team_resolve, book_names} — never
run_picks or the other extracted modules.
"""
import math
from collections import defaultdict

from thresholds import (
    LONGSHOT_PAIR_RHO, LONGSHOT_MAX_PER_GAME,
    MIN_LEG_EDGE_DAILY, MIN_LEG_COVER_PROB_DAILY,
)
from market_config import TEAM_ABBREV
from quant.distributions import normal_cdf
from team_resolve import get_team_abbrev
from book_names import norm_book as _norm_book, display_book


def _longshot_pos_corr_pair(a, b):
    """True iff (a, b) is the positively-correlated pair: pitcher OUTS under +
    opposing team's TEAM_TOTAL over in the same game (Plan 9 §9B, ρ ≈ +0.30-0.40 —
    pitcher exits early → opposing offense scoring; mirror of the X1 negative pair).
    Opposing-team check mirrors filter_cross_type_correlations (team_abbrev fields).
    """
    g = a.get("game", "")
    if not g or g != b.get("game", ""):
        return False
    for outs_pick, tt_pick in ((a, b), (b, a)):
        if (outs_pick.get("stat") == "OUTS" and outs_pick.get("direction") == "under"
                and tt_pick.get("stat") == "TEAM_TOTAL" and tt_pick.get("direction") == "over"):
            t_outs = outs_pick.get("team_abbrev", "")
            t_tt = tt_pick.get("team_abbrev", "")
            if t_outs and t_tt and t_outs != t_tt:
                return True
    return False


def _longshot_effective_wp(p, selected):
    """Effective win prob of candidate p for longshot RANKING, conditional on
    already-selected legs (Plan 9 §9B). If p forms a positively-correlated pair
    with a selected leg q, independence understates the joint prob — rank p by
    P(p | q) = joint / P(q), where (Bernoulli-φ identity):

        joint = p·q + ρ·sqrt(p(1−p)·q(1−q))

    Equals the raw win_prob when no boosted pair exists. Ranking-only: the
    displayed/logged combined_prob stays the independence product (conservative
    for the boosted pair).
    """
    wp = p["win_prob"]
    best = wp
    for q_pick in selected:
        if _longshot_pos_corr_pair(p, q_pick):
            q = q_pick["win_prob"]
            if q <= 0.0:
                continue
            joint = wp * q + LONGSHOT_PAIR_RHO * math.sqrt(
                max(0.0, wp * (1.0 - wp) * q * (1.0 - q)))
            best = max(best, min(0.99, joint / q))
    return best


def build_safest6_parlay(qualified):
    """Build a longshot parlay from the 6 safest picks by win probability.

    This is a HIT-FREQUENCY PRODUCT (Plan 9 §9G decision, 2026-06-06):
    selecting by win_prob maximizes how often the card has at least one
    parlay winner (engagement/subscriber value — a hit every ~2-3 weeks at
    daily cadence), not EV. An EV-factor ranking (1 + edge/implied) would be
    theoretically superior (~+77% vs ~+19% slip EV in the worked example) but
    is a product direction change requiring subscriber expectation management.
    Current design is intentional and documented as hit-frequency.

    Per-game cap of 2: prevents same-game correlation from dominating the
    combined probability estimate (which assumes independence across legs).
    If the top 6 by WP would pull 3+ from one game, the 3rd+ are skipped
    and replaced by the next-best picks from other games.

    Independence assumption is valid for cross-game legs: positive cross-game
    correlation (shared pace/scoring environment) would make true joint prob
    >= naive product, so independence is conservative, not aggressive.
    """
    # Hit-frequency product: rank by win_prob, not EV-factor.
    # Plan 9 §9B: iterative greedy — each round selects the pool max by
    # EFFECTIVE wp (conditional on already-selected positively-correlated
    # partners via _longshot_effective_wp). With no boosted pairs this is
    # sequence-identical to the old single-pass wp-desc sort (max() resolves
    # ties to the lowest index in the wp-desc pool).
    pool = sorted(qualified, key=lambda p: p["win_prob"], reverse=True)
    game_counts: dict = {}
    player_counts: dict = {}
    safest = []
    while pool and len(safest) < 6:
        p = max(pool, key=lambda c: _longshot_effective_wp(c, safest))
        pool.remove(p)
        g = p.get("game", "")
        player = p.get("player", "")
        if game_counts.get(g, 0) >= LONGSHOT_MAX_PER_GAME:
            continue
        # Max 1 leg per player — same player's stats are correlated, not independent
        if player and player_counts.get(player, 0) >= 1:
            continue
        game_counts[g] = game_counts.get(g, 0) + 1
        if player:
            player_counts[player] = player_counts.get(player, 0) + 1
        safest.append(p)
    if len(safest) < 6:
        return None
    # Displayed/logged combined_prob stays the independence product — conservative
    # for a boosted pair (true joint prob >= product under positive ρ).
    combined_prob = 1.0
    combined_dec  = 1.0
    book_counts: dict = {}
    for p in safest:
        combined_prob *= p["win_prob"]
        o = p.get("odds", -110)
        if o > 0:
            combined_dec *= 1.0 + o / 100.0
        else:
            combined_dec *= 1.0 + 100.0 / abs(o)
        bk = _norm_book(p.get("book", ""))
        if bk:
            book_counts[bk] = book_counts.get(bk, 0) + 1
    # Actual payout from book leg prices (not model fair value)
    if combined_dec >= 2.0:
        parlay_odds = int(round((combined_dec - 1.0) * 100.0))
    else:
        parlay_odds = int(round(-100.0 / (combined_dec - 1.0)))
    # Modal book across legs — best guess for where to parlay
    best_book = max(book_counts, key=book_counts.get) if book_counts else ""
    return {"legs": safest, "combined_prob": combined_prob, "parlay_odds": parlay_odds, "book": best_book}


def build_value_parlay(qualified):
    """5-leg fallback parlay — fires only when 6-leg longshot cannot be built.
    Same per-game (LONGSHOT_MAX_PER_GAME) and per-player (1) caps as longshot.
    Returns None if fewer than 5 legs pass all caps.

    Plan 10 §S: per-leg +EV admissibility gate (adj_edge > 0). Compounding ~14% vig on
    individually −EV legs is presumptively −EV, so we return None rather than ship a parlay
    built from non-positive-edge legs.
    """
    ranked = sorted(qualified, key=lambda p: p["win_prob"], reverse=True)
    game_counts: dict = {}
    player_counts: dict = {}
    safest = []
    for p in ranked:
        g = p.get("game", "")
        player = p.get("player", "")
        if p.get("adj_edge", 0) <= 0:
            continue  # Plan 10 §S: exclude non-positive-edge legs
        if game_counts.get(g, 0) >= LONGSHOT_MAX_PER_GAME:
            continue
        if player and player_counts.get(player, 0) >= 1:
            continue
        game_counts[g] = game_counts.get(g, 0) + 1
        if player:
            player_counts[player] = player_counts.get(player, 0) + 1
        safest.append(p)
        if len(safest) == 5:
            break
    if len(safest) < 5:
        return None
    combined_prob = 1.0
    combined_dec  = 1.0
    book_counts: dict = {}
    for p in safest:
        combined_prob *= p["win_prob"]
        o = p.get("odds", -110)
        if o > 0:
            combined_dec *= 1.0 + o / 100.0
        else:
            combined_dec *= 1.0 + 100.0 / abs(o)
        bk = _norm_book(p.get("book", ""))
        if bk:
            book_counts[bk] = book_counts.get(bk, 0) + 1
    if combined_dec >= 2.0:
        parlay_odds = int(round((combined_dec - 1.0) * 100.0))
    else:
        parlay_odds = int(round(-100.0 / (combined_dec - 1.0)))
    best_book = max(book_counts, key=book_counts.get) if book_counts else ""
    return {"legs": safest, "combined_prob": combined_prob, "parlay_odds": parlay_odds, "book": best_book}


def build_alt_spread_parlay(game_lines, team_proj_map, sport_sigmas, alt_spread_data=None, debug=False):
    """
    Build alt spread parlay (NBA ONLY).
    Selects legs by edge (model cover prob vs implied prob from odds).
    Tries 3 legs → 2 → 1 per book, one leg per game.
    Only posts if combined parlay odds >= -130.
    """
    if alt_spread_data is None:
        alt_spread_data = []

    def dbg(msg):
        if debug:
            print(f"  [daily-lay-debug] {msg}")

    MIN_COMBINED_ODDS_VAL = -130  # combined parlay must be -130 or longer
    MAX_COMBINED_ODDS_VAL = 100   # combined parlay must not exceed +100

    def american_to_decimal(odds):
        if odds > 0:
            return 1.0 + odds / 100.0
        return 1.0 + 100.0 / abs(odds)

    def decimal_to_american(dec):
        if dec >= 2.0:
            return (dec - 1.0) * 100.0
        return -100.0 / (dec - 1.0)

    # Step 1: Build per-team projection info from NBA game lines
    team_game_info = {}
    nba_games = []
    for gl in game_lines:
        if gl.get("sport", "").upper() != "NBA":
            continue
        home = gl["home"]
        away = gl["away"]
        sigma = sport_sigmas.get("NBA", {}).get("spread", 12.0)
        sport_prefix = "NBA_"

        home_proj = away_proj = None
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

        spread_data = gl.get("spread", {})
        home_std = spread_data.get(home, {}).get("line")
        away_std = spread_data.get(away, {}).get("line")

        if home_proj is not None and away_proj is not None:
            margin = home_proj - away_proj
            dbg(f"GAME {gl['game']}: home={home_proj:.1f} away={away_proj:.1f} margin={margin:+.1f}")
            team_game_info[home] = {"margin": margin,  "sigma": sigma, "game": gl["game"], "sport": "NBA", "std_spread": home_std}
            team_game_info[away] = {"margin": -margin, "sigma": sigma, "game": gl["game"], "sport": "NBA", "std_spread": away_std}
        else:
            dbg(f"SKIP proj {gl['game']}: home_proj={home_proj} away_proj={away_proj}")
            team_game_info[home] = {"margin": None, "sigma": sigma, "game": gl["game"], "sport": "NBA", "std_spread": home_std}
            team_game_info[away] = {"margin": None, "sigma": sigma, "game": gl["game"], "sport": "NBA", "std_spread": away_std}

        nba_games.append(gl["game"])

    if not nba_games:
        dbg("No NBA games found")
        return None

    # Step 2: Score every alt spread entry by edge + quality filters
    scored = []
    for entry in alt_spread_data:
        team = entry["team"]
        if team not in team_game_info:
            continue
        info = team_game_info[team]
        if info["margin"] is None:
            continue

        odds = entry["odds"]
        line = entry["line"]
        margin = info["margin"]
        sigma = info["sigma"]

        implied = abs(odds) / (abs(odds) + 100.0) if odds < 0 else 100.0 / (odds + 100.0)
        cover_prob = 1.0 - normal_cdf(-line, margin, sigma)
        # Raw vigged implied (not no-vig) — alt-spread lines are one-sided, making no-vig
        # impossible. Conservative: vigged implied is harder to beat at 0.025 threshold.
        edge = cover_prob - implied

        # Per-leg quality gates: screen out noise before composite scoring
        if edge < MIN_LEG_EDGE_DAILY:
            dbg(f"  {team} {line:+.1f} @ {odds}: SKIP edge {edge:.3f} < {MIN_LEG_EDGE_DAILY}")
            continue
        if cover_prob < MIN_LEG_COVER_PROB_DAILY:
            dbg(f"  {team} {line:+.1f} @ {odds}: SKIP cover_prob {cover_prob:.3f} < {MIN_LEG_COVER_PROB_DAILY}")
            continue

        # Composite leg score: edge weighted 60%, excess cover prob weighted 40%.
        # The 0.58 floor clips the baseline — only rewarding probability meaningfully
        # above the minimum, not raw implied probability (which penalises tight lines).
        # Odds quality bonus: legs in -145 to -100 range get a 5% boost (market is
        # less certain = better value signal than -200+ juice).
        prob_excess = max(0.0, cover_prob - MIN_LEG_COVER_PROB_DAILY)
        odds_quality = 1.05 if -145 <= odds <= -100 else 1.00
        leg_score = (edge * 0.60 + prob_excess * 0.40) * odds_quality

        dbg(f"  {team} {line:+.1f} @ {odds} [{entry['book']}]: cover={cover_prob:.3f} implied={implied:.3f} edge={edge:+.3f} leg_score={leg_score:.4f}")

        scored.append({
            "team": team,
            "game": info["game"],
            "sport": info["sport"],
            "std_spread": info["std_spread"],
            "margin": margin,
            "sigma": sigma,
            "line": line,
            "odds": odds,
            "book": entry["book"],
            "cover_prob": cover_prob,
            "edge": edge,
            "leg_score": leg_score,
        })

    if not scored:
        dbg("No scored entries — no alt spread data passed per-leg quality gates")
        return None

    # Step 3: Per book, pick best leg-score line per game, then try 3→2 legs (min 2)
    book_game_best = defaultdict(dict)
    for s in scored:
        bk, gm = s["book"], s["game"]
        if gm not in book_game_best[bk] or s["leg_score"] > book_game_best[bk][gm]["leg_score"]:
            book_game_best[bk][gm] = s

    best_result = None
    best_score = float("-inf")

    for book, game_bests in book_game_best.items():
        # Sort by composite leg_score (edge × 0.60 + prob_excess × 0.40 × odds_quality)
        entries = sorted(game_bests.values(), key=lambda x: x["leg_score"], reverse=True)
        dbg(f"Book {book}: {len(entries)} game(s)")
        for e in entries:
            dbg(f"  {e['game']} → {e['team']} {e['line']:+.1f} @ {e['odds']} edge={e['edge']:+.3f} leg_score={e['leg_score']:.4f}")

        # Min 2 legs — a single alt spread leg is a straight bet, not a parlay product
        for num_legs in [3, 2]:
            if len(entries) < num_legs:
                continue
            leg_entries = entries[:num_legs]
            combined_dec = 1.0
            for e in leg_entries:
                combined_dec *= american_to_decimal(e["odds"])
            parlay_odds = decimal_to_american(combined_dec)

            dbg(f"  {book} {num_legs}-leg combined: {parlay_odds:.0f}")

            if parlay_odds < MIN_COMBINED_ODDS_VAL:
                dbg(f"  {book} {num_legs}-leg: {parlay_odds:.0f} < {MIN_COMBINED_ODDS_VAL} — too juicy, skip")
                continue
            if parlay_odds > MAX_COMBINED_ODDS_VAL:
                dbg(f"  {book} {num_legs}-leg: {parlay_odds:.0f} > {MAX_COMBINED_ODDS_VAL} — too long, skip")
                continue

            total_leg_score = sum(e["leg_score"] for e in leg_entries)
            if total_leg_score > best_score:
                best_score = total_leg_score
                best_result = (book, leg_entries, parlay_odds, num_legs)
            break  # found valid leg count for this book

    if not best_result:
        dbg("No valid parlay found — all books either too juicy, no edge, or under 2 legs")
        return None

    best_book, best_entries, best_parlay_odds, num_legs = best_result

    legs = []
    for e in best_entries:
        bought_pts = (e["line"] - e["std_spread"]) if e["std_spread"] is not None else 0.0
        legs.append({
            "team": e["team"],
            "team_abbrev": get_team_abbrev(e["game"], ""),
            "game": e["game"],
            "margin": e["margin"],
            "std_spread": e["std_spread"],
            "alt_spread": e["line"],
            "bought_pts": bought_pts,
            "alt_cover_prob": e["cover_prob"],
            "real_odds": e["odds"],
            "real_book": display_book(best_book),
            "book_key": best_book,
            "sport": e["sport"],
            "decimal_odds": american_to_decimal(e["odds"]),
        })

    combined_prob = 1.0
    for leg in legs:
        combined_prob *= leg["alt_cover_prob"]

    return {
        "legs": legs,
        "num_legs": num_legs,
        "combined_prob": combined_prob,
        "parlay_odds": best_parlay_odds,
        "book": display_book(best_book),
        "has_real_odds": True,
    }
