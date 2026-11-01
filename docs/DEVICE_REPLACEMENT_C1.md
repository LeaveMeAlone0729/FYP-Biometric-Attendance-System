# Stage C1 device replacement implementation

Implemented on SH, 1 November 2026. The device-owned replacement flow is connected end to end. Real replacement remains fail closed until the partner supplies genuine institution-trusted biometric results and single-use approvals. No production test grants are installed.

## Chapter 4 design alignment

Reviewed `C:\Users\yap10\Downloads\YapSengHin_Chapter4_System Design (1).docx`: Module 3, Figure 4.7 (activity), Figure 4.12 (sequence), and Table 4.4 DEVICE_REPLACEMENT_REQUEST. Both diagrams require candidate PENDING -> face/liveness identity verification -> revoke old and activate new only on success; failure preserves the old device. Failed/cancelled/expired candidates are retained as terminal audit history rather than physically discarded.

The document predates the approved two-device/public-key policy: its one-ACTIVE-device and bearer-token wording is superseded by two ACTIVE slots and ECDSA P-256 possession proof. Replacement applies to exactly one occupied slot. The other slot never changes. Institutional trust is mandatory; ordinary COMPLETED_UNTRUSTED is not replacement approval.

## Reused components and database entity mapping

There is no duplicate biometric or activation service. `DeviceReplacementService` extends `PendingEnrollmentService` for preparation/cancellation. Existing proof/status/current endpoints, DeviceBiometricService, DeviceActivationService, Android Keystore bridge and Flutter camera/automatic activation coordinator are reused.

DEVICE_REPLACEMENT_REQUEST is represented by `pending_device_registrations WHERE operation='replace_device'`. This preserves the existing FK-linked biometric, activation and audit history rather than introducing a competing request table.

| Chapter 4 field | Physical representation |
| --- | --- |
| request_id | pending_registration_id |
| student_id | authenticated student_id |
| old_device_id | legacy slot_one_device_id FK; for replacement it anchors the selected old device in either slot |
| new_device_id | candidate_device_id; becomes a registered-device ID only after activation |
| biometric_result | server-owned device_biometric_sessions evidence; separate genuine trusted result/grant IDs in the activation challenge authorize the handover |
| verification_status | CHALLENGE_ISSUED, KEY_PROVEN, FAILED, EXPIRED, CANCELLED or ACTIVATED; trusted grant and challenge result are audited separately |
| requested_at | created_at |

New nullable `replaced_device_fingerprint` preserves the exact original key binding. Existing old-device IDs, public keys, fingerprints, statuses and registration timestamps are untouched by migration. Pending candidates are not inserted as ACTIVE registrations and consume no extra slot.

## REST contract

Every route requires the existing `Authorization: Bearer <login token>`. Extra trust/PASS/private-key fields are forbidden by the preparation/confirmation schemas. Student and auth-session hash are derived on the server.

New preparation endpoint:

```http
POST /api/v1/devices/replacements
```

```json
{"slot_number":1,"old_device_id":"server-device-id","platform":"android","public_key_spki":"base64-DER-SPKI","device_name":"New tablet","device_model":"Display metadata only"}
```

201 response (abridged):

```json
{"success":true,"pending_registration_id":"server-pending-id","candidate_device_id":"server-candidate-id","operation":"replace_device","slot_number":1,"replaced_device_id":"server-device-id","replaced_device_fingerprint":"old-key-sha256","public_key_fingerprint":"new-key-sha256","status":"CHALLENGE_ISSUED","algorithm":"ECDSA_P256_SHA256","signature_encoding":"base64-DER","signing_payload":"base64-canonical-server-JSON","challenge_expires_at":"ISO8601","expires_at":"ISO8601","activation_enabled":false,"attendance_authorized":false}
```

Retained routes under `/api/v1/devices/pending-registrations`:

| Method and suffix | Request | Result |
| --- | --- | --- |
| GET /current | none | current request for this login, including replacement target |
| GET /{id} | none | bound request status and original expiry |
| POST /{id}/proof | {"signature":"base64-DER"} | KEY_PROVEN after valid candidate-key signature |
| POST /{id}/cancel | {} | CANCELLED; registered devices unchanged |
| POST /{id}/activation-readiness | {} | ELIGIBLE plus genuine server approval/revision/result IDs, or fail closed |
| POST /{id}/activation-challenges | {"approval_id":"server-grant-id"} | fresh candidate-key activation challenge |
| POST /{id}/activate | {"approval_id":"server-grant-id","challenge_id":"server-challenge-id","signature":"base64-DER"} | server-confirmed ACTIVE replacement device; attendance_authorized=false |
| GET /{id}/activation-status | none | ACTIVE only while the resulting candidate is actually ACTIVE in the correct slot |

Biometrics use the existing attendance-free `POST /api/v1/device-approvals`, `POST /api/v1/device-approvals/{id}/face`, `POST /api/v1/device-approvals/{id}/liveness/frame`, and GET status. Replacement responses have operation=replace_device and the selected slot. Matching, threshold, random finger challenge and three consecutive accepted frames remain unchanged. B3 completion is still COMPLETED_UNTRUSTED.

Preparation proof expires within 120 seconds; the whole request within five minutes or login expiry, whichever is earlier. Activation challenge and genuine grant/result freshness remain at most 60 seconds and are further bounded by pending/login expiry. Retrying preparation with identical login/target/key returns the same open request without extending expiry. A different pending operation/target/key is rejected. A different login cannot take over a pending request.

Representative errors: REPLACEMENT_TARGET_NOT_FOUND (404), PENDING_EXISTS (409), KEY_ALREADY_REGISTERED (409), INVALID_SIGNATURE (403), CHALLENGE_EXPIRED (410), CANDIDATE_PROOF_REQUIRED (409), REPLACEMENT_BINDING_MISMATCH (403), REPLACEMENT_TARGET_CHANGED (409), APPROVAL_UNAVAILABLE (503), BIOMETRIC_TRUST_REQUIRED (403), APPROVAL_MISMATCH (403), APPROVAL_EXPIRED (410), APPROVAL_USED (409), INVALID_ACTIVATION_SIGNATURE (403), ACTIVATION_EXPIRED (410), ACTIVATION_REPLAYED (409), ACTIVATION_CONFLICT (409). All expected replacement/activation failures are audited through existing enrollment/activation event tables.

## Atomic handover and threat controls

All mutations lock student -> authenticated session -> pending request -> target registration -> nonce/grant/revision as applicable. This follows existing enrollment/activation lock ordering. Preparation serializes conflicting requests, including different occupied slots. The database retains generated ACTIVE-slot uniqueness on (student_id,active_slot), slot IN (1,2), globally unique key fingerprints, and one open candidate per student/slot.

Activation revalidates KEY_PROVEN, expiry, exact ownership/login, candidate canonical key, unchanged target ID/fingerprint/slot/status and purpose. The trusted provider must validate current trusted template revision and exact fresh result/grant binding. Old enrollment grants, another student's grant, a stale revision, a reused grant or B3 test ID cannot authorize replacement. Fingerprints select keys; ECDSA signatures prove possession. Model/hardware labels confer no trust.

Inside the existing savepoint: consume genuine grant -> mark only target REVOKED with reason/time -> flush the released target slot -> insert candidate ACTIVE in that same slot -> mark request ACTIVATED -> write success audits -> flush and recheck deadlines. Any insertion/authorization failure rolls back revocation and grant consumption. An owned submitted activation nonce is consumed on failure; a fresh challenge may be requested where prerequisites remain valid. Duplicate confirmation cannot revoke twice. Phase 2 rechecks ACTIVE status, so both new checks and previously issued but unsubmitted revoked-key proofs fail after replacement.

Cancellation locks the same student/request and makes further key proof, biometrics or activation fail. An already completed handover cannot be cancelled. Terminal biometric identity failure ends the replacement request without changing registrations. Wrong positioning/gesture feedback retains the existing recoverable biometric behavior. No attendance services or endpoints are invoked.

## Partner contract extension

The seven TrustedApprovalProvider methods and partner entry point are unchanged. ApprovalBinding now has optional `replaced_device_id` and `replaced_device_fingerprint` fields (None for existing enrollment). For replacement the provider must persist and compare both, operation=replace_device, selected slot, student, login hash, request ID, candidate ID/fingerprint and trusted template revision. They are necessary to prevent approving a different old device or slot with an earlier grant.

Partner dependency: institutional template provenance/current revision, secure enrollment/recovery/invalidation, fresh attendance-free trusted face/liveness result issuance, and transactional single-use grants for this entire binding. Legacy templates must not be automatically trusted. Do not relabel COMPLETED_UNTRUSTED sessions. See TRUSTED_BIOMETRIC_PROVIDER_CONTRACT.md. Missing integration stays unavailable in production; no production mock, flag or test route exists.

## Flutter flow and key safety

My Device offers Replace Slot 1/2 device for each occupied slot. The student starts on the new installation. The existing per-student Keystore alias is reused if present or created only after the explicit preparation action. A key already registered in any slot/history is rejected by the backend; an existing registered installation is rejected before key creation. No alias deletion, rotation, uninstall or app-data clearing is performed.

PendingDeviceScreen is configured with the selected target and reuses current/proof/status/cancel APIs. It shows the old device remains ACTIVE, expiry, key proof, failed/cancelled/completed status and biometric navigation. Reopening the same target on the same login restores matching server/key state. An expired terminal request for a different operation no longer blocks a new replacement. A different login waits for old request expiry. Keys persist throughout retries/restarts.

The separate B3 camera sends only device approval frames. After genuine server-confirmed completion it releases the camera, displays real PASS evidence with replacement-specific wording and automatically invokes readiness -> challenge -> retained-key signature -> confirm. Success returns through preparation to My Device, whose existing navigation callback reloads the authenticated device list and runs fresh automatic verification. An uncertain lost confirmation is reconciled by status once; signatures are not blindly replayed. Missing trust shows unavailable, preserves the old device and offers safe return. There is no manual verification or approval bypass button.

## Migration evidence and commands

Backup/configuration: `.work/stage-c1-backup/20261101-170753/`. Matching configuration is ACL-protected; do not publish it or the SQL backup. The manifest records SHA256 values and all original-column row counts/hashes for all 21 tables. The backup was restored into an isolated attendance_c1_restore_* schema and verified before DDL. Old backend workers were stopped. The migration was validated on the restored copy, applied to production, then rerun with no schema steps. All original records matched after both runs.

The upgrade adds only nullable target fingerprint metadata and carefully replaces known legacy CHECK definitions in single ALTER statements. It permits replace_device in slots 1/2 and terminal CANCELLED; existing enrollment remains restricted to Slot 2. No index, uniqueness constraint, registered row, biometric template or attendance row is removed or rewritten. Unknown schema drift aborts; every step is re-inspected and original row projections rehashed. Fresh installations use the updated device-owned SQLAlchemy models.

Executed from the project root while workers were stopped:

```powershell
.\backend\venv\Scripts\python.exe -B backend\migrate_device_replacement.py --evidence .work\stage-c1-backup\20261101-170753\manifest.json --validate-restored-copy
.\backend\venv\Scripts\python.exe -B backend\migrate_device_replacement.py --evidence .work\stage-c1-backup\20261101-170753\manifest.json --apply-production
```

Do not reuse stale evidence after the original data changes. Future deployment requires a fresh verified full backup/restoration and matching configuration. Application startup never applies this DDL automatically.

## Testing and safe reproduction

Backend full suite: 164 tests, 163 passed and one optional live-API test skipped. Includes real signature, expiry/replay, student/login/target mismatches, missing/untrusted/expired/reused approval, cancellation racing activation, conflicting concurrent preparations, concurrent activation, revoked-key rejection, late insert rollback including grant rollback, and unaffected-slot preservation. Relevant final pending/replacement/contract tests were rerun after recovery guard changes. Flutter tests cover retained keys, restart recovery, unavailable trust, exact target signatures, lost confirmation, both replacement actions and phone/tablet layouts. Flutter full suite: 142 passed, one opt-in integration test skipped in the regular run and exercised separately in all three real-HTTP modes. Flutter analyze: no issues. Android debug APK build succeeded. Final pending/replacement/API-contract rerun: 29 passed.

The existing opt-in real-HTTP runner now accepts replacement mode; it creates a disposable database/ephemeral loopback server, drives production Flutter services and My Device, uses real ECDSA signatures and actual REST/MariaDB transactions, then destroys its disposable database and key. Biometrics and institutional trust are controlled test fixtures, not camera-accuracy tests. Fixtures are confined to backend/tests and frontend/test and cannot be selected by production configuration/routes.

```powershell
# Project root; these do not touch production registrations.
.\backend\venv\Scripts\python.exe -B backend\tests\run_slot2_end_to_end.py --replacement-slot 1
.\backend\venv\Scripts\python.exe -B backend\tests\run_slot2_end_to_end.py --replacement-slot 2
.\backend\venv\Scripts\python.exe -B backend\tests\run_slot2_end_to_end.py
$env:ATTENDANCE_DEVICE_MYSQL_TESTS='1'
.\backend\venv\Scripts\python.exe -B -m unittest discover -s backend/tests -v
Set-Location frontend
& C:\Users\yap10\flutter\bin\flutter.bat test
& C:\Users\yap10\flutter\bin\flutter.bat analyze
& C:\Users\yap10\flutter\bin\flutter.bat build apk --debug --dart-define=API_BASE_URL=http://127.0.0.1:8000
```

Successful isolated evidence: Slot 1 `.work/slot2-e2e-d83d09ee228e/result.json`; Slot 2 `.work/slot2-e2e-fcc9ab735f4e/result.json`; original enrollment regression `.work/slot2-e2e-830381369653/result.json`. Each has a My Device screenshot, safe HTTP trace, committed row metadata and zero-attendance assertion. Both replacement tests verified old-target revocation and an unchanged other slot; the refreshed UI shows both ACTIVE devices and fresh verification PASS.

APK output: `frontend/build/app/outputs/flutter-apk/app-debug.apk`. No physical app was uninstalled, cleared or updated for this task. Do not test replacing the real Samsung Slot 1 during development. Use isolated runner fixtures to exercise successful replacement. The current production provider is unavailable, and no real replacement/activation request was submitted by this implementation task.

## Changed files

Backend composition/contracts: app.py; modules/devices/{pending_models,pending_schemas,pending_service,activation_models,activation_schemas,activation_service,approval_provider,biometric_models,biometric_schemas,biometric_service,service}.py.
New backend components: modules/devices/replacement_service.py, replacement_router.py, replacement_migration.py; migrate_device_replacement.py.
Backend tests: tests/test_device_replacement.py (new); tests/run_slot2_end_to_end.py (reused runner extended).
Flutter: modules/devices/screens/{my_device_screen,pending_device_screen,device_biometric_approval_screen,device_registration_screen}.dart; services/{pending_device_service,device_biometric_api,device_activation_service,device_activation_state}.dart; widgets/device_biometric_completion.dart.
Flutter tests: device_replacement_test.dart (new), device_activation_state_test.dart, slot2_end_to_end_test.dart.
Documentation: DEVICE_REPLACEMENT_C1.md (new), TRUSTED_BIOMETRIC_PROVIDER_CONTRACT.md, API_INTEGRATION.md, MODULE_OWNERSHIP.md and openapi.json.

No partner-owned algorithm/enrollment/deletion/camera source or attendance endpoint was modified. No Android native key code or aliases were changed. No commit, push or merge was performed.
