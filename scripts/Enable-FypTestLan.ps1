param([string]$InterfaceAlias = 'Wi-Fi')
# Explicit operator step only. Never called automatically by fyp-test.ps1.
$ErrorActionPreference = 'Stop'
$principal = [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Run this reviewed script in Administrator PowerShell after approving private LAN access.'
}
if ((Get-NetConnectionProfile -InterfaceAlias $InterfaceAlias).NetworkCategory -ne 'Private') {
    throw 'Confirm a trusted Private network first; this script does not change network categories.'
}
$listeners = @(Get-NetTCPConnection -State Listen -LocalPort 8002 -ErrorAction Stop)
$owners = @($listeners.OwningProcess | Select-Object -Unique)
if ($owners.Count -ne 1) { throw 'Start the isolated backend loopback-only first.' }
$process = Get-CimInstance Win32_Process -Filter "ProcessId=$($owners[0])"
if ($process.CommandLine -notlike '*backend*manual_android_test.py*--profile*manual-android-*backend-profile.json*' -or
    (Split-Path -Leaf $process.ExecutablePath) -ne 'python.exe') { throw 'Port 8002 is not the expected disposable launcher.' }
$ruleName = 'FYP-Isolated-Private-LAN-8002'
if (Get-NetFirewallRule -Name $ruleName -ErrorAction SilentlyContinue) {
    throw 'Rule already exists. Inspect it instead of overwriting existing firewall settings.'
}
New-NetFirewallRule -Name $ruleName -DisplayName 'FYP isolated private LAN TCP 8002' `
    -Direction Inbound -Action Allow -Enabled True -Profile Private -InterfaceAlias $InterfaceAlias `
    -Protocol TCP -LocalPort 8002 -RemoteAddress LocalSubnet -Program $process.ExecutablePath | Out-Null
Write-Output 'Private LAN transport rule created for isolated TCP 8002 only. This does not authorize attendance.'
