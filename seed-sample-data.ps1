param([string]$AsOf)
$ErrorActionPreference = 'Stop'
$attendancePython = Join-Path $PSScriptRoot 'backend\venv\Scripts\python.exe'
$seedRuntime = Join-Path $PSScriptRoot '.work\seed-runtime'
$previousPythonPath = $env:PYTHONPATH
try {
    $usableVenv = $false
    if (Test-Path -LiteralPath $attendancePython) {
        try {
            & $attendancePython --version 2>$null | Out-Null
            $usableVenv = $LASTEXITCODE -eq 0
        }
        catch { $usableVenv = $false }
    }
    if (-not $usableVenv) {
        if (-not (Test-Path -LiteralPath $seedRuntime)) {
            throw 'The backend Python environment is unavailable. Restore it, or install sqlalchemy mysql-connector-python cryptography tzdata into .work\seed-runtime using a working Python.'
        }
        $attendancePython = (Get-Command python -ErrorAction Stop).Source
        $env:PYTHONPATH = $seedRuntime
    }
    $seedArguments = @((Join-Path $PSScriptRoot 'backend\seed_sample.py'))
    if ($AsOf) { $seedArguments += @('--as-of', $AsOf) }
    & $attendancePython @seedArguments
    if ($LASTEXITCODE -ne 0) { throw 'Sample data seeding failed; check the error above.' }
}
finally {
    $env:PYTHONPATH = $previousPythonPath
}
