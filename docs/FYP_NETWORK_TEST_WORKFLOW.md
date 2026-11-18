# Isolated FYP network workflow

This guide supersedes the device-IP-specific LAN setup in
TABLET_LAN_TEST_READINESS.md. Reachability and attendance authorization are separate.
All commands below run from `C:\FYP\FYP-Biometric-Attendance-System` on SH.

Use PowerShell 7 for the .ps1 wrapper. Windows PowerShell 5 currently blocks script
files on this laptop; use `backend\venv\Scripts\python.exe -B backend\fyp_test.py`
with the same arguments instead of changing execution policy. See
[FYP_STARTUP_IDENTITY_FIX.md](FYP_STARTUP_IDENTITY_FIX.md) for lifecycle test evidence
and the exact supervisor PASS/FAIL sequence. A stopped `status` is expected to
return JSON STOPPED/BACKEND_NOT_RUNNING with exit code 1.

## Two backends: do not mix them

The observed port 8000 process runs `uvicorn main:app` and uses the original
default configuration (`attendance_proposal_xampp`, port 3306, root, DEMO_MODE).
It was inspected through process/configuration metadata only, never queried or
restarted. Do not use start-backend.ps1 or the original manage_network_policy.py
for this disposable exercise: those commands use original Settings/.env defaults.

The new wrapper uses only the existing private profile at
`C:\FYP\DB-DeviceManagement\manual-android-20261106-033334-1f0285`.
FastAPI is 8002, database is `fypdevicemgmt_restore_a199e7f82903` on loopback 3322,
phpMyAdmin is loopback 8082, and FYPTEST001 is synthetic. Runtime credentials,
the disposable encryption key and all existing test enrollments are retained.
There is no production fallback. ACCOUNT_BOUND_FYP remains a demonstration
assurance level, not institution-verified identity.

## Start once, then use any local test devices

```powershell
.\fyp-test.ps1 start --loopback
.\fyp-test.ps1 status
```

One-time administrator operation, only after explicit approval of private LAN
access (approval was given in this chat):

```powershell
.\Enable-FypTestLan.ps1 -InterfaceAlias 'Wi-Fi'
```

It only adds `FYP-Isolated-Private-LAN-8002`: TCP 8002, the actual disposable
Python executable, Private profile, Wi-Fi and LocalSubnet. It never changes
network categories, other rules, router settings or port 8000. It refuses to
overwrite an existing rule; inspect existing settings instead. This is a transport
rule, not a student-device list and not attendance authorization. A new device
does not need an individual rule. A different adapter may need a separately
approved one-time transport rule; Public Wi-Fi must not be silently reclassified.

Start/restart the isolated backend with automatically selected Private LAN address:

```powershell
.\fyp-test.ps1 start --lan
```

This starts MariaDB first, checks its port/datadir identity, then starts FastAPI
and waits for actual HTTP readiness. Only the disposable backend is restarted
when changing listener mode. Loopback and the specific LAN address listen on
8002; never 0.0.0.0. Database and phpMyAdmin stay loopback-only. No tunnel exists.
The returned `api_base_url` is the value to compile into Flutter. If multiple
Private adapters exist, use `start --lan --interface 'Wi-Fi'`.

The old `clients` allowlist is retired. Explicit `start --lan` archives the old
listener JSON and replaces it with adapter address/subnet metadata only; it does
not edit student/device bindings. Direct use of a legacy nonempty clients list
fails with a clear instruction rather than silently changing access. The old
external Start-TabletBackend.py is obsolete and should not be used.

## Configure attendance authorization independently

For multiple simultaneous CIDRs, use named `policy add`, `disable --id` and
`remove --id` commands in [FYP_MULTIPLE_NETWORK_POLICIES.md](FYP_MULTIPLE_NETWORK_POLICIES.md).
All rows share the existing backend policy store. Remove retires the row while
preserving references; `policy list --all` shows retired rows.

Save the previous simulation policy before changing it (the output must not exist):

```powershell
.\fyp-test.ps1 policy export --output C:\FYP\network-policy-before.json
.\fyp-test.ps1 policy list
```

For an explicitly approved **home-LAN simulation**, use the actual test CIDR
shown by `Get-NetIPAddress -InterfaceAlias Wi-Fi -AddressFamily IPv4`:

```powershell
# Example only: this is NOT an approved university network.
.\fyp-test.ps1 policy set --cidr 192.168.0.0/24 --simulation
.\fyp-test.ps1 policy list
.\fyp-test.ps1 policy disable
.\fyp-test.ps1 policy enable
```

`set` without --id targets `fyp-simulation`, named SIMULATION ONLY - FYP test network.
No policy is seeded automatically. These commands use the existing NetworkPolicy,
put_policy and NetworkPolicyEvent architecture, with canonical ipaddress validation
and transactions. There is no second policy store or student policy-management API.
IPv6 attendance policies can also be configured where the deployment provides
actual IPv6 peers. This local launcher currently binds IPv4 only.

The offline operator uses the existing private admin credential, never sent to
Flutter or placed in command arguments. The web backend retains its limited
runtime account (policy SELECT, not policy administration). The operator pins
3322/schema/account/version/datadir and blocks production-port connections before
networking. Its admin credential is confined to the disposable instance, but
should still be kept private; this is not a public admin service.

Other existing enabled policies remain effective and are shown by `list`. Review
all enabled policies rather than assuming the simulation row is the only one.
Changing an enabled policy persists in MariaDB and affects the next verification;
an earlier diagnostic or preflight PASS cannot replace the final fresh check.

Restore the prior simulation state:

```powershell
.\fyp-test.ps1 policy restore --input C:\FYP\network-policy-before.json
```

If the snapshot had no simulation row, restoration disables the newly created
row rather than deleting referenced policy/audit history. It does not alter other
policies. Listener backups are kept as lan-listener.before-*.json in the private
environment; the database profile/key never changes when switching networks.

## Android Studio / Flutter

Create/list/close test attendance windows with the same wrapper's `session`
commands in [FYP_SESSION_OPERATOR.md](FYP_SESSION_OPERATOR.md). Generated PINs
are shown only on successful creation; existing attendance history is retained.

Enable USB debugging on the intended disposable tablet and confirm its serial.
Join the same trusted LAN and check this URL in tablet Chrome:
`http://<laptop-current-LAN-IP>:8002/manual-test/isolation`.
This proves reachability only. Then rebuild with the printed startup URL:

```powershell
cd frontend
# Installs/runs: execute only after approval for this specific test tablet.
flutter run -d 7732690b --debug --dart-define=API_BASE_URL=http://192.168.0.162:8002
```

The IP above is the observed laptop address on 6 November, not a business-logic
constant. On a different Wi-Fi run start --lan again and use its new URL; no source
edit is needed. Android Studio's Flutter run configuration takes the same
`--dart-define=API_BASE_URL=...` argument. Do not target the original Samsung,
uninstall, clear data, force a downgrade or rotate keys on signing conflicts.

Login/profile require valid credentials, not a network policy. In Profile →
Network Verification, PASS means the backend's current ASGI peer matches a valid
enabled policy. FAIL retains the actual backend reason. Transport failure means
the server could not verify the connection; it does not mean the backend proved
NETWORK_NOT_AUTHORIZED. First face enrollment and Slot 2/replacement use their
existing independent APIs and genuine face/liveness/Keystore proofs.

The final read-only audit found FYPTEST001 already has an active ACCOUNT_BOUND_FYP
template and both device slots ACTIVE, with zero attendance records. Preserve
those records: no re-enrollment, reset or third-device registration is needed
for network testing. This is test-account state, not production DEMO001 state.

## Attendance boundary and limitations

PIN validation → fresh device/network preflight → camera face/liveness → separate
fresh single-use signed attendance proof → fresh source-IP/CIDR verification at
the single attendance writer. A diagnostic PASS, skipped diagnostic screen, early
preflight PASS or client PASS flag never authorizes the insert.

Loopback (127/8, ::1, mapped loopback) always fails, even with a matching policy.
USB reverse, a host portproxy and emulator NAT may make the observed peer loopback
or a host/gateway address. There is no loopback-authorization exception here.
Remove only separately reviewed disposable forwarding rules, never arbitrary
system entries. No active portproxy entries were found during this audit.

No Wi-Fi SSID/BSSID, claimed IP, location field, X-Forwarded-For or CF-Connecting-IP
is accepted as origin evidence. Proxy headers are disabled in the isolated server.
Do not add a reverse proxy/tunnel without separately authenticating that proxy
path and testing original-source handling. A host proxy can destroy origin evidence.

On a direct home LAN this demonstrates source-IP membership in a configured
simulation range, not university presence. NAT exposes a gateway/public egress,
not a uniquely identified phone. University deployment requires institution-
confirmed address ranges and routing, with consideration of VPN/shared egress.
Same SSID or local subnet alone is not proof of university presence. Mobile data
usually cannot reach a laptop's private LAN URL; that is a reachability limitation,
not a backend CIDR verdict. Do not use Cloudflare egress IP as campus proof.

## Stop / rollback

```powershell
.\fyp-test.ps1 stop
# Or return to localhost while retaining test data/key:
.\fyp-test.ps1 start --loopback
# Administrator cleanup, if desired, after stopping LAN access:
Remove-NetFirewallRule -Name FYP-Isolated-Private-LAN-8002
```

No production process, database, biometric template, registration or Android key
is changed by these commands. Keep the scoped test rule until testing finishes
only if you want local LAN access. Full backend routes should not be published
on the internet; this is synthetic private-LAN testing with cleartext HTTP.
