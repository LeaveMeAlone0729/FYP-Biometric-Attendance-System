"""Future activation storage. Never created by application startup."""
from datetime import datetime
from sqlalchemy import CheckConstraint, Computed, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from models import Base
from .pending_models import PendingDeviceRegistration


class DeviceActivationChallenge(Base):
    __tablename__ = "device_activation_challenges"
    __table_args__ = (
        CheckConstraint("((operation = 'enroll_second_device' AND slot_number = 2) OR (operation = 'replace_device' AND slot_number IN (1,2)))", name="ck_activation_purpose"),
        CheckConstraint("result IN ('PENDING','PASS','FAIL')", name="ck_activation_result"),
        CheckConstraint("(result = 'PENDING' AND consumed_at IS NULL) OR (result <> 'PENDING' AND consumed_at IS NOT NULL)", name="ck_activation_consumption"),
        UniqueConstraint("open_pending_id", name="uq_activation_open_pending"),
    )
    challenge_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.student_id"), index=True)
    auth_token_hash: Mapped[str] = mapped_column(ForeignKey("auth_sessions.token_hash"))
    pending_registration_id: Mapped[str] = mapped_column(ForeignKey("pending_device_registrations.pending_registration_id"))
    candidate_device_id: Mapped[str] = mapped_column(String(64))
    public_key_fingerprint: Mapped[str] = mapped_column(String(64))
    approval_id: Mapped[str] = mapped_column(String(64))
    trusted_template_revision_id: Mapped[str] = mapped_column(String(128))
    operation: Mapped[str] = mapped_column(String(32), default="enroll_second_device")
    slot_number: Mapped[int] = mapped_column(default=2)
    signing_payload: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime)
    result: Mapped[str] = mapped_column(String(10), default="PENDING")
    failure_code: Mapped[str | None] = mapped_column(String(64))
    open_pending_id: Mapped[str | None] = mapped_column(String(64), Computed(
        "CASE WHEN consumed_at IS NULL THEN pending_registration_id ELSE NULL END", persisted=True))


class DeviceActivationEvent(Base):
    __tablename__ = "device_activation_events"
    __table_args__ = (CheckConstraint("result IN ('ISSUED','PASS','FAIL')", name="ck_activation_event_result"),)
    event_id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.student_id"), index=True)
    pending_registration_id: Mapped[str | None] = mapped_column(ForeignKey("pending_device_registrations.pending_registration_id"))
    challenge_id: Mapped[str | None] = mapped_column(ForeignKey("device_activation_challenges.challenge_id"))
    action: Mapped[str] = mapped_column(String(32))
    result: Mapped[str] = mapped_column(String(10))
    code: Mapped[str] = mapped_column(String(64))
    occurred_at: Mapped[datetime] = mapped_column(DateTime)


ACTIVATION_TABLES = [DeviceActivationChallenge.__table__, DeviceActivationEvent.__table__]
