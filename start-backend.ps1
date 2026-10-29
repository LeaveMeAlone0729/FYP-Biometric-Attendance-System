param([int]$Port = 8000)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Join-Path $PSScriptRoot 'backend')
$attendancePython = Join-Path $PWD 'venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $attendancePython)) { throw 'Create backend\venv and install backend\requirements.txt first. See README.md.' }
& $attendancePython -m uvicorn main:app --host 0.0.0.0 --port $Port --no-proxy-headers --reload
exit $LASTEXITCODE
