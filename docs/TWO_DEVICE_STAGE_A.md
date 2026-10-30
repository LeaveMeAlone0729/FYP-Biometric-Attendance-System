# Stage A — Two-device foundation

The database can represent at most two ACTIVE trusted key registrations per
student. SECOND-DEVICE ENROLLMENT IS NOT ENABLED. Stage B must supply a separate,
server-validated facial/liveness approval before any second registration can be
activated. Phase 3 replacement is also not implemented. No biometric algorithms,
biometric endpoints, attendance writer, native Keystore channel or key aliases
were changed.

## Storage policy

`registered_devices` retains its device primary key, globally unique public-key
fingerprint, original student FK and all existing fields. New fields are:

- `slot_number`: SMALLINT NOT NULL DEFAULT 1, CHECK in (1,2). Historical records
  retain their slot, so revocation cannot reset the initial-enrollment exception.
- `active_slot`: STORED generated CASE WHEN status='ACTIVE' THEN slot_number ELSE
  NULL END. Clients never choose or write this generated value.
- `revoked_at`, `revocation_reason`: nullable metadata reserved for Phase 3.

The old UNIQUE(student_id) is replaced by UNIQUE(student_id,active_slot), plus a
normal (student_id,status) FK-supporting/query index. Status is constrained to
ACTIVE/INACTIVE/REVOKED. Only one ACTIVE occupant can exist in each slot; NULL
active slots permit preserved inactive history. The globally unique key fingerprint
continues preventing key sharing between accounts. Display names/models are metadata,
not identity evidence. Direct SQL fixture insertion is used only in isolated tests.

## Enrollment remains locked

Both POST registration-challenges and POST registrations still lock the student
and reject ANY existing registration history with DEVICE_ALREADY_REGISTERED.
Only a student's initial registration can become ACTIVE, in slot 1. A stale valid
initial challenge cannot fill slot 2 after another registration wins. Concurrent
requests cannot use separate initial-registration exceptions. Strict schemas reject
invented approval flags, slot choices and extra device IDs. No pending-biometric
approval endpoint, override flag or replacement route is included in Stage A.

## Device list API

GET `/api/v1/devices` requires the existing bearer login and returns ACTIVE records
belonging to that student, ordered by slot. Example:

```json
{
  "success": true,
  "devices": [{
    "device_id": "EXISTING_DEVICE_ID",
    "slot_number": 1,
    "device_name": "sh phone",
    "device_model": "samsung SM-A346E",
    "platform": "android",
    "status": "ACTIVE",
    "public_key_fingerprint": "64_LOWERCASE_HEX_CHARACTERS",
    "registered_at": "2026-10-30T03:16:59+08:00"
  }],
  "active_count": 1,
  "maximum_active_devices": 2,
  "initial_registration_available": false,
  "additional_enrollment_enabled": false
}
```

GET `/api/v1/devices/current` remains a legacy single-history metadata endpoint.
It returns the one record (including inactive status) or null, and fails closed
with 409 DEVICE_SELECTOR_REQUIRED if there are multiple historical registrations.
It never arbitrarily selects the first device for verification.

## Fingerprint-selected automatic verification

Flutter reads its existing local Keystore public fingerprint BEFORE requesting a
challenge. It calls:

POST `/api/v1/devices/verification-challenges`

```json
{"operation":"device_status","public_key_fingerprint":"64_LOWERCASE_HEX_CHARACTERS"}
```

The fingerprint is only a selector. The server looks up that key under the
authenticated student and checks ACTIVE status, then binds the challenge to the
exact registration, stored key fingerprint, login and operation. Confirmation
continues to require the existing ECDSA P-256/SHA-256 signature:

```json
{"challenge_id":"SERVER_CHALLENGE_ID","operation":"device_status","signature":"BASE64_DER_SIGNATURE"}
```

Signature, ownership, ACTIVE state, expiry and single use remain mandatory. The
challenge's device ID selects the row during confirmation, rather than selecting
an arbitrary registration belonging to the student. A selector for another
account/unregistered key returns DEVICE_KEY_NOT_REGISTERED; it never registers it.
An omitted/invalid selector returns 422. Older clients must update; no insecure
fingerprint-free verification fallback is provided. PASS remains point-in-time
and `attendance_authorized` remains false.

With no local key, Flutter reports negative-only telemetry to the existing
verification-failures endpoint with `challenge_id: null` (or absent). Audit records
have source=client, result=FAIL, and no device/challenge attribution. This prevents
blaming the Samsung for a different installation's missing key. If a failure
occurs after issuance, the existing owned-challenge negative report is preserved.
These reports cannot create PASS, activate a slot or revoke either device.

## UI and Keystore

My Device displays up to two ACTIVE registrations and identifies `This installation`
only for the device returned by the current successful signed check. Verification
runs automatically on entry/resume; there is no verification button or PASS cache.
Additional enrollment is visibly locked. The enrollment form is available only
when the server says the account has no registration history.

The alias remains `attendance.device.v1.<hash of normalized student ID>` on each
Android installation. The Samsung's key is neither exported nor regenerated.
Separate physical installations have separate Keystores, even with the same alias.
The read/sign-only verification code never calls getOrCreateKey.

## Controlled migration and evidence

The verified private backup/configuration and evidence are stored under:

`.work/stage-a-backup/20261031-024259/`

This ignored directory contains sensitive SQL/configuration; keep it private.
`manifest.json` records SQL/configuration SHA-256 hashes, all original table counts
and data digests, restored-copy validation and live migration steps. The SQL backup
was restored into `attendance_stagea_restore_0c54999078`; all 15 tables matched.

The migration uses a database advisory lock and validates/resumes every schema
step. It first adds/backfills slot metadata and adds the new checks/indexes while
the original student-only unique index REMAINS IN PLACE. An exact temporary table
clone then proves two ACTIVE slots work, third/duplicate slots fail, invalid status
fails, and inactive history cannot be reactivated into an occupied slot. Only after
metadata validation AND enforcement probes succeed can the old index be removed.
Original-column projections are hashed before/after to detect changes to any
existing registration, audit, account, biometric or attendance record.

Commands used, from the repository root:

```powershell
.\backend\venv\Scripts\python.exe backend\migrate_two_devices.py --evidence .work\stage-a-backup\20261031-024259\manifest.json --validate-restored-copy
# Stop old Uvicorn launcher AND child workers; port 8000 must be closed.
.\backend\venv\Scripts\python.exe backend\migrate_two_devices.py --evidence .work\stage-a-backup\20261031-024259\manifest.json --apply-production
```

The migration is already applied; normal startup needs no migration command.
The CLI verifies the SQL/configuration hashes, restored-copy success and original
data baseline before live changes, and refuses to proceed while port 8000 is in
use. It does not create backups itself; use only a freshly verified backup/restore
manifest. After normal API activity, the old data baseline may differ, intentionally
blocking a replay with stale evidence. A new upgrade/recovery attempt needs a
current verified backup. Do not rerun setup, restore over production, or blindly
reinstate the old one-device index once two registrations exist.

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

MariaDB tests create/drop only randomly named isolated test schemas. Tests cover
both keys, owner-scoped selectors, invalid signatures, repeated/concurrent proofs,
third/duplicate slots, inactive history, blocked second enrollment, stale initial
proofs, migration interruption/wrong guards and idempotent resumption. Existing
registration, biometric, liveness and attendance regressions also run.

## Physical Samsung test

Keep the installed app's data, package identity and Keystore key. Do not uninstall,
clear app data, or re-register. Your Samsung SM-A346E is `RFCW30BZKAZ`.

The backend was restarted at its original `127.0.0.1:8000` address after migration.
USB reverse connects the phone to it:

```powershell
Set-Location 'C:\Users\yap10\OneDrive\Desktop\FYP-Biometric-Attendance-System'
$attendanceAdb = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
& $attendanceAdb devices -l
& $attendanceAdb -s RFCW30BZKAZ reverse tcp:8000 tcp:8000
Set-Location frontend
flutter build apk --debug --dart-define=API_BASE_URL=http://127.0.0.1:8000
& $attendanceAdb -s RFCW30BZKAZ install -r build\app\outputs\flutter-apk\app-debug.apk
```

Use a strict in-place adb install: if installation fails, stop and investigate;
do not uninstall as a workaround. Open Attend, sign in, and open My Device.
Expected: 1 / 2 ACTIVE devices, `sh phone` in slot 1, automatic PASS, `This installation`,
and additional enrollment locked until Stage B. Reopen/resume for another fresh check.
A second unregistered phone must not become ACTIVE. Do not insert a second real
registration manually: the two-device scenarios are isolated fixtures only.

An opt-in physical test lives in `integration_test/existing_device_smoke_test.dart`.
It reads/signs with the existing key, creates its own login and proof audit, then
logs out only that test login. It never enrolls or changes keys or attendance.
Use a prebuilt test APK installed strictly with adb -r, and attach
`test_driver/existing_device_smoke_driver.dart` with `flutter drive --use-existing-app`.
Do not use an install path that falls back to uninstalling the app. Restore the
normal main.dart APK with another in-place update afterward.


## Completion evidence (2026-10-31)

- Full backend suite: 97 tests run, 96 passed, one optional live logout test skipped.
- Final migration/security suite after explicit runtime-guard hardening: all 10 passed,
  including real MariaDB constraints, concurrency and resumable migration tests.
- Flutter analysis: no issues. Flutter unit/widget suite: all 46 passed.
- Debug APK build: passed. Existing-key integration test on USB Samsung SM-A346E: passed.
- Server audit event 22: DEMO001, original Samsung device, PASS / DEVICE_VERIFIED,
  2026-10-31 03:02:56 (application Asia/Kuala_Lumpur time).
- Normal lib/main.dart APK restored by a successful in-place update after the smoke test.
  Original and replacement APK signing certificates matched. No uninstall/data clear.
- All original rows across all 15 tables preserved. Biometric and attendance tables
  unchanged; original Samsung fields, public key, fingerprint, timestamp and ACTIVE
  status unchanged. It now occupies slot 1. Matching backend configuration unchanged.
- Expected physical-test additions only: one login session, one verification challenge,
  and two verification events (challenge issuance and signed PASS). Prior audit rows retained.
- Live migration and restored-copy validation passed; idempotent rerun made no schema changes.
  Private manifest records each step and original-data comparisons. Backup and restored
  copy are retained. Migration safety checks remain enabled even under Python -O.
- No commits, pushes, merges, replacement enrollment or second-device activation performed.

## Changed-file inventory

- `README.md`
- `backend/migrate_two_devices.py`
- `backend/modules/devices/models.py`
- `backend/modules/devices/router.py`
- `backend/modules/devices/schemas.py`
- `backend/modules/devices/service.py`
- `backend/modules/devices/two_device_migration.py`
- `backend/modules/devices/verification_schemas.py`
- `backend/modules/devices/verification_service.py`
- `backend/tests/test_device_verification.py`
- `backend/tests/test_two_device_stage_a.py`
- `docs/API_INTEGRATION.md`
- `docs/DEVICE_REGISTRATION.md`
- `docs/DEVICE_VERIFICATION.md`
- `docs/MODULE_OWNERSHIP.md`
- `docs/TWO_DEVICE_STAGE_A.md`
- `docs/openapi.json`
- `frontend/integration_test/existing_device_smoke_test.dart`
- `frontend/lib/modules/devices/screens/device_registration_screen.dart`
- `frontend/lib/modules/devices/screens/my_device_screen.dart`
- `frontend/lib/modules/devices/services/device_api.dart`
- `frontend/lib/modules/devices/services/device_verification_service.dart`
- `frontend/pubspec.lock`
- `frontend/pubspec.yaml`
- `frontend/test/device_registration_test.dart`
- `frontend/test/device_verification_test.dart`
- `frontend/test_driver/existing_device_smoke_driver.dart`
