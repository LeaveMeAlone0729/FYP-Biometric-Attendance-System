"""Explicit local-test assurance; legacy key scope and reusable account scope.

Neither scope is institution verification. Account scope needs its own profile
opt-in and witnessed server evidence; it never supplies an operation grant.
"""
import hashlib
import hmac
import json
import re

from sqlalchemy import select

from .management_models import EnrollmentRevision


DEMO_STUDENT = 'DEMO001'
PREFIX = 'local-demo-'
CREDENTIAL = 'local_demo_slot2_key'
ACCOUNT_POLICY = 'local_fyp_account_management'


def account_enabled(db):
    key = db.info.get(CREDENTIAL)
    return db.info.get(ACCOUNT_POLICY) is True and isinstance(key, bytes) and len(key) == 32


def account_profile(parent):
    """Private launcher opt-in, default OFF. Never read from HTTP or demo_mode alone."""
    path = parent / 'local-device-management.json'
    if not path.exists():
        return False
    data = json.loads(path.read_text(encoding='utf-8-sig'))
    if (set(data) != {'version', 'enabled'} or type(data['version']) is not int
            or data['version'] != 1 or type(data['enabled']) is not bool):
        raise ValueError('LOCAL_ACCOUNT_PROFILE_INVALID')
    return data['enabled']


def account_evidence(key, revision, scan_id):
    message = json.dumps(['LOCAL_FYP_ACCOUNT_V1', revision.revision_id, revision.student_id,
        revision.template_hash, revision.verified_at.replace(microsecond=0).isoformat(), scan_id], separators=(',', ':')).encode()
    signature = hmac.new(key, message, hashlib.sha256).hexdigest()
    return f'LOCAL_FYP_ACCOUNT|{scan_id}|{signature}'


def verified_account(db, revision):
    if (revision is None or not account_enabled(db) or not revision.revision_id.startswith(PREFIX)
            or revision.invalidated_at is not None or revision.provenance != 'account_bound_fyp'
            or revision.assurance_level != 'UNVERIFIED'):
        return False
    evidence = re.fullmatch(r'LOCAL_FYP_ACCOUNT\|([A-Za-z0-9_-]{1,64})\|[0-9a-f]{64}', revision.evidence_reference)
    if evidence is None or not hmac.compare_digest(
            account_evidence(db.info[CREDENTIAL], revision, evidence.group(1)), revision.evidence_reference):
        return False
    from models import Student
    student = db.get(Student, revision.student_id)
    return bool(student and student.account_status == 'active' and student.biometric_status == 'active'
                and student.face_encoding and hashlib.sha256(student.face_encoding.encode()).hexdigest() == revision.template_hash)


def local_candidate(db, student_id):
    """Mark test-origin candidates without granting them any authorization."""
    if not account_enabled(db):
        return False
    row = db.scalar(select(EnrollmentRevision).where(
        EnrollmentRevision.student_id == student_id, EnrollmentRevision.invalidated_at.is_(None)))
    return row is None or row.revision_id.startswith(PREFIX) or row.assurance_level == 'UNVERIFIED'


def enabled(db, student_id):
    key = db.info.get(CREDENTIAL)
    return student_id == DEMO_STUDENT and isinstance(key, bytes) and len(key) == 32


def evidence_reference(key, revision, fingerprint, scan_id):
    message = json.dumps([
        'LOCAL_FYP_DEMO_V1', revision.revision_id, revision.student_id,
        revision.template_hash, revision.verified_at.isoformat(), fingerprint, scan_id,
    ], separators=(',', ':')).encode()
    signature = hmac.new(key, message, hashlib.sha256).hexdigest()
    return f'LOCAL_FYP_DEMO|{fingerprint}|{scan_id}|{signature}'


def verified_fingerprint(db, revision):
    if (not revision.revision_id.startswith(PREFIX) or not enabled(db, revision.student_id)
            or revision.invalidated_at is not None or revision.provenance != 'account_bound_fyp'
            or revision.assurance_level != 'UNVERIFIED'):
        return None
    evidence = re.fullmatch(r'LOCAL_FYP_DEMO\|([0-9a-f]{64})\|([A-Za-z0-9_-]{1,64})\|[0-9a-f]{64}',
                            revision.evidence_reference)
    if evidence is None:
        return None
    fingerprint, scan_id = evidence.groups()
    expected = evidence_reference(db.info[CREDENTIAL], revision, fingerprint, scan_id)
    return fingerprint if hmac.compare_digest(expected, revision.evidence_reference) else None


def permits_binding(db, revision, binding):
    if revision.revision_id.startswith(PREFIX):
        if verified_account(db, revision):
            return (binding.student_id == revision.student_id and binding.candidate_device_id.startswith(PREFIX)
                    and ((binding.operation == 'enroll_second_device' and binding.slot_number == 2)
                         or (binding.operation == 'replace_device' and binding.slot_number in (1, 2)
                             and bool(binding.replaced_device_id) and bool(binding.replaced_device_fingerprint))))
        return (binding.candidate_device_id.startswith(PREFIX) and binding.operation == 'enroll_second_device'
                and binding.slot_number == 2 and binding.student_id == revision.student_id
                and verified_fingerprint(db, revision) == binding.public_key_fingerprint)
    return not binding.candidate_device_id.startswith(PREFIX)


def permits_device(db, device):
    if not device.device_id.startswith(PREFIX):
        return True
    revision = db.scalar(select(EnrollmentRevision).where(
        EnrollmentRevision.student_id == device.student_id, EnrollmentRevision.invalidated_at.is_(None)))
    if verified_account(db, revision):
        return device.slot_number in (1, 2)
    if device.slot_number != 2 or not enabled(db, device.student_id):
        return False
    return revision is not None and verified_fingerprint(db, revision) == device.public_key_fingerprint
