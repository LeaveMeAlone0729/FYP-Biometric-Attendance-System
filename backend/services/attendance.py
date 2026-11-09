"""The single runtime attendance writer; all three authorizations are mandatory."""
from config import iso_time
from models import Attendance,VerificationAttempt
from sqlalchemy.exc import IntegrityError
from modules.authorization.service import AttendanceAuthorizationService
from modules.devices.service import DeviceRegistrationError


def record_verified_attendance(context,db,student,challenge,session,*,auth=None,request_scope=None,device_challenge_id=None,device_signature=None):
    """Require passive anti-spoof evidence and fresh device/network authorization."""
    authorization=AttendanceAuthorizationService(context)
    result=authorization.authorize(db,student,auth,challenge,session,request_scope,device_challenge_id,device_signature)
    student,auth,challenge,session,nonce,network_id=result
    try:
        with db.begin_nested():
            authorization.fresh(db,student,auth,challenge,session,nonce)
            challenge.consumed=True;challenge.stage='complete'
            root=db.get(VerificationAttempt,challenge.verification_id)
            root.verification_result='success';root.stage='complete';root.failure_reason=None
            record=Attendance(student_id=student.student_id,session_id=session.session_id,
                verification_id=root.verification_id,taken_at=context.now(),status='Present')
            db.add(record);db.flush()
            authorization.fresh(db,student,auth,challenge,session,nonce)
            nonce.result='PASS';nonce.failure_code=None
            authorization.event(db,student,auth,'authorize','PASS','ATTENDANCE_AUTHORIZED',challenge,nonce,network_id)
            db.flush()
        context.runtime_liveness.discard(challenge)
    except (IntegrityError,DeviceRegistrationError) as exc:
        if isinstance(exc,IntegrityError):status,code,message=409,'ATTENDANCE_ALREADY_RECORDED','Attendance has already been recorded or the attendance state changed concurrently.'
        else:status,code,message=exc.status,exc.code,exc.message
        authorization.reject(db,student,auth,status,code,message,attempt=challenge,nonce=nonce,network_id=network_id,final=True)
    return dict(success=True,complete=True,face_verified=True,liveness_verified=True,
        attendance_id=record.attendance_id,recorded_at=iso_time(record.taken_at,context.settings),message='Attendance accepted')
