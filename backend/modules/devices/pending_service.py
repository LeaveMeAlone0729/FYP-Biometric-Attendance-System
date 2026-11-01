"""Pending second-device preparation. No biometrics or attendance dependencies."""
import base64
import json
import secrets
from datetime import timedelta
from sqlalchemy import case, func, select
from sqlalchemy.exc import IntegrityError
from config import iso_time
from .crypto import canonical_public_key, verify_signature
from .models import RegisteredDevice
from .pending_models import PendingDeviceRegistration, DeviceEnrollmentEvent
from .service import DeviceRegistrationService, DeviceRegistrationError

OPERATION = "enroll_second_device"
OPEN = ("CHALLENGE_ISSUED", "KEY_PROVEN")


class PendingEnrollmentService(DeviceRegistrationService):
    def audit(self, db, student, action, result, code, pending=None):
        db.add(DeviceEnrollmentEvent(student_id=student.student_id,
            pending_registration_id=pending.pending_registration_id if pending else None,
            action=action, result=result, code=code, occurred_at=self.context.now()))

    def refuse(self, db, student, action, status, code, message, pending=None):
        self.audit(db, student, action, "FAIL", code, pending)
        raise DeviceRegistrationError(status, code, message)

    def capacity(self, db, student):
        rows = db.scalars(select(RegisteredDevice).where(
            RegisteredDevice.student_id == student.student_id).with_for_update()).all()
        active = [r for r in rows if r.status == "ACTIVE"]
        if len(active) >= 2:
            self.refuse(db, student, "prepare", 409, "DEVICE_LIMIT_REACHED", "Two trusted devices are already active.")
        # Stage B2 never turns a historical slot into a replacement shortcut.
        if any(r.slot_number == 2 for r in rows):
            self.refuse(db, student, "prepare", 409, "REPLACEMENT_REQUIRED", "Slot 2 has registration history. Use the approved replacement workflow for the occupied slot.")
        if len(active) != 1 or active[0].slot_number != 1:
            self.refuse(db, student, "prepare", 409, "INITIAL_REGISTRATION_REQUIRED", "An active initial Slot 1 registration is required.")
        return active[0]

    def check_target(self, db, student, pending):
        if pending.operation == "enroll_second_device":
            return self.capacity(db, student)
        if pending.operation != "replace_device" or pending.slot_number not in (1,2):
            self.refuse(db,student,"target",403,"REPLACEMENT_BINDING_MISMATCH","Invalid replacement operation.",pending)
        signed=json.loads(pending.signing_payload)
        if any(signed.get(k)!=v for k,v in {"operation":pending.operation,"slot_number":pending.slot_number,
                "replaced_device_id":pending.slot_one_device_id,"replaced_device_fingerprint":pending.replaced_device_fingerprint,
                "candidate_device_id":pending.candidate_device_id,"public_key_fingerprint":pending.public_key_fingerprint}.items()):
            self.refuse(db,student,"target",403,"REPLACEMENT_BINDING_MISMATCH","Replacement target binding changed.",pending)
        target=db.scalar(select(RegisteredDevice).where(RegisteredDevice.device_id==pending.slot_one_device_id).with_for_update().execution_options(populate_existing=True))
        if (target is None or target.student_id!=student.student_id or target.status!="ACTIVE"
                or target.slot_number!=pending.slot_number or target.public_key_fingerprint!=pending.replaced_device_fingerprint):
            self.refuse(db,student,"target",409,"REPLACEMENT_TARGET_CHANGED","The selected device changed. Start a new replacement request.",pending)
        return target

    def expire(self, db, student, pending):
        now = self.context.now()
        if pending.status in OPEN and (pending.expires_at <= now or
                (pending.status == "CHALLENGE_ISSUED" and pending.challenge_expires_at <= now)):
            pending.status = "EXPIRED"
            pending.challenge_consumed_at = pending.challenge_consumed_at or now
            self.audit(db, student, "expire", "INFO", "PENDING_EXPIRED", pending)
            db.flush()

    def info(self, pending, include_payload=False):
        return dict(success=True, pending_registration_id=pending.pending_registration_id,
            candidate_device_id=pending.candidate_device_id, slot_number=pending.slot_number, operation=pending.operation,
            replaced_device_id=pending.slot_one_device_id if pending.operation=="replace_device" else None,
            replaced_device_fingerprint=pending.replaced_device_fingerprint,
            public_key_fingerprint=pending.public_key_fingerprint, status=pending.status,
            algorithm="ECDSA_P256_SHA256", signature_encoding="base64-DER",
            signing_payload=base64.b64encode(pending.signing_payload.encode()).decode() if include_payload and pending.status == "CHALLENGE_ISSUED" else None,
            challenge_expires_at=iso_time(pending.challenge_expires_at, self.context.settings),
            expires_at=iso_time(pending.expires_at, self.context.settings),
            key_proven_at=iso_time(pending.key_proven_at, self.context.settings),
            activation_enabled=False, biometric_approval_status="UNAVAILABLE", attendance_authorized=False)

    def owned(self, db, student, auth, identifier):
        pending = db.scalar(select(PendingDeviceRegistration).where(
            PendingDeviceRegistration.pending_registration_id == identifier).with_for_update()
            .execution_options(populate_existing=True))
        if pending is None or pending.student_id != student.student_id or pending.auth_token_hash != auth.token_hash:
            self.refuse(db, student, "lookup", 404, "PENDING_NOT_FOUND", "Pending registration not found for this login.")
        self.expire(db, student, pending)
        return pending

    def begin_pending(self, db, student, auth, data):
        student = self.lock_identity(db, student, auth, "pending")
        slot_one = self.capacity(db, student)
        try:
            public, fingerprint = canonical_public_key(data.public_key_spki)
        except ValueError as exc:
            self.refuse(db, student, "prepare", 422, "INVALID_PUBLIC_KEY", str(exc))
        if db.scalar(select(RegisteredDevice).where(RegisteredDevice.public_key_fingerprint == fingerprint)):
            self.refuse(db, student, "prepare", 409, "KEY_ALREADY_REGISTERED", "This key is already registered. Use a different installation; do not rotate its key.")
        open_rows = db.scalars(select(PendingDeviceRegistration).where(
            PendingDeviceRegistration.student_id == student.student_id,
            PendingDeviceRegistration.status.in_(OPEN)).with_for_update()).all()
        for old in open_rows:
            self.expire(db, student, old)
            if old.status in OPEN:
                if (old.auth_token_hash == auth.token_hash and old.public_key_fingerprint == fingerprint
                        and old.operation == OPERATION and old.slot_number == 2 and old.slot_one_device_id == slot_one.device_id):
                    # Recover a lost response without issuing a new challenge or resetting expiry.
                    return self.info(old, include_payload=True)
                self.refuse(db, student, "prepare", 409, "PENDING_EXISTS", "Another pending enrollment exists. Wait for its expiry before starting again.")
        now = self.context.now()
        recent = db.scalar(select(func.count()).select_from(DeviceEnrollmentEvent).where(
            DeviceEnrollmentEvent.student_id == student.student_id, DeviceEnrollmentEvent.code == "PENDING_CREATED",
            DeviceEnrollmentEvent.occurred_at > now - timedelta(minutes=5)))
        if recent >= 5:
            self.refuse(db, student, "prepare", 429, "ENROLLMENT_RATE_LIMITED", "Too many enrollment attempts. Try again in five minutes.")
        identifier, candidate = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        expires = min(now + timedelta(minutes=5), auth.expires_at)
        challenge_expires = min(now + timedelta(seconds=120), expires)
        payload = json.dumps(dict(version=1, operation=OPERATION, slot_number=2,
            pending_registration_id=identifier, candidate_device_id=candidate,
            student_id=student.student_id, auth_session_hash=auth.token_hash,
            public_key_fingerprint=fingerprint, nonce=secrets.token_urlsafe(32),
            expires_at=iso_time(challenge_expires, self.context.settings)), sort_keys=True, separators=(",", ":"))
        pending = PendingDeviceRegistration(pending_registration_id=identifier, candidate_device_id=candidate,
            student_id=student.student_id, auth_token_hash=auth.token_hash, slot_one_device_id=slot_one.device_id,
            slot_number=2, operation=OPERATION, public_key_spki=public, public_key_fingerprint=fingerprint,
            device_name=data.device_name, device_model=data.device_model, signing_payload=payload,
            status="CHALLENGE_ISSUED", created_at=now, expires_at=expires, challenge_expires_at=challenge_expires)
        try:
            with db.begin_nested():
                db.add(pending); db.flush()
        except IntegrityError:
            self.refuse(db, student, "prepare", 409, "PENDING_EXISTS", "Another pending enrollment already exists.")
        self.audit(db, student, "prepare", "ISSUED", "PENDING_CREATED", pending)
        return self.info(pending, include_payload=True)

    def proof(self, db, student, auth, identifier, signature):
        student = self.lock_identity(db, student, auth, "pending_proof")
        pending = self.owned(db, student, auth, identifier)
        if pending.status == "EXPIRED":
            self.refuse(db, student, "proof", 410, "CHALLENGE_EXPIRED", "Candidate proof expired. Start preparation again using the same local key.", pending)
        if pending.status != "CHALLENGE_ISSUED" or pending.challenge_consumed_at is not None:
            self.refuse(db, student, "proof", 409, "CHALLENGE_CONSUMED", "This candidate challenge has already ended.", pending)
        pending.challenge_consumed_at = self.context.now()
        pending.status = "FAILED"  # Every submitted signature consumes the challenge, including failures.
        slot_one = self.check_target(db, student, pending)
        if slot_one.device_id != pending.slot_one_device_id:
            self.refuse(db, student, "proof", 409, "DEVICE_STATE_CHANGED", "The initial registration has changed.", pending)
        if not verify_signature(pending.public_key_spki, pending.signing_payload, signature):
            self.refuse(db, student, "proof", 403, "INVALID_SIGNATURE", "The candidate signature could not be verified.", pending)
        pending.status = "KEY_PROVEN"
        pending.key_proven_at = self.context.now()
        self.audit(db, student, "proof", "PASS", "CANDIDATE_KEY_PROVEN", pending)
        return self.info(pending)

    def current_pending(self, db, student, auth):
        student = self.lock_identity(db, student, auth, "pending_status")
        pending = db.scalar(select(PendingDeviceRegistration).where(
            PendingDeviceRegistration.student_id == student.student_id,
            PendingDeviceRegistration.auth_token_hash == auth.token_hash).order_by(
            case((PendingDeviceRegistration.status.in_(OPEN), 1), else_=0).desc(),
            PendingDeviceRegistration.created_at.desc(), PendingDeviceRegistration.pending_registration_id.desc()).limit(1).with_for_update())
        if pending: self.expire(db, student, pending)
        return dict(success=True, pending=self.info(pending, include_payload=True) if pending else None)

    def status(self, db, student, auth, identifier):
        student = self.lock_identity(db, student, auth, "pending_status")
        return self.info(self.owned(db, student, auth, identifier), include_payload=True)
