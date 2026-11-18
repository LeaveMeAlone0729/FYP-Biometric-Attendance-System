"""Reusable UNVERIFIED local-test anchors; no live records/real identity claims."""
from datetime import timedelta
import hashlib
import json
from pathlib import Path
import sys
from unittest.mock import patch

import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from local_account_verification import record_account, AccountVerificationRejected
from modules.devices import local_demo
from modules.devices.management_models import EnrollmentRevision, DeviceBiometricAuthorization, EnrollmentObservation
from modules.devices.biometric_models import DeviceBiometricSession
from models import Attendance, Student
import test_device_replacement as replacement
import test_device_biometrics as biometric
import test_reusable_replacement_policy as normal


@pytest.fixture(scope='module')
def password_hash():
    replacement.ReplacementTests.setUpClass()
    return replacement.ReplacementTests.password_hash


@pytest.fixture
def flow(password_hash):
    h = replacement.ReplacementTests()
    h.password_hash = password_hash
    h.setUp()
    # Generic DEVICE001, not the legacy hardcoded demo identity.
    info = {local_demo.CREDENTIAL: bytes(range(32)), local_demo.ACCOUNT_POLICY: True}
    h.f.sessions.configure(info=info)
    h.f.fixture.app.state.sessions.configure(info=info)
    try:
        yield h
    finally:
        h.tearDown()


def setup_scan(h, slot):
    pending = h.prepare(slot)
    assert pending['candidate_device_id'].startswith(local_demo.PREFIX)
    bio = biometric.DeviceBiometricTests()
    bio.f, bio.p, bio.pending = h.f, h.h.p, pending
    scan, _ = bio.complete()
    assert h.post('/activation-readiness', {}).json()['code'] == 'LOCAL_FYP_ACCOUNT_VERIFICATION_REQUIRED'
    return scan


def account_anchor(h, slot):
    scan = setup_scan(h, slot)
    with h.f.sessions.begin() as db:
        revision = record_account(db, 'DEVICE001', scan, h.f.fixture.now)
        assert db.get(EnrollmentRevision, revision).assurance_level == 'UNVERIFIED'
        assert local_demo.verified_account(db, db.get(EnrollmentRevision, revision))
        assert db.scalar(select(func.count()).select_from(DeviceBiometricAuthorization)) == 0
        assert db.get(EnrollmentObservation, scan) is None
    # Setting provenance must not retroactively authorize its setup scan.
    assert h.post('/activation-readiness', {}).json()['code'] == 'FRESH_BIOMETRIC_PROOF_REQUIRED'
    assert h.post('/cancel', {}).status_code == 200
    h.f.fixture.now += timedelta(seconds=1)
    return revision


@pytest.mark.parametrize('slot', [1, 2])
def test_both_slots_new_scan_grant_atomic_replacement_and_local_only_key(flow, slot):
    h = flow
    revision = account_anchor(h, slot)
    pending, approval, _, body = normal.ready(h, slot)
    assert pending['candidate_device_id'].startswith(local_demo.PREFIX)
    assert h.post('/activate', body).status_code == 200
    assert h.post('/activate', body).json()['code'] == 'ACTIVATION_REPLAYED'
    after = h.rows()
    old = h.h.binding.replaced_device_id
    assert after[old]['status'] == 'REVOKED'
    assert after[pending['candidate_device_id']]['status'] == 'ACTIVE'
    for key, row in h.before.items():
        if key != old:
            assert after[key] == row
    assert sum(row['status'] == 'ACTIVE' for row in after.values()) == 2
    assert h.f.issue(fingerprint=h.before[old]['public_key_fingerprint']).status_code == 403
    proof = h.f.issue(fingerprint=pending['public_key_fingerprint'])
    assert h.f.confirm(proof.json(), key=h.h.p.key).json()['result'] == 'PASS'
    with h.f.sessions() as db:
        assert db.get(DeviceBiometricAuthorization, approval['approval_id']).consumed_at is not None
        assert db.get(EnrollmentRevision, revision).assurance_level == 'UNVERIFIED'
        assert db.get(EnrollmentRevision, revision).evidence_reference.startswith('LOCAL_FYP_ACCOUNT|')
    h.f.sessions.configure(info={})
    h.f.fixture.app.state.sessions.configure(info={})
    assert h.f.issue(fingerprint=pending['public_key_fingerprint']).json()['code'] == 'LOCAL_DEMO_DEVICE_DISABLED'
    assert h.h.count(Attendance) == 0


@pytest.mark.parametrize('slot', [1, 2])
@pytest.mark.parametrize('failure', ['wrong_key', 'expired', 'wrong_login'])
def test_each_operation_rejects_wrong_candidate_expiry_and_login(flow, slot, failure):
    h = flow
    account_anchor(h, slot)
    _, approval, challenge, body = normal.ready(h, slot)
    headers = None
    if failure == 'wrong_key':
        body['signature'] = h.h.signature(challenge, ec.generate_private_key(ec.SECP256R1()))
    elif failure == 'expired':
        h.f.fixture.now += timedelta(seconds=61)
    else:
        headers = h.f.fixture.login('DEVICE001')
    response = h.post('/activate', body, headers=headers)
    assert response.status_code >= 400
    h.assert_unchanged()
    with h.f.sessions() as db:
        assert db.get(DeviceBiometricAuthorization, approval['approval_id']).consumed_at is None


@pytest.mark.parametrize('slot', [1, 2])
def test_failed_candidate_insert_rolls_back_new_local_grant_and_revocation(flow, slot):
    h = flow
    account_anchor(h, slot)
    pending, approval, _, body = normal.ready(h, slot)
    original = Session.flush
    from modules.devices.models import RegisteredDevice
    def fail(db, *a, **kw):
        if any(isinstance(r, RegisteredDevice) and r.device_id == pending['candidate_device_id'] for r in db.new):
            raise IntegrityError('synthetic insert failure', {}, Exception('test only'))
        return original(db, *a, **kw)
    with patch.object(Session, 'flush', fail):
        assert h.post('/activate', body).json()['code'] == 'ACTIVATION_CONFLICT'
    h.assert_unchanged()
    with h.f.sessions() as db:
        assert db.get(DeviceBiometricAuthorization, approval['approval_id']).consumed_at is None


def test_profile_default_off_and_malformed_config(tmp_path):
    assert local_demo.account_profile(tmp_path) is False
    path = tmp_path/'local-device-management.json'
    path.write_text(json.dumps({'version':1,'enabled':True}))
    assert local_demo.account_profile(tmp_path) is True
    path.write_text(json.dumps({'version':1,'enabled':'true'}))
    with pytest.raises(ValueError):
        local_demo.account_profile(tmp_path)


@pytest.mark.parametrize('bad', ['profile_off', 'credential_missing', 'wrong_student', 'expired_scan', 'missing_completion', 'wrong_target'])
def test_operator_requires_fresh_actual_bound_evidence(flow, bad):
    h = flow
    scan = setup_scan(h, 1)
    with h.f.sessions.begin() as db:
        if bad == 'profile_off':
            db.info[local_demo.ACCOUNT_POLICY] = False
        elif bad == 'credential_missing':
            db.info.pop(local_demo.CREDENTIAL)
        elif bad == 'expired_scan':
            h.f.fixture.now += timedelta(seconds=91)
        elif bad == 'missing_completion':
            from modules.devices.biometric_models import DeviceBiometricEvent
            db.query(DeviceBiometricEvent).filter_by(approval_id=scan, action='complete').delete()
        elif bad == 'wrong_target':
            from modules.devices.pending_models import PendingDeviceRegistration
            db.get(PendingDeviceRegistration, h.h.identifier).replaced_device_fingerprint = 'forged'
        with pytest.raises(AccountVerificationRejected):
            record_account(db, 'DEVICE002' if bad == 'wrong_student' else 'DEVICE001', scan, h.f.fixture.now)
        assert db.scalar(select(func.count()).select_from(EnrollmentRevision)) == 0
    h.assert_unchanged()


def test_tampered_or_unknown_account_evidence_never_qualifies(flow):
    h = flow
    revision = account_anchor(h, 2)
    with h.f.sessions.begin() as db:
        db.get(EnrollmentRevision, revision).evidence_reference += 'tampered'
    h.prepare(2)
    assert h.post('/activation-readiness', {}).json()['code'] == 'LOCAL_FYP_ACCOUNT_VERIFICATION_REQUIRED'
    h.assert_unchanged()


def test_account_signature_uses_mysql_datetime_second_precision(flow):
    h = flow
    scan = setup_scan(h, 1)
    h.f.fixture.now += timedelta(microseconds=550000)
    with h.f.sessions.begin() as db:
        identifier = record_account(db, 'DEVICE001', scan, h.f.fixture.now)
    with h.f.sessions.begin() as db:
        revision = db.get(EnrollmentRevision, identifier)
        revision.verified_at = revision.verified_at.replace(microsecond=0)
    with h.f.sessions() as db:
        assert local_demo.verified_account(db, db.get(EnrollmentRevision, identifier))


def test_explicit_transition_preserves_old_evidence_and_face_and_cannot_reuse_setup(flow):
    h = flow
    with h.f.sessions.begin() as db:
        template = db.get(Student, 'DEVICE001').face_encoding
        old = EnrollmentRevision(revision_id='local-demo-old-evidence', student_id='DEVICE001',
            template_hash=hashlib.sha256(template.encode()).hexdigest(), provenance='account_bound_fyp',
            assurance_level='UNVERIFIED', evidence_reference='LEGACY-NOT-INSTITUTIONAL', verified_at=h.f.fixture.now)
        db.add(old)
    scan = setup_scan(h, 1)
    with h.f.sessions.begin() as db:
        revision = record_account(db, 'DEVICE001', scan, h.f.fixture.now)
        assert revision != old.revision_id
        previous = db.get(EnrollmentRevision, old.revision_id)
        assert previous.evidence_reference == 'LEGACY-NOT-INSTITUTIONAL'
        assert previous.invalidated_at == h.f.fixture.now
        assert db.get(Student, 'DEVICE001').face_encoding == template
        with pytest.raises(AccountVerificationRejected):
            record_account(db, 'DEVICE001', scan, h.f.fixture.now)
    h.assert_unchanged()
