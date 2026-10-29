"""Registration only. All mutation paths serialize on the existing student row."""
import base64
import json
import secrets
from datetime import timedelta
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from config import iso_time
from models import AuthSession, Student
from .crypto import canonical_public_key, verify_signature
from .models import DeviceRegistrationChallenge, DeviceRegistrationEvent, RegisteredDevice

CHALLENGE_SECONDS = 120
ISSUANCE_LIMIT = 5


class DeviceRegistrationError(Exception):
    def __init__(self, status, code, message):
        self.status, self.code, self.message = status, code, message
        super().__init__(message)


class DeviceRegistrationService:
    def __init__(self, context):
        self.context = context

    def event(self, db, student, action, outcome, code, registration_id=None, device_id=None):
        db.add(DeviceRegistrationEvent(student_id=student.student_id, action=action,
            outcome=outcome, code=code, registration_id=registration_id,
            device_id=device_id, occurred_at=self.context.now()))

    def deny(self, db, student, action, status, code, message, registration_id=None):
        self.event(db, student, action, "failed", code, registration_id)
        # Router converts this to a response so get_db commits the failure audit.
        raise DeviceRegistrationError(status, code, message)

    def lock_identity(self, db, student, auth, action):
        # Shared student lock also serializes registration with existing login/logout.
        current = db.scalar(select(Student).where(Student.student_id == student.student_id)
                            .with_for_update().execution_options(populate_existing=True))
        session = db.scalar(select(AuthSession).where(AuthSession.token_hash == auth.token_hash)
                            .with_for_update().execution_options(populate_existing=True))
        if current.account_status != "active" or session is None or session.expires_at <= self.context.now():
            self.deny(db, current, action, 401, "SESSION_EXPIRED", "Please sign in again.")
        return current

    def current(self, db, student):
        device = db.scalar(select(RegisteredDevice).where(RegisteredDevice.student_id == student.student_id))
        return {"success": True, "device": self.info(device) if device else None}

    def info(self, device):
        return dict(device_id=device.device_id, device_name=device.device_name,
            device_model=device.device_model, platform=device.platform, status=device.status,
            public_key_fingerprint=device.public_key_fingerprint,
            registered_at=iso_time(device.registered_at, self.context.settings))

    def begin(self, db, student, auth, data):
        student = self.lock_identity(db, student, auth, "challenge")
        if db.scalar(select(RegisteredDevice).where(RegisteredDevice.student_id == student.student_id)):
            self.deny(db, student, "challenge", 409, "DEVICE_ALREADY_REGISTERED",
                      "A device is already registered. Replacement is not available in Phase 1.")
        recent = db.scalar(select(func.count()).select_from(DeviceRegistrationEvent).where(
            DeviceRegistrationEvent.student_id == student.student_id,
            DeviceRegistrationEvent.action == "challenge",
            DeviceRegistrationEvent.outcome == "success",
            DeviceRegistrationEvent.occurred_at > self.context.now() - timedelta(minutes=5)))
        if recent >= ISSUANCE_LIMIT:
            self.deny(db, student, "challenge", 429, "REGISTRATION_RATE_LIMITED",
                      "Too many registration challenges. Try again in five minutes.")
        try:
            public_key, fingerprint = canonical_public_key(data.public_key_spki)
        except ValueError as exc:
            self.deny(db, student, "challenge", 422, "INVALID_PUBLIC_KEY", str(exc))
        if db.scalar(select(RegisteredDevice).where(RegisteredDevice.public_key_fingerprint == fingerprint)):
            self.deny(db, student, "challenge", 409, "KEY_ALREADY_REGISTERED",
                      "This installation key is already registered.")
        now = self.context.now()
        expires = min(now + timedelta(seconds=CHALLENGE_SECONDS), auth.expires_at)
        identifier = secrets.token_urlsafe(32)
        payload = json.dumps(dict(version=1, operation="device_registration", registration_id=identifier,
            student_id=student.student_id, public_key_fingerprint=fingerprint,
            nonce=secrets.token_urlsafe(32), expires_at=iso_time(expires, self.context.settings)),
            sort_keys=True, separators=(",", ":"))
        # New challenges supersede older pending registrations for this account.
        for old in db.scalars(select(DeviceRegistrationChallenge).where(
                DeviceRegistrationChallenge.student_id == student.student_id,
                DeviceRegistrationChallenge.consumed_at.is_(None)).with_for_update()):
            old.consumed_at = now
        db.add(DeviceRegistrationChallenge(registration_id=identifier, student_id=student.student_id,
            auth_token_hash=auth.token_hash, public_key_spki=public_key, public_key_fingerprint=fingerprint,
            device_name=data.device_name, device_model=data.device_model, signing_payload=payload,
            created_at=now, expires_at=expires))
        self.event(db, student, "challenge", "success", "CHALLENGE_ISSUED", identifier)
        return dict(success=True, registration_id=identifier, algorithm="ECDSA_P256_SHA256",
            signature_encoding="base64-DER", signing_payload=base64.b64encode(payload.encode()).decode(),
            expires_at=iso_time(expires, self.context.settings))

    def confirm(self, db, student, auth, data):
        student = self.lock_identity(db, student, auth, "confirm")
        challenge = db.scalar(select(DeviceRegistrationChallenge).where(
            DeviceRegistrationChallenge.registration_id == data.registration_id).with_for_update()
            .execution_options(populate_existing=True))
        if (challenge is None or challenge.student_id != student.student_id
                or challenge.auth_token_hash != auth.token_hash):
            self.deny(db, student, "confirm", 404, "REGISTRATION_NOT_FOUND",
                      "Registration challenge not found.")
        identifier = challenge.registration_id
        if challenge.consumed_at is not None:
            self.deny(db, student, "confirm", 409, "CHALLENGE_CONSUMED",
                      "This registration challenge has already ended.", identifier)
        now = self.context.now()
        challenge.consumed_at = now
        if challenge.expires_at <= now:
            self.deny(db, student, "confirm", 410, "CHALLENGE_EXPIRED",
                      "Registration timed out. Start registration again.", identifier)
        if db.scalar(select(RegisteredDevice).where(RegisteredDevice.student_id == student.student_id)):
            self.deny(db, student, "confirm", 409, "DEVICE_ALREADY_REGISTERED",
                      "A device is already registered.", identifier)
        if not verify_signature(challenge.public_key_spki, challenge.signing_payload, data.signature):
            self.deny(db, student, "confirm", 403, "INVALID_SIGNATURE",
                      "The device signature could not be verified. Start registration again.", identifier)
        device = RegisteredDevice(device_id=secrets.token_urlsafe(32), student_id=student.student_id,
            public_key_spki=challenge.public_key_spki, public_key_fingerprint=challenge.public_key_fingerprint,
            device_name=challenge.device_name, device_model=challenge.device_model,
            platform="android", status="ACTIVE", registered_at=now)
        try:
            # The savepoint preserves the failure audit and consumed nonce on a key race.
            with db.begin_nested():
                db.add(device)
                db.flush()
        except IntegrityError:
            self.deny(db, student, "confirm", 409, "DEVICE_REGISTRATION_CONFLICT",
                      "The device or installation key has already been registered.", identifier)
        self.event(db, student, "confirm", "success", "DEVICE_REGISTERED", identifier, device.device_id)
        return {"success": True, "device": self.info(device)}
