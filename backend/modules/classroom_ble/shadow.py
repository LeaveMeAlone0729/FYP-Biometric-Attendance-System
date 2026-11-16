"""BLE diagnostic binding to an existing attendance attempt and passed preflight."""
import hashlib
import json

from sqlalchemy import func, select

from models import Challenge, ClassSession
from modules.authorization.models import AttendanceDeviceChallenge
from modules.classroom_wifi.models import AttendanceWifiBinding, AttemptClassroom, WifiEvent
from modules.devices.service import DeviceRegistrationError

OPERATION = 'attendance_ble_shadow'


def challenge_id(attempt_id):
    # Domain-separated from standalone random challenge IDs. The existing
    # primary key limits this optional check to one per attendance attempt.
    return hashlib.sha256(f'{OPERATION}:{attempt_id}'.encode()).hexdigest()


def bind(db, context, student, auth, *, attempt_id, proof_id, classroom_id, fingerprint):
    attempt = db.get(Challenge, attempt_id, with_for_update=True, populate_existing=True)
    proof = db.get(AttendanceDeviceChallenge, proof_id, populate_existing=True)
    if (attempt is None or proof is None or attempt.student_id != student.student_id
            or attempt.auth_token_hash != auth.token_hash
            or proof.attendance_challenge_id != attempt_id or proof.session_id != attempt.session_id
            or proof.student_id != student.student_id or proof.auth_token_hash != auth.token_hash
            or proof.key_fingerprint != fingerprint or proof.result != 'PASS' or proof.consumed_at is None
            or json.loads(proof.signing_payload).get('purpose') != 'attendance_preflight'):
        raise DeviceRegistrationError(403, 'BLE_SHADOW_BINDING_MISMATCH',
                                      'BLE requires the device and login that passed attendance preflight.')
    snapshot = db.get(AttemptClassroom, attempt_id)
    if snapshot is None or snapshot.session_id != attempt.session_id or snapshot.classroom_id != classroom_id:
        raise DeviceRegistrationError(403, 'BLE_SHADOW_BINDING_MISMATCH',
                                      'BLE classroom does not match this attendance attempt.')
    session = db.get(ClassSession, attempt.session_id, populate_existing=True)
    if (attempt.consumed or attempt.expires_at <= context.now()
            or session is None or not context.session_open(session, student, db)):
        raise DeviceRegistrationError(410, 'BLE_SHADOW_ATTEMPT_ENDED', 'This attendance attempt has ended.')
    return attempt, proof


def recent_outcomes(db, now):
    """Bounded admin projection without payloads, keys or student identifiers."""
    from .models import BleChallenge, BleEvent

    attempts = db.execute(select(
        Challenge.challenge_id, Challenge.verification_id, Challenge.session_id,
        Challenge.expires_at, Challenge.consumed, AttemptClassroom.classroom_id,
        AttemptClassroom.created_at,
    ).join(AttemptClassroom, AttemptClassroom.attempt_id == Challenge.challenge_id)
        .order_by(Challenge.verification_id.desc()).limit(50)).all()
    if not attempts:
        return
    ids = [challenge_id(row.challenge_id) for row in attempts]
    results = {row.challenge_id: row for row in db.execute(select(
        BleChallenge.challenge_id, BleChallenge.classroom_id, BleChallenge.result,
        BleChallenge.failure_code, BleChallenge.created_at, BleChallenge.consumed_at,
        BleChallenge.expires_at,
    ).where(BleChallenge.operation == OPERATION, BleChallenge.challenge_id.in_(ids)))}
    no_policy = {row.challenge_id: row.occurred_at for row in db.execute(select(
        BleEvent.challenge_id, func.max(BleEvent.occurred_at).label('occurred_at'),
    ).where(BleEvent.challenge_id.in_(ids), BleEvent.reason_code == 'NO_ENABLED_BLE_POLICY')
        .group_by(BleEvent.challenge_id))}
    latest_preflight_wifi = select(func.max(WifiEvent.event_id)).join(
        AttendanceWifiBinding, AttendanceWifiBinding.challenge_id == WifiEvent.challenge_id,
    ).where(AttendanceWifiBinding.attempt_id.in_([row.challenge_id for row in attempts]),
            AttendanceWifiBinding.purpose == 'attendance_preflight', WifiEvent.result != 'ISSUED'
    ).group_by(AttendanceWifiBinding.attempt_id)
    wifi_failures = {row.attempt_id: row for row in db.execute(select(
        AttendanceWifiBinding.attempt_id, WifiEvent.reason_code, WifiEvent.verified_at,
    ).join(WifiEvent, WifiEvent.challenge_id == AttendanceWifiBinding.challenge_id)
        .where(WifiEvent.event_id.in_(latest_preflight_wifi), WifiEvent.result == 'FAIL'))}
    for attempt in attempts:
        identifier = challenge_id(attempt.challenge_id)
        check = results.get(identifier)
        result, reason, occurred = 'NOT CHECKED', '—', attempt.created_at
        if check is not None and check.classroom_id == attempt.classroom_id:
            occurred = check.consumed_at or check.created_at
            if check.result == 'PENDING':
                if attempt.consumed or min(attempt.expires_at, check.expires_at) <= now:
                    result, reason = 'UNAVAILABLE', 'BLE_RESULT_NOT_RECEIVED'
                else:
                    reason = 'BLE_CHECK_PENDING'
            else:
                reason = check.failure_code or 'BLE_APPROVED'
                unavailable = check.result == 'UNCERTAIN' or reason in {
                    'BLE_CHALLENGE_EXPIRED', 'BLE_SHADOW_ATTEMPT_ENDED',
                }
                result = 'UNAVAILABLE' if unavailable else check.result
        elif identifier in no_policy:
            reason, occurred = 'NO_ENABLED_BLE_POLICY', no_policy[identifier]
        elif attempt.challenge_id in wifi_failures:
            wifi = wifi_failures[attempt.challenge_id]
            reason, occurred = wifi.reason_code, wifi.verified_at
        yield dict(attempt=attempt.verification_id, session=attempt.session_id,
                   classroom=attempt.classroom_id or '—', result=result, reason=reason,
                   occurred=occurred.isoformat(sep=' ', timespec='seconds'))
