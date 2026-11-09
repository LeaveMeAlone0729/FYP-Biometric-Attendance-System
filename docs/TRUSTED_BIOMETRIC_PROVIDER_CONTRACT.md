# Device biometric authorization contract

Current confirmed FYP scope, 6 November 2026. See
[implementation, migration, tests and demo](SELF_SERVICE_DEVICE_MANAGEMENT.md).

## Composition and ownership

The device-owned trusted_approval_provider() now returns the built-in
LocalDeviceApprovalProvider from backend/modules/devices/management_approval.py.
There is no dependency on modules.biometrics.trusted_device_provider and no
faculty approval request for each Slot 2 or replacement operation. Existing
activation transaction checks and dataclass bindings remain mandatory.

The opt-in FYP policy establishes ACCOUNT_BOUND_FYP assurance during first face
enrollment for an offline school-provisioned account. This proves account binding,
not institutional identity. It is not INSTITUTION_VERIFIED. Legacy templates are
never backfilled. See [policy, tests and demo](FYP_ACCOUNT_BOUND_ENROLLMENT.md).
Face deletion/replacement, faculty approval and identity recovery remain outside
the app. No faculty approval is requested per ordinary device operation.

The original environment supports a separate [supervised identity verification
handoff](SUPERVISED_ENROLLMENT_VERIFICATION.md) for a legacy template with no
revision history. It records a signed institutional attestation and uses the
existing provider for subsequent fresh device authorization.

## Server-only interface

The seven-method interface remains for device service compatibility:

- current_template_revision: load/lock the current valid enrollment revision,
  check its exact encrypted-template hash and provenance; return None otherwise.
- validate_template_trust: ensure that same revision is still current/valid.
- invalidate_revision: rejected by this app with EXTERNAL_RECOVERY_REQUIRED;
  enrollment lifecycle administration remains external, with no public route.
- find_fresh_approval: find a fresh, unconsumed local server authorization for the
  entire exact operation binding. Reject unverified enrollment or absent fresh
  evidence. Never fabricate a grant during lookup.
- validate_and_lock: load the persistent authorization and validate its binding,
  revision, freshness and single-use state under lock.
- validate_fresh_result: validate the separate result, source observation and
  genuinely completed face/liveness session against that same revision/binding.
- consume: revalidate and mark consumed inside the caller's activation transaction.
  Never commit independently, call attendance or write through another connection.

## Bound values

Python definitions remain in backend/modules/devices/approval_provider.py.
Datetime fields use the existing configured local backend time; REST timestamps
are timezone-qualified ISO8601. These values are never client PASS submissions.

| Value | Required binding/data |
|---|---|
| ApprovalBinding | student_id, auth_token_hash, pending_registration_id, candidate_device_id, public_key_fingerprint, slot_number, operation, optional replaced_device_id and replaced_device_fingerprint |
| TrustedTemplateRevision | revision_id, student_id, exact encrypted-template SHA-256, trusted, invalidated_at |
| TrustedBiometricResult | separate result_id, exact binding, revision ID, genuinely accepted face/liveness, verified_at, expires_at, TRUSTED_SERVER_RESULT classification |
| TrustedBiometricApproval | separate approval_id, exact binding, revision ID, valid provenance, PASS, same verified_at, bounded expires_at, consumed_at and result_id |

For replacement, target ID/fingerprint must match the locked ACTIVE registration;
for second enrollment they are None and slot_number is 2. Model names and client
hardware identifiers are not identity proof. Candidate-key proof and final
activation signatures remain required regardless of biometric authorization.

## Issuance and storage

management_models.py adds school_provisioned_accounts, device_enrollment_revisions,
device_enrollment_observations, device_biometric_authorizations and
device_trust_events. Conservative production grants remain SELECT-only on
enrollment revisions. The explicitly isolated FYP demonstration actor additionally
needs INSERT on revisions, for the atomic first-enrollment path only. Neither
actor can modify/invalidate revisions or write school provisioning attestations.
Clients cannot write assurance/revision/identity fields.

At NEW biometric-session creation, capture an already valid revision and exact
binding. Only after fresh unchanged partner inference accepts the face and three
liveness frames can the completion hook issue a distinct local result and grant.
The grant expires within 60 seconds, and no later than biometric/pending/login
expiry. Its source session is unique. Grant/result timestamps cannot be refreshed
by reading status or requesting readiness. A later revision cannot qualify an old
scan. Template/revision changes, login changes, expiry and replay all fail closed.

Raw device_biometric_sessions remain COMPLETED_UNTRUSTED. Their ID and flags alone
remain unusable as authorization. The separate result_id may not be a raw B3 ID.
Activation independently validates the separate result, revision and all bindings.
Consumption and ACTIVE insertion/replacement share one transaction/savepoint;
failed insertion rolls back consumption and revocation.

external_verified records require INSTITUTION_VERIFIED assurance and an actual
external identity-verification handoff/evidence. No real identity verification
is claimed or seeded here. account_bound_fyp requires ACCOUNT_BOUND_FYP assurance,
the explicit startup policy and a matching school provisioning record. Disabling
the policy immediately prevents its use for device activation. synthetic_fixture is
restricted to explicitly marked in-memory SQLite test Sessions. MySQL, file-based
SQLite, ordinary runtime Sessions, DEMO_MODE, request fields and environment
variables cannot enable it. It is not a production enrollment bypass.

## REST behavior

The existing activation-readiness, activation-challenges, activate and
activation-status endpoints are unchanged. Flutter automatically follows readiness
with retained-key signing only after server eligibility. Raw/pending responses do
not authorize activation. Pending biometric_approval_status is now NOT_CHECKED.

- BIOMETRIC_TRUST_REQUIRED (403): initial enrollment provenance unverified.
- FRESH_BIOMETRIC_PROOF_REQUIRED (403): qualifying new face/liveness proof absent.
- APPROVAL_UNAVAILABLE (503): storage/migration unavailable, not missing faculty.
- APPROVAL_MISMATCH/APPROVAL_REVISION_CHANGED (403): binding/current revision changed.
- APPROVAL_EXPIRED (410), APPROVAL_USED (409): freshness or consumption failure.

No client-only result can activate a device. No attendance endpoint is used by
this workflow. Face replacement/recovery remains external; successful ordinary
device operations do not need a faculty approval interaction each time.
