#!/usr/bin/env python3
"""
results_graphic.py — Auto-generate daily results card PNG for #daily-recap
Programmatic Pillow card — no templates needed.

Called automatically from grade_picks.py after the recap embed posts,
or run standalone for any date.

Usage:
    python results_graphic.py                           # Today's results
    python results_graphic.py --date 2026-04-14
    python results_graphic.py --date 2026-04-14 --test  # Save locally, don't post
    python results_graphic.py --date 2026-04-14 --out C:/path/result.png

Requires: pip install pillow --break-system-packages
"""

import argparse, csv, io, json, os, sys, time
from datetime import datetime
from pathlib import Path

try:
    import requests
except ImportError:
    print("pip install requests --break-system-packages")
    sys.exit(1)

try:
    from PIL import Image, ImageDraw, ImageFont
    _HAS_PIL = True
except ImportError:
    _HAS_PIL = False

# ── Config ────────────────────────────────────────────────────────────────────
PICK_LOG_PATH         = os.path.expanduser("~/Documents/JonnyParlay/data/pick_log.csv")
DISCORD_RECAP_WEBHOOK = "https://discord.com/api/webhooks/1493388658638848344/1RixaqCAX9kYdjrfDPt9bLKrr3Xn1LQmNvzWHAutT62k09dSsdhvOYBb18JhkS49mwU0"
OUTPUT_DIR            = os.path.expanduser("~/Documents/JonnyParlay/results_graphics")

GAME_LINE_STATS = {"TOTAL", "SPREAD", "TEAM_TOTAL", "ML_FAV", "ML_DOG",
                   "F5_TOTAL", "F5_SPREAD", "F5_ML", "NRFI", "YRFI"}

# ── Colours ───────────────────────────────────────────────────────────────────
BG          = (17,  17,  24)   # #111118
ACCENT_WIN  = (46,  204, 113)  # #2ECC71
ACCENT_LOSS = (255, 68,  68)   # #FF4444
GOLD        = (255, 215, 0)    # #FFD700
WHITE       = (255, 255, 255)
GREY_MID    = (160, 160, 160)
GREY_DIM    = (70,  70,  90)

# ── Helpers ───────────────────────────────────────────────────────────────────

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

def _pick_graphic_line(p):
    """Short pick label for the graphic card."""
    stat = p.get("stat", "")
    if stat in GAME_LINE_STATS:
        team = p.get("player", p.get("team", ""))
        dir_ = p.get("direction", "").upper()
        line = p.get("line", "")
        if stat == "SPREAD":
            # player field already contains "TEAM LINE" (e.g. "LAK -1.5") — don't append line again
            return team
        elif stat in ("ML_FAV", "ML_DOG"):
            return f"{team}  ML"
        elif stat == "TOTAL":
            return f"Total  {dir_}  {line}"
        elif stat == "TEAM_TOTAL":
            team_abbr = p.get("team", "")
            return f"{team_abbr}  Team Total  {dir_}  {line}"
        else:
            return f"{team}  {stat}  {dir_}  {line}".strip()
    else:
        last = ((p.get("player", "") or "").split() or [""])[-1].upper()
        dir_ = p.get("direction", "").upper()
        return f"{last}  {dir_} {p.get('line','')}  {stat}".strip()


# ── Font loader ───────────────────────────────────────────────────────────────

def _load_fonts():
    """Load truetype fonts from the host system, fall back to Pillow built-in."""
    bold_paths = [
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/calibrib.ttf",
        "C:/Windows/Fonts/verdanab.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    reg_paths = [
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/calibri.ttf",
        "C:/Windows/Fonts/verdana.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]

    def try_load(paths, size):
        for p in paths:
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
        # Pillow 10+ accepts size; older versions don't — handle both
        try:
            return ImageFont.load_default(size=size)
        except TypeError:
            return ImageFont.load_default()

    return {
        "title":      try_load(bold_paths, 38),
        "stats":      try_load(bold_paths, 28),
        "tier_badge": try_load(bold_paths, 20),
        "pick_text":  try_load(reg_paths,  24),
        "pick_bold":  try_load(bold_paths, 24),
        "pl_text":    try_load(bold_paths, 22),
        "footer":     try_load(reg_paths,  18),
    }


# ── Card generator ────────────────────────────────────────────────────────────

def generate_results_card(date_str, day_picks):
    """
    Generate a daily results card PNG.

    Returns BytesIO containing the PNG data.
    day_picks: list of graded pick dicts from pick_log.csv.

    Card layout (landscape, Discord-optimised):
      ┌──────────────────────────────────────────────────────┐
      │ ▌  April 14 Results                    3W · 2L       │
      │ ▌  +1.85u  ·  ROI +12.3%                            │
      │ ────────────────────────────────────────────────────  │
      │   ✅ MONTOUR  UNDER 2.5  SOG            +1.00u       │
      │   ❌ MACKINNON  OVER 3.5  SOG           -0.75u       │
      │   ✅ LAK  -1.5                           +0.46u      │
      │ ────────────────────────────────────────────────────  │
      │ @picksbyjonny                   edge > everything    │
      └──────────────────────────────────────────────────────┘
    """
    if not _HAS_PIL:
        raise ImportError("pillow not installed — pip install pillow --break-system-packages")

    fonts = _load_fonts()

    # Layout
    W        = 1200
    ACCENT_W = 8      # left accent bar
    PAD_X    = 56
    ROW_H    = 52     # height per pick row
    TOP_H    = 190    # header area
    BOTTOM_H = 64     # footer
    H        = TOP_H + ROW_H * len(day_picks) + BOTTOM_H

    img  = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    w, l, pu, pl, roi = daily_stats(day_picks)
    accent = ACCENT_WIN if pl >= 0 else ACCENT_LOSS

    # Left accent bar
    draw.rectangle([0, 0, ACCENT_W, H], fill=accent)

    # Subtle top-right glow
    draw.rectangle([W - 3, 0, W, H], fill=(accent[0]//6, accent[1]//6, accent[2]//6))

    # ── Title ──────────────────────────────────────────────────
    try:
        dt         = datetime.strptime(date_str, "%Y-%m-%d")
        title_str  = f"{dt.strftime('%B')} {dt.day} Results"
    except Exception:
        title_str  = f"{date_str} Results"

    TEXT_X = PAD_X + ACCENT_W + 16

    draw.text((TEXT_X, 32), title_str, font=fonts["title"], fill=WHITE)

    # Record — top right
    record_str = f"{w}W  ·  {l}L"
    if pu:
        record_str += f"  ·  {pu}P"
    draw.text((W - PAD_X, 35), record_str, font=fonts["stats"], fill=accent, anchor="ra")

    # ── Stats line ─────────────────────────────────────────────
    pl_str  = f"{pl:+.2f}u"
    roi_str = f"ROI {roi:+.1f}%"
    draw.text((TEXT_X, 88), f"{pl_str}   ·   {roi_str}", font=fonts["stats"], fill=accent)

    # ── Divider ────────────────────────────────────────────────
    div_y1 = 148
    draw.rectangle([PAD_X, div_y1, W - PAD_X, div_y1 + 1], fill=GREY_DIM)

    # ── Pick rows ──────────────────────────────────────────────
    for i, p in enumerate(day_picks):
        y      = TOP_H - 45 + i * ROW_H
        result = p.get("result", "")
        ppl    = compute_pl(p.get("size", 0), p.get("odds", "-110"), result)
        label  = _pick_graphic_line(p)
        emoji  = "✅" if result == "W" else ("❌" if result == "L" else "➖")

        row_color = ACCENT_WIN if result == "W" else (ACCENT_LOSS if result == "L" else GREY_MID)

        # Alternating row background
        if i % 2 == 0:
            draw.rectangle([ACCENT_W, y, W, y + ROW_H], fill=(22, 22, 32))

        mid_y = y + ROW_H // 2

        # ── Result badge (W / L / P) — drawn, no emoji chars ──
        result_label = "W" if result == "W" else ("L" if result == "L" else "P")
        rbadge_x = TEXT_X
        rbadge_w, rbadge_h = 28, 22
        draw.rounded_rectangle(
            [rbadge_x, mid_y - rbadge_h // 2, rbadge_x + rbadge_w, mid_y + rbadge_h // 2],
            radius=4, fill=row_color
        )
        draw.text(
            (rbadge_x + rbadge_w // 2, mid_y),
            result_label, font=fonts["tier_badge"], fill=BG, anchor="mm"
        )

        # ── Tier badge ─────────────────────────────────────────
        tier    = p.get("tier", "")
        tier_x  = rbadge_x + rbadge_w + 10
        if tier:
            tbadge_w = len(tier) * 9 + 14
            draw.rounded_rectangle(
                [tier_x, mid_y - 11, tier_x + tbadge_w, mid_y + 11],
                radius=4, fill=(30, 30, 45)
            )
            draw.text(
                (tier_x + tbadge_w // 2, mid_y),
                tier, font=fonts["tier_badge"], fill=GREY_MID, anchor="mm"
            )
            pick_x = tier_x + tbadge_w + 14
        else:
            pick_x = tier_x

        # ── Pick label ─────────────────────────────────────────
        draw.text((pick_x, mid_y), label, font=fonts["pick_text"], fill=WHITE, anchor="lm")

        # P/L — right-aligned
        pl_tag = f"{ppl:+.2f}u"
        draw.text((W - PAD_X, mid_y), pl_tag, font=fonts["pl_text"], fill=row_color, anchor="rm")

    # ── Bottom divider ─────────────────────────────────────────
    div_y2 = H - BOTTOM_H
    draw.rectangle([PAD_X, div_y2, W - PAD_X, div_y2 + 1], fill=GREY_DIM)

    # ── Footer ─────────────────────────────────────────────────
    draw.text((TEXT_X, H - 38), "@picksbyjonny", font=fonts["footer"], fill=GOLD)
    draw.text((W - PAD_X, H - 38), "edge > everything",
              font=fonts["footer"], fill=GREY_MID, anchor="ra")

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf


# ── Discord post ──────────────────────────────────────────────────────────────

def post_results_graphic(date_str, day_picks, webhook_url=None, suppress_ping=False):
    """Generate results card PNG and post to Discord as a file attachment.

    Called by grade_picks.py after the recap embed posts.
    suppress_ping is accepted for API compatibility but not currently used here
    (graphic posts have no @everyone — the recap embed already handles that).
    """
    if not _HAS_PIL:
        print("  ⚠ results_graphic: pillow not installed — skipping PNG. "
              "Run: pip install pillow --break-system-packages")
        return False
    if not day_picks:
        return False

    wh = webhook_url or DISCORD_RECAP_WEBHOOK
    if not wh:
        return False

    try:
        png_buf  = generate_results_card(date_str, day_picks)
        filename = f"results_{date_str}.png"
        payload  = {"username": "PicksByJonny", "content": ""}
        data     = {"payload_json": json.dumps(payload)}
        files    = {"files[0]": (filename, png_buf, "image/png")}

        for attempt in range(1, 4):
            try:
                png_buf.seek(0)
                r = requests.post(wh, data=data, files=files, timeout=20)
            except requests.exceptions.RequestException as exc:
                if attempt < 3:
                    print(f"  [Discord] ⚠ Results graphic transport error (attempt {attempt}/3): {exc} — retrying")
                    time.sleep(2 ** attempt)
                    continue
                print(f"  [Discord] ⚠ Results graphic transport error: {exc}")
                return False
            if r.status_code == 429:
                time.sleep(float(r.json().get("retry_after", 2.0)))
                continue
            if r.status_code in (200, 204):
                print(f"  [Discord] ✅ Results graphic posted for {date_str}")
                return True
            # Retry transient 5xx errors; fail fast on 4xx
            if 500 <= r.status_code < 600 and attempt < 3:
                print(f"  [Discord] ⚠ Results graphic 5xx {r.status_code} (attempt {attempt}/3) — retrying")
                time.sleep(2 ** attempt)
                continue
            print(f"  [Discord] ⚠ Results graphic failed: {r.status_code} {r.text[:200]}")
            return False

    except Exception as e:
        print(f"  [Discord] ⚠ Results graphic error: {e}")
    return False


# ── CLI ───────────────────────────────────────────────────────────────────────

def _load_day_picks(date_str):
    p = Path(PICK_LOG_PATH)
    if not p.exists():
        return []
    with open(p, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return [
        r for r in rows
        if r.get("date") == date_str
        and r.get("result") in ("W", "L", "P")
        and r.get("run_type", "primary") in ("primary", "bonus", "manual", "", None)
    ]


def main():
    parser = argparse.ArgumentParser(description="Generate and post daily results graphic")
    parser.add_argument("--date", default=None, help="Date YYYY-MM-DD (default: today)")
    parser.add_argument("--test", action="store_true",
                        help="Save PNG locally only — don't post to Discord")
    parser.add_argument("--out",  default=None, help="Custom output path for PNG")
    args = parser.parse_args()

    if not _HAS_PIL:
        print("❌ Pillow not installed. Run: pip install pillow --break-system-packages")
        sys.exit(1)

    date_str   = args.date or datetime.now().strftime("%Y-%m-%d")
    day_picks  = _load_day_picks(date_str)

    if not day_picks:
        print(f"  ❌ No graded picks for {date_str}")
        sys.exit(0)

    print(f"  Generating results card: {date_str}  ({len(day_picks)} picks)")
    png_buf = generate_results_card(date_str, day_picks)

    # Always save locally
    out_path = args.out or os.path.join(OUTPUT_DIR, f"results_{date_str}.png")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "wb") as f:
        png_buf.seek(0)
        f.write(png_buf.read())
    print(f"  ✅ Saved: {out_path}")

    if not args.test:
        png_buf.seek(0)
        post_results_graphic(date_str, day_picks)
    else:
        print("  [--test] Skipped Discord post")


if __name__ == "__main__":
    main()
