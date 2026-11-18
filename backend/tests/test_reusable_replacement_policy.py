"""Both-slot normal FYP policy regressions; SQLite, synthetic face, real ECDSA.

No patched approval provider and no LOCAL DEMO/account/model exception.
"""
from datetime import timedelta
from pathlib import Path
import sys
from unittest.mock import patch

import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from models import Attendance
from modules.devices.management_models import DeviceBiometricAuthorization, EnrollmentRevision
from modules.devices.models import RegisteredDevice
import test_account_bound_enrollment as account
import test_device_biometrics as biometric
import test_device_replacement as replacement


@pytest.fixture(scope='module')
def password_hash():
    replacement.ReplacementTests.setUpClass()
    return replacement.ReplacementTests.password_hash


@pytest.fixture
def flow(password_hash):
    h = replacement.ReplacementTests()
    h.password_hash = password_hash
    h.setUp()
    account.prepare_account(h.f)
    assert account.enroll(h.f).status_code == 200
    try:
        yield h
    finally:
        h.tearDown()


def ready(h, slot):
    pending = h.prepare(slot)
    bio = biometric.DeviceBiometricTests()
    bio.f, bio.p, bio.pending = h.f, h.h.p, pending
    bio.complete()
    response = h.post('/activation-readiness', {})
    assert response.status_code == 200, response.text
    approval = response.json()
    response = h.post('/activation-challenges', {'approval_id': approval['approval_id']})
    assert response.status_code == 201, response.text
    challenge = response.json()
    body = dict(approval_id=approval['approval_id'], challenge_id=challenge['challenge_id'],
                signature=h.h.signature(challenge))
    return pending, approval, challenge, body


@pytest.mark.parametrize('slot', [1, 2])
def test_success_and_replay_revoke_only_selected_key(flow, slot):
    h = flow
    pending, approval, challenge, body = ready(h, slot)
    response = h.post('/activate', body)
    assert response.status_code == 200, response.text
    assert h.post('/activate', body).json()['code'] == 'ACTIVATION_REPLAYED'
    after = h.rows()
    old = h.h.binding.replaced_device_id
    assert after[old]['status'] == 'REVOKED'
    assert after[pending['candidate_device_id']]['status'] == 'ACTIVE'
    assert sum(row['status'] == 'ACTIVE' for row in after.values()) == 2
    for identifier, row in h.before.items():
        if identifier != old:
            assert after[identifier] == row
    assert h.f.issue(fingerprint=h.before[old]['public_key_fingerprint']).status_code == 403
    proof = h.f.issue(fingerprint=after[pending['candidate_device_id']]['public_key_fingerprint'])
    assert h.f.confirm(proof.json(), key=h.h.p.key).json()['result'] == 'PASS'
    with h.f.sessions() as db:
        assert db.get(DeviceBiometricAuthorization, approval['approval_id']).consumed_at is not None
        assert db.scalar(select(EnrollmentRevision)).assurance_level == 'ACCOUNT_BOUND_FYP'
    assert h.h.count(Attendance) == 0


@pytest.mark.parametrize('slot', [1, 2])
def test_no_fresh_replacement_scan_never_uses_enrollment_as_approval(flow, slot):
    h = flow
    h.prepare(slot)
    response = h.post('/activation-readiness', {})
    assert response.json()['code'] == 'FRESH_BIOMETRIC_PROOF_REQUIRED'
    h.assert_unchanged()


@pytest.mark.parametrize('slot', [1, 2])
def test_wrong_candidate_signature_does_not_revoke(flow, slot):
    h = flow
    _, _, challenge, body = ready(h, slot)
    body['signature'] = h.h.signature(challenge, ec.generate_private_key(ec.SECP256R1()))
    assert h.post('/activate', body).json()['code'] == 'INVALID_ACTIVATION_SIGNATURE'
    h.assert_unchanged()


@pytest.mark.parametrize('slot', [1, 2])
def test_expired_approval_keeps_both_devices(flow, slot):
    h = flow
    _, _, _, body = ready(h, slot)
    h.f.fixture.now += timedelta(seconds=61)
    response = h.post('/activate', body)
    assert response.status_code == 410, response.text
    h.assert_unchanged()


@pytest.mark.parametrize('slot', [1, 2])
def test_wrong_login_cannot_consume_approval(flow, slot):
    h = flow
    _, approval, _, body = ready(h, slot)
    response = h.post('/activate', body, headers=h.f.fixture.login('DEVICE001'))
    assert response.status_code == 404, response.text
    with h.f.sessions() as db:
        assert db.get(DeviceBiometricAuthorization, approval['approval_id']).consumed_at is None
    h.assert_unchanged()


@pytest.mark.parametrize('slot', [1, 2])
def test_insert_failure_rolls_back_target_revocation_and_approval(flow, slot):
    h = flow
    pending, approval, _, body = ready(h, slot)
    before = h.rows()
    original_flush = Session.flush
    def fail_candidate_insert(db, *args, **kwargs):
        if any(isinstance(row, RegisteredDevice) and row.device_id == pending['candidate_device_id'] for row in db.new):
            raise IntegrityError('isolated candidate insertion failure', {}, Exception('synthetic fault'))
        return original_flush(db, *args, **kwargs)
    with patch.object(Session, 'flush', fail_candidate_insert):
        response = h.post('/activate', body)
    assert response.json()['code'] == 'ACTIVATION_CONFLICT', response.text
    assert h.rows() == before
    with h.f.sessions() as db:
        assert db.get(DeviceBiometricAuthorization, approval['approval_id']).consumed_at is None
    assert h.h.count(Attendance) == 0
