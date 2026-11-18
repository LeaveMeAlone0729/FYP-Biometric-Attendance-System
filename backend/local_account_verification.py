"""Explicit offline LOCAL FYP account verification, never an HTTP trust API.

Records UNVERIFIED demo provenance, NOT a device grant. A new operation/scan
afterward must obtain the ordinary short-lived single-use authorization.
"""
import hashlib
import re
import secrets

from sqlalchemy import select

from models import Student, AuthSession
from modules.devices import local_demo
from modules.devices.models import RegisteredDevice
from modules.devices.pending_models import PendingDeviceRegistration, DeviceEnrollmentEvent
from modules.devices.biometric_models import DeviceBiometricSession, DeviceBiometricEvent
from modules.devices.management_models import EnrollmentRevision, DeviceTrustEvent
from modules.devices.crypto import canonical_public_key


class AccountVerificationRejected(ValueError):
    pass


def require(ok, message):
    if not ok:
        raise AccountVerificationRejected(message)


def record_account(db, student_id, scan_id, now):
    require(local_demo.account_enabled(db), 'Explicit local account profile and operator credential required.')
    require(isinstance(student_id, str) and re.fullmatch(r'[A-Z0-9]{1,11}', student_id)
            and isinstance(scan_id, str) and re.fullmatch(r'[A-Za-z0-9_-]{1,64}', scan_id), 'Exact student/scan identifiers required.')
    student = db.scalar(select(Student).where(Student.student_id == student_id).with_for_update())
    require(student is not None and student.account_status == 'active'
            and student.biometric_status == 'active' and bool(student.face_encoding), 'An active account with existing enrollment is required.')
    scan = db.get(DeviceBiometricSession, scan_id, with_for_update=True, populate_existing=True)
    template_hash = hashlib.sha256(student.face_encoding.encode()).hexdigest()
    require(scan is not None and scan.student_id == student_id and scan.stage == 'COMPLETED_UNTRUSTED'
            and scan.valid_frames == 3 and scan.completed_at is not None
            and scan.created_at <= scan.completed_at <= now < scan.expires_at
            and scan.template_binding == template_hash and scan.candidate_device_id.startswith(local_demo.PREFIX),
            'A new, unexpired, genuine local-test face/liveness completion is required.')
    pending = db.get(PendingDeviceRegistration, scan.pending_registration_id, with_for_update=True, populate_existing=True)
    require(pending is not None and pending.student_id == student_id and pending.status == 'KEY_PROVEN'
            and pending.consumed_at is None and pending.expires_at > now and pending.key_proven_at is not None
            and pending.key_proven_at <= scan.created_at and pending.auth_token_hash == scan.auth_token_hash
            and pending.candidate_device_id == scan.candidate_device_id
            and pending.public_key_fingerprint == scan.public_key_fingerprint
            and pending.operation == scan.operation and pending.slot_number == scan.slot_number,
            'Fresh candidate/key/login/operation binding required.')
    _, fingerprint = canonical_public_key(pending.public_key_spki)
    require(fingerprint == pending.public_key_fingerprint, 'Candidate key binding changed.')
    require(db.scalar(select(RegisteredDevice.device_id).where(
        RegisteredDevice.public_key_fingerprint == fingerprint)) is None, 'Candidate key is already registered.')
    auth = db.get(AuthSession, scan.auth_token_hash, with_for_update=True, populate_existing=True)
    require(auth is not None and auth.student_id == student_id and auth.expires_at > now, 'Original authenticated login expired.')
    target = db.get(RegisteredDevice, pending.slot_one_device_id, with_for_update=True, populate_existing=True)
    require(target is not None and target.student_id == student_id and target.status == 'ACTIVE', 'Original ACTIVE target required.')
    require((pending.operation == 'replace_device' and pending.slot_number in (1, 2)
             and target.slot_number == pending.slot_number and target.public_key_fingerprint == pending.replaced_device_fingerprint)
            or (pending.operation == 'enroll_second_device' and pending.slot_number == 2 and target.slot_number == 1),
            'Target slot/operation changed.')
    require(db.scalar(select(DeviceEnrollmentEvent.event_id).where(
        DeviceEnrollmentEvent.pending_registration_id == pending.pending_registration_id,
        DeviceEnrollmentEvent.student_id == student_id, DeviceEnrollmentEvent.action == 'proof',
        DeviceEnrollmentEvent.result == 'PASS', DeviceEnrollmentEvent.code == 'CANDIDATE_KEY_PROVEN',
        DeviceEnrollmentEvent.occurred_at <= scan.created_at)) is not None, 'Server key-proof evidence missing.')
    require(db.scalar(select(DeviceBiometricEvent.event_id).where(
        DeviceBiometricEvent.approval_id == scan_id, DeviceBiometricEvent.student_id == student_id,
        DeviceBiometricEvent.action == 'complete', DeviceBiometricEvent.result == 'PASS',
        DeviceBiometricEvent.code == 'BIOMETRICS_COMPLETED_UNTRUSTED',
        DeviceBiometricEvent.occurred_at == scan.completed_at)) is not None, 'Server biometric completion evidence missing.')
    require(db.scalar(select(DeviceTrustEvent.event_id).where(
        DeviceTrustEvent.action == 'local_account_verify', DeviceTrustEvent.authorization_id == scan_id)) is None,
        'This setup scan was already used.')
    previous = db.scalar(select(EnrollmentRevision).where(
        EnrollmentRevision.student_id == student_id, EnrollmentRevision.invalidated_at.is_(None)).with_for_update())
    if previous is not None:
        require(previous.assurance_level == 'UNVERIFIED' and previous.template_hash == template_hash
                and not local_demo.verified_account(db, previous),
                'Eligible provenance already exists, or enrollment changed. No automatic revision replacement.')
        previous.invalidated_at = now
        db.flush()  # Release only the current-revision uniqueness key.
    revision = EnrollmentRevision(revision_id=local_demo.PREFIX + secrets.token_urlsafe(32), student_id=student_id,
        template_hash=template_hash, provenance='account_bound_fyp', assurance_level='UNVERIFIED',
        verified_at=now.replace(microsecond=0))
    revision.evidence_reference = local_demo.account_evidence(db.info[local_demo.CREDENTIAL], revision, scan_id)
    db.add(revision)
    db.add(DeviceTrustEvent(student_id=student_id, action='local_account_verify',
        code='LOCAL_FYP_ACCOUNT_VERIFIED_UNVERIFIED', revision_id=revision.revision_id,
        authorization_id=scan_id, occurred_at=now))
    db.flush()
    # MySQL DATETIME(0) can round fractional seconds. Sign a whole-second value
    # and verify the actual stored row before reporting setup success.
    db.refresh(revision)
    require(local_demo.verified_account(db, revision), 'Stored Local enrollment evidence did not validate; setup was rolled back.')
    return revision.revision_id



if __name__ == '__main__':
    import sys
    from local_enrollment import main
    raise SystemExit(main(['record', *sys.argv[1:]]))
