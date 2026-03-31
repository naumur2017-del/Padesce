param(
    [Parameter(Mandatory = $true)]
    [string]$Target,

    [Parameter(Mandatory = $true)]
    [string[]]$Source,

    [ValidateSet("newer", "source", "target")]
    [string]$ConflictStrategy = "newer",

    [string[]]$Table,

    [string[]]$ExcludeTable,

    [string]$BackupDir,

    [int]$Timeout = 60,

    [switch]$DryRun,

    [switch]$NoBackup
)

$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonCandidates = @(
    (Join-Path $projectRoot "venv\\Scripts\\python.exe"),
    "python"
)
$python = $null

foreach ($candidate in $pythonCandidates) {
    if ($candidate -eq "python") {
        $command = Get-Command python -ErrorAction SilentlyContinue
        if ($command) {
            $resolved = $command.Source
            & $resolved -c "pass" *> $null
            if ($LASTEXITCODE -eq 0) {
                $python = $resolved
                break
            }
        }
    } elseif (Test-Path $candidate) {
        & $candidate -c "pass" *> $null
        if ($LASTEXITCODE -eq 0) {
            $python = $candidate
            break
        }
    }
}

if (-not $python) {
    throw "Python introuvable. Activez l'environnement virtuel ou installez Python."
}

$arguments = @((Join-Path $projectRoot "manage.py"), "sync_sqlite", "--target", $Target, "--conflict-strategy", $ConflictStrategy, "--timeout", $Timeout)

foreach ($item in $Source) { $arguments += @("--source", $item) }
foreach ($item in $Table) { $arguments += @("--table", $item) }
foreach ($item in $ExcludeTable) { $arguments += @("--exclude-table", $item) }
if ($BackupDir) { $arguments += @("--backup-dir", $BackupDir) }
if ($DryRun) { $arguments += "--dry-run" }
if ($NoBackup) { $arguments += "--no-backup" }

& $python @arguments
exit $LASTEXITCODE
