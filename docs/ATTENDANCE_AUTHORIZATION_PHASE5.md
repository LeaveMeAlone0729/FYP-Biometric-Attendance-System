# Phase 5 final attendance authorization

Implemented on branch SH, 1 November 2026. The existing attendance writer now unconditionally requires genuine server face/liveness evidence, a fresh attendance-specific registered-device signature and a fresh final-request CIDR check. There is no alternate HTTP attendance-writing path or development bypass. Production network policies remain empty and real attendance is therefore fail closed until the intended network is explicitly configured. Physical Samsung/home-LAN testing has not been performed in this task.

## Exact insertion endpoint and ownership boundary

Runtime flow: `POST /attendance/start` validates class PIN/group/window and creates verification_challenges -> `POST /verify-face` matches the enrolled face and generates the original random gesture -> `POST /liveness/frame` validates fresh face/hand frames -> on the third consecutive accepted frame BiometricService calls `backend/services/attendance.py:record_verified_attendance`.

That shared function is the only runtime Attendance(...) insertion site. It calls AttendanceAuthorizationService.authorize BEFORE constructing/inserting Attendance. No new completion endpoint was added. Both direct API requests and legacy clients reach the same mandatory guard. The existing offline `backend/seed_sample.py` also inserts explicitly fictional sample attendance as an operator data-import tool; it is not an HTTP route, was not run or changed, and must not be used as an attendance authorization path. Test fixtures also insert isolated data only.

Ownership was reviewed and explained before editing. Minimum partner-owned changes:

| File | Integration change | Preserved behavior |
| --- | --- | --- |
| backend/modules/biometrics/router.py | /liveness/frame accepts request scope and two proof fields; obtains student/auth locks first; wraps domain denials so their audits commit | Existing endpoint, operation ID, multipart image handling and biometric responses |
| backend/modules/biometrics/service.py | liveness_frame adds keyword context parameters and forwards them only at the final writer call | Entire inference/progress body before the final return; all other biometric methods |
| frontend/lib/modules/biometrics/screens/camera_screen.dart | Optional BiometricApi dependency injection (three additions and one initialization change) | Existing capture, orientation, consent, red/green guide, random gesture UI, retry/cancel/countdown/feedback behavior |

No partner inference.py, templates.py, constants.py, face matching threshold, enrollment/deletion function or Flutter BiometricApi implementation was changed. The same face encoding/distance and hand detection functions are called. The three-frame requirement and random finger challenge remain unchanged. Existing face templates and legacy template trust status are not modified.

## Device challenge protocol

After the partner's server confirms face matching, Flutter automatically requests:

```http
POST /api/v1/attendance/device-challenges
Authorization: Bearer <current-login-token>
Content-Type: application/json
```

```json
{"attendance_challenge_id":"id-from-attendance-start","public_key_fingerprint":"64-lowercase-hex-of-local-SPKI"}
```

The strict JSON schema accepts no student/device/session IDs, private keys, IPs or PASS flags. The backend derives those bindings, requires the same current login and genuine face-verified liveness stage, finds the student's ACTIVE registration by fingerprint and validates its canonical P-256 public key. Slot 1 or Slot 2 is supported. Unknown, KEY_PROVEN-only, inactive/revoked and other-student keys cannot obtain an attendance proof. Names/model/hardware identifiers confer no authority.

201 response:

```json
{
  "success":true,
  "challenge_id":"single-use-device-nonce-id",
  "attendance_challenge_id":"current-biometric-attempt-id",
  "attendance_session_id":123,
  "device_id":"server-registration-id",
  "slot_number":1,
  "public_key_fingerprint":"64-lowercase-hex",
  "operation":"attendance_authorization",
  "algorithm":"ECDSA_P256_SHA256",
  "signature_encoding":"base64-DER",
  "signing_payload":"base64-UTF8-canonical-server-JSON",
  "expires_at":"ISO8601-with-timezone"
}
```

The exact signed JSON includes version=1, purpose/operation=attendance_authorization, nonce ID, student ID, hashed login reference, attendance challenge ID, attendance class/session ID, biometric verification ID, registered device ID, slot, fingerprint, random nonce and server expiry. Expiry is at most 60 seconds and never exceeds login or biometric attempt expiry. The client signs the original decoded bytes through the existing Android Keystore alias; the private key never leaves Keystore.

Repeated identical issuance recovers the current unconsumed nonce without extending its deadline. An expired nonce is ended before issuing another. One open nonce per attendance attempt is enforced by a generated unique key; student/auth/attempt locks serialize conflicts. Another device cannot silently switch the current attempt's binding. Issuance is limited to 20 per student per five minutes.

Flutter adds the proof to the existing multipart request:

```http
POST /liveness/frame
Authorization: Bearer <same-login-token>
```

```text
challenge_id=<attendance challenge ID>
file=<fresh camera frame>
device_challenge_id=<attendance device nonce ID>
device_signature=<base64-DER ECDSA signature>
```

The form fields remain optional at parsing time to preserve biometric progress/response compatibility, but BOTH are mandatory at the final insertion boundary. Older clients may reach biometric progress but cannot record attendance without the new proof. No fallback accepts standalone Phase 2 PASS events or client device/network/biometric flags. The Profile My Device challenge belongs to a different table/purpose and is explicitly tested as unusable here.

## Final biometric/device/network transaction

1. Lock current student and authenticated login before the biometric challenge. Lock the actual attendance challenge/class session and recheck owner, login, expiry and attendance window.
2. Require server-persisted liveness stage, pending verification root, finite matching face distance below the unchanged threshold and exactly three consecutive accepted liveness frames. B3 device-enrollment COMPLETED_UNTRUSTED sessions do not satisfy this state machine.
3. Load/lock the submitted attendance-specific nonce. Require exact student/login/attendance challenge/class session binding and unconsumed, unexpired state. An owned final submission consumes the nonce, including invalid-signature and network failures.
4. Reload/lock the registered device. Require ACTIVE status in Slot 1/2, correct ownership and unchanged canonical key/fingerprint. Check the signed payload's entire binding and verify ECDSA SHA256 against the stored public key.
5. Call the existing NetworkVerificationService on THIS `/liveness/frame` Request.scope, operation=attendance_authorization and attendance_attempt_id=the current biometric challenge ID. No earlier Profile diagnostic is consulted. Enabled policies are re-read/validated and locked in the same transaction. Empty/invalid/disabled policy sets, outside ranges and loopback all fail closed; forwarded headers are ignored.
6. Recheck deadlines/window and duplicate attendance. Inside a savepoint, mark the challenge/root complete, insert the one existing Attendance row, flush and recheck deadlines, mark the nonce PASS and write an authorization PASS event linked to the fresh network audit.
7. The shared function-scoped get_db dependency commits before the response. Unique attendance(student,session) remains the final duplicate guard. If insertion or a late deadline check fails, the savepoint rolls back Attendance and success state; the outer transaction records a terminal failed attempt, spent nonce and failure audit. Network checks that passed before a late overall failure remain diagnostic evidence, never reusable authority.

All participating attendance/auth/device/network tables are validated as transactional InnoDB before deployment. No student-global verified flag is set. A successful response retains the existing shape: success, complete, face_verified, liveness_verified, attendance_id, recorded_at and message. GET /verification/{id} remains read-only and reports success only after the actual committed attendance path completes.

Representative final errors include ATTENDANCE_DEVICE_NOT_REGISTERED, ATTENDANCE_DEVICE_NOT_ACTIVE, ATTENDANCE_DEVICE_SIGNATURE_INVALID, ATTENDANCE_DEVICE_PROOF_EXPIRED, ATTENDANCE_DEVICE_PROOF_REPLAYED, ATTENDANCE_DEVICE_PROOF_MISMATCH, ATTENDANCE_BIOMETRICS_REQUIRED, NETWORK_NOT_AUTHORIZED, NO_ENABLED_NETWORK_POLICY, NETWORK_POLICY_INVALID, LOOPBACK_SOURCE_NOT_AUTHORIZED, ATTENDANCE_AUTHORIZATION_EXPIRED and ATTENDANCE_ALREADY_RECORDED. Device/network denials use the existing audit-preserving response wrapper; biometric failures keep the partner's existing verification-attempt audit.

## Source-IP trust

Only the final request's ASGI scope.client IP is used. The backend was restarted with --no-proxy-headers; start-backend.ps1 already uses the same flag. This is mandatory because an ASGI server can otherwise rewrite scope.client before FastAPI receives it. There is no public source-IP override or proxy bypass. IPv4, IPv6 and mapped IPv4 handling remain those of Phase 4. Loopback/ADB reverse never constitutes authorised campus-network proof.

## Flutter integration

Shared AttendanceFlowScreen injects AuthorizedAttendanceBiometricApi into the existing partner CameraScreen. The device-owned adapter inherits the unchanged face/result/cancel API behavior and automatically obtains/signs the attendance nonce before submitting liveness frames. It caches only an unconsumed signed nonce for that exact student/login/attempt until its deadline, coalesces concurrent preparation and refreshes expired challenges. It never caches a standalone PASS, creates/rotates a key or sends an IP/authorization flag. Successful completion clears the attempt's cached proof.

Missing local key, unregistered/revoked device, expired/invalid signature, network/policy denial and biometric errors are shown by the existing camera failure UI. The server-confirmed completion still controls the success screen. No new manual verification button or Android permission was introduced. Session changes while signing cannot submit under a new login. App data and all existing Keystore aliases/keys remain unchanged; no APK was installed on a real device during development.

## Migration and database preservation

New tables only: attendance_device_challenges (bound nonce, payload, expiry, single-use result, unique open attempt) and attendance_authorization_events (student/login/attempt/device/nonce/network audit links and result/reason/time). Existing attendance, student, registered-device, template and policy schemas/rows were not altered or backfilled.

Backup/configuration: `.work/phase5-backup/20261101-184826/`, protected with ACLs. All 24 original tables were backed up and restored into a verified attendance_p5_restore_* schema. The additive migration, every column/PK/FK/CHECK/generated unique guard, transactional engine and temporary-table constraint probes were verified there; repeat execution created nothing. Only after restored integration tests passed and workers were stopped was production migration applied. Production has 26 tables, with no seeded network range and no development approvals.

Executed commands (already applied):

```powershell
.\backend\venv\Scripts\python.exe -B backend\migrate_attendance_authorization.py --evidence .work\phase5-backup\20261101-184826\manifest.json --validate-restored-copy
.\backend\venv\Scripts\python.exe -B backend\migrate_attendance_authorization.py --evidence .work\phase5-backup\20261101-184826\manifest.json --apply-production
```

Future database changes require a fresh verified backup/evidence. The current evidence describes this snapshot; do not reuse it to overwrite newer data. Startup never performs DDL. Backups/configuration contain sensitive data and must not be committed/shared.

## Automated test evidence

Full backend suite: 193 run, 192 passed, one optional live-API test skipped. Existing biometric workflow tests now use genuine disposable ECDSA proofs and an isolated authorised source rather than an authentication bypass. The previous expectation that attendance succeeds from any address was intentionally changed: face enrollment remains independent, final attendance is denied outside its configured network. The isolated network-migration test drops/recreates empty dependent fixture tables in FK order; no production tables are dropped.

Full Flutter suite: 158 passed, one opt-in Slot 2 cross-process test skipped. Seven new signing/injected-camera tests cover cache scope/expiry, concurrent preparation, missing key, invalid binding, login change, signed multipart requests, server-confirmed success and visible network denial. Flutter analyze is clean; Android debug APK build passed.

Actual REST/transaction integration: `.work/p5-restored-integration-52cfd74a16c2.json`.

The runner restores the verified SQL backup into a NEW disposable attendance_p5_test_* MariaDB database, applies the actual migration, creates only disposable students/devices/classes and simulation policies there, and exercises the real /attendance/start, /verify-face, nonce and /liveness/frame endpoints with real software P-256 signatures. Biometric inference is a controlled fixture; original state-machine/threshold code runs unchanged. This is not a physical-camera accuracy test and contains no production fixture route/configuration.

24 scenarios passed: both ACTIVE slots; repeated and replayed submissions; invalid signature; revocation after issue; wrong login/student; outside source; spoofed forwarding; no enabled/disabled/invalid policy; localhost; expired/missing proof; face mismatch; incorrect gesture; unknown key; an actually KEY_PROVEN pending candidate; failure after the insertion flush with rollback; and concurrent final submissions. Three disposable attendance rows committed: one Slot 1 success, one Slot 2 success, and exactly one concurrent winner. Every failure inserted zero. The evidence records test attendance IDs and authorization/network audits. Every ORIGINAL restored row, including original attendance and Samsung registration, was compared by primary key and preserved. The production snapshot was separately rehashed unchanged, and the disposable DB was dropped.

The copy-only later phone setup utility was also tested in that disposable restored schema; it creates class/policy metadata only and never inserts attendance or modifies a device, face template or key.

Reproduction:

```powershell
Set-Location C:\FYP\FYP-Biometric-Attendance-System
.\backend\venv\Scripts\python.exe -B backend\tests\run_attendance_authorization_restored.py --evidence .work\phase5-backup\20261101-184826\manifest.json
$env:ATTENDANCE_DEVICE_MYSQL_TESTS='1'
.\backend\venv\Scripts\python.exe -B -m unittest discover -s backend/tests -v
Set-Location frontend
& C:\Users\yap10\flutter\bin\flutter.bat test
& C:\Users\yap10\flutter\bin\flutter.bat analyze
& C:\Users\yap10\flutter\bin\flutter.bat build apk --debug --dart-define=API_BASE_URL=http://127.0.0.1:8000
```

## Safe later Samsung and home Wi-Fi testing

Do NOT test against production attendance. Use the verified restored copy on a separate port. It contains the original Samsung PUBLIC-key registration and encrypted face template, so the original phone can prove possession without re-registering or changing its private key. Do not select registration/replacement, uninstall the app, clear data or rotate keys. Keep all tests in a dedicated terminal and stop that copy backend when finished.

1. In a dedicated PowerShell terminal, choose only the verified restored copy and start the backend on port 8001:

```powershell
Set-Location C:\FYP\FYP-Biometric-Attendance-System
$evidencePath = '.work\phase5-backup\20261101-184826\manifest.json'
$evidence = Get-Content $evidencePath -Raw | ConvertFrom-Json
if ($evidence.restored_database -notmatch '^attendance_p5_restore_[0-9a-f]{12}$' -or $evidence.restored_database -eq $evidence.source_database) { throw 'Not an isolated restored copy' }
$env:DB_NAME = $evidence.restored_database
$env:DEMO_MODE = 'false'
.\backend\venv\Scripts\python.exe -B -m uvicorn main:app --app-dir backend --host 0.0.0.0 --port 8001 --no-proxy-headers
```

2. Connect computer and Samsung to the intended home/lab Wi-Fi. Find the computer's LAN IPv4 using ipconfig. In a second terminal build with that actual LAN address (replace the placeholder), then install only with -r:

```powershell
Set-Location C:\FYP\FYP-Biometric-Attendance-System\frontend
& C:\Users\yap10\flutter\bin\flutter.bat build apk --debug --dart-define=API_BASE_URL=http://<computer-LAN-IPv4>:8001
$adb = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
& $adb devices -l
$samsungSerial = '<Samsung serial from adb devices -l>'
& $adb -s $samsungSerial install -r build\app\outputs\flutter-apk\app-debug.apk
```

Do not use localhost/ADB reverse for an authorised-network PASS. A direct LAN connection is required. Any Windows firewall change should be narrowly scoped to this isolated lab server; this task did not change firewall rules.

3. Sign in as DEMO001 normally, open My Device and confirm the existing Samsung installation matches. Open Network Verification on the COPY server before creating a policy. Its FAIL response shows the actual backend-observed source IP; do not substitute a client-reported IP.

4. From the project root, explicitly create a temporary test class and narrow source policy ONLY in the restored copy. Replace the address with the observed Samsung source (/32 for IPv4 or /128 for IPv6). The utility rejects production names and never changes any student/device/template/attendance row:

```powershell
.\backend\venv\Scripts\python.exe -B backend\tests\prepare_attendance_phone_test.py --evidence .work\phase5-backup\20261101-184826\manifest.json --student DEMO001 --cidr '<observed-Samsung-source-IPv4>/32'
```

It prints the copy database, temporary class PIN, policy ID and class expiry. The PIN is for the isolated test class. Policy activation is explicit and copy-only, not a campus claim. The class expiry does not automatically disable its policy.

5. On Samsung, enter that test PIN, complete real face/liveness, and observe automatic signing and the final result. A successful record is in the COPY only. Repeat the PIN and verify duplicate rejection. Disable the returned policy ID using manage_network_policy.py in a separate terminal with DB_NAME explicitly set to the COPY, then use a new test class/attempt to verify network denial and zero new attendance. Stop the copy backend and close its dedicated environment terminal when done.

No permanent production network policy is needed for these tests. The home range is an explicitly authorised simulation, not TARUMT's campus range. For a production deployment an institution-approved observed egress policy and reviewed transport/proxy topology are required.

## Remaining partner dependencies

No device-owned attendance-signing/network/writer hook remains unconnected. Attendance on an already ACTIVE Samsung registration uses the partner's existing server face/liveness authorization, not the separate Stage B3 enrollment test result.

The partner's institutional biometric template trust/enrollment/recovery provider remains necessary for real Slot 2 activation and device replacement; this task neither implements it nor grants trust to legacy templates. The Xiaomi candidate therefore remains inactive. Future changes to which templates may be used for attendance belong to that coordinated policy; this integration preserves current biometric matching policy and does not relabel COMPLETED_UNTRUSTED as a grant.

## Changed files in Phase 5

New backend: modules/authorization/{__init__,models,service,router,migration}.py; migrate_attendance_authorization.py; tests/test_attendance_authorization.py; tests/run_attendance_authorization_restored.py; tests/prepare_attendance_phone_test.py.
Changed backend: app.py (router composition); services/attendance.py (mandatory guarded existing writer); modules/biometrics/router.py and service.py (forwarding hooks); tests/test_workflow.py (real isolated authorization prerequisites); tests/test_network_verification.py (dependent fixture FK teardown order).
New Flutter: modules/devices/services/attendance_device_authorization.dart and authorized_attendance_biometric_api.dart; test/attendance_authorization_test.dart.
Changed Flutter: modules/biometrics/screens/camera_screen.dart (API injection); screens/attendance_flow_screen.dart (inject automatic signing adapter).
Documentation: this report; README.md; docs/API_INTEGRATION.md; docs/MODULE_OWNERSHIP.md; docs/openapi.json. Existing uncommitted Phase 4 changes were preserved.

No real replacement, physical installation, private-key operation or source biometric-template change was performed. Production attendance and all original rows were preserved. No commit, push or merge.

## Final preservation evidence

`.work/p5-final-evidence.json` confirms every original-column row projection across the 24 original tables still matches the pre-migration backup, including the five production attendance records. The source now has 26 tables; attendance_device_challenges, attendance_authorization_events and network_policies each contain zero production rows. Both backup/configuration hashes match. Existing historical attendance was retained without retroactively assigning device/network approvals.

AST comparison confirms every partner biometric method except the liveness forwarding signature/final call is identical to HEAD, and the entire liveness body before that final call is identical. Camera source is identical after removing only the API-injection hook. Native Android Keystore, inference/constants/templates and partner Flutter BiometricApi have no changes. No disposable p5 test database remains. The running backend exposes the new proof route and has proxy-header rewriting disabled.


## Early preflight before biometric capture (November 2026 refinement)

The normal student flow is now: valid PIN (`POST /attendance/start`) → signed, server-authoritative readiness check → camera → genuine face match and liveness → separate fresh final device proof → fresh final-request network check → existing attendance writer. An early rejection, unavailable backend/Keystore, malformed response, session change or timeout opens the existing **Verification result** view with the reason and never initializes the camera. The result view's class PIN check is complete; facial identity and live gesture remain incomplete. Return to attendance and enter the PIN again after correcting the problem.

New authenticated endpoints:

- `POST /api/v1/attendance/preflight-challenges`: `{ "attendance_challenge_id": "<PIN-issued attempt>", "public_key_fingerprint": "<64 lowercase hex>" }`. Checks ownership/login/window, face-stage pending state, current ACTIVE registered key (either slot) and the actual ASGI connection CIDR policy. Returns the existing device-challenge schema with `operation: "attendance_preflight"`, a base64 canonical signing payload and maximum 60-second expiry. Unknown JSON fields, including submitted IP/PASS fields, are rejected.
- `POST /api/v1/attendance/preflight`: `{ "attendance_challenge_id": "<same attempt>", "challenge_id": "<preflight nonce>", "signature": "<base64 DER ECDSA signature>" }`. Verifies the signature and exact student/login/attempt/class/device/key/slot/purpose/expiry binding, consumes the nonce and rechecks the current request's connection IP and enabled policies. Success: `{ "success": true, "result": "PASS", "attendance_authorized": false, "attendance_challenge_id": "...", "device_id": "...", "network_verification_id": 123 }`. Errors retain the existing `{success:false,code,message}` envelope.

The device fingerprint selects a registration; only the signature proves possession. Flutter reads/signs the existing Android key without creating or rotating keys. It does not cache preflight PASS or reuse its signature. The individual API/native operations are bounded, with a 40-second overall preflight UI timeout. No camera, facial request or liveness request is started until a genuine matching server response arrives.

No migration is required. The existing nonce table retains its `operation='attendance_authorization'` database constraint as the attendance-family discriminator; the signed payload's **purpose and operation** distinguish `attendance_preflight` from `attendance_authorization`. Preflight consumes its nonce before the final nonce can be issued. The existing unique open-attempt index, student/attempt locks, expiry, issuance rate limit and audit tables are reused. Audit action `preflight` and code `ATTENDANCE_PREFLIGHT_PASSED` identify readiness, never a final grant. Network records reuse the existing attendance-bound network audit operation and link to the attempt; the authorization audit distinguishes preflight from final authorization.

The final `/liveness/frame` writer remains mandatory, unchanged by this refinement. It requires genuine face matching and three accepted gesture frames, another signed nonce with purpose `attendance_authorization`, current ACTIVE ownership and a fresh ASGI-source policy decision in the insertion transaction. A preflight nonce (consumed or unconsumed), Profile PASS, client PASS flag or previous successful policy check is insufficient. Policy disablement, network changes, device revocation, expiry or replay after readiness still prevent insertion. Direct legacy clients do not gain any authorization by skipping preflight: the final guard remains fail closed. The preflight itself neither advances biometric state nor creates Attendance.

Changed files for this refinement:

- `backend/modules/authorization/service.py`, `router.py`: reuse the existing locked challenge/device/network service for signed readiness and typed REST responses.
- `frontend/lib/modules/devices/services/attendance_device_authorization.dart`: separate uncached preflight proof and strict server-response validation, using existing Keystore calls.
- `frontend/lib/screens/attendance_flow_screen.dart`: await preflight after valid PIN and route failures to the existing result view; injectable dependencies support navigation tests.
- Partner-owned `frontend/lib/modules/biometrics/screens/camera_screen.dart`: presentation-only `initialFailure` entry into its existing result UI, with no camera initialization/timers. No inference, thresholds, gesture, capture/orientation or attendance algorithm changes.
- `backend/tests/test_attendance_authorization.py`, `backend/tests/run_attendance_authorization_restored.py`, `frontend/test/attendance_authorization_test.dart`, new `frontend/test/attendance_preflight_test.dart`: readiness, proof separation, rejection/navigation, policy/device changes and final-write regressions.
- This document, `docs/API_INTEGRATION.md`, `docs/MODULE_OWNERSHIP.md`, and regenerated `docs/openapi.json`.

The restored test runner now snapshots all current production rows read-only before testing and compares them again afterward. Its historical backup remains a verified restored fixture; legitimate records created since that backup must not be mistaken for test modifications. All test writes/signing keys/policies remain isolated. No production schema, policies, attendance, registrations, templates or secrets are changed by this refinement; no physical app installation or key operation is performed.

Safe retest: restart the local backend with `--no-proxy-headers`, build Flutter with the intended API_BASE_URL, and update via `adb -s <Samsung-serial> install -r <apk>` only if installing later. Never uninstall or clear data. Use the earlier isolated restored-copy phone setup on port 8001 for actual attendance tests. With its policy disabled, a valid PIN must immediately show Verification result, with no camera permission prompt or capture. With an explicitly configured LAN simulation policy enabled and a registered installation, readiness allows the camera. Disable the copy's policy after readiness and before the last gesture frame: final authorization must fail with no new attendance row. ADB reverse/localhost is always rejected, regardless of broad CIDR ranges. Do not change production policy merely to pass tests.


### Preflight validation results

- Full backend: 200 tests run; 199 passed, 1 optional live-API test skipped. Isolated MariaDB schema/concurrency tests enabled with ATTENDANCE_DEVICE_MYSQL_TESTS=1.
- Full Flutter: 167 passed, 1 opt-in Slot 2 integration test skipped. Includes early policy/device rejection, unavailable backend, strict response binding, retained keys, separate final proof, final server network denial and camera-free failure/result lifecycle/navigation.
- Flutter analyze: no issues. Debug APK build passed; existing toolchain deprecation notices remain. APK was not installed and no physical keys were accessed. This build uses API_BASE_URL=http://127.0.0.1:8000 and intentionally cannot prove an authorised network through ADB reverse; build with the direct LAN URL for later network testing.
- Restored MariaDB: 27 cases passed. Exactly three disposable attendance rows were inserted only for intended successful final authorizations. Every rejection had zero attendance delta; readiness itself inserted none. Original restored rows stayed unchanged and the disposable database was dropped.
- Latest evidence: `.work/p5-restored-integration-0b5d7b753173.json`. Every current production row in all 26 tables matched the fresh pre-test snapshot. Current production baseline contains six attendance rows, one registered device and one network policy; these existing records were preserved, not changed to match the older historical backup. The original Samsung registration and encrypted face template are included in the verified row hashes.
- Logs: `.work/p5-preflight-all-backend.log`, `p5-preflight-all-flutter.log`, `p5-preflight-analyze.log`, `p5-preflight-build.log`, `p5-preflight-restored.log`.

Reproduce backend tests from project root:

```powershell
$env:ATTENDANCE_DEVICE_MYSQL_TESTS='1'
.\backend\venv\Scripts\python.exe -B -m unittest discover -s backend/tests
.\backend\venv\Scripts\python.exe -B backend/tests/run_attendance_authorization_restored.py --evidence .work/phase5-backup/20261101-184826/manifest.json
```

From frontend, run `flutter test` and `flutter analyze`. For later direct LAN testing, build with `flutter build apk --debug --dart-define=API_BASE_URL=http://<computer-LAN-IP>:8001` against the isolated restored backend. Restart the backend and update the app to load these changes; the existing running server/app have not been replaced during this refinement. No migration, production data write, policy change, commit or push was performed.
