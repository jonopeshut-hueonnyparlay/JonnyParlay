#!/usr/bin/env python3
"""
analyze_picks.py — Backtest analysis dashboard for pick_log.csv
Breaks down ROI, win rate, and edge accuracy by every dimension.

Usage:
    python analyze_picks.py                    # Full analysis
    python analyze_picks.py --sport NBA        # Filter to one sport
    python analyze_picks.py --since 2026-04-01 # Only recent picks
    python analyze_picks.py --stat AST         # Filter to one stat type
    python analyze_picks.py --shadow           # Include MLB shadow log
    python analyze_picks.py --model-only       # Exclude manual picks
    python analyze_picks.py --export           # Save report to .txt file
"""

import csv, os, sys, argparse
from datetime import datetime
from pathlib import Path
from collections import defaultdict
from zoneinfo import ZoneInfo

# Canonical locked-reader helper — every pick_log reader must take the same
# FileLock as the writers (audit H-8 / M-series).
sys.path.insert(0, str(Path(__file__).resolve().parent))
from pick_log_io import load_rows  # noqa: E402
# Canonical pick-label formatter (audit L-3). Use the same short/long
# label helpers as weekly_recap so a new stat type only has to be taught
# to pick_labels.py once.
from pick_labels import detail_line as _pick_detail_line  # noqa: E402

# M9: resolved via paths.py — honours $JONNYPARLAY_ROOT
from paths import (  # noqa: E402
    PICK_LOG_PATH as _PICK_LOG_PATH_P,
    PICK_LOG_MANUAL_PATH as _PICK_LOG_MANUAL_PATH_P,
    PICK_LOG_MLB_PATH as _PICK_LOG_MLB_PATH_P,
    data_path as _data_path,
)

PICK_LOG_PATH        = str(_PICK_LOG_PATH_P)
PICK_LOG_MANUAL_PATH = str(_PICK_LOG_MANUAL_PATH_P)
PICK_LOG_MLB_PATH    = str(_PICK_LOG_MLB_PATH_P)
OUTPUT_FOLDER        = str(_data_path("picks"))

MIN_SAMPLE_NOTE = 20  # Warn when a bucket has fewer than this many picks


def _parse_odds(s):
    try:
        return int(float(str(s).replace("+", ""))) if s else 0
    except (ValueError, TypeError):
        return 0

def _parse_float(s, default=0.0):
    try:
        return float(s) if s else default
    except (ValueError, TypeError):
        return default


def load_picks(path, sport_filter=None, since_filter=None, stat_filter=None,
               extra_paths=None, exclude_run_types=None):
    """Load graded picks from one or more CSV logs.

    Delegates row-reading + filtering to ``pick_log_io.load_rows`` (arch
    note #3) so every consumer of pick_log.csv shares a single audited
    open+lock+filter core. Numeric enrichment of odds/edge/size stays
    local to the analyzer — downstream breakdowns need those fields.
    """
    paths = [path] + list(extra_paths or [])
    picks = load_rows(
        paths,
        sports=[sport_filter] if sport_filter else None,
        since=since_filter,
        stats=[stat_filter] if stat_filter else None,
        exclude_run_types=exclude_run_types,
        graded_only=True,
    )
    for row in picks:
        row["odds_num"]       = _parse_odds(row.get("odds"))
        row["edge_num"]       = _parse_float(row.get("edge"))
        row["size_num"]       = _parse_float(row.get("size"))
        row["pick_score_num"] = _parse_float(row.get("pick_score"))
        row["win_prob_num"]   = _parse_float(row.get("win_prob"))
        row["result"]         = (row.get("result") or "").strip().upper()
    return picks


def calc_metrics(picks):
    """Calculate W/L/P, win rate, ROI, units P&L."""
    w    = sum(1 for p in picks if p["result"] == "W")
    l    = sum(1 for p in picks if p["result"] == "L")
    push = sum(1 for p in picks if p["result"] == "P")
    total = w + l
    win_rate = w / total if total > 0 else 0

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

    risked = sum(p["size_num"] for p in picks if p["result"] != "P")
    roi = (units_pl / risked * 100) if risked > 0 else 0
    avg_edge = sum(p["edge_num"] for p in picks) / len(picks) if picks else 0
    avg_predicted = sum(p["win_prob_num"] for p in picks) / len(picks) if picks else 0

    return {
        "total": len(picks), "w": w, "l": l, "push": push,
        "win_rate": win_rate, "units_pl": units_pl, "roi": roi,
        "avg_edge": avg_edge, "avg_predicted_wp": avg_predicted,
        "actual_wp": win_rate,
    }


def format_record(m, warn_sample=False):
    """Format a metrics dict as a readable line."""
    record = f"{m['w']}-{m['l']}"
    if m['push'] > 0:
        record += f"-{m['push']}P"
    note = f"  ⚠ small sample (n={m['total']})" if warn_sample and m['total'] < MIN_SAMPLE_NOTE else ""
    return (f"{record} ({m['win_rate']:.1%}) | "
            f"{m['units_pl']:+.2f}u ({m['roi']:+.1f}% ROI) | "
            f"Avg Edge: {m['avg_edge']:.2%} | "
            f"Calib: {m['avg_predicted_wp']:.1%} pred → {m['actual_wp']:.1%} actual"
            f"{note}")


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
        warn = m["total"] < MIN_SAMPLE_NOTE
        lines.append(f"    {key:20s} ({m['total']:3d} picks) → {format_record(m, warn_sample=warn)}")

    if len(lines) == 3:
        lines.append("    (no groups with enough picks)")
    return "\n".join(lines)


def odds_bucket(odds):
    """Bucket American odds for grouping."""
    if odds == 0:    return "unknown"
    if odds >= 100:  return "+100 or better"
    if odds >= -109: return "-100 to -109"
    if odds >= -119: return "-110 to -119"
    if odds >= -129: return "-120 to -129"
    if odds >= -139: return "-130 to -139"
    if odds >= -149: return "-140 to -149"
    return "-150 or worse"

def edge_bucket(edge):
    if edge < 0.03: return "< 3%"
    elif edge < 0.05: return "3-5%"
    elif edge < 0.08: return "5-8%"
    elif edge < 0.12: return "8-12%"
    else: return "12%+"

def pick_score_bucket(ps):
    """Bucket a Pick Score onto the canonical 0–120 scale (audit M-13).

    Real scores observed in ``data/pick_log.csv`` range roughly 13 → 95.
    Under KILLSHOT v2 (Apr 21 2026), pick_score >= 90 is the qualification
    floor — sizing is no longer bucketed by score (it's driven by win_prob
    + edge). The pre-M-13 bucketing (``< 3 / 3-5 / 5-8 / 8-12 / 12+``) was
    calibrated to an older Pick Score scale and dumped every real pick
    into ``12+``, which made the breakdown useless.

    The buckets below capture sub-KILLSHOT conviction in the lower bands
    and split the KILLSHOT floor (≥90) into three high-conviction bins so
    the report tells you whether the top of the distribution is pulling
    its weight.
    """
    try:
        ps = float(ps)
    except (TypeError, ValueError):
        return "unknown"
    if ps < 40:     return "< 40"
    elif ps < 60:   return "40-60"
    elif ps < 75:   return "60-75"
    elif ps < 90:   return "75-90"
    elif ps < 95:   return "90-95 (KS floor)"
    elif ps < 100:  return "95-100"
    else:           return "100+"


def streak_analysis(picks):
    """Find current and longest win/loss streaks."""
    if not picks:
        return "No picks"

    sorted_picks = sorted(picks, key=lambda p: (p.get("date", ""), p.get("run_time", "")))
    longest_w = longest_l = temp_streak = 0
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
        if r == "W": longest_w = max(longest_w, temp_streak)
        else:        longest_l = max(longest_l, temp_streak)

    return f"Current: {temp_streak}{temp_type} | Best W streak: {longest_w} | Worst L streak: {longest_l}"


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


def calibration_section(picks):
    """Calibration analysis with sample size warnings."""
    lines = [f"\n  {'─'*60}", "  CALIBRATION (Predicted Win% vs Actual):", f"  {'─'*60}"]

    # Only props with real win_prob (skip parlays/game lines with 0)
    cal_picks = [p for p in picks if p["win_prob_num"] > 0]
    if not cal_picks:
        lines.append("    (no picks with win probability data)")
        return "\n".join(lines)

    wp_buckets = defaultdict(list)
    for p in cal_picks:
        wp = p["win_prob_num"]
        if wp < 0.55:   bucket = "50-55%"
        elif wp < 0.60: bucket = "55-60%"
        elif wp < 0.65: bucket = "60-65%"
        elif wp < 0.70: bucket = "65-70%"
        else:           bucket = "70%+"

        wp_buckets[bucket].append(p)

    for bucket in ["50-55%", "55-60%", "60-65%", "65-70%", "70%+"]:
        if bucket not in wp_buckets:
            continue
        bp = wp_buckets[bucket]
        m  = calc_metrics(bp)
        n  = m["total"]
        warn = "  ⚠ n<20" if n < MIN_SAMPLE_NOTE else ""
        avg_pred_wp = sum(p["win_prob_num"] for p in bp) / len(bp)  # true average predicted wp in bucket
        diff = m["win_rate"] - avg_pred_wp
        arrow = "↑" if diff > 0.03 else ("↓" if diff < -0.03 else "≈")
        lines.append(f"    Predicted {bucket:8s} ({n:3d} picks) → Actual: {m['win_rate']:.1%} {arrow}  |  {m['units_pl']:+.2f}u{warn}")

    total_cal = len(cal_picks)
    if total_cal < 100:
        lines.append(f"\n    ℹ  {total_cal} calibration picks — need ~100+ for reliable signal.")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Backtest analysis for pick_log.csv")
    parser.add_argument("--sport",      default=None,  help="Filter by sport (NBA, NHL, MLB, etc.)")
    parser.add_argument("--since",      default=None,  help="Only picks from this date forward (YYYY-MM-DD)")
    parser.add_argument("--stat",       default=None,  help="Filter by stat type (AST, SOG, K, etc.)")
    parser.add_argument("--shadow",     action="store_true", help="Include MLB shadow log (pick_log_mlb.csv)")
    parser.add_argument("--model-only", action="store_true", help="Exclude manual picks (run_type=manual)")
    parser.add_argument("--export",     action="store_true", help="Save report to .txt file")
    args = parser.parse_args()

    log_path = Path(PICK_LOG_PATH)
    if not log_path.exists():
        print(f"  No pick log found at {log_path}")
        return

    extra = [PICK_LOG_MANUAL_PATH]
    if args.shadow:
        extra.append(PICK_LOG_MLB_PATH)

    exclude_run_types = {"manual"} if args.model_only else None

    picks = load_picks(log_path, args.sport, args.since, args.stat,
                       extra_paths=extra, exclude_run_types=exclude_run_types)
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
    if args.sport:      filters.append(f"Sport: {args.sport}")
    if args.since:      filters.append(f"Since: {args.since}")
    if args.stat:       filters.append(f"Stat: {args.stat}")
    if args.shadow:     filters.append("Shadow: ON")
    if args.model_only: filters.append("Model only (no manual)")
    if filters:
        report.append(f"  Filters: {' | '.join(filters)}")

    date_range = f"{min(p['date'] for p in picks)} → {max(p['date'] for p in picks)}"
    report.append(f"  Date range: {date_range}")
    report.append(f"  Total graded picks: {len(picks)}")
    if len(picks) < MIN_SAMPLE_NOTE:
        report.append(f"  ⚠  Small sample — breakdowns are directional only (need {MIN_SAMPLE_NOTE}+ per group for signal)")

    # Overall
    overall = calc_metrics(picks)
    report.append(f"\n  {'='*60}")
    report.append(f"  OVERALL: {format_record(overall)}")
    report.append(f"  {'='*60}")
    report.append(f"  Streaks: {streak_analysis(picks)}")

    # Breakdowns
    report.append(breakdown(picks, lambda p: p.get("sport", "?"),      "BY SPORT",                  min_count=1))
    report.append(breakdown(picks, lambda p: p.get("stat", "?"),       "BY STAT TYPE",              min_count=2))
    report.append(breakdown(picks, lambda p: p.get("tier", "?"),       "BY TIER",                   min_count=2))
    report.append(breakdown(picks, lambda p: p.get("run_type", "?"),   "BY RUN TYPE",               min_count=2))
    report.append(breakdown(picks, lambda p: p.get("direction", "?"),  "BY DIRECTION (Over/Under)", min_count=3))
    report.append(breakdown(picks, lambda p: edge_bucket(p["edge_num"]),           "BY EDGE BUCKET",       min_count=2))
    report.append(breakdown(picks, lambda p: pick_score_bucket(p["pick_score_num"]), "BY PICK SCORE BUCKET", min_count=2))
    report.append(breakdown(picks, lambda p: odds_bucket(p["odds_num"]),           "BY ODDS RANGE",        min_count=2))
    report.append(breakdown(picks, lambda p: p.get("mode", "?"),       "BY MODE",                   min_count=1))
    report.append(breakdown(picks, lambda p: p.get("book", "?"),       "BY BOOK",                   min_count=2))

    # Card slot breakdown (primary picks only)
    primary_with_slot = [p for p in picks
                         if p.get("run_type", "") in ("primary", "", None)
                         and p.get("card_slot", "").strip()]
    if primary_with_slot:
        report.append(breakdown(primary_with_slot,
                                lambda p: f"Slot {p.get('card_slot','')}",
                                "BY CARD SLOT (primary only)", min_count=1))

    # Calibration
    report.append(calibration_section(picks))

    # Daily P&L
    report.append(daily_pl(picks))

    # Top 10 best and worst
    report.append(f"\n  {'─'*60}")
    report.append("  TOP 10 PICKS (by unit profit):")
    report.append(f"  {'─'*60}")
    winners = sorted([p for p in picks if p["result"] == "W"],
                     key=lambda p: p["size_num"] * (p["odds_num"]/100 if p["odds_num"] > 0 else 100/abs(p["odds_num"]) if p["odds_num"] < 0 else 0),
                     reverse=True)[:10]
    for p in winners:
        odds   = p["odds_num"]
        size   = p["size_num"]
        profit = size * (odds/100 if odds > 0 else 100/abs(odds)) if odds != 0 else 0
        # audit L-3: descriptor comes from the canonical formatter so a
        # new stat type (e.g. PARLAY → "Daily Lay 3-leg @ +540") doesn't
        # have to be inlined here on top of pick_labels.py and weekly_recap.
        report.append(f"    +{profit:.2f}u  {_pick_detail_line(p)}")

    report.append(f"\n  WORST 10 PICKS (biggest losses):")
    losers = sorted([p for p in picks if p["result"] == "L"],
                    key=lambda p: p["size_num"], reverse=True)[:10]
    for p in losers:
        report.append(f"    -{p['size_num']:.2f}u  {_pick_detail_line(p)}")

    full_report = "\n".join(report)
    print(full_report)

    if args.export:
        tag = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
        if args.shadow:     tag += "_shadow"
        if args.model_only: tag += "_model"
        export_path = Path(OUTPUT_FOLDER) / f"backtest_{tag}.txt"
        export_path.parent.mkdir(parents=True, exist_ok=True)
        with open(export_path, "w", encoding="utf-8") as f:
            f.write(full_report)
        print(f"\n  📊 Report saved to {export_path}")


if __name__ == "__main__":
    main()
