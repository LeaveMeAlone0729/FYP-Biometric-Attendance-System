"""Opt-in real HTTP + MariaDB + Flutter integration. No production fixture switch.
Run this script explicitly. Only a new disposable DB and loopback ephemeral port
are accepted. Actual production endpoints are used without adding test routes.
"""
import argparse
import os,sys,json,secrets,re,socket,threading,subprocess,time,hashlib
from pathlib import Path
from dataclasses import replace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import mysql.connector
import uvicorn
from sqlalchemy import select
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from config import Settings,local_now
from database import make_engine
from models import Student,Attendance
from security import hash_password,encrypt_encoding
from modules.devices.models import RegisteredDevice
from modules.devices.activation_models import DeviceActivationChallenge
from modules.devices.pending_models import PendingDeviceRegistration
from modules.devices.crypto import canonical_public_key
import test_device_verification as verification
from test_device_activation import FixtureProvider,FixtureRevision,FixtureResult,FixtureGrant
from datetime import timedelta

root=Path(__file__).resolve().parents[2]
os.chdir(root)
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--replacement-slot',type=int,choices=(1,2));args=parser.parse_args()
replacement_slot=args.replacement_slot
settings=Settings();schema='attendance_slot2_e2e_'+secrets.token_hex(6)
if not re.fullmatch('attendance_slot2_e2e_[0-9a-f]{12}',schema) or schema==settings.db_name:raise RuntimeError('Unsafe isolated DB')
folder=root/'.work'/('slot2-e2e-'+secrets.token_hex(6));folder.mkdir(parents=True)
subprocess.run(['icacls',str(folder),'/inheritance:r','/grant:r',os.environ['USERNAME']+':(OI)(CI)F'],check=True,capture_output=True)
control=mysql.connector.connect(host=settings.db_host,port=settings.db_port,user=settings.db_user,password=settings.db_password)
h=None;server=None;thread=None;engine=None;created=False
try:
 with control.cursor() as c:c.execute('CREATE DATABASE `'+schema+'` CHARACTER SET utf8mb4')
 created=True;engine=make_engine(replace(settings,db_name=schema))
 h=verification.DeviceVerificationTests();h.engine_override=engine;h.password_hash=hash_password('test-password');h.setUp()
 h.fixture.settings=replace(h.fixture.settings,db_name=schema)
 h.fixture.app.state.context.settings=h.fixture.settings
 h.fixture.app.state.settings=h.fixture.settings
 if h.fixture.app.state.context.engine.url.database!=schema or h.fixture.settings.db_name==settings.db_name:
  raise RuntimeError('Fixture engine/configuration must be isolated')
 h.fixture.now=local_now(settings).replace(microsecond=0);h.fixture.app.state.context.bio.gesture=3
 with h.sessions.begin() as db:
  student=db.get(Student,'DEVICE001');student.face_encoding=encrypt_encoding([0.0]*128,h.fixture.settings.biometric_key);student.biometric_status='active'
  slot_one=db.get(RegisteredDevice,h.device_id);slot_one.device_name='Samsung fixture';slot_one.device_model='SM-A346E fixture'
  db.add(FixtureRevision(revision_id='revision-1',student_id='DEVICE001',template_hash=hashlib.sha256(student.face_encoding.encode()).hexdigest(),trusted=True))
 def slot_one_state():
  with h.sessions() as db:
   row=db.get(RegisteredDevice,h.device_id)
   return {col.name:getattr(row,col.name) for col in RegisteredDevice.__table__.columns}
 if replacement_slot:
  old_key=ec.generate_private_key(ec.SECP256R1())
  old_public=old_key.public_key().public_bytes(serialization.Encoding.DER,serialization.PublicFormat.SubjectPublicKeyInfo)
  old_public,old_fingerprint=canonical_public_key(__import__('base64').b64encode(old_public).decode())
  with h.sessions.begin() as db:
   db.add(RegisteredDevice(device_id='old-slot-two-fixture',student_id='DEVICE001',slot_number=2,public_key_spki=old_public,
    public_key_fingerprint=old_fingerprint,device_name='Existing tablet fixture',device_model='Fixture',platform='android',status='ACTIVE',registered_at=h.fixture.now))
 with h.sessions() as db:
  originals={d.device_id:{col.name:getattr(d,col.name) for col in RegisteredDevice.__table__.columns} for d in db.scalars(select(RegisteredDevice))}
 replacement_target=None
 if replacement_slot:
  old=next(d for d in originals.values() if d['slot_number']==replacement_slot)
  replacement_target={name:old[name] for name in ('device_id','slot_number','device_name','public_key_fingerprint')}
 original=slot_one_state()
 key=ec.generate_private_key(ec.SECP256R1());key_path=folder/'candidate.pem'
 key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
 public=key.public_key().public_bytes(serialization.Encoding.DER,serialization.PublicFormat.SubjectPublicKeyInfo)
 public,fingerprint=canonical_public_key(__import__('base64').b64encode(public).decode())
 class EndToEndFixtureProvider(FixtureProvider):
  def find_fresh_approval(self,db,binding,now):
   # A separate trusted test result is provisioned by this TEST fixture only.
   # It never reads/promotes B3 state, IDs, flags or historical test results.
   grant=db.scalar(select(FixtureGrant).where(FixtureGrant.binding==json.dumps(binding.__dict__)).with_for_update())
   if grant is None:
    identifier='fixture-'+secrets.token_hex(12);result_id='trusted-fixture-'+secrets.token_hex(12)
    db.add(FixtureResult(result_id=result_id,binding=json.dumps(binding.__dict__),revision_id='revision-1',
      face_verified=True,liveness_verified=True,classification='TRUSTED_SERVER_RESULT',verified_at=now,expires_at=now+timedelta(seconds=60)))
    db.add(FixtureGrant(approval_id=identifier,result_id=result_id,binding=json.dumps(binding.__dict__),revision_id='revision-1',
      result='PASS',verified_at=now,expires_at=now+timedelta(seconds=60)))
    db.flush()
   return super().find_fresh_approval(db,binding,now)
 requests=[]
 app=h.fixture.app
 class TraceApplication:
  async def __call__(self,scope,receive,send):
   async def recorded(message):
    if scope['type']=='http' and message['type']=='http.response.start':
     requests.append({'method':scope['method'],'path':scope['path'],'status':message['status']})
    await send(message)
   await app(scope,receive,recorded)
 sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
 if port==8000:raise RuntimeError('Never use production port')
 config=uvicorn.Config(TraceApplication(),host='127.0.0.1',port=port,log_level='error',access_log=False)
 server=uvicorn.Server(config)
 manifest={'base_url':f'http://127.0.0.1:{port}','student':'DEVICE001','password':'test-password',
  'python':str(root/'backend/venv/Scripts/python.exe'),'signer':str(Path(__file__).with_name('slot2_fixture_signer.py')),
  'key_path':str(key_path),'public_key_spki':public,'public_key_fingerprint':fingerprint,
  'output_dir':str(folder),'replacement_target':replacement_target}
 manifest_path=folder/'manifest.json';manifest_path.write_text(json.dumps(manifest),encoding='utf-8')
 with patch('modules.devices.activation_service.trusted_approval_provider',return_value=EndToEndFixtureProvider()),patch('modules.devices.biometric_service.secrets.randbelow',return_value=2):
  thread=threading.Thread(target=server.run,kwargs={'sockets':[sock]},daemon=True);thread.start()
  deadline=time.monotonic()+20
  while not server.started:
   if time.monotonic()>deadline:raise RuntimeError('Isolated HTTP server failed to start')
   time.sleep(.05)
  env=os.environ.copy();env['SLOT2_E2E_MANIFEST']=str(manifest_path)
  result=subprocess.run(['C:/Users/yap10/flutter/bin/flutter.bat','test','test/slot2_end_to_end_test.dart','--reporter','expanded'],
    cwd=root/'frontend',env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=180)
  (folder/'flutter.log').write_text(result.stdout,encoding='utf-8')
  if result.returncode:print(result.stdout[-8000:]);raise RuntimeError('Flutter real-HTTP integration failed')
 with h.sessions() as db:
  devices=db.scalars(select(RegisteredDevice).where(RegisteredDevice.student_id=='DEVICE001',RegisteredDevice.status=='ACTIVE').order_by(RegisteredDevice.slot_number)).all()
  assert len(devices)==2 and devices[(replacement_slot or 2)-1].public_key_fingerprint==fingerprint
  registered_rows=[{name:getattr(device,name) for name in ('device_id','student_id','slot_number','device_name','status','public_key_fingerprint')} for device in devices]
  assert db.scalar(select(__import__('sqlalchemy').func.count()).select_from(Attendance))==0
  assert db.scalar(select(__import__('sqlalchemy').func.count()).select_from(FixtureGrant).where(FixtureGrant.consumed_at!=None))==1
  assert db.scalar(select(__import__('sqlalchemy').func.count()).select_from(DeviceActivationChallenge).where(DeviceActivationChallenge.result=='PASS'))==1
 if replacement_slot:
  with h.sessions() as db:
   for identifier,old in originals.items():
    current=db.get(RegisteredDevice,identifier)
    if identifier==replacement_target['device_id']:
     assert current.status=='REVOKED' and current.revoked_at is not None
    else:assert {col.name:getattr(current,col.name) for col in RegisteredDevice.__table__.columns}==old
 else:assert slot_one_state()==original
 assert not any('/attendance' in row['path'] or row['path']=='/liveness/frame' for row in requests)
 evidence={'isolated_database':schema,'registered_device_rows':registered_rows,'http_requests':requests,'active_slots':[1,2],
  'slot_one_preserved':replacement_slot!=1,'replacement_slot':replacement_slot,'unaffected_slot_preserved':True,'old_target_revoked':bool(replacement_slot),'attendance_inserts':0,'single_use_grant_consumed':True,
  'real_p256_signature_verified':True,'flutter_my_device':'2 / 2 ACTIVE devices',
  'production_routes_or_configuration_modified_for_fixture':False}
 (folder/'result.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')
 print(json.dumps({'result':'PASS','evidence':str(folder/'result.json'),'ui':str(folder/'my-device-two-active.png'),
  'active_slots':[1,2],'replacement_slot':replacement_slot,'unaffected_slot_preserved':True,'attendance_inserts':0}))
finally:
 if server:server.should_exit=True
 if thread:thread.join(timeout=15)
 if h:h.tearDown()
 elif engine:engine.dispose()
 if created:
  if not re.fullmatch('attendance_slot2_e2e_[0-9a-f]{12}',schema) or schema==settings.db_name:raise RuntimeError('Unsafe isolated cleanup')
  with control.cursor() as c:c.execute('DROP DATABASE `'+schema+'`')
 control.close()
 for name in ('candidate.pem','manifest.json'):
  artifact=folder/name
  if artifact.parent.resolve()!=folder.resolve():raise RuntimeError('Unsafe temporary fixture cleanup')
  artifact.unlink(missing_ok=True)
