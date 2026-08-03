# backup_data.ps1 — Daily backup of JonnyParlay's pick_log*.csv family + the
# Discord dedup guard, with post-copy verification and rotation (ADR-003 T14).
#
# Previously: a hardcoded 3-file list (pick_log.csv, pick_log_manual.csv,
# pick_log_mlb.csv) silently missed 7 of the 10 real pick_log*.csv files that
# exist today -- including the two largest (pick_log_calibration.csv,
# pick_log_blocked.csv). No verification existed: a truncated or corrupted
# copy would report success. No rotation existed: one new dated subfolder
# forever, unbounded growth. This had also never actually been run --
# $env:USERPROFILE\OneDrive\Backups\JonnyParlay did not exist on this
# machine before T14.
#
# .env is deliberately EXCLUDED. The destination syncs to OneDrive
# (Microsoft's cloud); copying secrets (API keys, webhook URLs) there is a
# real exposure surface this script should not create. Back up .env, if
# ever needed, through a separate, non-cloud-synced mechanism.
#
# Verification: every copied file's SHA256 is recorded in a per-backup
# _manifest.json. -RestoreDrill re-hashes the files in the most recent
# backup and confirms they still match their recorded hash -- catching
# corruption/tampering of the backup itself, not just a failed initial copy.
# This is the CSV-file analog of EdgeModel's db_backup.py --verify-latest
# (which does the same job for a live SQLite DB via integrity_check).
#
# Destination allow-list validation (2026-07-26 incident): a stale execution
# of the pre-rewrite version of this script (which hardcoded .env into its
# file list) left a real .env copy sitting in the backup destination. The
# manifest never flagged it -- the manifest only ever records what THIS
# invocation copied, so it structurally cannot catch a file it never knew to
# look for. After every backup, the actual destination folder contents are
# checked against an explicit forbidden-pattern list (.env, *.key, *.pem,
# credentials*, secrets*). If any match, the run reports FAILURE -- even
# though the legitimate files were still correctly backed up and verified --
# because "everything expected was copied" is not the same claim as "nothing
# forbidden is present," and only the second one is what actually happened
# in the incident this closes.
#
# Usage (production, real destination):
#   .\backup_data.ps1
#   .\backup_data.ps1 -RestoreDrill
# Usage (testing, isolated dirs):
#   .\backup_data.ps1 -SourceDir <path> -DestRoot <path> -KeepCount <n>
#
# Scheduling: NOT done by this script or automatically by anyone running it.
# To register as a daily Windows Scheduled Task (run this yourself, after
# reviewing it -- mirrors EdgeModel's own \EdgeModel\db_backup task pattern):
#
#   $action  = New-ScheduledTaskAction -Execute "powershell.exe" `
#       -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$PSScriptRoot\backup_data.ps1`""
#   $trigger = New-ScheduledTaskTrigger -Daily -At 4:00AM
#   Register-ScheduledTask -TaskName "JonnyParlay Backup" -Action $action `
#       -Trigger $trigger -Description "Daily pick_log*.csv backup (ADR-003 T14)."

param(
    [string]$SourceDir = $PSScriptRoot,
    [string]$DestRoot = "$env:USERPROFILE\OneDrive\Backups\JonnyParlay",
    [int]$KeepCount = 7,
    [switch]$RestoreDrill,
    [string]$LogPath = ""
)

$ErrorActionPreference = "Stop"
$dataDir = Join-Path $SourceDir "data"

# Durable, script-level logging (2026-07-26 hardening): Task Scheduler
# launches powershell.exe as a raw process with a single argument string --
# shell redirection syntax (*>>, etc.) embedded there does NOT get
# interpreted as a redirect; it's silently consumed as literal arguments to
# the script instead (confirmed empirically). Writing the log file directly,
# from inside the script, is the only form that works identically whether
# invoked manually or from a scheduled task. Add-Content always appends.
if (-not $LogPath) {
    $LogPath = Join-Path (Join-Path $SourceDir "data") "backup.log"
}

function Write-Log {
    <#
    Never pass secret values here. Every call site in this script logs
    filenames, paths, and pass/fail summaries only -- never file contents or
    environment-variable values.
    #>
    param([string]$Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    try {
        $logDir = Split-Path -Parent $LogPath
        if ($logDir -and -not (Test-Path $logDir)) {
            New-Item -ItemType Directory -Path $logDir -Force | Out-Null
        }
        Add-Content -Path $LogPath -Value "[$timestamp] $Message" -Encoding utf8
    } catch {
        # Logging must never be why a backup fails -- if the log write itself
        # fails (e.g. disk full), fall back to console only and keep going.
        Write-Host "Write-Log failed: $_" -ForegroundColor Yellow
    }
}

# Explicit forbidden patterns for the destination allow-list check. Matched
# with -like (case-insensitive, standard PowerShell wildcard semantics)
# against each file's leaf name only -- never its contents.
$script:ForbiddenPatterns = @(".env", "*.key", "*.pem", "credentials*", "secrets*")

function Test-DestinationAllowList {
    <#
    Scans $Path (a single dated backup folder) for any file matching
    $script:ForbiddenPatterns. Returns the list of matching filenames (empty
    if none). Deliberately scoped to one dated folder, not the whole
    $DestRoot tree -- each day's folder is validated when IT is created;
    re-scanning every historical folder on every run would be redundant and
    would re-flag already-known, already-reported historical contamination
    forever.
    #>
    param([string]$Path)
    $found = @()
    $allFiles = Get-ChildItem -Path $Path -File -Force -ErrorAction SilentlyContinue
    foreach ($f in $allFiles) {
        foreach ($pattern in $script:ForbiddenPatterns) {
            if ($f.Name -like $pattern) {
                $found += $f.Name
                break
            }
        }
    }
    return $found
}

function Get-BackupFileList {
    $files = @()
    if (Test-Path $dataDir) {
        $files += Get-ChildItem -Path $dataDir -Filter "pick_log*.csv" -File -ErrorAction SilentlyContinue
        $guard = Join-Path $dataDir "discord_posted.json"
        if (Test-Path $guard) {
            $files += Get-Item $guard
        }
    }
    return $files
}

function Get-Sha256Hash {
    <#
    Equivalent to (Get-FileHash -Path $Path -Algorithm SHA256).Hash, computed via
    the .NET crypto API directly rather than the cmdlet -- Get-FileHash depends on
    Microsoft.PowerShell.Utility auto-loading, which some CI runners don't have
    ("Get-FileHash is not recognized as the name of a cmdlet"). Same uppercase-hex,
    no-dashes output format, so manifest.json contents and drill comparisons are
    unaffected.
    #>
    param([string]$Path)
    $sha256 = [System.Security.Cryptography.SHA256]::Create()
    try {
        $bytes = [System.IO.File]::ReadAllBytes($Path)
        $hashBytes = $sha256.ComputeHash($bytes)
        return [System.BitConverter]::ToString($hashBytes) -replace '-', ''
    } finally {
        $sha256.Dispose()
    }
}

function Invoke-RestoreDrill {
    Write-Log "=== Restore drill started ==="
    Write-Log "Destination directory: $DestRoot"
    if (-not (Test-Path $DestRoot)) {
        Write-Host "No backups exist at $DestRoot" -ForegroundColor Red
        Write-Log "Restore drill result: FAILED -- no backups exist at $DestRoot"
        Write-Log "Final state: FAILURE"
        Write-Log "Exit code: 1"
        exit 1
    }
    $latest = Get-ChildItem -Path $DestRoot -Directory -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if (-not $latest) {
        Write-Host "No dated backup folders found under $DestRoot" -ForegroundColor Red
        Write-Log "Restore drill result: FAILED -- no dated backup folders found"
        Write-Log "Final state: FAILURE"
        Write-Log "Exit code: 1"
        exit 1
    }
    $manifestPath = Join-Path $latest.FullName "_manifest.json"
    if (-not (Test-Path $manifestPath)) {
        Write-Host "No manifest found in $($latest.FullName) -- cannot verify" -ForegroundColor Red
        Write-Log "Restore drill result: FAILED -- no manifest found in $($latest.Name)"
        Write-Log "Final state: FAILURE"
        Write-Log "Exit code: 1"
        exit 1
    }
    $manifest = Get-Content $manifestPath -Raw | ConvertFrom-Json
    $failed = @()
    $checked = 0
    foreach ($prop in $manifest.PSObject.Properties) {
        $checked++
        $filePath = Join-Path $latest.FullName $prop.Name
        if (-not (Test-Path $filePath)) {
            $failed += "$($prop.Name) (missing)"
            continue
        }
        $actualHash = Get-Sha256Hash -Path $filePath
        if ($actualHash -ne $prop.Value) {
            $failed += "$($prop.Name) (hash mismatch)"
        }
    }
    if ($failed.Count -gt 0) {
        Write-Host "RESTORE DRILL FAILED on $($latest.Name): $($failed -join ', ')" -ForegroundColor Red
        Write-Log "Restore drill result: FAILED -- $($failed -join ', ')"
        Write-Log "Final state: FAILURE"
        Write-Log "Exit code: 1"
        exit 1
    }
    Write-Host "Restore drill OK: $checked/$checked file(s) verified in $($latest.Name)" -ForegroundColor Green
    Write-Log "Restore drill result: OK ($checked/$checked file(s) verified in $($latest.Name))"
    Write-Log "Final state: SUCCESS"
    Write-Log "Exit code: 0"
    exit 0
}

function Invoke-Backup {
    Write-Log "=== Backup started ==="
    Write-Log "Source directory: $SourceDir"

    if (-not (Test-Path $DestRoot)) {
        New-Item -ItemType Directory -Path $DestRoot -Force | Out-Null
    }
    $stamp = Get-Date -Format "yyyy-MM-dd"
    $destDate = Join-Path $DestRoot $stamp
    if (-not (Test-Path $destDate)) {
        New-Item -ItemType Directory -Path $destDate -Force | Out-Null
    }
    Write-Log "Destination directory: $destDate"

    $files = Get-BackupFileList
    Write-Log "Files selected: $($files.Name -join ', ')"
    $manifest = @{}
    $failed = @()

    foreach ($f in $files) {
        $destFile = Join-Path $destDate $f.Name
        Copy-Item $f.FullName $destFile -Force
        $srcHash = Get-Sha256Hash -Path $f.FullName
        $dstHash = Get-Sha256Hash -Path $destFile
        if ($srcHash -eq $dstHash) {
            $manifest[$f.Name] = $dstHash
        } else {
            $failed += $f.Name
        }
    }

    if ($manifest.Count -gt 0) {
        $manifest | ConvertTo-Json | Set-Content -Path (Join-Path $destDate "_manifest.json") -Encoding utf8
    }

    if ($failed.Count -gt 0) {
        Write-Log "Verification: FAILED -- $($failed -join ', ')"
    } else {
        Write-Log "Verification: OK ($($manifest.Count)/$($files.Count))"
    }

    # Rotation: keep the KeepCount most recent dated backup folders, by real
    # LastWriteTime -- not filename string. Matches EdgeModel's db_backup.py's
    # own hard-learned lesson (a tagged/irregular folder name can sort out of
    # chronological order alphabetically even when dates normally wouldn't).
    $allBackups = Get-ChildItem -Path $DestRoot -Directory -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime
    $removedCount = 0
    if ($allBackups.Count -gt $KeepCount) {
        $toDelete = $allBackups | Select-Object -First ($allBackups.Count - $KeepCount)
        foreach ($old in $toDelete) {
            Remove-Item $old.FullName -Recurse -Force
        }
        $removedCount = $toDelete.Count
    }
    Write-Log "Rotation: kept $([Math]::Min($allBackups.Count, $KeepCount)) folder(s), removed $removedCount old folder(s)"

    if ($failed.Count -gt 0) {
        Write-Host "Backup FAILED verification for: $($failed -join ', ')" -ForegroundColor Red
        Write-Log "Final state: FAILURE (verification)"
        Write-Log "Exit code: 1"
        exit 1
    }

    # Destination allow-list validation runs LAST, after the legitimate files
    # are already safely copied and verified above -- a forbidden file being
    # present doesn't mean today's real backup should be discarded, it means
    # the overall result must not be reported as a clean success.
    $forbidden = Test-DestinationAllowList -Path $destDate
    if ($forbidden.Count -gt 0) {
        Write-Log "Allow-list validation: FAILED -- forbidden file(s): $($forbidden -join ', ')"
    } else {
        Write-Log "Allow-list validation: OK"
    }
    if ($forbidden.Count -gt 0) {
        Write-Host "BACKUP NOT CLEAN: forbidden file(s) present in ${destDate}: $($forbidden -join ', ')" -ForegroundColor Red
        Write-Host "Legitimate files were still backed up and verified above -- remove the forbidden file(s) and re-run to confirm a clean result." -ForegroundColor Yellow
        Write-Log "Final state: FAILURE (forbidden files present)"
        Write-Log "Exit code: 1"
        exit 1
    }

    Write-Host "Backed up and verified $($manifest.Count)/$($files.Count) file(s) to $destDate" -ForegroundColor Green
    Write-Log "Final state: SUCCESS"
    Write-Log "Exit code: 0"
    exit 0
}

if ($RestoreDrill) {
    Invoke-RestoreDrill
} else {
    Invoke-Backup
}
