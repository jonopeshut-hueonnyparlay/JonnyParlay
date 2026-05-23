#Requires -Version 5
param([string]$Sport = "")

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding           = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING     = "utf-8"
$ErrorActionPreference    = "Continue"
Set-Location $PSScriptRoot

function Find-CSV([string]$sport) {
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

if ($Sport -eq "") {
    Write-Host "Usage: .\go.bat <sport>"
    Write-Host "  .\go.bat mlb"
    Write-Host "  .\go.bat wnba"
    Write-Host "  .\go.bat nhl"
    Write-Host "  .\go.bat nba"
    Read-Host "`nPress Enter to exit"
    exit 0
}

$csv = Find-CSV $Sport
if (-not $csv) {
    Write-Host "No $($Sport.ToUpper()) CSV found in Downloads (modified in last 12h)." -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "$($Sport.ToUpper()): $($csv.Name)" -ForegroundColor Cyan
python run_picks.py "$($csv.FullName)"

if ($Sport.ToLower() -eq "nba") {
    Write-Host "`nNBA SHADOW (custom projections)..." -ForegroundColor Cyan
    python engine\generate_projections.py --shadow
}

Read-Host "`nPress Enter to exit"
