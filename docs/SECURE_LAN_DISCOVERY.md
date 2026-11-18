# Secure classroom LAN discovery

## Status and approval

The operator approved installer-provisioned, environment-specific public trust and
a direct HTTPS LAN listener in this chat. Code is opt-in. No actual Full/Local keys
have been provisioned, no live service restarted, no firewall changed and no APK
installed by this implementation task. Existing unpaired APKs retain their explicit
legacy compiled HTTP configuration; they do **not** gain automatic discovery.

## Existing architecture and findings

- `frontend/lib/services/api_routes.dart` allowlists general APIs. Full sends login,
  logout, config, profile, classes and attendance history/summary to public HTTPS.
  All other operations remain classroom-only. Local uses its own backend for both.
- `api_client.dart` formerly compiled `CLASSROOM_API_BASE_URL`; network events close
  transports and invalidate proof/session revisions without replaying signed POSTs.
- `original_fyp.py` and `local_fyp.py` pin database identity on the operator machine.
  `/local-fyp/identity` is loopback-only and its hash is not proof of remote server
  key possession. It remains unchanged and private. Device ECDSA keys authenticate
  Android **to** the server, not the server to Android.
- `fyp_operator.Host.lan()` already requires one active physical Wi-Fi IPv4 with a
  default gateway. Installers formerly rebuilt with that address on every change.
- CIDR verification reads the direct ASGI client, ignores forwarding headers and
  rejects loopback. Classroom Wi-Fi proof is signed and session-bound. BLE remains
  observation/shadow-only; neither discovery nor BLE authorizes attendance.
- Existing Android INTERNET, ACCESS_NETWORK_STATE and ACCESS_WIFI_STATE permissions
  support the current NSD implementation; no permission was added. Android NSD is
  scoped to the active Wi-Fi network on API 33+. On older Android, candidates are
  filtered against the active Wi-Fi IPv4 subnets. VPN/default mobile data fails
  closed. Newer Android local-network restrictions may require an explicit platform
  permission in a future target-SDK update; this implementation never auto-grants it.

## Approved trust design

1. The trusted local operator explicitly creates a NEW identity after an existing
   database identity pin is present. Provisioning never runs at startup/install.
2. Each Full/Local environment gets its own private directory, random server ID,
   private CA certificate and separate TLS server key/leaf certificate. The CA
   signing key is discarded after issuing the leaf. Existing folders are never
   overwritten or silently rotated. Windows ACL changes apply only to this NEW
   directory, for the current user and SYSTEM, without elevation.
3. The trusted repository-local installer validates the pinned database identity
   and exports **only** the public CA, stable hostname, server ID, mode and database
   identity hash into `FYP_LAN_TRUST_B64`. It never exports TLS private keys,
   encryption keys, credentials, templates or device keys. The APK is the explicit
   first-use trust bootstrap through the operator's existing ADB/install workflow.
   Do not accept pairing material downloaded from an untrusted advertisement.
4. Full and Local are checked against `FYP_LOCAL_MODE`; their identities cannot be
   interchanged. A changed server/database identity or expired certificate requires
   deliberate operator re-pairing, not TOFU, a popup that accepts arbitrary certs,
   or an automatic trust reset. Preserve the private key during ordinary upgrades.

This is local application server trust, not institutional biometric assurance.
It does not elevate ACCOUNT_BOUND_FYP or legacy face enrollment provenance.

## Listeners, advertisement and lifecycle

The same supported original/Local backend process owns:

- existing HTTP port 8000, unchanged for the existing gateway/admin/legacy clients;
- opt-in HTTPS port **8005**, bound only to the current physical Wi-Fi IPv4;
- `_fyp-classroom._tcp.local.` mDNS, registered only on that IPv4 interface.

The TLS listener serves the **same ASGI app directly**, with lifespan owned once by
the existing listener and `proxy_headers=False` on both. It is not an HTTP proxy:
CIDR and final attendance see the tablet's actual connection address. TLS identity
responses at `/classroom-discovery/identity` reject plaintext. Public gateway
allowlists are unchanged; discovery/pairing/security routes are not forwarded.

The launcher checks port 8005 belongs to the verified port-8000 backend PID. There
is no separately adopted discovery process or shutdown script. Normal owned-process
shutdown closes both listeners. Graceful shutdown unregisters the advertisement.
If the existing Windows process terminator ends the process abruptly, sockets close
at the OS boundary and cached advertisements age out (15-second advertisement TTL);
a cached hint is never usable without a fresh successful TLS connection.
The backend polls physical Wi-Fi every three seconds, withdraws the old interface
and rebinds/re-advertises on a valid new private IPv4. No default/ambiguous Wi-Fi
withdraws discovery rather than advertising on Ethernet/VPN/public interfaces.
Multicast failure leaves pinned manual-address recovery available. Failure to bind
TLS fails startup rather than accepting an unauthenticated discovery connection.

## Android behavior

`LanDiscoveryChannel` performs a bounded four-second foreground NSD lookup; results
are untrusted hints. No subnet/range scan or arbitrary hostname DNS lookup occurs.
Only RFC1918 literal IPv4 candidates on the phone's current Wi-Fi subnet, port 8005,
are eligible. At most eight deduplicated candidates receive bounded anonymous TLS
identity probes in parallel. No bearer, face image, PIN or signed proof is sent in
these probes. Native/Dart discovery failures and missing permission fail closed.

The TLS connection validates the installed private CA **and** stable logical DNS
hostname, even though the TCP socket connects to a newly resolved literal address.
There is no `badCertificateCallback`, insecure verification request or system CA
fallback for these connections. Only one verified endpoint with the installed
server ID/mode/database binding is selected. Multiple verified addresses are
ambiguous and require operator investigation; unknown certificates/identities are
never auto-selected. The actual authenticated requests reuse that TLS transport,
reject redirects and retain all original server authorization.

Wi-Fi/default-network and DHCP address changes discard the selected address,
transport and interrupted proof revision. The next fresh operation rediscovers.
Signed POSTs/uploads are never replayed. Full's general Cloudflare session remains
usable when classroom LAN is unavailable. Full classroom operations do not need a
new Cloudflare lookup when LAN is available (an unexpired existing login is still
required). Local has no public fallback. On mobile data a paired classroom call
fails with `CLASSROOM_WIFI_REQUIRED` before probing; it cannot authorize attendance.

## Explicit provisioning and deployment — NOT executed in this task

Requires separate operator approval for actual provisioning/restarts/installation.
Run from the repository root in the intended environment:

```powershell
# Install just the new mDNS runtime dependency in the EXISTING backend venv.
.\backend\venv\Scripts\python.exe -m pip install 'zeroconf>=0.148,<0.155'

# ONE TIME only, after reviewing the intended mode and its existing identity pin.
# Type PAIR at the interactive prompt. Refuses any existing discovery folder.
.\backend\venv\Scripts\python.exe .\backend\lan_discovery.py provision --mode Full
# Partner instead uses --mode Local with their OWN pinned database/profile.
```

Full private files: `%USERPROFILE%\FYP-Original-Local\lan-discovery`.
Local: the existing `%USERPROFILE%\FYP-Partner-Local\<repository-hash>\lan-discovery`.
Keep them outside Git. The generated `server.key` must never be shared or logged.
The certificates expire (leaf: two years; CA: three); failures require explicit
renewal/re-pairing. There is no automatic rotation or certificate-validation bypass.

After separately approving a supported scoped stop/start:

```powershell
.\fyp-start.ps1
.\fyp-install.ps1
.\fyp-stop.ps1
# Partner equivalents retain -Mode Local on each command.
```

Do not use stop/start without verifying existing process ownership. The normal
installer automatically exports public trust if configured; without it, legacy
behavior stays explicit. Pairing needs one updated APK installation; **subsequent
IP changes alone need no rebuild/reinstall**. Normal installation preserves app
data and Keystore keys. Do not uninstall or clear data to fix a pairing failure.

Firewall review may be needed for TCP 8005 and UDP 5353 on the intended Private
Wi-Fi interface/LocalSubnet. No rules are created by this change. School networks
may be Public or forbid multicast/client-to-client traffic: do not broadly enable
inbound access, silently authorize a new network or bypass campus controls.

## Manual recovery and restricted school Wi-Fi

In Network Verification, a paired build shows **Classroom connection**. Refresh
rediscovers. If multicast is blocked but direct connectivity is allowed, enter the
operator-confirmed laptop IPv4 and choose **Verify paired server at this address**.
This only supplies an address hint; the same installed TLS and identity checks are
mandatory. The hint is cleared on network changes and cannot change the trust pin.

If client isolation/firewall blocks direct TCP, automatic and manual modes both
fail. Ask the network administrator for an authorized testing LAN. Cloudflare is
not a fallback for classroom, device, biometric or attendance security.

## Testing and physical acceptance

Automated coverage includes synthetic fresh certificates, actual loopback TLS
handshakes (correct CA/hostname and rogue CA/wrong hostname), Full/Local identity
rejection, home-to-school address change, malicious hints, multiple candidates,
deduplication, no multicast, manual fallback, mobile data, network interruption,
public/LAN independent failure and no signed POST replay. Backend mocks validate
same-process listener rebind/cleanup and unowned-port rejection. Existing gateway,
attendance, device, PIN, face/liveness, CIDR, Wi-Fi and BLE suites remain mandatory.
These tests do not prove Android NSD or campus physical connectivity.

Physical tests still required after approved deployment:

1. Pair/install Full on Xiaomi 7732690b using the trusted laptop. Confirm the public
   and classroom paths are separate and all normal security checks are required.
2. Change laptop Wi-Fi/IP without rebuilding the APK. Refresh and confirm the same
   installed identity connects at the new address. Observe actual tablet ASGI IP.
3. Switch tablet Wi-Fi off/mobile data on: general APIs work through Cloudflare;
   classroom fails promptly without opening the biometric camera after rejection.
4. Switch back to authorized Wi-Fi: start a NEW preflight/proof. Never replay old
   scans/signatures. Wi-Fi and CIDR policy mismatches must still reject attendance.
5. Block multicast in a controlled test: confirm no discovery, then use the manual
   address with the same TLS pin. Block direct LAN: both must fail without fallback.
6. Advertise another synthetic server: it cannot receive login/face/proof data.
7. Partner pairs their own Local identity and database; Full trust/sessions are not
   copied or accepted. Use the intended mode's APK; no silent session migration.
8. Gracefully stop only the owned backend: advertisement disappears and 8005 closes.

No database schema, policy, attendance row, face algorithm, device registration,
BLE UUID, public gateway route or Cloudflare configuration change is needed.

## Verified local results (2026-11-16)

- Relevant backend suite: **332 passed, 4 skipped**. Skips are opt-in real database
  concurrency/integration checks; no production SQL was executed. One non-failing
  Starlette/httpx test-client deprecation warning remains.
- Complete Flutter suite: **331 passed, 1 skipped** (unprovided isolated Slot 2
  end-to-end manifest). This includes 24 new discovery/TLS tests.
- Flutter analysis: no issues. Android debug APK: builds, including the native NSD
  channel. This ordinary build has no real trust provisioning and is NOT a deployed
  paired APK. No APK was installed.
- All four PowerShell entry/helper scripts parse; Python helpers compile;
  `git diff --check` is clean.
- Zeroconf 0.154.0 API smoke passed from a temporary dependency directory without
  opening multicast sockets. The working backend venv was not modified; its mDNS
  dependency must be installed at deployment.
- Source secret check found no new usable secrets (the unchanged deliberate invalid
  credential-bearing URL rejection fixture remains in an existing test).

Evidence logs on this laptop: `%TEMP%\fyp-lan-backend-final.log` and
`%TEMP%\fyp-lan-flutter-final.log`. Reproduce with the existing test Python/pytest
environment and Flutter SDK:

```powershell
.\backend\venv\Scripts\python.exe -m pytest backend/tests/test_lan_discovery.py backend/tests/test_fyp_operator.py backend/tests/test_partner_local_mode.py backend/tests/test_original_fyp.py backend/tests/test_public_gateway.py backend/tests/test_attendance_authorization.py backend/tests/test_network_verification.py backend/tests/test_classroom_attendance.py backend/tests/test_classroom_ble.py backend/tests/test_attendance_ble_shadow.py backend/tests/test_network_ble_test_mode.py backend/tests/test_device_replacement.py backend/tests/test_device_management.py backend/tests/test_account_bound_enrollment.py backend/tests/test_workflow.py backend/tests/test_admin_testing.py -q -p no:cacheprovider
Set-Location frontend
flutter test --no-pub -r expanded
flutter analyze --no-pub
flutter build apk --debug --no-pub
```

On this laptop, pytest was provided through the existing temporary test dependency
directory (`$env:PYTHONPATH = Join-Path $env:TEMP 'fyp-precommit-testdeps-20261116'`)
instead of changing the live application's venv. TLS tests generate disposable keys
in temporary folders and remove their Flutter fixture folder afterward.

## Changed-file inventory

Modified:

- `backend/fyp_operator.py`
- `backend/local_fyp.py`
- `backend/original_fyp.py`
- `backend/requirements.txt`
- `frontend/android/app/src/main/kotlin/com/example/frontend/MainActivity.kt`
- `frontend/android/app/src/main/kotlin/com/example/frontend/NetworkChangesChannel.kt`
- `frontend/lib/modules/networks/screens/network_verification_screen.dart`
- `frontend/lib/services/api_client.dart`
- `install-fyp-android.ps1`

Added:

- `backend/lan_discovery.py`
- `backend/tests/test_lan_discovery.py`
- `docs/SECURE_LAN_DISCOVERY.md`
- `frontend/android/app/src/main/kotlin/com/example/frontend/LanDiscoveryChannel.kt`
- `frontend/lib/modules/networks/widgets/classroom_connection_card.dart`
- `frontend/lib/services/lan_discovery.dart`
- `frontend/test/secure_lan_discovery_test.dart`

## References

- [Android NSD](https://developer.android.com/develop/connectivity/wifi/use-nsd)
- [Android local network permissions](https://developer.android.com/privacy-and-security/local-network-permission)
- [python-zeroconf interface binding](https://python-zeroconf.readthedocs.io/en/stable/api.html)
- [Dart custom connection factory](https://api.dart.dev/dart-io/HttpClient/connectionFactory.html)
- [Dart TLS on a connected socket](https://api.dart.dev/dart-io/SecureSocket/secure.html)
