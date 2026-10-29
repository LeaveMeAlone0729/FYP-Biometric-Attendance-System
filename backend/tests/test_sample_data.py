"""Relational and preservation checks for the fictional presentation dataset."""
import sys
import unittest
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import create_engine, event, func, select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from database import make_sessions
from models import (Attendance, Base, ClassSchedule, ClassSession, Course, Programme,
                    Student, StudentGroup, VerificationAttempt)
from seed_sample import PASSWORD, seed_sample
from security import verify_password


class SampleDataTests(unittest.TestCase):
    def test_history_integrity_rerun_and_existing_record_preservation(self):
        engine = create_engine('sqlite://')
        @event.listens_for(engine, 'connect')
        def enable_foreign_keys(connection, _):
            connection.execute('PRAGMA foreign_keys=ON')
        Base.metadata.create_all(engine)
        sessions = make_sessions(engine)
        try:
            with sessions.begin() as db:
                db.add(Programme(programme_code='OTHER', programme_name='Existing programme'))
                db.flush()
                old_group = StudentGroup(programme_code='OTHER', group_name='Existing group',
                    academic_year=2026, year_of_study=1, semester=1)
                db.add(old_group)
                db.flush()
                db.add(Student(student_id='EXISTING', name='Existing student', email='existing@example.test',
                    group_id=old_group.group_id, password_hash='unchanged', created_at=datetime(2026, 1, 1)))
            with sessions.begin() as db:
                seed_sample(db, date(2026, 10, 29))
            with sessions.begin() as db:
                self.assertEqual(db.scalar(select(func.count()).select_from(Student)), 37)
                self.assertEqual(db.scalar(select(func.count()).select_from(ClassSchedule)), 12)
                self.assertEqual(db.scalar(select(func.count()).select_from(ClassSession)), 144)
                for student in db.scalars(select(Student).where(Student.student_id != 'EXISTING')):
                    self.assertTrue(verify_password(PASSWORD, student.password_hash))
                    self.assertIsNone(student.face_encoding)
                    self.assertIsNone(student.consent_at)
                for record in db.scalars(select(Attendance)):
                    session = db.get(ClassSession, record.session_id)
                    schedule = db.get(ClassSchedule, session.schedule_id)
                    student = db.get(Student, record.student_id)
                    attempt = db.get(VerificationAttempt, record.verification_id)
                    self.assertEqual(student.group_id, schedule.group_id)
                    self.assertLess(session.session_date, date(2026, 10, 29))
                    self.assertEqual(record.taken_at.date(), session.session_date)
                    self.assertLessEqual(session.start_time, record.taken_at.time())
                    self.assertLessEqual(record.taken_at.time(), session.end_time)
                    self.assertEqual((attempt.student_id, attempt.session_id), (record.student_id, record.session_id))
                    self.assertEqual(attempt.stage, 'sample_data')
                    self.assertIsNone(attempt.face_distance)
                for identifier in ('24WMR10010', '24WMR10110', '24WCS10010'):
                    self.assertEqual(db.scalar(select(func.count()).select_from(Attendance).where(Attendance.student_id == identifier)), 0)
                self.assertGreater(db.scalar(select(func.count()).select_from(VerificationAttempt).where(
                    VerificationAttempt.verification_result == 'failed')), 0)
                counts = {table.name: db.scalar(select(func.count()).select_from(table)) for table in Base.metadata.sorted_tables}
                # Simulate a student setting a password and enrolling between runs.
                student = db.get(Student, '24WMR10001')
                student.password_hash = 'student-changed-password'
                student.face_encoding = 'existing-encrypted-template'
            with sessions.begin() as db:
                seed_sample(db, date(2026, 10, 29))
            with sessions() as db:
                self.assertEqual(counts, {table.name: db.scalar(select(func.count()).select_from(table)) for table in Base.metadata.sorted_tables})
                self.assertEqual(db.get(Student, 'EXISTING').password_hash, 'unchanged')
                student = db.get(Student, '24WMR10001')
                self.assertEqual(student.password_hash, 'student-changed-password')
                self.assertEqual(student.face_encoding, 'existing-encrypted-template')
            # A conflicting existing course must roll back the whole transaction.
            with sessions.begin() as db:
                db.get(Course, 'BMIT3173').course_name = 'Existing custom course'
            with self.assertRaisesRegex(ValueError, 'Course code collision'):
                with sessions.begin() as db:
                    seed_sample(db, date(2026, 10, 29))
            with sessions() as db:
                self.assertEqual(db.get(Course, 'BMIT3173').course_name, 'Existing custom course')
                self.assertEqual(counts, {table.name: db.scalar(select(func.count()).select_from(table)) for table in Base.metadata.sorted_tables})
        finally:
            engine.dispose()


if __name__ == '__main__':
    unittest.main()
