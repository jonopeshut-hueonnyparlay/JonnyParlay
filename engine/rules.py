"""Hard rules, R12 cooldown, soft-rule premium selection, and daily caps.

Extracted from run_picks.py (extract-and-re-export refactor, Step 8) and
re-imported there so existing call sites and `from run_picks import ...` keep
resolving. Imports only {stdlib, paths, thresholds, calibrated, pick_log_lock,
pick_log_writers, name_norm} — never run_picks or the other extracted modules.
"""
import csv
import logging
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

from paths import PICK_LOG_PATH as _PICK_LOG_PATH_P
from thresholds import MAX_PREMIUM_PICKS, MIN_PICK_SCORE, MIN_OVER_SCORE, MIN_WIN_PROB
from calibrated import PITCHER_STATS, COMBO_STATS
from pick_log_lock import _pick_log_lock
from pick_log_writers import log_blocked_pick
from name_norm import normalize_name

logger = logging.getLogger("jonnyparlay")

PICK_LOG_PATH = str(_PICK_LOG_PATH_P)


def apply_hard_rules(picks, shadow_dest=None, log_blocked=False):
    """Apply R4 (REB bans), R11 (AST under 1.5/2.5 ban) before anything else.

    shadow_dest: if provided, killed picks are appended here (for shadow logging)
    instead of being silently dropped.
    """
    filtered = []
    for p in picks:
        # R4: REB Overs — structural over-projection; routed to shadow
        if p["stat"] == "REB" and p["direction"] == "over":
            if shadow_dest is not None:
                p["gate_result"] = "R4_REB_OVER"
                p.setdefault("pick_score", None)
                shadow_dest.append(p)
            continue
        # R4: U2.5 REB — volatile at low lines; routed to shadow
        if p["stat"] == "REB" and p["direction"] == "under" and p["line"] <= 2.5:
            if shadow_dest is not None:
                p["gate_result"] = "R4_REB_U25"
                p.setdefault("pick_score", None)
                shadow_dest.append(p)
            continue
        # R11: DATA_GATED protective rule (gambler's-fallacy-adjacent) — AST under 1.5/2.5
        # ban kept ACTIVE. Empirical basis is thin: n=15, ROI +0.017 (CI ±25pp — marginally
        # positive); AST→T1B floor 0.06 + BM shrinkage already screen these. Reclassified
        # per Plan 10 §R11 (mirror R9/R12 treatment); lift at n≥40 shadow (calib bias ±3pp
        # + CLV≥0). Logs to pick_log_blocked.csv. 0.5 and >2.5 are live.
        if p["stat"] == "AST" and p["direction"] == "under" and p["line"] in (1.5, 2.5):
            p["gate_result"] = "R11_AST_U25"
            if log_blocked:
                log_blocked_pick(p)
            if shadow_dest is not None:
                p.setdefault("pick_score", None)
                shadow_dest.append(p)
            continue
        filtered.append(p)
    return filtered

def auto_r12_from_log(today_str: str, window_days: int = 5) -> list[str]:
    """Read pick_log.csv and return player names with a loss in the last window_days.
    These are auto-added to the R12 cooldown list so you never have to pass --cooldown manually.
    Only counts primary/bonus picks (not manual) to avoid polluting the list with one-offs.
    No sport filter: a player on NBA cooldown also suppresses NHL/MLB entries for that name.
    Near-zero practical risk given naming divergence across sports."""
    log_path = Path(PICK_LOG_PATH)
    if not log_path.exists():
        return []
    try:
        # F2.8: was window_days-1 (gave 4 days not 5); fixed to window_days
        cutoff = (datetime.strptime(today_str, "%Y-%m-%d") - timedelta(days=window_days)).strftime("%Y-%m-%d")
        # Shared lock — must not race a concurrent capture_clv write (audit H-8).
        with _pick_log_lock(log_path):
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
    """R12: Skip players whose last MBP pick was a loss within 5 days.

    Product rule, NOT an EV rule (Plan 9 §9J reclassification): avoids
    re-posting a player who just failed the card. Not evidence-based as risk
    control — one loss has ~40-45% probability even when the model is correct
    (likelihood ratio ≈ 1, posterior edge unchanged). Classify as
    gambler's-fallacy-adjacent; EV cost unknown (cooldown removes players
    exactly when the book may have moved the line toward us off the visible
    miss). When CLV data matures: replace the loss trigger with a
    negative-CLV condition (e.g., CLV ≤ −2pp on last pick, or 2+ consecutive
    losses with negative CLV).
    """
    if not cooldown_players:
        return picks
    cool_set = {normalize_name(n) for n in cooldown_players}
    return [p for p in picks if normalize_name(p["player"]) not in cool_set]

def apply_soft_rules_premium(premium, all_qualifying, max_per_game=2):
    """
    Apply R6, R7, R9, R10 to build the Premium card.

    R8 (reserved T1/T1B slots) RETIRED 2026-06-06 (Plan 9 §9F): T1 WR 46.6% < 50%
    hit the pre-registered removal trigger. Tiers are now calibration-quality
    routing buckets, not conviction levels — reserving card slots for the
    moderate-calibration bucket was backwards. All slots fill by pure Pick Score.

    R9 is a product/optics rule, not an EV rule (Plan 9 §9J) — see the
    comment at the R9 block below.

    max_per_game — R7 override (default 2). Thin-slate nights can raise this.
    """
    all_by_ps = sorted(all_qualifying, key=lambda p: p["pick_score"], reverse=True)

    # Count how many overs passed all gates
    total_overs = sum(1 for p in all_qualifying if p["direction"] == "over")

    premium = []
    used = set()  # track by id() to avoid duplicates
    game_count = defaultdict(int)
    stat_count = defaultdict(int)          # R10: per-stat total (any direction)
    pitcher_game_dir_count = defaultdict(int)  # G12: (game, direction) → pitcher prop count
    over_count = 0
    has_over = False

    def can_add(p):
        game = p.get("game", "")
        # Score floors: kill low-conviction filler (score<25 overall; overs need 40+)
        if p.get("pick_score", 0) < MIN_PICK_SCORE:
            return False
        if p["direction"] == "over" and p.get("pick_score", 0) < MIN_OVER_SCORE:
            return False
        if p.get("win_prob", 1.0) < MIN_WIN_PROB:
            return False
        if game_count[game] >= max_per_game:  # R7
            return False
        if stat_count[p["stat"]] >= 1:  # R10: max 1 pick per stat (3-pick card)
            return False
        if p["direction"] == "over" and over_count >= 2:  # R6: max 2 overs on 3-pick card
            return False
        # G12: Max 2 same-direction pitcher props per game on Premium
        if p["stat"] in PITCHER_STATS:
            pgd_key = (game, p["direction"])
            if pitcher_game_dir_count[pgd_key] >= 2:
                return False
        # R_COMBO: Max 1 combo pick per player — prevents correlated-loss stacking
        # (e.g., Clark PRA+PA+PR all fail when PTS component misses, as on opening day 2026).
        if p["stat"] in COMBO_STATS:
            player = p.get("player", "")
            if player and any(q.get("player") == player and q["stat"] in COMBO_STATS for q in premium):
                return False
        return True

    def add_pick(p):
        nonlocal over_count, has_over
        premium.append(p)
        used.add(id(p))
        game = p.get("game", "")
        game_count[game] += 1
        stat_count[p["stat"]] += 1
        if p["stat"] in PITCHER_STATS:
            pitcher_game_dir_count[(game, p["direction"])] += 1
        if p["direction"] == "over":
            over_count += 1
            has_over = True

    # Fill all slots (up to MAX_PREMIUM_PICKS) by pure Pick Score from ALL tiers
    # (R8 T1/T1B reservation retired 2026-06-06, Plan 9 §9F)
    for p in all_by_ps:
        if len(premium) >= MAX_PREMIUM_PICKS:
            break
        if id(p) in used:
            continue
        if can_add(p):
            add_pick(p)

    # R9: Product/optics rule — ensures premium card has at least one over direction
    # when 3+ overs qualified. Not an EV rule (forced-over may have lower score than
    # displaced pick; a model leaning under may be correctly harvesting the over-shade).
    # Cost is unmeasured. When CLV data matures, add a monitor:
    # cumulative score-gap + realized P&L of forced-over vs displaced picks. (Plan 9 §9J)
    if total_overs >= 3 and not has_over and len(premium) == MAX_PREMIUM_PICKS:
        # Identify the lowest-PS non-over to remove (last in list = lowest PS)
        swap_idx = None
        for i in range(len(premium) - 1, -1, -1):
            if premium[i]["direction"] != "over":
                swap_idx = i
                break
        if swap_idx is not None:
            old_pick = premium[swap_idx]
            old_game = old_pick.get("game", "")
            # Temporarily remove old_pick's contributions so can_add() sees correct state
            game_count[old_game] -= 1
            stat_count[old_pick["stat"]] -= 1
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
                stat_count[best_over["stat"]] += 1
                if best_over["stat"] in PITCHER_STATS:
                    pitcher_game_dir_count[(new_game, best_over["direction"])] += 1
                used.add(id(best_over))
                over_count += 1
                has_over = True
            else:
                # No valid over found — restore old_pick's contributions
                game_count[old_game] += 1
                stat_count[old_pick["stat"]] += 1
                if old_pick["stat"] in PITCHER_STATS:
                    pitcher_game_dir_count[(old_game, old_pick["direction"])] += 1
                used.add(id(old_pick))

    return premium[:MAX_PREMIUM_PICKS]

def apply_caps(picks, sport_totals, max_per_game=2, units_already_bet=0.0):
    """Apply daily caps: per-stat, per-game, per-sport, daily total.
    Includes G12: max 2 same-direction pitcher props per game.

    max_per_game — R7 override (default 2). Thin-slate nights can raise this.
    units_already_bet — units logged in earlier runs today (cross-run 12u cap)."""
    # Sort by pick_score descending so best picks get cap priority (fixes H4 bug)
    picks = sorted(picks, key=lambda p: p.get("pick_score", 0), reverse=True)

    result = []
    stat_count = defaultdict(int)
    game_count = defaultdict(int)
    sport_units = defaultdict(float)
    total_units = units_already_bet  # start at cross-run total, not 0
    pitcher_game_dir = defaultdict(int)   # G12: (game, direction) → count of pitcher props

    # NHL SOG gets 6 per stat, everything else 2
    STAT_CAP = defaultdict(lambda: 2)
    STAT_CAP["SOG"] = 6

    SPORT_UNIT_CAP = {"NBA": 8.0, "WNBA": 4.0, "NHL": 5.0, "NFL": 5.0, "MLB": 8.0}

    hrr_team_game = defaultdict(int)   # (team, game) → count of HRR picks; max 1 per team per game

    for p in picks:
        stat = p["stat"]
        game = p.get("game", "")
        sport = p.get("sport", "NBA")
        size = p["size"]

        if stat_count[stat] >= STAT_CAP[stat]:
            continue
        if game_count[game] >= max_per_game:
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

        # G_HRR_TEAM: HRR within-lineup correlation (r≈0.25-0.35). Max 1 HRR per team per game.
        if stat == "HRR":
            team = p.get("team", p.get("team_abbrev", ""))
            if hrr_team_game[(team, game)] >= 1:
                continue

        result.append(p)
        stat_count[stat] += 1
        game_count[game] += 1
        sport_units[sport] += size
        total_units += size
        if stat in PITCHER_STATS:
            pitcher_game_dir[(game, p["direction"])] += 1
        if stat == "HRR":
            team = p.get("team", p.get("team_abbrev", ""))
            hrr_team_game[(team, game)] += 1

    return result
