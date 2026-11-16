param([ValidateSet('Full','Local')][string]$Mode = 'Full')
$ErrorActionPreference = 'Stop'
$Mode = if ($Mode -eq 'Local') { 'Local' } else { 'Full' }
$python = Join-Path $PSScriptRoot 'backend\venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'Existing backend virtual environment is missing. No fallback used.' }
& $python (Join-Path $PSScriptRoot 'backend\fyp_operator.py') start --mode $Mode
exit $LASTEXITCODE
