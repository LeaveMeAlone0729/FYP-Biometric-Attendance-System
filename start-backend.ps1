param([int]$Port = 8000)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Join-Path $PSScriptRoot 'backend')
$attendancePython = Join-Path $PWD 'venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $attendancePython)) { throw 'Create backend\venv with Python 3.12 and install backend\requirements.txt first.' }
& $attendancePython -B -m modules.biometrics.migration
if ($LASTEXITCODE -ne 0) { throw 'Could not prepare the liveness schema. Check that MySQL is running.' }
& $attendancePython -B -m modules.biometrics.model_assets
if ($LASTEXITCODE -ne 0) { throw 'Biometric model verification failed. Check the model download error above.' }
& $attendancePython -m uvicorn main:app --host 0.0.0.0 --port $Port --no-proxy-headers --reload
exit $LASTEXITCODE
