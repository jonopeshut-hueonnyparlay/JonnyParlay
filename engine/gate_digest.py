#!/usr/bin/env python3
"""gate_digest.py — Weekly gate-counter digest for ops visibility (P2.11).

Turns the per-row blocked-pick ledger (which nobody reads) into a weekly
operator-facing summary, and surfaces progress toward the open data-gates.

Two sections:
  1. Gate fires this week — tallies ``gate_result`` from pick_log_blocked.csv
     over the Mon–Sun window, by gate code (with per-sport split). Suspension
     gates (SOG/HA/RA) and shadow-routed gates (G8B/G8C/...) are intentionally
     absent from that log, so counts read as STRUCTURAL blocks.
  2. Open data-gate progress — a snapshot reusing gate_check.compute_gate_status()
     (Calibration Platt, MLB Platt, SGP, Combo, EdgeModel CLV, H3). Snapshot,
     NOT weekly-windowed.

Posts to DISCORD_GATES_WEBHOOK. Blank by default → prints to console and never
POSTs (same opt-in pattern as DISCORD_GAME_LINES_WEBHOOK). Ops-facing: no
@everyone ping.

Schedule via Windows Task Scheduler: Sunday, after weekly_recap.py.

Usage:
    python gate_digest.py                       # most-recent completed week
    python gate_digest.py --week 2026-06-15     # week containing this date
    python gate_digest.py --dry-run             # console only, never POST
    python gate_digest.py --repost              # bypass the post-once guard
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

# Resolve sibling engine modules whether run from project root or engine/.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from paths import PICK_LOG_BLOCKED_PATH  # noqa: E402

# Reuse the canonical week-window math (single source of truth, audit DRY).
from weekly_recap import (  # noqa: E402
    week_range,
    week_range_containing,
    _fmt_week_label,
)

# Reuse the shared data-gate status computation (one code path with the CLI).
from gate_check import compute_gate_status  # noqa: E402

# Ops webhook. Prefer the secrets_config constant once it's registered there;
# fall back to the env var directly so this module works before that one-line
# addition lands (secrets_config.py is write-protected). Importing secrets_config
# also loads .env into os.environ, so the getenv fallback still sees .env values.
try:
    from secrets_config import DISCORD_GATES_WEBHOOK  # noqa: E402
except ImportError:
    import secrets_config  # noqa: F401,E402  (ensures .env is loaded)
    DISCORD_GATES_WEBHOOK = os.getenv("DISCORD_GATES_WEBHOOK", "")

BRAND_USERNAME = "PicksByJonny"
EMBED_COLOR = 0x111111  # near-black, matches the luxury/sharp brand
TOP_GATES = 15          # cap Section 1 rows so the embed field stays < 1024 chars

# Post-once guard, shared cross-process helper if present (mirror weekly_recap).
try:
    from discord_guard import claim_post as _claim_post, release_post as _release_post
    _HAS_GUARD = True
except ImportError:
    _HAS_GUARD = False


# ── Data loading + aggregation ────────────────────────────────────────────────

def load_blocked_rows(path=PICK_LOG_BLOCKED_PATH) -> list[dict]:
    """Read the blocked-pick ledger. Returns [] if the file doesn't exist yet."""
    p = Path(path)
    if not p.exists():
        return []
    # errors="replace": the ledger can carry cp1252 accents in player names
    # (e.g. "Jokić"). We only read date/sport/gate_result, so a mangled name
    # byte must not crash the digest.
    with open(p, newline="", encoding="utf-8", errors="replace") as f:
        return list(csv.DictReader(f))


def filter_week_blocked(rows: list[dict], mon_str: str, sun_str: str) -> list[dict]:
    """Rows whose ``date`` falls in [mon_str, sun_str]. Dates are YYYY-MM-DD
    strings (lexicographic compare == calendar compare for that format)."""
    return [
        r for r in rows
        if mon_str <= (r.get("date") or "").strip() <= sun_str
    ]


def tally_gate_fires(week_rows: list[dict]):
    """Return (by_gate Counter, gate_sport {gate: Counter{sport: n}}, total)."""
    by_gate: Counter = Counter()
    gate_sport: dict[str, Counter] = defaultdict(Counter)
    for r in week_rows:
        gate = (r.get("gate_result") or "").strip()
        if not gate:
            continue
        sport = (r.get("sport") or "").strip() or "?"
        by_gate[gate] += 1
        gate_sport[gate][sport] += 1
    total = sum(by_gate.values())
    return by_gate, gate_sport, total


# ── Rendering ─────────────────────────────────────────────────────────────────

def _sport_split(sport_counts: Counter) -> str:
    """'NBA 30, MLB 12' — descending by count."""
    return ", ".join(f"{sp} {n}" for sp, n in sport_counts.most_common())


def build_section1_lines(mon_str: str, sun_str: str) -> list[str]:
    """Section 1 — gate fires this week (from the blocked-pick ledger)."""
    week_rows = filter_week_blocked(load_blocked_rows(), mon_str, sun_str)
    by_gate, gate_sport, total = tally_gate_fires(week_rows)

    if total == 0:
        return ["No structural gate blocks logged this week."]

    lines = [f"{total} structural blocks across {len(by_gate)} gate(s):"]
    for gate, cnt in by_gate.most_common(TOP_GATES):
        lines.append(f"  {gate} — {cnt}  ({_sport_split(gate_sport[gate])})")
    if len(by_gate) > TOP_GATES:
        lines.append(f"  ...and {len(by_gate) - TOP_GATES} more gate(s)")
    lines.append(
        "Excluded by design: suspension gates (SOG/HA/RA) + "
        "shadow-routed gates (G8B/G8C/G8D/R4_REB_*/R11_AST_U25/...)."
    )
    return lines


def build_section2_lines() -> list[str]:
    """Section 2 — open data-gate progress snapshot (not weekly-windowed)."""
    # ASCII markers only — render_console() is the default (blank-webhook) path
    # and prints to the Windows cp1252 console, which can't encode emoji.
    lines = []
    for label, count, target, note, reached in compute_gate_status():
        mark = "[x]" if reached else "[ ]"
        lines.append(f"  {mark} {label}: {count}/{target}  ({note})")
    return lines


def render_console(mon_str: str, sun_str: str) -> str:
    """Plaintext digest for --dry-run or when the webhook is unconfigured."""
    week_label = _fmt_week_label(mon_str, sun_str)
    parts = [
        f"Weekly Gate Digest — {week_label}  ({mon_str} – {sun_str})",
        "",
        "Section 1 — Gate fires this week:",
        *build_section1_lines(mon_str, sun_str),
        "",
        "Section 2 — Open data-gate progress (snapshot):",
        *build_section2_lines(),
    ]
    return "\n".join(parts)


def build_digest_embed(mon_str: str, sun_str: str) -> dict:
    """Discord embed payload. No @everyone — this is ops, not member-facing."""
    week_label = _fmt_week_label(mon_str, sun_str)
    s1 = "\n".join(build_section1_lines(mon_str, sun_str))[:1024]
    s2 = "\n".join(build_section2_lines())[:1024]
    embed = {
        "title": f"Weekly Gate Digest — {week_label}",
        "color": EMBED_COLOR,
        "fields": [
            {"name": "Gate fires this week", "value": s1 or "—", "inline": False},
            {"name": "Open data-gate progress (snapshot)", "value": s2 or "—", "inline": False},
        ],
        "footer": {"text": f"{mon_str} – {sun_str} · structural blocks only"},
    }
    return {"username": BRAND_USERNAME, "embeds": [embed]}


# ── Posting ───────────────────────────────────────────────────────────────────

def post_digest(mon_str: str, sun_str: str, dry_run: bool = False, force: bool = False) -> bool:
    """Post the digest, or print it when --dry-run / webhook unconfigured.

    Returns True if the digest was delivered (posted or printed), False only on
    a real POST failure.
    """
    # Console path: dry-run, or no webhook configured (blank-default opt-in).
    if dry_run or not DISCORD_GATES_WEBHOOK:
        why = "dry-run" if dry_run else "DISCORD_GATES_WEBHOOK unset"
        print(f"[gate-digest] console output ({why}):\n")
        print(render_console(mon_str, sun_str))
        return True

    guard_key = f"gate_digest:{mon_str}"
    if _HAS_GUARD and not force:
        if not _claim_post(guard_key):
            print(f"  [gate-digest] already posted for {mon_str} — use --repost to override")
            return True

    # Lazy import: only needed on the live-POST path.
    from discord_post import _webhook_post

    payload = build_digest_embed(mon_str, sun_str)
    if _webhook_post(DISCORD_GATES_WEBHOOK, payload, label="gate digest"):
        print(f"  [gate-digest] OK posted — week of {_fmt_week_label(mon_str, sun_str)}")
        return True

    if _HAS_GUARD and not force:
        _release_post(guard_key)  # let a retry re-post
    print("  [gate-digest] FAILED post")
    return False


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Post the weekly gate-counter digest")
    parser.add_argument("--week", default=None,
                        help="Any date within the target week (YYYY-MM-DD). "
                             "Defaults to the most recently completed week.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print to console; never POST to Discord.")
    parser.add_argument("--repost", action="store_true",
                        help="Bypass the post-once guard.")
    args = parser.parse_args()

    if args.week:
        ref_date = datetime.strptime(args.week, "%Y-%m-%d")
        mon_str, sun_str = week_range_containing(ref_date)
    else:
        mon_str, sun_str = week_range()

    posted = post_digest(mon_str, sun_str, dry_run=args.dry_run, force=args.repost)
    sys.exit(0 if posted else 2)


if __name__ == "__main__":
    main()
