"""Add fictional, realistic academic fixtures without replacing existing records.

Run with DEMO_MODE=true. Historical records are explicitly marked sample_data;
they are presentation fixtures, never evidence of successful biometric testing.
"""
import argparse
from datetime import date, datetime, time, timedelta
from pathlib import Path

from sqlalchemy import func, select

from config import Settings, local_now
from database import make_engine, make_sessions
from models import (Attendance, ClassSchedule, ClassSession, Course, Programme,
                    Student, StudentGroup, VerificationAttempt)
from security import digest, hash_password

TERM_START = date(2026, 9, 28)
TERM_END = date(2026, 12, 18)
PASSWORD = 'CampusAttend2026!'
PROGRAMMES = (
    ('BIT', 'Bachelor of Information Technology (Honours)'),
    ('BCS', 'Bachelor of Computer Science (Honours)'),
)
COURSES = (
    ('BMIT3173', 'Mobile Application Development', 3),
    ('BMIT3093', 'Information Security', 3),
    ('BMIT2023', 'Database Management Systems', 3),
    ('BMIT3063', 'Software Engineering', 3),
    ('BMCS3013', 'Artificial Intelligence', 3),
    ('BMCS3023', 'Computer Networks', 3),
)
# Fictional names and identifiers; example.test addresses never contact real people.
ROSTERS = (
    ('BIT', 'RIT3S1-G1', '24WMR100', (
        ('Aiman Hakim bin Zulkifli', 'aiman.hakim'),
        ('Tan Wei Jie', 'weijie.tan'),
        ('Nur Aisyah binti Rahman', 'aisyah.rahman'),
        ('Lim Xin Yi', 'xinyi.lim'),
        ('Kavinesh a/l Suresh', 'kavinesh.suresh'),
        ('Chong Jia En', 'jiaen.chong'),
        ('Muhammad Danish bin Azlan', 'danish.azlan'),
        ('Wong Kai Wen', 'kaiwen.wong'),
        ('Priya a/p Rajendran', 'priya.rajendran'),
        ('Siti Nur Iman binti Salleh', 'iman.salleh'),
        ('Lee Jun Hao', 'junhao.lee'),
        ('Soh Mei Ling', 'meiling.soh'),
    )),
    ('BIT', 'RIT3S1-G2', '24WMR101', (
        ('Farah Nabila binti Ismail', 'farah.ismail'),
        ('Ng Zi Xuan', 'zixuan.ng'),
        ('Arvind a/l Krishnan', 'arvind.krishnan'),
        ('Teoh Pei Shan', 'peishan.teoh'),
        ('Amirul Haziq bin Roslan', 'haziq.roslan'),
        ('Goh Yu Heng', 'yuheng.goh'),
        ('Nurul Syafiqah binti Hassan', 'syafiqah.hassan'),
        ('Liew Wen Qi', 'wenqi.liew'),
        ('Harshini a/p Mohan', 'harshini.mohan'),
        ('Ahmad Firdaus bin Kamal', 'firdaus.kamal'),
        ('Yap Zhi Ming', 'zhiming.yap'),
        ('Chua Hui Min', 'huimin.chua'),
    )),
    ('BCS', 'RCS3S1-G1', '24WCS100', (
        ('Siti Balqis binti Abdullah', 'balqis.abdullah'),
        ('Ong Jun Wei', 'junwei.ong'),
        ('Darshini a/p Kumar', 'darshini.kumar'),
        ('Chew Xin Rou', 'xinrou.chew'),
        ('Muhammad Irfan bin Fauzi', 'irfan.fauzi'),
        ('Low Zhen Yu', 'zhenyu.low'),
        ('Nur Amirah binti Yusof', 'amirah.yusof'),
        ('Heng Jia Hui', 'jiahui.heng'),
        ('Viknesh a/l Raman', 'viknesh.raman'),
        ('Nur Sabrina binti Hamid', 'sabrina.hamid'),
        ('Ho Wei Sheng', 'weisheng.ho'),
        ('Lau Qian Yi', 'qianyi.lau'),
    )),
)
# group, course, weekday (Monday=0), start, end, type, venue, lecturer, PIN
TIMETABLE = (
    (0, 'BMIT3173', 0, 9, 11, 'Practical', 'ICT Lab B204', 'Dr. Faridah Osman', '482731'),
    (0, 'BMIT3093', 1, 10, 12, 'Lecture', 'Lecture Hall A201', 'Mr. Adrian Tan', '619284'),
    (0, 'BMIT2023', 2, 14, 16, 'Practical', 'ICT Lab B206', 'Ms. Kavitha Nair', '735916'),
    (0, 'BMIT3063', 3, 9, 11, 'Tutorial', 'Tutorial Room C103', 'Dr. Melissa Wong', '294853'),
    (1, 'BMIT3173', 0, 14, 16, 'Practical', 'ICT Lab B204', 'Dr. Faridah Osman', '563817'),
    (1, 'BMIT3093', 1, 14, 16, 'Lecture', 'Lecture Hall A201', 'Mr. Adrian Tan', '847295'),
    (1, 'BMIT2023', 2, 9, 11, 'Practical', 'ICT Lab B206', 'Ms. Kavitha Nair', '316948'),
    (1, 'BMIT3063', 4, 10, 12, 'Tutorial', 'Tutorial Room C103', 'Dr. Melissa Wong', '928461'),
    (2, 'BMCS3013', 0, 11, 13, 'Lecture', 'Lecture Hall A203', 'Dr. Kelvin Lim', '671429'),
    (2, 'BMCS3023', 1, 9, 11, 'Practical', 'Network Lab B301', 'Mr. Hafiz Rahman', '453982'),
    (2, 'BMIT2023', 3, 14, 16, 'Practical', 'ICT Lab B206', 'Ms. Kavitha Nair', '892637'),
    (2, 'BMIT3063', 4, 14, 16, 'Tutorial', 'Tutorial Room C103', 'Dr. Melissa Wong', '247519'),
)


def seed_sample(db, as_of):
    """Insert missing rows only. Caller owns the transaction; safe to rerun."""
    for code, name in PROGRAMMES:
        existing = db.get(Programme, code)
        if existing and existing.programme_name != name:
            raise ValueError(f'Programme code collision: {code}')
        if existing is None:
            db.add(Programme(programme_code=code, programme_name=name))
    for code, name, credits in COURSES:
        existing = db.get(Course, code)
        if existing and (existing.course_name != name or existing.credit_hour != credits):
            raise ValueError(f'Course code collision: {code}')
        if existing is None:
            db.add(Course(course_code=code, course_name=name, credit_hour=credits))
    db.flush()
    groups, students = [], []
    for programme, name, prefix, roster in ROSTERS:
        group = db.scalar(select(StudentGroup).where(
            StudentGroup.programme_code == programme, StudentGroup.group_name == name,
            StudentGroup.academic_year == 2026, StudentGroup.year_of_study == 3,
            StudentGroup.semester == 1))
        if group is None:
            group = StudentGroup(programme_code=programme, group_name=name,
                                 academic_year=2026, year_of_study=3, semester=1)
            db.add(group)
            db.flush()
        groups.append(group)
        members = []
        for index, (full_name, email_name) in enumerate(roster, 1):
            identifier = prefix + f'{index:02}'
            email = email_name + '@student.example.test'
            student = db.get(Student, identifier)
            if student and (student.name, student.email, student.group_id) != (full_name, email, group.group_id):
                raise ValueError(f'Student ID collision: {identifier}')
            if student is None:
                if db.scalar(select(Student).where(Student.email == email)):
                    raise ValueError(f'Email collision: {email}')
                student = Student(student_id=identifier, group_id=group.group_id, name=full_name,
                    email=email, password_hash=hash_password(PASSWORD),
                    account_status='inactive' if index == 11 else 'active',
                    created_at=datetime(2026, 10, 26, 8) if index == 10 else datetime(2026, 9, 21, 8))
                db.add(student)
            members.append(student)
        students.append(members)
    db.flush()

    for slot, (group_index, code, weekday, start, end, kind, venue, lecturer, pin) in enumerate(TIMETABLE):
        group = groups[group_index]
        schedule = db.scalar(select(ClassSchedule).where(
            ClassSchedule.group_id == group.group_id, ClassSchedule.course_code == code,
            ClassSchedule.day_of_week == (TERM_START + timedelta(days=weekday)).strftime('%A'),
            ClassSchedule.start_time == time(start), ClassSchedule.end_time == time(end),
            ClassSchedule.start_date == TERM_START, ClassSchedule.end_date == TERM_END,
            ClassSchedule.class_type == kind, ClassSchedule.lecturer == lecturer))
        if schedule is None:
            schedule = ClassSchedule(group_id=group.group_id, course_code=code,
                day_of_week=(TERM_START + timedelta(days=weekday)).strftime('%A'),
                start_time=time(start), end_time=time(end), start_date=TERM_START,
                end_date=TERM_END, class_type=kind, lecturer=lecturer)
            db.add(schedule)
            db.flush()
        day = TERM_START + timedelta(days=weekday)
        week = 0
        while day <= TERM_END:
            session = db.scalar(select(ClassSession).where(
                ClassSession.schedule_id == schedule.schedule_id, ClassSession.session_date == day))
            created_session = session is None
            if created_session:
                session = ClassSession(schedule_id=schedule.schedule_id, session_date=day,
                    start_time=time(start), end_time=time(end), venue=venue,
                    status='closed' if day < as_of else 'active', pin_hash=digest(pin))
                db.add(session)
                db.flush()
            # Never fill a session whose metadata has been changed by an operator.
            compatible = (session.start_time == time(start) and session.end_time == time(end)
                          and session.status != 'cancelled' and session.pin_hash == digest(pin))
            if day < as_of and compatible:
                for member_index, student in enumerate(students[group_index]):
                    if day < student.created_at.date() or member_index == 9:
                        continue  # New enrolment has no invented attendance history.
                    # Deterministic variation includes strong and low-attendance students.
                    score = (week * 7 + slot * 3 + member_index * 11) % 20
                    threshold = 20 if member_index == 0 else (11 if member_index == 8 else 17)
                    present = score < threshold
                    stamp = datetime.combine(day, time(start)) + timedelta(minutes=2 + member_index % 7)
                    if present:
                        existing = db.scalar(select(Attendance).where(
                            Attendance.student_id == student.student_id, Attendance.session_id == session.session_id))
                        if existing is None:
                            attempt = VerificationAttempt(student_id=student.student_id,
                                session_id=session.session_id, verification_result='success', stage='sample_data',
                                attempted_at=stamp - timedelta(seconds=10),
                                failure_reason='[SAMPLE] Imported fictional attendance; no biometric verification performed.')
                            db.add(attempt)
                            db.flush()
                            db.add(Attendance(student_id=student.student_id, session_id=session.session_id,
                                verification_id=attempt.verification_id, taken_at=stamp, status='Present'))
                    else:
                        reason = '[SAMPLE] Simulated unsuccessful verification; no attendance recorded.'
                        existing = db.scalar(select(VerificationAttempt).where(
                            VerificationAttempt.student_id == student.student_id,
                            VerificationAttempt.session_id == session.session_id,
                            VerificationAttempt.stage == 'sample_data', VerificationAttempt.failure_reason == reason))
                        if existing is None:
                            db.add(VerificationAttempt(student_id=student.student_id, session_id=session.session_id,
                                verification_result='failed', stage='sample_data', attempted_at=stamp, failure_reason=reason))
                    db.flush()
            day += timedelta(days=7)
            week += 1
    return groups


def write_accounts(path):
    lines = ['ATTENDANCE SYSTEM - FICTIONAL TEST ACCOUNTS',
        'All names, identifiers, course details and history are synthetic sample data.',
        'Initial password for the accounts below: ' + PASSWORD,
        'Sign in using Student ID. Passwords in the database are PBKDF2 hashes.',
        'Face templates, consent and login tokens are NOT seeded.',
        'Register your own face before camera testing.',
        'Only student login is implemented. Admin/lecturer RBAC is NOT implemented.',
        'Lecturer names in the timetable are descriptive records, not login accounts.',
        'Existing account passwords and face registrations are preserved on rerun.', '',
        'STUDENT ID   | FULL NAME | GROUP | STATUS / TEST SCENARIO']
    for _, group, prefix, roster in ROSTERS:
        for index, (name, _) in enumerate(roster, 1):
            scenario = ('Inactive: login must fail' if index == 11 else
                        'New enrolment: empty history' if index == 10 else
                        'Lower attendance history' if index == 9 else
                        'Full attendance history' if index == 1 else 'Active: varied attendance history')
            lines.append(f'{prefix}{index:02} | {name} | {group} | {scenario}')
    lines += ['', 'CLASS PINS (Kuala Lumpur time; valid only within the dated class window)',
              'Term: 28 September - 18 December 2026. Sessions include 2 November testing week.',
              'PINs repeat weekly for convenient testing; there is no all-day bypass.']
    for gi, code, weekday, start, end, _, venue, lecturer, pin in TIMETABLE:
        day = (TERM_START + timedelta(days=weekday)).strftime('%A')
        lines.append(f'{ROSTERS[gi][1]} | {code} | {day} {start:02}:00-{end:02}:00 | {pin} | {venue} | {lecturer}')
    lines += ['', 'Sample history is tagged verification_attempts.stage=sample_data.',
              'Missing attendance represents absence; percentages are calculated by the existing API.',
              'These records must not be reported as observed biometric test results.']
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--as-of', type=date.fromisoformat,
                        help='Generate historical records strictly before this date (default: local today).')
    parser.add_argument('--accounts-file', type=Path,
                        default=Path(__file__).resolve().parents[1] / '.work' / 'testing-accounts.txt')
    args = parser.parse_args()
    settings = Settings()
    if not settings.demo_mode:
        parser.error('Sample data requires DEMO_MODE=true. No records were changed.')
    as_of = args.as_of or local_now(settings).date()
    if as_of > local_now(settings).date():
        parser.error('--as-of cannot be in the future.')
    engine = make_engine(settings)
    try:
        with make_sessions(engine).begin() as db:
            seed_sample(db, as_of)
        write_accounts(args.accounts_file)
        with make_sessions(engine)() as db:
            for cls in (Programme, StudentGroup, Student, Course, ClassSchedule, ClassSession, Attendance, VerificationAttempt):
                print(f'{cls.__tablename__}: {db.scalar(select(func.count()).select_from(cls))} total rows')
        print(f'Sample data committed to {settings.db_name}; history before {as_of}.')
        print(f'Testing accounts: {args.accounts_file.resolve()}')
    finally:
        engine.dispose()


if __name__ == '__main__':
    main()
