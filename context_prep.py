#!/usr/bin/env python3
"""
context_prep.py — Fetches today's MLB/WNBA games from Odds API and copies
a ready-to-paste context research prompt to clipboard.

Usage:
    python context_prep.py
    python context_prep.py --sport MLB
    python context_prep.py --sport WNBA

Drop this file at C:\\Dev\\JonnyParlay\\context_prep.py
"""

import os
import sys
import json
import argparse
import urllib.request
import urllib.parse
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

# ── Load .env ──────────────────────────────────────────────────────────────────
_ROOT = Path(__file__).resolve().parent
_ENV  = _ROOT / ".env"

def _load_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

_load_env(_ENV)

API_KEY   = os.getenv("ODDS_API_KEY", "")   # never hardcode the key (audit 2026-06)
LOCAL_TZ  = ZoneInfo("America/Denver")

ACTIVE_SPORTS = {
    "baseball_mlb":     "MLB",
    "basketball_wnba":  "WNBA",
}

# ── Prompt template ────────────────────────────────────────────────────────────
_TEMPLATE = """\
You are doing daily context research for JonnyParlay, a quantitative sports betting engine. \
Research each game below using web search and return a JSON array — nothing else, no explanation.

TODAY: {date}

GAMES:
{games}

---

For each game research these 15 factors:
rlm (reverse line movement), line_move (since open), public_sharp (public % vs sharp), \
weather (MLB only), era_fip (pitcher matchup), bullpen (last 3 days), umpire (run environment), \
pythag (win% vs record), form (last 10), division (rivalry context), motivation (playoff/rest), \
home_away (home/away splits), injury (key players), rest (days rest), travel (road team timezone)

Factor verdict: "confirms" | "neutral" | "conflicts"
Weights: rlm/injury/line_move = 3x | era_fip/bullpen/public_sharp/motivation = 2x | rest/others = 1x
Overall verdict: "confirms" if weighted confirms >60% | "conflicts" if weighted conflicts >60% | else "neutral"
Confidence: abs(confirms_weight - conflicts_weight) / total_weight

Return ONLY valid JSON — no markdown, no text before or after:

[
  {{
    "game": "AWAY @ HOME",
    "date": "{date_iso}",
    "sport": "MLB",
    "verdict": "neutral",
    "confidence": 0.00,
    "factors": {{
      "rlm": "neutral", "line_move": "neutral", "public_sharp": "neutral",
      "weather": "neutral", "era_fip": "neutral", "bullpen": "neutral",
      "umpire": "neutral", "pythag": "neutral", "form": "neutral",
      "division": "neutral", "motivation": "neutral", "home_away": "neutral",
      "injury": "neutral", "rest": "neutral", "travel": "neutral"
    }},
    "summary": "1-2 sentences on strongest signals only.",
    "researched_at": "{date_iso}T00:00:00"
  }}
]
"""

# ── Odds API fetch ─────────────────────────────────────────────────────────────
def _fetch_games(sport_key: str, sport_name: str, today, now) -> list[str]:
    params = urllib.parse.urlencode({"apiKey": API_KEY, "dateFormat": "iso"})
    url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/events?{params}"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            events = json.loads(resp.read().decode())
    except Exception as e:
        print(f"  ⚠  Could not fetch {sport_name}: {e}")
        return []

    lines = []
    for ev in events:
        ts = ev["commence_time"].replace("Z", "+00:00")
        local = datetime.fromisoformat(ts).astimezone(LOCAL_TZ)
        if local.date() != today or local <= now:
            continue
        # "%-I" is Linux; on Windows use "%#I"
        try:
            time_str = local.strftime("%-I:%M %p MDT")
        except ValueError:
            time_str = local.strftime("%#I:%M %p MDT")
        lines.append(f"- {ev['away_team']} @ {ev['home_team']} ({time_str}) — {sport_name}")
    return lines


# ── Clipboard ─────────────────────────────────────────────────────────────────
def _copy(text: str) -> bool:
    try:
        import pyperclip
        pyperclip.copy(text)
        return True
    except ImportError:
        pass
    # Windows fallback
    try:
        import subprocess
        proc = subprocess.Popen(["clip"], stdin=subprocess.PIPE, shell=True)
        proc.communicate(text.encode("utf-8"))
        return proc.returncode == 0
    except Exception:
        pass
    return False


# ── Main ──────────────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(description="Generate JonnyParlay context research prompt")
    parser.add_argument("--sport", default="ALL", choices=["ALL", "MLB", "WNBA", "NBA", "NHL"])
    args = parser.parse_args()

    now   = datetime.now(LOCAL_TZ)
    today = now.date()
    date_str = now.strftime("%B %-d, %Y") if sys.platform != "win32" else now.strftime("%B %#d, %Y")
    date_iso = today.isoformat()

    print(f"\nJonnyParlay Context Prep — {date_str}")
    print("─" * 45)

    sport_filter = None if args.sport == "ALL" else args.sport
    all_games: list[str] = []

    for sport_key, sport_name in ACTIVE_SPORTS.items():
        if sport_filter and sport_name != sport_filter:
            continue
        print(f"  Fetching {sport_name}...", end=" ", flush=True)
        games = _fetch_games(sport_key, sport_name, today, now)
        print(f"{len(games)} game(s)")
        all_games.extend(games)

    if not all_games:
        print("\n  No games found for today. Check API key or pass games manually.")
        sys.exit(1)

    print()
    for g in all_games:
        print(f"  {g}")

    prompt = _TEMPLATE.format(
        date=date_str,
        date_iso=date_iso,
        games="\n".join(all_games),
    )

    # Save to file
    out_path = _ROOT / "context_prompt_today.txt"
    out_path.write_text(prompt, encoding="utf-8")
    print(f"\n  Saved → {out_path}")

    if _copy(prompt):
        print("  ✅ Copied to clipboard — paste into Claude Opus 4.8\n")
    else:
        print("  (Could not copy to clipboard — use the saved file)\n")
        print("  pip install pyperclip  ← fixes clipboard support\n")


if __name__ == "__main__":
    main()
