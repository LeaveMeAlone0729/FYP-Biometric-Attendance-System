"""Device biometric TEST sessions; deliberately not trusted approval grants."""
from datetime import datetime
from sqlalchemy import CheckConstraint, Computed, DateTime, ForeignKey, Integer, SmallInteger, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from models import Base
from .pending_models import PendingDeviceRegistration


class DeviceBiometricSession(Base):
    __tablename__ = "device_biometric_sessions"
    __table_args__ = (
        CheckConstraint("stage IN ('FACE','LIVENESS','COMPLETED_UNTRUSTED','FAILED','EXPIRED')", name="ck_device_bio_stage"),
        CheckConstraint("((operation = 'enroll_second_device' AND slot_number = 2) OR (operation = 'replace_device' AND slot_number IN (1,2)))", name="ck_device_bio_purpose"),
        CheckConstraint("valid_frames >= 0 AND valid_frames <= 3 AND frame_count >= 0 AND frame_count <= 60", name="ck_device_bio_frames"),
        CheckConstraint("fingers IS NULL OR (fingers >= 1 AND fingers <= 5)", name="ck_device_bio_fingers"),
        UniqueConstraint("open_pending_id", name="uq_device_bio_open_pending"),
    )
    approval_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    pending_registration_id: Mapped[str] = mapped_column(ForeignKey("pending_device_registrations.pending_registration_id"), index=True)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.student_id"), index=True)
    auth_token_hash: Mapped[str] = mapped_column(ForeignKey("auth_sessions.token_hash"))
    candidate_device_id: Mapped[str] = mapped_column(String(64))
    public_key_fingerprint: Mapped[str] = mapped_column(String(64))
    slot_number: Mapped[int] = mapped_column(SmallInteger, default=2)
    operation: Mapped[str] = mapped_column(String(32), default="enroll_second_device")
    template_binding: Mapped[str] = mapped_column(String(64))
    stage: Mapped[str] = mapped_column(String(24), default="FACE")
    open_pending_id: Mapped[str | None] = mapped_column(String(64), Computed("CASE WHEN stage IN ('FACE','LIVENESS') THEN pending_registration_id ELSE NULL END", persisted=True))
    fingers: Mapped[int | None] = mapped_column(SmallInteger)
    valid_frames: Mapped[int] = mapped_column(Integer, default=0)
    frame_count: Mapped[int] = mapped_column(Integer, default=0)
    frame_hashes: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    failure_code: Mapped[str | None] = mapped_column(String(64))


class DeviceBiometricEvent(Base):
    __tablename__ = "device_biometric_events"
    __table_args__ = (CheckConstraint("result IN ('ISSUED','PASS','FAIL')", name="ck_device_bio_event_result"),)
    event_id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.student_id"), index=True)
    approval_id: Mapped[str | None] = mapped_column(ForeignKey("device_biometric_sessions.approval_id"))
    action: Mapped[str] = mapped_column(String(24))
    result: Mapped[str] = mapped_column(String(10))
    code: Mapped[str] = mapped_column(String(64))
    occurred_at: Mapped[datetime] = mapped_column(DateTime)


BIOMETRIC_TABLES=[DeviceBiometricSession.__table__,DeviceBiometricEvent.__table__]
