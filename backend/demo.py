"""Explicit demo fixtures, never generated when DEMO_MODE is false."""
from datetime import datetime, time, timedelta
from sqlalchemy import select
from models import Programme, StudentGroup, Course, ClassSchedule, ClassSession
from security import digest

DEMO_PIN = '123456'

def seed_demo(db, now):
    # Serialize daily fixture creation when the app loads timetable and summary together.
    programme = db.scalar(select(Programme).where(Programme.programme_code == 'DEMO').with_for_update())
    if programme is None:
        db.add(Programme(programme_code='DEMO', programme_name='Demonstration Computing Programme'))
        db.flush()
    for group_id, name in ((1, 'DEMO-A'), (2, 'DEMO-B')):
        if db.get(StudentGroup, group_id) is None:
            db.add(StudentGroup(group_id=group_id, programme_code='DEMO', group_name=name,
                year_of_study=3, semester=1, academic_year=now.year))
    db.flush()
    fixtures = [('DEMO101', 'Biometric Attendance Lab', 1), ('DEMO102', 'Software Security', 1),
                ('DEMO201', 'Other Group Lab', 2)]
    for index, (code, name, group_id) in enumerate(fixtures, 1):
        if db.get(Course, code) is None:
            db.add(Course(course_code=code, course_name=name, credit_hour=3))
            db.flush()
        if db.get(ClassSchedule, index) is None:
            db.add(ClassSchedule(schedule_id=index, course_code=code, group_id=group_id,
                day_of_week='Demo daily', class_type='Practical', start_time=time(0, 0),
                end_time=time(23, 59, 59), start_date=now.date(), end_date=now.date()+timedelta(days=365),
                lecturer='Demo lecturer'))
            db.flush()
        # A dated session is created only once; existing attendance is never rewritten.
        for days_ago in range(0, 4):
            day = now.date() - timedelta(days=days_ago)
            exists = db.scalar(select(ClassSession).where(ClassSession.schedule_id == index, ClassSession.session_date == day))
            if exists is None:
                db.add(ClassSession(schedule_id=index, session_date=day, start_time=time(0, 0),
                    end_time=time(23, 59, 59), venue='Demo room', status='active' if days_ago == 0 else 'closed',
                    pin_hash=digest(DEMO_PIN if index == 1 else ('654321' if index == 2 else '222222'))))
    db.flush()
