"""Optional later phone test setup: metadata/policy ONLY in the verified restored copy.
Never updates a student, device, key, face template or attendance row.
"""
import argparse,getpass,json,re,secrets,sys
from pathlib import Path
from datetime import datetime,timedelta,time
from dataclasses import replace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sqlalchemy import text
from config import Settings,local_now
from database import make_engine,make_sessions
from models import Student,Course,ClassSchedule,ClassSession
from security import digest
from modules.networks.cidr import parse_cidr
from modules.networks.policies import put_policy

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--evidence',required=True,type=Path);parser.add_argument('--student',required=True)
parser.add_argument('--cidr',required=True,help='Explicit observed lab source /32 or /128; never a guessed campus range')
args=parser.parse_args();evidence=json.loads(args.evidence.read_text(encoding='utf-8'))
target=evidence['restored_database'];source=evidence['source_database']
if not evidence.get('p5_restored_migration_verified') or not re.fullmatch('attendance_p5_(?:restore|test)_[0-9a-f]{12}',target) or target==source:
    raise RuntimeError('Only the verified isolated restored copy is allowed')
network=parse_cidr(args.cidr)
if network.is_loopback:raise RuntimeError('Loopback is never an authorised network source')
settings=replace(Settings(),db_name=target,demo_mode=False);engine=make_engine(settings)
try:
    with make_sessions(engine).begin() as db:
        if db.scalar(text('SELECT DATABASE()'))!=target:raise RuntimeError('Wrong database')
        student=db.get(Student,args.student)
        if student is None or not student.face_encoding or student.biometric_status!='active':raise RuntimeError('An existing enrolled student in the restored copy is required')
        now=local_now(settings);start=max(now-timedelta(minutes=5),datetime.combine(now.date(),time.min));end=min(now+timedelta(minutes=30),datetime.combine(now.date(),time(23,59,59)))
        course_id='H'+secrets.token_hex(4).upper();pin=str(secrets.randbelow(1000000)).zfill(6)
        db.add(Course(course_code=course_id,course_name='Isolated home Wi-Fi attendance test',credit_hour=1));db.flush()
        schedule=ClassSchedule(course_code=course_id,group_id=student.group_id,day_of_week=now.strftime('%A'),class_type='Lab test',start_time=start.time(),end_time=end.time(),start_date=now.date(),end_date=now.date(),lecturer='Isolated test');db.add(schedule);db.flush()
        session=ClassSession(schedule_id=schedule.schedule_id,session_date=now.date(),start_time=start.time(),end_time=end.time(),venue='Controlled home simulation',status='active',pin_hash=digest(pin));db.add(session)
        policy=put_policy(db,network_id='home-sim-'+secrets.token_hex(6),name='Explicit isolated home Wi-Fi simulation',cidr=str(network),enabled=True,actor='isolated-test:'+getpass.getuser(),now=now)
        db.flush();result=dict(database=target,student=args.student,test_pin=pin,class_session_id=session.session_id,policy_id=policy.network_id,source_cidr=policy.network_cidr,class_expires_at=end.isoformat(),production_modified=False)
    print(json.dumps(result))
finally:engine.dispose()
