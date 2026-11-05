"""Additive network tables; no attendance/biometric/device-row changes."""
from datetime import datetime
from sqlalchemy import Boolean,CheckConstraint,DateTime,ForeignKey,Index,String,Text
from sqlalchemy.orm import Mapped,mapped_column,validates
from models import Base
from .cidr import canonical_cidr

class NetworkPolicy(Base):
    __tablename__='network_policies'
    __table_args__=(CheckConstraint('enabled IN (0,1)',name='ck_network_policy_enabled'),)
    network_id: Mapped[str]=mapped_column(String(64),primary_key=True)
    network_name: Mapped[str]=mapped_column(String(100))
    network_cidr: Mapped[str]=mapped_column(String(45))
    enabled: Mapped[bool]=mapped_column(Boolean,default=False,server_default='0')
    created_at: Mapped[datetime]=mapped_column(DateTime)
    updated_at: Mapped[datetime]=mapped_column(DateTime)
    @validates('network_cidr')
    def valid_cidr(self,key,value):return canonical_cidr(value)

class NetworkVerificationEvent(Base):
    __tablename__='network_verification_events'
    __table_args__=(
        CheckConstraint("result IN ('PASS','FAIL')",name='ck_network_event_result'),
        CheckConstraint("(result='PASS' AND matched_policy_id IS NOT NULL AND source_ip IS NOT NULL AND policy_cidr IS NOT NULL) OR (result='FAIL' AND matched_policy_id IS NULL)",name='ck_network_pass_binding'),
        CheckConstraint("(operation='network_diagnostic' AND attendance_attempt_id IS NULL) OR (operation='attendance_authorization' AND attendance_attempt_id IS NOT NULL)",name='ck_network_event_operation'),
        Index('ix_network_event_student_time','student_id','verified_at'),)
    verification_id: Mapped[int]=mapped_column(primary_key=True)
    student_id: Mapped[str]=mapped_column(ForeignKey('students.student_id'))
    auth_token_hash: Mapped[str]=mapped_column(ForeignKey('auth_sessions.token_hash'))
    operation: Mapped[str]=mapped_column(String(32))
    attendance_attempt_id: Mapped[str | None]=mapped_column(String(64))
    source_ip: Mapped[str | None]=mapped_column(String(45))
    result: Mapped[str]=mapped_column(String(4))
    reason_code: Mapped[str]=mapped_column(String(64))
    matched_policy_id: Mapped[str | None]=mapped_column(ForeignKey('network_policies.network_id'))
    policy_cidr: Mapped[str | None]=mapped_column(String(45))
    policy_updated_at: Mapped[datetime | None]=mapped_column(DateTime)
    verified_at: Mapped[datetime]=mapped_column(DateTime)

class NetworkPolicyEvent(Base):
    __tablename__='network_policy_events'
    event_id: Mapped[int]=mapped_column(primary_key=True)
    network_id: Mapped[str]=mapped_column(ForeignKey('network_policies.network_id'))
    actor: Mapped[str]=mapped_column(String(128))
    action: Mapped[str]=mapped_column(String(20))
    previous_value: Mapped[str | None]=mapped_column(Text)
    new_value: Mapped[str]=mapped_column(Text)
    occurred_at: Mapped[datetime]=mapped_column(DateTime)

NETWORK_TABLES=[NetworkPolicy.__table__,NetworkVerificationEvent.__table__,NetworkPolicyEvent.__table__]
