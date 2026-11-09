# FYP account-bound first enrollment

6 November 2026, branch SH. This is the confirmed demonstration policy, distinct
from institutional identity verification. It supersedes the earlier statement
that every usable enrollment needs an external institution-verified handoff.

## Assurance and limitations

School operators pre-create accounts with fixed student IDs and assigned demo
passwords. They separately attest the accounts in `school_provisioned_accounts`.
Only an authenticated active account on that roster can enroll under the FYP
policy. The first successfully stored face is permanently bound to the server
session's student ID. This is **ACCOUNT_BOUND_FYP**, never **INSTITUTION_VERIFIED**.

An assigned password proves control of that account, not the identity of the
person presenting a face. Someone who obtains the password before first
enrollment could bind their own face. Fixed/shared/known demonstration passwords
make that risk greater. Secure credential distribution and supervised initial
enrollment are real-deployment concerns; they are not fabricated by this code.
Use synthetic accounts for demonstration, never claim this meets institutional
identity-proofing requirements.

No faculty approval is needed for each ordinary device operation. Face correction
and identity recovery remain external and unimplemented. Face deletion is absent;
existing, missing/inactive, invalidated-history and second enrollments cannot be
unlocked by the app. Legacy templates including DEMO001 receive no new provenance.
Do not clear their templates, seed attestations for them as a shortcut or relabel
old completed biometric sessions.

## Configuration and boundaries

`FYP_ACCOUNT_BOUND_ENROLLMENT=false` is the default, independent of DEMO_MODE.
An explicitly configured, private disposable FYP demonstration backend may set
it true. The guarded production launcher does not enable this policy from the
environment; its enrollment revision privileges remain SELECT-only. No production
configuration, database grants or environment file was changed here.

When enabled:

- Public `/register` is denied even if DEMO_MODE is also true. Group self-assignment
  is disabled. School roster attestation has no HTTP writer.
- `/register-face` uses only the bearer session's student ID, locks/reloads the
  student and authentication session, checks expiry/account status and school
  attestation, and rejects unexpected multipart fields. A client student_id or
  assurance_level is rejected with 422, including on preview requests.
- The partner face detector/encoder/encryption remain unchanged. No positioning
  preview creates a revision or template. After actual first capture, template,
  consent, revision and audit commit in one transaction. Session expiry after
  slow inference or a storage error rolls everything back.
- First enrollment creates `provenance=account_bound_fyp`,
  `assurance_level=ACCOUNT_BOUND_FYP`, a random revision ID, exact encrypted-template
  SHA-256, school provisioning reference and enrollment timestamp.
- It does **not** issue device activation approval. A new, separately bound device
  face/liveness run is still required after candidate-key possession.
- The local device provider accepts that revision only while this explicit policy
  is enabled and the exact template/roster/revision remain valid. External verified
  revisions instead require INSTITUTION_VERIFIED and real external evidence.
- Raw B3 sessions remain COMPLETED_UNTRUSTED. Fresh qualifying completion produces
  a separate operation-specific, single-use server authorization. The existing
  fresh P-256 activation challenge/signature and atomic transaction remain required.

Existing REST routes and successful enrollment response fields are unchanged.
Enrollment errors are 401 for missing/expired sessions, 403 for an unattested
account, 409 for locked/already enrolled history, 422 for injected fields, and
503 for unavailable provenance storage. Device authorization retains its existing
binding/expiry/replay/signature errors. The word `trusted` in the legacy internal
provider interface means eligible under the configured assurance policy; it does
not promote ACCOUNT_BOUND_FYP to institutional identity assurance.

## Schema, migration and permissions

Five additive tables are managed by `migrate_device_management.py`:

| Table | Purpose |
|---|---|
| school_provisioned_accounts | Student FK/PK, school provisioning reference and timestamp; offline operator writes only |
| device_enrollment_revisions | Student, encrypted-template hash, provenance, explicit assurance_level, evidence/timestamps and unique current revision |
| device_enrollment_observations | Revision and exact operation binding captured before scanning |
| device_biometric_authorizations | Separate result/grant IDs, expiry and atomic single-use consumption |
| device_trust_events | Enrollment, observation, issuance and consumption audit without images/tokens |

Conservative production runtime grants include SELECT on school attestations and
revisions. The isolated FYP actor additionally needs INSERT on revisions; it must
not have UPDATE/DELETE there, or write school attestations. Existing narrow student
biometric-column UPDATE privileges suffice. The school provisioning operator owns
student/roster INSERT; it does not run the mobile/API backend. No account/role
creation or provisioning endpoint is exposed to students.

The migration accepts only a loopback, non-3306, specifically named restored
database, dedicated disposable data directory and verified backup/baseline
evidence. It never seeds provenance, mutates existing registrations/templates or
widens production privileges. Existing malformed/older management tables fail
validation rather than being dropped/recreated; do not apply an ad-hoc overwrite.

```powershell
.\backend\venv\Scripts\python.exe -B backend\migrate_device_management.py `
  --profile '<private-isolated-profile.json>' --evidence '<verified-restore-evidence.json>'
```

See [profile/evidence fields](SELF_SERVICE_DEVICE_MANAGEMENT.md). No production
migration was run. The restored-copy acceptance runner below validates the actual
additive migration, original row hashes, idempotent rerun and MySQL constraints.

## Reproducible isolated supervisor demonstration

From `C:\FYP\FYP-Biometric-Attendance-System`:

```powershell
# Fast isolated HTTP/crypto tests; no real inference or external database access.
.\backend\venv\Scripts\python.exe -B -m unittest discover `
  -s backend\tests -p test_account_bound_enrollment.py -v

# MariaDB 10.4.27 restore, real transactions, restricted runtime actor and restarts.
.\backend\venv\Scripts\python.exe -B backend\tests\run_account_bound_mariadb.py
```

The second command requires the existing verified backup and compatible disposable
binaries referenced in the runner. It reserves only port 3321, creates a new private
directory beneath `C:\FYP\DB-DeviceManagement`, initializes clean system tables,
and restores the verified dump into a uniquely named schema. No production process
or account is queried. A Python network guard blocks existing DB ports 3306–3320.
All processes use hidden console creation; shutdown is graceful and bounded.

The preserved restored schema is used only for migration and comparison. HTTP
writes use separate fresh synthetic schemas and a restricted runtime account;
that account cannot read the restored real-data schema. Deterministic biometric
inputs and disposable software signing keys are **test fixtures**, not real camera
or Android Keystore evidence. The actual login, enrollment, local provider, device
REST endpoints, cryptographic protocol and database transactions are exercised.

Demonstrate in order:

1. Pre-create a synthetic school account and roster attestation in the offline
   fixture; log in with its assigned test credential.
2. Submit its first face through `/register-face`; show the saved assurance and
   revision are ACCOUNT_BOUND_FYP. Try enrollment again and show rejection.
3. Prove Slot 2 candidate key possession; complete fresh face and three accepted
   liveness frames. Automatic readiness/challenge/signing must end in two ACTIVE
   devices. An untrusted legacy template must remain blocked instead.
4. Replace disposable Slot 1 and Slot 2 in separate scenarios. Show old-key
   rejection, new-key verification and unchanged other-slot data.
5. Show wrong face/liveness, forged signature, replay, injected student ID and
   unauthenticated enrollment rejections. Confirm zero attendance writes.
6. Observe concurrency and restart results in the private REPORT.json. Do not
   display client.ini, bootstrap secrets, tokens, biometric values or private logs
   containing credentials. The runner starts no web server or tunnel and stops
   its disposable MariaDB before returning.

## Physical-device tests still required

Use only a separately prepared private demo backend/database, newly provisioned
synthetic students and spare/test installations. Do not alter Samsung's real
account, binding, app data or key; do not re-enroll a legacy face.

1. Enable the explicit FYP policy only on that backend and provision a NEW synthetic
   school account/roster using an offline operator. Set an assigned test password;
   keep public registration disabled. Choose the intended private API base URL.
2. Log in and enroll the face once using the real camera. Confirm the server revision
   says ACCOUNT_BOUND_FYP, and no edit-ID, delete-face or re-enrollment route works.
3. Register disposable Slot 1, then prepare Slot 2 on a different installation with
   its own retained Keystore key. Complete real face/liveness; verify automatic
   activation and a refreshed 2/2 ACTIVE list. Restart apps and backend; verify both
   keys still work independently.
4. Use a third spare installation/key for each replacement. Verify only the target
   key is revoked, failures preserve old registration, and the other slot still
   verifies. Check expiry, interrupted response/retry and session-change behavior.
5. Test attendance separately on an explicitly authorized private-LAN CIDR. Device
   management creates no attendance; final attendance still requires fresh device,
   actual-source network and biometric authorization. Do not seed production policy.

These manual tests were not performed by the automated fixtures. Fixed credentials
and account-bound initial enrollment remain demonstration limitations, even after
physical tests succeed.

## Final acceptance results

| Requirement | Result |
|---|---|
| First enrollment | WORKING in isolated HTTP and MariaDB tests |
| Slot 2 | WORKING under the explicit account-bound policy in isolated tests |
| Slot 1 / Slot 2 replacement | WORKING in isolated tests; old key rejected and other slot preserved |
| MariaDB integration | PASS: 11 scenarios using the actual local provider and restricted actor |
| Concurrent first enrollments | PASS: one 200, one 409; one permanent revision |
| Conflicting replacement candidates | PASS: one 201, one 409 |
| Concurrent activation confirmations | PASS: one 200, one 409; one atomic handover |
| Runtime privilege denials | PASS: 6 checks with expected permission errors |
| Graceful restarts | PASS: 3; ACTIVE rows, consumed grant, account-bound template/revision and zero synthetic attendance durable |
| Integrity | PASS: 877 restored/synthetic/system tables checked per pass; no corruption/crash markers |
| Preservation | PASS: all 26 restored original table row hashes matched, including six attendance rows, Samsung registration and encrypted template |
| Backend regression | PASS: 238 passed, 10 opt-in/live tests skipped (248 discovered) |
| Flutter regression | PASS: 183 passed, 1 skipped |
| Flutter analysis | PASS: no issues |
| Physical mobile testing | Outstanding; no real app/key/binding/template was changed |
| Supervisor demonstration | READY for the isolated protocol/database demo; PARTIAL for a physical-camera/Keystore demonstration |

Final private MariaDB evidence:
`C:\FYP\DB-DeviceManagement\account-bound-20261106-013909-a49723\REPORT.json`.
The run lasted 92.7 seconds and its server is stopped. A first attempt had a
Windows internal-socket guard issue, and an additional fault-injection test initially
expected an exception instead of the existing safe 503 response; both test-runner
issues were corrected before the accepted final runs. No production repair,
query, migration, real trust promotion or attendance write was performed.

Local regression evidence is in ignored `.work/account-bound-backend-accepted.log`,
`.work/backend-validation.json`, `.work/account-bound-flutter.json`,
`.work/account-bound-mariadb-release.log` and `.work/account-bound-preservation.json`.
The expected IntegrityError diagnostic in the acceptance log is deliberate
storage-failure injection; rollback and safe HTTP 503 are verified.

Files added for this policy: `modules/biometrics/enrollment_policy.py`,
`tests/test_account_bound_enrollment.py`, `tests/run_account_bound_mariadb.py` and
this guide. Existing school/provenance models, local device provider, Settings,
AppContext, account signup restrictions and guarded runtime grant inventory were
extended. The partner service/router changed only enrollment authorization,
session revalidation and atomic provenance hooks. Flutter completion guidance
and its test now explicitly distinguish account assurance from institutional
identity. README, API/ownership/provider documentation and generated OpenAPI were
reviewed/updated. Previous device-management work remains uncommitted and intact.

No commit, push, reset, merge, production configuration change, mobile install,
app-data clearing, key regeneration or Cloudflare operation was performed.
