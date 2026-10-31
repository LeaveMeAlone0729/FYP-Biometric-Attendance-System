# Trusted biometric provider contract — partner integration

This is the exact server-side adapter contract for Slot 2 activation. Device REST
and Flutter activation are implemented. No partner algorithm/lifecycle source was
changed. The default remains UnavailableTrustedApprovalProvider. There is no mock,
client PASS flag, environment switch or development override in production.

## Entry point

The partner implements **backend/modules/biometrics/trusted_device_provider.py**:

```python
def create_device_approval_provider():
    return YourInstitutionalApprovalProvider()
```

No such partner file has been created by the device module. The device-owned
trusted_approval_provider() loads it when present and checks that all seven methods
below exist. Missing module/dependencies, entrypoint or methods fail closed with
APPROVAL_UNAVAILABLE (503). Existing deployment therefore cannot activate Slot 2.
The adapter must be stateless/thread-safe and use the provided SQLAlchemy session.

The authoritative Python definitions are in backend/modules/devices/approval_provider.py:

```python
current_template_revision(db, student_id: str, now: datetime) -> TrustedTemplateRevision | None
validate_template_trust(db, revision: TrustedTemplateRevision, now: datetime) -> None
invalidate_revision(db, student_id: str, revision_id: str, reason: str, now: datetime) -> None
find_fresh_approval(db, binding: ApprovalBinding, now: datetime) -> TrustedBiometricApproval | None
validate_fresh_result(db, approval: TrustedBiometricApproval, binding: ApprovalBinding,
                      revision: TrustedTemplateRevision, now: datetime) -> TrustedBiometricResult | None
validate_and_lock(db, approval_id: str, binding: ApprovalBinding, now: datetime) -> TrustedBiometricApproval | None
consume(db, approval: TrustedBiometricApproval, now: datetime) -> None
```

## Exact value schemas

These are server-side values, NEVER client-submitted authorization JSON. Actual
Python values are the frozen dataclasses; datetime fields are naive datetimes in
the existing Settings.timezone (Asia/Kuala_Lumpur), matching context.now()/DB dates.
REST timestamps use timezone-qualified ISO8601 through existing iso_time().

| Dataclass | Fields and types |
| --- | --- |
| ApprovalBinding | student_id: str; auth_token_hash: str; pending_registration_id: str; candidate_device_id: str; public_key_fingerprint: str; slot_number: int (=2); operation: str (=enroll_second_device) |
| TrustedTemplateRevision | revision_id: str; student_id: str; template_hash: str (SHA256 hex of the exact current encrypted students.face_encoding value); trusted: bool; invalidated_at: datetime or None |
| TrustedBiometricResult | result_id: str; binding: ApprovalBinding; trusted_template_revision_id: str; face_verified: bool; liveness_verified: bool; verified_at: datetime; expires_at: datetime; classification: str (=TRUSTED_SERVER_RESULT) |
| TrustedBiometricApproval | approval_id: str; binding: ApprovalBinding; trusted_template_revision_id: str; template_trusted: bool; result: str (=PASS); verified_at: datetime; expires_at: datetime; consumed_at: datetime or None; biometric_result_id: str (mandatory for activation) |

A successful grant must point to a separately persisted genuine trusted result,
not a B3 test ID. The device service rejects any biometric_result_id that exists
in device_biometric_sessions, even if an adapter tries to relabel it as trusted.
Names/model strings and client-reported hardware identifiers are not proof.

## Required storage and behavior

The partner owns storage/migrations for current template revisions, trusted
biometric results, single-use approvals, authorized recovery and audit. Table names
are not prescribed by the device adapter, but records must supply every field
above and support transactional row locking. Recommended ownership:
biometric_template_revisions, trusted_biometric_results, trusted_device_approvals,
biometric_recovery_approvals and immutable biometric audit events. Do not install
fixture tables from backend/tests/test_device_activation.py into production.

- current_template_revision selects and locks the CURRENT institutional revision
  for the authenticated student. Return None if no trusted provenance exists.
- validate_template_trust checks institution approval, active current template,
  revision/student/hash match, no invalidation and approved enrollment/recovery
  provenance. A student cannot establish their own institutional trust. Existing
  biometric_status=active, face matching or consent alone never establishes it.
- invalidate_revision is for authorized partner/admin lifecycle code only. There
  is no student device REST endpoint for it. Revoke eligibility of dependent
  unconsumed grants/results and audit the administrator/reason in the same
  transaction. Follow the same student-first locking order as device activation.
- find_fresh_approval finds a persistent genuine unconsumed grant for the ENTIRE
  exact binding. It must not synthesize one from B3 completion. Return None if no
  eligible grant exists; do not treat absence as success.
- validate_and_lock loads an authoritative grant scoped to the binding, with
  FOR UPDATE. No client values may instantiate a grant. The service independently
  checks exact binding, PASS, trusted revision, expiry, freshness and consumption.
- validate_fresh_result locks/validates the referenced genuine server result. Both
  face and liveness must have actually passed in an attendance-free trusted
  workflow using the institution-approved revision at verification time. Validate
  chronology against institutional approval/recovery and ensure no invalidation.
  Never copy/relabel old COMPLETED_UNTRUSTED flags, hashes, frames or audit PASS
  events into a new trusted result. Those test sessions are not authorization.
- verified_at must be identical between grant/result, not later than now and no
  older than 60 seconds. Result expiry must be after now and no later than
  verified_at+60 seconds; grant expiry must not exceed result expiry. A new grant
  timestamp must not refresh an old biometric result's freshness.
- consume rechecks and marks the exact persistent grant consumed once, under its
  lock. Any reuse, revision change, expiry or binding mismatch must reject. It
  must not commit, roll back the outer transaction, create a second DB connection,
  call attendance, or persist outside the caller's DB transaction.

Activation already holds student/auth/pending/device/challenge locks. Adapter
lookups must scope records to the student before mutation; lock grant/current
revision/result rows consistently. Invalidation/recovery must serialize with the
same student lock. Grant consumption and Slot 2 insert share one savepoint/outer
transaction, so failed insertion does not burn a grant or partially activate.
Unexpected adapter/DB failures must roll back the outer transaction.

## Trusted workflow integration still owned by the partner

Current camera endpoints remain B3 untrusted tests. Device completion automatically
asks readiness, but its PASS flags are not sent as authorization. The partner must
integrate issuance of a NEW genuine trusted result/grant from its trusted,
attendance-free biometric workflow under this exact pending/session/key binding.
Merely approving a template or implementing a lookup does not create a fresh
result. Historical B3 results cannot be upgraded after institutional approval.
Once that genuine grant exists, the finished device flow automatically finds it,
requests/signs a fresh activation nonce and completes registration. No additional
manual device-verification button is required. The provider entrypoint is the
server composition hook; a genuine issuer/capture integration is also required.

Enrollment/deletion/recovery security, legacy-untrusted handling (including
DEMO001), administrator authorization and trust invalidation remain mandatory
partner work. Do not approve every template on startup, automatically trust
existing rows, or create production fixtures to make activation pass.

## Error contract

Raise DeviceRegistrationError(status, code, safe_message), or return None for a
missing grant/revision/result where specified. Normal device envelopes are
{success:false, code, message}. No images/templates/tokens/signatures are logged.
APPROVAL_UNAVAILABLE=503; BIOMETRIC_TRUST_REQUIRED/APPROVAL_MISMATCH=403;
APPROVAL_EXPIRED=410; APPROVAL_USED=409; APPROVAL_REVISION_CHANGED=403.
The service adds its own nonce, candidate, capacity and signature checks.
