"""Tests for backup_data.ps1 -- JonnyParlay's pick_log*.csv backup mechanism
(ADR-003 T14).

No PowerShell test framework (Pester) exists in this repo, and none is
introduced here -- these tests invoke the real script via subprocess against
isolated temp directories (-SourceDir/-DestRoot/-KeepCount parameters exist
specifically to make this possible without ever touching the real
$env:USERPROFILE\\OneDrive path). This exercises the actual script, not a
reimplementation of its logic.

Requires Windows PowerShell (powershell.exe) -- skipped elsewhere.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "backup_data.ps1"

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="PowerShell script, Windows-only")


def _run(source_dir, dest_root, keep_count=7, restore_drill=False, log_path=None):
    """log_path defaults to a file isolated alongside dest_root -- every test
    gets its own log file automatically without needing to pass one, and
    real production runs are never touched."""
    if log_path is None:
        log_path = Path(dest_root).parent / "backup.log"
    args = [
        "powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
        "-File", str(SCRIPT),
        "-SourceDir", str(source_dir),
        "-DestRoot", str(dest_root),
        "-KeepCount", str(keep_count),
        "-LogPath", str(log_path),
    ]
    if restore_drill:
        args.append("-RestoreDrill")
    proc = subprocess.run(args, capture_output=True, text=True, timeout=60)
    proc.log_path = Path(log_path)
    return proc


def _make_source(tmp_path, extra_files=None):
    """A source tree shaped like the real repo: SourceDir/data/pick_log*.csv."""
    src = tmp_path / "source"
    data = src / "data"
    data.mkdir(parents=True)
    for name, content in (extra_files or {}).items():
        (data / name).write_text(content, encoding="utf-8")
    return src


_ALL_REAL_PICK_LOG_FILES = [
    "pick_log.csv", "pick_log_blocked.csv", "pick_log_calibration.csv",
    "pick_log_custom.csv", "pick_log_custom_archive_pre_plan10.csv",
    "pick_log_game_lines.csv", "pick_log_manual.csv", "pick_log_mlb.csv",
    "pick_log_shadow_stats.csv", "pick_log_wnba.csv",
]


def test_all_current_pick_log_files_included(tmp_path):
    """The previous hardcoded 3-file list silently missed 7 of the 10 real
    pick_log*.csv files -- including the two largest. Dynamic discovery must
    catch all of them, not just the ones someone remembered to list."""
    files = {name: f"header\n{name}-content\n" for name in _ALL_REAL_PICK_LOG_FILES}
    src = _make_source(tmp_path, files)
    dest = tmp_path / "dest"

    proc = _run(src, dest)
    assert proc.returncode == 0, proc.stdout + proc.stderr

    dated_dirs = list(dest.glob("*"))
    assert len(dated_dirs) == 1
    backed_up = {p.name for p in dated_dirs[0].glob("pick_log*.csv")}
    assert backed_up == set(_ALL_REAL_PICK_LOG_FILES)


def test_env_excluded_from_cloud_synced_backup(tmp_path):
    src = _make_source(tmp_path, {"pick_log.csv": "a,b\n1,2\n"})
    (src / ".env").write_text("ODDS_API_KEY=secret123\n", encoding="utf-8")
    dest = tmp_path / "dest"

    proc = _run(src, dest)
    assert proc.returncode == 0, proc.stdout + proc.stderr

    dated_dir = next(dest.glob("*"))
    assert not (dated_dir / ".env").exists()
    assert (dated_dir / "pick_log.csv").exists()


def test_discord_guard_json_still_included(tmp_path):
    """discord_posted.json was in the original hardcoded list -- confirm the
    rewrite didn't accidentally drop it while switching to dynamic discovery."""
    src = _make_source(tmp_path, {"pick_log.csv": "a,b\n1,2\n"})
    (src / "data" / "discord_posted.json").write_text("{}", encoding="utf-8")
    dest = tmp_path / "dest"

    proc = _run(src, dest)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    dated_dir = next(dest.glob("*"))
    assert (dated_dir / "discord_posted.json").exists()


def test_backup_writes_a_verification_manifest(tmp_path):
    """Post-copy verification must be recorded, not just checked-and-discarded
    -- otherwise a later restore drill has nothing to verify against."""
    src = _make_source(tmp_path, {"pick_log.csv": "a,b\n1,2\n"})
    dest = tmp_path / "dest"

    proc = _run(src, dest)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    dated_dir = next(dest.glob("*"))
    manifest_path = dated_dir / "_manifest.json"
    assert manifest_path.exists()
    # Windows PowerShell 5.1's `-Encoding utf8` writes a UTF-8 BOM by design
    # (a known PS 5.1 quirk) -- PowerShell's own ConvertFrom-Json (used by the
    # script's own restore drill) tolerates it natively; utf-8-sig here
    # matches that tolerance rather than assuming a BOM-free file.
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    assert "pick_log.csv" in manifest
    assert len(manifest["pick_log.csv"]) == 64  # sha256 hex digest length


def test_restore_drill_passes_on_untampered_backup(tmp_path):
    src = _make_source(tmp_path, {"pick_log.csv": "a,b\n1,2\n"})
    dest = tmp_path / "dest"
    assert _run(src, dest).returncode == 0

    drill = _run(src, dest, restore_drill=True)
    assert drill.returncode == 0, drill.stdout + drill.stderr


def test_restore_drill_detects_corrupted_backup(tmp_path):
    """The real failure-detection surface: a backup file that has changed
    since it was written (bit rot, accidental edit) must be caught, not
    silently trusted."""
    src = _make_source(tmp_path, {"pick_log.csv": "a,b\n1,2\n"})
    dest = tmp_path / "dest"
    assert _run(src, dest).returncode == 0

    dated_dir = next(dest.glob("*"))
    (dated_dir / "pick_log.csv").write_text("TAMPERED", encoding="utf-8")

    drill = _run(src, dest, restore_drill=True)
    assert drill.returncode != 0, drill.stdout + drill.stderr


def test_rotation_keeps_only_keep_count_backups(tmp_path):
    """10 pre-existing dated backup folders + today's new one must reduce to
    exactly KeepCount, oldest removed first (by real timestamp, not filename
    string -- matches EdgeModel's own db_backup.py precedent)."""
    src = _make_source(tmp_path, {"pick_log.csv": "a,b\n1,2\n"})
    dest = tmp_path / "dest"
    dest.mkdir()
    import time
    for i in range(10):
        old_dir = dest / f"2026-01-{i + 1:02d}"
        old_dir.mkdir()
        (old_dir / "placeholder.csv").write_text("x", encoding="utf-8")
        # Force distinct, ascending mtimes regardless of how fast these loop
        # iterations execute.
        mtime = time.time() - (100 - i)
        import os
        os.utime(old_dir, (mtime, mtime))

    proc = _run(src, dest, keep_count=7)
    assert proc.returncode == 0, proc.stdout + proc.stderr

    remaining = sorted(p.name for p in dest.glob("*") if p.is_dir())
    assert len(remaining) == 7
    # The 4 oldest placeholder dirs (2026-01-01..04) must be gone; the 6
    # newest placeholders (05..10) plus today's new real backup must remain.
    for stale in ("2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04"):
        assert stale not in remaining, remaining


def test_source_with_no_pick_log_files_backs_up_nothing_but_succeeds(tmp_path):
    src = _make_source(tmp_path, {})
    dest = tmp_path / "dest"
    proc = _run(src, dest)
    assert proc.returncode == 0, proc.stdout + proc.stderr


# --- Destination allow-list validation ---------------------------------------
#
# The 2026-07-26 incident: a stale execution of the old (pre-rewrite) script
# left a real .env copy sitting in the backup destination. The manifest never
# flagged it -- the manifest only ever records what THIS invocation copied,
# and .env was never part of that. Manifest validation alone cannot catch a
# file it never knew to look for. This validates the actual destination
# folder contents against an explicit allow/forbidden list instead.

def test_forbidden_file_in_destination_fails_loudly(tmp_path):
    """Simulates the real incident shape: a forbidden file already present in
    the dated destination folder (as if left by some other process), then a
    normal backup run. The run's legitimate files must still be backed up
    (don't lose real data over someone else's mess), but the overall result
    must report failure, not success -- and must name the file, never its
    contents."""
    src = _make_source(tmp_path, {"pick_log.csv": "a,b\n1,2\n"})
    dest = tmp_path / "dest"
    stamp = __import__("datetime").date.today().isoformat()
    dated_dir = dest / stamp
    dated_dir.mkdir(parents=True)
    (dated_dir / ".env").write_text("ODDS_API_KEY=super-secret-value-12345\n", encoding="utf-8")

    proc = _run(src, dest)

    assert proc.returncode != 0, "must not report success when a forbidden file is present"
    combined = proc.stdout + proc.stderr
    assert ".env" in combined
    assert "super-secret-value-12345" not in combined, "must never print file contents"
    # The legitimate file must still have been backed up despite the failure.
    assert (dated_dir / "pick_log.csv").exists()


@pytest.mark.parametrize("forbidden_name", [
    ".env", "id.key", "server.pem", "credentials.json", "secrets.yaml",
])
def test_each_forbidden_pattern_is_detected(tmp_path, forbidden_name):
    src = _make_source(tmp_path, {"pick_log.csv": "a,b\n1,2\n"})
    dest = tmp_path / "dest"
    stamp = __import__("datetime").date.today().isoformat()
    dated_dir = dest / stamp
    dated_dir.mkdir(parents=True)
    (dated_dir / forbidden_name).write_text("secret", encoding="utf-8")

    proc = _run(src, dest)
    assert proc.returncode != 0, f"{forbidden_name} should have been flagged forbidden"
    assert forbidden_name in (proc.stdout + proc.stderr)


def test_clean_backup_passes_allow_list_validation(tmp_path):
    """The new validation step must not break the existing, already-correct
    happy path -- a backup containing only allowed files still succeeds."""
    files = {name: "x" for name in _ALL_REAL_PICK_LOG_FILES}
    src = _make_source(tmp_path, files)
    (src / "data" / "discord_posted.json").write_text("{}", encoding="utf-8")
    dest = tmp_path / "dest"

    proc = _run(src, dest)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "forbidden" not in (proc.stdout + proc.stderr).lower()


# --- Durable script-level logging --------------------------------------------
#
# Task Scheduler launches powershell.exe as a raw process with a single
# argument string -- shell redirection syntax (*>>, etc.) embedded there does
# NOT get interpreted as a redirect; it's consumed as literal script
# arguments instead (confirmed empirically, not assumed). The only reliable
# way to get a durable log from a scheduled run is the script writing its own
# log file directly, which is what these tests cover.

import re

_TIMESTAMP_RE = re.compile(r"\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\]")


def test_successful_backup_writes_expected_log_entries(tmp_path):
    src = _make_source(tmp_path, {"pick_log.csv": "a,b\n1,2\n"})
    dest = tmp_path / "dest"

    proc = _run(src, dest)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert proc.log_path.exists()
    log = proc.log_path.read_text(encoding="utf-8-sig")

    assert _TIMESTAMP_RE.search(log), "every entry must be timestamped"
    assert str(src) in log                      # source directory logged
    assert str(dest) in log                      # destination directory logged
    assert "pick_log.csv" in log                 # files selected logged
    assert re.search(r"verification.*ok", log, re.IGNORECASE)
    assert re.search(r"rotation", log, re.IGNORECASE)
    assert re.search(r"allow-list.*ok", log, re.IGNORECASE)
    assert re.search(r"success", log, re.IGNORECASE)
    assert "exit code: 0" in log.lower()


def test_failed_backup_writes_failure_reason(tmp_path):
    """A verification-style failure -- simulated here via a forbidden file,
    the failure path this session can trigger deterministically -- must log
    a reason, not just a bare 'failed'."""
    src = _make_source(tmp_path, {"pick_log.csv": "a,b\n1,2\n"})
    dest = tmp_path / "dest"
    stamp = __import__("datetime").date.today().isoformat()
    dated_dir = dest / stamp
    dated_dir.mkdir(parents=True)
    (dated_dir / ".env").write_text("secret", encoding="utf-8")

    proc = _run(src, dest)
    assert proc.returncode != 0
    log = proc.log_path.read_text(encoding="utf-8-sig")
    assert re.search(r"fail", log, re.IGNORECASE)
    assert "exit code: 1" in log.lower()


def test_forbidden_file_logged_without_contents(tmp_path):
    src = _make_source(tmp_path, {"pick_log.csv": "a,b\n1,2\n"})
    dest = tmp_path / "dest"
    stamp = __import__("datetime").date.today().isoformat()
    dated_dir = dest / stamp
    dated_dir.mkdir(parents=True)
    (dated_dir / ".env").write_text("ODDS_API_KEY=super-secret-value-99999\n", encoding="utf-8")

    proc = _run(src, dest)
    log = proc.log_path.read_text(encoding="utf-8-sig")
    assert ".env" in log                                  # filename: yes
    assert "super-secret-value-99999" not in log           # contents: never
    assert "ODDS_API_KEY" not in log


def test_restore_drill_result_logged(tmp_path):
    src = _make_source(tmp_path, {"pick_log.csv": "a,b\n1,2\n"})
    dest = tmp_path / "dest"
    assert _run(src, dest).returncode == 0

    proc = _run(src, dest, restore_drill=True)
    assert proc.returncode == 0
    log = proc.log_path.read_text(encoding="utf-8-sig")
    assert re.search(r"restore drill.*ok", log, re.IGNORECASE)


def test_log_appends_across_multiple_runs(tmp_path):
    """Add-Content appends by default -- confirm this holds in practice
    across two full, separate script invocations, not just within one."""
    src = _make_source(tmp_path, {"pick_log.csv": "a,b\n1,2\n"})
    dest = tmp_path / "dest"

    first = _run(src, dest)
    assert first.returncode == 0
    log_after_first = first.log_path.read_text(encoding="utf-8-sig")

    second = _run(src, dest, log_path=first.log_path)
    assert second.returncode == 0
    log_after_second = second.log_path.read_text(encoding="utf-8-sig")

    assert log_after_second.startswith(log_after_first), (
        "second run must append, not overwrite, the first run's entries"
    )
    assert len(log_after_second) > len(log_after_first)
    # Two separate "start" markers, not one.
    assert log_after_second.count("Backup started") == 2
