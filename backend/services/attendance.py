"""Demo attendance completion seam for the eventual combined backend."""

from config import iso_time
from models import Attendance, VerificationAttempt
from sqlalchemy.exc import IntegrityError


def record_verified_attendance(context, db, student, challenge, session):
    """Complete the demo; the combined backend can coordinate teammate checks here."""
    # Called inside the same transaction only after face and liveness checks pass.
    challenge.consumed = True
    challenge.stage = "complete"
    root = db.get(VerificationAttempt, challenge.verification_id)
    root.verification_result = "success"
    root.stage = "complete"
    root.failure_reason = None
    record = Attendance(
        student_id=student.student_id,
        session_id=session.session_id,
        verification_id=root.verification_id,
        taken_at=context.now(),
        status="Present",
    )
    db.add(record)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        context.reject(
            db,
            student.student_id,
            "duplicate",
            "Attendance has already been recorded for this class.",
            session.session_id,
            409,
        )
    return {
        "success": True,
        "complete": True,
        "face_verified": True,
        "liveness_verified": True,
        "attendance_id": record.attendance_id,
        "recorded_at": iso_time(record.taken_at, context.settings),
        "message": "Attendance accepted",
    }
