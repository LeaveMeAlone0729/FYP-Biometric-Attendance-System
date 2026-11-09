"""Optional, isolated metadata: importing this module cannot migrate core tables."""
from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from models import Student, AuthSession, ClassSession, Challenge
from modules.authorization.models import AttendanceDeviceChallenge
from modules.devices.models import RegisteredDevice


class ClassroomBase(DeclarativeBase):
    pass


class Classroom(ClassroomBase):
    __tablename__ = 'wifi_classrooms'
    classroom_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime)


class WifiPolicy(ClassroomBase):
    __tablename__ = 'classroom_wifi_policies'
    policy_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    classroom_id: Mapped[str] = mapped_column(ForeignKey(Classroom.classroom_id), index=True)
    bssid: Mapped[str] = mapped_column(String(17))
    ssid: Mapped[str | None] = mapped_column(String(32))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    retired_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime)


class WifiChallenge(ClassroomBase):
    __tablename__ = 'classroom_wifi_challenges'
    __table_args__ = (UniqueConstraint('student_id', 'device_id', 'evidence_hash', name='uq_wifi_observation'),)
    challenge_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    student_id: Mapped[str] = mapped_column(ForeignKey(Student.student_id), index=True)
    auth_token_hash: Mapped[str] = mapped_column(ForeignKey(AuthSession.token_hash))
    device_id: Mapped[str] = mapped_column(ForeignKey(RegisteredDevice.device_id))
    key_fingerprint: Mapped[str] = mapped_column(String(64))
    classroom_id: Mapped[str] = mapped_column(ForeignKey(Classroom.classroom_id))
    operation: Mapped[str] = mapped_column(String(40))
    signing_payload: Mapped[str] = mapped_column(Text)
    evidence_hash: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime)
    result: Mapped[str] = mapped_column(String(20), default='PENDING')
    failure_code: Mapped[str | None] = mapped_column(String(60))


class WifiEvent(ClassroomBase):
    __tablename__ = 'classroom_wifi_events'
    event_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[str] = mapped_column(ForeignKey(Student.student_id), index=True)
    challenge_id: Mapped[str | None] = mapped_column(String(64))
    device_id: Mapped[str | None] = mapped_column(String(64))
    classroom_id: Mapped[str | None] = mapped_column(String(64))
    result: Mapped[str] = mapped_column(String(20))
    reason_code: Mapped[str] = mapped_column(String(60))
    matched_policy_id: Mapped[str | None] = mapped_column(String(64))
    evidence_hash: Mapped[str | None] = mapped_column(String(64))
    verified_at: Mapped[datetime] = mapped_column(DateTime)


class WifiPolicyEvent(ClassroomBase):
    __tablename__ = 'classroom_wifi_policy_events'
    event_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    policy_id: Mapped[str] = mapped_column(String(64))
    actor: Mapped[str] = mapped_column(String(100))
    action: Mapped[str] = mapped_column(String(20))
    snapshot: Mapped[str] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(DateTime)


class SessionClassroom(ClassroomBase):
    __tablename__ = 'session_classroom_requirements'
    session_id: Mapped[int] = mapped_column(ForeignKey(ClassSession.session_id), primary_key=True)
    classroom_id: Mapped[str | None] = mapped_column(ForeignKey(Classroom.classroom_id))
    revision: Mapped[int] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(DateTime)


class AttemptClassroom(ClassroomBase):
    __tablename__ = 'attempt_classroom_requirements'
    attempt_id: Mapped[str] = mapped_column(ForeignKey(Challenge.challenge_id), primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey(ClassSession.session_id))
    classroom_id: Mapped[str | None] = mapped_column(ForeignKey(Classroom.classroom_id))
    revision: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime)


class AttendanceWifiBinding(ClassroomBase):
    __tablename__ = 'attendance_wifi_bindings'
    challenge_id: Mapped[str] = mapped_column(ForeignKey(WifiChallenge.challenge_id), primary_key=True)
    attempt_id: Mapped[str] = mapped_column(ForeignKey(AttemptClassroom.attempt_id), index=True)
    device_challenge_id: Mapped[str] = mapped_column(ForeignKey(AttendanceDeviceChallenge.challenge_id))
    purpose: Mapped[str] = mapped_column(String(40))
    # Short-lived normalized observation retained for final policy re-evaluation,
    # not an image or trusted RF measurement. Bound by the verified signature.
    evidence: Mapped[str | None] = mapped_column(Text)
    used_at: Mapped[datetime | None] = mapped_column(DateTime)
