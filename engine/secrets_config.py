"""secrets_config.py — Centralized secrets for the JonnyParlay engine.

Reads from environment variables first, then from a local `.env` file in
the project root (or engine/, or ~/Documents/JonnyParlay/). `.env` is
git-ignored; this module is safe to commit.

Usage (in any engine file):
    from secrets_config import ODDS_API_KEY, DISCORD_WEBHOOK_URL
    # or
    from secrets_config import require_odds_api_key, require_webhook

On Windows, Jono's canonical `.env` lives at:
    C:\\Users\\jono4\\Documents\\JonnyParlay\\.env

Template (copy from `.env.example`):
    ODDS_API_KEY=...
    DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
    DISCORD_BONUS_WEBHOOK=...
    DISCORD_ALT_PARLAY_WEBHOOK=...
    DISCORD_RECAP_WEBHOOK=...
    DISCORD_KILLSHOT_WEBHOOK=...
    DISCORD_MONTHLY_WEBHOOK=...
    DISCORD_ANNOUNCE_WEBHOOK=...
    DISCORD_FALLBACK_WEBHOOK=...   # optional — fires on primary post failure (H-7)

Covers audit findings C-5 (hardcoded Odds API key) and C-6 (hardcoded
Discord webhook URLs).
"""

from __future__ import annotations

import os
from pathlib import Path


# ── .env loader (no external deps) ──────────────────────────────────────────

def _load_dotenv(path: Path) -> bool:
    """Load KEY=VALUE pairs from a .env file into os.environ.

    Existing environment variables take precedence (never overwritten).
    Quoted values (single or double) have the quotes stripped.
    Comment lines (starting with #) and blank lines are ignored.
    Returns True if the file existed and was parsed, False otherwise.
    """
    if not path.exists():
        return False
    try:
        with path.open("r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                key, _, val = line.partition("=")
                key = key.strip()
                val = val.strip()
                # Strip matching surrounding quotes
                if len(val) >= 2 and val[0] == val[-1] and val[0] in ("'", '"'):
                    val = val[1:-1]
                if key and key not in os.environ:
                    os.environ[key] = val
        return True
    except OSError:
        return False


# Candidate locations (first match wins). Ordered by precedence:
#   1. Project root (one level above engine/)
#   2. Engine folder itself
#   3. Windows user's canonical JonnyParlay folder
_ENGINE_DIR = Path(__file__).resolve().parent
_CANDIDATES = [
    _ENGINE_DIR.parent / ".env",
    _ENGINE_DIR / ".env",
    Path.home() / "Documents" / "JonnyParlay" / ".env",
]
DOTENV_PATH: Path | None = None
for _p in _CANDIDATES:
    if _load_dotenv(_p):
        DOTENV_PATH = _p
        break


# ── Public secrets ──────────────────────────────────────────────────────────

ODDS_API_KEY: str = os.getenv("ODDS_API_KEY", "")

# Discord webhooks — one per channel. Blank = not configured.
DISCORD_WEBHOOK_URL:        str = os.getenv("DISCORD_WEBHOOK_URL",        "")  # #premium-portfolio
DISCORD_BONUS_WEBHOOK:      str = os.getenv("DISCORD_BONUS_WEBHOOK",      "")  # #bonus-drops
DISCORD_ALT_PARLAY_WEBHOOK: str = os.getenv("DISCORD_ALT_PARLAY_WEBHOOK", "")  # #daily-lay
DISCORD_RECAP_WEBHOOK:      str = os.getenv("DISCORD_RECAP_WEBHOOK",      "")  # #daily-recap
DISCORD_KILLSHOT_WEBHOOK:   str = os.getenv("DISCORD_KILLSHOT_WEBHOOK",   "")  # #killshot
DISCORD_MONTHLY_WEBHOOK:    str = os.getenv("DISCORD_MONTHLY_WEBHOOK",    "")  # #monthly-tracker
DISCORD_ANNOUNCE_WEBHOOK:   str = os.getenv("DISCORD_ANNOUNCE_WEBHOOK",   "")  # #announcements
# H-7 (closed Apr 20 2026): optional secondary webhook. When the primary
# #announcements webhook fails (deleted channel, 4xx, Cloudflare outage), the
# morning_preview / weekly_recap posters send a compact alert here so Jono
# finds out within seconds instead of the next day. Blank = feature disabled.
# Point at a personal DM webhook or a low-traffic mod-alerts channel.
DISCORD_FALLBACK_WEBHOOK:   str = os.getenv("DISCORD_FALLBACK_WEBHOOK",   "")  # optional alert channel


# ── Helpers (fail-fast when a value is required at use-time) ────────────────

def require_odds_api_key() -> str:
    """Return ODDS_API_KEY or raise a descriptive error. Use in API call sites."""
    if not ODDS_API_KEY:
        raise RuntimeError(
            "ODDS_API_KEY not configured. Set the env var, or add "
            "ODDS_API_KEY=<key> to .env (see secrets_config.py docstring "
            "for path candidates)."
        )
    return ODDS_API_KEY


_WEBHOOK_REGISTRY = {
    "premium":    ("DISCORD_WEBHOOK_URL",        DISCORD_WEBHOOK_URL),
    "bonus":      ("DISCORD_BONUS_WEBHOOK",      DISCORD_BONUS_WEBHOOK),
    "alt_parlay": ("DISCORD_ALT_PARLAY_WEBHOOK", DISCORD_ALT_PARLAY_WEBHOOK),
    "recap":      ("DISCORD_RECAP_WEBHOOK",      DISCORD_RECAP_WEBHOOK),
    "killshot":   ("DISCORD_KILLSHOT_WEBHOOK",   DISCORD_KILLSHOT_WEBHOOK),
    "monthly":    ("DISCORD_MONTHLY_WEBHOOK",    DISCORD_MONTHLY_WEBHOOK),
    "announce":   ("DISCORD_ANNOUNCE_WEBHOOK",   DISCORD_ANNOUNCE_WEBHOOK),
    "fallback":   ("DISCORD_FALLBACK_WEBHOOK",   DISCORD_FALLBACK_WEBHOOK),
}


def require_webhook(name: str) -> str:
    """Return a webhook URL by short name (e.g. 'announce') or raise."""
    if name not in _WEBHOOK_REGISTRY:
        raise KeyError(f"Unknown webhook name: {name!r}. Valid: {sorted(_WEBHOOK_REGISTRY)}")
    env_key, url = _WEBHOOK_REGISTRY[name]
    if not url:
        raise RuntimeError(
            f"Webhook {name!r} not configured. Set env var {env_key} or add "
            f"{env_key}=<url> to .env."
        )
    return url


def summary() -> str:
    """Return a redacted inventory — useful for debugging missing secrets."""
    def _redact(s: str) -> str:
        if not s:
            return "<not set>"
        return s[:8] + "..." + s[-4:] if len(s) > 16 else "<set>"
    lines = [f"  .env loaded from: {DOTENV_PATH or '<none>'}"]
    lines.append(f"  ODDS_API_KEY:        {_redact(ODDS_API_KEY)}")
    for short, (env_key, url) in _WEBHOOK_REGISTRY.items():
        lines.append(f"  {env_key:28s} {_redact(url)}")
    return "\n".join(lines)


if __name__ == "__main__":
    print("JonnyParlay secrets inventory:\n")
    print(summary())
