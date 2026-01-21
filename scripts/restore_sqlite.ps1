$ErrorActionPreference = "Stop"
Param(
    [Parameter(Mandatory = $true)][string]$BackupFile,
    [string]$TargetDb = "db.sqlite3"
)

if (-not (Test-Path $BackupFile)) {
    Write-Error "Backup file not found: $BackupFile"
}
Copy-Item $BackupFile $TargetDb -Force
Write-Host "Restored $BackupFile to $TargetDb"
