#!/usr/bin/env python3
"""
clv_report.py — Performance + CLV analysis report.

Reads pick_log.csv and prints a rolling edge quality dashboard.
Run any time. CLV columns populate as capture_clv.py runs.

Usage:
    python clv_report.py [--days N] [--sport SPORT] [--tier TIER]

Options:
    --days   Look-back window in days (default: 30)
    --sport  Filter by sport (NBA, NHL, MLB, NFL, etc.)
    --tier   Filter by tier (T1, T2, T3, T1B, KILLSHOT)
"""

import argparse
import csv
import math
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

# Canonical locked-reader helper — every pick_log reader must take the same
# FileLock as the writers (audit H-8 / M-series).
sys.path.insert(0, str(Path(__file__).resolve().parent))
from pick_log_io import load_rows  # noqa: E402

# ── Paths ─────────────────────────────────────────────────────────────────────
# Audit M-26 (closed Apr 21 2026): path resolution now routes through
# engine/paths.py so a $JONNYPARLAY_ROOT override works the same way here
# as in every other tool. The previous engine-folder-heuristic is preserved
# as a fallback inside paths.py's _resolve_project_root, so invoking
# ``python clv_report.py`` from either the repo root or engine/ still works
# with no env var set.
from paths import (  # noqa: E402
    DATA_DIR,
    PICK_LOG_PATH as PICK_LOG,
    PICK_LOG_MANUAL_PATH as PICK_LOG_MANUAL,
    PICK_LOG_MLB_PATH,
)

SHADOW_LOGS = {
    "MLB": PICK_LOG_MLB_PATH,
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def implied_prob(american_odds):
    try:
        o = float(american_odds)
    except (ValueError, TypeError):
        return None
    if o < 0:
        return abs(o) / (abs(o) + 100)
    else:
        return 100 / (o + 100)


def payout_mult(american_odds):
    """Return net payout multiplier for 1 unit risked."""
    try:
        o = float(american_odds)
    except (ValueError, TypeError):
        return None
    if o < 0:
        return 100 / abs(o)
    else:
        return o / 100


def units_pnl(result, size, odds):
    """Calculate units P&L for a pick."""
    try:
        size = float(size)
        mult = payout_mult(odds)
    except (ValueError, TypeError):
        return 0.0
    if result == "W":
        return size * mult
    elif result == "L":
        return -size
    else:  # P or blank
        return 0.0


def safe_float(val, default=None):
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def pct(val, total):
    return f"{val/total*100:.1f}%" if total > 0 else "—"


def clv_grade(avg_clv):
    """Grade CLV quality."""
    if avg_clv is None:
        return "—"
    if avg_clv >= 0.04:
        return "🟢 Strong"
    elif avg_clv >= 0.02:
        return "🟡 Solid"
    elif avg_clv >= 0.00:
        return "🟡 Marginal"
    else:
        return "🔴 Negative"


def roi_grade(roi):
    if roi >= 0.08:
        return "🟢"
    elif roi >= 0.03:
        return "🟡"
    elif roi >= 0:
        return "⚪"
    else:
        return "🔴"


# ── Load ──────────────────────────────────────────────────────────────────────

def load_all_picks(days, sport_filter, tier_filter, stat_filter=None, include_shadow=False):
    """Load graded (W/L/P) picks from the main + manual + optional shadow
    logs, filtered to the last ``days`` days, optional sport, optional tier.

    Manual picks are real bets so their P&L/ROI is included.  They have no
    CLV data (capture_clv skips the manual log) so they contribute to
    volume/ROI but don't move CLV averages.

    Arch note #3: row-reading + filtering goes through
    ``pick_log_io.load_rows`` — one audited open+lock+filter path.
    """
    cutoff = (datetime.now(ZoneInfo("America/New_York")) - timedelta(days=days)).strftime("%Y-%m-%d")

    log_files = [PICK_LOG]
    if PICK_LOG_MANUAL.exists():
        log_files.append(PICK_LOG_MANUAL)
    if include_shadow:
        log_files += [p for p in SHADOW_LOGS.values() if p.exists()]

    rows = load_rows(
        log_files,
        sports=[sport_filter] if sport_filter else None,
        tiers=[tier_filter] if tier_filter else None,
        since=cutoff,
        exclude_run_types=["daily_lay"],
        exclude_stats=["PARLAY"],
        graded_only=True,
    )
    if stat_filter:
        rows = [r for r in rows if r.get("stat", "").upper() == stat_filter.upper()]
    return rows


# ── Analysis ──────────────────────────────────────────────────────────────────

def analyze(picks):
    """Return structured stats dict for a list of picks."""
    w = l = p = 0
    units_won = 0.0
    units_risked = 0.0
    edges = []
    pick_scores = []
    clvs = []

    for pick in picks:
        result = pick.get("result", "")
        size   = safe_float(pick.get("size"), 0)
        odds   = safe_float(pick.get("odds"))
        edge   = safe_float(pick.get("edge"))
        score  = safe_float(pick.get("pick_score"))
        clv_raw = safe_float(pick.get("clv"))

        if result == "W":
            w += 1
        elif result == "L":
            l += 1
        elif result == "P":
            p += 1

        pnl = units_pnl(result, size, odds)
        units_won += pnl
        if result in ("W", "L"):
            units_risked += size

        if edge is not None:
            edges.append(edge)
        if score is not None:
            pick_scores.append(score)
        if clv_raw is not None:
            clvs.append(clv_raw)

    total_graded = w + l + p
    win_rate = w / (w + l) if (w + l) > 0 else None
    avg_edge = sum(edges) / len(edges) if edges else None
    avg_score = sum(pick_scores) / len(pick_scores) if pick_scores else None
    roi = units_won / units_risked if units_risked > 0 else None
    avg_clv = sum(clvs) / len(clvs) if clvs else None
    clv_beat_rate = sum(1 for c in clvs if c > 0) / len(clvs) if clvs else None

    return {
        "total": total_graded,
        "w": w, "l": l, "p": p,
        "win_rate": win_rate,
        "units_won": units_won,
        "units_risked": units_risked,
        "roi": roi,
        "avg_edge": avg_edge,
        "avg_score": avg_score,
        "avg_clv": avg_clv,
        "clv_beat_rate": clv_beat_rate,
        "clv_n": len(clvs),
    }


def fmt_stat(label, value, fmt=".4f", suffix=""):
    if value is None:
        return f"  {label:<22} {'—'}"
    return f"  {label:<22} {value:{fmt}}{suffix}"


def fmt_record(stats):
    w, l, p = stats["w"], stats["l"], stats["p"]
    wr = f"{stats['win_rate']*100:.1f}%" if stats["win_rate"] is not None else "—"
    return f"{w}-{l}{f'-{p}P' if p else ''} ({wr})"


def section(title):
    print(f"\n{'─'*56}")
    print(f"  {title}")
    print(f"{'─'*56}")


# ── Main report ───────────────────────────────────────────────────────────────

def run(days, sport_filter, tier_filter, stat_filter=None, include_shadow=False):
    picks = load_all_picks(days, sport_filter, tier_filter, stat_filter=stat_filter,
                           include_shadow=include_shadow)

    filters = []
    if sport_filter:
        filters.append(sport_filter.upper())
    if tier_filter:
        filters.append(tier_filter.upper())
    if stat_filter:
        filters.append(stat_filter.upper())
    filter_str = f" [{', '.join(filters)}]" if filters else ""

    print(f"\n{'═'*56}")
    print(f"  picksbyjonny — CLV + Performance Report")
    print(f"  Last {days} days{filter_str}  ·  {len(picks)} graded picks")
    print(f"{'═'*56}")

    if not picks:
        print("\n  No graded picks in this window.\n")
        return

    # ── Overall ───────────────────────────────────────────────────────────────
    s = analyze(picks)
    section("OVERALL")
    print(f"  Record:   {fmt_record(s)}")
    pnl_sign = "+" if s["units_won"] >= 0 else ""
    print(f"  Units:    {pnl_sign}{s['units_won']:.2f}u  (risked {s['units_risked']:.2f}u)")
    if s["roi"] is not None:
        roi_sign = "+" if s["roi"] >= 0 else ""
        print(f"  ROI:      {roi_grade(s['roi'])} {roi_sign}{s['roi']*100:.1f}%")
    print(f"  Avg Edge: {s['avg_edge']*100:.2f}%" if s["avg_edge"] is not None else "  Avg Edge: —")
    print(f"  Avg Score:{s['avg_score']:.1f}" if s["avg_score"] is not None else "  Avg Score: —")

    if s["clv_n"] > 0:
        clv_sign = "+" if s["avg_clv"] >= 0 else ""
        beat_pct = f"{s['clv_beat_rate']*100:.0f}%" if s["clv_beat_rate"] is not None else "—"
        print(f"\n  CLV:      {clv_grade(s['avg_clv'])}  avg {clv_sign}{s['avg_clv']*100:.2f}%  ({s['clv_n']} samples, {beat_pct} beat close)")
    else:
        print(f"\n  CLV:      — (no closing odds captured yet)")

    # ── By Tier ───────────────────────────────────────────────────────────────
    section("BY TIER")
    tiers_order = ["KILLSHOT", "T1", "T1B", "T2", "T3"]
    by_tier = defaultdict(list)
    for p in picks:
        by_tier[p.get("tier", "?")].append(p)

    all_tiers = tiers_order + [t for t in by_tier if t not in tiers_order]
    for tier in all_tiers:
        tp = by_tier.get(tier, [])
        if not tp:
            continue
        ts = analyze(tp)
        pnl = f"{'+' if ts['units_won']>=0 else ''}{ts['units_won']:.2f}u"
        clv_str = ""
        if ts["clv_n"] > 0:
            clv_str = f"  CLV {'+' if ts['avg_clv']>=0 else ''}{ts['avg_clv']*100:.2f}% ({ts['clv_n']})"
        roi_str = f"  ROI {'+' if (ts['roi'] or 0)>=0 else ''}{(ts['roi'] or 0)*100:.1f}%" if ts["roi"] is not None else ""
        print(f"  {tier:<10} {fmt_record(ts):<18} {pnl:<10}{roi_str}{clv_str}")

    # ── By Sport ──────────────────────────────────────────────────────────────
    section("BY SPORT")
    by_sport = defaultdict(list)
    for p in picks:
        by_sport[p.get("sport", "?")].append(p)

    for sport in sorted(by_sport):
        sp = by_sport[sport]
        ss = analyze(sp)
        pnl = f"{'+' if ss['units_won']>=0 else ''}{ss['units_won']:.2f}u"
        clv_str = ""
        if ss["clv_n"] > 0:
            clv_str = f"  CLV {'+' if ss['avg_clv']>=0 else ''}{ss['avg_clv']*100:.2f}%"
        roi_str = f"  ROI {'+' if (ss['roi'] or 0)>=0 else ''}{(ss['roi'] or 0)*100:.1f}%" if ss["roi"] is not None else ""
        print(f"  {sport:<10} {fmt_record(ss):<18} {pnl:<10}{roi_str}{clv_str}")

    # ── By Stat ───────────────────────────────────────────────────────────────
    # Per-stat CLV table (T3, 2026-05-02): stats with N>=5, sorted by avg_clv desc.
    # Shows CLV sample count to surface which stats have enough data.
    section("BY STAT TYPE")
    by_stat = defaultdict(list)
    for p in picks:
        by_stat[p.get("stat", "?")].append(p)

    stat_rows = []
    for stat, sp in by_stat.items():
        ss = analyze(sp)
        stat_rows.append((stat, ss))
    stat_rows.sort(key=lambda x: x[1]["total"], reverse=True)

    clv_stat_rows = [(st, ss) for st, ss in stat_rows if ss["clv_n"] >= 5]
    clv_stat_rows.sort(key=lambda x: x[1]["avg_clv"] if x[1]["avg_clv"] is not None else -float("inf"),
                       reverse=True)  # H12: -99 → -inf so stats with no CLV data sort below any real value

    for stat, ss in stat_rows:
        pnl = f"{'+' if ss['units_won']>=0 else ''}{ss['units_won']:.2f}u"
        clv_str = ""
        if ss["clv_n"] > 0:
            clv_str = f"  CLV {'+' if ss['avg_clv']>=0 else ''}{ss['avg_clv']*100:.2f}% (n={ss['clv_n']})"
        print(f"  {stat:<12} {fmt_record(ss):<18} {pnl:<10}{clv_str}")

    if clv_stat_rows:
        print(f"\n  CLV ranking by stat (n≥5, sorted best→worst):")
        print(f"  {'Stat':<12}  {'Avg CLV':>9}  {'Beat%':>7}  {'n':>5}")
        for stat, ss in clv_stat_rows:
            beat = f"{ss['clv_beat_rate']*100:.0f}%" if ss.get("clv_beat_rate") is not None else "—"
            clv_sign = "+" if ss["avg_clv"] >= 0 else ""
            print(f"  {stat:<12}  {clv_sign}{ss['avg_clv']*100:>8.2f}%  {beat:>7}  {ss['clv_n']:>5}")

    # ── CLV Breakdown (when data exists) ──────────────────────────────────────
    clv_picks = [p for p in picks if safe_float(p.get("clv")) is not None]
    if clv_picks:
        section(f"CLV BREAKDOWN  ({len(clv_picks)}/{len(picks)} picks with closing odds)")
        pos = [p for p in clv_picks if safe_float(p.get("clv"), 0) > 0]
        neg = [p for p in clv_picks if safe_float(p.get("clv"), 0) <= 0]
        print(f"  Beat close:   {len(pos)}/{len(clv_picks)} ({len(pos)/len(clv_picks)*100:.0f}%)")

        if pos:
            ps = analyze(pos)
            print(f"  +CLV record:  {fmt_record(ps)}  {'+' if ps['units_won']>=0 else ''}{ps['units_won']:.2f}u")
        if neg:
            ns = analyze(neg)
            pnl = f"{'+' if ns['units_won']>=0 else ''}{ns['units_won']:.2f}u"
            print(f"  -CLV record:  {fmt_record(ns)}  {pnl}")

        # Rolling 7-day CLV trend  # M6: OrderedDict import removed — was unused
        dates = sorted(set(p.get("date", "") for p in clv_picks))
        if len(dates) >= 3:
            print(f"\n  7-day CLV trend:")
            day_clvs = defaultdict(list)
            for p in clv_picks:
                day_clvs[p.get("date", "")].append(safe_float(p.get("clv"), 0))
            for d in sorted(day_clvs)[-7:]:
                vals = day_clvs[d]
                avg = sum(vals) / len(vals)
                bar = "▓" * max(0, int(avg * 500)) if avg > 0 else "░" * max(0, int(abs(avg) * 500))
                sign = "+" if avg >= 0 else ""
                print(f"  {d}  {sign}{avg*100:.2f}%  {bar[:20]}")
    else:
        section("CLV BREAKDOWN")
        print(f"  No closing odds captured yet.")
        print(f"  Run capture_clv.py before each game session to start tracking.")

    # ── Recent picks ──────────────────────────────────────────────────────────
    section("LAST 10 PICKS")
    recent = sorted(picks, key=lambda x: (x.get("date",""), x.get("run_time","")), reverse=True)[:10]
    for p in recent:
        result = p.get("result", "?")
        icon = "✓" if result == "W" else ("✗" if result == "L" else "·")
        clv_raw = safe_float(p.get("clv"))
        clv_str = f"  CLV {'+' if clv_raw>=0 else ''}{clv_raw*100:.1f}%" if clv_raw is not None else ""
        tier = p.get("tier", "")
        player = p.get("player", "")[:28]
        stat = p.get("stat", "")
        line = p.get("line", "")
        direction = p.get("direction", "")
        print(f"  {icon} {p.get('date','')}  {tier:<10} {player:<28} {stat} {line} {direction}{clv_str}")

    print(f"\n{'='*56}\n")


def main():
    parser = argparse.ArgumentParser(description="CLV + performance report")
    parser.add_argument("--version", action="version", version="clv_report 1.0.0")  # L6
    parser.add_argument("--days",   type=int, default=30, help="Look-back days (default: 30)")
    parser.add_argument("--sport",  default=None, help="Filter by sport (NBA, NHL, etc.)")
    parser.add_argument("--tier",   default=None, help="Filter by tier (T1, T2, KILLSHOT, etc.)")
    parser.add_argument("--stat",   default=None,
                        help="Filter by stat (PTS, AST, REB, 3PM, SOG, etc.) — case-insensitive")
    parser.add_argument("--shadow", action="store_true", help="Include shadow (MLB) log")
    args = parser.parse_args()
    run(args.days, args.sport, args.tier,
        stat_filter=args.stat.upper() if args.stat else None,  # M28: normalize before passing down
        include_shadow=args.shadow)


if __name__ == "__main__":
    main()
