"""Mandatory final boundary; real ECDSA and isolated biometric/network fixtures."""
import base64,json,sys,unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient
from sqlalchemy import select,func,text
from models import Attendance,Challenge,AuthSession,Student,VerificationAttempt
from security import hash_password,digest
from modules.authorization.models import AttendanceDeviceChallenge,AttendanceAuthorizationEvent
from modules.authorization.service import AttendanceAuthorizationService
from modules.devices.models import RegisteredDevice
from modules.devices.crypto import canonical_public_key
from modules.devices.service import DeviceRegistrationError
from modules.networks.models import NetworkVerificationEvent
from services.attendance import record_verified_attendance
import test_workflow as workflow

class AttendanceAuthorizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.password_hash=hash_password('test-password');cls.bio_key=Fernet.generate_key().decode()
    def setUp(self):
        self.f=workflow.WorkflowTests();self.f.password_hash=self.password_hash;self.f.key=self.bio_key;self.f.setUp()
    def tearDown(self):self.f.tearDown()
    def count(self,model):
        with self.f.sessions() as db:return db.scalar(select(func.count()).select_from(model))
    def start(self):
        identifier=self.f.start();self.f.face(identifier);return identifier
    def issue(self,identifier,fingerprint=None,headers=None):
        return self.f.client.post('/api/v1/attendance/device-challenges',headers=headers or self.f.headers,json={'attendance_challenge_id':identifier,'public_key_fingerprint':fingerprint or self.f.device_fingerprint})
    def signature(self,proof,key=None):return base64.b64encode((key or self.f.device_key).sign(base64.b64decode(proof['signing_payload']),ec.ECDSA(hashes.SHA256()))).decode()
    def frame(self,identifier,proof=None,*,key=None,source=None,headers=None,extra=None,image=b'final-live'):
        fields={'challenge_id':identifier,**(extra or {})}
        if proof:fields.update(device_challenge_id=proof['challenge_id'],device_signature=self.signature(proof,key))
        client=self.f.client if source is None else TestClient(self.f.app,client=(source,12345))
        try:return client.post('/liveness/frame',headers=headers or self.f.headers,data=fields,files={'file':('frame.jpg',image,'image/jpeg')})
        finally:
            if source is not None:client.close()
    def ready(self):
        identifier=self.start();issued=self.issue(identifier);self.assertEqual(issued.status_code,201,issued.text);proof=issued.json()
        for i in range(2):self.assertEqual(self.frame(identifier,proof,image=('accepted-'+str(i)).encode()).status_code,200)
        return identifier,proof
    def denied(self,response,code):
        self.assertEqual(response.json()['code'],code,response.text);self.assertEqual(self.count(Attendance),0)
    def test_success_uses_single_attempt_nonce_and_fresh_network_then_replay_fails(self):
        identifier,proof=self.ready();payload=json.loads(base64.b64decode(proof['signing_payload']))
        self.assertEqual(payload['attendance_challenge_id'],identifier);self.assertEqual(payload['purpose'],'attendance_authorization')
        self.assertEqual(payload['student_id'],'TEST001');self.assertTrue(payload['auth_session_hash'])
        response=self.frame(identifier,proof);self.assertEqual(response.status_code,200,response.text);self.assertTrue(response.json()['complete'])
        self.assertEqual(self.count(Attendance),1);self.assertEqual(self.frame(identifier,proof,image=b'again').status_code,409)
        self.assertEqual(self.count(Attendance),1)
        with self.f.sessions() as db:
            nonce=db.get(AttendanceDeviceChallenge,proof['challenge_id']);self.assertEqual(nonce.result,'PASS');self.assertIsNotNone(nonce.consumed_at)
            event=db.scalar(select(AttendanceAuthorizationEvent).where(AttendanceAuthorizationEvent.result=='PASS'))
            network=db.get(NetworkVerificationEvent,event.network_verification_id)
            self.assertEqual(network.operation,'attendance_authorization');self.assertEqual(network.attendance_attempt_id,identifier);self.assertEqual(network.source_ip,'192.0.2.10')
        duplicate=self.f.client.post('/attendance/start',headers=self.f.headers,json={'pin':'123456'})
        self.assertEqual(duplicate.status_code,409);self.assertEqual(self.count(Attendance),1)
    def test_either_active_slot_can_sign_and_other_slot_is_preserved(self):
        key=ec.generate_private_key(ec.SECP256R1())
        public,fingerprint=canonical_public_key(base64.b64encode(key.public_key().public_bytes(serialization.Encoding.DER,serialization.PublicFormat.SubjectPublicKeyInfo)).decode())
        with self.f.sessions.begin() as db:
            old=db.get(RegisteredDevice,'workflow-fixture-device');original={c.name:getattr(old,c.name) for c in RegisteredDevice.__table__.columns}
            db.add(RegisteredDevice(device_id='slot-two-fixture',student_id='TEST001',slot_number=2,public_key_spki=public,public_key_fingerprint=fingerprint,device_name='Tablet fixture',device_model='test',platform='android',status='ACTIVE',registered_at=self.f.current))
        identifier=self.start();proof=self.issue(identifier,fingerprint).json();self.assertEqual(proof['slot_number'],2)
        for i in range(3):response=self.frame(identifier,proof,key=key,image=('slot2-'+str(i)).encode())
        self.assertEqual(response.status_code,200,response.text);self.assertEqual(self.count(Attendance),1)
        with self.f.sessions() as db:
            old=db.get(RegisteredDevice,'workflow-fixture-device');self.assertEqual({c.name:getattr(old,c.name) for c in RegisteredDevice.__table__.columns},original)
    def test_missing_proof_and_client_pass_flags_cannot_write(self):
        identifier,proof=self.ready()
        self.denied(self.frame(identifier,extra={'device_verified':'true','network_verified':'true','biometric_pass':'true'}),'ATTENDANCE_DEVICE_PROOF_REQUIRED')
    def test_invalid_signature_consumes_nonce_and_preserves_failure_audit(self):
        identifier,proof=self.ready();self.denied(self.frame(identifier,proof,key=ec.generate_private_key(ec.SECP256R1())),'ATTENDANCE_DEVICE_SIGNATURE_INVALID')
        with self.f.sessions() as db:
            self.assertEqual(db.get(AttendanceDeviceChallenge,proof['challenge_id']).result,'FAIL')
            self.assertIsNotNone(db.scalar(select(AttendanceAuthorizationEvent).where(AttendanceAuthorizationEvent.code=='ATTENDANCE_DEVICE_SIGNATURE_INVALID')))
        self.assertEqual(self.frame(identifier,proof,image=b'replayed-after-fail').status_code,409)
    def test_expired_attendance_signature_cannot_write(self):
        identifier,proof=self.ready();self.f.current+=timedelta(seconds=61)
        self.denied(self.frame(identifier,proof),'ATTENDANCE_DEVICE_PROOF_EXPIRED')
    def test_unknown_revoked_or_pending_device_cannot_obtain_attendance_proof(self):
        identifier=self.start()
        self.denied(self.issue(identifier,'0'*64),'ATTENDANCE_DEVICE_NOT_REGISTERED')
        with self.f.sessions.begin() as db:db.get(RegisteredDevice,'workflow-fixture-device').status='REVOKED'
        self.denied(self.issue(identifier),'ATTENDANCE_DEVICE_NOT_ACTIVE')
    def test_revocation_after_challenge_is_rechecked_at_the_insert_boundary(self):
        identifier,proof=self.ready()
        with self.f.sessions.begin() as db:db.get(RegisteredDevice,'workflow-fixture-device').status='REVOKED'
        self.denied(self.frame(identifier,proof),'ATTENDANCE_DEVICE_NOT_ACTIVE')
    def test_wrong_student_or_login_cannot_issue_or_submit(self):
        identifier,proof=self.ready()
        for student in ['TEST001','TEST002']:
            login=self.f.client.post('/login',json={'student_id':student,'password':'test-password'}).json()
            headers={'Authorization':'Bearer '+login['access_token']}
            self.denied(self.issue(identifier,headers=headers),'ATTENDANCE_ATTEMPT_MISMATCH')
            self.assertEqual(self.frame(identifier,proof,headers=headers).status_code,403)
        self.assertEqual(self.count(Attendance),0)
    def test_different_attendance_attempt_cannot_reuse_signature(self):
        first,proof=self.ready();second=self.start()
        for i in range(2):self.frame(second,image=('new-'+str(i)).encode())
        self.denied(self.frame(second,proof,image=b'new-final'),'ATTENDANCE_DEVICE_PROOF_MISMATCH')
    def test_profile_device_pass_is_never_an_attendance_proof(self):
        identifier,_=self.ready()
        issued=self.f.client.post('/api/v1/devices/verification-challenges',headers=self.f.headers,json={'operation':'device_status','public_key_fingerprint':self.f.device_fingerprint}).json()
        signature=self.signature(issued)
        self.assertEqual(self.f.client.post('/api/v1/devices/verifications',headers=self.f.headers,json={'operation':'device_status','challenge_id':issued['challenge_id'],'signature':signature}).status_code,200)
        self.denied(self.frame(identifier,issued),'ATTENDANCE_DEVICE_PROOF_MISMATCH')
    def test_network_is_rechecked_on_final_request_and_spoofed_headers_ignored(self):
        self.assertEqual(self.f.client.post('/api/v1/networks/verifications',headers=self.f.headers,json={}).json()['result'],'PASS')
        identifier,proof=self.ready()
        self.denied(self.frame(identifier,proof,source='198.51.100.7',headers={**self.f.headers,'X-Forwarded-For':'192.0.2.10'}),'NETWORK_NOT_AUTHORIZED')
        with self.f.sessions() as db:
            event=db.scalar(select(NetworkVerificationEvent).where(NetworkVerificationEvent.operation=='attendance_authorization'))
            self.assertEqual(event.source_ip,'198.51.100.7');self.assertEqual(event.result,'FAIL')
    def test_missing_disabled_or_invalid_policy_fail_closed(self):
        for mode in ['missing','disabled','invalid']:
            with self.subTest(mode=mode):
                if mode!='missing':
                    self.tearDown();self.setUp()
                identifier,proof=self.ready()
                with self.f.sessions.begin() as db:
                    if mode=='missing':db.execute(text('DELETE FROM network_policies'))
                    elif mode=='disabled':db.execute(text('UPDATE network_policies SET enabled=0'))
                    else:db.execute(text("UPDATE network_policies SET network_cidr='invalid'"))
                code='NETWORK_POLICY_INVALID' if mode=='invalid' else 'NO_ENABLED_NETWORK_POLICY'
                self.denied(self.frame(identifier,proof),code)
    def test_loopback_cannot_authorize_attendance(self):
        identifier,proof=self.ready();self.denied(self.frame(identifier,proof,source='127.0.0.1'),'LOOPBACK_SOURCE_NOT_AUTHORIZED')
    def test_failed_biometrics_never_reaches_writer(self):
        identifier=self.f.start();self.assertEqual(self.f.image('/verify-face',identifier,b'other-face').status_code,400)
        self.assertEqual(self.count(Attendance),0)
        self.assertNotEqual(self.issue(identifier).status_code,201)
    def test_existing_writer_cannot_be_called_without_biometrics_or_request_auth(self):
        identifier=self.start();proof=self.issue(identifier).json()
        with self.f.sessions() as db:
            student=db.get(Student,'TEST001');auth=db.get(AuthSession,digest(self.f.headers['Authorization'].split()[1]));attempt=db.get(Challenge,identifier)
            with self.assertRaises(DeviceRegistrationError) as raised:
                record_verified_attendance(self.f.app.state.context,db,student,attempt,db.get(__import__('models').ClassSession,attempt.session_id),auth=auth,request_scope={'client':('192.0.2.10',100)},device_challenge_id=proof['challenge_id'],device_signature=self.signature(proof))
            self.assertEqual(raised.exception.code,'ATTENDANCE_BIOMETRICS_REQUIRED');db.commit()
        self.assertEqual(self.count(Attendance),0)
    def test_late_insert_deadline_failure_rolls_back_attendance_but_audits_rejection(self):
        identifier,proof=self.ready();original=AttendanceAuthorizationService.fresh;calls=0
        def late(service,*args):
            nonlocal calls
            calls+=1
            if calls==3:raise DeviceRegistrationError(410,'ATTENDANCE_AUTHORIZATION_EXPIRED','Expired at insert')
            return original(service,*args)
        with patch.object(AttendanceAuthorizationService,'fresh',late):self.denied(self.frame(identifier,proof),'ATTENDANCE_AUTHORIZATION_EXPIRED')
        with self.f.sessions() as db:
            nonce=db.get(AttendanceDeviceChallenge,proof['challenge_id']);self.assertEqual(nonce.result,'FAIL')
            self.assertIsNotNone(db.scalar(select(AttendanceAuthorizationEvent).where(AttendanceAuthorizationEvent.code=='ATTENDANCE_AUTHORIZATION_EXPIRED')))

    def preflight_issue(self,identifier,**kwargs):
        return self.f.client.post('/api/v1/attendance/preflight-challenges',headers=self.f.headers,json={'attendance_challenge_id':identifier,'public_key_fingerprint':self.f.device_fingerprint},**kwargs)
    def preflight_confirm(self,identifier,proof,*,source=None,key=None,headers=None):
        client=self.f.client if source is None else TestClient(self.f.app,client=(source,12345))
        try:return client.post('/api/v1/attendance/preflight',headers=headers or self.f.headers,json={'attendance_challenge_id':identifier,'challenge_id':proof['challenge_id'],'signature':self.signature(proof,key)})
        finally:
            if source is not None:client.close()
    def test_preflight_passes_before_face_without_grant_or_attendance_and_cannot_replace_final_proof(self):
        identifier=self.f.start();proof=self.preflight_issue(identifier).json()
        self.assertEqual(proof['operation'],'attendance_preflight')
        response=self.preflight_confirm(identifier,proof);self.assertEqual(response.status_code,200,response.text)
        self.assertFalse(response.json()['attendance_authorized']);self.assertEqual(self.count(Attendance),0)
        with self.f.sessions() as db:self.assertEqual(db.get(Challenge,identifier).stage,'face')
        self.assertEqual(self.preflight_confirm(identifier,proof).status_code,409)
        self.f.face(identifier)
        for i in range(2):self.frame(identifier,image=('preflight-'+str(i)).encode())
        self.denied(self.frame(identifier,proof),'ATTENDANCE_DEVICE_PROOF_REPLAYED')
    def test_preflight_disabled_missing_invalid_policies_reject_before_camera(self):
        for mode in ['disabled','missing','invalid']:
            if mode!='disabled':self.tearDown();self.setUp()
            identifier=self.f.start()
            with self.f.sessions.begin() as db:
                db.execute(text({'disabled':'UPDATE network_policies SET enabled=0','missing':'DELETE FROM network_policies','invalid':"UPDATE network_policies SET network_cidr='invalid'"}[mode]))
            response=self.preflight_issue(identifier)
            self.denied(response,'NETWORK_POLICY_INVALID' if mode=='invalid' else 'NO_ENABLED_NETWORK_POLICY')
            self.assertEqual(self.count(AttendanceDeviceChallenge),0)
    def test_preflight_invalid_signature_expiry_revoked_and_wrong_session_fail(self):
        identifier=self.f.start();proof=self.preflight_issue(identifier).json()
        self.denied(self.preflight_confirm(identifier,proof,key=ec.generate_private_key(ec.SECP256R1())),'ATTENDANCE_DEVICE_SIGNATURE_INVALID')
        proof=self.preflight_issue(identifier).json();self.f.current+=timedelta(seconds=61)
        self.denied(self.preflight_confirm(identifier,proof),'ATTENDANCE_DEVICE_PROOF_EXPIRED')
        proof=self.preflight_issue(identifier).json()
        login=self.f.client.post('/login',json={'student_id':'TEST001','password':'test-password'}).json()
        self.denied(self.preflight_confirm(identifier,proof,headers={'Authorization':'Bearer '+login['access_token']}),'ATTENDANCE_ATTEMPT_MISMATCH')
        with self.f.sessions.begin() as db:db.get(RegisteredDevice,'workflow-fixture-device').status='REVOKED'
        self.denied(self.preflight_confirm(identifier,proof),'ATTENDANCE_DEVICE_NOT_ACTIVE')
    def test_preflight_confirm_rechecks_connection_and_ignores_spoofed_header(self):
        identifier=self.f.start();proof=self.preflight_issue(identifier).json()
        self.denied(self.preflight_confirm(identifier,proof,source='198.51.100.7',headers={**self.f.headers,'X-Forwarded-For':'192.0.2.10'}),'NETWORK_NOT_AUTHORIZED')
    def test_preflight_pass_then_policy_disabled_still_rejects_final_write(self):
        identifier=self.f.start();proof=self.preflight_issue(identifier).json()
        self.assertEqual(self.preflight_confirm(identifier,proof).status_code,200)
        self.f.face(identifier);final=self.issue(identifier).json()
        for i in range(2):self.frame(identifier,final,image=('later-'+str(i)).encode())
        with self.f.sessions.begin() as db:db.execute(text('UPDATE network_policies SET enabled=0'))
        self.denied(self.frame(identifier,final),'NO_ENABLED_NETWORK_POLICY')
    def test_preflight_pass_then_device_revoked_still_rejects_final_write(self):
        identifier=self.f.start();proof=self.preflight_issue(identifier).json()
        self.assertEqual(self.preflight_confirm(identifier,proof).status_code,200)
        self.f.face(identifier);final=self.issue(identifier).json()
        for i in range(2):self.frame(identifier,final,image=('revoke-'+str(i)).encode())
        with self.f.sessions.begin() as db:db.get(RegisteredDevice,'workflow-fixture-device').status='REVOKED'
        self.denied(self.frame(identifier,final),'ATTENDANCE_DEVICE_NOT_ACTIVE')
    def test_preflight_then_separate_final_proof_succeeds(self):
        identifier=self.f.start();early=self.preflight_issue(identifier).json()
        self.assertEqual(self.preflight_confirm(identifier,early).status_code,200)
        self.f.face(identifier);final=self.issue(identifier).json()
        self.assertNotEqual(early['challenge_id'],final['challenge_id'])
        for i in range(3):response=self.frame(identifier,final,image=('success-'+str(i)).encode())
        self.assertEqual(response.status_code,200,response.text);self.assertEqual(self.count(Attendance),1)
