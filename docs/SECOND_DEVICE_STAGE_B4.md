# Stage B4 — historical preparation report

**Superseded for current behavior by [completed activation integration](SECOND_DEVICE_ACTIVATION_INTEGRATION.md).**
Public activation routes and production tables are now installed. The missing
trusted provider still blocks real activation; the historical evidence below
describes the earlier preparation-only stage.

## Scope and reuse

B4 prepares the last device-owned step. It does not issue institutional trust or
activate real devices. PendingEnrollmentService still owns KEY_PROVEN candidates,
student/auth/pending locks, capacity/history checks and enrollment audit. Existing
ECDSA SPKI/DER verification, ApprovalBinding, TrustedBiometricApproval and
validate_approval are reused. The older unsigned _activation_transaction skeleton
now rejects; signed activation is isolated in DeviceActivationService. No duplicate
registration writer remains callable through that old entry point.

DeviceActivationService.issue and confirm always return APPROVAL_UNAVAILABLE and
record rejection in the existing enrollment audit table. They do not need the new
B4 schema to exist. The private _issue_transaction/_confirm_transaction cores
are unrouted and use the same always-unavailable production provider. There is no
configuration, client flag, demo mode, environment switch or HTTP override that
unlocks them. The provider factory itself is unchanged. Fixture providers and
fixture revision/grant tables exist only in backend/tests/test_device_activation.py.
No application import/router registers those fixtures.

## Prepared transaction

1. Lock current student and login rows; validate active identity and ownership.
2. Lock the owned pending candidate and require unexpired KEY_PROVEN, proof time,
   unconsumed enrollment, operation enroll_second_device and Slot 2.
3. Lock device rows and recheck exactly one original ACTIVE Slot 1, unchanged
   Slot 1 ID, vacant Slot 2, no historical replacement shortcut and no duplicate
   public-key registration. Database slot CHECK and unique active-slot constraints
   remain the final guard. Names/model strings never establish device identity.
4. Ask the server provider to load/lock a real trusted grant and CURRENT trusted
   template revision. Validate all bindings, PASS, trust provenance, freshness
   (maximum 60 seconds), expiry and non-consumption. A B3 test ID/result cannot
   satisfy this contract. A template hash or biometric_status=active is not trust.
5. Issue a separate server activation nonce. It expires at the earliest of 60 s,
   grant expiry, pending expiry and login expiry. A repeated issue for the same
   still-valid exact binding returns the same challenge without extending expiry.
   Five new challenges per student per five minutes are allowed. At most one
   unconsumed activation challenge exists for a pending registration.
6. Require a fresh ECDSA P-256 SHA256 signature from the candidate's existing
   Keystore key over the exact decoded signing_payload bytes. Candidate proof and
   Phase 2 verification payloads cannot be substituted. Consume an owned submitted
   activation nonce even on invalid signature or rejected prerequisites. A foreign
   student/session/pending lookup cannot consume another candidate's nonce.
7. Revalidate provider grant/current revision and every binding after key proof.
   Inside one savepoint, consume the grant, insert ACTIVE Slot 2, consume pending
   enrollment and write success audits. Recheck deadlines before/after consumption
   and after flush. Signature/approval/capacity failures are audited. A failed insert
   or consumption rolls back the savepoint; the failure audit and consumed nonce
   can commit without consuming the grant or partially activating the candidate.
8. Caller owns the outer transaction and must commit before sending a success.
   The future HTTP adapter must catch DeviceRegistrationError as the existing
   registration_response/get_db convention does, preserving rejection audits and
   nonce use. No component commits internally. Unhandled infrastructure errors
   must roll back the whole outer transaction.

The candidate challenge stores approval ID and trusted revision ID. Its canonical
JSON signing payload includes version, purpose=device_activation, operation,
Slot 2, challenge ID, student/login binding, pending ID, candidate ID/fingerprint,
approval ID, trusted revision ID, server nonce and expiry. The returned payload is
base64; the signature is base64 DER. Never log payloads, signatures, tokens, images,
private keys or templates. DeviceActivationEvent stores only server identifiers,
action/result/reason codes and timestamps. Existing audit records are retained.

## Internal contracts, no public REST endpoints

Private fixture/review calls:

```text
_issue_transaction(db, student, auth, pending_id, approval_id)
  -> challenge_id, pending_registration_id, candidate_device_id,
     public_key_fingerprint, operation, slot_number, approval_id,
     trusted_template_revision_id, algorithm, signature_encoding,
     signing_payload, expires_at
_confirm_transaction(db, student, auth, pending_id, challenge_id, approval_id, signature)
  -> {success: true, device: {status: ACTIVE, slot_number: 2, ...},
      attendance_authorized: false}
```

Those success contracts are exercised ONLY with isolated trusted test fixtures.
Normal issue/confirm are hard-blocked. No activation or activation-challenge path
exists in FastAPI/OpenAPI. The B3 endpoints still produce COMPLETED_UNTRUSTED,
with every trust/consumption/activation flag false. Random gestures, three accepted
frames, partner algorithms, face threshold and attendance endpoints are unchanged.

## Storage and migration evidence

Prepared additive tables:

- device_activation_challenges: purpose/session/candidate/grant/revision-bound
  signed nonces; unique open pending registration; consumption consistency CHECK.
- device_activation_events: dedicated per-challenge issuance and PASS/FAIL audit.

No existing table/constraint is altered or removed. Application startup does not
create these tables. **Production schema is unchanged: B4 tables are not installed.**

Verified private SQL/config backup and evidence:
`.work/stage-b4-backup/20261101-034222/manifest.json`.
The SQL dump was restored into attendance_b4_restore_6254275f062d (see manifest for
exact restored database name; the manifest is authoritative). Every one of the 19
original tables matched its row count and sorted original-column SHA-256 digest.
Keep database.sql and backend.env private. Configuration/secrets were copied,
never generated or rotated. The backup folder has restricted Windows ACLs.

The migration was run only against that restored copy, validating original data
before/after, all schema steps, CHECK/unique enforcement probes and an idempotent
rerun. A CHECK-normalization mismatch stopped initial validation safely; it was
corrected and resumed. Both B4 tables now validate on the restored copy. Production
application workers were not stopped because no production DDL was attempted.

Repeat restored-copy verification from the project root:

```powershell
.\backend\venv\Scripts\python.exe -B backend\migrate_device_activation.py --evidence .work\stage-b4-backup\20261101-034222\manifest.json --validate-restored-copy
```

This CLI deliberately has no --apply-production mode and rejects the production
DB as its target. A future reviewed deployment must create fresh backup evidence,
validate a fresh restored copy, stop old workers, deploy the additive tables with
resumable validation, preserve original data and only then consider route/provider
integration. Do not apply production DDL as part of testing this UI.

## Flutter readiness and future automatic flow

DeviceActivationState accepts the dedicated untrusted result shape and exposes
key/face/liveness checks separately from activation. Automatic activation and
isActive remain false; incomplete or client-forged trust flags cannot advance it.
The completion view shows key/face/liveness PASS, NOT ACTIVE, trusted approval
NOT YET AVAILABLE, and Device activation UNAVAILABLE. There is only Back to My
Device. Preparation also explicitly states that approval/activation are unavailable.
No activation HTTP request, enabled activation button or new native key operation
was added. My Device still lists only backend-confirmed ACTIVE registrations and
runs existing verification automatically; no biometric PASS is cached as authority.

Future reviewed automatic chain (no manual verification button): a real trusted
server biometric workflow issues a fresh grant; device service obtains activation
nonce, signs with the retained candidate key, submits proof, then refreshes My
Device only after the committed backend ACTIVE response. This chain is documented
but deliberately not wired. A failed/uncertain response must be reconciled with
server registration state; never infer ACTIVE from local PASS or a submitted request.
Old COMPLETED_UNTRUSTED sessions must not be promoted into grants.

## Partner dependencies

The partner must implement approved biometric enrollment/deletion/recovery
boundaries, institution-approved current template revisions, legacy-untrusted
handling (including DEMO001), authorized administrator recovery without student
self-approval, revision invalidation and a persistent single-use grant provider.
The provider must lock current template trust and grant rows and participate in
the caller's transaction without committing. Integration and its TOCTOU/race
behavior need independent review. Until then production service methods and UI
remain blocked, regardless of face/liveness success. Fresh activation signature
support must then be wired to the retained Keystore key without rotating aliases.

## Retest B4 UI on tablet 7732690b

With the existing backend running, install in place; do not uninstall/clear data:

```powershell
Set-Location C:\FYP\FYP-Biometric-Attendance-System
$adb = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
& $adb -s 7732690b reverse tcp:8000 tcp:8000
& $adb -s 7732690b install -r frontend\build\app\outputs\flutter-apk\app-debug.apk
```

Renew expired candidate preparation with the retained key, complete B3, and verify
PASS checks plus NOT ACTIVE/approval unavailable/activation unavailable. Back to
My Device must not add Slot 2. No physical activation test is possible or intended.
Do not pass the emulator webcam profile for a real tablet. No Samsung app or key
operation is required. The newly built B4 APK has not been installed by this task.

## Completion evidence

- Full backend suite: 147 run, 146 passed, one optional live-API test skipped.
  All opt-in isolated MariaDB device/slot/replay/activation tests were enabled.
- Targeted B4 suite: 18 passed, including actual concurrent MariaDB confirmation.
- Full Flutter suite: 121 passed; flutter analyze clean; USB-localhost debug APK built.
- All 19 production tables still match the fresh B4 backup hashes, including every
  attendance, student/template, pending/B3 audit and registered-device record.
- Production has neither B4 table; ACTIVE Slot 2 count is zero. Samsung sh phone /
  SM-A346E remains ACTIVE Slot 1, original registered_at 2026-10-30 03:16:59, with
  unchanged original device ID, public key/fingerprint and all other stored fields.
- Protected partner biometric/attendance and B3 random/liveness sources match
  pre-change hashes. The configuration hash still matches the backed-up .env.
- No new public endpoint, trusted grant, production activation, phone installation,
  schema reset/reseed, Keystore operation, commit, push or merge was performed.

## Files changed for B4

Backend:

- backend/modules/devices/activation_models.py (new)
- backend/modules/devices/activation_service.py (new)
- backend/modules/devices/activation_migration.py (new)
- backend/migrate_device_activation.py (new, restored-copy validator only)
- backend/modules/devices/pending_service.py (disable superseded unsigned sketch)
- backend/tests/test_device_activation.py (new, fixtures only)

Flutter:

- frontend/lib/modules/devices/services/device_activation_state.dart (new)
- frontend/lib/modules/devices/screens/device_biometric_approval_screen.dart
- frontend/lib/modules/devices/screens/pending_device_screen.dart
- frontend/lib/modules/devices/widgets/device_biometric_completion.dart
- frontend/test/device_activation_state_test.dart (new)
- frontend/test/device_biometric_completion_test.dart

Documentation:

- docs/SECOND_DEVICE_STAGE_B4.md (new)
- docs/MODULE_OWNERSHIP.md
- docs/API_INTEGRATION.md

Private ignored backup/evidence and test logs are under .work and must not be
published. Existing uncommitted work from earlier stages was preserved.
