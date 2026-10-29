"""Shared persistence, audit and challenge rules used by the demo modules."""

import secrets
import threading

from config import iso_time
from database import make_sessions
from fastapi import HTTPException
from models import (
    Challenge,
    ClassSchedule,
    ClassSession,
    StudentGroup,
    VerificationAttempt,
)
from security import hash_password
from sqlalchemy import select


class AppContext:
    def __init__(self, settings, engine, biometrics, clock):
        self.settings = settings
        self.engine = engine
        self.bio = biometrics
        self.now = clock
        self.sessions = make_sessions(engine)
        self.login_failures = {}
        self.login_lock = threading.Lock()
        # Equalize unknown-account and wrong-password verification cost.
        self.dummy_password = hash_password(secrets.token_urlsafe(24))

    def audit(self, db, student_id, stage, reason, session_id=None, result="failed"):
        attempt = VerificationAttempt(
            student_id=student_id,
            session_id=session_id,
            stage=stage,
            verification_result=result,
            failure_reason=reason,
            attempted_at=self.now(),
        )
        db.add(attempt)
        db.flush()
        return attempt

    def reject(
        self, db, student_id, stage, reason, session_id=None, status=400, challenge=None
    ):
        if challenge:
            challenge.consumed = True
            root = db.get(VerificationAttempt, challenge.verification_id)
            root.verification_result = "failed"
            root.failure_reason = reason
            root.stage = stage
        self.audit(db, student_id, stage, reason, session_id)
        db.commit()  # Failed attempts must survive the HTTP exception rollback.
        raise HTTPException(status, reason)

    def session_open(self, session, student, db):
        schedule = db.get(ClassSchedule, session.schedule_id)
        current = self.now()
        return (
            schedule.group_id == student.group_id
            and session.status == "active"
            and session.session_date == current.date()
            and session.start_time <= current.time() <= session.end_time
            and schedule.start_date <= current.date() <= schedule.end_date
        )

    def get_challenge(self, identifier, expected_stage, db, student, auth):
        challenge = db.scalar(
            select(Challenge)
            .where(Challenge.challenge_id == identifier)
            .with_for_update()
        )
        if (
            challenge is None
            or challenge.student_id != student.student_id
            or challenge.auth_token_hash != auth.token_hash
        ):
            self.reject(
                db,
                student.student_id,
                expected_stage,
                "This verification request is not valid.",
                status=403,
            )
        if challenge.consumed:
            self.reject(
                db,
                student.student_id,
                expected_stage,
                "This verification has already ended. Start again.",
                challenge.session_id,
                409,
            )
        if challenge.expires_at <= self.now():
            self.reject(
                db,
                student.student_id,
                expected_stage,
                "Verification timed out. Enter the attendance PIN again.",
                challenge.session_id,
                410,
                challenge,
            )
        if challenge.stage != expected_stage:
            self.reject(
                db,
                student.student_id,
                expected_stage,
                "Complete the verification steps in order.",
                challenge.session_id,
                409,
            )
        session = db.get(ClassSession, challenge.session_id)
        if not self.session_open(session, student, db):
            self.reject(
                db,
                student.student_id,
                "session",
                "The class attendance window is closed.",
                session.session_id,
                409,
                challenge,
            )
        return challenge, session

    def profile(self, student, db):
        group = db.get(StudentGroup, student.group_id)
        return {
            "student_id": student.student_id,
            "name": student.name,
            "email": student.email,
            "group_id": group.group_id,
            "group_name": group.group_name,
            "programme_code": group.programme_code,
            "biometric_status": student.biometric_status,
            "consent_at": iso_time(student.consent_at, self.settings),
        }
