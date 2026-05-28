#!/usr/bin/env python3
"""morning_preview.py — Daily morning pick preview for #announcements.

Posts today's picks as a Discord embed to #announcements with a
duplicate-post guard (audit M-2 TOCTOU fix).

Usage:
    python morning_preview.py                        # Preview today's picks
    python morning_preview.py --date 2026-04-20      # Preview specific date
    python morning_preview.py --test                 # Suppress @everyone ping
    python morning_preview.py --repost               # Force re-post (bypass guard)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

# Ensure engine/ directory is importable (when run from repo root or Task Scheduler).
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

# ── Shared pick_log reader (arch note #3) ─────────────────────────────────────
from pick_log_io import load_rows  # noqa: E402

# ── Shared HTTP helpers (audit M-4 + M-16) ────────────────────────────────────
from http_utils import default_headers, retry_after_secs  # noqa: E402

try:
    import requests
except ImportError:
    print("pip install requests --break-system-packages")
    sys.exit(1)

# ── Path resolution (audit M-26) ──────────────────────────────────────────────
from paths import (  # noqa: E402
    PICK_LOG_PATH as _PICK_LOG_PATH_P,
    PICK_LOG_MANUAL_PATH as _PICK_LOG_MANUAL_PATH_P,
    DISCORD_GUARD_FILE as _DISCORD_GUARD_FILE_P,
)
PICK_LOG_PATH = str(_PICK_LOG_PATH_P)
PICK_LOG_MANUAL_PATH = str(_PICK_LOG_MANUAL_PATH_P)
DISCORD_GUARD_FILE = str(_DISCORD_GUARD_FILE_P)

# ── Announce webhook loaded from env/.env (audit C-6) ─────────────────────────
from secrets_config import DISCORD_ANNOUNCE_WEBHOOK  # noqa: E402

# ── Brand constants (audit L-7) ───────────────────────────────────────────────
from brand import BRAND_TAGLINE, BRAND_HANDLE, SPORT_EMOJI  # noqa: E402

# ── Atomic JSON writer (arch note #2) ─────────────────────────────────────────
from io_utils import atomic_write_json  # noqa: E402

# ── Fallback notifier (audit H-7) ─────────────────────────────────────────────
from webhook_fallback import notify_fallback  # noqa: E402

# ── Shared cross-process Discord guard (audit M-2) ────────────────────────────
try:
    from discord_guard import (
        load_guard as _shared_load_guard,
        save_guard as _shared_save_guard,
        claim_post as _shared_claim_post,
        release_post as _shared_release_post,
        prune_guard as _shared_prune_guard,
    )
    _HAS_SHARED_GUARD = True
except ImportError:
    _HAS_SHARED_GUARD = False

# ── Config ────────────────────────────────────────────────────────────────────
BRAND_LOGO = (
    "https://cdn.discordapp.com/attachments/1115840612915228727/"
    "1225636209221566625/JonnyParlaylogoRedBlack.png"
)

# Tier display order for the morning preview card (audit M-11).
# KILLSHOT at the top (highest conviction), DAILY_LAY at the bottom
# (separate product / pricing model). T1B sits between T1 and T2 — it's
# a sub-tier of T1 but not quite KILLSHOT quality.
# Must contain ONLY real tier tokens from pick_log.csv's `tier` column.
# Run-type labels (PREMIUM, POTD, BONUS, primary, bonus, etc.) are NOT tiers.
TIER_ORDER: list[str] = [
    "KILLSHOT",
    "T1",
    "T1B",
    "T2",
    "T3",
    "DAILY_LAY",
]

_GUARD_TTL_DAYS = 90


# ── Guard helpers ─────────────────────────────────────────────────────────────

def _prune_guard(guard: dict) -> dict:
    from datetime import timedelta
    cutoff = (
        datetime.now(ZoneInfo("America/New_York")).replace(tzinfo=None)
        - timedelta(days=_GUARD_TTL_DAYS)
    )
    pruned: dict = {}
    for key, val in guard.items():
        keep = True
        for part in key.split(":"):
            if len(part) == 10 and part[4] == "-" and part[7] == "-":
                try:
                    dt = datetime.strptime(part, "%Y-%m-%d")
                    if dt < cutoff:
                        keep = False
                    break
                except ValueError:
                    continue
        if keep:
            pruned[key] = val
    return pruned


def _load_guard() -> dict:
    if _HAS_SHARED_GUARD:
        return _shared_load_guard()
    try:
        with open(DISCORD_GUARD_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_guard(guard: dict) -> None:
    if _HAS_SHARED_GUARD:
        _shared_save_guard(guard)
        return
    try:
        atomic_write_json(DISCORD_GUARD_FILE, _prune_guard(guard))
    except Exception as e:
        import logging as _lg
        _lg.getLogger("morning_preview").warning(
            "Guard save failed — guard not persisted: %s", e
        )


# ── pick_log loader (arch note #3 wrapper) ────────────────────────────────────

def load_pick_log(path: str = PICK_LOG_PATH) -> list[dict]:
    """Load all rows from pick_log. No filtering — returns every row.

    Arch note #3: delegates to pick_log_io.load_rows for the shared lock.
    """
    return load_rows([path])


def get_today_picks(rows: list[dict], date_str: str) -> list[dict]:
    """Filter rows to today's ungraded picks (result blank / pending)."""
    return [
        r for r in rows
        if r.get("date", "") == date_str
        and r.get("run_type") in {"primary", "bonus", "daily_lay", "sgp", "longshot", ""}
        and r.get("result", "").strip() == ""
    ]


# ── Webhook post ──────────────────────────────────────────────────────────────

def _webhook_post(url: str, payload: dict, retries: int = 3, backoff: float = 2.0,
                  label: str = "morning_preview") -> bool:
    """POST ``payload`` JSON to ``url`` with retry on 429 / transient 5xx.

    Uses ``default_headers`` (audit M-16 UA) and ``retry_after_secs``
    (audit M-4 safe 429 parsing). Never uses the crash-prone
    ``float(r.json().get("retry_after", …))`` pattern.
    """
    if not url:
        return False
    headers = default_headers({"Content-Type": "application/json"})
    for attempt in range(1, retries + 1):
        try:
            r = requests.post(url, json=payload, headers=headers, timeout=10)
            if r.status_code == 429:
                wait = retry_after_secs(r, default=backoff)
                time.sleep(wait)
                continue
            if r.status_code in (200, 204):
                return True
            if 500 <= r.status_code < 600 and attempt < retries:
                print(f"  [morning_preview] Discord 5xx {r.status_code} (attempt {attempt}/{retries}) — retrying")
                time.sleep(2 ** attempt)
                continue
            print(f"  [morning_preview] Discord {r.status_code}: {r.text[:200]}")
            return False
        except requests.exceptions.RequestException as e:
            if attempt < retries:
                print(f"  [morning_preview] Discord transport error (attempt {attempt}/{retries}): {e} — retrying")
                time.sleep(2 ** attempt)
            else:
                print(f"  [morning_preview] Discord post error: {e}")
    return False


# ── Embed builder ─────────────────────────────────────────────────────────────

def _tier_sort_key(tier: str) -> int:
    """Return a sort position for a tier token using TIER_ORDER."""
    t = tier.upper() if tier else ""
    try:
        return TIER_ORDER.index(t)
    except ValueError:
        return len(TIER_ORDER)  # Unknown tiers sort to the bottom


def _format_pick_line(pick: dict) -> str:
    """Render a single pick as a short human-readable line."""
    sport   = pick.get("sport", "")
    player  = pick.get("player", "")
    stat    = pick.get("stat", "")
    line    = pick.get("line", "")
    dir_    = pick.get("direction", "").upper()
    odds    = pick.get("odds", "")
    tier    = pick.get("tier", "")
    book    = pick.get("book", "")

    emoji = SPORT_EMOJI.get(sport, "")

    # Spread / ML / total stats: game-line format
    game_line_stats = {"SPREAD", "ML_FAV", "ML_DOG", "TOTAL", "TEAM_TOTAL",
                       "F5_ML", "F5_SPREAD", "F5_TOTAL", "PARLAY"}
    if stat.upper() in game_line_stats:
        pick_str = f"{player} {dir_} {line}".strip()
    else:
        # Prop: "Player STAT OVER/UNDER line"
        pick_str = f"{player} {stat} {dir_} {line}".strip()

    tier_badge = f" `{tier}`" if tier else ""
    odds_str   = f" @ `{odds}`" if odds else ""
    book_str   = f" _{book}_" if book else ""
    return f"{emoji} **{pick_str}**{tier_badge}{odds_str}{book_str}"


def build_preview_embed(date_str: str, picks: list[dict],
                        suppress_ping: bool = False) -> dict:
    """Build the Discord embed payload for the morning preview."""
    et_zone = ZoneInfo("America/New_York")
    _now = datetime.now(et_zone)
    now_str = f"{_now.strftime('%b')} {_now.day} {_now.strftime('%Y')}"

    # Sort by tier order
    sorted_picks = sorted(picks, key=lambda p: _tier_sort_key(p.get("tier", "")))

    lines = []
    for p in sorted_picks:
        lines.append(_format_pick_line(p))

    n = len(picks)
    desc_header = f"**{n} pick{'s' if n != 1 else ''} today — let's get it** 🎯\n"
    desc_body = "\n".join(lines) if lines else "_No picks yet._"

    desc = f"{desc_header}\n{desc_body}"

    content = "" if suppress_ping else "@everyone"

    return {
        "username": "PicksByJonny",
        "content": content,
        "embeds": [{
            "title":       f"📋 Morning Preview — {date_str}",
            "description": desc,
            "color":       0xFFD700,
            "thumbnail":   {"url": BRAND_LOGO},
            "footer":      {"text": f"{BRAND_HANDLE} | {BRAND_TAGLINE} | {now_str}"},
        }]
    }


# ── Main post function ────────────────────────────────────────────────────────

def post_morning_preview(date_str: str, picks: list[dict],
                         suppress_ping: bool = False,
                         force: bool = False) -> bool:
    """Build and post the morning preview embed to #announcements.

    Parameters
    ----------
    date_str:
        YYYY-MM-DD date string for the preview card.
    picks:
        Today's ungraded picks from pick_log.csv.
    suppress_ping:
        True when running in --test mode (no @everyone).
    force:
        True when running with --repost (bypass guard, re-post anyway).

    Returns
    -------
    bool
        True on successful webhook post; False on guard-blocked or failure.

    Guard contract (audit M-2 TOCTOU fix)
    ======================================
    * Normal post: claim_post BEFORE firing the webhook. A second concurrent
      process will see the claim and bail immediately — no duplicate posts.
    * Webhook failure: release_post so the next run can re-claim and retry.
    * Webhook success: keep the claim so a second run is blocked.
    * --test (suppress_ping): skip claim entirely — test runs must not lock
      out the real post. BUT still check for an existing real claim — if a
      real run already posted, --test must not re-fire the webhook.
    * --repost (force): bypass the claim check entirely and post regardless.
    """
    if not picks:
        return False

    guard_key = f"preview:{date_str}"

    if suppress_ping:
        # --test mode: no claim, but respect an already-set real claim.
        # Determine if a real claim already exists regardless of guard backend.
        if _HAS_SHARED_GUARD:
            from discord_guard import is_posted as _is_posted
            _already = _is_posted(guard_key)
        else:
            _already = bool(_load_guard().get(guard_key))
        if _already:
            print(f"  [SKIP] Morning preview already posted for {date_str}")
            return False
        # Fire without claiming.
        payload = build_preview_embed(date_str, picks, suppress_ping=True)
        return _webhook_post(DISCORD_ANNOUNCE_WEBHOOK, payload)

    if not force:
        # Normal run: atomic claim-and-post (M-2 TOCTOU fix).
        if _HAS_SHARED_GUARD:
            claimed = _shared_claim_post(guard_key)
            if not claimed:
                print(f"  [SKIP] Morning preview already posted for {date_str}")
                return False
        else:
            guard = _load_guard()
            if guard.get(guard_key):
                print(f"  [SKIP] Morning preview already posted for {date_str}")
                return False
            guard[guard_key] = True
            _save_guard(guard)

        payload = build_preview_embed(date_str, picks, suppress_ping=False)
        ok = _webhook_post(DISCORD_ANNOUNCE_WEBHOOK, payload)
        if ok:
            if not _HAS_SHARED_GUARD:
                pass  # guard already saved above in fallback path
            return True
        # Webhook failed — release so a retry can re-claim.
        if _HAS_SHARED_GUARD:
            _shared_release_post(guard_key)
        else:
            g = _load_guard()
            g.pop(guard_key, None)
            _save_guard(g)
        print(f"  [morning_preview] Discord post failed for {date_str}")
        return False

    # --repost (force=True): fire regardless of guard state.
    if _HAS_SHARED_GUARD:
        _shared_claim_post(guard_key)  # may already be claimed — that's OK
    payload = build_preview_embed(date_str, picks, suppress_ping=False)
    ok = _webhook_post(DISCORD_ANNOUNCE_WEBHOOK, payload)
    if ok:
        if _HAS_SHARED_GUARD:
            _shared_claim_post(guard_key)  # idempotent re-persist
        else:
            g = _load_guard()
            g[guard_key] = True
            _save_guard(g)
    return ok


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Post morning preview to #announcements")
    parser.add_argument(
        "--date", default=None,
        help="Date to preview (YYYY-MM-DD). Defaults to today (ET).",
    )
    parser.add_argument(
        "--test", action="store_true",
        help="Suppress @everyone ping (test mode — does not claim the guard).",
    )
    parser.add_argument(
        "--repost", action="store_true",
        help="Force re-post even if already posted today.",
    )
    args = parser.parse_args()

    et_zone = ZoneInfo("America/New_York")
    if args.date:
        date_str = args.date
    else:
        date_str = datetime.now(et_zone).strftime("%Y-%m-%d")

    print(f"\nMorning Preview: {date_str}")

    rows = load_pick_log()
    if not rows:
        print("  pick_log.csv not found or empty — nothing to preview")
        sys.exit(1)

    picks = get_today_picks(rows, date_str)
    if not picks:
        print(f"  No ungraded picks found for {date_str}")
        sys.exit(0)

    print(f"  {len(picks)} pick(s) for {date_str}")

    posted = post_morning_preview(
        date_str, picks,
        suppress_ping=args.test,
        force=args.repost,
    )

    # AUDIT H-7: exit non-zero on failure so Task Scheduler surfaces the outage.
    if not posted:
        print("  [morning_preview] H-7: post failed — exiting 2 so the scheduler flags it.")
        try:
            notify_fallback("morning_preview", err=f"date={date_str}")
        except Exception as _e:  # noqa: BLE001
            print(f"  [morning_preview] fallback notifier raised (suppressed): {_e}")
        sys.exit(2)


if __name__ == "__main__":
    main()
