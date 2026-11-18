# Offline Pester 3+ tests. Every firewall mutation and admin check is mocked.
Import-Module (Join-Path (Split-Path $PSScriptRoot -Parent) 'FypApprovedPhoneFirewall.psm1') -Force
InModuleScope FypApprovedPhoneFirewall {
    Describe 'FYP exact-peer persistent firewall preparation' {
        function TestPlan {
            New-FypApprovedPhonePlan -Serial 'synthetic-phone' -Model 'Test Android' `
                -LaptopIP '172.22.125.187' -LaptopPrefix 24 -PhoneIP '172.22.125.188' -PhonePrefix 24 `
                -SSID 'Authorized school test' -PhoneSSID 'Authorized school test' `
                -InterfaceAlias 'Wi-Fi' -Program 'C:\FYP\Python\python.exe' -CurrentProfile Public
        }
        BeforeEach {
            $script:saved = $null
            Mock Assert-FypFirewallAdministrator -ModuleName FypApprovedPhoneFirewall {}
            Mock Get-NetFirewallRule -ModuleName FypApprovedPhoneFirewall { if ($null -ne $script:saved) { $script:saved } }
            Mock New-NetFirewallRule -ModuleName FypApprovedPhoneFirewall {
                $script:saved = [pscustomobject]@{
                    Name = 'FYP Pinned HTTPS 8005 - Approved Test Phone'
                    Group = 'FYP-Pinned-HTTPS-Approved-Phone-v1'; Profile = 'Public'
                }
            }
            Mock Set-NetFirewallRule -ModuleName FypApprovedPhoneFirewall {}
            Mock Remove-NetFirewallRule -ModuleName FypApprovedPhoneFirewall { $script:saved = $null }
        }
        It 'prepares an exact peer, executable, interface and local IP without a running backend' {
            $p = TestPlan
            $p.RemoteAddress | Should Be '172.22.125.188'
            $p.LocalAddress | Should Be '172.22.125.187'
            $p.Profile | Should Be Public
            $p.PolicyStore | Should Be PersistentStore
            $p.LocalPort | Should Be 8005
            $p.Program | Should Be 'C:\FYP\Python\python.exe'
            Assert-MockCalled New-NetFirewallRule -Scope It -Times 0 -Exactly
        }
        It 'rejects unknown, broad, noncanonical or public peer addresses' {
            foreach ($bad in @('Any', '172.22.0.0/16', '172.022.125.188', '8.8.8.8', '')) {
                { ConvertTo-FypIPv4Number $bad } | Should Throw
            }
        }
        It 'rejects a different subnet or Wi-Fi identity' {
            { New-FypApprovedPhonePlan -Serial x -Model Android -LaptopIP '172.22.125.187' -LaptopPrefix 24 `
                -PhoneIP '172.22.126.188' -PhonePrefix 24 -SSID a -PhoneSSID a `
                -InterfaceAlias Wi-Fi -Program 'C:\Python\python.exe' } | Should Throw
            { New-FypApprovedPhonePlan -Serial x -Model Android -LaptopIP '172.22.125.187' -LaptopPrefix 24 `
                -PhoneIP '172.22.125.188' -PhonePrefix 24 -SSID a -PhoneSSID b `
                -InterfaceAlias Wi-Fi -Program 'C:\Python\python.exe' } | Should Throw
        }
        It 'refuses a missing or wrong approval without mutation' {
            { Set-FypApprovedPhoneRule -Plan (TestPlan) -Approval NO } | Should Throw
            Assert-MockCalled New-NetFirewallRule -Scope It -Times 0 -Exactly
            Assert-MockCalled Set-NetFirewallRule -Scope It -Times 0 -Exactly
        }
        It 'creates only the approved persistent TCP 8005 Public rule' {
            Set-FypApprovedPhoneRule -Plan (TestPlan) -Approval 'ALLOW 172.22.125.188' | Should Be PERSISTENT_FYP_PHONE_RULE_SAVED
            Assert-MockCalled New-NetFirewallRule -Scope It -Times 1 -Exactly -ParameterFilter {
                $RemoteAddress -eq '172.22.125.188' -and $LocalAddress -eq '172.22.125.187' -and
                $LocalPort -eq 8005 -and $Protocol -eq 'TCP' -and $Profile -eq 'Public' -and
                $Program -eq 'C:\FYP\Python\python.exe' -and $PolicyStore -eq 'PersistentStore'
            }
        }
        It 'repeated application updates only its owned rule and never creates duplicates' {
            $p = TestPlan
            Set-FypApprovedPhoneRule -Plan $p -Approval 'ALLOW 172.22.125.188' | Out-Null
            Set-FypApprovedPhoneRule -Plan $p -Approval 'ALLOW 172.22.125.188' | Out-Null
            Assert-MockCalled New-NetFirewallRule -Scope It -Times 1 -Exactly
            Assert-MockCalled Set-NetFirewallRule -Scope It -Times 1 -Exactly -ParameterFilter {
                $Name -eq 'FYP Pinned HTTPS 8005 - Approved Test Phone' -and $RemoteAddress -eq '172.22.125.188'
            }
        }
        It 'requires new exact consent when the phone IP changes' {
            $p = TestPlan; $p.RemoteAddress = '172.22.125.189'
            { Set-FypApprovedPhoneRule -Plan $p -Approval 'ALLOW 172.22.125.188' } | Should Throw
            Assert-MockCalled Set-NetFirewallRule -Scope It -Times 0 -Exactly
        }
        It 'updates the one owned remote address only after matching new approval' {
            $p = TestPlan
            Set-FypApprovedPhoneRule -Plan $p -Approval 'ALLOW 172.22.125.188' | Out-Null
            $p.RemoteAddress = '172.22.125.189'
            Set-FypApprovedPhoneRule -Plan $p -Approval 'ALLOW 172.22.125.189' | Out-Null
            Assert-MockCalled Set-NetFirewallRule -Scope It -Times 1 -Exactly -ParameterFilter {
                $Name -eq 'FYP Pinned HTTPS 8005 - Approved Test Phone' -and
                $RemoteAddress -eq '172.22.125.189' -and $Profile -eq 'Public' -and $LocalPort -eq 8005
            }
        }
        It 'refuses to overwrite an unowned same-name rule' {
            $script:saved = [pscustomobject]@{Name=$script:RuleName;Group='Unrelated app';Profile='Public'}
            { Set-FypApprovedPhoneRule -Plan (TestPlan) -Approval 'ALLOW 172.22.125.188' } | Should Throw
            Assert-MockCalled Set-NetFirewallRule -Scope It -Times 0 -Exactly
            Assert-MockCalled Remove-NetFirewallRule -Scope It -Times 0 -Exactly
        }
        It 'rejects attempts to broaden the port, profile or peer' {
            foreach ($property in @('Profile', 'LocalPort', 'RemoteAddress', 'InterfaceAlias')) {
                $p = TestPlan
                switch ($property) {
                    Profile { $p.Profile = 'Any' }
                    LocalPort { $p.LocalPort = 8000 }
                    RemoteAddress { $p.RemoteAddress = 'Any' }
                    InterfaceAlias { $p.InterfaceAlias = 'Any' }
                }
                { Set-FypApprovedPhoneRule -Plan $p -Approval "ALLOW $($p.RemoteAddress)" } | Should Throw
            }
            Assert-MockCalled New-NetFirewallRule -Scope It -Times 0 -Exactly
        }
        It 'removes only its own rule, safely repeats removal and needs no connected phone' {
            Set-FypApprovedPhoneRule -Plan (TestPlan) -Approval 'ALLOW 172.22.125.188' | Out-Null
            Remove-FypApprovedPhoneRule -Approval REMOVE | Should Be FYP_PHONE_RULE_ABSENT
            Remove-FypApprovedPhoneRule -Approval REMOVE | Should Be FYP_PHONE_RULE_ABSENT
            Assert-MockCalled Remove-NetFirewallRule -Scope It -Times 1 -Exactly
        }
        It 'refuses to remove a same-name rule owned by another tool' {
            $script:saved = [pscustomobject]@{Name=$script:RuleName;Group='Unrelated app';Profile='Public'}
            { Remove-FypApprovedPhoneRule -Approval REMOVE } | Should Throw
            Assert-MockCalled Remove-NetFirewallRule -Scope It -Times 0 -Exactly
        }
    }
}
