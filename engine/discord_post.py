"""Discord I/O layer — webhook posting, post-dedup guard, embeds, and the posters.

Extracted from run_picks.py (extract-and-re-export refactor, Step 16) and re-imported
there so existing call sites and `from run_picks import ...` (including the SGP builders'
`from run_picks import _webhook_post`) keep resolving. Owns:
  - the confirm-mode flag (set/get accessors — a mutated module-global cannot be shared
    by a re-export, so run_picks calls set_confirm_mode()/get_confirm_mode()),
  - the context-verdict cache (_CTX_VERDICTS, loaded at import — read by the embeds),
  - the cross-process post-dedup guard, _webhook_post, all embed builders, all posters,
  - the post-guard / session-cap query helpers the posters depend on
    (_card_guard_should_block_logging, _card_already_posted_today, _units_bet_today).

Imports only {stdlib, requests, http_utils, webhook_fallback, discord_guard,
secrets_config, paths, brand, io_utils, book_names, output_format, sizing,
pick_log_lock, pick_log_writers, quant.odds, thresholds} — never run_picks or the
other extracted modules.
"""
import os
import csv
import json
import time
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path

from secrets_config import (
    DISCORD_WEBHOOK_URL,
    DISCORD_BONUS_WEBHOOK,
    DISCORD_ALT_PARLAY_WEBHOOK,
    DISCORD_LONGSHOT_WEBHOOK,
    DISCORD_KILLSHOT_WEBHOOK,
)
from paths import (
    PICK_LOG_PATH as _PICK_LOG_PATH_P,
    DISCORD_GUARD_FILE as _DISCORD_GUARD_FILE_P,
)
from brand import BRAND_TAGLINE
from io_utils import atomic_write_json
from book_names import display_book
from output_format import fmt_odds, fmt_pct
from sizing import size_daily_lay, size_bonus_pick
from pick_log_lock import _pick_log_lock
from pick_log_writers import (
    _log_daily_lay, _log_longshot, _log_value_parlay, _log_bonus_pick,
)
from quant.odds import implied_prob
from thresholds import (
    MIN_DAILY_LAY_PROB, LONGSHOT_SIZE, VALUE_PARLAY_SIZE,
    BONUS_DAILY_CAP, MIN_BONUS_SCORE, MIN_BONUS_WIN_PROB,
)

PICK_LOG_PATH = str(_PICK_LOG_PATH_P)
DISCORD_GUARD_FILE = str(_DISCORD_GUARD_FILE_P)
logger = logging.getLogger(__name__)
BRAND_LOGO = "https://cdn.discordapp.com/attachments/1115840612915228727/1225636209221566625/JonnyParlaylogoRedBlack.png"

# ── Context research verdicts (display-only; written by engine/context_research.py) ─
_CTX_VERDICTS: dict = {}
_ctx_path = Path(__file__).parent.parent / "data" / "context_verdicts.json"
if _ctx_path.exists():
    try:
        for _v in json.loads(_ctx_path.read_text(encoding="utf-8")):
            _CTX_VERDICTS[_v["game"]] = _v
    except Exception:
        pass


# ============================================================
#  DISCORD POSTING FUNCTIONS
# ============================================================

# Set to True via --confirm flag — gates every Discord post behind a y/n prompt.
# A mutated module-global cannot be shared across a re-export (rebinding the name in
# run_picks would not touch this module's copy, which _confirm_post reads), so main()
# uses set_confirm_mode()/get_confirm_mode() instead of assigning the bare name.
_CONFIRM_MODE = False


def set_confirm_mode(value):
    """Enable/disable the y/n confirmation prompt before every Discord post."""
    global _CONFIRM_MODE
    _CONFIRM_MODE = bool(value)


def get_confirm_mode():
    """Return the current confirm-mode flag."""
    return _CONFIRM_MODE


def _confirm_post(label):
    """Prompt user before posting to Discord. Returns True to proceed, False to skip.
    Always returns True when _CONFIRM_MODE is off."""
    if not _CONFIRM_MODE:
        return True
    try:
        ans = input(f"\n  [Confirm] Post '{label}' to Discord? [y/n] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("\n  [Confirm] Skipping (no input).")
        return False
    return ans in ("y", "yes")


_DISCORD_GUARD_TTL_DAYS = 90


try:
    from discord_guard import (
        load_guard as _shared_load_guard,
        save_guard as _shared_save_guard,
        prune_guard as _shared_prune_guard,
        claim_post as _shared_claim_post,
        release_post as _shared_release_post,
        mark_posted as _shared_mark_posted,
    )
    _HAS_SHARED_GUARD = True
except ImportError:
    _HAS_SHARED_GUARD = False


def _prune_discord_guard(guard):
    """Drop guard keys older than _DISCORD_GUARD_TTL_DAYS (based on embedded YYYY-MM-DD token)."""
    from datetime import datetime, timedelta
    # Pin cutoff to ET (pick-log date convention). Strip tzinfo so the compare
    # against naive strptime dates stays valid (audit H-1).
    cutoff = datetime.now(ZoneInfo("America/New_York")).replace(tzinfo=None) - timedelta(days=_DISCORD_GUARD_TTL_DAYS)
    pruned = {}
    for key, val in guard.items():
        keep = True
        for p in key.split(":"):
            if len(p) == 10 and p[4] == "-" and p[7] == "-":
                try:
                    dt = datetime.strptime(p, "%Y-%m-%d")
                    if dt < cutoff:
                        keep = False
                    break
                except ValueError:
                    continue
        if keep:
            pruned[key] = val
    return pruned


def _load_discord_guard():
    """Load the Discord post de-dup registry from disk. Returns {} on miss."""
    # Delegate to shared cross-process-safe helper if available
    if _HAS_SHARED_GUARD:
        return _shared_load_guard()
    try:
        with open(DISCORD_GUARD_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_discord_guard(guard):
    """Persist the Discord post de-dup registry atomically with TTL pruning."""
    # Delegate to shared cross-process-safe helper if available
    if _HAS_SHARED_GUARD:
        _shared_save_guard(guard)
        return
    try:
        atomic_write_json(DISCORD_GUARD_FILE, _prune_discord_guard(guard))
    except Exception as e:
        logger.warning(f"[Discord] Guard write failed: {e}")
        # Best-effort fallback — prune stale entries before writing
        try:
            guard = _prune_discord_guard(guard)
            with open(DISCORD_GUARD_FILE, "w", encoding="utf-8") as f:
                json.dump(guard, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
        except Exception:
            pass


def _discord_already_posted(key):
    """Return True if this guard key has already been posted (read-only check).
    Use _discord_claim_post for the atomic test-and-set before posting.
    """
    return bool(_load_discord_guard().get(key))


def _discord_mark_posted(key):
    """Record a successful Discord post (legacy RMW wrapper).
    Prefer _discord_claim_post for new call sites.
    """
    if _HAS_SHARED_GUARD:
        _shared_mark_posted(key)
        return
    g = _load_discord_guard()
    g[key] = True
    _save_discord_guard(g)


def _discord_claim_post(key):
    """Atomic test-and-set: claim a guard key before posting.
    Returns True if THIS run just claimed key (caller should post).
    Returns False if already claimed (caller should skip).
    Fixes audit C3 (TOCTOU) + H3 (suppress_ping guard omission).
    """
    if _HAS_SHARED_GUARD:
        return _shared_claim_post(key)
    # Fallback: best-effort non-atomic claim (no discord_guard module)
    if _load_discord_guard().get(key):
        return False
    _discord_mark_posted(key)
    return True


def _discord_release_post(key):
    """Un-claim a guard key after a failed webhook post so the next run
    can retry. No-op if the key is not set. Do NOT call after success.
    """
    if _HAS_SHARED_GUARD:
        _shared_release_post(key)
        return
    g = _load_discord_guard()
    if key in g:
        del g[key]
        _save_discord_guard(g)


def _notify_post_failure(label, guard_key=None, err=None):
    """Release the guard claim (if any) and fire the fallback webhook alert.
    Swallows all errors — a broken notifier must never mask the real failure.
    Fixes audit H5 / F6.4 / F6.7.
    """
    if guard_key:
        _discord_release_post(guard_key)
    try:
        from webhook_fallback import notify_fallback
        notify_fallback(label, err=err)
    except Exception as _e:
        logger.warning(f"[fallback-notifier] raised (suppressed): {_e}")


def _webhook_post(url, payload, retries=3, backoff=2.0, label="Discord post"):
    """POST a JSON payload to a Discord webhook URL. Retries on failure with exponential backoff.
    If _CONFIRM_MODE is True, prompts for y/n confirmation before sending.

    Audit M-4 / M-16 (closed Apr 20 2026): retry_after parsed via
    http_utils.retry_after_secs so a non-JSON / empty 429 body can't
    crash the poster, and the Retry-After header is preferred over the
    (Discord-specific) JSON body. Canonical UA from default_headers()
    stamps every outbound webhook post.
    """
    if not url:
        logger.warning("[Discord] Webhook URL not configured — skipping post.")
        return False
    if not _confirm_post(label):
        print(f"  [Confirm] ⏭️  Skipped: {label}")
        return False
    import requests as _req
    from http_utils import default_headers as _dh, retry_after_secs as _ras
    headers = _dh()
    for attempt in range(1, retries + 1):
        try:
            # H5/H22: split timeout (connect=5s, read=10s); ReadTimeout is NOT
            # retried because the POST body has already been sent — a retry risks
            # a duplicate Discord post.
            r = _req.post(url, json=payload, headers=headers, timeout=(5, 10))
            if r.status_code == 429:
                retry_after = _ras(r, default=backoff)
                logger.warning(f"[Discord] Rate limited — waiting {retry_after:.1f}s (attempt {attempt}/{retries})")
                time.sleep(retry_after)
                continue
            r.raise_for_status()
            return True
        except _req.exceptions.ReadTimeout as e:
            # H5: never retry ReadTimeout — POST body was already delivered.
            logger.error(f"[Discord] ReadTimeout (body already sent, NOT retrying): {e}")
            return False
        except Exception as e:
            if attempt < retries:
                wait = backoff ** attempt
                logger.warning(f"[Discord] Post failed (attempt {attempt}/{retries}): {e} — retrying in {wait:.1f}s")
                time.sleep(wait)
            else:
                logger.error(f"[Discord] Post failed after {retries} attempts: {e}")
    return False


def build_premium_embed(premium, mode, today, suppress_ping=False, sport=None):
    """Build the Discord embed payload for the premium card (#premium-portfolio)."""
    emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]
    mode_emoji = {"Default": "⚖️", "Aggressive": "🔥", "Conservative": "🛡️"}
    picks = premium[:5]
    total_u = sum(p.get("size", 0) for p in picks)

    now_et = datetime.now(ZoneInfo("America/New_York")).strftime("%I:%M %p ET")
    mode_str = f"{mode_emoji.get(mode, '⚖️')} {mode}"
    sport_label = f" · {sport}" if sport else ""

    lines = [f"**{len(picks)} picks | {total_u:.2f}u | {mode_str}**\n"]
    for i, p in enumerate(picks):
        e = emojis[i] if i < len(emojis) else "•"
        stat = p.get("stat", "")
        direction = p["direction"].upper()
        line_val = p["line"]
        odds_str = fmt_odds(p["odds"])
        book_str = display_book(p["book"])
        size = p.get("size", 0)
        game = p.get("game", "")
        edge_str = f"+{p['adj_edge']*100:.1f}%"
        score_str = f"{p.get('pick_score', 0):.1f}"
        tier = p.get("tier", "")

        # Game-line stats use full player field; props use last name only
        _SUFFIXES = {"jr.", "sr.", "ii", "iii", "iv"}
        if stat == "TEAM_TOTAL":
            pick_label = f"{p['player']} {direction} {line_val}"
        elif stat in ("ML_FAV", "ML_DOG"):
            pick_label = p["player"]  # already "TEAM ML", e.g. "MON ML"
        elif stat in ("SPREAD", "TOTAL", "F5_TOTAL", "F5_SPREAD", "F5_ML"):
            pick_label = f"{p['player']} {direction} {line_val}"
        elif stat in ("NRFI", "YRFI"):
            matchup = p.get("team_abbrev") or p.get("game", "")
            pick_label = f"{matchup} {stat}" if matchup else stat
        elif stat == "GOLF_WIN":
            pick_label = f"{p['player']} {direction}"
        elif stat == "PARLAY":
            pick_label = (p.get("player") or "Parlay").strip()
        else:
            parts = (p.get("player") or "").split() or [""]
            last = parts[-1]
            if last.lower() in _SUFFIXES and len(parts) >= 2:
                last = parts[-2]
            pick_label = f"{last} {direction} {line_val} {stat}"

        inj_flag    = " 🔄" if p.get("injury_trigger") else ""
        _ctx = _CTX_VERDICTS.get(game, {})
        _ctx_tag = "  [CTX+]" if _ctx.get("verdict") == "confirms" else ("  [CTX-]" if _ctx.get("verdict") == "fades" else "")
        lines.append(f"{e} **{pick_label}**{_ctx_tag} | {odds_str} | {book_str} | **{size:.2f}u**{inj_flag}")
        lines.append(f"╰ {game} | Edge {edge_str} | Score {score_str}")

    lines.append(f"\n━━━━━━━━━━━━━━━━")
    lines.append(f"**Total:** {total_u:.2f}u")

    return {
        "username": "PicksByJonny",
        "content": "" if suppress_ping else "@everyone",
        "embeds": [{
            "title": f"🔒 Premium Portfolio{sport_label} — {today}",
            "description": "\n".join(lines),
            "color": 0xFFD700,  # Gold
            "thumbnail": {"url": BRAND_LOGO},
            "footer": {"text": f"{BRAND_TAGLINE} · {now_et}"},
        }]
    }


def build_potd_embed(potd, today, sport=None):
    """Build the standalone POTD embed (posted after premium card, same channel)."""
    stat = potd.get("stat", "")
    direction = potd["direction"].upper()
    line_val = potd["line"]
    game = potd.get("game", "")
    odds_str = fmt_odds(potd["odds"])
    book_str = display_book(potd["book"])
    size = potd.get("size", 0)
    edge_str = f"+{potd['adj_edge']*100:.1f}%"
    score_str = f"{potd.get('pick_score', 0):.1f}"
    tier = potd.get("tier", "")
    proj = potd.get("proj", 0)
    now_et = datetime.now(ZoneInfo("America/New_York")).strftime("%I:%M %p ET")

    _SUFFIXES = {"jr.", "sr.", "ii", "iii", "iv"}
    if stat == "TEAM_TOTAL":
        pick_label = f"{potd['player']} {direction} {line_val}"
    elif stat in ("ML_FAV", "ML_DOG"):
        pick_label = potd["player"]
    elif stat in ("SPREAD", "TOTAL", "F5_TOTAL", "F5_SPREAD", "F5_ML"):
        pick_label = f"{potd['player']} {direction} {line_val}"
    elif stat in ("NRFI", "YRFI"):
        matchup = potd.get("team_abbrev") or potd.get("game", "")
        pick_label = f"{matchup} {stat}" if matchup else stat
    elif stat == "GOLF_WIN":
        pick_label = f"{potd['player']} {direction}"
    elif stat == "PARLAY":
        pick_label = (potd.get("player") or "Parlay").strip()
    else:
        parts = (potd.get("player") or "").split() or [""]
        last = parts[-1]
        if last.lower() in _SUFFIXES and len(parts) >= 2:
            last = parts[-2]
        pick_label = f"{last} {direction} {line_val} {stat}"

    _ctx = _CTX_VERDICTS.get(game, {})
    _ctx_tag = " [CTX+]" if _ctx.get("verdict") == "confirms" else (" [CTX-]" if _ctx.get("verdict") == "fades" else "")
    description = (
        f"━━━━━━━━━━━━━━━━\n"
        f"**{pick_label}**{_ctx_tag}\n"
        f"{potd['player']} | {game}\n"
        f"━━━━━━━━━━━━━━━━\n\n"
        f"{odds_str} @ {book_str} | **{size:.2f}u**\n\n"
        f"Edge: **{edge_str}** | Score: **{score_str}**\n"
        f"Proj: {proj:.1f} {stat.lower()}"
    )

    sport_suffix = f" · {sport}" if sport else ""
    return {
        "username": "PicksByJonny",
        "embeds": [{
            "title": f"⭐ Pick of the Day{sport_suffix} — {today}",
            "description": description,
            "color": 0xFF4500,  # OrangeRed
            "thumbnail": {"url": BRAND_LOGO},
            "footer": {"text": f"{BRAND_TAGLINE} · {now_et}"},
        }]
    }


def post_to_discord(premium, mode, today, suppress_ping=False, force=False, sport=None):
    """Post the premium card + standalone POTD embed to #premium-portfolio.

    Uses discord_posted.json guard keys to prevent double-posts on re-run.
    sport: sorted sport key e.g. "MLB", "NBA", "NBA+NHL" — enables separate
    MLB + NBA cards on the same day. Guard key: premium_card:{sport}:{date}.
    force=True (--force-card) releases the guard keys before claiming so the
    card re-posts even if it was already sent today.
    """
    if not premium:
        print("  [Discord] No premium picks — skipping premium post.")
        return

    _sport_label = sport or "MULTI"

    # Premium card
    premium_key = f"premium_card:{_sport_label}:{today}"
    if force:
        _discord_release_post(premium_key)
    if not _discord_claim_post(premium_key):
        print(f"  [Discord] ⏭️  Premium card already posted for {_sport_label} {today} — skipping")
    else:
        payload = build_premium_embed(premium, mode, today, suppress_ping=suppress_ping, sport=sport)
        if _webhook_post(DISCORD_WEBHOOK_URL, payload, label="premium card"):
            print(f"  [Discord] ✅ Premium card posted ({len(premium[:5])} picks) [{_sport_label}]")
        else:
            _notify_post_failure("premium_card", guard_key=premium_key)

    # POTD — separate embed, same channel, same webhook.
    # premium[0] is guaranteed non-KILLSHOT (KILLSHOTs are excluded from premium).
    potd_key = f"potd:{_sport_label}:{today}"
    if force:
        _discord_release_post(potd_key)
    if not _discord_claim_post(potd_key):
        print(f"  [Discord] ⏭️  POTD already posted for {_sport_label} {today} — skipping")
    else:
        potd = premium[0]
        potd_payload = build_potd_embed(potd, today, sport=sport)
        if _webhook_post(DISCORD_WEBHOOK_URL, potd_payload, label=f"POTD: {potd['player']} {potd['stat']}"):
            print(f"  [Discord] ✅ POTD posted: {potd['player']} {potd['stat']}")
        else:
            _discord_release_post(potd_key)


# size_daily_lay lives in sizing.py (imported above with size_bonus_pick).


def post_daily_lay(alt_spread_parlay, today, suppress_ping=False, save=True):
    """Post the alt spread parlay to #daily-lay channel."""
    if not DISCORD_ALT_PARLAY_WEBHOOK or not alt_spread_parlay:
        print("  [Discord] No alt spread parlay — skipping #daily-lay post.")
        return
    legs = alt_spread_parlay.get("legs", [])
    if not legs:
        return

    combined_prob = alt_spread_parlay.get("combined_prob", 0)
    # M26: also compute book-implied combined prob for transparency (gate uses model prob)
    book_implied_combined = 1.0
    for _leg in legs:
        _leg_odds = _leg.get("real_odds")
        if _leg_odds is not None:
            book_implied_combined *= implied_prob(_leg_odds)
    if combined_prob < MIN_DAILY_LAY_PROB:
        print(f"  [Discord] Daily Lay combined prob {combined_prob*100:.1f}% < {MIN_DAILY_LAY_PROB*100:.0f}% threshold — skipping weak parlay.")
        return

    guard_key = f"daily_lay:{today}"
    if not _discord_claim_post(guard_key):
        print(f"  [Discord] ⏭️  Daily Lay already posted for {today} — skipping")
        return

    now_et = datetime.now(ZoneInfo("America/New_York")).strftime("%I:%M %p ET")
    book = alt_spread_parlay.get("book", "N/A")
    parlay_odds_raw = alt_spread_parlay.get("parlay_odds", 0)
    parlay_odds = fmt_odds(parlay_odds_raw)
    n_legs = len(legs)
    DAILY_LAY_SIZE = size_daily_lay(combined_prob, parlay_odds_raw)
    print(f"  [daily-lay-sizing] Kelly sizing: combined_prob={combined_prob:.3f} (book-implied={book_implied_combined:.3f}) odds={parlay_odds} → {DAILY_LAY_SIZE:.2f}u")

    leg_lines = [f"{n_legs}-leg alt spread parlay @ {book}\n"]
    for i, leg in enumerate(legs, 1):
        team = leg.get("team", "")
        spread = leg.get("alt_spread", 0)
        sign = "+" if spread > 0 else ""
        leg_odds = fmt_odds(leg.get("real_odds", 0)) if leg.get("real_odds") else "N/A"
        cover_pct = f"{leg.get('alt_cover_prob', 0)*100:.0f}%"
        game = leg.get("game", "")
        leg_lines.append(f"**Leg {i}** | {team} {sign}{spread:.1f} (alt) | {leg_odds} | {cover_pct} cover")
        leg_lines.append(f"╰ {game}")

    leg_lines.append(f"\n━━━━━━━━━━━━━━━━")
    leg_lines.append(f"**{parlay_odds}** combined | **{DAILY_LAY_SIZE:.2f}u**")

    payload = {
        "username": "PicksByJonny",
        "content": "" if suppress_ping else "@everyone",
        "embeds": [{
            "title": f"🎲 Daily Lay — {today}",
            "description": "\n".join(leg_lines),
            "color": 0x9B59B6,
            "footer": {"text": f"{BRAND_TAGLINE} · {now_et}"}
        }]
    }
    if _webhook_post(DISCORD_ALT_PARLAY_WEBHOOK, payload, label=f"daily lay ({n_legs} legs @ {parlay_odds})"):
        print(f"  [Discord] ✅ Daily Lay posted to #daily-lay ({n_legs} legs @ {parlay_odds})")
        _log_daily_lay(alt_spread_parlay, today, save=save)
    else:
        _notify_post_failure("daily_lay", guard_key=guard_key)


def post_longshot(safest6_parlay, today, suppress_ping=False, save=True):
    """Post the longshot 6-leg parlay to #longshot (or #bonus-drops fallback)."""
    if not safest6_parlay:
        print("  [Discord] No longshot parlay — skipping.")
        return
    legs = safest6_parlay.get("legs", [])
    if len(legs) < 6:
        return

    webhook = DISCORD_LONGSHOT_WEBHOOK or DISCORD_BONUS_WEBHOOK
    if not webhook:
        print("  [Discord] DISCORD_LONGSHOT_WEBHOOK not configured — skipping longshot post.")
        return

    guard_key = f"longshot:{today}"
    if not _discord_claim_post(guard_key):
        print(f"  [Discord] ⏭️  Longshot already posted for {today} — skipping")
        return

    now_et = datetime.now(ZoneInfo("America/New_York")).strftime("%I:%M %p ET")
    combined_prob = safest6_parlay.get("combined_prob", 0)
    parlay_odds   = fmt_odds(safest6_parlay.get("parlay_odds", 0))
    book_display  = display_book(safest6_parlay.get("book", "")) or "N/A"

    _GL_STAT_CODES = {
        "ML_FAV", "ML_DOG", "SPREAD", "TOTAL", "TEAM_TOTAL",
        "F5_ML", "F5_SPREAD", "F5_TOTAL", "NRFI", "YRFI",
    }
    leg_lines = [f"6-leg longshot — safest model picks\n"]
    for i, leg in enumerate(legs, 1):
        dir_word  = "Over" if str(leg.get("direction", "")).lower() == "over" else "Under"
        wp_pct    = f"{leg.get('win_prob', 0)*100:.0f}%"
        stat      = leg.get("stat", "")
        # Game-line picks: player description already contains the market name;
        # appending the raw stat code (e.g. TEAM_TOTAL, F5_TOTAL) is redundant.
        stat_suffix = "" if stat in _GL_STAT_CODES else f" {stat}"
        leg_lines.append(
            f"**Leg {i}** | {leg.get('player','')} {dir_word} {leg.get('line','')}"
            f"{stat_suffix} | {wp_pct}"
        )
    leg_lines.append(f"\n━━━━━━━━━━━━━━━━")
    leg_lines.append(f"**{parlay_odds}** combined | **{LONGSHOT_SIZE:.2f}u** | {combined_prob*100:.1f}% model prob | 📍 {book_display}")

    payload = {
        "username": "PicksByJonny",
        "content": "" if suppress_ping else "@everyone",
        "embeds": [{
            "title": f"🎯 Longshot — {today}",
            "description": "\n".join(leg_lines),
            "color": 0xE74C3C,
            "footer": {"text": f"{BRAND_TAGLINE} · {now_et}"}
        }]
    }
    if _webhook_post(webhook, payload, label=f"longshot (6-leg @ {parlay_odds})"):
        print(f"  [Discord] ✅ Longshot posted ({parlay_odds})")
        if save:
            _log_longshot(safest6_parlay, today)
    else:
        _discord_release_post(guard_key)


def post_value_parlay(value_parlay, today, suppress_ping=False, save=True):
    """Post the 5-leg value parlay to #bonus-drops (fires only when longshot cannot build)."""
    if not value_parlay:
        return
    legs = value_parlay.get("legs", [])
    if len(legs) < 5:
        return

    webhook = DISCORD_BONUS_WEBHOOK
    if not webhook:
        print("  [Discord] DISCORD_BONUS_WEBHOOK not configured — skipping value parlay post.")
        return

    guard_key = f"value_parlay:{today}"
    if not _discord_claim_post(guard_key):
        print(f"  [Discord] ⏭️  Value parlay already posted for {today} — skipping")
        return

    now_et = datetime.now(ZoneInfo("America/New_York")).strftime("%I:%M %p ET")
    combined_prob = value_parlay.get("combined_prob", 0)
    parlay_odds   = fmt_odds(value_parlay.get("parlay_odds", 0))
    book_display  = display_book(value_parlay.get("book", "")) or "N/A"

    _GL_STAT_CODES = {
        "ML_FAV", "ML_DOG", "SPREAD", "TOTAL", "TEAM_TOTAL",
        "F5_ML", "F5_SPREAD", "F5_TOTAL", "NRFI", "YRFI",
    }
    leg_lines = [f"5-leg value parlay — safest model picks\n"]
    for i, leg in enumerate(legs, 1):
        dir_word  = "Over" if str(leg.get("direction", "")).lower() == "over" else "Under"
        wp_pct    = f"{leg.get('win_prob', 0)*100:.0f}%"
        stat      = leg.get("stat", "")
        stat_suffix = "" if stat in _GL_STAT_CODES else f" {stat}"
        leg_lines.append(
            f"**Leg {i}** | {leg.get('player','')} {dir_word} {leg.get('line','')}"
            f"{stat_suffix} | {wp_pct}"
        )
    leg_lines.append(f"\n━━━━━━━━━━━━━━━━")
    leg_lines.append(f"**{parlay_odds}** combined | **{VALUE_PARLAY_SIZE:.2f}u** | {combined_prob*100:.1f}% model prob | 📍 {book_display}")

    payload = {
        "username": "PicksByJonny",
        "content": "" if suppress_ping else "@everyone",
        "embeds": [{
            "title": f"💎 Value Parlay — {today}",
            "description": "\n".join(leg_lines),
            "color": 0x2ECC71,
            "footer": {"text": f"{BRAND_TAGLINE} · {now_et}"}
        }]
    }
    if _webhook_post(webhook, payload, label=f"value parlay (5-leg @ {parlay_odds})"):
        print(f"  [Discord] ✅ Value parlay posted ({parlay_odds})")
        if save:
            _log_value_parlay(value_parlay, today)
    else:
        _discord_release_post(guard_key)


def _card_guard_should_block_logging(card_was_up: bool, no_discord: bool, force_card: bool) -> bool:
    """Return True iff the premium-card guard should suppress log_picks.

    The card guard exists for *Discord* dedup — preventing a duplicate
    premium-card post when the day's card has already shipped.  Two flags
    bypass it because they decouple logging from the Discord post:

    * ``--no-discord`` (shadow / research / dry-run): no Discord post will
      ever happen, so the guard has no purpose.  Without this bypass the
      shadow scheduled task silently logs zero rows whenever the live
      SaberSim card has already fired earlier in the day — the original
      symptom that motivated audit item A4 (2026-05-06).
    * ``--force-card``: explicit operator override (existing behavior;
      kept here for clarity and so the helper covers both paths).
    """
    if not card_was_up:
        return False
    if no_discord or force_card:
        return False
    return True


def _card_already_posted_today(today_str, sport_key=None):
    """Return True if a premium card for this sport has already been posted today.

    sport_key: sorted sport string e.g. "MLB", "NBA", "NBA+NHL". If None, checks
    all sport keys (backward compat). Per-sport keys allow running MLB + NBA
    separately on the same day without the second run being blocked.

    H14: previous implementation scanned pick_log.csv for 'primary' run_type
    rows, which conflates card posting with KILLSHOT pick logging — a run that
    only qualified KILLSHOT picks would log them as run_type='primary' and
    incorrectly suppress the card on the next run.

    Now uses the discord guard key as the source of truth. Falls back to
    pick_log scan (checking card_slot is set) when the guard cannot be read.
    """
    try:
        guard = _load_discord_guard()
        if sport_key:
            # Check sport-keyed guard (new format) first, then legacy global key
            if guard.get(f"premium_card:{sport_key}:{today_str}"):
                return True
        else:
            # Backward compat: check any sport key for today
            prefix = f"premium_card:"
            for k, v in guard.items():
                if k.endswith(f":{today_str}") and k.startswith(prefix) and v:
                    return True
        # Guard says not posted — also check pick_log as a safety net.
        # Require card_slot to be non-blank: only the card posting path sets
        # card_slot; KILLSHOT-only runs leave it blank (H14 fix).
        log_path = Path(PICK_LOG_PATH)
        if not log_path.exists():
            return False
        with _pick_log_lock(log_path):
            with open(log_path, "r", newline="", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
        return any(
            r.get("date") == today_str
            and r.get("run_type") in {"primary", "", None}
            and r.get("card_slot", "").strip() not in ("", "0")
            and (not sport_key or r.get("sport", "") in sport_key.split("+"))
            for r in rows
        )
    except Exception as e:
        logger.warning("_is_card_posted: unexpected error — returning False: %s", e)
        return False


def _units_bet_today(today_str):
    """Sum units already bet today across all run_types (for cross-run 12u cap).

    Reads pick_log.csv and sums the size column for today's rows. Manual picks
    are excluded (they're tracked separately and don't count against daily cap).
    Returns 0.0 on any error so the cap falls back to session-only behaviour.
    """
    try:
        log_path = Path(PICK_LOG_PATH)
        if not log_path.exists():
            return 0.0
        with _pick_log_lock(log_path):
            with open(log_path, "r", newline="", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
        total = sum(
            float(r.get("size", 0) or 0)
            for r in rows
            if r.get("date") == today_str
            and r.get("run_type", "").lower() != "manual"
        )
        return round(total, 4)
    except Exception as e:
        logger.warning("_units_bet_today: unexpected error — returning 0.0: %s", e)
        return 0.0


def post_extras_to_discord(qualified, run_id=None, save=True):
    """Post a single bonus drop to #bonus-drops.

    Selection rules (Option A from handoff):
      - "New" = pick not already in pick_log.csv under run_type='bonus' OR 'primary' for today
      - Single highest Pick Score new pick only
      - Hard cap: 5 bonus posts per calendar day (checked via pick_log.csv)

    run_id: optional identifier for this run (defaults to current timestamp string).
    """
    if not DISCORD_BONUS_WEBHOOK:
        print("  [Discord] DISCORD_BONUS_WEBHOOK not configured — skipping bonus post.")
        return

    today_str = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
    # ET for run_id so timestamp stays consistent with today_str (audit H-1).
    run_id = run_id or datetime.now(ZoneInfo("America/New_York")).strftime("%H%M%S")

    # --- Check daily cap ---
    log_path = Path(PICK_LOG_PATH)
    bonus_today_count = 0
    already_posted_keys = set()  # (player_lower, stat, line, direction)

    if log_path.exists() and log_path.stat().st_size > 0:
        # Shared lock — don't race a mid-flush CLV/grader write (audit H-8).
        with _pick_log_lock(log_path):
            with open(log_path, "r", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get("date", "") != today_str:
                        continue
                    # Count bonus posts
                    if row.get("run_type", "").lower() == "bonus":
                        bonus_today_count += 1
                    # Only block re-posting if: was on the premium card OR already a bonus drop
                    # Qualified picks that didn't make the card ARE eligible for bonus
                    is_card_pick = row.get("card_slot", "").strip() not in ("", None)
                    is_bonus = row.get("run_type", "").lower() == "bonus"
                    if is_card_pick or is_bonus:
                        already_posted_keys.add((
                            row.get("player", "").strip().lower(),
                            row.get("stat", "").strip(),
                            str(row.get("line", "")).strip(),
                            row.get("direction", "").strip().lower(),
                        ))

    if bonus_today_count >= BONUS_DAILY_CAP:
        print(f"  [Discord] Bonus cap reached ({BONUS_DAILY_CAP}/day) — skipping bonus post.")
        return

    # --- Find single highest-score new pick ---
    eligible = []
    for p in qualified:
        key = (
            p.get("player", "").strip().lower(),
            p.get("stat", "").strip(),
            str(p.get("line", "")).strip(),
            p.get("direction", "").strip().lower(),
        )
        if (key not in already_posted_keys
                and p.get("pick_score") is not None
                and p.get("pick_score", 0) >= MIN_BONUS_SCORE
                and p.get("win_prob", 0) >= MIN_BONUS_WIN_PROB
                and p.get("tier") != "KILLSHOT"):
            eligible.append(p)

    if not eligible:
        print("  [Discord] No new picks available for bonus drop.")
        return

    best = max(eligible, key=lambda p: p.get("pick_score", 0))

    # --- Re-size the bonus pick with VAKE variance + tier multipliers ---
    # The pick entered here with base sizing (from size_picks_base), which caps
    # at 1.25u for any edge ≥ 9% regardless of tier. A standalone bonus drop
    # should track Premium tier economics (T3 ≈ 0.50u, T2 ≈ 1.00u), so recompute.
    # This overwrites the pick's `size` field, which _log_bonus_pick then reads.
    _prev_size = best.get("size")
    resized = size_bonus_pick(best)
    if resized is None:
        # Audit H-9: VAKE math rolled below the tier floor — refuse to ship
        # a dust bet. size_bonus_pick already logged the reason. We don't
        # try the next-best pick here: the bonus selector already filtered
        # on MIN_BONUS_SCORE and MIN_BONUS_WIN_PROB, so the top eligible
        # pick failing sizing is a real signal that today's bonus slate is
        # too weak. Skip for the day rather than drilling down into the
        # scraps.
        logger.warning("Bonus drop skipped — top eligible pick failed H-9 sizing gate.")
        return
    best["size"] = resized
    if _prev_size is not None and _prev_size != best["size"]:
        print(f"  [Discord] Bonus sizing: {best['tier']} {best['stat']} "
              f"{_prev_size:.2f}u → {best['size']:.2f}u (VAKE)")

    # M6: check 12u session cap AFTER sizing (uses the actual resized value, not base size)
    _units_so_far = _units_bet_today(today_str)
    _bonus_est = best.get("size", 1.25)
    if _units_so_far + _bonus_est > 12.0:
        print(f"  [Discord] Bonus drop skipped — session cap: {_units_so_far:.2f}u logged + {_bonus_est:.2f}u bonus would exceed 12u.")
        return

    # --- Build embed ---
    dir_word = "Over" if best["direction"] == "over" else "Under"
    team = best.get("team_abbrev", "")
    lines = [
        f"**{best['player']} ({team}) {dir_word} {best['line']} {best['stat']}**",
        f"{fmt_odds(best['odds'])} @ {display_book(best['book'])} — **{best.get('size',0):.2f}u**",
        "",
        f"Win: **{fmt_pct(best['win_prob'])}** | Edge: **{fmt_pct(best['adj_edge'])}** | Score: **{best.get('pick_score',0):.1f}**",
        f"Proj: {best['proj']:.1f} | {best['game']}",
    ]
    payload = {
        "username": "PicksByJonny",
        "embeds": [{
            "title": "💎 Bonus Drop",
            "description": "\n".join(lines),
            "color": 0x00BFFF,  # Deep sky blue
            "footer": {"text": BRAND_TAGLINE},
        }]
    }

    if _webhook_post(DISCORD_BONUS_WEBHOOK, payload, label=f"bonus drop: {best['player']} {best['stat']}"):
        print(f"  [Discord] ✅ Bonus drop posted: {best['player']} {best['stat']} (Score: {best.get('pick_score',0):.1f})")
        # Log this bonus pick to pick_log.csv with run_type='bonus'.
        # Discord post already succeeded — any log failure must NOT crash the run
        # or we end up with a ghost post and no ledger entry for grade_picks/CLV.
        try:
            _log_bonus_pick(best, run_id, today_str, save=save)
        except Exception as _log_err:
            logger.error(f"Bonus drop posted but logging failed: {_log_err}")
            logger.warning(f"Backfill manually: {best['player']} {best['stat']} {best['direction']} {best['line']} @ {best['odds']} ({best['book']})")


def build_killshot_embed(pick, today, suppress_ping=False):
    """Build a KILLSHOT embed for #killshot channel."""
    dir_word = "Over" if pick.get("direction") == "over" else "Under"
    team     = pick.get("team_abbrev", "")
    score    = pick.get("pick_score", 0)
    content  = "" if suppress_ping else "@everyone"

    _ctx = _CTX_VERDICTS.get(pick.get("game", ""), {})
    _ctx_tag = "  [CTX+]" if _ctx.get("verdict") == "confirms" else ("  [CTX-]" if _ctx.get("verdict") == "fades" else "")
    desc = "\n".join([
        f"**{pick['player']} ({team}) {dir_word} {pick['line']} {pick['stat']}**{_ctx_tag}",
        f"{fmt_odds(pick['odds'])} @ {display_book(pick['book'])} — **{pick.get('size', 0):.2f}u**",
        "",
        f"Win: **{fmt_pct(pick['win_prob'])}** | Edge: **{fmt_pct(pick['adj_edge'])}** | Score: **{score:.1f}**",
        f"Proj: {pick['proj']:.1f} | {pick['game']}",
    ])

    return {
        "username": "PicksByJonny",
        "content": content,
        "embeds": [{
            "title":       "⚡ KILLSHOT",
            "description": desc,
            "color":       0xFF0000,
            "thumbnail":   {"url": BRAND_LOGO},
            "footer":      {"text": f"{today} · {BRAND_TAGLINE} · high conviction only"},
        }]
    }


def post_killshots_to_discord(killshots, today, today_str, suppress_ping=False):
    """Post each KILLSHOT pick to #killshot channel.

    Uses per-pick guard keys (killshot:{date}:{player}:{stat}) so a rerun of
    run_picks.py doesn't re-fire pings for already-posted KILLSHOTS. Guard
    is only marked on real (non-test) successful posts.
    """
    if not killshots:
        return
    if not DISCORD_KILLSHOT_WEBHOOK:
        print("  [Discord] DISCORD_KILLSHOT_WEBHOOK not configured — skipping KILLSHOT posts.")
        return
    for pick in killshots:
        ks_key = f"killshot:{today_str}:{pick.get('player','').strip().lower()}:{pick.get('stat','')}:{pick.get('direction','')}:{pick.get('line','')}"
        if not _discord_claim_post(ks_key):
            print(f"  [Discord] ⏭️  KILLSHOT already posted: {pick['player']} {pick['stat']} — skipping")
            continue
        payload = build_killshot_embed(pick, today, suppress_ping=suppress_ping)
        if _webhook_post(DISCORD_KILLSHOT_WEBHOOK, payload, label=f"KILLSHOT: {pick['player']} {pick['stat']}"):
            print(f"  [Discord] 🎯 KILLSHOT posted: {pick['player']} {pick['stat']} ({pick.get('size', 0):.2f}u · Score {pick.get('pick_score', 0):.1f})")
        else:
            _notify_post_failure(
                f"killshot:{pick.get('player','')}:{pick.get('stat','')}",
                guard_key=ks_key,
            )
            print(f"  [Discord] ⚠ KILLSHOT post failed: {pick['player']} {pick['stat']}")
