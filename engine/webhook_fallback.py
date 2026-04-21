"""Fallback webhook notifier for primary Discord post failures.

Audit H-7 (closed Apr 20 2026).

Before this module, a failed post to ``#announcements`` looked like this:

    1. morning_preview or weekly_recap POSTs the embed.
    2. Discord returns 4xx / 5xx / network error.
    3. ``_webhook_post`` prints a ``⚠`` and returns False.
    4. The CLI exits non-zero (Section 31 pre-H-7 partial close).
    5. Jono finds out the next morning when nobody DMs him about the card.

The non-zero exit does surface in Task Scheduler's history column — but only
if Jono opens it. The audit asked for a loud secondary channel: post a short
"primary failed" alert to a fallback webhook so the notification hits Jono's
phone the same way the recap would have.

Design
------
* ``DISCORD_FALLBACK_WEBHOOK`` is optional. If blank, ``notify_fallback`` is
  a silent no-op — back-compat is the default for any install without the
  env var set.
* The notifier **never raises**. A failing notifier must not mask the real
  failure it's trying to announce.
* The posted payload is compact — single ~80-char content string, no embed,
  no files — so the fallback channel can be rate-limited without drama.

Usage (from morning_preview / weekly_recap failure paths)::

    from webhook_fallback import notify_fallback
    if not posted:
        notify_fallback("morning_preview", err="HTTP 404 (channel deleted?)")
        sys.exit(2)
"""

from __future__ import annotations

import socket
from datetime import datetime, timezone
from typing import Optional

try:
    import requests
except ImportError:  # requests is a hard dep in production — test envs may skip
    requests = None  # type: ignore[assignment]

try:
    # Canonical UA (audit M-16). Ignored if http_utils isn't importable (unit tests).
    from http_utils import default_headers as _default_headers
except Exception:  # pragma: no cover — http_utils import failure is not our problem
    def _default_headers() -> dict[str, str]:
        return {"User-Agent": "JonnyParlay/fallback"}


# ── Knobs ─────────────────────────────────────────────────────────────────────
# The fallback POST has a VERY short timeout. If the primary webhook is
# already down, the fallback endpoint may ALSO be under stress; a long
# timeout would stall the CLI and make Task Scheduler's retry behavior
# unpredictable. 4 seconds is enough for a healthy Discord POST and short
# enough that a fully-down endpoint doesn't block the exit.
FALLBACK_TIMEOUT_SECS: float = 4.0

# Content length cap — Discord hard-limits content to 2000 chars. We keep
# the alert well under that so a future extra field can't accidentally
# overflow, AND because a paging alert should be terse.
MAX_CONTENT_LEN: int = 400


def _resolve_url() -> str:
    """Fetch the fallback webhook URL at call time, not at import time.

    Reading through a helper (instead of importing the module-level constant
    from secrets_config) lets tests monkeypatch the env var per-test without
    having to reload the whole module. secrets_config reads env at import;
    this reads env on every call.
    """
    import os
    return os.environ.get("DISCORD_FALLBACK_WEBHOOK", "") or ""


def _format_alert(context: str, err: Optional[str]) -> str:
    """Build the single-line alert content string.

    Example:
        [picksbyjonny alert] morning_preview post failed · host=jono-pc
        2026-04-20T14:02:11Z · err: HTTP 404 (channel deleted?)
    """
    host = socket.gethostname() or "unknown-host"
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    base = f"🚨 [picksbyjonny alert] {context} post failed · host={host} · {ts}"
    if err:
        base += f" · err: {err}"
    if len(base) > MAX_CONTENT_LEN:
        base = base[: MAX_CONTENT_LEN - 3] + "..."
    return base


def notify_fallback(context: str, err: Optional[str] = None) -> bool:
    """Post a compact alert to DISCORD_FALLBACK_WEBHOOK.

    Parameters
    ----------
    context : str
        Short tag identifying the caller, e.g. ``"morning_preview"`` or
        ``"weekly_recap"``. Surfaced in the alert body so the receiver can
        tell which post failed.
    err : str, optional
        Free-text error detail to append (usually the HTTP status or a
        snippet of the error body). Keep it short — the content is capped.

    Returns
    -------
    bool
        True if the fallback POST returned 2xx. False if disabled, if the
        webhook URL is blank, if requests is unavailable, or if the POST
        itself failed. **Never raises** — a notifier that crashes the caller
        defeats the purpose.
    """
    url = _resolve_url()
    if not url:
        # Feature disabled — no alerts. Print a hint once so Jono can see
        # in the log why the fallback didn't fire if he expected it to.
        print("  [webhook_fallback] DISCORD_FALLBACK_WEBHOOK not set — no secondary alert sent")
        return False

    if requests is None:
        print("  [webhook_fallback] requests unavailable — cannot send fallback alert")
        return False

    content = _format_alert(context, err)
    payload = {"content": content}

    try:
        r = requests.post(
            url,
            json=payload,
            headers=_default_headers(),
            timeout=FALLBACK_TIMEOUT_SECS,
        )
    except Exception as e:  # noqa: BLE001 — swallow EVERYTHING
        # Don't let a dead fallback webhook crash the caller.
        print(f"  [webhook_fallback] alert POST raised {type(e).__name__}: {e}")
        return False

    ok = 200 <= getattr(r, "status_code", 0) < 300
    if ok:
        print(f"  [webhook_fallback] secondary alert sent ({r.status_code})")
    else:
        # Don't retry — if both primary and fallback are down, keep the
        # failure loud but don't hammer either endpoint.
        body = getattr(r, "text", "")[:120]
        print(f"  [webhook_fallback] alert POST returned {r.status_code}: {body}")
    return ok


__all__ = [
    "FALLBACK_TIMEOUT_SECS",
    "MAX_CONTENT_LEN",
    "notify_fallback",
]
