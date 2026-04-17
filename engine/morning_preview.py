#!/usr/bin/env python3
"""
morning_preview.py — Post a daily picks teaser to #announcements
Reads today's picks from pick_log.csv and fires a Discord embed.
Designed to run right after run_picks.py logs the day's card.

Workflow:
    1. python run_picks.py nhl.csv          ← logs picks + posts premium card
    2. python morning_preview.py            ← announces to #announcements
   (or run_picks.py calls morning_preview automatically at the end)

Usage:
    python morning_preview.py              # Today's picks
    python morning_preview.py --test       # Suppress @everyone
    python morning_preview.py --date 2026-04-14  # Specific date
    python morning_preview.py --repost     # Force re-post (bypass guard)
"""

import argparse, csv, json, os, sys, time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

try:
    import requests
except ImportError:
    print("pip install requests --break-system-packages")
    sys.exit(1)

# ── Config ────────────────────────────────────────────────────────────────────
PICK_LOG_PATH            = os.path.expanduser("~/Documents/JonnyParlay/data/pick_log.csv")
DISCORD_GUARD_FILE       = os.path.expanduser("~/Documents/JonnyParlay/data/discord_posted.json")
DISCORD_ANNOUNCE_WEBHOOK = "https://discord.com/api/webhooks/1493399935515889768/GV9M__Wd2ZC037gJ_3zFhjWKGDE_srWzhzQYWIAvmUpAscgRO1p-XjgkS0zVLgK_4s_x"
BRAND_LOGO               = "https://cdn.discordapp.com/attachments/1115840612915228727/1225636209221566625/JonnyParlaylogoRedBlack.png"

SPORT_EMOJI = {
    "NHL": "🏒", "NBA": "🏀", "NFL": "🏈",
    "MLB": "⚾", "NCAAB": "🏀", "NCAAF": "🏈",
}

TIER_ORDER = ["KILLSHOT", "PREMIUM", "POTD", "BONUS", "T1", "T2", "T3"]

# ── Helpers ───────────────────────────────────────────────────────────────────

def load_pick_log(path=PICK_LOG_PATH):
    p = Path(path)
    if not p.exists():
        return []
    with open(p, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))

def get_today_picks(rows, date_str):
    """All picks logged today — primary tier only, graded or not.

    Blank/missing run_type is treated as primary (matches legacy rows + default).
    """
    primary_markers = {"primary", "", None}
    return [
        r for r in rows
        if r.get("date") == date_str
        and r.get("run_type") in primary_markers
    ]

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

def _webhook_post(url, payload, retries=3):
    if not url:
        return False
    for attempt in range(1, retries + 1):
        try:
            r = requests.post(url, json=payload, timeout=10)
            if r.status_code == 429:
                time.sleep(float(r.json().get("retry_after", 2.0)))
                continue
            if r.status_code in (200, 204):
                return True
            print(f"  ⚠ Discord {r.status_code}: {r.text[:200]}")
            return False
        except Exception as e:
            if attempt < retries:
                time.sleep(2 ** attempt)
            else:
                print(f"  ⚠ Discord post error: {e}")
    return False


# ── Embed builder ─────────────────────────────────────────────────────────────

def build_preview_embed(date_str, today_picks, suppress_ping=False):
    """Build the picks preview embed for #announcements."""
    if not today_picks:
        return None

    n = len(today_picks)

    # Tier breakdown
    tier_counts = defaultdict(int)
    for p in today_picks:
        tier_counts[p.get("tier", "?")] += 1

    # Sport breakdown
    sport_counts = defaultdict(int)
    for p in today_picks:
        s = p.get("sport", "")
        if s:
            sport_counts[s] += 1

    # Date formatting (cross-platform)
    try:
        dt           = datetime.strptime(date_str, "%Y-%m-%d")
        date_display = f"{dt.strftime('%B')} {dt.day}, {dt.year}"
        day_name     = dt.strftime("%A")
    except Exception:
        date_display = date_str
        day_name     = "Today"

    # Tier lines (respect display order)
    tier_lines = []
    shown = set()
    for t in TIER_ORDER:
        if t in tier_counts:
            cnt = tier_counts[t]
            tier_lines.append(f"**{t}:** {cnt} {'pick' if cnt == 1 else 'picks'}")
            shown.add(t)
    for t, cnt in sorted(tier_counts.items()):
        if t not in shown:
            tier_lines.append(f"**{t}:** {cnt} {'pick' if cnt == 1 else 'picks'}")

    # Sport lines
    sport_lines = []
    for s in sorted(sport_counts.keys()):
        emoji = SPORT_EMOJI.get(s, "🎯")
        cnt   = sport_counts[s]
        sport_lines.append(f"{emoji} **{s}** · {cnt}")

    picks_noun = "pick" if n == 1 else "picks"
    total_line = f"**{n} {picks_noun}** locked in for {day_name}'s slate"

    desc = "\n".join([
        total_line,
        "",
        "\n".join(tier_lines),
        "",
        "\n".join(sport_lines),
        "",
        "━━━━━━━━━━━━━━━━━━━━━━━━━",
        "Head to **#premium-portfolio** for the full card.",
    ]).strip()

    content = "" if suppress_ping else "@everyone"

    return {
        "username": "PicksByJonny",
        "content":  content,
        "embeds": [{
            "title":       f"🎯 Tonight's Card Is Live",
            "description": desc,
            "color":       0xFFD700,
            "thumbnail":   {"url": BRAND_LOGO},
            "footer":      {"text": f"{date_display} · edge > everything"},
        }]
    }


# ── Main post function ────────────────────────────────────────────────────────

def post_morning_preview(date_str, today_picks, suppress_ping=False, force=False):
    """Build and post the morning picks preview to #announcements.

    Called from run_picks.py at the end of a normal run, or standalone.
    """
    if not today_picks:
        print(f"  [morning_preview] No picks for {date_str} — run run_picks.py first")
        return False

    guard     = _load_guard()
    guard_key = f"preview:{date_str}"

    if not force and guard.get(guard_key):
        print(f"  [Discord] ⏭️  Morning preview already posted for {date_str} — use --repost to override")
        return False

    payload = build_preview_embed(date_str, today_picks, suppress_ping=suppress_ping)
    if not payload:
        return False

    if _webhook_post(DISCORD_ANNOUNCE_WEBHOOK, payload):
        print(f"  [Discord] ✅ Morning preview posted for {date_str} ({len(today_picks)} picks)")
        if not suppress_ping:
            guard[guard_key] = True
            _save_guard(guard)
        return True

    print(f"  [Discord] ❌ Morning preview post failed")
    return False


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Post morning picks preview to #announcements")
    parser.add_argument("--date",   default=None,
                        help="Date YYYY-MM-DD (default: today)")
    parser.add_argument("--test",   action="store_true",
                        help="Suppress @everyone ping")
    parser.add_argument("--repost", action="store_true",
                        help="Force re-post (bypass guard)")
    args = parser.parse_args()

    date_str    = args.date or datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
    rows        = load_pick_log()

    if not rows:
        print("  ❌ pick_log.csv not found")
        sys.exit(1)

    today_picks = get_today_picks(rows, date_str)

    if not today_picks:
        print(f"  ❌ No picks found for {date_str}")
        print(f"     Run run_picks.py first to log today's picks, then re-run this script.")
        sys.exit(0)

    print(f"  Found {len(today_picks)} picks for {date_str}")
    post_morning_preview(date_str, today_picks, suppress_ping=args.test, force=args.repost)


if __name__ == "__main__":
    main()
