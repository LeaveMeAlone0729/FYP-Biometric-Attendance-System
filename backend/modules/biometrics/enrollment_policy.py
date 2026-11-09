from database_compat import shared_read
"""Opt-in, lower-assurance FYP enrollment. Never institutional identity proof."""
import hashlib
import secrets
from fastapi import HTTPException
from sqlalchemy import select
from models import AuthSession
from modules.devices.management_models import (
    SchoolProvisionedAccount, EnrollmentRevision, DeviceTrustEvent)
from modules.devices.management_approval import available


def enabled(context):
    return getattr(context.settings, 'fyp_account_bound_enrollment', False) is True


def check_first_enrollment(context, db, student, auth):
    if not enabled(context):
        return None
    if not available(db):
        raise HTTPException(503, 'Account-bound enrollment storage is unavailable.')
    # Student is already locked by register_face; lock order matches device flows.
    current = db.scalar(select(AuthSession).where(
        AuthSession.token_hash == (auth.token_hash if auth else '')
    ).with_for_update().execution_options(populate_existing=True))
    if (student is None or current is None or current.student_id != student.student_id
            or current.expires_at <= context.now() or student.account_status != 'active'):
        raise HTTPException(401, 'A valid student session is required for enrollment.')
    school = db.scalar(select(SchoolProvisionedAccount).where(
        SchoolProvisionedAccount.student_id == student.student_id
    ).with_for_update(read=shared_read(db)).execution_options(populate_existing=True))
    if (school is None or not school.provisioning_reference.strip()
            or school.provisioned_at > context.now()):
        raise HTTPException(403, 'Only school-provisioned accounts may enroll under the FYP policy.')
    # Any revision history, even invalidated, prevents reset/re-enrollment.
    if db.scalar(select(EnrollmentRevision.revision_id).where(
            EnrollmentRevision.student_id == student.student_id).limit(1)) is not None:
        raise HTTPException(409, 'First enrollment is permanent. Recovery is outside this application.')
    return school


def record_first_enrollment(context, db, student, auth, school):
    if school is None:
        return
    # Revalidate expiry after potentially slow inference, before recording success.
    check_first_enrollment(context, db, student, auth)
    now = context.now()
    revision = EnrollmentRevision(revision_id=secrets.token_urlsafe(32),
        student_id=student.student_id,
        template_hash=hashlib.sha256(student.face_encoding.encode()).hexdigest(),
        provenance='account_bound_fyp', assurance_level='ACCOUNT_BOUND_FYP',
        evidence_reference=school.provisioning_reference, verified_at=now)
    db.add(revision)
    db.add(DeviceTrustEvent(student_id=student.student_id, action='first_enrollment',
        code='ACCOUNT_BOUND_FYP_ENROLLED', revision_id=revision.revision_id, occurred_at=now))
    db.flush()  # Template, consent, provenance and audit commit atomically via get_db.
