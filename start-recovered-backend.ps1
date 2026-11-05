param(
    [Parameter(Mandatory=$true)][string]$Profile,
    [string]$ListenHost,
    [int]$Port = 8000,
    [switch]$CheckOnly
)
$ErrorActionPreference = 'Stop'
$recoveryPython = Join-Path $PSScriptRoot 'backend\venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $recoveryPython)) { throw 'Backend virtual environment is required.' }
if (-not $CheckOnly -and [string]::IsNullOrWhiteSpace($ListenHost)) { throw 'Specify the approved existing HTTP ListenHost.' }
$recoveryArgs = @('-B', (Join-Path $PSScriptRoot 'backend\production_app.py'), '--profile', $Profile)
if ($CheckOnly) { $recoveryArgs += '--check-only' }
else { $recoveryArgs += @('--host', $ListenHost, '--port', [string]$Port) }
& $recoveryPython @recoveryArgs
exit $LASTEXITCODE
