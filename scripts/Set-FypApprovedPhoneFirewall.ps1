param([string]$Serial = '7732690b', [string]$InterfaceAlias = 'Wi-Fi', [switch]$PlanOnly)
$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSScriptRoot 'FypApprovedPhoneFirewall.psm1') -Force
$root = Split-Path -Parent $PSScriptRoot
$plan = Get-FypApprovedPhonePlan -Repository $root -Serial $Serial -InterfaceAlias $InterfaceAlias
Write-Output 'EXACT PROPOSED RULE (no firewall change yet):'
$plan | ConvertTo-Json
$existing = Get-FypOwnedPhoneRule
if ($existing) { Write-Output 'Only this tool-owned persistent rule will be updated; no other rule is changed.' }
Write-Output 'Public profile only. No attendance authorization, mDNS, HTTP 8000, admin or gateway access is added.'
if ($PlanOnly) { return }
$approval = Read-Host "Verify model, serial, Wi-Fi and both IPs above. Type ALLOW $($plan.RemoteAddress) to apply"
if ($approval -cne "ALLOW $($plan.RemoteAddress)") { throw 'NOT_APPROVED_NO_CHANGE' }
# Prevent consent for one network/address from being applied after a network change.
$fresh = Get-FypApprovedPhonePlan -Repository $root -Serial $Serial -InterfaceAlias $InterfaceAlias
if (($fresh | ConvertTo-Json -Compress) -cne ($plan | ConvertTo-Json -Compress)) {
    throw 'NETWORK_OR_DEVICE_CHANGED_NO_RULE_APPLIED_RUN_AGAIN'
}
Set-FypApprovedPhoneRule -Plan $fresh -Approval $approval
Write-Output 'Saved in PersistentStore (survives restart). No restart performed or required. Test phone TCP/pinned TLS and My Device separately.'
