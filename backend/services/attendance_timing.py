"""Class-end absence finalization and the two-hour staff correction window."""
import asyncio
import logging
from datetime import datetime, timedelta

from sqlalchemy import and_, exists, func, or_, select
from starlette.concurrency import run_in_threadpool

from models import Attendance, Challenge, ClassSchedule, ClassSession, Student, VerificationAttempt

CORRECTION_WINDOW = timedelta(hours=2)
SWEEP_SECONDS = 10
log = logging.getLogger(__name__)


def class_end(session):
    return datetime.combine(session.session_date, session.end_time)


def correction_deadline(session):
    return class_end(session) + CORRECTION_WINDOW


def staff_can_edit(session, now):
    return (session.status != 'cancelled'
            and datetime.combine(session.session_date, session.start_time) <= now < correction_deadline(session))


def end_pending_proofs(db, *, student_id, session_id, stage, message):
    for challenge in db.scalars(select(Challenge).where(
        Challenge.student_id == student_id, Challenge.session_id == session_id,
        Challenge.consumed.is_(False),
    ).with_for_update()):
        challenge.consumed, challenge.stage = True, stage
        attempt = db.get(VerificationAttempt, challenge.verification_id)
        if attempt and attempt.verification_result == 'pending':
            attempt.verification_result = 'cancelled'
            attempt.failure_reason = message


def finalize_due_attendance(db, *, now, session_id=None, student_id=None, session_date=None, limit=500):
    """Insert missing absences only; caller owns commit/rollback.

    The candidate query is rechecked under student-first locks, matching student
    check-in and staff saves. Existing records, including corrections, are kept.
    A student created after a class ended is not retrospectively marked absent.
    """
    due = or_(ClassSession.session_date < now.date(), and_(
        ClassSession.session_date == now.date(), ClassSession.end_time <= now.time()))
    # Legacy MySQL imports can contain zero dates, which the driver returns as
    # None. They cannot establish enrollment before a historical class.
    enrolled = and_(Student.created_at >= datetime(1000, 1, 1), or_(func.date(Student.created_at) < ClassSession.session_date, and_(
        func.date(Student.created_at) == ClassSession.session_date,
        func.time(Student.created_at) <= ClassSession.end_time)))
    missing = ~exists(select(Attendance.attendance_id).where(
        Attendance.student_id == Student.student_id, Attendance.session_id == ClassSession.session_id))
    query = (select(Student.student_id, ClassSession.session_id)
        .select_from(Student).join(ClassSchedule, ClassSchedule.group_id == Student.group_id)
        .join(ClassSession, ClassSession.schedule_id == ClassSchedule.schedule_id)
        .where(ClassSession.status != 'cancelled', due, enrolled, missing)
        .order_by(Student.student_id, ClassSession.session_id))
    if session_id is not None:
        query = query.where(ClassSession.session_id == session_id)
    if student_id is not None:
        query = query.where(Student.student_id == student_id)
    if session_date is not None:
        query = query.where(ClassSession.session_date == session_date)
    if limit is not None:
        query = query.limit(limit)
    candidates = db.execute(query).all()
    if not candidates:
        return 0
    student_ids = sorted({sid for sid, _ in candidates})
    session_ids = sorted({sid for _, sid in candidates})
    students = {student.student_id: student for student in db.scalars(select(Student)
        .where(Student.student_id.in_(student_ids)).order_by(Student.student_id)
        .with_for_update().execution_options(populate_existing=True))}
    sessions = {session.session_id: session for session in db.scalars(select(ClassSession)
        .where(ClassSession.session_id.in_(session_ids)).order_by(ClassSession.session_id)
        .with_for_update().execution_options(populate_existing=True))}
    recorded = set(db.execute(select(Attendance.student_id, Attendance.session_id)
        .where(Attendance.student_id.in_(student_ids), Attendance.session_id.in_(session_ids))
        .with_for_update()).all())
    count = 0
    for sid, session_key in candidates:
        student, session = students.get(sid), sessions.get(session_key)
        if student is None or session is None or (sid, session_key) in recorded:
            continue
        schedule = db.get(ClassSchedule, session.schedule_id)
        end = class_end(session)
        if (session.status == 'cancelled' or now < end or student.created_at is None or student.created_at > end
                or schedule is None or schedule.group_id != student.group_id):
            continue
        audit = VerificationAttempt(student_id=sid, session_id=session_key,
            stage='auto_absence', verification_result='auto_absent', attempted_at=now,
            face_distance=None, failure_reason='System: class ended without a recorded attendance submission.')
        db.add(audit)
        db.flush()
        db.add(Attendance(student_id=sid, session_id=session_key, verification_id=audit.verification_id,
                          taken_at=end, status='Absent'))
        end_pending_proofs(db, student_id=sid, session_id=session_key, stage='class_ended',
                           message='Class ended. Missing attendance was recorded as absent.')
        recorded.add((sid, session_key))
        count += 1
    db.flush()
    return count


async def run_absence_worker(context, stop, *, interval=SWEEP_SECONDS):
    """Sweep even while no browser or mobile request is open; catch up on restart."""
    def sweep():
        with context.sessions() as db, db.begin():
            return finalize_due_attendance(db, now=context.now())

    while not stop.is_set():
        try:
            await run_in_threadpool(sweep)
        except Exception as exc:
            # Connector exceptions can contain private connection details.
            log.warning('Automatic attendance sweep failed (%s); retrying.', type(exc).__name__)
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval)
        except TimeoutError:
            pass
