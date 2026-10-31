# Completed device-owned Slot 2 activation integration

Device REST endpoints, automatic Flutter signing/navigation and the additive
production migration are implemented. The missing partner trust provider is an
external prerequisite, not an activation bypass. The real Xiaomi remains inactive.
Current B3 results remain COMPLETED_UNTRUSTED and cannot grant activation.

## REST contracts

All paths start with /api/v1/devices/pending-registrations/{pending_id}.
Use the same student bearer login that owns the pending request. Requests forbid
extra fields, student IDs, slot choices, biometric PASS flags and client revisions.
See docs/openapi.json for exact generated request/response schemas.

| Method and suffix | Body | Result |
| --- | --- | --- |
| POST /activation-readiness | {} | 200 ELIGIBLE from a genuine server grant; currently 503 APPROVAL_UNAVAILABLE |
| POST /activation-challenges | {"approval_id":"SERVER_GRANT_ID"} | 201 fresh/idempotently recovered bound activation challenge |
| POST /activate | {"approval_id":"SERVER_GRANT_ID","challenge_id":"SERVER_NONCE_ID","signature":"BASE64_DER_SIGNATURE"} | 200 committed ACTIVE Slot 2, or a rejection |
| GET /activation-status | no body | Current server ACTIVE/NOT_ACTIVE/EXPIRED and exact candidate/device binding |

Readiness success example (only genuine trusted provider can produce this):

```json
{
  "success":true,"status":"ELIGIBLE",
  "pending_registration_id":"PENDING_ID","candidate_device_id":"CANDIDATE_ID",
  "public_key_fingerprint":"SHA256_HEX","operation":"enroll_second_device","slot_number":2,
  "approval_id":"GRANT_ID","trusted_template_revision_id":"REVISION_ID",
  "biometric_result_id":"GENUINE_TRUSTED_RESULT_ID","expires_at":"SERVER_ISO8601"
}
```

Challenge success includes the same binding/grant/revision/result, plus challenge_id,
algorithm=ECDSA_P256_SHA256, signature_encoding=base64-DER, signing_payload and
expires_at. Decode signing_payload from base64 and sign the exact bytes with the
retained candidate Keystore key. Its canonical JSON binds version=1,
purpose=device_activation, operation, Slot 2, nonce, expiry, student/login,
pending/candidate/fingerprint, approval, trusted revision and trusted result ID.
Timestamp precision is normalized to MariaDB's persisted seconds for stable retry
payloads; deadlines never extend past grant, pending or auth expiry (maximum 60 s).

Activation success:

```json
{"success":true,"device":{"device_id":"CANDIDATE_ID","slot_number":2,
 "device_name":"Tablet","device_model":"Android","platform":"android","status":"ACTIVE",
 "public_key_fingerprint":"SHA256_HEX","registered_at":"SERVER_ISO8601"},
 "attendance_authorized":false}
```

Final status includes success, status, pending_registration_id, candidate_device_id,
public_key_fingerprint, operation, slot_number, device (ACTIVE matching row or null),
active_count, maximum_active_devices=2 and attendance_authorized=false. Status is
session-scoped. After a new login use My Device's authenticated registration list;
old-login pending requests cannot be taken over.

Common failures: APPROVAL_UNAVAILABLE (503), BIOMETRIC_TRUST_REQUIRED (403),
APPROVAL_EXPIRED (410), APPROVAL_USED (409), APPROVAL_MISMATCH (403),
APPROVAL_REVISION_CHANGED (403), CANDIDATE_PROOF_REQUIRED (409), PENDING_EXPIRED
(410), PENDING_NOT_FOUND/ACTIVATION_NOT_FOUND (404), ACTIVATION_BINDING_MISMATCH
(403), INVALID_ACTIVATION_SIGNATURE (403), ACTIVATION_REPLAYED (409),
ACTIVATION_EXPIRED (410), DEVICE_LIMIT_REACHED/REPLACEMENT_REQUIRED (409).
Unauthenticated requests return 401. No client PASS can satisfy the schemas.

## Transaction and replay safety

The Stage B4 transaction core is reused. Authenticated public methods now delegate
to it; they no longer hard-stop before genuine provider evaluation. Obsolete unsigned pending-service sketches have been removed; the signed activation service is the sole implementation. Student/auth/pending/device
locks, one open nonce per pending registration, slot CHECK/unique constraints,
canonical public-key validation and current capacity are rechecked. The candidate
signs a nonce separate from its initial key proof. Submitted owned failures consume
the activation nonce. Foreign student/session/pending lookups cannot consume it.

Provider grant/current revision/fresh result are independently validated at
readiness, issuance and confirmation. IDs from device_biometric_sessions are
explicitly rejected as trusted results. No B3 completion ID or client PASS is used
as an approval. The signed nonce also pins the trusted result ID so it cannot be
swapped between issuance and confirmation.

Grant consumption, ACTIVE Slot 2 insert, pending consumption and success audits
are atomic. Failure rollback preserves the grant and original registration while
allowing the denied attempt/nonce consumption to commit. Responses are sent only
after the existing get_db transaction dependency commits. Three-device insertion
is rejected and historical Slot 2 cannot be reused as a replacement shortcut.
No enrollment request imports or invokes the attendance writer.

## Flutter behavior

After B3 genuine server face/liveness completion, the camera/timers stop and the
coordinator automatically runs:

1. Read the retained local public key; never call getOrCreateKey or rotate aliases.
2. GET final status; recover a previously committed exact ACTIVE candidate safely.
3. POST empty readiness. B3 flags/test ID are not submitted. A separate fresh
   provider grant is the only source of eligibility.
4. Request challenge using that server grant; check all returned bindings against
   local key, completed candidate, login, pending, operation, slot and signed bytes.
5. Sign through the existing native Keystore channel and submit once.
6. Accept only matching server ACTIVE confirmation, return through preparation to
   My Device and refresh registrations. Display 2 / 2 ACTIVE devices only from
   the authenticated server list, never by incrementing local counts.

Calls are serialized per login/pending binding. Every async stage checks session
revision/navigation state. Requests/signing are bounded. Lost confirmation reads
status once instead of replaying the signature. Failed/unavailable/expired trust
stops with an explanation and safe Back to My Device. No enabled activation or
manual verification button exists. UI readiness flags alone never grant authority.

## Partner contract

See TRUSTED_BIOMETRIC_PROVIDER_CONTRACT.md and approval_provider.py. The optional
partner entrypoint is modules.biometrics.trusted_device_provider.create_device_approval_provider.
No partner source was created/changed. The absent adapter returns unavailable;
current templates including DEMO001 remain untrusted. The partner must provide
secure trust/recovery, a genuine attendance-free fresh result/grant issuer and
transactional validation/consumption. Existing untrusted B3 tests must not be
promoted. Once that independently validated grant exists, no downstream device
API/signing/navigation scaffold remains to implement.

## Migration and deployment evidence

Fresh private backup/config and all 19 original table hashes:
.work/stage-b4-backup/20261101-040601/manifest.json.
The SQL dump was restored and every original table verified. The additive migration
created only device_activation_challenges and device_activation_events on the
restored copy, checked every schema step and enforcement probe, and reran as a
no-op. Old backend launcher/reloader/worker trees were then confirmed stopped.
The same evidence-gated migration was explicitly applied to production, preserving
all original records and constraints; an immediate rerun was a no-op. Production
now has 21 tables. One hidden backend tree was restarted at 127.0.0.1:8000 with
--no-proxy-headers. No reset/reseed or secret regeneration was performed.

Commands used from the project root:

```powershell
.\backend\venv\Scripts\python.exe -B backend\migrate_device_activation.py --evidence .work\stage-b4-backup\20261101-040601\manifest.json --validate-restored-copy
# Stop all old backend workers and verify port 8000 is closed first.
.\backend\venv\Scripts\python.exe -B backend\migrate_device_activation.py --evidence .work\stage-b4-backup\20261101-040601\manifest.json --apply-production
```

Do not replay stale evidence after ordinary API activity. Create/verify a current
backup and restored copy for later changes. Keep database.sql/backend.env private.
Production adapter/result/grant fixture tables were never installed.

## Tablet retest

The latest APK was installed in place and the physical unavailable-provider result was verified. Never uninstall/clear data or touch Samsung keys for this test.
With the backend running:

```powershell
Set-Location C:\FYP\FYP-Biometric-Attendance-System
$adb = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
& $adb -s 7732690b reverse tcp:8000 tcp:8000
& $adb -s 7732690b install -r frontend\build\app\outputs\flutter-apk\app-debug.apk
```

Renew expired preparation with the same retained key, complete B3, and expect an
automatic readiness check followed by APPROVAL_UNAVAILABLE, NOT ACTIVE and safe
return. My Device must still show only Samsung Slot 1. Do not create production
approvals or delete/re-enroll templates to force the success branch. Successful
activation is exercised only in isolated trusted-provider tests until partner
trust is genuinely integrated. Do not pass an emulator webcam profile on tablet.

## Final verification

- Full backend: 150 tests, 149 passed and one optional live-API regression skipped.
  Isolated MariaDB device/slot/replay/activation concurrency tests were enabled.
- Final activation-specific suite: all 21 passed, including authenticated REST
  success, invalid/replayed signatures, trust/result/revision binding, rollback,
  real concurrent confirmation and explicit rejection of relabelled B3 test IDs.
- Flutter analyze: clean. Full Flutter suite: all 132 passed. Tests cover automatic
  readiness/challenge/sign/confirm, missing/expired/untrusted approval, wrong key,
  session changes, duplicate calls, lost-response reconciliation, timeout, safe
  navigation and existing biometric/attendance/phone/tablet UI regressions.
- Debug APK built with API_BASE_URL=http://127.0.0.1:8000. It was not installed by
  this task; use install -r above and never uninstall/clear data as a workaround.
- Live OpenAPI exposes all four activation routes; all four unauthenticated smoke
  requests returned 401. No real student token/login was used for smoke testing.
- All 19 pre-existing production table hashes still match the fresh backup after
  deployment, including templates, registered keys/devices, attendance and audits.
- New production activation tables each contain zero rows. No fixture tables are
  installed. The absent adapter resolves to UnavailableTrustedApprovalProvider.
- Real ACTIVE Slot 2 count is zero. Samsung sh phone / SM-A346E remains ACTIVE
  Slot 1 with its original device ID, public key/fingerprint and registration time
  2026-10-30 03:16:59. The real Xiaomi has not been activated.
- Protected partner biometric/attendance and B3 random/liveness files match their
  pre-change hashes. Matching backend configuration is unchanged. No native
  Keystore code, existing keys, biometric templates or attendance writer changed.
- No commits, pushes or merges were performed. Earlier uncommitted work was retained.

## Files changed in this integration

Backend: backend/app.py; backend/modules/devices/activation_service.py;
backend/modules/devices/approval_provider.py;
backend/modules/devices/activation_router.py (new);
backend/modules/devices/activation_schemas.py (new);
backend/migrate_device_activation.py;
backend/tests/test_device_activation.py;
backend/tests/test_device_biometrics.py;
backend/tests/test_pending_device_enrollment.py.

Flutter: frontend/lib/modules/devices/services/device_activation_service.dart (new);
frontend/lib/modules/devices/screens/device_biometric_approval_screen.dart;
frontend/lib/modules/devices/screens/my_device_screen.dart;
frontend/lib/modules/devices/screens/pending_device_screen.dart;
frontend/lib/modules/devices/widgets/device_biometric_completion.dart;
frontend/test/device_activation_service_test.dart (new);
frontend/test/device_biometric_test.dart;
frontend/test/device_biometric_completion_test.dart;
frontend/test/device_verification_test.dart.

Documentation: docs/openapi.json; docs/API_INTEGRATION.md;
docs/MODULE_OWNERSHIP.md; docs/SECOND_DEVICE_STAGE_B4.md (historical notice);
docs/SECOND_DEVICE_ACTIVATION_INTEGRATION.md (new);
docs/TRUSTED_BIOMETRIC_PROVIDER_CONTRACT.md (new).

The B4 activation models/schema constraints were reused unchanged. No additional
schema alterations or partner-owned source modifications were needed. Private
ignored SQL/config/manifest/log evidence under .work must not be published.

## Final cross-process and physical verification

See [final verification report](DEVICE_REGISTRATION_FINAL_VERIFICATION.md). The
actual Flutter services/HTTP endpoints/MariaDB integration successfully activated
isolated Slot 2 and rendered My Device at 2/2 ACTIVE. The physical Xiaomi passed
real face/liveness/key checks and correctly displayed APPROVAL_UNAVAILABLE and
NOT ACTIVE. Old unused unsigned B2 methods were removed, not left as placeholders.
