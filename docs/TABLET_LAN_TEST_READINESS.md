# Real tablet preparation — 6 November 2026

**Historical preparation record.** The per-device transport configuration and
Start-TabletBackend.py described below are superseded by
[FYP_NETWORK_TEST_WORKFLOW.md](FYP_NETWORK_TEST_WORKFLOW.md). Current LAN startup
has no individual client-IP allowlist; use fyp-test.ps1 rather than those old steps.

Branch: SH. No physical installation was performed.

## Approved LAN continuation

The user confirmed trusted home Wi-Fi and approved the minimum Private-network
and TCP 8002 firewall changes. Tablet ADB `7732690b` is now connected (model
2410CRP4CG); its Wi-Fi address is `192.168.0.94/24`.

Prepared administrator script (no credentials):
`C:\FYP\Tablet-LAN-Setup\Enable-TabletLan.ps1`

It changes only the Wi-Fi category to Private and creates
`FYP-Disposable-Tablet-8002-20261106`, allowing TCP 8002 on the Wi-Fi interface,
local address 192.168.0.162, remote address 192.168.0.94, Private profile and the
specific runtime Python executable. It does not change existing Public rules,
port 8000, MariaDB, router settings or production data. On setup failure it
attempts to roll back only its own new rule/category change.

Normal elevated PowerShell launches exited without a success record, and
read-only inspection still showed Public/no new rule. The operator was asked to
run the script in an Administrator PowerShell; no UAC bypass or private-folder
ACL relaxation was attempted. The final cause of the elevation-launch failure
is not established. Do not assume approval alone means Windows applied changes.

After that administrator step, this non-elevated command validates the exact
interface and firewall rule, gracefully restarts only the disposable backend,
and enables both 127.0.0.1:8002 and 192.168.0.162:8002:

```powershell
cd C:\FYP\FYP-Biometric-Attendance-System
.\backend\venv\Scripts\python.exe -B 'C:\FYP\DB-DeviceManagement\manual-android-20261106-033334-1f0285\Start-TabletBackend.py'
```

This helper has been syntax-checked, but live LAN activation is pending the
administrator step. The optional private `lan-listener.json` is used by the
existing start controller on subsequent starts. Without it, loopback remains the
default. LAN startup rejects a Public interface, address/subnet mismatch, and
non-RFC1918 or overly broad subnets. An ASGI peer gate rejects other source IPs,
including forged forwarding-header claims, without rewriting ASGI source IP.
Nine offline guard/configuration tests passed. MariaDB and phpMyAdmin remain
loopback-only. Changes to Wi-Fi address/profile require stopping and revalidating
this disposable LAN setup; the firewall rule applies only to Private networks.

After activation, verify from the actual tablet without installing anything:

```powershell
$adb = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
& $adb -s 7732690b shell curl --noproxy '*' --connect-timeout 3 --max-time 8 http://192.168.0.162:8002/manual-test/isolation
```

The tablet has curl available. A real HTTP response is required before reporting
tablet reachability PASS. No physical installation is authorized yet.

Cleanup (administrator; after stopping the disposable LAN backend):

```powershell
Remove-NetFirewallRule -Name 'FYP-Disposable-Tablet-8002-20261106'
# Restore the prior profile only if desired and this is still the same network:
Set-NetConnectionProfile -InterfaceAlias 'Wi-Fi' -NetworkCategory Public
```

Remove only the private `lan-listener.json` to restore default loopback-only
startup. Keep the database, credentials, encryption key and app data intact.

## Verified state

- Wi-Fi laptop address: `192.168.0.162/24`, gateway `192.168.0.1`.
- `192.168.56.1` belongs to VirtualBox and is not the tablet's Wi-Fi target.
- Wi-Fi is classified **Public** by Windows. Firewall is enabled.
- Two existing Python inbound allow rules apply to Public networks/any port.
  These rules were inspected only, not changed or relied upon for this test.
- Isolated FastAPI remains `127.0.0.1:8002`; MariaDB remains
  `127.0.0.1:3322`. The serving Python process has an established DB connection
  to 3322. Its isolation probe passed, including pre-connect rejection of 3306.
- The private profile requires `fypdevicemgmt_restore_a199e7f82903` and the
  dedicated runtime account. Production configuration was not changed.
- Only Samsung SM-A346E (`RFCW30BZKAZ`) was visible over ADB. No commands were
  sent to its application or Keystore. Tablet `7732690b` was not connected.

## Build prepared

API_BASE_URL: `http://192.168.0.162:8002`

APK:
`C:\FYP\DB-DeviceManagement\manual-android-20261106-033334-1f0285\tablet-lan-20261106\app-tablet-lan-debug.apk`

SHA-256:
`26479BFD506D2FAD10DE811D27C58D73A34870F7A827E432AA0CA5DF6D43CADC`

The compiled debug kernel contains the specified URL. APK ZIP integrity passed.
The packaged manifest declares INTERNET and CAMERA permissions and permits
cleartext HTTP. No manifest, native Keystore or partner enrollment code was edited.
This local HTTP build must not be used for internet access or real credentials.

Build command, from `frontend`:

```powershell
flutter build apk --debug --dart-define=API_BASE_URL=http://192.168.0.162:8002
```

Six offline isolated configuration/production-port guard tests passed. Android
debug build passed. Flutter emitted future Gradle/AGP/Kotlin support warnings;
no toolchain upgrade or validation bypass was applied.

## Original LAN readiness discovery

The backend is intentionally still loopback-only. A successful laptop localhost
probe does not prove tablet reachability. No tablet HTTP reachability is claimed.

Before enabling a LAN listener:

1. Confirm this is a trusted private Wi-Fi network and connect the tablet to it.
2. Obtain approval for changing this Wi-Fi profile to Private and adding a
   Private-profile inbound TCP 8002 rule restricted to this Python executable,
   laptop address and local subnet. Do not disable the firewall or broaden the
   existing Public-profile rules. Guest/client isolation on the router can still
   block tablet access.
3. Configure only the disposable backend to listen on the specific LAN address,
   preserving its explicit private DB profile, production-port guard and
   `proxy_headers=False`. Keep MariaDB and phpMyAdmin loopback-only. The existing
   launcher currently binds loopback; no production launcher should be used.
4. Check `http://192.168.0.162:8002/manual-test/isolation` in tablet Chrome.
   Expect disposable=true, db_port=3322 and production_port_blocked=true.
5. If DHCP changes the address, rebuild with the new URL. Do not use the
   VirtualBox adapter, 0.0.0.0 as a client URL, or any public tunnel.

Proposed administrator commands for review only — NOT EXECUTED:

```powershell
Set-NetConnectionProfile -InterfaceAlias 'Wi-Fi' -NetworkCategory Private
New-NetFirewallRule -DisplayName 'FYP disposable tablet TCP 8002' `
  -Direction Inbound -Action Allow -Profile Private -Protocol TCP `
  -LocalAddress 192.168.0.162 -LocalPort 8002 -RemoteAddress LocalSubnet `
  -Program 'C:\Users\yap10\AppData\Local\Programs\Python\Python312\python.exe'
```

Do not apply these on an untrusted Wi-Fi network. A USB-only test using the
existing loopback backend remains an alternative and needs no firewall change;
see MANUAL_ANDROID_TEST_ENVIRONMENT.md for its different API URL/build command.

## Tablet instructions — only after installation approval

Enable Developer options and USB debugging on the tablet, attach its USB cable
and accept its debugging prompt. Prefer disconnecting the Samsung cable to avoid
an accidental target selection. From the repository root:

```powershell
$adb = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
& $adb devices -l
# Confirm 7732690b is the intended tablet and reports "device".
& $adb -s 7732690b shell getprop ro.product.model
# STOP if the serial/model is not the intended tablet.
& $adb -s 7732690b install -r 'C:\FYP\DB-DeviceManagement\manual-android-20261106-033334-1f0285\tablet-lan-20261106\app-tablet-lan-debug.apk'
```

If signing incompatibility or a version downgrade is reported, stop; do not
uninstall, clear data, rotate keys or automatically force a downgrade.

Alternatively, after approval, in Android Studio select only tablet `7732690b`
and add this Flutter run configuration argument:
`--dart-define=API_BASE_URL=http://192.168.0.162:8002`.
Equivalent terminal command from `frontend`:

```powershell
flutter run -d 7732690b --debug --dart-define=API_BASE_URL=http://192.168.0.162:8002
```

`flutter run` builds AND installs; it was not executed during preparation.

Log in as FYPTEST001 using the private test credentials, then complete genuine
first face enrollment through the existing screen. Do not insert fake templates.
If this tablet must be Slot 2, register another disposable installation as Slot 1
first. Registering this tablet first makes it Slot 1. Never copy the protected
Samsung binding or test replacement against DEMO001. No attendance network policy
is added by this preparation; attendance remains fail-closed independently.
