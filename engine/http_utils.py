"""http_utils.py — shared HTTP helpers for the JonnyParlay engine.

Closes audit M-4 (webhook retry safety) + M-16 (User-Agent on API calls).

* :data:`JONNYPARLAY_UA` — canonical User-Agent string. Every outbound
  request the engine makes — Odds API, NBA / NHL / MLB stats endpoints,
  Discord webhooks — should carry this UA so server-side logs can
  distinguish us from generic ``python-requests`` scrapers (some CDNs
  outright block the default UA — see ``post_nrfi_bonus.py`` where we
  had to work around Cloudflare's 1010 block).

* :func:`default_headers` — drop-in ``headers=`` argument for
  ``requests.get/post`` calls. Accepts an optional ``extra`` mapping so
  callers can add request-specific headers (``Content-Type``, etc.)
  without re-listing the UA each time.

* :func:`retry_after_secs` — robust ``Retry-After`` parser. The naive
  pattern the engine had before was ``float(r.json().get("retry_after", …))``
  which:

      1. crashed on empty / non-JSON 429 responses;
      2. ignored the ``Retry-After`` HTTP header that Discord and most
         CDNs actually use;
      3. accepted any junk the JSON happened to contain, including
         strings with units like ``"2s"`` that ``float`` rejects.

  The replacement prefers the header, falls back to the JSON body, and
  clamps the result into a sensible range so a rogue ``retry_after=3600``
  can't stall a grader run for an hour.
"""

from __future__ import annotations

from email.utils import parsedate_to_datetime
from typing import Mapping, MutableMapping


__all__ = [
    "JONNYPARLAY_UA",
    "default_headers",
    "retry_after_secs",
]


# Matches the Mozilla-flavoured UA the manual bonus poster uses, plus a
# JonnyParlay tag so operators can find our traffic in server logs.
JONNYPARLAY_UA: str = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "JonnyParlay/1.0 (+https://picksbyjonny.com)"
)


def default_headers(extra: Mapping[str, str] | None = None) -> dict[str, str]:
    """Return a headers dict containing the canonical User-Agent.

    If ``extra`` is provided, its keys are merged on top. A key of
    ``"User-Agent"`` in ``extra`` deliberately wins over the default so
    specialized callers (e.g. scrapers that need to mimic a browser
    exactly) can override — but those should be rare.
    """
    headers: dict[str, str] = {"User-Agent": JONNYPARLAY_UA}
    if extra:
        headers.update(extra)
    return headers


# Clamp: nothing should ever sleep longer than 30s from a single
# Retry-After hint. Discord's advertised worst-case backoff is ~15s.
_MAX_RETRY_AFTER_S: float = 30.0
# Floor: even a deliberately small value (0 / 0.1) is still worth a
# beat so we don't hammer the endpoint with a tight loop.
_MIN_RETRY_AFTER_S: float = 0.5


def retry_after_secs(response, default: float = 2.0) -> float:
    """Best-effort parse of the ``Retry-After`` directive from a 429 response.

    Priority order:

      1. ``Retry-After`` HTTP header, parsed as either a float (seconds)
         or an HTTP date (per RFC 7231).
      2. JSON body ``retry_after`` field (Discord's rate-limit shape).
      3. ``default``.

    The result is clamped to ``[_MIN_RETRY_AFTER_S, _MAX_RETRY_AFTER_S]``.

    This helper never raises — a malformed response body falls through
    to the default rather than propagating into the webhook retry loop.
    """
    # 1. Header (float seconds OR HTTP date).
    header_val = ""
    try:
        header_val = str(response.headers.get("Retry-After", "") or "").strip()
    except AttributeError:
        # Response object doesn't expose .headers — fall through.
        header_val = ""

    if header_val:
        try:
            return _clamp(float(header_val))
        except (TypeError, ValueError):
            pass
        # Could be an HTTP date (e.g. "Wed, 21 Oct 2026 07:28:00 GMT").
        try:
            from datetime import datetime, timezone
            target = parsedate_to_datetime(header_val)
            if target is not None:
                if target.tzinfo is None:
                    target = target.replace(tzinfo=timezone.utc)
                delta = (target - datetime.now(tz=timezone.utc)).total_seconds()
                if delta > 0:
                    return _clamp(delta)
        except Exception:
            pass

    # 2. JSON body. Many 429 responses have empty or non-JSON bodies,
    #    so every .json() access must be guarded.
    try:
        body = response.json()
    except Exception:
        body = None
    if isinstance(body, MutableMapping) or isinstance(body, dict):
        candidate = body.get("retry_after")
        if candidate is not None:
            try:
                return _clamp(float(candidate))
            except (TypeError, ValueError):
                pass

    # 3. Default.
    return _clamp(float(default))


def _clamp(value: float) -> float:
    if value < _MIN_RETRY_AFTER_S:
        return _MIN_RETRY_AFTER_S
    if value > _MAX_RETRY_AFTER_S:
        return _MAX_RETRY_AFTER_S
    return value
