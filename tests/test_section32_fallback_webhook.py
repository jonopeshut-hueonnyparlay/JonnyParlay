"""Regression tests for Section 32 — H-7 fallback webhook notifier.

Covers:
    - engine/webhook_fallback.py public contract + error-swallow guarantee
    - notify_fallback() no-ops when DISCORD_FALLBACK_WEBHOOK is unset
    - notify_fallback() posts once on failure, does not retry
    - Network/transport errors are swallowed (never raise)
    - morning_preview.py + weekly_recap.py both import + call notify_fallback
      on their post-failure code path, right before sys.exit(2)
    - Alert content stays under Discord's content length cap
    - secrets_config surfaces DISCORD_FALLBACK_WEBHOOK in the registry
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
ENGINE_DIR = REPO_ROOT / "engine"
sys.path.insert(0, str(ENGINE_DIR))


# ── webhook_fallback module contract ──────────────────────────────────────────

def test_webhook_fallback_module_importable():
    import webhook_fallback  # noqa: F401
    assert hasattr(webhook_fallback, "notify_fallback")
    assert hasattr(webhook_fallback, "FALLBACK_TIMEOUT_SECS")
    assert hasattr(webhook_fallback, "MAX_CONTENT_LEN")


def test_public_api_exported():
    import webhook_fallback
    assert set(webhook_fallback.__all__) == {
        "FALLBACK_TIMEOUT_SECS",
        "MAX_CONTENT_LEN",
        "notify_fallback",
    }


def test_timeout_is_short_enough_to_not_stall_cli():
    """If both primary and fallback are down, the CLI must still exit quickly.
    Anything over 10s will stall Task Scheduler's retry loop."""
    import webhook_fallback
    assert webhook_fallback.FALLBACK_TIMEOUT_SECS <= 10.0


def test_content_cap_under_discord_hard_limit():
    """Discord's content field hard-limits at 2000 chars. Leave headroom."""
    import webhook_fallback
    assert webhook_fallback.MAX_CONTENT_LEN <= 2000


# ── notify_fallback behavior ──────────────────────────────────────────────────

def test_notify_fallback_no_op_when_env_unset(monkeypatch):
    """If DISCORD_FALLBACK_WEBHOOK isn't set, we never touch the network."""
    monkeypatch.delenv("DISCORD_FALLBACK_WEBHOOK", raising=False)
    import webhook_fallback
    with patch.object(webhook_fallback, "requests") as mock_requests:
        result = webhook_fallback.notify_fallback("test_ctx")
        assert result is False
        mock_requests.post.assert_not_called()


def test_notify_fallback_no_op_when_env_blank(monkeypatch):
    """Empty string ≡ unset — back-compat for cleared env vars."""
    monkeypatch.setenv("DISCORD_FALLBACK_WEBHOOK", "")
    import webhook_fallback
    with patch.object(webhook_fallback, "requests") as mock_requests:
        result = webhook_fallback.notify_fallback("test_ctx")
        assert result is False
        mock_requests.post.assert_not_called()


def test_notify_fallback_posts_when_configured(monkeypatch):
    monkeypatch.setenv("DISCORD_FALLBACK_WEBHOOK", "https://discord.com/api/webhooks/test")
    import webhook_fallback
    mock_response = MagicMock(status_code=204, text="")
    with patch.object(webhook_fallback, "requests") as mock_requests:
        mock_requests.post.return_value = mock_response
        result = webhook_fallback.notify_fallback("morning_preview", err="HTTP 404")
    assert result is True
    mock_requests.post.assert_called_once()
    # Verify URL + content shape.
    _, kwargs = mock_requests.post.call_args
    assert "content" in kwargs["json"]
    assert "morning_preview" in kwargs["json"]["content"]
    assert "HTTP 404" in kwargs["json"]["content"]


def test_notify_fallback_swallows_network_error(monkeypatch):
    """A dead fallback must not crash the caller."""
    monkeypatch.setenv("DISCORD_FALLBACK_WEBHOOK", "https://example.com/webhook")
    import webhook_fallback
    with patch.object(webhook_fallback, "requests") as mock_requests:
        mock_requests.post.side_effect = ConnectionError("DNS resolution failed")
        # Must not raise.
        result = webhook_fallback.notify_fallback("weekly_recap")
    assert result is False


def test_notify_fallback_does_not_retry(monkeypatch):
    """On 5xx we intentionally do NOT retry — would hammer a stressed endpoint."""
    monkeypatch.setenv("DISCORD_FALLBACK_WEBHOOK", "https://discord.com/api/webhooks/test")
    import webhook_fallback
    mock_response = MagicMock(status_code=500, text="server error")
    with patch.object(webhook_fallback, "requests") as mock_requests:
        mock_requests.post.return_value = mock_response
        result = webhook_fallback.notify_fallback("weekly_recap")
    assert result is False
    assert mock_requests.post.call_count == 1


def test_notify_fallback_handles_400_series(monkeypatch):
    """Webhook revoked / expired → 401/404. No retry, return False, no raise."""
    monkeypatch.setenv("DISCORD_FALLBACK_WEBHOOK", "https://discord.com/api/webhooks/test")
    import webhook_fallback
    mock_response = MagicMock(status_code=404, text='{"message":"Unknown Webhook"}')
    with patch.object(webhook_fallback, "requests") as mock_requests:
        mock_requests.post.return_value = mock_response
        result = webhook_fallback.notify_fallback("morning_preview")
    assert result is False


def test_notify_fallback_swallows_any_exception_type(monkeypatch):
    """BLE001 swallow is intentional — every exception type must be absorbed."""
    monkeypatch.setenv("DISCORD_FALLBACK_WEBHOOK", "https://example.com/webhook")
    import webhook_fallback
    for exc in (ValueError("v"), RuntimeError("r"), OSError("o"), TimeoutError("t")):
        with patch.object(webhook_fallback, "requests") as mock_requests:
            mock_requests.post.side_effect = exc
            result = webhook_fallback.notify_fallback("ctx")
        assert result is False, f"notify_fallback leaked {type(exc).__name__}"


def test_notify_fallback_returns_false_when_requests_missing(monkeypatch):
    monkeypatch.setenv("DISCORD_FALLBACK_WEBHOOK", "https://discord.com/api/webhooks/test")
    import webhook_fallback
    with patch.object(webhook_fallback, "requests", None):
        result = webhook_fallback.notify_fallback("ctx")
    assert result is False


def test_alert_content_includes_timestamp_and_host(monkeypatch):
    monkeypatch.setenv("DISCORD_FALLBACK_WEBHOOK", "https://discord.com/api/webhooks/test")
    import webhook_fallback
    mock_response = MagicMock(status_code=204, text="")
    with patch.object(webhook_fallback, "requests") as mock_requests:
        mock_requests.post.return_value = mock_response
        webhook_fallback.notify_fallback("weekly_recap", err="HTTP 503")
    content = mock_requests.post.call_args.kwargs["json"]["content"]
    # ISO-ish UTC timestamp marker.
    assert re.search(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", content)
    assert "host=" in content
    assert "weekly_recap" in content


def test_alert_content_truncated_at_cap(monkeypatch):
    monkeypatch.setenv("DISCORD_FALLBACK_WEBHOOK", "https://discord.com/api/webhooks/test")
    import webhook_fallback
    mock_response = MagicMock(status_code=204, text="")
    with patch.object(webhook_fallback, "requests") as mock_requests:
        mock_requests.post.return_value = mock_response
        huge_err = "x" * 10_000
        webhook_fallback.notify_fallback("ctx", err=huge_err)
    content = mock_requests.post.call_args.kwargs["json"]["content"]
    assert len(content) <= webhook_fallback.MAX_CONTENT_LEN
    assert content.endswith("...")


def test_alert_works_without_err_arg(monkeypatch):
    monkeypatch.setenv("DISCORD_FALLBACK_WEBHOOK", "https://discord.com/api/webhooks/test")
    import webhook_fallback
    mock_response = MagicMock(status_code=204, text="")
    with patch.object(webhook_fallback, "requests") as mock_requests:
        mock_requests.post.return_value = mock_response
        assert webhook_fallback.notify_fallback("ctx") is True
    content = mock_requests.post.call_args.kwargs["json"]["content"]
    assert "ctx" in content
    assert "err:" not in content  # No err appended.


def test_notify_fallback_uses_short_timeout(monkeypatch):
    monkeypatch.setenv("DISCORD_FALLBACK_WEBHOOK", "https://discord.com/api/webhooks/test")
    import webhook_fallback
    mock_response = MagicMock(status_code=204, text="")
    with patch.object(webhook_fallback, "requests") as mock_requests:
        mock_requests.post.return_value = mock_response
        webhook_fallback.notify_fallback("ctx")
    kwargs = mock_requests.post.call_args.kwargs
    assert kwargs["timeout"] == webhook_fallback.FALLBACK_TIMEOUT_SECS


def test_notify_fallback_sends_jonnyparlay_user_agent(monkeypatch):
    """Audit M-16 parity — secondary alerts must also carry the canonical UA."""
    monkeypatch.setenv("DISCORD_FALLBACK_WEBHOOK", "https://discord.com/api/webhooks/test")
    import webhook_fallback
    mock_response = MagicMock(status_code=204, text="")
    with patch.object(webhook_fallback, "requests") as mock_requests:
        mock_requests.post.return_value = mock_response
        webhook_fallback.notify_fallback("ctx")
    headers = mock_requests.post.call_args.kwargs["headers"]
    ua = headers.get("User-Agent", "")
    assert "JonnyParlay" in ua


def test_resolve_url_reads_env_at_call_time(monkeypatch):
    """Importing webhook_fallback must NOT snapshot the env var — tests need
    to be able to set the var AFTER import."""
    # Clear, import, then set — should still work.
    monkeypatch.delenv("DISCORD_FALLBACK_WEBHOOK", raising=False)
    import webhook_fallback
    assert webhook_fallback._resolve_url() == ""
    monkeypatch.setenv("DISCORD_FALLBACK_WEBHOOK", "https://x.example/y")
    assert webhook_fallback._resolve_url() == "https://x.example/y"


# ── Caller wiring ─────────────────────────────────────────────────────────────

def _strip_comments(source: str) -> str:
    """Strip # comments so a regex search for executable-code patterns doesn't
    false-positive on doc prose referencing the same token."""
    out = []
    for line in source.splitlines():
        if line.lstrip().startswith("#"):
            continue
        idx = line.find("#")
        if idx != -1:
            line = line[:idx]
        out.append(line)
    return "\n".join(out)


def test_morning_preview_imports_notify_fallback():
    src = _strip_comments((ENGINE_DIR / "morning_preview.py").read_text(encoding="utf-8"))
    assert "from webhook_fallback import notify_fallback" in src
    assert "notify_fallback(" in src


def test_weekly_recap_imports_notify_fallback():
    src = _strip_comments((ENGINE_DIR / "weekly_recap.py").read_text(encoding="utf-8"))
    assert "from webhook_fallback import notify_fallback" in src
    assert "notify_fallback(" in src


def test_morning_preview_calls_fallback_before_exit():
    """Order check: notify_fallback must appear before sys.exit(2) in the
    failure branch so the alert is sent before the process dies."""
    src = _strip_comments((ENGINE_DIR / "morning_preview.py").read_text(encoding="utf-8"))
    # Find the "post failed" branch. Simple substring order check — if both
    # tokens appear, the fallback call must come first.
    notify_idx = src.find("notify_fallback(")
    # Use a specific substring that only appears in the failure branch.
    exit_idx = src.rfind("sys.exit(2)")
    assert notify_idx != -1 and exit_idx != -1
    assert notify_idx < exit_idx, \
        "notify_fallback must be called BEFORE sys.exit(2) so the alert fires"


def test_weekly_recap_calls_fallback_before_exit():
    src = _strip_comments((ENGINE_DIR / "weekly_recap.py").read_text(encoding="utf-8"))
    notify_idx = src.find("notify_fallback(")
    exit_idx = src.rfind("sys.exit(2)")
    assert notify_idx != -1 and exit_idx != -1
    assert notify_idx < exit_idx


def test_callers_wrap_fallback_in_try_except():
    """Paranoid contract: even though notify_fallback swallows its own errors,
    callers must still wrap it so a future refactor (e.g. someone adds a raise
    inside the notifier) can't leak an exception past the exit code."""
    for name in ("morning_preview.py", "weekly_recap.py"):
        src = _strip_comments((ENGINE_DIR / name).read_text(encoding="utf-8"))
        # Find the block containing notify_fallback.
        idx = src.find("notify_fallback(")
        assert idx != -1
        # Walk back up ~400 chars and check for "try:" before the call.
        window = src[max(0, idx - 400):idx]
        assert "try:" in window, \
            f"{name} must wrap notify_fallback in try/except as a belt-and-suspenders guard"


# ── secrets_config integration ────────────────────────────────────────────────

def test_secrets_config_exposes_fallback_webhook():
    import secrets_config
    assert hasattr(secrets_config, "DISCORD_FALLBACK_WEBHOOK")


def test_secrets_config_registry_includes_fallback():
    import secrets_config
    registry = secrets_config._WEBHOOK_REGISTRY
    assert "fallback" in registry
    env_key, _url = registry["fallback"]
    assert env_key == "DISCORD_FALLBACK_WEBHOOK"


def test_require_webhook_fallback_raises_when_unset(monkeypatch):
    """Optional-by-default means require_webhook('fallback') should raise when
    the URL is blank — mirror the behavior of require_webhook('announce')."""
    # Need to reload secrets_config after monkeypatching.
    monkeypatch.setenv("DISCORD_FALLBACK_WEBHOOK", "")
    # Force fresh import so module-level constants re-read env.
    if "secrets_config" in sys.modules:
        del sys.modules["secrets_config"]
    import secrets_config
    with pytest.raises(RuntimeError, match="fallback"):
        secrets_config.require_webhook("fallback")


def test_require_webhook_fallback_returns_when_set(monkeypatch):
    monkeypatch.setenv("DISCORD_FALLBACK_WEBHOOK", "https://discord.com/api/webhooks/fb")
    if "secrets_config" in sys.modules:
        del sys.modules["secrets_config"]
    import secrets_config
    assert secrets_config.require_webhook("fallback") == "https://discord.com/api/webhooks/fb"


# ── Cleanup ───────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _restore_secrets_config_after_mutation():
    """Some tests above reload secrets_config with patched env vars. Restore
    a clean module state afterward so downstream tests don't inherit a
    mutated module global."""
    yield
    for mod in ("secrets_config",):
        sys.modules.pop(mod, None)
