from datetime import datetime
from sqlalchemy import CheckConstraint,Computed,DateTime,ForeignKey,Index,String,Text,UniqueConstraint
from sqlalchemy.orm import Mapped,mapped_column
from models import Base
from modules.devices.models import RegisteredDevice
from modules.networks.models import NetworkVerificationEvent

class AttendanceDeviceChallenge(Base):
    __tablename__='attendance_device_challenges'
    __table_args__=(
        CheckConstraint("operation='attendance_authorization'",name='ck_attendance_device_purpose'),
        CheckConstraint("result IN ('PENDING','PASS','FAIL')",name='ck_attendance_device_result'),
        CheckConstraint("(result='PENDING' AND consumed_at IS NULL) OR (result<>'PENDING' AND consumed_at IS NOT NULL)",name='ck_attendance_device_consumption'),
        UniqueConstraint('open_attendance_id',name='uq_attendance_device_open_attempt'),)
    challenge_id: Mapped[str]=mapped_column(String(64),primary_key=True)
    student_id: Mapped[str]=mapped_column(ForeignKey('students.student_id'))
    auth_token_hash: Mapped[str]=mapped_column(ForeignKey('auth_sessions.token_hash'))
    attendance_challenge_id: Mapped[str]=mapped_column(ForeignKey('verification_challenges.challenge_id'))
    session_id: Mapped[int]=mapped_column(ForeignKey('class_sessions.session_id'))
    device_id: Mapped[str]=mapped_column(ForeignKey('registered_devices.device_id'))
    key_fingerprint: Mapped[str]=mapped_column(String(64))
    operation: Mapped[str]=mapped_column(String(32),default='attendance_authorization')
    signing_payload: Mapped[str]=mapped_column(Text)
    created_at: Mapped[datetime]=mapped_column(DateTime)
    expires_at: Mapped[datetime]=mapped_column(DateTime)
    consumed_at: Mapped[datetime | None]=mapped_column(DateTime)
    result: Mapped[str]=mapped_column(String(10),default='PENDING')
    failure_code: Mapped[str | None]=mapped_column(String(64))
    open_attendance_id: Mapped[str | None]=mapped_column(String(64),Computed("CASE WHEN consumed_at IS NULL THEN attendance_challenge_id ELSE NULL END",persisted=True))

class AttendanceAuthorizationEvent(Base):
    __tablename__='attendance_authorization_events'
    __table_args__=(CheckConstraint("result IN ('ISSUED','PASS','FAIL')",name='ck_attendance_auth_result'),Index('ix_attendance_auth_student_time','student_id','occurred_at'))
    event_id: Mapped[int]=mapped_column(primary_key=True)
    student_id: Mapped[str]=mapped_column(ForeignKey('students.student_id'))
    auth_token_hash: Mapped[str]=mapped_column(ForeignKey('auth_sessions.token_hash'))
    attendance_challenge_id: Mapped[str | None]=mapped_column(ForeignKey('verification_challenges.challenge_id'))
    device_challenge_id: Mapped[str | None]=mapped_column(ForeignKey('attendance_device_challenges.challenge_id'))
    device_id: Mapped[str | None]=mapped_column(ForeignKey('registered_devices.device_id'))
    network_verification_id: Mapped[int | None]=mapped_column(ForeignKey('network_verification_events.verification_id'))
    action: Mapped[str]=mapped_column(String(20))
    result: Mapped[str]=mapped_column(String(10))
    code: Mapped[str]=mapped_column(String(64))
    occurred_at: Mapped[datetime]=mapped_column(DateTime)

AUTHORIZATION_TABLES=[AttendanceDeviceChallenge.__table__,AttendanceAuthorizationEvent.__table__]
