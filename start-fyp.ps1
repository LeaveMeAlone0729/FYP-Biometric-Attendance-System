param([ValidateSet('start','check','admin-init')][string]$Action = 'start')
$ErrorActionPreference = 'Stop'
$python = Join-Path $PSScriptRoot 'backend\venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'Existing backend virtual environment is missing. No fallback used.' }
& $python (Join-Path $PSScriptRoot 'backend\original_fyp.py') $Action
exit $LASTEXITCODE
