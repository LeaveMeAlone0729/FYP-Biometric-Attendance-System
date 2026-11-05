# Phase 4 network verification FR-06

Implemented on SH for the controlled FYP simulation, 1 November 2026. The backend compares the current ASGI connection source IP with enabled database CIDR policies, persists PASS/FAIL evidence and returns a diagnostic to Flutter. No real campus network was assumed or tested. Attendance recording is unchanged and is not yet gated by network verification; the combined final decision belongs to Phase 5.

## Requirements and architecture review

Reviewed FR-06 in `C:\Users\yap10\Downloads\YapSengHin_Chapter3_Methodology and Requirements (3).docx` and Module 4 / controlled-simulation design in `C:\Users\yap10\Downloads\YapSengHin_Chapter4_System Design (1).docx`. FR-06 requires the request to originate through an authorised network. Chapter 4 describes backend-observed IP membership in stored CIDR ranges and explicitly distinguishes simulation from campus deployment and NAT-observed addresses.

There was no network model/table/service in the existing architecture. Shared verification_attempts lacks source-IP/policy metadata, so the new module follows the existing device-owned router/service/model/audit separation using the same FastAPI authentication, SQLAlchemy sessions and MySQL database. `backend/services/attendance.py:record_verified_attendance` still performs the final insert after the partner's face/liveness flow. Neither that writer, attendance routes nor partner inference/enrollment/deletion code was changed. Stage C1 and the unavailable trusted biometric provider remain unchanged.

## Files changed

New backend files:

- backend/modules/networks/__init__.py
- backend/modules/networks/cidr.py
- backend/modules/networks/models.py
- backend/modules/networks/policies.py
- backend/modules/networks/service.py
- backend/modules/networks/schemas.py
- backend/modules/networks/router.py
- backend/modules/networks/migration.py
- backend/manage_network_policy.py
- backend/migrate_network_verification.py
- backend/tests/test_network_verification.py
- backend/tests/run_network_simulation.py

New Flutter files:

- frontend/lib/modules/networks/services/network_verification_api.dart
- frontend/lib/modules/networks/screens/network_verification_screen.dart
- frontend/test/network_verification_test.dart

Existing files changed: backend/app.py (router composition only); frontend/lib/screens/student_profile_screen.dart (network navigation card only); docs/openapi.json; docs/API_INTEGRATION.md; docs/MODULE_OWNERSHIP.md; README.md. This report is new. No dependency, Android manifest, Keystore alias, device service, biometric algorithm or attendance source change was needed.

## Policy store and operator authorization

`network_policies` stores network_id (VARCHAR64 PK), network_name (VARCHAR100), network_cidr (VARCHAR45), enabled (Boolean, SQL default false), created_at and updated_at. The Chapter 4 policy_status concept maps to enabled. Multiple IPv4/IPv6 ranges are supported. Nothing is seeded or enabled by migration.

All application/CLI policy input uses Python ipaddress.ip_network(..., strict=True). CIDRs must contain an explicit prefix and must be proper network addresses; host bits, malformed prefixes, interface scope IDs and plain addresses are rejected. IPv6 is canonicalized. IPv4-mapped sources normalize to IPv4; configure their policies using IPv4 CIDRs rather than mapped IPv6 CIDRs. Model names, hardware IDs, SSIDs and GPS are irrelevant.

Policy administration uses the trusted local operator CLI and database access, not student authentication. No policy write/list HTTP API exists. Student clients cannot add/enable a range. Each CLI change writes an atomic network_policy_events record with OS operator, old/new configuration and timestamp. No delete command exists; disable preserves history.

```powershell
# Project root. Read-only; currently returns an empty list.
.\backend\venv\Scripts\python.exe -B backend\manage_network_policy.py list

# Explicit example of a SIMULATED range, NOT a real campus network.
# Do not execute unless this is the lab range you intend to authorize.
.\backend\venv\Scripts\python.exe -B backend\manage_network_policy.py put --id lab-v4 --name "Controlled lab simulation" --cidr 192.0.2.0/24 --enable
.\backend\venv\Scripts\python.exe -B backend\manage_network_policy.py disable --id lab-v4
```

Omitting --enable on put creates/updates the policy as disabled. Enable validates the stored CIDR again. A student with direct operating-system/database access is outside the student API trust boundary; this CLI is an operator tool, not an administrator role granted to student accounts.

## Trusted source IP and server configuration

Only request.scope['client'][0] is read. No client IP JSON, query fields, X-Forwarded-For, Forwarded, X-Real-IP, external IP-discovery services or Android identifiers are used. The empty request schema rejects extra JSON fields. Hostnames are not resolved to manufacture a source address.

IMPORTANT: an ASGI server can rewrite scope.client BEFORE FastAPI sees it. Therefore Uvicorn proxy headers must remain disabled. The existing start-backend.ps1 already includes --no-proxy-headers, and the running backend was restarted with that flag. A real socket test launches Uvicorn with proxy_headers=False and demonstrates that a forged authorised X-Forwarded-For still produces the actual loopback IP and FAIL. Application code cannot recover the original socket address after an upstream server has overwritten it.

```powershell
# Project root; recommended existing launcher, suitable for direct LAN testing.
.\start-backend.ps1

# Equivalent explicit command from backend/:
.\venv\Scripts\python.exe -B -m uvicorn main:app --host 0.0.0.0 --port 8000 --no-proxy-headers
```

Do not place this prototype behind a forwarding proxy or enable proxy-header rewriting without a separate reviewed proxy trust design. The current policy is direct connection scope. Loopback (127.0.0.0/8, ::1 and mapped loopback) is always rejected, even if someone adds a covering CIDR. Unspecified/multicast addresses and malformed/missing peers fail closed. IPv4-mapped IPv6 peers normalize to canonical IPv4.

## Verification and audit behavior

The service rechecks authenticated student/login under the existing student-first lock order. It reads and locks enabled policies in the caller's transaction and validates every enabled CIDR. An invalid enabled policy blocks the entire decision, even if another range would match. Disabled invalid rows are ignored. Among multiple valid matches, the most-specific prefix wins, then network ID for a deterministic tie. IPv4 and IPv6 are compared only against the same address family.

`network_verification_events` records student, hashed login reference, operation, optional server-owned attendance attempt reference, canonical source IP, result, reason, matched policy FK, policy CIDR/version-time snapshot and timestamp. PASS is database-constrained to a non-null source/policy/CIDR. Diagnostic events cannot carry an attendance attempt. The future attendance operation requires an exact nonempty server-owned attempt ID. `network_policy_events` records operator configuration history.

Known failure reasons: NETWORK_NOT_AUTHORIZED, NO_ENABLED_NETWORK_POLICY, NETWORK_POLICY_INVALID, LOOPBACK_SOURCE_NOT_AUTHORIZED, SOURCE_IP_MISSING, SOURCE_IP_INVALID and SOURCE_IP_NOT_UNICAST. Auth failures return 401/403 without claiming a network result. Database/audit persistence errors return an error, never PASS; an unavailable database cannot persist its own failure audit. IPs are stored because FR-06 requires source evidence; there are no images, biometric templates or raw bearer tokens in these new logs.

No previous PASS is reused. A diagnostic event ID is an audit reference, not a grant. A network match cannot establish device ownership, biometric identity, institutional template trust or physical location.

## REST API

```http
POST /api/v1/networks/verifications
Authorization: Bearer <existing-login-token>
Content-Type: application/json

{}
```

HTTP 200 means the diagnostic was processed; inspect result. Both business PASS and FAIL are audited and committed before the response. Extra input fields return 422. Missing/expired authentication returns 401; DB service failure returns 503 through existing API conventions.

PASS example (controlled source fixture):

```json
{
  "success":true,
  "verification_id":2,
  "result":"PASS",
  "reason_code":"NETWORK_AUTHORIZED",
  "message":"The backend-observed source IP matches an enabled authorised network policy.",
  "source_ip":"192.0.2.10",
  "matched_policy_id":"sim-v4",
  "matched_policy_name":"Controlled simulation",
  "verified_at":"2026-10-30T12:00:00+08:00",
  "operation":"network_diagnostic",
  "attendance_authorized":false
}
```

FAIL example (ADB-style loopback; IDs/timestamps are illustrative):

```json
{
  "success":true,
  "verification_id":8,
  "result":"FAIL",
  "reason_code":"LOOPBACK_SOURCE_NOT_AUTHORIZED",
  "message":"The backend sees a localhost connection, which is not campus-network proof. USB ADB reverse may cause this. Use isolated simulation tests or a direct configured LAN connection.",
  "source_ip":"127.0.0.1",
  "matched_policy_id":null,
  "matched_policy_name":null,
  "verified_at":"2026-10-30T12:00:00+08:00",
  "operation":"network_diagnostic",
  "attendance_authorized":false
}
```

## Flutter behavior

Profile / Account & biometrics -> Network Verification opens the independent screen. It checks automatically on entry, displays only the server's PASS/FAIL, reason, observed IP, matching policy and timestamp, and allows a fresh connection check. The API adapter sends {} and validates the response shape/binding; it contains no CIDR logic. Network/API/session errors and timeouts stop the spinner and remain visible. Resuming discards stale results and performs a fresh check. Phone/tablet layouts scroll normally.

The screen explains controlled simulation, ADB reverse loopback and the absence of attendance authorization. No Android location or Wi-Fi permissions/dependencies were added. No attendance camera/endpoint was wired to the diagnostic.

## Safe migration evidence

Backup: `.work/phase4-backup/20261101-175624/` with ACL-protected database.sql and matching backend.env. Manifest stores hashes and all original-column row counts/hashes for the 21 original tables. The backup was restored to isolated `attendance_p4_restore_2d4b1d5cf267` and verified. Old backend workers were stopped before production DDL.

The restored-copy migration created three new tables, validated every column/PK/FK/CHECK and the audit index/default-disabled status, and ran actual temporary-table constraint probes. A repeat run created nothing. Only then was production upgraded with the same validation and original-record verification. No existing table/constraint/index was dropped, no row was reset/reseeded, and no policy was inserted. MariaDB Boolean reflection is explicitly verified as TINYINT(1).

Executed commands (already applied; future data changes require a fresh verified backup/evidence):

```powershell
.\backend\venv\Scripts\python.exe -B backend\migrate_network_verification.py --evidence .work\phase4-backup\20261101-175624\manifest.json --validate-restored-copy
.\backend\venv\Scripts\python.exe -B backend\migrate_network_verification.py --evidence .work\phase4-backup\20261101-175624\manifest.json --apply-production
```

The migration fails on unexpected schema drift, mismatched SQL/config hashes, missing restoration proof or a listening old backend at port 8000. Startup never applies DDL. Backups contain sensitive existing data and must not be committed/shared.

## Automated PASS/FAIL evidence

`backend/tests/run_network_simulation.py` runs only an isolated in-memory SQLite/TestClient environment. It asserts that its engine is isolated, injects controlled ASGI peers in the TEST transport and drives the actual authenticated production route/service. No production source override, fixture endpoint, environment bypass or default trusted CIDR exists. Test timestamps use a fixed fixture clock and are not physical-campus measurements.

Evidence: `.work/p4-network-simulation.json`.

| Case | Observed source | Expected result |
| --- | --- | --- |
| Authorised simulated IPv4 | 192.0.2.10 | PASS, sim-v4 |
| Outside enabled range | 198.51.100.10 | FAIL, NETWORK_NOT_AUTHORIZED |
| Missing / disabled policies | 192.0.2.10 | FAIL, NO_ENABLED_NETWORK_POLICY |
| Invalid enabled CIDR plus another valid range | 2001:db8:1234::5 | FAIL, NETWORK_POLICY_INVALID |
| Forged X-Forwarded-For=192.0.2.10 | actual peer 198.51.100.10 | FAIL; header ignored |
| Authorised simulated IPv6 | 2001:db8:1234::5 | PASS, sim-v6 |
| Outside IPv6 range | 2001:db8:9876::5 | FAIL |
| IPv4-mapped IPv6 | ::ffff:192.0.2.10 | PASS as 192.0.2.10 |
| ADB-style loopback | 127.0.0.1 | FAIL, LOOPBACK_SOURCE_NOT_AUTHORIZED |

All simulation cases assert zero attendance inserts. Isolated MariaDB tests exercise additive migration, resumability, real CHECK enforcement and concurrent PASS/FAIL audit inserts. Tests also cover no student policy API, authentication, body spoofing rejection, longest-prefix matching, source parse errors, policy changes invalidating fresh checks and the future server-owned attempt interface.

## Exact local test commands

```powershell
Set-Location C:\FYP\FYP-Biometric-Attendance-System
.\backend\venv\Scripts\python.exe -B backend\tests\run_network_simulation.py
$env:ATTENDANCE_DEVICE_MYSQL_TESTS='1'
.\backend\venv\Scripts\python.exe -B -m unittest discover -s backend/tests -v
Set-Location frontend
& C:\Users\yap10\flutter\bin\flutter.bat test
& C:\Users\yap10\flutter\bin\flutter.bat analyze
& C:\Users\yap10\flutter\bin\flutter.bat build apk --debug --dart-define=API_BASE_URL=http://127.0.0.1:8000
```

For USB testing on the Xiaomi tablet (optional; not performed automatically in this task):

```powershell
# Project root; keep the no-proxy-headers backend running in another terminal.
$adb = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
& $adb -s 7732690b reverse tcp:8000 tcp:8000
& $adb -s 7732690b install -r frontend\build\app\outputs\flutter-apk\app-debug.apk
```

Open Profile -> Network Verification. Expect backend-observed 127.0.0.1 (or loopback IPv6) and FAIL; this demonstrates the security boundary, not a broken campus check. Do not add a localhost allow rule. `install -r` preserves data/keys; never uninstall, clear data or perform a Samsung replacement. No physical app/key operation was executed by this task.

To demonstrate a real TCP connection to a simulated LAN (optional, operator supervised):

1. Start `start-backend.ps1` on the computer; it binds directly with proxy headers disabled. Connect the tablet/computer to the chosen lab LAN.
2. Build with `--dart-define=API_BASE_URL=http://<computer-LAN-IP>:8000` and install using `adb install -r`. If Windows firewall blocks the connection, arrange a narrowly scoped lab rule; this task did not change firewall settings.
3. Open Network Verification before adding any policy. Read the actual backend-observed source IP from the FAIL response. It may differ from the tablet's interface address due to NAT.
4. Explicitly configure an operator-approved lab policy, for example a narrow IPv4 /32 for that exact observed LAN source. In PowerShell set `$labSource = '<actual observed IPv4>'`, then run `.\backend\venv\Scripts\python.exe -B backend\manage_network_policy.py put --id lab-tablet --name "Controlled LAN tablet simulation" --cidr "$labSource/32" --enable` from the project root. For IPv6 use a proper /128 instead.
5. Check again: PASS requires the real connection source to match the enabled policy. Disable the test policy with `manage_network_policy.py disable --id lab-tablet` and check again: FAIL.

These are explicit lab authorizations, not TARUMT campus ranges. The pure ASGI simulation remains the repeatable test when USB reverse obscures the network. Real campus deployment requires institution-confirmed observable egress CIDRs, a reviewed NAT/proxy topology and secure transport. IP membership does not prove physical location or Wi-Fi SSID.

## Remaining Phase 5 integration

Call `NetworkVerificationService(context).verify(db, student, auth, request.scope, operation='attendance_authorization', attendance_attempt_id=<server-owned-current-attempt-id>)` on the exact final attendance HTTP request and in the same transaction as the final insert. It locks current enabled policies until transaction completion and logs the exact attempt/login/source/policy snapshot. Do not accept a client PASS, source IP, old event ID or earlier diagnostic as authorization.

The final coordinator must combine genuine server biometric evidence, fresh attempt-bound candidate/device signature and this fresh network decision before `record_verified_attendance` inserts. On FAIL it must return a rejection while preserving the rejection audit and creating zero attendance rows. Avoid raising an exception that simply rolls back the failure audit. Review camera-to-final-request binding, session ownership, policy mutation races, replay and rollback with the partner before changing attendance endpoints. Existing attendance routes currently remain biometric-only, exactly as before this phase.

## Preservation and validation summary

Full backend suite: 177 tests, 176 passed, one optional live-API skip. Full Flutter suite: 151 passed, one opt-in Slot 2 integration test skipped. All nine new network tests pass. Flutter analyze: no issues. Android debug APK build succeeded. Final evidence is `.work/p4-final-evidence.json`; all 21 original-table row projections and matching backup/configuration hashes were reverified after testing. Production now has 24 tables and all three new network tables remain empty. No partner biometric service/camera/inference, attendance writer/router, device replacement implementation, Android Keystore code or secrets were changed. Samsung Slot 1 remains ACTIVE and unchanged, Xiaomi candidate keys were never accessed/rotated, and no real device replacement was performed. No commit, push or merge.


## Flutter connection-failure presentation (3 November 2026)

Network Verification displays `Network verification: PASS` only for a valid server diagnostic PASS. A server diagnostic FAIL or HTTP rejection displays `Network verification: FAIL` and preserves the server's actual reason/message.

Timeout, connection refused, DNS failure and an unreachable backend also display `Network verification: FAIL`, with local presentation code `VERIFICATION_SERVER_UNREACHABLE` and the message: "Unable to reach the verification server. Connect to the authorised network and try again." The screen explicitly states that the backend could not verify the source IP. It does not invent `NETWORK_NOT_AUTHORIZED`, a backend-observed IP, policy match, verification timestamp or server audit result when no response arrived. The existing timeout bounds, manual retry and lifecycle refresh remain in place; late responses cannot turn a timed-out result into PASS.

The shared HTTP client now identifies transport exceptions as REQUEST_TIMEOUT or NETWORK_ERROR, while preserving actual HTTP rejection codes/messages. NetworkVerificationFailure maps only transport failures to reachability guidance. Malformed responses and expired login remain failures with their own explanation.

Attendance PIN submission and early preflight use the same reachability explanation. If PIN validation is unreachable the PIN screen blocks progress; if the signed preflight is unreachable after PIN validation, the existing result screen opens with `Network verification: FAIL` and the camera never starts. No preflight PASS is cached as final authorization. No backend, cryptographic proof, biometric algorithm, final writer, CIDR policy, registration or database changes are involved in this presentation update.

Changed Flutter files: `lib/services/api_client.dart`, `lib/modules/networks/services/network_verification_failure.dart` (new), `lib/modules/networks/screens/network_verification_screen.dart`, `lib/screens/attendance_flow_screen.dart`; tests `network_verification_test.dart`, `attendance_preflight_test.dart`, `attendance_authorization_test.dart` (transport fixtures), `device_verification_test.dart` (specific transport code regression).

Physical retest after installing a separately built update with `adb install -r`: authorised reachable Wi-Fi should show the backend PASS; reachable unauthorised source should show the backend FAIL reason; moving away from the network hosting 172.22.153.134:8000 should show FAIL with server-unreachable guidance. Such a connection failure cannot establish whether the mobile/hotspot source belongs to a CIDR policy. Return to the authorised reachable network and retry. This task does not install, uninstall or clear the app, access Keystore keys, change server addresses/policies, or write production data.

Validation: full `flutter test` passed with 176 tests passing and 1 opt-in integration test skipped. `flutter analyze` reported no issues. Tests exercise valid server PASS, server diagnostic/HTTP FAIL with original reasons, real bounded diagnostic timeout, refused/DNS/client transport errors, late PASS suppression, and unreachable/timeout preflight with zero camera openings and no signing/capture. Logs: `.work/network-ux-flutter-tests.log` and `.work/network-ux-analyze.log`. `git diff --check` passed. Branch remains SH; no backend/database or physical-device operations were performed.
