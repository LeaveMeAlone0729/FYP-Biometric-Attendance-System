param([string]$DeviceId = '', [string]$ApiBaseUrl = 'http://10.0.2.2:8000')
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Join-Path $PSScriptRoot 'frontend')
$attendanceFlutterArgs = @('run', "--dart-define=API_BASE_URL=$ApiBaseUrl")
if ($DeviceId) { $attendanceFlutterArgs += @('-d', $DeviceId) }
& flutter @attendanceFlutterArgs
exit $LASTEXITCODE
