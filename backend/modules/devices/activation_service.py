"""Authenticated activation workflow; genuine institutional trust is mandatory.

The default provider always rejects. Untrusted B3 results never grant authority.
Caller owns the outer transaction and must commit rejection audits/nonce use,
as registration_response/get_db do; never catch an error and commit partial success.
"""
import hashlib
import base64
import json
import secrets
from datetime import timedelta
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from models import AuthSession
from config import iso_time
from .activation_models import DeviceActivationChallenge, DeviceActivationEvent
from .approval_provider import (ApprovalBinding, TrustedTemplateRevision, TrustedBiometricResult,
    trusted_approval_provider, validate_approval)
from .biometric_models import DeviceBiometricSession
from .crypto import canonical_public_key, verify_signature
from .models import RegisteredDevice
from .pending_service import PendingEnrollmentService
from .service import DeviceRegistrationError


class DeviceActivationService(PendingEnrollmentService):
    def issue(self, db, student, auth, pending_id, approval_id):
        return self._issue_transaction(db,student,auth,pending_id,approval_id)

    def confirm(self, db, student, auth, pending_id, challenge_id, approval_id, signature):
        return self._confirm_transaction(db,student,auth,pending_id,challenge_id,approval_id,signature)

    def readiness(self,db,student,auth,pending_id):
        def operation(state):
            nonlocal student,auth
            student,auth=self._identity(db,student,auth)
            pending=self.owned(db,student,auth,pending_id);state['pending_id']=pending_id
            self._candidate(db,student,pending)
            provider=trusted_approval_provider()
            approval=provider.find_fresh_approval(db,self._binding(student,auth,pending),self.context.now())
            if approval is None:self._reject(403,'BIOMETRIC_TRUST_REQUIRED','A fresh trusted server approval is required. Untrusted biometric checks cannot activate this device.')
            approval=self._approval(provider,db,student,auth,pending,approval.approval_id)
            self._event(db,student,'readiness','ISSUED','TRUSTED_APPROVAL_ELIGIBLE',state)
            return dict(success=True,status='ELIGIBLE',pending_registration_id=pending_id,
                candidate_device_id=pending.candidate_device_id,public_key_fingerprint=pending.public_key_fingerprint,
                operation=pending.operation,slot_number=pending.slot_number,approval_id=approval.approval_id,
                trusted_template_revision_id=approval.trusted_template_revision_id,
                biometric_result_id=approval.biometric_result_id,expires_at=iso_time(approval.expires_at,self.context.settings))
        return self._attempt(db,student,'readiness',operation)

    def status(self,db,student,auth,pending_id):
        def operation(state):
            nonlocal student,auth
            student,auth=self._identity(db,student,auth)
            pending=self.owned(db,student,auth,pending_id);state['pending_id']=pending_id
            device=db.scalar(select(RegisteredDevice).where(RegisteredDevice.device_id==pending.candidate_device_id,
                RegisteredDevice.student_id==student.student_id).with_for_update())
            active=(pending.status=='ACTIVATED' and pending.consumed_at is not None and device is not None
                and device.status=='ACTIVE' and device.slot_number==pending.slot_number and device.public_key_fingerprint==pending.public_key_fingerprint)
            return dict(success=True,status='ACTIVE' if active else ('EXPIRED' if pending.status=='EXPIRED' else 'NOT_ACTIVE'),
                pending_registration_id=pending_id,candidate_device_id=pending.candidate_device_id,
                public_key_fingerprint=pending.public_key_fingerprint,operation=pending.operation,slot_number=pending.slot_number,
                device=self.info_device(device) if active else None,
                active_count=len(self.active_devices(db,student)),maximum_active_devices=2,attendance_authorized=False)
        return self._attempt(db,student,'status',operation)

    def _event(self, db, student, action, result, code, state):
        db.add(DeviceActivationEvent(student_id=student.student_id, action=action,
            result=result, code=code, occurred_at=self.context.now(),
            pending_registration_id=state.get("pending_id"),
            challenge_id=state.get("challenge_id")))

    def _attempt(self, db, student, action, operation):
        state={}
        try:
            return operation(state)
        except DeviceRegistrationError as exc:
            challenge=state.get("challenge")
            if challenge is not None and challenge.consumed_at is None:
                challenge.consumed_at=self.context.now()
                challenge.result="FAIL"; challenge.failure_code=exc.code
            if challenge is not None and state.get("submitted"):
                challenge.failure_code=exc.code
            self._event(db, student, action, "FAIL", exc.code, state)
            db.flush()
            raise

    @staticmethod
    def _reject(status, code, message):
        raise DeviceRegistrationError(status, code, message)

    def _identity(self, db, student, auth):
        student=self.lock_identity(db, student, auth, "activation")
        current=db.scalar(select(AuthSession).where(AuthSession.token_hash==auth.token_hash)
            .with_for_update().execution_options(populate_existing=True))
        if current.student_id!=student.student_id:
            self._reject(401,"SESSION_MISMATCH","This login does not belong to the student.")
        return student,current

    def _candidate(self, db, student, pending):
        if pending.expires_at<=self.context.now():
            self._reject(410,"PENDING_EXPIRED","Candidate preparation expired.")
        if pending.status!="KEY_PROVEN" or pending.consumed_at is not None or pending.key_proven_at is None:
            self._reject(409,"CANDIDATE_PROOF_REQUIRED","A current KEY_PROVEN candidate is required.")
        if pending.operation not in ("enroll_second_device","replace_device") or pending.slot_number not in (1,2):
            self._reject(403,"ACTIVATION_BINDING_MISMATCH","Candidate operation or slot changed.")
        slot_one=self.check_target(db,student,pending)
        if slot_one.device_id!=pending.slot_one_device_id:
            self._reject(409,"DEVICE_STATE_CHANGED","The initial registration changed.")
        try: _,fingerprint=canonical_public_key(pending.public_key_spki)
        except ValueError: fingerprint=None
        if fingerprint!=pending.public_key_fingerprint:
            self._reject(403,"CANDIDATE_KEY_INVALID","Candidate public-key binding is invalid.")
        if db.scalar(select(RegisteredDevice.device_id).where(
                RegisteredDevice.public_key_fingerprint==fingerprint)):
            self._reject(409,"KEY_ALREADY_REGISTERED","Candidate key is already registered.")

    @staticmethod
    def _binding(student,auth,pending):
        return ApprovalBinding(student.student_id,auth.token_hash,pending.pending_registration_id,
            pending.candidate_device_id,pending.public_key_fingerprint,pending.slot_number,pending.operation,
            pending.slot_one_device_id if pending.operation=="replace_device" else None,pending.replaced_device_fingerprint)

    def _approval(self,provider,db,student,auth,pending,approval_id,expected_revision=None):
        binding=self._binding(student,auth,pending);now=self.context.now()
        approval=validate_approval(provider.validate_and_lock(db,approval_id,binding,now),approval_id,binding,now)
        if expected_revision is not None and approval.trusted_template_revision_id!=expected_revision:
            self._reject(403,'APPROVAL_REVISION_CHANGED','Trusted template revision changed after issuance.')
        if not approval.biometric_result_id or db.get(DeviceBiometricSession,approval.biometric_result_id) is not None:
            self._reject(403,'BIOMETRIC_TRUST_REQUIRED','COMPLETED_UNTRUSTED is never an activation approval.')
        revision=provider.current_template_revision(db,student.student_id,now)
        if not isinstance(revision,TrustedTemplateRevision) or not revision.trusted or revision.invalidated_at is not None:
            self._reject(403,'BIOMETRIC_TRUST_REQUIRED','An institution-approved current template revision is required.')
        provider.validate_template_trust(db,revision,now)
        if (revision.student_id!=student.student_id or student.biometric_status!='active' or not student.face_encoding
                or revision.template_hash!=hashlib.sha256(student.face_encoding.encode()).hexdigest()):
            self._reject(403,'BIOMETRIC_TRUST_REQUIRED','Current template provenance is invalid.')
        if revision.revision_id!=approval.trusted_template_revision_id:
            self._reject(403,'APPROVAL_REVISION_CHANGED','Trusted template revision changed.')
        result=provider.validate_fresh_result(db,approval,binding,revision,now)
        if (not isinstance(result,TrustedBiometricResult) or result.result_id!=approval.biometric_result_id
                or result.binding!=binding or result.trusted_template_revision_id!=revision.revision_id
                or result.classification!='TRUSTED_SERVER_RESULT' or not result.face_verified or not result.liveness_verified):
            self._reject(403,'BIOMETRIC_TRUST_REQUIRED','A genuine bound trusted server biometric result is required.')
        if (result.verified_at!=approval.verified_at or result.verified_at>now
                or result.verified_at<now-timedelta(seconds=60) or result.expires_at<=now
                or approval.expires_at>result.expires_at or result.expires_at>result.verified_at+timedelta(seconds=60)):
            self._reject(410,'APPROVAL_EXPIRED','Trusted biometric result is expired or mismatched.')
        return approval

    def _issue_transaction(self,db,student,auth,pending_id,approval_id):
        """Shared transaction core; production provider currently unavailable."""
        def operation(state):
            nonlocal student,auth
            student,auth=self._identity(db,student,auth)
            pending=self.owned(db,student,auth,pending_id);state["pending_id"]=pending_id
            self._candidate(db,student,pending)
            provider=trusted_approval_provider()
            approval=self._approval(provider,db,student,auth,pending,approval_id)
            now=self.context.now()
            old=db.scalars(select(DeviceActivationChallenge).where(
                DeviceActivationChallenge.pending_registration_id==pending_id,
                DeviceActivationChallenge.consumed_at==None).with_for_update()).all()
            for challenge in old:
                if challenge.expires_at<=now:
                    challenge.result="FAIL";challenge.consumed_at=now;challenge.failure_code="ACTIVATION_EXPIRED"
                    self._event(db,student,"expire","FAIL","ACTIVATION_EXPIRED",
                        dict(pending_id=pending_id,challenge_id=challenge.challenge_id))
                elif (challenge.approval_id==approval_id and challenge.trusted_template_revision_id==approval.trusted_template_revision_id
                        and challenge.student_id==student.student_id and challenge.auth_token_hash==auth.token_hash
                        and challenge.candidate_device_id==pending.candidate_device_id
                        and challenge.public_key_fingerprint==pending.public_key_fingerprint
                        and challenge.operation==pending.operation and challenge.slot_number==pending.slot_number):
                    return self._challenge_info(challenge)
                else:self._reject(409,"ACTIVATION_PENDING","Another activation challenge is still pending.")
            db.flush()
            recent=db.scalar(select(func.count()).select_from(DeviceActivationEvent).where(
                DeviceActivationEvent.student_id==student.student_id,DeviceActivationEvent.result=="ISSUED",DeviceActivationEvent.action=="challenge",
                DeviceActivationEvent.occurred_at>now-timedelta(minutes=5)))
            if recent>=5:self._reject(429,"ACTIVATION_RATE_LIMITED","Too many activation challenges.")
            identifier=secrets.token_urlsafe(32)
            expires=min(now+timedelta(seconds=60),pending.expires_at,auth.expires_at,approval.expires_at).replace(microsecond=0)
            if expires<=now:self._reject(410,"ACTIVATION_EXPIRED","Activation prerequisites expired.")
            payload=json.dumps(dict(version=1,purpose="device_activation",operation=pending.operation,slot_number=pending.slot_number,
                challenge_id=identifier,student_id=student.student_id,auth_session_hash=auth.token_hash,
                pending_registration_id=pending_id,candidate_device_id=pending.candidate_device_id,
                public_key_fingerprint=pending.public_key_fingerprint,approval_id=approval_id,
                trusted_template_revision_id=approval.trusted_template_revision_id,biometric_result_id=approval.biometric_result_id,
                replaced_device_id=approval.binding.replaced_device_id,replaced_device_fingerprint=approval.binding.replaced_device_fingerprint,
                nonce=secrets.token_urlsafe(32),expires_at=iso_time(expires,self.context.settings)),sort_keys=True,separators=(",",":"))
            challenge=DeviceActivationChallenge(challenge_id=identifier,student_id=student.student_id,
                auth_token_hash=auth.token_hash,pending_registration_id=pending_id,candidate_device_id=pending.candidate_device_id,
                public_key_fingerprint=pending.public_key_fingerprint,approval_id=approval_id,
                trusted_template_revision_id=approval.trusted_template_revision_id,operation=pending.operation,slot_number=pending.slot_number,
                signing_payload=payload,created_at=now,expires_at=expires,result="PENDING")
            db.add(challenge);db.flush();state["challenge_id"]=identifier
            self._event(db,student,"challenge","ISSUED","ACTIVATION_CHALLENGE_ISSUED",state)
            return self._challenge_info(challenge)
        return self._attempt(db,student,"challenge",operation)

    def _challenge_info(self,challenge):
        return dict(success=True,challenge_id=challenge.challenge_id,
            pending_registration_id=challenge.pending_registration_id,
            candidate_device_id=challenge.candidate_device_id,public_key_fingerprint=challenge.public_key_fingerprint,
            operation=challenge.operation,slot_number=challenge.slot_number,approval_id=challenge.approval_id,
            trusted_template_revision_id=challenge.trusted_template_revision_id,
            biometric_result_id=json.loads(challenge.signing_payload)["biometric_result_id"],
            algorithm="ECDSA_P256_SHA256",signature_encoding="base64-DER",
            signing_payload=base64.b64encode(challenge.signing_payload.encode()).decode(),
            expires_at=iso_time(challenge.expires_at,self.context.settings))

    def _confirm_transaction(self,db,student,auth,pending_id,challenge_id,approval_id,signature):
        def operation(state):
            nonlocal student,auth
            student,auth=self._identity(db,student,auth)
            pending=self.owned(db,student,auth,pending_id);state["pending_id"]=pending_id
            challenge=db.scalar(select(DeviceActivationChallenge).where(
                DeviceActivationChallenge.challenge_id==challenge_id).with_for_update()
                .execution_options(populate_existing=True))
            if challenge is None or challenge.student_id!=student.student_id or challenge.auth_token_hash!=auth.token_hash or challenge.pending_registration_id!=pending_id:
                self._reject(404,"ACTIVATION_NOT_FOUND","Activation challenge not found for this login and candidate.")
            state.update(challenge=challenge,challenge_id=challenge_id)
            if challenge.consumed_at is not None:self._reject(409,"ACTIVATION_REPLAYED","Activation challenge already consumed.")
            if challenge.expires_at<=self.context.now():self._reject(410,"ACTIVATION_EXPIRED","Activation challenge expired.")
            self._candidate(db,student,pending)
            if (challenge.candidate_device_id!=pending.candidate_device_id or challenge.public_key_fingerprint!=pending.public_key_fingerprint
                    or challenge.operation!=pending.operation or challenge.slot_number!=pending.slot_number or challenge.approval_id!=approval_id):
                self._reject(403,"ACTIVATION_BINDING_MISMATCH","Activation binding changed.")
            # Every owned submitted attempt consumes its nonce, including failures.
            state["submitted"]=True
            challenge.consumed_at=self.context.now();challenge.result="FAIL"
            if not verify_signature(pending.public_key_spki,challenge.signing_payload,signature):
                self._reject(403,"INVALID_ACTIVATION_SIGNATURE","Fresh candidate-key signature is invalid.")
            provider=trusted_approval_provider()
            approval=self._approval(provider,db,student,auth,pending,approval_id,challenge.trusted_template_revision_id)
            if approval.trusted_template_revision_id!=challenge.trusted_template_revision_id:
                self._reject(403,"APPROVAL_REVISION_CHANGED","Trusted template revision changed.")
            if json.loads(challenge.signing_payload).get('biometric_result_id')!=approval.biometric_result_id:
                self._reject(403,'APPROVAL_MISMATCH','Trusted biometric result changed after challenge issuance.')
            def fresh():
                now=self.context.now()
                if min(challenge.expires_at,pending.expires_at,auth.expires_at,approval.expires_at)<=now:
                    self._reject(410,"ACTIVATION_EXPIRED","Activation expired while processing.")
            fresh()
            try:
                with db.begin_nested():
                    # Provider MUST lock current revision + grant and consume in this same DB transaction.
                    provider.consume(db,approval,self.context.now())
                    fresh()
                    if pending.operation=="replace_device":
                        target=self.check_target(db,student,pending)
                        target.status="REVOKED";target.revoked_at=self.context.now()
                        target.revocation_reason="Approved replacement " + pending.pending_registration_id
                        db.flush()  # Release only the target ACTIVE slot inside the savepoint.
                    device=RegisteredDevice(device_id=pending.candidate_device_id,student_id=student.student_id,
                        slot_number=pending.slot_number,public_key_spki=pending.public_key_spki,public_key_fingerprint=pending.public_key_fingerprint,
                        device_name=pending.device_name,device_model=pending.device_model,platform="android",status="ACTIVE",registered_at=self.context.now())
                    db.add(device);pending.status="ACTIVATED";pending.consumed_at=self.context.now()
                    self.audit(db,student,"activation","PASS",("DEVICE_REPLACED" if pending.operation=="replace_device" else "SECOND_DEVICE_ACTIVATED"),pending)
                    self._event(db,student,"activate","PASS",("DEVICE_REPLACED" if pending.operation=="replace_device" else "SECOND_DEVICE_ACTIVATED"),state)
                    db.flush();fresh()
            except IntegrityError:
                self._reject(409,"ACTIVATION_CONFLICT","Slot or candidate registration changed concurrently.")
            challenge.result="PASS";challenge.failure_code=None
            return dict(success=True,device=self.info_device(device),attendance_authorized=False)
        return self._attempt(db,student,"activate",operation)

    def info_device(self,device):
        from .service import DeviceRegistrationService
        return DeviceRegistrationService.info(self,device)
