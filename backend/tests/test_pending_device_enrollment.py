"""B2 security tests: real ECDSA, isolated fixtures, no biometric PASS bypass."""
import base64
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
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from config import Settings
from database import make_engine
from models import Attendance, ClassSession
from modules.devices.models import RegisteredDevice
from modules.devices.pending_models import PendingDeviceRegistration, DeviceEnrollmentEvent
from modules.devices.pending_migration import upgrade_pending_schema
from modules.devices.pending_service import PendingEnrollmentService
from modules.devices.approval_provider import ApprovalBinding, TrustedBiometricApproval, validate_approval, trusted_approval_provider
from modules.devices.service import DeviceRegistrationError
from security import hash_password
import test_device_verification as verification

PREFIX = "/api/v1/devices/pending-registrations"


class PendingDeviceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.password_hash=hash_password("test-password")

    def setUp(self):
        self.f=verification.DeviceVerificationTests()
        self.f.password_hash=self.password_hash
        if hasattr(self,"engine_override"): self.f.engine_override=self.engine_override
        self.f.setUp()
        self.key=ec.generate_private_key(ec.SECP256R1())
        self.body=self.f.fixture.body(self.key)

    def tearDown(self): self.f.tearDown()

    def begin(self, body=None, headers=None):
        return self.f.client.post(PREFIX,headers=headers or self.f.headers,json=body or self.body)

    def signed(self, pending, key=None):
        signature=(key or self.key).sign(base64.b64decode(pending["signing_payload"]),ec.ECDSA(hashes.SHA256()))
        return {"signature":base64.b64encode(signature).decode()}

    def prove(self, pending, key=None, headers=None):
        return self.f.client.post(PREFIX+"/"+pending["pending_registration_id"]+"/proof",headers=headers or self.f.headers,json=self.signed(pending,key))

    def count(self, model):
        with self.f.sessions() as db: return db.scalar(select(func.count()).select_from(model))

    def test_proof_is_bound_and_never_activates_or_records_attendance(self):
        classes=self.count(ClassSession)
        before=self.f.client.get("/api/v1/devices",headers=self.f.headers).json()["devices"]
        response=self.begin();self.assertEqual(response.status_code,201,response.text)
        pending=response.json();payload=json.loads(base64.b64decode(pending["signing_payload"]))
        self.assertEqual(payload["operation"],"enroll_second_device")
        self.assertEqual(payload["slot_number"],2)
        self.assertEqual(payload["student_id"],"DEVICE001")
        self.assertTrue(payload["auth_session_hash"])
        self.assertEqual(payload["candidate_device_id"],pending["candidate_device_id"])
        self.assertEqual(payload["public_key_fingerprint"],pending["public_key_fingerprint"])
        proven=self.prove(pending);self.assertEqual(proven.status_code,200,proven.text)
        self.assertEqual(proven.json()["status"],"KEY_PROVEN")
        self.assertFalse(proven.json()["activation_enabled"])
        self.assertFalse(proven.json()["attendance_authorized"])
        self.assertEqual(self.count(RegisteredDevice),1)
        self.assertEqual(self.count(Attendance),0);self.assertEqual(self.count(ClassSession),classes)
        self.assertEqual(self.f.client.get("/api/v1/devices",headers=self.f.headers).json()["devices"],before)
        check=self.f.issue();self.assertEqual(self.f.confirm(check.json()).status_code,200)
        with self.f.sessions() as db:
            events=db.scalars(select(DeviceEnrollmentEvent).order_by(DeviceEnrollmentEvent.event_id)).all()
            self.assertEqual([e.code for e in events],["PENDING_CREATED","CANDIDATE_KEY_PROVEN"])

    def test_invalid_signature_consumes_challenge_and_logs_failure(self):
        pending=self.begin().json()
        denied=self.prove(pending,self.f.key)
        self.assertEqual(denied.status_code,403);self.assertEqual(denied.json()["code"],"INVALID_SIGNATURE")
        self.assertEqual(self.prove(pending).status_code,409)
        with self.f.sessions() as db:
            row=db.get(PendingDeviceRegistration,pending["pending_registration_id"])
            self.assertEqual(row.status,"FAILED");self.assertIsNotNone(row.challenge_consumed_at)
            self.assertIsNotNone(db.scalar(select(DeviceEnrollmentEvent).where(DeviceEnrollmentEvent.code=="INVALID_SIGNATURE")))

    def test_expiry_replay_and_retry_keep_original_registration(self):
        pending=self.begin().json()
        self.f.fixture.now+=timedelta(seconds=121)
        self.assertEqual(self.prove(pending).status_code,410)
        again=self.begin().json();self.assertNotEqual(again["pending_registration_id"],pending["pending_registration_id"])
        self.assertEqual(self.prove(again).status_code,200)
        self.assertEqual(self.prove(again).status_code,409)
        self.f.fixture.now+=timedelta(minutes=6)
        denied=self.f.client.post('/api/v1/device-approvals',headers=self.f.headers,json={"pending_registration_id":again["pending_registration_id"]})
        self.assertEqual(denied.status_code,410)
        self.assertEqual(self.count(RegisteredDevice),1)

    def test_wrong_student_and_login_session_cannot_read_or_consume(self):
        pending=self.begin().json()
        for headers in (self.f.fixture.login("DEVICE002"),self.f.fixture.login("DEVICE001")):
            self.assertEqual(self.prove(pending,headers=headers).status_code,404)
            self.assertEqual(self.f.client.get(PREFIX+'/'+pending['pending_registration_id'],headers=headers).status_code,404)
            self.assertIsNone(self.f.client.get(PREFIX+'/current',headers=headers).json()['pending'])
        self.assertEqual(self.prove(pending).status_code,200)

    def test_duplicate_is_idempotent_without_resetting_expiry(self):
        first=self.begin().json()
        self.f.fixture.now+=timedelta(seconds=10)
        second=self.begin().json()
        self.assertEqual(first,second);self.assertEqual(self.count(PendingDeviceRegistration),1)
        body=self.f.fixture.body(ec.generate_private_key(ec.SECP256R1()))
        self.assertEqual(self.begin(body=body).json()["code"],"PENDING_EXISTS")
        self.assertEqual(self.begin(headers=self.f.fixture.login('DEVICE001')).json()['code'],'PENDING_EXISTS')
        self.assertEqual(self.prove(first).status_code,200)
        self.assertEqual(self.begin().json()["status"],"KEY_PROVEN")

    def test_registered_key_initial_endpoint_and_extra_flags_cannot_bypass(self):
        self.assertEqual(self.begin(body=self.f.fixture.body()).json()["code"],"KEY_ALREADY_REGISTERED")
        self.assertEqual(self.f.fixture.begin(body=self.body).json()["code"],"DEVICE_ALREADY_REGISTERED")
        for extra in ({"approved":True},{"slot_number":2},{"student_id":"DEVICE002"}):
            self.assertEqual(self.begin(body={**self.body,**extra}).status_code,422)
        response=self.f.client.post('/api/v1/device-approvals',headers=self.f.headers,json={'pending_registration_id':'p'*32,'biometric_pass':True})
        self.assertEqual(response.status_code,422)

    def test_trusted_provider_remains_closed_while_untrusted_biometrics_need_template(self):
        pending=self.begin().json();identifier=pending['pending_registration_id']
        body={'pending_registration_id':identifier}
        self.assertEqual(self.f.client.post('/api/v1/device-approvals',headers=self.f.headers,json=body).status_code,409)
        self.prove(pending)
        response=self.f.client.post('/api/v1/device-approvals',headers=self.f.headers,json=body)
        self.assertEqual(response.status_code,409);self.assertEqual(response.json()['code'],'BIOMETRIC_TEMPLATE_REQUIRED')
        for method,path in (('get',''),('post','/face'),('post','/liveness/frame')):
            response=getattr(self.f.client,method)('/api/v1/device-approvals/fabricated'+path,headers=self.f.headers)
            self.assertEqual(response.status_code,404 if method=='get' else 422)
        self.assertEqual(self.f.client.post(PREFIX+'/'+identifier+'/activate',headers=self.f.headers,json={'approval_id':'fake','challenge_id':'missing','signature':'invalid'}).status_code,404)
        self.assertEqual(self.count(RegisteredDevice),1);self.assertEqual(self.count(Attendance),0)
        service=PendingEnrollmentService(self.f.fixture.app.state.context)
        self.assertFalse(hasattr(service,'_activation_transaction'))
        self.assertFalse(hasattr(service,'activation_preparation'))

    def _identity(self,db):
        from models import Student,AuthSession
        from security import digest
        return db.get(Student,'DEVICE001'),db.get(AuthSession,digest(self.f.headers['Authorization'].split()[1]))

    def test_no_slot_one_or_historical_second_device_requires_other_workflow(self):
        other=self.f.fixture.login('DEVICE002')
        self.assertEqual(self.begin(headers=other).json()['code'],'INITIAL_REGISTRATION_REQUIRED')
        from modules.devices.crypto import canonical_public_key
        public,fingerprint=canonical_public_key(self.body['public_key_spki'])
        with self.f.sessions.begin() as db:
            db.add(RegisteredDevice(device_id='tablet',student_id='DEVICE001',slot_number=2,
                public_key_spki=public,public_key_fingerprint=fingerprint,device_name='Tablet',device_model='Test',platform='android',status='ACTIVE',registered_at=self.f.fixture.now))
        self.assertEqual(self.begin().json()['code'],'DEVICE_LIMIT_REACHED')
        with self.f.sessions.begin() as db: db.get(RegisteredDevice,'tablet').status='REVOKED'
        self.assertEqual(self.begin().json()['code'],'REPLACEMENT_REQUIRED')

    def test_missing_signature_and_missing_login_are_rejected(self):
        pending=self.begin().json()
        path=PREFIX+'/'+pending['pending_registration_id']+'/proof'
        self.assertEqual(self.f.client.post(path,headers=self.f.headers,json={}).status_code,422)
        self.assertEqual(self.f.client.post(PREFIX,json=self.body).status_code,401)
        self.assertEqual(self.prove(pending).status_code,200)

    def test_pending_database_constraints(self):
        pending=self.begin().json()
        with self.assertRaises(IntegrityError):
            with self.f.sessions.begin() as db:
                row=db.get(PendingDeviceRegistration,pending['pending_registration_id'])
                row.slot_number=3
        with self.assertRaises(IntegrityError):
            with self.f.sessions.begin() as db:
                row=db.get(PendingDeviceRegistration,pending['pending_registration_id'])
                row.status='ACTIVE'

    def test_missing_untrusted_stale_reused_mismatched_server_approvals(self):
        now=self.f.fixture.now
        binding=ApprovalBinding('DEVICE001','session','pending','candidate','f'*64)
        good=TrustedBiometricApproval('approval',binding,'revision',True,'PASS',now,now+timedelta(seconds=60))
        self.assertIs(validate_approval(good,'approval',binding,now),good)
        variants=[(None,'BIOMETRIC_TRUST_REQUIRED'),(replace(good,template_trusted=False),'BIOMETRIC_TRUST_REQUIRED'),
            (replace(good,trusted_template_revision_id=''),'BIOMETRIC_TRUST_REQUIRED'),
            (replace(good,result='FAIL'),'BIOMETRIC_TRUST_REQUIRED'),
            (replace(good,expires_at=now),'APPROVAL_EXPIRED'),
            (replace(good,consumed_at=now),'APPROVAL_USED'),
            (replace(good,verified_at=now-timedelta(seconds=61)),'APPROVAL_EXPIRED')]
        for field in ('student_id','auth_token_hash','pending_registration_id','candidate_device_id','public_key_fingerprint','operation','slot_number'):
            variants.append((replace(good,binding=replace(binding,**{field:3 if field=='slot_number' else 'wrong'})),'APPROVAL_MISMATCH'))
        for approval,code in variants:
            with self.assertRaises(DeviceRegistrationError) as denied: validate_approval(approval,'approval',binding,now)
            self.assertEqual(denied.exception.code,code)
        with self.assertRaises(DeviceRegistrationError) as denied: trusted_approval_provider().validate_and_lock(None,'approval',binding,now)
        self.assertEqual(denied.exception.code,'APPROVAL_UNAVAILABLE')


@unittest.skipUnless(os.getenv('ATTENDANCE_DEVICE_MYSQL_TESTS')=='1','Opt-in isolated MariaDB B2 races.')
class PendingMariaDBTests(unittest.TestCase):
    def test_concurrent_creation_proof_and_resumable_schema(self):
        import mysql.connector
        settings=Settings();schema='attendance_b2_test_'+secrets.token_hex(6)
        control=mysql.connector.connect(host=settings.db_host,port=settings.db_port,user=settings.db_user,password=settings.db_password)
        harness=PendingDeviceTests();created=False;engine=None
        try:
            with control.cursor() as c:c.execute('CREATE DATABASE `'+schema+'` CHARACTER SET utf8mb4')
            created=True;engine=make_engine(replace(settings,db_name=schema))
            harness.engine_override=engine;harness.password_hash=hash_password('test-password');harness.setUp()
            report=upgrade_pending_schema(engine);self.assertEqual(report['created_tables'],[])
            f=harness.f
            second_key=ec.generate_private_key(ec.SECP256R1())
            bodies=[harness.body,f.fixture.body(second_key)]
            def create(body):
                with TestClient(f.fixture.app) as client:
                    return client.post(PREFIX,headers=f.headers,json=body)
            with ThreadPoolExecutor(max_workers=2) as pool: results=list(pool.map(create,bodies))
            self.assertEqual(sorted(r.status_code for r in results),[201,409])
            winner=next(r.json() for r in results if r.status_code==201)
            from modules.devices.crypto import canonical_public_key
            winner_key=harness.key if winner['public_key_fingerprint']==canonical_public_key(harness.body['public_key_spki'])[1] else second_key
            proof=harness.signed(winner,winner_key);expected=[200,409]
            def submit(_):
                with TestClient(f.fixture.app) as client:
                    return client.post(PREFIX+'/'+winner['pending_registration_id']+'/proof',headers=f.headers,json=proof).status_code
            with ThreadPoolExecutor(max_workers=2) as pool: statuses=list(pool.map(submit,range(2)))
            self.assertEqual(sorted(statuses),expected)
            self.assertEqual(harness.count(PendingDeviceRegistration),1)
            self.assertEqual(harness.count(RegisteredDevice),1)
            self.assertEqual(harness.count(Attendance),0)
            self.assertEqual(upgrade_pending_schema(engine)['created_tables'],[])
        finally:
            if hasattr(harness,'f'):harness.tearDown()
            elif engine:engine.dispose()
            if created:
                if not re.fullmatch('attendance_b2_test_[0-9a-f]{12}',schema):raise RuntimeError('Unsafe test cleanup')
                with control.cursor() as c:c.execute('DROP DATABASE `'+schema+'`')
            control.close()
