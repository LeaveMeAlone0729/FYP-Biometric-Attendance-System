"""Local operator handoff for witnessed institutional identity re-verification."""
import argparse
from datetime import timedelta
import hashlib
import json
from pathlib import Path
import re
import secrets

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from sqlalchemy import select
from sqlalchemy.orm import Session

from app_time import iso_time, local_now
from models import Student
from modules.devices.biometric_models import DeviceBiometricEvent, DeviceBiometricSession
from modules.devices.management_models import DeviceTrustEvent, EnrollmentRevision
from modules.devices.pending_models import DeviceEnrollmentEvent, PendingDeviceRegistration
from modules.devices import local_demo
from original_fyp import PRIVATE, backend_ready, bounded_engine, identity, private_directory, probe, settings


MAX_EVIDENCE_AGE = timedelta(minutes=10)
VERIFIER_KEY = PRIVATE / 'institution-enrollment-verifier.pem'
ATTESTATION = (
    'I am an authorized institutional identity verifier. I checked the person against '
    'the institution identity record for this account and personally witnessed this '
    'live face and liveness scan on the candidate device. I approve this existing '
    'enrollment template for this verified identity and retained the case evidence.'
)


class VerificationRejected(ValueError):
    pass


def supervised_evidence(db, student_id, scan_id, reference, now, time_settings):
    """Read a completed scan and lock the student against enrollment changes."""
    if (not isinstance(student_id, str) or not re.fullmatch(r'[A-Z0-9]{1,11}', student_id)
            or not isinstance(scan_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', scan_id)
            or not isinstance(reference, str) or not re.fullmatch(r'[A-Za-z0-9._/-]{1,80}', reference)):
        raise VerificationRejected('Use the student ID, exact scan reference, and an opaque institutional case ID.')
    student = db.scalar(select(Student).where(Student.student_id == student_id).with_for_update())
    if student is None or student.account_status != 'active' or student.biometric_status != 'active' or not student.face_encoding:
        raise VerificationRejected('An active student and existing face enrollment are required.')
    if db.scalar(select(EnrollmentRevision.revision_id).where(
            EnrollmentRevision.student_id == student_id).limit(1)) is not None:
        raise VerificationRejected('Enrollment history already exists. Refer the case to institutional recovery.')

    scan = db.get(DeviceBiometricSession, scan_id)
    template_hash = hashlib.sha256(student.face_encoding.encode()).hexdigest()
    if (scan is None or scan.approval_id != scan_id or scan.student_id != student_id
            or scan.operation != 'enroll_second_device'
            or scan.slot_number != 2 or scan.stage != 'COMPLETED_UNTRUSTED' or scan.valid_frames != 3
            or scan.template_binding != template_hash or scan.completed_at is None
            or not scan.created_at <= scan.completed_at < scan.expires_at
            or not scan.completed_at <= now < scan.completed_at + MAX_EVIDENCE_AGE):
        raise VerificationRejected('A fresh completed Slot 2 scan for this exact enrollment is required.')

    pending = db.get(PendingDeviceRegistration, scan.pending_registration_id)
    if (pending is None or pending.student_id != student_id or pending.operation != scan.operation
            or pending.slot_number != scan.slot_number or pending.auth_token_hash != scan.auth_token_hash
            or pending.candidate_device_id != scan.candidate_device_id
            or pending.public_key_fingerprint != scan.public_key_fingerprint
            or pending.status not in ('KEY_PROVEN', 'EXPIRED') or pending.consumed_at is not None
            or pending.key_proven_at is None or not pending.key_proven_at <= scan.created_at
            or scan.completed_at >= pending.expires_at):
        raise VerificationRejected('The scan is missing its original candidate-key binding.')
    if db.scalar(select(DeviceBiometricEvent.event_id).where(
            DeviceBiometricEvent.approval_id == scan_id, DeviceBiometricEvent.student_id == student_id,
            DeviceBiometricEvent.action == 'complete', DeviceBiometricEvent.result == 'PASS',
            DeviceBiometricEvent.code == 'BIOMETRICS_COMPLETED_UNTRUSTED').limit(1)) is None:
        raise VerificationRejected('The server completion event is missing.')

    return {
        'purpose': 'fyp-supervised-enrollment-v1',
        'attestation': ATTESTATION,
        'student_id': student_id,
        'scan_id': scan_id,
        'case_reference': reference,
        'template_sha256': template_hash,
        'candidate_key_fingerprint': scan.public_key_fingerprint,
        'completed_at': iso_time(scan.completed_at, time_settings),
        'expires_at': iso_time(scan.completed_at + MAX_EVIDENCE_AGE, time_settings),
    }


def encode_evidence(evidence):
    return (json.dumps(evidence, indent=2, sort_keys=True) + '\n').encode('utf-8')


def record_verified_enrollment(db, payload, signature, verifier, now, time_settings):
    """Record a new revision after checking a trusted verifier's exact statement."""
    try:
        verifier.verify(signature, payload)
    except InvalidSignature:
        raise VerificationRejected('The attestation signature did not match the pinned institutional verifier.') from None
    evidence = json.loads(payload)
    if not isinstance(evidence, dict):
        raise VerificationRejected('Invalid signed attestation.')
    expected = supervised_evidence(db, evidence.get('student_id'), evidence.get('scan_id'),
                                   evidence.get('case_reference'), now, time_settings)
    if payload != encode_evidence(expected):
        raise VerificationRejected('The signed attestation differs from the current server evidence.')

    signer = hashlib.sha256(verifier.public_bytes_raw()).hexdigest()
    revision = EnrollmentRevision(
        revision_id=secrets.token_urlsafe(32), student_id=evidence['student_id'],
        template_hash=evidence['template_sha256'], provenance='external_verified',
        assurance_level='INSTITUTION_VERIFIED', verified_at=now,
        evidence_reference=f"{evidence['case_reference']}|scan={evidence['scan_id']}|signer={signer}",
    )
    db.add(revision)
    db.add(DeviceTrustEvent(student_id=revision.student_id, action='identity_reverification',
        code='INSTITUTION_REVERIFICATION_RECORDED', revision_id=revision.revision_id, occurred_at=now))
    db.flush()
    return revision.revision_id


def record_local_demo(db, scan_id, now, time_settings):
    student_id = local_demo.DEMO_STUDENT
    if not local_demo.enabled(db, student_id):
        raise VerificationRejected('Explicit local demo mode and its operator credential are required.')
    evidence = supervised_evidence(db, student_id, scan_id, 'LOCAL-FYP-DEMO', now, time_settings)
    scan = db.get(DeviceBiometricSession, scan_id)
    if not scan.candidate_device_id.startswith(local_demo.PREFIX):
        raise VerificationRejected('Start a fresh tablet request in local demo mode before collecting evidence.')
    if db.scalar(select(DeviceEnrollmentEvent.event_id).where(
            DeviceEnrollmentEvent.pending_registration_id == scan.pending_registration_id,
            DeviceEnrollmentEvent.student_id == student_id,
            DeviceEnrollmentEvent.action == 'proof', DeviceEnrollmentEvent.result == 'PASS',
            DeviceEnrollmentEvent.code == 'CANDIDATE_KEY_PROVEN',
            DeviceEnrollmentEvent.occurred_at <= scan.created_at).limit(1)) is None:
        raise VerificationRejected('The server device-key proof event is missing.')
    revision = EnrollmentRevision(
        revision_id=local_demo.PREFIX + secrets.token_urlsafe(32), student_id=student_id,
        template_hash=evidence['template_sha256'], provenance='account_bound_fyp',
        assurance_level='UNVERIFIED', verified_at=now,
    )
    revision.evidence_reference = local_demo.evidence_reference(
        db.info[local_demo.CREDENTIAL], revision, evidence['candidate_key_fingerprint'], scan_id)
    db.add(revision)
    db.add(DeviceTrustEvent(student_id=student_id, action='local_demo_verify',
        code='LOCAL_FYP_DEMO_ENROLLMENT_VERIFIED', revision_id=revision.revision_id, occurred_at=now))
    db.flush()
    return revision.revision_id


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    prepare = commands.add_parser('prepare')
    prepare.add_argument('--student', required=True)
    prepare.add_argument('--scan', required=True)
    prepare.add_argument('--case', required=True)
    prepare.add_argument('--out', required=True, type=Path)
    record = commands.add_parser('record')
    record.add_argument('--evidence', required=True, type=Path)
    record.add_argument('--signature', required=True, type=Path)
    commands.add_parser('init-demo')
    demo = commands.add_parser('record-demo')
    demo.add_argument('--scan', required=True)
    args = parser.parse_args(argv)
    engine = None
    try:
        if args.command == 'record':
            if not VERIFIER_KEY.is_file():
                raise VerificationRejected('The authorized institutional verifier public key is not provisioned.')
            verifier = serialization.load_pem_public_key(VERIFIER_KEY.read_bytes())
            if not isinstance(verifier, Ed25519PublicKey):
                raise VerificationRejected('The pinned verifier key must be an Ed25519 public key.')
            if args.evidence.stat().st_size > 4096 or args.signature.stat().st_size != 64:
                raise VerificationRejected('Expected the issued JSON and a raw 64-byte Ed25519 signature.')
            payload, signature = args.evidence.read_bytes(), args.signature.read_bytes()

        value = settings()
        pinned = probe()
        session_info = {}
        if args.command in ('init-demo', 'record-demo'):
            if not value.demo_mode:
                raise VerificationRejected('The original environment must be configured for FYP demo testing.')
            key_path = PRIVATE / 'local-demo-slot2.key'
            if args.command == 'init-demo':
                private_directory()
                if not key_path.exists():
                    with key_path.open('xb') as output:
                        output.write(secrets.token_bytes(32))
                if len(key_path.read_bytes()) != 32:
                    raise VerificationRejected('The private local demo credential is invalid.')
                print('Local demo operator credential is ready.')
                return 0
            import httpx
            key = key_path.read_bytes()
            backend_ready()
            with httpx.Client(timeout=4, trust_env=False) as client:
                status = client.get('http://127.0.0.1:8000/local-fyp/demo-slot2')
            if status.status_code != 200 or status.json().get('credential_sha256') != hashlib.sha256(key).hexdigest():
                raise VerificationRejected('The original backend is not serving the configured local demo profile.')
            session_info[local_demo.CREDENTIAL] = key
        engine = bounded_engine(value)
        with Session(engine, info=session_info) as db, db.begin():
            if identity(db.connection(), value) != pinned:
                raise VerificationRejected('Original database identity changed.')
            now = local_now(value).replace(microsecond=0)
            if args.command == 'prepare':
                evidence = supervised_evidence(db, args.student, args.scan, args.case, now, value)
                with args.out.open('xb') as output:
                    output.write(encode_evidence(evidence))
                message = 'Evidence prepared for institutional signature.'
            elif args.command == 'record-demo':
                record_local_demo(db, args.scan, now, value)
                message = 'LOCAL FYP DEMO evidence recorded. Start a fresh Slot 2 request and scan.'
            else:
                record_verified_enrollment(db, payload, signature, verifier, now, value)
                message = 'Verified enrollment recorded. Start a fresh Slot 2 request and scan.'
        print(message)
        return 0
    except VerificationRejected as error:
        print(str(error))
        return 1
    except Exception as error:
        print(f'Identity handoff failed ({type(error).__name__}). Check original database readiness and evidence files.')
        return 1
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == '__main__':
    raise SystemExit(main())
