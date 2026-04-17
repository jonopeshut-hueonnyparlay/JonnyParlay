#!/usr/bin/env python3
"""
analyze_picks.py — Backtest analysis dashboard for pick_log.csv
Breaks down ROI, win rate, and edge accuracy by every dimension.

Usage:
    python analyze_picks.py                    # Full analysis
    python analyze_picks.py --sport NBA        # Filter to one sport
    python analyze_picks.py --since 2026-04-01 # Only recent picks
    python analyze_picks.py --stat AST         # Filter to one stat type
    python analyze_picks.py --export           # Save report to .txt file
"""

import csv, os, sys, argparse
from datetime import datetime
from pathlib import Path
from collections import defaultdict

PICK_LOG_PATH = os.path.expanduser("~/Documents/JonnyParlay/data/pick_log.csv")
OUTPUT_FOLDER = os.path.expanduser("~/Documents/JonnyParlay/data/picks")


def load_picks(path, sport_filter=None, since_filter=None, stat_filter=None):
    """Load graded picks from CSV."""
    picks = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            result = row.get("result", "").strip().upper()
            if result not in ("W", "L", "P"):
                continue  # Skip ungraded
            if sport_filter and row.get("sport", "").upper() != sport_filter.upper():
                continue
            if since_filter and row.get("date", "") < since_filter:
                continue
            if stat_filter and row.get("stat", "").upper() != stat_filter.upper():
                continue

            # Parse numeric fields
            try:
                row["odds_num"] = int(row.get("odds", 0)) if row.get("odds") else 0
                row["edge_num"] = float(row.get("edge", 0)) if row.get("edge") else 0.0
                row["size_num"] = float(row.get("size", 0)) if row.get("size") else 0.0
                row["pick_score_num"] = float(row.get("pick_score", 0)) if row.get("pick_score") else 0.0
                row["win_prob_num"] = float(row.get("win_prob", 0)) if row.get("win_prob") else 0.0
            except ValueError:
                row["odds_num"] = 0
                row["edge_num"] = 0.0
                row["size_num"] = 0.0
                row["pick_score_num"] = 0.0
                row["win_prob_num"] = 0.0

            row["result"] = result
            picks.append(row)
    return picks


def calc_metrics(picks):
    """Calculate W/L/P, win rate, ROI, units P&L."""
    w = sum(1 for p in picks if p["result"] == "W")
    l = sum(1 for p in picks if p["result"] == "L")
    push = sum(1 for p in picks if p["result"] == "P")
    total = w + l  # exclude pushes from rate
    win_rate = w / total if total > 0 else 0

    # Unit P&L
    units_pl = 0
    for p in picks:
        size = p["size_num"]
        odds = p["odds_num"]
        if p["result"] == "W":
            if odds > 0:
                units_pl += size * (odds / 100)
            elif odds < 0:
                units_pl += size * (100 / abs(odds))
        elif p["result"] == "L":
            units_pl -= size

    roi = (units_pl / sum(p["size_num"] for p in picks) * 100) if sum(p["size_num"] for p in picks) > 0 else 0

    # Average edge
    avg_edge = sum(p["edge_num"] for p in picks) / len(picks) if picks else 0

    # Calibration: predicted win% vs actual win%
    avg_predicted = sum(p["win_prob_num"] for p in picks) / len(picks) if picks else 0

    return {
        "total": len(picks), "w": w, "l": l, "push": push,
        "win_rate": win_rate, "units_pl": units_pl, "roi": roi,
        "avg_edge": avg_edge, "avg_predicted_wp": avg_predicted,
        "actual_wp": win_rate,
    }


def format_record(m):
    """Format a metrics dict as a readable line."""
    record = f"{m['w']}-{m['l']}"
    if m['push'] > 0:
        record += f"-{m['push']}P"
    return (f"{record} ({m['win_rate']:.1%}) | "
            f"{m['units_pl']:+.2f}u ({m['roi']:+.1f}% ROI) | "
            f"Avg Edge: {m['avg_edge']:.2%} | "
            f"Calib: {m['avg_predicted_wp']:.1%} pred → {m['actual_wp']:.1%} actual")


def breakdown(picks, key_fn, label, min_count=3):
    """Group picks by a key function and show metrics for each group."""
    groups = defaultdict(list)
    for p in picks:
        k = key_fn(p)
        if k:
            groups[k].append(p)

    lines = [f"\n  {'─'*60}", f"  {label}:", f"  {'─'*60}"]
    sorted_groups = sorted(groups.items(), key=lambda x: calc_metrics(x[1])["units_pl"], reverse=True)
    for key, group_picks in sorted_groups:
        if len(group_picks) < min_count:
            continue
        m = calc_metrics(group_picks)
        lines.append(f"    {key:20s} ({m['total']:3d} picks) → {format_record(m)}")

    if len(lines) == 3:
        lines.append("    (no groups with enough picks)")
    return "\n".join(lines)


def edge_bucket(edge):
    """Bucket edge values for grouping."""
    if edge < 0.03: return "< 3%"
    elif edge < 0.05: return "3-5%"
    elif edge < 0.08: return "5-8%"
    elif edge < 0.12: return "8-12%"
    else: return "12%+"


def pick_score_bucket(ps):
    """Bucket pick scores."""
    if ps < 3: return "< 3"
    elif ps < 5: return "3-5"
    elif ps < 8: return "5-8"
    elif ps < 12: return "8-12"
    else: return "12+"


def streak_analysis(picks):
    """Find current and longest win/loss streaks."""
    if not picks:
        return "No picks"

    sorted_picks = sorted(picks, key=lambda p: (p.get("date", ""), p.get("run_time", "")))

    current_streak = 0
    current_type = None
    longest_w = 0
    longest_l = 0
    temp_streak = 0
    temp_type = None

    for p in sorted_picks:
        r = p["result"]
        if r == "P":
            continue
        if r == temp_type:
            temp_streak += 1
        else:
            temp_type = r
            temp_streak = 1

        if r == "W":
            longest_w = max(longest_w, temp_streak)
        else:
            longest_l = max(longest_l, temp_streak)

    current_streak = temp_streak
    current_type = temp_type

    return f"Current: {current_streak}{current_type} | Best W streak: {longest_w} | Worst L streak: {longest_l}"


def daily_pl(picks):
    """Show daily P&L over time."""
    by_date = defaultdict(list)
    for p in picks:
        by_date[p.get("date", "unknown")].append(p)

    lines = [f"\n  {'─'*60}", "  Daily P&L:", f"  {'─'*60}"]
    running = 0
    for date in sorted(by_date.keys()):
        m = calc_metrics(by_date[date])
        running += m["units_pl"]
        bar_len = int(abs(m["units_pl"]) * 2)
        bar = ("█" * bar_len) if m["units_pl"] >= 0 else ("░" * bar_len)
        sign = "+" if m["units_pl"] >= 0 else ""
        lines.append(f"    {date}  {m['w']}-{m['l']:>2d}  {sign}{m['units_pl']:6.2f}u  {bar:20s}  (running: {running:+.2f}u)")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Backtest analysis for pick_log.csv")
    parser.add_argument("--sport", default=None, help="Filter by sport (NBA, NHL, MLB, etc.)")
    parser.add_argument("--since", default=None, help="Only picks from this date forward (YYYY-MM-DD)")
    parser.add_argument("--stat", default=None, help="Filter by stat type (AST, SOG, K, etc.)")
    parser.add_argument("--export", action="store_true", help="Save report to .txt file")
    args = parser.parse_args()

    log_path = Path(PICK_LOG_PATH)
    if not log_path.exists():
        print(f"  No pick log found at {log_path}")
        return

    picks = load_picks(log_path, args.sport, args.since, args.stat)
    if not picks:
        print("  No graded picks found matching filters")
        return

    # Build report
    report = []
    report.append("""
    ╔═══════════════════════════════════════════════════╗
    ║  JonnyParlay Backtest Analysis                    ║
    ║  Pick Log Performance Report                      ║
    ╚═══════════════════════════════════════════════════╝""")

    filters = []
    if args.sport: filters.append(f"Sport: {args.sport}")
    if args.since: filters.append(f"Since: {args.since}")
    if args.stat: filters.append(f"Stat: {args.stat}")
    if filters:
        report.append(f"  Filters: {' | '.join(filters)}")

    date_range = f"{min(p['date'] for p in picks)} → {max(p['date'] for p in picks)}"
    report.append(f"  Date range: {date_range}")
    report.append(f"  Total graded picks: {len(picks)}")

    # Overall metrics
    overall = calc_metrics(picks)
    report.append(f"\n  {'='*60}")
    report.append(f"  OVERALL: {format_record(overall)}")
    report.append(f"  {'='*60}")
    report.append(f"  Streaks: {streak_analysis(picks)}")

    # Breakdowns
    report.append(breakdown(picks, lambda p: p.get("sport", "?"), "BY SPORT", min_count=1))
    report.append(breakdown(picks, lambda p: p.get("stat", "?"), "BY STAT TYPE", min_count=2))
    report.append(breakdown(picks, lambda p: p.get("tier", "?"), "BY TIER", min_count=2))
    report.append(breakdown(picks, lambda p: p.get("direction", "?"), "BY DIRECTION (Over/Under)", min_count=3))
    report.append(breakdown(picks, lambda p: edge_bucket(p["edge_num"]), "BY EDGE BUCKET", min_count=2))
    report.append(breakdown(picks, lambda p: pick_score_bucket(p["pick_score_num"]), "BY PICK SCORE BUCKET", min_count=2))
    report.append(breakdown(picks, lambda p: p.get("mode", "?"), "BY MODE", min_count=1))
    report.append(breakdown(picks, lambda p: p.get("book", "?"), "BY BOOK", min_count=2))

    # Calibration analysis
    report.append(f"\n  {'─'*60}")
    report.append("  CALIBRATION (Predicted Win% vs Actual):")
    report.append(f"  {'─'*60}")
    wp_buckets = defaultdict(list)
    for p in picks:
        wp = p["win_prob_num"]
        if wp < 0.55: bucket = "50-55%"
        elif wp < 0.60: bucket = "55-60%"
        elif wp < 0.65: bucket = "60-65%"
        elif wp < 0.70: bucket = "65-70%"
        else: bucket = "70%+"
        wp_buckets[bucket].append(p)

    for bucket in ["50-55%", "55-60%", "60-65%", "65-70%", "70%+"]:
        if bucket in wp_buckets and len(wp_buckets[bucket]) >= 2:
            bp = wp_buckets[bucket]
            m = calc_metrics(bp)
            report.append(f"    Predicted {bucket:8s} ({m['total']:3d} picks) → Actual: {m['win_rate']:.1%}  |  {m['units_pl']:+.2f}u")

    # Daily P&L
    report.append(daily_pl(picks))

    # Top 10 best and worst picks
    report.append(f"\n  {'─'*60}")
    report.append("  TOP 10 PICKS (by unit profit):")
    report.append(f"  {'─'*60}")
    winners = sorted([p for p in picks if p["result"] == "W"],
                     key=lambda p: p["size_num"] * (p["odds_num"]/100 if p["odds_num"] > 0 else 100/abs(p["odds_num"]) if p["odds_num"] < 0 else 0),
                     reverse=True)[:10]
    for p in winners:
        odds = p["odds_num"]
        size = p["size_num"]
        profit = size * (odds/100 if odds > 0 else 100/abs(odds)) if odds != 0 else 0
        report.append(f"    +{profit:.2f}u  {p['player']} {p['direction']} {p['line']} {p['stat']} ({p['sport']}) @ {'+' if odds > 0 else ''}{odds}")

    report.append(f"\n  WORST 10 PICKS (biggest losses):")
    losers = sorted([p for p in picks if p["result"] == "L"],
                    key=lambda p: p["size_num"], reverse=True)[:10]
    for p in losers:
        report.append(f"    -{p['size_num']:.2f}u  {p['player']} {p['direction']} {p['line']} {p['stat']} ({p['sport']}) @ {'+' if p['odds_num'] > 0 else ''}{p['odds_num']}")

    full_report = "\n".join(report)
    print(full_report)

    if args.export:
        export_path = Path(OUTPUT_FOLDER) / f"backtest_{datetime.now().strftime('%Y-%m-%d')}.txt"
        export_path.parent.mkdir(parents=True, exist_ok=True)
        with open(export_path, "w", encoding="utf-8") as f:
            f.write(full_report)
        print(f"\n  📊 Report saved to {export_path}")


if __name__ == "__main__":
    main()
