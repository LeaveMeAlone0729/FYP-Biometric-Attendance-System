# Stage B2 — second-device preparation (activation disabled)

B2 adds candidate preparation only. There is no Slot 2 activation endpoint,
configuration flag, demo bypass, emulator exemption, working biometric provider,
or client PASS flag. Existing initial enrollment, automatic verification,
biometric algorithms/lifecycle, attendance endpoints/writer and native Keystore
sources/aliases are preserved. Stage B1 institutional trust/recovery remains the
partner's prerequisite. Possession of an account password plus a self-enrolled
face is not institutional identity evidence.

## Storage and invariants

- `pending_device_registrations` stores candidate public SPKI, fingerprint, name/model,
  opaque candidate ID, student/session, original Slot 1 ID, fixed Slot 2 and operation,
  server challenge, expiry, proof/consumption timestamps and status.
- `device_enrollment_events` stores attributed issuance, successful KEY proof,
  failures and expiry events. A CANDIDATE_KEY_PROVEN / PASS event means key possession
  only; it is NOT biometric approval, device trust or attendance authorization.
- Neither table stores a private key, raw frame or biometric template. Device names,
  model names and client hardware identifiers are not identity evidence.
- Generated `open_slot` is 2 only for CHALLENGE_ISSUED/KEY_PROVEN. Unique
  `(student_id,open_slot)` allows one live pending enrollment; expired/failed history
  is retained. CHECK constraints enforce Slot 2, operation and allowed statuses.
- Existing registered-device slot/check/fingerprint constraints stay unchanged.
- Enrollment locks student then login then owned pending records. It requires
  exactly one historical registration: ACTIVE Slot 1. Any Slot 2 history requires
  future approved replacement, even if that device was revoked. Two ACTIVE devices
  reject a third candidate. Pending preparation does not reserve an ACTIVE slot.
- Proof challenge: 120 seconds. Pending lifetime: five minutes, both capped by
  login expiry. Expiry is applied lazily on access; no background deletion occurs.
- Any submitted invalid signature consumes its challenge. Missing malformed fields
  are schema failures before proof processing. Owned valid proof cannot be replayed.
- Identical student/login/key begin retries return the same pending record without
  extending expiry. A different key/login conflicts until the open request expires.
  KEY_PROVEN retries recover status, rather than issuing another proof challenge.
- Failed audit responses use the existing commit-preserving error boundary. Unexpected
  database/transaction failures roll back, so a success is never returned uncommitted.

## REST API

All endpoints use the existing student bearer authentication and strict Pydantic
inputs. Student/login bindings are derived from the bearer, never accepted as fields.

| Method/path | Behavior |
|---|---|
| GET `/api/v1/devices` | Existing fields plus `pending_enrollment_available`; `additional_enrollment_enabled` remains false. |
| POST `/api/v1/devices/pending-registrations` | Start/idempotently recover candidate proof, HTTP 201. |
| GET `/api/v1/devices/pending-registrations/current` | Latest open candidate for this exact login, or most recent history/null. |
| GET `/api/v1/devices/pending-registrations/{id}` | Read owned/login-bound pending state. |
| POST `/api/v1/devices/pending-registrations/{id}/proof` | Consume challenge and verify ECDSA signature. |
| POST `/api/v1/device-approvals` | Require an owned, unexpired KEY_PROVEN candidate, then return 503 APPROVAL_UNAVAILABLE. |
| GET `/api/v1/device-approvals/{id}` | Authenticated 503 APPROVAL_UNAVAILABLE scaffold. |
| POST `/api/v1/device-approvals/{id}/face` | Authenticated 503; no frame parser, storage or inference. |
| POST `/api/v1/device-approvals/{id}/liveness/frame` | Authenticated 503; no frame parser, storage or inference. |

Do not upload camera frames to B2 scaffolds. No approval resource is created and
arbitrary approval IDs cannot become authorization. There is no `/activate` route.
An API client must inspect HTTP status and `code`, not infer success from reaching
an endpoint. OpenAPI is exported to `docs/openapi.json`.

Begin input:

```json
{
  "public_key_spki": "BASE64_DER_P256_SPKI",
  "platform": "android",
  "device_name": "My tablet",
  "device_model": "Android tablet"
}
```

Response (timestamps and IDs are server-generated):

```json
{
  "success": true,
  "pending_registration_id": "OPAQUE_PENDING_ID",
  "candidate_device_id": "OPAQUE_CANDIDATE_ID",
  "public_key_fingerprint": "64_LOWERCASE_HEX_CHARACTERS",
  "slot_number": 2,
  "operation": "enroll_second_device",
  "status": "CHALLENGE_ISSUED",
  "algorithm": "ECDSA_P256_SHA256",
  "signature_encoding": "base64-DER",
  "signing_payload": "BASE64_SERVER_PAYLOAD",
  "challenge_expires_at": "SERVER_ISO8601_TIME",
  "expires_at": "SERVER_ISO8601_TIME",
  "key_proven_at": null,
  "activation_enabled": false,
  "biometric_approval_status": "UNAVAILABLE",
  "attendance_authorized": false
}
```

The decoded signing payload binds version, fixed operation/slot, pending/candidate
IDs, student, login-session hash (not the bearer token), fingerprint, nonce and
challenge expiry. Android signs its decoded UTF-8 bytes using SHA256withECDSA.

Proof input:

```json
{"signature":"BASE64_DER_SIGNATURE"}
```

Proof success returns the same response shape, `status: KEY_PROVEN`, a proof time
and `signing_payload: null`. ACTIVE status is never created by this endpoint.

Approval input:

```json
{"pending_registration_id":"OPAQUE_PENDING_ID"}
```

Expected B2 response, HTTP 503:

```json
{"success":false,"code":"APPROVAL_UNAVAILABLE","message":"Trusted biometric approval is not integrated. Candidate remains inactive."}
```

Other errors include KEY_ALREADY_REGISTERED, PENDING_EXISTS, DEVICE_LIMIT_REACHED,
REPLACEMENT_REQUIRED, INITIAL_REGISTRATION_REQUIRED (409), INVALID_SIGNATURE (403),
CHALLENGE_CONSUMED (409), CHALLENGE_EXPIRED/PENDING_EXPIRED (410), PENDING_NOT_FOUND
(404 for another student/login), ENROLLMENT_RATE_LIMITED (429), and strict schema
errors (422). Five new successful pending issuances per five minutes are allowed.

## Partner integration contract and activation dependency

`approval_provider.py` defines a server-only protocol and frozen binding/grant
objects. Its ONLY production provider is UnavailableTrustedApprovalProvider.
No environment setting, student request, demo mode or framework dependency can
select a permissive provider. The server-only validator rejects absent/untrusted,
failed, expired, consumed, future-dated or mismatched grants.

A future partner adapter must load and lock an authentic persisted approval and
CURRENT institutional trust revision in the same SQLAlchemy transaction. It must
check the actual current encrypted-template binding, revocation, student and login,
operation, Slot 2, pending ID, candidate ID/fingerprint, and fresh server-produced
face/liveness evidence. A grant lasts at most 60 seconds and is single-use.
`trusted_template_revision_id` must come from trusted server state, not the client.
Pure dataclass validation does not prove provenance or current-template trust;
those are mandatory provider responsibilities. `consume` must perform a guarded
single-use update and must NOT commit independently.

`activation_preparation` is a hard-disabled, unrouted entry point.
`_activation_transaction` documents/prepares lock, capacity, validation,
provider-consumption, insert, pending-consumption and audit in one savepoint; its
provider always refuses before any insert. It is not a production-ready activation
API. Before enabling it, independent review must add a fresh candidate-signed
activation challenge, implement and validate the real partner adapter and
lifecycle invalidation, test atomic rollback/races, then explicitly replace the
hard stop and introduce a reviewed route. No flag can unlock this work today.

The partner must deliver the approved B1 enrollment/deletion hooks, legacy-untrusted
revision tracking, institutional staff authentication/independent recovery approval,
trusted revision invalidation, and an attendance-free face/liveness workflow.
Do not call `/attendance/start`, `/verify-face`, `/liveness/frame`, or the attendance
writer from device preparation. The existing biometric service writes attendance
on liveness completion and is unsuitable as an approval endpoint.

## Flutter behavior

My Device retains automatic verification on entry/resume. It shows Slot 2 preparation
availability separately from disabled enrollment/activation. An unregistered
installation can open Prepare this second device. A currently verified registered
installation is directed to use the second Android installation.

The new screen reads pending status without generating keys. Only the explicit
Prepare Slot 2 enrollment action may call the existing getOrCreateKey. It reads
first, rejects an already registered fingerprint, reuses a candidate key if present,
and never rotates/deletes a key. The unchanged per-student alias is local to each
Android installation, so a tablet has its own private key even with the same alias.
The service checks login revision around each asynchronous proof step and recovers
a lost proof response through owned status rather than blindly replaying it.

The UI shows KEY_PROVEN, EXPIRED and API/Keystore errors and explains that biometric
approval is unavailable and the candidate is not ACTIVE. There is no manual
verification button, camera workflow, activation button or cached PASS authorization.

## Controlled migration

Private SQL/config backup and SHA-256/data evidence:
`.work/stage-b2-backup/20261031-221838/manifest.json`.
The matching configuration and SQL must remain private. All original 15 tables were
verified against the restored copy `attendance_b2_restore_dbe2b47730da` before schema
work. The new migration creates only the two B2 tables. It preserves all original
tables/rows, checks Stage A guards, validates each new table on resumption, probes
constraints on a temporary clone and checks idempotent reruns. It fails closed on
malformed existing new tables rather than dropping or recreating them.

Commands from the repository root:

```powershell
.\backend\venv\Scripts\python.exe -B backend\migrate_pending_devices.py --evidence .work\stage-b2-backup\20261031-221838\manifest.json --validate-restored-copy
# Stop all backend workers; port 8000 must be closed.
.\backend\venv\Scripts\python.exe -B backend\migrate_pending_devices.py --evidence .work\stage-b2-backup\20261031-221838\manifest.json --apply-production
```

The CLI requires a verified restored backup, matching SQL/configuration hashes,
original data baseline and restored migration evidence before production changes.
After ordinary API activity, use a new verified backup instead of stale evidence.
Keep B2 routes unavailable if the migration has not been applied. Do not run setup,
reseed, restore over production or roll back by deleting candidate/audit history.

## Safe tablet/emulator testing

The Samsung app is not uninstalled, cleared or updated by B2 development. Do not
rotate its key or re-register it. No production face enrollment/deletion is needed.

1. Start the existing backend on 127.0.0.1:8000 after migration.
2. Connect a physical tablet or start a tablet AVD. List IDs with adb devices -l.
3. Build/install ONLY to the explicitly selected tablet/emulator:

```powershell
Set-Location 'C:\FYP\FYP-Biometric-Attendance-System'
.\backend\venv\Scripts\python.exe -m uvicorn main:app --app-dir backend --host 127.0.0.1 --port 8000 --no-proxy-headers --reload
# A second PowerShell terminal:
$attendanceAdb = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
& $attendanceAdb devices -l
# Replace this with the tablet/AVD ID, never the Samsung serial.
$attendanceCandidate = 'emulator-5554'
& $attendanceAdb -s $attendanceCandidate reverse tcp:8000 tcp:8000
Set-Location 'C:\FYP\FYP-Biometric-Attendance-System\frontend'
& C:\Users\yap10\flutter\bin\flutter.bat build apk --debug --dart-define=API_BASE_URL=http://127.0.0.1:8000
& $attendanceAdb -s $attendanceCandidate install -r build\app\outputs\flutter-apk\app-debug.apk
& $attendanceAdb -s $attendanceCandidate shell am start -n com.example.frontend/.MainActivity
```

Stop if installation fails; do not uninstall or clear data as a workaround.
Sign in as DEMO001 on the candidate, open My Device, then Prepare this second device.
Enter a candidate name and prepare once. Expect KEY_PROVEN plus APPROVAL_UNAVAILABLE;
registered count remains 1/2 and Samsung remains ACTIVE Slot 1. No biometric frames
or attendance are involved. Same-session retries reuse the pending request; after
expiry prepare again with the same retained key. A different login must wait for
the old request to expire. Candidate preparation creates expected pending/audit and
login/verification diagnostic records, but never trusted device/attendance rows.

An emulator may exercise Keystore signing and inactive preparation only. This is
NOT hardware authenticity or a physical-device attestation claim. B2 adds no
emulator/production bypass and cannot activate ANY candidate. Future hardware
attestation/Play Integrity policy needs separate implementation and review.

## Automated checks

```powershell
$env:ATTENDANCE_DEVICE_MYSQL_TESTS = '1'
try { .\backend\venv\Scripts\python.exe -B -m unittest discover -s backend/tests -v }
finally { Remove-Item Env:ATTENDANCE_DEVICE_MYSQL_TESTS }
Set-Location frontend
& C:\Users\yap10\flutter\bin\flutter.bat analyze
& C:\Users\yap10\flutter\bin\flutter.bat test
& C:\Users\yap10\flutter\bin\flutter.bat build apk --debug
```

MariaDB tests create/drop only randomly named disposable test databases. No tests
log in to or change the Samsung or production DEMO001 account. Physical Samsung
verification is a separate manual check; automated regression signs real ECDSA
keys in isolated fixtures and leaves the phone installation untouched.


## Completion evidence

- Full backend regression: 109 run, 108 passed, one optional live logout test skipped.
  This includes 12 B2 tests and the opt-in real MariaDB concurrency/constraint tests.
- Flutter analysis: no issues. All 55 unit/widget tests passed (nine new B2 tests).
- Android debug APK built successfully; existing Gradle/AGP/Kotlin future-support
  warnings remain. No toolchain changes or installation bypass was added.
- Restored and production migrations both passed with constraint enforcement probes;
  immediate reruns created no tables. All 15 original tables' data remained identical.
- Production new tables were empty after migration. registered_devices count remained
  one and attendance count remained three. Original biometric, login and device audit
  records were preserved; no production login or proof was generated for testing.
- Samsung DEMO001 / sh phone remains ACTIVE Slot 1, original device ID, public key,
  fingerprint and registered_at 2026-10-30 03:16:59 unchanged. The app and Android
  Keystore were not touched. Physical Samsung verification was not rerun in B2;
  unchanged verification behavior is covered by isolated regression tests.
- All protected biometric/attendance/auth/native sources and backend configuration
  were verified unchanged. Backend restarted with its original launch arguments.
- No activation, production biometric approval, emulator bypass, commits, pushes
  or merges were performed. The partner dependency remains unresolved intentionally.

## Changed-file inventory

- `README.md`
- `backend/app.py`
- `backend/migrate_pending_devices.py`
- `backend/modules/devices/approval_provider.py`
- `backend/modules/devices/pending_migration.py`
- `backend/modules/devices/pending_models.py`
- `backend/modules/devices/pending_router.py`
- `backend/modules/devices/pending_schemas.py`
- `backend/modules/devices/pending_service.py`
- `backend/modules/devices/schemas.py`
- `backend/modules/devices/service.py`
- `backend/tests/test_pending_device_enrollment.py`
- `docs/API_INTEGRATION.md`
- `docs/DEVICE_REGISTRATION.md`
- `docs/MODULE_OWNERSHIP.md`
- `docs/SECOND_DEVICE_STAGE_B2.md`
- `docs/openapi.json`
- `frontend/lib/modules/devices/screens/my_device_screen.dart`
- `frontend/lib/modules/devices/screens/pending_device_screen.dart`
- `frontend/lib/modules/devices/services/device_api.dart`
- `frontend/lib/modules/devices/services/pending_device_service.dart`
- `frontend/test/pending_device_test.dart`

## Enrollment UI follow-up

The refined UI hides repeated preparation after KEY_PROVEN and opens an independent,
disabled biometric requirements screen. It no longer requests unavailable approval
automatically after proof. See [DEVICE_BIOMETRIC_APPROVAL_UI.md](DEVICE_BIOMETRIC_APPROVAL_UI.md)
for retained-key/session behavior and the partner camera reuse boundary.

## Stage B3 supersedes approval scaffolds

Pending/key proof behavior is preserved. The device-approval URLs now run untrusted
face/liveness TEST sessions. The trusted provider and activation are still disabled.
See [SECOND_DEVICE_STAGE_B3.md](SECOND_DEVICE_STAGE_B3.md).
