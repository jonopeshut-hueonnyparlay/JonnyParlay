"""capture_clv_batch.py -- idempotent, re-runnable nightly CLV batch (#15).

Replaces the long-running, flaky capture_clv DAEMON (uptime guards, poll windows, a
single-instance lock, self-termination timers) with discrete, re-runnable batch
invocations (Brief-2's "nightly-batch reality"): schedule it across the tip window
(alongside the closing-line cron) instead of holding a process open all day. Each run
GAP-DETECTS pick_log rows still missing a closing line, fetches each one's closing odds
(from the live market near tip), writes closing_odds + clv back IDEMPOTENTLY, and records
provenance keyed by (event id, target timestamp). Re-running is a no-op for rows already
captured, so a missed invocation is simply recovered by the next run -- none of the
daemon's fragility, and graded rows whose market has closed stay pending (logged, not
corrupted).

The per-pick closing-odds fetch is INJECTABLE (closing_for_pick); the default reuses the
daemon's proven helpers (fetch_events / fetch_game_odds / flatten_outcomes /
get_closing_odds_for_pick) with a per-game odds cache, fail-soft. CLV math is the
daemon's calc_clv (single source of truth -- no formula drift).

CLI:  python engine/capture_clv_batch.py [--date YYYY-MM-DD] [--logs path ...]
"""
from __future__ import annotations

import argparse
import csv
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

_ENGINE = Path(__file__).resolve().parent
if str(_ENGINE) not in sys.path:
    sys.path.insert(0, str(_ENGINE))

from capture_clv import calc_clv  # single source of truth for the CLV formula
from pick_log_io import read_rows_locked_if_exists
from pick_log_schema import CANONICAL_HEADER, write_schema_sidecar

try:
    from paths import PICK_LOG_PATH, DATA_DIR
except Exception:  # pragma: no cover
    DATA_DIR = _ENGINE.parent / "data"
    PICK_LOG_PATH = DATA_DIR / "pick_log.csv"

try:
    from filelock import FileLock
except Exception:  # pragma: no cover
    FileLock = None

log = logging.getLogger("jonnyparlay")

_GRADED = {"W", "L", "PUSH", "P", "VOID"}
_PROVENANCE_PATH = Path(DATA_DIR) / "clv_capture_provenance.csv"
_PROV_FIELDS = ["captured_at", "event_id", "target_ts", "date", "player", "stat",
                "line", "direction", "your_odds", "closing_odds", "book", "clv"]


def needs_clv(row: dict) -> bool:
    """A graded pick whose closing line was never captured -- the gap the batch fills.

    Graded (the game is final, so the close is knowable) AND closing_odds is blank or
    'STALE' (the daemon gave up). Re-runnable: a row with a real closing_odds is skipped.
    """
    if str(row.get("result") or "").strip().upper() not in _GRADED:
        return False
    co = str(row.get("closing_odds") or "").strip().upper()
    return co in ("", "STALE")


def _your_odds(row: dict):
    s = (row.get("odds") or "").strip()
    if not s:
        return None
    try:
        return int(float(s.lstrip("+")))
    except (TypeError, ValueError):
        return None


def apply_batch(rows: list, closing_for_pick, now_iso: str):
    """Fill closing_odds/clv on every pending row via closing_for_pick(pick). Mutates
    rows in place. Idempotent: only rows where needs_clv() are touched, and a row whose
    fetch returns None stays pending (recovered next run). Returns (n_pending, captures).
    """
    captures, pending = [], 0
    for r in rows:
        if not needs_clv(r):
            continue
        pending += 1
        try:
            quote = closing_for_pick(r)
        except Exception as exc:
            log.warning("clv batch: fetch failed for %s (%s)", r.get("player"), exc)
            quote = None
        if not quote:
            continue
        closing_odds, closing_opp, book, event_id, target_ts = quote
        if closing_odds is None:
            continue
        yo = _your_odds(r)
        clv = calc_clv(yo, closing_odds, closing_opp) if yo not in (None, 0) else None
        r["closing_odds"] = closing_odds
        if clv is not None:
            r["clv"] = round(clv, 6)
        captures.append({
            "captured_at": now_iso, "event_id": event_id or "", "target_ts": target_ts or "",
            "date": r.get("date", ""), "player": r.get("player", ""), "stat": r.get("stat", ""),
            "line": r.get("line", ""), "direction": r.get("direction", ""), "your_odds": yo,
            "closing_odds": closing_odds, "book": book or "", "clv": r.get("clv", ""),
        })
    return pending, captures


def _write_back(path: Path, rows: list) -> None:
    """Atomically rewrite the pick_log with closing_odds/clv filled (canonical schema)."""
    def _do():
        tmp = path.with_suffix(path.suffix + ".tmp")
        with open(tmp, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=CANONICAL_HEADER, extrasaction="ignore", restval="")
            w.writeheader()
            w.writerows(rows)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
        try:
            write_schema_sidecar(path)
        except Exception as exc:  # pragma: no cover
            log.warning("clv batch: sidecar refresh failed (%s)", exc)

    if FileLock is not None:
        with FileLock(str(path) + ".lock", timeout=30):
            _do()
    else:  # pragma: no cover
        _do()


def _append_provenance(captures: list, provenance_path: Path) -> None:
    if not captures:
        return
    provenance_path.parent.mkdir(parents=True, exist_ok=True)
    new = not provenance_path.exists() or provenance_path.stat().st_size == 0
    with open(provenance_path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=_PROV_FIELDS, extrasaction="ignore")
        if new:
            w.writeheader()
        w.writerows(captures)


def make_default_closing_for_pick(date: str):
    """Production fetcher: reuse the daemon's helpers with a per-(sport,game) odds cache.

    Fail-soft -> None on any miss (the row stays pending and the next run retries). Uses
    vigged CLV (closing_opp=None); the vig-free refinement remains the daemon's domain.
    """
    from capture_clv import (SPORT_KEYS, fetch_events, fetch_game_odds,
                             flatten_outcomes, get_closing_odds_for_pick)
    _ev_cache: dict = {}   # sport -> [events]
    _odds_cache: dict = {}  # event_id -> (outcomes_by_market, home, away, commence)

    def _events(sport):
        key = SPORT_KEYS.get((sport or "").upper())
        if not key:
            return []
        if sport not in _ev_cache:
            try:
                _ev_cache[sport] = fetch_events(key) or []
            except Exception:
                _ev_cache[sport] = []
        return _ev_cache[sport]

    def _match_event(sport, game):
        g = (game or "").lower()
        for ev in _events(sport):
            home, away = ev.get("home_team", ""), ev.get("away_team", "")
            if home and away and (home.lower() in g or away.lower() in g):
                return ev
        return None

    def closing_for_pick(pick):
        sport, game = pick.get("sport", ""), pick.get("game", "")
        ev = _match_event(sport, game)
        if not ev:
            return None
        eid = ev.get("id", "")
        if eid not in _odds_cache:
            try:
                key = SPORT_KEYS.get((sport or "").upper())
                data = fetch_game_odds(eid, key, ["h2h", "spreads", "totals"])
                _odds_cache[eid] = (flatten_outcomes(data) if data else {},
                                    ev.get("home_team", ""), ev.get("away_team", ""),
                                    ev.get("commence_time", ""))
            except Exception:
                _odds_cache[eid] = ({}, "", "", "")
        obm, home, away, commence = _odds_cache[eid]
        if not obm:
            return None
        try:
            closing_odds, book = get_closing_odds_for_pick(pick, obm, home, away)
        except Exception:
            return None
        if closing_odds is None:
            return None
        return (closing_odds, None, book, eid, commence)

    return closing_for_pick


def run_batch(date: str = None, log_paths: list = None, closing_for_pick=None,
              now_iso: str = None, provenance_path: Path = None) -> dict:
    """Run one idempotent CLV pass over the pick logs. Returns a summary dict."""
    now_iso = now_iso or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    closing_for_pick = closing_for_pick or make_default_closing_for_pick(date)
    prov = Path(provenance_path or _PROVENANCE_PATH)
    paths = [Path(p) for p in (log_paths or [PICK_LOG_PATH])]

    summary = {"now": now_iso, "logs": [], "pending": 0, "captured": 0}
    for path in paths:
        rows, _ = read_rows_locked_if_exists(path)
        if not rows:
            summary["logs"].append({"path": str(path), "pending": 0, "captured": 0})
            continue
        if date:
            target = [r for r in rows if r.get("date") == date]
        else:
            target = rows
        pending, captures = apply_batch(target, closing_for_pick, now_iso)
        if captures:
            _write_back(path, rows)        # rows mutated in place -> writes filled values
            _append_provenance(captures, prov)
        summary["logs"].append({"path": str(path), "pending": pending, "captured": len(captures)})
        summary["pending"] += pending
        summary["captured"] += len(captures)
    return summary


def main(argv=None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser(description="Idempotent nightly CLV batch (#15).")
    ap.add_argument("--date", help="only this ET slate date (YYYY-MM-DD)")
    ap.add_argument("--logs", nargs="*", help="pick_log paths (default: the main pick_log)")
    ns = ap.parse_args(argv)
    s = run_batch(date=ns.date, log_paths=ns.logs)
    print(f"CLV batch: {s['captured']} captured / {s['pending']} pending across "
          f"{len(s['logs'])} log(s). Re-run any time to fill the rest.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
