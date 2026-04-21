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
from zoneinfo import ZoneInfo

# Canonical locked-reader helper — every pick_log reader must take the same
# FileLock as the writers (audit H-8 / M-series).
sys.path.insert(0, str(Path(__file__).resolve().parent))
from pick_log_io import load_rows  # noqa: E402

# Shared HTTP helpers (audit M-4 + M-16). Canonical User-Agent on every
# outbound request + robust Retry-After parsing for 429 responses.
from http_utils import default_headers, retry_after_secs  # noqa: E402

# Centralized brand tagline (audit L-7).
from brand import BRAND_TAGLINE  # noqa: E402

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
PICK_LOG_MANUAL_PATH  = os.path.expanduser("~/Documents/JonnyParlay/data/pick_log_manual.csv")

# Recap webhook loaded from env/.env — see secrets_config.py (audit C-6).
from secrets_config import DISCORD_RECAP_WEBHOOK

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

# Refunded terminal results — stake comes back to the bettor and the bet is
# excluded from the ROI denominator. Mirrors weekly_recap._REFUNDED_RESULTS
# (audit H-5) and grade_picks.TERMINAL_RESULTS (audit M-23). Before M-23 this
# card excluded only "P"; a single VOID pick in a day would inflate `risked`
# and understate the day's ROI on the graphic posted to Discord.
_REFUNDED_RESULTS = frozenset({"P", "VOID"})


def daily_stats(picks):
    w      = sum(1 for p in picks if p.get("result") == "W")
    l      = sum(1 for p in picks if p.get("result") == "L")
    pu     = sum(1 for p in picks if p.get("result") == "P")
    pl     = sum(compute_pl(p.get("size", 0), p.get("odds", "-110"), p.get("result", "")) for p in picks)
    # audit M-23: exclude VOID from risked too, matching weekly_recap (H-5).
    risked = sum(
        float(p.get("size", 0) or 0)
        for p in picks
        if str(p.get("result", "")).strip().upper() not in _REFUNDED_RESULTS
    )
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
#
# Audit M-7 (closed Apr 20 2026).
#
# Historical behavior: hardcoded C:/Windows/Fonts paths only — silently fell
# back to Pillow's tiny bitmap default when fonts were missing, with no way
# to tell from the rendered PNG that fallback had happened. Fresh Windows
# installs or containerized runs would post unreadable cards to Discord.
#
# New behavior — the font search chain is, in order:
#   1. JONNYPARLAY_FONTS env var (os.pathsep-separated files OR directories)
#   2. Repo-local ``fonts/`` directory next to this script (so a brand font
#      can be dropped in without code changes)
#   3. Hardcoded OS fallbacks (Windows / macOS / Linux common paths)
#   4. Pillow bitmap default — LOUD warning emitted once per process
#
# ``get_font_report()`` exposes which path was chosen for each requested
# size, so ``grade_picks.py`` / a smoke test / the CLI can surface fallback
# state instead of silently shipping ugly PNGs to Discord.

_SYSTEM_BOLD_FALLBACKS = (
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/calibrib.ttf",
    "C:/Windows/Fonts/verdanab.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
)
_SYSTEM_REG_FALLBACKS = (
    "C:/Windows/Fonts/arial.ttf",
    "C:/Windows/Fonts/calibri.ttf",
    "C:/Windows/Fonts/verdana.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
)

# Populated by _load_fonts on first call; consumed by get_font_report().
_FONT_REPORT: dict[str, dict] = {}
_FALLBACK_WARNED = False


class FontsUnavailableError(RuntimeError):
    """Raised by _load_fonts when strict mode is on and no truetype font
    resolved for at least one font slot (audit M-5).

    Strict mode is opt-in via ``JONNYPARLAY_FONTS_STRICT=1``. Default
    behavior (warn-and-ship) is preserved for back-compat so a missing
    font on Jono's Windows box never blocks a recap while the incident
    is investigated.
    """


def _strict_fonts_enabled() -> bool:
    """Return True iff JONNYPARLAY_FONTS_STRICT is set to a truthy value.

    Truthy = {"1", "true", "yes", "on"} (case-insensitive). Anything else
    (unset, empty, "0", "false") → strict mode off = legacy behavior.
    """
    raw = (os.environ.get("JONNYPARLAY_FONTS_STRICT") or "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _expand_env_paths(env_value: str | None) -> list[str]:
    """Turn JONNYPARLAY_FONTS into a concrete ordered path list.

    Each entry in the env var can be either a file path (used directly) or
    a directory (all .ttf/.otf/.ttc within it, sorted). Entries are split
    on os.pathsep — colon on POSIX, semicolon on Windows.
    """
    if not env_value:
        return []
    out: list[str] = []
    for raw in env_value.split(os.pathsep):
        p = raw.strip()
        if not p:
            continue
        pth = Path(p)
        if pth.is_dir():
            for f in sorted(pth.iterdir()):
                if f.suffix.lower() in {".ttf", ".otf", ".ttc"}:
                    out.append(str(f))
        else:
            out.append(str(pth))
    return out


def _repo_font_dir_paths() -> list[str]:
    """Scan ``<repo>/fonts/`` for bundled brand fonts."""
    fdir = Path(__file__).resolve().parent.parent / "fonts"
    if not fdir.is_dir():
        return []
    return [
        str(f) for f in sorted(fdir.iterdir())
        if f.suffix.lower() in {".ttf", ".otf", ".ttc"}
    ]


def _build_search_chain(family: str) -> list[str]:
    """Return the ordered path list to try when loading ``family``.

    family ∈ {"bold", "regular"}. Env + fonts/ paths are tried for BOTH
    families (small cost, big flexibility — the user can drop one file
    and have it used everywhere).
    """
    env_paths = _expand_env_paths(os.environ.get("JONNYPARLAY_FONTS"))
    repo_paths = _repo_font_dir_paths()
    fallback = _SYSTEM_BOLD_FALLBACKS if family == "bold" else _SYSTEM_REG_FALLBACKS
    return [*env_paths, *repo_paths, *fallback]


def _try_load_one(paths: list[str], size: int):
    """Try each path, return (font, chosen_path_or_None)."""
    for p in paths:
        try:
            return ImageFont.truetype(p, size), p
        except Exception:
            continue
    # Pillow 10+ accepts size; older versions don't.
    try:
        return ImageFont.load_default(size=size), None
    except TypeError:
        return ImageFont.load_default(), None


def _load_fonts():
    """Load all fonts required by the results card; record where they came from."""
    global _FALLBACK_WARNED
    bold_chain = _build_search_chain("bold")
    reg_chain  = _build_search_chain("regular")

    specs = [
        ("title",      "bold", 38),
        ("stats",      "bold", 28),
        ("tier_badge", "bold", 20),
        ("pick_text",  "regular", 24),
        ("pick_bold",  "bold", 24),
        ("pl_text",    "bold", 22),
        ("footer",     "regular", 18),
    ]
    out = {}
    report: dict[str, dict] = {}
    any_fallback = False
    for name, family, size in specs:
        chain = bold_chain if family == "bold" else reg_chain
        font, chosen = _try_load_one(chain, size)
        out[name] = font
        report[name] = {"family": family, "size": size, "path": chosen}
        if chosen is None:
            any_fallback = True

    _FONT_REPORT.clear()
    _FONT_REPORT.update(report)

    # Audit M-5: strict mode refuses to ship an illegible bitmap-font card.
    # When ``JONNYPARLAY_FONTS_STRICT=1`` is set, any slot that fell back to
    # the Pillow bitmap default raises — callers (generate_results_card,
    # grade_picks posting path, CLI) treat the raise as "don't post this
    # card" rather than silently emitting something embarrassing.
    #
    # The previous behavior (warn-and-ship) is preserved for installs
    # without the env var, so an ops flip doesn't need to be coordinated
    # with a Windows font install in the same PR.
    if any_fallback and _strict_fonts_enabled():
        missing = [n for n, meta in report.items() if meta.get("path") is None]
        raise FontsUnavailableError(
            "JONNYPARLAY_FONTS_STRICT=1 but no truetype font resolved for "
            f"slot(s): {missing}. Refusing to render an illegible bitmap-"
            "font card. Install a system font, or set JONNYPARLAY_FONTS to "
            "a valid .ttf path, or drop a brand font into fonts/ next to "
            "results_graphic.py."
        )

    # One-time process-level warning when falling through to bitmap default.
    # Silent degradation was the original audit finding.
    if any_fallback and not _FALLBACK_WARNED:
        _FALLBACK_WARNED = True
        print(
            "[results_graphic] ⚠ No truetype font found on this system — "
            "rendering with Pillow's bitmap default (cards will look bad). "
            "Fix: set JONNYPARLAY_FONTS to a .ttf path, or drop a brand font "
            "into the repo-root fonts/ directory. (Set JONNYPARLAY_FONTS_STRICT=1 "
            "to raise instead of warn — audit M-5.)",
            file=sys.stderr, flush=True,
        )

    return out


def get_font_report() -> dict:
    """Diagnostic: return {slot: {family, size, path}} for the last _load_fonts call.

    ``path`` is None for any slot that fell back to Pillow's bitmap default.
    Callers (grade_picks, CLI, tests) can use this to check that truetype
    resolution actually succeeded before posting to Discord.
    """
    return {k: dict(v) for k, v in _FONT_REPORT.items()}


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
    draw.text((W - PAD_X, H - 38), BRAND_TAGLINE,
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

        # Audit M-4 + M-16 (closed Apr 20 2026): default_headers() stamps
        # the canonical JonnyParlay UA; retry_after_secs() prefers the
        # Retry-After header, falls back to Discord's JSON body, and
        # clamps to [0.5s, 30s] so a rogue Retry-After can't stall posting.
        headers = default_headers()
        for attempt in range(1, 4):
            try:
                png_buf.seek(0)
                r = requests.post(wh, data=data, files=files,
                                  headers=headers, timeout=20)
            except requests.exceptions.RequestException as exc:
                if attempt < 3:
                    print(f"  [Discord] ⚠ Results graphic transport error (attempt {attempt}/3): {exc} — retrying")
                    time.sleep(2 ** attempt)
                    continue
                print(f"  [Discord] ⚠ Results graphic transport error: {exc}")
                return False
            if r.status_code == 429:
                time.sleep(retry_after_secs(r, default=2.0))
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

# Shadow sports never appear on the public results graphic (CLAUDE.md contract).
# Keep this mirrored with run_picks.SHADOW_SPORTS.
SHADOW_SPORTS = frozenset({"MLB"})

# Run types allowed on the PUBLIC graphic. "manual" is excluded (audit H-6 —
# CLAUDE.md says manual picks never appear in Discord output; the graphic
# posts to DISCORD_RECAP_WEBHOOK so including manual rows = public leak).
_PUBLIC_RUN_TYPES = frozenset({"primary", "bonus", "daily_lay", "", None})


def _load_day_picks(date_str):
    """Load graded picks for `date_str` for the PUBLIC results graphic.

    Only reads the main pick_log.csv — manual picks never go on Discord
    (audit H-6). Shadow sports (MLB) are also filtered out (audit H-14) so
    if a shadow row somehow leaks into the main log, it still doesn't end
    up on the public card.

    Arch note #3: filtering routes through ``pick_log_io.load_rows``.  The
    run_types set retains ``""`` so legacy rows with blank run_type still
    pass (canonical migration normalises ``None`` → ``""`` on read).
    """
    return load_rows(
        [PICK_LOG_PATH],
        date_equals=date_str,
        run_types=_PUBLIC_RUN_TYPES,
        exclude_sports=SHADOW_SPORTS,
        graded_only=True,
    )


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

    date_str   = args.date or datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
    day_picks  = _load_day_picks(date_str)

    if not day_picks:
        print(f"  ❌ No graded picks for {date_str}")
        sys.exit(0)

    print(f"  Generating results card: {date_str}  ({len(day_picks)} picks)")
    try:
        png_buf = generate_results_card(date_str, day_picks)
    except FontsUnavailableError as e:
        # Audit M-5: strict mode refused to render. Exit non-zero so the
        # scheduler / caller treats this as a failure, not "no picks".
        print(f"  ❌ results_graphic aborted — {e}", file=sys.stderr, flush=True)
        sys.exit(3)

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
