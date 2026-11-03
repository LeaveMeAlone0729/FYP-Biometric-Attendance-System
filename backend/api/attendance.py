"""Supporting demo PIN, timetable and attendance history routes."""

import secrets
from datetime import datetime, timedelta

from config import iso_time
from demo import seed_demo
from fastapi import APIRouter, Depends, HTTPException
from models import (
    Attendance,
    Challenge,
    ClassSchedule,
    ClassSession,
    Course,
    Student,
    VerificationAttempt,
)
from modules.biometrics.schemas import ChallengeStarted
from security import digest
from sqlalchemy import func, select

from .context import AppContext
from .dependencies import authenticated, get_context, get_db
from .schemas import ERROR_RESPONSES, PinEntry

router = APIRouter(tags=["Demo attendance"])


@router.post(
    "/attendance/start",
    operation_id="startAttendanceVerification",
    response_model=ChallengeStarted,
    responses=ERROR_RESPONSES,
    summary="Validate the demo class PIN and start a biometric challenge",
)
def start_attendance(
    data: PinEntry,
    identity=Depends(authenticated),
    db=Depends(get_db, scope="function"),
    context: AppContext = Depends(get_context),
):
    student, auth = identity
    # Serializes starts for a student, and prevents overlapping active challenges.
    student = db.scalar(
        select(Student)
        .where(Student.student_id == student.student_id)
        .with_for_update()
    )
    failures = db.scalar(
        select(func.count())
        .select_from(VerificationAttempt)
        .where(
            VerificationAttempt.student_id == student.student_id,
            VerificationAttempt.stage == "pin",
            VerificationAttempt.verification_result == "failed",
            VerificationAttempt.attempted_at > context.now() - timedelta(minutes=5),
        )
    )
    if failures >= 5:
        raise HTTPException(
            429, "Too many incorrect attendance PINs. Try again in five minutes."
        )
    if context.settings.demo_mode:
        seed_demo(db, context.now())
    matches = db.scalars(
        select(ClassSession)
        .join(ClassSchedule)
        .where(
            ClassSchedule.group_id == student.group_id,
            ClassSession.session_date == context.now().date(),
            ClassSession.pin_hash == digest(data.pin),
            ClassSession.status == "active",
        )
    ).all()
    matches = [
        session for session in matches if context.session_open(session, student, db)
    ]
    if len(matches) != 1:
        context.reject(
            db,
            student.student_id,
            "pin",
            "The PIN does not match an active class for your group.",
        )
    session = matches[0]
    if db.scalar(
        select(Attendance).where(
            Attendance.session_id == session.session_id,
            Attendance.student_id == student.student_id,
        )
    ):
        context.reject(
            db,
            student.student_id,
            "duplicate",
            "Your attendance for this class has already been recorded.",
            session.session_id,
            409,
        )
    if student.biometric_status != "active":
        context.reject(
            db,
            student.student_id,
            "face",
            "Register your face in Profile before taking attendance.",
            session.session_id,
            409,
        )
    for old in db.scalars(
        select(Challenge).where(
            Challenge.student_id == student.student_id, Challenge.consumed == False
        )
    ):
        old.consumed = True
        root = db.get(VerificationAttempt, old.verification_id)
        root.verification_result = "cancelled"
        root.failure_reason = "Replaced by a new verification request."
    attempt = context.audit(
        db, student.student_id, "face", None, session.session_id, "pending"
    )
    challenge = Challenge(
        challenge_id=secrets.token_urlsafe(32),
        student_id=student.student_id,
        session_id=session.session_id,
        auth_token_hash=auth.token_hash,
        verification_id=attempt.verification_id,
        stage="face",
        expires_at=context.now()
        + timedelta(seconds=context.settings.challenge_seconds),
    )
    db.add(challenge)
    schedule = db.get(ClassSchedule, session.schedule_id)
    course = db.get(Course, schedule.course_code)
    return {
        "success": True,
        "challenge_id": challenge.challenge_id,
        "expires_at": iso_time(challenge.expires_at, context.settings),
        "course_name": course.course_name,
        "session_id": session.session_id,
        "venue": session.venue,
        "stage": "face",
        "expires_in": context.settings.challenge_seconds,
    }


@router.get("/classes")
def classes(
    identity=Depends(authenticated),
    db=Depends(get_db, scope="function"),
    context: AppContext = Depends(get_context),
):
    student, auth = identity
    if context.settings.demo_mode:
        seed_demo(db, context.now())
    rows = db.execute(
        select(ClassSession, ClassSchedule, Course)
        .select_from(ClassSession)
        .join(ClassSchedule, ClassSession.schedule_id == ClassSchedule.schedule_id)
        .join(Course, ClassSchedule.course_code == Course.course_code)
        .where(
            ClassSchedule.group_id == student.group_id,
            ClassSession.session_date.between(
                context.now().date(), context.now().date() + timedelta(days=7)
            ),
        )
        .order_by(ClassSession.session_date, ClassSession.start_time)
    ).all()
    attended = set(
        db.scalars(
            select(Attendance.session_id).where(
                Attendance.student_id == student.student_id
            )
        )
    )
    return [
        {
            "session_id": session.session_id,
            "course_code": course.course_code,
            "course_name": course.course_name,
            "date": session.session_date.isoformat(),
            "start_time": session.start_time.isoformat(),
            "end_time": session.end_time.isoformat(),
            "venue": session.venue,
            "class_type": schedule.class_type,
            "lecturer": schedule.lecturer,
            "is_open": context.session_open(session, student, db),
            "attended": session.session_id in attended,
        }
        for session, schedule, course in rows
    ]


@router.get("/attendance/history")
def history(
    identity=Depends(authenticated),
    db=Depends(get_db, scope="function"),
    context: AppContext = Depends(get_context),
):
    student, auth = identity
    rows = db.execute(
        select(Attendance, ClassSession, Course)
        .select_from(Attendance)
        .join(ClassSession, Attendance.session_id == ClassSession.session_id)
        .join(ClassSchedule, ClassSession.schedule_id == ClassSchedule.schedule_id)
        .join(Course, ClassSchedule.course_code == Course.course_code)
        .where(Attendance.student_id == student.student_id)
        .order_by(Attendance.taken_at.desc())
        .limit(200)
    ).all()
    return [
        {
            "attendance_id": record.attendance_id,
            "session_id": session.session_id,
            "course_code": course.course_code,
            "course_name": course.course_name,
            "session_date": session.session_date.isoformat(),
            "taken_at": iso_time(record.taken_at, context.settings),
            "status": record.status,
            "verification_id": record.verification_id,
        }
        for record, session, course in rows
    ]


@router.get("/attendance/summary")
def summary(
    identity=Depends(authenticated),
    db=Depends(get_db, scope="function"),
    context: AppContext = Depends(get_context),
):
    student, auth = identity
    if context.settings.demo_mode:
        seed_demo(db, context.now())
    rows = db.execute(
        select(ClassSession, Course)
        .select_from(ClassSession)
        .join(ClassSchedule, ClassSession.schedule_id == ClassSchedule.schedule_id)
        .join(Course, ClassSchedule.course_code == Course.course_code)
        .where(
            ClassSchedule.group_id == student.group_id,
            ClassSession.status != "cancelled",
            ClassSession.session_date <= context.now().date(),
        )
    ).all()
    attended = set(
        db.scalars(
            select(Attendance.session_id).where(
                Attendance.student_id == student.student_id
            )
        )
    )
    counts = {}
    for session, course in rows:
        # Exclude sessions that have not ended, unless attendance was already submitted.
        ended = datetime.combine(session.session_date, session.end_time) < context.now()
        if ended or session.session_id in attended:
            item = counts.setdefault(
                course.course_code,
                {
                    "course_code": course.course_code,
                    "course_name": course.course_name,
                    "attended": 0,
                    "total": 0,
                },
            )
            item["total"] += 1
            item["attended"] += int(session.session_id in attended)
    return [
        {**item, "percentage": round(item["attended"] / item["total"] * 100, 1)}
        for item in counts.values()
    ]
