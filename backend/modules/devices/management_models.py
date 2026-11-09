"""Enrollment assurance and operation approvals. No client trust-writing API."""
from datetime import datetime
from sqlalchemy import CheckConstraint, Computed, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from models import Base
from .biometric_models import DeviceBiometricSession


class SchoolProvisionedAccount(Base):
    """Offline school provisioning attestation; runtime has no write permission."""
    __tablename__ = 'school_provisioned_accounts'
    __table_args__ = {'mysql_engine': 'InnoDB'}
    student_id: Mapped[str] = mapped_column(ForeignKey('students.student_id'), primary_key=True)
    provisioning_reference: Mapped[str] = mapped_column(String(255))
    provisioned_at: Mapped[datetime] = mapped_column(DateTime)


class EnrollmentRevision(Base):
    __tablename__ = 'device_enrollment_revisions'
    __table_args__ = (
        CheckConstraint("provenance IN ('external_verified','synthetic_fixture','account_bound_fyp')", name='ck_device_revision_provenance'),
        CheckConstraint("assurance_level IN ('UNVERIFIED','ACCOUNT_BOUND_FYP','INSTITUTION_VERIFIED')", name='ck_device_revision_assurance'),
        UniqueConstraint('current_student', name='uq_device_current_revision'),
        {'mysql_engine': 'InnoDB'},
    )
    revision_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    student_id: Mapped[str] = mapped_column(ForeignKey('students.student_id'), index=True)
    template_hash: Mapped[str] = mapped_column(String(64))
    provenance: Mapped[str] = mapped_column(String(32))
    assurance_level: Mapped[str] = mapped_column(String(32), default='UNVERIFIED', server_default='UNVERIFIED')
    evidence_reference: Mapped[str] = mapped_column(String(255))
    verified_at: Mapped[datetime] = mapped_column(DateTime)
    invalidated_at: Mapped[datetime | None] = mapped_column(DateTime)
    current_student: Mapped[str | None] = mapped_column(String(11),
        Computed('CASE WHEN invalidated_at IS NULL THEN student_id ELSE NULL END', persisted=True))


class EnrollmentObservation(Base):
    """Captures provenance BEFORE scanning; old completed sessions cannot qualify."""
    __tablename__ = 'device_enrollment_observations'
    __table_args__ = {'mysql_engine': 'InnoDB'}
    session_id: Mapped[str] = mapped_column(ForeignKey('device_biometric_sessions.approval_id'), primary_key=True)
    revision_id: Mapped[str] = mapped_column(ForeignKey('device_enrollment_revisions.revision_id'))
    binding: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime)


class DeviceBiometricAuthorization(Base):
    """Separate fresh result AND single-use grant; never the raw B3 session ID."""
    __tablename__ = 'device_biometric_authorizations'
    __table_args__ = {'mysql_engine': 'InnoDB'}
    approval_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    result_id: Mapped[str] = mapped_column(String(64), unique=True)
    source_session_id: Mapped[str] = mapped_column(ForeignKey('device_enrollment_observations.session_id'), unique=True)
    revision_id: Mapped[str] = mapped_column(ForeignKey('device_enrollment_revisions.revision_id'))
    student_id: Mapped[str] = mapped_column(ForeignKey('students.student_id'), index=True)
    binding: Mapped[str] = mapped_column(Text)
    verified_at: Mapped[datetime] = mapped_column(DateTime)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime)


class DeviceTrustEvent(Base):
    __tablename__ = 'device_trust_events'
    __table_args__ = {'mysql_engine': 'InnoDB'}
    event_id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[str] = mapped_column(ForeignKey('students.student_id'), index=True)
    action: Mapped[str] = mapped_column(String(24))
    code: Mapped[str] = mapped_column(String(64))
    revision_id: Mapped[str | None] = mapped_column(String(64))
    authorization_id: Mapped[str | None] = mapped_column(String(64))
    occurred_at: Mapped[datetime] = mapped_column(DateTime)


MANAGEMENT_TABLES = [SchoolProvisionedAccount.__table__, EnrollmentRevision.__table__, EnrollmentObservation.__table__,
                     DeviceBiometricAuthorization.__table__, DeviceTrustEvent.__table__]
