# Self-service Slot 2 and device replacement

6 November 2026, branch SH. The newer [ACCOUNT_BOUND_FYP policy](FYP_ACCOUNT_BOUND_ENROLLMENT.md) supersedes initial-enrollment and MariaDB validation limitations below. Device-owned implementation under the confirmed FYP
policy. No production database, real binding/template, mobile app or Android key
was changed. No tunnel, commit, push or branch merge was performed.

## Policy and result

Students cannot remove/change their face in the app. Faculty identity recovery
and face replacement remain external and are not implemented here. Faculty
approval is **not requested for each ordinary device operation**.

The missing partner trusted_device_provider dependency is replaced by the
built-in LocalDeviceApprovalProvider. It automatically authorizes an eligible
operation after authenticated login, candidate-key possession and fresh
face/liveness against a previously verified enrollment revision. It does not
establish the identity of an initially enrolled face.

| Item | Result |
|---|---|
| Slot 2 | Working through actual REST/crypto/DB transactions in isolated synthetic demo; real unverified enrollments remain blocked |
| Replacement of either slot | Working in isolated demo, preserving the other slot and rejecting revoked keys |
| External per-operation approval provider | Removed; local server authorization is still mandatory |
| Current/legacy initial face identity provenance | UNVERIFIED; nothing is automatically marked institution-trusted |
| Supervisor demo | Ready for the explicitly synthetic offline protocol demo; physical/production readiness remains partial |

First Slot 1 bootstrap registration remains the existing authenticated key-proof
process. It does not confer identity provenance on a face or allow a second
registration through the initial endpoint.

## Why removal of Remove Face was insufficient

The partner removed both student UI deletion and DELETE /biometrics and blocked
re-enrollment of existing/missing/inactive records. That prevents the former
self-service template substitution path. First enrollment still verifies account
credentials, consent and a detected face; it does not prove institutional student
identity. Therefore active status, consent and face matching alone cannot create
an enrollment-provenance record. Legacy templates, including DEMO001, are not
silently elevated.

## Authorization sequence

1. Prepare a Slot 2 or replacement candidate using the existing pending routes.
   The backend binds its server-generated candidate/pending IDs, authenticated
   student/session, canonical public-key fingerprint, operation, slot and old
   target ID/fingerprint. Candidate proof uses the retained Android Keystore key.
2. At creation of a **new** biometric session, capture an existing valid enrollment
   revision and the exact operation binding. Missing provenance leaves this scan
   untrusted. Adding a revision later cannot upgrade an old completed scan.
3. Run the existing partner face detection/encoding/distance threshold and random
   finger challenge, with the unchanged three accepted liveness frames. Raw B3
   results deliberately remain COMPLETED_UNTRUSTED / UNTRUSTED_TEST_RESULT with
   trusted=false. Those raw flags are never activation authority.
4. Only after genuine fresh completion, and only if the pre-captured revision is
   still valid for the exact encrypted template, persist a **separate** biometric
   result and single-use device authorization with distinct server IDs. Lifetime
   is at most 60 seconds and bounded by session/pending/login expiration. No
   client PASS, public grant-creation endpoint or faculty request is involved.
5. Flutter automatically checks activation status/readiness. An ELIGIBLE response
   is followed by a new activation challenge, a signature from the existing
   candidate key and confirmation. No manual device-verification button is added.
6. The existing activation transaction validates signature, ownership, every
   binding, current revision/template hash, fresh result, expiry, replay and slot
   capacity. It consumes the authorization in the same savepoint as the insert.
   Replacement revokes the checked old device only inside that successful
   transaction; rollback preserves both the old device and unused grant.
7. My Device refreshes only after server-confirmed ACTIVE. Phase 2 rejects the
   old key after replacement and allows the new key. The other slot is unchanged.
   A device proof still does not authorize attendance: fresh final attendance
   device proof, actual-source CIDR and partner face/liveness checks remain.

Current password login/Profile access is not globally revoked by device
replacement; the revoked installation loses trusted-device/attendance eligibility.

## Stored data and one-time enrollment boundary

Five additive tables, no updates to existing records by the migration:

| Table | Purpose | Runtime permissions |
|---|---|---|
| school_provisioned_accounts | Offline school provisioning attestation/reference and date | SELECT only |
| device_enrollment_revisions | Current encrypted-template hash, provenance, external evidence reference, verification/invalidation dates; unique current revision per student | SELECT only |
| device_enrollment_observations | Revision and exact binding captured before a fresh biometric session | SELECT, INSERT |
| device_biometric_authorizations | Distinct result/grant IDs, source observation, binding, revision, completion/expiry/consumption dates; one grant per source session | SELECT, INSERT, UPDATE(consumed_at) only |
| device_trust_events | Capture, issue and consume audit events, without biometric images or tokens | INSERT only |

The conservative production app has **no enrollment-trust writer**. The opt-in isolated FYP actor may INSERT an ACCOUNT_BOUND_FYP revision only during first enrollment of an offline school-provisioned account; it cannot modify/invalidate revisions or write school attestations. An external verified
enrollment handoff may supply an external_verified revision matching the current
encrypted face template and an actual evidence reference. How faculty verifies
identity or replaces that face is outside this app. The conservative production database runtime account
cannot insert, update or invalidate these enrollment revisions. There is no
faculty/student approval UI or recovery REST endpoint. Invalidating/changing a
revision or template blocks outstanding grants.

The synthetic_fixture provenance is accepted only on explicitly tagged
**in-memory SQLite test Sessions**. MySQL, normal Sessions, file-based SQLite,
client fields, DEMO_MODE and environment variables cannot enable it. The fixture
is confined to backend/tests/test_device_management.py and the offline runner;
normal app composition never sets its Session marker. Do not copy test fixtures
or label real enrolled students synthetic to make production activation pass.

## REST compatibility and errors

Existing routes are retained:

- POST /api/v1/devices/pending-registrations and /{id}/proof.
- POST /api/v1/devices/replacements, using the shared pending/proof lifecycle.
- POST /api/v1/device-approvals and /{id}/face, /{id}/liveness/frame.
- POST /api/v1/devices/pending-registrations/{id}/activation-readiness.
- POST /api/v1/devices/pending-registrations/{id}/activation-challenges.
- POST /api/v1/devices/pending-registrations/{id}/activate; GET /{id}/activation-status.

Readiness request remains `{}`. Eligible responses contain the existing opaque
approval_id, trusted_template_revision_id and biometric_result_id and the exact
candidate binding; the client cannot supply or decide these verdicts. Activation
confirmation remains `{approval_id, challenge_id, signature}`. The old raw B3 ID
cannot be substituted for the new authorization/result IDs.

Errors: BIOMETRIC_TRUST_REQUIRED (403, enrollment provenance not established),
FRESH_BIOMETRIC_PROOF_REQUIRED (403, no qualifying fresh scan), existing
APPROVAL_MISMATCH/APPROVAL_EXPIRED/APPROVAL_USED and signature/replay errors.
APPROVAL_UNAVAILABLE (503) now means authorization storage/schema unavailable,
not a missing faculty provider. Flutter distinguishes unverified enrollment and
fresh-scan-required states without claiming ACTIVE or rotating a key.

Pending responses now say biometric_approval_status=NOT_CHECKED. Their
activation_enabled=false and the raw B3 flags remain false: these responses are
not final authorization. The separate activation flow supplies actual eligibility.
The initial-registration listing's additional_enrollment_enabled=false continues
to mean the initial API cannot directly activate another device; use pending
enrollment followed by fresh biometric authorization.

## Migration safety and current status

No production MariaDB schema change was executed. The five-table migration was
validated against a fresh disposable MariaDB 10.4.27 verified restore, with all
26 original table hashes unchanged, actual restricted-runtime REST tests,
concurrency checks and three graceful restarts. See the account-bound policy
report for current evidence. Production application remains separately controlled.

The operator entry point **only accepts isolated restored databases**:

```powershell
.\backend\venv\Scripts\python.exe -B backend\migrate_device_management.py `
  --profile '<private-isolated-profile.json>' --evidence '<verified-restore-evidence.json>'
```

It has no production mode, defaults or trust seeding. Profile fields: db_host
(127.0.0.1), db_port (never 3306), db_name (fypdevicemgmt_restore_ plus 12 hex
characters), db_user (fyp_device_migrator), private db_password and expected_datadir
(inside C:/FYP/DB-DeviceManagement). Evidence must name the same restored database,
a different source_database, restored_backup_verified=true, sql_dump/sql_sha256,
and the original all-table baseline in the existing backup format. Never share
the private password/profile. Rehearse using an isolated server and account only.

The runner validates the backup hash, endpoint/datadir, original row hashes before
and after, existing Stage A slot guards, each created/resumed table and a no-op
rerun. It never alters existing tables/constraints or creates database accounts.
Supply approved operator privileges for new-table DDL plus original baseline
reads; do not grant runtime trust-writing authority. Stop if any evidence or
validation fails. Do not run setup/seed/reset or copy corrupted system tables.

The guarded runtime grant policy was extended narrowly for these four tables;
the guarded launcher intentionally rejects an old schema/grant set. Existing
production configuration/secrets and actual grants were not changed.

## Controlled supervisor demonstration

From the repository root:

```powershell
.\backend\venv\Scripts\python.exe -B backend\tests\run_device_management_demo.py
```

This starts **no server or tunnel**, accepts no real identity/DB/port arguments,
blocks external database connections and uses the actual local provider through
the actual ASGI REST/signing/transaction pipeline. Enrollment provenance and
biometric inputs are explicitly synthetic fixtures; P-256 signatures are real
disposable software keys. It demonstrates Slot 2, both replacement slots,
revocation, unaffected-slot preservation, untrusted-enrollment rejection,
signature replay rejection and blocked face deletion/re-enrollment.

Output: ignored `.work/device-management-demo.json`, labelled OFFLINE SYNTHETIC
IN-MEMORY DEMONSTRATION with real_identity_trust_proven=false. It records zero
attendance and no production/mobile access. It is not an approval service and
does not prove institutional identity or physical camera/Keystore behavior.

## Manual mobile tests still required

Use spare test installations, synthetic students and a separately verified
private backend/disposable database. Do not overwrite/uninstall the real Samsung
app, clear its data, change its key or use the real student's enrollment/bindings.

1. Register a first test device and record its fingerprint. Restart normally and
   confirm the existing key is retained and automatic verification still passes.
2. For an **unverified** synthetic enrollment, prepare a second device and finish
   real camera face/liveness. Expect enrollment-provenance rejection, NOT ACTIVE,
   no new registration, no attendance and the first device unchanged.
3. Positive real-camera testing may now use a NEW school-provisioned synthetic
   account and first enrollment under the explicit ACCOUNT_BOUND_FYP demo policy.
   Alternatively it needs actual external institutional provenance. The offline fixture is not
   deployable to the production/MariaDB runtime. Until that prerequisite exists,
   do not claim real-phone activation works or fabricate external approval.
4. Once that prerequisite and isolated migration validation exist, prepare Slot 2
   with its own retained key. Complete face/liveness; automatic readiness/signing
   must end with two server-confirmed ACTIVE devices. Restart backend/apps and
   verify persistence and independent fresh proofs from both keys.
5. Use a third spare installation with its own distinct candidate key to replace
   only disposable Slot 2, then an explicitly approved disposable Slot 1.
   Confirm selected old-key rejection, new-key PASS, unchanged other-slot PASS,
   no premature revocation on failures, expiry/replay/session rejection and zero
   attendance from enrollment/replacement.
6. Test private-LAN attendance separately: unapproved CIDR/ADB loopback remains
   denied and final authorization still requires new device proof and biometrics.

Never report software-key or deterministic-inference fixture tests as proof of
Android hardware non-exportability or real face/liveness accuracy.

## Earlier local validation (superseded by account-bound acceptance)

| Check | Result |
|---|---|
| Full backend suite, external DB connections disabled | PASS: 227 passed, 10 opt-in/live tests skipped |
| New local-provider security tests (included above) | PASS: 21 tests |
| Offline synthetic protocol demonstration | PASS: 6 scenarios, zero attendance inserts |
| Regenerated biometric/OpenAPI contract tests | PASS: 4 tests |
| Full Flutter suite | PASS: 183 passed, 1 skipped |
| Flutter analysis | PASS: no issues |
| Python source parsing | PASS: 119 files |
| Git whitespace/conflict checks | PASS |

Evidence is retained in ignored `.work/backend-validation.json`,
`.work/device-management-demo.json`, `.work/device-management-flutter-verified.json`
and their associated logs. These earlier results are supplemented by the restored-MariaDB migration,
restricted-account, concurrency and restart checks in the account-bound report.
Physical-camera accuracy and real Android Keystore behavior remain manual tests.
No production migration or institutional identity verification was performed.

## Source changes

New management_models.py, management_approval.py and management_migration.py;
offline migrate_device_management.py; new test_device_management.py and
run_device_management_demo.py. Existing approval composition, device biometric
completion hooks, pending status, runtime grants and associated tests were updated.
Flutter changes are device-module status/guidance and tests. API schema was
regenerated. Partner inference, attendance writer, network rules, Keystore aliases and native
key code were not changed. The subsequent account-bound policy adds only first-
enrollment authorization/provenance hooks to the biometric service/router; see
the newer report for that source list and current validation.
