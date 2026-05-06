"""D1 redistribution + 240-min constraint + Vegas-vs-240 diagnostics.

Captures the state of injury_parser.redistribute_minutes() and
nba_projector.run_projections()'s lineup-protected constraint, and writes a
JSON sidecar per game_date to data/diagnostics/redistrib_YYYY-MM-DD.json.

The Vegas-vs-240 diagnostic (H1 audit, 2026-05-06) captures the per-team
state immediately before and immediately after constrain_team_totals() to
quantify how often the Vegas constraint deflates top-5 minutes after the
240-min lineup-protection logic has set them. Output sidecar:
data/diagnostics/vegas_constraint_YYYY-MM-DD.json.

Toggles via env vars (independent):
    JONNYPARLAY_DIAG_REDISTRIB=1        # redistribution + 240-min
    JONNYPARLAY_DIAG_VEGAS_VS_240=1     # constrain_team_totals pre/post

When disabled, every public function is a no-op and zero behavior change is
introduced into the projection pipeline. Logging-only — does not mutate
projections, overrides, or the constraint logic.

Buffer lifecycle:
    redistribute_minutes() writes out_player + recipient records.
    run_projections() writes pre + post constraint records, then flushes.
    flush(game_date) writes the redistrib_DATE.json file and clears the buffer.
    constrain_team_totals() writes pre/post Vegas records.
    flush_vegas(game_date) writes vegas_constraint_DATE.json and clears.
"""
from __future__ import annotations

import json
import logging
import os
from collections import defaultdict
from pathlib import Path
from typing import Optional

from paths import DATA_DIR

log = logging.getLogger("diagnostics")


def _is_enabled() -> bool:
    return os.environ.get("JONNYPARLAY_DIAG_REDISTRIB", "").lower() in ("1", "true", "yes")


def _new_team_record() -> dict:
    return {
        "out_players": [],
        "recipients": [],
        "ewma_only_sum": None,
        "override_sum": None,
        "pre_constraint_total": None,
        "core_total": None,
        "bench_total": None,
        "bench_scale": None,
        "post_constraint_total": None,
    }


_buffer: dict[int, dict] = defaultdict(_new_team_record)


def enabled() -> bool:
    """True iff JONNYPARLAY_DIAG_REDISTRIB is set."""
    return _is_enabled()


def reset() -> None:
    """Clear the buffer.  Idempotent; safe to call when disabled."""
    _buffer.clear()


def record_out_player(team_id: int, pid: int, pos: str, avg_min: float) -> None:
    if not _is_enabled():
        return
    _buffer[int(team_id)]["out_players"].append({
        "pid": int(pid),
        "pos": pos or "",
        "avg_min": round(float(avg_min), 2),
    })


def record_recipient(team_id: int, pid: int, pos_group: str,
                     avg_min: float, bump: float,
                     pre_override: Optional[float], post_override: float,
                     hit_cap: bool) -> None:
    if not _is_enabled():
        return
    _buffer[int(team_id)]["recipients"].append({
        "pid": int(pid),
        "pos_group": pos_group,
        "avg_min": round(float(avg_min), 2),
        "bump": round(float(bump), 2),
        "pre_override": None if pre_override is None else round(float(pre_override), 2),
        "post_override": round(float(post_override), 2),
        "hit_cap": bool(hit_cap),
    })


def record_team_pre_constraint(team_id: int, *, ewma_only_sum: float,
                               override_sum: float, pre_constraint_total: float,
                               core_total: float, bench_total: float) -> None:
    if not _is_enabled():
        return
    rec = _buffer[int(team_id)]
    rec["ewma_only_sum"] = round(float(ewma_only_sum), 2)
    rec["override_sum"] = round(float(override_sum), 2)
    rec["pre_constraint_total"] = round(float(pre_constraint_total), 2)
    rec["core_total"] = round(float(core_total), 2)
    rec["bench_total"] = round(float(bench_total), 2)


def record_team_post_constraint(team_id: int, bench_scale: float,
                                post_constraint_total: float) -> None:
    if not _is_enabled():
        return
    rec = _buffer[int(team_id)]
    rec["bench_scale"] = round(float(bench_scale), 4)
    rec["post_constraint_total"] = round(float(post_constraint_total), 2)


def flush(game_date: str) -> Optional[Path]:
    """Write the buffer as JSON sidecar and clear it.

    Returns the output path on success, None when disabled or buffer is empty.
    """
    if not _is_enabled():
        return None
    if not _buffer:
        return None
    out_dir = DATA_DIR / "diagnostics"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"redistrib_{game_date}.json"
    payload = {str(tid): rec for tid, rec in _buffer.items()}
    out_file.write_text(json.dumps(payload, indent=2, sort_keys=True))
    log.info("D1: wrote redistribution diagnostics to %s (%d teams)",
             out_file, len(payload))
    reset()
    return out_file


# ---------------------------------------------------------------------------
# H1 (audit 2026-05-06) — Vegas team-total constraint pre/post diagnostic
# ---------------------------------------------------------------------------

_VEGAS_BUFFER: dict[int, dict] = {}


def _is_vegas_enabled() -> bool:
    return os.environ.get("JONNYPARLAY_DIAG_VEGAS_VS_240", "").lower() in ("1", "true", "yes")


def enabled_vegas_vs_240() -> bool:
    """True iff JONNYPARLAY_DIAG_VEGAS_VS_240 is set."""
    return _is_vegas_enabled()


def reset_vegas() -> None:
    """Clear the vegas diag buffer.  Idempotent; safe when disabled."""
    _VEGAS_BUFFER.clear()


def record_team_pre_vegas(team_id: int, projections: list) -> None:
    """Snapshot pre-Vegas per-player proj_min and proj_pts for one team.

    Call inside constrain_team_totals() at the top of the per-team loop,
    before any mutation. ``projections`` is the team's list of player dicts.
    Players are ordered descending by proj_min so top-5 == first five
    entries in every captured array.
    """
    if not _is_vegas_enabled():
        return
    sorted_desc = sorted(
        projections,
        key=lambda x: float(x.get("proj_min", 0.0) or 0.0),
        reverse=True,
    )
    pids: list[int] = []
    mins: list[float] = []
    pts: list[float] = []
    for p in sorted_desc:
        pid_raw = p.get("player_id", -1)
        try:
            pid = int(pid_raw) if pid_raw is not None else -1
        except (TypeError, ValueError):
            pid = -1
        pids.append(pid)
        mins.append(float(p.get("proj_min", 0.0) or 0.0))
        pts.append(float(p.get("proj_pts", 0.0) or 0.0))

    _VEGAS_BUFFER[int(team_id)] = {
        "n_players": len(sorted_desc),
        "all_pids": pids,
        "all_min_pre": [round(m, 2) for m in mins],
        "all_pts_pre": [round(x, 2) for x in pts],
        "team_min_total_pre": round(sum(mins), 2),
        "proj_pts_sum_pre": round(sum(pts), 2),
        "top5_pids": pids[:5],
        "top5_min_pre": [round(m, 2) for m in mins[:5]],
    }


def record_team_post_vegas(team_id: int, *, raw_scale: float,
                           clipped_scale: float, vegas_total: float,
                           projections: list) -> None:
    """Capture post-Vegas state for one team.

    Call at the end of each per-team iteration in constrain_team_totals(),
    AFTER the (no-)mutation step. Fires whether or not the team was actually
    scaled (short-circuited cases captured for completeness).
    """
    if not _is_vegas_enabled():
        return
    rec = _VEGAS_BUFFER.get(int(team_id))
    if rec is None:
        # Pre-hook didn't fire — defensive no-op rather than raise.
        return
    by_pid: dict[int, dict] = {}
    for p in projections:
        pid_raw = p.get("player_id", -1)
        try:
            pid = int(pid_raw) if pid_raw is not None else -1
        except (TypeError, ValueError):
            pid = -1
        by_pid[pid] = p

    rec["raw_scale"] = round(float(raw_scale), 4)
    rec["clipped_scale"] = round(float(clipped_scale), 4)
    rec["vegas_total"] = round(float(vegas_total), 2)
    rec["all_min_post"] = [
        round(float((by_pid.get(pid, {}) or {}).get("proj_min", 0.0) or 0.0), 2)
        for pid in rec["all_pids"]
    ]
    rec["top5_min_post"] = rec["all_min_post"][:5]


def flush_vegas(game_date: str) -> Optional[Path]:
    """Write the vegas diag buffer as JSON sidecar and clear it.

    Returns the output path on success, None when disabled or buffer is empty.
    """
    if not _is_vegas_enabled():
        return None
    if not _VEGAS_BUFFER:
        return None
    out_dir = DATA_DIR / "diagnostics"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"vegas_constraint_{game_date}.json"
    payload = {str(tid): rec for tid, rec in _VEGAS_BUFFER.items()}
    out_file.write_text(json.dumps(payload, indent=2, sort_keys=True))
    log.info("D1 (vegas): wrote vegas-constraint diagnostics to %s (%d teams)",
             out_file, len(payload))
    reset_vegas()
    return out_file
