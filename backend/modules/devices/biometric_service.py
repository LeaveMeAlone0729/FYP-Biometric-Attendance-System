"""Attendance-free face/liveness checks. Inference reused; trust never conferred."""
import hashlib
import json
import math
import secrets
from datetime import timedelta
from cryptography.fernet import InvalidToken
from sqlalchemy import func, select
from config import iso_time
from modules.biometrics.constants import MAX_IMAGE_BYTES, MAX_LIVENESS_FRAMES, REQUIRED_LIVENESS_FRAMES
from modules.biometrics.inference import BiometricError
from modules.biometrics.templates import decrypt_encoding
from .biometric_diagnostics import trace,adjustment_code
from .biometric_models import DeviceBiometricSession, DeviceBiometricEvent
from .pending_service import PendingEnrollmentService
from .service import DeviceRegistrationError

OPEN=("FACE","LIVENESS")


class DeviceBiometricService(PendingEnrollmentService):
    def bio_event(self,db,student,action,result,code,session=None):
        db.add(DeviceBiometricEvent(student_id=student.student_id,
            approval_id=session.approval_id if session else None,action=action,result=result,
            code=code,occurred_at=self.context.now()))

    def fail(self,db,student,status,code,message,session=None):
        if session and session.stage in OPEN:
            session.stage="EXPIRED" if status==410 else "FAILED"
            session.failure_code=code
        trace("rejected",code=code,status=status)
        self.bio_event(db,student,"biometric", "FAIL",code,session)
        raise DeviceRegistrationError(status,code,message)

    def template(self,db,student,session=None):
        if not student.face_encoding or student.biometric_status!="active":
            self.fail(db,student,409,"BIOMETRIC_TEMPLATE_REQUIRED","An enrolled face template is required for this test.",session)
        binding=hashlib.sha256(student.face_encoding.encode()).hexdigest()
        if session and binding!=session.template_binding:
            self.fail(db,student,409,"TEMPLATE_CHANGED","The enrolled template changed. Start a new biometric test.",session)
        try: reference=decrypt_encoding(student.face_encoding,self.context.settings.biometric_key)
        except (InvalidToken,ValueError,TypeError):
            self.fail(db,student,409,"BIOMETRIC_TEMPLATE_UNAVAILABLE","The enrolled template cannot be used. Contact the project administrator.",session)
        return binding,reference

    def check_pending(self,db,student,auth,identifier):
        pending=self.owned(db,student,auth,identifier)
        if pending.expires_at<=self.context.now() or pending.status=="EXPIRED":
            self.fail(db,student,410,"PENDING_EXPIRED","Pending key preparation has expired.")
        if pending.status!="KEY_PROVEN" or pending.consumed_at is not None:
            self.fail(db,student,409,"CANDIDATE_PROOF_REQUIRED","Complete candidate-key proof before starting biometric checks.")
        slot_one=self.capacity(db,student)
        if slot_one.device_id!=pending.slot_one_device_id:
            self.fail(db,student,409,"DEVICE_STATE_CHANGED","The initial device registration changed.")
        return pending

    def result(self,session,message=None,ready=False,feedback_code=None):
        return dict(success=True,approval_id=session.approval_id,pending_registration_id=session.pending_registration_id,
            candidate_device_id=session.candidate_device_id,public_key_fingerprint=session.public_key_fingerprint,
            operation="enroll_second_device",slot_number=2,stage=session.stage,ready=ready,
            feedback_code=feedback_code or ("FACE_VERIFIED" if session.stage=="LIVENESS" else session.stage),
            face_verified=session.stage in ("LIVENESS","COMPLETED_UNTRUSTED"),
            liveness_verified=session.stage=="COMPLETED_UNTRUSTED",complete=session.stage=="COMPLETED_UNTRUSTED",
            fingers=session.fingers,valid_frames=session.valid_frames,required_frames=REQUIRED_LIVENESS_FRAMES,
            expires_at=iso_time(session.expires_at,self.context.settings),
            expires_in=max(0,int((session.expires_at-self.context.now()).total_seconds())),
            result_classification="UNTRUSTED_TEST_RESULT",trusted=False,activation_eligible=False,
            consumable=False,activation_enabled=False,message=message or (
                "Biometric checks completed — awaiting trusted biometric approval" if session.stage=="COMPLETED_UNTRUSTED"
                else "Center your face in the camera." if session.stage=="FACE" else
                f"Show {session.fingers} finger(s) on one hand, palm toward the camera; keep your face visible."))

    def create(self,db,student,auth,identifier):
        student=self.lock_identity(db,student,auth,"device_biometrics")
        pending=self.check_pending(db,student,auth,identifier)
        binding,_=self.template(db,student)
        now=self.context.now()
        previous=db.scalars(select(DeviceBiometricSession).where(
            DeviceBiometricSession.pending_registration_id==identifier).order_by(DeviceBiometricSession.created_at.desc()).with_for_update()).all()
        for old in previous:
            if old.stage in OPEN and old.expires_at<=now:
                old.stage="EXPIRED";old.failure_code="BIOMETRIC_EXPIRED"
                self.bio_event(db,student,"expiry","FAIL","BIOMETRIC_EXPIRED",old)
            elif old.stage in (*OPEN,"COMPLETED_UNTRUSTED") and old.expires_at>now:
                if (old.student_id!=student.student_id or old.auth_token_hash!=auth.token_hash
                        or old.candidate_device_id!=pending.candidate_device_id or old.public_key_fingerprint!=pending.public_key_fingerprint
                        or old.operation!="enroll_second_device" or old.slot_number!=2):
                    self.fail(db,student,403,"BIOMETRIC_BINDING_MISMATCH","Biometric test binding changed.",old)
                if old.template_binding!=binding:
                    self.fail(db,student,409,"TEMPLATE_CHANGED","The template changed. Start a new pending request.",old)
                return self.result(old)
        db.flush()
        recent=db.scalar(select(func.count()).select_from(DeviceBiometricSession).where(
            DeviceBiometricSession.student_id==student.student_id,DeviceBiometricSession.created_at>now-timedelta(minutes=5)))
        if recent>=5:self.fail(db,student,429,"BIOMETRIC_RATE_LIMITED","Too many biometric tests. Try again in five minutes.")
        session=DeviceBiometricSession(approval_id=secrets.token_urlsafe(32),pending_registration_id=identifier,
            student_id=student.student_id,auth_token_hash=auth.token_hash,candidate_device_id=pending.candidate_device_id,
            public_key_fingerprint=pending.public_key_fingerprint,slot_number=2,operation="enroll_second_device",
            template_binding=binding,stage="FACE",valid_frames=0,frame_count=0,frame_hashes="[]",
            created_at=now,expires_at=min(now+timedelta(seconds=self.context.settings.challenge_seconds),now+timedelta(seconds=90),pending.expires_at,auth.expires_at))
        db.add(session);db.flush()
        self.bio_event(db,student,"create","ISSUED","UNTRUSTED_BIOMETRIC_SESSION_CREATED",session)
        return self.result(session)

    def load(self,db,student,auth,identifier,stage=None):
        student=self.lock_identity(db,student,auth,"device_biometrics")
        session=db.scalar(select(DeviceBiometricSession).where(DeviceBiometricSession.approval_id==identifier).with_for_update().execution_options(populate_existing=True))
        if session is None or session.student_id!=student.student_id or session.auth_token_hash!=auth.token_hash:
            self.fail(db,student,404,"BIOMETRIC_SESSION_NOT_FOUND","Biometric test not found for this login.")
        if session.expires_at<=self.context.now():
            self.fail(db,student,410,"BIOMETRIC_EXPIRED","Biometric test expired. Start a new test.",session)
        pending=self.check_pending(db,student,auth,session.pending_registration_id)
        if (session.candidate_device_id!=pending.candidate_device_id or session.public_key_fingerprint!=pending.public_key_fingerprint
                or session.slot_number!=2 or session.operation!="enroll_second_device"):
            self.fail(db,student,403,"BIOMETRIC_BINDING_MISMATCH","Biometric test does not match this candidate.",session)
        self.template(db,student,session)
        if stage and session.stage!=stage:
            self.fail(db,student,409,"BIOMETRIC_STAGE_INVALID","This biometric stage has ended or has not started.")
        return student,session,pending

    def status(self,db,student,auth,identifier):
        _,session,_=self.load(db,student,auth,identifier)
        return self.result(session)

    def image(self,db,student,session,file):
        if session.frame_count>=MAX_LIVENESS_FRAMES:
            self.fail(db,student,429,"FRAME_LIMIT_REACHED","Too many frames. Start a new biometric test.",session)
        session.frame_count+=1
        trace("decode_started")
        image=self.context.bio.decode(file.file.read(MAX_IMAGE_BYTES+1))
        shape=getattr(image,"shape",None)
        trace("decoded",width=int(shape[1]) if shape is not None else None,height=int(shape[0]) if shape is not None else None)
        digest=hashlib.sha256(image.tobytes()).hexdigest()
        hashes=json.loads(session.frame_hashes)
        if digest in hashes:
            self.fail(db,student,409,"FRAME_REPLAY","A repeated frame was rejected. Start a new live biometric test.",session)
        hashes.append(digest);session.frame_hashes=json.dumps(hashes)
        return image

    def after_inference(self,db,student,session,pending):
        if session.expires_at<=self.context.now() or pending.expires_at<=self.context.now():
            self.fail(db,student,410,"BIOMETRIC_EXPIRED","Biometric test expired while processing the frame.",session)
        db.refresh(student)
        self.template(db,student,session)

    def face(self,db,student,auth,identifier,file):
        student,session,pending=self.load(db,student,auth,identifier,"FACE")
        try:
            image=self.image(db,student,session,file)
            trace("face_detection_started")
            encoding=self.context.bio.guided_face(image)
            trace("template_matching_started")
            _,reference=self.template(db,student,session)
            distance=self.context.bio.distance(encoding,reference)
        except BiometricError as exc:
            trace("adjustment",code=adjustment_code(exc))
            self.after_inference(db,student,session,pending)
            self.bio_event(db,student,"face","FAIL","FACE_ADJUST",session)
            return self.result(session,str(exc),feedback_code=adjustment_code(exc))
        except (RuntimeError,ImportError):
            self.fail(db,student,503,"BIOMETRIC_ENGINE_UNAVAILABLE","Biometric inference is unavailable. Check backend dependencies and the hand model.",session)
        self.after_inference(db,student,session,pending)
        if not math.isfinite(distance) or distance>=self.context.settings.face_threshold:
            self.fail(db,student,403,"FACE_NOT_MATCHED","Face not matched. Use your own enrolled face.",session)
        trace("face_verified")
        session.stage="LIVENESS";session.fingers=secrets.randbelow(5)+1
        self.bio_event(db,student,"face","PASS","FACE_MATCHED_UNTRUSTED",session)
        return self.result(session,ready=True)

    def liveness(self,db,student,auth,identifier,file):
        student,session,pending=self.load(db,student,auth,identifier,"LIVENESS")
        try:
            image=self.image(db,student,session,file)
            _,reference=self.template(db,student,session)
            distance=self.context.bio.distance(self.context.bio.face(image),reference)
            if not math.isfinite(distance) or distance>=self.context.settings.face_threshold:
                self.fail(db,student,403,"FACE_SUBSTITUTED","Your enrolled face must remain visible.",session)
            count=self.context.bio.hand(image)
            if count!=session.fingers:raise BiometricError(f"Show {session.fingers} finger(s) on one hand with your palm toward the camera.")
        except BiometricError as exc:
            trace("adjustment",code=adjustment_code(exc))
            self.after_inference(db,student,session,pending)
            session.valid_frames=0
            self.bio_event(db,student,"liveness","FAIL","LIVENESS_ADJUST",session)
            return self.result(session,str(exc),feedback_code=adjustment_code(exc))
        except (RuntimeError,ImportError):
            self.fail(db,student,503,"BIOMETRIC_ENGINE_UNAVAILABLE","Biometric inference is unavailable. Check backend dependencies and the hand model.",session)
        self.after_inference(db,student,session,pending)
        session.valid_frames+=1
        if session.valid_frames==REQUIRED_LIVENESS_FRAMES:
            session.stage="COMPLETED_UNTRUSTED";session.completed_at=self.context.now()
            self.bio_event(db,student,"complete","PASS","BIOMETRICS_COMPLETED_UNTRUSTED",session)
        return self.result(session,ready=True)
