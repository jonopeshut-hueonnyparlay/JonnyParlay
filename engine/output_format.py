"""Console/text card formatting (fmt_* helpers + full-card format_output).

Extracted from run_picks.py (extract-and-re-export refactor, Step 6) and
re-imported there so existing call sites and `from run_picks import ...` keep
resolving. Imports only {stdlib, book_names, market_config, thresholds,
calibrated, sizing} — never run_picks or the other extracted modules.
"""
from collections import defaultdict

from book_names import display_book
from market_config import SLOW_BOOKS
from thresholds import LONGSHOT_SIZE, MAX_PREMIUM_PICKS
from calibrated import SIGMA, SIGMA_WNBA, POISSON_STATS, PITCHER_STATS, BATTER_CORR_STATS
from sizing import size_daily_lay


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


def format_output(premium, safest5, all_qualified, all_picks, mode, today,
                   safest6_parlay=None, alt_spread_parlay=None, max_per_game=2,
                   killshots=None, units_already_bet=0.0):
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
            _inj = " [INJ]" if p.get("injury_trigger") else ""
            out.append(f"{e} {size:.2f}u | {p['player']} ({p.get('team_abbrev','')}) {fmt_dir(p['direction'])}{p['line']} {p['stat']} @ {fmt_odds(p['odds'])} ({display_book(p['book'])}){_inj}")
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
                    _inj_note = " [INJ]" if p.get("injury_trigger") else ""
                    _slow_note = " [SLOW BOOK]" if (p.get("injury_trigger") and p.get("book", "").lower() in SLOW_BOOKS) else ""
                    out.append(f"  {p.get('size',0):.2f}u | {p['player']} ({p.get('team_abbrev','')}) {fmt_dir(p['direction'])}{p['line']} {stat} @ {fmt_odds(p['odds'])} ({display_book(p['book'])}) | {fmt_pct(p['win_prob'])} | {fmt_pct(p['adj_edge'])} | {p['game']}{_inj_note}{_slow_note}")
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

    # === G. SANITY CHECK TABLE (PASS picks only) ===
    out.append(f"{'='*50}")
    out.append("G. SANITY CHECK TABLE")
    out.append(f"{'='*50}")
    out.append(f"{'Pick':<35} {'Proj':>5} {'Line':>5} {'Fair%':>6} {'NV%':>6} {'Edge':>6} {'AdjE':>6} {'Size':>5} {'Tier':>4}")
    out.append("─" * 100)
    pass_picks = sorted(all_qualified, key=lambda x: x.get("adj_edge", 0), reverse=True)
    for p in pass_picks:
        label = f"{p['player']} {fmt_dir(p['direction'])}{p['line']} {p['stat']}"[:34]
        size  = p.get("size", 0)
        nv    = p.get("nv_prob", 0)
        raw_e = p["raw_edge"]
        out.append(
            f"{label:<35} {p['proj']:5.1f} {p['line']:5.1f} {p['win_prob']*100:5.1f}% "
            f"{nv*100:5.1f}% {raw_e*100:5.1f}% {p['adj_edge']*100:5.1f}% "
            f"{size:5.2f} {p.get('tier',''):>4}"
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
        out.append("Max 3 Positions (per sport)")
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

    # === ALT SPREAD PARLAY ===
    _dlay_n = alt_spread_parlay.get("num_legs", "?") if alt_spread_parlay else "?"
    _dlay_bk = alt_spread_parlay.get("book", "") if alt_spread_parlay else ""
    _dlay_hdr = f"ALT SPREAD PARLAY — {_dlay_n}-Leg ({_dlay_bk})" if _dlay_bk else f"ALT SPREAD PARLAY — {_dlay_n}-Leg"
    out.append(f"{'='*50}")
    out.append(_dlay_hdr)
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
    stat_counts_chk = defaultdict(int)
    for p in premium:
        stat_counts_chk[p["stat"]] += 1
    max_same = max(stat_counts_chk.values()) if stat_counts_chk else 0
    has_u25_ast = any(p["stat"] == "AST" and p["direction"] == "under" and p["line"] in (1.5, 2.5) for p in all_qualified)
    has_u25_reb = any(p["stat"] == "REB" and p["direction"] == "under" and p["line"] <= 2.5 for p in all_qualified)
    has_reb_over = any(p["stat"] == "REB" and p["direction"] == "over" for p in all_qualified)
    has_g8_fail = any(
        (p["stat"] in ("AST","REB","SOG","K","HA","HITS") and p["line"] <= 1.5
         and not (p["stat"] == "AST" and p.get("sport") == "NHL"
                  and p["line"] == 0.5 and p["direction"] == "under")) or
        (p["stat"] == "AST" and p["direction"] == "over" and p["line"] <= 4.5
         and p.get("sport") != "WNBA") or
        (p["stat"] == "SOG" and p["direction"] == "under" and p["line"] <= 3.5) or
        (p["stat"] == "3PM" and p["direction"] == "over" and p["line"] <= 1.5
         and p.get("sport") != "WNBA")
        for p in all_qualified
    )
    has_heavy_juice = any(p["odds"] <= -150 for p in all_qualified)
    _STAT_MIN_WIN_PROB = {"TB": 0.60}
    has_g13b_fail = any(
        (p.get("stat") in _STAT_MIN_WIN_PROB and p.get("win_prob", 0) < _STAT_MIN_WIN_PROB[p["stat"]])
        or (p.get("stat") == "HRR" and p.get("line", 0) <= 0.5 and p.get("win_prob", 0) < 0.58)
        or (p.get("stat") == "HRR" and p.get("line", 0) > 0.5 and p.get("win_prob", 0) < 0.65)
        or p.get("stat") == "RA"
        for p in all_qualified
    )
    def _g14_fail(p):
        s, d, ln, pr = p["stat"], p["direction"], p["line"], p.get("proj", 0.0)
        sp = p.get("sport", "")
        if s in SIGMA and s not in POISSON_STATS:
            _s = (SIGMA_WNBA.get(s) if sp == "WNBA" else None) or SIGMA[s]
            _sig = max(pr * _s["mult"], _s["min"])
            return ((ln - pr) / _sig if d == "under" else (pr - ln) / _sig) < 0.10
        if s == "3PM" and sp == "WNBA":
            _s = SIGMA_WNBA["3PM"]; _sig = max(pr * _s["mult"], _s["min"])
            return ((ln - pr) / _sig if d == "under" else (pr - ln) / _sig) < 0.10
        return False
    has_g14_fail = any(_g14_fail(p) for p in all_qualified)
    has_g15_fail = any(
        p.get("stat") == "3PM"
        and p.get("pts_cv")
        and float(p["pts_cv"]) >= 0.60
        for p in all_qualified
    )
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

    # M7: include KILLSHOT units in daily cap validation (premium only was under-counting)
    if killshots is None:
        killshots = []
    ks_u = sum(p.get("size", 0) for p in killshots)
    # 16.3: include same-session parlay sizes (daily_lay + longshot) in display total.
    # SGP is posted via a separate flow and not passed here; the real 12u cap is still
    # enforced on the next sport's cross-run read of pick_log.csv.
    _lay_u = size_daily_lay(
        alt_spread_parlay.get("combined_prob", 0),
        alt_spread_parlay.get("parlay_odds", 0),
    ) if alt_spread_parlay and alt_spread_parlay.get("legs") else 0.0
    _longshot_u = LONGSHOT_SIZE if safest6_parlay and safest6_parlay.get("legs") else 0.0
    total_u_all = total_u + ks_u + _lay_u + _longshot_u + units_already_bet

    checks = [
        (f"Premium card: {n_prem} picks generated", n_prem == MAX_PREMIUM_PICKS or n_prem == 0),
        (f"Safest picks generated", len(safest5) > 0 or not all_qualified),
        (f"R9 directional balance: {n_overs_prem} overs on Premium", n_overs_prem >= 1 if n_overs_all >= 3 else True),
        (f"R10 same-stat cap: max {max_same} picks of same stat (any direction)", max_same <= 1),
        (f"R11 enforced: No AST under 1.5 or 2.5", not has_u25_ast),
        (f"R4 enforced: No REB Overs, no U2.5 REB", not has_reb_over and not has_u25_reb),
        (f"G8/G8B/G8C/G8D enforced: No AST/REB/SOG/K/HA/HITS at line ≤ 1.5 (exc. NHL AST 0.5u); no AST over ≤ 4.5; no SOG under ≤ 3.5; no 3PM over ≤ 1.5", not has_g8_fail),
        (f"G13B enforced: TB killed (G_TB_DISABLED), HRR fully killed (G_HRR_DISABLED), RA killed (G_RA_DISABLED)", not has_g13b_fail),
        (f"G14 enforced: Projection clearance (normal z≥0.10 for PTS/MLB stats)", not has_g14_fail),
        (f"G15 enforced: No 3PM bets for HIGH-VAR players (pts_cv>=0.60)", not has_g15_fail),
        (f"G7 enforced: No odds ≤ -150", not has_heavy_juice),
        (f"R7 enforced: Max per game = {max_game} (cap: {max_per_game})", max_game <= max_per_game),
        (f"G11 enforced: Max pitcher props per pitcher = {max_pitcher_props}", max_pitcher_props <= 1),
        (f"G11b enforced: Max batter corr props per batter = {max_batter_corr}", max_batter_corr <= 1),
        (f"All sizes ≤ 1.25u (excl. KILLSHOT)", all(p.get("size",0) <= 1.25 for p in all_qualified if p.get("tier") != "KILLSHOT")),
        (f"Daily cap (prev {units_already_bet:.2f}u + premium {total_u:.2f}u + KILLSHOT {ks_u:.2f}u + parlays {_lay_u+_longshot_u:.2f}u = {total_u_all:.2f}u) ≤ 12u", total_u_all <= 12.0),
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
