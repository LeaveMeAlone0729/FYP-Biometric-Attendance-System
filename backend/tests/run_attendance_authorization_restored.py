"""Opt-in actual REST/crypto on a fresh isolated restored MariaDB database.
Never touches production attendance or production policy. No HTTP fixture bypass.
"""
import argparse,base64,hashlib,json,os,re,secrets,subprocess,sys
from pathlib import Path
from datetime import datetime,timedelta,time
from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from modules.devices.service import DeviceRegistrationError
from modules.authorization.service import AttendanceAuthorizationService
import mysql.connector
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient
from sqlalchemy import inspect,select,func,text
from app import create_app
from config import Settings
from database import make_engine,make_sessions
from models import Programme,StudentGroup,Student,Course,ClassSchedule,ClassSession,Attendance,Challenge,AuthSession
from security import hash_password,encrypt_encoding,digest
from modules.devices.models import RegisteredDevice
from modules.devices.crypto import canonical_public_key
from modules.networks.models import NetworkPolicy,NetworkVerificationEvent
from modules.authorization.models import AttendanceDeviceChallenge,AttendanceAuthorizationEvent
from modules.authorization.migration import upgrade_attendance_authorization_schema
from modules.devices.two_device_migration import verify_original_data
from test_workflow import SyntheticBiometrics

parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--evidence',required=True,type=Path);args=parser.parse_args()
root=Path(__file__).resolve().parents[2];os.chdir(root)
manifest=json.loads(args.evidence.read_text(encoding='utf-8'));folder=Path(manifest['backup_path']);settings=Settings()
assert manifest.get('restored_backup_verified') and manifest.get('p5_restored_migration_verified')
assert settings.db_name==manifest['source_database']
assert hashlib.sha256((folder/'database.sql').read_bytes()).hexdigest()==manifest['sql_sha256']
assert hashlib.sha256((root/'backend/.env').read_bytes()).hexdigest()==manifest['configuration_sha256']
# A historical backup is a valid isolated fixture, not a current production
# baseline: legitimate attendance may have changed since that backup was taken.
# Snapshot every current source table read-only before testing, then compare again.
source_baseline={}
production=make_engine(settings)
try:
    with production.connect() as c:
        for table in inspect(c).get_table_names():
            assert re.fullmatch('[A-Za-z0-9_]+',table)
            columns=[column['name'] for column in inspect(c).get_columns(table)]
            rows=c.exec_driver_sql('SELECT * FROM `'+table+'`').mappings().all()
            encoded=sorted(json.dumps(dict(row),default=str,sort_keys=True,separators=(',',':')).encode() for row in rows)
            source_digest=hashlib.sha256()
            for row in encoded:source_digest.update(len(row).to_bytes(8,'big'));source_digest.update(row)
            source_baseline[table]=dict(columns=columns,count=len(rows),sha256=source_digest.hexdigest())
finally:production.dispose()
schema='attendance_p5_test_'+secrets.token_hex(6)
assert re.fullmatch('attendance_p5_test_[0-9a-f]{12}',schema) and schema!=settings.db_name
control=mysql.connector.connect(host=settings.db_host,port=settings.db_port,user=settings.db_user,password=settings.db_password)
engine=None;created=False;app=None
try:
    with control.cursor() as c:c.execute('CREATE DATABASE `'+schema+'` CHARACTER SET utf8mb4')
    created=True
    env=os.environ.copy();env['MYSQL_PWD']=settings.db_password
    with (folder/'database.sql').open('rb') as source:
        subprocess.run(['C:/xampp/mysql/bin/mysql.exe','--host='+settings.db_host,'--port='+str(settings.db_port),'--user='+settings.db_user,'--default-character-set=utf8mb4','--database='+schema],stdin=source,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True,env=env)
    isolated=replace(settings,db_name=schema,demo_mode=False);engine=make_engine(isolated)
    verify_original_data(engine,manifest['baseline']);migration=upgrade_attendance_authorization_schema(engine)
    assert upgrade_attendance_authorization_schema(engine)['created_tables']==[]
    original={}
    with engine.connect() as c:
        for table in inspect(c).get_table_names():
            assert re.fullmatch('[A-Za-z0-9_]+',table)
            pk=inspect(c).get_pk_constraint(table)['constrained_columns']
            rows=c.exec_driver_sql('SELECT * FROM `'+table+'`').mappings().all()
            original[table]=(pk,{tuple(row[k] for k in pk):dict(row) for row in rows})
    sessions=make_sessions(engine);clock=[datetime(2026,11,1,12)];bio=SyntheticBiometrics()
    app=create_app(isolated,engine,bio,lambda:clock[0]);password_hash=hash_password('isolated-test-password')
    assert app.state.context.engine.url.database!=settings.db_name
    with sessions.begin() as db:
        assert db.scalar(select(func.count()).select_from(NetworkPolicy))==0,'Use a fresh backup with no enabled production simulation policies for this matrix'
        assert db.get(Programme,'P5SIM') is None
        db.add(Programme(programme_code='P5SIM',programme_name='Isolated final authorization tests'));db.flush()
        group=StudentGroup(programme_code='P5SIM',group_name='P5SIM',year_of_study=1,semester=1,academic_year=2026);db.add(group);db.flush();group_id=group.group_id
        db.add(Course(course_code='P5SIM',course_name='Isolated final authorization',credit_hour=1));db.flush()
        schedule=ClassSchedule(course_code='P5SIM',group_id=group_id,day_of_week='Sunday',class_type='Test',start_time=time(10),end_time=time(14),start_date=clock[0].date(),end_date=clock[0].date(),lecturer='Isolated fixture');db.add(schedule);db.flush()
        session=ClassSession(schedule_id=schedule.schedule_id,session_date=clock[0].date(),start_time=time(10),end_time=time(14),venue='Isolated simulation',status='active',pin_hash=digest('765432'));db.add(session);db.flush();class_id=session.session_id
        db.add(NetworkPolicy(network_id='p5-isolated',network_name='Isolated source simulation',network_cidr='192.0.2.0/24',enabled=True,created_at=clock[0],updated_at=clock[0]))
    number=0;cases=[]
    def request(method,path,headers=None,source='192.0.2.10',**kwargs):
        client=TestClient(app,client=(source,12345))
        try:return getattr(client,method)(path,headers=headers or {},**kwargs)
        finally:client.close()
    def fixture(slot=1,status='ACTIVE'):
        global number
        number+=1;identifier='P5T'+str(number).zfill(6);key=ec.generate_private_key(ec.SECP256R1())
        public,fp=canonical_public_key(base64.b64encode(key.public_key().public_bytes(serialization.Encoding.DER,serialization.PublicFormat.SubjectPublicKeyInfo)).decode())
        device_id='p5-disposable-'+secrets.token_hex(12)
        with sessions.begin() as db:
            db.add(Student(student_id=identifier,group_id=group_id,name='Isolated student '+str(number),email=identifier.lower()+'@isolated.test',password_hash=password_hash,face_encoding=encrypt_encoding([0.0]*128,settings.biometric_key),biometric_status='active',account_status='active',consent_at=clock[0],created_at=clock[0]));db.flush()
            db.add(RegisteredDevice(device_id=device_id,student_id=identifier,slot_number=slot,public_key_spki=public,public_key_fingerprint=fp,device_name='Disposable test device',device_model='Software P256 fixture',platform='android',status=status,registered_at=clock[0]))
        login=request('post','/login',json={'student_id':identifier,'password':'isolated-test-password'});assert login.status_code==200,login.text
        return dict(student=identifier,key=key,fp=fp,device=device_id,headers={'Authorization':'Bearer '+login.json()['access_token']})
    def count():
        with sessions() as db:return db.scalar(select(func.count()).select_from(Attendance))
    def frame(f,attempt,image,proof=None,key=None,headers=None,source='192.0.2.10'):
        fields={'challenge_id':attempt}
        if proof:fields.update(device_challenge_id=proof['challenge_id'],device_signature=base64.b64encode((key or f['key']).sign(base64.b64decode(proof['signing_payload']),ec.ECDSA(hashes.SHA256()))).decode())
        return request('post','/liveness/frame',headers or f['headers'],source,data=fields,files={'file':('frame.jpg',image,'image/jpeg')})
    def match_face(f,attempt,face=b'correct-face'):
        matched=request('post','/verify-face',f['headers'],data={'challenge_id':attempt},files={'file':('frame.jpg',face,'image/jpeg')})
        blink_index=0
        for index in range(24):
            if matched.status_code!=200 or matched.json().get('face_verified'):break
            assert matched.json().get('liveness_step')=='head',matched.text
            action=matched.json()['head_action'];clock[0]+=timedelta(milliseconds=500)
            if action=='blink':
                action=('blink_open','blink_closed','blink_reopen')[blink_index%3];blink_index+=1
            pixels=f'head-{action}-{index}'.encode()
            matched=request('post','/verify-face',f['headers'],data={'challenge_id':attempt},files={'file':('frame.jpg',pixels,'image/jpeg')})
        if matched.status_code==200:
            assert matched.json().get('head_movement_verified'),matched.text
            bio.gesture=matched.json()['fingers']
        return matched
    def begin(f,face=b'correct-face'):
        started=request('post','/attendance/start',f['headers'],json={'pin':'765432'});assert started.status_code==200,started.text
        attempt=started.json()['challenge_id']
        matched=match_face(f,attempt,face)
        return attempt,matched
    def proof(f,attempt):return request('post','/api/v1/attendance/device-challenges',f['headers'],json={'attendance_challenge_id':attempt,'public_key_fingerprint':f['fp']})
    def ready(f):
        attempt,matched=begin(f);assert matched.status_code==200,matched.text
        issued=proof(f,attempt);assert issued.status_code==201,issued.text;nonce=issued.json()
        for i in range(2):
            accepted=frame(f,attempt,('accepted-'+str(i)).encode(),nonce);assert accepted.status_code==200,accepted.text
        return attempt,nonce
    def record(name,before,response,delta=0):
        after=count();assert after==before+delta,(name,before,after,response.text)
        cases.append(dict(case=name,http_status=response.status_code,result='PASS' if delta else 'REJECTED',reason=response.json().get('code') or response.json().get('message'),attendance_delta=after-before))
    # Early checks use real REST/crypto and never write Attendance. Final checks
    # still observe policy changes after a genuine successful preflight.
    for mode in ['disabled before camera','policy changed after preflight','valid preflight']:
        f=fixture();before=count()
        started=request('post','/attendance/start',f['headers'],json={'pin':'765432'});assert started.status_code==200
        attempt=started.json()['challenge_id']
        if mode=='disabled before camera':
            with sessions.begin() as db:db.get(NetworkPolicy,'p5-isolated').enabled=False
        early=request('post','/api/v1/attendance/preflight-challenges',f['headers'],json={'attendance_challenge_id':attempt,'public_key_fingerprint':f['fp']})
        if mode=='disabled before camera':
            assert early.status_code==403 and early.json()['code']=='NO_ENABLED_NETWORK_POLICY',early.text
            record('preflight rejects disabled policy before biometrics',before,early)
            with sessions.begin() as db:db.get(NetworkPolicy,'p5-isolated').enabled=True
            continue
        assert early.status_code==201,early.text
        early=early.json();signature=base64.b64encode(f['key'].sign(base64.b64decode(early['signing_payload']),ec.ECDSA(hashes.SHA256()))).decode()
        checked=request('post','/api/v1/attendance/preflight',f['headers'],json={'attendance_challenge_id':attempt,'challenge_id':early['challenge_id'],'signature':signature})
        assert checked.status_code==200 and checked.json()['attendance_authorized']==False,checked.text
        assert count()==before
        if mode=='valid preflight':
            cases.append(dict(case='valid preflight is readiness only',http_status=200,result='PREFLIGHT_PASS',attendance_delta=0));continue
        matched=match_face(f,attempt)
        assert matched.status_code==200,matched.text;bio.gesture=matched.json()['fingers'];nonce=proof(f,attempt).json()
        for i in range(2):assert frame(f,attempt,('preflight-live-'+str(i)).encode(),nonce).status_code==200
        with sessions.begin() as db:db.get(NetworkPolicy,'p5-isolated').enabled=False
        denied=frame(f,attempt,b'preflight-final',nonce)
        assert denied.status_code==403 and denied.json()['code']=='NO_ENABLED_NETWORK_POLICY',denied.text
        record('final writer rejects policy disabled after preflight',before,denied)
        with sessions.begin() as db:db.get(NetworkPolicy,'p5-isolated').enabled=True
    for slot in [1,2]:
        f=fixture(slot);attempt,nonce=ready(f);before=count();result=frame(f,attempt,b'final-success',nonce);assert result.status_code==200,result.text
        record('success from ACTIVE Slot '+str(slot),before,result,1)
        before=count();replayed=frame(f,attempt,b'replay',nonce);assert replayed.status_code==409;record('replayed completed Slot '+str(slot),before,replayed)
        repeated=request('post','/attendance/start',f['headers'],json={'pin':'765432'});assert repeated.status_code==409;record('repeated attendance submission Slot '+str(slot),before,repeated)
    for mode in ['invalid signature','revoked after issue','wrong login','wrong student','unauthorised source','spoofed forwarding','missing policy','disabled policy','invalid policy','localhost','expired proof','missing proof']:
        f=fixture();attempt,nonce=ready(f);before=count();kwargs={};old_clock=clock[0]
        if mode=='invalid signature':kwargs['key']=ec.generate_private_key(ec.SECP256R1())
        elif mode=='revoked after issue':
            with sessions.begin() as db:db.get(RegisteredDevice,f['device']).status='REVOKED'
        elif mode=='wrong login':
            login=request('post','/login',json={'student_id':f['student'],'password':'isolated-test-password'}).json();kwargs['headers']={'Authorization':'Bearer '+login['access_token']}
        elif mode=='wrong student':kwargs['headers']=fixture()['headers']
        elif mode in ['unauthorised source','spoofed forwarding']:
            kwargs['source']='198.51.100.90'
            if mode=='spoofed forwarding':kwargs['headers']={**f['headers'],'X-Forwarded-For':'192.0.2.10'}
        elif mode in ['missing policy','disabled policy','invalid policy']:
            with sessions.begin() as db:
                policy=db.get(NetworkPolicy,'p5-isolated')
                if mode=='invalid policy':db.execute(text("UPDATE network_policies SET network_cidr='invalid' WHERE network_id='p5-isolated'"))
                else:policy.enabled=False
        elif mode=='localhost':kwargs['source']='127.0.0.1'
        elif mode=='expired proof':clock[0]+=timedelta(seconds=61)
        elif mode=='missing proof':nonce=None
        result=frame(f,attempt,('final-'+mode).encode(),nonce,**kwargs);assert result.status_code in (403,409,410),result.text
        record(mode,before,result)
        clock[0]=old_clock
        if mode in ['missing policy','disabled policy','invalid policy']:
            with sessions.begin() as db:
                policy=db.get(NetworkPolicy,'p5-isolated');policy.network_cidr='192.0.2.0/24';policy.enabled=True
    f=fixture();before=count();attempt,result=begin(f,b'other-face');assert result.status_code==400;record('biometric face mismatch',before,result)
    f=fixture();before=count();attempt,_=begin(f);nonce=proof(f,attempt).json();bio.gesture=0
    result=frame(f,attempt,b'wrong-gesture',nonce);assert result.status_code==200 and not result.json()['complete'];record('incorrect live gesture',before,result)
    # Unknown and actually KEY_PROVEN pending keys cannot get an attendance nonce.
    f=fixture();before=count()
    with sessions.begin() as db:db.delete(db.get(RegisteredDevice,f['device']))
    attempt,_=begin(f);result=proof(f,attempt);assert result.status_code==403;record('unknown installation key',before,result)
    f=fixture();candidate=ec.generate_private_key(ec.SECP256R1())
    public,fp=canonical_public_key(base64.b64encode(candidate.public_key().public_bytes(serialization.Encoding.DER,serialization.PublicFormat.SubjectPublicKeyInfo)).decode())
    pending=request('post','/api/v1/devices/pending-registrations',f['headers'],json={'public_key_spki':public,'device_name':'Disposable pending candidate','device_model':'Software fixture','platform':'android'})
    assert pending.status_code==201,pending.text
    pending=pending.json();signature=base64.b64encode(candidate.sign(base64.b64decode(pending['signing_payload']),ec.ECDSA(hashes.SHA256()))).decode()
    proven=request('post','/api/v1/devices/pending-registrations/'+pending['pending_registration_id']+'/proof',f['headers'],json={'signature':signature});assert proven.json()['status']=='KEY_PROVEN'
    before=count();attempt,_=begin(f);result=proof({**f,'key':candidate,'fp':fp},attempt);assert result.status_code==403;record('KEY_PROVEN pending key remains unauthorized',before,result)
    f=fixture();attempt,nonce=ready(f);before=count();fresh=AttendanceAuthorizationService.fresh;calls=0
    def late(service,*args):
        global calls
        calls+=1
        if calls==3:raise DeviceRegistrationError(410,'ATTENDANCE_AUTHORIZATION_EXPIRED','Isolated late insertion expiry')
        return fresh(service,*args)
    with patch.object(AttendanceAuthorizationService,'fresh',late):result=frame(f,attempt,b'late-rollback',nonce)
    assert result.status_code==410,result.text;record('late failure rolls back inserted row',before,result)
    with sessions() as db:assert db.get(AttendanceDeviceChallenge,nonce['challenge_id']).result=='FAIL'
    f=fixture();attempt,nonce=ready(f);before=count()
    with ThreadPoolExecutor(max_workers=2) as pool:responses=list(pool.map(lambda i:frame(f,attempt,('concurrent-'+str(i)).encode(),nonce),range(2)))
    assert sorted(r.status_code for r in responses)==[200,409],[r.text for r in responses]
    record('concurrent final submissions exactly one insertion',before,next(r for r in responses if r.status_code==200),1)
    # Exercise the later phone-test helper against THIS disposable restored copy,
    # not the pristine migration-validation copy or production.
    helper_manifest=root/'.work'/('p5-phone-helper-'+secrets.token_hex(6)+'.json')
    helper_manifest.write_text(json.dumps({**manifest,'restored_database':schema}),encoding='utf-8')
    try:
        helper=subprocess.run([sys.executable,'-B','backend/tests/prepare_attendance_phone_test.py','--evidence',str(helper_manifest),'--student',f['student'],'--cidr','192.0.2.200/32'],check=True,capture_output=True,text=True,encoding='utf-8')
        physical_setup=json.loads(helper.stdout);assert physical_setup['database']==schema and not physical_setup['production_modified']
    finally:helper_manifest.unlink(missing_ok=True)
    # Compare every original restored row by PK, including original attendance/registered keys/templates.
    with engine.connect() as c:
        for table,(pk,rows) in original.items():
            current={tuple(row[k] for k in pk):dict(row) for row in c.exec_driver_sql('SELECT * FROM `'+table+'`').mappings()}
            assert all(current.get(key)==value for key,value in rows.items()),'Original restored records changed: '+table
        inserted=c.execute(select(Attendance.attendance_id,Attendance.student_id,Attendance.session_id,Attendance.verification_id).where(Attendance.student_id.like('P5T%'))).mappings().all()
        assert len(inserted)==3
        audit=c.execute(select(AttendanceAuthorizationEvent.code,AttendanceAuthorizationEvent.result).where(AttendanceAuthorizationEvent.result.in_(['PASS','FAIL']))).mappings().all()
    production=make_engine(settings)
    try:verify_original_data(production,source_baseline)
    finally:production.dispose()
    output=root/'.work'/('p5-restored-integration-'+secrets.token_hex(6)+'.json')
    evidence=dict(database=schema,restored_backup_sha256=manifest['sql_sha256'],migration=migration,cases=cases,inserted_disposable_attendance=[dict(row) for row in inserted],audit=[dict(row) for row in audit],all_failure_attendance_deltas_zero=True,all_original_restored_rows_preserved=True,production_all_original_rows_preserved=True,production_baseline=source_baseline,production_network_policies_added=False,copy_only_phone_setup_verified=True,biometric_inference='controlled fixture; original service state machine/threshold used',device_signatures='real disposable ECDSA P256 SHA256 DER',test_database_dropped_after_completion=True)
    output.write_text(json.dumps(evidence,indent=2,default=str),encoding='utf-8')
    print(json.dumps(dict(result='PASS',cases=len(cases),successful_disposable_attendance=len(inserted),all_failures_inserted_zero=True,evidence=str(output))))
finally:
    if engine:engine.dispose()
    if created:
        assert re.fullmatch('attendance_p5_test_[0-9a-f]{12}',schema) and schema!=settings.db_name
        with control.cursor() as c:c.execute('DROP DATABASE `'+schema+'`')
    control.close()
