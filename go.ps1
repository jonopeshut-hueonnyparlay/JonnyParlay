#Requires -Version 5
# L16: root entry-point files are 5-line runpy shims — no sync loop needed.
param([string]$Sport = "")

try {
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    $OutputEncoding           = [System.Text.Encoding]::UTF8
} catch { }
$env:PYTHONIOENCODING     = "utf-8"
$ErrorActionPreference    = "Continue"
Set-Location $PSScriptRoot

# Dependency map: import-name → pip-name (M-9)
$depMap = @{
    "filelock"  = "filelock"
    "requests"  = "requests"
    "PIL"       = "pillow"
    "openpyxl"  = "openpyxl"
}

function Write-Hdr([string]$msg) {
    Write-Host "`n=== $msg ===" -ForegroundColor Cyan
}

function Find-CSV([string]$sport) {
    # Check sport-specific archive first (no time limit — latest file wins)
    $archiveDir = "$env:USERPROFILE\Documents\Data\SaberSim\$($sport.ToUpper())"
    if (Test-Path $archiveDir) {
        $archived = Get-ChildItem "$archiveDir\*.csv" -ErrorAction SilentlyContinue |
                    Where-Object { $_.Name -imatch "\b$sport\b" } |
                    Sort-Object LastWriteTime -Descending |
                    Select-Object -First 1
        if ($archived) { return $archived }
    }
    # Fall back to Downloads (fresh files only — last 12h)
    $dirs = @("$env:USERPROFILE\Downloads\projections", "$env:USERPROFILE\Downloads") |
            Where-Object { Test-Path $_ }
    $csvs = $dirs | ForEach-Object {
        Get-ChildItem "$_\*.csv" -ErrorAction SilentlyContinue
    } | Where-Object {
        $_.Name -imatch "\b$sport\b" -and
        (New-TimeSpan -Start $_.LastWriteTime -End (Get-Date)).TotalHours -lt 12
    } | Sort-Object LastWriteTime -Descending
    return $csvs | Select-Object -First 1
}

Write-Hdr "JonnyParlay — go.ps1"

if ($Sport -eq "") {
    Write-Host "Usage: .\go.ps1 <sport>"
    Write-Host "  .\go.ps1 mlb"
    Write-Host "  .\go.ps1 wnba"
    Write-Host "  .\go.ps1 nhl"
    Write-Host "  .\go.ps1 nba"
    Read-Host "`nPress Enter to exit"
    exit 0
}

# Wait up to 15 minutes for the SaberSim CSV to appear in Downloads.
$waitStart = Get-Date
$csv = $null
while ($true) {
    $csv = Find-CSV $Sport
    if ($csv) { break }
    $elapsed = (Get-Date) - $waitStart
    if ($elapsed.TotalMinutes -gt 15) {
        Write-Host "Timed out waiting for $($Sport.ToUpper()) CSV (15 min). Drop the file and re-run." -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit 2
    }
    Write-Host "Waiting for $($Sport.ToUpper()) CSV in Downloads..." -ForegroundColor Yellow
    Start-Sleep -Seconds 15
}

Write-Host "$($Sport.ToUpper()): $($csv.Name)" -ForegroundColor Cyan
python run_picks.py "$($csv.FullName)"

if ($Sport.ToLower() -eq "nba") {
    Write-Host "`nNBA SHADOW (custom projections)..." -ForegroundColor Cyan
    python engine\generate_projections.py --shadow
}

Read-Host "`nPress Enter to exit"
