param([string]$Serial, [ValidateSet('Full','Local')][string]$Mode = 'Full')
$ErrorActionPreference = 'Stop'
$Mode = if ($Mode -eq 'Local') { 'Local' } else { 'Full' }
$python = Join-Path $PSScriptRoot 'backend\venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'Existing backend virtual environment is missing. No fallback used.' }
$arguments = @((Join-Path $PSScriptRoot 'backend\fyp_operator.py'), 'install', '--mode', $Mode)
if ($Serial) { $arguments += @('--serial', $Serial) }
& $python @arguments
exit $LASTEXITCODE
