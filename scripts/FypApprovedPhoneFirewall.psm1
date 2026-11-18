Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$script:RuleName = 'FYP Pinned HTTPS 8005 - Approved Test Phone'
$script:RuleGroup = 'FYP-Pinned-HTTPS-Approved-Phone-v1'

function ConvertTo-FypIPv4Number([string]$Address) {
    $ip = $null
    if (-not [Net.IPAddress]::TryParse($Address, [ref]$ip) -or
        $ip.AddressFamily -ne [Net.Sockets.AddressFamily]::InterNetwork -or
        $ip.ToString() -cne $Address) { throw 'INVALID_IPV4' }
    $b = $ip.GetAddressBytes()
    if (-not ($b[0] -eq 10 -or ($b[0] -eq 172 -and $b[1] -ge 16 -and $b[1] -le 31) -or
        ($b[0] -eq 192 -and $b[1] -eq 168))) { throw 'PRIVATE_IPV4_REQUIRED' }
    return ([uint64]$b[0] * 16777216 + [uint64]$b[1] * 65536 + [uint64]$b[2] * 256 + $b[3])
}

function New-FypApprovedPhonePlan {
    param([string]$Serial, [string]$Model, [string]$LaptopIP, [int]$LaptopPrefix,
        [string]$PhoneIP, [int]$PhonePrefix, [string]$SSID, [string]$PhoneSSID,
        [string]$InterfaceAlias, [string]$Program, [string]$CurrentProfile)
    $laptop = ConvertTo-FypIPv4Number $LaptopIP
    $phone = ConvertTo-FypIPv4Number $PhoneIP
    if ($laptop -eq $phone) { throw 'PEER_EQUALS_LAPTOP' }
    foreach ($prefix in @($LaptopPrefix, $PhonePrefix)) {
        if ($prefix -lt 1 -or $prefix -gt 32) { throw 'INVALID_SUBNET_PREFIX' }
        $block = [math]::Pow(2, 32 - $prefix)
        if ([math]::Floor($laptop / $block) -ne [math]::Floor($phone / $block)) {
            throw 'PHONE_NOT_ON_CURRENT_LAN'
        }
    }
    if (-not $SSID -or $SSID -cne $PhoneSSID) { throw 'WIFI_SSID_MISMATCH' }
    if (-not $Serial -or -not $Model -or -not $InterfaceAlias -or
        -not [IO.Path]::IsPathRooted($Program) -or (Split-Path $Program -Leaf) -ne 'python.exe') {
        throw 'DEVICE_OR_BACKEND_IDENTITY_MISSING'
    }
    [pscustomobject][ordered]@{
        Name = $script:RuleName; DisplayName = $script:RuleName; Group = $script:RuleGroup
        Direction = 'Inbound'; Protocol = 'TCP'; LocalPort = 8005; Profile = 'Public'
        Action = 'Allow'; Enabled = 'True'; LocalAddress = $LaptopIP; RemoteAddress = $PhoneIP
        Program = $Program; InterfaceAlias = $InterfaceAlias; EdgeTraversalPolicy = 'Block'
        PolicyStore = 'PersistentStore'
        Serial = $Serial; Model = $Model; SSID = $SSID; CurrentProfile = $CurrentProfile
    }
}

function Get-FypApprovedPhonePlan {
    param([string]$Repository, [string]$Serial = '7732690b', [string]$InterfaceAlias = 'Wi-Fi')
    $adb = Join-Path $env:LOCALAPPDATA 'Android\sdk\platform-tools\adb.exe'
    if (-not (Test-Path -LiteralPath $adb)) { throw 'ADB_NOT_FOUND' }
    $state = & $adb -s $Serial get-state 2>$null
    if ($LASTEXITCODE -ne 0 -or ($state -join '').Trim() -ne 'device') {
        throw 'APPROVED_PHONE_NOT_CONNECTED_NO_RULE_APPLIED'
    }
    $model = (& $adb -s $Serial shell getprop ro.product.model) -join ''
    if ($LASTEXITCODE -ne 0 -or -not $model.Trim()) { throw 'PHONE_MODEL_UNAVAILABLE' }
    $phoneWifi = (& $adb -s $Serial shell cmd wifi status) -join "`n"
    if ($LASTEXITCODE -ne 0 -or $phoneWifi -notmatch '(?m)^Wifi is connected to "([^"\r\n]+)"\s*$') {
        throw 'PHONE_WIFI_NOT_VERIFIED'
    }
    $phoneSSID = $Matches[1]
    $phoneAddresses = (& $adb -s $Serial shell ip -4 addr show wlan0) -join "`n"
    if ($LASTEXITCODE -ne 0) { throw 'PHONE_IP_UNAVAILABLE' }
    $rows = @([regex]::Matches($phoneAddresses, '\binet ([0-9.]+)/([0-9]+)\b'))
    if ($rows.Count -ne 1) { throw 'PHONE_IP_AMBIGUOUS' }
    $profile = @(Get-NetConnectionProfile -InterfaceAlias $InterfaceAlias -ErrorAction Stop)
    $ips = @(Get-NetIPAddress -InterfaceAlias $InterfaceAlias -AddressFamily IPv4 -ErrorAction Stop |
        Where-Object AddressState -eq 'Preferred')
    if ($profile.Count -ne 1 -or $ips.Count -ne 1) { throw 'LAPTOP_NETWORK_AMBIGUOUS' }
    # Fail closed on localized/unrecognized/multiple Wi-Fi interface output.
    $wlan = (& netsh.exe wlan show interfaces) -join "`n"
    if ($LASTEXITCODE -ne 0) { throw 'LAPTOP_WIFI_UNAVAILABLE' }
    $names = @([regex]::Matches($wlan, '(?m)^\s*Name\s*:\s*([^\r\n]+)'))
    $ssids = @([regex]::Matches($wlan, '(?m)^\s*SSID\s*:\s*([^\r\n]+)'))
    if ($names.Count -ne 1 -or $names[0].Groups[1].Value.Trim() -ne $InterfaceAlias -or $ssids.Count -ne 1) {
        throw 'LAPTOP_WIFI_IDENTITY_AMBIGUOUS'
    }
    $config = Join-Path $Repository 'backend\venv\pyvenv.cfg'
    $exe = @(Get-Content -LiteralPath $config | Where-Object { $_ -match '^executable\s*=' })
    if ($exe.Count -ne 1) { throw 'BACKEND_PYTHON_NOT_VERIFIED' }
    $program = ($exe[0] -split '=', 2)[1].Trim()
    if (-not (Test-Path -LiteralPath $program -PathType Leaf)) { throw 'BACKEND_PYTHON_MISSING' }
    $listeners = @(Get-NetTCPConnection -State Listen -LocalPort 8005 -ErrorAction SilentlyContinue)
    foreach ($listener in $listeners) {
        $process = Get-CimInstance Win32_Process -Filter "ProcessId=$($listener.OwningProcess)" -ErrorAction Stop
        if ($process.ExecutablePath -ne $program -or
            $process.CommandLine -notmatch [regex]::Escape((Join-Path $Repository 'backend\original_fyp.py')) -or
            $process.CommandLine -notmatch 'serve-backend' -or
            $listener.LocalAddress -ne $ips[0].IPAddress) { throw 'HTTPS_LISTENER_IDENTITY_MISMATCH' }
    }
    # A stopped backend is allowed: configure its verified executable, never start it.
    New-FypApprovedPhonePlan -Serial $Serial -Model $model.Trim() -LaptopIP $ips[0].IPAddress `
        -LaptopPrefix $ips[0].PrefixLength -PhoneIP $rows[0].Groups[1].Value `
        -PhonePrefix ([int]$rows[0].Groups[2].Value) -SSID $ssids[0].Groups[1].Value.Trim() `
        -PhoneSSID $phoneSSID -InterfaceAlias $InterfaceAlias -Program $program `
        -CurrentProfile ([string]$profile[0].NetworkCategory)
}

function Assert-FypFirewallAdministrator {
    $user = [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
    if (-not $user.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw 'ADMINISTRATOR_POWERSHELL_REQUIRED'
    }
}

function Get-FypOwnedPhoneRule {
    # Enumerate then filter: an absent exact name is not a provider error.
    $rules = @(Get-NetFirewallRule -PolicyStore PersistentStore -ErrorAction Stop |
        Where-Object Name -eq $script:RuleName)
    if ($rules.Count -gt 1 -or ($rules.Count -eq 1 -and $rules[0].Group -ne $script:RuleGroup)) {
        throw 'RULE_NAME_COLLISION_NOT_OWNED_NO_CHANGE'
    }
    if ($rules.Count -eq 1) { return $rules[0] }
}

function Set-FypApprovedPhoneRule {
    param([Parameter(Mandatory)]$Plan, [Parameter(Mandatory)][string]$Approval)
    Assert-FypFirewallAdministrator
    if ($Approval -cne "ALLOW $($Plan.RemoteAddress)") { throw 'EXPLICIT_APPROVAL_REQUIRED_NO_CHANGE' }
    # Revalidate even when invoked directly; never permit a supplied broad plan.
    [void](ConvertTo-FypIPv4Number $Plan.LocalAddress)
    [void](ConvertTo-FypIPv4Number $Plan.RemoteAddress)
    if ($Plan.Name -ne $script:RuleName -or $Plan.Group -ne $script:RuleGroup -or
        $Plan.Profile -ne 'Public' -or $Plan.Protocol -ne 'TCP' -or $Plan.LocalPort -ne 8005 -or
        $Plan.Direction -ne 'Inbound' -or $Plan.Action -ne 'Allow' -or
        $Plan.EdgeTraversalPolicy -ne 'Block' -or $Plan.PolicyStore -ne 'PersistentStore' -or
        -not [IO.Path]::IsPathRooted($Plan.Program) -or (Split-Path $Plan.Program -Leaf) -ne 'python.exe' -or
        -not $Plan.InterfaceAlias -or $Plan.InterfaceAlias -eq 'Any') { throw 'UNSAFE_RULE_PLAN_NO_CHANGE' }
    $existing = Get-FypOwnedPhoneRule
    $args = @{}
    foreach ($key in @('Name','Direction','Protocol','LocalPort','Profile','Action','Enabled',
        'LocalAddress','RemoteAddress','Program','InterfaceAlias','EdgeTraversalPolicy','PolicyStore')) {
        $args[$key] = $Plan.$key
    }
    $description = "FYP exact-peer testing only; approved serial=$($Plan.Serial); SSID=$($Plan.SSID). IP is not device identity. TLS/device authorization remain mandatory."
    if ($existing) {
        Set-NetFirewallRule @args -NewDisplayName $script:RuleName -Description $description -ErrorAction Stop | Out-Null
    } else {
        New-NetFirewallRule @args -DisplayName $script:RuleName -Group $script:RuleGroup `
            -Description $description -ErrorAction Stop | Out-Null
    }
    $saved = Get-FypOwnedPhoneRule
    if (-not $saved -or [string]$saved.Profile -ne 'Public') { throw 'PERSISTENCE_VERIFICATION_FAILED' }
    'PERSISTENT_FYP_PHONE_RULE_SAVED'
}

function Remove-FypApprovedPhoneRule {
    param([string]$Approval)
    Assert-FypFirewallAdministrator
    if ($Approval -cne 'REMOVE') { throw 'EXPLICIT_REMOVAL_APPROVAL_REQUIRED' }
    $existing = Get-FypOwnedPhoneRule
    if ($existing) {
        Remove-NetFirewallRule -Name $script:RuleName -PolicyStore PersistentStore -ErrorAction Stop
        if (Get-FypOwnedPhoneRule) { throw 'RULE_REMOVAL_VERIFICATION_FAILED' }
    }
    'FYP_PHONE_RULE_ABSENT'
}

Export-ModuleMember -Function Get-FypApprovedPhonePlan, New-FypApprovedPhonePlan, `
    Get-FypOwnedPhoneRule, Set-FypApprovedPhoneRule, Remove-FypApprovedPhoneRule
