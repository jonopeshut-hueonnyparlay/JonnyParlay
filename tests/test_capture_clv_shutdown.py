"""test_capture_clv_shutdown.py — regression tests for audit H-10.

Covers the graceful shutdown surface in capture_clv.py:
  - _request_shutdown flips the flag
  - _interruptible_sleep wakes early when the flag flips
  - _interruptible_sleep returns True for a full sleep (not interrupted)
  - _install_signal_handlers is idempotent and cross-platform safe
  - subprocess smoke test: SIGTERM while the daemon waits for picks → clean
    exit + released lockfile (POSIX only)

Run:
    python test_capture_clv_shutdown.py
    # or: python -m pytest test_capture_clv_shutdown.py -v
"""

import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

ENGINE_DIR = Path(__file__).resolve().parent / "engine"
sys.path.insert(0, str(ENGINE_DIR))

import capture_clv  # noqa: E402


def _reset_flag():
    capture_clv._shutdown_requested = False
    capture_clv._shutdown_signal_name = None


# ── Unit tests ────────────────────────────────────────────────────────────────

def test_handler_flips_flag():
    _reset_flag()
    assert capture_clv._shutdown_requested is False
    capture_clv._request_shutdown(signal.SIGTERM, None)
    assert capture_clv._shutdown_requested is True
    assert capture_clv._shutdown_signal_name == "SIGTERM"
    _reset_flag()


def test_interruptible_sleep_full_duration():
    """No signal → sleeps full duration and returns True."""
    _reset_flag()
    t0 = time.time()
    ret = capture_clv._interruptible_sleep(0.4, chunk_secs=0.1)
    elapsed = time.time() - t0
    assert ret is True, "full-duration sleep should return True"
    assert 0.35 <= elapsed <= 0.8, f"unexpected elapsed: {elapsed}"


def test_interruptible_sleep_wakes_on_flag():
    """Flag flip mid-sleep → returns False within ~1 chunk."""
    _reset_flag()

    def _trigger():
        time.sleep(0.15)
        capture_clv._request_shutdown(signal.SIGTERM, None)

    t = threading.Thread(target=_trigger)
    t.start()
    t0 = time.time()
    ret = capture_clv._interruptible_sleep(5.0, chunk_secs=0.1)
    elapsed = time.time() - t0
    t.join()

    assert ret is False, "interrupted sleep should return False"
    assert elapsed < 1.5, f"sleep did not wake fast enough: {elapsed}s"
    _reset_flag()


def test_interruptible_sleep_zero_duration():
    _reset_flag()
    assert capture_clv._interruptible_sleep(0) is True
    assert capture_clv._interruptible_sleep(-1) is True
    capture_clv._shutdown_requested = True
    # With flag already set, zero sleep returns False (signal already queued)
    assert capture_clv._interruptible_sleep(0) is False
    _reset_flag()


def test_install_signal_handlers_is_idempotent():
    """Calling twice must not raise."""
    capture_clv._install_signal_handlers()
    capture_clv._install_signal_handlers()
    # Verify SIGTERM handler is bound to our handler
    current = signal.getsignal(signal.SIGTERM)
    assert current is capture_clv._request_shutdown, f"SIGTERM not bound: {current}"


def test_second_signal_raises_systemexit():
    """Second signal must hard-exit (so Ctrl+C twice still kills a stuck daemon)."""
    _reset_flag()
    capture_clv._request_shutdown(signal.SIGTERM, None)  # first: flips flag
    try:
        capture_clv._request_shutdown(signal.SIGTERM, None)  # second: raises
    except SystemExit as e:
        assert e.code == 1
    else:
        raise AssertionError("second signal should have raised SystemExit")
    finally:
        # Restore handler since _request_shutdown reset SIGTERM to SIG_DFL
        try:
            signal.signal(signal.SIGTERM, signal.SIG_DFL)
        except (ValueError, OSError):
            pass
        _reset_flag()


# ── Subprocess smoke test (POSIX only) ────────────────────────────────────────

def test_subprocess_sigterm_releases_lock():
    """Spawn the daemon, let it enter the poll loop, SIGTERM it, verify:
      1. Process exits 0 within ~5s
      2. clv_daemon.lock is released (no stale lock blocks the next run)
      3. stderr has no unhandled traceback"""
    if os.name != "posix":
        print("  [skip] subprocess signal test is POSIX-only")
        return

    from filelock import FileLock, Timeout as FileLockTimeout

    repo = Path(__file__).resolve().parent.parent

    # Use a sandboxed lockfile so we never collide with a real host-side
    # daemon's lock (capture_clv.py honours JONNYPARLAY_DAEMON_LOCK).
    import tempfile
    tmpdir = tempfile.mkdtemp(prefix="clv-shutdown-test-")
    lock_path = Path(tmpdir) / "clv_daemon.lock"

    # Use a date with no picks so the daemon just sits in the "waiting" path.
    env = os.environ.copy()
    # Fake API key so secrets_config doesn't complain at import
    env.setdefault("ODDS_API_KEY", "test-key-noop")
    # Redirect daemon lockfile so we don't fight the real host-side daemon
    env["JONNYPARLAY_DAEMON_LOCK"] = str(lock_path)
    # Shrink poll interval so it actually sleeps in interruptible chunks
    # (not strictly required, but makes the test faster).
    # We'll send SIGTERM while it's sleeping.

    proc = subprocess.Popen(
        [sys.executable, "-u", str(repo / "engine" / "capture_clv.py"),
         "--date", "2099-12-31"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        cwd=str(repo),
    )

    # Wait for the daemon to reach the poll loop. Detect via stdout marker
    # ("Lock acquired" banner) rather than lockfile existence, because on some
    # filesystems a 0-byte stale lockfile pre-exists. We drain stdout on a
    # thread so the pipe doesn't fill and block the child.
    startup_output: list[str] = []
    startup_ready = threading.Event()

    def _drain():
        for line in iter(proc.stdout.readline, b""):
            startup_output.append(line.decode(errors="replace"))
            if b"Lock acquired" in line or b"No picks logged yet" in line:
                startup_ready.set()

    drainer = threading.Thread(target=_drain, daemon=True)
    drainer.start()

    if not startup_ready.wait(timeout=10):
        proc.kill()
        proc.communicate()
        raise AssertionError(
            "daemon never reached poll loop — startup output was:\n"
            + "".join(startup_output)
        )

    # Give it a beat to enter the interruptible sleep
    time.sleep(1.0)

    proc.send_signal(signal.SIGTERM)

    # Wait for the process to exit without competing with the drain thread for
    # the stdout pipe (communicate() would race the drainer and eat the
    # shutdown-acknowledgement line).
    try:
        rc = proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        raise AssertionError("daemon did not exit within 15s of SIGTERM")

    # Drain thread naturally exits on EOF after the child closes its stdout.
    drainer.join(timeout=5)
    stdout = "".join(startup_output).encode()
    stderr = proc.stderr.read() if proc.stderr else b""
    assert rc == 0, f"daemon exited non-zero ({rc}).\nstderr:\n{stderr.decode()}"

    # Stderr must be clean (no uncaught traceback). Allow prints to stderr but
    # no "Traceback (most recent call last):"
    err = stderr.decode()
    assert "Traceback" not in err, f"unhandled traceback on shutdown:\n{err}"

    # Lockfile must be releasable (either unlinked, or acquirable fresh)
    try:
        new_lock = FileLock(str(lock_path), timeout=0.5)
        new_lock.acquire()
        new_lock.release()
    except FileLockTimeout:
        raise AssertionError(
            f"clv_daemon.lock still held after SIGTERM — daemon did not release "
            f"its single-instance lock on graceful shutdown"
        )

    # stdout should mention the shutdown path
    out = stdout.decode()
    assert "Shutdown requested" in out or "received" in out, \
        f"daemon did not acknowledge shutdown in stdout:\n{out}"

    # Cleanup
    import shutil
    try:
        shutil.rmtree(tmpdir, ignore_errors=True)
    except Exception:
        pass


# ── Fallback runner ───────────────────────────────────────────────────────────

def _run_all():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed, failed = 0, []
    for t in tests:
        try:
            t()
            print(f"  ✅ {t.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  ❌ {t.__name__} — {e}")
            failed.append(t.__name__)
        except Exception as e:
            print(f"  🚫 {t.__name__} — {type(e).__name__}: {e}")
            failed.append(t.__name__)
    print(f"\n  {passed}/{len(tests)} passed")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(_run_all())
