"""Supporting demo accounts; independent of biometric inference."""

import secrets
from datetime import timedelta

from config import iso_time
from fastapi import APIRouter, Depends, HTTPException
from models import (
    AuthSession,
    Challenge,
    Student,
    StudentGroup,
    VerificationAttempt,
)
from security import digest, hash_password, verify_password
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from .context import AppContext
from .dependencies import authenticated, get_context, get_db
from .schemas import Login, Registration

router = APIRouter(tags=["Demo accounts"])


@router.get("/groups")
def groups(
    db=Depends(get_db, scope="function"), context: AppContext = Depends(get_context)
):
    if not context.settings.demo_mode:
        # Production group assignment is controlled through pre-provisioned student accounts.
        return []
    return [
        {
            "group_id": g.group_id,
            "group_name": g.group_name,
            "programme_code": g.programme_code,
        }
        for g in db.scalars(select(StudentGroup).order_by(StudentGroup.group_id))
    ]


@router.post("/register", status_code=201)
def register(
    data: Registration,
    db=Depends(get_db, scope="function"),
    context: AppContext = Depends(get_context),
):
    if not context.settings.demo_mode:
        raise HTTPException(
            403, "Student accounts must be provisioned by the institution."
        )
    if db.get(StudentGroup, data.group_id) is None:
        raise HTTPException(400, "Choose a valid student group.")
    if db.scalar(
        select(Student).where(
            (Student.student_id == data.student_id) | (Student.email == data.email)
        )
    ):
        raise HTTPException(
            409, "An account with this student ID or email already exists."
        )
    db.add(
        Student(
            student_id=data.student_id,
            group_id=data.group_id,
            name=data.name,
            email=data.email,
            password_hash=hash_password(data.password),
            created_at=context.now(),
        )
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            409, "An account with this student ID or email already exists."
        )
    return {"success": True, "message": "Account created successfully"}


@router.post("/login")
def login(
    data: Login,
    db=Depends(get_db, scope="function"),
    context: AppContext = Depends(get_context),
):
    identifier = data.student_id.strip().upper()
    throttle_key = identifier
    with context.login_lock:
        cutoff = context.now() - timedelta(minutes=15)
        failures = [
            t for t in context.login_failures.get(throttle_key, []) if t > cutoff
        ]
        if len(failures) >= 8:
            raise HTTPException(
                429, "Too many unsuccessful sign-ins. Try again in 15 minutes."
            )
        # Count before doing expensive work so concurrent requests cannot bypass the limit.
        context.login_failures[throttle_key] = failures + [context.now()]
        if len(context.login_failures) > 2000:
            for key in list(context.login_failures):
                if not any(t > cutoff for t in context.login_failures[key]):
                    del context.login_failures[key]
    student = db.scalar(
        select(Student).where(Student.student_id == identifier).with_for_update()
    )
    valid = verify_password(
        data.password, student.password_hash if student else context.dummy_password
    )
    if not student or not valid or student.account_status != "active":
        raise HTTPException(401, "Invalid student ID or password.")
    with context.login_lock:
        context.login_failures.pop(throttle_key, None)
    token = secrets.token_urlsafe(48)
    expires = context.now() + timedelta(hours=context.settings.session_hours)
    db.add(
        AuthSession(
            token_hash=digest(token), student_id=student.student_id, expires_at=expires
        )
    )
    return {
        "success": True,
        "access_token": token,
        "token_type": "bearer",
        "expires_at": iso_time(expires, context.settings),
        "student": context.profile(student, db),
    }


@router.post("/logout")
def logout(
    identity=Depends(authenticated),
    db=Depends(get_db, scope="function"),
    context: AppContext = Depends(get_context),
):
    student, auth = identity
    # Keep token row for challenge foreign keys, but revoke it immediately.
    # MySQL DATETIME has whole-second precision; ensure revocation is already in the past.
    auth.expires_at = context.now() - timedelta(seconds=1)
    for challenge in db.scalars(
        select(Challenge).where(
            Challenge.auth_token_hash == auth.token_hash, Challenge.consumed == False
        )
    ):
        challenge.consumed = True
        root = db.get(VerificationAttempt, challenge.verification_id)
        root.verification_result = "cancelled"
        root.failure_reason = "Signed out before verification completed."
    return {"success": True}


@router.get("/me")
def me(
    identity=Depends(authenticated),
    db=Depends(get_db, scope="function"),
    context: AppContext = Depends(get_context),
):
    student, auth = identity
    return context.profile(student, db)
