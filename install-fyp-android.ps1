param([string]$Serial, [switch]$BuildOnly, [string]$LanIp)
$ErrorActionPreference = 'Stop'
if (-not $BuildOnly -and [string]::IsNullOrWhiteSpace($Serial)) {
    throw 'Specify -Serial using adb devices, or use -BuildOnly to build without installing.'
}
$baseUrl = 'http://127.0.0.1:8000'
if ($LanIp) {
    $address = $null
    if (-not [System.Net.IPAddress]::TryParse($LanIp, [ref]$address) -or
        $address.AddressFamily -ne [System.Net.Sockets.AddressFamily]::InterNetwork -or
        [System.Net.IPAddress]::IsLoopback($address) -or
        -not (Get-NetIPAddress -AddressFamily IPv4 -IPAddress $address.ToString() -ErrorAction SilentlyContinue)) {
        throw 'LanIp must be an IPv4 address assigned to this laptop on the local network.'
    }
    $baseUrl = "http://${address}:8000"
}
$frontend = Join-Path $PSScriptRoot 'frontend'
$properties = Get-Content -LiteralPath (Join-Path $frontend 'android\local.properties')
function PropertyPath([string]$name) {
    $line = $properties | Where-Object { $_.StartsWith($name + '=') } | Select-Object -First 1
    if (-not $line) { throw "Missing $name in existing android/local.properties" }
    return $line.Substring($name.Length + 1).Replace('\\','\').Replace('\:',':')
}
$adb = Join-Path (PropertyPath 'sdk.dir') 'platform-tools\adb.exe'
$flutter = Join-Path (PropertyPath 'flutter.sdk') 'bin\flutter.bat'
if (-not (Test-Path -LiteralPath $adb)) { throw 'Installed SDK adb.exe not found.' }
if (-not (Test-Path -LiteralPath $flutter)) { throw 'Installed Flutter SDK not found.' }
if (-not $BuildOnly) {
    try {
        $ready = Invoke-RestMethod 'http://127.0.0.1:8000/local-fyp/identity' -TimeoutSec 5
    } catch {
        if ($null -ne $_.Exception.Response -and [int]$_.Exception.Response.StatusCode -eq 404) {
            throw "Port 8000 does not serve the original FYP identity route. Stop the current backend gracefully, then run '.\backend\venv\Scripts\python.exe .\backend\original_fyp.py serve-backend' from the repository root."
        }
        throw
    }
    if ($ready.environment -ne 'original' -or $ready.db_port -ne 3306 -or $ready.database -ne 'attendance_proposal_xampp') {
        throw 'Original backend identity is not ready. No installation performed.'
    }
    $state = & $adb -s $Serial get-state 2>$null
    if ($LASTEXITCODE -ne 0 -or $state -ne 'device') { throw "Selected device $Serial is disconnected or unauthorized." }
    if ($LanIp) {
        Invoke-RestMethod "$baseUrl/config" -TimeoutSec 5 | Out-Null
    } else {
        & $adb -s $Serial reverse tcp:8000 tcp:8000
        if ($LASTEXITCODE -ne 0) { throw 'ADB reverse failed.' }
    }
}
Push-Location $frontend
try {
    & $flutter build apk --debug "--dart-define=API_BASE_URL=$baseUrl"
    if ($LASTEXITCODE -ne 0) { throw 'APK build failed.' }
    if (-not $BuildOnly) {
        & $adb -s $Serial install -r (Join-Path $frontend 'build\app\outputs\flutter-apk\app-debug.apk')
        if ($LASTEXITCODE -ne 0) { throw 'Install failed. Do not uninstall or clear app data; resolve signing/version compatibility.' }
    }
} finally { Pop-Location }
Write-Output "APK backend URL is $baseUrl."
if (-not $LanIp) {
    Write-Output 'USB loopback is transport only and cannot authorize campus attendance.'
}
