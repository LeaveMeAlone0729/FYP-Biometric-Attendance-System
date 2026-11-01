"""Replacement preparation; reuses proof, biometrics and atomic activation."""
import json
import secrets
from datetime import timedelta
from sqlalchemy import select, func
from .pending_service import PendingEnrollmentService, OPEN
from .pending_models import PendingDeviceRegistration, DeviceEnrollmentEvent
from .models import RegisteredDevice
from .crypto import canonical_public_key
from config import iso_time

class DeviceReplacementService(PendingEnrollmentService):
    def begin_replacement(self,db,student,auth,data):
        student=self.lock_identity(db,student,auth,"replacement")
        target=db.scalar(select(RegisteredDevice).where(RegisteredDevice.device_id==data.old_device_id,
            RegisteredDevice.student_id==student.student_id,RegisteredDevice.slot_number==data.slot_number,
            RegisteredDevice.status=="ACTIVE").with_for_update())
        if target is None:self.refuse(db,student,"replace_prepare",404,"REPLACEMENT_TARGET_NOT_FOUND","No ACTIVE device matches this slot and student.")
        try:public,fingerprint=canonical_public_key(data.public_key_spki)
        except ValueError as exc:self.refuse(db,student,"replace_prepare",422,"INVALID_PUBLIC_KEY",str(exc))
        if db.scalar(select(RegisteredDevice.device_id).where(RegisteredDevice.public_key_fingerprint==fingerprint)):
            self.refuse(db,student,"replace_prepare",409,"KEY_ALREADY_REGISTERED","Use the new installation's distinct retained key. Never rotate an existing registered key.")
        for old in db.scalars(select(PendingDeviceRegistration).where(PendingDeviceRegistration.student_id==student.student_id,PendingDeviceRegistration.status.in_(OPEN)).with_for_update()).all():
            self.expire(db,student,old)
            if old.status in OPEN:
                if (old.auth_token_hash==auth.token_hash and old.operation=="replace_device" and old.slot_number==data.slot_number
                        and old.slot_one_device_id==target.device_id and old.replaced_device_fingerprint==target.public_key_fingerprint and old.public_key_fingerprint==fingerprint):
                    return self.info(old,include_payload=True)
                self.refuse(db,student,"replace_prepare",409,"PENDING_EXISTS","Cancel or wait for the existing pending request to expire.")
        now=self.context.now()
        recent=db.scalar(select(func.count()).select_from(DeviceEnrollmentEvent).where(DeviceEnrollmentEvent.student_id==student.student_id,
            DeviceEnrollmentEvent.action=="replace_prepare",DeviceEnrollmentEvent.result=="ISSUED",DeviceEnrollmentEvent.occurred_at>now-timedelta(minutes=5)))
        if recent>=5:self.refuse(db,student,"replace_prepare",429,"REPLACEMENT_RATE_LIMITED","Too many replacement requests. Try again later.")
        identifier,candidate=secrets.token_urlsafe(32),secrets.token_urlsafe(32)
        expires=min(now+timedelta(minutes=5),auth.expires_at);challenge_expires=min(now+timedelta(seconds=120),expires)
        payload=json.dumps(dict(version=1,operation="replace_device",slot_number=target.slot_number,
            pending_registration_id=identifier,candidate_device_id=candidate,student_id=student.student_id,auth_session_hash=auth.token_hash,
            public_key_fingerprint=fingerprint,replaced_device_id=target.device_id,replaced_device_fingerprint=target.public_key_fingerprint,
            nonce=secrets.token_urlsafe(32),expires_at=iso_time(challenge_expires,self.context.settings)),sort_keys=True,separators=(",",":"))
        pending=PendingDeviceRegistration(pending_registration_id=identifier,candidate_device_id=candidate,student_id=student.student_id,
            auth_token_hash=auth.token_hash,slot_one_device_id=target.device_id,replaced_device_fingerprint=target.public_key_fingerprint,
            slot_number=target.slot_number,operation="replace_device",public_key_spki=public,public_key_fingerprint=fingerprint,
            device_name=data.device_name,device_model=data.device_model,signing_payload=payload,status="CHALLENGE_ISSUED",
            created_at=now,expires_at=expires,challenge_expires_at=challenge_expires)
        db.add(pending);db.flush();self.audit(db,student,"replace_prepare","ISSUED","REPLACEMENT_PENDING",pending)
        return self.info(pending,include_payload=True)

    def cancel(self,db,student,auth,identifier):
        student=self.lock_identity(db,student,auth,"replacement_cancel")
        pending=self.owned(db,student,auth,identifier)
        if pending.status=="ACTIVATED":self.refuse(db,student,"cancel",409,"ALREADY_ACTIVATED","A completed replacement cannot be cancelled.",pending)
        if pending.status in OPEN:
            pending.status="CANCELLED";pending.challenge_consumed_at=pending.challenge_consumed_at or self.context.now()
            self.audit(db,student,"cancel","INFO","PENDING_CANCELLED",pending)
        return self.info(pending)
