from database_compat import shared_read
"""Local automatic approvals against pre-established enrollment provenance.

Never approves an enrollment. Synthetic provenance is accepted ONLY on an
in-memory SQLite connection explicitly tagged by an isolated test Session.
No HTTP input, environment variable or production profile enables that fixture.
"""
from dataclasses import asdict
from datetime import timedelta
import hashlib
import json
import secrets
from sqlalchemy import inspect, select
from models import Student, AuthSession
from .approval_provider import (ApprovalBinding, TrustedTemplateRevision,
    TrustedBiometricApproval, TrustedBiometricResult, validate_approval)
from .management_models import (SchoolProvisionedAccount, EnrollmentRevision, EnrollmentObservation,
    DeviceBiometricAuthorization, DeviceTrustEvent, MANAGEMENT_TABLES)
from .biometric_models import DeviceBiometricSession
from .pending_models import PendingDeviceRegistration
from .service import DeviceRegistrationError
from . import local_demo


def deny(code='BIOMETRIC_TRUST_REQUIRED', message='Enrollment identity provenance is not verified. Device management remains blocked; face recovery is outside this application.'):
    raise DeviceRegistrationError(403, code, message)


def binding_for(session, pending):
    return ApprovalBinding(session.student_id, session.auth_token_hash,
        session.pending_registration_id, session.candidate_device_id,
        session.public_key_fingerprint, session.slot_number, session.operation,
        pending.slot_one_device_id if session.operation == 'replace_device' else None,
        pending.replaced_device_fingerprint)


def encode(binding):
    return json.dumps(asdict(binding), sort_keys=True, separators=(',', ':'))


def available(db):
    return db is not None and all(inspect(db.connection()).has_table(t.name) for t in MANAGEMENT_TABLES)


class LocalDeviceApprovalProvider:
    def storage(self, db):
        if not available(db):
            raise DeviceRegistrationError(503, 'APPROVAL_UNAVAILABLE',
                'Device authorization storage is unavailable. Apply and validate the additive migration on an isolated restored copy first.')

    def _valid_revision(self, db, row, now):
        if row is None or row.invalidated_at is not None or row.verified_at > now or not row.evidence_reference:
            return False
        if row.revision_id.startswith(local_demo.PREFIX):
            if local_demo.verified_fingerprint(db, row) is None:
                return False
        elif row.provenance == 'synthetic_fixture':
            engine = db.get_bind()
            if not (engine.dialect.name == 'sqlite' and engine.url.database in (None, '', ':memory:')
                    and db.info.get('synthetic_enrollment_fixture') is True):
                return False
        elif row.provenance == 'account_bound_fyp':
            if db.info.get('fyp_account_bound_enrollment') is not True or row.assurance_level != 'ACCOUNT_BOUND_FYP':
                return False
            account = db.scalar(select(SchoolProvisionedAccount).where(
                SchoolProvisionedAccount.student_id == row.student_id
            ).with_for_update(read=shared_read(db)).execution_options(populate_existing=True))
            if (account is None or not account.provisioning_reference.strip()
                    or account.provisioned_at > row.verified_at
                    or row.evidence_reference != account.provisioning_reference):
                return False
        elif row.provenance != 'external_verified' or row.assurance_level != 'INSTITUTION_VERIFIED':
            return False
        student = db.get(Student, row.student_id)
        return bool(student and student.account_status == 'active' and student.biometric_status == 'active'
            and student.face_encoding and hashlib.sha256(student.face_encoding.encode()).hexdigest() == row.template_hash)

    def current_template_revision(self, db, student_id, now):
        self.storage(db)
        row = db.scalar(select(EnrollmentRevision).where(EnrollmentRevision.student_id == student_id,
            EnrollmentRevision.invalidated_at == None).with_for_update(read=shared_read(db)).execution_options(populate_existing=True))
        if not self._valid_revision(db, row, now):
            return None
        return TrustedTemplateRevision(row.revision_id, row.student_id, row.template_hash, True)

    def validate_template_trust(self, db, revision, now):
        current = self.current_template_revision(db, revision.student_id, now)
        if current != revision:
            deny()

    def invalidate_revision(self, *args, **kwargs):
        # No in-app faculty/recovery workflow. External lifecycle administration
        # owns revision invalidation; this interface cannot impersonate staff.
        deny('EXTERNAL_RECOVERY_REQUIRED', 'Enrollment recovery and revision changes are outside this application.')

    def _row(self, db, identifier):
        return db.scalar(select(DeviceBiometricAuthorization).where(
            DeviceBiometricAuthorization.approval_id == identifier).with_for_update().execution_options(populate_existing=True))

    def validate_and_lock(self, db, approval_id, binding, now):
        self.storage(db)
        if not approval_id:
            deny()
        row = self._row(db, approval_id)
        if row is None:
            deny()
        revision = self.current_template_revision(db, binding.student_id, now)
        if revision is not None and not local_demo.permits_binding(
                db, db.get(EnrollmentRevision, revision.revision_id), binding):
            deny('APPROVAL_MISMATCH', 'The enrollment verification does not authorize this device key or operation.')
        approval = TrustedBiometricApproval(row.approval_id, ApprovalBinding(**json.loads(row.binding)),
            row.revision_id, bool(revision and revision.revision_id == row.revision_id),
            'PASS', row.verified_at, row.expires_at, row.consumed_at, row.result_id)
        return validate_approval(approval, approval_id, binding, now)

    def find_fresh_approval(self, db, binding, now):
        self.storage(db)
        if self.current_template_revision(db, binding.student_id, now) is None:
            if (local_demo.enabled(db, binding.student_id) and binding.candidate_device_id.startswith(local_demo.PREFIX)
                    and binding.operation == 'enroll_second_device' and binding.slot_number == 2):
                deny('LOCAL_DEMO_EVIDENCE_REQUIRED', 'LOCAL DEMO verification needs the local operator to record evidence from this fresh scan.')
            deny()
        row = db.scalar(select(DeviceBiometricAuthorization).where(
            DeviceBiometricAuthorization.binding == encode(binding),
            DeviceBiometricAuthorization.consumed_at == None,
            DeviceBiometricAuthorization.expires_at > now).order_by(
                DeviceBiometricAuthorization.verified_at.desc()).with_for_update())
        if row is None:
            deny('FRESH_BIOMETRIC_PROOF_REQUIRED', 'Complete a fresh face and liveness scan after enrollment provenance has been established.')
        return self.validate_and_lock(db, row.approval_id, binding, now)

    def validate_fresh_result(self, db, approval, binding, revision, now):
        row = self._row(db, approval.approval_id)
        if row is None or row.result_id != approval.biometric_result_id or row.binding != encode(binding):
            return None
        observation = db.get(EnrollmentObservation, row.source_session_id)
        session = db.get(DeviceBiometricSession, row.source_session_id)
        pending = db.get(PendingDeviceRegistration, session.pending_registration_id) if session else None
        if (observation is None or session is None or observation.binding != row.binding
                or observation.revision_id != revision.revision_id or row.revision_id != revision.revision_id
                or session.stage != 'COMPLETED_UNTRUSTED' or session.valid_frames != 3
                or session.completed_at != row.verified_at
                or session.template_binding != revision.template_hash or pending is None
                or binding_for(session, pending) != binding
                or observation.created_at > session.completed_at):
            return None
        return TrustedBiometricResult(row.result_id, binding, revision.revision_id,
            True, True, row.verified_at, row.expires_at)

    def consume(self, db, approval, now):
        self.validate_and_lock(db, approval.approval_id, approval.binding, now)
        row = self._row(db, approval.approval_id)
        row.consumed_at = now
        db.add(DeviceTrustEvent(student_id=approval.binding.student_id, action='consume',
            code='DEVICE_AUTHORIZATION_CONSUMED', revision_id=row.revision_id,
            authorization_id=row.approval_id, occurred_at=now))
        db.flush()


def capture_enrollment(db, student, session, pending, now):
    """Only called at new session creation, never status/readiness or old completion."""
    if not available(db):
        return
    provider = LocalDeviceApprovalProvider()
    revision = provider.current_template_revision(db, student.student_id, now)
    if revision is None:
        return
    binding = binding_for(session, pending)
    if not local_demo.permits_binding(db, db.get(EnrollmentRevision, revision.revision_id), binding):
        return
    db.add(EnrollmentObservation(session_id=session.approval_id, revision_id=revision.revision_id,
        binding=encode(binding), created_at=now))
    db.add(DeviceTrustEvent(student_id=student.student_id, action='capture',
        code='VERIFIED_ENROLLMENT_CAPTURED', revision_id=revision.revision_id, occurred_at=now))
    db.flush()


def issue_device_authorization(db, student, session, pending, now):
    """Called only after fresh unchanged partner inference accepted all frames."""
    if not available(db):
        return
    observation = db.get(EnrollmentObservation, session.approval_id)
    if observation is None:
        return
    provider = LocalDeviceApprovalProvider()
    revision = provider.current_template_revision(db, student.student_id, now)
    binding = binding_for(session, pending)
    auth = db.scalar(select(AuthSession).where(AuthSession.token_hash == session.auth_token_hash)
        .with_for_update().execution_options(populate_existing=True))
    if (revision is None or revision.revision_id != observation.revision_id
            or not local_demo.permits_binding(db, db.get(EnrollmentRevision, revision.revision_id), binding)
            or revision.template_hash != session.template_binding
            or observation.binding != encode(binding) or session.stage != 'COMPLETED_UNTRUSTED'
            or session.valid_frames != 3 or session.completed_at != now
            or pending.status != 'KEY_PROVEN' or pending.consumed_at is not None
            or auth is None or auth.student_id != student.student_id
            or min(session.expires_at, pending.expires_at, auth.expires_at) <= now):
        return
    # The unique source-session constraint prevents issuing a second grant for it.
    grant = DeviceBiometricAuthorization(approval_id=secrets.token_urlsafe(32),
        result_id=secrets.token_urlsafe(32), source_session_id=session.approval_id,
        revision_id=revision.revision_id, student_id=student.student_id, binding=encode(binding),
        verified_at=now, expires_at=min(now+timedelta(seconds=60), session.expires_at, pending.expires_at, auth.expires_at))
    db.add(grant)
    db.add(DeviceTrustEvent(student_id=student.student_id, action='issue',
        code='FRESH_DEVICE_AUTHORIZATION_ISSUED', revision_id=revision.revision_id,
        authorization_id=grant.approval_id, occurred_at=now))
    db.flush()
