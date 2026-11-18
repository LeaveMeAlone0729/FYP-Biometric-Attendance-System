"""Direct device face/PAD evidence: synthetic identities, no live database."""
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import select, func

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import test_device_biometrics as biometric
from modules.devices.biometric_models import DeviceBiometricSession, DeviceBiometricEvent
from modules.devices.management_models import DeviceBiometricAuthorization
from models import Attendance


@pytest.fixture(scope='module')
def password():
    biometric.DeviceBiometricTests.setUpClass()
    return biometric.DeviceBiometricTests.password_hash


@pytest.fixture
def flow(password):
    h=biometric.DeviceBiometricTests();h.password_hash=password;h.setUp()
    try:
        yield h
    finally:
        h.tearDown()


def test_direct_scan_uses_partner_face_pad_but_no_hand_or_head_challenge(flow):
    bio=flow.f.fixture.app.state.context.bio
    with patch.object(bio,'hand',side_effect=AssertionError('No gestures allowed')) as hand, patch.object(bio,'head_pose',side_effect=AssertionError('No head challenges allowed')) as head:
        identifier,response=flow.complete()
    assert response.status_code==200
    result=response.json()
    assert result['verification_mode']=='DIRECT_FACE_PAD_V1'
    assert result['face_verified'] and result['anti_spoof_verified']
    assert result['fingers'] is None and result['valid_frames']==3
    assert result['trusted'] is False and result['activation_eligible'] is False
    hand.assert_not_called();head.assert_not_called()
    with flow.f.sessions() as db:
        events=db.scalars(select(DeviceBiometricEvent).where(DeviceBiometricEvent.approval_id==identifier)).all()
        assert sum(e.code=='DIRECT_FACE_PAD_FRAME_VERIFIED' and e.result=='PASS' for e in events)==3
        assert db.scalar(select(func.count()).select_from(Attendance))==0
        assert db.scalar(select(func.count()).select_from(DeviceBiometricAuthorization))==0


@pytest.mark.parametrize('pixels',[b'photo',b'screen',b'video'])
def test_existing_partner_spoof_rejection_never_completes_or_authorizes(flow,pixels):
    identifier,_=flow.face()
    result=flow.frame(identifier,pixels,'liveness/frame')
    assert result.status_code==200
    assert result.json()['ready'] is False
    assert not result.json()['complete'] and not result.json()['anti_spoof_verified']
    assert result.json()['valid_frames']==0
    assert flow.p.count(Attendance)==0
    assert flow.p.count(DeviceBiometricAuthorization)==0


@pytest.mark.parametrize('evidence',[None,{}, {'real_scores':[float('nan'),1]}, {'real_scores':['PASS',1]}])
def test_missing_or_invalid_pad_evidence_fails_closed(flow,evidence):
    identifier,_=flow.face()
    bio=flow.f.fixture.app.state.context.bio
    with patch.object(bio,'face_observation',return_value=([0.0]*128,evidence)):
        result=flow.frame(identifier,b'fresh-invalid-pad','liveness/frame')
    assert result.status_code==503
    assert result.json()['code']=='BIOMETRIC_ENGINE_UNAVAILABLE'
    assert flow.p.count(DeviceBiometricAuthorization)==0
    assert flow.p.count(Attendance)==0


def test_old_client_must_negotiate_direct_protocol_without_creating_session(flow):
    response=flow.f.client.post('/api/v1/device-approvals',headers=flow.f.headers,
        json={'pending_registration_id':flow.pending['pending_registration_id']})
    assert response.status_code==409
    assert response.json()['code']=='DIRECT_FACE_SCAN_REQUIRED'
    assert flow.p.count(DeviceBiometricSession)==0


def test_legacy_scan_cannot_be_relabelled_as_direct_pad(flow):
    identifier=flow.create().json()['approval_id']
    with flow.f.sessions.begin() as db:
        marker=db.scalar(select(DeviceBiometricEvent).where(DeviceBiometricEvent.approval_id==identifier,
            DeviceBiometricEvent.code=='DIRECT_FACE_PAD_SESSION_CREATED'))
        db.delete(marker)
    response=flow.frame(identifier)
    assert response.status_code==409
    assert response.json()['code']=='BIOMETRIC_PROTOCOL_CHANGED'
    assert flow.p.count(DeviceBiometricAuthorization)==0


def test_client_pad_and_success_flags_are_rejected(flow):
    identifier=flow.create().json()['approval_id']
    response=flow.frame(identifier,extra={'anti_spoof_verified':'true','complete':'true'})
    assert response.status_code==422
    assert response.json()['code']=='INVALID_FRAME_INPUT'
    assert flow.p.count(DeviceBiometricAuthorization)==0
