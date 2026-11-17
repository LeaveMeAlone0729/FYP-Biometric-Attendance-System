param(
    [string]$Environment = '',
    [ValidateSet(8000,8002)][int]$BackendPort = 8002,
    [switch]$InitAdmin,
    [switch]$CheckOnly
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$panelPython = Join-Path $projectRoot 'backend\venv\Scripts\python.exe'
$panelArgs = @('-B', (Join-Path $projectRoot 'backend\admin_testing_launcher.py'), '--backend-port', [string]$BackendPort)
if ($Environment) { $panelArgs += @('--environment', $Environment) }
if ($InitAdmin) { $panelArgs += '--init-admin' }
if ($CheckOnly) { $panelArgs += '--check-only' }
& $panelPython @panelArgs
exit $LASTEXITCODE
