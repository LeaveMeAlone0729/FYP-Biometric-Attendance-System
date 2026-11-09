"""A local operator credential scopes demo trust to one student and tablet key."""
import hashlib
import hmac
import json
import re

from sqlalchemy import select

from .management_models import EnrollmentRevision


DEMO_STUDENT = 'DEMO001'
PREFIX = 'local-demo-'
CREDENTIAL = 'local_demo_slot2_key'


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
        return (binding.candidate_device_id.startswith(PREFIX) and binding.operation == 'enroll_second_device'
                and binding.slot_number == 2 and binding.student_id == revision.student_id
                and verified_fingerprint(db, revision) == binding.public_key_fingerprint)
    return not binding.candidate_device_id.startswith(PREFIX)


def permits_device(db, device):
    if not device.device_id.startswith(PREFIX):
        return True
    if device.slot_number != 2 or not enabled(db, device.student_id):
        return False
    revision = db.scalar(select(EnrollmentRevision).where(
        EnrollmentRevision.student_id == device.student_id, EnrollmentRevision.invalidated_at.is_(None)))
    return revision is not None and verified_fingerprint(db, revision) == device.public_key_fingerprint
