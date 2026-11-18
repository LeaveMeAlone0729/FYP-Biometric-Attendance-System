# Original FYP demonstration: three commands

This guide describes default **Full** mode. The opt-in **Local** variant is
documented in [PARTNER_LOCAL_MODE.md](PARTNER_LOCAL_MODE.md). Existing Full
settings and process state remain separate from Local configuration/state.

Use PowerShell on branch SH at `C:\FYP\FYP-Biometric-Attendance-System`.

```powershell
.\fyp-start.ps1
.\fyp-install.ps1
.\fyp-stop.ps1
```

These commands operate the original `attendance_proposal_xampp:3306` environment.
They do not use scripts\fyp-test.ps1, MySQL 3332, an isolated schema or database fallback.
Existing legacy scripts remain available internally/for historical workflows;
you do not need to call them separately for the normal demonstration.

## One-time prerequisites

* Existing backend virtual environment, Flutter/Android SDK in the existing
  frontend/android/local.properties, downloaded biometric models, original
  backend/.env and unchanged biometric encryption key.
* Previously initialized original database identity and admin credentials under
  `%USERPROFILE%\FYP-Original-Local`. Missing identity is a blocker, not permission
  to trust a new database. No passwords or account recovery are performed here.
* Active Wi-Fi with exactly one usable default-route IPv4. The commands do not
  modify firewall profiles/rules, CIDRs or classroom Wi-Fi/BLE policies. If LAN
  access is blocked or the network changes, correct the approved environment;
  do not disable verification to obtain READY.
* Existing Cloudflared Windows service must already run for named tunnel
  `fyp-attendance-gateway`, with public hostname `api.bioattsys.xyz` forwarding
  ONLY to `http://127.0.0.1:8004`. This workflow never installs/reconfigures or
  automatically elevates the service. Any administrator action is separate.
* On the first start, confirm the non-secret tunnel UUID against the named
  tunnel/this laptop connector in the Cloudflare dashboard. For an inline-token
  service, the UUID can be decoded in memory without printing the token. This
  laptop's actual service instead uses an Administrator/SYSTEM-private token
  file: its contents are deliberately never read. Enter only the dashboard UUID
  and type CONFIRM. The operator-attested name/UUID is pinned to hashes of the
  service definition and token-file size/mtime/path metadata. An attribute or
  service definition change blocks reuse until separately reviewed. This is
  explicit operator verification, not an assertion that a secret was inspected.
  No ACL change or elevation is needed when metadata is readable. If the exact
  mapping cannot be verified, do not confirm. Public health alone cannot prove
  the connector's friendly name. Named-run services are checked directly.
* Known SENGHIN broadcaster executable and sibling DLL at
  `%TEMP%\fyp-ble-probe-2e8a44c743da4761bec53f3ef493b974\bin\Debug\net9.0-windows10.0.26100.0\BleProbe.exe`.
  It must retain UUID b1ba7f4e-6931-49d5-99de-7e0caa159105, GATT implementation
  and continuous mode. Bluetooth must be enabled and required .NET runtime
  available. The utility is outside Git and Windows may clear TEMP. Missing
  files produce BLE NOT READY; no substitute is downloaded or generated.
  The launcher prepares its unchanged EXE/DLL/manifests in ignored
  `runtime/ble-beacon/`, adding only the exact Windows SDK runtime dependencies
  declared by BleProbe.deps.json from the existing local NuGet SDK cache.
  Assembly/file versions and copy SHA-256 values are checked. No latest-version
  substitution, external utility modification or Bluetooth launch occurs while
  preparing this bundle. Missing exact cache dependencies are a clear blocker.

## Start

`fyp-start.ps1` checks the exact repository and SH, discovers the current Wi-Fi
IPv4, and checks process/binding conflicts before launching anything. It rejects
multiple backend listeners, unknown port owners, localhost-only backend owners,
external admin/gateway bindings or already-running processes without listeners.
It never repairs those conflicts by terminating them. Review and approve any
separate cleanup before rerunning.

If original MariaDB already listens on 3306, it is reused without restart. The
existing original launcher performs bounded read-only identity and application
schema validation against the saved original pin. Wrong identity/schema blocks
startup before exposing a new gateway. No SQL writes or migrations are executed.

If MariaDB is stopped, the script verifies the existing `C:\xampp\mysql\bin`
installation and absence of an already-starting original mysqld. It asks you to
type START before launching it with its existing my.ini and automatic Aria repair
OFF. It never initializes or replaces data. This is a real database startup, not
a repair; unexpected corruption or access-denied errors remain blockers. The
shared database remains running even if a later component fails or you run stop.

After verifying the existing Cloudflared service, startup uses readiness checks:

1. Original backend: `original_fyp.py serve-backend --lan --local-demo-slot2`,
   0.0.0.0:8000, original identity plus localhost and current LAN /config.
2. Admin: `original_fyp.py serve-panel`, 127.0.0.1:8003 and login readiness.
3. Gateway: `public_gateway.py`, **127.0.0.1:8004**, correct public Host header.
4. Public HTTPS /config, unauthenticated /me and blocked sensitive-route checks.
5. Known SENGHIN broadcaster with --continuous, bounded wait for its actual
   Windows GATT Started log. This confirms Windows publisher state, not a new
   over-the-air tablet detection. An externally launched known broadcaster
   needs an explicit fresh-detection confirmation because its old console log
   cannot be reconstructed. It is reused but never claimed for shutdown.
   Both the original known external path and the prepared bundle are recognized
   for reuse; two matching publishers are rejected. A healthy existing publisher
   is checked/reused before any attempt to prepare or start another instance.

Healthy processes with matching identities are reused and not added to ownership
state. Newly started venv wrappers and their verified listener children are
recorded with PID, executable, command, and creation time. Hidden child processes
avoid repeatedly flashing terminal windows. Every new child explicitly receives
NETWORK_BLE_TEST_MODE=false, overriding a stale inherited true setting. Existing
backends must also report false or startup is refused; no restart is automatic.

READY is printed only after all checks succeed. Each failure identifies its
component/code and exact workflow log file; component stdout/stderr are under
`runtime/logs/<timestamp>-<run-id>/`. A partial startup remains recorded; rerunning
fyp-stop.ps1 can clean up its verified owned components. It does not clean up
shared/reused processes. No automatic restart loops, watchdogs or scheduled
tasks are created.

## Install

`fyp-install.ps1` verifies the same original database, backend identities and
bindings, disabled diagnostic setting, local gateway and public security checks.
It freshly discovers Wi-Fi IPv4 and prints connected ADB serials/models. Only
the sole authorized Xiaomi 7732690b is selected automatically. If another device
or multiple devices are connected, type the exact serial, or use:

```powershell
.\fyp-install.ps1 -Serial 7732690b
```

The existing installer builds with:

* PUBLIC_API_BASE_URL=https://api.bioattsys.xyz
* CLASSROOM_API_BASE_URL=http://CURRENT_WIFI_IPV4:8000
* API_BASE_URL compatibility default equal to the classroom LAN URL.

It installs with adb install -r on the selected serial only. It does not use ADB
reverse, uninstall, clear data or regenerate Keystore keys. Package/signature or
version conflicts stop safely; do not solve them by clearing the original app.
After installation the script checks com.example.frontend, pulls the installed
base APK locally and compares SHA-256 with the built APK. The temporary pulled
copy is then removed. Output includes the selected serial, URLs and APK hash.
This verifies installed build identity, not physical attendance success.

The Python helper runs only the trusted repository-local installer as:
`powershell.exe -NoProfile -ExecutionPolicy Bypass -File <repo>\scripts\install-fyp-android.ps1 ...`.
This is a child-process/session setting, not a CurrentUser or LocalMachine policy
change. It fixes the case where the outer fyp-install.ps1 runs but its fresh
Windows PowerShell child rejects the nested script as disabled. Organizational
MachinePolicy/UserPolicy still take precedence. A remaining policy denial is
reported as ANDROID_CHILD_SCRIPT_POLICY_REJECTED_ADMIN_REVIEW_REQUIRED; there is
no escalation, persistent policy change or alternate execution retry.

## Stop

`fyp-stop.ps1` reads only `runtime/owned-processes.json`. It does not adopt a
listener or stop a process by port. Expected roles/commands come from source,
not arbitrary commands saved in that file. PID, executable, command and creation
time must match before stopping; the Windows process handle's creation time is
checked again to close the PID-reuse race. Changed/unreadable identities are
left untouched and reported. Repeated stop is safe.

Only owned gateway, admin, backend and beacon processes are stopped. Wrapper
children are stopped before their owned wrappers. This uses verified Windows
process termination, not an in-app graceful-signout request; do not run it during
an active attendance submission. Windows releases the terminated beacon's
advertiser resources, but a fresh tablet scan is still needed to confirm that
the UUID disappears over the air. The external BleProbe source is not modified.

MariaDB and the Cloudflared Windows service are always preserved, even if start
launched MariaDB after confirmation. Stopping an owned gateway makes its public
origin unavailable while the connector service stays installed/running. If all
services were reused, stop deliberately leaves them running and says so. This
is necessary to honor ownership; it is not a global system shutdown.

## Attendance and public security

General APIs use Cloudflare; classroom attendance/security stays on direct LAN
with no public fallback. PIN, ACTIVE device/key proof, signatures, freshness,
replay protection, actual ASGI-source CIDR, session Wi-Fi, face recognition,
liveness and duplicate prevention are unchanged. BLE remains shadow/diagnostic
only and cannot independently authorize or reject normal attendance. The local
demo Slot 2 flag is preserved separately from disabled Network + BLE Test Mode.
No script creates sessions, modifies policies or inserts attendance.

## Local files and credentials

`runtime/` is Git-ignored. State contains only newly owned process identities
and the non-secret approved tunnel mapping; no tunnel token or password is
stored there. Original credentials and encryption keys stay in their existing
locations. Never share runtime logs, private .env or credentials as teammate
setup. Do not commit generated APKs or the external beacon executable.

## BLE dependencies

Full mode prepares the beacon dependency bundle under `runtime/ble-beacon` through
`backend/ble_bundle.py`. It requires a live owned process and a GATT Started result
before reporting readiness. Missing dependencies or radio failures do not imply
attendance authorization. Preserve active ownership state and stop through the
matching workflow before replacing a running bundle.
