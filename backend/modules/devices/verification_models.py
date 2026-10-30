"""Fresh, operation-bound possession checks. No attendance authorization grants."""
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from models import Base
from .models import RegisteredDevice  # Register the Phase 1 FK target.


class DeviceVerificationChallenge(Base):
    __tablename__ = "device_verification_challenges"
    challenge_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.student_id"), index=True)
    auth_token_hash: Mapped[str] = mapped_column(ForeignKey("auth_sessions.token_hash"))
    device_id: Mapped[str] = mapped_column(ForeignKey("registered_devices.device_id"))
    key_fingerprint: Mapped[str] = mapped_column(String(64))
    operation: Mapped[str] = mapped_column(String(40))
    signing_payload: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime)
    result: Mapped[str] = mapped_column(String(20), default="PENDING")
    failure_code: Mapped[str | None] = mapped_column(String(60))


class DeviceVerificationEvent(Base):
    __tablename__ = "device_verification_events"
    event_id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.student_id"), index=True)
    challenge_id: Mapped[str | None] = mapped_column(String(64), index=True)
    device_id: Mapped[str | None] = mapped_column(String(64))
    operation: Mapped[str] = mapped_column(String(40))
    action: Mapped[str] = mapped_column(String(30))
    result: Mapped[str] = mapped_column(String(20))
    code: Mapped[str] = mapped_column(String(60))
    source: Mapped[str] = mapped_column(String(20), default="server")
    occurred_at: Mapped[datetime] = mapped_column(DateTime, index=True)


VERIFICATION_TABLES = [DeviceVerificationChallenge.__table__, DeviceVerificationEvent.__table__]
