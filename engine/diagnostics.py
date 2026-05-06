"""D1 redistribution + 240-min constraint diagnostics.

Captures the state of injury_parser.redistribute_minutes() and
nba_projector.run_projections()'s lineup-protected constraint, and writes a
JSON sidecar per game_date to data/diagnostics/redistrib_YYYY-MM-DD.json.

Toggle via env var:
    JONNYPARLAY_DIAG_REDISTRIB=1

When disabled, every public function is a no-op and zero behavior change is
introduced into the projection pipeline. Logging-only — does not mutate
projections, overrides, or the constraint logic.

Buffer lifecycle:
    redistribute_minutes() writes out_player + recipient records.
    run_projections() writes pre + post constraint records, then flushes.
    flush(game_date) writes the JSON file and clears the buffer.
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
