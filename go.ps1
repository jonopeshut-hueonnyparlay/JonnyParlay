#Requires -Version 5
<#
  go.ps1 -- JonnyParlay full daily run
  ------------------------------------
  Does EVERYTHING:
    1. Dependency check + auto-install (filelock, requests, pillow)
    2. File integrity + freshness check
    3. CLV daemon task verification (offers to create if missing)
    4. Stale lockfile cleanup
    5. SaberSim CSV detection (current folder -> Downloads -> wait)
    6. Auto-classify CSVs by sport (filename + header sniff)
    7. Run run_picks.py for each detected sport
    8. Kick CLV daemon

  Usage:
    go.bat                # interactive, default flow
    go.bat -SkipRun       # just preflight, don't run engine
    go.bat -DryRun        # show what would happen, make no changes
    go.bat -Sports nba    # restrict to specific sport(s), comma-separated
#>

[CmdletBinding()]
param(
    [switch]$SkipRun,
    [switch]$DryRun,
    [string]$Sports = "auto"
)

# Don't use Stop -- external commands (python, schtasks) return non-zero as a normal signal.
$ErrorActionPreference = "Continue"
Set-Location $PSScriptRoot

# Audit M-6 (closed Apr 20 2026): force UTF-8 for console I/O so our emoji
# + box-drawing characters render correctly in cmd / Windows Terminal.
# Without this, Python prints via this PowerShell session crash with
# UnicodeEncodeError when stdout is cp1252 (default on en-US Windows).
# Applies to both what this script writes (Write-Host) AND anything the
# child python processes output via stdout/stderr.
try {
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    $OutputEncoding           = [System.Text.Encoding]::UTF8
} catch {
    # Non-fatal — some hosts (ISE, old PS) reject the assignment. The engine
    # will still run; worst case a unicode char prints as '?'.
}

# Audit L-6 (closed Apr 21 2026): start_clv_daemon.bat already sets
# PYTHONIOENCODING=utf-8 so the daemon's stdout stays clean when cmd.exe
# pipes its output into the rotating log. go.ps1 runs the same engine under
# a different launcher (run_picks.py, grade_picks.py, weekly_recap.py) and
# inherited the console's cp1252 default on Windows — any emoji or
# box-drawing character in a Python exception traceback crashed the child.
# Setting it here matches the daemon launcher and closes the gap.
$env:PYTHONIOENCODING = "utf-8"

# Trap ANY unhandled error: show it, pause, exit cleanly so we can debug.
trap {
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Red
    Write-Host "  UNHANDLED ERROR" -ForegroundColor Red
    Write-Host "============================================================" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    Write-Host ""
    Write-Host "Line:        $($_.InvocationInfo.ScriptLineNumber)"
    Write-Host "Position:    $($_.InvocationInfo.Line.Trim())"
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit 1
}

function Write-Hdr($text) {
    Write-Host ""
    Write-Host ("=" * 60) -ForegroundColor Cyan
    Write-Host "  $text" -ForegroundColor Cyan
    Write-Host ("=" * 60) -ForegroundColor Cyan
}

function Write-Ok($msg)   { Write-Host "[ OK ] $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "[WARN] $msg" -ForegroundColor Yellow }
function Write-Err($msg)  { Write-Host "[FAIL] $msg" -ForegroundColor Red }

Write-Hdr "JonnyParlay -- Full Daily Run"
if ($DryRun) { Write-Warn "DRY RUN -- no changes will be made" }

# ===========================================================
# 1. Python check
# ===========================================================
Write-Host "`n[1/8] Python check..."
try {
    $pyv = (python --version 2>&1) -join ""
    Write-Ok $pyv
} catch {
    Write-Err "Python not found on PATH. Install Python 3.10+ first."
    Read-Host "Press Enter to exit"; exit 1
}

# ===========================================================
# 2. Dependencies
# ===========================================================
Write-Host "`n[2/8] Dependency check..."
# Audit M-9 (closed Apr 20 2026): openpyxl was missing from this map even
# though weekly_recap.py writes an .xlsx attachment. Silent no-install meant
# recap CSVs shipped without the spreadsheet. Mirror of preflight.bat step 5.
$depMap = @{ "filelock"="filelock"; "requests"="requests"; "PIL"="pillow"; "openpyxl"="openpyxl" }
foreach ($import in $depMap.Keys) {
    $pkg = $depMap[$import]
    python -c "import $import" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Warn "$pkg missing"
        if (-not $DryRun) {
            python -m pip install $pkg --break-system-packages 2>&1 | Out-Null
            python -c "import $import" 2>$null
            if ($LASTEXITCODE -eq 0) { Write-Ok "$pkg installed" }
            else                     { Write-Err "$pkg install failed" }
        }
    } else {
        Write-Ok "$pkg"
    }
}

# ===========================================================
# 3. Required files + freshness
# ===========================================================
Write-Host "`n[3/8] File integrity..."
$required = @(
    "run_picks.py",
    "grade_picks.py",
    "capture_clv.py",
    "start_clv_daemon.bat",
    "engine\run_picks.py",
    "engine\grade_picks.py",
    "engine\capture_clv.py"
)
$allOk = $true
foreach ($f in $required) {
    if (Test-Path $f) {
        $age = (New-TimeSpan -Start (Get-Item $f).LastWriteTime -End (Get-Date)).TotalHours
        $ageStr = if ($age -lt 1) { "<1h" } elseif ($age -lt 24) { "{0:N0}h" -f $age } else { "{0:N0}d" -f ($age/24) }
        Write-Ok "$f  ($ageStr old)"
    } else {
        Write-Err "Missing: $f"
        $allOk = $false
    }
}
if (-not (Test-Path "data\pick_log.csv")) {
    Write-Warn "data\pick_log.csv missing -- will be created on first run"
}
if (-not $allOk) {
    Write-Err "Required files missing. Fix and re-run."
    Read-Host "Press Enter to exit"; exit 1
}

# Engine/root sync check
# Audit H-12: analyze_picks.py was drifting silently (53-line diff) because
# it wasn't in this list. Anything with a root mirror must be listed here so
# preflight auto-syncs on every run. Also adding results_graphic.py,
# weekly_recap.py, morning_preview.py, pick_log_schema.py, name_utils.py —
# all of these are imported by run_picks.py / grade_picks.py and have root
# mirrors for CI + Cowork discovery.
$syncPairs = @(
    @("run_picks.py",        "engine\run_picks.py"),
    @("grade_picks.py",      "engine\grade_picks.py"),
    @("capture_clv.py",      "engine\capture_clv.py"),
    @("analyze_picks.py",    "engine\analyze_picks.py"),
    @("results_graphic.py",  "engine\results_graphic.py"),
    @("weekly_recap.py",     "engine\weekly_recap.py"),
    @("morning_preview.py",  "engine\morning_preview.py"),
    @("pick_log_schema.py",  "engine\pick_log_schema.py"),
    @("name_utils.py",       "engine\name_utils.py")
)
foreach ($pair in $syncPairs) {
    $root = $pair[0]; $eng = $pair[1]
    if ((Test-Path $root) -and (Test-Path $eng)) {
        $rootHash = (Get-FileHash $root).Hash
        $engHash  = (Get-FileHash $eng).Hash
        if ($rootHash -ne $engHash) {
            Write-Warn "$root differs from $eng"
            if (-not $DryRun) {
                Copy-Item $eng $root -Force
                Write-Ok "Synced $eng -> $root"
            }
        }
    }
}

# ===========================================================
# 4. CLV daemon task
# ===========================================================
Write-Host "`n[4/8] CLV daemon scheduled task..."
schtasks /query /tn "JonnyParlay CLV Daemon" 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Warn "CLV daemon task not scheduled"
    if (-not $DryRun) {
        $create = Read-Host "Create task now? (runs daily at 10am) [y/n]"
        if ($create -eq "y") {
            $bat = Join-Path $PSScriptRoot "start_clv_daemon.bat"
            schtasks /create /tn "JonnyParlay CLV Daemon" /tr "`"$bat`"" /sc daily /st 10:00 /f | Out-Null
            if ($LASTEXITCODE -eq 0) { Write-Ok "CLV daemon task created" }
            else                     { Write-Err "Task creation failed" }
        }
    }
} else {
    Write-Ok "CLV daemon task scheduled"
}

# ===========================================================
# 5. Stale lockfile cleanup
# ===========================================================
Write-Host "`n[5/8] Lockfile cleanup..."
$locks = @("data\pick_log.csv.lock", "data\discord_posted.json.lock")
$cleaned = 0
foreach ($lock in $locks) {
    if (Test-Path $lock) {
        if (-not $DryRun) { Remove-Item $lock -Force }
        Write-Ok "Cleared stale $lock"
        $cleaned++
    }
}
if ($cleaned -eq 0) { Write-Ok "No stale lockfiles" }

# ===========================================================
# 6. SaberSim CSV detection
# ===========================================================
Write-Host "`n[6/8] SaberSim CSV detection..."
$today = Get-Date -Format "yyyy-MM-dd"
# Primary drop location + fallback to flat Downloads (projections subfolder is where Jono saves SaberSim exports)
$downloadDirs = @(
    "$env:USERPROFILE\Downloads\projections",
    "$env:USERPROFILE\Downloads"
) | Where-Object { Test-Path $_ }
$downloads = $downloadDirs[0]  # Preferred for new-file wait loop

function Detect-Sport([string]$path) {
    $name = [IO.Path]::GetFileNameWithoutExtension($path).ToLower()
    if ($name -match "\bnba\b|basketball")    { return "nba" }
    if ($name -match "\bnhl\b|hockey")        { return "nhl" }
    if ($name -match "\bnfl\b|football")      { return "nfl" }
    if ($name -match "\bmlb\b|baseball")      { return "mlb" }
    if ($name -match "\bncaab\b")             { return "ncaab" }
    # Header sniff fallback
    try {
        $header = ((Get-Content $path -TotalCount 1) -join "").ToLower()
        if ($header -match "shots.on.goal|\bsog\b|\bsaves\b")         { return "nhl" }
        if ($header -match "\b3pm\b|rebounds|\breb\b|assists")        { return "nba" }
        if ($header -match "rush.yards|rec.yards|passing")            { return "nfl" }
        if ($header -match "\brbi\b|strikeouts|\bera\b|\bhits\b")     { return "mlb" }
    } catch {}
    return $null
}

# Allowed sports filter
$allowedSports = if ($Sports -eq "auto") { @("nba","nhl","nfl","mlb","ncaab") }
                 else                    { $Sports.ToLower().Split(",") | ForEach-Object { $_.Trim() } }

$resolved = @{}   # sport -> source path

# Phase A: existing fresh CSVs in working dir
foreach ($sp in $allowedSports) {
    $local = "$sp.csv"
    if (Test-Path $local) {
        $hrs = (New-TimeSpan -Start (Get-Item $local).LastWriteTime -End (Get-Date)).TotalHours
        if ($hrs -lt 12) {
            Write-Ok "$local already present ($([math]::Round($hrs,1))h old)"
            $resolved[$sp] = $local
        } else {
            Write-Warn "$local is $([math]::Round($hrs,1))h old -- will refresh from Downloads if possible"
        }
    }
}

# Phase B: scan Downloads for recent CSVs
$missing = $allowedSports | Where-Object { -not $resolved.ContainsKey($_) }
if ($missing.Count -gt 0) {
    Write-Host "  Scanning $($downloadDirs -join ', ') for CSVs modified in last 6h..."
    $recentCsvs = $downloadDirs | ForEach-Object {
        Get-ChildItem "$_\*.csv" -ErrorAction SilentlyContinue
    } | Where-Object { (New-TimeSpan -Start $_.LastWriteTime -End (Get-Date)).TotalHours -lt 6 } |
        Sort-Object LastWriteTime -Descending
    foreach ($csv in $recentCsvs) {
        $sport = Detect-Sport $csv.FullName
        if ($sport -and ($missing -contains $sport) -and (-not $resolved.ContainsKey($sport))) {
            Write-Host "  Found: $($csv.Name) -> $sport.csv" -ForegroundColor Green
            if (-not $DryRun) { Copy-Item $csv.FullName "$sport.csv" -Force }
            $resolved[$sport] = "$sport.csv"
        }
    }
}

# Phase C: if still missing sports and user wanted auto, wait
$missing = $allowedSports | Where-Object { -not $resolved.ContainsKey($_) }
if (($missing.Count -gt 0) -and ($Sports -eq "auto") -and ($resolved.Count -eq 0) -and (-not $DryRun)) {
    Write-Host ""
    Write-Warn "No SaberSim CSVs found yet."
    Write-Host "  Download from https://sabersim.com and save to Downloads\projections (or this folder)."
    Write-Host "  I'll scan every 5s. Enter 'skip' to proceed with none, 'q' to quit."
    Write-Host ""
    $waitStart = Get-Date
    while ($true) {
        if ([Console]::KeyAvailable) {
            $k = [Console]::ReadKey($true)
            if ($k.KeyChar -eq 'q') { Write-Host "Quit."; exit 0 }
            if ($k.KeyChar -eq 's') { Write-Host "Skipping CSV wait."; break }
        }
        Start-Sleep -Seconds 5
        $new = $downloadDirs | ForEach-Object {
            Get-ChildItem "$_\*.csv" -ErrorAction SilentlyContinue
        } | Where-Object { $_.LastWriteTime -gt $waitStart } |
            Sort-Object LastWriteTime -Descending
        $found = $false
        foreach ($csv in $new) {
            $sport = Detect-Sport $csv.FullName
            if ($sport -and (-not $resolved.ContainsKey($sport))) {
                Write-Host "  Found: $($csv.Name) -> $sport.csv" -ForegroundColor Green
                Copy-Item $csv.FullName "$sport.csv" -Force
                $resolved[$sport] = "$sport.csv"
                $found = $true
            }
        }
        if ($found) {
            $more = Read-Host "  Add more sports? [y/n]"
            if ($more -ne "y") { break }
            $waitStart = Get-Date
        }
        if ((New-TimeSpan -Start $waitStart -End (Get-Date)).TotalMinutes -gt 15) {
            # Audit M-18 (closed Apr 20 2026): a plain `break` fell through to
            # the rest of the script, which then printed "No CSVs resolved,
            # nothing to run" and exited 0. Task Scheduler (and Jono's morning
            # glance) read exit-0 as success. Now we exit 2 so the wrapper can
            # flag the CSV-wait timeout as a real failure and Jono can retry.
            Write-Err "Timed out after 15 min waiting for SaberSim CSV. Re-run when ready."
            Read-Host "Press Enter to exit"
            exit 2
        }
    }
}

if ($resolved.Count -eq 0) {
    Write-Warn "No CSVs resolved. Nothing to run."
    if (-not $SkipRun) { Read-Host "Press Enter to exit"; exit 0 }
} else {
    Write-Host ""
    Write-Ok "Resolved: $($resolved.Keys -join ', ')"
}

# ===========================================================
# 7. Run engine
# ===========================================================
if ($SkipRun) {
    Write-Host "`n[7/8] Skipping engine run (-SkipRun flag)" -ForegroundColor Yellow
} elseif ($DryRun) {
    Write-Host "`n[7/8] DRY RUN -- would run:"
    foreach ($sp in $resolved.Keys) { Write-Host "  python run_picks.py $sp.csv" }
} else {
    Write-Hdr "[7/8] Running engine"
    foreach ($sp in $resolved.Keys) {
        Write-Host "`n--- $($sp.ToUpper()) ---`n" -ForegroundColor Cyan
        python run_picks.py "$sp.csv"
        if ($LASTEXITCODE -ne 0) {
            Write-Warn "run_picks.py $sp.csv exited $LASTEXITCODE"
            $cont = Read-Host "Continue with remaining sports? [y/n]"
            if ($cont -ne "y") { break }
        }
    }
}

# ===========================================================
# 8. Kick CLV daemon
# ===========================================================
Write-Host ""
if (-not $DryRun -and -not $SkipRun) {
    Write-Host "[8/8] Triggering CLV daemon..."
    schtasks /run /tn "JonnyParlay CLV Daemon" 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) { Write-Ok "CLV daemon kicked" }
    else                     { Write-Warn "CLV daemon not triggered (already running or not scheduled)" }
} else {
    Write-Host "[8/8] Skipping CLV daemon trigger"
}

Write-Hdr "Done. grade_picks.py will grade after games."
if (-not $DryRun) { Read-Host "Press Enter to exit" }
