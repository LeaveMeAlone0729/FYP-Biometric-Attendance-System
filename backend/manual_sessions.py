"""Disposable operator adapter over existing academic models and creation logic."""
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
import secrets
from sqlalchemy import select,func
from models import Course,ClassSchedule,ClassSession,StudentGroup,Attendance
from manage import create_class_session
from security import digest
from manual_android_test import require,DB_PORT


def require_backend_ready(env):
    from prepare_manual_android_test import verified_pid
    import httpx
    require(verified_pid(env,'backend') is not None,'BACKEND_NOT_RUNNING: run fyp-test.ps1 start --lan')
    try:
        response=httpx.get('http://127.0.0.1:8002/manual-test/isolation',timeout=3,trust_env=False)
        response.raise_for_status();data=response.json()
    except (httpx.HTTPError,ValueError):
        require(False,'BACKEND_NOT_READY: run fyp-test.ps1 status and inspect isolated logs')
    require(data.get('disposable') is True and data.get('db_port')==DB_PORT
        and data.get('production_port_blocked') is True,'BACKEND_ISOLATION_CHECK_FAILED')


def describe(db,session,now,timezone):
    schedule=db.get(ClassSchedule,session.schedule_id);course=db.get(Course,schedule.course_code)
    begin=datetime.combine(session.session_date,session.start_time)
    end=datetime.combine(session.session_date,session.end_time)
    state=('CLOSED' if session.status!='active' else 'EXPIRED' if now>end
        else 'SCHEDULED' if now<begin else 'OPEN')
    if state=='OPEN' and not schedule.start_date<=now.date()<=schedule.end_date:state='OUTSIDE_SCHEDULE'
    return dict(session_id=session.session_id,schedule_id=schedule.schedule_id,class_code=course.course_code,
        class_name=course.course_name,group_id=schedule.group_id,status=session.status,window_state=state,
        starts_at=begin.replace(tzinfo=ZoneInfo(timezone)).isoformat(),
        expires_at=end.replace(tzinfo=ZoneInfo(timezone)).isoformat(),
        attendance_count=db.scalar(select(func.count()).select_from(Attendance).where(Attendance.session_id==session.session_id)))


def list_sessions(db,*,now,timezone,course_code=None,include_all=False):
    if course_code is not None:require(db.get(Course,course_code) is not None,'CLASS_NOT_FOUND')
    query=select(ClassSession).join(ClassSchedule)
    if course_code:query=query.where(ClassSchedule.course_code==course_code)
    rows=[describe(db,row,now,timezone) for row in db.scalars(query.order_by(ClassSession.session_date.desc(),ClassSession.session_id.desc()))]
    return rows if include_all else [r for r in rows if r['window_state']=='OPEN']


def unused_pin(db, *, group_id, session_date):
    # The caller holds the group lock. Read current hashes even in repeatable-read transactions.
    hashes = set(db.scalars(select(ClassSession.pin_hash).join(ClassSchedule).where(
        ClassSchedule.group_id == group_id,
        ClassSession.session_date == session_date).with_for_update()))
    for _ in range(20):
        candidate = str(secrets.randbelow(900000) + 100000)
        if digest(candidate) not in hashes:
            return candidate
    require(False, 'PIN_GENERATION_FAILED: retry')


def regenerate_pin(db, *, session_id, current_time, timezone):
    group_id = db.scalar(select(ClassSchedule.group_id).join(ClassSession).where(
        ClassSession.session_id == session_id))
    require(group_id is not None, 'SESSION_NOT_FOUND')
    # Same group-first lock order as session creation.
    db.scalar(select(StudentGroup).where(StudentGroup.group_id == group_id).with_for_update())
    row = db.get(ClassSession, session_id, with_for_update=True, populate_existing=True)
    require(row is not None, 'SESSION_NOT_FOUND')
    pin = unused_pin(db, group_id=group_id, session_date=row.session_date)
    result = describe(db, row, current_time(), timezone)
    require(result['window_state'] == 'OPEN', 'SESSION_NOT_OPEN: only open sessions can receive a new PIN.')
    row.pin_hash = digest(pin)
    return {**result, 'pin': pin, 'pin_shown_once': True}


def create_session(db,*,now,timezone,course_code,group_id=None,minutes=None,expires_at=None,classroom_id=None):
    now=now.replace(microsecond=0)
    require(not (minutes is not None and expires_at is not None),'CHOOSE_DURATION_OR_EXPIRY')
    if expires_at is not None:
        try:
            end=datetime.fromisoformat(expires_at)
            if end.tzinfo:end=end.astimezone(ZoneInfo(timezone)).replace(tzinfo=None)
        except (ValueError,TypeError):require(False,'INVALID_EXPIRY: use an ISO date/time in Asia/Kuala_Lumpur')
    else:
        minutes=30 if minutes is None else minutes
        require(type(minutes) is int and 1<=minutes<=1440,'INVALID_DURATION: use 1 to 1440 minutes')
        end=now+timedelta(minutes=minutes)
    end=end.replace(microsecond=0)
    require(end>now,'EXPIRY_MUST_BE_IN_FUTURE')
    require(end.date()==now.date(),'SESSION_CANNOT_CROSS_MIDNIGHT')
    course=db.get(Course,course_code)
    require(course is not None,'CLASS_NOT_FOUND: use an existing test course code')
    groups=set(db.scalars(select(ClassSchedule.group_id).where(ClassSchedule.course_code==course_code)))
    require(bool(groups),'CLASS_HAS_NO_EXISTING_GROUP_SCHEDULE')
    if group_id is None:
        require(len(groups)==1,'CLASS_GROUP_AMBIGUOUS: specify --group-id')
        group_id=next(iter(groups))
    require(group_id in groups,'CLASS_GROUP_NOT_FOUND')
    # Serialize new operator sessions for this group; no changes to the group itself.
    db.scalar(select(StudentGroup).where(StudentGroup.group_id==group_id).with_for_update())
    existing=db.scalars(select(ClassSession).join(ClassSchedule).where(ClassSchedule.group_id==group_id,
        ClassSchedule.course_code==course_code,ClassSession.session_date==now.date(),ClassSession.status=='active').with_for_update()).all()
    require(not any(s.start_time<=end.time() and s.end_time>=now.time() for s in existing),
        'SESSION_OVERLAP: close the existing session explicitly or wait for expiry')
    pin=unused_pin(db,group_id=group_id,session_date=now.date())
    previous=db.scalar(select(ClassSchedule).where(ClassSchedule.course_code==course_code,
        ClassSchedule.group_id==group_id).order_by(ClassSchedule.schedule_id.desc()))
    row=create_class_session(db,group_id=group_id,course_code=course_code,course_name=course.course_name,
        session_date=now.date(),start=now.time(),end=end.time(),venue='Isolated FYP test',
        lecturer=previous.lecturer,pin=pin)
    db.flush()
    if classroom_id is not None:
        from modules.classroom_wifi.attendance import configure
        configure(db,session_id=row.session_id,classroom_id=classroom_id,now=now)
    return {**describe(db,row,now,timezone),'pin':pin,'pin_shown_once':True}


def close_session(db,*,session_id,now,timezone,expire=False):
    row=db.get(ClassSession,session_id,with_for_update=True,populate_existing=True)
    require(row is not None,'SESSION_NOT_FOUND')
    changed=row.status=='active'
    if changed:row.status='closed';db.flush()
    # Existing window/attendance/verification history stays intact. The existing
    # session_open/final writer rejects a closed session without a new bypass.
    return {**describe(db,row,now,timezone),'changed':changed,'operation':'EXPIRE' if expire else 'CLOSE',
        'message':'Session closed immediately; original window and attendance history retained.'}
