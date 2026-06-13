"""Cross-process file lock for pick_log writes.

Extracted from run_picks.py (extract-and-re-export refactor, Step 1) and
re-imported there so existing call sites and `from run_picks import ...` keep
resolving. Imports only {stdlib, filelock} — never run_picks or the other
extracted modules.
"""
from contextlib import contextmanager

# filelock (hard dep, shared with capture_clv.py + grade_picks.py).
# Audit C-1: filelock is a required dependency. Fallback removed — a missing
# lock silently re-enables the CLV daemon / grader race conditions.
try:
    from filelock import FileLock, Timeout as _FileLockTimeout
except ImportError as e:
    raise ImportError(
        "filelock is required for pick_log/Discord-guard safety. "
        "Install it: pip install filelock --break-system-packages"
    ) from e


@contextmanager
def _pick_log_lock(log_path, timeout=30):
    """Acquire exclusive lock on pick_log to prevent CLV daemon/grader races.

    CRIT-1: on timeout, raises _FileLockTimeout — never yields without the lock.
    Yielding without the lock would allow a concurrent CLV daemon write to race
    the pick_log append, potentially corrupting the ledger.
    """
    lock_path = str(log_path) + ".lock"
    with FileLock(lock_path, timeout=timeout):
        yield
    # _FileLockTimeout propagates naturally if the lock can't be acquired.
