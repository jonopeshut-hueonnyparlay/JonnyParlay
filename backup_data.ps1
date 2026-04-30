# backup_data.ps1 — Daily backup of critical JonnyParlay data files.
# Schedule via Task Scheduler or run manually after a session.
# Copies pick logs, .env, and discord guard to OneDrive/Backups.
#
# Usage: .\backup_data.ps1

$src  = $PSScriptRoot
$dest = "$env:USERPROFILE\OneDrive\Backups\JonnyParlay"

if (-not (Test-Path $dest)) {
    New-Item -ItemType Directory -Path $dest -Force | Out-Null
}

$stamp    = Get-Date -Format "yyyy-MM-dd"
$destDate = "$dest\$stamp"

if (-not (Test-Path $destDate)) {
    New-Item -ItemType Directory -Path $destDate -Force | Out-Null
}

$files = @(
    "$src\data\pick_log.csv",
    "$src\data\pick_log_manual.csv",
    "$src\data\pick_log_mlb.csv",
    "$src\data\discord_posted.json",
    "$src\.env"
)

$copied = 0
foreach ($f in $files) {
    if (Test-Path $f) {
        Copy-Item $f $destDate -Force
        $copied++
    }
}

Write-Host "Backed up $copied file(s) to $destDate" -ForegroundColor Green
