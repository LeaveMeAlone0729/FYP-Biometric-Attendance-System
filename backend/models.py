"""Proposal entities plus revocable authentication sessions and biometric challenges."""
from datetime import date, datetime, time
from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, Time, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass

class Programme(Base):
    __tablename__ = 'programmes'
    programme_code: Mapped[str] = mapped_column(String(10), primary_key=True)
    programme_name: Mapped[str] = mapped_column(String(150))

class StudentGroup(Base):
    __tablename__ = 'student_groups'
    group_id: Mapped[int] = mapped_column(primary_key=True)
    programme_code: Mapped[str] = mapped_column(ForeignKey('programmes.programme_code'))
    group_name: Mapped[str] = mapped_column(String(20))
    year_of_study: Mapped[int] = mapped_column(Integer)
    semester: Mapped[int] = mapped_column(Integer)
    academic_year: Mapped[int] = mapped_column(Integer)

class Student(Base):
    __tablename__ = 'students'
    student_id: Mapped[str] = mapped_column(String(11), primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey('student_groups.group_id'))
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(150), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    face_encoding: Mapped[str | None] = mapped_column(Text)
    biometric_status: Mapped[str] = mapped_column(String(20), default='not_registered')
    account_status: Mapped[str] = mapped_column(String(20), default='active')
    consent_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime)

class Course(Base):
    __tablename__ = 'courses'
    course_code: Mapped[str] = mapped_column(String(10), primary_key=True)
    course_name: Mapped[str] = mapped_column(String(150))
    credit_hour: Mapped[int] = mapped_column(Integer)

class ClassSchedule(Base):
    __tablename__ = 'class_schedules'
    schedule_id: Mapped[int] = mapped_column(primary_key=True)
    course_code: Mapped[str] = mapped_column(ForeignKey('courses.course_code'))
    group_id: Mapped[int] = mapped_column(ForeignKey('student_groups.group_id'))
    day_of_week: Mapped[str] = mapped_column(String(15))
    class_type: Mapped[str] = mapped_column(String(20))
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    lecturer: Mapped[str] = mapped_column(String(100))

class ClassSession(Base):
    __tablename__ = 'class_sessions'
    __table_args__ = (UniqueConstraint('schedule_id', 'session_date'),)
    session_id: Mapped[int] = mapped_column(primary_key=True)
    schedule_id: Mapped[int] = mapped_column(ForeignKey('class_schedules.schedule_id'))
    session_date: Mapped[date] = mapped_column(Date)
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
    venue: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(20), default='active')
    pin_hash: Mapped[str] = mapped_column(String(64))

class VerificationAttempt(Base):
    __tablename__ = 'verification_attempts'
    verification_id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[str] = mapped_column(ForeignKey('students.student_id'), index=True)
    session_id: Mapped[int | None] = mapped_column(ForeignKey('class_sessions.session_id'))
    verification_result: Mapped[str] = mapped_column(String(20))
    stage: Mapped[str] = mapped_column(String(30))
    attempted_at: Mapped[datetime] = mapped_column(DateTime)
    failure_reason: Mapped[str | None] = mapped_column(String(255))
    face_distance: Mapped[float | None] = mapped_column(Float)

class Attendance(Base):
    __tablename__ = 'attendance'
    __table_args__ = (UniqueConstraint('session_id', 'student_id', name='one_attendance_per_session'),)
    attendance_id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey('class_sessions.session_id'))
    student_id: Mapped[str] = mapped_column(ForeignKey('students.student_id'), index=True)
    verification_id: Mapped[int] = mapped_column(ForeignKey('verification_attempts.verification_id'))
    taken_at: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(20))

class AuthSession(Base):
    __tablename__ = 'auth_sessions'
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    student_id: Mapped[str] = mapped_column(ForeignKey('students.student_id'))
    expires_at: Mapped[datetime] = mapped_column(DateTime)

class Challenge(Base):
    __tablename__ = 'verification_challenges'
    challenge_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    student_id: Mapped[str] = mapped_column(ForeignKey('students.student_id'))
    session_id: Mapped[int] = mapped_column(ForeignKey('class_sessions.session_id'))
    auth_token_hash: Mapped[str] = mapped_column(ForeignKey('auth_sessions.token_hash'))
    verification_id: Mapped[int] = mapped_column(ForeignKey('verification_attempts.verification_id'))
    stage: Mapped[str] = mapped_column(String(20), default='face')
    fingers: Mapped[int | None] = mapped_column(Integer)
    valid_frames: Mapped[int] = mapped_column(Integer, default=0)
    frame_hashes: Mapped[str] = mapped_column(Text, default='[]')
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    consumed: Mapped[bool] = mapped_column(Boolean, default=False)
