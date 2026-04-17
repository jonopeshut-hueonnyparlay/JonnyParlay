#!/usr/bin/env python3
"""
weekly_recap.py — Weekly performance recap for #announcements
Reads pick_log.csv, computes Mon–Sun stats, posts embed + xlsx attachment.
Schedule via Windows Task Scheduler: every Sunday at 9:00 PM ET.

Usage:
    python weekly_recap.py                       # This/most-recent completed week
    python weekly_recap.py --test                # Suppress @everyone
    python weekly_recap.py --week 2026-04-13     # Week containing this date
    python weekly_recap.py --repost              # Force re-post (bypass guard)

Requires: pip install openpyxl --break-system-packages  (for xlsx attachment)
"""

import argparse, calendar, csv, io, json, os, sys, time
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

try:
    import requests
except ImportError:
    print("pip install requests --break-system-packages")
    sys.exit(1)

try:
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    _HAS_OPENPYXL = True
except ImportError:
    _HAS_OPENPYXL = False

# ── Config ────────────────────────────────────────────────────────────────────
PICK_LOG_PATH            = os.path.expanduser("~/Documents/JonnyParlay/data/pick_log.csv")
DISCORD_GUARD_FILE       = os.path.expanduser("~/Documents/JonnyParlay/data/discord_posted.json")
DISCORD_ANNOUNCE_WEBHOOK = "https://discord.com/api/webhooks/1493399935515889768/GV9M__Wd2ZC037gJ_3zFhjWKGDE_srWzhzQYWIAvmUpAscgRO1p-XjgkS0zVLgK_4s_x"
BRAND_LOGO               = "https://cdn.discordapp.com/attachments/1115840612915228727/1225636209221566625/JonnyParlaylogoRedBlack.png"

GAME_LINE_STATS = {"TOTAL", "SPREAD", "TEAM_TOTAL", "ML_FAV", "ML_DOG",
                   "F5_TOTAL", "F5_SPREAD", "F5_ML", "NRFI", "YRFI"}

# Run types counted in weekly/monthly totals (matches grade_picks.py COUNTED_RUN_TYPES).
COUNTED_RUN_TYPES = {"primary", "bonus", "manual", "daily_lay", "", None}

_BOOK_DISPLAY = {
    # CO_LEGAL_BOOKS — must match keys used by run_picks.py exactly
    "espnbet":        "theScore Bet",
    "hardrockbet":    "Hard Rock Bet",
    "draftkings":     "DraftKings",
    "fanduel":        "FanDuel",
    "williamhill_us": "Caesars",
    "betmgm":         "BetMGM",
    "betrivers":      "BetRivers",
    "ballybet":       "Bally Bet",
    "betparx":        "BetParx",
    "pointsbetus":    "PointsBet",
    "bet365":         "bet365",
    "fanatics":       "Fanatics",
    "twinspires":     "TwinSpires",
    "circasports":    "Circa",
    "superbook":      "SuperBook",
    "tipico":         "Tipico",
    "wynnbet":        "WynnBET",
    "betway":         "Betway",
}

def display_book(key):
    """Map internal API book key to display name. Strips region suffix (e.g. hardrockbet_fl)."""
    k = (key or "").lower()
    if k in _BOOK_DISPLAY:
        return _BOOK_DISPLAY[k]
    # Strip common regional suffixes (_fl, _nj, _pa, etc.) and try again
    base = k.rsplit("_", 1)[0] if "_" in k else k
    if base in _BOOK_DISPLAY:
        return _BOOK_DISPLAY[base]
    return (key or "").title()

# ── Core helpers ──────────────────────────────────────────────────────────────

def compute_pl(size, odds_str, result):
    try:
        size = float(size)
        odds = int(float(str(odds_str).replace("+", "")))
    except (ValueError, TypeError):
        return 0.0
    if result == "W":
        return round(size * (100 / abs(odds)), 4) if odds < 0 else round(size * (odds / 100), 4)
    elif result == "L":
        return round(-size, 4)
    return 0.0

def daily_stats(picks):
    w      = sum(1 for p in picks if p.get("result") == "W")
    l      = sum(1 for p in picks if p.get("result") == "L")
    pu     = sum(1 for p in picks if p.get("result") == "P")
    pl     = sum(compute_pl(p.get("size", 0), p.get("odds", "-110"), p.get("result", "")) for p in picks)
    risked = sum(float(p.get("size", 0) or 0) for p in picks if p.get("result") != "P")
    roi    = (pl / risked * 100) if risked > 0 else 0.0
    return w, l, pu, round(pl, 2), round(roi, 1)

def load_picks(path=PICK_LOG_PATH):
    p = Path(path)
    if not p.exists():
        return []
    with open(p, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))

def week_range(ref=None):
    """Return (monday_str, sunday_str) for the most recently completed week.
    If today is Sunday, returns this week (Mon–today).
    """
    today = ref or datetime.now()
    days_since_sunday = (today.weekday() + 1) % 7  # 0 on Sunday
    last_sunday = today - timedelta(days=days_since_sunday)
    last_monday = last_sunday - timedelta(days=6)
    return last_monday.strftime("%Y-%m-%d"), last_sunday.strftime("%Y-%m-%d")

def week_range_containing(ref_date):
    """Return (monday_str, sunday_str) for the week that contains ref_date."""
    monday = ref_date - timedelta(days=ref_date.weekday())
    sunday = monday + timedelta(days=6)
    return monday.strftime("%Y-%m-%d"), sunday.strftime("%Y-%m-%d")

def filter_week(all_rows, mon_str, sun_str):
    return [
        r for r in all_rows
        if r.get("result") in ("W", "L", "P")
        and r.get("run_type") in COUNTED_RUN_TYPES
        and mon_str <= r.get("date", "") <= sun_str
    ]

def _fmt_week_label(mon_str, sun_str):
    """'Apr 7 – Apr 13'  (cross-platform, no leading zero)"""
    mon_dt = datetime.strptime(mon_str, "%Y-%m-%d")
    sun_dt = datetime.strptime(sun_str, "%Y-%m-%d")
    return f"{mon_dt.strftime('%b')} {mon_dt.day} – {sun_dt.strftime('%b')} {sun_dt.day}"

def _pick_short_label(p):
    stat = p.get("stat", "")
    if stat in GAME_LINE_STATS:
        team = p.get("player", p.get("team", ""))
        dir_ = p.get("direction", "").upper()
        line = p.get("line", "")
        if stat == "SPREAD":      return f"{team} {line}"
        elif stat in ("ML_FAV", "ML_DOG"): return f"{team} ML"
        elif stat == "TOTAL":     return f"Total {dir_} {line}"
        else:                     return f"{team} {stat} {dir_} {line}".strip()
    else:
        last = ((p.get("player", "") or "").split() or [""])[-1].upper()
        return f"{last} {p.get('direction','').upper()} {p.get('line','')} {stat}".strip()


# ── xlsx builder ──────────────────────────────────────────────────────────────

def build_weekly_xlsx(week_picks, mon_str, sun_str):
    """Build xlsx. Returns BytesIO or None if openpyxl not installed."""
    if not _HAS_OPENPYXL:
        return None

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Weekly Picks"

    dark_fill = PatternFill("solid", fgColor="111118")
    alt_fill  = PatternFill("solid", fgColor="16161F")
    hdr_fill  = PatternFill("solid", fgColor="1a1a28")
    hdr_font  = Font(bold=True, color="FFD700", size=11)
    row_bdr   = Border(bottom=Side(style="thin", color="333344"))
    center    = Alignment(horizontal="center", vertical="center")

    headers = ["Date", "Sport", "Pick", "Stat", "Dir", "Line", "Odds", "Book", "Tier", "Size", "Result", "P/L"]
    for col, h in enumerate(headers, 1):
        c = ws.cell(row=1, column=col, value=h)
        c.font, c.fill, c.alignment = hdr_font, hdr_fill, center
    ws.row_dimensions[1].height = 22

    for ri, p in enumerate(week_picks, 2):
        pl     = compute_pl(p.get("size", 0), p.get("odds", "-110"), p.get("result", ""))
        result = p.get("result", "")
        fill   = alt_fill if ri % 2 == 0 else dark_fill
        values = [
            p.get("date", ""), p.get("sport", ""), _pick_short_label(p),
            p.get("stat", ""), p.get("direction", "").upper(), p.get("line", ""),
            p.get("odds", ""), display_book(p.get("book", "")),
            p.get("tier", ""), float(p.get("size", 0) or 0),
            result, round(pl, 2),
        ]
        for col, val in enumerate(values, 1):
            c = ws.cell(row=ri, column=col, value=val)
            c.alignment, c.border, c.fill = center, row_bdr, fill
            if col == 11:
                c.font = Font(color=("2ECC71" if result == "W" else "FF4444" if result == "L" else "AAAAAA"), bold=True)
            if col == 12:
                c.font = Font(color="2ECC71" if pl >= 0 else "FF4444", bold=True)
        ws.row_dimensions[ri].height = 18

    # Totals
    tr = len(week_picks) + 2
    w, l, pu, pl_total, roi = daily_stats(week_picks)
    ws.cell(row=tr, column=1,  value="TOTALS").font  = Font(bold=True, color="FFD700", size=11)
    ws.cell(row=tr, column=11, value=f"{w}W-{l}L{('-' + str(pu) + 'P') if pu else ''}").font = Font(bold=True, color="FFD700")
    ws.cell(row=tr, column=12, value=round(pl_total, 2)).font = Font(bold=True, color="2ECC71" if pl_total >= 0 else "FF4444")
    ws.cell(row=tr + 1, column=12, value=f"ROI: {roi:+.1f}%").font = Font(color="FFD700", bold=True)

    for col, w_ in enumerate([12, 6, 36, 8, 5, 6, 8, 16, 10, 6, 8, 8], 1):
        ws.column_dimensions[get_column_letter(col)].width = w_
    ws.freeze_panes = "A2"

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


# ── Discord embed ─────────────────────────────────────────────────────────────

def build_weekly_embed(mon_str, sun_str, week_picks, all_rows, suppress_ping=False):
    w, l, pu, pl, roi = daily_stats(week_picks)
    pl_str  = f"+{pl:.2f}u" if pl >= 0 else f"{pl:.2f}u"
    roi_str = f"+{roi:.1f}%" if roi >= 0 else f"{roi:.1f}%"
    week_label = _fmt_week_label(mon_str, sun_str)
    now_str    = datetime.now(ZoneInfo("America/New_York")).strftime("%I:%M %p ET")

    # Daily breakdown
    grouped = defaultdict(list)
    for p in week_picks:
        grouped[p["date"]].append(p)
    day_lines = []
    for d in sorted(grouped.keys()):
        dw, dl, _, dpl, _ = daily_stats(grouped[d])
        dpl_str   = f"+{dpl:.2f}u" if dpl >= 0 else f"{dpl:.2f}u"
        emoji     = "✅" if dpl > 0 else ("❌" if dpl < 0 else "➖")
        dt        = datetime.strptime(d, "%Y-%m-%d")
        day_label = f"{dt.strftime('%a')} {dt.day}"
        day_lines.append(f"{emoji} **{day_label}:** {dw}-{dl} · {dpl_str}")

    # Tier breakdown
    tier_stats = defaultdict(lambda: [0, 0, 0.0])
    for p in week_picks:
        t = p.get("tier", "?"); res = p.get("result", "")
        ppl = compute_pl(p.get("size", 0), p.get("odds", "-110"), res)
        if res == "W":   tier_stats[t][0] += 1
        elif res == "L": tier_stats[t][1] += 1
        tier_stats[t][2] += ppl
    tier_lines = []
    for t in sorted(tier_stats.keys()):
        tw, tl, tpl = tier_stats[t]
        tier_lines.append(f"**{t}:** {tw}-{tl} · {('+' if tpl >= 0 else '')}{tpl:.1f}u")

    # Best / worst
    pick_pls = [(p, compute_pl(p.get("size",0), p.get("odds","-110"), p.get("result",""))) for p in week_picks]
    best  = max(pick_pls, key=lambda x: x[1], default=None)
    worst = min(pick_pls, key=lambda x: x[1], default=None)
    best_line  = f"\n🏆 **Best:** {_pick_short_label(best[0])} · {best[1]:+.2f}u"   if best  else ""
    worst_line = f"\n💀 **Worst:** {_pick_short_label(worst[0])} · {worst[1]:+.2f}u" if (worst and worst != best) else ""

    # Month running total
    dt = datetime.strptime(sun_str, "%Y-%m-%d")
    month_prefix = f"{dt.year}-{dt.month:02d}-"
    month_picks  = [r for r in all_rows
                    if r.get("result") in ("W","L","P")
                    and r.get("run_type") in COUNTED_RUN_TYPES
                    and r.get("date","").startswith(month_prefix)]
    mw, ml, _, mpl, _ = daily_stats(month_picks)
    mpl_str = f"+{mpl:.1f}u" if mpl >= 0 else f"{mpl:.1f}u"

    has_xlsx   = _HAS_OPENPYXL
    footer_cta = "Full breakdown attached ↓" if has_xlsx else "edge > everything"
    color      = 0xFFD700 if pl >= 0 else 0xFF4444
    content    = "" if suppress_ping else "@everyone"

    desc = "\n".join([
        f"**{w}-{l}{('-' + str(pu) + 'P') if pu else ''} · {pl_str} · ROI {roi_str}**",
        "",
        "\n".join(day_lines),
        "",
        "━━━━━━━━━━━━━━━━━━━━━━━━━",
        "\n".join(tier_lines),
        best_line + worst_line,
        "",
        f"**{calendar.month_name[dt.month]} so far:** {mw}-{ml} · {mpl_str}",
        "",
        "━━━━━━━━━━━━━━━━━━━━━━━━━",
        footer_cta,
    ]).strip()

    return {
        "username": "PicksByJonny",
        "content":  content,
        "embeds": [{
            "title":       f"📅 Weekly Recap — {week_label}",
            "description": desc,
            "color":       color,
            "thumbnail":   {"url": BRAND_LOGO},
            "footer":      {"text": f"picksbyjonny · edge > everything · {now_str}"},
        }]
    }


# ── Guard helpers ─────────────────────────────────────────────────────────────

def _load_guard():
    try:
        with open(DISCORD_GUARD_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def _save_guard(guard):
    os.makedirs(os.path.dirname(DISCORD_GUARD_FILE), exist_ok=True)
    with open(DISCORD_GUARD_FILE, "w", encoding="utf-8") as f:
        json.dump(guard, f, indent=2)


# ── Webhook post with optional file ──────────────────────────────────────────

def _webhook_post_with_file(url, payload, file_buf=None, filename="weekly.xlsx"):
    """POST to Discord webhook, optionally with an xlsx file attachment."""
    if not url:
        return False
    for attempt in range(1, 4):
        try:
            if file_buf is not None:
                file_buf.seek(0)
                data  = {"payload_json": json.dumps(payload)}
                files = {"files[0]": (
                    filename, file_buf,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )}
                r = requests.post(url, data=data, files=files, timeout=20)
            else:
                r = requests.post(url, json=payload, timeout=10)
            if r.status_code == 429:
                time.sleep(float(r.json().get("retry_after", 2.0)))
                continue
            if r.status_code in (200, 204):
                return True
            print(f"  ⚠ Discord {r.status_code}: {r.text[:200]}")
            return False
        except Exception as e:
            if attempt < 3:
                time.sleep(2 ** attempt)
            else:
                print(f"  ⚠ Discord post error: {e}")
    return False


# ── Main post function ────────────────────────────────────────────────────────

def post_weekly_recap(week_picks, mon_str, sun_str, all_rows, suppress_ping=False, force=False):
    """Build and post the weekly recap embed + xlsx to #announcements."""
    if not week_picks:
        print(f"  No graded picks for week {mon_str} – {sun_str}")
        return False

    guard     = _load_guard()
    guard_key = f"weekly:{mon_str}"

    if not force and guard.get(guard_key):
        print(f"  [Discord] ⏭️  Weekly recap already posted for {mon_str} — use --repost to override")
        return False

    payload   = build_weekly_embed(mon_str, sun_str, week_picks, all_rows, suppress_ping=suppress_ping)
    xlsx_buf  = build_weekly_xlsx(week_picks, mon_str, sun_str)
    xlsx_name = f"picks_week_{mon_str}.xlsx"

    if not _HAS_OPENPYXL:
        print("  ⚠  openpyxl not installed — no xlsx attachment. Run: pip install openpyxl --break-system-packages")

    if _webhook_post_with_file(DISCORD_ANNOUNCE_WEBHOOK, payload, xlsx_buf, xlsx_name):
        w, l, _, pl, roi = daily_stats(week_picks)
        pl_str = f"+{pl:.2f}u" if pl >= 0 else f"{pl:.2f}u"
        print(f"  [Discord] ✅ Weekly recap posted — {w}W-{l}L · {pl_str} · week of {_fmt_week_label(mon_str, sun_str)}")
        if not suppress_ping:
            guard[guard_key] = True
            _save_guard(guard)
        return True

    print("  [Discord] ❌ Weekly recap post failed")
    return False


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Post weekly recap to #announcements")
    parser.add_argument("--week",   default=None,
                        help="Any date within the target week (YYYY-MM-DD). "
                             "Defaults to most recently completed week.")
    parser.add_argument("--test",   action="store_true", help="Suppress @everyone ping")
    parser.add_argument("--repost", action="store_true", help="Force re-post (bypass guard)")
    args = parser.parse_args()

    if args.week:
        ref_date = datetime.strptime(args.week, "%Y-%m-%d")
        mon_str, sun_str = week_range_containing(ref_date)
    else:
        mon_str, sun_str = week_range()

    week_label = _fmt_week_label(mon_str, sun_str)
    print(f"\nWeekly recap: {week_label}  ({mon_str} – {sun_str})")

    all_rows = load_picks()
    if not all_rows:
        print("  ❌ pick_log.csv not found")
        sys.exit(1)

    week_picks = filter_week(all_rows, mon_str, sun_str)
    if not week_picks:
        print(f"  ❌ No graded picks for {week_label}")
        sys.exit(0)

    w, l, pu, pl, roi = daily_stats(week_picks)
    pl_str = f"+{pl:.2f}u" if pl >= 0 else f"{pl:.2f}u"
    print(f"  {w}W-{l}L · {pl_str} · ROI {roi:+.1f}%  ({len(week_picks)} picks)")

    post_weekly_recap(
        week_picks, mon_str, sun_str, all_rows,
        suppress_ping=args.test,
        force=args.repost,
    )


if __name__ == "__main__":
    main()
