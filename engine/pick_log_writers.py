"""Pick-log CSV writers (primary/bonus/parlays/blocked/candidates) + legs-JSON helpers.

Named pick_log_writers (not pick_log_io — that module already houses the canonical
locked *readers*). Extracted from run_picks.py (extract-and-re-export refactor, Step 7) and
re-imported there so existing call sites and `from run_picks import ...` keep
resolving. Imports only {stdlib, pick_log_lock, paths, market_config, book_names,
pick_log_schema, thresholds, sizing} — never run_picks or the other extracted
modules.
"""
import os
import csv
import logging
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from pick_log_lock import _pick_log_lock
from paths import (
    PICK_LOG_PATH as _PICK_LOG_PATH_P,
    PICK_LOG_BLOCKED_PATH as _PICK_LOG_BLOCKED_PATH_P,
)
from market_config import _BLOCKED_LOG_SKIP_GATES, _BLOCKED_LOG_COLS
from book_names import norm_book as _norm_book
from pick_log_schema import (
    CANONICAL_HEADER,
    LIVE_SOURCE as _LIVE_SOURCE,
    normalize_american_odds as _normalize_odds,
    normalize_size as _normalize_size,
    normalize_proj as _normalize_proj,
    normalize_edge as _normalize_edge,
    normalize_is_home as _normalize_is_home,
    write_schema_sidecar as _write_schema_sidecar,
)
from thresholds import LONGSHOT_SIZE, VALUE_PARLAY_SIZE
from sizing import size_daily_lay

logger = logging.getLogger("jonnyparlay")

PICK_LOG_PATH = str(_PICK_LOG_PATH_P)
PICK_LOG_BLOCKED_PATH = str(_PICK_LOG_BLOCKED_PATH_P)


def log_blocked_pick(pick):
    """Append one row to pick_log_blocked.csv for a gate-blocked pick.

    Skips suspension gates (G_SOG_SUSPENDED, G_HA_SUSPENDED, G_RA_DISABLED) —
    those block by policy, not by structural signal we want to audit.
    Also skips picks that actually passed (gate_result == "PASS").
    """
    gate = pick.get("gate_result", "")
    if not gate or gate == "PASS" or gate in _BLOCKED_LOG_SKIP_GATES:
        return
    path = Path(PICK_LOG_BLOCKED_PATH)
    write_header = not path.exists() or path.stat().st_size == 0
    today = datetime.now(ZoneInfo("America/New_York")).date().isoformat()
    row = {
        "date": today,
        "sport": pick.get("sport", ""),
        "player": pick.get("player", ""),
        "stat": pick.get("stat", ""),
        "line": pick.get("line", ""),
        "direction": pick.get("direction", ""),
        "odds": pick.get("odds", ""),
        "edge": round(pick.get("adj_edge", pick.get("edge", 0)), 4),
        "win_prob": round(pick.get("win_prob", pick.get("adj_wp", 0)), 4),
        "gate_result": gate,
    }
    with open(path, "a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=_BLOCKED_LOG_COLS)
        if write_header:
            writer.writeheader()
        writer.writerow(row)

def log_candidates(candidates, mode, today_str):
    """Write the full gate-passing pick pool to pick_log_candidates.csv for formula backtesting.

    Each row is one qualifying pick (before apply_caps / premium selection) with:
      - All standard pick fields (wp, edge, tier, pick_score under new formula)
      - candidate_rank: rank by current pick_score (1 = highest)
      - score_old_6040: score under old 60/40 formula (pre-refactor reference)
      - score_5050: score under 50/50 formula
    """
    from paths import DATA_DIR
    path = DATA_DIR / "pick_log_candidates.csv"
    fieldnames = [
        "date", "run_time", "sport", "player", "team", "stat", "line", "direction",
        "proj", "win_prob", "edge", "odds", "book", "tier", "pick_score", "size",
        "game", "mode", "candidate_rank", "score_old_6040", "score_5050",
        "cold_start_subtype", "injury_trigger",
    ]
    now = datetime.now(ZoneInfo("America/New_York"))
    run_time = now.strftime("%H:%M")
    write_header = not path.exists() or path.stat().st_size == 0

    ranked = sorted(candidates, key=lambda p: p.get("pick_score", 0), reverse=True)

    def _old_score(p):
        wp_n = (p.get("win_prob", 0.5) * 100 - 50) / 25 * 100
        e_n  = (p.get("adj_edge", p.get("edge", 0)) * 100) / 20 * 100
        return 0.60 * wp_n + 0.40 * e_n

    def _5050_score(p):
        wp_n = (p.get("win_prob", 0.5) * 100 - 50) / 25 * 100
        e_n  = (p.get("adj_edge", p.get("edge", 0)) * 100) / 15 * 100
        # Tier mult retired 2026-06-06 (Plan 9 §9F) — BM shrinkage upstream.
        return 0.50 * wp_n + 0.50 * e_n

    with _pick_log_lock(path):
        with open(path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            if write_header:
                writer.writeheader()
            for rank, p in enumerate(ranked, 1):
                edge = p.get("adj_edge", p.get("edge", 0))
                writer.writerow({
                    "date":               today_str,
                    "run_time":           run_time,
                    "sport":              p.get("sport", ""),
                    "player":             p.get("player", ""),
                    "team":               p.get("team_abbrev", ""),
                    "stat":               p.get("stat", ""),
                    "line":               p.get("line", ""),
                    "direction":          p.get("direction", ""),
                    "proj":               round(p.get("proj", 0), 2),
                    "win_prob":           round(p.get("win_prob", 0), 4),
                    "edge":               round(edge, 4),
                    "odds":               p.get("odds", ""),
                    "book":               p.get("book", ""),
                    "tier":               p.get("tier", ""),
                    "pick_score":         round(p.get("pick_score", 0), 2),
                    "size":               p.get("size", 0),
                    "game":               p.get("game", ""),
                    "mode":               mode,
                    "candidate_rank":     rank,
                    "score_old_6040":     round(_old_score(p), 2),
                    "score_5050":         round(_5050_score(p), 2),
                    "cold_start_subtype": p.get("cold_start_subtype", ""),
                    "injury_trigger":     p.get("injury_trigger", False),
                })
    print(f"  [--log-candidates] Logged {len(ranked)} candidates → {path.name}")

def log_picks(qualified, mode, log_path_override=None, premium_picks=None, run_type="primary"):
    """Append all qualified picks to pick_log.csv for backtesting.
    Columns: date, run_time, sport, player, team, stat, line, direction,
             proj, win_prob, edge, odds, book, tier, pick_score, size, game, mode
    Actual result column left blank — fill in manually or automate later.

    premium_picks: list of up to 5 picks that were on the posted premium card.
                   These get card_slot=1-5; all others get card_slot=''.

    run_type: schema run_type for logged rows (default "primary").
              Shadow call sites pass run_type explicitly via the run_type param.

    DEDUP: On repeat runs, skips picks that already exist in the log for today
    (matched on date + player + stat + line + direction). Updates odds/size/proj
    on the existing row if the pick already exists but values changed.
    """
    log_path = log_path_override if log_path_override else Path(PICK_LOG_PATH)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    _now_et  = datetime.now(ZoneInfo("America/New_York"))
    run_date = _now_et.strftime("%Y-%m-%d")
    run_time = _now_et.strftime("%H:%M")
    # v5 provenance: run_id ties these rows to the run; source per market comes from
    # the resolver's coverage_manifest decision (LIVE_SOURCE while every market is
    # dormant/'shadow'; 'edgemodel'/'blend:<w>' once a market is promoted). Fail-soft.
    run_id = f"{run_date}T{run_time}"
    try:
        import resolver as _resolver
        _src_map = _resolver.source_map()
        _live_source = _resolver.LIVE_SOURCE
    except Exception:
        _src_map, _live_source = {}, "sabersim"

    def _src_for(pick):
        return _src_map.get(((pick.get("sport") or "").upper(),
                             (pick.get("stat") or "").upper()), _live_source)

    # All logs (live and shadow) use cross-run dedup keyed on
    # (date, player, stat, line, direction). A same-day re-run with the
    # same CSV logs 0 new picks; a direction flip logs a new row.

    # Build card slot lookup: (player_lower, stat, line, direction) -> slot number
    card_slot_map = {}
    if premium_picks:
        for i, p in enumerate(premium_picks[:5], start=1):
            key = (
                p.get("player", "").strip().lower(),
                p.get("stat", "").strip(),
                str(p.get("line", "")).strip(),
                p.get("direction", "").strip().lower(),
            )
            card_slot_map[key] = i

    # Canonical schema lives in pick_log_schema.py (audit H-3).
    # Local alias kept so downstream code below can keep reading `HEADER`.
    HEADER = CANONICAL_HEADER

    # Read-modify-write the pick_log under a single lock so the read, the
    # conditional header rewrite, and the append can't be torn apart by a
    # concurrent capture_clv.py flush or manual writer (audit H-8).
    with _pick_log_lock(log_path):
        # Load existing rows and build a set of today's pick keys
        existing_rows = []
        existing_keys = set()
        old_header = None
        if log_path.exists() and log_path.stat().st_size > 0:
            with open(log_path, "r", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                old_header = reader.fieldnames or []
                for row in reader:
                    existing_rows.append(row)
                    if row.get("date", "") == run_date:
                        # Dedup key is a tuple of date, player, stat, line, direction.
                        key = (
                            row.get("date", ""),
                            row.get("player", "").strip().lower(),
                            row.get("stat", "").strip(),
                            str(row.get("line", "")).strip(),
                            row.get("direction", "").strip().lower(),
                        )
                        existing_keys.add(key)

        # If header has changed (new columns added), rewrite the file with updated header.
        # Atomic replace: write to tmp, fsync, then os.replace. Prevents truncation-to-empty
        # if the engine is killed mid-rewrite (audit H-5).
        if old_header and set(HEADER) != set(old_header):
            tmp_path = log_path.with_suffix(log_path.suffix + ".tmp")
            try:
                with open(tmp_path, "w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=HEADER, extrasaction="ignore")
                    writer.writeheader()
                    for row in existing_rows:
                        writer.writerow(row)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp_path, log_path)
            except Exception:
                # Clean up orphaned tmp on failure so we don't accumulate cruft
                try:
                    tmp_path.unlink(missing_ok=True)
                except OSError:
                    pass
                raise
            print(f"  📋 Updated pick_log header: added {set(HEADER) - set(old_header)}")

        # Split qualified picks into new vs already-logged
        new_picks = []
        skipped = 0
        for p in qualified:
            key = (
                run_date,
                p.get("player", "").strip().lower(),
                p.get("stat", "").strip(),
                str(p.get("line", "")).strip(),
                p.get("direction", "").strip().lower(),
            )
            if key in existing_keys:
                skipped += 1
            else:
                new_picks.append(p)
                existing_keys.add(key)  # prevent intra-run dupes too

        # Append only new picks
        write_header = not log_path.exists() or log_path.stat().st_size == 0
        if new_picks:
            with open(log_path, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                if write_header:
                    writer.writerow(HEADER)
                for p in new_picks:
                    if not p.get("player") or not p.get("stat"):
                        logger.warning(f"Skipping incomplete pick (missing player/stat): {p}")
                        continue
                    slot_key = (
                        p.get("player", "").strip().lower(),
                        p.get("stat", "").strip(),
                        str(p.get("line", "")).strip(),
                        p.get("direction", "").strip().lower(),
                    )
                    card_slot = card_slot_map.get(slot_key, "")
                    _src = _src_for(p)
                    writer.writerow([
                        run_date,
                        run_time,
                        run_type,           # schema run_type (default "primary"; shadow callers override)
                        p.get("sport", ""),
                        p.get("player", ""),
                        p.get("team_abbrev", ""),
                        p.get("stat", ""),
                        p.get("line", ""),
                        p.get("direction", ""),
                        # M-11: 2-decimal canonical proj string.
                        _normalize_proj(p.get("proj", 0)),
                        f"{p.get('win_prob', 0):.4f}",
                        # M-12: 4-decimal canonical edge (decimal, not %).
                        _normalize_edge(p.get("adj_edge", 0)),
                        # Odds normalized to canonical sign-prefixed form
                        # (PICK_LOG_AUDIT H-3 — prevents analyze_picks.py
                        # crashing on bare "105" and silently computing 0 profit).
                        _normalize_odds(p.get("odds", "")),
                        _norm_book(p.get("book", "")),
                        p.get("tier", ""),
                        f"{(p.get('pick_score') or 0):.1f}",
                        # M-10: canonical 2-decimal size ("0.50" not "0.5").
                        _normalize_size(p.get("size", 0)),
                        p.get("game", ""),
                        mode,
                        "",  # result — blank, fill in after games
                        "",  # closing_odds — filled by capture_clv.py
                        "",  # clv — filled by capture_clv.py
                        card_slot,  # 1-5 if on premium card, blank otherwise
                        # M-3: canonical "True"/"False"/"" for is_home — set for
                        # team-based stats, blank for props.
                        _normalize_is_home(p.get("is_home", ""), p.get("stat", "")),
                        p.get("context_verdict", ""),
                        p.get("context_reason", ""),
                        p.get("context_score", ""),
                        "",  # legs — blank for primary/bonus (F2.5: was missing, silently dropped)
                        # v4: pre-Platt over_p; blank for non-prop picks (game lines, parlays).
                        f"{p['over_p_raw']:.4f}" if p.get("over_p_raw") is not None else "",
                        # v5 provenance: source from the resolver decision, model tag, run id.
                        _src,
                        "edgemodel" if _src != _live_source else "",
                        run_id,
                        "",  # v6: clv_corrected — filled by capture_clv.py
                    ])
                # Commit to disk before releasing the outer lock (audit H-5).
                f.flush()
                os.fsync(f.fileno())

    if skipped > 0:
        print(f"\n  📝 Logged {len(new_picks)} new picks to {log_path} (skipped {skipped} duplicates from earlier run)")
    else:
        print(f"\n  📝 Logged {len(new_picks)} picks to {log_path}")

    # A3 / N3 (audit 2026-05-06): structured warning when a write produces
    # no new rows so a shadow daemon / scheduled-task review can spot a
    # silent no-op.  qualified_in distinguishes "input was empty (gates
    # filtered everything)" from "all dedup'd against earlier run".
    if len(new_picks) == 0:
        logger.warning(
            "log_picks: 0 new rows written to %s "
            "(qualified_in=%d, dedup_skipped=%d). "
            "If qualified_in>0 this is dedup blocking a re-run; "
            "if qualified_in=0 the upstream gate filtered everything.",
            log_path, len(qualified), skipped,
        )

    # M-13: refresh the schema sidecar on every successful write. Cheap
    # (< 1ms) and lets future readers verify the on-disk schema version
    # without sniffing column names.
    try:
        _write_schema_sidecar(log_path)
    except Exception as _sidecar_err:
        # Sidecar failure must never block pick logging — log and carry on.
        logger.warning(f"M-13 sidecar write failed for {log_path}: {_sidecar_err}")

def _daily_lay_legs_json(legs):
    """Serialise daily_lay legs to the canonical `legs` JSON column format.

    Each entry: {team, spread, game, cover_prob, odds}
    The grader reads team+spread from here instead of parsing the `game` field
    as a string (audit H9 / F2.6 / F4.5).
    Returns empty string on any failure.
    """
    import json as _json
    try:
        out = []
        for leg in legs:
            out.append({
                "team":       str(leg.get("team", "")),
                "spread":     float(leg.get("alt_spread", 0)),
                "game":       str(leg.get("game", "")),
                "cover_prob": float(leg.get("alt_cover_prob", leg.get("cover_prob", 0))),
                "odds":       int(round(leg.get("real_odds", 0))),
            })
        return _json.dumps(out, separators=(",", ":"))
    except Exception:
        return ""

def _log_daily_lay(alt_spread_parlay, today_str, save=True):
    """Append the Daily Lay parlay to pick_log.csv as run_type='daily_lay'."""
    if not save:
        return
    log_path = Path(PICK_LOG_PATH)
    if not log_path.exists():
        logger.warning(f"[DailyLay] pick_log.csv not found at {PICK_LOG_PATH} — daily lay not logged.")
        return
    legs = alt_spread_parlay.get("legs", [])
    if not legs:
        return
    run_time = datetime.now(ZoneInfo("America/New_York")).strftime("%H:%M")
    parlay_odds = alt_spread_parlay.get("parlay_odds", 0)
    book = _norm_book(alt_spread_parlay.get("book", ""))

    # Single row summarising the whole parlay
    legs_desc = " / ".join(
        f"{leg.get('team','')} {'+' if leg.get('alt_spread',0)>0 else ''}{leg.get('alt_spread','')}"
        for leg in legs
    )
    rows_to_add = [{
        "date": today_str,
        "run_time": run_time,
        "run_type": "daily_lay",
        "sport": "",
        "player": f"Daily Lay {len(legs)}-leg",
        "team": "",
        "stat": "PARLAY",
        "line": "",
        "direction": "cover",
        "proj": "",
        "win_prob": "",
        "edge": "",
        # Parlay odds normalized to canonical sign-prefixed form
        # (PICK_LOG_AUDIT H-3). Bare int would trip analyze_picks.py for any
        # positive parlay price (e.g. +540 → "540" → no sign prefix).
        "odds": _normalize_odds(int(round(parlay_odds))) if parlay_odds else "",
        "book": book,
        "tier": "DAILY_LAY",
        "pick_score": "",
        # M-10: canonical "0.50" not bare 0.50 — string sort / xlsx display
        # parity with other run_types.
        # Dynamic Kelly sizing — computed by size_daily_lay() in post_daily_lay().
        # Re-derive here from the same inputs so _log_daily_lay stays self-contained.
        "size": _normalize_size(size_daily_lay(
            alt_spread_parlay.get("combined_prob", 0),
            alt_spread_parlay.get("parlay_odds", 0),
        )),
        "game": legs_desc,
        "mode": "",
        "result": "",
        "closing_odds": "",
        "clv": "",
        "card_slot": "",
        "is_home": "",
        "context_verdict": "",
        "context_reason": "",
        "context_score": "",
        "legs": _daily_lay_legs_json(legs),
        "over_p_raw": "",
        # v5 provenance: parlay legs are live-source priced; aggregate row, no run_id.
        "source": _LIVE_SOURCE,
        "model_version": "",
        "run_id": "",
    }]

    try:
        # Acquire lock for the ENTIRE read-check-write cycle so the CLV daemon
        # can't rewrite pick_log.csv mid-operation (which is what truncated
        # the 2026-04-19 daily_lay row to 17 fields).
        with _pick_log_lock(log_path):
            with open(log_path, "r", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                existing = list(reader)

            # Check not already logged today
            already = any(
                r.get("date") == today_str and r.get("run_type") == "daily_lay"
                for r in existing
            )
            if already:
                return

            with open(log_path, "a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=CANONICAL_HEADER, extrasaction="ignore", restval="")
                for row in rows_to_add:
                    writer.writerow(row)
                # Commit to disk before releasing the outer lock (audit H-5).
                f.flush()
                os.fsync(f.fileno())
        print(f"  📝 Daily Lay logged ({len(rows_to_add)} legs)")
        # M-13: refresh sidecar after a successful daily-lay append.
        try:
            _write_schema_sidecar(log_path)
        except Exception as _sidecar_err:
            logger.warning(f"M-13 sidecar write failed for {log_path}: {_sidecar_err}")
    except Exception as e:
        logger.error(f"Daily Lay log failed: {e}")

def _legs_json(picks, sport_override=None):
    """Serialise a list of pick dicts to the canonical `legs` JSON string.

    Stores only the fields needed by the grader (player, direction, line,
    stat, sport, game). Returns "" on failure so callers never crash.
    """
    import json as _json
    try:
        out = []
        for p in picks:
            sport = sport_override or p.get("sport", "NBA")
            out.append({
                "player":    str(p.get("player", "")),
                "direction": str(p.get("direction", "")).lower(),
                "line":      float(p.get("line", 0)),
                "stat":      str(p.get("stat", "")),
                "sport":     sport,
                "game":      str(p.get("game", "")),
                "win_prob":  float(p.get("win_prob", p.get("fair_prob", 0))),
            })
        return _json.dumps(out, separators=(",", ":"))
    except Exception:
        return ""

def _log_longshot(safest6_parlay, today_str, save=True):
    """Append the longshot parlay to pick_log.csv as run_type='longshot'."""
    if not save:
        return
    log_path = Path(PICK_LOG_PATH)
    if not log_path.exists():
        return
    legs = safest6_parlay.get("legs", [])
    if not legs:
        return

    run_time    = datetime.now(ZoneInfo("America/New_York")).strftime("%H:%M")
    parlay_odds = safest6_parlay.get("parlay_odds", 0)
    legs_json   = _legs_json(legs)

    # Human-readable game field: first sport/game for context
    sports_seen = sorted({p.get("sport", "") for p in legs if p.get("sport", "")})
    def _longshot_leg_label(p):
        """Compact leg label for the longshot game field.
        Handles over/under props, ML (direction='win'), and spread (direction='cover')
        so game-line legs don't show confusing 'U0' when there is no meaningful line."""
        direction = str(p.get("direction", "")).lower()
        stat      = p.get("stat", "")
        line      = p.get("line", "")
        short     = p.get("player", "").split()[-1]
        if direction == "win":
            # ML leg: player name is e.g. "NYM ML" — drop the trailing "ML" word and show "NYM WIN"
            team_short = " ".join(p.get("player", "").split()[:-1]) or short
            return f"{team_short} WIN"
        if direction == "cover":
            sign = "+" if float(line or 0) > 0 else ""
            return f"{short} {sign}{line} {stat}"
        if stat in ("NRFI", "YRFI"):
            matchup = p.get("team_abbrev", "")
            return f"{matchup} {stat}" if matchup else stat
        # Standard over/under prop or TEAM_TOTAL
        dir_char = "O" if direction == "over" else "U"
        return f"{short} {dir_char}{line} {stat}"

    player_desc = " / ".join(_longshot_leg_label(p) for p in legs)

    row = {
        "date":            today_str,
        "run_time":        run_time,
        "run_type":        "longshot",
        "sport":           ",".join(sports_seen),
        "player":          f"Longshot {len(legs)}-leg",
        "team":            "",
        "stat":            "PARLAY",
        "line":            "",
        "direction":       "",
        "proj":            "",
        "win_prob":        f"{safest6_parlay.get('combined_prob', 0):.4f}",
        "edge":            "",
        "odds":            _normalize_odds(int(round(parlay_odds))) if parlay_odds else "",
        "book":            _norm_book(safest6_parlay.get("book", "")),
        "tier":            "LONGSHOT",
        "pick_score":      "",
        "size":            _normalize_size(LONGSHOT_SIZE),
        "game":            player_desc,
        "mode":            "",
        "result":          "",
        "closing_odds":    "",
        "clv":             "",
        "card_slot":       "",
        "is_home":         "",
        "context_verdict": "",
        "context_reason":  "",
        "context_score":   "",
        "legs":            legs_json,
        "over_p_raw":      "",
        # v5 provenance: parlay legs are live-source priced; aggregate row, no run_id.
        "source":          _LIVE_SOURCE,
        "model_version":   "",
        "run_id":          "",
    }

    try:
        with _pick_log_lock(log_path):
            with open(log_path, "r", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            already = any(
                r.get("date") == today_str and r.get("run_type") == "longshot"
                for r in rows
            )
            if already:
                print("  [pick_log] Longshot already logged today — skipping.")
                return
            with open(log_path, "a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=CANONICAL_HEADER, extrasaction="ignore", restval="")
                writer.writerow(row)
                f.flush()
                os.fsync(f.fileno())
        print(f"  📝 Longshot logged ({len(legs)} legs)")
        try:
            _write_schema_sidecar(log_path)
        except Exception as _se:
            logger.warning(f"M-13 sidecar write failed: {_se}")
    except Exception as e:
        logger.error(f"Longshot log failed: {e}")

def _log_value_parlay(value_parlay, today_str, save=True):
    """Append the value parlay to pick_log.csv as run_type='value_parlay'."""
    if not save:
        return
    log_path = Path(PICK_LOG_PATH)
    if not log_path.exists():
        return
    legs = value_parlay.get("legs", [])
    if not legs:
        return

    run_time    = datetime.now(ZoneInfo("America/New_York")).strftime("%H:%M")
    parlay_odds = value_parlay.get("parlay_odds", 0)
    legs_json   = _legs_json(legs)

    sports_seen = sorted({p.get("sport", "") for p in legs if p.get("sport", "")})
    def _value_parlay_leg_label(p):
        direction = str(p.get("direction", "")).lower()
        stat      = p.get("stat", "")
        line      = p.get("line", "")
        short     = p.get("player", "").split()[-1]
        if direction == "win":
            team_short = " ".join(p.get("player", "").split()[:-1]) or short
            return f"{team_short} WIN"
        if direction == "cover":
            sign = "+" if float(line or 0) > 0 else ""
            return f"{short} {sign}{line} {stat}"
        if stat in ("NRFI", "YRFI"):
            matchup = p.get("team_abbrev", "")
            return f"{matchup} {stat}" if matchup else stat
        dir_char = "O" if direction == "over" else "U"
        return f"{short} {dir_char}{line} {stat}"

    player_desc = " / ".join(_value_parlay_leg_label(p) for p in legs)

    row = {
        "date":            today_str,
        "run_time":        run_time,
        "run_type":        "value_parlay",
        "sport":           ",".join(sports_seen),
        "player":          f"Value Parlay {len(legs)}-leg",
        "team":            "",
        "stat":            "PARLAY",
        "line":            "",
        "direction":       "",
        "proj":            "",
        "win_prob":        f"{value_parlay.get('combined_prob', 0):.4f}",
        "edge":            "",
        "odds":            _normalize_odds(int(round(parlay_odds))) if parlay_odds else "",
        "book":            _norm_book(value_parlay.get("book", "")),
        "tier":            "LONGSHOT",
        "pick_score":      "",
        "size":            _normalize_size(VALUE_PARLAY_SIZE),
        "game":            player_desc,
        "mode":            "",
        "result":          "",
        "closing_odds":    "",
        "clv":             "",
        "card_slot":       "",
        "is_home":         "",
        "context_verdict": "",
        "context_reason":  "",
        "context_score":   "",
        "legs":            legs_json,
        "over_p_raw":      "",
        # v5 provenance: parlay legs are live-source priced; aggregate row, no run_id.
        "source":          _LIVE_SOURCE,
        "model_version":   "",
        "run_id":          "",
    }

    try:
        with _pick_log_lock(log_path):
            with open(log_path, "r", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            already = any(
                r.get("date") == today_str and r.get("run_type") == "value_parlay"
                for r in rows
            )
            if already:
                print("  [pick_log] Value parlay already logged today — skipping.")
                return
            with open(log_path, "a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=CANONICAL_HEADER, extrasaction="ignore", restval="")
                writer.writerow(row)
                f.flush()
                os.fsync(f.fileno())
        print(f"  📝 Value parlay logged ({len(legs)} legs)")
        try:
            _write_schema_sidecar(log_path)
        except Exception as _se:
            logger.warning(f"M-13 sidecar write failed: {_se}")
    except Exception as e:
        logger.error(f"Value parlay log failed: {e}")

def _log_bonus_pick(pick, run_id, today_str, save=True):
    """Append a bonus pick to pick_log.csv with run_type='bonus'."""
    if not save:
        return
    log_path = Path(PICK_LOG_PATH)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    run_time = datetime.now(ZoneInfo("America/New_York")).strftime("%H:%M")

    # Canonical schema (audit H-3). Using the exact same object as log_picks()
    # means header drift between the primary and bonus writers is impossible.
    BONUS_HEADER = CANONICAL_HEADER
    write_header = not log_path.exists() or log_path.stat().st_size == 0
    # v5 provenance: resolve this bonus pick's source from the coverage_manifest.
    try:
        import resolver as _resolver
        _bonus_live = _resolver.LIVE_SOURCE
        _bonus_src = _resolver.source_map().get(
            ((pick.get("sport") or "").upper(), (pick.get("stat") or "").upper()), _bonus_live)
    except Exception:
        _bonus_live = _bonus_src = "sabersim"
    with _pick_log_lock(log_path):
        with open(log_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=BONUS_HEADER, extrasaction="ignore")
            if write_header:
                writer.writeheader()
            writer.writerow({
                "date":       today_str,
                "run_time":   run_time,
                "run_type":   "bonus",
                "sport":      pick.get("sport", ""),
                "player":     pick.get("player", ""),
                "team":       pick.get("team_abbrev", ""),
                "stat":       pick.get("stat", ""),
                "line":       pick.get("line", ""),
                "direction":  pick.get("direction", ""),
                # M-11 / M-12 / M-10: canonical numeric formatting.
                "proj":       _normalize_proj(pick.get("proj", 0)),
                "win_prob":   f"{pick.get('win_prob', 0):.4f}",
                "edge":       _normalize_edge(pick.get("adj_edge", 0)),
                # Normalized to sign-prefixed form (PICK_LOG_AUDIT H-3).
                "odds":       _normalize_odds(pick.get("odds", "")),
                "book":       _norm_book(pick.get("book", "")),
                "tier":       pick.get("tier", ""),
                "pick_score": f"{pick.get('pick_score', 0):.1f}",
                "size":       _normalize_size(pick.get("size", 0)),
                "game":       pick.get("game", ""),
                "mode":       "",
                "result":     "",
                "closing_odds": "",
                "clv":        "",
                "card_slot":        "",  # blank for bonus picks
                # M-3: canonical "True"/"False"/"" for is_home.
                "is_home":          _normalize_is_home(pick.get("is_home", ""),
                                                        pick.get("stat", "")),
                "context_verdict":  pick.get("context_verdict", ""),
                "context_reason":   pick.get("context_reason", ""),
                "context_score":    pick.get("context_score", ""),
                # v4: pre-Platt over_p; blank if not carried through (e.g. legacy pick dict).
                "over_p_raw": f"{pick['over_p_raw']:.4f}" if pick.get("over_p_raw") is not None else "",
                # v5 provenance: source per market (resolver decision), model tag, run id.
                "source": _bonus_src,
                "model_version": "edgemodel" if _bonus_src != _bonus_live else "",
                "run_id": str(run_id) if run_id is not None else "",
            })
            # Commit to disk before releasing the outer lock (audit H-5).
            f.flush()
            os.fsync(f.fileno())

    # M-13: refresh sidecar after a successful bonus append.
    try:
        _write_schema_sidecar(log_path)
    except Exception as _sidecar_err:
        logger.warning(f"M-13 sidecar write failed for {log_path}: {_sidecar_err}")
