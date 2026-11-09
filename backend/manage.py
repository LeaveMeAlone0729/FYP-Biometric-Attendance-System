"""Local operator tools; administrative actions are never exposed to student clients."""
import argparse
import getpass
import re
from datetime import date, time
from sqlalchemy import select
from config import Settings, local_now
from database import make_engine, make_sessions
from models import ClassSchedule, ClassSession, Course, Programme, Student, StudentGroup
from security import digest, hash_password


def create_class_session(db,*,group_id,course_code,course_name,session_date,start,end,venue,lecturer,pin):
    """Existing operator creation workflow, shared with the isolated test wrapper."""
    if not db.get(StudentGroup,group_id):raise ValueError('Group not found.')
    if not re.fullmatch(r'\d{6}',pin):raise ValueError('Use a six-digit PIN.')
    if end<=start:raise ValueError('End time must be after start time on the same day.')
    if not re.fullmatch(r'[A-Za-z0-9]{1,10}',course_code):raise ValueError('Use a course code with up to 10 letters/digits.')
    existing=db.scalars(select(ClassSession).join(ClassSchedule).where(
        ClassSchedule.group_id==group_id,ClassSession.session_date==session_date,
        ClassSession.pin_hash==digest(pin),ClassSession.status=='active')).all()
    if any(s.start_time<end and s.end_time>start for s in existing):
        raise ValueError('An overlapping session for this group already uses this PIN.')
    if not db.get(Course,course_code):
        db.add(Course(course_code=course_code,course_name=course_name,credit_hour=3));db.flush()
    schedule=ClassSchedule(course_code=course_code,group_id=group_id,
        day_of_week=session_date.strftime('%A'),class_type='Lecture',start_time=start,end_time=end,
        start_date=session_date,end_date=session_date,lecturer=lecturer)
    db.add(schedule);db.flush()
    session=ClassSession(schedule_id=schedule.schedule_id,session_date=session_date,start_time=start,
        end_time=end,venue=venue,status='active',pin_hash=digest(pin))
    db.add(session)
    return session

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    group = commands.add_parser('create-group')
    group.add_argument('--programme-code', required=True)
    group.add_argument('--programme-name', required=True)
    group.add_argument('--name', required=True)
    group.add_argument('--year-of-study', type=int, required=True)
    group.add_argument('--semester', type=int, required=True)
    group.add_argument('--academic-year', type=int, required=True)
    student = commands.add_parser('create-student')
    student.add_argument('student_id')
    student.add_argument('--name', required=True)
    student.add_argument('--email', required=True)
    student.add_argument('--group-id', type=int, required=True)
    session = commands.add_parser('create-session')
    session.add_argument('--group-id', type=int, required=True)
    session.add_argument('--course-code', required=True)
    session.add_argument('--course-name', required=True)
    session.add_argument('--date', type=date.fromisoformat, required=True)
    session.add_argument('--start', type=time.fromisoformat, required=True)
    session.add_argument('--end', type=time.fromisoformat, required=True)
    session.add_argument('--venue', required=True)
    session.add_argument('--lecturer', required=True)
    session.add_argument('--pin', required=True)
    args = parser.parse_args()
    settings = Settings(); current = local_now(settings)
    engine = make_engine(settings)
    with make_sessions(engine).begin() as db:
        if args.command == 'create-group':
            if not re.fullmatch(r'[A-Za-z0-9]{1,10}', args.programme_code): raise SystemExit('Invalid programme code.')
            if not 1 <= len(args.name.strip()) <= 20: raise SystemExit('Group name must contain 1–20 characters.')
            if min(args.year_of_study, args.semester, args.academic_year) < 1: raise SystemExit('Use positive year and semester values.')
            if not db.get(Programme, args.programme_code):
                db.add(Programme(programme_code=args.programme_code, programme_name=args.programme_name)); db.flush()
            group = StudentGroup(programme_code=args.programme_code, group_name=args.name.strip(),
                year_of_study=args.year_of_study, semester=args.semester, academic_year=args.academic_year)
            db.add(group); db.flush()
            print(f'Academic group created. group_id={group.group_id}')
        elif args.command == 'create-student':
            if not db.get(StudentGroup, args.group_id): raise SystemExit('Group not found.')
            if not re.fullmatch(r'[A-Za-z0-9]{3,11}', args.student_id): raise SystemExit('Invalid student ID.')
            if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', args.email): raise SystemExit('Invalid email.')
            if db.get(Student, args.student_id.upper()): raise SystemExit('Student already exists.')
            password = getpass.getpass('Initial password (at least 8 characters): ')
            if len(password) < 8 or len(password) > 128: raise SystemExit('Use 8–128 password characters.')
            db.add(Student(student_id=args.student_id.upper(), group_id=args.group_id, name=args.name.strip(),
                email=args.email.strip().lower(), password_hash=hash_password(password), created_at=current))
            print('Student account created.')
        elif args.command == 'create-session':
            try:create_class_session(db,group_id=args.group_id,course_code=args.course_code,
                course_name=args.course_name,session_date=args.date,start=args.start,end=args.end,
                venue=args.venue,lecturer=args.lecturer,pin=args.pin)
            except ValueError as exc:raise SystemExit(str(exc)) from None
            print('Dated class session created. Share the attendance PIN with the class when its window opens.')
    engine.dispose()

if __name__ == '__main__': main()
