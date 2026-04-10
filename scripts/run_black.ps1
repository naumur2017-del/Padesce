$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$python = "C:\Users\yvest\AppData\Local\Programs\Python\Python313\python.exe"
$packages = Join-Path $root ".black-packages"

if (-not (Test-Path $python)) {
    throw "Python 3.13 introuvable: $python"
}

if (-not (Test-Path $packages)) {
    throw "Packages black locaux introuvables: $packages"
}

$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONPATH = $packages

# Force a single worker to avoid the multiprocessing hangs seen on this machine.
& $python -m black -W 1 @args
exit $LASTEXITCODE
