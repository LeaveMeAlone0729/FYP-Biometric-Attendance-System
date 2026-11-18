"""Existing installations retain biometric and attendance data during upgrades."""
import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import create_engine, inspect, select, text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from database import make_sessions
from demo import seed_demo
from migrate import upgrade_schema
from modules.biometrics.migration import retire_liveness_column
from models import Attendance, AuthSession, Base, ClassSession, Student, VerificationAttempt


class MigrationTests(unittest.TestCase):
    def test_retiring_pad_column_preserves_existing_challenges(self):
        engine = create_engine('sqlite://')
        try:
            with engine.begin() as connection:
                connection.execute(text('CREATE TABLE verification_challenges (challenge_id TEXT PRIMARY KEY, consumed BOOLEAN, face_liveness_state TEXT)'))
                connection.execute(text("INSERT INTO verification_challenges VALUES ('existing', 0, 'obsolete runtime scores')"))
            self.assertEqual(retire_liveness_column(engine), ['verification_challenges.face_liveness_state'])
            self.assertEqual(retire_liveness_column(engine), [])
            with engine.connect() as connection:
                self.assertEqual(tuple(connection.execute(text('SELECT * FROM verification_challenges')).one()), ('existing', 0))
            self.assertNotIn('face_liveness_state', {c['name'] for c in inspect(engine).get_columns('verification_challenges')})
        finally:
            engine.dispose()

    def test_fresh_schema_and_empty_database_need_no_pad_column(self):
        engine = create_engine('sqlite://')
        try:
            self.assertEqual(retire_liveness_column(engine), [])
            Base.metadata.create_all(engine)
            self.assertNotIn('face_liveness_state', {c['name'] for c in inspect(engine).get_columns('verification_challenges')})
            self.assertEqual(retire_liveness_column(engine), [])
        finally:
            engine.dispose()

    def test_retiring_device_columns_preserves_biometrics_sessions_and_attendance(self):
        engine = create_engine('sqlite://')
        current = datetime(2026, 10, 29, 12)
        Base.metadata.create_all(engine)
        sessions = make_sessions(engine)
        try:
            with engine.begin() as connection:
                connection.execute(text('ALTER TABLE students ADD COLUMN device_hash VARCHAR(64)'))
                connection.execute(text("ALTER TABLE auth_sessions ADD COLUMN device_hash VARCHAR(64) NOT NULL DEFAULT 'legacy'"))
            with sessions.begin() as db:
                seed_demo(db, current)
                db.add(Student(student_id='MIGRATE001', group_id=1, name='Migration Student',
                    email='migration@example.test', password_hash='password-hash',
                    face_encoding='encrypted-template', biometric_status='active',
                    consent_at=current, created_at=current))
                db.flush()
                db.add(AuthSession(token_hash='a'*64, student_id='MIGRATE001', expires_at=current+timedelta(hours=8)))
                session = db.scalar(select(ClassSession))
                attempt = VerificationAttempt(student_id='MIGRATE001', session_id=session.session_id,
                    stage='complete', verification_result='success', attempted_at=current)
                db.add(attempt)
                db.flush()
                db.add(Attendance(student_id='MIGRATE001', session_id=session.session_id,
                    verification_id=attempt.verification_id, taken_at=current, status='Present'))
            self.assertEqual(upgrade_schema(engine), ['students.device_hash', 'auth_sessions.device_hash'])
            self.assertEqual(upgrade_schema(engine), [])
            for table in ('students', 'auth_sessions'):
                self.assertNotIn('device_hash', {c['name'] for c in inspect(engine).get_columns(table)})
            with sessions.begin() as db:
                student = db.get(Student, 'MIGRATE001')
                self.assertEqual(student.face_encoding, 'encrypted-template')
                self.assertEqual(student.password_hash, 'password-hash')
                self.assertEqual(student.consent_at, current)
                self.assertIsNotNone(db.get(AuthSession, 'a'*64))
                self.assertEqual(db.scalar(select(Attendance)).status, 'Present')
                # A fresh login must work after removing the legacy NOT NULL column.
                db.add(AuthSession(token_hash='b'*64, student_id=student.student_id, expires_at=current+timedelta(hours=8)))
        finally:
            engine.dispose()
