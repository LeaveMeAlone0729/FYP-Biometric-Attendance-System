from database_compat import shared_read
"""Signed observations, not RF attestation. No attendance imports or grants."""
import base64
import hashlib
import json
import secrets
from datetime import timedelta
from zoneinfo import ZoneInfo
from sqlalchemy import select, func
from config import iso_time
from modules.devices.crypto import decode_base64, verify_signature
from modules.devices.service import DeviceRegistrationError
from modules.devices.verification_service import DeviceVerificationService
from .models import Classroom, WifiChallenge, WifiEvent, WifiPolicy
from .policies import bssid, ssid

OPERATION = 'classroom_wifi_verification'
MESSAGES = {
    'CLASSROOM_WIFI_APPROVED': 'The reported access point matches this classroom simulation policy.',
    'WIFI_BSSID_MISMATCH': 'This access point is not approved for the selected classroom.',
    'WIFI_SSID_MISMATCH': 'The access point name does not match the classroom policy.',
    'WIFI_EVIDENCE_MISSING': 'Wi-Fi access point details are missing or redacted. Check permissions and Location services.',
    'WIFI_EVIDENCE_MALFORMED': 'The Wi-Fi observation is malformed. Refresh and try again.',
    'WIFI_EVIDENCE_STALE': 'The Wi-Fi observation is too old or the device clock differs. Refresh and check automatic date/time.',
    'WIFI_UNAVAILABLE': 'A connected Wi-Fi access point is unavailable. Connect to Wi-Fi and refresh.',
    'WIFI_PERMISSION_REQUIRED': 'Allow precise location permission and enable Location services to read Wi-Fi details.',
    'NO_ENABLED_CLASSROOM_POLICY': 'No enabled access point policy exists for this classroom.',
    'CLASSROOM_NOT_FOUND': 'The selected classroom is not configured.',
    'WIFI_CHALLENGE_NOT_FOUND': 'This check belongs to another login or does not exist. Start again.',
    'WIFI_CHALLENGE_REPLAYED': 'This check has already ended. Request a fresh check.',
    'WIFI_CHALLENGE_EXPIRED': 'The check expired. Refresh and verify again.',
    'WIFI_EVIDENCE_REPLAYED': 'This observation was already submitted. Refresh to take a new reading.',
    'INVALID_DEVICE_SIGNATURE': 'The Wi-Fi observation signature could not be verified.',
    'WIFI_RATE_LIMITED': 'Too many classroom checks. Wait one minute and try again.',
}


def parse_evidence(encoded):
    def unique(pairs):
        result = {}
        for k, v in pairs:
            if k in result: raise ValueError('duplicate key')
            result[k] = v
        return result
    raw = decode_base64(encoded)
    if len(raw) > 3000: raise ValueError('oversized evidence')
    value = json.loads(raw.decode('utf-8'), object_pairs_hook=unique,
                       parse_constant=lambda _: (_ for _ in ()).throw(ValueError('invalid number')))
    required = {'status', 'connection_type', 'permission_status', 'wifi_enabled', 'wifi_connected',
                'location_enabled', 'ssid', 'bssid', 'rssi_dbm', 'observed_at_ms'}
    if not isinstance(value, dict) or set(value) != required: raise ValueError('invalid fields')
    for name in ('status', 'connection_type', 'permission_status'):
        if not isinstance(value[name], str) or len(value[name]) > 40: raise ValueError('invalid status')
    for name in ('wifi_enabled', 'wifi_connected', 'location_enabled'):
        if value[name] is not None and type(value[name]) is not bool: raise ValueError('invalid boolean')
    if type(value['observed_at_ms']) is not int: raise ValueError('invalid timestamp')
    if value['rssi_dbm'] is not None and (type(value['rssi_dbm']) is not int or not -126 <= value['rssi_dbm'] < 0):
        raise ValueError('invalid RSSI')
    if value['bssid'] is not None: value['bssid'] = bssid(value['bssid'])
    value['ssid'] = ssid(value['ssid'])
    return raw.decode('utf-8'), value


class ClassroomWifiService:
    def __init__(self, context):
        self.context = context
        self.devices = DeviceVerificationService(context)

    def milliseconds(self, value):
        return int(value.replace(tzinfo=ZoneInfo(self.context.settings.timezone)).timestamp() * 1000)

    def event(self, db, student, result, code, challenge=None, policy=None):
        event = WifiEvent(student_id=student.student_id, result=result, reason_code=code,
            challenge_id=challenge.challenge_id if challenge else None,
            classroom_id=challenge.classroom_id if challenge else None,
            device_id=challenge.device_id if challenge else None,
            evidence_hash=challenge.evidence_hash if challenge else None,
            matched_policy_id=policy.policy_id if policy else None, verified_at=self.context.now())
        db.add(event)
        return event

    def deny(self, db, student, code, challenge=None, status=403):
        if challenge is not None and challenge.consumed_at is None:
            challenge.consumed_at = self.context.now()
            challenge.result = 'FAIL'
            challenge.failure_code = code
        self.event(db, student, 'FAIL', code, challenge)
        raise DeviceRegistrationError(status, code, MESSAGES[code])

    def begin(self, db, student, auth, data, *, operation=OPERATION, binding=None):
        student = self.devices.identity(db, student, auth, OPERATION)
        device = self.devices.device(db, student, OPERATION, fingerprint=data.public_key_fingerprint)
        if db.get(Classroom, data.classroom_id) is None:
            self.deny(db, student, 'CLASSROOM_NOT_FOUND', status=404)
        count = db.scalar(select(func.count()).select_from(WifiChallenge).where(
            WifiChallenge.student_id == student.student_id,
            WifiChallenge.created_at > self.context.now() - timedelta(minutes=1)))
        if count >= 20: self.deny(db, student, 'WIFI_RATE_LIMITED', status=429)
        now = self.context.now()
        identifier = secrets.token_urlsafe(32)
        expires = min(now + timedelta(seconds=45), auth.expires_at)
        payload = json.dumps(dict(version=1, operation=operation, challenge_id=identifier,
            student_id=student.student_id, auth_session=auth.token_hash, device_id=device.device_id,
            key_fingerprint=device.public_key_fingerprint, classroom_id=data.classroom_id,
            nonce=secrets.token_urlsafe(32), issued_at_ms=self.milliseconds(now),
            expires_at_ms=self.milliseconds(expires), **(binding or {})), sort_keys=True, separators=(',', ':'))
        challenge = WifiChallenge(challenge_id=identifier, student_id=student.student_id,
            auth_token_hash=auth.token_hash, device_id=device.device_id,
            key_fingerprint=device.public_key_fingerprint, classroom_id=data.classroom_id,
            operation=operation, signing_payload=payload, created_at=now, expires_at=expires)
        db.add(challenge)
        self.event(db, student, 'ISSUED', 'WIFI_CHALLENGE_ISSUED', challenge)
        return dict(success=True, challenge_id=identifier, operation=operation,
            classroom_id=data.classroom_id, device_id=device.device_id,
            public_key_fingerprint=device.public_key_fingerprint,
            signing_payload=base64.b64encode(payload.encode()).decode(),
            expires_at=iso_time(expires, self.context.settings))

    def confirm(self, db, student, auth, data):
        student = self.devices.identity(db, student, auth, OPERATION)
        ch = db.scalar(select(WifiChallenge).where(WifiChallenge.challenge_id == data.challenge_id)
            .with_for_update().execution_options(populate_existing=True))
        if ch is None or ch.student_id != student.student_id or ch.auth_token_hash != auth.token_hash:
            self.deny(db, student, 'WIFI_CHALLENGE_NOT_FOUND', status=404)
        if ch.consumed_at is not None: self.deny(db, student, 'WIFI_CHALLENGE_REPLAYED', ch, 409)
        if ch.expires_at <= self.context.now(): self.deny(db, student, 'WIFI_CHALLENGE_EXPIRED', ch, 410)
        from .models import AttendanceWifiBinding
        attendance_binding=db.get(AttendanceWifiBinding,ch.challenge_id)
        if attendance_binding is None and ch.operation != OPERATION:
            self.deny(db, student, 'WIFI_CHALLENGE_NOT_FOUND', ch)
        if attendance_binding is not None:
            from .attendance import AttendanceClassroomService
            try:AttendanceClassroomService(self.context).validate_binding(db,student,auth,ch,attendance_binding)
            except DeviceRegistrationError as exc:
                ch.consumed_at=self.context.now();ch.result='FAIL';ch.failure_code=exc.code
                self.event(db,student,'FAIL',exc.code,ch)
                raise
        try:
            device = self.devices.device(db, student, OPERATION, fingerprint=ch.key_fingerprint)
            if device.device_id != ch.device_id: raise DeviceRegistrationError(403, 'DEVICE_BINDING_CHANGED', 'Device registration changed.')
        except DeviceRegistrationError as exc:
            ch.consumed_at = self.context.now(); ch.result = 'FAIL'; ch.failure_code = exc.code
            self.event(db, student, 'FAIL', exc.code, ch)
            raise
        try:
            text, evidence = parse_evidence(data.evidence_payload)
        except (ValueError, TypeError, UnicodeError):
            self.deny(db, student, 'WIFI_EVIDENCE_MALFORMED', ch, 422)
        if not verify_signature(device.public_key_spki, ch.signing_payload + '\n' + text, data.signature):
            self.deny(db, student, 'INVALID_DEVICE_SIGNATURE', ch)
        if ch.expires_at <= self.context.now() or auth.expires_at <= self.context.now():
            self.deny(db, student, 'WIFI_CHALLENGE_EXPIRED', ch, 410)
        digest = hashlib.sha256(json.dumps(evidence, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()).hexdigest()
        previous = db.scalar(select(WifiChallenge.challenge_id).where(WifiChallenge.student_id == student.student_id,
            WifiChallenge.device_id == device.device_id, WifiChallenge.evidence_hash == digest).limit(1))
        if previous: self.deny(db, student, 'WIFI_EVIDENCE_REPLAYED', ch, 409)
        ch.evidence_hash = digest
        code, policy = self.evaluate(db, ch, evidence)
        if attendance_binding is not None:
            attendance_binding.evidence=json.dumps(evidence,sort_keys=True,separators=(',', ':'))
        ch.consumed_at = self.context.now()
        ch.result = 'PASS' if code == 'CLASSROOM_WIFI_APPROVED' else 'FAIL'
        ch.failure_code = None if ch.result == 'PASS' else code
        event = self.event(db, student, ch.result, code, ch, policy)
        db.flush()
        return dict(success=True, result=ch.result, reason_code=code, message=MESSAGES[code],
            verification_id=event.event_id, classroom_id=ch.classroom_id, device_id=ch.device_id,
            matched_policy_id=policy.policy_id if policy else None,
            verified_at=iso_time(event.verified_at, self.context.settings), operation=ch.operation,
            evidence_source='CLIENT_REPORTED_ANDROID_WIFI', attendance_authorized=False)

    def evaluate(self, db, ch, e):
        now_ms = self.milliseconds(self.context.now())
        if not self.milliseconds(ch.created_at) - 2000 <= e['observed_at_ms'] <= now_ms + 5000 or now_ms - e['observed_at_ms'] > 15000:
            return 'WIFI_EVIDENCE_STALE', None
        if e['permission_status'] != 'PRECISE_GRANTED' or e['location_enabled'] is not True:
            return 'WIFI_PERMISSION_REQUIRED', None
        if e['wifi_enabled'] is not True or e['wifi_connected'] is not True:
            return 'WIFI_UNAVAILABLE', None
        if e['status'] in ('PERMISSION_REQUIRED', 'LOCATION_DISABLED'):
            return 'WIFI_PERMISSION_REQUIRED', None
        if e['status'] in ('WIFI_OFF', 'NOT_CONNECTED', 'UNSUPPORTED', 'INFO_UNAVAILABLE'):
            return 'WIFI_UNAVAILABLE', None
        if not e['bssid'] or e['status'] == 'REDACTED': return 'WIFI_EVIDENCE_MISSING', None
        if e['status'] != 'AVAILABLE': return 'WIFI_EVIDENCE_MALFORMED', None
        # Lock current policy rows so disable/retirement cannot race the verdict.
        policies = list(db.scalars(select(WifiPolicy).where(WifiPolicy.classroom_id == ch.classroom_id,
            WifiPolicy.enabled.is_(True), WifiPolicy.retired_at.is_(None)).order_by(WifiPolicy.policy_id).with_for_update(read=shared_read(db))))
        if not policies: return 'NO_ENABLED_CLASSROOM_POLICY', None
        matching = [p for p in policies if p.bssid == e['bssid']]
        if not matching: return 'WIFI_BSSID_MISMATCH', None
        for p in matching:
            if p.ssid is None or p.ssid == e['ssid']: return 'CLASSROOM_WIFI_APPROVED', p
        return ('WIFI_EVIDENCE_MISSING' if e['ssid'] is None else 'WIFI_SSID_MISMATCH'), None
