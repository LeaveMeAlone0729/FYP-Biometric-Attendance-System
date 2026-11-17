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

## Schema and permissions

Enrollment uses `school_provisioned_accounts`, `device_enrollment_revisions`,
`device_enrollment_observations`, `device_biometric_authorizations` and
`device_trust_events`. The shared schema implementation remains in
`backend/modules/devices/management_migration.py`; current table inventory is
defined by `backend/application_schema.py`.

The school operator owns account/roster provisioning. Conservative production
runtime access to attestations/revisions is read-only. Explicit FYP enrollment
also needs revision INSERT, never permission to relabel or overwrite an existing
revision. No provisioning or trust-writing endpoint is exposed to students.

Existing schemas must be checked against a verified backup before any reviewed
upgrade. Startup does not run migrations, seed provenance or promote legacy faces.
See [device management](SELF_SERVICE_DEVICE_MANAGEMENT.md) and the
[provider contract](TRUSTED_BIOMETRIC_PROVIDER_CONTRACT.md).
