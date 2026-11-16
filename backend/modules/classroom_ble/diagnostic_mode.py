"""Opt-in diagnostic simulation. Creates no biometric or attendance attempt."""
import hmac
import json
import secrets
from types import SimpleNamespace

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from api.dependencies import authenticated, get_context, get_db
from database_compat import shared_read
from models import ClassSession, ClassSchedule
from security import digest
from modules.classroom_wifi.models import SessionClassroom, WifiChallenge
from modules.classroom_wifi.router import Confirm as WifiConfirm
from modules.classroom_wifi.service import ClassroomWifiService
from modules.devices.router import registration_response
from modules.devices.service import DeviceRegistrationError
from modules.devices.verification_service import DeviceVerificationService
from modules.networks.service import NetworkVerificationService
from .models import BleChallenge, BleEvent
from .router import Confirm as BleConfirm
from .service import BleVerificationService

router = APIRouter(prefix='/api/v1/network-ble-tests', tags=['Temporary network and BLE tests'])


def enabled(context=Depends(get_context)):
    if not context.settings.network_ble_test_mode:
        raise HTTPException(404, 'Network + BLE Test is disabled.')
    return context


class Start(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    session_id: int = Field(gt=0)
    pin: str = Field(pattern=r'^\d{6}$')
    public_key_fingerprint: str = Field(pattern=r'^[0-9a-f]{64}$')


class Finish(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    test_id: str = Field(pattern=r'^nbt\.\d+\.[A-Za-z0-9_-]{24}$', max_length=64)
    wifi: WifiConfirm
    ble: BleConfirm


def session_requirement(db, context, student, session_id):
    session = db.scalar(select(ClassSession).where(ClassSession.session_id == session_id)
                        .with_for_update(read=shared_read(db)).execution_options(populate_existing=True))
    if session is None or not context.session_open(session, student, db):
        raise DeviceRegistrationError(403, 'TEST_SESSION_NOT_ELIGIBLE', 'Select an open session for your group.')
    requirement = db.get(SessionClassroom, session_id, populate_existing=True)
    if requirement is None or requirement.classroom_id is None:
        raise DeviceRegistrationError(409, 'TEST_CLASSROOM_REQUIRED', 'The session needs a configured classroom.')
    return session, requirement


def result(db, context, student, test_id, classroom, device_id, network, wifi=None, ble=None, *, reason=None):
    stages = dict(network=network, wifi=wifi, ble=ble)
    failure = reason or next((value['reason_code'] for value in stages.values()
                              if value and value['result'] != 'PASS'), None)
    passed = failure is None and all(stages.values())
    code = 'NETWORK_BLE_TEST_PASS' if passed else failure or 'TEST_INCOMPLETE'
    db.add(BleEvent(student_id=student.student_id, challenge_id=test_id, classroom_id=classroom,
                    device_id=device_id, result='TEST_PASS' if passed else 'TEST_FAIL',
                    reason_code=code, occurred_at=context.now()))
    return dict(success=True, diagnostic_test=True, attendance_authorized=False,
                test_id=test_id, test_result='PASS' if passed else 'FAIL', reason_code=code,
                session_id=int(test_id.split('.')[1]), classroom_id=classroom, **stages)


def recent_test_outcomes(db):
    rows = db.execute(select(BleEvent.challenge_id, BleEvent.classroom_id, BleEvent.result,
        BleEvent.reason_code, BleEvent.occurred_at).where(
            BleEvent.result.in_(('TEST_PASS', 'TEST_FAIL')), BleEvent.challenge_id.like('nbt.%')
        ).order_by(BleEvent.event_id.desc()).limit(50)).all()
    for row in rows:
        parts = row.challenge_id.split('.')
        if len(parts) == 3 and parts[1].isdigit():
            yield dict(session=int(parts[1]), classroom=row.classroom_id, result=row.result,
                       reason=row.reason_code, occurred=row.occurred_at.isoformat(sep=' ', timespec='seconds'))


@router.get('/sessions')
def sessions(identity=Depends(authenticated), db=Depends(get_db, scope='function'), context=Depends(enabled)):
    student, _ = identity
    rows = db.scalars(select(ClassSession).join(ClassSchedule).where(
        ClassSchedule.group_id == student.group_id, ClassSession.status == 'active',
        ClassSession.session_date == context.now().date()).order_by(ClassSession.session_id)).all()
    available = []
    for session in rows:
        requirement = db.get(SessionClassroom, session.session_id)
        if context.session_open(session, student, db) and requirement and requirement.classroom_id:
            available.append(dict(session_id=session.session_id, classroom_id=requirement.classroom_id,
                                  venue=session.venue))
    return dict(success=True, diagnostic_test=True, sessions=available)


@router.post('/start')
def start(data: Start, request: Request, identity=Depends(authenticated),
          db=Depends(get_db, scope='function'), context=Depends(enabled)):
    def run():
        student, auth = identity
        devices = DeviceVerificationService(context)
        student = devices.identity(db, student, auth, 'network_ble_test')
        device = devices.device(db, student, 'network_ble_test', fingerprint=data.public_key_fingerprint)
        session, room = session_requirement(db, context, student, data.session_id)
        if not hmac.compare_digest(session.pin_hash, digest(data.pin)):
            raise DeviceRegistrationError(403, 'TEST_PIN_INVALID', 'The PIN does not match the selected session.')
        test_id = f'nbt.{session.session_id}.{secrets.token_urlsafe(18)}'
        network = NetworkVerificationService(context).verify(db, student, auth, request.scope)
        if network['result'] != 'PASS':
            return result(db, context, student, test_id, room.classroom_id, device.device_id, network)
        binding = dict(diagnostic_test=True, test_id=test_id, test_session_id=session.session_id,
                       test_classroom_revision=room.revision)
        selector = SimpleNamespace(classroom_id=room.classroom_id,
                                   public_key_fingerprint=device.public_key_fingerprint,
                                   attendance_attempt_id=None)
        wifi = ClassroomWifiService(context).begin(db, student, auth, selector, binding=binding)
        try:
            ble = BleVerificationService(context).begin(db, student, auth, selector,
                diagnostic_binding=dict(**binding, test_wifi_challenge_id=wifi['challenge_id']))
        except DeviceRegistrationError as exc:
            ch = db.get(WifiChallenge, wifi['challenge_id'])
            ch.consumed_at = context.now()
            ch.result, ch.failure_code = 'FAIL', exc.code
            return result(db, context, student, test_id, room.classroom_id, device.device_id,
                          network, reason=exc.code)
        return dict(success=True, diagnostic_test=True, attendance_authorized=False,
                    test_id=test_id, session_id=session.session_id, classroom_id=room.classroom_id,
                    network=network, wifi=wifi, ble=ble)
    return registration_response(run)


@router.post('/finish')
def finish(data: Finish, request: Request, identity=Depends(authenticated),
           db=Depends(get_db, scope='function'), context=Depends(enabled)):
    def run():
        student, auth = identity
        devices = DeviceVerificationService(context)
        student = devices.identity(db, student, auth, 'network_ble_test')
        wifi = db.get(WifiChallenge, data.wifi.challenge_id, with_for_update=True, populate_existing=True)
        ble = db.get(BleChallenge, data.ble.challenge_id, with_for_update=True, populate_existing=True)
        if (wifi is None or ble is None or any(ch.student_id != student.student_id or
                ch.auth_token_hash != auth.token_hash for ch in (wifi, ble))):
            raise DeviceRegistrationError(403, 'TEST_BINDING_MISMATCH', 'These test proofs belong to another login.')
        wp, bp = json.loads(wifi.signing_payload), json.loads(ble.signing_payload)
        if (any(p.get('diagnostic_test') is not True or p.get('test_id') != data.test_id for p in (wp, bp))
                or wp.get('test_session_id') != bp.get('test_session_id')
                or wp.get('test_classroom_revision') != bp.get('test_classroom_revision')
                or bp.get('test_wifi_challenge_id') != wifi.challenge_id
                or wifi.device_id != ble.device_id or wifi.key_fingerprint != ble.key_fingerprint
                or wifi.classroom_id != ble.classroom_id):
            raise DeviceRegistrationError(403, 'TEST_BINDING_MISMATCH', 'These test proofs do not belong together.')
        if ble.consumed_at is not None:
            raise DeviceRegistrationError(409, 'BLE_CHALLENGE_REPLAYED', 'Run a fresh diagnostic test.')
        if wifi.consumed_at is not None:
            raise DeviceRegistrationError(409, 'WIFI_CHALLENGE_REPLAYED', 'Run a fresh diagnostic test.')
        network = wifi_result = ble_result = None
        failure = None
        try:
            session, room = session_requirement(db, context, student, bp['test_session_id'])
            if room.classroom_id != ble.classroom_id or room.revision != bp['test_classroom_revision']:
                raise DeviceRegistrationError(409, 'TEST_CLASSROOM_CHANGED', 'The session classroom changed.')
            wifi_result = ClassroomWifiService(context).confirm(db, student, auth, data.wifi)
            if wifi_result['result'] == 'PASS':
                ble_result = BleVerificationService(context).confirm(db, student, auth, data.ble)
            network = NetworkVerificationService(context).verify(db, student, auth, request.scope)
            # Closing or reassigning a session during inference cannot produce PASS.
            session_requirement(db, context, student, session.session_id)
            if ble.expires_at <= context.now() or auth.expires_at <= context.now():
                raise DeviceRegistrationError(410, 'BLE_CHALLENGE_EXPIRED', 'The diagnostic deadline expired.')
            if wifi.expires_at <= context.now():
                raise DeviceRegistrationError(410, 'WIFI_CHALLENGE_EXPIRED', 'The diagnostic deadline expired.')
        except DeviceRegistrationError as exc:
            failure = exc.code
        code = failure or next((value['reason_code'] for value in (network, wifi_result, ble_result)
                                if value and value['result'] != 'PASS'), 'TEST_INCOMPLETE')
        for ch in (wifi, ble):
            if ch.consumed_at is None:
                ch.consumed_at = context.now()
                ch.result, ch.failure_code = 'FAIL', code
        return result(db, context, student, data.test_id, ble.classroom_id, ble.device_id,
                      network, wifi_result, ble_result, reason=failure)
    return registration_response(run)
