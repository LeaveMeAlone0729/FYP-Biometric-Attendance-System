from database_compat import shared_read
"""Server-owned final decision. No standalone PASS or client flags are accepted."""
import base64,json,math,secrets
from datetime import timedelta
from sqlalchemy import select,func
from models import Student,AuthSession,Challenge,ClassSession,VerificationAttempt,Attendance
from config import iso_time
from modules.devices.crypto import canonical_public_key,verify_signature
from modules.devices.models import RegisteredDevice
from modules.devices.local_demo import permits_device
from modules.devices.service import DeviceRegistrationError
from modules.networks.service import NetworkVerificationService
from modules.biometrics.constants import REQUIRED_LIVENESS_FRAMES
from .models import AttendanceDeviceChallenge,AttendanceAuthorizationEvent

class AttendanceAuthorizationService:
    def __init__(self,context):self.context=context

    def identity(self,db,student,auth):
        current=db.scalar(select(Student).where(Student.student_id==student.student_id).with_for_update().execution_options(populate_existing=True))
        session=db.scalar(select(AuthSession).where(AuthSession.token_hash==auth.token_hash).with_for_update().execution_options(populate_existing=True))
        if current is None or session is None or session.student_id!=current.student_id or current.account_status!='active' or session.expires_at<=self.context.now():
            raise DeviceRegistrationError(401,'ATTENDANCE_SESSION_EXPIRED','Your login expired. Sign in and enter the class PIN again.')
        return current,session

    def event(self,db,student,auth,action,result,code,attempt=None,nonce=None,network_id=None):
        db.add(AttendanceAuthorizationEvent(student_id=student.student_id,auth_token_hash=auth.token_hash,
            attendance_challenge_id=attempt.challenge_id if attempt else None,device_challenge_id=nonce.challenge_id if nonce else None,
            device_id=nonce.device_id if nonce else None,network_verification_id=network_id,
            action=action,result=result,code=code,occurred_at=self.context.now()))

    def reject(self,db,student,auth,status,code,message,*,attempt=None,nonce=None,network_id=None,final=False):
        if nonce is not None and nonce.result!='PASS':
            nonce.consumed_at=nonce.consumed_at or self.context.now();nonce.result='FAIL';nonce.failure_code=code
        if final and attempt is not None and not attempt.consumed:
            attempt.consumed=True
            root=db.get(VerificationAttempt,attempt.verification_id)
            root.verification_result='failed';root.stage='authorization';root.failure_reason=message
        self.event(db,student,auth,'authorize' if final else ('preflight' if nonce and json.loads(nonce.signing_payload).get('purpose')=='attendance_preflight' else 'challenge'),'FAIL',code,attempt,nonce,network_id)
        db.flush()
        raise DeviceRegistrationError(status,code,message)

    def attempt(self,db,student,auth,identifier):
        attempt=db.scalar(select(Challenge).where(Challenge.challenge_id==identifier).with_for_update().execution_options(populate_existing=True))
        if attempt is None or attempt.student_id!=student.student_id or attempt.auth_token_hash!=auth.token_hash:
            self.reject(db,student,auth,403,'ATTENDANCE_ATTEMPT_MISMATCH','This attendance attempt belongs to another student or login.')
        if attempt.consumed:self.reject(db,student,auth,409,'ATTENDANCE_ATTEMPT_ENDED','This attendance attempt has ended. Check history or start again.',attempt=attempt)
        if attempt.expires_at<=self.context.now():self.reject(db,student,auth,410,'ATTENDANCE_ATTEMPT_EXPIRED','Attendance verification expired. Enter the PIN again.',attempt=attempt)
        session=db.scalar(select(ClassSession).where(ClassSession.session_id==attempt.session_id).with_for_update(read=shared_read(db)).execution_options(populate_existing=True))
        if session is None or not self.context.session_open(session,student,db):
            self.reject(db,student,auth,409,'ATTENDANCE_WINDOW_CLOSED','The attendance window is closed.',attempt=attempt)
        return attempt,session

    def device(self,db,student,auth,attempt,*,fingerprint=None,nonce=None,final=False):
        criterion=RegisteredDevice.device_id==nonce.device_id if nonce else RegisteredDevice.public_key_fingerprint==fingerprint
        device=db.scalar(select(RegisteredDevice).where(RegisteredDevice.student_id==student.student_id,criterion).with_for_update().execution_options(populate_existing=True))
        def fail(code,message):self.reject(db,student,auth,403,code,message,attempt=attempt,nonce=nonce,final=final)
        if device is None:fail('ATTENDANCE_DEVICE_NOT_REGISTERED','This installation is not a registered attendance device. Register it or complete approved enrollment first.')
        if device.status!='ACTIVE' or device.slot_number not in (1,2):fail('ATTENDANCE_DEVICE_NOT_ACTIVE','This device is revoked or inactive. Use an ACTIVE trusted device.')
        if not permits_device(db, device):fail('LOCAL_DEMO_DEVICE_DISABLED','This LOCAL FYP DEMO device requires the original local demo profile.')
        try:_,actual=canonical_public_key(device.public_key_spki)
        except ValueError:actual=None
        if actual!=device.public_key_fingerprint or (nonce and actual!=nonce.key_fingerprint):fail('ATTENDANCE_DEVICE_BINDING_CHANGED','The registered key changed. Restart attendance using the correct installation.')
        return device

    def issue(self,db,student,auth,identifier,fingerprint,*,preflight=False,scope=None):
        student,auth=self.identity(db,student,auth);attempt,session=self.attempt(db,student,auth,identifier)
        root=db.get(VerificationAttempt,attempt.verification_id)
        if not preflight and (attempt.stage!='liveness' or root.verification_result!='pending' or root.face_distance is None or not math.isfinite(root.face_distance) or root.face_distance>=self.context.settings.face_threshold):
            self.reject(db,student,auth,409,'ATTENDANCE_FACE_REQUIRED','Complete genuine face verification before signing the attendance challenge.',attempt=attempt)
        if preflight:
            if attempt.stage!='face' or root.verification_result!='pending':
                self.reject(db,student,auth,409,'ATTENDANCE_PREFLIGHT_STAGE','Enter the class PIN again before checking attendance readiness.',attempt=attempt)
            self.preflight_network(db,student,auth,attempt,scope)
        device=self.device(db,student,auth,attempt,fingerprint=fingerprint)
        purpose='attendance_preflight' if preflight else 'attendance_authorization'
        now=self.context.now()
        old=db.scalar(select(AttendanceDeviceChallenge).where(AttendanceDeviceChallenge.attendance_challenge_id==identifier,AttendanceDeviceChallenge.consumed_at==None).with_for_update())
        if old:
            if old.expires_at>now:
                if old.device_id==device.device_id and old.auth_token_hash==auth.token_hash and old.key_fingerprint==fingerprint and json.loads(old.signing_payload).get('purpose')==purpose:return self.info(old,device.slot_number,db)
                self.reject(db,student,auth,409,'ATTENDANCE_DEVICE_PROOF_PENDING','Another device is already bound to this attendance attempt.',attempt=attempt)
            old.consumed_at=now;old.result='FAIL';old.failure_code='ATTENDANCE_DEVICE_PROOF_EXPIRED';db.flush()
        recent=db.scalar(select(func.count()).select_from(AttendanceAuthorizationEvent).where(AttendanceAuthorizationEvent.student_id==student.student_id,
            AttendanceAuthorizationEvent.result=='ISSUED',AttendanceAuthorizationEvent.occurred_at>now-timedelta(minutes=5)))
        if recent>=20:self.reject(db,student,auth,429,'ATTENDANCE_PROOF_RATE_LIMITED','Too many attendance device challenges. Try again shortly.',attempt=attempt)
        expires=min(now+timedelta(seconds=60),attempt.expires_at,auth.expires_at).replace(microsecond=0)
        if expires<=now:self.reject(db,student,auth,410,'ATTENDANCE_DEVICE_PROOF_EXPIRED','The attendance deadline expired. Start again.',attempt=attempt)
        nonce_id=secrets.token_urlsafe(32)
        payload=json.dumps(dict(version=1,purpose=purpose,operation=purpose,challenge_id=nonce_id,
            attendance_challenge_id=identifier,attendance_session_id=session.session_id,biometric_verification_id=attempt.verification_id,
            student_id=student.student_id,auth_session_hash=auth.token_hash,device_id=device.device_id,slot_number=device.slot_number,
            public_key_fingerprint=device.public_key_fingerprint,nonce=secrets.token_urlsafe(32),expires_at=iso_time(expires,self.context.settings)),sort_keys=True,separators=(',',':'))
        nonce=AttendanceDeviceChallenge(challenge_id=nonce_id,student_id=student.student_id,auth_token_hash=auth.token_hash,
            attendance_challenge_id=identifier,session_id=session.session_id,device_id=device.device_id,key_fingerprint=device.public_key_fingerprint,
            operation='attendance_authorization',signing_payload=payload,created_at=now,expires_at=expires,result='PENDING')
        db.add(nonce);db.flush();self.event(db,student,auth,'preflight' if preflight else 'challenge','ISSUED',
            'ATTENDANCE_PREFLIGHT_CHALLENGE_ISSUED' if preflight else 'ATTENDANCE_DEVICE_CHALLENGE_ISSUED',attempt,nonce)
        return self.info(nonce,device.slot_number,db)

    def info(self,nonce,slot,db=None):
        extra=self.context.classroom_attendance.info(db,nonce) if getattr(self.context,'classroom_attendance',None) is not None else {}
        return dict(success=True,challenge_id=nonce.challenge_id,attendance_challenge_id=nonce.attendance_challenge_id,
            attendance_session_id=nonce.session_id,device_id=nonce.device_id,slot_number=slot,public_key_fingerprint=nonce.key_fingerprint,
            operation=json.loads(nonce.signing_payload)['operation'],algorithm='ECDSA_P256_SHA256',signature_encoding='base64-DER',
            signing_payload=base64.b64encode(nonce.signing_payload.encode()).decode(),expires_at=iso_time(nonce.expires_at,self.context.settings),**extra)

    def preflight_network(self,db,student,auth,attempt,scope,nonce=None):
        network=NetworkVerificationService(self.context).verify(db,student,auth,scope,operation='attendance_authorization',attendance_attempt_id=attempt.challenge_id)
        if network['result']!='PASS':
            self.reject(db,student,auth,403,network['reason_code'],network['message'],attempt=attempt,nonce=nonce,network_id=network['verification_id'])
        return network

    def preflight(self,db,student,auth,identifier,proof_id,signature,scope,classroom_wifi_proof_id=None):
        student,auth=self.identity(db,student,auth);attempt,session=self.attempt(db,student,auth,identifier)
        nonce=db.scalar(select(AttendanceDeviceChallenge).where(AttendanceDeviceChallenge.challenge_id==proof_id).with_for_update().execution_options(populate_existing=True))
        def deny(status,code,message,owned=None):
            self.reject(db,student,auth,status,code,message,attempt=attempt,nonce=owned)
        if nonce is None or nonce.student_id!=student.student_id or nonce.auth_token_hash!=auth.token_hash or nonce.attendance_challenge_id!=identifier or nonce.session_id!=session.session_id:
            deny(403,'ATTENDANCE_DEVICE_PROOF_MISMATCH','Preflight belongs to another student, login or attendance attempt.')
        if nonce.consumed_at is not None:deny(409,'ATTENDANCE_DEVICE_PROOF_REPLAYED','This preflight proof was already used.')
        payload=json.loads(nonce.signing_payload)
        if payload.get('purpose')!='attendance_preflight' or payload.get('operation')!='attendance_preflight':
            deny(403,'ATTENDANCE_PREFLIGHT_PROOF_REQUIRED','A separate attendance preflight challenge is required.')
        nonce.consumed_at=self.context.now();nonce.result='FAIL';nonce.failure_code='ATTENDANCE_PREFLIGHT_FAILED'
        if nonce.expires_at<=self.context.now():deny(410,'ATTENDANCE_DEVICE_PROOF_EXPIRED','Preflight expired. Enter the PIN again.',nonce)
        device=self.device(db,student,auth,attempt,nonce=nonce)
        expected=dict(student_id=student.student_id,auth_session_hash=auth.token_hash,attendance_challenge_id=identifier,
            attendance_session_id=session.session_id,challenge_id=nonce.challenge_id,device_id=device.device_id,slot_number=device.slot_number,
            public_key_fingerprint=device.public_key_fingerprint,biometric_verification_id=attempt.verification_id,
            expires_at=iso_time(nonce.expires_at,self.context.settings))
        if any(payload.get(k)!=v for k,v in expected.items()):deny(403,'ATTENDANCE_DEVICE_BINDING_CHANGED','Preflight binding changed.',nonce)
        if not verify_signature(device.public_key_spki,nonce.signing_payload,signature):deny(403,'ATTENDANCE_DEVICE_SIGNATURE_INVALID','The preflight device signature is invalid.',nonce)
        root=db.get(VerificationAttempt,attempt.verification_id)
        if attempt.stage!='face' or root.verification_result!='pending':deny(409,'ATTENDANCE_PREFLIGHT_STAGE','Restart attendance before opening the camera.',nonce)
        network=self.preflight_network(db,student,auth,attempt,scope,nonce)
        if getattr(self.context,'classroom_attendance',None) is not None:
            try:self.context.classroom_attendance.check(db,student,auth,attempt,session,nonce,classroom_wifi_proof_id,preflight=True)
            except DeviceRegistrationError as exc:deny(exc.status,exc.code,exc.message,nonce)
        try:self.fresh(db,student,auth,attempt,session,nonce)
        except DeviceRegistrationError as exc:deny(exc.status,exc.code,exc.message,nonce)
        nonce.result='PASS';nonce.failure_code=None
        self.event(db,student,auth,'preflight','PASS','ATTENDANCE_PREFLIGHT_PASSED',attempt,nonce,network['verification_id'])
        return dict(success=True,result='PASS',attendance_authorized=False,attendance_challenge_id=identifier,
            device_id=device.device_id,network_verification_id=network['verification_id'])

    def authorize(self,db,student,auth,attempt,session,scope,proof_id,signature):
        if auth is None or scope is None:
            raise DeviceRegistrationError(403,'ATTENDANCE_AUTHORIZATION_REQUIRED','Attendance requires the authenticated request and fresh device/network authorization.')
        student,auth=self.identity(db,student,auth);attempt,session=self.attempt(db,student,auth,attempt.challenge_id)
        root=db.scalar(select(VerificationAttempt).where(VerificationAttempt.verification_id==attempt.verification_id).with_for_update())
        def deny(status,code,message,nonce=None,network_id=None):self.reject(db,student,auth,status,code,message,attempt=attempt,nonce=nonce,network_id=network_id,final=True)
        if (attempt.stage!='liveness' or root.verification_result!='pending' or root.stage!='liveness'
                or attempt.valid_frames!=REQUIRED_LIVENESS_FRAMES or root.face_distance is None
                or not math.isfinite(root.face_distance) or root.face_distance>=self.context.settings.face_threshold):
            deny(403,'ATTENDANCE_BIOMETRICS_REQUIRED','Successful server face matching and three live gesture frames are required.')
        if not proof_id or not signature:deny(403,'ATTENDANCE_DEVICE_PROOF_REQUIRED','A fresh signed attendance-device challenge is required. Update the app and use an ACTIVE registered installation.')
        nonce=db.scalar(select(AttendanceDeviceChallenge).where(AttendanceDeviceChallenge.challenge_id==proof_id).with_for_update().execution_options(populate_existing=True))
        if (nonce is None or nonce.student_id!=student.student_id or nonce.auth_token_hash!=auth.token_hash
                or nonce.attendance_challenge_id!=attempt.challenge_id or nonce.session_id!=session.session_id):
            deny(403,'ATTENDANCE_DEVICE_PROOF_MISMATCH','The device proof belongs to a different student, login or attendance session.')
        if nonce.consumed_at is not None:deny(409,'ATTENDANCE_DEVICE_PROOF_REPLAYED','This attendance device proof has already been used.')
        nonce.consumed_at=self.context.now();nonce.result='FAIL';nonce.failure_code='ATTENDANCE_NOT_COMMITTED'
        if nonce.expires_at<=self.context.now():deny(410,'ATTENDANCE_DEVICE_PROOF_EXPIRED','The attendance device signature expired. Enter the PIN again.',nonce)
        device=self.device(db,student,auth,attempt,nonce=nonce,final=True)
        payload=json.loads(nonce.signing_payload)
        expected=dict(purpose='attendance_authorization',operation='attendance_authorization',challenge_id=nonce.challenge_id,
            attendance_challenge_id=attempt.challenge_id,attendance_session_id=session.session_id,biometric_verification_id=attempt.verification_id,
            student_id=student.student_id,auth_session_hash=auth.token_hash,device_id=device.device_id,slot_number=device.slot_number,
            public_key_fingerprint=device.public_key_fingerprint,expires_at=iso_time(nonce.expires_at,self.context.settings))
        if nonce.operation!='attendance_authorization' or any(payload.get(k)!=v for k,v in expected.items()):deny(403,'ATTENDANCE_DEVICE_BINDING_CHANGED','Attendance challenge binding changed.',nonce)
        if not verify_signature(device.public_key_spki,nonce.signing_payload,signature):deny(403,'ATTENDANCE_DEVICE_SIGNATURE_INVALID','The attendance device signature is invalid. Use the installation holding the registered key.',nonce)
        network=NetworkVerificationService(self.context).verify(db,student,auth,scope,operation='attendance_authorization',attendance_attempt_id=attempt.challenge_id)
        if network['result']!='PASS':deny(403,network['reason_code'],network['message'],nonce,network['verification_id'])
        if getattr(self.context,'classroom_attendance',None) is not None:
            try:self.context.classroom_attendance.check(db,student,auth,attempt,session,nonce,scope.get('classroom_wifi_proof_id'))
            except DeviceRegistrationError as exc:deny(exc.status,exc.code,exc.message,nonce,network['verification_id'])
        try:self.fresh(db,student,auth,attempt,session,nonce)
        except DeviceRegistrationError as exc:deny(exc.status,exc.code,exc.message,nonce,network['verification_id'])
        if db.scalar(select(Attendance.attendance_id).where(Attendance.student_id==student.student_id,Attendance.session_id==session.session_id)):
            deny(409,'ATTENDANCE_ALREADY_RECORDED','Attendance has already been recorded for this class.',nonce,network['verification_id'])
        return student,auth,attempt,session,nonce,network['verification_id']

    def fresh(self,db,student,auth,attempt,session,nonce):
        if min(auth.expires_at,attempt.expires_at,nonce.expires_at)<=self.context.now() or not self.context.session_open(session,student,db):
            raise DeviceRegistrationError(410,'ATTENDANCE_AUTHORIZATION_EXPIRED','The attendance authorization expired while processing. Start again.')
        if getattr(self.context,'classroom_attendance',None) is not None:
            self.context.classroom_attendance.fresh(db,attempt,session)
