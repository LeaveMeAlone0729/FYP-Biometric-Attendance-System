"""Explicit staff decisions, recorded separately from biometric verification.

Uses the existing attendance/audit schema; never fabricates biometric success.
The caller owns the transaction. Student-first locking matches student check-in.
"""
from datetime import datetime

from sqlalchemy import select

from models import Attendance, ClassSchedule, ClassSession, Student, VerificationAttempt
from services.attendance_timing import correction_deadline, end_pending_proofs

PRESENT_STATUSES = ('Present', 'Late')


class StaffAttendanceError(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def require_staff_edit_window(session, now):
    if session.status == 'cancelled':
        raise StaffAttendanceError('Attendance cannot be changed for a cancelled session.', 409)
    if datetime.combine(session.session_date, session.start_time) > now:
        raise StaffAttendanceError('Attendance can be taken once the class starts.', 409)
    if now >= correction_deadline(session):
        raise StaffAttendanceError('The two-hour correction window has ended. This class register is read-only.', 409)


def mark_attendance(db, *, session_id, student_id, status, reason, actor, version, now):
    reason = reason.strip()
    if status not in ('Present', 'Absent'):
        raise StaffAttendanceError('Choose Present or Absent.')
    if not 3 <= len(reason) <= 120:
        raise StaffAttendanceError('Enter a reason between 3 and 120 characters.')
    if not actor or len(actor) > 40:
        raise StaffAttendanceError('A valid staff account is required.', 403)
    student = db.scalar(select(Student).where(Student.student_id == student_id)
                        .with_for_update().execution_options(populate_existing=True))
    session = db.scalar(select(ClassSession).where(ClassSession.session_id == session_id)
                        .with_for_update().execution_options(populate_existing=True))
    if student is None or session is None:
        raise StaffAttendanceError('Student or class session not found.', 404)
    schedule = db.get(ClassSchedule, session.schedule_id)
    if schedule is None or schedule.group_id != student.group_id:
        raise StaffAttendanceError('This student does not belong to this class group.', 403)
    require_staff_edit_window(session, now)
    record = db.scalar(select(Attendance).where(
        Attendance.session_id == session_id, Attendance.student_id == student_id,
    ).with_for_update().execution_options(populate_existing=True))
    actual_version = str(record.verification_id) if record else 'unmarked'
    if version != actual_version:
        raise StaffAttendanceError('Attendance changed since this page was loaded. Refresh and review it before saving.', 409)
    if record is not None and record.status == status:
        return False
    previous = record.status if record else 'Unmarked'
    audit = VerificationAttempt(
        student_id=student_id, session_id=session_id, stage='teacher_attendance',
        verification_result='manual_present' if status == 'Present' else 'manual_absent',
        attempted_at=now, face_distance=None,
        failure_reason=f'Staff: {actor}; {previous} -> {status}; Reason: {reason}',
    )
    db.add(audit)
    db.flush()
    if record is None:
        record = Attendance(student_id=student_id, session_id=session_id,
                            verification_id=audit.verification_id, taken_at=now, status=status)
        db.add(record)
    else:
        record.status, record.taken_at, record.verification_id = status, now, audit.verification_id
    # An outstanding student proof must not overwrite a staff decision later.
    end_pending_proofs(db, student_id=student_id, session_id=session_id,
                       stage='staff_recorded', message='Attendance recorded by staff.')
    db.flush()
    return True


def save_class_register(db, *, session_id, versions, present_ids, reason, actor, now):
    """Save a complete checkbox register atomically in the caller's transaction.

    Lock all students in ID order before locking the session, consistent with
    student check-in. Validate the complete roster and every version first.
    """
    if not isinstance(versions, dict) or not versions or any(
        not isinstance(key, str) or not isinstance(value, str) for key, value in versions.items()
    ):
        raise StaffAttendanceError('The class register is missing. Reload the class session.', 400)
    if (not isinstance(present_ids, list) or any(not isinstance(sid, str) for sid in present_ids)
            or len(present_ids) != len(set(present_ids)) or not set(present_ids) <= versions.keys()):
        raise StaffAttendanceError('The selected students do not match this class register.', 400)
    reason = reason.strip() or 'Class roll call recorded by staff.'
    if not 3 <= len(reason) <= 120:
        raise StaffAttendanceError('Enter a note between 3 and 120 characters, or leave it blank.')
    session = db.get(ClassSession, session_id)
    if session is None:
        raise StaffAttendanceError('Class session not found.', 404)
    schedule = db.get(ClassSchedule, session.schedule_id)
    if schedule is None:
        raise StaffAttendanceError('The class schedule is unavailable.', 404)
    students = db.scalars(select(Student).where(Student.group_id == schedule.group_id)
        .order_by(Student.student_id).with_for_update().execution_options(populate_existing=True)).all()
    if {student.student_id for student in students} != versions.keys():
        raise StaffAttendanceError('The enrolled student list changed. Reload the class register before saving.', 409)
    session = db.get(ClassSession, session_id, with_for_update=True, populate_existing=True)
    require_staff_edit_window(session, now)
    records = {record.student_id: record for record in db.scalars(select(Attendance)
        .where(Attendance.session_id == session_id).with_for_update().execution_options(populate_existing=True))}
    for student in students:
        existing = records.get(student.student_id)
        actual_version = str(existing.verification_id) if existing else 'unmarked'
        if actual_version != versions[student.student_id]:
            raise StaffAttendanceError('Attendance changed since this register was opened. Reload and review the latest check-ins before saving.', 409)
    selected = set(present_ids)
    changed = 0
    for student in students:
        existing = records.get(student.student_id)
        # Preserve checked existing attendance and its original evidence.
        if student.student_id in selected and existing and existing.status in PRESENT_STATUSES:
            continue
        target = 'Present' if student.student_id in selected else 'Absent'
        changed += int(mark_attendance(db, session_id=session_id, student_id=student.student_id,
            status=target, reason=reason, actor=actor, version=versions[student.student_id], now=now))
    return dict(changed=changed, present=len(selected), absent=len(students) - len(selected), total=len(students))
