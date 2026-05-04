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

import argparse, csv, json, os, sys, time, tempfile
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

# Canonical locked-reader helper — every pick_log reader must take the same
# FileLock as the writers (audit H-8 / M-series).
sys.path.insert(0, str(Path(__file__).resolve().parent))
from pick_log_io import load_rows  # noqa: E402

# Shared HTTP helpers (audit M-4 + M-16). Canonical User-Agent on every
# outbound request + robust Retry-After parsing for 429 responses.
from http_utils import default_headers, retry_after_secs  # noqa: E402

try:
    import requests
except ImportError:
    print("pip install requests --break-system-packages")
    sys.exit(1)

# M9: resolved via paths.py — honours $JONNYPARLAY_ROOT
from paths import (  # noqa: E402
    PICK_LOG_PATH as _PICK_LOG_PATH_P,
    DISCORD_GUARD_FILE as _DISCORD_GUARD_FILE_P,
)

# ── Config ────────────────────────────────────────────────────────────────────
PICK_LOG_PATH            = str(_PICK_LOG_PATH_P)
DISCORD_GUARD_FILE       = str(_DISCORD_GUARD_FILE_P)

# Announce webhook loaded from env/.env — see secrets_config.py (audit C-6).
from secrets_config import DISCORD_ANNOUNCE_WEBHOOK

# Centralized brand constants (audit L-7 + L-1) — tagline and sport-emoji
# mapping now live in brand.py so a rename/add is a single-file edit.
from brand import BRAND_TAGLINE, SPORT_EMOJI as _BRAND_SPORT_EMOJI  # noqa: E402

# Shared atomic-JSON writer (architectural note #2) — replaces the inline
# tmp+fsync+replace fallback in _save_guard.
from io_utils import atomic_write_json  # noqa: E402

BRAND_LOGO               = "https://cdn.discordapp.com/attachments/1115840612915228727/1225636209221566625/JonnyParlaylogoRedBlack.png"

# L-1: delegate to the canonical brand.SPORT_EMOJI map. Kept as a local
# name so existing call sites (`SPORT_EMOJI.get(s, "🎯")`) don't need to
# change — the map itself is imported from brand.py.
SPORT_EMOJI = _BRAND_SPORT_EMOJI

# Display order for tier breakdown in the #announcements preview
# (audit M-11, closed Apr 20 2026).
#
# These are tier TOKENS that actually appear in pick_log.csv — KILLSHOT,
# T1, T1B, T2, T3, DAILY_LAY — not run-type labels. The previous list
# ["KILLSHOT", "PREMIUM", "POTD", "BONUS", "T1", "T2", "T3"] mixed two
# axes (tier vs. run_type), omitted T1B and DAILY_LAY, and relied on an
# alphabetical fallback that placed T1B after T3 in the output. Keep this
# list in sync with run_picks.py tier emission + CLAUDE.md schema.
TIER_ORDER = ["KILLSHOT", "T1", "T1B", "T2", "T3", "DAILY_LAY"]

# ── Helpers ───────────────────────────────────────────────────────────────────

def load_pick_log(path=PICK_LOG_PATH):
    # Shared FileLock so a morning-preview run can't race with a still-open
    # log_picks() writer or CLV daemon (audit H-8).  Delegated to
    # pick_log_io.load_rows per arch note #3 — consistent open+lock path.
    return load_rows([path])

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

_GUARD_TTL_DAYS = 90


try:
    from discord_guard import (
        load_guard as _shared_load_guard,
        save_guard as _shared_save_guard,
        prune_guard as _shared_prune_guard,
        claim_post as _shared_claim_post,
        release_post as _shared_release_post,
        is_posted as _shared_is_posted,
    )
    _HAS_SHARED_GUARD = True
except ImportError:
    _HAS_SHARED_GUARD = False


def _prune_guard(guard):
    cutoff = datetime.now(ZoneInfo("America/New_York")).replace(tzinfo=None) - timedelta(days=_GUARD_TTL_DAYS)
    pruned = {}
    for key, val in guard.items():
        keep = True
        for p in key.split(":"):
            if len(p) == 10 and p[4] == "-" and p[7] == "-":
                try:
                    dt = datetime.strptime(p, "%Y-%m-%d")
                    if dt < cutoff:
                        keep = False
                    break
                except ValueError:
                    continue
        if keep:
            pruned[key] = val
    return pruned


def _load_guard():
    # Delegate to shared cross-process-safe helper if available
    if _HAS_SHARED_GUARD:
        return _shared_load_guard()
    try:
        with open(DISCORD_GUARD_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def _save_guard(guard):
    # Delegate to shared cross-process-safe helper if available
    if _HAS_SHARED_GUARD:
        _shared_save_guard(guard)
        return
    try:
        atomic_write_json(DISCORD_GUARD_FILE, _prune_guard(guard))
    except Exception as e:
        # H24: do NOT fall back to a direct open() write — a crash mid-write
        # would corrupt the guard file. Log and accept un-persisted state.
        import logging as _lg
        _lg.getLogger("morning_preview").warning(
            "Guard save failed — guard not persisted: %s", e
        )

def _webhook_post(url, payload, retries=3):
    """POST JSON payload to a Discord webhook.
    Retries on 429 (rate limit) and transient 5xx errors; fails fast on 4xx.

    Audit M-4 / M-16: retry_after parsed via http_utils.retry_after_secs
    (header-first, tolerates empty / non-JSON bodies), and the request
    carries the canonical JonnyParlay User-Agent.
    """
    if not url:
        return False
    headers = default_headers()
    for attempt in range(1, retries + 1):
        try:
            r = requests.post(url, json=payload, headers=headers, timeout=10)
            if r.status_code == 429:
                time.sleep(retry_after_secs(r, default=2.0))
                continue
            if r.status_code in (200, 204):
                return True
            # Retry transient 5xx; fail fast on 4xx
            if 500 <= r.status_code < 600 and attempt < retries:
                print(f"  ⚠ Discord 5xx {r.status_code} (attempt {attempt}/{retries}) — retrying")
                time.sleep(2 ** attempt)
                continue
            print(f"  ⚠ Discord {r.status_code}: {r.text[:200]}")
            return False
        except requests.exceptions.RequestException as e:
            if attempt < retries:
                print(f"  ⚠ Discord transport error (attempt {attempt}/{retries}): {e} — retrying")
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

    # Sport breakdown
    sport_counts = defaultdict(int)
    for p in today_picks:
        s = p.get("sport", "")
        if s:
            sport_counts[s] += 1

    # KILLSHOT callout
    ks_count = sum(1 for p in today_picks if p.get("tier") == "KILLSHOT")

    # Date formatting (cross-platform)
    try:
        dt           = datetime.strptime(date_str, "%Y-%m-%d")
        date_display = f"{dt.strftime('%B')} {dt.day}, {dt.year}"
        day_name     = dt.strftime("%A")
    except Exception:
        date_display = date_str
        day_name     = "Today"

    # Sport lines
    sport_lines = []
    for s in sorted(sport_counts.keys()):
        emoji = SPORT_EMOJI.get(s, "🎯")
        cnt   = sport_counts[s]
        sport_lines.append(f"{emoji} **{s}** | {cnt}")

    picks_noun = "pick" if n == 1 else "picks"
    total_line = f"**{n} {picks_noun}** locked in for {day_name}'s slate"

    body_lines = [total_line, ""]
    if ks_count:
        ks_noun = "pick" if ks_count == 1 else "picks"
        body_lines.append(f"⚡ **KILLSHOT** · {ks_count} {ks_noun} — check #killshot")
        body_lines.append("")
    body_lines += sport_lines
    body_lines += ["", "━━━━━━━━━━━━━━━━", "Head to **#premium-portfolio** for the full card."]

    desc = "\n".join(body_lines).strip()

    content = "" if suppress_ping else "@everyone"

    return {
        "username": "PicksByJonny",
        "content":  content,
        "embeds": [{
            "title":       f"🎯 Today's Card Is Live",
            "description": desc,
            "color":       0xFFD700,
            "thumbnail":   {"url": BRAND_LOGO},
            "footer":      {"text": f"{date_display} · {BRAND_TAGLINE}"},
        }]
    }


# ── Main post function ────────────────────────────────────────────────────────

def post_morning_preview(date_str, today_picks, suppress_ping=False, force=False):
    """Build and post the morning picks preview to #announcements.

    Called from run_picks.py at the end of a normal run, or standalone.

    Duplicate-post protection (audit M-2, closed Apr 20 2026):
      Two concurrent runs (Task Scheduler retry + manual, two manual kicks,
      etc.) used to both pass the load / check / post / save sequence — a
      classic TOCTOU race that fired @everyone twice. We now atomically
      claim the guard key BEFORE posting the webhook. If the claim fails
      (another process already claimed it), bail. If the claim succeeds
      and the webhook then fails, release the claim so a retry can re-claim.

      force=True bypasses the claim (used by --repost to re-fire after an
      issue). suppress_ping=True (--test) also bypasses the claim so you
      can re-test without clobbering the real-run claim.
    """
    if not today_picks:
        print(f"  [morning_preview] No picks for {date_str} — run run_picks.py first")
        return False

    guard_key = f"preview:{date_str}"

    # --- Test / force paths ---
    if force or suppress_ping:
        # Still honor "already posted" as a soft check — unless force=True,
        # we don't want --test to spam after a real post already fired.
        if suppress_ping and not force:
            already_posted = (
                _shared_is_posted(guard_key) if _HAS_SHARED_GUARD
                else bool(_load_guard().get(guard_key))
            )
            if already_posted:
                # Audit L-2 (closed Apr 20 2026): the previous skip marker
                # was a multi-codepoint emoji (U+23ED + U+FE0F) that cp1252
                # Windows consoles choke on, crashing the whole post path.
                # ASCII [SKIP] renders everywhere.
                print(f"  [Discord] [SKIP] Morning preview already posted for {date_str} — --test skipped")
                return False

        # H24: for --repost (force=True), claim the guard key BEFORE posting
        # so concurrent --repost invocations are serialized. Release any
        # stale claim first, then atomically re-claim.
        if force and not suppress_ping:
            if _HAS_SHARED_GUARD:
                _shared_release_post(guard_key)
                if not _shared_claim_post(guard_key):
                    print(f"  [Discord] [SKIP] --repost already in progress for {date_str}")
                    return False
            else:
                g = _load_guard()
                g[guard_key] = True
                _save_guard(g)  # pre-claim before post

        payload = build_preview_embed(date_str, today_picks, suppress_ping=suppress_ping)
        if not payload:
            if force and not suppress_ping and _HAS_SHARED_GUARD:
                _shared_release_post(guard_key)
            return False
        if _webhook_post(DISCORD_ANNOUNCE_WEBHOOK, payload):
            print(f"  [Discord] ✅ Morning preview posted for {date_str} ({len(today_picks)} picks)")
            return True
        # Webhook failed — release claim so a subsequent --repost can re-claim
        if force and not suppress_ping:
            if _HAS_SHARED_GUARD:
                _shared_release_post(guard_key)
            else:
                g = _load_guard()
                g.pop(guard_key, None)
                _save_guard(g)
        print(f"  [Discord] ❌ Morning preview post failed")
        return False

    # --- Default path: atomic claim ---
    if _HAS_SHARED_GUARD:
        if not _shared_claim_post(guard_key):
            # L-2: ASCII [SKIP] so cp1252 consoles don't crash.
            print(f"  [Discord] [SKIP] Morning preview already posted for {date_str} — use --repost to override")
            return False
    else:
        # Legacy fallback — still has a TOCTOU window, but at least keeps
        # the module functional when discord_guard isn't importable.
        guard = _load_guard()
        if guard.get(guard_key):
            # L-2: ASCII [SKIP] so cp1252 consoles don't crash.
            print(f"  [Discord] [SKIP] Morning preview already posted for {date_str} — use --repost to override")
            return False
        guard[guard_key] = True
        _save_guard(guard)

    payload = build_preview_embed(date_str, today_picks, suppress_ping=suppress_ping)
    if not payload:
        # Release the claim so a retry can build the payload again
        if _HAS_SHARED_GUARD:
            _shared_release_post(guard_key)
        return False

    if _webhook_post(DISCORD_ANNOUNCE_WEBHOOK, payload):
        print(f"  [Discord] ✅ Morning preview posted for {date_str} ({len(today_picks)} picks)")
        return True

    # Webhook failed — release the claim so a subsequent run can re-claim
    # and retry. DO NOT release on success, or a second run would duplicate.
    print(f"  [Discord] ❌ Morning preview post failed — releasing claim for retry")
    if _HAS_SHARED_GUARD:
        _shared_release_post(guard_key)
    else:
        g = _load_guard()
        g.pop(guard_key, None)
        _save_guard(g)
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
    posted = post_morning_preview(date_str, today_picks, suppress_ping=args.test, force=args.repost)
    # AUDIT H-7: exit non-zero on Discord post failure so Task Scheduler flags
    # the run as failed. Without this, a 4xx/Cloudflare/network outage looks
    # identical to a successful run in Task Scheduler history.
    if not posted:
        print("  [morning-preview] ❌ H-7: post failed — exiting 2 so the scheduler flags it.")
        # Fire the secondary fallback webhook alert (audit H-7, closed Apr 20
        # 2026). No-op if DISCORD_FALLBACK_WEBHOOK isn't configured, and
        # swallows its own failures — it must not mask the real exit code.
        try:
            from webhook_fallback import notify_fallback
            notify_fallback("morning_preview", err=f"date={date_str}")
        except Exception as _e:  # noqa: BLE001
            print(f"  [morning-preview] fallback notifier raised (suppressed): {_e}")
        sys.exit(2)


if __name__ == "__main__":
    main()
