param([ValidateSet('start','check','admin-init')][string]$Action = 'start')
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot 'backend\venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'Existing backend virtual environment is missing. No fallback used.' }
& $python (Join-Path $projectRoot 'backend\original_fyp.py') $Action
exit $LASTEXITCODE
