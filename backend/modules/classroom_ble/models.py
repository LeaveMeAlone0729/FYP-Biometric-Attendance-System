from datetime import datetime
from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from models import Student, AuthSession
from modules.devices.models import RegisteredDevice
from modules.classroom_wifi.models import Classroom


class BleBase(DeclarativeBase): pass


class BlePolicy(BleBase):
    __tablename__='classroom_ble_policies'
    __table_args__=(CheckConstraint('minimum_samples BETWEEN 3 AND 50',name='ck_ble_sample_count'),
        CheckConstraint('rssi_threshold BETWEEN -127 AND 0',name='ck_ble_threshold'),
        CheckConstraint('max_age_seconds BETWEEN 10 AND 30',name='ck_ble_age'),
        CheckConstraint('simulation_only=1',name='ck_ble_simulation'))
    policy_id: Mapped[str]=mapped_column(String(64),primary_key=True)
    classroom_id: Mapped[str]=mapped_column(ForeignKey(Classroom.classroom_id),index=True)
    service_uuid: Mapped[str]=mapped_column(String(36))
    label: Mapped[str | None]=mapped_column(String(100))
    enabled: Mapped[bool]=mapped_column(Boolean,default=False,server_default=text('0'))
    minimum_samples: Mapped[int]=mapped_column(Integer,default=5)
    rssi_threshold: Mapped[int]=mapped_column(Integer,default=-65)
    max_age_seconds: Mapped[int]=mapped_column(Integer,default=15)
    simulation_only: Mapped[bool]=mapped_column(Boolean,default=True)
    revision: Mapped[int]=mapped_column(Integer,default=1)
    created_at: Mapped[datetime]=mapped_column(DateTime)
    updated_at: Mapped[datetime]=mapped_column(DateTime)
    retired_at: Mapped[datetime | None]=mapped_column(DateTime)


class BleChallenge(BleBase):
    __tablename__='classroom_ble_challenges'
    __table_args__=(UniqueConstraint('student_id','device_id','evidence_hash',name='uq_ble_observation'),)
    challenge_id: Mapped[str]=mapped_column(String(64),primary_key=True)
    student_id: Mapped[str]=mapped_column(ForeignKey(Student.student_id),index=True)
    auth_token_hash: Mapped[str]=mapped_column(ForeignKey(AuthSession.token_hash))
    device_id: Mapped[str]=mapped_column(ForeignKey(RegisteredDevice.device_id))
    key_fingerprint: Mapped[str]=mapped_column(String(64))
    classroom_id: Mapped[str]=mapped_column(ForeignKey(Classroom.classroom_id))
    operation: Mapped[str]=mapped_column(String(40))
    policy_hash: Mapped[str]=mapped_column(String(64))
    signing_payload: Mapped[str]=mapped_column(Text)
    evidence_hash: Mapped[str | None]=mapped_column(String(64))
    created_at: Mapped[datetime]=mapped_column(DateTime)
    expires_at: Mapped[datetime]=mapped_column(DateTime)
    consumed_at: Mapped[datetime | None]=mapped_column(DateTime)
    result: Mapped[str]=mapped_column(String(20),default='PENDING')
    failure_code: Mapped[str | None]=mapped_column(String(64))


class BleEvent(BleBase):
    __tablename__='classroom_ble_events'
    event_id: Mapped[int]=mapped_column(Integer,primary_key=True)
    student_id: Mapped[str]=mapped_column(ForeignKey(Student.student_id),index=True)
    challenge_id: Mapped[str | None]=mapped_column(String(64))
    classroom_id: Mapped[str | None]=mapped_column(String(64))
    device_id: Mapped[str | None]=mapped_column(String(64))
    result: Mapped[str]=mapped_column(String(20))
    reason_code: Mapped[str]=mapped_column(String(64))
    matched_policy_id: Mapped[str | None]=mapped_column(String(64))
    sample_count: Mapped[int | None]=mapped_column(Integer)
    median_rssi: Mapped[str | None]=mapped_column(String(16))
    evidence_hash: Mapped[str | None]=mapped_column(String(64))
    occurred_at: Mapped[datetime]=mapped_column(DateTime)


class BlePolicyEvent(BleBase):
    __tablename__='classroom_ble_policy_events'
    event_id: Mapped[int]=mapped_column(Integer,primary_key=True)
    policy_id: Mapped[str]=mapped_column(String(64))
    actor: Mapped[str]=mapped_column(String(100))
    action: Mapped[str]=mapped_column(String(20))
    snapshot: Mapped[str]=mapped_column(Text)
    occurred_at: Mapped[datetime]=mapped_column(DateTime)
