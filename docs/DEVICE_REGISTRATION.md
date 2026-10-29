# Phase 1: Device Registration

This module adds registration only to the shared FastAPI/MySQL/Flutter Android app.
Login, face enrollment, face matching, liveness and attendance continue unchanged.
In particular, `/liveness/frame` still records attendance as before. Registration
is not yet an attendance prerequisite. No replacement, revocation, CIDR checks,
admin approval endpoint or final attendance coordinator is introduced in Phase 1.

## Implementation and ownership

- Backend: `backend/modules/devices/{models,schemas,crypto,service,router,migration}.py`.
- Android: `DeviceKeyStoreChannel.kt`, registered by `MainActivity.kt`.
- Flutter: `frontend/lib/modules/devices/`; open Student → Account & Sign Out → My Device.
- Existing partner code under `modules/biometrics/` is unchanged.

The native bridge uses the maintained Android Keystore APIs through Flutter's
standard MethodChannel (no new plugin or package dependency). Android generates
an EC `secp256r1` key with signing purpose and SHA-256. Private-key export is
unavailable; no delete, rotate, import-private-key or replacement method exists.
A background platform-channel queue keeps Keystore work off the Android UI thread.
The alias is derived from the authenticated student ID so accounts on a test phone
have separate installation keys. Names and models are descriptive client metadata.

References: [Android Keystore](https://developer.android.com/privacy-and-security/keystore),
[Flutter platform channels](https://docs.flutter.dev/platform-integration/platform-channels),
[Cryptography ECDSA](https://cryptography.io/en/latest/hazmat/primitives/asymmetric/ec/).

## REST contract

All three routes require the existing opaque login token:

```http
Authorization: Bearer YOUR_LOGIN_TOKEN
```

Do not supply a student ID. The server derives it from authentication. Use the
same login for challenge and confirmation. Another login, even for the same
student, cannot confirm the first login's challenge.

### POST /api/v1/devices/registration-challenges

```json
{
  "public_key_spki": "BASE64_DER_SUBJECT_PUBLIC_KEY_INFO",
  "platform": "android",
  "device_name": "My Samsung phone",
  "device_model": "samsung SM-A346E"
}
```

`device_name` is 1–100 characters, `device_model` 1–150. Only P-256 public keys
are accepted. Extra fields, private keys and client PASS flags are rejected.

Response: HTTP 201.

```json
{
  "success": true,
  "registration_id": "SERVER_GENERATED_REGISTRATION_ID",
  "algorithm": "ECDSA_P256_SHA256",
  "signature_encoding": "base64-DER",
  "signing_payload": "BASE64_EXACT_BYTES_TO_SIGN",
  "expires_at": "2026-10-30T15:02:00+08:00"
}
```

Decode `signing_payload` with standard padded Base64. Sign those exact bytes
using Android `SHA256withECDSA`; do not reconstruct JSON, prehash it, or sign the
Base64 string. Encode the resulting ASN.1 DER ECDSA signature using standard
padded Base64 without line breaks. The Python verifier uses ECDSA/SHA-256.

The signed UTF-8 JSON binds protocol version, operation `device_registration`,
registration ID, student ID, canonical public-key SHA-256 fingerprint, random
256-bit nonce and expiry. The database additionally binds the original bearer
session and freezes the submitted name/model/key. The confirmation accepts only
the ID and signature; the caller cannot swap enrollment data afterward.

Lifetime is 120 seconds, capped at the login expiry. A new challenge consumes
older pending registrations for that student. Five successful challenge issues
per student per rolling five minutes are allowed; registration does not use
process-local locks or rate-limit state.

### POST /api/v1/devices/registrations

```json
{
  "registration_id": "SERVER_GENERATED_REGISTRATION_ID",
  "signature": "BASE64_DER_ECDSA_SIGNATURE"
}
```

Response: HTTP 201.

```json
{
  "success": true,
  "device": {
    "device_id": "SERVER_GENERATED_DEVICE_ID",
    "device_name": "My Samsung phone",
    "device_model": "samsung SM-A346E",
    "platform": "android",
    "status": "ACTIVE",
    "public_key_fingerprint": "64_LOWERCASE_HEX_CHARACTERS",
    "registered_at": "2026-10-30T15:00:20+08:00"
  }
}
```

### GET /api/v1/devices/current

Returns HTTP 200 with the same `device` object, or:

```json
{"success": true, "device": null}
```

It never creates a key or registration. Public-key material is stored in MySQL
but not returned by this status endpoint. It exposes no other student's device.

### Failure responses

Module failures use:

```json
{"success":false,"code":"INVALID_SIGNATURE","message":"The device signature could not be verified. Start registration again."}
```

| Status | Codes / meaning |
| --- | --- |
| 401 | Shared sign-in/session failure; `SESSION_EXPIRED` on a locked recheck |
| 403 | `INVALID_SIGNATURE` |
| 404 | `REGISTRATION_NOT_FOUND` (also another account/login's challenge) |
| 409 | `DEVICE_ALREADY_REGISTERED`, `KEY_ALREADY_REGISTERED`, `CHALLENGE_CONSUMED`, `DEVICE_REGISTRATION_CONFLICT` |
| 410 | `CHALLENGE_EXPIRED` |
| 422 | `INVALID_PUBLIC_KEY`, or existing shared validation envelope with `fields` |
| 429 | `REGISTRATION_RATE_LIMITED` |
| 503 | Existing shared database-unavailable response |

Shared authentication/validation errors retain their existing envelope and may
have no `code`. Never branch on human-readable message strings.

An invalid signature or expired owned challenge consumes it. Subsequent attempts
return 409. Wrong-owner/login requests return 404 without consuming the owner's
challenge. A replay never changes the registered key. Lost successful responses
can be recovered by GET current; the Flutter screen does this automatically.

## Database and migration

New tables only:

- `registered_devices`: student FK (unique), canonical public SPKI, unique
  SHA-256 fingerprint, name/model, platform, ACTIVE status and registration time.
- `device_registration_challenges`: account/login FKs, frozen enrollment data,
  signed payload, creation/expiry/consumption times.
- `device_registration_events`: student FK, optional registration/device IDs,
  action, outcome, reason code and timestamp. No signature, raw image, password,
  bearer token or private key is recorded in audit events.

Student/auth row locks serialize owned mutations. A unique student constraint
prevents two device registrations; a unique key fingerprint prevents reuse by
another account. Cross-account insert races use a savepoint so the failed audit
and nonce consumption survive the unique-key conflict. Router-owned failure
responses commit those audit-only outcomes through the existing DB dependency;
they do not call the biometric `context.reject()` commit helper.

Migration from the repository root:

```powershell
.\backend\venv\Scripts\python.exe backend\migrate_devices.py
```

This idempotently creates only the three new tables, requires existing students
and auth_sessions tables, and leaves all existing rows, columns and `.env` intact.
It does not invoke the old device_hash-dropping migration or regenerate secrets.
`setup.py` also registers/creates these tables for new installations; existing
installations should use the targeted command above, not rerun full setup.

Phase 1 deliberately has no device deletion/replacement API. The unique student
constraint reserves one registration; future approved replacement needs an
explicit migration/state transition retaining history. Do not delete database
rows or clear app data as a replacement shortcut.

## Run on the USB-connected Android phone

The phone detected during implementation was `RFCW30BZKAZ` (Samsung SM-A346E).
Use `adb devices -l` again if the connection changes.

Terminal 1, from the repository root (start MySQL first):

```powershell
Set-Location 'C:\Users\yap10\OneDrive\Desktop\FYP-Biometric-Attendance-System'
.\backend\venv\Scripts\python.exe backend\migrate_devices.py
.\start-backend.ps1
```

If the existing backend already listens on 8000, reuse/restart it in its original
terminal rather than launching a second copy. Its reload mode detects source edits.

Terminal 2, USB forwarding avoids dependence on Wi-Fi or the PC LAN address:

```powershell
Set-Location 'C:\Users\yap10\OneDrive\Desktop\FYP-Biometric-Attendance-System'
& "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe" devices -l
& "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe" -s RFCW30BZKAZ reverse tcp:8000 tcp:8000
.\start-frontend.ps1 -DeviceId RFCW30BZKAZ -ApiBaseUrl http://127.0.0.1:8000
```

Rebuild/relaunch rather than hot reload after adding native Kotlin code. Sign in,
open Student → Account & Sign Out → My Device, enter a name, and register. Confirm
ACTIVE, revisit/restart and confirm the local key still matches. Opening on a
second installation must not offer replacement. Existing attendance must still
work without any registered device. USB reverse is local test transport, not
future network verification evidence.

## Automated verification

```powershell
# Repository root: backend workflow, crypto, API, migration and biometric tests.
.\backend\venv\Scripts\python.exe -m unittest discover -s backend/tests -v

# Optional real MySQL races: creates and drops ONLY a random disposable schema.
$env:ATTENDANCE_DEVICE_MYSQL_TESTS = '1'
try {
  .\backend\venv\Scripts\python.exe -m unittest discover -s backend/tests -p test_device_registration.py -v
} finally { Remove-Item Env:ATTENDANCE_DEVICE_MYSQL_TESTS }

Set-Location frontend
flutter analyze
flutter test
flutter build apk --debug
```

The opt-in MySQL test requires CREATE/DROP DATABASE permission and never clears
the configured application database. It tests concurrent confirmation of one
challenge and simultaneous registration of the same key by different students.
Flutter tests mock platform messaging and do not certify physical Keystore
behavior; perform the phone registration flow above for that final validation.

## Assurance and future boundaries

The client uses Android Keystore without an exportable fallback. The server
proves possession of a P-256 key, not that an arbitrary REST caller used genuine
Android hardware: verified key attestation is outside Phase 1. Hardware-backed
storage is device-dependent. First registration trusts the authenticated account;
it is not supervised identity proof. Losing the key requires a future approved
replacement workflow. HTTPS is required outside isolated local development.
Later phases can reuse the public key for fresh operation-bound possession
challenges, CIDR policy checks and the final attendance coordinator described in
API_INTEGRATION.md. No Phase 1 result should be treated as attendance authorization.

## Implementation verification and changed files

Checks completed on SH:

- Backend full suite with disposable-MySQL concurrency enabled: 65 tests run,
  64 passed and one existing optional live logout regression skipped.
- Biometric/OpenAPI contracts rechecked after final export: 3 passed.
- Flutter analysis: no issues. Flutter tests: 29 passed.
- Android debug APK built successfully. Existing Gradle/AGP/Kotlin future-support
  warnings remain; their versions were not changed for this feature.
- Live backend exposes the three device routes and returns 401 without login.
- Active database migration applied; existing row counts and `.env` hash were
  unchanged. A second migration was a no-op.
- Physical Android registration still needs the manual steps above; no account
  was automatically bound to a device during implementation.

Files added or modified for this feature:

| File | Purpose |
| --- | --- |
| backend/modules/devices/__init__.py | Separate module package |
| backend/modules/devices/models.py | Three new database models |
| backend/modules/devices/schemas.py | Strict request/response contracts |
| backend/modules/devices/crypto.py | P-256 public-key validation and DER signature verification |
| backend/modules/devices/service.py | Ownership, single-use challenge, rate limit, locking and audit |
| backend/modules/devices/router.py | Three authenticated REST endpoints |
| backend/modules/devices/migration.py | Additive/idempotent table creation |
| backend/migrate_devices.py | Targeted existing-database upgrade command |
| backend/app.py | Router registration |
| backend/setup.py | New-install schema registration |
| backend/tests/test_device_registration.py | Security, preservation and real MySQL race tests |
| frontend/android/app/src/main/kotlin/com/example/frontend/DeviceKeyStoreChannel.kt | Non-exportable Android key generation and signing |
| frontend/android/app/src/main/kotlin/com/example/frontend/MainActivity.kt | Register native channel |
| frontend/lib/modules/devices/services/device_key_store.dart | Typed native bridge |
| frontend/lib/modules/devices/services/device_api.dart | REST client |
| frontend/lib/modules/devices/screens/my_device_screen.dart | Registration/current-device/recovery UI |
| frontend/lib/screens/student_profile_screen.dart | Student UI entry point |
| frontend/test/device_registration_test.dart | Transport, channel and screen regression tests |
| docs/DEVICE_REGISTRATION.md | API, migration, assurance and phone-test runbook |
| docs/API_INTEGRATION.md | Link the new shared API without changing biometric contracts |
| docs/MODULE_OWNERSHIP.md | Device module boundaries |
| docs/openapi.json | Generated public API contract |
| README.md | Phase 1 availability and migration entry point |

The four pre-existing edits in `.gitignore`, `frontend/analysis_options.yaml`,
`frontend/android/gradle.properties` and `frontend/pubspec.lock` were preserved.
No changes were committed, pushed or merged. Biometric algorithm/service files,
login endpoints and the attendance writer were not modified.
