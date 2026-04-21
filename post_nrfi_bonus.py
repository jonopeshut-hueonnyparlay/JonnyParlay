"""
One-shot bonus webhook post for TOR@ARI NRFI Under 0.5.
Was blocked by GG1 gate on auto-run; posting manually as bonus drop.
Run from Windows:  python post_nrfi_bonus.py

Audit fixes layered in (Section 20):
  - PICK_LOG H-1 / AUDIT H-14: shadow-aware log routing. MLB picks go to
    pick_log_mlb.csv, not the main log. Shadow picks never post to Discord
    either — this script guards both.
  - H-3: schema comes from pick_log_schema.CANONICAL_HEADER, not an inline
    27-col list that drifts from truth.
  - PICK_LOG H-3: odds normalized via normalize_american_odds before write
    (always sign-prefixed: "+108", never bare "108").
  - H-8 / M-series: write held under pick_log_lock so a concurrent
    capture_clv.py / grade_picks.py read doesn't tear the append.
"""
import csv
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

# Load bonus webhook from env/.env (audit C-6). secrets_config lives in engine/.
sys.path.insert(0, str(Path(__file__).parent / "engine"))
from secrets_config import DISCORD_BONUS_WEBHOOK as WEBHOOK  # noqa: E402
from pick_log_schema import (  # noqa: E402
    CANONICAL_HEADER,
    normalize_american_odds,
    normalize_edge,
    normalize_is_home,
    normalize_proj,
    normalize_size,
    write_schema_sidecar,
)
from pick_log_io import pick_log_lock  # noqa: E402

# Centralized brand tagline (audit L-7).
from brand import BRAND_TAGLINE  # noqa: E402

# ── shadow-sport routing ──────────────────────────────────────────────────────
# Mirror of run_picks.SHADOW_SPORTS / SHADOW_LOG_PATHS. Keep in sync — these
# drive whether a pick is allowed to post to Discord AT ALL, and which CSV it
# gets appended to. If a shadow sport ever gets promoted, update both this
# script and run_picks.py together.
SHADOW_SPORTS = frozenset({"MLB"})

DATA_DIR = Path(__file__).parent / "data"
MAIN_LOG = DATA_DIR / "pick_log.csv"
SHADOW_LOGS = {
    "MLB": DATA_DIR / "pick_log_mlb.csv",
}


def _log_path_for(sport: str) -> Path:
    """Return the correct log CSV for ``sport``.

    Shadow sports go to their isolated log so nothing downstream (Discord
    recap, public card, analyze_picks breakouts) accidentally surfaces them.
    """
    if sport and sport.upper() in SHADOW_SPORTS:
        path = SHADOW_LOGS.get(sport.upper())
        if path is None:  # pragma: no cover — defensive
            raise RuntimeError(
                f"sport {sport!r} is in SHADOW_SPORTS but has no log path "
                f"mapped. Add it to SHADOW_LOGS."
            )
        return path
    return MAIN_LOG


# ── pick data ─────────────────────────────────────────────────────────────────

SPORT = "MLB"  # ← controls routing. MLB → shadow log, no Discord post.

desc = (
    "**Blue Jays @ Diamondbacks — NRFI Under 0.5**\n"
    "+108 @ FanDuel — **0.50u**\n\n"
    "Win: **68.4%** · Edge: **21.3%** · Tier: **T2**\n"
    "Model NRFI prob: 68% · Line moved +106 → +108"
)
payload = {
    "username": "PicksByJonny",
    "embeds": [{
        "title": "💎 Bonus Drop",
        "description": desc,
        "color": 0x00BFFF,
        "footer": {"text": BRAND_TAGLINE},
    }],
}

# ── POST webhook (shadow-gated) ──────────────────────────────────────────────
# Shadow sports never post. PICK_LOG_AUDIT H-1 was the public leak case:
# this script posted an MLB bonus to the public bonus-drops channel even
# though MLB is supposed to be silent. Gate at the webhook, not just at the
# log write.
if SPORT.upper() in SHADOW_SPORTS:
    print(
        f"[Discord] SKIP — {SPORT} is a shadow sport. Webhook suppressed. "
        f"Row will be appended to {_log_path_for(SPORT).name} for tracking."
    )
else:
    req = urllib.request.Request(
        WEBHOOK,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) PicksByJonny/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            print(f"[Discord] Webhook POST status: {r.status}")
    except urllib.error.HTTPError as e:
        print(f"[Discord] FAILED: {e.code} {e.reason}")
        print(e.read().decode("utf-8", errors="replace"))
        sys.exit(1)

# ── Append pick_log ──────────────────────────────────────────────────────────
now_et = datetime.now(ZoneInfo("America/New_York"))
today = now_et.strftime("%Y-%m-%d")
run_time = now_et.strftime("%H:%M")

row = {
    "date": today,
    "run_time": run_time,
    "run_type": "bonus",
    "sport": SPORT,
    "player": "NRFI",
    # Audit L-9 (closed Apr 20 2026): the pick_log schema expects a single
    # team name in the `team` column — "TOR@ARI" is a game string, not a team,
    # and breaks downstream readers that split by team (grader accent-matching,
    # team-pace lookups). For pitcher-matchup props like NRFI we store the away
    # team to mirror the leftmost slot in the `game` field (away @ home).
    "team": "Toronto Blue Jays",
    "stat": "NRFI",
    "line": "0.5",
    "direction": "under",
    # Normalized at write time (audit M-3 / M-10 / M-11) — match Section 24
    # normalizers used by run_picks.py so downstream readers never have to guess.
    "proj":     normalize_proj("0.68"),
    "win_prob": "0.6840",
    "edge":     normalize_edge("0.2130"),
    # Normalized at write time (PICK_LOG_AUDIT H-3) — always sign-prefixed.
    "odds":     normalize_american_odds("+108"),
    "book": "fanduel",
    "tier": "T2",
    "pick_score": "85.0",
    "size":     normalize_size("0.50"),
    "game": "Toronto Blue Jays @ Arizona Diamondbacks",
    "mode": "",
    "result": "",
    "closing_odds": "",
    "clv": "",
    "card_slot": "",
    # Stat-aware is_home normalizer: NRFI is not in _IS_HOME_REQUIRED_STATS
    # so this stays blank. If the stat is ever swapped to SPREAD/ML/F5, the
    # helper enforces a canonical "True"/"False".
    "is_home": normalize_is_home("", "NRFI"),
    "context_verdict": "",
    "context_reason": "",
    "context_score": "",
}

log_path = _log_path_for(SPORT)
log_path.parent.mkdir(parents=True, exist_ok=True)

# Hold the shared pick_log FileLock across the existence-check AND the write
# so a concurrent writer can't append between our header-check and our row
# (audit H-8 / M-series).
with pick_log_lock(log_path):
    write_header = not log_path.exists() or log_path.stat().st_size == 0
    with open(log_path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CANONICAL_HEADER, extrasaction="ignore")
        if write_header:
            w.writeheader()
        w.writerow(row)

# Refresh the schema sidecar (audit M-13) so readers can detect version drift.
# Best-effort — a sidecar failure must never orphan the pick we just logged.
try:
    write_schema_sidecar(log_path)
except Exception as _sidecar_err:
    print(f"[pick_log] ⚠ M-13 sidecar refresh failed for {log_path}: {_sidecar_err}")

print(f"[pick_log] ✅ Appended bonus row: TOR@ARI NRFI U0.5 @ +108 fanduel")
print(f"[pick_log] {log_path}")
