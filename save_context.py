#!/usr/bin/env python3
"""
save_context.py — Save Claude.ai context research JSON to context_verdicts.json.

Usage:
    python save_context.py                     # reads from clipboard
    python save_context.py context_output.json # reads from file
    python save_context.py --dry-run           # preview only, no write

Drop this file at C:\\Dev\\JonnyParlay\\save_context.py
"""

import json
import sys
import re
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

_LOCAL_TZ      = ZoneInfo("America/Denver")
_ROOT          = Path(__file__).resolve().parent
_VERDICTS_PATH = _ROOT / "data" / "context_verdicts.json"

VALID_VERDICTS   = {"confirms", "neutral", "conflicts"}
REQUIRED_FACTORS = {
    "rlm", "line_move", "public_sharp", "weather", "era_fip",
    "bullpen", "umpire", "pythag", "form", "division",
    "motivation", "home_away", "injury", "rest", "travel",
}


# ── Helpers ────────────────────────────────────────────────────────────────────
def _load_existing() -> list:
    if _VERDICTS_PATH.exists():
        try:
            return json.loads(_VERDICTS_PATH.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


def _validate(entry: dict) -> str | None:
    if not entry.get("game"):
        return "missing 'game'"
    if entry.get("verdict") not in VALID_VERDICTS:
        return f"invalid verdict: {entry.get('verdict')!r}"
    factors = entry.get("factors", {})
    missing = REQUIRED_FACTORS - set(factors)
    if missing:
        return f"missing factors: {sorted(missing)}"
    bad = {k: v for k, v in factors.items() if v not in VALID_VERDICTS}
    if bad:
        return f"bad factor values: {bad}"
    return None


def _merge(existing: list, new_entries: list, today: str) -> list:
    kept  = [e for e in existing if e.get("date") == today]
    index = {(e["game"], e["date"]): i for i, e in enumerate(kept)}
    for entry in new_entries:
        entry.setdefault("date", today)
        key = (entry["game"], entry["date"])
        if key in index:
            kept[index[key]] = entry
        else:
            index[key] = len(kept)
            kept.append(entry)
    return kept


def _strip_and_parse(raw: str) -> list:
    raw = re.sub(r"```json\s*", "", raw)
    raw = re.sub(r"```\s*", "", raw)
    return json.loads(raw.strip())


def _read_clipboard() -> str:
    try:
        import pyperclip
        return pyperclip.paste()
    except ImportError:
        pass
    # Windows fallback via PowerShell
    try:
        import subprocess
        result = subprocess.run(
            ["powershell", "-Command", "Get-Clipboard"],
            capture_output=True, text=True, timeout=5
        )
        return result.stdout
    except Exception:
        pass
    raise RuntimeError("Could not read clipboard. Install pyperclip: pip install pyperclip")


# ── Main ──────────────────────────────────────────────────────────────────────
def main() -> None:
    dry_run = "--dry-run" in sys.argv
    args    = [a for a in sys.argv[1:] if not a.startswith("--")]

    # ── Read raw JSON ──────────────────────────────────────────────────────────
    if args:
        path = Path(args[0])
        if not path.exists():
            print(f"ERROR: file not found: {path}")
            sys.exit(1)
        raw = path.read_text(encoding="utf-8")
        source = str(path)
    else:
        print("Reading from clipboard...")
        try:
            raw = _read_clipboard()
        except RuntimeError as e:
            print(f"ERROR: {e}")
            sys.exit(1)
        source = "clipboard"

    # ── Parse ──────────────────────────────────────────────────────────────────
    try:
        entries = _strip_and_parse(raw)
    except json.JSONDecodeError as e:
        print(f"ERROR: could not parse JSON from {source}: {e}")
        sys.exit(1)

    if not isinstance(entries, list):
        print("ERROR: expected a JSON array at the top level")
        sys.exit(1)

    # ── Validate ───────────────────────────────────────────────────────────────
    errors = []
    for i, entry in enumerate(entries):
        err = _validate(entry)
        if err:
            errors.append(f"  entry {i} ({entry.get('game', '?')}): {err}")
    if errors:
        print("VALIDATION ERRORS:")
        for e in errors:
            print(e)
        sys.exit(1)

    # ── Stamp defaults ─────────────────────────────────────────────────────────
    today   = datetime.now(_LOCAL_TZ).strftime("%Y-%m-%d")
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    for entry in entries:
        entry.setdefault("date", today)
        entry.setdefault("sport", "MLB")
        entry.setdefault("researched_at", now_iso)

    # ── Preview ────────────────────────────────────────────────────────────────
    print(f"\n  {len(entries)} verdict(s) for {today}:")
    for e in entries:
        icon = {"confirms": "✅", "conflicts": "❌", "neutral": "➖"}.get(e["verdict"], "?")
        print(f"  {icon} [{e['verdict'].upper():8s}] {e['game']}  (conf={e.get('confidence',0):.2f})")

    if dry_run:
        print("\n  [DRY RUN] — nothing written\n")
        return

    # ── Merge + write ──────────────────────────────────────────────────────────
    existing = _load_existing()
    merged   = _merge(existing, entries, today)

    tmp = _VERDICTS_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(merged, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(_VERDICTS_PATH)

    print(f"\n  ✅ Saved {len(merged)} total verdict(s) → {_VERDICTS_PATH}\n")


if __name__ == "__main__":
    main()
