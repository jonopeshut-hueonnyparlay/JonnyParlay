#!/usr/bin/env python3
"""Test harness for the context sanity system (run_pregame_scan + run_context_check).

Audit M-21 (closed Apr 20 2026): this file used to execute real Anthropic API
calls on every ``python test_context.py`` invocation, racking up spend against
Jono's credits. It had no flag, no dry-run path, no error handling. Running it
twice accidentally was wasting $0.05-$0.10 per cycle.

The fix is simple: default to ``--mock`` (canned responses, no network I/O) and
require an explicit ``--live`` flag to hit the real API. ``--live`` still needs
``ANTHROPIC_API_KEY`` set — mock doesn't. That way an unconfigured Cowork
sandbox or CI agent can import and run this file without authenticating.

Usage::

    python test_context.py                 # default: mocked, no API calls
    python test_context.py --live          # real calls (uses your API credits)
    python test_context.py --live --quiet  # fewer prints for smoke-test runs

Picks the same sample slate as before (5 NBA props) so the harness output
format remains compatible with any tooling that greps the log.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from typing import Tuple
from zoneinfo import ZoneInfo

# engine/ lives alongside this file; put it on the path so ``run_picks`` and
# its helpers resolve. Doing this before any engine-local import.
sys.path.insert(0, "engine")


# ── Canned mock responses ───────────────────────────────────────────────────

# Mock bulletins mimic what run_pregame_scan() returns: a dict mapping sport →
# a long block of free-text news that the pick-level check later consumes. The
# text intentionally includes one OUT name ("Jalen Green") so the downstream
# context_check can surface a ``conflicts`` verdict in mock mode.
_MOCK_BULLETINS = {
    "NBA": (
        "Injury report roundup: Stephen Curry (upper respiratory) is PROBABLE "
        "and expected to start. Jalen Green is OUT (right hamstring). Devin "
        "Booker is ACTIVE. Paolo Banchero is ACTIVE. LaMelo Ball is ACTIVE. "
        "No rotation changes expected tonight."
    ),
}

# Mock context verdicts: keyed by player name for deterministic output.
# Tuples: (verdict, reason, score) matching run_context_check's return type.
_MOCK_VERDICTS: dict[str, Tuple[str, str, float]] = {
    "Jalen Green":       ("conflicts", "OUT (right hamstring) per mock bulletin", 0.95),
    "Stephen Curry":     ("supports",  "Probable/expected to start — model OK",   0.70),
    "Devin Booker":      ("neutral",   "No material context signal",               0.50),
    "Paolo Banchero":    ("neutral",   "No material context signal",               0.50),
    "LaMelo Ball":       ("supports",  "Active and in starting lineup",            0.65),
}


def _mock_pregame_scan(sports, _today):
    """Drop-in replacement for run_pregame_scan — returns canned bulletins."""
    return {s: _MOCK_BULLETINS.get(s, "") for s in sports}


def _mock_context_check(pick, _today, pregame_notes=""):
    """Drop-in replacement for run_context_check — returns canned verdict."""
    return _MOCK_VERDICTS.get(
        pick.get("player", ""),
        ("neutral", "No mock verdict configured for this player", 0.50),
    )


# ── Sample slate (stable across runs) ───────────────────────────────────────

SAMPLE_PICKS = [
    {"sport": "NBA", "player": "Devin Booker",    "stat": "PTS", "line": 25.5, "direction": "over",
     "game": "Golden State Warriors @ Phoenix Suns"},
    {"sport": "NBA", "player": "LaMelo Ball",     "stat": "3PM", "line": 4.5,  "direction": "over",
     "game": "Charlotte Hornets @ Orlando Magic"},
    {"sport": "NBA", "player": "Paolo Banchero",  "stat": "PTS", "line": 22.5, "direction": "over",
     "game": "Charlotte Hornets @ Orlando Magic"},
    {"sport": "NBA", "player": "Jalen Green",     "stat": "PTS", "line": 18.5, "direction": "over",
     "game": "Golden State Warriors @ Phoenix Suns"},
    {"sport": "NBA", "player": "Stephen Curry",   "stat": "PTS", "line": 26.5, "direction": "over",
     "game": "Golden State Warriors @ Phoenix Suns"},
]


# ── Main ────────────────────────────────────────────────────────────────────

def _parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Run the context sanity system against a canned NBA slate.",
    )
    mode = p.add_mutually_exclusive_group()
    mode.add_argument(
        "--mock",
        action="store_true",
        default=True,
        help="Use canned responses — no Anthropic API calls. Default.",
    )
    mode.add_argument(
        "--live",
        action="store_true",
        default=False,
        help="Hit the real Anthropic API. Costs API credits. Requires ANTHROPIC_API_KEY.",
    )
    p.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress per-pick prints (just emit verdict counts at the end).",
    )
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = _parse_args(argv)

    # --live wins over the (default-True) --mock flag.
    use_live = args.live

    if use_live:
        # Defer the import: we only need the real functions in live mode, and
        # importing run_picks has side effects (configures loggers, reads .env).
        try:
            from run_picks import run_context_check, run_pregame_scan  # type: ignore
        except Exception as e:  # noqa: BLE001 — any import failure is fatal here
            print(f"[test_context] Failed to import live context functions: {e}", file=sys.stderr)
            print("               Run with --mock (default) or fix your ANTHROPIC_API_KEY.", file=sys.stderr)
            return 2
        pregame_scan_fn = run_pregame_scan
        context_check_fn = run_context_check
        mode_label = "LIVE"
    else:
        pregame_scan_fn = _mock_pregame_scan
        context_check_fn = _mock_context_check
        mode_label = "MOCK"

    today = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
    if not args.quiet:
        print(f"--- Pregame scan ({today}) [{mode_label}] ---")

    sports = sorted({p["sport"] for p in SAMPLE_PICKS})
    try:
        bulletins = pregame_scan_fn(sports, today)
    except Exception as e:  # noqa: BLE001
        print(f"[test_context] pregame scan failed: {type(e).__name__}: {e}", file=sys.stderr)
        return 2

    if not args.quiet:
        for sport, text in bulletins.items():
            snippet = (text or "(empty)")[:150].replace("\n", " ")
            print(f"  [{sport}] {snippet}...")

        print(f"\n--- Sanity checks [{mode_label}] ---")
        print(f"{'Player':<22} {'Stat':<5} {'Verdict':<12}  Reason")
        print("-" * 70)

    counts = {"supports": 0, "neutral": 0, "conflicts": 0, "skipped": 0, "error": 0}
    for p in SAMPLE_PICKS:
        notes = bulletins.get(p["sport"], "")
        try:
            verdict, reason, _score = context_check_fn(p, today, pregame_notes=notes)
        except Exception as e:  # noqa: BLE001
            verdict, reason = "error", f"{type(e).__name__}: {e}"
        counts[verdict] = counts.get(verdict, 0) + 1
        if not args.quiet:
            icon = {
                "conflicts": "X CUT",
                "supports":  "+ GOOD",
                "neutral":   "- PASS",
                "skipped":   "~ SKIP",
                "error":     "! ERR",
            }.get(verdict, "- PASS")
            print(f"{p['player']:<22} {p['stat']:<5} {icon:<12}  {reason}")

    # Summary line is always printed — stable smoke-test signal.
    total = len(SAMPLE_PICKS)
    print(
        f"[{mode_label}] {total} picks · "
        f"supports={counts['supports']} · neutral={counts['neutral']} · "
        f"conflicts={counts['conflicts']} · errors={counts['error']}"
    )

    # Exit 1 if any check errored out so a CI wrapper flags it.
    return 1 if counts.get("error", 0) else 0


if __name__ == "__main__":
    raise SystemExit(main())
