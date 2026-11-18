param([string]$Serial, [switch]$BuildOnly, [string]$LanIp, [string]$PublicApiUrl,
      [ValidateSet('Full','Local')][string]$Mode = 'Full', [string]$ExpectedIdentity)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
if (-not $BuildOnly -and [string]::IsNullOrWhiteSpace($Serial)) {
    throw 'Specify -Serial using adb devices, or use -BuildOnly to build without installing.'
}
$baseUrl = 'http://127.0.0.1:8000'
if ($PublicApiUrl) {
    $publicUri = $null
    if (-not [Uri]::TryCreate($PublicApiUrl, [UriKind]::Absolute, [ref]$publicUri) -or
        ($publicUri.Scheme -ne 'https' -and -not ($Mode -eq 'Local' -and $publicUri.Scheme -eq 'http')) -or $publicUri.UserInfo -or
        $publicUri.AbsolutePath -ne '/' -or $publicUri.Query -or $publicUri.Fragment -or -not $LanIp) {
        throw 'PublicApiUrl must be an HTTPS origin without credentials; also specify the classroom LanIp.'
    }
    $PublicApiUrl = $PublicApiUrl.TrimEnd('/')
}
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
if ($Mode -eq 'Local') {
    if (-not $LanIp -or $PublicApiUrl -ne $baseUrl) { throw 'LOCAL mode requires identical explicit LAN HTTP origins for general and classroom APIs.' }
    $octets = ([System.Net.IPAddress]::Parse($LanIp)).GetAddressBytes()
    if (-not ($octets[0] -eq 10 -or ($octets[0] -eq 172 -and $octets[1] -ge 16 -and $octets[1] -le 31) -or ($octets[0] -eq 192 -and $octets[1] -eq 168))) {
        throw 'LOCAL HTTP builds require a private RFC1918 LAN IPv4 address.'
    }
    if (-not $BuildOnly -and $ExpectedIdentity -notmatch '^[0-9a-f]{64}$') { throw 'Use fyp-install.ps1 -Mode Local to supply the verified Local backend identity.' }
}
$frontend = Join-Path $projectRoot 'frontend'
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
    if ($Mode -eq 'Local') {
        if ($ready.environment -ne 'partner_local' -or $ready.database -eq 'attendance_proposal_xampp' -or $ready.identity -ne $ExpectedIdentity) {
            throw 'Verified Local backend identity mismatch. No installation performed.'
        }
    } elseif ($ready.environment -ne 'original' -or $ready.db_port -ne 3306 -or $ready.database -ne 'attendance_proposal_xampp') {
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
    $defines = @("--dart-define=API_BASE_URL=$baseUrl", "--dart-define=CLASSROOM_API_BASE_URL=$baseUrl")
    if ($PublicApiUrl) { $defines += "--dart-define=PUBLIC_API_BASE_URL=$PublicApiUrl" }
    $localBuild = if ($Mode -eq 'Local') { 'true' } else { 'false' }
    $defines += "--dart-define=FYP_LOCAL_MODE=$localBuild"
    if (-not $BuildOnly) {
        # Public certificates only, from the operator's existing private identity pin.
        # Provisioning is never called here. A missing profile keeps explicit legacy mode.
        $python = Join-Path $projectRoot 'backend\venv\Scripts\python.exe'
        $trust = & $python (Join-Path $projectRoot 'backend\lan_discovery.py') export --mode $Mode --expected-identity $ready.identity
        if ($LASTEXITCODE -ne 0) { throw 'LAN discovery trust validation failed; no fallback or installation.' }
        if ($trust) {
            $trustB64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes(($trust -join "`n")))
            $defines += "--dart-define=FYP_LAN_TRUST_B64=$trustB64"
        }
    }
    & $flutter build apk --debug @defines
    if ($LASTEXITCODE -ne 0) { throw 'APK build failed.' }
    if (-not $BuildOnly) {
        # A long build must not install a now-stale LAN configuration.
        if ($LanIp -and -not (Get-NetIPAddress -AddressFamily IPv4 -IPAddress $LanIp -ErrorAction SilentlyContinue)) {
            throw 'Laptop LAN address changed during build. No installation performed; retry with the current Wi-Fi address.'
        }
        $identityAfterBuild = Invoke-RestMethod 'http://127.0.0.1:8000/local-fyp/identity' -TimeoutSec 5
        if ($identityAfterBuild.identity -ne $ready.identity) { throw 'Backend identity changed during build. No installation performed.' }
        $stateAfterBuild = & $adb -s $Serial get-state 2>$null
        if ($LASTEXITCODE -ne 0 -or $stateAfterBuild -ne 'device') { throw 'Selected Android device disconnected during build. No installation performed.' }
        & $adb -s $Serial install -r (Join-Path $frontend 'build\app\outputs\flutter-apk\app-debug.apk')
        if ($LASTEXITCODE -ne 0) { throw 'Install failed. Do not uninstall or clear app data; resolve signing/version compatibility.' }
    }
} finally { Pop-Location }
Write-Output "APK backend URL is $baseUrl."
Write-Output "APK mode is $Mode."
if (-not $LanIp) {
    Write-Output 'USB loopback is transport only and cannot authorize campus attendance.'
}
