"""Real API/security state machine with deterministic partner inference fixtures."""
import json
import os
import re
import secrets
import sys
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from sqlalchemy import select
from config import Settings
from database import make_engine
from models import Student,Attendance,ClassSession,VerificationAttempt
from modules.devices.models import RegisteredDevice
from modules.devices.biometric_models import DeviceBiometricSession,DeviceBiometricEvent
from modules.devices.biometric_migration import upgrade_biometric_schema
from modules.devices.pending_models import PendingDeviceRegistration
from modules.devices.approval_provider import trusted_approval_provider,ApprovalBinding
from modules.devices.service import DeviceRegistrationError
from security import encrypt_encoding,hash_password
import test_pending_device_enrollment as pending_tests

PREFIX='/api/v1/device-approvals'


class DeviceBiometricTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.password_hash=hash_password('test-password')

    def setUp(self):
        self.p=pending_tests.PendingDeviceTests();self.p.password_hash=self.password_hash
        if hasattr(self,'engine_override'):self.p.engine_override=self.engine_override
        self.p.setUp();self.f=self.p.f
        with self.f.sessions.begin() as db:
            student=db.get(Student,'DEVICE001');student.face_encoding=encrypt_encoding([0.0]*128,self.f.fixture.settings.biometric_key);student.biometric_status='active'
        self.pending=self.p.begin().json();self.p.prove(self.pending)

    def tearDown(self):self.p.tearDown()

    def create(self,headers=None,pending=None):
        return self.f.client.post(PREFIX,headers=headers or self.f.headers,json={'pending_registration_id':pending or self.pending['pending_registration_id']})

    def frame(self,identifier,image=b'neutral-face',stage='face',headers=None,extra=None):
        return self.f.client.post(PREFIX+'/'+identifier+'/'+stage,headers=headers or self.f.headers,
            files={'file':('frame.jpg',image,'image/jpeg')},data=extra or {})

    def face(self):
        created=self.create();self.assertEqual(created.status_code,201,created.text)
        identifier=created.json()['approval_id'];response=self.frame(identifier)
        self.assertEqual(response.status_code,200,response.text)
        self.f.fixture.app.state.context.bio.gesture=response.json()['fingers']
        return identifier,response

    def complete(self):
        identifier,_=self.face()
        for index in range(3):
            response=self.frame(identifier,('live-frame-'+str(index)).encode(),'liveness/frame')
            self.assertEqual(response.status_code,200,response.text)
        return identifier,response

    def test_success_remains_untrusted_nonconsumable_and_creates_no_attendance(self):
        counts={model:self.p.count(model) for model in (Attendance,ClassSession,VerificationAttempt)}
        before=self.f.client.get('/api/v1/devices',headers=self.f.headers).json()['devices']
        identifier,response=self.complete();result=response.json()
        self.assertEqual(result['stage'],'COMPLETED_UNTRUSTED')
        self.assertTrue(result['face_verified']);self.assertTrue(result['liveness_verified']);self.assertTrue(result['complete'])
        self.assertEqual(result['result_classification'],'UNTRUSTED_TEST_RESULT')
        for field in ('trusted','consumable','activation_eligible','activation_enabled'):self.assertFalse(result[field])
        self.assertEqual(self.f.client.get(PREFIX+'/'+identifier,headers=self.f.headers).json()['stage'],'COMPLETED_UNTRUSTED')
        self.assertEqual(self.f.client.get('/api/v1/devices',headers=self.f.headers).json()['devices'],before)
        self.assertEqual(self.p.count(RegisteredDevice),1)
        for model,count in counts.items():self.assertEqual(self.p.count(model),count)
        self.assertEqual(self.f.client.post('/api/v1/devices/pending-registrations/'+self.pending['pending_registration_id']+'/activate',headers=self.f.headers,json={'approval_id':identifier,'challenge_id':'missing','signature':'invalid'}).status_code,404)
        with self.assertRaises(DeviceRegistrationError):trusted_approval_provider().validate_and_lock(None,identifier,ApprovalBinding('x','x','x','x','x'),self.f.fixture.now)

    def test_wrong_face_is_terminal_and_no_client_pass_flag_is_accepted(self):
        identifier=self.create().json()['approval_id']
        self.assertEqual(self.frame(identifier,b'other-face').json()['code'],'FACE_NOT_MATCHED')
        self.assertEqual(self.frame(identifier,b'neutral-new').status_code,409)
        self.assertEqual(self.frame(identifier,extra={'PASS':'true'}).status_code,422)

    def test_liveness_wrong_gesture_resets_then_can_recover(self):
        identifier,response=self.face()
        self.frame(identifier,b'live1','liveness/frame')
        self.f.fixture.app.state.context.bio.gesture=0
        wrong=self.frame(identifier,b'wrong-gesture','liveness/frame').json()
        self.assertFalse(wrong['complete']);self.assertEqual(wrong['valid_frames'],0)
        self.f.fixture.app.state.context.bio.gesture=response.json()['fingers']
        for i in range(3):last=self.frame(identifier,('retry-'+str(i)).encode(),'liveness/frame')
        self.assertEqual(last.json()['stage'],'COMPLETED_UNTRUSTED')

    def test_face_substitution_during_liveness_fails(self):
        identifier,_=self.face()
        denied=self.frame(identifier,b'other-face-substitution','liveness/frame')
        self.assertEqual(denied.status_code,403);self.assertEqual(denied.json()['code'],'FACE_SUBSTITUTED')

    def test_replayed_frame_and_completed_session_cannot_advance_again(self):
        identifier,_=self.face()
        denied=self.frame(identifier,b'neutral-face','liveness/frame')
        self.assertEqual(denied.status_code,409);self.assertEqual(denied.json()['code'],'FRAME_REPLAY')
        completed,_=self.complete()
        self.assertEqual(self.frame(completed,b'new-live','liveness/frame').status_code,409)

    def test_expiry_and_slow_inference_never_produce_pass(self):
        identifier=self.create().json()['approval_id']
        self.f.fixture.now+=timedelta(seconds=91)
        self.assertEqual(self.frame(identifier).status_code,410)
        new=self.create().json()['approval_id']
        bio=self.f.fixture.app.state.context.bio
        def slow(image):self.f.fixture.now+=timedelta(seconds=91);return [0.0]*128
        with patch.object(bio,'guided_face',side_effect=slow):
            denied=self.frame(new,b'slow-face')
        self.assertEqual(denied.status_code,410)

    def test_wrong_student_session_and_unknown_pending_are_rejected(self):
        identifier=self.create().json()['approval_id']
        for headers in (self.f.fixture.login('DEVICE002'),self.f.fixture.login('DEVICE001')):
            self.assertEqual(self.f.client.get(PREFIX+'/'+identifier,headers=headers).status_code,404)
            self.assertEqual(self.frame(identifier,headers=headers).status_code,404)
            self.assertEqual(self.create(headers=headers).status_code,404)
        self.assertEqual(self.create(pending='missing-pending-registration').status_code,404)
        self.assertEqual(self.frame(identifier).status_code,200)

    def test_missing_unproven_and_expired_pending_are_rejected(self):
        with self.f.sessions.begin() as db:db.get(PendingDeviceRegistration,self.pending['pending_registration_id']).status='CHALLENGE_ISSUED'
        self.assertEqual(self.create().json()['code'],'CANDIDATE_PROOF_REQUIRED')
        with self.f.sessions.begin() as db:db.get(PendingDeviceRegistration,self.pending['pending_registration_id']).expires_at=self.f.fixture.now
        self.assertEqual(self.create().status_code,410)

    def test_template_replacement_invalidates_existing_test(self):
        identifier=self.create().json()['approval_id']
        with self.f.sessions.begin() as db:db.get(Student,'DEVICE001').face_encoding=encrypt_encoding([0.0]*128,self.f.fixture.settings.biometric_key)
        self.assertEqual(self.frame(identifier).json()['code'],'TEMPLATE_CHANGED')

    def test_candidate_binding_mismatch_is_rejected(self):
        identifier=self.create().json()['approval_id']
        with self.f.sessions.begin() as db:db.get(DeviceBiometricSession,identifier).public_key_fingerprint='f'*64
        self.assertEqual(self.frame(identifier).json()['code'],'BIOMETRIC_BINDING_MISMATCH')

    def test_random_challenge_is_server_generated_and_begin_retry_is_idempotent(self):
        first=self.create().json();second=self.create().json()
        self.assertEqual(first['approval_id'],second['approval_id']);self.assertEqual(first['expires_at'],second['expires_at'])
        with patch('modules.devices.biometric_service.secrets.randbelow',return_value=4) as random:
            face=self.frame(first['approval_id']).json()
        random.assert_called_once_with(5);self.assertEqual(face['fingers'],5)
        self.assertEqual(self.f.client.post(PREFIX,headers=self.f.headers,json={'pending_registration_id':self.pending['pending_registration_id'],'trusted':True}).status_code,422)

    def test_controlled_randomness_covers_all_five_fresh_challenges(self):
        identifiers=[]
        with patch('modules.devices.biometric_service.secrets.randbelow',side_effect=range(5)) as random:
            for expected in range(1,6):
                created=self.create().json();identifier=created['approval_id']
                identifiers.append(identifier)
                self.assertIsNone(created['fingers'])
                matched=self.frame(identifier).json()
                self.assertEqual(matched['fingers'],expected)
                self.assertEqual(matched['stage'],'LIVENESS')
                # End this isolated test session through a genuine wrong-face rejection.
                denied=self.frame(identifier,b'other-face-'+str(expected).encode(),'liveness/frame')
                self.assertEqual(denied.status_code,403)
            self.assertEqual(random.call_args_list,[unittest.mock.call(5)]*5)
        self.assertEqual(len(set(identifiers)),5)
        self.assertEqual(self.p.count(Attendance),0)
        self.assertEqual(self.p.count(RegisteredDevice),1)

    def test_session_reuse_keeps_one_gesture_and_three_frames_do_not_reroll(self):
        with patch('modules.devices.biometric_service.secrets.randbelow',side_effect=[2,2]) as random:
            created=self.create().json();identifier=created['approval_id']
            self.assertEqual(self.create().json()['approval_id'],identifier)
            random.assert_not_called()
            self.assertFalse(self.frame(identifier,b'no-face').json()['ready'])
            random.assert_not_called()
            face=self.frame(identifier).json()
            self.assertEqual(face['fingers'],3)
            self.f.fixture.app.state.context.bio.gesture=3
            self.assertEqual(self.create().json()['approval_id'],identifier)
            self.assertEqual(self.create().json()['fingers'],3)
            self.assertEqual(self.f.client.get(PREFIX+'/'+identifier,headers=self.f.headers).json()['fingers'],3)
            for count in (1,2,3):
                live=self.frame(identifier,('fresh-'+str(count)).encode(),'liveness/frame').json()
                self.assertEqual(live['fingers'],3)
                self.assertEqual(live['valid_frames'],count)
                self.assertEqual(live['complete'],count==3)
                random.assert_called_once_with(5)
            completed=self.create().json()
            self.assertEqual(completed['approval_id'],identifier)
            self.assertEqual(completed['expires_at'],created['expires_at'])
            self.assertEqual(completed['stage'],'COMPLETED_UNTRUSTED')
            random.assert_called_once_with(5)
            self.f.fixture.now+=timedelta(seconds=91)
            new=self.create().json()
            self.assertNotEqual(new['approval_id'],identifier)
            self.assertIsNone(new['fingers'])
            new_face=self.frame(new['approval_id']).json()
            # A genuinely fresh random draw is allowed to repeat the same value.
            self.assertEqual(new_face['fingers'],3)
            self.assertEqual(random.call_count,2)
            self.assertEqual(self.frame(identifier,b'expired-frame','liveness/frame').status_code,410)
        self.assertEqual(self.p.count(Attendance),0)

    def test_wrong_gesture_resets_progress_without_generating_a_new_challenge(self):
        with patch('modules.devices.biometric_service.secrets.randbelow',return_value=0) as random:
            identifier,face=self.face()
            self.assertEqual(face.json()['fingers'],1)
            accepted=self.frame(identifier,b'first-live','liveness/frame').json()
            self.assertEqual(accepted['valid_frames'],1)
            self.f.fixture.app.state.context.bio.gesture=2
            rejected=self.frame(identifier,b'wrong-gesture','liveness/frame').json()
            self.assertEqual(rejected['valid_frames'],0)
            self.assertEqual(rejected['fingers'],1)
            self.assertFalse(rejected['complete'])
            self.f.fixture.app.state.context.bio.gesture=1
            for count in (1,2,3):
                result=self.frame(identifier,('retry-live-'+str(count)).encode(),'liveness/frame').json()
                self.assertEqual(result['valid_frames'],count)
                self.assertEqual(result['fingers'],1)
                self.assertEqual(result['complete'],count==3)
            random.assert_called_once_with(5)
        self.assertEqual(self.p.count(Attendance),0)

    def test_quality_error_and_rate_limits(self):
        for i in range(5):
            identifier=self.create().json()['approval_id']
            adjust=self.frame(identifier,b'no-face-'+str(i).encode())
            self.assertEqual(adjust.status_code,200);self.assertFalse(adjust.json()['ready'])
            self.frame(identifier,b'other-face-'+str(i).encode())
        self.assertEqual(self.create().status_code,429)

    def test_inference_unavailable_is_audited_and_never_passes(self):
        identifier,_=self.face()
        with patch.object(self.f.fixture.app.state.context.bio,'hand',side_effect=RuntimeError('model missing')):
            denied=self.frame(identifier,b'hand-inference-unavailable','liveness/frame')
        self.assertEqual(denied.status_code,503)
        self.assertEqual(denied.json()['code'],'BIOMETRIC_ENGINE_UNAVAILABLE')
        self.assertEqual(self.p.count(Attendance),0)

    def test_adjustment_codes_and_safe_correlated_logs(self):
        from modules.biometrics.inference import BiometricError
        identifier=self.create().json()['approval_id']
        with patch.object(self.f.fixture.app.state.context.bio,'guided_face',side_effect=BiometricError('Move closer and keep your face inside the circle.')):
            with self.assertLogs('uvicorn.error',level='INFO') as logs:
                response=self.f.client.post(PREFIX+'/'+identifier+'/face',headers={**self.f.headers,'X-Request-ID':'b3-safe-test-1234'},files={'file':('frame.jpg',b'PRIVATE_IMAGE_SENTINEL','image/jpeg')})
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['feedback_code'],'FACE_TOO_SMALL')
        self.assertFalse(response.json()['face_verified'])
        self.assertEqual(response.headers['X-Request-ID'],'b3-safe-test-1234')
        output=' '.join(logs.output)
        self.assertIn('stage=face_detection_started',output)
        self.assertIn('code=FACE_TOO_SMALL',output)
        self.assertNotIn('PRIVATE_IMAGE_SENTINEL',output)
        self.assertNotIn(self.f.headers['Authorization'],output)
        self.assertNotIn('DEVICE001',output)
        self.assertEqual(self.p.count(Attendance),0)

    def test_frame_budget_and_audit_results(self):
        identifier=self.create().json()['approval_id']
        with self.f.sessions.begin() as db:db.get(DeviceBiometricSession,identifier).frame_count=60
        self.assertEqual(self.frame(identifier).json()['code'],'FRAME_LIMIT_REACHED')
        with self.f.sessions() as db:
            events=db.scalars(select(DeviceBiometricEvent).where(DeviceBiometricEvent.approval_id==identifier)).all()
            self.assertTrue(any(e.code=='FRAME_LIMIT_REACHED' and e.result=='FAIL' for e in events))


@unittest.skipUnless(os.getenv('ATTENDANCE_DEVICE_MYSQL_TESTS')=='1','Isolated MariaDB B3 concurrency.')
class DeviceBiometricMariaDBTests(unittest.TestCase):
    def test_concurrent_creation_and_frame_replay_and_migration(self):
        import mysql.connector
        settings=Settings();schema='attendance_b3_test_'+secrets.token_hex(6)
        control=mysql.connector.connect(host=settings.db_host,port=settings.db_port,user=settings.db_user,password=settings.db_password)
        harness=DeviceBiometricTests();created=False;engine=None
        try:
            with control.cursor() as c:c.execute('CREATE DATABASE `'+schema+'` CHARACTER SET utf8mb4')
            created=True;engine=make_engine(replace(settings,db_name=schema))
            harness.engine_override=engine;harness.password_hash=hash_password('test-password');harness.setUp()
            self.assertEqual(upgrade_biometric_schema(engine)['created_tables'],[])
            def begin(_):
                with TestClient(harness.f.fixture.app) as client:return client.post(PREFIX,headers=harness.f.headers,json={'pending_registration_id':harness.pending['pending_registration_id']})
            with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(begin,range(2)))
            self.assertEqual([r.status_code for r in results],[201,201])
            self.assertEqual(results[0].json()['approval_id'],results[1].json()['approval_id'])
            identifier=results[0].json()['approval_id']
            def submit(_):
                with TestClient(harness.f.fixture.app) as client:return client.post(PREFIX+'/'+identifier+'/face',headers=harness.f.headers,files={'file':('f.jpg',b'neutral-face','image/jpeg')}).status_code
            with ThreadPoolExecutor(max_workers=2) as pool:statuses=list(pool.map(submit,range(2)))
            self.assertEqual(sorted(statuses),[200,409])
            self.assertEqual(harness.p.count(RegisteredDevice),1);self.assertEqual(harness.p.count(Attendance),0)
        finally:
            if hasattr(harness,'p'):harness.tearDown()
            elif engine:engine.dispose()
            if created:
                if not re.fullmatch('attendance_b3_test_[0-9a-f]{12}',schema):raise RuntimeError('Unsafe test cleanup')
                with control.cursor() as c:c.execute('DROP DATABASE `'+schema+'`')
            control.close()
