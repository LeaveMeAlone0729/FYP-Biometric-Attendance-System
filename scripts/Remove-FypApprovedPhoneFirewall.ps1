param([switch]$PlanOnly)
$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSScriptRoot 'FypApprovedPhoneFirewall.psm1') -Force
$rule = Get-FypOwnedPhoneRule
if (-not $rule) { Write-Output 'FYP_PHONE_RULE_ALREADY_ABSENT'; return }
$rule | Select-Object Name, DisplayName, Profile, Enabled | ConvertTo-Json
Write-Output 'Removes only this tool-owned approved-phone rule. Private rules and earlier temporary rules are untouched.'
if ($PlanOnly) { return }
$approval = Read-Host 'Type REMOVE to remove this rule after your presentation'
Remove-FypApprovedPhoneRule -Approval $approval
