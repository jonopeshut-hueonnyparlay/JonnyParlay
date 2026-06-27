#!/usr/bin/env python3
"""P-1 — Deterministic replay harness (JonnyParlay-only).

Re-runs the ``run_picks`` pipeline against FROZEN snapshots (CSV + odds JSON)
with **no live API calls** and a **frozen wall clock**, so two runs of the same
code produce byte-identical output. This is the safety net for the audit fix
pass: capture a golden from the unchanged build, then after each code change
re-run and diff to see exactly what repriced.

Determinism seams (why this is reproducible):
  * Clock      — frozen with ``freezegun.freeze_time`` (cache filename, tip-time
                 filtering, and pick-row timestamps all read ``datetime.now``).
  * Odds       — ``OddsFetcher._load_cache`` is monkeypatched to return the
                 snapshot's odds JSON. On a cache hit ``fetch_all`` returns the
                 pre-filtered ``{events, game_lines, props}`` block and skips all
                 network AND the wall-clock tip-time filter.
  * MLB starts — ``mlb_starter_fetcher.fetch_confirmed_starters`` stubbed to ``{}``
                 (no statsapi call). NB: MLB SP-confirmation is therefore disabled
                 in replay — consistent across runs, but not identical to the
                 original live run. Documented limitation.
  * Writes     — ``--no-save`` (no pick_log writes) + ``--no-discord`` (no posts).
                 The run is effectively read-only.

Usage:
  python replay/run_replay.py --capture        # write goldens from current code
  python replay/run_replay.py                  # check current code vs goldens (diff)
  python replay/run_replay.py --list           # list discovered snapshot jobs

Validation gate (P-1): ``--capture`` then a plain run must report 0 diffs
(byte-identical) — that proves the harness itself is deterministic. After a real
code change, a plain run shows the repricing diff for review.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

REPLAY_DIR = Path(__file__).resolve().parent
REPO_ROOT = REPLAY_DIR.parent
ENGINE_DIR = REPO_ROOT / "engine"
SNAP_DIR = REPLAY_DIR / "snapshots"
GOLDEN_DIR = REPLAY_DIR / "golden"

# Default freeze instant (UTC). 2026-06-15 23:30Z == 17:30 MDT == 19:30 ET,
# all on calendar day 2026-06-15. Overridable per-snapshot via meta.json "as_of".
FREEZE_DEFAULT = "2026-06-15 23:30:00"


def _discover():
    """Yield (date, sport, csv_path, odds_path, as_of) for every snapshot job."""
    jobs = []
    if not SNAP_DIR.exists():
        return jobs
    for snap in sorted(p for p in SNAP_DIR.iterdir() if p.is_dir()):
        meta = {}
        meta_path = snap / "meta.json"
        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        as_of = meta.get("as_of", FREEZE_DEFAULT)
        for csv in sorted(snap.glob("*.csv")):
            sport = csv.stem  # "MLB.csv" -> "MLB"
            odds = snap / f"odds_{sport}.json"
            if odds.exists():
                jobs.append((snap.name, sport, csv, odds, as_of))
    return jobs


def _job_key(date: str, sport: str) -> str:
    return f"{date}__{sport}"


# --------------------------------------------------------------------------- #
# Worker: runs ONE snapshot in an isolated subprocess (own FileLock + globals) #
# --------------------------------------------------------------------------- #
def _run_worker_subprocess(date, sport, csv_path, odds_path, as_of):
    cmd = [
        sys.executable, str(Path(__file__)),
        "--_worker",
        "--date", date, "--sport", sport,
        "--csv", str(csv_path), "--odds", str(odds_path),
        "--as-of", as_of,
    ]
    env = dict(os.environ)
    env["PYTHONHASHSEED"] = "0"            # neutralize set-ordering nondeterminism
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"                # open() defaults to utf-8 in the child
    res = subprocess.run(
        cmd, capture_output=True, cwd=str(REPO_ROOT), env=env,
        encoding="utf-8", errors="replace",
    )
    return res.stdout or "", res.stderr or "", res.returncode


def _apply_manifest_pin(snap_dir: Path) -> Path:
    """Pin the in-force coverage_manifest into the replay (P-1 / #8).

    The resolver + game-line handover both read resolver._MANIFEST_PATH. At replay we
    point it at the snapshot's pinned ``coverage_manifest.csv`` when present, so a
    promoted (weight>0) market replays DETERMINISTICALLY from a frozen input rather than
    the developer's live manifest. Absent -> point at a guaranteed-missing path so the
    resolver is DORMANT in replay (replay output is then independent of whatever is in
    the live coverage_manifest -- a strict determinism improvement). Returns the path used.
    """
    import resolver
    pinned = snap_dir / "coverage_manifest.csv"
    resolver._MANIFEST_PATH = pinned if pinned.exists() else (snap_dir / "__no_pinned_manifest__.csv")
    return resolver._MANIFEST_PATH


def _check_calibration_pin(snap_dir: Path) -> str:
    """Record + soft-check the pinned calibration_version (meta.json) against the code.

    Advisory only: a mismatch is printed to STDERR (never stdout, so goldens are
    unaffected) -- it flags that the snapshot was captured under a different calibration
    than the code now carries. Returns the pinned value ("" if none)."""
    meta_path = snap_dir / "meta.json"
    pinned = ""
    if meta_path.exists():
        try:
            pinned = (json.loads(meta_path.read_text(encoding="utf-8")) or {}).get("calibration_version", "") or ""
        except (OSError, json.JSONDecodeError):
            pinned = ""
    if pinned:
        try:
            from calibrated import PLATT_FIT_DATE as _cur
        except Exception:
            _cur = ""
        if _cur and pinned != _cur:
            print(f"[replay] WARNING: pinned calibration_version {pinned!r} != code {_cur!r} "
                  f"({snap_dir.name})", file=sys.stderr)
    return pinned


def _worker_entry(ns):
    """Inside the isolated subprocess: patch determinism seams, run main()."""
    sys.path.insert(0, str(ENGINE_DIR))

    import odds_io
    import mlb_starter_fetcher

    snap_odds = json.loads(Path(ns.odds).read_text(encoding="utf-8"))

    def _patched_load_cache(self, sport):
        # Return the snapshot for the sport under test; None otherwise.
        return snap_odds if sport == ns.sport else None

    # Patch the shared class object — run_picks holds the same class reference.
    odds_io.OddsFetcher._load_cache = _patched_load_cache
    # No statsapi call; SP-confirmation disabled in replay (see module docstring).
    mlb_starter_fetcher.fetch_confirmed_starters = lambda *a, **k: {}

    import run_picks  # noqa: E402  (after sys.path setup + patches)

    # #8: pin the in-force coverage_manifest + record the calibration_version so a
    # promoted market replays deterministically (and replay is independent of the live
    # manifest). Derive the snapshot dir from the frozen CSV path.
    _snap_dir = Path(ns.csv).resolve().parent
    _apply_manifest_pin(_snap_dir)
    _check_calibration_pin(_snap_dir)

    sys.argv = [
        "run_picks.py", str(ns.csv),
        "--no-save", "--no-discord", "--force", "--test",
        "--skip-health-check",  # replay validates pricing determinism, not env health (P2.10)
        "--mode", "Default",
    ]

    from freezegun import freeze_time
    with freeze_time(ns.as_of):
        try:
            run_picks.main()
        except SystemExit:
            pass


# --------------------------------------------------------------------------- #
# Parent modes: capture / check / list                                        #
# --------------------------------------------------------------------------- #
def _cmd_list(jobs):
    if not jobs:
        print("No snapshot jobs found under replay/snapshots/.")
        return 0
    print(f"{len(jobs)} snapshot job(s):")
    for date, sport, csv, odds, as_of in jobs:
        print(f"  {_job_key(date, sport):24}  csv={csv.name}  odds={odds.name}  as_of={as_of}")
    return 0


def _cmd_capture(jobs):
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    rc = 0
    for date, sport, csv, odds, as_of in jobs:
        key = _job_key(date, sport)
        stdout, stderr, code = _run_worker_subprocess(date, sport, csv, odds, as_of)
        if code != 0:
            print(f"  [FAIL] {key}: worker exited {code}")
            if stderr.strip():
                print("    stderr tail:\n" + "\n".join("      " + ln for ln in stderr.strip().splitlines()[-15:]))
            rc = 1
            continue
        out_path = GOLDEN_DIR / f"{key}.txt"
        out_path.write_text(stdout, encoding="utf-8", newline="\n")
        print(f"  [captured] {key}  ({len(stdout.splitlines())} lines) -> {out_path.relative_to(REPO_ROOT)}")
    return rc


def _cmd_check(jobs):
    import difflib
    if not GOLDEN_DIR.exists() or not any(GOLDEN_DIR.glob("*.txt")):
        print("No goldens found. Run with --capture first.")
        return 2
    any_diff = False
    any_fail = False
    for date, sport, csv, odds, as_of in jobs:
        key = _job_key(date, sport)
        golden_path = GOLDEN_DIR / f"{key}.txt"
        stdout, stderr, code = _run_worker_subprocess(date, sport, csv, odds, as_of)
        if code != 0:
            print(f"  [FAIL] {key}: worker exited {code}")
            if stderr.strip():
                print("    stderr tail:\n" + "\n".join("      " + ln for ln in stderr.strip().splitlines()[-15:]))
            any_fail = True
            continue
        if not golden_path.exists():
            print(f"  [NEW]  {key}: no golden (run --capture). {len(stdout.splitlines())} lines.")
            any_diff = True
            continue
        golden = golden_path.read_text(encoding="utf-8")
        if stdout == golden:
            print(f"  [OK]   {key}: byte-identical ({len(golden.splitlines())} lines)")
        else:
            any_diff = True
            diff = list(difflib.unified_diff(
                golden.splitlines(), stdout.splitlines(),
                fromfile=f"golden/{key}", tofile=f"current/{key}", lineterm=""))
            print(f"  [DIFF] {key}: {sum(1 for d in diff if d and d[0] in '+-' and not d.startswith(('+++','---')))} changed line(s)")
            for ln in diff[:60]:
                print("    " + ln)
            if len(diff) > 60:
                print(f"    ... ({len(diff) - 60} more diff lines)")
    if any_fail:
        return 1
    return 1 if any_diff else 0


def main():
    # Goldens contain emoji (⭐, ♻️ …); the parent prints diffs to a cp1252 console
    # on Windows — force utf-8 so diff printing doesn't crash on non-ASCII.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Deterministic replay harness (P-1).")
    ap.add_argument("--capture", action="store_true", help="Write goldens from current code.")
    ap.add_argument("--list", action="store_true", help="List discovered snapshot jobs.")
    # internal worker flags
    ap.add_argument("--_worker", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--date"); ap.add_argument("--sport")
    ap.add_argument("--csv"); ap.add_argument("--odds"); ap.add_argument("--as-of", dest="as_of")
    ns = ap.parse_args()

    if ns._worker:
        _worker_entry(ns)
        return

    jobs = _discover()
    if ns.list:
        sys.exit(_cmd_list(jobs))
    if ns.capture:
        sys.exit(_cmd_capture(jobs))
    sys.exit(_cmd_check(jobs))


if __name__ == "__main__":
    main()
