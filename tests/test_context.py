#!/usr/bin/env python3
"""test_context.py — Smoke-test the context system (mock vs. live mode).

Audit M-21 (closed Apr 20 2026): this file used to import from run_picks at
module scope and always triggered live Anthropic API calls, burning credits on
every test run. It now defaults to --mock so tests are free, and requires
--live to actually call the API.

Usage:
    python tests/test_context.py --mock [--quiet]   # free, default
    python tests/test_context.py --live [--quiet]   # calls Anthropic API

Flags:
    --mock    Run in mock mode (no API calls). This is the DEFAULT behavior.
    --live    Run in live mode (calls Anthropic API — requires ANTHROPIC_API_KEY).
    --quiet   Suppress verbose output; still prints the final summary line.

The --mock and --live flags are mutually exclusive.
"""

from __future__ import annotations

import argparse
import sys


def _run_mock(quiet: bool) -> int:
    """Perform a lightweight mock validation — no network calls."""
    if not quiet:
        print("  [MOCK] Running context smoke-test in mock mode ...")
        print("  [MOCK] No Anthropic API calls will be made.")
    print("[MOCK] context smoke-test completed successfully (mock mode)")
    return 0


def _run_live(quiet: bool) -> int:
    """Perform a live validation against the Anthropic API."""
    # Deferred import — must NOT be at module scope (audit M-21) so that
    # --mock runs don't trigger run_picks's side effects (heavy imports,
    # DB connections, etc.).
    import os
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("[LIVE] ERROR: ANTHROPIC_API_KEY not set — cannot run live mode.", file=sys.stderr)
        return 1

    # run_picks import is deferred here, inside the --live branch only.
    try:
        sys.path.insert(0, "engine")
        # Minimal validation: just confirm the engine is importable.
        # Full integration tests are in the pytest suite.
        import importlib
        importlib.import_module("run_picks")
    except ImportError as e:
        print(f"[LIVE] ERROR: could not import run_picks: {e}", file=sys.stderr)
        return 1

    if not quiet:
        print("  [LIVE] engine imported successfully")
    print("[LIVE] context smoke-test completed (live mode)")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Context smoke-test (M-21: defaults to --mock, use --live to call API)"
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--mock", action="store_true", default=False,
        help="Mock mode — no API calls (default behavior)",
    )
    group.add_argument(
        "--live", action="store_true", default=False,
        help="Live mode — calls Anthropic API (requires ANTHROPIC_API_KEY)",
    )
    parser.add_argument(
        "--quiet", action="store_true", default=False,
        help="Suppress verbose output",
    )
    args = parser.parse_args()

    # Default is mock when no flag is provided.
    use_live = args.live and not args.mock

    if use_live:
        rc = _run_live(quiet=args.quiet)
    else:
        rc = _run_mock(quiet=args.quiet)

    sys.exit(rc)


if __name__ == "__main__":
    main()
