"""Device possession only. PASS is a point-in-time audit result, never attendance authority."""
import base64
import json
import secrets
from datetime import timedelta
from sqlalchemy import func, select
from config import iso_time
from models import AuthSession, Student
from .crypto import canonical_public_key, verify_signature
from .models import RegisteredDevice
from .service import DeviceRegistrationError
from .verification_models import DeviceVerificationChallenge, DeviceVerificationEvent

VERIFICATION_SECONDS = 60
ISSUANCE_LIMIT = 20


class DeviceVerificationService:
    def __init__(self, context):
        self.context = context

    def event(self, db, student, operation, action, result, code, challenge=None, source="server"):
        event = DeviceVerificationEvent(student_id=student.student_id, operation=operation,
            action=action, result=result, code=code, source=source,
            challenge_id=challenge.challenge_id if challenge else None,
            device_id=challenge.device_id if challenge else None, occurred_at=self.context.now())
        db.add(event)
        return event

    def deny(self, db, student, operation, status, code, message, challenge=None):
        if challenge is not None and challenge.consumed_at is None:
            challenge.consumed_at = self.context.now()
            challenge.result = "FAIL"
            challenge.failure_code = code
        self.event(db, student, operation, "verify" if challenge else "challenge", "FAIL", code, challenge)
        # The device router returns an error response so get_db commits denial evidence.
        raise DeviceRegistrationError(status, code, message)

    def identity(self, db, student, auth, operation):
        student = db.scalar(select(Student).where(Student.student_id == student.student_id)
            .with_for_update().execution_options(populate_existing=True))
        current = db.scalar(select(AuthSession).where(AuthSession.token_hash == auth.token_hash)
            .with_for_update().execution_options(populate_existing=True))
        if student is None or current is None:
            raise DeviceRegistrationError(401, "SESSION_EXPIRED", "Please sign in again.")
        if current.expires_at <= self.context.now() or student.account_status != "active":
            self.deny(db, student, operation, 401, "SESSION_EXPIRED", "Please sign in again.")
        return student

    def device(self, db, student, operation, challenge=None):
        device = db.scalar(select(RegisteredDevice).where(RegisteredDevice.student_id == student.student_id)
            .with_for_update().execution_options(populate_existing=True))
        if device is None:
            self.deny(db, student, operation, 409, "DEVICE_NOT_REGISTERED",
                      "Register this Android device before checking its identity.", challenge)
        if device.status != "ACTIVE":
            self.deny(db, student, operation, 403, "DEVICE_NOT_ACTIVE",
                      "Your registered device is not active. Contact the project administrator.", challenge)
        if challenge is not None and (device.device_id != challenge.device_id
                or device.public_key_fingerprint != challenge.key_fingerprint):
            self.deny(db, student, operation, 403, "DEVICE_BINDING_CHANGED",
                      "The device registration changed. Start a fresh check.", challenge)
        try:
            _, fingerprint = canonical_public_key(device.public_key_spki)
        except ValueError:
            fingerprint = None
        if fingerprint != device.public_key_fingerprint:
            self.deny(db, student, operation, 403, "DEVICE_KEY_INVALID",
                      "The registered public key is not valid. Contact the project administrator.", challenge)
        return device

    def begin(self, db, student, auth, data):
        operation = data.operation
        student = self.identity(db, student, auth, operation)
        device = self.device(db, student, operation)
        recent = db.scalar(select(func.count()).select_from(DeviceVerificationEvent).where(
            DeviceVerificationEvent.student_id == student.student_id,
            DeviceVerificationEvent.result == "ISSUED",
            DeviceVerificationEvent.occurred_at > self.context.now() - timedelta(minutes=5)))
        if recent >= ISSUANCE_LIMIT:
            self.deny(db, student, operation, 429, "VERIFICATION_RATE_LIMITED",
                      "Too many automatic device checks. Try again in five minutes.")
        now = self.context.now()
        expires = min(now + timedelta(seconds=VERIFICATION_SECONDS), auth.expires_at)
        identifier = secrets.token_urlsafe(32)
        payload = json.dumps(dict(version=1, purpose="device_verification", operation=operation,
            challenge_id=identifier, student_id=student.student_id, device_id=device.device_id,
            public_key_fingerprint=device.public_key_fingerprint, nonce=secrets.token_urlsafe(32),
            expires_at=iso_time(expires, self.context.settings)), sort_keys=True, separators=(",", ":"))
        challenge = DeviceVerificationChallenge(challenge_id=identifier, student_id=student.student_id,
            auth_token_hash=auth.token_hash, device_id=device.device_id,
            key_fingerprint=device.public_key_fingerprint, operation=operation,
            signing_payload=payload, created_at=now, expires_at=expires, result="PENDING")
        db.add(challenge)
        self.event(db, student, operation, "challenge", "ISSUED", "VERIFICATION_CHALLENGE_ISSUED", challenge)
        return dict(success=True, challenge_id=identifier, device_id=device.device_id, operation=operation,
            public_key_fingerprint=device.public_key_fingerprint, algorithm="ECDSA_P256_SHA256",
            signature_encoding="base64-DER", signing_payload=base64.b64encode(payload.encode()).decode(),
            expires_at=iso_time(expires, self.context.settings))

    def owned_challenge(self, db, student, auth, data):
        # All device mutations lock student -> auth -> device -> challenge.
        challenge = db.scalar(select(DeviceVerificationChallenge).where(
            DeviceVerificationChallenge.challenge_id == data.challenge_id).with_for_update()
            .execution_options(populate_existing=True))
        if challenge is None or challenge.student_id != student.student_id or challenge.auth_token_hash != auth.token_hash:
            self.deny(db, student, data.operation, 404, "VERIFICATION_NOT_FOUND",
                      "Device verification challenge not found.")
        if challenge.consumed_at is not None:
            self.deny(db, student, data.operation, 409, "VERIFICATION_REPLAYED",
                      "This device check has already ended. Start a fresh check.", challenge)
        if challenge.expires_at <= self.context.now():
            self.deny(db, student, data.operation, 410, "VERIFICATION_EXPIRED",
                      "The device check expired. Start a fresh check.", challenge)
        if challenge.operation != data.operation:
            self.deny(db, student, data.operation, 403, "OPERATION_MISMATCH",
                      "The device check belongs to a different operation.", challenge)
        return challenge

    def confirm(self, db, student, auth, data):
        student = self.identity(db, student, auth, data.operation)
        # Lock the active device before challenge to match issuance/replacement order.
        device = db.scalar(select(RegisteredDevice).where(RegisteredDevice.student_id == student.student_id)
            .with_for_update().execution_options(populate_existing=True))
        challenge = self.owned_challenge(db, student, auth, data)
        device = self.device(db, student, data.operation, challenge)
        if not verify_signature(device.public_key_spki, challenge.signing_payload, data.signature):
            self.deny(db, student, data.operation, 403, "INVALID_DEVICE_SIGNATURE",
                      "Device identity could not be verified. This installation may not hold the registered key.", challenge)
        # Recheck after crypto work; no successful response can cross its deadline.
        if challenge.expires_at <= self.context.now() or auth.expires_at <= self.context.now():
            self.deny(db, student, data.operation, 410, "VERIFICATION_EXPIRED",
                      "The device check expired. Start a fresh check.", challenge)
        challenge.consumed_at = self.context.now()
        challenge.result = "PASS"
        event = self.event(db, student, data.operation, "verify", "PASS", "DEVICE_VERIFIED", challenge)
        db.flush()
        return dict(success=True, result="PASS", verification_id=event.event_id,
            challenge_id=challenge.challenge_id, device_id=device.device_id, operation=challenge.operation,
            verified_at=iso_time(event.occurred_at, self.context.settings),
            challenge_expires_at=iso_time(challenge.expires_at, self.context.settings), attendance_authorized=False)

    def client_failure(self, db, student, auth, data):
        student = self.identity(db, student, auth, data.operation)
        challenge = self.owned_challenge(db, student, auth, data)
        challenge.consumed_at = self.context.now()
        challenge.result = "FAIL"
        challenge.failure_code = data.reason_code
        self.event(db, student, data.operation, "client_failure", "FAIL", data.reason_code, challenge, source="client")
        return dict(success=True, result="FAIL", code=data.reason_code)
