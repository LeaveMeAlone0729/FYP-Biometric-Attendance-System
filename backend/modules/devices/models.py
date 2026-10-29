"""Additive Phase 1 tables. No changes to biometric or account records."""
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from models import Base


class RegisteredDevice(Base):
    __tablename__ = "registered_devices"
    device_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    # Phase 1 has no revocation/replacement route: one registration per student.
    student_id: Mapped[str] = mapped_column(ForeignKey("students.student_id"), unique=True)
    public_key_spki: Mapped[str] = mapped_column(Text)
    public_key_fingerprint: Mapped[str] = mapped_column(String(64), unique=True)
    device_name: Mapped[str] = mapped_column(String(100))
    device_model: Mapped[str] = mapped_column(String(150))
    platform: Mapped[str] = mapped_column(String(20), default="android")
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")
    registered_at: Mapped[datetime] = mapped_column(DateTime)


class DeviceRegistrationChallenge(Base):
    __tablename__ = "device_registration_challenges"
    registration_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.student_id"), index=True)
    auth_token_hash: Mapped[str] = mapped_column(ForeignKey("auth_sessions.token_hash"))
    public_key_spki: Mapped[str] = mapped_column(Text)
    public_key_fingerprint: Mapped[str] = mapped_column(String(64))
    device_name: Mapped[str] = mapped_column(String(100))
    device_model: Mapped[str] = mapped_column(String(150))
    signing_payload: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime)


class DeviceRegistrationEvent(Base):
    __tablename__ = "device_registration_events"
    event_id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.student_id"), index=True)
    registration_id: Mapped[str | None] = mapped_column(String(64))
    device_id: Mapped[str | None] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(30))
    outcome: Mapped[str] = mapped_column(String(20))
    code: Mapped[str] = mapped_column(String(60))
    occurred_at: Mapped[datetime] = mapped_column(DateTime, index=True)


DEVICE_TABLES = [RegisteredDevice.__table__, DeviceRegistrationChallenge.__table__,
                 DeviceRegistrationEvent.__table__]
