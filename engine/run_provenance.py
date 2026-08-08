"""run_provenance.py -- which code produced the last live pick run?

WHY THIS EXISTS, AND WHY IT IS NOT A COPY OF EdgeModel'S CHECK
EdgeModel has a long-running BlockingScheduler that imports its modules once and then holds
them for days, so a merge there is dormant until the process restarts. That gap swallowed three
shipped fixes and is detected by EdgeModel's chk_code_version_drift.

JonnyParlay has no such process. The CLV daemon self-terminates once captures are done and
`run_picks` is per-invocation, so every run already loads current code. **The stale-daemon
failure cannot occur here, and porting that check as-is would guard a problem this repo does
not have.**

The gap it DOES have is provenance, and it is more severe because this is the live card:
`pick_log.csv` carries a `model_version` column that is EMPTY on all 390 graded picks and all
26,985 calibration rows, and `run_id` is populated on 1 of 390. So for the only real-money
record in the system there is no way to establish which code priced it.

`model_version` is deliberately NOT reused for this. Its schema meaning is a SOURCE tag --
blank for the live source, 'edgemodel' when a pick came from EdgeModel (pick_log_writers.py) --
and overloading it would corrupt the one provenance field that already works.

WHAT THIS RECORDS, AND THE QUESTION IT ANSWERS
On each pick run: the git SHA, whether the tree was dirty, the run id, and the timestamp, into
`data/run_provenance.json`. The question is "did the code change since the run that produced
these picks?" -- which matters before comparing today's results against yesterday's, and before
attributing any performance change to a code change.

Self-contained by design. It does NOT import EdgeModel (that interface is documented
offline-only, with no stability contract) and does NOT live in pricing_core, whose stated
design intent is stateless pure math with zero I/O. Forty duplicated lines is the correct trade
against violating either boundary.
"""
from __future__ import annotations

import json
import logging
import subprocess
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger("run_provenance")

UNKNOWN = "unknown"
_SHA_LEN = 12
_GIT_TIMEOUT_S = 5
_REPO = Path(__file__).resolve().parent
PROVENANCE_PATH = _REPO.parent / "data" / "run_provenance.json"


def _git(*args):
    """Run git in this repo. None on any failure at all."""
    try:
        out = subprocess.run(("git", "-C", str(_REPO), *args), capture_output=True,
                             text=True, timeout=_GIT_TIMEOUT_S, check=False)
    except Exception as exc:  # noqa: BLE001 - git missing, hung, sandboxed, anything
        log.debug("run_provenance: git %s failed (%s)", args, exc)
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def code_version() -> str:
    """`<sha12>`, `<sha12>.dirty`, or `unknown`.

    A failed `git status` reads `.unknowndirty` rather than being treated as clean -- a failed
    check is not evidence of a clean tree, and picks produced from a modified checkout must not
    masquerade as the committed SHA.
    """
    sha = _git("rev-parse", "HEAD")
    if not sha:
        return UNKNOWN
    sha = sha[:_SHA_LEN]
    status = _git("status", "--porcelain")
    if status is None:
        return f"{sha}.unknowndirty"
    return f"{sha}.dirty" if status else sha


def record_run(run_id: str, run_type: str = "primary", path: Path | None = None):
    """Record the code that produced this pick run. Never raises.

    Overwrites rather than appends: the question is which code produced the MOST RECENT run,
    and a growing file would need parsing rules the reader does not have. Fail-soft because a
    provenance write must never take down a live pick run.
    """
    target = path or PROVENANCE_PATH
    ver = code_version()
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps({
            "code_version": ver,
            "run_id": run_id,
            "run_type": run_type,
            "recorded_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }, indent=2), encoding="utf-8")
        log.info("run_provenance: run %s produced by %s", run_id, ver)
        return ver
    except Exception as exc:  # noqa: BLE001 - never block a live run
        log.warning("run_provenance: could not record run %s (%s) -- the health check will "
                    "report 'cannot tell' rather than a false OK", run_id, exc)
        return None


def read_last_run(path: Path | None = None):
    """The recorded provenance dict, or None if never recorded / unreadable.

    None means "cannot tell", which is NOT "no drift". Callers must report the difference
    rather than defaulting to pass -- an unread field that defaults to success is precisely how
    model_version stayed empty on 390 live picks without anyone noticing.
    """
    target = path or PROVENANCE_PATH
    try:
        return json.loads(target.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 - absent or malformed
        return None


def drift_status(path: Path | None = None):
    """('OK'|'WARN'|'STALE', message) comparing the last run's code to what is on disk now."""
    rec = read_last_run(path)
    if rec is None:
        return "WARN", ("no run provenance recorded yet -- cannot tell which code produced the "
                        "last pick run (run picks once to establish a baseline)")
    was, now = rec.get("code_version", UNKNOWN), code_version()
    if UNKNOWN in (was, now):
        return "WARN", f"version unresolvable (run={was}, disk={now}) -- git metadata missing"
    if was == now:
        return "OK", f"last run {rec.get('run_id')} produced by {was}, unchanged since"
    return "STALE", (f"code CHANGED since the last pick run: run {rec.get('run_id')} was "
                     f"produced by {was}, disk is now {now} -- results from that run are not "
                     f"attributable to current code")
