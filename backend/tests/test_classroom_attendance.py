"""Synthetic biometric fixtures + real P-256 + actual single attendance writer.
Never evidence of physical face/liveness or hardware-key success.
"""
import base64,json,sys,unittest
from datetime import timedelta
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import hashes
from sqlalchemy import select
from fastapi.testclient import TestClient
from models import ClassSession,Challenge,Attendance
from security import hash_password
from modules.classroom_wifi.migration import upgrade
from modules.classroom_wifi.models import AttendanceWifiBinding,AttemptClassroom,SessionClassroom,WifiChallenge
from modules.classroom_wifi.policies import change
from modules.classroom_wifi.attendance import AttendanceClassroomService,configure
from modules.classroom_wifi.service import ClassroomWifiService
from modules.classroom_wifi.router import router
import test_attendance_authorization as authorization

PATH='/api/v1/classroom-wifi'


class ClassroomAttendanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.password_hash=hash_password('test-password');cls.bio_key=Fernet.generate_key().decode()
    def setUp(self):
        self.a=authorization.AttendanceAuthorizationTests();self.a.password_hash=self.password_hash;self.a.bio_key=self.bio_key
        if hasattr(self,'engine_override'):self.a.engine_override=self.engine_override
        self.a.setUp();self.f=self.a.f;upgrade(self.f.engine)
        self.f.app.include_router(router)
        self.provider=AttendanceClassroomService(self.f.app.state.context)
        self.f.app.state.context.classroom_attendance=self.provider
        self.sequence=0
        with self.f.sessions.begin() as db:
            change(db,'add',policy_id='a-home',classroom='A',access_point='d8:42:a1:9e:de:2f',network_name='Home',actor='test',now=self.f.current)
            self.session_id=db.scalar(select(ClassSession.session_id).order_by(ClassSession.session_id))
            configure(db,session_id=self.session_id,classroom_id='A',now=self.f.current)
    def tearDown(self):self.a.tearDown()

    def evidence(self,**updates):
        self.sequence+=1
        return {**dict(status='AVAILABLE',connection_type='WIFI',permission_status='PRECISE_GRANTED',
            wifi_enabled=True,wifi_connected=True,location_enabled=True,ssid='Home',bssid='d8:42:a1:9e:de:2f',
            rssi_dbm=-46,observed_at_ms=ClassroomWifiService(self.f.app.state.context).milliseconds(self.f.current)+self.sequence),**updates}
    def wifi(self,attempt,device,*,preflight=False,evidence=None,key=None,headers=None):
        headers=headers or self.f.headers
        r=self.f.client.post(PATH+'/attendance-challenges',headers=headers,json=dict(attendance_challenge_id=attempt,device_challenge_id=device['challenge_id'],preflight=preflight))
        self.assertEqual(r.status_code,201,r.text);ch=r.json()
        raw=json.dumps(evidence or self.evidence()).encode()
        sig=(key or self.f.device_key).sign(base64.b64decode(ch['signing_payload'])+b'\n'+raw,ec.ECDSA(hashes.SHA256()))
        body=dict(challenge_id=ch['challenge_id'],evidence_payload=base64.b64encode(raw).decode(),signature=base64.b64encode(sig).decode())
        r=self.f.client.post(PATH+'/verifications',headers=headers,json=body)
        return r,ch,body
    def ready(self):
        attempt=self.a.start();device=self.a.issue(attempt).json()
        self.assertTrue(device['classroom_wifi_required']);self.assertEqual(device['classroom_id'],'A')
        for i in range(2):self.a.frame(attempt,device,image=('prior'+str(i)).encode())
        return attempt,device
    def final(self,attempt,device,wifi,**kw):
        return self.a.frame(attempt,device,extra={'classroom_wifi_proof_id':wifi},**kw)
    def denied(self,response,code):self.a.denied(response,code)

    def test_authorized_final_commit_and_duplicate_preserves_single_attendance(self):
        attempt,device=self.ready();r,ch,_=self.wifi(attempt,device);self.assertEqual(r.json()['result'],'PASS',r.text)
        response=self.final(attempt,device,ch['challenge_id']);self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(self.a.count(Attendance),1)
        self.assertEqual(self.final(attempt,device,ch['challenge_id'],image=b'repeat').status_code,409)
        self.assertEqual(self.f.client.post('/attendance/start',headers=self.f.headers,json={'pin':'123456'}).status_code,409)
        with self.f.sessions() as db:self.assertIsNotNone(db.get(AttendanceWifiBinding,ch['challenge_id']).used_at)

    def test_same_authorized_ip_wrong_bssid_cannot_write(self):
        attempt,device=self.ready();r,ch,_=self.wifi(attempt,device,evidence=self.evidence(bssid='c6:0b:cc:3b:1b:1e'))
        self.assertEqual(r.json()['reason_code'],'WIFI_BSSID_MISMATCH')
        self.denied(self.final(attempt,device,ch['challenge_id']),'WIFI_BSSID_MISMATCH')

    def test_wrong_ip_correct_bssid_and_forwarding_spoof_cannot_write(self):
        attempt,device=self.ready();r,ch,_=self.wifi(attempt,device)
        self.denied(self.final(attempt,device,ch['challenge_id'],source='198.51.100.1',headers={**self.f.headers,'X-Forwarded-For':'192.0.2.10'}),'NETWORK_NOT_AUTHORIZED')

    def test_multiple_bssids_and_optional_ssid(self):
        with self.f.sessions.begin() as db:change(db,'add',policy_id='a-other',classroom='A',access_point='c6:0b:cc:3b:1b:1e',actor='test',now=self.f.current)
        attempt,device=self.ready();r,ch,_=self.wifi(attempt,device,evidence=self.evidence(bssid='c6:0b:cc:3b:1b:1e',ssid='Other',rssi_dbm=-120))
        self.assertEqual(r.json()['result'],'PASS');self.assertEqual(self.final(attempt,device,ch['challenge_id']).status_code,200)

    def test_disabled_policy_after_wifi_pass_rejected_at_final_commit(self):
        attempt,device=self.ready();r,ch,_=self.wifi(attempt,device)
        with self.f.sessions.begin() as db:change(db,'disable',policy_id='a-home',actor='test',now=self.f.current)
        self.denied(self.final(attempt,device,ch['challenge_id']),'NO_ENABLED_CLASSROOM_POLICY')

    def test_stale_receipt_after_biometric_delay_rejected_and_fresh_replacement_works(self):
        attempt,device=self.ready();r,ch,_=self.wifi(attempt,device)
        self.f.current+=timedelta(seconds=16)
        self.denied(self.final(attempt,device,ch['challenge_id']),'WIFI_EVIDENCE_STALE')

    def test_refresh_after_long_biometric_delay_uses_new_reading(self):
        attempt,device=self.ready();self.wifi(attempt,device)
        self.f.current+=timedelta(seconds=16)
        r,ch,_=self.wifi(attempt,device)
        self.assertEqual(self.final(attempt,device,ch['challenge_id']).status_code,200)

    def test_missing_proof_and_diagnostic_pass_do_not_authorize(self):
        attempt,device=self.ready()
        r=self.f.client.post(PATH+'/challenges',headers=self.f.headers,json={'classroom_id':'A','public_key_fingerprint':self.f.device_fingerprint})
        ch=r.json();raw=json.dumps(self.evidence()).encode()
        signature=self.f.device_key.sign(base64.b64decode(ch['signing_payload'])+b'\n'+raw,ec.ECDSA(hashes.SHA256()))
        self.f.client.post(PATH+'/verifications',headers=self.f.headers,json={'challenge_id':ch['challenge_id'],'evidence_payload':base64.b64encode(raw).decode(),'signature':base64.b64encode(signature).decode()})
        self.denied(self.final(attempt,device,ch['challenge_id']),'CLASSROOM_WIFI_BINDING_MISMATCH')

    def test_missing_wifi_proof_fail_closed(self):
        attempt,device=self.ready();self.denied(self.a.frame(attempt,device),'CLASSROOM_WIFI_PROOF_REQUIRED')

    def test_wrong_session_student_and_signature_rejected(self):
        attempt,device=self.ready();other=self.f.client.post('/login',json={'student_id':'TEST002','password':'test-password'}).json()
        r=self.f.client.post(PATH+'/attendance-challenges',headers={'Authorization':'Bearer '+other['access_token']},json={'attendance_challenge_id':attempt,'device_challenge_id':device['challenge_id']})
        self.assertEqual(r.status_code,403)
        r,ch,body=self.wifi(attempt,device,key=ec.generate_private_key(ec.SECP256R1()))
        self.assertEqual(r.json()['code'],'INVALID_DEVICE_SIGNATURE')
        self.assertEqual(self.a.count(Attendance),0)

    def test_wrong_device_receipt_binding_rejected(self):
        attempt,device=self.ready();r,ch,_=self.wifi(attempt,device)
        with self.f.sessions.begin() as db:db.get(WifiChallenge,ch['challenge_id']).key_fingerprint='0'*64
        self.denied(self.final(attempt,device,ch['challenge_id']),'CLASSROOM_WIFI_BINDING_MISMATCH')

    def test_nonce_expiry_and_replayed_confirmation(self):
        attempt,device=self.ready();r,ch,body=self.wifi(attempt,device)
        again=self.f.client.post(PATH+'/verifications',headers=self.f.headers,json=body)
        self.assertEqual(again.json()['code'],'WIFI_CHALLENGE_REPLAYED')
        self.f.current+=timedelta(seconds=46)
        self.denied(self.final(attempt,device,ch['challenge_id']),'WIFI_CHALLENGE_EXPIRED')

    def test_requirement_immutable_during_attempt_and_removal_explicit(self):
        attempt=self.f.start()
        with self.f.sessions.begin() as db:
            with self.assertRaisesRegex(ValueError,'CLASSROOM_REQUIREMENT_IN_USE'):
                configure(db,session_id=self.session_id,classroom_id=None,now=self.f.current)
        with self.f.sessions.begin() as db:
            db.get(Challenge,attempt).consumed=True
            configure(db,session_id=self.session_id,classroom_id=None,now=self.f.current)
        attempt,device=self.ready_without_requirement()
        self.assertFalse(device['classroom_wifi_required'])
        for i in range(3):r=self.a.frame(attempt,device,image=('unbound'+str(i)).encode())
        self.assertEqual(r.status_code,200,r.text)
    def ready_without_requirement(self):
        attempt=self.a.start();return attempt,self.a.issue(attempt).json()

    def test_changed_requirement_revision_invalidates_snapshot(self):
        attempt,device=self.ready();r,ch,_=self.wifi(attempt,device)
        with self.f.sessions.begin() as db:db.get(SessionClassroom,self.session_id).revision+=1
        self.denied(self.final(attempt,device,ch['challenge_id']),'CLASSROOM_REQUIREMENT_CHANGED')

    def test_deadline_crossed_inside_writer_savepoint_rolls_back_attendance(self):
        attempt,device=self.ready();r,ch,_=self.wifi(attempt,device)
        original=self.provider.fresh;calls=0
        def delayed(db,attempt,session):
            nonlocal calls
            calls+=1
            if calls==3:self.f.current+=timedelta(seconds=16)
            return original(db,attempt,session)
        with patch.object(self.provider,'fresh',side_effect=delayed):
            self.denied(self.final(attempt,device,ch['challenge_id']),'WIFI_EVIDENCE_STALE')

    def test_loopback_never_accepted_with_correct_wifi(self):
        attempt,device=self.ready();r,ch,_=self.wifi(attempt,device)
        self.denied(self.final(attempt,device,ch['challenge_id'],source='127.0.0.1'),'LOOPBACK_SOURCE_NOT_AUTHORIZED')

    def test_permission_unavailable_malformed_ssid_and_stale_cannot_authorize(self):
        cases=[({'permission_status':'DENIED'},'WIFI_PERMISSION_REQUIRED'),
            ({'wifi_connected':False},'WIFI_UNAVAILABLE'),({'bssid':'bad'},'WIFI_EVIDENCE_MALFORMED'),
            ({'ssid':'Wrong'},'WIFI_SSID_MISMATCH'),({'observed_at_ms':1},'WIFI_EVIDENCE_STALE')]
        for changes,code in cases:
            attempt,device=self.ready();r,ch,_=self.wifi(attempt,device,evidence=self.evidence(**changes))
            self.assertEqual(r.json().get('reason_code',r.json().get('code')),code,r.text)
            self.denied(self.final(attempt,device,ch['challenge_id']),code)

    def test_session_creation_with_classroom_uses_existing_operator(self):
        from manual_sessions import create_session
        with self.f.sessions.begin() as db:
            for session in db.scalars(select(ClassSession)):session.status='closed'
            row=create_session(db,now=self.f.current,timezone='Asia/Kuala_Lumpur',course_code='DEMO101',minutes=20,classroom_id='A')
            self.assertEqual(len(row['pin']),6)
            self.assertEqual(db.get(SessionClassroom,row['session_id']).classroom_id,'A')

    def test_wrong_attempt_receipt_cannot_cross_bind(self):
        first,device=self.ready();r,ch,_=self.wifi(first,device)
        second,second_device=self.ready()
        self.denied(self.final(second,second_device,ch['challenge_id']),'CLASSROOM_WIFI_BINDING_MISMATCH')

    def test_preflight_checks_wifi_before_camera_and_not_final_authority(self):
        attempt=self.f.start()
        device=self.f.client.post('/api/v1/attendance/preflight-challenges',headers=self.f.headers,json={'attendance_challenge_id':attempt,'public_key_fingerprint':self.f.device_fingerprint}).json()
        r,ch,_=self.wifi(attempt,device,preflight=True)
        response=self.f.client.post('/api/v1/attendance/preflight',headers=self.f.headers,json={'attendance_challenge_id':attempt,'challenge_id':device['challenge_id'],'signature':self.a.signature(device),'classroom_wifi_proof_id':ch['challenge_id']})
        self.assertEqual(response.status_code,200,response.text);self.assertFalse(response.json()['attendance_authorized'])
        self.f.face(attempt);device=self.a.issue(attempt).json()
        for i in range(2):self.a.frame(attempt,device,image=('preflight-frame'+str(i)).encode())
        self.denied(self.final(attempt,device,ch['challenge_id']),'CLASSROOM_WIFI_BINDING_MISMATCH')

    def test_concurrent_final_requests_insert_once_mariadb(self):
        if self.f.engine.dialect.name!='mysql':self.skipTest('MariaDB row-lock suite')
        attempt,device=self.ready();r,ch,_=self.wifi(attempt,device)
        def submit(i):return self.final(attempt,device,ch['challenge_id'],source='192.0.2.10',image=('concurrent'+str(i)).encode()).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(submit,range(2)))
        self.assertEqual(results.count(200),1);self.assertEqual(self.a.count(Attendance),1)
