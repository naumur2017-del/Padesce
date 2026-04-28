Param(
    [Parameter(Mandatory=$true)] [ValidateSet('sqlite','postgres')] [string]$DbType,
    [Parameter(Mandatory=$true)] [string]$SqlFile,
    [string]$SqliteFile,
    [string]$PgHost,
    [int]$PgPort = 5432,
    [string]$PgUser,
    [string]$PgDatabase,
    [string]$PgPassword
)

function Backup-Sqlite {
    param($File)
    $ts = Get-Date -Format yyyyMMdd_HHmmss
    $backup = "$File.pre_sync_$ts.bak"
    Copy-Item -Path $File -Destination $backup -Force
    Write-Output "Created backup: $backup"
    return $backup
}

function Apply-Sqlite {
    param($DbFile, $SqlFile)
    if (-not (Get-Command sqlite3 -ErrorAction SilentlyContinue)) {
        Write-Error "sqlite3 cli not found in PATH. Install sqlite3 or run SQL by other means."
        exit 1
    }
    & sqlite3 $DbFile ".read $SqlFile"
    Write-Output "Applied SQL to $DbFile"
}

function Backup-Postgres {
    param($Host,$Port,$User,$Database)
    $ts = Get-Date -Format yyyyMMdd_HHmmss
    $file = "$Database.pre_sync_$ts.sql"
    $env:PGPASSWORD = $PgPassword
    $cmd = "pg_dump -h $Host -p $Port -U $User -d $Database -F p -f $file"
    Write-Output "Running: $cmd"
    cmd /c $cmd
    Write-Output "Created backup: $file"
    Remove-Item Env:PGPASSWORD
    return $file
}

function Apply-Postgres {
    param($Host,$Port,$User,$Database,$SqlFile)
    if (-not (Get-Command psql -ErrorAction SilentlyContinue)) {
        Write-Error "psql not found in PATH. Install PostgreSQL client utilities."
        exit 1
    }
    $env:PGPASSWORD = $PgPassword
    $cmd = "psql -h $Host -p $Port -U $User -d $Database -f $SqlFile"
    Write-Output "Running: $cmd"
    cmd /c $cmd
    Remove-Item Env:PGPASSWORD
    Write-Output "Applied SQL to $Database"
}

if ($DbType -eq 'sqlite') {
    if (-not $SqliteFile) { Write-Error "Provide -SqliteFile path for sqlite mode."; exit 1 }
    $backup = Backup-Sqlite -File $SqliteFile
    Apply-Sqlite -DbFile $SqliteFile -SqlFile $SqlFile
    Write-Output "Done (sqlite). Keep backup: $backup"
} else {
    if (-not ($PgHost -and $PgUser -and $PgDatabase -and $PgPassword)) { Write-Error "Provide Postgres connection params (PgHost, PgUser, PgDatabase, PgPassword)."; exit 1 }
    $backup = Backup-Postgres -Host $PgHost -Port $PgPort -User $PgUser -Database $PgDatabase
    Apply-Postgres -Host $PgHost -Port $PgPort -User $PgUser -Database $PgDatabase -SqlFile $SqlFile
    Write-Output "Done (postgres). Keep backup: $backup"
}
