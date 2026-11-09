"""Attendance adapter; classroom requirements are configured per session."""
import json
from types import SimpleNamespace
from sqlalchemy import select
from models import ClassSession, Challenge
from modules.authorization.models import AttendanceDeviceChallenge
from modules.authorization.service import AttendanceAuthorizationService
from modules.devices.service import DeviceRegistrationError
from .models import Classroom, SessionClassroom, AttemptClassroom, AttendanceWifiBinding, WifiChallenge
from .service import ClassroomWifiService, MESSAGES


def configure(db, *, session_id, classroom_id, now):
    session=db.scalar(select(ClassSession).where(ClassSession.session_id==session_id).with_for_update())
    if session is None: raise ValueError('SESSION_NOT_FOUND')
    if classroom_id is not None and db.get(Classroom,classroom_id) is None: raise ValueError('CLASSROOM_NOT_FOUND')
    row=db.get(SessionClassroom,session_id)
    current=row.classroom_id if row else None
    if current==classroom_id:return dict(session_id=session_id,classroom_id=current,revision=row.revision if row else 0,changed=False)
    if db.scalar(select(Challenge.challenge_id).where(Challenge.session_id==session_id,
            Challenge.consumed.is_(False),Challenge.expires_at>now).limit(1)):
        raise ValueError('CLASSROOM_REQUIREMENT_IN_USE: wait for active attempts to finish or expire')
    if row is None:
        row=SessionClassroom(session_id=session_id,revision=0,updated_at=now);db.add(row)
    row.classroom_id=classroom_id;row.revision+=1;row.updated_at=now
    from .models import WifiPolicyEvent
    db.add(WifiPolicyEvent(policy_id='session:'+str(session_id),actor='disposable-session-operator',
        action='SESSION_REQUIREMENT',snapshot=json.dumps(dict(classroom_id=classroom_id,revision=row.revision)),occurred_at=now))
    db.flush()
    return dict(session_id=session_id,classroom_id=classroom_id,revision=row.revision,changed=True)


class AttendanceClassroomService:
    def __init__(self,context):self.context=context

    def fail(self,code,message=None,status=403):
        raise DeviceRegistrationError(status,code,message or MESSAGES.get(code,'Classroom authorization failed. Enter the PIN again.'))

    def freeze(self,db,attempt,session):
        # Caller holds student then class-session lock; configuration uses the same
        # session lock, so PIN start and requirement changes have a defined order.
        db.flush()
        row=db.get(SessionClassroom,session.session_id)
        snapshot=AttemptClassroom(attempt_id=attempt.challenge_id,session_id=session.session_id,
            classroom_id=row.classroom_id if row else None,revision=row.revision if row else 0,created_at=self.context.now())
        db.add(snapshot);db.flush()

    def requirement(self,db,attempt,session):
        current=db.get(SessionClassroom,session.session_id,populate_existing=True)
        snapshot=db.get(AttemptClassroom,attempt.challenge_id,populate_existing=True)
        classroom=current.classroom_id if current else None;revision=current.revision if current else 0
        if snapshot is None:
            if classroom is not None:self.fail('CLASSROOM_ATTEMPT_NOT_BOUND','This attempt predates the classroom requirement. Enter the PIN again.')
            return None
        if snapshot.session_id!=session.session_id or snapshot.classroom_id!=classroom or snapshot.revision!=revision:
            self.fail('CLASSROOM_REQUIREMENT_CHANGED','The session classroom requirement changed. Enter the PIN again.')
        return snapshot.classroom_id

    def info(self,db,nonce):
        attempt=db.get(Challenge,nonce.attendance_challenge_id);session=db.get(ClassSession,nonce.session_id)
        classroom=self.requirement(db,attempt,session)
        return dict(classroom_wifi_required=classroom is not None,classroom_id=classroom)

    def issue(self,db,student,auth,data):
        authorization=AttendanceAuthorizationService(self.context)
        student,auth=authorization.identity(db,student,auth)
        attempt,session=authorization.attempt(db,student,auth,data.attendance_challenge_id)
        classroom=self.requirement(db,attempt,session)
        if classroom is None:self.fail('CLASSROOM_NOT_REQUIRED','This session does not require classroom Wi-Fi.',409)
        nonce=db.get(AttendanceDeviceChallenge,data.device_challenge_id,with_for_update=True,populate_existing=True)
        purpose='attendance_preflight' if data.preflight else 'attendance_authorization'
        if nonce is None or nonce.student_id!=student.student_id or nonce.auth_token_hash!=auth.token_hash or nonce.attendance_challenge_id!=attempt.challenge_id or nonce.session_id!=session.session_id:
            self.fail('CLASSROOM_DEVICE_PROOF_MISMATCH')
        if nonce.consumed_at is not None or nonce.expires_at<=self.context.now() or json.loads(nonce.signing_payload).get('purpose')!=purpose:
            self.fail('CLASSROOM_DEVICE_PROOF_EXPIRED','Request a fresh attendance device challenge.',410)
        device=authorization.device(db,student,auth,attempt,nonce=nonce)
        binding=dict(attendance_attempt_id=attempt.challenge_id,attendance_session_id=session.session_id,
            device_challenge_id=nonce.challenge_id,requirement_revision=db.get(AttemptClassroom,attempt.challenge_id).revision)
        result=ClassroomWifiService(self.context).begin(db,student,auth,
            SimpleNamespace(classroom_id=classroom,public_key_fingerprint=device.public_key_fingerprint),
            operation='attendance_classroom_preflight' if data.preflight else 'attendance_classroom_final',binding=binding)
        db.flush()  # Persist nonce before its FK-bound attendance receipt.
        db.add(AttendanceWifiBinding(challenge_id=result['challenge_id'],attempt_id=attempt.challenge_id,
            device_challenge_id=nonce.challenge_id,purpose=purpose))
        db.flush()
        return result

    def check(self,db,student,auth,attempt,session,nonce,identifier,*,preflight=False):
        classroom=self.requirement(db,attempt,session)
        if classroom is None:return
        if not identifier:self.fail('CLASSROOM_WIFI_PROOF_REQUIRED','Fresh classroom Wi-Fi verification is required for this session.')
        row=db.get(AttendanceWifiBinding,identifier,with_for_update=True,populate_existing=True)
        ch=db.get(WifiChallenge,identifier,with_for_update=True,populate_existing=True)
        purpose='attendance_preflight' if preflight else 'attendance_authorization'
        operation='attendance_classroom_preflight' if preflight else 'attendance_classroom_final'
        if row is None or ch is None or row.attempt_id!=attempt.challenge_id or row.device_challenge_id!=nonce.challenge_id or row.purpose!=purpose or ch.operation!=operation or ch.student_id!=student.student_id or ch.auth_token_hash!=auth.token_hash or ch.device_id!=nonce.device_id or ch.key_fingerprint!=nonce.key_fingerprint or ch.classroom_id!=classroom:
            self.fail('CLASSROOM_WIFI_BINDING_MISMATCH')
        if row.used_at is not None:self.fail('WIFI_EVIDENCE_REPLAYED')
        if ch.result!='PASS' or not row.evidence:
            self.fail(ch.failure_code if ch.result=='FAIL' and ch.failure_code in MESSAGES else 'CLASSROOM_WIFI_PROOF_REQUIRED')
        if ch.expires_at<=self.context.now():self.fail('WIFI_CHALLENGE_EXPIRED',status=410)
        code,_=ClassroomWifiService(self.context).evaluate(db,ch,json.loads(row.evidence))
        if code!='CLASSROOM_WIFI_APPROVED':self.fail(code)
        row.used_at=self.context.now()
        db.info['attendance_wifi_receipt']=(attempt.challenge_id,identifier)
        ClassroomWifiService(self.context).event(db,student,'PASS','ATTENDANCE_CLASSROOM_PREFLIGHT' if preflight else 'ATTENDANCE_CLASSROOM_AUTHORIZED',ch)

    def validate_binding(self,db,student,auth,ch,row):
        authorization=AttendanceAuthorizationService(self.context)
        attempt,session=authorization.attempt(db,student,auth,row.attempt_id)
        classroom=self.requirement(db,attempt,session)
        nonce=db.get(AttendanceDeviceChallenge,row.device_challenge_id,with_for_update=True,populate_existing=True)
        expected='attendance_classroom_preflight' if row.purpose=='attendance_preflight' else 'attendance_classroom_final'
        payload=json.loads(ch.signing_payload)
        snapshot=db.get(AttemptClassroom,attempt.challenge_id)
        if nonce is None or nonce.consumed_at is not None or nonce.expires_at<=self.context.now():self.fail('CLASSROOM_DEVICE_PROOF_EXPIRED',status=410)
        if classroom!=ch.classroom_id or ch.operation!=expected or nonce.auth_token_hash!=auth.token_hash or nonce.student_id!=student.student_id or nonce.device_id!=ch.device_id or nonce.key_fingerprint!=ch.key_fingerprint or nonce.attendance_challenge_id!=attempt.challenge_id or nonce.session_id!=session.session_id or json.loads(nonce.signing_payload).get('purpose')!=row.purpose or any(payload.get(k)!=v for k,v in dict(attendance_attempt_id=attempt.challenge_id,attendance_session_id=session.session_id,device_challenge_id=nonce.challenge_id,requirement_revision=snapshot.revision).items()):
            self.fail('CLASSROOM_WIFI_BINDING_MISMATCH')

    def fresh(self,db,attempt,session):
        classroom=self.requirement(db,attempt,session)
        if classroom is None:return
        receipt=db.info.get('attendance_wifi_receipt')
        if receipt is None or receipt[0]!=attempt.challenge_id:self.fail('CLASSROOM_WIFI_PROOF_REQUIRED')
        row=db.get(AttendanceWifiBinding,receipt[1]);ch=db.get(WifiChallenge,receipt[1])
        if ch is None or row is None or ch.expires_at<=self.context.now():self.fail('WIFI_CHALLENGE_EXPIRED',status=410)
        code,_=ClassroomWifiService(self.context).evaluate(db,ch,json.loads(row.evidence))
        if code!='CLASSROOM_WIFI_APPROVED':self.fail(code)
