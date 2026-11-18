> Historical self-service implementation evidence. For the current reusable BOTH-slot workflow and the explicit LOCAL FYP / UNVERIFIED legacy-account policy, use [Reusable device replacement](REUSABLE_DEVICE_REPLACEMENT.md). No historical or self-enrolled template is silently promoted to institutional assurance.

# Self-service Slot 2 and device replacement

The [ACCOUNT_BOUND_FYP policy](FYP_ACCOUNT_BOUND_ENROLLMENT.md) defines first-enrollment assurance. Device activation still requires the fresh
proof sequence below.

## Policy and result

Students cannot remove/change their face in the app. Faculty identity recovery
and face replacement remain external and are not implemented here. Faculty
approval is **not requested for each ordinary device operation**.

The missing partner trusted_device_provider dependency is replaced by the
built-in LocalDeviceApprovalProvider. It automatically authorizes an eligible
operation after authenticated login, candidate-key possession and fresh
face/liveness against a previously verified enrollment revision. It does not
establish the identity of an initially enrolled face.

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
is not enabled by normal app composition. Do not copy synthetic fixtures
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

## Schema maintenance

Current tables are defined by `backend/application_schema.py`. Shared feature
schema helpers remain in `backend/modules/devices/`; old standalone migration
launchers and acceptance runners have been removed. Startup only validates the
schema. Any existing-database upgrade needs a verified backup, matching encryption
key and reviewed schema plan. Never seed enrollment provenance to make an
unverified legacy face eligible.
