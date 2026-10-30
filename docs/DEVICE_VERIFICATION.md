# Phase 2: Automatic Device Verification

One shared FastAPI server and MySQL database. This phase reuses the registered
Phase 1 public key and the exact existing Android Keystore alias/sign method.
It never generates, rotates, deletes or replaces a key during verification.

## Automatic behavior

Open Student → Account & Sign Out → My Device. The page loads registration
information and automatically requests a fresh device check. Returning to the
page, or resuming the app while the page is present, requests another fresh check.
There is no Verify This Device or manual retry/verification button. The page
shows registered ACTIVE status separately from the latest check's PASS/error and
timestamp. PASS is point-in-time information, not a login-wide authorization.

My Device is a status-only screen. If no device exists, its enrollment link opens
`DeviceRegistrationScreen`, which preserves the Phase 1 registration flow. On
return, status is checked automatically. No replacement shortcut was added.
Login, biometrics, liveness, class PIN checks and attendance remain unchanged.
Verification is not yet invoked/enforced during attendance or required to log in.

## REST contracts

All requests use the same existing opaque bearer login token:

```http
Authorization: Bearer YOUR_LOGIN_TOKEN
Content-Type: application/json
```

The server derives the student and registered device; neither is chosen by the
request. Only operation `device_status` is currently accepted. Unknown fields,
client PASS flags and attendance operations/attempt IDs are rejected (422).

### POST /api/v1/devices/verification-challenges

```json
{"operation":"device_status"}
```

HTTP 201:

```json
{
  "success": true,
  "challenge_id": "SERVER_GENERATED_ID",
  "device_id": "REGISTERED_DEVICE_ID",
  "operation": "device_status",
  "public_key_fingerprint": "SHA256_HEX",
  "algorithm": "ECDSA_P256_SHA256",
  "signature_encoding": "base64-DER",
  "signing_payload": "BASE64_EXACT_BYTES_TO_SIGN",
  "expires_at": "2026-10-30T15:01:00+08:00"
}
```

The signed UTF-8 payload binds protocol version, purpose `device_verification`,
operation, student, device, registered-key fingerprint, challenge ID, a random
256-bit nonce and expiry. The database additionally binds the initiating bearer
session. Another login for the same student cannot confirm the challenge.

Expiry is 60 seconds, capped by login expiry. Each call gets a separate nonce;
parallel operations do not invalidate each other's pending challenges. Issuance
is limited to 20 challenges per student per rolling five minutes, stored in MySQL.

Decode the payload using standard padded Base64 and sign those exact bytes with
Android SHA256withECDSA. Send the ASN.1 DER signature in standard padded Base64.
Do not sign the Base64 text, reconstruct JSON or prehash the payload.

### POST /api/v1/devices/verifications

```json
{
  "challenge_id": "SERVER_GENERATED_ID",
  "operation": "device_status",
  "signature": "BASE64_DER_SIGNATURE"
}
```

HTTP 200:

```json
{
  "success": true,
  "result": "PASS",
  "verification_id": 123,
  "challenge_id": "SERVER_GENERATED_ID",
  "device_id": "REGISTERED_DEVICE_ID",
  "operation": "device_status",
  "verified_at": "2026-10-30T15:00:10+08:00",
  "challenge_expires_at": "2026-10-30T15:01:00+08:00",
  "attendance_authorized": false
}
```

`challenge_expires_at` is the proof-submission deadline, NOT a period during
which an earlier PASS can authorize other operations. `verification_id` is an
audit ID, not a bearer grant. The server consumes the challenge in the same
transaction as its PASS audit. No attendance row is inserted.

### POST /api/v1/devices/verification-failures

Best-effort negative diagnostics when the local key/signing API cannot be used:

```json
{
  "challenge_id": "SERVER_GENERATED_ID",
  "operation": "device_status",
  "reason_code": "LOCAL_KEY_MISSING"
}
```

Allowed reasons: `LOCAL_KEY_MISSING`, `LOCAL_KEY_MISMATCH`, `KEYSTORE_UNAVAILABLE`.
HTTP 200 returns `{"success":true,"result":"FAIL","code":"LOCAL_KEY_MISSING"}`.
These records are marked `source=client`. They are explicitly untrusted failure
reports; they can only consume the caller's own pending challenge as FAIL and
can never create PASS, register a device, replace a key or authorize attendance.

If the API cannot be reached, the Flutter service preserves the local error even
if reporting also fails. It does not invent a server audit record or retry a
possibly consumed signature. Any unreachable pending proof remains unusable
past its deadline; the server enforces expiry whenever it is submitted.

## Failure handling and audit

Module errors use `{"success":false,"code":"...","message":"..."}`.
Existing shared authentication/validation/database envelopes remain supported.

| HTTP | Code / meaning |
| --- | --- |
| 401 | Login missing, expired/revoked, or failed locked session recheck |
| 403 | DEVICE_NOT_ACTIVE, DEVICE_BINDING_CHANGED, DEVICE_KEY_INVALID, INVALID_DEVICE_SIGNATURE, OPERATION_MISMATCH |
| 404 | VERIFICATION_NOT_FOUND, including another student/login's challenge |
| 409 | DEVICE_NOT_REGISTERED, VERIFICATION_REPLAYED |
| 410 | VERIFICATION_EXPIRED |
| 422 | Unsupported operation, extra fields or malformed request schema |
| 429 | VERIFICATION_RATE_LIMITED |
| 503 | Shared database-unavailable response |

An invalid signature, expired owned challenge or changed/inactive binding is a
terminal FAIL. A replay logs FAIL but never overwrites an earlier PASS. Wrong
owners/logins receive 404 without consuming the rightful owner's challenge.
The account, login and device are locked/reloaded before proof acceptance; expiry
is checked again after signature verification. No process-local lock is used.

Flutter also distinguishes LOCAL_KEY_MISSING, LOCAL_KEY_MISMATCH,
KEYSTORE_UNAVAILABLE, SIGN_IN_REQUIRED, SESSION_CHANGED and network/API failures.
A session-revision guard prevents a pending signing operation from being submitted
under a new login, including a new login to the same account. Every verify()
invocation requests fresh proof; no PASS is cached or written into the profile.

## Database migration

New tables only:

- `device_verification_challenges`: student/session/device FKs, frozen key
  fingerprint, intended operation, signed payload, creation/expiry/consumption,
  PENDING/PASS/FAIL and terminal failure reason.
- `device_verification_events`: actor, device/challenge, operation, action,
  ISSUED/PASS/FAIL, reason code, server/client origin and timestamp.

Audit excludes raw signatures, private keys, bearer tokens and biometric images.
The new tables do not change registered keys, Phase 1 challenges/audit, accounts,
auth sessions, facial templates or attendance. Migration is idempotent:

```powershell
# From the repository root; do not rerun setup or regenerate .env.
.\backend\venv\Scripts\python.exe backend\migrate_device_verification.py
```

Phase 1 must already be initialized. `setup.py` includes both migrations for new
installations. Existing installations should use the targeted command above.

## USB Samsung test

Your connected SM-A346E is `RFCW30BZKAZ`; recheck with adb if necessary. Keep the
existing application/data and debug signing identity. Do not uninstall the app,
clear its data or re-register the phone: verification must use its Phase 1 key.

Terminal 1 (MySQL running):

```powershell
Set-Location 'C:\Users\yap10\OneDrive\Desktop\FYP-Biometric-Attendance-System'
.\backend\venv\Scripts\python.exe backend\migrate_device_verification.py
.\start-backend.ps1
```

Reuse/restart the existing API terminal if it already listens on port 8000.

Terminal 2:

```powershell
Set-Location 'C:\Users\yap10\OneDrive\Desktop\FYP-Biometric-Attendance-System'
$attendanceAdb = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
& $attendanceAdb devices -l
& $attendanceAdb -s RFCW30BZKAZ reverse tcp:8000 tcp:8000
.\start-frontend.ps1 -DeviceId RFCW30BZKAZ -ApiBaseUrl http://127.0.0.1:8000
```

Sign in and open My Device. Without pressing a verification button, expect
checking → PASS with a check time. Leave/reopen or background/resume and observe
a fresh check. Turn off the backend temporarily and reopen to test the connection
error; restore it and reopen. Do not delete a real key to test missing-key errors;
automated tests cover them. Existing attendance must still work as before.

Audit query (run locally in your existing MySQL tools):

```sql
SELECT event_id, student_id, challenge_id, operation, action, result, code,
       source, occurred_at
FROM device_verification_events
ORDER BY event_id DESC
LIMIT 20;
```

Each successful check has a new challenge and a server-origin DEVICE_VERIFIED
PASS entry. Device status remains ACTIVE independently of a failed current check.

## Automated checks

```powershell
$env:ATTENDANCE_DEVICE_MYSQL_TESTS = '1'
try {
  .\backend\venv\Scripts\python.exe -m unittest discover -s backend/tests -v
} finally { Remove-Item Env:ATTENDANCE_DEVICE_MYSQL_TESTS }
Set-Location frontend
flutter analyze
flutter test
flutter build apk --debug
```

MySQL concurrency tests create/drop only randomly named disposable schemas.
They cover replay races and simultaneous FAIL vs signed PASS. Existing registration
races/regressions also run. Flutter tests cover fresh signing, concurrent calls,
missing/mismatched keys, expiry/replay/signature/API errors, login changes, automatic
entry/resume and the absence of a manual verification button. Native messaging is
mocked in Flutter tests; confirm the physical phone flow above separately.

## Phase 5 integration

The reusable entry point is `DeviceVerificationService.verify()`. It already
performs challenge → existing-key signature → backend confirmation without user
interaction. Phase 5 should call it from the attendance coordinator, adding a
strict attendance-specific operation and server-validated attendance_attempt_id
binding to the request, signed payload and persisted evidence. That operation is
intentionally rejected today; do not reuse `device_status` PASS as an attendance
proof or send a PASS flag from Flutter. The final writer must revalidate device,
login, proof freshness, network and biometric evidence transactionally.

No changes were made to `/liveness/frame` or the attendance writer in this phase.
Android key attestation and device replacement remain outside this implementation.

## Verification results and file inventory

- Backend full suite with disposable MySQL tests enabled: 87 run, 86 passed,
  one existing optional live logout regression skipped.
- Final OpenAPI/biometric contracts: 3 passed.
- Flutter analysis: no issues. Flutter regression suite: 43 passed.
- Android debug APK: built successfully with the existing toolchain. Existing
  future-support warnings for Gradle/AGP/Kotlin remain; no upgrades were made.
- Existing row counts, all registered-device records and `.env` hash were
  unchanged by migration; a second migration was a no-op.
- Running backend exposes the verification routes. USB Samsung device detected.
- Actual Phase 2 verification on the physical phone still needs the manual
  navigation/test steps above. No real device was re-enrolled during this work.

| File | Change |
| --- | --- |
| backend/modules/devices/verification_models.py | Challenge and audit tables |
| backend/modules/devices/verification_schemas.py | Strict operation/proof/negative-report contracts |
| backend/modules/devices/verification_service.py | Fresh proof, locking, signature, expiry, replay and audit |
| backend/modules/devices/verification_migration.py | Additive two-table upgrade |
| backend/migrate_device_verification.py | Existing-install migration command |
| backend/modules/devices/router.py | Three Phase 2 REST endpoints |
| backend/modules/devices/schemas.py | Display ACTIVE/INACTIVE/REVOKED registration state |
| backend/setup.py | Register Phase 2 schema for new installs |
| backend/tests/test_device_verification.py | Security, audit, migration and MySQL race tests |
| frontend/lib/modules/devices/services/device_verification_service.dart | Automatic existing-key signing; no PASS cache |
| frontend/lib/modules/devices/services/device_api.dart | Verification/negative-diagnostic transport |
| frontend/lib/services/api_client.dart | Preserve error codes and expose session revision for stale-work checks |
| frontend/lib/modules/devices/screens/my_device_screen.dart | Status-only view; automatic entry/resume checks |
| frontend/lib/modules/devices/screens/device_registration_screen.dart | Preserved Phase 1 enrollment on its own screen |
| frontend/test/device_verification_test.dart | Automatic service/lifecycle/error/no-button tests |
| frontend/test/device_registration_test.dart | Existing registration regression targets the enrollment screen |
| docs/DEVICE_VERIFICATION.md | Phase 2 runbook and API contract |
| docs/DEVICE_REGISTRATION.md | Link the new screen/status behavior |
| docs/API_INTEGRATION.md | Shared REST and Phase 5 boundary |
| docs/MODULE_OWNERSHIP.md | Phase 2 component ownership |
| docs/openapi.json | Regenerated live API contract |
| README.md | Phase 2 entry point and migration |

Work remained on SH. No commits, pushes or merges were made. Existing backend
login, biometric algorithms, liveness/attendance writer and native Keystore
implementation were verified unchanged against the branch.
