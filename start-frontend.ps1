param([string]$DeviceId = '', [string]$ApiBaseUrl = 'http://127.0.0.1:8000')
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Join-Path $PSScriptRoot 'frontend')

# Forward the API through the connected Android debugging transport (USB or Wi-Fi).
$apiUri = [uri]$ApiBaseUrl
if ($apiUri.Host -in @('127.0.0.1', 'localhost')) {
    $adbCommand = Get-Command adb -ErrorAction SilentlyContinue
    $adbPath = if ($adbCommand) { $adbCommand.Source } else { $null }
    if (-not $adbPath) {
        foreach ($sdkRoot in @($env:ANDROID_HOME, $env:ANDROID_SDK_ROOT, (Join-Path $env:LOCALAPPDATA 'Android\sdk'))) {
            if (-not $sdkRoot) { continue }
            $candidate = Join-Path $sdkRoot 'platform-tools\adb.exe'
            if (Test-Path -LiteralPath $candidate) { $adbPath = $candidate; break }
        }
    }
    if (-not $adbPath) { throw 'Android platform-tools were not found. Set ANDROID_HOME to your Android SDK folder.' }
    $deviceOutput = & $adbPath devices
    if ($LASTEXITCODE -ne 0) { throw 'Could not list Android devices. Check your debugging connection.' }
    $connectedDevices = @($deviceOutput | Select-String '^(\S+)\s+device\s*$' | ForEach-Object { $_.Matches[0].Groups[1].Value })
    if (-not $DeviceId) {
        if ($connectedDevices.Count -eq 0) { throw 'Connect your Android phone with USB or wireless debugging first.' }
        if ($connectedDevices.Count -gt 1) { throw 'Multiple Android devices are connected. Supply -DeviceId using an ID from adb devices.' }
        $DeviceId = $connectedDevices[0]
    }
    if ($DeviceId -notin $connectedDevices) { throw "Android device '$DeviceId' is not connected. Use an ID from adb devices." }
    $apiPort = "tcp:$($apiUri.Port)"
    & $adbPath -s $DeviceId reverse $apiPort $apiPort
    if ($LASTEXITCODE -ne 0) { throw 'API port forwarding failed. Reconnect wireless debugging and try again.' }
    Write-Host "API forwarding ready: $ApiBaseUrl"
}

$attendanceFlutterArgs = @('run', "--dart-define=API_BASE_URL=$ApiBaseUrl")
if ($DeviceId) { $attendanceFlutterArgs += @('-d', $DeviceId) }
& flutter @attendanceFlutterArgs
exit $LASTEXITCODE
