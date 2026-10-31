"""Stage B2 candidates and audit only; pending rows are never trusted devices."""
from datetime import datetime
from sqlalchemy import CheckConstraint, Computed, DateTime, ForeignKey, Index, SmallInteger, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from models import Base
from .models import RegisteredDevice  # Register the Slot 1 FK target before DDL.


class PendingDeviceRegistration(Base):
    __tablename__ = "pending_device_registrations"
    __table_args__ = (
        CheckConstraint("slot_number = 2", name="ck_pending_device_slot"),
        CheckConstraint("operation = 'enroll_second_device'", name="ck_pending_device_operation"),
        CheckConstraint("status IN ('CHALLENGE_ISSUED','KEY_PROVEN','FAILED','EXPIRED','ACTIVATED')", name="ck_pending_device_status"),
        UniqueConstraint("student_id", "open_slot", name="uq_pending_device_student_slot"),
        Index("ix_pending_device_student_created", "student_id", "created_at"),
    )
    pending_registration_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    candidate_device_id: Mapped[str] = mapped_column(String(64), unique=True)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.student_id"))
    auth_token_hash: Mapped[str] = mapped_column(ForeignKey("auth_sessions.token_hash"))
    slot_one_device_id: Mapped[str] = mapped_column(ForeignKey("registered_devices.device_id"))
    slot_number: Mapped[int] = mapped_column(SmallInteger, default=2, server_default="2")
    operation: Mapped[str] = mapped_column(String(32), default="enroll_second_device")
    public_key_spki: Mapped[str] = mapped_column(Text)
    public_key_fingerprint: Mapped[str] = mapped_column(String(64))
    device_name: Mapped[str] = mapped_column(String(100))
    device_model: Mapped[str] = mapped_column(String(150))
    signing_payload: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), default="CHALLENGE_ISSUED")
    open_slot: Mapped[int | None] = mapped_column(SmallInteger, Computed(
        "CASE WHEN status IN ('CHALLENGE_ISSUED','KEY_PROVEN') THEN slot_number ELSE NULL END", persisted=True))
    created_at: Mapped[datetime] = mapped_column(DateTime)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    challenge_expires_at: Mapped[datetime] = mapped_column(DateTime)
    challenge_consumed_at: Mapped[datetime | None] = mapped_column(DateTime)
    key_proven_at: Mapped[datetime | None] = mapped_column(DateTime)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime)


class DeviceEnrollmentEvent(Base):
    __tablename__ = "device_enrollment_events"
    __table_args__ = (CheckConstraint("result IN ('ISSUED','PASS','FAIL','INFO')", name="ck_enrollment_event_result"),)
    event_id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.student_id"), index=True)
    pending_registration_id: Mapped[str | None] = mapped_column(ForeignKey("pending_device_registrations.pending_registration_id"))
    action: Mapped[str] = mapped_column(String(32))
    result: Mapped[str] = mapped_column(String(10))
    code: Mapped[str] = mapped_column(String(64))
    occurred_at: Mapped[datetime] = mapped_column(DateTime)


PENDING_TABLES = [PendingDeviceRegistration.__table__, DeviceEnrollmentEvent.__table__]
