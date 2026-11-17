"""Explicit offline LOCAL FYP account verification, never an HTTP trust API.

Records UNVERIFIED demo provenance, NOT a device grant. A new operation/scan
afterward must obtain the ordinary short-lived single-use authorization.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import subprocess

from sqlalchemy import select
from sqlalchemy.orm import Session

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
        template_hash=template_hash, provenance='account_bound_fyp', assurance_level='UNVERIFIED', verified_at=now)
    revision.evidence_reference = local_demo.account_evidence(db.info[local_demo.CREDENTIAL], revision, scan_id)
    db.add(revision)
    db.add(DeviceTrustEvent(student_id=student_id, action='local_account_verify',
        code='LOCAL_FYP_ACCOUNT_VERIFIED_UNVERIFIED', revision_id=revision.revision_id,
        authorization_id=scan_id, occurred_at=now))
    db.flush()
    return revision.revision_id


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--student', required=True)
    parser.add_argument('--scan', required=True)
    parser.add_argument('--confirm', required=True)
    parser.add_argument('--backup-dir', required=True, type=Path)
    args = parser.parse_args(argv)
    engine = None
    try:
        require(args.confirm == 'LOCAL-FYP-UNVERIFIED', 'Explicit UNVERIFIED local-test attestation required.')
        import original_fyp
        import httpx
        from config import local_now
        from reset_demo_slot2 import packed
        settings = original_fyp.settings()
        require(settings.demo_mode and local_demo.account_profile(original_fyp.PRIVATE), 'Local test profile is OFF.')
        pinned = original_fyp.probe()
        key = (original_fyp.PRIVATE / 'local-demo-slot2.key').read_bytes()
        require(len(key) == 32, 'Private operator credential invalid.')
        with httpx.Client(timeout=4, trust_env=False) as client:
            status = client.get('http://127.0.0.1:8000/local-fyp/demo-slot2')
            require(status.status_code == 200 and status.json().get('device_management_enabled') is True
                    and status.json().get('credential_sha256') == hashlib.sha256(key).hexdigest(),
                    'Matching live local account profile is required.')
        require(args.backup_dir.is_absolute() and not args.backup_dir.exists(), 'New private backup directory required.')
        args.backup_dir.mkdir(parents=False)
        owner = subprocess.check_output(['whoami'], text=True).strip()
        subprocess.run(['icacls', str(args.backup_dir), '/inheritance:r', '/grant:r',
                        owner + ':(OI)(CI)F', 'SYSTEM:(OI)(CI)F'], capture_output=True, check=True, timeout=10)
        engine = original_fyp.bounded_engine(settings)
        info = {local_demo.CREDENTIAL: key, local_demo.ACCOUNT_POLICY: True}
        with Session(engine, info=info) as db, db.begin():
            require(original_fyp.identity(db.connection(), settings) == pinned, 'Original database identity changed.')
            # Same student lock as normal device operations; snapshot before any revision write.
            student = db.scalar(select(Student).where(Student.student_id == args.student).with_for_update())
            require(student is not None, 'Student not found.')
            rows = db.scalars(select(EnrollmentRevision).where(EnrollmentRevision.student_id == args.student)).all()
            backup = packed({'purpose': 'EXPLICIT_LOCAL_ACCOUNT_SETUP', 'student': args.student,
                'scan': args.scan, 'revisions': [{c.name: getattr(row, c.name) for c in EnrollmentRevision.__table__.columns} for row in rows]})
            with (args.backup_dir / 'prior-revisions.json').open('xb') as stream:
                stream.write(backup); stream.flush(); os.fsync(stream.fileno())
            digest = hashlib.sha256(backup).hexdigest()
            require(hashlib.sha256((args.backup_dir / 'prior-revisions.json').read_bytes()).hexdigest() == digest, 'Backup verification failed.')
            (args.backup_dir / 'manifest.json').write_text(json.dumps({'sha256': digest, 'bytes': len(backup)}))
            revision = record_account(db, args.student, args.scan, local_now(settings))
        print(json.dumps({'result': 'LOCAL_FYP_ACCOUNT_RECORDED_UNVERIFIED', 'student': args.student,
                          'revision': revision, 'backup': str(args.backup_dir), 'device_activated': False,
                          'next': 'Cancel the setup request; prepare a NEW request and genuine scan for device authorization.'}))
        return 0
    except Exception as error:
        print(json.dumps({'result': 'ACCOUNT_SETUP_NOT_COMPLETED', 'reason': str(error) if isinstance(error, AccountVerificationRejected) else type(error).__name__, 'no_automatic_retry': True}))
        return 1
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == '__main__':
    raise SystemExit(main())
