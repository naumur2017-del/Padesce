$ErrorActionPreference = "Stop"
Param(
    [string]$SourceDb = "db.sqlite3",
    [string]$DestinationDir = "backups"
)

if (-not (Test-Path $SourceDb)) {
    Write-Error "Source DB not found: $SourceDb"
}

if (-not (Test-Path $DestinationDir)) {
    New-Item -ItemType Directory -Path $DestinationDir | Out-Null
}

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$dest = Join-Path $DestinationDir ("db-$timestamp.sqlite3")
Copy-Item $SourceDb $dest
Write-Host "Backup created: $dest"
