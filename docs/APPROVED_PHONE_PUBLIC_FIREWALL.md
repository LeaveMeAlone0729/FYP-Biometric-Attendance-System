# Persistent Public Wi-Fi access for the approved FYP test phone

This is an explicit operator configuration, not part of startup. It opens only
direct pinned HTTPS TCP 8005. It never starts a service, changes a network profile,
or grants attendance permission. No rule was applied during preparation.

## Previous successful test

The temporary rule `FYP-Temp-Public-8005-7732690b-20261118` allowed a single
verified phone and laptop address, TCP 8005, Public profile, Wi-Fi interface and
the existing backend Python executable. Phone TCP, pinned TLS, My Device and
Wi-Fi off/on recovery passed. Its old addresses are **not** reused here.
The existing Private-profile rule is preserved.

## Files

- `scripts/Set-FypApprovedPhoneFirewall.ps1`: inspect, display, approve and apply.
- `scripts/Remove-FypApprovedPhoneFirewall.ps1`: inspect and remove only its rule.
- `scripts/FypApprovedPhoneFirewall.psm1`: shared validation and ownership checks.
- `scripts/tests/FypApprovedPhoneFirewall.Tests.ps1`: offline mocked tests.

## At school: one command

Connect the intended Xiaomi by USB, unlock it and authorize USB debugging. Connect
both laptop and phone to the intended authorized Wi-Fi. Open **PowerShell 7 as
Administrator** in the repository, then run:

```powershell
.\scripts\Set-FypApprovedPhoneFirewall.ps1
```

The default intended serial is `7732690b`. A different explicitly selected testing
device requires `-Serial <its-adb-serial>` and operator review of its model/serial.
The script reads the phone's current Wi-Fi SSID and IPv4 through ADB; it never
accepts a manually supplied remote IP. It verifies the laptop Wi-Fi identity,
checks both addresses are private and mutually on their current subnets, derives
the Python executable from this checkout's virtual environment and, if 8005 is
running, verifies the listener's original FYP launcher and address.

Review the displayed exact rule, phone model/serial, SSID and both IPs. To apply,
type the exact prompt text `ALLOW <displayed-phone-IP>`. The script rereads the
network/device information after consent and refuses changes during the prompt.
There is no automatic address update or unattended approval switch.

For a read-only preview:

```powershell
.\scripts\Set-FypApprovedPhoneFirewall.ps1 -PlanOnly
```

A disconnected phone produces an error and no rule. A stopped backend is allowed
for configuration; it is never started by these scripts. Multiple/unrecognized
Wi-Fi interfaces, unknown/localized SSID output, unavailable addresses, a mismatched
SSID/subnet, or another process using 8005 fail closed. No scanning of a subnet is
performed. Enterprise Wi-Fi/client isolation may still prevent peer access.

## Exact persistent rule

| Field | Value |
|---|---|
| Name and display name | FYP Pinned HTTPS 8005 - Approved Test Phone |
| Ownership group | FYP-Pinned-HTTPS-Approved-Phone-v1 |
| Store | PersistentStore |
| Direction / action | Inbound / Allow |
| Profile | Public only |
| Protocol / port | TCP / local 8005 only |
| Remote address | One ADB-verified phone IPv4 |
| Local address | Current verified laptop Wi-Fi IPv4 |
| Interface | Selected verified Wi-Fi interface |
| Program | Existing backend Python executable |
| Edge traversal | Block |

Repeated approved applications update the same owned rule, without duplicates.
A same-name rule lacking this tool's ownership group is never adopted or changed.
Private rules, historical temporary rules, mDNS UDP 5353, HTTP 8000, admin 8003 and
gateway 8004 are untouched. Unrelated rules are never changed.

PersistentStore survives reboot; the scripts do **not** reboot to test it.
The backend must separately be running with its normal pinned HTTPS configuration.
Private-profile traffic continues using existing Private rules. This Public rule
does not become active on a Private network.

## After applying

1. Test phone-to-laptop TCP 8005.
2. In Flutter My Device, verify the paired server at the displayed laptop IP if
   automatic discovery is unavailable. mDNS access is **not** added by this rule.
3. Confirm My Device loads, then test Wi-Fi off/on and refresh.
4. Keep backend CIDR/Wi-Fi, signatures, PIN, face/PAD and attendance checks unchanged.

TLS pinning and backend environment identity remain mandatory. An IP rule is not
cryptographic phone identity: DHCP may later assign that address to someone else.
Recheck the actual phone before testing. If **either** address, Wi-Fi interface or
backend executable changes, rerun the script and approve the newly displayed
scope. Never broaden it to Any or a classroom subnet. Rules do not automatically
authorize a school network or bypass client isolation.

## Remove after the presentation / rollback

In Administrator PowerShell in the repository:

```powershell
.\scripts\Remove-FypApprovedPhoneFirewall.ps1
```

Type `REMOVE` when prompted. No phone or running backend is needed. Removal is
idempotent and refuses a same-name unowned rule. This is also the rollback if
connectivity testing fails; no existing rules need restoration because they were
never changed.

To disable instead (only after confirming the rule's ownership group above):

```powershell
Disable-NetFirewallRule -PolicyStore PersistentStore -Name 'FYP Pinned HTTPS 8005 - Approved Test Phone'
```

## Preparation validation

Offline tests use synthetic addresses and mocked firewall/admin operations.
They cover exact scope, invalid/broad addresses, wrong Wi-Fi/subnet, explicit
consent, changed phone IP, owned-rule updates, collision rejection and repeatable
removal. Live preparation uses PlanOnly; no active firewall mutation is permitted.
Actual school reachability and reboot persistence are not claimed physically tested.

Preparation results (18 November 2026): **12 offline tests passed**; all four
PowerShell files parsed successfully; Git whitespace check passed. A real
PlanOnly preview detected Xiaomi `7732690b` / `2410CRP4CG` at home address
`192.168.0.94`, laptop `192.168.0.162`, SSID `Ultraman_yap_5Ghz`, Private profile,
with the backend stopped. A deliberately nonexistent serial was rejected without
mutation. Before/after active-firewall snapshots matched. These addresses are
historical preview evidence, not defaults or approvals for school.
